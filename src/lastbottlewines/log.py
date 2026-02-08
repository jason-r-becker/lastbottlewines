"""Logging configuration for lastbottlewines.

Provides:
- File-based logging to data/logs/lastbottlewines.log
- A BufferingHandler that collects errors and sends a single daily
  digest email to the owner (jason) via the notifier module.

Usage:
    from lastbottlewines.log import get_logger, send_error_digest

    logger = get_logger(__name__)
    logger.info("Something happened")
    logger.error("Something went wrong")

    # Call at end of main() to flush any buffered errors
    send_error_digest()
"""

import logging
import json
from datetime import datetime, timezone
from pathlib import Path

from lastbottlewines.utils import data_dir

LOG_DIR = data_dir("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "lastbottlewines.log"
ERROR_BUFFER_FILE = LOG_DIR / "error_buffer.json"


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger."""
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(logging.DEBUG)

        formatter = logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # File handler — all levels
        fh = logging.FileHandler(LOG_FILE)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        logger.addHandler(fh)

        # Buffer handler — errors only, writes to a JSON file for daily digest
        bh = _BufferingFileHandler(ERROR_BUFFER_FILE)
        bh.setLevel(logging.ERROR)
        bh.setFormatter(formatter)
        logger.addHandler(bh)

    return logger


class _BufferingFileHandler(logging.Handler):
    """Appends ERROR+ records to a JSON-lines file for daily digest."""

    def __init__(self, path: Path):
        super().__init__()
        self.path = path

    def emit(self, record):
        try:
            entry = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": self.format(record),
            }
            with open(self.path, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            self.handleError(record)


def _read_and_clear_buffer() -> list[dict]:
    """Read all buffered errors and clear the file."""
    if not ERROR_BUFFER_FILE.exists():
        return []

    entries = []
    with open(ERROR_BUFFER_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    entries.append({"message": line})

    # Clear the buffer
    ERROR_BUFFER_FILE.unlink(missing_ok=True)
    return entries


def send_error_digest() -> None:
    """Send a single email digest of all buffered errors to the owner.

    Reads jason's user config to get the email address.
    Should be called once at the end of each scheduled run.
    """
    errors = _read_and_clear_buffer()
    if not errors:
        return

    # Load jason's config for the owner email
    from lastbottlewines.config import load_user_config
    from lastbottlewines.notifier import _send_email

    owner_config_path = data_dir("user_configs") / "jason.yaml"
    if not owner_config_path.exists():
        # Can't send digest without owner config; log to file only
        logger = get_logger("lastbottlewines.log")
        logger.warning(
            "Cannot send error digest: jason.yaml not found at %s",
            owner_config_path,
        )
        return

    owner_config = load_user_config(owner_config_path)
    owner_email = owner_config.get("contact", {}).get("email")
    if not owner_email:
        return

    subject = f"Last Bottle Wines — Error Digest ({datetime.now(timezone.utc).strftime('%Y-%m-%d')})"
    body_lines = [
        f"Errors collected: {len(errors)}",
        f"Report time: {datetime.now(timezone.utc).isoformat()}\n",
        "=" * 60,
    ]
    for err in errors:
        body_lines.append(err.get("message", str(err)))
        body_lines.append("-" * 60)

    try:
        _send_email(owner_email, subject, "\n".join(body_lines))
    except Exception:
        # Last resort — already logged to file, nothing more we can do
        pass
