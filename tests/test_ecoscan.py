import json
from pathlib import Path

from tools.ecoscan import monitor


def test_github_tree_inventory_counts_blob_sizes(monkeypatch):
    responses = [
        ({"size": 12, "default_branch": "main"}, {}),
        ({"tree": [{"type": "blob", "size": 100}, {"type": "tree"}, {"type": "blob", "size": 250}], "truncated": False}, {}),
    ]
    monkeypatch.setattr(monitor, "_json_request", lambda url, token=None: responses.pop(0))
    result = monitor.scan_github({"source_id": "s1", "project_id": "p1", "repository": "owner/repo", "ref": "main"}, None)
    assert result["status"] == "COMPLETE"
    assert result["file_count"] == 2
    assert result["logical_bytes"] == 350
    assert result["repository_size_bytes"] == 12 * 1024


def test_empty_repository_is_not_reported_as_failure(monkeypatch):
    def fail(url, token=None):
        raise monitor.ScanError("EMPTY", "empty")
    monkeypatch.setattr(monitor, "_json_request", fail)
    result = monitor.scan_github({"source_id": "s1", "project_id": "p1", "repository": "owner/empty"}, None)
    assert result["status"] == "EMPTY"
    assert result["logical_bytes"] == 0


def test_inaccessible_source_is_not_counted_as_zero():
    config = {"projects": [{"project_id": "p1", "name": "Project", "sources": ["s1"]}]}
    results = [{"source_id": "s1", "project_id": "p1", "status": "NOT_AUTHORIZED_OR_NOT_FOUND", "logical_bytes": None, "file_count": None}]
    report = monitor.build_report(config, results)
    project = report["projects"][0]
    assert project["known_logical_bytes"] == 0
    assert project["logical_bytes_complete"] is False
    assert report["total_is_complete"] is False
    assert report["alerts"][0]["code"] == "SOURCE_INCOMPLETE"


def test_unregistered_project_is_not_assumed_empty():
    report = monitor.build_report({"projects": [{"project_id": "p1", "name": "Project", "sources": []}]}, [])
    assert report["projects"][0]["coverage"] == "NOT_REGISTERED"
    assert report["total_is_complete"] is False


def test_local_scan_counts_files_without_following_symlinks(tmp_path):
    (tmp_path / "one.txt").write_text("abc", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "two.bin").write_bytes(b"12345")
    outside = tmp_path.parent / "outside.txt"
    outside.write_text("should not be counted", encoding="utf-8")
    try:
        (tmp_path / "linked.txt").symlink_to(outside)
    except (OSError, NotImplementedError):
        pass
    result = monitor.scan_local({"source_id": "local1", "project_id": "p1", "path": str(tmp_path)})
    assert result["status"] == "COMPLETE"
    assert result["file_count"] == 2
    assert result["logical_bytes"] == 8


def test_write_report_creates_json_and_markdown(tmp_path):
    report = monitor.build_report({"projects": [{"project_id": "p1", "name": "Project", "sources": ["s1"]}]}, [
        {"source_id": "s1", "project_id": "p1", "status": "COMPLETE", "logical_bytes": 10, "file_count": 1, "provider": "fixture"}
    ])
    output = monitor.write_report(report, tmp_path / "latest.json")
    assert json.loads(output.read_text(encoding="utf-8"))["known_logical_bytes"] == 10
    assert output.with_suffix(".md").exists()


def test_missing_configured_source_marks_project_incomplete():
    config = {"projects": [{"project_id": "p1", "name": "Project", "sources": ["s1", "s2"]}]}
    results = [{"source_id": "s1", "project_id": "p1", "status": "COMPLETE", "logical_bytes": 10, "file_count": 1}]
    report = monitor.build_report(config, results)
    project = report["projects"][0]
    assert project["coverage"] == "INCOMPLETE"
    assert project["missing_source_ids"] == ["s2"]
    assert any(alert["code"] == "SOURCE_NOT_SCANNED" for alert in report["alerts"])


def test_github_inventory_supports_independent_path_scopes(monkeypatch):
    responses = [
        ({"size": 50, "default_branch": "main"}, {}),
        ({"tree": [
            {"path": "README.md", "type": "blob", "size": 10},
            {"path": "products/megamarket/brief.md", "type": "blob", "size": 20},
            {"path": "projects/NEXORA/notes.md", "type": "blob", "size": 30},
        ], "truncated": False}, {}),
    ]
    monkeypatch.setattr(monitor, "_json_request", lambda url, token=None: responses.pop(0))
    result = monitor.scan_github({
        "source_id": "market", "project_id": "MEGAMARKET", "repository": "owner/repo",
        "ref": "main", "include_paths": ["products/megamarket/"]
    }, None)
    assert result["file_count"] == 1
    assert result["logical_bytes"] == 20
    assert result["repository_size_bytes"] is None


def test_disabled_mode_performs_no_scan(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"mode": "DISABLED", "projects": [], "sources": []}), encoding="utf-8")
    monkeypatch.setattr(monitor, "scan_source", lambda *args: (_ for _ in ()).throw(AssertionError("scan must not run")))
    assert monitor.main(["--config", str(config_path), "--output", str(tmp_path / "out.json")]) == 0
    assert not (tmp_path / "out.json").exists()


def test_scheduled_mode_can_be_disabled_without_scanning(tmp_path, monkeypatch):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"mode": "MANUAL", "scheduled_enabled": False, "projects": [], "sources": []}), encoding="utf-8")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "schedule")
    monkeypatch.setattr(monitor, "scan_source", lambda *args: (_ for _ in ()).throw(AssertionError("scan must not run")))
    assert monitor.main(["--config", str(config_path), "--output", str(tmp_path / "out.json")]) == 0
    assert not (tmp_path / "out.json").exists()
