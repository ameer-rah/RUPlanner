from app.core.transcript import (
    classify_grade,
    merge_extracted_rows,
    latest_status_codes,
    normalize_extracted_courses,
    normalize_raw_code,
)


def test_raw_code_normalization_is_strict_but_whitespace_tolerant():
    assert normalize_raw_code("01: 198 :111") == "01:198:111"
    assert normalize_raw_code("CS111") is None


def test_grade_flags_are_deterministic_and_exclusive():
    assert classify_grade(" a- ") == ("A-", True, False, False)
    assert classify_grade("F") == ("F", False, True, False)
    assert classify_grade("") == ("", False, False, True)
    assert classify_grade("W") == ("W", False, False, False)
    assert classify_grade("made-up") == ("MADE-UP", False, False, False)


def test_raw_code_mapping_overrides_hallucinated_short_code():
    courses = normalize_extracted_courses(
        [{
            "title_raw": "INTRO COMPUTER SCI",
            "raw_code": "01:198:111",
            "rutgers_code": "MATH151",
            "grade": "A",
            "credits": "4.0",
        }],
        {"01:198:111": "CS111"},
        {"CS111", "MATH151"},
    )
    assert courses[0].rutgers_code == "CS111"
    assert courses[0].passed is True


def test_unknown_and_transfer_title_guesses_are_not_auto_applied():
    courses = normalize_extracted_courses(
        [
            {"raw_code": "01:999:999", "rutgers_code": "CS111", "grade": "A"},
            {"title_raw": "CALCULUS I", "rutgers_code": "MATH151", "grade": "TR", "is_transfer": True},
        ],
        {},
        {"CS111", "MATH151"},
    )
    assert [c.rutgers_code for c in courses] == [None, None]


def test_latest_attempt_controls_completed_status():
    courses = normalize_extracted_courses(
        [
            {"raw_code": "01:198:111", "grade": "A", "semester": "Fall 2023"},
            {"raw_code": "01:198:111", "grade": "", "semester": "Spring 2024"},
            {"raw_code": "01:640:151", "grade": "F", "semester": "Fall 2023"},
            {"raw_code": "01:640:151", "grade": "B", "semester": "Spring 2024"},
        ],
        {"01:198:111": "CS111", "01:640:151": "MATH151"},
        {"CS111", "MATH151"},
    )
    completed, in_progress = latest_status_codes(courses)
    assert completed == ["CS111", "MATH151"]
    assert in_progress == []
    canonical_completed, canonical_in_progress = latest_status_codes(courses, canonical=True)
    assert canonical_completed == ["01:198:111", "01:640:151"]
    assert canonical_in_progress == []


def test_partial_deterministic_parse_is_completed_by_ai_rows():
    deterministic = [{
        "raw_code": "01:198:111",
        "title_raw": "INTRO COMPUTER SCI",
        "grade": "A",
        "semester": "Fall 2024",
        "credits": 4,
    }]
    ai = [
        {**deterministic[0], "rutgers_code": "CS111"},
        {
            "raw_code": "01:640:151",
            "title_raw": "CALCULUS I",
            "grade": "B+",
            "semester": "Fall 2024",
            "credits": 4,
        },
    ]
    merged = merge_extracted_rows(deterministic, ai)
    assert [row["raw_code"] for row in merged] == ["01:198:111", "01:640:151"]


def test_ai_can_fill_blank_grade_without_overriding_printed_grade():
    deterministic = [
        {"raw_code": "01:198:111", "grade": "", "semester": "Fall 2024"},
        {"raw_code": "01:640:151", "grade": "A", "semester": "Fall 2024"},
    ]
    ai = [
        {"raw_code": "01:198:111", "grade": "B", "semester": "Fall 2024"},
        {"raw_code": "01:640:151", "grade": "C", "semester": "Fall 2024"},
    ]
    merged = merge_extracted_rows(deterministic, ai)
    assert [row["grade"] for row in merged] == ["B", "A"]
