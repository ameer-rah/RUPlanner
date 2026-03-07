from pydantic import BaseModel, Field
from typing import List, Optional


class CourseInput(BaseModel):
    code: str


class PlanRequest(BaseModel):
    degree_level: str = Field("bachelor", description="Associate, Bachelor, or Master")
    majors: List[str]
    minors: List[str]
    completed_courses: List[str]
    target_grad_term: str = Field(..., description="e.g., Spring 2028")
    start_term: Optional[str] = Field(None, description="First term to schedule; defaults to current term if omitted")
    max_credits_per_term: int = 15


class PlannedCourse(BaseModel):
    code: str
    title: str
    credits: int
    is_elective: bool = False
    elective_options: List[str] = []  # full pool the student can swap from


class TermPlan(BaseModel):
    term: str
    courses: List[PlannedCourse]
    total_credits: int


class PlanResponse(BaseModel):
    terms: List[TermPlan]
    remaining_courses: List[str]
    warnings: List[str]
    completion_term: Optional[str] = None  # last term with courses when finished before graduation


class ProgramInfo(BaseModel):
    school: str
    degree_level: str
    major_name: str
    catalog_year: str
    display_name: str


class CourseSearchResult(BaseModel):
    code: str
    title: str
    credits: int
