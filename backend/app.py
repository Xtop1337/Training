"""
Бэкенд сайта Training: регистрация по почте с подтверждением, вход, выход,
восстановление пароля и хранение прогресса в аккаунте.

Запуск (из корня проекта):
    python backend/app.py
Сервер откроется на http://127.0.0.1:5000

Адреса API:
    GET  /api/health    — проверка, что сервер работает
    POST /api/register  — регистрация:      {"email": "...", "password": "..."}
    GET  /api/confirm   — ссылка из письма: /api/confirm?code=...
    POST /api/resend    — письмо ещё раз:   {"email": "...", "password": "..."}
    POST /api/login     — вход:             {"email": "...", "password": "..."}
    POST /api/forgot    — забыл пароль:     {"email": "..."}  — придёт письмо со ссылкой
    POST /api/reset     — новый пароль:     {"code": "код из ссылки", "password": "..."}
    GET  /api/me        — кто вошёл
    POST /api/logout    — выход
    GET  /api/progress  — весь прогресс пользователя
    POST /api/progress  — сохранить прогресс: {"key": "limits-progress-v1", "data": {"0-1": true}}
    POST /api/profile   — настройки профиля: {"nickname": "...", "avatar": "data:image/webp;base64,..." или null}
Для /api/me, /api/logout, /api/progress и /api/profile нужен заголовок Authorization: Bearer <токен>.
Почта, пароль и ник принимаются только латиницей.
"""

import base64
import re
import smtplib

from flask import Flask, jsonify, redirect, request
from werkzeug.security import check_password_hash, generate_password_hash

import config
import database
import mailer


app = Flask(__name__)
# Чтобы русские буквы в ответах не превращались в коды вида Р
app.json.ensure_ascii = False


@app.after_request
def add_cors_headers(response):
    """
    Функция, которая добавляет к каждому ответу заголовки CORS.
    Сайт и сервер живут на разных адресах, и без этих заголовков
    браузер не даст странице прочитать ответ сервера.
    """
    origin = request.headers.get("Origin")
    if origin in config.ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Vary"] = "Origin"

    return response


# ---------- помощники ----------

def make_error(message, status, code=""):
    """
    Функция, которая собирает ответ с ошибкой в формате JSON,
    например {"error": "Неверная почта или пароль"}.
    code — короткое имя ошибки, по которому сайт понимает, что показать.
    """
    body = {"error": message}
    if code:
        body["code"] = code

    return jsonify(body), status


def read_json():
    """
    Функция, которая читает JSON из тела запроса.
    Если там не словарь, возвращает пустой словарь.
    """
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        data = {}

    return data


def read_email_and_password():
    """
    Функция, которая достаёт почту и пароль из тела запроса.
    Почта приводится к нижнему регистру.
    """
    data = read_json()
    email = str(data.get("email", "")).strip().lower()
    password = str(data.get("password", ""))

    return email, password


def read_token():
    """
    Функция, которая достаёт токен из заголовка Authorization: Bearer <токен>.
    Если заголовка нет, возвращает пустую строку.
    """
    header = request.headers.get("Authorization", "")
    token = ""
    if header.startswith("Bearer "):
        token = header[len("Bearer "):].strip()

    return token


def get_current_user():
    """
    Функция, которая по токену из заголовка находит вошедшего пользователя.
    Возвращает строку из таблицы users или None.
    """
    token = read_token()
    user = None
    if token:
        user = database.find_user_by_token(token)

    return user


def check_email(email):
    """
    Функция, которая проверяет, похожа ли строка на адрес почты.
    Возвращает текст ошибки или пустую строку, если всё хорошо.
    """
    error = ""
    if not email.isascii():
        error = "Почта пишется только латиницей, например name@gmail.com. Переключи раскладку на английскую."
    elif len(email) > config.EMAIL_MAX_LENGTH or not re.fullmatch(config.EMAIL_PATTERN, email, re.ASCII):
        error = "Похоже, в адресе почты ошибка. Пример: name@gmail.com"

    return error


def check_password(password):
    """
    Функция, которая проверяет пароль.
    Возвращает текст ошибки или пустую строку, если пароль подходит.
    """
    error = ""
    if password and not re.fullmatch(config.PASSWORD_PATTERN, password, re.ASCII):
        error = "Пароль — только латинские буквы, цифры и знаки, без русских букв и пробелов"
    elif len(password) < config.PASSWORD_MIN_LENGTH:
        error = f"Пароль должен быть не короче {config.PASSWORD_MIN_LENGTH} символов"
    elif len(password) > config.PASSWORD_MAX_LENGTH:
        error = f"Пароль должен быть не длиннее {config.PASSWORD_MAX_LENGTH} символов"

    return error


