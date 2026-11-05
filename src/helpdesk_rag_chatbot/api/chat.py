from uuid import uuid7

from fastapi import APIRouter
from pydantic import UUID7, BaseModel, ConfigDict, Field

from helpdesk_rag_chatbot.api.dependencies import ChatServiceDependency


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    user_id: UUID7 | None = Field(
        description="The unique identifier of the user making the request. If not provided, a new UUID will be generated for the session."
    )
    session_id: UUID7 | None = Field(
        description="The unique identifier of the chat session. If not provided, a new UUID will be generated for the session."
    )
    message: str = Field(
        description="The input message to send to the chatbot.",
        min_length=1,
        max_length=1000,
    )


class ChatResponse(BaseModel):
    request_id: UUID7 = Field(
        description="The unique identifier of the chat request. This is returned to the client for tracking purposes."
    )
    answer: str = Field(description="The generated response text from the chatbot.")


router = APIRouter()


@router.post("/chat")
async def chat(body: ChatRequest, service: ChatServiceDependency) -> ChatResponse:
    """
    Handle a chat request and return a response.

    :param body: The chat request containing the input text.
    :param service: The chat service dependency.
    :return: A chat response containing the generated reply.
    """
    answer = await service.reply(body.message)
    return ChatResponse(request_id=uuid7(), answer=answer)
