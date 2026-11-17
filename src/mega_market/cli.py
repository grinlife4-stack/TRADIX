"""Offline command-line entry point for permission-backed Mega Market sales imports."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

from .catalog import SourceDescriptor
from .sales import SalesReportImport, import_normalized_sales_report


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise argparse.ArgumentTypeError("timestamp must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("timestamp must include a timezone")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mega-market",
        description="Run the offline Mega Market sales-report importer.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    sales = commands.add_parser(
        "import-sales",
        help="validate and normalize one permission-backed JSON sales report",
    )
    sales.add_argument("--input", type=Path, required=True, help="path to the source JSON report")
    sales.add_argument("--source-id", required=True)
    sales.add_argument("--source-name", required=True)
    sales.add_argument("--permission-reference", required=True)
    sales.add_argument(
        "--terms-reviewed-at",
        type=_timestamp,
        required=True,
        help="timezone-aware ISO-8601 timestamp of the operator's terms review",
    )
    sales.add_argument(
        "--output",
        type=Path,
        help="write the normalized result to a new file; existing files are never overwritten",
    )
    return parser


def _result_document(imported: SalesReportImport) -> dict[str, object]:
    observations = imported.observations
    return {
        "schema_version": "mega-market-import-result-v1",
        "report_id": imported.report_id,
        "source_id": imported.source_id,
        "market_code": imported.market_code,
        "generated_at": imported.generated_at.isoformat(),
        "period_start": imported.period_start.isoformat(),
        "period_end": imported.period_end.isoformat(),
        "coverage_complete": imported.coverage_complete,
        "raw_payload_sha256": imported.raw_payload_sha256,
        "observation_count": len(observations),
        "observations": [
            {
                "product_identity_key": item.product_identity_key,
                "source_record_id": item.source_record_id,
                "metric": item.metric,
                "value": str(item.value),
                "unit": item.unit,
                "observed_at": item.observed_at.isoformat(),
                "window_start": item.window_start.isoformat(),
                "window_end": item.window_end.isoformat(),
                "verified": item.verified,
                "reference": item.reference,
                "permission_reference": item.permission_reference,
                "raw_payload_sha256": item.raw_payload_sha256,
                "coverage_complete": item.coverage_complete,
            }
            for item in observations
        ],
        "commercial_authorization": False,
        "decision": "evidence_import_only",
    }


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.command != "import-sales":
        parser.error("unsupported command")

    try:
        raw_payload = args.input.read_bytes()
        descriptor = SourceDescriptor(
            source_id=args.source_id,
            display_name=args.source_name,
            access_mode="manual_import",
            permission_status="approved",
            permission_reference=args.permission_reference,
            terms_reviewed_at=args.terms_reviewed_at,
        )
        imported = import_normalized_sales_report(raw_payload, descriptor)
        rendered = json.dumps(
            _result_document(imported),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n"

        if args.output is None:
            sys.stdout.write(rendered)
        else:
            try:
                with args.output.open("x", encoding="utf-8", newline="\n") as handle:
                    handle.write(rendered)
            except FileExistsError as exc:
                raise FileExistsError(f"output file already exists: {args.output}") from exc
            sys.stdout.write(f"Import result written to {args.output}\n")
        return 0
    except (OSError, TypeError, ValueError) as exc:
        sys.stderr.write(f"mega-market: error: {exc}\n")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
