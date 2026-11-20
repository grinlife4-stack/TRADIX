"""Command-line interface for the standalone BRIDEX engineering plane."""

from __future__ import annotations

import argparse
import json
import sys

from .manifest import BridgeManifestError, load_manifest, resolve_package_files
from .package import build_package, verify_package
from .scaffold import create_bridge_project


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bridex", description="Validate and package independent Bridge tools.")
    commands = parser.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="generate an independent draft-only Bridge project")
    init.add_argument("--path", required=True, help="new Bridge project directory")
    init.add_argument("--name", required=True)
    init.add_argument("--owner-id", required=True)
    init.add_argument("--owner-assignment-ref", required=True)
    init.add_argument("--operator-id", required=True)
    init.add_argument("--operator-assignment-ref", required=True)
    init.add_argument("--version", default="0.1.0")
    init.add_argument("--bridge-id", help="optional urn:uuid identifier; generated when omitted")

    validate = commands.add_parser("validate", help="validate bridge.json and its explicit package file set")
    validate.add_argument("--root", required=True, help="Bridge source root containing bridge.json")

    package = commands.add_parser("package", help="create a deterministic, integrity-manifested Bridge ZIP")
    package.add_argument("--root", required=True, help="Bridge source root containing bridge.json")
    package.add_argument("--output", required=True, help="output ZIP path outside the source root")

    verify = commands.add_parser("verify", help="verify a BRIDEX package without extracting or executing it")
    verify.add_argument("package", help="Bridge package ZIP")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "init":
            root = create_bridge_project(
                args.path,
                name=args.name,
                owner_id=args.owner_id,
                owner_assignment_ref=args.owner_assignment_ref,
                operator_id=args.operator_id,
                operator_assignment_ref=args.operator_assignment_ref,
                version=args.version,
                bridge_id=args.bridge_id,
            )
            _, manifest = load_manifest(root)
            result = {
                "created": True,
                "path": str(root),
                "bridge_id": manifest["bridge_id"],
                "lifecycle": manifest["lifecycle"],
            }
        elif args.command == "validate":
            root, manifest = load_manifest(args.root)
            files = resolve_package_files(root, manifest)
            result = {
                "valid": True,
                "bridge_id": manifest["bridge_id"],
                "version": manifest["version"],
                "package_file_count": len(files),
            }
        elif args.command == "package":
            result = build_package(args.root, args.output)
        else:
            result = verify_package(args.package)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except (BridgeManifestError, OSError, ValueError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
