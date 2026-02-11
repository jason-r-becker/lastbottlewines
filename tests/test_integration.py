"""Integration tests for lastbottlewines.

These tests hit real external services (Gemini API, SMTP, lastbottlewines.com)
and require a valid .env file. Run with:

    uv run pytest tests/ -v

To run a specific test:
    uv run pytest tests/test_integration.py::test_prompt_generation -v
    uv run pytest tests/test_integration.py::test_gemini_scoring -v
    uv run pytest tests/test_integration.py::test_send_email -v
"""

import os
from pathlib import Path

import pytest
import yaml

# Use the app's own .env loader so tests use the same path as production
from lastbottlewines.last_bottle import _load_dotenv
_load_dotenv()

from lastbottlewines.config import load_user_config, in_price_range
from lastbottlewines.scorer import (
    generate_wine_scoring_prompt,
    score_wine,
)
from lastbottlewines.notifier import _send_email, notify_user
from lastbottlewines.scraper import scrape_last_bottle


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_CONFIG = {
    "profile": "I like bold reds and dry whites.",
    "types": ["Cabernet Sauvignon", "Chardonnay"],
    "price_range": [20, 100],
    "type_specific_price_ranges": {
        "Cabernet Sauvignon": [30, 80],
        "Chardonnay": [20, 60],
    },
    "always_notify_for": ["Opus One"],
    "never_notify_for": ["Yellow Tail"],
    "notify_threshold": 90,
    "contact": {"email": "you@example.com"},
}

SAMPLE_WINE = "2021 Château Margaux Grand Vin, Margaux"


@pytest.fixture
def config():
    return SAMPLE_CONFIG.copy()


@pytest.fixture
def user_config_path(tmp_path, config):
    """Write a temp YAML config and return its path."""
    p = tmp_path / "testuser.yaml"
    with open(p, "w") as f:
        yaml.dump(config, f)
    return p


# ---------------------------------------------------------------------------
# 1. Config loading
# ---------------------------------------------------------------------------


class TestConfig:
    def test_load_user_config(self, user_config_path):
        cfg = load_user_config(user_config_path)
        assert cfg["profile"] == "I like bold reds and dry whites."
        assert "Cabernet Sauvignon" in cfg["types"]
        assert cfg["notify_threshold"] == 90

    def test_in_price_range_within(self, config):
        assert in_price_range(50.0, config) is True

    def test_in_price_range_below(self, config):
        assert in_price_range(5.0, config) is False

    def test_in_price_range_above(self, config):
        assert in_price_range(200.0, config) is False


# ---------------------------------------------------------------------------
# 2. Environment loading
# ---------------------------------------------------------------------------


class TestEnv:
    def test_env_file_exists(self):
        env_path = Path(__file__).resolve().parent.parent / ".env"
        assert env_path.exists(), ".env file not found — copy from .env.example"

    def test_google_api_key_loaded(self):
        val = os.environ.get("GOOGLE_API_KEY", "")
        assert val and not val.startswith("your-"), "GOOGLE_API_KEY not set or still a placeholder"

    def test_smtp_user_loaded(self):
        val = os.environ.get("SMTP_USER", "")
        assert val and "@" in val, "SMTP_USER not set or invalid"

    def test_smtp_pass_loaded(self):
        val = os.environ.get("SMTP_PASS", "")
        assert val and not val.startswith("your-"), "SMTP_PASS not set or still a placeholder"

    def test_smtp_host_loaded(self):
        assert os.environ.get("SMTP_HOST"), "SMTP_HOST not set"

    def test_smtp_port_loaded(self):
        port = os.environ.get("SMTP_PORT", "")
        assert port.isdigit(), f"SMTP_PORT not set or invalid: {port!r}"


# ---------------------------------------------------------------------------
# 3. Prompt generation
# ---------------------------------------------------------------------------


