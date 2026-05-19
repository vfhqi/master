r"""
Patcher: MD V2 Chrome Parity FOLLOWUP (13-May-26 evening)

Initial chrome-parity patch missed the .header-controls-row (#3 TOGGLES /
#4 FILTERS bar). This patch extends the suppression CSS to hide BOTH
.header-tabs-row AND .header-controls-row on V2 tabs.

MUST run Windows-side. Idempotent. Supports --force.
"""
import os, shutil, py_compile, sys
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent.resolve()
DASH_PY = SCRIPT_DIR / "build_dashboard.py"
MARKER_BYTES = b"MD-V2-CHROME-PARITY-FOLLOWUP-MARKER"

CRLF = b"\r\n"


def fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


def check_fuse_environment():
    here = str(SCRIPT_DIR).replace("\\", "/")
    if "/sessions/" in here or here.startswith("/tmp"):
        fail("Refusing to run from Cowork/FUSE mount.")


FOLLOWUP_CSS = b'''
/* MD-V2-CHROME-PARITY-FOLLOWUP-MARKER-CSS-START */
/* Extend chrome suppression: also hide .header-controls-row (the #3 Toggles / #4 Filters row)
   on every V2 tab. The initial patch missed this row. */
body[data-active-tab="summary"] .header-controls-row,
body[data-active-tab^="stage_"] .header-controls-row { display: none !important; }
/* MD-V2-CHROME-PARITY-FOLLOWUP-MARKER-CSS-END */
'''

ANCHOR_CSS_END = b'/* MD-V2-CHROME-PARITY-MARKER-CSS-END */\n"""' + CRLF


def main():
    check_fuse_environment()
    print(f"[chrome-parity-followup-patch] working dir: {SCRIPT_DIR}")
    if not DASH_PY.exists(): fail(f"build_dashboard.py not found")
    src = DASH_PY.read_bytes()
    print(f"[chrome-parity-followup-patch] build_dashboard.py: {len(src)} bytes")

    if MARKER_BYTES in src:
        if "--force" in sys.argv:
            baks = sorted(SCRIPT_DIR.glob("build_dashboard.py.bak-pre-md-v2-chrome-parity-followup-*"), reverse=True)
            if not baks:
                fail("No followup backup found to revert from.")
            print(f"[chrome-parity-followup-patch] --force: reverting from {baks[0].name}")
            shutil.copy2(baks[0], DASH_PY)
            src = DASH_PY.read_bytes()
            if MARKER_BYTES in src: fail("Backup still has marker.")
        else:
            print(f"[chrome-parity-followup-patch] marker present - already applied. Use --force to re-apply.")
            return

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = DASH_PY.with_suffix(f".py.bak-pre-md-v2-chrome-parity-followup-{ts}")
    shutil.copy2(DASH_PY, bak)
    print(f"[chrome-parity-followup-patch] backup: {bak.name}")

    if src.count(ANCHOR_CSS_END) != 1:
        fail(f"Anchor count = {src.count(ANCHOR_CSS_END)} (expected 1). Did chrome-parity patcher run first?")

    css_prefix = b'/* MD-V2-CHROME-PARITY-MARKER-CSS-END */\n'
    css_suffix = b'"""' + CRLF
    css_repl = css_prefix + FOLLOWUP_CSS + css_suffix
    src = src.replace(ANCHOR_CSS_END, css_repl, 1)

    tmp = DASH_PY.with_suffix(f".py.tmp-{ts}")
    tmp.write_bytes(src)
    try:
        py_compile.compile(str(tmp), doraise=True)
    except py_compile.PyCompileError as e:
        tmp.unlink(missing_ok=True)
        fail(f"py_compile failed: {e}")
    os.replace(str(tmp), str(DASH_PY))
    print(f"[chrome-parity-followup-patch] OK. New size: {DASH_PY.stat().st_size} bytes")
    print(f"[chrome-parity-followup-patch] marker count: {DASH_PY.read_bytes().count(MARKER_BYTES)}")
    print(f"[chrome-parity-followup-patch] DONE. Next: python scripts\\build_dashboard.py")


if __name__ == "__main__":
    main()
