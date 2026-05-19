r"""
Patcher: Pre-indicators V2-nav button (13-May-26, Session 24)

Backfill for the missing piece of the Pre-indicators tab rollout.

Background
----------
The V2 nav strip is built by ensureV2Nav() inside the chrome-parity JS bootstrap
inside build_dashboard.py's CHROME_PARITY_JS raw string. It currently shows
dead <span class="v2-nav-placeholder"> elements for Pre-indicators /
Post-indicators / Setups / Tests / Master Overview.

The original Pre-indicators patcher updated the (dead) OLD_TABS registry, but
the V2 nav strip doesn't read that list - it's hand-written inline. So the new
Pre-indicators tab is fully wired in renderTab dispatch + IMPLEMENTED_TABS, but
the nav strip has no clickable entry for it.

This patcher swaps the Pre-indicators placeholder for a real button.

Same surgery pattern will work for Post-indicators / Setups / Tests / Master
Overview in their respective T2-T5 patchers (each gets its own swap line).

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


ANCHOR_LF = b"      + '<span class=\"v2-nav-placeholder\" title=\"Coming soon\">Pre-indicators</span>'\n"
REPLACE_LF = b"      + '<button class=\"v2-nav-btn\" data-v2-tab=\"pre_indicators\" onclick=\"switchTab(\\'pre_indicators\\')\">Pre-indicators</button>'\n"
ANCHOR_CRLF  = ANCHOR_LF.replace(b'\n', b'\r\n')
REPLACE_CRLF = REPLACE_LF.replace(b'\n', b'\r\n')


def main():
    check_fuse_environment()
    print(f"[pi-nav-button] working dir: {SCRIPT_DIR}")
    if not DASH_PY.exists(): fail("build_dashboard.py not found")
    src = DASH_PY.read_bytes()
    orig_size = len(src)
    print(f"[pi-nav-button] build_dashboard.py: {orig_size} bytes")

    n_lf = src.count(ANCHOR_LF)
    n_crlf = src.count(ANCHOR_CRLF)

    if n_lf == 0 and n_crlf == 0:
        # Already applied or shape drifted
        has_button = b'data-v2-tab="pre_indicators"' in src
        print(f"[pi-nav-button] anchor not found (LF=0, CRLF=0).")
        print(f"[pi-nav-button] data-v2-tab=\"pre_indicators\" present: {has_button}")
        if has_button:
            print(f"[pi-nav-button] LOOKS already applied. Exiting clean.")
            return
        fail("Anchor not found AND no pre_indicators button present. Inspect manually.")

    if n_lf > 1 or n_crlf > 1:
        fail(f"Anchor ambiguous (LF={n_lf}, CRLF={n_crlf}).")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = DASH_PY.with_suffix(f".py.bak-pre-pi-nav-button-{ts}")
    shutil.copy2(DASH_PY, bak)
    print(f"[pi-nav-button] backup: {bak.name}")

    if n_lf == 1:
        src = src.replace(ANCHOR_LF, REPLACE_LF, 1)
        print(f"[pi-nav-button]   edit applied (LF, 1 match)")
    else:
        src = src.replace(ANCHOR_CRLF, REPLACE_CRLF, 1)
        print(f"[pi-nav-button]   edit applied (CRLF, 1 match)")

    tmp = DASH_PY.with_suffix(f".py.tmp-{ts}")
    tmp.write_bytes(src)
    try:
        py_compile.compile(str(tmp), doraise=True)
    except py_compile.PyCompileError as e:
        tmp.unlink(missing_ok=True)
        fail(f"py_compile failed: {e}")
    os.replace(str(tmp), str(DASH_PY))
    new_size = DASH_PY.stat().st_size
    print(f"[pi-nav-button] OK. New size: {new_size} bytes (delta {new_size - orig_size:+d})")

    # Post-write verification
    final = DASH_PY.read_bytes()
    has_button = b'data-v2-tab="pre_indicators"' in final
    has_placeholder = b'v2-nav-placeholder" title="Coming soon">Pre-indicators' in final
    print(f"[pi-nav-button] post-write button present     : {has_button}")
    print(f"[pi-nav-button] post-write placeholder removed: {not has_placeholder}")
    if not has_button or has_placeholder:
        print(f"[pi-nav-button] WARN: state mismatch. Inspect.")
    print(f"[pi-nav-button] DONE. Next: python scripts\\build_dashboard.py")


if __name__ == "__main__":
    main()
