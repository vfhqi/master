"""
BP DIAGNOSTIC ANALYSIS — Loose vs Medium vs Tight, 12-month historical lookback
================================================================================

Question Richard asked (02-May-26): does Medium/Tight Plateau add diagnostic
value beyond Loose for identifying Stage 1 bases that will launch into Stage 2?

Method:
1. Load each stock's 5Y price history from charts/{ticker}.js
2. For each of the last 12 calendar month-ends, reconstruct BP Loose/Medium/Tight
   pass status (using the same 63-day, 95% threshold logic as
   generate_master_data.py) AND MM99 Capital pass status (T1-T8 all True).
3. For each historical pass-event at level L on date D, look forward up to 6
   months to see if MM99 Capital is achieved. Tag outcomes.
4. Cross-tab pass-level vs outcome -> conversion rate, survival, forward returns.

Outcome definitions:
- LAUNCHED:   MM99 Capital achieved within 6 months (default = success)
- HOLDING:    Still in BP Loose at +6 months but no MM99 Capital
- FAILED:     Price drops 15%+ from base midpoint within 6 months OR no longer
              in BP Loose AND no MM99 Capital
- INCONCLUSIVE: Insufficient forward data (less than 6 months left)

Forward returns: 1M / 3M / 6M raw price change from snapshot date.

Run: python analyse_bp_diagnostic.py [--limit N]
"""

import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta

CHARTS_DIR = os.path.join(os.path.dirname(__file__), "..", "charts")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "PROJECTS", "SA - Master Dashboard")

# Chart row layout: [date, o, h, l, c, vol, ma5, ma10, ma20, ma50, ma100, ma150, ma200]
IDX = {"date": 0, "open": 1, "high": 2, "low": 3, "close": 4, "vol": 5,
       "ma5": 6, "ma10": 7, "ma20": 8, "ma50": 9, "ma100": 10, "ma150": 11, "ma200": 12}


def load_chart(path):
    """Parse a single charts/{ticker}.js file into a list of OHLCV+MA rows."""
    with open(path, "r", encoding="utf-8") as f:
        txt = f.read()
    m = re.search(r'CHART_REGISTRY\["([^"]+)"\]=(\[.*\]);?\s*$', txt, re.DOTALL)
    if not m:
        return None, None
    ticker = m.group(1)
    try:
        rows = json.loads(m.group(2))
    except json.JSONDecodeError:
        return ticker, None
    return ticker, rows


def within_pct(a, b, pct):
    if a is None or b is None or b == 0:
        return False
    return abs(a - b) / b <= pct


def bp_test_at_row(row, level):
    """Apply BP test (loose=0.15, medium=0.10, tight=0.05) at a single row.
    Returns True iff all the within-pct conditions for that level hold."""
    close = row[IDX["close"]]
    ma50 = row[IDX["ma50"]]
    ma150 = row[IDX["ma150"]]
    ma200 = row[IDX["ma200"]]
    if level == "loose":
        return (within_pct(close, ma200, 0.15) and within_pct(close, ma150, 0.15)
                and within_pct(ma50, ma200, 0.15) and within_pct(ma50, ma150, 0.15))
    elif level == "medium":
        return (within_pct(close, ma200, 0.10) and within_pct(close, ma150, 0.10)
                and within_pct(ma50, ma200, 0.10) and within_pct(ma50, ma150, 0.10)
                and within_pct(ma150, ma200, 0.10))
    else:  # tight
        return (within_pct(close, ma200, 0.05) and within_pct(close, ma150, 0.05)
                and within_pct(ma50, ma200, 0.05) and within_pct(ma50, ma150, 0.05)
                and within_pct(ma150, ma200, 0.05))


def bp_passes_at(rows, idx, level, lookback=63, threshold=0.95):
    """Does BP[level] pass as of row[idx]? Same 95%-of-63-days logic as pipeline."""
    if idx < lookback - 1:
        return False
    window = rows[idx - lookback + 1: idx + 1]
    passes = sum(1 for r in window if bp_test_at_row(r, level))
    return passes / lookback >= threshold


