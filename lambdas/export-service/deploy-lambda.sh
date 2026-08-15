#!/usr/bin/env bash
# Deploy/update the DiabetesCare monthly PDF report Lambda.
#
# The Lambda reuses the shared app modules (app/config.py, app/database.py,
# app/report.py — all light: only boto3 + stdlib, no FastAPI/jose/passlib) and
# adds `reportlab`. boto3 is already in the Lambda runtime.
#
# Prereqs:
#   - `aws` CLI installed & authenticated (`aws sts get-caller-identity`)
#   - Python venv at ../../.venv with `reportlab` installed
#   - A Lambda execution role ARN (see iam-policy.json)
#
# Usage:
#   ./deploy-lambda.sh <lambda-role-arn>
#   e.g. ./deploy-lambda.sh arn:aws:iam::123456789012:role/diabetescare-export
set -euo pipefail

ROLE_ARN="${1:-}"
if [ -z "$ROLE_ARN" ]; then
  echo "Usage: $0 <lambda-role-arn>"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
VENV="$REPO_ROOT/.venv"
WORK="$(mktemp -d)"

FUNCTION_NAME="diabetescare-export"
echo "Staging into $WORK ..."

# 1. Lambda handler + the shared app package (empty __init__.py so `app` imports).
mkdir -p "$WORK/app"
cp "$SCRIPT_DIR/lambda_function.py" "$WORK/lambda_function.py"
: > "$WORK/app/__init__.py"
cp "$REPO_ROOT/app/config.py" "$WORK/app/config.py"
cp "$REPO_ROOT/app/database.py" "$WORK/app/database.py"
cp "$REPO_ROOT/app/report.py" "$WORK/app/report.py"

# 2. Vendored dependencies (reportlab + pillow) at the zip top level so
#    `import reportlab` resolves. Pull ONLY these from the venv's
#    site-packages to keep the zip small.
SITE_PKG="$VENV/lib/python"*/site-packages
for pkg in reportlab PIL pillow; do
  for d in "$SITE_PKG/$pkg" "$SITE_PKG/${pkg,,}.dist-info" "$SITE_PKG/${pkg}.dist-info"; do
    if [ -e "$d" ]; then cp -r "$d" "$WORK/"; fi
  done
done

# 3. Zip the contents (top-level handler + app/ package + deps).
ZIP_PATH="$WORK/function.zip"
( cd "$WORK" && zip -r -q function.zip lambda_function.py app reportlab )
# add pillow under its import name
( cd "$WORK" && zip -r -q function.zip PIL )
cp "$ZIP_PATH" "$SCRIPT_DIR/function.zip"
echo "Built $SCRIPT_DIR/function.zip"

# 4. Create or update the function.
echo "Deploying function '$FUNCTION_NAME' ..."
if aws lambda get-function --function-name "$FUNCTION_NAME" >/dev/null 2>&1; then
  aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file "fileb://$SCRIPT_DIR/function.zip" \
    --publish
else
  aws lambda create-function \
    --function-name "$FUNCTION_NAME" \
    --runtime python3.12 \
    --handler lambda_function.lambda_handler \
    --role "$ROLE_ARN" \
    --zip-file "fileb://$SCRIPT_DIR/function.zip" \
    --timeout 60 \
    --memory-size 512 \
    --environment Variables="{DYNAMODB_TABLE=DiabetesCare,PDF_REPORTS_S3_BUCKET=diabetescare-reports-484504929783-us-east-1-an,AWS_REGION=us-east-1}"
fi

rm -rf "$WORK"
echo "Done."
