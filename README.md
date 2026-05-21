# spec-driven-pipeline

A Python pipeline that turns structured feature specs into working code, tests, and audit trails — powered by the Gemini API.

You write a YAML (or JSON or Markdown) spec describing what a feature should do. The pipeline plans it, generates code, writes tests, runs quality gates, and logs everything.

---

## How it works

```
spec file → load & validate → Gemini plans → approval 1
         → Gemini generates code → Gemini generates tests
         → ruff + mypy + pytest + bandit → approval 2 → audit log
```

---

## Setup

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/Nipun2001M/spec-to-code.git
cd spec-to-code
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
```

### 2. Install dependencies

```bash
pip install google-generativeai pyyaml python-dotenv ruff mypy pytest bandit
```

### 3. Configure environment

```bash
cp .env.template .env
```

Open `.env` and set your Gemini API key:

```
GEMINI_API_KEY=your-gemini-api-key-here
```

Get a key at [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey).

---

## Running the pipeline

```bash
python pipeline.py specs/raw/user_login.yaml
```

### CLI flags

| Flag | Default | Description |
|---|---|---|
| `spec_file` | *(required)* | Path to spec file (.yaml / .json / .md) |
| `--model` | `gemini-2.5-flash` | Gemini model to use |
| `--skip-gates` | none | Space-separated gate names to skip |
| `--no-strict` | off | Warn on spec issues instead of exiting |

### Examples

```bash
# run with a different model
python pipeline.py specs/raw/user_login.yaml --model gemini-2.0-flash

# skip mypy and bandit during development
python pipeline.py specs/raw/user_login.yaml --skip-gates mypy bandit

# load a JSON spec in non-strict mode
python pipeline.py specs/raw/payments.json --no-strict
```

---

## Writing a spec

Specs live in `specs/raw/`. Supported formats: `.yaml`, `.yml`, `.json`, `.md` (YAML front matter).

**Required fields:**

```yaml
spec_id: "feat-001"
feature: "User Login"
status: "draft"           # draft | reviewed | approved
owner: "auth-team"
created_at: "2026-05-19"
objective: >
  One paragraph describing why this feature exists.
user_story:
  as_a: "registered user"
  i_want: "to log in with my email and password"
  so_that: "I can access my account"
business_rules:
  - id: BR-001
    rule: "Accounts lock after 5 failed attempts"
acceptance_criteria:
  - id: AC-001
    given: "a user with valid credentials"
    when: "they submit the login form"
    then: "they receive a JWT and are redirected to the dashboard"
non_functional_requirements:
  performance:
    - "respond within 300ms at p95"
  security:
    - "all traffic over HTTPS"
out_of_scope:
  - "OAuth / social login"
```

See `specs/raw/user_login.yaml` for a full example.

---

## Folder structure

```
spec-to-code/
│
├── pipeline.py           # entry point
├── config.yaml
├── .env.template
│
├── specs/
│   ├── raw/              # drop spec files here
│   ├── spec_loader.py
│   ├── spec_validator.py
│   └── spec_schema.py
│
├── pipeline/
│   ├── planner.py        # Gemini: spec → plan
│   ├── approval.py       # human approval checkpoint
│   ├── code_generator.py # Gemini: plan tasks → code files
│   ├── test_generator.py # Gemini: acceptance criteria → tests
│   └── quality_gates.py  # ruff, mypy, pytest, bandit
│
├── output/
│   └── generated/        # generated code lands here
│
├── tests/
│   ├── unit/             # generated unit tests land here
│   └── integration/      # generated integration tests land here
│
└── audit/
    ├── audit_logger.py
    ├── logs/             # final audit JSON files
    └── traces/           # per-call Gemini prompt + response traces
```

---

## Architecture decisions

### Why Gemini?

Gemini 2.5 Flash offers a large context window (1M tokens), making it possible to pass the entire spec, plan, and generated code in a single prompt during test generation — no chunking required for typical feature specs.

### Structured JSON output enforced by prompt

Rather than using Gemini's native structured output mode, prompts explicitly instruct the model to return raw JSON with defined keys (`filename`, `content`, etc). This gives full control over the schema without being tied to a specific SDK version. A fence-stripper handles cases where the model wraps output in markdown code blocks despite instructions.

### Two approval checkpoints

Checkpoint 1 (after planning) lets the engineer reject a bad plan before any API calls or file writes happen — saving both time and cost. Checkpoint 2 (after quality gates) gives a final human review before the audit is closed, useful in regulated environments.

### Path safety via `Path.resolve()`

Before writing any generated file, the resolved absolute path is checked against the allowed directories from `config.yaml`. This prevents prompt-injection attacks where a malicious spec tricks Gemini into writing files outside `output/generated/`.

### Audit at two granularities

- **Per-call traces** (`audit/traces/`) — every individual Gemini prompt and raw response, useful for debugging model output
- **Final audit log** (`audit/logs/`) — single JSON with the full run summary including timestamps, approval events, and quality gate results

### Fail-fast quality gates

Gates run in order: `ruff → mypy → pytest → bandit`. The pipeline exits with code `1` on the first failure. This keeps feedback fast and avoids running expensive security scans on code that doesn't even type-check.

---

## Tradeoffs

| Decision | Tradeoff |
|---|---|
| One Gemini call per task | Predictable output and easy audit, but slower and more expensive than batching |
| No streaming | Simpler parsing of complete JSON responses, but higher latency per call |
| `subprocess` for quality gates | Works with any tool version installed locally; no Python API coupling |
| Generated tests land in `tests/` | Keeps test discovery automatic, but risks overwriting hand-written tests with the same spec_id |

---

## Limitations

- Generated code is only as good as the spec — vague acceptance criteria produce vague code
- Quality gates run on `output/generated/` only; they do not re-check pre-existing code
- No retry logic on Gemini calls yet — a transient API error aborts the pipeline at that step
- Test files are overwritten on re-runs with the same spec_id

---

## Future improvements

- [ ] Retry with exponential backoff on Gemini API errors
- [ ] Diff-based code regeneration — only re-generate files affected by spec changes
- [ ] HTML run report from `output/reports/`
- [ ] CI mode (`--ci`) that skips approval prompts and uses exit codes only
- [ ] Multi-spec batch mode — run the pipeline across an entire `specs/raw/` directory
- [ ] Support for OpenAI and Anthropic as alternative providers via `config.yaml`
- [ ] Vector-store spec memory — reuse context from previously generated features
