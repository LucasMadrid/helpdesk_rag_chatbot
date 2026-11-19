# 0011. Relevance threshold for abstaining

- **Status:** Accepted
- **Date:** 2026-11-19

## Context

Top-k always returns k chunks, relevant or not (ADR 0010). For "What is on the canteen menu on Friday?" all 4 off-topic chunks reached the model. Only prompt rule 3 stopped it from citing them. A confident wrong answer is worse than no answer, especially for HR policy, so we want code, not only the prompt, to keep weak evidence away from the model.

Questions:

- **Where is the cut made?** In the retriever, or in `ChatService` after retrieval.
- **What score is compared, and in which unit?**
- **What happens when no chunk passes?** A fixed reply, or the model with no sources.
- **Which value?**

Constraints:

- `ChatService` takes a `BaseRetriever` port (ADR 0010) and should not learn about scores.
- Unit tests run without network. `InMemoryVectorStore` has no relevance-score function: `similarity_search_with_relevance_scores` raises `NotImplementedError`.
- A greeting ("Hi there!") or a thank-you scores as low as an off-topic question.

## Options considered

Where to cut:

1. **In the retriever:** `as_retriever(search_type="similarity_score_threshold")` with `score_threshold` in `search_kwargs`. Each chunk under the threshold is dropped, so a weak 4th chunk goes too. The service still gets a list of documents, sometimes empty.
2. **In the service**, on scores returned by the store. Needs a new port that returns `(Document, score)` pairs, and the service would depend on the store's score unit.

What to do with no chunk left:

1. **Fixed reply without calling the model.** Deterministic and free, but "Hi there!" and "thanks" would get "I don't know".
2. **Call the model with sources `(none)`.** The model words the abstain and still handles greetings. It cannot cite anything, because there is nothing to cite.

## Decision

We cut in the retriever and call the model with sources `(none)`.

- `get_retriever(store, k, search_filter, min_score=None)`. `None` keeps plain `"similarity"` search. A value switches to `"similarity_score_threshold"` and adds `score_threshold` to `search_kwargs`, next to `k` and `filter`.
- New setting `retrieval_min_score` (`RETRIEVAL_MIN_SCORE`, default **0.65**, `ge=0`, `le=1`). `0.0` turns the threshold off. It must be a float: the retriever rejects an int `score_threshold`.
- The threshold is in **relevance units**, not raw cosine. `PineconeVectorStore._cosine_relevance_score_fn` maps Pinecone's cosine (-1 to 1) to `(cosine + 1) / 2` (0 to 1), and that is what `score_threshold` is compared with.
- `prompts.py` gets `NO_SOURCES = "(none)"`. When no chunk is sent, `ChatService.reply` puts `NO_SOURCES` into `{context}` instead of `""`.
- Prompt rule 3: if the sources are `(none)` or none answers the question, say the documents don't cover it and cite nothing. HR topics go to People Operations (hr@example.com, ext. 4470), everything else to the IT Service Desk (servicedesk@example.com, ext. 4357).
- With no chunk sent, `cited_sources` gets `[]` and returns `[]`, so the response has no sources whatever the model writes. Code guarantees "no weak citation"; the prompt only decides the wording.
- The lifespan passes `resolved.retrieval_min_score` to `get_retriever`.
- Tests use `ScoredInMemoryVectorStore` (`tests/fakes.py`), an `InMemoryVectorStore` that overrides `_select_relevance_score_fn` with Pinecone's `(score + 1) / 2`. A query with the same text as a chunk scores 1.0, so `min_score=0.99` gives a deterministic "relevant" and "irrelevant".

### How 0.65 was chosen

Top-1 chunk per question, `recursive` namespace, current versions only, 2026-11-18. `raw` = `similarity_search_with_score`, `rel` = `similarity_search_with_relevance_scores`.

