import logging
from uuid import UUID

from fastapi import APIRouter
from pydantic import UUID7, BaseModel, ConfigDict, Field

from helpdesk_rag_chatbot.api.dependencies import (
    ChatServiceDependency,
    RequestIdDependency,
)

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    user_id: UUID7 = Field(
        description="The unique identifier (UUIDv7) of the user making the request."
    )
    session_id: UUID7 = Field(
        description="The unique identifier (UUIDv7) of the chat session."
    )
    message: str = Field(
        description="The input message to send to the chatbot.",
        min_length=1,
        max_length=1000,
    )


class ChatResponse(BaseModel):
    request_id: UUID7 = Field(
        description="The server-generated unique identifier (UUIDv7) of this request. It is also attached to traces, so the client can quote it when reporting a problem."
    )
    answer: str = Field(description="The generated response text from the chatbot.")


router = APIRouter()


@router.post("/chat")
async def chat(
    body: ChatRequest, request_id: RequestIdDependency, service: ChatServiceDependency
) -> ChatResponse:
    """
    Handle a chat request and return the generated response.

    :param body: The validated request containing the user, session, and message.
    :param request_id: The ID the request ID middleware assigned to this request.
    :param service: The service that generates a reply for the chat message.
    :return: The generated answer and the request ID used to track this call.
    """
    logger.info(
        "chat request received",
        extra={"user_id": str(body.user_id), "message_length": len(body.message)},
    )

    raise RuntimeError("boom")

    answer = await service.reply(
        body.message,
        request_id=request_id,
        user_id=str(body.user_id),
        session_id=str(body.session_id),
    )
    return ChatResponse(request_id=UUID(request_id), answer=answer)
