"""Streamlit chat UI for the helpdesk. It only talks to a ChatBackend (backend.py).

Run from the repo root (so Streamlit finds .streamlit/config.toml):
    uv run --extra ui streamlit run src/helpdesk_rag_chatbot/ui/app.py

Look: .streamlit/config.toml. Words, starter prompts, demo users: ui.toml.
It calls the API at HELPDESK_API_URL (default http://localhost:8000). Set
HELPDESK_DEMO=1 to use DemoBackend (in memory) instead, with no API running.
"""

import os
import time
import tomllib
from pathlib import Path
from uuid import UUID, uuid7

import streamlit as st

from helpdesk_rag_chatbot.ui.api_client import HelpdeskClient
from helpdesk_rag_chatbot.ui.backend import ApiError, ChatBackend
from helpdesk_rag_chatbot.ui.demo_backend import DemoBackend
from helpdesk_rag_chatbot.ui.sidebar import SEARCH_MIN_CHATS, ago, current_first, short

UI_TOML = Path(__file__).resolve().parents[3] / "ui.toml"
IMAGE_MARKER = "\n[image: "  # what history stores instead of an image (ADR 0008)
USER_AVATAR = ":material/person:"
BOT_AVATAR = ":material/support_agent:"


@st.cache_data
def load_ui_config() -> dict:
    with UI_TOML.open("rb") as f:
        return tomllib.load(f)


cfg = load_ui_config()
st.set_page_config(
    page_title=cfg["assistant_name"], page_icon=":material/support_agent:"
)
st.logo(
    ":material/support_agent:", size="large"
)  # also shown when the sidebar is closed


@st.cache_resource
def get_backend() -> ChatBackend:
    """One backend for the whole Streamlit server: the API, or demo data."""
    if os.getenv("HELPDESK_DEMO") == "1":
        return DemoBackend()
    return HelpdeskClient(os.getenv("HELPDESK_API_URL", "http://localhost:8000"))


client = get_backend()
DEMO = isinstance(client, DemoBackend)

# ---- state -----------------------------------------------------------------
# session_id: the chat on screen. A new chat gets a fresh UUID7 on the client;
# the first POST /chat with it creates the session on the server (ADR 0006).
state = st.session_state
state.setdefault("user", cfg["demo_users"][0])
state.setdefault("session_id", uuid7())
state.setdefault("messages", [])  # dicts: role, content, request_id?, image?, error?
state.setdefault("pending", None)  # a starter prompt that was clicked


def start_new_chat() -> None:
    state.session_id = uuid7()
    state.messages = []


def switch_user() -> None:
    """Sign in as the user picked in the sidebar, on a fresh chat."""
    picked = state.user_menu
    if picked == state.user["name"]:
        return
    state.user = next(u for u in cfg["demo_users"] if u["name"] == picked)
    start_new_chat()


def open_chat(session_id: UUID) -> None:
    try:
        history = client.get_messages(session_id, UUID(state.user["id"]))
    except ApiError as e:
        st.toast(friendly_error(e), icon=":material/error:")
        return
    state.session_id = session_id
    state.messages = [{"role": m.role, "content": m.content} for m in history]


def friendly_error(e: ApiError) -> str:
    if e.status is None:
        return "Can't reach the helpdesk service. Is the API running?"
    if e.status == 404:
        return "This chat doesn't exist any more."
    if e.status == 422:
        return f"That message was rejected: {e.detail}"
    return e.detail  # 503s already carry a message meant for users


@st.dialog("Delete this chat?")
def confirm_delete(session_id: UUID, title: str) -> None:
    st.write(f"**{title}** and all its messages will be deleted. This can't be undone.")
    left, right = st.columns(2)
    if left.button("Cancel", width="stretch"):
        st.rerun()
    if right.button("Delete", type="primary", width="stretch"):
        try:
            client.delete_session(session_id, UUID(state.user["id"]))
        except ApiError as e:
            st.error(friendly_error(e))
            return
        start_new_chat()
        st.rerun()


