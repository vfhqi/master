#!/usr/bin/env python3
"""
patch_md_v2_mdjump_consumers_s27_2026_05_14.py
==============================================
SESSION 27 FOLLOW-UP (T-2) - _mdJump consumer wiring.

Targets: scripts/build_dashboard.py

Wires the 4 indicator/setup/test tab modules (pre_indicators / post_indicators
/ setups / tests) to CONSUME window._mdJump on render and pre-apply the chip
filter. This completes the Master Overview clickable-cell feature: Master
Overview already SETS window._mdJump = {tab, patternKey, tier} and calls
switchTab; this patch makes the target tab read it and arm the filter.

>>> RUN ORDER: this patcher MUST run AFTER the three Session 27 patchers <<<
    (patch_md_v2_tests_s27, patch_md_v2_tests_module_s27,
     patch_md_v2_master_overview_s27). It anchors on the post-S27 renderTests()
     function from the rebuilt ct module; running it before the S27 dashboard
     patcher would not find that anchor and would abort cleanly.

What it does - 4 uniform insertions, one per render entry function:
  renderPreIndicators / renderPostIndicators / renderSetups / renderTests
each gets a small block at the TOP that:
  1. reads window._mdJump
  2. if _mdJump.tab matches this tab AND _mdJump.patternKey + _mdJump.tier are
     set, sets that pattern's tierFilter to [tier]  (other patterns untouched)
  3. clears window._mdJump  (so it fires exactly once, on the first render
     after the jump - subsequent re-renders of the same tab are unaffected)

Each module's tierFilter object is module-local (piState/poState/stState/
ctState.tierFilter) - the insertion is INSIDE the module's closure, so it can
reach the state directly. The consumer is defensive: unknown patternKey or
tier is a no-op, never throws.

Patcher discipline: idempotent (marker check), pre-write backup, atomic write
at END, post-write verification, py_compile gate.

Run (Windows-side, AFTER the 3 S27 patchers + refresh_all):
  cd C:\\Users\\richb\\Documents\\COWORK\\master-dashboard
  python scripts\\patch_md_v2_mdjump_consumers_s27_2026_05_14.py
  python scripts\\build_dashboard.py        (rebuild index.html)
  git add -A && git commit -m "feat(MD V2): _mdJump consumer wiring - Master Overview cells pre-apply chip filter"
  git push
"""

import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
TARGET = SCRIPT_DIR / "build_dashboard.py"
MARKER = "MD-V2-MDJUMP-CONSUMER-S27-MARKER"


# The consumer block, parameterised per module. {STATE} = the module-local
# state object name; {TAB} = the tab id this module renders. Indented to sit
# inside the render function body.
def _consumer(state, tab):
    return (
        "    // " + MARKER + ": Master Overview cell-click handoff. Read\n"
        "    // window._mdJump once; if it targets this tab, arm the chip filter\n"
        "    // for the named pattern, then clear it so it fires exactly once.\n"
        "    (function(){\n"
        "      var j = window._mdJump;\n"
        "      if (j && j.tab === '" + tab + "') {\n"
        "        if (j.patternKey && j.tier && " + state + ".tierFilter &&\n"
        "            " + state + ".tierFilter.hasOwnProperty(j.patternKey)) {\n"
        "          " + state + ".tierFilter[j.patternKey] = [j.tier];\n"
        "        }\n"
        "        window._mdJump = null;\n"
        "      }\n"
        "    })();\n"
    )


# Each edit: (label, anchor, new). The anchor is the verbatim render-fn
# opening line; new = anchor + the consumer block injected right after it.
EDITS = [
    (
        "renderPreIndicators",
        "  function renderPreIndicators() {\n",
        "  function renderPreIndicators() {\n" + _consumer("piState", "pre_indicators"),
    ),
    (
        "renderPostIndicators",
        "  function renderPostIndicators() {\n",
        "  function renderPostIndicators() {\n" + _consumer("poState", "post_indicators"),
    ),
    (
        "renderSetups",
        "  function renderSetups() {\n",
        "  function renderSetups() {\n" + _consumer("stState", "setups"),
    ),
    (
        # post-S27 ct module: renderTests() is the entry. Anchor on its
        # opening line - identical in the S27 ct payload.
        "renderTests",
        "  function renderTests() {\n",
        "  function renderTests() {\n" + _consumer("ctState", "tests"),
    ),
]


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def main():
    if not TARGET.exists():
        print("ERROR: target not found: %s" % TARGET)
        sys.exit(1)

    src = TARGET.read_text(encoding="utf-8")

    if MARKER in src:
        print("SKIP: %s already present - patch already applied." % MARKER)
        sys.exit(0)

    # locate ALL anchors before mutating; each must appear exactly once
    problems = []
    for label, anchor, _ in EDITS:
        n = src.count(anchor)
        if n != 1:
            problems.append("%s anchor found %d times (expected 1) - is the post-S27 ct module present?" % (label, n))
    if problems:
        print("ERROR: anchor location failed - NOT writing:")
        for p in problems:
            print("  - %s" % p)
        print("\n  NOTE: this patcher must run AFTER the 3 Session 27 patchers.")
        sys.exit(1)

    new_src = src
    for label, anchor, new in EDITS:
        new_src = new_src.replace(anchor, new, 1)

    # validate compile
    tmp_out = SCRIPT_DIR / "_s27_mdjump_patched.py.s27check"
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

    # pre-write backup
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = TARGET.with_suffix(TARGET.suffix + ".bak-pre-mdjump-consumers-s27-%s" % ts)
    shutil.copy2(TARGET, backup)

    # atomic write
    tmp_final = TARGET.with_suffix(TARGET.suffix + ".mdjtmp")
    tmp_final.write_text(new_src, encoding="utf-8")
    tmp_final.replace(TARGET)

    # post-write verification
    written = TARGET.read_text(encoding="utf-8")
    checks = {
        "marker present (4x)": written.count(MARKER) == 4,
        "pi consumer": "j.tab === 'pre_indicators'" in written and "piState.tierFilter[j.patternKey]" in written,
        "po consumer": "j.tab === 'post_indicators'" in written and "poState.tierFilter[j.patternKey]" in written,
        "st consumer": "j.tab === 'setups'" in written and "stState.tierFilter[j.patternKey]" in written,
        "ct consumer": "j.tab === 'tests'" in written and "ctState.tierFilter[j.patternKey]" in written,
        "clears _mdJump": written.count("window._mdJump = null;") >= 4,
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
    print()
    all_ok = True
    for name, ok in checks.items():
        print("  [%s] %s" % ("OK" if ok else "FAIL", name))
        all_ok = all_ok and ok
    if not all_ok:
        print("\n  ONE OR MORE POST-WRITE CHECKS FAILED - review before building.")
        sys.exit(1)
    print("\n  All post-write checks passed.")


if __name__ == "__main__":
    main()
