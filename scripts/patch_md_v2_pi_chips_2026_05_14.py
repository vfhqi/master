#!/usr/bin/env python3
# =============================================================================
# patch_md_v2_pi_chips_2026_05_14.py
# -----------------------------------------------------------------------------
# Adds the rating-tier multi-select chip filter (D-MD-V2-59) to the Pre-test
# indicators tab. Edits build_dashboard.py only.
#
#   EDIT 1 - replace the Pre-test indicators JS module block (marker-delimited)
#   EDIT 2 - replace the Pre-test indicators CSS block (marker-delimited)
#
# Payload files (must sit alongside this patcher in scripts/):
#   _pi_v3_module.js  - PI module with the chip filter
#   _pi_v3_css.txt    - PI CSS with chip styling
#
# Scope note: chip filter applies to the 3 Pre-test indicator patterns only.
# The other indicator/setup/test tabs get it as part of their own rebuilds
# (the rating ladder and the chip filter land together, tab by tab).
#
# Discipline (D-MD-V2-43): heredoc -> /tmp -> atomic cp -> MD5 byte-verify.
# Idempotent (marker check), pre-write backup, atomic write at END, post-write
# verification. Edit tool BANNED on build_dashboard.py.
# =============================================================================
import sys, os, shutil, py_compile, tempfile
from datetime import datetime

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(SCRIPTS_DIR, "build_dashboard.py")
MODULE_PAYLOAD = os.path.join(SCRIPTS_DIR, "_pi_v3_module.js")
CSS_PAYLOAD = os.path.join(SCRIPTS_DIR, "_pi_v3_css.txt")
MARKER = "MD-V2-PI-CHIPS-S25-MARKER"

def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def main():
    for pth in (TARGET, MODULE_PAYLOAD, CSS_PAYLOAD):
        if not os.path.exists(pth):
            print("ERROR: required file not found: %s" % pth); sys.exit(1)

    src = read(TARGET)
    pi_module = read(MODULE_PAYLOAD).rstrip("\n")
    pi_css = read(CSS_PAYLOAD).rstrip("\n")

    if MARKER in src:
        print("IDEMPOTENT: %s already present. No-op." % MARKER)
        sys.exit(0)

    orig_len = len(src)

    # -------------------------------------------------------------------------
    # EDIT 1 - replace the PI JS module block. The module sits between
    # MARKER-START and MARKER-END. The MODULE-START/END wrappers stay; we
    # replace everything from the inner START to the inner END inclusive.
    # -------------------------------------------------------------------------
    m_start = "/* MD-V2-PRE-INDICATORS-MARKER-START */"
    m_end = "/* MD-V2-PRE-INDICATORS-MARKER-END */"
    i0 = src.find(m_start)
    i1 = src.find(m_end)
    if i0 == -1 or i1 == -1 or i1 < i0:
        print("ERROR: EDIT 1 - PI module marker block not found or malformed."); sys.exit(1)
    i1_end = i1 + len(m_end)
    # payload itself begins with m_start and ends with m_end
    if not pi_module.startswith(m_start) or not pi_module.rstrip().endswith(m_end):
        print("ERROR: EDIT 1 - module payload missing inner START/END markers."); sys.exit(1)
    src = src[:i0] + pi_module + src[i1_end:]

    # -------------------------------------------------------------------------
    # EDIT 2 - replace the PI CSS block (marker-delimited, inclusive).
    # -------------------------------------------------------------------------
    css_start = "/* MD-V2-PRE-INDICATORS-MARKER-CSS-START */"
    css_end = "/* MD-V2-PRE-INDICATORS-MARKER-CSS-END */"
    j0 = src.find(css_start)
    j1 = src.find(css_end)
    if j0 == -1 or j1 == -1 or j1 < j0:
        print("ERROR: EDIT 2 - PI CSS marker block not found or malformed."); sys.exit(1)
    j1_end = j1 + len(css_end)
    if not pi_css.startswith(css_start) or not pi_css.rstrip().endswith(css_end):
        print("ERROR: EDIT 2 - CSS payload missing START/END markers."); sys.exit(1)
    src = src[:j0] + pi_css + src[j1_end:]

    # -------------------------------------------------------------------------
    # Validate, pre-write backup, atomic write, post-write verify.
    # -------------------------------------------------------------------------
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".py", prefix="bd_chips_")
    os.close(tmp_fd)
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(src)
    try:
        py_compile.compile(tmp_path, doraise=True)
    except py_compile.PyCompileError as e:
        print("ERROR: patched build_dashboard.py fails py_compile:\n%s" % e)
        os.unlink(tmp_path); sys.exit(1)
    if b"\x00" in src.encode("utf-8"):
        print("ERROR: null bytes detected - aborting.")
        os.unlink(tmp_path); sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = TARGET + ".bak-pre-md-v2-pi-chips-s25-" + ts
    shutil.copy2(TARGET, backup)
    print("Pre-write backup: %s" % backup)

    shutil.copy2(tmp_path, TARGET)
    os.unlink(tmp_path)

    new_len = len(src)
    print("OK: build_dashboard.py patched.")
    print("    %d bytes -> %d bytes (delta %+d)" % (orig_len, new_len, new_len - orig_len))
    print("    marker: %s" % MARKER)

    check = read(TARGET)
    if MARKER not in check:
        print("ERROR: post-write verification failed - marker missing!"); sys.exit(1)
    checks = [
        ("EDIT 1 module chip filter", "piToggleTier"),
        ("EDIT 1 module chip filter", "piSelectAllTiers"),
        ("EDIT 1 module chip filter", "tierFilter"),
        ("EDIT 1 module chip filter", "piApplyTierFilter"),
        ("EDIT 2 CSS chip styling", "pi-tier-chip"),
        ("EDIT 2 CSS chip styling", "pi-chip-collapsing"),
    ]
    for name, token in checks:
        if token not in check:
            print("ERROR: post-write verification - %s missing token '%s'" % (name, token)); sys.exit(1)
    for m in ("MD-V2-PRE-INDICATORS-MARKER-CSS-START", "MD-V2-PRE-INDICATORS-MARKER-CSS-END",
              "MD-V2-PRE-INDICATORS-MARKER-MODULE-START", "MD-V2-PRE-INDICATORS-MARKER-MODULE-END",
              "MD-V2-PRE-INDICATORS-MARKER-START", "MD-V2-PRE-INDICATORS-MARKER-END"):
        if check.count(m) != 1:
            print("ERROR: post-write verification - marker '%s' count = %d (expected 1)" % (m, check.count(m))); sys.exit(1)
    print("Post-write verification: PASS (marker + both edits + 6 marker-blocks intact).")

if __name__ == "__main__":
    main()
