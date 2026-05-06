"""
apply_residual_remap.py — Remap residual ticker references in:
  - positions.json (Richard's investments — ticker field on each investment)
  - master-dashboard/data/universe.json (dashboard_ticker field on each stock)
  - master-dashboard/data/stage-snapshots.json (date-keyed historical stages)
  - master-dashboard/data/ticker_mapping.json (legacy 29-stock crosswalk)

Discovered during Quality Gate audit (06-May-26): even after remapping watchlist,
mapping, prices, ssem, valuation, the CARLB-DK ghost persisted. Root cause:
positions.json line 179 still has Carlsberg under ticker='CARLB-DK', and
build_dashboard.py creates stub price/filter entries for any position ticker
not found in priceMap. Other residual references found in universe.json's
dashboard_ticker field, stage-snapshots.json (historical), and the legacy
ticker_mapping.json file.

This script remaps all four. Atomic write with byte-verify per silent-truncation
defence.

Usage:  python apply_residual_remap.py --dry-run
        python apply_residual_remap.py
"""
import argparse
import json
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
COWORK = SCRIPT_DIR.parent.parent

POSITIONS = COWORK / "positions.json"
UNIVERSE = SCRIPT_DIR.parent / "data" / "universe.json"
SNAPSHOTS = SCRIPT_DIR.parent / "data" / "stage-snapshots.json"
TICKER_MAPPING = SCRIPT_DIR.parent / "data" / "ticker_mapping.json"

RENAMES = {
    "ASSA-SE":  "ASSA.B-SE",
    "BEIJ-SE":  "BEIJ.B-SE",
    "CLAS-SE":  "CLAS.B-SE",
    "EKTA-SE":  "EKTA.B-SE",
    "ELUX-SE":  "ELUX.B-SE",
    "GETI-SE":  "GETI.B-SE",
    "HEXA-SE":  "HEXA.B-SE",
    "LIFCO-SE": "LIFCO.B-SE",
    "NIBE-SE":  "NIBE.B-SE",
    "NOLA-SE":  "NOLA.B-SE",
    "NOVO-DK":  "NOVO.B-DK",
    "NSIS-DK":  "NSIS.B-DK",
    "PEAB-SE":  "PEAB.B-SE",
    "SAGA-SE":  "SAGA.B-SE",
    "SKA-SE":   "SKA.B-SE",
    "SKF-SE":   "SKF.B-SE",
    "TEL2-SE":  "TEL2.B-SE",
    "VOLV-SE":  "VOLV.B-SE",
    "ATCO-SE":  "ATCO.A-SE",
    "BT-GB":    "BT.A-GB",
    "AIR-DE":   "AIR-FR",
    "CARLB-DK": "CARL.B-DK",
    "NKT-SE":   "NKT-DK",
    "PRY-GB":   "PRY-IT",
}

DROPS = {
    "UNA-NL":  "ULVR-GB",
    "RDSA-NL": "SHEL-GB",
}

# yfinance ticker remaps for completeness
YF_RENAMES = {
    "ASSA.ST":   "ASSA-B.ST",
    "BEIJ.ST":   "BEIJ-B.ST",
    "CLAS.ST":   "CLAS-B.ST",
    "EKTA.ST":   "EKTA-B.ST",
    "ELUX.ST":   "ELUX-B.ST",
    "GETI.ST":   "GETI-B.ST",
    "HEXA.ST":   "HEXA-B.ST",
    "LIFCO.ST":  "LIFCO-B.ST",
    "NIBE.ST":   "NIBE-B.ST",
    "NOLA.ST":   "NOLA-B.ST",
    "NOVO.CO":   "NOVO-B.CO",
    "NSIS.CO":   "NSIS-B.CO",
    "PEAB.ST":   "PEAB-B.ST",
    "SAGA.ST":   "SAGA-B.ST",
    "SKA.ST":    "SKA-B.ST",
    "SKF.ST":    "SKF-B.ST",
    "TEL2.ST":   "TEL2-B.ST",
    "VOLV.ST":   "VOLV-B.ST",
    "ATCO.ST":   "ATCO-A.ST",
    "BT.L":      "BT-A.L",
    "AIR.DE":    "AIR.PA",
    "CARL.CO":   "CARL-B.CO",
    "NKT.ST":    "NKT.CO",
    "PRY.L":     "PRY.MI",
}


