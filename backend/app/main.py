from contextlib import asynccontextmanager
import asyncio
import logging
import os
import re
from dotenv import load_dotenv

load_dotenv()
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import bcrypt
import requests as _requests
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from apscheduler.schedulers.background import BackgroundScheduler
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

from .database import engine, Base, SessionLocal
from . import models
from .schemas import (
    PlanRequest, PlanResponse, ProgramInfo, CourseSearchResult,
    UserCreate, Token, SaveScheduleRequest, GoogleAuthRequest,
    SnipeCreate, SnipeOut,
    ForgotPasswordRequest, ResetPasswordRequest,
    TranscriptResult, CourseDetail,
)
from .core.planner import heuristic_plan
from .core.sniper import poll_snipes, fetch_sections_for_subject

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from management.ingest_courses import ingest, current_terms

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    import sys
    print("ERROR: SECRET_KEY environment variable must be set", file=sys.stderr)
    sys.exit(1)
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")
if not ADMIN_TOKEN:
    import sys
    print("ERROR: ADMIN_TOKEN environment variable must be set", file=sys.stderr)
    sys.exit(1)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

_BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "12"))

def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(_BCRYPT_ROUNDS)).decode()

def _verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

def _validate_password_strength(password: str) -> str | None:
    if len(password) < 12:
        return "Password must be at least 12 characters long."
    if not re.search(r"[a-z]", password):
        return "Password must contain lowercase letters."
    if not re.search(r"[A-Z]", password):
        return "Password must contain uppercase letters."
    if not re.search(r"\d", password):
        return "Password must contain numbers."
    if not re.search(r"[!@#$%^&*\-_=+]", password):
        return "Password must contain special characters (!@#$%^&*-_=+)."
    return None

# Phone number encryption for sniper feature
_PHONE_ENCRYPTION_KEY = os.getenv("PHONE_ENCRYPTION_KEY")
_phone_cipher = None
if _PHONE_ENCRYPTION_KEY:
    try:
        _phone_cipher = Fernet(_PHONE_ENCRYPTION_KEY.encode())
    except Exception:
        logger.warning("Invalid PHONE_ENCRYPTION_KEY; phone numbers will be stored unencrypted")

def _encrypt_phone(phone: str) -> str:
    if not _phone_cipher:
        return phone
    try:
        return _phone_cipher.encrypt(phone.encode()).decode()
    except Exception as exc:
        logger.error("Phone encryption failed: %s", exc)
        return phone

def _decrypt_phone(encrypted: str) -> str:
    if not _phone_cipher:
        return encrypted
    try:
        return _phone_cipher.decrypt(encrypted.encode()).decode()
    except Exception as exc:
        logger.error("Phone decryption failed: %s", exc)
        return encrypted

_bearer = HTTPBearer()
_scheduler = BackgroundScheduler()
_limiter = Limiter(key_func=get_remote_address)

def _run_course_ingest() -> None:
    """Run course ingestion for the current academic terms."""
    year, terms = current_terms()
    print(f"[course-ingest] Fetching {terms} {year}...")
    ingest(year=year, terms=terms)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    _scheduler.add_job(poll_snipes, "interval", minutes=2, id="snipe_poll")
    _scheduler.add_job(_run_course_ingest, "interval", hours=24, id="course_ingest")
    _scheduler.start()
    # Run once at startup so the DB is always fresh on boot.
    _run_course_ingest()
    yield
    _scheduler.shutdown(wait=False)

app = FastAPI(title="RU Planner API", lifespan=lifespan)
app.state.limiter = _limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_ALLOWED_ORIGINS = list({
    o.strip().rstrip("/")
    for o in os.getenv("ALLOWED_ORIGINS", FRONTEND_URL).split(",")
    if o.strip()
})

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(Exception)
async def _global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error("Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "An internal error occurred. Please try again."})


def _create_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)

