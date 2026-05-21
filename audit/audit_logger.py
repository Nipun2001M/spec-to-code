from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

AUDIT_LOGS_DIR = Path("audit/logs")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_audit_record(
    spec: dict,
    plan: dict,
    approval_requested_at: str,
    approval_granted_at: str,
    code_results: list[dict],
    test_results: dict,
    quality_gate_results: list[dict],
) -> dict:
    return {
        "pipeline_run": {
            "completed_at": _now_iso(),
            "spec_id": spec.get("spec_id"),
            "spec_version": spec.get("version", "1.0.0"),
            "feature": spec.get("feature"),
            "status": spec.get("status"),
            "owner": spec.get("owner"),
        },
        "spec_snapshot": spec,
        "plan": {
            "tasks": plan.get("tasks", []),
            "technical_design": plan.get("technical_design"),
            "impacted_files": plan.get("impacted_files", []),
            "risks": plan.get("risks", []),
            "test_strategy": plan.get("test_strategy"),
        },
        "approval": {
            "requested_at": approval_requested_at,
            "granted_at": approval_granted_at,
        },
        "code_generation": {
            "total_tasks": len(code_results),
            "written": sum(1 for r in code_results if r.get("written")),
            "skipped": sum(1 for r in code_results if not r.get("written")),
            "files": [
                {
                    "task": r.get("task"),
                    "filename": r.get("filename"),
                    "written": r.get("written"),
                    "skipped_reason": r.get("skipped_reason"),
                    "content_length": len(r.get("content") or ""),
                }
                for r in code_results
            ],
        },
        "test_generation": {
            "unit": {
                "filename": test_results.get("unit", {}).get("filename"),
                "written": test_results.get("unit", {}).get("written", False),
                "skipped_reason": test_results.get("unit", {}).get("skipped_reason"),
            },
            "integration": {
                "filename": test_results.get("integration", {}).get("filename"),
                "written": test_results.get("integration", {}).get("written", False),
                "skipped_reason": test_results.get("integration", {}).get("skipped_reason"),
            },
        },
        "quality_gates": [
            {
                "gate": r.get("gate"),
                "description": r.get("description"),
                "passed": r.get("passed"),
                "returncode": r.get("returncode"),
                "timestamp": r.get("timestamp"),
                "cmd": r.get("cmd"),
                "stdout_tail": (r.get("stdout") or "").strip().splitlines()[-20:],
                "stderr_tail": (r.get("stderr") or "").strip().splitlines()[-10:],
                "error": r.get("error"),
            }
            for r in quality_gate_results
        ],
        "quality_gates_summary": {
            "total": len(quality_gate_results),
            "passed": sum(1 for r in quality_gate_results if r.get("passed")),
            "failed": sum(1 for r in quality_gate_results if not r.get("passed")),
            "all_passed": all(r.get("passed") for r in quality_gate_results),
        },
    }


def save_audit(
    spec: dict,
    plan: dict,
    approval_requested_at: str,
    approval_granted_at: str,
    code_results: list[dict],
    test_results: dict,
    quality_gate_results: list[dict],
) -> Path:
    AUDIT_LOGS_DIR.mkdir(parents=True, exist_ok=True)

    spec_id = spec.get("spec_id", "unknown")
    filename = f"{_timestamp_slug()}_{spec_id}_final_audit.json"
    audit_path = AUDIT_LOGS_DIR / filename

    record = build_audit_record(
        spec=spec,
        plan=plan,
        approval_requested_at=approval_requested_at,
        approval_granted_at=approval_granted_at,
        code_results=code_results,
        test_results=test_results,
        quality_gate_results=quality_gate_results,
    )

    with open(audit_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2, ensure_ascii=False)

    print(f"[audit_logger] final audit saved to: {audit_path}")
    return audit_path
