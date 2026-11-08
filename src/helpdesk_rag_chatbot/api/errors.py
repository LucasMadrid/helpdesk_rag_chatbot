import logging

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


async def llm_unavailable_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Turn an "LLM could not be reached" error into a 503 response.

    The error is transient, so it is logged at WARNING (not ERROR) with its
    traceback. The body carries the request ID so the client can quote it, but
    never the exception text, which can leak internal details such as the
    gateway URL.

    :param request: The request that failed; its state holds the request ID.
    :param exc: The LLM error raised while handling the request.
    :return: A 503 JSON response with a generic detail and the request ID.
    """
    request_id = request.state.request_id
    logger.warning(
        "llm unavailable",
        exc_info=exc,
        extra={"error_type": type(exc).__name__},
    )
    return JSONResponse(
        status_code=503,
        content={
            "detail": "The assistant is temporarily unavailable. Please try again.",
            "request_id": request_id,
        },
    )
