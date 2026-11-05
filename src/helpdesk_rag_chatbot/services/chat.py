from langchain_core.language_models import BaseChatModel
from langchain_core.output_parsers import StrOutputParser

from helpdesk_rag_chatbot.services.prompts import HELPDESK_PROMPT


class ChatService:
    """Generate helpdesk replies using a chat model.

    Attributes:
        chat_model: The chat model used to generate replies.
    """

    def __init__(self, chat_model: BaseChatModel):
        self.chat_model = chat_model
        # Declaring the chain here to avoid re-creating it for every reply, which would be inefficient.
        self.chain = HELPDESK_PROMPT | self.chat_model | StrOutputParser()

    async def reply(self, message: str, context: str = "") -> str:
        """
        Generate a reply to the given message using the chat model.

        :param message: The input message to generate a reply for.
        :param context: The context to use for generating the reply.
        :return: The generated reply as a string.
        """
        return await self.chain.ainvoke({"context": context, "question": message})
