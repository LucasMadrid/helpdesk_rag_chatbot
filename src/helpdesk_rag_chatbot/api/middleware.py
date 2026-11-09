import logging
import time
import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from helpdesk_rag_chatbot.utils.logging_setup import request_id_ctx

logger = logging.getLogger(__name__)


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
    request_id_token = request_id_ctx.set(request_id)
    request.state.request_id = request_id

    start_time = time.perf_counter()
    # Health checks are polled constantly, so keep them out of INFO.
    level = logging.DEBUG if request.url.path == "/health" else logging.INFO
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request failed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": 500,
                "duration_ms": round((time.perf_counter() - start_time) * 1000, 1),
            },
        )
        # Return the 500 here instead of re-raising: re-raising would make the
        # server log the same traceback again and send a body with no request ID.
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "request_id": request_id},
            headers={"X-Request-ID": request_id},
        )
    else:
        response.headers["X-Request-ID"] = request_id
        logger.log(
            level,
            "request completed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - start_time) * 1000, 1),
            },
        )
        return response
    finally:
        # Runs after the log calls above, so they still see the request ID.
        request_id_ctx.reset(request_id_token)
