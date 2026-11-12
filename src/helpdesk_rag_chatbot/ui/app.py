"""Streamlit chat UI for the helpdesk. It only talks to a ChatBackend (backend.py).

Run from the repo root (so Streamlit finds .streamlit/config.toml):
    uv run --extra ui streamlit run src/helpdesk_rag_chatbot/ui/app.py

Look: .streamlit/config.toml. Words, starter prompts, demo users: ui.toml.
Until W3-03 wires the API, every answer comes from DemoBackend (in memory).
"""

import tomllib
from pathlib import Path
from uuid import UUID, uuid7

import streamlit as st

from helpdesk_rag_chatbot.ui.backend import ApiError, ChatBackend
from helpdesk_rag_chatbot.ui.demo_backend import DemoBackend

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


@st.cache_resource
def get_backend() -> ChatBackend:
    """One backend for the whole Streamlit server (W3-03 swaps in the API client)."""
    return DemoBackend()


client = get_backend()
DEMO = isinstance(client, DemoBackend)

# The only CSS: chat titles in the sidebar read better left-aligned.
st.html("""<style>
.st-key-recent button, .st-key-recent button > div { justify-content: flex-start; }
</style>""")

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


# ---- sidebar: who, new chat, recent chats ----------------------------------
with st.sidebar:
    st.markdown(f"#### :material/support_agent: {cfg['assistant_name']}")
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
    st.space("small")

    try:
        sessions = client.list_sessions(UUID(state.user["id"]))
    except ApiError as e:
        sessions = []
        st.caption(f":material/cloud_off: {friendly_error(e)}")

    recent = st.container(key="recent", gap="small")
    if sessions:
        recent.caption("Recent")
    for s in sessions:
        current = s.session_id == state.session_id
        label = s.title if len(s.title) <= 34 else s.title[:33] + "…"
        recent.button(
            label,
            key=f"s-{s.session_id}",
            width="stretch",
            type="secondary" if current else "tertiary",
            on_click=open_chat,
            args=(s.session_id,),
        )

    current = next((s for s in sessions if s.session_id == state.session_id), None)
    if current:
        st.space("small")
        if st.button("Delete this chat", icon=":material/delete:", type="tertiary"):
            confirm_delete(current.session_id, current.title)

    st.space("large")
    names = [u["name"] for u in cfg["demo_users"]]
    picked = st.selectbox("Signed in as", names, index=names.index(state.user["name"]))
    if picked != state.user["name"]:
        state.user = cfg["demo_users"][names.index(picked)]
        start_new_chat()
        st.rerun()


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
            st.image(msg["image"], width=260)
        elif has_marker:
            st.caption(":material/image: Screenshot attached (not stored)")
        if msg.get("request_id"):
            st.caption(
                f"Ref `{msg['request_id']}`", help="Quote this if you report a problem."
            )


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

    with (
        st.chat_message("assistant", avatar=BOT_AVATAR),
        st.spinner("Looking it up…"),
    ):
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
    state.messages.append(bot_msg)
    st.rerun()  # redraw so the sidebar lists the new chat
