"""Minimal offline ECOSCAN administration CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .registry import RegistryError, load_registry
from .store import ProjectStore, StoreError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ecoscan")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate-registry", help="validate a project source registry")
    validate.add_argument("registry", type=Path)

    initialize = commands.add_parser("init-store", help="initialize one project's local SQLite store")
    initialize.add_argument("--data-root", type=Path, required=True)
    initialize.add_argument("--project-id", required=True)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate-registry":
            registry = load_registry(args.registry)
            print(json.dumps({
                "status": "VALID",
                "schema_version": registry.schema_version,
                "project_id": registry.project_id,
                "source_count": len(registry.sources),
            }, sort_keys=True))
            return 0
        if args.command == "init-store":
            store = ProjectStore(args.data_root, args.project_id)
            print(json.dumps({"status": "INITIALIZED", "project_id": args.project_id, "path": str(store.path)}))
            return 0
    except (RegistryError, StoreError, OSError) as exc:
        print(json.dumps({"status": "REJECTED", "error": str(exc)}, sort_keys=True))
        return 2
    return 2
