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
