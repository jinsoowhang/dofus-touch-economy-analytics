# Memory

**Last updated:** 2026-08-22

## Dofus Touch Economy Analytics

- Public identity: analytics engineering for player-observed Dofus Touch item prices, crafting economics, sales behavior.
- The public README presents the current system as a local-first economy tracker and
  hosted analytics project. It states explicitly that FastAPI writes to SQLite and
  that BigQuery snapshots plus dbt builds are manual, separate publication steps.
- Local stack: Python 3.12, uv, FastAPI, Jinja, vendored HTMX, SQLAlchemy, Alembic, SQLite, dbt Core, dbt-duckdb, and DuckDB.
- Implemented application: a loopback-only FastAPI/Jinja/vendored-HTMX website with versioned JSON endpoints. SQLite owns operational state while DuckDB and dbt remain the downstream analytical layer.
- Application prices are append-only observations with audit-preserving invalidation. Item Search records total price with implicit quantity one; each new `item_cost.csv` checksum now seeds idempotent, lot-one current-price observations, using the last file occurrence for duplicate identities without creating Sales listings.
- Hosted dbt models consume the latest fully manifested BigQuery snapshot: nine
  operational staging models, latest-valid-price and latest-recipe intermediate
  models, and item, price-observation, Sales, and recipe-ingredient marts. Tests
  enforce identifiers, relationships, positive amounts, recipe-position uniqueness,
  and ordered Sales dates.
- Raw CSVs, SQLite and DuckDB databases, import reports, secrets, task-observer files, and worktrees stay local and ignored.
- Canonical local sources: `item_sales.csv`, `item_recipes.csv`, and `item_cost.csv` under `data/raw`.
- Only synthetic samples may be committed until redistribution rights are established.
- Current CSV abbreviated dates mean ingestion and date-dependent models require deterministic ISO dates from a re-export or an explicitly approved parsing rule; never infer missing years.
- Source-derived costs, profits, differences, and ROI are preserved for reconciliation but recomputed as governed measures.
- `item_cost.csv` and `item_recipes.csv` are included in the application importer; `item_sales.csv` remains deferred until its dates and grain are deterministic.
- Item identity uses whitespace-collapsed Unicode case-folded exact names. Cost identities also include normalized category; ambiguous recipe ingredients remain unresolved rather than being guessed.
- A no-result search offers advisory close-name links and manual item creation. Similarity never establishes identity, exact duplicates are blocked, and each item records whether it was first created by import or manually.
- Manual item names and entered category overrides are whitespace-normalized and title-cased at the start of each space-delimited word; apostrophes and other punctuation do not start a new capitalized word. When category is omitted, a reviewed final-word equipment suffix may infer it; explicit category input wins and arbitrary substrings never classify an item.
- The shared page header exposes Item, Sales, and BigQuery Sync as top-level navigation. Item opens a hover-, click-, and keyboard-accessible submenu containing Item Search, Recipes, and Recipe Calculator; the active item destination remains identified inside that submenu. A blank item query renders the full catalog; typing filters it by normalized name, and an optional exact Category filter combines with the name query. Item Search headers sort by name, category, current price, or observation date in either direction, with inactive headers starting descending, active filters preserved, and missing values kept last.
- Item icons are cached locally by UUID and shown in Item Search, item detail, recipes, and Sales. Fetching prefers the current Dofus Touch client data, then exact DofusDB and Dofus Wiki matches; reviewed legacy-name aliases cover outdated source spellings without fuzzy identity matching. The live catalog sync imports every unique exchangeable Dofus Touch item/category identity without deleting local rows or replacing existing UUIDs, prices, provenance, or history.
- The ignored `data/app/item_icons/` cache is independent of SQLite. Copying or
  restoring the database does not restore its files; run `uv run dofus-fetch-icons`
  when the cache is absent. On 2026-08-22, the canonical cache was rebuilt with
  11,390 available PNGs (93 MB); ten upstream images remained unavailable.
