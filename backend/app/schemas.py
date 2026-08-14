import re
from pydantic import BaseModel, Field, field_validator
from typing import Annotated, Dict, List, Optional

_COURSE_CODE_RE = re.compile(r"^(?:[A-Z]{1,8}\d{1,4}[A-Z]?|\d{2}:\d{3}:\d{3,4})$")
_PROGRAM_NAME_RE = re.compile(r"^[A-Za-z0-9 _,.\-&/'()–—]+$")


class CourseInput(BaseModel):
    """Represent a course code supplied as planner input."""
    code: str


class ElectiveOption(BaseModel):
    """Describe one concrete course that can fill an elective slot."""
    code: str
    title: str
    credits: float
    prerequisites: List[str] = []


class PlanRequest(BaseModel):
    """Validate the academic profile and constraints used to build a plan."""
    degree_level: str = Field("bachelor", description="Associate, Bachelor, or Master")
    majors: Annotated[List[str], Field(max_length=5)]
    minors: Annotated[List[str], Field(max_length=5)]
    concentrations: Annotated[List[str], Field(default=[], max_length=5, description="Optional concentration programs to layer on top of the major.")]
    completed_courses: Annotated[List[str], Field(max_length=200)]
    in_progress_courses: Annotated[List[str], Field(default=[], max_length=100)]
    in_progress_terms: Dict[str, str] = Field(default_factory=dict)
    in_progress_credit_hours: Dict[str, float] = Field(default_factory=dict)
    earned_degree_credits: float = Field(
        default=0,
        ge=0,
        le=300,
        description="Registrar-reported earned degree credits, including unmatched transfer credit.",
    )
    course_grades: Dict[str, str] = Field(default_factory=dict)
    class_year: Optional[int] = Field(default=None, ge=1, le=10)

    @field_validator("majors", "minors", "concentrations", mode="before")
    @classmethod
    def validate_program_names(cls, v: list) -> list:
        """Reject unsafe or excessively long program names before planning.

        Args:
            v: Program names submitted by the client.

        Returns:
            The validated list without modification.

        Raises:
            ValueError: If a name has an invalid type, length, or character.
        """
        for name in v:
            if not isinstance(name, str) or len(name) > 200:
                raise ValueError(f"Invalid program name: {name!r}")
            if not _PROGRAM_NAME_RE.match(name):
                raise ValueError(f"Program name contains disallowed characters: {name!r}")
        return v
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

    @field_validator("completed_courses", "in_progress_courses", mode="before")
    @classmethod
    def validate_course_codes(cls, v: list) -> list:
        """Ensure completed and in-progress courses use supported code formats.

        Args:
            v: Course codes submitted by the client.

        Returns:
            The validated list without modification.

        Raises:
            ValueError: If any course code is malformed.
        """
        for code in v:
            if not isinstance(code, str) or not _COURSE_CODE_RE.match(code):
                raise ValueError(f"Invalid course code: {code!r}")
        return v

    @field_validator("course_grades", mode="before")
    @classmethod
    def validate_course_grades(cls, v: dict) -> dict:
        """Validate grade mappings and normalize their values for comparison.

        Args:
            v: Mapping of course codes to registrar grades.

        Returns:
            A mapping with uppercase course codes and grades.

        Raises:
            ValueError: If the mapping is too large or contains invalid data.
        """
        if len(v) > 200:
            raise ValueError("Too many course grades")
        for code, grade in v.items():
            if not isinstance(code, str) or not _COURSE_CODE_RE.match(code.upper()):
                raise ValueError(f"Invalid course code: {code!r}")
            if not isinstance(grade, str) or len(grade) > 4:
                raise ValueError(f"Invalid grade for {code!r}")
        return {code.upper(): grade.upper() for code, grade in v.items()}

    @field_validator("preferred_seasons", mode="before")
    @classmethod
    def validate_seasons(cls, v: list) -> list:
        """Restrict scheduling preferences to supported academic seasons.

        Args:
            v: Preferred season names.

        Returns:
            The validated list without modification.

        Raises:
            ValueError: If any season is unsupported.
        """
        valid = {"Spring", "Summer", "Fall", "Winter"}
        for s in v:
            if s not in valid:
                raise ValueError(f"Invalid season: {s!r}")
        return v

    @field_validator("degree_level", mode="before")
    @classmethod
    def validate_degree_level(cls, v: str) -> str:
        """Restrict plan generation to recognized degree levels.

        Args:
            v: Degree level supplied by the client.

        Returns:
            The validated degree level.

        Raises:
            ValueError: If the degree level is unsupported.
        """
        valid = {"associate", "bachelor", "master", "doctorate"}
        if v.lower() not in valid:
            raise ValueError(f"Invalid degree level: {v!r}")
        return v


