"""S3 persistence helpers for Lambda deployment.

On Lambda there is no persistent filesystem, so we store the SQLite database
and user config files in S3. This module provides download/upload helpers
that the rest of the application uses transparently.

Required environment variables:
    S3_BUCKET  – the S3 bucket name (e.g. "lastbottlewines-data")

Bucket layout:
    s3://<bucket>/wines.db
    s3://<bucket>/user_configs/jason.yaml
    s3://<bucket>/user_configs/...
    s3://<bucket>/logs/error_buffer.json
"""

import os
import logging
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

BUCKET = os.environ.get("S3_BUCKET", "")


def _client():
    return boto3.client("s3")


def download_file(s3_key: str, local_path: Path) -> bool:
    """Download a file from S3 to a local path. Returns True on success."""
    if not BUCKET:
        logger.warning("S3_BUCKET not set, skipping download of %s", s3_key)
        return False
    try:
        local_path.parent.mkdir(parents=True, exist_ok=True)
        _client().download_file(BUCKET, s3_key, str(local_path))
        logger.info("Downloaded s3://%s/%s → %s", BUCKET, s3_key, local_path)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            logger.info("s3://%s/%s not found (first run?)", BUCKET, s3_key)
            return False
        logger.error("Failed to download s3://%s/%s: %s", BUCKET, s3_key, e)
        return False


def upload_file(local_path: Path, s3_key: str) -> bool:
    """Upload a local file to S3. Returns True on success."""
    if not BUCKET:
        logger.warning("S3_BUCKET not set, skipping upload of %s", s3_key)
        return False
    if not local_path.exists():
        logger.warning("Local file %s does not exist, skipping upload", local_path)
        return False
    try:
        _client().upload_file(str(local_path), BUCKET, s3_key)
        logger.info("Uploaded %s → s3://%s/%s", local_path, BUCKET, s3_key)
        return True
    except ClientError as e:
        logger.error("Failed to upload %s: %s", s3_key, e)
        return False


def download_directory(s3_prefix: str, local_dir: Path) -> int:
    """Download all files under an S3 prefix to a local directory.

    Returns the number of files downloaded.
    """
    if not BUCKET:
        return 0
    count = 0
    paginator = _client().get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=BUCKET, Prefix=s3_prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            # Derive local path relative to the prefix
            rel = key[len(s3_prefix):].lstrip("/")
            if not rel:
                continue
            local_path = local_dir / rel
            download_file(key, local_path)
            count += 1
    return count


def sync_data_from_s3(data_dir: Path) -> None:
    """Pull wines.db, user_configs/, and logs/ from S3 into local data_dir."""
    download_file("wines.db", data_dir / "wines.db")
    download_directory("user_configs/", data_dir / "user_configs")
    download_file("logs/error_buffer.json", data_dir / "logs" / "error_buffer.json")


def sync_data_to_s3(data_dir: Path) -> None:
    """Push wines.db and logs/ back to S3 after a run."""
    upload_file(data_dir / "wines.db", "wines.db")
    error_buffer = data_dir / "logs" / "error_buffer.json"
    if error_buffer.exists():
        upload_file(error_buffer, "logs/error_buffer.json")
