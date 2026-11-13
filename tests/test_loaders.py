from pathlib import Path

import pytest
import yaml
from openpyxl import Workbook

from helpdesk_rag_chatbot.ingestion.loaders import (
    load_corpus,
    load_document,
    read_metadata,
    read_text,
)

DOCS_DIR = Path(__file__).parents[1] / "data" / "docs"


@pytest.mark.parametrize(
    "file_name",
    ["hr-leave-policy.v1.0.pdf", "it-software-catalogue.v1.0.xlsx"],
    ids=["pdf", "xlsx"],
)
def test_pdf_and_xlsx_metadata_comes_from_sidecar(file_name: str) -> None:
    path = DOCS_DIR / file_name
    sidecar = yaml.safe_load(path.with_suffix(".meta.yaml").read_text(encoding="utf-8"))
    metadata = read_metadata(path)
    assert metadata == sidecar
    assert metadata["file"] == file_name


def test_read_metadata_reads_markdown_front_matter(tmp_path: Path) -> None:
    doc = tmp_path / "x.v1.0.md"
    doc.write_text('---\ndoc_id: x\nversion: "1.0"\n---\n\n# Body\n', encoding="utf-8")
    assert read_metadata(doc) == {"doc_id": "x", "version": "1.0"}


def test_read_metadata_reads_sidecar_next_to_pdf(tmp_path: Path) -> None:
    doc = tmp_path / "x.v1.0.pdf"
    doc.write_bytes(b"%PDF-1.4")
    (tmp_path / "x.v1.0.meta.yaml").write_text(
        'doc_id: x\nversion: "1.0"\n', encoding="utf-8"
    )
    assert read_metadata(doc) == {"doc_id": "x", "version": "1.0"}


def test_read_metadata_missing_sidecar_names_it(tmp_path: Path) -> None:
    doc = tmp_path / "x.v1.0.pdf"
    doc.write_bytes(b"%PDF-1.4")
    with pytest.raises(FileNotFoundError, match=r"x\.v1\.0\.meta\.yaml"):
        read_metadata(doc)


def test_read_text_xlsx_writes_prose_and_labelled_rows(tmp_path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.title = "Catalogue"
    sheet.append(["Costs are per user per year.", None, None])
    sheet.append(["Application", "Version", "Cost"])
    sheet.append(["Outlook", "16.0", 0])
    sheet.append(["Teams", None, 0])
    workbook.create_sheet("Help").append(["Contact the Service Desk."])
    doc = tmp_path / "x.v1.0.xlsx"
    workbook.save(doc)

    assert read_text(doc) == (
        "## Catalogue\n\n"
        "Costs are per user per year.\n\n"
        "Application: Outlook | Version: 16.0 | Cost: 0\n"
        "Application: Teams | Cost: 0\n\n"
        "## Help\n\n"
        "Contact the Service Desk."
    )


def test_xlsx_text_includes_every_sheet() -> None:
    text = read_text(DOCS_DIR / "it-software-catalogue.v1.0.xlsx")
    for sheet in ("Overview", "Catalogue", "How to request", "Temporary admin rights"):
        assert f"## {sheet}" in text
    # Changed on purpose: table rows are labelled with their column headers.
    assert "Application: Outlook | Minimum version: 16.0" in text


def test_read_text_markdown_drops_front_matter() -> None:
    text = read_text(DOCS_DIR / "it-vpn-guide.v1.0.md")
    assert "doc_id:" not in text
    assert text.startswith("# ")


def test_read_text_pdf_drops_page_furniture() -> None:
    text = read_text(DOCS_DIR / "hr-leave-policy.v1.0.pdf")
    assert "Vacation and Leave Policy" in text
    assert "Page 1" not in text
    assert "Corvane Logistics Software ·" not in text


def test_read_text_rejects_unsupported_file_type(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"notes\.docx"):
        read_text(tmp_path / "notes.docx")


@pytest.mark.parametrize(
    ("file_name", "doc_id", "file_type"),
    [
        ("it-vpn-guide.v1.0.md", "it-vpn-guide@1.0", "md"),
        ("hr-leave-policy.v1.0.pdf", "hr-leave-policy@1.0", "pdf"),
        ("it-software-catalogue.v1.0.xlsx", "it-software-catalogue@1.0", "xlsx"),
    ],
    ids=["markdown", "pdf", "xlsx"],
)
def test_load_document_sets_id_source_and_file_type(
    file_name: str, doc_id: str, file_type: str
) -> None:
    document = load_document(DOCS_DIR / file_name)
    assert document.id == doc_id
    assert document.metadata["source"] == file_name
    assert document.metadata["file_type"] == file_type


def test_load_document_keeps_file_metadata() -> None:
    path = DOCS_DIR / "hr-remote-work-policy.v2.0.md"
    document = load_document(path)
    assert read_metadata(path).items() <= document.metadata.items()


def test_load_document_cleans_text() -> None:
    document = load_document(DOCS_DIR / "hr-leave-policy.v1.0.pdf")
    assert document.page_content.startswith("Vacation and Leave Policy")
    assert document.page_content == document.page_content.strip()


def test_load_document_gives_each_version_its_own_id() -> None:
    old = load_document(DOCS_DIR / "hr-remote-work-policy.v1.0.md")
    new = load_document(DOCS_DIR / "hr-remote-work-policy.v2.0.md")
    assert (old.id, new.id) == (
        "hr-remote-work-policy@1.0",
        "hr-remote-work-policy@2.0",
    )


def test_unsupported_suffix_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match=r"x\.docx"):
        load_document(tmp_path / "x.docx")


def test_load_document_gives_every_format_the_same_metadata_keys() -> None:
    keys = {
        name: set(load_document(DOCS_DIR / name).metadata)
        for name in (
            "it-vpn-guide.v1.0.md",
            "hr-leave-policy.v1.0.pdf",
            "it-software-catalogue.v1.0.xlsx",
        )
    }
    assert all("file" not in k for k in keys.values()), keys
    assert len({frozenset(k) for k in keys.values()}) == 1, keys


def test_load_corpus_loads_every_real_document() -> None:
    documents = load_corpus(DOCS_DIR)
    assert len(documents) == 17
    assert {d.metadata["file_type"] for d in documents} == {"md", "pdf", "xlsx"}


def test_load_corpus_skips_unsupported_files_and_subfolders(tmp_path: Path) -> None:
    (tmp_path / "x.v1.0.md").write_text(
        '---\ndoc_id: x\nversion: "1.0"\n---\n\nBody\n', encoding="utf-8"
    )
    (tmp_path / "notes.txt").write_text("not a document", encoding="utf-8")
    nested = tmp_path / "archive"
    nested.mkdir()
    (nested / "y.v1.0.md").write_text(
        '---\ndoc_id: y\nversion: "1.0"\n---\n\nBody\n', encoding="utf-8"
    )
    assert [d.id for d in load_corpus(tmp_path)] == ["x@1.0"]


def test_load_corpus_returns_documents_in_file_name_order() -> None:
    sources = [d.metadata["source"] for d in load_corpus(DOCS_DIR)]
    assert sources == sorted(sources)
