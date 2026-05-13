r"""
Patcher: MD V2 Remove SUMMARY tab (13-May-26 evening, Session 23 close)

SUMMARY was a yesterday artefact, not part of the MD V2 project. This patcher
fully removes it:
  1. Drops the SUMMARY button from the V2 nav strip
  2. Removes the body[data-active-tab="summary"] selectors from chrome-parity CSS
  3. Removes the SUMMARY case from renderTab dispatch (if reachable)
  4. Flips the default landing tab from "summary" to "stage_1"
  5. Removes "summary" from IMPLEMENTED_TABS

The renderSummary function and #tab-summary div itself stay in place (unreachable
zombie code) - they will be cleaned up wholesale when legacy chrome is retired
post-cutover. Removing them surgically here is high-risk for low gain.

MUST run Windows-side. Idempotent. Supports --force.
"""
import os, shutil, py_compile, sys
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent.resolve()
DASH_PY = SCRIPT_DIR / "build_dashboard.py"
MARKER_BYTES = b"MD-V2-REMOVE-SUMMARY-MARKER"

CRLF = b"\r\n"


def fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


def check_fuse_environment():
    here = str(SCRIPT_DIR).replace("\\", "/")
    if "/sessions/" in here or here.startswith("/tmp"):
        fail("Refusing to run from Cowork/FUSE mount.")


# Each (anchor, replacement) pair is one surgical edit.
# All anchors must be unique in the file. Any miss is a fatal.
EDITS = [
    # 1. Strip SUMMARY button from V2 nav HTML (inside JS_BOOTSTRAP)
    (
        b"      + '<span class=\"v2-nav-label\">MD V2</span>'\n"
        b"      + '<button class=\"v2-nav-btn\" data-v2-tab=\"summary\" onclick=\"switchTab(\\'summary\\')\">SUMMARY</button>'\n"
        b"      + '<button class=\"v2-nav-btn\" data-v2-tab=\"stage_1\"",
        b"      + '<span class=\"v2-nav-label\">MD V2</span>'\n"
        b"      + '<button class=\"v2-nav-btn\" data-v2-tab=\"stage_1\"",
    ),
    # 2. Strip body[data-active-tab="summary"] from chrome-parity hide rule
    (
        b'body[data-active-tab="summary"] .header-tabs-row,\n'
        b'body[data-active-tab^="stage_"] .header-tabs-row { display: none !important; }',
        b'body[data-active-tab^="stage_"] .header-tabs-row { display: none !important; }',
    ),
    # 3. Strip body[data-active-tab="summary"] from chrome-parity show rule for .v2-nav
    (
        b'body[data-active-tab="summary"] .v2-nav,\n'
        b'body[data-active-tab^="stage_"] .v2-nav { display: flex; }',
        b'body[data-active-tab^="stage_"] .v2-nav { display: flex; }',
    ),
    # 4. Strip body[data-active-tab="summary"] from chrome-parity FOLLOWUP hide rule
    (
        b'body[data-active-tab="summary"] .header-controls-row,\n'
        b'body[data-active-tab^="stage_"] .header-controls-row { display: none !important; }',
        b'body[data-active-tab^="stage_"] .header-controls-row { display: none !important; }',
    ),
    # 5. Flip default landing tab from summary to stage_1
    (
        b'var currentTab="summary"',
        b'var currentTab="stage_1"',
    ),
    # 6. Remove "summary" entry from IMPLEMENTED_TABS
    (
        b'IMPLEMENTED_TABS = [\r\n'
        b'    "summary",\r\n'
        b'    "stage_1",  # MD-V2-STAGE1-MARKER\r\n',
        b'IMPLEMENTED_TABS = [\r\n'
        b'    "stage_1",  # MD-V2-STAGE1-MARKER\r\n',
    ),
]


