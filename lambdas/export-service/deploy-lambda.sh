#!/usr/bin/env bash
# Deploy/update the DiabetesCare monthly PDF report Lambda.
#
# IMPORTANT: reportlab eagerly imports Pillow at import time (PIL.Image ->
# _imaging), so the native Pillow .so MUST match the Lambda runtime platform
# (CPython 3.12, Linux x86_64). We therefore cross-install the deps for that
# platform with pip --platform/--python-version (NOT from the host venv, which
# would ship macOS/cp314 wheels -> ImportError on the Lambda).
#
# The Lambda reuses the shared app modules (app/config.py, app/database.py,
# app/report.py — all light: only boto3 + stdlib, no FastAPI/jose/passlib).
# boto3 is already in the Lambda runtime.
#
# Prereqs:
#   - `aws` CLI installed & authenticated (`aws sts get-caller-identity`)
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
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
STAGING="$(mktemp -d)"
ZIP_PATH="$SCRIPT_DIR/function.zip"

FUNCTION_NAME="diabetescare-export"
PY_VER="3.12"            # must match the Lambda runtime below
echo "Staging into $STAGING ..."

# 1. Lambda handler + the shared app package (empty __init__.py so `app` imports).
mkdir -p "$STAGING/app"
cp "$SCRIPT_DIR/lambda_function.py" "$STAGING/lambda_function.py"
: > "$STAGING/app/__init__.py"
cp "$REPO_ROOT/app/config.py" "$REPO_ROOT/app/database.py" "$REPO_ROOT/app/report.py" "$STAGING/app/"

# 2. Vendored dependencies cross-compiled for the Lambda platform at the zip top
#    level (so `import reportlab`/`import PIL` resolve). --only_binary avoids
#    building from source. reportlab is pure-Python (portable); Pillow +
#    charset_normalizer come as cp312 manylinux x86_64 wheels -> match the runtime.
#    NOTE: assumes an x86_64 Lambda. For arm64, change the platform to
#    manylinux2014_aarch64 (and Lambda architecture to arm64).
#    (Use the shell's `pip` if you prefer; `python3 -m pip` works with or without
#    the project venv activated.)
python3 -m pip install --target "$STAGING" \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version "$PY_VER" \
  --only-binary :all: \
  -q "reportlab>=4.0.0"

# 3. Strip staging noise that Lambda doesn't need and can ignore.
find "$STAGING" -type d -name "__pycache__" -prune -exec rm -rf {} +
rm -rf "$STAGING/bin"

# 4. Zip the contents (top-level handler + app/ package + deps).
rm -f "$ZIP_PATH"
( cd "$STAGING" && zip -r -q "$ZIP_PATH" . )
echo "Built $ZIP_PATH ($(du -h "$ZIP_PATH" | cut -f1))"

# Sanity-check: no macOS/darwin or cp3y4-native wheels slipped through.
if unzip -Z1 "$ZIP_PATH" | grep -qE "darwin"; then
  echo "ERROR: found macOS/darwin native files in the zip — will fail on the Linux Lambda." >&2
  exit 1
fi

# 5. Create or update the function.
echo "Deploying function '$FUNCTION_NAME' ..."
if aws lambda get-function --function-name "$FUNCTION_NAME" >/dev/null 2>&1; then
  aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file "fileb://$ZIP_PATH" \
    --publish
else
  aws lambda create-function \
    --function-name "$FUNCTION_NAME" \
    --runtime "python${PY_VER}" \
    --handler lambda_function.lambda_handler \
    --role "$ROLE_ARN" \
    --zip-file "fileb://$ZIP_PATH" \
    --timeout 60 \
    --memory-size 512 \
    --environment Variables="{DYNAMODB_TABLE=DiabetesCare,PDF_REPORTS_S3_BUCKET=diabetescare-reports-484504929783-us-east-1-an,AWS_REGION=us-east-1}"
fi

rm -rf "$STAGING"
echo "Done."
