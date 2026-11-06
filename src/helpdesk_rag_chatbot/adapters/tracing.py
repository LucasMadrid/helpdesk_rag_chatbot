"""Langfuse tracing adapter.

Importing this module has no side effects: no client is created and no network
call is made. The handler is built on demand and only when tracing is enabled.
"""

from langchain_core.callbacks import BaseCallbackHandler
from langfuse import Langfuse, get_client
from langfuse.langchain import CallbackHandler

from helpdesk_rag_chatbot.config import Settings


def get_langfuse_handler(settings: Settings) -> CallbackHandler | None:
    """
    Build the Langfuse LangChain callback handler from the application settings.

    :param settings: Application settings providing the Langfuse configuration.
    :return: A CallbackHandler, or None when tracing is disabled.
    """
    if not settings.langfuse_enabled:
        return None
    public_key = settings.langfuse_public_key.get_secret_value()
    # Langfuse keeps one client per public key, so the handler below finds it.
    Langfuse(
        public_key=public_key,
        secret_key=settings.langfuse_secret_key.get_secret_value(),
        base_url=str(settings.langfuse_base_url),
    )
    return CallbackHandler(public_key=public_key)


def get_callback_handlers(settings: Settings) -> list[BaseCallbackHandler]:
    """
    Build the callback handlers for the chat service.

    :param settings: Application settings providing the Langfuse configuration.
    :return: A list with the Langfuse handler, or an empty list when tracing is off.
    """
    handler = get_langfuse_handler(settings)
    return [handler] if handler is not None else []


def shutdown_tracing(settings: Settings) -> None:
    """
    Flush pending traces and stop the Langfuse background workers.

    Langfuse sends traces in batches from a background thread, so without this
    the last traces before the app stops can be lost. Does nothing when tracing
    is disabled.

    :param settings: Application settings providing the Langfuse configuration.
    """
    if not settings.langfuse_enabled:
        return
    get_client(public_key=settings.langfuse_public_key.get_secret_value()).shutdown()
