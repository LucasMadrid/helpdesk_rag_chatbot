"""Tests for helpdesk_rag_chatbot.adapters.tracing."""

import os
import subprocess
import sys
from unittest.mock import MagicMock

import pytest
from langfuse.langchain import CallbackHandler

from helpdesk_rag_chatbot.adapters import tracing
from helpdesk_rag_chatbot.adapters.tracing import get_langfuse_handler
from helpdesk_rag_chatbot.config import Settings

# Required settings only. LANGFUSE_ENABLED is deliberately absent, so the
# default can be tested.
REQUIRED = {
    "LITELLM_URL": "http://gateway.test:4000",
    "LITELLM_KEY": "sk-test",
    "LITELLM_MODEL": "gpt-test",
    "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
    "LANGFUSE_SECRET_KEY": "sk-lf-test",
    "LANGFUSE_BASE_URL": "http://localhost:3000",
    "APP_DB_URL": "postgresql://user:pw@localhost:5432/app",
}


def make_settings(**overrides: object) -> Settings:
    """Build validated Settings from explicit values, ignoring any real .env.

    Deterministic: Langfuse tracing is off unless a test overrides it.
    """
    base: dict[str, object] = {**REQUIRED, "LANGFUSE_ENABLED": False}
    # Merge as dicts: an override replaces a base value instead of raising
    # "multiple values for keyword argument".
    return Settings(_env_file=None, **(base | overrides))  # type: ignore[call-arg]


def test_import_needs_no_langfuse_environment() -> None:
    # A fresh interpreter, because this module already imported tracing at the
    # top, so an in-process import_module would only return the cached module.
    env = {k: v for k, v in os.environ.items() if not k.startswith("LANGFUSE_")}
    result = subprocess.run(
        [sys.executable, "-c", "import helpdesk_rag_chatbot.adapters.tracing"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_tracing_is_off_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    # No LANGFUSE_ENABLED anywhere: not in the env, not in .env, not in the kwargs.
    monkeypatch.delenv("LANGFUSE_ENABLED", raising=False)
    settings = Settings(_env_file=None, **REQUIRED)  # type: ignore[call-arg]

    assert settings.langfuse_enabled is False
    assert get_langfuse_handler(settings) is None


def test_handler_is_built_when_enabled() -> None:
    handler = get_langfuse_handler(make_settings(LANGFUSE_ENABLED=True))

    assert isinstance(handler, CallbackHandler)


def test_shutdown_flushes_langfuse_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = MagicMock()
    monkeypatch.setattr(tracing, "get_client", lambda **_: client)

    tracing.shutdown_tracing(make_settings(LANGFUSE_ENABLED=True))

    client.shutdown.assert_called_once_with()


def test_shutdown_does_nothing_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    monkeypatch.setattr(tracing, "get_client", lambda **_: client)

    tracing.shutdown_tracing(make_settings())

    client.shutdown.assert_not_called()
