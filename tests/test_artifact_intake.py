import tempfile
import unittest
import zipfile
from pathlib import Path

from docx import Document
from openpyxl import Workbook
from pypdf import PdfWriter

from tools.artifact_intake.artifact_intake import (
    ArtifactError,
    extract_zip,
    inspect_zip,
    read_text,
    sha256_file,
)
from tools.artifact_intake.document_readers import DocumentReadError, read_document


class ArtifactIntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_hash_and_text_read(self):
        source = self.root / "note.txt"
        source.write_text("TRADIX", encoding="utf-8")
        self.assertEqual(len(sha256_file(source)), 64)
        self.assertEqual(read_text(source)["content"], "TRADIX")

    def test_inspect_and_extract_zip(self):
        archive = self.root / "sample.zip"
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("docs/readme.txt", "hello")
        report = inspect_zip(archive)
        self.assertTrue(report["valid"])
        result = extract_zip(archive, self.root / "out")
        self.assertEqual(result["extracted_files"], 1)
        self.assertEqual((self.root / "out/docs/readme.txt").read_text(), "hello")

    def test_reject_path_traversal(self):
        archive = self.root / "unsafe.zip"
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("../escape.txt", "not safe")
        with self.assertRaises(ArtifactError):
            inspect_zip(archive)

    def test_extraction_does_not_overwrite(self):
        archive = self.root / "sample.zip"
        with zipfile.ZipFile(archive, "w") as output:
            output.writestr("note.txt", "new")
        destination = self.root / "out"
        destination.mkdir()
        (destination / "note.txt").write_text("existing")
        with self.assertRaises(FileExistsError):
            extract_zip(archive, destination)
        self.assertEqual((destination / "note.txt").read_text(), "existing")

    def test_read_docx_text_and_table(self):
        path = self.root / "sample.docx"
        document = Document()
        document.add_paragraph("Document body")
        table = document.add_table(rows=1, cols=2)
        table.cell(0, 0).text = "left"
        table.cell(0, 1).text = "right"
        document.save(path)
        result = read_document(path)
        self.assertEqual(result["format"], "docx")
        self.assertIn("Document body", result["text"])
        self.assertIn("left | right", result["text"])

    def test_read_xlsx_values(self):
        path = self.root / "sample.xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Ledger"
        sheet.append(["Item", "Amount"])
        sheet.append(["A", 125])
        workbook.save(path)
        result = read_document(path)
        self.assertEqual(result["format"], "xlsx")
        self.assertEqual(result["sheets"][0]["name"], "Ledger")
        self.assertEqual(result["sheets"][0]["rows"][1], ["A", "125"])

    def test_read_pdf_page_count(self):
        path = self.root / "sample.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=300, height=300)
        with path.open("wb") as output:
            writer.write(output)
        result = read_document(path)
        self.assertEqual(result["format"], "pdf")
        self.assertEqual(result["page_count"], 1)

    def test_reject_unsupported_document_type(self):
        path = self.root / "sample.doc"
        path.write_text("legacy format")
        with self.assertRaises(DocumentReadError):
            read_document(path)


    def test_docx_and_xlsx_reject_high_compression_ratio_before_parser(self):
        for suffix in (".docx", ".xlsx"):
            with self.subTest(suffix=suffix):
                path = self.root / f"compressed{suffix}"
                with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                    archive.writestr("payload.xml", b"A" * 200_000)
                with self.assertRaisesRegex(DocumentReadError, "compression ratio"):
                    read_document(path)

    def test_office_preflight_rejects_excessive_member_count(self):
        from unittest.mock import patch
        from tools.artifact_intake import document_readers

        path = self.root / "many.docx"
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("one.xml", "1")
            archive.writestr("two.xml", "2")
        with patch.object(document_readers, "MAX_OFFICE_ZIP_ENTRIES", 1):
            with self.assertRaisesRegex(DocumentReadError, "member limit"):
                read_document(path)

    def test_office_preflight_rejects_total_uncompressed_size(self):
        from unittest.mock import patch
        from tools.artifact_intake import document_readers

        path = self.root / "expanded.xlsx"
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as archive:
            archive.writestr("payload.xml", b"x" * 2048)
        with patch.object(document_readers, "MAX_OFFICE_ZIP_UNCOMPRESSED_BYTES", 1024):
            with self.assertRaisesRegex(DocumentReadError, "total uncompressed byte limit"):
                read_document(path)

    def test_xlsx_rejects_extracted_text_over_limit(self):
        from unittest.mock import patch
        from tools.artifact_intake import document_readers

        path = self.root / "long-cell.xlsx"
        workbook = Workbook()
        workbook.active["A1"] = "four"
        workbook.save(path)
        with patch.object(document_readers, "MAX_EXTRACTED_CHARS", 3):
            with self.assertRaisesRegex(DocumentReadError, "extracted text"):
                read_document(path)



if __name__ == "__main__":
    unittest.main()
