#!/usr/bin/env bash
# Deploy the DiabetesCare PDF-compression Lambda end-to-end (idempotent, one command):
#   ./deploy-lambda.sh
#
# Creates:
#   - IAM role `diabetescare-compress-pdf-role` (lambda.amazonaws.com)
#     + inline policy from iam-policy.json + managed SQS/Lambda execution roles
#   - SQS queue `diabetescare-resource-compress-<acct>-<region>`
#     + resource policy allowing S3 (resource bucket) + lambda.amazonaws.com to send
#   - Lambda `diabetescare-compress-pdf` (python3.12) subscribed to the queue
#   - S3 `ObjectCreated:*` event notification on the resource bucket
#     (suffix `pdf`) -> that queue
#
# IMPORTANT: pikepdf ships a compiled native extension (_core/.so). The zip must
# contain the cp312 manylinux x86_64 wheel, NOT the host (macOS/3.14) wheel --
# otherwise the Lambda fails to import PIL-equivalent and returns ImportModuleError.
# We therefore cross-install with pip --platform/--python-version/--only-binary.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"               # repo root (.../diabetescare)

REGION="${AWS_REGION:-$(aws configure get region 2>/dev/null || echo us-east-1)}"
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
RESOURCE_BUCKET="diabetescare-resource-${ACCOUNT}-${REGION}-an"
QUEUE_NAME="diabetescare-resource-compress-${ACCOUNT}-${REGION}"
ROLE_NAME="diabetescare-compress-pdf-role"
POLICY_NAME="diabetescare-compress-pdf-policy"
FUNCTION_NAME="diabetescare-compress-pdf"
PY_VER="3.12"

# ----------------------------------------------------------------------------
# 1) Build the deployable zip (cp312 linux wheels only).
# ----------------------------------------------------------------------------
echo "[1/6] Building package (cp312 linux wheels)..."
STAGE="$(mktemp -d)"
ZIP_PATH="$SCRIPT_DIR/function.zip"

python3 -m pip install --target "$STAGE" \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version "$PY_VER" \
  --only-binary :all: \
  -q -r "$SCRIPT_DIR/requirements.txt"

cp "$SCRIPT_DIR/lambda_function.py" "$STAGE/lambda_function.py"
find "$STAGE" -type d -name "__pycache__" -prune -exec rm -rf {} +
rm -rf "$STAGE/bin"
rm -f "$ZIP_PATH"
( cd "$STAGE" && zip -r -q "$ZIP_PATH" . )

if unzip -Z1 "$ZIP_PATH" | grep -qiE "darwin"; then
  echo "ERROR: macOS/darwin native files in zip -- will fail on the Linux Lambda." >&2
  rm -rf "$STAGE"
  exit 1
fi
echo "    built $ZIP_PATH ($(du -h "$ZIP_PATH" | cut -f1)) -- pikepdf native ext:"
unzip -Z1 "$ZIP_PATH" | grep -iE "_core.*\.so|qpdf.*\.so" | head -3 || true
rm -rf "$STAGE"

# ----------------------------------------------------------------------------
# 2) IAM role + policies (reused if present).
# ----------------------------------------------------------------------------
echo "[2/6] Ensuring IAM role '$ROLE_NAME'..."
TRUST="$(mktemp)"
cat > "$TRUST" <<'EOF'
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Service": "lambda.amazonaws.com"},
    "Action": "sts:AssumeRole"
  }]
}
EOF
aws iam get-role --role-name "$ROLE_NAME" >/dev/null 2>&1 || \
  aws iam create-role --role-name "$ROLE_NAME" \
    --assume-role-policy-document "file://$TRUST" >/dev/null
rm -f "$TRUST"
ROLE_ARN="$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)"
aws iam put-role-policy --role-name "$ROLE_NAME" --policy-name "$POLICY_NAME" \
  --policy-document "file://$SCRIPT_DIR/iam-policy.json"
aws iam attach-role-policy --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaSQSQueueExecutionRole
aws iam attach-role-policy --role-name "$ROLE_NAME" \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
echo "    role=$ROLE_ARN"

# ----------------------------------------------------------------------------
# 3) SQS queue + resource policy (S3 + Lambda can send).
# ----------------------------------------------------------------------------
echo "[3/6] Ensuring SQS queue '$QUEUE_NAME'..."
QUEUE_URL="$(aws sqs create-queue --queue-name "$QUEUE_NAME" \
  --attributes VisibilityTimeout=120 --query 'QueueUrl' --output text)"
QUEUE_ARN="$(aws sqs get-queue-attributes --queue-url "$QUEUE_URL" \
  --attribute-names QueueArn --query 'Attributes.QueueArn' --output text)"

