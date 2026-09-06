# Sales Activity Performance Research and Proposal

Date: 2026-09-05 (Pacific)
Status: Phase one authorized by “start implementing” and implemented on 2026-09-05.
The research below records the original baseline; implementation results follow.

## Recommendation

Prioritize a searchable item picker and pagination of the active/sold tables.
Combine those changes with removal of repeated Sales calculations. Use partial
HTML updates next to improve repricing, sorting, and marking sold. A move of the
runtime database to the WSL Linux filesystem is a separate, measured opportunity.

Keep FastAPI, SQLite, Jinja, and the existing HTMX stack. The evidence does not
justify a framework rewrite, a database-engine migration, Redis, or extra workers
as the first response to this page's latency.

## Method and limits

- Profiled the existing `/sales` route using an isolated application test client
  with a SQLite read-only connection and `PRAGMA query_only=ON`. Instrumentation
  lived in `/tmp`, not application source or the running web process.
- Measured the live local page in headless Chromium at 1440 × 1000: one fresh
  browser context, two subsequent loads, and active-only/sold-only views.
- Used browser-only script blocking to separate script execution from the cost of
  the document. This was diagnostic, not a proposed production configuration.
- Compared identical context construction and template rendering against the
  canonical database on `/mnt/c` and an online-backup copy under Linux `/tmp`.
  The temporary private copy was deleted after the comparison. Confirmation runs
  executed the database benchmark and browser diagnostic sequentially to avoid
  contention between the two measurements.
- These are local samples, not production percentiles or measurements from the
  user's Windows browser. Dataset size can change while the user records sales.
  Stage timings are inclusive and must not be added together.
- No application source, configuration, database state, or server process was
  changed by the research. Only project research notes were added/updated.

## Observed baseline

| Measure | Observation |
| --- | --- |
| Live full-page load | 2.00–2.06 seconds across three loads |
| Live time to first byte | 0.79–0.80 seconds |
| Isolated complete GET | 0.78–0.89 seconds across four runs |
| HTML before compression | 5,939,536 bytes, about 5.94 MB |
| HTML transferred with gzip | 553,509 bytes, about 554 KB |
| Item picker | 10,948 catalog choices plus placeholder; 3,311,889 HTML bytes |
| Sales rendered | 328 active + 412 completed = 740 rows |
| Document elements | 28,665, excluding text nodes and browser-internal nodes |
| Long main-thread tasks | 0.90–1.11 seconds total; longest 0.73–0.79 seconds |
| SQL queries per default request | 24 |
| Building item choices | Approximately 301–322 ms |
| Both calls to sold history combined | Approximately 97–132 ms |
| Standalone template rendering | Approximately 138 ms in one warmed measurement |
| Stored completed sales without cost snapshot | 137; evaluated twice on the default page |

The active-only view still took about 1.72 seconds and contained 5.02 MB of HTML.
The sold-only view took about 1.12 seconds and contained 4.34 MB. Both retained the
entire catalog picker. Browser image elements numbered 740, but images already
use `loading="lazy"`; the cold initial load fetched only 11 resources. Warm
static-resource transfers were zero, while the page still took about two seconds.

## Findings tied to the code

1. `SalesService.item_choices()` calls `CatalogRepository.search("", limit=None)`.
   It materializes every active catalog item and builds a response object with
   suggestion metadata for each. The `<select id="sale-item">` contributes about
   56% of the page's HTML. Returning fewer columns can reduce Python work, but
   retaining all 10,948 options still leaves substantial rendering overhead.
2. `_sales_context()` renders both entire listing tables. `SalesService.active()`
   and `sold()` compute responses before applying filters/sorts in Python, so a
   small filtered result does not necessarily mean proportionally less work.
3. `_sales_context()` loads sold history for its table, then `daily_totals()` calls
   `sold()` again. This repeats loading and historical-cost reconstruction for the
   137 completed rows lacking stored snapshots. Reuse must preserve the chart's
   independence from table filters: reuse an unfiltered result, not filtered rows.
4. `PriceService.current_for_items()` gets latest prices across the entire market
   and then filters in Python. The measured request needed 280 ingredient prices
   but loaded 1,385 market prices. `_recipe_costs()` also loads all recipe versions
   for the requested crafted items before choosing the latest in Python.
5. Price edits and Sales actions use full-page POST/redirect/GET behavior. Even
   small changes repeat the picker, tables, calculations, compression, and browser
   work. Existing HTMX can support smaller responses without replacing the stack.
