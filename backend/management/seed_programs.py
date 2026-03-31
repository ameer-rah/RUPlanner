#!/usr/bin/env python3
"""
Seed the programs table from the consolidated registry files in backend/data/.

Each registry file (e.g. sas_programs.json) contains all programs for one school
under a top-level "programs" dict keyed by a slug.  Adding a new major means
adding an entry to that file — no code change needed here.

Usage (run from backend/):
    python -m management.seed_programs
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.database import engine, SessionLocal, Base
from app.models import Program  # noqa — registers model with Base
from sqlalchemy.orm.attributes import flag_modified

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Registry files to load — add new schools here
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


def seed() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    inserted = updated = skipped = 0

    try:
        for registry_filename in REGISTRY_FILES:
            registry_path = DATA_DIR / registry_filename
            if not registry_path.exists():
                print(f"  SKIP  {registry_filename} (file not found)")
                continue

            with open(registry_path, "r", encoding="utf-8") as fh:
                registry: dict = json.load(fh)

            programs: dict = registry.get("programs", {})
            if not programs:
                print(f"  WARN  {registry_filename} has no 'programs' key — skipping")
                continue

            print(f"\nLoading {registry_filename} ({len(programs)} programs) ...")

            for slug, payload in programs.items():
                school = payload.get("school")
                degree_level = payload.get("degree_level")
                major_name = payload.get("major_name")
                catalog_year = payload.get("catalog_year", registry.get("catalog_year", "2025-2026"))

                if not all([school, degree_level, major_name]):
                    print(f"  SKIP  {slug}: missing school/degree_level/major_name")
                    skipped += 1
                    continue

                existing = (
                    db.query(Program)
                    .filter(
                        Program.school == school,
                        Program.degree_level == degree_level,
                        Program.major_name == major_name,
                        Program.catalog_year == catalog_year,
                    )
                    .first()
                )

                if existing:
                    existing.requirements = payload
                    flag_modified(existing, "requirements")
                    print(f"  UPDATE {school} | {degree_level:<12} | {major_name} ({catalog_year})")
                    updated += 1
                else:
                    db.add(
                        Program(
                            school=school,
                            degree_level=degree_level,
                            major_name=major_name,
                            catalog_year=catalog_year,
                            requirements=payload,
                        )
                    )
                    print(f"  INSERT {school} | {degree_level:<12} | {major_name} ({catalog_year})")
                    inserted += 1

        db.commit()
        total = db.query(Program).count()
        print(f"\nDone. {inserted} inserted, {updated} updated, {skipped} skipped. {total} program(s) total in DB.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
