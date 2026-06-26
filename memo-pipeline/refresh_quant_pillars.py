#!/usr/bin/env python3
"""
refresh_quant_pillars.py -- B7b: daily quant pillar refresh for p1/p5/p6.

Reads three master-dashboard data files and writes letter grades (A-F) for the
quantitative pillars to databases/master/ic-ratings-current.json:

  p1_technical_momentum  ← s3_aligned_results.json (Minervini criteria score)
                           + tab9_data.json (Stage 2 classification)
  p5_ss_earnings_momentum ← factset-ssem.json (SSEM momentum score)
  p6_valuation           ← factset-valuation.json (PE percentile vs history)

GRADE THRESHOLDS (v1, provisional — tune via P1/P5/P6_THRESHOLDS constants):

  p1 (Minervini score 0-6 criteria, Stage 2 classification):
    A: Stage2=Probable AND score >= 4
    B: Stage2=Probable OR (Stage2=Plausible AND score >= 3)
    C: Stage2=Plausible OR score >= 3
    D: Stage2=Possible OR score >= 1
    F: Stage2=None AND score == 0
    —: data absent

  p5 (SSEM momentum — signed weighted-revision score):
    A: >= 15   (strong positive — broad upgrades)
    B: >= 5    (moderate positive)
    C: >= -3   (flat or mild negative, majority buy)
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
  If an entry was last_updated_by != "quant_refresh" AND p1/p5/p6 are already
  set to non-"—" values, the existing grades are NOT overwritten.
  Use --force to override all.

Usage:
  python3 scripts/memo-pipeline/refresh_quant_pillars.py
  python3 scripts/memo-pipeline/refresh_quant_pillars.py --dry-run
  python3 scripts/memo-pipeline/refresh_quant_pillars.py --force  # overwrite APM grades
  python3 scripts/memo-pipeline/refresh_quant_pillars.py --ticker BRAV-SE

Author: Watson (Sonnet, SA role), 2026-06-26 (Block B7b).
"""

import os, sys, json, argparse, tempfile
from pathlib import Path
from datetime import date

HERE = Path(__file__).resolve().parent
IC_RATINGS_PATH = "databases/master/ic-ratings-current.json"

# ---------------------------------------------------------------------------
# Grade thresholds — tune these without code changes
# ---------------------------------------------------------------------------

# p1: (min_minervini_score, stage2_classification) → grade
# Stage 2 classifications: "Probable" > "Plausible" > "Possible" > "None"
STAGE2_RANK = {"Probable": 3, "Plausible": 2, "Possible": 1, "None": 0}

# p5 SSEM momentum score → letter grade
P5_THRESHOLDS = [
    (15,  "A"),
    ( 5,  "B"),
    (-3,  "C"),
    (-15, "D"),
]  # below -15 → F

# p6 PE percentile (lower = cheaper = better)
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
# Data loaders
# ---------------------------------------------------------------------------

def load_quant_data(R: Path) -> dict:
    """Load all three quant source files. Returns dict keyed by ticker."""
    data_dir = R / "master-dashboard" / "data"
    
    # p1 source 1: Minervini criteria scores
    s3 = {}
    s3_path = data_dir / "s3_aligned_results.json"
    if s3_path.exists():
        raw = json.loads(s3_path.read_text(encoding="utf-8"))
        s3 = raw.get("results", {})
    
    # p1 source 2: Stage 2 classification
    stage2 = {}
    tab9_path = data_dir / "tab9_data.json"
    if tab9_path.exists():
        raw = json.loads(tab9_path.read_text(encoding="utf-8"))
        stage2 = raw.get("all_ratings", {})
    
    # p5 source: SSEM
    ssem = {}
    ssem_path = data_dir / "factset-ssem.json"
    if ssem_path.exists():
        raw = json.loads(ssem_path.read_text(encoding="utf-8"))
        ssem = {k: v for k, v in raw.items() if k != "_meta"}
    
    # p6 source: valuation
    val = {}
    val_path = data_dir / "factset-valuation.json"
    if val_path.exists():
        raw = json.loads(val_path.read_text(encoding="utf-8"))
        val = {k: v for k, v in raw.items() if k != "_meta"}
    
    # Merge by ticker
    all_tickers = set(s3) | set(stage2) | set(ssem) | set(val)
    merged = {}
    for t in all_tickers:
        merged[t] = {
            "s3_score": s3.get(t, {}).get("score"),
            "stage2":   stage2.get(t, {}).get("s2"),
            "ssem_momentum": ssem.get(t, {}).get("momentum"),
            "pe_percentile": val.get(t, {}).get("pe_percentile"),
        }
    return merged

