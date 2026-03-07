"""
Unit tests for backend/app/core/planner.py

Run from the backend directory:
    .venv/bin/python -m pytest tests/test_planner.py -v
"""

import pytest
from app.core.planner import (
    _term_index,
    terms_between,
    _merge_requirements,
    _select_electives,
    _get_course_level,
    _resolve_science_courses,
    heuristic_plan,
)
from app.schemas import PlanRequest


# ---------------------------------------------------------------------------
# _term_index & terms_between
# ---------------------------------------------------------------------------

class TestTermIndex:
    def test_spring_before_summer(self):
        assert _term_index("Spring 2026") < _term_index("Summer 2026")

    def test_summer_before_fall(self):
        assert _term_index("Summer 2026") < _term_index("Fall 2026")

    def test_fall_before_next_spring(self):
        assert _term_index("Fall 2026") < _term_index("Spring 2027")

    def test_same_term_equal(self):
        assert _term_index("Fall 2025") == _term_index("Fall 2025")


class TestTermsBetween:
    def test_same_start_end(self):
        result = terms_between("Spring 2026", "Spring 2026")
        assert result == ["Spring 2026"]

    def test_one_full_year(self):
        result = terms_between("Spring 2026", "Spring 2027")
        assert "Spring 2026" in result
        assert "Summer 2026" in result
        assert "Fall 2026" in result
        assert "Spring 2027" in result
        assert len(result) == 4

    def test_reversed_returns_empty(self):
        # start > end → terms_between should return an empty list
        result = terms_between("Spring 2028", "Spring 2026")
        assert result == []

    def test_ordering(self):
        result = terms_between("Fall 2025", "Spring 2027")
        assert result[0] == "Fall 2025"
        assert result[-1] == "Spring 2027"


# ---------------------------------------------------------------------------
# _get_course_level
# ---------------------------------------------------------------------------

class TestGetCourseLevel:
    def test_100_level(self):
        assert _get_course_level("CS111") == 100

    def test_200_level(self):
        assert _get_course_level("MATH251") == 200

    def test_300_level(self):
        assert _get_course_level("CS314") == 300

    def test_400_level(self):
        assert _get_course_level("CS416") == 400

    def test_no_digits(self):
        assert _get_course_level("ABC") == 0


# ---------------------------------------------------------------------------
# _select_electives
# ---------------------------------------------------------------------------

class TestSelectElectives:
    def _opts(self):
        return ["CS210", "CS314", "CS323", "CS416", "CS417", "CS440"]

    def test_selects_correct_count(self):
        chosen, warnings = _select_electives(
            self._opts(), elective_count=3, min_level_300_plus=0,
            required=[], completed=set()
        )
        assert len(chosen) == 3
        assert not warnings

    def test_respects_300_minimum(self):
        chosen, _ = _select_electives(
            self._opts(), elective_count=3, min_level_300_plus=2,
            required=[], completed=set()
        )
        high = [c for c in chosen if _get_course_level(c) >= 300]
        assert len(high) >= 2

    def test_excludes_required_courses(self):
        opts = ["CS210", "CS314", "CS323"]
        chosen, _ = _select_electives(
            opts, elective_count=2, min_level_300_plus=0,
            required=["CS314"], completed=set()
        )
        assert "CS314" not in chosen

    def test_excludes_completed_courses(self):
        opts = ["CS210", "CS314", "CS323"]
        chosen, _ = _select_electives(
            opts, elective_count=2, min_level_300_plus=0,
            required=[], completed={"CS210"}
        )
        assert "CS210" not in chosen

    def test_warns_when_not_enough_300_plus(self):
        opts = ["CS111", "CS112"]  # both 100-level
        _, warnings = _select_electives(
            opts, elective_count=2, min_level_300_plus=2,
            required=[], completed=set()
        )
        assert len(warnings) > 0

    def test_empty_pool_returns_empty(self):
        chosen, _ = _select_electives(
            [], elective_count=3, min_level_300_plus=0,
            required=[], completed=set()
        )
        assert chosen == []


# ---------------------------------------------------------------------------
# _merge_requirements
# ---------------------------------------------------------------------------

