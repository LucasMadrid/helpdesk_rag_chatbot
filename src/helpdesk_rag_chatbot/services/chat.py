from dataclasses import dataclass

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, trim_messages
from langchain_core.output_parsers import StrOutputParser

from helpdesk_rag_chatbot.services.prompts import HELPDESK_PROMPT


@dataclass(frozen=True)
class ImageAttachment:
    """An image the API layer already checked: its MIME type and raw base64."""

    mime_type: str
    data: str


class ChatService:
    """Generate helpdesk replies using a chat model.

    Each reply loads the session's earlier turns (trimmed to a token budget),
    sends them with the new question and an optional image to the model, and
    saves the question and answer to the history only if the call succeeds. An
    image is sent to the model but never stored: the history keeps a text
    marker instead.

    Attributes:
        chat_model: The chat model used to generate replies.
        history_max_tokens: Token budget for the earlier turns sent to the
            model. Older turns are dropped from the prompt, not from the stored
            history.
        callbacks: LangChain callback handlers run on every reply, for example
            tracing. An empty list means no callbacks.
        chain: The prompt, chat model and output parser, built once and reused
            for every reply.
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

    def _run_config(
        self, *, user_id, session_id, request_id, past, kept, image
    ) -> dict:
        """
        Build the LangChain run config for one reply: callbacks, run name and
        the metadata that tracing (Langfuse) uses to group and filter traces.

        :param user_id: The unique identifier of the user making the request.
        :param session_id: The unique identifier of the chat session.
        :param request_id: The unique identifier of the chat request.
        :param past: All stored messages of the session, before trimming.
        :param kept: The messages of ``past`` that fit the token budget and are
            sent to the model.
        :param image: The attached image, or None. Only its presence is
            recorded; the image data never goes into the metadata.
        :return: A dict to pass as ``config`` to the chain.
        """
        return {
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
                "has_image": image is not None,
            },
        }

    @staticmethod
    def _build_question(message: str, image: ImageAttachment | None) -> HumanMessage:
        """
        Build the message sent to the model: plain text, or text plus the image.

        :param message: The user's question.
        :param image: The attached image, or None.
        :return: A HumanMessage; with an image its content is a list of blocks.
        """
        if image is None:
            return HumanMessage(content=message)
        return HumanMessage(
            content=[
                {"type": "text", "text": message},
                {
                    "type": "image",
                    "base64": image.data,
                    "mime_type": image.mime_type,
                },
            ]
        )

    @staticmethod
    def _history_text(message: str, image: ImageAttachment | None) -> str:
        """
        Build the text stored in the history for the user's turn.

        The image itself is never stored, only a marker with its MIME type, so
        the database does not fill up with base64.

        :param message: The user's question.
        :param image: The attached image, or None.
        :return: The message, plus an ``[image: <mime type>]`` line if attached.
        """
        if image is None:
            return message
        return f"{message}\n[image: {image.mime_type}]"

    async def reply(
        self,
        message: str,
        context: str = "",
        image: ImageAttachment = None,
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

        question = self._build_question(message, image)

        answer = await self.chain.ainvoke(
            {
                "context": context,
                "history": kept,
                "question": [question],
            },
            config=self._run_config(
                user_id=user_id,
                session_id=session_id,
                request_id=request_id,
                past=past,
                kept=kept,
                image=image,
            ),
        )

        saved = self._history_text(message, image)
        await history.aadd_messages(
            [HumanMessage(content=saved), AIMessage(content=answer)]
        )

        return answer
