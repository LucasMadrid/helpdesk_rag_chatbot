from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import UUID7, BaseModel

from helpdesk_rag_chatbot.adapters.sessions import SessionSummary
from helpdesk_rag_chatbot.api.dependencies import SessionStoreDependency

router = APIRouter()

_ROLE = {"human": "user", "ai": "assistant"}


class MessageOut(BaseModel):
    role: Literal["user", "assistant"]
    content: str


@router.get("/sessions")
async def list_sessions(
    user_id: Annotated[UUID7, Query()], sessions: SessionStoreDependency
) -> list[SessionSummary]:
    """
    List a user's chat sessions, most recently updated first.

    Returns at most 50 sessions, and only those owned by ``user_id``. A user
    with no sessions gets an empty list, not a 404.

    :param user_id: The user (UUIDv7, query parameter) whose sessions to list.
    :param sessions: The session store backed by this request's connection.
    :return: The user's session summaries (id, title, created and updated times).
    """
    return await sessions.list_sessions(user_id)


@router.get("/sessions/{session_id}/messages")
async def list_messages(
    session_id: UUID7,
    user_id: Annotated[UUID7, Query()],
    sessions: SessionStoreDependency,
) -> list[MessageOut]:
    """
    Return the messages of one of a user's chat sessions, oldest first.

    Only the owner can read a session. If the session doesn't exist or belongs
    to another user the response is a 404 (``SessionNotFound``), so a client
    can't tell the two cases apart. Messages other than user and assistant
    (such as system or tool messages) are skipped.

    :param session_id: The session (UUIDv7, path parameter) to read.
    :param user_id: The user (UUIDv7, query parameter) who must own the session.
    :param sessions: The sessions store backed by this request's connection.
    :return: The session's messages in the order they were added.
    :raises SessionNotFound: If the session is missing or owned by someone else.
    """
    messages = await sessions.get_messages(session_id, user_id)

    return [
        MessageOut(role=_ROLE[m.type], content=m.text)
        for m in messages
        if m.type in _ROLE
    ]


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: UUID7,
    user_id: Annotated[UUID7, Query()],
    sessions: SessionStoreDependency,
):
    """
    Delete one of a user's chat sessions together with its messages.

    Responds with 204 and no body on success. If the session doesn't exist or
    belongs to another user, nothing is deleted and the response is a 404
    (``SessionNotFound``), so a client can't tell the two cases apart.

    :param session_id: The session (UUIDv7, path parameter) to delete.
    :param user_id: The user (UUIDv7, query parameter) who must own the session.
    :param sessions: The session store backed by this request's connection.
    :raises SessionNotFound: If the session is missing or owned by someone else.
    """
    await sessions.delete_session(session_id, user_id)
