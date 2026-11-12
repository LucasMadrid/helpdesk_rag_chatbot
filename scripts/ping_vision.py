"""Manual smoke test: send one screenshot to the real LiteLLM gateway.

Checks that the configured model accepts image input, by asking it to read an
image. Not part of pytest (it needs network access and real credentials). Run
it from the repo root with a populated ``.env``::

    uv run python scripts/ping_vision.py                      # ~/Desktop/vpn-error.png
    uv run python scripts/ping_vision.py path/to/screenshot.png

The image must be a PNG, JPEG or WebP. Paste the output into the PR description.
"""

import base64
import sys
from pathlib import Path

from langchain_core.messages import HumanMessage

from helpdesk_rag_chatbot.adapters.llm import get_chat_model
from helpdesk_rag_chatbot.config import get_settings

DEFAULT_IMAGE = Path.home() / "Desktop" / "vpn-error.png"

MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_IMAGE
    mime_type = MIME_TYPES.get(path.suffix.lower())
    if mime_type is None:
        print(f"FAILED: {path.name} is not a PNG, JPEG or WebP file")
        return 1
    if not path.is_file():
        print(f"FAILED: {path} not found")
        return 1

    settings = get_settings()
    print(f"model: {settings.litellm_model}")
    print(f"image: {path} ({mime_type}, {path.stat().st_size} bytes)")

    message = HumanMessage(
        content=[
            {"type": "text", "text": "What does this error say?"},
            {
                "type": "image",
                "base64": base64.b64encode(path.read_bytes()).decode(),
                "mime_type": mime_type,
            },
        ]
    )

    try:
        response = get_chat_model(settings).invoke([message])
    except Exception as exc:  # noqa: BLE001 - surface any failure for the PR
        print(f"FAILED: {type(exc).__name__}: {exc}")
        return 1

    print(f"reply: {response.content}")
    print(f"usage: {response.usage_metadata}")
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
