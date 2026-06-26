#!/usr/bin/env python3
"""
refresh_quant_pillars.py -- B7b: daily quant pillar refresh for p1/p5/p6.

Reads master-dashboard data files and writes letter grades to
databases/master/ic-ratings-current.json:

  p1_technical_momentum   ← filter-results.json md_v2 (timeliness grade)
                            Uses canonical TL_ROWS logic from generate-timeliness-page.py.
                            Returns A/B/C for timeliness-qualified stocks, "—" if absent.
  p5_ss_earnings_momentum ← factset-ssem.json (SSEM momentum score)
  p6_valuation            ← factset-valuation.json (PE percentile vs history)

GRADE THRESHOLDS:

  p1 (timeliness grade from md_v2 TL_ROWS):
    A: Qualified or Probable on a group-1 TL row (probing bet, retest, VCP, spec)
    B: Plausible on a group-1 row, OR Probable on a group-2 row (pull_back/basing, s2gate)
    C: Possible on a group-1 row, OR Plausible on a group-2 row
    —: not in filter-results, or no qualifying TL cell

  p5 (SSEM momentum — signed weighted-revision score):
    A: >= 15   (strong positive — broad upgrades)
    B: >= 5    (moderate positive)
    C: >= -3   (flat or mild negative)
    D: >= -15  (meaningful negative)
    F: < -15   (broad downgrades)
    —: data absent

  p6 (PE percentile vs own history, 0-100 where low = cheap):
    A: <= 20   (historically cheap)
    B: <= 40
    C: <= 60
    D: <= 80
    F: > 80    (historically expensive)
    —: data absent or no PE data

OVERRIDE PROTECTION:
  If last_updated_by != "quant_refresh" AND p1/p5/p6 already set to non-"—",
  existing grades are NOT overwritten. Use --force to override.

Usage:
  python3 scripts/memo-pipeline/refresh_quant_pillars.py
  python3 scripts/memo-pipeline/refresh_quant_pillars.py --dry-run
  python3 scripts/memo-pipeline/refresh_quant_pillars.py --force
  python3 scripts/memo-pipeline/refresh_quant_pillars.py --ticker BRAV-SE

Author: Watson (Sonnet, SA role), 2026-06-26 (Block B7b, OQ-2 p1→timeliness).
"""

import os, sys, json, argparse, tempfile
from pathlib import Path
from datetime import date

HERE = Path(__file__).resolve().parent
IC_RATINGS_PATH = "databases/master/ic-ratings-current.json"

# ---------------------------------------------------------------------------
# Timeliness grade constants — canonical copy from generate-timeliness-page.py
# ---------------------------------------------------------------------------

TL_ROWS = [
    {"id":"pb_s1",     "path":["tests","probing_bet_s1"],                "stageNum":1, "cells":{"A":["Qualified","Probable"],"B":["Plausible"],"C":["Possible"]}},
    {"id":"pb_s2",     "path":["tests","probing_bet_s2"],                "stageNum":2, "cells":{"A":["Qualified","Probable"],"B":["Plausible"],"C":["Possible"]}},
    {"id":"retest",    "path":["tests","healthy_retest"],                "stageNum":2, "cells":{"A":["Qualified","Probable"],"B":["Plausible"],"C":["Possible"]}},
    {"id":"vcp",       "path":["tests","vcp_deploy_s2"],                 "stageNum":2, "cells":{"A":["Qualified","Probable"],"B":["Plausible"],"C":["Possible"]}},
    {"id":"spec_s3",   "path":["tests","speculative_bet_s3"],            "stageNum":3, "cells":{"A":["Qualified","Probable"],"B":["Plausible"],"C":["Possible"]}},
    {"id":"spec_s4",   "path":["tests","speculative_bet_s4"],            "stageNum":4, "cells":{"A":["Qualified","Probable"],"B":["Plausible"],"C":["Possible"]}},
    {"id":"pull_back", "path":["pre_indicators","pulling_back_uptrend"], "stageNum":2, "cells":{"B":["Probable"],"C":["Plausible"]}, "s2gate":True},
    {"id":"basing",    "path":["pre_indicators","basing"],               "stageNum":2, "cells":{"B":["Probable"],"C":["Plausible"]}, "s2gate":True},
    {"id":"s1_late",   "path":["stage_1"],                               "stageNum":1, "cells":{"B":["Probable"]}},
    {"id":"s1_early",  "path":["stage_1"],                               "stageNum":1, "cells":{"B":["Plausible"],"C":["Possible"]}},
]
TL_LETTER_RANK = {"A": 5, "B": 4, "C": 3, "D": 2, "F": 1}
TL_STAGE_RANK  = {2: 4, 1: 3, 3: 2, 4: 1}

# ---------------------------------------------------------------------------
# p5/p6 thresholds
# ---------------------------------------------------------------------------

