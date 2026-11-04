# 0002. LLM client: ChatOpenAI against the LiteLLM proxy

- **Status:** Accepted
- **Date:** 2026-11-04

## Context

The app calls LLMs through the academy's LiteLLM proxy. The proxy speaks the OpenAI HTTP API and owns the provider side: provider keys, model aliases, fallbacks, budgets and rate limits.

The app still needs a LangChain chat model on its side to send requests to the proxy. The adapter `adapters/llm.py` (`get_chat_model(settings)`) builds that model, and it is the only module allowed to import the client library. We had to choose which client it uses.

## Options considered

1. **`ChatOpenAI` from `langchain-openai`.** A thin wrapper over the official `openai` SDK. It talks to any OpenAI-compatible endpoint through `base_url`.
2. **`ChatLiteLLM` from `langchain-litellm`.** A wrapper over the `litellm` SDK, which routes to 100+ providers from inside our process.

## Decision

We use `ChatOpenAI` with `base_url` pointed at the LiteLLM proxy, and we remove `langchain-litellm` from the dependencies.

The proxy already decides which provider answers. The client only needs to speak the proxy's protocol, so we choose the thinnest client that does that. With `ChatLiteLLM`, the in-process `litellm` SDK would run its own routing before the proxy routes the same request again. It still sends only one HTTP request, so the extra routing adds code and dependencies without changing the result.

`ChatOpenAI` is maintained by the LangChain team and is the best-tested path for what the app needs next: streaming, tool calling, `with_structured_output`, token usage and image inputs.

## Consequences

**Benefits**

- Fewer dependencies. `langchain-litellm` pulled in the full `litellm` SDK and about 40 transitive packages (boto3, huggingface-hub, tokenizers...).
- Switching models is a `.env` change (`LITELLM_MODEL`). Switching providers is a proxy config change. Neither touches our code.
- Switching the client later only touches `adapters/llm.py`, because the rest of the app sees `BaseChatModel`.

**Costs**

- Provider features that are not in the OpenAI schema must be passed through `extra_body`.

**Watch out**

- **Retries multiply.** If the proxy also retries or falls back, our client's `max_retries` stacks on top of it. Retry in one layer, or know the worst case: `timeout × (max_retries + 1)` on our side alone.
- `HttpUrl` normalizes `LITELLM_URL` (for example by adding a trailing slash). Check the URL the client actually calls.

**When to revisit**

- If we drop the proxy and call providers directly, `ChatLiteLLM` (or `init_chat_model`) becomes the better fit.

## Lessons learned

- Before adding a library, check which layer already owns that responsibility. Here the gateway owns provider routing, so the client should not do it again.
- An adapter keeps a wrong choice cheap: changing the client is a one-file change.
