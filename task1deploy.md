# DiabetesCare — Task #1 AWS Deployment Guide

Deploy the DiabetesCare monolithic app on EC2 with DynamoDB.

---

## Prerequisites

- AWS account with admin access
- A key pair created in your chosen region (EC2 → Key Pairs)
- The `diabetescare/` project files on your local machine
- AWS CLI installed locally (optional, for CLI-based steps)

---

## Step 1: Create the DynamoDB Table

1. Go to **AWS Console → DynamoDB → Create table**
2. Configure:
   - **Table name:** `DiabetesCare`
   - **Partition key:** `PK` (String)
   - **Sort key:** `SK` (String)
   - **Capacity mode:** On-demand (pay-per-request)
   - **Encryption:** Default (AWS owned key)
3. Click **Create table**

> No secondary indexes are needed — all queries use PK/SK patterns.

---

## Step 2: Create an S3 Bucket for Resources

1. Go to **AWS Console → S3 → Create bucket**
2. Configure:
   - **Bucket name:** `diabetescare-resources`
   - **AWS Region:** Same as your EC2 instance (e.g., `us-east-1`)
   - **Block all public access:** Enabled
   - **Bucket Versioning:** Disable
   - **Default encryption:** SSE-S3 (Amazon S3 managed keys)
3. Click **Create bucket**
4. The EC2 IAM role (created in Step 3) will grant the app access via `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`

---

## Step 3: Create an IAM Role for EC2

1. Go to **AWS Console → IAM → Roles → Create role**
2. **Trusted entity type:** AWS service
3. **Use case:** EC2
4. **Permissions policy:** Attach both:
   - `AmazonDynamoDBFullAccess`
     - (Or a custom inline policy granting `GetItem`, `PutItem`, `Query`, `Scan`, `DeleteItem` on `arn:aws:dynamodb:*:*:table/DiabetesCare`)
   - `AmazonS3FullAccess`
     - (Or a custom inline policy granting `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`, `s3:ListBucket` on `arn:aws:s3:::diabetescare-resources` and `arn:aws:s3:::diabetescare-resources/*`)
5. **Role name:** `diabetescare-ec2-role`
6. Click **Create role**

---

## Step 4: Launch an EC2 Instance

1. Go to **AWS Console → EC2 → Instances → Launch instance**
2. Configure:
   - **Name:** `DiabetesCare-App`
   - **AMI:** Amazon Linux 2023 (HVM), 64-bit (x86)
   - **Instance type:** `t2.micro` (or `t3.micro` — free tier eligible)
   - **Key pair:** Select your existing key pair (or create one)
   - **VPC:** default VPC (or your custom VPC)
3. **Network settings → Edit:**
   - **Auto-assign public IP:** Enable
   - **Firewall (security groups):** Create new security group with these rules:

| Type | Protocol | Port | Source | Description |
|------|----------|------|--------|-------------|
| SSH | TCP | 22 | Your IP (`x.x.x.x/32`) | SSH access |
| HTTP | TCP | 8000 | `0.0.0.0/0` | App access |
| Custom TCP | TCP | 8000 | `0.0.0.0/0` | App access (fallback) |

4. **Advanced details → IAM instance profile:** Select `diabetescare-ec2-role`
5. **Storage:** 8 GB gp2 or gp3 (enough for the app)
6. Click **Launch instance**
7. Wait for **Status check** to show `2/2 checks passed`
8. Note the **Public IPv4 address** — you'll need it throughout this guide.

---

## Step 5: Upload Project Files to EC2

### Option A — SCP (recommended)

From your local machine:

```bash
# Replace with your key and EC2 public IP
scp -i /path/to/your-key.pem -r diabetescare/ ec2-user@<EC2-PUBLIC-IP>:/home/ec2-user/diabetescare
```

### Option B — Git clone

If your project is on a private GitHub repo:

```bash
# SSH into EC2, then:
sudo yum install -y git
git clone <your-repo-url> /home/ec2-user/diabetescare
```

### Verify:

```bash
ssh -i /path/to/your-key.pem ec2-user@<EC2-PUBLIC-IP>
ls /home/ec2-user/diabetescare/
# Should see: app/  static/  scripts/  requirements.txt  ec2-deploy.sh  run-local.sh
```

---

## Step 6: Run the Deployment Script

SSH into the instance, then:

```bash
cd /home/ec2-user/diabetescare
chmod +x ec2-deploy.sh
./ec2-deploy.sh
```

### What the script does (step by step):

1. **Updates system packages** — `sudo yum update -y`
2. **Installs Python pip** — `sudo yum install -y python3-pip`
3. **Installs Python dependencies:**
   ```bash
   pip3 install -r requirements.txt
   ```
   Installs: `fastapi`, `uvicorn`, `boto3`, `python-jose`, `passlib`, `bcrypt`, `python-multipart`
4. **Creates systemd service** at `/etc/systemd/system/diabetescare.service`:

   ```
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
    Environment="S3_BUCKET=diabetescare-resources"
    ExecStart=/usr/local/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
   Restart=always
   RestartSec=5

   [Install]
   WantedBy=multi-user.target
   ```

