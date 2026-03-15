"""Database engine, session factory, and request-scoped DB dependency."""

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import settings

database_url = (
    "postgresql+asyncpg://"
    f"{settings.DB_USER}:{settings.DB_PASSWORD}"
    f"@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}?ssl=mode={settings.DB_SSLMODE}"
)
if settings.DB_CHANNELBINDING:
    database_url += f"&channel_binding={settings.DB_CHANNELBINDING}"

engine = create_async_engine(database_url, pool_pre_ping=True)

# pylint: disable=invalid-name
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session for a request lifecycle."""
    async with AsyncSessionLocal() as session:
        yield session