# ---- sidebar: new chat, recent chats grouped by day, who --------------------
# The only CSS: Streamlit can't pin a footer to the sidebar bottom natively, so the
# chat list gets "viewport height minus the rest of the sidebar". If the profile
# sits too high or the sidebar scrolls, tune CHAT_LIST_OFFSET_REM.
CHAT_LIST_OFFSET_REM = 17
CHAT_LIST_CSS = (
    ".st-key-chatlist { "
    f"height: calc(100vh - {CHAT_LIST_OFFSET_REM}rem) !important; "
    "overflow-y: auto !important; }"
    # The open chat: its whole row (title, age, menu) gets a soft accent fill.
    ".st-key-current-chat { "
    "background-color: rgba(110, 104, 240, 0.18); border-radius: 0.75rem; }"
)
with st.sidebar:
    st.html(f"<style>{CHAT_LIST_CSS}</style>")
    st.markdown(f"#### {cfg['assistant_name']}")
    if DEMO:
        st.badge(
            "Demo data, not connected to the API",
            icon=":material/science:",
            color="gray",
        )
    st.button(
        "New chat",
        icon=":material/edit_square:",
        type="primary",
        width="stretch",
        on_click=start_new_chat,
    )

    try:
        sessions = client.list_sessions(UUID(state.user["id"]))
    except ApiError as e:
        sessions = []
        st.caption(f":material/cloud_off: {friendly_error(e)}")

    shown = sessions
    if len(sessions) > SEARCH_MIN_CHATS:
        query = st.text_input(
            "Search chats",
            placeholder="Search chats",
            icon=":material/search:",
            label_visibility="collapsed",
            key="chat_search",
        )
        shown = [s for s in sessions if query.strip().lower() in s.title.lower()]
        if not shown:
            st.caption("No chats match.")

    # The list has a fixed height (see CHAT_LIST_CSS) and scrolls inside it, so the
    # profile below it stays at the bottom whether there are 3 chats or 50.
    with st.container(key="chatlist"):
        for day, group in current_first(shown, state.session_id):
            st.caption(day.upper())
            for s in group:
                current = s.session_id == state.session_id
                # Columns, not a horizontal container: that one wraps the age and
                # the menu onto a second line when the full-width button fills it.
                row = st.container(key="current-chat" if current else None)
                title_col, age_col, menu_col = row.columns(
                    [6, 2, 1.3], vertical_alignment="center", gap="xsmall"
                )
                title = short(s.title, 20)
                title_col.button(
                    f"**{title}**" if current else title,
                    key=f"s-{s.session_id}",
                    icon=":material/chat_bubble:",
                    type="tertiary",
                    width="stretch",
                    help=s.title,
                    on_click=open_chat,
                    args=(s.session_id,),
                )
                age_col.caption(ago(s.updated_at))
                choice = menu_col.menu_button(
                    ":material/more_horiz:",
                    ["Delete"],
                    key=f"m-{s.session_id}",
                    type="tertiary",
                    help="Chat options",
                )
                if choice == "Delete":
                    confirm_delete(s.session_id, s.title)

    st.menu_button(
        f":material/account_circle: {state.user['name']}",
        [u["name"] for u in cfg["demo_users"]],
        key="user_menu",
        width="stretch",
        on_click=switch_user,
        format_func=lambda n: f"✓ {n}" if n == state.user["name"] else n,
    )


# ---- main: one chat ---------------------------------------------------------
def render(msg: dict) -> None:
    avatar = USER_AVATAR if msg["role"] == "user" else BOT_AVATAR
    with st.chat_message(msg["role"], avatar=avatar):
        text, has_marker, _ = msg["content"].partition(IMAGE_MARKER)
        if msg.get("error"):
            st.error(text, icon=":material/error:")
        else:
            st.markdown(text)
        if msg.get("image"):
            st.image(msg["image"], width=200, alt="Attached screenshot")
        elif has_marker:
            st.caption(":material/image: Screenshot attached (not stored)")
        if msg["role"] == "assistant":
            answer_footer(msg)


def answer_footer(msg: dict) -> None:
    """Answer time and request ID, kept small: the ID is only for bug reports."""
    seconds, request_id = msg.get("seconds"), msg.get("request_id")
    if seconds is None and not request_id:
        return  # e.g. an answer reopened from history
    footer = st.container(horizontal=True, vertical_alignment="center", gap="small")
    if seconds is not None:
        footer.caption(f":material/schedule: {seconds:.1f} s")
    if request_id:
        with footer.popover(
            "Ref",
            icon=":material/tag:",
            type="tertiary",
            key=f"ref-{request_id}",
            help="The request ID, for reporting a problem",
        ):
            st.caption("Quote this ID if you report a problem.")
            st.code(request_id, language=None)


if not state.messages:
    st.space("large")
    st.markdown(f"## How can I help, {state.user['name'].split()[0]}?")
    st.caption(cfg["tagline"])
    st.space("small")
    pick = st.pills(
        "Try",
        cfg["starter_prompts"],
        label_visibility="collapsed",
        key=f"starters-{state.session_id}",
    )
    if pick:
        state.pending = pick

for msg in state.messages:
    render(msg)

submitted = st.chat_input(
    cfg["input_placeholder"],
    accept_file=True,
    file_type=["png", "jpg", "jpeg", "webp"],
    max_upload_size=5,  # MB, same limit as the API
    max_chars=1000,
    submit_mode="disable",  # no second send while an answer is being generated
)

text, upload = None, None
if submitted:
    text, upload = submitted.text.strip(), (submitted.files or [None])[0]
elif state.pending:
    text, state.pending = state.pending, None

if text or upload:
    if not text:
        text = "What does this screenshot show?"
    image = (upload.type, upload.getvalue()) if upload else None
    user_msg = {"role": "user", "content": text, "image": image[1] if image else None}
    state.messages.append(user_msg)
    render(user_msg)

    with st.chat_message("assistant", avatar=BOT_AVATAR):
        # The shimmering label is the "working" cue while the API answers.
        status = st.status(":shimmer[Thinking…]", type="compact")
        started = time.perf_counter()
        try:
            reply = client.chat(UUID(state.user["id"]), state.session_id, text, image)
            bot_msg = {
                "role": "assistant",
                "content": reply.answer,
                "request_id": reply.request_id,
            }
        except ApiError as e:
            bot_msg = {
                "role": "assistant",
                "content": friendly_error(e),
                "request_id": e.request_id,
                "error": True,
            }
        bot_msg["seconds"] = time.perf_counter() - started
        status.update(
            label=f"Answered in {bot_msg['seconds']:.1f} s",
            state="error" if bot_msg.get("error") else "complete",
        )
    state.messages.append(bot_msg)
    st.rerun()  # redraw so the sidebar lists the new chat
