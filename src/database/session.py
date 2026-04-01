"""Database session management."""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config import Config
from .models import Base

logger = logging.getLogger(__name__)

# Global engine and session factory
_engine = None
_async_session_factory = None


def init_db(database_url: str | None = None):
    """Initialize database engine and session factory."""
    global _engine, _async_session_factory

    if database_url is None:
        config = Config()
        database_url = config.database_url

    logger.info(
        f"Initializing database: {database_url.split('@')[-1] if '@' in database_url else 'local'}"
    )

    _engine = create_async_engine(
        database_url,
        echo=False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
    )

    _async_session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    logger.info("Database initialized successfully")


async def create_tables():
    """Create all database tables."""
    global _engine
    if _engine is None:
        init_db()

    logger.info("Creating database tables...")
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created successfully")


@asynccontextmanager
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Get database session."""
    global _async_session_factory

    if _async_session_factory is None:
        init_db()

    async with _async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
