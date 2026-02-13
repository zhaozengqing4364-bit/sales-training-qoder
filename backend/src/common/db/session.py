"""
Database session management with async support
"""
import os
from collections.abc import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.exc import SQLAlchemyError

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/ai_practice")

# Determine if using SQLite (for development/testing)
is_sqlite = DATABASE_URL.startswith("sqlite")

# Create engine with appropriate settings for the database type
if is_sqlite:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
    )
else:
    engine = create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=20,
        max_overflow=10,
    )

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for FastAPI to get database session.
    
    P1-9: Removed implicit auto-commit. Business logic must explicitly
    call session.commit() to control transaction boundaries.
    This prevents accidental commits of incomplete data.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except (SQLAlchemyError, ValueError):
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database - create all tables"""
    from common.db.models import Base
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_database_url() -> str:
    """Get the database URL for creating new connections."""
    return DATABASE_URL
