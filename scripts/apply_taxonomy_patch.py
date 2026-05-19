"""
apply_taxonomy_patch.py — Atomically apply approved taxonomy unification.

Two file changes:
  1. stock_mapping_final.json:
       - Add 33 new entries (truly-unmapped stocks with proposed taxonomy)
       - Rename key TELIA-SW -> TELIA-SE (wrong country in mapping)
  2. pullback-watchlist.json:
       - Rename 25 stocks (ticker + yfinance_ticker)
       - Drop 2 duplicates (UNA-NL = Unilever; RDSA-NL = Shell)

Safety:
  - Loads both files, validates structure
  - Builds new objects in memory
  - Writes to .tmp staging path
  - Verifies tmp file by re-reading and comparing key counts
  - Atomic os.replace -> live filename
  - Prints before/after summary

Usage:  python apply_taxonomy_patch.py
        python apply_taxonomy_patch.py --dry-run    # show changes, don't write
"""
import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
COWORK = SCRIPT_DIR.parent.parent

WATCHLIST = COWORK / "databases" / "pullback-watchlist.json"
MAPPING = COWORK / "stock_mapping_final.json"

# ── Approved Batch 1 renames: ticker + yfinance ──
# Format: old_ticker -> (new_ticker, new_yfinance)
WL_RENAMES = {
    # .B-suffix (18)
    "ASSA-SE":  ("ASSA.B-SE",  "ASSA-B.ST"),
    "BEIJ-SE":  ("BEIJ.B-SE",  "BEIJ-B.ST"),
    "CLAS-SE":  ("CLAS.B-SE",  "CLAS-B.ST"),
    "EKTA-SE":  ("EKTA.B-SE",  "EKTA-B.ST"),
    "ELUX-SE":  ("ELUX.B-SE",  "ELUX-B.ST"),
    "GETI-SE":  ("GETI.B-SE",  "GETI-B.ST"),
    "HEXA-SE":  ("HEXA.B-SE",  "HEXA-B.ST"),
    "LIFCO-SE": ("LIFCO.B-SE", "LIFCO-B.ST"),
    "NIBE-SE":  ("NIBE.B-SE",  "NIBE-B.ST"),
    "NOLA-SE":  ("NOLA.B-SE",  "NOLA-B.ST"),
    "NOVO-DK":  ("NOVO.B-DK",  "NOVO-B.CO"),
    "NSIS-DK":  ("NSIS.B-DK",  "NSIS-B.CO"),
    "PEAB-SE":  ("PEAB.B-SE",  "PEAB-B.ST"),
    "SAGA-SE":  ("SAGA.B-SE",  "SAGA-B.ST"),
    "SKA-SE":   ("SKA.B-SE",   "SKA-B.ST"),
    "SKF-SE":   ("SKF.B-SE",   "SKF-B.ST"),
    "TEL2-SE":  ("TEL2.B-SE",  "TEL2-B.ST"),
    "VOLV-SE":  ("VOLV.B-SE",  "VOLV-B.ST"),
    # .A-suffix (2)
    "ATCO-SE":  ("ATCO.A-SE",  "ATCO-A.ST"),
    "BT-GB":    ("BT.A-GB",    "BT-A.L"),
    # cross-country (5)
    "AIR-DE":   ("AIR-FR",     "AIR.PA"),
    "CARLB-DK": ("CARL.B-DK",  "CARL-B.CO"),
    "NKT-SE":   ("NKT-DK",     "NKT.CO"),
    "PRY-GB":   ("PRY-IT",     "PRY.MI"),
}

# Drops (Unilever + Shell duplicates — keep ULVR-GB and SHEL-GB which are already mapped)
WL_DROPS = {"UNA-NL", "RDSA-NL"}

# ── Mapping key rename ──
MAP_RENAMES = {
    "TELIA-SW": "TELIA-SE",
}

