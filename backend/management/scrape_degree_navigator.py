#!/usr/bin/env python3
from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
from pathlib import Path

from playwright.async_api import async_playwright, Page, TimeoutError as PWTimeout

DATA_DIR      = Path(__file__).resolve().parents[1] / "data"
OUT_PROGRAMS  = DATA_DIR / "dn_programs.json"
OUT_CATALOG   = DATA_DIR / "dn_catalog.json"
CHECKPOINT    = DATA_DIR / "dn_checkpoint.json"

DN_BASE   = "https://dn.rutgers.edu"
DN_HOME   = f"{DN_BASE}/Home.aspx?pageid=default"
DN_SEARCH = f"{DN_BASE}/DN/Audit/ViewDegrees.aspx?pageid=DNViewDegrees"
DN_AUDIT  = f"{DN_BASE}/DN/Audit/DegreeAudit.aspx?pageid=audit&degreeID="

_SUBJ_PREFIX: dict[str, str] = {
    "198": "CS",    "640": "MATH",  "960": "STAT",  "750": "PHYS",
    "160": "CHEM",  "165": "BIOC",  "115": "BIO",   "118": "BIO",
    "694": "MCB",   "190": "ECON",  "920": "SOC",   "830": "PSYC",
    "790": "POLS",  "730": "PHIL",  "447": "LING",  "070": "ANTH",
    "082": "ANTH",  "450": "GEOG",  "460": "GEOSC", "506": "HIST",
    "510": "HIST",  "512": "HIST",  "358": "ENGL",  "355": "ENGL",
    "352": "ENGL",  "359": "ENGL",  "351": "CW",    "354": "FILM",
    "185": "COGS",  "175": "COMMUN","563": "ARTH",  "016": "AFRS",
    "986": "WGSS",  "195": "CRIM",  "377": "ENVST", "090": "AMST",
    "098": "ASIAN", "940": "SPAN",  "420": "FREN",  "700": "MUSIC",
    "887": "DANC",  "219": "EXER",  "501": "PUBH",  "560": "PUBP",
    "762": "RELIG", "490": "ITAL",  "776": "POLS",  "840": "THEA",
    "440": "ECE",   "332": "CHE",   "125": "CEE",   "670": "MAE",
    "573": "ISE",   "137": "BME",
    "010": "ACCT",  "136": "BAIT",  "620": "MGT",   "630": "MKT",
    "390": "FIN",   "623": "HRM",
    "163": "PHAR",  "164": "PHRC",  "166": "PHBT",  "167": "PHSL",
    "168": "PCHM",  "169": "PTHR",
}

_KNOWN_PREFIXES = {
    "CS","MATH","STAT","PHYS","CHEM","ECON","SOC","PSYC","POLS","PHIL",
    "GEOG","GEOSC","LING","ARTH","WGSS","CRIM","HIST","ENGL","BIO","BIOC",
    "MCB","ANTH","COMMUN","COGS","ENVST","AMST","ASIAN","AFRS","SPAN",
    "FREN","THEA","MUSIC","DANC","EXER","PUBH","PUBP","RELIG","FILM","ITAL",
    "ECE","CHE","CEE","MAE","ISE","BME","ACCT","BAIT","MGT","MKT","FIN",
    "HRM","PHAR","PHRC","PHBT","PHSL","PCHM","PTHR","CW",
}

_RU_FULL    = re.compile(r'\b\d{2}:(\d{3}):(\d{3}[A-Z]?)\b')
_RU_SHORT   = re.compile(r'\b(\d{3}):(\d{3}[A-Z]?)\b')
_SHORT_FORM = re.compile(r'\b([A-Z]{2,8})\s*(\d{3}[A-Z]?)\b')


def _norm(raw: str) -> str | None:
    raw = raw.strip().replace("\u00a0", " ")
    m = _RU_FULL.match(raw)
    if m:
        pfx = _SUBJ_PREFIX.get(m.group(1))
        return f"{pfx}{m.group(2)}" if pfx else None
    m = _RU_SHORT.match(raw)
    if m:
        pfx = _SUBJ_PREFIX.get(m.group(1))
        return f"{pfx}{m.group(2)}" if pfx else None
    m = re.match(r'^([A-Z]{2,8})\s*(\d{3}[A-Z]?)$', raw)
    if m and m.group(1) in _KNOWN_PREFIXES:
        return f"{m.group(1)}{m.group(2)}"
    return None


