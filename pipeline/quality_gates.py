from __future__ import annotations
import sys
import json
import subprocess
from datetime import datetime
from pathlib import Path

AUDIT_LOGS_DIR = Path("audit/logs")

# gate definitions: name, command template (target path inserted at runtime)
GATES = [
    {
        "name": "ruff",
        "cmd": ["ruff", "check", "{target}"],
        "description": "linting",
    },
    {
        "name": "mypy",
        "cmd": ["mypy", "{target}", "--ignore-missing-imports"],
        "description": "type checking",
    },
    {
        "name": "pytest",
        "cmd": ["pytest", "{target}", "-v", "--tb=short"],
        "description": "unit and integration tests",
    },
    {
        "name": "bandit",
        "cmd": ["bandit", "-r", "{target}", "-ll"],
        "description": "security scanning",
    },
]


def _run_gate(gate: dict, target: str) -> dict:
    cmd = [part.replace("{target}", target) for part in gate["cmd"]]
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
        )
        passed = proc.returncode == 0
        stdout = proc.stdout
        stderr = proc.stderr
        error = None
    except FileNotFoundError:
        passed = False
        stdout = ""
        stderr = ""
        error = f"tool '{gate['name']}' not found — is it installed and on PATH?"

    return {
        "gate": gate["name"],
        "description": gate["description"],
        "target": target,
        "timestamp": timestamp,
        "cmd": cmd,
        "passed": passed,
        "returncode": proc.returncode if error is None else None,
        "stdout": stdout,
        "stderr": stderr,
        "error": error,
    }


def _save_result(result: dict) -> Path:
    AUDIT_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    status = "pass" if result["passed"] else "fail"
    file_name = f"{result['timestamp']}_{result['gate']}_{status}.json"
    log_path = AUDIT_LOGS_DIR / file_name
    with open(log_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    return log_path


def _print_result(result: dict) -> None:
    icon = "✓" if result["passed"] else "✗"
    status = "PASS" if result["passed"] else "FAIL"
    print(f"  [{icon}] {result['gate']} ({result['description']}) — {status}")
    if not result["passed"]:
        if result["error"]:
            print(f"      error: {result['error']}")
        if result["stdout"].strip():
            for line in result["stdout"].strip().splitlines()[-20:]:
                print(f"      {line}")
        if result["stderr"].strip():
            for line in result["stderr"].strip().splitlines()[-10:]:
                print(f"      {line}")


def run_quality_gates(target: str = ".", gates: list | None = None) -> list:
    # runs all (or a named subset of) quality gates against target path
    # stops and exits the pipeline on the first failure
    # returns list of result dicts for all gates that ran

    selected = (
        [g for g in GATES if g["name"] in gates]
        if gates
        else GATES
    )

    print(f"\n[quality_gates] running {len(selected)} gate(s) on '{target}' ...")
    print("=" * 60)

    results = []

    for gate in selected:
        result = _run_gate(gate, target)
        log_path = _save_result(result)
        _print_result(result)
        print(f"      audit: {log_path.name}")
        results.append(result)

        if not result["passed"]:
            print("\n" + "=" * 60)
            print(f"[quality_gates] PIPELINE STOPPED — '{result['gate']}' gate failed.")
            print(f"  Fix the issue above and re-run the pipeline.")
            print(f"  Full details saved to: {log_path}")
            print("=" * 60)
            sys.exit(1)

    print("=" * 60)
    print(f"[quality_gates] all {len(results)} gate(s) passed.\n")
    return results
