#!/usr/bin/env python3
"""
update_ic_ratings.py -- B7a: sync memo ratings to ic-ratings-current.json at Station 6.

Reads Files/{TICKER}/A-J-memo/ratings.json and writes the memo pillar grades
(MR3→p2, MR4→p3, MR5→p4) plus recommendation/stage to ic-ratings-current.json.

Usage:
  python3 scripts/memo-pipeline/update_ic_ratings.py --ticker BRAV-SE
  python3 scripts/memo-pipeline/update_ic_ratings.py --ticker BRAV-SE --dry-run
  python3 scripts/memo-pipeline/update_ic_ratings.py --backfill   # all closed memos

Safe to run multiple times (idempotent).

Mapping (memo → ic-ratings pillar):
  MR3 → p2_market_paradigm_fit
  MR4 → p3_fundamental_change
  MR5 → p4_building_blocks

p1/p5/p6 are set by the daily quant-pillar refresh (B7b), not by this script.

Author: Watson (Sonnet, SA role), 2026-06-26 (Block B7a).
"""

import os, sys, json, argparse, tempfile, time
from pathlib import Path
from datetime import date

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

IC_RATINGS_PATH = "databases/master/ic-ratings-current.json"

# Memo master-rating → ic-ratings pillar column
MR_TO_PILLAR = {
    "MR3": "p2_market_paradigm_fit",
    "MR4": "p3_fundamental_change",
    "MR5": "p4_building_blocks",
}


def cowork_root() -> Path:
    if os.environ.get("COWORK_ROOT"):
        return Path(os.environ["COWORK_ROOT"]).resolve()
    candidates = sorted(Path("/sessions").glob("*/mnt/COWORK")) if Path("/sessions").exists() else []
    if candidates:
        return candidates[0].resolve()
    return Path(".").resolve()


