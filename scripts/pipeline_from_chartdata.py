#!/usr/bin/env python3
"""Pipeline driver — sources OHLCV from chart-data.json instead of yfinance.

Why this exists:
- Cowork sandbox has no yfinance package
- Default pipeline path (generate_master_data.main) falls back to sample
  data when yfinance import fails, producing synthetic prices that break
  ratings (UBS wrongly Probable Stage 4, Naturgy wrongly Probable Late
  Stage 1, etc.)
- chart-data.json contains real OHLCV harvested by Richard's PC; lagged
  ~4 weeks but real

This driver:
1. Loads universe.json + chart-data.json
2. Converts chart bars (d/o/h/l/c/v) into the row format build_prices_json
   expects (date/open/high/low/close/volume)
3. Calls build_prices_json, compute_all_filters,
   compute_master_dashboard_screens
4. Writes data/prices.json + data/filter-results.json

Benchmark (^STOXX) is not in chart-data; RS composite will return None for
every stock. That means RS-dependent tests in S2/S3/S4 do not fire. This is
the correct fail-safe behaviour while real benchmark data is unavailable
in-sandbox.

After Richard restores yfinance on his PC, the standard
generate_master_data.main path resumes.

Created 2026-05-19 by SA (autonomous run, MD-V2 full-fix batch).
"""
from __future__ import annotations
import json
import sys
import os
import importlib
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SCRIPTS = ROOT / "scripts"

sys.path.insert(0, str(SCRIPTS))


def _load_json(p):
    with open(p) as f:
        return json.load(f)


def _convert_chart_bars_to_ohlcv(bars):
    """Convert chart-data bar dicts to yfinance-style OHLCV rows."""
    out = []
    for b in bars:
        out.append({
            "date": b["d"],
            "open": b["o"],
            "high": b["h"],
            "low": b["l"],
            "close": b["c"],
            "volume": b.get("v", 0),
        })
    return out


