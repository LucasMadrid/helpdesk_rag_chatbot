"""Manual smoke test: send one ``invoke("ping")`` to the real LiteLLM gateway.

Not part of pytest (it needs network access and real credentials). Run it from
the repo root with a populated ``.env``::

    uv run python scripts/ping_llm.py

Paste the output into the PR description.
"""

import sys
import time

from helpdesk_rag_chatbot.adapters.llm import get_chat_model
from helpdesk_rag_chatbot.config import get_settings


def main() -> int:
    settings = get_settings()
    print(f"gateway: {settings.litellm_url}")
    print(f"model:   {settings.litellm_model}")
    print(f"timeout: {settings.llm_timeout}s")

    model = get_chat_model(settings)

    start = time.perf_counter()
    try:
        response = model.invoke("ping")
    except Exception as exc:  # noqa: BLE001 - surface any failure for the PR
        print(f"FAILED: {type(exc).__name__}: {exc}")
        return 1
    elapsed = time.perf_counter() - start

    print(f"latency: {elapsed:.2f}s")
    print(f"reply:   {response.content!r}")
    print(f"usage:   {response.usage_metadata}")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
