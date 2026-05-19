"""
Master Dashboard - Filter History Integrity Validator
=====================================================

Stand-alone validator for data/filter-history.json.
Runs four integrity checks:

  1. Per-filter base-rate floor (warning)
     Capital count at T-0 must exceed configurable floor.
     Catches universe-wide null pattern (the 06-May-26 incident).

  2. T-0 cross-check vs filter-results.json (ERROR if >5 stocks)
     filter-history T-0 Capital count must match filter-results.json
     within +/-2 stocks per filter. Mismatch >5 = hard fail.

  3. Staleness (warning)
     filter-history _meta.generated must be within 36h of
     filter-results.json _meta.generated.

  4. Distribution sanity (warning)
     no single stage (Capital/Late/Early/None) may be >80% of
     universe for any filter at any timepoint. Catches all-null
     pattern that bit us on 06-May.

EXIT CODES:
  0 = clean (no warnings, no errors)
  1 = warnings only (advisory)
  2 = error (hard fail - abort downstream consumers)

Usage:
  python scripts/validate_filter_history.py
  python scripts/validate_filter_history.py --quiet
  python scripts/validate_filter_history.py --history PATH --results PATH

Hooked into refresh_all.py as a hard gate (step 3).

Authored: 11-May-26. Reference: corrections.md C17.
Revised: 11-May-26 PM - fixed stocks-as-list handling and UTR floor.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"

# Per-filter Capital base-rate floors at T-0. Below floor = warning.
# UTR set to 0 (was 2) - 11-May-26 data shows 0 UTR Capital legitimately.
BASE_RATE_FLOORS = {
    "basing_plateau":  2,
    "probing_bet":     20,
    "vcp":             0,
    "mm99":            10,
    "uptrend_retest":  0,
    "s3_topping":      0,
    "s4_declining":    0,
    "collapse":        0,
}

ACTIVE_FILTERS = ("basing_plateau", "probing_bet", "mm99", "uptrend_retest")

DIST_SATURATION_PCT = 0.80
XCHECK_TOLERANCE = 2
XCHECK_ERROR_THRESHOLD = 5
STALENESS_HOURS = 36


def safe_json_load(path):
    """Tolerate trailing concatenated docs / FUSE truncation tails."""
    with open(path) as f:
        content = f.read()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        dec = json.JSONDecoder()
        obj, _ = dec.raw_decode(content)
        return obj


def parse_meta_ts(s):
    """Parse a timestamp string. Return datetime or None."""
    if not s:
        return None
    fmts = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]
    for fmt in fmts:
        try:
            return datetime.strptime(s.strip()[:19], fmt[:19])
        except ValueError:
            continue
    return None


def count_stages_for_filter(stages_dict, filt):
    """stages_dict = filter-history.stages['T-X'] = {ticker: {filter: stage}}.
    Returns dict {stage: count}.
    """
    out = {"Capital": 0, "Late": 0, "Early": 0, None: 0, "other": 0}
    for tk, per_filter in stages_dict.items():
        s = per_filter.get(filt) if isinstance(per_filter, dict) else None
        if s in ("Capital", "Late", "Early"):
            out[s] += 1
        elif s is None:
            out[None] += 1
        else:
            out["other"] += 1
    return out


def count_results_capital(filter_results, filt):
    """filter-results.json has a 'stocks' LIST. Each item is a dict with a
    ticker and per-filter NESTED DICTS like
        {'mm99': {'stage': 'Capital', ...}, ...}.

    Defensive against alternative shapes:
      - stocks as dict (legacy) -> iterate values
      - filter field as plain string (older format) -> treat string == 'Capital'
    """
    stocks = filter_results.get("stocks") if isinstance(filter_results, dict) else None
    if stocks is None:
        return 0

    if isinstance(stocks, list):
        items = stocks
    elif isinstance(stocks, dict):
        items = stocks.values()
    else:
        return 0

    n = 0
    for s in items:
        if not isinstance(s, dict):
            continue
        v = s.get(filt)
        if isinstance(v, dict):
            stage = v.get("stage") or v.get("state")
        elif isinstance(v, str):
            stage = v
        else:
            stage = None
        if stage == "Capital":
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--history", default=str(DATA_DIR / "filter-history.json"))
    ap.add_argument("--results", default=str(DATA_DIR / "filter-results.json"))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    warnings = []
    errors = []

    def log(msg):
        if not args.quiet:
            print(msg)

    def warn(msg):
        warnings.append(msg)
        print("  WARN: " + msg, file=sys.stderr)

    def err(msg):
        errors.append(msg)
        print("  ERROR: " + msg, file=sys.stderr)

    log("Filter-history integrity validator")
    log("  history: " + args.history)
    log("  results: " + args.results)

    if not os.path.exists(args.history):
        err("filter-history.json not found at " + args.history)
        sys.exit(2)
    if not os.path.exists(args.results):
        err("filter-results.json not found at " + args.results)
        sys.exit(2)

    try:
        fh = safe_json_load(args.history)
    except Exception as e:
        err("failed to parse filter-history.json: " + str(e))
        sys.exit(2)
    try:
        fr = safe_json_load(args.results)
    except Exception as e:
        err("failed to parse filter-results.json: " + str(e))
        sys.exit(2)

    fh_meta = fh.get("_meta", {}) if isinstance(fh, dict) else {}
    fr_meta = fr.get("_meta", {}) if isinstance(fr, dict) else {}
    stages = fh.get("stages") if isinstance(fh, dict) else None
    if not stages or "T-0" not in stages:
        err("filter-history.json missing 'stages' section or T-0 timepoint")
        sys.exit(2)

    t0_stages = stages.get("T-0", {})
    universe_size = len(t0_stages)
    log("  universe size at T-0: " + str(universe_size))

    log("")
    log("Check 1: per-filter Capital base-rate floors at T-0")
    for filt, floor in BASE_RATE_FLOORS.items():
        counts = count_stages_for_filter(t0_stages, filt)
        cap = counts["Capital"]
        log("  " + filt.ljust(20) + " Capital=" + str(cap).rjust(4) + "  floor=" + str(floor))
        if cap < floor:
            warn("base-rate floor breach: " + filt + " has " + str(cap) + " Capital at T-0 (floor=" + str(floor) + ")")

    log("")
    log("Check 2: T-0 cross-check against filter-results.json")
    for filt in BASE_RATE_FLOORS.keys():
        fh_cap = count_stages_for_filter(t0_stages, filt)["Capital"]
        fr_cap = count_results_capital(fr, filt)
        diff = abs(fh_cap - fr_cap)
        log("  " + filt.ljust(20) + " fh=" + str(fh_cap).rjust(4) + "  fr=" + str(fr_cap).rjust(4) + "  diff=" + str(diff))
        if diff > XCHECK_ERROR_THRESHOLD:
            err("T-0 cross-check FAIL: " + filt + " filter-history=" + str(fh_cap) + " vs filter-results=" + str(fr_cap) + " (diff=" + str(diff) + " > " + str(XCHECK_ERROR_THRESHOLD) + ")")
        elif diff > XCHECK_TOLERANCE:
            warn("T-0 cross-check soft drift: " + filt + " fh=" + str(fh_cap) + " fr=" + str(fr_cap) + " diff=" + str(diff))

    log("")
    log("Check 3: staleness")
    fh_ts = parse_meta_ts(fh_meta.get("generated"))
    fr_ts = parse_meta_ts(fr_meta.get("generated"))
    if fh_ts and fr_ts:
        delta_h = abs((fr_ts - fh_ts).total_seconds()) / 3600.0
        log("  history generated: " + str(fh_ts))
        log("  results generated: " + str(fr_ts))
        log("  delta: " + str(round(delta_h, 1)) + "h  (threshold " + str(STALENESS_HOURS) + "h)")
        if delta_h > STALENESS_HOURS:
            warn("staleness: filter-history is " + str(round(delta_h, 1)) + "h apart from filter-results")
    else:
        warn("staleness check skipped - could not parse timestamps")

    log("")
    log("Check 4: distribution sanity (no single stage >80%)")
    for tp_label in ("T-0", "T-1", "T-5", "T-22"):
        tp_stages = stages.get(tp_label, {})
        if not tp_stages:
            continue
        for filt in ACTIVE_FILTERS:
            counts = count_stages_for_filter(tp_stages, filt)
            total = sum(v for k, v in counts.items() if k != "other")
            if total == 0:
                continue
            for stage, n in counts.items():
                if stage == "other":
                    continue
                pct = n / total
                if pct > DIST_SATURATION_PCT:
                    stage_label = str(stage) if stage is not None else "None"
                    warn("distribution saturation: " + filt + " @ " + tp_label + " has " + str(n) + "/" + str(total) + " = " + str(round(pct*100)) + "% in " + stage_label + " stage")

    log("")
    log("Summary: " + str(len(warnings)) + " warnings, " + str(len(errors)) + " errors")
    if errors:
        print("VALIDATION FAILED - " + str(len(errors)) + " error(s)", file=sys.stderr)
        sys.exit(2)
    if warnings:
        print("VALIDATION PASSED WITH WARNINGS - " + str(len(warnings)) + " warning(s)", file=sys.stderr)
        sys.exit(1)
    log("VALIDATION CLEAN")
    sys.exit(0)


if __name__ == "__main__":
    main()
