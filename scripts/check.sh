#!/usr/bin/env bash
set -euo pipefail

export DO_NOT_TRACK=1

uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python -m compileall -q src
uv run dbt debug --profiles-dir .
uv run dbt parse --profiles-dir .
uv run sqlfluff lint models analyses
uv run python scripts/check_public_files.py
