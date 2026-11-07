import uuid

from fastapi import APIRouter
from pydantic import UUID7, BaseModel, ConfigDict, Field

from helpdesk_rag_chatbot.api.dependencies import ChatServiceDependency


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
async def chat(body: ChatRequest, service: ChatServiceDependency) -> ChatResponse:
    """
    Handle a chat request and return a response.

    :param body: The chat request containing the input text.
    :param service: The chat service dependency.
    :return: A chat response containing the generated reply.
    """
    request_id = uuid.uuid7()
    answer = await service.reply(
        body.message,
        request_id=str(request_id),
        user_id=str(body.user_id),
        session_id=str(body.session_id),
    )
    return ChatResponse(request_id=request_id, answer=answer)
