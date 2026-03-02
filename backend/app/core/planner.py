import json
import re
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx

from ..schemas import PlanRequest, PlanResponse, PlannedCourse, TermPlan

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

# Map school → catalog filename (add new schools here)
_SCHOOL_CATALOG: Dict[str, str] = {
    "SAS": "sas_catalog.json",
    "SOE": "soe_catalog.json",
}

# Maps (request degree_level, hint found in major string) → DB degree_level value
_DEGREE_LEVEL_MAP: Dict[Tuple[str, Optional[str]], str] = {
    ("bachelor", "ba"):  "bachelor_ba",
    ("bachelor", "bs"):  "bachelor_bs",
    ("bachelor", None):  "bachelor_bs",   # default when no BA/BS hint
    ("minor",    None):  "minor",
    ("master",   None):  "master",
    ("associate", None): "associate",
}

CATALOG_YEAR = "2025-2026"

_SEASONS = ["Spring", "Summer", "Fall"]


# ---------------------------------------------------------------------------
# DB-backed catalog loader (falls back to JSON when DB is empty or unavailable)
# ---------------------------------------------------------------------------

def _load_catalog_from_db() -> Dict[str, Dict]:
    """
    Query the courses table populated by management/ingest_courses.py.
    Returns an empty dict if the DB is unavailable or the table is empty.
    Prerequisites are NOT stored in the DB yet; they come from the JSON catalog.
    """
    try:
        from ..database import SessionLocal
        from ..models import Course
        db = SessionLocal()
        try:
            rows = db.query(Course).all()
            return {
                r.code: {
                    "code": r.code,
                    "title": r.title,
                    "credits": r.credits,
                    "prerequisites": [],        # merged from JSON below
                    "spring_offered": r.spring_offered,
                    "summer_offered": r.summer_offered,
                    "fall_offered": r.fall_offered,
                }
                for r in rows
            }
        finally:
            db.close()
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# Term helpers
# ---------------------------------------------------------------------------

def _term_index(term: str) -> int:
    """Return a sortable integer for a term string like 'Spring 2026'."""
    season, year = term.split()
    return int(year) * 3 + _SEASONS.index(season)


def current_term() -> str:
    """Return the current academic term derived from today's date."""
    today = date.today()
    month = today.month
    year = today.year
    if month <= 5:
        season = "Spring"
    elif month <= 8:
        season = "Summer"
    else:
        season = "Fall"
    return f"{season} {year}"


def terms_between(start: str, end: str) -> List[str]:
    """Return every term from *start* up to and including *end*."""
    start_idx = _term_index(start)
    end_idx = _term_index(end)
    terms: List[str] = []
    for i in range(start_idx, end_idx + 1):
        year = i // 3
        season = _SEASONS[i % 3]
        terms.append(f"{season} {year}")
    return terms


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_catalog(path: Path) -> Dict[str, Dict]:
    """
    Load course catalog. The JSON file is the source of truth for prerequisites.
    If the DB has been populated by ingest_courses.py it is overlaid so that
    titles, credits, and offering flags stay current without manual edits.
    """
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    json_catalog: Dict[str, Dict] = {course["code"]: course for course in data}

    db_catalog = _load_catalog_from_db()
    if not db_catalog:
        return json_catalog

    # Merge: DB supplies credits and offering flags (live from Rutgers SIS).
    # JSON supplies prerequisites, corequisites, and human-readable titles.
    merged: Dict[str, Dict] = {}
    all_codes = json_catalog.keys() | db_catalog.keys()
    for code in all_codes:
        if code in db_catalog:
            entry = dict(db_catalog[code])
            json_entry = json_catalog.get(code, {})
            entry["prerequisites"] = json_entry.get("prerequisites", [])
            entry["corequisites"] = json_entry.get("corequisites", [])
            # Prefer the full readable title from JSON over the SIS abbreviation.
            if json_entry.get("title"):
                entry["title"] = json_entry["title"]
        else:
            entry = dict(json_catalog[code])
            entry.setdefault("corequisites", [])
        merged[code] = entry
    return merged


