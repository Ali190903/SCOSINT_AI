"""
SCOSINT_AI Database — SQLAlchemy Async Engine

WHY: PostgreSQL + AsyncPG — async I/O ilə DB əməliyyatları.
Scan nəticələri burada saxlanılır. Alembic migration-ları ilə
schema dəyişiklikləri idarə edilir.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import get_settings

# Lazy initialization — yalnız lazım olanda yaradılır
_engine = None
_session_factory = None


def get_engine():
    """Async SQLAlchemy engine (singleton)."""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database.url,
            echo=settings.api_debug,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Async session factory (singleton)."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


async def get_session() -> AsyncSession:
    """Dependency injection üçün — FastAPI route-larında istifadə."""
    factory = get_session_factory()
    async with factory() as session:
        yield session
