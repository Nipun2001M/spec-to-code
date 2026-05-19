from specs.spec_schema import (
    REQUIRED_TOP_LEVEL_FIELDS,
    VALID_STATUSES,
    USER_STORY_FIELDS,
    BUSINESS_RULE_FIELDS,
    ACCEPTANCE_CRITERIA_FIELDS,
)


class SpecValidationError(Exception):
    # raised when one or more validation rules fail
    def __init__(self, spec_id: str, errors: list[str]):
        self.spec_id = spec_id
        self.errors = errors
        super().__init__(f"spec '{spec_id}' failed validation with {len(errors)} error(s)")


def validate_spec(spec: dict) -> list[str]:
    # returns a list of error strings; empty list means the spec is valid
    errors = []
    spec_id = spec.get("spec_id", "<unknown>")

    # top-level required fields
    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in spec:
            errors.append(f"missing required field: '{field}'")

    # status must be one of the allowed values
    status = spec.get("status")
    if status and status not in VALID_STATUSES:
        errors.append(f"invalid status '{status}'; must be one of {sorted(VALID_STATUSES)}")

    # user_story sub-fields
    user_story = spec.get("user_story", {})
    if isinstance(user_story, dict):
        for field in USER_STORY_FIELDS:
            if field not in user_story:
                errors.append(f"user_story missing field: '{field}'")
    else:
        errors.append("user_story must be a mapping")

    # business_rules — must be a non-empty list with required keys
    rules = spec.get("business_rules", [])
    if not isinstance(rules, list) or len(rules) == 0:
        errors.append("business_rules must be a non-empty list")
    else:
        for i, rule in enumerate(rules):
            for field in BUSINESS_RULE_FIELDS:
                if field not in rule:
                    errors.append(f"business_rules[{i}] missing field: '{field}'")

    # acceptance_criteria — must be a non-empty list with required keys
    criteria = spec.get("acceptance_criteria", [])
    if not isinstance(criteria, list) or len(criteria) == 0:
        errors.append("acceptance_criteria must be a non-empty list")
    else:
        for i, ac in enumerate(criteria):
            for field in ACCEPTANCE_CRITERIA_FIELDS:
                if field not in ac:
                    errors.append(f"acceptance_criteria[{i}] missing field: '{field}'")

    # non_functional_requirements — must be a mapping
    nfr = spec.get("non_functional_requirements")
    if nfr is not None and not isinstance(nfr, dict):
        errors.append("non_functional_requirements must be a mapping")

    # out_of_scope — must be a list if present
    oos = spec.get("out_of_scope")
    if oos is not None and not isinstance(oos, list):
        errors.append("out_of_scope must be a list")

    return errors


def validate_spec_strict(spec: dict) -> None:
    # raises SpecValidationError if any errors are found
    errors = validate_spec(spec)
    if errors:
        raise SpecValidationError(spec.get("spec_id", "<unknown>"), errors)
