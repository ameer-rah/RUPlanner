from typing import Any
from datetime import datetime

from sqlalchemy import String, Integer, Text, Boolean, UniqueConstraint, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from .database import Base


class Course(Base):
    __tablename__ = "courses"

    code: Mapped[str] = mapped_column(String(20), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, nullable=False)
    subject_code: Mapped[str | None] = mapped_column(String(10))
    course_number: Mapped[str | None] = mapped_column(String(10))
    spring_offered: Mapped[bool] = mapped_column(Boolean, default=True)
    summer_offered: Mapped[bool] = mapped_column(Boolean, default=False)
    fall_offered: Mapped[bool] = mapped_column(Boolean, default=True)
    description: Mapped[str | None] = mapped_column(Text)


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
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class SavedSchedule(Base):
    __tablename__ = "saved_schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="My Schedule")
    plan_data: Mapped[Any] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


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
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)   # E.164, e.g. +17325551234
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
