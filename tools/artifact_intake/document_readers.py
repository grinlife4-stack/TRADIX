"""Optional readers for PDF, DOCX and XLSX files.

Install the `documents` extra to enable these readers. Files are read-only;
macros and embedded objects are not executed. Office ZIP containers are
preflighted before a document parser is allowed to open them.
"""
from __future__ import annotations

import struct
import zipfile
from pathlib import Path

MAX_DOCUMENT_BYTES = 50 * 1024 * 1024
MAX_EXTRACTED_CHARS = 2_000_000
MAX_PDF_PAGES = 5_000
MAX_XLSX_CELLS = 100_000

# DOCX/XLSX are ZIP containers. Bound both their directory metadata and the
# expansion work a parser could trigger before handing the file to a library.
MAX_OFFICE_ZIP_ENTRIES = 4_096
MAX_OFFICE_ZIP_CENTRAL_DIRECTORY_BYTES = 4 * 1024 * 1024
MAX_OFFICE_ZIP_UNCOMPRESSED_BYTES = 64 * 1024 * 1024
MAX_OFFICE_ZIP_MEMBER_BYTES = 32 * 1024 * 1024
MAX_OFFICE_ZIP_COMPRESSION_RATIO = 100


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


def _preflight_office_zip(path: Path) -> None:
    """Reject oversized or pathological Office ZIP containers before parsing."""
    try:
        file_size = path.stat().st_size
        tail_size = min(file_size, 22 + 65_535)
        with path.open("rb") as source:
            source.seek(file_size - tail_size)
            tail = source.read(tail_size)

        eocd_offset = tail.rfind(b"PK\x05\x06")
        if eocd_offset < 0 or eocd_offset + 22 > len(tail):
            raise DocumentReadError("Office document has no valid ZIP directory record")

        (
            signature,
            disk_number,
            directory_disk,
            entries_on_disk,
            entry_count,
            directory_size,
            directory_offset,
            comment_length,
        ) = struct.unpack_from("<4s4H2LH", tail, eocd_offset)

        if signature != b"PK\x05\x06":
            raise DocumentReadError("Office document has an invalid ZIP directory record")
        if eocd_offset + 22 + comment_length != len(tail):
            raise DocumentReadError("Office document has an invalid ZIP comment length")
        if disk_number != 0 or directory_disk != 0 or entries_on_disk != entry_count:
            raise DocumentReadError("multi-disk Office ZIP documents are not supported")
        if (
            entry_count == 0xFFFF
            or directory_size == 0xFFFFFFFF
            or directory_offset == 0xFFFFFFFF
        ):
            raise DocumentReadError("ZIP64 Office documents are not supported by bounded readers")
        if entry_count > MAX_OFFICE_ZIP_ENTRIES:
            raise DocumentReadError(
                f"Office document exceeds {MAX_OFFICE_ZIP_ENTRIES} ZIP member limit"
            )
        if directory_size > MAX_OFFICE_ZIP_CENTRAL_DIRECTORY_BYTES:
            raise DocumentReadError(
                "Office document ZIP directory exceeds "
                f"{MAX_OFFICE_ZIP_CENTRAL_DIRECTORY_BYTES} byte limit"
            )
        absolute_eocd = file_size - tail_size + eocd_offset
        if directory_offset + directory_size > absolute_eocd:
            raise DocumentReadError("Office document ZIP directory is out of bounds")

        with zipfile.ZipFile(path, "r") as archive:
            members = archive.infolist()
            if len(members) != entry_count:
                raise DocumentReadError("Office document ZIP member count is inconsistent")
            seen_names: set[str] = set()
            total_uncompressed = 0
            for member in members:
                if member.filename in seen_names:
                    raise DocumentReadError("Office document contains duplicate ZIP member names")
                seen_names.add(member.filename)
                if member.flag_bits & 0x1:
                    raise DocumentReadError("encrypted Office ZIP members are not supported")
                if member.file_size > MAX_OFFICE_ZIP_MEMBER_BYTES:
                    raise DocumentReadError(
                        f"Office ZIP member exceeds {MAX_OFFICE_ZIP_MEMBER_BYTES} byte limit"
                    )
                total_uncompressed += member.file_size
                if total_uncompressed > MAX_OFFICE_ZIP_UNCOMPRESSED_BYTES:
                    raise DocumentReadError(
                        "Office document exceeds "
                        f"{MAX_OFFICE_ZIP_UNCOMPRESSED_BYTES} total uncompressed byte limit"
                    )
                if member.file_size:
                    if member.compress_size == 0:
                        raise DocumentReadError("Office ZIP member has an invalid compression size")
                    ratio = member.file_size / member.compress_size
                    if ratio > MAX_OFFICE_ZIP_COMPRESSION_RATIO:
                        raise DocumentReadError(
                            "Office ZIP member exceeds "
                            f"{MAX_OFFICE_ZIP_COMPRESSION_RATIO}:1 compression ratio limit"
                        )
    except DocumentReadError:
        raise
    except (OSError, zipfile.BadZipFile, struct.error, ValueError) as exc:
        raise DocumentReadError(f"Office document ZIP preflight failed: {type(exc).__name__}") from exc


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
    _preflight_office_zip(path)
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
        text = _bounded("\\n".join(parts))
        return {"format": "docx", "paragraph_count": len(document.paragraphs),
                "table_count": len(document.tables), "text": text}
    except DocumentReadError:
        raise
    except Exception as exc:
        raise DocumentReadError(f"DOCX extraction failed: {exc}") from exc


def read_xlsx(path: Path) -> dict:
    _check_file(path)
    _preflight_office_zip(path)
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
        extracted_chars = 0
        for worksheet in workbook.worksheets:
            rows = []
            for row in worksheet.iter_rows(values_only=True):
                values = ["" if value is None else str(value) for value in row]
                cell_count += len(values)
                extracted_chars += sum(len(value) for value in values)
                if cell_count > MAX_XLSX_CELLS:
                    raise DocumentReadError(
                        f"workbook exceeds {MAX_XLSX_CELLS} cell limit"
                    )
                if extracted_chars > MAX_EXTRACTED_CHARS:
                    raise DocumentReadError(
                        f"extracted text exceeds {MAX_EXTRACTED_CHARS} character limit"
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
