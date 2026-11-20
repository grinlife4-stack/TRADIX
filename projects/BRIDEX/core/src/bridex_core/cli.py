"""Command-line interface for standalone Bridge package validation."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from .manifest import ManifestValidationError, load_manifest


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bridex-manifest")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="validate an owner-exportable Bridge package manifest")
    validate.add_argument("path", help="path to bridge manifest JSON")
    args = parser.parse_args(argv)
    try:
        load_manifest(args.path)
    except ManifestValidationError as exc:
        print(f"invalid: {exc}", file=sys.stderr)
        return 2
    print("valid: BRIDEX Bridge Package Manifest 0.1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
