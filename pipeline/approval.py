from __future__ import annotations
import sys


def _wrap_print(text: str, width: int = 56) -> None:
    line = ""
    for word in text.split():
        if len(line) + len(word) + 1 > width:
            print(f"  {line}")
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        print(f"  {line}")


def _print_plan_summary(spec: dict, plan: dict) -> None:
    spec_id = spec.get("spec_id", "<unknown>")
    feature = spec.get("feature", "<unknown>")

    print("\n" + "=" * 60)
    print(f"  PLAN SUMMARY — {feature} ({spec_id})")
    print("=" * 60)

    tasks = plan.get("tasks", [])
    print(f"\nTasks ({len(tasks)}):")
    for i, task in enumerate(tasks, 1):
        print(f"  {i}. {task}")

    print("\nTechnical Design:")
    _wrap_print(plan.get("technical_design", "N/A"))

    impacted = plan.get("impacted_files", [])
    print(f"\nImpacted Files ({len(impacted)}):")
    for f in impacted:
        print(f"  - {f}")

    risks = plan.get("risks", [])
    print(f"\nRisks ({len(risks)}):")
    for r in risks:
        if isinstance(r, dict):
            print(f"  ! {r.get('risk', r)}")
            if "mitigation" in r:
                print(f"    -> {r['mitigation']}")
        else:
            print(f"  ! {r}")

    print("\nTest Strategy:")
    _wrap_print(plan.get("test_strategy", "N/A"))

    print("\n" + "=" * 60)


def request_approval(spec: dict, plan: dict) -> bool:
    _print_plan_summary(spec, plan)

    while True:
        answer = input("\nApprove this plan and continue? [yes/no]: ").strip().lower()
        if answer in {"yes", "y"}:
            print("[approval] plan approved — continuing pipeline.\n")
            return True
        elif answer in {"no", "n"}:
            print("[approval] plan rejected — pipeline stopped. No files were generated.")
            sys.exit(0)
        else:
            print("  please type 'yes' or 'no'.")