def mm99_capital_at(rows, idx):
    """Recreate MM99 8-test all-pass at row[idx]. Need >=252 rows for 52W high/low.
    Tests:
      T1 P > 150D, T2 P > 200D
      T3 150D > 200D
      T4 200D rising (vs ~22 trading days ago)
      T5 50D > 150D, T6 50D > 200D
      T7 P > 50D
      T8 P within 25% of 52W high AND >= 25% above 52W low
    """
    if idx < 252:
        return False
    r = rows[idx]
    p = r[IDX["close"]]
    ma50 = r[IDX["ma50"]]
    ma150 = r[IDX["ma150"]]
    ma200 = r[IDX["ma200"]]
    if None in (p, ma50, ma150, ma200):
        return False

    # T4 — 200D rising: compare to 200D MA ~22 trading days ago
    if idx - 22 < 0 or rows[idx - 22][IDX["ma200"]] is None:
        return False
    ma200_prev = rows[idx - 22][IDX["ma200"]]

    # T8 — 52W high / low
    window_252 = rows[idx - 251: idx + 1]
    highs = [w[IDX["high"]] for w in window_252 if w[IDX["high"]] is not None]
    lows = [w[IDX["low"]] for w in window_252 if w[IDX["low"]] is not None]
    if not highs or not lows:
        return False
    h52 = max(highs)
    l52 = min(lows)

    t1 = p > ma150
    t2 = p > ma200
    t3 = ma150 > ma200
    t4 = ma200 > ma200_prev
    t5 = ma50 > ma150
    t6 = ma50 > ma200
    t7 = p > ma50
    t8 = (p >= h52 * 0.75) and (p >= l52 * 1.25)
    return all([t1, t2, t3, t4, t5, t6, t7, t8])


