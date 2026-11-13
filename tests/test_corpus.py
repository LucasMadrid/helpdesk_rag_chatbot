"""Contract tests for the RAG corpus in data/docs.

These guard the front matter that ingestion (W5) relies on: Pinecone metadata
and the W5-01 current-version filter both read it as-is.
"""

from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import frontmatter
import pytest
import yaml

DOCS_DIR = Path(__file__).parents[1] / "data" / "docs"
DOC_SUFFIXES = (".md", ".pdf", ".xlsx")
DOC_FILES = sorted(
    path for suffix in DOC_SUFFIXES for path in DOCS_DIR.glob(f"*{suffix}")
)
SIDECARS = sorted(DOCS_DIR.glob("*.meta.yaml"))

REQUIRED_KEYS = {"doc_id", "title", "version", "valid_from", "status", "area"}
AREAS = {"IT", "HR", "General"}
STRING_KEYS = ("version", "valid_from", "valid_to", "supersedes")
DATE_KEYS = ("valid_from", "valid_to")


def _meta(path: Path) -> dict[str, Any]:
    """Markdown carries its own front matter; PDF and XLSX docs use a sidecar.

    ``x.v1.0.pdf`` -> ``x.v1.0.meta.yaml`` (``with_suffix`` swaps only ``.pdf``).
    """
    if path.suffix == ".md":
        return frontmatter.load(path).metadata
    meta: dict[str, Any] = yaml.safe_load(
        path.with_suffix(".meta.yaml").read_text(encoding="utf-8")
    )
    return meta


ALL_META = {path: _meta(path) for path in DOC_FILES}

by_name = pytest.mark.parametrize("path", DOC_FILES, ids=lambda p: p.name)


def _by_doc_id() -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for meta in ALL_META.values():
        groups[meta["doc_id"]].append(meta)
    return groups


def test_corpus_has_expected_files() -> None:
    assert len(DOC_FILES) == 17
    assert len({meta["doc_id"] for meta in ALL_META.values()}) == 15


@by_name
def test_every_doc_has_required_front_matter(path: Path) -> None:
    meta = ALL_META[path]
    missing = REQUIRED_KEYS - meta.keys()
    assert not missing, f"missing keys: {sorted(missing)}"
    assert meta["area"] in AREAS


@by_name
def test_version_and_dates_are_strings(path: Path) -> None:
    meta = ALL_META[path]
    for key in STRING_KEYS:
        if key in meta:
            assert isinstance(meta[key], str), (
                f"{key} is {type(meta[key]).__name__}, quote it"
            )
    for key in DATE_KEYS:
        if key in meta:
            date.fromisoformat(meta[key])


@by_name
def test_file_name_matches_doc_id_and_version(path: Path) -> None:
    meta = ALL_META[path]
    assert path.name == f"{meta['doc_id']}.v{meta['version']}{path.suffix}"


@pytest.mark.parametrize("sidecar", SIDECARS, ids=lambda p: p.name)
def test_every_sidecar_file_exists(sidecar: Path) -> None:
    meta = yaml.safe_load(sidecar.read_text(encoding="utf-8"))
    assert "file" in meta, "sidecar has no 'file' key"
    assert (DOCS_DIR / meta["file"]).is_file(), f"{meta['file']} not found"


@pytest.mark.parametrize("doc_id", sorted(_by_doc_id()))
def test_each_doc_id_has_exactly_one_current_version(doc_id: str) -> None:
    statuses = [meta["status"] for meta in _by_doc_id()[doc_id]]
    assert statuses.count("current") == 1, statuses


SUPERSEDED_DOC_IDS = sorted(
    doc_id
    for doc_id, metas in _by_doc_id().items()
    if any(meta["status"] == "superseded" for meta in metas)
)


@pytest.mark.parametrize("doc_id", SUPERSEDED_DOC_IDS)
def test_superseded_ends_before_current_starts(doc_id: str) -> None:
    metas = _by_doc_id()[doc_id]
    (current,) = [meta for meta in metas if meta["status"] == "current"]
    current_start = date.fromisoformat(current["valid_from"])
    for old in (meta for meta in metas if meta["status"] == "superseded"):
        assert date.fromisoformat(old["valid_to"]) < current_start, old["version"]
