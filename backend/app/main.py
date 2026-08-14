from contextlib import asynccontextmanager
import asyncio
import logging
import os
import re
import threading
import time
from dotenv import load_dotenv

load_dotenv()
from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, UploadFile, File, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
import requests as _requests
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

from .database import engine, Base, SessionLocal
from . import models
from .schemas import (
    PlanRequest, PlanResponse, ProgramInfo, CourseSearchResult,
    Token, SaveScheduleRequest, GoogleAuthRequest,
    SnipeCreate, SnipeOut,
    TranscriptResult,
)
from .core.planner import heuristic_plan, _get_sas_core_index, invalidate_catalog_cache
from .core.transcript import (
    extract_deterministic_rows,
    latest_status_codes,
    merge_extracted_rows,
    normalize_extracted_courses,
)
from .core.sniper import fetch_sections_for_subject

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    import sys
    print("ERROR: SECRET_KEY environment variable must be set", file=sys.stderr)
    sys.exit(1)
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")

# Maps Rutgers subject numbers (3-digit zero-padded) to short course prefixes (e.g. "198" -> "CS")
_SUBJECT_TO_PREFIX: dict[str, str] = {
    "010": "ACCT", "007": "ACE", "016": "AFRS", "098": "AMES", "050": "AMST",
    "340": "ANSC", "070": "ANTH", "074": "ARAB", "080": "ARCH", "081": "ART",
    "082": "ARTH", "750": "PHYS", "115": "BCHEM", "119": "BIO", "137": "BIOTECH",
    "140": "BLAW", "125": "BME", "116": "BSYSE", "135": "BUSS", "148": "CBN",
    "180": "CEE", "155": "CHE", "160": "CHEM", "165": "CHN", "175": "CINE",
    "190": "CLAS", "185": "COGS", "192": "COMM", "195": "COMPLIT", "762": "CRP",
    "198": "CS", "214": "DANC", "216": "DISAB", "705": "NURS", "332": "ECE",
    "220": "ECON", "300": "EDUC", "355": "EXPOS", "350": "ENGL", "375": "ENVSCI",
    "370": "ENT", "885": "ESME", "572": "EXSC", "390": "FIN", "420": "FREN",
    "400": "FS", "447": "GENET", "450": "GEOG", "460": "GEOSC", "470": "GERM",
    "554": "IGS", "490": "GREK", "500": "HEBR", "504": "HINDI", "510": "HIST",
    "501": "HLAD", "507": "HIED", "545": "IRHR", "540": "ISE", "560": "ITAL",
    "194": "ITI", "563": "JWST", "567": "JOUR", "217": "JPN", "574": "KOR",
    "550": "LA", "590": "LAS", "595": "LAT", "600": "LCS", "615": "LING",
    "650": "MAE", "642": "MAP", "640": "MATH", "712": "MARINE", "695": "MCB",
    "663": "MCHM", "667": "MEDST", "625": "MES", "107": "METEOR", "681": "MICROB",
    "660": "MGMT", "630": "MKTG", "635": "MSE", "700": "MUS", "709": "NUTRSCI",
    "718": "PCOL", "726": "PERS", "720": "PHAR", "730": "PHIL", "761": "PHSL",
    "765": "PBIO", "790": "POLS", "810": "PORT", "830": "PSYC", "832": "PUBH",
    "840": "RELGS", "859": "RUSS", "799": "SCM", "920": "SOC", "910": "MSW",
    "940": "SPAN", "475": "SPMD", "960": "STAT", "965": "THEA", "976": "TURF",
    "975": "TURK", "988": "WGSS", "360": "EURO", "643": "GQF",
}

_SOC_COURSE_CACHE: dict[tuple[int, str], tuple[float, list[dict]]] = {}
_SOC_CACHE_LOCK = threading.Lock()
_SOC_CACHE_TTL_SECONDS = 15 * 60
_SOC_CACHE_MAX_TERMS = 8
_SOC_TERM_CODE = {"Winter": "0", "Spring": "1", "Summer": "7", "Fall": "9"}


