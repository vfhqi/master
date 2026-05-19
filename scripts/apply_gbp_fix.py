#!/usr/bin/env python3
"""
apply_gbp_fix.py — GBp → GBP conversion patch for generate_master_data.py
===========================================================================
Watson-authored patch, 2026-05-19.

PROBLEM:
  yfinance returns London Stock Exchange (.L) stock prices in pence (GBp),
  not pounds (GBP). generate_master_data.py has no currency conversion, so
  UK stocks display prices ~100x too high (e.g. Ashtead shows ~4,700 instead
  of ~£47). Affects all 189 stocks with yfinance_ticker ending in ".L".

FIX:
  In build_prices_json(), before compute_smas() is called, divide OHLC by 100
  for any .L ticker. SMAs, 52W high/low, and all downstream fields are then
  computed in pounds. The yfinance cache files are left untouched (they stay
  in pence as yfinance returns them).

RUN THIS SCRIPT on Windows:
  cd C:\\Users\\richb\\Documents\\COWORK\\master-dashboard\\scripts
  python apply_gbp_fix.py

Then regenerate master-data.js:
  python generate_master_data.py
"""

import os
import shutil
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(SCRIPT_DIR, "generate_master_data.py")
BAK    = TARGET + f".bak-pre-gbp-fix-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

# ── The exact target string (8-space indent — inside build_prices_json) ──────
OLD = '        rows_with_sma = compute_smas(raw_data[yf])\n'

NEW = (
    '        # GBp → GBP: London Stock Exchange (.L) tickers report in pence;\n'
    '        # divide OHLC by 100 to get pounds before computing SMAs and all downstream stats.\n'
    '        raw_rows = raw_data[yf]\n'
    '        if yf.endswith(".L"):\n'
    '            raw_rows = [\n'
    '                {**r,\n'
    '                 "open":  round(r["open"]  / 100, 4),\n'
    '                 "high":  round(r["high"]  / 100, 4),\n'
    '                 "low":   round(r["low"]   / 100, 4),\n'
    '                 "close": round(r["close"] / 100, 4)}\n'
    '                for r in raw_rows\n'
    '            ]\n'
    '        rows_with_sma = compute_smas(raw_rows)\n'
)

def main():
    if not os.path.exists(TARGET):
        print(f"ERROR: Target file not found: {TARGET}")
        return 1

    print(f"Reading: {TARGET}")
    with open(TARGET, 'r', encoding='utf-8') as f:
        content = f.read()

    count = content.count(OLD)
    if count == 0:
        # Check if patch was already applied
        if 'raw_rows = raw_data[yf]' in content and 'endswith(".L")' in content:
            print("SKIPPED: Patch already applied.")
            return 0
        print(f"ERROR: Target string not found in {TARGET}")
        print("Expected to find (indented with 8 spaces):")
        print(f"  {repr(OLD)}")
        return 1
    if count > 1:
        print(f"ERROR: Target string found {count} times — ambiguous, not patching.")
        return 1

    print(f"Creating backup: {BAK}")
    shutil.copy2(TARGET, BAK)

    patched = content.replace(OLD, NEW, 1)

    # Verify
    assert 'raw_rows = raw_data[yf]' in patched
    assert 'if yf.endswith(".L"):' in patched
    assert OLD not in patched, "Old string still present after patch"

    print(f"Writing patched file...")
    with open(TARGET, 'w', encoding='utf-8') as f:
        f.write(patched)

    orig_bytes = os.path.getsize(BAK)
    new_bytes  = os.path.getsize(TARGET)
    print(f"  Original: {orig_bytes:,} bytes")
    print(f"  Patched:  {new_bytes:,} bytes  (delta: +{new_bytes - orig_bytes:,} bytes)")
    print()
    print("SUCCESS. GBp → GBP fix applied.")
    print()
    print("NEXT STEPS:")
    print("  1. Run:  python generate_master_data.py")
    print("     (uses existing yfinance cache — no network needed)")
    print("  2. Verify AHT-GB price is ~£47, not ~4,700")
    print("  3. Push master-data.js to GitHub")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
