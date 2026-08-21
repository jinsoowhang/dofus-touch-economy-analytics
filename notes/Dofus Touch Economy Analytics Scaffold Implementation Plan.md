# Dofus Touch Economy Analytics Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a public-safe, reproducible dbt and DuckDB repository scaffold while preserving the supplied source data locally and outside Git.

**Architecture:** The dbt project lives at the repository root and targets a local ignored DuckDB file. This milestone creates repository boundaries, tooling, documentation, tests, and CI; a later ingestion milestone will validate the source contracts and load immutable raw tables before dbt models are introduced.

**Tech Stack:** Python 3.12, uv, dbt Core 1.12.0, dbt-duckdb 1.10.1, DuckDB, Ruff 0.16.1, SQLFluff 4.2.2, Pytest 9.1.1, pre-commit 4.6.1, GitHub Actions

---

## File map

- `.gitignore`: Excludes local data, databases, secrets, generated artifacts, and private workflow bookkeeping.
- `.gitattributes`: Normalizes repository text files to LF and marks binary formats.
- `.editorconfig`: Defines UTF-8, LF, indentation, and whitespace conventions.
- `.python-version`: Selects Python 3.12 for uv.
- `.env.example`: Documents that the local scaffold requires no secrets.
- `pyproject.toml`: Declares the environment and Python quality-tool configuration.
- `uv.lock`: Locks the complete Python dependency graph.
- `.sqlfluff`: Configures dbt-aware DuckDB SQL linting.
- `dbt_project.yml`: Defines the root dbt project and model layers.
- `profiles.yml`: Defines the secret-free local DuckDB development target.
- `analyses/README.md`: Explains the purpose of dbt analyses.
- `macros/README.md`: Explains the rule for adding dbt macros.
- `models/README.md`: Defines dbt layers, grains, and naming.
- `models/staging/README.md`: Defines source-oriented staging responsibilities.
- `models/intermediate/README.md`: Defines reusable transformation responsibilities.
- `models/marts/README.md`: Defines consumer-facing model responsibilities.
- `seeds/README.md`: Restricts seeds to small public reference data.
- `snapshots/README.md`: Defers snapshots until mutable-source semantics exist.
- `src/README.md`: Reserves Python source code for the ingestion milestone.
- `tests/dbt/README.md`: Defines singular dbt test responsibilities.
- `data/README.md`: Explains local, sample, and warehouse data boundaries.
- `data/raw/README.md`: Documents canonical local source filenames.
- `data/samples/README.md`: Restricts committed samples to synthetic data.
- `data/warehouse/README.md`: Explains ignored DuckDB artifacts.
- `scripts/check_public_files.py`: Fails when forbidden local artifacts are tracked.
- `scripts/check.sh`: Runs all local and CI verification commands.
- `scripts/__init__.py`: Makes the repository scripts importable in tests.
- `tests/python/test_check_public_files.py`: Tests the public-file policy.
- `.pre-commit-config.yaml`: Runs fast repository checks before commits.
- `README.md`: Provides the public project overview and setup instructions.
- `LICENSE`: Applies the MIT license to original project code.
- `docs/architecture.md`: Documents component boundaries and data flow.
- `docs/data-contract.md`: Documents canonical source names and field contracts.
- `docs/adr/0001-use-dbt-and-duckdb.md`: Records the local stack decision.
- `AGENTS.md`: Gives public-safe instructions to future coding agents.
- `.github/workflows/ci.yml`: Reproduces verification in GitHub Actions without raw data.
- `MEMORY.md`: Preserves stable project decisions.
- `notes/Session Notes 2026-08-20.md`: Records this scaffold session and verification.

## Task 1: Establish repository and data safety boundaries

**Files:**

- Create: `.gitignore`
- Create: `.gitattributes`
- Create: `.editorconfig`
- Create: `.python-version`
- Create: `.env.example`
- Create: `data/README.md`
- Create: `data/raw/README.md`
- Create: `data/samples/README.md`
- Create: `data/warehouse/README.md`

- [ ] **Step 1: Create the directory structure**

Run:

```bash
mkdir -p data/raw data/samples data/warehouse
```

Expected: the three directories exist and the command produces no output.

- [ ] **Step 2: Create `.gitignore`**

```gitignore
# Local environment and secrets
.env
.env.*
!.env.example
.venv/

# Python
__pycache__/
*.py[cod]
.pytest_cache/
.ruff_cache/
.coverage
htmlcov/

# dbt and SQLFluff
target/
dbt_packages/
logs/
.sqlfluffcache

# Local data and warehouse artifacts
data/raw/**
!data/raw/README.md
data/warehouse/**
!data/warehouse/README.md
*.duckdb
*.duckdb.wal
*.xlsx

# Private workflow bookkeeping
.user.yml
skill-observations/
.worktrees/

# Editors and operating systems
.vscode/
.idea/
.DS_Store
Thumbs.db
```

