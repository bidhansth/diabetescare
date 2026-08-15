from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from typing import Optional
import uuid
import json
import base64
import boto3
from datetime import datetime, timezone
from app.models import EntryCreate, EntryResponse
from app.database import create_entry, get_entries, get_alerts, get_medication, get_entries_for_month
from app.report import build_monthly_pdf
from app.config import get_settings
from app.auth import get_current_user

router = APIRouter()


@router.get("", response_model=list[EntryResponse])
async def list_entries(
    type: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    limit: int = Query(50, le=200),
    user: dict = Depends(get_current_user)
):
    user_id = user["PK"].replace("USER#", "")
    items = get_entries(user_id, entry_type=type, from_date=from_date, to_date=to_date, limit=limit)
    return [
        EntryResponse(
            entryId=i["entryId"],
            userId=user_id,
            type=i["type"],
            value=i["value"],
            unit=i["unit"],
            notes=i.get("notes"),
            medicationId=i.get("medicationId"),
            medicationName=i.get("medicationName"),
            timestamp=i["timestamp"],
            createdAt=i["createdAt"]
        )
        for i in items
    ]


@router.post("", response_model=EntryResponse)
async def create_new_entry(body: EntryCreate, user: dict = Depends(get_current_user)):
    valid_types = {"glucose", "meal", "medication", "exercise"}
    if body.type not in valid_types:
        raise HTTPException(status_code=422, detail=f"Invalid type. Must be one of: {', '.join(valid_types)}")
    if body.value <= 0:
        raise HTTPException(status_code=422, detail="Value must be positive")

    user_id = user["PK"].replace("USER#", "")

    medication_name = None
    if body.type == "medication" and body.medicationId:
        med = get_medication(user_id, body.medicationId)
        if med:
            medication_name = med["name"]

    item = create_entry(
        user_id=user_id,
        entry_type=body.type,
        value=body.value,
        unit=body.unit,
        notes=body.notes,
        timestamp=body.timestamp,
        medicationId=body.medicationId,
        medicationName=medication_name
    )
    return EntryResponse(
        entryId=item["entryId"],
        userId=user_id,
        type=item["type"],
        value=item["value"],
        unit=item["unit"],
        notes=item.get("notes"),
        medicationId=item.get("medicationId"),
        medicationName=item.get("medicationName"),
        timestamp=item["timestamp"],
        createdAt=item["createdAt"]
    )


@router.get("/alerts")
async def list_alerts(user: dict = Depends(get_current_user)):
    user_id = user["PK"].replace("USER#", "")
    return get_alerts(user_id)


@router.post("/export-pdf")
def export_pdf(user: dict = Depends(get_current_user)):
    """Generate the current month's health report as a PDF.

    When PDF_EXPORT_LAMBDA is configured (production) the work is handed off to
    the S3-backed report Lambda: we POST a job request, the Lambda writes the
    PDF to PDF_REPORTS_S3_BUCKET and returns a presigned download URL, and this
    endpoint streams that JSON back so the browser can download the file.

    When PDF_EXPORT_LAMBDA is empty (local dev) the FastAPI app builds the PDF
    in-process and returns it as a data: URL in the same JSON shape, so the
    browser downloads it identically — no AWS Lambda or S3 required.
    """
    user_id = user["PK"].replace("USER#", "")

    now = datetime.now(timezone.utc)
    year, month = now.year, now.month
    month_label = f"{year}-{month:02d}"
    month_start = f"{year}-{month:02d}-01T00:00:00"
    next_month = month % 12 + 1
    next_year = year + (1 if month == 12 else 0)
    month_end = f"{next_year}-{next_month:02d}-01T00:00:00"

    settings = get_settings()

    if settings.PDF_EXPORT_LAMBDA:
        client = boto3.client("lambda", region_name=settings.AWS_REGION)
        payload = {
            "userId": user_id,
            "userName": user.get("name", ""),
            "email": user.get("email", ""),
            "monthStart": month_start,
            "monthEnd": month_end,
            "monthLabel": month_label,
            "requestId": str(uuid.uuid4()),
        }
        response = client.invoke(
            FunctionName=settings.PDF_EXPORT_LAMBDA,
            InvocationType="RequestResponse",
            Payload=json.dumps(payload),
        )
        if response.get("FunctionError"):
            raise HTTPException(status_code=502, detail="Report generation failed")
        result = json.loads(response["Payload"].read())
        return JSONResponse(
            content={
                "downloadUrl": result["downloadUrl"],
                "filename": result["filename"],
                "createdAt": result.get("createdAt"),
            }
        )

    entries = get_entries_for_month(user_id, month_start, month_end)
    pdf_bytes = build_monthly_pdf(
        entries,
        month_label,
        user_name=user.get("name", ""),
        start_iso=month_start,
        end_iso=month_end,
    )
    filename = f"diabetescare-report-{month_label}.pdf"
    # Local fallback: no S3/Lambda here, so return the same JSON shape as
    # production but with a data: URL (the local analog of the presigned URL).
    # The frontend downloads `data.downloadUrl` identically in both modes.
    data_url = "data:application/pdf;base64," + base64.b64encode(pdf_bytes).decode("ascii")
    return JSONResponse(
        content={
            "downloadUrl": data_url,
            "filename": filename,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }
    )
