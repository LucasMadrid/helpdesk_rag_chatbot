# 0008. Send images to the model once and never store them

- **Status:** Accepted
- **Date:** 2026-11-12

## Context

Helpdesk users want to send a screenshot of an error dialog, and academy Project 1 requires image input. W3-01 adds an optional image to `POST /chat`.

An image raises three questions the text-only API never had:

- **How does it travel?** `POST /chat` is one JSON body today, with Pydantic validation and tests built around it.
- **Can we trust it?** An upload is the easiest way to hurt an API: a huge string, junk that is not base64, or a file that says it is a PNG and is not. The client's declared type proves nothing.
- **What happens to it after the call?** Since W2-02 every question is saved to `chat_history` and resent on later turns, trimmed to `HISTORY_MAX_TOKENS` (ADR 0005, ADR 0007). A screenshot is hundreds of KB of base64.

Constraints:

- `ChatService` stays free of API types (dependencies point inwards: `api` -> `services`).
- The model behind the gateway must accept images. Checked before the ticket: `gpt-5.4-nano` through LiteLLM read the text of a VPN error screenshot (`scripts/ping_vision.py`).
- No new dependency for a check we can do in a few lines.

## Options considered

How the image travels:

1. **Multipart upload** (`UploadFile`). Standard for files and no base64 overhead, but the body is no longer JSON: the schema, the error format and every test change.
2. **Base64 inside the JSON body.** One body, one Pydantic model, the same 422 errors. Costs about 33% more bytes (4 characters for every 3 bytes).

What is stored:

1. **Store the image in `chat_history`** with the question. Follow-up questions can still see it, but every row grows by the image's size, every later turn resends it (cost, and it eats the history budget of ADR 0007), and the database now holds user screenshots, which can contain personal data.
2. **Store the image elsewhere** (object storage) and keep a reference. Keeps follow-ups possible without bloating the history, but needs new infrastructure, retention rules and access control. Too much for this ticket.
3. **Send the image once and store only text plus a marker.**

## Decision

Base64 in JSON (option 2 for transport), and the image is sent once and never stored (option 3).

- `ChatRequest` gets an optional `image: ImageInput` with `media_type` (`image/png`, `image/jpeg` or `image/webp`) and `data` (raw base64, no `data:` prefix).
- The server checks the bytes in a Pydantic `model_validator`, in this order, cheapest first:
  1. `data` is at most `4 * ceil(5 MB / 3)` characters (`max_length`), so a huge string is rejected before anything is decoded.
  2. `base64.b64decode(data, validate=True)` succeeds, so junk and a `data:` prefix are rejected.
  3. The decoded size is at most 5 MB.
  4. The first bytes (the magic number) match `media_type`, using `sniff_image_type()`. The declared type is never trusted on its own.
  Any failure is a `422` pointing at `image`, and the service is not called.
- The route maps `ImageInput` to an `ImageAttachment` dataclass in `services/chat.py`, so the service never imports the API schema.
- `ChatService` sends the question as one `HumanMessage`: plain text without an image, or a text block plus LangChain's standard `image` block with an image. `ChatOpenAI` turns that block into the OpenAI `image_url` data URL the gateway expects. The prompt's question slot became `MessagesPlaceholder("question")` so it can hold either.
- History stores the question plus a marker, for example `What does this error mean?\n[image: image/png]`, never the base64.
- Traces get `has_image` in their metadata. Logs never contain image data.

## Consequences

**Benefits**

- One JSON API: the request without `image` behaves exactly as before.
- Bad uploads stop at validation with a clear `422`, before any model call or database write.
- `chat_history` rows stay small, and later turns cost the same with or without an earlier screenshot. The history budget of ADR 0007 still only counts text.
- No screenshots in the database, so no retention or privacy questions for stored images yet.
- No new dependency: three `startswith` checks cover PNG, JPEG and WebP.

**Costs**

- **Follow-ups can't see the image.** "What was the error code in the screenshot?" on the next turn only sees the marker. The model can only use what it wrote in its first answer.
- **About 33% more bytes on the wire** than a multipart upload.
- **The magic-number check is shallow.** It proves the file starts like a PNG, JPEG or WebP, not that the whole file is a valid image. The model provider still parses it.
- **The 5 MB limit is a constant** in `api/chat.py`, not a setting.
- **The gateway model must support vision.** A text-only model in `LITELLM_MODEL` would fail on every request with an image.

**When to revisit**

- If users often ask follow-ups about a screenshot: store images in object storage with a retention period, and resend the latest one while the session is active (option 2 of what is stored).
- When the Streamlit UI (W3-02) sends images: check that the client strips the `data:` prefix or sends raw base64.
- When RAG arrives: decide in the prompt how a screenshot relates to the retrieved documents (see Lessons learned).
- If clients need larger images or other types: make the limit a setting, and consider a real image library for validation.

## Lessons learned

- LangChain callbacks see the OpenAI-shaped `image_url` dict in `message.content`, not the `image` block we built. Tests that read the prompt must assert on `message.content_blocks`, LangChain's standard view of the same message.
- The base64 length cap is not an exact size check. `4 * ceil(5 MB / 3)` characters can decode to 1 byte more than 5 MB, so the decoded-size check is still needed. `test_chat_rejects_an_image_one_byte_over_the_decoded_limit` is the only test that reaches it.
- Changing a typed argument without changing every caller is easy to miss: passing the API's `ImageInput` straight to the service gave a `500` (`'ImageInput' object has no attribute 'mime_type'`) on the first real image, while every text-only test stayed green.
- In the manual run (VPN error 809 screenshot), the model described the error and suggested checks even though the context was empty and the system prompt says to only point the user to the helpdesk then. The screenshot acts like context. The RAG prompt will need to say how to treat it.
