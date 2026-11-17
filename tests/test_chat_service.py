import asyncio

import pytest
from fakes import PromptSpy
from langchain_core.callbacks import BaseCallbackHandler, CallbackManagerForRetrieverRun
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.documents import Document
from langchain_core.language_models import FakeListChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.retrievers import BaseRetriever
from pydantic import Field

from helpdesk_rag_chatbot.services.chat import ChatService, ImageAttachment
from helpdesk_rag_chatbot.services.prompts import HELPDESK_PROMPT
from helpdesk_rag_chatbot.services.rag import Source, context_tokens, format_context

IDS = {"user_id": "u-1", "request_id": "r-1", "session_id": "s-1"}

PORTAL_DOC = Document(
    page_content="Use the portal.",
    metadata={
        "title": "Password Reset",
        "doc_id": "it-password-reset",
        "version": "2.0",
    },
)


VPN_DOC = Document(
    page_content="Install the VPN client. " * 20,
    metadata={"title": "VPN Setup", "doc_id": "it-vpn-setup", "version": "1.0"},
)


class FakeRetriever(BaseRetriever):
    """Return the same chunks for every query and record each query."""

    docs: list[Document]
    queries: list[str] = Field(default_factory=list)

    def _get_relevant_documents(
        self, query: str, *, run_manager: CallbackManagerForRetrieverRun
    ) -> list[Document]:
        self.queries.append(query)
        return self.docs


def test_reply_returns_fake_model_response():
    service = ChatService(FakeListChatModel(responses=["Reset it from the portal."]))

    reply = asyncio.run(
        service.reply(
            "How do I reset my password?",
            **IDS,
            history=InMemoryChatMessageHistory(),
        )
    )

    assert reply.answer == "Reset it from the portal."
    assert reply.sources == []


def test_prompt_renders_system_then_human_with_question():
    messages = HELPDESK_PROMPT.format_messages(
        context="Use the portal.",
        history=[],
        question=[HumanMessage(content="How do I reset my password?")],
    )

    assert len(messages) == 2
    assert isinstance(messages[0], SystemMessage)
    assert "Use the portal." in messages[0].content
    assert isinstance(messages[1], HumanMessage)
    assert messages[1].content == "How do I reset my password?"


def test_prompt_needs_only_context_history_and_question():
    # A stray {placeholder} in the prompt text would become a required input
    # and make every reply fail with a missing-variable error.
    assert set(HELPDESK_PROMPT.input_variables) == {"context", "history", "question"}


def test_prompt_tells_the_model_how_to_cite():
    system = HELPDESK_PROMPT.format_messages(
        context="[1] Password Reset (it-password-reset v2.0)\nUse the portal.",
        history=[],
        question=[HumanMessage(content="How do I reset my password?")],
    )[0].content

    # cited_sources parses [n] markers, so the prompt must ask for them.
    assert "Put [n] right after each sentence that uses source n" in system
    assert system.rstrip().endswith("Use the portal.")


class RecordingHandler(BaseCallbackHandler):
    """Capture the run name and metadata LangChain passes to callbacks."""

    def __init__(self) -> None:
        self.names: list[str] = []
        self.metadata: list[dict] = []

    def on_chain_start(self, serialized, inputs, *, metadata=None, name=None, **kwargs):
        self.names.append(name)
        self.metadata.append(metadata or {})


def test_reply_sends_run_name_and_ids_to_callbacks():
    handler = RecordingHandler()
    service = ChatService(FakeListChatModel(responses=["ok"]), callbacks=[handler])

    asyncio.run(service.reply("hi", history=InMemoryChatMessageHistory(), **IDS))

    assert "chat-response" in handler.names
    assert any(
        m.get("langfuse_tags") == ["chat"]
        and m.get("langfuse_user_id") == "u-1"
        and m.get("langfuse_session_id") == "s-1"
        and m.get("request_id") == "r-1"
        and m.get("history_messages_total") == 0
        and m.get("history_messages_sent") == 0
        for m in handler.metadata
    )


def test_reply_records_retrieval_in_trace_metadata():
    handler = RecordingHandler()
    used = context_tokens(format_context([PORTAL_DOC]))
    service = ChatService(
        FakeListChatModel(responses=["ok"]),
        callbacks=[handler],
        # VPN_DOC is retrieved but does not fit next to PORTAL_DOC.
        retriever=FakeRetriever(docs=[PORTAL_DOC, VPN_DOC]),
        history_max_tokens=2000,
        context_max_tokens=used + 100,
    )

    asyncio.run(service.reply("hi", history=InMemoryChatMessageHistory(), **IDS))

    assert any(
        m.get("chunks_retrieved") == 2
        and m.get("chunks_sent") == 1
        and m.get("context_tokens") == used
        and m.get("history_budget") == 100
        for m in handler.metadata
    )


def test_reply_works_without_callbacks():
    service = ChatService(FakeListChatModel(responses=["ok"]))

    reply = asyncio.run(
        service.reply("hi", history=InMemoryChatMessageHistory(), **IDS)
    )

    assert reply.answer == "ok"