def _get_current_user_id(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
) -> int:
    token = credentials.credentials if credentials else request.cookies.get("ru_planner_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return int(user_id)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


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
                tracks=list((r.requirements or {}).get("tracks", {}).keys()),
            )
            for r in rows
        ]
    finally:
        db.close()

@app.get("/courses", response_model=List[CourseSearchResult])
@_limiter.limit("20/minute")
def search_courses(request: Request, q: str = Query("", max_length=100), limit: int = Query(20, ge=1, le=100)) -> List[CourseSearchResult]:
    if not q:
        return []
    if not re.match(r"^[a-zA-Z0-9\s\-:]+$", q):
        raise HTTPException(status_code=400, detail="Invalid search query")
    db = SessionLocal()
    try:
        pattern = f"{q}%"
        rows = (
            db.query(models.Course)
            .filter(
                models.Course.code.ilike(pattern)
                | models.Course.title.ilike(f"%{q}%")
                | models.Course.raw_code.ilike(f"%{q}%")
            )
            .order_by(models.Course.code)
            .limit(limit)
            .all()
        )
        return [
            CourseSearchResult(code=r.code, title=r.title, credits=r.credits, raw_code=r.raw_code)
            for r in rows
        ]
    finally:
        db.close()


@app.get("/courses/resolve")
@_limiter.limit("30/minute")
def resolve_course(request: Request, q: str = Query(..., max_length=50)) -> CourseSearchResult:
    """Resolve either a raw Rutgers code (01:198:111) or short code (CS111) to the full course record."""
    if not re.match(r"^[a-zA-Z0-9:]+$", q):
        raise HTTPException(status_code=400, detail="Invalid code format")
    db = SessionLocal()
    try:
        if re.match(r"^\d{2}:\d{3}:\d{3,4}$", q):
            course = db.query(models.Course).filter(models.Course.raw_code == q).first()
        else:
            course = db.query(models.Course).filter(models.Course.code == q.upper()).first()
        if not course:
            raise HTTPException(status_code=404, detail=f"Course not found: {q}")
        return CourseSearchResult(code=course.code, title=course.title, credits=course.credits, raw_code=course.raw_code)
    finally:
        db.close()

