#!/bin/bash
set -e

APP_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_USER="ssm-user"

echo "=== Checking deployment files ==="
if [ ! -d "$APP_DIR" ]; then
  echo "ERROR: $APP_DIR does not exist."
  exit 1
fi
if [ ! -d "$APP_DIR/static" ]; then
  echo "ERROR: '$APP_DIR/static' directory not found."
  echo "Make sure you are running this script from the diabetescare repository root."
  exit 1
fi

echo "=== Installing system packages ==="
if command -v dnf &> /dev/null; then
  sudo dnf update -y
  sudo dnf install -y python3-pip
elif command -v yum &> /dev/null; then
  sudo yum update -y
  sudo yum install -y python3-pip
else
  echo "ERROR: No package manager found (tried dnf, yum)."
  exit 1
fi

echo "=== Installing Python dependencies ==="
cd "$APP_DIR"
python3 -m pip install -r requirements.txt

echo "=== Creating systemd service ==="
sudo tee /etc/systemd/system/diabetescare.service > /dev/null <<EOF
[Unit]
Description=DiabetesCare FastAPI App
After=network.target

[Service]
Type=simple
User=${APP_USER}
WorkingDirectory=${APP_DIR}
Environment="AWS_REGION=us-east-1"
Environment="DYNAMODB_TABLE=DiabetesCare"
Environment="STORAGE_BACKEND=s3"
Environment="JWT_SECRET=66ljXZ43xGvaQx+yqZd43XDf2NO40HX3VL7e2GRk4ac="
Environment="S3_BUCKET=diabetescare-resource0622-484504929783-us-east-1-an"
Environment="CAROUSEL_S3_BUCKET=diabetescare-carousel0622-484504929783-us-east-1-an"
ExecStart=python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "=== Starting service ==="
sudo systemctl daemon-reload
sudo systemctl enable diabetescare
sudo systemctl start diabetescare

echo "=== Status ==="
sudo systemctl status diabetescare --no-pager

echo "=== Done ==="
INSTANCE_ID="$(curl -s http://169.254.169.254/latest/meta-data/instance-id)"
echo "Instance: $INSTANCE_ID"
echo ""
echo "To access the app:"
echo "  1. Check the ALB DNS name in AWS Console (EC2 > Load Balancers)"
echo "  2. Or use SSM Port Forwarding:"
echo "     aws ssm start-session --target $INSTANCE_ID \\"
echo "       --document-name AWS-StartPortForwardingSession \\"
echo "       --parameters '{\"portNumber\":[\"8000\"],\"localPortNumber\":[\"8000\"]}'"
echo "     Then open http://localhost:8000"
