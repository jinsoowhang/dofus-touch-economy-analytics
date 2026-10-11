# Session Notes 2026-10-05

## Screenshot sales reconciliation

- Resolved the supplied host path for `IMG_9529.png` through the available Windows
  Downloads mount. Visually transcribed 11 quantity-one equipment sale notices;
  the evidence hash was absent from previous manual reconciliation audits.
- All names uniquely matched active catalog items in the established latest-recipe
  Tailor/Shoemaker/Jeweller scope. Used oldest exact-price listings first. Royal
  Indigo Amublop required the sole screenshot-authoritative price correction,
  from 69,000 to 68,000 kamas. Five unidentified expiration notices do not identify
  listings and caused no changes.
- Applied the user-authorized batch atomically through SalesService at the
  screenshot's October 5, 19:23:44 Pacific save time, following the established
  same-day rule. Revenue is 734,000 kamas; all 11 historical recipe costs are known.
  An integrity-checked online SQLite backup preceded mutation. Evidence, exact
  listing IDs, the backup path, and verification remain in the ignored
  `data/reports/manual-screenshot-sales-2026-10-05.json`; the private commit script
  refuses replay when this report exists.
- Verified before commit and against saved SQLite: exactly 11 listing rows changed,
  exactly one price observation appended, no listings created or deleted, original
  listing start times preserved, and existing observations and unrelated tables
  unchanged. Integrity and foreign-key checks passed. Live counts are 728 sold and
  211 active listings.
- Focused verification passed: 45 Sales/capture-service tests. The full check script
  was not run for this local data operation because application code, schema,
  dependencies, and dbt models were unchanged. Screenshots, operational data, the
  private report/script, and backups remain outside tracked files.
- Home, Sales, Dashboard, and Insights each returned HTTP 200 against live SQLite.
  Private-script lint and formatting, public-file policy, and working-tree whitespace
  checks passed. Only memory and this session note are tracked-file changes.

## Recipe Calculator ingredient-order investigation

- The requested Combined Shopping List order is Craftable Item followed by each
  recipe's ingredient display order. The example sequence for Ancestral Ring is
  Scratchy Wool, Purple Warko Hairs, Podgy Tofu Leg, Tourmaline, Dragomilk, then
  Ancestral Treechnid Essence.
- Confirmed the calculator already sorts craft names ascending and then the first
  stored recipe position. Its Craftable Item header restores that initial order
  after sorting another column, and ingredient-price recalculation preserves the
  chosen table sort. Existing tests cover these behaviors.
- Read-only verification against live SQLite reproduced a different Ancestral Ring
  sequence: Ancestral Treechnid Essence, Tourmaline, Podgy Tofu Leg, Purple Warko
  Hairs, Dragomilk, Scratchy Wool. The original imported raw `ingredientIds` and
  corresponding quantities agree with those positions; this is a source/display
  mismatch rather than an alphabetical ingredient-sort defect.
- The Dofus Fashionista Touch recipe page agrees with the user's example:
  https://dofusfashionista.gg/touch/encyclopedia/item/equipment/8466-ancestral-ring/
  Other recipes demonstrate that reversing ingredient positions or sorting numeric
  ingredient IDs cannot reproduce that site's order consistently.
- Ankama's current data endpoint was unavailable: shell network resolution is
  restricted, web retrieval of its JSON/CDN endpoints failed, and the official
  encyclopedia required a browser verification challenge. No client actions or
  collection workflow was automated.
- Asked whether the intended source is the in-game recipe display or Dofus
  Fashionista. The user subsequently confirmed the in-game display. No application
  code, recipe records, or prices changed during that investigation; do not infer
  a universal ordering rule or substitute
  a name-specific exception without identifying the requested source.

## In-game recipe-order source confirmed