P5_THRESHOLDS = [
    (15,  "A"),
    ( 5,  "B"),
    (-3,  "C"),
    (-15, "D"),
]  # below -15 → F

P6_THRESHOLDS = [
    (20, "A"),
    (40, "B"),
    (60, "C"),
    (80, "D"),
]  # above 80 → F

# ---------------------------------------------------------------------------
# Root detection
# ---------------------------------------------------------------------------

def cowork_root() -> Path:
    if os.environ.get("COWORK_ROOT"):
        return Path(os.environ["COWORK_ROOT"]).resolve()
    candidates = sorted(Path("/sessions").glob("*/mnt/COWORK")) if Path("/sessions").exists() else []
    if candidates:
        return candidates[0].resolve()
    return Path(".").resolve()

# ---------------------------------------------------------------------------
# Timeliness helper functions — exact port from generate-timeliness-page.py
# ---------------------------------------------------------------------------

def _tl_get_rating(md, path):
    obj = md
    for p in path:
        obj = obj.get(p) if isinstance(obj, dict) else None
    if isinstance(obj, dict) and obj.get("rating") and obj["rating"] != "None":
        return obj["rating"]
    return None

def _tl_is_s2pp(md):
    """True if stock is in Stage 2 price position (stage_2.rating Plausible or Probable)."""
    r = (md.get("stage_2") or {}).get("rating")
    return r in ("Plausible", "Probable")

def _tl_get_cells(md):
    result, s2pp = [], _tl_is_s2pp(md)
    for ri, row in enumerate(TL_ROWS):
        if row.get("s2gate") and not s2pp:
            continue
        rating = _tl_get_rating(md, row["path"])
        if not rating:
            continue
        for col, vals in row["cells"].items():
            if rating in vals:
                result.append({"col": col, "rowIdx": ri, "stageNum": row["stageNum"]})
    return result

def _tl_best_cell(cells):
    if not cells:
        return None
    best = cells[0]
    for c in cells[1:]:
        lrd = TL_LETTER_RANK.get(c["col"], 0) - TL_LETTER_RANK.get(best["col"], 0)
        if lrd > 0:   best = c; continue
        if lrd < 0:   continue
        srd = TL_STAGE_RANK.get(c["stageNum"], 0) - TL_STAGE_RANK.get(best["stageNum"], 0)
        if srd > 0:   best = c; continue
        if srd < 0:   continue
        if c["rowIdx"] < best["rowIdx"]:
            best = c
    return best

# ---------------------------------------------------------------------------
# Data loaders
# ---------------------------------------------------------------------------

def load_filter_results_index(R: Path) -> dict:
    """Returns {ticker: stock_entry} from filter-results.json."""
    path = R / "master-dashboard" / "data" / "filter-results.json"
    if not path.exists():
        print(f"  WARNING: filter-results.json not found at {path}", file=sys.stderr)
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    return {s["ticker"]: s for s in raw.get("stocks", []) if s.get("ticker")}


def load_p5p6_data(R: Path) -> dict:
    """Load p5 (SSEM) and p6 (valuation) source files. Returns dict keyed by ticker."""
    data_dir = R / "master-dashboard" / "data"

    ssem = {}
    ssem_path = data_dir / "factset-ssem.json"
    if ssem_path.exists():
        raw = json.loads(ssem_path.read_text(encoding="utf-8"))
        ssem = {k: v for k, v in raw.items() if k != "_meta"}

    val = {}
    val_path = data_dir / "factset-valuation.json"
    if val_path.exists():
        raw = json.loads(val_path.read_text(encoding="utf-8"))
        val = {k: v for k, v in raw.items() if k != "_meta"}

    all_tickers = set(ssem) | set(val)
    merged = {}
    for t in all_tickers:
        merged[t] = {
            "ssem_momentum": ssem.get(t, {}).get("momentum"),
            "pe_percentile": val.get(t, {}).get("pe_percentile"),
        }
    return merged

# ---------------------------------------------------------------------------
# Grade computation
# ---------------------------------------------------------------------------

def grade_p1_timeliness(ticker: str, fr_idx: dict) -> str:
    """TL grade (A/B/C) from filter-results.json md_v2, or '—' if absent."""
    entry = fr_idx.get(ticker)
    if entry is None:
        return "—"
    md = entry.get("md_v2", {})
    cells = _tl_get_cells(md)
    best = _tl_best_cell(cells)
    if best is None:
        return "—"
    return best["col"]


def grade_p5(momentum) -> str:
    if momentum is None:
        return "—"
    for threshold, grade in P5_THRESHOLDS:
        if momentum >= threshold:
            return grade
    return "F"


def grade_p6(pe_percentile) -> str:
    if pe_percentile is None:
        return "—"
    for threshold, grade in P6_THRESHOLDS:
        if pe_percentile <= threshold:
            return grade
    return "F"

