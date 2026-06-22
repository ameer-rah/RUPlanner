import json
import re
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import networkx as nx

from ..schemas import PlanRequest, PlanResponse, PlannedCourse, TermPlan, ElectiveOption, CoreCurriculumBlock, CourseStatus, ProgramSummary

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
    """If the program has a 'tracks' dict and a track was specified, merge that track's
    requirements on top of the base requirements (track keys take precedence)."""
    if not track:
        return requirements
    tracks = requirements.get("tracks", {})
    if not tracks or track not in tracks:
        return requirements
    base = {k: v for k, v in requirements.items() if k != "tracks"}
    track_reqs = dict(tracks[track])
    return {**base, **track_reqs}


def _load_catalog_from_db() -> Dict[str, Dict]:
    return _get_db_catalog()


_SAS_CORE_INDEX: Dict[str, List[str]] = {}  # {course_code: [designation, ...]}
_SAS_CORE_INDEX_LOADED = False

_DB_CATALOG_CACHE: Dict[str, Dict] = {}
_DB_CATALOG_LOADED = False

_DN_PROGRAMS_CACHE: Dict = {}
_DN_PROGRAMS_LOADED = False


def _get_db_catalog() -> Dict[str, Dict]:
    global _DB_CATALOG_CACHE, _DB_CATALOG_LOADED
    if _DB_CATALOG_LOADED:
        return _DB_CATALOG_CACHE
    try:
        from ..database import SessionLocal
        from ..models import Course
        db = SessionLocal()
        try:
            rows = db.query(Course).all()
            _DB_CATALOG_CACHE = {
                r.code: {
                    "code": r.code,
                    "title": r.title,
                    "credits": r.credits,
                    "prerequisites": [],
                    "spring_offered": r.spring_offered,
                    "summer_offered": r.summer_offered,
                    "fall_offered": r.fall_offered,
                }
                for r in rows
            }
        finally:
            db.close()
    except Exception:
        _DB_CATALOG_CACHE = {}
    _DB_CATALOG_LOADED = True
    return _DB_CATALOG_CACHE


