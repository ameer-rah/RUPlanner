from contextlib import asynccontextmanager
import os
import re
from dotenv import load_dotenv

load_dotenv()
from datetime import datetime, timedelta
from typing import List

from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import bcrypt
import requests as _requests
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from apscheduler.schedulers.background import BackgroundScheduler

from .database import engine, Base, SessionLocal
from . import models
from .schemas import (
    PlanRequest, PlanResponse, ProgramInfo, CourseSearchResult,
    UserCreate, Token, SaveScheduleRequest, GoogleAuthRequest,
    SnipeCreate, SnipeOut,
    ForgotPasswordRequest, ResetPasswordRequest,
)
from .core.planner import heuristic_plan
from .core.sniper import poll_snipes, fetch_sections_for_subject

SECRET_KEY = os.getenv("SECRET_KEY", "ru-planner-dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

_bearer = HTTPBearer()
_scheduler = BackgroundScheduler()

@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    _scheduler.add_job(poll_snipes, "interval", minutes=2, id="snipe_poll")
    _scheduler.start()
    yield
    _scheduler.shutdown(wait=False)

app = FastAPI(title="RU Planner API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_LEVEL_LABEL = {
    "bachelor_bs":           "BS",
    "bachelor_ba":           "BA",
    "bachelor_bfa":          "BFA",
    "bachelor_bm":           "BM",
    "bachelor_bsba":         "BSBA",
    "concentration":         "Concentration",
    "minor":                 "Minor",
    "master":                "MS",
    "master_ms":             "MS",
    "master_ma":             "MA",
    "master_mat":            "MAT",
    "master_meng":           "MEng",
    "doctorate":             "PhD",
    "professional_doctorate":"PsyD",
    "associate":             "AS",
}

@app.get("/programs", response_model=List[ProgramInfo])
def list_programs() -> List[ProgramInfo]:
    db = SessionLocal()
    try:
        rows = (
            db.query(models.Program)
            .order_by(models.Program.school, models.Program.major_name, models.Program.degree_level)
            .all()
        )
        return [
            ProgramInfo(
                school=r.school,
                degree_level=r.degree_level,
                major_name=r.major_name,
                catalog_year=r.catalog_year,
                display_name=(
                    f"{r.major_name}"
                    f" ({_LEVEL_LABEL.get(r.degree_level, r.degree_level)}, {r.school})"
                ),
            )
            for r in rows
        ]
    finally:
        db.close()

@app.get("/courses", response_model=List[CourseSearchResult])
def search_courses(q: str = "", limit: int = 20) -> List[CourseSearchResult]:
    if not q:
        return []
    db = SessionLocal()
    try:
        pattern = f"{q}%"
        rows = (
            db.query(models.Course)
            .filter(
                models.Course.code.ilike(pattern) | models.Course.title.ilike(f"%{q}%")
            )
            .order_by(models.Course.code)
            .limit(limit)
            .all()
        )
        return [
            CourseSearchResult(code=r.code, title=r.title, credits=r.credits)
            for r in rows
        ]
    finally:
        db.close()

@app.post("/plan", response_model=PlanResponse)
def generate_plan(payload: PlanRequest) -> PlanResponse:
    try:
        return heuristic_plan(payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))

