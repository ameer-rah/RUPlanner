import json
import math
import re
import threading
import time
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx

from ..schemas import PlanRequest, PlanResponse, PlannedCourse, TermPlan, ElectiveOption, CoreCurriculumBlock, CourseStatus, ProgramSummary
from .eligibility import StudentRecord, evaluate_rule, rule_for_course

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

_SCHOOL_CATALOG: Dict[str, str] = {
    "SAS": "sas_catalog.json",
    "SOE": "soe_catalog.json",
    "SPPP": "sppp_catalog.json",
    "MGSA": "mgsa_catalog.json",
    "RBS": "rbs_catalog.json",
    "SCI": "sci_catalog.json",
    "SMLR": "smlr_catalog.json",
    "SEBS": "sebs_catalog.json",
    "SSW": "ssw_catalog.json",
    "SON": "son_catalog.json",
    "EMSP": "emsp_catalog.json",
    "GSE": "gse_catalog.json",
    "GSAPP": "gsapp_catalog.json",
}

_SCHOOL_TO_DN_KEY: Dict[str, str] = {
    "SAS":  "dn_2721",
    "SEBS": "dn_2742",
    "RBS":  "dn_2841",
    "SPPP": "dn_18",
    "SON":  "dn_37",
    "SOE":  "dn_29",
    "SCI":  "dn_2721",   # SC&I students satisfy SAS Core
    "SMLR": "dn_2721",  # SMLR students satisfy SAS Core
    "MGSA": "dn_13",
}

_DEGREE_LEVEL_MAP: Dict[Tuple[str, Optional[str]], str] = {
    ("bachelor", "ba"):   "bachelor_ba",
    ("bachelor", "bs"):   "bachelor_bs",
    ("bachelor", "bfa"):  "bachelor_bfa",
    ("bachelor", "bm"):   "bachelor_bm",
    ("bachelor", "bsba"): "bachelor_bsba",
    ("bachelor", None):   "bachelor_bs",
    ("minor",         None):  "minor",
    ("master",        None):  "master",
    ("master",        "ms"):  "master_ms",
    ("master",        "ma"):  "master_ma",
    ("master",        "mat"): "master_mat",
    ("master",        "meng"):"master_meng",
    ("doctorate",              None):  "doctorate",
    ("phd",                    None):  "doctorate",
    ("doctoral",               None):  "doctoral",
    ("professional_doctorate", None):  "professional_doctorate",
    ("psyd",                   None):  "professional_doctorate",
    ("edd",                    None):  "professional_doctorate",
    ("pharmd",                 None):  "professional_doctorate",
    ("associate",              None):  "associate",
    ("concentration",          None):  "concentration",
}

CATALOG_YEAR = "2025-2026"

_SEASONS = ["Spring", "Summer", "Fall", "Winter"]

# Keys: (school, degree_level, major_name)
# Values: dict of fields to remove (set to None) or override.
# Add entries here whenever scraped program data has incorrect fields.
_PROGRAM_PATCHES: Dict[Tuple[str, str, str], Dict] = {
    # CS BS has no statistics requirement — was incorrectly scraped.
    # CS213/CS214 are electives, not required core courses.
    ("SAS", "bachelor_bs", "Computer Science"): {
        "statistics_requirement": None,
        "move_to_electives": ["CS213", "CS214"],
    },
    # ChemE's science elective was misclassified under statistics_requirement.
    ("SOE", "bachelor_bs", "Chemical Engineering"): {
        "statistics_requirement": None,
    },
}


def _apply_program_patches(school: str, degree_level: str, major_name: str, requirements: Dict) -> Dict:
    """Correct known source-data defects before planning a program.

    Args:
        school: School abbreviation used in the patch key.
        degree_level: Normalized database degree level.
        major_name: Canonical program name.
        requirements: Requirements loaded from the program source.

    Returns:
        A patched copy, or the original mapping when no patch is registered.
    """
    patch = _PROGRAM_PATCHES.get((school, degree_level, major_name))
    if not patch:
        return requirements
    result = dict(requirements)
    for field, value in patch.items():
        if field == "move_to_electives":
            # Move listed courses out of required_courses and into electives.options
            to_move = set(value)
            result["required_courses"] = [c for c in result.get("required_courses", []) if c not in to_move]
            electives = dict(result.get("electives", {}))
            options = list(electives.get("options", []))
            for c in value:
                if c not in options:
                    options.append(c)
            electives["options"] = options
            result["electives"] = electives
        elif value is None:
            result.pop(field, None)
        else:
            result[field] = value
    return result


def _apply_track(requirements: Dict, track: Optional[str]) -> Dict:
    """Apply a validated track while preserving an optional general path.

    A program opts into mandatory selection with ``track_required: true``.
    Merely publishing optional specializations does not invalidate its general
    curriculum.
    """
    tracks = requirements.get("tracks", {})
    dimensions = requirements.get("track_dimensions", [])
    if not track:
        if (tracks or dimensions) and requirements.get("track_required") is True:
            raise ValueError("This program requires a track selection.")
        return requirements
    if dimensions:
        selections = track.split("/")
        if len(selections) != len(dimensions):
            raise ValueError("This program requires a selection for every track category.")
        chosen: List[Dict] = []
        for dimension, selection in zip(dimensions, selections):
            options = dimension.get("options", {})
            if selection not in options or not isinstance(options[selection], dict):
                raise ValueError(f"Unknown {dimension.get('label', 'track')} selection '{selection}'.")
            chosen.append(options[selection])
        base = {k: v for k, v in requirements.items() if k not in {"tracks", "track_dimensions"}}
        result = dict(base)
        result["required_courses"] = list(dict.fromkeys([
            *base.get("required_courses", []),
            *(course for option in chosen for course in option.get("required_courses", [])),
        ]))
        result["requirement_groups"] = [
            *base.get("requirement_groups", []),
            *(group for option in chosen for group in option.get("requirement_groups", [])),
        ]
        result["selected_track"] = track
        return result
    if not isinstance(tracks, dict) or track not in tracks:
        available = ", ".join(str(name) for name in tracks) if isinstance(tracks, dict) else ""
        suffix = f" Available tracks: {available}." if available else " This program does not define tracks."
        raise ValueError(f"Unknown track '{track}'.{suffix}")
    if not isinstance(tracks[track], dict):
        raise ValueError(f"Track '{track}' has invalid requirement data.")
    base = {k: v for k, v in requirements.items() if k != "tracks"}
    track_reqs = dict(tracks[track])
    result = {**base, **track_reqs}
    if base.get("required_courses") or track_reqs.get("required_courses"):
        result["required_courses"] = list(dict.fromkeys([
            *base.get("required_courses", []),
            *track_reqs.get("required_courses", []),
        ]))
    if base.get("requirement_groups") or track_reqs.get("requirement_groups"):
        result["requirement_groups"] = [
            *base.get("requirement_groups", []),
            *track_reqs.get("requirement_groups", []),
        ]
    result["selected_track"] = track
    return result


def _load_catalog_from_db() -> Dict[str, Dict]:
    """Load the shared course catalog through the planner's cache layer.

    Returns:
        Catalog entries keyed by unambiguous course code.
    """
    return _get_db_catalog()


_SAS_CORE_INDEX: Dict[str, List[str]] = {}  # {course_code: [designation, ...]}
_SAS_CORE_INDEX_LOADED = False

_DB_CATALOG_CACHE: Dict[str, Dict] = {}
_DB_CATALOG_LOADED_AT = 0.0
_DB_CATALOG_TTL_SECONDS = 5 * 60
_DB_CATALOG_LOCK = threading.Lock()

_DN_PROGRAMS_CACHE: Dict = {}
_DN_PROGRAMS_LOADED = False


def _get_db_catalog() -> Dict[str, Dict]:
    """Return a cached database catalog, refreshing it after the TTL expires.

    The last valid snapshot is retained when the database is temporarily
    unavailable so planning can continue without replacing good cached data.

    Returns:
        Catalog entries keyed by unique course alias.
    """
    global _DB_CATALOG_CACHE, _DB_CATALOG_LOADED_AT
    now = time.monotonic()
    if _DB_CATALOG_LOADED_AT and now - _DB_CATALOG_LOADED_AT < _DB_CATALOG_TTL_SECONDS:
        return _DB_CATALOG_CACHE
    with _DB_CATALOG_LOCK:
        now = time.monotonic()
        if _DB_CATALOG_LOADED_AT and now - _DB_CATALOG_LOADED_AT < _DB_CATALOG_TTL_SECONDS:
            return _DB_CATALOG_CACHE
        try:
            from ..database import SessionLocal
            from ..models import Course
            db = SessionLocal()
            try:
                rows = db.query(Course).all()
                aliases: Dict[str, List] = {}
                for row in rows:
                    aliases.setdefault(row.code, []).append(row)
                # A short alias is usable by legacy requirement JSON only when it
                # resolves to exactly one canonical Rutgers course.
                catalog = {
                    code: {
                        "code": r.code,
                        "raw_code": r.raw_code,
                        "title": r.title,
                        "credits": r.credits,
                        "prerequisites": [],
                        "spring_offered": r.spring_offered,
                        "summer_offered": r.summer_offered,
                        "fall_offered": r.fall_offered,
                    }
                    for code, matches in aliases.items()
                    if len(matches) == 1
                    for r in matches
                }
            finally:
                db.close()
        except Exception:
            # Keep the last known-good catalog during a transient database error.
            return _DB_CATALOG_CACHE
        _DB_CATALOG_CACHE = catalog
        _DB_CATALOG_LOADED_AT = now
        return _DB_CATALOG_CACHE


