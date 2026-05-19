"""
audit_system_integrity.py — Cross-file ticker consistency audit.

Born of the 06-May-26 taxonomy unification project, where a single ticker
rename had to propagate across 8 separate files. Drift in any of them caused
silent or visible bugs (CARLB-DK ghost row, 23 silently orphaned SSEM stocks).

This is the SA role's standing audit tool. Run on demand, fortnightly under
the System Integrity audit, or as a soft pre-flight step in the data pipeline.

Files audited:
  1. databases/pullback-watchlist.json           — universe membership (ticker, dashboard_ticker)
  2. stock_mapping_final.json                    — canonical taxonomy (keyed by ticker)
  3. master-dashboard/data/universe.json         — dashboard universe (ticker, dashboard_ticker)
  4. master-dashboard/data/prices.json           — price data (ticker)
  5. master-dashboard/data/filter-results.json   — filter results (ticker)
  6. master-dashboard/data/factset-ssem.json     — SSEM data (key)
  7. master-dashboard/data/factset-valuation.json — valuation data (key)
  8. master-dashboard/data/stage-snapshots.json  — historical stages (date -> ticker)
  9. master-dashboard/data/ticker_mapping.json   — legacy 29-stock crosswalk
 10. positions.json                              — Richard's investments (ticker)
 11. master-dashboard/charts/*.js                — chart files (filename)

Checks:
  A. WATCHLIST is the canonical universe. Every other file's tickers must be
     a SUBSET of watchlist tickers.
  B. EVERY watchlist ticker must have a canonical mapping entry.
  C. positions.json tickers must all be in watchlist (live positions need data).
  D. No duplicate tickers within any single file.
  E. Chart files must exist for every watchlist ticker (warning, not error
     — yfinance-delisted stocks won't have charts).
  F. dashboard_ticker fields (universe.json) must all match canonical.

Output: severity-grouped report. Exit code 0 (clean), 1 (warnings only),
2 (errors found).

Usage:
  python audit_system_integrity.py                # soft mode — warnings only
  python audit_system_integrity.py --strict       # treat warnings as errors
  python audit_system_integrity.py --quiet        # suppress per-issue lines, summary only
  python audit_system_integrity.py --json         # JSON output for programmatic use
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DASHBOARD = SCRIPT_DIR.parent
COWORK = DASHBOARD.parent

WATCHLIST = COWORK / "databases" / "pullback-watchlist.json"
MAPPING = COWORK / "stock_mapping_final.json"
POSITIONS = COWORK / "positions.json"
UNIVERSE = DASHBOARD / "data" / "universe.json"
PRICES = DASHBOARD / "data" / "prices.json"
FILTERS = DASHBOARD / "data" / "filter-results.json"
SSEM = DASHBOARD / "data" / "factset-ssem.json"
VAL = DASHBOARD / "data" / "factset-valuation.json"
SNAPSHOTS = DASHBOARD / "data" / "stage-snapshots.json"
TICKER_MAPPING_LEGACY = DASHBOARD / "data" / "ticker_mapping.json"
CHARTS_DIR = DASHBOARD / "charts"


def safe_load(path):
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def get_tickers_from_list(data, key="stocks", subkey="ticker"):
    if not data or key not in data:
        return []
    items = data[key]
    if isinstance(items, dict):
        return list(items.keys())
    return [i.get(subkey) for i in items if isinstance(i, dict) and i.get(subkey)]


def find_duplicates(tickers):
    counts = Counter(tickers)
    return {tk: c for tk, c in counts.items() if c > 1}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true",
                        help="Treat warnings as errors (exit 2 on any issue)")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress per-issue detail; summary only")
    parser.add_argument("--json", action="store_true",
                        help="Emit JSON report instead of human-readable text")
    args = parser.parse_args()

    issues = {"errors": [], "warnings": [], "info": []}

    def err(msg):
        issues["errors"].append(msg)

    def warn(msg):
        issues["warnings"].append(msg)

    def info(msg):
        issues["info"].append(msg)

    # ── Load ──
    wl = safe_load(WATCHLIST)
    sm = safe_load(MAPPING)
    pos = safe_load(POSITIONS)
    universe = safe_load(UNIVERSE)
    prices = safe_load(PRICES)
    filters = safe_load(FILTERS)
    ssem = safe_load(SSEM)
    val = safe_load(VAL)
    snap = safe_load(SNAPSHOTS)
    tm_legacy = safe_load(TICKER_MAPPING_LEGACY)

    if wl is None:
        err(f"CRITICAL: watchlist not found at {WATCHLIST}")
        return _emit(issues, args)
    if sm is None:
        err(f"CRITICAL: mapping not found at {MAPPING}")
        return _emit(issues, args)

    wl_tickers = [s["ticker"] for s in wl["stocks"]]
    wl_set = set(wl_tickers)
    wl_dups = find_duplicates(wl_tickers)
    if wl_dups:
        err(f"WATCHLIST has {len(wl_dups)} duplicate ticker(s): {dict(list(wl_dups.items())[:5])}")

    sm_tickers = {tk for tk, td in sm.items()
                  if isinstance(td, dict) and td.get("new_industry")}

    # ── A. Cross-file ticker subset check ──
    info(f"Watchlist: {len(wl_tickers)} rows, {len(wl_set)} unique")
    info(f"Mapping:   {len(sm_tickers)} entries with taxonomy")

    def check_subset(name, tickers, file_label, severity="warn"):
        ts = set(tickers) if not isinstance(tickers, set) else tickers
        rogue = ts - wl_set
        if rogue:
            sample = sorted(rogue)[:10]
            msg = f"{file_label}: {len(rogue)} ticker(s) not in watchlist: {sample}"
            (warn if severity == "warn" else err)(msg)
        return rogue

    # B. Every watchlist ticker must be in mapping
    unmapped = wl_set - sm_tickers
    if unmapped:
        err(f"MAPPING: {len(unmapped)} watchlist ticker(s) have no canonical taxonomy: {sorted(unmapped)[:10]}")
    else:
        info(f"Mapping coverage: {len(wl_set)}/{len(wl_set)} (100%)")

    # C. prices.json
    if prices:
        prices_tickers = get_tickers_from_list(prices)
        prices_dups = find_duplicates(prices_tickers)
        if prices_dups:
            err(f"PRICES: {len(prices_dups)} duplicate ticker(s): {dict(list(prices_dups.items())[:5])}")
        check_subset("prices", prices_tickers, "PRICES", "error")

    # D. filter-results.json
    if filters:
        f_tickers = get_tickers_from_list(filters)
        f_dups = find_duplicates(f_tickers)
        if f_dups:
            err(f"FILTERS: {len(f_dups)} duplicate ticker(s): {dict(list(f_dups.items())[:5])}")
        check_subset("filters", f_tickers, "FILTERS", "error")

    # E. universe.json + dashboard_ticker check
    if universe:
        uni_tickers = get_tickers_from_list(universe)
        uni_dups = find_duplicates(uni_tickers)
        if uni_dups:
            err(f"UNIVERSE: {len(uni_dups)} duplicate ticker(s): {dict(list(uni_dups.items())[:5])}")
        check_subset("universe", uni_tickers, "UNIVERSE", "warn")
        # F. dashboard_ticker drift
        dt_drift = []
        for s in universe.get("stocks", []):
            dt = s.get("dashboard_ticker")
            tk = s.get("ticker")
            if dt and dt != tk and dt not in wl_set:
                dt_drift.append(f"{tk} -> dashboard_ticker={dt}")
        if dt_drift:
            warn(f"UNIVERSE.dashboard_ticker drift: {len(dt_drift)} entries point at non-watchlist tickers: {dt_drift[:5]}")

    # G. SSEM keys
    if ssem:
        ssem_keys = [k for k in ssem.keys() if k != "_meta"]
        ssem_set = set(ssem_keys)
        rogue = ssem_set - wl_set
        if rogue:
            warn(f"SSEM: {len(rogue)} key(s) not in watchlist (silent data orphans): {sorted(rogue)[:10]}")

    # H. Valuation keys
    if val:
        val_keys = [k for k in val.keys() if k != "_meta"]
        rogue = set(val_keys) - wl_set
        if rogue:
            warn(f"VALUATION: {len(rogue)} key(s) not in watchlist: {sorted(rogue)[:10]}")

    # I. positions.json (CRITICAL — affects live data)
    if pos and "investments" in pos:
        pos_tickers = [i["ticker"] for i in pos["investments"] if "ticker" in i]
        pos_dups = find_duplicates(pos_tickers)
        if pos_dups:
            err(f"POSITIONS: {len(pos_dups)} duplicate ticker(s): {pos_dups}")
        rogue = set(pos_tickers) - wl_set
        if rogue:
            err(f"POSITIONS: {len(rogue)} live investment(s) not in watchlist (live tracking broken): {sorted(rogue)}")

    # J. stage-snapshots.json
    if snap:
        snap_rogue = {}
        for date_key, day_data in snap.items():
            if not isinstance(day_data, dict):
                continue
            rogue = set(day_data.keys()) - wl_set
            if rogue:
                snap_rogue[date_key] = sorted(rogue)
        if snap_rogue:
            sample_date = list(snap_rogue.keys())[0]
            warn(f"STAGE-SNAPSHOTS: {len(snap_rogue)} date(s) contain stale tickers; sample {sample_date}: {snap_rogue[sample_date][:5]}")

    # K. legacy ticker_mapping.json (low priority — Watson loads canonical now)
    if tm_legacy and "stocks" in tm_legacy:
        tm_tickers = list(tm_legacy["stocks"].keys())
        rogue = set(tm_tickers) - wl_set
        if rogue:
            info(f"LEGACY ticker_mapping.json: {len(rogue)} stale ticker(s) — not load-bearing but worth cleaning")

    # L. chart files
    if CHARTS_DIR.exists():
        chart_files = {p.stem for p in CHARTS_DIR.glob("*.js")}
        missing_charts = wl_set - chart_files
        rogue_charts = chart_files - wl_set
        if missing_charts:
            warn(f"CHARTS: {len(missing_charts)} watchlist ticker(s) have no chart file (likely yfinance-delisted): {sorted(missing_charts)[:10]}")
        if rogue_charts:
            warn(f"CHARTS: {len(rogue_charts)} chart file(s) for non-watchlist tickers (rename leftovers): {sorted(rogue_charts)[:10]}")

    return _emit(issues, args)


def _emit(issues, args):
    if args.json:
        print(json.dumps(issues, indent=2))
    else:
        print()
        print("=" * 70)
        print("SYSTEM INTEGRITY AUDIT")
        print("=" * 70)
        for sev in ("errors", "warnings", "info"):
            items = issues[sev]
            if not items:
                continue
            if not args.quiet or sev == "errors":
                print(f"\n{sev.upper()} ({len(items)}):")
                for m in items:
                    print(f"  - {m}")
        print()
        print(f"Summary: {len(issues['errors'])} errors, {len(issues['warnings'])} warnings, {len(issues['info'])} info")
        if not issues["errors"] and not issues["warnings"]:
            print("Clean.")
        print()

    if issues["errors"]:
        return 2
    if issues["warnings"] and args.strict:
        return 2
    if issues["warnings"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
