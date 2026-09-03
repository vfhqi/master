"""
Master Dashboard — Unified Data Pipeline
=========================================
Reads universe.json, fetches OHLCV via yfinance (REAL market data only — no synthetic fallback),
computes 7 SMAs, RS composite, and runs all 5 screening filters.

Outputs:
  data/prices.json         — per-stock price, MAs, volume, 52W stats
  data/filter-results.json — per-stock pass/fail for all 5 filters
  data/rs-data.json        — RS composite + percentile ranks

Usage:
  python generate_master_data.py                 # yfinance with cache
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


def _safe_write_json(obj, out_path, min_bytes=1, validate=None,
                     indent=2, ensure_ascii=True, separators=None):
    """Disk-full/FUSE-hardened atomic JSON write.

    Write to a temp file on the SAME filesystem as the destination, force it to
    physical disk with fsync (so a delayed write-back flush cannot silently
    truncate it, and a full disk raises ENOSPC HERE instead of corrupting the
    file after the process has already reported success), re-read and validate
    it from a fresh on-disk read, atomically rename it into place, then re-read
    and validate the final destination. Raise on any failure. This is the fix
    for the recurring 'Unterminated string' truncation of universe(-master).json
    (root cause: writes reported success, then a delayed flush truncated the
    file on disk; the old verify read the tmp back from page cache, not disk).
    """
    import os, json, tempfile, errno
    out_path = os.fspath(out_path)
    d = os.path.dirname(os.path.abspath(out_path)) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".safe_", suffix=".json", dir=d)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=indent, ensure_ascii=ensure_ascii,
                      separators=separators)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError as e:
                if e.errno == errno.ENOSPC:
                    raise
        if os.path.getsize(tmp) < min_bytes:
            raise IOError("safe-write: temp file too small (%d bytes)"
                          % os.path.getsize(tmp))
        with open(tmp, "r", encoding="utf-8") as f:
            v = json.load(f)
        if validate is not None:
            validate(v)
        os.replace(tmp, out_path)
        tmp = None
    finally:
        if tmp is not None:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    with open(out_path, "r", encoding="utf-8") as f:
        v2 = json.load(f)
    if validate is not None:
        validate(v2)
    return v2


# ── Paths ─────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
CACHE_DIR = PROJECT_DIR / "cache"
UNIVERSE_PATH = DATA_DIR / "universe.json"

# Reuse existing pullback-monitor cache if available
LEGACY_CACHE_DIR = SCRIPT_DIR.parent.parent / "databases" / "pullback-cache"

# Bucket 2 pipeline guards (SA Workstream C, 25-May-26 PM).
# - check_disk_space aborts before heavy writes if free space is too low.
# - verify_output re-reads each big output after write to catch silent truncation.
# Wrapped in safe_guard so a guard BUG never aborts the pipeline; legitimate
# guard trips (DiskSpaceError, OutputVerifyError) still propagate as designed.
try:
    import pipeline_guards as _pg
except Exception as _e:
    _pg = None
    print("[guards] pipeline_guards import failed: {} -- continuing unguarded.".format(_e))
HISTORY_PATH = str(DATA_DIR / ".size-history.json")

LOOKBACK_DAYS = 1650  # ~5.5 years for 200D MA warmup + chart display

# D-MD-COVERAGE-2026-08-04.
# Minimum bars before a stock is emitted to prices.json. Was a hard-coded 200,
# which silently removed Bally's Intralot (140 bars) from every dashboard while
# it sat correctly in universe-master.json, universe.json, the watchlist AND the
# chart files. The 200 protected nothing: every fixed-offset access inside
# build_prices_json is length-guarded, and running the real pipeline
# (build_prices_json -> compute_all_filters -> compute_master_dashboard_screens)
# at a gate of 20 produced correct records with nulls where a window is too
# short, no exceptions and no NaN/inf values. 60 keeps the 20D and 50D averages
# meaningful, which are the shortest target MAs in use, and sits inside a natural
# gap in the data (no stock in the universe has 60-99 bars).
MIN_HISTORY_ROWS = 60

# Bars below which long-window readings (150D/200D, 12M relative strength) are
# not computable. Emitted on the record so a consumer can filter deliberately
# rather than a stock vanishing.
FULL_HISTORY_ROWS = 200

# Rolling full re-seed. A cache can only ever grow FORWARDS: the incremental
# fetch starts at last_date - OVERLAP, so (a) history that appears upstream
# earlier than the cache's first bar is unreachable for ever, and (b) when a
# stock goes ex-dividend the provider re-scales its ENTIRE history while we
# rewrite only the last few days, leaving the cache on two different price
# bases at once. Measured 04-Aug-2026: 6 of 22 randomly sampled caches were
# mixed-basis, understating 12-month relative strength by 1.9 to 6.0
# percentage points, always negative, always worst for dividend payers.
# Re-fetching a deterministic slice each night bounds basis staleness to
# RESEED_CYCLE_DAYS and repairs truncation without anyone noticing it happened.
RESEED_CYCLE_DAYS = 20


def _reseed_ledger_path():
    return DATA_DIR / ".reseed-ledger.json"


def _load_reseed_ledger():
    """{ticker: 'YYYY-MM-DD'} — when each ticker was last SUCCESSFULLY re-fetched in full.

    Replaces the index-position rotation that let ART-ES go twenty consecutive builds without a
    full re-fetch and left its history on a pre-dividend basis (D-PMS-248). A missing entry sorts
    first, so a ticker that has never been re-seeded is always picked before one that has.

    Returns {} on any problem. A missing or unreadable ledger degrades to "everything looks
    equally old", which re-seeds the alphabetically-first slice — wasteful for one night, but it
    can never stop a build or skip a ticker for ever.
    """
    try:
        p = _reseed_ledger_path()
        if not p.exists():
            return {}
        with open(p, encoding="utf-8") as fh:
            d = json.load(fh)
        return {str(k): str(v) for k, v in d.items()} if isinstance(d, dict) else {}
    except Exception as exc:                      # noqa: BLE001 - deliberately total
        print(f"  RE-SEED LEDGER: unreadable, treating every ticker as unseeded ({exc})")
        return {}


def _save_reseed_ledger(ledger, marks, today_str):
    """Record today's SUCCESSFUL re-seeds. Never called when --no-reseed skipped the rotation.

    Only tickers whose re-seed actually landed are marked. A rejected re-seed (`RESEED-REJECT`,
    where the fresh series failed `_reseed_is_safe`) or a failed save must leave the ticker looking
    as old as it really is — otherwise the oldest-first rule would consider it fresh and never come
    back to it, which is exactly the silent-miss failure this replaced.
    """
    if not marks:
        return
    try:
        for label in marks:
            ledger[label] = today_str
        def _v(d):
            assert isinstance(d, dict) and d, "reseed-ledger verify: not a non-empty dict"
        _safe_write_json(ledger, _reseed_ledger_path(), min_bytes=2, validate=_v,
                         indent=None, separators=(",", ":"))
        print(f"  RE-SEED LEDGER: recorded {len(marks)} successful re-seed(s) for {today_str}")
    except Exception as exc:                      # noqa: BLE001 - deliberately total
        # A ledger that fails to save means tonight's work is not recorded, so those tickers are
        # re-seeded again tomorrow. Wasteful, harmless, and must not abort a completed build.
        print(f"  RE-SEED LEDGER: could not be saved, tonight's re-seeds will repeat ({exc})")


def _load_forced_reseeds(path):
    """Tickers to re-fetch in full tonight regardless of the rotation, then clear the request.

    Written by scripts/apm_pms_alignment.py when it finds a stock whose moving averages differ
    between the two price stores, which is the signature of a cache stranded on a stale dividend
    basis. Returns a set of ticker labels; returns an empty set on ANY problem, because a repair
    channel that can break a build is worse than the drift it repairs.

    The file is consumed (deleted) on read. If the underlying basis problem is still there
    tomorrow, tomorrow's alignment run writes it again -- self-limiting rather than self-repeating.
    """
    try:
        if not os.path.exists(path):
            return set()
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        tickers = doc.get("tickers") if isinstance(doc, dict) else doc
        if not isinstance(tickers, list):
            return set()
        out = {str(t) for t in tickers if isinstance(t, str) and t.strip()}
        if len(out) > 200:
            # A request to re-fetch a fifth of the universe is not a repair, it is a symptom of
            # something else being wrong. Refuse it rather than turning one night's build into a
            # multi-hour deep fetch that nobody asked for.
            print(f"  FORCED RE-SEED: REFUSED -- {len(out)} tickers requested, cap is 200. "
                  f"Something upstream is wrong; investigate rather than re-fetching.")
            return set()
        try:
            os.remove(path)
        except OSError:
            pass
        if out:
            print(f"  FORCED RE-SEED: {len(out)} ticker(s) requested by the alignment run "
                  f"(stale dividend basis): {', '.join(sorted(out))}")
        return out
    except Exception as exc:              # noqa: BLE001 - deliberately total
        print(f"  FORCED RE-SEED: skipped, could not read the request file ({exc})")
        return set()
SMA_PERIODS = [5, 10, 20, 50, 100, 150, 200]
BENCHMARK_TICKER = "^STOXX"
# Cached for scripts/pms_historical_performance.py only; NOT the relative-strength
# benchmark, which stays BENCHMARK_TICKER.
BENCHMARK_50_TICKER = "^STOXX50E"


def _updown_note(avg_up, avg_dn, n_rows, label):
    """Explain a null or zero up/down volume ratio instead of leaving it bare.

    Returns None when the ratio is an ordinary number. The three explained cases:
      no down days  -> ratio is undefined, and the reading is maximally BULLISH
      no up days    -> ratio is 0.0, and the reading is maximally BEARISH
      too few rows  -> genuinely insufficient history, the only real 'missing'
    """
    if n_rows < 2:
        return f"{label} up/down volume: insufficient history ({n_rows} bar(s))"
    if avg_dn == 0 and avg_up == 0:
        return f"{label} up/down volume: no volume recorded in the window"
    if avg_dn == 0:
        return (f"{label} up/down volume: NO down-volume days in the window, so the ratio "
                f"is undefined. This is the STRONGEST bullish reading, not missing data.")
    if avg_up == 0:
        return (f"{label} up/down volume: NO up-volume days in the window. The 0.0 is the "
                f"STRONGEST bearish reading, not a neutral one.")
    return None

# ── Cache System (reused from pullback monitor) ──────────────────────────

def _cache_path(yf_ticker, cache_dir=None):
    """Return the cache file path for a yfinance ticker."""
    cd = cache_dir or CACHE_DIR
    safe = yf_ticker.replace("^", "_caret_").replace(".", "_dot_").replace("/", "_slash_")
    return cd / f"{safe}.json"


def load_cache(yf_ticker):
    """Load cached OHLCV rows. Checks project cache first, then legacy.

    Hardened 04-Aug-2026 (D-MD-LEGACY-CACHE). Two problems with the old version,
    both found by running the real main() offline rather than by reading it:

    1. The legacy store `databases/pullback-cache` is a SECOND, STALER copy of
       the same data — 995 files, last bars mostly 31-Jul-2026, and 320 of 400
       sampled carry a NaN close in their final bars. Those are the phantom rows
       the old exclusive-`end=` fetch produced (see FINDING-2026-08-04). Nothing
       declared when the fallback was used, and because the incremental path
       merges whatever load_cache() returns and then save_cache()s it, a NaN
       could be PROMOTED out of the legacy store into the live cache.
    2. No caller could tell which store a series came from.

    So: filter non-finite OHLC rows on read, whatever the source, and announce a
    legacy read with the age of what it served. A fallback must declare itself.
    """
    for _idx, cd in enumerate([CACHE_DIR, LEGACY_CACHE_DIR]):
        path = _cache_path(yf_ticker, cd)
        if not path.exists():
            continue
        try:
            with open(path) as f:
                rows = json.load(f)
        except (json.JSONDecodeError, IOError):
            continue
        if not isinstance(rows, list):
            continue

        def _finite(r):
            for k in ("open", "high", "low", "close"):
                v = r.get(k)
                if not isinstance(v, (int, float)) or math.isnan(v) or math.isinf(v):
                    return False
            return True

        clean = [r for r in rows if isinstance(r, dict) and _finite(r)]
        if len(clean) != len(rows):
            print("  CACHE-CLEAN %-12s — dropped %d row(s) with non-finite OHLC from %s"
                  % (yf_ticker, len(rows) - len(clean),
                     "legacy pullback-cache" if _idx else "project cache"))
        if _idx == 1:
            _last = clean[-1]["date"] if clean else "empty"
            print("  LEGACY-CACHE %-12s — served from databases/pullback-cache, "
                  "last bar %s. This store is not maintained by the nightly build; "
                  "treat its age as unknown." % (yf_ticker, _last))
        return clean or None
    return None


def save_cache(yf_ticker, rows):
    """Save OHLCV rows to project cache.

    Hardened 2026-07-03 (see reference_master_dashboard_cache_truncation_repair.md):
    was a raw open()+json.dump() with no fsync and no verify, so a delayed
    write-back flush (or a FUSE/disk-full interruption) could silently
    truncate or drop the write after this function had already returned
    successfully -- exactly the failure that left master-dashboard/cache/
    (incl. the STOXX benchmark file) stuck on 2026-06-29 data for four
    nights running while the fetch itself kept succeeding. Uses the same
    _safe_write_json() atomic-temp-file + fsync + re-read + verify +
    atomic-rename helper already applied to universe.json on 2026-07-02,
    plus an extra monotonic-last-date check specific to price series: a
    successful write must never leave the cache's last date older than
    it was before the write.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(yf_ticker)

    prev_last_date = None
    if path.exists():
        try:
            with open(path) as f:
                prev_rows = json.load(f)
            if prev_rows:
                prev_last_date = prev_rows[-1].get("date")
        except Exception:
            # Existing file unreadable/corrupt -- don't let that block a
            # good new write; the validator below still protects the new
            # write's own internal consistency.
            prev_last_date = None

    def _validate(v, _ticker=yf_ticker, _prev=prev_last_date):
        assert isinstance(v, list) and len(v) > 0, (
            "save_cache verify failed for %s: result is empty or not a list"
            % _ticker
        )
        last = v[-1]
        assert isinstance(last, dict) and "date" in last and "close" in last, (
            "save_cache verify failed for %s: last row missing date/close"
            % _ticker
        )
        if _prev is not None:
            assert last["date"] >= _prev, (
                "save_cache verify failed for %s: new last date %s is "
                "older than existing cache last date %s -- refusing to "
                "overwrite good data with stale data"
                % (_ticker, last["date"], _prev)
            )

    _safe_write_json(rows, path, min_bytes=1, validate=_validate)


def _merge_cached_and_new(cached_rows, new_rows):
    by_date = {}
    for r in (cached_rows or []):
        by_date[r["date"]] = r
    for r in (new_rows or []):
        by_date[r["date"]] = r
    return sorted(by_date.values(), key=lambda r: r["date"])


def _carry_forward_missing(cached, fresh):
    """Cached bars the provider no longer serves, but ONLY from the point where
    the two series agree on level.

    Yahoo withdraws recently published European sessions (see
    FINDING-2026-08-04), so the cache is sometimes the only copy of a real
    trading day. Those bars must survive a re-seed. Bars from before the
    agreement point must not: they are on the old, pre-adjustment basis and
    carrying them across would rebuild the very discontinuity the re-seed exists
    to remove.
    """
    fm = {r["date"]: r["close"] for r in fresh}
    agree_from = None
    for c in cached:
        f = fm.get(c["date"])
        if f is None or not f:
            continue
        if abs(c["close"] - f) / f <= 0.005:   # same tolerance as _reseed_is_safe
            if agree_from is None:
                agree_from = c["date"]
        else:
            agree_from = None
    if agree_from is None:
        # No agreement region: keep nothing rather than guess. Announce it,
        # because it means a provider-withdrawn bar is being dropped.
        print("  CARRY-FORWARD: no agreement region found — %d cache-only bar(s) "
              "not carried into the re-seeded series" % len(
                  [c for c in cached if c["date"] not in fm]))
        return []
    return [c for c in cached
            if c["date"] not in fm and c["date"] >= agree_from]


def _reseed_is_safe(cached, fresh):
    """Is wholesale replacement of `cached` by `fresh` an improvement?

    Three tests, all on the dates the two series SHARE:
      * level agreement on the most recent shared bars — pins the instrument to
        the right price today;
      * daily-return agreement across the overlap — survives a dividend
        rescaling (which is a constant multiplier on a prefix and so changes the
        return on the ex-date only) while catching a genuinely mis-mapped
        symbol, which disagrees everywhere;
      * flat-run rate — refuses a fresh series that is more stale-patched than
        the cache.

    Levels alone are the wrong test: they legitimately differ across a dividend
    join, which is exactly the drift being repaired.
    """
    if not fresh or not cached:
        return False, "no fresh data returned"
    cm = {r["date"]: r["close"] for r in cached}
    fm = {r["date"]: r["close"] for r in fresh}
    shared = [d for d in (r["date"] for r in fresh) if d in cm]
    if len(shared) < 20:
        return False, "only %d shared bars, too few to prove identity" % len(shared)
    if len(fresh) < len(cached) * 0.9:
        return False, ("fresh series is shorter than the cache (%d vs %d)"
                       % (len(fresh), len(cached)))
    lvl = max(abs(fm[d] - cm[d]) / cm[d] for d in shared[-3:] if cm[d])
    if lvl > 0.005:
        return False, "last shared bars differ by %.2f%% — not the same instrument" % (lvl * 100)
    mism = 0
    for i in range(1, len(shared)):
        d0, d1 = shared[i - 1], shared[i]
        if cm[d0] and fm[d0]:
            if abs((fm[d1] - fm[d0]) / fm[d0] - (cm[d1] - cm[d0]) / cm[d0]) > 0.005:
                mism += 1
    rate = mism / max(1, len(shared) - 1)
    if rate > 0.03:
        return False, ("daily returns disagree on %.1f%% of shared bars" % (rate * 100))

    def _flat(seq):
        return (sum(1 for i in range(1, len(seq)) if seq[i] == seq[i - 1])
                / max(1, len(seq) - 1))
    cflat = _flat([cm[d] for d in shared])
    fflat = _flat([fm[d] for d in shared])
    if fflat > cflat + 0.05:
        return False, ("fresh series is flat-lined on %.1f%% of shared bars against "
                       "%.1f%% in the cache — provider data is degraded"
                       % (fflat * 100, cflat * 100))
    return True, ("identity ok, returns match, flat-run %.1f%% vs %.1f%%"
                  % (fflat * 100, cflat * 100))


# ── yfinance Fetch ────────────────────────────────────────────────────────

