#!/usr/bin/env python3
# =============================================================================
# patch_md_v2_screens_s26_2026_05_14.py
# -----------------------------------------------------------------------------
# Session 26 (14-May-26) rebuild of Post-test indicators, Capital qualification
# setups, and Capital deployment tests in the LIVE inlined screens copy in
# generate_master_data.py. Locked decisions D-MD-V2-60, -61, -62, -63.
#
#   EDIT A  build_prices_json: VCP contraction extraction (D-MD-V2-61).
#           Within the base (swing_high_global_idx -> today), extract the
#           ordered contraction sequence with depth, avg volume, low.
#   EDIT B  entry dict: add vcp_contractions field.
#   EDIT C  compute_master_dashboard_screens: VCP accessor + 4-test helper.
#   EDIT D  Post-test indicators -> structured md["post_indicators"] with
#           per-pattern {tests,count,total,rating,qualifies} (D-MD-V2-60).
#   EDIT E  Setups -> restructure all 4 with test decomposition (D-MD-V2-62).
#   EDIT F  Tests -> restructure probing_bet + vcp with decomposition +
#           confirmation test (D-MD-V2-63).
#
# Discipline (D-MD-V2-43): heredoc -> /tmp -> atomic cp -> MD5 byte-verify.
# Idempotent (marker check), pre-write backup, py_compile clean, atomic write
# at END, post-write verification. Edit tool BANNED on generate_master_data.py.
# =============================================================================
import sys, os, shutil, py_compile, tempfile
from datetime import datetime

