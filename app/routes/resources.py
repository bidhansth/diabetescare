import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Header
from typing import Optional
from app.models import ResourceResponse
from app.config import get_settings
from app.database import (
    create_resource, get_resources, get_resource,
    delete_resource_from_db, increment_download_count,
)
from app.auth import get_current_user, get_current_admin, decode_token
from app.database import get_user_by_id
from app.storage import validate_file, save_file, delete_file, get_download_response

router = APIRouter()


@router.get("", response_model=list[ResourceResponse])
async def list_resources(user: dict = Depends(get_current_user)):
    items = get_resources()
    return [
        ResourceResponse(
            resourceId=i["resourceId"],
            name=i["name"],
            fileType=i["fileType"],
            fileSize=i["fileSize"],
            uploadedBy=i.get("uploadedBy", ""),
            uploadedAt=i["uploadedAt"],
            downloadCount=i.get("downloadCount", 0),
            description=i.get("description", ""),
        )
        for i in items
    ]


@router.post("", response_model=ResourceResponse)
async def upload_resource(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: str = Form(""),
    user: dict = Depends(get_current_admin),
):
    valid, file_type = validate_file(file.content_type or "application/octet-stream")
    if not valid:
        raise HTTPException(status_code=422, detail=file_type)

    settings = get_settings()
    if settings.STORAGE_BACKEND == "s3":
        from app.storage import check_s3_health
        ok, msg = check_s3_health()
        if not ok:
            raise HTTPException(status_code=503, detail=f"S3 storage is misconfigured: {msg}")

    resource_id = str(uuid.uuid4())
    file_key = f"resources/{resource_id}/{file.filename or 'file'}"

    size = await save_file(file, file_key)

    if size > 50 * 1024 * 1024:
        delete_file(file_key)
        raise HTTPException(status_code=422, detail="File exceeds 50MB size limit")

    item = create_resource(
        resource_id=resource_id,
        name=name,
        file_type=file_type,
        file_key=file_key,
        file_size=size,
        content_type=file.content_type or "application/octet-stream",
        uploaded_by=user.get("PK", ""),
        description=description,
    )

    return ResourceResponse(
        resourceId=item["resourceId"],
        name=item["name"],
        fileType=item["fileType"],
        fileSize=item["fileSize"],
        uploadedBy=item["uploadedBy"],
        uploadedAt=item["uploadedAt"],
        downloadCount=item["downloadCount"],
        description=item.get("description", ""),
    )


@router.get("/{resource_id}/download")
async def download_resource(
    resource_id: str,
    token: Optional[str] = Query(None),
    authorization: Optional[str] = Header(None),
):
    user = None
    if token:
        try:
            payload = decode_token(token)
            user = get_user_by_id(payload.get("sub"))
        except Exception:
            pass
    if not user and authorization:
        try:
            scheme, _, t = authorization.partition(" ")
            if scheme.lower() == "bearer":
                payload = decode_token(t)
                user = get_user_by_id(payload.get("sub"))
        except Exception:
            pass
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")

    resource = get_resource(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    increment_download_count(resource_id)

    original_filename = resource["fileKey"].rsplit("/", 1)[-1] or resource["name"]
    response = get_download_response(
        resource["fileKey"],
        original_filename,
        resource["contentType"],
    )
    if response is None:
        raise HTTPException(status_code=404, detail="File not found on storage")
    return response


@router.delete("/{resource_id}")
async def delete_resource_endpoint(resource_id: str, user: dict = Depends(get_current_admin)):
    resource = get_resource(resource_id)
    if not resource:
        raise HTTPException(status_code=404, detail="Resource not found")

    delete_file(resource["fileKey"])
    delete_resource_from_db(resource_id)
    return {"detail": "Resource deleted"}
