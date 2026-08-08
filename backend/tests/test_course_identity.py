from app.models import Course
from management.ingest_courses import parse_credits


def test_full_rutgers_code_is_course_primary_key():
    assert [column.name for column in Course.__table__.primary_key.columns] == ["raw_code"]
    assert not Course.__table__.c.code.unique


def test_fractional_and_variable_credits_are_not_truncated():
    assert parse_credits({"credits": "1.5"}) == 1.5
    assert parse_credits({"credits": "2.5-4.0"}) == 2.5
    assert parse_credits({}) == 0.0
