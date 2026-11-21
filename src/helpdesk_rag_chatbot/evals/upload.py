"""Upload evals/questions.yaml to the tune and holdout datasets in Langfuse.

Run with ``uv run python -m helpdesk_rag_chatbot.evals.upload``.
"""

import logging
from pathlib import Path

from helpdesk_rag_chatbot.adapters.tracing import get_langfuse_client
from helpdesk_rag_chatbot.config import get_settings
from helpdesk_rag_chatbot.evals.dataset import load_questions, upload_questions
from helpdesk_rag_chatbot.utils.logging_setup import configure_logging

QUESTIONS_FILE = Path("evals/questions.yaml")

logger = logging.getLogger(__name__)


def main() -> None:
    """
    Load the eval questions and upload them to Langfuse, then log the counts.

    Reads settings from the environment and talks to Langfuse even when
    ``LANGFUSE_ENABLED`` is false, because this is an explicit command. The
    counts are logged as one JSON line (``"eval dataset uploaded"`` with
    ``tune`` and ``holdout``), like the other commands' logs.

    :raises pydantic.ValidationError: If a question in the YAML is invalid.
    :raises ValueError: If two questions share an id.
    """
    settings = get_settings()
    configure_logging(level=settings.log_level)

    # Validate the whole file before anything reaches Langfuse.
    questions = load_questions(QUESTIONS_FILE)
    client = get_langfuse_client(settings)
    try:
        counts = upload_questions(client, questions)
    finally:
        client.shutdown()  # stop the SDK's background workers so the command exits

    logger.info("eval dataset uploaded", extra=counts)


if __name__ == "__main__":
    main()
