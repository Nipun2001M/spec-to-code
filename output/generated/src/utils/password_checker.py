import re

def check_password_strength(password: str) -> dict:
    """
    Checks the strength of a given password against a set of predefined rules.

    Args:
        password (str): The password string to check.

    Returns:
        dict: A dictionary containing the 'score' (number of met rules)
              and 'failed_rules' (list of IDs for unmet rules).
    """
    score = 0
    failed_rules = []

    # Define password strength rules with their IDs and check functions.
    # Each check function takes the password string as an argument and returns a boolean.
    rules = [
        {
            "id": "BR-001",
            "check": lambda p: len(p) >= 8,
            "description": "Password must be at least 8 characters long."
        },
        {
            "id": "BR-002",
            "check": lambda p: bool(re.search(r"[A-Z]", p)),
            "description": "Password must contain at least one uppercase letter."
        },
        {
            "id": "BR-003",
            "check": lambda p: bool(re.search(r"[a-z]", p)),
            "description": "Password must contain at least one lowercase letter."
        },
        {
            "id": "BR-004",
            "check": lambda p: bool(re.search(r"[0-9]", p)),
            "description": "Password must contain at least one digit."
        },
        {
            "id": "BR-005",
            "check": lambda p: bool(re.search(r"[^a-zA-Z0-9]", p)),
            "description": "Password must contain at least one special character."
        },
    ]

    # Iterate through each rule to calculate the score and identify failed rules.
    for rule in rules:
        if rule["check"](password):
            score += 1
        else:
            failed_rules.append(rule["id"])

    return {
        "score": score,
        "failed_rules": failed_rules
    }
