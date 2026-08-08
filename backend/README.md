# RU Planner backend

The API and recurring background jobs are separate processes.

```sh
# Web/API process (safe to scale horizontally)
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Background worker (run exactly one replica)
python -m app.worker
```

The worker polls active course snipes every two minutes and refreshes course
data every 24 hours. It also refreshes courses once when it starts. These can
be configured with `SNIPE_POLL_INTERVAL_MINUTES`,
`COURSE_INGEST_INTERVAL_HOURS`, and `WORKER_RUN_INGEST_ON_STARTUP`.

Deploy the worker as a separate singleton service/process. APScheduler's job
options prevent overlapping executions inside that process, but they do not
provide distributed locking between multiple worker replicas.

The existing `POST /admin/ingest-courses` endpoint remains available for a
manual authenticated refresh.

## Database migrations

Apply migrations in numeric order before deploying the matching application
revision. `Base.metadata.create_all()` creates missing tables but does not alter
existing columns or keys.

```sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f management/migrations/001_expand_snipe_phone_number.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f management/migrations/002_canonical_course_identity.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f management/migrations/003_user_onboarding_profile.sql
```

Migration 002 changes the course primary key from the friendly alias (`CS111`)
to the canonical Rutgers code (`01:198:111`). It deliberately fails if a legacy
row cannot be assigned a full Rutgers code; resolve such rows before retrying.
Migration 003 marks existing users with saved schedules as onboarded. New users
are marked onboarded after their first successful plan generation; subsequent
logins restore their last plan instead of showing the setup wizard.

## Correctness boundaries

- Requirement JSON keeps independent elective/science/statistics groups for
  multi-program plans. Courses do not double-count across elective groups by
  default.
- Course eligibility supports typed `allOf`, `anyOf`, minimum-grade,
  concurrent-course, earned-credit, class-year, and program restrictions.
- Transcript parsing is deterministic-first. AI is used only as a fallback,
  and its codes/status flags are treated as untrusted input.
- Title-only transfer-course guesses are never automatically applied. Students
  review detected courses before adding them to a plan.

The transcript fixtures under `tests/fixtures/transcripts` are fully synthetic.
Add anonymized real-format fixtures only with explicit student consent and with
names, IDs, contact details, addresses, and document metadata removed.
