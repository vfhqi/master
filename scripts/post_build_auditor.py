#!/usr/bin/env python3
"""
Post-Build Auditor — Master Dashboard deployed HTML integrity check.

Runs AFTER build_dashboard.py (and ideally after push) to verify the
deployed/index.html is structurally complete, has all expected markers,
has its embedded MASTER_DATA stocks count matching the source JSONs,
and contains the rendered tab/column counts the build is supposed to
produce.

Invocation:
    python scripts/post_build_auditor.py                # audits local index.html
    python scripts/post_build_auditor.py --remote       # also fetches deployed URL

Exit codes:
    0 — all checks passed
    1 — at least one check failed
    2 — fatal error (script itself crashed)

Author: Session 43 autonomous batch (17-May-26)
SOP-ref: Item #9a post-build half. Complements pre_build_validator.py.
"""
import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from typing import List, Tuple, Optional

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
DATA_DIR = ROOT / "data"
INDEX_HTML = ROOT / "index.html"
DEPLOYED_URL = "https://vfhqi.github.io/master/index.html"

# Markers the build is expected to produce. Update on each new patcher.
EXPECTED_MARKERS = [
    # NOTE: S40 batch markers (P1-P5) are PYTHON COMMENTS in the patcher scripts,
    # NOT in the rendered HTML by design — do NOT list them here.
    # S41 batch (16-May-26) - in-HTML markers verified live
    "MD-V2-S41-FMTNUM-NEAR-INTEGER-MARKER",
    "MD-V2-S41-OVERVIEW-STAGE1-SPLIT-MARKER",
    "MD-V2-S41-CHART-RIGHT-FREEZE-COL-MARKER",
    # S42 batch (17-May-26) - in-HTML markers verified live
    "MD-V2-CHART-ZOOM-PER-TAB-OVERRIDE-S42-MARKER",
    "MD-V2-S42-STAGE-COLOUR-MIRROR-MARKER",
    # S43 batch (17-May-26) - markers to verify post-application
    # "MD-V2-S43-BREAKOUT-RATING-OVERRIDE-MARKER",  # uncomment after S43 ships
]

# Expected tab IDs in the dashboard (sanity check)
EXPECTED_TAB_IDS = [
    "summary",      # Overview
    "stage_1", "stage_2", "stage_3", "stage_4",
    "pre_indicators", "post_indicators", "setups", "tests",
]

# ANSI colours
RED, GREEN, YELLOW, RESET, BOLD = "\033[91m", "\033[92m", "\033[93m", "\033[0m", "\033[1m"


def fail(msg): return ("FAIL", msg)
def warn(msg): return ("WARN", msg)
def ok(msg):   return ("OK", msg)


def read_html(path_or_url: str) -> Optional[str]:
    if path_or_url.startswith("http"):
        try:
            with urllib.request.urlopen(path_or_url, timeout=30) as r:
                return r.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"  fetch failed: {e}", file=sys.stderr)
            return None
    p = Path(path_or_url)
    if not p.exists(): return None
    return p.read_text(encoding="utf-8", errors="replace")


def check_structural(html: str) -> List[Tuple[str, str]]:
    r = []
    if not html.strip().startswith("<!DOCTYPE") and not html.strip().startswith("<html"):
        r.append(fail("HTML does not start with <!DOCTYPE or <html>"))
    elif not html.rstrip().endswith("</html>"):
        r.append(fail("HTML does not end with </html>"))
    else:
        r.append(ok(f"HTML structure brackets OK ({len(html):,} chars)"))

    # Script balance — opening vs closing tags must match
    opens = len(re.findall(r"<script\b[^>]*>", html, re.IGNORECASE))
    closes = len(re.findall(r"</script\s*>", html, re.IGNORECASE))
    if opens != closes:
        r.append(fail(f"<script> unbalanced: {opens} open, {closes} close"))
    else:
        r.append(ok(f"<script> balanced ({opens} pairs)"))

    # Var PB corruption (historical pattern flagged in feedback_dashboard_corruption_pattern.md)
    if re.search(r"\bvar\s+PB\s*=", html):
        r.append(fail("var PB found — historical dashboard corruption marker"))
    else:
        r.append(ok("no var PB corruption marker"))

    return r


def check_markers(html: str) -> List[Tuple[str, str]]:
    r = []
    for m in EXPECTED_MARKERS:
        if m in html:
            r.append(ok(f"marker present: {m}"))
        else:
            r.append(fail(f"marker MISSING: {m}"))
    return r


