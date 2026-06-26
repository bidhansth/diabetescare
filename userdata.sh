#!/bin/bash
set -e

REPO_URL="https://github.com/bidhansth/diabetescare.git"
APP_DIR="/home/ec2-user/diabetescare"
APP_USER="ec2-user"
AWS_REGION="us-east-1"
DYNAMODB_TABLE="DiabetesCare"
JWT_SECRET="66ljXZ43xGvaQx+yqZd43XDf2NO40HX3VL7e2GRk4ac="
STORAGE_BACKEND="s3"
S3_BUCKET="diabetescare-resource0622-484504929783-us-east-1-an"
CAROUSEL_S3_BUCKET="diabetescare-carousel0622-484504929783-us-east-1-an"

exec > /var/log/diabetescare-userdata.log 2>&1

echo "=== Updating system packages ==="
yum update -y

echo "=== Installing system dependencies ==="
yum install -y git python3-pip awscli

echo "=== Cloning repository ==="
git clone "$REPO_URL" "$APP_DIR"

echo "=== Installing Python dependencies ==="
cd "$APP_DIR"
pip3 install -r requirements.txt

echo "=== Creating systemd service ==="
sudo tee /etc/systemd/system/diabetescare.service > /dev/null <<EOF
[Unit]
Description=DiabetesCare FastAPI App
After=network.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$APP_DIR
Environment="AWS_REGION=$AWS_REGION"
Environment="DYNAMODB_TABLE=$DYNAMODB_TABLE"
Environment="STORAGE_BACKEND=$STORAGE_BACKEND"
Environment="JWT_SECRET=$JWT_SECRET"
Environment="S3_BUCKET=$S3_BUCKET"
Environment="CAROUSEL_S3_BUCKET=$CAROUSEL_S3_BUCKET"
ExecStart=/usr/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "=== Starting service ==="
chown -R "$APP_USER:$APP_USER" "$APP_DIR"
systemctl daemon-reload
systemctl enable diabetescare
systemctl start diabetescare

echo "=== Status ==="
systemctl status diabetescare --no-pager

PUBLIC_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)
echo "=== Done ==="
echo "App running at http://$PUBLIC_IP:8000"
