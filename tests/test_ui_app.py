"""The Streamlit page, driven headless with AppTest against DemoBackend.

Skipped when the ``ui`` extra (Streamlit) is not installed.
"""

from pathlib import Path

import pytest

pytest.importorskip("streamlit")
import streamlit as st
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "src/helpdesk_rag_chatbot/ui/app.py"


@pytest.fixture
def app() -> AppTest:
    st.cache_resource.clear()  # a fresh DemoBackend for every test
    return AppTest.from_file(str(APP), default_timeout=10).run()


def test_new_chat_shows_the_greeting_and_starter_questions(app: AppTest) -> None:
    assert not app.exception
    assert any("How can I help, Ana?" in m.value for m in app.markdown)
    assert len(app.chat_message) == 0


def test_sending_a_message_shows_question_answer_and_lists_the_chat(
    app: AppTest,
) -> None:
    app.chat_input[0].set_value("How do I reset my password?").run()

    assert [m.name for m in app.chat_message] == ["user", "assistant"]
    assert any(b.label.startswith("How do I reset") for b in app.sidebar.button)


def test_a_backend_error_is_shown_in_the_chat(app: AppTest) -> None:
    app.chat_input[0].set_value("simulate error").run()

    assert not app.exception
    assert "temporarily unavailable" in app.error[0].value


def test_switching_user_hides_the_other_users_chats(app: AppTest) -> None:
    app.chat_input[0].set_value("Ana's question").run()

    app.sidebar.selectbox[0].set_value("Ben (Sales)").run()

    assert not any(b.label == "Ana's question" for b in app.sidebar.button)
    assert len(app.chat_message) == 0
