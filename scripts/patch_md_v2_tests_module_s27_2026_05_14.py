#!/usr/bin/env python3
"""
patch_md_v2_tests_module_s27_2026_05_14.py
==========================================
SESSION 27 - Capital deployment tests tab RESTRUCTURE (dashboard side).

Targets: scripts/build_dashboard.py

Rebuilds the `ct` (Tests) tab module + CSS to match the Session 27 pipeline
restructure (see patch_md_v2_tests_s27_2026_05_14.py). Implements the
dashboard half of D-MD-V2-64 .. D-MD-V2-68:
  - 4 tests (was 3): ma_retest_upwards / vcp_deploy_s1 / vcp_deploy_s2 /
    probing_bet, each shown "in totality" - related setup test columns +
    trigger columns side by side.
  - 4-stage info block (Stage 1-4 ratings, info-only) after the 8 inputs.
  - Collapsing-rating info column on Probing bet.
  - L5D / L20D recent-trigger window columns (2 per test), reading the
    fired_l5d / fired_l20d / days_since_fired / history_depth fields the
    pipeline stamps onto each test record. Graceful "building" state when
    history depth is thin.
  - Chip filter, rating/score columns, pass-count breakdown, sortable
    headers, scope/tint/portfolio controls - all carried from the S26 ct
    module unchanged.

ALSO FIXES a pre-existing latent bug: the renderTab dispatch calls
`renderCapTests()` but the pre-S27 ct module exported only `renderTests` -
`renderCapTests` was undefined, a ReferenceError on Tests-tab click. The
new module exports BOTH names; this patcher additionally corrects the
dispatch line to `renderTests()` for cleanliness.

Three marker-bounded replacements + one dispatch-line fix:
  1. CSS block      MD-V2-TESTS-MARKER-CSS-START .. -CSS-END  (inclusive)
  2. inner module   MD-V2-TESTS-MARKER-START .. -END          (inclusive)
  3. dispatch line  renderCapTests() -> renderTests()

Payload files (must sit beside this patcher in scripts/):
  _ct_module_s27.js   - the new inner-module body (incl. both markers)
  _ct_css_s27.txt     - the new CSS block (incl. both markers)

Patcher discipline: idempotent (marker check), pre-write backup, atomic
write at END, post-write verification, payload byte-verify.

Run (Windows-side):
  cd C:\\Users\\richb\\Documents\\COWORK\\master-dashboard
  python scripts\\patch_md_v2_tests_module_s27_2026_05_14.py
"""

import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
TARGET = SCRIPT_DIR / "build_dashboard.py"
MODULE_PAYLOAD = SCRIPT_DIR / "_ct_module_s27.js"
CSS_PAYLOAD = SCRIPT_DIR / "_ct_css_s27.txt"
MARKER = "MD-V2-TESTS-S27-MARKER"

CSS_START = "/* MD-V2-TESTS-MARKER-CSS-START */"
CSS_END = "/* MD-V2-TESTS-MARKER-CSS-END */"
MOD_START = "/* MD-V2-TESTS-MARKER-START */"
MOD_END = "/* MD-V2-TESTS-MARKER-END */"

DISPATCH_OLD = '  else if(id==="tests")renderCapTests();  /* MD-V2-TESTS-MARKER */'
DISPATCH_NEW = '  else if(id==="tests")renderTests();  /* MD-V2-TESTS-MARKER MD-V2-TESTS-S27-MARKER: was renderCapTests (undefined) */'


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def _replace_block(src, start_tok, end_tok, new_block, label):
    """Replace src region from start_tok through end_tok (inclusive) with
    new_block. new_block is expected to itself begin with start_tok and end
    with end_tok. Returns new src. Exits on anchor failure."""
    i = src.find(start_tok)
    if i < 0:
        print("ERROR: %s start marker not found (%s)" % (label, start_tok))
        sys.exit(1)
    j = src.find(end_tok, i)
    if j < 0:
        print("ERROR: %s end marker not found (%s)" % (label, end_tok))
        sys.exit(1)
    j_end = j + len(end_tok)
    old_block = src[i:j_end]
    if old_block == new_block:
        print("WARNING: %s block already identical - no-op" % label)
    return src[:i] + new_block + src[j_end:]