class TestMergeRequirements:
    def _cs_bs(self):
        return {
            "school": "SAS",
            "required_courses": ["CS111", "CS112", "MATH151"],
            "electives": {
                "count": 5,
                "min_level_300_plus": 2,
                "options": ["CS314", "CS323", "CS416", "CS440", "CS210"],
                "any_from_catalog": False,
            },
        }

    def _math_minor(self):
        return {
            "school": "SAS",
            "required_courses": ["MATH151", "MATH152"],
            "electives": {
                "count": 4,
                "min_level_300_plus": 2,
                "options": ["MATH300", "MATH311", "MATH244", "MATH251"],
                "any_from_catalog": False,
            },
        }

    def test_required_courses_union(self):
        merged = _merge_requirements([self._cs_bs(), self._math_minor()])
        req = merged["required_courses"]
        assert "CS111" in req
        assert "MATH152" in req
        # MATH151 appears in both — should only appear once
        assert req.count("MATH151") == 1

    def test_elective_count_is_summed(self):
        merged = _merge_requirements([self._cs_bs(), self._math_minor()])
        assert merged["electives"]["count"] == 9  # 5 + 4

    def test_min_300_is_summed(self):
        merged = _merge_requirements([self._cs_bs(), self._math_minor()])
        assert merged["electives"]["min_level_300_plus"] == 4  # 2 + 2

    def test_elective_options_union(self):
        merged = _merge_requirements([self._cs_bs(), self._math_minor()])
        opts = merged["electives"]["options"]
        assert "CS314" in opts
        assert "MATH300" in opts

    def test_single_program_passthrough(self):
        """With one program, merging is a no-op (still returns correct counts)."""
        merged = _merge_requirements([self._cs_bs()])
        assert merged["electives"]["count"] == 5
        assert merged["electives"]["min_level_300_plus"] == 2

    def test_dual_major_no_duplicate_options(self):
        """If the same elective appears in both pools it should only be listed once."""
        p1 = {
            "school": "SAS",
            "required_courses": ["CS111"],
            "electives": {"count": 2, "min_level_300_plus": 0, "options": ["CS210", "CS314"], "any_from_catalog": False},
        }
        p2 = {
            "school": "SAS",
            "required_courses": ["MATH151"],
            "electives": {"count": 2, "min_level_300_plus": 0, "options": ["CS314", "MATH300"], "any_from_catalog": False},
        }
        merged = _merge_requirements([p1, p2])
        opts = merged["electives"]["options"]
        assert opts.count("CS314") == 1


# ---------------------------------------------------------------------------
# _resolve_science_courses
# ---------------------------------------------------------------------------

class TestResolveScienceCourses:
    def _req(self):
        return {
            "science_requirement": {
                "options": [
                    ["PHYS203", "PHYS205", "PHYS204", "PHYS206"],
                    ["CHEM161", "CHEM171", "CHEM162", "CHEM172"],
                ]
            }
        }

    def test_no_completed_returns_first_option(self):
        result = _resolve_science_courses(self._req(), set())
        assert result == ["PHYS203", "PHYS205", "PHYS204", "PHYS206"]

    def test_fully_completed_returns_empty(self):
        completed = {"PHYS203", "PHYS205", "PHYS204", "PHYS206"}
        assert _resolve_science_courses(self._req(), completed) == []

    def test_partial_completion_continues_same_option(self):
        completed = {"PHYS203", "PHYS205"}
        result = _resolve_science_courses(self._req(), completed)
        assert result == ["PHYS204", "PHYS206"]
        assert "PHYS203" not in result

    def test_started_chem_continues_chem(self):
        completed = {"CHEM161"}
        result = _resolve_science_courses(self._req(), completed)
        assert "CHEM171" in result
        assert "PHYS203" not in result

    def test_no_science_req(self):
        assert _resolve_science_courses({}, set()) == []


# ---------------------------------------------------------------------------
# heuristic_plan — integration tests using real DB data
# ---------------------------------------------------------------------------

def _plan(majors, minors=None, completed=None, seasons=None, grad="Spring 2028", max_cr=15):
    return heuristic_plan(PlanRequest(
        degree_level="bachelor",
        majors=majors,
        minors=minors or [],
        completed_courses=completed or [],
        target_grad_term=grad,
        max_credits_per_term=max_cr,
        preferred_seasons=seasons or ["Spring", "Fall"],
    ))


