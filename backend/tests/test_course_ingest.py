from datetime import date
from unittest.mock import Mock

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import Course, CourseImport, CourseOffering
from management import ingest_courses as importer


def course(code, level="U", campus="NB"):
    return {"courseString": code, "title": "Sample Course", "credits": 3, "level": level, "mainCampus": campus}


def test_imports_both_levels_and_preserves_last_good_snapshot(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    monkeypatch.setattr(importer, "SessionLocal", factory)
    rows = [course("01:198:111"), course("01:999:123"), course("16:198:501", "G")]
    response = Mock()
    response.json.side_effect = [rows, rows, [], [course("21:198:111", campus="NK")], [rows[0], rows[2]]]
    request = Mock(return_value=response)
    monkeypatch.setattr(importer.requests, "get", request)

    for _ in range(2):
        result = importer.ingest(2027, ["winter"])
        assert [scope["status"] for scope in result] == ["published", "published"]
    assert request.call_args.kwargs["params"] == {"year": 2027, "term": "0", "campus": "NB"}

    for _ in range(2):
        assert [scope["status"] for scope in importer.ingest(2027, ["winter"])] == ["failed", "failed"]
    assert [scope["status"] for scope in importer.ingest(2027, ["winter"])] == ["failed", "published"]

    with factory() as db:
        assert db.get(Course, "01:999:123").code == "01:999:123"
        assert db.get(Course, "01:198:111").code == "CS111"
        assert db.get(Course, "21:198:111") is None
        assert db.get(CourseImport, (2027, "winter", "U")).course_count == 2
        assert len(db.scalars(select(CourseOffering)).all()) == 3


def test_dry_run_uses_no_database_and_reports_unmapped_courses(monkeypatch):
    monkeypatch.setattr(importer, "fetch_term", lambda *_: [course("01:999:123")])
    session = Mock()
    monkeypatch.setattr(importer, "SessionLocal", session)

    undergraduate, graduate = importer.ingest(2027, ["spring"], dry_run=True)

    session.begin.assert_not_called()
    assert undergraduate["status"] == "preview"
    assert undergraduate["unmapped_count"] == 1
    assert graduate["status"] == "preview"
    assert graduate["course_count"] == 0


def test_fall_refresh_uses_next_year_for_winter_and_spring():
    assert importer.current_term_specs(date(2026, 11, 23)) == [
        (2026, "summer"), (2026, "fall"), (2027, "winter"), (2027, "spring")
    ]


def test_published_term_records_empty_level(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    monkeypatch.setattr(importer, "SessionLocal", factory)
    monkeypatch.setattr(importer, "fetch_term", lambda *_: [course("01:198:111")])

    for _ in range(2):
        assert [scope["status"] for scope in importer.ingest(2027, ["winter"])] == ["published", "published"]

    with factory() as db:
        assert db.get(CourseImport, (2027, "winter", "G")).course_count == 0
        assert len(db.scalars(select(CourseOffering)).all()) == 1
