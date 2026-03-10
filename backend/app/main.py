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
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from apscheduler.schedulers.background import BackgroundScheduler

from .database import engine, Base, SessionLocal
from . import models
from .schemas import (
    PlanRequest, PlanResponse, ProgramInfo, CourseSearchResult,
    UserCreate, Token, SaveScheduleRequest, GoogleAuthRequest,
    SnipeCreate, SnipeOut,
)
from .core.planner import heuristic_plan
from .core.sniper import poll_snipes, fetch_sections_for_subject

SECRET_KEY = os.getenv("SECRET_KEY", "ru-planner-dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")

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


_RU_CODE_RE = re.compile(r'\b\d{2}:\d{3}:\d{3}\b')

_DEPT_MAP = {
    "198": "CS",
    "151": "MATH",
    "152": "MATH",
    "250": "MATH",
    "640": "MATH",
    "642": "MATH",
    "160": "PHYS",
    "750": "PHYS",
    "160": "CHEM",
    "160": "BIOL",
    "447": "STAT",
}

_SUBJECT_DEPT: dict = {
    "01:198": "CS",
    "01:640": "MATH",
    "01:642": "MATH",
    "01:750": "PHYS",
    "01:160": "CHEM",
    "01:119": "BIOL",
    "01:447": "STAT",
    "14:332": "ECE",
    "14:540": "BME",
    "01:355": "STAT",
    "01:090": "HNRS",
    "01:730": "PSYCH",
    "01:920": "SOC",
    "01:790": "POLISCI",
    "01:070": "ANTHRO",
    "01:220": "ECON",
    "01:355": "STAT",
    "01:300": "ENGLISH",
    "01:685": "LINGUISTICS",
}


def _parse_transcript_text(text: str) -> List[str]:
    codes: List[str] = []

    for match in _RU_CODE_RE.finditer(text):
        raw = match.group()
        parts = raw.split(":")
        if len(parts) == 3:
            school_dept = f"{parts[0]}:{parts[1]}"
            course_num = parts[2]
            subject = _SUBJECT_DEPT.get(school_dept)
            if subject:
                code = f"{subject}{course_num}"
                if code not in codes:
                    codes.append(code)

    formatted_re = re.compile(r'\b([A-Z]{2,8})(\d{2,4}[A-Z]?)\b')
    for match in formatted_re.finditer(text):
        code = match.group(0).upper()
        if code not in codes:
            codes.append(code)

    return codes


@app.post("/parse-transcript", response_model=List[str])
async def parse_transcript(file: UploadFile = File(...)) -> List[str]:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 20 MB).")

    try:
        from pypdf import PdfReader
        import io as _io
        reader = PdfReader(_io.BytesIO(content))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not read PDF: {exc}")

    codes = _parse_transcript_text(text)
    return codes


# ── Auth helpers ─────────────────────────────────────────────────────────────

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


# ── Auth endpoints ────────────────────────────────────────────────────────────

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
        if not user or not _verify_password(payload.password, user.hashed_password):
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


# ── Schedule save/load endpoints ──────────────────────────────────────────────

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


# ── SOC proxy ─────────────────────────────────────────────────────────────────

@app.get("/soc/sections")
def soc_sections(
    subject: str = Query(..., description="Subject number, e.g. 198"),
    year: str = Query("2026"),
    term: str = Query("9"),
    campus: str = Query("NB"),
):
    """Proxy to Rutgers SOC API — returns sections for a subject with open/closed status."""
    sections = fetch_sections_for_subject(subject, year, term, campus)
    return sections


# ── Course Sniper endpoints ────────────────────────────────────────────────────

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
