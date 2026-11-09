"""
Работа с базой данных.
Если в настройках задан DATABASE_URL (например, база Postgres на Neon), используется Postgres.
Если нет — файл SQLite backend/training.db: так удобно запускать сервер у себя без настройки.

В базе пять таблиц:
    users          — пользователи: почта, хеш пароля (сам пароль не хранится), подтверждена ли почта;
    sessions       — сессии, то есть «пропуска», которые выдаются после входа;
    email_codes    — одноразовые ссылки для подтверждения почты;
    password_codes — одноразовые ссылки для смены пароля;
    progress       — прогресс в тренажёрах: какие задачи решены.
"""

import hashlib
import json
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone

import config


# Postgres или SQLite — решается один раз при запуске
USE_POSTGRES = bool(config.DATABASE_URL)

if USE_POSTGRES:
    import psycopg
    from psycopg.rows import dict_row

    # Ошибка «такая запись уже есть» (например, повторная почта)
    INTEGRITY_ERRORS = (psycopg.IntegrityError,)
    # Столбец id, который сам увеличивается: в Postgres и SQLite он пишется по-разному
    ID_COLUMN = "id SERIAL PRIMARY KEY"
else:
    INTEGRITY_ERRORS = (sqlite3.IntegrityError,)
    ID_COLUMN = "id INTEGER PRIMARY KEY AUTOINCREMENT"


def get_connection():
    """
    Функция, которая открывает соединение с базой данных.
    Строки результата можно читать по имени столбца: user["email"].
    """
    if USE_POSTGRES:
        connection = psycopg.connect(config.DATABASE_URL, row_factory=dict_row)
    else:
        connection = sqlite3.connect(config.DATABASE_PATH)
        connection.row_factory = sqlite3.Row

    return connection


def run(connection, sql, params=()):
    """
    Функция, которая выполняет SQL-запрос и возвращает курсор с результатом.
    Во всех запросах места для значений отмечены знаком ?, как принято в SQLite.
    Postgres ждёт %s, поэтому для него знаки заменяются.
    """
    if USE_POSTGRES:
        sql = sql.replace("?", "%s")
    cursor = connection.execute(sql, params)

    return cursor


def get_time_text(days=0, hours=0, seconds=0):
    """
    Функция, которая возвращает время в UTC в виде текста,
    например "2026-11-08T14:52:32". Время можно сдвинуть вперёд или назад.
    """
    moment = datetime.now(timezone.utc) + timedelta(days=days, hours=hours, seconds=seconds)

    return moment.strftime("%Y-%m-%dT%H:%M:%S")


def hash_token(token):
    """
    Функция, которая превращает токен в хеш SHA-256.
    В базе хранится только хеш: если базу украдут, воспользоваться им не получится.
    """
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

    return token_hash


def remove_old_tables(connection):
    """
    Функция, которая удаляет таблицы от первой версии бэкенда,
    где вход был по логину, а не по почте. В них были только тестовые аккаунты.
    Первая версия жила только в SQLite, поэтому в Postgres проверять нечего.
    """
    if USE_POSTGRES:
        return

    columns = [row["name"] for row in connection.execute("PRAGMA table_info(users)")]
    if columns and "email" not in columns:
        print("В базе старая таблица users (вход по логину) — удаляю её и сессии.")
        run(connection, "DROP TABLE users")
        run(connection, "DROP TABLE IF EXISTS sessions")


def create_tables():
    """
    Функция, которая создаёт все таблицы, если их ещё нет в базе.
    """
    connection = get_connection()
    remove_old_tables(connection)
    run(
        connection,
        f"""
        CREATE TABLE IF NOT EXISTS users (
            {ID_COLUMN},
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_confirmed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            mail_sent_at TEXT
        )
        """
    )
    run(
        connection,
        """
        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """
    )
    run(
        connection,
        """
        CREATE TABLE IF NOT EXISTS email_codes (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """
    )
    run(
        connection,
        """
        CREATE TABLE IF NOT EXISTS password_codes (
            token_hash TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """
    )
    run(
        connection,
        """
        CREATE TABLE IF NOT EXISTS progress (
            user_id INTEGER NOT NULL,
            topic_key TEXT NOT NULL,
            data TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (user_id, topic_key),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """
    )
    connection.commit()
    connection.close()


