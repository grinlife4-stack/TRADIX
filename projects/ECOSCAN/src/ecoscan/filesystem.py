from __future__ import annotations
import os
import stat
import uuid
from datetime import datetime, timezone
from pathlib import Path
from .contracts import AdapterContractError, AdapterResult, ScanContext
from .models import SourceDescriptor

class FilesystemAdapter:
    """Read-only local filesystem metadata adapter. Never opens file contents."""
    adapter_id = "filesystem"
    version = "0.1.0"

    def __init__(self, base_dir: str | Path | None = None) -> None:
        self.base_dir = Path(base_dir or Path.cwd()).expanduser().absolute()

    def _root(self, source: SourceDescriptor) -> Path:
        configured = Path(source.locator).expanduser()
        root = configured if configured.is_absolute() else self.base_dir / configured
        root = root.absolute()
        cursor = root
        while cursor != cursor.parent:
            if cursor.is_symlink():
                raise AdapterContractError("filesystem locator contains a symbolic-link path component")
            cursor = cursor.parent
        try:
            info = root.lstat()
        except OSError as exc:
            raise AdapterContractError("filesystem source is unavailable") from exc
        if not stat.S_ISDIR(info.st_mode):
            raise AdapterContractError("filesystem source must be a real directory")
        return root

    def validate_config(self, source_descriptor: SourceDescriptor) -> None:
        if source_descriptor.source_type != "filesystem":
            raise AdapterContractError("filesystem adapter accepts filesystem sources only")
        self._root(source_descriptor)

    def scan(self, context: ScanContext) -> AdapterResult:
        root = self._root(context.source)
        file_count = byte_count = items = pages = 0
        limitations: set[str] = set()

        def onerror(exc: OSError) -> None:
            limitations.add("DIRECTORY_METADATA_UNAVAILABLE")

        for current, dirs, files in os.walk(root, topdown=True, onerror=onerror, followlinks=False):
            current_path = Path(current)
            safe_dirs = []
            context.guard.consume_page()
            pages += 1
            for name in dirs:
                candidate = current_path / name
                try:
                    if candidate.is_symlink():
                        limitations.add("SYMLINK_DIRECTORY_SKIPPED")
                    else:
                        safe_dirs.append(name)
                except OSError:
                    limitations.add("DIRECTORY_METADATA_UNAVAILABLE")
            dirs[:] = safe_dirs
            for name in files:
                candidate = current_path / name
                try:
                    info = candidate.lstat()
                    if not stat.S_ISREG(info.st_mode):
                        limitations.add("NON_REGULAR_FILE_SKIPPED")
                        continue
                    context.guard.consume_item()
                    items += 1
                    file_count += 1
                    byte_count += info.st_size
                except OSError:
                    limitations.add("FILE_METADATA_UNAVAILABLE")

        state = "PARTIAL" if limitations else "COMPLETE"
        confidence = "MEDIUM" if limitations else "HIGH"
        measured_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        common = {
            "schema_version": "0.1", "project_id": context.project_id,
            "source_id": context.source.source_id, "measured_at": measured_at,
            "source_timestamp": None, "method": "filesystem-lstat",
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
