from typing import Any
from datetime import UTC, datetime

from sqlalchemy import String, Integer, Float, Text, Boolean, UniqueConstraint, DateTime, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from .database import Base


def utc_now() -> datetime:
    """Return naive UTC for compatibility with the existing database columns."""
    return datetime.now(UTC).replace(tzinfo=None)


class Course(Base):
    __tablename__ = "courses"

    # The full Rutgers offering-unit/subject/number tuple is the identity.
    # Friendly aliases such as CS111 are display/search fields and are not unique.
    raw_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    credits: Mapped[float] = mapped_column(Float, nullable=False)
    subject_code: Mapped[str | None] = mapped_column(String(10))
    course_number: Mapped[str | None] = mapped_column(String(10))
    spring_offered: Mapped[bool] = mapped_column(Boolean, default=True)
    summer_offered: Mapped[bool] = mapped_column(Boolean, default=False)
    fall_offered: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str | None] = mapped_column(Text)
    offering_unit_code: Mapped[str | None] = mapped_column(String(4), nullable=True)


class Program(Base):
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    school: Mapped[str] = mapped_column(String(50), nullable=False)
    degree_level: Mapped[str] = mapped_column(String(20), nullable=False)
    major_name: Mapped[str] = mapped_column(String(255), nullable=False)
    catalog_year: Mapped[str] = mapped_column(String(10), nullable=False)
    requirements: Mapped[Any] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "school", "degree_level", "major_name", "catalog_year",
            name="uq_program",
        ),
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    onboarding_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    planner_profile: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    last_plan: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class SavedSchedule(Base):
    __tablename__ = "saved_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="My Schedule")
    plan_data: Mapped[Any] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    __table_args__ = (Index("ix_saved_schedules_user_created", "user_id", "created_at"),)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)


class Snipe(Base):
    __tablename__ = "snipes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    course_code: Mapped[str] = mapped_column(String(20), nullable=False)   # e.g. "CS111"
    course_title: Mapped[str] = mapped_column(String(255), nullable=False)
    section_index: Mapped[str] = mapped_column(String(10), nullable=False)  # e.g. "08735"
    section_number: Mapped[str] = mapped_column(String(10), nullable=False) # e.g. "01"
    year: Mapped[str] = mapped_column(String(6), nullable=False)            # e.g. "2026"
    term: Mapped[str] = mapped_column(String(4), nullable=False)            # "9"=Fall,"1"=Spring
    campus: Mapped[str] = mapped_column(String(5), nullable=False, default="NB")
    # Fernet ciphertext is typically ~100+ characters even for an E.164 value.
    phone_number: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utc_now)

    __table_args__ = (
        Index("ix_snipes_user_active", "user_id", "active"),
        Index("ix_snipes_pollable", "active", "notified_at"),
    )
