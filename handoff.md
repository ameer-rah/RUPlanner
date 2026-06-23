# RU Planner — Handoff Document
_Last updated: 2026-06-23_

---

## What Was Done (Previous Sessions)

### 1. Transcript Parser
- Switched from Anthropic document API (base64) to pypdf text extraction → plain text sent to Claude Haiku
- `ANTHROPIC_API_KEY` added to `backend/env.yaml`
- **Files:** `backend/app/main.py`, `backend/env.yaml`

### 2. Full-Page Step Wizard
- Rebuilt planner into a full-page split wizard: Degree → Program → Start → Schedule → Transcript → Review → Generate
- Fixed preview panel clipping, auto-submit bug on Transcript step, and added a Review step before generation
- **Files:** `frontend/src/app/planner/page.tsx`, `frontend/src/app/globals.css`

### 3. Master Programs Audit & Cleanup
- Deleted 10 master's programs with <20% course catalog coverage. 52 remain, all schedulable.
- Normalized CS MS, Economics MA, ECE MS field names
- **Files:** `backend/data/sas_programs.json`, `soe_programs.json`, `rbs_programs.json`, `ssw_programs.json`

### 4. Em Dash Program Name Bug
- Programs with `–` or `—` in names returned `[object Object]` error
- Fixed regex in `backend/app/schemas.py` and error display in `frontend/src/app/planner/page.tsx`
- **Deployed:** commit `95f8d29`

### 5. Course Sniper & Schedules Redesign
- Redesigned both pages to match the dark wizard aesthetic of My Planner
- Split layouts: left panel (pure black `var(--bg)`) + right content panel (`var(--surface-2)`)
- Added staggered entrance animations, hover interactions, pulsing red dot on active snipes
- **Files:** `frontend/src/app/sniper/page.tsx`, `frontend/src/app/schedules/page.tsx`

### 6. RMP Badges Per Section Row
- Moved RateMyProfessors badge from a single top-of-modal block to every section row inline
- Added module-level promise cache in `RmpBadge.tsx` to deduplicate concurrent requests for the same professor
- Raised `/rmp/rating` rate limit from 10/min → 60/min
- **Files:** `frontend/src/app/CourseDetailModal.tsx`, `frontend/src/app/RmpBadge.tsx`, `backend/app/main.py`

### 7. Course Sniper SOC Fix
- Fixed `NameError: _RUTGERS_DEPT_TO_PREFIX` — added `_SUBJECT_TO_PREFIX` dict at module level in `main.py`
- Made level=U and level=G SOC fetches run in parallel via `ThreadPoolExecutor`
- **Files:** `backend/app/main.py`

---

## What Was Done This Session (2026-06-23)

### 8. Auth Flash Bug Fixed
- **Problem:** New users (especially on Safari and Firefox with strict privacy settings) logged in successfully, reached `/planner`, then within <1 second were redirected back to the login page.
- **Root cause:** The backend sets an `httpOnly` cookie on its own Cloud Run domain (`ruplanner-backend-*.run.app`). Browsers like Safari with ITP (Intelligent Tracking Prevention) silently block cross-site cookies from being stored. So the planner's `/auth/me` call had no cookie to send, got a 401 immediately, and redirected back to login.
- **Fix:** After every successful login (email/password and Google), the JWT `access_token` (already in the login response body) is saved to `localStorage`. All protected API calls now include `Authorization: Bearer <token>` alongside `credentials: 'include'`. The backend already reads the Authorization header before cookies, so it just works regardless of cookie blocking.
- **Also fixed:** The `Content-Security-Policy` `connect-src` header in `next.config.mjs` had `https://backend-1073787278310.us-east1.run.app` — this is the actual URL `NEXT_PUBLIC_API_BASE_URL` points to in Vercel. A previous attempt to "correct" it to `ruplanner-backend-...` broke all API calls. Both URLs are now included in `connect-src`.
- **Files:** `frontend/src/app/page.tsx`, `frontend/src/app/planner/page.tsx`, `frontend/src/app/schedules/page.tsx`, `frontend/src/app/sniper/page.tsx`, `frontend/next.config.mjs`
- **Commits:** `8096c15`, `27c298f`

**Important note on the two Cloud Run URLs:** Both `https://backend-1073787278310.us-east1.run.app` and `https://ruplanner-backend-1073787278310.us-east1.run.app` return 200 and are live. Vercel's `NEXT_PUBLIC_API_BASE_URL` env var points to the former (without `ruplanner-` prefix). Do not remove it from `connect-src`.

---

## Pending Issues to Fix

### Bug 1: Transcript Parser — Inaccurate for Many Transcript Formats

