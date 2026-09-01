# Session Notes 2026-08-29

## Analytics engineering fundamentals and recipe economics

### Context

Applied the dbt project-structure concepts from the user's Analytics Engineering
learning example through one locally executable transformation slice. The work was
explicitly credential-free and did not publish to or run against BigQuery.

### Work completed

- Added nine DuckDB-only synthetic seeds implementing the complete operational raw
  snapshot contract with 34 invented rows. The fixture covers two market contexts,
  complete ingredient pricing, a resolved ingredient without a price, an unresolved
  ingredient, and fallback from a newer invalidated observation.
- Added `int_recipe_ingredient_costs` at one latest-recipe ingredient position per
  market and `int_recipe_costs` at one latest recipe per market. The models preserve
  missing inputs, calculate price coverage, and emit a recipe cost only when every
  ingredient resolves and has a valid current price.
- Added `fct_recipe_economics` at one crafted item using its latest recipe per
  observed market. It exposes current item unit price, complete recipe cost,
  estimated profit, and estimated ROI as a ratio; incomplete inputs remain null.
- Added the non-materialized `recipe_price_coverage` analysis for engineering review
  by market and profession.
- Added six singular assertions for composite grains, ingredient-cost arithmetic,
  cost-status semantics, profit and ROI reconciliation, and the exact DuckDB fixture
  outcomes. Existing generic key, relationship, and accepted-value tests remain in
  the model YAML.
- Expanded the public local check sequence to seed the synthetic sources, run a full
  dbt build, and SQL-lint singular tests. Updated the public setup, architecture,
  ingestion guide, seed policy, model documentation, and agent commands.
- Added dbt's generated `dbt_internal_packages/` directory to both ignore and
  forbidden-public-file policy.

### Decisions

- Keep market context explicit in every recipe-cost and recipe-economics grain.
- Derive the set of observed markets from all staged observations, including markets
  whose current observations may all be invalidated, then use only latest valid
  observations for prices.
- Never treat an unresolved ingredient or missing price as zero. Recipe cost, profit,
  and ROI are available only when their required inputs are complete.
- Use seeds only for small invented DuckDB fixtures. BigQuery targets keep the seeds
  disabled and continue reading manifested private operational snapshots.
- Do not add dbt snapshots: operational snapshots are already immutable, recipes are
  versioned, and price observations are append-only.

### Verification

- Focused documented-command tests passed: 5 tests with the existing Starlette
  deprecation warning.
- Nine synthetic seeds loaded successfully, and dbt documentation generation wrote a
  complete catalog.
- The full local dbt build passed all 126 selected nodes: 18 models and 108 data tests,
  with no warnings, errors, or skips.
- Fixture reconciliation produced six expected mart rows. Synthetic Sword cost,
  profit, and ROI were 80, 920, and 11.5 in the primary market and 96, 804, and 8.375
  in the secondary market. Missing-price and unresolved recipes retained null costs
  and economics.
- `./scripts/check.sh` passed: Ruff lint and formatting, 256 Python tests, package
  compilation, dbt profile validation and parsing, nine seed loads, the 126-node dbt
  build, SQLFluff across models, analyses, and singular tests, and public-file policy.
  The Python suite retains the existing Starlette deprecation warning.
- No BigQuery snapshot publication, dbt Cloud build, or external credential use was
  performed.

### Next step

After review, publish the current operational snapshot and run the new graph in the
BigQuery development environment before considering a manual production build. A
later learning slice can model item-level sales performance from `fct_sales`.

## Download screenshot sales reconciliation

- Reviewed the private `IMG_9199.jpg` screenshot in the user's Downloads folder; it
  remained outside the repository.
- Found four visible sale messages. Graytess Cape at 47,000 kamas, Snowy Grale Boots
  at 149,000 kamas, and Royal Coco Amublop at 74,000 kamas had exact active
  item-name and asking-price matches. Where identical active listings existed, the
  oldest row was selected first.
- Marked the three matched listings sold atomically at one shared timestamp for
  270,000 kamas. Historical ingredient-price coverage was incomplete, so all three
  recipe-cost-at-sale snapshots remained null rather than treating missing costs as
  zero.
- Left Minoskito Skin at 1,517 kamas unchanged because the catalog item had no Sales
  listing; no listing or sale data was fabricated.
