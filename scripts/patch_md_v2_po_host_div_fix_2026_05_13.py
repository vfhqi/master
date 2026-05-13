r"""
Patcher: Add Post-indicators to OLD_TABS list (13-May-26, Session 24 continuation)

Fix for missing post-indicators tab host div. The OLD_TABS registry in
build_dashboard.py drives emission of <div id="tab-XXX"> host divs in the
compiled HTML. The earlier bundled patcher skipped this edit thinking the
list was dead - it isn't.

Single-edit, no marker plant.

MUST run Windows-side.
"""
import os, shutil, py_compile, sys
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent.resolve()
DASH_PY = SCRIPT_DIR / "build_dashboard.py"

CRLF = b"\r\n"


def fail(msg):
    print("FAIL: " + msg)
    sys.exit(1)


def check_fuse_environment():
    here = str(SCRIPT_DIR).replace("\\", "/")
    if "/sessions/" in here or here.startswith("/tmp"):
        fail("Refusing to run from Cowork/FUSE mount.")


ANCHOR_LF = (
    b'    # MD-V2-PRE-INDICATORS-MARKER - Pre-indicators (3 leading binary patterns)\n'
    b'    {"id": "pre_indicators", "label": "Pre-indicators", "accent": "#0F6E56"},\n'
)
REPLACE_LF = (
    b'    # MD-V2-PRE-INDICATORS-MARKER - Pre-indicators (3 leading binary patterns)\n'
    b'    {"id": "pre_indicators", "label": "Pre-indicators", "accent": "#0F6E56"},\n'
    b'    # MD-V2-POST-INDICATORS-MARKER - Post-indicators (5 trailing binary patterns)\n'
    b'    {"id": "post_indicators", "label": "Post-indicators", "accent": "#A32D2D"},\n'
)


def main():
    check_fuse_environment()
    print("[po-host-div-fix] working dir: " + str(SCRIPT_DIR))
    if not DASH_PY.exists(): fail("build_dashboard.py not found")
    src = DASH_PY.read_bytes()
    orig_size = len(src)
    print("[po-host-div-fix] build_dashboard.py: " + str(orig_size) + " bytes")

    a_crlf = ANCHOR_LF.replace(b'\n', b'\r\n').replace(b'\r\r\n', b'\r\n')
    r_crlf = REPLACE_LF.replace(b'\n', b'\r\n').replace(b'\r\r\n', b'\r\n')
    n_lf = src.count(ANCHOR_LF)
    n_crlf = src.count(a_crlf)
    if n_lf == 0 and n_crlf == 0:
        # Already applied?
        if b'"id": "post_indicators"' in src:
            print("[po-host-div-fix] LOOKS already applied. Exiting clean.")
            return
        fail("Anchor not found AND no post_indicators entry. Inspect manually.")
    if n_lf > 1 or n_crlf > 1:
        fail("Anchor ambiguous (LF=" + str(n_lf) + ", CRLF=" + str(n_crlf) + ").")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = DASH_PY.with_suffix(".py.bak-pre-po-host-div-fix-" + ts)
    shutil.copy2(DASH_PY, bak)
    print("[po-host-div-fix] backup: " + bak.name)

    if n_lf == 1:
        src = src.replace(ANCHOR_LF, REPLACE_LF, 1)
        print("[po-host-div-fix]   edit applied (LF, 1 match)")
    else:
        src = src.replace(a_crlf, r_crlf, 1)
        print("[po-host-div-fix]   edit applied (CRLF, 1 match)")

    tmp = DASH_PY.with_suffix(".py.tmp-" + ts)
    tmp.write_bytes(src)
    try:
        py_compile.compile(str(tmp), doraise=True)
    except py_compile.PyCompileError as e:
        tmp.unlink(missing_ok=True)
        fail("py_compile failed: " + str(e))
    os.replace(str(tmp), str(DASH_PY))
    new_size = DASH_PY.stat().st_size
    print("[po-host-div-fix] OK. New size: " + str(new_size) + " bytes (delta " + str(new_size - orig_size) + ")")

    final = DASH_PY.read_bytes()
    print('[po-host-div-fix] PO entry in OLD_TABS: ' + str(b'"id": "post_indicators"' in final))
    print("[po-host-div-fix] DONE. Next: python scripts\\build_dashboard.py")


if __name__ == "__main__":
    main()
