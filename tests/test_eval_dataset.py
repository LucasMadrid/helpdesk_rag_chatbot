"""Tests for the eval question loader in evals/dataset.py (W6-01)."""

from collections import Counter
from pathlib import Path
from typing import Any, get_args

import pytest
import yaml
from pydantic import ValidationError

from helpdesk_rag_chatbot.evals.dataset import (
    EvalQuestion,
    ExpectedSource,
    QuestionType,
    load_questions,
)
from helpdesk_rag_chatbot.ingestion.loaders import load_corpus

ROOT = Path(__file__).parents[1]
QUESTIONS_FILE = ROOT / "evals" / "questions.yaml"
DOCS_DIR = ROOT / "data" / "docs"

SOURCE = {"doc_id": "it-vpn-guide", "version": "1.0", "section": "Fixing error 809"}


def _item(**overrides: Any) -> dict[str, Any]:
    """A valid answerable question; override fields to break it."""
    item = {
        "id": "Q01",
        "split": "tune",
        "type": "single",
        "question": "My VPN says error 809",
        "answer": "Switch Protocol to TLS (port 443).",
        "sources": [SOURCE],
    }
    return item | overrides


def _write(tmp_path: Path, items: list[dict[str, Any]]) -> Path:
    path = tmp_path / "questions.yaml"
    path.write_text(yaml.safe_dump(items))
    return path


# 1
def test_real_questions_file_loads() -> None:
    questions = load_questions(QUESTIONS_FILE)

    assert questions
    assert all(isinstance(q, EvalQuestion) for q in questions)
    assert all(isinstance(s, ExpectedSource) for q in questions for s in q.sources)
    assert len({q.id for q in questions}) == len(questions)


# 2
def test_duplicate_id_raises_and_names_it(tmp_path: Path) -> None:
    path = _write(
        tmp_path,
        [_item(id="Q01"), _item(id="Q02"), _item(id="Q01", question="Other")],
    )

    with pytest.raises(ValueError, match=r"Duplicate question ids: \['Q01'\]"):
        load_questions(path)


# 3
def test_unanswerable_with_sources_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unanswerable"):
        EvalQuestion.model_validate(_item(type="unanswerable"))

    abstain = EvalQuestion.model_validate(_item(type="unanswerable", sources=[]))
    assert abstain.should_abstain


# 4
def test_answerable_without_sources_is_rejected() -> None:
    with pytest.raises(ValidationError, match="unanswerable"):
        EvalQuestion.model_validate(_item(sources=[]))

    answerable = EvalQuestion.model_validate(_item())
    assert not answerable.should_abstain


# 5
def test_bad_id_is_rejected() -> None:
    for bad_id in ["Q1", "Q001", "q01", "01", ""]:
        with pytest.raises(ValidationError, match="id"):
            EvalQuestion.model_validate(_item(id=bad_id))


# The file against the corpus: a source that names a missing doc or section
# can never be matched, so the citation metric would score it wrong forever.


def _corpus() -> dict[str, str]:
    """Each doc's cleaned text, keyed ``<doc_id>@<version>`` as at ingestion."""
    return {doc.id: doc.page_content for doc in load_corpus(DOCS_DIR)}


def _lines(text: str) -> set[str]:
    """Every line of a doc, with Markdown heading marks stripped."""
    return {line.strip().lstrip("#").strip() for line in text.splitlines()}


# 6
def test_every_source_names_a_doc_version_in_the_corpus() -> None:
    corpus = _corpus()
    missing = [
        f"{q.id}: {s.doc_id}@{s.version}"
        for q in load_questions(QUESTIONS_FILE)
        for s in q.sources
        if f"{s.doc_id}@{s.version}" not in corpus
    ]

    assert not missing, f"not in data/docs: {missing}"


# 7
def test_every_source_section_is_a_line_in_its_doc() -> None:
    corpus = _corpus()
    missing = [
        f"{q.id}: {s.section!r} in {s.doc_id}@{s.version}"
        for q in load_questions(QUESTIONS_FILE)
        for s in q.sources
        if f"{s.doc_id}@{s.version}" in corpus
        and s.section not in _lines(corpus[f"{s.doc_id}@{s.version}"])
    ]

    assert not missing, f"section text doesn't match the doc: {missing}"


# The shape of the dataset: tune is what we iterate on, holdout is run once at
# the end of W7, so it must test every behaviour and share nothing with tune.


# 8
def test_dataset_has_40_numbered_questions_split_25_15() -> None:
    questions = load_questions(QUESTIONS_FILE)
    splits = Counter(q.split for q in questions)

    assert [q.id for q in questions] == [f"Q{n:02d}" for n in range(1, 41)]
    assert splits == {"tune": 25, "holdout": 15}


# 9
def test_holdout_covers_every_type_and_repeats_no_tune_question() -> None:
    questions = load_questions(QUESTIONS_FILE)
    holdout = [q for q in questions if q.split == "holdout"]
    tune_texts = {_normalise(q.question) for q in questions if q.split == "tune"}

    assert {q.type for q in holdout} == set(get_args(QuestionType))
    assert not [q.id for q in holdout if _normalise(q.question) in tune_texts]


def _normalise(text: str) -> str:
    return " ".join(text.lower().split())
