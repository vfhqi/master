#!/usr/bin/env python3
"""
=============================================================================
Session 47 post-apply Stage-distribution verification
=============================================================================
Project: SA - Master Dashboard
Session: S47 (18-May-2026)
Author: [W] Watson (Systems Architect role)
Decisions: D-MD-V2-112 (S1 cushion), D-MD-V2-113 (S2 criteria),
           D-MD-V2-114 (S3 prior-uptrend), D-MD-V2-115 (S4 rewrite)

Purpose: After Richard applies the four S47 Stage patchers (S1→S2→S3→S4),
         runs refresh_all.py + build_dashboard.py, run this script against
         the regenerated filter-results.json to verify Stage distributions
         are reasonable and invariants hold.

USAGE
-----
    python3 verify_s47_stages.py                          # uses default path
    python3 verify_s47_stages.py path/to/filter-results.json

DEFAULT PATH
    master-dashboard/data/filter-results.json (relative to script, searching upward)

WHAT THIS SCRIPT CHECKS
------------------------
Stage-specific invariants (post-Task-3):
  S1. Cushion removal: S1 Probable count should DROP from pre-patch baseline.
  S2. New 13-criteria ladder: if Probable > 20% of universe (>~189), flag
      for threshold tightening to 11/13. Also verify total=13.
  S3. prior_uptrend gate: no stock may have Stage 3 rated AND prior_uptrend=False.
      Also verify prior_uptrend field exists on every stock.
  S4. Specific-combination ladder: verify every stock's rating matches exactly
      one of the defined test-combination patterns.
  S4b. _stage_3_fired_in_last_60d helper: verify info_stage_3_lookback field
       is present and either has data or reports "insufficient history".

Cross-stage checks:
  X1. S1+S4 Probable collision count should be LOWER than pre-patch (was 124).

Distribution overview:
  D1-D4. Full rating distribution per Stage.

PRE-PATCH BASELINES (from 17-May audit memo + S47 handoff, 946-stock universe)
  - S1 Probable (Early+Late): ~260
  - S4 Probable: 463
  - S1+S4 Probable collision: 124
  - S3 Probable Invalidation: 66
  - S3 Plausible Invalidation: 241

OUTPUT
------
Prints summary table. Writes JSON report alongside input file
(filter-results.json.s47-stages-verify.json).
Exit code: 0 = all checks pass, 1 = hard failure, 2 = warnings only.
=============================================================================
"""
import json
import os
import sys
import argparse
from collections import Counter, defaultdict

# Valid rating sets per stage (post-S47)
S1_RATINGS = {"None", "Possible", "Plausible", "Probable Early", "Probable Late"}
S2_RATINGS = {"None", "Possible", "Plausible", "Probable"}
S3_RATINGS = {"None", "Possible Topping", "Plausible Invalidation", "Probable Invalidation"}
S4_RATINGS = {"None", "Possible", "Plausible", "Probable", "Probable (Accelerating)"}

# Pre-patch baselines (from audit memo + handoff, 946-stock universe)
PRE_PATCH = {
    "s1_probable": 260,          # Early + Late combined
    "s4_probable": 463,          # all Probable variants
    "s1_s4_collision": 124,      # both Probable simultaneously
    "s3_probable": 66,           # Probable Invalidation
    "s3_plausible": 241,         # Plausible Invalidation
    "universe": 946,
}


def _load_filter_results(path):
    """Load filter-results.json, handling potential truncation gracefully."""
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    try:
        data = json.loads(raw)
        stocks = data.get("stocks", data) if isinstance(data, dict) else data
        if isinstance(stocks, dict):
            stocks = list(stocks.values())
        return stocks, None
    except json.JSONDecodeError as e:
        # File may be truncated — try to salvage
        import re
        ticker_pat = re.compile(r'\{\s*"ticker"\s*:\s*"[^"]+"')
        splits = [m.start() for m in ticker_pat.finditer(raw)]
        stocks = []
        for i in range(len(splits)):
            start = splits[i]
            end = splits[i + 1] if i + 1 < len(splits) else len(raw)
            chunk = raw[start:end].rstrip().rstrip(",").rstrip()
            try:
                stocks.append(json.loads(chunk))
            except json.JSONDecodeError:
                pass
        warning = (f"JSON truncated (parsed {len(stocks)} of expected "
                   f"{PRE_PATCH['universe']}; JSONDecodeError: {e})")
        return stocks, warning


