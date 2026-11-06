"""PostgreSQL connection for application data."""

from functools import lru_cache
from typing import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session

from backend.app.settings import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True, pool_size=10, max_overflow=20)


def get_db() -> Iterator[Session]:
    """Give a request its database session. Routes commit explicitly, so errors reach the client."""
    with Session(get_engine()) as session:
        yield session
