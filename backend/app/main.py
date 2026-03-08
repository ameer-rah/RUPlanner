from contextlib import asynccontextmanager
import re
from typing import List

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

from .database import engine, Base, SessionLocal
from . import models
from .schemas import PlanRequest, PlanResponse, ProgramInfo, CourseSearchResult
from .core.planner import heuristic_plan


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="RU Planner API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_LEVEL_LABEL = {
    "bachelor_bs":   "BS",
    "bachelor_ba":   "BA",
    "bachelor_bfa":  "BFA",
    "bachelor_bm":   "BM",
    "bachelor_bsba": "BSBA",
    "concentration": "Concentration",
    "minor":         "Minor",
    "master":        "MS",
    "associate":     "AS",
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
