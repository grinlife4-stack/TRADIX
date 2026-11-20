"""Command-line interface for standalone Bridge package validation/export."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from .archive import export_package, restore_package
from .conformance import ConformanceSuiteError, run_schema_suite
from .generator import create_bridge_scaffold
from .layout import verify_package
from .manifest import ManifestValidationError, load_manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bridex-manifest")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="validate an owner-exportable Bridge package manifest")
    validate.add_argument("path", help="path to bridge manifest JSON")
    package = commands.add_parser("verify-package", help="verify an exported Bridge package directory")
    package.add_argument("directory", help="path to exported package directory")
    export = commands.add_parser("export", help="create a deterministic ZIP export")
    export.add_argument("directory", help="verified Bridge package directory")
    export.add_argument("archive", help="new ZIP output path")
    restore = commands.add_parser("restore", help="safely restore and verify a ZIP package")
    restore.add_argument("archive", help="Bridge package ZIP archive")
    restore.add_argument("directory", help="new restore destination directory")
    conformance = commands.add_parser("conformance", help="run a published OBIS conformance suite")
    conformance.add_argument("layer", choices=["schema"], help="conformance layer")
    conformance.add_argument("suite", help="path to versioned conformance suite JSON")
    scaffold = commands.add_parser("scaffold", help="generate an incomplete, owner-specific Bridge project scaffold")
    scaffold.add_argument("directory", help="new output directory")
    scaffold.add_argument("--bridge-id", required=True)
    scaffold.add_argument("--name", required=True)
    scaffold.add_argument("--version", required=True)
    scaffold.add_argument("--owner-id", required=True)
    scaffold.add_argument("--owner-name", required=True)
    scaffold.add_argument("--operator-id", required=True)
    scaffold.add_argument("--operator-name", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            load_manifest(args.path)
            print("valid: BRIDEX Bridge Package Manifest 0.1")
        elif args.command == "verify-package":
            report = verify_package(args.directory)
            print("valid: BRIDEX portable Bridge package 0.1")
            print(json.dumps(report, sort_keys=True))
        elif args.command == "export":
            report = export_package(args.directory, args.archive)
            print("exported: BRIDEX portable Bridge package 0.1")
            print(json.dumps(report, sort_keys=True))
        elif args.command == "restore":
            report = restore_package(args.archive, args.directory)
            print("restored: BRIDEX portable Bridge package 0.1")
            print(json.dumps(report, sort_keys=True))
        elif args.command == "conformance":
            report = run_schema_suite(args.suite)
            print("passed: OBIS schema conformance suite")
            print(json.dumps(report, sort_keys=True))
        else:
            report = create_bridge_scaffold(
                args.directory, bridge_id=args.bridge_id, name=args.name,
                implementation_version=args.version, owner_id=args.owner_id,
                owner_name=args.owner_name, operator_id=args.operator_id,
                operator_name=args.operator_name,
            )
            print("created: BRIDEX scaffold only; implementation and owner attestation remain pending")
            print(json.dumps(report, sort_keys=True))
    except (ManifestValidationError, ConformanceSuiteError) as exc:
        print(f"invalid: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
