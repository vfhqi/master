"""
Patcher A — Master Dashboard minor UI patches (11-May-26)
=========================================================

Five edits:
  1. Default tab on load = CHANGES (was MM99)
  2. Selected tab styling — stronger active-tab visual
     (thicker accent bar + bold + slight scale + box-shadow)
  3. MM99 Sectors tile = Industries tile height (min-height:450px)
  4. CHANGES tab section title — dynamic date span using actual
     snapshot offsets, not naive subtract-7-days
  4b. CHANGES tab section title — show last-pipeline-run date so
      staleness is visible (per audit-11-May lesson)

Idempotent via anchor-string find/replace. Each edit aborts with
clear error if anchor not unique. Pre-write backup created.

Usage (Windows-side):
  cd C:\\Users\\richb\\Documents\\COWORK\\master-dashboard
  python scripts\\patch_dashboard_minor_2026_05_11.py
  python scripts\\build_dashboard.py
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
TARGET = PROJECT_DIR / "scripts" / "build_dashboard.py"


def backup(p):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = p.with_suffix(p.suffix + f".bak-pre-minor-patches-{ts}")
    shutil.copy2(p, bak)
    print(f"  backup -> {bak.name}")
    return bak


def replace_once(content, old, new, label):
    n = content.count(old)
    if n == 0:
        print(f"  [{label}] anchor not found:\n    {old[:120]}")
        sys.exit(1)
    if n > 1:
        print(f"  [{label}] anchor matches {n} times (must be unique):\n    {old[:120]}")
        sys.exit(1)
    return content.replace(old, new)


def main():
    print(f"Patching: {TARGET}")
    if not TARGET.exists():
        print(f"  ERROR: target not found")
        sys.exit(1)

    backup(TARGET)
    content = TARGET.read_text(encoding="utf-8")
    original_len = len(content)

    # ---- Edit 1: Default tab = CHANGES ----
    # Two locations need updating, both compare t["id"] to "mm99".

    # 1a — Active CSS class on tab buttons
    content = replace_once(
        content,
        'active = \' tab-active\' if t["id"] == "mm99" else \'\'',
        'active = \' tab-active\' if t["id"] == "changes" else \'\'',
        "Edit 1a (default tab active class)",
    )

    # 1b — Tab container display: block for changes, none for others
    content = replace_once(
        content,
        'display = "block" if t["id"] == "mm99" else "none"',
        'display = "block" if t["id"] == "changes" else "none"',
        "Edit 1b (default tab container display)",
    )

    # 1c — JS-side initial `currentTab` variable (line ~552)
    # Drives renderTab(currentTab) calls on data refresh/sort handlers.
    content = replace_once(
        content,
        'var currentTab="mm99",currentSort={col:"mm99_score",dir:"desc"};',
        'var currentTab="changes",currentSort={col:"chg_score",dir:"desc"};',
        "Edit 1c (currentTab initial value + currentSort default)",
    )

    # ---- Edit 2: Stronger active-tab visual ----
    # Current CSS (line 212):
    #   .tab-btn.tab-active{background:var(--tab-accent,#1b3d5c);color:#fff;font-weight:600;border-left-color:var(--tab-accent,#1b3d5c)}
    # New: bolder, scaled, shadow, thicker left border, slight letter-spacing.
    OLD_ACTIVE = ".tab-btn.tab-active{background:var(--tab-accent,#1b3d5c);color:#fff;font-weight:600;border-left-color:var(--tab-accent,#1b3d5c)}"
    NEW_ACTIVE = (
        ".tab-btn.tab-active{"
        "background:var(--tab-accent,#1b3d5c);"
        "color:#fff;font-weight:700;"
        "border:1px solid var(--tab-accent,#1b3d5c);"
        "border-left:5px solid var(--tab-accent,#1b3d5c);"
        "box-shadow:0 2px 6px rgba(0,0,0,0.18),inset 0 -2px 0 rgba(255,255,255,0.25);"
        "transform:translateY(-1px);"
        "letter-spacing:.3px;"
        "padding:5px 12px;"
        "position:relative;z-index:2}"
        ".tab-btn.tab-active:hover{background:var(--tab-accent,#1b3d5c);color:#fff;border-color:var(--tab-accent,#1b3d5c)}"
    )
    content = replace_once(content, OLD_ACTIVE, NEW_ACTIVE, "Edit 2 (active tab styling)")

    # ---- Edit 3: MM99 Sectors tile height — match Industries ----
    # Add min-height to .half-table .data-table-wrap so both tiles
    # in any ind-sec-wrap render at equal minimum height.
    # Current CSS (line 440):
    #   .half-table .data-table-wrap{overflow-y:auto;overflow-x:hidden}
    OLD_HT = ".half-table .data-table-wrap{overflow-y:auto;overflow-x:hidden}"
    NEW_HT = ".half-table .data-table-wrap{overflow-y:auto;overflow-x:hidden;min-height:450px}"
    content = replace_once(content, OLD_HT, NEW_HT, "Edit 3 (half-table min-height)")

    # ---- Edit 4: CHANGES tab section title — dynamic dating ----
    # Current (line 4115):
    #   h+='<h3 id="section-summary" style="margin:16px 0 8px;font-size:15px;font-weight:600;color:var(--text-primary)">Changes over last week &mdash; '+fmtDDM(t5D)+' to '+fmtDDM(t0D)+'</h3>';
    # New: keep core structure but show pipeline-run date alongside
    # so staleness is visible. Use actual t5D/t0D dates which derive
    # from fh._meta.generated (anchored on snapshot, not wall-clock).
    OLD_TITLE = (
        'h+=\'<h3 id="section-summary" style="margin:16px 0 8px;font-size:15px;font-weight:600;color:var(--text-primary)">Changes over last week &mdash; \'+fmtDDM(t5D)+\' to \'+fmtDDM(t0D)+\'</h3>\';'
    )
    NEW_TITLE = (
        'var _ageDays=Math.round((new Date()-t0D)/86400000);'
        'var _ageNote=_ageDays<=1?\'\':_ageDays<=3?\' &middot; <span style="color:#d69e2e">data \'+_ageDays+\'d old</span>\':\' &middot; <span style="color:#c53030;font-weight:700">data \'+_ageDays+\'d old &mdash; re-run pipeline</span>\';'
        'h+=\'<h3 id="section-summary" style="margin:16px 0 8px;font-size:15px;font-weight:600;color:var(--text-primary)">Changes over last week &mdash; \'+fmtDDM(t5D)+\' to \'+fmtDDM(t0D)+\' <span style="font-size:11px;font-weight:400;color:var(--text-secondary)">(pipeline run \'+fmtDDM(t0D)+\')</span>\'+_ageNote+\'</h3>\';'
    )
    content = replace_once(content, OLD_TITLE, NEW_TITLE, "Edit 4 (dynamic dating + staleness note)")

    # ---- Write back ----
    new_len = len(content)
    delta = new_len - original_len
    TARGET.write_text(content, encoding="utf-8")
    print(f"  wrote {new_len:,} bytes (was {original_len:,}, delta {delta:+,})")

    # py_compile sanity
    import py_compile
    try:
        py_compile.compile(str(TARGET), doraise=True)
        print("  py_compile: OK")
    except py_compile.PyCompileError as e:
        print(f"  py_compile FAILED: {e}")
        sys.exit(1)

    print("  done. Run: python scripts\\build_dashboard.py")


if __name__ == "__main__":
    main()
