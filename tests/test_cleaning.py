import pytest

from helpdesk_rag_chatbot.ingestion.cleaning import clean_text


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