def make_user_info(user):
    """
    Функция, которая выбирает из строки базы данных то,
    что можно отдать сайту. Хеш пароля наружу не отдаётся.
    """
    user_info = {
        "email": user["email"],
        "name": user["nickname"] or user["email"].split("@")[0],
        "nickname": user["nickname"] or "",
        "avatar": user["avatar"] or "",
        "created_at": user["created_at"],
    }

    return user_info


def send_confirm_mail(user_id, email):
    """
    Функция, которая создаёт новую ссылку и отправляет письмо.
    Возвращает True, если письмо ушло, и False, если почтовый сервер не ответил.
    """
    code = database.create_email_code(user_id)
    sent = True
    try:
        mailer.send_confirm_email(email, code)
    except (smtplib.SMTPException, OSError) as error:
        print("Не удалось отправить письмо:", error)
        sent = False
    if sent:
        database.mark_mail_sent(user_id)

    return sent


def check_nickname(nickname):
    """
    Функция, которая проверяет ник. Возвращает текст ошибки или пустую строку.
    """
    error = ""
    if not nickname.isascii():
        error = "Ник пишется только латиницей. Переключи раскладку на английскую."
    elif not re.fullmatch(config.NICKNAME_PATTERN, nickname, re.ASCII):
        error = (f"Ник — от {config.NICKNAME_MIN_LENGTH} до {config.NICKNAME_MAX_LENGTH} символов: "
                 "латинские буквы, цифры, точка, _ и -. Начинается с буквы или цифры.")

    return error


# Первые байты файлов-картинок, которые принимаем в аватарку
IMAGE_SIGNATURES = {
    "png": lambda raw: raw.startswith(b"\x89PNG\r\n\x1a\n"),
    "jpeg": lambda raw: raw.startswith(b"\xff\xd8\xff"),
    "webp": lambda raw: raw[:4] == b"RIFF" and raw[8:12] == b"WEBP",
}


def check_avatar(avatar):
    """
    Функция, которая проверяет аватарку: data:-ссылку на картинку PNG, JPEG или WebP.
    Проверяет, что внутри действительно картинка этого типа и что она не слишком большая.
    Возвращает текст ошибки или пустую строку.
    """
    match = re.fullmatch(r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/]+={0,2})", avatar)
    if match is None:
        return "Аватарка — картинка PNG, JPEG или WebP"
    if len(match.group(2)) > config.AVATAR_MAX_BYTES * 4 // 3 + 4:
        return "Картинка слишком большая"
    try:
        raw = base64.b64decode(match.group(2), validate=True)
    except ValueError:
        return "Картинка повреждена"
    if not IMAGE_SIGNATURES[match.group(1)](raw):
        return "Картинка повреждена"

    return ""


def clean_progress(data):
    """
    Функция, которая проверяет прогресс, присланный сайтом,
    и оставляет только пары «номер задачи: true».
    Возвращает словарь или None, если данные не подходят.
    """
    if not isinstance(data, dict) or len(data) > config.PROGRESS_MAX_ITEMS:
        return None

    cleaned = {}
    for task_id, is_done in data.items():
        if isinstance(task_id, str) and len(task_id) <= 20 and is_done is True:
            cleaned[task_id] = True

    return cleaned


# ---------- адреса API ----------

def make_status():
    """
    Функция, которая собирает короткую сводку о сервере для проверки настроек.
    Секретов в ней нет: только какая база и почта включены и куда ведут ссылки.
    """
    if config.BREVO_API_KEY:
        mail = "brevo"
    elif config.SMTP_HOST:
        mail = "smtp"
    else:
        mail = "off"
    status = {
        "ok": True,
        "database": "postgres" if database.USE_POSTGRES else "sqlite",
        "mail": mail,
        "email_links": config.EMAIL_LINKS,
        "api_url": config.API_URL,
        "site_url": config.SITE_URL,
    }

    return status


@app.get("/")
def index():
    """
    Главная страница сервера. Сам сайт живёт на Vercel, а здесь только API,
    поэтому показываем, что сервер работает, и где что лежит.
    """
    status = make_status()
    status["service"] = "Training API"
    status["health"] = "/api/health"

    return jsonify(status)


