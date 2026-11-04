from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from helpdesk_rag_chatbot.config import Settings


def get_chat_model(settings: Settings) -> BaseChatModel:
    """
    Build a chat model that talks to the LiteLLM gateway.

    The gateway exposes an OpenAI-compatible API, so ``ChatOpenAI`` is pointed
    at ``settings.litellm_url`` and authenticated with ``settings.litellm_key``.
    Requests use ``settings.llm_timeout`` seconds as timeout and are retried up
    to 2 times on transient errors.

    :param settings: Application settings providing the gateway URL, API key,
        model name and request timeout.
    :return: A ``BaseChatModel`` instance configured for the gateway.
    """
    return ChatOpenAI(
        base_url=str(settings.litellm_url),
        api_key=settings.litellm_key,  # SecretStr is accepted directly
        model=settings.litellm_model,
        timeout=settings.llm_timeout,
        max_retries=2,
    )
