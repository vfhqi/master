#!/usr/bin/env python3
"""
patch_md_v2_tests_s27_2026_05_14.py
===================================
SESSION 27 - Capital deployment tests tab RESTRUCTURE (pipeline side).

Targets: scripts/generate_master_data.py  (the LIVE inlined screens copy).

Implements D-MD-V2-64 .. D-MD-V2-68:
  - D-MD-V2-64: split the single `vcp` deployment test into `vcp_deploy_s1`
    + `vcp_deploy_s2` (stage-gated forms). Tests tab = 4 tests now:
    ma_retest_upwards / vcp_deploy_s1 / vcp_deploy_s2 / probing_bet.
  - D-MD-V2-65: each test displayed "in totality" - carries its related
    setup's test columns + trigger columns. Each VCP test gets its OWN
    VCP columns (gates differ).
  - D-MD-V2-66: 4-stage info block - NO pipeline work (stage ratings are
    already at md["stage_1"].rating .. md["stage_4"].rating; the dashboard
    reads them directly).
  - D-MD-V2-67: L5D / L20D recent-trigger windows. Implemented as Richard's
    persist-and-append architecture (NOT 20x-per-run recompute):
      * new data/test-history.json keyed by date; pipeline appends today's
        per-stock per-test `qualifies` booleans every run (cost = 1 day).
      * a one-off SEED routine (6 days, per Richard's cap) re-evaluates the
        4 deployment tests at recent historical bar slices to back-create
        history. Runs only when invoked with --seed-test-history; the daily
        path never recomputes.
      * window fields (fired_l5d / fired_l20d / days_since_fired) are
        computed from the history file and written ONTO each test record in
        filter-results.json, so the dashboard reads them via the existing
        s.md_v2.tests[key] path - no new MASTER_DATA wiring.
  - D-MD-V2-68: pipeline + dashboard patcher pair; this is the pipeline half.

Patcher discipline (D-MD-V2-43 / S25 doctrine):
  - heredoc-authored, validated beside the patcher, atomic cp, MD5 byte-verify
  - idempotent (marker check), pre-write backup, atomic write at END
  - post-write verification block
  - targets the LIVE inlined copy, never the dead _md_v2_screens.py sidecar

Run (Windows-side):
  cd C:\\Users\\richb\\Documents\\COWORK\\master-dashboard
  python scripts\\patch_md_v2_tests_s27_2026_05_14.py
"""

import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
TARGET = SCRIPT_DIR / "generate_master_data.py"
MARKER = "MD-V2-TESTS-S27-MARKER"

# ----------------------------- payload blocks -----------------------------

# EDIT 1 - replaces the entire "# 3 TESTS" section body.
# Anchored between the section banner and the `md["tests"] = tests` line.
# Anchor on the unique, pure-ASCII 'tests = {}' line ONLY. The box-drawing
# banner above it (3 TESTS ...) is left in place; EDIT_1_NEW does not re-emit
# it. This avoids embedding UTF-8 box chars / em-dash in the patcher.
ANCHOR_1_START = '        tests = {}\n'

ANCHOR_1_END = '''        md["tests"] = tests
'''

EDIT_1_NEW = r'''        # MD-V2-TESTS-S27-MARKER: 4 CAPITAL DEPLOYMENT TESTS (was 3).
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
        }

        # Back-compat aliases - downstream / historical readers may still
        # reference the pre-S27 keys. Keep them pointing at sensible values.
        utr_stage = fr.get("uptrend_retest", {}).get("stage")
        tests["uptrend_retest"] = {"stage": utr_stage, "qualifies": mr_qualifies}
        tests["vcp"] = {
            "qualifies": bool(vd1_qualifies or vd2_qualifies),
            "_note": "S27: vcp test split into vcp_deploy_s1 + vcp_deploy_s2; this alias = OR of both.",
        }

        md["tests"] = tests
'''

# EDIT 2 - new functions, inserted just before `def _save_daily_snapshot(`.
ANCHOR_2 = 'def _save_daily_snapshot(filter_results):'

EDIT_2_NEW = r'''# -- MD-V2-TESTS-S27-MARKER: persist-and-append test history (D-MD-V2-67) --
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
# Per Richard 14-May-26: seed depth capped at 6 days for the shake-out
# phase (cheap to regenerate if a test definition changes); the format and
# the dashboard degradation handle up to 20, so a later full backfill is
# just a deeper seed run, no re-architecting.

TEST_HISTORY_PATH = DATA_DIR / "test-history.json"

# The 4 live deployment tests whose qualify-history we persist.
DEPLOYMENT_TEST_KEYS = ["ma_retest_upwards", "vcp_deploy_s1", "vcp_deploy_s2", "probing_bet"]

# Window sizes (trading days). Format supports up to 20; seed depth is a
# separate, smaller knob (Richard: 6 for now).
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


'''

# EDIT 3 - wire apply_test_history into main(), AND add the --seed-test-history
# CLI flag. Two sub-edits.

# 3a: add the argparse flag, just after the --strict-integrity arg line.
ANCHOR_3A = '    parser.add_argument("--strict-integrity", action="store_true", help="Abort on any system-integrity audit warning (default: warn-only)")\n'
EDIT_3A_NEW = ANCHOR_3A + '    parser.add_argument("--seed-test-history", type=int, default=0, metavar="N", help="MD-V2-TESTS-S27-MARKER: one-off - back-create N days of deployment-test history (Richard cap: 6)")\n'

