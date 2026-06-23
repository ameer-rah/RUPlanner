# RU Planner — Handoff Document
_Generated: 2026-06-22_

---

## What Was Done This Session

### 1. Transcript Parser Fixed
- **Problem:** Uploading a PDF returned "AI returned an unreadable response. Please try again."
- **Root cause:** `ANTHROPIC_API_KEY` was missing from Cloud Run env vars, and the code was trying to use the Anthropic document API (base64) which isn't supported by Haiku.
- **Fix:** Switched to pypdf text extraction → plain text sent to Claude Haiku (`claude-haiku-4-5-20251001`). `ANTHROPIC_API_KEY` added to `backend/env.yaml`. `ADMIN_TOKEN` hard-exit removed so Cloud Run starts without it.
- **Files:** `backend/app/main.py`, `backend/env.yaml`

### 2. Full-Page Step Wizard
- **Problem:** Planner was a static sidebar form.
- **Fix:** Rebuilt into a full-page split wizard (left: 480px step form, right: decorative preview panel with floating cards) modeled after getcracked.io. 6 steps: Degree → Program → Start → Schedule → Transcript → Generate.
- **Fixes along the way:**
  - Preview panel was clipped by topbar → added `margin-top: var(--topbar-height)` to `.wizard-fullpage`
  - Step 5 (Transcript) was auto-submitting on Next click → browser re-fired submit when button type changed in-place; fixed by making all Generate buttons `type="button"` with explicit `onClick`
  - Added a Review step (step 5 = summary table, step 6 = Generate button) so users see what they're submitting before triggering generation
- **Files:** `frontend/src/app/planner/page.tsx`, `frontend/src/app/globals.css`

### 3. Master Programs Audit & Cleanup
- **Problem:** Many master's programs produced "0 courses scheduled" because their course codes weren't in any catalog JSON.
- **Fix:** Audited all master programs against catalog JSONs. Deleted 10 programs with <20% coverage. Normalized CS MS, Economics MA, ECE MS field names (`category_a_courses`/`core_courses`/`tracks` → `required_courses`/`electives`). 52 master programs remain, all schedulable.
- **Files:** `backend/data/sas_programs.json`, `soe_programs.json`, `rbs_programs.json`, `ssw_programs.json`

### 4. Em Dash Program Name Bug Fixed (most recent)
- **Problem:** Programs with em dashes in their names (e.g. "Medicinal Chemistry (MS — Non-Thesis Option)") returned `Error: [object Object]`.
- **Root cause (backend):** `_PROGRAM_NAME_RE` regex didn't allow `–` or `—`, causing a Pydantic 422 where `detail` is an array of objects, not a string.
- **Root cause (frontend):** Error display did `setStatus(\`Error: ${err.detail}\`)` without checking if `detail` was an array.
- **Fix:**
  - `backend/app/schemas.py` line 6: added `–—` to regex character class
  - `frontend/src/app/planner/page.tsx` ~line 927: stringify array detail properly
- **Deployed:** commit `95f8d29`, Cloud Run revision `ruplanner-backend-00008-rb4`

---

## Pending Issues to Fix

### Bug 1: Course Sniper — Index Lookup Fails

**Symptom:** Entering a 5-digit section index and clicking "Look up" either returns "Section not found" or times out even for valid sections.

**Where to look:**
- `backend/app/main.py` lines 764–795 — `/soc/section-by-index` endpoint
- The endpoint fetches `courses.json?level=U` (undergrad only). If the indexed section belongs to a **graduate-level** course, it will never be found.
- Also: the endpoint has no campus-level fallback — if the section is at Camden or Newark campus, `campus=NB` won't find it.
- `frontend/src/app/sniper/page.tsx` lines 264–276 — frontend lookup call

**Likely fixes:**
1. Add `level=G` fallback: if not found in `level=U`, retry with `level=G` (or fetch both in parallel).
2. Consider fetching `courses.json` without the `level` param — the SOC API returns all levels if omitted.
3. If performance is the concern (full course list is ~4 MB), cache the response in-memory for 10–15 minutes with a simple `functools.lru_cache` or a module-level dict with a timestamp.