5. **Enables and starts the service:**

   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable diabetescare
   sudo systemctl start diabetescare
   ```

---

## Step 7: Verify the Deployment

```bash
# Check service status
sudo systemctl status diabetescare --no-pager

sudo sed -i 's|/usr/local/bin/uvicorn|/home/ec2-user/.local/bin/uvicorn|' /etc/systemd/system/diabetescare.service

# View live logs
sudo journalctl -u diabetescare -f

# Test the app locally on EC2
curl -s http://localhost:8000/static/index.html | head -5
# Should return HTML of the login page

# Get your public IP
curl -s http://169.254.169.254/latest/meta-data/public-ipv4
```

---

## Step 8: Access the App

Open your browser and go to:

```
http://<EC2-PUBLIC-IP>:8000
```

You should see the DiabetesCare login page.

---

## Testing Checklist

- [ ] **Sign up** — Create a new account with name, email, password
- [ ] **Log in** — Sign in with your credentials
- [ ] **Dashboard loads** — Shows welcome message, stat cards
- [ ] **Log Glucose** — Click Glucose button, enter a value, save
- [ ] **Log Meal** — Click Meal button, enter carbs, save
- [ ] **Log Medication** — Click Medication button, enter dosage, save
- [ ] **Log Exercise** — Click Exercise button, enter minutes, save
- [ ] **History pages** — Each type tab shows its entries
- [ ] **Alerts** — Log glucose < 70 or > 180, check Alerts page
- [ ] **Medications** — Manage medications from the dashboard
- [ ] **Date filters** — Filter history by date range
- [ ] **Restart test** — `sudo systemctl restart diabetescare` — app comes back up
- [ ] **Resources page** — Navigate to Resources, see sample resource list
- [ ] **Download resource** — Click download on a resource, file downloads with correct extension
- [ ] **Admin login** — Log in as `admin@diabetescare.com` / `Admin@123`, get redirected to admin panel
- [ ] **Admin upload** — Upload a PDF from the admin panel
- [ ] **User download** — Log in as a regular user, download the uploaded file
- [ ] **Admin promote** — Promote a user to admin from the admin Users tab

---

## Troubleshooting

### App won't start

```bash
sudo journalctl -u diabetescare -n 50 --no-pager
```

Look for Python import errors or DynamoDB connection errors.

### DynamoDB access denied

Verify the EC2 instance has the IAM role attached:

```bash
aws sts assume-role --role-arn ...  # debug IAM
# Check if the role is attached:
curl http://169.254.169.254/latest/meta-data/iam/security-credentials/
```

Also check the role's trust policy allows EC2 and has the correct permissions.

### Port 8000 not reachable

- Check EC2 security group — ensure inbound rule for port 8000 from `0.0.0.0/0`
- Check if uvicorn is running: `sudo systemctl status diabetescare`
- Check the EC2 firewall: `sudo systemctl status firewalld` (usually disabled on Amazon Linux)

### Changes not reflecting

If you updated the code:

```bash
sudo systemctl restart diabetescare
sudo journalctl -u diabetescare -f  # watch logs on restart
```

---

## Environment Variables Reference

| Variable | Description | Default | Required |
|---|---|---|---|
| `AWS_REGION` | AWS region for DynamoDB | `us-east-1` | Yes |
| `DYNAMODB_TABLE` | DynamoDB table name | `DiabetesCare` | Yes |
| `JWT_SECRET` | Secret key for JWT signing | `dev-secret-...` | Yes (change in production) |
| `DYNAMODB_ENDPOINT_URL` | Custom DynamoDB endpoint (local dev only) | (empty) | No |
| `STORAGE_BACKEND` | Storage backend: `local` (dev) or `s3` (production) | `local` | Yes (set to `s3` in production) |
| `STORAGE_LOCAL_PATH` | Local filesystem path for storage (dev only) | `./local-storage` | No |
| `S3_BUCKET` | S3 bucket name for resource files (production) | `diabetescare-resources` | Yes (when `STORAGE_BACKEND=s3`) |

---

## Architecture

```
Browser ──▶ EC2 (t2.micro)
                │
        uvicorn ── FastAPI
            │         │
            │    Static Files
            │    (HTML/CSS/JS)
            │
        boto3 (AWS SDK)
            ├──────────────────┐
            ▼                  ▼
      DynamoDB            S3 Bucket
   "DiabetesCare"    "diabetescare-resources"
  ┌──────────────────┐  ┌──────────────┐
  │ USER#{id} PROFILE│  │ PDFs         │
  │ USER#{id} ENTRY# │  │ Images       │
  │ USER#{id} ALERT# │  │ Videos       │
  │ USER#{id} MED#   │  │ Word docs    │
  │ RESOURCES        │  └──────────────┘
  └──────────────────┘
```

---

## Cleaning Up

To avoid ongoing charges, delete the resources when done:

1. **EC2:** AWS Console → EC2 → Instances → select `DiabetesCare-App` → Instance state → Terminate
2. **DynamoDB:** AWS Console → DynamoDB → Tables → select `DiabetesCare` → Delete
3. **IAM Role:** AWS Console → IAM → Roles → `diabetescare-ec2-role` → Delete
4. **Security Group:** AWS Console → EC2 → Security Groups → select the group → Actions → Delete
