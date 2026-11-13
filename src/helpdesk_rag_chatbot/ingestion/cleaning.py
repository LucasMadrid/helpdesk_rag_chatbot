import re
import unicodedata


def clean_text(text: str) -> str:
    """
    Normalise whitespace and Unicode in text extracted from a document.

    Applies NFKC first, so look-alike characters such as ligatures (``ﬁ``)
    and full-width forms become their plain forms, then converts ``\\r\\n``
    to ``\\n``, strips every line and collapses three or more newlines into
    one blank line.

    :param text: Raw text extracted from a Markdown, PDF or XLSX document.
    :return: The cleaned text, with paragraphs separated by at most one blank
        line and no whitespace at either end.
    """

    text_normalized = unicodedata.normalize("NFKC", text)
    text_normalized = text_normalized.replace("\r\n", "\n")

    text_normalized = "\n".join(line.strip() for line in text_normalized.split("\n"))

    text_normalized = re.sub("\n{3,}", "\n\n", text_normalized)

    return text_normalized.strip()
