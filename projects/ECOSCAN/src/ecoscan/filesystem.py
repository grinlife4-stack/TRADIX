from __future__ import annotations

import os
import stat
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .contracts import AdapterContractError, AdapterResult, ScanContext
from .models import SourceDescriptor


class FilesystemAdapter:
    """Read-only metadata adapter using descriptor-relative, no-follow traversal."""

    adapter_id = "filesystem"
    version = "0.1.0"

    def __init__(
        self,
        base_dir: str | Path | None = None,
        allowed_root: str | Path | None = None,
    ) -> None:
        self.base_dir = Path(base_dir or Path.cwd()).expanduser().absolute()
        # The allowed root is trusted configuration. All source traversal below it
        # is performed relative to an opened directory descriptor.
        self.allowed_root = Path(allowed_root or self.base_dir).expanduser().resolve()

    def _open_root(self, source: SourceDescriptor) -> int:
        configured = Path(source.locator).expanduser()
        root = Path(os.path.abspath(configured if configured.is_absolute() else self.base_dir / configured))
        try:
            relative = root.relative_to(self.allowed_root)
        except ValueError as exc:
            raise AdapterContractError("filesystem source escapes its configured allowed root") from exc

        required = ("O_DIRECTORY", "O_NOFOLLOW")
        if any(not hasattr(os, name) for name in required) or os.open not in os.supports_dir_fd:
            raise AdapterContractError("platform cannot guarantee no-follow descriptor-relative traversal")

        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        try:
            current_fd = os.open(self.allowed_root, flags)
        except OSError as exc:
            raise AdapterContractError("configured allowed root is unavailable or unsafe") from exc

        try:
            for part in relative.parts:
                if part in ("", "."):
                    continue
                if part == "..":
                    raise AdapterContractError("filesystem locator contains parent traversal")
                next_fd = os.open(part, flags, dir_fd=current_fd)
                os.close(current_fd)
                current_fd = next_fd
            info = os.fstat(current_fd)
            if not stat.S_ISDIR(info.st_mode):
                raise AdapterContractError("filesystem source must be a real directory")
            return current_fd
        except AdapterContractError:
            os.close(current_fd)
            raise
        except OSError as exc:
            os.close(current_fd)
            raise AdapterContractError("filesystem locator is unavailable or contains a symbolic link") from exc

    def validate_config(self, source_descriptor: SourceDescriptor) -> None:
        if source_descriptor.source_type != "filesystem":
            raise AdapterContractError("filesystem adapter accepts filesystem sources only")
        supported = {"logical_bytes", "file_count"}
        if not source_descriptor.expected_measurements or not set(source_descriptor.expected_measurements).issubset(supported):
            raise AdapterContractError("filesystem adapter supports logical_bytes and file_count measurements only")
        if "://" in source_descriptor.locator:
            raise AdapterContractError("filesystem locator must be a local path, not a URL")
        fd = self._open_root(source_descriptor)
        os.close(fd)

    def scan(self, context: ScanContext) -> AdapterResult:
        root_fd = self._open_root(context.source)
        file_count = byte_count = items = pages = 0
        limitations: set[str] = set()

        def onerror(exc: OSError) -> None:
            limitations.add("DIRECTORY_METADATA_UNAVAILABLE")

        try:
            # fwalk + dir_fd keeps traversal anchored to the already-open root.
            for current, dirs, files, current_fd in os.fwalk(
                ".", topdown=True, onerror=onerror, follow_symlinks=False, dir_fd=root_fd
            ):
                context.guard.consume_page()
                pages += 1
                safe_dirs = []
                for name in dirs:
                    try:
                        info = os.stat(name, dir_fd=current_fd, follow_symlinks=False)
                        if stat.S_ISDIR(info.st_mode):
                            safe_dirs.append(name)
                        else:
                            limitations.add("SYMLINK_DIRECTORY_SKIPPED")
                    except OSError:
                        limitations.add("DIRECTORY_METADATA_UNAVAILABLE")
                dirs[:] = safe_dirs

                for name in files:
                    try:
                        info = os.stat(name, dir_fd=current_fd, follow_symlinks=False)
                        if not stat.S_ISREG(info.st_mode):
                            limitations.add("NON_REGULAR_FILE_SKIPPED")
                            continue
                        context.guard.consume_item()
                        items += 1
                        file_count += 1
                        byte_count += info.st_size
                    except OSError:
                        limitations.add("FILE_METADATA_UNAVAILABLE")
        finally:
            os.close(root_fd)

        state = "PARTIAL" if limitations else "COMPLETE"
        confidence = "MEDIUM" if limitations else "HIGH"
        measured_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        common = {
            "schema_version": "0.1", "project_id": context.project_id,
            "source_id": context.source.source_id, "measured_at": measured_at,
            "source_timestamp": None, "method": "filesystem-descriptor-lstat",
            "adapter_id": self.adapter_id, "adapter_version": self.version,
            "coverage_state": state, "confidence": confidence,
            "limitations": sorted(limitations), "evidence_ref": None, "checkpoint_ref": None,
        }
        values = {"logical_bytes": (byte_count, "byte"), "file_count": (file_count, "file")}
        measurements = []
        for kind in context.source.expected_measurements:
            if kind not in values:
                continue
            value, unit = values[kind]
            measurements.append({**common, "measurement_id": str(uuid.uuid4()), "kind": kind, "value": value, "unit": unit})
        return AdapterResult(state, tuple(measurements), items, pages, None, tuple(sorted(limitations)), None)