- [ ] **Step 3: Create `.gitattributes`**

```gitattributes
* text=auto eol=lf
*.csv text eol=lf
*.json text eol=lf
*.md text eol=lf
*.py text eol=lf
*.sql text eol=lf
*.toml text eol=lf
*.yaml text eol=lf
*.yml text eol=lf
*.duckdb binary
*.xlsx binary
```

- [ ] **Step 4: Create `.editorconfig`**

```ini
root = true

[*]
charset = utf-8
end_of_line = lf
insert_final_newline = true
trim_trailing_whitespace = true
indent_style = space
indent_size = 2

[*.{py,sql}]
indent_size = 4

[*.md]
trim_trailing_whitespace = true
```

- [ ] **Step 5: Create `.python-version` and `.env.example`**

`.python-version`:

```text
3.12
```

`.env.example`:

```dotenv
# The local DuckDB scaffold requires no secrets.
```

- [ ] **Step 6: Document the data directories**

`data/README.md`:

```markdown
# Data directories

- `raw/` contains local source files and is ignored except for its README.
- `samples/` is reserved for small synthetic fixtures that are safe to publish.
- `warehouse/` contains local DuckDB databases and is ignored except for its README.

Original source data is not distributed by this repository.
```

`data/raw/README.md`:

```markdown
# Local raw data

Place the private source exports here using these canonical names:

- `item_sales.csv`
- `item_recipes.csv`
- `item_cost.csv`

Everything in this directory except this README is ignored by Git.
```

`data/samples/README.md`:

```markdown
# Synthetic samples

This directory is reserved for small, synthetic datasets used by automated tests and public examples. Do not copy rows from the private raw exports into this directory.
```

`data/warehouse/README.md`:

```markdown
# Local warehouse

dbt writes the local DuckDB development database to this directory. Database files are generated locally and ignored by Git.
```

- [ ] **Step 7: Verify ignore behavior before placing source files**

Run:

```bash
git check-ignore --no-index -v data/raw/item_sales.csv
git check-ignore --no-index -v data/raw/item_recipes.csv
git check-ignore --no-index -v data/raw/item_cost.csv
git check-ignore --no-index -v data/warehouse/dofus_touch.duckdb
git check-ignore --no-index -v .user.yml
git check-ignore --no-index -v skill-observations/log.md
git check-ignore --no-index -v .worktrees/analytics-scaffold
```

Expected: every command prints the matching `.gitignore` rule and exits successfully.

- [ ] **Step 8: Check formatting and commit repository boundaries**

Run:

```bash
git diff --check
git add -- .gitignore .gitattributes .editorconfig .python-version .env.example data/README.md data/raw/README.md data/samples/README.md data/warehouse/README.md
git diff --cached --check
git commit -m "chore: establish repository boundaries"
```

Expected: both checks produce no output and the commit records only the listed public files.

## Task 2: Place the supplied data under canonical local names

**Files:**

- Create locally and ignore: `data/raw/item_sales.csv`
- Create locally and ignore: `data/raw/item_recipes.csv`
- Create locally and ignore: `data/raw/item_cost.csv`

- [ ] **Step 1: Resolve exactly one matching source for each CSV**

Run:

```bash
downloads_dir="${DOFUS_TOUCH_DOWNLOADS_DIR:?Set DOFUS_TOUCH_DOWNLOADS_DIR to the source export directory}"
sales_sources=("$downloads_dir"/*" - item_sales.csv")
recipe_sources=("$downloads_dir"/*" - item_recipes.csv")
cost_sources=("$downloads_dir"/*" - item_cost.csv")

[[ ${#sales_sources[@]} -eq 1 && -f "${sales_sources[0]}" ]]
[[ ${#recipe_sources[@]} -eq 1 && -f "${recipe_sources[0]}" ]]
[[ ${#cost_sources[@]} -eq 1 && -f "${cost_sources[0]}" ]]
```

Expected: all three validation commands exit successfully without output.

- [ ] **Step 2: Copy the CSVs without preserving the source prefix**

Run:

```bash
downloads_dir="${DOFUS_TOUCH_DOWNLOADS_DIR:?Set DOFUS_TOUCH_DOWNLOADS_DIR to the source export directory}"
sales_sources=("$downloads_dir"/*" - item_sales.csv")
recipe_sources=("$downloads_dir"/*" - item_recipes.csv")
cost_sources=("$downloads_dir"/*" - item_cost.csv")

[[ ${#sales_sources[@]} -eq 1 && -f "${sales_sources[0]}" ]]
[[ ${#recipe_sources[@]} -eq 1 && -f "${recipe_sources[0]}" ]]
[[ ${#cost_sources[@]} -eq 1 && -f "${cost_sources[0]}" ]]

cp -- "${sales_sources[0]}" data/raw/item_sales.csv
cp -- "${recipe_sources[0]}" data/raw/item_recipes.csv
cp -- "${cost_sources[0]}" data/raw/item_cost.csv
```

