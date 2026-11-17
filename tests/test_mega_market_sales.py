import hashlib
import json
from datetime import datetime, timedelta, timezone
import pytest
from mega_market import SourceDescriptor, import_normalized_sales_report

NOW=datetime(2026,11,17,12,0,tzinfo=timezone.utc)
DESCRIPTOR=SourceDescriptor(
    source_id="authorized-report",display_name="Authorized sales report",
    access_mode="manual_import",permission_status="approved",
    permission_reference="permission://signed-agreement/42",
    terms_reviewed_at=NOW-timedelta(days=1),
)

def payload(*,coverage=True,metric="units_sold",value="18",permission=None):
    return json.dumps({
        "schema_version":"1","report_id":"report-2026-11",
        "source_id":"authorized-report",
        "permission_reference":permission or DESCRIPTOR.permission_reference,
        "market_code":"DE","generated_at":"2026-11-17T12:00:00Z",
        "period_start":"2026-11-01T00:00:00Z","period_end":"2026-11-16T23:59:59Z",
        "coverage_complete":coverage,
        "records":[{"record_id":"line-1","product_identity_key":"gtin:04006381333931",
                    "metric":metric,"value":value,
                    "unit":"transactions" if metric=="transaction_count" else "units"}],
    },separators=(",",":")).encode()

def test_approved_complete_report_imports_verified_sales_with_payload_hash():
    raw=payload()
    result=import_normalized_sales_report(raw,DESCRIPTOR)
    item=result.observations[0]
    assert result.raw_payload_sha256==hashlib.sha256(raw).hexdigest()
    assert item.verified is True and item.coverage_complete is True
    assert item.metric=="units_sold" and item.value.as_tuple().digits==(1,8)
    assert item.permission_reference==DESCRIPTOR.permission_reference
    assert item.raw_payload_sha256==result.raw_payload_sha256

def test_incomplete_report_is_imported_but_not_verified():
    result=import_normalized_sales_report(payload(coverage=False),DESCRIPTOR)
    assert result.observations[0].verified is False
    assert result.observations[0].coverage_complete is False

def test_unapproved_source_is_rejected():
    blocked=SourceDescriptor("authorized-report","Sales report","manual_import","blocked",None,None)
    with pytest.raises(ValueError,match="not approved"):
        import_normalized_sales_report(payload(),blocked)

def test_permission_reference_must_match_registered_source():
    with pytest.raises(ValueError,match="does not match"):
        import_normalized_sales_report(payload(permission="permission://other"),DESCRIPTOR)

def test_proxy_metric_cannot_be_imported_as_direct_sales():
    with pytest.raises(ValueError,match="must be transaction_count or units_sold"):
        import_normalized_sales_report(payload(metric="bestseller_rank"),DESCRIPTOR)

def test_numeric_json_sales_value_is_rejected():
    raw=payload().replace(b'"value":"18"',b'"value":18')
    with pytest.raises(TypeError,match="decimal string"):
        import_normalized_sales_report(raw,DESCRIPTOR)

def test_duplicate_record_ids_are_rejected():
    raw=payload()
    doc=json.loads(raw)
    doc["records"].append(dict(doc["records"][0]))
    with pytest.raises(ValueError,match="duplicate sales record_id"):
        import_normalized_sales_report(json.dumps(doc).encode(),DESCRIPTOR)

def test_duplicate_json_keys_are_rejected():
    raw=b'{"schema_version":"1","schema_version":"1"}'
    with pytest.raises(ValueError,match="duplicate JSON key"):
        import_normalized_sales_report(raw,DESCRIPTOR)

def test_report_period_must_end_before_generated_at():
    doc=json.loads(payload())
    doc["period_end"]="2026-11-18T00:00:00Z"
    with pytest.raises(ValueError,match="after generated_at"):
        import_normalized_sales_report(json.dumps(doc).encode(),DESCRIPTOR)

def test_report_requires_timezone_aware_timestamps():
    doc=json.loads(payload())
    doc["period_start"]="2026-11-01T00:00:00"
    with pytest.raises(ValueError,match="timezone"):
        import_normalized_sales_report(json.dumps(doc).encode(),DESCRIPTOR)
