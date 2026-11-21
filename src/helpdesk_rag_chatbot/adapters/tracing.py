"""Langfuse tracing adapter.

Importing this module has no side effects: no client is created and no network
call is made. The handler is built on demand and only when tracing is enabled;
the client can also be built on its own, for commands such as the eval dataset
upload that talk to Langfuse whether or not the app traces.
"""

from importlib.metadata import version

from langchain_core.callbacks import BaseCallbackHandler
from langfuse import Langfuse, get_client
from langfuse.langchain import CallbackHandler

from helpdesk_rag_chatbot.config import Settings


def get_langfuse_handler(settings: Settings) -> CallbackHandler | None:
    """
    Build the Langfuse LangChain callback handler from the application settings.

    The handler does not take credentials itself: it looks up the client
    registered for its public key, so the client is built first.

    :param settings: Application settings providing the Langfuse configuration.
    :return: A CallbackHandler, or None when tracing is disabled.
    """
    if not settings.langfuse_enabled:
        return None
    get_langfuse_client(settings)  # registers the client the handler looks up by key
    return CallbackHandler(public_key=settings.langfuse_public_key.get_secret_value())


def get_langfuse_client(settings: Settings) -> Langfuse:
    """
    Build the Langfuse client from the application settings.

    Ignores ``LANGFUSE_ENABLED`` on purpose: that flag switches tracing of the
    running app, while callers of this function, such as the eval dataset
    upload, are explicit commands that must reach Langfuse either way.

    :param settings: Application settings providing the Langfuse configuration.
    :return: The client, tagged with the app environment and package version.
    """
    public_key = settings.langfuse_public_key.get_secret_value()
    # Langfuse keeps one client per public key; CallbackHandler finds it by key.
    client = Langfuse(
        public_key=public_key,
        secret_key=settings.langfuse_secret_key.get_secret_value(),
        # Strip the trailing slash: pydantic's HttpUrl turns "http://localhost:3000"
        # into "http://localhost:3000/", and the Langfuse SDK appends "/api/...",
        # so it would POST to "//api/public/otel/v1/traces". Langfuse answers that
        # with a 308 redirect, which the exporter does not follow, so every trace
        # is silently dropped (no error, no log line).
        base_url=str(settings.langfuse_base_url).rstrip("/"),
        environment=settings.app_env,
        # The package version, so a regression can be tied to a deploy.
        release=version("helpdesk_rag_chatbot"),
    )

    return client


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
