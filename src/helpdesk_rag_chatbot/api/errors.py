import logging

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
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


async def session_not_found_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Turn ``SessionNotFound`` into a 404 response.

    The same answer is given whether the session does not exist or belongs to
    another user, so a client cannot probe for other users' session ids. This is
    an expected client error, so it is logged at INFO without a traceback.

    :param request: The request that failed; its state holds the request ID.
    :param exc: The ``SessionNotFound`` raised while handling the request.
    :return: A 404 JSON response with a generic detail and the request ID.
    """

    request_id = request.state.request_id
    # An expected client error, so INFO and no traceback.
    logger.info("session not found", extra={"error_type": type(exc).__name__})

    return JSONResponse(
        status_code=404,
        content={
            "detail": "Session not found.",
            "request_id": request_id,
        },
    )


async def db_pool_timeout_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Turn a database pool timeout into a 503 response.

    ``PoolTimeout`` means every pooled connection stayed busy for the whole wait,
    so the service is overloaded, not broken: the client can retry. It is logged
    at WARNING with its traceback. The body carries the request ID but never the
    exception text.

    :param request: The request that failed; its state holds the request ID.
    :param exc: The ``PoolTimeout`` raised while getting a connection.
    :return: A 503 JSON response with a generic detail and the request ID.
    """
    logger.warning(
        "database pool timeout",
        exc_info=exc,
        extra={"error_type": type(exc).__name__},
    )
    return JSONResponse(
        status_code=503,
        content={
            "detail": "The service is busy. Please try again.",
            "request_id": request.state.request_id,
        },
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Turn a request validation error into a 422 response that never echoes input.

    FastAPI's default 422 repeats each field's ``input``, which for an image
    would send megabytes of base64 back to the client (and into logs). ``ctx``
    can hold the raw exception, which is not JSON-serialisable. Both are
    dropped; ``type``, ``loc`` and ``msg`` stay, so the client still sees which
    field failed and why. The request ID is added so the client can quote it.

    :param request: The request that failed; its state holds the request ID.
    :param exc: The ``RequestValidationError`` raised while validating the request.
    :return: A 422 JSON response with the trimmed errors and the request ID.
    """
    errors = [
        {k: v for k, v in e.items() if k not in ("input", "ctx")} for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "detail": jsonable_encoder(errors),
            "request_id": request.state.request_id,
        },
    )
