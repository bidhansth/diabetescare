import os
import io
from pathlib import Path
import boto3
from botocore.exceptions import ClientError
from fastapi import UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from app.config import get_settings


ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "image/jpeg": "image",
    "image/png": "image",
    "image/gif": "image",
    "image/webp": "image",
    "video/mp4": "video",
    "video/webm": "video",
    "application/msword": "word",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "word",
}


def validate_file(content_type: str) -> tuple[bool, str]:
    if content_type not in ALLOWED_TYPES:
        return False, f"File type '{content_type}' is not allowed"
    return True, ALLOWED_TYPES[content_type]


def _get_s3_client():
    settings = get_settings()
    return boto3.client("s3", region_name=settings.AWS_REGION)


def check_s3_health() -> tuple[bool, str]:
    settings = get_settings()
    if settings.STORAGE_BACKEND != "s3":
        return False, f"Storage backend is '{settings.STORAGE_BACKEND}', not S3"
    try:
        s3 = _get_s3_client()
        s3.head_bucket(Bucket=settings.S3_BUCKET)
        return True, "S3 bucket is accessible"
    except ClientError as e:
        code = e.response["Error"]["Code"]
        if code == "404":
            return False, f"S3 bucket '{settings.S3_BUCKET}' does not exist"
        elif code == "403":
            return False, f"No permission to access S3 bucket '{settings.S3_BUCKET}'"
        return False, f"S3 error: {e.response['Error']['Message']}"
    except Exception as e:
        return False, f"S3 error: {str(e)}"


def get_local_path(file_key: str) -> Path:
    return Path(get_settings().STORAGE_LOCAL_PATH) / file_key


async def save_file(file: UploadFile, file_key: str, bucket: str | None = None) -> int:
    settings = get_settings()
    if settings.STORAGE_BACKEND == "s3":
        s3 = _get_s3_client()
        bucket = bucket or settings.S3_BUCKET
        buffer = io.BytesIO()
        size = 0
        while chunk := await file.read(8192):
            buffer.write(chunk)
            size += len(chunk)
        buffer.seek(0)
        s3.upload_fileobj(buffer, bucket, file_key)
        return size
    else:
        local_path = get_local_path(file_key)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        size = 0
        with open(local_path, "wb") as f:
            while chunk := await file.read(8192):
                f.write(chunk)
                size += len(chunk)
        return size


def delete_file(file_key: str, bucket: str | None = None):
    settings = get_settings()
    if settings.STORAGE_BACKEND == "s3":
        s3 = _get_s3_client()
        bucket = bucket or settings.S3_BUCKET
        try:
            s3.delete_object(Bucket=bucket, Key=file_key)
        except ClientError:
            pass
    else:
        local_path = get_local_path(file_key)
        if local_path.exists():
            os.remove(local_path)
            parent = local_path.parent
            while parent != Path(settings.STORAGE_LOCAL_PATH) and not any(parent.iterdir()):
                parent.rmdir()
                parent = parent.parent


def get_download_response(file_key: str, filename: str, content_type: str, bucket: str | None = None):
    settings = get_settings()
    if settings.STORAGE_BACKEND == "s3":
        s3 = _get_s3_client()
        bucket = bucket or settings.S3_BUCKET
        try:
            response = s3.get_object(Bucket=bucket, Key=file_key)
            return StreamingResponse(
                response["Body"].iter_chunks(),
                media_type=content_type,
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        except ClientError:
            return None
    else:
        local_path = get_local_path(file_key)
        if not local_path.exists():
            return None
        return FileResponse(
            path=local_path,
            media_type=content_type,
            filename=filename,
        )
