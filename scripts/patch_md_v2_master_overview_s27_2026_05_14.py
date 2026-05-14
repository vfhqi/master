#!/usr/bin/env python3
"""
patch_md_v2_master_overview_s27_2026_05_14.py
=============================================
SESSION 27 - Master Overview tab (NEW TAB).

Targets: scripts/build_dashboard.py

Builds the Master Overview tab per build-spec roadmap item 2: a synoptic
rating matrix - every MD V2 screen (4 stages + 3 pre-test indicators + 5
post-test indicators + 4 capital qualification setups + 4 capital
deployment tests = 20 rows) x 4 rating-tier columns (None/Possible/
Plausible/Probable), count of stocks per cell. Cells are clickable: they
jump to the underlying tab and stash a (pattern, tier) intent in
window._mdJump. The funnel banner and other visualisations are PARKED
(Richard's instruction) - this is the basic table.

Master Overview becomes the DEFAULT LANDING TAB (Richard's instruction).

This is a NEW TAB, so it follows the D-MD-V2-44 5-edit checklist, plus a
6th edit for the default-tab change:
  1. TABS entry           -> emits the <div id="tab-master_overview"> host
  2. V2 nav button swap   -> placeholder span -> real <button>
  3. IMPLEMENTED_TABS     -> wires into switchTab gating
  4. renderTab dispatch   -> else if(id==="master_overview")renderMasterOverview()
  5. module + CSS inline  -> the mo module + its CSS block
  6. bootstrap default    -> window.currentTab || 'stage_1' -> || 'master_overview'

NOTE on _mdJump consumers: the per-tab tierFilter states (piState/poState/
ctState/...) are module-local vars, not on window. So a cell click jumps to
the correct tab but cannot yet reach in to pre-apply the chip filter. Wiring
the 4 indicator/setup/test modules to CONSUME window._mdJump is a small,
clearly-scoped FOLLOW-UP patch - deliberately kept separate from this build
so the new-tab blast radius stays clean. The jump works now; the auto-filter
lights up when the consumer wiring lands.

Payload files (must sit beside this patcher in scripts/):
  _mo_module_s27.js   - the mo module body (incl. START/END markers)
  _mo_css_s27.txt     - the mo CSS block (incl. CSS-START/END markers)

Run order vs the Tests-module patcher: INDEPENDENT. This patcher anchors on
the TABS list, IMPLEMENTED_TABS, the nav placeholder, the bootstrap line,
the SETUPS dispatch line, and the TESTS CSS-END / MODULE-END markers - none
of which the Tests-module patcher rewrites. Either order is safe.

Patcher discipline: idempotent (marker check), pre-write backup, atomic
write at END, post-write verification.

Run (Windows-side):
  cd C:\\Users\\richb\\Documents\\COWORK\\master-dashboard
  python scripts\\patch_md_v2_master_overview_s27_2026_05_14.py
"""

import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
TARGET = SCRIPT_DIR / "build_dashboard.py"
MODULE_PAYLOAD = SCRIPT_DIR / "_mo_module_s27.js"
CSS_PAYLOAD = SCRIPT_DIR / "_mo_css_s27.txt"
MARKER = "MD-V2-MASTER-OVERVIEW-S27-MARKER"

# --- EDIT 1: TABS entry (host div emission) ---
# Insert a master_overview TABS entry right after the tests entry.
ANCHOR_1 = '    {"id": "tests", "label": "Tests", "accent": "#0F6E56"},\n'
EDIT_1_NEW = ANCHOR_1 + '    # MD-V2-MASTER-OVERVIEW-S27-MARKER - synoptic rating matrix, default landing tab\n    {"id": "master_overview", "label": "Master Overview", "accent": "#1b3d5c"},\n'

# --- EDIT 2: V2 nav button swap (placeholder span -> button) ---
ANCHOR_2 = "      + '<span class=\"v2-nav-placeholder\" title=\"Coming soon\">Master Overview</span>';"
EDIT_2_NEW = ("      + '<span class=\"v2-nav-sep\"></span>'\n"
              "      + '<span class=\"v2-nav-grp-label\">Overview</span>'\n"
              "      + '<button class=\"v2-nav-btn v2-grp-overview\" data-v2-tab=\"master_overview\" onclick=\"switchTab(\\'master_overview\\')\">Master Overview</button>';  /* MD-V2-MASTER-OVERVIEW-S27-MARKER */")

