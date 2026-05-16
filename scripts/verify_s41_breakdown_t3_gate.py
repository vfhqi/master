"""
S41 Verification Script — Break-down MA T3 gate impact analysis
================================================================
Runs OFFLINE on the current filter-results.json + prices.json. Two modes:

  preview  -- before applying the patcher: simulates what the T3 gate WOULD do
              (reads current 2-test ratings, applies T3 to each, reports the
              before/after rating transitions + named examples of demotions).

  verify   -- after running `refresh_all.py` post-patcher: reads the live 3-test
              ratings + checks that DIASORIN no longer rates Probable on 200D
              (or equivalent — script greps for any ticker matching 'DIA' as
              the canonical false-positive). Reports the new distribution.

USAGE
-----
    python scripts/verify_s41_breakdown_t3_gate.py preview
    python scripts/verify_s41_breakdown_t3_gate.py verify
"""
from __future__ import annotations
import json
import os
import sys
from collections import Counter


REPO_ROOT_HINT = "master-dashboard"


def _find_repo() -> str:
    cur = os.path.abspath(os.path.dirname(__file__))
    cand = os.path.abspath(os.path.join(cur, os.pardir))
    if os.path.basename(cand) == REPO_ROOT_HINT and os.path.isdir(os.path.join(cand, "data")):
        return cand
    raise SystemExit(f"[ABORT] cannot locate repo root from {cur}")


BREAKDOWN_CONFIGS = [
    ("breakdown_50D",  "5D",  "50D"),
    ("breakdown_150D", "10D", "150D"),
    ("breakdown_200D", "20D", "200D"),
]


def _rating_from_count(count: int, total: int) -> str:
    if count <= 0:
        return "None"
    if count >= total:
        return "Probable"
    if count / total >= (2.0 / 3.0):
        return "Plausible"
    return "Possible"


def preview(repo: str) -> int:
    """Simulate T3 gate against current 2-test ratings."""
    with open(os.path.join(repo, "data", "prices.json"), encoding="utf-8") as fh:
        prices = json.load(fh)
    with open(os.path.join(repo, "data", "filter-results.json"), encoding="utf-8") as fh:
        fr = json.load(fh)
    stocks = fr["stocks"]
    p_by = {p["ticker"]: p for p in prices}
    print(f"[*] {len(stocks)} stocks loaded.\n")

    for key, short, long in BREAKDOWN_CONFIGS:
        before = Counter()
        after = Counter()
        moves = Counter()
        named_demotions = []
        for s in stocks:
            md = s.get("md_v2") or {}
            pi = md.get("post_indicators") or {}
            block = pi.get(key) or {}
            cur_rating = block.get("rating", "MISSING")
            cur_count = block.get("count", 0)
            before[cur_rating] += 1
            td = p_by.get(s["ticker"])
            mas = (td or {}).get("mas") or {}
            sm, lm = mas.get(short), mas.get(long)
            t3 = bool(sm is not None and lm is not None and sm > lm)
            new_count = cur_count + (1 if t3 else 0)
            new_rating = _rating_from_count(new_count, 3)
            after[new_rating] += 1
            moves[(cur_rating, new_rating)] += 1
            if cur_rating == "Probable" and new_rating != "Probable" and len(named_demotions) < 12:
                named_demotions.append((s["ticker"], cur_rating, new_rating, t3, sm, lm))

        print(f"=== {key} ({short} vs {long} T3 gate) ===")
        print(f"  {'Tier':<10} {'BEFORE':>8} {'AFTER':>8} {'DELTA':>8}")
        for tier in ["None", "Possible", "Plausible", "Probable"]:
            b, a = before.get(tier, 0), after.get(tier, 0)
            d = a - b
            print(f"  {tier:<10} {b:>8} {a:>8} {d:+d}")
        if named_demotions:
            print(f"\n  Demoted-from-Probable examples (T3 failed):")
            for tk, b, a, t3, sm, lm in named_demotions:
                sm_s = f"{sm:.4f}" if sm is not None else "None"
                lm_s = f"{lm:.4f}" if lm is not None else "None"
                print(f"    {tk:<14} {b:<10} -> {a:<10}  short_ma={sm_s}  long_ma={lm_s}")
        print()

    print("\n=== DIASORIN check (any ticker containing 'DIA') ===")
    for s in stocks:
        if "DIA" not in s["ticker"].upper():
            continue
        md = s.get("md_v2") or {}
        pi = md.get("post_indicators") or {}
        td = p_by.get(s["ticker"]) or {}
        mas = td.get("mas") or {}
        print(f"\n  {s['ticker']}  price={td.get('price')}")
        for key, short, long in BREAKDOWN_CONFIGS:
            block = pi.get(key) or {}
            r = block.get("rating")
            cur_count = block.get("count", 0)
            sm, lm = mas.get(short), mas.get(long)
            t3 = bool(sm is not None and lm is not None and sm > lm)
            new_count = cur_count + (1 if t3 else 0)
            new_rating = _rating_from_count(new_count, 3)
            sm_s = f"{sm:.4f}" if sm is not None else "None"
            lm_s = f"{lm:.4f}" if lm is not None else "None"
            print(f"    {key:<18} BEFORE={r!r:<12} ma{short}={sm_s}  ma{long}={lm_s}  T3={t3}  AFTER={new_rating!r}")
    return 0


def verify(repo: str) -> int:
    """Read live ratings AFTER refresh_all.py to confirm T3 is wired in."""
    with open(os.path.join(repo, "data", "filter-results.json"), encoding="utf-8") as fh:
        fr = json.load(fh)
    stocks = fr["stocks"]
    print(f"[*] {len(stocks)} stocks loaded.\n")

    for key, short, long in BREAKDOWN_CONFIGS:
        total_check = Counter()
        rating_dist = Counter()
        t3_pass_count = 0
        t3_total = 0
        for s in stocks:
            md = s.get("md_v2") or {}
            pi = md.get("post_indicators") or {}
            block = pi.get(key) or {}
            tot = block.get("total", -1)
            total_check[tot] += 1
            rating_dist[block.get("rating", "MISSING")] += 1
            t3_key = f"t3_ma{short.rstrip('D')}_above_ma{long.rstrip('D')}"
            tests = block.get("tests") or {}
            if t3_key in tests:
                t3_total += 1
                if tests[t3_key]:
                    t3_pass_count += 1
        print(f"=== {key} ===")
        print(f"  totals (expect all 3): {dict(total_check)}")
        print(f"  rating distribution:   {dict(rating_dist)}")
        if t3_total:
            print(f"  T3 test ({short} > {long}) pass rate: {t3_pass_count}/{t3_total} = {100*t3_pass_count/t3_total:.1f}%")
        else:
            print(f"  T3 test MISSING from data -- patcher not applied or refresh not run.")
        print()
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 1 or argv[0] not in ("preview", "verify"):
        print("Usage: python scripts/verify_s41_breakdown_t3_gate.py {preview|verify}")
        return 1
    repo = _find_repo()
    return preview(repo) if argv[0] == "preview" else verify(repo)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
