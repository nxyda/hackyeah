from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings


def create_database_engine() -> AsyncEngine:
    """Tworzy asynchroniczny silnik SQLAlchemy dla PostgreSQL/Supabase."""

    return create_async_engine(get_settings().database_url, pool_pre_ping=True)


engine = create_database_engine()
SessionFactory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Provide an asynchronous database session for a single request.

    The session is automatically closed after the request.
    """
    async with SessionFactory() as db:
        yield db