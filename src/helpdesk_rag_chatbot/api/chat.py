import base64
import binascii
import logging
import math
from typing import Literal, Self
from uuid import UUID

from fastapi import APIRouter
from pydantic import UUID7, BaseModel, ConfigDict, Field, model_validator

from helpdesk_rag_chatbot.api.dependencies import (
    ChatServiceDependency,
    RequestIdDependency,
    SessionStoreDependency,
)
from helpdesk_rag_chatbot.services.chat import ImageAttachment

logger = logging.getLogger(__name__)


def sniff_image_type(raw: bytes) -> str | None:
    if raw.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if raw.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    return None


MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB after decoding
MAX_IMAGE_B64_CHARS = 4 * math.ceil(MAX_IMAGE_BYTES / 3)  # base64: 4 chars per 3 bytes


class ChatRequest(BaseModel):
    """Request body for ``POST /chat``: who is asking, in which session, and what."""

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

    image: ImageInput | None = None


class ChatResponse(BaseModel):
    """Response body for ``POST /chat``: the generated answer and its request ID."""

    request_id: UUID7 = Field(
        description="The server-generated unique identifier (UUIDv7) of this request. It is also attached to traces, so the client can quote it when reporting a problem."
    )
    answer: str = Field(description="The generated response text from the chatbot.")


class ImageInput(BaseModel):
    media_type: Literal["image/png", "image/jpeg", "image/webp"]
    data: str = Field(min_length=1, max_length=MAX_IMAGE_B64_CHARS)

    @model_validator(mode="after")
    def check_bytes(self) -> Self:
        try:
            raw = base64.b64decode(self.data, validate=True)
        except binascii.Error:
            raise ValueError("data is not valid base64") from None

        if len(raw) > MAX_IMAGE_BYTES:
            raise ValueError(
                f"image is larger than {MAX_IMAGE_BYTES // (1024 * 1024)} MB"
            )

        if sniff_image_type(raw) != self.media_type:
            raise ValueError(f"data is not a valid {self.media_type} image")

        return self


router = APIRouter()


@router.post("/chat")
async def chat(
    body: ChatRequest,
    request_id: RequestIdDependency,
    service: ChatServiceDependency,
    sessions: SessionStoreDependency,
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

    history = await sessions.open_history(
        body.session_id, body.user_id, title=body.message[:80]
    )

    image = None
    if body.image is not None:
        image = ImageAttachment(mime_type=body.image.media_type, data=body.image.data)

    answer = await service.reply(
        body.message,
        request_id=request_id,
        user_id=str(body.user_id),
        session_id=str(body.session_id),
        history=history,
        image=image,
    )
    return ChatResponse(request_id=UUID(request_id), answer=answer)
