# RUPlanner

RUPlanner is a Rutgers–New Brunswick degree planning engine. This repo starts
with the core "planner brain" (requirements evaluation + prerequisite-aware
semester planning) so it can power a web app later.

## What’s in here

- `src/types.ts`: core data models (courses, requirements, prereqs, terms)
- `src/requirements/engine.ts`: requirement satisfaction evaluator
- `src/planner/planner.ts`: heuristic semester-by-semester planner
- `src/data/sample.ts`: sample Rutgers CS-like data for a demo run
- `src/cli.ts`: minimal CLI that prints a generated plan

## Quick start

1. Install deps:

   `npm install`

2. Create `.env` (never commit this file):

   `DATABASE_URL="postgresql://user:pass@host:5432/ruplanner"`

   `NEXTAUTH_URL="http://localhost:3000"`

   `NEXTAUTH_SECRET="replace-me"`

   `UPSTASH_REDIS_REST_URL="https://your-upstash-url"`

   `UPSTASH_REDIS_REST_TOKEN="your-upstash-token"`

   `AUTH0_CLIENT_ID="your-auth0-client-id"`

   `AUTH0_CLIENT_SECRET="your-auth0-client-secret"`

   `AUTH0_ISSUER="https://your-tenant.us.auth0.com"`

   `MOCK_AUTH_ENABLED="true"`

   `GOOGLE_CLIENT_ID="your-google-client-id"`

   `GOOGLE_CLIENT_SECRET="your-google-client-secret"`

   `LOCAL_AUTH_ENABLED="true"`

2. Run the demo:

   `npm run demo`

3. Run the web app:

   `npm run dev`

## Security notes

- `.env` is ignored by Git; keep secrets out of the repo.
- Use a strong `NEXTAUTH_SECRET` and rotate it if exposed.
- Use least-privilege DB users in production (no superuser).
- Store production secrets in the hosting provider’s secret manager.
- Rate limiting uses Upstash Redis in production; set the Upstash env vars.
- Run `npx prisma migrate dev` after adding new schema models (like audit logs).

## Dev-only helpers

- `GET /api/audit` returns the latest 20 audit log entries in development.
- `POST /api/plan` requires authentication; use the NetID mock login until SSO is wired.
- `GET /api/profile` and `POST /api/profile` manage the current user's profile.
- `PUT /api/plan` saves plan edits from the plan editor.
- `POST /api/auth/register` creates a local account (email/username/password).

## Next steps

- Wire this into a Next.js app
- Persist data in Postgres (Prisma)
- Add Rutgers SSO and a student-facing UI
