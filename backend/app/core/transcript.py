"""Deterministic validation for untrusted transcript extraction output."""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping

from ..schemas import CourseDetail


PASSING_GRADES = {
    "A", "A+", "A-", "B", "B+", "B-", "C", "C+", "C-", "D", "D+", "D-",
    "P", "PA", "S", "TR", "TE", "TC", "T", "EX", "HP", "LP",
}
FAILING_GRADES = {"F", "WF", "U", "UF", "NC"}
NON_COMPLETION_GRADES = {"W", "WD", "WN", "NR", "AB", "NG", "AU"}
_RAW_CODE_RE = re.compile(r"^(\d{2}):(\d{3}):(\d{3,4})$")
_TERM_RE = re.compile(r"^(Spring|Summer|Fall|Winter)\s+(\d{4})$", re.IGNORECASE)
_TERM_HEADER_RE = re.compile(r"^(Spring|Summer|Fall|Winter)\s+(\d{4})\b", re.IGNORECASE)
_TERM_ORDER = {"Spring": 0, "Summer": 1, "Fall": 2, "Winter": 3}
_ROW_RE = re.compile(
    r"^\s*(?P<raw>\d{2}\s*:\s*\d{3}\s*:\s*\d{3,4})\s+"
    r"(?P<title>.*?)\s+(?P<credits>\d+(?:\.\d+)?)"
    r"(?:\s+(?P<grade>[A-Za-z][A-Za-z+\-]*))?\s*$"
)
_TRANSFER_EQUIV_RE = re.compile(
    r"^\s*(?P<title>.*?)\s+(?P<credits>\d+(?:\.\d+)?)\s+"
    r"(?P<grade>[A-Za-z][A-Za-z+\-]*)\s+Equivalent:\s*"
    r"(?P<raw>\d{2}\s*:\s*\d{3}\s*:\s*\d{3,4})\s*$",
    re.IGNORECASE,
)
_TRANSFER_ROW_RE = re.compile(
    r"^\s*(?P<title>.*?)\s+(?P<credits>\d+(?:\.\d+)?)\s+"
    r"(?P<grade>TR|TE|TC|T|EX)\s*$",
    re.IGNORECASE,
)
_COLUMN_ROW_RE = re.compile(
    r"^\s*(?P<title>.*?)\s+(?P<school>\d{2})\s+(?P<dept>\d{3})\s+"
    r"(?P<course>\d{3,4})\s+(?P<tail>.*?)\s*$"
)
_TRANSFER_COLUMN_RE = re.compile(
    r"^\s*(?P<title>.*?)\s+TR\s+T\d{2}\s+[A-Z]+\s+(?P<credits>\d+\.\d+)\s*$",
    re.IGNORECASE,
)