def invalidate_catalog_cache() -> None:
    """Force the next planner request to reload recently ingested courses."""
    global _DB_CATALOG_LOADED_AT
    with _DB_CATALOG_LOCK:
        _DB_CATALOG_LOADED_AT = 0.0


def _get_dn_programs() -> Dict:
    """Load and cache Degree Navigator program data used for core curricula.

    Returns:
        Parsed program data, or an empty mapping when the file cannot be read.
    """
    global _DN_PROGRAMS_CACHE, _DN_PROGRAMS_LOADED
    if _DN_PROGRAMS_LOADED:
        return _DN_PROGRAMS_CACHE
    try:
        dn_path = DATA_DIR / "dn_programs.json"
        with open(dn_path, "r", encoding="utf-8") as fh:
            _DN_PROGRAMS_CACHE = json.load(fh)
    except Exception:
        _DN_PROGRAMS_CACHE = {}
    _DN_PROGRAMS_LOADED = True
    return _DN_PROGRAMS_CACHE


def _get_sas_core_index() -> Dict[str, List[str]]:
    """Load and cache the mapping from courses to SAS Core designations.

    Returns:
        Designation lists keyed by course code, or an empty mapping on failure.
    """
    global _SAS_CORE_INDEX, _SAS_CORE_INDEX_LOADED
    if _SAS_CORE_INDEX_LOADED:
        return _SAS_CORE_INDEX
    try:
        path = DATA_DIR / "sas_core_index.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        _SAS_CORE_INDEX = data.get("index", {})
    except Exception:
        _SAS_CORE_INDEX = {}
    _SAS_CORE_INDEX_LOADED = True
    return _SAS_CORE_INDEX


_BLOCK_TAG_RE = re.compile(r"\[([A-Za-z]+)\]")

def _tags_for_block(title: str) -> Set[str]:
    """Extract SAS Core designation tags from a block title, e.g. '[WCd]' → {'WCd'}."""
    tags = {m.group(1) for m in _BLOCK_TAG_RE.finditer(title)}
    # Degree Navigator abbreviates the Contemporary Challenges block as CC,
    # while the official course index publishes its two goals separately.
    if "CC" in tags:
        tags.remove("CC")
        tags.update({"CCD", "CCO"})
    return tags


def _core_goal_slots(title: str, total_courses: Optional[int]) -> List[Set[str]]:
    """Return the distinct designation goals a core block must satisfy.

    Degree Navigator's block titles contain a union of tags, but several SAS
    blocks require different goals to be met by different courses. Treating
    that union as interchangeable can falsely complete a block with two WCd,
    two SCL, or two QQ courses.
    """
    tags = _tags_for_block(title)
    if "[CC]" in title:
        return [{"CCD"}, {"CCO"}]
    if {"SCL", "HST"}.issubset(tags):
        return [{"SCL"}, {"HST"}]
    if {"WC", "WCr", "WCd"}.issubset(tags):
        return [{"WC"}, {"WCr"}, {"WCd"}]
    if {"QQ", "QR"}.issubset(tags):
        return [{"QQ"}, {"QR"}]
    if tags.intersection({"AHo", "AHp", "AHq", "AHr"}) and total_courses == 2:
        # The two AH courses must meet two different goals. The concrete goal
        # is chosen during matching, so each slot initially accepts all four.
        ah = tags.intersection({"AHo", "AHp", "AHq", "AHr"})
        return [set(ah), set(ah)]
    return [set(tags) for _ in range(total_courses or 0)]


def _match_core_assignments(
    title: str,
    total_courses: Optional[int],
    course_codes: List[str],
    core_index: Dict[str, List[str]],
) -> List[Tuple[str, str]]:
    """Allocate distinct courses to distinct core goals, without double count."""
    slots = _core_goal_slots(title, total_courses)
    ah_tags = {"AHo", "AHp", "AHq", "AHr"}
    best: List[Tuple[str, str]] = []

    def search(slot_index: int, matched: List[Tuple[str, str]], used_tags: Set[str]) -> None:
        """Backtrack through goal slots and retain the largest valid matching."""
        nonlocal best
        if len(matched) > len(best):
            best = list(matched)
        if slot_index >= len(slots):
            return
        slot = slots[slot_index]
        for code in course_codes:
            if any(matched_code == code for matched_code, _ in matched):
                continue
            eligible = slot.intersection(core_index.get(code, []))
            if len(slots) == 2 and slot.intersection(ah_tags):
                eligible -= used_tags
            for tag in sorted(eligible):
                search(slot_index + 1, [*matched, (code, tag)], used_tags | {tag})
        search(slot_index + 1, matched, used_tags)

    search(0, [], set())
    return best


def _match_core_courses(
    title: str,
    total_courses: Optional[int],
    course_codes: List[str],
    core_index: Dict[str, List[str]],
) -> List[str]:
    """Return distinct courses that can fill the core block's goal slots.

    Args:
        title: Core block title containing designation tags.
        total_courses: Number of courses required by the block.
        course_codes: Candidate course codes.
        core_index: Core designations keyed by course code.

    Returns:
        Matched course codes without their internal goal-tag assignments.
    """
    return [code for code, _ in _match_core_assignments(title, total_courses, course_codes, core_index)]


def _prerequisite_closure(code: str, catalog: Dict[str, Dict], satisfied: Set[str]) -> Set[str]:
    """Return all catalogued prerequisites needed to take ``code``."""
    needed: Set[str] = set()
    stack = [code]
    while stack:
        current = stack.pop()
        for prereq in catalog.get(current, {}).get("prerequisites", []):
            if prereq in satisfied or prereq in needed or prereq not in catalog:
                continue
            needed.add(prereq)
            stack.append(prereq)
    return needed


def _core_candidate_key(code: str, catalog: Dict[str, Dict], satisfied: Set[str]) -> Tuple:
    """Prefer the smallest prerequisite burden, then lower-level courses."""
    prereqs = _prerequisite_closure(code, catalog, satisfied)
    prereq_credits = sum(float(catalog[item].get("credits") or 0) for item in prereqs)
    return (prereq_credits, len(prereqs), _get_course_level(code), code)


def _load_core_curriculum(
    school: str, completed_courses: Set[str]
) -> Tuple[Optional[str], List[Dict], List[str]]:
    """Load core curriculum blocks for a school from dn_programs.json.

    Returns (curriculum_name, blocks, required_courses_list).
    Returns (None, [], []) if no data exists for this school.
    """
    dn_key = _SCHOOL_TO_DN_KEY.get(school)
    if not dn_key:
        return None, [], []

    dn_data = _get_dn_programs()
    if not dn_data:
        return None, [], []

    program = dn_data.get("programs", {}).get(dn_key)
    if not program:
        return None, [], []

    curriculum_name: str = program.get("major_name", "Core Curriculum")
    raw_blocks: List[Dict] = program.get("_raw_blocks", [])

    if not raw_blocks:
        return None, [], []

    # Schools that share the Rutgers SAS Core designation system (R1-R6, [WCd], [AHp], etc.)
    # All these schools' blocks use the same tags, so the same index applies.
    _SAS_CORE_SCHOOLS = {"SAS", "SEBS", "RBS", "SPPP", "SON", "SOE", "SCI", "SMLR"}
    core_index = _get_sas_core_index() if school in _SAS_CORE_SCHOOLS else {}

    blocks: List[CoreCurriculumBlock] = []
    all_core_courses: List[str] = []

    for rb in raw_blocks:
        courses: List[str] = rb.get("courses", [])
        total: Optional[int] = rb.get("total_courses")
        block_title: str = rb.get("title", "")
        block_tags = _tags_for_block(block_title)

        # Expand the display pool with completed designated courses, then
        # allocate them to the block's distinct goals.
        if block_tags and core_index:
            for code in sorted(completed_courses):
                desigs = set(core_index.get(code, []))
                if desigs & block_tags and code not in courses:
                    courses = list(courses) + [code]

        completed_candidates = [c for c in courses if c in completed_courses]
        if block_tags and core_index:
            completed_assignments = _match_core_assignments(
                block_title, total, completed_candidates, core_index
            )
            completed_in_block = [code for code, _ in completed_assignments]
        else:
            completed_assignments = []
            completed_in_block = completed_candidates[:total]
        needed = max(0, (total or 0) - len(completed_in_block)) if total is not None else 0
        blocks.append(
            CoreCurriculumBlock(
                title=block_title,
                total_courses=total,
                courses=courses,
                is_elective=rb.get("is_elective", False),
                completed=completed_in_block,
                needed=needed,
                goal_slots=[sorted(slot) for slot in _core_goal_slots(block_title, total)],
                completed_goal_tags=[tag for _, tag in completed_assignments],
            )
        )
        # Elective blocks are optional pools — don't schedule them as required.
        # For required blocks, only add as many courses as the block actually needs.
        if not rb.get("is_elective", False) and needed > 0:
            remaining_in_block = [c for c in courses if c not in completed_courses]
            for c in remaining_in_block[:needed]:
                if c not in all_core_courses:
                    all_core_courses.append(c)

    return curriculum_name, blocks, all_core_courses


def _term_index(term: str) -> int:
    """Convert a display term into a sortable four-terms-per-year index.

    Args:
        term: Term formatted as ``Season YYYY``.

    Returns:
        Integer index used for chronological comparisons.

    Raises:
        ValueError: If the term format or season is invalid.
    """
    season, year = term.split()
    return int(year) * 4 + _SEASONS.index(season)


def current_term() -> str:
    """Return the planning term that contains today's date.

    Returns:
        Current term formatted as ``Season YYYY``.
    """
    today = date.today()
    month = today.month
    year = today.year
    if month <= 5:
        season = "Spring"
    elif month <= 8:
        season = "Summer"
    elif month <= 11:
        season = "Fall"
    else:
        season = "Winter"
    return f"{season} {year}"


