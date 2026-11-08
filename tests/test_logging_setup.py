"""Tests for the logging setup (helpdesk_rag_chatbot.utils.logging_setup)."""

import json
import logging
import sys
from datetime import UTC, datetime
from uuid import uuid7

import pytest

from helpdesk_rag_chatbot.utils.logging_setup import (
    _QUIET_LOGGERS,
    JsonFormatter,
    RequestIdFilter,
    configure_logging,
    request_id_ctx,
)


def make_record(
    msg: str = "hello",
    *args: object,
    level: int = logging.INFO,
    exc_info: tuple | None = None,
    **extra: object,
) -> logging.LogRecord:
    """Build a record the way ``logger.info(msg, *args, extra=extra)`` would."""
    return logging.getLogger("test.logger").makeRecord(
        "test.logger", level, __file__, 1, msg, args, exc_info, extra=extra or None
    )


def format_record(record: logging.LogRecord) -> dict:
    return json.loads(JsonFormatter().format(record))


# --- JsonFormatter ---------------------------------------------------------


def test_formatter_prints_the_core_fields() -> None:
    record = make_record("user %s logged in", "ana", level=logging.WARNING)

    data = format_record(record)

    assert data["logger"] == "test.logger"
    assert data["level"] == "WARNING"
    assert data["message"] == "user ana logged in"  # %s was filled in
    assert data["exception"] is None
    assert data["time"]


def test_formatter_includes_extra_fields() -> None:
    data = format_record(make_record(status=200, duration_ms=12.5))

    assert data["status"] == 200
    assert data["duration_ms"] == 12.5


def test_formatter_serialises_values_json_cannot() -> None:
    # Without default=str this would raise TypeError and the line would be lost.
    some_id = uuid7()
    moment = datetime(2026, 11, 8, tzinfo=UTC)

    data = format_record(make_record(id=some_id, when=moment))

    assert data["id"] == str(some_id)
    assert data["when"] == str(moment)


def test_extra_cannot_overwrite_core_fields() -> None:
    record = make_record("real message", level=logging.INFO, request_id="ignored")
    record.__dict__.update({"level": "FAKE", "logger": "fake", "time": "never"})

    data = format_record(record)

    assert data["level"] == "INFO"
    assert data["logger"] == "test.logger"
    assert data["time"] != "never"


def test_formatter_includes_the_traceback() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = make_record("failed", exc_info=sys.exc_info())

    data = format_record(record)

    assert "ValueError: boom" in data["exception"]


def test_formatter_works_on_a_record_that_skipped_the_filter() -> None:
    # caplog and other handlers can hand over records with no request_id.
    data = format_record(make_record())

    assert data["request_id"] == "-"


def test_request_id_is_printed_once() -> None:
    record = make_record()
    RequestIdFilter().filter(record)

    line = JsonFormatter().format(record)

    assert line.count('"request_id"') == 1


# --- RequestIdFilter -------------------------------------------------------


def test_filter_copies_the_context_request_id_onto_the_record() -> None:
    token = request_id_ctx.set("abc-123")
    try:
        record = make_record()
        keep = RequestIdFilter().filter(record)
    finally:
        request_id_ctx.reset(token)

    assert keep is True
    assert record.request_id == "abc-123"  # type: ignore[attr-defined]


def test_filter_uses_the_default_outside_a_request() -> None:
    record = make_record()

    RequestIdFilter().filter(record)

    assert record.request_id == "-"  # type: ignore[attr-defined]


# --- configure_logging -----------------------------------------------------


def test_unknown_level_is_rejected_with_a_clear_message() -> None:
    with pytest.raises(ValueError, match="verbose"):
        configure_logging("verbose")


@pytest.mark.parametrize("name", ["debug", "DEBUG", "Debug"])
def test_level_name_is_case_insensitive(name: str) -> None:
    configure_logging(name)

    assert logging.getLogger().level == logging.DEBUG


def test_calling_it_twice_does_not_duplicate_handlers() -> None:
    configure_logging("INFO")
    configure_logging("INFO")

    assert len(logging.getLogger().handlers) == 1


@pytest.mark.parametrize("name", _QUIET_LOGGERS)
def test_third_party_loggers_are_quiet_at_info(name: str) -> None:
    configure_logging("INFO")

    assert logging.getLogger(name).level == logging.WARNING


@pytest.mark.parametrize("name", _QUIET_LOGGERS)
def test_third_party_loggers_are_loud_at_debug(name: str) -> None:
    configure_logging("DEBUG")

    assert logging.getLogger(name).level == logging.DEBUG


def test_third_party_loggers_are_never_louder_than_the_app() -> None:
    # At ERROR the app wants errors only, so httpx warnings must not slip through.
    configure_logging("ERROR")

    assert logging.getLogger("httpx").level == logging.ERROR


def test_end_to_end_line_has_request_id_and_extras(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("INFO")
    token = request_id_ctx.set("req-1")
    try:
        logging.getLogger("helpdesk_rag_chatbot.demo").info(
            "done", extra={"status": 200}
        )
    finally:
        request_id_ctx.reset(token)

    data = json.loads(capsys.readouterr().err)

    assert data["message"] == "done"
    assert data["request_id"] == "req-1"
    assert data["status"] == 200


def test_end_to_end_third_party_info_is_dropped(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("INFO")

    logging.getLogger("httpx").info("HTTP Request: POST ...")
    logging.getLogger("httpx").warning("slow response")

    lines = capsys.readouterr().err.strip().splitlines()
    assert [json.loads(line)["message"] for line in lines] == ["slow response"]