# ---------------------------------------------------------------------------
# Program resolution (DB-backed)
# ---------------------------------------------------------------------------

def _load_requirements_from_db(
    school: str, degree_level: str, major_name: str, catalog_year: str
) -> Dict:
    from ..database import SessionLocal
    from ..models import Program

    db = SessionLocal()
    try:
        row = (
            db.query(Program)
            .filter(
                Program.school == school,
                Program.degree_level == degree_level,
                Program.major_name == major_name,
                Program.catalog_year == catalog_year,
            )
            .first()
        )
        if row is None:
            raise ValueError(
                f"No program in DB: school={school}, level={degree_level}, "
                f"major='{major_name}', year={catalog_year}. "
                "Run: python -m management.seed_programs"
            )
        return dict(row.requirements)  # JSON column → dict
    finally:
        db.close()


def _parse_major_entry(entry: str, level_raw: str) -> Tuple[str, Optional[str], str]:
    """
    Parse a program string like "Computer Science (BS, SAS)" into
    (school, db_degree_level, major_name).

    Supports formats produced by GET /programs:
        "Computer Science (BS, SAS)"
        "Computer Science (BA, SAS)"
        "Computer Science (Minor, SAS)"
        "Mathematics (BS, SAS)"

    Falls back gracefully when no parentheticals are present.
    """
    m = re.match(r'^(.+?)\s*\(([^)]+)\)\s*$', entry.strip())
    if not m:
        # No parenthetical — derive level from the request field
        db_level = _DEGREE_LEVEL_MAP.get((level_raw, None))
        return "SAS", db_level, entry.strip().title()

    major_name = m.group(1).strip()
    tokens = [t.strip().upper() for t in m.group(2).split(",")]

    school = next((t for t in tokens if t in {"SAS", "SOE", "RBS"}), "SAS")
    level_token = next((t for t in tokens if t not in {"SAS", "SOE", "RBS"}), "")

    db_level: Optional[str] = {
        "BS":    "bachelor_bs",
        "BA":    "bachelor_ba",
        "MINOR": "minor",
        "MS":    "master",
        "AS":    "associate",
    }.get(level_token)

    # Fallback: use the request's degree_level when no explicit token found
    if db_level is None:
        db_level = _DEGREE_LEVEL_MAP.get((level_raw, None))

    return school, db_level, major_name


def _merge_requirements(programs: List[Dict]) -> Dict:
    """Union two or more program requirement dicts (dual major / major + minor)."""
    merged_required: List[str] = []
    for p in programs:
        for c in p.get("required_courses", []):
            if c not in merged_required:
                merged_required.append(c)

    max_count = max((p.get("electives", {}).get("count", 0) for p in programs), default=0)
    max_300 = max(
        (p.get("electives", {}).get("min_level_300_plus", 0) for p in programs), default=0
    )
    all_options: List[str] = []
    for p in programs:
        for c in p.get("electives", {}).get("options", []):
            if c not in all_options and c not in merged_required:
                all_options.append(c)
    any_from_catalog = any(
        p.get("electives", {}).get("any_from_catalog", False) for p in programs
    )

    result: Dict = {
        "required_courses": merged_required,
        "electives": {
            "count": max_count,
            "options": all_options,
            "any_from_catalog": any_from_catalog,
            "min_level_300_plus": max_300,
        },
    }

    sci = next(
        (p["science_requirement"] for p in programs if p.get("science_requirement")), None
    )
    if sci:
        result["science_requirement"] = sci

    stats = next(
        (p["statistics_requirement"] for p in programs if p.get("statistics_requirement")), None
    )
    if stats:
        result["statistics_requirement"] = stats

    return result


