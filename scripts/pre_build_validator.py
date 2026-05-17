#!/usr/bin/env python3
"""
Pre-Build Validator — Master Dashboard data integrity gate.

Runs BEFORE build_dashboard.py to catch broken JSONs, row-count
divergence, schema drift, missing required fields. Aborts the build
with a non-zero exit code if anything fails — preventing bad ships.

Invocation:
    python scripts/pre_build_validator.py

Exit codes:
    0 — all checks passed
    1 — at least one check failed
    2 — fatal error (script itself crashed)

Author: Session 43 autonomous batch (17-May-26)
SOP-ref: Item #9a — automated audit/QC, both pre-build (gate) AND
         post-build (audit). This is the pre-build half.
"""
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Resolve paths relative to this script's directory
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
DATA_DIR = ROOT / "data"

# Files we expect the build to consume
REQUIRED_JSON_FILES = {
    "filter-results.json": {
        "required_top_keys": ["_meta", "stocks"],
        "stocks_min_count": 800,    # universe is ~946; alarm below 800
        "per_stock_required_keys": [
            "ticker", "md_v2"
        ],
        "md_v2_required_subkeys": [
            "stage_1", "stage_2", "stage_3", "stage_4",
            "pre_indicators", "indicators", "post_indicators",
            "setups", "tests", "persistence"
        ],
    },
    "prices.json": {
        "required_top_keys": [],
        "per_stock_required_keys": [
            "ticker", "price", "mas", "high_52w", "low_52w"
        ],
    },
    "stage-snapshots.json": {
        "required_top_keys": [],
    },
    "filter-history.json": {
        "required_top_keys": [],
    },
    "universe.json": {
        "required_top_keys": [],
    },
}

# ANSI colours (works in Windows Terminal + WSL + Linux)
RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def fail(msg: str) -> Tuple[str, str]:
    return ("FAIL", msg)


def warn(msg: str) -> Tuple[str, str]:
    return ("WARN", msg)


def ok(msg: str) -> Tuple[str, str]:
    return ("OK", msg)


def check_file_exists(name: str) -> Tuple[str, str]:
    p = DATA_DIR / name
    if not p.exists():
        return fail(f"{name} missing (expected at {p})")
    if p.stat().st_size == 0:
        return fail(f"{name} is empty")
    return ok(f"{name} exists ({p.stat().st_size:,} bytes)")


def check_json_parses(name: str) -> Tuple[Tuple[str, str], Any]:
    p = DATA_DIR / name
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ok(f"{name} parses as valid JSON"), data
    except json.JSONDecodeError as e:
        return fail(
            f"{name} is INVALID JSON — parse fails at line {e.lineno} col {e.colno} (char {e.pos}): {e.msg}"
        ), None
    except Exception as e:
        return fail(f"{name} failed to read: {e}"), None


def check_required_keys(name: str, data: Any, schema: Dict) -> List[Tuple[str, str]]:
    results = []
    if not isinstance(data, (dict, list)):
        results.append(fail(f"{name} top-level is {type(data).__name__}; expected dict or list"))
        return results

    if "required_top_keys" in schema:
        if isinstance(data, dict):
            missing = [k for k in schema["required_top_keys"] if k not in data]
            if missing:
                results.append(fail(f"{name} missing top-level keys: {missing}"))
            else:
                results.append(ok(f"{name} top-level keys present"))

    # Per-stock checks if stocks list exists
    stocks = None
    if isinstance(data, dict) and "stocks" in data and isinstance(data["stocks"], list):
        stocks = data["stocks"]
    elif isinstance(data, list):
        stocks = data

    if stocks is not None:
        # Row count check
        min_count = schema.get("stocks_min_count")
        if min_count is not None and len(stocks) < min_count:
            results.append(fail(
                f"{name} has only {len(stocks)} stocks; expected >= {min_count}"
            ))
        else:
            results.append(ok(f"{name} stocks count = {len(stocks)}"))

        # Per-stock required key check
        per_keys = schema.get("per_stock_required_keys", [])
        md_v2_keys = schema.get("md_v2_required_subkeys", [])
        missing_per_stock = []
        missing_md_v2 = []
        for s in stocks[:10]:  # sample first 10
            tkr = s.get("ticker", "?")
            for k in per_keys:
                if k not in s:
                    missing_per_stock.append(f"{tkr}/{k}")
            if md_v2_keys and "md_v2" in s:
                for k in md_v2_keys:
                    if k not in s["md_v2"]:
                        missing_md_v2.append(f"{tkr}/md_v2/{k}")
        if missing_per_stock:
            results.append(fail(f"{name} stocks missing keys (sample): {missing_per_stock[:5]}"))
        if missing_md_v2:
            results.append(fail(f"{name} stocks missing md_v2 subkeys (sample): {missing_md_v2[:5]}"))
        if not missing_per_stock and not missing_md_v2 and (per_keys or md_v2_keys):
            results.append(ok(f"{name} per-stock schema OK (sampled 10)"))

    return results


