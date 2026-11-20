from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from .controls import ControlState, ExecutionGate
from .filesystem import FilesystemAdapter
from .registry import EcosystemRegistry, ProjectRegistry, RegistryError, load_registry
from .runner import ScanRunner
from .store import ProjectStore
from .transfer import TransferError, export_store, import_store

def _controls(path: str):
    try:
        data = json.loads(Path(path).expanduser().read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot load controls: {exc}") from exc
    allowed = {"global_enabled", "enabled_projects", "enabled_subsystems", "enabled_sources", "authorized_actors"}
    if not isinstance(data, dict) or set(data) - allowed:
        raise ValueError("controls file contains unknown fields")
    actors = set()
    for item in data.get("authorized_actors", []):
        if not isinstance(item, list) or len(item) != 5 or any(not isinstance(x, str) or not x for x in item):
            raise ValueError("authorized_actors entries must contain five non-empty strings")
        actors.add(tuple(item))
    state = ControlState(
        global_enabled=data.get("global_enabled", False),
        enabled_projects=frozenset(data.get("enabled_projects", [])),
        enabled_subsystems=frozenset(tuple(x) for x in data.get("enabled_subsystems", [])),
        enabled_sources=frozenset(tuple(x) for x in data.get("enabled_sources", [])),
    )
    return state, actors

def _projects(registry: ProjectRegistry | EcosystemRegistry):
    return registry.projects if isinstance(registry, EcosystemRegistry) else (registry,)

def build_parser():
    parser = argparse.ArgumentParser(prog="ecoscan", description="Independent local-only ECOSCAN inventory")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate-registry")
    validate.add_argument("registry")
    scan = sub.add_parser("scan")
    scan.add_argument("--registry", required=True)
    scan.add_argument("--controls", required=True)
    scan.add_argument("--actor", required=True)
    scan.add_argument("--scope", choices=["ecosystem", "project", "section", "source"], default="ecosystem")
    scan.add_argument("--project")
    scan.add_argument("--section")
    scan.add_argument("--source")
    scan.add_argument("--db-dir", default=".ecoscan/db")
    scan.add_argument("--export-dir", default=".ecoscan/exports")
    scan.add_argument("--format", choices=["json", "jsonl", "both"], default="both")
    export = sub.add_parser("export")
    export.add_argument("--project", required=True)
    export.add_argument("--db-dir", default=".ecoscan/db")
    export.add_argument("--output-dir", required=True)
    export.add_argument("--format", choices=["json", "jsonl", "both"], default="both")
    imp = sub.add_parser("import")
    imp.add_argument("--project", required=True)
    imp.add_argument("--db-dir", default=".ecoscan/db")
    imp.add_argument("--file", required=True)
    return parser

def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate-registry":
            registry = load_registry(args.registry)
            projects = _projects(registry)
            print(json.dumps({"status": "VALID", "project_count": len(projects), "source_count": sum(len(p.sources) for p in projects)}, ensure_ascii=False))
            return 0
        if args.command == "export":
            store = ProjectStore(args.db_dir, args.project)
            paths = export_store(store, args.output_dir, args.format)
            print(json.dumps({"project_id": args.project, "exports": [str(p) for p in paths]}))
            return 0
        if args.command == "import":
            store = ProjectStore(args.db_dir, args.project)
            count = import_store(args.file, store)
            print(json.dumps({"project_id": args.project, "records_imported": count}))
            return 0
        registry = load_registry(args.registry)
        projects = _projects(registry)
        if args.scope == "project" and not args.project:
            raise ValueError("project scope requires --project")
        if args.scope == "section" and (not args.project or not args.section):
            raise ValueError("section scope requires --project and --section")
        if args.scope == "source" and (not args.project or not args.source):
            raise ValueError("source scope requires --project and --source")
        if args.scope == "ecosystem" and any((args.project, args.section, args.source)):
            raise ValueError("ecosystem scope does not accept selectors")
        state, actors = _controls(args.controls)
        authorizer = lambda actor, project, owner, operator, source: (actor, project, owner, operator, source) in actors
        gate = ExecutionGate(state, authorizer)
        base_dir = Path(args.registry).expanduser().resolve().parent
        adapter = FilesystemAdapter(base_dir, allowed_root=base_dir.parent)
        outcomes = []
        exports = []
        for project in projects:
            if args.scope in {"project", "section", "source"} and project.project_id != args.project:
                continue
            sources = list(project.sources)
            if args.scope == "section":
                sources = [s for s in sources if s.subsystem_id == args.section]
            if args.scope == "source":
                sources = [s for s in sources if s.source_id == args.source]
            if args.scope == "source" and not sources:
                raise ValueError("source is not registered in selected project")
            if args.scope == "section" and not sources:
                raise ValueError("section is not registered in selected project")
            store = ProjectStore(args.db_dir, project.project_id)
            runner = ScanRunner(project, gate, {"filesystem": adapter}, store)
            for source in sources:
                outcome = runner.run(source.source_id, args.actor)
                outcomes.append({"scan_id": outcome.scan_id, "project_id": outcome.project_id, "source_id": outcome.source_id, "coverage_state": outcome.coverage_state, "reason_code": outcome.reason_code, "measurements_written": outcome.measurements_written})
            if args.export_dir and sources:
                exports.extend(str(p) for p in export_store(store, args.export_dir, args.format))
        if args.scope == "project" and not any(p.project_id == args.project for p in projects):
            raise ValueError("unknown project")
        print(json.dumps({"outcomes": outcomes, "exports": exports}, ensure_ascii=False, indent=2))
        return 2 if any(x["coverage_state"] in {"FAILED", "NOT_AUTHORIZED", "NOT_CONFIGURED"} for x in outcomes) else 0
    except (RegistryError, TransferError, ValueError) as exc:
        print(f"ECOSCAN: {exc}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
