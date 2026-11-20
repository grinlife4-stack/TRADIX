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
    assert project["known_logical_bytes"] is None
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


def test_exvarli_ascii_path_scope_is_attributed_and_excluded_correctly(monkeypatch):
    tree = {"tree": [
        {"path": "README.md", "type": "blob", "size": 23},
        {"path": "projects/EXVARLI/record.json", "type": "blob", "size": 11},
        {"path": "docs/projects/EXVARLI_FINANCIAL_ARCHITECTURE.md", "type": "blob", "size": 13},
        {"path": "projects/EXVARLİ/legacy.txt", "type": "blob", "size": 17},
        {"path": "projects/NEXORA/notes.md", "type": "blob", "size": 19},
    ], "truncated": False}
    responses = [
        ({"size": 50, "default_branch": "main"}, {}), (tree, {}),
        ({"size": 50, "default_branch": "main"}, {}), (tree, {}),
    ]
    monkeypatch.setattr(monitor, "_json_request", lambda url, token=None: responses.pop(0))

    exvarli = monitor.scan_github({
        "source_id": "exvarli", "project_id": "EXVARLI", "repository": "owner/repo",
        "ref": "main",
        "include_paths": ["projects/EXVARLI/", "docs/projects/EXVARLI_FINANCIAL_ARCHITECTURE.md"],
    }, None)
    tradix = monitor.scan_github({
        "source_id": "tradix", "project_id": "TRADIX", "repository": "owner/repo",
        "ref": "main",
        "exclude_paths": ["projects/EXVARLI/", "docs/projects/EXVARLI_FINANCIAL_ARCHITECTURE.md"],
    }, None)

    assert exvarli["file_count"] == 2
    assert exvarli["logical_bytes"] == 24
    assert tradix["file_count"] == 3
    assert tradix["logical_bytes"] == 59


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


def test_select_project_scope_includes_only_project_sources():
    config = {
        "projects": [
            {"project_id": "p1", "name": "One", "sources": ["s1", "s2"]},
            {"project_id": "p2", "name": "Two", "sources": ["s3"]},
        ],
        "sources": [
            {"source_id": "s1", "project_id": "p1"},
            {"source_id": "s2", "project_id": "p1"},
            {"source_id": "s3", "project_id": "p2"},
        ],
    }
    selected = monitor.select_scope(config, "project", ["p2"])
    assert [p["project_id"] for p in selected["projects"]] == ["p2"]
    assert [s["source_id"] for s in selected["sources"]] == ["s3"]


def test_select_source_scope_does_not_expand_to_sibling_sources():
    config = {
        "projects": [{"project_id": "p1", "name": "One", "sources": ["s1", "s2"]}],
        "sources": [
            {"source_id": "s1", "project_id": "p1"},
            {"source_id": "s2", "project_id": "p1"},
        ],
    }
    selected = monitor.select_scope(config, "source", source_ids=["s2"])
    assert selected["projects"][0]["sources"] == ["s2"]
    assert [s["source_id"] for s in selected["sources"]] == ["s2"]


def test_scope_selection_rejects_unknown_ids_and_ambiguous_arguments():
    config = {"projects": [{"project_id": "p1", "sources": ["s1"]}], "sources": [{"source_id": "s1", "project_id": "p1"}]}
    import pytest
    with pytest.raises(ValueError):
        monitor.select_scope(config, "project", ["missing"])
    with pytest.raises(ValueError):
        monitor.select_scope(config, "ecosystem", project_ids=["p1"])
    with pytest.raises(ValueError):
        monitor.select_scope(config, "source")


