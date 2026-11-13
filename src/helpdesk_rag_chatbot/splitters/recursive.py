from langchain_text_splitters import RecursiveCharacterTextSplitter, TextSplitter


def build_recursive_splitter(chunk_size: int, chunk_overlap: int) -> TextSplitter:
    """
    Build a recursive character splitter that records each chunk's start offset.

    Splits on paragraphs, then lines, then words, then characters until chunks
    fit. ``add_start_index`` stores each chunk's offset in its parent as
    ``start_index``.

    :param chunk_size: Maximum chunk length in characters.
    :param chunk_overlap: Number of characters shared between consecutive chunks.
    :return: A configured ``RecursiveCharacterTextSplitter``.
    """
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap, add_start_index=True
    )
