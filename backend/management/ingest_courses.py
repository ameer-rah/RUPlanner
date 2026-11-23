#!/usr/bin/env python3
"""
Rutgers SIS course ingestion script.

Pulls the New Brunswick undergraduate and graduate schedule from the
Rutgers Schedule of Classes API and upserts it into the local database.

Usage (run from backend/):
    python -m management.ingest_courses
    python -m management.ingest_courses --year 2026
    python -m management.ingest_courses --year 2026 --terms fall spring
"""
import argparse
from datetime import date, datetime
import logging
import math
import re
import sys
from pathlib import Path

# Allow running from backend/ without installing the package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import requests
from sqlalchemy import delete, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import Course, CourseImport, CourseOffering, utc_now

# ---------------------------------------------------------------------------
# Rutgers Schedule of Classes API
# Term codes: 0=Winter, 1=Spring, 7=Summer, 9=Fall
# ---------------------------------------------------------------------------
SIS_BASE = "https://sis.rutgers.edu/soc/api/courses.json"
CAMPUS = "NB"
LEVELS = ("U", "G")
COURSE_CODE = re.compile(r"[0-9]{2}:[A-Z0-9]{3}:[A-Z0-9]{3}")
logger = logging.getLogger(__name__)

TERM_CODES = {
    "winter": "0",
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
    "762": "PPP",       # Planning and Public Policy (Bloustein — cross-listed)
    "775": "EJBSC",     # Bloustein School shared core (stats, methods, internship)
    "832": "PUBH",      # Public Health (Bloustein)
    "833": "PPOL",      # Public Policy (Bloustein)
    "170": "CRP",       # City and Regional Planning (Bloustein)
    "501": "HA",        # Health Administration (Bloustein)
    "971": "UPD",       # Urban Planning and Design (Bloustein)
    "843": "PADM",      # Public Administration and Management (Bloustein)
    "652": "MEHE",      # Medical Ethics and Health Policy (Bloustein)
    "975": "URST",      # Urban Studies (Bloustein)
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
    "206": "DANC",      # Dance performance/studio (Mason Gross, 07:206)
    "185": "COGS",      # Cognitive Science (01:185)
    "175": "CINE",      # Cinema Studies
    "840": "RELGS",     # Religion
    "070": "ANTH",      # Anthropology
    "195": "COMPLIT",   # Comparative Literature
    "350": "JOUR",      # Journalism & Media Studies (old subject code)
    # SC&I — School of Communication and Information (school code 04)
    "189": "SCI",       # SC&I interdisciplinary / shared courses (04:189)
    "192": "COMM",      # Communication (04:192)
    "547": "ITI",       # Information Technology & Informatics (SC&I, 04:547)
    "567": "JMS",       # Journalism and Media Studies (04:567)
    "420": "FREN",      # French
    "470": "GERM",      # German
    "560": "ITAL",      # Italian
    "565": "JPN",       # Japanese
    "563": "CHN",       # Chinese
    "574": "KOR",       # Korean
    "860": "RUSS",      # Russian
    "490": "PORT",      # Portuguese
    "940": "SPAN",      # Spanish
    "535": "AMST",      # American Studies
    "016": "AFRS",      # Africana Studies
    "534": "LER",       # Labor Studies & Employment Relations (SMLR, 37:575)
    "533": "HRM",       # Human Resource Management (SMLR, 37:533)
    "624": "LSER",      # SMLR shared management/org-behavior courses (37:624)
    "356": "SOCW",      # Social Work (legacy subject code)
    "910": "SW",        # Social Work — School of Social Work (SSW) undergraduate BA courses
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
    # Business — Rutgers Business School (RBS, school 33)
    "010": "ACCT",      # Accounting (33:010)
    "011": "PROF",      # Professional Development / Career Management (33:011)
    "136": "BAIT",      # Business Analytics and Information Technology (33:136)
    "140": "BLAW",      # Business Law (33:140)
    "382": "ENT",       # Entrepreneurship (33:382)
    "390": "FIN",       # Finance (33:390)
    "522": "BUSS",      # Business Ethics / General Business (33:522)
    "620": "MGMT",      # Management and Global Business (33:620)
    "630": "MKTG",      # Marketing (33:630)
    "799": "SCM",       # Supply Chain Management (33:799)
    "851": "RE",        # Real Estate (33:851)
    # Mason Gross School of the Arts (MGSA — school code 07)
    "203": "DSTU",      # Dance Studies (07:203)
    "211": "FILM",      # Filmmaking (07:211)
    "700": "MUSC",      # Music — academic/theory/history (07:700)
    "701": "MUSA",      # Music Applied — ensembles/private instruction (07:701)
    "966": "THTA",      # Theater Arts BFA — applied/studio courses (07:966)
    # SPPP / Bloustein — additional subjects
    "575": "DISA",      # Disability Studies (37:575, cross-listed SPPP minor)
    # SEBS — School of Environmental and Biological Sciences (school code 11)
    "067": "ANSC",      # Animal Science (11:067)
    "090": "AGECO",     # Agricultural, Food and Resource Economics (11:090)
    "100": "BIOTECH",   # Biotechnology (11:100)
    "050": "BSYSE",     # Biological and Agricultural Engineering (11:050)
    "370": "EENR",      # Ecology, Evolution, and Natural Resources (11:370)
    "373": "EPIB",      # Environmental Policy, Institutions, and Behavior (11:373)
    "400": "FS",        # Food Science (11:400)
    "430": "HUMEC",     # Human Ecology (11:430)
    "550": "LA",        # Landscape Architecture (11:550)
    # NOTE: "563" is Chinese (01:563) in SUBJECT_TO_PREFIX; Marine Sciences (11:563)
    # is handled via _UNIT_SUBJECT_OVERRIDE below.
    "670": "METEOR",    # Meteorology (11:670)
    "680": "MICROB",    # Microbiology (11:680)
    "709": "NUTRSCI",   # Nutritional Sciences (11:709)
    "776": "PBIO",      # Plant Biology (11:776)
    "780": "PLSC",      # Plant Science (11:780)
    "902": "TURF",      # Turfgrass Science (11:902)
    # GSE — Graduate School of Education (school code 15/16)
    "230": "EADM",      # Educational Administration and Supervision (15:230)
    "233": "ACE",       # Adult and Continuing Education (15:233)
    "245": "CSA",       # College Student Affairs (15:245)
    "250": "EDLT",      # Learning and Teaching — General (15:250)
    "251": "ECEE",      # Early Childhood/Elementary Education (15:251)
    "252": "ENGLA",     # English/Language Arts Education (15:252)
    "253": "LANE",      # Language Education / ESL / Bilingual (15:253)
    "254": "MAED",      # Mathematics Education (15:254)
    "255": "EDUC",      # Nondepartmental GSE / EdD Core (15:255)
    "256": "SCED",      # Science Education (15:256)
    "257": "SSED",      # Social Studies Education (15:257)
    "262": "DSLE",      # Design of Learning Environments (15:262)
    "267": "TLED",      # Teacher Leadership (15:267)
    "290": "EDPY",      # Educational Psychology (15:290)
    "291": "ESME",      # Educational Statistics, Measurement, and Evaluation (15:291)
    "293": "SPED",      # Special Education (15:293)
    "294": "GFED",      # Gifted Education (15:294)
    "295": "LCD",       # Learning, Cognition, and Development (15:295)
    "297": "CPSY",      # Counseling Psychology and School Counseling (15:297)
    "299": "READ",      # Reading / Literacy Education (15:299)
    "310": "SPFE",      # Social and Philosophical Foundations of Education (15:310)
    "300": "EDPD",      # PhD in Education graduate courses (16:300)
    "507": "HIED",      # PhD in Higher Education graduate courses (16:507)
    # SON — School of Nursing (school code 10)
    "678": "NURS",      # Nursing undergraduate courses (10:678)
    # EMSP — Ernest Mario School of Pharmacy (school code 30/31)
    "158": "PHBT",      # Pharmaceutical Biotechnology / Microbiology (30:158)
    "715": "PCHM",      # Pharmaceutical Chemistry (30:715)
    "718": "PHSL",      # Physiology / Pathophysiology / Pharmacology (30:718)
    "720": "PTHR",      # Pharmacotherapy (30:720)
    "721": "PHAR",      # Pharmaceutics / Drug Delivery / Biopharmaceutics (30:721)
    "725": "PHRC",      # Pharmacy Care / Practice / Clinical (30:725)
    "663": "MCHM",      # Medicinal Chemistry graduate program (31:663)
    "115": "BCHEM",     # Biochemistry graduate (31:115)
    # "560" intentionally omitted here — unit 31 override handles PCOL (see _UNIT_SUBJECT_OVERRIDE)
}

