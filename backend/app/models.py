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
