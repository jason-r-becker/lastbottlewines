"""
Last Bottle Wines - Wine scoring and tracking system

Orchestrates scraping, scoring, and database operations for tracking
wine recommendations based on user preferences.
"""

import os
from datetime import datetime, timezone
from pathlib import Path

from lastbottlewines.scraper import scrape_last_bottle
from lastbottlewines.scorer import score_wine, generate_wine_scoring_prompt
from lastbottlewines.config import load_user_config, in_price_range
from lastbottlewines.wine_database import WineDatabase
from lastbottlewines.utils import data_dir
from lastbottlewines.notifier import notify_user
from lastbottlewines.log import get_logger, send_error_digest

logger = get_logger(__name__)


def _load_dotenv():
    """Load .env file into environment if it exists."""
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if not env_path.exists():
        return
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            key, _, value = line.partition("=")
            value = value.strip('"').strip("'")
            os.environ[key.strip()] = value


def main():
    """
    Main orchestration function.

    Scrapes the current wine, evaluates it against user preferences,
    scores it, and records everything in the database.
    """
    _load_dotenv()
    timestamp = datetime.now(timezone.utc)

    # Scrape the current wine
    result = scrape_last_bottle()
    if not result:
        logger.error("No wine data found from scraping.")
        send_error_digest()
        return

    wine_name, price = result

    db = WineDatabase()

    # Skip if this wine was already scored in the last 7 days
    if db.is_duplicate_wine(wine_name):
        logger.info("'%s' already scored in the last 7 days, skipping.", wine_name)
        db.close()
        send_error_digest()
        return

    wine_id = db.add_wine(wine_name, price, timestamp=timestamp)
    user_configs_dir = data_dir("user_configs")
    if not user_configs_dir.exists():
        logger.error("User configs directory not found: %s", user_configs_dir)
        db.close()
        send_error_digest()
        return

    for config_path in user_configs_dir.glob("*.yaml"):
        user_id = config_path.stem
        if user_id == 'template':
            continue

        try:
            user_config = load_user_config(config_path)
        except Exception as e:
            logger.error("Error loading config for %s: %s", user_id, e)
            continue

        # Check if wine is in price range
        if not in_price_range(price, user_config):
            continue

        # Generate scoring prompt and score
        prompt = generate_wine_scoring_prompt(wine_name, user_config)
        score = score_wine(prompt)

        if score is None:
            logger.error("Failed to score %s for %s", wine_name, user_id)
            continue

        logger.info("Score for %s (%s): %d", user_id, wine_name, score)

        # Record score in database
        db.add_user_score(user_id, wine_id, score, timestamp=timestamp)

        # Determine whether to notify the user
        notify_threshold = user_config.get("notify_threshold")
        always_notify = user_config.get("always_notify_for", [])
        should_notify = False

        if wine_name in always_notify:
            should_notify = True
        elif notify_threshold is not None and isinstance(notify_threshold, int):
            if score >= notify_threshold:
                should_notify = True

        if should_notify:
            try:
                notify_user(user_config, wine_name, score, price)
                logger.info("Notification sent to %s for %s", user_id, wine_name)
            except Exception as e:
                logger.error("Failed to send notification to %s: %s", user_id, e)

    db.close()
    send_error_digest()


if __name__ == "__main__":
    main()