6. JavaScript is not the sole browser bottleneck. In a diagnostic confirmation,
   total main-thread task time was about 1.31 seconds normally, 1.23 seconds with
   `sales.js` blocked, and 1.21 seconds with all page JavaScript disabled. Those
   single diagnostic samples suggest that removing scripts alone would leave
   most of the document-processing cost intact.
7. The project/database are on a Windows 9P mount. In the sequential database-only
   comparison, warmed context-plus-template samples had medians of 735 ms on
   `/mnt/c` and 514 ms with a Linux ext4 database copy, about 30% less server work.
   This excluded HTTP, gzip, and browser rendering; it is not a claim of 30% less
   end-to-end page latency, nor a measured benefit from moving the whole repo.

## Options

| Option | Scope | Likely benefit | Effort / tradeoff |
| --- | --- | --- | --- |
| A. Server-only improvements | Reuse unfiltered sold results, request-scoped derived values, SQL-scoped ingredient prices, and only necessary catalog/recipe columns/versions | Modest response-time reduction; no workflow change | Small–medium. Leaves the large HTML document and browser work intact. |
| B. Reduce initial page size — recommended | Server-backed item search with 20–50 results; independently paginated active/sold tables, initially 50 rows each | Largest opportunity to improve initial load and responsiveness as history grows | Medium. Item selection becomes search-driven; bulk-selection semantics must be explicit. |
| C. Partial updates and deferred sections | Update affected rows, totals, and counts after actions; fetch Sold History/chart content when needed | Especially valuable for repricing, sorting, and repeated marking sold | Medium. Must synchronize related sections and handle stale selections and failures. |
| D. Native WSL database/runtime location | Move the authoritative operational DB, or later the whole working environment, onto Linux storage | Measured improvement in server-side work without changing the page workflow | Small code change but operational coordination: every web/Slack/import/snapshot process must use the same DB. Does not reduce DOM size. |

### Proposed first implementation

- Add a server-backed item picker using existing HTMX, preserving category
  filtering, keyboard use, exact UUID selection, and completed-sale price
  suggestions. Query after approximately 200–300 ms of idle typing and cap results
  at 20–50. Category choices should be fetched independently from the full picker.
- Add separate pagination state for Currently Selling and Sold History, initially
  50 rows each. Apply filters and sorting to the full matching set before slicing,
  including cost/profit sorting. Keep counts, chart totals, and active listed value
  at their existing full-data grains.
- Define bulk selection before implementation: the smallest version makes Select
  all explicitly mean the current page. If cross-page selection is required, retain
  selected UUIDs separately and preserve the existing atomic validation of all
  selected records. Never silently change all-record selection into page selection.
- Load unfiltered sold data once per request and reuse it for the chart and table
  projection. Restrict current-price queries to required ingredients and load the
  latest recipes without materializing unused versions where safe.
- Measure again before adding persistent caches or new indexes.

### Follow-on improvements

- Use HTMX to save prices and refresh the affected row plus summary sections.
  Repricing can change cost/profit elsewhere, sorting position, relist dates, and
  chart values, so update the smallest correct section rather than assuming one
  DOM cell is always sufficient.
- Lazy-load Sold History/chart data when the corresponding section is opened or
  first revealed. Collapsing already-rendered HTML alone will not eliminate its
  server/query/document cost.
- Consider a coordinated native-WSL storage move if the remaining server latency
  justifies it. Keep a single authoritative DB, back it up, and update every
  configured writer/reader; do not create divergent local operational databases.
- Cross-request caches are optional later. Invalidating them must cover web writes,
  Slack confirmations, imports, recipe/catalog syncs, invalidations, and reopening
  sales. Request-scoped reuse avoids those freshness risks.

## Acceptance criteria for a later implementation

Targets, not measured promises:

- On the same machine and comparable data, warmed initial load below 1 second,
  time to first byte below 400 ms, and no main-thread task exceeding 200 ms.
- Reduce initial decoded HTML below 1 MB and rendered elements below 5,000;
  verify with representative 10× history growth as well as current data.
- No duplicate sold-history materialization on a default request. Item search and
  basic table requests should scale with a bounded result set.
- Verify price entry, suggestions, sorting, all filters, pagination, bulk actions,
  scroll restoration, missing-cost states, immutable historical cost, all-data
  chart totals, and the established two summary rows.
