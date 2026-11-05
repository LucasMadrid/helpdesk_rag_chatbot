import asyncio

from helpdesk_rag_chatbot.adapters.llm import get_chat_model
from helpdesk_rag_chatbot.config import get_settings
from helpdesk_rag_chatbot.services.chat import ChatService

settings = get_settings()
chat_model = get_chat_model(settings)
chat_service = ChatService(chat_model)


async def main() -> None:
    """Send a sample helpdesk question and print the assistant's reply."""
    message = "How do I reset my password?"
    context = "You can reset your password by clicking the 'Forgot Password' link on the login page."
    reply = await chat_service.reply(message, context)
    print(f"User: {message}")
    print(f"Helpdesk: {reply}")


if __name__ == "__main__":
    asyncio.run(main())
