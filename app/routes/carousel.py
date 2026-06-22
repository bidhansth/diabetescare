import uuid
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Optional
from app.models import CarouselSlideResponse
from app.config import get_settings
from app.database import (
    create_slide, get_slides, get_slide, delete_slide_from_db,
)
from app.auth import get_current_admin
from app.storage import save_file, delete_file, get_download_response

router = APIRouter()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}


@router.get("/carousel", response_model=list[CarouselSlideResponse])
async def list_carousel_slides():
    items = get_slides()
    settings = get_settings()
    result = []
    for i in items:
        if settings.STORAGE_BACKEND == "s3":
            import boto3
            from botocore.exceptions import ClientError
            s3 = boto3.client("s3", region_name=settings.AWS_REGION)
            try:
                url = s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": settings.CAROUSEL_S3_BUCKET, "Key": i["imageKey"]},
                    ExpiresIn=86400,
                )
            except ClientError:
                url = ""
        else:
            url = f"/api/carousel/{i['slideId']}/image"

        result.append(CarouselSlideResponse(
            slideId=i["slideId"],
            caption=i.get("caption", ""),
            imageUrl=url,
            position=i.get("position", 0),
            uploadedBy=i.get("uploadedBy", ""),
            uploadedAt=i.get("uploadedAt", ""),
        ))
    return result


@router.get("/carousel/{slide_id}/image")
async def serve_carousel_image(slide_id: str):
    slide = get_slide(slide_id)
    if not slide:
        raise HTTPException(status_code=404, detail="Slide not found")

    settings = get_settings()
    if settings.STORAGE_BACKEND == "s3":
        import boto3
        from botocore.exceptions import ClientError
        s3 = boto3.client("s3", region_name=settings.AWS_REGION)
        try:
            url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.CAROUSEL_S3_BUCKET, "Key": slide["imageKey"]},
                ExpiresIn=3600,
            )
            from fastapi.responses import RedirectResponse
            return RedirectResponse(url=url)
        except ClientError:
            raise HTTPException(status_code=404, detail="Image not found")
    else:
        response = get_download_response(
            slide["imageKey"],
            f"slide_{slide_id}",
            slide.get("contentType", "image/jpeg"),
        )
        if response is None:
            raise HTTPException(status_code=404, detail="Image not found")
        response.headers["Content-Disposition"] = "inline"
        return response


@router.post("/carousel", response_model=CarouselSlideResponse)
async def upload_carousel_slide(
    caption: str = Form(""),
    file: UploadFile = File(...),
    user: dict = Depends(get_current_admin),
):
    if file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"File type '{file.content_type}' is not allowed. Allowed: JPEG, PNG, GIF, WebP"
        )

    slide_id = str(uuid.uuid4())
    ext = (file.filename or "image").rsplit(".", 1)[-1] if "." in (file.filename or "") else "jpg"
    file_key = f"carousel/{slide_id}.{ext}"

    settings = get_settings()
    bucket = settings.CAROUSEL_S3_BUCKET if settings.STORAGE_BACKEND == "s3" else None
    size = await save_file(file, file_key, bucket)

    if size > 10 * 1024 * 1024:
        delete_file(file_key, bucket)
        raise HTTPException(status_code=422, detail="Image exceeds 10MB size limit")

    slides = get_slides()
    max_pos = max((s.get("position", 0) for s in slides), default=0)
    position = max_pos + 1

    item = create_slide(
        slide_id=slide_id,
        caption=caption,
        image_key=file_key,
        content_type=file.content_type,
        position=int(position),
        uploaded_by=user.get("PK", "").replace("USER#", ""),
        file_size=size,
    )

    if settings.STORAGE_BACKEND == "s3":
        import boto3
        from botocore.exceptions import ClientError
        s3 = boto3.client("s3", region_name=settings.AWS_REGION)
        try:
            url = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.CAROUSEL_S3_BUCKET, "Key": file_key},
                ExpiresIn=86400,
            )
        except ClientError:
            url = ""
    else:
        url = f"/api/carousel/{slide_id}/image"

    return CarouselSlideResponse(
        slideId=item["slideId"],
        caption=item.get("caption", ""),
        imageUrl=url,
        position=item.get("position", 0),
        uploadedBy=item.get("uploadedBy", ""),
        uploadedAt=item.get("uploadedAt", ""),
    )


@router.delete("/carousel/{slide_id}")
async def delete_carousel_slide(slide_id: str, user: dict = Depends(get_current_admin)):
    slide = get_slide(slide_id)
    if not slide:
        raise HTTPException(status_code=404, detail="Slide not found")

    settings = get_settings()
    bucket = settings.CAROUSEL_S3_BUCKET if settings.STORAGE_BACKEND == "s3" else None
    delete_file(slide["imageKey"], bucket)
    delete_slide_from_db(slide_id)
    return {"detail": "Slide deleted"}