def test_disabled_source_is_not_scanned_and_marks_coverage_incomplete(tmp_path, monkeypatch):
    config = {
        "mode": "MANUAL",
        "projects": [{"project_id": "p1", "name": "One", "enabled": True, "sources": ["s1"]}],
        "sources": [{"source_id": "s1", "project_id": "p1", "provider": "github", "repository": "owner/repo", "enabled": False}],
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setattr(monitor, "scan_source", lambda *args: (_ for _ in ()).throw(AssertionError("disabled source must not be scanned")))
    assert monitor.main(["--config", str(config_path), "--output", str(tmp_path / "out.json")]) == 0
    report = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert report["projects"][0]["coverage"] == "INCOMPLETE"
    assert report["projects"][0]["sources"][0]["status"] == "DISABLED"
    assert report["projects"][0]["sources"][0]["logical_bytes"] is None


def test_manual_source_scope_scans_only_selected_source(tmp_path, monkeypatch):
    config = {
        "mode": "MANUAL",
        "projects": [{"project_id": "p1", "name": "One", "sources": ["s1", "s2"]}],
        "sources": [
            {"source_id": "s1", "project_id": "p1", "provider": "fixture", "enabled": True},
            {"source_id": "s2", "project_id": "p1", "provider": "fixture", "enabled": True},
        ],
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    scanned = []
    def fake_scan(source, token):
        scanned.append(source["source_id"])
        return {"source_id": source["source_id"], "project_id": source["project_id"], "provider": "fixture", "status": "COMPLETE", "logical_bytes": 5, "file_count": 1}
    monkeypatch.setattr(monitor, "scan_source", fake_scan)
    assert monitor.main(["--config", str(config_path), "--scope", "source", "--source", "s2", "--output", str(tmp_path / "out.json")]) == 0
    report = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    assert scanned == ["s2"]
    assert report["scan_scope"]["type"] == "source"
    assert report["source_count"] == 1


def test_disabled_project_is_reported_as_disabled_not_unregistered_or_zero(tmp_path, monkeypatch):
    config = {
        "mode": "MANUAL",
        "projects": [{"project_id": "p1", "name": "One", "enabled": False, "sources": ["s1"]}],
        "sources": [{"source_id": "s1", "project_id": "p1", "provider": "fixture", "enabled": True}],
    }
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    monkeypatch.setattr(monitor, "scan_source", lambda *args: (_ for _ in ()).throw(AssertionError("disabled project must not be scanned")))
    assert monitor.main(["--config", str(config_path), "--output", str(tmp_path / "out.json")]) == 0
    report = json.loads((tmp_path / "out.json").read_text(encoding="utf-8"))
    project = report["projects"][0]
    assert project["coverage"] == "DISABLED"
    assert project["known_logical_bytes"] is None
    assert project["sources"][0]["status"] == "DISABLED"
    assert any(alert["code"] == "PROJECT_DISABLED" for alert in report["alerts"])


def test_railway_volume_adapter_reports_capacity_and_backup_metadata_only(monkeypatch):
    def fake_graphql(query, variables, token):
        assert variables == {"id": "instance-1", "volumeInstanceId": "instance-1"}
        assert token == "test-token"
        assert "volumeInstanceBackupList" in query
        return {
            "volumeInstance": {
                "id": "instance-1",
                "mountPath": "/data",
                "currentSizeMB": 500,
                "state": "READY",
                "volume": {"id": "volume-1", "name": "artifact-data"},
                "serviceInstance": {"serviceName": "artifact-gateway"},
            },
            "volumeInstanceBackupList": [
                {"id": "backup-1", "name": "daily", "createdAt": "2026-11-19T00:00:00Z", "expiresAt": None, "usedMB": 120, "referencedMB": 90}
            ],
        }
    monkeypatch.setattr(monitor, "_railway_graphql", fake_graphql)
    result = monitor.scan_railway_volume(
        {"source_id": "railway-vol-1", "project_id": "TRADIX", "volume_instance_id": "instance-1"},
        "test-token",
    )
    assert result["status"] == "COMPLETE"
    assert result["capacity_bytes"] == 500 * 1024 * 1024
    assert result["logical_bytes"] is None
    assert result["backup_used_bytes"] == 120 * 1024 * 1024
    assert result["backup_referenced_bytes"] == 90 * 1024 * 1024
    assert result["service_name"] == "artifact-gateway"
    assert "no volume contents read" in result["method"]


def test_railway_volume_resolves_instance_from_volume_and_environment(monkeypatch):
    calls = []
    def fake_graphql(query, variables, token):
        calls.append((query, variables, token))
        if "volumeInstances" in query:
            assert variables == {"environmentId": "env-1"}
            return {"environment": {"volumeInstances": [
                {"id": "instance-1", "volume": {"id": "volume-1", "name": "artifact-data"}}
            ]}}
        assert variables == {"id": "instance-1", "volumeInstanceId": "instance-1"}
        return {
            "volumeInstance": {
                "id": "instance-1", "mountPath": "/data", "currentSizeMB": 500,
                "state": "READY", "volume": {"id": "volume-1", "name": "artifact-data"},
                "serviceInstance": {"serviceName": "artifact-gateway"},
            },
            "volumeInstanceBackupList": [],
        }
    monkeypatch.setattr(monitor, "_railway_graphql", fake_graphql)
    result = monitor.scan_railway_volume({
        "source_id": "railway-vol-1", "project_id": "TRADIX",
        "volume_id": "volume-1", "environment_id": "env-1",
    }, "test-token")
    assert result["status"] == "COMPLETE"
    assert result["volume_instance_id"] == "instance-1"
    assert len(calls) == 2


def test_railway_volume_resolution_fails_closed_on_missing_or_ambiguous_match(monkeypatch):
    def fake_graphql(query, variables, token):
        return {"environment": {"volumeInstances": [
            {"id": "instance-1", "volume": {"id": "volume-1"}},
            {"id": "instance-2", "volume": {"id": "volume-1"}},
        ]}}
    monkeypatch.setattr(monitor, "_railway_graphql", fake_graphql)
    result = monitor.scan_railway_volume({
        "source_id": "railway-vol-1", "project_id": "TRADIX",
        "volume_id": "volume-1", "environment_id": "env-1",
    }, "test-token")
    assert result["status"] == "FAILED"
    assert result["capacity_bytes"] is None


def test_railway_volume_requires_instance_or_volume_environment_and_token():
    source = {"source_id": "railway-vol-1", "project_id": "TRADIX"}
    missing_target = monitor.scan_railway_volume(source, "test-token")
    assert missing_target["status"] == "NOT_CONFIGURED"
    assert missing_target["capacity_bytes"] is None
    missing_token = monitor.scan_railway_volume({
        **source, "volume_id": "volume-1", "environment_id": "env-1"
    }, None)
    assert missing_token["status"] == "NOT_CONFIGURED"
    assert missing_token["logical_bytes"] is None


def test_scan_source_uses_railway_oauth_access_token(monkeypatch):
    monkeypatch.setenv("RAILWAY_OAUTH_ACCESS_TOKEN", "oauth-viewer-token")
    monkeypatch.setenv("RAILWAY_PROJECT_TOKEN", "unused-project-token")
    monkeypatch.setenv("RAILWAY_API_TOKEN", "unused-account-token")
    captured = {}
    def fake_scan(source, token):
        captured["token"] = token
        return {"status": "COMPLETE"}
    monkeypatch.setattr(monitor, "scan_railway_volume", fake_scan)
    result = monitor.scan_source({"source_id": "r1", "project_id": "P1", "provider": "railway_volume"}, None)
    assert result["status"] == "COMPLETE"
    assert captured["token"] == "oauth-viewer-token"


def test_railway_graphql_uses_bearer_oauth_access_token(monkeypatch):
    captured = {}
    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return b'{"data":{"environment":{"id":"env-1"}}}'
    def fake_urlopen(request, timeout):
        captured["request"] = request
        return FakeResponse()
    monkeypatch.setattr(monitor.urllib.request, "urlopen", fake_urlopen)
    data = monitor._railway_graphql("query { environment(id: \"env-1\") { id } }", {}, "oauth-viewer-token")
    request = captured["request"]
    assert request.get_header("Authorization") == "Bearer oauth-viewer-token"
    assert request.get_header("Project-access-token") is None
    assert data["environment"]["id"] == "env-1"


def test_railway_graphql_errors_fail_closed(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return b'{"errors":[{"message":"Not Authorized"}]}'
    monkeypatch.setattr(monitor.urllib.request, "urlopen", lambda *args, **kwargs: FakeResponse())
    try:
        monitor._railway_graphql("query { me { id } }", {}, "bad-token")
    except monitor.ScanError as exc:
        assert exc.status == "NOT_AUTHORIZED_OR_NOT_FOUND"
    else:
        raise AssertionError("GraphQL authorization errors must fail closed")


def test_s3_compatible_adapter_lists_metadata_with_pagination(monkeypatch):
    monkeypatch.setenv("ECOSCAN_TEST_ACCESS", "access")
    monkeypatch.setenv("ECOSCAN_TEST_SECRET", "secret")
    bodies = [
        b'<ListBucketResult><IsTruncated>true</IsTruncated><NextContinuationToken>next-page</NextContinuationToken><Contents><Key>a.bin</Key><Size>10</Size></Contents></ListBucketResult>',
        b'<ListBucketResult><IsTruncated>false</IsTruncated><Contents><Key>b.bin</Key><Size>25</Size></Contents></ListBucketResult>',
    ]
    requests = []
    class FakeResponse:
        def __init__(self, body):
            self.body = body
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return self.body
    def fake_urlopen(request, timeout):
        requests.append(request)
        return FakeResponse(bodies.pop(0))
    monkeypatch.setattr(monitor.urllib.request, "urlopen", fake_urlopen)
    result = monitor.scan_s3_compatible({
        "source_id": "r2-main", "project_id": "P1", "provider": "s3_compatible",
        "endpoint": "https://account.r2.cloudflarestorage.com", "bucket": "assets",
        "region": "auto", "url_style": "path",
        "access_key_env": "ECOSCAN_TEST_ACCESS", "secret_key_env": "ECOSCAN_TEST_SECRET",
    })
    assert result["status"] == "COMPLETE"
    assert result["file_count"] == 2
    assert result["logical_bytes"] == 35
    assert result["page_count"] == 2
    assert "Authorization" in requests[0].headers
    assert "continuation-token=next-page" in requests[1].full_url
    assert "no object bodies downloaded" in result["method"]


def test_s3_compatible_adapter_does_not_report_missing_credentials_as_zero(monkeypatch):
    monkeypatch.delenv("ECOSCAN_MISSING_ACCESS", raising=False)
    monkeypatch.delenv("ECOSCAN_MISSING_SECRET", raising=False)
    result = monitor.scan_s3_compatible({
        "source_id": "b2-archive", "project_id": "P1",
        "endpoint": "https://s3.us-west-004.backblazeb2.com", "bucket": "archive",
        "access_key_env": "ECOSCAN_MISSING_ACCESS", "secret_key_env": "ECOSCAN_MISSING_SECRET",
    })
    assert result["status"] == "NOT_CONFIGURED"
    assert result["logical_bytes"] is None
    assert result["file_count"] is None


def test_s3_compatible_adapter_marks_truncated_listing_partial(monkeypatch):
    monkeypatch.setenv("ECOSCAN_TEST_ACCESS", "access")
    monkeypatch.setenv("ECOSCAN_TEST_SECRET", "secret")
    class FakeResponse:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self):
            return b'<ListBucketResult><IsTruncated>true</IsTruncated><Contents><Key>a</Key><Size>7</Size></Contents></ListBucketResult>'
    monkeypatch.setattr(monitor.urllib.request, "urlopen", lambda *args, **kwargs: FakeResponse())
    result = monitor.scan_s3_compatible({
        "source_id": "s3-partial", "project_id": "P1", "endpoint": "https://s3.example.test",
        "bucket": "bucket", "access_key_env": "ECOSCAN_TEST_ACCESS",
        "secret_key_env": "ECOSCAN_TEST_SECRET", "max_pages": 1,
    })
    assert result["status"] == "PARTIAL"
    assert result["logical_bytes"] == 7

def test_railway_volume_resolution_accepts_relay_connection_shape(monkeypatch):
    calls = []
    def fake_graphql(query, variables, token):
        calls.append(query)
        if "volumeInstances" in query:
            return {"environment": {"volumeInstances": {"edges": [
                {"node": {"id": "instance-1", "volume": {"id": "volume-1", "name": "artifact-data"}}}
            ]}}}
        return {
            "volumeInstance": {
                "id": "instance-1", "mountPath": "/data", "currentSizeMB": 500,
                "state": "READY", "volume": {"id": "volume-1", "name": "artifact-data"},
                "serviceInstance": {"serviceName": "artifact-gateway"},
            },
            "volumeInstanceBackupList": [],
        }
    monkeypatch.setattr(monitor, "_railway_graphql", fake_graphql)
    result = monitor.scan_railway_volume({
        "source_id": "railway-vol-1", "project_id": "TRADIX",
        "volume_id": "volume-1", "environment_id": "env-1",
    }, "test-token")
    assert result["status"] == "COMPLETE"
    assert result["volume_instance_id"] == "instance-1"
    assert len(calls) == 2

