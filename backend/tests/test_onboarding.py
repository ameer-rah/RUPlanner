from fastapi.testclient import TestClient

from app.database import SessionLocal
from app.main import app
from app.models import User


client = TestClient(app)


def _ensure_test_user(onboarded: bool = False) -> None:
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == 1).first()
        if not user:
            user = User(
                id=1,
                email="returning@example.invalid",
                hashed_password="test-only",
            )
            db.add(user)
        user.onboarding_completed = onboarded
        user.planner_profile = None
        user.last_plan = None
        db.commit()
    finally:
        db.close()


def test_me_exposes_account_onboarding_state():
    _ensure_test_user(onboarded=True)
    response = client.get("/auth/me")
    assert response.status_code == 200
    assert response.json()["onboarding_completed"] is True


def test_successful_first_plan_completes_onboarding_and_persists_profile():
    _ensure_test_user(onboarded=False)
    response = client.post("/plan", json={
        "degree_level": "bachelor",
        "majors": ["Computer Science (BS, SAS)"],
        "minors": [],
        "completed_courses": [],
        "target_grad_term": "Spring 2030",
        "max_credits_per_term": 18,
        "preferred_seasons": ["Spring", "Fall"],
    })
    assert response.status_code == 200

    profile = client.get("/profile")
    assert profile.status_code == 200
    data = profile.json()
    assert data["onboarding_completed"] is True
    assert data["planner_profile"]["majors"] == ["Computer Science (BS, SAS)"]
    assert data["last_plan"]["terms"]
