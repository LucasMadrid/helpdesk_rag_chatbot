"""DemoBackend follows the API rules the UI relies on (ownership, titles, markers)."""

from uuid import uuid7

import pytest

from helpdesk_rag_chatbot.ui.backend import ApiError
from helpdesk_rag_chatbot.ui.demo_backend import DemoBackend


def test_first_message_creates_a_session_titled_with_it() -> None:
    backend, ana, chat = DemoBackend(), uuid7(), uuid7()

    backend.chat(ana, chat, "How do I reset my password?")

    [session] = backend.list_sessions(ana)
    assert (session.session_id, session.title) == (chat, "How do I reset my password?")


def test_messages_keep_an_image_marker_not_the_image() -> None:
    backend, ana, chat = DemoBackend(), uuid7(), uuid7()

    backend.chat(ana, chat, "What is this?", ("image/png", b"\x89PNG"))

    user, bot = backend.get_messages(chat, ana)
    assert (user.role, user.content) == ("user", "What is this?\n[image: image/png]")
    assert bot.role == "assistant"


def test_another_user_cannot_see_chat_in_or_delete_a_session() -> None:
    backend, ana, ben, chat = DemoBackend(), uuid7(), uuid7(), uuid7()
    backend.chat(ana, chat, "hi")

    assert backend.list_sessions(ben) == []
    for call in (
        lambda: backend.get_messages(chat, ben),
        lambda: backend.delete_session(chat, ben),
        lambda: backend.chat(ben, chat, "hi"),
    ):
        with pytest.raises(ApiError) as e:
            call()
        assert e.value.status == 404


def test_simulate_error_raises_a_503_with_a_request_id() -> None:
    with pytest.raises(ApiError) as e:
        DemoBackend().chat(uuid7(), uuid7(), "please simulate error")

    assert e.value.status == 503
    assert e.value.request_id
