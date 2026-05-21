from specs.spec_schema import (
    REQUIRED_TOP_LEVEL_FIELDS,
    VALID_STATUSES,
    USER_STORY_FIELDS,
    BUSINESS_RULE_FIELDS,
    ACCEPTANCE_CRITERIA_FIELDS,
)


class SpecValidationError(Exception):
    def __init__(self, spec_id: str, errors: list[str]):
        self.spec_id = spec_id
        self.errors = errors
        super().__init__(f"spec '{spec_id}' failed validation with {len(errors)} error(s)")


def _check_top_level(spec: dict) -> list[str]:
    errors = [f"missing required field: '{f}'" for f in REQUIRED_TOP_LEVEL_FIELDS if f not in spec]
    status = spec.get("status")
    if status and status not in VALID_STATUSES:
        errors.append(f"invalid status '{status}'; must be one of {sorted(VALID_STATUSES)}")
    return errors


def _check_user_story(spec: dict) -> list[str]:
    user_story = spec.get("user_story", {})
    if not isinstance(user_story, dict):
        return ["user_story must be a mapping"]
    return [f"user_story missing field: '{f}'" for f in USER_STORY_FIELDS if f not in user_story]


def _check_list_items(items: list, field_name: str, required_keys: list[str]) -> list[str]:
    errors = []
    for i, item in enumerate(items):
        for key in required_keys:
            if key not in item:
                errors.append(f"{field_name}[{i}] missing field: '{key}'")
    return errors


def _check_business_rules(spec: dict) -> list[str]:
    rules = spec.get("business_rules", [])
    if not isinstance(rules, list) or len(rules) == 0:
        return ["business_rules must be a non-empty list"]
    return _check_list_items(rules, "business_rules", BUSINESS_RULE_FIELDS)


def _check_acceptance_criteria(spec: dict) -> list[str]:
    criteria = spec.get("acceptance_criteria", [])
    if not isinstance(criteria, list) or len(criteria) == 0:
        return ["acceptance_criteria must be a non-empty list"]
    return _check_list_items(criteria, "acceptance_criteria", ACCEPTANCE_CRITERIA_FIELDS)


def _check_optional_fields(spec: dict) -> list[str]:
    errors = []
    nfr = spec.get("non_functional_requirements")
    if nfr is not None and not isinstance(nfr, dict):
        errors.append("non_functional_requirements must be a mapping")
    oos = spec.get("out_of_scope")
    if oos is not None and not isinstance(oos, list):
        errors.append("out_of_scope must be a list")
    return errors


def validate_spec(spec: dict) -> list[str]:
    errors = []
    errors.extend(_check_top_level(spec))
    errors.extend(_check_user_story(spec))
    errors.extend(_check_business_rules(spec))
    errors.extend(_check_acceptance_criteria(spec))
    errors.extend(_check_optional_fields(spec))
    return errors