def resolve_program(request: PlanRequest) -> Dict:
    """
    Look up every major/minor in the request, merge their requirements, and
    return a dict with the catalog path and merged requirements dict.
    Raises ValueError if no program is found at all.
    """
    level_raw = request.degree_level.strip().lower()
    found: List[Dict] = []

    for major_raw in request.majors:
        school, db_level, major_name = _parse_major_entry(major_raw, level_raw)
        if not db_level:
            continue
        try:
            reqs = _load_requirements_from_db(school, db_level, major_name, CATALOG_YEAR)
            found.append(reqs)
        except ValueError:
            continue

    for minor_raw in request.minors:
        if not minor_raw.strip():
            continue
        school, db_level, major_name = _parse_major_entry(minor_raw, "minor")
        if not db_level:
            continue
        try:
            reqs = _load_requirements_from_db(school, db_level, major_name, CATALOG_YEAR)
            found.append(reqs)
        except ValueError:
            continue

    if not found:
        raise ValueError(
            f"No matching program found for majors={request.majors}, "
            f"minors={request.minors}, degree_level='{request.degree_level}'. "
            "Run: python -m management.seed_programs to populate the programs table."
        )

    # Derive the catalog from the primary major's school.  For cross-school
    # dual degrees (e.g. SAS + SOE), the major's school takes precedence.
    primary_school = found[0].get("school", "SAS")
    catalog_file = _SCHOOL_CATALOG.get(primary_school, _SCHOOL_CATALOG.get("SAS", "sas_catalog.json"))
    merged_reqs = found[0] if len(found) == 1 else _merge_requirements(found)

    return {
        "catalog": DATA_DIR / catalog_file,
        "requirements": merged_reqs,
    }


# ---------------------------------------------------------------------------
# Requirement helpers
# ---------------------------------------------------------------------------

def _resolve_science_courses(requirements: Dict, completed: Set[str]) -> List[str]:
    """
    Return the courses needed to satisfy the science sequence requirement.
    If the student already finished any full option, return [].
    If they started one option, complete that one.
    Otherwise default to the first option (physics sequence).
    """
    sci_req = requirements.get("science_requirement", {})
    if not sci_req:
        return []

    options: List[List[str]] = sci_req.get("options", [])
    if not options:
        return []

    # Already satisfied one option?
    for option in options:
        if all(c in completed for c in option):
            return []

    # Partially started one option? Continue it.
    for option in options:
        if any(c in completed for c in option):
            return [c for c in option if c not in completed]

    # Default: first option.
    return list(options[0])


def _resolve_stats_course(requirements: Dict, completed: Set[str]) -> Optional[str]:
    stats_req = requirements.get("statistics_requirement", {})
    if not stats_req:
        return None
    options: List[str] = stats_req.get("options", [])
    if not options or any(c in completed for c in options):
        return None
    return options[0]


