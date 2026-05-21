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
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    match = re.match(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    if not match:
        raise ValueError(f"markdown spec must contain a YAML front matter block (--- ... ---): {path}")
    data = yaml.safe_load(match.group(1))
    if not isinstance(data, dict):
        raise ValueError(f"front matter must be a YAML mapping, got {type(data).__name__}")
    return data


def _parse(path: Path, ext: str) -> dict:
    try:
        if ext in {".yaml", ".yml"}:
            return _parse_yaml(path)
        if ext == ".json":
            return _parse_json(path)
        return _parse_markdown(path)
    except (yaml.YAMLError, json.JSONDecodeError) as exc:
        raise ValueError(f"failed to parse '{path.name}': {exc}") from exc


def load_spec(file_path: str, strict: bool = True) -> dict:
    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(f"spec file not found: {file_path}")

    ext = path.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"unsupported file type '{ext}'. supported: {sorted(SUPPORTED_EXTENSIONS)}")

    data = _parse(path, ext)

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
