# dbt Developer and BigQuery setup

This guide creates a hosted dbt pilot without removing the reproducible local
dbt Core and DuckDB workflow. The hosted environment must use synthetic data until
a secure analytical loader for contract-approved private data is approved.

## Assumptions

- Use a dedicated Google Cloud project for this repository. The commands below grant
  the dbt service account project-level BigQuery roles and are too broad for a shared
  production project.
- Use the BigQuery `US` multi-region unless existing data already uses another
  location. Every related dataset must use the same location.
- Use dbt's Core `Latest` release track during the pilot. BigQuery support in the
  hosted Fusion v2 runtime is currently preview.
- Keep `profiles.yml`, `dbt-core`, and `dbt-duckdb` for local development and CI until
  BigQuery parity is demonstrated with real models.

Do not place a service-account JSON key in this repository, a shell command, a note,
or a chat. If a key is downloaded into the checkout accidentally, move it under the
ignored `.secrets/` directory immediately, upload it directly to dbt, then securely
remove the local copy. Never commit it.

## 1. Prepare BigQuery

Open Google Cloud Shell in the dedicated project. Set these values, replacing only
the project ID or location:

```bash
export DOFUS_GCP_PROJECT_ID='replace-with-project-id'
export DOFUS_BQ_LOCATION='US'
export DOFUS_DBT_SERVICE_ACCOUNT='dbt-cloud'
```

Enable the APIs, create the service account, and create the two base datasets:

```bash
gcloud config set project "${DOFUS_GCP_PROJECT_ID}"
gcloud services enable bigquery.googleapis.com iam.googleapis.com

gcloud iam service-accounts describe \
  "${DOFUS_DBT_SERVICE_ACCOUNT}@${DOFUS_GCP_PROJECT_ID}.iam.gserviceaccount.com" \
  >/dev/null 2>&1 || gcloud iam service-accounts create \
  "${DOFUS_DBT_SERVICE_ACCOUNT}" \
  --display-name='dbt Developer BigQuery'

bq show "${DOFUS_GCP_PROJECT_ID}:dofus_dev" >/dev/null 2>&1 || \
  bq --location="${DOFUS_BQ_LOCATION}" mk --dataset \
  --description='dbt development base dataset' \
  "${DOFUS_GCP_PROJECT_ID}:dofus_dev"

bq show "${DOFUS_GCP_PROJECT_ID}:dofus_prod" >/dev/null 2>&1 || \
  bq --location="${DOFUS_BQ_LOCATION}" mk --dataset \
  --description='dbt production base dataset' \
  "${DOFUS_GCP_PROJECT_ID}:dofus_prod"
```

Grant the two roles dbt documents for reading and creating BigQuery tables and
views:

```bash
export DOFUS_DBT_SERVICE_ACCOUNT_EMAIL="${DOFUS_DBT_SERVICE_ACCOUNT}@${DOFUS_GCP_PROJECT_ID}.iam.gserviceaccount.com"

gcloud projects add-iam-policy-binding "${DOFUS_GCP_PROJECT_ID}" \
  --member="serviceAccount:${DOFUS_DBT_SERVICE_ACCOUNT_EMAIL}" \
  --role='roles/bigquery.dataEditor'

gcloud projects add-iam-policy-binding "${DOFUS_GCP_PROJECT_ID}" \
  --member="serviceAccount:${DOFUS_DBT_SERVICE_ACCOUNT_EMAIL}" \
  --role='roles/bigquery.user'
```

The configured custom schemas cause dbt to create datasets such as
`dofus_dev_staging` and `dofus_prod_marts`. `roles/bigquery.user` permits those
dataset creations. If this is not a dedicated project, stop instead and pre-create
all required datasets with dataset-level grants before connecting dbt.

In Google Cloud Console, open **IAM & Admin > Service Accounts**, select the
`dbt-cloud` account, then choose **Keys > Add key > Create new key > JSON**. This is
the only credential format available to a free dbt Developer account for both
development and deployment. Treat the downloaded file as a secret. Upload it in the
next step; do not open or copy its contents into project files.

