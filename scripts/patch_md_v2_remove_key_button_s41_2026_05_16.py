"""
S41 PATCHER -- remove the "Key" button from the header on all pages.

Richard's brief (16-May-26): "Remove the 'key' button from top right on all
pages. Logic: Not being used."

CHANGE
------
build_dashboard.py L12761 -- drop the `<button onclick="openKey()">Key</button>`
emission from the header-right-btns container, leaving only the Chart button.

The openKey()/closeKey()/_removeKeyRows machinery at L2810-2828 is left in
place as dead code -- removing the button is sufficient for the user-visible
behaviour Richard asked for, and the machinery can be cleaned in a separate
hygiene pass without functional risk.
"""
from __future__ import annotations
import ast, datetime as _dt, difflib, hashlib, os, py_compile, subprocess, sys, tempfile

REPO_ROOT_HINT = "master-dashboard"
TARGET_REL     = os.path.join("scripts", "build_dashboard.py")
MARKER         = "MD-V2-S41-REMOVE-KEY-BUTTON-MARKER"
BAK_TAG        = "s41-remove-key-button"
ENABLE_PY_COMPILE = True

ANCHOR = """        '    <div class="header-right-btns">\\n'
        '      <button class="ctrl-btn" onclick="openKey()">Key</button>\\n'
        '      <button class="ctrl-btn" id="hdr-chart-btn" onclick="openChart(\\'Overview\\')">Chart</button>\\n'
        '    </div>\\n'"""

REPLACEMENT = """        '    <div class="header-right-btns">\\n'
        # MD-V2-S41-REMOVE-KEY-BUTTON-MARKER -- "Key" button removed per S41 brief (16-May-26)
        '      <button class="ctrl-btn" id="hdr-chart-btn" onclick="openChart(\\'Overview\\')">Chart</button>\\n'
        '    </div>\\n'"""


def _find_repo_root():
    cur = os.path.abspath(os.path.dirname(__file__))
    cand = os.path.abspath(os.path.join(cur, os.pardir))
    if os.path.basename(cand) == REPO_ROOT_HINT and os.path.exists(os.path.join(cand, ".git")):
        return cand
    walk = cur
    for _ in range(6):
        if os.path.exists(os.path.join(walk, ".git")):
            return walk
        walk = os.path.abspath(os.path.join(walk, os.pardir))
    raise SystemExit("[ABORT] cannot locate repo root from " + cur)


def _git_show_head_text(repo, rel):
    rel_posix = rel.replace(os.sep, "/")
    out = subprocess.run(["git", "show", "HEAD:" + rel_posix], cwd=repo, check=True, capture_output=True)
    return out.stdout.decode("utf-8")


def _wt_text(repo, rel):
    with open(os.path.join(repo, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def _md5_text(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def main(argv):
    test_mode = "--test" in argv
    repo = _find_repo_root()
    rel = TARGET_REL
    abs_target = os.path.join(repo, rel)
    print("[*] Repo root: " + repo)
    print("[*] Target: " + rel)
    print("[*] Marker: " + MARKER)
    print("[*] Mode: " + ("DRY-RUN" if test_mode else "WRITE"))
    head_src = _git_show_head_text(repo, rel)
    wt_src = _wt_text(repo, rel)
    print("[*] HEAD chars: %d | WT chars: %d" % (len(head_src), len(wt_src)))
    if _md5_text(wt_src) != _md5_text(head_src):
        if test_mode:
            print("[WARN] WT diverges from HEAD; dry-run proceeds (gates on HEAD).")
        else:
            print("[ABORT] WT diverges from HEAD.")
            return 2
    if MARKER in head_src:
        print("[OK] MARKER already in HEAD.")
        return 0
    if MARKER in wt_src:
        print("[OK] MARKER in WT, not HEAD.")
        return 0
    n = head_src.count(ANCHOR)
    print("[*] Anchor matches: %d (expected 1)" % n)
    if n != 1:
        print("[ABORT] Anchor count != 1.")
        return 3
    new_src = head_src.replace(ANCHOR, REPLACEMENT, 1)
    assert MARKER in new_src and new_src.count(REPLACEMENT) == 1
    print("[*] Char delta: %+d" % (len(new_src) - len(head_src)))
    if ENABLE_PY_COMPILE:
        try:
            ast.parse(new_src)
        except SyntaxError as e:
            print("[ABORT] ast.parse: " + str(e))
            return 4
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tf:
            tf.write(new_src)
            tmp_py = tf.name
        try:
            py_compile.compile(tmp_py, doraise=True)
            print("[*] py_compile: OK")
        except py_compile.PyCompileError as e:
            print("[ABORT] py_compile: " + str(e))
            return 5
        finally:
            try:
                os.unlink(tmp_py)
            except OSError:
                pass
    print("\n--- DIFF ---")
    sys.stdout.writelines(difflib.unified_diff(head_src.splitlines(keepends=True), new_src.splitlines(keepends=True), fromfile="HEAD:" + rel, tofile="PATCHED:" + rel, n=2))
    print("--- END DIFF ---\n")
    if test_mode:
        print("[OK] DRY-RUN gates passed.")
        return 0
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = abs_target + ".bak-pre-" + BAK_TAG + "-" + ts
    with open(bak, "w", encoding="utf-8") as fh:
        fh.write(wt_src)
    print("[*] Backup: " + os.path.relpath(bak, repo))
    fd, tmp_out = tempfile.mkstemp(prefix=".patch-", suffix=".tmp", dir=os.path.dirname(abs_target))
    os.close(fd)
    with open(tmp_out, "w", encoding="utf-8") as fh:
        fh.write(new_src)
    os.replace(tmp_out, abs_target)
    after = _wt_text(repo, rel)
    if _md5_text(after) != _md5_text(new_src):
        print("[ABORT] post-write md5 mismatch.")
        return 6
    if MARKER not in after:
        print("[ABORT] MARKER missing post-write.")
        return 7
    print("[OK] WRITE complete. %d chars on disk." % len(after))
    print("[OK] NEXT: python scripts/build_dashboard.py && git add -A && git commit && git push")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
