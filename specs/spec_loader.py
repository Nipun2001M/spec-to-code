import yaml
import os
from pathlib import Path


def load_spec(file_path: str) -> dict:
    # load a single spec YAML file and return it as a dict
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"spec file not found: {file_path}")
    if path.suffix not in {".yaml", ".yml"}:
        raise ValueError(f"unsupported file type: {path.suffix}")
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"spec file must be a YAML mapping: {file_path}")
    return data


def load_all_specs(specs_dir: str) -> list[dict]:
    # load every .yaml / .yml file found in specs_dir
    # returns a list of (path, spec_dict) tuples
    results = []
    specs_path = Path(specs_dir)
    if not specs_path.is_dir():
        raise NotADirectoryError(f"specs directory not found: {specs_dir}")
    for file in sorted(specs_path.glob("**/*.yaml")):
        spec = load_spec(str(file))
        results.append({"path": str(file), "spec": spec})
    for file in sorted(specs_path.glob("**/*.yml")):
        spec = load_spec(str(file))
        results.append({"path": str(file), "spec": spec})
    return results


def get_spec_id(spec: dict) -> str:
    # safe helper to retrieve spec_id for logging
    return spec.get("spec_id", "<unknown>")