def _word_overlap(a: str, b: str) -> float:
    wa = {w for w in re.sub(r"[^a-z\s]", "", a.lower()).split() if len(w) > 2}
    wb = {w for w in re.sub(r"[^a-z\s]", "", b.lower()).split() if len(w) > 2}
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def _extract_transcript_text(content: bytes) -> str:
    import pdfplumber
    import io as _io
    parts: List[str] = []
    with pdfplumber.open(_io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            mid_x = page.width / 2
            for x0, x1 in [(0, mid_x), (mid_x, page.width)]:
                col = page.crop((x0, 0, x1, page.height))
                clean = col.filter(
                    lambda obj: obj["object_type"] != "char" or obj.get("size", 0) < 15
                )
                text = clean.extract_text(x_tolerance=2, y_tolerance=3) or ""
                if text.strip():
                    parts.append(text)
    return "\n".join(parts)


@app.post("/parse-transcript-debug")
async def parse_transcript_debug(file: UploadFile = File(...)) -> dict:
    content = await file.read()
    try:
        text = _extract_transcript_text(content)
    except Exception as exc:
        return {"error": str(exc)}
    from .transcript_parser import parse_transcript_text
    result = parse_transcript_text(text)
    return {
        "raw_text_first_800": text[:800],
        "total_lines": len(text.splitlines()),
        "courses_found": len(result.courses),
        "completed": [
            {"norm": c.normalized_code, "title": c.title_raw, "grade": c.grade}
            for c in result.get_completed_courses()
        ],
        "in_progress": [
            {"norm": c.normalized_code, "title": c.title_raw}
            for c in result.get_in_progress_courses()
        ],
        "warnings": result.warnings,
    }


@app.post("/parse-transcript", response_model=List[str])
async def parse_transcript(file: UploadFile = File(...)) -> List[str]:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 20 MB).")
    try:
        text = _extract_transcript_text(content)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not read PDF: {exc}")

    from .transcript_parser import parse_transcript_text
    result = parse_transcript_text(text)

    db = SessionLocal()
    try:
        all_courses = db.query(models.Course).with_entities(
            models.Course.code, models.Course.title
        ).all()
    finally:
        db.close()

    by_number: dict = {}
    for code, title in all_courses:
        num = re.sub(r"^[A-Z]+", "", code)
        by_number.setdefault(num, []).append((code, title))

    seen: set = set()
    codes: List[str] = []
    for course in result.get_completed_courses():
        candidates = by_number.get(course.crs, [])
        if not candidates:
            continue
        if len(candidates) == 1:
            best_code = candidates[0][0]
        else:
            best_code, best_score = max(
                candidates,
                key=lambda c: _word_overlap(course.title_raw, c[1]),
            )[0], 0.0
            for code, title in candidates:
                score = _word_overlap(course.title_raw, title)
                if score > best_score:
                    best_score = score
                    best_code = code
            if best_score < 0.3:
                continue
        if best_code not in seen:
            seen.add(best_code)
            codes.append(best_code)

    return codes

def _create_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def _get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> int:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return int(user_id)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.post("/auth/register", response_model=Token)
def register(payload: UserCreate) -> Token:
    db = SessionLocal()
    try:
        if db.query(models.User).filter(models.User.email == payload.email).first():
            raise HTTPException(status_code=400, detail="Email already registered")
        user = models.User(email=payload.email, hashed_password=_hash_password(payload.password))
        db.add(user)
        db.commit()
        db.refresh(user)
        return Token(access_token=_create_token(user.id), token_type="bearer")
    finally:
        db.close()

@app.post("/auth/login", response_model=Token)
def login(payload: UserCreate) -> Token:
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == payload.email).first()
        if not user or not user.hashed_password or not _verify_password(payload.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        return Token(access_token=_create_token(user.id), token_type="bearer")
    finally:
        db.close()

@app.post("/auth/google", response_model=Token)
def google_auth(payload: GoogleAuthRequest) -> Token:
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="Google auth is not configured on the server.")
    try:
        idinfo = google_id_token.verify_oauth2_token(
            payload.credential,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )
        email = idinfo["email"]
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google token.")
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            user = models.User(email=email, hashed_password="")
            db.add(user)
            db.commit()
            db.refresh(user)
        return Token(access_token=_create_token(user.id), token_type="bearer")
    finally:
        db.close()

@app.get("/auth/me")
def me(user_id: int = Depends(_get_current_user_id)):
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {"id": user.id, "email": user.email}
    finally:
        db.close()

