"""
Master Dashboard — Unified Data Pipeline
=========================================
Reads universe.json, fetches OHLCV via yfinance (or generates sample data),
computes 7 SMAs, RS composite, and runs all 5 screening filters.

Outputs:
  data/prices.json         — per-stock price, MAs, volume, 52W stats
  data/filter-results.json — per-stock pass/fail for all 5 filters
  data/rs-data.json        — RS composite + percentile ranks

Usage:
  python generate_master_data.py                 # yfinance with cache
  python generate_master_data.py --sample        # sample data (no network)
  python generate_master_data.py --full-refresh  # force re-pull
"""

import json
import sys
import os
import math
from pathlib import Path
from datetime import datetime, timedelta, date
from collections import defaultdict
import argparse

# ── Paths ─────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
CACHE_DIR = PROJECT_DIR / "cache"
UNIVERSE_PATH = DATA_DIR / "universe.json"

# Reuse existing pullback-monitor cache if available
LEGACY_CACHE_DIR = SCRIPT_DIR.parent.parent / "databases" / "pullback-cache"

LOOKBACK_DAYS = 1650  # ~5.5 years for 200D MA warmup + chart display
SMA_PERIODS = [5, 10, 20, 50, 100, 150, 200]
BENCHMARK_TICKER = "^STOXX"

# ── Cache System (reused from pullback monitor) ──────────────────────────

def _cache_path(yf_ticker, cache_dir=None):
    """Return the cache file path for a yfinance ticker."""
    cd = cache_dir or CACHE_DIR
    safe = yf_ticker.replace("^", "_caret_").replace(".", "_dot_").replace("/", "_slash_")
    return cd / f"{safe}.json"