def load_ratings_json(ticker: str, R: Path) -> dict:
    """Load Files/{TICKER}/A-J-memo/ratings.json."""
    path = R / "Files" / ticker / "A-J-memo" / "ratings.json"
    if not path.exists():
        raise FileNotFoundError(f"ratings.json not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_ic_ratings(R: Path) -> tuple:
    """Load ic-ratings-current.json. Returns (data_dict, path)."""
    path = R / IC_RATINGS_PATH
    if not path.exists():
        raise FileNotFoundError(f"ic-ratings-current.json not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    return data, path


def company_name_from_universe(ticker: str, R: Path) -> str:
    """Look up company name from universe.json. Falls back to ticker."""
    try:
        uni_path = R / "master-dashboard" / "data" / "universe.json"
        if uni_path.exists():
            uni = json.loads(uni_path.read_text(encoding="utf-8"))
            if isinstance(uni, list):
                for row in uni:
                    if row.get("ticker") == ticker:
                        return row.get("company", row.get("name", ticker))
            elif isinstance(uni, dict):
                row = uni.get(ticker, {})
                return row.get("company", row.get("name", ticker))
    except Exception:
        pass
    return ticker


def _find_entry(stocks: list, ticker: str) -> tuple:
    """Find entry index for ticker. Try exact match first, then bare ticker.
    Returns (index, matched_key) or (-1, None)."""
    # 1. Exact match (e.g., BRAV-SE)
    for i, s in enumerate(stocks):
        if s.get("ticker") == ticker:
            return i, ticker
    # 2. Bare-ticker match: strip country suffix (last hyphen + 2 chars if uppercase alpha)
    parts = ticker.rsplit("-", 1)
    if len(parts) == 2 and parts[1].isalpha() and parts[1].isupper() and len(parts[1]) == 2:
        base = parts[0]
        for i, s in enumerate(stocks):
            if s.get("ticker") == base:
                return i, base
    return -1, None


def _make_new_entry(ticker: str, ratings: dict, R: Path) -> dict:
    """Create a minimal new ic-ratings stock entry from memo ratings."""
    company = (
        ratings.get("company")
        or company_name_from_universe(ticker, R)
        or ticker
    )
    stage_raw = ratings.get("stage", "triaging")
    stage = stage_raw.title()   # "dd" → "DD" handled below
    if stage_raw.lower() in ("esa", "dd"):
        stage = stage_raw.upper()
    elif stage_raw.lower() == "triaging":
        stage = "Triaging"
    
    pillars = {
        "p1_technical_momentum": "—",
        "p2_market_paradigm_fit": "—",
        "p3_fundamental_change": "—",
        "p4_building_blocks": "—",
        "p5_ss_earnings_momentum": "—",
        "p6_valuation": "—",
    }
    return {
        "ticker": ticker,
        "company_name": company,
        "sector": None,
        "market_cap_eur_bn": None,
        "stage": stage,
        "status": "Active",
        "last_updated": str(date.today()),
        "last_updated_by": "pipeline",
        "pillars": pillars,
        "investment_case": {
            "primary_setup": None,
            "supporting_setup": None,
            "setup_maturity": None,
            "false_friend_risk": None,
            "fulcrum_drivers": None,
            "key_drivers": None,
            "transmission_clarity": None,
            "complexity_flag": False,
        },
        "actions": {
            "apm_recommendation": ratings.get("recommendation"),
            "next_action": None,
            "key_question": None,
            "parking_reason": None,
            "reassessment_trigger": None,
        },
        "interest_level": "medium",
        "_pipeline_source": "memo-pipeline/Station-6",
    }


def update_ic_ratings(ticker: str, R: Path, dry_run: bool = False) -> str:
    """Read ratings.json for ticker, update ic-ratings-current.json.
    Returns a log line describing what happened."""
    ratings = load_ratings_json(ticker, R)
    mr = ratings.get("master_ratings", {})
    
    # Extract grades we're responsible for
    p2 = mr.get("MR3", "—") or "—"
    p3 = mr.get("MR4", "—") or "—"
    p4 = mr.get("MR5", "—") or "—"
    stage_raw = ratings.get("stage", "")
    stage = stage_raw.upper() if stage_raw.lower() in ("esa", "dd") else stage_raw.title()
    recommendation = ratings.get("recommendation")
    
    data, ic_path = load_ic_ratings(R)
    stocks = data.get("stocks", [])
    
    idx, matched_key = _find_entry(stocks, ticker)
    
    if idx == -1:
        # New entry
        entry = _make_new_entry(ticker, ratings, R)
        entry["pillars"]["p2_market_paradigm_fit"] = p2
        entry["pillars"]["p3_fundamental_change"] = p3
        entry["pillars"]["p4_building_blocks"] = p4
        if recommendation:
            entry["actions"]["apm_recommendation"] = recommendation
        stocks.append(entry)
        action = f"CREATED new entry for {ticker} (suffix format)"
    else:
        # Update existing entry
        entry = stocks[idx]
        old = {
            "p2": entry.get("pillars", {}).get("p2_market_paradigm_fit", "—"),
            "p3": entry.get("pillars", {}).get("p3_fundamental_change", "—"),
            "p4": entry.get("pillars", {}).get("p4_building_blocks", "—"),
        }
        entry.setdefault("pillars", {})
        entry["pillars"]["p2_market_paradigm_fit"] = p2
        entry["pillars"]["p3_fundamental_change"] = p3
        entry["pillars"]["p4_building_blocks"] = p4
        if stage:
            entry["stage"] = stage
        entry["last_updated"] = str(date.today())
        entry["last_updated_by"] = "pipeline"
        entry.setdefault("_pipeline_source", "memo-pipeline/Station-6")
        if recommendation and entry.get("actions"):
            entry["actions"]["apm_recommendation"] = recommendation
        action = (
            f"UPDATED {matched_key!r} entry: "
            f"p2 {old['p2']}→{p2}, p3 {old['p3']}→{p3}, p4 {old['p4']}→{p4}"
        )
    
    data["stocks"] = stocks
    
    if dry_run:
        return f"[DRY-RUN] {action}"
    
    # Write via tempfile+os.replace (FUSE safe)
    new_content = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    fd, tmp_path = tempfile.mkstemp(dir=str(ic_path.parent), suffix=".tmp")
    try:
        os.write(fd, new_content.encode("utf-8"))
        os.close(fd)
        os.replace(tmp_path, str(ic_path))
    except Exception as e:
        os.close(fd)
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        raise RuntimeError(f"write failed for {ic_path}: {e}") from e
    
    return action


def backfill_all(R: Path, dry_run: bool = False) -> list:
    """Find all Files/{TICKER}/A-J-memo/ratings.json files and sync each."""
    files_dir = R / "Files"
    results = []
    for ratings_path in sorted(files_dir.rglob("A-J-memo/ratings.json")):
        try:
            ratings = json.loads(ratings_path.read_text(encoding="utf-8"))
            ticker = ratings.get("ticker")
            if not ticker:
                # Try to infer from path
                ticker = ratings_path.parts[-3]
            msg = update_ic_ratings(ticker, R, dry_run=dry_run)
            results.append(f"  OK  {ticker}: {msg}")
        except Exception as e:
            results.append(f"  ERR {ratings_path}: {e}")
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="B7a: sync memo ratings → ic-ratings-current.json")
    ap.add_argument("--ticker", help="Suffixed ticker to sync (e.g. BRAV-SE)")
    ap.add_argument("--backfill", action="store_true", help="Sync all closed memos with ratings.json")
    ap.add_argument("--dry-run", action="store_true", help="Preview only — do not write")
    args = ap.parse_args()

    R = cowork_root()

    if args.backfill:
        results = backfill_all(R, dry_run=args.dry_run)
        for r in results:
            print(r)
        print(f"\nBackfill complete ({len(results)} memos processed)")
    elif args.ticker:
        try:
            msg = update_ic_ratings(args.ticker, R, dry_run=args.dry_run)
            print(f"OK: {msg}")
        except Exception as e:
            print(f"ERROR: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        ap.print_help()
