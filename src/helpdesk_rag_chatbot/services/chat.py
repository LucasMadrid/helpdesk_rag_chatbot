from dataclasses import dataclass

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    trim_messages,
)
from langchain_core.output_parsers import StrOutputParser
from langchain_core.retrievers import BaseRetriever
from langchain_core.runnables import RunnableConfig

from helpdesk_rag_chatbot.services.prompts import (
    CONDENSE_PROMPT,
    HELPDESK_PROMPT,
    NO_SOURCES,
)
from helpdesk_rag_chatbot.services.rag import (
    Source,
    cited_sources,
    context_tokens,
    fit_docs,
    format_context,
)


@dataclass(frozen=True)
class ImageAttachment:
    """An image the API layer already checked: its MIME type and raw base64."""

    mime_type: str
    data: str


@dataclass(frozen=True)
class ChatReply:
    """
    A generated answer and the documents it cites.

    :ivar answer: The model's answer text.
    :ivar sources: The documents the answer cites with ``[n]`` markers, once
        each, in order of first mention. Empty if it cites none.
    """

    answer: str
    sources: list[Source]


class ChatService:
    """
    Generate helpdesk replies grounded in retrieved documents.

    Each reply retrieves chunks for the question, keeps the top-ranked ones
    that fit the context budget, and gives the earlier turns of the session
    whatever budget is left. It sends the numbered chunks, the trimmed history,
    the new question and an optional image to the model, and returns the
    answer with the sources it cites. The question and answer are saved to the
    history only if the call succeeds. An image is sent to the model but never
    stored: the history keeps a text marker instead.

    :ivar chat_model: The chat model used to generate replies.
    :ivar history_max_tokens: Token budget for the earlier turns sent to the
        model. Older turns are dropped from the prompt, not from the stored
        history.
    :ivar context_max_tokens: Token budget shared by the retrieved chunks and
        the earlier turns. Chunks are fitted first; history gets what is left,
        up to ``history_max_tokens``.
    :ivar rewrite_history_messages: How many of the newest stored messages the
        question rewrite sees. 0 turns the rewrite off, so the message itself
        is the retrieval query.
    :ivar callbacks: LangChain callback handlers run on every reply, for
        example tracing. An empty list means no callbacks.
    :ivar retriever: Finds the chunks for a question, or None to answer
        without retrieved context.
    :ivar chain: The prompt, chat model and output parser, built once and
        reused for every reply.
    :ivar condense_chain: The rewrite prompt, chat model and output parser,
        built once and reused to turn follow-ups into standalone questions.
    """

    def __init__(
        self,
        chat_model: BaseChatModel,
        callbacks: list[BaseCallbackHandler] | None = None,
        *,
        retriever: BaseRetriever | None = None,
        history_max_tokens: int = 2000,
        context_max_tokens: int = 3000,
        rewrite_history_messages: int = 6,
    ):
        self.chat_model = chat_model
        self.history_max_tokens = history_max_tokens
        self.context_max_tokens = context_max_tokens
        self.rewrite_history_messages = rewrite_history_messages
        self.callbacks = callbacks or []
        self.retriever = retriever
        # Declaring the chain here to avoid re-creating it for every reply, which would be inefficient.
        self.chain = HELPDESK_PROMPT | self.chat_model | StrOutputParser()
        # Declaring the condense chain for query enhancement
        self.condense_chain = CONDENSE_PROMPT | self.chat_model | StrOutputParser()

    def _run_config(
        self,
        *,
        user_id: str,
        session_id: str,
        request_id: str,
        chunks_retrieved: int,
        chunks_sent: int,
        context_tokens_used: int,
        history_budget: int,
        past: list[BaseMessage],
        kept: list[BaseMessage],
        image: ImageAttachment | None,
    ) -> RunnableConfig:
        """
        Build the LangChain run config for one reply.

        It holds the callbacks, the run name and the metadata that tracing
        (Langfuse) uses to group and filter traces.

        :param user_id: The unique identifier of the user making the request.
        :param session_id: The unique identifier of the chat session.
        :param request_id: The unique identifier of the chat request.
        :param chunks_retrieved: How many chunks the retriever returned.
        :param chunks_sent: How many of them fit ``context_max_tokens`` and
            were sent to the model.
        :param context_tokens_used: Approximate tokens of the formatted context.
        :param history_budget: Tokens the history was trimmed to: what the
            context left of the budget, at most ``history_max_tokens``.
        :param past: All stored messages of the session, before trimming.
        :param kept: The messages of ``past`` that fit the token budget and are
            sent to the model.
        :param image: The attached image, or None. Only its presence is
            recorded; the image data never goes into the metadata.
        :return: The config to pass to the chain.
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
                "chunks_retrieved": chunks_retrieved,
                "chunks_sent": chunks_sent,
                "context_tokens": context_tokens_used,
                "history_budget": history_budget,
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

    @staticmethod
    def _history_budget(history_max: int, context_max: int, used: int) -> int:
        """
        Work out how many tokens of history fit next to the retrieved context.

        History gets whatever the documents left of the context budget, but
        never more than its own cap, and never less than zero.

        :param history_max: The history cap, ``HISTORY_MAX_TOKENS``.
        :param context_max: The shared budget, ``CONTEXT_MAX_TOKENS``.
        :param used: Tokens already used by the formatted context.
        :return: The token budget for ``trim_messages``; 0 if no room is left.
        """
        return max(0, min(history_max, context_max - used))

    async def _retrieval_query(
        self,
        message: str,
        past: list[BaseMessage],
        *,
        user_id: str,
        session_id: str,
        request_id: str,
    ) -> str:
        """
        Build the query sent to the retriever for this message.

        A follow-up such as "and on Mac?" retrieves poorly on its own, so the
        model rewrites it as a standalone question from the newest
        ``rewrite_history_messages`` of the history. With no history, or with
        the rewrite turned off, the message is used as it is and no model call
        is made.

        :param message: The user's question.
        :param past: All stored messages of the session, before trimming.
        :param user_id: The unique identifier of the user making the request.
        :param session_id: The unique identifier of the chat session.
        :param request_id: The unique identifier of the chat request.
        :return: The standalone question, stripped of surrounding whitespace,
            or ``message`` unchanged when no rewrite is made or the model
            returns an empty one.
        """
        if not past or self.rewrite_history_messages == 0:
            return message

        trimmed_past = trim_messages(
            past,
            max_tokens=self.rewrite_history_messages,
            token_counter=len,
            strategy="last",  # keep the newest messages
            start_on="human",  # never start with an answer whose question was cut
        )

        rewritten = await self.condense_chain.ainvoke(
            {
                "history": trimmed_past,
                "question": message,
            },
            config={
                "callbacks": self.callbacks,
                # Stable and verb-first, like "chat-response" in _run_config.
                "run_name": "rewrite-question",
                "metadata": {
                    "langfuse_user_id": user_id,
                    "langfuse_session_id": session_id,
                    # The rewrite is its own trace; the tag lets it be filtered.
                    "langfuse_tags": ["rewrite"],
                    "request_id": request_id,
                },
            },
        )
        # An empty rewrite would search for "", so keep the original message.
        return rewritten.strip() or message

    async def reply(
        self,
        message: str,
        *,
        image: ImageAttachment | None = None,
        user_id: str,
        request_id: str,
        session_id: str,
        history: BaseChatMessageHistory,
    ) -> ChatReply:
        """
        Answer a message from the retrieved documents and the session history.

        The steps, in order:

        1. Retrieve chunks for ``message`` (none without a retriever).
        2. Keep the top-ranked chunks that fit ``context_max_tokens``
           (``fit_docs``) and number them as ``[n]`` blocks.
        3. Give the history what the chunks left of that budget, at most
           ``history_max_tokens``, and keep the newest turns that fit.
        4. Call the model, then save the question and answer.
        5. Map the answer's ``[n]`` citations to sources. Only chunks that
           were sent count: a citation of a dropped chunk is ignored.

        :param message: The user's question. It is also the retrieval query.
        :param image: An optional image to send to the model with the question.
            It is not stored: the history keeps a text marker instead.
        :param user_id: The unique identifier of the user making the request.
        :param request_id: The unique identifier of the chat request.
        :param session_id: The unique identifier of the chat session.
        :param history: The stored messages of this session. Earlier turns are
            loaded into the prompt, and the new question and answer are saved
            only after the model call succeeds.
        :return: The answer and the sources it cites.
        """

        past = await history.aget_messages()

        if self.retriever is not None:
            # The rewrite only serves retrieval, so skip it without a retriever.
            query = await self._retrieval_query(
                message,
                past,
                user_id=user_id,
                session_id=session_id,
                request_id=request_id,
            )
            docs = await self.retriever.ainvoke(query)
        else:
            docs = []

        sent = fit_docs(docs, self.context_max_tokens)

        context = format_context(sent) or NO_SOURCES
        used = context_tokens(context)

        history_budget = self._history_budget(
            self.history_max_tokens, self.context_max_tokens, used
        )

        kept = trim_messages(
            past,
            max_tokens=history_budget,
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
                chunks_retrieved=len(docs),
                chunks_sent=len(sent),
                context_tokens_used=used,
                history_budget=history_budget,
                past=past,
                kept=kept,
                image=image,
            ),
        )

        saved = self._history_text(message, image)
        await history.aadd_messages(
            [HumanMessage(content=saved), AIMessage(content=answer)]
        )

        return ChatReply(answer=answer, sources=cited_sources(answer, sent))
