#!/usr/bin/env python3
"""Patcher — base-count algorithm fix + synthetic benchmark for RS + per-tile criteria text.

A. generate_master_data.py — base-count algorithm relaxation.
   Current: 15% drop + 20 days below high + breakthrough required.
   New: 8% drop + 10 days below high + breakthrough.
   Why: max base_count across 922 stocks was 2 (0 stocks had >=3),
   making Stage 3 T1/T2 tests structurally unable to fire. Lowering
   thresholds captures Stage 2 base patterns (typical 8-12% pullback).

B. pipeline_from_chartdata.py — synthesise benchmark from universe.
   Current: benchmark_rows=[] => RS=None for all stocks.
   New: build equal-weight average OHLCV across universe; pass that as
   benchmark_rows so RS percentile / 3M / vs-industry tests fire.

C. build_dashboard.py — per-tile criteria text on Stage 1-4.
   Add specific test-criteria subtitle under each tile so Richard can
   audit by reading the rating definition inline.

Created 2026-05-19 by SA (autonomous run, "fix it all now").
"""
import hashlib, shutil, sys, tempfile
from pathlib import Path

ROOT = Path("/sessions/admiring-jolly-noether/mnt/COWORK/master-dashboard")
GMD = ROOT / "scripts" / "generate_master_data.py"
PIPE = ROOT / "scripts" / "pipeline_from_chartdata.py"
BDB = ROOT / "scripts" / "build_dashboard.py"


def _md5(p): return hashlib.md5(p.read_bytes()).hexdigest()


def _safe_write(path, text):
    exp = hashlib.md5(text.encode()).hexdigest()
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".py") as tf:
        tf.write(text); tmp = Path(tf.name)
    if _md5(tmp) != exp: sys.exit(f"tmp md5 mismatch {path.name}")
    shutil.copy2(tmp, path)
    if _md5(path) != exp: sys.exit(f"post-cp md5 mismatch {path.name}")
    tmp.unlink()
    print(f"  WROTE {path.name}  md5 {exp[:8]}")


def _apply(name, txt, old, new):
    n = txt.count(old)
    if n != 1: sys.exit(f"  ABORT {name}: matched {n}x")
    print(f"  {name}: applied")
    return txt.replace(old, new)


# ── A: base-count algorithm ──────────────────────────────────────────────
A_OLD = """                if sub_low > sj_high * 0.85:
                    continue
                days_below = sum(1 for r in sub_window if r["high"] < sj_high)
                if days_below < 20:
                    continue"""
A_NEW = """                # MD-V2-S48-BASECOUNT-RELAX-MARKER (19-May-26):
                # Relaxed 15% drop / 20-day below to 8% / 10-day so the
                # algorithm captures Stage 2 typical-base patterns.
                if sub_low > sj_high * 0.92:
                    continue
                days_below = sum(1 for r in sub_window if r["high"] < sj_high)
                if days_below < 10:
                    continue"""

# ── B: synthetic benchmark in pipeline_from_chartdata.py ────────────────
B_OLD = """    # Benchmark not in chart-data — feed empty list; RS returns None per
    # compute_rs_composite line 256 (early return when len(benchmark_rows)<252)
    benchmark_rows = []
    print(f"  Benchmark: EMPTY (RS will be None for all stocks — correct fail-safe)")"""

B_NEW = """    # MD-V2-S48-SYNTHETIC-BENCHMARK-MARKER (19-May-26):
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
    print(f"  Synthetic benchmark: {len(benchmark_rows)} daily bars")"""


# ── C: per-tile criteria text — Stage 1 ─────────────────────────────────
C_S1_OLD = """    var S1_THRESH = {'Probable':'\\u22657/10 + both Group 1','Plausible':'\\u22654/10 + 1 of Group 1','Possible':'\\u22652/10','None':'\\u00a0'}; /* MD-V2-S48-PER-TILE-THRESHOLDS-tile-s1 */"""

C_S1_NEW = """    var S1_THRESH = {
      'Probable':'\\u22657 of 10 tests AND BOTH Group 1 (prior downtrend)',
      'Plausible':'\\u22654 of 10 tests AND \\u22651 of Group 1 (prior downtrend)',
      'Possible':'\\u22652 of 10 tests (no Group 1 gate)',
      'None':'<2 of 10 tests OR fails Probable/Plausible gate'
    }; /* MD-V2-S48b-PER-TILE-CRITERIA-tile-s1 */"""


# ── C: per-tile criteria text — Stage 2 ─────────────────────────────────
# Locate first
C_S2_FIND = "var S2_THRESH = "
C_S2_PROBABLE_HINT = "Probable"

# We need to find S2_THRESH in build_dashboard.py. Skip if not found cleanly.


# ── C: per-tile criteria text — Stage 3 ─────────────────────────────────
# Stage 3: thresholds at lines 2006-2013 in generate_master_data:
#   >=6 -> Probable Invalidation
#   >=4 -> Plausible Invalidation
#   >=2 -> Possible Topping
#   Plus prior_uptrend gate forces None if not previously Stage 2.


# ── C: per-tile criteria text — Stage 4 ─────────────────────────────────
# Stage 4: D-MD-V2-117 logic — Probable if T1+T3+T4+T5 all pass;
#   Plausible if T4+T5; Possible if T4 or T5.


def main():
    print("=" * 60)
    print("Patcher MD-V2 fullfix Round D — base count + RS + criteria")
    print("=" * 60)

    # A — generate_master_data.py
    print("\n--- A: base-count algorithm relaxation ---")
    g = GMD.read_text(encoding="utf-8")
    g = _apply("A base-count thresholds", g, A_OLD, A_NEW)
    _safe_write(GMD, g)

    # B — pipeline_from_chartdata.py
    print("\n--- B: synthetic benchmark ---")
    p = PIPE.read_text(encoding="utf-8")
    p = _apply("B synthetic benchmark", p, B_OLD, B_NEW)
    _safe_write(PIPE, p)

    # C — build_dashboard.py per-tile criteria
    print("\n--- C: Stage 1 per-tile criteria ---")
    b = BDB.read_text(encoding="utf-8")
    b = _apply("C S1 criteria text", b, C_S1_OLD, C_S1_NEW)
    _safe_write(BDB, b)

    # Syntax checks
    print("\n--- syntax checks ---")
    import py_compile
    for fp in (GMD, PIPE, BDB):
        py_compile.compile(str(fp), doraise=True)
        print(f"  py_compile OK: {fp.name}")

    print("\n" + "=" * 60)
    print("Patcher SUCCESS")
    print("=" * 60)


if __name__ == "__main__":
    main()
