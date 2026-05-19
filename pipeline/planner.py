import os
import json
import yaml
import textwrap
from datetime import datetime
from pathlib import Path

import google.generativeai as genai

# audit traces directory — mirrors config.yaml paths.audit_traces
AUDIT_TRACES_DIR = Path("audit/traces")

# expected top-level keys in the plan returned by Gemini
PLAN_REQUIRED_KEYS = {
    "tasks",
    "technical_design",
    "impacted_files",
    "risks",
    "test_strategy",
}


def _build_prompt(spec: dict) -> str:
    spec_yaml = yaml.dump(spec, default_flow_style=False, allow_unicode=True)
    return textwrap.dedent(f"""
        You are a senior software architect. Given the feature spec below, produce a
        detailed implementation plan as a single JSON object with exactly these keys:

        - tasks           : list of actionable development tasks (strings)
        - technical_design: string describing architecture, patterns, and data flow
        - impacted_files  : list of file paths expected to be created or modified
        - risks           : list of objects with keys "risk" and "mitigation"
        - test_strategy   : string describing unit, integration, and e2e test approach

        Return ONLY valid JSON — no markdown fences, no extra explanation.

        --- SPEC START ---
        {spec_yaml}
        --- SPEC END ---
    """).strip()


def _save_audit(spec_id: str, prompt: str, response_text: str, plan: dict) -> Path:
    AUDIT_TRACES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    file_name = f"{timestamp}_{spec_id}_plan.json"
    trace_path = AUDIT_TRACES_DIR / file_name

    trace = {
        "spec_id": spec_id,
        "timestamp": timestamp,
        "prompt": prompt,
        "raw_response": response_text,
        "plan": plan,
    }
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(trace, f, indent=2, ensure_ascii=False)

    return trace_path


def _validate_plan(plan: dict) -> list[str]:
    return [f"missing key: '{k}'" for k in PLAN_REQUIRED_KEYS if k not in plan]


def run_planner(spec: dict, model_name: str = "gemini-2.5-flash") -> dict:
    # resolve api key
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY (or GOOGLE_API_KEY) not set. Add it to your .env file."
        )

    spec_id = spec.get("spec_id", "unknown")
    prompt = _build_prompt(spec)

    print(f"[planner] calling Gemini ({model_name}) for spec '{spec_id}' ...")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name=model_name)

    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.2,
            max_output_tokens=4096,
        ),
    )

    raw_text = response.text.strip()

    # strip markdown fences if the model added them despite instructions
    if raw_text.startswith("```"):
        raw_text = "\n".join(raw_text.split("\n")[1:])
    if raw_text.endswith("```"):
        raw_text = "\n".join(raw_text.split("\n")[:-1])

    try:
        plan = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        trace_path = _save_audit(spec_id, prompt, raw_text, {})
        raise ValueError(
            f"[planner] Gemini returned non-JSON output for spec '{spec_id}'. "
            f"Raw response saved to {trace_path}. Parse error: {exc}"
        ) from exc

    # validate plan shape
    errors = _validate_plan(plan)
    if errors:
        print(f"[planner] warning — plan for '{spec_id}' is missing keys:")
        for err in errors:
            print(f"  - {err}")

    trace_path = _save_audit(spec_id, prompt, response.text, plan)
    print(f"[planner] plan saved to {trace_path}")

    return plan