def load_cache(yf_ticker):
    """Load cached OHLCV rows. Checks project cache first, then legacy."""
    for cd in [CACHE_DIR, LEGACY_CACHE_DIR]:
        path = _cache_path(yf_ticker, cd)
        if path.exists():
            try:
                with open(path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                continue
    return None


def save_cache(yf_ticker, rows):
    """Save OHLCV rows to project cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(yf_ticker)
    with open(path, "w") as f:
        json.dump(rows, f, separators=(",", ":"))


def _merge_cached_and_new(cached_rows, new_rows):
    by_date = {}
    for r in (cached_rows or []):
        by_date[r["date"]] = r
    for r in (new_rows or []):
        by_date[r["date"]] = r
    return sorted(by_date.values(), key=lambda r: r["date"])


# ── yfinance Fetch ────────────────────────────────────────────────────────

def _fetch_ticker(yf, ticker, start_date, end_date):
    """Fetch OHLCV for a single ticker from yfinance."""
    try:
        t = yf.Ticker(ticker)
        hist = t.history(start=start_date.strftime("%Y-%m-%d"),
                        end=end_date.strftime("%Y-%m-%d"))
        if len(hist) > 0:
            rows = []
            for idx, row in hist.iterrows():
                rows.append({
                    "date": idx.strftime("%Y-%m-%d"),
                    "open": round(float(row["Open"]), 4),
                    "high": round(float(row["High"]), 4),
                    "low": round(float(row["Low"]), 4),
                    "close": round(float(row["Close"]), 4),
                    "volume": int(row["Volume"]),
                })
            return rows
        return []
    except Exception as e:
        print(f"  ERR  {ticker:12s} — {e}")
        return []


def fetch_all_data(universe, full_refresh=False):
    """Fetch OHLCV for all universe stocks + benchmark."""
    import yfinance as yf

    end_date = datetime.now()
    full_start = end_date - timedelta(days=LOOKBACK_DAYS + 250)
    OVERLAP = 5

    tickers = [(s["yfinance_ticker"], s["ticker"]) for s in universe["stocks"]]
    tickers.append((BENCHMARK_TICKER, "BENCHMARK"))

    data = {}
    stats = {"full": 0, "incr": 0, "cache": 0, "err": 0}

    for yf_ticker, label in tickers:
        cached = None if full_refresh else load_cache(yf_ticker)

        if cached and not full_refresh:
            last_date = datetime.strptime(cached[-1]["date"], "%Y-%m-%d")
            days_stale = (end_date - last_date).days
            if days_stale <= 1:
                data[yf_ticker] = cached
                stats["cache"] += 1
                print(f"  CACHE {yf_ticker:12s} — {len(cached)} days")
                continue

            new_rows = _fetch_ticker(yf, yf_ticker, last_date - timedelta(days=OVERLAP), end_date)
            if new_rows:
                merged = _merge_cached_and_new(cached, new_rows)
                cutoff = (end_date - timedelta(days=LOOKBACK_DAYS + 250)).strftime("%Y-%m-%d")
                merged = [r for r in merged if r["date"] >= cutoff]
                save_cache(yf_ticker, merged)
                data[yf_ticker] = merged
                stats["incr"] += 1
                print(f"  INCR  {yf_ticker:12s} — {len(new_rows)} new, {len(merged)} total")
            else:
                data[yf_ticker] = cached
                stats["cache"] += 1
                print(f"  STALE {yf_ticker:12s} — using {len(cached)}-day cache")
        else:
            new_rows = _fetch_ticker(yf, yf_ticker, full_start, end_date)
            if new_rows:
                save_cache(yf_ticker, new_rows)
                data[yf_ticker] = new_rows
                stats["full"] += 1
                print(f"  FULL  {yf_ticker:12s} — {len(new_rows)} days")
            else:
                stats["err"] += 1
                print(f"  FAIL  {yf_ticker:12s}")

    print(f"\n  Summary: {stats['full']} full, {stats['incr']} incr, {stats['cache']} cached, {stats['err']} errors\n")
    return data


# ── Sample Data Generator ─────────────────────────────────────────────────

def generate_sample_data(universe):
    """Generate realistic sample OHLCV for testing without network."""
    import random
    random.seed(42)

    data = {}
    end = datetime.now()

    tickers = [(s["yfinance_ticker"], s["ticker"]) for s in universe["stocks"]]
    tickers.append((BENCHMARK_TICKER, "BENCHMARK"))

    for yf_ticker, label in tickers:
        rows = []
        price = random.uniform(15, 500)
        base_vol = random.randint(100000, 5000000)

        # Generate ~500 trading days (enough for 200D MA + history)
        trading_days = 500
        current = end - timedelta(days=int(trading_days * 1.45))

        # Alternate advance/pullback phases for realistic patterns
        phases = [
            (80, 0.002), (40, -0.001), (60, 0.0015), (30, -0.0008),
            (50, 0.002), (25, -0.001), (40, 0.0018), (20, -0.0012),
            (60, 0.001), (30, -0.0005), (65, 0.0012)
        ]
        phase_idx = 0
        phase_day = 0

        for _ in range(trading_days):
            while current.weekday() >= 5:
                current += timedelta(days=1)

            if phase_idx < len(phases):
                drift = phases[phase_idx][1]
                if phase_day >= phases[phase_idx][0]:
                    phase_idx += 1
                    phase_day = 0
            else:
                drift = 0.001

            daily_ret = drift + random.gauss(0, 0.015)
            price *= (1 + daily_ret)
            price = max(price, 0.5)

            intraday_range = price * random.uniform(0.008, 0.025)
            high = price + random.uniform(0, intraday_range * 0.6)
            low = price - random.uniform(0, intraday_range * 0.6)
            open_price = low + random.uniform(0.2, 0.8) * (high - low)
            vol = int(base_vol * random.uniform(0.5, 2.0))

            rows.append({
                "date": current.strftime("%Y-%m-%d"),
                "open": round(open_price, 4),
                "high": round(high, 4),
                "low": round(low, 4),
                "close": round(price, 4),
                "volume": vol,
            })

            current += timedelta(days=1)
            phase_day += 1

        data[yf_ticker] = rows
        print(f"  SAMPLE {yf_ticker:12s} — {len(rows)} days, last close: {price:.2f}")

    return data


# ── SMA Computation ───────────────────────────────────────────────────────

def compute_smas(ohlcv_rows, periods=SMA_PERIODS):
    """Compute SMAs for all specified periods. Returns list of dicts with SMA fields added."""
    closes = [r["close"] for r in ohlcv_rows]
    n = len(closes)

    result = []
    for i in range(n):
        row = dict(ohlcv_rows[i])
        for p in periods:
            key = f"sma_{p}"
            if i >= p - 1:
                row[key] = round(sum(closes[i - p + 1:i + 1]) / p, 4)
            else:
                row[key] = None
        result.append(row)
    return result


# ── RS Composite (IBD-style) ──────────────────────────────────────────────

def compute_rs_composite(stock_rows, benchmark_rows):
    """Compute IBD-style RS composite: 0.4*3M + 0.2*6M + 0.2*9M + 0.2*12M.
    Returns the composite value and component returns."""
    if len(stock_rows) < 252 or len(benchmark_rows) < 252:
        return None, {}

    def _period_return(rows, days):
        if len(rows) < days:
            return None
        start_price = rows[-days]["close"]
        end_price = rows[-1]["close"]
        if start_price <= 0:
            return None
        ret = (end_price - start_price) / start_price
        return max(min(ret, 2.0), -2.0)  # Cap at +/-200%

    stock_returns = {}
    bench_returns = {}
    for label, days in [("3M", 63), ("6M", 126), ("9M", 189), ("12M", 252)]:
        stock_returns[label] = _period_return(stock_rows, days)
        bench_returns[label] = _period_return(benchmark_rows, days)

    if any(v is None for v in stock_returns.values()):
        return None, stock_returns

    # Use RELATIVE returns (stock - benchmark) per Q6 decision (23-Apr-26)
    rel_returns = {}
    for label in ["3M", "6M", "9M", "12M"]:
        sr = stock_returns[label]
        br = bench_returns.get(label)
        if sr is not None and br is not None:
            rel_returns[label] = sr - br
        else:
            rel_returns[label] = sr  # Fallback to absolute if no benchmark

    composite = (0.4 * rel_returns["3M"] +
                 0.2 * rel_returns["6M"] +
                 0.2 * rel_returns["9M"] +
                 0.2 * rel_returns["12M"])

    return round(composite, 6), stock_returns


def compute_rs_percentiles(rs_values):
    """Given dict of {ticker: rs_composite}, compute 0-99 percentile ranks."""
    valid = {k: v for k, v in rs_values.items() if v is not None}
    if not valid:
        return {}
    sorted_items = sorted(valid.items(), key=lambda x: x[1])
    n = len(sorted_items)
    percentiles = {}
    for rank, (ticker, val) in enumerate(sorted_items):
        percentiles[ticker] = int(round(rank / max(n - 1, 1) * 99))
    return percentiles


# ── prices.json Builder ──────────────────────────────────────────────────

def build_prices_json(universe, raw_data, benchmark_rows):
    """Build prices.json with per-stock price data, MAs, 52W stats, RS."""
    prices = []
    rs_composites = {}

    for stock in universe["stocks"]:
        yf = stock["yfinance_ticker"]
        ticker = stock["ticker"]

        if yf not in raw_data or len(raw_data[yf]) < 200:
            print(f"  SKIP {ticker} — insufficient data ({len(raw_data.get(yf, []))} rows)")
            continue

        rows_with_sma = compute_smas(raw_data[yf])

        # Latest row + previous day
        latest = rows_with_sma[-1]
        prev = rows_with_sma[-2] if len(rows_with_sma) > 1 else latest

        # 52-week high/low (last 252 trading days)
        lookback_252 = rows_with_sma[-252:] if len(rows_with_sma) >= 252 else rows_with_sma
        high_52w = max(r["high"] for r in lookback_252)
        low_52w = min(r["low"] for r in lookback_252)

        # Swing high detection (Q8, 23-Apr-26): most recent local peak
        # A swing high = a day whose high is higher than the 5 days before and after it
        swing_high = high_52w  # fallback to 52W high
        lookback_for_swing = rows_with_sma[-126:] if len(rows_with_sma) >= 126 else rows_with_sma  # 6 months
        swing_window = 5  # days on each side
        swing_high_global_idx = None  # MD-V2-PIPELINE-FIELDS-S25-MARKER: index into rows_with_sma of the swing high
        for si in range(len(lookback_for_swing) - 1, swing_window - 1, -1):
            candidate = lookback_for_swing[si]["high"]
            is_peak = True
            for sj in range(max(0, si - swing_window), min(len(lookback_for_swing), si + swing_window + 1)):
                if sj != si and lookback_for_swing[sj]["high"] > candidate:
                    is_peak = False
                    break
            if is_peak:
                swing_high = candidate
                # map local swing index -> global index into rows_with_sma
                swing_high_global_idx = len(rows_with_sma) - len(lookback_for_swing) + si
                break

        # Volume averages
        recent_20 = rows_with_sma[-20:] if len(rows_with_sma) >= 20 else rows_with_sma
        recent_60 = rows_with_sma[-60:] if len(rows_with_sma) >= 60 else rows_with_sma
        adv_1m = round(sum(r["volume"] for r in recent_20) / len(recent_20))
        adv_3m = round(sum(r["volume"] for r in recent_60) / len(recent_60))

        # Up/down day volume split (ORIG-18)
        # Classify each day: up = close >= prior close, down = close < prior close
        def _split_vol(window):
            up_vols, dn_vols = [], []
            for i in range(1, len(window)):
                if window[i]["close"] >= window[i - 1]["close"]:
                    up_vols.append(window[i]["volume"])
                else:
                    dn_vols.append(window[i]["volume"])
            avg_up = round(sum(up_vols) / len(up_vols)) if up_vols else 0
            avg_dn = round(sum(dn_vols) / len(dn_vols)) if dn_vols else 0
            return avg_up, avg_dn

        adv_1m_up, adv_1m_dn = _split_vol(recent_20)
        adv_3m_up, adv_3m_dn = _split_vol(recent_60)
        # MD-V2-CALIB2-MARKER: 10D up/down volume split (added for Breakout indicator)
        recent_10 = rows_with_sma[-10:] if len(rows_with_sma) >= 10 else rows_with_sma
        adv_10d_up, adv_10d_dn = _split_vol(recent_10)

        # RS composite
        rs_composite, rs_returns = compute_rs_composite(raw_data[yf], benchmark_rows)
        rs_composites[ticker] = rs_composite

        # Build MAs dict (current + previous day for DoD comparison)
        # MD-V2-S46-MAS-5D-LOOKBACK-MARKER (18-May-26): also expose 5d-ago + 6d-ago
        # MA values to enable the Probing/Spec test (D-MD-V2-108) criterion 5
        # ("20D MA rising AND was falling 5 days ago" -> 5-day actionability window).
        mas = {}
        for p in SMA_PERIODS:
            key = f"sma_{p}"
            mas[f"{p}D"] = latest.get(key)
            mas[f"{p}D_prev"] = prev.get(key)
            mas[f"{p}D_5d_ago"] = rows_with_sma[-6].get(key) if len(rows_with_sma) >= 6 else None
            mas[f"{p}D_6d_ago"] = rows_with_sma[-7].get(key) if len(rows_with_sma) >= 7 else None

        # Previous day close for the SMA DoD calculations in the pullback monitor
        prev_sma_rows = rows_with_sma[-2] if len(rows_with_sma) > 1 else None

        # 200D uptrend month count: how many of last 12 months had 200D MA rising MoM
        ma200_months_rising = 0
        ma200_month_detail = []
        if len(rows_with_sma) >= 252:
            # Sample month-end 200D values (every ~21 trading days)
            month_samples = []
            for mi in range(13):  # 13 sample points = 12 intervals
                idx = len(rows_with_sma) - 1 - (mi * 21)
                if idx >= 0 and rows_with_sma[idx].get("sma_200") is not None:
                    month_samples.append(rows_with_sma[idx]["sma_200"])
                else:
                    month_samples.append(None)
            month_samples.reverse()  # oldest first
            for mi in range(1, len(month_samples)):
                if month_samples[mi] is not None and month_samples[mi - 1] is not None:
                    rising = month_samples[mi] > month_samples[mi - 1]
                    ma200_month_detail.append(rising)
                    if rising:
                        ma200_months_rising += 1
                else:
                    ma200_month_detail.append(False)

        # Basing Plateau 3-month duration: check each BP test over last 63 trading days
        # 95% threshold = at least 60 of 63 days must meet the condition.
        # Per-day pass/fail history + current continuous-streak retained (02-May-26)
        # so the dashboard can render duration richness, not just binary flags.
        bp_duration = {"loose": False, "medium": False, "tight": False}
        bp_lookback = min(63, len(rows_with_sma))
        bp_window = rows_with_sma[-bp_lookback:]
        bp_threshold = 0.95

        def _bp_history(window, test_fn):
            """Return per-day boolean list (oldest first) of test outcomes."""
            return [bool(test_fn(r)) for r in window]

        def _bp_streak(history):
            """Walk history backwards from latest day; count consecutive True's
            until first False. Returns 0 if today is failing."""
            n = 0
            for v in reversed(history):
                if v:
                    n += 1
                else:
                    break
            return n

        def _wp(r, key_a, key_b, pct):
            """Within ±pct of each other using SMA values from a single row."""
            va = r.get(key_a)
            vb = r.get(key_b)
            if va is None or vb is None or vb == 0:
                return False
            return abs(va - vb) / vb <= pct

        # Loose: P within ±15% of 200D AND 150D, AND 50D within ±15% of 200D AND 150D
        loose_test = lambda r: (
            _wp(r, "close", "sma_200", 0.15) and _wp(r, "close", "sma_150", 0.15) and
            _wp(r, "sma_50", "sma_200", 0.15) and _wp(r, "sma_50", "sma_150", 0.15))
        loose_history = _bp_history(bp_window, loose_test)
        loose_passes = sum(1 for v in loose_history if v)
        loose_pct = (loose_passes / len(loose_history)) if loose_history else 0
        bp_duration["loose"] = loose_pct >= bp_threshold
        bp_duration["loose_pct"] = round(loose_pct, 3)
        bp_duration["loose_days_passed"] = loose_passes
        bp_duration["loose_days_total"] = len(loose_history)
        bp_duration["loose_history"] = loose_history
        bp_duration["loose_streak"] = _bp_streak(loose_history)

        # Medium: + 150D within ±10% of 200D
        medium_test = lambda r: (
            _wp(r, "close", "sma_200", 0.10) and _wp(r, "close", "sma_150", 0.10) and
            _wp(r, "sma_50", "sma_200", 0.10) and _wp(r, "sma_50", "sma_150", 0.10) and
            _wp(r, "sma_150", "sma_200", 0.10))
        medium_history = _bp_history(bp_window, medium_test)
        medium_passes = sum(1 for v in medium_history if v)
        medium_pct = (medium_passes / len(medium_history)) if medium_history else 0
        bp_duration["medium"] = medium_pct >= bp_threshold
        bp_duration["medium_pct"] = round(medium_pct, 3)
        bp_duration["medium_days_passed"] = medium_passes
        bp_duration["medium_days_total"] = len(medium_history)
        bp_duration["medium_history"] = medium_history
        bp_duration["medium_streak"] = _bp_streak(medium_history)

        # Tight: all within ±5%
        tight_test = lambda r: (
            _wp(r, "close", "sma_200", 0.05) and _wp(r, "close", "sma_150", 0.05) and
            _wp(r, "sma_50", "sma_200", 0.05) and _wp(r, "sma_50", "sma_150", 0.05) and
            _wp(r, "sma_150", "sma_200", 0.05))
        tight_history = _bp_history(bp_window, tight_test)
        tight_passes = sum(1 for v in tight_history if v)
        tight_pct = (tight_passes / len(tight_history)) if tight_history else 0
        bp_duration["tight"] = tight_pct >= bp_threshold
        bp_duration["tight_pct"] = round(tight_pct, 3)
        bp_duration["tight_days_passed"] = tight_passes
        bp_duration["tight_days_total"] = len(tight_history)
        bp_duration["tight_history"] = tight_history
        bp_duration["tight_streak"] = _bp_streak(tight_history)

        # ── Pass B (03-May-26): 3 new orthogonal Stage-1 tests ─────
        # Stored as bp_extras dict; consumed by qualification block as bp.flat_mas_pass /
        # bp.vol_contraction_pass / bp.time_in_base_pass and the bp.score composite.

        bp_extras = {
            "flat_mas_pass": False, "slope_200": None, "slope_150": None,
            "vol_contraction_pass": False, "vol_ratio": None,
            "time_in_base_pass": False, "days_since_drop": None,
        }

        # T-NEW-1: MA slope flatness (annualised)
        # slope = (sma_today - sma_63d_ago) / sma_63d_ago * (252/63) = annualised
        # Pass if abs(slope_200) <= 0.05 AND abs(slope_150) <= 0.08 (loosened in Pass A.3)
        if len(rows_with_sma) >= 64:
            sma_200_today = rows_with_sma[-1].get("sma_200")
            sma_150_today = rows_with_sma[-1].get("sma_150")
            sma_200_prior = rows_with_sma[-64].get("sma_200")
            sma_150_prior = rows_with_sma[-64].get("sma_150")
            if sma_200_today and sma_200_prior and sma_200_prior != 0:
                slope_200 = (sma_200_today - sma_200_prior) / sma_200_prior * (252.0 / 63.0)
                bp_extras["slope_200"] = round(slope_200, 4)
            if sma_150_today and sma_150_prior and sma_150_prior != 0:
                slope_150 = (sma_150_today - sma_150_prior) / sma_150_prior * (252.0 / 63.0)
                bp_extras["slope_150"] = round(slope_150, 4)
            if bp_extras["slope_200"] is not None and bp_extras["slope_150"] is not None:
                # Pass A.3 (03-May-26): loosened from ±2%/±4% to ±5%/±8% per Richard.
                # Original ±2% caught only 5% of universe (most stocks have mild trend drift in
                # current Iran-driven environment). ±5% on 200D is still genuinely flat (5%/yr ≈ barely ticking).
                bp_extras["flat_mas_pass"] = (
                    abs(bp_extras["slope_200"]) <= 0.05 and abs(bp_extras["slope_150"]) <= 0.08
                )

        # T-NEW-2: Volume contraction — avg L3M vol / avg L12M vol < 0.90
        # L3M is INCLUDED in L12M (per Richard's spec; Watson flagged limitation in decisions.md).
        if len(rows_with_sma) >= 252:
            vols_l3m = [r.get("volume") for r in rows_with_sma[-63:] if r.get("volume") is not None]
            vols_l12m = [r.get("volume") for r in rows_with_sma[-252:] if r.get("volume") is not None]
            if len(vols_l3m) > 0 and len(vols_l12m) > 0:
                avg_l3m = sum(vols_l3m) / len(vols_l3m)
                avg_l12m = sum(vols_l12m) / len(vols_l12m)
                if avg_l12m > 0:
                    ratio = avg_l3m / avg_l12m
                    bp_extras["vol_ratio"] = round(ratio, 3)
                    bp_extras["vol_contraction_pass"] = ratio < 0.90

        # T-NEW-3: Time-in-base — ≥60 trading days since last 20% drop from prior 30d high
        # AND no MM99 Capital pass in last ~3 month-ends. (mm99_monthly_history populated below;
        # we use this stock's mm99_monthly_history list which we'll compute next.)
        # Walk back from today, find most recent close that was ≤80% of its prior 30d high.
        if len(rows_with_sma) >= 60:
            window_n = min(252, len(rows_with_sma))
            most_recent_drop_idx = None
            for back_i in range(window_n - 1, 30, -1):  # newest -> oldest, but keep last drop
                cl = rows_with_sma[-1 - (window_n - 1 - back_i)].get("close") if back_i < window_n else None
            # Simpler: index 0..len(rows_with_sma)-1 walking forward, track latest qualifying drop
            most_recent_drop_idx = None
            n_total = len(rows_with_sma)
            for i in range(30, n_total):
                row_i = rows_with_sma[i]
                cl = row_i.get("close")
                if cl is None:
                    continue
                prior_window = rows_with_sma[i-30:i]
                prior_highs = [r.get("high") for r in prior_window if r.get("high") is not None]
                if not prior_highs:
                    continue
                prior_high = max(prior_highs)
                if prior_high > 0 and cl <= prior_high * 0.80:
                    most_recent_drop_idx = i
            if most_recent_drop_idx is not None:
                days_since = (n_total - 1) - most_recent_drop_idx
            else:
                days_since = window_n  # no drop found in window — treat as full window
            bp_extras["days_since_drop"] = days_since
            # mm99 recent capital check — populated below; use placeholder of False here, refined
            # after mm99_monthly_history is built. Pre-set time_in_base_pass on days_since alone;
            # final pass-flag is recomputed after mm99_monthly_history exists (see below).
            bp_extras["time_in_base_pass"] = days_since >= 60

        # ── MM99 Monthly History (T1-T8, 28-Apr-26) ────────────────
        # At each of the last 12 calendar month-ends, reconstruct all 8
        # Minervini technical tests and record whether ALL 8 passed.
        # Result: list of 12 booleans, oldest first.
        mm99_monthly_history = []
        if len(rows_with_sma) >= 252:
            # Build a date-indexed lookup from rows_with_sma for fast access
            # Each row has row["date"] as a string "YYYY-MM-DD"
            row_dates = [r["date"] for r in rows_with_sma]

            # Determine the 12 calendar month-ends preceding the latest date
            latest_date = datetime.strptime(row_dates[-1], "%Y-%m-%d").date()
            month_end_dates = []
            # Walk backwards from the month before the latest date's month
            d = latest_date.replace(day=1) - timedelta(days=1)  # last day of prior month
            for _ in range(12):
                month_end_dates.append(d)
                d = d.replace(day=1) - timedelta(days=1)  # last day of month before
            month_end_dates.reverse()  # oldest first

            for me_date in month_end_dates:
                # Find the nearest trading day on or before this month-end
                me_str = me_date.strftime("%Y-%m-%d")
                # Binary search: find last row with date <= me_str
                best_idx = None
                for scan_i in range(len(row_dates) - 1, -1, -1):
                    if row_dates[scan_i] <= me_str:
                        best_idx = scan_i
                        break

                if best_idx is None or best_idx < 252:
                    # Not enough history at this month-end to compute 52W stats
                    mm99_monthly_history.append(False)
                    continue

                snap = rows_with_sma[best_idx]
                snap_p = snap["close"]
                snap_200 = snap.get("sma_200")
                snap_150 = snap.get("sma_150")
                snap_50 = snap.get("sma_50")

                if snap_200 is None or snap_150 is None or snap_50 is None:
                    mm99_monthly_history.append(False)
                    continue

                # T1: Price > 200D MA
                h_t1 = snap_p > snap_200
                # T2: 200D MA rising (compare to prior month's nearest row)
                # Use row ~21 trading days earlier
                prev_200_idx = max(0, best_idx - 21)
                prev_200_val = rows_with_sma[prev_200_idx].get("sma_200")
                h_t2 = (prev_200_val is not None and snap_200 > prev_200_val)
                # T3: Price > 150D MA
                h_t3 = snap_p > snap_150
                # T4: 150D > 200D
                h_t4 = snap_150 > snap_200
                # T5: 50D > 150D
                h_t5 = snap_50 > snap_150
                # T6: Price > 50D MA
                h_t6 = snap_p > snap_50
                # T7: Price > 52W Low * 1.20 (at that point in time)
                lookback_52w = rows_with_sma[max(0, best_idx - 252):best_idx + 1]
                h_h52 = max(r["high"] for r in lookback_52w)
                h_l52 = min(r["low"] for r in lookback_52w)
                h_t7 = (h_l52 > 0 and snap_p > h_l52 * 1.20)
                # T8: Price within 25% of 52W High
                h_t8 = (h_h52 > 0 and snap_p >= h_h52 * 0.75)

                all_pass = all([h_t1, h_t2, h_t3, h_t4, h_t5, h_t6, h_t7, h_t8])
                mm99_monthly_history.append(all_pass)
        else:
            mm99_monthly_history = [False] * 12

        # Pad to exactly 12 if we got fewer month-ends
        while len(mm99_monthly_history) < 12:
            mm99_monthly_history.insert(0, False)

        # Pass B refinement: time_in_base_pass also requires no recent MM99 Capital pass
        # (any of the last 3 month-ends). If MM99 Capital fired recently, the stock has
        # already launched into Stage 2 — it's not a fresh Stage 1 base.
        if bp_extras.get("time_in_base_pass") and len(mm99_monthly_history) >= 3:
            recent_mm99_capital = any(mm99_monthly_history[-3:])
            if recent_mm99_capital:
                bp_extras["time_in_base_pass"] = False

        # ── UTR pre-computed metrics (S3-S7, 27-Apr-26) ─────────────
        # These feed into compute_all_filters for Uptrend Retest signals.
        # Pattern follows BP duration: compute from daily rows here, pass as summary fields.

        # S3: Volume trend — is volume drying up during pullback?
        # Compare recent 10-day ADV to 50-day ADV. Ratio < 1.0 = volume declining (constructive).
        recent_10 = rows_with_sma[-10:] if len(rows_with_sma) >= 10 else rows_with_sma
        recent_50 = rows_with_sma[-50:] if len(rows_with_sma) >= 50 else rows_with_sma
        adv_10d = sum(r["volume"] for r in recent_10) / len(recent_10) if recent_10 else 0
        adv_50d = sum(r["volume"] for r in recent_50) / len(recent_50) if recent_50 else 0
        utr_vol_trend = round(adv_10d / adv_50d, 4) if adv_50d > 0 else None

        # S4: Up/down volume ratio (1-month) — already have adv_1m_up / adv_1m_dn
        utr_updown_ratio = round(adv_1m_up / adv_1m_dn, 4) if adv_1m_dn > 0 else None

        # S5: Candle quality — % of last 20 days where close is in upper 40% of daily range
        # Upper 40% means close >= low + 0.6 * (high - low). This signals accumulation.
        candle_window = rows_with_sma[-20:] if len(rows_with_sma) >= 20 else rows_with_sma
        candle_upper_count = 0
        candle_valid = 0
        for cr in candle_window:
            rng = cr["high"] - cr["low"]
            if rng > 0:
                candle_valid += 1
                if cr["close"] >= cr["low"] + 0.6 * rng:
                    candle_upper_count += 1
        utr_candle_quality = round(candle_upper_count / candle_valid, 4) if candle_valid > 0 else None

        # S6: Distribution days in last 25 sessions
        # O'Neil definition: close < prior close AND volume > 1.25× ADV50
        dist_window = rows_with_sma[-26:] if len(rows_with_sma) >= 26 else rows_with_sma  # 26 rows → 25 comparisons
        dist_day_count = 0
        for di in range(1, len(dist_window)):
            if (dist_window[di]["close"] < dist_window[di - 1]["close"] and
                    adv_50d > 0 and dist_window[di]["volume"] > 1.25 * adv_50d):
                dist_day_count += 1
        utr_dist_days = dist_day_count

        # S7: Pullback contraction — ATR10 vs ATR20
        # True Range = max(H-L, |H-prev_C|, |L-prev_C|). Ratio < 1.0 = range contracting.
        def _atr(window):
            """Average True Range over a window of daily rows."""
            trs = []
            for ai in range(1, len(window)):
                h = window[ai]["high"]
                l = window[ai]["low"]
                pc = window[ai - 1]["close"]
                tr = max(h - l, abs(h - pc), abs(l - pc))
                trs.append(tr)
            return sum(trs) / len(trs) if trs else 0

        atr_window_20 = rows_with_sma[-21:] if len(rows_with_sma) >= 21 else rows_with_sma
        atr_window_10 = rows_with_sma[-11:] if len(rows_with_sma) >= 11 else rows_with_sma
        atr_20 = _atr(atr_window_20)
        atr_10 = _atr(atr_window_10)
        utr_pullback_contraction = round(atr_10 / atr_20, 4) if atr_20 > 0 else None

        # ── UTR V2 pre-computed fields (27-Apr-26) ─────────────────────
        # MA direction bools: confirm pullback is short-term (Early stage E2)
        utr_5d_declining = False
        utr_10d_declining = False
        utr_50d_rising = False
        utr_150d_rising = False
        if prev_sma_rows is not None:
            sma5_now = latest.get("sma_5")
            sma5_prev = prev_sma_rows.get("sma_5")
            if sma5_now is not None and sma5_prev is not None:
                utr_5d_declining = sma5_now < sma5_prev
            sma10_now = latest.get("sma_10")
            sma10_prev = prev_sma_rows.get("sma_10")
            if sma10_now is not None and sma10_prev is not None:
                utr_10d_declining = sma10_now < sma10_prev
            sma50_now = latest.get("sma_50")
            sma50_prev = prev_sma_rows.get("sma_50")
            if sma50_now is not None and sma50_prev is not None:
                utr_50d_rising = sma50_now > sma50_prev
            sma150_now = latest.get("sma_150")
            sma150_prev = prev_sma_rows.get("sma_150")
            if sma150_now is not None and sma150_prev is not None:
                utr_150d_rising = sma150_now > sma150_prev

        # Test MA identification: which MA is price approaching from above?
        # Scan 50D → 100D → 150D → 200D. First one price is within range of AND above.
        utr_test_ma = None
        utr_test_ma_dist = None
        _price = latest["close"]
        for _ma_label, _ma_period in [("50D", 50), ("100D", 100), ("150D", 150), ("200D", 200)]:
            _ma_val = latest.get(f"sma_{_ma_period}")
            if _ma_val is not None and _ma_val > 0:
                _dist_pct = (_price - _ma_val) / _ma_val
                # Price must be above or at most 2% below (slight undercut OK per Minervini)
                # and within 10% above (beyond 10% above = not approaching)
                if -0.02 <= _dist_pct <= 0.10:
                    utr_test_ma = _ma_label
                    utr_test_ma_dist = round(_dist_pct * 100, 2)  # as percentage
                    break

        # Retest counting: completed touch-and-bounce cycles per MA since uptrend began.
        # A completed retest = price came within 2% of MA, then moved at least 5% above it.
        # "Uptrend began" proxy: first point where 200D MA began rising in our lookback.
        utr_retest_counts = {"50D": 0, "100D": 0, "150D": 0}
        if len(rows_with_sma) >= 200:
            # Find uptrend start: first row where 200D is rising vs prior row
            _uptrend_start_idx = None
            for _ri in range(1, len(rows_with_sma)):
                _r_now = rows_with_sma[_ri]
                _r_prev = rows_with_sma[_ri - 1]
                if (_r_now.get("sma_200") is not None and _r_prev.get("sma_200") is not None
                        and _r_now["sma_200"] > _r_prev["sma_200"]):
                    _uptrend_start_idx = _ri
                    break

            if _uptrend_start_idx is not None:
                _scan_rows = rows_with_sma[_uptrend_start_idx:]
                for _ma_label, _ma_period in [("50D", 50), ("100D", 100), ("150D", 150)]:
                    _in_touch = False  # currently within 2% of MA
                    _bounced = False   # has moved 5%+ above after a touch
                    _count = 0
                    for _sr in _scan_rows:
                        _ma_v = _sr.get(f"sma_{_ma_period}")
                        if _ma_v is None or _ma_v <= 0:
                            continue
                        _d = (_sr["close"] - _ma_v) / _ma_v
                        if not _in_touch and -0.02 <= _d <= 0.02:
                            # Touched the MA
                            _in_touch = True
                            _bounced = False
                        elif _in_touch and _d > 0.05:
                            # Bounced 5%+ above — retest complete
                            _count += 1
                            _in_touch = False
                            _bounced = True
                        elif _in_touch and _d < -0.05:
                            # Broke down through MA — failed retest, reset
                            _in_touch = False
                            _bounced = False
                    utr_retest_counts[_ma_label] = _count


        # ── MD-V2-PIPELINE-MARKER: Historical MA samples + base detection ──
        # ── MD V2: 12-month MA samples (150D, 200D) + Volume 200D-MA trend ──
        def _sample_monthly_ma(rows, sma_key, n_months=13):
            samples = []
            for mi in range(n_months):
                idx = len(rows) - 1 - (mi * 21)
                if idx >= 0 and rows[idx].get(sma_key) is not None:
                    samples.append(rows[idx][sma_key])
                else:
                    samples.append(None)
            samples.reverse()
            return samples

        def _decline_rates(samples):
            rates = []
            for i in range(1, len(samples)):
                if samples[i] is None or samples[i - 1] is None or samples[i - 1] == 0:
                    rates.append(None)
                else:
                    rates.append((samples[i] - samples[i - 1]) / samples[i - 1])
            return rates

        ma150_samples = _sample_monthly_ma(rows_with_sma, "sma_150") if len(rows_with_sma) >= 252 else [None] * 13
        ma200_samples = _sample_monthly_ma(rows_with_sma, "sma_200") if len(rows_with_sma) >= 252 else [None] * 13
        ma150_mom_rates = _decline_rates(ma150_samples)
        ma200_mom_rates = _decline_rates(ma200_samples)

        # Volume MA-200 trend
        vol200_samples = []
        volumes = [r["volume"] for r in rows_with_sma]
        for mi in range(13):
            idx = len(rows_with_sma) - 1 - (mi * 21)
            if idx >= 199:
                v200 = sum(volumes[idx - 199:idx + 1]) / 200.0
                vol200_samples.append(v200)
            else:
                vol200_samples.append(None)
        vol200_samples.reverse()
        vol_ma200_month_detail = []
        vol_ma200_months_rising = 0
        for mi in range(1, len(vol200_samples)):
            if vol200_samples[mi] is not None and vol200_samples[mi - 1] is not None:
                rising = vol200_samples[mi] > vol200_samples[mi - 1]
                vol_ma200_month_detail.append(rising)
                if rising:
                    vol_ma200_months_rising += 1
            else:
                vol_ma200_month_detail.append(False)

        # 20D MA monthly history
        ma20_samples = _sample_monthly_ma(rows_with_sma, "sma_20") if len(rows_with_sma) >= 32 else [None] * 13
        ma20_month_detail = []
        ma20_months_rising = 0
        for mi in range(1, len(ma20_samples)):
            if ma20_samples[mi] is not None and ma20_samples[mi - 1] is not None:
                rising = ma20_samples[mi] > ma20_samples[mi - 1]
                ma20_month_detail.append(rising)
                if rising:
                    ma20_months_rising += 1
            else:
                ma20_month_detail.append(False)

        # ── Base count since 52W low (15% fall + 20 days below high + breakthrough) ──
        base_count_since_52wl = 0
        if len(rows_with_sma) >= 252:
            last_252 = rows_with_sma[-252:]
            lows_252 = [r["low"] for r in last_252]
            min_low_idx_rel = lows_252.index(min(lows_252))
            start_idx_global = len(rows_with_sma) - 252 + min_low_idx_rel
            swing_window_bp = 5
            completed_swing_highs = []
            for sj in range(start_idx_global + swing_window_bp, len(rows_with_sma) - swing_window_bp):
                candidate = rows_with_sma[sj]["high"]
                is_peak = True
                for sk in range(sj - swing_window_bp, sj + swing_window_bp + 1):
                    if sk != sj and rows_with_sma[sk]["high"] > candidate:
                        is_peak = False
                        break
                if is_peak:
                    completed_swing_highs.append((sj, candidate))
            for sj_idx, sj_high in completed_swing_highs:
                sub_end = len(rows_with_sma)
                for nh_idx, _ in completed_swing_highs:
                    if nh_idx > sj_idx:
                        sub_end = nh_idx
                        break
                sub_window = rows_with_sma[sj_idx + 1:sub_end]
                if not sub_window:
                    continue
                sub_low = min(r["low"] for r in sub_window)
                # MD-V2-S48-BASECOUNT-RELAX-MARKER (19-May-26):
                # Relaxed 15% drop / 20-day below to 8% / 10-day so the
                # algorithm captures Stage 2 typical-base patterns.
                if sub_low > sj_high * 0.92:
                    continue
                days_below = sum(1 for r in sub_window if r["high"] < sj_high)
                if days_below < 10:
                    continue
                sub_low_idx_in_sub = next(i for i, r in enumerate(sub_window) if r["low"] == sub_low)
                post_low_window = sub_window[sub_low_idx_in_sub:]
                breakthrough = any(r["high"] > sj_high for r in post_low_window)
                if breakthrough:
                    base_count_since_52wl += 1

        # ── Higher-lows / Lower-lows count (last 6 months) ──
        higher_lows_count = 0
        lower_lows_count = 0
        if len(rows_with_sma) >= 126:
            trough_window = 5
            swing_lows = []
            recent_180 = rows_with_sma[-180:] if len(rows_with_sma) >= 180 else rows_with_sma
            for ti in range(trough_window, len(recent_180) - trough_window):
                candidate = recent_180[ti]["low"]
                is_trough = True
                for tj in range(ti - trough_window, ti + trough_window + 1):
                    if tj != ti and recent_180[tj]["low"] < candidate:
                        is_trough = False
                        break
                if is_trough:
                    swing_lows.append((ti, candidate))
            if len(swing_lows) >= 2:
                higher_lows_count = 1
                for k in range(len(swing_lows) - 1, 0, -1):
                    if swing_lows[k][1] > swing_lows[k - 1][1]:
                        higher_lows_count += 1
                    else:
                        break
                lower_lows_count = 1
                for k in range(len(swing_lows) - 1, 0, -1):
                    if swing_lows[k][1] < swing_lows[k - 1][1]:
                        lower_lows_count += 1
                    else:
                        break

        # ── RS at M=-3 (composite-only; percentile computed in second pass) ──
        rs_at_m3 = None
        if len(rows_with_sma) >= 126 and benchmark_rows and len(benchmark_rows) >= 126:
            try:
                sliced_stock = rows_with_sma[:-63]
                sliced_bench = benchmark_rows[:len(sliced_stock)] if len(benchmark_rows) >= len(sliced_stock) else benchmark_rows
                if len(sliced_stock) >= 252 and len(sliced_bench) >= 252:
                    rs_m3_composite, _ = compute_rs_composite(sliced_stock, sliced_bench)
                    rs_at_m3 = rs_m3_composite
            except Exception:
                rs_at_m3 = None

        # ── Recent pullback % from swing high ──
        recent_pullback_pct = None
        if swing_high and swing_high > 0:
            recent_pullback_pct = round((swing_high - latest["close"]) / swing_high, 4)

        # ── MD-V2-PIPELINE-FIELDS-S25-MARKER: Session 25 pipeline fields ──
        # max_pullback_since_swing_high (D-MD-V2-49 test 1): the DEEPEST drawdown
        # from the swing high reached on/after the swing-high day - even if price
        # has since reclawed some of the loss. recent_pullback_pct measures only
        # the CURRENT distance, which is insufficient for the Basing test.
        max_pullback_since_swing_high = None
        days_below_swing_high = None
        if swing_high and swing_high > 0 and swing_high_global_idx is not None:
            _post_rows = rows_with_sma[swing_high_global_idx:]
            if _post_rows:
                _min_low = min(r["low"] for r in _post_rows)
                max_pullback_since_swing_high = round((swing_high - _min_low) / swing_high, 4)
            # days_below_swing_high (D-MD-V2-49 test 2): count trailing trading days
            # where the close has been below the swing high. Counts back from the
            # latest row until a day closes at/above the swing high.
            _dbsh = 0
            for _r in reversed(rows_with_sma):
                if _r["close"] < swing_high:
                    _dbsh += 1
                else:
                    break
            days_below_swing_high = _dbsh

        # utr_candle_quality_10d / _3d (D-MD-V2-51 t6 / D-MD-V2-52 t3):
        # same logic as the existing 20-day utr_candle_quality - proportion of
        # days whose close sits in the UPPER 40% of the daily range
        # (close >= low + 0.6 * range). Windowed to 10 and 3 trading days.
        def _candle_quality(window):
            _uc = 0
            _vd = 0
            for _cr in window:
                _rng = _cr["high"] - _cr["low"]
                if _rng > 0:
                    _vd += 1
                    if _cr["close"] >= _cr["low"] + 0.6 * _rng:
                        _uc += 1
            return round(_uc / _vd, 4) if _vd > 0 else None
        _cq10_window = rows_with_sma[-10:] if len(rows_with_sma) >= 10 else rows_with_sma
        _cq3_window = rows_with_sma[-3:] if len(rows_with_sma) >= 3 else rows_with_sma
        utr_candle_quality_10d = _candle_quality(_cq10_window)
        utr_candle_quality_3d = _candle_quality(_cq3_window)

        # utr_updown_ratio_5d (D-MD-V2-52 t4): up-day vol / down-day vol over the
        # last 5 trading days only. Reuses the existing _split_vol helper.
        _recent_5 = rows_with_sma[-5:] if len(rows_with_sma) >= 5 else rows_with_sma
        _adv_5d_up, _adv_5d_dn = _split_vol(_recent_5)
        utr_updown_ratio_5d = round(_adv_5d_up / _adv_5d_dn, 4) if _adv_5d_dn > 0 else None

        # close_pct_change_today (D-MD-V2-52 t5 confirmation): today's close vs
        # yesterday's close as a fraction. >= 0.02 satisfies the confirmation test.
        close_pct_change_today = None
        if prev["close"] and prev["close"] > 0:
            close_pct_change_today = round((latest["close"] - prev["close"]) / prev["close"], 4)
        # ── END MD-V2-PIPELINE-FIELDS-S25-MARKER block ──

        # ── MD-V2-SCREENS-S26-MARKER: VCP contraction extraction (D-MD-V2-61) ──
        # Within the base (swing high -> today), walk the price series and
        # extract the ordered sequence of contractions. A contraction is a
        # local-high-to-local-low swing. Detection uses a SINGLE sensitive
        # swing threshold (Option A); the wide-early/tight-late requirement
        # is enforced downstream by the narrowing test, not here.
        # Each contraction stores: depth (pct decline), avg daily volume, low.
        VCP_SWING_THRESHOLD = 0.03  # ~3% - primary calibration parameter
        vcp_contractions = []
        if swing_high_global_idx is not None and swing_high_global_idx < len(rows_with_sma) - 3:
            _base = rows_with_sma[swing_high_global_idx:]
            # Walk the base extracting alternating swing highs and swing lows.
            # Start at the swing high; find the next swing low (a trough that
            # then recovers by >= threshold), then the next swing high, etc.
            _i = 0
            _n = len(_base)
            _cur_high_idx = 0
            _cur_high = _base[0]["high"]
            while _i < _n:
                # find the lowest low between cur_high and the next point
                # where price recovers >= threshold off that low
                _low_idx = _cur_high_idx
                _low_val = _base[_cur_high_idx]["low"]
                _j = _cur_high_idx + 1
                _recovered = False
                while _j < _n:
                    if _base[_j]["low"] < _low_val:
                        _low_val = _base[_j]["low"]
                        _low_idx = _j
                    # recovery off the running low?
                    if _low_val > 0 and (_base[_j]["high"] - _low_val) / _low_val >= VCP_SWING_THRESHOLD:
                        _recovered = True
                        break
                    _j += 1
                # only count a contraction if it is a real high->low->recovery
                if _low_idx > _cur_high_idx and _cur_high > 0:
                    _depth = (_cur_high - _low_val) / _cur_high
                    if _depth >= VCP_SWING_THRESHOLD:
                        _seg = _base[_cur_high_idx:_low_idx + 1]
                        _vols = [r["volume"] for r in _seg if r.get("volume") is not None]
                        _avg_vol = (sum(_vols) / len(_vols)) if _vols else 0
                        vcp_contractions.append({
                            "depth": round(_depth, 4),
                            "avg_vol": round(_avg_vol),
                            "low": round(_low_val, 4),
                        })
                if not _recovered:
                    break
                # the next swing high = highest high between this low and the
                # recovery point; advance past it
                _next_high_idx = _low_idx
                _next_high = _base[_low_idx]["high"]
                _k = _low_idx + 1
                while _k <= _j and _k < _n:
                    if _base[_k]["high"] > _next_high:
                        _next_high = _base[_k]["high"]
                        _next_high_idx = _k
                    _k += 1
                if _next_high_idx <= _cur_high_idx:
                    break  # no progress - stop
                _cur_high_idx = _next_high_idx
                _cur_high = _next_high
                _i = _next_high_idx
                if len(vcp_contractions) >= 8:
                    break  # safety cap
        # ── END MD-V2-SCREENS-S26-MARKER VCP block ──
        # ── END MD-V2-PIPELINE-MARKER block ──

        entry = {
            "ticker": ticker,
            "yf_ticker": yf,
            "company_name": stock["company_name"],
            "sector": stock["sector"],
            "industry": stock["industry"],
            "price": latest["close"],
            "price_prev": prev["close"],
            "date": latest["date"],
            "mas": mas,
            "ma200_months_rising": ma200_months_rising,
            "ma200_month_detail": ma200_month_detail,
            "mm99_monthly_history": mm99_monthly_history,
            "bp_duration": bp_duration,
            "bp_extras": bp_extras,
            "high_52w": round(high_52w, 4),
            "swing_high": round(swing_high, 4),
            "low_52w": round(low_52w, 4),
            "adv_1m": adv_1m,
            "adv_3m": adv_3m,
            "adv_1m_up": adv_1m_up,
            "adv_1m_dn": adv_1m_dn,
            "adv_3m_up": adv_3m_up,
            "adv_3m_dn": adv_3m_dn,
            "adv_10d_up": adv_10d_up,
            "adv_10d_dn": adv_10d_dn,
            "rs_composite": rs_composite,
            "rs_returns": rs_returns,
            # UTR pre-computed metrics (S3-S7)
            "utr_vol_trend": utr_vol_trend,           # S3: 10D/50D ADV ratio (< 1.0 = declining)
            "utr_updown_ratio": utr_updown_ratio,     # S4: up-day vol / down-day vol
            "utr_candle_quality": utr_candle_quality,  # S5: % closes in upper 40% of range
            "utr_dist_days": utr_dist_days,           # S6: distribution day count (last 25)
            "utr_pullback_contraction": utr_pullback_contraction,  # S7: ATR10/ATR20 ratio
            # UTR V2 fields
            "utr_5d_declining": utr_5d_declining,
            "utr_10d_declining": utr_10d_declining,
            "utr_50d_rising": utr_50d_rising,
            "utr_150d_rising": utr_150d_rising,
            "utr_test_ma": utr_test_ma,               # which MA being tested: "50D"/"100D"/"150D"/"200D"/None
            "utr_test_ma_dist": utr_test_ma_dist,     # % distance to test MA
            "utr_retest_counts": utr_retest_counts,   # {"50D": N, "100D": N, "150D": N}
            # MD V2 historical fields
            "ma150_samples": [round(s, 4) if s is not None else None for s in ma150_samples],
            "ma200_samples": [round(s, 4) if s is not None else None for s in ma200_samples],
            "ma150_mom_rates": [round(r, 5) if r is not None else None for r in ma150_mom_rates],
            "ma200_mom_rates": [round(r, 5) if r is not None else None for r in ma200_mom_rates],
            "vol_ma200_month_detail": vol_ma200_month_detail,
            "vol_ma200_months_rising": vol_ma200_months_rising,
            "ma20_month_detail": ma20_month_detail,
            "ma20_months_rising": ma20_months_rising,
            "base_count_since_52wl": base_count_since_52wl,
            "higher_lows_count": higher_lows_count,
            "lower_lows_count": lower_lows_count,
            "rs_at_m3": rs_at_m3,
            "recent_pullback_pct": recent_pullback_pct,
            # MD-V2-PIPELINE-FIELDS-S25-MARKER: Session 25 fields
            "max_pullback_since_swing_high": max_pullback_since_swing_high,
            "days_below_swing_high": days_below_swing_high,
            "utr_candle_quality_10d": utr_candle_quality_10d,
            "utr_candle_quality_3d": utr_candle_quality_3d,
            "utr_updown_ratio_5d": utr_updown_ratio_5d,
            "close_pct_change_today": close_pct_change_today,
            # MD-V2-SCREENS-S26-MARKER: VCP contraction sequence
            "vcp_contractions": vcp_contractions,
        }
        prices.append(entry)

    # Compute RS percentiles across the alpha universe
    rs_pcts = compute_rs_percentiles(rs_composites)
    for entry in prices:
        entry["rs_percentile"] = rs_pcts.get(entry["ticker"])

    # Sector-level RS: compute per-sector, then rank within sector
    sector_stocks = defaultdict(list)
    for entry in prices:
        sector_stocks[entry["sector"]].append(entry["ticker"])
    for sector, tickers_in_sector in sector_stocks.items():
        sector_rs = {t: rs_composites.get(t) for t in tickers_in_sector}
        sector_pcts = compute_rs_percentiles(sector_rs)
        # Compute sector mean RS for excess return calculation (Q2, 23-Apr-26)
        sector_vals = [v for v in sector_rs.values() if v is not None]
        sector_mean = sum(sector_vals) / len(sector_vals) if sector_vals else None
        for entry in prices:
            if entry["ticker"] in sector_pcts:
                entry["rs_vs_sector"] = sector_pcts[entry["ticker"]]
                # Excess return: stock RS - sector mean RS (positive = outperforming sector)
                my_rs = rs_composites.get(entry["ticker"])
                entry["rs_excess_sector"] = round(my_rs - sector_mean, 6) if my_rs is not None and sector_mean is not None else None

    # Industry-level RS: compute per-industry, then rank within industry (Q3, 23-Apr-26)
    industry_stocks = defaultdict(list)
    for entry in prices:
        industry_stocks[entry.get("industry", "")].append(entry["ticker"])
    for industry, tickers_in_industry in industry_stocks.items():
        industry_rs = {t: rs_composites.get(t) for t in tickers_in_industry}
        industry_pcts = compute_rs_percentiles(industry_rs)
        industry_vals = [v for v in industry_rs.values() if v is not None]
        industry_mean = sum(industry_vals) / len(industry_vals) if industry_vals else None
        for entry in prices:
            if entry["ticker"] in industry_pcts:
                entry["rs_vs_industry"] = industry_pcts[entry["ticker"]]
                my_rs = rs_composites.get(entry["ticker"])
                entry["rs_excess_industry"] = round(my_rs - industry_mean, 6) if my_rs is not None and industry_mean is not None else None

    # Market-level excess return: stock RS - universe mean RS
    all_rs_vals = [v for v in rs_composites.values() if v is not None]
    market_mean = sum(all_rs_vals) / len(all_rs_vals) if all_rs_vals else None
    for entry in prices:
        my_rs = rs_composites.get(entry["ticker"])
        entry["rs_excess_market"] = round(my_rs - market_mean, 6) if my_rs is not None and market_mean is not None else None

    return prices


# ── Filter Computation Engine ─────────────────────────────────────────────

def compute_all_filters(prices):
    """Compute all 5 screening filters for each stock. Returns filter-results dict."""
    results = []

    for stock in prices:
        ticker = stock["ticker"]
        p = stock["price"]
        p_prev = stock["price_prev"]
        mas = stock["mas"]
        h52 = stock["high_52w"]
        l52 = stock["low_52w"]

        # Helper: safe MA access
        def ma(period):
            return mas.get(f"{period}D")

        def ma_prev(period):
            return mas.get(f"{period}D_prev")

        def ma_rising(period):
            curr = ma(period)
            prev = ma_prev(period)
            if curr is None or prev is None:
                return False
            return curr > prev

        def within_pct(val, ref, pct):
            """Is val within ±pct% of ref?"""
            if val is None or ref is None or ref == 0:
                return False
            ratio = abs(val - ref) / ref
            return ratio <= pct

        def above(val, ref):
            if val is None or ref is None:
                return False
            return val > ref

        # ── BASING PLATEAU ────────────────────────────────────────────
        # Tests check TODAY's values + 3-month duration (95% of 63 days)
        bp = {}
        bp_dur = stock.get("bp_duration", {})

        # Group A — Loose (±15%) — today's test AND 3-month duration
        t1 = within_pct(p, ma(200), 0.15) and within_pct(p, ma(150), 0.15)
        t2 = within_pct(ma(50), ma(200), 0.15) and within_pct(ma(50), ma(150), 0.15)
        loose_dur = bp_dur.get("loose", False)
        bp["group_a"] = {"pass": t1 and t2 and loose_dur, "tests": {"T1": t1, "T2": t2},
                         "duration_met": loose_dur, "duration_pct": bp_dur.get("loose_pct", 0),
                         "days_passed": bp_dur.get("loose_days_passed", 0),
                         "days_total": bp_dur.get("loose_days_total", 0),
                         "history": bp_dur.get("loose_history", []),
                         "streak": bp_dur.get("loose_streak", 0)}

        # Group B — Medium (±10%)
        t3 = within_pct(p, ma(200), 0.10) and within_pct(p, ma(150), 0.10)
        t4 = within_pct(ma(50), ma(200), 0.10) and within_pct(ma(50), ma(150), 0.10)
        t5 = within_pct(ma(150), ma(200), 0.10)
        medium_dur = bp_dur.get("medium", False)
        bp["group_b"] = {"pass": t3 and t4 and t5 and medium_dur, "tests": {"T3": t3, "T4": t4, "T5": t5},
                         "duration_met": medium_dur, "duration_pct": bp_dur.get("medium_pct", 0),
                         "days_passed": bp_dur.get("medium_days_passed", 0),
                         "days_total": bp_dur.get("medium_days_total", 0),
                         "history": bp_dur.get("medium_history", []),
                         "streak": bp_dur.get("medium_streak", 0)}

        # Group C — Tight (±5%)
        t6 = within_pct(p, ma(200), 0.05) and within_pct(p, ma(150), 0.05)
        t7 = within_pct(ma(50), ma(200), 0.05) and within_pct(ma(50), ma(150), 0.05)
        t8 = within_pct(ma(150), ma(200), 0.05)
        tight_dur = bp_dur.get("tight", False)
        bp["group_c"] = {"pass": t6 and t7 and t8 and tight_dur, "tests": {"T6": t6, "T7": t7, "T8": t8},
                         "duration_met": tight_dur, "duration_pct": bp_dur.get("tight_pct", 0),
                         "days_passed": bp_dur.get("tight_days_passed", 0),
                         "days_total": bp_dur.get("tight_days_total", 0),
                         "history": bp_dur.get("tight_history", []),
                         "streak": bp_dur.get("tight_streak", 0)}

        # ── Pass B (D-MD-FILTER-12 to 15): composite-score + new stage mapping ──
        # Pull the 3 new test results from bp_extras (computed in build_prices_json).
        bp_ex = stock.get("bp_extras", {}) or {}
        bp["flat_mas_pass"] = bp_ex.get("flat_mas_pass", False)
        bp["slope_200"] = bp_ex.get("slope_200")
        bp["slope_150"] = bp_ex.get("slope_150")
        bp["vol_contraction_pass"] = bp_ex.get("vol_contraction_pass", False)
        bp["vol_ratio"] = bp_ex.get("vol_ratio")
        bp["time_in_base_pass"] = bp_ex.get("time_in_base_pass", False)
        bp["days_since_drop"] = bp_ex.get("days_since_drop")

        # Composite BP score: 0-4 based on the 4 orthogonal tests.
        # Test 1 = Basing (group_a pass, i.e. Loose ±15% + 3-month duration)
        # Test 2 = Flat MAs (T-NEW-1)
        # Test 3 = Volume contraction (T-NEW-2)
        # Test 4 = Time-in-base (T-NEW-3)
        bp_test_basing = bool(bp["group_a"]["pass"])
        bp_test_flat = bool(bp["flat_mas_pass"])
        bp_test_vol = bool(bp["vol_contraction_pass"])
        bp_test_time = bool(bp["time_in_base_pass"])
        bp["score"] = sum([bp_test_basing, bp_test_flat, bp_test_vol, bp_test_time])
        bp["score_max"] = 4
        bp["score_breakdown"] = {
            "basing": bp_test_basing,
            "flat_mas": bp_test_flat,
            "vol_contraction": bp_test_vol,
            "time_in_base": bp_test_time,
        }

        # Stage mapping (D-MD-FILTER-12): 4->Capital, 3->Late, 2->Early, <2->None.
        # Score=1 (Basing only) is rendered as "Base Only" tile but does NOT count as a stage.
        if bp["score"] == 4:
            bp["stage"] = "Capital"
        elif bp["score"] == 3:
            bp["stage"] = "Late"
        elif bp["score"] == 2:
            bp["stage"] = "Early"
        else:
            bp["stage"] = None

        # ── PROBING BET ───────────────────────────────────────────────
        pb = {}
        # Group A — Early (3 of 5 rising)
        pb_t1 = p > p_prev if p_prev else False
        pb_t2 = ma_rising(5)
        pb_t3 = ma_rising(10)
        pb_t4 = ma_rising(20)
        pb_t5 = ma_rising(50)
        a_tests = {"T1": pb_t1, "T2": pb_t2, "T3": pb_t3, "T4": pb_t4, "T5": pb_t5}
        a_met = sum(1 for v in a_tests.values() if v)
        pb["group_a"] = {"pass": a_met >= 3, "met": a_met, "required": 3, "tests": a_tests}

        # Group B — Late (1 of 2)
        pb_t6 = ma_rising(20)
        pb_t7 = ma_rising(50)
        b_tests = {"T6": pb_t6, "T7": pb_t7}
        b_met = sum(1 for v in b_tests.values() if v)
        pb["group_b"] = {"pass": b_met >= 1, "met": b_met, "required": 1, "tests": b_tests}

        # Group C — Dead Cat (price ≥30% below 52W high)
        pct_below_52wh = (h52 - p) / h52 if h52 > 0 else 0
        pb_t8 = pct_below_52wh >= 0.30
        pb["group_c"] = {"pass": pb_t8, "tests": {"T8": pb_t8}, "pct_below_52wh": round(pct_below_52wh, 4)}

        # Group D — Capital PB1 (P>20D + 20D rising)
        pb_t9 = above(p, ma(20))
        pb_t10 = ma_rising(20)
        pb["group_d"] = {"pass": pb_t9 and pb_t10, "tests": {"T9": pb_t9, "T10": pb_t10}}

        # Group E — Capital PB2 (P>50D + 50D rising)
        pb_t11 = above(p, ma(50))
        pb_t12 = ma_rising(50)
        pb["group_e"] = {"pass": pb_t11 and pb_t12, "tests": {"T11": pb_t11, "T12": pb_t12}}

        # PB qualification stage
        if pb["group_d"]["pass"] or pb["group_e"]["pass"]:
            pb["stage"] = "Capital"
        elif pb["group_b"]["pass"]:
            pb["stage"] = "Late"
        elif pb["group_a"]["pass"]:
            pb["stage"] = "Early"
        else:
            pb["stage"] = None

        # ── MM 99 ────────────────────────────────────────────────────
        mm = {}
        # Group A — Long-term
        mm_t1 = above(p, ma(200))
        # T2: 200D upward trend MoM — use month count (pass = at least 1 month rising)
        ma200_mr = stock.get("ma200_months_rising", 0)
        mm_t2 = ma200_mr >= 1
        mm["group_a"] = {"pass": mm_t1 and mm_t2, "tests": {"T1": mm_t1, "T2": mm_t2}, "ma200_months_rising": ma200_mr}

        # Group B — Mid-term
        mm_t3 = above(p, ma(150))
        mm_t4 = above(ma(150), ma(200))
        mm["group_b"] = {"pass": mm_t3 and mm_t4, "tests": {"T3": mm_t3, "T4": mm_t4}}

        # Group C — Short-term
        mm_t5 = above(ma(50), ma(150))
        mm_t6 = above(p, ma(50))
        mm["group_c"] = {"pass": mm_t5 and mm_t6, "tests": {"T5": mm_t5, "T6": mm_t6}}

        # Group D — 52W Leadership
        mm_t7 = above(p, l52 * 1.20) if l52 and l52 > 0 else False  # P > 20% above 52W low
        mm_t8 = (p >= h52 * 0.75) if h52 and h52 > 0 else False  # P within 25% of 52W high
        mm["group_d"] = {"pass": mm_t7 and mm_t8, "tests": {"T7": mm_t7, "T8": mm_t8}}

        # Group E — Relative Strength: excess return tests (Q2/Q3, 23-Apr-26)
        # T9: stock RS - sector mean RS > 0 (outperforming sector)
        # T10: stock RS - industry mean RS > 0 (outperforming industry)
        # T11: stock RS - market mean RS > 0 (outperforming market)
        rs_pct = stock.get("rs_percentile")
        rs_vs_sector = stock.get("rs_vs_sector")
        rs_excess_sector = stock.get("rs_excess_sector")
        rs_excess_industry = stock.get("rs_excess_industry")
        rs_excess_market = stock.get("rs_excess_market")
        mm_t9 = (rs_excess_sector is not None and rs_excess_sector > 0)
        mm_t10 = (rs_excess_industry is not None and rs_excess_industry > 0)
        mm_t11 = (rs_excess_market is not None and rs_excess_market > 0)
        mm["group_e"] = {
            "pass": mm_t9 and mm_t10 and mm_t11,
            "tests": {"T9": mm_t9, "T10": mm_t10, "T11": mm_t11},
            "rs_percentile": rs_pct,
            "rs_vs_sector": rs_vs_sector,
            "rs_excess_sector": rs_excess_sector,
            "rs_excess_industry": rs_excess_industry,
            "rs_excess_market": rs_excess_market,
        }

        # MM99 score: count passing groups A-D tests (8 tests = original Minervini template)
        mm_8pt = sum(1 for t in [mm_t1, mm_t2, mm_t3, mm_t4, mm_t5, mm_t6, mm_t7, mm_t8] if t)
        mm["score_8pt"] = mm_8pt
        # Full 11-test score
        mm_11 = mm_8pt + sum(1 for t in [mm_t9, mm_t10, mm_t11] if t)
        mm["score_11"] = mm_11

        # Monthly history: how many of last 12 months passed all 8 technical tests
        mm_hist = stock.get("mm99_monthly_history", [False] * 12)
        mm["monthly_history"] = mm_hist
        mm["months_passing"] = sum(1 for m in mm_hist if m)

        # MM99 qualification
        if mm_8pt >= 8 and mm["group_e"]["pass"]:
            mm["stage"] = "Capital"
        elif mm_8pt >= 7:
            mm["stage"] = "Late"
        elif mm_8pt >= 5:
            mm["stage"] = "Early"
        else:
            mm["stage"] = None

        # ── VCP (simplified — full pattern detection is Phase 2) ─────
        vcp = {}
        # T1: Stage 2 uptrend (require MM Groups A+B pass)
        vcp_t1 = mm["group_a"]["pass"] and mm["group_b"]["pass"]
        # T2-T5: Pattern detection requires multi-day swing analysis — placeholder
        vcp["stage_2_uptrend"] = vcp_t1
        vcp["pattern_detected"] = False  # Placeholder until pattern detection built
        vcp["note"] = "VCP pattern detection pending — Phase 2. Stage 2 check only."
        vcp["stage"] = None  # Cannot qualify without pattern detection

        # ── UPTREND RETEST V2 — Pullback Lifecycle (27-Apr-26) ────────
        # Stage = position in pullback lifecycle, not a composite score.
        # Early (pulling back) → Late (approaching MA) → Capital (healthy retest) → Invalidation
        utr = {}

        # ── Raw metrics used across stages ──
        swing_h = stock.get("swing_high", h52)
        depth = (swing_h - p) / swing_h if swing_h and swing_h > 0 else 0
        depth_pct = round(depth * 100, 2)
        vol_trend = stock.get("utr_vol_trend")        # 10D/50D ADV ratio
        updown_ratio = stock.get("utr_updown_ratio")  # up-day vol / down-day vol
        candle_q = stock.get("utr_candle_quality")     # % closes in upper 40% of range
        dist_days = stock.get("utr_dist_days")         # distribution day count (25d)
        pb_contract = stock.get("utr_pullback_contraction")  # ATR10/ATR20
        test_ma = stock.get("utr_test_ma")             # "50D"/"100D"/"150D"/"200D"/None
        test_ma_dist = stock.get("utr_test_ma_dist")   # % distance to test MA
        retest_counts = stock.get("utr_retest_counts", {})
        _5d_dec = stock.get("utr_5d_declining", False)
        _10d_dec = stock.get("utr_10d_declining", False)
        _50d_rise = stock.get("utr_50d_rising", False)
        _150d_rise = stock.get("utr_150d_rising", False)

        # ── EARLY tests ──
        # E1: Pullback initiated — depth 3-10% from swing high
        e1 = 0.03 <= depth <= 0.10
        # E2: Short-term MAs rolling, intermediate intact
        e2 = (_5d_dec or _10d_dec) and _50d_rise and _150d_rise
        # E3: Volume declining (health indicator, not a gate)
        e3 = "pass" if (vol_trend is not None and vol_trend < 1.0) else "amber" if (vol_trend is not None and vol_trend <= 1.2) else "fail"
        # E4: Distribution days low (0-1 expected at Early)
        e4 = "pass" if (dist_days is not None and dist_days <= 1) else "amber" if (dist_days is not None and dist_days <= 2) else "fail"

        early_qual = e1 and e2  # E1 + E2 required

        # ── LATE tests ──
        # L1: Depth 8-20% from swing high
        l1 = 0.08 <= depth <= 0.20
        # L2: Price approaching key MA — within 5% of test MA, still above
        l2 = test_ma is not None and test_ma_dist is not None and 0 <= test_ma_dist <= 5.0
        # L3: Volume dried up (confirmed) — 10D/50D < 0.85
        l3 = vol_trend is not None and vol_trend < 0.85
        # L4: Up/down volume ratio > 1.0 (constructive)
        l4 = updown_ratio is not None and updown_ratio > 1.0
        # L5: Range contracting — ATR10/ATR20 < 0.9
        l5 = pb_contract is not None and pb_contract < 0.9
        # L6: Distribution days contained — 0-3
        l6 = dist_days is not None and dist_days <= 3

        late_qual = l1 and l2  # L1 + L2 required (position check)
        late_quality = sum(1 for x in [l3, l4, l5, l6] if x)  # quality score 0-4

        # ── CAPITAL tests ──
        # C1: Price at support MA — within 2% (above or slight undercut)
        c1 = test_ma is not None and test_ma_dist is not None and -2.0 <= test_ma_dist <= 2.0
        # C2: Depth reasonable — below 25%
        c2 = depth < 0.25
        # C3: Volume dried up — 10D/50D < 0.80
        c3 = vol_trend is not None and vol_trend < 0.80
        # C4: Up/down ratio positive — > 1.1
        c4 = updown_ratio is not None and updown_ratio > 1.1
        # C5: Candle quality — >=50% of last 10d close in upper 40% range
        c5 = candle_q is not None and candle_q >= 0.50
        # C6: Distribution days low — 0-2 in last 25d
        c6 = dist_days is not None and dist_days <= 2
        # C7: Range contracted — ATR10/ATR20 < 0.85
        c7 = pb_contract is not None and pb_contract < 0.85
        # C8: RS holding — percentile >= 70
        c8 = rs_pct is not None and rs_pct >= 70

        capital_tests = [c1, c2, c3, c4, c5, c6, c7, c8]
        capital_qual = all(capital_tests)  # ALL must pass
        capital_count = sum(1 for x in capital_tests if x)

        # ── INVALIDATION checks ──
        # Any one kills the pattern
        inv_depth = depth > 0.25
        inv_ma_break = (test_ma is not None and test_ma_dist is not None and test_ma_dist < -5.0)
        inv_dist = dist_days is not None and dist_days >= 6
        inv_rs = rs_pct is not None and rs_pct < 50
        invalidated = inv_depth or inv_ma_break or inv_dist or inv_rs

        # ── Stage determination (lifecycle progression) ──
        if invalidated:
            utr["stage"] = None
        elif capital_qual:
            utr["stage"] = "Capital"
        elif late_qual:
            utr["stage"] = "Late"
        elif early_qual:
            utr["stage"] = "Early"
        else:
            utr["stage"] = None

        # ── Retest count for current test MA (Minervini conviction modifier) ──
        current_retest_num = 0
        if test_ma and test_ma in retest_counts:
            current_retest_num = retest_counts[test_ma]
        # Current retest is the one in progress (not yet completed), so display as N+1
        if test_ma:
            current_retest_num += 1

        # ── Output structure ──
        utr["depth_pct"] = depth_pct
        utr["test_ma"] = test_ma
        utr["test_ma_dist"] = test_ma_dist
        utr["retest_counts"] = retest_counts
        utr["current_retest_num"] = current_retest_num

        # Per-test results for dashboard display (pass/amber/fail per stage context)
        utr["tests"] = {
            "e1_depth": "pass" if e1 else ("amber" if 0.01 <= depth <= 0.12 else "fail"),
            "e2_ma_roll": "pass" if e2 else "fail",
            "e3_vol": e3,
            "e4_dist": e4,
            "l1_depth": "pass" if l1 else ("amber" if 0.05 <= depth <= 0.22 else "fail"),
            "l2_ma_approach": "pass" if l2 else ("amber" if test_ma is not None and test_ma_dist is not None and test_ma_dist <= 8.0 else "fail"),
            "l3_vol_dry": "pass" if l3 else ("amber" if vol_trend is not None and vol_trend < 1.0 else "fail"),
            "l4_updown": "pass" if l4 else ("amber" if updown_ratio is not None and updown_ratio >= 0.8 else "fail"),
            "l5_contraction": "pass" if l5 else ("amber" if pb_contract is not None and pb_contract < 1.05 else "fail"),
            "l6_dist": "pass" if l6 else ("amber" if dist_days is not None and dist_days <= 5 else "fail"),
            "c1_at_ma": "pass" if c1 else "fail",
            "c2_depth": "pass" if c2 else "fail",
            "c3_vol": "pass" if c3 else "fail",
            "c4_updown": "pass" if c4 else "fail",
            "c5_candle": "pass" if c5 else "fail",
            "c6_dist": "pass" if c6 else "fail",
            "c7_contraction": "pass" if c7 else "fail",
            "c8_rs": "pass" if c8 else "fail",
        }
        utr["capital_count"] = capital_count
        utr["late_quality"] = late_quality

        # Invalidation flags for dashboard
        utr["invalidation"] = {
            "depth": inv_depth,
            "ma_break": inv_ma_break,
            "dist": inv_dist,
            "rs": inv_rs,
        }

        # MA direction bools (for dashboard display)
        utr["ma_direction"] = {
            "5d_declining": _5d_dec,
            "10d_declining": _10d_dec,
            "50d_rising": _50d_rise,
            "150d_rising": _150d_rise,
        }

        # Raw metric values for tooltip/detail display
        utr["metrics"] = {
            "vol_trend": vol_trend,
            "updown_ratio": updown_ratio,
            "candle_quality": candle_q,
            "dist_days": dist_days,
            "contraction": pb_contract,
            "rs_percentile": rs_pct,
        }

        # ── Assemble result ───────────────────────────────────────────
        results.append({
            "ticker": ticker,
            "basing_plateau": bp,
            "probing_bet": pb,
            "mm99": mm,
            "vcp": vcp,
            "uptrend_retest": utr,
        })

    return results


# ──────────────────────────────────────────────────────────────────────────
# MD V2 — Master Dashboard Screens (Stages, Indicators, Setups, Tests)
# Authored 12-May-26 per Richard's locked spec.
# Matrix-integrity architecture: every score computed once here, attached to
# each stock's filter-results record. All tabs read from r.md_v2.
# ──────────────────────────────────────────────────────────────────────────

def compute_master_dashboard_screens(prices, filter_results):
    """Compute MD V2 screens for each stock. Mutates filter_results in place
    by adding r['md_v2'] = {...} per stock.

    prices: list of stock dicts from build_prices_json
    filter_results: list of filter-results dicts from compute_all_filters
    """
    # Build lookup
    p_by_ticker = {p["ticker"]: p for p in prices}

    # First pass: compute RS-trend percentile baseline (M=-3 RS values across universe)
    # so we can derive percentile-at-M3 per stock for the trend-comparison tests.
    rs_m3_values = {}
    for p in prices:
        if p.get("rs_at_m3") is not None:
            rs_m3_values[p["ticker"]] = p["rs_at_m3"]
    rs_m3_pcts = compute_rs_percentiles(rs_m3_values) if rs_m3_values else {}

    for fr in filter_results:
        ticker = fr["ticker"]
        p = p_by_ticker.get(ticker)
        if not p:
            fr["md_v2"] = {"_error": "no prices data"}
            continue

        md = {}

        # Convenience accessors
        price = p["price"]
        mas = p["mas"]
        ma20 = mas.get("20D")
        ma50 = mas.get("50D")
        ma150 = mas.get("150D")
        ma200 = mas.get("200D")
        ma200_prev = mas.get("200D_prev")
        ma150_prev = mas.get("150D_prev")
        ma50_prev = mas.get("50D_prev")
        h52 = p["high_52w"]
        l52 = p["low_52w"]
        swing_high = p.get("swing_high", h52)
        rs_pct = p.get("rs_percentile")
        rs_vs_sec = p.get("rs_vs_sector")
        rs_vs_ind = p.get("rs_vs_industry")
        rs_excess_mkt = p.get("rs_excess_market")
        adv_1m_up = p.get("adv_1m_up", 0)
        adv_1m_dn = p.get("adv_1m_dn", 0)
        ma150_mom_rates = p.get("ma150_mom_rates", [None] * 12)
        ma200_mom_rates = p.get("ma200_mom_rates", [None] * 12)
        ma150_samples = p.get("ma150_samples", [None] * 13)
        ma200_samples = p.get("ma200_samples", [None] * 13)
        base_count = p.get("base_count_since_52wl", 0)
        higher_lows = p.get("higher_lows_count", 0)
        lower_lows = p.get("lower_lows_count", 0)
        recent_pullback = p.get("recent_pullback_pct", 0)
        rs_returns = p.get("rs_returns", {}) or {}

        # ── MD-V2-SCREENS-S25-FIX-MARKER: Session 25 accessors ──
        max_pullback_ssh = p.get("max_pullback_since_swing_high")
        days_below_sh = p.get("days_below_swing_high")
        utr_50d_rising = p.get("utr_50d_rising", False)
        utr_150d_rising = p.get("utr_150d_rising", False)
        utr_5d_declining = p.get("utr_5d_declining", False)
        utr_10d_declining = p.get("utr_10d_declining", False)
        utr_vol_trend = p.get("utr_vol_trend")
        utr_updown_ratio = p.get("utr_updown_ratio")
        utr_updown_ratio_5d = p.get("utr_updown_ratio_5d")
        utr_dist_days = p.get("utr_dist_days")
        utr_pullback_contraction = p.get("utr_pullback_contraction")
        utr_test_ma = p.get("utr_test_ma")
        utr_test_ma_dist = p.get("utr_test_ma_dist")
        utr_retest_counts = p.get("utr_retest_counts", {}) or {}
        utr_candle_quality_10d = p.get("utr_candle_quality_10d")
        utr_candle_quality_3d = p.get("utr_candle_quality_3d")
        close_pct_change_today = p.get("close_pct_change_today")
        vcp_contractions = p.get("vcp_contractions", []) or []
        # ── END MD-V2-SCREENS-S25-FIX-MARKER accessors ──

        # ── MD-V2-SCREENS-S26-MARKER: VCP 4-test computation (D-MD-V2-61) ──
        # Shared by both VCP setups. 4 tests, all must pass to qualify.
        def _vcp_tests(contractions):
            n = len(contractions)
            # Test 1: contracting volatility range - strict T1 > T2 > T3 > T4
            t1_narrowing = False
            if n >= 2:
                t1_narrowing = all(
                    contractions[i]["depth"] < contractions[i - 1]["depth"]
                    for i in range(1, n)
                )
            # Test 2: sufficient number of contractions - 2 to 4 inclusive
            t2_count_ok = (2 <= n <= 4)
            # Test 3: positive volume trend - avg vol falls across contractions
            t3_vol_declining = False
            if n >= 2:
                t3_vol_declining = all(
                    contractions[i]["avg_vol"] < contractions[i - 1]["avg_vol"]
                    for i in range(1, n)
                )
            # Test 4: higher lows through the pattern - each low above the prior
            t4_higher_lows = False
            if n >= 2:
                t4_higher_lows = all(
                    contractions[i]["low"] > contractions[i - 1]["low"]
                    for i in range(1, n)
                )
            tests = {
                "t1_narrowing_contractions": bool(t1_narrowing),
                "t2_sufficient_count": bool(t2_count_ok),
                "t3_volume_declining": bool(t3_vol_declining),
                "t4_higher_lows": bool(t4_higher_lows),
            }
            cnt = sum(1 for v in tests.values() if v)
            return tests, cnt
        vcp_tests, vcp_test_count = _vcp_tests(vcp_contractions)
        vcp_qualifies = bool(vcp_test_count == 4)
        # ── END MD-V2-SCREENS-S26-MARKER VCP helper ──

        # ── MD-V2-WAVE4-TEST-VALUES-MARKER: per-pattern numeric test values (D-MD-V2 Wave 4) ──
        # For each md_v2 pattern, build a parallel dict keyed by the SAME
        # test keys as `tests`, carrying the underlying number where one
        # exists or a short label where the test is inherently binary.
        # Computed here, in the same pass, from the same locals that
        # produced the booleans, so value and boolean cannot drift apart.
        def _md_v2_round(x, nd=4):
            try:
                if x is None:
                    return None
                return round(float(x), nd)
            except (TypeError, ValueError):
                return None

        def _md_v2_pct_gap(a, b):
            try:
                if a is None or b is None or b == 0:
                    return None
                return round((float(a) - float(b)) / float(b), 4)
            except (TypeError, ValueError):
                return None

        def _md_v2_vcp_values(vt, contractions):
            n = len(contractions)
            return {
                "t1_narrowing_contractions": (
                    "narrowing" if vt.get("t1_narrowing_contractions") else "not narrowing"),
                "t2_sufficient_count": n,
                "t3_volume_declining": (
                    "declining" if vt.get("t3_volume_declining") else "not declining"),
                "t4_higher_lows": (
                    "higher lows" if vt.get("t4_higher_lows") else "not higher"),
            }
        # ── END MD-V2-WAVE4-TEST-VALUES-MARKER helper ──

        # ──────────────────────────────────────────────────────────────
        # STAGE 1 — Consolidating / Basing
        # MD-V2-S48-S1-PRIOR-DOWNTREND-MARKER (19-May-26, D-MD-V2-116):
        # Added NEW Group 1 "Prior downtrend" — 2 tests for whether 150D / 200D
        # MAs were declining MoM 4-6 months ago. Existing Groups 1-4 renumbered
        # to 2-5. Total tests: 10 (was 8). Gate: at least 1 prior-downtrend test
        # must pass for Plausible+; both must pass for Probable Late.
        # Why: chart evidence (Naturgy / Vaisala / Klepierre / Austevollafood)
        # showed Stage 2 stocks wrongly rated Probable Late S1. Prior-downtrend
        # filters them.
        # ──────────────────────────────────────────────────────────────
        s1 = {"tests": {}, "groups": {}, "count": 0, "rating": "None"}

        # ── NEW Group 1 — Prior downtrend (4-6 months ago) ──────────────
        # ma200_mom_rates / ma150_mom_rates are 12-element arrays:
        # index 0 = oldest (12 mo ago), index 11 = most recent month.
        # 4-6 months ago = indices 6 (6mo), 7 (5mo), 8 (4mo).
        # Test passes if at least 2 of those 3 monthly rates were < 0.
        def _was_declining_4to6mo_ago(rates):
            if len(rates) < 9:
                return False
            candidate_idx = [6, 7, 8]
            vals = [rates[i] for i in candidate_idx if rates[i] is not None]
            if len(vals) < 2:
                return False
            return sum(1 for r in vals if r < 0) >= 2

        s1_t_pd1 = _was_declining_4to6mo_ago(ma150_mom_rates)
        s1_t_pd2 = _was_declining_4to6mo_ago(ma200_mom_rates)
        s1["tests"]["T_PD1_150D_was_declining_4to6mo_ago"] = s1_t_pd1
        s1["tests"]["T_PD2_200D_was_declining_4to6mo_ago"] = s1_t_pd2
        s1["groups"]["g1_prior_downtrend"] = {
            "PD1_150D_was_declining_4to6mo_ago": s1_t_pd1,
            "PD2_200D_was_declining_4to6mo_ago": s1_t_pd2,
        }
        new_count = sum(1 for t in [s1_t_pd1, s1_t_pd2] if t)
        new_both = bool(s1_t_pd1 and s1_t_pd2)

        # ── Group 2 (was 1) — Slowing decline rate ──────────────────────
        def _decline_decelerating(rates):
            """Last 3 MoM rates: d0, d-1, d-2 (most recent first when reversed).
            rates is index 11 (most recent) -> 0 (oldest). We want |d_11| < |d_10| < |d_9|."""
            if len(rates) < 12:
                return False, False
            d0 = rates[11]
            d1 = rates[10]
            d2 = rates[9]
            if d0 is None or d1 is None or d2 is None:
                return False, False
            is_flat_or_rising = d0 >= -0.005
            decelerating = (abs(d0) < abs(d1) < abs(d2)) and d1 < 0 and d2 < 0
            return decelerating, is_flat_or_rising

        s1_t1_decel, s1_t1_flat = _decline_decelerating(ma150_mom_rates)
        s1_t2_decel, s1_t2_flat = _decline_decelerating(ma200_mom_rates)
        s1["tests"]["T1_150D_decel"] = s1_t1_decel
        s1["tests"]["T2_200D_decel"] = s1_t2_decel
        s1["groups"]["g2_slowing_decline"] = {
            "T1_150D_decelerating": s1_t1_decel,
            "T1_150D_flat_or_rising_exception": s1_t1_flat,
            "T2_200D_decelerating": s1_t2_decel,
            "T2_200D_flat_or_rising_exception": s1_t2_flat,
        }

        # ── Group 3 (was 2) — Flat MAs (+/-2% of M-1, M-2, M-3) ────────
        def _ma_flat_3m(samples):
            if len(samples) < 4 or any(samples[-i] is None for i in [1, 2, 3, 4]):
                return False
            m0 = samples[-1]
            for ref in [samples[-2], samples[-3], samples[-4]]:
                if ref == 0 or abs(m0 - ref) / ref > 0.02:
                    return False
            return True

        s1_t3 = _ma_flat_3m(ma150_samples)
        s1_t4 = _ma_flat_3m(ma200_samples)
        s1["tests"]["T3_150D_flat"] = s1_t3
        s1["tests"]["T4_200D_flat"] = s1_t4
        s1["groups"]["g3_flat_mas"] = {"T3": s1_t3, "T4": s1_t4}

        # ── Group 4 (was 3) — Positively stacked MAs ───────────────────
        s1_t5 = (ma50 is not None and ma150 is not None and ma50 > ma150)
        s1_t6 = (ma150 is not None and ma200 is not None and ma150 > ma200)
        s1["tests"]["T5_50_above_150"] = s1_t5
        s1["tests"]["T6_150_above_200"] = s1_t6
        s1["groups"]["g4_stack"] = {"T5": s1_t5, "T6": s1_t6}

        # ── Group 5 (was 4) — Higher lows ──────────────────────────────
        s1_t7 = higher_lows >= 2
        s1_t8 = higher_lows >= 3
        s1["tests"]["T7_higher_lows_1m"] = s1_t7
        s1["tests"]["T8_higher_lows_3m"] = s1_t8
        s1["groups"]["g5_higher_lows"] = {"T7": s1_t7, "T8": s1_t8}

        # ── Composite count (10 tests max, +2 flat-MA bonus retained) ──
        count = new_count  # start with prior-downtrend
        for t in [s1_t1_decel, s1_t2_decel, s1_t3, s1_t4, s1_t5, s1_t6, s1_t7, s1_t8]:
            if t:
                count += 1
        if not s1_t1_decel and s1_t1_flat and s1_t3:
            count += 1
        if not s1_t2_decel and s1_t2_flat and s1_t4:
            count += 1

        s1["count"] = count
        s1["new_group_count"] = new_count
        s1["new_group_both"] = new_both

        # Rating ladder (D-MD-V2-118, 19-May-26):
        # Collapsed Probable Early + Probable Late into single Probable tier
        # per Richard's 17-May definitions and 19-May reaffirmation.
        # Probable: count >= 7 AND both new prior-downtrend tests pass
        # Plausible: count >= 4 AND at least 1 new prior-downtrend test passes
        # Possible: count >= 2 (no gate)
        if new_both and count >= 7:
            s1["rating"] = "Probable"
        elif new_count >= 1 and count >= 4:
            s1["rating"] = "Plausible"
        elif count >= 2:
            s1["rating"] = "Possible"
        else:
            s1["rating"] = "None"
        md["stage_1"] = s1

        # ──────────────────────────────────────────────────────────────
        # STAGE 2 — Uptrend
        # ──────────────────────────────────────────────────────────────
        s2 = {"tests": {}, "groups": {}, "count": 0, "rating": "None"}
        # Group 1 — LT trend
        s2_t1 = (price is not None and ma200 is not None and price > ma200)
        s2_t2 = (ma200 is not None and ma200_prev is not None and ma200 > ma200_prev)
        s2["tests"]["T1_P_above_200D"] = s2_t1
        s2["tests"]["T2_200D_rising_MoM"] = s2_t2
        s2["groups"]["g1_lt_trend"] = {"T1": s2_t1, "T2": s2_t2}

        # Group 2 — MT trend
        s2_t3 = (price is not None and ma150 is not None and price > ma150)
        s2_t4 = (ma150 is not None and ma200 is not None and ma150 > ma200)
        s2["tests"]["T3_P_above_150D"] = s2_t3
        s2["tests"]["T4_150_above_200"] = s2_t4
        s2["groups"]["g2_mt_trend"] = {"T3": s2_t3, "T4": s2_t4}

        # Group 3 — ST trend
        # MD-V2-S47-S2-NEW-CRITERIA-MARKER (18-May-26, D-MD-V2-113):
        # Added T11 (50D>200D), T12 (50D rising d/d), moved to Group 3.
        # T13 (150D rising d/d) added to Group 2 below.
        s2_t5 = (ma50 is not None and ma150 is not None and ma50 > ma150)
        s2_t11 = (ma50 is not None and ma200 is not None and ma50 > ma200)
        s2_t12 = (ma50 is not None and ma50_prev is not None and ma50 > ma50_prev)
        s2["tests"]["T5_50_above_150"] = s2_t5
        s2["tests"]["T11_50_above_200"] = s2_t11
        s2["tests"]["T12_50D_rising"] = s2_t12
        s2["groups"]["g3_st_trend"] = {"T5": s2_t5, "T11": s2_t11, "T12": s2_t12}

        # T13 — 150D MA rising (day-over-day). Logically belongs to Group 2
        # (MT trend) but added here to keep diff localised. Appended to g2.
        s2_t13 = (ma150 is not None and ma150_prev is not None and ma150 > ma150_prev)
        s2["tests"]["T13_150D_rising"] = s2_t13
        s2["groups"]["g2_mt_trend"]["T13"] = s2_t13

        # Group 4 — Price leadership
        s2_t6 = (price is not None and h52 is not None and h52 > 0 and price >= h52 * 0.75)
        s2_t7 = (price is not None and l52 is not None and l52 > 0 and price > l52 * 1.25)
        s2["tests"]["T6_within_25pct_52WH"] = s2_t6
        s2["tests"]["T7_above_25pct_52WL"] = s2_t7
        s2["groups"]["g4_price_leadership"] = {"T6": s2_t6, "T7": s2_t7}

        # Group 5 — Relative strength
        s2_t8 = (rs_vs_sec is not None and rs_vs_sec >= 70)
        s2_t9 = (rs_vs_ind is not None and rs_vs_ind >= 70)
        s2_t10 = (rs_pct is not None and rs_pct >= 70)
        s2["tests"]["T8_RS_vs_sector_70"] = s2_t8
        s2["tests"]["T9_RS_vs_industry_70"] = s2_t9
        s2["tests"]["T10_RS_vs_market_70"] = s2_t10
        s2["groups"]["g5_rs"] = {"T8": s2_t8, "T9": s2_t9, "T10": s2_t10}

        # Composite count — 13 tests (was 10; +T11, +T12, +T13 per D-MD-V2-113)
        s2_count = sum(1 for t in [s2_t1, s2_t2, s2_t3, s2_t4, s2_t5, s2_t6, s2_t7, s2_t8, s2_t9, s2_t10, s2_t11, s2_t12, s2_t13] if t)
        s2["count"] = s2_count
        s2["total"] = 13
        if s2_count >= 12:  # MD-V2-S47B-S2-TIGHTEN-12-OF-13 (19-May-26 audit-hook tighten)
            s2["rating"] = "Probable"
        elif s2_count >= 9:
            s2["rating"] = "Plausible"
        elif s2_count >= 8:
            s2["rating"] = "Possible"
        else:
            s2["rating"] = "None"
        md["stage_2"] = s2

        # ──────────────────────────────────────────────────────────────
        # STAGE 3 — Topping / Invalidated
        # ──────────────────────────────────────────────────────────────
        s3 = {"tests": {}, "groups": {}, "count": 0, "rating": "None"}
        # Group 1 — Base count
        s3_t1 = base_count >= 3
        s3_t2 = base_count >= 4
        s3["tests"]["T1_3_plus_bases"] = s3_t1
        s3["tests"]["T2_4_plus_bases"] = s3_t2
        s3["groups"]["g1_base_count"] = {"T1": s3_t1, "T2": s3_t2}

        # Group 2 — Price trend
        # T3: 200D MA slope flattening — decline rate decelerating, OR going from rising to flat
        # Approximation: 200D MoM rate L3M trending towards 0 from positive (rising MA losing momentum)
        s3_t3 = False
        if len(ma200_mom_rates) >= 3:
            d0 = ma200_mom_rates[-1]
            d1 = ma200_mom_rates[-2]
            d2 = ma200_mom_rates[-3]
            if all(x is not None for x in [d0, d1, d2]):
                # Was rising, now decelerating toward flat
                s3_t3 = d2 > 0.005 and d1 > 0 and d0 < d1 and d0 < d2 and abs(d0) < 0.015
        s3_t4 = (ma50 is not None and ma150 is not None and ma50 < ma150)
        s3["tests"]["T3_200D_flattening"] = s3_t3
        s3["tests"]["T4_50_below_150"] = s3_t4
        s3["groups"]["g2_price_trend"] = {"T3": s3_t3, "T4": s3_t4}

        # Group 3 — Investor debate
        s3_t5 = (adv_1m_dn > 0 and adv_1m_up > 0 and adv_1m_dn >= adv_1m_up * 1.10)
        # Volatility test #6 needs ATR L1M vs prior 3M — approximate using utr_pullback_contraction (ATR10/ATR20)
        s3_t6 = (p.get("utr_pullback_contraction") is not None and p["utr_pullback_contraction"] >= 1.10)
        # MD-V2-S47-S3-PRIOR-UPTREND-MARKER (18-May-26, D-MD-V2-114):
        # T7 tightened: strict price < 50D AND 50D rolling over (was: price <= 50D * 1.05).
        s3_t7 = (price is not None and ma50 is not None and ma50_prev is not None
                 and price < ma50 and ma50 < ma50_prev)
        s3["tests"]["T5_volume_down_up_ratio"] = s3_t5
        s3["tests"]["T6_volatility_increase"] = s3_t6
        s3["tests"]["T7_price_below_50d_and_50d_rolling"] = s3_t7
        s3["groups"]["g3_debate"] = {"T5": s3_t5, "T6": s3_t6, "T7": s3_t7}

        # Group 4 — Lower lows
        s3_t8 = lower_lows >= 2
        s3_t9 = lower_lows >= 3
        s3["tests"]["T8_lower_lows_1m"] = s3_t8
        s3["tests"]["T9_lower_lows_3m"] = s3_t9
        s3["groups"]["g4_lower_lows"] = {"T8": s3_t8, "T9": s3_t9}

        # Group 5 — RS trend (current vs M-3 < 80%)
        # Use rs_returns 3M as proxy for relative RS-now vs RS-then. Negative 3M = weakening.
        s3_t10 = False
        rs_3m = rs_returns.get("3M")
        if rs_3m is not None:
            # Stock vs benchmark return last 3M is weak (< 80% means stock has lost ground)
            # Threshold: rs_3m < -0.05 (lost 5%+ vs benchmark in 3M) = trend weakening
            s3_t10 = rs_3m < -0.05
        s3["tests"]["T10_RS_trend_weakening"] = s3_t10
        s3["groups"]["g5_rs_trend"] = {"T10": s3_t10}

        s3_count = sum(1 for t in [s3_t1, s3_t2, s3_t3, s3_t4, s3_t5, s3_t6, s3_t7, s3_t8, s3_t9, s3_t10] if t)
        s3["count"] = s3_count
        if s3_count >= 6:
            s3["rating"] = "Probable Invalidation"
        elif s3_count >= 4:
            s3["rating"] = "Plausible Invalidation"
        elif s3_count >= 2:
            s3["rating"] = "Possible Topping"
        else:
            s3["rating"] = "None"

        # Prior-uptrend hard precondition (D-MD-V2-114):
        # Stage 3 should only fire if the stock was previously in Stage 2.
        # Proxy: 200D MA was rising 6-7 months ago (ma200_m6 > ma200_m7).
        ma200_m6 = ma200_samples[-7] if len(ma200_samples) >= 7 else None
        ma200_m7 = ma200_samples[-8] if len(ma200_samples) >= 8 else None
        prior_uptrend = bool(ma200_m6 is not None and ma200_m7 is not None and ma200_m6 > ma200_m7)
        if not prior_uptrend:
            s3["rating"] = "None"

        # Display column: prior_uptrend boolean + pct change for Group 1.
        # Dashboard's existing %-vs-yes/no toggle handles the display.
        prior_uptrend_pct = None
        if ma200_m6 is not None and ma200_m7 is not None and ma200_m7 > 0:
            prior_uptrend_pct = round(((ma200_m6 - ma200_m7) / ma200_m7) * 100, 2)
        s3["prior_uptrend"] = prior_uptrend
        s3["test_values"] = {
            "prior_uptrend": prior_uptrend,
            "prior_uptrend_pct": prior_uptrend_pct,
        }

        md["stage_3"] = s3

        # ──────────────────────────────────────────────────────────────
        # STAGE 4 — Decline
        # ──────────────────────────────────────────────────────────────
        # D-MD-V2-115: ensure Stage 3 snapshot cache is loaded for lookback.
        _ensure_stage3_snapshots()
        s4 = {"tests": {}, "groups": {}, "count": 0, "rating": "None"}
        # Group 1 — Price trends
        s4_t1 = (ma200 is not None and ma200_prev is not None and ma200 < ma200_prev)
        # T2: 200D decline accelerating — most recent MoM rate more negative than prior
        s4_t2 = False
        if len(ma200_mom_rates) >= 2 and ma200_mom_rates[-1] is not None and ma200_mom_rates[-2] is not None:
            s4_t2 = ma200_mom_rates[-1] < ma200_mom_rates[-2] < 0
        s4["tests"]["T1_200D_declining"] = s4_t1
        s4["tests"]["T2_200D_decline_accelerating"] = s4_t2
        s4["groups"]["g1_price_trends"] = {"T1": s4_t1, "T2": s4_t2}

        # Group 2 — MA stack
        s4_t3 = (
            price is not None and ma50 is not None and ma150 is not None and ma200 is not None
            and price < ma50 < ma150 < ma200
        )
        s4_t4 = (ma150 is not None and ma200 is not None and ma150 < ma200)
        s4_t5 = (ma50 is not None and ma150 is not None and ma50 < ma150)
        s4["tests"]["T3_total_stack_down"] = s4_t3
        s4["tests"]["T4_150_below_200"] = s4_t4
        s4["tests"]["T5_50_below_150"] = s4_t5
        s4["groups"]["g2_ma_stack"] = {"T3": s4_t3, "T4": s4_t4, "T5": s4_t5}

        # Group 3 — RS
        s4_t6 = (rs_vs_ind is not None and rs_vs_ind < 50) or (rs_pct is not None and rs_pct < 50)
        s4_t7 = (rs_3m is not None and rs_3m < -0.05)
        s4["tests"]["T6_RS_absolute_weak"] = s4_t6
        s4["tests"]["T7_RS_trend_weak"] = s4_t7
        s4["groups"]["g3_rs"] = {"T6": s4_t6, "T7": s4_t7}

        s4_count = sum(1 for t in [s4_t1, s4_t2, s4_t3, s4_t4, s4_t5, s4_t6, s4_t7] if t)
        s4["count"] = s4_count

        # MD-V2-S48-S4-LABEL-MERGE-MARKER (19-May-26, D-MD-V2-117):
        # Merge "Probable" + "Probable (Accelerating)" into a single
        # "Probable" rating. Preserve T2 firing via s4["accelerating"] flag so
        # the dashboard can surface it as a badge or column without changing
        # the headline count. Previously the (Accelerating) sub-label hid 36
        # stocks from the per-tab Probable tile.
        if s4_t1 and s4_t3 and s4_t4 and s4_t5:
            s4["rating"] = "Probable"
            s4["accelerating"] = bool(s4_t2)
        elif s4_t4 and s4_t5:
            s4["rating"] = "Plausible"
            s4["accelerating"] = False
        elif s4_t4 or s4_t5:
            s4["rating"] = "Possible"
            s4["accelerating"] = False
        else:
            s4["rating"] = "None"
            s4["accelerating"] = False

        # Stage-3 lookback INFO column (D-MD-V2-115):
        # Does NOT modify Stage 4 rating — informational only.
        s3_lookback = _stage_3_fired_in_last_60d(ticker, _s47_stage3_snapshots)
        s4["info_stage_3_lookback"] = s3_lookback
        s4["test_values"] = {
            "s3_fired_in_60d": s3_lookback["fired"],
            "s3_days_ago": s3_lookback["days_ago"],
            "s3_history_depth_ok": s3_lookback["history_depth_ok"],
        }

        md["stage_4"] = s4

        # ──────────────────────────────────────────────────────────────
        # 7 INDICATOR PATTERNS (3 pre-test leading + 4 post-test trailing)
        # ──────────────────────────────────────────────────────────────
        ind = {}

        # Pre-test leading indicators
        # MD-V2-SCREENS-S25-FIX-MARKER: Session 25 rewrite. Each pre-test indicator is now an
        # explicit AND of named boolean tests; tests/count/rating emitted in
        # md["pre_indicators"] so the dashboard can render per-pattern
        # rating + score columns (D-MD-V2-55, Option A 3-tier ladder).

        # ---- Indicator 1: Pulling back within MT/LT uptrend (D-MD-V2-50) ----
        # In a real MT/LT uptrend (50D + 150D MAs still rising) AND currently
        # inside a pullback (5D + 10D MAs rolling over). No Stage 2 rating gate.
        pb_t1_50d_rising = bool(utr_50d_rising)
        pb_t2_150d_rising = bool(utr_150d_rising)
        pb_t3_5d_rolling = bool(utr_5d_declining)
        pb_t4_10d_rolling = bool(utr_10d_declining)
        pb_tests = {
            "t1_50d_rising": pb_t1_50d_rising,
            "t2_150d_rising": pb_t2_150d_rising,
            "t3_5d_rolling_over": pb_t3_5d_rolling,
            "t4_10d_rolling_over": pb_t4_10d_rolling,
        }
        pb_count = sum(1 for v in pb_tests.values() if v)
        ind["pulling_back_uptrend"] = bool(pb_count == 4)

        # ---- Indicator 2: Basing (D-MD-V2-49) ----
        # 4 tests: price pullback >=15% (max drawdown since swing high, even if
        # partly reclawed) AND price below swing high >=20 trading days AND
        # price > 200D MA AND 200D MA still rising MoM.
        ba_t1_pullback = bool(max_pullback_ssh is not None and max_pullback_ssh >= 0.15)
        ba_t2_time = bool(days_below_sh is not None and days_below_sh >= 20)
        ba_t3_above_200d = bool(price is not None and ma200 is not None and price > ma200)
        ba_t4_200d_rising = bool(ma200 is not None and ma200_prev is not None and ma200 > ma200_prev)
        ba_tests = {
            "t1_price_pullback_ge15": ba_t1_pullback,
            "t2_time_below_high_ge20d": ba_t2_time,
            "t3_price_above_200d": ba_t3_above_200d,
            "t4_200d_rising": ba_t4_200d_rising,
        }
        ba_count = sum(1 for v in ba_tests.values() if v)
        ind["basing"] = bool(ba_count == 4)
        # Back-compat alias - some downstream code still references basing_below_high
        ind["basing_below_high"] = ind["basing"]

        # ---- Indicator 3: Collapsing (logic unchanged) ----
        # Both: SP 30% below 52WH AND SP fall >=20% from recent high.
        co_t1_30_below_52wh = bool(price is not None and h52 is not None and h52 > 0 and price <= h52 * 0.70)
        co_t2_pullback_ge20 = bool(recent_pullback is not None and recent_pullback >= 0.20)
        co_tests = {
            "t1_price_le_70pct_52wh": co_t1_30_below_52wh,
            "t2_pullback_ge20": co_t2_pullback_ge20,
        }
        co_count = sum(1 for v in co_tests.values() if v)
        ind["collapsing"] = bool(co_count == 2)

        # ---- Per-pattern rating ladder (D-MD-V2-55, Option A 3-tier) ----
        def _pre_rating(count, total):
            """Option A 3-tier ladder scaled to test count.
            0 -> None ; ~1/3 -> Possible ; ~2/3 -> Plausible ; all -> Probable."""
            if count <= 0:
                return "None"
            if count >= total:
                return "Probable"
            frac = count / total
            if frac >= (2.0 / 3.0):
                return "Plausible"
            return "Possible"

        md["pre_indicators"] = {
            # MD-V2-S46-PB-LADDER-MARKER (18-May-26, D-MD-V2-107):
            # Custom rating ladder for pulling_back_uptrend per Richard's spec.
            # 4/4 = Probable; 3/4 = Plausible; 2/4 = Possible; 0-1/4 = None.
            # Raises Possible floor from 1/4 to 2/4 vs the shared _pre_rating
            # function (which still governs the other eight pre-indicators).
            "pulling_back_uptrend": {
                "tests": pb_tests, "count": pb_count, "total": 4,
                "rating": ("Probable" if pb_count >= 4 else "Plausible" if pb_count >= 3 else "Possible" if pb_count >= 2 else "None"),
                "qualifies": ind["pulling_back_uptrend"],
                "test_values": {
                    "t1_50d_rising": "rising" if pb_t1_50d_rising else "not rising",
                    "t2_150d_rising": "rising" if pb_t2_150d_rising else "not rising",
                    "t3_5d_rolling_over": "rolling over" if pb_t3_5d_rolling else "not rolling",
                    "t4_10d_rolling_over": "rolling over" if pb_t4_10d_rolling else "not rolling",
                },
            },
            "basing": {
                "tests": ba_tests, "count": ba_count, "total": 4,
                "rating": _pre_rating(ba_count, 4), "qualifies": ind["basing"],
                "test_values": {
                    "t1_price_pullback_ge15": _md_v2_round(max_pullback_ssh),
                    "t2_time_below_high_ge20d": days_below_sh,
                    "t3_price_above_200d": _md_v2_pct_gap(price, ma200),
                    "t4_200d_rising": _md_v2_pct_gap(ma200, ma200_prev),
                },
            },
            "collapsing": {
                "tests": co_tests, "count": co_count, "total": 2,
                "rating": _pre_rating(co_count, 2), "qualifies": ind["collapsing"],
                "test_values": {
                    "t1_price_le_70pct_52wh": _md_v2_pct_gap(price, h52),
                    "t2_pullback_ge20": _md_v2_round(recent_pullback),
                },
            },
        }

        # Back-compat: keep is_s2_uptrend defined for downstream setup/test logic
        # that still references it (probing_bet, vcp setups, etc).
        is_s2_uptrend = (s2["rating"] in ("Probable", "Plausible"))

        # Post-test trailing indicators
        # MD-V2-SCREENS-S26-MARKER: Session 26 rewrite. Each post-test indicator is
        # now an explicit AND of named boolean tests; tests/count/rating
        # emitted in md["post_indicators"] for PI-parity rendering
        # (D-MD-V2-60). Definitions UNCHANGED - tests surfaced as-is.

        ma5 = mas.get("5D")
        ma20_prev = mas.get("20D_prev")
        adv_10d_up_v = p.get("adv_10d_up", 0) or 0
        adv_10d_dn_v = p.get("adv_10d_dn", 0) or 0
        ma50_prev_v = ma50_prev
        ma150_prev_v = ma150_prev
        ma200_prev_v = ma200_prev
        _price_prev = p.get("price_prev", price)

        # ---- Indicator: Breakout (2 tests) ----
        bo_t1_price = bool(price is not None and ma5 is not None and ma5 > 0 and price > ma5 * 1.08)
        bo_t2_vol = bool(adv_10d_up_v > 0 and adv_10d_dn_v > 0 and adv_10d_up_v >= adv_10d_dn_v * 1.10)
        bo_tests = {"t1_price_gt_108pct_5dma": bo_t1_price, "t2_updown_vol_ge110": bo_t2_vol}
        bo_count = sum(1 for v in bo_tests.values() if v)
        ind["breakout"] = bool(bo_count == 2)

        # ---- Indicator: Advancing (3 tests; t3 hidden from display) ----
        # D-MD-V2-60: 'not in breakout' stays in qualify logic but is NOT
        # a display column (hidden=True). Advancing shows 2 cols, qualifies on 3.
        ad_t1_above_20d = bool(price is not None and ma20 is not None and price > ma20)
        ad_t2_20d_rising = bool(ma20 is not None and ma20_prev is not None and ma20 > ma20_prev)
        ad_t3_not_breakout = bool(not ind["breakout"])
        ad_tests = {
            "t1_price_above_20dma": ad_t1_above_20d,
            "t2_20dma_rising": ad_t2_20d_rising,
            "t3_not_in_breakout": ad_t3_not_breakout,
        }
        ad_count = sum(1 for v in ad_tests.values() if v)
        ind["advancing"] = bool(ad_count == 3)

        # ---- Indicator: Breakdown 50D (2 tests + MA hard gate) ----  MD-V2-S41-BREAKDOWN-MA-HARD-GATE-MARKER
        # S41 (16-May-26, brief #10): MA-precondition HARD GATE on bd_50D_ma_gate
        # = (MA5 > MA50). NOT a counted test — if the gate fails, the indicator
        # is force-filtered (qualifies=False and rating="None" downstream).
        # Filters DIASORIN-class false positives (price nicks above MA from
        # below, falls back, T1+T2 trip without a real prior uptrend).
        ma5_v_bd = mas.get("5D")
        bd50_t1 = bool(price is not None and ma50 is not None and price < ma50)
        bd50_t2 = bool(ma50_prev_v is not None and ma50_prev_v > 0 and _price_prev >= ma50_prev_v * 0.99)
        bd50_ma_gate = bool(ma5_v_bd is not None and ma50 is not None and ma5_v_bd > ma50)
        bd50_tests = {"t1_price_below_50dma": bd50_t1, "t2_prev_at_or_above_50dma": bd50_t2}
        bd50_count = sum(1 for v in bd50_tests.values() if v)
        ind["breakdown_50D"] = bool(bd50_count == 2 and bd50_ma_gate)

        # ---- Indicator: Breakdown 150D (2 tests + MA hard gate) ----
        # S41 (16-May-26, brief #9): MA-precondition HARD GATE on
        # bd_150D_ma_gate = (MA10 > MA150). Same logic at MT timeframe.
        ma10_v_bd = mas.get("10D")
        bd150_t1 = bool(price is not None and ma150 is not None and price < ma150)
        bd150_t2 = bool(ma150_prev_v is not None and ma150_prev_v > 0 and _price_prev >= ma150_prev_v * 0.99)
        bd150_ma_gate = bool(ma10_v_bd is not None and ma150 is not None and ma10_v_bd > ma150)
        bd150_tests = {"t1_price_below_150dma": bd150_t1, "t2_prev_at_or_above_150dma": bd150_t2}
        bd150_count = sum(1 for v in bd150_tests.values() if v)
        ind["breakdown_150D"] = bool(bd150_count == 2 and bd150_ma_gate)

        # ---- Indicator: Breakdown 200D (2 tests + MA hard gate) ----
        # S41 (16-May-26, brief #8): MA-precondition HARD GATE on
        # bd_200D_ma_gate = (MA20 > MA200). THE DIASORIN FIX.
        ma20_v_bd = mas.get("20D")
        bd200_t1 = bool(price is not None and ma200 is not None and price < ma200)
        bd200_t2 = bool(ma200_prev_v is not None and ma200_prev_v > 0 and _price_prev >= ma200_prev_v * 0.99)
        bd200_ma_gate = bool(ma20_v_bd is not None and ma200 is not None and ma20_v_bd > ma200)
        bd200_tests = {"t1_price_below_200dma": bd200_t1, "t2_prev_at_or_above_200dma": bd200_t2}
        bd200_count = sum(1 for v in bd200_tests.values() if v)
        ind["breakdown_200D"] = bool(bd200_count == 2 and bd200_ma_gate)

        md["indicators"] = ind

        # Structured post_indicators for PI-parity rendering (D-MD-V2-60).
        # Advancing total=3 (incl hidden test) but display shows 2 columns.
        md["post_indicators"] = {
            "breakout": {
                "tests": bo_tests, "count": bo_count, "total": 2,
                "rating": _pre_rating(bo_count, 2), "qualifies": ind["breakout"],
                "test_values": {
                    "t1_price_gt_108pct_5dma": _md_v2_pct_gap(price, ma5),
                    "t2_updown_vol_ge110": (_md_v2_round(adv_10d_up_v / adv_10d_dn_v, 3)
                                            if adv_10d_dn_v else None),
                },
            },
            "advancing": {
                "tests": ad_tests, "count": ad_count, "total": 3,
                "rating": _pre_rating(ad_count, 3), "qualifies": ind["advancing"],
                "test_values": {
                    "t1_price_above_20dma": _md_v2_pct_gap(price, ma20),
                    "t2_20dma_rising": _md_v2_pct_gap(ma20, ma20_prev),
                    "t3_not_in_breakout": "not in breakout" if ad_t3_not_breakout else "in breakout",
                },
            },
            "breakdown_50D": {
                "tests": bd50_tests, "count": bd50_count, "total": 2,
                "rating": _pre_rating(bd50_count, 2) if bd50_ma_gate else "None",
                "qualifies": ind["breakdown_50D"],
                "ma_gate": {"name": "ma5_above_ma50", "passes": bd50_ma_gate},
                "test_values": {
                    "t1_price_below_50dma": _md_v2_pct_gap(price, ma50),
                    "t2_prev_at_or_above_50dma": _md_v2_pct_gap(_price_prev, ma50_prev_v),
                    "ma_gate_ma5_above_ma50": _md_v2_pct_gap(ma5_v_bd, ma50),
                },
            },
            "breakdown_150D": {
                "tests": bd150_tests, "count": bd150_count, "total": 2,
                "rating": _pre_rating(bd150_count, 2) if bd150_ma_gate else "None",
                "qualifies": ind["breakdown_150D"],
                "ma_gate": {"name": "ma10_above_ma150", "passes": bd150_ma_gate},
                "test_values": {
                    "t1_price_below_150dma": _md_v2_pct_gap(price, ma150),
                    "t2_prev_at_or_above_150dma": _md_v2_pct_gap(_price_prev, ma150_prev_v),
                    "ma_gate_ma10_above_ma150": _md_v2_pct_gap(ma10_v_bd, ma150),
                },
            },
            "breakdown_200D": {
                "tests": bd200_tests, "count": bd200_count, "total": 2,
                "rating": _pre_rating(bd200_count, 2) if bd200_ma_gate else "None",
                "qualifies": ind["breakdown_200D"],
                "ma_gate": {"name": "ma20_above_ma200", "passes": bd200_ma_gate},
                "test_values": {
                    "t1_price_below_200dma": _md_v2_pct_gap(price, ma200),
                    "t2_prev_at_or_above_200dma": _md_v2_pct_gap(_price_prev, ma200_prev_v),
                    "ma_gate_ma20_above_ma200": _md_v2_pct_gap(ma20_v_bd, ma200),
                },
            },
        }

        # ──────────────────────────────────────────────────────────────
        # 4 SETUPS — capital deployment eligibility
        # ──────────────────────────────────────────────────────────────
        setups = {}

        # MD-V2-SCREENS-S26-MARKER: Session 26 rewrite. All 4 setups decomposed into
        # named test columns + Option A rating ladder (D-MD-V2-62).
        # healthy_retest REPLACES the old utr_after_s2_pullback (built S25).

        # ---- Setup 1: Probing bet (2 tests) - definitions unchanged ----
        s1_qualifying = s1["rating"] in ("Plausible", "Probable Early", "Probable Late")
        s3_qualifying = s3["rating"] in ("Plausible Invalidation", "Probable Invalidation")
        s4_qualifying = s4["rating"] in ("Plausible", "Probable")
        pbs_t1_stage_or_collapsing = bool(s1_qualifying or s3_qualifying or s4_qualifying or ind["collapsing"])
        pbs_t2_breakout = bool(ind["breakout"])
        pbs_tests = {
            "t1_stage_qualifying_or_collapsing": pbs_t1_stage_or_collapsing,
            "t2_breakout": pbs_t2_breakout,
        }
        pbs_count = sum(1 for v in pbs_tests.values() if v)
        setups["probing_bet"] = {
            "tests": pbs_tests, "count": pbs_count, "total": 2,
            "rating": _pre_rating(pbs_count, 2), "qualifies": bool(pbs_count == 2),
            "test_values": {
                "t1_stage_qualifying_or_collapsing": (
                    "qualifying" if pbs_t1_stage_or_collapsing else "not qualifying"),
                "t2_breakout": "breakout" if pbs_t2_breakout else "no breakout",
            },
        }

        # ---- Setup 2: VCP after S1->2 plateau (4 VCP tests + stage gate) ----
        # D-MD-V2-62: uses the new 4-test VCP contraction structure.
        # The stage gate (S1->2 transition) is folded into test 1 alongside
        # the narrowing check so the displayed tests are the 4 VCP tests.
        s1_to_2_transition = (
            s1["rating"] in ("Probable Late", "Probable Early") and
            s2["rating"] in ("Possible", "Plausible")
        )
        vcp_s1_tests = dict(vcp_tests)
        vcp_s1_count = vcp_test_count
        setups["vcp_after_s1_plateau"] = {
            "tests": vcp_s1_tests, "count": vcp_s1_count, "total": 4,
            "rating": _pre_rating(vcp_s1_count, 4),
            "qualifies": bool(vcp_qualifies and s1_to_2_transition),
            "info_stage_gate": bool(s1_to_2_transition),
            "info_contraction_count": len(vcp_contractions),
            "test_values": _md_v2_vcp_values(vcp_tests, vcp_contractions),
        }

        # ---- Setup 3: Healthy retest within MT/LT uptrend (6 tests) ----
        # Built in Session 25 (D-MD-V2-51). Unchanged here.
        hr_t1_vol_contracting = bool(utr_vol_trend is not None and utr_vol_trend < 1.0)
        hr_t2_updown_ge105 = bool(utr_updown_ratio is not None and utr_updown_ratio >= 1.05)
        hr_t3_few_dist_days = bool(utr_dist_days is not None and utr_dist_days <= 3)
        hr_t4_volatility_contracting = bool(utr_pullback_contraction is not None and utr_pullback_contraction < 1.0)
        hr_t5_testing_ma = bool(utr_test_ma is not None)
        hr_t6_buying_l10d = bool(utr_candle_quality_10d is not None and utr_candle_quality_10d >= 0.5)
        hr_tests = {
            "t1_volume_contracting": hr_t1_vol_contracting,
            "t2_updown_vol_ge105": hr_t2_updown_ge105,
            "t3_few_distribution_days": hr_t3_few_dist_days,
            "t4_volatility_contracting": hr_t4_volatility_contracting,
            "t5_testing_meaningful_ma": hr_t5_testing_ma,
            "t6_buying_through_l10d": hr_t6_buying_l10d,
        }
        hr_count = sum(1 for v in hr_tests.values() if v)
        hr_retest_count = utr_retest_counts.get(utr_test_ma) if utr_test_ma else None
        setups["healthy_retest"] = {
            "tests": hr_tests, "count": hr_count, "total": 6,
            "rating": _pre_rating(hr_count, 6),
            "qualifies": bool(hr_count == 6),
            "info_ma_retested": utr_test_ma,
            "info_ma_dist_pct": utr_test_ma_dist,
            "info_retest_count": hr_retest_count,
            "test_values": {
                "t1_volume_contracting": _md_v2_round(utr_vol_trend, 3),
                "t2_updown_vol_ge105": _md_v2_round(utr_updown_ratio, 3),
                "t3_few_distribution_days": utr_dist_days,
                "t4_volatility_contracting": _md_v2_round(utr_pullback_contraction, 3),
                "t5_testing_meaningful_ma": (utr_test_ma if utr_test_ma else "none"),
                "t6_buying_through_l10d": _md_v2_round(utr_candle_quality_10d, 3),
            },
        }
        # Back-compat alias - downstream may still reference utr_after_s2_pullback
        setups["utr_after_s2_pullback"] = setups["healthy_retest"]["qualifies"]

        # ---- Setup 4: VCP after S2 base (4 VCP tests + stage gate) ----
        # D-MD-V2-62: uses the new 4-test VCP contraction structure.
        vcp_s2_tests = dict(vcp_tests)
        vcp_s2_count = vcp_test_count
        _s2_base_gate = bool(is_s2_uptrend and ind["basing"])
        setups["vcp_after_s2_base"] = {
            "tests": vcp_s2_tests, "count": vcp_s2_count, "total": 4,
            "rating": _pre_rating(vcp_s2_count, 4),
            "qualifies": bool(vcp_qualifies and _s2_base_gate),
            "info_stage_gate": _s2_base_gate,
            "info_contraction_count": len(vcp_contractions),
            "test_values": _md_v2_vcp_values(vcp_tests, vcp_contractions),
        }

        md["setups"] = setups

        # ──────────────────────────────────────────────────────────────
        # 3 TESTS — capital qualification/invalidation
        # ──────────────────────────────────────────────────────────────
        # MD-V2-TESTS-S27-MARKER: 4 CAPITAL DEPLOYMENT TESTS (was 3).
        # D-MD-V2-64: the single `vcp` test SPLITS into vcp_deploy_s1 +
        #   vcp_deploy_s2 (stage-gated forms). 4 tests total:
        #     ma_retest_upwards / vcp_deploy_s1 / vcp_deploy_s2 / probing_bet
        # D-MD-V2-65: each test carries its related SETUP's test columns +
        #   the trigger columns ("in totality"). Each VCP test gets its OWN
        #   VCP columns because the stage gates differ.
        # D-MD-V2-67: window fields (fired_l5d/fired_l20d/days_since_fired)
        #   are stamped on later by apply_test_history(); here we only emit
        #   the current-day test structure + `qualifies`.
        tests = {}

        # ---- Test: Upwards moving average retest (ma_retest_upwards) ----
        # Pairs with the Healthy retest setup. D-MD-V2-65 reconcile item 1:
        # the 6 healthy-retest setup columns and ma_retest's own t1/t2 OVERLAP
        # (both test "near a meaningful MA"). We show the UNION, no double
        # count: the 6 healthy-retest columns as the SETUP block, then the
        # MA-reclaim trigger (close above the test MA) + the confirmation as
        # the TRIGGER block. ma_retest t1 ("near a test MA") is folded into
        # the healthy-retest t5 ("testing a meaningful MA") - same condition,
        # shown once.
        _test_ma_period = {"50D": "50D", "100D": "100D", "150D": "150D", "200D": "200D"}.get(utr_test_ma)
        _test_ma_val = mas.get(_test_ma_period) if _test_ma_period else None
        mr_setup_t1_vol_contracting = bool(utr_vol_trend is not None and utr_vol_trend < 1.0)
        mr_setup_t2_updown_ge105 = bool(utr_updown_ratio is not None and utr_updown_ratio >= 1.05)
        mr_setup_t3_few_dist_days = bool(utr_dist_days is not None and utr_dist_days <= 3)
        mr_setup_t4_volatility_contracting = bool(utr_pullback_contraction is not None and utr_pullback_contraction < 1.0)
        mr_setup_t5_testing_ma = bool(utr_test_ma is not None)
        mr_setup_t6_buying_l10d = bool(utr_candle_quality_10d is not None and utr_candle_quality_10d >= 0.5)
        mr_trig_reclaim = bool(price is not None and _test_ma_val is not None and price > _test_ma_val)
        mr_trig_confirmation = bool(close_pct_change_today is not None and close_pct_change_today >= 0.02)
        mr_tests = {
            "s1_volume_contracting": mr_setup_t1_vol_contracting,
            "s2_updown_vol_ge105": mr_setup_t2_updown_ge105,
            "s3_few_distribution_days": mr_setup_t3_few_dist_days,
            "s4_volatility_contracting": mr_setup_t4_volatility_contracting,
            "s5_testing_meaningful_ma": mr_setup_t5_testing_ma,
            "s6_buying_through_l10d": mr_setup_t6_buying_l10d,
            "x1_reclaim_close_above_ma": mr_trig_reclaim,
            "x2_confirmation_close_ge2pct": mr_trig_confirmation,
        }
        mr_count = sum(1 for v in mr_tests.values() if v)
        # qualify logic preserves D-MD-V2-52 intent: setup healthy enough,
        # near+above a test MA, and confirmed.
        mr_qualifies = bool(
            mr_setup_t5_testing_ma and mr_trig_reclaim and mr_trig_confirmation and
            (mr_setup_t1_vol_contracting or mr_setup_t6_buying_l10d)
        )
        tests["ma_retest_upwards"] = {
            "tests": mr_tests, "count": mr_count, "total": 8,
            "rating": _pre_rating(mr_count, 8),
            "qualifies": mr_qualifies,
            "info_ma_retested": utr_test_ma,
            "info_retest_count": (utr_retest_counts.get(utr_test_ma) if utr_test_ma else None),
            "test_values": {
                "s1_volume_contracting": _md_v2_round(utr_vol_trend, 3),
                "s2_updown_vol_ge105": _md_v2_round(utr_updown_ratio, 3),
                "s3_few_distribution_days": utr_dist_days,
                "s4_volatility_contracting": _md_v2_round(utr_pullback_contraction, 3),
                "s5_testing_meaningful_ma": (utr_test_ma if utr_test_ma else "none"),
                "s6_buying_through_l10d": _md_v2_round(utr_candle_quality_10d, 3),
                "x1_reclaim_close_above_ma": _md_v2_pct_gap(price, _test_ma_val),
                "x2_confirmation_close_ge2pct": _md_v2_round(close_pct_change_today),
            },
        }

        # ---- Test: Healthy retest of upwards MA (healthy_retest) ----
        # MD-V2-S46-HEALTHY-RETEST-MARKER (18-May-26, D-MD-V2-108)
        # New "Core MM trade" test per Richard's S46 brief §8.2. Coexists
        # with ma_retest_upwards above during transition; dashboard render
        # is a follow-up patcher. Architecture per D-MD-V2-108:
        #   Group A: Stage 2 hard precondition (D-MD-V2-109)
        #   Group B: pulling-back-uptrend inlined (4 tests, all required)
        #   Group C: 6 healthy-retest setup tests (reuse mr_setup_t1-t6)
        #   Group D: reclaim + confirmation (reuse mr_trig_* above)
        # 13 criteria total. Today's-close confirmation per D-MD-V2-111.
        # v1: criterion 12 (reclaim) uses mr_trig_reclaim ("price > MA now");
        # the 10-day window enhancement is a follow-up patcher (needs new
        # upstream field in uptrend_retest filter).
        hr_stage_qualifies = bool(s2.get("rating") in ("Probable", "Plausible"))
        hr_b1_50d_rising = bool(pb_t1_50d_rising)
        hr_b2_150d_rising = bool(pb_t2_150d_rising)
        hr_b3_5d_declining = bool(pb_t3_5d_rolling)
        hr_b4_10d_declining = bool(pb_t4_10d_rolling)
        hr_tests = {
            "g1_stage_2_qualifies": hr_stage_qualifies,
            "g2_b1_50d_rising": hr_b1_50d_rising,
            "g2_b2_150d_rising": hr_b2_150d_rising,
            "g2_b3_5d_declining": hr_b3_5d_declining,
            "g2_b4_10d_declining": hr_b4_10d_declining,
            "g3_c1_volume_contracting": mr_setup_t1_vol_contracting,
            "g3_c2_up_vol_gt_down_vol": mr_setup_t2_updown_ge105,
            "g3_c3_few_distribution_days": mr_setup_t3_few_dist_days,
            "g3_c4_volatility_reducing": mr_setup_t4_volatility_contracting,
            "g3_c5_testing_meaningful_ma": mr_setup_t5_testing_ma,
            "g3_c6_buying_through_l10d": mr_setup_t6_buying_l10d,
            "g4_d1_reclaimed_ma": mr_trig_reclaim,
            "g4_d2_confirmation_close_ge2pct": mr_trig_confirmation,
        }
        hr_count = sum(1 for v in hr_tests.values() if v)
        _hr_group_b_all = bool(hr_b1_50d_rising and hr_b2_150d_rising and
                               hr_b3_5d_declining and hr_b4_10d_declining)
        _hr_group_c_count = sum([
            1 if mr_setup_t1_vol_contracting else 0,
            1 if mr_setup_t2_updown_ge105 else 0,
            1 if mr_setup_t3_few_dist_days else 0,
            1 if mr_setup_t4_volatility_contracting else 0,
            1 if mr_setup_t5_testing_ma else 0,
            1 if mr_setup_t6_buying_l10d else 0,
        ])
        if not hr_stage_qualifies:
            hr_rating = "None"
        elif not _hr_group_b_all:
            hr_rating = "None"
        elif _hr_group_c_count < 3:
            hr_rating = "Possible"
        elif not mr_trig_reclaim:
            hr_rating = "Plausible"
        elif not mr_trig_confirmation:
            hr_rating = "Probable"
        else:
            hr_rating = "Qualified"
        hr_qualifies = bool(hr_rating == "Qualified")
        tests["healthy_retest"] = {
            "tests": hr_tests, "count": hr_count, "total": 13,
            "rating": hr_rating,
            "qualifies": hr_qualifies,
            "info_ma_retested": utr_test_ma,
            "info_retest_count": (utr_retest_counts.get(utr_test_ma) if utr_test_ma else None),
            "info_window_note": "v1: criterion 12 is 'price > MA now'; 10-day window enhancement deferred to follow-up patcher",
            "test_values": {
                "g1_stage_2_qualifies": (s2.get("rating") if hr_stage_qualifies else "not S2 P/P"),
                "g2_b1_50d_rising": ("rising" if hr_b1_50d_rising else "not rising"),
                "g2_b2_150d_rising": ("rising" if hr_b2_150d_rising else "not rising"),
                "g2_b3_5d_declining": ("declining" if hr_b3_5d_declining else "not declining"),
                "g2_b4_10d_declining": ("declining" if hr_b4_10d_declining else "not declining"),
                "g3_c1_volume_contracting": _md_v2_round(utr_vol_trend, 3),
                "g3_c2_up_vol_gt_down_vol": _md_v2_round(utr_updown_ratio, 3),
                "g3_c3_few_distribution_days": utr_dist_days,
                "g3_c4_volatility_reducing": _md_v2_round(utr_pullback_contraction, 3),
                "g3_c5_testing_meaningful_ma": (utr_test_ma if utr_test_ma else "none"),
                "g3_c6_buying_through_l10d": _md_v2_round(utr_candle_quality_10d, 3),
                "g4_d1_reclaimed_ma": _md_v2_pct_gap(price, _test_ma_val),
                "g4_d2_confirmation_close_ge2pct": _md_v2_round(close_pct_change_today),
            },
        }

        # ---- Test: VCP after Stage 1->2 (vcp_deploy_s1) ----  D-MD-V2-64/65
        # Gate column: Stage 1 rating is Probable Early OR Probable Late.
        # Then the 4 VCP contraction columns (this test's OWN columns) +
        # breakout trigger + confirmation trigger.
        vd1_gate_s1_probable = bool(s1["rating"] in ("Probable Early", "Probable Late"))
        vd1_trig_breakout = bool(ind["breakout"])
        vd1_trig_confirmation = bool(close_pct_change_today is not None and close_pct_change_today >= 0.02)
        vd1_tests = {
            "g1_stage1_probable": vd1_gate_s1_probable,
            "v1_narrowing_contractions": bool(vcp_tests["t1_narrowing_contractions"]),
            "v2_sufficient_count": bool(vcp_tests["t2_sufficient_count"]),
            "v3_volume_declining": bool(vcp_tests["t3_volume_declining"]),
            "v4_higher_lows": bool(vcp_tests["t4_higher_lows"]),
            "x1_breakout": vd1_trig_breakout,
            "x2_confirmation_close_ge2pct": vd1_trig_confirmation,
        }
        vd1_count = sum(1 for v in vd1_tests.values() if v)
        vd1_qualifies = bool(vd1_gate_s1_probable and vcp_qualifies and vd1_trig_breakout and vd1_trig_confirmation)
        tests["vcp_deploy_s1"] = {
            "tests": vd1_tests, "count": vd1_count, "total": 7,
            "rating": _pre_rating(vd1_count, 7),
            "qualifies": vd1_qualifies,
            "info_contraction_count": len(vcp_contractions),
            "test_values": dict({
                "g1_stage1_probable": (s1["rating"] if vd1_gate_s1_probable else "not probable"),
                "x1_breakout": "breakout" if vd1_trig_breakout else "no breakout",
                "x2_confirmation_close_ge2pct": _md_v2_round(close_pct_change_today),
            }, **{("v" + k[1:]): v for k, v in
                  _md_v2_vcp_values(vcp_tests, vcp_contractions).items()}),
        }

        # ---- Test: VCP after Stage 2 base (vcp_deploy_s2) ----  D-MD-V2-64/65
        # Gate column: Stage 2 rating Plausible-or-better AND the Basing
        # pre-test indicator qualifies (the old vcp_after_s2_base logic:
        # is_s2_uptrend AND ind["basing"]). Then 4 VCP columns + breakout +
        # confirmation.
        vd2_gate_s2_basing = bool(is_s2_uptrend and ind["basing"])
        vd2_trig_breakout = bool(ind["breakout"])
        vd2_trig_confirmation = bool(close_pct_change_today is not None and close_pct_change_today >= 0.02)
        vd2_tests = {
            "g1_stage2_basing": vd2_gate_s2_basing,
            "v1_narrowing_contractions": bool(vcp_tests["t1_narrowing_contractions"]),
            "v2_sufficient_count": bool(vcp_tests["t2_sufficient_count"]),
            "v3_volume_declining": bool(vcp_tests["t3_volume_declining"]),
            "v4_higher_lows": bool(vcp_tests["t4_higher_lows"]),
            "x1_breakout": vd2_trig_breakout,
            "x2_confirmation_close_ge2pct": vd2_trig_confirmation,
        }
        vd2_count = sum(1 for v in vd2_tests.values() if v)
        vd2_qualifies = bool(vd2_gate_s2_basing and vcp_qualifies and vd2_trig_breakout and vd2_trig_confirmation)
        tests["vcp_deploy_s2"] = {
            "tests": vd2_tests, "count": vd2_count, "total": 7,
            "rating": _pre_rating(vd2_count, 7),
            "qualifies": vd2_qualifies,
            "info_contraction_count": len(vcp_contractions),
            "test_values": dict({
                "g1_stage2_basing": ("S2 + basing" if vd2_gate_s2_basing else "gate not met"),
                "x1_breakout": "breakout" if vd2_trig_breakout else "no breakout",
                "x2_confirmation_close_ge2pct": _md_v2_round(close_pct_change_today),
            }, **{("v" + k[1:]): v for k, v in
                  _md_v2_vcp_values(vcp_tests, vcp_contractions).items()}),
        }

        # ---- Test: Probing bet (probing_bet) ----  D-MD-V2-64/65
        # 2 probing-bet-setup columns + breakout trigger + confirmation
        # trigger. D-MD-V2-65 reconcile item 3: the probing-bet SETUP's t2 is
        # itself the breakout - so we show breakout ONCE, as the trigger.
        # The setup block here = the stage-qualifying test only. Plus the
        # Collapsing pre-test indicator RATING as an INFO column (info only,
        # NOT in qualify logic).
        pb_stage = fr.get("probing_bet", {}).get("stage")
        pbt_setup_stage = bool(pb_stage in ("Late", "Capital"))
        pbt_trig_breakout = bool(ind["breakout"])
        pbt_trig_confirmation = bool(close_pct_change_today is not None and close_pct_change_today >= 0.02)
        pbt_tests = {
            "s1_pb_stage_late_or_capital": pbt_setup_stage,
            "x1_breakout": pbt_trig_breakout,
            "x2_confirmation_close_ge2pct": pbt_trig_confirmation,
        }
        pbt_count = sum(1 for v in pbt_tests.values() if v)
        pbt_qualifies = bool(pbt_setup_stage and pbt_trig_breakout and pbt_trig_confirmation)
        _collapsing_rec = (md.get("pre_indicators", {}) or {}).get("collapsing", {}) or {}
        tests["probing_bet"] = {
            "tests": pbt_tests, "count": pbt_count, "total": 3,
            "rating": _pre_rating(pbt_count, 3),
            "qualifies": pbt_qualifies,
            "info_pb_stage": pb_stage,
            "info_collapsing_rating": _collapsing_rec.get("rating", "None"),
            "test_values": {
                "s1_pb_stage_late_or_capital": (pb_stage if pb_stage else "none"),
                "x1_breakout": "breakout" if pbt_trig_breakout else "no breakout",
                "x2_confirmation_close_ge2pct": _md_v2_round(close_pct_change_today),
            },
        }

        # Back-compat aliases - downstream / historical readers may still
        # reference the pre-S27 keys. Keep them pointing at sensible values.
        utr_stage = fr.get("uptrend_retest", {}).get("stage")
        tests["uptrend_retest"] = {"stage": utr_stage, "qualifies": mr_qualifies}
        tests["vcp"] = {
            "qualifies": bool(vd1_qualifies or vd2_qualifies),
            "_note": "S27: vcp test split into vcp_deploy_s1 + vcp_deploy_s2; this alias = OR of both.",
        }

        # ---- Tests: Probing bet (S1, S2) + Speculative bet (S3, S4) ----
        # MD-V2-S46-PROBING-SPEC-MARKER (18-May-26, D-MD-V2-108 + D-MD-V2-110)
        # Four stage-parameterised variants of one underlying test per Richard's
        # S46 brief §8.1. Architecture:
        #   Group A: Stage X hard precondition (D-MD-V2-109; variant differs by stage)
        #   Group B: 5D rising + 10D rising (test-internal per Divergence 1 Option A)
        #   Group C: P > 20D + 20D turn (rising now + was falling 5d ago) + today's close +2%
        # 6 criteria. Today's-close confirmation per D-MD-V2-111.
        # PREREQUISITE: requires Patcher C (MD-V2-S46-MAS-5D-LOOKBACK-MARKER)
        # for mas["20D_5d_ago"] / mas["20D_6d_ago"]. Without Patcher C, the
        # 20D turn check reads None and is always False (degrades gracefully;
        # tests still compute but never reach Probable+).
        ps_ma5_now = mas.get("5D")
        ps_ma5_prev = mas.get("5D_prev")
        ps_ma10_now = mas.get("10D")
        ps_ma10_prev = mas.get("10D_prev")
        ps_ma20_now = mas.get("20D")
        ps_ma20_prev = mas.get("20D_prev")
        ps_ma20_5d_ago = mas.get("20D_5d_ago")
        ps_ma20_6d_ago = mas.get("20D_6d_ago")
        ps_b1_5d_rising = bool(ps_ma5_now is not None and ps_ma5_prev is not None and ps_ma5_now > ps_ma5_prev)
        ps_b2_10d_rising = bool(ps_ma10_now is not None and ps_ma10_prev is not None and ps_ma10_now > ps_ma10_prev)
        ps_c1_price_gt_20d = bool(price is not None and ps_ma20_now is not None and price > ps_ma20_now)
        ps_c2_ma20_now_rising = bool(ps_ma20_now is not None and ps_ma20_prev is not None and ps_ma20_now > ps_ma20_prev)
        ps_c2_ma20_was_falling_5d_ago = bool(ps_ma20_5d_ago is not None and ps_ma20_6d_ago is not None and ps_ma20_5d_ago < ps_ma20_6d_ago)
        ps_c2_ma20_turn = bool(ps_c2_ma20_now_rising and ps_c2_ma20_was_falling_5d_ago)
        ps_c3_followthrough = bool(close_pct_change_today is not None and close_pct_change_today >= 0.02)

        def _ps_rating(stage_qualifies):
            if not stage_qualifies:
                return "None"
            if not (ps_b1_5d_rising and ps_b2_10d_rising):
                return "None"
            if ps_c1_price_gt_20d and ps_c2_ma20_turn and ps_c3_followthrough:
                return "Qualified"
            if ps_c1_price_gt_20d and ps_c2_ma20_turn:
                return "Probable"
            # MD-V2-S47C-PS-PLAUSIBLE-TIGHTEN-MARKER (19-May-26): was 'c1 OR c2' for Plausible
            # which was too loose (Plausible counts 200+ across variants). Tightened to require
            # c1 (price above 20D MA) specifically — the actual breakout signal. c2 alone (20D
            # turn without price above) drops to Possible.
            if ps_c1_price_gt_20d:
                return "Plausible"
            return "Possible"

        def _ps_build(stage_qualifies, variant_key, stage_rating_value):
            ps_tests = {
                "g1_stage_qualifies": stage_qualifies,
                "g2_5d_rising": ps_b1_5d_rising,
                "g3_10d_rising": ps_b2_10d_rising,
                "g4_price_gt_20d": ps_c1_price_gt_20d,
                "g5_20d_turn_last_5d": ps_c2_ma20_turn,
                "g6_followthrough_close_ge2pct": ps_c3_followthrough,
            }
            ps_count = sum(1 for v in ps_tests.values() if v)
            ps_rating = _ps_rating(stage_qualifies)
            return {
                "tests": ps_tests, "count": ps_count, "total": 6,
                "rating": ps_rating,
                "qualifies": bool(ps_rating == "Qualified"),
                "info_variant": variant_key,
                "info_stage_rating": stage_rating_value,
                "test_values": {
                    "g1_stage_qualifies": (stage_rating_value if stage_qualifies else "not in stage"),
                    "g2_5d_rising": ("rising" if ps_b1_5d_rising else "not rising"),
                    "g3_10d_rising": ("rising" if ps_b2_10d_rising else "not rising"),
                    "g4_price_gt_20d": _md_v2_pct_gap(price, ps_ma20_now),
                    "g5_20d_turn_last_5d": (
                        "turn (rising now, falling 5d ago)" if ps_c2_ma20_turn
                        else "rising but no recent turn" if ps_c2_ma20_now_rising
                        else "not rising"
                    ),
                    "g6_followthrough_close_ge2pct": _md_v2_round(close_pct_change_today),
                },
            }

        # Stage gates per variant. Stage X must be at any non-None rating
        # (Possible+/Plausible+/Probable+) for the variant to fire.
        _s1_rating_val = s1.get("rating") if isinstance(s1, dict) else None
        _s2_rating_val = s2.get("rating") if isinstance(s2, dict) else None
        _s3_rating_val = s3.get("rating") if isinstance(s3, dict) else None
        _s4_rating_val = s4.get("rating") if isinstance(s4, dict) else None
        # MD-V2-S47C-PS-ENTRY-GATE-TIGHTEN-MARKER (19-May-26): was 'any non-None stage rating' which
        # was too loose (Plausible counts 200+ across variants in broad market). Tightened to require
        # confirmed-stage rating only. Note stage labels differ: Stage 1 uses "Probable Early"/"Probable
        # Late", Stage 3 uses "Probable Invalidation"/"Plausible Invalidation"/"Possible Topping",
        # Stage 4 uses "Probable"/"Probable (Accelerating)"/"Plausible"/"Possible". Substring match
        # on "Probable" or "Plausible" catches the confirmed tier across all four.
        def _rating_confirmed(r):
            if not r or r == "None":
                return False
            return ("Probable" in r) or ("Plausible" in r)
        _s1_in = _rating_confirmed(_s1_rating_val)
        _s2_in = _rating_confirmed(_s2_rating_val)
        _s3_in = _rating_confirmed(_s3_rating_val) or (_s3_rating_val == "Possible Topping")
        _s4_in = _rating_confirmed(_s4_rating_val)

        tests["probing_bet_s1"] = _ps_build(_s1_in, "probing_bet_s1", _s1_rating_val)
        tests["probing_bet_s2"] = _ps_build(_s2_in, "probing_bet_s2", _s2_rating_val)
        tests["speculative_bet_s3"] = _ps_build(_s3_in, "speculative_bet_s3", _s3_rating_val)
        tests["speculative_bet_s4"] = _ps_build(_s4_in, "speculative_bet_s4", _s4_rating_val)

        md["tests"] = tests

        # ──────────────────────────────────────────────────────────────
        # PERSISTENCE — 12-month sparkline data per screen
        # ──────────────────────────────────────────────────────────────
        # Each sparkline is a 12-bool array (oldest first, most recent last)
        # showing whether the screen's rating was ≥ Plausible in that month.
        # FOR V1: we can only compute the LATEST snapshot; full historical
        # backfill requires re-running the screens at historical price slices
        # which is computationally expensive. Mark as V2 enhancement and emit
        # current-snapshot-only persistence placeholder.
        persistence = {
            "stage_1_persistence": [False] * 11 + [s1["rating"] in ("Plausible", "Probable Early", "Probable Late")],
            "stage_2_persistence": [False] * 11 + [s2["rating"] in ("Plausible", "Probable")],
            "stage_3_persistence": [False] * 11 + [s3["rating"] in ("Plausible Invalidation", "Probable Invalidation")],
            "stage_4_persistence": [False] * 11 + [s4["rating"] in ("Plausible", "Probable")],
            "_note": "V1 emits current-month only. Full 12-month backfill is V2 (requires historical re-run).",
        }
        md["persistence"] = persistence

        # Attach
        fr["md_v2"] = md

    return filter_results


# ── Historical Stage Computation (D-MD-DATA-6) ───────────────────────────

def compute_historical_stages(universe, raw_data, benchmark_rows, t0_filter_results=None, offsets=None):
    """Compute filter stages at historical time points by slicing OHLCV data.

    For each offset (trading days back from today), truncates each stock's
    raw OHLCV data at that point, then re-runs build_prices_json +
    compute_all_filters to get stage assignments.

    Args:
        universe: universe dict with stocks list
        raw_data: dict of {yf_ticker: [ohlcv_rows]} (full history)
        benchmark_rows: benchmark OHLCV rows
        t0_filter_results: pre-computed filter results for T-0 (avoids recomputation)
        offsets: list of trading-day offsets, e.g. [1, 5, 22]
                 Default: [1, 5, 22] (1D, 1W, 1M ago)

    Returns:
        dict: {
            "T-0": {ticker: {filter: stage, ...}, ...},
            "T-1": {ticker: {filter: stage, ...}, ...},
            "T-5": {ticker: {filter: stage, ...}, ...},
            "T-22": {ticker: {filter: stage, ...}, ...},
        }
    """
    if offsets is None:
        offsets = [1, 5, 22]

    FILTERS = ["basing_plateau", "probing_bet", "mm99", "vcp", "uptrend_retest"]
    history = {}

    # T-0 (today) — use pre-computed results if available
    if t0_filter_results is not None:
        print("\n── Historical stages: T-0 (today) — using pre-computed ──")
        t0_stages = {}
        for r in t0_filter_results:
            t0_stages[r["ticker"]] = {f: r[f].get("stage") for f in FILTERS}
        history["T-0"] = t0_stages
        print(f"  {len(t0_stages)} stocks (pre-computed)")
    else:
        print("\n── Historical stages: T-0 (today) ──")
        prices_t0 = build_prices_json(universe, raw_data, benchmark_rows)
        filters_t0 = compute_all_filters(prices_t0)
        t0_stages = {}
        for r in filters_t0:
            t0_stages[r["ticker"]] = {f: r[f].get("stage") for f in FILTERS}
        history["T-0"] = t0_stages
        print(f"  {len(t0_stages)} stocks processed")

    # T-N for each offset
    for offset in offsets:
        label = f"T-{offset}"
        print(f"\n── Historical stages: {label} ({offset} trading days back) ──")

        # Slice raw_data: remove the last `offset` trading days from each ticker
        sliced_data = {}
        skipped = 0
        for yf_ticker, rows in raw_data.items():
            if len(rows) > offset:
                sliced_data[yf_ticker] = rows[:-offset]
            else:
                skipped += 1
                # Not enough data — skip this ticker at this offset

        # Slice benchmark too
        sliced_bench = benchmark_rows[:-offset] if len(benchmark_rows) > offset else []

        if skipped:
            print(f"  Skipped {skipped} tickers (insufficient data for {offset}-day lookback)")

        # Re-run full pipeline on sliced data
        prices_tn = build_prices_json(universe, sliced_data, sliced_bench)
        filters_tn = compute_all_filters(prices_tn)

        tn_stages = {}
        for r in filters_tn:
            tn_stages[r["ticker"]] = {f: r[f].get("stage") for f in FILTERS}
        history[label] = tn_stages
        print(f"  {len(tn_stages)} stocks processed")

    return history


def _extract_change_summary(history, offsets=None):
    """Build per-ticker change records comparing T-0 to each historical point.

    Returns:
        list of dicts: [{ticker, filter, current, previous, offset_label, direction}, ...]
        where direction is 'upgrade' or 'downgrade'.
    """
    if offsets is None:
        offsets = [1, 5, 22]

    FILTERS = ["basing_plateau", "probing_bet", "mm99", "vcp", "uptrend_retest"]
    STAGE_RANK = {None: 0, "Early": 1, "Late": 2, "Capital": 3}

    changes = []
    t0 = history.get("T-0", {})

    for offset in offsets:
        label = f"T-{offset}"
        tn = history.get(label, {})

        for ticker in t0:
            if ticker not in tn:
                continue
            for filt in FILTERS:
                curr = t0[ticker].get(filt)
                prev = tn[ticker].get(filt)
                if curr != prev:
                    curr_rank = STAGE_RANK.get(curr, 0)
                    prev_rank = STAGE_RANK.get(prev, 0)
                    direction = "upgrade" if curr_rank > prev_rank else "downgrade"
                    changes.append({
                        "ticker": ticker,
                        "filter": filt,
                        "current": curr,
                        "previous": prev,
                        "offset": offset,
                        "offset_label": label,
                        "direction": direction,
                    })

    return changes


# -- MD-V2-TESTS-S27-MARKER: persist-and-append test history (D-MD-V2-67) --
#
# Richard's architecture: do NOT recompute the last 20 bars on every run.
# Instead, append today's per-stock per-test `qualifies` booleans to a
# date-keyed history file each run (cost = 1 day). The L5D/L20D window
# fields are then derived from whatever history has accumulated and stamped
# onto each test record so the dashboard reads them via the existing
# s.md_v2.tests[key] path.
#
# The one-off SEED (apply_test_history with seed=N) re-evaluates the 4
# deployment tests at recent historical bar slices to back-create history.
# Per Richard 16-May-26 (S39 T-C, MD-V2-S39-T-C-SEED-DEPTH-20): seed depth
# bumped from 6 to 20 days now that the shake-out phase is done. Run
# --seed-test-history 20 once Windows-side to fully populate; daily pipeline
# appends from there. Format supports up to 20 natively; TEST_HISTORY_MAX_KEEP
# (30 days) gives one week of cushion before the rolling-window trim kicks in.

TEST_HISTORY_PATH = DATA_DIR / "test-history.json"

# The 4 live deployment tests whose qualify-history we persist.
DEPLOYMENT_TEST_KEYS = ["ma_retest_upwards", "vcp_deploy_s1", "vcp_deploy_s2", "probing_bet"]

# Window sizes (trading days). Format supports up to 20; seed depth knob
# bumped to 20 per S39 T-C (Richard 16-May-26). See header comment above.
TEST_HISTORY_WINDOWS = {"l5d": 5, "l20d": 20}
TEST_HISTORY_MAX_KEEP = 30  # cap stored days so the file does not grow unbounded


def _load_test_history():
    """Load data/test-history.json. Shape:
        { "YYYY-MM-DD": { ticker: { test_key: bool, ... }, ... }, ... }
    Returns {} on missing / corrupt."""
    if not TEST_HISTORY_PATH.exists():
        return {}
    try:
        with open(TEST_HISTORY_PATH, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (json.JSONDecodeError, IOError):
        return {}


def _save_test_history(history):
    """Write data/test-history.json, trimmed to the most recent
    TEST_HISTORY_MAX_KEEP dates."""
    dates = sorted(history.keys())
    if len(dates) > TEST_HISTORY_MAX_KEEP:
        for old in dates[:-TEST_HISTORY_MAX_KEEP]:
            del history[old]
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(TEST_HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, separators=(",", ":"))


def _extract_today_test_row(fr):
    """Pull today's per-test `qualifies` booleans out of one filter-results
    record. Returns { test_key: bool }."""
    row = {}
    tests = (fr.get("md_v2", {}) or {}).get("tests", {}) or {}
    for k in DEPLOYMENT_TEST_KEYS:
        rec = tests.get(k)
        if isinstance(rec, dict):
            row[k] = bool(rec.get("qualifies"))
        else:
            row[k] = False
    return row


def _compute_window_fields(ticker, test_key, history):
    """Given the accumulated history (today's row already merged in) work
    out the L5D / L20D window fields for one stock + test.

    Returns dict:
        fired_l5d        : bool  - test qualified at least once in L5D window
        fired_l20d       : bool  - ... in the L20D window
        days_since_fired : int|None - trading-day gap to the most recent
                           fire within the L20D window (0 = fired today)
        history_depth    : int   - how many days of history exist for this
                           ticker+test (drives the dashboard "building" state)
    """
    dates = sorted(history.keys())
    # Ordered (date, fired) for this ticker+test, oldest first. A day where
    # the ticker is absent counts as no-data (does NOT extend depth, is NOT
    # a fail).
    series = []
    for d in dates:
        day = history.get(d, {})
        tk = day.get(ticker)
        if tk is None:
            continue
        if test_key in tk:
            series.append((d, bool(tk[test_key])))
    depth = len(series)
    fired_l5d = False
    fired_l20d = False
    days_since = None
    # index 0 = most recent (today)
    for i, (_, fired) in enumerate(reversed(series)):
        if fired:
            if days_since is None:
                days_since = i
            if i < TEST_HISTORY_WINDOWS["l5d"]:
                fired_l5d = True
            if i < TEST_HISTORY_WINDOWS["l20d"]:
                fired_l20d = True
        if i >= TEST_HISTORY_WINDOWS["l20d"]:
            break
    if days_since is not None and days_since >= TEST_HISTORY_WINDOWS["l20d"]:
        days_since = None
    return {
        "fired_l5d": fired_l5d,
        "fired_l20d": fired_l20d,
        "days_since_fired": days_since,
        "history_depth": depth,
    }


def apply_test_history(filter_results, seed=0, raw_data=None, universe=None,
                       benchmark_rows=None):
    """Persist-and-append test history, then stamp L5D/L20D window fields
    onto each test record in filter_results.

    Daily path (seed=0):
      1. load test-history.json
      2. append today's per-stock per-test `qualifies` row
      3. save test-history.json
      4. compute window fields from accumulated history, write them onto
         each fr["md_v2"]["tests"][key] as fired_l5d / fired_l20d /
         days_since_fired / history_depth

    Seed path (seed=N, one-off):
      Before step 2, back-create up to N historical days by re-evaluating
      the 4 deployment tests at sliced bar endpoints. Requires raw_data +
      universe + benchmark_rows. Per Richard, N is capped at 6 during the
      shake-out phase.
    """
    history = _load_test_history()
    today_str = date.today().strftime("%Y-%m-%d")

    # -- one-off seed: back-create historical days --
    if seed and raw_data is not None and universe is not None:
        print("\n-- Seeding test history: up to %d historical day(s) --" % seed)
        # offsets 1..seed trading days back. Re-run build_prices_json +
        # compute_all_filters + compute_master_dashboard_screens on sliced
        # raw_data (the proven compute_historical_stages pattern), then
        # harvest the 4 deployment tests' `qualifies` per stock. This is the
        # ONLY place the historical recompute happens; the daily path never
        # does it.
        try:
            bench_dates = [r["date"] for r in (benchmark_rows or [])]
            for offset in range(1, seed + 1):
                if benchmark_rows is None or len(benchmark_rows) <= offset:
                    print("  T-%d: insufficient benchmark data - stop" % offset)
                    break
                label_date = bench_dates[-1 - offset] if len(bench_dates) > offset else None
                if label_date is None:
                    break
                if label_date in history:
                    print("  T-%d (%s): already in history - skip" % (offset, label_date))
                    continue
                sliced = {}
                for yf_t, rows in raw_data.items():
                    if len(rows) > offset:
                        sliced[yf_t] = rows[:-offset]
                sliced_bench = benchmark_rows[:-offset] if len(benchmark_rows) > offset else []
                prices_tn = build_prices_json(universe, sliced, sliced_bench)
                filters_tn = compute_all_filters(prices_tn)
                filters_tn = compute_master_dashboard_screens(prices_tn, filters_tn)
                day_row = {}
                for fr in filters_tn:
                    day_row[fr["ticker"]] = _extract_today_test_row(fr)
                history[label_date] = day_row
                print("  T-%d (%s): %d stocks seeded" % (offset, label_date, len(day_row)))
        except Exception as e:
            print("  SEED WARNING: back-creation aborted (%s); continuing with daily append only" % e)

    # -- daily append: today's row --
    today_row = {}
    for fr in filter_results:
        today_row[fr["ticker"]] = _extract_today_test_row(fr)
    history[today_str] = today_row

    _save_test_history(history)
    print("  test-history.json: %d day(s) stored (today = %s, %d stocks)"
          % (len(history), today_str, len(today_row)))

    # -- stamp window fields onto each test record --
    stamped = 0
    for fr in filter_results:
        ticker = fr["ticker"]
        tests = (fr.get("md_v2", {}) or {}).get("tests", {})
        if not isinstance(tests, dict):
            continue
        for k in DEPLOYMENT_TEST_KEYS:
            rec = tests.get(k)
            if not isinstance(rec, dict):
                continue
            win = _compute_window_fields(ticker, k, history)
            rec["fired_l5d"] = win["fired_l5d"]
            rec["fired_l20d"] = win["fired_l20d"]
            rec["days_since_fired"] = win["days_since_fired"]
            rec["history_depth"] = win["history_depth"]
        stamped += 1
    print("  window fields stamped on %d stocks" % stamped)
    return filter_results


# ── Stage 3 lifecycle lookback infrastructure (D-MD-V2-115) ──

def _load_stage3_snapshots():
    """Load Stage 3 lifecycle rating snapshots from data/stage-snapshots.json.

    Returns a dict keyed by date-string, where each value is a dict mapping
    ticker to its Stage 3 lifecycle rating (e.g. "Probable Invalidation",
    "Plausible Invalidation", "Possible Topping", "None", or null if not
    yet recorded). Returns empty dict on any load failure.
    """
    snapshot_path = DATA_DIR / "stage-snapshots.json"
    if not snapshot_path.exists():
        return {}
    try:
        with open(snapshot_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}
    # Extract only the "stage_3_rating" field from each day's per-ticker dict.
    result = {}
    for day_str, tickers in data.items():
        day_ratings = {}
        for tk, fields in tickers.items():
            if isinstance(fields, dict):
                day_ratings[tk] = fields.get("stage_3_rating")
        result[day_str] = day_ratings
    return result


# Module-level cache — loaded once per run, used by all _stage_3_fired_in_last_60d calls.
_s47_stage3_snapshots = None


def _ensure_stage3_snapshots():
    """Lazy-load the Stage 3 snapshot cache exactly once per pipeline run."""
    global _s47_stage3_snapshots
    if _s47_stage3_snapshots is None:
        _s47_stage3_snapshots = _load_stage3_snapshots()
    return _s47_stage3_snapshots


def _stage_3_fired_in_last_60d(ticker, snapshots):
    """Check if ticker had a Stage 3 Probable or Plausible rating in last 60 days.

    Args:
        ticker: stock ticker string
        snapshots: dict from _load_stage3_snapshots()

    Returns:
        dict with three fields:
        - fired (bool): True if any snapshot in the last 60 trading days shows
          this ticker at Stage 3 "Probable Invalidation" or "Plausible Invalidation".
        - days_ago (int or None): number of calendar days since the most recent
          Stage 3 firing, or None if no firing found in the window.
        - history_depth_ok (bool): True if >=10 days of snapshot history exist
          overall. If False, result should display "insufficient history".
    """
    if not snapshots:
        return {"fired": False, "days_ago": None, "history_depth_ok": False}

    sorted_dates = sorted(snapshots.keys(), reverse=True)
    history_depth_ok = len(sorted_dates) >= 10

    today = date.today()
    cutoff = today - timedelta(days=60)
    qualifying_ratings = {"Probable Invalidation", "Plausible Invalidation"}

    fired = False
    days_ago = None

    for day_str in sorted_dates:
        try:
            day_date = datetime.strptime(day_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if day_date < cutoff:
            break  # Past the 60-day window

        rating = snapshots.get(day_str, {}).get(ticker)
        if rating in qualifying_ratings:
            fired = True
            delta = (today - day_date).days
            if days_ago is None or delta < days_ago:
                days_ago = delta

    return {"fired": fired, "days_ago": days_ago, "history_depth_ok": history_depth_ok}


def _save_daily_snapshot(filter_results):
    """Append today's stage assignments to data/stage-snapshots.json.

    This builds up real day-by-day history over time. Each entry is keyed
    by date so re-running on the same day overwrites (idempotent).

    D-MD-V2-115 extension: also persists Stage 3 lifecycle rating
    alongside the existing setup-stage data, enabling the Stage 4
    lookback column.
    """
    FILTERS = ["basing_plateau", "probing_bet", "mm99", "vcp", "uptrend_retest"]
    snapshot_path = DATA_DIR / "stage-snapshots.json"

    # Load existing snapshots
    existing = {}
    if snapshot_path.exists():
        try:
            with open(snapshot_path) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            existing = {}

    # Build today's snapshot
    today = date.today().strftime("%Y-%m-%d")
    today_stages = {}
    for r in filter_results:
        entry = {f: r[f].get("stage") for f in FILTERS}
        # D-MD-V2-115: persist Stage 3 lifecycle rating for lookback
        md_v2 = r.get("md_v2", {})
        s3 = md_v2.get("stage_3", {})
        entry["stage_3_rating"] = s3.get("rating", "None")
        today_stages[r["ticker"]] = entry

    existing[today] = today_stages

    # Write back
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(snapshot_path, "w") as f:
        json.dump(existing, f, separators=(",", ":"))

    print(f"  Daily snapshot saved: {today} ({len(today_stages)} stocks, {len(existing)} total days)")


def main():
    parser = argparse.ArgumentParser(description="Master Dashboard data pipeline")
    parser.add_argument("--sample", action="store_true", help="Use sample data (no yfinance)")
    parser.add_argument("--full-refresh", action="store_true", help="Force full re-pull from yfinance")
    parser.add_argument("--full-universe", action="store_true", help="Use full 976-stock watchlist instead of alpha universe")
    parser.add_argument("--with-history", action="store_true", help="Compute historical stages at T-1/T-5/T-22 for CHANGES tab")
    parser.add_argument("--allow-unmapped", action="store_true", help="Allow watchlist stocks with no canonical taxonomy (default: abort)")
    parser.add_argument("--strict-integrity", action="store_true", help="Abort on any system-integrity audit warning (default: warn-only)")
    parser.add_argument("--seed-test-history", type=int, default=0, metavar="N", help="MD-V2-TESTS-S27-MARKER: one-off - back-create N days of deployment-test history (Richard cap: 20 per S39 T-C, MD-V2-S39-T-C-SEED-DEPTH-20)")
    args = parser.parse_args()

    # ── Advisory: system-integrity audit (cross-file ticker drift) ──
    # Soft warning by default; strict mode aborts.
    print("\n── Pre-flight: system integrity audit ──")
    import subprocess
    integrity_script = SCRIPT_DIR / "audit_system_integrity.py"
    if integrity_script.exists():
        cmd = [sys.executable, str(integrity_script), "--quiet"]
        if args.strict_integrity:
            cmd.append("--strict")
        rc = subprocess.call(cmd)
        if rc == 2:
            print("  System integrity audit reported errors above.")
            if args.strict_integrity:
                print("  --strict-integrity flag set — aborting.")
                sys.exit(1)
            else:
                print("  Continuing in warn-only mode. Re-run with --strict-integrity to enforce.")
        elif rc == 1:
            print("  System integrity audit reported warnings above (non-blocking).")
        else:
            print("  System integrity audit clean.")
    else:
        print(f"  Skipping — audit_system_integrity.py not found at {integrity_script}")

    # Load universe — either alpha (125 stocks) or full watchlist (976 stocks)
    if args.full_universe:
        watchlist_path = SCRIPT_DIR.parent.parent / "databases" / "pullback-watchlist.json"
        if not watchlist_path.exists():
            print(f"ERROR: Watchlist not found at {watchlist_path}")
            sys.exit(1)
        with open(watchlist_path) as f:
            wl = json.load(f)
        universe = {"stocks": wl["stocks"]}
        print(f"Loaded FULL watchlist: {len(universe['stocks'])} stocks")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(UNIVERSE_PATH, "w") as f:
            json.dump(universe, f, indent=2)
        print(f"  Saved as universe.json ({len(universe['stocks'])} stocks)")
    else:
        with open(UNIVERSE_PATH) as f:
            universe = json.load(f)
        print(f"Loaded universe: {len(universe['stocks'])} stocks")

    # ── Canonical taxonomy lookup ──
    sm_path = SCRIPT_DIR.parent.parent / "stock_mapping_final.json"
    sm_map = {}
    if sm_path.exists():
        with open(sm_path) as f:
            sm_raw = json.load(f)
        for tk, td in sm_raw.items():
            if isinstance(td, dict) and td.get("new_industry"):
                sm_map[tk] = {"industry": td["new_industry"], "sector": td["new_sector"]}
        print(f"Loaded canonical taxonomy: {len(sm_map)} tickers from stock_mapping_final.json")
        mapped = 0
        unmapped = []
        for stock in universe["stocks"]:
            tk = stock["ticker"]
            if tk in sm_map:
                stock["industry"] = sm_map[tk]["industry"]
                stock["sector"] = sm_map[tk]["sector"]
                mapped += 1
            else:
                unmapped.append(tk)
        print(f"  Mapped: {mapped} / {len(universe['stocks'])}. Unmapped: {len(unmapped)}")
        if unmapped[:10]:
            print(f"  Unmapped sample: {unmapped[:10]}")
        # ── Build-time validator: every watchlist ticker must have canonical taxonomy ──
        if unmapped and not args.allow_unmapped:
            print()
            print("=" * 60)
            print(f"ERROR: {len(unmapped)} watchlist tickers have no canonical taxonomy.")
            print("       Run audit_taxonomy.py to see details, then either:")
            print("         (a) add entries to stock_mapping_final.json, OR")
            print("         (b) re-run with --allow-unmapped to bypass this check.")
            print()
            print("Unmapped tickers:")
            for tk in unmapped:
                print(f"  - {tk}")
            print("=" * 60)
            sys.exit(1)
    else:
        print(f"WARNING: stock_mapping_final.json not found at {sm_path} — using raw watchlist taxonomy")

    # Fetch data
    # MD-V2-S48-NO-SAMPLE-FALLBACK-MARKER (19-May-26):
    # The silent fallback to sample data is REMOVED. If yfinance fails to
    # import or fetch, the run halts with a clear error so the operator
    # sees the failure instead of shipping synthetic ratings.
    # The --sample flag is preserved for explicit testing only.
    data_source = "sample"
    if args.sample:
        print("\n── Generating sample data (explicit --sample flag) ──")
        raw_data = generate_sample_data(universe)
    else:
        print("\n── Fetching yfinance data ──")
        try:
            raw_data = fetch_all_data(universe, full_refresh=args.full_refresh)
            data_source = "yfinance"
        except ImportError as e:
            raise RuntimeError(
                "yfinance is not installed. Pipeline refuses to fall back to "
                "sample data because that contaminated the dashboard on "
                "19-May-26. Install yfinance ('pip install yfinance --upgrade') "
                "on the machine running this pipeline. To deliberately use "
                "sample data, re-run with --sample. Underlying ImportError: "
                f"{e}"
            )

    # Get benchmark data
    benchmark_rows = raw_data.get(BENCHMARK_TICKER, [])
    if not benchmark_rows:
        print("  WARNING: No benchmark data — RS calculations will be affected")

    # Build prices.json
    print("\n── Building prices.json ──")
    prices = build_prices_json(universe, raw_data, benchmark_rows)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / "prices.json", "w") as f:
        json.dump({
            "_meta": {
                "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "count": len(prices),
                "source": data_source,
            },
            "stocks": prices
        }, f, indent=2)
    print(f"  Written {len(prices)} stocks to data/prices.json")

    # Compute filters
    print("\n── Computing filters ──")
    filter_results = compute_all_filters(prices)
    print("\n── Computing MD V2 screens ──")
    filter_results = compute_master_dashboard_screens(prices, filter_results)
    print(f"  Attached md_v2 to {len(filter_results)} stocks")

    # -- MD-V2-TESTS-S27-MARKER: persist-and-append test history (D-MD-V2-67) --
    print("\n-- Test history (persist-and-append) --")
    filter_results = apply_test_history(
        filter_results,
        seed=args.seed_test_history,
        raw_data=raw_data,
        universe=universe,
        benchmark_rows=benchmark_rows,
    )
    with open(DATA_DIR / "filter-results.json", "w") as f:
        json.dump({
            "_meta": {
                "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "count": len(filter_results),
                "filters": ["basing_plateau", "probing_bet", "mm99", "vcp", "uptrend_retest"],
                "notes": "VCP pattern detection pending Phase 2. UTR V2 lifecycle stages live (27-Apr-26)."
            },
            "stocks": filter_results
        }, f, indent=2)
    print(f"  Written {len(filter_results)} stocks to data/filter-results.json")

    # Daily snapshot — always save (builds up real history for CHANGES tab)
    print("\n── Daily snapshot ──")
    _save_daily_snapshot(filter_results)

    # Summary
    print("\n── Filter Summary ──")
    for filt in ["basing_plateau", "probing_bet", "mm99", "uptrend_retest"]:
        stages = {"Early": 0, "Late": 0, "Capital": 0, "None": 0}
        for r in filter_results:
            stage = r[filt].get("stage") or "None"
            stages[stage] = stages.get(stage, 0) + 1
        print(f"  {filt:20s} — Early: {stages['Early']}, Late: {stages['Late']}, Capital: {stages['Capital']}, None: {stages['None']}")

    # MM99 score distribution
    score_dist = defaultdict(int)
    for r in filter_results:
        score_dist[r["mm99"]["score_8pt"]] += 1
    print(f"  MM99 8pt scores: {dict(sorted(score_dist.items()))}")

    # ── Historical stages for CHANGES tab (D-MD-DATA-6) ──
    if args.with_history:
        print("\n══ HISTORICAL STAGES (--with-history) ══")
        history = compute_historical_stages(universe, raw_data, benchmark_rows,
                                            t0_filter_results=filter_results)
        changes = _extract_change_summary(history)

        # Write filter-history.json — per-ticker stages at each time point
        with open(DATA_DIR / "filter-history.json", "w") as f:
            json.dump({
                "_meta": {
                    "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
                    "offsets": [0, 1, 5, 22],
                    "offset_labels": ["T-0", "T-1", "T-5", "T-22"],
                    "description": "Stage assignments at 4 time points for CHANGES tab",
                },
                "stages": history,
                "changes": changes,
            }, f, indent=2)
        print(f"\n  Written filter-history.json — {len(history)} time points")
        print(f"  Total changes detected: {len(changes)}")

        # Quick summary of changes per offset
        for offset_label in ["T-1", "T-5", "T-22"]:
            offset_changes = [c for c in changes if c["offset_label"] == offset_label]
            ups = sum(1 for c in offset_changes if c["direction"] == "upgrade")
            downs = sum(1 for c in offset_changes if c["direction"] == "downgrade")
            print(f"  {offset_label}: {ups} upgrades, {downs} downgrades")

    print("\nDone.")


if __name__ == "__main__":
    main()
