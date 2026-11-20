from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API_ROOT = "https://api.github.com"
USER_AGENT = "TRADIX-Portfolio-Storage-Monitor/0.1"
SUCCESS_STATUSES = {"COMPLETE", "EMPTY"}
_REQUEST_CACHE: dict[str, tuple[dict[str, Any], dict[str, str]]] = {}


class ScanError(Exception):
    def __init__(self, status: str, message: str):
        super().__init__(message)
        self.status = status


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _json_request(url: str, token: str | None = None) -> tuple[dict[str, Any], dict[str, str]]:
    if url in _REQUEST_CACHE:
        return _REQUEST_CACHE[url]
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": USER_AGENT,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            payload = json.loads(response.read().decode("utf-8"))
            result = (payload, {k.lower(): v for k, v in response.headers.items()})
            _REQUEST_CACHE[url] = result
            return result
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 409 and "empty" in body.lower():
            raise ScanError("EMPTY", "GitHub repository has no commits or Git tree yet") from exc
        if exc.code == 403 and (exc.headers.get("X-RateLimit-Remaining") == "0" or "rate limit" in body.lower()):
            raise ScanError("RATE_LIMITED", "GitHub API rate limit reached") from exc
        if exc.code in (401, 403, 404):
            raise ScanError("NOT_AUTHORIZED_OR_NOT_FOUND", f"GitHub returned HTTP {exc.code}; check repository visibility and read permissions") from exc
        raise ScanError("FAILED", f"GitHub returned HTTP {exc.code}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise ScanError("FAILED", f"GitHub request failed: {exc}") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ScanError("FAILED", "GitHub returned an invalid JSON response") from exc


def scan_github(source: dict[str, Any], token: str | None) -> dict[str, Any]:
    repo = source["repository"]
    ref = source.get("ref", "main")
    base = f"{API_ROOT}/repos/{repo}"
    measured_at = utc_now()
    try:
        metadata, _ = _json_request(base, token)
        branch = ref or metadata.get("default_branch") or "main"
        encoded_ref = urllib.parse.quote(str(branch), safe="")
        tree, _ = _json_request(f"{base}/git/trees/{encoded_ref}?recursive=1", token)
        entries = tree.get("tree", [])
        blobs = [entry for entry in entries if entry.get("type") == "blob"]
        include_paths = source.get("include_paths") or []
        exclude_paths = source.get("exclude_paths") or []
        def matches_scope(path: str, scope: str) -> bool:
            normalized = scope.strip("/")
            return path == normalized or path.startswith(normalized + "/")
        if include_paths:
            blobs = [entry for entry in blobs if any(matches_scope(entry.get("path", ""), scope) for scope in include_paths)]
        if exclude_paths:
            blobs = [entry for entry in blobs if not any(matches_scope(entry.get("path", ""), scope) for scope in exclude_paths)]
        blob_bytes = sum(int(entry.get("size", 0) or 0) for entry in blobs)
        truncated = bool(tree.get("truncated", False))
        return {
            "source_id": source["source_id"], "project_id": source["project_id"],
            "provider": "github", "reference": repo, "ref": branch,
            "measured_at": measured_at, "status": "PARTIAL" if truncated else "COMPLETE",
            "file_count": len(blobs), "logical_bytes": blob_bytes,
            "repository_size_bytes": int(metadata.get("size", 0) or 0) * 1024 if not include_paths and not exclude_paths else None,
            "path_scope": {"include_paths": include_paths, "exclude_paths": exclude_paths},
            "capacity_bytes": None, "method": "GitHub repository metadata + recursive Git tree blob sizes with optional path scoping",
            "error": None,
            "limitations": [
                "Tree blob bytes represent the checked-out tree, not the complete .git history or remote object storage.",
                "Git LFS pointer files are counted as pointer blobs; external LFS object sizes are not included.",
                "GitHub repository_size_bytes is a provider-reported repository-size estimate in KiB and is shown separately, not added to logical_bytes."
            ] + (["GitHub marked the recursive tree as truncated; file count and bytes are lower bounds."] if truncated else [])
        }
    except ScanError as exc:
        if exc.status == "EMPTY":
            return {
                "source_id": source["source_id"], "project_id": source["project_id"],
                "provider": "github", "reference": repo, "ref": ref,
                "measured_at": measured_at, "status": "EMPTY", "file_count": 0,
                "logical_bytes": 0, "repository_size_bytes": 0, "capacity_bytes": None,
                "method": "GitHub repository metadata/tree API", "error": None,
                "limitations": ["Repository has no Git commit/tree; zero means empty repository, not a failed scan."]
            }
        return {
            "source_id": source["source_id"], "project_id": source["project_id"],
            "provider": "github", "reference": repo, "ref": ref,
            "measured_at": measured_at, "status": exc.status, "file_count": None,
            "logical_bytes": None, "repository_size_bytes": None, "capacity_bytes": None,
            "method": "GitHub repository metadata + recursive Git tree blob sizes",
            "error": str(exc), "limitations": []
        }


def scan_local(source: dict[str, Any]) -> dict[str, Any]:
    root = Path(source["path"]).expanduser()
    measured_at = utc_now()
    if not root.exists():
        return {"source_id": source["source_id"], "project_id": source["project_id"], "provider": "local", "reference": str(root), "measured_at": measured_at, "status": "NOT_CONFIGURED", "file_count": None, "logical_bytes": None, "repository_size_bytes": None, "capacity_bytes": None, "method": "read-only filesystem metadata", "error": "Configured local path does not exist or is not mounted", "limitations": []}
    if not root.is_dir():
        return {"source_id": source["source_id"], "project_id": source["project_id"], "provider": "local", "reference": str(root), "measured_at": measured_at, "status": "FAILED", "file_count": None, "logical_bytes": None, "repository_size_bytes": None, "capacity_bytes": None, "method": "read-only filesystem metadata", "error": "Configured local path is not a directory", "limitations": []}
    count = total = 0
    errors: list[str] = []
    def record_walk_error(exc: OSError) -> None:
        errors.append(f"directory scan: {exc.__class__.__name__}")
    for current, dirs, files in os.walk(root, followlinks=False, onerror=record_walk_error):
        dirs[:] = [d for d in dirs if not (Path(current) / d).is_symlink()]
        for name in files:
            path = Path(current) / name
            try:
                if path.is_symlink():
                    continue
                stat = path.stat(follow_symlinks=False)
                if path.is_file():
                    count += 1
                    total += stat.st_size
            except OSError as exc:
                errors.append(f"{path.name}: {exc.__class__.__name__}")
    return {"source_id": source["source_id"], "project_id": source["project_id"], "provider": "local", "reference": str(root), "measured_at": measured_at, "status": "PARTIAL" if errors else "COMPLETE", "file_count": count, "logical_bytes": total, "repository_size_bytes": None, "capacity_bytes": None, "method": "read-only filesystem metadata; symlinks are not followed", "error": "; ".join(errors[:10]) if errors else None, "limitations": ["Filesystem scan counts allocated-independent logical file lengths, not physical block usage."]}


def scan_source(source: dict[str, Any], token: str | None) -> dict[str, Any]:
    provider = source.get("provider")
    if provider == "github":
        return scan_github(source, token)
    if provider == "local":
        return scan_local(source)
    return {"source_id": source.get("source_id", "unknown"), "project_id": source.get("project_id", "unknown"), "provider": str(provider), "reference": source.get("reference"), "measured_at": utc_now(), "status": "UNSUPPORTED", "file_count": None, "logical_bytes": None, "repository_size_bytes": None, "capacity_bytes": source.get("capacity_bytes"), "method": "not implemented", "error": f"Provider adapter not implemented: {provider}", "limitations": []}


def build_report(config: dict[str, Any], results: list[dict[str, Any]]) -> dict[str, Any]:
    by_source = {r["source_id"]: r for r in results}
    projects = []
    for project in config.get("projects", []):
        expected_ids = project.get("sources", [])
        selected = [by_source[sid] for sid in expected_ids if sid in by_source]
        missing_ids = [sid for sid in expected_ids if sid not in by_source]
        known = [r for r in selected if r.get("status") in SUCCESS_STATUSES and isinstance(r.get("logical_bytes"), int)]
        failed = [r for r in selected if r.get("status") not in SUCCESS_STATUSES]
        has_gaps = bool(failed or missing_ids)
        projects.append({
            "project_id": project["project_id"], "name": project["name"],
            "source_count": len(expected_ids), "measured_source_count": len(known),
            "coverage": "NOT_REGISTERED" if not expected_ids else ("INCOMPLETE" if has_gaps else "COMPLETE"),
            "known_logical_bytes": sum(r["logical_bytes"] for r in known),
            "logical_bytes_complete": bool(expected_ids) and not has_gaps,
            "missing_source_ids": missing_ids,
            "sources": selected
        })
    known_total = sum(p["known_logical_bytes"] for p in projects)
    incomplete = [r for r in results if r.get("status") not in SUCCESS_STATUSES]
    alerts = []
    for project in projects:
        if project["coverage"] == "NOT_REGISTERED":
            alerts.append({"severity": "WARNING", "code": "PROJECT_NOT_REGISTERED", "project_id": project["project_id"], "source_id": None, "message": "No storage source is registered for this project", "evidence": None})
        for missing_id in project.get("missing_source_ids", []):
            alerts.append({"severity": "WARNING", "code": "SOURCE_NOT_SCANNED", "project_id": project["project_id"], "source_id": missing_id, "message": "Configured source produced no measurement record", "evidence": None})
    for result in incomplete:
        alerts.append({"severity": "WARNING", "code": "SOURCE_INCOMPLETE", "project_id": result["project_id"], "source_id": result["source_id"], "message": f"Source scan status: {result['status']}", "evidence": result.get("error")})
    return {
        "schema_version": 1, "tool": "TRADIX Portfolio Storage Monitor", "generated_at": utc_now(),
        "mode": config.get("mode", "MANUAL"), "portfolio_coverage": "INCOMPLETE" if incomplete or any(p["coverage"] != "COMPLETE" for p in projects) else "COMPLETE",
        "project_count": len(projects), "source_count": len(results),
        "known_logical_bytes": known_total, "known_logical_mib": round(known_total / (1024 * 1024), 3),
        "total_is_complete": not incomplete and all(p["coverage"] == "COMPLETE" for p in projects),
        "alerts": alerts, "projects": projects,
        "limitations": config.get("notes", []) + [
            "This report measures only configured and accessible sources.",
            "Logical file bytes, provider-reported repository size, and physical storage consumption are separate measures.",
            "No unconfigured local disk, cloud bucket, backup, Railway volume contents, or external storage is inferred as zero."
        ]
    }


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Portfolio Storage Monitor Report", "", f"- Generated: {report['generated_at']}", f"- Coverage: **{report['portfolio_coverage']}**", f"- Known logical data: **{report['known_logical_mib']} MiB** (partial subtotal, not necessarily portfolio total)", f"- Sources: {report['source_count']}", "", "## Project inventory", "", "| Project | Coverage | Known logical size | Sources |", "|---|---|---:|---:|"]
    for project in report["projects"]:
        size = f"{project['known_logical_bytes'] / (1024 * 1024):.3f} MiB" if project["measured_source_count"] else "Not measured"
        lines.append(f"| {project['name']} | {project['coverage']} | {size} | {project['measured_source_count']}/{project['source_count']} |")
    lines += ["", "## Sources", "", "| Project | Source | Scope | Status | Files | Logical bytes | Provider repo size |", "|---|---|---|---|---:|---:|---:|"]
    for project in report["projects"]:
        for source in project["sources"]:
            count = source.get("file_count") if source.get("file_count") is not None else "—"
            size = source.get("logical_bytes")
            repo_size = source.get("repository_size_bytes")
            scope = source.get("path_scope") or {}
            if scope.get("include_paths"):
                scope_label = "include: " + ", ".join(scope["include_paths"])
            elif scope.get("exclude_paths"):
                scope_label = "repository minus: " + ", ".join(scope["exclude_paths"])
            else:
                scope_label = "whole repository"
            lines.append(f"| {project['name']} | {source['source_id']} | {scope_label} | {source['status']} | {count} | {size if size is not None else '—'} | {repo_size if repo_size is not None else '—'} |")
    lines += ["", "## Alerts", ""]
    if report["alerts"]:
        for alert in report["alerts"]:
            lines.append(f"- **{alert['severity']} {alert['code']}** — {alert['project_id']} / {alert['source_id']}: {alert['message']}. {alert.get('evidence') or ''}")
    else:
        lines.append("No source-access or scan-completeness alerts.")
    lines += ["", "## Limitations", ""]
    lines.extend(f"- {item}" for item in report["limitations"])
    return "\n".join(lines) + "\n"


def write_report(report: dict[str, Any], output: Path) -> Path:
    output.parent.mkdir(parents=True, exist_ok=True)
    output = output.resolve()
    fd, temp_name = tempfile.mkstemp(prefix=output.name + ".", suffix=".tmp", dir=str(output.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        os.replace(temp_name, output)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    output.with_suffix(".md").write_text(render_markdown(report), encoding="utf-8")
    return output


def publish_issue(report: dict[str, Any], token: str, repository: str) -> str:
    api = f"https://api.github.com/repos/{repository}/issues"
    title = "Portfolio Storage Monitor — Latest Report"
    body = render_markdown(report)
    body += "\n---\n_This issue is maintained automatically by the optional TRADIX Portfolio Storage Monitor. It is not proof of complete portfolio coverage when the report says INCOMPLETE._\n"
    headers = {"Accept": "application/vnd.github+json", "Authorization": f"Bearer {token}", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": USER_AGENT, "Content-Type": "application/json"}
    request = urllib.request.Request(f"{api}?state=open&per_page=100", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            issues = json.loads(response.read().decode("utf-8"))
        existing = next((item for item in issues if item.get("title") == title and "pull_request" not in item), None)
        payload = json.dumps({"title": title, "body": body}).encode("utf-8")
        if existing:
            req = urllib.request.Request(f"{api}/{existing['number']}", data=payload, headers=headers, method="PATCH")
        else:
            req = urllib.request.Request(api, data=payload, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
        return result.get("html_url", "issue updated")
    except (urllib.error.HTTPError, urllib.error.URLError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Could not publish GitHub report issue: {exc}") from exc


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only, independent portfolio storage inventory")
    parser.add_argument("--config", default="tools/portfolio_storage_monitor/config/portfolio.json")
    parser.add_argument("--output", default="artifacts/storage-monitor/latest.json")
    parser.add_argument("--publish-github-issue", action="store_true", help="Update a single report issue using a GitHub token with issues:write")
    args = parser.parse_args(argv)
    try:
        config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 2
    if config.get("mode", "MANUAL") == "DISABLED":
        print("Monitor is DISABLED; no scans were run.")
        return 0
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    if event_name == "schedule" and not config.get("scheduled_enabled", False):
        print("Scheduled monitoring is disabled in the registry; no scans were run.")
        return 0
    if event_name == "schedule":
        config["mode"] = "SCHEDULED"
    token = os.environ.get("PORTFOLIO_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    results = [scan_source(source, token) for source in config.get("sources", [])]
    report = build_report(config, results)
    output = write_report(report, Path(args.output))
    print(render_markdown(report))
    print(f"JSON report: {output}")
    if args.publish_github_issue:
        repository = os.environ.get("GITHUB_REPOSITORY", "grinlife4-stack/TRADIX")
        if not token:
            print("Issue publication skipped: no GitHub token was provided.", file=sys.stderr)
            return 3
        try:
            print(f"GitHub report issue: {publish_issue(report, token, repository)}")
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