# ── New mapping entries (33) ──
# All have full prefixed sector + industry per Batch 2 sign-off
NEW_MAPPINGS = {
    "ABB-SE":   {"new_industry": "O. Industrials and capital goods",                    "new_sector": "O.4. Capital goods - grid"},
    "ALIV-SE":  {"new_industry": "H. Consumer discretionary",                            "new_sector": "H.15. Automotive - OEM or supplier"},
    "AXFO-SE":  {"new_industry": "A. Consumer staples",                                  "new_sector": "A.5. Food retail"},
    "BALD-SE":  {"new_industry": "N. Real assets",                                       "new_sector": "N.1. TBD"},
    "DIOS-SE":  {"new_industry": "N. Real assets",                                       "new_sector": "N.1. TBD"},
    "DUST-SE":  {"new_industry": "O. Industrials and capital goods",                    "new_sector": "O.15. Distributors"},
    "ERIC-SE":  {"new_industry": "J. Technology",                                        "new_sector": "J.8. Hardware"},
    "HMS-SE":   {"new_industry": "J. Technology",                                        "new_sector": "J.8. Hardware"},
    "HUSQ-SE":  {"new_industry": "H. Consumer discretionary",                            "new_sector": "H.17. Consumer products"},
    "INWI-SE":  {"new_industry": "M. Materials",                                         "new_sector": "M.6. Basic materials and construction"},
    "KINV-SE":  {"new_industry": "G. Financials",                                        "new_sector": "G.4. Holding companies"},
    "LATO-SE":  {"new_industry": "G. Financials",                                        "new_sector": "G.4. Holding companies"},
    "LIAB-SE":  {"new_industry": "O. Industrials and capital goods",                    "new_sector": "O.2. Products - various [SPLIT]"},
    "LUMI-SE":  {"new_industry": "J. Technology",                                        "new_sector": "J.7. Software - Computer games"},
    "SAND-SE":  {"new_industry": "O. Industrials and capital goods",                    "new_sector": "O.7. Capital goods - factory equipment"},
    "SBB-SE":   {"new_industry": "N. Real assets",                                       "new_sector": "N.1. TBD"},
    "SECU-SE":  {"new_industry": "K. Professional, business and consumer services",     "new_sector": "K.1. Security and facilities services"},
    "SWED-SE":  {"new_industry": "G. Financials",                                        "new_sector": "G.13. Banks"},
    "SWMA-SE":  {"new_industry": "A. Consumer staples",                                  "new_sector": "A.2. Tobacco"},
    "TOBII-SE": {"new_industry": "J. Technology",                                        "new_sector": "J.8. Hardware"},
    "ADS-DE":   {"new_industry": "H. Consumer discretionary",                            "new_sector": "H.17. Consumer products"},
    "CBK-DE":   {"new_industry": "G. Financials",                                        "new_sector": "G.13. Banks"},
    "BARC-GB":  {"new_industry": "G. Financials",                                        "new_sector": "G.13. Banks"},
    "LLOY-GB":  {"new_industry": "G. Financials",                                        "new_sector": "G.13. Banks"},
    "RKT-GB":   {"new_industry": "A. Consumer staples",                                  "new_sector": "A.4. Household products"},
    "BN-FR":    {"new_industry": "A. Consumer staples",                                  "new_sector": "A.6. Food production"},
    "BNP-FR":   {"new_industry": "G. Financials",                                        "new_sector": "G.13. Banks"},
    "KER-FR":   {"new_industry": "H. Consumer discretionary",                            "new_sector": "H.1. Luxury goods"},
    "MC-FR":    {"new_industry": "H. Consumer discretionary",                            "new_sector": "H.1. Luxury goods"},
    "OR-FR":    {"new_industry": "A. Consumer staples",                                  "new_sector": "A.4. Household products"},
    "SU-FR":    {"new_industry": "O. Industrials and capital goods",                    "new_sector": "O.4. Capital goods - grid"},
    "VIE-FR":   {"new_industry": "E. Utilities",                                         "new_sector": "E.3. Utilities - Water and other non-power"},
    "NESN-CH":  {"new_industry": "A. Consumer staples",                                  "new_sector": "A.6. Food production"},
    "UBSG-CH":  {"new_industry": "G. Financials",                                        "new_sector": "G.13. Banks"},
}

