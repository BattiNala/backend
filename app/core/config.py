from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "BattiNala Backend"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = (
        "postgresql+psycopg://postgres:postgres@localhost:5432/battinala"
    )
    JWT_SECRET: str = "change-me"
    JWT_ALG: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MIN: int = 60

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
