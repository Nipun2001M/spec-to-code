# spec-driven-pipeline

A Python pipeline that reads a feature spec (YAML) and uses the Gemini API to generate code and tests for it, then runs quality checks and saves an audit log.

## Setup

```bash
git clone https://github.com/Nipun2001M/spec-to-code.git
cd spec-to-code
python -m venv .venv
.venv\Scripts\activate
pip install google-generativeai pyyaml python-dotenv ruff mypy pytest bandit
```

Copy `.env.template` to `.env` and add your Gemini API key:

```
GEMINI_API_KEY=your-key-here
```

Get a key at https://aistudio.google.com/app/apikey

## Usage

```bash
python pipeline.py specs/raw/password_strength.yaml
```

Optional flags:

- `--model gemini-2.0-flash` — use a different model
- `--skip-gates mypy bandit` — skip specific quality gates
- `--no-strict` — show warnings instead of failing on spec errors

## How it works

1. Loads and validates the spec file
2. Calls Gemini to generate an implementation plan
3. You review and approve the plan
4. Gemini generates code into `output/generated/`
5. Gemini generates tests into `tests/`
6. Runs ruff, mypy, pytest, bandit on the generated code
7. You do a final review
8. Saves an audit log to `audit/logs/`

## Writing a spec

Put spec files in `specs/raw/`. See `specs/raw/password_strength.yaml` for an example. Required fields:

```yaml
spec_id: "feat-001"
feature: "User Login"
status: "draft"
owner: "auth-team"
created_at: "2026-05-19"
objective: >
  Why this feature exists.
user_story:
  as_a: "registered user"
  i_want: "to log in with email and password"
  so_that: "I can access my account"
business_rules:
  - id: BR-001
    rule: "Accounts lock after 5 failed attempts"
acceptance_criteria:
  - id: AC-001
    given: "a user with valid credentials"
    when: "they submit the login form"
    then: "they receive a JWT"
non_functional_requirements:
  performance:
    - "respond within 300ms"
out_of_scope:
  - "OAuth / social login"
```

## Folder structure

```
spec-to-code/
├── pipeline.py
├── config.yaml
├── .env.template
├── specs/
│   ├── raw/              # put spec files here
│   ├── spec_loader.py
│   ├── spec_validator.py
│   └── spec_schema.py
├── pipeline/
│   ├── planner.py
│   ├── approval.py
│   ├── code_generator.py
│   ├── test_generator.py
│   └── quality_gates.py
├── output/
│   └── generated/
├── tests/
│   ├── unit/
│   └── integration/
└── audit/
    ├── audit_logger.py
    ├── logs/
    └── traces/
```
