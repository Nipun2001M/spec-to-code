import sys


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

    print(f"\nTechnical Design:")
    design = plan.get("technical_design", "N/A")
    # wrap long design text to 56 chars
    words, line = [], ""
    for word in design.split():
        if len(line) + len(word) + 1 > 56:
            print(f"  {line}")
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        print(f"  {line}")

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

    print(f"\nTest Strategy:")
    strategy = plan.get("test_strategy", "N/A")
    words, line = [], ""
    for word in strategy.split():
        if len(line) + len(word) + 1 > 56:
            print(f"  {line}")
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        print(f"  {line}")

    print("\n" + "=" * 60)


def request_approval(spec: dict, plan: dict) -> bool:
    # prints the plan summary and prompts the user for approval
    # returns True if approved, exits the process if rejected
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
