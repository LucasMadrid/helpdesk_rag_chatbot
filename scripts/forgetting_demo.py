"""Manual demo: watch the model forget when the history budget is small.

Sends a fixed conversation to a running API in ONE session, then asks about the
first message. Not part of pytest (it needs the real app, database and LLM).

1. Start the app with a small budget, e.g. ``HISTORY_MAX_TOKENS=400`` in ``.env``.
   That keeps the newest turns and drops the first one. Much smaller (e.g. 60)
   is below one answer, so no history is sent at all. ``--reload`` does not
   watch ``.env``: restart the server after changing it::

       uv run uvicorn helpdesk_rag_chatbot.main:create_app --factory --reload

2. Run this script from the repo root::

       uv run python scripts/forgetting_demo.py
       uv run python scripts/forgetting_demo.py --base-url http://localhost:8000

For each request it prints the status, latency, ``request_id`` and answer, plus
how many messages the server has stored for the session at that point
(``history_messages_total`` in the trace). The number of messages actually sent
to the model (``history_messages_sent``) is only visible in the trace: search
Langfuse for the printed ``request_id`` and read the trace metadata.
"""

import argparse
import sys
import time
from uuid import UUID, uuid7

import httpx

FACT = "My laptop is a Dell XPS"
FACT_KEYWORD = "xps"
FILLER = [
    "How do I reset my VPN password?",
    "My printer is offline, what should I check?",
    "How do I request a second monitor?",
    "Where can I find the office Wi-Fi password?",
]
FINAL_QUESTION = "What laptop do I have?"


def _post_chat(
    client: httpx.Client, user_id: UUID, session_id: UUID, message: str
) -> tuple[httpx.Response, float]:
    start = time.perf_counter()
    response = client.post(
        "/chat",
        json={
            "user_id": str(user_id),
            "session_id": str(session_id),
            "message": message,
        },
    )
    return response, time.perf_counter() - start


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument(
        "--user-id", type=UUID, default=None, help="default: new UUIDv7"
    )
    parser.add_argument(
        "--session-id", type=UUID, default=None, help="default: new UUIDv7"
    )
    parser.add_argument("--timeout", type=float, default=60.0, help="seconds/request")
    args = parser.parse_args()

    user_id = args.user_id or uuid7()
    session_id = args.session_id or uuid7()
    messages = [FACT, *FILLER, FINAL_QUESTION]

    print(f"api:        {args.base_url}")
    print(f"user_id:    {user_id}")
    print(f"session_id: {session_id}")
    print(f"messages:   {len(messages)}\n")

    stored = 0  # messages the server holds for this session before each request
    last_answer = ""
    failed = False
    rows: list[tuple[int, int, str, float, str]] = []

    with httpx.Client(base_url=args.base_url, timeout=args.timeout) as client:
        for number, message in enumerate(messages, start=1):
            print(f"[{number}/{len(messages)}] > {message}")
            try:
                response, elapsed = _post_chat(client, user_id, session_id, message)
            except httpx.HTTPError as exc:
                print(f"    FAILED: {type(exc).__name__}: {exc}\n")
                failed = True
                break

            if response.status_code != 200:
                print(f"    HTTP {response.status_code} after {elapsed:.2f}s")
                print(f"    body: {response.text}\n")
                failed = True
                break

            body = response.json()
            request_id = body["request_id"]
            last_answer = body["answer"]
            print(
                f"    HTTP 200 in {elapsed:.2f}s  request_id={request_id}\n"
                f"    history_messages_total (expected) = {stored}\n"
                f"    answer: {last_answer!r}\n"
            )
            rows.append((number, stored, request_id, elapsed, message))
            stored += 2  # this question + its answer are saved after success

        if not failed:
            sessions = client.get("/sessions", params={"user_id": str(user_id)})
            print(f"GET /sessions -> HTTP {sessions.status_code}")
            for item in sessions.json() if sessions.status_code == 200 else []:
                print(f"    {item['session_id']}  {item['title']!r}")
            print()

    print("Summary")
    print(f"{'#':>2}  {'total':>5}  {'latency':>8}  request_id")
    for number, total, request_id, elapsed, _ in rows:
        print(f"{number:>2}  {total:>5}  {elapsed:>7.2f}s  {request_id}")

    if failed:
        print("\nStopped early: see the error above and the app's own logs.")
        return 1

    remembered = FACT_KEYWORD in last_answer.lower()
    print(f"\nFinal question: {FINAL_QUESTION!r}")
    print(f"Answer mentions {FACT_KEYWORD.upper()!r}: {remembered}")
    print(
        "-> The model REMEMBERED the first message."
        if remembered
        else "-> The model FORGOT the first message (its turn was trimmed)."
    )
    last_id = rows[-1][2]
    print(
        f"\nNext: open the Langfuse trace for request_id={last_id} and read\n"
        "metadata.history_messages_sent. 'sent' < 'total' means trimming dropped\n"
        "older messages from the prompt (they are still stored in Postgres)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
