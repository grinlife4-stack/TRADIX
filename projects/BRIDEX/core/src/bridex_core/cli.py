"""Command-line entry point for the standalone BRIDEX generator."""

from __future__ import annotations

import argparse
import json

from .generator import create_bridge_project
from .manifest import load_manifest
from .package import package_bridge


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bridex", description="Generate and validate independent Bridge projects"
    )
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="create a new draft Bridge project")
    init.add_argument("--path", required=True)
    init.add_argument("--bridge-id", required=True)
    init.add_argument("--name", required=True)
    init.add_argument("--version", default="0.1.0")
    init.add_argument("--owner-id", required=True)
    init.add_argument("--owner-assignment-ref", required=True)
    init.add_argument("--operator-id", required=True)
    init.add_argument("--operator-assignment-ref", required=True)

    validate = commands.add_parser("validate", help="validate ownership and protocol manifest")
    validate.add_argument("path")

    package = commands.add_parser("package", help="create an allowlisted source package")
    package.add_argument("path")
    package.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init":
            path = create_bridge_project(
                args.path,
                bridge_id=args.bridge_id,
                name=args.name,
                version=args.version,
                owner_id=args.owner_id,
                owner_assignment_ref=args.owner_assignment_ref,
                operator_id=args.operator_id,
                operator_assignment_ref=args.operator_assignment_ref,
            )
            print(str(path))
        elif args.command == "validate":
            manifest = load_manifest(args.path)
            print(json.dumps({
                "valid": True,
                "bridge_id": manifest["bridge_id"],
                "lifecycle": manifest["lifecycle"],
            }, sort_keys=True))
        elif args.command == "package":
            path, digest = package_bridge(args.path, args.output)
            print(json.dumps({"package": str(path), "sha256": digest}, sort_keys=True))
        return 0
    except (ValueError, FileExistsError, OSError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, sort_keys=True))
        return 2
