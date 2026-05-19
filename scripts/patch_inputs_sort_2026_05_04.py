"""
patch_inputs_sort_2026_05_04.py

Fix #1: INPUTS column sort follows valueMode toggle.
  When valueMode==='pct', the column header sort key must use the percentage
  field (pct_52wh, pct_52wl, pct_ma20, etc.) so sort matches displayed values.
  Currently the header always sorts by the underlying raw price (high_52w,
  low_52w, _ma20, etc.) regardless of display mode -- looks like "sort broken"
  to the user when in % Distance mode because the displayed % values appear
  in random order.

Fix #2: Project pct_ma20/50/150/200 onto baseRows() so the new sort keys
  have data to sort on. Currently these % values are computed inline at
  render time in commonTds() but never stored on the row.

Fix #3: Live Portfolio rows on MM99/BP/PB tabs are never passed through
  sortData(). Render loops iterate posRows directly. Add sortData call so LP
  rows respect the active currentSort the same way QS rows do.

Fix #4: buildPortfolioTile (generic LP renderer for tabs without custom
  posRows path) also doesn't sort. Add sortData call.

Pattern: anchor-string find + replace via Python f-string substitution.
Pre-write backup: build_dashboard.py.bak-pre-inputs-sort-fix-{ts}.

Idempotent: each replacement uses a unique anchor; running twice is a no-op
  on the second run (post-replacement string won't match the search anchor).
"""

import shutil
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "build_dashboard.py"
TS = datetime.now().strftime("%Y%m%d-%H%M%S")
BAK = SRC.with_suffix(f".py.bak-pre-inputs-sort-fix-{TS}")


def patch(src_text: str, find: str, replace: str, label: str) -> str:
    """Apply one replacement. Asserts find is unique and present."""
    if find not in src_text:
        # Idempotency check: maybe it's already patched
        if replace in src_text:
            print(f"  [skip] {label}: already applied")
            return src_text
        raise SystemExit(f"  [FAIL] {label}: anchor not found")
    if src_text.count(find) > 1:
        raise SystemExit(f"  [FAIL] {label}: anchor appears {src_text.count(find)} times, must be unique")
    print(f"  [ok]   {label}")
    return src_text.replace(find, replace)


