#!/usr/bin/env python3
"""Test every non-doctorate major and minor against the /plan endpoint."""

import json
import urllib.request
import urllib.error
import sys

API = "http://localhost:8000"

DOCTORATE_LEVELS = {"doctorate", "doctoral", "professional_doctorate", "dual_professional_doctorate"}

def fetch(path):
    with urllib.request.urlopen(f"{API}{path}") as r:
        return json.load(r)

def post(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        body = json.loads(e.read().decode())
        return e.code, body

programs = fetch("/programs")
majors = [p for p in programs if p["degree_level"] not in DOCTORATE_LEVELS and p["degree_level"] != "minor"]
minors = [p for p in programs if p["degree_level"] == "minor"]

print(f"Testing {len(majors)} majors and {len(minors)} minors")
print("=" * 70)

failures = []
warnings_count = 0
success_count = 0

BASE_PAYLOAD = {
    "completed_courses": [],
    "start_term": "Fall 2026",
    "target_grad_term": "Spring 2030",
    "max_credits_per_term": 18,
    "summer_max_credits": 12,
    "winter_max_credits": 4,
    "preferred_seasons": ["Spring", "Fall"],
}

# --- Test each major alone ---
print("\n[MAJORS]")
for p in majors:
    name = p["display_name"]
    payload = {**BASE_PAYLOAD, "majors": [name], "minors": []}
    status, body = post("/plan", payload)
    if status != 200:
        failures.append(("MAJOR", name, status, body.get("detail", body)))
        print(f"  FAIL [{status}]  {name}")
        print(f"         {body.get('detail', body)}")
    else:
        terms = body.get("terms", [])
        remaining = body.get("remaining_courses", [])
        w = body.get("warnings", [])
        if remaining:
            warnings_count += 1
            print(f"  WARN           {name}  —  {len(remaining)} unscheduled: {remaining[:3]}")
        else:
            success_count += 1
            print(f"  OK  ({len(terms)} terms) {name}")

# --- Test each minor alone ---
print("\n[MINORS]")
for p in minors:
    name = p["display_name"]
    # Minors need a major to attach to; use a simple SAS BA
    payload = {
        **BASE_PAYLOAD,
        "majors": ["African, Middle Eastern and South Asian Languages and Literatures (BA, SAS)"],
        "minors": [name],
    }
    status, body = post("/plan", payload)
    if status != 200:
        failures.append(("MINOR", name, status, body.get("detail", body)))
        print(f"  FAIL [{status}]  {name}")
        print(f"         {body.get('detail', body)}")
    else:
        terms = body.get("terms", [])
        remaining = body.get("remaining_courses", [])
        if remaining:
            warnings_count += 1
            print(f"  WARN           {name}  —  {len(remaining)} unscheduled")
        else:
            success_count += 1
            print(f"  OK  ({len(terms)} terms) {name}")

# --- Summary ---
total = len(majors) + len(minors)
print("\n" + "=" * 70)
print(f"RESULTS: {success_count} OK  |  {warnings_count} warnings (unscheduled courses)  |  {len(failures)} hard failures")

if failures:
    print("\nHARD FAILURES:")
    for kind, name, status, detail in failures:
        print(f"  [{kind}] {name}  →  HTTP {status}: {detail}")
    sys.exit(1)
else:
    print("All programs returned HTTP 200.")