# ---------------------------------------------------------------------------
# Ticker lookup (handles suffixed BRAV-SE and bare BRAV for p5/p6 data)
# ---------------------------------------------------------------------------

def _p5p6_key(ic_ticker: str, p5p6_data: dict) -> str:
    if ic_ticker in p5p6_data:
        return ic_ticker
    for suffix in ["-SE", "-GB", "-DK", "-DE", "-FR", "-IT", "-BE", "-NL",
                   "-CH", "-AT", "-FI", "-NO", "-IE", "-ES", "-PT", "-PL"]:
        candidate = ic_ticker + suffix
        if candidate in p5p6_data:
            return candidate
    return None

# ---------------------------------------------------------------------------
# Main refresh
# ---------------------------------------------------------------------------

def refresh_ticker(entry: dict, fr_idx: dict, p5p6_data: dict,
                   force: bool = False) -> tuple:
    """Update p1/p5/p6 for one entry. Returns (changed: bool, log_line: str)."""
    ticker = entry.get("ticker", "?")

    # p1: timeliness grade
    new_p1 = grade_p1_timeliness(ticker, fr_idx)

    # p5/p6: from FactSet data
    pk = _p5p6_key(ticker, p5p6_data)
    if pk:
        q = p5p6_data[pk]
        new_p5 = grade_p5(q.get("ssem_momentum"))
        new_p6 = grade_p6(q.get("pe_percentile"))
    else:
        new_p5 = "—"
        new_p6 = "—"

    pillars = entry.setdefault("pillars", {})
    old_p1 = pillars.get("p1_technical_momentum", "—")
    old_p5 = pillars.get("p5_ss_earnings_momentum", "—")
    old_p6 = pillars.get("p6_valuation", "—")

    # Override protection: don't overwrite APM-set grades unless --force
    is_quant_managed = entry.get("last_updated_by") == "quant_refresh"
    if not force and not is_quant_managed:
        if old_p1 != "—":
            new_p1 = old_p1
        if old_p5 != "—":
            new_p5 = old_p5
        if old_p6 != "—":
            new_p6 = old_p6

    if new_p1 == old_p1 and new_p5 == old_p5 and new_p6 == old_p6:
        return False, f"{ticker}: no change (p1={old_p1}, p5={old_p5}, p6={old_p6})"

    pillars["p1_technical_momentum"] = new_p1
    pillars["p5_ss_earnings_momentum"] = new_p5
    pillars["p6_valuation"] = new_p6
    entry["last_updated"] = str(date.today())
    entry["last_updated_by"] = "quant_refresh"
    entry["_quant_refresh_at"] = str(date.today())

    changes = []
    if new_p1 != old_p1: changes.append(f"p1 {old_p1}→{new_p1}")
    if new_p5 != old_p5: changes.append(f"p5 {old_p5}→{new_p5}")
    if new_p6 != old_p6: changes.append(f"p6 {old_p6}→{new_p6}")

    return True, f"{ticker}: {', '.join(changes)}"


def run_refresh(R: Path, dry_run: bool = False, force: bool = False,
                ticker_filter: str = None) -> list:
    """Refresh all (or one) entries in ic-ratings-current.json."""
    ic_path = R / IC_RATINGS_PATH
    data = json.loads(ic_path.read_text(encoding="utf-8"))
    stocks = data.get("stocks", [])

    fr_idx   = load_filter_results_index(R)
    p5p6_data = load_p5p6_data(R)

    results = []
    changed_count = 0
    for entry in stocks:
        t = entry.get("ticker", "")
        if ticker_filter and t != ticker_filter:
            continue
        changed, log = refresh_ticker(entry, fr_idx, p5p6_data, force=force)
        if changed:
            changed_count += 1
        results.append(f"  {'CHANGED' if changed else 'skip   '} {log}")

    if not dry_run and changed_count > 0:
        data["stocks"] = stocks
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
            raise RuntimeError(f"write failed: {e}") from e

    results.append(
        f"\n  Total: {changed_count} updated, {len(stocks) - changed_count} unchanged"
        f"{' (DRY-RUN — not written)' if dry_run else ''}"
    )
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="B7b: daily quant pillar refresh — p1 (timeliness) / p5 / p6 → ic-ratings-current.json"
    )
    ap.add_argument("--dry-run", action="store_true", help="Preview without writing")
    ap.add_argument("--force",   action="store_true", help="Overwrite APM-set grades")
    ap.add_argument("--ticker",  help="Refresh a single ticker only")
    args = ap.parse_args()

    R = cowork_root()
    results = run_refresh(R, dry_run=args.dry_run, force=args.force, ticker_filter=args.ticker)
    for line in results:
        print(line)