def atomic_write_json(path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    with open(tmp, encoding="utf-8") as f:
        json.load(f)  # verify parses
    os.replace(tmp, path)


def patch_positions(dry_run):
    print("\n── positions.json ──")
    if not POSITIONS.exists():
        print(f"  SKIP: {POSITIONS} does not exist")
        return
    with open(POSITIONS, encoding="utf-8") as f:
        data = json.load(f)
    if "investments" not in data:
        print("  SKIP: no 'investments' key")
        return
    renamed = 0
    dropped_idx = []
    for i, inv in enumerate(data["investments"]):
        tk = inv.get("ticker")
        if tk in DROPS:
            kept = DROPS[tk]
            print(f"  DROP investment[{i}]: {tk} (Unilever/Shell duplicate; canonical = {kept})")
            dropped_idx.append(i)
            continue
        if tk in RENAMES:
            new_tk = RENAMES[tk]
            old_yf = inv.get("yfinance_ticker", "")
            new_yf = YF_RENAMES.get(old_yf, old_yf)
            inv["ticker"] = new_tk
            if old_yf in YF_RENAMES:
                inv["yfinance_ticker"] = new_yf
            print(f"  RENAME investment[{i}]: {tk} -> {new_tk}  (yf {old_yf} -> {new_yf})")
            renamed += 1

    # Drop in reverse order to preserve indices
    for i in reversed(dropped_idx):
        data["investments"].pop(i)

    print(f"  Renamed: {renamed}, Dropped: {len(dropped_idx)}")
    if dry_run:
        print("  DRY-RUN — not writing")
        return
    atomic_write_json(POSITIONS, data)
    print(f"  Wrote {POSITIONS.name}")


def patch_universe_dashboard_ticker(dry_run):
    print("\n── universe.json (dashboard_ticker field) ──")
    with open(UNIVERSE, encoding="utf-8") as f:
        data = json.load(f)
    renamed = 0
    for s in data.get("stocks", []):
        dt = s.get("dashboard_ticker")
        if dt and dt in RENAMES:
            new_dt = RENAMES[dt]
            print(f"  Update {s['ticker']}: dashboard_ticker {dt} -> {new_dt}")
            s["dashboard_ticker"] = new_dt
            renamed += 1
        elif dt and dt in DROPS:
            print(f"  Update {s['ticker']}: dashboard_ticker {dt} dropped (kept = {DROPS[dt]})")
            del s["dashboard_ticker"]
            renamed += 1
    print(f"  Updated: {renamed}")
    if dry_run:
        print("  DRY-RUN — not writing")
        return
    atomic_write_json(UNIVERSE, data)
    print(f"  Wrote {UNIVERSE.name}")


def patch_stage_snapshots(dry_run):
    print("\n── stage-snapshots.json ──")
    if not SNAPSHOTS.exists():
        print(f"  SKIP: {SNAPSHOTS} does not exist")
        return
    with open(SNAPSHOTS, encoding="utf-8") as f:
        data = json.load(f)
    # Schema: {"YYYY-MM-DD": {ticker: {filter: stage}}}
    total_renames = 0
    total_drops = 0
    for date_key, day_data in data.items():
        if not isinstance(day_data, dict):
            continue
        new_day = {}
        for tk, stages in day_data.items():
            if tk in DROPS:
                kept = DROPS[tk]
                if kept in day_data:
                    total_drops += 1
                    continue
                new_day[kept] = stages
                total_renames += 1
                continue
            if tk in RENAMES:
                new_tk = RENAMES[tk]
                if new_tk in day_data:
                    total_drops += 1
                    continue
                new_day[new_tk] = stages
                total_renames += 1
                continue
            new_day[tk] = stages
        data[date_key] = new_day
    print(f"  Total renames across snapshots: {total_renames}, drops: {total_drops}")
    if dry_run:
        print("  DRY-RUN — not writing")
        return
    atomic_write_json(SNAPSHOTS, data)
    print(f"  Wrote {SNAPSHOTS.name}")


def patch_ticker_mapping(dry_run):
    print("\n── data/ticker_mapping.json (legacy 29-stock crosswalk) ──")
    if not TICKER_MAPPING.exists():
        print(f"  SKIP: {TICKER_MAPPING} does not exist")
        return
    with open(TICKER_MAPPING, encoding="utf-8") as f:
        data = json.load(f)
    if "stocks" not in data:
        print("  SKIP: no 'stocks' key")
        return
    new_stocks = {}
    renamed = 0
    dropped = 0
    for tk, td in data["stocks"].items():
        if tk in DROPS:
            print(f"  Drop: {tk} (canonical = {DROPS[tk]})")
            dropped += 1
            continue
        if tk in RENAMES:
            new_tk = RENAMES[tk]
            print(f"  Rename: {tk} -> {new_tk}")
            if "fs" in td and td["fs"] == tk:
                td["fs"] = new_tk
            new_stocks[new_tk] = td
            renamed += 1
            continue
        new_stocks[tk] = td
    data["stocks"] = new_stocks
    print(f"  Renamed: {renamed}, Dropped: {dropped}")
    if dry_run:
        print("  DRY-RUN — not writing")
        return
    atomic_write_json(TICKER_MAPPING, data)
    print(f"  Wrote {TICKER_MAPPING.name}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        print("*** DRY RUN — no files will be modified ***")

    patch_positions(args.dry_run)
    patch_universe_dashboard_ticker(args.dry_run)
    patch_stage_snapshots(args.dry_run)
    patch_ticker_mapping(args.dry_run)

    if args.dry_run:
        print("\nDRY-RUN complete. Re-run without --dry-run to apply.")
    else:
        print("\nResidual remap applied. Now rebuild dashboard:")
        print("  python build_dashboard.py")


if __name__ == "__main__":
    main()
