REQUIRED_TOP_LEVEL_FIELDS = [
    "spec_id",
    "feature",
    "status",
    "owner",
    "created_at",
    "objective",
    "user_story",
    "business_rules",
    "acceptance_criteria",
    "non_functional_requirements",
    "out_of_scope",
]

VALID_STATUSES = {"draft", "reviewed", "approved"}

USER_STORY_FIELDS = ["as_a", "i_want", "so_that"]

BUSINESS_RULE_FIELDS = ["id", "rule"]

ACCEPTANCE_CRITERIA_FIELDS = ["id", "given", "when", "then"]
