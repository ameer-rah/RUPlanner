import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ruplanner.db")

is_sqlite = DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False, "timeout": 30} if is_sqlite else {}
engine_options = {"connect_args": connect_args, "pool_pre_ping": not is_sqlite}
if not is_sqlite:
    engine_options["pool_recycle"] = 300
engine = create_engine(DATABASE_URL, **engine_options)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Shared declarative base used to register every database model."""

    pass


def get_db():
    """Provide one request-scoped database session and always close it.

    Yields:
        A SQLAlchemy session for a FastAPI dependency consumer.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
