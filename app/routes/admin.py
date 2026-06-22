from fastapi import APIRouter, Depends, HTTPException
from app.models import UserResponse
from app.database import get_all_users, update_user_role
from app.auth import get_current_admin
from app.storage import check_s3_health
from app.config import get_settings

router = APIRouter()


@router.get("/storage-status")
async def storage_status(user: dict = Depends(get_current_admin)):
    settings = get_settings()
    ok, msg = check_s3_health()
    return {
        "backend": settings.STORAGE_BACKEND,
        "healthy": ok,
        "message": msg,
    }


@router.get("/users", response_model=list[UserResponse])
async def list_users(user: dict = Depends(get_current_admin)):
    items = get_all_users()
    return [
        UserResponse(
            userId=i["PK"].replace("USER#", ""),
            name=i["name"],
            email=i["email"],
            role=i.get("role", "user"),
            createdAt=i.get("createdAt", ""),
        )
        for i in items
    ]


@router.patch("/users/{user_id}/role")
async def promote_user(user_id: str, user: dict = Depends(get_current_admin)):
    update_user_role(user_id, "admin")
    return {"detail": "User promoted to admin"}
