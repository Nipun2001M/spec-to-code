# schema definition for a feature spec
# used by spec_validator to check structure and required fields

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

# required keys inside user_story
USER_STORY_FIELDS = ["as_a", "i_want", "so_that"]

# required keys inside each business_rule item
BUSINESS_RULE_FIELDS = ["id", "rule"]

# required keys inside each acceptance_criteria item
ACCEPTANCE_CRITERIA_FIELDS = ["id", "given", "when", "then"]

# recognised top-level keys inside non_functional_requirements
NFR_KNOWN_GROUPS = {"performance", "security", "availability", "observability"}
