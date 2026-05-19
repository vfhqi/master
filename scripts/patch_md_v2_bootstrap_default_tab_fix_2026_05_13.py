r"""
Patcher: MD V2 Bootstrap Default-Tab Fix (13-May-26 evening, Session 24)

Bug
---
After the SUMMARY removal patcher ran (commit ea37260), the V2 nav strip
correctly contains only Stage 1-4 buttons and `var currentTab="stage_1"`
is set in the inline data bootstrap. But on first paint, `body[data-active-tab]`
is set to `"summary"` rather than `"stage_1"`, so:
  - The `.v2-nav { display: flex }` rule (gated on body[data-active-tab^="stage_"])
    does not match → V2 nav strip is `display: none` until first manual click.
  - The `.header-tabs-row { display: none !important }` rule (same gate) does
    not match → legacy chrome strip is still visible at first paint.
  - Clicking any tab fixes it by routing through the wrapped switchTab → syncV2State.

Root cause
----------
The chrome-parity bootstrap's load-time sync uses:

  ensureV2Nav();
  syncV2State(window.currentTab || 'summary');

`currentTab` was declared with `var currentTab="stage_1"` *inside an IIFE*, so
it is function-scoped, not a global. `window.currentTab` is therefore `undefined`
at bootstrap, the `||` falls through, and `syncV2State('summary')` runs at load.

Fix
---
Replace both occurrences of `'summary'` with `'stage_1'` in the fallback —
matches the new default landing tab. Two textual occurrences (one inside the
DOMContentLoaded branch, one inside the else-branch).

Idempotent. Supports --force. Reverts via backup.

MUST run Windows-side. Refuses to run on Cowork/FUSE mount.
"""
import os, shutil, py_compile, sys
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent.resolve()
DASH_PY = SCRIPT_DIR / "build_dashboard.py"
MARKER_BYTES = b"MD-V2-BOOTSTRAP-DEFAULT-TAB-FIX-MARKER"

CRLF = b"\r\n"


def fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


def check_fuse_environment():
    here = str(SCRIPT_DIR).replace("\\", "/")
    if "/sessions/" in here or here.startswith("/tmp"):
        fail("Refusing to run from Cowork/FUSE mount.")


# Single anchor that uniquely captures BOTH occurrences via repetition.
# The DOMContentLoaded handler and the else-branch both have the same literal
# fallback string. We replace both in one pass with a regex-style two-step:
#   pass 1: rewrite the DOMContentLoaded line (anchored on its enclosing context)
#   pass 2: rewrite the else-branch line (anchored on its enclosing context)
EDITS = [
    # Edit 1 — DOMContentLoaded handler fallback
    (
        b"  if (document.readyState === 'loading') {\n"
        b"    document.addEventListener('DOMContentLoaded', function(){ ensureV2Nav(); syncV2State(window.currentTab || 'summary'); });\n"
        b"  } else {\n"
        b"    ensureV2Nav();\n"
        b"    syncV2State(window.currentTab || 'summary');\n"
        b"  }",
        b"  if (document.readyState === 'loading') {\n"
        b"    document.addEventListener('DOMContentLoaded', function(){ ensureV2Nav(); syncV2State(window.currentTab || 'stage_1'); });\n"
        b"  } else {\n"
        b"    ensureV2Nav();\n"
        b"    syncV2State(window.currentTab || 'stage_1');\n"
        b"  }",
    ),
]


