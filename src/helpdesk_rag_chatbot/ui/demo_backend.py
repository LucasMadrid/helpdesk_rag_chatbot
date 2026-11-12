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
    def __init__(self) -> None:
        self._sessions: dict[UUID, _Session] = {}

    def chat(
        self,
        user_id: UUID,
        session_id: UUID,
        message: str,
        image: tuple[str, bytes] | None = None,
    ) -> ChatReply:
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
        mine = [
            SessionInfo(sid, s.title, s.updated_at)
            for sid, s in self._sessions.items()
            if s.user_id == user_id
        ]
        return sorted(mine, key=lambda s: s.updated_at, reverse=True)[:50]

    def get_messages(self, session_id: UUID, user_id: UUID) -> list[Message]:
        return list(self._owned(session_id, user_id).messages)

    def delete_session(self, session_id: UUID, user_id: UUID) -> None:
        self._owned(session_id, user_id)
        del self._sessions[session_id]

    def _owned(self, session_id: UUID, user_id: UUID) -> _Session:
        session = self._sessions.get(session_id)
        if session is None or session.user_id != user_id:
            raise ApiError(404, "Session not found.", str(uuid7()))
        return session