Expected: the three canonical CSV files exist under `data/raw/`.

- [ ] **Step 3: Verify the copied CSV hashes**

Run:

```bash
sha256sum -- data/raw/item_sales.csv data/raw/item_recipes.csv data/raw/item_cost.csv
```

Expected:

```text
b6719f950deb360330c64c1b06ae5d5ca169f74dde524bfed8a4c57dbf44d7c1  data/raw/item_sales.csv
f9cfba6fb25c31f4e0db792dc57b35b05df97aa584065fc63f4ab65569a597b0  data/raw/item_recipes.csv
1914c1ed77398b261e8b0145b9680a5859a199c3b5b6b055770ba3026d910601  data/raw/item_cost.csv
```

- [ ] **Step 4: Verify all local data is ignored**

Run:

```bash
git check-ignore -v data/raw/item_sales.csv data/raw/item_recipes.csv data/raw/item_cost.csv
git status --short
```

Expected: all three files match `data/raw/**`; Git status does not list the raw files or `skill-observations/`. This task creates no commit because all outputs are intentionally local-only.

## Task 3: Create the locked Python analytics toolchain

**Files:**

- Create: `pyproject.toml`
- Create: `.sqlfluff`
- Create: `uv.lock` through `uv lock`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "dofus-touch-economy-analytics"
version = "0.1.0"
description = "Analytics engineering for a player-observed Dofus Touch economy"
requires-python = ">=3.12,<3.13"
dependencies = [
  "dbt-core==1.12.0",
  "dbt-duckdb==1.10.1",
]

[dependency-groups]
dev = [
  "pre-commit==4.6.1",
  "pytest==9.1.1",
  "ruff==0.16.1",
  "sqlfluff==4.2.2",
  "sqlfluff-templater-dbt==4.2.2",
]

[tool.uv]
package = false

[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.pytest.ini_options]
testpaths = ["tests/python"]
addopts = "-ra"
```

- [ ] **Step 2: Create `.sqlfluff`**

```ini
[sqlfluff]
dialect = duckdb
templater = dbt
max_line_length = 100

[sqlfluff:templater:dbt]
project_dir = .
profiles_dir = .
```

- [ ] **Step 3: Lock and install the environment**

Run:

```bash
uv python install 3.12
uv lock
uv sync --locked --all-groups
```

Expected: uv creates `uv.lock` and completes dependency installation without a resolver error.

- [ ] **Step 4: Verify tool versions**

Run:

```bash
uv run dbt --version
uv run ruff --version
uv run sqlfluff --version
uv run pytest --version
```

Expected: the output includes dbt Core 1.12.0, the DuckDB plugin 1.10.1, Ruff 0.16.1, SQLFluff 4.2.2, and Pytest 9.1.1.

- [ ] **Step 5: Commit the locked toolchain**

Run:

```bash
git add -- pyproject.toml uv.lock .sqlfluff
git diff --cached --check
git commit -m "build: add locked analytics toolchain"
```

Expected: the commit includes only the three toolchain files.

## Task 4: Create the empty dbt and DuckDB project

**Files:**

- Create: `dbt_project.yml`
- Create: `profiles.yml`
- Create: `analyses/README.md`
- Create: `macros/README.md`
- Create: `models/README.md`
- Create: `models/staging/README.md`
- Create: `models/intermediate/README.md`
- Create: `models/marts/README.md`
- Create: `seeds/README.md`
- Create: `snapshots/README.md`
- Create: `src/README.md`
- Create: `tests/dbt/README.md`

- [ ] **Step 1: Create the dbt directory structure**

Run:

```bash
mkdir -p analyses macros models/staging models/intermediate models/marts seeds snapshots src tests/dbt tests/python
```

Expected: all directories exist and the command produces no output.

- [ ] **Step 2: Create `dbt_project.yml`**

```yaml
name: dofus_touch_economy_analytics
version: 1.0.0
config-version: 2

profile: dofus_touch_economy_analytics

model-paths: ["models"]
analysis-paths: ["analyses"]
test-paths: ["tests/dbt"]
seed-paths: ["seeds"]
macro-paths: ["macros"]
snapshot-paths: ["snapshots"]

clean-targets:
  - target
  - dbt_packages
  - logs

models:
  dofus_touch_economy_analytics:
    staging:
      +materialized: view
      +schema: staging
    intermediate:
      +materialized: view
      +schema: intermediate
    marts:
      +materialized: table
      +schema: marts
