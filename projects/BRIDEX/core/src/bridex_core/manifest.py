"""Strict validation for independently owned Bridge project manifests."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_BRIDGE_ID = re.compile(r"^[a-z][a-z0-9-]{2,62}$")
_SLUG = re.compile(r"^[a-z][a-z0-9-]{1,62}$")
_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_ALLOWED_ROOT = {
    "format_version", "bridge_id", "name", "version", "owner", "operator",
    "maintainer", "protocols", "peers", "capabilities", "lifecycle",
}
_ALLOWED_ROLE = {"id", "assignment_ref"}


class ManifestError(ValueError):
    """A Bridge manifest is incomplete, ambiguous, or unsafe."""


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{field}_required")
    return value.strip()


def validate_manifest(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ManifestError("manifest_must_be_object")
    if set(data) - _ALLOWED_ROOT:
        raise ManifestError("unknown_manifest_fields")
    missing = (_ALLOWED_ROOT - {"maintainer"}) - set(data)
    if missing:
        raise ManifestError("missing_manifest_fields")
    if data["format_version"] != "1":
        raise ManifestError("unsupported_manifest_format")
    if not _BRIDGE_ID.fullmatch(_nonempty(data["bridge_id"], "bridge_id")):
        raise ManifestError("invalid_bridge_id")
    _nonempty(data["name"], "name")
    if not isinstance(data["version"], str) or not _VERSION.fullmatch(data["version"]):
        raise ManifestError("invalid_semver")

    for role in ("owner", "operator", "maintainer"):
        value = data.get(role)
        if role == "maintainer" and value is None:
            continue
        if not isinstance(value, dict) or set(value) != _ALLOWED_ROLE:
            raise ManifestError(f"{role}_assignment_evidence_required")
        if not _SLUG.fullmatch(_nonempty(value["id"], f"{role}_id")):
            raise ManifestError(f"{role}_id_invalid")
        _nonempty(value["assignment_ref"], f"{role}_assignment_ref")

    if data["protocols"] != {"obis": "0.1"}:
        raise ManifestError("obis_0_1_protocol_required")
    if not isinstance(data["peers"], list):
        raise ManifestError("peers_must_be_list")
    for peer in data["peers"]:
        if not isinstance(peer, dict) or set(peer) != {"peer_id", "trust_ref", "enabled"}:
            raise ManifestError("peer_record_invalid")
        if not _SLUG.fullmatch(_nonempty(peer["peer_id"], "peer_id")):
            raise ManifestError("peer_id_invalid")
        _nonempty(peer["trust_ref"], "peer_trust_ref")
        if peer["enabled"] is not False:
            raise ManifestError("new_peers_must_start_disabled")

    if not isinstance(data["capabilities"], list):
        raise ManifestError("capabilities_must_be_list")
    for item in data["capabilities"]:
        if not isinstance(item, dict) or set(item) != {"capability_id", "version", "required_scopes", "enabled"}:
            raise ManifestError("capability_record_invalid")
        _nonempty(item["capability_id"], "capability_id")
        if not isinstance(item["version"], str) or not _VERSION.fullmatch(item["version"]):
            raise ManifestError("capability_version_invalid")
        scopes = item["required_scopes"]
        if not isinstance(scopes, list) or not scopes or not all(isinstance(s, str) and s.strip() for s in scopes):
            raise ManifestError("capability_scopes_required")
        if item["enabled"] is not False:
            raise ManifestError("new_capabilities_must_start_disabled")
    if data["lifecycle"] != "draft":
        raise ManifestError("generated_bridge_must_start_draft")
    return data


def load_manifest(project_dir: str | Path) -> dict[str, Any]:
    try:
        data = json.loads((Path(project_dir) / "bridex.json").read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ManifestError("bridex_manifest_not_found") from exc
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError("bridex_manifest_invalid_json") from exc
    return validate_manifest(data)