def _get_dn_programs() -> Dict:
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
    return {m.group(1) for m in _BLOCK_TAG_RE.finditer(title)}


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

        # Expand: any completed course whose SAS Core designations overlap this block counts
        if block_tags and core_index:
            for code in completed_courses:
                desigs = set(core_index.get(code, []))
                if desigs & block_tags and code not in courses:
                    courses = list(courses) + [code]

        completed_in_block = [c for c in courses if c in completed_courses]
        needed = max(0, (total or 0) - len(completed_in_block)) if total is not None else 0
        blocks.append(
            CoreCurriculumBlock(
                title=block_title,
                total_courses=total,
                courses=courses,
                is_elective=rb.get("is_elective", False),
                completed=completed_in_block,
                needed=needed,
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
    season, year = term.split()
    return int(year) * 4 + _SEASONS.index(season)


def current_term() -> str:
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
    start_idx = _term_index(start)
    end_idx = _term_index(end)
    terms: List[str] = []
    for i in range(start_idx, end_idx + 1):
        year = i // 4
        season = _SEASONS[i % 4]
        terms.append(f"{season} {year}")
    return terms


def load_catalog(path: Path) -> Dict[str, Dict]:
    with open(path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    json_catalog: Dict[str, Dict] = {course["code"]: course for course in data}

    db_catalog = _load_catalog_from_db()
    if not db_catalog:
        return json_catalog

    merged: Dict[str, Dict] = {}
    all_codes = json_catalog.keys() | db_catalog.keys()
    for code in all_codes:
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
        "electives": {
            "count": total_count,
            "options": all_options,
            "any_from_catalog": any_from_catalog,
            "min_level_300_plus": total_300,
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

    for key in (
        "sci_intro_requirement", "advanced_core_requirement",
        "foundation_requirement", "practice_electives", "concept_electives",
        "diversity_requirement",
    ):
        val = next((p[key] for p in programs if p.get(key)), None)
        if val:
            result[key] = val

    return result


def resolve_program(request: PlanRequest) -> Dict:
    level_raw = request.degree_level.strip().lower()
    found: List[Dict] = []
    individual_programs: List[Dict] = []  # [{reqs, name, type}]

    for major_raw in request.majors:
        school, db_level, major_name, track = _parse_major_entry(major_raw, level_raw)
        if not db_level:
            continue
        try:
            reqs = _load_requirements_from_db(school, db_level, major_name, CATALOG_YEAR)
            reqs = _apply_program_patches(school, db_level, major_name, reqs)
            reqs = _apply_track(reqs, track)
            found.append(reqs)
            individual_programs.append({"reqs": reqs, "name": major_name, "type": "major"})
        except ValueError:
            continue

    for minor_raw in request.minors:
        if not minor_raw.strip():
            continue
        school, db_level, major_name, track = _parse_major_entry(minor_raw, "minor")
        if not db_level:
            continue
        try:
            reqs = _load_requirements_from_db(school, db_level, major_name, CATALOG_YEAR)
            reqs = _apply_program_patches(school, db_level, major_name, reqs)
            reqs = _apply_track(reqs, track)
            found.append(reqs)
            display_name = f"{major_name} — {track}" if track else major_name
            individual_programs.append({"reqs": reqs, "name": display_name, "type": "minor"})
        except ValueError:
            continue

    for conc_raw in (request.concentrations or []):
        if not conc_raw.strip():
            continue
        school, db_level, major_name, track = _parse_major_entry(conc_raw, "concentration")
        if not db_level:
            continue
        try:
            reqs = _load_requirements_from_db(school, db_level, major_name, CATALOG_YEAR)
            reqs = _apply_program_patches(school, db_level, major_name, reqs)
            reqs = _apply_track(reqs, track)
            found.append(reqs)
            individual_programs.append({"reqs": reqs, "name": major_name, "type": "concentration"})
        except ValueError:
            continue

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

    merged_catalog: Dict[str, Dict] = {}
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
    if not req:
        return None
    options: List[str] = req.get("options", [])
    if not options:
        return None
    if any(o in completed for o in options):
        return None
    return next((o for o in options if o in catalog), None)


def _resolve_science_courses(requirements: Dict, completed: Set[str]) -> List[str]:
    sci_req = requirements.get("science_requirement", {})
    if not sci_req:
        return []

    options: List[List[str]] = sci_req.get("options", [])
    if not options:
        return []

    for option in options:
        if all(c in completed for c in option):
            return []

    for option in options:
        if any(c in completed for c in option):
            return [c for c in option if c not in completed]

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
) -> Tuple[List[str], List[str]]:
    available = [c for c in elective_options if c not in required and c not in completed]
    high400 = [c for c in available if _get_course_level(c) >= 400]
    high300 = [c for c in available if _get_course_level(c) >= 300]

    chosen: List[str] = []
    warnings_out: List[str] = []

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
    flag = f"{season.lower()}_offered"
    return any(entry.get(flag, False) for entry in catalog.values())


def _is_offered(course: Dict, season: str, season_has_data: Dict[str, bool]) -> bool:
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
    program = resolve_program(request)
    catalog: Dict[str, Dict] = program["catalog"]
    requirements: Dict = program["requirements"]

    completed: Set[str] = {c.strip().upper() for c in request.completed_courses}
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
            def _level(c: str) -> int:
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
    stubbed = _build_catalog_stubs(all_referenced, catalog)
    if stubbed:
        warnings.append(
            f"Full catalog details unavailable for {len(stubbed)} graduate course(s) "
            f"({', '.join(stubbed[:6])}{'…' if len(stubbed) > 6 else ''}). "
            "Credits shown as 3 per course (standard graduate unit). Verify with the registrar."
        )

    for code in _resolve_science_courses(requirements, completed):
        if code not in required:
            required.append(code)

    stat_code = _resolve_stats_course(requirements, completed)
    if stat_code and stat_code not in required:
        required.append(stat_code)

    electives = requirements.get("electives", {})
    elective_count: int = electives.get("count", 0)
    elective_options: List[str] = list(electives.get("options", []))
    min_level_300_plus: int = electives.get("min_level_300_plus", 0)

    if electives.get("any_from_catalog") and not elective_options:
        elective_options = [c for c in catalog if c not in required]

    elective_options = [c for c in elective_options if c in catalog]

    completed_elec = [c for c in elective_options if c in completed]
    completed_elec_high = [c for c in completed_elec if _get_course_level(c) >= 300]
    elective_count = max(0, elective_count - len(completed_elec))
    min_level_300_plus = max(0, min_level_300_plus - len(completed_elec_high))

    elective_400_plus: int = electives.get("min_level_400_plus", 0)
    completed_elec_400 = [c for c in completed_elec if _get_course_level(c) >= 400]
    elective_400_plus = max(0, elective_400_plus - len(completed_elec_400))

    chosen_electives, elective_warnings = _select_electives(
        elective_options, elective_count, min_level_300_plus, required, completed,
        min_level_400_plus=elective_400_plus,
    )
    warnings.extend(elective_warnings)
    required += chosen_electives

    elective_set: Set[str] = set(chosen_electives)
    full_elective_pool: List[str] = [
        c for c in elective_options if c not in completed
    ]

    for req_key in ("sci_intro_requirement", "advanced_core_requirement", "foundation_requirement"):
        opt = _resolve_choice_requirement(requirements.get(req_key, {}), completed, catalog)
        if opt and opt not in required:
            required.append(opt)

    for pool_key in ("practice_electives", "concept_electives"):
        pool_req = requirements.get(pool_key, {})
        if not pool_req:
            continue
        pool_opts = [c for c in pool_req.get("options", []) if c in catalog]
        pool_count = pool_req.get("count", 0)
        pool_300 = pool_req.get("min_level_300_plus", 0)
        pool_400 = pool_req.get("min_level_400_plus", 0)

        completed_pool = [c for c in pool_opts if c in completed]
        pool_count = max(0, pool_count - len(completed_pool))
        pool_300 = max(0, pool_300 - len([c for c in completed_pool if _get_course_level(c) >= 300]))
        pool_400 = max(0, pool_400 - len([c for c in completed_pool if _get_course_level(c) >= 400]))

        chosen_pool, pool_warnings = _select_electives(
            pool_opts, pool_count, pool_300, required, completed, pool_400
        )
        warnings.extend(pool_warnings)
        for c in chosen_pool:
            if c not in required:
                required.append(c)
                elective_set.add(c)
        for c in pool_opts:
            if c not in completed and c not in full_elective_pool:
                full_elective_pool.append(c)

    # For each unfulfilled SAS Core block with tag-based requirements, pick real courses to schedule
    if _core_tag_index:
        for blk in core_curriculum_blocks:
            if blk.needed <= 0 or blk.total_courses is None:
                continue
            tags = set(re.findall(r'\[([A-Za-z]+)\]', blk.title))
            if not tags:
                continue
            # Count courses already in the plan (required but not completed) that satisfy this block
            already_covering = sum(
                1 for c in required
                if c not in completed and tags.intersection(set(_core_tag_index.get(c, [])))
            )
            actual_needed = max(0, blk.needed - already_covering)
            if actual_needed <= 0:
                continue
            req_set = set(required)
            # Pick lowest-level catalog courses matching any of the block's tags
            candidates = sorted(
                [c for c, ctags in _core_tag_index.items()
                 if tags.intersection(set(ctags)) and c in catalog
                 and c not in completed and c not in req_set],
                key=lambda c: int(re.search(r'\d+', c).group()) if re.search(r'\d+', c) else 999
            )
            picked = candidates[:actual_needed]
            for c in picked:
                required.append(c)
                elective_set.add(c)
            # Expose all candidates as swap options
            for c in candidates:
                if c not in full_elective_pool:
                    full_elective_pool.append(c)

    _collect_missing_prereqs(required, catalog, completed, required)

    remaining = [c for c in required if c not in completed]

    # Compute progress: how many required credits the student has already completed
    completed_in_req = [c for c in required if c in completed]
    completed_credits_count = sum(catalog.get(c, {}).get("credits", 3) for c in completed_in_req)
    total_credits_count = sum(catalog.get(c, {}).get("credits", 3) for c in required)

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
        queue = [c for c in topo_order if c in remaining_set and c not in co_pulled]
    except nx.NetworkXUnfeasible:
        warnings.append("Prerequisite cycle detected; scheduling without ordering guarantees.")
        queue = [c for c in remaining if c not in co_pulled]

    season_has_data = {s: _season_has_data(catalog, s) for s in _SEASONS}
    scheduled: Set[str] = set()
    planned_terms: List[TermPlan] = []

    for term in terms:
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

        term_courses: List[PlannedCourse] = []
        term_credits = 0
        next_queue: List[str] = []
        prior_scheduled: Set[str] = set(scheduled)
        this_term: Set[str] = set()

        for code in queue:
            if code in scheduled or code in this_term:
                continue

            course = catalog.get(code)
            if not course:
                warnings.append(f"Course {code} not found in catalog — skipped.")
                continue

            prereqs: Set[str] = set(course.get("prerequisites", []))
            prereqs_met = prereqs.issubset(completed | prior_scheduled)
            offered = _is_offered(course, season, season_has_data)

            pending_co_credits = sum(
                catalog[co]["credits"]
                for co in course.get("corequisites", [])
                if co not in scheduled and co not in this_term and co not in completed and co in catalog
            )
            fits = (
                term_credits + course["credits"] + pending_co_credits
                <= term_max
            )

            if prereqs_met and offered and fits:
                is_elec = code in elective_set
                term_courses.append(
                    PlannedCourse(
                        code=course["code"],
                        title=course["title"],
                        credits=course["credits"],
                        is_elective=is_elec,
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
                    co_prereqs: Set[str] = set(co.get("prerequisites", []))
                    if co_prereqs.issubset(completed | prior_scheduled | this_term):
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
    in_progress: Set[str] = {c.strip().upper() for c in (request.completed_courses or []) if c.strip().upper() not in completed}
    # Collect all planned course codes across all scheduled terms
    planned_codes: Set[str] = {c.code for term in non_empty_terms for c in term.courses}

    programs_summary: List[ProgramSummary] = []
    for prog in individual_programs:
        prog_reqs = prog["reqs"]
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
            science_completed=sci_completed,
            stats_completed=stats_completed,
        ))

    return PlanResponse(
        terms=non_empty_terms,
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