def _soc_courses_for_term(year: int, season: str) -> list[dict]:
    """Return the official Rutgers NB undergraduate SOC payload for one term."""
    key = (year, season)
    now = time.monotonic()
    with _SOC_CACHE_LOCK:
        cached = _SOC_COURSE_CACHE.get(key)
        if cached and now - cached[0] < _SOC_CACHE_TTL_SECONDS:
            return cached[1]
    response = _requests.get(
        "https://sis.rutgers.edu/soc/api/courses.json",
        params={"year": year, "term": _SOC_TERM_CODE[season], "campus": "NB", "level": "U"},
        timeout=20,
    )
    response.raise_for_status()
    courses = response.json()
    with _SOC_CACHE_LOCK:
        expired = [
            cache_key for cache_key, (created_at, _) in _SOC_COURSE_CACHE.items()
            if now - created_at >= _SOC_CACHE_TTL_SECONDS
        ]
        for cache_key in expired:
            _SOC_COURSE_CACHE.pop(cache_key, None)
        if len(_SOC_COURSE_CACHE) >= _SOC_CACHE_MAX_TERMS:
            oldest = min(_SOC_COURSE_CACHE, key=lambda item: _SOC_COURSE_CACHE[item][0])
            _SOC_COURSE_CACHE.pop(oldest, None)
        _SOC_COURSE_CACHE[key] = (now, courses)
    return courses


def _soc_course_result(course: dict) -> CourseSearchResult:
    subject = str(course.get("subject", "")).zfill(3)
    number = str(course.get("courseNumber", "")).lstrip("0") or "0"
    prefix = _SUBJECT_TO_PREFIX.get(subject)
    core_tags = list(dict.fromkeys(
        item.get("code") or item.get("coreCode")
        for item in (course.get("coreCodes") or [])
        if item.get("code") or item.get("coreCode")
    ))
    unit = str(course.get("offeringUnitCode") or "01").zfill(2)
    raw_code = f"{unit}:{subject}:{str(course.get('courseNumber', '')).zfill(3)}"
    display_code = f"{prefix}{number}" if prefix else raw_code
    return CourseSearchResult(
        code=display_code,
        raw_code=raw_code,
        title=course.get("expandedTitle") or course.get("title") or display_code,
        credits=float(course.get("credits") or 0),
        core_tags=core_tags,
    )

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
_limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

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

_PROGRAM_CACHE: list = [0.0, []]
_PROGRAM_CACHE_TTL_SECONDS = 5 * 60
_PROGRAM_CACHE_LOCK = threading.Lock()

@app.get("/programs", response_model=List[ProgramInfo])
def list_programs() -> List[ProgramInfo]:
    now = time.monotonic()
    with _PROGRAM_CACHE_LOCK:
        if _PROGRAM_CACHE[1] and now - _PROGRAM_CACHE[0] < _PROGRAM_CACHE_TTL_SECONDS:
            return _PROGRAM_CACHE[1]
    db = SessionLocal()
    try:
        rows = (
            db.query(models.Program)
            .order_by(models.Program.school, models.Program.major_name, models.Program.degree_level)
            .all()
        )
        programs = [
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
                track_labels={
                    key: value.get("display_name", key.replace("_", " ").title())
                    for key, value in (r.requirements or {}).get("tracks", {}).items()
                },
                track_dimensions=(r.requirements or {}).get("track_dimensions", []),
            )
            for r in rows
        ]
        with _PROGRAM_CACHE_LOCK:
            _PROGRAM_CACHE[0] = now
            _PROGRAM_CACHE[1] = programs
        return programs
    finally:
        db.close()

