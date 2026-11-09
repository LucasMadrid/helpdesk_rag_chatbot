"""Shared pytest fixtures."""

import logging
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import asynccontextmanager

import pytest

from helpdesk_rag_chatbot import main
from helpdesk_rag_chatbot.config import Settings
from helpdesk_rag_chatbot.utils.logging_setup import _QUIET_LOGGERS

# Required settings only. LANGFUSE_ENABLED is deliberately absent, so a test can
# check its default.
REQUIRED_SETTINGS: dict[str, object] = {
    "LITELLM_URL": "http://gateway.test:4000",
    "LITELLM_KEY": "sk-test",
    "LITELLM_MODEL": "gpt-test",
    "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
    "LANGFUSE_SECRET_KEY": "sk-lf-test",
    "LANGFUSE_BASE_URL": "http://localhost:3000",
    "APP_DB_URL": "postgresql://user:pw@localhost:5432/app",
}

SettingsFactory = Callable[..., Settings]


@pytest.fixture
def required_settings() -> dict[str, object]:
    """A fresh copy of the required settings, as environment-style keys."""
    return dict(REQUIRED_SETTINGS)


@pytest.fixture
def make_settings() -> SettingsFactory:
    """Build validated Settings from explicit values, ignoring any real .env.

    Deterministic: Langfuse tracing is off unless a test overrides it.
    """

    def _make(**overrides: object) -> Settings:
        base = {**REQUIRED_SETTINGS, "LANGFUSE_ENABLED": False}
        # Merge as dicts: an override replaces a base value instead of raising
        # "multiple values for keyword argument".
        return Settings(_env_file=None, **(base | overrides))  # type: ignore[call-arg]

    return _make


@pytest.fixture(autouse=True)
def restore_logging() -> Iterator[None]:
    """Undo configure_logging after each test.

    The app's lifespan and configure_logging change global state (root handlers
    and levels, quiet third-party loggers), which would otherwise leak into
    later tests.
    """
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    quiet = {name: logging.getLogger(name).level for name in _QUIET_LOGGERS}
    yield
    root.handlers[:] = handlers
    root.setLevel(level)
    for name, old in quiet.items():
        logging.getLogger(name).setLevel(old)


class FakePool:
    """Stands in for AsyncConnectionPool, so no database is needed.

    ``events`` records the calls in order, so a test can assert on the sequence.
    """

    def __init__(self) -> None:
        self.events: list[str] = []

    async def open(self, wait: bool = False, timeout: float = 30.0) -> None:
        self.events.append("open")

    async def close(self, timeout: float = 5.0) -> None:
        self.events.append("close")

    @asynccontextmanager
    async def connection(self) -> AsyncIterator[object]:
        self.events.append("connection")
        yield object()


@pytest.fixture
def fake_pool(monkeypatch: pytest.MonkeyPatch) -> FakePool:
    """Replace the app's database pool and table setup with in-memory fakes.

    Request this in any test that runs the lifespan (``with TestClient(app)``),
    otherwise startup tries to reach a real Postgres.
    """
    pool = FakePool()
    monkeypatch.setattr(main, "build_db_pool", lambda settings: pool)

    async def fake_create_table(conn: object) -> None:
        pool.events.append("create_table")

    monkeypatch.setattr(main, "create_chat_history_table", fake_create_table)
    return pool
