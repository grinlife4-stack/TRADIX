"""Run a bounded, deterministic first execution of the TRADIX factory.

This proves task validation, plan parsing, isolated artifact creation, test execution,
a separate static review process, and evidence reporting. It does not call an LLM.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime, timezone

from tradix.factory.model_contract import ModelResponse, PlanDocument
from tradix.factory.task_contract import RiskClass, TaskEnvelope, TaskState, transition_task


ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, default=ROOT / "examples/first_run/request.json")
    parser.add_argument("--plan", type=Path, default=ROOT / "examples/first_run/plan.json")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"output directory must be empty: {output}")
    output.mkdir(parents=True, exist_ok=True)

    task = TaskEnvelope.from_mapping(read_json(args.request))
    plan_payload = read_json(args.plan)
    plan_response = ModelResponse(
        provider="deterministic_fixture",
        model_id="first-run-plan-v1",
        output_text=json.dumps(plan_payload),
        request_id=f"fixture-{task.task_id}",
    )
    plan = PlanDocument.from_model_response(plan_response)

    events_path = output / "event_log.jsonl"
    event_number = 0
    current = TaskState.QUEUED

    def move(target: TaskState, evidence: tuple[str, ...] = ()) -> None:
        nonlocal current, event_number
        previous = current
        current = transition_task(task, current, target, evidence_refs=evidence)
        event_number += 1
        event = {
            "event_number": event_number,
            "task_id": task.task_id,
            "from_state": previous.value,
            "to_state": current.value,
            "actor": "factory_demo_runner",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "idempotency_key": f"{task.task_id}:{event_number}:{current.value}",
        }
        with events_path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, sort_keys=True) + "\n")

    move(TaskState.PLANNED)

    template_root = ROOT / "examples/first_run/templates"
    generated_source = output / "src/text_tools.py"
    generated_tests = output / "tests/test_text_tools.py"
    generated_source.parent.mkdir(parents=True, exist_ok=True)
    generated_tests.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(template_root / "text_tools.py", generated_source)
    shutil.copyfile(template_root / "test_text_tools.py", generated_tests)
    move(TaskState.IMPLEMENTING)
    move(TaskState.TESTING)

    test_command = [
        sys.executable, "-m", "pytest", "-q", str(generated_tests),
    ]
    test_run = subprocess.run(
        test_command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    test_report = {
        "command": test_command,
        "exit_code": test_run.returncode,
        "stdout": test_run.stdout,
        "stderr": test_run.stderr,
        "status": "PASS" if test_run.returncode == 0 else "FAIL",
    }
    test_report_path = output / "test_report.json"
    write_json(test_report_path, test_report)

    if test_run.returncode != 0:
        failure = {
            "task_id": task.task_id,
            "status": "FAILED",
            "last_state": current.value,
            "failed_stage": "generated_tests",
            "test_report": str(test_report_path.relative_to(output)),
            "execution_mode": "deterministic_fixture_no_llm",
        }
        write_json(output / "factory_report.json", failure)
        print(json.dumps(failure, indent=2))
        return 1

    move(TaskState.REVIEW, (str(test_report_path),))
    review_report_path = output / "review_report.json"
    review_command = [
        sys.executable,
        str(ROOT / "scripts/review_factory_demo.py"),
        "--workspace", str(output),
        "--report", str(review_report_path),
    ]
    review_run = subprocess.run(
        review_command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=60,
        check=False,
    )
    if review_run.returncode != 0:
        failure = {
            "task_id": task.task_id,
            "status": "FAILED",
            "last_state": current.value,
            "failed_stage": "static_review",
            "review_stdout": review_run.stdout,
            "review_stderr": review_run.stderr,
            "execution_mode": "deterministic_fixture_no_llm",
        }
        write_json(output / "factory_report.json", failure)
        print(json.dumps(failure, indent=2))
        return 1

    move(TaskState.CANDIDATE, (str(review_report_path),))
    artifact_paths = [
        generated_source, generated_tests, test_report_path, review_report_path, events_path
    ]
    report = {
        "task_id": task.task_id,
        "title": task.title,
        "status": "CANDIDATE",
        "final_state": current.value,
        "execution_mode": "deterministic_fixture_no_llm",
        "model_provider_called": False,
        "plan_summary": plan.summary,
        "plan_steps": len(plan.steps),
        "tests": {
            "status": test_report["status"],
            "output": test_report["stdout"].strip(),
        },
        "static_review": "PASS",
        "deployment": "NOT_ATTEMPTED",
        "approval_required": task.approval_required,
        "evidence": {
            "test_report": "test_report.json",
            "review_report": "review_report.json",
            "event_log": "event_log.jsonl",
        },
        "artifacts": {
            str(path.relative_to(output)): {
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in artifact_paths
        },
        "limitations": [
            "Implementation was materialized from a reviewed deterministic template, not generated by an LLM.",
            "Static review is not an independent semantic code review.",
            "Candidate was not deployed.",
            "This run does not persist events to Neon or artifacts to B2."
        ],
    }
    write_json(output / "factory_report.json", report)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
