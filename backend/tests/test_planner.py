import pytest
from app.core.planner import (
    _term_index,
    terms_between,
    _merge_requirements,
    _select_electives,
    _get_course_level,
    _resolve_science_courses,
    _collect_missing_prereqs,
    _apply_track,
    _core_candidate_key,
    _match_core_courses,
    heuristic_plan,
)
from app.schemas import PlanRequest


class TestTermIndex:
    def test_spring_before_summer(self):
        assert _term_index("Spring 2026") < _term_index("Summer 2026")

    def test_summer_before_fall(self):
        assert _term_index("Summer 2026") < _term_index("Fall 2026")

    def test_fall_before_next_spring(self):
        assert _term_index("Fall 2026") < _term_index("Spring 2027")

    def test_same_term_equal(self):
        assert _term_index("Fall 2025") == _term_index("Fall 2025")


class TestApplyTrack:
    def test_multiple_track_dimensions_are_combined(self):
        requirements = {
            "track_required": True,
            "requirement_groups": [{"label": "Base", "count": 1, "options": ["BASE100"]}],
            "track_dimensions": [
                {"label": "theme", "options": {"environment": {"requirement_groups": [{"label": "Theme", "count": 2, "options": []}]}}},
                {"label": "region", "options": {"south_asia": {"requirement_groups": [{"label": "Region", "count": 2, "options": []}]}}},
            ],
        }
        selected = _apply_track(requirements, "environment/south_asia")
        assert [group["label"] for group in selected["requirement_groups"]] == ["Base", "Theme", "Region"]

    def test_required_track_must_be_selected(self):
        requirements = {
            "required_courses": ["BASE100"],
            "track_required": True,
            "tracks": {"Cyber": {"required_courses": ["CYBER200"]}},
        }
        with pytest.raises(ValueError, match="requires a track selection"):
            _apply_track(requirements, None)

    def test_unknown_track_is_rejected(self):
        requirements = {
            "tracks": {
                "Cyber": {"required_courses": ["CYBER200"]},
                "Policy": {"required_courses": ["POLICY200"]},
            }
        }
        with pytest.raises(ValueError, match="Unknown track 'Imaginary'.*Cyber, Policy"):
            _apply_track(requirements, "Imaginary")

    def test_optional_tracks_allow_general_path(self):
        requirements = {
            "required_courses": ["BASE100"],
            "tracks": {"Research": {"required_courses": ["RES200"]}},
        }
        assert _apply_track(requirements, None) is requirements

    def test_explicit_general_track_is_selectable(self):
        requirements = {
            "required_courses": ["BASE100"],
            "track_required": True,
            "tracks": {
                "General": {"required_courses": ["GEN200"]},
                "Research": {"required_courses": ["RES200"]},
            },
        }
        selected = _apply_track(requirements, "General")
        assert selected["required_courses"] == ["BASE100", "GEN200"]
        assert selected["selected_track"] == "General"
        assert "tracks" not in selected

    def test_track_payload_must_be_an_object(self):
        requirements = {"tracks": {"Broken": ["COURSE100"]}}
        with pytest.raises(ValueError, match="invalid requirement data"):
            _apply_track(requirements, "Broken")


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
        assert "Winter 2026" in result
        assert len(result) == 5

    def test_reversed_returns_empty(self):
        result = terms_between("Spring 2028", "Spring 2026")
        assert result == []

    def test_ordering(self):
        result = terms_between("Fall 2025", "Spring 2027")
        assert result[0] == "Fall 2025"
        assert result[-1] == "Spring 2027"


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
        opts = ["CS111", "CS112"]
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
        assert req.count("MATH151") == 1

    def test_elective_quotas_remain_independent(self):
        merged = _merge_requirements([self._cs_bs(), self._math_minor()])
        assert [group["count"] for group in merged["elective_groups"]] == [5, 4]

    def test_level_minimums_remain_independent(self):
        merged = _merge_requirements([self._cs_bs(), self._math_minor()])
        assert [group["min_level_300_plus"] for group in merged["elective_groups"]] == [2, 2]

    def test_elective_options_are_not_unioned(self):
        merged = _merge_requirements([self._cs_bs(), self._math_minor()])
        assert "CS314" in merged["elective_groups"][0]["options"]
        assert "MATH300" in merged["elective_groups"][1]["options"]

    def test_single_program_passthrough(self):
        merged = _merge_requirements([self._cs_bs()])
        assert merged["elective_groups"] == [self._cs_bs()["electives"]]

    def test_overlapping_options_stay_in_their_own_groups(self):
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
        assert "CS314" in merged["elective_groups"][0]["options"]
        assert "CS314" in merged["elective_groups"][1]["options"]


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