def _extract_codes(text: str) -> list[str]:
    found: list[str] = []
    seen: set[str] = set()

    for m in _RU_FULL.finditer(text):
        pfx = _SUBJ_PREFIX.get(m.group(1))
        if pfx:
            c = f"{pfx}{m.group(2)}"
            if c not in seen:
                found.append(c); seen.add(c)

    for m in _RU_SHORT.finditer(text):
        pfx = _SUBJ_PREFIX.get(m.group(1))
        if pfx:
            c = f"{pfx}{m.group(2)}"
            if c not in seen:
                found.append(c); seen.add(c)

    for m in _SHORT_FORM.finditer(text):
        if m.group(1) in _KNOWN_PREFIXES:
            c = f"{m.group(1)}{m.group(2)}"
            if c not in seen:
                found.append(c); seen.add(c)

    return found


async def login(page: Page, netid: str | None, password: str | None) -> None:
    print(f"[login] → {DN_HOME}")
    await page.goto(DN_HOME, wait_until="domcontentloaded")
    await asyncio.sleep(2)

    if "cas.rutgers.edu" in page.url or "login" in page.url.lower():
        if netid and password:
            print("[login] Filling credentials automatically…")
            await page.fill("#username", netid)
            await page.fill("#password", password)
            await page.click('input[type="submit"], button[type="submit"]')
        else:
            print()
            print("=" * 60)
            print("  CAS login page is open in the browser.")
            print("  Please log in with your NetID — script will continue")
            print("  automatically once you are redirected back to DN.")
            print("=" * 60)
            print()

        try:
            await page.wait_for_url(f"{DN_BASE}/**", timeout=120_000)
        except PWTimeout:
            sys.exit("[ERROR] Login timed out after 2 minutes.")

    print(f"[login] Authenticated — now at {page.url}")


async def collect_program_list(page: Page) -> list[dict]:
    print(f"\n[list] Loading {DN_SEARCH}")
    await page.goto(DN_SEARCH, wait_until="domcontentloaded")
    await asyncio.sleep(1)

    rpp_sel = await page.query_selector(
        'select[name*="rpp"], select[id*="rpp"], '
        'select[name*="PageSize"], select[id*="PageSize"], '
        'select[name*="pageSize"], select[id*="pageSize"]'
    )
    if rpp_sel:
        opts = await rpp_sel.query_selector_all("option")
        best_val, best_int = "", 0
        for opt in opts:
            v = (await opt.get_attribute("value") or "").strip()
            try:
                n = int(v)
                if n > best_int:
                    best_int, best_val = n, v
            except ValueError:
                pass
        if best_val:
            await rpp_sel.select_option(value=best_val)
            print(f"[list] Results per page → {best_val}")

    search_btn = await page.query_selector(
        'input[type="submit"][value="Search"], '
        'input[type="submit"], '
        'button[type="submit"]'
    )
    if search_btn:
        await search_btn.click()
    else:
        await page.keyboard.press("Enter")
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(1)

    programs: list[dict] = []
    page_num = 1

    while True:
        rows = await _parse_results_page(page)
        programs.extend(rows)
        print(f"[list] Page {page_num}: {len(rows)} programs (total so far: {len(programs)})")

        next_link = await page.query_selector(
            'a[href*="Page$Next"], '
            'a[href*="__doPostBack"][title="Next page"], '
            'a.next-page'
        )
        if not next_link:
            links = await page.query_selector_all('a[href*="__doPostBack"]')
            for lnk in links:
                txt = (await lnk.inner_text()).strip()
                if txt in (">", "Next", "next"):
                    next_link = lnk
                    break

        if not next_link:
            break

        await next_link.click()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(1)
        page_num += 1

    print(f"[list] Found {len(programs)} programs total across {page_num} page(s)")
    return programs


