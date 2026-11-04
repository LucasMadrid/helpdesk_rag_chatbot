from fastapi import FastAPI

from helpdesk_rag_chatbot.api.health import router as health_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="Helpdesk RAG Chatbot API", version="1.0.0")
    app.include_router(health_router)
    return app
