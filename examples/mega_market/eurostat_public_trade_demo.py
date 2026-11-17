"""Fetch and inspect a narrow, publicly reusable Eurostat Comext trade-data slice.

This is a live public-statistics demonstration, not retail-sales evidence.
No marketplace, supplier, order, payment, or wallet system is contacted.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

DATASET = "DS-045409"
API_BASE = "https://ec.europa.eu/eurostat/api/comext/dissemination/sdmx/2.1/data"
SOURCE_PAGE = "https://ec.europa.eu/eurostat/databrowser/view/DS-045409/default/table?lang=en"
REUSE_POLICY = "https://ec.europa.eu/eurostat/help/copyright-notice"

# Engineering sample only: annual German imports of HS 8703 (motor cars and other motor vehicles)
# reported against France, 2020-2025. This is not a launch-market decision.
QUERY = {
    "frequency": "A",
    "reporter": "DE",
    "partner": "FR",
    "product": "8703",
    "flow": "1",  # Eurostat Comext code 1 = imports.
    "indicator": "VALUE_IN_EUROS",
}


def build_request_url(start_year: int, end_year: int) -> str:
    if not (1990 <= start_year <= end_year <= 2100):
        raise ValueError("year range must be ordered and within 1990..2100")
    key = (
        f"{QUERY['frequency']}.{QUERY['reporter']}.{QUERY['partner']}."
        f"{QUERY['product']}.{QUERY['flow']}.{QUERY['indicator']}"
    )
    params = urllib.parse.urlencode({
        "format": "SDMX-CSV",
        "startPeriod": str(start_year),
        "endPeriod": str(end_year),
    })
    return f"{API_BASE}/{DATASET}/{key}?{params}"


def parse_sdmx_csv(payload: bytes, start_year: int, end_year: int) -> dict:
    """Validate the exact requested slice and normalize observations without floats."""
    if not isinstance(payload, bytes) or not payload:
        raise ValueError("Eurostat response is empty")
    if len(payload) > 10_000_000:
        raise ValueError("Eurostat response exceeds the 10 MB safety limit")

    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Eurostat response is not UTF-8 CSV") from exc

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("Eurostat response has no CSV header")
    # Comext SDMX-CSV currently emits lowercase dimension names, while some
    # other Eurostat SDMX-CSV responses use uppercase names. Normalize headers.
    header_map = {
        name.strip().upper(): name
        for name in reader.fieldnames
        if name and name.strip()
    }
    required = {
        "FREQ", "REPORTER", "PARTNER", "PRODUCT", "FLOW",
        "TIME_PERIOD", "INDICATORS", "OBS_VALUE",
    }
    missing = required - set(header_map)
    if missing:
        preview = text[:1200].replace("\\n", " ")
        raise ValueError(
            f"Unexpected Eurostat response. missing_headers={sorted(missing)!r}; "
            f"preview={preview!r}"
        )

    def field(row: dict, name: str, default: str = "") -> str:
        original_name = header_map.get(name)
        return row.get(original_name, default) if original_name else default

    observations = []
    missing_value_rows = 0
    seen_periods = set()
    source_last_update = None
    source_dataflow = None

    for row_number, row in enumerate(reader, start=2):
        expected = {
            "FREQ": QUERY["frequency"],
            "REPORTER": QUERY["reporter"],
            "PARTNER": QUERY["partner"],
            "PRODUCT": QUERY["product"],
            "FLOW": QUERY["flow"],
            "INDICATORS": QUERY["indicator"],
        }
        for name, expected_value in expected.items():
            actual = field(row, name)
            if actual != expected_value:
                raise ValueError(
                    f"row {row_number} has unexpected {name}: {actual!r}"
                )

        source_last_update = source_last_update or field(row, "LAST UPDATE") or None
        source_dataflow = source_dataflow or field(row, "DATAFLOW") or None

        period = field(row, "TIME_PERIOD").strip()
        if len(period) != 4 or not period.isdigit():
            raise ValueError(f"row {row_number} has invalid annual TIME_PERIOD")
        year = int(period)
        if not start_year <= year <= end_year:
            raise ValueError(f"row {row_number} is outside the requested year range")
        if year in seen_periods:
            raise ValueError(f"duplicate annual observation for {year}")
        seen_periods.add(year)

        raw_value = field(row, "OBS_VALUE").strip()
        if raw_value in {"", ".", ".."}:
            missing_value_rows += 1
            continue
        try:
            value = Decimal(raw_value)
        except InvalidOperation as exc:
            raise ValueError(f"row {row_number} has a non-decimal OBS_VALUE") from exc
        if not value.is_finite() or value < 0:
            raise ValueError(f"row {row_number} has an invalid trade value")

        raw_multiplier = field(row, "UNIT_MULT").strip()
        if raw_multiplier:
            try:
                multiplier = int(raw_multiplier)
            except ValueError as exc:
                raise ValueError(f"row {row_number} has invalid UNIT_MULT") from exc
        else:
            multiplier = None

        observations.append({
            "year": year,
            "obs_value": format(value, "f"),
            "unit": "EUR as reported by VALUE_IN_EUROS",
            "unit_multiplier": multiplier,
            "observation_status": field(row, "OBS_STATUS").strip() or None,
        })

    if not observations:
        raise ValueError("Eurostat returned no numeric observations for this slice")

    observations.sort(key=lambda item: item["year"])
    return {
        "dataset": DATASET,
        "source_dataflow": source_dataflow,
        "source_last_update": source_last_update,
        "dimensions": {
            "frequency": "annual",
            "reporter": "DE",
            "partner": "FR",
            "product_code": "8703",
            "product_label": "Motor cars and other motor vehicles (HS 8703)",
            "flow": "imports",
            "indicator": "VALUE_IN_EUROS",
        },
        "requested_period": {"start_year": start_year, "end_year": end_year},
        "observations": observations,
        "numeric_observation_count": len(observations),
        "missing_value_row_count": missing_value_rows,
    }

def fetch_bytes(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "text/csv, application/vnd.sdmx.data+csv;version=1.0.0",
            "User-Agent": "TRADIX-MegaMarket-Public-Data-Demo/0.1",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            if response.status != 200:
                raise RuntimeError(f"Eurostat returned HTTP {response.status}")
            payload = response.read(10_000_001)
    except urllib.error.HTTPError as exc:
        detail = exc.read(4000).decode("utf-8", "replace")
        raise RuntimeError(f"Eurostat returned HTTP {exc.code}: {detail}") from exc
    if len(payload) > 10_000_000:
        raise ValueError("Eurostat response exceeds the 10 MB safety limit")
    return payload


def write_outputs(payload: bytes, normalized: dict, url: str, output_dir: Path) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    digest = hashlib.sha256(payload).hexdigest()

    raw_path = output_dir / "raw_eurostat_comext_sdmx.csv"
    normalized_path = output_dir / "normalized_trade_observations.json"
    manifest_path = output_dir / "manifest.json"
    report_path = output_dir / "report.md"

    raw_path.write_bytes(payload)
    normalized_document = {
        "evidence_class": "real_public_trade_statistics",
        "source": "Eurostat Comext",
        "source_dataset": DATASET,
        "source_page": SOURCE_PAGE,
        "downloaded_at_utc": downloaded_at,
        "raw_payload_sha256": digest,
        "transformation": (
            "Filtered one annual SDMX-CSV slice and normalized numeric values "
            "to decimal strings; no estimates, interpolation, FX conversion, "
            "or retail-sales inference."
        ),
        **normalized,
    }
    normalized_path.write_text(
        json.dumps(normalized_document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    manifest = {
        "mode": "live_public_data",
        "source": "Eurostat",
        "dataset": DATASET,
        "api_url": url,
        "source_page": SOURCE_PAGE,
        "reuse_policy_url": REUSE_POLICY,
        "reuse_scope_review": (
            "This sample is limited to Germany as reporter and France as partner "
            "(both EU Member States) and HS level 4. Eurostat's reuse notice permits "
            "commercial reuse subject to stated exceptions. Re-check the notice "
            "for every future query; do not generalize this clearance to non-EU "
            "partner data, EFTA-declared trade data, or restricted CN8 data."
        ),
        "required_attribution": (
            f"Source: Eurostat, Comext dataset {DATASET}; accessed {downloaded_at}. "
            "Filtered and reformatted by TRADIX. Changes to the source data are disclosed."
        ),
        "downloaded_at_utc": downloaded_at,
        "raw_file": raw_path.name,
        "raw_payload_sha256": digest,
        "numeric_observation_count": normalized["numeric_observation_count"],
        "missing_value_row_count": normalized["missing_value_row_count"],
        "interpretation_limit": (
            "Customs trade value is not retail sell-through, consumer demand, "
            "a current market price, supplier availability, or product profitability."
        ),
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# MegaMarket: Eurostat public trade-data sample",
        "",
        f"- Source: Eurostat Comext, dataset {DATASET}",
        f"- Retrieved (UTC): {downloaded_at}",
        f"- Raw payload SHA-256: {digest}",
        "- Query: annual German imports from France, HS 1001 (wheat and meslin), value in euros",
        f"- Period requested: {normalized['requested_period']['start_year']}–{normalized['requested_period']['end_year']}",
        "",
        "| Year | Trade value (EUR, as reported) | Unit multiplier | Status |",
        "|---:|---:|---:|---|",
    ]
    for item in normalized["observations"]:
        lines.append(
            f"| {item['year']} | {item['obs_value']} | "
            f"{item['unit_multiplier'] if item['unit_multiplier'] is not None else 'not supplied'} | "
            f"{item['observation_status'] or 'not supplied'} |"
        )
    lines.extend([
        "",
        "## What this proves",
        "",
        "The pipeline retrieved a real public statistical response, preserved the exact raw payload, "
        "computed its SHA-256, checked the requested dimensions, and produced normalized records.",
        "",
        "## What this does not prove",
        "",
        "These are customs trade-flow statistics. They are not store sales, retail demand, a live offer, "
        "supplier authorization, landed cost, or profit. They cannot pass the direct-sales commercial gate.",
        "",
        "## Reuse and attribution",
        "",
        manifest["required_attribution"],
        "",
        f"Reuse conditions: {REUSE_POLICY}",
        "",
        "The query is intentionally restricted to EU Member State reporting/partner countries and HS4. "
        "This narrow review does not authorize every possible Eurostat or third-party data slice.",
        "",
    ])
    report_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "mode": "live_public_data",
        "source": "Eurostat Comext",
        "dataset": DATASET,
        "query": normalized["dimensions"],
        "period": normalized["requested_period"],
        "numeric_observations": normalized["numeric_observation_count"],
        "missing_value_rows": normalized["missing_value_row_count"],
        "raw_payload_sha256": digest,
        "output_directory": str(output_dir),
        "commercial_decision": "not_assessed_trade_statistics_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-year", type=int, default=2020)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/megamarket-eurostat"),
    )
    args = parser.parse_args()

    url = build_request_url(args.start_year, args.end_year)
    payload = fetch_bytes(url)
    normalized = parse_sdmx_csv(payload, args.start_year, args.end_year)
    result = write_outputs(payload, normalized, url, args.output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
