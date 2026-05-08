#!/usr/bin/env python3
"""
Build sas_core_index.json — maps Rutgers course codes to their SAS Core designations.

Fetches live data from the Rutgers Schedule of Classes API across Fall, Spring, and Summer.
Output: backend/data/sas_core_index.json

Usage (run from backend/):
    python -m management.build_sas_core_index
    python -m management.build_sas_core_index --year 2025
"""
import argparse
import gzip
import json
import sys
import urllib.request
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OUT_FILE = DATA_DIR / "sas_core_index.json"

SIS_BASE = "https://sis.rutgers.edu/soc/api/courses.json"

# Only SAS offering unit (01) — other units don't use SAS Core
SAS_OFFERING_UNIT = "01"

# Mirrors ingest_courses.py SUBJECT_TO_PREFIX exactly
SUBJECT_TO_PREFIX: dict[str, str] = {
    # SAS — Science
    "198": "CS",       "640": "MATH",    "960": "STAT",
    "750": "PHYS",     "160": "CHEM",    "694": "MCB",
    "119": "BIO",      "146": "CBN",     "460": "GEOSC",
    "447": "GENET",    "377": "EXSC",    "762": "PPP",
    "775": "EJBSC",    "832": "PUBH",    "833": "PPOL",
    "170": "CRP",      "501": "HA",      "971": "UPD",
    "843": "PADM",     "652": "MEHE",    "975": "URST",
    # SAS — Humanities & Social Sciences
    "730": "PHIL",     "920": "SOC",     "830": "PSYC",
    "790": "POLS",     "220": "ECON",    "202": "CRIM",
    "082": "ARTH",     "085": "ART",     "615": "LING",
    "450": "GEOG",     "988": "WGSS",    "512": "HIST",
    "506": "MUS",      "965": "THEA",    "706": "DANC",
    "175": "CINE",     "840": "RELGS",   "070": "ANTH",
    "195": "COMPLIT",  "350": "JOUR",
    # SC&I
    "189": "SCI",      "192": "COMM",    "547": "ITI",     "567": "JMS",
    # Languages
    "420": "FREN",     "470": "GERM",    "560": "ITAL",
    "565": "JPN",      "563": "CHN",     "574": "KOR",
    "860": "RUSS",     "490": "PORT",    "925": "SPAN",
    "535": "AMST",     "016": "AFRS",
    # SMLR
    "534": "LER",      "533": "HRM",     "624": "LSER",
    # Social Work
    "356": "SOCW",     "910": "SW",
    # Writing / Composition
    "355": "EXPOS",
    # SOE
    "440": "ENG",      "125": "BME",     "180": "CEE",
    "540": "ISE",      "332": "ECE",     "650": "MAE",
    "155": "CHE",      "635": "MSE",     "117": "ENVE",    "375": "ENVSCI",
    # MGSA
    "203": "DSTU",     "211": "FILM",    "700": "MUSC",    "701": "MUSA",    "966": "THTA",
    # RBS
    "010": "ACCT",     "011": "PROF",    "136": "BAIT",    "140": "BLAW",
    "382": "ENT",      "390": "FIN",     "522": "BUSS",    "620": "MGMT",
    "630": "MKTG",     "799": "SCM",     "851": "RE",
    # SEBS
    "067": "ANSC",     "090": "AGECO",   "100": "BIOTECH",
    "370": "EENR",     "373": "EPIB",    "400": "FS",
    "430": "HUMEC",    "550": "LA",      "670": "METEOR",
    "680": "MICROB",   "709": "NUTRSCI", "776": "PBIO",    "780": "PLSC",
}


def _fetch(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"Accept-Encoding": "gzip", "User-Agent": "RUPlanner/1.0"},
    )
    resp = urllib.request.urlopen(req, timeout=30)
    raw = resp.read()
    if resp.headers.get("Content-Encoding") == "gzip" or raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    return raw


def _merge_term(courses: list, index: dict) -> int:
    added = 0
    for c in courses:
        if c.get("offeringUnitCode", "").strip() != SAS_OFFERING_UNIT:
            continue
        core_codes = c.get("coreCodes") or []
        if not core_codes:
            continue
        subject = str(c.get("subject", "")).zfill(3)
        course_number = str(c.get("courseNumber", "")).lstrip("0") or "0"
        prefix = SUBJECT_TO_PREFIX.get(subject)
        if not prefix:
            continue
        code = f"{prefix}{course_number}"
        designations = [cc["coreCode"] for cc in core_codes if cc.get("coreCode")]
        if designations:
            existing = index.get(code, [])
            for d in designations:
                if d not in existing:
                    existing.append(d)
            if code not in index:
                added += 1
            index[code] = existing
    return added


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", default="2025")
    args = parser.parse_args()

    index: dict[str, list[str]] = {}
    terms = [("Fall", "9"), ("Spring", "1"), ("Summer", "7")]

    for term_name, term_code in terms:
        year = str(int(args.year) + (1 if term_code == "1" else 0))
        url = f"{SIS_BASE}?year={year}&term={term_code}&campus=NB&level=U"
        print(f"Fetching {term_name} {year} …", flush=True)
        raw = _fetch(url)
        courses = json.loads(raw)
        added = _merge_term(courses, index)
        print(f"  {len(courses)} courses, {added} new codes added (total {len(index)})")

    print(f"\nTotal: {len(index)} courses with SAS Core designations")

    from collections import Counter
    counts: Counter = Counter()
    for desigs in index.values():
        for d in desigs:
            counts[d] += 1
    for tag, n in sorted(counts.items()):
        print(f"  {tag}: {n}")

    out = {"year": args.year, "terms": ["9", "1", "7"], "index": index}
    OUT_FILE.write_text(json.dumps(out, indent=2, sort_keys=True))
    print(f"\nWrote {OUT_FILE}")


if __name__ == "__main__":
    main()
