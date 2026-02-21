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
