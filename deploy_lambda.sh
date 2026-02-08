#!/usr/bin/env bash
# deploy_lambda.sh — Package and deploy lastbottlewines to AWS Lambda
#
# ============================================================
#  ONE-TIME SETUP (do these manually first):
#
#  1. Install & configure the AWS CLI:
#       aws configure
#
#  2. Create the S3 bucket:
#       aws s3 mb s3://lastbottlewines-data --region us-east-1
#
#  3. Create the IAM role (uses the policy file in this repo):
#       aws iam create-role \
#         --role-name lastbottlewines-lambda-role \
#         --assume-role-policy-document '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
#
#       aws iam put-role-policy \
#         --role-name lastbottlewines-lambda-role \
#         --policy-name lastbottlewines-policy \
#         --policy-document file://iam_policy.json
#
#  4. Upload your user configs to S3:
#       aws s3 cp data/user_configs/ s3://lastbottlewines-data/user_configs/ --recursive
#
#  5. Set the environment variables below, then run this script.
#
# ============================================================
#
# Usage:
#   chmod +x deploy_lambda.sh
#   ./deploy_lambda.sh

set -euo pipefail

# ---------- Configuration ----------
FUNCTION_NAME="lastbottlewines"
S3_BUCKET="lastbottlewines-data"
REGION="us-east-1"
SMTP_HOST="smtp.gmail.com"
SMTP_PORT="465"

# Load secrets from .env file (gitignored)
ENV_FILE="$(cd "$(dirname "$0")" && pwd)/.env"
if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: .env file not found. Create one from .env.example:"
    echo "  cp .env.example .env"
    echo "  nano .env"
    exit 1
fi
source "$ENV_FILE"

if [[ -z "${ROLE_ARN:-}" || -z "${SMTP_USER:-}" || -z "${SMTP_PASS:-}" || -z "${GOOGLE_API_KEY:-}" ]]; then
    echo "ERROR: .env must define ROLE_ARN, SMTP_USER, SMTP_PASS, and GOOGLE_API_KEY."
    exit 1
fi

HANDLER="lastbottlewines.lambda_handler.handler"
BUILD_DIR="/tmp/lastbottlewines-lambda"
ZIP_FILE="/tmp/lastbottlewines-lambda.zip"

# --- Build ---
echo "==> Building deployment package"
rm -rf "$BUILD_DIR" "$ZIP_FILE"
mkdir -p "$BUILD_DIR"
pip install --target "$BUILD_DIR" --platform manylinux2014_x86_64 --only-binary=:all: ".[lambda]"
cd "$BUILD_DIR" && zip -rq "$ZIP_FILE" . -x '*.pyc' '__pycache__/*'

# --- Deploy ---
if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" &>/dev/null; then
    echo "==> Updating Lambda function"
    aws lambda update-function-code \
        --function-name "$FUNCTION_NAME" \
        --zip-file "fileb://$ZIP_FILE" \
        --region "$REGION" --no-cli-pager
else
    echo "==> Creating Lambda function"
    aws lambda create-function \
        --function-name "$FUNCTION_NAME" \
        --runtime python3.12 \
        --role "$ROLE_ARN" \
        --handler "$HANDLER" \
        --zip-file "fileb://$ZIP_FILE" \
        --timeout 300 \
        --memory-size 256 \
        --region "$REGION" \
        --no-cli-pager \
        --environment "Variables={S3_BUCKET=$S3_BUCKET,SMTP_HOST=$SMTP_HOST,SMTP_PORT=$SMTP_PORT,SMTP_USER=$SMTP_USER,SMTP_PASS=$SMTP_PASS,GOOGLE_API_KEY=$GOOGLE_API_KEY}"
fi

# --- Wait for function to be ready ---
echo "==> Waiting for function to become Active..."
aws lambda wait function-active-v2 --function-name "$FUNCTION_NAME" --region "$REGION"

# --- Env vars (always update) ---
echo "==> Updating environment variables"
aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --no-cli-pager \
    --environment "Variables={S3_BUCKET=$S3_BUCKET,SMTP_HOST=$SMTP_HOST,SMTP_PORT=$SMTP_PORT,SMTP_USER=$SMTP_USER,SMTP_PASS=$SMTP_PASS,GOOGLE_API_KEY=$GOOGLE_API_KEY}" > /dev/null

# --- Schedule (hourly) ---
echo "==> Setting up hourly schedule"
RULE_NAME="lastbottlewines-hourly"
aws events put-rule --name "$RULE_NAME" --schedule-expression "rate(1 hour)" --region "$REGION" --state ENABLED --no-cli-pager > /dev/null

FUNCTION_ARN=$(aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" --query 'Configuration.FunctionArn' --output text)

aws lambda add-permission \
    --function-name "$FUNCTION_NAME" \
    --statement-id "${RULE_NAME}-invoke" \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn "$(aws events describe-rule --name "$RULE_NAME" --region "$REGION" --query 'Arn' --output text)" \
    --region "$REGION" &>/dev/null || true

aws events put-targets --rule "$RULE_NAME" --targets "Id=1,Arn=$FUNCTION_ARN" --region "$REGION" --no-cli-pager > /dev/null

echo ""
echo "Done! '$FUNCTION_NAME' deployed and scheduled to run every hour."
echo ""
echo "Test it:  aws lambda invoke --function-name $FUNCTION_NAME /dev/stdout"