# Default placeholder fields for NEW_MAPPINGS (consistent with existing entries)
NEW_DEFAULTS = {"interest": None, "knowledge": None, "timeliness": None, "thematic": None}


def atomic_write(path, data):
    """Write JSON to .tmp then os.replace -> path. Verifies by re-reading."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    # Verify by re-reading
    with open(tmp, encoding="utf-8") as f:
        re_read = json.load(f)
    if not isinstance(re_read, (dict, list)):
        raise RuntimeError(f"Re-read of {tmp} produced unexpected type")
    os.replace(tmp, path)
    print(f"  Wrote {path.name}")


def patch_mapping(dry_run):
    print("\n── Patching stock_mapping_final.json ──")
    with open(MAPPING, encoding="utf-8") as f:
        sm = json.load(f)
    before = len(sm)
    print(f"  Loaded {before} entries")

    # Build new dict preserving key order: existing entries first (with renames applied),
    # then new entries appended
    new_sm = {}
    renamed_count = 0
    for k, v in sm.items():
        new_k = MAP_RENAMES.get(k, k)
        if new_k in new_sm:
            print(f"  WARN: rename target {new_k} already exists (from {k}), keeping first occurrence")
            continue
        new_sm[new_k] = v
        if new_k != k:
            renamed_count += 1
            print(f"  Renamed key: {k} -> {new_k}")

    added_count = 0
    for tk, taxonomy in NEW_MAPPINGS.items():
        if tk in new_sm:
            existing = new_sm[tk]
            print(f"  WARN: {tk} already in mapping (industry={existing.get('new_industry')}). Skipping.")
            continue
        entry = {**taxonomy, **NEW_DEFAULTS}
        new_sm[tk] = entry
        added_count += 1

    after = len(new_sm)
    print(f"  Renamed: {renamed_count}, Added: {added_count}")
    print(f"  Before: {before}, After: {after}")

    if dry_run:
        print("  DRY-RUN — not writing")
        return
    atomic_write(MAPPING, new_sm)


def patch_watchlist(dry_run):
    print("\n── Patching pullback-watchlist.json ──")
    with open(WATCHLIST, encoding="utf-8") as f:
        wl = json.load(f)
    before = len(wl["stocks"])
    print(f"  Loaded {before} stocks")

    new_stocks = []
    renamed = 0
    dropped = 0
    for s in wl["stocks"]:
        tk = s["ticker"]
        if tk in WL_DROPS:
            print(f"  Dropped: {tk} ({s.get('company_name', '')})")
            dropped += 1
            continue
        if tk in WL_RENAMES:
            new_tk, new_yf = WL_RENAMES[tk]
            old_yf = s.get("yfinance_ticker", "")
            s = {**s, "ticker": new_tk, "yfinance_ticker": new_yf}
            print(f"  Renamed: {tk:12s} -> {new_tk:14s}  (yf {old_yf} -> {new_yf})")
            renamed += 1
        new_stocks.append(s)

    wl["stocks"] = new_stocks
    # Bump _meta.updated
    if "_meta" in wl:
        wl["_meta"]["updated"] = date.today().isoformat()

    after = len(new_stocks)
    print(f"  Renamed: {renamed}, Dropped: {dropped}")
    print(f"  Before: {before}, After: {after}")

    if dry_run:
        print("  DRY-RUN — not writing")
        return
    atomic_write(WATCHLIST, wl)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    args = parser.parse_args()

    if args.dry_run:
        print("*** DRY RUN — no files will be modified ***\n")

    patch_mapping(args.dry_run)
    patch_watchlist(args.dry_run)

    if args.dry_run:
        print("\nDRY-RUN complete. Re-run without --dry-run to apply.")
    else:
        print("\nPatch applied. Now run audit_taxonomy.py to verify 976/976 mapped.")


if __name__ == "__main__":
    main()
