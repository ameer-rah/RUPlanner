"""
transcript_parser.py
Rutgers New Brunswick Transcript Parser

Parses the fixed-width column format used by Rutgers SIS transcripts:

  TITLE                 SCH  DEPT  CRS  SEC   CRED  PR  GRADE
  INTRO COMPUTER SCI    01   198   111  52     4.0   B+
  STDNTS IN TRANSITION  01   090   220  04     1.0   P  PA
  EUR FASHION & DESIGN  01   510   232  01     3.0   E  F
  SOFTWARE METHODOLOGY  01   198   213  03     4.0       (in-progress, no grade)
"""

import re
from dataclasses import dataclass, field
from typing import Optional


# -- Grading rules -------------------------------------------------------------

NON_PASSING_GRADES = {
    "F", "W", "WF", "WD", "NC", "U", "UF", "NR", "NG", "TZ", "AU", "IN", "I",
}

TRANSFER_PASSING = {"TR", "T", "TE", "TC"}


def _grade_is_passing(grade: str, pr_flag: str = "") -> bool:
    if not grade:
        return False  # in-progress / no grade yet
    g = grade.upper().strip()
    if g in NON_PASSING_GRADES:
        return False
    if g in TRANSFER_PASSING:
        return True
    if g == "PA":
        return True
    if g == "NC":
        return False
    return g not in NON_PASSING_GRADES


# -- Data classes --------------------------------------------------------------

@dataclass
class ParsedCourse:
    title_raw: str
    sch: str
    dept: str
    crs: str
    section: str
    credits: float
    pr_flag: str
    grade: str
    course_code: str       # e.g. "01:198:111"
    normalized_code: str   # e.g. "198:111"  (dept:crs)
    semester: str
    is_transfer: bool
    is_in_progress: bool
    passed: bool
    is_retake: bool


@dataclass
class TranscriptParseResult:
    student_name: str = ""
    student_id: str = ""
    courses: list = field(default_factory=list)
    semesters: list = field(default_factory=list)
    total_transfer_credits: float = 0.0
    warnings: list = field(default_factory=list)

    def get_completed_courses(self):
        return [c for c in self.courses if c.passed and not c.is_in_progress]

    def get_in_progress_courses(self):
        return [c for c in self.courses if c.is_in_progress]


# -- Regex patterns ------------------------------------------------------------

SEMESTER_RE = re.compile(
    r"^(Fall|Spring|Summer|Winter|Intersession)\s+(20\d{2})",
    re.IGNORECASE,
)

TRANSFER_BLOCK_RE = re.compile(r"^TRANSFER COURSES", re.IGNORECASE)

RUTGERS_SCHOOL_RE = re.compile(
    r"(SCHOOL OF|RUTGERS BUSINESS|MASON GROSS|EDWARD J\. BLOUSTEIN|"
    r"ERNEST MARIO|SCHOOL OF COMMUNICATION|SCHOOL OF ENGINEERING|"
    r"SCHOOL OF ENVIRONMENTAL|SCHOOL OF MANAGEMENT)",
    re.IGNORECASE,
)

SKIP_PATTERNS = [
    re.compile(r"^SUB TOPIC:", re.IGNORECASE),
    re.compile(r"^TOTAL (CREDITS|TRANSFER)", re.IGNORECASE),
    re.compile(r"^DEGREE CREDITS EARNED", re.IGNORECASE),
    re.compile(r"^TERM AVG", re.IGNORECASE),
    re.compile(r"^\*{2,}"),
    re.compile(r"^UNOFFICIAL COPY"),
    re.compile(r"^RECORD (OF|DATE)"),
    re.compile(r"^STUDENT NUMBER"),
    re.compile(r"^TITLE\s+SCH"),
    re.compile(r"^MAJOR:"),
    re.compile(r"^MINOR:"),
    re.compile(r"^CLASS:"),
    re.compile(r"^PAGE:"),
    re.compile(r"^LAST TERM"),
    re.compile(r"^INCREMENTED"),
    re.compile(r"^\.$"),
]

COURSE_LINE_RE = re.compile(
    r"""
    ^
    \s{0,4}
    (?P<title>[A-Z][A-Z0-9 &'/\-,\.]+?)
    \s+
    (?P<sch>\d{2})
    \s+
    (?P<dept>\d{3})
    \s+
    (?P<crs>\d{3}[A-Z]?)
    \s+
    (?P<sec>[A-Z0-9]{1,3})
    \s+
    (?P<cred>\d{1,2}\.\d)
    (?:
      \s+(?P<pr>[A-Z]{1,2})?
      \s*(?P<grade>[A-Z][A-Z+\-]*)?
    )?
    \s*$
    """,
    re.VERBOSE,
)

