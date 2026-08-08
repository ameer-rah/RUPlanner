"""Broad program smoke test that runs in-process (no live server required)."""

from fastapi.testclient import TestClient

from app.main import app


SUPPORTED_UNDERGRAD_LEVELS = {
    "bachelor_bs", "bachelor_ba", "bachelor_bfa", "bachelor_bm", "bachelor_bsba", "minor",
}


def test_every_listed_undergraduate_program_can_be_planned():
    client = TestClient(app)
    programs_response = client.get("/programs")
    assert programs_response.status_code == 200
    programs = [
        program for program in programs_response.json()
        if program["degree_level"] in SUPPORTED_UNDERGRAD_LEVELS
    ]
    failures = []
    base_payload = {
        "completed_courses": [],
        "start_term": "Fall 2026",
        "target_grad_term": "Spring 2030",
        "max_credits_per_term": 18,
        "summer_max_credits": 12,
        "winter_max_credits": 4,
        "preferred_seasons": ["Spring", "Fall"],
    }

    for program in programs:
        if program["degree_level"] == "minor":
            majors = ["African, Middle Eastern and South Asian Languages and Literatures (BA, SAS)"]
            minors = [program["display_name"]]
        else:
            majors = [program["display_name"]]
            minors = []
        response = client.post(
            "/plan", json={**base_payload, "majors": majors, "minors": minors},
        )
        if response.status_code != 200:
            failures.append(
                f"{program['display_name']}: HTTP {response.status_code} {response.text[:200]}"
            )

    assert not failures, "Program planning failures:\n" + "\n".join(failures)
