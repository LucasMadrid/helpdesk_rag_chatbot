from contextlib import asynccontextmanager
from importlib.metadata import version

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware

from helpdesk_rag_chatbot.adapters.llm import get_chat_model
from helpdesk_rag_chatbot.adapters.tracing import (
    get_callback_handlers,
    shutdown_tracing,
)
from helpdesk_rag_chatbot.api.chat import router as chat_router
from helpdesk_rag_chatbot.api.health import router as health_router
from helpdesk_rag_chatbot.api.middleware import add_request_id
from helpdesk_rag_chatbot.config import Settings, get_settings
from helpdesk_rag_chatbot.services.chat import ChatService


def make_lifespan(settings: Settings | None = None):
    """
    Build the lifespan handler for the FastAPI application.

    :param settings: Settings to use. When None, the cached settings from
        ``get_settings()`` are read at startup (so importing this module never
        needs a valid ``.env``).
    :return: A lifespan context manager factory for ``FastAPI(lifespan=...)``.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """
        Manage the application's startup and shutdown.

        On startup, build a single ``ChatService`` (chat model plus tracing
        callbacks) and store it in ``app.state.chat_service``, so every request
        reuses it instead of creating its own (see ADR 0003). On shutdown, flush
        the buffered Langfuse traces so the last requests are not lost.

        :param app: The FastAPI application whose state holds the shared clients.
        """
        resolved = settings or get_settings()
        app.state.chat_service = ChatService(
            get_chat_model(resolved), callbacks=get_callback_handlers(resolved)
        )
        try:
            yield
        finally:
            # Shutdown: flush buffered traces so the last requests are not lost.
            shutdown_tracing(resolved)

    return lifespan


def create_app(settings: Settings | None = None) -> FastAPI:
    """
    Create and configure the FastAPI application.

    :param settings: Optional settings, mainly for tests. Defaults to ``get_settings()``.
    :return: The configured FastAPI application.
    """
    app = FastAPI(
        title="Helpdesk RAG Chatbot API",
        version=version("helpdesk_rag_chatbot"),
        lifespan=make_lifespan(settings),
    )
    # Register request ID middleware
    app.add_middleware(BaseHTTPMiddleware, dispatch=add_request_id)
    # Register Routers
    app.include_router(health_router, tags=["health"])
    app.include_router(chat_router, tags=["chat"])
    return app