class TestPrompt:
    def test_prompt_contains_wine_name(self, config):
        prompt = generate_wine_scoring_prompt(SAMPLE_WINE, config)
        assert SAMPLE_WINE in prompt

    def test_prompt_contains_profile(self, config):
        prompt = generate_wine_scoring_prompt(SAMPLE_WINE, config)
        assert "bold reds" in prompt

    def test_prompt_contains_types(self, config):
        prompt = generate_wine_scoring_prompt(SAMPLE_WINE, config)
        assert "Cabernet Sauvignon" in prompt
        assert "Chardonnay" in prompt

    def test_prompt_contains_always_notify(self, config):
        prompt = generate_wine_scoring_prompt(SAMPLE_WINE, config)
        assert "Opus One" in prompt

    def test_prompt_contains_never_notify(self, config):
        prompt = generate_wine_scoring_prompt(SAMPLE_WINE, config)
        assert "Yellow Tail" in prompt

    def test_prompt_contains_price_range(self, config):
        prompt = generate_wine_scoring_prompt(SAMPLE_WINE, config)
        assert "$20" in prompt
        assert "$100" in prompt

    def test_prompt_asks_for_score(self, config):
        prompt = generate_wine_scoring_prompt(SAMPLE_WINE, config)
        assert "0-100" in prompt


# ---------------------------------------------------------------------------
# 3. Scraper (hits lastbottlewines.com)
# ---------------------------------------------------------------------------


class TestScraper:
    @pytest.mark.network
    def test_scrape_returns_wine_and_price(self):
        result = scrape_last_bottle()
        assert result is not None, "Scraper returned None — site may be down"
        wine_name, price = result
        assert isinstance(wine_name, str) and len(wine_name) > 0
        assert isinstance(price, float) and price > 0


# ---------------------------------------------------------------------------
# 4. Gemini scoring (hits the Gemini API — requires GOOGLE_API_KEY)
# ---------------------------------------------------------------------------


class TestGeminiScoring:
    @pytest.mark.skipif(
        not os.environ.get("GOOGLE_API_KEY"),
        reason="GOOGLE_API_KEY not set",
    )
    @pytest.mark.network
    def test_score_wine_returns_valid_int(self, config):
        prompt = generate_wine_scoring_prompt(SAMPLE_WINE, config)
        score = score_wine(prompt)
        assert score is not None, "Gemini returned no parseable score"
        assert 0 <= score <= 100

    @pytest.mark.skipif(
        not os.environ.get("GOOGLE_API_KEY"),
        reason="GOOGLE_API_KEY not set",
    )
    @pytest.mark.network
    def test_always_notify_wine_scores_high(self, config):
        """Opus One is in always_notify — prompt says score it 100."""
        prompt = generate_wine_scoring_prompt("Opus One", config)
        score = score_wine(prompt)
        assert score is not None
        assert score == 100, (
            f"Expected 100 for always-notify wine, got {score}"
        )

    @pytest.mark.skipif(
        not os.environ.get("GOOGLE_API_KEY"),
        reason="GOOGLE_API_KEY not set",
    )
    @pytest.mark.network
    def test_never_notify_wine_scores_low(self, config):
        """Yellow Tail is in never_notify — should score low."""
        prompt = generate_wine_scoring_prompt(
            "Yellow Tail Reserve Shiraz", config
        )
        score = score_wine(prompt)
        assert score is not None
        assert score < 50, f"Expected <50 for never-notify wine, got {score}"


# ---------------------------------------------------------------------------
# 5. Email notification (hits real SMTP — requires SMTP_* env vars)
# ---------------------------------------------------------------------------


class TestEmail:
    @pytest.mark.skipif(
        not os.environ.get("SMTP_USER") or not os.environ.get("SMTP_PASS"),
        reason="SMTP credentials not set",
    )
    @pytest.mark.network
    def test_send_email(self):
        """Sends a real test email to the SMTP_USER address."""
        to = os.environ["SMTP_USER"]
        _send_email(
            to_address=to,
            subject="[TEST] lastbottlewines test suite",
            body="If you received this, email sending works.\n\nThis is an automated test.",
        )
        # No exception = success

    @pytest.mark.skipif(
        not os.environ.get("SMTP_USER") or not os.environ.get("SMTP_PASS"),
        reason="SMTP credentials not set",
    )
    @pytest.mark.network
    def test_notify_user(self):
        """Sends a full wine alert email via notify_user()."""
        config = SAMPLE_CONFIG.copy()
        config["contact"] = {"email": os.environ["SMTP_USER"]}
        notify_user(
            config=config,
            wine_name=SAMPLE_WINE,
            score=95,
            price=89.99,
        )
