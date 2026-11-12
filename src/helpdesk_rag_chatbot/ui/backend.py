"""What the chat UI needs from a backend, and the errors it understands.

``app.py`` only talks to a ``ChatBackend``. Two implementations satisfy it:
``DemoBackend`` (in memory, no API needed) and, from W3-03, ``HelpdeskClient``
(HTTP calls to the FastAPI app).
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID


@dataclass(frozen=True)
class ChatReply:
    answer: str
    request_id: str


@dataclass(frozen=True)
class SessionInfo:
    session_id: UUID
    title: str
    updated_at: datetime


@dataclass(frozen=True)
class Message:
    role: Literal["user", "assistant"]
    content: str


class ApiError(Exception):
    """A call failed. ``status`` is None when the backend could not be reached."""

    def __init__(
        self, status: int | None, detail: str, request_id: str | None = None
    ) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.request_id = request_id


class ChatBackend(Protocol):
    def chat(
        self,
        user_id: UUID,
        session_id: UUID,
        message: str,
        image: tuple[str, bytes] | None = None,
    ) -> ChatReply: ...

    def list_sessions(self, user_id: UUID) -> list[SessionInfo]: ...

    def get_messages(self, session_id: UUID, user_id: UUID) -> list[Message]: ...

    def delete_session(self, session_id: UUID, user_id: UUID) -> None: ...