# Subject codes shared between multiple schools that need offering-unit disambiguation.
# When the SIS API returns offeringUnitCode == key and subject == inner key,
# override the SUBJECT_TO_PREFIX lookup with the mapped prefix.
# Format: { offeringUnitCode: { subject: prefix } }
_UNIT_SUBJECT_OVERRIDE: dict[str, dict[str, str]] = {
    "07": {
        "965": "THTR",   # Mason Gross Theater BA (07:965) — SAS uses same subject → THEA
    },
    "11": {
        "563": "MARINE", # Marine Sciences (11:563) — SAS/language uses same subject → CHN
    },
    "15": {
        "300": "EDPD",   # GSE PhD in Education courses (15:300) — disambiguate from SAS Education (05:300)
    },
    "16": {
        "300": "EDPD",   # GSE PhD graduate courses offered under unit 16
        "507": "HIED",   # PhD in Higher Education (16:507)
    },
    # EMSP graduate — Pharmacy grad (school code 31) uses subject 560 which conflicts with ITAL (01:560)
    "31": {
        "560": "PCOL",   # Pharmacology graduate (31:560) — unit 01 uses same subject for Italian
    },
    # GSAPP — Graduate School of Applied and Professional Psychology (school code 18)
    # Subject codes 820, 821, 826, 829, 844 are shared with other offering units
    # (e.g. 820 is also used by SAS Middle East/African language departments under unit 01),
    # so we must restrict mapping to offeringUnitCode "18" only.
    "18": {
        "820": "PPSY",   # Professional Psychology — core/shared GSAPP courses (18:820)
        "821": "CLPSY",  # Clinical Psychology (18:821)
        "826": "SPSY",   # School Psychology (18:826)
        "829": "OPSY",   # Organizational Psychology (18:829)
        "844": "MAP",    # Master of Applied Psychology (18:844)
    },
}