@app.get("/api/health")
def health():
    """
    Функция для проверки, что сервер запущен и отвечает.
    """

    return jsonify(make_status())


@app.post("/api/register")
def register():
    """
    Функция регистрации: создаёт пользователя с неподтверждённой почтой
    и отправляет письмо со ссылкой. Войти можно только после подтверждения.
    """
    email, password = read_email_and_password()

    error = check_email(email) or check_password(password)
    if error:
        return make_error(error, 400)

    if database.find_user_by_email(email) is not None:
        return make_error("Эта почта уже зарегистрирована. Попробуй войти.", 409, "exists")

    try:
        user_id = database.add_user(email, generate_password_hash(password))
    except database.INTEGRITY_ERRORS:
        return make_error("Эта почта уже зарегистрирована. Попробуй войти.", 409, "exists")

    # Почта на хостинге не настроена: письмо не дойдёт, поэтому сразу открываем аккаунт
    if not config.EMAIL_LINKS:
        database.confirm_user(user_id)
        token = database.create_session(user_id)
        user = database.find_user_by_id(user_id)
        return jsonify({"token": token, "user": make_user_info(user), "message": "Аккаунт создан, ты вошёл."}), 201

    if not send_confirm_mail(user_id, email):
        return make_error(
            "Аккаунт создан, но письмо не отправилось. Попробуй войти — мы предложим отправить его ещё раз.",
            502,
            "mail_failed",
        )

    return jsonify({"email": email, "message": "Мы отправили письмо со ссылкой. Открой его, чтобы подтвердить почту."}), 201


@app.get("/api/confirm")
def confirm():
    """
    Функция, которая срабатывает, когда человек открывает ссылку из письма.
    Подтверждает почту и перенаправляет обратно на сайт.
    """
    code = request.args.get("code", "")
    confirmed = bool(code) and database.confirm_email(code)
    result = "1" if confirmed else "0"

    return redirect(f"{config.SITE_URL}/?confirmed={result}")