@app.get("/courses", response_model=List[CourseSearchResult])
@_limiter.limit("20/minute")
def search_courses(
    request: Request,
    q: str = Query("", max_length=100),
    term: Optional[str] = Query(None, max_length=20),
    limit: int = Query(20, ge=1, le=100),
) -> List[CourseSearchResult]:
    if not q:
        return []
    if not re.match(r"^[a-zA-Z0-9\s\-:]+$", q):
        raise HTTPException(status_code=400, detail="Invalid search query")
    season = term.split()[0].capitalize() if term else None
    if season and season not in {"Spring", "Summer", "Fall", "Winter"}:
        raise HTTPException(status_code=400, detail="Invalid semester")

    core_index = _get_sas_core_index()

    if term:
        match = re.fullmatch(r"(Spring|Summer|Fall|Winter)\s+(\d{4})", term.strip(), re.IGNORECASE)
        if not match:
            raise HTTPException(status_code=400, detail="Semester must look like 'Fall 2026'")
        season = match.group(1).capitalize()
        year = int(match.group(2))
        try:
            official_courses = _soc_courses_for_term(year, season)
        except (_requests.RequestException, ValueError):
            raise HTTPException(status_code=502, detail="Rutgers Schedule of Classes is unavailable")
        needle = q.strip().lower()
        matches: list[CourseSearchResult] = []
        seen: set[str] = set()
        for course in official_courses:
            result = _soc_course_result(course)
            tag_match = any(tag.lower() == needle for tag in result.core_tags)
            text_match = (
                needle in result.code.lower()
                or needle in result.title.lower()
                or needle in (result.raw_code or "").lower()
            )
            if (tag_match or text_match) and result.raw_code not in seen:
                matches.append(result)
                seen.add(result.raw_code or result.code)
        return sorted(matches, key=lambda course: (course.code, course.raw_code or ""))[:limit]

    query_tag = next((tag for tags in core_index.values() for tag in tags if tag.lower() == q.strip().lower()), None)
    designation_codes = [code for code, tags in core_index.items() if query_tag in tags] if query_tag else []

    db = SessionLocal()
    try:
        course_query = db.query(models.Course)
        if designation_codes:
            course_query = course_query.filter(models.Course.code.in_(designation_codes))
        else:
            pattern = f"{q}%"
            course_query = course_query.filter(
                models.Course.code.ilike(pattern)
                | models.Course.title.ilike(f"%{q}%")
                | models.Course.raw_code.ilike(f"%{q}%")
            )
        season_column = {
            "Spring": models.Course.spring_offered,
            "Summer": models.Course.summer_offered,
            "Fall": models.Course.fall_offered,
        }.get(season)
        if season_column is not None:
            course_query = course_query.filter(season_column.is_(True))
        elif season == "Winter":
            return []
        rows = course_query.order_by(models.Course.code).limit(limit).all()
        return [
            CourseSearchResult(
                code=r.code,
                title=r.title,
                credits=r.credits,
                raw_code=r.raw_code,
                core_tags=core_index.get(r.code, []),
            )
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
            matches = db.query(models.Course).filter(models.Course.code == q.upper()).limit(2).all()
            if len(matches) > 1:
                raise HTTPException(
                    status_code=409,
                    detail=f"Course alias '{q.upper()}' is ambiguous; use the full Rutgers code.",
                )
            course = matches[0] if matches else None
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
    return await _generate_plan(payload, user_id)


@app.post("/dev/plan", response_model=PlanResponse, include_in_schema=False)
@_limiter.limit("60/minute")
async def generate_preview_plan(request: Request, payload: PlanRequest) -> PlanResponse:
    client_host = request.client.host if request.client else ""
    origin = request.headers.get("origin", "")
    loopback_hosts = {"127.0.0.1", "::1", "localhost", "testclient"}
    local_origin = origin in {"http://localhost:3000", "http://127.0.0.1:3000", ""}
    if client_host not in loopback_hosts or not local_origin:
        raise HTTPException(status_code=404, detail="Not found")
    return await _generate_plan(payload, None)


async def _generate_plan(payload: PlanRequest, user_id: Optional[int]) -> PlanResponse:
    try:
        loop = asyncio.get_running_loop()
        result = await asyncio.wait_for(
            loop.run_in_executor(None, heuristic_plan, payload),
            timeout=30.0,
        )
        if user_id is not None:
            db = SessionLocal()
            try:
                user = db.query(models.User).filter(models.User.id == user_id).first()
                if user:
                    user.onboarding_completed = True
                    user.planner_profile = payload.model_dump(mode="json")
                    user.last_plan = result.model_dump(mode="json")
                    db.commit()
            finally:
                db.close()
        return result
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Plan generation timed out.")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

_MAX_PDF_BYTES = 5 * 1024 * 1024   # 5 MB
_MAX_PDF_PAGES = 20

# Per-semester extraction prompt — focused and small so each call never truncates.
_CHUNK_EXTRACT_PROMPT = """Extract every course row from this Rutgers transcript section.
Return ONLY a valid JSON array — no prose, no markdown fences, nothing else.

Each element must follow this shape exactly:
{"title_raw":"INTRO COMPUTER SCI","raw_code":"01:198:111","rutgers_code":"CS111","grade":"A","passed":true,"failed":false,"is_transfer":false,"is_in_progress":false,"semester":"Fall 2023","credits":4.0,"equivalency_note":""}

Field rules:
- title_raw: course title exactly as printed
- raw_code: XX:YYY:ZZZ exactly as printed; null if not visible
- rutgers_code: short code derived from a Rutgers raw_code (01:198:111→CS111, 01:640:151→MATH151, 01:355:101→EXPOS101); null if uncertain
- Transfer courses: never guess a Rutgers equivalency from the title. Set rutgers_code only when a Rutgers equivalent is explicitly printed on the transcript; otherwise null.
- grade: exactly as printed; empty string "" if no grade yet (in-progress)
- Rutgers passing grades — passed=true: A A+ A- B B+ B- C C+ C- D D+ D- P PA TR TE TC S T EX
- Rutgers failing grades — failed=true: F WF WD U UF NC NR WN
- W (plain withdrawal): passed=false, failed=false, is_in_progress=false
- is_in_progress=true: grade is blank or missing
- is_transfer=true: if this section header says TRANSFER
- semester: use the section label (e.g. "Fall 2023"); "Transfer" for transfer blocks
- credits: numeric float
- equivalency_note: one sentence for transfer courses only; empty string "" for all others
- Include EVERY course row — do not skip any

Return ONLY the JSON array. No other text."""


def _split_transcript_by_term(pdf_text: str) -> list:
    """Return list of (section_label, section_text) pairs split by term headers."""
    pattern = re.compile(
        r'((?:Fall|Spring|Summer|Winter)\s+\d{4}|TRANSFER\s+(?:CREDIT\w*|WORK|COURSES?))',
        re.IGNORECASE,
    )
    parts = pattern.split(pdf_text)
    chunks = []
    preamble = parts[0].strip() if parts else ""
    if preamble and re.search(r"\d{2}\s*:\s*\d{3}\s*:\s*\d{3,4}", preamble):
        chunks.append(("Transcript Preamble", preamble))
    # parts alternates: preamble, header1, body1, header2, body2, ...
    for i in range(1, len(parts) - 1, 2):
        label = parts[i].strip()
        body = parts[i + 1] if i + 1 < len(parts) else ""
        if body.strip():
            chunks.append((label, f"{label}\n{body}"))
    # If no term headers found, process as one block so we always attempt extraction.
    return chunks or [("Full Transcript", pdf_text)]


async def _extract_chunk(client, section_label: str, section_text: str) -> list:
    """Call Claude Sonnet for one transcript section; return list of raw course dicts."""
    import json as _json
    import anthropic as _anthropic
    try:
        msg = await asyncio.wait_for(
            client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": f"{_CHUNK_EXTRACT_PROMPT}\n\nSection: {section_label}\n\n{section_text}",
                }],
            ),
            timeout=45.0,
        )
        raw = msg.content[0].text.strip()
        start = raw.find("[")
        end = raw.rfind("]")
        if start == -1 or end == -1:
            logger.warning("Transcript chunk '%s': no JSON array in response", section_label)
            return []
        parsed = _json.loads(raw[start:end + 1])
        return parsed if isinstance(parsed, list) else []
    except asyncio.TimeoutError:
        logger.warning("Transcript chunk '%s' timed out", section_label)
        return []
    except (_json.JSONDecodeError, _anthropic.APIError, Exception) as exc:
        logger.warning("Transcript chunk '%s' failed: %s", section_label, exc)
        return []


