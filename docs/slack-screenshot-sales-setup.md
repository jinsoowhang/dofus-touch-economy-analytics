# Slack screenshot Sales setup

This runbook configures the private, confirmation-required `#dofus-touch` pilot. The
worker receives screenshots over Slack Socket Mode, stores its audit state in the
local SQLite application database, asks a local Codex CLI process only for structured
visual extraction, and applies deterministic Sales rules after the allowlisted owner
confirms a preview. The CLI uses the owner's saved ChatGPT subscription login; no
OpenAI API key is required. The worker does not control or scrape the game client.

## Current release boundary

- Only one configured workspace, private channel, and owner user are accepted.
- Only top-level PNG, JPEG, and WebP file messages are accepted. Threads and bot
  messages are ignored.
- `sold` is implemented in confirmation mode. It should not be treated as validated
  until the private gold-set evaluation and controlled Slack pilot pass.
- `market` reconciliation is implemented and unit-tested, but live marketplace image
  extraction is deliberately disabled until a private labeled marketplace screenshot
  validates the layout. A `market` message currently ends in `needs_review` without a
  model call or database mutation.
- The executable rejects either auto-commit flag when set to `true`. Do not enable
  autonomy without the separate evaluation, pilot, and ADR gates in the approved
  design.

## 1. Create the private Slack app

1. Manually create a private Slack channel named `#dofus-touch`.
2. In Slack's app management site, create an app **from an app manifest** and paste
   [slack-app-manifest.yml](slack-app-manifest.yml).
3. Install the app to the intended workspace.
4. In **Basic Information > App-Level Tokens**, generate an `xapp-` token with only
   `connections:write`. This app-level token cannot be declared in the manifest.
5. Invite the installed bot to the private channel. Private-channel history and files
   are unavailable until the app is a member.
6. Record the workspace ID, private-channel ID, and the single owner's member ID.
   Slack exposes the channel and member IDs from their details/copy-link menus.

The manifest requests only these bot scopes: `groups:history`, `files:read`, and
`chat:write`. It enables Socket Mode, interactivity, and the `message.groups` event.
If the scopes or events change, reinstall the app before restarting the worker.

## 2. Store private configuration

Keep secrets outside Git. Create an ignored `.env.slack` file or use a private shell
environment or secret manager to set:

```bash
DOFUS_SLACK_BOT_TOKEN='<xoxb token>'
DOFUS_SLACK_APP_TOKEN='<xapp token>'
DOFUS_SLACK_WORKSPACE_ID='<workspace ID>'
DOFUS_SLACK_CHANNEL_ID='<private channel ID>'
DOFUS_SLACK_OWNER_USER_ID='<owner member ID>'
DOFUS_SLACK_SOLD_AUTO_COMMIT=false
DOFUS_SLACK_MARKET_AUTO_COMMIT=false
```

Never commit `.env.slack` or paste either token into logs, issues, or chat. The
repository's `.gitignore` excludes `.env.*` files except the public-safe example.

`.env.example` documents the optional Codex binary, model, timeout,
approved-profession, and evidence-path settings. With the model setting blank, the
worker uses the current Codex CLI subscription default. It also defaults to a
180-second extraction timeout, a 20 MiB image limit, a 90-day terminal-evidence
retention period, and the `Tailor`, `Shoemaker`, and `Jeweller` professions.

Install Codex CLI separately and sign in interactively with the ChatGPT account whose
subscription should fund the work:

```bash
codex login
codex login status
```