def main():
    print(f"Reading: {SRC}")
    text = SRC.read_text(encoding="utf-8")
    orig_size = len(text)
    print(f"  size: {orig_size:,} bytes")

    print(f"Backup: {BAK}")
    shutil.copy2(SRC, BAK)

    # --- Fix #2: project pct_ma fields onto baseRows() ---------------------
    # Anchor: the existing _ma20/_ma50/_ma150/_ma200 projection lines.
    text = patch(
        text,
        find=(
            "      _ma20:p.mas?p.mas[\"20D\"]:null,_ma50:p.mas?p.mas[\"50D\"]:null,\n"
            "      _ma150:p.mas?p.mas[\"150D\"]:null,_ma200:p.mas?p.mas[\"200D\"]:null,\n"
            "      mas:p.mas,high_52w:p.high_52w,low_52w:p.low_52w,"
        ),
        replace=(
            "      _ma20:p.mas?p.mas[\"20D\"]:null,_ma50:p.mas?p.mas[\"50D\"]:null,\n"
            "      _ma150:p.mas?p.mas[\"150D\"]:null,_ma200:p.mas?p.mas[\"200D\"]:null,\n"
            "      // FIX-INPUTSORT 2026-05-04: project pct_ma fields so sort keys can use them in % mode.\n"
            "      pct_ma20:(p.mas&&p.mas[\"20D\"])?(p.price-p.mas[\"20D\"])/p.mas[\"20D\"]:null,\n"
            "      pct_ma50:(p.mas&&p.mas[\"50D\"])?(p.price-p.mas[\"50D\"])/p.mas[\"50D\"]:null,\n"
            "      pct_ma150:(p.mas&&p.mas[\"150D\"])?(p.price-p.mas[\"150D\"])/p.mas[\"150D\"]:null,\n"
            "      pct_ma200:(p.mas&&p.mas[\"200D\"])?(p.price-p.mas[\"200D\"])/p.mas[\"200D\"]:null,\n"
            "      mas:p.mas,high_52w:p.high_52w,low_52w:p.low_52w,"
        ),
        label="Fix #2: project pct_ma fields onto baseRows()",
    )

    # --- Fix #1a: dynamic sort keys in commonCols() (MM99/PB) --------------
    # Anchor: the entire current commonCols() inputs block.
    text = patch(
        text,
        find=(
            "    +th(\"52WH\",\"high_52w\",\"col-num col-price\",\"52-week high (toggle to %)\",\"width:52px\")\n"
            "    +th(\"52WL\",\"low_52w\",\"col-num col-price\",\"52-week low (toggle to %)\",\"width:52px\")\n"
            "    +th(\"20D\",\"_ma20\",\"col-num col-price\",\"20-day moving average\",\"width:46px\")\n"
            "    +th(\"50D\",\"_ma50\",\"col-num col-price\",\"50-day moving average\",\"width:46px\")\n"
            "    +th(\"150D\",\"_ma150\",\"col-num col-price\",\"150-day moving average\",\"width:46px\")\n"
            "    +th(\"200D\",\"_ma200\",\"col-num col-price\",\"200-day moving average\",\"width:46px\")\n"
            "    +th(\"RS\",\"rs_pct\",\"col-num col-rs\",\"Relative Strength percentile 0-100 (IBD composite)\",\"width:32px\");\n"
            "}"
        ),
        replace=(
            "    // FIX-INPUTSORT 2026-05-04: sort keys follow valueMode -- pct mode sorts by displayed % field.\n"
            "    +th(\"52WH\",valueMode===\"pct\"?\"pct_52wh\":\"high_52w\",\"col-num col-price\",\"52-week high (toggle to %)\",\"width:52px\")\n"
            "    +th(\"52WL\",valueMode===\"pct\"?\"pct_52wl\":\"low_52w\",\"col-num col-price\",\"52-week low (toggle to %)\",\"width:52px\")\n"
            "    +th(\"20D\",valueMode===\"pct\"?\"pct_ma20\":\"_ma20\",\"col-num col-price\",\"20-day moving average\",\"width:46px\")\n"
            "    +th(\"50D\",valueMode===\"pct\"?\"pct_ma50\":\"_ma50\",\"col-num col-price\",\"50-day moving average\",\"width:46px\")\n"
            "    +th(\"150D\",valueMode===\"pct\"?\"pct_ma150\":\"_ma150\",\"col-num col-price\",\"150-day moving average\",\"width:46px\")\n"
            "    +th(\"200D\",valueMode===\"pct\"?\"pct_ma200\":\"_ma200\",\"col-num col-price\",\"200-day moving average\",\"width:46px\")\n"
            "    +th(\"RS\",\"rs_pct\",\"col-num col-rs\",\"Relative Strength percentile 0-100 (IBD composite)\",\"width:32px\");\n"
            "}"
        ),
        label="Fix #1a: dynamic sort keys in commonCols()",
    )

    # --- Fix #1b: dynamic sort keys in utrCommonCols() ---------------------
    text = patch(
        text,
        find=(
            "    +th(\"52WH\",\"high_52w\",\"col-num col-price col-input\",\"52-week high\",\"width:52px\")\n"
            "    +th(\"52WL\",\"low_52w\",\"col-num col-price col-input\",\"52-week low\",\"width:52px\")\n"
            "    +th(\"20D\",\"_ma20\",\"col-num col-price col-input\",\"20-day MA\",\"width:46px\")\n"
            "    +th(\"50D\",\"_ma50\",\"col-num col-price col-input\",\"50-day MA\",\"width:46px\")\n"
            "    +th(\"150D\",\"_ma150\",\"col-num col-price col-input\",\"150-day MA\",\"width:46px\")\n"
            "    +th(\"200D\",\"_ma200\",\"col-num col-price col-input\",\"200-day MA\",\"width:46px\")\n"
            "    +th(\"RS\",\"rs_pct\",\"col-num col-rs col-input\",\"RS percentile\",\"width:32px\");\n"
            "}"
        ),
        replace=(
            "    // FIX-INPUTSORT 2026-05-04: sort keys follow valueMode in UTR common cols too.\n"
            "    +th(\"52WH\",valueMode===\"pct\"?\"pct_52wh\":\"high_52w\",\"col-num col-price col-input\",\"52-week high\",\"width:52px\")\n"
            "    +th(\"52WL\",valueMode===\"pct\"?\"pct_52wl\":\"low_52w\",\"col-num col-price col-input\",\"52-week low\",\"width:52px\")\n"
            "    +th(\"20D\",valueMode===\"pct\"?\"pct_ma20\":\"_ma20\",\"col-num col-price col-input\",\"20-day MA\",\"width:46px\")\n"
            "    +th(\"50D\",valueMode===\"pct\"?\"pct_ma50\":\"_ma50\",\"col-num col-price col-input\",\"50-day MA\",\"width:46px\")\n"
            "    +th(\"150D\",valueMode===\"pct\"?\"pct_ma150\":\"_ma150\",\"col-num col-price col-input\",\"150-day MA\",\"width:46px\")\n"
            "    +th(\"200D\",valueMode===\"pct\"?\"pct_ma200\":\"_ma200\",\"col-num col-price col-input\",\"200-day MA\",\"width:46px\")\n"
            "    +th(\"RS\",\"rs_pct\",\"col-num col-rs col-input\",\"RS percentile\",\"width:32px\");\n"
            "}"
        ),
        label="Fix #1b: dynamic sort keys in utrCommonCols()",
    )

    # --- Fix #3a: sort posRows on MM99 LP ---------------------------------
    text = patch(
        text,
        find=(
            "  // SESSION 10 — split Live Portfolio + Qualified Stocks into two separate tables, mirroring BP/PB/UTR pattern.\n"
            "  // Each table has its own <thead> (LP non-sticky via data-table-portfolio class; QS sticky), each gets its own <h3> section heading.\n"
            "  var posRows=applyIndSecFilter(filterToPositions(allRows));\n"
            "  rows=applyIndSecFilter(rows);"
        ),
        replace=(
            "  // SESSION 10 — split Live Portfolio + Qualified Stocks into two separate tables, mirroring BP/PB/UTR pattern.\n"
            "  // Each table has its own <thead> (LP non-sticky via data-table-portfolio class; QS sticky), each gets its own <h3> section heading.\n"
            "  // FIX-INPUTSORT 2026-05-04: LP rows now respect currentSort like QS rows.\n"
            "  var posRows=sortData(applyIndSecFilter(filterToPositions(allRows)),currentSort.col,currentSort.dir);\n"
            "  rows=applyIndSecFilter(rows);"
        ),
        label="Fix #3a: sort posRows on MM99 LP",
    )

    # --- Fix #3b: sort posRowsBP on BP LP ---------------------------------
    text = patch(
        text,
        find=(
            "  var posRowsBP=applyIndSecFilter(filterToPositions(allRows));\n"
            "  // Enrich position rows with BP data (they may not have been enriched if filtered out)"
        ),
        replace=(
            "  // FIX-INPUTSORT 2026-05-04: LP rows now respect currentSort like QS rows.\n"
            "  var posRowsBP=sortData(applyIndSecFilter(filterToPositions(allRows)),currentSort.col,currentSort.dir);\n"
            "  // Enrich position rows with BP data (they may not have been enriched if filtered out)"
        ),
        label="Fix #3b: sort posRowsBP on BP LP",
    )

    # --- Fix #3c: sort posRowsPB2 on PB LP --------------------------------
    text = patch(
        text,
        find=(
            "  // Apply ind/sec filter to portfolio too\n"
            "  var posRowsPB2f=[];for(var pf2=0;pf2<posRowsPB2.length;pf2++){if(passIndSecFilter(posRowsPB2[pf2]))posRowsPB2f.push(posRowsPB2[pf2])}\n"
            "  if(posRowsPB2f.length>0){"
        ),
        replace=(
            "  // Apply ind/sec filter to portfolio too\n"
            "  var posRowsPB2f=[];for(var pf2=0;pf2<posRowsPB2.length;pf2++){if(passIndSecFilter(posRowsPB2[pf2]))posRowsPB2f.push(posRowsPB2[pf2])}\n"
            "  // FIX-INPUTSORT 2026-05-04: LP rows now respect currentSort like QS rows.\n"
            "  posRowsPB2f=sortData(posRowsPB2f,currentSort.col,currentSort.dir);\n"
            "  if(posRowsPB2f.length>0){"
        ),
        label="Fix #3c: sort posRowsPB2f on PB LP",
    )

    # --- Fix #4: sort posRows in buildPortfolioTile -----------------------
    # Anchor: the existing posRows gather + length check at the start of the body.
    text = patch(
        text,
        find=(
            "  var posRows=[];\n"
            "  for(var j=0;j<allR.length;j++){if(pt[allR[j].ticker]&&passIndSecFilter(allR[j]))posRows.push(allR[j])}\n"
            "  if(posRows.length===0)return\"\";"
        ),
        replace=(
            "  var posRows=[];\n"
            "  for(var j=0;j<allR.length;j++){if(pt[allR[j].ticker]&&passIndSecFilter(allR[j]))posRows.push(allR[j])}\n"
            "  // FIX-INPUTSORT 2026-05-04: generic LP tile rows now respect currentSort like QS rows.\n"
            "  posRows=sortData(posRows,currentSort.col,currentSort.dir);\n"
            "  if(posRows.length===0)return\"\";"
        ),
        label="Fix #4: sort posRows in buildPortfolioTile",
    )

    # --- Write & verify ----------------------------------------------------
    SRC.write_text(text, encoding="utf-8")
    new_size = SRC.stat().st_size
    delta = new_size - orig_size
    print(f"\nWrote: {SRC}")
    print(f"  new size: {new_size:,} bytes (delta {delta:+,})")
    print(f"  backup at: {BAK}")

    # Sanity tail check
    tail = text[-200:]
    assert "if __name__ == \"__main__\":" in tail, "tail missing main guard -- file may be truncated"
    print("  tail check: OK")

    print("\nDone. Next: run build_dashboard.py to regenerate index.html.")


if __name__ == "__main__":
    main()
