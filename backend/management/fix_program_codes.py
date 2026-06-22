#!/usr/bin/env python3
"""
fix_program_codes.py

Audits every program JSON file in backend/data/ for course codes that don't
exist in the database. For each missing code, asks Claude to suggest the
correct Rutgers equivalent based on program context and actual courses in
the DB. Writes corrected JSON files in-place and prints a diff report.

Usage (run from backend/):
    python -m management.fix_program_codes            # fix all schools
    python -m management.fix_program_codes --dry-run  # report only, no writes
    python -m management.fix_program_codes --school sas  # one school only
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

import anthropic
from app.database import SessionLocal
from app import models

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

REGISTRY_FILES = [
    "sas_programs.json",
    "soe_programs.json",
    "sppp_programs.json",
    "mgsa_programs.json",
    "rbs_programs.json",
    "sci_programs.json",
    "smlr_programs.json",
    "sebs_programs.json",
    "ssw_programs.json",
    "son_programs.json",
    "emsp_programs.json",
    "gse_programs.json",
    "gsapp_programs.json",
]


def load_all_courses(db) -> dict[str, str]:
    rows = db.query(models.Course).with_entities(
        models.Course.code, models.Course.title
    ).all()
    return {r.code: r.title for r in rows}


def courses_by_prefix(all_courses: dict[str, str]) -> dict[str, list[str]]:
    by_prefix: dict[str, list[str]] = {}
    for code in all_courses:
        prefix = re.sub(r"\d.*", "", code)
        by_prefix.setdefault(prefix, []).append(code)
    return by_prefix


def ask_claude(
    client: anthropic.Anthropic,
    wrong_code: str,
    program_name: str,
    school: str,
    all_required: list[str],
    candidates: list[tuple[str, str]],
) -> str | None:
    candidates_text = "\n".join(
        f"  {code}: {title}" for code, title in candidates[:60]
    )
    required_context = ", ".join(c for c in all_required[:20] if c != wrong_code)

    prompt = f"""You are verifying Rutgers University New Brunswick course codes.

A program requirements file lists this course code: "{wrong_code}"
That exact code does NOT exist in Rutgers' course catalog.

Program: {program_name} ({school})
Other courses in this program: {required_context}

Actual Rutgers courses in the same or related department that DO exist:
{candidates_text if candidates_text else "  (none found in same prefix — see other programs' courses for context)"}

Task: What is the correct Rutgers course code that "{wrong_code}" was meant to represent?

Rules:
- Only return a code you are highly confident exists at Rutgers NB
- Common mistakes to correct: BIO101→BIO115, BIO102→BIO116, COMMUN→COMM, ENGL→ENGL (check actual numbers), CLASS→CLAS
- If this looks like a graduate course code for a grad program (MSW, MLER, NURS, GSCM, GACCT etc.) with no matching undergrad course, return null
- If there is genuinely no confident match, return null
- Return ONLY valid JSON: {{"correct_code": "XXXNNN" or null, "reason": "one sentence"}}"""

    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=120,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
    try:
        data = json.loads(raw)
        return data.get("correct_code") or None
    except Exception:
        return None


def fix_file(
    registry_path: Path,
    all_courses: dict[str, str],
    prefix_map: dict[str, list[str]],
    client: anthropic.Anthropic,
    dry_run: bool,
) -> tuple[int, int]:
    """Fix one registry file. Returns (corrections_made, codes_left_missing)."""
    data = json.loads(registry_path.read_text())
    programs: dict = data.get("programs", {})
    corrections = 0
    still_missing = 0
    changed = False

    for slug, prog in programs.items():
        school = prog.get("school", "?")
        name = prog.get("major_name", slug)
        all_req: list[str] = prog.get("required_courses", [])
        elec_opts: list[str] = prog.get("electives", {}).get("options", [])
        all_codes = all_req + elec_opts

        for code in list(dict.fromkeys(all_codes)):  # dedupe, preserve order
            if code in all_courses:
                continue

            # Build candidates: same prefix first, then matching number
            prefix = re.sub(r"\d.*", "", code)
            number = re.sub(r"[A-Z]+", "", code)
            seen: set[str] = set()
            candidates: list[tuple[str, str]] = []

            for c in sorted(prefix_map.get(prefix, [])):
                if c not in seen:
                    candidates.append((c, all_courses[c]))
                    seen.add(c)

            for c, title in all_courses.items():
                cn = re.sub(r"[A-Z]+", "", c)
                if cn == number and c not in seen:
                    candidates.append((c, title))
                    seen.add(c)

            print(f"  [{school}] {name}: '{code}' missing — querying Claude…", flush=True)
            corrected = ask_claude(client, code, name, school, all_req, candidates)

            if corrected and corrected in all_courses:
                print(f"    ✓ {code}  →  {corrected}  ({all_courses[corrected]})")
                if code in prog.get("required_courses", []):
                    prog["required_courses"] = [
                        corrected if c == code else c
                        for c in prog["required_courses"]
                    ]
                elec = prog.get("electives", {})
                if code in elec.get("options", []):
                    elec["options"] = [
                        corrected if c == code else c
                        for c in elec["options"]
                    ]
                corrections += 1
                changed = True
            elif corrected:
                print(f"    ✗ Claude suggested '{corrected}' but it's not in DB — skipping")
                still_missing += 1
            else:
                print(f"    — No confident match for '{code}' — leaving as-is")
                still_missing += 1

    if changed and not dry_run:
        registry_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        print(f"  Saved {registry_path.name}")

    return corrections, still_missing


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fix wrong Rutgers course codes in program JSON files using Claude"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Report corrections without writing files")
    parser.add_argument("--school", default="",
                        help="Only process files matching this school (e.g. sas, soe, rbs)")
    args = parser.parse_args()

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    db = SessionLocal()
    try:
        all_courses = load_all_courses(db)
    finally:
        db.close()

    prefix_map = courses_by_prefix(all_courses)
    print(f"Loaded {len(all_courses)} courses from DB\n")

    total_fixed = 0
    total_missing = 0

    files = REGISTRY_FILES
    if args.school:
        files = [f for f in files if args.school.lower() in f.lower()]

    for fname in files:
        path = DATA_DIR / fname
        if not path.exists():
            print(f"SKIP {fname} (not found)")
            continue
        print(f"\n=== {fname} ===")
        fixed, missing = fix_file(path, all_courses, prefix_map, client, dry_run=args.dry_run)
        total_fixed += fixed
        total_missing += missing
        print(f"  {fixed} corrected, {missing} still unresolved")

    print(f"\n{'='*50}")
    print(f"Total corrected: {total_fixed}")
    print(f"Total still missing: {total_missing}")
    if args.dry_run:
        print("(dry run — no files written)")
    else:
        print("Run  python -m management.seed_programs  to push changes to DB.")


if __name__ == "__main__":
    main()