## 2. Connect dbt to BigQuery

In dbt:

1. Open **Account settings > Connections > New connection**.
2. Select **BigQuery**, not **BigQuery (Legacy)**.
3. Upload the service-account JSON key.
4. Set **Location** to the exact value used for the datasets, such as `US`.
5. Set **Maximum bytes billed** to `1000000000` for the pilot. A query estimated
   above 1 GB will fail before execution instead of incurring query charges.
6. Save and use **Test connection**.
7. After the test passes, remove the downloaded JSON file from the local machine.
   Do not delete or disable the corresponding key in Google Cloud while dbt uses it.

If the optional settings are not shown on the global connection screen, attach the
connection to the project first, then open the project's development connection and
set **Maximum bytes billed** there.

## 3. Connect the GitHub repository

The repository is:

```text
https://github.com/jinsoowhang/dofus-touch-economy-analytics
```

Use dbt's native GitHub integration and grant the dbt GitHub application access only
to this repository. Select `main` as the production branch. The native integration is
preferred because it supports the normal branch and pull-request workflow.

The dbt platform supplies connection profiles from its environment settings. It does
not use the tracked local `profiles.yml` file.

## 4. Configure environments

Create or confirm these settings:

| Setting | Development | Deployment |
| --- | --- | --- |
| Connection | BigQuery pilot connection | BigQuery pilot connection |
| Project | Google Cloud project ID | Google Cloud project ID |
| Dataset | `dofus_dev` | `dofus_prod` |
| Target name | `dev` | `prod` |
| Threads | `4` | `4` |
| Runtime | Core `Latest` | Core `Latest` |

Use the same service account for both environments during the solo pilot. Separate
development and deployment identities before the project becomes multi-user or
production-sensitive.

## 5. Verify the pilot

In the Studio IDE:

1. Open the project and create a development branch.
2. Run `dbt parse`.
3. Run `dbt compile`.
4. Confirm the project name is `dofus_touch_economy_analytics` and no private local
   paths or files appear in the IDE.

The repository intentionally has no domain models yet, so a successful connection,
parse, and compile are the complete hosted verification for this milestone. Do not
add a placeholder model solely to make a job build a relation.

After the first real model and synthetic source fixture exist, create a manual
deployment job named `Production build` with `dbt build`. Keep scheduling disabled
until there is a deterministic ingestion process that lands data before the job.

## 6. Cost and data boundaries

- Keep the per-query maximum in dbt and configure a small BigQuery daily custom query
  quota as a second guardrail.
- Do not upload the private CSV exports manually to make the Cloud connection appear
  complete.
- The future loader must validate contracts, preserve load metadata, report rejected
  rows, and authenticate without placing credentials in Git.
- Only contract-approved private tables or documented synthetic fixtures may feed
  hosted dbt models.

## Completion checklist

- [ ] BigQuery base datasets exist in the selected location.
- [ ] The `dbt-cloud` service account has only the required BigQuery roles in a
      dedicated project.
- [ ] dbt's BigQuery connection test passes.
- [ ] GitHub `main` is connected through the native integration.
- [ ] Development uses `dofus_dev`; deployment uses `dofus_prod`.
- [ ] `dbt parse` and `dbt compile` pass in the Studio IDE.
- [ ] No service-account JSON file, raw CSV, or private database is tracked.
- [ ] No scheduled production job exists before deterministic ingestion and real
      models exist.

## References

- [Connect BigQuery in dbt](https://docs.getdbt.com/docs/platform/connect-data-platform/connect-bigquery)
- [Configure Git in dbt](https://docs.getdbt.com/docs/platform/git/configure-git)
- [BigQuery IAM roles](https://cloud.google.com/bigquery/docs/access-control)
- [BigQuery cost controls](https://cloud.google.com/bigquery/docs/best-practices-costs)
- [Google service-account security](https://cloud.google.com/iam/docs/best-practices-service-accounts)
