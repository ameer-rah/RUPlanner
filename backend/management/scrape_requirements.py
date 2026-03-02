#!/usr/bin/env python3
"""
Scrape SAS major requirements from Rutgers department pages and produce
draft entries for sas_programs.json.

Usage (run from backend/):
    # Scrape a specific major by slug and print draft JSON
    python -m management.scrape_requirements --major history_ba

    # Scrape all configured majors and merge into sas_programs.json
    python -m management.scrape_requirements --all

    # List all configured majors
    python -m management.scrape_requirements --list

Output is always a draft — review before committing to sas_programs.json.
Courses not found in the catalog are flagged with a "MISSING_IN_CATALOG" warning.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
REGISTRY_PATH = DATA_DIR / "sas_programs.json"
CATALOG_PATH = DATA_DIR / "sas_catalog.json"

# ---------------------------------------------------------------------------
# Rutgers subject-code → short prefix mapping
# Full subject code: school:subject:number  e.g. 01:198:111
# ---------------------------------------------------------------------------
SUBJECT_TO_PREFIX: Dict[str, str] = {
    # SAS
    "506": "HIST",    # History (general)
    "508": "HIST",    # Africana/Global history
    "510": "HIST",    # European History
    "512": "HIST",    # US History
    "358": "ENGL",    # English Literature
    "359": "ENGL",    # English Theories/Methods
    "351": "ENGL",    # Creative Writing
    "354": "FILM",    # Film Studies
    "198": "CS",      # Computer Science
    "640": "MATH",    # Mathematics
    "960": "STAT",    # Statistics
    "750": "PHYS",    # Physics
    "160": "CHEM",    # Chemistry
    "920": "SOC",     # Sociology
    "830": "PSYC",    # Psychology
    "790": "POLS",    # Political Science
    "730": "PHIL",    # Philosophy
    "447": "LING",    # Linguistics
    "070": "ANTH",    # Anthropology
    "082": "ANTH",    # Anthropology (alt)
    "776": "POLS",    # Political Science (alt)
    "563": "ARTH",    # Art History
    "082": "GEOG",    # Geography (check)
    "450": "GEOG",    # Geography
    "460": "GEOSC",   # Geological Sciences
    "165": "BIOC",    # Biochemistry
    "694": "MCB",     # Molecular Biology
    "115": "BIO",     # Biological Sciences
    "118": "BIO",     # Biology (alt)
    "694": "MCB",     # Molecular Biology & Biochemistry
    "190": "ECON",    # Economics
    "175": "COMMUN",  # Communication
    "185": "COGS",    # Cognitive Science
    "082": "AFRS",    # Africana Studies (alt)
    "016": "AFRS",    # Africana Studies
    "986": "WGSS",    # Women's Gender Sexuality Studies
    "195": "CRIM",    # Criminal Justice
    "377": "ENVST",   # Environmental Studies
    "090": "AMST",    # American Studies
    "098": "ASIAN",   # Asian Studies
    "940": "SPAN",    # Spanish
    "420": "FREN",    # French
    "910": "SOCWK",   # Social Work
    "840": "THEA",    # Theater Arts
    "700": "MUSIC",   # Music
    "082": "ANTH",    # Anthropology
    "887": "DANC",    # Dance
    "219": "EXER",    # Exercise Science
    "501": "PUBH",    # Public Health
    "560": "PUBP",    # Public Policy
    "762": "RELIG",   # Religion
    "563": "ARTH",    # Art History
    "082": "CLCS",    # Classics (check)
    "490": "ITAL",    # Italian
    "420": "FREN",    # French
    "563": "ARTH",    # Art History
}

# Prefix we already have normalized in the catalog
KNOWN_PREFIXES = {
    "CS", "MATH", "STAT", "PHYS", "CHEM", "ECON", "SOC", "PSYC", "POLS",
    "PHIL", "GEOG", "GEOSC", "LING", "ARTH", "WGSS", "CRIM", "HIST",
    "ENGL", "BIO", "BIOC", "MCB", "ANTH", "COMMUN", "COGS", "ENVST",
    "AMST", "ASIAN", "AFRS", "SPAN", "FREN", "THEA", "MUSIC", "DANC",
    "EXER", "PUBH", "PUBP", "RELIG", "SOC", "FILM",
}

# ---------------------------------------------------------------------------
# Major registry: slug → (degree_level, major_name, school, requirements_url)
# Add new majors here.
# ---------------------------------------------------------------------------
MAJOR_REGISTRY: Dict[str, Tuple[str, str, str, str]] = {
    # --- Already in sas_programs.json (kept for re-scraping) ---
    "history_ba": (
        "bachelor_ba", "History", "SAS",
        "https://history.rutgers.edu/academics/undergraduate/major-requirements",
    ),
    "english_ba": (
        "bachelor_ba", "English", "SAS",
        "https://english.rutgers.edu/academics/undergraduate-91/englishmajor.html",
    ),
    "biology_ba": (
        "bachelor_ba", "Biological Sciences", "SAS",
        "https://sasundergrad.rutgers.edu/majors-and-core-curriculum/major/major-minor-details/biology",
    ),
    "cell_biology_neuroscience_ba": (
        "bachelor_ba", "Cell Biology and Neuroscience", "SAS",
        "https://sasundergrad.rutgers.edu/majors-and-core-curriculum/major/major-minor-details/cell-biology-and-neuroscience",
    ),
    "cognitive_science_ba": (
        "bachelor_ba", "Cognitive Science", "SAS",
        "https://sasundergrad.rutgers.edu/majors-and-core-curriculum/major/major-minor-details/cognitive-science",
    ),
    "communication_ba": (
        "bachelor_ba", "Communication", "SAS",
        "https://sasundergrad.rutgers.edu/majors-and-core-curriculum/major/major-minor-details/communication",
    ),
    "anthropology_cultural_ba": (
        "bachelor_ba", "Anthropology", "SAS",
        "https://sasundergrad.rutgers.edu/majors-and-core-curriculum/major/major-minor-details/anthropology-cultural",
    ),
    "data_science_cs_bs": (
        "bachelor_bs", "Data Science - Computer Science Track", "SAS",
        "https://sasundergrad.rutgers.edu/majors-and-core-curriculum/major/major-minor-details/data-science-computer-science-track",
    ),
    "data_science_stats_ba": (
        "bachelor_ba", "Data Science - Statistics Track", "SAS",
        "https://sasundergrad.rutgers.edu/majors-and-core-curriculum/major/major-minor-details/data-science-statistics-track",
    ),
    "environmental_studies_ba": (
        "bachelor_ba", "Environmental Studies", "SAS",
        "https://sasundergrad.rutgers.edu/majors-and-core-curriculum/major/major-minor-details/environmental-studies",
    ),
    "genetics_ba": (
        "bachelor_ba", "Genetics", "SAS",
        "https://sasundergrad.rutgers.edu/majors-and-core-curriculum/major/major-minor-details/genetics",
    ),
    "molecular_biology_biochemistry_ba": (
        "bachelor_ba", "Molecular Biology and Biochemistry", "SAS",
        "https://sasundergrad.rutgers.edu/majors-and-core-curriculum/major/major-minor-details/molecular-biology-and-biochemistry",
    ),
    "exercise_science_bs": (
        "bachelor_bs", "Exercise Science", "SAS",
        "https://sasundergrad.rutgers.edu/majors-and-core-curriculum/major/major-minor-details/exercise-science",
    ),
    "public_health_bs": (
        "bachelor_bs", "Public Health", "SAS",
        "https://sasundergrad.rutgers.edu/majors-and-core-curriculum/major/major-minor-details/public-health",
    ),
    "astrophysics_bs": (
        "bachelor_bs", "Astrophysics", "SAS",
        "https://sasundergrad.rutgers.edu/majors-and-core-curriculum/major/major-minor-details/astrophysics",
    ),
    "american_studies_ba": (
        "bachelor_ba", "American Studies", "SAS",
        "https://sasundergrad.rutgers.edu/majors-and-core-curriculum/major/major-minor-details/american-studies",
    ),
    "africana_studies_ba": (
        "bachelor_ba", "Africana Studies", "SAS",
        "https://sasundergrad.rutgers.edu/majors-and-core-curriculum/major/major-minor-details/africana-studies",
    ),
    "spanish_ba": (
        "bachelor_ba", "Spanish", "SAS",
        "https://sasundergrad.rutgers.edu/majors-and-core-curriculum/major/major-minor-details/spanish",
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_catalog_codes() -> set:
    with open(CATALOG_PATH, "r", encoding="utf-8") as fh:
        catalog = json.load(fh)
    return {c["code"] for c in catalog}


def _normalize_course_code(raw: str) -> Optional[str]:
    """
    Convert a raw Rutgers course code to our short form.

    Handles:
      01:198:111   →  CS111
      01:640:151   →  MATH151
      198:111      →  CS111
      CS111        →  CS111  (already normalized)
    """
    raw = raw.strip()

    # Already normalized (e.g. CS111, MATH151)
    m = re.match(r'^([A-Z]{2,8})(\d{3}[A-Z]?)$', raw)
    if m:
        return raw

    # Full Rutgers format: 01:198:111 or 01:198:111H
    m = re.match(r'^\d{2}:(\d{3}):(\d{3}[A-Z]?)$', raw)
    if m:
        subject, number = m.group(1), m.group(2)
        prefix = SUBJECT_TO_PREFIX.get(subject)
        if prefix:
            return f"{prefix}{number}"
        return None  # unknown subject

    # Short Rutgers format: 198:111
    m = re.match(r'^(\d{3}):(\d{3}[A-Z]?)$', raw)
    if m:
        subject, number = m.group(1), m.group(2)
        prefix = SUBJECT_TO_PREFIX.get(subject)
        if prefix:
            return f"{prefix}{number}"
        return None

    return None


def _extract_courses_from_html(html: str) -> List[str]:
    """
    Extract all course codes from raw HTML text.
    Returns normalized codes in our short format.
    """
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(separator=" ")

    found: List[str] = []
    seen: set = set()

    # Pattern 1: full Rutgers  01:198:111 or 01:198:111H
    for m in re.finditer(r'\b\d{2}:\d{3}:\d{3}[A-Z]?\b', text):
        code = _normalize_course_code(m.group())
        if code and code not in seen:
            found.append(code)
            seen.add(code)

    # Pattern 2: short  198:111 or 198:111H
    for m in re.finditer(r'\b\d{3}:\d{3}[A-Z]?\b', text):
        code = _normalize_course_code(m.group())
        if code and code not in seen:
            found.append(code)
            seen.add(code)

    # Pattern 3: already-normalized  CS111, MATH151
    for m in re.finditer(r'\b([A-Z]{2,8})(\d{3}[A-Z]?)\b', text):
        candidate = m.group()
        if m.group(1) in KNOWN_PREFIXES and candidate not in seen:
            found.append(candidate)
            seen.add(candidate)

    return found


def fetch_and_extract(url: str) -> List[str]:
    """Fetch a URL and return normalized course codes found in the page."""
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "RUPlanner-scraper/1.0"})
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"  WARN  fetch failed for {url}: {exc}", file=sys.stderr)
        return []
    return _extract_courses_from_html(resp.text)


def build_draft_entry(
    slug: str,
    degree_level: str,
    major_name: str,
    school: str,
    courses: List[str],
    catalog_codes: set,
) -> dict:
    """
    Build a draft sas_programs.json entry.
    Splits courses into required (first ~4) and elective options as a heuristic —
    the human reviewer should adjust this.
    """
    missing = [c for c in courses if c not in catalog_codes]

    entry = {
        "school": school,
        "degree_level": degree_level,
        "major_name": major_name,
        "catalog_year": "2025-2026",
        "required_courses": courses[:4] if len(courses) >= 4 else courses,
        "electives": {
            "count": max(0, len(courses) - 4),
            "min_level_300_plus": 0,
            "options": courses[4:],
            "any_from_catalog": False,
        },
        "constraints": [],
        "notes": [
            "DRAFT — review and adjust required_courses vs electives split.",
            f"Source: see MAJOR_REGISTRY['{slug}'] in scrape_requirements.py",
        ],
    }

    if missing:
        entry["notes"].append(
            f"MISSING_IN_CATALOG: {', '.join(missing)} — add these to sas_catalog.json"
        )

    return entry


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_list() -> None:
    print(f"{'Slug':<40} {'Degree':<14} Major")
    print("-" * 80)
    for slug, (deg, name, school, url) in sorted(MAJOR_REGISTRY.items()):
        print(f"{slug:<40} {deg:<14} {name}")


def cmd_scrape(slug: str) -> Optional[dict]:
    if slug not in MAJOR_REGISTRY:
        print(f"ERROR: unknown slug '{slug}'. Use --list to see options.", file=sys.stderr)
        return None

    degree_level, major_name, school, url = MAJOR_REGISTRY[slug]
    print(f"Scraping: {major_name} ({degree_level}) from {url}", file=sys.stderr)

    courses = fetch_and_extract(url)
    print(f"  Found {len(courses)} course codes: {courses}", file=sys.stderr)

    catalog_codes = _load_catalog_codes()
    return build_draft_entry(slug, degree_level, major_name, school, courses, catalog_codes)


def cmd_scrape_all(merge: bool = False) -> None:
    catalog_codes = _load_catalog_codes()
    drafts: Dict[str, dict] = {}

    for slug, (degree_level, major_name, school, url) in MAJOR_REGISTRY.items():
        print(f"\nScraping [{slug}] {major_name} ({degree_level}) ...", file=sys.stderr)
        courses = fetch_and_extract(url)
        print(f"  {len(courses)} courses found", file=sys.stderr)
        drafts[slug] = build_draft_entry(slug, degree_level, major_name, school, courses, catalog_codes)

    if merge:
        with open(REGISTRY_PATH, "r", encoding="utf-8") as fh:
            registry: dict = json.load(fh)
        existing_keys = set(registry["programs"].keys())
        added = 0
        for slug, entry in drafts.items():
            if slug not in existing_keys:
                registry["programs"][slug] = entry
                print(f"  ADDED {slug}", file=sys.stderr)
                added += 1
            else:
                print(f"  SKIP  {slug} (already in registry)", file=sys.stderr)
        with open(REGISTRY_PATH, "w", encoding="utf-8") as fh:
            json.dump(registry, fh, indent=2)
        print(f"\nMerged {added} new draft entries into {REGISTRY_PATH}", file=sys.stderr)
    else:
        print(json.dumps(drafts, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape SAS major requirements")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="List configured majors")
    group.add_argument("--major", metavar="SLUG", help="Scrape a single major by slug")
    group.add_argument("--all", action="store_true", help="Scrape all configured majors")
    parser.add_argument(
        "--merge",
        action="store_true",
        help="With --all: merge new drafts directly into sas_programs.json",
    )
    args = parser.parse_args()

    if args.list:
        cmd_list()
    elif args.major:
        entry = cmd_scrape(args.major)
        if entry:
            print(json.dumps(entry, indent=2))
    elif args.all:
        cmd_scrape_all(merge=args.merge)


if __name__ == "__main__":
    main()
