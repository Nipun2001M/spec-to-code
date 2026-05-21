import sys
import argparse
from datetime import datetime, timezone
from dotenv import load_dotenv

from specs.spec_loader import load_spec
from pipeline.planner import run_planner
from pipeline.approval import request_approval
from pipeline.code_generator import generate_code
from pipeline.test_generator import generate_tests
from pipeline.quality_gates import run_quality_gates
from audit.audit_logger import save_audit

load_dotenv()


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="pipeline",
        description="spec-driven pipeline — loads a spec, plans, generates, tests, and audits",
    )
    parser.add_argument(
        "spec_file",
        help="path to the spec file (.yaml, .yml, .json, or .md)",
    )
    parser.add_argument(
        "--model",
        default="gemini-2.5-flash",
        help="Gemini model name to use (default: gemini-2.5-flash)",
    )
    parser.add_argument(
        "--skip-gates",
        nargs="*",
        metavar="GATE",
        help="quality gate names to skip, e.g. --skip-gates mypy bandit",
    )
    parser.add_argument(
        "--no-strict",
        action="store_true",
        help="load spec in non-strict mode (warnings only, no exit on missing fields)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    print("\n" + "=" * 60)
    print("  SPEC-DRIVEN PIPELINE")
    print("=" * 60)

    # step 1 — load and validate spec
    print(f"\n[step 1/8] loading spec: {args.spec_file}")
    spec = load_spec(args.spec_file, strict=not args.no_strict)
    print(f"  spec '{spec.get('spec_id')}' loaded — feature: {spec.get('feature')}")

    # step 2 — plan with Gemini
    print("\n[step 2/8] generating plan ...")
    plan = run_planner(spec, model_name=args.model)

    # step 3 — approval checkpoint 1 (plan review)
    print("\n[step 3/8] approval checkpoint 1 — plan review")
    approval_1_requested_at = _now_iso()
    request_approval(spec, plan)
    approval_1_granted_at = _now_iso()

    # step 4 — generate code
    print("\n[step 4/8] generating code ...")
    code_results = generate_code(spec, plan, model_name=args.model)

    # step 5 — generate tests
    print("\n[step 5/8] generating tests ...")
    test_results = generate_tests(spec, code_results, model_name=args.model)

    # step 6 — quality gates
    print("\n[step 6/8] running quality gates ...")
    all_gate_names = ["ruff", "mypy", "pytest", "bandit"]
    skip = set(args.skip_gates or [])
    gates_to_run = [g for g in all_gate_names if g not in skip]
    if skip:
        print(f"  skipping gates: {sorted(skip)}")
    gate_results = run_quality_gates(target="output/generated", gates=gates_to_run)

    # step 7 — approval checkpoint 2 (final review before audit close)
    print("\n[step 7/8] approval checkpoint 2 — final review")
    approval_2_requested_at = _now_iso()
    request_approval(spec, plan)
    approval_2_granted_at = _now_iso()

    # step 8 — write final audit log
    print("\n[step 8/8] writing audit log ...")
    audit_path = save_audit(
        spec=spec,
        plan=plan,
        approval_requested_at=approval_1_requested_at,
        approval_granted_at=approval_2_granted_at,
        code_results=code_results,
        test_results=test_results,
        quality_gate_results=gate_results,
    )

    print("\n" + "=" * 60)
    print("  PIPELINE COMPLETE")
    print(f"  spec    : {spec.get('spec_id')} — {spec.get('feature')}")
    print(f"  code    : {sum(1 for r in code_results if r.get('written'))} file(s) written")
    print(f"  tests   : {sum(1 for r in test_results.values() if r.get('written'))}/2 file(s) written")
    print(f"  gates   : {sum(1 for r in gate_results if r.get('passed'))}/{len(gate_results)} passed")
    print(f"  audit   : {audit_path}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