@app.post("/auth/forgot-password", status_code=200)
def forgot_password(payload: ForgotPasswordRequest):
    import secrets
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == payload.email).first()
        if user:
            token = secrets.token_urlsafe(32)
            expires = datetime.utcnow() + timedelta(hours=1)
            reset_token = models.PasswordResetToken(
                user_id=user.id, token=token, expires_at=expires
            )
            db.add(reset_token)
            db.commit()
            if RESEND_API_KEY:
                import resend as _resend
                _resend.api_key = RESEND_API_KEY
                reset_link = f"{FRONTEND_URL}/reset-password?token={token}"
                _resend.Emails.send({
                    "from": "RU Planner <noreply@ruplanner.app>",
                    "to": [user.email],
                    "subject": "Reset your RU Planner password",
                    "html": f"""
                        <div style="font-family:sans-serif;max-width:480px;margin:0 auto;padding:32px 24px">
                          <img src="{FRONTEND_URL}/RUPlanner Logo.svg" alt="RU Planner" style="height:36px;margin-bottom:24px" />
                          <h2 style="margin:0 0 8px;font-size:20px;color:#111">Reset your password</h2>
                          <p style="margin:0 0 24px;color:#555;font-size:14px;line-height:1.6">
                            We received a request to reset the password for your RU Planner account.
                            Click the button below to choose a new password. This link expires in 1 hour.
                          </p>
                          <a href="{reset_link}" style="display:inline-block;background:#cc0033;color:#fff;text-decoration:none;padding:12px 24px;border-radius:8px;font-size:15px;font-weight:600">
                            Reset password
                          </a>
                          <p style="margin:24px 0 0;color:#888;font-size:12px;line-height:1.6">
                            If you didn't request this, you can safely ignore this email.
                            Your password will not change.
                          </p>
                        </div>
                    """,
                })
        return {"message": "If that email is registered, a reset link has been sent."}
    finally:
        db.close()


@app.post("/auth/reset-password", status_code=200)
def reset_password(payload: ResetPasswordRequest):
    db = SessionLocal()
    try:
        reset_token = (
            db.query(models.PasswordResetToken)
            .filter(
                models.PasswordResetToken.token == payload.token,
                models.PasswordResetToken.used == False,
                models.PasswordResetToken.expires_at > datetime.utcnow(),
            )
            .first()
        )
        if not reset_token:
            raise HTTPException(status_code=400, detail="Invalid or expired reset link.")
        if len(payload.new_password) < 6:
            raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")
        user = db.query(models.User).filter(models.User.id == reset_token.user_id).first()
        user.hashed_password = _hash_password(payload.new_password)
        reset_token.used = True
        db.commit()
        return {"message": "Password reset successfully."}
    finally:
        db.close()


@app.post("/schedules")
def save_schedule(payload: SaveScheduleRequest, user_id: int = Depends(_get_current_user_id)):
    db = SessionLocal()
    try:
        schedule = models.SavedSchedule(user_id=user_id, name=payload.name, plan_data=payload.plan_data)
        db.add(schedule)
        db.commit()
        db.refresh(schedule)
        return {"id": schedule.id, "message": "Schedule saved"}
    finally:
        db.close()

@app.get("/schedules")
def get_schedules(user_id: int = Depends(_get_current_user_id)):
    db = SessionLocal()
    try:
        rows = (
            db.query(models.SavedSchedule)
            .filter(models.SavedSchedule.user_id == user_id)
            .order_by(models.SavedSchedule.created_at.desc())
            .all()
        )
        return [{"id": r.id, "name": r.name, "plan_data": r.plan_data, "created_at": r.created_at.isoformat()} for r in rows]
    finally:
        db.close()

@app.delete("/schedules/{schedule_id}", status_code=204)
def delete_schedule(schedule_id: int, user_id: int = Depends(_get_current_user_id)):
    db = SessionLocal()
    try:
        row = (
            db.query(models.SavedSchedule)
            .filter(models.SavedSchedule.id == schedule_id, models.SavedSchedule.user_id == user_id)
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="Schedule not found")
        db.delete(row)
        db.commit()
    finally:
        db.close()

_RMP_URL = "https://www.ratemyprofessors.com/graphql"
_RMP_HOME = "https://www.ratemyprofessors.com/"
_RMP_SCHOOL_ID = "U2Nob29sLTgyNQ=="
_rmp_cache: dict = {}
_RMP_HEADERS = {
    "Authorization": "Basic dGVzdDp0ZXN0",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Origin": "https://www.ratemyprofessors.com",
    "Referer": "https://www.ratemyprofessors.com/",
}
_rmp_session: "_requests.Session | None" = None

_RMP_QUERY = """
query NewSearchTeachersQuery($text: String!, $schoolID: ID!, $first: Int!) {
  newSearch {
    teachers(query: {text: $text, schoolID: $schoolID}, first: $first) {
      edges {
        node {
          firstName
          lastName
          avgRating
          numRatings
          avgDifficulty
          wouldTakeAgainPercent
          department
          legacyId
        }
      }
    }
  }
}
"""