class PromptRecorder(BaseCallbackHandler):
    """Capture the messages the chat model actually receives."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def on_chat_model_start(self, serialized, messages, **kwargs):
        self.prompts.extend(m.content for batch in messages for m in batch)


def test_reply_puts_retrieved_chunks_into_the_prompt():
    recorder = PromptRecorder()
    service = ChatService(
        FakeListChatModel(responses=["ok"]),
        callbacks=[recorder],
        retriever=FakeRetriever(docs=[PORTAL_DOC]),
    )

    asyncio.run(
        service.reply("How do I reset it?", history=InMemoryChatMessageHistory(), **IDS)
    )

    assert any(
        "[1] Password Reset (it-password-reset v2.0)\nUse the portal." in p
        for p in recorder.prompts
    )


def test_reply_returns_the_sources_the_answer_cites():
    service = ChatService(
        FakeListChatModel(responses=["Use the portal [1]."]),
        retriever=FakeRetriever(docs=[PORTAL_DOC]),
    )

    reply = asyncio.run(
        service.reply("How do I reset it?", history=InMemoryChatMessageHistory(), **IDS)
    )

    assert reply.answer == "Use the portal [1]."
    assert reply.sources == [
        Source(
            doc_id="it-password-reset",
            title="Password Reset",
            version="2.0",
            numbers=(1,),
        )
    ]


def test_reply_searches_with_the_users_question():
    retriever = FakeRetriever(docs=[PORTAL_DOC])
    service = ChatService(FakeListChatModel(responses=["ok"]), retriever=retriever)

    asyncio.run(
        service.reply(
            "How do I reset my password?", history=InMemoryChatMessageHistory(), **IDS
        )
    )

    assert retriever.queries == ["How do I reset my password?"]


def test_reply_returns_only_cited_sources():
    sso_doc = Document(
        page_content="Sign in with SSO.",
        metadata={
            "title": "Single Sign-On",
            "doc_id": "it-sso-login",
            "version": "1.1",
        },
    )
    service = ChatService(
        FakeListChatModel(responses=["Sign in with SSO [2]."]),
        retriever=FakeRetriever(docs=[PORTAL_DOC, sso_doc, VPN_DOC]),
    )

    reply = asyncio.run(
        service.reply("How do I sign in?", history=InMemoryChatMessageHistory(), **IDS)
    )

    # All 3 chunks were sent, but only chunk 2 is cited.
    assert reply.sources == [
        Source(
            doc_id="it-sso-login", title="Single Sign-On", version="1.1", numbers=(2,)
        )
    ]


def test_reply_drops_chunks_that_do_not_fit_the_context_budget():
    recorder = PromptRecorder()
    service = ChatService(
        FakeListChatModel(responses=["ok"]),
        callbacks=[recorder],
        retriever=FakeRetriever(docs=[PORTAL_DOC, VPN_DOC]),
        # Room for the first chunk only.
        context_max_tokens=context_tokens(format_context([PORTAL_DOC])),
    )

    asyncio.run(
        service.reply("How do I reset it?", history=InMemoryChatMessageHistory(), **IDS)
    )

    system_prompt = recorder.prompts[0]
    assert "[1] Password Reset (it-password-reset v2.0)" in system_prompt
    assert "it-vpn-setup" not in system_prompt


def test_reply_ignores_citations_of_chunks_that_were_not_sent():
    service = ChatService(
        FakeListChatModel(responses=["See [1] and [2]."]),
        retriever=FakeRetriever(docs=[PORTAL_DOC, VPN_DOC]),
        context_max_tokens=context_tokens(format_context([PORTAL_DOC])),
    )

    reply = asyncio.run(
        service.reply("How do I reset it?", history=InMemoryChatMessageHistory(), **IDS)
    )

    # [2] was retrieved but dropped by the budget, so it is not a source.
    assert [s.doc_id for s in reply.sources] == ["it-password-reset"]


def test_reply_gives_history_only_the_budget_left_after_chunks():
    spy = PromptSpy()
    history = InMemoryChatMessageHistory()
    history.add_user_message("q1")
    history.add_ai_message("a1")
    # The chunk uses all but 1 token of the shared budget, so no stored turn
    # fits, even though history_max_tokens alone would allow them.
    used = context_tokens(format_context([PORTAL_DOC]))
    service = ChatService(
        FakeListChatModel(responses=["a2"]),
        callbacks=[spy],
        retriever=FakeRetriever(docs=[PORTAL_DOC]),
        history_max_tokens=2000,
        context_max_tokens=used + 1,
    )

    asyncio.run(service.reply("q2", history=history, **IDS))

    # [1:] skips the system message. Only the new question is left.
    assert [m.content for m in spy.prompts[0][1:]] == ["q2"]


def test_reply_saves_question_and_answer_to_history():
    history = InMemoryChatMessageHistory()
    service = ChatService(FakeListChatModel(responses=["a1"]))

    asyncio.run(service.reply("q1", history=history, **IDS))

    assert [(m.type, m.content) for m in history.messages] == [
        ("human", "q1"),
        ("ai", "a1"),
    ]


class FailingModel(FakeListChatModel):
    def _call(self, *args, **kwargs):
        raise RuntimeError("model down")


def test_reply_does_not_save_when_the_model_fails():
    history = InMemoryChatMessageHistory()
    service = ChatService(FailingModel(responses=["unused"]))

    with pytest.raises(RuntimeError):
        asyncio.run(service.reply("q1", history=history, **IDS))

    assert history.messages == []


def test_second_reply_sends_first_turn_to_the_model():
    spy = PromptSpy()
    history = InMemoryChatMessageHistory()
    service = ChatService(FakeListChatModel(responses=["a1", "a2"]), callbacks=[spy])

    asyncio.run(service.reply("q1", history=history, **IDS))
    asyncio.run(service.reply("q2", history=history, **IDS))

    # [1:] skips the system message.
    assert [m.content for m in spy.prompts[1][1:]] == ["q1", "a1", "q2"]
    assert [m.type for m in history.messages] == ["human", "ai", "human", "ai"]


def test_reply_sends_only_the_newest_turns_that_fit():
    spy = PromptSpy()
    history = InMemoryChatMessageHistory()
    for i in range(1, 6):
        history.add_user_message(f"q{i}")
        history.add_ai_message(f"a{i}")
    # Each stored message counts as 5 or 6 tokens (approximate counter), so a
    # budget of 25 has room for the two newest turns (22) but not a third (33).
    service = ChatService(
        FakeListChatModel(responses=["a6"]), history_max_tokens=25, callbacks=[spy]
    )

    asyncio.run(service.reply("q6", history=history, **IDS))

    # [1:] skips the system message. The new question is always sent.
    assert [m.content for m in spy.prompts[0][1:]] == ["q4", "a4", "q5", "a5", "q6"]
    # Trimming only affects the prompt: nothing is removed from the stored history.
    assert len(history.messages) == 12


def test_reply_never_starts_the_history_with_an_answer():
    spy = PromptSpy()
    history = InMemoryChatMessageHistory()
    for i in range(1, 6):
        history.add_user_message(f"q{i}")
        history.add_ai_message(f"a{i}")
    # A budget of 17 fits a4, q5 and a5, but a4's question was cut, so
    # start_on="human" drops a4 as well.
    service = ChatService(
        FakeListChatModel(responses=["a6"]), history_max_tokens=17, callbacks=[spy]
    )

    asyncio.run(service.reply("q6", history=history, **IDS))

    # [1:] skips the system message.
    assert [m.content for m in spy.prompts[0][1:]] == ["q5", "a5", "q6"]


def test_reply_still_sends_the_question_when_no_turn_fits():
    spy = PromptSpy()
    history = InMemoryChatMessageHistory()
    history.add_user_message("q1")
    history.add_ai_message("a1")
    # A budget of 1 token is smaller than any single stored message, so the
    # whole history is dropped from the prompt.
    service = ChatService(
        FakeListChatModel(responses=["a2"]), history_max_tokens=1, callbacks=[spy]
    )

    reply = asyncio.run(service.reply("q2", history=history, **IDS))

    # [1:] skips the system message. Only the new question is left.
    assert [m.content for m in spy.prompts[0][1:]] == ["q2"]
    assert reply.answer == "a2"
    # The dropped turn is still stored, and the new turn is saved after it.
    assert [m.content for m in history.messages] == ["q1", "a1", "q2", "a2"]


def test_reply_sends_the_image_to_the_model():
    spy = PromptSpy()
    service = ChatService(FakeListChatModel(responses=["ok"]), callbacks=[spy])
    image = ImageAttachment(mime_type="image/png", data="iVBORw0KGgo=")

    asyncio.run(
        service.reply(
            "What is this error?",
            history=InMemoryChatMessageHistory(),
            image=image,
            **IDS,
        )
    )

    block = spy.prompts[0][-1].content_blocks[1]
    assert (block["type"], block["base64"]) == ("image", "iVBORw0KGgo=")


def test_reply_saves_a_marker_instead_of_the_image():
    history = InMemoryChatMessageHistory()
    service = ChatService(FakeListChatModel(responses=["ok"]))
    image = ImageAttachment(mime_type="image/png", data="iVBORw0KGgo=")

    asyncio.run(
        service.reply("What is this error?", history=history, image=image, **IDS)
    )

    # The stored question is plain text with a marker: no base64 in the database.
    assert [m.content for m in history.messages] == [
        "What is this error?\n[image: image/png]",
        "ok",
    ]


@pytest.mark.parametrize(
    ("history_max", "context_max", "used", "expected"),
    [
        (2000, 3000, 500, 2000),  # plenty of room: history keeps its own cap
        (2000, 3000, 1500, 1500),  # docs leave less than the cap
        (2000, 3000, 3200, 0),  # docs went over: no history, not negative
    ],
)
def test_history_budget(history_max, context_max, used, expected):
    assert ChatService._history_budget(history_max, context_max, used) == expected
