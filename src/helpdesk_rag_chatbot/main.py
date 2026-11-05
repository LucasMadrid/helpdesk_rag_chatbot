from importlib.metadata import version

from fastapi import FastAPI

from helpdesk_rag_chatbot.api.chat import router as chat_router
from helpdesk_rag_chatbot.api.health import router as health_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Helpdesk RAG Chatbot API", version=version("helpdesk_rag_chatbot")
    )
    app.include_router(health_router, tags=["health"])
    app.include_router(chat_router, tags=["chat"])
    return app
