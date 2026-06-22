import os
import boto3
from functools import lru_cache


class Settings:
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    DYNAMODB_TABLE: str = os.getenv("DYNAMODB_TABLE", "DiabetesCare")
    DYNAMODB_ENDPOINT_URL: str = os.getenv("DYNAMODB_ENDPOINT_URL", "")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "dev-secret-change-in-production")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_HOURS: int = 24
    STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local")
    STORAGE_LOCAL_PATH: str = os.getenv("STORAGE_LOCAL_PATH", "./local-storage")
    STORAGE_MAX_SIZE: int = 50 * 1024 * 1024
    S3_BUCKET: str = os.getenv("S3_BUCKET", "diabetescare-resources")
    CAROUSEL_S3_BUCKET: str = os.getenv("CAROUSEL_S3_BUCKET", "diabetescare-carousel")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def get_dynamodb():
    kwargs = {"region_name": get_settings().AWS_REGION}
    if get_settings().DYNAMODB_ENDPOINT_URL:
        kwargs["endpoint_url"] = get_settings().DYNAMODB_ENDPOINT_URL
    return boto3.resource("dynamodb", **kwargs)
