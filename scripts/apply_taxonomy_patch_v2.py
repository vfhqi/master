"""
apply_taxonomy_patch_v2.py — One-line follow-up to v1.

Renames mapping key UNA-GB -> ULVR-GB. UNA-GB became orphan after we dropped
UNA-NL from watchlist. ULVR-GB is the kept Unilever ticker but had no mapping.
Single rename fixes both.
"""
import json
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
COWORK = SCRIPT_DIR.parent.parent
MAPPING = COWORK / "stock_mapping_final.json"

with open(MAPPING, encoding="utf-8") as f:
    sm = json.load(f)

if "ULVR-GB" in sm:
    print("ULVR-GB already exists in mapping — no rename needed")
    raise SystemExit(0)

if "UNA-GB" not in sm:
    print("ERROR: UNA-GB not found in mapping")
    raise SystemExit(1)

# Build new dict preserving order, with key swap
new_sm = {}
for k, v in sm.items():
    if k == "UNA-GB":
        new_sm["ULVR-GB"] = v
        print(f"Renamed: UNA-GB -> ULVR-GB  ({v.get('new_industry')} / {v.get('new_sector')})")
    else:
        new_sm[k] = v

# Atomic write
tmp = MAPPING.with_suffix(".json.tmp")
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(new_sm, f, indent=2, ensure_ascii=False)
with open(tmp, encoding="utf-8") as f:
    re_read = json.load(f)
assert "ULVR-GB" in re_read and "UNA-GB" not in re_read
os.replace(tmp, MAPPING)

print(f"Wrote {MAPPING.name}: {len(sm)} -> {len(new_sm)} entries (count unchanged, key renamed)")
