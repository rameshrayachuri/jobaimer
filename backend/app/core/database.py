from collections.abc import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings

# Engine is created lazily so a missing DATABASE_URL only fails when
# a request actually hits a DB endpoint, not at startup.
_engine = None
_session_factory = None


def _get_engine():
    global _engine, _session_factory
    if _engine is None:
        url = settings.DATABASE_URL
        if not url:
            raise RuntimeError(
                "DATABASE_URL is not set. Add it to your .env file.\n"
                "Get your Neon connection string from https://console.neon.tech"
            )
        url = url.replace("postgresql://", "postgresql+asyncpg://").replace(
            "postgres://", "postgresql+asyncpg://"
        )
        _engine = create_async_engine(
            url,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=300,
            echo=settings.ENVIRONMENT == "development",
        )
        _session_factory = async_sessionmaker(
            _engine, class_=AsyncSession,
            expire_on_commit=False, autocommit=False, autoflush=False,
        )
    return _engine, _session_factory


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    _, factory = _get_engine()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
