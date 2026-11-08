"""Tests for helpdesk_rag_chatbot.adapters.llm."""

from collections.abc import Callable

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from helpdesk_rag_chatbot.adapters.llm import get_chat_model
from helpdesk_rag_chatbot.config import Settings

SettingsFactory = Callable[..., Settings]


def test_returns_base_chat_model(make_settings: SettingsFactory) -> None:
    assert isinstance(get_chat_model(make_settings()), BaseChatModel)


def test_settings_are_wired_into_client(make_settings: SettingsFactory) -> None:
    model = get_chat_model(make_settings(LLM_TIMEOUT=7.0))
    assert isinstance(model, ChatOpenAI)
    assert model.openai_api_base == "http://gateway.test:4000/"
    assert model.openai_api_key.get_secret_value() == "sk-test"
    assert model.model_name == "gpt-test"
    assert model.request_timeout == 7.0
    assert model.max_retries == 2
