"""Deterministic, allowlisted export of an independently deployable Bridge project."""

from __future__ import annotations

import hashlib
import os
import stat
import zipfile
from pathlib import Path, PurePosixPath

from .manifest import load_manifest

_PACKAGE_FILES = ("bridex.json", "README.md", "config/bridge.example.json")


class PackageError(ValueError):
    """The Bridge project cannot be safely exported."""


def package_bridge(project_dir: str | Path, output: str | Path) -> tuple[Path, str]:
    root = Path(project_dir).resolve(strict=True)
    manifest = load_manifest(root)
    destination = Path(output).expanduser().resolve()
    if destination == root or root in destination.parents:
        raise PackageError("package_output_must_be_outside_project")
    if destination.exists() and destination.is_dir():
        raise PackageError("package_output_must_be_file")

    files = list(_PACKAGE_FILES)
    for folder in ("src", "tests"):
        base = root / folder
        if base.exists():
            for item in sorted(base.rglob("*")):
                if item.is_symlink():
                    raise PackageError("symlink_not_allowed")
                if item.is_file():
                    files.append(item.relative_to(root).as_posix())

    entries: list[tuple[str, bytes]] = []
    for relative in sorted(set(files)):
        posix = PurePosixPath(relative)
        if posix.is_absolute() or ".." in posix.parts or relative.startswith("."):
            raise PackageError("unsafe_package_path")
        path = root.joinpath(*posix.parts)
        if path.is_symlink() or not path.is_file():
            raise PackageError(f"required_package_file_missing:{relative}")
        if not stat.S_ISREG(path.stat().st_mode):
            raise PackageError("non_regular_file")
        if path.name.lower() in {".env", "secrets.json", "credentials.json", "id_rsa", "id_ed25519"}:
            raise PackageError("secret_file_not_allowed")
        entries.append((relative, path.read_bytes()))

    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(destination.name + ".tmp")
    try:
        with zipfile.ZipFile(temp, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for name, content in entries:
                info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
                info.external_attr = 0o100644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, content)
        os.replace(temp, destination)
    finally:
        if temp.exists():
            temp.unlink()
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    return destination, digest
