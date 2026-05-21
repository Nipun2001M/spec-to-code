from __future__ import annotations
import os
import re
import json
import time
import yaml
import textwrap
from datetime import datetime, timezone
from pathlib import Path

from google import genai
from google.genai import types
from google.genai import errors as genai_errors

AUDIT_TRACES_DIR = Path("audit/traces")
UNIT_TESTS_DIR = Path("tests/unit")
INTEGRATION_TESTS_DIR = Path("tests/integration")


def _format_acceptance_criteria(criteria: list[dict]) -> str:
    lines = []
    for ac in criteria:
        ac_id = ac.get("id", "?")
        lines.append(f"  {ac_id}:")
        lines.append(f"    given: {ac.get('given', '')}")
        lines.append(f"    when:  {ac.get('when', '')}")
        lines.append(f"    then:  {ac.get('then', '')}")
    return "\n".join(lines)


def _format_generated_code(code_results: list[dict]) -> str:
    # only include files that were actually written
    parts = []
    for r in code_results:
        if r.get("written") and r.get("filename") and r.get("content"):
            parts.append(f"# file: {r['filename']}\n{r['content']}")
    return "\n\n".join(parts) if parts else "# no generated code available"


def _build_unit_test_prompt(spec: dict, code_results: list[dict]) -> str:
    feature = spec.get("feature", "unknown feature")
    spec_id = spec.get("spec_id", "unknown")
    criteria = spec.get("acceptance_criteria", [])
    ac_block = _format_acceptance_criteria(criteria)
    code_block = _format_generated_code(code_results)

    return textwrap.dedent(f"""
        You are a senior Python test engineer writing pytest unit tests.

        Feature: {feature} ({spec_id})

        Acceptance Criteria:
        {ac_block}

        Generated Implementation Code:
        {code_block}

        Write unit tests that:
        - have one test function per acceptance criteria ID (name each test_<ac_id_lowercase>)
        - mock all external dependencies (db, api calls, email)
        - use pytest and unittest.mock only — no extra libraries
        - include a comment above each test referencing its AC ID

        Return ONLY a single valid JSON object with:
        - "filename" : "tests/unit/test_{spec_id.lower().replace('-', '_')}.py"
        - "content"  : the full test file as a string

        No markdown fences. No text outside the JSON.
    """).strip()


def _build_integration_test_prompt(spec: dict, code_results: list[dict]) -> str:
    feature = spec.get("feature", "unknown feature")
    spec_id = spec.get("spec_id", "unknown")
    criteria = spec.get("acceptance_criteria", [])
    ac_block = _format_acceptance_criteria(criteria)
    code_block = _format_generated_code(code_results)

    return textwrap.dedent(f"""
        You are a senior Python test engineer writing pytest integration tests.

        Feature: {feature} ({spec_id})

        Acceptance Criteria:
        {ac_block}

        Generated Implementation Code:
        {code_block}

        Write integration tests that:
        - test end-to-end flows combining multiple components
        - have one test function per acceptance criteria ID (name each test_<ac_id_lowercase>_integration)
        - use pytest fixtures for setup/teardown
        - use a real (in-memory or sqlite) database where applicable — mock only external network calls
        - include a comment above each test referencing its AC ID

        Return ONLY a single valid JSON object with:
        - "filename" : "tests/integration/test_{spec_id.lower().replace('-', '_')}_integration.py"
        - "content"  : the full test file as a string

        No markdown fences. No text outside the JSON.
    """).strip()


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = "\n".join(text.split("\n")[1:])
    if text.endswith("```"):
        text = "\n".join(text.split("\n")[:-1])
    return text.strip()


def _fix_invalid_escapes(text: str) -> str:
    # Gemini sometimes embeds Python regex patterns (\w \d \s) in JSON string values.
    # These are invalid JSON escapes. Double the backslash so JSON sees \\w, \\d, etc.
    return re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)


def _on_rate_limit(attempt: int, max_retries: int) -> None:
    if attempt == max_retries:
        raise RuntimeError(
            "Gemini rate limit (429) exhausted after all retries. "
            "Run with --model gemini-2.0-flash for a higher daily quota."
        )
    print(f"  [!] rate-limited (429) on attempt {attempt}/{max_retries}. Retrying in 65s ...")
    time.sleep(65)


