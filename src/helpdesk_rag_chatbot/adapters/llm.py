from langchain_core.exceptions import (
    ModelConnectionError,
    ModelRateLimitError,
    ModelTimeoutError,
)
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from openai import BadRequestError

from helpdesk_rag_chatbot.config import Settings

# Errors that mean "the model could not be reached right now", not "the request
# was wrong". They are transient, so the caller can answer 503 and the client may
# retry. Bad credentials, invalid requests and similar errors are deliberately
# not listed: they are our bugs, and should surface as a 500.
LLM_UNAVAILABLE_ERRORS: tuple[type[Exception], ...] = (
    ModelConnectionError,  # the gateway could not be reached
    ModelTimeoutError,  # it did not answer within settings.llm_timeout
    ModelRateLimitError,  # it is up, but is rejecting calls for now
)

# The provider's content filter (Azure OpenAI behind LiteLLM) rejects some
# messages before the model sees them, for example jailbreak attempts. LiteLLM
# answers 400 and langchain-openai raises OpenAIInvalidRequestError, a subclass
# of openai.BadRequestError. The status code and body carry no structured code,
# so the LiteLLM error name in the message is the only signal.
CONTENT_FILTER_MARKER = "ContentPolicyViolationError"


def is_content_filtered(exc: BaseException) -> bool:
    """
    Tell whether an LLM error means the provider's content filter blocked the call.

    :param exc: An exception raised by the chat model.
    :return: True for a ``BadRequestError`` whose message names LiteLLM's
        ``ContentPolicyViolationError``; False for any other error, including
        other bad requests, which are our bugs.
    """
    return isinstance(exc, BadRequestError) and CONTENT_FILTER_MARKER in str(exc)


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
