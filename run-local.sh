#!/bin/bash
set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/.venv"
SCRIPT_DIR="$PROJECT_DIR/scripts"
MOTO_PORT=4567
APP_PORT=8000

echo "=== DiabetesCare Local Development Server ==="
echo ""

source "$VENV_DIR/bin/activate"

MOTOPID=""
cleanup() {
  echo ""
  echo "Shutting down..."
  if [ -n "$MOTOPID" ] && kill -0 "$MOTOPID" 2>/dev/null; then
    kill "$MOTOPID" 2>/dev/null
    echo "  Moto stopped"
  fi
}
trap cleanup EXIT

# ── Step 1: Start local DynamoDB ──
echo "[1/5] Starting local DynamoDB on port $MOTO_PORT..."

if docker info > /dev/null 2>&1; then
  echo "  Using Docker (DynamoDB Local)"
  if ! docker ps --format '{{.Names}}' | grep -q "^dynamodb-local$"; then
    if docker ps -a --format '{{.Names}}' | grep -q "^dynamodb-local$"; then
      docker start dynamodb-local
    else
      docker run -d --name dynamodb-local \
        -p "$MOTO_PORT:8000" \
        amazon/dynamodb-local:latest \
        -jar DynamoDBLocal.jar -sharedDb
    fi
    for i in $(seq 1 15); do
      if curl -s "http://localhost:$MOTO_PORT" > /dev/null 2>&1; then break; fi
      sleep 1
    done
  fi
else
  echo "  Docker not available — using moto (in-memory mock)"
  kill $(lsof -ti:$MOTO_PORT) 2>/dev/null || true
  moto_server -p "$MOTO_PORT" &
  MOTOPID=$!
  sleep 2
fi

export DYNAMODB_ENDPOINT_URL="http://localhost:$MOTO_PORT"
echo "  DynamoDB endpoint: $DYNAMODB_ENDPOINT_URL"

# ── Step 2: Create DiabetesCare table ──
echo "[2/5] Setting up DynamoDB table..."
export AWS_REGION="us-east-1"
export AWS_ACCESS_KEY_ID="fake"
export AWS_SECRET_ACCESS_KEY="fake"
export DYNAMODB_TABLE="DiabetesCare"
export JWT_SECRET="local-dev-secret-do-not-use-in-prod"
python "$SCRIPT_DIR/setup-local-db.py"

# ── Step 3: Seed demo data ──
echo "[3/5] Seeding demo data..."
python "$SCRIPT_DIR/seed-data.py"

# ── Step 4: Start uvicorn ──
echo "[4/5] Starting uvicorn on port $APP_PORT..."
echo ""

cd "$PROJECT_DIR"
uvicorn app.main:app --host 0.0.0.0 --port "$APP_PORT" --reload
