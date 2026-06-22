from fastapi import APIRouter, Depends, HTTPException
from app.models import MedicationCreate, MedicationResponse
from app.database import create_medication, get_medications, delete_medication
from app.auth import get_current_user

router = APIRouter()


@router.get("", response_model=list[MedicationResponse])
async def list_medications(user: dict = Depends(get_current_user)):
    user_id = user["PK"].replace("USER#", "")
    items = get_medications(user_id)
    return [
        MedicationResponse(
            medicationId=i["medicationId"],
            name=i["name"],
            dosage=i["dosage"],
            createdAt=i["createdAt"]
        )
        for i in items
    ]


@router.post("", response_model=MedicationResponse)
async def add_medication(body: MedicationCreate, user: dict = Depends(get_current_user)):
    user_id = user["PK"].replace("USER#", "")
    item = create_medication(user_id, body.name, body.dosage)
    return MedicationResponse(
        medicationId=item["medicationId"],
        name=item["name"],
        dosage=item["dosage"],
        createdAt=item["createdAt"]
    )


@router.delete("/{med_id}")
async def remove_medication(med_id: str, user: dict = Depends(get_current_user)):
    user_id = user["PK"].replace("USER#", "")
    delete_medication(user_id, med_id)
    return {"ok": True}