def main():
    check_fuse_environment()
    print(f"[remove-summary-patch] working dir: {SCRIPT_DIR}")
    if not DASH_PY.exists(): fail(f"build_dashboard.py not found")
    src = DASH_PY.read_bytes()
    orig_size = len(src)
    print(f"[remove-summary-patch] build_dashboard.py: {orig_size} bytes")

    if MARKER_BYTES in src:
        if "--force" in sys.argv:
            baks = sorted(SCRIPT_DIR.glob("build_dashboard.py.bak-pre-md-v2-remove-summary-*"), reverse=True)
            if not baks:
                fail("No remove-summary backup found to revert from.")
            print(f"[remove-summary-patch] --force: reverting from {baks[0].name}")
            shutil.copy2(baks[0], DASH_PY)
            src = DASH_PY.read_bytes()
            if MARKER_BYTES in src: fail("Backup still has marker.")
        else:
            print(f"[remove-summary-patch] marker present - already applied. Use --force to re-apply.")
            return

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = DASH_PY.with_suffix(f".py.bak-pre-md-v2-remove-summary-{ts}")
    shutil.copy2(DASH_PY, bak)
    print(f"[remove-summary-patch] backup: {bak.name}")

    # Apply each edit, with strict uniqueness checks.
    for i, (anchor, replacement) in enumerate(EDITS, 1):
        n_lf = src.count(anchor)
        # Try with CRLF variant too in case the file's line endings differ
        anchor_lf = anchor.replace(b'\r\n', b'\n')
        anchor_crlf = anchor.replace(b'\n', b'\r\n').replace(b'\r\r\n', b'\r\n')
        n_native = src.count(anchor_lf) + (src.count(anchor_crlf) if anchor != anchor_crlf else 0)
        if n_lf == 1:
            src = src.replace(anchor, replacement, 1)
            print(f"[remove-summary-patch]   edit {i}/{len(EDITS)}: applied (1 match)")
        elif n_lf == 0:
            # Try LF-only variant
            if src.count(anchor_lf) == 1 and anchor_lf != anchor:
                src = src.replace(anchor_lf, replacement.replace(b'\r\n', b'\n'), 1)
                print(f"[remove-summary-patch]   edit {i}/{len(EDITS)}: applied (LF variant, 1 match)")
            else:
                fail(f"edit {i}/{len(EDITS)}: anchor count = 0 (also tried LF variant: {src.count(anchor_lf)}). Anchor head: {anchor[:80]!r}")
        else:
            fail(f"edit {i}/{len(EDITS)}: anchor count = {n_lf} (expected 1).")

    # Add idempotency marker as a CSS comment so future runs detect it without breaking anything
    marker_comment = b'\n/* ' + MARKER_BYTES + b' applied ' + ts.encode() + b' */\n"""\r\n'
    css_close_anchor = b'/* MD-V2-CHROME-PARITY-FOLLOWUP-MARKER-CSS-END */\n"""' + CRLF
    if src.count(css_close_anchor) != 1:
        fail(f"Could not find chrome-parity-followup close anchor to plant marker (count={src.count(css_close_anchor)})")
    src = src.replace(
        css_close_anchor,
        b'/* MD-V2-CHROME-PARITY-FOLLOWUP-MARKER-CSS-END */' + marker_comment,
        1,
    )

    tmp = DASH_PY.with_suffix(f".py.tmp-{ts}")
    tmp.write_bytes(src)
    try:
        py_compile.compile(str(tmp), doraise=True)
    except py_compile.PyCompileError as e:
        tmp.unlink(missing_ok=True)
        fail(f"py_compile failed: {e}")
    os.replace(str(tmp), str(DASH_PY))
    new_size = DASH_PY.stat().st_size
    print(f"[remove-summary-patch] OK. New size: {new_size} bytes (delta {new_size - orig_size:+d})")
    print(f"[remove-summary-patch] marker count: {DASH_PY.read_bytes().count(MARKER_BYTES)}")
    print(f"[remove-summary-patch] DONE. Next: python scripts\\build_dashboard.py")


if __name__ == "__main__":
    main()
