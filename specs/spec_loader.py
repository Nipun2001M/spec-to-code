import yaml
import json
import re
from pathlib import Path
from specs.spec_validator import validate_spec, SpecValidationError

SUPPORTED_EXTENSIONS = {".yaml", ".yml", ".json", ".md"}


def _parse_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"expected a YAML mapping, got {type(data).__name__}")
    return data


def _parse_json(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"expected a JSON object, got {type(data).__name__}")
    return data


def _parse_markdown(path: Path) -> dict:
    # extracts YAML front matter delimited by ---
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        raise ValueError(
            f"markdown spec must contain a YAML front matter block (--- ... ---): {path}"
        )
    data = yaml.safe_load(match.group(1))
    if not isinstance(data, dict):
        raise ValueError(f"front matter must be a YAML mapping, got {type(data).__name__}")
    return data


def load_spec(file_path: str, strict: bool = True) -> dict:
    # load a single spec file (yaml/json/md), validate it, and return as dict
    # if strict=True raises SpecValidationError on missing fields
    # if strict=False prints warnings and returns the dict anyway
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"spec file not found: {file_path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"unsupported file type '{ext}'. supported: {sorted(SUPPORTED_EXTENSIONS)}"
        )

    # parse
    try:
        if ext in {".yaml", ".yml"}:
            data = _parse_yaml(path)
        elif ext == ".json":
            data = _parse_json(path)
        elif ext == ".md":
            data = _parse_markdown(path)
    except (yaml.YAMLError, json.JSONDecodeError) as exc:
        raise ValueError(f"failed to parse '{path.name}': {exc}") from exc

    # validate
    errors = validate_spec(data)
    if errors:
        spec_id = data.get("spec_id", "<unknown>")
        if strict:
            print(f"\n[spec_loader] validation failed for spec '{spec_id}' in {path.name}:")
            for err in errors:
                print(f"  - {err}")
            raise SpecValidationError(spec_id, errors)
        else:
            print(f"\n[spec_loader] warnings for spec '{spec_id}' in {path.name}:")
            for err in errors:
                print(f"  - {err}")

    return data


def load_all_specs(specs_dir: str, strict: bool = True) -> list[dict]:
    # load every supported spec file under specs_dir recursively
    # returns list of dicts with keys: path, spec
    # failed specs are reported and skipped (never crash the full batch)
    specs_path = Path(specs_dir)
    if not specs_path.is_dir():
        raise NotADirectoryError(f"specs directory not found: {specs_dir}")

    results = []
    files = sorted(
        f for f in specs_path.rglob("*") if f.suffix.lower() in SUPPORTED_EXTENSIONS
    )

    for file in files:
        try:
            spec = load_spec(str(file), strict=strict)
            results.append({"path": str(file), "spec": spec})
        except (SpecValidationError, ValueError, FileNotFoundError) as exc:
            print(f"[spec_loader] skipping '{file.name}': {exc}")

    print(f"[spec_loader] loaded {len(results)}/{len(files)} spec(s) from '{specs_dir}'")
    return results


def get_spec_id(spec: dict) -> str:
    return spec.get("spec_id", "<unknown>")
