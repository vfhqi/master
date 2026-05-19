"""
=============================================================================
verify_s47_apply.py — Post-apply verification for S47 Stage criteria changes
=============================================================================
Project: SA - Master Dashboard
Session: S47 (18-May-2026)
Decisions: D-MD-V2-112, D-MD-V2-113, D-MD-V2-114, D-MD-V2-115

Checks:
1. All four S47 markers present in generate_master_data.py
2. filter-results.json parses and has expected stock count
3. Stage distribution: Probable/Plausible/Possible/None counts per Stage
4. S1+S4 collision count (target: single digits)
5. Stage 2 audit hook: Probable count as % of universe (flag if >20%)
6. Stage 3 prior_uptrend field present in data
7. Stage 4 info_stage_3_lookback field present in data
8. Stage 4 "Probable (Accelerating)" rating variant exists

Usage:
    python scripts/verify_s47_apply.py
=============================================================================
"""
import json
import os
import sys

def _find_repo_root():
    cur = os.path.abspath(os.path.dirname(__file__))
    cand = os.path.abspath(os.path.join(cur, os.pardir))
    if os.path.basename(cand) == "master-dashboard" and os.path.exists(os.path.join(cand, ".git")):
        return cand
    walk = cur
    for _ in range(6):
        if os.path.exists(os.path.join(walk, ".git")):
            return walk
        walk = os.path.abspath(os.path.join(walk, os.pardir))
    raise SystemExit("[ABORT] cannot locate repo root")


