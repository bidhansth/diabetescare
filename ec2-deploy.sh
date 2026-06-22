#!/bin/bash
set -e

APP_DIR="/home/ec2-user/diabetescare"

echo "=== Checking deployment files ==="
if [ ! -d "$APP_DIR" ]; then
  echo "ERROR: $APP_DIR does not exist."
  echo "Clone your repo first:"
  echo "  git clone <your-repo-url> $APP_DIR"
  exit 1
fi
if [ ! -d "$APP_DIR/static" ]; then
  echo "ERROR: '$APP_DIR/static' directory not found."
  echo "Make sure the repository is cloned correctly."
  exit 1
fi

echo "=== Installing system packages ==="
sudo yum update -y
sudo yum install -y python3-pip

echo "=== Installing Python dependencies ==="
cd "$APP_DIR"
pip3 install -r requirements.txt

echo "=== Creating systemd service ==="
sudo tee /etc/systemd/system/diabetescare.service > /dev/null <<'EOF'
[Unit]
Description=DiabetesCare FastAPI App
After=network.target

[Service]
Type=simple
User=ec2-user
WorkingDirectory=/home/ec2-user/diabetescare
Environment="AWS_REGION=us-east-1"
Environment="DYNAMODB_TABLE=DiabetesCare"
Environment="STORAGE_BACKEND=s3"
Environment="JWT_SECRET=66ljXZ43xGvaQx+yqZd43XDf2NO40HX3VL7e2GRk4ac="
Environment="S3_BUCKET=diabetescare-resource0622-484504929783-us-east-1-an"
Environment="CAROUSEL_S3_BUCKET=diabetescare-carousel0622-484504929783-us-east-1-an"
ExecStart=/home/ec2-user/.local/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
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
echo "App running at http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8000"