@app.post("/parse-transcript", response_model=TranscriptResult)
@_limiter.limit("5/minute")
async def parse_transcript(request: Request, file: UploadFile = File(...)) -> TranscriptResult:
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
        pypdf_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        pdf_text = pypdf_text
        # Positioned extraction frequently preserves Rutgers transcript columns
        # that pypdf flattens or interleaves. Prefer whichever representation
        # exposes more course codes, then more usable text.
        try:
            import pdfplumber
            with pdfplumber.open(_io2.BytesIO(content)) as document:
                plumber_text = "\n".join(
                    page.extract_text(layout=True) or "" for page in document.pages
                )
            raw_pattern = r"\d{2}\s*:\s*\d{3}\s*:\s*\d{3,4}"
            pypdf_score = (len(re.findall(raw_pattern, pypdf_text)), len(pypdf_text))
            plumber_score = (len(re.findall(raw_pattern, plumber_text)), len(plumber_text))
            if plumber_score > pypdf_score:
                pdf_text = plumber_text
        except Exception as exc:
            logger.info("pdfplumber transcript extraction unavailable: %s", exc)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid or corrupted PDF file.")

    if not pdf_text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from this PDF. Please ensure it is not a scanned image.")

    # Combine deterministic precision with AI recall. Previously, recognizing a
    # single local row disabled AI for the entire document and silently omitted
    # every row whose layout differed.
    deterministic_rows = extract_deterministic_rows(pdf_text)
    ai_rows: list = []
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        client = _anthropic.AsyncAnthropic(api_key=api_key)
        chunks = _split_transcript_by_term(pdf_text)
        chunk_results = await asyncio.gather(
            *[_extract_chunk(client, label, text) for label, text in chunks]
        )
        for result in chunk_results:
            ai_rows.extend(result)
    all_raw = merge_extracted_rows(deterministic_rows, ai_rows)

    if not all_raw:
        raise HTTPException(
            status_code=502,
            detail="Could not extract any course rows from this transcript. Please try another PDF export.",
        )

    # Treat model output as untrusted extraction.  Codes and status flags are
    # derived and validated locally before they can affect a student's plan.
    _db_resolve = SessionLocal()
    try:
        catalog_rows = _db_resolve.query(models.Course.raw_code, models.Course.code).all()
        raw_code_map = {raw: code for raw, code in catalog_rows if raw}
        known_codes = {code for _, code in catalog_rows}
        courses_detail = normalize_extracted_courses(all_raw, raw_code_map, known_codes)
    finally:
        _db_resolve.close()

    # Extract student name from the transcript preamble.
    name_match = re.search(
        r'(?:Name|Student)[:\s]+([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)+)',
        pdf_text[:600],
    )
    student_name = name_match.group(1) if name_match else ""

    # Build summary from extracted data — no extra API call needed.
    earned_credits = sum(c.credits for c in courses_detail if c.passed)
    n_passed = sum(1 for c in courses_detail if c.passed)
    n_failed = sum(1 for c in courses_detail if c.failed)
    n_transfer = sum(1 for c in courses_detail if c.is_transfer and c.passed)
    n_in_progress = sum(1 for c in courses_detail if c.is_in_progress)
    parts_summary = [f"{n_passed} courses passed ({earned_credits:.1f} earned credits)"]
    if n_failed:
        parts_summary.append(f"{n_failed} failed")
    if n_transfer:
        parts_summary.append(f"{n_transfer} transfer credits")
    if n_in_progress:
        parts_summary.append(f"{n_in_progress} currently in progress")
    ai_summary = f"Extracted {len(courses_detail)} total courses: {', '.join(parts_summary)}."

    matched, in_progress = latest_status_codes(courses_detail, canonical=True)
    inferred: dict = {}

    for c in courses_detail:
        if c.is_transfer and c.passed and c.rutgers_code:
            inferred[c.rutgers_code] = f"Transfer: {c.title_raw}"

    return TranscriptResult(
        matched=matched,
        in_progress=in_progress,
        inferred=inferred,
        courses_detail=courses_detail,
        ai_summary=ai_summary,
        student_name=student_name,
    )

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
        return {
            "id": user.id,
            "email": user.email,
            "onboarding_completed": user.onboarding_completed,
        }
    finally:
        db.close()