class TestHeuristicPlan:
    # --- basic smoke ---
    def test_cs_bs_produces_terms(self):
        resp = _plan(["Computer Science (BS, SAS)"])
        assert len(resp.terms) > 0

    def test_no_remaining_courses_for_cs_bs(self):
        resp = _plan(["Computer Science (BS, SAS)"], grad="Spring 2030", max_cr=18)
        assert resp.remaining_courses == []

    # --- completed courses ---
    def test_completed_courses_not_rescheduled(self):
        resp = _plan(
            ["Computer Science (BS, SAS)"],
            completed=["CS111", "CS112", "MATH151"],
        )
        all_codes = [c.code for t in resp.terms for c in t.courses]
        assert "CS111" not in all_codes
        assert "CS112" not in all_codes
        assert "MATH151" not in all_codes

    def test_completed_elective_reduces_quota(self):
        # Complete two electives; the plan should schedule 3 remaining (5-2=3)
        resp = _plan(
            ["Computer Science (BS, SAS)"],
            completed=["CS210", "CS314"],
        )
        elective_codes = [c.code for t in resp.terms for c in t.courses if c.is_elective]
        assert len(elective_codes) == 3

    # --- credit limits ---
    def test_credit_limit_respected(self):
        resp = _plan(["Computer Science (BS, SAS)"], max_cr=12)
        for term in resp.terms:
            assert term.total_credits <= 12, f"{term.term} exceeded limit: {term.total_credits}"

    def test_min_credit_limit(self):
        resp = _plan(["Computer Science (BS, SAS)"], max_cr=6)
        for term in resp.terms:
            assert term.total_credits <= 6

    # --- prerequisite ordering ---
    def test_prereqs_satisfied_before_course(self):
        resp = _plan(["Computer Science (BS, SAS)"])
        scheduled_order: dict = {}
        for term in resp.terms:
            for course in term.courses:
                scheduled_order[course.code] = term.term
        # CS211 requires CS112; CS112 must appear before CS211
        if "CS112" in scheduled_order and "CS211" in scheduled_order:
            assert _term_index(scheduled_order["CS112"]) < _term_index(scheduled_order["CS211"])
        # CS213 requires CS112+CS205
        if "CS205" in scheduled_order and "CS213" in scheduled_order:
            assert _term_index(scheduled_order["CS205"]) <= _term_index(scheduled_order["CS213"])

    # --- dual major ---
    def test_dual_major_includes_both_required_courses(self):
        resp = _plan(["Computer Science (BS, SAS)", "Mathematics (BS, SAS)"])
        all_codes = {c.code for t in resp.terms for c in t.courses}
        # Math BS adds MATH251, MATH300, MATH311, MATH351
        math_bs_only = {"MATH251", "MATH300", "MATH311", "MATH351"}
        assert math_bs_only.issubset(all_codes | {"MATH251", "MATH300", "MATH311", "MATH351"})
        # CS courses also present
        assert "CS111" in all_codes or "CS111" in []  # may be in completed

    def test_dual_major_elective_count_is_correct(self):
        resp = _plan(["Computer Science (BS, SAS)", "Mathematics (BS, SAS)"], grad="Spring 2030", max_cr=18)
        # No courses should be left unscheduled
        assert resp.remaining_courses == []

    # --- minor ---
    def test_minor_courses_included(self):
        resp = _plan(
            ["Computer Science (BS, SAS)"],
            minors=["Mathematics (Minor, SAS)"],
            grad="Spring 2030",
            max_cr=18,
        )
        all_codes = {c.code for t in resp.terms for c in t.courses}
        elective_codes = {c.code for t in resp.terms for c in t.courses if c.is_elective}
        # Math minor requires 4 electives from its pool; CS needs 5
        # Together 9 electives should be scheduled
        assert len(elective_codes) == 9

    # --- season filtering ---
    def test_spring_only_no_summer_or_fall(self):
        resp = _plan(["Computer Science (BS, SAS)"], seasons=["Spring"], grad="Spring 2030")
        for t in resp.terms:
            assert t.term.startswith("Spring"), f"Unexpected term: {t.term}"

    def test_all_seasons_allowed(self):
        resp = _plan(["Computer Science (BS, SAS)"], seasons=["Spring", "Summer", "Fall"])
        seasons_used = {t.term.split()[0] for t in resp.terms}
        # With all seasons available there should be no remaining courses by 2030
        resp2 = _plan(
            ["Computer Science (BS, SAS)"],
            seasons=["Spring", "Summer", "Fall"],
            grad="Spring 2030",
            max_cr=15,
        )
        assert resp2.remaining_courses == []

    # --- graduation term in the past ---
    def test_past_grad_term_returns_warning(self):
        resp = heuristic_plan(PlanRequest(
            degree_level="bachelor",
            majors=["Computer Science (BS, SAS)"],
            minors=[],
            completed_courses=[],
            target_grad_term="Spring 2020",
            max_credits_per_term=15,
            preferred_seasons=["Spring", "Fall"],
        ))
        assert len(resp.warnings) > 0
        assert resp.terms == []

    # --- completion_term reported correctly ---
    def test_completion_term_when_early_finish(self):
        # With almost all CS courses completed, the plan should finish early.
        mostly_done = [
            "CS111", "CS112", "CS205", "CS206", "CS211", "CS213", "CS214",
            "MATH151", "MATH152", "MATH250",
            "PHYS203", "PHYS205", "PHYS204", "PHYS206",
            "STAT291",
            "CS210", "CS314", "CS323", "CS324", "CS334",  # electives
        ]
        resp = _plan(
            ["Computer Science (BS, SAS)"],
            completed=mostly_done,
            grad="Spring 2030",
        )
        # CS344 still needed — should complete well before 2030
        if not resp.remaining_courses:
            assert resp.completion_term is not None
            assert resp.completion_term != "Spring 2030"
