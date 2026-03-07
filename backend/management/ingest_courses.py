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
    "706": "DANC",      # Dance
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
    "925": "SPAN",      # Spanish
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
    "560": "PCOL",      # Pharmacology graduate (31:560)
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
        offering_unit = raw.get("offeringUnitCode", "")
        # Check unit-level override first (e.g. Mason Gross Theater vs SAS Theater)
        unit_overrides = _UNIT_SUBJECT_OVERRIDE.get(offering_unit, {})
        prefix = unit_overrides.get(subject) or SUBJECT_TO_PREFIX.get(subject)
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
