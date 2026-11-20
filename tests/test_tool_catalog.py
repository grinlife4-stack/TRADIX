import sqlite3
import pytest

from tradix.tools import ToolCatalog, ToolDescriptor, ToolStatusError


def descriptor(**overrides):
    values = dict(
        tool_id="flutter",
        version="3.24.0",
        category="mobile-framework",
        source_uri="https://github.com/flutter/flutter",
        license_id="BSD-3-Clause",
        platforms=("android", "ios", "web"),
        capabilities=("cross-platform-ui", "mobile-build-input"),
        execution_modes=("local", "hosted-runner"),
        adapter_contract_version="1.0.0",
        free_open_source=True,
        notes="Candidate only; not installed or connected.",
    )
    values.update(overrides)
    return ToolDescriptor(**values)


def test_register_reopen_and_filter(tmp_path):
    db = tmp_path / "tools.sqlite"
    ToolCatalog(db).register(descriptor(), "catalog-import")
    catalog = ToolCatalog(db)
    item = catalog.get("flutter", "3.24.0")
    assert item["status"] == "discovered"
    assert item["platforms"] == ("android", "ios", "web")
    assert catalog.list_tools(category="mobile-framework")[0]["tool_id"] == "flutter"


def test_duplicate_version_rejected(tmp_path):
    catalog = ToolCatalog(tmp_path / "tools.sqlite")
    catalog.register(descriptor(), "test")
    with pytest.raises(sqlite3.IntegrityError):
        catalog.register(descriptor(), "test")


@pytest.mark.parametrize("overrides", [
    {"version": "latest"},
    {"version": "01.2.3"},
    {"tool_id": "../escape"},
    {"source_uri": "file:///etc/passwd"},
    {"source_uri": "https://user:pass@example.com/tool"},
    {"license_id": ""},
    {"platforms": ()},
    {"platforms": ("linux", "linux")},
    {"free_open_source": "yes"},
])
def test_invalid_descriptors_rejected(tmp_path, overrides):
    with pytest.raises(ValueError):
        descriptor(**overrides).validate()


def test_lifecycle_evidence_and_history(tmp_path):
    catalog = ToolCatalog(tmp_path / "tools.sqlite")
    catalog.register(descriptor(), "scanner")
    with pytest.raises(ToolStatusError):
        catalog.transition("flutter", "3.24.0", "evaluated", "reviewer", "reviewed")
    catalog.transition("flutter", "3.24.0", "evaluated", "reviewer", "reviewed", "evidence://review/1")
    catalog.transition("flutter", "3.24.0", "approved", "owner", "approved", "https://evidence.example/approval/1")
    catalog.transition("flutter", "3.24.0", "connected", "operator", "health check recorded", "https://evidence.example/health/1")
    assert catalog.get("flutter", "3.24.0")["status"] == "connected"
    assert [e["status"] for e in catalog.history("flutter", "3.24.0")] == [
        "discovered", "evaluated", "approved", "connected"
    ]


def test_invalid_transition_rejected(tmp_path):
    catalog = ToolCatalog(tmp_path / "tools.sqlite")
    catalog.register(descriptor(), "scanner")
    with pytest.raises(ToolStatusError):
        catalog.transition("flutter", "3.24.0", "connected", "operator", "connect", "evidence://x")


@pytest.mark.parametrize("bad_ref", ["", "not-a-uri", "file:///tmp/evidence", "https://user:pass@host/evidence"])
def test_invalid_evidence_reference_rejected(tmp_path, bad_ref):
    catalog = ToolCatalog(tmp_path / "tools.sqlite")
    catalog.register(descriptor(), "scanner")
    with pytest.raises(ToolStatusError):
        catalog.transition("flutter", "3.24.0", "evaluated", "reviewer", "review", bad_ref)


def test_suspend_retire_terminal(tmp_path):
    catalog = ToolCatalog(tmp_path / "tools.sqlite")
    catalog.register(descriptor(), "scanner")
    catalog.transition("flutter", "3.24.0", "suspended", "security", "license concern")
    catalog.transition("flutter", "3.24.0", "retired", "owner", "replaced")
    with pytest.raises(ToolStatusError):
        catalog.transition("flutter", "3.24.0", "approved", "owner", "re-enable", "evidence://x")


def test_ordinary_mutation_blocked(tmp_path):
    db = tmp_path / "tools.sqlite"
    ToolCatalog(db).register(descriptor(), "scanner")
    with sqlite3.connect(db) as connection:
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("UPDATE tools SET descriptor_json='{}'")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM tool_events")


def test_memory_database_rejected():
    with pytest.raises(ValueError):
        ToolCatalog(":memory:")


def test_non_descriptor_rejected(tmp_path):
    with pytest.raises(TypeError):
        ToolCatalog(tmp_path / "tools.sqlite").register({"tool_id": "x"}, "test")
