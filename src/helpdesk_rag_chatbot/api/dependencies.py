from typing import Annotated

from fastapi import Depends

from helpdesk_rag_chatbot.adapters.llm import get_chat_model
from helpdesk_rag_chatbot.config import Settings, get_settings
from helpdesk_rag_chatbot.services.chat import ChatService


def get_chat_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> ChatService:
    """
    Build a ChatService instance using the provided settings.

    :param settings: Application settings providing the chat model configuration.
    :return: A ChatService instance configured with the appropriate chat model.
    """
    chat_model = get_chat_model(settings)
    return ChatService(chat_model)


# Define a dependency type for ChatService to be used in FastAPI routes
ChatServiceDependency = Annotated[ChatService, Depends(get_chat_service)]