# ── SETTLED-BAR GUARD (D-MD-SETTLED-BAR-2026-08-11) ───────────────────────
#
# This REPLACES D-MD-PRICE-FRESH-2026-08-04's two hard-coded heuristics. They are
# deleted rather than left defined, because a dead constant invites reuse:
#
#     LATE_CLOSING_LABEL_SUFFIXES = ("-US",)   # drop today's bar for any -US label
#     EU_MARKETS_CLOSED_HOUR = 17              # ...and for everyone before 17:00 local
#
# Why each had to go:
#
#   * The suffix rule keys on the ticker LABEL, not the clock, so it fired at
#     EVERY hour of the day. A post-US-close pass layered on top of it is a no-op:
#     the bar it waited all evening for is dropped again the moment it arrives.
#     That is the whole reason Richard's original brief -- "run the US price data
#     after the US close so the PMS is right the next morning" -- could not be
#     satisfied by scheduling alone, and why it stayed open for three sessions.
#   * The label is an internal taxonomy tag, not a venue. Flutter traded as
#     FLTR-GB while listed in London and now trades as FLUT-US in New York; for a
#     while the label and the venue disagreed and the rule was simply wrong.
#   * A UK-hour constant is wrong for about three weeks each March and again each
#     late October, when the UK and US daylight-saving switches are out of step
#     and the US close lands at 20:00 UK rather than 21:00.
#
# The replacement asks the VENUE, via scripts/market_session.py. Read that
# module's docstring for the mechanism (`now >= regular.end`, taken from the
# provider's own session window), the cost (one probe per VENUE per run, roughly
# 20 calls for a 987-name universe, not one per ticker) and the live measurement
# that rules out the `regularMarketTime < end` form.
#
# FAILING DIRECTION, unchanged and deliberate: anything that cannot be answered
# drops today's bar. A dropped bar is recovered by the next run's overlap fetch;
# a mid-session bar written as a close is permanent and silently wrong, and the
# Position Management System evaluates stops on closes.

_MS_MODULE = None
_MS_TRIED = False


