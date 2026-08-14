"""Singleton background worker for recurring RU Planner jobs.

Run exactly one instance separately from the API::

    python -m app.worker

Keeping these jobs out of the FastAPI lifespan prevents every API replica from
starting its own course ingestion and course-sniper polling loop.
"""

import logging
import os
from pathlib import Path

from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from . import models  # noqa: F401 - registers SQLAlchemy models with Base
from .core.sniper import poll_snipes
from .database import Base, engine
from management.ingest_courses import current_term_specs, ingest

logger = logging.getLogger(__name__)


def _positive_int_env(name: str, default: int) -> int:
    """Read a positive integer setting so invalid job intervals fail early.

    Args:
        name: Environment variable name.
        default: Value used when the variable is absent.

    Returns:
        The validated positive integer.

    Raises:
        ValueError: If the configured value is not a positive integer.
    """
    raw = os.getenv(name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")
    return value


def _bool_env(name: str, default: bool) -> bool:
    """Read a conventional boolean environment setting.

    Args:
        name: Environment variable name.
        default: Value used when the variable is absent.

    Returns:
        The parsed boolean value.

    Raises:
        ValueError: If the configured text is not a supported boolean spelling.
    """
    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean, got {raw!r}")


def run_course_ingest() -> None:
    """Refresh current academic terms so planning uses recent offerings."""
    for year, term in current_term_specs():
        logger.info("Fetching course data for %s %s", term, year)
        ingest(year=year, terms=[term])


def configure_scheduler(scheduler: BlockingScheduler) -> None:
    """Register non-overlapping recurring jobs on a worker-owned scheduler.

    Args:
        scheduler: Blocking scheduler dedicated to this worker process.
    """
    scheduler.add_job(
        poll_snipes,
        "interval",
        minutes=_positive_int_env("SNIPE_POLL_INTERVAL_MINUTES", 2),
        id="snipe_poll",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    scheduler.add_job(
        run_course_ingest,
        "interval",
        hours=_positive_int_env("COURSE_INGEST_INTERVAL_HOURS", 24),
        id="course_ingest",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )


def main() -> None:
    """Initialize storage and run the process-owned blocking job scheduler."""
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    Base.metadata.create_all(bind=engine)

    scheduler = BlockingScheduler(timezone="UTC")
    configure_scheduler(scheduler)

    if _bool_env("WORKER_RUN_INGEST_ON_STARTUP", True):
        run_course_ingest()

    logger.info("RU Planner worker started")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("RU Planner worker stopped")


if __name__ == "__main__":
    main()
