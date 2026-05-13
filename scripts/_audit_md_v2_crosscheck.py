"""
MD V2 Cross-Check Audit Harness — Windows-side
Reads filter-results.json (full file), computes:
  1. NxN co-occurrence matrix across all 18 criteria (4 stages + 7 indicators + 4 setups + 3 tests)
  2. List of 3-tuple combinations sorted by stock count
  3. List of 4-tuple combinations sorted by stock count

Output: data/_md_v2_audit_crosscheck.json
"""
import json
import sys
import itertools
from pathlib import Path
from collections import Counter

SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_PATH = SCRIPT_DIR.parent / "data" / "filter-results.json"
OUT_PATH = SCRIPT_DIR.parent / "data" / "_md_v2_audit_crosscheck.json"

# Threshold for "stock triggers criterion"
STAGE_THRESHOLDS = {
    "stage_1": ("Plausible", "Probable Early", "Probable Late"),
    "stage_2": ("Plausible", "Probable"),
    "stage_3": ("Plausible Invalidation", "Probable Invalidation"),
    "stage_4": ("Plausible", "Probable"),
}

CRITERIA_GROUPS = {
    "stages": ["stage_1", "stage_2", "stage_3", "stage_4"],
    "indicators": ["pullback_to_retest", "basing_below_high", "collapsing", "breakout",
                   "advancing", "breakdown_50D", "breakdown_150D", "breakdown_200D"],
    "setups": ["probing_bet", "vcp_after_s1_plateau", "utr_after_s2_pullback", "vcp_after_s2_base"],
    "tests": ["test_probing_bet", "test_vcp", "test_uptrend_retest"],
}
ALL_CRITERIA = (
    CRITERIA_GROUPS["stages"] +
    CRITERIA_GROUPS["indicators"] +
    CRITERIA_GROUPS["setups"] +
    CRITERIA_GROUPS["tests"]
)


def stock_triggers(md, criterion):
    """Return True if stock's md_v2 block triggers the given criterion."""
    if criterion in STAGE_THRESHOLDS:
        return md.get(criterion, {}).get("rating") in STAGE_THRESHOLDS[criterion]
    if criterion in CRITERIA_GROUPS["indicators"]:
        return bool(md.get("indicators", {}).get(criterion))
    if criterion in CRITERIA_GROUPS["setups"]:
        return bool(md.get("setups", {}).get(criterion))
    if criterion == "test_probing_bet":
        return bool(md.get("tests", {}).get("probing_bet", {}).get("qualifies"))
    if criterion == "test_vcp":
        return bool(md.get("tests", {}).get("vcp", {}).get("qualifies"))
    if criterion == "test_uptrend_retest":
        return bool(md.get("tests", {}).get("uptrend_retest", {}).get("qualifies"))
    return False


def main():
    if not DATA_PATH.exists():
        print(f"ERROR: {DATA_PATH} not found")
        sys.exit(1)
    print(f"Reading {DATA_PATH} ({DATA_PATH.stat().st_size:,} bytes)...")
    with open(DATA_PATH, "rb") as f:
        data = json.loads(f.read())
    stocks = data.get("stocks", [])
    print(f"  Loaded {len(stocks)} stocks")

    # Per-stock trigger flags: dict[ticker][criterion] = bool
    flags = {}
    for s in stocks:
        md = s.get("md_v2")
        if not md or "_error" in md:
            continue
        f = {c: stock_triggers(md, c) for c in ALL_CRITERIA}
        flags[s["ticker"]] = f

    total = len(flags)
    print(f"  Analyzing {total} stocks across {len(ALL_CRITERIA)} criteria")

    # Singleton counts
    singletons = {c: sum(1 for t in flags.values() if t[c]) for c in ALL_CRITERIA}
    print("\nSingleton trigger counts:")
    for grp_name, grp_list in CRITERIA_GROUPS.items():
        print(f"  {grp_name}:")
        for c in grp_list:
            print(f"    {c:30s}: {singletons[c]} / {total}")

    # 1. NxN matrix
    matrix = {}
    for a in ALL_CRITERIA:
        matrix[a] = {}
        for b in ALL_CRITERIA:
            if a == b:
                matrix[a][b] = singletons[a]
            else:
                matrix[a][b] = sum(1 for t in flags.values() if t[a] and t[b])

    # 2. All 3-tuple combos with count >= 5
    triples = Counter()
    for ticker, f in flags.items():
        active = [c for c in ALL_CRITERIA if f[c]]
        for combo in itertools.combinations(active, 3):
            triples[combo] += 1
    triples_sorted = sorted(triples.items(), key=lambda x: -x[1])
    triples_significant = [(list(k), v) for k, v in triples_sorted if v >= 5]

    # 3. All 4-tuple combos with count >= 3
    quads = Counter()
    for ticker, f in flags.items():
        active = [c for c in ALL_CRITERIA if f[c]]
        for combo in itertools.combinations(active, 4):
            quads[combo] += 1
    quads_sorted = sorted(quads.items(), key=lambda x: -x[1])
    quads_significant = [(list(k), v) for k, v in quads_sorted if v >= 3]

    # 4. Conflict pairs: stocks triggering BOTH a "bullish" criterion AND a "bearish" criterion
    BULLISH = ["stage_1", "stage_2", "pullback_to_retest", "basing_below_high",
               "breakout", "advancing",
               "probing_bet", "vcp_after_s1_plateau", "utr_after_s2_pullback", "vcp_after_s2_base",
               "test_probing_bet", "test_vcp", "test_uptrend_retest"]
    BEARISH = ["stage_3", "stage_4", "collapsing",
               "breakdown_50D", "breakdown_150D", "breakdown_200D"]
    conflicts = []
    for bull in BULLISH:
        for bear in BEARISH:
            count = matrix[bull][bear]
            if count > 0:
                # Get example tickers
                samples = sorted([t for t in flags if flags[t][bull] and flags[t][bear]])[:5]
                conflicts.append({
                    "bullish": bull,
                    "bearish": bear,
                    "count": count,
                    "sample_tickers": samples,
                })
    conflicts.sort(key=lambda x: -x["count"])

    out = {
        "generated": data.get("_meta", {}).get("generated"),
        "total_stocks": total,
        "criteria": ALL_CRITERIA,
        "singletons": singletons,
        "matrix": matrix,
        "triple_combos_top50": triples_significant[:50],
        "quad_combos_top50": quads_significant[:50],
        "conflict_pairs": conflicts[:30],
        "_note_triple_threshold": "Triples shown if ≥5 stocks",
        "_note_quad_threshold": "Quads shown if ≥3 stocks",
    }

    with open(OUT_PATH, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nAudit written: {OUT_PATH} ({OUT_PATH.stat().st_size:,} bytes)")

    # Headline conflicts to terminal
    print("\n=== Top 10 bull-vs-bear conflict pairs ===")
    for conf in conflicts[:10]:
        print(f"  {conf['bullish']:25s} + {conf['bearish']:25s}: {conf['count']} stocks (e.g. {', '.join(conf['sample_tickers'])})")
    print(f"\nTriples ≥5 stocks: {len(triples_significant)}")
    print(f"Quads ≥3 stocks: {len(quads_significant)}")
    print("\nTop 5 triple combos:")
    for combo, count in triples_significant[:5]:
        print(f"  {count}: {' + '.join(combo)}")

if __name__ == "__main__":
    main()
