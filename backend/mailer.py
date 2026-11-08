"""
Отправка писем: подтверждение почты и восстановление пароля.
Настройки почтового ящика берутся из config.py (а туда — из backend/.env).
"""

import smtplib
from email.message import EmailMessage

import config


def make_message(email, subject, intro, button_text, link, footer):
    """
    Функция, которая собирает письмо: тему, обычный текст и HTML-версию с кнопкой.
    """
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.MAIL_FROM
    message["To"] = email
    message.set_content(f"Привет!\n\n{intro}\n\n{link}\n\n{footer}")
    message.add_alternative(
        f"""
        <div style="font-family:Arial,sans-serif;font-size:16px;line-height:1.5;color:#141D4A">
          <p>Привет!</p>
          <p>{intro}</p>
          <p><a href="{link}" style="display:inline-block;padding:12px 22px;border-radius:999px;
          background:#3157D5;color:#fff;text-decoration:none">{button_text}</a></p>
          <p style="color:#525C79;font-size:14px">{footer}</p>
        </div>
        """,
        subtype="html",
    )

    return message


def send_message(message, link):
    """
    Функция, которая отправляет готовое письмо через SMTP.
    Если почта для отправки не настроена (SMTP_HOST пустой),
    письмо не отправляется, а ссылка печатается в терминал — так удобно проверять локально.
    """
    if not config.SMTP_HOST:
        print("\n========== ПИСЬМО (почта не настроена, поэтому оно не отправлено) ==========")
        print(f"Кому: {message['To']}")
        print(f"Тема: {message['Subject']}")
        print(f"Ссылка: {link}")
        print("============================================================================\n")
        return

    if config.SMTP_PORT == 465:
        server = smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, timeout=15)
    else:
        server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15)
        server.starttls()
    server.login(config.SMTP_USER, config.SMTP_PASSWORD)
    server.send_message(message)
    server.quit()


def send_confirm_email(email, code):
    """
    Функция, которая отправляет письмо со ссылкой для подтверждения почты.
    Ссылка ведёт на сервер: он подтверждает почту и возвращает человека на сайт.
    """
    link = f"{config.API_URL}/api/confirm?code={code}"
    message = make_message(
        email,
        "Подтверди почту на Training",
        "Ты зарегистрировался на Training — тренажёрах по матанализу. "
        "Чтобы подтвердить почту, открой ссылку:",
        "Подтвердить почту",
        link,
        f"Ссылка действует {config.CONFIRM_LINK_HOURS} часа. "
        "Если ты не регистрировался, просто удали это письмо.",
    )
    send_message(message, link)


def send_reset_email(email, code):
    """
    Функция, которая отправляет письмо со ссылкой для смены пароля.
    Ссылка ведёт на сайт: там откроется окно «Новый пароль».
    """
    link = f"{config.SITE_URL}/?reset={code}"
    message = make_message(
        email,
        "Восстановление пароля на Training",
        "Кто-то (надеемся, ты) попросил сменить пароль на Training. "
        "Чтобы придумать новый пароль, открой ссылку:",
        "Сменить пароль",
        link,
        f"Ссылка действует {config.RESET_LINK_HOURS} час и сработает один раз. "
        "Если ты не просил сменить пароль, просто удали это письмо — старый пароль продолжит работать.",
    )
    send_message(message, link)
