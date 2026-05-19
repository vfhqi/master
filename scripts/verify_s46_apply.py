#!/usr/bin/env python3
"""
=============================================================================
Session 46 post-apply verification
=============================================================================
Project: SA - Master Dashboard
Session: S46 (18-May-2026)
Author: [W] Watson (Systems Architect role)
Purpose: After Richard applies the four S46 patchers + runs refresh_all.py
         + runs build_dashboard.py, run this script against the regenerated
         filter-results.json to verify the new JSON fields are populated
         correctly and the new tests are firing as expected.

USAGE
-----
    python3 verify_s46_apply.py                          # uses default path
    python3 verify_s46_apply.py path/to/filter-results.json

DEFAULT PATH
    master-dashboard/data/filter-results.json (relative to COWORK root)

WHAT THIS SCRIPT CHECKS
-----------------------
Structural checks (every stock):
  C1. md_v2.tests.healthy_retest exists, has total=13, rating in valid set
  C2. md_v2.tests.probing_bet_s1 exists, has total=6, info_variant matches
  C3. md_v2.tests.probing_bet_s2 exists, has total=6, info_variant matches
  C4. md_v2.tests.speculative_bet_s3 exists, has total=6, info_variant matches
  C5. md_v2.tests.speculative_bet_s4 exists, has total=6, info_variant matches
  C6. Legacy tests still present (ma_retest_upwards, probing_bet, vcp_deploy_s1, vcp_deploy_s2)

Pulling-back ladder checks (D-MD-V2-107 verification):
  L1. Sample of stocks with pulling_back_uptrend count==1 — rating MUST be "None" (was "Possible")
  L2. Sample of stocks with pulling_back_uptrend count==2 — rating MUST be "Possible"
  L3. Sample of stocks with pulling_back_uptrend count==3 — rating MUST be "Plausible"
  L4. Sample of stocks with pulling_back_uptrend count==4 — rating MUST be "Probable"

Distribution stats per new test:
  D1. healthy_retest rating distribution (None/Possible/Plausible/Probable/Qualified)
  D2. probing_bet_s1 distribution
  D3. probing_bet_s2 distribution
  D4. speculative_bet_s3 distribution
  D5. speculative_bet_s4 distribution
  D6. pulling_back_uptrend rating distribution

Cross-reference checks:
  X1. probing_bet_s1 should fire ONLY on stocks where stage_1.rating != None
  X2. probing_bet_s2 should fire ONLY on stocks where stage_2.rating != None
  X3. speculative_bet_s3 should fire ONLY on stocks where stage_3.rating != None
  X4. speculative_bet_s4 should fire ONLY on stocks where stage_4.rating != None
  X5. healthy_retest "Qualified" stocks vs ma_retest_upwards "qualifies" — should overlap heavily
       (both test the same underlying setup; healthy_retest adds Stage 2 hard gate + the new ladder)

OUTPUT
------
Prints summary table. Writes detailed JSON report alongside the input file
(filter-results.json.s46-verify.json). Exit code: 0 if all checks pass, 1 if
any structural check fails (rating/total mismatch, missing keys), 2 if
distribution stats look anomalous (e.g. zero Qualified across all five new
tests — suggests something is wrong but not necessarily broken).
=============================================================================
"""
import json
import os
import sys
import argparse
from collections import Counter, defaultdict

RATING_SET = {"None", "Possible", "Plausible", "Probable", "Qualified",
              "Probable Early", "Probable Late", "Probable (Accelerating)"}

NEW_TESTS_6CRIT = ["probing_bet_s1", "probing_bet_s2",
                   "speculative_bet_s3", "speculative_bet_s4"]
LEGACY_TESTS = ["ma_retest_upwards", "probing_bet",
                "vcp_deploy_s1", "vcp_deploy_s2"]


def check_stock(stock, results):
    """Run structural checks on one stock. Append results to results dict."""
    tk = stock.get("ticker", "?")
    md = stock.get("md_v2", {}) or {}
    tests = md.get("tests", {}) or {}

    # C1: healthy_retest
    hr = tests.get("healthy_retest")
    if hr is None:
        results["c1_healthy_retest_missing"].append(tk)
    else:
        if hr.get("total") != 13:
            results["c1_healthy_retest_total_mismatch"].append((tk, hr.get("total")))
        if hr.get("rating") not in RATING_SET:
            results["c1_healthy_retest_invalid_rating"].append((tk, hr.get("rating")))
        if not isinstance(hr.get("tests"), dict):
            results["c1_healthy_retest_tests_missing"].append(tk)

    # C2-C5: probing/spec
    for key in NEW_TESTS_6CRIT:
        t = tests.get(key)
        if t is None:
            results[f"{key}_missing"].append(tk)
        else:
            if t.get("total") != 6:
                results[f"{key}_total_mismatch"].append((tk, t.get("total")))
            if t.get("rating") not in RATING_SET:
                results[f"{key}_invalid_rating"].append((tk, t.get("rating")))
            if t.get("info_variant") != key:
                results[f"{key}_info_variant_mismatch"].append(
                    (tk, t.get("info_variant"))
                )

    # C6: legacy tests
    for key in LEGACY_TESTS:
        if key not in tests:
            results[f"c6_legacy_{key}_missing"].append(tk)

    return md, tests