async def _parse_results_page(page: Page) -> list[dict]:
    rows: list[dict] = []

    links = await page.query_selector_all('a[href*="DegreeAudit.aspx"]')
    for link in links:
        href = await link.get_attribute("href") or ""
        m = re.search(r'degreeID=(\d+)', href, re.I)
        if not m:
            continue
        degree_id = m.group(1)

        row_handle = await link.evaluate_handle("el => el.closest('tr')")
        row_el = row_handle.as_element()
        cells = await row_el.query_selector_all("td") if row_el else []
        code = (await cells[0].inner_text()).strip() if len(cells) > 0 else ""
        name = (await cells[1].inner_text()).strip() if len(cells) > 1 else ""

        rows.append({"degree_id": degree_id, "code": code, "name": name})

    return rows


async def scrape_audit(page: Page, prog: dict) -> dict:
    url = f"{DN_AUDIT}{prog['degree_id']}"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
        await asyncio.sleep(1)
    except PWTimeout:
        return _empty_result(prog, "navigation timed out")

    try:
        await page.wait_for_selector(
            '#ctl00_mainContent_ctl13_gridVisualReqs',
            timeout=15_000,
        )
    except PWTimeout:
        return _empty_result(prog, "requirements grid not found")

    req_rows = await page.query_selector_all(
        '#ctl00_mainContent_ctl13_gridVisualReqs tr.ReportGridItemA, '
        '#ctl00_mainContent_ctl13_gridVisualReqs tr.ReportGridItemB'
    )

    required_courses: list[str] = []
    elective_options: list[str] = []
    raw_blocks: list[dict] = []

    for row in req_rows:
        title_el = await row.query_selector('a[name][id]')
        title = (await title_el.inner_text()).strip() if title_el else ""

        label_spans = await row.query_selector_all('span.DeAcLabel')
        block_codes: list[str] = []
        for span in label_spans:
            txt = (await span.inner_text()).strip()
            if re.match(r'^\d{2}:\d{3}:\d{3}[A-Z]?$', txt) or \
               re.match(r'^\d{3}:\d{3}[A-Z]?$', txt):
                c = _norm(txt)
                if c and c not in block_codes:
                    block_codes.append(c)

        row_text = await row.inner_text()
        for c in _extract_codes(row_text):
            if c not in block_codes:
                block_codes.append(c)

        title_lc = title.lower()
        is_elective = any(kw in title_lc for kw in (
            "elective", "option", "choose", "select", "free", "open"
        ))

        if is_elective:
            for c in block_codes:
                if c not in elective_options:
                    elective_options.append(c)
        else:
            for c in block_codes:
                if c not in required_courses:
                    required_courses.append(c)

        total_m = re.search(r'Total Courses:\s*(\d+)', row_text)
        raw_blocks.append({
            "title":         title,
            "courses":       block_codes,
            "is_elective":   is_elective,
            "total_courses": int(total_m.group(1)) if total_m else None,
        })

    elective_count = 0
    for b in raw_blocks:
        if b["is_elective"] and b["total_courses"]:
            elective_count = b["total_courses"]
            break
    if not elective_count and elective_options:
        elective_count = 3

    degree_level = _map_degree(prog["name"])

    result: dict = {
        "school":           prog.get("code", ""),
        "degree_level":     degree_level,
        "major_name":       prog["name"],
        "catalog_year":     "2025-2026",
        "required_courses": required_courses,
        "electives": {
            "count":              elective_count,
            "min_level_300_plus": 0,
            "options":            elective_options,
            "any_from_catalog":   False,
        },
        "constraints": [],
        "notes":        [],
        "_raw_blocks":  raw_blocks,
    }

    if not required_courses and not elective_options:
        result["notes"].append(
            "WARNING: no course codes extracted — "
            "program may use category-based requirements (e.g. Core Curriculum)"
        )

    return result


def _empty_result(prog: dict, reason: str) -> dict:
    return {
        "school":           prog.get("code", ""),
        "degree_level":     _map_degree(prog["name"]),
        "major_name":       prog["name"],
        "catalog_year":     "2025-2026",
        "required_courses": [],
        "electives":        {"count": 0, "options": [], "any_from_catalog": False},
        "constraints":      [],
        "notes":            [f"ERROR: {reason}"],
        "_raw_blocks":      [],
    }