**Symptom:** Users are reporting that the transcript parser misses courses, misidentifies grades, or fails to match course codes correctly. The developer's own transcript works well, but other students' transcripts — especially those who have spent their entire time at Rutgers (no transfer credits), who are in graduate programs, or who have unusual academic histories — are not parsed accurately.

**Why this happens:**

The parser was developed and tested primarily against one transcript format. Rutgers transcripts vary significantly depending on:

1. **Pure Rutgers students (no transfers):** Their transcripts have no "Transfer Courses" block, which the prompt specifically calls out. Claude may handle the simpler format fine, but edge cases like withdrawn courses (W), Pass/No Credit grades, and audited courses may be misclassified.

2. **Transfer students:** Transcripts include a "Transfer Courses" block with course titles from other institutions. Claude has to infer Rutgers equivalents from titles alone, which is error-prone — especially for general education courses with generic names like "ENGLISH COMPOSITION" or "CALCULUS I" that could map to many Rutgers codes.

3. **Graduate students:** Graduate transcripts at Rutgers look different from undergrad transcripts — different grade scales (High Pass / Pass / Low Pass / Fail), thesis credits, research credits, and seminar formats that may not have clean course codes.

4. **Non-standard grade entries:** Grades like `PA`, `NC`, `TE`, `TC`, `WF`, `WD`, `WN`, `NR`, `AB`, `NG` all appear on Rutgers transcripts. The prompt covers many but may miss combinations.

5. **Repeated courses:** Students who failed and retook a course appear twice with the same course code. The parser may count both as completed or skip one.

6. **Co-op / internship credits:** These appear on transcripts as credits with no real course code.

**Where to look:**
- `backend/app/main.py` — `_TRANSCRIPT_PROMPT` (around line 316) and the `parse_transcript` endpoint
- `frontend/src/app/TranscriptUpload.tsx` — the results display

**How to improve it:**

1. **Collect real transcript samples.** Get 5–10 anonymized transcripts from students with different backgrounds (pure Rutgers, transfer, graduate, co-op). Identify exactly where parsing fails for each one. Do not guess — test.

2. **Expand the prompt's grade handling.** Audit the full list of Rutgers grade codes and add any missing ones to the `passed`/`failed`/`is_in_progress` rules in `_TRANSCRIPT_PROMPT`.

3. **Add few-shot examples to the prompt.** The current prompt has one example course. Adding 3–5 examples covering transfer credits, in-progress courses, and failed/repeated courses will significantly improve Claude's output consistency.

4. **Handle repeated courses explicitly.** Add a rule to the prompt: if the same course code appears more than once, only mark it as `passed` if the most recent attempt has a passing grade.

5. **Post-processing validation.** After Claude returns the JSON, add a Python validation pass that checks for obvious issues: duplicate course codes, credits that are 0 or >6, grades that don't match the passed/failed flags.

6. **Show the user what was detected before applying it.** The current flow auto-applies matched courses immediately when the transcript is uploaded. Consider adding a confirmation step where the user can see the detected courses and remove any that look wrong before they're fed into the plan generator.

---

### Bug 2: Course Sniper — Index Lookup May Miss Graduate Sections

**Symptom:** Entering a 5-digit section index for a graduate course returns "Section not found."

**Root cause:** The `/soc/section-by-index` endpoint fetches `courses.json?level=U` and `level=G` in parallel, but the campus is hardcoded to `NB`. Camden and Newark campus sections will never be found.

**Fix:** Add campus fallback (try `NB`, then `NK`, then `CM`) or remove the campus filter entirely from the index lookup since we're matching by index number which is globally unique.

**Files:** `backend/app/main.py` — `/soc/section-by-index` endpoint

---

## Deployment Reference

| Layer | Host | How to deploy |
|-------|------|---------------|
| Frontend | Vercel | Auto-deploys on `git push origin main` |
| Backend | Google Cloud Run (`us-east1`) | `gcloud builds submit --tag gcr.io/ru-planner-489603/ruplanner-backend` then `gcloud run deploy ruplanner-backend --image gcr.io/ru-planner-489603/ruplanner-backend --region us-east1 --env-vars-file env.yaml` |

Backend service URLs (both live):
- `https://backend-1073787278310.us-east1.run.app` ← **this is what Vercel points to**
- `https://ruplanner-backend-1073787278310.us-east1.run.app`

Env vars for backend live in `backend/env.yaml` (not committed — contains secrets).
Required vars: `DATABASE_URL`, `SECRET_KEY`, `ANTHROPIC_API_KEY`, `ALLOWED_ORIGINS`, `FRONTEND_URL`, `GOOGLE_CLIENT_ID`.