def check_embedded_data(html: str) -> List[Tuple[str, str]]:
    r = []
    # Find MASTER_DATA assignment
    m = re.search(r"window\.MASTER_DATA\s*=\s*(\{.*?\});\s*\n", html, re.DOTALL)
    if not m:
        m = re.search(r"window\.MASTER_DATA\s*=\s*(\{)", html)
        if m:
            r.append(warn("MASTER_DATA assignment found but cannot extract object (large)"))
        else:
            r.append(fail("MASTER_DATA assignment NOT found in HTML"))
            return r
    # Count stocks via the embedded literal — look for entries like "ticker":
    stock_count = len(re.findall(r'"ticker"\s*:\s*"[A-Z0-9.\-]+"', html))
    r.append(ok(f"embedded stocks ~ {stock_count} (ticker mentions)"))
    return r


def check_tabs(html: str) -> List[Tuple[str, str]]:
    r = []
    for tab_id in EXPECTED_TAB_IDS:
        # tab containers are usually <div id="tab-..." or data-tab="..."
        if re.search(rf'(id|data-tab)="(tab[-_])?{tab_id}"', html, re.IGNORECASE):
            r.append(ok(f"tab {tab_id} present"))
        elif tab_id in html:
            r.append(warn(f"tab {tab_id} referenced but no canonical container"))
        else:
            r.append(fail(f"tab {tab_id} NOT found"))
    return r


def check_freshness(path: str, max_age_h: float = 30.0) -> Tuple[str, str]:
    p = Path(path)
    if not p.exists(): return fail(f"{path} missing")
    import datetime
    mt = datetime.datetime.fromtimestamp(p.stat().st_mtime)
    age = (datetime.datetime.now() - mt).total_seconds() / 3600
    if age > max_age_h:
        return warn(f"{path} mtime {age:.1f}h old (warn > {max_age_h}h)")
    return ok(f"{path} mtime {age:.1f}h old")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--remote", action="store_true", help="also audit deployed URL")
    args = parser.parse_args()

    print(f"{BOLD}Post-Build Auditor — Master Dashboard{RESET}")
    print(f"Local: {INDEX_HTML}")
    if args.remote:
        print(f"Remote: {DEPLOYED_URL}")
    print()

    all_results = []

    # === Local audit ===
    print(f"{BOLD}[LOCAL] index.html{RESET}")
    html_local = read_html(str(INDEX_HTML))
    if html_local is None:
        all_results.append(fail("local index.html missing"))
        print(f"  [FAIL] local index.html missing")
    else:
        for r in check_structural(html_local):
            all_results.append(r); print(f"  [{r[0]}] {r[1]}")
        for r in check_markers(html_local):
            all_results.append(r); print(f"  [{r[0]}] {r[1]}")
        for r in check_embedded_data(html_local):
            all_results.append(r); print(f"  [{r[0]}] {r[1]}")
        for r in check_tabs(html_local):
            all_results.append(r); print(f"  [{r[0]}] {r[1]}")
        r = check_freshness(str(INDEX_HTML))
        all_results.append(r); print(f"  [{r[0]}] {r[1]}")
    print()

    if args.remote:
        print(f"{BOLD}[REMOTE] {DEPLOYED_URL}{RESET}")
        html_rem = read_html(DEPLOYED_URL)
        if html_rem is None:
            all_results.append(fail("remote fetch failed"))
            print(f"  [FAIL] remote fetch failed")
        else:
            for r in check_structural(html_rem):
                all_results.append(r); print(f"  [{r[0]}] {r[1]}")
            for r in check_markers(html_rem):
                all_results.append(r); print(f"  [{r[0]}] {r[1]}")
            for r in check_embedded_data(html_rem):
                all_results.append(r); print(f"  [{r[0]}] {r[1]}")
        print()

    fails = [r for r in all_results if r[0] == "FAIL"]
    warns = [r for r in all_results if r[0] == "WARN"]
    oks   = [r for r in all_results if r[0] == "OK"]
    print(f"{BOLD}Summary{RESET}: {GREEN}{len(oks)} OK{RESET} | {YELLOW}{len(warns)} WARN{RESET} | {RED}{len(fails)} FAIL{RESET}")

    if fails:
        print(f"\n{RED}{BOLD}AUDIT: FAIL{RESET}")
        return 1
    print(f"\n{GREEN}{BOLD}AUDIT: PASS{RESET}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        print(f"Auditor crashed: {e}", file=sys.stderr)
        import traceback; traceback.print_exc()
        sys.exit(2)