| Group | raw | rel | Question → top doc |
|---|---|---|---|
| answerable | 0.706 | 0.853 | My VPN says error 809 → it-vpn-guide |
| answerable | 0.676 | 0.838 | How many days a year can I work from another country? → hr-remote-work-policy |
| answerable | 0.645 | 0.823 | When does a new starter's laptop arrive? → it-laptop-request |
| answerable | 0.613 | 0.807 | I clicked a phishing link. Who do I call? → it-security-incident-reporting |
| answerable | 0.604 | 0.802 | How many vacation days do I have? → hr-leave-policy |
| near-miss | 0.599 | 0.800 | How do I install SecureLink on Linux? → it-vpn-guide |
| answerable | 0.567 | 0.783 | How much is the home-office allowance? → hr-remote-work-policy |
| answerable | 0.562 | 0.781 | How do I reset my password? → it-password-mfa-policy |
| unanswerable | 0.539 | 0.770 | Do Corvane employees get share options? → hr-working-hours-overtime |
| answerable | 0.537 | 0.769 | Can I still get my MFA code by SMS? → it-password-mfa-policy |
| answerable | 0.527 | 0.763 | How long do I have to submit expenses? → hr-expense-travel-policy |
| unanswerable | 0.442 | 0.721 | Where can I park my car at the Dublin office? → hr-benefits-payroll |
| near-miss | 0.409 | 0.705 | How many weeks of parental leave do I get? → hr-leave-policy |
| answerable | 0.388 | 0.694 | Teams shows error caa20002 → it-known-errors-faq |
| unanswerable | 0.354 | 0.677 | What is the guest Wi-Fi password? → it-vpn-guide |
| **threshold** | | **0.650** | |
| off-topic | 0.257 | 0.629 | What is on the canteen menu on Friday? → hr-offboarding-checklist |
| greeting | 0.238 | 0.619 | Hi there! → hr-onboarding-guide |
| off-topic | 0.156 | 0.578 | Who won the football world cup in 2022? → hr-leave-policy |
| off-topic | 0.125 | 0.562 | Write a poem about the sea → it-password-mfa-policy |

- The lowest answerable question scores 0.694 and the highest off-topic one 0.629. 0.65 sits in that gap, on the low side: a missed answer costs more than an off-topic chunk that prompt rule 3 still catches.
- The 3 unanswerable questions (0.677 to 0.770) score like answerable ones. No threshold can separate them; prompt rule 3 has to.

## Consequences

**Benefits**

- Off-topic questions send 0 chunks, so they cannot produce a citation, and the prompt is smaller.
- Weak chunks among the top k are dropped too, not only all-or-nothing.
- Greetings and thanks still get a normal reply.
- `ChatService` is unchanged apart from the `(none)` fallback: the threshold lives where the scores are.

**Costs**

- **The gap is small.** 0.065 between the lowest answerable and the highest off-topic question, measured on 19 questions. A new document, embedding model or splitter changes every score.
- **Short, code-heavy questions score low.** "Teams shows error caa20002" is the lowest answerable question (0.694). Raising the threshold would hit these first.
- **In-domain unanswerable questions still pass.** Parking, guest Wi-Fi and share options reach the model with chunks; only the prompt keeps it from inventing an answer.
- **The scores are not in the trace.** `chunks_retrieved` shows how many passed, not how close they were to the threshold.
- **The unit depends on the store.** Another vector store may map distance to relevance differently, so the value must be measured again after a swap.

**When to revisit**

- In the W6 evals: measure the abstain rate on unanswerable questions and the miss rate on answerable ones, then tune `RETRIEVAL_MIN_SCORE`.
- After changing the embedding model, the splitter (W7) or the vector store: run the measurement script again.
- If tuning needs per-request scores, log them in the trace metadata.

## Lessons learned

- The W5-02 canteen scores (0.277 to 0.287) were raw cosine. In the unit the retriever compares, the same chunks score about 0.64. A threshold of 0.4 picked from the raw numbers would have let every off-topic chunk through.
- `InMemoryVectorStore` raises `NotImplementedError` for relevance scores, so a score-threshold retriever can't be tested on it without a subclass.
- Live run (step 7): _fill in: canteen chunks retrieved, "Hi there!" reply, working-abroad source._
