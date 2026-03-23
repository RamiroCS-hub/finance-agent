from typing import Any, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings


def build_engine_kwargs(config=settings) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "echo": False,
        "future": True,
        "pool_pre_ping": True,
        "pool_size": config.DATABASE_POOL_SIZE,
        "max_overflow": config.DATABASE_MAX_OVERFLOW,
        "pool_recycle": config.DATABASE_POOL_RECYCLE_SECONDS,
    }
    if config.DATABASE_USE_SSL:
        kwargs["connect_args"] = {"ssl": True}
    return kwargs


def build_engine(database_url: str | None = None):
    return create_async_engine(database_url or settings.DATABASE_URL, **build_engine_kwargs())


# Create the async engine
engine = build_engine()

# Create the async session maker
async_session_maker = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency to get the async database session."""
    async with async_session_maker() as session:
        yield session
