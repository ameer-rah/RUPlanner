from contextlib import asynccontextmanager
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .database import engine, Base, SessionLocal
from . import models  # noqa: F401 — registers all models so create_all sees them
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
    "bachelor_bs": "BS",
    "bachelor_ba": "BA",
    "minor": "Minor",
    "master": "MS",
    "associate": "AS",
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
