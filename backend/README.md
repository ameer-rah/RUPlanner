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
manual authenticated refresh. Each run reports the result for its exact
New Brunswick term scopes. The worker and CLI use the same importer.

Preview published course counts and any unmapped subjects
without opening or writing to a database:

```sh
python -m management.ingest_courses --year 2027 --terms spring winter --dry-run --verify
```

For a backfill, point the CLI at the intended database and omit `--dry-run`.
A failed or empty response keeps the last stored offerings for that term.
Check scope outcomes and counts in the worker logs after deployment.

Production runs course ingestion as the `ruplanner-course-refresh` Cloud Run
job in `us-east1`. Cloud Scheduler starts it daily at 4 a.m. Eastern. The job
runs `python -m management.ingest_courses` directly. When releasing an importer
change, update both the API service and the job to the tested image digest.
The standalone worker remains available for environments that also run
snipe polling.

## Database migrations

On an existing database, apply only pending migrations in numeric order before
deploying the matching application revision. A fresh database can initialize
directly from the current models. `Base.metadata.create_all()` creates missing
tables but does not alter existing columns or keys.

```sh
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f management/migrations/001_expand_snipe_phone_number.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f management/migrations/002_canonical_course_identity.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f management/migrations/003_user_onboarding_profile.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f management/migrations/004_query_indexes.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f management/migrations/005_nb_course_offerings.sql
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

## New Brunswick program rule review

The course feed controls which Rutgers courses have scheduled offerings.
Degree rules are versioned separately by school, degree, program, and catalog
year. The legacy rule versions remain available for draft planning. A catalog
year selection alone does not establish which rules apply to a particular
student. Confirm the applicable program and year in Degree Navigator, and
reconcile approved exceptions with the student's audit.

### Computer Science pilot

Use the [New Brunswick undergraduate catalog](https://newbrunswick-26-27-undergrad.catalogs.rutgers.edu/),
the department's [B.A. requirements](https://www.cs.rutgers.edu/academics/undergraduate/cs-degrees/b-a-degree?catid=47),
[B.S. requirements](https://www.cs.rutgers.edu/academics/undergraduate/cs-degrees/b-s-degree?view=article),
and [elective rules](https://www.cs.rutgers.edu/academics/undergraduate/electives).
Verify each catalog version independently before publishing it.

- Confirm which rules govern each cohort. The current department pages list
  five electives for the B.A. and seven for the B.S., with different minimum
  New Brunswick CS counts. They also restrict the use of lower-level,
  outside-department, and individually approved courses. The B.S. page refers
  to the B.A. in its residency and elective time-limit clauses. Confirm the
  intended B.S. rules before encoding either clause.
- Review the [introductory sequence transition](https://www.cs.rutgers.edu/academics/undergraduate/new-introductory-computer-science-course-sequence)
  separately from the catalog-year rules. Rutgers phases out CS111 starting
  Spring 2027 and CS112 starting Fall 2027. Eligibility for CS121 and recognition
  of legacy credit depend on placement and student circumstances. CS120 can
  prepare a student for CS121 and carries SAS credit, but carries no CS major
  credit. Verify legacy, AP, transfer, and repeat cases before certifying either
  degree version.
- Compare remaining blocks and course allocations with advisor-reviewed
  [Degree Navigator](https://nbdn.rutgers.edu/students/using-degree-navigator)
  examples. Include a legacy sequence, a transition student, a transfer with
  confirmed credit, and a B.S. with science and external electives. Also include
  school core, credit minimums, grades, and permitted overlap. Use synthetic or
  appropriately redacted records in regression fixtures.
- Publish only rules the validator can enforce. Keep missing policy or
  student-specific evidence visible as review items. Expand the pilot after
  the reviewed examples agree with both the plan and the independent check.

For a deployment that can fetch the source pages, record reviewed fingerprints
and run the comparison from a scheduler:

```sh
python -m management.check_program_sources /path/to/pilot-sources.json --record
python -m management.check_program_sources /path/to/pilot-sources.json
```

The comparison exits 1 on changes and 2 when fetching or reading fails. Alert
on both statuses and review any changed source before recording a new
fingerprint. The command never edits course or program rules. Direct requests
from the development environment returned HTTP 403 during the pilot, so a live
baseline and scheduled run still require a host with access to these pages.

The [New Brunswick Engineering catalog](https://newbrunswick-26-27-undergrad.catalogs.rutgers.edu/schools/eng/course-listing/course-listing)
provides course descriptions on public subject pages. A read-only trial found
281 candidate codes across the 11 linked subjects, with 19 combined course
headings and three pages yielding no headings under the trial's extraction
rule. The source also uses shortened prerequisite references, nested choices,
and permission requirements. These pages could supply descriptions and
source evidence, but a parser would need to preserve those distinctions and
flag ambiguous prerequisite rules for review. No supported bulk catalog
feed was verified. Scheduled imports can ship independently of catalog and
degree-rule publication.
