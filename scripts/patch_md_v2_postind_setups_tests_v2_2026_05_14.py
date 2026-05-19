#!/usr/bin/env python3
# =============================================================================
# patch_md_v2_postind_setups_tests_v2_2026_05_14.py
# -----------------------------------------------------------------------------
# Session 26 (14-May-26). Rebuilds the Post-test indicators, Capital
# qualification setups, and Capital deployment tests tab modules + CSS to full
# Pre-test-indicators parity (test columns, per-pattern rating + score,
# rating-tier multi-select chip filter, super-group banding where applicable,
# pass-count breakdown). Edits build_dashboard.py only.
# Locked decisions D-MD-V2-60, -62, -63 (display); D-MD-V2-61 is in the
# companion pipeline patcher patch_md_v2_screens_s26_2026_05_14.py.
#
#   6 edits - 3 module blocks + 3 CSS blocks, all marker-delimited.
#
# Payload files (must sit alongside this patcher in scripts/):
#   _po_v2_module.js / _po_v2_css.txt   - Post-test indicators
#   _st_v2_module.js / _st_v2_css.txt   - Capital qualification setups
#   _ct_v2_module.js / _ct_v2_css.txt   - Capital deployment tests
#
# Discipline (D-MD-V2-43): heredoc -> /tmp -> atomic cp -> MD5 byte-verify.
# Idempotent, pre-write backup, atomic write at END, post-write verification.
# Edit tool BANNED on build_dashboard.py.
# =============================================================================
import sys, os, shutil, py_compile, tempfile
from datetime import datetime

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(SCRIPTS_DIR, "build_dashboard.py")
MARKER = "MD-V2-S26-CHIPS-MARKER"

# (payload module file, payload css file, module START marker, module END marker,
#  css START marker, css END marker, a token that must appear post-patch)
BLOCKS = [
    ("_po_v2_module.js", "_po_v2_css.txt",
     "MD-V2-POST-INDICATORS-MARKER-START", "MD-V2-POST-INDICATORS-MARKER-END",
     "MD-V2-POST-INDICATORS-MARKER-CSS-START", "MD-V2-POST-INDICATORS-MARKER-CSS-END",
     "renderPostIndicators", "poToggleTier"),
    ("_st_v2_module.js", "_st_v2_css.txt",
     "MD-V2-SETUPS-MARKER-START", "MD-V2-SETUPS-MARKER-END",
     "MD-V2-SETUPS-MARKER-CSS-START", "MD-V2-SETUPS-MARKER-CSS-END",
     "renderSetups", "stToggleTier"),
    ("_ct_v2_module.js", "_ct_v2_css.txt",
     "MD-V2-TESTS-MARKER-START", "MD-V2-TESTS-MARKER-END",
     "MD-V2-TESTS-MARKER-CSS-START", "MD-V2-TESTS-MARKER-CSS-END",
     "renderTests", "ctToggleTier"),
]

def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def replace_block(src, start_marker, end_marker, payload, label):
    s = "/* " + start_marker + " */"
    e = "/* " + end_marker + " */"
    i0 = src.find(s)
    i1 = src.find(e)
    if i0 == -1 or i1 == -1 or i1 < i0:
        print("ERROR: %s - marker block not found or malformed (%s .. %s)." % (label, start_marker, end_marker))
        sys.exit(1)
    i1_end = i1 + len(e)
    if not payload.startswith(s) or not payload.rstrip().endswith(e):
        print("ERROR: %s - payload missing its START/END markers." % label)
        sys.exit(1)
    return src[:i0] + payload + src[i1_end:]

def main():
    if not os.path.exists(TARGET):
        print("ERROR: target not found: %s" % TARGET); sys.exit(1)
    for mod_f, css_f, *_ in BLOCKS:
        for f in (mod_f, css_f):
            if not os.path.exists(os.path.join(SCRIPTS_DIR, f)):
                print("ERROR: payload not found: %s" % f); sys.exit(1)

    src = read(TARGET)
    if MARKER in src:
        print("IDEMPOTENT: %s already present. No-op." % MARKER)
        sys.exit(0)
    orig_len = len(src)

    for mod_f, css_f, m_start, m_end, css_start, css_end, _t1, _t2 in BLOCKS:
        mod_payload = read(os.path.join(SCRIPTS_DIR, mod_f)).rstrip("\n")
        css_payload = read(os.path.join(SCRIPTS_DIR, css_f)).rstrip("\n")
        src = replace_block(src, m_start, m_end, mod_payload, "module " + mod_f)
        src = replace_block(src, css_start, css_end, css_payload, "css " + css_f)

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".py", prefix="bd_s26_")
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
    backup = TARGET + ".bak-pre-md-v2-postind-setups-tests-s26-" + ts
    shutil.copy2(TARGET, backup)
    print("Pre-write backup: %s" % backup)
    shutil.copy2(tmp_path, TARGET)
    os.unlink(tmp_path)

    new_len = len(src)
    print("OK: build_dashboard.py patched (Session 26 - 3 modules + 3 CSS).")
    print("    %d bytes -> %d bytes (delta %+d)" % (orig_len, new_len, new_len - orig_len))
    print("    marker: %s" % MARKER)

    check = read(TARGET)
    if MARKER not in check:
        print("ERROR: post-write verification failed - marker missing!"); sys.exit(1)
    for mod_f, css_f, m_start, m_end, css_start, css_end, t1, t2 in BLOCKS:
        for tok in (t1, t2):
            if tok not in check:
                print("ERROR: post-write verification - missing token '%s' (%s)" % (tok, mod_f)); sys.exit(1)
        for m in (m_start, m_end, css_start, css_end):
            if check.count(m) != 1:
                print("ERROR: post-write verification - marker '%s' count = %d (expected 1)" % (m, check.count(m))); sys.exit(1)
    # the module-wrapper markers must still be intact too
    for m in ("MD-V2-POST-INDICATORS-MARKER-MODULE-START", "MD-V2-POST-INDICATORS-MARKER-MODULE-END",
              "MD-V2-SETUPS-MARKER-MODULE-START", "MD-V2-SETUPS-MARKER-MODULE-END",
              "MD-V2-TESTS-MARKER-MODULE-START", "MD-V2-TESTS-MARKER-MODULE-END"):
        if check.count(m) != 1:
            print("ERROR: post-write verification - wrapper marker '%s' count = %d" % (m, check.count(m))); sys.exit(1)
    print("Post-write verification: PASS (marker + 6 blocks + 6 wrapper markers intact).")

if __name__ == "__main__":
    main()
