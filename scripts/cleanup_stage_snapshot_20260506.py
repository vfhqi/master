"""
One-time cleanup — flag the 2026-05-06 polluted stage-snapshots entry.

Context: On 06-May-26, the morning pipeline run produced MM99 stage
classification = null universe-wide (0 Capital across 946 stocks). The
broken classification was captured in stage-snapshots.json keyed by date.
The next pipeline run self-healed filter-results.json but stage-snapshots
retains the bad day as a permanent audit-trail entry.

This script marks the 2026-05-06 entry as `_invalid: true` with a reason
note so future longitudinal queries can skip it. Does NOT delete the
underlying data — audit trail preserved.

Idempotent: if the entry is already flagged, exits cleanly without changes.
Creates a pre-write backup.

Authored: 11-May-26. See corrections.md C17, D-MD-INFRA-3.

Usage:
  python scripts/cleanup_stage_snapshot_20260506.py
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
TARGET_FILE = PROJECT_DIR / "data" / "stage-snapshots.json"
TARGET_DATE = "2026-05-06"
INVALID_REASON = "MM99 stage classification returned null universe-wide; suspected upstream cache/MA hiccup. See corrections.md C17."


def safe_json_load(path):
    """Tolerate trailing concatenated docs (per build_dashboard.py pattern)."""
    with open(path) as f:
        content = f.read()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        dec = json.JSONDecoder()
        obj, _ = dec.raw_decode(content)
        return obj


def main():
    print(f"Cleanup: flag {TARGET_DATE} entry in {TARGET_FILE}")
    if not TARGET_FILE.exists():
        print(f"  ERROR: {TARGET_FILE} not found")
        sys.exit(1)

    try:
        data = safe_json_load(TARGET_FILE)
    except Exception as e:
        print(f"  ERROR parsing JSON: {e}")
        sys.exit(1)

    if TARGET_DATE not in data:
        print(f"  WARNING: '{TARGET_DATE}' not present in stage-snapshots.json — nothing to flag.")
        sys.exit(0)

    entry = data[TARGET_DATE]
    if not isinstance(entry, dict):
        print(f"  ERROR: entry under '{TARGET_DATE}' is not a dict ({type(entry).__name__})")
        sys.exit(1)

    if entry.get("_invalid") is True:
        print(f"  '{TARGET_DATE}' already flagged as _invalid — nothing to do.")
        sys.exit(0)

    # Backup
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = TARGET_FILE.with_suffix(TARGET_FILE.suffix + f".bak-pre-cleanup-{ts}")
    shutil.copy2(TARGET_FILE, bak)
    print(f"  backup -> {bak.name}")

    # Add flags (preserves all existing ticker keys under the date)
    entry["_invalid"] = True
    entry["_reason"] = INVALID_REASON
    entry["_flagged_on"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Write
    with open(TARGET_FILE, "w") as f:
        json.dump(data, f, indent=None, separators=(",", ":"))

    print(f"  flagged '{TARGET_DATE}' with _invalid=true")
    print(f"  wrote {TARGET_FILE.stat().st_size:,} bytes")
    print("  done.")


if __name__ == "__main__":
    main()
