"""Tests for helpdesk_rag_chatbot.config."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import HttpUrl, SecretStr, ValidationError

from helpdesk_rag_chatbot.config import Settings, get_settings

REQUIRED_ENV = {
    "LITELLM_URL": "http://localhost:4000",
    "LITELLM_KEY": "sk-litellm",
    "LITELLM_MODEL": "gpt-test",
    "LANGFUSE_PUBLIC_KEY": "pk-lf-test",
    "LANGFUSE_SECRET_KEY": "sk-lf-test",
    "LANGFUSE_BASE_URL": "http://localhost:3000",
    "APP_DB_URL": "postgresql://user:pw@localhost:5432/app",
}
OPTIONAL_ENV = ["LLM_TIMEOUT", "HISTORY_MAX_TOKENS"]


@pytest.fixture(autouse=True)
def isolated_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Run each test with no ambient settings and no real .env file.

    Clears every setting from the process environment, moves the cwd to an empty
    temp dir (so the relative ``env_file=".env"`` finds nothing) and resets the
    ``get_settings`` cache before and after.
    """
    for name in [*REQUIRED_ENV, *OPTIONAL_ENV]:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def full_env(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Set every required variable in the environment."""
    for name, value in REQUIRED_ENV.items():
        monkeypatch.setenv(name, value)
    return REQUIRED_ENV


def test_loads_values_from_environment(full_env: dict[str, str]) -> None:
    settings = Settings()

    assert settings.litellm_url == HttpUrl(full_env["LITELLM_URL"])
    assert settings.litellm_model == "gpt-test"
    assert settings.langfuse_base_url == HttpUrl(full_env["LANGFUSE_BASE_URL"])
    assert settings.litellm_key.get_secret_value() == "sk-litellm"
    assert settings.langfuse_public_key.get_secret_value() == "pk-lf-test"
    assert settings.langfuse_secret_key.get_secret_value() == "sk-lf-test"
    assert settings.app_db_url.get_secret_value() == full_env["APP_DB_URL"]


def test_llm_timeout_defaults_to_15(full_env: dict[str, str]) -> None:
    assert Settings().llm_timeout == 15.0


def test_llm_timeout_can_be_overridden(
    full_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("LLM_TIMEOUT", "12.5")

    assert Settings().llm_timeout == 12.5


def test_history_max_tokens_defaults_to_2000(full_env: dict[str, str]) -> None:
    assert Settings().history_max_tokens == 2000


def test_history_max_tokens_of_zero_is_rejected(
    full_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HISTORY_MAX_TOKENS", "0")

    with pytest.raises(ValidationError):
        Settings()


# Test that each required environment variable is validated and named when missing.
@pytest.mark.parametrize("missing", sorted(REQUIRED_ENV))
def test_missing_required_variable_fails_and_names_it(
    missing: str, full_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(missing)

    with pytest.raises(ValidationError) as exc_info:
        Settings()

    assert missing in str(exc_info.value)


@pytest.mark.parametrize("name", ["LITELLM_URL", "LANGFUSE_BASE_URL"])
def test_invalid_url_is_rejected(
    name: str, full_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(name, "not a url")

    with pytest.raises(ValidationError):
        Settings()


def test_secrets_are_masked_in_repr_and_str(full_env: dict[str, str]) -> None:
    settings = Settings()
    rendered = repr(settings) + str(settings)

    assert isinstance(settings.litellm_key, SecretStr)
    for name in ("LITELLM_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_PUBLIC_KEY"):
        assert full_env[name] not in rendered
    assert "pw@" not in rendered  # db password


def test_get_settings_returns_cached_instance(full_env: dict[str, str]) -> None:
    assert get_settings() is get_settings()


def test_get_settings_cache_clear_rereads_environment(
    full_env: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    first = get_settings()
    monkeypatch.setenv("LITELLM_MODEL", "changed")

    assert get_settings().litellm_model == first.litellm_model  # still cached

    get_settings.cache_clear()

    assert get_settings().litellm_model == "changed"
