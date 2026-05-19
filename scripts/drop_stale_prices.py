"""
drop_stale_prices.py — Surgically drop ghost ticker entries from prices.json.

Discovered during Quality Gate audit (06-May-26): CARLB-DK persisted in
prices.json as an empty stub row (price=null, industry="", sector="") because
the previous pipeline run created it as a fallback while factset-ssem.json
still referenced the old key. After apply_factset_remap.py the SSEM trigger
is gone but the stub itself remains in prices.json.

This script removes any prices.json row whose ticker is NOT in the canonical
universe (pullback-watchlist.json).

Usage:  python drop_stale_prices.py --dry-run
        python drop_stale_prices.py
"""
import argparse
import json
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
COWORK = SCRIPT_DIR.parent.parent
DATA = SCRIPT_DIR.parent / "data"

PRICES = DATA / "prices.json"
WATCHLIST = COWORK / "databases" / "pullback-watchlist.json"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    with open(WATCHLIST, encoding="utf-8") as f:
        wl = json.load(f)
    canonical_tickers = {s["ticker"] for s in wl["stocks"]}
    print(f"Canonical universe: {len(canonical_tickers)} tickers")

    with open(PRICES, encoding="utf-8") as f:
        data = json.load(f)
    before = len(data["stocks"])
    print(f"prices.json: {before} stocks")

    new_stocks = []
    dropped = []
    for s in data["stocks"]:
        if s["ticker"] in canonical_tickers:
            new_stocks.append(s)
        else:
            dropped.append({
                "ticker": s["ticker"],
                "company": s.get("company_name", ""),
                "price": s.get("price"),
                "industry": s.get("industry", ""),
                "sector": s.get("sector", ""),
            })

    after = len(new_stocks)
    print(f"Dropped: {len(dropped)}")
    for d in dropped:
        print(f"  - {d['ticker']}  company='{d['company']}'  price={d['price']}  industry='{d['industry']}'  sector='{d['sector']}'")
    print(f"Before: {before}, After: {after}")

    if args.dry_run:
        print("DRY-RUN — not writing")
        return

    data["stocks"] = new_stocks
    if "_meta" in data:
        data["_meta"]["count"] = after

    tmp = PRICES.with_suffix(".json.tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, separators=(",", ":"), ensure_ascii=False)
    with open(tmp, encoding="utf-8") as f:
        re_read = json.load(f)
    assert len(re_read["stocks"]) == after
    os.replace(tmp, PRICES)
    print(f"Wrote {PRICES.name}")
    print()
    print("Now rebuild dashboard: python build_dashboard.py")


if __name__ == "__main__":
    main()
