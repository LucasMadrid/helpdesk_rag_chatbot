# uv run python check_clean.py
from helpdesk_rag_chatbot.ingestion.cleaning import clean_text

cases = {
    "a  \r\n\r\n\r\n\r\n b ": "a\n\nb",
    "ﬁle": "file",
    "\n a \n": "a",
    "a\n\nb": "a\n\nb",
}
for raw, want in cases.items():
    got = clean_text(raw)
    print("OK " if got == want else "BAD", repr(raw), "->", repr(got))
