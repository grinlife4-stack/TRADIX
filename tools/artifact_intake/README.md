# TRADIX Artifact Intake MVP

This first slice provides local, dependency-free handling for common file intake tasks:

- Calculate SHA-256 for any file without modifying it.
- Validate and inventory ZIP archives, including CRC checks.
- Safely extract ZIP archives while rejecting traversal paths, symlinks, duplicate names, oversized entries, and suspicious compression ratios.
- Read bounded UTF-8 text files with their SHA-256.

## Requirements

- Python 3.10+
- Python standard library only

## Usage

From the repository root:

```bash
python tools/artifact_intake/artifact_intake.py hash path/to/file.zip
python tools/artifact_intake/artifact_intake.py inspect-zip path/to/file.zip
python tools/artifact_intake/artifact_intake.py extract-zip path/to/file.zip /tmp/extracted
python tools/artifact_intake/artifact_intake.py read-text path/to/README.md
```

Run tests:

```bash
python -m pytest -q tests/test_artifact_intake.py
```

## Safety and current limits

- The source file is never edited.
- Extraction does not overwrite existing files.
- ZIP extraction is bounded by limits defined in `artifact_intake.py`; review those limits before processing unusually large archives.
- Text reading is UTF-8 only and capped at 2 MB.
- PDF, DOCX, XLSX, OCR, remote connectors, cloud storage, and GitHub binary upload are not implemented in this MVP.
- This tool is a local utility, not a service and not a product runtime dependency.
- Do not place credentials or private project artifacts in the public TRADIX repository.

The next stage can add format-specific readers and authenticated transfer adapters behind documented interfaces, while keeping each product's files and permissions separate.