- Benchmark initial loads and action-to-stable-UI latency separately. Do not
  perform live mutating benchmarks on operational records; use synthetic fixtures
  or a disposable database for write flows.

## Primary references

- [SQLAlchemy performance FAQ](https://docs.sqlalchemy.org/en/20/faq/performance.html)
  distinguishes SQL execution, result fetching, ORM materialization, and code
  profiling; it recommends fetching specific columns when complete entities are
  unnecessary.
- [Google: DOM size and interactivity](https://web.dev/articles/dom-size-and-interactivity)
  explains the rendering and interaction costs of large documents and recommends
  limiting the initial DOM, including pagination where appropriate.
- [HTMX active search](https://htmx.org/examples/active-search/) demonstrates
  delayed, server-backed search using the existing application approach.
- [HTMX trigger reference](https://htmx.org/attributes/hx-trigger/) documents delayed
  input and load/revealed triggers for deferred content.
- [Microsoft: working across WSL filesystems](https://learn.microsoft.com/en-us/windows/wsl/filesystems)
  recommends Linux storage for Linux-command-line workloads.

## Phase one implementation and verification

Implemented the recommended bounded picker/pagination option with targeted query
reuse. No runtime storage move, schema migration, partial table mutation refresh,
or persistent cache was introduced.

- `/sales/item-choices` returns up to 25 normalized name/category matches after a
  250 ms input debounce. A native select preserves keyboard selection, UUID form
  submission, and completed-sale median suggestions. Invalid submissions preserve
  the chosen item and price even when outside the initial result limit. Failed or
  superseded searches cannot silently restore an old selection.
- Active and sold tables show 50 rows per independent page. Filters and sorting,
  including computed profit, apply to the whole matching set before slicing.
  Summary counts and totals remain complete, and chart totals remain unfiltered.
  Sort links reset their own page, filter submissions reset both, mutation URLs
  preserve pages, and out-of-range pages clamp after data changes. Bulk selection
  explicitly covers only the visible page.
- Completed Sales are materialized once per GET and reused by the table and chart.
  Current costs load only the latest recipe versions and requested ingredient
  prices. Picker median queries restrict history to the returned item IDs.
  Historical cost reconstruction and unknown-cost handling remain unchanged.
- Anchored the scrollable Sales table to contain absolutely positioned accessible
  labels, eliminating a small mobile document overflow found during verification.

| Local measurement | Before | After phase one |
| --- | --- | --- |
| Warm Chromium full load | About 2.00–2.06 s | 0.44–0.52 s |
| Warm TTFB | About 0.79–0.80 s | 0.34–0.39 s |
| Decoded HTML | 5,939,536 bytes | 426,786 bytes |
| Gzip HTML | 553,509 bytes | 23,148 bytes |
| Document elements | 28,665 | 3,139 |
| Longest warm main-thread task | About 0.73–0.79 s | 0.051–0.060 s |
| Default GET SQL queries | 24 | 19 |

After measurements used a temporary read-only application on port 8001 against
the canonical database; the user's port-8000 process was left alone. The catalog
remained comparable, while the user continued recording sales: the initial after
sample had 327 active and 413 sold rows. These few local samples are directional,
not percentile guarantees, and do not independently measure write latency.

A disposable backup on the same mounted filesystem was expanded to 7,660 listings
(10× its then-current history). Warm isolated server GETs took 0.79–0.83 seconds,
with approximately 0.43 MB HTML and 50 active checkboxes. The copy was removed.
This confirms bounded rendering but **not bounded server calculation cost**;
full-history projections/filtering remain the next scaling target. It is a
server-only growth check, not a 10× browser-latency measurement.

Verification: `./scripts/check.sh` passed, including 371 Python tests, 126 dbt
build/test nodes, Python/SQL lint, formatting, compilation, and public-file policy.
Focused regression coverage checks filtering/sorting before pagination, independent
pages, mutation redirects, full totals, chart independence, single history loading,
bounded picker results, validation selection, medians, and scoped valid prices.
Chromium verified desktop/mobile layout, keyboard selection, category search,
no-results handling, failed-search recovery, stale-response suppression, page-only
bulk selection, and navigation with no JavaScript errors. The final CSS containment
and cache-version changes received focused browser/template checks after the full
suite. Temporary tools, reports, and screenshots stayed outside tracked files.
