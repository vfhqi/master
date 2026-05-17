"""
S41 Verification Script -- Break-down MA hard gate (Diasorin fix) impact analysis

Two modes:

  preview  -- BEFORE applying the patcher: simulates what the hard gate WOULD
              do (reads current 2-test ratings, applies the simulated gate,
              reports before/after rating transitions + named demotions +
              a DIASORIN-specific check).

  verify   -- AFTER running refresh_all.py post-patcher: reads the LIVE ratings
              and the new ma_gate field stored alongside, confirms the gate is
              wired in and reports the new rating distribution.

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


def _find_repo():
    cur = os.path.abspath(os.path.dirname(__file__))
    cand = os.path.abspath(os.path.join(cur, os.pardir))
    if os.path.basename(cand) == REPO_ROOT_HINT and os.path.isdir(os.path.join(cand, "data")):
        return cand
    raise SystemExit("[ABORT] cannot locate repo root from " + cur)


BREAKDOWN_CONFIGS = [
    ("breakdown_50D",  "5D",  "50D"),
    ("breakdown_150D", "10D", "150D"),
    ("breakdown_200D", "20D", "200D"),
]


def _coerce_list(obj, label):
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict):
        for k in ("stocks", "prices", "data", "records", "items"):
            v = obj.get(k)
            if isinstance(v, list):
                return v
        vals = list(obj.values())
        if vals and isinstance(vals[0], dict):
            if "ticker" in vals[0]:
                return vals
            return [{**v, "ticker": k} for k, v in obj.items() if isinstance(v, dict)]
    raise SystemExit("[ABORT] cannot extract list from " + label + " (type=" + type(obj).__name__ + ")")


def preview(repo):
    with open(os.path.join(repo, "data", "prices.json"), encoding="utf-8") as fh:
        prices_raw = json.load(fh)
    with open(os.path.join(repo, "data", "filter-results.json"), encoding="utf-8") as fh:
        fr_raw = json.load(fh)
    prices = _coerce_list(prices_raw, "prices.json")
    stocks = _coerce_list(fr_raw, "filter-results.json")
    p_by = {p.get("ticker"): p for p in prices if isinstance(p, dict) and p.get("ticker")}
    print("[*] %d stocks in filter-results, %d in prices lookup.\n" % (len(stocks), len(p_by)))
    print('Simulating the HARD GATE: if MA-short <= MA-long, force rating to')
    print('"None" and qualifies=False. Tests stay /2; ladder semantics preserved.\n')
    for key, short, lng in BREAKDOWN_CONFIGS:
        before = Counter(); after = Counter(); demos = []
        for s in stocks:
            md = s.get("md_v2") or {}
            pi = md.get("post_indicators") or {}
            block = pi.get(key) or {}
            cur_rating = block.get("rating", "MISSING")
            before[cur_rating] += 1
            td = p_by.get(s["ticker"])
            mas = (td or {}).get("mas") or {}
            sm, lm = mas.get(short), mas.get(lng)
            gate = bool(sm is not None and lm is not None and sm > lm)
            new_rating = cur_rating if gate else "None"
            after[new_rating] += 1
            if cur_rating == "Probable" and new_rating == "None" and len(demos) < 12:
                demos.append((s["ticker"], cur_rating, new_rating, gate, sm, lm))
        print("=== %s (%s > %s hard gate) ===" % (key, short, lng))
        print("  %-10s %8s %8s %8s" % ("Tier", "BEFORE", "AFTER", "DELTA"))
        for tier in ["None", "Possible", "Plausible", "Probable"]:
            b, a = before.get(tier, 0), after.get(tier, 0)
            print("  %-10s %8d %8d %+d" % (tier, b, a, a - b))
        if demos:
            print("\n  Filtered-from-Probable examples (gate failed):")
            for tk, b, a, gp, sm, lm in demos:
                sm_s = ("%.4f" % sm) if sm is not None else "None"
                lm_s = ("%.4f" % lm) if lm is not None else "None"
                print("    %-14s %-10s -> %-10s  short_ma=%s  long_ma=%s" % (tk, b, a, sm_s, lm_s))
        print()

    print("\n=== DIASORIN check (any ticker containing 'DIA') ===")
    for s in stocks:
        if "DIA" not in s["ticker"].upper():
            continue
        md = s.get("md_v2") or {}
        pi = md.get("post_indicators") or {}
        td = p_by.get(s["ticker"]) or {}
        mas = td.get("mas") or {}
        print("\n  %s  price=%s" % (s["ticker"], td.get("price")))
        for key, short, lng in BREAKDOWN_CONFIGS:
            block = pi.get(key) or {}
            r = block.get("rating")
            sm, lm = mas.get(short), mas.get(lng)
            gate = bool(sm is not None and lm is not None and sm > lm)
            new_rating = r if gate else "None"
            print("    %-18s BEFORE=%r ma%s=%s ma%s=%s gate=%s AFTER=%r" % (
                key, r, short, sm, lng, lm, gate, new_rating))
    return 0


def verify(repo):
    """AFTER refresh_all: confirm hard gate is live. Reads ma_gate field on
    each breakdown block (added by the patcher) and reports gate pass-rate +
    rating distribution + Probable counts vs the original/predicted."""
    with open(os.path.join(repo, "data", "filter-results.json"), encoding="utf-8") as fh:
        fr_raw = json.load(fh)
    stocks = _coerce_list(fr_raw, "filter-results.json")
    print("[*] %d stocks loaded.\n" % len(stocks))

    # Original Probable counts (from S41 preview run) for the diff column
    ORIG_PROBABLE = {"breakdown_50D": 111, "breakdown_150D": 65, "breakdown_200D": 50}

    for key, short, lng in BREAKDOWN_CONFIGS:
        rating_dist = Counter()
        gate_present = 0
        gate_pass = 0
        gate_total = 0
        for s in stocks:
            md = s.get("md_v2") or {}
            pi = md.get("post_indicators") or {}
            block = pi.get(key) or {}
            rating_dist[block.get("rating", "MISSING")] += 1
            ma_gate = block.get("ma_gate")
            if isinstance(ma_gate, dict):
                gate_present += 1
                gate_total += 1
                if ma_gate.get("passes"):
                    gate_pass += 1
        print("=== %s ===" % key)
        print("  rating distribution: %s" % dict(rating_dist))
        live_prob = rating_dist.get("Probable", 0)
        orig_prob = ORIG_PROBABLE.get(key, "?")
        if isinstance(orig_prob, int):
            print("  Probable: %d (was %d -> demoted %d)" % (live_prob, orig_prob, orig_prob - live_prob))
        if gate_present == 0:
            print("  ma_gate field MISSING from data -- patcher not applied OR refresh hasn't picked it up.")
        else:
            print("  ma_gate present on %d/%d stocks; pass rate %d/%d = %.1f%%" % (
                gate_present, len(stocks), gate_pass, gate_total,
                100.0 * gate_pass / gate_total if gate_total else 0.0))
        # DIASORIN check
        for s in stocks:
            if s["ticker"] in ("DIA-IT",):
                block = s.get("md_v2", {}).get("post_indicators", {}).get(key, {})
                print("  DIA-IT %s: rating=%r ma_gate=%s" % (
                    key, block.get("rating"), block.get("ma_gate")))
        print()
    return 0


def main(argv):
    if len(argv) != 1 or argv[0] not in ("preview", "verify"):
        print("Usage: python scripts/verify_s41_breakdown_t3_gate.py {preview|verify}")
        return 1
    repo = _find_repo()
    return preview(repo) if argv[0] == "preview" else verify(repo)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