def current_term_specs(today: date | None = None) -> list[tuple[int, str]]:
    """Refresh the active term, its predecessor, and the next two candidates."""
    today = today or date.today()
    year = today.year
    if today.month <= 5:
        return [(year, "winter"), (year, "spring"), (year, "summer"), (year, "fall")]
    if today.month <= 7:
        return [(year, "spring"), (year, "summer"), (year, "fall"), (year + 1, "winter")]
    return [(year, "summer"), (year, "fall"), (year + 1, "winter"), (year + 1, "spring")]


def fetch_term(year: int, term_name: str) -> list[dict]:
    """Fetch and validate the entire New Brunswick response before writing it."""
    response = requests.get(
        SIS_BASE,
        params={"year": year, "term": TERM_CODES[term_name], "campus": CAMPUS},
        timeout=30,
    )
    response.raise_for_status()
    courses = response.json()
    if not isinstance(courses, list):
        raise ValueError("Expected Rutgers to return a list of courses")
    for course in courses:
        if not isinstance(course, dict):
            raise ValueError("Unexpected Rutgers course record")
        raw_code = course.get("courseString")
        title = course.get("title")
        if (
            not isinstance(raw_code, str)
            or not COURSE_CODE.fullmatch(raw_code)
            or not isinstance(title, str)
            or not title.strip()
            or len(title.strip()) > 255
            or course.get("level") not in LEVELS
            or course.get("mainCampus") != CAMPUS
        ):
            raise ValueError(f"Invalid New Brunswick course record: {raw_code!r}")
    return courses


def parse_credits(raw_course: dict) -> float:
    """Extract the minimum numeric credit value without inventing missing data.

    Args:
        raw_course: Raw SIS course object with one of the known credit fields.

    Returns:
        Parsed credits, using the lower bound for ranges, or ``0.0`` if unknown.
    """
    for field in ("credits", "creditHours", "credit"):
        val = raw_course.get(field)
        if val is not None:
            try:
                # Handle ranges like "3-4" — take the lower bound.
                credits = float(str(val).split("-")[0].strip())
                if math.isfinite(credits) and credits >= 0:
                    return credits
            except (ValueError, AttributeError):
                continue
    return 0.0  # unknown; never invent credits


def normalize_courses(raw_courses: list[dict], term_name: str) -> dict[str, dict]:
    """Use Rutgers identity for every course, including unfamiliar subjects."""
    rows: dict[str, dict] = {}
    for raw in raw_courses:
        raw_code = raw["courseString"]
        offering_unit, subject, number_raw = raw_code.split(":")
        unit_overrides = _UNIT_SUBJECT_OVERRIDE.get(offering_unit, {})
        prefix = unit_overrides.get(subject) or SUBJECT_TO_PREFIX.get(subject)
        number = number_raw.lstrip("0") or number_raw
        rows.setdefault(raw_code, {
            "code": f"{prefix}{number}" if prefix else raw_code,
            "title": raw["title"].strip(),
            "credits": parse_credits(raw),
            "subject_code": subject,
            "course_number": number_raw,
            "offering_unit_code": offering_unit,
            "raw_code": raw_code,
            "spring_offered": term_name == "spring",
            "summer_offered": term_name == "summer",
            "fall_offered": term_name == "fall",
        })
    return rows


