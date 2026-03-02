#!/usr/bin/env python3
"""
Rutgers SIS course ingestion script.

Pulls every undergraduate course offered at New Brunswick from the
Rutgers Schedule of Classes API and upserts it into the local database.

Usage (run from backend/):
    python -m management.ingest_courses
    python -m management.ingest_courses --year 2026
    python -m management.ingest_courses --year 2026 --terms fall spring
"""
import argparse
import sys
from pathlib import Path

# Allow running from backend/ without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests
from sqlalchemy.orm import Session

from app.database import engine, SessionLocal, Base
from app.models import Course

# ---------------------------------------------------------------------------
# Rutgers Schedule of Classes API
# Term codes: 1=Spring, 7=Summer, 9=Fall
# ---------------------------------------------------------------------------
SIS_BASE = "https://sis.rutgers.edu/soc/api/courses.json"
CAMPUS = "NB"
LEVEL = "U"  # Undergraduate

TERM_CODES = {
    "spring": "1",
    "summer": "7",
    "fall":   "9",
}

# Map Rutgers SIS subject codes → human-readable course prefix.
# Add more as you expand to other schools.
SUBJECT_TO_PREFIX: dict[str, str] = {
    # SAS — Science
    "198": "CS",
    "640": "MATH",
    "960": "STAT",
    "750": "PHYS",
    "160": "CHEM",
    "694": "MCB",       # Molecular Biology & Biochemistry (was MOLBIO)
    "119": "BIO",       # General Biology sequence (intro courses)
    "146": "CBN",       # Cell Biology and Neuroscience
    "460": "GEOSC",     # Earth and Planetary Sciences
    "447": "GENET",     # Genetics
    "377": "EXSC",      # Exercise Science / Kinesiology & Health
    "832": "PUBH",      # Public Health (Bloustein)
    "762": "UPD",       # Urban Planning & Design (Bloustein)
    # SAS — Humanities & Social Sciences
    "730": "PHIL",
    "920": "SOC",       # Sociology (was wrongly PSYC)
    "830": "PSYC",      # Psychology
    "790": "POLS",
    "220": "ECON",
    "202": "CRIM",      # Criminal Justice
    "082": "ARTH",      # Art History
    "085": "ART",       # Studio Art / Visual Arts
    "615": "LING",      # Linguistics
    "450": "GEOG",
    "988": "WGSS",      # Women's and Gender Studies
    "512": "HIST",
    "506": "MUS",       # Music
    "965": "THEA",      # Theater Arts
    "706": "DANC",      # Dance
    "175": "CINE",      # Cinema Studies
    "840": "RELGS",     # Religion
    "070": "ANTH",      # Anthropology
    "195": "COMPLIT",   # Comparative Literature
    "350": "JOUR",      # Journalism & Media Studies
    "547": "ITI",       # Information Technology & Informatics (SC&I)
    "420": "FREN",      # French
    "470": "GERM",      # German
    "560": "ITAL",      # Italian
    "565": "JPN",       # Japanese
    "563": "CHN",       # Chinese
    "574": "KOR",       # Korean
    "860": "RUSS",      # Russian
    "490": "PORT",      # Portuguese
    "925": "SPAN",      # Spanish
    "535": "AMST",      # American Studies
    "016": "AFRS",      # Africana Studies
    "534": "LER",       # Labor Studies & Employment Relations (SMLR)
    "356": "SOCW",      # Social Work
    # Engineering — SOE core departments
    "440": "ENG",       # General Engineering / ID3EA / Packaging (SOE)
    "125": "BME",       # Biomedical Engineering
    "180": "CEE",       # Civil & Environmental Engineering
    "540": "ISE",       # Industrial & Systems Engineering
    "332": "ECE",       # Electrical & Computer Engineering
    "650": "MAE",       # Mechanical & Aerospace Engineering
    "155": "CHE",       # Chemical & Biochemical Engineering
    "635": "MSE",       # Materials Science & Engineering
    # Engineering — cross-school
    "117": "ENVE",      # Environmental Engineering (11:117)
    "375": "ENVSCI",    # Environmental Science (11:375)
    # Writing / Composition
    "355": "EXPOS",     # Expository Writing / Technical Writing
    # Business
    "010": "ACCT",
    "799": "SCM",       # Supply Chain Management (33:799)
    "390": "FIN",
    "620": "MKTG",
    "136": "BAIT",
}