# ---------- пользователи ----------

def find_user_by_email(email):
    """
    Функция, которая ищет пользователя по почте.
    Почта всегда хранится маленькими буквами (это делает app.py), поэтому регистр не важен.
    Возвращает строку из таблицы users или None, если такой почты нет.
    """
    connection = get_connection()
    user = run(connection, "SELECT * FROM users WHERE email = ?", (email.lower(),)).fetchone()
    connection.close()

    return user


def add_user(email, password_hash):
    """
    Функция, которая добавляет нового пользователя (почта пока не подтверждена).
    Возвращает id созданного пользователя.
    """
    connection = get_connection()
    try:
        row = run(
            connection,
            "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?) RETURNING id",
            (email.lower(), password_hash, get_time_text()),
        ).fetchone()
        connection.commit()
    finally:
        connection.close()
    user_id = row["id"]

    return user_id


def mark_mail_sent(user_id):
    """
    Функция, которая запоминает, когда пользователю отправили письмо.
    Нужна, чтобы не слать письма слишком часто.
    """
    connection = get_connection()
    run(connection, "UPDATE users SET mail_sent_at = ? WHERE id = ?", (get_time_text(), user_id))
    connection.commit()
    connection.close()


def can_send_mail(user):
    """
    Функция, которая проверяет, прошло ли достаточно времени с прошлого письма.
    """
    border = get_time_text(seconds=-config.RESEND_PAUSE_SECONDS)
    allowed = user["mail_sent_at"] is None or user["mail_sent_at"] <= border

    return allowed


def confirm_user(user_id):
    """
    Функция, которая отмечает почту пользователя подтверждённой без письма.
    Нужна, когда на хостинге почта не настроена и письмо со ссылкой отправить нельзя.
    """
    connection = get_connection()
    run(connection, "UPDATE users SET is_confirmed = 1 WHERE id = ?", (user_id,))
    connection.commit()
    connection.close()


# ---------- подтверждение почты ----------

def create_email_code(user_id):
    """
    Функция, которая создаёт одноразовый код для ссылки из письма.
    Старые коды этого пользователя удаляются: работает только последняя ссылка.
    Возвращает сам код (в базе хранится только его хеш).
    """
    code = secrets.token_urlsafe(32)
    connection = get_connection()
    run(connection, "DELETE FROM email_codes WHERE user_id = ?", (user_id,))
    run(
        connection,
        "INSERT INTO email_codes (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (hash_token(code), user_id, get_time_text(hours=config.CONFIRM_LINK_HOURS)),
    )
    connection.commit()
    connection.close()

    return code


def confirm_email(code):
    """
    Функция, которая подтверждает почту по коду из ссылки.
    Код после этого удаляется. Возвращает True, если всё получилось,
    и False, если код неверный или срок ссылки истёк.
    """
    connection = get_connection()
    row = run(
        connection,
        "SELECT user_id FROM email_codes WHERE token_hash = ? AND expires_at > ?",
        (hash_token(code), get_time_text()),
    ).fetchone()
    confirmed = row is not None
    if confirmed:
        run(connection, "UPDATE users SET is_confirmed = 1 WHERE id = ?", (row["user_id"],))
        run(connection, "DELETE FROM email_codes WHERE user_id = ?", (row["user_id"],))
        connection.commit()
    connection.close()

    return confirmed


# ---------- смена пароля ----------

def create_password_code(user_id):
    """
    Функция, которая создаёт одноразовый код для ссылки «сменить пароль».
    Старые коды этого пользователя удаляются: работает только последняя ссылка.
    Возвращает сам код (в базе хранится только его хеш).
    """
    code = secrets.token_urlsafe(32)
    connection = get_connection()
    run(connection, "DELETE FROM password_codes WHERE user_id = ?", (user_id,))
    run(
        connection,
        "INSERT INTO password_codes (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (hash_token(code), user_id, get_time_text(hours=config.RESET_LINK_HOURS)),
    )
    connection.commit()
    connection.close()

    return code


