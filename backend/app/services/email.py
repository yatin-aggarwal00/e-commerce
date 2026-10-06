"""Transactional email.

The ``console`` backend (default) prints messages to the application log, which
is perfect for development and tests. The ``smtp`` backend sends real mail. In
production, point this at a provider such as SES, SendGrid or Postmark.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from app.core.config import settings

logger = logging.getLogger("app.email")


def send_email(to: str, subject: str, body: str) -> None:
    if settings.EMAIL_BACKEND == "smtp" and settings.SMTP_HOST:
        _send_smtp(to, subject, body)
    else:
        logger.info("EMAIL -> %s | %s\n%s", to, subject, body)


def _send_smtp(to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.EMAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        server.starttls()
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)


def send_order_confirmation(to: str, order_number: str, total_cents: int, currency: str) -> None:
    amount = f"{total_cents / 100:.2f} {currency.upper()}"
    send_email(
        to,
        f"Order {order_number} confirmed",
        f"Thank you for your purchase!\n\n"
        f"Your order {order_number} has been confirmed and paid ({amount}).\n"
        f"You can track it at {settings.FRONTEND_URL}/account/orders.\n",
    )


def send_order_status_update(to: str, order_number: str, status: str) -> None:
    send_email(
        to,
        f"Order {order_number} update: {status}",
        f"Your order {order_number} status is now: {status}.\n"
        f"Track it at {settings.FRONTEND_URL}/account/orders.\n",
    )


def send_password_reset(to: str, token: str) -> None:
    link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    send_email(
        to,
        "Reset your password",
        f"Use the link below to reset your password (valid for "
        f"{settings.PASSWORD_RESET_EXPIRE_MINUTES} minutes):\n\n{link}\n",
    )