def check_s1_cushion_removal(stocks, results):
    """S1: With cushion removed, Probable count should DROP."""
    s1_probable_count = 0
    for s in stocks:
        md = s.get("md_v2", {})
        r = md.get("stage_1", {}).get("rating", "None")
        if r in ("Probable Early", "Probable Late"):
            s1_probable_count += 1
        if r not in S1_RATINGS:
            results["s1_invalid_rating"].append((s.get("ticker"), r))

    results["s1_probable_count"] = s1_probable_count
    baseline = PRE_PATCH["s1_probable"]
    dropped = s1_probable_count < baseline
    results["s1_cushion_drop"] = dropped
    return dropped


def check_s2_criteria(stocks, n_stocks, results):
    """S2: 13 criteria, new ladder. Flag if Probable > 20%."""
    s2_probable_count = 0
    for s in stocks:
        md = s.get("md_v2", {})
        s2 = md.get("stage_2", {})
        r = s2.get("rating", "None")
        total = s2.get("total")
        count = s2.get("count")

        if r not in S2_RATINGS:
            results["s2_invalid_rating"].append((s.get("ticker"), r))
        if total is not None and total != 13:
            results["s2_total_not_13"].append((s.get("ticker"), total))
        if r == "Probable":
            s2_probable_count += 1
            # Verify count >= 10
            if count is not None and count < 10:
                results["s2_probable_low_count"].append(
                    (s.get("ticker"), count))
        elif r == "Plausible":
            if count is not None and (count < 9 or count >= 10):
                results["s2_plausible_count_mismatch"].append(
                    (s.get("ticker"), count))
        elif r == "Possible":
            if count is not None and (count < 8 or count >= 9):
                results["s2_possible_count_mismatch"].append(
                    (s.get("ticker"), count))

    pct = (s2_probable_count / n_stocks * 100) if n_stocks else 0
    results["s2_probable_count"] = s2_probable_count
    results["s2_probable_pct"] = pct
    threshold_breach = pct > 20
    results["s2_threshold_breach"] = threshold_breach
    return not threshold_breach


def check_s3_prior_uptrend(stocks, results):
    """S3: Any stock with Stage 3 rated AND prior_uptrend=False must be None."""
    invariant_pass = True
    for s in stocks:
        tk = s.get("ticker", "?")
        md = s.get("md_v2", {})
        s3 = md.get("stage_3", {})
        r = s3.get("rating", "None")

        # Check prior_uptrend field exists
        if "prior_uptrend" not in s3:
            results["s3_prior_uptrend_missing"].append(tk)
            continue

        prior_uptrend = s3.get("prior_uptrend")

        # HARD INVARIANT: if prior_uptrend is False, rating MUST be None
        if prior_uptrend is False and r != "None":
            results["s3_uptrend_gate_violation"].append((tk, r))
            invariant_pass = False

        if r not in S3_RATINGS and r != "None":
            results["s3_invalid_rating"].append((tk, r))

    results["s3_gate_invariant_pass"] = invariant_pass
    return invariant_pass


