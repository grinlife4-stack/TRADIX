"""Independent, deterministic review gate for the first-run demo artifact."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


FORBIDDEN_MARKERS = (
    "eval(",
    "exec(",
    "os.system",
    "subprocess.",
    "pickle.",
    "socket.",
    "requests.",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def review(workspace: Path) -> dict:
    source = workspace / "src" / "text_tools.py"
    tests = workspace / "tests" / "test_text_tools.py"
    checks: list[dict[str, str]] = []

    for label, path in (("source_exists", source), ("tests_exist", tests)):
        checks.append({"check": label, "result": "PASS" if path.is_file() else "FAIL"})

    if source.is_file():
        source_text = source.read_text(encoding="utf-8")
        checks.append({
            "check": "public_function_signature",
            "result": "PASS" if re.search(r"^def slugify\(value: str\) -> str:", source_text, re.M) else "FAIL",
        })
        checks.append({
            "check": "forbidden_execution_and_network_markers",
            "result": "PASS" if not any(marker in source_text for marker in FORBIDDEN_MARKERS) else "FAIL",
        })
    if tests.is_file():
        test_text = tests.read_text(encoding="utf-8")
        checks.append({
            "check": "normalization_and_type_error_tests",
            "result": "PASS" if "test_slugify_normalizes_text" in test_text and "test_slugify_rejects_non_string_input" in test_text else "FAIL",
        })

    hashes = {}
    for label, path in (("source", source), ("tests", tests)):
        if path.is_file():
            hashes[label] = sha256(path)

    passed = bool(checks) and all(item["result"] == "PASS" for item in checks)
    return {
        "reviewer": "separate_static_rule_process",
        "status": "PASS" if passed else "FAIL",
        "checks": checks,
        "sha256": hashes,
        "limitations": [
            "This is deterministic static review, not an independent AI code review.",
            "It does not prove semantic correctness beyond the executed tests and listed checks."
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()

    result = review(args.workspace.resolve())
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
