"""Embedding model client, served through the LiteLLM gateway."""

from langchain.embeddings import Embeddings
from langchain_openai.embeddings import OpenAIEmbeddings

from helpdesk_rag_chatbot.config import Settings


def get_embeddings(settings: Settings) -> Embeddings:
    """
    Build the embedding client used to vectorise documents and queries.

    Calls go to the LiteLLM gateway through its OpenAI-compatible API. Token
    length checks on the client side are off (``check_embedding_ctx_length=False``),
    because they tokenise with tiktoken, which only knows OpenAI model names, and
    the gateway may serve a different model. Text is sent as-is, so chunks must
    already fit the model's input limit.

    :param settings: Application settings; uses ``litellm_url``, ``litellm_key``,
        ``embedding_model``, ``embedding_dimensions`` and ``llm_timeout``.
    :return: An ``Embeddings`` instance that returns vectors of
        ``embedding_dimensions`` length, which must match the Pinecone index.
    """
    return OpenAIEmbeddings(
        base_url=str(settings.litellm_url),
        api_key=settings.litellm_key,  # SecretStr is accepted directly
        model=settings.embedding_model,
        dimensions=settings.embedding_dimensions,
        check_embedding_ctx_length=False,
        timeout=settings.llm_timeout,
        max_retries=2,
    )