- The user confirmed that the in-game recipe display is authoritative. Continued
  research identified a maintained Touch-data pipeline which documents the same
  production config/API as this repository and publishes raw client tables:
  https://github.com/Trameur/DofusFashionistaVanced/blob/main/docs/touch_data_sources.md
  Its encyclopedia code reads stored recipe positions without applying an
  ingredient-name sort. This is supporting evidence, not proof of the game's
  display rule or the current authoritative ingredient-array order.
- The production API and public client bundle remain inaccessible within the
  session's restricted network. Prepared ignored, read-only diagnostic
  `data/reports/inspect-touch-recipe-order.py` for execution in a normal terminal.
  It caches the current Items/Recipes payloads and public client JavaScript under
  `data/reports/touch-recipe-order-source/`, compares Ancestral Ring with the
  user's exact sequence and local provenance, and opens operational SQLite with
  `mode=ro`. It never runs client JavaScript or writes application records.
- Private-script Ruff lint, formatting, compilation, and ignored-file checks passed.
  Asked the user to run `uv run python data/reports/inspect-touch-recipe-order.py`
  so the source/display comparison can proceed. The UI change remains incomplete
  pending that external network read. No full check script was run because no
  application code, schema, dependencies, or models changed.

## In-game ingredient order refreshed

- The user ran the diagnostic in their normal terminal. Its ignored cache contains
  the current production Items/Recipes payloads, client bundle, and an inspection
  timestamp of October 5, 20:07 Pacific. Ancestral Ring's current `ingredientIds`
  exactly match the supplied sequence. Inspection of the cached client's
  `RecipeBox.setupRecipe` confirmed that it creates each ingredient slot by
  traversing that array and pairing the corresponding `quantities` entry.
- Compared every latest local recipe against its original numeric source identity.
  Found 3,292 pure order changes and 817 recipes already in the correct order.
  No ingredient compositions, quantities, or professions changed in the matched
  sources. The 68 legacy recipes without a current numeric recipe source were
  preserved. No arbitrary sorting rule, item-specific exception, or UI-code change
  was required; the existing calculator already groups by Craftable Item and then
  source recipe position.
- Created an integrity-checked online SQLite backup and rehearsed the update on an
  isolated copy. Revalidated the complete live state against that backup under a
  write lock before applying the same atomic, append-only operation. One provenance
  batch (`dofus_touch_recipe_order_refresh`) records the authoritative raw arrays;
  it appended 3,292 recipe versions, 17,191 ordered ingredients, 3,292 source
  records, and 20,483 source-name rows. All original rows in every table remained
  byte-for-byte unchanged; prices, Sales, and unrelated tables gained no rows.
- The ignored `data/reports/touch-recipe-order-refresh-2026-10-05.json` records
  evidence hashes, the backup, trial/live verification, and old-to-new recipe IDs.
  The private refresh script refuses replay when its audit exists. Both pre-commit
  and saved-state integrity/foreign-key checks passed.
- Confirmed all 4,109 current source-backed latest recipes now match production
  order. Live calculator output and the rendered Combined Shopping List template
  show craft groups alphabetically and Ancestral Ring's six requested ingredients
  in order. Item detail uses the same new order. Compared a three-craft calculator
  result with the backup: ingredient quantities, costs, prices, statuses, weights,
  and aggregate totals are identical when keyed by craft/ingredient identity.
- Seventy-four focused recipe-sync, recipe-service, and Sales tests passed.
  Focused HTTP web tests and an initial live TestClient check hung during AnyIO
  portal startup, before any request. A bounded faulthandler diagnostic reproduced
  that environment limitation; the hanging checks were stopped. Verified the live
  services and Jinja template directly instead. The full check script was not run
  because this task only updated ignored operational data and session records.
  No application code, schema, dependencies, or dbt models changed.
- Recalculate or refresh the Recipe Calculator to load the updated ingredient
  order. No application restart is needed for this database-only refresh. Cached
  public game data, client code, reports, private scripts, backups, and the trial
  database remain ignored.
