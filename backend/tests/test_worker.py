from unittest.mock import Mock

import pytest

from app import worker


def test_configure_scheduler_registers_single_instance_jobs(monkeypatch):
    monkeypatch.setenv("SNIPE_POLL_INTERVAL_MINUTES", "5")
    monkeypatch.setenv("COURSE_INGEST_INTERVAL_HOURS", "12")
    scheduler = Mock()

    worker.configure_scheduler(scheduler)

    assert scheduler.add_job.call_count == 2
    sniper_call, ingest_call = scheduler.add_job.call_args_list
    assert sniper_call.args == (worker.poll_snipes, "interval")
    assert sniper_call.kwargs == {
        "minutes": 5,
        "id": "snipe_poll",
        "replace_existing": True,
        "coalesce": True,
        "max_instances": 1,
    }
    assert ingest_call.args == (worker.run_course_ingest, "interval")
    assert ingest_call.kwargs == {
        "hours": 12,
        "id": "course_ingest",
        "replace_existing": True,
        "coalesce": True,
        "max_instances": 1,
    }


def test_run_course_ingest_uses_current_terms(monkeypatch):
    ingest = Mock()
    monkeypatch.setattr(worker, "current_term_specs", lambda: [(2027, "spring"), (2027, "fall")])
    monkeypatch.setattr(worker, "ingest", ingest)

    worker.run_course_ingest()

    assert ingest.call_args_list == [
        (((), {"year": 2027, "terms": ["spring"]})),
        (((), {"year": 2027, "terms": ["fall"]})),
    ]


@pytest.mark.parametrize("value", ["0", "-1", "not-a-number"])
def test_interval_configuration_rejects_invalid_values(monkeypatch, value):
    monkeypatch.setenv("SNIPE_POLL_INTERVAL_MINUTES", value)

    with pytest.raises(ValueError, match="SNIPE_POLL_INTERVAL_MINUTES"):
        worker.configure_scheduler(Mock())


def test_boolean_configuration_is_strict(monkeypatch):
    monkeypatch.setenv("WORKER_RUN_INGEST_ON_STARTUP", "sometimes")

    with pytest.raises(ValueError, match="WORKER_RUN_INGEST_ON_STARTUP"):
        worker._bool_env("WORKER_RUN_INGEST_ON_STARTUP", True)
