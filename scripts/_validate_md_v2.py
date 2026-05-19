"""
MD V2 Validation Harness — Windows-side
Reads filter-results.json (full file, ~14.7MB), runs validation summary,
emits a compact ~50-150KB summary file Cowork can ingest.

Output: data/_md_v2_validation_summary.json

Run from PowerShell:
  cd C:\\Users\\richb\\Documents\\COWORK\\master-dashboard
  python scripts\\_validate_md_v2.py
"""
import json
import sys
from pathlib import Path
from collections import Counter

SCRIPT_DIR = Path(__file__).parent.resolve()
DATA_PATH = SCRIPT_DIR.parent / "data" / "filter-results.json"
OUT_PATH = SCRIPT_DIR.parent / "data" / "_md_v2_validation_summary.json"

def main():
    if not DATA_PATH.exists():
        print(f"ERROR: {DATA_PATH} not found")
        sys.exit(1)
    print(f"Reading {DATA_PATH} ({DATA_PATH.stat().st_size:,} bytes)...")
    with open(DATA_PATH, "rb") as f:
        data = json.loads(f.read())
    stocks = data.get("stocks", [])
    print(f"  Loaded {len(stocks)} stocks")

    # Distribution counters
    s1_dist = Counter()
    s2_dist = Counter()
    s3_dist = Counter()
    s4_dist = Counter()
    ind_dist = {k: 0 for k in ["pullback_to_retest", "basing_below_high", "collapsing",
                                "breakout", "advancing", "breakdown_50D", "breakdown_150D", "breakdown_200D"]}
    setup_dist = {k: 0 for k in ["probing_bet", "vcp_after_s1_plateau", "utr_after_s2_pullback", "vcp_after_s2_base"]}
    test_qualifies = {"probing_bet": 0, "vcp": 0, "uptrend_retest": 0}
    vcp_stage_dist = Counter()

    # Per-stock detail for the 100-stock cohort
    cohort = []
    n_with_md_v2 = 0
    n_missing_md_v2 = 0
    missing_sample = []

    for s in stocks:
        md = s.get("md_v2")
        if not md or "_error" in md:
            n_missing_md_v2 += 1
            if len(missing_sample) < 5:
                missing_sample.append({"ticker": s["ticker"], "error": md.get("_error") if md else "no md_v2 key"})
            continue
        n_with_md_v2 += 1
        s1_dist[md["stage_1"]["rating"]] += 1
        s2_dist[md["stage_2"]["rating"]] += 1
        s3_dist[md["stage_3"]["rating"]] += 1
        s4_dist[md["stage_4"]["rating"]] += 1
        for k in ind_dist:
            if md["indicators"].get(k):
                ind_dist[k] += 1
        for k in setup_dist:
            if md["setups"].get(k):
                setup_dist[k] += 1
        for k in test_qualifies:
            if md["tests"][k]["qualifies"]:
                test_qualifies[k] += 1
        vcp_stage_dist[md["tests"]["vcp"]["stage"]] += 1

    # Build 100-stock cohort: 9 live positions + spread across stages
    LIVE_POSITIONS = ["AZA-SE", "BYLOT-GR", "CARL.B-DK", "CVSG-GB", "ENAV-IT", "FEVR-GB",
                      "HTWS-GB", "RYA-IE", "THEON-NL"]
    by_ticker = {s["ticker"]: s for s in stocks if s.get("md_v2") and "_error" not in s["md_v2"]}

    cohort_tickers = set()
    for t in LIVE_POSITIONS:
        if t in by_ticker:
            cohort_tickers.add(t)

    # Pipeline tickers (some prominent)
    PIPELINE_TICKERS = ["MTU-DE", "DCC-GB", "CRBN-NL", "FLTR-GB", "DKSH-CH", "XVIVO-SE",
                       "PRY-IT", "NKT-DK", "NEX-FR", "VOD-GB", "NSIS-DK", "HTRO-SE",
                       "ABB-SE", "AENA-ES", "EKTA-SE", "BAS-DE", "AHT-GB"]
    for t in PIPELINE_TICKERS:
        if t in by_ticker:
            cohort_tickers.add(t)

    # Top 25 by S2 Probable (strong uptrend) — TM_A signal
    s2_probable_tickers = [t for t, s in by_ticker.items() if s["md_v2"]["stage_2"]["rating"] == "Probable"]
    s2_probable_tickers.sort()
    for t in s2_probable_tickers[:20]:
        cohort_tickers.add(t)

    # Top 20 with S3 Probable Invalidation
    s3_probable_tickers = [t for t, s in by_ticker.items() if s["md_v2"]["stage_3"]["rating"] == "Probable Invalidation"]
    s3_probable_tickers.sort()
    for t in s3_probable_tickers[:15]:
        cohort_tickers.add(t)

    # Top 20 with S4 Probable
    s4_probable_tickers = [t for t, s in by_ticker.items() if s["md_v2"]["stage_4"]["rating"] == "Probable"]
    s4_probable_tickers.sort()
    for t in s4_probable_tickers[:15]:
        cohort_tickers.add(t)

    # Top 10 with S1 Probable Late
    s1_late_tickers = [t for t, s in by_ticker.items() if s["md_v2"]["stage_1"]["rating"] == "Probable Late"]
    s1_late_tickers.sort()
    for t in s1_late_tickers[:10]:
        cohort_tickers.add(t)

    # Top 10 with setups firing
    setup_tickers = [t for t, s in by_ticker.items() if any(s["md_v2"]["setups"].values())]
    setup_tickers.sort()
    for t in setup_tickers[:10]:
        cohort_tickers.add(t)

    # Build per-stock cohort records
    for t in sorted(cohort_tickers):
        if t not in by_ticker:
            continue
        s = by_ticker[t]
        md = s["md_v2"]
        rec = {
            "ticker": t,
            "s1": {"count": md["stage_1"]["count"], "rating": md["stage_1"]["rating"]},
            "s2": {"count": md["stage_2"]["count"], "rating": md["stage_2"]["rating"]},
            "s3": {"count": md["stage_3"]["count"], "rating": md["stage_3"]["rating"]},
            "s4": {"count": md["stage_4"]["count"], "rating": md["stage_4"]["rating"]},
            "vcp_stage": md["tests"]["vcp"]["stage"],
            "vcp_higher_lows": md["tests"]["vcp"]["higher_lows_count"],
            "vcp_qualifies": md["tests"]["vcp"]["qualifies"],
            "active_indicators": [k for k, v in md["indicators"].items() if v],
            "active_setups": [k for k, v in md["setups"].items() if v],
            "is_live_position": t in LIVE_POSITIONS,
            "is_pipeline": t in PIPELINE_TICKERS,
        }
        cohort.append(rec)

    summary = {
        "generated": data.get("_meta", {}).get("generated"),
        "total_stocks": len(stocks),
        "n_with_md_v2": n_with_md_v2,
        "n_missing_md_v2": n_missing_md_v2,
        "missing_sample": missing_sample,
        "distributions": {
            "stage_1": dict(s1_dist),
            "stage_2": dict(s2_dist),
            "stage_3": dict(s3_dist),
            "stage_4": dict(s4_dist),
            "indicators": ind_dist,
            "setups": setup_dist,
            "tests_qualifying": test_qualifies,
            "vcp_stage": dict(vcp_stage_dist),
        },
        "cohort": cohort,
        "cohort_size": len(cohort),
    }

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_PATH, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nValidation summary written: {OUT_PATH} ({OUT_PATH.stat().st_size:,} bytes)")
    print(f"  Stocks with md_v2: {n_with_md_v2} / {len(stocks)}")
    print(f"  Cohort size: {len(cohort)}")
    print(f"  Stage 1 ratings: {dict(s1_dist)}")
    print(f"  Stage 2 ratings: {dict(s2_dist)}")
    print(f"  Stage 3 ratings: {dict(s3_dist)}")
    print(f"  Stage 4 ratings: {dict(s4_dist)}")
    print(f"  Indicators firing: {ind_dist}")
    print(f"  Setups firing: {setup_dist}")
    print(f"  VCP stages: {dict(vcp_stage_dist)}")

if __name__ == "__main__":
    main()