def _call_gemini(prompt: str, client: genai.Client, model_name: str) -> str:
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.2,
                    max_output_tokens=4096,
                    response_mime_type="application/json",
                ),
            )
            return response.text
        except genai_errors.ServerError as exc:
            if attempt == max_retries:
                raise
            wait = 2 ** attempt
            print(
                f"  [!] Gemini returned {exc.code} ({exc.status}) on attempt {attempt}/{max_retries}. "
                f"Retrying in {wait}s ..."
            )
            time.sleep(wait)
        except genai_errors.ClientError as exc:
            if getattr(exc, "code", None) == 429:
                _on_rate_limit(attempt, max_retries)
            else:
                raise


def _save_audit(spec_id: str, label: str, prompt: str,
                response_text: str, result: dict) -> Path:
    AUDIT_TRACES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    file_name = f"{timestamp}_{spec_id}_{label}.json"
    trace_path = AUDIT_TRACES_DIR / file_name

    trace = {
        "spec_id": spec_id,
        "label": label,
        "timestamp": timestamp,
        "prompt": prompt,
        "raw_response": response_text,
        "result": result,
    }
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(trace, f, indent=2, ensure_ascii=False)

    return trace_path


def _parse_and_write(raw_text: str, allowed_dirs: list[Path],
                     label: str) -> dict:
    # parses Gemini response and writes the test file if path is safe
    result = {"filename": None, "content": None, "written": False, "skipped_reason": None}

    cleaned = _strip_fences(raw_text)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        try:
            data = json.loads(_fix_invalid_escapes(cleaned))
        except json.JSONDecodeError as exc:
            result["skipped_reason"] = f"non-JSON response: {exc}"
            return result

    filename = data.get("filename")
    content = data.get("content")

    if not filename or not content:
        result["skipped_reason"] = "response missing 'filename' or 'content'"
        return result

    result["filename"] = filename
    result["content"] = content

    # path safety — must be inside one of the allowed test dirs
    target = Path(filename).resolve()
    if not any(allowed in target.parents or target == allowed for allowed in allowed_dirs):
        result["skipped_reason"] = (
            f"'{filename}' is outside allowed test directories — skipped for safety"
        )
        return result

    out_path = Path(filename)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(content)

    result["written"] = True
    return result


def generate_tests(spec: dict, code_results: list[dict],
                   model_name: str = "gemini-2.5-flash") -> dict:
    # generates unit and integration tests for the spec
    # returns dict with keys: unit, integration (each a result dict)

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY (or GOOGLE_API_KEY) not set. Add it to your .env file."
        )

    client = genai.Client(api_key=api_key)

    spec_id = spec.get("spec_id", "unknown")
    allowed_dirs = [
        UNIT_TESTS_DIR.resolve(),
        INTEGRATION_TESTS_DIR.resolve(),
    ]

    output = {}

    # unit tests
    print(f"[test_generator] generating unit tests for '{spec_id}' ...")
    unit_prompt = _build_unit_test_prompt(spec, code_results)
    unit_raw = _call_gemini(unit_prompt, client, model_name)
    unit_result = _parse_and_write(unit_raw, allowed_dirs, "unit")

    if unit_result["written"]:
        print(f"  [+] written: {unit_result['filename']}")
    else:
        print(f"  [!] unit tests skipped: {unit_result['skipped_reason']}")

    trace = _save_audit(spec_id, "unit_tests", unit_prompt, unit_raw, unit_result)
    print(f"  [audit] {trace.name}")
    output["unit"] = unit_result

    # integration tests
    print(f"[test_generator] generating integration tests for '{spec_id}' ...")
    int_prompt = _build_integration_test_prompt(spec, code_results)
    int_raw = _call_gemini(int_prompt, client, model_name)
    int_result = _parse_and_write(int_raw, allowed_dirs, "integration")

    if int_result["written"]:
        print(f"  [+] written: {int_result['filename']}")
    else:
        print(f"  [!] integration tests skipped: {int_result['skipped_reason']}")

    trace = _save_audit(spec_id, "integration_tests", int_prompt, int_raw, int_result)
    print(f"  [audit] {trace.name}")
    output["integration"] = int_result

    written = sum(1 for r in output.values() if r["written"])
    print(f"\n[test_generator] done — {written}/2 test file(s) written.")

    return output