def fetch_term(year: int, term_name: str) -> list[dict]:
    """Fetch all courses for one term from the SIS API."""
    code = TERM_CODES[term_name]
    params = {"year": year, "term": code, "campus": CAMPUS, "level": LEVEL}
    try:
        resp = requests.get(SIS_BASE, params=params, timeout=30)
        resp.raise_for_status()
        courses = resp.json()
        print(f"  {term_name.capitalize()} {year}: {len(courses)} courses returned by API")
        return courses
    except requests.RequestException as exc:
        print(f"  Warning: could not fetch {term_name} {year}: {exc}")
        return []


def parse_credits(raw_course: dict) -> int:
    """Extract an integer credit value from the SIS course object."""
    for field in ("credits", "creditHours", "credit"):
        val = raw_course.get(field)
        if val is not None:
            try:
                # Handle ranges like "3-4" — take the lower bound.
                return int(str(val).split("-")[0].strip())
            except (ValueError, AttributeError):
                continue
    return 3  # safe default


def upsert_courses(db: Session, raw_courses: list[dict], term_name: str) -> int:
    """Upsert a list of raw SIS course objects into the DB. Returns count of new rows."""
    is_spring = term_name == "spring"
    is_summer = term_name == "summer"
    is_fall   = term_name == "fall"

    # Deduplicate within this batch first (API returns one entry per section).
    seen_this_batch: dict[str, dict] = {}
    for raw in raw_courses:
        subject = raw.get("subject", "")
        prefix = SUBJECT_TO_PREFIX.get(subject)
        if not prefix:
            continue

        number_raw = raw.get("courseNumber", "")
        number = number_raw.lstrip("0") or number_raw
        code = f"{prefix}{number}"
        title = (raw.get("title") or "").strip()
        if not code or not title:
            continue

        if code not in seen_this_batch:
            seen_this_batch[code] = {
                "code": code,
                "title": title,
                "credits": parse_credits(raw),
                "subject_code": subject,
                "course_number": number_raw,
            }

    upserted = 0
    for code, info in seen_this_batch.items():
        existing: Course | None = db.get(Course, code)
        if existing:
            existing.title = info["title"]
            existing.credits = info["credits"]
            existing.spring_offered = existing.spring_offered or is_spring
            existing.summer_offered = existing.summer_offered or is_summer
            existing.fall_offered   = existing.fall_offered   or is_fall
        else:
            db.add(Course(
                code=code,
                title=info["title"],
                credits=info["credits"],
                subject_code=info["subject_code"],
                course_number=info["course_number"],
                spring_offered=is_spring,
                summer_offered=is_summer,
                fall_offered=is_fall,
            ))
            upserted += 1

    return upserted


def ingest(year: int, terms: list[str]) -> None:
    # Ensure tables exist.
    Base.metadata.create_all(bind=engine)

    db: Session = SessionLocal()
    total = 0
    try:
        for term_name in terms:
            raw_courses = fetch_term(year, term_name)
            if not raw_courses:
                continue
            count = upsert_courses(db, raw_courses, term_name)
            db.commit()
            total += count
            print(f"  → {count} new courses written for {term_name.capitalize()} {year}")
    finally:
        db.close()

    db2: Session = SessionLocal()
    try:
        total_in_db = db2.query(Course).count()
    finally:
        db2.close()

    print(f"\nDone. {total} new courses added this run. {total_in_db} total courses in DB.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest Rutgers SIS course data into the local database."
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2026,
        help="Academic year to fetch (default: 2026)",
    )
    parser.add_argument(
        "--terms",
        nargs="+",
        choices=["spring", "summer", "fall"],
        default=["spring", "summer", "fall"],
        help="Which terms to fetch (default: all three)",
    )
    args = parser.parse_args()

    print(f"Ingesting courses for {args.year}: {', '.join(args.terms)}")
    ingest(year=args.year, terms=args.terms)


if __name__ == "__main__":
    main()
