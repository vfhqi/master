"""
dedupe_watchlist.py — Remove duplicate ticker rows from pullback-watchlist.json.

Surfaced after apply_taxonomy_patch.py renamed AIR-DE -> AIR-FR but the watchlist
already had an AIR-FR row (Airbus has primary listing in Paris, secondary in
Frankfurt; both rows in watchlist were really the same company).

Strategy:
  - Find all duplicate tickers
  - For each duplicate group, prefer the row with most fields filled in
    (specifically: dashboard_ticker present, longer company_name)
  - Remove the loser, keep the winner
  - Print before/after with chosen winners highlighted

Usage:  python dedupe_watchlist.py --dry-run
        python dedupe_watchlist.py
"""
import argparse
import json
import os
from collections import defaultdict
from pathlib import Path
from datetime import date

SCRIPT_DIR = Path(__file__).resolve().parent
COWORK = SCRIPT_DIR.parent.parent
WATCHLIST = COWORK / "databases" / "pullback-watchlist.json"


def score_row(row):
    """Higher score = prefer to keep this row.
       Tie-break: dashboard_ticker present > longer company_name > more populated fields."""
    s = 0
    if row.get("dashboard_ticker"):
        s += 10
    s += len(row.get("company_name", ""))
    s += sum(1 for v in row.values() if v not in (None, "", []))
    return s


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open(WATCHLIST, encoding="utf-8") as f:
        wl = json.load(f)

    before = len(wl["stocks"])
    print(f"Loaded {before} stock rows")

    # Group by ticker
    by_ticker = defaultdict(list)
    for i, s in enumerate(wl["stocks"]):
        by_ticker[s["ticker"]].append((i, s))

    duplicates = {tk: rows for tk, rows in by_ticker.items() if len(rows) > 1}
    if not duplicates:
        print("No duplicates found.")
        return

    print(f"Found {len(duplicates)} ticker(s) with duplicate rows:")
    print()

    rows_to_drop = set()  # set of original list indices
    for tk, rows in duplicates.items():
        print(f"  {tk}:")
        scored = [(score_row(r), i, r) for i, r in rows]
        scored.sort(reverse=True)  # highest score first
        winner_score, winner_i, winner = scored[0]
        for score, i, r in scored:
            tag = "  KEEP" if i == winner_i else "  DROP"
            print(f"    {tag} (score={score:3d}) idx={i:4d} company='{r.get('company_name','')}' "
                  f"yf={r.get('yfinance_ticker','')} dash_tk={r.get('dashboard_ticker','-')}")
            if i != winner_i:
                rows_to_drop.add(i)
        print()

    new_stocks = [s for i, s in enumerate(wl["stocks"]) if i not in rows_to_drop]
    after = len(new_stocks)
    print(f"Before: {before}, After: {after}, Dropped: {len(rows_to_drop)}")

    if args.dry_run:
        print("DRY-RUN — not writing")
        return

    wl["stocks"] = new_stocks
    if "_meta" in wl:
        wl["_meta"]["updated"] = date.today().isoformat()

    tmp = WATCHLIST.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(wl, f, indent=2, ensure_ascii=False)
    with open(tmp, encoding="utf-8") as f:
        re_read = json.load(f)
    assert len(re_read["stocks"]) == after
    os.replace(tmp, WATCHLIST)
    print(f"Wrote {WATCHLIST.name}")


if __name__ == "__main__":
    main()
