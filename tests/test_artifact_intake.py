import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.artifact_intake.artifact_intake import (
    ArtifactError,
    extract_zip,
    inspect_zip,
    read_text,
    sha256_file,
)


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


if __name__ == "__main__":
    unittest.main()
