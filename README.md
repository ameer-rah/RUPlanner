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
=======
# RU Planner

RU Planner is a web-based academic planning tool that generates a personalized
semester-by-semester schedule based on degree level, majors/minors, completed
courses, and target graduation term.

This repo is rebuilt from the spec in `RU Planner.md` and follows a
three-tier architecture:

- **Frontend**: Next.js (TypeScript)
- **Backend API**: FastAPI (Python)
- **Data layer**: PostgreSQL

## Project Structure

```
RUPlanner/
├── frontend/          # Next.js UI
├── backend/           # FastAPI API + planning logic
├── data/              # Sample data (JSON/CSV)
└── docker-compose.yml # Local dev stack
```

## Quick Start (Local)

### Backend

```
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend

```
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## API

- `POST /plan` generates a plan from user inputs.
