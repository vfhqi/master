"""
apply_factset_remap.py — Remap old ticker keys in FactSet data files to canonical.

Discovered during Quality Gate audit (06-May-26): the ticker rename patch
updated watchlist + mapping + universe + prices but did NOT touch the FactSet
data files. Result:
  - 23 of 24 renamed stocks have their SSEM (earnings momentum) data orphaned
    under the OLD ticker key (Carlsberg, Volvo, Ericsson, etc.).
  - 3 stocks have orphaned valuation data.
  - CARLB-DK appears as a visible empty ghost row in MM99 (only one because the
    chart-manifest still references it; the other 22 are silently orphaned).

This script:
  - Loads factset-ssem.json and factset-valuation.json
  - Remaps each old key -> new key (per WL_RENAMES from apply_taxonomy_patch.py)
  - Drops keys for the 2 dropped tickers (UNA-NL, RDSA-NL) — Unilever data lives
    under ULVR-GB, Shell under SHEL-GB
  - Atomic write with byte-verify, per silent-truncation defence

Usage:  python apply_factset_remap.py --dry-run
        python apply_factset_remap.py
"""
import argparse
import json
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent / "data"

SSEM = DATA_DIR / "factset-ssem.json"
VAL = DATA_DIR / "factset-valuation.json"

# Mirror of WL_RENAMES from apply_taxonomy_patch.py
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

# Drops — duplicates of stocks that already have an entry under the kept ticker
DROPS = {
    "UNA-NL":  "ULVR-GB",   # Unilever
    "RDSA-NL": "SHEL-GB",   # Shell
}


def remap(path, dry_run):
    print(f"\n── {path.name} ──")
    if not path.exists():
        print(f"  SKIP: {path} does not exist")
        return
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    # Keep _meta if present (don't iterate as ticker)
    meta = data.pop("_meta", None) if isinstance(data, dict) else None

    if not isinstance(data, dict):
        print(f"  ERROR: expected top-level dict, got {type(data).__name__}")
        return

    before = len(data)
    new_data = {}
    renamed_count = 0
    dropped_count = 0
    collisions = []

    # First pass: copy non-renamed/non-dropped keys as-is
    # Second pass: apply renames (after dropping the targets so renames win on collision)
    for k, v in data.items():
        if k in DROPS:
            kept = DROPS[k]
            if kept in data:
                # Drop OK — kept ticker has its own entry
                print(f"  Drop: {k} (duplicate of {kept})")
                dropped_count += 1
                continue
            else:
                # Drop target doesn't have its own entry — would lose data
                # Rename instead so data isn't lost
                print(f"  Rename (drop fallback): {k} -> {kept} (no existing entry)")
                if kept in new_data:
                    collisions.append((k, kept))
                    continue
                new_data[kept] = v
                renamed_count += 1
                continue
        if k in RENAMES:
            new_k = RENAMES[k]
            if new_k in data:
                # Both old and new exist? Prefer new entry, drop old
                print(f"  Drop (collision): {k} - {new_k} already exists in source")
                dropped_count += 1
                continue
            if new_k in new_data:
                collisions.append((k, new_k))
                continue
            new_data[new_k] = v
            print(f"  Rename: {k} -> {new_k}")
            renamed_count += 1
            continue
        # Pass-through
        if k in new_data:
            collisions.append((k, k))
            continue
        new_data[k] = v

    if meta is not None:
        # Re-attach _meta at the top
        new_data = {"_meta": meta, **new_data}

    after = len([k for k in new_data if k != "_meta"])

    print(f"  Renamed: {renamed_count}, Dropped: {dropped_count}, Collisions: {len(collisions)}")
    if collisions:
        for old, new in collisions:
            print(f"    COLLISION: {old} -> {new}")
    print(f"  Before: {before}, After: {after}")

    if dry_run:
        print("  DRY-RUN — not writing")
        return

    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(new_data, f, separators=(",", ":"), ensure_ascii=False)
    # Verify
    with open(tmp, encoding="utf-8") as f:
        re_read = json.load(f)
    re_count = len([k for k in re_read if k != "_meta"])
    assert re_count == after, f"Verify failed: wrote {after}, read back {re_count}"
    os.replace(tmp, path)
    print(f"  Wrote {path.name}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.dry_run:
        print("*** DRY RUN — no files will be modified ***")

    remap(SSEM, args.dry_run)
    remap(VAL, args.dry_run)

    if args.dry_run:
        print("\nDRY-RUN complete. Re-run without --dry-run to apply.")
    else:
        print("\nFactSet data files remapped. Now rebuild dashboard:")
        print("  python build_dashboard.py")


if __name__ == "__main__":
    main()
