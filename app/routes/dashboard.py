from fastapi import APIRouter, Depends
from typing import Counter
from app.models import DashboardResponse, EntryResponse
from app.database import get_today_entries, get_latest_entry
from app.auth import get_current_user

router = APIRouter()


@router.get("", response_model=DashboardResponse)
async def dashboard(user: dict = Depends(get_current_user)):
    user_id = user["PK"].replace("USER#", "")
    today_entries = get_today_entries(user_id)

    counts = Counter(e["type"] for e in today_entries)

    latest_glucose = get_latest_entry(user_id, "glucose")

    return DashboardResponse(
        todayEntries=[
            EntryResponse(
                entryId=e["entryId"],
                userId=user_id,
                type=e["type"],
                value=e["value"],
                unit=e["unit"],
                notes=e.get("notes"),
                medicationId=e.get("medicationId"),
                medicationName=e.get("medicationName"),
                timestamp=e["timestamp"],
                createdAt=e["createdAt"]
            )
            for e in today_entries
        ],
        todayCounts=dict(counts),
        latestGlucose=latest_glucose["value"] if latest_glucose else None,
        latestGlucoseUnit=latest_glucose["unit"] if latest_glucose else None,
        latestGlucoseTime=latest_glucose["timestamp"] if latest_glucose else None
    )
