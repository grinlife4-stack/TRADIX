import json
from pathlib import Path

from mega_market.cli import main


FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "mega_market" / "sales_report_v1.json"


def arguments(*extra: str) -> list[str]:
    return [
        "import-sales",
        "--input", str(FIXTURE),
        "--source-id", "demo-sales-source",
        "--source-name", "Synthetic demo source",
        "--permission-reference", "fixture://demo/permission",
        "--terms-reviewed-at", "2026-11-16T12:00:00Z",
        *extra,
    ]


def test_cli_imports_synthetic_report_and_emits_audit_summary(capsys):
    assert main(arguments()) == 0
    output = json.loads(capsys.readouterr().out)

    assert output["schema_version"] == "mega-market-import-result-v1"
    assert output["report_id"] == "synthetic-demo-report-2026-11"
    assert output["market_code"] == "DE"
    assert output["observation_count"] == 2
    assert {item["metric"] for item in output["observations"]} == {
        "units_sold", "transaction_count"
    }
    assert all(item["verified"] for item in output["observations"])
    assert len(output["raw_payload_sha256"]) == 64
    assert output["commercial_authorization"] is False
    assert output["decision"] == "evidence_import_only"


def test_cli_writes_a_new_output_file_without_overwriting(tmp_path, capsys):
    output_path = tmp_path / "import-result.json"
    assert main(arguments("--output", str(output_path))) == 0
    first_content = output_path.read_text(encoding="utf-8")
    assert json.loads(first_content)["observation_count"] == 2

    assert main(arguments("--output", str(output_path))) == 2
    assert output_path.read_text(encoding="utf-8") == first_content
    assert "already exists" in capsys.readouterr().err


def test_cli_rejects_permission_reference_mismatch(capsys):
    args = arguments("--permission-reference", "fixture://wrong/permission")
    assert main(args) == 2
    assert "does not match the approved source" in capsys.readouterr().err
