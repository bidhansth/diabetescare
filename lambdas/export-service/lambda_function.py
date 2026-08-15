"""DiabetesCare monthly PDF report Lambda.

Triggered synchronously by the EC2 FastAPI app
(`app/routes/entries.py::export_pdf`) via lambda:InvokeFunction.

Flow:
    EC2  ->  lambda.invoke(RequestResponse){ userId, monthStart, monthEnd, ... }
    Lambda -> DynamoDB Query (full pagination) for the month's entries
            -> build_monthly_pdf(entries, ...)        # shared app.report module
            -> s3.put_object( Bucket=PDF_REPORTS_S3_BUCKET, ... )
            -> s3.generate_presigned_url(ExpiresIn=3600)
    Lambda -> { downloadUrl, filename, createdAt }

The browser opens the presigned URL and S3 streams the file to the user
immediately (Content-Disposition: attachment triggers the download without
any CORS configuration on the bucket).

Deployment (see deploy-lambda.sh): the zip must contain app/__init__.py,
app/config.py, app/database.py, app/report.py so these imports resolve:
    from app.report import build_monthly_pdf
    from app.database import get_entries_for_month
"""

import os
import json
import uuid
from datetime import datetime, timezone

import boto3

from app.report import build_monthly_pdf
from app.database import get_entries_for_month

TABLE = os.environ["DYNAMODB_TABLE"]
BUCKET = os.environ["PDF_REPORTS_S3_BUCKET"]
REGION = os.environ.get("AWS_REGION", "us-east-1")


def _month_range(month_label: str):
    """Parse a 'YYYY-MM' label into (month_start, month_end) ISO-ish bounds."""
    year, month = (int(x) for x in month_label.split("-"))
    start = f"{year}-{month:02d}-01T00:00:00"
    next_month = month % 12 + 1
    next_year = year + (1 if month == 12 else 0)
    end = f"{next_year}-{next_month:02d}-01T00:00:00"
    return start, end


def lambda_handler(event, context):
    user_id = event["userId"]
    month_label = event.get("monthLabel") or datetime.now(timezone.utc).strftime("%Y-%m")
    start = event.get("monthStart")
    end = event.get("monthEnd")
    if not (start and end):
        start, end = _month_range(month_label)

    user_name = event.get("userName", "")

    entries = get_entries_for_month(user_id, start, end)
    pdf_bytes = build_monthly_pdf(
        entries,
        month_label,
        user_name=user_name,
        start_iso=start,
        end_iso=end,
    )

    request_id = event.get("requestId") or str(uuid.uuid4())
    filename = f"diabetescare-report-{month_label}.pdf"
    key = f"reports/{user_id}/{request_id}.pdf"

    s3 = boto3.client("s3", region_name=REGION)
    s3.put_object(
        Bucket=BUCKET,
        Key=key,
        Body=pdf_bytes,
        ContentType="application/pdf",
        ContentDisposition=f'attachment; filename="{filename}"',
    )

    download_url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": BUCKET, "Key": key},
        ExpiresIn=3600,  # 1 hour
    )

    return {
        "downloadUrl": download_url,
        "filename": filename,
        "createdAt": datetime.now(timezone.utc).isoformat(),
    }
