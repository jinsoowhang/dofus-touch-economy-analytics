# Session Notes 2026-09-03

## Screenshot sales recorded for September 2 and 3

### Request and interpretation

- The user supplied three sold-notification screenshots outside the repository: two
  for yesterday, interpreted as the Pacific calendar date 2026-09-02, and one for
  today, interpreted as 2026-09-03.
- The two September 2 images contained 35 complete visible occurrences. Partially
  visible boundary lines were excluded rather than inferred or guessed. The
  September 3 image contained 15 complete visible occurrences.
- Because no sale time was supplied for September 2, its shared effective timestamp
  is 2026-09-02 23:59:59 America/Los_Angeles. September 3 uses the screenshot's local
  save time, 2026-09-03 20:48:12.245071 America/Los_Angeles, which avoids assigning a
  future time.

### Reconciliation and operational update

- Rehearsed both batches through the deterministic sold-capture planner. Every
  in-scope name resolved to one exact active catalog item with enough active Sales
  listings. Exact-price candidates were reserved first, then the oldest remaining
  exact-item candidate was used where a price correction was necessary.
- Atomically marked 49 listings sold through the transaction-ready Sales service:
  34 for September 2 and 15 for September 3. All use manual sale lineage because the
  images were supplied directly rather than ingested as Slack capture batches.
- Corrected the selected Shika's Hat Sales Price from 99,000 to the screenshot's
  44,000 kamas and appended its linked quantity-one price observation at the sale
  timestamp.
- Preserved Pork Loin ** remained unchanged because its latest recipe profession is
  Hunter, outside the approved Tailor, Shoemaker, and Jeweller screenshot scope.
- Created ignored integrity-checked online backup
  `data/app/backups/dofus-touch-before-manual-screenshot-sales-2026-09-02-and-2026-09-03-20260904T035219754844Z.sqlite3`
  before the single transaction. The screenshots remain outside the repository.

### Result and verification

- September 2 records 34 sales and 2,104,250 kamas revenue. Recipe cost is known for
  32 sales: 1,476,459 kamas cost and 615,541 kamas profit over the covered sales.
- September 3 records 15 sales and 1,272,000 kamas revenue. Recipe cost is known for
  14 sales: 954,041 kamas cost and 278,959 kamas profit over the covered sales.
- Confirmed every selected listing has the intended Pacific sale date, timestamp,
  and manual source. SQLite integrity is `ok` for both the live database and backup,
  and the running `/sales` page returned HTTP 200.
- No application code, raw screenshot, local database, or backup was added to Git.