class PlannedCourse(BaseModel):
    """Describe a course placement and its role in a generated plan."""
    code: str
    title: str
    credits: float
    is_elective: bool = False
    is_general_elective: bool = False
    prerequisites: List[str] = []
    elective_options: List[ElectiveOption] = []
    core_tags: List[str] = []
    is_in_progress: bool = False


class TermPlan(BaseModel):
    """Group planned courses and their credit total for one academic term."""
    term: str
    courses: List[PlannedCourse]
    total_credits: float


class CoreCurriculumBlock(BaseModel):
    """Summarize progress and options for one core-curriculum requirement."""
    title: str
    total_courses: Optional[int]
    courses: List[str]
    is_elective: bool
    completed: List[str]
    needed: int
    available_courses: List[str] = []
    goal_slots: List[List[str]] = []
    completed_goal_tags: List[str] = []


class CourseDetail(BaseModel):
    """Store normalized transcript details used to audit course matching."""
    title_raw: str
    raw_code: Optional[str] = None
    rutgers_code: Optional[str] = None
    grade: str = ""
    passed: bool = False
    failed: bool = False
    is_transfer: bool = False
    is_in_progress: bool = False
    semester: str = ""
    credits: float = 0.0
    equivalency_note: str = ""


class TranscriptResult(BaseModel):
    """Return normalized transcript courses and planner-ready status data."""
    matched: List[str]
    in_progress: List[str] = []
    inferred: Dict[str, str] = {}
    courses_detail: List["CourseDetail"] = []
    ai_summary: str = ""
    student_name: str = ""
    earned_degree_credits: float = 0
    in_progress_terms: Dict[str, str] = Field(default_factory=dict)
    in_progress_credit_hours: Dict[str, float] = Field(default_factory=dict)


class CourseStatus(BaseModel):
    """Associate a required course with its current completion state."""
    code: str
    status: str  # "completed" | "in_progress" | "planned" | "not_scheduled"


class ProgramSummary(BaseModel):
    """Summarize completed and outstanding requirements for one program."""
    name: str
    type: str  # "major" | "minor" | "concentration"
    required: List[CourseStatus] = []
    electives_needed: int = 0
    electives_completed: List[str] = []
    electives_planned: List[str] = []
    elective_options: List[str] = []
    elective_min_300_plus: int = 0
    elective_min_400_plus: int = 0
    science_completed: List[str] = []
    science_options: List[List[str]] = []
    stats_completed: List[str] = []
    stats_options: List[str] = []
    requirement_groups: List[Dict] = []


class PlanResponse(BaseModel):
    """Represent a generated multi-term plan and its completion metadata."""
    terms: List[TermPlan]
    remaining_courses: List[str]
    warnings: List[str]
    completion_term: Optional[str] = None
    completed_credits: float = 0
    total_credits: float = 0
    core_curriculum_name: Optional[str] = None
    core_curriculum_blocks: List[CoreCurriculumBlock] = []
    completed_course_map: Dict[str, str] = {}  # {course_code: requirement_label}
    programs_summary: List["ProgramSummary"] = []


class ProgramInfo(BaseModel):
    """Expose catalog metadata needed to select a degree program or track."""
    school: str
    degree_level: str
    major_name: str
    catalog_year: str
    display_name: str
    tracks: List[str] = []
    track_labels: Dict[str, str] = {}
    track_dimensions: List[Dict] = []


class CourseSearchResult(BaseModel):
    """Provide the catalog fields displayed for a course search match."""
    code: str
    title: str
    credits: float
    raw_code: Optional[str] = None
    prerequisites: List[str] = []
    core_tags: List[str] = []


class GoogleAuthRequest(BaseModel):
    """Carry the Google identity credential exchanged during sign-in."""
    credential: str


class Token(BaseModel):
    """Return an access token and its authentication scheme."""
    access_token: str
    token_type: str


class SaveScheduleRequest(BaseModel):
    """Carry a named plan snapshot for persistent schedule storage."""
    name: str = "My Schedule"
    plan_data: dict


class SavedScheduleInfo(BaseModel):
    """Describe a persisted schedule returned to its owner."""
    id: int
    name: str
    created_at: str
    plan_data: dict


class SnipeCreate(BaseModel):
    """Validate the section and contact data needed to create an alert."""
    course_code: str
    course_title: str
    section_index: str
    section_number: str
    year: str
    term: str          # "9"=Fall, "1"=Spring, "7"=Summer, "0"=Winter
    campus: str = "NB"
    phone_number: str  # E.164 format, e.g. +17325551234


class SnipeOut(BaseModel):
    """Expose a stored section alert with decrypted owner-facing details."""
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
