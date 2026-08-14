"""Hermetic defaults installed before tests import the application."""

from __future__ import annotations

import os
import contextlib
import io
from pathlib import Path
import sys
import tempfile
import types

import pytest


os.environ.setdefault("SECRET_KEY", "test-only-secret-key")
os.environ.setdefault("BCRYPT_ROUNDS", "4")
os.environ["RATE_LIMIT_ENABLED"] = "false"

# Use a disposable database; the session fixture seeds program requirements.
_test_db_dir = tempfile.TemporaryDirectory(prefix="ruplanner-pytest-")
_test_db = Path(_test_db_dir.name) / "ruplanner.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db}"


def _install_slowapi_stub() -> None:
    """Supply the decorator API when optional rate-limit middleware is absent."""
    try:
        import slowapi  # noqa: F401
        return
    except ModuleNotFoundError:
        pass

    package = types.ModuleType("slowapi")
    util = types.ModuleType("slowapi.util")
    errors = types.ModuleType("slowapi.errors")

    class RateLimitExceeded(Exception):
        pass

    class Limiter:
        def __init__(self, key_func=None):
            self.key_func = key_func

        def limit(self, _rule):
            return lambda endpoint: endpoint

    def get_remote_address(request):
        return request.client.host if request.client else "testclient"

    async def handler(_request, _exc):  # pragma: no cover
        return None

    package.Limiter = Limiter
    package._rate_limit_exceeded_handler = handler
    util.get_remote_address = get_remote_address
    errors.RateLimitExceeded = RateLimitExceeded
    sys.modules["slowapi"] = package
    sys.modules["slowapi.util"] = util
    sys.modules["slowapi.errors"] = errors


_install_slowapi_stub()


def _install_anthropic_stub() -> None:
    try:
        import anthropic  # noqa: F401
        return
    except ModuleNotFoundError:
        module = types.ModuleType("anthropic")

        class APIError(Exception):
            pass

        class AsyncAnthropic:
            def __init__(self, **_kwargs):
                pass

        module.APIError = APIError
        module.AsyncAnthropic = AsyncAnthropic
        sys.modules["anthropic"] = module


_install_anthropic_stub()


@pytest.fixture(autouse=True, scope="session")
def _authenticated_api_requests():
    """Keep legacy planner endpoint tests focused on planning, not login."""
    from app.database import Base, engine
    from app.main import app, _get_current_user_id
    from management.seed_programs import seed

    Base.metadata.create_all(bind=engine)
    with contextlib.redirect_stdout(io.StringIO()):
        seed()
    app.dependency_overrides[_get_current_user_id] = lambda: 1
    yield
    app.dependency_overrides.pop(_get_current_user_id, None)
