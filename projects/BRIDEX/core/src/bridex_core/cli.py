"""Command-line interface for standalone Bridge package validation."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence

from .layout import verify_package
from .manifest import ManifestValidationError, load_manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bridex-manifest")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="validate an owner-exportable Bridge package manifest")
    validate.add_argument("path", help="path to bridge manifest JSON")
    package = commands.add_parser("verify-package", help="verify an exported Bridge package directory")
    package.add_argument("directory", help="path to exported package directory")
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            load_manifest(args.path)
            print("valid: BRIDEX Bridge Package Manifest 0.1")
        else:
            report = verify_package(args.directory)
            print("valid: BRIDEX portable Bridge package 0.1")
            print(json.dumps(report, sort_keys=True))
    except ManifestValidationError as exc:
        print(f"invalid: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
