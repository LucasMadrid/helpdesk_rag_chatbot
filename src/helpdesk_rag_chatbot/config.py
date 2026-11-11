from functools import lru_cache
from typing import Literal

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed application settings for the helpdesk RAG chatbot.

    Values are read from environment variables, falling back to a `.env` file
    in the working directory. Missing required values raise a validation error
    at instantiation; unknown variables are ignored.

    Groups:
            LiteLLM: gateway URL, API key and model name used for LLM calls.
            Langfuse: public/secret keys and base URL used for tracing, plus
            LANGFUSE_ENABLED (optional, default false) to switch tracing on.
            APP_ENV: environment name sent to Langfuse (optional, default
            "development").
            App DB: connection URL for the application database.
            LLM_TIMEOUT: request timeout in seconds (optional, default 15.0).
            HISTORY_MAX_TOKENS: token budget for earlier turns sent to the model,
            counted approximately (optional, default 2000, must be > 0).
            LOG_LEVEL: logging level (optional, default INFO).

    Secrets are `SecretStr`, so they are masked in `repr` and logs; call
    `.get_secret_value()` to read them.
    """

    litellm_url: HttpUrl = Field(validation_alias="LITELLM_URL")
    litellm_key: SecretStr = Field(validation_alias="LITELLM_KEY")
    litellm_model: str = Field(validation_alias="LITELLM_MODEL")

    langfuse_public_key: SecretStr = Field(validation_alias="LANGFUSE_PUBLIC_KEY")
    langfuse_secret_key: SecretStr = Field(validation_alias="LANGFUSE_SECRET_KEY")
    langfuse_base_url: HttpUrl = Field(validation_alias="LANGFUSE_BASE_URL")
    langfuse_enabled: bool = Field(default=False, validation_alias="LANGFUSE_ENABLED")

    # Sent to Langfuse as the trace environment, so dev traces stay out of
    # production dashboards. Lowercase letters, digits, hyphens and underscores only.
    app_env: str = Field(
        default="development",
        validation_alias="APP_ENV",
        pattern=r"^[a-z0-9_-]{1,40}$",
    )

    app_db_url: SecretStr = Field(validation_alias="APP_DB_URL")
    llm_timeout: float = Field(default=15.0, validation_alias="LLM_TIMEOUT")
    history_max_tokens: int = Field(
        default=2000, gt=0, validation_alias="HISTORY_MAX_TOKENS"
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", validation_alias="LOG_LEVEL"
    )

    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", env_file_encoding="utf-8"
    )


@lru_cache
def get_settings() -> Settings:
    """
    Return the cached application settings instance.
    :return: The cached Settings instance.
    """
    return Settings()
