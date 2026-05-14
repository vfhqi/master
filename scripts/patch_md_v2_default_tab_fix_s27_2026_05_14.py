#!/usr/bin/env python3
"""
patch_md_v2_default_tab_fix_s27_2026_05_14.py
=============================================
SESSION 27 FOLLOW-UP FIX - Master Overview default-tab bootstrap miss.

Targets: scripts/build_dashboard.py

BUG (found by Chrome-MCP verification of the deployed becc2ed build):
The page-load bootstrap renders the Stage 1 tab, not Master Overview, even
though Master Overview is meant to be the default landing tab. Body attribute
gets set to master_overview but the content shown is Stage 1.

ROOT CAUSE:
The Master Overview patcher's EDIT 6 changed `window.currentTab || 'stage_1'`
in two places (the V2 nav sync, ~lines 8490/8493). But the ACTUAL default the
bootstrap renders from is a DIFFERENT string - the `currentTab` variable
DECLARATION at ~line 1673:
    var currentTab="stage_1",currentSort={...}; /* SUMMARY-TAB-DEFAULT */
The `__chgBoot` bootstrap reads that variable and calls switchTab(currentTab).
EDIT 6's anchor never matched this line, so currentTab stayed "stage_1".

FIX:
One change - the `currentTab` initialiser on the SUMMARY-TAB-DEFAULT line:
    currentTab="stage_1"  ->  currentTab="master_overview"
Anchored on the full unique line (the `/* SUMMARY-TAB-DEFAULT */` marker
comment makes it unambiguous; the anchor string appears exactly once).

Everything else in the Session 27 build verified working on the deployed
build - this is the only defect found. Idempotent, pre-write backup, atomic
write, post-write verification, encoding="utf-8" throughout (no /tmp paths).

Run (Windows-side):
  cd C:\\Users\\richb\\Documents\\COWORK\\master-dashboard
  python scripts\\patch_md_v2_default_tab_fix_s27_2026_05_14.py
  python scripts\\build_dashboard.py
  git add -A
  git commit -m "fix(MD V2): Session 27 - default landing tab bootstrap (was rendering Stage 1, now Master Overview)"
  git push
"""

import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
TARGET = SCRIPT_DIR / "build_dashboard.py"
MARKER = "MD-V2-DEFAULT-TAB-FIX-S27-MARKER"

# Anchor on the FULL line - the SUMMARY-TAB-DEFAULT marker comment makes it
# unique and stable. Change only the currentTab initialiser; keep currentSort
# and the marker comment intact, and append our own marker so the patch is
# idempotent.
ANCHOR = 'var currentTab="stage_1",currentSort={col:"chg_qual_count",dir:"desc"}; /* SUMMARY-TAB-DEFAULT */'
REPLACEMENT = 'var currentTab="master_overview",currentSort={col:"chg_qual_count",dir:"desc"}; /* SUMMARY-TAB-DEFAULT MD-V2-DEFAULT-TAB-FIX-S27-MARKER: was stage_1, Master Overview is the default landing tab */'


def md5(p):
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def main():
    if not TARGET.exists():
        print("ERROR: target not found: %s" % TARGET)
        sys.exit(1)

    src = TARGET.read_text(encoding="utf-8")

    # idempotency
    if MARKER in src:
        print("SKIP: %s already present - patch already applied." % MARKER)
        sys.exit(0)

    # locate the anchor - must appear exactly once
    n = src.count(ANCHOR)
    if n != 1:
        print("ERROR: anchor found %d times (expected exactly 1) - NOT writing." % n)
        print("  anchor: %s" % ANCHOR)
        sys.exit(1)

    new_src = src.replace(ANCHOR, REPLACEMENT, 1)

    # validate compile (temp file beside the patcher, cleaned up after)
    tmp_out = SCRIPT_DIR / "_s27_defaulttab_patched.py.s27check"
    tmp_out.write_text(new_src, encoding="utf-8")
    import py_compile
    try:
        py_compile.compile(str(tmp_out), doraise=True)
    except py_compile.PyCompileError as e:
        print("ERROR: patched build_dashboard.py fails py_compile:\n%s" % e)
        sys.exit(1)
    finally:
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
    backup = TARGET.with_suffix(TARGET.suffix + ".bak-pre-default-tab-fix-s27-%s" % ts)
    shutil.copy2(TARGET, backup)

    # atomic write
    tmp_final = TARGET.with_suffix(TARGET.suffix + ".dtftmp")
    tmp_final.write_text(new_src, encoding="utf-8")
    tmp_final.replace(TARGET)

    # post-write verification
    written = TARGET.read_text(encoding="utf-8")
    checks = {
        "marker present": MARKER in written,
        "currentTab now master_overview": 'var currentTab="master_overview"' in written,
        "old stage_1 default gone": 'var currentTab="stage_1"' not in written,
        "currentSort preserved": 'currentSort={col:"chg_qual_count",dir:"desc"}' in written,
        "SUMMARY-TAB-DEFAULT marker preserved": "SUMMARY-TAB-DEFAULT" in written,
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
