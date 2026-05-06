"""
audit_taxonomy.py — Diff pullback-watchlist.json against stock_mapping_final.json.

Outputs:
  - Console summary: mapped / unmapped counts, exact-vs-normalised breakdown
  - Markdown report at:  projects/SA - Master Dashboard/taxonomy-audit-{date}.md

The normaliser tries, in order:
  1. exact ticker match
  2. ticker with .B suffix added before -COUNTRY (e.g. EKTA-SE -> EKTA.B-SE)
  3. ticker with .A suffix added
  4. cross-country alias (NKT-SE -> NKT-DK; PRY-GB -> PRY-IT; AIR-DE -> AIR-FR;
     UNA-NL -> UNA-GB; NEX-FR -> NEX-FR; CARLB-DK -> CARL.B-DK; NSIS-DK -> NSIS.B-DK)

Usage:  python audit_taxonomy.py
"""
import json
import re
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
COWORK = SCRIPT_DIR.parent.parent  # master-dashboard/scripts -> master-dashboard -> COWORK

WATCHLIST = COWORK / "databases" / "pullback-watchlist.json"
MAPPING = COWORK / "stock_mapping_final.json"
REPORT_DIR = COWORK / "projects" / "SA - Master Dashboard"
REPORT = REPORT_DIR / f"taxonomy-audit-{date.today().isoformat()}.md"

# Cross-country aliases known from state.md "Universe.json cleanup" parked work
# + sample observations from inspection of mapping vs watchlist.
# Format: watchlist_ticker -> mapping_ticker (where they're known to differ by country)
CROSS_COUNTRY_ALIASES = {
    "CARLB-DK": "CARL.B-DK",
    "NSIS-DK":  "NSIS.B-DK",
    "NKT-SE":   "NKT-DK",
    "PRY-GB":   "PRY-IT",
    "AIR-DE":   "AIR-FR",
    "UNA-NL":   "UNA-GB",
    "RDSA-NL":  "RDSA-NL",  # placeholder, may not have a mapping
    # state.md flags these as genuinely missing — keep in audit:
    # ABB-SE, ALIV-SE, DUST-SE, LUMI-SE, SWMA-SE, TOBII-SE
}

DUAL_CLASS_SUFFIXES = [".B", ".A"]


def split_ticker(t):
    """Return (base, country) from 'EKTA-SE' -> ('EKTA', 'SE'). Returns (t, None) if no country suffix."""
    m = re.match(r"^(.+)-([A-Z]{2,3})$", t)
    if m:
        return m.group(1), m.group(2)
    return t, None


def candidate_keys(ticker):
    """Yield candidate keys to try in mapping for this watchlist ticker, in priority order."""
    yield ticker  # 1. exact
    base, country = split_ticker(ticker)
    if country is None:
        return
    # 2 + 3: try .B then .A inserted before -COUNTRY
    for sfx in DUAL_CLASS_SUFFIXES:
        if base.endswith(sfx):
            continue  # already has it
        yield f"{base}{sfx}-{country}"
    # 4: cross-country alias
    if ticker in CROSS_COUNTRY_ALIASES:
        yield CROSS_COUNTRY_ALIASES[ticker]


def lookup(ticker, mapping_keys):
    """Return (matched_key, lookup_strategy) or (None, None)."""
    strategies = ["exact", ".B-suffix", ".A-suffix", "cross-country"]
    for i, key in enumerate(candidate_keys(ticker)):
        if key in mapping_keys:
            return key, strategies[i] if i < len(strategies) else "alias"
    return None, None


