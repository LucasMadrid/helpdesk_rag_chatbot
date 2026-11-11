# 0007. Trim the history sent to the model to a token budget

- **Status:** Accepted
- **Date:** 2026-11-11

## Context

Since W2-02, `ChatService.reply` loads every stored message of the session and sends all of them to the model before the new question (ADR 0005). ADR 0005 named the cost: histories grow without limit. A chat model is stateless, so every turn resends the whole conversation. Each call gets slower and more expensive, and a chat's total cost grows with the square of its length. A long enough chat would also go past the model's context window, and the call would fail.

W2-04 has to put a ceiling on what each call sends.

Constraints:

- The stored history must stay complete. A future UI may show the whole conversation, and a later change (a bigger budget, a summary of old turns) may want it back.
- `ChatService` should keep knowing only `BaseChatMessageHistory` and a chat model (ADR 0005), so the unit tests still need no database and no tokenizer.
- The models behind the gateway can change (ADR 0002), so the count should not depend on one model's tokenizer.
- Once retrieval arrives, history will share the context window with the retrieved documents.

## Options considered

1. **Keep the last N messages** (a fixed count). Simple, but a count says nothing about size: five short turns and five 1,000-character answers cost very different amounts.
2. **Delete old messages from the database.** Saves storage too, but loses the conversation for good and breaks the "stored history stays complete" constraint.
3. **Summarise old turns into one message** (a summary memory). Keeps old facts, but every trim needs an extra LLM call, adds latency and cost, and adds a summary that can be wrong. Too much for this ticket.
4. **Trim the prompt to a token budget with `trim_messages`** (`langchain_core.messages`), and leave the stored history alone.

For the token count:

- **The model's tokenizer** (`token_counter=chat_model`, or `tiktoken`). Exact, but it ties the count to one model family and can need a download at startup or in tests.
- **`token_counter="approximate"`** (`count_tokens_approximately`): about 4 characters per token plus 3 tokens per message. No dependencies, the same for any model.

## Decision

We choose option 4, with the approximate counter.

- New setting `history_max_tokens` (`HISTORY_MAX_TOKENS`, default `2000`, `gt=0`). `0` or a negative value fails validation, so the app does not start. `main.py` passes it into `ChatService`.
- `ChatService.reply` loads the messages as before (`past`) and runs `trim_messages(past, max_tokens=..., token_counter="approximate", strategy="last", start_on="human")`. Only the result (`kept`) goes to the chain as `history`.
  - `strategy="last"`: keep the newest messages and drop the oldest, because a follow-up usually refers to the last few turns.
  - `start_on="human"`: the kept history never starts with an answer whose question was cut.
- The system prompt and the new question are always sent and are not counted against the budget.
- Every trace gets `history_messages_total` (`len(past)`) and `history_messages_sent` (`len(kept)`) in its metadata, so Langfuse shows when and how much was trimmed.
- Saving does not change: the new question and answer are still added after the model call, and nothing is deleted.

## Consequences

**Benefits**

- Each call has a ceiling on history tokens, so long chats cost at most about `HISTORY_MAX_TOKENS` of history per turn instead of the whole conversation.
- The budget is a cap, not a fixed cost: a chat shorter than the budget sends exactly what it sent before.
- The full conversation stays in `app-db`.
- No new dependency and no tokenizer download; unit tests use `InMemoryChatMessageHistory` and a fake model as before.
- Trimming is visible per request in Langfuse.

**Costs**

- **The model forgets old turns.** A fact from early in the chat ("my laptop is a Dell XPS") is gone once its turn falls outside the budget, and the model answers as if it was never said.
- **Messages are kept whole,** so one long answer can push out several turns at once. In the demo at a budget of 400, one ~290-token printer answer left room for only one earlier turn on the next call.
- **The count is approximate.** The real prompt can be a little over or under the budget, depending on the language and the model's tokenizer.
- **A budget smaller than one message sends no history at all.** At 60 tokens every stored answer was too big, so from the second question on the model got only the system prompt and the question.

**When to revisit**

- If users need facts from early in long chats: summarise the dropped turns into one short message (option 3) instead of raising the budget a lot.
- When retrieval is added: decide how the context window is split between history and documents, and check that the two budgets together fit the model.
- If the gateway moves to models with very different tokenizers, or the budget needs to be exact: switch `token_counter` to the model's own counter.

## Lessons learned

- Trimming is invisible from the answers alone at the default budget. With `HISTORY_MAX_TOKENS=2000`, `scripts/forgetting_demo.py` (one fact, four unrelated questions, then "What laptop do I have?") built about 700 tokens of history, so all 10 messages were sent and the model remembered the Dell XPS.
- At 400, the last call sent 4 of 10 messages (`history_messages_sent = 4`, `history_messages_total = 10` in Langfuse) and the model no longer knew the laptop. The third answer still said "restart your laptop", so the fact was there until older turns started falling out. The whole last call used 444 tokens ($0.000211).
- At 60, every stored answer was larger than the budget, so no history was sent at all. That shows the cap works but not the useful part (keep the newest, drop the oldest). A demo needs a budget between one turn and the whole chat.
- The approximate counter runs about 18% high on our English helpdesk text. For that last call (gpt-5.4-nano), it counted 388 tokens for the whole prompt; Langfuse reported 328 input tokens (116 output, 444 total), and `tiktoken` with o200k_base gave 319. For the history alone it was 192 against 168. Too high is the safe side for a cap: a 2000 budget keeps about 1,700 real tokens. For Chinese, Japanese or Korean text (about 1 to 1.5 characters per token), it would count 2 to 3 times too low instead, and the cap would no longer be safe.
- The real tokenizer needs the network the first time: `tiktoken` downloads its encoding file and failed in a sandbox that blocked the host.
- `uvicorn --reload` watches `.py` files, not `.env`. After changing `HISTORY_MAX_TOKENS`, restart the server, or it keeps the old value.