def _get_course_level(code: str) -> int:
    """Return the hundreds-place level of a course (e.g., CS314 → 300, CS111 → 100)."""
    match = re.search(r'\d+', code)
    if not match:
        return 0
    return (int(match.group()) // 100) * 100


def _select_electives(
    elective_options: List[str],
    elective_count: int,
    min_level_300_plus: int,
    required: List[str],
    completed: Set[str],
) -> Tuple[List[str], List[str]]:
    """
    Pick electives satisfying the min-300-level constraint.
    Returns (chosen_electives, warnings).
    """
    available = [c for c in elective_options if c not in required and c not in completed]
    high = [c for c in available if _get_course_level(c) >= 300]

    chosen: List[str] = []
    warnings_out: List[str] = []

    # Fill required high-level slots first (preserving option-list order)
    for c in high:
        if len(chosen) >= min_level_300_plus:
            break
        chosen.append(c)

    if len(chosen) < min_level_300_plus:
        warnings_out.append(
            f"Only {len(chosen)} elective(s) at 300+ level available "
            f"(need {min_level_300_plus}). Consider different elective options."
        )

    # Fill remaining slots with any available option
    for c in available:
        if len(chosen) >= elective_count:
            break
        if c not in chosen:
            chosen.append(c)

    return chosen, warnings_out


# ---------------------------------------------------------------------------
# Offering-flag helpers
# ---------------------------------------------------------------------------

def _season_has_data(catalog: Dict[str, Dict], season: str) -> bool:
    """
    Return True if the DB has at least one course marked as offered in *season*.
    If False it means we haven't ingested that term's data yet, so we should
    not block any course from being placed in that season.
    """
    flag = f"{season.lower()}_offered"
    return any(entry.get(flag, False) for entry in catalog.values())


def _is_offered(course: Dict, season: str, season_has_data: Dict[str, bool]) -> bool:
    """Return True if *course* can be scheduled in *season*."""
    if not season_has_data.get(season, False):
        return True  # No ingested data for this season → assume offered.
    flag = f"{season.lower()}_offered"
    # JSON-only courses won't have the flag; treat them as offered everywhere.
    return course.get(flag, True)


# ---------------------------------------------------------------------------
# Core scheduling algorithm
# ---------------------------------------------------------------------------

def heuristic_plan(request: PlanRequest) -> PlanResponse:
    program = resolve_program(request)
    catalog = load_catalog(program["catalog"])
    requirements: Dict = program["requirements"]  # already a dict from the DB

    completed: Set[str] = {c.strip().upper() for c in request.completed_courses}
    warnings: List[str] = []

    # Warn about completed course codes not found in any catalog
    for code in sorted(completed):
        if code not in catalog:
            warnings.append(f"Completed course '{code}' not found in catalog — treated as satisfied prereq but may be a typo.")

    # --- Build full required-course list ---
    required: List[str] = list(requirements.get("required_courses", []))

    # Science sequence (BS only)
    for code in _resolve_science_courses(requirements, completed):
        if code not in required:
            required.append(code)

    # Statistics requirement
    stat_code = _resolve_stats_course(requirements, completed)
    if stat_code and stat_code not in required:
        required.append(stat_code)

    # Electives (with constraint enforcement)
    electives = requirements.get("electives", {})
    elective_count: int = electives.get("count", 0)
    elective_options: List[str] = list(electives.get("options", []))
    min_level_300_plus: int = electives.get("min_level_300_plus", 0)

    if electives.get("any_from_catalog") and not elective_options:
        elective_options = [c for c in catalog if c not in required]

    # Drop any option codes that aren't in the merged catalog — they can't be
    # scheduled and would generate noise warnings during planning.
    elective_options = [c for c in elective_options if c in catalog]

    # Reduce elective quota by however many the student has already completed.
    completed_elec = [c for c in elective_options if c in completed]
    completed_elec_high = [c for c in completed_elec if _get_course_level(c) >= 300]
    elective_count = max(0, elective_count - len(completed_elec))
    min_level_300_plus = max(0, min_level_300_plus - len(completed_elec_high))

    chosen_electives, elective_warnings = _select_electives(
        elective_options, elective_count, min_level_300_plus, required, completed
    )
    warnings.extend(elective_warnings)
    required += chosen_electives

    # Track which codes are elective suggestions so we can label them later.
    elective_set: Set[str] = set(chosen_electives)
    # Build the full remaining pool (excluding already-completed and already-required)
    full_elective_pool: List[str] = [
        c for c in elective_options if c not in completed
    ]

    # Remove already-completed courses
    remaining = [c for c in required if c not in completed]

    # --- Determine term window ---
    start = request.start_term or current_term()
    terms = terms_between(start, request.target_grad_term)

    if not terms:
        warnings.append(
            f"Target graduation term '{request.target_grad_term}' is at or before "
            f"the start term '{start}'. Please choose a future graduation date."
        )
        return PlanResponse(terms=[], remaining_courses=remaining, warnings=warnings)

    # --- Build prerequisite graph for topological ordering ---
    remaining_set = set(remaining)
    G: nx.DiGraph = nx.DiGraph()
    for code in remaining:
        G.add_node(code)
        for prereq in catalog.get(code, {}).get("prerequisites", []):
            if prereq in remaining_set:
                G.add_edge(prereq, code)

    # Courses that are corequisites of other required courses should NOT appear
    # as standalone items in the queue — they will be dragged in alongside their
    # partner course.  This prevents labs (e.g. PHYS205) from being scheduled
    # in an earlier term than their paired lecture (PHYS203).
    co_pulled: Set[str] = set()
    for code in remaining:
        for co in catalog.get(code, {}).get("corequisites", []):
            if co in remaining_set:
                co_pulled.add(co)

    try:
        topo_order = list(nx.topological_sort(G))
        queue = [c for c in topo_order if c in remaining_set and c not in co_pulled]
    except nx.NetworkXUnfeasible:
        warnings.append("Prerequisite cycle detected; scheduling without ordering guarantees.")
        queue = [c for c in remaining if c not in co_pulled]

    # --- Greedy scheduling with prerequisite + offering checks ---
    season_has_data = {s: _season_has_data(catalog, s) for s in _SEASONS}
    scheduled: Set[str] = set()   # courses placed in all prior terms
    planned_terms: List[TermPlan] = []

    for term in terms:
        season = term.split()[0]  # "Spring", "Summer", or "Fall"
        term_courses: List[PlannedCourse] = []
        term_credits = 0
        next_queue: List[str] = []
        # Snapshot of courses finished BEFORE this term — used for prereq checks
        # so that a course whose prereq is also being placed this term is deferred.
        prior_scheduled: Set[str] = set(scheduled)
        # Tracks codes added during this term's loop (for dedup only).
        this_term: Set[str] = set()

        for code in queue:
            # May have been pulled in as a corequisite earlier in this term.
            if code in scheduled or code in this_term:
                continue

            course = catalog.get(code)
            if not course:
                warnings.append(f"Course {code} not found in catalog — skipped.")
                continue

            prereqs: Set[str] = set(course.get("prerequisites", []))
            # Only courses from PRIOR terms (not the current term) satisfy prereqs.
            prereqs_met = prereqs.issubset(completed | prior_scheduled)
            offered = _is_offered(course, season, season_has_data)

            # Include credits from any unscheduled corequisites so the whole
            # group is budgeted together before committing any of them.
            pending_co_credits = sum(
                catalog[co]["credits"]
                for co in course.get("corequisites", [])
                if co not in scheduled and co not in this_term and co not in completed and co in catalog
            )
            fits = (
                term_credits + course["credits"] + pending_co_credits
                <= request.max_credits_per_term
            )

            if prereqs_met and offered and fits:
                is_elec = code in elective_set
                term_courses.append(
                    PlannedCourse(
                        code=course["code"],
                        title=course["title"],
                        credits=course["credits"],
                        is_elective=is_elec,
                        elective_options=full_elective_pool if is_elec else [],
                    )
                )
                term_credits += course["credits"]
                this_term.add(code)

                # Force corequisites into the same term (e.g. lecture + lab).
                for co_code in course.get("corequisites", []):
                    if co_code in scheduled or co_code in this_term or co_code in completed:
                        continue
                    co = catalog.get(co_code)
                    if not co:
                        continue
                    co_prereqs: Set[str] = set(co.get("prerequisites", []))
                    # Coreqs may depend on courses placed this term (their partner).
                    if co_prereqs.issubset(completed | prior_scheduled | this_term):
                        term_courses.append(
                            PlannedCourse(
                                code=co["code"],
                                title=co["title"],
                                credits=co["credits"],
                            )
                        )
                        term_credits += co["credits"]
                        this_term.add(co_code)
            else:
                next_queue.append(code)

        scheduled |= this_term
        queue = next_queue
        planned_terms.append(
            TermPlan(term=term, courses=term_courses, total_credits=term_credits)
        )

    if queue:
        warnings.append(
            f"Not all requirements fit before {request.target_grad_term}. "
            "Consider extending your graduation date or increasing max credits per term."
        )

    # Report any co-pulled courses (labs, etc.) that couldn't be scheduled
    # because their lecture partner also wasn't scheduled in time.
    unscheduled_co = [c for c in co_pulled if c not in scheduled and c not in completed]
    queue.extend(unscheduled_co)

    return PlanResponse(
        terms=[t for t in planned_terms if t.courses],
        remaining_courses=queue,
        warnings=warnings,
    )