**Files to change:** `backend/app/main.py` (the `/soc/section-by-index` endpoint)

---

### Bug 2: Auto-Logout When Closing the App

**Symptom:** Closing the browser tab/window keeps the user's JWT alive in `localStorage` indefinitely. There's no session expiry.

**Current state:**
- Tokens stored in `localStorage` keys `ru_planner_token` and `ru_planner_email`
- Manual logout calls `POST /auth/logout` and clears localStorage (`frontend/src/app/planner/page.tsx` line 884)
- No automatic cleanup on tab close

**Approaches (pick one):**

**Option A — `sessionStorage` instead of `localStorage` (simplest)**
Swap `localStorage` → `sessionStorage` everywhere tokens are set/read. `sessionStorage` is cleared automatically when the tab is closed. Tokens persist across page refreshes but not across tab closes.
- Search: `localStorage.setItem.*ru_planner` and `localStorage.getItem.*ru_planner` in all frontend files
- Also update `layout.tsx` and any auth callbacks

**Option B — Short-lived JWT + refresh token (most secure)**
Issue a 15-minute JWT and a 7-day httpOnly cookie refresh token. Requires backend changes to `/auth/token` and a new `/auth/refresh` endpoint. More work but standard practice.

**Option C — `beforeunload` + `navigator.sendBeacon` (unreliable)**
Call `navigator.sendBeacon('/auth/logout')` on `beforeunload`. Browsers don't guarantee this fires on tab kill, so it's not reliable for security purposes — only cosmetic.

**Recommended:** Option A for now (low risk, fast). Option B if compliance/security matters later.

**Files to change:**
- `frontend/src/app/layout.tsx` — where tokens are read on mount
- `frontend/src/app/planner/page.tsx` — where tokens are set after login
- `frontend/src/app/auth/page.tsx` — login/signup flow (where `localStorage.setItem` is called)

---

### Bug 3: Rate My Professor Not Showing for Every Professor

**Symptom:** The RMP badge appears for the first instructor of the first section, but not for instructors in other sections of the same course.

**Where to look:**
- `frontend/src/app/CourseDetailModal.tsx` lines 113–139 — fetches RMP only for `sections[0]?.instructors[0]`; the result is stored in a single `rmp` state variable and rendered once above the sections list
- `frontend/src/app/CourseDetailModal.tsx` lines 302–340 — the sections rows render instructor names as plain text with no badge
- `frontend/src/app/RmpBadge.tsx` — standalone `<RmpBadge instructorName="..." />` component that self-fetches; already works correctly

**Fix:**
1. In the sections table rows (`CourseDetailModal.tsx` ~line 303), replace the plain instructor `<div>` with a flex row that includes `<RmpBadge instructorName={instructor} />` next to the name.
2. Remove the top-of-modal single RMP block (lines 220–259) since it'll be redundant once each row has its own badge.
3. `RmpBadge` already deduplicates by instructor name via its own `useEffect` — but if the same professor teaches multiple sections, it'll fire the same `/rmp/rating` request multiple times. Optionally lift the cache to a `Map<string, RmpData>` in the modal's state and pass data down as a prop instead of fetching in each badge.

**Files to change:** `frontend/src/app/CourseDetailModal.tsx` (and optionally refactor `RmpBadge.tsx` to accept pre-fetched data)

---

## Deployment Reference

| Layer | Host | How to deploy |
|-------|------|---------------|
| Frontend | Vercel | Auto-deploys on `git push origin main` |
| Backend | Google Cloud Run (`us-east1`) | `gcloud builds submit --tag gcr.io/ru-planner-489603/ruplanner-backend` then `gcloud run deploy ruplanner-backend --image ... --region us-east1 --env-vars-file env.yaml` |

Backend service URL: `https://ruplanner-backend-1073787278310.us-east1.run.app`

Env vars for backend live in `backend/env.yaml` (not committed — contains secrets). Required vars: `DATABASE_URL`, `SECRET_KEY`, `ANTHROPIC_API_KEY`, `ALLOWED_ORIGINS`.