# --- EDIT 3: IMPLEMENTED_TABS entry ---
ANCHOR_3 = '    "tests",  # MD-V2-TESTS-MARKER\n'
EDIT_3_NEW = ANCHOR_3 + '    "master_overview",  # MD-V2-MASTER-OVERVIEW-S27-MARKER\n'

# --- EDIT 4: renderTab dispatch (anchor on the stable SETUPS line) ---
ANCHOR_4 = '  else if(id==="setups")renderSetups();  /* MD-V2-SETUPS-MARKER */\n'
EDIT_4_NEW = ANCHOR_4 + '  else if(id==="master_overview")renderMasterOverview();  /* MD-V2-MASTER-OVERVIEW-S27-MARKER */\n'

# --- EDIT 5: module + CSS inline ---
# CSS inserted right after the Tests CSS-END marker.
ANCHOR_5A = "/* MD-V2-TESTS-MARKER-CSS-END */"
# module inserted right after the Tests MODULE-END marker.
ANCHOR_5B = "/* MD-V2-TESTS-MARKER-MODULE-END */"

# --- EDIT 6: bootstrap default tab (two occurrences) ---
ANCHOR_6 = "window.currentTab || 'stage_1'"
EDIT_6_NEW = "window.currentTab || 'master_overview'"


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def main():
    for p in (TARGET, MODULE_PAYLOAD, CSS_PAYLOAD):
        if not p.exists():
            print("ERROR: required file not found: %s" % p)
            sys.exit(1)

    src = TARGET.read_text(encoding="utf-8")

    if MARKER in src:
        print("SKIP: %s already present in %s - patch already applied." % (MARKER, TARGET.name))
        sys.exit(0)

    module_new = MODULE_PAYLOAD.read_text(encoding="utf-8").rstrip("\n")
    css_new = CSS_PAYLOAD.read_text(encoding="utf-8").rstrip("\n")

    # payload sanity
    if "MD-V2-MASTER-OVERVIEW-MARKER-START" not in module_new or "MD-V2-MASTER-OVERVIEW-MARKER-END" not in module_new:
        print("ERROR: _mo_module_s27.js missing its START/END markers")
        sys.exit(1)
    if "MD-V2-MASTER-OVERVIEW-MARKER-CSS-START" not in css_new or "MD-V2-MASTER-OVERVIEW-MARKER-CSS-END" not in css_new:
        print("ERROR: _mo_css_s27.txt missing its CSS markers")
        sys.exit(1)
    if MARKER not in module_new:
        print("ERROR: _mo_module_s27.js missing the %s marker" % MARKER)
        sys.exit(1)

    # -- locate ALL anchors before mutating --
    problems = []
    if ANCHOR_1 not in src:           problems.append("ANCHOR_1 (TABS tests entry) not found")
    if ANCHOR_2 not in src:           problems.append("ANCHOR_2 (nav placeholder span) not found")
    if ANCHOR_3 not in src:           problems.append("ANCHOR_3 (IMPLEMENTED_TABS tests) not found")
    if ANCHOR_4 not in src:           problems.append("ANCHOR_4 (setups dispatch line) not found")
    if ANCHOR_5A not in src:          problems.append("ANCHOR_5A (Tests CSS-END marker) not found")
    if ANCHOR_5B not in src:          problems.append("ANCHOR_5B (Tests MODULE-END marker) not found")
    if src.count(ANCHOR_6) < 1:       problems.append("ANCHOR_6 (bootstrap default tab) not found")
    if problems:
        print("ERROR: anchor location failed - NOT writing:")
        for p in problems:
            print("  - %s" % p)
        sys.exit(1)

    new_src = src

    # EDIT 1
    new_src = new_src.replace(ANCHOR_1, EDIT_1_NEW, 1)
    # EDIT 2
    new_src = new_src.replace(ANCHOR_2, EDIT_2_NEW, 1)
    # EDIT 3
    new_src = new_src.replace(ANCHOR_3, EDIT_3_NEW, 1)
    # EDIT 4
    new_src = new_src.replace(ANCHOR_4, EDIT_4_NEW, 1)
    # EDIT 5A - CSS after Tests CSS-END
    new_src = new_src.replace(ANCHOR_5A, ANCHOR_5A + "\n\n" + css_new, 1)
    # EDIT 5B - module after Tests MODULE-END
    new_src = new_src.replace(ANCHOR_5B, ANCHOR_5B + "\n\n\n/* MD-V2-MASTER-OVERVIEW-MARKER-MODULE-START */\n" +
                              module_new + "\n/* MD-V2-MASTER-OVERVIEW-MARKER-MODULE-END */", 1)
    # EDIT 6 - bootstrap default tab, BOTH occurrences
    n6 = new_src.count(ANCHOR_6)
    new_src = new_src.replace(ANCHOR_6, EDIT_6_NEW)

    # -- validate compile --
    tmp_out = SCRIPT_DIR / "_s27_mo_patched.py.s27check"
    tmp_out.write_text(new_src, encoding="utf-8")
    import py_compile
    try:
        py_compile.compile(str(tmp_out), doraise=True)
    except py_compile.PyCompileError as e:
        print("ERROR: patched build_dashboard.py fails py_compile:\n%s" % e)
        sys.exit(1)
    finally:
        # clean up the validation temp file + any py_compile cache it created
        try:
            tmp_out.unlink(missing_ok=True)
            _pyc = tmp_out.parent / "__pycache__"
            if _pyc.is_dir():
                for _f in _pyc.glob(tmp_out.stem + "*"):
                    _f.unlink(missing_ok=True)
        except Exception:
            pass

    # -- pre-write backup --
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = TARGET.with_suffix(TARGET.suffix + ".bak-pre-master-overview-s27-%s" % ts)
    shutil.copy2(TARGET, backup)

    # -- atomic write --
    tmp_final = TARGET.with_suffix(TARGET.suffix + ".s27motmp")
    tmp_final.write_text(new_src, encoding="utf-8")
    tmp_final.replace(TARGET)

    # -- post-write verification --
    written = TARGET.read_text(encoding="utf-8")
    checks = {
        "marker present": MARKER in written,
        "TABS master_overview entry": '{"id": "master_overview", "label": "Master Overview"' in written,
        "nav button (placeholder gone)": '<span class="v2-nav-placeholder" title="Coming soon">Master Overview</span>' not in written,
        "nav button present": 'data-v2-tab="master_overview"' in written and "v2-grp-overview" in written,
        "IMPLEMENTED_TABS entry": '"master_overview",  # MD-V2-MASTER-OVERVIEW-S27-MARKER' in written,
        "dispatch entry": 'else if(id==="master_overview")renderMasterOverview();' in written,
        "module inlined": "renderMasterOverview" in written and "MD-V2-MASTER-OVERVIEW-MARKER-MODULE-START" in written,
        "CSS inlined": "#mo-main-table" in written and "MD-V2-MASTER-OVERVIEW-MARKER-CSS-START" in written,
        "default tab changed (both)": written.count("window.currentTab || 'master_overview'") == n6 and "window.currentTab || 'stage_1'" not in written,
        "20 rows in module": written.count("ratingPath:") >= 20,
        "compiles": True,
    }
    try:
        py_compile.compile(str(TARGET), doraise=True)
    except py_compile.PyCompileError as e:
        checks["compiles"] = False
        print("  POST-WRITE COMPILE FAIL: %s" % e)

    print()
    print("  patched : %s" % TARGET)
    print("  backup  : %s" % backup)
    print("  md5     : %s" % md5(TARGET))
    print("  bytes   : %d  (was %d)" % (TARGET.stat().st_size, len(src)))
    print("  bootstrap default-tab occurrences swapped: %d" % n6)
    print()
    all_ok = True
    for name, ok in checks.items():
        print("  [%s] %s" % ("OK" if ok else "FAIL", name))
        all_ok = all_ok and ok
    if not all_ok:
        print("\n  ONE OR MORE POST-WRITE CHECKS FAILED - review before running refresh_all.")
        sys.exit(1)
    print("\n  All post-write checks passed.")


if __name__ == "__main__":
    main()