# 3b: call apply_test_history after compute_master_dashboard_screens, before
# the filter-results.json write. Anchor on the screens-attached print line.
ANCHOR_3B = '    print(f"  Attached md_v2 to {len(filter_results)} stocks")\n'
EDIT_3B_NEW = ANCHOR_3B + '''
    # -- MD-V2-TESTS-S27-MARKER: persist-and-append test history (D-MD-V2-67) --
    print("\\n-- Test history (persist-and-append) --")
    filter_results = apply_test_history(
        filter_results,
        seed=args.seed_test_history,
        raw_data=raw_data,
        universe=universe,
        benchmark_rows=benchmark_rows,
    )
'''


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def main():
    if not TARGET.exists():
        print("ERROR: target not found: %s" % TARGET)
        sys.exit(1)

    src = TARGET.read_text(encoding="utf-8")

    # -- idempotency --
    if MARKER in src:
        print("SKIP: %s already present in %s - patch already applied." % (MARKER, TARGET.name))
        sys.exit(0)

    # -- locate all anchors BEFORE mutating anything --
    problems = []
    if ANCHOR_1_START not in src:
        problems.append("ANCHOR_1_START (# 3 TESTS section banner) not found")
    if ANCHOR_1_END not in src:
        problems.append('ANCHOR_1_END (md["tests"] = tests) not found')
    if ANCHOR_2 not in src:
        problems.append("ANCHOR_2 (def _save_daily_snapshot) not found")
    if ANCHOR_3A not in src:
        problems.append("ANCHOR_3A (--strict-integrity arg) not found")
    if ANCHOR_3B not in src:
        problems.append("ANCHOR_3B (Attached md_v2 print) not found")
    if problems:
        print("ERROR: anchor location failed - NOT writing:")
        for p in problems:
            print("  - %s" % p)
        sys.exit(1)

    # EDIT 1 - replace the section body. Slice from ANCHOR_1_START through
    # ANCHOR_1_END inclusive and substitute.
    i_start = src.index(ANCHOR_1_START)
    i_end = src.index(ANCHOR_1_END, i_start) + len(ANCHOR_1_END)
    old_block = src[i_start:i_end]
    if old_block == EDIT_1_NEW:
        print("ERROR: EDIT 1 would be a no-op")
        sys.exit(1)
    new_src = src[:i_start] + EDIT_1_NEW + src[i_end:]

    # EDIT 2 - insert new functions before _save_daily_snapshot.
    if ANCHOR_2 not in new_src:
        print("ERROR: ANCHOR_2 lost after EDIT 1")
        sys.exit(1)
    new_src = new_src.replace(ANCHOR_2, EDIT_2_NEW + ANCHOR_2, 1)

    # EDIT 3a - argparse flag.
    if ANCHOR_3A not in new_src:
        print("ERROR: ANCHOR_3A lost after earlier edits")
        sys.exit(1)
    new_src = new_src.replace(ANCHOR_3A, EDIT_3A_NEW, 1)

    # EDIT 3b - call site.
    if ANCHOR_3B not in new_src:
        print("ERROR: ANCHOR_3B lost after earlier edits")
        sys.exit(1)
    new_src = new_src.replace(ANCHOR_3B, EDIT_3B_NEW, 1)

    # -- validate the patched source compiles --
    tmp_out = SCRIPT_DIR / "_s27_pipeline_patched.py.s27check"
    tmp_out.write_text(new_src, encoding="utf-8")
    import py_compile
    try:
        py_compile.compile(str(tmp_out), doraise=True)
    except py_compile.PyCompileError as e:
        print("ERROR: patched source fails py_compile:\n%s" % e)
        sys.exit(1)
    finally:
        # clean up the validation temp file + any py_compile cache it created
        try:
            tmp_out.unlink(missing_ok=True)
            _pyc = tmp_out.parent / "__pycache__"
            if _pyc.is_dir():
                for _f in _pyc.glob(tmp_out.stem + "*"):
                    _f.unlink(missing_ok=True)
        except Exception:
            pass

    # -- pre-write backup --
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = TARGET.with_suffix(TARGET.suffix + ".bak-pre-tests-s27-%s" % ts)
    shutil.copy2(TARGET, backup)

    # -- atomic write at END --
    tmp_final = TARGET.with_suffix(TARGET.suffix + ".s27tmp")
    tmp_final.write_text(new_src, encoding="utf-8")
    tmp_final.replace(TARGET)

    # -- post-write verification --
    written = TARGET.read_text(encoding="utf-8")
    checks = {
        "marker present": MARKER in written,
        "vcp_deploy_s1 emitted": 'tests["vcp_deploy_s1"]' in written,
        "vcp_deploy_s2 emitted": 'tests["vcp_deploy_s2"]' in written,
        "ma_retest 8-col": '"total": 8,' in written and "x1_reclaim_close_above_ma" in written,
        "probing_bet info_collapsing_rating": "info_collapsing_rating" in written,
        "apply_test_history defined": "def apply_test_history(" in written,
        "apply_test_history called": "filter_results = apply_test_history(" in written,
        "seed-test-history flag": "--seed-test-history" in written,
        "old single vcp block gone": 'vcpt_tests = dict(vcp_tests)' not in written,
        "compiles": True,
    }
    try:
        py_compile.compile(str(TARGET), doraise=True)
    except py_compile.PyCompileError as e:
        checks["compiles"] = False
        print("  POST-WRITE COMPILE FAIL: %s" % e)

    print()
    print("  patched : %s" % TARGET)
    print("  backup  : %s" % backup)
    print("  md5     : %s" % md5(TARGET))
    print("  bytes   : %d" % TARGET.stat().st_size)
    print()
    all_ok = True
    for name, ok in checks.items():
        print("  [%s] %s" % ("OK" if ok else "FAIL", name))
        all_ok = all_ok and ok
    if not all_ok:
        print("\n  ONE OR MORE POST-WRITE CHECKS FAILED - review before running refresh_all.")
        sys.exit(1)
    print("\n  All post-write checks passed.")


if __name__ == "__main__":
    main()
