"""Tests for helpdesk_rag_chatbot.adapters.llm."""

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from helpdesk_rag_chatbot.adapters.llm import get_chat_model
from helpdesk_rag_chatbot.config import Settings


def make_settings() -> Settings:
    """Build validated Settings from explicit values, ignoring any real .env."""
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        LITELLM_URL="http://gateway.test:4000",
        LITELLM_KEY="sk-test",
        LITELLM_MODEL="gpt-test",
        LANGFUSE_PUBLIC_KEY="pk-lf-test",
        LANGFUSE_SECRET_KEY="sk-lf-test",
        LANGFUSE_BASE_URL="http://localhost:3000",
        APP_DB_URL="postgresql://user:pw@localhost:5432/app",
        LLM_TIMEOUT=7.0,
    )


def test_returns_base_chat_model() -> None:
    assert isinstance(get_chat_model(make_settings()), BaseChatModel)


def test_settings_are_wired_into_client() -> None:
    model = get_chat_model(make_settings())
    assert isinstance(model, ChatOpenAI)
    assert model.openai_api_base == "http://gateway.test:4000/"
    assert model.openai_api_key.get_secret_value() == "sk-test"
    assert model.model_name == "gpt-test"
    assert model.request_timeout == 7.0
    assert model.max_retries == 2
