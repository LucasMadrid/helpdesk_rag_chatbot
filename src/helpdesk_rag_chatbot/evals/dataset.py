from collections import Counter
from pathlib import Path
from typing import Any, Literal, Self

import yaml
from langfuse import Langfuse
from pydantic import BaseModel, Field, model_validator

Split = Literal["tune", "holdout"]
QuestionType = Literal[
    "single",
    "version",
    "trap",
    "image-error-code",
    "unanswerable",
    "near-miss",
    "multi-doc",
]
# One Langfuse dataset per split, so a run can never mix tune and holdout items.
DATASET_NAMES: dict[Split, str] = {
    "tune": "helpdesk-qa-tune",
    "holdout": "helpdesk-qa-holdout",
}
# Shown in the Langfuse UI, so whoever opens a dataset knows how to use it.
DATASET_DESCRIPTIONS: dict[Split, str] = {
    "tune": (
        "Helpdesk RAG eval questions, tune split: run as often as needed while "
        "developing. Source of truth: evals/questions.yaml; don't edit items here."
    ),
    "holdout": (
        "Helpdesk RAG eval questions, holdout split: run once, at the end of W7; "
        "never tune against it. Source of truth: evals/questions.yaml; don't edit "
        "items here."
    ),
}


class ExpectedSource(BaseModel):
    """A document section that a correct answer must cite.

    :ivar doc_id: The document's id in the corpus, for example ``it-vpn-guide``.
    :ivar version: The document version, as a string (``"2.0"``, not ``2.0``).
    :ivar section: The heading of the section that holds the answer.
    """

    doc_id: str
    version: str
    section: str


class EvalQuestion(BaseModel):
    """One eval question from ``evals/questions.yaml``.

    :ivar id: ``Q`` plus two digits, for example ``Q01``.
    :ivar split: ``tune`` (used while developing) or ``holdout`` (run once).
    :ivar type: What the question tests, for example ``trap`` or ``unanswerable``.
    :ivar question: The text sent to the bot.
    :ivar answer: The reference answer the bot's reply is judged against.
    :ivar sources: The documents a correct answer cites; empty when the docs
        don't cover the question.
    """

    id: str = Field(pattern=r"^Q\d{2}$")
    split: Split
    type: QuestionType
    question: str = Field(min_length=1)
    answer: str
    sources: list[ExpectedSource]

    @model_validator(mode="after")
    def _unanswerable_has_no_sources(self) -> Self:
        # Both sides must agree, or the abstain metric scores the wrong items.
        if (self.type == "unanswerable") != (not self.sources):
            raise ValueError(
                f"{self.id}: type 'unanswerable' and an empty 'sources' must go "
                f"together (type={self.type!r}, {len(self.sources)} sources)"
            )
        return self

    @property
    def should_abstain(self) -> bool:
        """Whether the bot should say the docs don't cover the question."""
        return self.type == "unanswerable"


def load_questions(path: Path) -> list[EvalQuestion]:
    """Load and validate the eval questions from a YAML file.

    :param path: The YAML file, a list of question mappings
        (normally ``evals/questions.yaml``).
    :returns: The questions in file order; empty for an empty file.
    :raises pydantic.ValidationError: An item is missing a field or has an
        invalid value.
    :raises ValueError: Two or more questions share an id; the message lists
        the duplicated ids.
    """
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or []

    eval_questions = [EvalQuestion.model_validate(item) for item in raw]

    counter_ids = Counter(q.id for q in eval_questions)
    dupes = [i for i, n in counter_ids.items() if n > 1]

    if dupes:
        raise ValueError(f"Duplicate question ids: {sorted(dupes)}")

    return eval_questions


ITEM_ID_PREFIX = "helpdesk-qa-"


def to_dataset_item(question: EvalQuestion) -> dict[str, Any]:
    """Turn an eval question into the fields of a Langfuse dataset item.

    The item id is stable (``Q06`` -> ``helpdesk-qa-q06``), so re-uploading the
    YAML updates each item in place instead of adding a copy.

    :param question: A validated question from ``load_questions``.
    :returns: A dict with ``id``, ``input`` (what the bot is sent),
        ``expected_output`` (what it is judged against) and ``metadata``
        (for filtering results by question, type and split).
    """
    return {
        "id": f"{ITEM_ID_PREFIX}{question.id.lower()}",
        "input": {"question": question.question},
        "expected_output": {
            "answer": question.answer,
            "sources": [source.model_dump() for source in question.sources],
            "should_abstain": question.should_abstain,
        },
        "metadata": {
            "question_id": question.id,
            "type": question.type,
            "split": question.split,
        },
    }


def upload_questions(client: Langfuse, questions: list[EvalQuestion]) -> dict[str, int]:
    """Create or update the tune and holdout datasets in Langfuse.

    Safe to run again after editing the YAML: Langfuse upserts datasets by name
    and items by id, and the ids come from ``to_dataset_item``, so each item is
    updated in place. A question deleted from the YAML is not deleted from
    Langfuse; archive it in the UI.

    :param client: A Langfuse client, usually from ``get_langfuse_client``.
    :param questions: The questions from ``load_questions``.
    :returns: How many items were uploaded to each split's dataset, for example
        ``{"tune": 25, "holdout": 15}``.
    """
    for split, name in DATASET_NAMES.items():
        client.create_dataset(name=name, description=DATASET_DESCRIPTIONS[split])

    for q in questions:
        client.create_dataset_item(
            dataset_name=DATASET_NAMES[q.split], **to_dataset_item(q)
        )

    counts = Counter(q.split for q in questions)
    return {split: counts[split] for split in DATASET_NAMES}