- Created the ignored recovery backup
  `data/app/backups/dofus_touch-before-download-screenshot-sales-20260829T230346Z.sqlite3`.
  No BigQuery snapshot was published.

### Verification

- Independent reconciliation confirmed that the latest sale batch contains exactly
  the three expected name-and-price pairs at the shared timestamp.
- Active listings changed from 172 to 169, completed listings from 164 to 167, and
  completed recorded revenue from 13,126,997 to 13,396,997 kamas.
- SQLite `PRAGMA integrity_check` returned `ok` for both the recovery backup and the
  updated operational database.
- The full application check suite was not run because application code, schemas,
  dependencies, and model behavior were unchanged.

## Currently Selling relist dates

- Added a sortable Relisted Date directly after Selling Since in Currently Selling.
  The original selling date remains unchanged, while listings that have not been
  repriced show an em dash.
- Derived the relist timestamp from the listing's existing linked append-only price
  observation when it occurred after `selling_started_at`. This gives existing
  repriced listings their historical relist date without a schema migration or
  duplicated operational state.
- Made both manual price edits and Apply suggestion reset the seven-Pacific-day
  price-review clock. The existing age and markdown prompt disappears immediately
  after repricing; when it becomes due again, its age is labeled as days since
  relist.
- Eager-loaded linked price observations with Sales rows to avoid per-row queries
  while deriving relist dates.
- Added service and web regressions for initial null relist dates, independent
  repricing, relist sorting with nulls last, reset price-review eligibility, the
  new table column, and the Apply suggestion flow.

### Verification

- Focused Sales service and web tests passed: 94 tests with the existing Starlette
  deprecation warning.
- `./scripts/check.sh` passed: Ruff lint and formatting, 259 Python tests, package
  compilation, dbt profile validation and parsing, nine seed loads, the 126-node dbt
  build, SQLFluff, and public-file policy. The Python suite retains the same existing
  Starlette deprecation warning.

## Sales position and recipe planning improvements

### Work completed

- Restored the exact Currently Selling scroll offset after manual repricing or
  Apply suggestion on the later `pageshow` lifecycle, after browser navigation has
  settled. The Currently Selling section anchor remains the no-storage fallback.
- Added sortable Cost Per Item to Select Craftable Items. The value is the current
  complete ingredient cost for one craft and remains an explicit em dash when any
  ingredient price is missing.
- Kept Combined Shopping List crafts alphabetized while ordering each craft's
  consolidated ingredients by their first source recipe position rather than by
  ingredient name.
- Added a browser-only Craft Quantity control to item recipe sections. It scales
  displayed ingredient quantities, row total costs, and Total Recipe Cost from one
  through 1,000 without mutating recipe or price data.

### Verification

- Recipe service tests passed: 21 tests.
- Web tests passed: 62 tests.
- JavaScript syntax checks, request-scoped Ruff lint and formatting, and whitespace
  checks passed.
- `./scripts/check.sh` was attempted but stopped in its initial Ruff phase on five
  lint errors in unrelated, concurrently added Slack-capture implementation files.
  Those in-progress files were preserved without modification.

## Stakeholder Insights and combined ingredient totals

### Work completed

- Added Insights as a top-level header destination immediately after Sales. The
  read-only stakeholder report uses existing governed SQLite-backed services and
  makes no request-time DuckDB, BigQuery, or dbt calls.
- Added an executive overview for completed sales, recorded revenue, average time to
  sell, active inventory, listed value, and known historical profit.
- Added an analyst readout comparing the seven Pacific calendar days ending on the
  latest recorded sale with the preceding seven days. It also reports repeat demand,
  revenue concentration, historical cost coverage, and known-profit margin while
  keeping missing data explicit.
- Added a current action queue for overdue price reviews, out-of-stock items,
  profitable recipes, and the highest current ROI, plus a sortable category table
  weighted by completed listing count.
- Added All Crafts Total Quantity beside Craft Total Quantity in the Combined
  Shopping List. Shared canonical ingredients repeat the across-cart requirement on
  every craft-attributed row, including repeated ingredient slots and unresolved
  ingredients matched by normalized source name.
- Removed the Price Coverage summary card without changing the completeness rules
  that keep incomplete Total Cost explicit.

### Verification

- `uv run pytest -q tests/python/test_web.py` passed: 63 tests.
- The combined Insights, recipe, and Sales service suites passed: 55 tests.
- Request-scoped Ruff lint and formatting, package compilation, JavaScript syntax,
  and whitespace checks passed.