def publish_snapshot(
    db: Session, year: int, term: str, level: str, courses: dict[str, dict], fetched_at: datetime,
    term_has_courses: bool,
) -> str:
    """Publish course metadata and term membership together in one transaction."""
    postgres = db.get_bind().dialect.name == "postgresql"
    if postgres:
        # Serialize worker and on-demand writers, including the first refresh.
        db.execute(text("SELECT pg_advisory_xact_lock(82750621)"))
    key = (year, term, level)
    previous = db.get(CourseImport, key)
    if previous and previous.synced_at > fetched_at:
        return "superseded"
    if not term_has_courses:
        if previous:
            raise ValueError("Unexpected empty feed for a previously published term")
        return "unpublished"
    if previous and len(courses) < previous.course_count * 0.75:
        raise ValueError(f"Course count dropped from {previous.course_count} to {len(courses)}")

    insert = pg_insert if postgres else sqlite_insert
    rows = [courses[code] for code in sorted(courses)]
    for offset in range(0, len(rows), 500):
        batch = rows[offset:offset + 500]
        statement = insert(Course).values(batch)
        db.execute(statement.on_conflict_do_update(
            index_elements=["raw_code"],
            set_={
                "title": statement.excluded.title,
                "credits": statement.excluded.credits,
                "spring_offered": Course.spring_offered | statement.excluded.spring_offered,
                "summer_offered": Course.summer_offered | statement.excluded.summer_offered,
                "fall_offered": Course.fall_offered | statement.excluded.fall_offered,
            },
        ))

    db.execute(delete(CourseOffering).where(
        CourseOffering.year == year, CourseOffering.term == term, CourseOffering.level == level
    ))
    if courses:
        db.execute(insert(CourseOffering), [
            {"year": year, "term": term, "level": level, "raw_code": code} for code in courses
        ])
    db.merge(CourseImport(year=year, term=term, level=level, course_count=len(courses), synced_at=fetched_at))
    return "published"


def ingest(
    year: int, terms: list[str], level: str | None = None, verify: bool = False, dry_run: bool = False
) -> list[dict]:
    """Refresh each New Brunswick term and level, retaining the last good data on failure."""
    levels = (level,) if level is not None else LEVELS
    results = []
    for term in terms:
        fetched_at = utc_now()
        try:
            feed = fetch_term(year, term)
            error = None
        except (requests.RequestException, ValueError) as exc:
            feed = []
            error = str(exc)

        for scope_level in levels:
            courses = normalize_courses([row for row in feed if row["level"] == scope_level], term)
            scope = {
                "campus": CAMPUS, "year": year, "term": term, "level": scope_level,
                "course_count": len(courses),
                "unmapped_count": sum(code == course["code"] for code, course in courses.items()),
            }
            try:
                if error:
                    raise ValueError(error)
                if dry_run:
                    scope["status"] = "preview" if feed else "unpublished"
                else:
                    with SessionLocal.begin() as db:
                        scope["status"] = publish_snapshot(
                            db, year, term, scope_level, courses, fetched_at, term_has_courses=bool(feed)
                        )
            except DBAPIError as exc:
                code = getattr(exc.orig, "pgcode", None)
                error_code = f" (SQLSTATE {code})" if code else ""
                scope.update(status="failed", error=f"Database write failed{error_code}")
            except SQLAlchemyError:
                scope.update(status="failed", error="Database write failed")
            except ValueError as exc:
                scope.update(status="failed", error=str(exc))
            results.append(scope)
            log = logger.warning if scope["status"] == "failed" else logger.info
            log("New Brunswick course refresh %s", scope)
            if verify:
                logger.info("Subjects with no search alias in this feed: %s", sorted({
                    row["subject_code"] for code, row in courses.items() if code == row["code"]
                }))
    return results


def main() -> None:
    """Run a read-only inventory, a manual backfill, or the regular refresh."""
    parser = argparse.ArgumentParser(description="Refresh courses from Rutgers New Brunswick.")
    parser.add_argument("--year", type=int, help="Calendar year to backfill")
    parser.add_argument("--terms", nargs="+", choices=TERM_CODES)
    parser.add_argument("--level", choices=LEVELS, help="Refresh just one level (default: both)")
    parser.add_argument("--verify", action="store_true", help="Report unfamiliar subject codes")
    parser.add_argument("--dry-run", action="store_true", help="Inventory Rutgers records without database access")
    args = parser.parse_args()
    if args.terms and args.year is None:
        parser.error("--terms requires --year")
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    specs = current_term_specs() if args.year is None else [
        (args.year, term) for term in (args.terms or TERM_CODES)
    ]
    results = [
        result
        for year, term in specs
        for result in ingest(year, [term], level=args.level, verify=args.verify, dry_run=args.dry_run)
    ]
    if any(result["status"] == "failed" for result in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
