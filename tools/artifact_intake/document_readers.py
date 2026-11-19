"""Optional readers for PDF, DOCX and XLSX files.

Install the `documents` extra to enable these readers. Files are read-only;
macros and embedded objects are not executed.
"""
from __future__ import annotations

from pathlib import Path

MAX_DOCUMENT_BYTES = 50 * 1024 * 1024
MAX_EXTRACTED_CHARS = 2_000_000
MAX_PDF_PAGES = 5_000
MAX_XLSX_CELLS = 100_000


class DocumentReadError(Exception):
    """Raised when a document cannot be safely or reliably extracted."""


def _check_file(path: Path) -> None:
    if not path.is_file():
        raise DocumentReadError("document path is not a regular file")
    if path.stat().st_size > MAX_DOCUMENT_BYTES:
        raise DocumentReadError(f"document exceeds {MAX_DOCUMENT_BYTES} byte limit")


def _bounded(text: str) -> str:
    if len(text) > MAX_EXTRACTED_CHARS:
        raise DocumentReadError(
            f"extracted text exceeds {MAX_EXTRACTED_CHARS} character limit"
        )
    return text


def read_pdf(path: Path) -> dict:
    _check_file(path)
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise DocumentReadError(
            "PDF support is optional; install TRADIX with the 'documents' extra"
        ) from exc
    try:
        reader = PdfReader(str(path), strict=True)
        if reader.is_encrypted:
            raise DocumentReadError("encrypted PDFs are not supported")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise DocumentReadError(f"PDF exceeds {MAX_PDF_PAGES} page limit")
        pages = []
        total = 0
        for index, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            total += len(text)
            if total > MAX_EXTRACTED_CHARS:
                raise DocumentReadError(
                    f"extracted text exceeds {MAX_EXTRACTED_CHARS} character limit"
                )
            pages.append({"page": index, "text": text})
        return {"format": "pdf", "page_count": len(pages), "pages": pages}
    except DocumentReadError:
        raise
    except Exception as exc:
        raise DocumentReadError(f"PDF extraction failed: {exc}") from exc


def read_docx(path: Path) -> dict:
    _check_file(path)
    try:
        from docx import Document
    except ImportError as exc:
        raise DocumentReadError(
            "DOCX support is optional; install TRADIX with the 'documents' extra"
        ) from exc
    try:
        document = Document(str(path))
        parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text]
        for table_index, table in enumerate(document.tables, start=1):
            parts.append(f"[Table {table_index}]")
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        text = _bounded("\n".join(parts))
        return {"format": "docx", "paragraph_count": len(document.paragraphs),
                "table_count": len(document.tables), "text": text}
    except DocumentReadError:
        raise
    except Exception as exc:
        raise DocumentReadError(f"DOCX extraction failed: {exc}") from exc


def read_xlsx(path: Path) -> dict:
    _check_file(path)
    try:
        from openpyxl import load_workbook
    except ImportError as exc:
        raise DocumentReadError(
            "XLSX support is optional; install TRADIX with the 'documents' extra"
        ) from exc
    workbook = None
    try:
        workbook = load_workbook(
            filename=str(path), read_only=True, data_only=True, keep_links=False
        )
        sheets = []
        cell_count = 0
        for worksheet in workbook.worksheets:
            rows = []
            for row in worksheet.iter_rows(values_only=True):
                values = ["" if value is None else str(value) for value in row]
                cell_count += len(values)
                if cell_count > MAX_XLSX_CELLS:
                    raise DocumentReadError(
                        f"workbook exceeds {MAX_XLSX_CELLS} cell limit"
                    )
                if any(values):
                    rows.append(values)
            sheets.append({"name": worksheet.title, "rows": rows})
        return {"format": "xlsx", "sheet_count": len(sheets), "sheets": sheets}
    except DocumentReadError:
        raise
    except Exception as exc:
        raise DocumentReadError(f"XLSX extraction failed: {exc}") from exc
    finally:
        if workbook is not None:
            workbook.close()


def read_document(path: Path) -> dict:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return read_pdf(path)
    if suffix == ".docx":
        return read_docx(path)
    if suffix == ".xlsx":
        return read_xlsx(path)
    raise DocumentReadError(
        f"unsupported document type: {suffix or '(no extension)'}; supported: .pdf, .docx, .xlsx"
    )
