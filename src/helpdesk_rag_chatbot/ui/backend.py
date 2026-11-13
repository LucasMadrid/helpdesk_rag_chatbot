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
    """The assistant's answer to one message, with the request id to quote."""

    answer: str
    request_id: str


@dataclass(frozen=True)
class SessionInfo:
    """One chat in the sidebar: its id, title and last update time."""

    session_id: UUID
    title: str
    updated_at: datetime


@dataclass(frozen=True)
class Message:
    """One message of a stored chat."""

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
    """The calls the chat UI makes. Every method raises ``ApiError`` on failure."""

    def chat(
        self,
        user_id: UUID,
        session_id: UUID,
        message: str,
        image: tuple[str, bytes] | None = None,
    ) -> ChatReply:
        """
        Send a message, creating the session if its id is new.

        :param user_id: The user sending the message.
        :param session_id: The chat to add the message to.
        :param message: The user's text.
        :param image: An optional ``(mime_type, raw_bytes)`` screenshot.
        :return: The assistant's reply.
        :raises ApiError: If the call fails or the session belongs to another
            user.
        """
        ...

    def list_sessions(self, user_id: UUID) -> list[SessionInfo]:
        """
        List a user's chats, most recently updated first.

        :param user_id: The user whose chats to list.
        :return: The user's sessions.
        :raises ApiError: If the call fails.
        """
        ...

    def get_messages(self, session_id: UUID, user_id: UUID) -> list[Message]:
        """
        Return a chat's messages, oldest first.

        :param session_id: The chat to read.
        :param user_id: The user who owns the chat.
        :return: The chat's messages.
        :raises ApiError: If the call fails or the chat is not the user's.
        """
        ...

    def delete_session(self, session_id: UUID, user_id: UUID) -> None:
        """
        Delete a chat and all its messages.

        :param session_id: The chat to delete.
        :param user_id: The user who owns the chat.
        :raises ApiError: If the call fails or the chat is not the user's.
        """
        ...
