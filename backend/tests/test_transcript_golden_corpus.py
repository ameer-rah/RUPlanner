"""Golden transcript cases at the untrusted-AI/deterministic-parser boundary.

Fixtures contain only invented names and histories. ``mock_extraction`` is the
captured shape a mocked extraction provider would return; no network, model, or
credential is involved in these regression tests.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from app.core.transcript import (
    extract_deterministic_rows,
    latest_status_codes,
    normalize_extracted_courses,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "transcripts"
CASES = (
    "undergraduate",
    "graduate",
    "transfer",
    "repeated_course",
    "unusual_grades",
)


def load_case(name: str) -> dict:
    with (FIXTURE_DIR / f"{name}.json").open(encoding="utf-8") as fixture_file:
        return json.load(fixture_file)


@pytest.mark.parametrize("case_name", CASES)
def test_golden_transcript_normalization_with_mocked_extraction(case_name: str):
    case = load_case(case_name)
    extractor = Mock(return_value=case["mock_extraction"])

    extracted_rows = extractor(case["transcript_text"])
    catalog = case["catalog"]
    courses = normalize_extracted_courses(
        extracted_rows,
        raw_code_map=catalog,
        known_codes=set(catalog.values()),
    )
    completed, in_progress = latest_status_codes(courses)

    extractor.assert_called_once_with(case["transcript_text"])
    assert completed == case["expected"]["completed"]
    assert in_progress == case["expected"]["in_progress"]
    assert sum(course.rutgers_code is None for course in courses) == case["expected"]["unmatched_count"]


def test_transfer_title_guess_is_rejected_but_explicit_equivalency_is_kept():
    case = load_case("transfer")
    courses = normalize_extracted_courses(
        case["mock_extraction"], case["catalog"], set(case["catalog"].values())
    )

    assert courses[0].rutgers_code == "MATH151"
    assert courses[0].passed is True
    assert courses[1].rutgers_code is None
    assert courses[1].equivalency_note


@pytest.mark.parametrize("case_name", CASES)
def test_deterministic_parser_reads_printed_rutgers_rows(case_name: str):
    case = load_case(case_name)
    expected = {
        row["raw_code"] for row in case["mock_extraction"] if row.get("raw_code")
    }
    parsed = {
        row["raw_code"] for row in extract_deterministic_rows(case["transcript_text"])
    }
    assert expected.issubset(parsed)


def test_unusual_grades_and_invalid_values_remain_safe():
    case = load_case("unusual_grades")
    courses = normalize_extracted_courses(
        case["mock_extraction"], case["catalog"], set(case["catalog"].values())
    )
    by_title = {course.title_raw: course for course in courses}

    assert by_title["EXPOS"].passed is True
    assert by_title["INTRO DISCRETE STRUCT I"].failed is True
    assert not by_title["INTRO LINEAR ALGEBRA"].passed
    assert not by_title["INTRO LINEAR ALGEBRA"].failed
    assert not by_title["GENERAL PHYSICS"].is_in_progress
    assert by_title["INTRO DISCRETE STRUCT II"].is_in_progress is True
    assert by_title["TOPICS"].rutgers_code is None
    assert by_title["TOPICS"].credits == 0.0


def test_fixture_corpus_contains_no_real_identifiers():
    forbidden_keys = {"student_id", "netid", "email", "date_of_birth", "address"}
    for case_name in CASES:
        case = load_case(case_name)
        assert "synthetic" in case["privacy"].lower()
        assert forbidden_keys.isdisjoint(case)


def test_official_fixed_column_rows_and_registered_terms_are_parsed_locally():
    text = """
TRANSFER COURSES
Fall 2023
 FRESHMAN COMPOSITION                 01 355 101       3.0
 GENERAL HUMANITIES                   TR T01 EC         3.0
Fall 2026 SCHOOL OF ARTS AND SCIENCES
 DESIGN AND ANALYSIS OF ALGORITHMS    01 198 344 01    4.0
Spring 2027 SCHOOL OF ARTS AND SCIENCES
 INTRODUCTION TO ARTIFICIAL INTELLIGENCE 01 198 440 01 4.0 A
"""
    rows = extract_deterministic_rows(text)

    assert [(row["raw_code"], row["grade"], row["semester"]) for row in rows] == [
        ("01:355:101", "TR", "Fall 2023"),
        (None, "TR", "Fall 2023"),
        ("01:198:344", "", "Fall 2026"),
        ("01:198:440", "A", "Spring 2027"),
    ]