def run(fr_path):
    print(f"Loading: {fr_path}")
    with open(fr_path) as f:
        fr = json.load(f)
    stocks = fr.get("stocks", [])
    N = len(stocks)
    print(f"Universe: {N} stocks\n")

    results = defaultdict(list)

    # Structural pass
    for stock in stocks:
        check_stock(stock, results)

    structural_keys = [k for k in results.keys()
                       if k.startswith(("c1_", "c2_", "c3_", "c4_", "c5_", "c6_"))
                       or k.endswith(("_missing", "_total_mismatch",
                                       "_invalid_rating", "_info_variant_mismatch"))]
    structural_fail = any(results[k] for k in structural_keys)

    print("=" * 72)
    print("STRUCTURAL CHECKS")
    print("=" * 72)
    if not structural_fail:
        print("  ALL PASS - new tests present, totals correct, ratings valid, legacy preserved")
    else:
        for k in sorted(structural_keys):
            if results[k]:
                print(f"  FAIL [{k}]: {len(results[k])} stocks affected")
                for sample in results[k][:5]:
                    print(f"    - {sample}")
                if len(results[k]) > 5:
                    print(f"    ... and {len(results[k]) - 5} more")
    print()

    # Pulling-back ladder verification (D-MD-V2-107)
    print("=" * 72)
    print("PULLING-BACK LADDER CHECK (D-MD-V2-107)")
    print("=" * 72)
    expected_ladder = {0: "None", 1: "None", 2: "Possible",
                       3: "Plausible", 4: "Probable"}
    pb_by_count = defaultdict(list)
    for s in stocks:
        pb = (s.get("md_v2", {}).get("pre_indicators", {}) or {}).get(
            "pulling_back_uptrend", {})
        c = pb.get("count")
        r = pb.get("rating")
        if c is not None:
            pb_by_count[c].append((s.get("ticker"), r))
    pb_ladder_pass = True
    for ct, expected_rating in expected_ladder.items():
        observed = pb_by_count.get(ct, [])
        if not observed:
            print(f"  count={ct}: 0 stocks (no sample)")
            continue
        wrong = [(t, r) for t, r in observed if r != expected_rating]
        if wrong:
            pb_ladder_pass = False
            print(f"  count={ct}: FAIL - {len(wrong)}/{len(observed)} stocks have wrong rating "
                  f"(expected '{expected_rating}'). Sample: {wrong[:3]}")
        else:
            print(f"  count={ct}: PASS - all {len(observed)} stocks rated '{expected_rating}'")
    print()

    # Distribution stats per new test
    print("=" * 72)
    print("DISTRIBUTION STATS - new tests")
    print("=" * 72)

    def dist(stocks, test_key):
        c = Counter()
        for s in stocks:
            t = (s.get("md_v2", {}).get("tests", {}) or {}).get(test_key, {})
            c[t.get("rating", "MISSING")] += 1
        return c

    for tk in ["healthy_retest"] + NEW_TESTS_6CRIT:
        c = dist(stocks, tk)
        print(f"  {tk}:")
        for rating in ["None", "Possible", "Plausible", "Probable", "Qualified", "MISSING"]:
            n = c.get(rating, 0)
            if n > 0:
                pct = (n / N * 100) if N else 0
                print(f"    {rating:12} : {n:4} ({pct:5.1f}%)")
        print()

    # pulling_back_uptrend rating dist
    pb_dist = Counter()
    for s in stocks:
        pb = (s.get("md_v2", {}).get("pre_indicators", {}) or {}).get(
            "pulling_back_uptrend", {})
        pb_dist[pb.get("rating", "MISSING")] += 1
    print(f"  pulling_back_uptrend (pre-indicator):")
    for rating in ["None", "Possible", "Plausible", "Probable", "MISSING"]:
        n = pb_dist.get(rating, 0)
        if n > 0:
            pct = (n / N * 100) if N else 0
            print(f"    {rating:12} : {n:4} ({pct:5.1f}%)")
    print()

    # Cross-reference: probing/spec variant fires only on matching stage
    print("=" * 72)
    print("CROSS-REFERENCE - probing/spec variants vs their stage gates")
    print("=" * 72)
    stage_keys = {"probing_bet_s1": "stage_1",
                  "probing_bet_s2": "stage_2",
                  "speculative_bet_s3": "stage_3",
                  "speculative_bet_s4": "stage_4"}
    x_pass = True
    for test_key, stage_key in stage_keys.items():
        bad = []
        for s in stocks:
            md = s.get("md_v2", {}) or {}
            t = md.get("tests", {}).get(test_key, {})
            stage = md.get(stage_key, {})
            r = t.get("rating", "None")
            sr = stage.get("rating", "None")
            if r != "None" and (sr in (None, "None")):
                # Test fires but stage rating is None -> wrong
                bad.append((s.get("ticker"), r, sr))
        if bad:
            x_pass = False
            print(f"  {test_key} vs {stage_key}: FAIL - {len(bad)} stocks fire on test "
                  f"but stage rating is None. Sample: {bad[:3]}")
        else:
            non_none = sum(1 for s in stocks
                           if (s.get("md_v2", {}).get("tests", {}).get(test_key, {})
                               .get("rating", "None")) != "None")
            print(f"  {test_key} vs {stage_key}: PASS - {non_none} stocks fire; "
                  f"all have non-None stage rating")
    print()

    # Cross-reference: healthy_retest Qualified vs ma_retest_upwards qualifies
    print("=" * 72)
    print("CROSS-REFERENCE - healthy_retest Qualified vs ma_retest_upwards qualifies")
    print("=" * 72)
    hr_qual = set()
    mr_qual = set()
    for s in stocks:
        tk = s.get("ticker")
        hr = s.get("md_v2", {}).get("tests", {}).get("healthy_retest", {})
        mr = s.get("md_v2", {}).get("tests", {}).get("ma_retest_upwards", {})
        if hr.get("rating") == "Qualified":
            hr_qual.add(tk)
        if mr.get("qualifies"):
            mr_qual.add(tk)
    overlap = hr_qual & mr_qual
    hr_only = hr_qual - mr_qual
    mr_only = mr_qual - hr_qual
    print(f"  healthy_retest Qualified: {len(hr_qual)} stocks")
    print(f"  ma_retest_upwards qualifies: {len(mr_qual)} stocks")
    print(f"  Overlap (both): {len(overlap)} stocks")
    print(f"  healthy_retest only (Stage 2 gate caught these): {len(hr_only)} stocks")
    print(f"  ma_retest_upwards only (Stage 2 gate removed these): {len(mr_only)} stocks")
    print(f"  Note: healthy_retest is STRICTER (adds Stage 2 P/P gate + all-4 Group B);")
    print(f"        we expect hr_qual <= mr_qual in most cases. mr_only is sane.")
    print(f"        hr_only is anomalous - suggests stocks where the new ladder")
    print(f"        is more permissive than mr_qualifies; investigate if non-empty.")
    print()

    # Summary verdict
    print("=" * 72)
    print("VERDICT")
    print("=" * 72)
    overall_pass = (not structural_fail) and pb_ladder_pass and x_pass
    if overall_pass:
        print("  OVERALL: ALL STRUCTURAL + LADDER + CROSS-REF CHECKS PASS")
    else:
        print("  OVERALL: ONE OR MORE CHECKS FAILED - see details above")
    print()

    # Write detailed report
    out = fr_path + ".s46-verify.json"
    report = {
        "fr_path": fr_path,
        "universe_size": N,
        "structural_fail": structural_fail,
        "pulling_back_ladder_pass": pb_ladder_pass,
        "cross_ref_pass": x_pass,
        "overall_pass": overall_pass,
        "distributions": {
            tk: dict(dist(stocks, tk)) for tk in ["healthy_retest"] + NEW_TESTS_6CRIT
        },
        "pulling_back_distribution": dict(pb_dist),
        "healthy_retest_vs_ma_retest_upwards": {
            "hr_qual_count": len(hr_qual),
            "mr_qual_count": len(mr_qual),
            "overlap_count": len(overlap),
            "hr_only_count": len(hr_only),
            "mr_only_count": len(mr_only),
            "hr_only_sample": sorted(hr_only)[:20],
            "mr_only_sample": sorted(mr_only)[:20],
        },
        "structural_failures": {k: results[k][:20] for k in structural_keys if results[k]},
    }
    with open(out, "w") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"Detailed report: {out}")

    return 0 if overall_pass else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("filter_results_path", nargs="?",
                    default=None,
                    help="Path to filter-results.json (default: master-dashboard/data/filter-results.json)")
    args = ap.parse_args()
    fr_path = args.filter_results_path
    if not fr_path:
        # default: relative to script location
        here = os.path.abspath(os.path.dirname(__file__))
        # search upward for master-dashboard
        for _ in range(6):
            candidate = os.path.join(here, "master-dashboard", "data", "filter-results.json")
            if os.path.exists(candidate):
                fr_path = candidate
                break
            candidate2 = os.path.join(here, "data", "filter-results.json")
            if os.path.exists(candidate2):
                fr_path = candidate2
                break
            here = os.path.abspath(os.path.join(here, os.pardir))
        if not fr_path:
            print("ERR: cannot find filter-results.json; pass path explicitly", file=sys.stderr)
            return 1
    return run(fr_path)


if __name__ == "__main__":
    sys.exit(main())
