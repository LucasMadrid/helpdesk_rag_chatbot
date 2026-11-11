from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, trim_messages
from langchain_core.output_parsers import StrOutputParser

from helpdesk_rag_chatbot.services.prompts import HELPDESK_PROMPT


class ChatService:
    """Generate helpdesk replies using a chat model.

    Attributes:
        chat_model: The chat model used to generate replies.
        callbacks: LangChain callback handlers run on every reply, for example
            tracing. An empty list means no callbacks.
    """

    def __init__(
        self,
        chat_model: BaseChatModel,
        callbacks: list[BaseCallbackHandler] | None = None,
        *,
        history_max_tokens: int = 2000,
    ):
        self.chat_model = chat_model
        self.history_max_tokens = history_max_tokens
        self.callbacks = callbacks or []
        # Declaring the chain here to avoid re-creating it for every reply, which would be inefficient.
        self.chain = HELPDESK_PROMPT | self.chat_model | StrOutputParser()

    async def reply(
        self,
        message: str,
        context: str = "",
        *,
        user_id: str,
        request_id: str,
        session_id: str,
        history: BaseChatMessageHistory,
    ) -> str:
        """
        Generate a reply to the given message using the chat model.

        :param message: The input message to generate a reply for.
        :param context: The context to use for generating the reply.
        :param user_id: The unique identifier of the user making the request.
        :param request_id: The unique identifier of the chat request.
        :param session_id: The unique identifier of the chat session.
        :param history: The stored messages of this session. Earlier turns are
            loaded into the prompt, and the new question and answer are saved
            only after the model call succeeds.
        :return: The generated reply as a string.
        """

        past = await history.aget_messages()

        kept = trim_messages(
            past,
            max_tokens=self.history_max_tokens,
            token_counter="approximate",
            strategy="last",  # keep the newest messages
            start_on="human",  # never start with an answer whose question was cut
        )

        answer = await self.chain.ainvoke(
            {"context": context, "history": kept, "question": message},
            config={
                "callbacks": self.callbacks,
                # Names are an API for Langfuse evaluators and dashboards: keep it
                # verb-first, free of dynamic values, and stable.
                "run_name": "chat-response",
                "metadata": {
                    # The langfuse_* names are a Langfuse convention, so a different
                    # tracing vendor would need different keys here. We accept this
                    # small leak to keep ChatService free of vendor imports.
                    "langfuse_user_id": user_id,
                    "langfuse_session_id": session_id,
                    # Tags are immutable and can only be set when the trace is created.
                    "langfuse_tags": ["chat"],
                    "request_id": request_id,
                    "history_messages_total": len(past),
                    "history_messages_sent": len(kept),
                },
            },
        )

        await history.aadd_messages(
            [HumanMessage(content=message), AIMessage(content=answer)]
        )

        return answer