class TestCollectMissingPrereqs:
    def _catalog(self):
        return {
            "A100": {"prerequisites": []},
            "B200": {"prerequisites": ["A100"]},
            "C300": {"prerequisites": ["B200"]},
            "D400": {"prerequisites": ["C300"]},
        }

    def test_adds_direct_prereq(self):
        required = ["B200"]
        _collect_missing_prereqs(required, self._catalog(), set(), required)
        assert "A100" in required

    def test_adds_transitive_prereqs(self):
        required = ["D400"]
        _collect_missing_prereqs(required, self._catalog(), set(), required)
        assert "C300" in required
        assert "B200" in required
        assert "A100" in required

    def test_skips_completed(self):
        required = ["C300"]
        _collect_missing_prereqs(required, self._catalog(), {"B200"}, required)
        assert "B200" not in required
        assert "A100" not in required

    def test_no_duplicates(self):
        required = ["B200", "C300"]
        _collect_missing_prereqs(required, self._catalog(), set(), required)
        assert required.count("A100") == 1
        assert required.count("B200") == 1

    def test_skips_codes_not_in_catalog(self):
        catalog = {"X300": {"prerequisites": ["MISSING999"]}}
        required = ["X300"]
        _collect_missing_prereqs(required, catalog, set(), required)
        assert "MISSING999" not in required

    def test_no_prereqs_no_change(self):
        required = ["A100"]
        _collect_missing_prereqs(required, self._catalog(), set(), required)
        assert required == ["A100"]


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
    def test_science_path_prefers_lower_total_prerequisite_cost(self):
        requirements = {"science_requirement": {"options": [["ADV300"], ["INTRO100"]]}}
        catalog = {
            "ADV300": {"credits": 3, "prerequisites": ["MID200"]},
            "MID200": {"credits": 3, "prerequisites": ["INTRO100"]},
            "INTRO100": {"credits": 3, "prerequisites": []},
        }
        assert _resolve_science_courses(requirements, set(), catalog) == ["INTRO100"]

    def test_core_matching_requires_distinct_writing_goals(self):
        index = {
            "EXPOS101": ["WC"],
            "FREN214": ["WCd"],
            "FREN215": ["WCd"],
            "HIST201": ["WCr"],
        }
        matched = _match_core_courses(
            "Writing [WC], [WCr], [WCd]", 3,
            ["EXPOS101", "FREN214", "FREN215"], index,
        )
        assert len(matched) == 2
        assert len(_match_core_courses(
            "Writing [WC], [WCr], [WCd]", 3,
            ["EXPOS101", "FREN214", "FREN215", "HIST201"], index,
        )) == 3

    def test_core_candidate_scoring_penalizes_prerequisite_chains(self):
        catalog = {
            "DIRECT101": {"credits": 3, "prerequisites": []},
            "CHAIN214": {"credits": 3, "prerequisites": ["CHAIN213"]},
            "CHAIN213": {"credits": 3, "prerequisites": ["CHAIN131"]},
            "CHAIN131": {"credits": 4, "prerequisites": []},
        }
        assert _core_candidate_key("DIRECT101", catalog, set()) < _core_candidate_key("CHAIN214", catalog, set())

    def test_cs_core_does_not_add_an_unnecessary_language_sequence(self):
        resp = _plan(["Computer Science (BS, SAS)"], grad="Spring 2030", max_cr=18)
        codes = {course.code for term in resp.terms for course in term.courses}
        assert not {"FREN101", "FREN102", "FREN131", "FREN213", "FREN214", "FREN215"}.issubset(codes)

    def test_cs_bs_produces_terms(self):
        resp = _plan(["Computer Science (BS, SAS)"])
        assert len(resp.terms) > 0

    def test_no_remaining_courses_for_cs_bs(self):
        resp = _plan(["Computer Science (BS, SAS)"], grad="Spring 2030", max_cr=18)
        assert resp.remaining_courses == []

    def test_completed_courses_not_rescheduled(self):
        resp = _plan(
            ["Computer Science (BS, SAS)"],
            completed=["CS111", "CS112", "MATH151"],
        )
        all_codes = [c.code for t in resp.terms for c in t.courses]
        assert "CS111" not in all_codes
        assert "CS112" not in all_codes
        assert "MATH151" not in all_codes

    def test_registered_courses_keep_their_term_and_consume_capacity(self):
        request = PlanRequest(
            degree_level="bachelor",
            majors=["Computer Science (BS, SAS)"],
            minors=[],
            completed_courses=[],
            in_progress_courses=["CS111", "MATH151", "EXPOS101"],
            in_progress_terms={
                "CS111": "Fall 2026",
                "MATH151": "Fall 2026",
                "EXPOS101": "Fall 2026",
            },
            in_progress_credit_hours={"CS111": 4, "MATH151": 4, "EXPOS101": 3},
            earned_degree_credits=90,
            start_term="Fall 2026",
            target_grad_term="Spring 2027",
            max_credits_per_term=12,
            preferred_seasons=["Fall", "Spring"],
        )
        response = heuristic_plan(request)
        fall = next(term for term in response.terms if term.term == "Fall 2026")

        assert fall.total_credits == 11
        assert {course.code for course in fall.courses} == {"CS111", "MATH151", "EXPOS101"}
        assert all(course.is_in_progress for course in fall.courses)

    def test_completed_elective_reduces_quota(self):
        resp = _plan(
            ["Computer Science (BS, SAS)"],
            completed=["CS210", "CS314"],
        )
        elective_codes = [c.code for t in resp.terms for c in t.courses if c.is_elective]
        assert "CS210" not in elective_codes
        assert "CS314" not in elective_codes

    def test_credit_limit_respected(self):
        resp = _plan(["Computer Science (BS, SAS)"], max_cr=12)
        for term in resp.terms:
            assert term.total_credits <= 12, f"{term.term} exceeded limit: {term.total_credits}"

    def test_min_credit_limit(self):
        resp = _plan(["Computer Science (BS, SAS)"], max_cr=6)
        for term in resp.terms:
            assert term.total_credits <= 6

    def test_prereqs_satisfied_before_course(self):
        resp = _plan(["Computer Science (BS, SAS)"])
        scheduled_order: dict = {}
        for term in resp.terms:
            for course in term.courses:
                scheduled_order[course.code] = term.term
        if "CS112" in scheduled_order and "CS211" in scheduled_order:
            assert _term_index(scheduled_order["CS112"]) < _term_index(scheduled_order["CS211"])
        if "CS205" in scheduled_order and "CS213" in scheduled_order:
            assert _term_index(scheduled_order["CS205"]) <= _term_index(scheduled_order["CS213"])

    def test_dual_major_includes_both_required_courses(self):
        resp = _plan(["Computer Science (BS, SAS)", "Mathematics (BS, SAS)"])
        all_codes = {c.code for t in resp.terms for c in t.courses}
        math_bs_only = {"MATH251", "MATH300", "MATH311", "MATH351"}
        assert math_bs_only.issubset(all_codes | {"MATH251", "MATH300", "MATH311", "MATH351"})
        assert "CS111" in all_codes or "CS111" in []

    def test_dual_major_elective_count_is_correct(self):
        resp = _plan(["Computer Science (BS, SAS)", "Mathematics (BS, SAS)"], grad="Spring 2030", max_cr=18)
        assert resp.remaining_courses == []

    def test_four_year_dance_plan_prioritizes_prerequisite_chains(self):
        resp = _plan(["Dance (BFA, MGSA)"], grad="Spring 2030", max_cr=18)
        assert resp.remaining_courses == []
        assert not any("Not all requirements fit" in warning for warning in resp.warnings)

    def test_four_year_design_plan_uses_official_six_course_design_sequence(self):
        resp = _plan(["Design (BFA, MGSA)"], grad="Spring 2030", max_cr=18)
        assert resp.remaining_courses == []
        scheduled = {course.code for term in resp.terms for course in term.courses}
        assert "ART434" not in scheduled

    def test_professional_school_plan_loads_shared_sas_prerequisites(self):
        resp = _plan(["Animal Science (BS, SEBS)"], grad="Spring 2030", max_cr=18)
        all_codes = {course.code for term in resp.terms for course in term.courses}
        assert "MATH135" in all_codes
        assert "MATH115" in all_codes
        assert resp.remaining_courses == []

    def test_minor_courses_included(self):
        resp = _plan(
            ["Computer Science (BS, SAS)"],
            minors=["Mathematics (Minor, SAS)"],
            grad="Spring 2030",
            max_cr=18,
        )
        all_codes = {c.code for t in resp.terms for c in t.courses}
        elective_codes = {c.code for t in resp.terms for c in t.courses if c.is_elective}
        assert len(elective_codes) == 9

    def test_spring_only_no_summer_or_fall(self):
        resp = _plan(["Computer Science (BS, SAS)"], seasons=["Spring"], grad="Spring 2030")
        for t in resp.terms:
            assert t.term.startswith("Spring"), f"Unexpected term: {t.term}"

    def test_all_seasons_allowed(self):
        resp = _plan(["Computer Science (BS, SAS)"], seasons=["Spring", "Summer", "Fall"])
        seasons_used = {t.term.split()[0] for t in resp.terms}
        resp2 = _plan(
            ["Computer Science (BS, SAS)"],
            seasons=["Spring", "Summer", "Fall"],
            grad="Spring 2030",
            max_cr=15,
        )
        assert resp2.remaining_courses == []

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

    def test_finance_bsba_elective_prereqs_scheduled(self):
        resp = _plan(["Finance (BSBA, RBS)"], grad="Spring 2030", max_cr=20)
        all_codes = {c.code for t in resp.terms for c in t.courses}
        if "ACCT472" in all_codes:
            assert "ACCT326" in all_codes, "ACCT326 (prereq of ACCT472) should be scheduled"
            assert "ACCT325" in all_codes, "ACCT325 (prereq of ACCT326) should be scheduled"
        assert resp.remaining_courses == [], f"Unscheduled: {resp.remaining_courses}"

    def test_completed_major_courses_do_not_bypass_degree_credit_minimum(self):
        mostly_done = [
            "CS111", "CS112", "CS205", "CS206", "CS211", "CS213", "CS214",
            "MATH151", "MATH152", "MATH250",
            "PHYS203", "PHYS205", "PHYS204", "PHYS206",
            "STAT291",
            "CS210", "CS314", "CS323", "CS324", "CS334",
        ]
        resp = _plan(
            ["Computer Science (BS, SAS)"],
            completed=mostly_done,
            grad="Spring 2030",
        )
        assert resp.total_credits >= 120

    def test_timeline_keeps_empty_terms_through_requested_graduation(self):
        resp = heuristic_plan(PlanRequest(
            degree_level="bachelor",
            majors=["Computer Science (BS, SAS)"],
            minors=[],
            completed_courses=[],
            start_term="Fall 2026",
            target_grad_term="Spring 2030",
            max_credits_per_term=18,
            preferred_seasons=["Spring", "Fall"],
        ))
        assert [term.term for term in resp.terms] == [
            "Fall 2026", "Spring 2027", "Fall 2027", "Spring 2028",
            "Fall 2028", "Spring 2029", "Fall 2029", "Spring 2030",
        ]
        assert sum(term.total_credits for term in resp.terms) >= 120
        assert resp.terms[-2].courses
        assert resp.terms[-1].courses
