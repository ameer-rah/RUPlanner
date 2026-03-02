import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# SQLite by default for local dev; set DATABASE_URL env var for PostgreSQL.
# PostgreSQL example: postgresql://ruplanner:ruplanner@localhost:5432/ruplanner
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./ruplanner.db")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
