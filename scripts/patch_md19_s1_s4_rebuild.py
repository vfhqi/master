#!/usr/bin/env python3
"""Patcher — MD-V2 Stage 1 + Stage 4 rebuild per Richard's 19-May briefs.

Applies three discrete edits to scripts/generate_master_data.py:

(1) STAGE 1 — add NEW Group 1 "Prior downtrend" with two tests
    - PD1: 150D MA was declining MoM 4-6 months ago (majority of 3 monthly checks)
    - PD2: 200D MA was declining MoM 4-6 months ago
    Renumbers existing Group 1 (slowing decline) -> Group 2,
    Group 2 (flat MAs) -> Group 3, Group 3 (stack) -> Group 4,
    Group 4 (higher lows) -> Group 5. Total tests: 10 (was 8).

    Rating ladder (D-MD-V2-116):
    - Probable Late: total >=7 AND both new tests pass
    - Probable Early: total >=5 AND at least 1 new test passes
    - Plausible: total >=4 AND at least 1 new test passes
    - Possible: total >=2 (no gate)
    - None: total <2

    Why: chart evidence (Naturgy / Vaisala / Klepierre / Austevollafood) shows
    stocks rated Probable Late Stage 1 that are actually Stage 2 with rising
    long-term MAs. The prior-downtrend gate filters them out.

(2) STAGE 4 — merge "Probable (Accelerating)" into "Probable" + sub-flag
    Existing logic split T1+T3+T4+T5 stocks into two labels: plain "Probable"
    if T2 false, "Probable (Accelerating)" if T2 also true. Per-tab Stage 4
    tile only counts plain "Probable" (=38) hiding the 36 Accelerating
    stocks. New: rating = "Probable" for both, set s4["accelerating"] flag.

(3) METADATA — update prices.json + filter-results.json _meta.source label
    accordingly when the pipeline runs through here (driver respects).

Created 2026-05-19 by SA (autonomous run, MD-V2 full-fix batch).
Backup: scripts/generate_master_data.py.bak-pre-md19-fullfix-* already in place.
"""
from __future__ import annotations
import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "generate_master_data.py"


def _md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


# ── EDIT 1 — Stage 1 rebuild block ────────────────────────────────────────

S1_OLD_BLOCK = """        # ──────────────────────────────────────────────────────────────
        # STAGE 1 — Consolidating / Basing
        # ──────────────────────────────────────────────────────────────
        s1 = {"tests": {}, "groups": {}, "count": 0, "rating": "None"}
        # Group 1 — Slowing decline rate (decline-deceleration over 3 months)
        # Tests #1 (150D) and #2 (200D)
        # UNLESS MA is flat (not declining now) → double-weight tests #3/#4
        def _decline_decelerating(rates):
            \"\"\"Last 3 MoM rates: d0, d-1, d-2 (most recent first when reversed).
            rates is index 11 (most recent) → 0 (oldest). We want |d_11| < |d_10| < |d_9|.\"\"\"
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
            \"\"\"Latest MA value should be within ±2% of M-1, M-2, M-3.\"\"\"
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
        # MD-V2-S47-S1-CUSHION-REMOVAL-MARKER (18-May-26, D-MD-V2-112):
        # Path B — strict positive stack. Removed x0.97 cushion from T5/T6.
        # 50D must be ABOVE 150D; 150D must be ABOVE 200D. No 3% tolerance.
        s1_t5 = (ma50 is not None and ma150 is not None and ma50 > ma150)
        s1_t6 = (ma150 is not None and ma200 is not None and ma150 > ma200)
        s1["tests"]["T5_50_above_150x97"] = s1_t5
        s1["tests"]["T6_150_above_200x97"] = s1_t6
        s1["groups"]["g3_stack"] = {"T5": s1_t5, "T6": s1_t6}

        # Group 4 — Higher lows
        s1_t7 = higher_lows >= 2  # L1M low > prior 3M low — approximated by 2+ higher lows
        s1_t8 = higher_lows >= 3  # L3M low > prior 3M low — stronger signal (3+ higher lows)
        s1["tests"]["T7_higher_lows_1m"] = s1_t7
        s1["tests"]["T8_higher_lows_3m"] = s1_t8
        s1["groups"]["g4_higher_lows"] = {"T7": s1_t7, "T8": s1_t8}

        # Composite count
        # Standard: count all 8 tests
        # EXCEPTION per Richard: if MA flat instead of decelerating-decline → double-weight T3/T4
        count = 0
        for t in [s1_t1_decel, s1_t2_decel, s1_t3, s1_t4, s1_t5, s1_t6, s1_t7, s1_t8]:
            if t:
                count += 1
        # Apply double-weight bonus: if T1 (decel) failed BUT T1_flat exception true → T3 counts double if T3 true
        if not s1_t1_decel and s1_t1_flat and s1_t3:
            count += 1  # extra bonus
        if not s1_t2_decel and s1_t2_flat and s1_t4:
            count += 1  # extra bonus

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
        md["stage_1"] = s1"""