def terms_between(start: str, end: str) -> List[str]:
    """Build the inclusive chronological sequence between two terms.

    Args:
        start: First term formatted as ``Season YYYY``.
        end: Last term formatted as ``Season YYYY``.

    Returns:
        All terms from ``start`` through ``end``, inclusive.

    Raises:
        ValueError: If either term has an invalid format or season.
    """
    start_idx = _term_index(start)
    end_idx = _term_index(end)
    terms: List[str] = []
    for i in range(start_idx, end_idx + 1):
        year = i // 4
        season = _SEASONS[i % 4]
        terms.append(f"{season} {year}")
    return terms


def load_catalog(path: Path) -> Dict[str, Dict]:
    """Load a school's curated catalog and enrich matching rows from the DB.

    The curated file remains the eligibility boundary; database rows may add
    current metadata but cannot introduce courses from unrelated schools.

    Args:
        path: Path to the school's JSON catalog.

    Returns:
        Merged catalog entries keyed by course code.

    Raises:
        FileNotFoundError: If the curated catalog does not exist.
        json.JSONDecodeError: If the curated catalog is invalid JSON.
    """
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    json_catalog: Dict[str, Dict] = {course["code"]: course for course in data}

    db_catalog = _load_catalog_from_db()
    if not db_catalog:
        return json_catalog

    # A school catalog is an eligibility boundary.  The database contains courses
    # from every Rutgers school, so unioning all DB rows here contaminated every
    # program catalog and made unrelated courses available as electives.  DB data
    # may enrich a course already present in this school's curated catalog, but it
    # must not expand the catalog.
    merged: Dict[str, Dict] = {}
    for code in json_catalog:
        if code in db_catalog:
            entry = dict(db_catalog[code])
            json_entry = json_catalog.get(code, {})
            entry["prerequisites"] = json_entry.get("prerequisites", [])
            entry["corequisites"] = json_entry.get("corequisites", [])
            if json_entry.get("title"):
                entry["title"] = json_entry["title"]
        else:
            entry = dict(json_catalog[code])
            entry.setdefault("corequisites", [])
        merged[code] = entry
    return merged


