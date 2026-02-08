"""AWS Lambda handler for lastbottlewines.

This module wraps the main() function with S3 sync so the SQLite
database, user configs, and error buffer persist between invocations.

Lambda environment variables required:
    S3_BUCKET   – S3 bucket for data persistence
    SMTP_HOST   – SMTP server hostname
    SMTP_PORT   – SMTP server port
    SMTP_USER   – SMTP username / from address
    SMTP_PASS   – SMTP password / app password
    GOOGLE_API_KEY – Gemini API key (used by google-genai)
"""

import os
import logging

from lastbottlewines.utils import data_dir
from lastbottlewines.s3 import sync_data_from_s3, sync_data_to_s3
from lastbottlewines.last_bottle import main

logger = logging.getLogger(__name__)


def handler(event, context):
    """AWS Lambda entry point.

    1. Downloads data from S3 to /tmp
    2. Runs the main scoring pipeline
    3. Uploads updated data back to S3
    """
    # Lambda writable directory
    tmp_data = data_dir()

    try:
        # Pull persisted state from S3
        sync_data_from_s3(tmp_data)

        # Run the pipeline
        main()

    finally:
        # Always push state back, even if main() errored
        sync_data_to_s3(tmp_data)

    return {"statusCode": 200, "body": "OK"}
