import json
import logging
from contextvars import ContextVar

# Context variable for Request ID
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

# Third-party loggers that are too chatty at INFO. They stay at WARNING unless
# the app itself runs at DEBUG.
_QUIET_LOGGERS = (
    "httpx",
    "httpcore",
    "httpx2",
    "httpcore2",
    "openai",
    "litellm",
    "langfuse",
)

# Standard log attributes as a dictionary
_STANDARD = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)


class RequestIdFilter(logging.Filter):
    """Add the current request ID to each log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Attach the current request ID and keep the record."""
        record.request_id = request_id_ctx.get()  # read your ContextVar
        return True  # True = keep the record


class JsonFormatter(logging.Formatter):
    """Format log records as JSON."""

    def format(self, record: logging.LogRecord) -> str:
        """Serialize a log record and its exception, if present, as JSON."""

        payload = {
            "logger": record.name,
            "time": self.formatTime(record),
            "level": record.levelname,
            "message": record.getMessage(),
            "request_id": record.request_id,  # type: ignore
            "exception": self.formatException(record.exc_info)
            if record.exc_info
            else None,
        }

        # Add extra attributes to the log
        for key, value in record.__dict__.items():
            if key not in _STANDARD:
                payload[key] = value

        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    """
    Configure root logging with a JSON-formatted stream handler.

    :param level: Level name such as ``"INFO"`` or ``"DEBUG"`` (case-insensitive).
    :raises ValueError: If ``level`` is not a known logging level name.
    """
    levels = logging.getLevelNamesMapping()  # {"DEBUG": 10, "INFO": 20, ...}
    try:
        level_no = levels[level.upper()]
    except KeyError:
        raise ValueError(
            f"Unknown log level {level!r}; use one of {sorted(levels)}"
        ) from None

    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.handlers.clear()  # avoid duplicate lines if called more than once
    root.addHandler(handler)
    root.setLevel(level_no)

    third_party_level = (
        level_no if level_no <= logging.DEBUG else max(level_no, logging.WARNING)
    )

    for name in _QUIET_LOGGERS:
        logging.getLogger(name).setLevel(third_party_level)
