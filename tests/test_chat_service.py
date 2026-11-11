import asyncio

import pytest
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.language_models import FakeListChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from helpdesk_rag_chatbot.services.chat import ChatService
from helpdesk_rag_chatbot.services.prompts import HELPDESK_PROMPT

IDS = {"user_id": "u-1", "request_id": "r-1", "session_id": "s-1"}


def test_reply_returns_fake_model_response():
    service = ChatService(FakeListChatModel(responses=["Reset it from the portal."]))

    reply = asyncio.run(
        service.reply(
            "How do I reset my password?",
            context="Use the portal.",
            **IDS,
            history=InMemoryChatMessageHistory(),
        )
    )

    assert reply == "Reset it from the portal."


def test_prompt_renders_system_then_human_with_question():
    messages = HELPDESK_PROMPT.format_messages(
        context="Use the portal.", history=[], question="How do I reset my password?"
    )

    assert len(messages) == 2
    assert isinstance(messages[0], SystemMessage)
    assert "Use the portal." in messages[0].content
    assert isinstance(messages[1], HumanMessage)
    assert messages[1].content == "How do I reset my password?"


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


def test_reply_works_without_callbacks():
    service = ChatService(FakeListChatModel(responses=["ok"]))

    reply = asyncio.run(
        service.reply("hi", history=InMemoryChatMessageHistory(), **IDS)
    )

    assert reply == "ok"


class PromptRecorder(BaseCallbackHandler):
    """Capture the messages the chat model actually receives."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def on_chat_model_start(self, serialized, messages, **kwargs):
        self.prompts.extend(m.content for batch in messages for m in batch)


def test_reply_puts_context_into_the_prompt():
    recorder = PromptRecorder()
    service = ChatService(FakeListChatModel(responses=["ok"]), callbacks=[recorder])

    asyncio.run(
        service.reply(
            "How do I reset it?",
            context="Use the portal.",
            history=InMemoryChatMessageHistory(),
            **IDS,
        )
    )

    assert any("Use the portal." in p for p in recorder.prompts)


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


class PromptSpy(BaseCallbackHandler):
    """Keep each prompt (list of messages) the chat model received."""

    def __init__(self) -> None:
        self.prompts: list[list] = []

    def on_chat_model_start(self, serialized, messages, **kwargs):
        self.prompts.append(messages[0])


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
    assert reply == "a2"
    # The dropped turn is still stored, and the new turn is saved after it.
    assert [m.content for m in history.messages] == ["q1", "a1", "q2", "a2"]