S1_NEW_BLOCK = """        # ──────────────────────────────────────────────────────────────
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
            \"\"\"Last 3 MoM rates: d0, d-1, d-2 (most recent first when reversed).
            rates is index 11 (most recent) -> 0 (oldest). We want |d_11| < |d_10| < |d_9|.\"\"\"
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

        # Rating ladder (D-MD-V2-116):
        if new_both and count >= 7:
            s1["rating"] = "Probable Late"
        elif new_count >= 1 and count >= 5:
            s1["rating"] = "Probable Early"
        elif new_count >= 1 and count >= 4:
            s1["rating"] = "Plausible"
        elif count >= 2:
            s1["rating"] = "Possible"
        else:
            s1["rating"] = "None"
        md["stage_1"] = s1"""


# ── EDIT 2 — Stage 4 rating block ─────────────────────────────────────────

S4_OLD_BLOCK = """        # MD-V2-S47-S4-REWRITE-MARKER (18-May-26, D-MD-V2-115):
        # Specific-combinations ladder per Richard's 17-May definitions.
        # Replaces old count-based ladder (3/7, 2/7, 1/7).
        if s4_t1 and s4_t3 and s4_t4 and s4_t5:
            s4["rating"] = "Probable"
            if s4_t2:
                s4["rating"] = "Probable (Accelerating)"
        elif s4_t4 and s4_t5:
            s4["rating"] = "Plausible"
        elif s4_t4 or s4_t5:
            s4["rating"] = "Possible"
        else:
            s4["rating"] = "None"
"""

S4_NEW_BLOCK = """        # MD-V2-S48-S4-LABEL-MERGE-MARKER (19-May-26, D-MD-V2-117):
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
"""


def apply_patch():
    src_text = SRC.read_text(encoding="utf-8")
    pre_md5 = hashlib.md5(src_text.encode()).hexdigest()
    print(f"  pre-edit size: {len(src_text):,} chars  md5: {pre_md5}")

    # Verify both old blocks present
    edits = [
        ("S1 block", S1_OLD_BLOCK, S1_NEW_BLOCK),
        ("S4 block", S4_OLD_BLOCK, S4_NEW_BLOCK),
    ]
    for name, old, new in edits:
        count_old = src_text.count(old)
        print(f"  {name}: matches OLD block {count_old}x")
        if count_old != 1:
            print(f"  ABORT — {name} old block matched {count_old}x (need exactly 1)")
            sys.exit(2)

    # Apply edits
    new_text = src_text
    for name, old, new in edits:
        new_text = new_text.replace(old, new)

    post_md5 = hashlib.md5(new_text.encode()).hexdigest()
    print(f"  post-edit size: {len(new_text):,} chars  md5: {post_md5}")

    # Write via /tmp + cp + verify per FUSE safety pattern
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".py") as tf:
        tf.write(new_text)
        tmp_path = Path(tf.name)
    tmp_md5 = _md5(tmp_path)
    if tmp_md5 != post_md5:
        print(f"  ABORT — tmp md5 {tmp_md5} != expected {post_md5}")
        sys.exit(3)
    print(f"  tmp file: {tmp_path}  md5 verified")

    shutil.copy2(tmp_path, SRC)
    final_md5 = _md5(SRC)
    if final_md5 != post_md5:
        print(f"  ABORT — post-cp md5 {final_md5} != expected {post_md5}")
        sys.exit(4)
    print(f"  cp back to mount: md5 {final_md5} VERIFIED")
    tmp_path.unlink()

    # Syntax sanity
    import py_compile
    try:
        py_compile.compile(str(SRC), doraise=True)
        print(f"  py_compile: OK")
    except py_compile.PyCompileError as e:
        print(f"  py_compile FAIL: {e}")
        sys.exit(5)

    print(f"\n  Patcher SUCCESS")


if __name__ == "__main__":
    apply_patch()
