"""Typed, explainable course eligibility rules.

Rules are JSON-compatible so catalog ingestion can persist them without embedding
policy in planner code. Legacy prerequisite lists are adapted to ``allOf`` rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


_GRADE_POINTS = {
    "F": 0, "D": 1, "D+": 2, "C-": 3, "C": 4, "C+": 5,
    "B-": 6, "B": 7, "B+": 8, "A-": 9, "A": 10, "A+": 11,
    "P": 4, "PA": 4, "S": 4, "TR": 4, "TE": 4, "TC": 4,
}


@dataclass(frozen=True)
class StudentRecord:
    """Store the academic facts used to evaluate enrollment eligibility.

    Keeping these facts immutable makes each rule evaluation reproducible and
    prevents one course check from changing the inputs used by another.
    """
    completed: frozenset[str]
    grades: Mapping[str, str] = field(default_factory=dict)
    in_progress: frozenset[str] = frozenset()
    programs: frozenset[str] = frozenset()
    earned_credits: float = 0.0
    class_year: int | None = None


@dataclass(frozen=True)
class EligibilityResult:
    """Describe whether a student may take a course and why.

    ``unknown`` distinguishes a verified failure from one caused by missing or
    unsupported data so callers can explain uncertainty to the student.
    """
    allowed: bool
    reasons: tuple[str, ...] = ()
    unknown: bool = False


def _course_rule(rule: Mapping[str, Any], record: StudentRecord) -> EligibilityResult:
    """Evaluate one course prerequisite, including concurrency and grade rules.

    Args:
        rule: Course rule containing a code and optional grade/concurrency data.
        record: Student facts against which the prerequisite is checked.

    Returns:
        An eligibility result with a user-facing reason when the rule fails.
    """
    code = str(rule.get("course", "")).upper()
    concurrent = bool(rule.get("concurrent", False))
    present = code in record.completed or (concurrent and code in record.in_progress)
    if not present:
        return EligibilityResult(False, (f"requires {code}",))
    minimum = str(rule.get("minGrade", "")).upper()
    if minimum and code in record.grades:
        actual = record.grades[code].upper()
        if actual not in _GRADE_POINTS or minimum not in _GRADE_POINTS:
            return EligibilityResult(False, (f"grade requirement for {code} could not be verified",), True)
        if _GRADE_POINTS[actual] < _GRADE_POINTS[minimum]:
            return EligibilityResult(False, (f"requires {minimum} or better in {code}",))
    elif minimum:
        return EligibilityResult(False, (f"grade for {code} is unknown",), True)
    return EligibilityResult(True)


def evaluate_rule(rule: Any, record: StudentRecord) -> EligibilityResult:
    """Recursively evaluate a JSON-compatible eligibility rule.

    This central evaluator supports composite and non-course restrictions so
    planner code does not need to duplicate enrollment policy.

    Args:
        rule: A course, list, or mapping representing an eligibility rule.
        record: Student facts used to resolve the rule.

    Returns:
        The combined eligibility decision, reasons, and uncertainty status.
    """
    if not rule:
        return EligibilityResult(True)
    if isinstance(rule, str):
        return _course_rule({"course": rule}, record)
    if isinstance(rule, list):
        rule = {"allOf": rule}
    if not isinstance(rule, Mapping):
        return EligibilityResult(False, ("invalid eligibility rule",), True)

    if "course" in rule:
        return _course_rule(rule, record)
    if "allOf" in rule:
        results = [evaluate_rule(item, record) for item in rule["allOf"]]
        failures = [reason for result in results if not result.allowed for reason in result.reasons]
        return EligibilityResult(not failures, tuple(failures), any(r.unknown for r in results))
    if "anyOf" in rule:
        results = [evaluate_rule(item, record) for item in rule["anyOf"]]
        if any(result.allowed for result in results):
            return EligibilityResult(True)
        reasons = tuple(reason for result in results for reason in result.reasons)
        return EligibilityResult(False, reasons, any(r.unknown for r in results))
    if "minCredits" in rule:
        needed = float(rule["minCredits"])
        return EligibilityResult(
            record.earned_credits >= needed,
            () if record.earned_credits >= needed else (f"requires {needed:g} earned credits",),
        )
    if "programIn" in rule:
        allowed = set(rule["programIn"])
        match = bool(allowed.intersection(record.programs))
        return EligibilityResult(match, () if match else ("restricted to an eligible program",))
    if "classYearAtLeast" in rule:
        if record.class_year is None:
            return EligibilityResult(False, ("class year is unknown",), True)
        needed = int(rule["classYearAtLeast"])
        return EligibilityResult(record.class_year >= needed, () if record.class_year >= needed else (f"requires class year {needed}+",))
    return EligibilityResult(False, ("unsupported eligibility rule",), True)


def rule_for_course(course: Mapping[str, Any]) -> Any:
    """Return the best available eligibility rule for a catalog course.

    Args:
        course: Catalog entry containing modern or legacy prerequisite fields.

    Returns:
        The explicit eligibility rule, prerequisite rule, or a legacy adapter.
    """
    return course.get("eligibility_rule") or course.get("prerequisite_rule") or {
        "allOf": course.get("prerequisites", [])
    }
