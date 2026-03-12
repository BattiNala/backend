"""Application settings loaded from environment and defaults."""

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed runtime configuration for the application."""

    APP_NAME: str = "BattiNala Backend"
    VERSION: str = "0.2.0"
    API_V1_STR: str = "/api/v1"
    DB_HOST: str = "localhost"
    DB_PORT: int = 5432
    DB_USER: str = "postgres"
    DB_PASSWORD: str = "password"
    DB_NAME: str = "battinala_db"

    JWT_SECRET: str = "change-me"
    JWT_ALG: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MIN: int = 60
    REFRESH_TOKEN_EXPIRE_MIN: int = 10080  # 7 days

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # S3 Settings
    S3_BUCKET_NAME: str = "battinala"
    S3_REGION_NAME: str = "us-east-1"
    S3_ENDPOINT_URL: str
    # e.g. "https://<accountid>.r2.cloudflarestorage.com" for Cloudflare R2
    S3_ACCESS_KEY_ID: str
    S3_SECRET_ACCESS_KEY: str
    S3_FORCE_PATH_STYLE: Optional[bool] = None
    # True for MinIO/R2, False for AWS S3, None to auto-detect


settings = Settings()
