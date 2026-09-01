# Session Notes 2026-08-31

## README Slack worker launch command

### Documentation

- Added `uv run --env-file .env.slack dofus-slack-worker` to the main local setup
  flow in the README.
- Clarified that the worker runs in a second terminal alongside the blocking local
  web process and only after completing the private Slack setup.
- Updated the README and Slack runbook to show both the `.env.slack` configuration
  check and live worker command while keeping the ignored secret file out of Git.

### Verification

- `uv run pytest tests/python/test_documented_commands.py -q` passed (6 tests).
- `uv run python scripts/check_public_files.py` passed.
- `git diff --check -- README.md` passed.

## Slack preview decision controls

### Pilot result

- The first reported live confirmation-required `sold` batch completed end to end
  and committed 18 listing changes. Only this aggregate result is recorded; private
  screenshot rows and Slack identifiers remain local.
- This begins the controlled pilot but does not satisfy the 20-batch autonomy gate.

### Behavior

- Confirm and Reject now immediately replace the interactive preview buttons with a
  non-interactive decision state.
- The independently retried terminal receipt updates that same preview message rather
  than posting a second reply, so stale buttons cannot remain confusingly active.

### Verification

- Focused Slack worker and capture-repository verification passed (14 tests).
- `./scripts/check.sh` passed: Ruff lint and formatting, 325 Python tests, package
  compilation, dbt debug/parse, nine seed loads, all 126 dbt build nodes, SQLFluff,
  and public-file policy.
- `git diff --check` passed, and ignored private Slack configuration, evidence,
  operational databases, and backups remained outside the publication set.

## Recipe Calculator cost-banded default quantities

### Behavior

- New Recipe Calculator entries use a quantity of four below 50,000 kamas, three
  from 50,000 through below 100,000, two from 100,000 through 500,000, and one above
  500,000 or when current recipe cost is incomplete.
- The rule applies to calculator search and suggestions plus shared Add actions on
  Recipes, Best Sellers, Profit Opportunities, and item detail.
- Existing saved cart quantities remain unchanged. Out of Stock's explicit Suggested
  Restock quantity continues to take precedence over the cost-banded default.

### Verification

- Boundary coverage includes 0, 50,000, 100,000, and 500,000 kamas plus missing,
  negative, just-below, and just-above cases.
- Focused recipe, web, and static-asset verification passed (111 tests).
- `./scripts/check.sh` passed: Ruff lint and formatting, 334 Python tests, package
  compilation, dbt debug/parse, nine seed loads, all 126 dbt build nodes, SQLFluff,
  and public-file policy.
