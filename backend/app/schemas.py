import re
from pydantic import BaseModel, Field, field_validator
from typing import Annotated, Dict, List, Optional

_COURSE_CODE_RE = re.compile(r"^[A-Z]{1,8}\d{1,4}[A-Z]?$")


class CourseInput(BaseModel):
    code: str


class ElectiveOption(BaseModel):
    code: str
    title: str
    credits: int
    prerequisites: List[str] = []


class PlanRequest(BaseModel):
    degree_level: str = Field("bachelor", description="Associate, Bachelor, or Master")
    majors: Annotated[List[str], Field(max_length=5)]
    minors: Annotated[List[str], Field(max_length=5)]
    concentrations: Annotated[List[str], Field(default=[], max_length=5, description="Optional concentration programs to layer on top of the major.")]
    completed_courses: Annotated[List[str], Field(max_length=200)]
    target_grad_term: str = Field(..., max_length=20, description="e.g., Spring 2028")
    start_term: Optional[str] = Field(None, max_length=20, description="First term to schedule; defaults to current term if omitted")
    max_credits_per_term: int = Field(default=15, ge=1, le=24)
    summer_max_credits: int = Field(
        default=12, ge=0, le=18,
        description="Maximum total credits allowed in any Summer term (SAS policy: no more than 12 credits).",
    )
    winter_max_credits: int = Field(
        default=4, ge=0, le=9,
        description="Maximum credits allowed in any Winter term (SAS policy: max 4 credits for one course, or two 1–1.5 credit courses up to 3 credits).",
    )
    preferred_seasons: Annotated[List[str], Field(default=["Spring", "Fall"], max_length=4, description="Seasons in which the student wants to enroll (Spring, Summer, Fall, Winter). Defaults to Spring and Fall.")]

    @field_validator("completed_courses", mode="before")
    @classmethod
    def validate_course_codes(cls, v: list) -> list:
        for code in v:
            if not isinstance(code, str) or not _COURSE_CODE_RE.match(code):
                raise ValueError(f"Invalid course code: {code!r}")
        return v

    @field_validator("preferred_seasons", mode="before")
    @classmethod
    def validate_seasons(cls, v: list) -> list:
        valid = {"Spring", "Summer", "Fall", "Winter"}
        for s in v:
            if s not in valid:
                raise ValueError(f"Invalid season: {s!r}")
        return v

    @field_validator("degree_level", mode="before")
    @classmethod
    def validate_degree_level(cls, v: str) -> str:
        valid = {"associate", "bachelor", "master", "doctorate"}
        if v.lower() not in valid:
            raise ValueError(f"Invalid degree level: {v!r}")
        return v


class PlannedCourse(BaseModel):
    code: str
    title: str
    credits: int
    is_elective: bool = False
    prerequisites: List[str] = []
    elective_options: List[ElectiveOption] = []
    core_tags: List[str] = []


class TermPlan(BaseModel):
    term: str
    courses: List[PlannedCourse]
    total_credits: int


class CoreCurriculumBlock(BaseModel):
    title: str
    total_courses: Optional[int]
    courses: List[str]
    is_elective: bool
    completed: List[str]
    needed: int


class TranscriptResult(BaseModel):
    matched: List[str]
    in_progress: List[str] = []     # courses currently enrolled in (no grade yet)
    inferred: Dict[str, str] = {}   # {rutgers_code: "Transfer: ORIG DEPT NUM — Title"}


class CourseStatus(BaseModel):
    code: str
    status: str  # "completed" | "in_progress" | "planned" | "not_scheduled"


class ProgramSummary(BaseModel):
    name: str
    type: str  # "major" | "minor" | "concentration"
    required: List[CourseStatus] = []
    electives_needed: int = 0
    electives_completed: List[str] = []
    electives_planned: List[str] = []
    science_completed: List[str] = []
    stats_completed: List[str] = []


class PlanResponse(BaseModel):
    terms: List[TermPlan]
    remaining_courses: List[str]
    warnings: List[str]
    completion_term: Optional[str] = None
    completed_credits: int = 0
    total_credits: int = 0
    core_curriculum_name: Optional[str] = None
    core_curriculum_blocks: List[CoreCurriculumBlock] = []
    completed_course_map: Dict[str, str] = {}  # {course_code: requirement_label}
    programs_summary: List["ProgramSummary"] = []


class ProgramInfo(BaseModel):
    school: str
    degree_level: str
    major_name: str
    catalog_year: str
    display_name: str
    tracks: List[str] = []


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


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class SaveScheduleRequest(BaseModel):
    name: str = "My Schedule"
    plan_data: dict


class SavedScheduleInfo(BaseModel):
    id: int
    name: str
    created_at: str
    plan_data: dict


class SnipeCreate(BaseModel):
    course_code: str
    course_title: str
    section_index: str
    section_number: str
    year: str
    term: str          # "9"=Fall, "1"=Spring, "7"=Summer, "0"=Winter
    campus: str = "NB"
    phone_number: str  # E.164 format, e.g. +17325551234


class SnipeOut(BaseModel):
    id: int
    course_code: str
    course_title: str
    section_index: str
    section_number: str
    year: str
    term: str
    campus: str
    phone_number: str
    active: bool
    notified_at: Optional[str]
    created_at: str