def main():
    repo = _find_repo_root()
    src_path = os.path.join(repo, "scripts", "generate_master_data.py")
    data_path = os.path.join(repo, "data", "filter-results.json")

    print("=" * 70)
    print("  S47 Post-Apply Verification")
    print("=" * 70)
    errors = []
    warnings = []

    # ── CHECK 1: Markers in source ──
    print("\n── CHECK 1: S47 markers in generate_master_data.py ──")
    with open(src_path, "r", encoding="utf-8") as f:
        src = f.read()

    markers = {
        "S1 (cushion removal)": "MD-V2-S47-S1-CUSHION-REMOVAL-MARKER",
        "S2 (new criteria)": "MD-V2-S47-S2-NEW-CRITERIA-MARKER",
        "S3 (prior uptrend)": "MD-V2-S47-S3-PRIOR-UPTREND-MARKER",
        "S4 (rewrite)": "MD-V2-S47-S4-REWRITE-MARKER",
    }
    for label, marker in markers.items():
        found = marker in src
        status = "OK" if found else "MISSING"
        print(f"  [{status}] {label}: {marker}")
        if not found:
            errors.append(f"Marker missing: {label}")

    # ── CHECK 2: filter-results.json parse ──
    print("\n── CHECK 2: filter-results.json parse ──")
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        stocks = data.get("stocks", data) if isinstance(data, dict) else data
        if isinstance(stocks, dict):
            stocks = list(stocks.values())
        n_stocks = len(stocks)
        print(f"  [OK] Parsed: {n_stocks} stocks")
        if n_stocks < 900:
            warnings.append(f"Stock count {n_stocks} is below expected ~946")
            print(f"  [WARN] Stock count below expected ~946")
    except (json.JSONDecodeError, IOError) as e:
        print(f"  [FAIL] Cannot parse: {e}")
        errors.append("filter-results.json parse failure")
        stocks = []

    if not stocks:
        print("\n[ABORT] No stock data — cannot run distribution checks.")
        print(f"  Errors: {len(errors)}, Warnings: {len(warnings)}")
        return 1

    # ── CHECK 3: Stage distribution ──
    print("\n── CHECK 3: Stage distribution ──")
    for stage_key, stage_label in [
        ("stage_1", "Stage 1"),
        ("stage_2", "Stage 2"),
        ("stage_3", "Stage 3"),
        ("stage_4", "Stage 4"),
    ]:
        dist = {}
        for s in stocks:
            md = s.get("md_v2", {})
            stage = md.get(stage_key, {})
            rating = stage.get("rating", "N/A")
            dist[rating] = dist.get(rating, 0) + 1

        print(f"\n  {stage_label} ({stage_key}):")
        for rating in sorted(dist.keys()):
            count = dist[rating]
            pct = (count / n_stocks) * 100
            print(f"    {rating:30s}: {count:4d} ({pct:5.1f}%)")

    # ── CHECK 4: S1+S4 collision ──
    print("\n── CHECK 4: Stage 1 + Stage 4 collision count ──")
    s1_probable = set()
    s4_probable = set()
    for s in stocks:
        md = s.get("md_v2", {})
        ticker = s.get("ticker", "?")
        s1r = md.get("stage_1", {}).get("rating", "None")
        s4r = md.get("stage_4", {}).get("rating", "None")
        if s1r in ("Probable Early", "Probable Late"):
            s1_probable.add(ticker)
        if s4r.startswith("Probable"):
            s4_probable.add(ticker)

    collisions = s1_probable & s4_probable
    print(f"  S1 Probable: {len(s1_probable)}")
    print(f"  S4 Probable: {len(s4_probable)}")
    print(f"  Collisions:  {len(collisions)}")
    if len(collisions) > 10:
        warnings.append(f"S1+S4 collisions = {len(collisions)} (target: single digits)")
        print(f"  [WARN] Collision count exceeds single digits")
    else:
        print(f"  [OK] Target met (single digits)")
    if collisions:
        for t in sorted(collisions)[:10]:
            print(f"    - {t}")
        if len(collisions) > 10:
            print(f"    ... and {len(collisions) - 10} more")

    # ── CHECK 5: Stage 2 audit hook (20% Probable threshold) ──
    print("\n── CHECK 5: Stage 2 Probable audit hook ──")
    s2_probable = sum(1 for s in stocks if s.get("md_v2", {}).get("stage_2", {}).get("rating") == "Probable")
    s2_pct = (s2_probable / n_stocks) * 100
    print(f"  Stage 2 Probable: {s2_probable} of {n_stocks} ({s2_pct:.1f}%)")
    if s2_pct > 20:
        warnings.append(f"Stage 2 Probable = {s2_pct:.1f}% — EXCEEDS 20% threshold. Tighten to 11/13.")
        print(f"  [ACTION REQUIRED] Probable > 20% of universe.")
        print(f"  → Tighten Probable threshold from 10/13 to 11/13 and re-run.")
    else:
        print(f"  [OK] Below 20% threshold — ladder holds.")

    # ── CHECK 6: Stage 3 prior_uptrend field ──
    print("\n── CHECK 6: Stage 3 prior_uptrend field ──")
    s3_has_field = sum(1 for s in stocks if "prior_uptrend" in s.get("md_v2", {}).get("stage_3", {}))
    print(f"  Stocks with prior_uptrend field: {s3_has_field} of {n_stocks}")
    if s3_has_field == n_stocks:
        print(f"  [OK] All stocks have the field")
    else:
        errors.append(f"prior_uptrend field missing on {n_stocks - s3_has_field} stocks")
        print(f"  [FAIL] Missing on {n_stocks - s3_has_field} stocks")

    # ── CHECK 7: Stage 4 info_stage_3_lookback field ──
    print("\n── CHECK 7: Stage 4 info_stage_3_lookback field ──")
    s4_has_lookback = sum(1 for s in stocks if "info_stage_3_lookback" in s.get("md_v2", {}).get("stage_4", {}))
    print(f"  Stocks with info_stage_3_lookback: {s4_has_lookback} of {n_stocks}")
    if s4_has_lookback == n_stocks:
        print(f"  [OK] All stocks have the field")
    else:
        errors.append(f"info_stage_3_lookback field missing on {n_stocks - s4_has_lookback} stocks")
        print(f"  [FAIL] Missing on {n_stocks - s4_has_lookback} stocks")

    # Check history depth
    depth_ok = sum(1 for s in stocks
                   if s.get("md_v2", {}).get("stage_4", {}).get("info_stage_3_lookback", {}).get("history_depth_ok"))
    if depth_ok == 0:
        print(f"  [INFO] No stocks have sufficient history depth yet (expected on first run)")
    else:
        print(f"  [INFO] {depth_ok} stocks have sufficient history depth")

    # ── CHECK 8: Stage 4 "Probable (Accelerating)" variant ──
    print("\n── CHECK 8: Stage 4 'Probable (Accelerating)' variant ──")
    s4_accel = sum(1 for s in stocks if s.get("md_v2", {}).get("stage_4", {}).get("rating") == "Probable (Accelerating)")
    print(f"  Stocks rated 'Probable (Accelerating)': {s4_accel}")
    if s4_accel > 0:
        print(f"  [OK] Rating variant present in data")
    else:
        print(f"  [INFO] No stocks currently rated Probable (Accelerating) — may be normal")

    # ── CHECK 9: Stage 2 total field ──
    print("\n── CHECK 9: Stage 2 total field (should be 13) ──")
    s2_total_13 = sum(1 for s in stocks if s.get("md_v2", {}).get("stage_2", {}).get("total") == 13)
    print(f"  Stocks with total=13: {s2_total_13} of {n_stocks}")
    if s2_total_13 == n_stocks:
        print(f"  [OK] All stocks show 13-test total")
    else:
        errors.append(f"Stage 2 total!=13 on {n_stocks - s2_total_13} stocks")
        print(f"  [FAIL] Mismatch on {n_stocks - s2_total_13} stocks")

    # ── SUMMARY ──
    print("\n" + "=" * 70)
    print(f"  ERRORS:   {len(errors)}")
    print(f"  WARNINGS: {len(warnings)}")
    for e in errors:
        print(f"    [ERROR] {e}")
    for w in warnings:
        print(f"    [WARN]  {w}")
    if not errors:
        print("  RESULT: PASS")
    else:
        print("  RESULT: FAIL")
    print("=" * 70)

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
