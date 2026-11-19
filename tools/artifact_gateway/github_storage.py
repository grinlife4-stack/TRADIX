"""Small GitHub Contents API adapter for binary artifacts.

Use a dedicated project repository and a non-production artifact branch. Tokens are
read only from the runtime environment and are never included in receipts or logs.
"""
from __future__ import annotations

import base64
import hashlib
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

MAX_GITHUB_UPLOAD_BYTES = 20 * 1024 * 1024


class GitHubTransferError(Exception):
    """A GitHub upload or its verification failed."""


@dataclass(frozen=True)
class GitHubTarget:
    repository: str
    branch: str
    path_prefix: str
    token: str


def upload_binary(path: Path, *, project_id: str, sha256: str, target: GitHubTarget) -> dict:
    size = path.stat().st_size
    if size > MAX_GITHUB_UPLOAD_BYTES:
        raise GitHubTransferError(
            f"GitHub Contents API uploads are capped here at {MAX_GITHUB_UPLOAD_BYTES} bytes"
        )
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", target.repository):
        raise GitHubTransferError("invalid GitHub repository target")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}", project_id):
        raise GitHubTransferError("invalid project namespace")
    prefix = target.path_prefix.strip("/")
    if not prefix or any(
        part in {"", ".", ".."} or not re.fullmatch(r"[A-Za-z0-9_.-]+", part)
        for part in prefix.split("/")
    ):
        raise GitHubTransferError("a safe, non-empty GitHub path prefix is required")
    if not target.branch or target.branch.startswith("-"):
        raise GitHubTransferError("an explicit existing target branch is required")
    if len(target.token) < 20:
        raise GitHubTransferError("GitHub token is missing or invalid")

    file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    if file_hash != sha256:
        raise GitHubTransferError("input file does not match the supplied SHA-256")
    relative_path = f"{prefix}/{project_id}/{sha256[:2]}/{sha256}"
    encoded_path = urllib.parse.quote(relative_path, safe="/")
    api_url = f"https://api.github.com/repos/{target.repository}/contents/{encoded_path}"
    headers = {
        "Authorization": f"Bearer {target.token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "TRADIX-Artifact-Gateway",
    }
    raw_headers = {**headers, "Accept": "application/vnd.github.raw+json"}
    # GitHub Contents API reads default to the repository's default branch unless
    # ref is explicit. Always verify against the exact branch targeted by the PUT.
    readback_url = f"{api_url}?{urllib.parse.urlencode({'ref': target.branch})}"

    try:
        # Content-addressed paths make retries idempotent. Reuse an existing object
        # only after downloading it from the target branch and verifying its SHA-256.
        existing_request = urllib.request.Request(readback_url, headers=raw_headers, method="GET")
        try:
            with urllib.request.urlopen(existing_request, timeout=30) as response:
                existing = response.read()
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            existing = None
        if existing is not None:
            existing_hash = hashlib.sha256(existing).hexdigest()
            if len(existing) != size or existing_hash != sha256:
                raise GitHubTransferError("existing GitHub object failed integrity verification")
            return {
                "repository": target.repository,
                "branch": target.branch,
                "path": relative_path,
                "commit_sha": None,
                "verified_sha256": existing_hash,
                "size_bytes": size,
                "reused_existing": True,
            }

        content = base64.b64encode(path.read_bytes()).decode("ascii")
        payload = json.dumps({
            "message": f"Store project artifact {sha256}",
            "content": content,
            "branch": target.branch,
        }).encode("utf-8")
        request = urllib.request.Request(
            api_url, data=payload, headers={**headers, "Content-Type": "application/json"},
            method="PUT",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
        content_info = result.get("content") or {}
        commit_info = result.get("commit") or {}
        if content_info.get("path") != relative_path or not commit_info.get("sha"):
            raise GitHubTransferError("GitHub did not return the expected path and commit")

        verify_request = urllib.request.Request(readback_url, headers=raw_headers, method="GET")
        with urllib.request.urlopen(verify_request, timeout=30) as response:
            downloaded = response.read()
        verified_hash = hashlib.sha256(downloaded).hexdigest()
        if len(downloaded) != size or verified_hash != sha256:
            raise GitHubTransferError("GitHub read-back verification failed")
        return {
            "repository": target.repository,
            "branch": target.branch,
            "path": relative_path,
            "commit_sha": commit_info["sha"],
            "verified_sha256": verified_hash,
            "size_bytes": size,
            "reused_existing": False,
        }
    except GitHubTransferError:
        raise
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, KeyError) as exc:
        raise GitHubTransferError(f"GitHub transfer failed: {type(exc).__name__}") from exc