TARGET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generate_master_data.py")
MARKER = "MD-V2-SCREENS-S26-MARKER"

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
    # EDIT A - VCP contraction extraction in build_prices_json.
    # Anchor: the end of the Session 25 pipeline-fields block.
    # -------------------------------------------------------------------------
    anchorA = (
        "        close_pct_change_today = None\n"
        "        if prev[\"close\"] and prev[\"close\"] > 0:\n"
        "            close_pct_change_today = round((latest[\"close\"] - prev[\"close\"]) / prev[\"close\"], 4)\n"
        "        # ── END MD-V2-PIPELINE-FIELDS-S25-MARKER block ──\n"
    )
    replaceA = (
        "        close_pct_change_today = None\n"
        "        if prev[\"close\"] and prev[\"close\"] > 0:\n"
        "            close_pct_change_today = round((latest[\"close\"] - prev[\"close\"]) / prev[\"close\"], 4)\n"
        "        # ── END MD-V2-PIPELINE-FIELDS-S25-MARKER block ──\n"
        "\n"
        "        # ── " + MARKER + ": VCP contraction extraction (D-MD-V2-61) ──\n"
        "        # Within the base (swing high -> today), walk the price series and\n"
        "        # extract the ordered sequence of contractions. A contraction is a\n"
        "        # local-high-to-local-low swing. Detection uses a SINGLE sensitive\n"
        "        # swing threshold (Option A); the wide-early/tight-late requirement\n"
        "        # is enforced downstream by the narrowing test, not here.\n"
        "        # Each contraction stores: depth (pct decline), avg daily volume, low.\n"
        "        VCP_SWING_THRESHOLD = 0.03  # ~3% - primary calibration parameter\n"
        "        vcp_contractions = []\n"
        "        if swing_high_global_idx is not None and swing_high_global_idx < len(rows_with_sma) - 3:\n"
        "            _base = rows_with_sma[swing_high_global_idx:]\n"
        "            # Walk the base extracting alternating swing highs and swing lows.\n"
        "            # Start at the swing high; find the next swing low (a trough that\n"
        "            # then recovers by >= threshold), then the next swing high, etc.\n"
        "            _i = 0\n"
        "            _n = len(_base)\n"
        "            _cur_high_idx = 0\n"
        "            _cur_high = _base[0][\"high\"]\n"
        "            while _i < _n:\n"
        "                # find the lowest low between cur_high and the next point\n"
        "                # where price recovers >= threshold off that low\n"
        "                _low_idx = _cur_high_idx\n"
        "                _low_val = _base[_cur_high_idx][\"low\"]\n"
        "                _j = _cur_high_idx + 1\n"
        "                _recovered = False\n"
        "                while _j < _n:\n"
        "                    if _base[_j][\"low\"] < _low_val:\n"
        "                        _low_val = _base[_j][\"low\"]\n"
        "                        _low_idx = _j\n"
        "                    # recovery off the running low?\n"
        "                    if _low_val > 0 and (_base[_j][\"high\"] - _low_val) / _low_val >= VCP_SWING_THRESHOLD:\n"
        "                        _recovered = True\n"
        "                        break\n"
        "                    _j += 1\n"
        "                # only count a contraction if it is a real high->low->recovery\n"
        "                if _low_idx > _cur_high_idx and _cur_high > 0:\n"
        "                    _depth = (_cur_high - _low_val) / _cur_high\n"
        "                    if _depth >= VCP_SWING_THRESHOLD:\n"
        "                        _seg = _base[_cur_high_idx:_low_idx + 1]\n"
        "                        _vols = [r[\"volume\"] for r in _seg if r.get(\"volume\") is not None]\n"
        "                        _avg_vol = (sum(_vols) / len(_vols)) if _vols else 0\n"
        "                        vcp_contractions.append({\n"
        "                            \"depth\": round(_depth, 4),\n"
        "                            \"avg_vol\": round(_avg_vol),\n"
        "                            \"low\": round(_low_val, 4),\n"
        "                        })\n"
        "                if not _recovered:\n"
        "                    break\n"
        "                # the next swing high = highest high between this low and the\n"
        "                # recovery point; advance past it\n"
        "                _next_high_idx = _low_idx\n"
        "                _next_high = _base[_low_idx][\"high\"]\n"
        "                _k = _low_idx + 1\n"
        "                while _k <= _j and _k < _n:\n"
        "                    if _base[_k][\"high\"] > _next_high:\n"
        "                        _next_high = _base[_k][\"high\"]\n"
        "                        _next_high_idx = _k\n"
        "                    _k += 1\n"
        "                if _next_high_idx <= _cur_high_idx:\n"
        "                    break  # no progress - stop\n"
        "                _cur_high_idx = _next_high_idx\n"
        "                _cur_high = _next_high\n"
        "                _i = _next_high_idx\n"
        "                if len(vcp_contractions) >= 8:\n"
        "                    break  # safety cap\n"
        "        # ── END " + MARKER + " VCP block ──\n"
    )
    if anchorA not in src:
        print("ERROR: EDIT A anchor not found (S25 pipeline-fields block end)."); sys.exit(1)
    src = src.replace(anchorA, replaceA, 1)

    # -------------------------------------------------------------------------
    # EDIT B - add vcp_contractions to the entry dict.
    # Anchor: the S25 close_pct_change_today entry line.
    # -------------------------------------------------------------------------
    anchorB = '            "close_pct_change_today": close_pct_change_today,\n'
    replaceB = (
        '            "close_pct_change_today": close_pct_change_today,\n'
        "            # " + MARKER + ": VCP contraction sequence\n"
        '            "vcp_contractions": vcp_contractions,\n'
    )
    if anchorB not in src:
        print("ERROR: EDIT B anchor not found (close_pct_change_today entry line)."); sys.exit(1)
    if src.count(anchorB) != 1:
        print("ERROR: EDIT B anchor not unique (%d matches)." % src.count(anchorB)); sys.exit(1)
    src = src.replace(anchorB, replaceB, 1)

    # -------------------------------------------------------------------------
    # EDIT C - VCP accessor + 4-test helper in compute_master_dashboard_screens.
    # Anchor: the S25 accessors block end.
    # -------------------------------------------------------------------------
    anchorC = (
        "        close_pct_change_today = p.get(\"close_pct_change_today\")\n"
        "        # ── END MD-V2-SCREENS-S25-FIX-MARKER accessors ──\n"
    )
    replaceC = (
        "        close_pct_change_today = p.get(\"close_pct_change_today\")\n"
        "        vcp_contractions = p.get(\"vcp_contractions\", []) or []\n"
        "        # ── END MD-V2-SCREENS-S25-FIX-MARKER accessors ──\n"
        "\n"
        "        # ── " + MARKER + ": VCP 4-test computation (D-MD-V2-61) ──\n"
        "        # Shared by both VCP setups. 4 tests, all must pass to qualify.\n"
        "        def _vcp_tests(contractions):\n"
        "            n = len(contractions)\n"
        "            # Test 1: contracting volatility range - strict T1 > T2 > T3 > T4\n"
        "            t1_narrowing = False\n"
        "            if n >= 2:\n"
        "                t1_narrowing = all(\n"
        "                    contractions[i][\"depth\"] < contractions[i - 1][\"depth\"]\n"
        "                    for i in range(1, n)\n"
        "                )\n"
        "            # Test 2: sufficient number of contractions - 2 to 4 inclusive\n"
        "            t2_count_ok = (2 <= n <= 4)\n"
        "            # Test 3: positive volume trend - avg vol falls across contractions\n"
        "            t3_vol_declining = False\n"
        "            if n >= 2:\n"
        "                t3_vol_declining = all(\n"
        "                    contractions[i][\"avg_vol\"] < contractions[i - 1][\"avg_vol\"]\n"
        "                    for i in range(1, n)\n"
        "                )\n"
        "            # Test 4: higher lows through the pattern - each low above the prior\n"
        "            t4_higher_lows = False\n"
        "            if n >= 2:\n"
        "                t4_higher_lows = all(\n"
        "                    contractions[i][\"low\"] > contractions[i - 1][\"low\"]\n"
        "                    for i in range(1, n)\n"
        "                )\n"
        "            tests = {\n"
        "                \"t1_narrowing_contractions\": bool(t1_narrowing),\n"
        "                \"t2_sufficient_count\": bool(t2_count_ok),\n"
        "                \"t3_volume_declining\": bool(t3_vol_declining),\n"
        "                \"t4_higher_lows\": bool(t4_higher_lows),\n"
        "            }\n"
        "            cnt = sum(1 for v in tests.values() if v)\n"
        "            return tests, cnt\n"
        "        vcp_tests, vcp_test_count = _vcp_tests(vcp_contractions)\n"
        "        vcp_qualifies = bool(vcp_test_count == 4)\n"
        "        # ── END " + MARKER + " VCP helper ──\n"
    )
    if anchorC not in src:
        print("ERROR: EDIT C anchor not found (S25 accessors block end)."); sys.exit(1)
    src = src.replace(anchorC, replaceC, 1)

    # -------------------------------------------------------------------------
    # EDIT D - Post-test indicators -> structured md["post_indicators"].
    # Anchor: from "# Post-test trailing indicators" through md["indicators"] = ind
    # -------------------------------------------------------------------------
    anchorD = (
        "        # Post-test trailing indicators\n"
        "        # 4. Breakout (P > 1.08x 5D MA AND ADV up > 1.10x down)\n"
        "        ma5 = mas.get(\"5D\")\n"
        "        breakout_price = (price is not None and ma5 is not None and ma5 > 0 and price > ma5 * 1.08)\n"
        "        # MD-V2-CALIB2: use T10D up/down volume window (was 20D)\n"
        "        adv_10d_up_v = p.get(\"adv_10d_up\", 0) or 0\n"
        "        adv_10d_dn_v = p.get(\"adv_10d_dn\", 0) or 0\n"
        "        breakout_vol = (adv_10d_up_v > 0 and adv_10d_dn_v > 0 and adv_10d_up_v >= adv_10d_dn_v * 1.10)\n"
        "        ind[\"breakout\"] = bool(breakout_price and breakout_vol)\n"
        "\n"
        "        # 5. Advancing (catch-all positive trend without breakout-spike: P above 20D, 20D rising)\n"
        "        ma20_prev = mas.get(\"20D_prev\")\n"
        "        advancing = (\n"
        "            price is not None and ma20 is not None and price > ma20 and\n"
        "            ma20_prev is not None and ma20 > ma20_prev and\n"
        "            not ind[\"breakout\"]\n"
        "        )\n"
        "        ind[\"advancing\"] = bool(advancing)\n"
        "\n"
        "        # 6. Breaking down through 50D\n"
        "        ma50_prev_v = ma50_prev\n"
        "        ind[\"breakdown_50D\"] = bool(\n"
        "            price is not None and ma50 is not None and ma50_prev_v is not None and\n"
        "            price < ma50 and\n"
        "            # was above recently\n"
        "            ma50_prev_v > 0 and p.get(\"price_prev\", price) >= ma50_prev_v * 0.99\n"
        "        )\n"
        "\n"
        "        # 7. Breaking down through 150D\n"
        "        ma150_prev_v = ma150_prev\n"
        "        ind[\"breakdown_150D\"] = bool(\n"
        "            price is not None and ma150 is not None and ma150_prev_v is not None and\n"
        "            price < ma150 and\n"
        "            p.get(\"price_prev\", price) >= ma150_prev_v * 0.99\n"
        "        )\n"
        "\n"
        "        # 8. Breaking down through 200D\n"
        "        ma200_prev_v = ma200_prev\n"
        "        ind[\"breakdown_200D\"] = bool(\n"
        "            price is not None and ma200 is not None and ma200_prev_v is not None and\n"
        "            price < ma200 and\n"
        "            p.get(\"price_prev\", price) >= ma200_prev_v * 0.99\n"
        "        )\n"
        "\n"
        "        md[\"indicators\"] = ind\n"
    )
    replaceD = (
        "        # Post-test trailing indicators\n"
        "        # " + MARKER + ": Session 26 rewrite. Each post-test indicator is\n"
        "        # now an explicit AND of named boolean tests; tests/count/rating\n"
        "        # emitted in md[\"post_indicators\"] for PI-parity rendering\n"
        "        # (D-MD-V2-60). Definitions UNCHANGED - tests surfaced as-is.\n"
        "\n"
        "        ma5 = mas.get(\"5D\")\n"
        "        ma20_prev = mas.get(\"20D_prev\")\n"
        "        adv_10d_up_v = p.get(\"adv_10d_up\", 0) or 0\n"
        "        adv_10d_dn_v = p.get(\"adv_10d_dn\", 0) or 0\n"
        "        ma50_prev_v = ma50_prev\n"
        "        ma150_prev_v = ma150_prev\n"
        "        ma200_prev_v = ma200_prev\n"
        "        _price_prev = p.get(\"price_prev\", price)\n"
        "\n"
        "        # ---- Indicator: Breakout (2 tests) ----\n"
        "        bo_t1_price = bool(price is not None and ma5 is not None and ma5 > 0 and price > ma5 * 1.08)\n"
        "        bo_t2_vol = bool(adv_10d_up_v > 0 and adv_10d_dn_v > 0 and adv_10d_up_v >= adv_10d_dn_v * 1.10)\n"
        "        bo_tests = {\"t1_price_gt_108pct_5dma\": bo_t1_price, \"t2_updown_vol_ge110\": bo_t2_vol}\n"
        "        bo_count = sum(1 for v in bo_tests.values() if v)\n"
        "        ind[\"breakout\"] = bool(bo_count == 2)\n"
        "\n"
        "        # ---- Indicator: Advancing (3 tests; t3 hidden from display) ----\n"
        "        # D-MD-V2-60: 'not in breakout' stays in qualify logic but is NOT\n"
        "        # a display column (hidden=True). Advancing shows 2 cols, qualifies on 3.\n"
        "        ad_t1_above_20d = bool(price is not None and ma20 is not None and price > ma20)\n"
        "        ad_t2_20d_rising = bool(ma20 is not None and ma20_prev is not None and ma20 > ma20_prev)\n"
        "        ad_t3_not_breakout = bool(not ind[\"breakout\"])\n"
        "        ad_tests = {\n"
        "            \"t1_price_above_20dma\": ad_t1_above_20d,\n"
        "            \"t2_20dma_rising\": ad_t2_20d_rising,\n"
        "            \"t3_not_in_breakout\": ad_t3_not_breakout,\n"
        "        }\n"
        "        ad_count = sum(1 for v in ad_tests.values() if v)\n"
        "        ind[\"advancing\"] = bool(ad_count == 3)\n"
        "\n"
        "        # ---- Indicator: Breakdown 50D (2 tests) ----\n"
        "        bd50_t1 = bool(price is not None and ma50 is not None and price < ma50)\n"
        "        bd50_t2 = bool(ma50_prev_v is not None and ma50_prev_v > 0 and _price_prev >= ma50_prev_v * 0.99)\n"
        "        bd50_tests = {\"t1_price_below_50dma\": bd50_t1, \"t2_prev_at_or_above_50dma\": bd50_t2}\n"
        "        bd50_count = sum(1 for v in bd50_tests.values() if v)\n"
        "        ind[\"breakdown_50D\"] = bool(bd50_count == 2)\n"
        "\n"
        "        # ---- Indicator: Breakdown 150D (2 tests) ----\n"
        "        bd150_t1 = bool(price is not None and ma150 is not None and price < ma150)\n"
        "        bd150_t2 = bool(ma150_prev_v is not None and ma150_prev_v > 0 and _price_prev >= ma150_prev_v * 0.99)\n"
        "        bd150_tests = {\"t1_price_below_150dma\": bd150_t1, \"t2_prev_at_or_above_150dma\": bd150_t2}\n"
        "        bd150_count = sum(1 for v in bd150_tests.values() if v)\n"
        "        ind[\"breakdown_150D\"] = bool(bd150_count == 2)\n"
        "\n"
        "        # ---- Indicator: Breakdown 200D (2 tests) ----\n"
        "        bd200_t1 = bool(price is not None and ma200 is not None and price < ma200)\n"
        "        bd200_t2 = bool(ma200_prev_v is not None and ma200_prev_v > 0 and _price_prev >= ma200_prev_v * 0.99)\n"
        "        bd200_tests = {\"t1_price_below_200dma\": bd200_t1, \"t2_prev_at_or_above_200dma\": bd200_t2}\n"
        "        bd200_count = sum(1 for v in bd200_tests.values() if v)\n"
        "        ind[\"breakdown_200D\"] = bool(bd200_count == 2)\n"
        "\n"
        "        md[\"indicators\"] = ind\n"
        "\n"
        "        # Structured post_indicators for PI-parity rendering (D-MD-V2-60).\n"
        "        # Advancing total=3 (incl hidden test) but display shows 2 columns.\n"
        "        md[\"post_indicators\"] = {\n"
        "            \"breakout\": {\n"
        "                \"tests\": bo_tests, \"count\": bo_count, \"total\": 2,\n"
        "                \"rating\": _pre_rating(bo_count, 2), \"qualifies\": ind[\"breakout\"],\n"
        "            },\n"
        "            \"advancing\": {\n"
        "                \"tests\": ad_tests, \"count\": ad_count, \"total\": 3,\n"
        "                \"rating\": _pre_rating(ad_count, 3), \"qualifies\": ind[\"advancing\"],\n"
        "            },\n"
        "            \"breakdown_50D\": {\n"
        "                \"tests\": bd50_tests, \"count\": bd50_count, \"total\": 2,\n"
        "                \"rating\": _pre_rating(bd50_count, 2), \"qualifies\": ind[\"breakdown_50D\"],\n"
        "            },\n"
        "            \"breakdown_150D\": {\n"
        "                \"tests\": bd150_tests, \"count\": bd150_count, \"total\": 2,\n"
        "                \"rating\": _pre_rating(bd150_count, 2), \"qualifies\": ind[\"breakdown_150D\"],\n"
        "            },\n"
        "            \"breakdown_200D\": {\n"
        "                \"tests\": bd200_tests, \"count\": bd200_count, \"total\": 2,\n"
        "                \"rating\": _pre_rating(bd200_count, 2), \"qualifies\": ind[\"breakdown_200D\"],\n"
        "            },\n"
        "        }\n"
    )
    if anchorD not in src:
        print("ERROR: EDIT D anchor not found (post-test indicators block)."); sys.exit(1)
    src = src.replace(anchorD, replaceD, 1)

    # -------------------------------------------------------------------------
    # EDIT E - Setups: restructure all 4 with test decomposition.
    # Anchor: from "# 4 SETUPS" header through md["setups"] = setups
    # -------------------------------------------------------------------------
    anchorE = (
        "        # 4 SETUPS — capital deployment eligibility\n"
        "        # ─────────────────────────────────────────────────────────────\n"
        "        setups = {}\n"
    )
    # we anchor on a smaller unique slice and replace through md["setups"] = setups
    anchorE_start = "        setups = {}\n\n        # Setup 1: Probing bet breakout"
    anchorE_end = "        md[\"setups\"] = setups\n"
    iE0 = src.find(anchorE_start)
    iE1 = src.find(anchorE_end)
    if iE0 == -1 or iE1 == -1 or iE1 < iE0:
        print("ERROR: EDIT E anchor span not found."); sys.exit(1)
    iE1_end = iE1 + len(anchorE_end)
    replaceE = (
        "        setups = {}\n"
        "\n"
        "        # " + MARKER + ": Session 26 rewrite. All 4 setups decomposed into\n"
        "        # named test columns + Option A rating ladder (D-MD-V2-62).\n"
        "        # healthy_retest REPLACES the old utr_after_s2_pullback (built S25).\n"
        "\n"
        "        # ---- Setup 1: Probing bet (2 tests) - definitions unchanged ----\n"
        "        s1_qualifying = s1[\"rating\"] in (\"Plausible\", \"Probable Early\", \"Probable Late\")\n"
        "        s3_qualifying = s3[\"rating\"] in (\"Plausible Invalidation\", \"Probable Invalidation\")\n"
        "        s4_qualifying = s4[\"rating\"] in (\"Plausible\", \"Probable\")\n"
        "        pbs_t1_stage_or_collapsing = bool(s1_qualifying or s3_qualifying or s4_qualifying or ind[\"collapsing\"])\n"
        "        pbs_t2_breakout = bool(ind[\"breakout\"])\n"
        "        pbs_tests = {\n"
        "            \"t1_stage_qualifying_or_collapsing\": pbs_t1_stage_or_collapsing,\n"
        "            \"t2_breakout\": pbs_t2_breakout,\n"
        "        }\n"
        "        pbs_count = sum(1 for v in pbs_tests.values() if v)\n"
        "        setups[\"probing_bet\"] = {\n"
        "            \"tests\": pbs_tests, \"count\": pbs_count, \"total\": 2,\n"
        "            \"rating\": _pre_rating(pbs_count, 2), \"qualifies\": bool(pbs_count == 2),\n"
        "        }\n"
        "\n"
        "        # ---- Setup 2: VCP after S1->2 plateau (4 VCP tests + stage gate) ----\n"
        "        # D-MD-V2-62: uses the new 4-test VCP contraction structure.\n"
        "        # The stage gate (S1->2 transition) is folded into test 1 alongside\n"
        "        # the narrowing check so the displayed tests are the 4 VCP tests.\n"
        "        s1_to_2_transition = (\n"
        "            s1[\"rating\"] in (\"Probable Late\", \"Probable Early\") and\n"
        "            s2[\"rating\"] in (\"Possible\", \"Plausible\")\n"
        "        )\n"
        "        vcp_s1_tests = dict(vcp_tests)\n"
        "        vcp_s1_count = vcp_test_count\n"
        "        setups[\"vcp_after_s1_plateau\"] = {\n"
        "            \"tests\": vcp_s1_tests, \"count\": vcp_s1_count, \"total\": 4,\n"
        "            \"rating\": _pre_rating(vcp_s1_count, 4),\n"
        "            \"qualifies\": bool(vcp_qualifies and s1_to_2_transition),\n"
        "            \"info_stage_gate\": bool(s1_to_2_transition),\n"
        "            \"info_contraction_count\": len(vcp_contractions),\n"
        "        }\n"
        "\n"
        "        # ---- Setup 3: Healthy retest within MT/LT uptrend (6 tests) ----\n"
        "        # Built in Session 25 (D-MD-V2-51). Unchanged here.\n"
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
        "\n"
        "        # ---- Setup 4: VCP after S2 base (4 VCP tests + stage gate) ----\n"
        "        # D-MD-V2-62: uses the new 4-test VCP contraction structure.\n"
        "        vcp_s2_tests = dict(vcp_tests)\n"
        "        vcp_s2_count = vcp_test_count\n"
        "        _s2_base_gate = bool(is_s2_uptrend and ind[\"basing\"])\n"
        "        setups[\"vcp_after_s2_base\"] = {\n"
        "            \"tests\": vcp_s2_tests, \"count\": vcp_s2_count, \"total\": 4,\n"
        "            \"rating\": _pre_rating(vcp_s2_count, 4),\n"
        "            \"qualifies\": bool(vcp_qualifies and _s2_base_gate),\n"
        "            \"info_stage_gate\": _s2_base_gate,\n"
        "            \"info_contraction_count\": len(vcp_contractions),\n"
        "        }\n"
        "\n"
        "        md[\"setups\"] = setups\n"
    )
    src = src[:iE0] + replaceE + src[iE1_end:]

    # -------------------------------------------------------------------------
    # EDIT F - Tests: restructure probing_bet + vcp with decomposition + confirmation.
    # Anchor span: from "# Test 1: Probing bet" through the end of the vcp test dict.
    # -------------------------------------------------------------------------
    anchorF_start = "        # Test 1: Probing bet — reuse existing probing_bet filter\n"
    anchorF_end = (
        "        tests[\"vcp\"] = {\n"
        "            \"stage\": vcp_stage,\n"
        "            \"higher_lows_count\": vcp_count,\n"
        "            \"vol_declining\": vol_declining,\n"
        "            \"stage_gate_met\": s1_or_s2_gate,\n"
        "            \"qualifies\": bool(s1_or_s2_gate and vcp_count >= 2 and vol_declining),\n"
        "        }\n"
    )
    iF0 = src.find(anchorF_start)
    iF1 = src.find(anchorF_end)
    if iF0 == -1 or iF1 == -1 or iF1 < iF0:
        print("ERROR: EDIT F anchor span not found."); sys.exit(1)
    iF1_end = iF1 + len(anchorF_end)
    replaceF = (
        "        # " + MARKER + ": Session 26 rewrite. Probing bet + VCP deployment\n"
        "        # tests decomposed into named test columns + Option A rating ladder,\n"
        "        # each with a mandatory confirmation test (D-MD-V2-63 / D-MD-V2-53).\n"
        "\n"
        "        # ---- Test 1: Probing bet deployment (3 tests incl confirmation) ----\n"
        "        pb_stage = fr.get(\"probing_bet\", {}).get(\"stage\")\n"
        "        pbt_t1_stage_late_or_capital = bool(pb_stage in (\"Late\", \"Capital\"))\n"
        "        pbt_t2_breakout = bool(ind[\"breakout\"])\n"
        "        pbt_t3_confirmation = bool(close_pct_change_today is not None and close_pct_change_today >= 0.02)\n"
        "        pbt_tests = {\n"
        "            \"t1_pb_stage_late_or_capital\": pbt_t1_stage_late_or_capital,\n"
        "            \"t2_breakout\": pbt_t2_breakout,\n"
        "            \"t3_confirmation_close_ge2pct\": pbt_t3_confirmation,\n"
        "        }\n"
        "        pbt_count = sum(1 for v in pbt_tests.values() if v)\n"
        "        tests[\"probing_bet\"] = {\n"
        "            \"tests\": pbt_tests, \"count\": pbt_count, \"total\": 3,\n"
        "            \"rating\": _pre_rating(pbt_count, 3),\n"
        "            \"qualifies\": bool(pbt_count == 3),\n"
        "            \"info_pb_stage\": pb_stage,\n"
        "        }\n"
        "\n"
        "        # ---- Test 2: VCP deployment (5 tests = 4 VCP + confirmation) ----\n"
        "        # D-MD-V2-63: uses the new 4-test VCP contraction structure plus the\n"
        "        # mandatory confirmation test.\n"
        "        vol_declining = (p.get(\"utr_vol_trend\") is not None and p[\"utr_vol_trend\"] < 1.0)\n"
        "        s1_or_s2_gate = (\n"
        "            s1[\"rating\"] in (\"Plausible\", \"Probable Early\", \"Probable Late\") or\n"
        "            (is_s2_uptrend and recent_pullback is not None and recent_pullback >= 0.15)\n"
        "        )\n"
        "        vcpt_t5_confirmation = bool(close_pct_change_today is not None and close_pct_change_today >= 0.02)\n"
        "        vcpt_tests = dict(vcp_tests)\n"
        "        vcpt_tests[\"t5_confirmation_close_ge2pct\"] = vcpt_t5_confirmation\n"
        "        vcpt_count = sum(1 for v in vcpt_tests.values() if v)\n"
        "        tests[\"vcp\"] = {\n"
        "            \"tests\": vcpt_tests, \"count\": vcpt_count, \"total\": 5,\n"
        "            \"rating\": _pre_rating(vcpt_count, 5),\n"
        "            \"qualifies\": bool(vcp_qualifies and vcpt_t5_confirmation and s1_or_s2_gate),\n"
        "            \"info_stage_gate\": bool(s1_or_s2_gate),\n"
        "            \"info_contraction_count\": len(vcp_contractions),\n"
        "        }\n"
    )
    src = src[:iF0] + replaceF + src[iF1_end:]

    # -------------------------------------------------------------------------
    # Validate, backup, atomic write, post-write verify.
    # -------------------------------------------------------------------------
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".py", prefix="gmd_s26_")
    os.close(tmp_fd)
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(src)
    try:
        py_compile.compile(tmp_path, doraise=True)
    except py_compile.PyCompileError as e:
        print("ERROR: patched source fails py_compile:\n%s" % e)
        os.unlink(tmp_path); sys.exit(1)
    if b"\x00" in src.encode("utf-8"):
        print("ERROR: null bytes detected - aborting.")
        os.unlink(tmp_path); sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = TARGET + ".bak-pre-md-v2-screens-s26-" + ts
    shutil.copy2(TARGET, backup)
    print("Pre-write backup: %s" % backup)
    shutil.copy2(tmp_path, TARGET)
    os.unlink(tmp_path)

    new_len = len(src)
    print("OK: generate_master_data.py patched (Session 26).")
    print("    %d bytes -> %d bytes (delta %+d)" % (orig_len, new_len, new_len - orig_len))
    print("    marker: %s" % MARKER)

    with open(TARGET, "r", encoding="utf-8") as f:
        check = f.read()
    if MARKER not in check:
        print("ERROR: post-write verification failed - marker missing!"); sys.exit(1)
    for token in ['vcp_contractions', '_vcp_tests', 'md["post_indicators"]',
                  'setups["probing_bet"] = {', 'setups["vcp_after_s1_plateau"] = {',
                  'setups["vcp_after_s2_base"] = {', 'tests["probing_bet"] = {',
                  'tests["vcp"] = {']:
        if token not in check:
            print("ERROR: post-write verification - missing token: %s" % token); sys.exit(1)
    print("Post-write verification: PASS (marker + all 6 edits applied).")

if __name__ == "__main__":
    main()