# Transfer courses have no section column
TRANSFER_ONLY_RE = re.compile(
    r"""
    ^\s{0,4}
    (?P<title>[A-Z][A-Z0-9 &'/\-,\.]+?)
    \s+
    (?P<sch>\d{2})
    \s+
    (?P<dept>\d{3})
    \s+
    (?P<crs>\d{3}[A-Z]?)
    \s+
    (?P<cred>\d{1,2}\.\d)
    \s*$
    """,
    re.VERBOSE,
)

STUDENT_NAME_RE = re.compile(r"RECORD OF:\s+(.+)", re.IGNORECASE)
STUDENT_ID_RE   = re.compile(r"STUDENT NUMBER:\s+(\d+)", re.IGNORECASE)


# -- Core parser ---------------------------------------------------------------

def parse_transcript_text(raw_text: str) -> TranscriptParseResult:
    result = TranscriptParseResult()
    lines = raw_text.split("\n")
    _parse_lines(lines, result)
    return result


def _parse_lines(lines: list, result: TranscriptParseResult):
    current_semester = ""
    in_transfer_block = False

    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()

        if not result.student_name:
            m = STUDENT_NAME_RE.search(line)
            if m:
                result.student_name = m.group(1).strip()

        if not result.student_id:
            m = STUDENT_ID_RE.search(line)
            if m:
                result.student_id = m.group(1).strip()

        if not stripped:
            continue
        if any(p.search(stripped) for p in SKIP_PATTERNS):
            m = re.search(r"TOTAL TRANSFER CREDITS:\s*([\d.]+)", stripped)
            if m:
                result.total_transfer_credits = float(m.group(1))
            continue

        if TRANSFER_BLOCK_RE.match(stripped):
            in_transfer_block = True
            continue

        sem_match = SEMESTER_RE.match(stripped)
        if sem_match:
            season = sem_match.group(1).capitalize()
            year   = sem_match.group(2)
            current_semester = f"{season} {year}"
            if current_semester not in result.semesters:
                result.semesters.append(current_semester)
            if RUTGERS_SCHOOL_RE.search(line):
                in_transfer_block = False
            continue

        # Skip institution name lines in transfer block (all caps, no course pattern)
        if in_transfer_block and re.match(r"^[A-Z\s&\-'\.]+$", stripped):
            if not COURSE_LINE_RE.match(line):
                continue

        course = _try_parse_course_line(line, current_semester, in_transfer_block)
        if course:
            result.courses.append(course)
        else:
            if re.search(r"\d{3}\s+\d{3}\s+\d+\.\d", line):
                result.warnings.append(
                    f"Unmatched course-like line in {current_semester}: {line.strip()!r}"
                )


def _try_parse_course_line(
    line: str,
    semester: str,
    is_transfer: bool,
) -> Optional[ParsedCourse]:
    m = COURSE_LINE_RE.match(line)
    sec = None

    if not m and is_transfer:
        m = TRANSFER_ONLY_RE.match(line)
        if m:
            sec = ""

    if not m:
        return None

    title_raw = m.group("title").strip()
    sch       = m.group("sch")
    dept      = m.group("dept")
    crs       = m.group("crs")
    section   = sec if sec is not None else (m.group("sec") if "sec" in m.groupdict() else "")
    credits   = float(m.group("cred"))
    pr_flag   = ((m.group("pr") if "pr" in m.groupdict() else None) or "").strip().upper()
    grade     = ((m.group("grade") if "grade" in m.groupdict() else None) or "").strip().upper()

    # Regex may put grade in pr_flag slot when there's no actual PR flag
    if pr_flag and not grade:
        if re.match(r"^[ABCDFWPNUTS][A+\-]?$", pr_flag) or pr_flag in ("PA", "NC", "TR"):
            grade   = pr_flag
            pr_flag = ""

    is_in_progress = (grade == "")
    is_retake      = pr_flag in ("E", "R")
    passed         = _grade_is_passing(grade, pr_flag)

    return ParsedCourse(
        title_raw       = title_raw,
        sch             = sch,
        dept            = dept,
        crs             = crs,
        section         = section,
        credits         = credits,
        pr_flag         = pr_flag,
        grade           = grade,
        course_code     = f"{sch}:{dept}:{crs}",
        normalized_code = f"{dept}:{crs}",
        semester        = semester,
        is_transfer     = is_transfer,
        is_in_progress  = is_in_progress,
        passed          = passed,
        is_retake       = is_retake,
    )
