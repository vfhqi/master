#!/usr/bin/env python3
# =============================================================================
# patch_md_v2_screens_s25_FIX_2026_05_14.py
# -----------------------------------------------------------------------------
# CORRECTIVE PATCHER (14-May-26). The original patch_md_v2_screens_s25 hit
# the DEAD sidecar _md_v2_screens.py. The LIVE copy of
# compute_master_dashboard_screens is INLINED in generate_master_data.py
# (injected Session 20, since diverged with Calib2 changes). This patcher
# applies the identical Session 25 logic to the live inlined copy.
# Session 25 (14-May-26) rewrite of the pre-test indicator / capital
# qualification setup / capital deployment test logic in generate_master_data.py.
# Locked decisions D-MD-V2-49, -50, -51, -52, -53, -55.
#
# EDIT A: add Session 25 convenience accessors
# EDIT B: rewrite the 3 pre-test indicators
#         - "pulling_back_uptrend" (was pullback_to_retest)  - D-MD-V2-50, 4 tests
#         - "basing"              (was basing_below_high)    - D-MD-V2-49, 4 tests
#         - "collapsing"          (unchanged logic, kept)
#         + emit structured md["pre_indicators"] with per-pattern tests/count/rating
# EDIT C: replace setup "utr_after_s2_pullback" with "healthy_retest" - D-MD-V2-51
# EDIT D: replace test "uptrend_retest" with "ma_retest_upwards" - D-MD-V2-52
#         (current-day pass/fail only; L5D/L20D windows deferred per Option 2)
#
# Discipline (D-MD-V2-43): heredoc -> /tmp -> atomic cp -> MD5 byte-verify.
# Patcher: idempotent, anchor-string replace, pre-write backup, py_compile
# clean, atomic write at END, post-write verification.
# =============================================================================
import sys, os, shutil, hashlib, py_compile, tempfile
from datetime import datetime

TARGET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generate_master_data.py")
MARKER = "MD-V2-SCREENS-S25-FIX-MARKER"