def check_s4_combination_ladder(stocks, results):
    """S4: Verify every stock's rating matches its test-combination pattern."""
    invariant_pass = True
    for s in stocks:
        tk = s.get("ticker", "?")
        md = s.get("md_v2", {})
        s4 = md.get("stage_4", {})
        r = s4.get("rating", "None")
        tests = s4.get("tests", {})

        if r not in S4_RATINGS:
            results["s4_invalid_rating"].append((tk, r))

        t1 = tests.get("T1_200D_declining", False)
        t2 = tests.get("T2_200D_decline_accelerating", False)
        t3 = tests.get("T3_total_stack_down", False)
        t4 = tests.get("T4_150_below_200", False)
        t5 = tests.get("T5_50_below_150", False)

        # Determine expected rating from combination rules
        if t1 and t3 and t4 and t5:
            if t2:
                expected = "Probable (Accelerating)"
            else:
                expected = "Probable"
        elif t4 and t5:
            expected = "Plausible"
        elif t4 or t5:
            expected = "Possible"
        else:
            expected = "None"

        # NOTE: The info_stage_3_lookback does NOT gate the rating
        # (D-MD-V2-115 deviation from audit memo Rec 4). So expected
        # rating is purely from the combination ladder above.

        if r != expected:
            results["s4_ladder_mismatch"].append((tk, r, expected,
                                                   {k: v for k, v in tests.items()
                                                    if k.startswith("T")}))
            invariant_pass = False

    results["s4_ladder_invariant_pass"] = invariant_pass
    return invariant_pass


def check_s4_lookback_helper(stocks, results):
    """S4b: Verify info_stage_3_lookback field present and sensible."""
    has_field = 0
    has_history_depth = 0
    has_insufficient = 0
    missing_field = 0

    for s in stocks:
        tk = s.get("ticker", "?")
        md = s.get("md_v2", {})
        s4 = md.get("stage_4", {})

        lookback = s4.get("info_stage_3_lookback")
        if lookback is None:
            results["s4_lookback_missing"].append(tk)
            missing_field += 1
            continue

        has_field += 1

        # Check for history_depth_ok field
        depth_ok = lookback.get("history_depth_ok")
        if depth_ok is True:
            has_history_depth += 1
        elif depth_ok is False:
            has_insufficient += 1
        # else: field exists but depth_ok not present — still acceptable

    results["s4_lookback_stats"] = {
        "has_field": has_field,
        "missing_field": missing_field,
        "has_history_depth": has_history_depth,
        "has_insufficient_history": has_insufficient,
    }

    # Pass if field exists on all stocks (even if all say insufficient history)
    all_present = missing_field == 0
    results["s4_lookback_field_present"] = all_present
    return all_present


def check_cross_stage_collisions(stocks, results):
    """X1: S1+S4 Probable collision count should be LOWER than pre-patch (124)."""
    s1_probable = set()
    s4_probable = set()

    for s in stocks:
        tk = s.get("ticker", "?")
        md = s.get("md_v2", {})
        s1r = md.get("stage_1", {}).get("rating", "None")
        s4r = md.get("stage_4", {}).get("rating", "None")

        if s1r in ("Probable Early", "Probable Late"):
            s1_probable.add(tk)
        if s4r.startswith("Probable"):
            s4_probable.add(tk)

    collisions = s1_probable & s4_probable
    results["x1_s1_probable"] = len(s1_probable)
    results["x1_s4_probable"] = len(s4_probable)
    results["x1_collision_count"] = len(collisions)
    results["x1_collision_tickers"] = sorted(collisions)
    results["x1_collision_reduced"] = len(collisions) < PRE_PATCH["s1_s4_collision"]
    results["x1_single_digits"] = len(collisions) < 10
    return results["x1_collision_reduced"]


def compute_distributions(stocks):
    """Compute full rating distribution per stage."""
    dists = {}
    for sk in ["stage_1", "stage_2", "stage_3", "stage_4"]:
        c = Counter()
        for s in stocks:
            r = s.get("md_v2", {}).get(sk, {}).get("rating", "N/A")
            c[r] += 1
        dists[sk] = dict(c)
    return dists