The status must report a ChatGPT login. The worker intentionally rejects API-key
authentication for this local bridge. `codex exec` reuses the saved CLI
authentication, as documented in OpenAI's
[non-interactive mode guide](https://learn.chatgpt.com/docs/non-interactive-mode).
Screenshots still leave the machine and are disclosed to OpenAI through Codex; the
bridge changes authentication and billing, not that disclosure boundary.

## 3. Prepare and validate the local worker

Install the locked environment and explicitly migrate the same database used by the
Web UI:

```bash
uv sync --locked --all-groups
DOFUS_APP_DATABASE_PATH=data/app/dofus_touch.sqlite3 uv run alembic upgrade head
uv run --env-file .env.slack dofus-slack-worker --check
```

The check is read-only: it validates required configuration, requires schema revision
`0010`, locates Codex CLI, and verifies its saved ChatGPT authentication. It does
not connect to Slack, invoke a model, send a screenshot, or migrate automatically.

The ignored private gold manifest can be evaluated separately after its screenshots
and labels have been reviewed:

```bash
uv run dofus-evaluate-captures \
  --manifest data/app/slack_sales_evidence/gold/manifest.json
```

The evaluator prints aggregate pass/fail counts only. It sends every referenced
screenshot to OpenAI through the local Codex CLI, consuming subscription usage, so run
it only when that disclosure is acceptable. Keep the manifest, labels, screenshots,
and model results under ignored local paths.

## 4. Run the confirmation pilot

Start the Web UI and worker in separate terminals against the same database:

```bash
uv run dofus-web
uv run --env-file .env.slack dofus-slack-worker
```

At startup the worker purges eligible old terminal evidence, catches up channel
history from its persisted watermark, and then opens Socket Mode. Use
`--skip-history-catch-up` only when intentionally excluding missed messages.

Post screenshots as one top-level message. The exact first non-empty caption line is
the action:

```text
sold
```

or:

```text
market
```

If the caption is absent or unrecognized, Slack presents owner-only action buttons.
One message and all of its images form one atomic batch. The Slack message timestamp
becomes the effective sold/listing time; history catch-up can therefore propose
backdated changes, but never bypasses confirmation.

For `sold`, a row such as invented item **Synthetic Hat** at 47,000 kamas can mark
only the oldest active Web UI listing with that exact catalog identity and price.
Repeated screenshot rows require the same number of exact active listings. The action
never creates a listing.

For `market`, the intended rule is additive count reconciliation: create only the
missing number of exact craftable item-and-price occurrences. Different active prices
conflict; extra Web UI rows remain untouched; nothing is repriced, deleted, or marked
sold. In this release, the live image-layout gate prevents this action from reaching a
preview or write.

Any ambiguity, unknown name, action/screen mismatch, stale preview, partial duplicate,
unsupported file, or provider disagreement moves the full batch to review and writes
no Sales changes. Review the Slack preview against the screenshot and Web UI before
selecting **Confirm**. **Reject** is terminal and changes no Sales data.
After either decision, the worker removes the interactive buttons from the preview
and updates that same message with the terminal result.
For a committed `sold` batch, the terminal receipt reports listings sold, total
recorded sales revenue, known cost and profit with cost coverage, items that became
out of stock, and screenshot rows excluded as out of scope. Missing cost snapshots
remain excluded from cost and profit instead of being treated as zero.

## Recovery, correction, and shutdown

- Immediately before each confirmed mutation, the worker creates an
  integrity-checked SQLite backup in `data/app/backups/`. Capture evidence is stored
  under `data/app/slack_sales_evidence/`.
- Terminal evidence is purged after 90 days on worker startup. Audit hashes, status,
  extraction metadata, and action history remain in SQLite. Nonterminal review
  evidence is retained until the batch is resolved.
- Exact duplicate Slack deliveries and exact duplicate image batches are no-ops.
  Slack receipt delivery is retried separately and cannot repeat a committed write.
- If a sale was confirmed incorrectly, use the Web UI's audited reopen action. Do not
  edit or delete append-only price observations.
- Stop the worker with Ctrl+C. To decommission it, stop the worker, revoke both Slack
  tokens, remove the app from the channel/workspace, and run `codex logout` if this
  machine should no longer retain ChatGPT authentication.

## Data boundary

Screenshots, captions, Slack IDs, tokens, raw extraction JSON, capture audit tables,
and backups stay local and Git-ignored, except that screenshot pixels are sent to
OpenAI for the requested Codex inference. The Codex subprocess runs ephemerally in a
temporary directory with user configuration and rules ignored, a read-only sandbox,
shell, multi-agent, local-image-tool, and web-search access disabled, and no inherited
Slack or application secrets. The normal snapshot loader publishes only generic
nullable sale-listing lineage (`listing_source`,
`listing_capture_uuid`, `sale_source`, and `sale_capture_uuid`) alongside normalized
listing data. It does not publish capture tables or trigger BigQuery/dbt
automatically.

Before any controlled pilot, run `./scripts/check.sh`, take a separate recovery
backup, and compare the screenshot, preview, and Web UI before and after every
confirmation. Record only aggregate evaluation and pilot results in tracked notes.
