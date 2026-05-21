# Session Handoff — May 9 2026

## What we fixed
Production sign-in was showing "cannot connect to server." Root cause: the backend runs on **Google Cloud Run** (`ru-planner-489603`, `us-east1`, service name `backend`) which was scaling to zero instances when idle, causing 15-30s cold starts that timed out on the frontend.

**Fix applied (already done):**
```sh
gcloud run services update backend --region us-east1 --min-instances 1
```
One warm instance now stays alive permanently. Cold starts are gone.

## Code changes committed to main
1. `backend/app/main.py` — added `GET /health` (no auth, returns `{"status":"ok"}`)
2. `frontend/vercel.json` — Vercel cron pings `/api/keepalive` every 5 min
3. `frontend/src/app/api/keepalive/route.ts` — keepalive route that hits backend `/health`
4. `frontend/src/app/page.tsx` — `fetchWithRetry` wraps all auth fetch calls (8s timeout, 2 retries)
5. `docker-compose.yml` — `restart: always` + faster Postgres healthcheck (local dev only, not used in prod)

## Still to do
Delete the two stale Cloud Run services (old deployments, not serving traffic):
```sh
gcloud run services delete ru-planner-backend --region us-east1
gcloud run services delete ruplanner-backend --region us-east1
```

## Production URLs
- Frontend: https://ruplanner.app (Vercel, auto-deploys on git push)
- Backend: https://backend-1073787278310.us-east1.run.app (Cloud Run)
