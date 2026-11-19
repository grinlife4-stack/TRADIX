#!/usr/bin/env python3
"""TRADIX Artifact Intake MVP: hash, inspect, safely extract ZIP, read UTF-8 text.

This is a local utility, not a remote upload service. It never modifies the source
artifact. Extraction refuses traversal paths, symlinks, duplicate output files,
and archives that exceed configured safety limits.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath

MAX_ENTRIES = 10_000
MAX_TOTAL_BYTES = 1_000_000_000
MAX_MEMBER_BYTES = 250_000_000
MAX_RATIO = 200
MAX_TEXT_BYTES = 2_000_000


class ArtifactError(Exception):
    """An artifact is invalid or exceeds a safety limit."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_member(info: zipfile.ZipInfo) -> None:
    name = info.filename
    member = PurePosixPath(name)
    mode = info.external_attr >> 16
    if not name or member.is_absolute() or "\\" in name:
        raise ArtifactError(f"unsafe archive path: {name!r}")
    if any(part in ("", ".", "..") for part in member.parts):
        raise ArtifactError(f"unsafe archive path: {name!r}")
    if member.parts and ":" in member.parts[0]:
        raise ArtifactError(f"unsafe archive path: {name!r}")
    if stat.S_ISLNK(mode):
        raise ArtifactError(f"symbolic link is not allowed: {name!r}")
    if info.file_size > MAX_MEMBER_BYTES:
        raise ArtifactError(f"archive member exceeds size limit: {name!r}")
    if info.file_size and info.compress_size == 0:
        raise ArtifactError(f"invalid compression metadata: {name!r}")
    if info.compress_size and info.file_size / info.compress_size > MAX_RATIO:
        raise ArtifactError(f"compression ratio limit exceeded: {name!r}")


def inspect_zip(path: Path) -> dict:
    if not zipfile.is_zipfile(path):
        raise ArtifactError("not a valid ZIP archive")
    with zipfile.ZipFile(path) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_ENTRIES:
            raise ArtifactError("archive contains too many entries")
        total = 0
        seen = set()
        for info in entries:
            validate_member(info)
            if info.filename in seen:
                raise ArtifactError(f"duplicate archive path: {info.filename!r}")
            seen.add(info.filename)
            total += info.file_size
            if total > MAX_TOTAL_BYTES:
                raise ArtifactError("archive exceeds total uncompressed size limit")
        corrupt = archive.testzip()
        if corrupt is not None:
            raise ArtifactError(f"CRC validation failed: {corrupt}")
        return {
            "path": str(path),
            "sha256": sha256_file(path),
            "valid": True,
            "entry_count": len(entries),
            "uncompressed_bytes": total,
            "entries": [
                {"name": item.filename, "bytes": item.file_size, "directory": item.is_dir()}
                for item in entries
            ],
        }


def extract_zip(path: Path, destination: Path) -> dict:
    report = inspect_zip(path)
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path) as archive:
        for info in archive.infolist():
            validate_member(info)
            target = (destination / Path(*PurePosixPath(info.filename).parts)).resolve()
            if target != destination and destination not in target.parents:
                raise ArtifactError(f"archive path escapes destination: {info.filename!r}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation prevents silent overwrites of existing files.
            with archive.open(info) as source, target.open("xb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
    return {
        "archive_sha256": report["sha256"],
        "destination": str(destination),
        "extracted_files": sum(not item["directory"] for item in report["entries"]),
    }


def read_text(path: Path) -> dict:
    size = path.stat().st_size
    if size > MAX_TEXT_BYTES:
        raise ArtifactError(f"text read limited to {MAX_TEXT_BYTES} bytes")
    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ArtifactError("file is not valid UTF-8 text") from exc
    return {"path": str(path), "bytes": size, "sha256": sha256_file(path), "content": content}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="TRADIX artifact intake MVP")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("hash", "inspect-zip", "read-text"):
        command = commands.add_parser(name)
        command.add_argument("path", type=Path)
    extract = commands.add_parser("extract-zip")
    extract.add_argument("path", type=Path)
    extract.add_argument("destination", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "hash":
            result = {"path": str(args.path), "sha256": sha256_file(args.path)}
        elif args.command == "inspect-zip":
            result = inspect_zip(args.path)
        elif args.command == "extract-zip":
            result = extract_zip(args.path, args.destination)
        else:
            result = read_text(args.path)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, zipfile.BadZipFile, ArtifactError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