def normalize_raw_code(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    compact = re.sub(r"\s+", "", value)
    match = _RAW_CODE_RE.fullmatch(compact)
    return compact if match else None


def extract_deterministic_rows(text: str) -> list[dict[str, Any]]:
    """Extract conventional text-PDF Rutgers rows without an AI dependency."""
    semester = ""
    is_transfer = False
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        stripped = line.strip()
        term = _TERM_HEADER_RE.match(stripped)
        if term:
            semester = f"{term.group(1).capitalize()} {term.group(2)}"
            if "SCHOOL OF" in stripped.upper():
                is_transfer = False
            continue
        if re.search(r"\bTRANSFER\s+(?:CREDIT|WORK|COURSES?)\b", stripped, re.IGNORECASE):
            semester = "Transfer"
            is_transfer = True
            continue
        match = (
            _ROW_RE.fullmatch(line)
            or _TRANSFER_EQUIV_RE.fullmatch(line)
            or (_TRANSFER_ROW_RE.fullmatch(line) if is_transfer else None)
        )
        if match:
            grade = match.group("grade") or ""
            rows.append({
                "title_raw": match.group("title").strip(),
                "raw_code": normalize_raw_code(match.groupdict().get("raw")),
                "grade": grade or ("TR" if is_transfer else ""),
                "semester": semester,
                "credits": float(match.group("credits")),
                "is_transfer": is_transfer,
            })
            continue

        transfer_match = _TRANSFER_COLUMN_RE.fullmatch(line) if is_transfer else None
        if transfer_match:
            rows.append({
                "title_raw": transfer_match.group("title").strip(),
                "raw_code": None,
                "grade": "TR",
                "semester": semester,
                "credits": float(transfer_match.group("credits")),
                "is_transfer": True,
            })
            continue

        # Official Rutgers PDFs commonly print the three code columns without
        # colons, followed by optional section/repeat/grade columns.
        column_match = _COLUMN_ROW_RE.fullmatch(line)
        if not column_match:
            continue
        tail_tokens = column_match.group("tail").split()
        credit_index = next(
            (index for index, token in enumerate(tail_tokens) if re.fullmatch(r"\d+\.\d+", token)),
            None,
        )
        if credit_index is None:
            continue
        after_credits = [token.upper() for token in tail_tokens[credit_index + 1:]]
        valid_grades = PASSING_GRADES | FAILING_GRADES | NON_COMPLETION_GRADES
        grade = next((token for token in reversed(after_credits) if token in valid_grades), "")
        rows.append({
            "title_raw": column_match.group("title").strip(),
            "raw_code": f"{column_match.group('school')}:{column_match.group('dept')}:{column_match.group('course')}",
            "grade": grade or ("TR" if is_transfer else ""),
            "semester": semester,
            "credits": float(tail_tokens[credit_index]),
            "is_transfer": is_transfer,
        })
    return rows


def merge_extracted_rows(
    deterministic_rows: Iterable[Any], ai_rows: Iterable[Any]
) -> list[dict[str, Any]]:
    """Merge high-precision local rows with higher-recall AI rows.

    Printed raw-code/term pairs identify attempts. Local values win, except an
    AI grade may fill a blank caused by PDF column extraction. AI-only attempts
    are retained and are still catalog/status validated by the caller.
    """
    merged: list[dict[str, Any]] = []
    positions: dict[tuple[str, str], int] = {}

    def row_key(row: dict[str, Any]) -> tuple[str, str]:
        raw = normalize_raw_code(row.get("raw_code"))
        semester = str(row.get("semester") or "").strip().lower()
        if raw:
            return raw, semester
        title = re.sub(r"\W+", "", str(row.get("title_raw") or "").lower())
        return f"title:{title}", semester

    for row in deterministic_rows:
        if not isinstance(row, dict):
            continue
        positions[row_key(row)] = len(merged)
        merged.append(dict(row))

    for row in ai_rows:
        if not isinstance(row, dict):
            continue
        key = row_key(row)
        existing_position = positions.get(key)
        if existing_position is None:
            positions[key] = len(merged)
            merged.append(dict(row))
            continue
        existing = merged[existing_position]
        for field in ("grade", "title_raw", "credits", "semester", "equivalency_note"):
            if existing.get(field) in (None, "", 0, 0.0) and row.get(field) not in (None, ""):
                existing[field] = row[field]
    return merged


def classify_grade(value: Any) -> tuple[str, bool, bool, bool]:
    grade = str(value or "").strip().upper()
    if not grade:
        return grade, False, False, True
    if grade in PASSING_GRADES:
        return grade, True, False, False
    if grade in FAILING_GRADES:
        return grade, False, True, False
    # Unknown and administrative grades are never assumed to be completed.
    return grade, False, False, False


def _credits(value: Any) -> float:
    try:
        credits = float(value)
    except (TypeError, ValueError):
        return 0.0
    return credits if 0 <= credits <= 25 else 0.0


def normalize_extracted_courses(
    rows: Iterable[Any],
    raw_code_map: Mapping[str, str],
    known_codes: set[str],
) -> list[CourseDetail]:
    """Convert AI-extracted rows into catalog-verified, invariant-safe records.

    A short code is accepted only when it is backed by a recognized raw Rutgers
    code or exists in the local catalog. Transfer-title guesses are deliberately
    left unmatched; official equivalency data must supply those mappings.
    """
    result: list[CourseDetail] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        raw_code = normalize_raw_code(row.get("raw_code"))
        is_transfer = bool(row.get("is_transfer", False))
        model_code = str(row.get("rutgers_code") or "").strip().upper() or None
        resolved_code = raw_code_map.get(raw_code) if raw_code else None

        if resolved_code:
            rutgers_code = resolved_code
        elif raw_code:
            # The transcript printed a code, but our catalog cannot verify it.
            rutgers_code = None
        elif not is_transfer and model_code in known_codes:
            rutgers_code = model_code
        else:
            rutgers_code = None

        grade, passed, failed, in_progress = classify_grade(row.get("grade"))
        result.append(CourseDetail(
            title_raw=str(row.get("title_raw") or "").strip()[:300],
            raw_code=raw_code,
            rutgers_code=rutgers_code,
            grade=grade,
            passed=passed,
            failed=failed,
            is_transfer=is_transfer,
            is_in_progress=in_progress,
            semester=str(row.get("semester") or "").strip()[:40],
            credits=_credits(row.get("credits")),
            equivalency_note=(
                str(row.get("equivalency_note") or "").strip()[:500]
                if is_transfer else ""
            ),
        ))
    return result


def latest_status_codes(
    courses: list[CourseDetail], *, canonical: bool = False
) -> tuple[list[str], list[str]]:
    """Return completed/in-progress codes using the latest attempt per course."""
    def term_key(course: CourseDetail, position: int) -> tuple[int, int, int]:
        match = _TERM_RE.fullmatch(course.semester)
        if not match:
            return (-1, -1, position)
        season = match.group(1).capitalize()
        return (int(match.group(2)), _TERM_ORDER[season], position)

    attempts: dict[str, list[tuple[tuple[int, int, int], CourseDetail]]] = {}
    for position, course in enumerate(courses):
        identity = course.raw_code if canonical else course.rutgers_code
        if not identity:
            continue
        key = term_key(course, position)
        attempts.setdefault(identity, []).append((key, course))

    # A later W/failure/in-progress registration does not erase credit already
    # earned by a passing attempt. Only courses with no passing attempt can be
    # classified as currently in progress.
    completed = [
        code for code, course_attempts in attempts.items()
        if any(course.passed for _, course in course_attempts)
    ]
    in_progress = [
        code for code, course_attempts in attempts.items()
        if not any(course.passed for _, course in course_attempts)
        and max(course_attempts, key=lambda item: item[0])[1].is_in_progress
    ]
    return completed, in_progress
