from pydantic import BaseModel, Field
from typing import List, Optional


class CourseInput(BaseModel):
    code: str


class ElectiveOption(BaseModel):
    code: str
    title: str
    credits: int
    prerequisites: List[str] = []


class PlanRequest(BaseModel):
    degree_level: str = Field("bachelor", description="Associate, Bachelor, or Master")
    majors: List[str]
    minors: List[str]
    completed_courses: List[str]
    target_grad_term: str = Field(..., description="e.g., Spring 2028")
    start_term: Optional[str] = Field(None, description="First term to schedule; defaults to current term if omitted")
    max_credits_per_term: int = 15
    summer_max_credits: int = Field(
        default=12,
        description="Maximum total credits allowed in any Summer term (SAS policy: no more than 12 credits).",
    )
    winter_max_credits: int = Field(
        default=4,
        description="Maximum credits allowed in any Winter term (SAS policy: max 4 credits for one course, or two 1–1.5 credit courses up to 3 credits).",
    )
    preferred_seasons: List[str] = Field(
        default=["Spring", "Fall"],
        description="Seasons in which the student wants to enroll (Spring, Summer, Fall, Winter). Defaults to Spring and Fall.",
    )


class PlannedCourse(BaseModel):
    code: str
    title: str
    credits: int
    is_elective: bool = False
    prerequisites: List[str] = []
    elective_options: List[ElectiveOption] = []


class TermPlan(BaseModel):
    term: str
    courses: List[PlannedCourse]
    total_credits: int


class PlanResponse(BaseModel):
    terms: List[TermPlan]
    remaining_courses: List[str]
    warnings: List[str]
    completion_term: Optional[str] = None


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


class UserCreate(BaseModel):
    email: str
    password: str


class GoogleAuthRequest(BaseModel):
    credential: str


class Token(BaseModel):
    access_token: str
    token_type: str


class SaveScheduleRequest(BaseModel):
    name: str = "My Schedule"
    plan_data: dict


class SavedScheduleInfo(BaseModel):
    id: int
    name: str
    created_at: str
    plan_data: dict
