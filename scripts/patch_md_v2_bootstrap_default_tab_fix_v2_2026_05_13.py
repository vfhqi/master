r"""
Patcher v2: MD V2 Bootstrap Default-Tab Fix (13-May-26 PM, Session 24, retry)

Why a v2
--------
v1 (patch_md_v2_bootstrap_default_tab_fix_2026_05_13.py) successfully applied
its edit IN MEMORY but then failed at the marker-plant step (anchor mismatch
on the chrome-parity-followup CSS-END marker, because the SUMMARY removal
patcher had already mutated that line by appending its own idempotency comment
inline). Because v1 used atomic os.replace AT THE END after marker-plant, the
sys.exit(1) on marker failure threw away the in-memory fix. Net: build_dashboard.py
still has the broken fallback, and the live HTML confirms it.

This v2 patcher:
  - Drops the marker-plant step entirely
  - Uses anchor-disappearance as natural idempotency (once the anchor is replaced,
    re-running fails fast with anchor-count=0)
  - Anchors on the verbatim if/else block as seen in the live HTML

Single edit. Atomic write. py_compile gate before commit.

MUST run Windows-side. Refuses to run on Cowork/FUSE mount.
"""
import os, shutil, py_compile, sys
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent.resolve()
DASH_PY = SCRIPT_DIR / "build_dashboard.py"

CRLF = b"\r\n"


def fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


def check_fuse_environment():
    here = str(SCRIPT_DIR).replace("\\", "/")
    if "/sessions/" in here or here.startswith("/tmp"):
        fail("Refusing to run from Cowork/FUSE mount.")


# Verbatim from live HTML at https://vfhqi.github.io/master/index.html
# Both branches use the same anchor in one block.
ANCHOR_LF = (
    b"  if (document.readyState === 'loading') {\n"
    b"    document.addEventListener('DOMContentLoaded', function(){ ensureV2Nav(); syncV2State(window.currentTab || 'summary'); });\n"
    b"  } else {\n"
    b"    ensureV2Nav();\n"
    b"    syncV2State(window.currentTab || 'summary');\n"
    b"  }"
)
REPLACE_LF = (
    b"  if (document.readyState === 'loading') {\n"
    b"    document.addEventListener('DOMContentLoaded', function(){ ensureV2Nav(); syncV2State(window.currentTab || 'stage_1'); });\n"
    b"  } else {\n"
    b"    ensureV2Nav();\n"
    b"    syncV2State(window.currentTab || 'stage_1');\n"
    b"  }"
)
ANCHOR_CRLF  = ANCHOR_LF.replace(b'\n', b'\r\n')
REPLACE_CRLF = REPLACE_LF.replace(b'\n', b'\r\n')


def main():
    check_fuse_environment()
    print(f"[bootstrap-default-fix-v2] working dir: {SCRIPT_DIR}")
    if not DASH_PY.exists(): fail("build_dashboard.py not found")
    src = DASH_PY.read_bytes()
    orig_size = len(src)
    print(f"[bootstrap-default-fix-v2] build_dashboard.py: {orig_size} bytes")

    # Idempotency check via anchor presence
    n_lf = src.count(ANCHOR_LF)
    n_crlf = src.count(ANCHOR_CRLF)
    if n_lf == 0 and n_crlf == 0:
        # Either already applied OR the file shape has drifted further.
        # Confirm by counting the "summary" fallback substring.
        residual_summary = src.count(b"window.currentTab || 'summary'")
        residual_stage1  = src.count(b"window.currentTab || 'stage_1'")
        print(f"[bootstrap-default-fix-v2] anchor not found (LF=0, CRLF=0).")
        print(f"[bootstrap-default-fix-v2] residual 'summary' fallbacks: {residual_summary}")
        print(f"[bootstrap-default-fix-v2] residual 'stage_1' fallbacks: {residual_stage1}")
        if residual_summary == 0 and residual_stage1 >= 1:
            print(f"[bootstrap-default-fix-v2] LOOKS already applied. Exiting clean.")
            return
        fail("Anchor not found AND file does not look already-applied. Inspect manually.")

    if n_lf > 1 or n_crlf > 1:
        fail(f"Anchor ambiguous (LF={n_lf}, CRLF={n_crlf}). Expected at most 1 in each form.")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = DASH_PY.with_suffix(f".py.bak-pre-md-v2-bootstrap-default-tab-fix-v2-{ts}")
    shutil.copy2(DASH_PY, bak)
    print(f"[bootstrap-default-fix-v2] backup: {bak.name}")

    if n_lf == 1:
        src = src.replace(ANCHOR_LF, REPLACE_LF, 1)
        print(f"[bootstrap-default-fix-v2]   edit applied (LF, 1 match)")
    else:
        src = src.replace(ANCHOR_CRLF, REPLACE_CRLF, 1)
        print(f"[bootstrap-default-fix-v2]   edit applied (CRLF, 1 match)")

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
    print(f"[bootstrap-default-fix-v2] OK. New size: {new_size} bytes (delta {new_size - orig_size:+d})")

    # Post-write verification
    final = DASH_PY.read_bytes()
    residual_summary = final.count(b"window.currentTab || 'summary'")
    residual_stage1  = final.count(b"window.currentTab || 'stage_1'")
    print(f"[bootstrap-default-fix-v2] post-write 'summary' fallbacks: {residual_summary}")
    print(f"[bootstrap-default-fix-v2] post-write 'stage_1' fallbacks: {residual_stage1}")
    if residual_summary != 0 or residual_stage1 != 2:
        print(f"[bootstrap-default-fix-v2] WARN: expected 0 summary + 2 stage_1, got {residual_summary} + {residual_stage1}. Inspect.")
    print(f"[bootstrap-default-fix-v2] DONE. Next: python scripts\\build_dashboard.py")


if __name__ == "__main__":
    main()
