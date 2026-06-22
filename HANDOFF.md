# Session Handoff — June 17, 2026

## Current State

Both servers run cleanly. All TypeScript errors are resolved (`npx tsc --noEmit` passes). All 14 security vulnerabilities are fixed. See `SECURITY_VULNERABILITIES.md` for the full fix log.

**Production URLs**
- Frontend: https://ruplanner.app (Vercel, auto-deploys on git push)
- Backend: https://backend-1073787278310.us-east1.run.app (Cloud Run, min 1 instance)

---

## What Was Done This Session (June 17, 2026)

### Security — All 14 vulnerabilities fixed

| # | Severity | Issue | Fix |
|---|----------|-------|-----|
| 1 | LOW | localStorage token storage | Removed; all fetches use `credentials: 'include'` with httponly cookies |
| 2 | LOW | Weak password (6 chars) | `_validate_password_strength`: 12-char min + uppercase/lowercase/digit/special |
| 3 | LOW | Admin token empty default | Server exits at startup if `ADMIN_TOKEN` unset |
| 4 | LOW | Unencrypted email / reset brute-force | `@_limiter.limit("3/minute")` on `/auth/forgot-password` + audit logging |
| 5 | LOW | Plaintext phone numbers | Fernet symmetric encryption at rest; decrypt only for Twilio |
| 6 | MEDIUM | Missing CSRF protection | All auth cookies already `samesite="strict"` |
| 7 | MEDIUM | Hardcoded RMP credentials | Removed `"Authorization": "Basic dGVzdDp0ZXN0"` from `_RMP_HEADERS` |
| 8 | MEDIUM | No rate limiting | Added per-IP limits: register (3/min), login (5/min), google (5/min), courses (20/min), rmp (10/min), soc (20/min), snipes (10/min) |
| 9 | MEDIUM | Insufficient SOC input validation | Added `pattern`/`min_length`/`max_length` to all 4 SOC query params |
| 10 | HIGH | Hardcoded SECRET_KEY fallback | Server exits at startup if `SECRET_KEY` unset |
| 11 | HIGH | 30-day JWT expiration | Reduced to 7 days (matching cookie `max_age`) |
| 12 | HIGH | SQL injection risk in search | Added `re.match(r"^[a-zA-Z0-9\s\-]+$", q)` + `max_length=100` on `/courses` |
| 13 | CRITICAL | Unvalidated PDF upload | Rate limited (5/min), 20MB → 5MB, MIME check, 20-page cap via `pypdf`, 10s async timeout |
| 14 | MEDIUM | PII + account existence in logs | Replaced `email=` + `found=` log with 12-char SHA-256 email hash; no enumeration signal |

### Bugs fixed during run test

**Backend forward-reference crash** (`backend/app/main.py`)
- `_create_token` and `_get_current_user_id` were defined at line ~408 but used as default argument values in route functions starting at line ~234. Python evaluates default args at module load time → `NameError` on startup.
- Fix: moved both functions to before the first route definition.

**Frontend TypeScript errors** (3 files)
- `schedules/page.tsx` — referenced `token` in 3 places but the variable was never declared (leftover from old localStorage migration). Removed all three references.
- `sniper/page.tsx` — `const [token, setToken]` was declared but `setToken` was never called and `token` never read. Removed the dead state.
- `CourseDetailModal.tsx` — removed `token: string` from Props; switched the `/soc/sections` fetch from `Authorization: Bearer` header to `credentials: 'include'` (consistent with cookie-based auth used everywhere else). Removed `token` from the `useEffect` dependency array.

---

## Environment Variables Required

All must be set in `backend/.env` (and Cloud Run secrets) before running:

```
DATABASE_URL=<neon postgres url>
SECRET_KEY=<python -c "import secrets; print(secrets.token_hex(32))">
ADMIN_TOKEN=<python -c "import secrets; print(secrets.token_hex(32))">
PHONE_ENCRYPTION_KEY=<python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
TWILIO_ACCOUNT_SID=<twilio sid>
TWILIO_AUTH_TOKEN=<twilio token>
TWILIO_FROM_NUMBER=<e.164 number>
RESEND_API_KEY=<resend key>
FRONTEND_URL=https://ruplanner.app
ALLOWED_ORIGINS=https://ruplanner.app,http://localhost:3000
BCRYPT_ROUNDS=12
```

Note: `backend/.env` currently has `BCRYPT_ROUNDS=4` (fast local dev). Set to `12` in production.

---

## Running Locally

```bash
# Backend (from /backend)
.venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend (from /frontend)
npm run dev
```

---

## Remaining Recommendations (not security vulnerabilities)

These are improvements, not blockers:

1. **Refresh tokens** — JWT is 7 days with no revocation. Implement short-lived access token (1hr) + long-lived refresh token (7 days) in a second httponly cookie to allow forced logout without password change.

2. **Account lockout** — After 5 failed login attempts, lock account for 30 minutes. Prevents credential stuffing even with rate limits in place.

3. **Security headers middleware** — Add `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Strict-Transport-Security` via a FastAPI middleware (code example in `SECURITY_VULNERABILITIES.md`).

4. **Dependency scanning in CI** — Add `safety check` and `bandit -r backend/` to the deploy pipeline.

5. **Delete stale Cloud Run services** — Two old services not serving traffic:
   ```sh
   gcloud run services delete ru-planner-backend --region us-east1
   gcloud run services delete ruplanner-backend --region us-east1
   ```

6. **`.bak` files** — `frontend/src/app/schedules/page.tsx.bak` and `frontend/src/app/sniper/page.tsx.bak` are untracked and should be deleted or gitignored.