def _load_requirements_from_db(
    school: str, degree_level: str, major_name: str, catalog_year: str
) -> Dict:
    """Load one program's requirements, including master-level fallbacks.

    Args:
        school: School abbreviation stored with the program.
        degree_level: Normalized degree level.
        major_name: Canonical program name.
        catalog_year: Catalog year to retrieve.

    Returns:
        A detached dictionary of program requirements.

    Raises:
        ValueError: If no compatible program record exists.
    """
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
        # Fallback: specific master sub-types → generic "master" (backward compat)
        if row is None and degree_level.startswith("master_"):
            row = (
                db.query(Program)
                .filter(
                    Program.school == school,
                    Program.degree_level == "master",
                    Program.major_name == major_name,
                    Program.catalog_year == catalog_year,
                )
                .first()
            )
        # Fallback: generic "master" → any master_* sub-type for this program
        if row is None and degree_level == "master":
            row = (
                db.query(Program)
                .filter(
                    Program.school == school,
                    Program.degree_level.like("master_%"),
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
        return dict(row.requirements)
    finally:
        db.close()


def _parse_major_entry(entry: str, level_raw: str) -> Tuple[str, Optional[str], str, Optional[str]]:
    """Returns (school, db_level, major_name, track_or_None)."""
    m = re.match(r'^(.+?)\s*\(([^)]+)\)\s*$', entry.strip())
    if not m:
        db_level = _DEGREE_LEVEL_MAP.get((level_raw, None))
        return "SAS", db_level, entry.strip().title(), None

    raw_name = m.group(1).strip()
    # Extract track: "Statistics — Data Science" → base="Statistics", track="Data Science"
    track: Optional[str] = None
    if " — " in raw_name:
        base, track = raw_name.split(" — ", 1)
        major_name = base.strip()
        track = track.strip()
    else:
        major_name = raw_name
    tokens = [t.strip().upper() for t in m.group(2).split(",")]

    _SCHOOLS = {"SAS", "SOE", "RBS", "SPPP", "MGSA", "SCI", "SMLR", "SEBS", "SSW", "SON", "EMSP", "GSE", "GSAPP"}
    school = next((t for t in tokens if t in _SCHOOLS), "SAS")
    level_token = next((t for t in tokens if t not in _SCHOOLS), "")

    db_level: Optional[str] = {
        "BS":              "bachelor_bs",
        "BA":              "bachelor_ba",
        "BFA":             "bachelor_bfa",
        "BM":              "bachelor_bm",
        "BSBA":            "bachelor_bsba",
        "BSLA":            "bachelor_bsla",
        "BACHELOR_BSLA":   "bachelor_bsla",
        "MINOR":           "minor",
        "MS":              "master_ms",
        "MA":              "master_ma",
        "MAT":             "master_mat",
        "MENG":            "master_meng",
        "PHD":             "doctorate",
        "PSYD":            "professional_doctorate",
        "EDD":             "professional_doctorate",
        "PHARMD":          "professional_doctorate",
        "DNP":             "professional_doctorate",
        "MCRP":            "master",
        "MPA":             "master",
        "MPH":             "master",
        "MPP":             "master",
        "MSW":             "master",
        "MFA":             "master",
        "MM":              "master",
        "MAT":             "master_mat",
        "MBA":             "master",
        "MLER":            "master",
        "MHRM":            "master",
        "MABA":            "master",
        "AS":              "associate",
        "CONCENTRATION":   "concentration",
        "DOCTORAL":        "doctoral",
        "CERTIFICATE":     "certificate",
    }.get(level_token)

    if db_level is None:
        db_level = _DEGREE_LEVEL_MAP.get((level_raw, None))

    return school, db_level, major_name, track


def _merge_requirements(programs: List[Dict]) -> Dict:
    """Combine requirements for a multi-program plan without losing quotas.

    Args:
        programs: Requirement mappings for selected majors, minors, or tracks.

    Returns:
        One planner-ready requirement mapping with deduplicated courses and
        independently preserved elective and choice groups.
    """
    merged_required: List[str] = []
    for p in programs:
        for c in p.get("required_courses", []):
            if c not in merged_required:
                merged_required.append(c)

    total_count = sum(p.get("electives", {}).get("count", 0) for p in programs)
    total_300 = sum(
        p.get("electives", {}).get("min_level_300_plus", 0) for p in programs
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
        # Preserve each quota independently. A unioned pool lets an elective
        # from one major satisfy another major's quota.
        "electives": {"count": 0, "options": []},
        "elective_groups": [dict(p.get("electives", {})) for p in programs if p.get("electives")],
        "science_requirements": [p["science_requirement"] for p in programs if p.get("science_requirement")],
        "statistics_requirements": [p["statistics_requirement"] for p in programs if p.get("statistics_requirement")],
        "requirement_groups": [
            dict(group)
            for p in programs
            for group in p.get("requirement_groups", [])
        ],
    }

    sci = next((p["science_requirement"] for p in programs if p.get("science_requirement")), None)
    if sci:
        result["science_requirement"] = sci

    stats = next(
        (p["statistics_requirement"] for p in programs if p.get("statistics_requirement")), None
    )
    if stats:
        result["statistics_requirement"] = stats

    for key in (
        "sci_intro_requirement", "advanced_core_requirement",
        "foundation_requirement", "practice_electives", "concept_electives",
        "diversity_requirement",
    ):
        val = next((p[key] for p in programs if p.get(key)), None)
        if val:
            result[key] = val

    return result


def _resolve_entry(entry: str, level_raw: str) -> Tuple[str, Dict]:
    """Resolve a selected display entry without confusing dashes in real names for tracks."""
    school, db_level, major_name, track = _parse_major_entry(entry, level_raw)
    if not db_level:
        raise ValueError(f"Unsupported degree level in program selection: {entry}")

    if track:
        exact_name = f"{major_name} — {track}"
        try:
            exact = _load_requirements_from_db(school, db_level, exact_name, CATALOG_YEAR)
        except ValueError:
            pass
        else:
            return exact_name, _apply_program_patches(school, db_level, exact_name, exact)

    requirements = _load_requirements_from_db(school, db_level, major_name, CATALOG_YEAR)
    requirements = _apply_program_patches(school, db_level, major_name, requirements)
    return major_name, _apply_track(requirements, track)


def resolve_program(request: PlanRequest) -> Dict:
    """Resolve selected programs into requirements and an eligible catalog.

    The combined catalog includes SAS dependencies needed by professional
    schools while each selected program's requirements remain authoritative.

    Args:
        request: Planning request containing degree and program selections.

    Returns:
        Catalog, merged requirements, and per-program metadata.

    Raises:
        ValueError: If no selected program can be resolved.
        FileNotFoundError: If no usable school catalog is available.
    """
    level_raw = request.degree_level.strip().lower()
    found: List[Dict] = []
    individual_programs: List[Dict] = []  # [{reqs, name, type}]

    for major_raw in request.majors:
        major_name, reqs = _resolve_entry(major_raw, level_raw)
        found.append(reqs)
        individual_programs.append({"reqs": reqs, "name": major_name, "type": "major"})

    for minor_raw in request.minors:
        if not minor_raw.strip():
            continue
        major_name, reqs = _resolve_entry(minor_raw, "minor")
        found.append(reqs)
        selected_track = reqs.get("selected_track")
        display_name = f"{major_name} — {selected_track}" if selected_track else major_name
        individual_programs.append({"reqs": reqs, "name": display_name, "type": "minor"})

    for conc_raw in (request.concentrations or []):
        if not conc_raw.strip():
            continue
        major_name, reqs = _resolve_entry(conc_raw, "concentration")
        found.append(reqs)
        individual_programs.append({"reqs": reqs, "name": major_name, "type": "concentration"})

    if not found:
        raise ValueError(
            f"No matching program found for majors={request.majors}, "
            f"minors={request.minors}, degree_level='{request.degree_level}'. "
            "Run: python -m management.seed_programs to populate the programs table."
        )

    merged_reqs = found[0] if len(found) == 1 else _merge_requirements(found)

    schools_seen: List[str] = []
    for p in found:
        s = p.get("school", "SAS")
        if s not in schools_seen:
            schools_seen.append(s)

    # Rutgers professional-school curricula routinely require SAS courses
    # (calculus, chemistry, physics, writing, statistics, etc.). Loading only
    # the owning school's catalog turns those real prerequisites into stubs or
    # leaves them unschedulable, which creates false "cannot finish" results.
    try:
        merged_catalog: Dict[str, Dict] = load_catalog(DATA_DIR / _SCHOOL_CATALOG["SAS"])
    except FileNotFoundError:
        merged_catalog = {}
    for school in schools_seen:
        cat_file = _SCHOOL_CATALOG.get(school)
        if cat_file:
            try:
                school_cat = load_catalog(DATA_DIR / cat_file)
                merged_catalog.update(school_cat)
            except FileNotFoundError:
                pass

    if not merged_catalog:
        merged_catalog = load_catalog(DATA_DIR / _SCHOOL_CATALOG["SAS"])

    return {
        "catalog": merged_catalog,
        "requirements": merged_reqs,
        "individual_programs": individual_programs,
    }


def _resolve_choice_requirement(req: Dict, completed: Set[str], catalog: Dict) -> Optional[str]:
    """Choose the least burdensome unsatisfied option from a choice rule.

    Args:
        req: Choice requirement containing course options.
        completed: Courses already completed or otherwise satisfied.
        catalog: Available course metadata.

    Returns:
        A course code to schedule, or ``None`` when already satisfied or empty.
    """
    if not req:
        return None
    options: List[str] = req.get("options", [])
    if not options:
        return None
    if any(o in completed for o in options):
        return None
    candidates = [option for option in options if option in catalog]
    return min(candidates, key=lambda code: _core_candidate_key(code, catalog, completed), default=None)


def _resolve_science_courses(requirements: Dict, completed: Set[str], catalog: Optional[Dict[str, Dict]] = None) -> List[str]:
    """Select the remaining courses from the best science sequence option.

    Args:
        requirements: Program requirements containing science alternatives.
        completed: Courses already satisfied.
        catalog: Optional metadata used to minimize prerequisite burden.

    Returns:
        Unsatisfied course codes from the selected science sequence.
    """
    sci_req = requirements.get("science_requirement", {})
    if not sci_req:
        return []

    options: List[List[str]] = sci_req.get("options", [])
    if not options:
        return []

    for option in options:
        if all(c in completed for c in option):
            return []

    partial = [option for option in options if any(c in completed for c in option)]
    candidates = partial or options
    if catalog:
        def option_key(option: List[str]) -> Tuple:
            """Rank a science sequence by prerequisites and remaining credits."""
            missing = [code for code in option if code not in completed]
            prerequisite_codes = set().union(*(
                _prerequisite_closure(code, catalog, completed) for code in missing
            )) if missing else set()
            return (
                sum(float(catalog.get(code, {}).get("credits") or 0) for code in prerequisite_codes),
                len(prerequisite_codes),
                sum(float(catalog.get(code, {}).get("credits") or 0) for code in missing),
                tuple(missing),
            )
        candidates = sorted(candidates, key=option_key)
    return [c for c in candidates[0] if c not in completed]


def _resolve_stats_course(requirements: Dict, completed: Set[str], catalog: Optional[Dict[str, Dict]] = None) -> Optional[str]:
    """Choose one unsatisfied statistics option with minimal prerequisites.

    Args:
        requirements: Program requirements containing statistics alternatives.
        completed: Courses already satisfied.
        catalog: Optional metadata used to rank valid options.

    Returns:
        The selected course code, or ``None`` if the requirement is satisfied.
    """
    stats_req = requirements.get("statistics_requirement", {})
    if not stats_req:
        return None
    options: List[str] = stats_req.get("options", [])
    if not options or any(c in completed for c in options):
        return None
    candidates = [option for option in options if not catalog or option in catalog]
    if catalog:
        return min(candidates, key=lambda code: _core_candidate_key(code, catalog, completed), default=None)
    return candidates[0] if candidates else None


def _get_course_level(code: str) -> int:
    """Infer a course's hundred-level bucket from its code.

    Args:
        code: Course identifier containing an optional numeric component.

    Returns:
        The rounded-down hundred level, or zero when no number is present.
    """
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
    min_level_400_plus: int = 0,
    catalog: Optional[Dict[str, Dict]] = None,
) -> Tuple[List[str], List[str]]:
    """Select electives while prioritizing required upper-level quotas.

    Args:
        elective_options: Approved elective course codes.
        elective_count: Total number of electives still needed.
        min_level_300_plus: Remaining quota at the 300 level or above.
        required: Courses already selected as requirements.
        completed: Courses already satisfied.
        min_level_400_plus: Remaining quota at the 400 level or above.
        catalog: Optional metadata used to favor lighter prerequisites.

    Returns:
        Selected elective codes and warnings for unfillable constraints.
    """
    available = [c for c in elective_options if c not in required and c not in completed]
    if catalog:
        satisfied = completed | set(required)
        available.sort(key=lambda code: _core_candidate_key(code, catalog, satisfied))
    high400 = [c for c in available if _get_course_level(c) >= 400]
    high300 = [c for c in available if _get_course_level(c) >= 300]

    chosen: List[str] = []
    warnings_out: List[str] = []

    if min_level_300_plus > elective_count or min_level_400_plus > elective_count:
        warnings_out.append(
            "Elective level minimum exceeds the elective quota; requirement data needs review."
        )
    min_level_300_plus = min(min_level_300_plus, elective_count)
    min_level_400_plus = min(min_level_400_plus, elective_count)

    for c in high400:
        if len(chosen) >= min_level_400_plus:
            break
        chosen.append(c)

    if len(chosen) < min_level_400_plus:
        warnings_out.append(
            f"Only {len(chosen)} elective(s) at 400+ level available "
            f"(need {min_level_400_plus}). Consider different elective options."
        )

    slots_300_needed = max(0, min_level_300_plus - len([c for c in chosen if _get_course_level(c) >= 300]))
    for c in high300:
        if slots_300_needed <= 0:
            break
        if c not in chosen:
            chosen.append(c)
            slots_300_needed -= 1

    if slots_300_needed > 0:
        warnings_out.append(
            f"Insufficient elective(s) at 300+ level to meet requirement. "
            "Consider different elective options."
        )

    for c in available:
        if len(chosen) >= elective_count:
            break
        if c not in chosen:
            chosen.append(c)

    return chosen, warnings_out


def _season_has_data(catalog: Dict[str, Dict], season: str) -> bool:
    """Check whether any catalog row contains affirmative offering data.

    Args:
        catalog: Course metadata keyed by code.
        season: Season whose offering flag should be inspected.

    Returns:
        ``True`` when the catalog has meaningful data for that season.
    """
    flag = f"{season.lower()}_offered"
    return any(entry.get(flag, False) for entry in catalog.values())


def _is_offered(course: Dict, season: str, season_has_data: Dict[str, bool]) -> bool:
    """Determine whether a course may be scheduled in a season.

    Args:
        course: Catalog metadata for one course.
        season: Candidate scheduling season.
        season_has_data: Whether each season has reliable offering data.

    Returns:
        The explicit offering value, defaulting permissively when data is absent.
    """
    if not season_has_data.get(season, False):
        return True
    flag = f"{season.lower()}_offered"
    return course.get(flag, True)


def _normalize_graduate_requirements(requirements: Dict) -> Tuple[Dict, List[str]]:
    """
    Normalize non-standard graduate program structures into the planner's
    expected format: {required_courses: [...], electives: {count, options}}.

    Returns (normalized_requirements, extra_warnings).
    Only uses course codes explicitly present in the data — no invented courses.
    """
    warnings_out: List[str] = []
    normalized = dict(requirements)

    # ── Step 1: Collect required courses from all known field names ──
    required: List[str] = list(requirements.get("required_courses") or [])
    seen_req: Set[str] = set(required)

    def _add(code: str) -> None:
        """Append a valid required code once while preserving source order."""
        if isinstance(code, str) and code not in seen_req:
            required.append(code)
            seen_req.add(code)

    # required_core_courses (list) — e.g. EMSP Medicinal Chemistry, GSAPP MABA
    rcc = requirements.get("required_core_courses")
    if isinstance(rcc, list):
        for c in rcc:
            _add(c)

    # additional_required_courses (list)
    for c in (requirements.get("additional_required_courses") or []):
        _add(c)

    # gse_required_courses (dict with "courses" key)
    gse_rc = requirements.get("gse_required_courses")
    if isinstance(gse_rc, dict):
        for c in gse_rc.get("courses", []):
            _add(c)

    # core_courses — can be either a flat {"required": [...]} (EdD programs)
    # or a nested semester structure handled in Step 2. Handle the flat case here.
    cc_val = requirements.get("core_courses", {})
    if isinstance(cc_val, dict):
        for c in cc_val.get("courses", []):
            _add(c)
        for c in cc_val.get("required", []):
            _add(c)

    # Fields that are dicts holding course lists under "courses", "required",
    # a singular "course" key, or nested sub-dicts with their own "courses"/"required".
    _DICT_COURSE_FIELDS = (
        "foundation_courses", "core_required", "specialization_required",
        "required_core", "capstone", "capstone_requirement",
        "advanced_practicum", "practicum", "practicum_sequence",
        "required_proseminars", "required_foundational",
        "studio", "lab_rotation", "research_requirement",
        "required_research_methods", "concentration_courses",
        "seminar_field", "curriculum_areas",
    )
    for field in _DICT_COURSE_FIELDS:
        val = requirements.get(field)
        if not isinstance(val, dict):
            continue
        # Direct "courses" list
        for c in val.get("courses", []):
            _add(c)
        # Direct "required" list
        for c in val.get("required", []):
            _add(c)
        # Singular "course" key (e.g. lab_rotation)
        single = val.get("course")
        if single:
            _add(single)
        # Nested sub-dicts with "courses" or "required" (e.g. MHRM required_core,
        # GSE EdD concentration_courses certification_option)
        for subval in val.values():
            if isinstance(subval, dict):
                for c in subval.get("courses", []):
                    _add(c)
                for c in subval.get("required", []):
                    _add(c)

    # Sub-elective pools: pick `count` (default 1) from options list.
    # Used for single-course requirements like seminars, practicum distributions,
    # capstone options, and choice requirements.
    _PICK_N_FIELDS = (
        "seminar_requirement", "advanced_practice_distribution",
        "advanced_contemporary_policy", "intro_requirement",
        "writing_requirement", "gateway_requirement",
        "management_requirement",
    )
    for field in _PICK_N_FIELDS:
        val = requirements.get(field)
        if isinstance(val, dict) and "options" in val:
            n = val.get("count", 1)
            for c in val["options"]:
                if n <= 0:
                    break
                if isinstance(c, str) and c not in seen_req:
                    _add(c)
                    n -= 1

    # capstone_options (bare list — pick 1)
    co_opts = requirements.get("capstone_options")
    if isinstance(co_opts, list):
        for c in co_opts:
            if isinstance(c, str) and c not in seen_req:
                _add(c)
                break

    # competency_areas / competency_categories: each nested area has count + options → pick 1 per area
    for comp_field in ("competency_areas", "competency_categories"):
        comp = requirements.get(comp_field)
        if not isinstance(comp, dict):
            continue
        for area_val in comp.values():
            if not isinstance(area_val, dict) or "options" not in area_val:
                continue
            n = area_val.get("count", 1)
            for c in area_val["options"]:
                if n <= 0:
                    break
                if isinstance(c, str) and c not in seen_req:
                    _add(c)
                    n -= 1

    # curriculum dict (EMSP PharmD): nested by year → semester → "required" list
    curriculum = requirements.get("curriculum")
    if isinstance(curriculum, dict):
        for year_data in curriculum.values():
            if not isinstance(year_data, dict):
                continue
            for sem_data in year_data.values():
                if isinstance(sem_data, dict):
                    for c in sem_data.get("required", []):
                        _add(c)
                    # writing_elective or similar choice sub-fields
                    for subval in sem_data.values():
                        if isinstance(subval, dict) and "options" in subval:
                            opts = subval["options"]
                            if opts:
                                _add(opts[0])

    # ── Step 1b: General scan — any top-level dict value with an "options" list and a
    # "count" key that we haven't already handled explicitly gets treated as a pick-N pool.
    # This catches fields like sas_electives, bloustein_electives, planning_specialization,
    # core_requirement, track_requirement, distribution_requirement, etc.
    _ALREADY_HANDLED = {
        "required_courses", "electives", "science_requirement", "statistics_requirement",
        "sci_intro_requirement", "advanced_core_requirement", "foundation_requirement",
        "practice_electives", "concept_electives", "diversity_requirement",
        "required_core_courses", "additional_required_courses", "gse_required_courses",
        "category_a_courses", "category_b_courses", "core_courses", "tracks",
        "competency_areas", "competency_categories", "curriculum",
        # metadata
        "school", "degree_level", "major_name", "catalog_year", "constraints", "notes",
        "description", "program_years", "total_credits", "total_credits_approx",
    } | set(_DICT_COURSE_FIELDS) | set(_PICK_N_FIELDS)

    for field, val in requirements.items():
        if field in _ALREADY_HANDLED:
            continue
        if not isinstance(val, dict) or "options" not in val:
            continue
        opts = [o for o in val["options"] if isinstance(o, str)]
        if not opts:
            continue
        n = val.get("count", 1)
        picked = 0
        for c in opts:
            if picked >= n:
                break
            if c not in seen_req:
                _add(c)
                picked += 1

    # ── Step 2: Handle complex structures that hold all courses in non-standard fields ──
    # Only enter these branches when the standard fields above yielded nothing.
    if not required:
        total_credits: int = requirements.get("total_credits", 30)
        elective_options: List[str] = []

        # category_a_courses / category_b_courses (e.g. SAS CS MS)
        cat_a = requirements.get("category_a_courses", {})
        cat_b = requirements.get("category_b_courses", {})
        if cat_a or cat_b:
            seen: Set[str] = set()
            for opt in cat_a.get("options", []) + cat_b.get("options", []):
                if opt not in seen:
                    elective_options.append(opt)
                    seen.add(opt)
            warnings_out.append(
                "This program uses flexible categories (A/B). "
                "The schedule below shows representative courses from the approved pool — "
                "consult your adviser to finalize your selection."
            )
            normalized["required_courses"] = []
            normalized["electives"] = {
                "count": total_credits // 3,
                "options": elective_options,
                "any_from_catalog": False,
            }
            return normalized, warnings_out

        # core_courses with semester sub-dicts (e.g. SAS Economics MA)
        # Check BEFORE tracks because Economics MA has both.
        core_courses = requirements.get("core_courses", {})
        if core_courses and isinstance(core_courses, dict):
            seen = set()
            for sem_data in core_courses.values():
                if not isinstance(sem_data, dict):
                    continue
                for c in sem_data.get("required", []):
                    if c not in seen:
                        required.append(c)
                        seen.add(c)
                for val in sem_data.values():
                    if isinstance(val, dict) and "options" in val:
                        for c in val["options"]:
                            if c not in seen:
                                elective_options.append(c)
                                seen.add(c)
            for track_data in requirements.get("tracks", {}).values():
                if not isinstance(track_data, dict):
                    continue
                for key in ("semester_3_required", "recommended_electives"):
                    for c in track_data.get(key, []):
                        if c not in seen:
                            elective_options.append(c)
                            seen.add(c)
            spent = len(required) * 3
            normalized["required_courses"] = required
            normalized["electives"] = {
                "count": max(0, (total_credits - spent) // 3),
                "options": elective_options,
                "any_from_catalog": False,
            }
            return normalized, warnings_out

        # tracks dict with nested course lists (e.g. SOE ECE MS)
        tracks = requirements.get("tracks", {})
        if tracks and isinstance(tracks, dict) and any(
            isinstance(v, dict) for v in tracks.values()
        ):
            seen = set()
            for track_data in tracks.values():
                if not isinstance(track_data, dict):
                    continue
                for val in track_data.values():
                    if isinstance(val, list):
                        for c in val:
                            if isinstance(c, str) and c not in seen:
                                elective_options.append(c)
                                seen.add(c)
            track_names = ", ".join(k.replace("_", " ").title() for k in tracks)
            warnings_out.append(
                f"This program offers specialization tracks ({track_names}). "
                "The schedule shows courses from all tracks — "
                "consult your adviser to select the right track for your goals."
            )
            normalized["required_courses"] = []
            normalized["electives"] = {
                "count": total_credits // 3,
                "options": elective_options,
                "any_from_catalog": False,
            }
            return normalized, warnings_out

    # ── Step 3: Write back the (possibly augmented) required_courses ──
    normalized["required_courses"] = required

    # ── Step 4: Fix electives — normalise alternative count field names ──
    electives = dict(requirements.get("electives", {}))
    if electives and "count" not in electives:
        for alt in ("count_capstone_track", "count_thesis_track", "count_non_thesis"):
            if alt in electives:
                electives["count"] = electives[alt]
                break
    # If electives has options but still no count, infer from total_credits
    if electives and "count" not in electives and electives.get("options"):
        total_cr = requirements.get("total_credits", 0)
        if total_cr:
            used_cr = sum(3 for _ in required)  # approximate 3cr/course
            remaining_cr = max(0, total_cr - used_cr)
            electives["count"] = max(1, remaining_cr // 3)
        else:
            electives["count"] = len(electives["options"])
    if electives:
        normalized["electives"] = electives

    return normalized, warnings_out


def _build_catalog_stubs(codes: List[str], catalog: Dict[str, Dict]) -> List[str]:
    """
    For course codes referenced in requirements but missing from the catalog,
    insert a minimal stub so the planner can schedule them.
    Returns list of codes that got stubs (for warning purposes).
    Uses only the course code as the title — no invented names.
    Assumes 3 credits, which is standard for graduate courses.
    """
    stubbed: List[str] = []
    for code in codes:
        if code not in catalog:
            catalog[code] = {
                "code": code,
                "title": code,
                "credits": 3,
                "prerequisites": [],
            }
            stubbed.append(code)
    return stubbed


def _collect_missing_prereqs(
    codes: List[str],
    catalog: Dict[str, Dict],
    completed: Set[str],
    required: List[str],
) -> None:
    """Add transitive, catalogued prerequisites to the required course list.

    Args:
        codes: Courses whose prerequisite trees should be traversed.
        catalog: Course metadata keyed by code.
        completed: Courses that already satisfy prerequisites.
        required: Mutable required-course list updated in place.
    """
    required_set: Set[str] = set(required)
    stack = list(codes)
    while stack:
        code = stack.pop()
        for prereq in catalog.get(code, {}).get("prerequisites", []):
            if prereq not in completed and prereq not in required_set and prereq in catalog:
                required.append(prereq)
                required_set.add(prereq)
                stack.append(prereq)


def heuristic_plan(request: PlanRequest) -> PlanResponse:
    """Build an explainable term-by-term plan using catalog constraints.

    This is the planner's orchestration entry point: it resolves program rules,
    accounts for prior work, selects alternatives, expands prerequisites, and
    schedules eligible courses within term and credit limits.

    Args:
        request: Student selections, history, time horizon, and load limits.

    Returns:
        Planned terms, requirement status, warnings, and program summaries.

    Raises:
        ValueError: If program selections or planning terms are invalid.
    """
    program = resolve_program(request)
    catalog: Dict[str, Dict] = program["catalog"]
    requirements: Dict = program["requirements"]

    completed_input: Set[str] = {c.strip().upper() for c in request.completed_courses}
    raw_to_alias = {
        entry.get("raw_code"): code
        for code, entry in catalog.items()
        if entry.get("raw_code")
    }
    completed: Set[str] = {
        raw_to_alias.get(code, code) for code in completed_input
    }
    in_progress: Set[str] = {
        raw_to_alias.get(code.strip().upper(), code.strip().upper())
        for code in (request.in_progress_courses or [])
    }
    in_progress -= completed
    covered: Set[str] = completed | in_progress
    in_progress_terms: Dict[str, str] = {
        raw_to_alias.get(code.strip().upper(), code.strip().upper()): term.strip()
        for code, term in (request.in_progress_terms or {}).items()
        if isinstance(code, str) and isinstance(term, str)
    }
    in_progress_credit_hours: Dict[str, float] = {
        raw_to_alias.get(code.strip().upper(), code.strip().upper()): float(credits)
        for code, credits in (request.in_progress_credit_hours or {}).items()
        if isinstance(code, str) and isinstance(credits, (int, float)) and credits >= 0
    }
    course_grades = {
        raw_to_alias.get(code, code): grade
        for code, grade in request.course_grades.items()
    }
    warnings: List[str] = []

    # Normalize non-standard graduate program structures (tracks, categories, etc.)
    requirements, grad_warnings = _normalize_graduate_requirements(requirements)
    warnings.extend(grad_warnings)

    # Check for departmental open-ended requirements (e.g. MAE MS "5 MAE 650-level courses")
    dept_req = requirements.get("departmental_courses", {})
    if dept_req and isinstance(dept_req, dict) and dept_req.get("min_count"):
        warnings.append(
            f"Note: {dept_req.get('description', 'Additional departmental courses required')}. "
            "These must be selected with your adviser — no specific course codes are defined in this data."
        )

    for code in sorted(completed):
        if code not in catalog:
            warnings.append(f"Completed course '{code}' not found in catalog — treated as satisfied prereq but may be a typo.")

    required: List[str] = list(requirements.get("required_courses", []))

    # Load core curriculum (general education) requirements for the student's school
    _primary_school = "SAS"
    if request.majors:
        _primary_school, _, _, _ = _parse_major_entry(request.majors[0], request.degree_level.strip().lower())
    core_curriculum_name, core_curriculum_blocks, core_courses = _load_core_curriculum(
        _primary_school, completed
    )
    _core_tag_index = _get_sas_core_index() if _primary_school in {"SAS", "SEBS", "RBS", "SPPP", "SON", "SOE", "SCI", "SMLR"} else {}

    # Build available_courses per incomplete block so the UI can show what satisfies each requirement
    if _core_tag_index:
        _tag_to_courses: dict[str, list[str]] = {}
        for _code, _tags in _core_tag_index.items():
            for _tag in _tags:
                _tag_to_courses.setdefault(_tag, []).append(_code)

        def _sort_by_level(codes: list[str]) -> list[str]:
            """Sort core options by their numeric course code for display."""
            def _level(c: str) -> int:
                """Extract a numeric sort value, placing nonnumeric codes last."""
                m = re.search(r"\d+", c)
                return int(m.group()) if m else 9999
            return sorted(codes, key=_level)

        for blk in core_curriculum_blocks:
            if blk.needed > 0:
                _block_tags = _tags_for_block(blk.title)
                _avail: list[str] = []
                _seen: set[str] = set()
                for _tag in _block_tags:
                    for _c in _tag_to_courses.get(_tag, []):
                        if _c not in completed and _c not in _seen:
                            _avail.append(_c)
                            _seen.add(_c)
                object.__setattr__(blk, "available_courses", _sort_by_level(_avail))

    for c in core_courses:
        if c not in required:
            required.append(c)
    # Warn about open-ended blocks (no known course list)
    for blk in core_curriculum_blocks:
        if blk.needed > 0 and not blk.courses:
            warnings.append(
                f"Core requirement '{blk.title}' needs {blk.needed} more course(s) "
                "— select from Degree Navigator (specific options not tracked here)."
            )

    # Build minimal stubs for graduate courses referenced in requirements but absent from catalog.
    # This prevents them from being silently dropped. Title = course code, credits = 3 (standard).
    all_referenced = list(required) + list(requirements.get("electives", {}).get("options", []))
    for group in requirements.get("requirement_groups", []):
        all_referenced.extend(group.get("options", []))
    # Graduate feeds sometimes list valid adviser-controlled courses before a
    # full catalog row is available. For undergraduate plans, stub only an
    # explicit required course—not every choice option—so a missing catalog row
    # cannot beat a verified option (for example CS425 over CS440).
    is_graduate = request.degree_level.strip().lower() in {"master", "doctorate"}
    # Preserve explicit required courses for older curated undergraduate feeds,
    # but never create fake candidates for an undergraduate choice group.
    stubbed = _build_catalog_stubs(all_referenced if is_graduate else required, catalog)
    if stubbed:
        warnings.append(
            f"Full catalog details unavailable for {len(stubbed)} graduate course(s) "
            f"({', '.join(stubbed[:6])}{'…' if len(stubbed) > 6 else ''}). "
            "Credits shown as 3 per course (standard graduate unit). Verify with the registrar."
        )

    for code in _resolve_science_courses(requirements, covered, catalog):
        if code not in required:
            required.append(code)

    for science_group in requirements.get("science_requirements", [])[1:]:
        for code in _resolve_science_courses({"science_requirement": science_group}, covered, catalog):
            if code not in required:
                required.append(code)

    stat_code = _resolve_stats_course(requirements, covered, catalog)
    if stat_code and stat_code not in required:
        required.append(stat_code)
    for statistics_group in requirements.get("statistics_requirements", [])[1:]:
        stat_code = _resolve_stats_course({"statistics_requirement": statistics_group}, covered, catalog)
        if stat_code and stat_code not in required:
            required.append(stat_code)

    electives = requirements.get("electives", {})
    elective_count: int = electives.get("count", 0)
    # Scraped requirement data occasionally contains duplicate options.  Without
    # deduplication one completed course can incorrectly satisfy multiple slots.
    elective_options: List[str] = list(dict.fromkeys(electives.get("options", [])))
    min_level_300_plus: int = electives.get("min_level_300_plus", 0)

    if electives.get("any_from_catalog") and not elective_options:
        elective_options = [c for c in catalog if c not in required]

    elective_options = [c for c in elective_options if c in catalog]

    completed_elec = [c for c in elective_options if c in covered]
    completed_elec_high = [c for c in completed_elec if _get_course_level(c) >= 300]
    elective_count = max(0, elective_count - len(completed_elec))
    min_level_300_plus = max(0, min_level_300_plus - len(completed_elec_high))

    elective_400_plus: int = electives.get("min_level_400_plus", 0)
    completed_elec_400 = [c for c in completed_elec if _get_course_level(c) >= 400]
    elective_400_plus = max(0, elective_400_plus - len(completed_elec_400))

    chosen_electives, elective_warnings = _select_electives(
        elective_options, elective_count, min_level_300_plus, required, covered,
        min_level_400_plus=elective_400_plus, catalog=catalog,
    )
    warnings.extend(elective_warnings)
    required += chosen_electives

    elective_set: Set[str] = set(chosen_electives)
    full_elective_pool: List[str] = [
        c for c in elective_options if c not in covered
    ]

    # Generic choose-N groups preserve track/category boundaries. Open adviser
    # pools remain visibly incomplete rather than being filled with guessed courses.
    consumed_group_courses: Set[str] = set()
    for group in requirements.get("requirement_groups", []):
        options = [c for c in dict.fromkeys(group.get("options", [])) if c in catalog]
        count = int(group.get("count", 1))
        completed_group = [c for c in options if c in covered and c not in consumed_group_courses]
        consumed_group_courses.update(completed_group[:count])
        needed = max(0, count - len(completed_group))
        chosen, group_warnings = _select_electives(
            options, needed, 0, required, covered, catalog=catalog
        )
        warnings.extend(group_warnings)
        for code in chosen:
            if code not in required:
                required.append(code)
                elective_set.add(code)
                consumed_group_courses.add(code)
        for code in options:
            if code not in covered and code not in full_elective_pool:
                full_elective_pool.append(code)
        if group.get("open_pool"):
            warnings.append(f"{group.get('label', 'Adviser-selected requirement')}: {group['open_pool']}")

    # Multi-program plans keep elective quotas separate and use a course at most
    # once across groups unless a future typed rule explicitly allows overlap.
    consumed_completed: Set[str] = set()
    for group in requirements.get("elective_groups", []):
        group_options = [
            c for c in dict.fromkeys(group.get("options", []))
            if c in catalog
        ]
        if group.get("any_from_catalog") and not group_options:
            group_options = [c for c in catalog if c not in required]
        group_completed = [
            c for c in group_options
            if c in covered and c not in consumed_completed
        ]
        consumed_completed.update(group_completed)
        group_count = max(0, group.get("count", 0) - len(group_completed))
        group_300 = max(
            0,
            group.get("min_level_300_plus", 0)
            - len([c for c in group_completed if _get_course_level(c) >= 300]),
        )
        group_400 = max(
            0,
            group.get("min_level_400_plus", 0)
            - len([c for c in group_completed if _get_course_level(c) >= 400]),
        )
        selected, group_warnings = _select_electives(
            group_options, group_count, group_300, required, covered, group_400, catalog
        )
        warnings.extend(group_warnings)
        for code in selected:
            if code not in required:
                required.append(code)
                elective_set.add(code)
        for code in group_options:
            if code not in covered and code not in full_elective_pool:
                full_elective_pool.append(code)

    for req_key in ("sci_intro_requirement", "advanced_core_requirement", "foundation_requirement"):
        opt = _resolve_choice_requirement(requirements.get(req_key, {}), covered, catalog)
        if opt and opt not in required:
            required.append(opt)

    for pool_key in ("practice_electives", "concept_electives"):
        pool_req = requirements.get(pool_key, {})
        if not pool_req:
            continue
        pool_opts = [c for c in dict.fromkeys(pool_req.get("options", [])) if c in catalog]
        pool_count = pool_req.get("count", 0)
        pool_300 = pool_req.get("min_level_300_plus", 0)
        pool_400 = pool_req.get("min_level_400_plus", 0)

        completed_pool = [c for c in pool_opts if c in covered]
        pool_count = max(0, pool_count - len(completed_pool))
        pool_300 = max(0, pool_300 - len([c for c in completed_pool if _get_course_level(c) >= 300]))
        pool_400 = max(0, pool_400 - len([c for c in completed_pool if _get_course_level(c) >= 400]))

        chosen_pool, pool_warnings = _select_electives(
            pool_opts, pool_count, pool_300, required, covered, pool_400, catalog
        )
        warnings.extend(pool_warnings)
        for c in chosen_pool:
            if c not in required:
                required.append(c)
                elective_set.add(c)
        for c in pool_opts:
            if c not in covered and c not in full_elective_pool:
                full_elective_pool.append(c)

    # For each unfulfilled core block, choose courses that add a distinct goal
    # while minimizing the full prerequisite burden.
    if _core_tag_index:
        for blk in core_curriculum_blocks:
            if blk.needed <= 0 or blk.total_courses is None:
                continue
            tags = _tags_for_block(blk.title)
            if not tags:
                continue
            req_set = set(required)
            existing = [
                code for code in [*in_progress, *required]
                if code not in completed and tags.intersection(_core_tag_index.get(code, []))
            ]
            matched = _match_core_courses(
                blk.title, blk.total_courses, [*blk.completed, *existing], _core_tag_index
            )
            candidates = sorted(
                [c for c, ctags in _core_tag_index.items()
                 if tags.intersection(set(ctags)) and c in catalog
                 and c not in covered and c not in req_set],
                key=lambda c: _core_candidate_key(c, catalog, covered | req_set),
            )
            selected: List[str] = []
            for candidate in candidates:
                trial = _match_core_courses(
                    blk.title, blk.total_courses, [*matched, *selected, candidate], _core_tag_index
                )
                if len(trial) > len(_match_core_courses(
                    blk.title, blk.total_courses, [*matched, *selected], _core_tag_index
                )):
                    selected.append(candidate)
                if len(trial) >= blk.total_courses:
                    break
            for code in selected:
                required.append(code)
                req_set.add(code)
            # Expose all candidates as swap options
            for c in candidates:
                if c not in full_elective_pool:
                    full_elective_pool.append(c)

    _collect_missing_prereqs(required, catalog, covered, required)

    # A bachelor's plan is not complete when the named major/core requirements
    # add up to fewer than the university's 120-credit degree minimum. Fill the
    # remaining space with real, offered catalog courses that have no hidden
    # prerequisite chain. These remain editable general electives in the UI.
    degree_elective_set: Set[str] = set()
    catalog_completed_credits = sum(
        float(catalog.get(code, {}).get("credits") or 0) for code in completed
    )
    completed_credits_count = max(catalog_completed_credits, request.earned_degree_credits)
    in_progress_credits = sum(
        in_progress_credit_hours.get(
            code, float(catalog.get(code, {}).get("credits") or 0)
        )
        for code in in_progress - completed
    )
    degree_credits = completed_credits_count + in_progress_credits + sum(
        float(catalog.get(code, {}).get("credits") or 0)
        for code in required if code not in covered
    )
    degree_credit_minimum = 120 if request.degree_level.strip().lower() == "bachelor" else 0
    if degree_credit_minimum:
        counted = set(required) | covered
        candidates = sorted(
            (
                code for code, course in catalog.items()
                if code not in counted
                and float(course.get("credits") or 0) > 0
                and not course.get("prerequisites")
                and (
                    course.get("fall_offered", True)
                    or course.get("spring_offered", True)
                )
            ),
            key=lambda code: (_get_course_level(code), code),
        )
        # Prefer a varied set of subjects, then find an exact half-credit
        # combination whenever the catalog permits one. Avoiding an arbitrary
        # credit overshoot matters for programs whose eight-term capacity is
        # exactly 120 credits.
        subject_counts: Dict[str, int] = {}
        deferred: List[str] = []
        for code in candidates:
            subject = re.match(r"[A-Z]+", code)
            subject_key = subject.group() if subject else code
            if subject_counts.get(subject_key, 0) >= 2:
                deferred.append(code)
                continue
            subject_counts[subject_key] = subject_counts.get(subject_key, 0) + 1
        diversified = [code for code in candidates if code not in deferred] + deferred
        diversified.sort(key=lambda code: (
            {3.0: 0, 1.0: 1, 2.0: 2}.get(float(catalog[code]["credits"]), 3),
            _get_course_level(code),
            code,
        ))
        needed_units = max(0, round((degree_credit_minimum - degree_credits) * 2))
        combinations: Dict[int, List[str]] = {0: []}
        for code in diversified:
            units = round(float(catalog[code]["credits"]) * 2)
            if units <= 0 or units > needed_units:
                continue
            for subtotal, chosen in sorted(combinations.items(), reverse=True):
                new_total = subtotal + units
                if new_total <= needed_units and new_total not in combinations:
                    combinations[new_total] = [*chosen, code]
            if needed_units in combinations:
                break
        selected_degree_electives = combinations[max(combinations)]
        for code in selected_degree_electives:
            required.append(code)
            elective_set.add(code)
            degree_elective_set.add(code)
            degree_credits += float(catalog[code]["credits"])
        if degree_credits < degree_credit_minimum:
            warnings.append(
                f"Only {degree_credits:g} of the {degree_credit_minimum} credits required "
                "for this bachelor's degree could be populated from the verified catalog."
            )

    remaining = [c for c in required if c not in covered]
    total_credits_count = degree_credits

    # Build a map of each completed course → the requirement label it satisfies
    completed_course_map: Dict[str, str] = {}
    base_required = set(requirements.get("required_courses", []))
    for c in completed:
        if c in base_required:
            completed_course_map[c] = "Required"
    for c in completed_elec:
        if c not in completed_course_map:
            completed_course_map[c] = "Elective"
    for opt in requirements.get("science_requirement", {}).get("options", []):
        if isinstance(opt, list):
            for c in opt:
                if c in completed and c not in completed_course_map:
                    completed_course_map[c] = "Science Requirement"
        elif opt in completed and opt not in completed_course_map:
            completed_course_map[opt] = "Science Requirement"
    for c in requirements.get("statistics_requirement", {}).get("options", []):
        if c in completed and c not in completed_course_map:
            completed_course_map[c] = "Statistics Requirement"
    for blk in core_curriculum_blocks:
        short = blk.title.split(":")[-1].strip()
        for c in blk.completed:
            if c not in completed_course_map:
                completed_course_map[c] = f"Core: {short}"

    start = request.start_term or current_term()
    grad_term = " ".join(
        w.capitalize() if i == 0 else w for i, w in enumerate(request.target_grad_term.split())
    )
    all_terms = terms_between(start, grad_term)

    if not all_terms:
        warnings.append(
            f"Target graduation term '{grad_term}' is at or before "
            f"the start term '{start}'. Please choose a future graduation date."
        )
        return PlanResponse(terms=[], remaining_courses=remaining, warnings=warnings)

    if request.preferred_seasons is not None and len(request.preferred_seasons) == 0:
        warnings.append(
            "No semesters selected. Please choose at least one semester (Spring, Summer, Fall, or Winter)."
        )
        return PlanResponse(terms=[], remaining_courses=remaining, warnings=warnings)
    preferred: set = {s.capitalize() for s in (request.preferred_seasons or _SEASONS)}
    if not preferred:
        preferred = set(_SEASONS)
    terms = [t for t in all_terms if t.split()[0] in preferred]
    if not terms:
        warnings.append(
            "No terms remain after applying your season preferences. "
            "Please select at least one season (Spring, Summer, Fall, or Winter)."
        )
        return PlanResponse(terms=[], remaining_courses=remaining, warnings=warnings)

    remaining_set = set(remaining)
    G: nx.DiGraph = nx.DiGraph()
    for code in remaining:
        G.add_node(code)
        for prereq in catalog.get(code, {}).get("prerequisites", []):
            if prereq in remaining_set:
                G.add_edge(prereq, code)

    co_pulled: Set[str] = set()
    for code in remaining:
        for co in catalog.get(code, {}).get("corequisites", []):
            if co in remaining_set:
                co_pulled.add(co)

    try:
        topo_order = list(nx.topological_sort(G))
        # Schedule prerequisite bottlenecks before flexible courses. A plain
        # topological order is valid but can consume a term's credit capacity
        # with unrelated electives and delay a long prerequisite chain until
        # graduation, falsely reporting that a normal four-year plan is
        # impossible.
        depth_cache: Dict[str, int] = {}
        def critical_depth(node: str) -> int:
            """Return the longest downstream prerequisite path from a course."""
            if node not in depth_cache:
                successors = list(G.successors(node))
                depth_cache[node] = 0 if not successors else 1 + max(critical_depth(child) for child in successors)
            return depth_cache[node]
        topo_position = {code: index for index, code in enumerate(topo_order)}
        queue = sorted(
            (c for c in topo_order if c in remaining_set and c not in co_pulled),
            key=lambda code: (-critical_depth(code), topo_position[code]),
        )
    except nx.NetworkXUnfeasible:
        warnings.append("Prerequisite cycle detected; scheduling without ordering guarantees.")
        queue = [c for c in remaining if c not in co_pulled]

    season_has_data = {s: _season_has_data(catalog, s) for s in _SEASONS}
    scheduled: Set[str] = set()
    planned_terms: List[TermPlan] = []

    for term_index, term in enumerate(terms):
        season = term.split()[0]
        # Apply season-specific credit caps per SAS policy:
        #   Summer: max 12 credits total (across Rutgers + elsewhere)
        #   Winter: max 4 credits (one course) or two 1–1.5 credit courses up to 3 credits
        if season == "Summer":
            term_max = min(request.max_credits_per_term, request.summer_max_credits)
        elif season == "Winter":
            term_max = min(request.max_credits_per_term, request.winter_max_credits)
        else:
            term_max = request.max_credits_per_term

        terms_left = len(terms) - term_index
        unscheduled_codes = set(queue) | {
            code for code in co_pulled if code not in scheduled and code not in completed
        }
        unscheduled_credits = sum(
            float(catalog.get(code, {}).get("credits") or 0)
            for code in unscheduled_codes
        )
        # Use the requested maximum as a hard ceiling, but spread the remaining
        # workload across the timeline instead of front-loading every term.
        balanced_term_max = min(
            term_max,
            max(4, math.ceil(unscheduled_credits / terms_left)),
        )

        # Preserve already-registered transcript courses in their real term.
        # They consume term capacity and remain visibly distinct from generated
        # recommendations, while still satisfying prerequisites/requirements.
        registered_codes = sorted(
            code for code in in_progress
            if in_progress_terms.get(code) == term
        )
        term_courses: List[PlannedCourse] = [
            PlannedCourse(
                code=catalog.get(code, {}).get("code", code),
                title=catalog.get(code, {}).get("title", code),
                credits=in_progress_credit_hours.get(
                    code, float(catalog.get(code, {}).get("credits") or 0)
                ),
                prerequisites=catalog.get(code, {}).get("prerequisites", []),
                core_tags=_core_tag_index.get(code, []),
                is_in_progress=True,
            )
            for code in registered_codes
        ]
        term_credits = sum(course.credits for course in term_courses)
        next_queue: List[str] = []
        prior_scheduled: Set[str] = set(scheduled)
        this_term: Set[str] = set()

        # Never let a flexible degree elective consume capacity needed by a
        # named program/core requirement offered in the same semester.
        term_queue = sorted(queue, key=lambda code: code in degree_elective_set)
        for code in term_queue:
            if code in scheduled or code in this_term:
                continue

            course = catalog.get(code)
            if not course:
                warnings.append(f"Course {code} not found in catalog — skipped.")
                continue

            eligibility = evaluate_rule(
                rule_for_course(course),
                StudentRecord(
                    completed=frozenset(covered | prior_scheduled),
                    grades=course_grades,
                    in_progress=frozenset(this_term),
                    programs=frozenset(p["name"] for p in program.get("individual_programs", [])),
                    earned_credits=completed_credits_count + sum(
                        catalog.get(c, {}).get("credits", 0) for c in in_progress | prior_scheduled
                    ),
                    class_year=request.class_year,
                ),
            )
            prereqs_met = eligibility.allowed
            offered = _is_offered(course, season, season_has_data)

            pending_co_credits = sum(
                catalog[co]["credits"]
                for co in course.get("corequisites", [])
                if co not in scheduled and co not in this_term and co not in completed and co in catalog
            )
            course_credit_limit = balanced_term_max if code in degree_elective_set else term_max
            fits = (
                term_credits + course["credits"] + pending_co_credits
                <= course_credit_limit
            )

            if prereqs_met and offered and fits:
                is_general_elective = code in degree_elective_set
                is_elec = code in elective_set and not is_general_elective
                term_courses.append(
                    PlannedCourse(
                        code=course["code"],
                        title=course["title"],
                        credits=course["credits"],
                        is_elective=is_elec,
                        is_general_elective=is_general_elective,
                        prerequisites=course.get("prerequisites", []),
                        core_tags=_core_tag_index.get(course["code"], []),
                        elective_options=[
                            ElectiveOption(
                                code=catalog[c]["code"],
                                title=catalog[c]["title"],
                                credits=catalog[c]["credits"],
                                prerequisites=catalog[c].get("prerequisites", []),
                            )
                            for c in full_elective_pool
                            if c in catalog and c != code
                        ] if is_elec else [],
                    )
                )
                term_credits += course["credits"]
                this_term.add(code)

                for co_code in course.get("corequisites", []):
                    if co_code in scheduled or co_code in this_term or co_code in completed:
                        continue
                    co = catalog.get(co_code)
                    if not co:
                        continue
                    co_eligibility = evaluate_rule(
                        rule_for_course(co),
                        StudentRecord(
                            completed=frozenset(covered | prior_scheduled | this_term),
                            grades=course_grades,
                            programs=frozenset(p["name"] for p in program.get("individual_programs", [])),
                            class_year=request.class_year,
                        ),
                    )
                    if co_eligibility.allowed:
                        term_courses.append(
                            PlannedCourse(
                                code=co["code"],
                                title=co["title"],
                                credits=co["credits"],
                                prerequisites=co.get("prerequisites", []),
                                core_tags=_core_tag_index.get(co["code"], []),
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
            f"Not all requirements fit before {grad_term}. "
            "Consider extending your graduation date or increasing max credits per term."
        )

    unscheduled_co = [c for c in co_pulled if c not in scheduled and c not in completed]
    queue.extend(unscheduled_co)

    non_empty_terms = [t for t in planned_terms if t.courses]
    last_course_term = non_empty_terms[-1].term if non_empty_terms else None

    completion_term = None
    if not queue and last_course_term and last_course_term != grad_term:
        completion_term = last_course_term

    # Build per-program requirement summaries
    individual_programs = program.get("individual_programs", [])
    # Collect all planned course codes across the full requested timeline.
    planned_codes: Set[str] = {c.code for term in planned_terms for c in term.courses}

    programs_summary: List[ProgramSummary] = []
    for prog in individual_programs:
        prog_reqs, _ = _normalize_graduate_requirements(prog["reqs"])
        prog_name = prog["name"]
        prog_type = prog["type"]

        # Required courses
        required_items: List[CourseStatus] = []
        for code in prog_reqs.get("required_courses", []):
            if code in completed:
                status = "completed"
            elif code in in_progress:
                status = "in_progress"
            elif code in planned_codes:
                status = "planned"
            else:
                status = "not_scheduled"
            required_items.append(CourseStatus(code=code, status=status))

        # Electives
        elec = prog_reqs.get("electives", {})
        elec_options: Set[str] = set(elec.get("options", []))
        elec_needed: int = elec.get("count", 0)
        elec_completed = [c for c in completed if c in elec_options]
        elec_planned = [c for c in planned_codes if c in elec_options and c not in completed]

        # Science requirement
        sci_completed: List[str] = []
        for opt in prog_reqs.get("science_requirement", {}).get("options", []):
            if isinstance(opt, list):
                for c in opt:
                    if c in completed:
                        sci_completed.append(c)
            elif opt in completed:
                sci_completed.append(opt)

        # Stats requirement
        stats_completed = [
            c for c in prog_reqs.get("statistics_requirement", {}).get("options", [])
            if c in completed
        ]

        programs_summary.append(ProgramSummary(
            name=prog_name,
            type=prog_type,
            required=required_items,
            electives_needed=elec_needed,
            electives_completed=elec_completed,
            electives_planned=elec_planned,
            elective_options=sorted(elec_options),
            elective_min_300_plus=elec.get("min_level_300_plus", 0),
            elective_min_400_plus=elec.get("min_level_400_plus", 0),
            science_completed=sci_completed,
            science_options=[
                option if isinstance(option, list) else [option]
                for option in prog_reqs.get("science_requirement", {}).get("options", [])
            ],
            stats_completed=stats_completed,
            stats_options=prog_reqs.get("statistics_requirement", {}).get("options", []),
            requirement_groups=prog_reqs.get("requirement_groups", []),
        ))

    return PlanResponse(
        # Preserve empty semesters so the editor always reaches the student's
        # requested graduation term and can accept courses added later.
        terms=planned_terms,
        remaining_courses=queue,
        warnings=warnings,
        completion_term=completion_term,
        completed_credits=completed_credits_count,
        total_credits=total_credits_count,
        core_curriculum_name=core_curriculum_name,
        core_curriculum_blocks=core_curriculum_blocks,
        completed_course_map=completed_course_map,
        programs_summary=programs_summary,
    )
