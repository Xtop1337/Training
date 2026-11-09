"""
Настройки бэкенда Training.
Всё, что может поменяться при переносе сервера на хостинг, собрано здесь.

Секреты (пароль от почты) в код не пишем: они лежат в файле backend/.env,
который не попадает в git. Образец — backend/.env.example.
"""

import os


# Папка, в которой лежит этот файл (backend/)
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))


def load_env_file(path):
    """
    Функция, которая читает файл .env со строками вида КЛЮЧ=значение
    и кладёт их в переменные окружения (os.environ).
    Если файла нет, ничего не делает.
    Переменные, уже заданные в системе, не перезаписываются,
    а пустые строки (КЛЮЧ=) пропускаются — тогда действует значение по умолчанию.
    """
    if not os.path.exists(path):
        return

    with open(path, encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            if value.strip():
                os.environ.setdefault(name.strip(), value.strip())


load_env_file(os.path.join(BACKEND_DIR, ".env"))


# База данных на хостинге — строка подключения к Postgres, например от Neon:
# postgresql://user:password@host/dbname?sslmode=require
# Если DATABASE_URL пустой, используется файл SQLite (удобно для запуска у себя).
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Файл базы данных SQLite. Создаётся сам при первом запуске сервера.
DATABASE_PATH = os.path.join(BACKEND_DIR, "training.db")

# Адрес и порт, на которых запускается сервер
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "5000"))

# Режим отладки: сервер сам перезапускается при изменении кода.
# На настоящем хостинге нужно поставить DEBUG=0 в .env.
DEBUG = os.environ.get("DEBUG", "1") == "1"

# Рабочий адрес сайта на Vercel. Подставляется на Render, если SITE_URL там не задан.
PRODUCTION_SITE_URL = "https://training-theta-eight.vercel.app"

# Render сам задаёт переменные RENDER и RENDER_EXTERNAL_URL (адрес сервиса, например
# https://training-mv0x.onrender.com). По ним понимаем, что сервер запущен на хостинге.
ON_RENDER = bool(os.environ.get("RENDER"))

# Адрес самого сервера: из него собирается ссылка в письме.
# Если API_URL не задан, на Render берётся его собственный адрес.
API_URL = (
    os.environ.get("API_URL") or os.environ.get("RENDER_EXTERNAL_URL") or "http://127.0.0.1:5000"
).strip().rstrip("/")

# Адрес сайта: сюда пользователь попадает после подтверждения почты.
# Если SITE_URL не задан, на Render это адрес сайта на Vercel, у себя — http://localhost:8000.
SITE_URL = (
    os.environ.get("SITE_URL") or (PRODUCTION_SITE_URL if ON_RENDER else "http://localhost:8000")
).strip().rstrip("/")

# Сайты, которым разрешено обращаться к API (CORS).
# Без этого браузер не даст странице с другого адреса читать ответы сервера.
# На хостинге адрес сайта (например, на Vercel) добавляется через переменную
# ALLOWED_ORIGINS — несколько адресов через запятую, без / в конце.
ALLOWED_ORIGINS = [
    PRODUCTION_SITE_URL,
    "https://xtop1337.github.io",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
for origin in os.environ.get("ALLOWED_ORIGINS", "").split(","):
    origin = origin.strip().rstrip("/")
    if origin and origin not in ALLOWED_ORIGINS:
        ALLOWED_ORIGINS.append(origin)

# Сайт из SITE_URL разрешается всегда, даже если его забыли вписать в ALLOWED_ORIGINS.
# Origin — это только схема и домен: из https://site.vercel.app/Training берётся https://site.vercel.app
_site_origin = "/".join(SITE_URL.split("/")[:3])
if _site_origin.startswith("http") and _site_origin not in ALLOWED_ORIGINS:
    ALLOWED_ORIGINS.append(_site_origin)

# Сколько дней действует вход, прежде чем придётся войти снова
SESSION_DAYS = 30

# Сколько часов действует ссылка из письма
CONFIRM_LINK_HOURS = 24

# Сколько часов действует ссылка для смены пароля
RESET_LINK_HOURS = 1

# Не чаще одного письма в столько секунд (защита от спама)
RESEND_PAUSE_SECONDS = 60

# Ограничения на почту и пароль. Всё пишется только латиницей:
# почта — латинские буквы, цифры и . _ % + - (домен тоже латиницей, например gmail.com);
# пароль — латинские буквы, цифры и знаки ASCII без пробелов.
EMAIL_MAX_LENGTH = 254
EMAIL_PATTERN = (
    r"[A-Za-z0-9._%+-]+@[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]*[A-Za-z0-9])?)*\.[A-Za-z]{2,}"
)
PASSWORD_MIN_LENGTH = 6
PASSWORD_MAX_LENGTH = 100
PASSWORD_PATTERN = r"[\x21-\x7E]+"

# Ник: 3–20 символов, латинские буквы, цифры, точка, _ и -; начинается с буквы или цифры
NICKNAME_MIN_LENGTH = 3
NICKNAME_MAX_LENGTH = 20
NICKNAME_PATTERN = r"[A-Za-z0-9][A-Za-z0-9_.-]{2,19}"

# Аватарка: картинка PNG, JPEG или WebP в виде data:-ссылки. Сайт сам уменьшает фото
# до 160×160, так что получается 5–20 КБ; больше этого предела сервер не примет.
AVATAR_MAX_BYTES = 80_000

# Ключи прогресса тренажёров — те же, что в localStorage на сайте
PROGRESS_KEYS = ["limits-progress-v1", "deriv-progress-v1", "integrals-progress-v1"]
PROGRESS_MAX_ITEMS = 1000

# Как отправляются письма — по первому заданному способу:
#   1) BREVO_API_KEY — через HTTP API сервиса Brevo (подходит для бесплатного Render,
#      где SMTP-порты закрыты);
#   2) SMTP_HOST — через обычный почтовый сервер (Яндекс, Mail.ru, Gmail);
#   3) ничего не задано — письмо не отправляется, а ссылка печатается в терминал.
BREVO_API_KEY = os.environ.get("BREVO_API_KEY", "")

# Имя отправителя, которое человек увидит в почте
MAIL_FROM_NAME = os.environ.get("MAIL_FROM_NAME", "Training")

SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
# Адрес отправителя; если не задан, берётся логин SMTP
MAIL_FROM = os.environ.get("MAIL_FROM") or SMTP_USER

# Настроена ли отправка писем (Brevo или SMTP)
MAIL_ENABLED = bool(BREVO_API_KEY or SMTP_HOST)

# Работают ли ссылки из писем: подтверждение почты и смена пароля.
# Почта настроена — письма уходят по-настоящему. У себя на компьютере без почты ссылка
# печатается в терминал. А на хостинге без почты письма никто не получит, поэтому:
#   - регистрация сразу открывает аккаунт, без подтверждения почты;
#   - восстановление пароля по почте недоступно.
# Подключишь Brevo (BREVO_API_KEY) — подтверждение и восстановление включатся сами.
EMAIL_LINKS = MAIL_ENABLED or not ON_RENDER
