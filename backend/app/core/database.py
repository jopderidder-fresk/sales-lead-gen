import asyncio
from collections.abc import Coroutine
from typing import TypeVar

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

_T = TypeVar("_T")

engine = create_async_engine(
    settings.database_url,
    echo=settings.sql_echo,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_session() -> AsyncSession:  # type: ignore[misc]
    async with async_session_factory() as session:
        yield session


# Persistent event loop for Celery worker processes.  Reusing a single loop
# across ``run_async()`` calls prevents the "Future attached to a different
# loop" error that occurs when asyncpg connections created on a previous
# (now-closed) event loop are reused after ``asyncio.run()`` closes it.
_worker_loop: asyncio.AbstractEventLoop | None = None


def _get_worker_loop() -> asyncio.AbstractEventLoop:
    global _worker_loop
    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
    return _worker_loop


def run_async(coro: Coroutine[object, object, _T]) -> _T:
    """Run an async coroutine from a synchronous Celery task.

    Uses a persistent event loop so that pooled asyncpg connections stay
    bound to the same loop across consecutive task invocations in a
    prefork worker process.
    """
    loop = _get_worker_loop()
    return loop.run_until_complete(coro)