@app.post("/plan", response_model=PlanResponse)
@_limiter.limit("10/minute")
async def generate_plan(
    request: Request,
    payload: PlanRequest,
    user_id: int = Depends(_get_current_user_id),
) -> PlanResponse:
    try:
        loop = asyncio.get_event_loop()
        return await asyncio.wait_for(
            loop.run_in_executor(None, heuristic_plan, payload),
            timeout=30.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Plan generation timed out.")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

_MAX_PDF_BYTES = 5 * 1024 * 1024   # 5 MB
_MAX_PDF_PAGES = 20

_TRANSCRIPT_PROMPT = """You are analyzing a Rutgers University transcript PDF.

Extract every course listed and return ONLY a valid JSON object in exactly this shape — no prose, no markdown fences:

{
  "student_name": "Full Name Here",
  "ai_summary": "2-3 sentence plain-English summary of the student's academic history including total credits, any failed courses, transfer credits, and current enrollment status.",
  "courses": [
    {
      "title_raw": "INTRO COMPUTER SCI",
      "raw_code": "01:198:111",
      "rutgers_code": "CS111",
      "grade": "A+",
      "passed": true,
      "failed": false,
      "is_transfer": false,
      "is_in_progress": false,
      "semester": "Fall 2023",
      "credits": 4.0,
      "equivalency_note": ""
    }
  ]
}

Rules for each course field:
- title_raw: course title exactly as it appears on the transcript
- raw_code: the full Rutgers subject code exactly as it appears on the transcript in XX:YYY:ZZZ format (e.g. "01:198:111"). Use null if not visible on the transcript.
- rutgers_code: the standard short course code derived from raw_code (e.g. CS111, MATH151, EXPOS101, PHYS204). For transfer courses, infer the best Rutgers equivalent based on title and credit count. Use null if no confident match exists.
- grade: exactly as printed (A+, B, C-, F, W, TR, PA, etc.). Use empty string "" for in-progress courses with no grade yet.
- passed: true if grade is any passing variant (A/B/C/D/P/TR/PA/TE/TC and their +/- forms)
- failed: true if grade is F, W, WF, WD, NC, U, UF, NR, WN — and the course is NOT in-progress
- is_transfer: true for any course appearing in a TRANSFER COURSES block
- is_in_progress: true when there is no grade listed yet (student currently enrolled)
- semester: e.g. "Fall 2023", "Spring 2024", "Transfer" for transfer block courses with no term
- credits: numeric credit value as a float
- equivalency_note: non-empty only for transfer courses — one sentence explaining why this Rutgers code is the best match. Leave empty string "" for non-transfer courses.

Return ONLY the JSON object. No other text."""


@app.post("/parse-transcript", response_model=TranscriptResult)
@_limiter.limit("5/minute")
async def parse_transcript(request: Request, file: UploadFile = File(...)) -> TranscriptResult:
    import base64
    import json as _json
    import anthropic as _anthropic

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")
    if file.content_type and file.content_type not in ("application/pdf", "application/octet-stream"):
        raise HTTPException(status_code=400, detail="Invalid file type. Only PDF accepted.")

    content = await file.read()
    if len(content) > _MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail=f"File too large (max {_MAX_PDF_BYTES // 1024 // 1024} MB).")

    try:
        from pypdf import PdfReader
        import io as _io2
        reader = PdfReader(_io2.BytesIO(content))
        if len(reader.pages) > _MAX_PDF_PAGES:
            raise HTTPException(status_code=400, detail=f"PDF too long (max {_MAX_PDF_PAGES} pages).")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or corrupted PDF file.")

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Transcript AI is not configured.")

    pdf_b64 = base64.standard_b64encode(content).decode()
    client = _anthropic.AsyncAnthropic(api_key=api_key)

    try:
        msg = await asyncio.wait_for(
            client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_b64,
                            },
                        },
                        {"type": "text", "text": _TRANSCRIPT_PROMPT},
                    ],
                }],
            ),
            timeout=45.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Transcript analysis timed out.")
    except _anthropic.APIError as exc:
        raise HTTPException(status_code=502, detail=f"AI service error: {exc}")

    raw = msg.content[0].text.strip()
    # Extract the JSON object regardless of preamble text or markdown fences.
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1:
        raw = raw[start:end + 1]

    try:
        data = _json.loads(raw)
    except _json.JSONDecodeError:
        logger.error("Transcript parse: Claude returned non-JSON: %s", raw[:500])
        raise HTTPException(status_code=502, detail="AI returned an unreadable response. Please try again.")

    # Build CourseDetail list; resolve raw_code → rutgers_code via DB when Claude couldn't.
    _db_resolve = SessionLocal()
    try:
        courses_detail: List[CourseDetail] = []
        for c in data.get("courses", []):
            rutgers_code = c.get("rutgers_code") or None
            raw_code_val = c.get("raw_code") or None
            if raw_code_val and not rutgers_code:
                import re as _re
                if _re.match(r"^\d{2}:\d{3}:\d{3,4}$", raw_code_val):
                    db_course = _db_resolve.query(models.Course).filter(
                        models.Course.raw_code == raw_code_val
                    ).first()
                    if db_course:
                        rutgers_code = db_course.code
            courses_detail.append(CourseDetail(
                title_raw=c.get("title_raw", ""),
                raw_code=raw_code_val,
                rutgers_code=rutgers_code,
                grade=c.get("grade", ""),
                passed=bool(c.get("passed", False)),
                failed=bool(c.get("failed", False)),
                is_transfer=bool(c.get("is_transfer", False)),
                is_in_progress=bool(c.get("is_in_progress", False)),
                semester=c.get("semester", ""),
                credits=float(c.get("credits", 0)),
                equivalency_note=c.get("equivalency_note", ""),
            ))
    finally:
        _db_resolve.close()

    seen: set = set()
    matched: List[str] = []
    in_progress: List[str] = []
    inferred: dict = {}

    for c in courses_detail:
        if not c.rutgers_code:
            continue
        if c.is_in_progress:
            if c.rutgers_code not in seen:
                seen.add(c.rutgers_code)
                in_progress.append(c.rutgers_code)
        elif c.passed:
            if c.is_transfer:
                inferred[c.rutgers_code] = f"Transfer: {c.title_raw}"
            if c.rutgers_code not in seen:
                seen.add(c.rutgers_code)
                matched.append(c.rutgers_code)

    return TranscriptResult(
        matched=matched,
        in_progress=in_progress,
        inferred=inferred,
        courses_detail=courses_detail,
        ai_summary=data.get("ai_summary", ""),
        student_name=data.get("student_name", ""),
    )

