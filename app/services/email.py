import smtplib
from email.message import EmailMessage

from flask import current_app


def send_email(message: EmailMessage, purpose: str) -> bool:
    mail_server = current_app.config.get("MAIL_SERVER")
    if not mail_server:
        current_app.logger.warning(
            "%s email not sent: MAIL_SERVER is not configured",
            purpose
        )
        return False

    use_ssl = current_app.config.get("MAIL_USE_SSL")
    use_tls = current_app.config.get("MAIL_USE_TLS")
    if not use_ssl and not use_tls:
        current_app.logger.error(
            "%s email not sent: secure SMTP is not enabled",
            purpose
        )
        return False

    try:
        if use_ssl:
            server = smtplib.SMTP_SSL(
                mail_server,
                current_app.config["MAIL_PORT"],
                timeout=10
            )
        else:
            server = smtplib.SMTP(
                mail_server,
                current_app.config["MAIL_PORT"],
                timeout=10
            )

        with server:
            if use_tls and not use_ssl:
                server.starttls()
            username = current_app.config.get("MAIL_USERNAME")
            password = current_app.config.get("MAIL_PASSWORD")
            if username:
                server.login(username, password)
            server.send_message(message)
        return True
    except (smtplib.SMTPException, OSError):
        current_app.logger.exception("Could not send %s email", purpose)
        return False
