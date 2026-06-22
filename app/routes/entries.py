from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from app.models import EntryCreate, EntryResponse
from app.database import create_entry, get_entries, get_alerts, get_medication
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
