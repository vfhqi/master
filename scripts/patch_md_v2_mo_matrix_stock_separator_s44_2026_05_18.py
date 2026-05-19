"""
S44 PATCHER -- Master Overview matrix Stock column separator

UI QC Issue 1 (18-May-26): the MO matrix name cell renders
  <span class="mo-mx-co">company</span><span class="mo-mx-tk">ticker</span>
inline with no visible separator. The existing margin-left: 5px on .mo-mx-tk
is visually inadequate — rows read as "3i GroupIII-GB", "A.G. BARRBAG-GB" etc.

FIX
---
Add a CSS ::before pseudo-element on .mo-mx-tk that inserts a middle-dot
separator character between the company name and ticker. Pure CSS patch,
zero JS changes, zero risk of functional regression.

Anchor: the .mo-mx-tk rule at line ~1959.
"""
from __future__ import annotations
import ast, datetime as _dt, hashlib, os, py_compile, subprocess, sys, tempfile

REPO_ROOT_HINT = "master-dashboard"
TARGET_REL     = os.path.join("scripts", "build_dashboard.py")
MARKER         = "MD-V2-S44-MO-MATRIX-STOCK-SEPARATOR-MARKER"
BAK_TAG        = "s44-mo-matrix-stock-separator"

ANCHOR = "#mo-matrix-table tbody td.mo-mx-name-cell .mo-mx-tk { color: #a39d88; font-size: 10px; margin-left: 5px; }"
REPLACEMENT = (
    "#mo-matrix-table tbody td.mo-mx-name-cell .mo-mx-tk { color: #a39d88; font-size: 10px; margin-left: 0; }\n"
    "#mo-matrix-table tbody td.mo-mx-name-cell .mo-mx-tk::before { content: '\\00b7'; "
    "color: #c4c0b0; font-weight: 400; margin: 0 4px; }  "
    "/* " + MARKER + " */"
)

def _find_repo_root():
    cur = os.path.abspath(os.path.dirname(__file__))
    # Walk up until we find the repo root
    for _ in range(10):
        if os.path.basename(cur) == REPO_ROOT_HINT and os.path.exists(os.path.join(cur, ".git")):
            return cur
        parent = os.path.abspath(os.path.join(cur, os.pardir))
        if parent == cur:
            break
        cur = parent
    # Fallback: try sibling of scripts dir
    cur = os.path.abspath(os.path.dirname(__file__))
    cand = os.path.abspath(os.path.join(cur, os.pardir))
    if os.path.basename(cand) == REPO_ROOT_HINT and os.path.exists(os.path.join(cand, ".git")):
        return cand
    raise SystemExit("[ABORT] cannot locate repo root from " + cur)

def _git_show(repo, rel):
    return subprocess.run(
        ["git", "show", "HEAD:" + rel.replace(os.sep, "/")],
        cwd=repo, check=True, capture_output=True
    ).stdout.decode("utf-8")

def _wt(repo, rel):
    with open(os.path.join(repo, rel), "r", encoding="utf-8") as f:
        return f.read()

def _md5(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()

def main(argv):
    test_mode = "--test" in argv
    repo = _find_repo_root()
    rel = TARGET_REL
    abs_target = os.path.join(repo, rel)

    head_src = _git_show(repo, rel)
    wt_src = _wt(repo, rel)
    print("[*] HEAD: %d chars | WT: %d chars" % (len(head_src), len(wt_src)))

    if _md5(wt_src) != _md5(head_src):
        if test_mode:
            print("[WARN] WT diverges from HEAD; dry-run on HEAD source.")
        else:
            print("[ABORT] WT diverges from HEAD.")
            return 2

    if MARKER in head_src:
        print("[OK] MARKER already in HEAD.")
        return 0
    if MARKER in wt_src:
        print("[OK] MARKER in WT, not yet committed.")
        return 0

    n = head_src.count(ANCHOR)
    print("[*] Anchor matches: %d (expected 1)" % n)
    if n != 1:
        print("[ABORT] Anchor count != 1.")
        return 3

    new_src = head_src.replace(ANCHOR, REPLACEMENT, 1)
    assert MARKER in new_src

    # Validate the result is still valid Python
    ast.parse(new_src)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tf:
        tf.write(new_src)
        tmp_py = tf.name
    try:
        py_compile.compile(tmp_py, doraise=True)
        print("[*] py_compile: OK")
    finally:
        try:
            os.unlink(tmp_py)
        except OSError:
            pass

    if test_mode:
        print("[OK] DRY-RUN gates passed.")
        return 0

    # Backup
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = abs_target + ".bak-pre-" + BAK_TAG + "-" + ts
    with open(bak, "w", encoding="utf-8") as f:
        f.write(wt_src)

    # Atomic write via temp file + replace
    fd, tmp_out = tempfile.mkstemp(prefix=".patch-", suffix=".tmp", dir=os.path.dirname(abs_target))
    os.close(fd)
    with open(tmp_out, "w", encoding="utf-8") as f:
        f.write(new_src)
    os.replace(tmp_out, abs_target)

    # Verify
    after = _wt(repo, rel)
    if _md5(after) != _md5(new_src):
        print("[ABORT] md5 mismatch.")
        return 6
    if MARKER not in after:
        print("[ABORT] MARKER missing.")
        return 7

    print("[OK] WRITE complete. %d chars on disk. MARKER present." % len(after))
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