@app.post("/auth/register", response_model=Token)
@_limiter.limit("3/minute")
def register(request: Request, payload: UserCreate, response: Response) -> Token:
    db = SessionLocal()
    try:
        strength_error = _validate_password_strength(payload.password)
        if strength_error:
            raise HTTPException(status_code=400, detail=strength_error)
        if db.query(models.User).filter(models.User.email == payload.email).first():
            raise HTTPException(status_code=400, detail="Email already registered")
        user = models.User(email=payload.email, hashed_password=_hash_password(payload.password))
        db.add(user)
        db.commit()
        db.refresh(user)
        token = _create_token(user.id)
        response.set_cookie(
            key="ru_planner_token",
            value=token,
            httponly=True,
            secure=True,
            samesite="none",
            max_age=7 * 24 * 60 * 60
        )
        return Token(access_token=token, token_type="bearer")
    finally:
        db.close()

@app.post("/auth/login", response_model=Token)
@_limiter.limit("5/minute")
def login(request: Request, payload: UserCreate, response: Response) -> Token:
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == payload.email).first()
        if not user or not user.hashed_password or not _verify_password(payload.password, user.hashed_password):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        token = _create_token(user.id)
        response.set_cookie(
            key="ru_planner_token",
            value=token,
            httponly=True,
            secure=True,
            samesite="none",
            max_age=7 * 24 * 60 * 60
        )
        return Token(access_token=token, token_type="bearer")
    finally:
        db.close()

@app.post("/auth/google", response_model=Token)
@_limiter.limit("5/minute")
def google_auth(request: Request, payload: GoogleAuthRequest, response: Response) -> Token:
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
        token = _create_token(user.id)
        response.set_cookie(
            key="ru_planner_token",
            value=token,
            httponly=True,
            secure=True,
            samesite="none",
            max_age=7 * 24 * 60 * 60
        )
        return Token(access_token=token, token_type="bearer")
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

@app.post("/auth/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(key="ru_planner_token", httponly=True, secure=True, samesite="none")
    return {"status": "ok"}


@app.post("/auth/forgot-password", status_code=200)
@_limiter.limit("3/minute")
def forgot_password(request: Request, payload: ForgotPasswordRequest):
    import secrets
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == payload.email).first()
        import hashlib
        logger.info(
            "Password reset requested for email_hash=%s from ip=%s",
            hashlib.sha256(payload.email.lower().encode()).hexdigest()[:12],
            request.client.host if request.client else "unknown",
        )
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
            logger.info("Password reset email sent for user_id=%s", user.id)
        return {"message": "If that email is registered, a reset link has been sent."}
    finally:
        db.close()