def _market_session():
    """Import COWORK/scripts/market_session.py once. Returns the module, or None.

    Loaded by path rather than as a package because master-dashboard/scripts is
    not a package and the .bat files run it with their own directory as cwd.
    Same pattern as scripts/check_price_staleness.py.
    """
    global _MS_MODULE, _MS_TRIED
    if _MS_TRIED:
        return _MS_MODULE
    _MS_TRIED = True
    path = SCRIPT_DIR.parent.parent / "scripts" / "market_session.py"
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("_market_session", str(path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _MS_MODULE = mod
        print(f"  SETTLED-BAR: venue guard active (market_session.py from {path})")
    except Exception as e:
        print("  " + "=" * 62)
        print(f"  SETTLED-BAR WARNING: could not import market_session.py ({e}).")
        print(f"    looked for: {path}")
        print("    Falling back to DROPPING today's bar for EVERY ticker, which is")
        print("    the safe direction but leaves every price one day behind until")
        print("    this is fixed. This is loud on purpose.")
        print("  " + "=" * 62)
        _MS_MODULE = None
    return _MS_MODULE


def _unsettled_cut(yf_ticker, rows, today_str):
    """Earliest bar date that is NOT yet settled at this symbol's venue.

    Returns None when every row is settled and nothing should be dropped.

    THE BAR DATE IS PASSED IN, AND THAT IS THE ENTIRE INTEGRATION RISK.

    market_session.should_drop_today() drops UNCONDITIONALLY when it is given no
    bar date. Wired at the OLD call sites -- before the fetch, where no bar date
    can exist -- it would have degraded silently into "always drop": the 04-Aug
    bug wearing a new hat, applied to all 987 names instead of 3, and it would
    have looked like a working guard. So the decision moved INSIDE _fetch_ticker,
    after `rows` is built, where the real last bar date is already in hand. The
    risk is designed out by WHERE the call sits, not merely tested for.
    `selftest_settled_bar()` pins that the bar date actually arrives.
    """
    if not rows:
        return None
    ms = _market_session()
    if ms is None:
        return today_str                      # fail closed
    last_bar = rows[-1]["date"]
    if not ms.should_drop_today(yf_ticker, bar_date=last_bar):
        return None
    sess = ms.session_for(yf_ticker)
    # The venue's own session date, NOT our local "today": at 23:30 UK a US
    # session dated the previous day is still running, and "today" names the
    # wrong day. Fall back to today_str only when the probe gave no session.
    return sess.get("live_date") or today_str


def _period_for_gap(days_gap):
    """Smallest yfinance `period` window that safely spans a cache gap.

    Why `period` and not `start`/`end`: an `end` bound is EXCLUSIVE, so
    `end=today` can never return today's bar. Worse, yfinance then returns the
    live session's bar relabelled with the previous trading day and a NaN close
    (proven 04-Aug-2026 by volume fingerprint: the identical volume 10,831 came
    back labelled 03-Aug under `end=04-Aug` and 04-Aug under `end=05-Aug`).
    The `period=` form returns the current session correctly and is the call
    generate_chart_data.py has run successfully 977 times a night for months.
    The two forms were verified value-identical on every overlapping settled
    day (4 tickers x 9 days, 0 mismatches).
    """
    if days_gap <= 25:
        return "1mo"
    if days_gap <= 80:
        return "3mo"
    if days_gap <= 170:
        return "6mo"
    if days_gap <= 350:
        return "1y"
    if days_gap <= 700:
        return "2y"
    if days_gap <= 1800:
        return "5y"
    return "10y"


def _last_expected_trading_day(now):
    """Most recent weekday on or before `now`, as a date.

    Public holidays are deliberately NOT modelled. Erring towards one extra
    fetch is the safe direction: a wasted call costs a second, a missed session
    can be permanent (Yahoo withdrew 31-Jul-2026 from every continental
    European listing within three days).
    """
    d = now.date()
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def _fetch_ticker(yf, ticker, period, label=None, today_str=None, drop_today=None):
    """Fetch OHLCV for a single ticker from yfinance.

    NaN guard added 2026-07-03 (see ROOT-CAUSE-price-nan-2026-07-03.md): yfinance
    can return a row where Open/High/Low/Close is NaN (a transient exchange-
    settlement data quirk, confirmed on this date concentrated in DE/IT/PT
    listings around 2026-07-01/02, gone on re-fetch). A NaN is a valid Python
    float, so it silently passed every prior "is this a number" check and
    poisoned price/prices.json (NaN is truthy -- `not float('nan')` is False --
    the same failure class already fixed in build_rs_dashboard_data.py earlier
    today). Any row with a NaN OHLC value is dropped here, at the point of
    ingestion, before it can reach the cache or prices.json.
    """
    try:
        t = yf.Ticker(ticker)
        hist = t.history(period=period)
        if len(hist) > 0:
            rows = []
            skipped_nan = 0
            for idx, row in hist.iterrows():
                _o, _h, _l, _c = (float(row["Open"]), float(row["High"]),
                                   float(row["Low"]), float(row["Close"]))
                if any(math.isnan(v) for v in (_o, _h, _l, _c)):
                    skipped_nan += 1
                    continue
                rows.append({
                    "date": idx.strftime("%Y-%m-%d"),
                    "open": round(_o, 4),
                    "high": round(_h, 4),
                    "low": round(_l, 4),
                    "close": round(_c, 4),
                    "volume": int(row["Volume"]),
                })
            if skipped_nan:
                print(f"  NAN-SKIP {ticker:12s} — {skipped_nan} row(s) with NaN OHLC dropped")
            # D-MD-SETTLED-BAR-2026-08-11 (supersedes F3's label/hour rule). A
            # bar from a session that has not closed yet is a mid-session
            # snapshot, not a close, and the PMS evaluates stops on closes.
            # Dropping it is safe: the OVERLAP re-fetch on the next run picks the
            # settled bar up -- and the 22:15 post-US-close pass exists precisely
            # so that "next run" is the SAME EVENING for the US tape, which is
            # what makes the price right in the PMS the next morning.
            #
            # drop_today=None is the default and the production path: ASK THE
            # VENUE. True/False are still honoured so the self-test can pin
            # behaviour without a network call.
            if drop_today is None:
                cut = _unsettled_cut(ticker, rows, today_str)
            else:
                cut = today_str if drop_today else None
            if cut:
                _before = len(rows)
                rows = [r for r in rows if r["date"] < cut]
                if len(rows) < _before:
                    print(f"  UNSETTLED-SKIP {ticker:12s} — dropped {_before - len(rows)} "
                          f"bar(s) dated {cut} or later; {label or ticker}'s venue "
                          f"session had not closed at fetch time")
            return rows
        return []
    except Exception as e:
        print(f"  ERR  {ticker:12s} — {e}")
        return []


def _flag_fetch_failures(failures):
    """Record tickers whose yfinance_ticker IS populated but yfinance still
    returned zero rows on a from-scratch fetch (no cache to fall back on).

    Added 23-Jul-26 as a direct amendment from the Liberty Global / blank-
    yfinance-ticker incident: a stress-test re-check that day found that a
    *correct, verified* mapping (PHNX-GB -> PHNX.L, Phoenix Group Holdings,
    confirmed live via web search to be a normally-traded FTSE 100 stock) can
    still silently vanish from prices.json if the Yahoo/yfinance backend
    itself refuses that one specific symbol (reproduced consistently across
    two separate sessions; quoteSummary 404 + no-timezone error; adjacent GB
    tickers fetched fine in the same call, ruling out a general outage). The
    original blank-ticker guards would never have caught this, because the
    mapping itself is correct -- the failure happens one step later, at
    fetch time. This writes to the SAME needs-attention-yfinance.json file
    the resolver uses, under a distinct reason string, so both failure modes
    (bad mapping vs. bad fetch) surface in one place without being confused
    for each other. Never raises -- must not be allowed to break the run."""
    if not failures:
        return
    try:
        needs_attention_path = SCRIPT_DIR.parent.parent / "databases" / "needs-attention-yfinance.json"
        d = {}
        if needs_attention_path.exists():
            try:
                with open(needs_attention_path, encoding="utf-8") as f:
                    d = json.load(f)
            except Exception:
                d = {}
        now = datetime.now().isoformat() + "Z"
        for label, yf_ticker in failures:
            d[label] = {
                "reason": ("yfinance fetch returned 0 rows for mapped ticker %s "
                           "despite no prior cache -- mapping may be correct but "
                           "the Yahoo/yfinance backend is refusing this symbol; "
                           "re-check manually, do not assume it is delisted "
                           "without independent verification" % yf_ticker),
                "flagged_at": now,
            }
        tmp = str(needs_attention_path) + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2, sort_keys=True)
        os.replace(tmp, needs_attention_path)
    except Exception as e:
        print("WARNING: could not write needs-attention file: %s" % e)


def fetch_all_data(universe, full_refresh=False, no_reseed=False):
    """Fetch OHLCV for all universe stocks + benchmark."""
    import yfinance as yf

    # D-MD-PRICE-FRESH-2026-08-04: record the library version in every run log.
    # yfinance is unpinned on the build machine and its date-window semantics are
    # what this whole path depends on. On 04-Aug-2026 nobody could answer "which
    # version does production run?" from any artefact. Now the log answers it.
    try:
        print(f"  yfinance version: {getattr(yf, '__version__', 'unknown')}")
    except Exception:
        pass

    end_date = datetime.now()
    full_start = end_date - timedelta(days=LOOKBACK_DAYS + 250)
    OVERLAP = 5
    today_str = end_date.strftime("%Y-%m-%d")
    expected_day = _last_expected_trading_day(end_date)

    # D-MD-COVERAGE-2026-08-04 (G1): today's re-seed slice. Deterministic from
    # the ordinal date, so every ticker is fully re-fetched once per cycle
    # regardless of run history, with no state to keep and no drift.
    # OLDEST FIRST, NOT POSITION-IN-FILE (02-Sep-2026, D-PMS-248).
    #
    # The old rule was `i % 20 == date.toordinal() % 20`, where `i` was the stock's INDEX POSITION
    # in universe.json — a file rebuilt from Notion every day. A stock therefore changed bucket
    # whenever names were added, removed or re-sorted above it, so it could be skipped for an
    # unbounded number of cycles with nothing recording the miss. **Measured on ART-ES: twenty
    # consecutive builds, every one incremental, no full re-fetch. Its bucket did come up on
    # 18-Aug and a build did run that day; its index had moved.** Bars before its 13-Apr-2026
    # ex-dividend date kept the old basis, its 200-day average came out 0.42% too high, and a live
    # tranche sitting 0.13% ABOVE its stop was reported 0.29% BELOW it.
    #
    # Now: a ledger records when each ticker was last successfully re-seeded, and each night takes
    # the OLDEST slice. Three properties the rotation did not have:
    #   * self-correcting -- a night missed for any reason leaves a ticker older, so it is picked
    #     sooner rather than skipped for ever;
    #   * bounded -- with the universe divided by the cycle length taken per night, the worst-case
    #     age is one cycle rather than unbounded;
    #   * observable -- the oldest basis in the universe is a number anyone can read off the
    #     ledger, instead of something nobody could see.
    _reseed_ledger = _load_reseed_ledger()
    _reseed_ledger_marks = []
    _all_labels = [s["ticker"] for s in universe["stocks"]]
    _per_night = max(1, -(-len(_all_labels) // RESEED_CYCLE_DAYS))   # ceiling division
    # Never-seeded tickers sort first: the empty string precedes any ISO date.
    _by_age = sorted(_all_labels, key=lambda t: (_reseed_ledger.get(t, ""), t))
    reseed_labels = set(_by_age[:_per_night])
    _oldest = _reseed_ledger.get(_by_age[0], "") if _by_age else ""
    print(f"  RE-SEED LEDGER: {sum(1 for t in _all_labels if t not in _reseed_ledger)} of "
          f"{len(_all_labels)} ticker(s) have never been re-seeded; oldest recorded basis is "
          f"{_oldest or 'none'}")
    # The benchmark is appended to the ticker list AFTER the universe, so an
    # index built off enumerate(universe["stocks"]) never selects it and it would
    # never be re-based. It drives every relative-strength figure in the system,
    # so it gets its own slot in the rotation. (Checked 04-Aug-2026: ^STOXX is a
    # price index with no dividend adjustment, 0.0000% drift over 1,307 shared
    # bars, so this is a hole being closed, not a live defect.)
    # The benchmark drives every relative-strength figure in the system and is appended to the
    # ticker list AFTER the universe, so it was never selected by the old index-based rotation.
    # It now sits in the same ledger as everything else and is re-seeded on its own age.
    if _reseed_ledger.get("BENCHMARK", "") <= _oldest:
        reseed_labels.add("BENCHMARK")
    # FORCED RE-SEEDS, ON TOP OF THE ROTATION (02-Sep-2026).
    #
    # The rotation buckets a stock by its INDEX POSITION in universe.json, and that file is
    # rebuilt from Notion every day. A stock therefore changes bucket whenever names are added,
    # removed or re-sorted above it, so it can be skipped for an unbounded number of cycles with
    # nothing recording that it was missed. Measured on ART-ES: twenty consecutive builds, every
    # one incremental, so bars written before its 13-Apr-2026 ex-dividend date still carried the
    # old unadjusted basis. Its 200-day average came out 0.42% too high, which moved the stop and
    # reported a live tranche as breached when it was not.
    #
    # This list is the repair channel. scripts/apm_pms_alignment.py writes any ticker whose two
    # price stores disagree about a moving average, and the next build re-fetches those tickers in
    # full, which is the only operation that puts a whole history back on one dividend basis.
    # Consumed once and cleared, so a repaired ticker does not re-fetch for ever.
    #
    # FAIL-SAFE BY CONSTRUCTION: any problem reading the file leaves the set untouched and the
    # build behaves exactly as it did before. A repair channel must never be able to stop a build.
    for _forced in _load_forced_reseeds(DATA_DIR / "force-reseed.json"):
        reseed_labels.add(_forced)
    if no_reseed:
        # A second run on the same date would select the same oldest slice and re-fetch
        # five years of history for the same tickers all over again. The 22:15 post-US-close
        # pass is exactly that second run.
        print(f"  RE-SEED: SKIPPED (--no-reseed). {len(reseed_labels)} ticker(s) were "
              f"already re-seeded by today's earlier build; repeating it would double the "
              f"deep-fetch load for no gain. The ledger is NOT touched, so nothing is "
              f"recorded as re-seeded that was not.")
        reseed_labels = set()
    else:
        print(f"  RE-SEED: {len(reseed_labels)} ticker(s) get a full re-fetch tonight, "
              f"chosen OLDEST-BASIS-FIRST over a {RESEED_CYCLE_DAYS}-build cycle "
              f"(bounds dividend-basis drift and repairs truncated caches)")
    # D-MD-SETTLED-BAR-2026-08-11: the "is this session settled?" question is no
    # longer answered here from a UK-hour constant. It is answered per VENUE,
    # inside _fetch_ticker, at the moment the bars are in hand. Warming the probe
    # cache here means the one-probe-per-venue cost is paid visibly, in one place,
    # rather than appearing as scattered latency during the fetch loop.
    _ms_boot = _market_session()
    if _ms_boot is not None:
        print(f"  SETTLED-BAR: build started {end_date:%H:%M} local; each venue is asked "
              f"whether its session has closed, once per venue.")

    tickers = [(s["yfinance_ticker"], s["ticker"]) for s in universe["stocks"]]
    tickers.append((BENCHMARK_TICKER, "BENCHMARK"))
    # 12-Aug-2026: cache the Euro Stoxx 50 too. scripts/pms_historical_performance.py
    # reads Euro Stoxx 600 from this cache but fetched ^STOXX50E LIVE via yfinance at
    # run time -- and that script only ever runs inside the Cowork sandbox, which has
    # no yfinance. So the Euro Stoxx 50 column had never once worked since it was added
    # on 07-Aug; it degraded to a warning every run. Production has yfinance, so caching
    # it here is the fix, and the reader needs no network at all.
    #
    # Deliberately labelled "BENCHMARK", reusing the already-proven non-fatal path: that
    # label is excluded from fetch_failures (so a bad index fetch can never fail the
    # nightly build) and is not in universe["stocks"], so it can never appear as a stock
    # row. The RS benchmark is still keyed on BENCHMARK_TICKER by ticker, not by label,
    # so ^STOXX remains the relative-strength reference and is unaffected.
    tickers.append((BENCHMARK_50_TICKER, "BENCHMARK"))

    data = {}
    stats = {"full": 0, "incr": 0, "cache": 0, "err": 0, "save_err": 0}
    fetch_failures = []

    for yf_ticker, label in tickers:
        cached = None if full_refresh else load_cache(yf_ticker)

        # G1: a re-seeded ticker takes the full path, which REPLACES rather than
        # merges. Merging is what welds two price bases together.
        #
        # But a fresh deep fetch is NOT automatically better than the cache, and
        # a blind nightly replacement would eventually destroy good history.
        # Proven 04-Aug-2026 on TEMN.SW, whose long history from the provider is
        # partly flat-lined: 67 of 321 shared bars repeat the previous close
        # against 4 in our cache. Re-seeding it would have overwritten genuine
        # daily closes with a stale-patched series. So the replacement is gated
        # on _reseed_is_safe() and silently falls back to the incremental path
        # when the fresh series does not clear it.
        _reseed = (label in reseed_labels) and not full_refresh and bool(cached)
        _reseed_rows = None
        if _reseed:
            _reseed_rows = _fetch_ticker(
                yf, yf_ticker, _period_for_gap(LOOKBACK_DAYS + 250), label, today_str)
            _safe, _why = _reseed_is_safe(cached, _reseed_rows)
            if _safe:
                print(f"  RESEED {yf_ticker:12s} — {len(cached)} -> {len(_reseed_rows)} rows "
                      f"({_why})")
                _carried = _carry_forward_missing(cached, _reseed_rows)
                _merged = sorted(_reseed_rows + _carried, key=lambda r: r["date"])
                _cut = (end_date - timedelta(days=LOOKBACK_DAYS + 250)).strftime("%Y-%m-%d")
                _merged = [r for r in _merged if r["date"] >= _cut]
                try:
                    save_cache(yf_ticker, _merged)
                    data[yf_ticker] = _merged
                    stats["reseed"] = stats.get("reseed", 0) + 1
                    # Only a re-seed that actually LANDED counts. A rejected or failed one must
                    # leave the ticker looking as old as it really is, or the oldest-first
                    # rotation would consider it fresh and never come back to it — which is the
                    # same silent-miss failure the rotation was rebuilt to remove.
                    _reseed_ledger_marks.append(label)
                    continue
                except Exception as e:
                    print(f"  RESEED-SAVE-ERR {yf_ticker:12s} — {e} (keeping prior cache)")
            else:
                stats["reseed_rejected"] = stats.get("reseed_rejected", 0) + 1
                print(f"  RESEED-REJECT {yf_ticker:12s} — {_why}; keeping the cached "
                      f"series and falling back to the incremental fetch")

        if cached and not full_refresh:
            last_date = datetime.strptime(cached[-1]["date"], "%Y-%m-%d")
            days_stale = (end_date - last_date).days
            # D-MD-PRICE-FRESH-2026-08-04 (F2): skip ONLY when the cache already
            # holds the last expected trading day. The former `days_stale <= 1`
            # meant "yesterday is good enough", which on every normal weekday
            # skipped the fetch that would have captured today -- and a session
            # not captured on the day can be withdrawn by the provider and lost
            # for good. F2 is not optional alongside F1: without it, F1 cancels
            # itself out from the second night onwards.
            if last_date.date() >= expected_day:
                data[yf_ticker] = cached
                stats["cache"] += 1
                print(f"  CACHE {yf_ticker:12s} — {len(cached)} days (holds {expected_day})")
                continue

            new_rows = _fetch_ticker(yf, yf_ticker,
                                     _period_for_gap(days_stale + OVERLAP),
                                     label, today_str)
            if new_rows:
                merged = _merge_cached_and_new(cached, new_rows)
                cutoff = (end_date - timedelta(days=LOOKBACK_DAYS + 250)).strftime("%Y-%m-%d")
                merged = [r for r in merged if r["date"] >= cutoff]
                try:
                    save_cache(yf_ticker, merged)
                    data[yf_ticker] = merged
                    stats["incr"] += 1
                    print(f"  INCR  {yf_ticker:12s} — {len(new_rows)} new, {len(merged)} total")
                except Exception as e:
                    # save_cache() rejected this write (regressive data,
                    # disk-full, etc.) -- keep the last known-good cache for
                    # this ticker rather than dropping it, and flag loudly.
                    data[yf_ticker] = cached
                    stats["save_err"] += 1
                    print(f"  SAVE-ERR {yf_ticker:12s} — {e} (kept prior {len(cached)}-day cache)")
            else:
                data[yf_ticker] = cached
                stats["cache"] += 1
                print(f"  STALE {yf_ticker:12s} — using {len(cached)}-day cache")
        else:
            new_rows = _fetch_ticker(yf, yf_ticker,
                                     _period_for_gap((end_date - full_start).days),
                                     label, today_str)
            if new_rows:
                _cut = (end_date - timedelta(days=LOOKBACK_DAYS + 250)).strftime("%Y-%m-%d")
                new_rows = [r for r in new_rows if r["date"] >= _cut]
            if new_rows:
                try:
                    save_cache(yf_ticker, new_rows)
                    data[yf_ticker] = new_rows
                    stats["full"] += 1
                    print(f"  FULL  {yf_ticker:12s} — {len(new_rows)} days")
                except Exception as e:
                    stats["save_err"] += 1
                    print(f"  SAVE-ERR {yf_ticker:12s} — {e} (no prior cache to fall back to)")
            else:
                stats["err"] += 1
                print(f"  FAIL  {yf_ticker:12s}")
                if label != "BENCHMARK":
                    fetch_failures.append((label, yf_ticker))

    _ms = _market_session()
    if _ms is not None:
        try:
            _rep = _ms.cache_report()
            if _rep:
                print("\n  SETTLED-BAR: venue verdicts this run (one probe each)")
                print(_rep)
        except Exception as _e:
            print(f"  SETTLED-BAR: venue report unavailable ({_e})")

    _flag_fetch_failures(fetch_failures)
    # Record tonight's SUCCESSFUL re-seeds so tomorrow's oldest-first selection can see them.
    # Deliberately after the whole loop, not inside it: a ticker marked mid-loop by a build that
    # then died would look fresh while its cache was half-written.
    _save_reseed_ledger(_reseed_ledger, _reseed_ledger_marks, today_str)
    print(f"\n  Summary: {stats['full']} full, {stats['incr']} incr, {stats['cache']} cached, "
          f"{stats.get('reseed', 0)} re-seeded, {stats.get('reseed_rejected', 0)} re-seed-rejected, "
          f"{stats['err']} fetch-errors, {stats['save_err']} save-errors\n")

    # D-MD-PRICE-FRESH-2026-08-04: self-check. yfinance is unpinned on the build
    # machine, so this run must prove for itself that the fetch actually reached
    # the current session rather than assume the library behaves as tested.
    _exp = expected_day.isoformat()
    _n_fresh = sum(1 for rows in data.values() if rows and rows[-1]["date"] == _exp)
    _n_tot = max(1, len(data))
    _pct = 100.0 * _n_fresh / _n_tot
    print(f"  FRESHNESS: {_n_fresh}/{_n_tot} tickers carry a {_exp} bar ({_pct:.1f}%)")
    if _pct < 50.0:
        print("  *** FRESHNESS WARNING: fewer than half the universe carries the last")
        print("      expected trading day. The fetch is NOT capturing the current")
        print("      session. Do not trust today's prices, moving averages or stages.")
        print("      See projects/SA - Position Management System/")
        print("      FINDING-2026-08-04-price-path-cannot-capture-the-current-session.md")
    print("")
    return data


# ── Synthetic sample-data generator REMOVED (D-PRICE-INTEGRITY, 22-May-26) ──
# This pipeline only ever emits REAL market data. The old random-OHLCV
# generator was the root cause of the 22-May-26 incident where fabricated
# prices silently overwrote real Yahoo data. It is intentionally gone.


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
    valid = {k: v for k, v in rs_values.items() if v is not None and not math.isnan(v)}
    if not valid:
        return {}
    sorted_items = sorted(valid.items(), key=lambda x: x[1])
    n = len(sorted_items)
    percentiles = {}
    for rank, (ticker, val) in enumerate(sorted_items):
        percentiles[ticker] = int(round(rank / max(n - 1, 1) * 99))
    return percentiles


_PROBE_CACHE = {}


def _load_probe_verdicts():
    """Verdicts from probe_dead_tickers.py, keyed by internal ticker.

    D-MD-COVERAGE-2026-08-04. The Monday probe has been recording which
    unpriced symbols still resolve at the provider, and NOTHING read the file.
    On 03-Aug it was reporting 21 resolvable tickers, five of them absent from
    prices.json, including Bally's Intralot. A detector with no reachable remedy
    is just a slower silence. Reading it here puts the verdict next to the drop.
    Never raises: a missing or malformed probe file must not break the build.
    """
    if _PROBE_CACHE:
        return _PROBE_CACHE.get("verdicts", {})
    verdicts = {}
    try:
        _p = DATA_DIR / "dead-ticker-probe-result.json"
        if _p.exists():
            with open(_p, encoding="utf-8") as _f:
                _d = json.load(_f)
            for _r in _d.get("resolves") or []:
                if isinstance(_r, dict) and _r.get("internal"):
                    verdicts[_r["internal"]] = _r
    except Exception as _e:
        print(f"  NOTE: could not read the dead-ticker probe result: {_e}")
    _PROBE_CACHE["verdicts"] = verdicts
    return verdicts


# ── prices.json Builder ──────────────────────────────────────────────────

# ── MD-S81B-52W-INTEGRITY-MARKER ─────────────────────────────────────────────
# Two distinct faults corrupt the 52-week window. Both were measured across all
# 997 cached series on 11-Aug-26 before these rules were written; neither rule is
# a guess, and the counts below are what the measurement returned.
#
# FAULT 1 — a single absurd intraday tick. The row's own open and close are sound
#   but its low or high is out by roughly 100x. Four rows in the entire cache:
#   EXPN-GB 29-Jul-26 (low 30.34 against a close of 3,077), HSBA-GB 13-Apr-26
#   (low 15.20 against a close of 1,332), VOD-GB 30-Jul-26 (high 12,047 against a
#   close of 119) and the STOXX benchmark 14-May-26 (a low of exactly 0.0).
#   Repaired from the row's OWN open and close, the most conservative source
#   available: the repair can only narrow the range, never invent a wider one.
#
# FAULT 2 — a unit discontinuity. The close series itself steps by about 100x
#   because the listing redenominated or moved venue. Pre-break rows are quoted in
#   a different unit and are NOT comparable with today's price, so they must not
#   contribute to the 52-week extrema. Four series: ROSE-GB (a 100x round trip
#   over one week in Feb-26), AHT-GB and JUST-GB (a step on the final row of a
#   series that then stops), and IDOX (no longer in the universe).
#
#   Where too little post-break history survives to define a 52-week range, emit
#   None rather than a fake one. This matters: a one-row "range" makes price equal
#   the 52-week high, which would let a dead series PASS the Stage 2 "within 25%
#   of the 52-week high" gate. A missing range fails that gate honestly.
#
# Thresholds are deliberately loose so they catch only the impossible: a real
# stock does not halve intraday and close unchanged, nor does it double.

_S81B_TICK_LOW_FRAC  = 0.5   # low below half that row's own close = impossible
_S81B_TICK_HIGH_MULT = 2.0   # high above twice that row's own close = impossible
_S81B_UNIT_BREAK_X   = 20.0  # close-to-close step of 20x or more = a unit change
_S81B_MIN_POST_BREAK = 20    # fewer post-break rows than this = no usable range

# build_prices_json runs four times per pipeline run (today plus the T-1/T-5/T-22
# historical slices for the CHANGES tab), so without this every repair would print
# up to four times and read like the fix was failing to stick. It is not: the repair
# is re-derived in memory on each pass by design. Report each one once per run.
_S81B_REPORTED = set()


def _s81b_repair_ticks(rows):
    """FAULT 1. Repair an absurd low/high from that row's own open and close.

    Mutates in memory only; the on-disk cache keeps the raw vendor record, so the
    repair is re-derived every run and never becomes an unauditable edit.
    Returns a list of (date, field, was, now) for logging.
    """
    fixed = []
    for r in rows:
        o, h, l, c = r.get("open"), r.get("high"), r.get("low"), r.get("close")
        if c is None or c <= 0:
            continue
        ref = [x for x in (o, c) if x is not None and x > 0]
        if not ref:
            continue
        # S81c. The original rule compared the low against the CLOSE alone. Run over
        # the full 1.27m-row history it produced three FALSE POSITIVES on genuine
        # extreme-move days: Atos 28-Nov-24 (opened 14,300, closed 7,814 — a real
        # 45% collapse, so a 17,300 high is legitimate), MFE-B 23-Oct-23 (-80% in a
        # day) and Nanobiotix 5-May-23 (+89% in a day, so a low below half the close
        # is real). Repairing those would have silently flattened real intraday
        # extremes on two universe stocks.
        #
        # Comparing against BOTH open and close removes all three, because open and
        # close are two independent observations of the same session: a genuine
        # extreme sits within a plausible multiple of at least one of them, whereas
        # a corrupt tick is absurd against both.
        lo_ref = min(ref)
        hi_ref = max(ref)
        if l is not None and l < _S81B_TICK_LOW_FRAC * lo_ref:
            fixed.append((r.get("date"), "low", l, lo_ref))
            r["low"] = lo_ref
        if h is not None and h > _S81B_TICK_HIGH_MULT * hi_ref:
            fixed.append((r.get("date"), "high", h, hi_ref))
            r["high"] = hi_ref
    return fixed


def _s81b_last_unit_break(rows):
    """FAULT 2. Index of the row at which the close series LAST stepped by >=20x.

    Returns None when the series is continuous. The last break is the one that
    matters: everything before it is in a superseded unit.
    """
    idx = None
    prev = None
    for i, r in enumerate(rows):
        c = r.get("close")
        if prev and c and (c / prev >= _S81B_UNIT_BREAK_X or prev / c >= _S81B_UNIT_BREAK_X):
            idx = i
        if c:
            prev = c
    return idx


def _s81b_52w_window(lookback, ticker=""):
    """Return (high, low, window_rows, kind) for the 52-week extrema.

    kind is None for a clean series, "excursion" where a temporary off-scale block
    was excluded, or "rebased" where the series stepped and did not come back.
    high and low are None when a rebasing leaves too little comparable history.
    """
    ticks = _s81b_repair_ticks(lookback)
    for d, field, was, now in ticks:
        _key = (ticker, d, field)
        if _key not in _S81B_REPORTED:
            _S81B_REPORTED.add(_key)
            print(f"  52W-TICK-REPAIR {ticker:12s} {d} {field}: {was} -> {now}")
    brk = _s81b_last_unit_break(lookback)
    if brk is None:
        return max(r["high"] for r in lookback), min(r["low"] for r in lookback), lookback, None

    # S81c. Two very different things produce a 100x step, and trimming everything
    # before it is only right for one of them.
    #
    #   EXCURSION — the series wanders off scale and comes back (ROSE-GB spent five
    #     days at 1/100 in Feb-26 and returned). Only those rows are wrong. Trimming
    #     to post-break threw away 131 rows of perfectly good history to fix five.
    #   REBASED  — the series steps and stays there, or simply stops (AHT-GB,
    #     JUST-GB). Everything before the step is in a superseded unit.
    #
    # The window median is a robust anchor for telling them apart: if the LAST row
    # is itself off-scale against the median, the series has rebased; otherwise the
    # off-scale rows are an excursion. This branch only ever runs on a series that
    # has already tripped the 20x step test, so a genuine multi-bagger cannot reach it.
    closes = [r["close"] for r in lookback if r.get("close")]
    if not closes:
        return None, None, lookback[brk:], "rebased"
    med = sorted(closes)[len(closes) // 2]
    last = lookback[-1].get("close")
    last_off_scale = bool(last and (last < med / 20.0 or last > med * 20.0))

    if not last_off_scale:
        clean = [r for r in lookback
                 if r.get("close") and med / 20.0 <= r["close"] <= med * 20.0]
        dropped = len(lookback) - len(clean)
        if clean:
            _k = (ticker, "excursion")
            if _k not in _S81B_REPORTED:
                _S81B_REPORTED.add(_k)
                print(f"  52W-EXCURSION {ticker:12s} — {dropped} off-scale row(s) excluded "
                      f"around {lookback[brk].get('date')}; range from the remaining {len(clean)}")
            return max(r["high"] for r in clean), min(r["low"] for r in clean), clean, "excursion"

    window = lookback[brk:]
    if len(window) < _S81B_MIN_POST_BREAK:
        print(f"  52W-REBASED {ticker:12s} at {lookback[brk].get('date')} — only "
              f"{len(window)} comparable row(s) since; 52-week range withheld")
        return None, None, window, "rebased"
    print(f"  52W-REBASED {ticker:12s} at {lookback[brk].get('date')} — 52-week "
          f"range computed from the {len(window)} rows since")
    return max(r["high"] for r in window), min(r["low"] for r in window), window, "rebased"


def build_prices_json(universe, raw_data, benchmark_rows, dropped=None):
    """Build prices.json with per-stock price data, MAs, 52W stats, RS.

    `dropped` (optional list) collects a dict per excluded stock so the caller
    can reconcile the universe against what was actually emitted. Before
    04-Aug-2026 an exclusion was a printed line in a 161KB log and nothing else,
    which is how a live holding stayed missing from every dashboard unnoticed.
    """
    prices = []
    rs_composites = {}

    # MD-V2-S54-MARKER: pre-compute industry/sector static counts
    # (sectors_in_industry_count, companies_in_sector_count — two new display columns)
    _pre_industry_sectors = defaultdict(set)
    _pre_sector_companies = defaultdict(int)
    for _ps in universe["stocks"]:
        _pi = _ps.get("industry", "")
        _psc = _ps.get("sector", "")
        if _pi and _psc:
            _pre_industry_sectors[_pi].add(_psc)
            _pre_sector_companies[_psc] += 1
    _industry_sector_count = {i: len(s) for i, s in _pre_industry_sectors.items()}

    for stock in universe["stocks"]:
        yf = stock["yfinance_ticker"]
        ticker = stock["ticker"]

        _n_rows = len(raw_data.get(yf, []))
        if yf not in raw_data or _n_rows < MIN_HISTORY_ROWS:
            # Row count alone CANNOT tell a genuine young listing from a broken
            # symbol: RICHT-HU (Gedeon Richter, listed for decades) and
            # VSURE-SE both sit at ~24 bars because their symbol has stopped
            # returning data, which looks identical to a recent IPO. So say so
            # honestly, and cross-reference probe_dead_tickers.py, which already
            # knows which symbols resolve and whose output nothing consumed
            # before 04-Aug-2026.
            _probe = _load_probe_verdicts()
            _resolves = _probe.get(ticker)
            if not (yf or "").strip():
                _reason, _cat = "no yfinance ticker mapped", "blank-symbol"
            elif _n_rows < 5:
                _reason, _cat = ("provider returned %d bar(s) — almost certainly "
                                 "delisted, renamed or a wrong symbol"
                                 % _n_rows), "no-data"
            else:
                _reason, _cat = ("only %d bars, below the %d-bar minimum — a young "
                                 "listing, or a symbol that has stopped returning "
                                 "history" % (_n_rows, MIN_HISTORY_ROWS)), "short-history"
            if _resolves:
                _reason += (" [weekly probe says %s RESOLVES at the provider as of %s, "
                            "so this is worth fixing, not ignoring]"
                            % (_resolves.get("symbol", yf), _resolves.get("last_date", "?")))
            print(f"  SKIP {ticker} — {_reason}")
            if dropped is not None:
                dropped.append({"ticker": ticker, "yfinance_ticker": yf,
                                "company_name": stock.get("company_name", ""),
                                "rows": _n_rows, "category": _cat, "reason": _reason})
            continue

        rows_with_sma = compute_smas(raw_data[yf])
        _short_history = _n_rows < FULL_HISTORY_ROWS
        if _short_history:
            # D-MD-COVERAGE-2026-08-04, amendment after testing the screens.
            # Lowering the gate let young listings in, but a missing long-window
            # average makes every test that needs it evaluate to pass=False —
            # INDISTINGUISHABLE from a genuine failure. Measured on TKMS-DE
            # (197 bars, no 200D): 13 pass-flags, 5 True / 8 False / 0 None,
            # identical in shape to SAP-DE which has 1,325 bars. A stock the
            # system cannot yet judge would have been silently ranked as a stock
            # that had been judged and failed. That is worse than the absence it
            # replaced, so say so loudly on the record and in the log.
            print("  SHORT-HISTORY %s — %d bars, below %d. Long-window readings "
                  "(150D/200D, 12M relative strength) are NOT computable, and any "
                  "screen test needing them will read as a FAILURE rather than an "
                  "unknown. Treat this stock's stage verdicts as provisional."
                  % (ticker, _n_rows, FULL_HISTORY_ROWS))

        # Defensive NaN fallback (2026-07-03): _fetch_ticker() now drops NaN
        # rows at ingestion (see NAN-SKIP above), so this should never trigger
        # against a fresh fetch. It stays as a second, independent layer of
        # defence against a NaN entering via any other path -- e.g. a cache
        # file written before this fix, or a future code path that bypasses
        # _fetch_ticker. Walk backwards from the tail and use the most recent
        # row whose close is a real, non-NaN number for latest/prev; never
        # silently serve a NaN price to the dashboard.
        def _clean_tail(rows):
            for i in range(len(rows) - 1, -1, -1):
                c = rows[i].get("close")
                if isinstance(c, (int, float)) and not math.isnan(c):
                    return i
            return None
        _clean_idx = _clean_tail(rows_with_sma)
        if _clean_idx is None:
            print(f"  SKIP {ticker} — no row with a valid (non-NaN) close")
            continue
        if _clean_idx != len(rows_with_sma) - 1:
            print(f"  NAN-FALLBACK {ticker} — tail row(s) had NaN close, "
                  f"using last valid close from {rows_with_sma[_clean_idx]['date']}")
            rows_with_sma = rows_with_sma[:_clean_idx + 1]

        # Latest row + previous day
        latest = rows_with_sma[-1]
        prev = rows_with_sma[-2] if len(rows_with_sma) > 1 else latest

        # 52-week high/low (last 252 trading days)
        lookback_252 = rows_with_sma[-252:] if len(rows_with_sma) >= 252 else rows_with_sma
        # MD-S81B-52W-INTEGRITY-MARKER: tick repair + unit-break-aware window.
        high_52w, low_52w, _lb52, _s81b_kind = _s81b_52w_window(lookback_252, ticker)
        _unit_break_52w = _s81b_kind is not None
        _unit_break_date = (_lb52[0].get("date") if (_s81b_kind == "rebased" and _lb52) else None)

        # Swing high detection (Q8, 23-Apr-26): most recent local peak
        # A swing high = a day whose high is higher than the 5 days before and after it
        swing_high = high_52w  # fallback to 52W high (may be None after S81b)
        lookback_for_swing = rows_with_sma[-126:] if len(rows_with_sma) >= 126 else rows_with_sma  # 6 months
        # S81b: a swing high taken from pre-break rows is quoted in a superseded
        # unit, which would read as a ~99% pullback against today's price and feed
        # straight into the uptrend-retest depth calculation. Restrict the swing
        # search to rows that are comparable with the current price.
        if _s81b_kind == "rebased" and _lb52:
            _swing_floor = _lb52[0].get("date")
            if _swing_floor:
                _trimmed = [r for r in lookback_for_swing if r.get("date") >= _swing_floor]
                if _trimmed:
                    lookback_for_swing = _trimmed
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
            # MD-V2-S54-MARKER: 20-day-ago MA (Stage 4 T2/T3 MoM decline test)
            mas[f"{p}D_20d_ago"] = rows_with_sma[-21].get(key) if len(rows_with_sma) >= 21 else None
        # 80-day-ago 200D MA (Stage 3 gate: 200D rising vs M-4)
        mas["200D_80d_ago"] = rows_with_sma[-81].get("sma_200") if len(rows_with_sma) >= 81 else None
        # 150-day-ago 200D MA (Stage 1 gate: 200D declining over 150D window)
        mas["200D_150d_ago"] = rows_with_sma[-151].get("sma_200") if len(rows_with_sma) >= 151 else None

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
        # Same zero-denominator semantics as the 5-day field below: a null here means
        # "no down-volume days in the window", which is maximally bullish, not absent.
        utr_updown_ratio = round(adv_1m_up / adv_1m_dn, 4) if adv_1m_dn > 0 else None
        utr_updown_ratio_note = _updown_note(adv_1m_up, adv_1m_dn, len(recent_20), "20-day")

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
        # MD-V2-S54-MARKER: Stage 3 T6 new ATR expansion ratio
        # L20D ATR vs prior L80D (days 21-100). Ratio >= 1.10 = volatility expanding = topping signal.
        _atr_l20d = _atr(rows_with_sma[-21:-1]) if len(rows_with_sma) >= 22 else None
        _atr_prior_80d = _atr(rows_with_sma[-101:-20]) if len(rows_with_sma) >= 101 else None
        atr_expansion_ratio = round(_atr_l20d / _atr_prior_80d, 4) if (_atr_l20d and _atr_prior_80d and _atr_prior_80d > 0) else None

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

        # 10-day MA reclaim: True if close crossed ABOVE the test MA within the last 10 trading days.
        # A crossover = day[i] close <= MA[i] then day[i+1] close > MA[i+1] (or equivalent).
        utr_ma_reclaim_10d = False
        if utr_test_ma is not None and len(rows_with_sma) >= 2:
            _rcl_period = {"50D": 50, "100D": 100, "150D": 150, "200D": 200}.get(utr_test_ma)
            if _rcl_period is not None:
                _sma_key = f"sma_{_rcl_period}"
                _rcl_window = rows_with_sma[-11:] if len(rows_with_sma) >= 11 else rows_with_sma
                for _rwi in range(1, len(_rcl_window)):
                    _c_now = _rcl_window[_rwi].get("close")
                    _m_now = _rcl_window[_rwi].get(_sma_key)
                    _c_prev = _rcl_window[_rwi - 1].get("close")
                    _m_prev = _rcl_window[_rwi - 1].get(_sma_key)
                    if all(v is not None for v in [_c_now, _m_now, _c_prev, _m_prev]):
                        if _c_prev <= _m_prev and _c_now > _m_now:
                            utr_ma_reclaim_10d = True
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
                if sub_low > sj_high * 0.85:
                    continue
                days_below = sum(1 for r in sub_window if r["high"] < sj_high)
                if days_below < 20:
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

        # MD-V2-S55: total lower-lows count in last ~2 months (42 trading days)
        # Used by Stage 3 T7. Counts pivot lows whose value is below the prior
        # pivot low, irrespective of contiguity (unlike the streak above).
        lower_lows_count_42d = 0
        if len(rows_with_sma) >= 42:
            _tw = 3
            _recent_42 = rows_with_sma[-42:]
            _ll_swings = []
            for _i in range(_tw, len(_recent_42) - _tw):
                _cand = _recent_42[_i]["low"]
                _is_trough = True
                for _j in range(_i - _tw, _i + _tw + 1):
                    if _j != _i and _recent_42[_j]["low"] < _cand:
                        _is_trough = False
                        break
                if _is_trough:
                    _ll_swings.append(_cand)
            for _k in range(1, len(_ll_swings)):
                if _ll_swings[_k] < _ll_swings[_k - 1]:
                    lower_lows_count_42d += 1

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
        #
        # NOTE ON THE WINDOW, deliberately left alone (12-Aug-2026): _split_vol compares
        # row i against row i-1, so 5 rows yield 4 day-over-day comparisons, not 5. That
        # off-by-one is the HOUSE CONVENTION -- the 20-day and 10-day siblings do exactly
        # the same. Fixing it here alone would make one member of the family disagree with
        # the others and would silently shift a number Richard reads every evening, so it
        # is documented rather than "corrected".
        #
        # WHY THE ZERO-DENOMINATOR CASE IS NOT A GAP (12-Aug-2026). `dn == 0` means there
        # were NO down-volume days in the window. That is not missing data: it is the
        # strongest possible up/down reading, and returning a bare None made it
        # indistinguishable from a computation failure. On 11-Aug it fired on three live
        # holdings at once -- Hilton Food (four straight up days), Theon (+9%) and Xvivo
        # (+15.5%) -- and the alignment note reported all three as a defect. Universe-wide
        # it was null on 63 of 982 names, 6.4%.
        #
        # The mirror case is just as misleading: `up == 0` yields a clean-looking 0.0,
        # which is the maximally BEARISH reading, not a neutral one.
        #
        # The ratio itself keeps its type (number or None) so no consumer breaks; the
        # REASON now travels beside it. Missing data must never read as healthy, and
        # healthy data must never read as missing.
        _recent_5 = rows_with_sma[-5:] if len(rows_with_sma) >= 5 else rows_with_sma
        _adv_5d_up, _adv_5d_dn = _split_vol(_recent_5)
        utr_updown_ratio_5d = round(_adv_5d_up / _adv_5d_dn, 4) if _adv_5d_dn > 0 else None
        utr_updown_ratio_5d_note = _updown_note(_adv_5d_up, _adv_5d_dn, len(_recent_5), "5-day")

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

        # Stage 1 streak metrics (replaces soft_stack_streak from MD-V2-S54)
        # short_soft_stack_streak: 20D >= 97% of 50D AND 50D >= 97% of 100D (Group 2 — Early-stage bottoming)
        short_soft_stack_streak = 0
        for _sr in reversed(rows_with_sma):
            _s20  = _sr.get("sma_20")
            _s50  = _sr.get("sma_50")
            _s100 = _sr.get("sma_100")
            if _s20 is None or _s50 is None or _s100 is None:
                break
            if _s20 >= 0.97 * _s50 and _s50 >= 0.97 * _s100:
                short_soft_stack_streak += 1
            else:
                break
        # long_soft_stack_streak: 100D >= 97% of 150D AND 150D >= 97% of 200D (Group 3 — Protracted bottoming)
        long_soft_stack_streak = 0
        for _sr in reversed(rows_with_sma):
            _s100 = _sr.get("sma_100")
            _s150 = _sr.get("sma_150")
            _s200 = _sr.get("sma_200")
            if _s100 is None or _s150 is None or _s200 is None:
                break
            if _s100 >= 0.97 * _s150 and _s150 >= 0.97 * _s200:
                long_soft_stack_streak += 1
            else:
                break

        # MD-V2-S54-MARKER: 504-day base count (Stage 3 T3)
        # Same algorithm as base_count_since_52wl but over 504-day (2-year) lookback window.
        base_count_504d = 0
        if len(rows_with_sma) >= 100:
            _lb504 = rows_with_sma[-504:] if len(rows_with_sma) >= 504 else rows_with_sma
            _sw504 = 5
            _shs504 = []
            for _sj in range(_sw504, len(_lb504) - _sw504):
                _cand = _lb504[_sj]["high"]
                _pk = True
                for _sk in range(_sj - _sw504, _sj + _sw504 + 1):
                    if _sk != _sj and _lb504[_sk]["high"] > _cand:
                        _pk = False
                        break
                if _pk:
                    _shs504.append((_sj, _cand))
            for _sj_idx, _sj_high in _shs504:
                _sub_end = len(_lb504)
                for _nh_idx, _ in _shs504:
                    if _nh_idx > _sj_idx:
                        _sub_end = _nh_idx
                        break
                _sub_w = _lb504[_sj_idx + 1:_sub_end]
                if not _sub_w:
                    continue
                _sub_low = min(r["low"] for r in _sub_w)
                if _sub_low > _sj_high * 0.85:
                    continue
                _days_below = sum(1 for r in _sub_w if r["high"] < _sj_high)
                if _days_below < 20:
                    continue
                _sub_low_i = next(i for i, r in enumerate(_sub_w) if r["low"] == _sub_low)
                _post_low = _sub_w[_sub_low_i:]
                if any(r["high"] > _sj_high for r in _post_low):
                    base_count_504d += 1

        entry = {
            "ticker": ticker,
            "yf_ticker": yf,
            # D-MD-COVERAGE-2026-08-04: state the depth of history behind every
            # record. A young listing now APPEARS with honest nulls in its long
            # windows rather than vanishing, and any consumer can filter on this
            # deliberately instead of a stock silently not existing.
            "history_rows": _n_rows,
            "insufficient_history": _short_history,
            # Names the readings that cannot exist yet, so a consumer can show
            # "not yet" instead of a false negative. Empty for a normal stock.
            "unavailable_readings": ([] if not _short_history else
                                     [k for k, need in (("150D", 150), ("200D", 200),
                                                        ("rs_12m", 252))
                                      if _n_rows < need]),
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
            "high_52w": (round(high_52w, 4) if high_52w is not None else None),
            "swing_high": (round(swing_high, 4) if swing_high is not None else None),
            "low_52w": (round(low_52w, 4) if low_52w is not None else None),
            # S81b: True when a ~100x unit discontinuity sits inside the 52-week
            # window, so the range above is either trimmed to post-break rows or
            # withheld entirely. Downstream should not present a range for these.
            "unit_break_52w": bool(_unit_break_52w),
            "unit_break_date": _unit_break_date,
            "unit_break_kind": _s81b_kind,
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
            "utr_ma_reclaim_10d": utr_ma_reclaim_10d,
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
            "lower_lows_count_42d": lower_lows_count_42d,
            "rs_at_m3": rs_at_m3,
            "recent_pullback_pct": recent_pullback_pct,
            # MD-V2-PIPELINE-FIELDS-S25-MARKER: Session 25 fields
            "max_pullback_since_swing_high": max_pullback_since_swing_high,
            "days_below_swing_high": days_below_swing_high,
            "utr_candle_quality_10d": utr_candle_quality_10d,
            "utr_candle_quality_3d": utr_candle_quality_3d,
            "utr_updown_ratio_5d": utr_updown_ratio_5d,
            "utr_updown_ratio_5d_note": utr_updown_ratio_5d_note,
            "utr_updown_ratio_note": utr_updown_ratio_note,
            "close_pct_change_today": close_pct_change_today,
            # MD-V2-SCREENS-S26-MARKER: VCP contraction sequence
            "vcp_contractions": vcp_contractions,
            # Stage 1 streak fields (MD-V2-S54 soft_stack_streak replaced)
            "short_soft_stack_streak": short_soft_stack_streak,
            "long_soft_stack_streak": long_soft_stack_streak,
            "atr_expansion_ratio": atr_expansion_ratio,
            "base_count_504d": base_count_504d,
            # Static industry/sector count columns
            "sectors_in_industry_count": _industry_sector_count.get(stock.get("industry", ""), 0),
            "companies_in_sector_count": _pre_sector_companies.get(stock.get("sector", ""), 0),
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
        sector_vals = [v for v in sector_rs.values() if v is not None and not math.isnan(v)]
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
        industry_vals = [v for v in industry_rs.values() if v is not None and not math.isnan(v)]
        industry_mean = sum(industry_vals) / len(industry_vals) if industry_vals else None
        for entry in prices:
            if entry["ticker"] in industry_pcts:
                entry["rs_vs_industry"] = industry_pcts[entry["ticker"]]
                my_rs = rs_composites.get(entry["ticker"])
                entry["rs_excess_industry"] = round(my_rs - industry_mean, 6) if my_rs is not None and industry_mean is not None else None

    # Market-level excess return: stock RS - universe mean RS
    all_rs_vals = [v for v in rs_composites.values() if v is not None and not math.isnan(v)]
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
        # S81b: h52 can now be None when a unit break leaves no comparable
        # history. None must not be compared with 0 — that raises in Python 3.
        # S81c: None, not 0. Zero renders on the probing-bet tab as "0% below the
        # 52-week high", i.e. AT the high, which is the opposite of what we know.
        pct_below_52wh = (h52 - p) / h52 if (h52 is not None and h52 > 0) else None
        pb_t8 = bool(pct_below_52wh is not None and pct_below_52wh >= 0.30)
        pb["group_c"] = {"pass": pb_t8, "tests": {"T8": pb_t8},
                         "pct_below_52wh": (round(pct_below_52wh, 4) if pct_below_52wh is not None else None)}

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
# S2 Monthly Persistence — 12-month backfill (MD-V2-S2-PERSIST-RATED-MARKER)
# ──────────────────────────────────────────────────────────────────────────

def compute_s2_monthly_persistence(universe, raw_data, benchmark_rows):
    """
    Compute Stage 2 ratings at month-end price snapshots for the past 12 months.

    Replicates the Stage 2 logic (4 gates + 5 tests) at each month-end using
    cached OHLCV data.  RS-based tests (T7/T8/T9) are computed cross-stock at
    each month-end so the percentile rankings are historically accurate.

    Returns:
        dict  {ticker: [r_M11, r_M10, ..., r_M0]}
              Index 0 = 11 months ago, index 11 = current month.
              Each entry is 'None' | 'Possible' | 'Plausible' | 'Probable'.
    """
    import calendar
    import bisect

    today = date.today()

    # --- Build 12 target month-end date strings (oldest first) ---
    month_ends = []
    for offset in range(11, -1, -1):      # 11 months ago to current month
        yr, mo = today.year, today.month - offset
        while mo <= 0:
            mo += 12
            yr -= 1
        last_day = calendar.monthrange(yr, mo)[1]
        target = date(yr, mo, last_day)
        if target > today:
            target = today
        month_ends.append(target.strftime('%Y-%m-%d'))

    # --- Universe metadata ---
    stock_meta = {}
    for stk in universe['stocks']:
        stock_meta[stk['ticker']] = {
            'yf':       stk['yfinance_ticker'],
            'industry': stk.get('industry', ''),
            'sector':   stk.get('sector', ''),
        }

    # --- Pre-compute SMA rows once per stock ---
    # compute_smas preserves all original fields (date, open, high, low, close, volume)
    bench_sma   = compute_smas(benchmark_rows) if len(benchmark_rows) >= 252 else []
    bench_dates = [r['date'] for r in bench_sma]

    stock_sma_map = {}   # ticker -> (sma_rows, date_list)
    for ticker, meta in stock_meta.items():
        raw = raw_data.get(meta['yf'], [])
        if len(raw) >= 200:
            sma_rows = compute_smas(raw)
            stock_sma_map[ticker] = (sma_rows, [r['date'] for r in sma_rows])

    # --- Result container ---
    result = {ticker: ['None'] * 12 for ticker in stock_sma_map}

    for mi, date_str in enumerate(month_ends):

        # --- Benchmark snapshot at this month-end ---
        bench_idx = bisect.bisect_right(bench_dates, date_str) - 1
        has_bench = bench_idx >= 251

        # --- Step 1: RS composite for every stock at this month-end ---
        rs_at_date = {}
        if has_bench:
            bench_slice = bench_sma[bench_idx - 251 : bench_idx + 1]
            for ticker, (rows, dates) in stock_sma_map.items():
                idx = bisect.bisect_right(dates, date_str) - 1
                if idx < 251:
                    continue
                stock_slice = rows[idx - 251 : idx + 1]
                rs_val, _ = compute_rs_composite(stock_slice, bench_slice)
                if rs_val is not None:
                    rs_at_date[ticker] = rs_val

        # --- Step 2: Cross-stock RS rankings at this month-end ---
        # Industry ranking by average RS
        ind_rs_vals = defaultdict(list)
        for ticker, rs_val in rs_at_date.items():
            ind = stock_meta[ticker]['industry']
            if ind:
                ind_rs_vals[ind].append(rs_val)

        ind_mean = {i: sum(v) / len(v) for i, v in ind_rs_vals.items() if v}
        ind_sorted = sorted(ind_mean, key=lambda x: ind_mean[x])
        n_ind = len(ind_sorted)
        ind_pct_rank = {
            ind: int(round(k / max(n_ind - 1, 1) * 99))
            for k, ind in enumerate(ind_sorted)
        }

        # Universe mean RS -> excess vs market per stock
        all_rs = list(rs_at_date.values())
        market_mean = sum(all_rs) / len(all_rs) if all_rs else 0.0
        rs_excess_mkt = {t: rs - market_mean for t, rs in rs_at_date.items()}

        # Industry mean excess vs market (for sector-within-industry ranking)
        ind_excess_mkt_mean = {}
        for ind in ind_mean:
            vals = [rs_excess_mkt[t] for t in rs_excess_mkt
                    if stock_meta.get(t, {}).get('industry', '') == ind]
            if vals:
                ind_excess_mkt_mean[ind] = sum(vals) / len(vals)

        # Sector excess vs industry -> rank within industry
        sec_excess_ind_vals = defaultdict(list)
        for ticker, rs_exc in rs_excess_mkt.items():
            sec = stock_meta[ticker]['sector']
            ind = stock_meta[ticker]['industry']
            ind_m = ind_excess_mkt_mean.get(ind)
            if sec and ind_m is not None:
                sec_excess_ind_vals[sec].append(rs_exc - ind_m)

        sec_mean_excess = {s: sum(v) / len(v) for s, v in sec_excess_ind_vals.items() if v}

        # Sector percentile within its industry
        sec_to_ind = {
            stock_meta[t]['sector']: stock_meta[t]['industry']
            for t in stock_meta if stock_meta[t]['sector']
        }
        sec_pct_in_ind = {}
        for industry_name in set(sec_to_ind.values()):
            secs_in_ind = [s for s, i in sec_to_ind.items() if i == industry_name]
            valid = [(s, sec_mean_excess[s]) for s in secs_in_ind if s in sec_mean_excess]
            valid.sort(key=lambda x: x[1])
            nn = len(valid)
            for rank, (s, _) in enumerate(valid):
                sec_pct_in_ind[s] = int(round(rank / max(nn - 1, 1) * 99))

        # Stock RS vs industry percentile
        rs_vs_ind_pct = {}
        for ind_name in set(stock_meta[t]['industry'] for t in stock_meta):
            if not ind_name:
                continue
            tickers_in = [t for t in rs_excess_mkt
                          if stock_meta.get(t, {}).get('industry', '') == ind_name]
            ind_m = ind_excess_mkt_mean.get(ind_name, 0.0)
            vals_in = [(t, rs_excess_mkt[t] - ind_m) for t in tickers_in]
            vals_in.sort(key=lambda x: x[1])
            nn = len(vals_in)
            for rank, (t, _) in enumerate(vals_in):
                rs_vs_ind_pct[t] = int(round(rank / max(nn - 1, 1) * 99))

        # --- Step 3: Stage 2 rating per stock at this month-end ---
        for ticker, (rows, dates) in stock_sma_map.items():
            idx = bisect.bisect_right(dates, date_str) - 1
            if idx < 199:
                continue

            row   = rows[idx]
            price = row.get('close')
            ma50  = row.get('sma_50')
            ma150 = row.get('sma_150')
            ma200 = row.get('sma_200')

            if any(v is None for v in [price, ma50, ma150, ma200]):
                continue

            # 52-week high: max daily high over last 252 rows ending at idx
            lookback = rows[max(0, idx - 251) : idx + 1]
            h52 = max(r['high'] for r in lookback) if lookback else None
            if not h52 or h52 <= 0:
                continue

            # 4 hard gates
            g1 = price > ma200
            g2 = price > ma150
            g3 = ma150 > ma200
            g4 = price >= h52 * 0.75
            if not (g1 and g2 and g3 and g4):
                result[ticker][mi] = 'None'
                continue

            # 5 tests (T5-T9 matching compute_master_dashboard_screens)
            t5 = ma50 > ma150
            t6 = ma50 > ma200
            ind = stock_meta[ticker]['industry']
            sec = stock_meta[ticker]['sector']
            t7 = ind_pct_rank.get(ind, 0) >= 70
            t8 = sec_pct_in_ind.get(sec, 0) >= 70
            t9 = rs_vs_ind_pct.get(ticker, 0) >= 70

            count = sum([t5, t6, t7, t8, t9])
            if count >= 4:
                result[ticker][mi] = 'Probable'
            elif count >= 3:
                result[ticker][mi] = 'Plausible'
            elif count >= 2:
                result[ticker][mi] = 'Possible'
            else:
                result[ticker][mi] = 'None'

    return result


# ── MD-V2-S81-SB-50D-TURN-MARKER ─────────────────────────────────────────────
# Single source of truth for the Stage 1 / Stage 3 / Stage 4 speculative-bet test.
#
# S81 (11-Aug-26, Richard's brief). Two changes from the S46 six-criterion test:
#   1. A SIXTH test — the 50-day MA freshly turning up — joins the 20-day turn in
#      the trigger group. The confirmation test renumbers to #7; total 6 -> 7.
#   2. The turn leg of the rating ladder is satisfied by EITHER the 20-day OR the
#      50-day MA having turned up, so a slower turn no longer disqualifies.
# The price leg is unchanged and still reads against the 20-day MA.
#
# The Stage 2 probing bet has its own 50D-only builder (_ps_build_50d) and is
# deliberately NOT routed through here.
#
# These functions are module-level so the nightly pipeline and any one-off
# recompute call the SAME code. Do not re-implement this ladder anywhere else.

PS_TEST_TOTAL = 7


def ps_round(x, nd=4):
    try:
        if x is None:
            return None
        return round(float(x), nd)
    except (TypeError, ValueError):
        return None


def ps_pct_gap(a, b):
    try:
        if a is None or b is None or b == 0:
            return None
        return round((float(a) - float(b)) / float(b), 4)
    except (TypeError, ValueError):
        return None


def ps_signals(price, mas, close_pct_change_today):
    """Primitive booleans behind the speculative-bet test, from one price row.

    A "turn" is: the MA is rising day-over-day now AND was falling 5 days ago.
    Missing inputs degrade to False rather than raising.
    """
    mas = mas or {}
    ma5_now, ma5_prev = mas.get("5D"), mas.get("5D_prev")
    ma10_now, ma10_prev = mas.get("10D"), mas.get("10D_prev")
    ma20_now, ma20_prev = mas.get("20D"), mas.get("20D_prev")
    ma20_5, ma20_6 = mas.get("20D_5d_ago"), mas.get("20D_6d_ago")
    ma50_now, ma50_prev = mas.get("50D"), mas.get("50D_prev")
    ma50_5, ma50_6 = mas.get("50D_5d_ago"), mas.get("50D_6d_ago")

    ma20_now_rising = bool(ma20_now is not None and ma20_prev is not None and ma20_now > ma20_prev)
    ma20_was_falling = bool(ma20_5 is not None and ma20_6 is not None and ma20_5 < ma20_6)
    ma50_now_rising = bool(ma50_now is not None and ma50_prev is not None and ma50_now > ma50_prev)
    ma50_was_falling = bool(ma50_5 is not None and ma50_6 is not None and ma50_5 < ma50_6)

    return {
        "ma20_now": ma20_now,
        "ma50_now": ma50_now,
        "close_pct_change_today": close_pct_change_today,
        "price": price,
        "b1_5d_rising": bool(ma5_now is not None and ma5_prev is not None and ma5_now > ma5_prev),
        "b2_10d_rising": bool(ma10_now is not None and ma10_prev is not None and ma10_now > ma10_prev),
        "c1_price_gt_20d": bool(price is not None and ma20_now is not None and price > ma20_now),
        "c1_price_gt_50d": bool(price is not None and ma50_now is not None and price > ma50_now),
        "c2_ma20_now_rising": ma20_now_rising,
        "c2_ma20_turn": bool(ma20_now_rising and ma20_was_falling),
        "c2_ma50_now_rising": ma50_now_rising,
        "c2_ma50_turn": bool(ma50_now_rising and ma50_was_falling),
        "c3_followthrough": bool(close_pct_change_today is not None and close_pct_change_today >= 0.02),
    }


def ps_turn(sig):
    """The trigger leg: EITHER moving average having freshly turned up (S81)."""
    return bool(sig["c2_ma20_turn"] or sig["c2_ma50_turn"])


def ps_rating(sig, stage_qualifies):
    if not stage_qualifies:
        return "None"
    if not (sig["b1_5d_rising"] and sig["b2_10d_rising"]):
        return "None"
    turn = ps_turn(sig)
    if sig["c1_price_gt_20d"] and turn and sig["c3_followthrough"]:
        return "Qualified"
    if sig["c1_price_gt_20d"] and turn:
        return "Probable"
    if sig["c1_price_gt_20d"] or turn:
        return "Plausible"
    return "Possible"


def _ps_turn_label(turned, rising):
    if turned:
        return "turn (rising now, falling 5d ago)"
    if rising:
        return "rising but no recent turn"
    return "not rising"


def ps_build(sig, stage_qualifies, variant_key, stage_rating_value):
    tests = {
        "g1_stage_qualifies": bool(stage_qualifies),
        "g2_5d_rising": sig["b1_5d_rising"],
        "g3_10d_rising": sig["b2_10d_rising"],
        "g4_price_gt_20d": sig["c1_price_gt_20d"],
        "g5_20d_turn_last_5d": sig["c2_ma20_turn"],
        "g6_50d_turn_last_5d": sig["c2_ma50_turn"],
        "g7_followthrough_close_ge2pct": sig["c3_followthrough"],
    }
    count = sum(1 for v in tests.values() if v)
    rating = ps_rating(sig, stage_qualifies)
    return {
        "tests": tests, "count": count, "total": PS_TEST_TOTAL,
        "rating": rating,
        "qualifies": bool(rating == "Qualified"),
        "info_variant": variant_key,
        "info_stage_rating": stage_rating_value,
        "test_values": {
            "g1_stage_qualifies": (stage_rating_value if stage_qualifies else "not in stage"),
            "g2_5d_rising": ("rising" if sig["b1_5d_rising"] else "not rising"),
            "g3_10d_rising": ("rising" if sig["b2_10d_rising"] else "not rising"),
            "g4_price_gt_20d": ps_pct_gap(sig["price"], sig["ma20_now"]),
            "g5_20d_turn_last_5d": _ps_turn_label(sig["c2_ma20_turn"], sig["c2_ma20_now_rising"]),
            "g6_50d_turn_last_5d": _ps_turn_label(sig["c2_ma50_turn"], sig["c2_ma50_now_rising"]),
            "g7_followthrough_close_ge2pct": ps_round(sig["close_pct_change_today"]),
        },
    }


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

    # MD-V2-S54-MARKER: pre-pass — industry and sector RS percentile rankings
    # Used by Stage 2 T7 (industry RS rank >= 70) and T8 (sector-within-industry RS rank >= 70),
    # and Stage 3 T8 (sector RS rank today vs 3M ago, degraded > 10 points).

    # Industry-level: avg rs_excess_market per industry → rank all industries
    _ind_excess_mkt = defaultdict(list)
    _sec_to_ind = {}
    for _pp in prices:
        _ii = _pp.get("industry", "")
        _ss = _pp.get("sector", "")
        _rem = _pp.get("rs_excess_market")
        if _ii and _rem is not None and not (isinstance(_rem, float) and math.isnan(_rem)):
            _ind_excess_mkt[_ii].append(_rem)
        if _ss and _ii:
            _sec_to_ind[_ss] = _ii
    _ind_mean_excess = {i: sum(v)/len(v) for i, v in _ind_excess_mkt.items() if v}
    _ind_sorted = sorted(_ind_mean_excess.keys(), key=lambda x: _ind_mean_excess[x])
    _n_ind = len(_ind_sorted)
    _ind_pct_rank = {ind: int(round(i / max(_n_ind - 1, 1) * 99)) for i, ind in enumerate(_ind_sorted)}

    # Sector-within-industry: avg rs_excess_industry per sector → rank within industry
    _sec_excess_ind = defaultdict(list)
    for _pp in prices:
        _ss = _pp.get("sector", "")
        _rei = _pp.get("rs_excess_industry")
        if _ss and _rei is not None and not (isinstance(_rei, float) and math.isnan(_rei)):
            _sec_excess_ind[_ss].append(_rei)
    _sec_mean_excess = {s: sum(v)/len(v) for s, v in _sec_excess_ind.items() if v}
    _sec_pct_in_ind = {}
    for _ii in set(_sec_to_ind.values()):
        _secs_in = [s for s, i in _sec_to_ind.items() if i == _ii and s in _sec_mean_excess]
        if not _secs_in:
            continue
        _secs_sorted = sorted(_secs_in, key=lambda x: _sec_mean_excess[x])
        _n_s = len(_secs_sorted)
        for _si, _sec in enumerate(_secs_sorted):
            # Edge case: sole sector in an industry is by definition #1 → assign 99
            if _n_s == 1:
                _sec_pct_in_ind[_sec] = 99
            else:
                _sec_pct_in_ind[_sec] = int(round(_si / (_n_s - 1) * 99))

    # M-3 sector-within-industry rank (for Stage 3 T8: sector RS drift > 10 pts vs 3M ago)
    _sec_m3_rs = defaultdict(list)
    for _pp in prices:
        _ss = _pp.get("sector", "")
        _ii = _pp.get("industry", "")
        _rs_m3v = _pp.get("rs_at_m3")
        if _ss and _ii and _rs_m3v is not None:
            _sec_m3_rs[_ss].append(_rs_m3v)
    _sec_m3_mean = {s: sum(v)/len(v) for s, v in _sec_m3_rs.items() if v}
    _sec_m3_pct_in_ind = {}
    for _ii in set(_sec_to_ind.values()):
        _secs_in = [s for s, i in _sec_to_ind.items() if i == _ii and s in _sec_m3_mean]
        if not _secs_in:
            continue
        _secs_sorted = sorted(_secs_in, key=lambda x: _sec_m3_mean[x])
        _n_s = len(_secs_sorted)
        for _si, _sec in enumerate(_secs_sorted):
            _sec_m3_pct_in_ind[_sec] = int(round(_si / max(_n_s - 1, 1) * 99))

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

        # MD-V2-S54-MARKER: new MA accessors for Stage 4 rewrite
        ma100 = mas.get("100D")
        ma100_20d_ago = mas.get("100D_20d_ago")
        ma200_20d_ago = mas.get("200D_20d_ago")
        ma200_80d_ago  = mas.get("200D_80d_ago")
        ma200_150d_ago = mas.get("200D_150d_ago")
        # Stock's sector and industry (for S2 T7/T8, S3 T8)
        _stock_sector = p.get("sector", "")
        _stock_industry = p.get("industry", "")

        # ── MD-V2-SCREENS-S25-FIX-MARKER: Session 25 accessors ──
        max_pullback_ssh = p.get("max_pullback_since_swing_high")
        days_below_sh = p.get("days_below_swing_high")
        utr_50d_rising = p.get("utr_50d_rising", False)
        utr_150d_rising = p.get("utr_150d_rising", False)
        utr_5d_declining = p.get("utr_5d_declining", False)
        utr_10d_declining = p.get("utr_10d_declining", False)
        utr_ma_reclaim_10d = p.get("utr_ma_reclaim_10d", False)
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
        # STAGE 1 — Consolidating / Basing  [MD-V2-S73-REWRITE]
        # Gate:    200D MA today < 200D MA 150 trading days ago
        # Group 1: Longer-term trend downwards? → gate only
        # Group 2: Early-stage bottoming?
        #   Test #2: 20D >= 97% of 50D >= 97% of 100D for 1M  (short_streak >= 20)
        #   Test #3: 20D >= 97% of 50D >= 97% of 100D for 3M+ (short_streak >= 63)
        # Group 3: Protracted bottoming?
        #   Test #4: 100D >= 97% of 150D >= 97% of 200D for 1M  (long_streak >= 20)
        #   Test #5: 100D >= 97% of 150D >= 97% of 200D for 3M+ (long_streak >= 63)
        # Possible:  gate AND #2
        # Plausible: gate AND #4
        # Probable:  gate AND (#3 OR #5)   [highest tier always wins]
        # ──────────────────────────────────────────────────────────────
        s1 = {"tests": {}, "groups": {}, "count": 0, "rating": "None"}
        _short_streak = p.get("short_soft_stack_streak", 0) or 0
        _long_streak  = p.get("long_soft_stack_streak",  0) or 0
        s1_gate = (ma200 is not None and ma200_150d_ago is not None and ma200 < ma200_150d_ago)
        _t2 = _short_streak >= 20
        _t3 = _short_streak >= 63
        _t4 = _long_streak  >= 20
        _t5 = _long_streak  >= 63
        s1["gate_200D_declining_vs_150d"] = s1_gate
        s1["short_soft_stack_streak"] = _short_streak
        s1["long_soft_stack_streak"]  = _long_streak
        s1["tests"] = {
            "t1_gate":     s1_gate,
            "t2_short_1m": _t2,
            "t3_short_3m": _t3,
            "t4_long_1m":  _t4,
            "t5_long_3m":  _t5,
        }
        s1["test_values"] = {
            "gate_200D_vs_150d_ago":        _md_v2_pct_gap(ma200, ma200_150d_ago),
            "short_soft_stack_streak_days": _short_streak,
            "long_soft_stack_streak_days":  _long_streak,
        }
        if s1_gate:
            if _t3 or _t5:
                s1["rating"] = "Probable"
            elif _t4:
                s1["rating"] = "Plausible"
            elif _t2:
                s1["rating"] = "Possible"
            else:
                s1["rating"] = "None"
        else:
            s1["rating"] = "None"
        md["stage_1"] = s1

        # ──────────────────────────────────────────────────────────────
        # STAGE 2 — Uptrend  [MD-V2-S54-REWRITE]
        # 4 hard gates: P>200D, P>150D, 150D>200D, P within 25% of 52W high
        # Gate failure → None. 5 tests: T5-T9. Possible=2/5, Plausible=3/5, Probable=4/5.
        # T5: 50D>150D / T6: 50D>200D / T7: industry RS pct >= 70 / T8: sector RS pct >= 70 / T9: rs_vs_industry >= 70
        # ──────────────────────────────────────────────────────────────
        s2 = {"tests": {}, "groups": {}, "count": 0, "rating": "None"}
        s2_gate1 = (price is not None and ma200 is not None and price > ma200)
        s2_gate2 = (price is not None and ma150 is not None and price > ma150)
        s2_gate3 = (ma150 is not None and ma200 is not None and ma150 > ma200)
        s2_gate4 = (price is not None and h52 is not None and h52 > 0 and price >= h52 * 0.75)
        s2_gates_pass = s2_gate1 and s2_gate2 and s2_gate3 and s2_gate4
        s2["gates"] = {
            "g1_P_above_200D": s2_gate1,
            "g2_P_above_150D": s2_gate2,
            "g3_150D_above_200D": s2_gate3,
            "g4_within_25pct_52WH": s2_gate4,
        }
        # Always populate test_values — RS data shown even for gate-failing stocks
        s2["test_values"] = {
            "T5_50D_vs_150D": _md_v2_pct_gap(ma50, ma150),
            "T6_50D_vs_200D": _md_v2_pct_gap(ma50, ma200),
            "T7_industry_RS_pct": _ind_pct_rank.get(_stock_industry, 0),
            "T8_sector_RS_pct_in_industry": _sec_pct_in_ind.get(_stock_sector, 0),
            "T9_rs_vs_industry": rs_vs_ind,
        }
        if s2_gates_pass:
            s2_t5 = (ma50 is not None and ma150 is not None and ma50 > ma150)
            s2_t6 = (ma50 is not None and ma200 is not None and ma50 > ma200)
            # T7: industry RS percentile rank >= 70 (avg rs_excess_market per industry, ranked vs all industries)
            s2_t7 = (_ind_pct_rank.get(_stock_industry, 0) >= 70)
            # T8: sector RS percentile rank >= 70 within its industry
            s2_t8 = (_sec_pct_in_ind.get(_stock_sector, 0) >= 70)
            # T9: stock's rs_vs_industry percentile >= 70
            s2_t9 = (rs_vs_ind is not None and rs_vs_ind >= 70)
            s2["tests"]["T5_50D_above_150D"] = s2_t5
            s2["tests"]["T6_50D_above_200D"] = s2_t6
            s2["tests"]["T7_industry_RS_pct_ge70"] = s2_t7
            s2["tests"]["T8_sector_RS_pct_ge70"] = s2_t8
            s2["tests"]["T9_stock_RS_vs_industry_ge70"] = s2_t9
            s2["groups"]["g1_ma_stack"] = {"T5": s2_t5, "T6": s2_t6}
            s2["groups"]["g2_rs"] = {"T7": s2_t7, "T8": s2_t8, "T9": s2_t9}
            s2_count = sum([s2_t5, s2_t6, s2_t7, s2_t8, s2_t9])
            s2["count"] = s2_count
            s2["total"] = 5
            if s2_count >= 4:
                s2["rating"] = "Probable"
            elif s2_count >= 3:
                s2["rating"] = "Plausible"
            elif s2_count >= 2:
                s2["rating"] = "Possible"
            else:
                s2["rating"] = "None"
        else:
            s2["rating"] = "None"
        md["stage_2"] = s2

        # ──────────────────────────────────────────────────────────────
        # STAGE 3 — Topping / Invalidated  [MD-V2-S55-REWRITE]
        # Gate 1: 200D MA today > 200D MA 80 trading days ago (still in uptrend)
        # Gate 2: Price > 200D MA (price above long-term trend)
        # 6 tests T3-T8. Possible=2, Plausible=3, Probable=4+.
        # T3: base_count_504d >= 3 / T4: 50D < 103% of 150D / T5: down vol > up vol (L20D)
        # T6: ATR expansion ratio >= 1.10 (L20D vs days 21-100)
        # T7: >=2 lower lows in the last ~2 months (42 trading days)
        # T8: sector RS pct-in-industry today dropped > 10 pts vs 3M ago
        # Ratings standardised to None / Possible / Plausible / Probable.
        # ──────────────────────────────────────────────────────────────
        s3 = {"tests": {}, "groups": {}, "count": 0, "rating": "None"}
        rs_3m = rs_returns.get("3M")  # used by downstream code; keep accessible
        s3_gate1 = (ma200 is not None and ma200_80d_ago is not None and ma200 > ma200_80d_ago)
        s3_gate2 = (price is not None and ma200 is not None and price > ma200)
        s3["gate_200D_still_rising_vs_80d"] = s3_gate1
        s3["gate_price_above_200D"] = s3_gate2
        if s3_gate1 and s3_gate2:
            _bc504 = p.get("base_count_504d", 0) or 0
            s3_t3 = _bc504 >= 3
            s3_t4 = (ma50 is not None and ma150 is not None and ma50 < ma150 * 1.03)
            s3_t5 = (adv_1m_dn > 0 and adv_1m_up > 0 and adv_1m_dn >= adv_1m_up * 1.10)
            # T6: ATR expansion ratio (L20D vs days 21-100)
            _atr_exp = p.get("atr_expansion_ratio")
            s3_t6 = (_atr_exp is not None and _atr_exp >= 1.10)
            # T7: 2+ lower lows in the last ~2 months (42 trading days) -- MD-V2-S55
            _ll42 = p.get("lower_lows_count_42d", 0) or 0
            s3_t7 = (_ll42 >= 2)
            # T8: sector RS pct-in-industry dropped > 10 percentile points vs 3M ago
            _sec_pct_now = _sec_pct_in_ind.get(_stock_sector, 0)
            _sec_pct_m3v = _sec_m3_pct_in_ind.get(_stock_sector, 0)
            s3_t8 = (_sec_pct_now < _sec_pct_m3v - 10)
            s3["tests"]["T3_base_count_504d_ge2"] = s3_t3
            s3["tests"]["T4_50D_below_103pct_150D"] = s3_t4
            s3["tests"]["T5_down_vol_exceeds_up_vol"] = s3_t5
            s3["tests"]["T6_ATR_expansion_ge110"] = s3_t6
            s3["tests"]["T7_lower_lows_2m_ge2"] = s3_t7
            s3["tests"]["T8_sector_RS_drift_gt10pts"] = s3_t8
            s3["groups"]["g1_base_deterioration"] = {"T3": s3_t3, "T4": s3_t4}
            s3["groups"]["g2_distribution_signals"] = {"T5": s3_t5, "T6": s3_t6, "T7": s3_t7}
            s3["groups"]["g3_rs_degradation"] = {"T8": s3_t8}
            s3_count = sum([s3_t3, s3_t4, s3_t5, s3_t6, s3_t7, s3_t8])
            s3["count"] = s3_count
            s3["test_values"] = {
                "T3_base_count_504d": _bc504,
                "T4_50D_vs_103pct_150D": _md_v2_pct_gap(ma50, ma150 * 1.03 if ma150 else None),
                "T5_down_vol_ratio": round(adv_1m_dn / adv_1m_up, 3) if adv_1m_up > 0 else None,
                "T6_ATR_expansion_ratio": _atr_exp,
                "T7_lower_lows_2m": _ll42,
                "T8_sector_pct_now_vs_m3": f"{_sec_pct_now} vs {_sec_pct_m3v}",
            }
            if s3_count >= 4:
                s3["rating"] = "Probable"
            elif s3_count >= 3:
                s3["rating"] = "Plausible"
            elif s3_count >= 2:
                s3["rating"] = "Possible"
            else:
                s3["rating"] = "None"
        else:
            s3["rating"] = "None"
            s3_count = 0
        md["stage_3"] = s3

        # ──────────────────────────────────────────────────────────────
        # STAGE 4 — Decline  [MD-V2-S54-REWRITE]
        # Gate: Price < 200D MA (stock has crossed below long-term trend)
        # T2: 100D MA today < 100D MA 20 trading days ago (MoM declining)
        # T3: 200D MA today < 200D MA 20 trading days ago (MoM declining)
        # T4: Price < 50D < 150D < 200D (full bearish MA stack)
        # Possible: T2 alone / Plausible: T2+T3 / Probable: T2+T3+T4
        # ──────────────────────────────────────────────────────────────
        _ensure_stage3_snapshots()
        s4 = {"tests": {}, "groups": {}, "count": 0, "rating": "None"}
        s4_gate = (price is not None and ma200 is not None and price < ma200)
        s4["gate_price_below_200D"] = s4_gate
        if s4_gate:
            s4_t2 = (ma100 is not None and ma100_20d_ago is not None and ma100 < ma100_20d_ago)
            s4_t3 = (ma200 is not None and ma200_20d_ago is not None and ma200 < ma200_20d_ago)
            s4_t4 = (price is not None and ma50 is not None and ma150 is not None and ma200 is not None
                     and price < ma50 and ma50 < ma150 and ma150 < ma200)
            s4["tests"]["T2_100D_MoM_declining"] = s4_t2
            s4["tests"]["T3_200D_MoM_declining"] = s4_t3
            s4["tests"]["T4_bearish_MA_stack"] = s4_t4
            s4["groups"]["g1_ma_decline"] = {"T2": s4_t2, "T3": s4_t3}
            s4["groups"]["g2_ma_stack"] = {"T4": s4_t4}
            s4["test_values"] = {
                "gate_price_vs_200D": _md_v2_pct_gap(price, ma200),
                "T2_100D_vs_100D_20d_ago": _md_v2_pct_gap(ma100, ma100_20d_ago),
                "T3_200D_vs_200D_20d_ago": _md_v2_pct_gap(ma200, ma200_20d_ago),
                "T4_stack_check": (
                    f"P{round(price,1)}<50D{round(ma50,1) if ma50 else '?'}<150D{round(ma150,1) if ma150 else '?'}<200D{round(ma200,1) if ma200 else '?'}"
                    if all(v is not None for v in [price, ma50, ma150, ma200]) else "data missing"
                ),
            }
            s4_count = sum([s4_t2, s4_t3, s4_t4])
            s4["count"] = s4_count
            if s4_t2 and s4_t3 and s4_t4:
                s4["rating"] = "Probable"
            elif s4_t2 and s4_t3:
                s4["rating"] = "Plausible"
            elif s4_t2:
                s4["rating"] = "Possible"
            else:
                s4["rating"] = "None"
        else:
            s4["rating"] = "None"
            s4_count = 0

        # Stage-3 lookback INFO column (D-MD-V2-115): informational only, does not modify rating.
        s3_lookback = _stage_3_fired_in_last_60d(ticker, _s47_stage3_snapshots)
        s4["info_stage_3_lookback"] = s3_lookback
        if "test_values" not in s4:
            s4["test_values"] = {}
        s4["test_values"].update({
            "s3_fired_in_60d": s3_lookback["fired"],
            "s3_days_ago": s3_lookback["days_ago"],
            "s3_history_depth_ok": s3_lookback["history_depth_ok"],
        })

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
        # MD-V2-S54-MARKER: Stage 1 now has "Probable"/"Plausible"/"None" (not Probable Early/Late)
        s1_qualifying = s1["rating"] in ("Plausible", "Probable")
        # MD-V2-S55: accept both old ('* Invalidation') and new (plain) S3 rating labels
        s3_qualifying = s3["rating"] in ("Plausible", "Probable", "Plausible Invalidation", "Probable Invalidation")
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
        # MD-V2-S54-MARKER: Stage 1 now emits "Probable" (not "Probable Late"/"Probable Early")
        s1_to_2_transition = (
            s1["rating"] == "Probable" and
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

        # MD-V2-S54-MARKER: industry/sector count columns (display only, not test inputs)
        md["sectors_in_industry_count"] = p.get("sectors_in_industry_count", 0)
        md["companies_in_sector_count"] = p.get("companies_in_sector_count", 0)
        md["industry_RS_pct_rank"] = _ind_pct_rank.get(_stock_industry, 0)
        md["sector_RS_pct_in_industry"] = _sec_pct_in_ind.get(_stock_sector, 0)

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
        # 10-day reclaim: crossed above the test MA within last 10 trading days.
        mr_trig_reclaim_10d = bool(utr_ma_reclaim_10d)
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
        # D-MD-V2-HR-S2GATE-16Aug26: Richard's ruling — the Stage 2 precondition
        # (rendered as "Gate #1" + "Gate #2" on the page) now accepts Possible as
        # well as Plausible/Probable. Was ("Probable","Plausible") only.
        hr_stage_qualifies = bool(s2.get("rating") in ("Probable", "Plausible", "Possible"))
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
            "g4_d1_reclaimed_ma": mr_trig_reclaim_10d,
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
        elif not mr_trig_reclaim_10d:
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
            "info_window_note": "v2: criterion 12 uses 10-day crossover lookback (price crossed above test MA in last 10 trading days)",
            "test_values": {
                "g1_stage_2_qualifies": (s2.get("rating") if hr_stage_qualifies else "not S2 Possible+"),
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
        vd1_gate_s1_probable = bool("Probable" in str(s1.get("rating", "")))
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
        # MD-V2-S81-SB-50D-TURN-MARKER: the primitive signals and the S1/S3/S4
        # builder now live at module level (see ps_signals / ps_build above) so
        # the nightly pipeline and any one-off recompute share one implementation.
        # The names below are kept because the Stage 2 50D-only builder reads them.
        _ps_sig = ps_signals(price, mas, close_pct_change_today)
        ps_ma50_now = _ps_sig["ma50_now"]
        ps_b1_5d_rising = _ps_sig["b1_5d_rising"]
        ps_b2_10d_rising = _ps_sig["b2_10d_rising"]
        ps_c1_price_gt_50d = _ps_sig["c1_price_gt_50d"]
        ps_c2_ma50_now_rising = _ps_sig["c2_ma50_now_rising"]
        ps_c2_ma50_turn = _ps_sig["c2_ma50_turn"]
        ps_c3_followthrough = _ps_sig["c3_followthrough"]

        # 50D variant rating + builder (S2 Probing Bet only).
        def _ps_rating_50d(stage_qualifies):
            if not stage_qualifies:
                return "None"
            if not (ps_b1_5d_rising and ps_b2_10d_rising):
                return "None"
            if ps_c1_price_gt_50d and ps_c2_ma50_turn and ps_c3_followthrough:
                return "Qualified"
            if ps_c1_price_gt_50d and ps_c2_ma50_turn:
                return "Probable"
            if ps_c1_price_gt_50d or ps_c2_ma50_turn:
                return "Plausible"
            return "Possible"

        def _ps_build_50d(stage_qualifies, variant_key, stage_rating_value):
            ps_tests = {
                "g1_stage_qualifies": stage_qualifies,
                "g2_5d_rising": ps_b1_5d_rising,
                "g3_10d_rising": ps_b2_10d_rising,
                "g4_price_gt_50d": ps_c1_price_gt_50d,
                "g5_50d_turn_last_5d": ps_c2_ma50_turn,
                "g6_followthrough_close_ge2pct": ps_c3_followthrough,
            }
            ps_count = sum(1 for v in ps_tests.values() if v)
            ps_rating = _ps_rating_50d(stage_qualifies)
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
                    "g4_price_gt_50d": _md_v2_pct_gap(price, ps_ma50_now),
                    "g5_50d_turn_last_5d": (
                        "turn (rising now, falling 5d ago)" if ps_c2_ma50_turn
                        else "rising but no recent turn" if ps_c2_ma50_now_rising
                        else "not rising"
                    ),
                    "g6_followthrough_close_ge2pct": _md_v2_round(close_pct_change_today),
                },
            }

        # Stage gates per variant.
        # S1/S2/S4: must be Plausible or Probable (substring match handles any sub-tier labels).
        # S3: any non-None rating is eligible (Possible Topping keeps) per D-MD-V2-110 —
        #     the Stage 3 prior-uptrend hard gate is already aggressive enough.
        _s1_rating_val = s1.get("rating") if isinstance(s1, dict) else None
        _s2_rating_val = s2.get("rating") if isinstance(s2, dict) else None
        _s3_rating_val = s3.get("rating") if isinstance(s3, dict) else None
        _s4_rating_val = s4.get("rating") if isinstance(s4, dict) else None
        _s1_in = bool(_s1_rating_val is not None and ("Plausible" in str(_s1_rating_val) or "Probable" in str(_s1_rating_val)))
        _s2_in = bool(_s2_rating_val is not None and ("Plausible" in str(_s2_rating_val) or "Probable" in str(_s2_rating_val)))
        _s3_in = bool(_s3_rating_val not in (None, "None"))
        _s4_in = bool(_s4_rating_val is not None and ("Plausible" in str(_s4_rating_val) or "Probable" in str(_s4_rating_val)))

        # Gate probing_bet.stage — clear if the stock does not meet Plausible+ for the
        # relevant stage. "Early"/"Late" PB stages reflect basing/early-uptrend momentum
        # and require S1 Plausible+. "Capital" PB stage reflects price-above-rising-MAs
        # momentum and requires S2 Plausible+. Without this gate, Possible and unrated
        # stocks appear in the probing-bet test display even though they haven't cleared
        # the stage-qualification threshold.
        _pb = fr.get("probing_bet")
        if isinstance(_pb, dict):
            _pb_stage = _pb.get("stage")
            if _pb_stage in ("Early", "Late") and not _s1_in:
                _pb["stage"] = None
            elif _pb_stage == "Capital" and not _s2_in:
                _pb["stage"] = None

        tests["probing_bet_s1"] = ps_build(_ps_sig, _s1_in, "probing_bet_s1", _s1_rating_val)  # S81: 7 tests, OR-turn
        tests["probing_bet_s2"] = _ps_build_50d(_s2_in, "probing_bet_s2", _s2_rating_val)  # D-MD-FILTER-1: Group E (50D)
        tests["speculative_bet_s3"] = ps_build(_ps_sig, _s3_in, "speculative_bet_s3", _s3_rating_val)  # S81
        tests["speculative_bet_s4"] = ps_build(_ps_sig, _s4_in, "speculative_bet_s4", _s4_rating_val)  # S81

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
            "stage_1_persistence": [False] * 11 + [s1["rating"] in ("Possible", "Plausible", "Probable")],
            "stage_2_persistence": [False] * 11 + [s2["rating"] in ("Plausible", "Probable")],
            "stage_3_persistence": [False] * 11 + [s3["rating"] in ("Plausible", "Probable", "Plausible Invalidation", "Probable Invalidation")],
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
    # Hardened write (14-Jul-26 SA): atomic tmp+fsync+verify+os.replace instead
    # of a raw open()+json.dump that a delayed FUSE flush could truncate.
    def _v_th(d):
        assert isinstance(d, dict), "test-history verify: not a dict"
    _safe_write_json(history, TEST_HISTORY_PATH, min_bytes=2, validate=_v_th,
                     indent=None, separators=(",", ":"))


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
    qualifying_ratings = {"Probable", "Plausible", "Probable Invalidation", "Plausible Invalidation"}

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
    # Hardened write (14-Jul-26 SA): atomic instead of raw open()+json.dump.
    def _v_snap(d):
        assert isinstance(d, dict), "stage-snapshots verify: not a dict"
    _safe_write_json(existing, snapshot_path, min_bytes=2, validate=_v_snap,
                     indent=None, separators=(",", ":"))

    print(f"  Daily snapshot saved: {today} ({len(today_stages)} stocks, {len(existing)} total days)")


# ── Stage history delta log (D-MD-V2-STAGEHIST, 17-Jul-26) ───────────────
#
# Richard's ask (17-Jul-26): a permanent, uncapped, delta-only log of every
# stage/gate/test/rating field produced by compute_master_dashboard_screens
# + compute_all_filters, so "which stocks moved into Stage 2 Probable/
# Plausible, and when" can be answered by querying a file instead of
# re-deriving it from memory each time.
#
# Design:
#   - _flatten_stage_fields() walks one ticker's filter-result record and
#     keeps only boolean / rating / stage / tri-state test-outcome leaves
#     (plus a small allowlist of gate-relevant scalar scores, e.g. MM99's
#     score_8pt). Raw numeric test_values and the pipeline's own internal
#     rolling-history arrays (basing_plateau.history, mm99.monthly_history,
#     stage_N_persistence) are deliberately excluded — they are noise for
#     a day-over-day CHANGE log and are already tracked elsewhere.
#   - data/stage-history-20d.json is the permanent, uncapped log. Entry 0
#     (or the oldest entry after a seed) is a full baseline; every entry
#     after that is delta-only: {ticker: {changed_field: new_value}}, and a
#     ticker with zero changed fields on a given day is omitted from that
#     day's "data" dict entirely.
#   - data/.stage-history-latest.json is a small internal cache holding the
#     most recently logged day's FULL flattened state, used only as the
#     diff base for the next day's delta. It is not one of the protected
#     production files (universe.json / filter-results.json / prices.json)
#     — it is new, created by this feature, and safe to overwrite each run
#     via the same atomic _safe_write_json() helper used everywhere else.
#   - compute_and_append_stage_history_delta() is idempotent per calendar
#     date: re-running the pipeline twice on the same day replaces that
#     day's entry rather than appending a duplicate.

STAGE_HISTORY_LOG_PATH = DATA_DIR / "stage-history-20d.json"
STAGE_HISTORY_LATEST_PATH = DATA_DIR / ".stage-history-latest.json"
# The state as of the last DIFFERENT date. Needed because the file above is advanced to today's
# state by the first build of the day, so a second same-day pass had nothing correct to diff
# against and was overwriting the day's record with a near-empty delta (D-PMS-253, 02-Sep-2026).
STAGE_HISTORY_PREVDAY_PATH = DATA_DIR / ".stage-history-prevday.json"

FLATTEN_SKIP_KEYS = {
    "test_values", "history", "monthly_history",
    "stage_1_persistence", "stage_2_persistence",
    "stage_3_persistence", "stage_4_persistence",
    "_note", "note", "retest_counts",
}
FLATTEN_SCALAR_ALLOW_KEYS = {"score_8pt", "score_11", "months_passing", "current_retest_num"}


def _flatten_stage_fields(value, path="", parent_key=None, out=None):
    """Recursively flatten one ticker's filter-result record (the dict that
    holds basing_plateau/probing_bet/mm99/vcp/uptrend_retest + md_v2) down
    to {dotted.path: value} for boolean / rating / stage / test-outcome
    leaves only. See module comment above for what's excluded and why."""
    if out is None:
        out = {}
    if isinstance(value, dict):
        for k, v in value.items():
            if k in FLATTEN_SKIP_KEYS:
                continue
            newpath = f"{path}.{k}" if path else k
            _flatten_stage_fields(v, newpath, parent_key=k, out=out)
        return out
    if isinstance(value, list):
        # No expected list leaves survive FLATTEN_SKIP_KEYS; ignore defensively.
        return out
    if isinstance(value, bool):
        out[path] = value
    elif isinstance(value, str):
        if parent_key in ("rating", "stage", "tests") or path.endswith((".stage", ".rating")):
            out[path] = value
    elif value is None:
        if parent_key == "stage" or path.endswith(".stage"):
            out[path] = value
    elif isinstance(value, (int, float)):
        if parent_key in FLATTEN_SCALAR_ALLOW_KEYS:
            out[path] = value
    return out


def _flatten_all_tickers(filter_results):
    """Return {ticker: {dotted.path: value}} for every stock in filter_results."""
    flat_all = {}
    for fr in filter_results:
        flat_all[fr["ticker"]] = _flatten_stage_fields(fr)
    return flat_all


def _diff_flat_states(prev, now):
    """Compare two {ticker: {path: value}} snapshots. Returns
    {ticker: {path: new_value}} containing ONLY changed/added fields.
    A field present in prev but absent in now is recorded as null
    (path removed / ticker dropped out of a filter this run). A ticker
    with zero differences is omitted entirely."""
    delta = {}
    all_tickers = set(prev.keys()) | set(now.keys())
    for tk in all_tickers:
        p = prev.get(tk, {})
        n = now.get(tk, {})
        changed = {}
        for k in set(p.keys()) | set(n.keys()):
            pv, nv = p.get(k), n.get(k)
            if pv != nv:
                changed[k] = nv if k in n else None
        if changed:
            delta[tk] = changed
    return delta


def _load_stage_history_doc():
    if STAGE_HISTORY_LOG_PATH.exists():
        try:
            with open(STAGE_HISTORY_LOG_PATH, encoding="utf-8") as f:
                d = json.load(f)
            if isinstance(d, dict) and isinstance(d.get("days"), list):
                return d
        except (json.JSONDecodeError, IOError):
            pass
    return {"_meta": {"description": "Permanent uncapped day-over-day delta "
                       "log of every stage/gate/test/rating field. Entry 0 "
                       "is a full baseline; all later entries are delta-only "
                       "(changed fields per ticker vs the prior logged day)."},
            "days": []}


def _load_latest_full_state():
    if not STAGE_HISTORY_LATEST_PATH.exists():
        return None
    try:
        with open(STAGE_HISTORY_LATEST_PATH, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except (json.JSONDecodeError, IOError):
        return None


def _save_latest_full_state(flat_all):
    def _v(d):
        assert isinstance(d, dict), "stage-history-latest verify: not a dict"
    _safe_write_json(flat_all, STAGE_HISTORY_LATEST_PATH, min_bytes=2,
                     validate=_v, indent=None, separators=(",", ":"))


def _load_prevday_full_state():
    """The full state as of the last DIFFERENT calendar date.

    Exists because `.stage-history-latest.json` is advanced to today's state by the first build of
    the day, which left a second same-day pass diffing today against itself. See
    compute_and_append_stage_history_delta() for the full account.
    """
    if not STAGE_HISTORY_PREVDAY_PATH.exists():
        return None
    try:
        with open(STAGE_HISTORY_PREVDAY_PATH, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else None
    except (json.JSONDecodeError, IOError):
        return None


def _save_prevday_full_state(flat_all):
    def _v(d):
        assert isinstance(d, dict), "stage-history-prevday verify: not a dict"
    _safe_write_json(flat_all, STAGE_HISTORY_PREVDAY_PATH, min_bytes=2,
                     validate=_v, indent=None, separators=(",", ":"))


def compute_and_append_stage_history_delta(filter_results, today_str=None):
    """Flatten today's filter_results, diff against the PREVIOUS DAY's full state, and append a
    delta (or baseline, if no prior state exists) entry to data/stage-history-20d.json.

    Idempotent per calendar date — safe to call more than once on the same day (replaces that
    day's entry rather than duplicating it), AND a second call now reproduces the same full
    delta the first one wrote instead of erasing it.

    THE DEFECT THIS FIXES (02-Sep-2026, D-PMS-253). Richard's Stage 2 monitoring had been blocked
    for four consecutive runs since 17-Aug-2026, and the cause was here.

    This log is delta-only: each day records what changed since the day before. The diff base was
    `.stage-history-latest.json`, which this function overwrites with today's state on every call.
    On any evening the build runs twice — the 18:00 European pass and the 22:15 post-US-close pass:

      * 18:00 diffs today against YESTERDAY, finds ~900 changed tickers, writes them.
      * 22:15 diffs today against THIS MORNING'S OWN RESULT, finds almost nothing, and the
        replace-if-present above overwrites the day's entry with that near-empty delta.

    The day's real record was destroyed. Measured 8 for 8 on the historical log: the late pass ran
    on 12, 13, 14, 17, 18, 19, 20 and 25-Aug, whose stored entries hold 13, 16, 15, 10, 9, 9, 9 and
    24 tickers; it did not run on 10, 11, 21-Aug or 01-Sep, whose entries hold 897, 983, 931 and
    974. Then confirmed by PREDICTION: the 01-Sep 15:00 build wrote 974 tickers, the 22:15 pass
    ran, and the stored entry for that date now holds 24.

    Downstream, `scripts/pms_stage2_transitions.py` needs the Stage 2 rating to have changed on at
    least 15 of the last 20 days and refuses to report otherwise — correctly, because an empty
    result would read as "nothing happened on your holdings" when the truth is "we cannot tell".

    THE FIX, and why this shape. Richard approved fixing it and left the method to Watson; two were
    considered. MERGING the second pass's delta into the first's was rejected: it needs merge logic,
    and an interrupted pass can leave a half-written record. Instead a second cache holds the
    previous DAY's state, so a repeat call on the same date diffs from the same base the first call
    used and simply recomputes the identical delta. No merge, and idempotent by construction.

    NOTE ON RECOVERY: this cannot repair the days already overwritten. The monitoring step stays
    blocked until a clean 20-day window rebuilds, roughly three weeks from 02-Sep-2026.
    """
    if today_str is None:
        today_str = date.today().strftime("%Y-%m-%d")

    flat_now = _flatten_all_tickers(filter_results)
    doc = _load_stage_history_doc()
    already_logged_today = any(d.get("date") == today_str for d in doc.get("days", []))

    if already_logged_today:
        # A SECOND pass on the same date. `latest` was advanced to today's state by the first
        # pass, so diffing against it would produce the near-empty delta described above.
        prev = _load_prevday_full_state()
        if prev is None:
            # Only reachable on the first build after this fix ships, if that build happens to be
            # a second pass of the day. Fall back to the old base for one run rather than aborting,
            # and SAY SO: a silent fallback here would look exactly like the bug it replaced.
            prev = _load_latest_full_state()
            print("  stage-history-20d.json: WARNING -- second pass today but no previous-day "
                  "state cached yet, so this delta is measured from this morning's state and will "
                  "understate the day. Self-corrects from the next first-pass build onward.")
        else:
            print(f"  stage-history-20d.json: second pass for {today_str}; diffing from the "
                  f"previous day's state so the day's full record is preserved.")
    else:
        # FIRST pass for this date. `latest` still holds the previous day's state, which is both
        # the correct diff base now and the base any second pass today will need, so promote it
        # BEFORE it gets overwritten below.
        prev = _load_latest_full_state()
        if prev is not None:
            _save_prevday_full_state(prev)

    if prev is None:
        entry = {"date": today_str, "type": "baseline", "data": flat_now}
    else:
        delta = _diff_flat_states(prev, flat_now)
        entry = {"date": today_str, "type": "delta", "data": delta}

    # Idempotent replace-if-present.
    doc["days"] = [d for d in doc.get("days", []) if d.get("date") != today_str]
    doc["days"].append(entry)

    def _v_doc(d):
        assert isinstance(d.get("days"), list) and len(d["days"]) >= 1, \
            "stage-history-20d verify: no days recorded"
    _safe_write_json(doc, STAGE_HISTORY_LOG_PATH, min_bytes=2, validate=_v_doc,
                     indent=None, separators=(",", ":"))
    _save_latest_full_state(flat_now)

    n_changed_tickers = len(entry["data"])
    print(f"  stage-history-20d.json: appended {entry['type']} entry for "
          f"{today_str} ({n_changed_tickers} ticker(s) with changes, "
          f"{len(doc['days'])} day(s) total in log)")
    return entry


def main():
    parser = argparse.ArgumentParser(description="Master Dashboard data pipeline")
    parser.add_argument("--full-refresh", action="store_true", help="Force full re-pull from yfinance")
    parser.add_argument("--no-reseed", action="store_true",
                        help="Skip tonight's re-seed rotation. For a SECOND run on "
                             "the same calendar date (the 22:15 post-US-close pass), "
                             "where the rotation has already been done by the 18:00 "
                             "build and repeating it only doubles provider load.")
    parser.add_argument("--full-universe", action="store_true", help="Use full 976-stock watchlist instead of alpha universe")
    parser.add_argument("--with-history", action="store_true", help="Compute historical stages at T-1/T-5/T-22 for CHANGES tab")
    parser.add_argument("--allow-unmapped", action="store_true", help="Allow watchlist stocks with no canonical taxonomy (default: abort)")
    parser.add_argument("--strict-integrity", action="store_true", help="Abort on any system-integrity audit warning (default: warn-only)")
    parser.add_argument("--strict-divergence", action="store_true", help="Abort if the canonical divergence guard finds errors (default: warn-only)")
    parser.add_argument("--seed-test-history", type=int, default=0, metavar="N", help="MD-V2-TESTS-S27-MARKER: one-off - back-create N days of deployment-test history (Richard cap: 20 per S39 T-C, MD-V2-S39-T-C-SEED-DEPTH-20)")
    args = parser.parse_args()

    # Bucket 2: disk-space pre-check on the drive where data outputs live (cross-platform).
    if _pg is not None:
        _pg.safe_guard(_pg.check_disk_space, required_mb=200,
                       label="generate_master_data (prices + filter-results)",
                       check_path=str(DATA_DIR), floor_mb=500)

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

    # ── Pre-flight: canonical divergence guard (D13; warn-only by default) ──
    # Confirms the dashboard consumers still match universe-master.json (the
    # single source of truth). Warn-only first; flip to --strict-divergence
    # after a clean week to make divergence blocking.
    print("\n── Pre-flight: canonical divergence guard ──")
    guard_script = SCRIPT_DIR / "divergence_guard.py"
    if guard_script.exists():
        gcmd = [sys.executable, str(guard_script), "--quiet"]
        if args.strict_divergence:
            gcmd.append("--strict")
        grc = subprocess.call(gcmd)
        if grc == 2:
            print("  Divergence guard reported ERRORS above.")
            if args.strict_divergence:
                print("  --strict-divergence set — aborting.")
                sys.exit(1)
            else:
                print("  Continuing in warn-only mode. Re-run with --strict-divergence to enforce.")
        elif grc == 1:
            print("  Divergence guard reported warnings (non-blocking).")
        else:
            print("  Divergence guard clean.")
    else:
        print(f"  Skipping — divergence_guard.py not found at {guard_script}")

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
        # Shape stability (14-Jul-26 SA): the 05:30 extract writes universe.json
        # WITH cohort/cohort_name (derive_universe.py, from canonical
        # universe-master.json); this 18:00 build rewrote it from the
        # pullback-watchlist, which lacks those two fields, silently dropping
        # cohort every evening. Join them back from the canonical source so
        # universe.json carries a single stable 10-field shape whichever job ran
        # last. Non-fatal: proceed without enrichment if the master is unreadable.
        try:
            _umj = SCRIPT_DIR.parent.parent / "databases" / "universe-master.json"
            _cohort_by_ticker = {}
            if _umj.exists():
                with open(_umj, encoding="utf-8") as _f:
                    for _s in json.load(_f).get("stocks", []):
                        _cohort_by_ticker[_s.get("ticker")] = (
                            _s.get("cohort_number", ""), _s.get("cohort_name", ""))
            _enriched = 0
            for _st in universe["stocks"]:
                _c = _cohort_by_ticker.get(_st.get("ticker"))
                if _c is not None:
                    _st.setdefault("cohort", _c[0])
                    _st.setdefault("cohort_name", _c[1])
                    _enriched += 1
                else:
                    _st.setdefault("cohort", "")
                    _st.setdefault("cohort_name", "")
            print(f"  Cohort enrichment: {_enriched}/{len(universe['stocks'])} matched to universe-master")
        except Exception as _coh_err:
            print(f"  WARNING: cohort enrichment skipped (non-fatal): {_coh_err}")
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        # Hardened write (fix 02-Jul-26): was a raw open()+json.dump with no
        # verify and an unconditional success message; a delayed flush could
        # truncate universe.json after this reported "Saved".
        _n = len(universe["stocks"])
        def _verify(d, _n=_n):
            assert isinstance(d.get("stocks"), list) and len(d["stocks"]) == _n, \
                "universe.json verify failed: expected %d stocks" % _n
        _safe_write_json(universe, UNIVERSE_PATH, min_bytes=1000, validate=_verify)
        print(f"  Saved as universe.json ({_n} stocks) -- fsync+atomic+verified")
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

    # ── Self-healing exclusion: every watchlist ticker must have a yfinance ticker ──
    # Added 23-Jul-26, revised same day (SA session) after the Liberty Global incident:
    # fetch_all_data() keys entirely off yfinance_ticker, so a blank value means the
    # ticker is passed to yfinance as "", the fetch returns 0 rows, and
    # build_prices_json's "SKIP {ticker} — insufficient data (0 rows)" line silently
    # drops the stock from prices.json and every file derived from it, with no error
    # anywhere. 14 stocks (incl. Liberty Global / LBTYA-US) were missing from the
    # dashboard for this exact reason, undetected until Richard noticed by inspection.
    #
    # The first version of this check hard-aborted the whole build on any blank
    # ticker. Richard correctly pointed out that just trades a silent failure for a
    # bigger one: one incomplete new stock added to Notion would stop the ENTIRE
    # dashboard refreshing for all 990 other stocks too. The actual structural fix is
    # resolve_missing_yfinance_tickers.py, which runs earlier in the daily chain and
    # auto-resolves the large majority of blanks against live yfinance data (verified
    # by both a real price-history check and a company-name match, not guessed
    # blindly), writing the fix back to Notion so it is permanent. What follows here
    # is the belt-and-braces safety net for anything that resolver could not fix (or
    # if it did not run): those tickers are EXCLUDED from this run's fetch only, the
    # gap is flagged to the shared needs-attention file so it stays visible, and the
    # rest of the build proceeds normally for every other stock.
    no_yf = [s for s in universe["stocks"] if not (s.get("yfinance_ticker") or "").strip()]
    if no_yf:
        tickers = [s["ticker"] for s in no_yf]
        print()
        print("=" * 60)
        print(f"WARNING: {len(tickers)} watchlist ticker(s) have no yfinance_ticker set:")
        for tk in tickers:
            print(f"  - {tk}")
        print("  Excluding from this run's price fetch (everything else proceeds).")
        print("  Run resolve_missing_yfinance_tickers.py, or fix the 'yfinance_ticker'")
        print("  property on each page in the Notion Stocks DB directly.")
        print("=" * 60)
        try:
            needs_attention_path = SCRIPT_DIR.parent.parent / "databases" / "needs-attention-yfinance.json"
            na = {}
            if needs_attention_path.exists():
                try:
                    with open(needs_attention_path, encoding="utf-8") as f:
                        na = json.load(f)
                except Exception:
                    na = {}
            now = datetime.now().isoformat() + "Z"
            for tk in tickers:
                na[tk] = {"reason": "blank yfinance_ticker survived the auto-resolver (or resolver "
                                    "did not run) -- excluded from generate_master_data.py's price "
                                    "fetch this run", "flagged_at": now}
            tmp = str(needs_attention_path) + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(na, f, indent=2, sort_keys=True)
            os.replace(tmp, needs_attention_path)
        except Exception as e:
            print(f"WARNING: could not write needs-attention file: {e}")
        exclude = {s["ticker"] for s in no_yf}
        universe["stocks"] = [s for s in universe["stocks"] if s["ticker"] not in exclude]

    # Fetch data — REAL market data only. No synthetic fallback (D-PRICE-INTEGRITY, 22-May-26).
    print("\n── Fetching yfinance data ──")
    try:
        import yfinance as _yf_probe  # noqa: F401 — presence probe only
    except ImportError:
        print("=" * 64)
        print("PRICE-INTEGRITY FATAL: yfinance is not available in this environment.")
        print("  Real prices cannot be fetched here (e.g. the Cowork sandbox).")
        print("  This pipeline NEVER fabricates prices and will NOT overwrite the")
        print("  existing real prices.json. Nothing was written.")
        print("  -> Run on Richard's PC (the scheduled yfinance job), OR use")
        print("     pipeline_from_chartdata.py for an in-sandbox rebuild from real")
        print("     (lagged) chart data.")
        print("=" * 64)
        sys.exit(3)
    raw_data = fetch_all_data(universe, full_refresh=args.full_refresh,
                              no_reseed=args.no_reseed)
    data_source = "yfinance"

    # Guard: a near-empty fetch must never overwrite good data.
    _n_with_rows = sum(1 for v in raw_data.values() if v)
    if _n_with_rows < max(1, int(0.5 * len(universe["stocks"]))):
        print("=" * 64)
        print(f"PRICE-INTEGRITY FATAL: only {_n_with_rows} tickers returned data;")
        print("  the fetch looks broken. Refusing to overwrite real prices.json.")
        print("=" * 64)
        sys.exit(3)

    # Get benchmark data
    benchmark_rows = raw_data.get(BENCHMARK_TICKER, [])
    if not benchmark_rows:
        print("  WARNING: No benchmark data — RS calculations will be affected")

    # Build prices.json
    print("\n── Building prices.json ──")
    _dropped = []
    prices = build_prices_json(universe, raw_data, benchmark_rows, dropped=_dropped)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # ── D-MD-COVERAGE-2026-08-04 (G3): universe-to-prices reconciliation ──
    # universe.json held 994 stocks and prices.json held 978, and NOTHING had
    # ever compared the two. That 16-stock gap hid Bally's Intralot from every
    # dashboard while it sat correctly in the source of record, the universe
    # file, the watchlist and the chart files. This closes it permanently: the
    # gap is now named, categorised, written to disk and printed on every run,
    # and it catches drop causes nobody has thought of yet.
    _emitted = {p["ticker"] for p in prices}
    _wanted = [s["ticker"] for s in universe["stocks"]]
    _accounted = {d["ticker"] for d in _dropped}
    for _tk in _wanted:
        if _tk not in _emitted and _tk not in _accounted:
            _dropped.append({"ticker": _tk, "yfinance_ticker": "", "company_name": "",
                             "rows": None, "category": "unexplained",
                             "reason": "absent from prices.json with no recorded reason — "
                                       "a drop path exists that this guard does not know about"})
    _by_cat = {}
    for _d in _dropped:
        _by_cat.setdefault(_d["category"], []).append(_d)
    _coverage = {
        "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "universe_count": len(_wanted),
        "emitted_count": len(_emitted),
        "dropped_count": len(_dropped),
        "coverage_pct": round(100.0 * len(_emitted) / max(1, len(_wanted)), 2),
        "by_category": {k: len(v) for k, v in sorted(_by_cat.items())},
        "dropped": sorted(_dropped, key=lambda d: (d["category"], d["ticker"])),
    }
    try:
        _safe_write_json(_coverage, DATA_DIR / "universe-coverage.json", min_bytes=50)
    except Exception as _e:
        print(f"  WARNING: could not write universe-coverage.json: {_e}")

    print()
    print("=" * 70)
    print("UNIVERSE COVERAGE — %d of %d stocks reached prices.json (%.1f%%)"
          % (len(_emitted), len(_wanted), _coverage["coverage_pct"]))
    print("=" * 70)
    if _dropped:
        for _cat in sorted(_by_cat):
            print("  %s (%d):" % (_cat.upper(), len(_by_cat[_cat])))
            for _d in sorted(_by_cat[_cat], key=lambda d: d["ticker"]):
                print("    %-12s %-14s %s"
                      % (_d["ticker"], _d.get("yfinance_ticker") or "-", _d["reason"]))
        if _by_cat.get("unexplained"):
            print()
            print("  *** UNEXPLAINED DROPS PRESENT. A stock left the pipeline by a route")
            print("      this guard does not model. Investigate before trusting today's")
            print("      screens: the same silence hid Bally's Intralot for months.")
        print("  Full detail: data/universe-coverage.json")
    else:
        print("  No stock was dropped. Universe and prices.json agree exactly.")
    print()

    # PRICE-INTEGRITY GATE (22-May-26): provenance + sanity-vs-prior + atomic write.
    import importlib as _il
    sys.path.insert(0, str(SCRIPT_DIR))
    _pi = _il.import_module("price_integrity")
    if not _pi.is_real_source(data_source):
        print(f"PRICE-INTEGRITY FATAL: refusing to write non-real source {data_source!r}.")
        sys.exit(3)
    _prices_path = DATA_DIR / "prices.json"
    _prior = None
    if _prices_path.exists():
        try:
            with open(_prices_path) as _pf:
                _prior = json.load(_pf).get("stocks")
        except Exception:
            _prior = None
    _ok, _reasons = _pi.sanity_check(prices, _prior)
    # Print INFO notes (large date-gap warnings) even on success.
    _info_notes = [r for r in _reasons if r.startswith("INFO:")]
    if _info_notes:
        print("PRICE-INTEGRITY NOTES:")
        for _n in _info_notes:
            print(f"    {_n}")
    if not _ok:
        print("=" * 64)
        print("PRICE-INTEGRITY FATAL: new prices failed sanity vs prior real data:")
        for _r in _reasons:
            if not _r.startswith("INFO:"):
                print(f"    - {_r}")
        print("  Keeping the existing prices.json untouched. Nothing overwritten.")
        print("=" * 64)
        sys.exit(3)
    _pi.atomic_write_json(str(_prices_path), {
        "_meta": {
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "count": len(prices),
            "source": data_source,
            "real": True,
        },
        "stocks": prices,
    })
    print(f"  Written {len(prices)} stocks to data/prices.json (source={data_source}, real)")

    # Last-known-good snapshot (structural protection, 16-Jun-26 D-STRUCT-01).
    # Copies prices.json to .last-known-good immediately after atomic write.
    # This is the authoritative repair source if the main file is later corrupted
    # by FUSE — prevents repair falling back to weeks-old dated backups. Non-fatal.
    try:
        import shutil as _shutil_pi
        _lkg_prices_path = DATA_DIR / "prices.json.last-known-good"
        _shutil_pi.copy2(str(_prices_path), str(_lkg_prices_path))
        print(f"  LKG snapshot: data/prices.json.last-known-good ({_prices_path.stat().st_size:,} bytes)")
    except Exception as _lkg_err:
        print(f"  WARNING: prices.json LKG snapshot failed (non-fatal): {_lkg_err}")

    # Compute filters
    print("\n── Computing filters ──")
    filter_results = compute_all_filters(prices)
    print("\n── Computing MD V2 screens ──")
    filter_results = compute_master_dashboard_screens(prices, filter_results)
    print(f"  Attached md_v2 to {len(filter_results)} stocks")

    # MD-V2-S2-PERSIST-RATED-MARKER: 12-month Stage 2 persistence backfill
    print("\n-- Computing Stage 2 monthly persistence (12-month backfill) --")
    _s2_monthly = compute_s2_monthly_persistence(universe, raw_data, benchmark_rows)
    _fr_by_tk = {r['ticker']: r for r in filter_results}
    _injected = 0
    for _tk, _monthly_ratings in _s2_monthly.items():
        if _tk in _fr_by_tk:
            _r = _fr_by_tk[_tk]
            if 'md_v2' in _r and 'persistence' in _r.get('md_v2', {}):
                _r['md_v2']['persistence']['stage_2_persistence_rated'] = _monthly_ratings
                _injected += 1
    print(f"  Backfilled Stage 2 persistence for {_injected} stocks ({len(_s2_monthly)} computed)")

    # -- MD-V2-TESTS-S27-MARKER: persist-and-append test history (D-MD-V2-67) --
    print("\n-- Test history (persist-and-append) --")
    filter_results = apply_test_history(
        filter_results,
        seed=args.seed_test_history,
        raw_data=raw_data,
        universe=universe,
        benchmark_rows=benchmark_rows,
    )
    # Hardened write (fix 09-Jul-26): was a raw open()+json.dump with no fsync
    # and only a post-hoc verify. filter-results.json is the largest raw writer
    # and truncated near-completion on nearly every nightly run (16/26/29/30-Jun,
    # 1/2/4/6/7/8-Jul) via delayed FUSE flush of the unflushed tail. Every writer
    # already converted to _safe_write_json (universe, universe-master, prices)
    # stopped truncating; this was the one still raw. Now atomic tmp+fsync+verify
    # +os.replace, matching the universe.json write above.
    _fr_payload = {
        "_meta": {
            "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "count": len(filter_results),
            "filters": ["basing_plateau", "probing_bet", "mm99", "vcp", "uptrend_retest"],
            "notes": "VCP pattern detection pending Phase 2. UTR V2 lifecycle stages live (27-Apr-26)."
        },
        "stocks": filter_results
    }
    _fr_n = len(filter_results)
    def _verify_fr(d, _n=_fr_n):
        assert isinstance(d.get("stocks"), list) and len(d["stocks"]) == _n, \
            "filter-results.json verify failed: expected %d stocks" % _n
    _safe_write_json(_fr_payload, DATA_DIR / "filter-results.json",
                     min_bytes=1_000_000, validate=_verify_fr)
    print(f"  Written {len(filter_results)} stocks to data/filter-results.json -- fsync+atomic+verified")

    # Stage history delta log (D-MD-V2-STAGEHIST, 17-Jul-26) — called right
    # after filter-results.json is written, per Richard's spec. Non-fatal:
    # a failure here must never block the main pipeline output.
    print("\n── Stage history delta log ──")
    try:
        compute_and_append_stage_history_delta(filter_results)
    except Exception as _sh_err:
        print(f"  WARNING: stage-history-20d.json update failed (non-fatal): {_sh_err}")

    # Bucket 2: verify-after-write on filter-results.json (kind=json + regression band).
    if _pg is not None:
        _pg.safe_guard(_pg.verify_output, str(DATA_DIR / "filter-results.json"),
                       min_bytes=1_000_000, kind="json",
                       history_path=HISTORY_PATH)

    # Last-known-good snapshot (structural protection, 16-Jun-26 D-STRUCT-01).
    # Copies filter-results.json to .last-known-good only AFTER verify_output
    # has confirmed the file is valid JSON. This is the authoritative repair
    # source for any subsequent FUSE corruption between nightly runs. Non-fatal.
    try:
        import shutil as _shutil_fr
        _fr_main_path = DATA_DIR / "filter-results.json"
        _fr_lkg_path  = DATA_DIR / "filter-results.json.last-known-good"
        _shutil_fr.copy2(str(_fr_main_path), str(_fr_lkg_path))
        print(f"  LKG snapshot: data/filter-results.json.last-known-good ({_fr_main_path.stat().st_size:,} bytes)")
    except Exception as _lkg_fr_err:
        print(f"  WARNING: filter-results.json LKG snapshot failed (non-fatal): {_lkg_fr_err}")


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
        # Hardened write (14-Jul-26 SA): atomic instead of raw open()+json.dump.
        _fh_payload = {
            "_meta": {
                "generated": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "offsets": [0, 1, 5, 22],
                "offset_labels": ["T-0", "T-1", "T-5", "T-22"],
                "description": "Stage assignments at 4 time points for CHANGES tab",
            },
            "stages": history,
            "changes": changes,
        }
        def _v_fh(d):
            assert isinstance(d.get("stages"), dict), "filter-history verify"
        _safe_write_json(_fh_payload, DATA_DIR / "filter-history.json",
                         min_bytes=2, validate=_v_fh)
        print(f"\n  Written filter-history.json — {len(history)} time points")
        print(f"  Total changes detected: {len(changes)}")

        # Quick summary of changes per offset
        for offset_label in ["T-1", "T-5", "T-22"]:
            offset_changes = [c for c in changes if c["offset_label"] == offset_label]
            ups = sum(1 for c in offset_changes if c["direction"] == "upgrade")
            downs = sum(1 for c in offset_changes if c["direction"] == "downgrade")
            print(f"  {offset_label}: {ups} upgrades, {downs} downgrades")

    print("\nDone.")


# ── SETTLED-BAR SELF-TEST (D-MD-SETTLED-BAR-2026-08-11) ───────────────────
#
# Run with:  python generate_master_data.py --selftest-settled-bar
#
# It makes NO network call. Every venue answer is injected, so the test pins the
# WIRING -- does the real last bar date actually reach the rule, and does the
# rule's answer actually reach the row filter -- rather than pinning whatever the
# market happened to be doing when it ran. market_session.py has its own
# self-test for the rule itself; this one exists because the rule being right and
# the rule being reached are different claims, and only the second one failed
# three handoffs in a row.


class _FakeMS(object):
    """Stands in for market_session. Records every call it receives."""

    def __init__(self, open_, live_date):
        self._open = open_
        self._live = live_date
        self.calls = []

    def should_drop_today(self, yf_ticker, bar_date=None, timeout=15):
        self.calls.append((yf_ticker, bar_date))
        if not self._open:
            return False
        if bar_date is None:
            return True
        return self._live is None or bar_date >= self._live

    def session_for(self, yf_ticker, timeout=15):
        return {"open": self._open, "live_date": self._live}

    def cache_report(self):
        return ""


class _FakeYF(object):
    """Minimal yfinance stand-in returning a fixed OHLCV frame."""

    def __init__(self, dates):
        self._dates = dates

    def Ticker(self, symbol):
        outer = self

        class _T(object):
            def history(self, period=None):
                return _FakeHist(outer._dates)
        return _T()


class _FakeHist(object):
    def __init__(self, dates):
        self._dates = dates

    def __len__(self):
        return len(self._dates)

    def iterrows(self):
        import datetime as _dt
        for d in self._dates:
            class _Idx(object):
                def __init__(self, s):
                    self._s = s

                def strftime(self, fmt):
                    return self._s
            yield _Idx(d), {"Open": 10.0, "High": 11.0, "Low": 9.0,
                            "Close": 10.5, "Volume": 1000}


def _install_fake_ms(fake):
    global _MS_MODULE, _MS_TRIED
    _MS_MODULE = fake
    _MS_TRIED = True


def selftest_settled_bar():
    global _MS_MODULE, _MS_TRIED
    fails = []

    def ck(name, cond):
        print("  %-70s %s" % (name, "ok" if cond else "FAIL"))
        if not cond:
            fails.append(name)

    DATES = ["2026-08-07", "2026-08-10", "2026-08-11"]
    TODAY = "2026-08-11"

    print("the wiring: does the REAL last bar date reach the rule?")
    fake = _FakeMS(open_=True, live_date="2026-08-11")
    _install_fake_ms(fake)
    rows = _fetch_ticker(_FakeYF(DATES), "FLUT", "1mo", "FLUT-US", TODAY)
    ck("should_drop_today was called at all", len(fake.calls) == 1)
    ck("it was called with the symbol, not the label",
       fake.calls and fake.calls[0][0] == "FLUT")
    ck("it was called with the REAL last bar date, not None",
       fake.calls and fake.calls[0][1] == "2026-08-11")
    ck("the unsettled bar was dropped", [r["date"] for r in rows] == DATES[:-1])

    print("an open venue whose unsettled date is NOT our today")
    # 23:30 UK: the running US session is still dated the previous day.
    fake = _FakeMS(open_=True, live_date="2026-08-10")
    _install_fake_ms(fake)
    rows = _fetch_ticker(_FakeYF(DATES), "FLUT", "1mo", "FLUT-US", "2026-08-11")
    ck("both the 10th and the 11th are dropped, keyed on the VENUE date",
       [r["date"] for r in rows] == ["2026-08-07"])

    print("a closed venue keeps everything")
    fake = _FakeMS(open_=False, live_date=None)
    _install_fake_ms(fake)
    rows = _fetch_ticker(_FakeYF(DATES), "AZA.ST", "1mo", "AZA-SE", TODAY)
    ck("a settled series is not trimmed", [r["date"] for r in rows] == DATES)
    ck("and the bar date still reached the rule",
       fake.calls and fake.calls[0][1] == "2026-08-11")

    print("MUTATION: break the wiring and the test must NOTICE")
    # If the bar date stopped being passed, _FakeMS returns True unconditionally
    # for an open venue -- and, critically, ALSO for a closed one under the real
    # module. Prove the closed-venue case is the one that catches it.
    fake = _FakeMS(open_=False, live_date=None)
    _install_fake_ms(fake)
    ck("a closed venue with NO bar date would still not drop (rule is short-circuit)",
       fake.should_drop_today("AZA.ST", bar_date=None) is False)
    fake_open = _FakeMS(open_=True, live_date="2026-08-11")
    ck("an OPEN venue with no bar date drops UNCONDITIONALLY -- the named risk",
       fake_open.should_drop_today("FLUT", bar_date=None) is True)
    ck("...and with a settled bar date it does NOT drop, which is the whole point",
       fake_open.should_drop_today("FLUT", bar_date="2026-08-10") is False)

    print("failing direction: no market_session module at all")
    _MS_MODULE = None
    _MS_TRIED = True
    rows = _fetch_ticker(_FakeYF(DATES), "FLUT", "1mo", "FLUT-US", TODAY)
    ck("an unimportable guard drops today's bar rather than trusting it",
       [r["date"] for r in rows] == DATES[:-1])

    print("explicit overrides still honoured (used by nothing in production)")
    _install_fake_ms(_FakeMS(open_=False, live_date=None))
    rows = _fetch_ticker(_FakeYF(DATES), "FLUT", "1mo", "FLUT-US", TODAY,
                         drop_today=True)
    ck("drop_today=True drops today regardless of the venue",
       [r["date"] for r in rows] == DATES[:-1])
    _install_fake_ms(_FakeMS(open_=True, live_date="2026-08-11"))
    rows = _fetch_ticker(_FakeYF(DATES), "FLUT", "1mo", "FLUT-US", TODAY,
                         drop_today=False)
    ck("drop_today=False keeps today regardless of the venue",
       [r["date"] for r in rows] == DATES)

    print("the REAL market_session, venue cache seeded by hand, still no network")
    # A fake that I wrote can only ever confirm my model of the rule. This phase
    # runs the SHIPPED rule, with its per-venue cache pre-seeded so session_for()
    # never reaches the network. It is the difference between "my stand-in behaves
    # as I expect" and "the code that actually runs behaves as I expect".
    _MS_MODULE = None
    _MS_TRIED = False
    real = _market_session()
    if real is None:
        print("    SKIPPED — market_session.py is not importable from this path.")
        print("    Run this self-test from master-dashboard/scripts/ to exercise it.")
    else:
        real._CACHE.clear()
        real._CACHE[""] = {"ok": True, "open": True, "live_date": "2026-08-11",
                           "exchange": "NYSE (seeded)", "currency": "USD",
                           "detail": "seeded by selftest"}
        real._CACHE["ST"] = {"ok": True, "open": False, "live_date": None,
                             "exchange": "Stockholm (seeded)", "currency": "SEK",
                             "detail": "seeded by selftest"}
        rows = _fetch_ticker(_FakeYF(DATES), "FLUT", "1mo", "FLUT-US", TODAY)
        ck("REAL rule: an open US tape drops the unsettled bar",
           [r["date"] for r in rows] == DATES[:-1])
        rows = _fetch_ticker(_FakeYF(DATES), "AZA.ST", "1mo", "AZA-SE", TODAY)
        ck("REAL rule: a closed Stockholm keeps every bar",
           [r["date"] for r in rows] == DATES)
        ck("no venue was probed over the network (cache untouched by new keys)",
           set(real._CACHE) == {"", "ST"})
        ck("REAL rule: the unconditional-drop trap is real, so the wiring matters",
           real.should_drop_today("FLUT", bar_date=None) is True
           and real.should_drop_today("FLUT", bar_date="2026-08-10") is False)
        real._CACHE.clear()

    print("the retired heuristics are GONE, not merely unused")
    ck("LATE_CLOSING_LABEL_SUFFIXES no longer exists",
       "LATE_CLOSING_LABEL_SUFFIXES" not in globals())
    ck("EU_MARKETS_CLOSED_HOUR no longer exists",
       "EU_MARKETS_CLOSED_HOUR" not in globals())

    _MS_MODULE = None
    _MS_TRIED = False
    print()
    print("SETTLED-BAR SELF-TEST %s"
          % ("PASSED" if not fails else "FAILED: %s" % fails))
    return 0 if not fails else 1


if __name__ == "__main__":
    if "--selftest-settled-bar" in sys.argv:
        sys.exit(selftest_settled_bar())
    main()