def _get_rmp_session() -> "_requests.Session":
    global _rmp_session
    if _rmp_session is None:
        _rmp_session = _requests.Session()
        _rmp_session.get(_RMP_HOME, headers=_RMP_HEADERS, timeout=5)
    return _rmp_session

def _name_matches(query: str, first: str, last: str) -> bool:
    parts = query.lower().split()
    first_l, last_l = first.lower(), last.lower()
    return all(p in first_l or p in last_l for p in parts)

@app.get("/rmp/rating")
def rmp_rating(name: str = Query(...)):
    if "," in name:
        parts = [p.strip().title() for p in name.split(",", 1)]
        query_name = f"{parts[1]} {parts[0]}"
    else:
        query_name = name.strip().title()
    cache_key = query_name.lower()
    if cache_key in _rmp_cache:
        return _rmp_cache[cache_key]
    try:
        session = _get_rmp_session()
        resp = session.post(
            _RMP_URL,
            json={"query": _RMP_QUERY, "variables": {"text": query_name, "schoolID": _RMP_SCHOOL_ID, "first": 5}},
            headers=_RMP_HEADERS,
            timeout=5,
        )
        edges = resp.json().get("data", {}).get("newSearch", {}).get("teachers", {}).get("edges", [])
    except Exception:
        return None
    node = None
    for edge in edges:
        n = edge["node"]
        if _name_matches(query_name, n.get("firstName", ""), n.get("lastName", "")):
            node = n
            break
    if node is None:
        _rmp_cache[cache_key] = None
        return None
    result = {
        "name": f"{node['firstName']} {node['lastName']}",
        "rating": node.get("avgRating"),
        "num_ratings": node.get("numRatings", 0),
        "difficulty": node.get("avgDifficulty"),
        "would_take_again": node.get("wouldTakeAgainPercent"),
        "legacy_id": node.get("legacyId"),
    }
    _rmp_cache[cache_key] = result
    return result

@app.get("/soc/sections")
def soc_sections(
    subject: str = Query(...),
    year: str = Query("2026"),
    term: str = Query("9"),
    campus: str = Query("NB"),
):
    sections = fetch_sections_for_subject(subject, year, term, campus)
    return sections

@app.post("/snipes", response_model=SnipeOut)
def create_snipe(payload: SnipeCreate, user_id: int = Depends(_get_current_user_id)):
    db = SessionLocal()
    try:
        snipe = models.Snipe(
            user_id=user_id,
            course_code=payload.course_code,
            course_title=payload.course_title,
            section_index=payload.section_index,
            section_number=payload.section_number,
            year=payload.year,
            term=payload.term,
            campus=payload.campus,
            phone_number=payload.phone_number,
        )
        db.add(snipe)
        db.commit()
        db.refresh(snipe)
        return _snipe_to_out(snipe)
    finally:
        db.close()

@app.get("/snipes", response_model=List[SnipeOut])
def list_snipes(user_id: int = Depends(_get_current_user_id)):
    db = SessionLocal()
    try:
        rows = (
            db.query(models.Snipe)
            .filter(models.Snipe.user_id == user_id)
            .order_by(models.Snipe.created_at.desc())
            .all()
        )
        return [_snipe_to_out(r) for r in rows]
    finally:
        db.close()

@app.delete("/snipes/{snipe_id}", status_code=204)
def delete_snipe(snipe_id: int, user_id: int = Depends(_get_current_user_id)):
    db = SessionLocal()
    try:
        row = (
            db.query(models.Snipe)
            .filter(models.Snipe.id == snipe_id, models.Snipe.user_id == user_id)
            .first()
        )
        if not row:
            raise HTTPException(status_code=404, detail="Snipe not found")
        db.delete(row)
        db.commit()
    finally:
        db.close()

def _snipe_to_out(s: models.Snipe) -> SnipeOut:
    return SnipeOut(
        id=s.id,
        course_code=s.course_code,
        course_title=s.course_title,
        section_index=s.section_index,
        section_number=s.section_number,
        year=s.year,
        term=s.term,
        campus=s.campus,
        phone_number=s.phone_number,
        active=s.active,
        notified_at=s.notified_at.isoformat() if s.notified_at else None,
        created_at=s.created_at.isoformat(),
    )