def reset_password(code, password_hash):
    """
    Функция, которая меняет пароль по коду из ссылки.
    Заодно:
        - подтверждает почту (раз человек открыл письмо, почта его);
        - удаляет код, чтобы ссылка сработала только один раз;
        - закрывает все сессии, чтобы старый пароль нигде больше не действовал.
    Возвращает id пользователя или None, если код неверный или срок ссылки истёк.
    """
    connection = get_connection()
    row = run(
        connection,
        "SELECT user_id FROM password_codes WHERE token_hash = ? AND expires_at > ?",
        (hash_token(code), get_time_text()),
    ).fetchone()
    user_id = None
    if row is not None:
        user_id = row["user_id"]
        run(
            connection,
            "UPDATE users SET password_hash = ?, is_confirmed = 1 WHERE id = ?", (password_hash, user_id)
        )
        run(connection, "DELETE FROM password_codes WHERE user_id = ?", (user_id,))
        run(connection, "DELETE FROM email_codes WHERE user_id = ?", (user_id,))
        run(connection, "DELETE FROM sessions WHERE user_id = ?", (user_id,))
        connection.commit()
    connection.close()

    return user_id


def find_user_by_id(user_id):
    """
    Функция, которая ищет пользователя по id.
    """
    connection = get_connection()
    user = run(connection, "SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    connection.close()

    return user


# ---------- сессии ----------

def create_session(user_id):
    """
    Функция, которая создаёт сессию для пользователя.
    Возвращает токен — случайную строку, которую сайт будет присылать
    в заголовке Authorization, чтобы сервер понимал, кто это.
    """
    token = secrets.token_urlsafe(32)
    connection = get_connection()
    run(
        connection,
        "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (hash_token(token), user_id, get_time_text(days=config.SESSION_DAYS)),
    )
    connection.commit()
    connection.close()

    return token


def find_user_by_token(token):
    """
    Функция, которая ищет пользователя по токену сессии.
    Возвращает строку из таблицы users
    или None, если токен неверный или срок сессии закончился.
    """
    connection = get_connection()
    user = run(
        connection,
        """
        SELECT users.*
        FROM sessions
        JOIN users ON users.id = sessions.user_id
        WHERE sessions.token_hash = ? AND sessions.expires_at > ?
        """,
        (hash_token(token), get_time_text()),
    ).fetchone()
    connection.close()

    return user


def delete_session(token):
    """
    Функция, которая удаляет сессию (выход из аккаунта).
    """
    connection = get_connection()
    run(connection, "DELETE FROM sessions WHERE token_hash = ?", (hash_token(token),))
    connection.commit()
    connection.close()


def delete_expired_rows():
    """
    Функция, которая удаляет из базы просроченные сессии и ссылки из писем.
    """
    now = get_time_text()
    connection = get_connection()
    run(connection, "DELETE FROM sessions WHERE expires_at <= ?", (now,))
    run(connection, "DELETE FROM email_codes WHERE expires_at <= ?", (now,))
    run(connection, "DELETE FROM password_codes WHERE expires_at <= ?", (now,))
    connection.commit()
    connection.close()


# ---------- прогресс ----------

def get_progress(user_id):
    """
    Функция, которая возвращает весь прогресс пользователя в виде словаря:
    {"limits-progress-v1": {"0-1": true, ...}, "deriv-progress-v1": {...}, ...}
    """
    connection = get_connection()
    rows = run(
        connection,
        "SELECT topic_key, data FROM progress WHERE user_id = ?", (user_id,)
    ).fetchall()
    connection.close()
    progress = {}
    for row in rows:
        progress[row["topic_key"]] = json.loads(row["data"])

    return progress


def save_progress(user_id, topic_key, data):
    """
    Функция, которая сохраняет прогресс по одному тренажёру.
    Если запись уже есть, она заменяется новой.
    """
    connection = get_connection()
    run(
        connection,
        """
        INSERT INTO progress (user_id, topic_key, data, updated_at) VALUES (?, ?, ?, ?)
        ON CONFLICT (user_id, topic_key) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at
        """,
        (user_id, topic_key, json.dumps(data), get_time_text()),
    )
    connection.commit()
    connection.close()