@app.get("/profile")
def get_profile(user_id: int = Depends(_get_current_user_id)):
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {
            "onboarding_completed": user.onboarding_completed,
            "planner_profile": user.planner_profile,
            "last_plan": user.last_plan,
        }
    finally:
        db.close()

@app.post("/auth/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(key="ru_planner_token", httponly=True, secure=True, samesite="none")
    return {"status": "ok"}


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
_rmp_cache: dict[str, tuple[float, dict | None]] = {}
_RMP_CACHE_TTL_SECONDS = 6 * 60 * 60
_RMP_CACHE_MAX_NAMES = 512
_RMP_CACHE_LOCK = threading.Lock()
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


def _cache_rmp(key: str, value: dict | None, created_at: float) -> None:
    with _RMP_CACHE_LOCK:
        expired = [
            name for name, (cached_at, _) in _rmp_cache.items()
            if created_at - cached_at >= _RMP_CACHE_TTL_SECONDS
        ]
        for name in expired:
            _rmp_cache.pop(name, None)
        if len(_rmp_cache) >= _RMP_CACHE_MAX_NAMES:
            oldest = min(_rmp_cache, key=lambda name: _rmp_cache[name][0])
            _rmp_cache.pop(oldest, None)
        _rmp_cache[key] = (created_at, value)

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
@_limiter.limit("60/minute")
def rmp_rating(request: Request, name: str = Query(..., max_length=100)):
    if "," in name:
        parts = [p.strip().title() for p in name.split(",", 1)]
        query_name = f"{parts[1]} {parts[0]}"
    else:
        query_name = name.strip().title()
    cache_key = query_name.lower()
    now = time.monotonic()
    with _RMP_CACHE_LOCK:
        cached = _rmp_cache.get(cache_key)
        if cached and now - cached[0] < _RMP_CACHE_TTL_SECONDS:
            return cached[1]
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
        _cache_rmp(cache_key, None, now)
        return None
    result = {
        "name": f"{node['firstName']} {node['lastName']}",
        "rating": node.get("avgRating"),
        "num_ratings": node.get("numRatings", 0),
        "difficulty": node.get("avgDifficulty"),
        "would_take_again": node.get("wouldTakeAgainPercent"),
        "legacy_id": node.get("legacyId"),
    }
    _cache_rmp(cache_key, result, now)
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
    base = f"https://sis.rutgers.edu/soc/api/courses.json?year={year}&term={term}&campus={campus}"
    try:
        from concurrent.futures import ThreadPoolExecutor
        def _fetch(url):
            r = _requests.get(url, timeout=12)
            r.raise_for_status()
            return r.json()
        with ThreadPoolExecutor(max_workers=2) as pool:
            fut_u = pool.submit(_fetch, f"{base}&level=U")
            fut_g = pool.submit(_fetch, f"{base}&level=G")
            courses_u = fut_u.result()
            courses_g = fut_g.result()
        courses = courses_u + courses_g
    except Exception:
        raise HTTPException(status_code=502, detail="Could not reach Rutgers SOC API.")
    for course in courses:
        for sec in course.get("sections", []):
            if str(sec.get("index", "")) == index:
                subject = str(course.get("subject", "")).zfill(3)
                prefix = _SUBJECT_TO_PREFIX.get(subject, subject)
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
    from management.ingest_courses import current_term_specs, ingest
    from .database import SessionLocal as _SL
    specs = current_term_specs()
    for year, term in specs:
        ingest(year=year, terms=[term])
    invalidate_catalog_cache()
    db = _SL()
    try:
        total = db.query(models.Course).count()
    finally:
        db.close()
    return {"terms": [{"year": year, "term": term} for year, term in specs], "total_in_db": total}


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