POLICY="$(mktemp)"
cat > "$POLICY" <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "s3.amazonaws.com"},
      "Action": "sqs:SendMessage",
      "Resource": "$QUEUE_ARN",
      "Condition": {"ArnLike": {"aws:SourceArn": "arn:aws:s3:::$RESOURCE_BUCKET"}}
    },
    {
      "Effect": "Allow",
      "Principal": {"Service": "lambda.amazonaws.com"},
      "Action": "sqs:SendMessage",
      "Resource": "$QUEUE_ARN"
    }
  ]
}
EOF
ATTR="$(mktemp)"
jq -n --slurpfile p "$POLICY" '{Policy: ($p[0] | tojson)}' > "$ATTR"
aws sqs set-queue-attributes --queue-url "$QUEUE_URL" --attributes "file://$ATTR"
rm -f "$POLICY" "$ATTR"
echo "    queue=$QUEUE_URL  ($QUEUE_ARN)"

# ----------------------------------------------------------------------------
# 4) Lambda function (create or update config + code).
# ----------------------------------------------------------------------------
echo "[4/6] Deploying Lambda '$FUNCTION_NAME'..."
if aws lambda get-function --function-name "$FUNCTION_NAME" >/dev/null 2>&1; then
  aws lambda update-function-configuration \
    --function-name "$FUNCTION_NAME" \
    --role "$ROLE_ARN" \
    --timeout 90 --memory-size 512 \
    --environment "Variables={S3_BUCKET=$RESOURCE_BUCKET}" >/dev/null
fi
echo "    function=$FUNCTION_NAME"

# ----------------------------------------------------------------------------
# 5) SQS -> Lambda event source mapping (create or update).
# ----------------------------------------------------------------------------
echo "[5/6] Ensuring SQS event source mapping..."
# The function must be Active before an event source mapping can reference it.
aws lambda wait function-active --function-name "$FUNCTION_NAME" >/dev/null 2>&1 || true
MAPPING_UUID="$(aws lambda list-event-source-mappings \
  --function-name "$FUNCTION_NAME" --event-source-arn "$QUEUE_ARN" \
  --query 'EventSourceMappings[0].UUID' --output text 2>/dev/null || true)"
if [ "$MAPPING_UUID" = "None" ] || [ -z "$MAPPING_UUID" ]; then
  for attempt in 1 2 3 4 5; do
    if aws lambda create-event-source-mapping \
        --function-name "$FUNCTION_NAME" \
        --event-source-arn "$QUEUE_ARN" \
        --batch-size 5 --enabled >/dev/null 2>&1; then
      break
    fi
    sleep 5
  done
else
  aws lambda update-event-source-mapping \
    --uuid "$MAPPING_UUID" \
    --function-name "$FUNCTION_NAME" \
    --batch-size 5 --enabled >/dev/null || true
fi
echo "    event source mapping attached"

# ----------------------------------------------------------------------------
# 6) S3 ObjectCreated (suffix pdf) -> SQS queue (merge, do not clobber existing).
# ----------------------------------------------------------------------------
echo "[6/6] Ensuring bucket notification on '$RESOURCE_BUCKET'..."
python3 - "$RESOURCE_BUCKET" "$QUEUE_ARN" <<'PY'
import json, os, sys, subprocess, tempfile
bucket, arn = sys.argv[1], sys.argv[2]
r = subprocess.run(["aws","s3api","get-bucket-notification-configuration",
                    "--bucket",bucket], capture_output=True, text=True)
cfg = json.loads(r.stdout) if r.returncode == 0 and r.stdout.strip() else {}
cfg.setdefault("QueueConfigurations", [])
cfg["QueueConfigurations"] = [
    q for q in cfg["QueueConfigurations"] if q.get("QueueArn") != arn
]
cfg["QueueConfigurations"].append({
    "Id": "diabetescare-compress-pdf",
    "QueueArn": arn,
    "Events": ["s3:ObjectCreated:*"],
    "Filter": {"Key": {"FilterRules": [{"Name": "suffix", "Value": "pdf"}]}},
})
tmp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
json.dump(cfg, tmp); tmp.close()
subprocess.run(["aws","s3api","put-bucket-notification-configuration",
                "--bucket",bucket,"--notification-configuration",f"file://{tmp.name}"],
               check=True)
os.unlink(tmp.name)
print("    bucket notification configured")
PY

echo "Done."
echo "Function: $FUNCTION_NAME"
echo "Queue:    $QUEUE_URL"
echo "Bucket:   $RESOURCE_BUCKET (suffix filter: pdf)"
