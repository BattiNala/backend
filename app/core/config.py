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
    DB_SSLMODE: str = "require"
    DB_CHANNELBINDING: Optional[str] = "require"

    JWT_SECRET: str = "change-me"
    JWT_ALG: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MIN: int = 60
    REFRESH_TOKEN_EXPIRE_MIN: int = 10080  # 7 days
    PASSWORD_RESET_TOKEN_EXPIRE_MIN: int = 10

    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    SMTP_FROM_EMAIL: str = "sender@battinala.com"
    SMTP_USER: Optional[str] = "sender@battinala.com"
    SMTP_PASS: Optional[str] = "password"
    SMTP_START_TLS: bool = True
    SMTP_VALIDATE_CERTS: bool = False

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

    # Routing
    OSM_PBF_PATH: str = "kathmandu_valley.osm.pbf"
    ROUTE_GRID_CELL_SIZE_DEG: float = 0.005
    ROUTE_GRAPH_CACHE_PATH: str = "route_graph_cache.pkl"
    ROUTE_MAX_SNAP_DISTANCE_M: float = 5.0
    ROUTE_RESPONSE_SIMPLIFY_TOLERANCE_M: float = 7.5
    ROUTE_HIGHWAY_TYPES: list[str] = [
        "motorway",
        "trunk",
        "primary",
        "secondary",
        "tertiary",
        "residential",
        "service",
        "unclassified",
        "living_street",
        "road",
    ]
    MISTRAL_API_KEY: str


settings = Settings()