```

- [ ] **Step 3: Create the secret-free local `profiles.yml`**

```yaml
dofus_touch_economy_analytics:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: data/warehouse/dofus_touch.duckdb
      schema: main
      threads: 4
```

- [ ] **Step 4: Document dbt model responsibilities**

`models/README.md`:

```markdown
# dbt models

Every model must document its grain and primary analytical responsibility.

- `staging/`: source-oriented renaming, typing, and basic validation.
- `intermediate/`: reusable transformations and normalized business concepts.
- `marts/`: consumer-facing dimensions, facts, and governed measures.

Naming conventions:

- `stg_<source>__<entity>`
- `int_<description>`
- `dim_<entity>`
- `fct_<process>`

Domain models begin only after the source contracts and full dates are deterministic.
```

`models/staging/README.md`:

```markdown
# Staging models

Staging models preserve source grain while renaming, typing, and documenting fields. They do not aggregate or encode cross-source business rules.
```

`models/intermediate/README.md`:

```markdown
# Intermediate models

Intermediate models contain reusable transformations such as normalized recipe ingredients and conformed item identities. They are not direct reporting interfaces.
```

`models/marts/README.md`:

```markdown
# Mart models

Marts expose documented dimensions, facts, and governed measures. Every mart must state its grain and intended consumers.
```

- [ ] **Step 5: Document the remaining dbt directories**

`analyses/README.md`:

```markdown
# dbt analyses

Store reusable analytical SQL that should compile with dbt but should not materialize as a warehouse model.
```

`macros/README.md`:

```markdown
# dbt macros

Add a macro only when the same transformation behavior is reused across multiple models or isolates adapter-specific SQL.
```

`seeds/README.md`:

```markdown
# dbt seeds

Seeds are limited to small, stable, public reference datasets. Raw source exports do not belong here.
```

`snapshots/README.md`:

```markdown
# dbt snapshots

Snapshots are introduced only when a mutable source table and its change-capture semantics are defined.
```

`src/README.md`:

```markdown
# Python source

The ingestion milestone will place contract validation and DuckDB loading code here. The scaffold intentionally contains no placeholder package.
```

`tests/dbt/README.md`:

```markdown
# Singular dbt tests

Store SQL tests for business invariants that cannot be expressed with generic schema tests. Python tests live in `tests/python/`.
```

- [ ] **Step 6: Verify the dbt profile and project**

Run:

```bash
DO_NOT_TRACK=1 uv run dbt debug --profiles-dir .
DO_NOT_TRACK=1 uv run dbt parse --profiles-dir .
```

Expected: `dbt debug` ends with `All checks passed!` and `dbt parse` exits successfully without creating domain models.

- [ ] **Step 7: Commit the dbt foundation**

Run:

```bash
git add -- dbt_project.yml profiles.yml analyses/README.md macros/README.md models/README.md models/staging/README.md models/intermediate/README.md models/marts/README.md seeds/README.md snapshots/README.md src/README.md tests/dbt/README.md
git diff --cached --check
git commit -m "build: scaffold dbt duckdb project"
```

Expected: the commit contains only the dbt configuration and directory documentation.

## Task 5: Add test-driven repository quality gates

**Files:**

- Create: `tests/python/test_check_public_files.py`
- Create: `scripts/__init__.py`
- Create: `scripts/check_public_files.py`
- Create: `scripts/check.sh`
- Create: `.pre-commit-config.yaml`

- [ ] **Step 1: Write the failing public-file policy tests**

Create `tests/python/test_check_public_files.py`:

```python
from scripts.check_public_files import find_forbidden_tracked_paths


def test_allows_public_repository_files() -> None:
    paths = [
        "README.md",
        ".env.example",
        "data/raw/README.md",
        "data/samples/example.csv",
        "data/warehouse/README.md",
        "models/staging/stg_source__items.sql",
    ]

    assert find_forbidden_tracked_paths(paths) == []


def test_rejects_private_or_generated_files() -> None:
    paths = [
        ".env",
        ".env.local",
        "data/raw/item_sales.csv",
        "private/local_source.xlsx",
        "data/warehouse/dofus_touch.duckdb",
        "dbt_packages/package/dbt_project.yml",
        "logs/dbt.log",
        ".user.yml",
        "target/manifest.json",
    ]

    assert find_forbidden_tracked_paths(paths) == sorted(paths)
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
uv run pytest tests/python/test_check_public_files.py -v
```

Expected: test collection fails with `ModuleNotFoundError: No module named 'scripts'`.

- [ ] **Step 3: Create the minimal public-file checker**

Run:

```bash
mkdir -p scripts
```

Expected: the `scripts/` directory exists.

Create an empty `scripts/__init__.py` and create `scripts/check_public_files.py`:

```python
from __future__ import annotations

