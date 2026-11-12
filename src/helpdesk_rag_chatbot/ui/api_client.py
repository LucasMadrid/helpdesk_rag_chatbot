"""A ChatBackend that calls the helpdesk FastAPI app over HTTP.

Every failure surfaces as ``ApiError``, so the UI handles one exception type:
an error response from the API keeps its status, detail and request ID, and a
server that cannot be reached (or that answers with something unreadable) has
no usable status or detail of its own.
"""

import base64
from collections.abc import Callable
from datetime import datetime
from typing import Any
from uuid import UUID

import httpx

from helpdesk_rag_chatbot.ui.backend import ApiError, ChatReply, Message, SessionInfo

_UNREACHABLE = "Could not reach the server. Please try again."
_UNEXPECTED = "The server sent an unexpected response."


class HelpdeskClient:
    """
    The ``ChatBackend`` implementation backed by the helpdesk HTTP API.

    :param base_url: Where the API is served, e.g. ``http://localhost:8000``.
    :param timeout: Seconds to wait for each request before giving up.
    :param transport: Replaces the network layer; used by tests to fake the API.
    """

    def __init__(
        self,
        base_url: str,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._client = httpx.Client(
            base_url=base_url, timeout=timeout, transport=transport
        )

    def chat(
        self,
        user_id: UUID,
        session_id: UUID,
        message: str,
        image: tuple[str, bytes] | None = None,
    ) -> ChatReply:
        """
        Send a message and return the assistant's answer.

        :param user_id: The user asking.
        :param session_id: The session to chat in; a new id starts a session.
        :param message: The user's text.
        :param image: Optional ``(media_type, raw_bytes)`` sent with the message.
        :return: The answer and the request ID of this call.
        :raises ApiError: On any HTTP error or unreachable server.
        """
        body: dict[str, Any] = {
            "user_id": str(user_id),
            "session_id": str(session_id),
            "message": message,
        }
        if image is not None:
            media_type, raw = image
            body["image"] = {
                "media_type": media_type,
                "data": base64.b64encode(raw).decode("ascii"),
            }
        response = self._send("POST", "/chat", json=body)
        data = self._json(response)
        return self._parse(
            response, lambda: ChatReply(data["answer"], str(data["request_id"]))
        )

    def list_sessions(self, user_id: UUID) -> list[SessionInfo]:
        """
        List the user's sessions, most recently updated first.

        :param user_id: The user whose sessions to list.
        :return: The user's sessions; empty if there are none.
        :raises ApiError: On any HTTP error or unreachable server.
        """
        response = self._send("GET", "/sessions", params={"user_id": str(user_id)})
        data = self._json(response)
        return self._parse(
            response,
            lambda: [
                SessionInfo(
                    UUID(s["session_id"]),
                    s["title"],
                    datetime.fromisoformat(s["updated_at"]),
                )
                for s in data
            ],
        )

    def get_messages(self, session_id: UUID, user_id: UUID) -> list[Message]:
        """
        Read the messages of one of the user's sessions, oldest first.

        :param session_id: The session to read.
        :param user_id: The user who must own the session.
        :return: The session's user and assistant messages.
        :raises ApiError: On any HTTP error (404 if not the owner) or unreachable
            server.
        """
        response = self._send(
            "GET",
            f"/sessions/{session_id}/messages",
            params={"user_id": str(user_id)},
        )
        data = self._json(response)
        return self._parse(
            response, lambda: [Message(m["role"], m["content"]) for m in data]
        )

    def delete_session(self, session_id: UUID, user_id: UUID) -> None:
        """
        Delete one of the user's sessions together with its messages.

        :param session_id: The session to delete.
        :param user_id: The user who must own the session.
        :raises ApiError: On any HTTP error (404 if not the owner) or unreachable
            server.
        """
        self._send(
            "DELETE", f"/sessions/{session_id}", params={"user_id": str(user_id)}
        )

    def _send(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Make a request; turn a network failure or error status into ApiError."""
        try:
            response = self._client.request(method, url, **kwargs)
        except httpx.HTTPError as exc:
            raise ApiError(None, _UNREACHABLE) from exc
        if response.is_error:
            raise _error_from(response)
        return response

    @staticmethod
    def _json(response: httpx.Response) -> Any:
        """Decode a success body, or raise ApiError if it is not JSON."""
        try:
            return response.json()
        except ValueError as exc:
            raise _unexpected(response) from exc

    @staticmethod
    def _parse[T](response: httpx.Response, build: Callable[[], T]) -> T:
        """Build a result from a success body, or raise ApiError if it is malformed."""
        try:
            return build()
        except (KeyError, TypeError, ValueError) as exc:
            raise _unexpected(response) from exc


def _unexpected(response: httpx.Response) -> ApiError:
    return ApiError(
        response.status_code, _UNEXPECTED, response.headers.get("X-Request-ID")
    )


def _error_from(response: httpx.Response) -> ApiError:
    """
    Turn an error response into an ``ApiError``.

    The API answers errors with ``{"detail": ..., "request_id": ...}``. ``detail``
    is a string, or for a 422 a list of field errors, of which the first ``msg``
    is used (the API's messages already name the field). Anything else (a proxy's HTML page, an empty body) falls back to
    the HTTP reason phrase. The request ID comes from the body, else the
    ``X-Request-ID`` header.
    """
    request_id = response.headers.get("X-Request-ID")
    detail = response.reason_phrase or f"HTTP {response.status_code}"
    try:
        body = response.json()
    except ValueError:
        body = None

    if isinstance(body, dict):
        request_id = body.get("request_id") or request_id
        raw = body.get("detail")
        if isinstance(raw, str) and raw:
            detail = raw
        elif isinstance(raw, list) and raw and isinstance(raw[0], dict):
            detail = str(raw[0].get("msg") or detail)
    return ApiError(response.status_code, detail, request_id)
