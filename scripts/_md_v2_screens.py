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

        # ── MD-V2-SCREENS-S25-MARKER: Session 25 accessors ──
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
        # ── END MD-V2-SCREENS-S25-MARKER accessors ──

        # ──────────────────────────────────────────────────────────────
        # STAGE 1 — Consolidating / Basing
        # ──────────────────────────────────────────────────────────────
        s1 = {"tests": {}, "groups": {}, "count": 0, "rating": "None"}
        # Group 1 — Slowing decline rate (decline-deceleration over 3 months)
        # Tests #1 (150D) and #2 (200D)
        # UNLESS MA is flat (not declining now) → double-weight tests #3/#4
        def _decline_decelerating(rates):
            """Last 3 MoM rates: d0, d-1, d-2 (most recent first when reversed).
            rates is index 11 (most recent) → 0 (oldest). We want |d_11| < |d_10| < |d_9|."""
            if len(rates) < 12:
                return False, False  # decelerating, flat
            d0 = rates[11]  # most recent month
            d1 = rates[10]
            d2 = rates[9]
            if d0 is None or d1 is None or d2 is None:
                return False, False
            is_flat_or_rising = d0 >= -0.005  # within 0.5% flat-ish or rising
            decelerating = (abs(d0) < abs(d1) < abs(d2)) and d1 < 0 and d2 < 0  # all 3 declining + decelerating
            return decelerating, is_flat_or_rising

        s1_t1_decel, s1_t1_flat = _decline_decelerating(ma150_mom_rates)
        s1_t2_decel, s1_t2_flat = _decline_decelerating(ma200_mom_rates)
        s1["tests"]["T1_150D_decel"] = s1_t1_decel
        s1["tests"]["T2_200D_decel"] = s1_t2_decel
        s1["groups"]["g1_slowing_decline"] = {
            "T1_150D_decelerating": s1_t1_decel,
            "T1_150D_flat_or_rising_exception": s1_t1_flat,
            "T2_200D_decelerating": s1_t2_decel,
            "T2_200D_flat_or_rising_exception": s1_t2_flat,
        }

        # Group 2 — Flattened MAs (±2% of M-1, M-2, M-3)
        def _ma_flat_3m(samples):
            """Latest MA value should be within ±2% of M-1, M-2, M-3."""
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
        s1["groups"]["g2_flat_mas"] = {"T3": s1_t3, "T4": s1_t4}

        # Group 3 — Positively stacked MAs
        s1_t5 = (ma50 is not None and ma150 is not None and ma150 > 0 and ma50 > ma150 * 0.97)
        s1_t6 = (ma150 is not None and ma200 is not None and ma200 > 0 and ma150 > ma200 * 0.97)
        s1["tests"]["T5_50_above_150x97"] = s1_t5
        s1["tests"]["T6_150_above_200x97"] = s1_t6
        s1["groups"]["g3_stack"] = {"T5": s1_t5, "T6": s1_t6}

        # Group 4 — Higher lows
        s1_t7 = higher_lows >= 2  # L1M low > prior 3M low — approximated by 2+ higher lows
        s1_t8 = higher_lows >= 3  # L3M low > prior 3M low — stronger signal (3+ higher lows)
        s1["tests"]["T7_higher_lows_1m"] = s1_t7
        s1["tests"]["T8_higher_lows_3m"] = s1_t8
        s1["groups"]["g4_higher_lows"] = {"T7": s1_t7, "T8": s1_t8}

        # Composite count: simple sum of the 8 tests
        # (Earlier draft included a double-weight bonus when MA was flat-or-rising; removed 13-May-26.)
        count = 0
        for t in [s1_t1_decel, s1_t2_decel, s1_t3, s1_t4, s1_t5, s1_t6, s1_t7, s1_t8]:
            if t:
                count += 1

        s1["count"] = count
        if count >= 5:
            s1["rating"] = "Probable Late"
        elif count == 4:
            s1["rating"] = "Probable Early"
        elif count == 3:
            s1["rating"] = "Plausible"
        elif count == 2:
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
        s2_t5 = (ma50 is not None and ma150 is not None and ma50 > ma150)
        s2["tests"]["T5_50_above_150"] = s2_t5
        s2["groups"]["g3_st_trend"] = {"T5": s2_t5}

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

        s2_count = sum(1 for t in [s2_t1, s2_t2, s2_t3, s2_t4, s2_t5, s2_t6, s2_t7, s2_t8, s2_t9, s2_t10] if t)
        s2["count"] = s2_count
        if s2_count >= 7:
            s2["rating"] = "Probable"
        elif s2_count == 6:
            s2["rating"] = "Plausible"
        elif s2_count == 5:
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
        # No-breakout test #7 — price fails > 5% above 50D for 5+ days
        # Approximation: price within 5% of 50D currently
        s3_t7 = (price is not None and ma50 is not None and ma50 > 0 and price <= ma50 * 1.05)
        s3["tests"]["T5_volume_down_up_ratio"] = s3_t5
        s3["tests"]["T6_volatility_increase"] = s3_t6
        s3["tests"]["T7_no_breakout"] = s3_t7
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
        md["stage_3"] = s3

        # ──────────────────────────────────────────────────────────────
        # STAGE 4 — Decline
        # ──────────────────────────────────────────────────────────────
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
        if s4_count >= 3:
            s4["rating"] = "Probable"
        elif s4_count == 2:
            s4["rating"] = "Plausible"
        elif s4_count == 1:
            s4["rating"] = "Possible"
        else:
            s4["rating"] = "None"
        md["stage_4"] = s4

        # ──────────────────────────────────────────────────────────────
        # 7 INDICATOR PATTERNS (3 pre-test leading + 4 post-test trailing)
        # ──────────────────────────────────────────────────────────────
        ind = {}

        # Pre-test leading indicators
        # MD-V2-SCREENS-S25-MARKER: Session 25 rewrite. Each pre-test indicator is now an
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
            "pulling_back_uptrend": {
                "tests": pb_tests, "count": pb_count, "total": 4,
                "rating": _pre_rating(pb_count, 4), "qualifies": ind["pulling_back_uptrend"],
            },
            "basing": {
                "tests": ba_tests, "count": ba_count, "total": 4,
                "rating": _pre_rating(ba_count, 4), "qualifies": ind["basing"],
            },
            "collapsing": {
                "tests": co_tests, "count": co_count, "total": 2,
                "rating": _pre_rating(co_count, 2), "qualifies": ind["collapsing"],
            },
        }

        # Back-compat: keep is_s2_uptrend defined for downstream setup/test logic
        # that still references it (probing_bet, vcp setups, etc).
        is_s2_uptrend = (s2["rating"] in ("Probable", "Plausible"))

        # Post-test trailing indicators
        # 4. Breakout (P > 1.08x 5D MA AND ADV up > 1.10x down)
        ma5 = mas.get("5D")
        breakout_price = (price is not None and ma5 is not None and ma5 > 0 and price > ma5 * 1.08)
        breakout_vol = (adv_1m_up > 0 and adv_1m_dn > 0 and adv_1m_up >= adv_1m_dn * 1.10)
        ind["breakout"] = bool(breakout_price and breakout_vol)

        # 5. Advancing (catch-all positive trend without breakout-spike: P above 20D, 20D rising)
        ma20_prev = mas.get("20D_prev")
        advancing = (
            price is not None and ma20 is not None and price > ma20 and
            ma20_prev is not None and ma20 > ma20_prev and
            not ind["breakout"]
        )
        ind["advancing"] = bool(advancing)

        # 6. Breaking down through 50D
        ma50_prev_v = ma50_prev
        ind["breakdown_50D"] = bool(
            price is not None and ma50 is not None and ma50_prev_v is not None and
            price < ma50 and
            # was above recently
            ma50_prev_v > 0 and p.get("price_prev", price) >= ma50_prev_v * 0.99
        )

        # 7. Breaking down through 150D
        ma150_prev_v = ma150_prev
        ind["breakdown_150D"] = bool(
            price is not None and ma150 is not None and ma150_prev_v is not None and
            price < ma150 and
            p.get("price_prev", price) >= ma150_prev_v * 0.99
        )

        # 8. Breaking down through 200D
        ma200_prev_v = ma200_prev
        ind["breakdown_200D"] = bool(
            price is not None and ma200 is not None and ma200_prev_v is not None and
            price < ma200 and
            p.get("price_prev", price) >= ma200_prev_v * 0.99
        )

        md["indicators"] = ind

        # ──────────────────────────────────────────────────────────────
        # 4 SETUPS — capital deployment eligibility
        # ──────────────────────────────────────────────────────────────
        setups = {}

        # Setup 1: Probing bet breakout (Stage 1/3/4 + Collapsing indicator + breakout signal)
        # Logic: stock has collapsed, may rebound — eligible for PB tranche
        s1_qualifying = s1["rating"] in ("Plausible", "Probable Early", "Probable Late")
        s3_qualifying = s3["rating"] in ("Plausible Invalidation", "Probable Invalidation")
        s4_qualifying = s4["rating"] in ("Plausible", "Probable")
        setups["probing_bet"] = bool(
            (s1_qualifying or s3_qualifying or s4_qualifying or ind["collapsing"]) and
            ind["breakout"]
        )

        # Setup 2: VCP+breakout after S1→2 plateau (Core MM tranche)
        # Logic: stock was in S1, is now transitioning to S2, has VCP-like higher-lows pattern, plus breakout
        s1_to_2_transition = (
            s1["rating"] in ("Probable Late", "Probable Early") and
            s2["rating"] in ("Possible", "Plausible")
        )
        has_vcp_pattern = (higher_lows >= 2)  # 2-3-4 unbroken higher lows
        setups["vcp_after_s1_plateau"] = bool(
            s1_to_2_transition and has_vcp_pattern and ind["breakout"]
        )

        # Setup 3: Healthy retest within MT/LT uptrend (D-MD-V2-51)
        # MD-V2-SCREENS-S25-MARKER: REPLACES the old utr_after_s2_pullback setup.
        # Asks whether the pullback is healthy/orderly as price comes toward the
        # MA that will be retested. 6 tests, ALL must pass. Plus 2 INFO fields
        # (ma_retested, retest_count) that are NOT part of the AND-logic.
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
        # INFO fields (not gates): which MA is being tested + touch count for THAT MA only
        hr_retest_count = utr_retest_counts.get(utr_test_ma) if utr_test_ma else None
        setups["healthy_retest"] = {
            "tests": hr_tests, "count": hr_count, "total": 6,
            "rating": _pre_rating(hr_count, 6),
            "qualifies": bool(hr_count == 6),
            "info_ma_retested": utr_test_ma,
            "info_ma_dist_pct": utr_test_ma_dist,
            "info_retest_count": hr_retest_count,
        }
        # Back-compat alias - downstream may still reference utr_after_s2_pullback
        setups["utr_after_s2_pullback"] = setups["healthy_retest"]["qualifies"]

        # Setup 4: VCP+breakout after S2 basing (Core MM tranche)
        # Logic: stock in S2, has basing pattern (≥15% pullback), VCP higher-lows, plus breakout
        setups["vcp_after_s2_base"] = bool(
            is_s2_uptrend and ind["basing_below_high"] and has_vcp_pattern and ind["breakout"]
        )

        md["setups"] = setups

        # ──────────────────────────────────────────────────────────────
        # 3 TESTS — capital qualification/invalidation
        # ──────────────────────────────────────────────────────────────
        tests = {}

        # Test 1: Probing bet — reuse existing probing_bet filter
        pb_stage = fr.get("probing_bet", {}).get("stage")
        tests["probing_bet"] = {
            "stage": pb_stage,
            "qualifies": pb_stage in ("Late", "Capital"),
        }

        # Test 2: VCP — higher_lows + volume declining through pattern + S1/S2 gate
        # Higher-lows count
        # Volume declining through troughs — approximated using existing utr_vol_trend (10D/50D ADV ratio < 1 = declining)
        vol_declining = (p.get("utr_vol_trend") is not None and p["utr_vol_trend"] < 1.0)
        s1_or_s2_gate = (
            s1["rating"] in ("Plausible", "Probable Early", "Probable Late") or
            (is_s2_uptrend and recent_pullback is not None and recent_pullback >= 0.15)
        )
        vcp_count = higher_lows  # 2 = early, 3 = mid, 4 = late
        if vcp_count >= 4:
            vcp_stage = "Late"
        elif vcp_count >= 3:
            vcp_stage = "Mid"
        elif vcp_count >= 2:
            vcp_stage = "Early"
        else:
            vcp_stage = None
        tests["vcp"] = {
            "stage": vcp_stage,
            "higher_lows_count": vcp_count,
            "vol_declining": vol_declining,
            "stage_gate_met": s1_or_s2_gate,
            "qualifies": bool(s1_or_s2_gate and vcp_count >= 2 and vol_declining),
        }

        # Test 3: Upwards moving average retest (D-MD-V2-52)
        # MD-V2-SCREENS-S25-MARKER: REPLACES the old uptrend_retest stage passthrough.
        # The binary go/no-go capital deployment trigger. 5 tests; pass logic =
        # (1) AND (2) AND (3 OR 4) AND (5). Current-day pass/fail only - the
        # L5D/L20D action-oriented trigger windows (D-MD-V2-54) are deferred to
        # a dedicated follow-up build (Option 2, confirmed 14-May-26).
        # test MA value: read the SMA of whichever MA is being tested
        _test_ma_period = {"50D": "50D", "100D": "100D", "150D": "150D", "200D": "200D"}.get(utr_test_ma)
        _test_ma_val = mas.get(_test_ma_period) if _test_ma_period else None
        mr_t1_near_test_ma = bool(utr_test_ma is not None)  # MANDATORY
        mr_t2_close_above_ma = bool(
            price is not None and _test_ma_val is not None and price > _test_ma_val
        )  # MANDATORY
        mr_t3_candle_l3d = bool(
            utr_candle_quality_3d is not None and utr_candle_quality_3d >= 0.5
        )  # ONE OF {3,4}
        mr_t4_updown_l5d = bool(
            utr_updown_ratio_5d is not None and utr_updown_ratio_5d >= 1.10
        )  # ONE OF {3,4}
        mr_t5_confirmation = bool(
            close_pct_change_today is not None and close_pct_change_today >= 0.02
        )  # MANDATORY confirmation (D-MD-V2-53)
        mr_tests = {
            "t1_near_test_ma": mr_t1_near_test_ma,
            "t2_close_above_test_ma": mr_t2_close_above_ma,
            "t3_closes_near_highs_l3d": mr_t3_candle_l3d,
            "t4_updown_vol_l5d": mr_t4_updown_l5d,
            "t5_confirmation_close_ge2pct": mr_t5_confirmation,
        }
        mr_count = sum(1 for v in mr_tests.values() if v)
        mr_qualifies = bool(
            mr_t1_near_test_ma and mr_t2_close_above_ma and
            (mr_t3_candle_l3d or mr_t4_updown_l5d) and mr_t5_confirmation
        )
        tests["ma_retest_upwards"] = {
            "tests": mr_tests, "count": mr_count, "total": 5,
            "rating": _pre_rating(mr_count, 5),
            "qualifies": mr_qualifies,
            "info_ma_retested": utr_test_ma,
        }
        # Back-compat alias - downstream may still reference uptrend_retest test
        utr_stage = fr.get("uptrend_retest", {}).get("stage")
        tests["uptrend_retest"] = {
            "stage": utr_stage,
            "qualifies": mr_qualifies,
        }

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
