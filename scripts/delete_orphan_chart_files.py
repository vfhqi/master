"""
delete_orphan_chart_files.py — Remove dot-form chart files orphaned by
rename_chart_files.py (06-May-26).

Background: rename_chart_files.py renamed ASSA-SE.js -> ASSA.B-SE.js (dot form),
but the dashboard JS uses _safeTickerFile() which converts . and / to _, so it
expects ASSA_B-SE.js (underscore form). The 06-May yfinance pipeline run then
correctly produced the underscore-form files, leaving the dot-form files
orphaned (dead weight, never read by the dashboard).

This script:
  - Deletes the 22 dot-form orphan files
  - Verifies the corresponding underscore-form file exists before each delete
    (safety: don't delete the orphan if the live file is missing)
  - Prints what was deleted and what was kept

Usage:  python delete_orphan_chart_files.py --dry-run
        python delete_orphan_chart_files.py
"""
import argparse
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
CHARTS_DIR = SCRIPT_DIR.parent / "charts"

# Each entry: (orphan_dot_form, expected_underscore_form)
# Sourced from rename_chart_files.py RENAMES dict — only the ones that produced
# a "."-containing destination filename get an orphan; cross-country renames
# without a "." in the new ticker (NKT-DK, PRY-IT, AIR-FR) don't apply.
ORPHANS = [
    ("ASSA.B-SE.js",  "ASSA_B-SE.js"),
    ("BEIJ.B-SE.js",  "BEIJ_B-SE.js"),
    ("CLAS.B-SE.js",  "CLAS_B-SE.js"),
    ("EKTA.B-SE.js",  "EKTA_B-SE.js"),
    ("ELUX.B-SE.js",  "ELUX_B-SE.js"),
    ("GETI.B-SE.js",  "GETI_B-SE.js"),
    ("HEXA.B-SE.js",  "HEXA_B-SE.js"),
    ("LIFCO.B-SE.js", "LIFCO_B-SE.js"),
    ("NIBE.B-SE.js",  "NIBE_B-SE.js"),
    ("NOLA.B-SE.js",  "NOLA_B-SE.js"),
    ("NOVO.B-DK.js",  "NOVO_B-DK.js"),
    ("NSIS.B-DK.js",  "NSIS_B-DK.js"),
    ("PEAB.B-SE.js",  "PEAB_B-SE.js"),
    ("SAGA.B-SE.js",  "SAGA_B-SE.js"),
    ("SKA.B-SE.js",   "SKA_B-SE.js"),
    ("SKF.B-SE.js",   "SKF_B-SE.js"),
    ("TEL2.B-SE.js",  "TEL2_B-SE.js"),
    ("VOLV.B-SE.js",  "VOLV_B-SE.js"),
    ("ATCO.A-SE.js",  "ATCO_A-SE.js"),
    ("BT.A-GB.js",    "BT_A-GB.js"),
    ("CARL.B-DK.js",  "CARL_B-DK.js"),
    # Note: AIR-FR.js (no dot, no underscore) — single canonical, no orphan.
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    deleted = 0
    skipped_no_live = []
    skipped_missing_orphan = []
    for orphan, live in ORPHANS:
        orphan_path = CHARTS_DIR / orphan
        live_path = CHARTS_DIR / live

        if not orphan_path.exists():
            skipped_missing_orphan.append(orphan)
            continue

        if not live_path.exists():
            print(f"  SKIP: {orphan} — live file {live} does NOT exist (would lose data)")
            skipped_no_live.append(orphan)
            continue

        print(f"  Delete: {orphan}  (live = {live}, {live_path.stat().st_size} bytes)")
        if not args.dry_run:
            orphan_path.unlink()
        deleted += 1

    print()
    print(f"Deleted: {deleted}")
    print(f"Skipped (orphan didn't exist): {len(skipped_missing_orphan)}")
    print(f"Skipped (live file missing — preserved orphan): {len(skipped_no_live)}")
    if skipped_no_live:
        print("  WARNING: These orphans were preserved because the live file is missing:")
        for o in skipped_no_live:
            print(f"    - {o}")
        print("  Run generate_chart_data.py --live to regenerate live files, then re-run this script.")
    if args.dry_run:
        print("\nDRY-RUN — no files modified")


if __name__ == "__main__":
    main()