def find_month_end_indices(rows, n_months=18):
    """Return list of (month_end_date_obj, idx_into_rows) for last n_months
    month-ends present in the data, oldest first."""
    if not rows:
        return []
    by_date = {}
    for i, r in enumerate(rows):
        try:
            d = datetime.strptime(r[IDX["date"]], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            continue
        # remember the LATEST trading day per (year, month)
        key = (d.year, d.month)
        by_date[key] = (d, i)
    # sort by year-month
    keys = sorted(by_date.keys())
    if len(keys) > n_months:
        keys = keys[-n_months:]
    return [by_date[k] for k in keys]


def analyse_one_stock(ticker, rows, snapshots_back=12, fwd_months=6):
    """For each of the last `snapshots_back` month-ends, evaluate BP pass
    levels and look forward `fwd_months` to determine outcome.

    Returns list of dicts, one per (snapshot_date, level_passed) event.
    """
    if not rows or len(rows) < 252 + 63:
        return []

    # We need fwd_months of forward data, so the snapshot must be at least
    # fwd_months from the END of the series. fwd_months = ~22 trading days each.
    fwd_trading_days = fwd_months * 22

    month_ends = find_month_end_indices(rows, n_months=snapshots_back + fwd_months)
    if not month_ends:
        return []

    events = []

    for snap_date, snap_idx in month_ends:
        # Need forward data
        if snap_idx + fwd_trading_days >= len(rows):
            continue

        # Evaluate each BP level at this snapshot
        levels_passed = []
        for level in ("loose", "medium", "tight"):
            if bp_passes_at(rows, snap_idx, level):
                levels_passed.append(level)

        if not levels_passed:
            continue  # not basing — not interesting for this analysis

        # Highest level passed (tight > medium > loose)
        if "tight" in levels_passed:
            highest = "tight"
        elif "medium" in levels_passed:
            highest = "medium"
        else:
            highest = "loose"

        # Forward analysis
        snap_close = rows[snap_idx][IDX["close"]]
        if snap_close is None:
            continue

        # Did MM99 Capital fire at any forward point within fwd_trading_days?
        launched_idx = None
        for fwd_i in range(snap_idx + 1, min(snap_idx + 1 + fwd_trading_days, len(rows))):
            if mm99_capital_at(rows, fwd_i):
                launched_idx = fwd_i
                break

        # Forward returns at 22 / 66 / 132 trading days (~1M / 3M / 6M)
        def fwd_ret(days):
            i = snap_idx + days
            if i >= len(rows):
                return None
            c = rows[i][IDX["close"]]
            return (c - snap_close) / snap_close if c is not None else None

        ret_1m = fwd_ret(22)
        ret_3m = fwd_ret(66)
        ret_6m = fwd_ret(132)

        # Survival: still in Loose BP at +6M?
        end_idx = snap_idx + fwd_trading_days
        still_loose = bp_passes_at(rows, end_idx, "loose")

        # Drawdown from snapshot price
        fwd_window = rows[snap_idx + 1: snap_idx + 1 + fwd_trading_days]
        fwd_lows = [r[IDX["low"]] for r in fwd_window if r[IDX["low"]] is not None]
        max_dd = (min(fwd_lows) - snap_close) / snap_close if fwd_lows else None

        # Outcome classification
        if launched_idx is not None:
            outcome = "LAUNCHED"
        elif max_dd is not None and max_dd <= -0.15:
            outcome = "FAILED"
        elif still_loose:
            outcome = "HOLDING"
        else:
            outcome = "BROKEN"  # left the base but didn't launch and didn't drop 15%

        events.append({
            "ticker": ticker,
            "date": snap_date.isoformat(),
            "highest_level": highest,
            "loose": "loose" in levels_passed,
            "medium": "medium" in levels_passed,
            "tight": "tight" in levels_passed,
            "outcome": outcome,
            "launched": launched_idx is not None,
            "ret_1m": ret_1m,
            "ret_3m": ret_3m,
            "ret_6m": ret_6m,
            "max_dd_6m": max_dd,
        })

    return events


def crosstab(events):
    """Build cross-tabulation of (highest_level passed) x (outcome)."""
    levels = ["loose", "medium", "tight"]
    outcomes = ["LAUNCHED", "HOLDING", "BROKEN", "FAILED"]
    table = {l: {o: 0 for o in outcomes} for l in levels}
    for e in events:
        table[e["highest_level"]][e["outcome"]] += 1
    return table, levels, outcomes


def percentile(vals, p):
    if not vals:
        return None
    s = sorted(vals)
    k = (len(s) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def summarise_returns(events):
    """For each highest-level bucket: forward return distribution."""
    out = {}
    for level in ("loose", "medium", "tight"):
        bucket = [e for e in events if e["highest_level"] == level]
        for horizon in ("ret_1m", "ret_3m", "ret_6m"):
            vals = [e[horizon] for e in bucket if e[horizon] is not None]
            out[(level, horizon)] = {
                "n": len(vals),
                "mean": (sum(vals) / len(vals)) if vals else None,
                "median": percentile(vals, 50),
                "p25": percentile(vals, 25),
                "p75": percentile(vals, 75),
                "pct_positive": (sum(1 for v in vals if v > 0) / len(vals)) if vals else None,
            }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="limit number of tickers (for testing)")
    ap.add_argument("--snapshots", type=int, default=12, help="month-end snapshots back")
    ap.add_argument("--fwd", type=int, default=6, help="forward months to check")
    args = ap.parse_args()

    chart_files = sorted(glob.glob(os.path.join(CHARTS_DIR, "*.js")))
    if args.limit:
        chart_files = chart_files[:args.limit]

    print(f"Analysing {len(chart_files)} chart files, {args.snapshots} snapshots back, {args.fwd}m forward...")

    all_events = []
    bad = 0
    too_short = 0
    for i, path in enumerate(chart_files):
        if i % 100 == 0:
            print(f"  {i}/{len(chart_files)} | events so far: {len(all_events)}")
        ticker, rows = load_chart(path)
        if rows is None:
            bad += 1
            continue
        if len(rows) < 252 + 63:
            too_short += 1
            continue
        events = analyse_one_stock(ticker, rows, args.snapshots, args.fwd)
        all_events.extend(events)

    print(f"\nDone. {len(all_events)} BP-pass events across universe.")
    print(f"  Parse failures: {bad} | Too short: {too_short}")

    # Cross-tab
    table, levels, outcomes = crosstab(all_events)
    print("\nCROSS-TABULATION (highest BP level passed -> 6mo outcome):")
    print(f"{'Level':<8}", *(f"{o:>10}" for o in outcomes), f"{'TOTAL':>8}", f"{'LAUNCH%':>8}", f"{'FAIL%':>8}")
    for L in levels:
        row = table[L]
        tot = sum(row.values())
        launch_pct = (row["LAUNCHED"] / tot * 100) if tot else 0
        fail_pct = (row["FAILED"] / tot * 100) if tot else 0
        print(f"{L:<8}",
              *(f"{row[o]:>10}" for o in outcomes),
              f"{tot:>8}",
              f"{launch_pct:>7.1f}%",
              f"{fail_pct:>7.1f}%")

    # Forward returns
    rets = summarise_returns(all_events)
    print("\nFORWARD RETURNS by highest level:")
    print(f"{'Level':<8} {'Horizon':<8} {'N':>6} {'Mean':>8} {'Median':>8} {'P25':>8} {'P75':>8} {'Pos%':>6}")
    for level in ("loose", "medium", "tight"):
        for horizon in ("ret_1m", "ret_3m", "ret_6m"):
            r = rets[(level, horizon)]
            if r["n"] == 0:
                print(f"{level:<8} {horizon:<8} {r['n']:>6} {'—':>8}")
                continue
            print(f"{level:<8} {horizon:<8} {r['n']:>6}",
                  f"{r['mean']*100:>7.2f}%",
                  f"{r['median']*100:>7.2f}%",
                  f"{r['p25']*100:>7.2f}%",
                  f"{r['p75']*100:>7.2f}%",
                  f"{r['pct_positive']*100:>5.1f}%")

    # Overlap analysis: of stocks passing Loose, how many ALSO pass Medium/Tight?
    loose_events = [e for e in all_events if e["loose"]]
    n_loose = len(loose_events)
    n_med = sum(1 for e in loose_events if e["medium"])
    n_tight = sum(1 for e in loose_events if e["tight"])
    print(f"\nOVERLAP — of {n_loose} Loose-pass events:")
    print(f"  Also Medium: {n_med} ({n_med/n_loose*100:.1f}%)" if n_loose else "  N/A")
    print(f"  Also Tight:  {n_tight} ({n_tight/n_loose*100:.1f}%)" if n_loose else "  N/A")

    # Save raw events + summary
    out_path = os.path.join(OUT_DIR, "bp-diagnostic-results.json")
    summary_path = os.path.join(OUT_DIR, "bp-diagnostic-summary.json")
    with open(out_path, "w") as f:
        json.dump(all_events, f, separators=(",", ":"))
    print(f"\nWrote {len(all_events)} events to {out_path}")

    summary = {
        "n_events": len(all_events),
        "n_files_analysed": len(chart_files) - bad - too_short,
        "n_parse_failures": bad,
        "n_too_short": too_short,
        "snapshots_back": args.snapshots,
        "fwd_months": args.fwd,
        "crosstab": table,
        "returns_by_level": {f"{lvl}|{h}": v for (lvl, h), v in rets.items()},
        "overlap": {
            "loose_total": n_loose,
            "loose_and_medium": n_med,
            "loose_and_tight": n_tight,
            "medium_pct_of_loose": (n_med / n_loose) if n_loose else None,
            "tight_pct_of_loose": (n_tight / n_loose) if n_loose else None,
        },
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"Wrote summary to {summary_path}")


if __name__ == "__main__":
    main()
