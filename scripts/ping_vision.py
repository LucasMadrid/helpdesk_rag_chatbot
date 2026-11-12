import base64, pathlib
from langchain_core.messages import HumanMessage
from helpdesk_rag_chatbot.adapters.llm import get_chat_model
from helpdesk_rag_chatbot.config import get_settings

data = base64.b64encode(
    pathlib.Path.home().joinpath("./vpn-error.png").read_bytes()
).decode()
msg = HumanMessage(
    content=[
        {"type": "text", "text": "What does this error say?"},
        {"type": "image", "base64": data, "mime_type": "image/png"},
    ]
)
print(get_chat_model(get_settings()).invoke([msg]).content)