- `./scripts/check.sh` was attempted but stopped in its initial Ruff phase on eight
  lint errors in unrelated, concurrently added Slack-capture implementation files.
  Those in-progress files were preserved without modification.

## Slack screenshot sales automation research and planning

### Context

Researched and planned a private `#dofus-touch` Slack workflow for two explicit
screenshot actions. `sold` will reconcile visible sale notifications with exact
active Sales listings. `market` will ensure the user's own visible, in-scope
craftable marketplace listings also exist in the Web UI. The user accepted the full
recommended-answer set from the `grill-me-yolo` review. This session intentionally
performed no implementation or external Slack/OpenAI setup.

### Research completed

- Reviewed the current Sales models, repositories, service transaction boundaries,
  migrations, operational snapshot contract, BigQuery schema evolution, dbt sale
  models and seeds, CLI/settings boundaries, ignored local-state policy, and prior
  screenshot reconciliation record.
- Confirmed from Slack's primary documentation that Socket Mode suits a local worker
  without public ingress, while disconnects, retries, prompt acknowledgment, private
  file authorization, and startup history recovery require durable intake.
- Confirmed from OpenAI's primary documentation that the Responses API supports
  base64 image inputs and strict structured outputs. The recommended pilot uses
  GPT-5.6 Terra, original image detail, `store: false`, and no Files API or model
  tools. Verified OpenAI Python 3.6.0 and Slack Bolt 1.30.0 from their official PyPI
  project pages for the future dependency task.

### Decisions

- Require the exact first caption line `sold` or `market`, or an owner-only Slack
  action button. Screenshot/model content never selects the business action.
- Treat all supported images on one top-level parent message as one atomic batch and
  use the Slack parent timestamp as the effective sale or listing-observation time.
- Keep the model limited to ordered raw name/whole-kama price extraction and screen
  classification. Exact normalized identity, latest recipe, approved professions,
  active-listing matches, occurrence counts, and writes are deterministic code.
- Use exact active item-and-price matching. `sold` assigns the oldest identical
  listing first and never fabricates data. `market` adds only missing exact counts;
  it never removes extra Web UI rows or automatically resolves a different-price
  conflict.
- Treat exact non-craftable or unapproved-profession items as visibly out of scope.
  Unresolved or ambiguous names and invalid in-scope rows send the full batch to
  review. Every accepted mutation remains all-or-nothing.
- Begin both actions in owner-confirmation mode. Keep independent automatic-mode
  flags and require a private exact-match corpus, 20 error-free confirmed live
  batches for that action, and an agreeing independent verification extraction
  before considering autonomy.
- Persist durable local batch, file, retry, decision, receipt, and append-only
  capture-to-listing action history. Use provider-neutral current sale-listing
  lineage for analytics; never publish capture tables, Slack identifiers,
  screenshots, captions, or raw model output.
- Retain terminal screenshot evidence for 90 days under ignored `data/app/`, create
  and integrity-check an online SQLite backup immediately before mutation, and retry
  a failed Slack receipt separately from an already committed database action.

### Planning artifacts

- Added `notes/Slack Screenshot Sales Automation Design.md` with the approved scope,
  action algorithms, architecture, data model, security boundaries, state machine,
  failure handling, and rollout gates.
- Added `notes/Slack Screenshot Sales Automation Implementation Plan.md` with a
  test-first, atomic-commit task sequence from private examples through dry run,
  confirmation pilot, and separately gated optional autonomy.
- Gate 0 requires at least one private labeled example of each supported client
  layout before prompts or row semantics are finalized. Those artifacts must stay
  outside Git.

### Verification

- Verified the two planning files against the current package, migration, snapshot,
  dbt, test, and documentation layout.
- Ran documentation whitespace and public-file-policy checks; results are recorded in
  the final handoff for this session.
- This planning work changed documentation and project records only. It did not
  change dependencies, application files, database schema, operational rows, a Slack
  app, an OpenAI project, or external configuration. Unrelated uncommitted Sales
  application and test changes appeared concurrently in the shared worktree; they
  were preserved without review or modification.

## Compact item recipe controls and quantity continuity

### Implementation

- Consolidated Craft Quantity, the total-cost preview, calculator cart status/action,
  and Open Recipe Calculator into one responsive horizontal control bar on item
  detail. The existing help text remains below the controls, and narrow screens may
  wrap rather than overflow.