import subprocess
from collections.abc import Iterable
from pathlib import PurePosixPath


FORBIDDEN_PREFIXES = (
    "data/raw/",
    "data/warehouse/",
    "dbt_packages/",
    "logs/",
    "skill-observations/",
    "target/",
)
ALLOWED_PATHS = {
    ".env.example",
    "data/raw/README.md",
    "data/warehouse/README.md",
}
FORBIDDEN_SUFFIXES = (".duckdb", ".duckdb.wal", ".xlsx")
FORBIDDEN_NAMES = {".user.yml"}


def is_forbidden_tracked_path(path: str) -> bool:
    normalized = PurePosixPath(path).as_posix()
    if normalized in ALLOWED_PATHS:
        return False

    name = PurePosixPath(normalized).name
    if name in FORBIDDEN_NAMES:
        return True
    if name == ".env" or name.startswith(".env."):
        return True
    if normalized.startswith(FORBIDDEN_PREFIXES):
        return True
    return normalized.endswith(FORBIDDEN_SUFFIXES)


def find_forbidden_tracked_paths(paths: Iterable[str]) -> list[str]:
    return sorted(path for path in paths if is_forbidden_tracked_path(path))


def tracked_paths() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [path for path in result.stdout.split("\0") if path]


def main() -> int:
    forbidden = find_forbidden_tracked_paths(tracked_paths())
    if not forbidden:
        print("Public-file policy passed.")
        return 0

    print("Forbidden tracked files:")
    for path in forbidden:
        print(f"- {path}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the focused tests and verify they pass**

Run:

```bash
uv run pytest tests/python/test_check_public_files.py -v
uv run python scripts/check_public_files.py
```

Expected: both tests pass and the script prints `Public-file policy passed.`.

- [ ] **Step 5: Create the repository check script**

Create `scripts/check.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

export DO_NOT_TRACK=1

uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run dbt debug --profiles-dir .
uv run dbt parse --profiles-dir .
uv run sqlfluff lint models analyses
uv run python scripts/check_public_files.py
```

Run:

```bash
chmod +x scripts/check.sh
```

Expected: `scripts/check.sh` is executable.

- [ ] **Step 6: Create `.pre-commit-config.yaml`**

```yaml
repos:
  - repo: local
    hooks:
      - id: ruff-check
        name: ruff check
        entry: uv run ruff check .
        language: system
        pass_filenames: false
      - id: ruff-format
        name: ruff format check
        entry: uv run ruff format --check .
        language: system
        pass_filenames: false
      - id: pytest
        name: pytest
        entry: uv run pytest
        language: system
        pass_filenames: false
      - id: dbt-parse
        name: dbt parse
        entry: env DO_NOT_TRACK=1 uv run dbt parse --profiles-dir .
        language: system
        pass_filenames: false
      - id: sqlfluff
        name: sqlfluff
        entry: env DO_NOT_TRACK=1 uv run sqlfluff lint
        language: system
        files: ^(analyses|models)/.*\.sql$
      - id: public-file-policy
        name: public file policy
        entry: uv run python scripts/check_public_files.py
        language: system
        pass_filenames: false
```

- [ ] **Step 7: Run all quality gates**

Run:

```bash
./scripts/check.sh
uv run pre-commit run --all-files
```

Expected: Ruff, Pytest, dbt, SQLFluff, the public-file policy, and all pre-commit hooks pass.

- [ ] **Step 8: Commit the quality gates**

Run:

```bash
git add -- tests/python/test_check_public_files.py scripts/__init__.py scripts/check_public_files.py scripts/check.sh .pre-commit-config.yaml
git diff --cached --check
git commit -m "test: add repository quality gates"
```

Expected: the commit contains the tests, checker, verification script, and pre-commit configuration.

## Task 6: Write public project and contributor documentation

**Required skill:** Invoke `create-agents-md` before creating `AGENTS.md`; apply its repository-specific guidance without adding private context.

**Files:**

- Create: `README.md`
- Create: `LICENSE`
- Create: `docs/architecture.md`
- Create: `docs/data-contract.md`
- Create: `docs/adr/0001-use-dbt-and-duckdb.md`
- Create: `AGENTS.md`

- [ ] **Step 1: Create the public `README.md`**

```markdown
# Dofus Touch Economy Analytics

An analytics engineering project for studying player-observed item prices, crafting economics, and sales behavior in Dofus Touch.

This is an unofficial fan project. It is not affiliated with, endorsed by, or sponsored by Ankama. Dofus Touch and related names belong to their respective owners.

## Project status

The repository currently provides the reproducible dbt and DuckDB foundation. Source ingestion and analytical models begin after the abbreviated source dates are replaced with deterministic ISO dates.

## Architecture

```text
private CSV exports
        |
        v
contract validation and DuckDB loading
        |
        v
dbt staging -> intermediate -> marts
        |
        v
governed metrics -> optional semantic layer and BI
```

The local scaffold uses DuckDB for a zero-infrastructure warehouse and dbt Core for transformation, testing, lineage, and documentation. See [`docs/architecture.md`](docs/architecture.md) for component boundaries.

## Local setup

Requirements:

- WSL or Linux
- Git
- uv

Install the locked environment and validate the project:

```bash
uv python install 3.12
uv sync --locked --all-groups
./scripts/check.sh
```

## Local data

Raw source files are not distributed. Local copies use these ignored paths:

- `data/raw/item_sales.csv`
- `data/raw/item_recipes.csv`
- `data/raw/item_cost.csv`

Only synthetic fixtures with clear provenance may be committed under `data/samples/`. See [`docs/data-contract.md`](docs/data-contract.md) for the source contract and known limitations.

## Repository structure

- `models/`: dbt staging, intermediate, and mart layers.
- `analyses/`: reusable analytical SQL that does not materialize.
- `tests/dbt/`: singular dbt business-rule tests.
- `tests/python/`: Python contract and repository tests.
- `src/`: ingestion code in the next milestone.
- `data/`: ignored raw and warehouse data plus public synthetic samples.
- `docs/`: architecture, contracts, and decisions.
- `notes/`: committed project designs and session records.

## Development checks

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest
DO_NOT_TRACK=1 uv run dbt debug --profiles-dir .
DO_NOT_TRACK=1 uv run dbt parse --profiles-dir .
DO_NOT_TRACK=1 uv run sqlfluff lint models analyses
uv run python scripts/check_public_files.py
```

Run every check with:

```bash
./scripts/check.sh
```

## Data and licensing

The MIT license covers original code in this repository. It does not grant rights to source data, game content, names, artwork, or other third-party material. Raw data remains local unless its redistribution rights are established separately.
```

- [ ] **Step 2: Create `LICENSE`**

```text
MIT License

Copyright (c) 2026 Jinsoo Whang

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 3: Create `docs/architecture.md`**

```markdown
# Architecture

## Objective

Build a trustworthy analytical layer over player-observed Dofus Touch economy data while keeping local source files private and transformations reproducible.

## Component boundaries

### Local source storage

`data/raw/` preserves source exports without modification. The files are local-only and excluded from Git.

### Ingestion

Python code under `src/` will validate source contracts and load immutable raw tables into DuckDB. Ingestion owns file parsing, source row numbers, load metadata, and rejected-row reporting.

### dbt staging

Staging models preserve source grain while standardizing names and types. They retain source values needed for reconciliation and expose parse status for malformed fields.

### dbt intermediate

Intermediate models normalize reusable concepts. The recipe export will become one row per recipe ingredient, and item names will receive deterministic exact-match normalization.

### dbt marts

Marts expose documented dimensions, facts, and governed measures. Each mart states its grain and intended consumers.

### Semantic and presentation layer

A semantic layer and BI tool are deferred until mart grains and metric definitions are stable. They consume marts rather than raw or staging relations.

## Data flow

```text
data/raw/*.csv
      |
      v
Python contract validation
      |
      +--> rejected rows and validation report
      |
      v
DuckDB raw schema
      |
      v
dbt staging -> intermediate -> marts
```

## Portability

DuckDB-specific behavior belongs in ingestion or focused macros. Transformation SQL should use portable constructs where practical so a future cloud warehouse remains an adapter change rather than a project rewrite.

## Current boundary

This scaffold contains no source ingestion or domain models. Those begin after exact source dates, row grains, and duplicate cost semantics are confirmed.
```

- [ ] **Step 4: Create `docs/data-contract.md`**

```markdown
# Source data contract

## Shared rules

- Encoding: UTF-8.
- Format: comma-delimited CSV with one header row.
- Column names: snake_case and stable within a dataset version.
- Dates: ISO `YYYY-MM-DD`.
- Timestamps: ISO 8601 with an explicit timezone.
- Currency: whole-number kama amounts.
- Raw files: immutable after receipt.
- Missing values: empty fields or a documented null token, not spreadsheet error values.

Current exports contain abbreviated dates, formatted numeric strings, percentages, and spreadsheet error values. They are preserved locally but do not satisfy the ingestion contract until deterministic replacements or explicit parsing rules are approved.

## `item_sales.csv`

Required columns, in source order:

```text
date
item
sold_date
sold_price
cost
profit
previous_price
start_reference
end_reference
difference
est_price_per_unit
memo
```

Provisional grain: one source spreadsheet row representing a listing or sale observation. The grain remains provisional because no stable transaction identifier or quantity is present.

## `item_recipes.csv`

Required leading columns:

```text
recipe_item
profession
```

The source then repeats `raw_material_n`, `quantity_n`, and `cost_n` for `n` from 1 through 8, followed by:

```text
total_cost
profit
ROI
```

The ingestion milestone will preserve the wide raw row. Intermediate dbt logic will normalize populated ingredient groups to one row per recipe and ingredient position.

## `item_cost.csv`

Required columns, in source order:

```text
raw_material
category
price
```

Item names are not unique in the current export. Ingestion must retain duplicates and report candidate-key violations rather than selecting a row silently.

## Required load metadata

Every raw table will add:

- `source_file_name`
- `source_row_number`
- `loaded_at`
- `observed_at`
- server or market context

The next milestone cannot assign `observed_at` until the source dates and collection context are deterministic.
```

- [ ] **Step 5: Create `docs/adr/0001-use-dbt-and-duckdb.md`**

```markdown
# ADR 0001: Use dbt Core and DuckDB locally

**Status:** Accepted
**Date:** 2026-08-20

## Context

The project starts with three CSV exports and needs analytics engineering conventions, reproducible transformations, tests, and documentation without requiring paid cloud infrastructure.

## Decision

Use dbt Core as the transformation framework and dbt-duckdb with a local ignored DuckDB file as the development warehouse. Manage Python and tool dependencies with uv.

## Consequences

- Contributors can run the project locally without accounts or credentials.
- dbt supplies model lineage, tests, documentation, and layer conventions.
- DuckDB-specific behavior must stay isolated so transformation SQL remains portable where practical.
- Lightdash and a hosted warehouse remain outside the scaffold milestone.
- Raw data remains local and CI validates the repository without it.
```

- [ ] **Step 6: Create project-specific `AGENTS.md` after applying the required skill**

The resulting file must preserve this repository-specific content:

```markdown
# AGENTS.md

## Project purpose

This repository builds a public, reproducible analytics engineering project for player-observed Dofus Touch economy data.

## Session workflow

- At the start of any task-oriented session, invoke the `task-observer` skill before using tools or producing deliverables.
- Read `MEMORY.md`, the latest file under `notes/`, and relevant files under `docs/` before changing project behavior.
- Keep project notes, designs, and session logs under `notes/`.
- At the end of a work session, update `MEMORY.md` with stable decisions and append or create `notes/Session Notes YYYY-MM-DD.md`.

## Data safety

- Never commit files under `data/raw/` except `data/raw/README.md`.
- Never commit DuckDB files, spreadsheets, credentials, `.env` files, `.user.yml`, task-observer logs, or worktree contents.
- Commit only synthetic data under `data/samples/` unless redistribution rights are documented.
- Preserve raw values; do not silently repair source data.
- Do not automate interaction with the game client or scrape a source without explicit authorization.

## Tooling

- Use Python 3.12 and `uv`; do not use pip directly.
- Run `uv sync --locked --all-groups` to install dependencies.
- Run `./scripts/check.sh` before claiming work is complete.

## dbt conventions

- Keep the dbt project at the repository root.
- Use `staging`, `intermediate`, and `marts` model layers.
- Name models `stg_<source>__<entity>`, `int_<description>`, `dim_<entity>`, or `fct_<process>`.
- Document the grain of every model.
- Keep raw-source parsing in staging and business rules in intermediate or mart models.
- Prefer portable SQL; isolate DuckDB-specific behavior in ingestion or focused macros.
- Add generic schema tests for keys and relationships and singular tests for business invariants.

## Coding conventions

- Use snake_case for Python, SQL, YAML fields, and filenames where supported.
- Use Ruff for Python and SQLFluff for dbt SQL.
- Make the smallest change that satisfies the current requirement.
- Keep commits atomic and stage files intentionally.
- Do not refactor unrelated files.
```

- [ ] **Step 7: Verify and commit public documentation**

Run:

```bash
git diff --check
uv run python scripts/check_public_files.py
git add -- README.md LICENSE docs/architecture.md docs/data-contract.md docs/adr/0001-use-dbt-and-duckdb.md AGENTS.md
git diff --cached --check
git commit -m "docs: document analytics repository"
```

Expected: whitespace and public-file checks pass and the commit contains only public documentation and agent instructions.

## Task 7: Add GitHub Actions verification

**Files:**

- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Create `.github/workflows/ci.yml`**

```yaml
name: ci

on:
  push:
  pull_request:

permissions:
  contents: read

jobs:
  checks:
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v6.0.0

      - name: Install uv
        uses: astral-sh/setup-uv@v9.0.0
        with:
          version: "0.12.0"
          enable-cache: true

      - name: Install Python
        run: uv python install 3.12

      - name: Install locked dependencies
        run: uv sync --locked --all-groups

      - name: Run repository checks
        run: ./scripts/check.sh
```

- [ ] **Step 2: Verify the workflow is public-data independent**

Run:

```bash
rg -n "data/raw|\\.env" .github/workflows/ci.yml
```

Expected: the command exits with no matches.

- [ ] **Step 3: Run the same command CI will run**

Run:

```bash
uv sync --locked --all-groups
./scripts/check.sh
```

Expected: every repository check passes without reading the ignored raw CSVs.

- [ ] **Step 4: Commit CI**

Run:

```bash
git add -- .github/workflows/ci.yml
git diff --cached --check
git commit -m "ci: verify analytics scaffold"
```

Expected: the commit contains only the GitHub Actions workflow.

## Task 8: Record project memory and complete verification

**Files:**

- Create: `MEMORY.md`
- Create: `notes/Session Notes 2026-08-20.md`

- [ ] **Step 1: Create `MEMORY.md`**

```markdown
# Memory

**Last updated:** 2026-08-20

## Dofus Touch Economy Analytics

- Public project identity: analytics engineering for player-observed Dofus Touch item prices, crafting economics, and sales behavior.
- Local stack: Python 3.12, uv, dbt Core, dbt-duckdb, and DuckDB.
- dbt layers: staging, intermediate, and marts.
- Raw CSVs, DuckDB files, secrets, task-observer files, and worktree contents remain local and ignored.
- Canonical local sources: `item_sales.csv`, `item_recipes.csv`, and `item_cost.csv` under `data/raw/`.
- Only synthetic samples may be committed until source-data redistribution rights are established.
- The source CSVs contain abbreviated dates; ingestion and date-dependent models require deterministic ISO dates from a re-export or an explicitly approved parsing rule.
- Source-derived costs, profits, differences, and ROI values will be preserved for reconciliation but recomputed as governed measures.
- The next milestone is test-driven source-contract validation and immutable loading into DuckDB.
```

- [ ] **Step 2: Run final verification before documenting completion**

Run:

```bash
uv sync --locked --all-groups
./scripts/check.sh
uv run pre-commit run --all-files
git check-ignore -v data/raw/item_sales.csv data/raw/item_recipes.csv data/raw/item_cost.csv data/warehouse/dofus_touch.duckdb .user.yml skill-observations/log.md .worktrees/analytics-scaffold
git status --short
```

Expected: dependency installation and all checks pass; each local-only file prints a matching ignore rule; Git status lists only `MEMORY.md` before the session notes are created.

- [ ] **Step 3: Create `notes/Session Notes 2026-08-20.md` from verified results**

```markdown
# Session Notes 2026-08-20

## Context

Established the public and local foundation for a Dofus Touch economy analytics engineering project using three private CSV exports.

## Work completed

- Defined and approved the repository design.
- Initialized Git with atomic commits.
- Established raw-data, warehouse, secret, and generated-file boundaries.
- Preserved the three CSV exports under concise canonical local names.
- Created a locked Python 3.12 environment with uv.
- Created an empty dbt Core project targeting local DuckDB.
- Added Python, SQL, dbt, public-file, pre-commit, and CI checks.
- Added public architecture, source-contract, decision, setup, and agent documentation.

## Decisions

- Keep raw source data out of Git.
- Use dbt Core and DuckDB locally before introducing hosted infrastructure.
- Do not create placeholder domain models.
- Do not infer missing years from abbreviated CSV dates.
- Recompute analytical measures rather than treating spreadsheet formulas as canonical.
- Normalize the wide recipe structure only after ingestion contracts are implemented.

## Verification

- `uv sync --locked --all-groups` completed successfully.
- `./scripts/check.sh` passed.
- `uv run pre-commit run --all-files` passed.
- dbt profile validation and project parsing passed.
- The public-file policy found no forbidden tracked artifacts.
- Git ignored all local CSV and DuckDB files.

## Next step

Obtain deterministic full dates, then implement test-driven source validation and immutable DuckDB loading before adding dbt models.
```

- [ ] **Step 4: Commit project memory and session notes**

Run:

```bash
git add -- MEMORY.md "notes/Session Notes 2026-08-20.md"
git diff --cached --check
git commit -m "docs: record analytics scaffold session"
```

Expected: the commit contains only project memory and the dated session notes.

- [ ] **Step 5: Verify the final repository state**

Run:

```bash
./scripts/check.sh
git status --short --branch
git log --oneline --decorate -8
```

Expected: all checks pass, Git reports `## main` with no tracked or untracked public files, and the log shows separate commits for design, boundaries, toolchain, dbt scaffold, quality gates, documentation, CI, and session records.
