from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from importlib.metadata import version

from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware

from helpdesk_rag_chatbot.adapters.chat_history import create_chat_history_table
from helpdesk_rag_chatbot.adapters.db import build_db_pool
from helpdesk_rag_chatbot.adapters.llm import LLM_UNAVAILABLE_ERRORS, get_chat_model
from helpdesk_rag_chatbot.adapters.tracing import (
    get_callback_handlers,
    shutdown_tracing,
)
from helpdesk_rag_chatbot.api.chat import router as chat_router
from helpdesk_rag_chatbot.api.errors import llm_unavailable_handler
from helpdesk_rag_chatbot.api.health import router as health_router
from helpdesk_rag_chatbot.api.middleware import add_request_id
from helpdesk_rag_chatbot.config import Settings, get_settings
from helpdesk_rag_chatbot.services.chat import ChatService
from helpdesk_rag_chatbot.utils.logging_setup import configure_logging


def make_lifespan(settings: Settings | None = None):
    """
    Build the lifespan handler for the FastAPI application.

    :param settings: Settings to use. When None, the cached settings from
        ``get_settings()`` are read at startup (so importing this module never
        needs a valid ``.env``).
    :return: A lifespan context manager factory for ``FastAPI(lifespan=...)``.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """
        Manage the application's startup and shutdown.

        On startup, build a single ``ChatService`` (chat model plus tracing
        callbacks) and store it in ``app.state.chat_service``, so every request
        reuses it instead of creating its own (see ADR 0003). On shutdown, flush
        the buffered Langfuse traces so the last requests are not lost.

        :param app: The FastAPI application whose state holds the shared clients.
        """
        resolved = settings or get_settings()

        pool = build_db_pool(resolved)

        async with pool.connection() as conn:
            await create_chat_history_table(conn)

        app.state.db_pool = pool

        configure_logging(level=resolved.log_level)

        app.state.chat_service = ChatService(
            get_chat_model(resolved), callbacks=get_callback_handlers(resolved)
        )

        await pool.open()
        try:
            yield
        finally:
            # Shutdown: flush buffered traces so the last requests are not lost.
            shutdown_tracing(resolved)

            await pool.close()

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
    # Register error handlers: one per exception class, all answering 503
    for exc_type in LLM_UNAVAILABLE_ERRORS:
        app.add_exception_handler(exc_type, llm_unavailable_handler)
    # Register Routers
    app.include_router(health_router, tags=["health"])
    app.include_router(chat_router, tags=["chat"])
    return app
