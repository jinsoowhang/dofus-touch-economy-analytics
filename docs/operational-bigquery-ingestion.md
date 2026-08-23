# Operational BigQuery ingestion

This workflow publishes the private, normalized SQLite application state to the
existing `dofus_dev` and `dofus_prod` BigQuery datasets. dbt then transforms the
latest complete snapshot into documented staging, intermediate, and mart models.

The SQLite database and its row data remain ignored local files. The public
repository contains only the loader, schemas, transformations, and synthetic tests.

## What is loaded

The loader reads these normalized operational tables in one read-only transaction:

| SQLite table | BigQuery raw table | Contents |
| --- | --- | --- |
| `import_batches` | `raw_import_batches` | Import checksums, filenames, status, and counts |
| `source_records` | `raw_source_records` | Accepted and rejected source-row provenance |
| `items` | `raw_items` | Canonical item catalog |
| `source_item_names` | `raw_source_item_names` | Exact source-name resolution decisions |
| `recipes` | `raw_recipes` | Versioned recipe headers |
| `recipe_ingredients` | `raw_recipe_ingredients` | Ordered recipe ingredients and quantities |
| `price_observations` | `raw_price_observations` | Price history and invalidations |
| `sale_listings` | `raw_sale_listings` | Active and sold application listings |

The ambiguous `data/raw/item_sales.csv` is not read. Sales come from normalized
application rows, which have stable IDs, deterministic UTC timestamps, item IDs, and
explicit active or sold state.

## Safety and publication contract

- The exact SQLite schema must match the loader contract. Missing or unexpected
  columns stop the load instead of being guessed.
- Required nulls and invalid timestamps stop extraction.
- A SHA-256 content hash identifies each immutable snapshot.
- Every raw row receives `_snapshot_id` and `_extracted_at` metadata.
- Raw tables are partitioned by extraction date and clustered by snapshot ID.
- The loader appends `raw_snapshot_manifest` last. dbt reads only the newest
  manifested snapshot, so an interrupted partial upload never becomes current.
- Rerunning an already published snapshot is a no-op. Retrying a partial snapshot
  replaces only rows with that same content hash.
- Source values are not written to logs or tracked intermediate files.

## Preview locally

From the repository root, use the dry run before every upload:

```bash
uv run dofus-load-bigquery --dry-run
```

It prints the content hash, application schema version, and table row counts without
contacting Google or printing source rows.

The default database is `data/app/dofus_touch.sqlite3`. To inspect another ignored
database explicitly:

```bash
uv run dofus-load-bigquery \
  --database-path=data/app/another.sqlite3 \
  --dry-run
```

## Authenticate without another key file

The loader uses Google Application Default Credentials (ADC). Install the Google
Cloud CLI, then run:

```bash
gcloud auth application-default login
gcloud auth application-default set-quota-project claude-projects-489306
```

This browser sign-in is for the local loader only. dbt Cloud continues using its
existing service-account credential. Do not download, copy, or commit another JSON
key.

## Load both datasets

Run:

```bash
uv run dofus-load-bigquery \
  --project-id=claude-projects-489306 \
  --location=US
```

Both `dofus_dev` and `dofus_prod` are loaded by default. To limit a test to
development, add `--dataset=dofus_dev`. The two datasets must already exist in `US`;
the loader intentionally does not create or relocate datasets.

The loader caps its manifest and retry queries at 1 GB processed. The connection's
1 GB maximum-bytes-billed setting separately protects dbt queries. The configured
project daily query quota is another enforcement control. The $10 monthly budget is
an alert, not a hard spending cap; BigQuery storage and any other enabled Google
Cloud services can still accrue charges.

## Run from the local website

Open the FastAPI website and choose **BigQuery Sync** in the top navigation. Review
the fixed project, location, datasets, and source, then select **Update BigQuery
Now** and confirm the publication. A terminal-style panel polls the in-process job
and shows snapshot, dataset, table, row-count, manifest, success, or failure progress.

The page uses the same content-addressed, manifest-last loader as the command above.
Only one run can be active in a web-server process, and the browser cannot provide a
command or override the configured targets. Output is capped in memory and does not
include source rows or credentials. The latest run state disappears when the web
server restarts.

The web server inherits local Google Application Default Credentials. If the panel
reports that credentials are unavailable, stop and run the `gcloud auth
application-default login` procedure above in the same operating environment before
retrying. A successful page run updates raw snapshots only; it does not invoke dbt
Cloud or refresh development or production marts.

## Verify in the Google Cloud sidebar

1. Open the Google Cloud console and select project `claude-projects-489306` in the
   top project picker.
2. Open the left navigation menu and choose **BigQuery**.
3. In the BigQuery **Explorer** sidebar, expand
   **claude-projects-489306 > dofus_dev**.
4. Confirm `raw_snapshot_manifest` plus the eight `raw_*` source tables appear.
5. Open `raw_snapshot_manifest`, then select **Preview**. The newest row is the
   snapshot that dbt will use.
6. Repeat under **claude-projects-489306 > dofus_prod**.

## Build and verify in the dbt sidebar

After new dbt code is present in the connected GitHub branch:

1. In dbt Cloud, open the left sidebar and select **Studio**.
2. Open **Dofus Touch Economy Analytics** and select the development branch that
   contains these models.
3. In the command bar at the bottom, run `dbt build`.
4. In the left file tree, open `models/marts/marts.yml`, then use the documentation
   or lineage view to inspect the tested models.
5. Return to Google Cloud **BigQuery > Explorer**. Refresh the project and expand
   `dofus_dev_marts`; it should contain `dim_items`, `fct_price_observations`,
   `fct_sales`, and `fct_recipe_ingredients`.

The production raw snapshot is available immediately after loading, but production
dbt marts appear only after a deployment job runs `dbt build`. Keep that job manual
until repeated development builds pass and costs have been observed.

## dbt model grains

- `dim_items`: one canonical item.
- `fct_price_observations`: one valid or invalidated price observation.
- `fct_sales`: one active or completed application sale listing.
- `fct_recipe_ingredients`: one ingredient position in the latest recipe for each
  crafted item.
- `int_latest_valid_price_observations`: one latest valid price per item and market.
- `int_latest_recipes`: one latest recipe version per crafted item.

Every model has schema tests for its keys and relationships. Singular tests enforce
positive quantities and prices, ordered sale dates, and unique recipe positions.
