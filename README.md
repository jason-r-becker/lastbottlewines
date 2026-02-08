# lastbottlewines

Scrapes [lastbottlewines.com](https://www.lastbottlewines.com), scores the current wine against your personal preferences using Google Gemini, and emails you when something scores above your threshold.

## How it works

1. **Scrape** — pulls the current wine name and price from Last Bottle Wines
2. **Filter** — checks price range and duplicate detection (SQLite)
3. **Score** — sends a detailed prompt to Gemini (`gemini-2.5-flash-lite`) with your taste profile, preferred types, and price ranges → returns a 0–100 score
4. **Notify** — if the score meets your threshold, sends an email alert with a link to buy

Supports multiple users — each gets their own config file and independent scoring.

## Quickstart

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/jason-r-becker/lastbottlewines.git
cd lastbottlewines
uv sync
```

### Configure

1. Copy the template config:
   ```bash
   cp data/user_configs/template.yaml data/user_configs/yourname.yaml
   ```

2. Edit `data/user_configs/yourname.yaml` with your wine preferences, price ranges, and email.

3. Set environment variables:
   ```bash
   export GOOGLE_API_KEY="your-gemini-api-key"

   # For email notifications
   export SMTP_HOST="smtp.gmail.com"
   export SMTP_PORT="465"
   export SMTP_USER="you@gmail.com"
   export SMTP_PASS="your-app-password"
   ```

### Run

```bash
uv run lastbottlewines
```

## User config

Each YAML file in `data/user_configs/` represents one user. See [`template.yaml`](data/user_configs/template.yaml) for all options:

| Field | Description |
|---|---|
| `profile` | Free-text description of your wine taste |
| `types` | List of wine types you like |
| `price_range` | `[min, max]` in dollars |
| `type_specific_price_ranges` | Optional per-type price overrides |
| `always_notify_for` | Wines that always trigger alerts |
| `never_notify_for` | Wines that never trigger alerts |
| `notify_threshold` | Minimum score (0–100) to send an email |
| `contact.email` | Your email address |

## Deploy to AWS Lambda

For hands-free hourly checks, deploy as a Lambda function with EventBridge scheduling and S3 for data persistence.

```bash
# One-time setup — see comments at the top of the script
chmod +x deploy_lambda.sh
./deploy_lambda.sh
```

See [`deploy_lambda.sh`](deploy_lambda.sh) for step-by-step instructions and [`iam_policy.json`](iam_policy.json) for the required IAM permissions.

## Project structure

```
src/lastbottlewines/
├── last_bottle.py      # Main orchestration
├── scraper.py          # Web scraping
├── scorer.py           # LLM scoring via Gemini
├── config.py           # YAML config loading
├── wine_database.py    # SQLite database (wines + user_scores)
├── notifier.py         # Email alerts
├── log.py              # Logging + daily error digest
├── utils.py            # Shared utilities
├── lambda_handler.py   # AWS Lambda entry point
└── s3.py               # S3 persistence for Lambda
```

## License

MIT
