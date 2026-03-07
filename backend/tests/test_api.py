"""
API smoke tests for the RU Planner FastAPI backend.

Run from the backend directory:
    .venv/bin/python -m pytest tests/test_api.py -v
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# GET /programs
# ---------------------------------------------------------------------------

class TestListPrograms:
    def test_returns_200(self):
        res = client.get("/programs")
        assert res.status_code == 200

    def test_returns_list(self):
        res = client.get("/programs")
        data = res.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_program_has_required_fields(self):
        res = client.get("/programs")
        prog = res.json()[0]
        for field in ("school", "degree_level", "major_name", "catalog_year", "display_name"):
            assert field in prog, f"Missing field: {field}"

    def test_contains_cs_bs(self):
        res = client.get("/programs")
        names = [p["display_name"] for p in res.json()]
        assert any("Computer Science" in n and "BS" in n for n in names)

    def test_minors_are_included(self):
        res = client.get("/programs")
        levels = [p["degree_level"] for p in res.json()]
        assert "minor" in levels


# ---------------------------------------------------------------------------
# GET /courses
# ---------------------------------------------------------------------------

class TestSearchCourses:
    def test_empty_query_returns_empty(self):
        res = client.get("/courses")
        assert res.status_code == 200
        assert res.json() == []

    def test_cs_prefix_returns_results(self):
        res = client.get("/courses?q=CS111")
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)

    def test_result_has_required_fields(self):
        res = client.get("/courses?q=MATH")
        data = res.json()
        if data:
            for field in ("code", "title", "credits"):
                assert field in data[0]

    def test_limit_respected(self):
        res = client.get("/courses?q=CS&limit=3")
        assert res.status_code == 200
        assert len(res.json()) <= 3


# ---------------------------------------------------------------------------
# POST /plan
# ---------------------------------------------------------------------------

def _base_payload(**overrides):
    payload = {
        "majors": ["Computer Science (BS, SAS)"],
        "minors": [],
        "completed_courses": [],
        "target_grad_term": "Spring 2028",
        "max_credits_per_term": 15,
        "preferred_seasons": ["Spring", "Fall"],
    }
    payload.update(overrides)
    return payload


class TestGeneratePlan:
    def test_valid_request_returns_200(self):
        res = client.post("/plan", json=_base_payload())
        assert res.status_code == 200

    def test_response_shape(self):
        res = client.post("/plan", json=_base_payload())
        data = res.json()
        assert "terms" in data
        assert "remaining_courses" in data
        assert "warnings" in data

    def test_terms_have_courses(self):
        res = client.post("/plan", json=_base_payload())
        terms = res.json()["terms"]
        assert len(terms) > 0
        for term in terms:
            assert "term" in term
            assert "courses" in term
            assert "total_credits" in term
            assert len(term["courses"]) > 0

    def test_course_shape(self):
        res = client.post("/plan", json=_base_payload())
        course = res.json()["terms"][0]["courses"][0]
        for field in ("code", "title", "credits", "is_elective"):
            assert field in course

    def test_completed_courses_excluded(self):
        payload = _base_payload(completed_courses=["CS111", "CS112"])
        res = client.post("/plan", json=payload)
        assert res.status_code == 200
        all_codes = [c["code"] for t in res.json()["terms"] for c in t["courses"]]
        assert "CS111" not in all_codes
        assert "CS112" not in all_codes

    def test_credit_limit_enforced(self):
        payload = _base_payload(max_credits_per_term=9)
        res = client.post("/plan", json=payload)
        for term in res.json()["terms"]:
            assert term["total_credits"] <= 9

    def test_dual_major_returns_200(self):
        payload = _base_payload(majors=["Computer Science (BS, SAS)", "Mathematics (BS, SAS)"])
        res = client.post("/plan", json=payload)
        assert res.status_code == 200

    def test_dual_major_includes_math_courses(self):
        payload = _base_payload(
            majors=["Computer Science (BS, SAS)", "Mathematics (BS, SAS)"],
            target_grad_term="Spring 2030",
            max_credits_per_term=18,
        )
        res = client.post("/plan", json=payload)
        all_codes = {c["code"] for t in res.json()["terms"] for c in t["courses"]}
        # Math BS unique courses should appear
        assert len(all_codes & {"MATH251", "MATH300", "MATH311", "MATH351"}) > 0

    def test_minor_electives_included(self):
        payload = _base_payload(
            minors=["Mathematics (Minor, SAS)"],
            target_grad_term="Spring 2030",
            max_credits_per_term=18,
        )
        res = client.post("/plan", json=payload)
        assert res.status_code == 200
        elective_codes = [
            c["code"]
            for t in res.json()["terms"]
            for c in t["courses"]
            if c["is_elective"]
        ]
        # CS(5) + Math minor(4) = 9 electives scheduled
        assert len(elective_codes) == 9

    def test_spring_only_no_other_seasons(self):
        payload = _base_payload(
            preferred_seasons=["Spring"],
            target_grad_term="Spring 2030",
        )
        res = client.post("/plan", json=payload)
        assert res.status_code == 200
        for term in res.json()["terms"]:
            assert term["term"].startswith("Spring")

    def test_summer_only_preference(self):
        payload = _base_payload(
            preferred_seasons=["Summer"],
            target_grad_term="Summer 2030",
        )
        res = client.post("/plan", json=payload)
        assert res.status_code == 200
        for term in res.json()["terms"]:
            assert term["term"].startswith("Summer")

    def test_unknown_program_returns_404(self):
        payload = _base_payload(majors=["Fake Degree That Does Not Exist (BS, SAS)"])
        res = client.post("/plan", json=payload)
        assert res.status_code == 404

    def test_past_graduation_returns_warning(self):
        payload = _base_payload(target_grad_term="Spring 2020")
        res = client.post("/plan", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert len(data["warnings"]) > 0
        assert data["terms"] == []

    def test_all_seasons_allowed(self):
        payload = _base_payload(
            preferred_seasons=["Spring", "Summer", "Fall"],
            target_grad_term="Spring 2030",
            max_credits_per_term=15,
        )
        res = client.post("/plan", json=payload)
        assert res.status_code == 200
        assert res.json()["remaining_courses"] == []


# ---------------------------------------------------------------------------
# POST /parse-transcript
# ---------------------------------------------------------------------------

class TestParseTranscript:
    def test_non_pdf_rejected(self):
        res = client.post(
            "/parse-transcript",
            files={"file": ("transcript.txt", b"CS111 MATH151", "text/plain")},
        )
        assert res.status_code == 400

    def test_malformed_pdf_returns_422(self):
        res = client.post(
            "/parse-transcript",
            files={"file": ("transcript.pdf", b"not a real pdf", "application/pdf")},
        )
        assert res.status_code == 422

    def test_valid_pdf_returns_list(self):
        # Build a minimal valid PDF in-memory
        try:
            from pypdf import PdfWriter
            import io
            writer = PdfWriter()
            writer.add_blank_page(width=612, height=792)
            buf = io.BytesIO()
            writer.write(buf)
            pdf_bytes = buf.getvalue()
        except Exception:
            pytest.skip("pypdf not available")

        res = client.post(
            "/parse-transcript",
            files={"file": ("transcript.pdf", pdf_bytes, "application/pdf")},
        )
        assert res.status_code == 200
        assert isinstance(res.json(), list)