- Live Dofus Touch recipes sync from Ankama's English client data as a checksum-idempotent, append-only provenance batch. Only exchangeable recipe results are in website scope; every crafted item and ingredient must resolve to the local catalog before any rows are written. A newer source checksum appends a new recipe version, so prior CSV recipes and price or Sales history remain intact while item detail selects the latest recipe. Recipe ingredient names link directly to item detail and show their current per-unit price and quantity-adjusted total cost; missing market observations remain explicit rather than using static client prices. Resolved per-unit prices are inline-editable on Enter or blur; each edit appends only the ingredient's price history and reloads the recalculated recipe without creating a Sales listing. Item detail also shows the standard required profession level derived from ingredient-slot unlocks: one or two ingredients require level 1, then three through eight require 10, 20, 40, 60, 80, and 100. The source `resultLevel` remains raw provenance and is not mislabeled as a profession requirement.
- The Recipes page lists the latest recipe per crafted item and derives current item price, recipe cost, profit, and ROI in bulk. Its URL-backed filters combine item-name substring, exact category, exact profession, a single dual-handle standard profession-level range, and profitable/non-profitable/unknown economics. Every displayed column sorts in either direction with missing values last, and rows link to the item's recipe section. Each Current Price cell is inline-editable on Enter or blur; a save appends a quantity-one price observation without creating a Sales listing, recalculates recipe economics, preserves filters and sorting, and restores the prior scroll offset when possible.
- The Recipe Calculator accepts up to 100 latest-recipe items with craft quantities from 1 through 1,000. It aggregates shared resolved ingredients by canonical item identity, combines their required quantities, lists consuming crafts, and derives current unit prices, extended costs, price coverage, and complete or known-cost totals. Unresolved ingredients and missing prices remain explicit; calculator selections are request-only and never mutate operational data.
- Catalog rows show title-cased category labels, latest valid total price without a currency suffix, and date-only observation time for the active market. Prices are selected in one bulk window query, and every row cell opens item detail for append-only price entry rather than direct mutation.
- Item detail presents one inline Current Price field that saves on Enter or blur and appends price history without creating a Sales listing. Visible history is a Date Observed/Price/Action table; its confirmed X action audit-invalidates and hides the selected observation, restoring the previous valid Current Price when necessary without physically deleting financial history. Crafting Metrics use responsive Recipe Cost, Profit, and percentage ROI cards, with an explicit incomplete-cost state when ingredient prices are missing.
- Each Sales row represents one item listing with an editable asking price, `selling_started_at`, and nullable `date_sold`; lot quantity is implicit and not part of the Sales workflow. New Sales entries require a positive price, and active price fields save on Enter or blur without a separate Update button. Entering or editing a Sales price appends a linked quantity-one price observation and makes it the item's current price while preserving history; Duplicate alone does not add redundant price history. Only explicit Sales actions create listings; item-page, recipe, and API price observations never enter Currently Selling. Selecting an item in the add form shows and prefills the integer median of that item's completed-sale prices with its sample count; active listings are excluded, missing history stays explicit, and the suggestion remains editable. Marking sold moves a listing into history, and the Sold History return action clears only `date_sold` to restore the same row to Currently Selling. Currently Selling and Sold History derive read-only Cost from the latest recipe and current ingredient prices, derive Profit as row price minus that cost, keep incomplete costs explicit, and sort both measures like other displayed fields. The Currently Selling summary displays both active count and summed asking price, and duplicate/mark-sold actions use accessible icons. Currently Selling row actions save and restore the exact scroll offset across their full-page refresh, with a section anchor as the no-storage fallback. Row checkboxes and a select-all control support atomic bulk Mark sold and Delete actions; bulk deletion requires confirmation, and a stale selection cannot partially mutate the batch. The add form can optionally filter items by category, and typed item matches move to the top of the dropdown. Active and sold tables sort independently by any displayed data field; inactive headers start descending, actions preserve both sort selections, and sort links return to the originating section anchor. The collapsed Sales **Filter Items** panel sits below the add form and combines normalized item-name substring, exact category, active/sold status, inclusive asking-price and computed-profit ranges, and inclusive activity-date ranges. Activity dates use `selling_started_at` for active rows and `date_sold` for sold rows in `America/Los_Angeles`; filters remain in URLs, sort links, and mutation redirects. Sales dates and chart totals are displayed and grouped in the same timezone; the chart separates Sales, known Cost, and known Profit and reports cost coverage, while stored timestamps remain UTC. Visible prices use comma grouping and comma-formatted price input is accepted. Page sections are title-cased and collapsible. Row deletion requires browser confirmation and does not delete linked price history.
- Bulk-toolbar text buttons explicitly override compact row-icon geometry so Mark
  selected sold and Delete selected share the same height, padding, line height, and
  alignment without enlarging row-level delete buttons.
