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
    Переменные, уже заданные в системе, не перезаписываются.
    """
    if not os.path.exists(path):
        return

    with open(path, encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            name, value = line.split("=", 1)
            os.environ.setdefault(name.strip(), value.strip())


load_env_file(os.path.join(BACKEND_DIR, ".env"))


# Файл базы данных SQLite. Создаётся сам при первом запуске сервера.
DATABASE_PATH = os.path.join(BACKEND_DIR, "training.db")

# Адрес и порт, на которых запускается сервер
HOST = os.environ.get("HOST", "127.0.0.1")
PORT = int(os.environ.get("PORT", "5000"))

# Режим отладки: сервер сам перезапускается при изменении кода.
# На настоящем хостинге нужно поставить DEBUG=0 в .env.
DEBUG = os.environ.get("DEBUG", "1") == "1"

# Адрес самого сервера: из него собирается ссылка в письме.
API_URL = os.environ.get("API_URL", "http://127.0.0.1:5000")

# Адрес сайта: сюда пользователь попадает после подтверждения почты.
SITE_URL = os.environ.get("SITE_URL", "http://localhost:8000")

# Сайты, которым разрешено обращаться к API (CORS).
# Без этого браузер не даст странице с другого адреса читать ответы сервера.
ALLOWED_ORIGINS = [
    "https://xtop1337.github.io",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

# Сколько дней действует вход, прежде чем придётся войти снова
SESSION_DAYS = 30

# Сколько часов действует ссылка из письма
CONFIRM_LINK_HOURS = 24

# Сколько часов действует ссылка для смены пароля
RESET_LINK_HOURS = 1

# Не чаще одного письма в столько секунд (защита от спама)
RESEND_PAUSE_SECONDS = 60

# Ограничения на почту и пароль
EMAIL_MAX_LENGTH = 254
PASSWORD_MIN_LENGTH = 6
PASSWORD_MAX_LENGTH = 100

# Ключи прогресса тренажёров — те же, что в localStorage на сайте
PROGRESS_KEYS = ["limits-progress-v1", "deriv-progress-v1", "integrals-progress-v1"]
PROGRESS_MAX_ITEMS = 1000

# Почта, с которой уходят письма (SMTP).
# Если SMTP_HOST пустой, письма не отправляются, а ссылка печатается в терминал —
# так удобно проверять всё локально.
SMTP_HOST = os.environ.get("SMTP_HOST", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "465"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
MAIL_FROM = os.environ.get("MAIL_FROM", SMTP_USER)