def _map_degree(name: str) -> str:
    n = name.upper()
    if "B.S." in n or " BS" in n or n.endswith("BS"):
        return "bachelor_bs"
    if "B.A." in n or " BA" in n or n.endswith("BA"):
        return "bachelor_ba"
    if "M.S." in n or " MS" in n or "MASTER OF SCIENCE" in n:
        return "master_ms"
    if "M.A." in n or " MA" in n or "MASTER OF ARTS" in n:
        return "master_ma"
    if "PHARM.D" in n or "PHARMD" in n:
        return "pharmd"
    if "PH.D" in n or "PHD" in n or "DOCTOR" in n:
        return "doctorate"
    if "MINOR" in n:
        return "minor"
    return "bachelor_bs"


def _load_cp() -> dict:
    if CHECKPOINT.exists():
        with open(CHECKPOINT) as f:
            return json.load(f)
    return {"scraped": {}}


def _save_cp(cp: dict) -> None:
    with open(CHECKPOINT, "w") as f:
        json.dump(cp, f, indent=2)


async def run(args: argparse.Namespace) -> None:
    netid    = args.netid    or os.environ.get("RUTGERS_NETID")
    password = args.password or os.environ.get("RUTGERS_PASSWORD")

    cp = _load_cp() if args.resume else {"scraped": {}}

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False, slow_mo=50)
        ctx     = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            locale="en-US",
        )
        page = await ctx.new_page()

        await login(page, netid, password)

        programs = await collect_program_list(page)
        if not programs:
            print("[ERROR] No programs found — check login or page structure.")
            await browser.close()
            return

        if args.limit:
            programs = programs[: args.limit]
            print(f"[info] --limit {args.limit}: scraping first {len(programs)} programs")

        total   = len(programs)
        scraped: dict[str, dict] = dict(cp["scraped"])
        catalog: dict[str, dict] = {}

        for i, prog in enumerate(programs, 1):
            slug = f"dn_{prog['degree_id']}"
            print(f"\n[{i}/{total}] {prog['name']}  (id={prog['degree_id']})", end="  ")

            if slug in scraped:
                print("SKIP (checkpoint)")
                continue

            result = await scrape_audit(page, prog)
            scraped[slug] = result

            n_req  = len(result["required_courses"])
            n_elec = len(result["electives"]["options"])
            print(f"→ {n_req} required, {n_elec} elective options")

            for code in result["required_courses"] + result["electives"]["options"]:
                if code not in catalog:
                    catalog[code] = {
                        "code":          code,
                        "title":         "",
                        "credits":       3,
                        "prerequisites": [],
                    }

            if i % 20 == 0:
                cp["scraped"] = scraped
                _save_cp(cp)
                print(f"  [checkpoint] {i}/{total}")

            await asyncio.sleep(args.pause)

        await browser.close()

    out = {"catalog_year": "2025-2026", "programs": scraped}
    with open(OUT_PROGRAMS, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\n[done] {OUT_PROGRAMS}  ({len(scraped)} programs)")

    existing: list[dict] = []
    if OUT_CATALOG.exists():
        with open(OUT_CATALOG) as f:
            existing = json.load(f)
    existing_codes = {c["code"] for c in existing}
    new_entries = [v for k, v in catalog.items() if k not in existing_codes]
    with open(OUT_CATALOG, "w") as f:
        json.dump(existing + new_entries, f, indent=2)
    print(f"[done] {OUT_CATALOG}  ({len(new_entries)} new entries added)")

    cp["scraped"] = scraped
    _save_cp(cp)
    print(f"[done] Checkpoint: {CHECKPOINT}")
    print(f"\nSummary: {len(scraped)} programs, {len(existing) + len(new_entries)} catalog entries")


def main() -> None:
    p = argparse.ArgumentParser(description="Scrape Rutgers Degree Navigator")
    p.add_argument("--netid",    default="",  help="NetID (or set RUTGERS_NETID)")
    p.add_argument("--password", default="",  help="Password (or set RUTGERS_PASSWORD)")
    p.add_argument("--limit",    type=int, default=0,
                   help="Stop after N programs (0 = all)")
    p.add_argument("--resume",   action="store_true",
                   help="Resume from dn_checkpoint.json")
    p.add_argument("--pause",    type=float, default=0.5,
                   help="Seconds between programs (default 0.5)")
    asyncio.run(run(p.parse_args()))


if __name__ == "__main__":
    main()
