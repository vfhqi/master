# Build spec — Overview page: transpose summary table + co-occurrence click

**Session 35 (15-May-26). SA / EXECUTION. SA - Master Dashboard.**
Covers Richard's Request 2 (transpose the Overview summary table to line up with
the matrix below) and Request 3 (co-occurrence "patterns" click behaviour). Request 1
(post-test indicator ratingPath fix) is a separate, already-validated patcher.

---

## Request 2 — transpose the summary table, align it to the matrix

### Current state
`#mo-main-table` (the "distribution table" at the top of the Master Overview tab):
- thead: one row — `Screen` | `None` | `Possible` | `Plausible` | `Probable` | `Total rated`.
- tbody: a section-banner row (colspan) whenever the section changes, then one data
  row per screen (20 screens) — screen label + four tier counts + total rated.
- Column widths: screen-col 320px, tier-col 110px x4, total-col 110px; table `width:100%`.

`#mo-matrix-table` (the 946-row matrix below): col 1 = `Stock` 190px (sticky-left),
then 20 screen columns x 64px each. The page `body` is the horizontal scroller on the
`master_overview` tab (Wave 3c) — `.v2-hscroll` / `.table-wrap` are inert.

### Target state
Transpose `#mo-main-table` so the five tiers run down as rows and the 20 screens run
across as columns, in the **same order and the same widths** as the matrix below, so
the two tables read as one aligned block.

- thead: **two rows**, mirroring the matrix:
  1. section-group band — corner cell + one `<th colspan=N>` per section
     (Stages 4, Pre-test 3, Post-test 5, Qualification setups 4, Deployment tests 4),
     reusing the matrix's `mo-mx-g-*` colour treatment.
  2. column-title row — corner cell (label: "Rated tier") + 20 screen-label `<th>`s.
- tbody: **five rows** — None, Possible, Plausible, Probable, Total rated. First cell =
  tier label (190px, sticky-left to match the matrix Stock column). Then 20 count cells.
- Column widths: `table-layout: fixed` + `<colgroup>` = 190px + 20x64px = 1470px,
  identical to the matrix. Both tables sit at the same left origin, so the page-body
  horizontal scroll moves them together — they line up with no shared-container
  restructure and no JS scroll-sync needed.
- thead is **`position: static`** (NOT sticky). The summary table scrolls away with the
  page. A pinned-band version is a deliberately deferred follow-up (told to Richard) —
  the dashboard's sticky-header stack is its most fragile area and is out of scope here.
- The `Total rated` row = column sum of the Possible+Plausible+Probable cells in that
  column (so it tracks the active filter automatically — see Request 3).

---

## Request 3 — co-occurrence "patterns" click behaviour

### Behaviour
- Clicking a count cell in the summary table (a screen x tier combination) **selects**
  it (toggle; visibly highlighted). Multiple cells can be selected.
- While any cell is selected, **every cell** recomputes its number to: count of stocks
  that pass the full selection filter **AND** have that cell's own screen = that cell's
  own tier. (Selected cells use the same formula — their own criterion is already in the
  filter, so they show the filtered count restricted to their screen/tier.)
- With nothing selected, every cell shows its plain count (today's behaviour).
- The **matrix below filters** to the stocks that pass the full selection filter.

### Selection semantics (confirmed with Richard)
- Multiple tiers selected **within one screen** → OR.
- Selections **across different screens** → AND.
- This is the same model the matrix's per-column filter chips used — so the chips are
  now redundant and are **removed** (confirmed with Richard). The summary-table selection
  becomes the single, shared filter state driving both tables. No two-views-disagree risk.

### Selection state
`moSel = { rowKey: { tier: true, ... }, ... }` — only present keys are active; a screen
with no entry is unconstrained. (This is the same shape as the old `moMxFilters`, which
it replaces.) A stock passes when, for every screen that has ≥1 selected tier, the
stock's normalised tier for that screen is one of the selected tiers.

### Judgement calls (made by Watson, within the escalation threshold — flagged here)
- **None is selectable.** All four tier rows' cells (None / Possible / Plausible /
  Probable) are valid co-occurrence criteria — "Probable on Basing AND None on Breakout"
  is a legitimate audit query. The `Total rated` row is a derived total, not a criterion —
  its cells are **not** selectable.
- **Jump-to-tab moves to the screen label.** The cell click is now the co-occurrence
  selector, so "jump to that screen's tab" moves onto a click of the screen-name column
  header — in **both** the summary table's column-title row and the matrix's column-title
  row (consistent: click a screen name anywhere on the Overview page → go to that tab).
- **A "Clear" affordance** is added next to the Scope control so a multi-cell selection
  can be reset in one click. The `_mdJump` handoff payload is unchanged.

---

## Transform plan (one patcher, `MD-V2-OVERVIEW-COOCCURRENCE-S35-MARKER`)

Target: `scripts/build_dashboard.py`. House style: read source via `git show HEAD:`,
idempotent on the marker, working-tree-vs-HEAD safety gate, exact anchor-count asserts,
py_compile before write, pre-write `.bak-pre-overview-cooccurrence-s35-<ts>` backup.
Run Windows-side (FUSE mount stale in the sandbox).

Edits:
1. **CSS** — replace the `#mo-main-table` rule block (between
   `MD-V2-MASTER-OVERVIEW-MARKER-CSS-START` and `-CSS-END`) with the transposed-table
   rules: `table-layout:fixed`, the `<colgroup>` widths, the two-row thead styling
   (reusing `mo-mx-g-*` group colours), sticky-left first column, the `.mo-cell`
   selected-state highlight, screen-label hover/cursor for the jump.
2. **CSS** — drop the `.mo-mx-chip*` rules and the `mo-mx-chip-row` sticky rule; adjust
   the matrix `mo-mx-group-row` / `mo-mx-col-row` `top:` offsets down by the removed
   chip-row height (group row → base; col row → base + group-row height).
3. **JS — `moRenderTable`** — rewrite to emit the transposed two-row thead + five-row
   tbody; compute each cell via the co-occurrence formula; paint selected cells.
4. **JS — selection state + handlers** — add `moSel`, `moSelRowPasses(md)`,
   `moSelToggle(rowKey,tier)`, `moClearSel()`; `moCellClick` becomes the selector
   (re-renders summary + matrix); add `moJumpToTab(rowKey)` for the screen-label click.
5. **JS — matrix** — `moMxBuildHead` drops the chip row (2 rows, not 3); `moMxRowPasses`
   → reads `moSel` (delete `moMxFilters` / `moMxToggleChip` / `moMxPaintChips`); wire the
   matrix col-row labels to `moJumpToTab`.
6. **JS — controls** — add the "Clear" button to the Scope control row.

## Validation plan
- `py_compile` the patcher and the patched `build_dashboard.py`.
- Extract the embedded JS by concatenating the 4 `r"""` pieces of the `js` string
  (joined across the `tab_ids_js` / `tab_labels_js` / `tab_accents_js` interludes) and
  `node --check` it — never a naive non-greedy regex (S34 Hot Wash lesson).
- Sandbox sanity: a headless JS harness over `filter-results.json` that reproduces
  `moSelRowPasses` + the cell formula and checks a worked example (e.g.
  Probable Stage 1 x Basing) by hand against the data.
- Chrome-MCP per SA Pre-Ship Discipline §2 once shipped: transposed table aligns column-
  for-column with the matrix; click → counts recompute + matrix filters; multi-select
  AND/OR; clear; screen-label jump; chips gone; console clean.
