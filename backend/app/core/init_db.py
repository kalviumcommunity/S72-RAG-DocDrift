from app.core.database import engine, Base
from app.core.logging import logger
import app.models # Ensure all models are registered with Base.metadata


async def init_database() -> None:
    """Creates all database tables defined in SQLAlchemy models if they do not exist."""
    async with engine.begin() as conn:
        logger.info("Initializing database tables...")
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables verified/created successfully.")