def main():
    # -- existence checks --
    for p in (TARGET, MODULE_PAYLOAD, CSS_PAYLOAD):
        if not p.exists():
            print("ERROR: required file not found: %s" % p)
            sys.exit(1)

    src = TARGET.read_text(encoding="utf-8")

    # -- idempotency --
    if MARKER in src:
        print("SKIP: %s already present in %s - patch already applied." % (MARKER, TARGET.name))
        sys.exit(0)

    module_new = MODULE_PAYLOAD.read_text(encoding="utf-8")
    css_new = CSS_PAYLOAD.read_text(encoding="utf-8")

    # payload sanity: each must carry its own markers
    if not (module_new.lstrip().startswith(MOD_START) and MOD_END in module_new):
        print("ERROR: _ct_module_s27.js does not carry its START/END markers")
        sys.exit(1)
    if not (css_new.lstrip().startswith(CSS_START) and CSS_END in css_new):
        print("ERROR: _ct_css_s27.txt does not carry its START/END markers")
        sys.exit(1)
    if MARKER not in module_new:
        print("ERROR: _ct_module_s27.js missing the %s marker" % MARKER)
        sys.exit(1)
    # normalise: payloads may have a trailing newline; markers are what matter

    # -- locate all anchors before mutating --
    problems = []
    if CSS_START not in src or CSS_END not in src:
        problems.append("CSS markers not both present")
    if MOD_START not in src or MOD_END not in src:
        problems.append("module markers not both present")
    if DISPATCH_OLD not in src:
        problems.append("dispatch line (renderCapTests) not found verbatim")
    if problems:
        print("ERROR: anchor location failed - NOT writing:")
        for p in problems:
            print("  - %s" % p)
        sys.exit(1)

    # -- EDIT 1: CSS block --
    # strip any trailing newline from payload so we replace marker-to-marker
    css_block = css_new.rstrip("\n")
    new_src = _replace_block(src, CSS_START, CSS_END, css_block, "CSS")

    # -- EDIT 2: inner module --
    module_block = module_new.rstrip("\n")
    new_src = _replace_block(new_src, MOD_START, MOD_END, module_block, "module")

    # -- EDIT 3: dispatch line fix --
    if DISPATCH_OLD not in new_src:
        print("ERROR: dispatch line lost after block replacements")
        sys.exit(1)
    new_src = new_src.replace(DISPATCH_OLD, DISPATCH_NEW, 1)

    # -- validate the patched source compiles (it is a .py that emits HTML) --
    tmp_out = SCRIPT_DIR / "_s27_dashboard_patched.py.s27check"
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
    backup = TARGET.with_suffix(TARGET.suffix + ".bak-pre-tests-module-s27-%s" % ts)
    shutil.copy2(TARGET, backup)

    # -- atomic write at END --
    tmp_final = TARGET.with_suffix(TARGET.suffix + ".s27tmp")
    tmp_final.write_text(new_src, encoding="utf-8")
    tmp_final.replace(TARGET)

    # -- post-write verification --
    written = TARGET.read_text(encoding="utf-8")
    checks = {
        "marker present": MARKER in written,
        "4 patterns in module": written.count('"shortLabel"') >= 4 or written.count("shortLabel:") >= 4,
        "vcp_deploy_s1 key": '"vcp_deploy_s1"' in written or "vcp_deploy_s1" in written,
        "vcp_deploy_s2 key": "vcp_deploy_s2" in written,
        "4-stage info block": "ctStageInfoCell" in written and "Stage ratings" in written,
        "collapsing info col": "ctInfoCollapsingCell" in written,
        "window cell renderer": "ctWindowCell" in written,
        "renderTests exported": "window.renderTests = renderTests" in written,
        "renderCapTests aliased": "window.renderCapTests = renderTests" in written,
        "dispatch fixed": "renderTests();  /* MD-V2-TESTS-MARKER MD-V2-TESTS-S27-MARKER" in written,
        "old renderCapTests dispatch gone": 'renderCapTests();  /* MD-V2-TESTS-MARKER */' not in written,
        "CSS 4th family": ".gh-g4" in written and ".grp-start-g4" in written,
        "CSS window cells": "ct-window-fired-recent" in written and "ct-window-building" in written,
        "all 5 marker tokens intact": all(t in written for t in (CSS_START, CSS_END, MOD_START, MOD_END)),
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
        print("\n  ONE OR MORE POST-WRITE CHECKS FAILED - review before running refresh_all.")
        sys.exit(1)
    print("\n  All post-write checks passed.")


if __name__ == "__main__":
    main()