- Added one-use, item-keyed session state for Craft Quantity around recipe ingredient
  price submissions. The redirected page restores the quantity before recalculating
  ingredient quantities and costs, then removes the transient value; the preview
  remains non-authoritative and resets after the user leaves the item workflow.
- Extended the item recipe web test to cover the consolidated control structure and
  the save/restore browser-state hooks.

### Verification

- `uv run pytest -q tests/python/test_web.py`: 63 passed.
- JavaScript syntax, scoped Python lint and formatting, package compilation,
  whitespace, and public-file-policy checks passed.
- `./scripts/check.sh` was attempted and stopped at Ruff on eight unrelated errors in
  the concurrently added Slack-capture implementation and tests. Those files were
  preserved without modification.

## Slack screenshot Sales automation implementation

### Work completed

- Added isolated worker configuration and locked OpenAI 3.6.0, Slack Bolt 1.30.0,
  and Pillow 12.3.0 dependencies. The normal FastAPI configuration remains usable
  without Slack or OpenAI secrets.
- Added Alembic revisions `0009` and `0010` for private capture batch/file/action
  audit state and nullable provider-neutral listing/sale lineage. The operational
  snapshot, BigQuery schema evolution, dbt staging, `fct_sales`, schema docs, and
  synthetic seed carry only generic lineage.
- Added validated streamed evidence storage for PNG/JPEG/WebP, size limits, SHA-256
  paths, 90-day terminal retention, path-containment checks, and integrity-checked
  online SQLite backups. Each valid file is durably linked before later attachments
  are processed, preventing untracked evidence after a partial invalid batch.
- Added strict screenshot schemas and an OpenAI Responses adapter using base64 image
  data, original detail, Pydantic structured output, `store: false`, and no tools.
  A private ignored aggregate-only gold evaluator and one labeled `sold` case are
  present.
- Added deterministic `sold` and `market` planners. Both enforce action/screen
  agreement, exact catalog identity, latest recipes, approved professions, whole
  prices, atomic rejection, and stale-preview revalidation. `sold` marks oldest
  exact active matches at the Slack timestamp; `market` adds only missing exact
  active counts and linked append-only observations.
- Added the single-owner/private-channel Slack Socket Mode worker with durable
  pre-ack intake, message and hash idempotency, leases, capped provider retries,
  history catch-up, action selection, previews, confirmation/rejection, separate
  receipt retry, evidence purge, and a schema/configuration `--check` mode.
- Kept the shipped executable confirmation-only: it rejects either auto-commit flag
  when true. Live `market` extraction is also hard-disabled until a private labeled
  marketplace screenshot validates the screen layout; such messages enter
  `needs_review` without an OpenAI call or Sales mutation.
- Added a secret-free Slack app manifest and an owner runbook covering private app
  setup, least-privilege scopes, secrets, migrations, evaluation, startup, history
  timestamps, exact action semantics, recovery, retention, correction, shutdown,
  and the local/analytical data boundary.

### Operational gates still open

- No Slack workspace/app/channel was created or changed, no tokens were available,
  and no live Socket Mode dry run or controlled confirmation pilot was performed.
- No OpenAI API key was available, so the private `sold` gold case was not evaluated
  against the live configured model.
- No marketplace screenshot was supplied. The market reconciliation service is
  synthetic-test complete, but its vision prompt and live path remain gated.
- The canonical application database was not migrated or mutated, and no BigQuery
  snapshot or dbt Cloud build was triggered.

### Verification

- Focused capture/configuration/CLI/documentation tests passed: 61 tests.
- `./scripts/check.sh` passed: Ruff lint and formatting, 316 Python tests, package
  compilation, dbt profile validation and parsing, nine seed loads, the 126-node dbt
  build, SQLFluff, and public-file policy.
- `uv lock --check`, `git diff --check`, and a direct ignore check for the private
  gold manifest passed. Final status contained no screenshot, database, backup,
  token, Slack payload, raw model output, or evaluation label.

### Live database schema recovery

- Confirmed the running `dofus-web` process used the project default
  `data/app/dofus_touch.sqlite3`, which was healthy but still at Alembic `0008` while
  the application model selected the new `0010` listing-lineage columns.
- Created and integrity-checked the ignored recovery backup
  `data/app/backups/dofus-touch-before-slack-schema-0010-20260830T000648366846Z.sqlite3`.
