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
CONFIG_PATH = Path("config.yaml")


def _load_allowed_dirs(config_path: Path) -> list[Path]:
    # reads output_dir from config.yaml and returns it as the only allowed root
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    output_dir = config.get("paths", {}).get("output_dir", "output/generated")
    return [Path(output_dir).resolve()]


def _is_path_allowed(filename: str, allowed_dirs: list[Path]) -> bool:
    # resolves the target path and checks it sits inside one of the allowed dirs
    target = Path(filename).resolve()
    return any(
        target == allowed or allowed in target.parents
        for allowed in allowed_dirs
    )


def _build_task_prompt(task: str, spec: dict, plan: dict) -> str:
    context = {
        "feature": spec.get("feature"),
        "spec_id": spec.get("spec_id"),
        "technical_design": plan.get("technical_design", ""),
        "impacted_files": plan.get("impacted_files", []),
    }
    context_yaml = yaml.dump(context, default_flow_style=False, allow_unicode=True)
    return textwrap.dedent(f"""
        You are a senior Python developer implementing a feature for a spec-driven pipeline.

        Context:
        {context_yaml}

        Task to implement:
        {task}

        Return ONLY a single valid JSON object with exactly these two keys:
        - "filename" : relative file path where this code should be saved (e.g. "output/generated/auth/login.py")
        - "content"  : the full file content as a string

        Rules:
        - filename must be inside the "output/generated" directory
        - Do not add markdown fences or any text outside the JSON object
        - Write production-quality, well-structured Python code
        - Use plain # comments only — no docstring blocks
    """).strip()


def _save_audit(spec_id: str, task_index: int, task: str, prompt: str,
                response_text: str, result: dict) -> Path:
    AUDIT_TRACES_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    # strip Windows-illegal chars: \ / : * ? " < > | and collapse whitespace
    safe_task = re.sub(r'[\\/:*?"<>|]', '', task[:40]).strip().replace(" ", "_")
    file_name = f"{timestamp}_{spec_id}_task{task_index:02d}_{safe_task}.json"
    trace_path = AUDIT_TRACES_DIR / file_name

    trace = {
        "spec_id": spec_id,
        "task_index": task_index,
        "task": task,
        "timestamp": timestamp,
        "prompt": prompt,
        "raw_response": response_text,
        "result": result,
    }
    with open(trace_path, "w", encoding="utf-8") as f:
        json.dump(trace, f, indent=2, ensure_ascii=False)

    return trace_path


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
    if text.endswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[:-1])
    return text.strip()


def _fix_invalid_escapes(text: str) -> str:
    # Gemini sometimes embeds Python regex patterns (\w \d \s) in JSON string values.
    # These are invalid JSON escapes. Double the backslash so JSON sees \\w, \\d, etc.
    return re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', text)


def _parse_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(_fix_invalid_escapes(text))


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
                    max_output_tokens=8192,
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


def generate_code(spec: dict, plan: dict,
                  model_name: str = "gemini-2.5-flash",
                  config_path: str = str(CONFIG_PATH)) -> list[dict]:
    # generates code for every task in the plan
    # returns list of dicts: {task, filename, content, written, skipped_reason}

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "GEMINI_API_KEY (or GOOGLE_API_KEY) not set. Add it to your .env file."
        )

    allowed_dirs = _load_allowed_dirs(Path(config_path))
    print(f"[code_generator] allowed output dirs: {[str(d) for d in allowed_dirs]}")

    client = genai.Client(api_key=api_key)

    spec_id = spec.get("spec_id", "unknown")
    tasks = plan.get("tasks", [])

    if not tasks:
        print("[code_generator] no tasks found in plan — nothing to generate.")
        return []

    results = []

    for i, task in enumerate(tasks, 1):
        print(f"\n[code_generator] task {i}/{len(tasks)}: {task}")

        prompt = _build_task_prompt(task, spec, plan)
        raw_text = _call_gemini(prompt, client, model_name)
        clean_text = _strip_fences(raw_text)

        result = {"task": task, "filename": None, "content": None,
                  "written": False, "skipped_reason": None}

        # parse json response
        try:
            data = _parse_json(clean_text)
        except json.JSONDecodeError as exc:
            reason = f"Gemini returned non-JSON: {exc}"
            print(f"  [!] {reason}")
            result["skipped_reason"] = reason
            _save_audit(spec_id, i, task, prompt, raw_text, result)
            results.append(result)
            continue

        filename = data.get("filename")
        content = data.get("content")

        if not filename or not content:
            reason = "response missing 'filename' or 'content' key"
            print(f"  [!] {reason}")
            result["skipped_reason"] = reason
            _save_audit(spec_id, i, task, prompt, raw_text, result)
            results.append(result)
            continue

        result["filename"] = filename
        result["content"] = content

        # path safety check
        if not _is_path_allowed(filename, allowed_dirs):
            reason = (
                f"filename '{filename}' is outside allowed directories "
                f"{[str(d) for d in allowed_dirs]} — skipped for safety"
            )
            print(f"  [!] {reason}")
            result["skipped_reason"] = reason
            _save_audit(spec_id, i, task, prompt, raw_text, result)
            results.append(result)
            continue

        # write file
        out_path = Path(filename)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(content)

        result["written"] = True
        print(f"  [+] written: {filename}")

        trace_path = _save_audit(spec_id, i, task, prompt, raw_text, result)
        print(f"  [audit] trace saved: {trace_path.name}")

        results.append(result)

    # final summary
    written = sum(1 for r in results if r["written"])
    skipped = len(results) - written
    print(f"\n[code_generator] done — {written} file(s) written, {skipped} skipped.")

    return results
