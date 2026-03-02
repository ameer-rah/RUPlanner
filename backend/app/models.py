from typing import Any

from sqlalchemy import String, Integer, Text, Boolean, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from .database import Base


class Course(Base):
    """
    A single course offered at Rutgers New Brunswick.
    Populated by management/ingest_courses.py via the Rutgers SIS API.
    Prerequisites are stored separately in the JSON catalogs until
    a prerequisite-extraction pipeline is added.
    """

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
    """
    One row per academic program (major, minor, or certificate).
    Adding a new major = inserting a row; no new JSON file needed.

    requirements stores the full dict that the planner already knows
    how to consume: required_courses, electives, science_requirement, etc.
    """

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