# ---------------------------------------------------------------------------
# Grade computation
# ---------------------------------------------------------------------------

def grade_p1(s3_score, stage2_str) -> str:
    """Technical momentum grade from Minervini criteria + Stage 2."""
    if s3_score is None and stage2_str is None:
        return "—"
    score = s3_score or 0
    s2r = STAGE2_RANK.get(stage2_str or "None", 0)
    if s2r >= 3 and score >= 4:      return "A"
    if s2r >= 3 or (s2r == 2 and score >= 3):  return "B"
    if s2r == 2 or score >= 3:       return "C"
    if s2r >= 1 or score >= 1:       return "D"
    return "F"


def grade_p5(momentum) -> str:
    """SSEM grade from momentum score."""
    if momentum is None:
        return "—"
    for threshold, grade in P5_THRESHOLDS:
        if momentum >= threshold:
            return grade
    return "F"


def grade_p6(pe_percentile) -> str:
    """Valuation grade from PE percentile."""
    if pe_percentile is None:
        return "—"
    for threshold, grade in P6_THRESHOLDS:
        if pe_percentile <= threshold:
            return grade
    return "F"

# ---------------------------------------------------------------------------
# Ticker lookup (handles both suffixed BRAV-SE and bare BRAV)
# ---------------------------------------------------------------------------

def _quant_key(ic_ticker: str, quant_data: dict) -> str:
    """Find the quant data key for an ic-ratings ticker (may be bare or suffixed)."""
    # Direct match
    if ic_ticker in quant_data:
        return ic_ticker
    # Try common suffix combinations
    for suffix in ["-SE", "-GB", "-DK", "-DE", "-FR", "-IT", "-BE", "-NL",
                   "-CH", "-AT", "-FI", "-NO", "-IE", "-ES", "-PT", "-PL"]:
        candidate = ic_ticker + suffix
        if candidate in quant_data:
            return candidate
    return None

# ---------------------------------------------------------------------------
# Main refresh
# ---------------------------------------------------------------------------

def refresh_ticker(entry: dict, quant_data: dict, force: bool = False) -> tuple:
    """Update p1/p5/p6 for one entry. Returns (changed: bool, log_line: str)."""
    ticker = entry.get("ticker", "?")
    
    # Find quant data
    qk = _quant_key(ticker, quant_data)
    if not qk:
        return False, f"{ticker}: no quant data found"
    q = quant_data[qk]
    
    # Compute grades
    new_p1 = grade_p1(q.get("s3_score"), q.get("stage2"))
    new_p5 = grade_p5(q.get("ssem_momentum"))
    new_p6 = grade_p6(q.get("pe_percentile"))
    
    pillars = entry.setdefault("pillars", {})
    old_p1 = pillars.get("p1_technical_momentum", "—")
    old_p5 = pillars.get("p5_ss_earnings_momentum", "—")
    old_p6 = pillars.get("p6_valuation", "—")
    
    # Override protection: don't overwrite APM-set grades unless --force
    is_quant_managed = entry.get("last_updated_by") == "quant_refresh"
    if not force and not is_quant_managed:
        # Only update "—" slots
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
    entry["_quant_source_ticker"] = qk
    
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
    
    quant_data = load_quant_data(R)
    
    results = []
    changed_count = 0
    for entry in stocks:
        t = entry.get("ticker", "")
        if ticker_filter and t != ticker_filter:
            continue
        changed, log = refresh_ticker(entry, quant_data, force=force)
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
    
    results.append(f"\n  Total: {changed_count} updated, {len(stocks) - changed_count} unchanged"
                   f"{' (DRY-RUN — not written)' if dry_run else ''}")
    return results


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="B7b: daily quant pillar refresh — p1/p5/p6 → ic-ratings-current.json"
    )
    ap.add_argument("--dry-run", action="store_true", help="Preview without writing")
    ap.add_argument("--force", action="store_true", help="Overwrite APM-set grades")
    ap.add_argument("--ticker", help="Refresh a single ticker only")
    args = ap.parse_args()

    R = cowork_root()
    results = run_refresh(R, dry_run=args.dry_run, force=args.force, ticker_filter=args.ticker)
    for line in results:
        print(line)
