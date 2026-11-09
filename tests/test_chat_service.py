import asyncio

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.language_models import FakeListChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from helpdesk_rag_chatbot.services.chat import ChatService
from helpdesk_rag_chatbot.services.prompts import HELPDESK_PROMPT

IDS = {"user_id": "u-1", "request_id": "r-1", "session_id": "s-1"}


def test_reply_returns_fake_model_response():
    service = ChatService(FakeListChatModel(responses=["Reset it from the portal."]))

    reply = asyncio.run(
        service.reply("How do I reset my password?", context="Use the portal.", **IDS)
    )

    assert reply == "Reset it from the portal."


def test_prompt_renders_system_then_human_with_question():
    messages = HELPDESK_PROMPT.format_messages(
        context="Use the portal.", question="How do I reset my password?"
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

    asyncio.run(service.reply("hi", **IDS))

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

    assert asyncio.run(service.reply("hi", **IDS)) == "ok"


class PromptRecorder(BaseCallbackHandler):
    """Capture the messages the chat model actually receives."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def on_chat_model_start(self, serialized, messages, **kwargs):
        self.prompts.extend(m.content for batch in messages for m in batch)


def test_reply_puts_context_into_the_prompt():
    recorder = PromptRecorder()
    service = ChatService(FakeListChatModel(responses=["ok"]), callbacks=[recorder])

    asyncio.run(service.reply("How do I reset it?", context="Use the portal.", **IDS))

    assert any("Use the portal." in p for p in recorder.prompts)