@app.post("/auth/reset-password", status_code=200)
def reset_password(payload: ResetPasswordRequest):
    strength_error = _validate_password_strength(payload.new_password)
    if strength_error:
        raise HTTPException(status_code=400, detail=strength_error)
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
        user = db.query(models.User).filter(models.User.id == reset_token.user_id).first()
        user.hashed_password = _hash_password(payload.new_password)
        reset_token.used = True
        db.commit()
        logger.info("Password reset completed for user_id=%s", user.id)
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
@_limiter.limit("10/minute")
def rmp_rating(request: Request, name: str = Query(..., max_length=100)):
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

@app.get("/soc/section-by-index")
@_limiter.limit("20/minute")
def soc_section_by_index(
    request: Request,
    index: str = Query(..., min_length=1, max_length=10, pattern=r"^\d+$"),
    year: str = Query(..., pattern=r"^\d{4}$"),
    term: str = Query(..., pattern=r"^\d$"),
    campus: str = Query("NB", pattern=r"^[A-Z]{2,3}$"),
):
    url = f"https://sis.rutgers.edu/soc/api/courses.json?year={year}&term={term}&campus={campus}&level=U"
    try:
        resp = _requests.get(url, timeout=15)
        resp.raise_for_status()
        courses = resp.json()
    except Exception:
        raise HTTPException(status_code=502, detail="Could not reach Rutgers SOC API.")
    for course in courses:
        for sec in course.get("sections", []):
            if str(sec.get("index", "")) == index:
                subject = str(course.get("subject", "")).zfill(3)
                prefix = _RUTGERS_DEPT_TO_PREFIX.get(subject, subject)
                course_num = str(course.get("courseNumber", "")).lstrip("0") or "0"
                return {
                    "course_code": f"{prefix}{course_num}",
                    "course_title": course.get("expandedTitle") or course.get("title", ""),
                    "section_number": sec.get("number", ""),
                    "section_index": index,
                    "open_status": sec.get("openStatus", False),
                    "instructors": [i.get("name", "") for i in sec.get("instructors", [])],
                    "meeting_times": sec.get("meetingTimes", []),
                }
    raise HTTPException(status_code=404, detail="Section index not found for this term.")


@app.get("/soc/sections")
def soc_sections(
    subject: str = Query(...),
    year: str = Query("2026"),
    term: str = Query("9"),
    campus: str = Query("NB"),
    courseNumber: str = Query(None),
):
    sections = fetch_sections_for_subject(subject, year, term, campus)
    if courseNumber:
        sections = [s for s in sections if s["courseNumber"] == courseNumber]
    return sections

@app.post("/snipes", response_model=SnipeOut)
@_limiter.limit("10/minute")
def create_snipe(request: Request, payload: SnipeCreate, user_id: int = Depends(_get_current_user_id)):
    db = SessionLocal()
    try:
        encrypted_phone = _encrypt_phone(payload.phone_number)
        snipe = models.Snipe(
            user_id=user_id,
            course_code=payload.course_code,
            course_title=payload.course_title,
            section_index=payload.section_index,
            section_number=payload.section_number,
            year=payload.year,
            term=payload.term,
            campus=payload.campus,
            phone_number=encrypted_phone,
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

def _require_admin(credentials: HTTPAuthorizationCredentials = Depends(_bearer)) -> None:
    if not ADMIN_TOKEN or credentials.credentials != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")


@app.post("/admin/ingest-courses", dependencies=[Depends(_require_admin)])
def admin_ingest_courses():
    """Trigger an on-demand course data refresh from the Rutgers SIS API."""
    from .database import SessionLocal as _SL
    year, terms = current_terms()
    ingest(year=year, terms=terms)
    db = _SL()
    try:
        total = db.query(models.Course).count()
    finally:
        db.close()
    return {"year": year, "terms": terms, "total_in_db": total}


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
        phone_number=_decrypt_phone(s.phone_number),
        active=s.active,
        notified_at=s.notified_at.isoformat() if s.notified_at else None,
        created_at=s.created_at.isoformat(),
    )
