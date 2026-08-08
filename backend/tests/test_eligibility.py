from app.core.eligibility import StudentRecord, evaluate_rule


def record(**kwargs):
    return StudentRecord(completed=frozenset(kwargs.pop("completed", [])), **kwargs)


def test_all_and_or_prerequisites():
    rule = {"allOf": ["CS111", {"anyOf": ["MATH151", "MATH135"]}]}
    assert evaluate_rule(rule, record(completed={"CS111", "MATH151"})).allowed
    assert not evaluate_rule(rule, record(completed={"CS111"})).allowed


def test_minimum_grade_is_explainable():
    result = evaluate_rule(
        {"course": "CS111", "minGrade": "C"},
        record(completed={"CS111"}, grades={"CS111": "D"}),
    )
    assert not result.allowed
    assert "C or better" in result.reasons[0]


def test_concurrent_course_and_standing_constraints():
    assert evaluate_rule(
        {"course": "MATH152", "concurrent": True},
        record(in_progress=frozenset({"MATH152"})),
    ).allowed
    assert not evaluate_rule({"minCredits": 60}, record(earned_credits=45)).allowed


def test_program_restriction_and_unknown_rule_fail_closed():
    assert evaluate_rule({"programIn": ["Computer Science"]}, record(programs=frozenset({"Computer Science"}))).allowed
    unknown = evaluate_rule({"permission": "instructor"}, record())
    assert not unknown.allowed and unknown.unknown
