from __future__ import annotations
import os
import json
import time
import yaml
import textwrap
from datetime import datetime
from pathlib import Path

from google import genai
from google.genai import types
from google.genai import errors as genai_errors

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

    client = genai.Client(api_key=api_key)

    # Retry up to 3 times with exponential backoff for transient 503 errors
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=8192,
                    response_mime_type="application/json",
                ),
            )
            break  # success — exit the retry loop
        except genai_errors.ServerError as exc:
            if attempt == max_retries:
                raise
            wait = 2 ** attempt
            print(
                f"[planner] Gemini returned {exc.code} ({exc.status}) on attempt {attempt}/{max_retries}. "
                f"Retrying in {wait}s ..."
            )
            time.sleep(wait)
        except genai_errors.ClientError as exc:
            if getattr(exc, "code", None) == 429:
                if attempt == max_retries:
                    raise RuntimeError(
                        "[planner] Gemini rate limit (429) hit after all retries. "
                        "You have likely exhausted your daily free-tier quota for this model. "
                        "Run with --model gemini-2.0-flash which has a higher daily limit."
                    ) from exc
                wait = 65
                print(
                    f"[planner] rate-limited (429) on attempt {attempt}/{max_retries}. "
                    f"Retrying in {wait}s ..."
                )
                time.sleep(wait)
            else:
                raise

    raw_text = response.text.strip()

    # strip markdown fences if the model added them despite instructions
    # handles: ```json\n...\n``` and ```\n...\n```
    if raw_text.startswith("```"):
        lines = raw_text.split("\n")
        raw_text = "\n".join(lines[1:])  # drop opening fence line (``` or ```json)
    if raw_text.endswith("```"):
        lines = raw_text.split("\n")
        raw_text = "\n".join(lines[:-1])  # drop closing fence line
    raw_text = raw_text.strip()

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
