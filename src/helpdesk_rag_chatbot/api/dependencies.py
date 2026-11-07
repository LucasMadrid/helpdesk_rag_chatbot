from typing import Annotated

from fastapi import Depends, Request

from helpdesk_rag_chatbot.services.chat import ChatService


def get_chat_service(request: Request) -> ChatService:
    """
    Return the ChatService that the app built once at startup.

    This only fetches the shared instance from ``app.state``; it builds nothing.
    The lifespan in ``main.py`` is the only place that creates it (ADR 0003).

    :param request: The incoming request, used to reach ``app.state``.
    :return: The shared ChatService instance.
    """
    return request.app.state.chat_service


# Define a dependency type for ChatService to be used in FastAPI routes
ChatServiceDependency = Annotated[ChatService, Depends(get_chat_service)]