- Applied the documented Alembic upgrade from `0008` through `0009` and `0010`.
  SQLite integrity remained `ok`; all 336 preexisting sale-listing rows had identical
  hashes across every preexisting column before and after migration. Active/sold
  counts remained 169/167 and recorded sold revenue remained 13,396,997 kamas.
- Verified the four lineage columns exist, existing listing sources were backfilled
  to `manual`, the database reports version `0010`, and the already-running `/sales`
  endpoint returns HTTP 200 without a restart.

### Codex CLI subscription bridge

- Replaced the direct OpenAI Responses/Python SDK transport with a local
  `CodexCliVisionAdapter`. The bridge reuses the saved ChatGPT login reported by
  `codex login status`, so neither the worker nor evaluator requires
  `OPENAI_API_KEY`.
- Removed the OpenAI Python dependency and its transitive-only lock entries. Added
  worker settings for the Codex binary, optional model override, and 180-second
  timeout; blank model configuration uses the current subscription default.
- Hardened each `codex exec` call with ephemeral mode, ignored user config and rules,
  disabled shell/multi-agent/view-image/web-search tools, a read-only sandbox, an
  isolated temporary working directory, no inherited shell environment, and a
  process-environment allowlist that excludes Slack and application secrets.
- Passed screenshot paths through the CLI's image option, supplied a strict
  Pydantic-derived JSON Schema, and read only the final structured message file.
  Adjusted the emitted schema so every property is required, matching Codex's
  structured-output contract while retaining the app-side default for warnings.
  Provider stderr and stdout are neither logged nor persisted; only a safe reported
  model identifier is extracted for the existing audit field.
- Updated the README, architecture, approved design, implementation plan, public-safe
  environment example, and owner runbook for ChatGPT subscription authentication and
  the unchanged screenshot-disclosure boundary.
- Verified Codex CLI 0.151.0 is logged in using ChatGPT. A tool-disabled blank-image
  probe returned a valid `other` extraction. The private ignored `sold` gold case
  passed 1/1 with zero false positives through the subscription bridge; no private
  screenshot content or labels were printed or tracked. Live marketplace evaluation
  remains blocked by the missing labeled screenshot, and no Slack workspace action or
  Sales mutation was performed.
- The real read-only worker readiness command passed against canonical schema `0010`
  and the saved ChatGPT login. Focused bridge/configuration/evaluation/CLI/worker
  verification passed 31 tests. The final `./scripts/check.sh` passed Ruff lint and
  formatting, all 323 Python tests, package compilation, dbt debug/parse, nine seed
  loads, the 126-node dbt build, SQLFluff, and public-file policy.

## Insights category reconciliation

### Findings and implementation

- Traced the Insights `Uncategorized` row to five exact, verified manual catalog
  items with null display categories. The current official Dofus Touch catalog
  identifies Ambusherboots and Boots Kwish as Boots, Captain Chafer's Spare Panties
  and Chouquish Belt as Belt, and Daggero's Red Necklace as Amulet.
- Confirmed Crobacape and Gorgoyle Cape are officially Cloaks. Updated catalog sync
  to fill a missing category only from a unique exact official match and to refine
  the legacy Cape label to Cloak while preserving `identity_category` and raw source
  provenance.
- Kept official Ceremonial Cape catalog identities intact because the game exposes
  them separately, including names duplicated across Cloak and Ceremonial Cape.
  Insights now rolls Cape and Ceremonial Cape into the broader Cloak reporting family.

### Local reconciliation

- Created and integrity-checked ignored online backup
  `data/app/backups/dofus-touch-before-category-reconciliation-20260830T005138Z.sqlite3`.
- Updated only the `category` field on the seven confirmed local items. All 351 sale
  listings and their 32,235,847-kama asking-price total remained unchanged, SQLite
  integrity remained `ok`, and zero sale listings now reference a null category.
- The current code projects six Insights categories with no Uncategorized row;
  Cloak combines 33 completed sales, 19 sold-item groups, 34 active listings, and
  2,081,497 recorded revenue.

### Verification

- Focused catalog-sync, Insights, and web tests passed: 77 tests.
- `./scripts/check.sh` passed: Ruff lint and formatting, all 324 Python tests,
  package compilation, dbt debug/parse, nine seed loads, the 126-node dbt build,
  SQLFluff, and public-file policy.
- Scoped whitespace and direct SQLite integrity checks also passed.
