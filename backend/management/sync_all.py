#!/usr/bin/env python3
"""
Master sync script — runs the full data pipeline in order.

Usage (from backend/):
    python -m management.sync_all              # ingest current year
    python -m management.sync_all --year 2026
    python -m management.sync_all --skip-fix   # skip Claude-powered code fixer
"""
import argparse
import subprocess
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def run(label: str, args: list[str]) -> bool:
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    result = subprocess.run([sys.executable, "-m"] + args, cwd=BACKEND)
    if result.returncode != 0:
        print(f"\n[ERROR] {label} failed (exit {result.returncode}). Stopping.")
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Full RU Planner data pipeline.")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument(
        "--skip-fix",
        action="store_true",
        help="Skip the Claude-powered program code fixer (requires ANTHROPIC_API_KEY)",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Pass --verify to ingest to report missing subject codes",
    )
    args = parser.parse_args()

    ingest_args = ["management.ingest_courses", "--year", str(args.year)]
    if args.verify:
        ingest_args.append("--verify")

    steps = [
        ("1/4  Ingest courses from SIS API", ingest_args),
    ]

    if not args.skip_fix:
        steps.append(("2/4  Fix program codes (Claude)", ["management.fix_program_codes"]))
    else:
        print("\n[Skipped] Program code fixer (--skip-fix)")

    steps += [
        ("3/4  Seed programs table", ["management.seed_programs"]),
        ("4/4  Build SAS Core index", ["management.build_sas_core_index"]),
    ]

    for label, cmd in steps:
        if not run(label, cmd):
            sys.exit(1)

    print(f"\n{'='*60}")
    print("  All steps complete.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
