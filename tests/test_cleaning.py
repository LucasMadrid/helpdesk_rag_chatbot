import pytest

from helpdesk_rag_chatbot.ingestion.cleaning import clean_text, remove_page_furniture


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("a\r\nb", "a\nb"),
        (" a \n b ", "a\nb"),
        ("a\n\n\n\nb", "a\n\nb"),
        ("\n a \n", "a"),
        ("a\n\n  \n\nb", "a\n\nb"),  # the ordering trap from step 3
    ],
    ids=["crlf", "strip-lines", "collapse", "strip-ends", "order-trap"],
)
def test_clean_text_each_step(raw: str, expected: str) -> None:
    assert clean_text(raw) == expected


def test_clean_text_normalises_whitespace() -> None:
    assert clean_text("a  \r\n\r\n\r\n\r\n b ") == "a\n\nb"


def test_clean_text_applies_nfkc() -> None:
    assert clean_text("ﬁle") == "file"


def test_remove_page_furniture_drops_repeated_header_and_page_numbers() -> None:
    pages = ["Header\nPage 1\nBody A\nEnd A", "Header\nPage 2\nBody B\nEnd B"]
    assert remove_page_furniture(pages) == ["Body A\nEnd A", "Body B\nEnd B"]


def test_remove_page_furniture_drops_page_x_of_y() -> None:
    pages = ["Body A\nMore A\nPage 1 of 2", "Body B\nMore B\nPage 2 of 2"]
    assert remove_page_furniture(pages) == ["Body A\nMore A", "Body B\nMore B"]


def test_remove_page_furniture_keeps_repeated_body_line() -> None:
    pages = [
        "Top A\nTop A2\nShared\nBottom A\nBottom A2",
        "Top B\nTop B2\nShared\nBottom B\nBottom B2",
    ]
    assert remove_page_furniture(pages) == pages


def test_remove_page_furniture_keeps_edge_line_on_some_pages_only() -> None:
    pages = ["Intro\nBody A", "Intro\nBody B", "Other\nBody C"]
    assert remove_page_furniture(pages) == pages


def test_remove_page_furniture_single_page_drops_only_page_number() -> None:
    assert remove_page_furniture(["Title\nBody\nPage 1"]) == ["Title\nBody"]


def test_remove_page_furniture_ignores_trailing_spaces() -> None:
    pages = ["Header \nBody A\nEnd A", "Header\nBody B\nEnd B"]
    assert remove_page_furniture(pages) == ["Body A\nEnd A", "Body B\nEnd B"]
