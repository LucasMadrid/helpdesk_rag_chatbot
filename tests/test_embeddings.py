"""Tests for helpdesk_rag_chatbot.adapters.embeddings."""

from collections.abc import Callable

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from helpdesk_rag_chatbot.adapters.embeddings import get_embeddings
from helpdesk_rag_chatbot.config import Settings

SettingsFactory = Callable[..., Settings]


def test_returns_embeddings(make_settings: SettingsFactory) -> None:
    assert isinstance(get_embeddings(make_settings()), Embeddings)


def test_settings_are_wired_into_client(make_settings: SettingsFactory) -> None:
    embeddings = get_embeddings(
        make_settings(
            LLM_TIMEOUT=7.0,
            EMBEDDING_MODEL="embed-test",
            EMBEDDING_DIMENSIONS=256,
        )
    )
    assert isinstance(embeddings, OpenAIEmbeddings)
    assert embeddings.openai_api_base == "http://gateway.test:4000/"
    assert embeddings.openai_api_key.get_secret_value() == "sk-test"
    assert embeddings.model == "embed-test"
    assert embeddings.dimensions == 256
    assert embeddings.request_timeout == 7.0
    assert embeddings.max_retries == 2


def test_client_side_token_check_is_off(make_settings: SettingsFactory) -> None:
    # tiktoken only knows OpenAI model names; the gateway may serve others.
    embeddings = get_embeddings(make_settings())
    assert isinstance(embeddings, OpenAIEmbeddings)
    assert embeddings.check_embedding_ctx_length is False