- Item detail shows item-scoped Currently Selling and Sold counts derived from
  normalized application `sale_listings`. Counts are always visible, including zero,
  exclude listings for other catalog items, and link to the matching item/status
  filter on the Sales page.
- For small application iterations, avoid broad README/design-document edits unless a public contract changes or the user asks; still maintain the required `MEMORY.md` and dated session note at session end.
- A later cost import may enrich a sole uncategorized manual item with its category while preserving the stable UUID, manual creation provenance, recipes, and price observations.
- The application importer validates both file contracts before writes, is idempotent by dataset checksum, preserves accepted and rejected raw-row provenance locally, and reports how many unique cost prices were seeded.
- Additive SQLite migrations for referenced tables should use supported direct `ALTER TABLE` operations rather than batch table rebuilds while foreign-key enforcement is active; populated upgrade tests must include dependent rows.
- Operational schema, Alembic migration, import CLI, repositories and services, HTML/HTMX interface, JSON API, local security boundary, and documentation are complete on `feature/fastapi-price-tracking`.
- A repository-owned loader now extracts eight exact-schema operational SQLite
  tables in one read-only transaction and publishes content-addressed, partitioned,
  clustered raw snapshots to both BigQuery base datasets. The manifest is appended
  last so dbt cannot select an interrupted partial upload; reruns are idempotent by
  SHA-256 content hash. The loader uses user Application Default Credentials and
  never writes source rows to tracked intermediate files.
- The ambiguous `item_sales.csv` still requires deterministic dates and confirmed
  row grain. Hosted Sales analytics instead use normalized application
  `sale_listings`, whose stable IDs and timestamps satisfy the operational contract.
- Local DuckDB remains the dbt Core profile for parsing and CI. The new operational
  models require BigQuery raw tables until a local SQLite-to-DuckDB bridge provides
  equivalent sources.
- Hosted pilot: use a free single-user dbt Developer project with BigQuery while
  retaining dbt Core and DuckDB locally until model parity is demonstrated.
- Hosted pilot environments use `dofus_dev` and `dofus_prod` base datasets in a
  dedicated Google Cloud project, dbt's Core `Latest` runtime, and a 1 GB
  maximum-bytes-billed guardrail.
- The free dbt Developer plan requires service-account JSON authentication for
  BigQuery. Credential files never enter Git; `.secrets/` is ignored and rejected by
  the public-file policy.
- Hosted data remains limited to synthetic sources or normalized private SQLite
  state published through the contracted snapshot loader. Never upload private CSVs
  manually.
- Account-side BigQuery and dbt connection, GitHub, development, and production
  environment setup is complete. Snapshot
  `afc1d6b429721529f3468ae8f395f0541cc817c71f54e75537a58512af3113ea`
  is verified in both US base datasets with 67,266 normalized rows each. Guarded
  development and production BigQuery dbt builds each passed all 96 model and test
  nodes. Both marts datasets contain 11,400 items, 1,138 price observations, 181
  Sales listings, and 18,943 latest-recipe ingredient rows. No scheduled deployment
  job exists.
- Google Cloud CLI 581.0.0 is installed outside the repository under the WSL user
  directory, and user ADC is configured with `claude-projects-489306` as its quota
  project. ADC remains outside Git and can be revoked separately from dbt Cloud's
  service-account key.
- The loopback BigQuery Sync page manually runs the fixed content-addressed snapshot loader against configured project `claude-projects-489306`, location `US`, and datasets `dofus_dev` plus `dofus_prod`. A process-local manager rejects overlapping runs and retains the latest capped, timestamped progress log; the browser cannot supply commands, targets, or credentials. Table-level progress never includes source rows. A successful run updates raw snapshots only, so dbt Cloud builds remain separate manual actions.