def main():
    if not os.path.exists(TARGET):
        print("ERROR: target not found: %s" % TARGET); sys.exit(1)

    with open(TARGET, "r", encoding="utf-8") as f:
        src = f.read()

    if MARKER in src:
        print("IDEMPOTENT: %s already present. No-op." % MARKER)
        sys.exit(0)

    orig_len = len(src)

    # -------------------------------------------------------------------------
    # EDIT A - Session 25 convenience accessors.
    # Anchor on the recent_pullback / rs_returns accessor lines.
    # -------------------------------------------------------------------------
    anchorA = (
        '        recent_pullback = p.get("recent_pullback_pct", 0)\n'
        '        rs_returns = p.get("rs_returns", {}) or {}\n'
    )
    replaceA = (
        '        recent_pullback = p.get("recent_pullback_pct", 0)\n'
        '        rs_returns = p.get("rs_returns", {}) or {}\n'
        "\n"
        "        # ── " + MARKER + ": Session 25 accessors ──\n"
        '        max_pullback_ssh = p.get("max_pullback_since_swing_high")\n'
        '        days_below_sh = p.get("days_below_swing_high")\n'
        '        utr_50d_rising = p.get("utr_50d_rising", False)\n'
        '        utr_150d_rising = p.get("utr_150d_rising", False)\n'
        '        utr_5d_declining = p.get("utr_5d_declining", False)\n'
        '        utr_10d_declining = p.get("utr_10d_declining", False)\n'
        '        utr_vol_trend = p.get("utr_vol_trend")\n'
        '        utr_updown_ratio = p.get("utr_updown_ratio")\n'
        '        utr_updown_ratio_5d = p.get("utr_updown_ratio_5d")\n'
        '        utr_dist_days = p.get("utr_dist_days")\n'
        '        utr_pullback_contraction = p.get("utr_pullback_contraction")\n'
        '        utr_test_ma = p.get("utr_test_ma")\n'
        '        utr_test_ma_dist = p.get("utr_test_ma_dist")\n'
        '        utr_retest_counts = p.get("utr_retest_counts", {}) or {}\n'
        '        utr_candle_quality_10d = p.get("utr_candle_quality_10d")\n'
        '        utr_candle_quality_3d = p.get("utr_candle_quality_3d")\n'
        '        close_pct_change_today = p.get("close_pct_change_today")\n'
        "        # ── END " + MARKER + " accessors ──\n"
    )
    if anchorA not in src:
        print("ERROR: EDIT A anchor not found (recent_pullback accessors)."); sys.exit(1)
    src = src.replace(anchorA, replaceA, 1)

    # -------------------------------------------------------------------------
    # EDIT B - rewrite the 3 pre-test indicators + emit md["pre_indicators"].
    # Anchor: from "# Pre-test leading indicators" through the collapsing block.
    # -------------------------------------------------------------------------
    anchorB = (
        "        # Pre-test leading indicators\n"
        "        # 1. Pullback to retest S2 uptrend (only meaningful in S2)\n"
        "        # Stock has fallen 5-25% from swing high recently, but stays above MAs (uptrend intact)\n"
        "        is_s2_uptrend = (s2[\"rating\"] in (\"Probable\", \"Plausible\"))\n"
        "        in_pullback_range = (recent_pullback is not None and 0.05 <= recent_pullback <= 0.25)\n"
        "        above_ma200 = (price is not None and ma200 is not None and price > ma200)\n"
        "        ind[\"pullback_to_retest\"] = bool(is_s2_uptrend and in_pullback_range and above_ma200)\n"
        "\n"
        "        # 2. Basing below recent high in S2 (≥15% fall + 20 days below high + still in S2)\n"
        "        # Approximation: recent pullback ≥15%, currently below swing high, and S2 plausible\n"
        "        ind[\"basing_below_high\"] = bool(\n"
        "            is_s2_uptrend and\n"
        "            recent_pullback is not None and recent_pullback >= 0.15 and\n"
        "            price is not None and swing_high is not None and price < swing_high\n"
        "        )\n"
        "\n"
        "        # 3. Collapsing (irrespective of stage)\n"
        "        # Both: SP 30% below 52WH AND SP fall ≥20% from L3M high\n"
        "        sp_30_below_52wh = (price is not None and h52 is not None and h52 > 0 and price <= h52 * 0.70)\n"
        "        # Approximation for \"L3M high\" — use swing_high (most recent peak in 6M); take stricter test of 20% off\n"
        "        sp_20_off_l3m_high = (recent_pullback is not None and recent_pullback >= 0.20)\n"
        "        ind[\"collapsing\"] = bool(sp_30_below_52wh and sp_20_off_l3m_high)\n"
    )
    replaceB = (
        "        # Pre-test leading indicators\n"
        "        # " + MARKER + ": Session 25 rewrite. Each pre-test indicator is now an\n"
        "        # explicit AND of named boolean tests; tests/count/rating emitted in\n"
        "        # md[\"pre_indicators\"] so the dashboard can render per-pattern\n"
        "        # rating + score columns (D-MD-V2-55, Option A 3-tier ladder).\n"
        "\n"
        "        # ---- Indicator 1: Pulling back within MT/LT uptrend (D-MD-V2-50) ----\n"
        "        # In a real MT/LT uptrend (50D + 150D MAs still rising) AND currently\n"
        "        # inside a pullback (5D + 10D MAs rolling over). No Stage 2 rating gate.\n"
        "        pb_t1_50d_rising = bool(utr_50d_rising)\n"
        "        pb_t2_150d_rising = bool(utr_150d_rising)\n"
        "        pb_t3_5d_rolling = bool(utr_5d_declining)\n"
        "        pb_t4_10d_rolling = bool(utr_10d_declining)\n"
        "        pb_tests = {\n"
        "            \"t1_50d_rising\": pb_t1_50d_rising,\n"
        "            \"t2_150d_rising\": pb_t2_150d_rising,\n"
        "            \"t3_5d_rolling_over\": pb_t3_5d_rolling,\n"
        "            \"t4_10d_rolling_over\": pb_t4_10d_rolling,\n"
        "        }\n"
        "        pb_count = sum(1 for v in pb_tests.values() if v)\n"
        "        ind[\"pulling_back_uptrend\"] = bool(pb_count == 4)\n"
        "\n"
        "        # ---- Indicator 2: Basing (D-MD-V2-49) ----\n"
        "        # 4 tests: price pullback >=15% (max drawdown since swing high, even if\n"
        "        # partly reclawed) AND price below swing high >=20 trading days AND\n"
        "        # price > 200D MA AND 200D MA still rising MoM.\n"
        "        ba_t1_pullback = bool(max_pullback_ssh is not None and max_pullback_ssh >= 0.15)\n"
        "        ba_t2_time = bool(days_below_sh is not None and days_below_sh >= 20)\n"
        "        ba_t3_above_200d = bool(price is not None and ma200 is not None and price > ma200)\n"
        "        ba_t4_200d_rising = bool(ma200 is not None and ma200_prev is not None and ma200 > ma200_prev)\n"
        "        ba_tests = {\n"
        "            \"t1_price_pullback_ge15\": ba_t1_pullback,\n"
        "            \"t2_time_below_high_ge20d\": ba_t2_time,\n"
        "            \"t3_price_above_200d\": ba_t3_above_200d,\n"
        "            \"t4_200d_rising\": ba_t4_200d_rising,\n"
        "        }\n"
        "        ba_count = sum(1 for v in ba_tests.values() if v)\n"
        "        ind[\"basing\"] = bool(ba_count == 4)\n"
        "        # Back-compat alias - some downstream code still references basing_below_high\n"
        "        ind[\"basing_below_high\"] = ind[\"basing\"]\n"
        "\n"
        "        # ---- Indicator 3: Collapsing (logic unchanged) ----\n"
        "        # Both: SP 30% below 52WH AND SP fall >=20% from recent high.\n"
        "        co_t1_30_below_52wh = bool(price is not None and h52 is not None and h52 > 0 and price <= h52 * 0.70)\n"
        "        co_t2_pullback_ge20 = bool(recent_pullback is not None and recent_pullback >= 0.20)\n"
        "        co_tests = {\n"
        "            \"t1_price_le_70pct_52wh\": co_t1_30_below_52wh,\n"
        "            \"t2_pullback_ge20\": co_t2_pullback_ge20,\n"
        "        }\n"
        "        co_count = sum(1 for v in co_tests.values() if v)\n"
        "        ind[\"collapsing\"] = bool(co_count == 2)\n"
        "\n"
        "        # ---- Per-pattern rating ladder (D-MD-V2-55, Option A 3-tier) ----\n"
        "        def _pre_rating(count, total):\n"
        "            \"\"\"Option A 3-tier ladder scaled to test count.\n"
        "            0 -> None ; ~1/3 -> Possible ; ~2/3 -> Plausible ; all -> Probable.\"\"\"\n"
        "            if count <= 0:\n"
        "                return \"None\"\n"
        "            if count >= total:\n"
        "                return \"Probable\"\n"
        "            frac = count / total\n"
        "            if frac >= (2.0 / 3.0):\n"
        "                return \"Plausible\"\n"
        "            return \"Possible\"\n"
        "\n"
        "        md[\"pre_indicators\"] = {\n"
        "            \"pulling_back_uptrend\": {\n"
        "                \"tests\": pb_tests, \"count\": pb_count, \"total\": 4,\n"
        "                \"rating\": _pre_rating(pb_count, 4), \"qualifies\": ind[\"pulling_back_uptrend\"],\n"
        "            },\n"
        "            \"basing\": {\n"
        "                \"tests\": ba_tests, \"count\": ba_count, \"total\": 4,\n"
        "                \"rating\": _pre_rating(ba_count, 4), \"qualifies\": ind[\"basing\"],\n"
        "            },\n"
        "            \"collapsing\": {\n"
        "                \"tests\": co_tests, \"count\": co_count, \"total\": 2,\n"
        "                \"rating\": _pre_rating(co_count, 2), \"qualifies\": ind[\"collapsing\"],\n"
        "            },\n"
        "        }\n"
        "\n"
        "        # Back-compat: keep is_s2_uptrend defined for downstream setup/test logic\n"
        "        # that still references it (probing_bet, vcp setups, etc).\n"
        "        is_s2_uptrend = (s2[\"rating\"] in (\"Probable\", \"Plausible\"))\n"
    )
    if anchorB not in src:
        print("ERROR: EDIT B anchor not found (pre-test indicators block)."); sys.exit(1)
    src = src.replace(anchorB, replaceB, 1)

    # -------------------------------------------------------------------------
    # EDIT C - replace setup "utr_after_s2_pullback" with "healthy_retest".
    # Anchor: the existing Setup 3 block.
    # -------------------------------------------------------------------------
    # NOTE: live generate_master_data.py carries the CALIB2 form of Setup 3
    # (D-MD-V2-8: setups are preconditions only - no breakout requirement).
    anchorC = (
        "        # Setup 3: UTR breakout after S2 pullback (Core MM tranche)\n"
        "        # Logic: stock in S2, has pulled back to retest MA, now breaking back up\n"
        "        utr_capital = fr.get(\"uptrend_retest\", {}).get(\"stage\") == \"Capital\"\n"
        "        setups[\"utr_after_s2_pullback\"] = bool(\n"
        "            is_s2_uptrend and ind[\"pullback_to_retest\"]\n"
        "        )\n"
    )
    replaceC = (
        "        # Setup 3: Healthy retest within MT/LT uptrend (D-MD-V2-51)\n"
        "        # " + MARKER + ": REPLACES the old utr_after_s2_pullback setup.\n"
        "        # Asks whether the pullback is healthy/orderly as price comes toward the\n"
        "        # MA that will be retested. 6 tests, ALL must pass. Plus 2 INFO fields\n"
        "        # (ma_retested, retest_count) that are NOT part of the AND-logic.\n"
        "        hr_t1_vol_contracting = bool(utr_vol_trend is not None and utr_vol_trend < 1.0)\n"
        "        hr_t2_updown_ge105 = bool(utr_updown_ratio is not None and utr_updown_ratio >= 1.05)\n"
        "        hr_t3_few_dist_days = bool(utr_dist_days is not None and utr_dist_days <= 3)\n"
        "        hr_t4_volatility_contracting = bool(utr_pullback_contraction is not None and utr_pullback_contraction < 1.0)\n"
        "        hr_t5_testing_ma = bool(utr_test_ma is not None)\n"
        "        hr_t6_buying_l10d = bool(utr_candle_quality_10d is not None and utr_candle_quality_10d >= 0.5)\n"
        "        hr_tests = {\n"
        "            \"t1_volume_contracting\": hr_t1_vol_contracting,\n"
        "            \"t2_updown_vol_ge105\": hr_t2_updown_ge105,\n"
        "            \"t3_few_distribution_days\": hr_t3_few_dist_days,\n"
        "            \"t4_volatility_contracting\": hr_t4_volatility_contracting,\n"
        "            \"t5_testing_meaningful_ma\": hr_t5_testing_ma,\n"
        "            \"t6_buying_through_l10d\": hr_t6_buying_l10d,\n"
        "        }\n"
        "        hr_count = sum(1 for v in hr_tests.values() if v)\n"
        "        # INFO fields (not gates): which MA is being tested + touch count for THAT MA only\n"
        "        hr_retest_count = utr_retest_counts.get(utr_test_ma) if utr_test_ma else None\n"
        "        setups[\"healthy_retest\"] = {\n"
        "            \"tests\": hr_tests, \"count\": hr_count, \"total\": 6,\n"
        "            \"rating\": _pre_rating(hr_count, 6),\n"
        "            \"qualifies\": bool(hr_count == 6),\n"
        "            \"info_ma_retested\": utr_test_ma,\n"
        "            \"info_ma_dist_pct\": utr_test_ma_dist,\n"
        "            \"info_retest_count\": hr_retest_count,\n"
        "        }\n"
        "        # Back-compat alias - downstream may still reference utr_after_s2_pullback\n"
        "        setups[\"utr_after_s2_pullback\"] = setups[\"healthy_retest\"][\"qualifies\"]\n"
    )
    if anchorC not in src:
        print("ERROR: EDIT C anchor not found (Setup 3 utr_after_s2_pullback block)."); sys.exit(1)
    src = src.replace(anchorC, replaceC, 1)

    # -------------------------------------------------------------------------
    # EDIT D - replace test "uptrend_retest" with "ma_retest_upwards".
    # Anchor: the existing Test 3 block.
    # -------------------------------------------------------------------------
    anchorD = (
        "        # Test 3: UTR — reuse existing uptrend_retest filter\n"
        "        utr_stage = fr.get(\"uptrend_retest\", {}).get(\"stage\")\n"
        "        tests[\"uptrend_retest\"] = {\n"
        "            \"stage\": utr_stage,\n"
        "            \"qualifies\": utr_stage in (\"Late\", \"Capital\"),\n"
        "        }\n"
    )
    replaceD = (
        "        # Test 3: Upwards moving average retest (D-MD-V2-52)\n"
        "        # " + MARKER + ": REPLACES the old uptrend_retest stage passthrough.\n"
        "        # The binary go/no-go capital deployment trigger. 5 tests; pass logic =\n"
        "        # (1) AND (2) AND (3 OR 4) AND (5). Current-day pass/fail only - the\n"
        "        # L5D/L20D action-oriented trigger windows (D-MD-V2-54) are deferred to\n"
        "        # a dedicated follow-up build (Option 2, confirmed 14-May-26).\n"
        "        # test MA value: read the SMA of whichever MA is being tested\n"
        "        _test_ma_period = {\"50D\": \"50D\", \"100D\": \"100D\", \"150D\": \"150D\", \"200D\": \"200D\"}.get(utr_test_ma)\n"
        "        _test_ma_val = mas.get(_test_ma_period) if _test_ma_period else None\n"
        "        mr_t1_near_test_ma = bool(utr_test_ma is not None)  # MANDATORY\n"
        "        mr_t2_close_above_ma = bool(\n"
        "            price is not None and _test_ma_val is not None and price > _test_ma_val\n"
        "        )  # MANDATORY\n"
        "        mr_t3_candle_l3d = bool(\n"
        "            utr_candle_quality_3d is not None and utr_candle_quality_3d >= 0.5\n"
        "        )  # ONE OF {3,4}\n"
        "        mr_t4_updown_l5d = bool(\n"
        "            utr_updown_ratio_5d is not None and utr_updown_ratio_5d >= 1.10\n"
        "        )  # ONE OF {3,4}\n"
        "        mr_t5_confirmation = bool(\n"
        "            close_pct_change_today is not None and close_pct_change_today >= 0.02\n"
        "        )  # MANDATORY confirmation (D-MD-V2-53)\n"
        "        mr_tests = {\n"
        "            \"t1_near_test_ma\": mr_t1_near_test_ma,\n"
        "            \"t2_close_above_test_ma\": mr_t2_close_above_ma,\n"
        "            \"t3_closes_near_highs_l3d\": mr_t3_candle_l3d,\n"
        "            \"t4_updown_vol_l5d\": mr_t4_updown_l5d,\n"
        "            \"t5_confirmation_close_ge2pct\": mr_t5_confirmation,\n"
        "        }\n"
        "        mr_count = sum(1 for v in mr_tests.values() if v)\n"
        "        mr_qualifies = bool(\n"
        "            mr_t1_near_test_ma and mr_t2_close_above_ma and\n"
        "            (mr_t3_candle_l3d or mr_t4_updown_l5d) and mr_t5_confirmation\n"
        "        )\n"
        "        tests[\"ma_retest_upwards\"] = {\n"
        "            \"tests\": mr_tests, \"count\": mr_count, \"total\": 5,\n"
        "            \"rating\": _pre_rating(mr_count, 5),\n"
        "            \"qualifies\": mr_qualifies,\n"
        "            \"info_ma_retested\": utr_test_ma,\n"
        "        }\n"
        "        # Back-compat alias - downstream may still reference uptrend_retest test\n"
        "        utr_stage = fr.get(\"uptrend_retest\", {}).get(\"stage\")\n"
        "        tests[\"uptrend_retest\"] = {\n"
        "            \"stage\": utr_stage,\n"
        "            \"qualifies\": mr_qualifies,\n"
        "        }\n"
    )
    if anchorD not in src:
        print("ERROR: EDIT D anchor not found (Test 3 uptrend_retest block)."); sys.exit(1)
    src = src.replace(anchorD, replaceD, 1)

    # -------------------------------------------------------------------------
    # Validate in /tmp, pre-write backup, atomic write, post-write verify.
    # -------------------------------------------------------------------------
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".py", prefix="screens_patch_")
    os.close(tmp_fd)
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(src)

    try:
        py_compile.compile(tmp_path, doraise=True)
    except py_compile.PyCompileError as e:
        print("ERROR: patched source fails py_compile:\n%s" % e)
        os.unlink(tmp_path)
        sys.exit(1)

    if b"\x00" in src.encode("utf-8"):
        print("ERROR: null bytes detected in patched source - aborting.")
        os.unlink(tmp_path)
        sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = TARGET + ".bak-pre-md-v2-screens-s25-fix-" + ts
    shutil.copy2(TARGET, backup)
    print("Pre-write backup: %s" % backup)

    shutil.copy2(tmp_path, TARGET)
    os.unlink(tmp_path)

    new_len = len(src)
    print("OK: generate_master_data.py patched (LIVE inlined screens copy).")
    print("    %d bytes -> %d bytes (delta +%d)" % (orig_len, new_len, new_len - orig_len))
    print("    marker: %s" % MARKER)

    with open(TARGET, "r", encoding="utf-8") as f:
        check = f.read()
    if MARKER not in check:
        print("ERROR: post-write verification failed - marker missing!"); sys.exit(1)
    for token in ['md["pre_indicators"]', 'setups["healthy_retest"]', 'tests["ma_retest_upwards"]']:
        if token not in check:
            print("ERROR: post-write verification - expected token missing: %s" % token); sys.exit(1)
    print("Post-write verification: PASS (marker + all 4 edits applied).")

if __name__ == "__main__":
    main()
