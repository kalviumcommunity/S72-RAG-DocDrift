from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings
from app.core.logging import logger

class Base(DeclarativeBase):
    pass

def _create_db_engine():
    """Initializes SQLAlchemy Async Engine with fallback to local aiosqlite."""
    url = settings.DATABASE_URL
    if url.startswith("postgresql+asyncpg"):
        try:
            import asyncpg
            return create_async_engine(
                url,
                echo=settings.DEBUG,
                future=True,
                pool_pre_ping=True,
                pool_size=10,
                max_overflow=20
            )
        except Exception as e:
            fallback_url = "sqlite+aiosqlite:///./docdrift_dev.db"
            logger.warning(f"asyncpg not available ({e}). Falling back to local SQLite: {fallback_url}")
            return create_async_engine(fallback_url, echo=settings.DEBUG, future=True)
    return create_async_engine(url, echo=settings.DEBUG, future=True)

# Create async engine
engine = _create_db_engine()

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for obtaining async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception as e:
            await session.rollback()
            logger.error(f"Database session error: {e}")
            raise
        finally:
            await session.close()