def main():
    print(f"Loading {WATCHLIST}")
    with open(WATCHLIST) as f:
        wl = json.load(f)
    n_rows = len(wl['stocks'])
    n_unique = len(set(s['ticker'] for s in wl['stocks']))
    print(f"  Watchlist: {n_rows} rows, {n_unique} unique tickers")
    if n_rows != n_unique:
        from collections import Counter
        dup_counts = Counter(s['ticker'] for s in wl['stocks'])
        dups = {t: c for t, c in dup_counts.items() if c > 1}
        print(f"  WARNING: {len(dups)} duplicate ticker(s): {dups}")
        print(f"  Run dedupe_watchlist.py to fix.")

    print(f"Loading {MAPPING}")
    with open(MAPPING) as f:
        sm = json.load(f)
    sm_with_taxonomy = {tk: td for tk, td in sm.items()
                        if isinstance(td, dict) and td.get("new_industry")}
    print(f"  Mapping: {len(sm)} total entries, {len(sm_with_taxonomy)} with new_industry")

    mapping_keys = set(sm_with_taxonomy.keys())
    wl_lookup = {s["ticker"]: s for s in wl["stocks"]}

    rows = []
    by_strategy = {"exact": [], ".B-suffix": [], ".A-suffix": [], "cross-country": []}
    unmapped = []

    for stock in wl["stocks"]:
        tk = stock["ticker"]
        matched, strategy = lookup(tk, mapping_keys)
        if matched:
            tax = sm_with_taxonomy[matched]
            rows.append({
                "watchlist_ticker": tk,
                "mapping_key": matched,
                "strategy": strategy,
                "industry": tax["new_industry"],
                "sector": tax["new_sector"],
                "raw_industry": stock.get("industry", ""),
                "raw_sector": stock.get("sector", ""),
            })
            by_strategy[strategy].append((tk, matched))
        else:
            unmapped.append({
                "ticker": tk,
                "company": stock.get("company_name", ""),
                "yfinance": stock.get("yfinance_ticker", ""),
                "raw_industry": stock.get("industry", ""),
                "raw_sector": stock.get("sector", ""),
            })

    # Mapping entries not used by any watchlist stock (potential drift)
    used_mapping_keys = {r["mapping_key"] for r in rows}
    orphan_mapping = sorted(set(sm_with_taxonomy.keys()) - used_mapping_keys)

    # ── Console summary ──
    print()
    print("=" * 60)
    print("RESULTS")
    print("=" * 60)
    total = len(wl["stocks"])
    mapped_n = len(rows)
    unmapped_n = len(unmapped)
    print(f"Mapped:    {mapped_n} / {total} ({100*mapped_n/total:.1f}%)")
    print(f"Unmapped:  {unmapped_n} / {total} ({100*unmapped_n/total:.1f}%)")
    print()
    print("Mapped breakdown by strategy:")
    for strat, hits in by_strategy.items():
        print(f"  {strat:18s}  {len(hits):4d}")
    print()
    print(f"Mapping orphans (in mapping, not in watchlist): {len(orphan_mapping)}")
    print()

    # ── Markdown report ──
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with open(REPORT, "w", encoding="utf-8") as f:
        f.write(f"# Taxonomy Audit — {date.today().isoformat()}\n\n")
        f.write(f"Generated by `master-dashboard/scripts/audit_taxonomy.py`.\n\n")
        f.write("## Summary\n\n")
        f.write(f"- Watchlist size: **{total}** stocks\n")
        f.write(f"- Mapping file entries with taxonomy: **{len(sm_with_taxonomy)}**\n")
        f.write(f"- **Mapped: {mapped_n} ({100*mapped_n/total:.1f}%)**\n")
        f.write(f"- **Unmapped: {unmapped_n} ({100*unmapped_n/total:.1f}%)**\n")
        f.write(f"- Mapping orphans (in mapping but not used by watchlist): {len(orphan_mapping)}\n\n")

        f.write("## Mapped breakdown by lookup strategy\n\n")
        f.write("| Strategy | Count | Implication |\n")
        f.write("|---|---:|---|\n")
        f.write(f"| Exact match | {len(by_strategy['exact'])} | No change needed |\n")
        f.write(f"| `.B` suffix added | {len(by_strategy['.B-suffix'])} | Watchlist needs renaming to `.B` form |\n")
        f.write(f"| `.A` suffix added | {len(by_strategy['.A-suffix'])} | Watchlist needs renaming to `.A` form |\n")
        f.write(f"| Cross-country alias | {len(by_strategy['cross-country'])} | Watchlist has wrong country |\n\n")

        # Detail tables
        for strat in [".B-suffix", ".A-suffix", "cross-country"]:
            hits = by_strategy[strat]
            if not hits:
                continue
            f.write(f"### Stocks needing rename — `{strat}` ({len(hits)})\n\n")
            f.write("| Old (watchlist) | New (mapping) |\n|---|---|\n")
            for old, new in sorted(hits):
                f.write(f"| `{old}` | `{new}` |\n")
            f.write("\n")

        f.write(f"## Truly unmapped stocks ({unmapped_n})\n\n")
        f.write("These stocks exist in the watchlist but have no entry in `stock_mapping_final.json` ")
        f.write("(after trying exact + .B/.A suffix + cross-country alias). They need taxonomy proposed.\n\n")
        f.write("| Ticker | Company | yfinance | Raw industry | Raw sector |\n")
        f.write("|---|---|---|---|---|\n")
        for s in unmapped:
            f.write(f"| `{s['ticker']}` | {s['company']} | `{s['yfinance']}` | {s['raw_industry']} | {s['raw_sector']} |\n")
        f.write("\n")

        if orphan_mapping:
            f.write(f"## Mapping orphans ({len(orphan_mapping)})\n\n")
            f.write("Entries in `stock_mapping_final.json` that no watchlist stock matched. ")
            f.write("Could be parked candidates, stale entries, or cases the normaliser missed.\n\n")
            f.write("<details><summary>Show all</summary>\n\n")
            for k in orphan_mapping:
                tax = sm_with_taxonomy[k]
                f.write(f"- `{k}` — {tax['new_industry']} / {tax['new_sector']}\n")
            f.write("\n</details>\n")

    print(f"Report written: {REPORT}")


if __name__ == "__main__":
    main()
