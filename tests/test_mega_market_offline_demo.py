import json
import runpy


def test_offline_sales_report_demo_runs_without_live_side_effects(capsys):
    demo = runpy.run_path("examples/mega_market/offline_sales_report_demo.py")
    assert demo["main"]() == 0

    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "offline_synthetic_demo"
    assert output["network_access"] is False
    assert output["source_permission_is_real"] is False
    assert output["supplier_authorization_is_real"] is False
    assert output["compliance_review_is_real"] is False
    assert output["imported_observation_count"] == 2
    assert len(output["payload_sha256"]) == 64
    assert output["demand_status"] == "direct_sales_observations_available"
    assert output["decision_status"] == "eligible_for_manual_pilot"
    assert "not authorization" in output["warning"]
