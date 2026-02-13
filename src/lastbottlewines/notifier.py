"""Simple notification helpers: email only.

Usage:
- Configure SMTP via environment variables: `SMTP_HOST`, `SMTP_PORT`,
  `SMTP_USER`, `SMTP_PASS`. If not provided, will try local SMTP at localhost:25.
- User config must include `contact` dict with key:
    - `email`: recipient email

Functions:
- `notify_user(config, wine_name, score, price, timestamp)` - high-level helper

This is intentionally minimal and uses only Python stdlib so it's free to run.
"""

import logging
import os
import smtplib
from email.message import EmailMessage
from typing import Optional

logger = logging.getLogger(__name__)


def _send_email(to_address: str, subject: str, body: str) -> None:
    """Send an email using SMTP. Reads config from environment variables.

    Falls back to localhost SMTP if no credentials are provided.
    """
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ.get(
        "SMTP_USER", f"no-reply@{os.environ.get('HOSTNAME', 'localhost')}"
    )
    msg["To"] = to_address
    msg.set_content(body)

    smtp_host = os.environ.get("SMTP_HOST")
    smtp_port = int(os.environ.get("SMTP_PORT", "0") or 0)
    smtp_user = os.environ.get("SMTP_USER")
    smtp_pass = os.environ.get("SMTP_PASS")

    if smtp_host and smtp_port:
        # Use provided SMTP server
        if smtp_user and smtp_pass:
            with smtplib.SMTP_SSL(smtp_host, smtp_port) as s:
                s.login(smtp_user, smtp_pass)
                s.send_message(msg)
        else:
            with smtplib.SMTP(smtp_host, smtp_port) as s:
                s.send_message(msg)
    else:
        # Fallback to local sendmail/SMTP (localhost:25)
        with smtplib.SMTP("localhost") as s:
            s.send_message(msg)


def notify_user(
    config: dict,
    wine_name: str,
    score: int,
    price: float,
) -> None:
    """High-level notify based on user config.

    config: user config dict loaded from YAML. Expected keys:
      - `contact` (dict): { email }
      - `notify_threshold` (int) optional
      - `always_notify_for` list of wine names
    """
    contact = config.get("contact", {})

    subject = f"Last Bottle Alert: {wine_name} — Score {score}"
    body = (
        f"Wine: {wine_name}\n"
        f"Price: ${price}\n"
        f"Score: {score}\n"
        f"\nPurchase link: https://lastbottlewines.com/\n"
    )

    try:
        email = config.get("email") or contact.get("email")
        if not email:
            raise ValueError("Email method requires `email` in contact config")
        _send_email(email, subject, body)
    except Exception as e:
        logger.error("Failed to send notification: %s", e)
