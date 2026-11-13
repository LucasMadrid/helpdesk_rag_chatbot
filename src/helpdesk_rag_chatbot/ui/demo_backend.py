"""An in-memory ChatBackend so the UI runs, and is tested, without the API.

It copies the API's rules that the UI can see: a new session id creates a
session titled with the first 80 characters, another user's session is a 404,
and an image is stored only as an ``[image: <type>]`` marker (ADR 0008).
Send a message containing "simulate error" to see the UI's error state.
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid7

from helpdesk_rag_chatbot.ui.backend import ApiError, ChatReply, Message, SessionInfo

DEMO_ANSWER = (
    "This is a demo answer: the UI is not connected to the API yet.\n\n"
    "_Source: none (demo mode)_"
)


@dataclass
class _Session:
    user_id: UUID
    title: str
    updated_at: datetime
    messages: list[Message] = field(default_factory=list)


class DemoBackend:
    """A ``ChatBackend`` that keeps sessions in memory and gives a fixed answer."""

    def __init__(self) -> None:
        self._sessions: dict[UUID, _Session] = {}

    def chat(
        self,
        user_id: UUID,
        session_id: UUID,
        message: str,
        image: tuple[str, bytes] | None = None,
    ) -> ChatReply:
        """
        Store the message and return the demo answer.

        A message containing "simulate error" raises a 503 instead.

        :param user_id: The user sending the message.
        :param session_id: The chat to add the message to; a new id creates it.
        :param message: The user's text.
        :param image: An optional ``(mime_type, raw_bytes)`` screenshot, stored
            only as a marker.
        :return: The demo reply.
        :raises ApiError: 503 on "simulate error", 404 if the session belongs to
            another user.
        """
        if "simulate error" in message.lower():
            raise ApiError(
                503,
                "The assistant is temporarily unavailable. Please try again.",
                str(uuid7()),
            )
        session = self._sessions.get(session_id)
        if session is None:
            session = _Session(user_id, message[:80], datetime.now(UTC))
            self._sessions[session_id] = session
        elif session.user_id != user_id:
            raise ApiError(404, "Session not found.", str(uuid7()))

        saved = message if image is None else f"{message}\n[image: {image[0]}]"
        session.messages += [
            Message("user", saved),
            Message("assistant", DEMO_ANSWER),
        ]
        session.updated_at = datetime.now(UTC)
        return ChatReply(DEMO_ANSWER, str(uuid7()))

    def list_sessions(self, user_id: UUID) -> list[SessionInfo]:
        """
        List a user's chats, most recently updated first, at most 50.

        :param user_id: The user whose chats to list.
        :return: The user's sessions.
        """
        mine = [
            SessionInfo(sid, s.title, s.updated_at)
            for sid, s in self._sessions.items()
            if s.user_id == user_id
        ]
        return sorted(mine, key=lambda s: s.updated_at, reverse=True)[:50]

    def get_messages(self, session_id: UUID, user_id: UUID) -> list[Message]:
        """
        Return a copy of a chat's messages, oldest first.

        :param session_id: The chat to read.
        :param user_id: The user who owns the chat.
        :return: The chat's messages.
        :raises ApiError: 404 if the chat doesn't exist or isn't the user's.
        """
        return list(self._owned(session_id, user_id).messages)

    def delete_session(self, session_id: UUID, user_id: UUID) -> None:
        """
        Delete a chat and all its messages.

        :param session_id: The chat to delete.
        :param user_id: The user who owns the chat.
        :raises ApiError: 404 if the chat doesn't exist or isn't the user's.
        """
        self._owned(session_id, user_id)
        del self._sessions[session_id]

    def _owned(self, session_id: UUID, user_id: UUID) -> _Session:
        session = self._sessions.get(session_id)
        if session is None or session.user_id != user_id:
            raise ApiError(404, "Session not found.", str(uuid7()))
        return session