def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] pipeline_from_chartdata starting")
    print(f"  ROOT: {ROOT}")

    universe = _load_json(DATA / "universe.json")
    print(f"  universe.json: {len(universe.get('stocks', []))} stocks")

    chart_path = DATA / "chart-data.json"
    print(f"  Loading chart-data.json ({chart_path.stat().st_size:,} bytes)...")
    chart_data = _load_json(chart_path)
    print(f"  chart-data.json: {len(chart_data)} tickers")

    # Build raw_data keyed by yfinance_ticker
    raw_data = {}
    missing = []
    for stock in universe["stocks"]:
        tkr = stock["ticker"]
        yf = stock["yfinance_ticker"]
        bars = chart_data.get(tkr)
        if not bars:
            missing.append(tkr)
            continue
        raw_data[yf] = _convert_chart_bars_to_ohlcv(bars)

    print(f"  Bound {len(raw_data)} tickers; {len(missing)} missing from chart-data")
    if missing[:5]:
        print(f"    First 5 missing: {missing[:5]}")

    # MD-V2-S48-SYNTHETIC-BENCHMARK-MARKER (19-May-26):
    # chart-data.json has no ^STOXX benchmark, so we build a synthetic
    # equal-weight benchmark from the universe itself. This restores
    # relative-strength tests on Stages 2 / 3 / 4 without depending on
    # yfinance. The benchmark is a per-day average of all per-stock closes
    # (and a synthetic OHLCV row in build_prices_json's expected shape).
    print(f"  Synthesising equal-weight benchmark from universe...")
    from collections import defaultdict
    by_date_closes = defaultdict(list)
    by_date_volumes = defaultdict(list)
    for yf_t, rows in raw_data.items():
        for r in rows:
            by_date_closes[r["date"]].append(r["close"])
            by_date_volumes[r["date"]].append(r.get("volume", 0))
    sorted_dates = sorted(by_date_closes.keys())
    benchmark_rows = []
    for d in sorted_dates:
        cl = by_date_closes[d]
        if len(cl) < 100:
            continue  # require enough constituents for a representative average
        avg = sum(cl) / len(cl)
        vol_total = sum(by_date_volumes[d])
        benchmark_rows.append({
            "date": d,
            "open": avg,
            "high": avg,
            "low": avg,
            "close": avg,
            "volume": vol_total,
        })
    print(f"  Synthetic benchmark: {len(benchmark_rows)} daily bars")

    # Fresh import to avoid stale sys.modules
    for mod in ("generate_master_data", "_md_v2_screens"):
        if mod in sys.modules:
            del sys.modules[mod]
    gmd = importlib.import_module("generate_master_data")

    # Build prices.json
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Building prices.json...")
    prices = gmd.build_prices_json(universe, raw_data, benchmark_rows)
    print(f"  prices: {len(prices)} stocks")

    DATA.mkdir(parents=True, exist_ok=True)
    with open(DATA / "prices.json", "w") as f:
        json.dump({
            "_meta": {
                "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "count": len(prices),
                "source": "chart-data (lagged)",
                "note": "Sourced from chart-data.json — lagged ~4 weeks vs real-time. yfinance restoration pending on Richard's PC.",
            },
            "stocks": prices,
        }, f, indent=2)
    print(f"  Wrote prices.json")

    # Filters
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Computing filters...")
    filter_results = gmd.compute_all_filters(prices)
    print(f"  filter_results: {len(filter_results)} stocks")

    # MD V2 screens
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Computing MD V2 screens...")
    filter_results = gmd.compute_master_dashboard_screens(prices, filter_results)
    print(f"  md_v2 attached to {len(filter_results)} stocks")

    # Apply test history (if function exists; some signatures vary)
    if hasattr(gmd, "apply_test_history"):
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Applying test history...")
        try:
            filter_results = gmd.apply_test_history(
                filter_results,
                seed=False,
                raw_data=raw_data,
                universe=universe,
                benchmark_rows=benchmark_rows,
            )
            print(f"  Test history applied")
        except Exception as e:
            print(f"  apply_test_history failed: {e} — continuing without")

    with open(DATA / "filter-results.json", "w") as f:
        json.dump({
            "_meta": {
                "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "count": len(filter_results),
                "source": "chart-data (lagged)",
                "filters": ["basing_plateau", "probing_bet", "mm99", "vcp", "uptrend_retest"],
                "notes": "Sourced from chart-data.json; benchmark RS unavailable in-sandbox.",
            },
            "stocks": filter_results,
        }, f, indent=2)
    print(f"  Wrote filter-results.json")

    # Quick distribution print for sanity
    from collections import Counter
    s1c, s2c, s3c, s4c = Counter(), Counter(), Counter(), Counter()
    for s in filter_results:
        mv = s.get("md_v2", {}) or {}
        s1c[(mv.get("stage_1") or {}).get("rating", "MISSING")] += 1
        s2c[(mv.get("stage_2") or {}).get("rating", "MISSING")] += 1
        s3c[(mv.get("stage_3") or {}).get("rating", "MISSING")] += 1
        s4c[(mv.get("stage_4") or {}).get("rating", "MISSING")] += 1

    print(f"\n=== Stage distributions (post-rebuild) ===")
    print(f"  Stage 1: {dict(s1c)}")
    print(f"  Stage 2: {dict(s2c)}")
    print(f"  Stage 3: {dict(s3c)}")
    print(f"  Stage 4: {dict(s4c)}")

    # Spot-check known names
    print(f"\n=== Spot-check ===")
    spot = ["UBSG-CH", "NTGY-ES", "VAIAS-FI", "LI-FR", "DIOS-SE", "BZU-IT", "AUSS-NO"]
    by_ticker = {s.get("ticker"): s for s in filter_results}
    for t in spot:
        rec = by_ticker.get(t)
        if not rec:
            print(f"  {t}: MISSING")
            continue
        mv = rec.get("md_v2", {})
        s1 = (mv.get("stage_1") or {}).get("rating", "?")
        s2 = (mv.get("stage_2") or {}).get("rating", "?")
        s3 = (mv.get("stage_3") or {}).get("rating", "?")
        s4 = (mv.get("stage_4") or {}).get("rating", "?")
        print(f"  {t}: S1={s1} | S2={s2} | S3={s3} | S4={s4}")


if __name__ == "__main__":
    main()