@app.post("/api/resend")
def resend():
    """
    Функция, которая отправляет письмо со ссылкой ещё раз.
    Нужны почта и пароль, чтобы никто не мог засыпать чужой ящик письмами.
    """
    email, password = read_email_and_password()

    user = database.find_user_by_email(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        return make_error("Неверная почта или пароль", 401)

    if user["is_confirmed"] or not config.EMAIL_LINKS:
        return jsonify({"message": "Почта уже подтверждена — можно входить."})

    if not database.can_send_mail(user):
        return make_error("Письмо уже отправлено. Подожди минуту и попробуй снова.", 429)

    if not send_confirm_mail(user["id"], user["email"]):
        return make_error("Не получилось отправить письмо, попробуй позже", 502)

    return jsonify({"message": "Отправили письмо ещё раз. Проверь почту и папку «Спам»."})


@app.post("/api/forgot")
def forgot_password():
    """
    Функция «Забыл пароль»: отправляет письмо со ссылкой для смены пароля.
    Ответ всегда одинаковый, есть такая почта в базе или нет, —
    чтобы по нему нельзя было узнать, кто зарегистрирован на сайте.
    """
    if not config.EMAIL_LINKS:
        return make_error("Восстановление пароля по почте пока недоступно.", 503, "no_mail")

    email = str(read_json().get("email", "")).strip().lower()

    error = check_email(email)
    if error:
        return make_error(error, 400)

    user = database.find_user_by_email(email)
    if user is not None and database.can_send_mail(user):
        code = database.create_password_code(user["id"])
        try:
            mailer.send_reset_email(user["email"], code)
            database.mark_mail_sent(user["id"])
        except (smtplib.SMTPException, OSError) as mail_error:
            print("Не удалось отправить письмо:", mail_error)
            return make_error("Не получилось отправить письмо, попробуй позже", 502)

    return jsonify({
        "message": "Если аккаунт с такой почтой есть, мы отправили на неё ссылку для смены пароля. "
                   "Она действует 1 час. Проверь и папку «Спам»."
    })


@app.post("/api/reset")
def reset_password():
    """
    Функция, которая меняет пароль по коду из ссылки в письме
    и сразу выполняет вход с новым паролем.
    """
    data = read_json()
    code = str(data.get("code", ""))
    password = str(data.get("password", ""))

    error = check_password(password)
    if error:
        return make_error(error, 400)

    user_id = None
    if code:
        user_id = database.reset_password(code, generate_password_hash(password))
    if user_id is None:
        return make_error("Ссылка устарела или уже использована. Запроси новую через «Забыл пароль?».", 400, "bad_code")

    token = database.create_session(user_id)
    user = database.find_user_by_id(user_id)

    return jsonify({"token": token, "user": make_user_info(user), "message": "Пароль изменён, ты вошёл в аккаунт."})


@app.post("/api/login")
def login():
    """
    Функция входа: проверяет почту и пароль и выдаёт новый токен.
    Если почта не подтверждена, войти нельзя.
    """
    email, password = read_email_and_password()

    if not (email + password).isascii():
        return make_error("Почта и пароль пишутся только латиницей. Переключи раскладку на английскую.", 400)

    user = database.find_user_by_email(email)
    if user is None or not check_password_hash(user["password_hash"], password):
        return make_error("Неверная почта или пароль", 401)

    if not user["is_confirmed"] and config.EMAIL_LINKS:
        return make_error("Сначала подтверди почту — ссылка в письме.", 403, "not_confirmed")

    token = database.create_session(user["id"])

    return jsonify({"token": token, "user": make_user_info(user)})


@app.get("/api/me")
def me():
    """
    Функция, которая по токену возвращает данные вошедшего пользователя.
    """
    user = get_current_user()
    if user is None:
        return make_error("Нужно войти в аккаунт", 401)

    return jsonify({"user": make_user_info(user)})


@app.post("/api/logout")
def logout():
    """
    Функция выхода: удаляет сессию, после этого токен больше не работает.
    """
    token = read_token()
    if token:
        database.delete_session(token)

    return jsonify({"ok": True})


@app.post("/api/profile")
def save_profile():
    """
    Функция, которая сохраняет настройки профиля: ник и аватарку.
    Можно прислать что-то одно. Пустой ник — показывать начало почты,
    пустая аватарка (null или "") — показывать первую букву имени.
    """
    user = get_current_user()
    if user is None:
        return make_error("Нужно войти в аккаунт", 401)

    data = read_json()
    nickname = None
    avatar = None
    if "nickname" in data:
        nickname = str(data.get("nickname") or "").strip()
        error = check_nickname(nickname) if nickname else ""
        if error:
            return make_error(error, 400, "bad_nickname")
    if "avatar" in data:
        avatar = str(data.get("avatar") or "")
        error = check_avatar(avatar) if avatar else ""
        if error:
            return make_error(error, 400, "bad_avatar")

    if "nickname" in data:
        database.set_nickname(user["id"], nickname or None)
    if "avatar" in data:
        database.set_avatar(user["id"], avatar or None)
    user = database.find_user_by_id(user["id"])

    return jsonify({"user": make_user_info(user), "message": "Профиль сохранён"})


@app.get("/api/progress")
def get_progress():
    """
    Функция, которая отдаёт весь прогресс пользователя по всем тренажёрам.
    """
    user = get_current_user()
    if user is None:
        return make_error("Нужно войти в аккаунт", 401)

    return jsonify({"progress": database.get_progress(user["id"])})


@app.post("/api/progress")
def save_progress():
    """
    Функция, которая сохраняет прогресс по одному тренажёру.
    """
    user = get_current_user()
    if user is None:
        return make_error("Нужно войти в аккаунт", 401)

    data = read_json()
    topic_key = data.get("key")
    progress = clean_progress(data.get("data"))
    if topic_key not in config.PROGRESS_KEYS or progress is None:
        return make_error("Неверные данные прогресса", 400)

    database.save_progress(user["id"], topic_key, progress)

    return jsonify({"ok": True})


def prepare_database():
    """
    Функция, которая создаёт таблицы (если их ещё нет) и удаляет просроченные записи.
    Вызывается сразу при загрузке файла: на хостинге сервер запускает gunicorn,
    и функция main() там не выполняется.
    """
    database.create_tables()
    database.delete_expired_rows()
    removed = database.delete_invalid_users()
    if removed:
        print("Удалены аккаунты с почтой не латиницей:", removed)
    if database.USE_POSTGRES:
        print("База данных: Postgres (DATABASE_URL)")
    else:
        print("База данных: SQLite,", config.DATABASE_PATH)
    if not config.BREVO_API_KEY and not config.SMTP_HOST:
        print("Почта для писем не настроена: ссылки из писем будут печататься здесь.")


prepare_database()


def main():
    """
    Функция, которая запускает сервер у себя на компьютере.
    На хостинге вместо неё работает команда: gunicorn app:app
    """
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)


if __name__ == "__main__":
    main()
