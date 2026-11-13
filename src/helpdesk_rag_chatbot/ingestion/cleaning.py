import re
import unicodedata

PAGE_NUMBER = re.compile(r"Page \d+( of \d+)?")
EDGE_LINES = 2


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


def remove_page_furniture(pages: list[str]) -> list[str]:
    """
    Drop running headers, footers and page numbers from the pages of a PDF.

    Only the first and last ``EDGE_LINES`` lines of each page are candidates.
    One is dropped if it appears at an edge of every page, or if it is a page
    number such as ``Page 3`` or ``Page 3 of 9``. Lines in the body of a page
    are always kept, even when they repeat. A single page has nothing to
    compare against, so only its page numbers are dropped. On a page of four
    lines or fewer every line is an edge, so a body line that repeats on
    every page is dropped too.

    :param pages: The text of each page, in order.
    :return: The same pages with their furniture lines removed.
    """
    pages_lines = [page.splitlines() for page in pages]

    edge_sets = [
        {line.strip() for line in lines[:EDGE_LINES] + lines[-EDGE_LINES:]}
        for lines in pages_lines
    ]
    repeated = set.intersection(*edge_sets) if len(edge_sets) >= 2 else set()

    def is_furniture(line: str, index: int, line_count: int) -> bool:
        at_edge = index < EDGE_LINES or index >= line_count - EDGE_LINES
        text = line.strip()
        return at_edge and (text in repeated or PAGE_NUMBER.fullmatch(text) is not None)

    return [
        "\n".join(
            line
            for index, line in enumerate(lines)
            if not is_furniture(line, index, len(lines))
        )
        for lines in pages_lines
    ]