def check_cross_file_congruence(parsed: Dict[str, Any]) -> List[Tuple[str, str]]:
    results = []
    fr = parsed.get("filter-results.json")
    pj = parsed.get("prices.json")
    uj = parsed.get("universe.json")

    fr_tickers = set()
    if fr and isinstance(fr, dict) and isinstance(fr.get("stocks"), list):
        fr_tickers = {s.get("ticker") for s in fr["stocks"] if s.get("ticker")}
    pj_tickers = set()
    if pj:
        if isinstance(pj, list):
            pj_tickers = {s.get("ticker") for s in pj if isinstance(s, dict) and s.get("ticker")}
        elif isinstance(pj, dict) and isinstance(pj.get("stocks"), list):
            pj_tickers = {s.get("ticker") for s in pj["stocks"] if s.get("ticker")}
    uj_tickers = set()
    if uj and isinstance(uj, dict):
        uj_tickers = set(uj.keys())

    if fr_tickers and pj_tickers:
        only_fr = fr_tickers - pj_tickers
        only_pj = pj_tickers - fr_tickers
        if only_fr or only_pj:
            results.append(warn(
                f"filter-results / prices ticker divergence — only in FR: {len(only_fr)}, only in P: {len(only_pj)}"
            ))
            if only_fr:
                results.append(warn(f"  sample only-in-FR: {sorted(only_fr)[:5]}"))
            if only_pj:
                results.append(warn(f"  sample only-in-P: {sorted(only_pj)[:5]}"))
        else:
            results.append(ok(f"filter-results / prices tickers match ({len(fr_tickers)})"))

    if fr_tickers and uj_tickers:
        only_fr = fr_tickers - uj_tickers
        only_uj = uj_tickers - fr_tickers
        if only_fr or only_uj:
            results.append(warn(
                f"filter-results / universe ticker divergence — only in FR: {len(only_fr)}, only in U: {len(only_uj)}"
            ))
        else:
            results.append(ok(f"filter-results / universe tickers match"))

    return results


def check_freshness(name: str, max_age_hours: float = 30.0) -> Tuple[str, str]:
    p = DATA_DIR / name
    if not p.exists():
        return fail(f"{name} missing — cannot check freshness")
    import datetime
    mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime)
    age_h = (datetime.datetime.now() - mtime).total_seconds() / 3600.0
    if age_h > max_age_hours:
        return warn(
            f"{name} mtime is {age_h:.1f}h old (warn threshold {max_age_hours}h) — last refresh may have failed"
        )
    return ok(f"{name} mtime is {age_h:.1f}h old (fresh)")


def main() -> int:
    print(f"{BOLD}Pre-Build Validator — Master Dashboard{RESET}")
    print(f"Data dir: {DATA_DIR}")
    print()

    all_results: List[Tuple[str, str]] = []
    parsed_data: Dict[str, Any] = {}

    # Step 1: existence
    print(f"{BOLD}[1/5] File existence{RESET}")
    for name in REQUIRED_JSON_FILES:
        r = check_file_exists(name)
        all_results.append(r)
        print(f"  [{r[0]}] {r[1]}")
    print()

    # Step 2: JSON parses
    print(f"{BOLD}[2/5] JSON parse validity{RESET}")
    for name in REQUIRED_JSON_FILES:
        r, data = check_json_parses(name)
        all_results.append(r)
        if data is not None:
            parsed_data[name] = data
        print(f"  [{r[0]}] {r[1]}")
    print()

    # Step 3: schema
    print(f"{BOLD}[3/5] Schema and row counts{RESET}")
    for name, schema in REQUIRED_JSON_FILES.items():
        if name in parsed_data:
            for r in check_required_keys(name, parsed_data[name], schema):
                all_results.append(r)
                print(f"  [{r[0]}] {r[1]}")
    print()

    # Step 4: cross-file congruence
    print(f"{BOLD}[4/5] Cross-file ticker congruence{RESET}")
    for r in check_cross_file_congruence(parsed_data):
        all_results.append(r)
        print(f"  [{r[0]}] {r[1]}")
    print()

    # Step 5: freshness
    print(f"{BOLD}[5/5] Freshness (mtime within 30h){RESET}")
    for name in REQUIRED_JSON_FILES:
        r = check_freshness(name)
        all_results.append(r)
        print(f"  [{r[0]}] {r[1]}")
    print()

    # Summary
    fails = [r for r in all_results if r[0] == "FAIL"]
    warns = [r for r in all_results if r[0] == "WARN"]
    oks   = [r for r in all_results if r[0] == "OK"]

    print(f"{BOLD}Summary{RESET}: {GREEN}{len(oks)} OK{RESET} | {YELLOW}{len(warns)} WARN{RESET} | {RED}{len(fails)} FAIL{RESET}")
    if fails:
        print(f"\n{RED}{BOLD}BUILD GATE: FAIL — fix the issues above before running build_dashboard.py{RESET}")
        return 1
    if warns:
        print(f"\n{YELLOW}{BOLD}BUILD GATE: PASS WITH WARNINGS — review and proceed{RESET}")
        return 0
    print(f"\n{GREEN}{BOLD}BUILD GATE: PASS{RESET}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"{RED}Validator crashed: {e}{RESET}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(2)
