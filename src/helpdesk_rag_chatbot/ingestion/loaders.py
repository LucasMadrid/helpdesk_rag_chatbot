from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

import frontmatter
import yaml
from langchain_core.documents import Document
from openpyxl import load_workbook
from pypdf import PdfReader

from helpdesk_rag_chatbot.ingestion.cleaning import clean_text, remove_page_furniture


def _read_markdown(path: Path) -> str:
    """
    Return the body of a Markdown document, without its front matter.

    The ``---`` block at the top holds metadata (see ``read_metadata``), not
    policy text, so it is left out of what gets chunked and embedded.

    :param path: The Markdown file.
    :return: The text after the front-matter block.
    """
    return frontmatter.load(path).content


def _read_pdf(path: Path) -> str:
    """
    Extract the text of a PDF, without its running headers and page numbers.

    Pages are joined with a blank line, so a page break reads like a paragraph
    break. Whitespace is left for ``clean_text`` to normalise.

    :param path: The PDF file.
    :return: The text of every page, in order.
    """
    pages = [page.extract_text() for page in PdfReader(path).pages]
    pages = remove_page_furniture(pages)

    return "\n\n".join(pages)


def _read_xlsx(path: Path) -> str:
    """
    Turn every sheet of a workbook into text, one section per sheet.

    Each sheet starts with a ``## <sheet name>`` heading. Formulas are read as
    their last calculated value. See ``_sheet_to_text`` for how rows become text.

    :param path: The XLSX file.
    :return: The text of every sheet, in workbook order.
    """
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        sections = [
            _sheet_to_text(sheet.title, sheet.iter_rows(values_only=True))
            for sheet in workbook.worksheets
        ]
    finally:
        workbook.close()  # read-only mode keeps the file open until closed
    return "\n\n".join(sections)


def _sheet_to_text(title: str, rows: Iterable[tuple[Any, ...]]) -> str:
    """
    Turn the rows of one sheet into prose paragraphs and labelled table rows.

    Empty cells are ignored. A row with one value is prose and becomes its own
    paragraph. The first row with two or more values is the table header. Each
    later row with two or more values is written as
    ``Header: value | Header: value``, so a row still makes sense when it ends
    up in a chunk without the header.

    :param title: The sheet name, used as the section heading.
    :param rows: The sheet's rows as tuples of cell values.
    :return: The sheet as text, with blocks separated by blank lines.
    """
    blocks = [f"## {title}"]
    header: list[str] | None = None
    table: list[str] = []

    for row in rows:
        cells = ["" if value is None else str(value).strip() for value in row]
        filled = [cell for cell in cells if cell]
        if not filled:
            continue
        if len(filled) == 1:
            if table:
                blocks.append("\n".join(table))
                table = []
            blocks.append(filled[0])
        elif header is None:
            header = cells
        else:
            pairs = [
                f"{name}: {cell}" if name else cell
                for name, cell in zip(header, cells, strict=False)
                if cell
            ]
            table.append(" | ".join(pairs))

    if table:
        blocks.append("\n".join(table))
    return "\n\n".join(blocks)


READERS: dict[str, Callable[[Path], str]] = {
    ".md": _read_markdown,
    ".pdf": _read_pdf,
    ".xlsx": _read_xlsx,
}
SUPPORTED_SUFFIXES = tuple(READERS)


def read_text(path: Path) -> str:
    """
    Extract a document's raw text with the reader for its file type.

    The text is not cleaned here; ``load_document`` runs ``clean_text`` once on
    the result, so every format is normalised the same way.

    :param path: A ``.md``, ``.pdf`` or ``.xlsx`` document.
    :return: The extracted text, before cleaning.
    :raises ValueError: If the file type is not one of ``SUPPORTED_SUFFIXES``.
    """
    reader = READERS.get(path.suffix)
    if reader is None:
        raise ValueError(f"unsupported file type: {path.name}")
    return reader(path)


def read_metadata(path: Path) -> dict[str, Any]:
    """
    Read a document's metadata from its front matter or its sidecar.

    Markdown files carry a ``---`` front-matter block. PDF and XLSX files can't,
    so their metadata sits next to them in ``<name>.meta.yaml``.

    :param path: The document file.
    :return: The metadata as a dict.
    :raises FileNotFoundError: If a PDF or XLSX has no sidecar; the message
        names the sidecar path.
    """

    if path.suffix == ".md":
        return frontmatter.load(path).metadata

    sidecar = path.with_suffix(".meta.yaml")
    if not sidecar.is_file():
        raise FileNotFoundError(f"{path.name} needs a metadata sidecar at {sidecar}")

    metadata: dict[str, Any] = yaml.safe_load(sidecar.read_text(encoding="utf-8"))
    return metadata


def load_document(path: Path) -> Document:
    """
    Load one corpus file as a LangChain ``Document`` ready for chunking.

    The text comes from the reader for the file's type and is then cleaned.
    The id is ``<doc_id>@<version>``, so two versions of the same policy never
    collide. The metadata is the file's own metadata plus ``source`` (the file
    name) and ``file_type`` (the suffix without its dot, e.g. ``pdf``). A
    sidecar's ``file`` key is dropped, since ``source`` already names the
    file, so every format ends up with the same keys.

    :param path: A ``.md``, ``.pdf`` or ``.xlsx`` document.
    :return: The document with cleaned text, id and metadata.
    :raises ValueError: If the file type is not supported.
    :raises FileNotFoundError: If a PDF or XLSX has no metadata sidecar.
    """
    if path.suffix not in SUPPORTED_SUFFIXES:
        raise ValueError(f"unsupported file type: {path.name}")

    metadata = read_metadata(path)
    metadata.pop("file", None)  # a sidecar's pointer to its file; same as source
    text = clean_text(read_text(path))

    return Document(
        id=f"{metadata['doc_id']}@{metadata['version']}",
        page_content=text,
        metadata={
            **metadata,
            "source": path.name,
            "file_type": path.suffix.lstrip("."),
        },
    )


def load_corpus(docs_dir: Path) -> list[Document]:
    """
    Load every supported document in a folder, in file-name order.

    Sidecars (``.meta.yaml``) and other unsupported files are skipped, and
    sub-folders are not searched.

    :param docs_dir: The corpus folder, e.g. ``data/docs``.
    :return: One ``Document`` per supported file, sorted by file name.
    """

    filtered_paths = sorted(
        path
        for path in docs_dir.iterdir()
        if path.is_file() and path.suffix in SUPPORTED_SUFFIXES
    )
    return [load_document(path) for path in filtered_paths]
