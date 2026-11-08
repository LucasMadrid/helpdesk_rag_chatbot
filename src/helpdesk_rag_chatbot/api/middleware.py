import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response


async def add_request_id(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """
    Attach a unique request ID to the request and its response.

    The ID is stored in ``request.state.request_id`` and returned in the
    ``X-Request-ID`` header. The ``/chat`` route reads it from the request state,
    so this middleware must stay registered in ``create_app``; without it the
    route fails with an ``AttributeError``.
    """
    request_id = str(uuid.uuid7())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response
