"""Create portable Bridge project skeletons without runtime service dependencies."""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
from pathlib import Path

from .manifest import validate_manifest


def _slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not result or not result[0].isalpha():
        raise ValueError("name_must_produce_slug")
    return result[:63].rstrip("-")


def create_bridge_project(
    destination: str | Path,
    *,
    bridge_id: str,
    name: str,
    owner_id: str,
    owner_assignment_ref: str,
    operator_id: str,
    operator_assignment_ref: str,
    version: str = "0.1.0",
) -> Path:
    target = Path(destination).expanduser().resolve()
    if target.exists():
        raise FileExistsError("destination_must_not_exist")
    if target == target.parent:
        raise ValueError("unsafe_destination")
    module_name = _slug(name).replace("-", "_")
    manifest = validate_manifest({
        "format_version": "1",
        "bridge_id": bridge_id,
        "name": name,
        "version": version,
        "owner": {"id": owner_id, "assignment_ref": owner_assignment_ref},
        "operator": {"id": operator_id, "assignment_ref": operator_assignment_ref},
        "maintainer": None,
        "protocols": {"obis": "0.1"},
        "peers": [],
        "capabilities": [],
        "lifecycle": "draft",
    })
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".bridex-", dir=parent))
    try:
        (staging / "config").mkdir()
        (staging / "src" / module_name).mkdir(parents=True)
        template_root = Path(__file__).parent / "templates" / "obis_bridge"
        shutil.copytree(template_root, staging / "src" / "obis_bridge")
        (staging / "tests").mkdir()
        (staging / "bridex.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        (staging / "pyproject.toml").write_text(
            f"[build-system]\\nrequires = [\"setuptools>=68\"]\\nbuild-backend = \"setuptools.build_meta\"\\n\\n"
            f"[project]\\nname = \"bridge-{module_name}\"\\nversion = \"{version}\"\\n"
            "requires-python = \">=3.11\"\\n"
            "[tool.setuptools.packages.find]\\nwhere = [\"src\"]\\n\\n"
            "[tool.setuptools.package-data]\\nobis_bridge = [\"schemas/*.json\"]\\n",
            encoding="utf-8",
        )
        (staging / "README.md").write_text(
            f"# {name}\n\nIndependent Bridge project {bridge_id}.\n\n"
            "This generated project is draft-only. No peer is trusted and no capability is enabled.\n\n"
            "The designated owner controls source, configuration, credentials, runtime, records, and release. "
            "The operator is separately recorded. This project has no BRIDEX or TRADIX runtime dependency.\n",
            encoding="utf-8",
        )
        (staging / "config" / "bridge.example.json").write_text(
            json.dumps({"peers": [], "enabled_capabilities": []}, indent=2) + "\n",
            encoding="utf-8",
        )
        (staging / "src" / module_name / "__init__.py").write_text(
            '"""Bridge-specific implementation belongs to this independently owned package."""\n',
            encoding="utf-8",
        )
        (staging / "tests" / "test_bridge_contract.py").write_text(
            "def test_generated_bridge_starts_with_no_enabled_peers_or_capabilities():\n"
            "    import json\n"
            "    from pathlib import Path\n"
            "    root = Path(__file__).parents[1]\n"
            "    manifest = json.loads((root / \"bridex.json\").read_text())\n"
            "    assert manifest[\"peers\"] == []\n"
            "    assert manifest[\"capabilities\"] == []\n"
            "    assert manifest[\"lifecycle\"] == \"draft\"\n",
            encoding="utf-8",
        )
        os.replace(staging, target)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return target
