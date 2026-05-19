#!/usr/bin/env python3
"""
stage_classifier.py
────────────────────
Per-stock 4-stage classifier (Weinstein-style).

Standalone utility importable by Master Dashboard build pipeline (future
Stages tab), the Universe & Portfolio Reports project (Sector/Industry +
Portfolio Technical Change Reports), or any downstream consumer needing
per-stock stage assignment.

DEFINITIONS
The 150D MA (~30-week MA) is the spine. Stage = (price vs MA, MA slope
over trailing 22 trading days, recent 22D price action for disambiguation).

  Stage 1 (Basing):     150D MA flat AND price near MA AND prior 60D was Stage 4
                        OR below flat MA with up rebound, OR below rising MA with
                        sharp recent decline.
  Stage 2 (Markup):     Price > 150D MA AND 150D MA rising (>+FLAT_PCT over 22D)
                        OR below rising MA without sharp decline = S2 pullback.
  Stage 3 (Topping):    150D MA flat AND price near MA AND prior 60D was Stage 2
                        OR above flat MA with neutral/negative recent action,
                        OR above falling MA.
  Stage 4 (Declining):  Price < 150D MA AND 150D MA falling (<-FLAT_PCT over 22D)
                        OR below flat MA with sharp recent decline.

RELATIONSHIP TO MM99 GROUPS
MM99 LT/MT/ST tests check price-vs-MA only (not slope). A stock can pass
MM99 LT+MT+ST and be in early Stage 3 because Stage 3 is defined by slope
flattening, not price-vs-MA alone. The Stages bucket adds the slope axis.

SENSITIVITY (measured 12-May-26 across 973 ticker universe):
  FLAT_PCT is the LOAD-BEARING threshold. From ±1% to ±5% shifts Stage 2
  from 410 → 124 stocks (3.3× swing). ±2% is the chosen default but is NOT
  robust. Distribution:
      FLAT_PCT ±1.0%: S1=164 S2=410 S3=150 S4=243
      FLAT_PCT ±1.5%: S1=187 S2=367 S3=198 S4=215
      FLAT_PCT ±2.0%: S1=217 S2=325 S3=238 S4=187  ← default
      FLAT_PCT ±2.5%: S1=255 S2=279 S3=285 S4=148
      FLAT_PCT ±3.0%: S1=285 S2=237 S3=321 S4=124
      FLAT_PCT ±5.0%: S1=368 S2=124 S3=418 S4=57
  NEAR_MA_PCT is benign (±5% to ±20% shifts S1/S3 by only ~25 stocks).

VERSION HISTORY
  v1.0  12-May-26  Initial release
  v1.1  12-May-26  Edge-case refinement using recent 22D price action:
                   - "below rising MA" defaults to S2 pullback (not S1 basing)
                     unless recent 22D decline > 5%
                   - flat-MA disambiguation now uses recent 22D price action
                     (above flat MA + recent decline = S3 confirmed; above
                      flat MA + recent rally = late S2 with lagging slope; etc.)
                   Originating hand-validation showed AZN-GB, NEX-FR, LR-FR,
                   DCC-GB, DKSH-CH, HNR1-DE, SREN-CH all misclassified by v1.0.

Run from command line:
  python stage_classifier.py --out <path>      # classify all charts
  python stage_classifier.py --test            # run self-tests
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional


__version__ = "1.1.0"

# Tunable thresholds — exposed as module constants for easy revision
FLAT_PCT = 0.02
NEAR_MA_PCT = 0.10
HISTORY_LOOKBACK_DAYS = 60
MIN_HISTORY_DAYS = 172


@dataclass
class StageResult:
    stage: Optional[int]
    label: str
    confidence: str
    inputs: dict


STAGE_LABELS = {
    1: "Stage 1 — Basing",
    2: "Stage 2 — Markup",
    3: "Stage 3 — Topping",
    4: "Stage 4 — Declining",
    None: "Unclassified",
}


def _label(stage):
    return STAGE_LABELS[stage]


def _make_result(stage, conf, inputs, extra=None):
    out_inputs = dict(inputs)
    if extra:
        out_inputs.update(extra)
    return StageResult(stage=stage, label=_label(stage), confidence=conf, inputs=out_inputs)


def classify_from_ohlc(closes, dates=None):
    """Classify stage from a chronological list of closing prices (oldest first)."""
    n = len(closes)
    if n < MIN_HISTORY_DAYS:
        return StageResult(
            stage=None, label=_label(None), confidence="low",
            inputs={"reason": f"insufficient history: {n} < {MIN_HISTORY_DAYS}"},
        )

    def ma150(i):
        if i + 1 < 150:
            return None
        window = closes[i - 149:i + 1]
        if any(c is None for c in window):
            return None
        return sum(window) / 150

    def ma150_slope_22d(i):
        cur = ma150(i)
        prior = ma150(i - 22)
        if cur is None or prior is None or prior == 0:
            return None
        return (cur - prior) / prior

    last_i = n - 1
    current_price = closes[last_i]
    current_ma = ma150(last_i)
    current_slope = ma150_slope_22d(last_i)

    if current_price is None or current_ma is None or current_slope is None:
        return StageResult(
            stage=None, label=_label(None), confidence="low",
            inputs={"reason": "missing current MA/slope"},
        )

    above_ma = current_price > current_ma
    pct_from_ma = (current_price - current_ma) / current_ma
    near_ma = abs(pct_from_ma) <= NEAR_MA_PCT
    ma_rising = current_slope > FLAT_PCT
    ma_falling = current_slope < -FLAT_PCT
    ma_flat = not ma_rising and not ma_falling

    inputs = {
        "current_price": round(current_price, 4),
        "current_150d_ma": round(current_ma, 4),
        "pct_from_ma": round(pct_from_ma, 4),
        "ma_slope_22d_pct": round(current_slope, 4),
        "above_ma": above_ma,
        "near_ma": near_ma,
        "ma_rising": ma_rising,
        "ma_falling": ma_falling,
        "ma_flat": ma_flat,
    }

    # Recent 22D price action (used for v1.1 disambiguation)
    if last_i >= 22:
        prior_close = closes[last_i - 22]
        if prior_close is not None and prior_close != 0:
            recent_22d = (current_price - prior_close) / prior_close
        else:
            recent_22d = None
    else:
        recent_22d = None

    # Clear-cut Stage 2: price above rising MA
    if above_ma and ma_rising:
        return _make_result(2, "high", inputs)

    # Clear-cut Stage 4: price below falling MA
    if (not above_ma) and ma_falling:
        return _make_result(4, "high", inputs)

    # Transitional zone: flat MA + price near MA → look back for prior regime
    if ma_flat and near_ma:
        lookback_i = last_i - HISTORY_LOOKBACK_DAYS
        prior_ma = ma150(lookback_i)
        prior_slope = ma150_slope_22d(lookback_i)
        if prior_ma is None or prior_slope is None:
            stage = 3 if above_ma else 1
            return _make_result(stage, "low", inputs, {"disambiguation": "insufficient prior history"})

        prior_price = closes[lookback_i]
        prior_above = prior_price > prior_ma
        prior_rising = prior_slope > FLAT_PCT
        prior_falling = prior_slope < -FLAT_PCT

        if prior_above and prior_rising:
            return _make_result(3, "high", inputs, {"prior_regime": "Stage 2"})
        if (not prior_above) and prior_falling:
            return _make_result(1, "high", inputs, {"prior_regime": "Stage 4"})

        stage = 3 if above_ma else 1
        return _make_result(stage, "medium", inputs, {"disambiguation": "ambiguous prior regime"})

    # v1.1 edge cases: use recent 22D price action

    # Above a flat MA
    if above_ma and ma_flat:
        if recent_22d is not None and recent_22d < -0.03:
            return _make_result(3, "medium", inputs, {"recent_22d_pct": round(recent_22d, 4), "note": "above flat MA, recent decline — S3 confirmed"})
        if recent_22d is not None and recent_22d > 0.03:
            return _make_result(2, "low", inputs, {"recent_22d_pct": round(recent_22d, 4), "note": "above flat MA, recent advance — late S2 (slope lagging)"})
        return _make_result(3, "low", inputs, {"note": "above flat MA, neutral recent action"})

    # Below a flat MA
    if (not above_ma) and ma_flat:
        if recent_22d is not None and recent_22d < -0.03:
            return _make_result(4, "medium", inputs, {"recent_22d_pct": round(recent_22d, 4), "note": "below flat MA, recent decline — S4 confirmed"})
        if recent_22d is not None and recent_22d > 0.03:
            return _make_result(1, "medium", inputs, {"recent_22d_pct": round(recent_22d, 4), "note": "below flat MA, recent advance — S1 forming"})
        return _make_result(1, "low", inputs, {"note": "below flat MA, neutral recent action"})

    # Above a falling MA — S3 rolling over
    if above_ma and ma_falling:
        return _make_result(3, "medium", inputs, {"note": "above falling MA — early S3"})

    # Below a rising MA — v1.1 fix: this is usually S2 pullback, not S1 basing
    if (not above_ma) and ma_rising:
        if recent_22d is not None and recent_22d < -0.05:
            return _make_result(1, "medium", inputs, {"recent_22d_pct": round(recent_22d, 4), "note": "below rising MA, sharp recent decline — S1 basing"})
        recent_str = round(recent_22d, 4) if recent_22d is not None else None
        return _make_result(2, "medium", inputs, {"recent_22d_pct": recent_str, "note": "below rising MA — S2 pullback (testing trend)"})

    return _make_result(None, "low", inputs, {"reason": "unreachable"})


def classify_many(ticker_closes_map):
    """Batch classify many tickers. Input is {ticker: [closes]}."""
    return {t: classify_from_ohlc(c) for t, c in ticker_closes_map.items()}


# ──────────────────────────────────────────────────────────────────────
# Self-tests
# ──────────────────────────────────────────────────────────────────────

def _self_test():
    failures = []
    passed = 0
    total = 0

    def check(name, expected_stage, result, expected_conf=None):
        nonlocal passed, total
        total += 1
        ok = result.stage == expected_stage
        if expected_conf:
            ok = ok and result.confidence == expected_conf
        if ok:
            passed += 1
        else:
            failures.append(
                f"  FAIL {name}: expected stage={expected_stage}"
                f"{' conf=' + expected_conf if expected_conf else ''}, "
                f"got stage={result.stage} conf={result.confidence}"
            )

    # 1: Clean Stage 2
    closes = [100 * (1.005 ** i) for i in range(200)]
    check("clean_S2_uptrend", 2, classify_from_ohlc(closes), expected_conf="high")

    # 2: Clean Stage 4
    closes = [100 * (0.995 ** i) for i in range(200)]
    check("clean_S4_downtrend", 4, classify_from_ohlc(closes), expected_conf="high")

    # 3: Insufficient history
    check("insufficient_history", None, classify_from_ohlc([100.0] * 50))

    # 4: Empty input
    check("empty_input", None, classify_from_ohlc([]))

    # 5: v1.1 fix — Stage 2 pullback (rising trend, mild recent pullback)
    closes_up = [100 * (1.004 ** i) for i in range(190)]
    pull_start = closes_up[-1]
    closes_pull = [pull_start * (1 - 0.005 * (i + 1)) for i in range(10)]
    closes = closes_up + closes_pull
    res = classify_from_ohlc(closes)
    total += 1
    if res.stage == 2:
        passed += 1
    else:
        failures.append(f"  FAIL v1.1_S2_pullback: expected S2, got {res.stage} ({res.inputs.get('note','')})")

    # 6: S1 after decline (below rising MA + sharp recent decline)
    closes_up = [100 * (1.004 ** i) for i in range(170)]
    closes_crash = [closes_up[-1] * (0.97 ** i) for i in range(30)]
    closes = closes_up + closes_crash
    res = classify_from_ohlc(closes)
    total += 1
    if res.stage in (1, 4):
        passed += 1
    else:
        failures.append(f"  FAIL crash_then_settle: expected S1 or S4, got {res.stage}")

    # 7: Flat MA + price near MA (transitional)
    closes = [100.0 + (i % 5 - 2) * 0.3 for i in range(200)]
    res = classify_from_ohlc(closes)
    total += 1
    if res.stage in (1, 3):
        passed += 1
    else:
        failures.append(f"  FAIL flat_transitional: expected S1 or S3, got {res.stage}")

    return passed, total, failures


# ──────────────────────────────────────────────────────────────────────
# CLI entry
# ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    import json
    import re
    import sys
    from collections import Counter
    from pathlib import Path

    ap = argparse.ArgumentParser()
    ap.add_argument("--charts-dir", type=Path, default=Path(__file__).resolve().parent.parent / "charts")
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--test", action="store_true")
    args = ap.parse_args()

    if args.test:
        print(f"stage_classifier.py v{__version__} — self-tests")
        p, t, fails = _self_test()
        print(f"\nResult: {p}/{t} passed")
        for f in fails:
            print(f)
        sys.exit(0 if p == t else 1)

    line_re = re.compile(r'CHART_REGISTRY\["([^"]+)"\]\s*=\s*(\[.*\]);?\s*$', re.DOTALL)
    results = {}
    counter = Counter()
    confidence_counter = Counter()
    files = sorted(args.charts_dir.glob("*.js"))
    if args.limit:
        files = files[:args.limit]
    print(f"Classifying {len(files)} tickers (v{__version__})...")

    for cf in files:
        try:
            txt = cf.read_text(encoding="utf-8", errors="ignore")
            idx = txt.find("CHART_REGISTRY[")
            m = line_re.search(txt[idx:])
            if not m:
                continue
            ticker = m.group(1)
            rows = json.loads(m.group(2).rstrip(";\n "))
            closes = [r[4] for r in rows if len(r) >= 5 and r[4] is not None]
            res = classify_from_ohlc(closes)
            results[ticker] = {
                "stage": res.stage,
                "label": res.label,
                "confidence": res.confidence,
                "inputs": res.inputs,
            }
            counter[res.stage] += 1
            confidence_counter[res.confidence] += 1
        except Exception as e:
            print(f"  FAIL {cf.name}: {e}")

    print("\nDistribution:")
    for k in [1, 2, 3, 4, None]:
        label = f"Stage {k}" if k else "Unclassified"
        print(f"  {label}: {counter[k]:>4}")
    print("\nConfidence:")
    for k in ["high", "medium", "low"]:
        print(f"  {k:>6}: {confidence_counter[k]:>4}")

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(results), encoding="utf-8")
        print(f"\nWrote {len(results)} entries to {args.out}")