def main():
    check_fuse_environment()
    print(f"[bootstrap-default-fix] working dir: {SCRIPT_DIR}")
    if not DASH_PY.exists(): fail(f"build_dashboard.py not found")
    src = DASH_PY.read_bytes()
    orig_size = len(src)
    print(f"[bootstrap-default-fix] build_dashboard.py: {orig_size} bytes")

    if MARKER_BYTES in src:
        if "--force" in sys.argv:
            baks = sorted(SCRIPT_DIR.glob("build_dashboard.py.bak-pre-md-v2-bootstrap-default-tab-fix-*"), reverse=True)
            if not baks:
                fail("No bootstrap-default-tab-fix backup found to revert from.")
            print(f"[bootstrap-default-fix] --force: reverting from {baks[0].name}")
            shutil.copy2(baks[0], DASH_PY)
            src = DASH_PY.read_bytes()
            if MARKER_BYTES in src: fail("Backup still has marker.")
        else:
            print(f"[bootstrap-default-fix] marker present - already applied. Use --force to re-apply.")
            return

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = DASH_PY.with_suffix(f".py.bak-pre-md-v2-bootstrap-default-tab-fix-{ts}")
    shutil.copy2(DASH_PY, bak)
    print(f"[bootstrap-default-fix] backup: {bak.name}")

    # Apply each edit with strict uniqueness.
    for i, (anchor, replacement) in enumerate(EDITS, 1):
        # Try LF first
        n_lf = src.count(anchor)
        # CRLF variant (line endings may differ in the file)
        anchor_crlf = anchor.replace(b'\n', b'\r\n')
        replacement_crlf = replacement.replace(b'\n', b'\r\n')
        n_crlf = src.count(anchor_crlf)

        if n_lf == 1:
            src = src.replace(anchor, replacement, 1)
            print(f"[bootstrap-default-fix]   edit {i}/{len(EDITS)}: applied (LF, 1 match)")
        elif n_crlf == 1:
            src = src.replace(anchor_crlf, replacement_crlf, 1)
            print(f"[bootstrap-default-fix]   edit {i}/{len(EDITS)}: applied (CRLF, 1 match)")
        elif n_lf == 0 and n_crlf == 0:
            fail(f"edit {i}/{len(EDITS)}: anchor count = 0 (both LF and CRLF). Anchor head: {anchor[:120]!r}")
        else:
            fail(f"edit {i}/{len(EDITS)}: ambiguous (LF={n_lf}, CRLF={n_crlf}, expected exactly 1 in one form).")

    # Plant idempotency marker as CSS comment in chrome-parity CSS-END area.
    # We anchor on the CHROME-PARITY-FOLLOWUP CSS-END marker (added by the summary
    # removal patcher).
    marker_comment = b'\n/* ' + MARKER_BYTES + b' applied ' + ts.encode() + b' */\n"""' + CRLF
    css_close_anchor = b'/* MD-V2-CHROME-PARITY-FOLLOWUP-MARKER-CSS-END */\n"""' + CRLF
    if src.count(css_close_anchor) != 1:
        # Try LF variant
        css_close_anchor_lf = b'/* MD-V2-CHROME-PARITY-FOLLOWUP-MARKER-CSS-END */\n"""\n'
        if src.count(css_close_anchor_lf) == 1:
            src = src.replace(
                css_close_anchor_lf,
                b'/* MD-V2-CHROME-PARITY-FOLLOWUP-MARKER-CSS-END */' + marker_comment.replace(CRLF, b'\n'),
                1,
            )
        else:
            fail(
                f"Could not find chrome-parity-followup close anchor to plant marker "
                f"(CRLF count={src.count(css_close_anchor)}, LF count={src.count(css_close_anchor_lf)})"
            )
    else:
        src = src.replace(
            css_close_anchor,
            b'/* MD-V2-CHROME-PARITY-FOLLOWUP-MARKER-CSS-END */' + marker_comment,
            1,
        )

    # Atomic write + py_compile check
    tmp = DASH_PY.with_suffix(f".py.tmp-{ts}")
    tmp.write_bytes(src)
    try:
        py_compile.compile(str(tmp), doraise=True)
    except py_compile.PyCompileError as e:
        tmp.unlink(missing_ok=True)
        fail(f"py_compile failed: {e}")
    os.replace(str(tmp), str(DASH_PY))
    new_size = DASH_PY.stat().st_size
    print(f"[bootstrap-default-fix] OK. New size: {new_size} bytes (delta {new_size - orig_size:+d})")
    print(f"[bootstrap-default-fix] marker count: {DASH_PY.read_bytes().count(MARKER_BYTES)}")
    print(f"[bootstrap-default-fix] DONE. Next: python scripts\\build_dashboard.py")


if __name__ == "__main__":
    main()