def run(fr_path):
    print(f"Loading: {fr_path}")
    stocks, parse_warning = _load_filter_results(fr_path)
    N = len(stocks)
    print(f"Universe: {N} stocks")
    if parse_warning:
        print(f"  WARNING: {parse_warning}")
    print()

    results = defaultdict(list)
    errors = []
    warnings = []

    if N == 0:
        print("[ABORT] No stock data — cannot run Stage checks.")
        return 1

    # ═══════════════════════════════════════════════════════════════════
    # CHECK S1: Cushion removal — Probable count should drop
    # ═══════════════════════════════════════════════════════════════════
    print("=" * 72)
    print("CHECK S1: Stage 1 cushion removal (D-MD-V2-112)")
    print("=" * 72)
    s1_pass = check_s1_cushion_removal(stocks, results)
    baseline = PRE_PATCH["s1_probable"]
    actual = results["s1_probable_count"]
    delta = actual - baseline
    print(f"  S1 Probable (Early+Late): {actual}")
    print(f"  Pre-patch baseline:       {baseline}")
    print(f"  Delta:                    {delta:+d}")
    if s1_pass:
        print(f"  [OK] Probable count dropped as expected (cushion removal working)")
    else:
        print(f"  [WARN] Probable count did NOT drop — cushion removal may not have applied")
        warnings.append(f"S1 Probable count {actual} >= baseline {baseline}")

    if results["s1_invalid_rating"]:
        print(f"  [FAIL] {len(results['s1_invalid_rating'])} stocks with invalid S1 rating")
        for sample in results["s1_invalid_rating"][:5]:
            print(f"    - {sample}")
        errors.append("S1 invalid ratings found")
    print()

    # ═══════════════════════════════════════════════════════════════════
    # CHECK S2: 13 criteria + new ladder + 20% audit hook
    # ═══════════════════════════════════════════════════════════════════
    print("=" * 72)
    print("CHECK S2: Stage 2 new criteria + ladder (D-MD-V2-113)")
    print("=" * 72)
    s2_pass = check_s2_criteria(stocks, N, results)
    print(f"  S2 Probable:       {results['s2_probable_count']} of {N} "
          f"({results['s2_probable_pct']:.1f}%)")
    print(f"  20% threshold:     {'BREACHED' if results['s2_threshold_breach'] else 'OK'}")

    if results["s2_threshold_breach"]:
        print(f"  [ACTION REQUIRED] Probable > 20% of universe.")
        print(f"  → Tighten Probable threshold from 10/13 to 11/13 and re-run.")
        warnings.append(f"S2 Probable at {results['s2_probable_pct']:.1f}% — exceeds 20% threshold")

    if results["s2_total_not_13"]:
        print(f"  [FAIL] {len(results['s2_total_not_13'])} stocks with total != 13")
        for sample in results["s2_total_not_13"][:5]:
            print(f"    - {sample}")
        errors.append(f"S2 total!=13 on {len(results['s2_total_not_13'])} stocks")
    else:
        print(f"  [OK] All stocks have total=13")

    if results["s2_probable_low_count"]:
        print(f"  [FAIL] {len(results['s2_probable_low_count'])} Probable stocks with count < 10")
        errors.append("S2 Probable stocks with count < 10")
    if results["s2_plausible_count_mismatch"]:
        print(f"  [FAIL] {len(results['s2_plausible_count_mismatch'])} Plausible stocks "
              f"with count not in [9]")
        errors.append("S2 Plausible ladder mismatch")
    if results["s2_possible_count_mismatch"]:
        print(f"  [FAIL] {len(results['s2_possible_count_mismatch'])} Possible stocks "
              f"with count not in [8]")
        errors.append("S2 Possible ladder mismatch")
    if results["s2_invalid_rating"]:
        print(f"  [FAIL] {len(results['s2_invalid_rating'])} stocks with invalid S2 rating")
        errors.append("S2 invalid ratings found")
    print()

    # ═══════════════════════════════════════════════════════════════════
    # CHECK S3: prior_uptrend gate — hard invariant
    # ═══════════════════════════════════════════════════════════════════
    print("=" * 72)
    print("CHECK S3: Prior-uptrend gate (D-MD-V2-114)")
    print("=" * 72)
    s3_pass = check_s3_prior_uptrend(stocks, results)

    s3_field_missing = len(results["s3_prior_uptrend_missing"])
    if s3_field_missing == 0:
        print(f"  [OK] prior_uptrend field present on all {N} stocks")
    else:
        print(f"  [FAIL] prior_uptrend field missing on {s3_field_missing} stocks")
        errors.append(f"S3 prior_uptrend field missing on {s3_field_missing} stocks")
        for sample in results["s3_prior_uptrend_missing"][:5]:
            print(f"    - {sample}")

    violations = len(results["s3_uptrend_gate_violation"])
    if violations == 0:
        print(f"  [OK] Gate invariant holds: no stock rated with prior_uptrend=False")
    else:
        print(f"  [FAIL] INVARIANT VIOLATION: {violations} stocks rated despite "
              f"prior_uptrend=False")
        errors.append(f"S3 gate invariant violated on {violations} stocks")
        for tk, r in results["s3_uptrend_gate_violation"][:10]:
            print(f"    - {tk}: rating={r}")

    # Distribution check — Probable and Plausible should drop from baselines
    s3_dist = Counter()
    for s in stocks:
        r = s.get("md_v2", {}).get("stage_3", {}).get("rating", "None")
        s3_dist[r] += 1
    s3_prob = s3_dist.get("Probable Invalidation", 0)
    s3_plaus = s3_dist.get("Plausible Invalidation", 0)
    print(f"  S3 Probable Invalidation:  {s3_prob} (was {PRE_PATCH['s3_probable']})")
    print(f"  S3 Plausible Invalidation: {s3_plaus} (was {PRE_PATCH['s3_plausible']})")
    if s3_prob < PRE_PATCH["s3_probable"]:
        print(f"  [OK] S3 Probable count dropped (prior_uptrend gate filtering)")
    else:
        print(f"  [INFO] S3 Probable count did not drop — may be expected if "
              f"few stocks lacked prior uptrend")

    if results["s3_invalid_rating"]:
        print(f"  [FAIL] {len(results['s3_invalid_rating'])} invalid S3 ratings")
        errors.append("S3 invalid ratings found")
    print()

    # ═══════════════════════════════════════════════════════════════════
    # CHECK S4: Specific-combination ladder (D-MD-V2-115)
    # ═══════════════════════════════════════════════════════════════════
    print("=" * 72)
    print("CHECK S4: Combination ladder (D-MD-V2-115)")
    print("=" * 72)
    s4_pass = check_s4_combination_ladder(stocks, results)

    mismatches = len(results["s4_ladder_mismatch"])
    if mismatches == 0:
        print(f"  [OK] All {N} stocks match combination-ladder rules exactly")
    else:
        print(f"  [FAIL] {mismatches} stocks have rating/test-combination mismatch")
        errors.append(f"S4 ladder mismatch on {mismatches} stocks")
        for tk, actual_r, expected_r, tests in results["s4_ladder_mismatch"][:10]:
            print(f"    - {tk}: got '{actual_r}', expected '{expected_r}'")
            active = [k for k, v in tests.items() if v]
            print(f"      tests true: {', '.join(active) if active else '(none)'}")

    # Check for Probable (Accelerating) variant
    s4_accel = sum(1 for s in stocks
                   if s.get("md_v2", {}).get("stage_4", {}).get("rating")
                   == "Probable (Accelerating)")
    s4_prob = sum(1 for s in stocks
                  if s.get("md_v2", {}).get("stage_4", {}).get("rating", "")
                  .startswith("Probable"))
    print(f"  S4 Probable (total):        {s4_prob} (was {PRE_PATCH['s4_probable']})")
    print(f"  S4 Probable (Accelerating): {s4_accel}")
    print(f"  S4 Probable (base):         {s4_prob - s4_accel}")
    if s4_prob < PRE_PATCH["s4_probable"]:
        print(f"  [OK] S4 Probable dropped from {PRE_PATCH['s4_probable']} "
              f"(combination ladder is stricter)")
    else:
        print(f"  [WARN] S4 Probable did not drop — combination ladder may not be applied")
        warnings.append(f"S4 Probable {s4_prob} >= baseline {PRE_PATCH['s4_probable']}")

    if results["s4_invalid_rating"]:
        print(f"  [FAIL] {len(results['s4_invalid_rating'])} invalid S4 ratings")
        errors.append("S4 invalid ratings found")
    print()

    # ═══════════════════════════════════════════════════════════════════
    # CHECK S4b: _stage_3_fired_in_last_60d helper output
    # ═══════════════════════════════════════════════════════════════════
    print("=" * 72)
    print("CHECK S4b: Stage-3 lookback helper (info_stage_3_lookback)")
    print("=" * 72)
    s4b_pass = check_s4_lookback_helper(stocks, results)
    stats = results["s4_lookback_stats"]
    print(f"  Field present:           {stats['has_field']} of {N}")
    print(f"  Field missing:           {stats['missing_field']}")
    print(f"  With sufficient history: {stats['has_history_depth']}")
    print(f"  Insufficient history:    {stats['has_insufficient_history']}")

    if s4b_pass:
        print(f"  [OK] info_stage_3_lookback field present on all stocks")
    else:
        print(f"  [FAIL] info_stage_3_lookback field missing on "
              f"{stats['missing_field']} stocks")
        errors.append(f"S4 lookback field missing on {stats['missing_field']} stocks")
        for tk in results["s4_lookback_missing"][:5]:
            print(f"    - {tk}")
        if len(results["s4_lookback_missing"]) > 5:
            print(f"    ... and {len(results['s4_lookback_missing']) - 5} more")

    if stats["has_insufficient_history"] == stats["has_field"] and stats["has_field"] > 0:
        print(f"  [INFO] All stocks report insufficient history — expected on first run")
        print(f"         (stage-snapshots.json has ~11 days; need ≥10 for depth_ok)")
    print()

    # ═══════════════════════════════════════════════════════════════════
    # CHECK X1: Cross-stage S1+S4 Probable collisions
    # ═══════════════════════════════════════════════════════════════════
    print("=" * 72)
    print("CHECK X1: S1+S4 Probable collision (cross-stage)")
    print("=" * 72)
    x1_pass = check_cross_stage_collisions(stocks, results)
    print(f"  S1 Probable (Early+Late): {results['x1_s1_probable']}")
    print(f"  S4 Probable (all):        {results['x1_s4_probable']}")
    print(f"  Collisions:               {results['x1_collision_count']} "
          f"(was {PRE_PATCH['s1_s4_collision']})")

    if results["x1_single_digits"]:
        print(f"  [OK] Collision count in single digits — target met")
    elif results["x1_collision_reduced"]:
        print(f"  [OK] Collision count reduced from {PRE_PATCH['s1_s4_collision']} "
              f"(but not yet single digits)")
        warnings.append(f"S1+S4 collisions = {results['x1_collision_count']} "
                        f"(reduced but not single digits)")
    else:
        print(f"  [WARN] Collision count NOT reduced from pre-patch baseline")
        warnings.append(f"S1+S4 collisions = {results['x1_collision_count']} "
                        f"(>= pre-patch {PRE_PATCH['s1_s4_collision']})")

    if results["x1_collision_tickers"]:
        for tk in results["x1_collision_tickers"][:15]:
            print(f"    - {tk}")
        if len(results["x1_collision_tickers"]) > 15:
            print(f"    ... and {len(results['x1_collision_tickers']) - 15} more")
    print()

    # ═══════════════════════════════════════════════════════════════════
    # DISTRIBUTION OVERVIEW
    # ═══════════════════════════════════════════════════════════════════
    print("=" * 72)
    print("DISTRIBUTION OVERVIEW — all four Stages")
    print("=" * 72)
    dists = compute_distributions(stocks)
    for sk in ["stage_1", "stage_2", "stage_3", "stage_4"]:
        print(f"\n  {sk}:")
        for rating in sorted(dists[sk].keys()):
            count = dists[sk][rating]
            pct = (count / N * 100) if N else 0
            print(f"    {rating:30s}: {count:4d} ({pct:5.1f}%)")
    print()

    # ═══════════════════════════════════════════════════════════════════
    # VERDICT
    # ═══════════════════════════════════════════════════════════════════
    print("=" * 72)
    print("VERDICT")
    print("=" * 72)

    hard_pass = s3_pass and s4_pass and s4b_pass
    soft_pass = s1_pass and s2_pass and x1_pass

    if hard_pass and soft_pass and not errors and not warnings:
        print("  OVERALL: ALL CHECKS PASS")
        exit_code = 0
    elif not hard_pass or errors:
        print("  OVERALL: HARD FAILURE — structural invariants violated")
        exit_code = 1
    else:
        print("  OVERALL: PASS WITH WARNINGS — distribution anomalies detected")
        exit_code = 2

    if errors:
        print(f"\n  ERRORS ({len(errors)}):")
        for e in errors:
            print(f"    [ERROR] {e}")
    if warnings:
        print(f"\n  WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"    [WARN]  {w}")
    if parse_warning:
        print(f"\n  PARSE WARNING: {parse_warning}")
    print()

    # Write JSON report
    out = fr_path + ".s47-stages-verify.json"
    report = {
        "fr_path": fr_path,
        "universe_size": N,
        "parse_warning": parse_warning,
        "pre_patch_baselines": PRE_PATCH,
        "checks": {
            "s1_cushion_removal": {
                "pass": s1_pass,
                "probable_count": results["s1_probable_count"],
                "baseline": PRE_PATCH["s1_probable"],
                "invalid_ratings": results["s1_invalid_rating"][:20],
            },
            "s2_criteria": {
                "pass": s2_pass,
                "probable_count": results["s2_probable_count"],
                "probable_pct": results["s2_probable_pct"],
                "threshold_breach": results["s2_threshold_breach"],
                "total_not_13": results["s2_total_not_13"][:20],
                "ladder_mismatches": {
                    "probable_low_count": results["s2_probable_low_count"][:20],
                    "plausible_mismatch": results["s2_plausible_count_mismatch"][:20],
                    "possible_mismatch": results["s2_possible_count_mismatch"][:20],
                },
                "invalid_ratings": results["s2_invalid_rating"][:20],
            },
            "s3_prior_uptrend": {
                "pass": s3_pass,
                "field_missing_count": len(results["s3_prior_uptrend_missing"]),
                "gate_violations": results["s3_uptrend_gate_violation"][:20],
                "invalid_ratings": results["s3_invalid_rating"][:20],
            },
            "s4_combination_ladder": {
                "pass": s4_pass,
                "mismatches": [(tk, ar, er)
                               for tk, ar, er, _ in results["s4_ladder_mismatch"][:30]],
                "invalid_ratings": results["s4_invalid_rating"][:20],
            },
            "s4_lookback_helper": {
                "pass": s4b_pass,
                "stats": results["s4_lookback_stats"],
                "missing_sample": results["s4_lookback_missing"][:20],
            },
            "x1_cross_stage_collisions": {
                "reduced": results["x1_collision_reduced"],
                "single_digits": results["x1_single_digits"],
                "count": results["x1_collision_count"],
                "baseline": PRE_PATCH["s1_s4_collision"],
                "tickers": results["x1_collision_tickers"][:30],
            },
        },
        "distributions": dists,
        "errors": errors,
        "warnings": warnings,
        "exit_code": exit_code,
    }
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"Detailed report: {out}")

    return exit_code


def main():
    ap = argparse.ArgumentParser(
        description="S47 post-apply Stage-distribution verification")
    ap.add_argument("filter_results_path", nargs="?", default=None,
                    help="Path to filter-results.json "
                         "(default: master-dashboard/data/filter-results.json)")
    args = ap.parse_args()
    fr_path = args.filter_results_path

    if not fr_path:
        here = os.path.abspath(os.path.dirname(__file__))
        for _ in range(6):
            candidate = os.path.join(here, "master-dashboard", "data",
                                     "filter-results.json")
            if os.path.exists(candidate):
                fr_path = candidate
                break
            candidate2 = os.path.join(here, "data", "filter-results.json")
            if os.path.exists(candidate2):
                fr_path = candidate2
                break
            here = os.path.abspath(os.path.join(here, os.pardir))
        if not fr_path:
            print("ERR: cannot find filter-results.json; pass path explicitly",
                  file=sys.stderr)
            return 1
    return run(fr_path)


if __name__ == "__main__":
    sys.exit(main())
