import asyncio

from langchain_core.language_models import FakeListChatModel
from langchain_core.messages import HumanMessage, SystemMessage

from helpdesk_rag_chatbot.services.chat import ChatService
from helpdesk_rag_chatbot.services.prompts import HELPDESK_PROMPT


def test_reply_returns_fake_model_response():
    service = ChatService(FakeListChatModel(responses=["Reset it from the portal."]))

    reply = asyncio.run(
        service.reply("How do I reset my password?", context="Use the portal.")
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
