"""
SA - Master Dashboard | Patcher: _mdJump cache-hit fix (S39 v2 - CRLF-safe).

V2 of the S39 mdJump cache-hit fix. V1 (2026-05-16 ~07:00 UK) aborted on
Windows because its WT-vs-HEAD safety gate used BINARY-mode reads. On Windows
with core.autocrlf=true, the WT file is CRLF on disk while the git blob is
LF -- so byte-compare reports a false divergence even when `git status` is
clean. V2 reads the WT in TEXT mode (Python universal newlines translates
CRLF -> LF on read) and writes in TEXT mode (auto LF -> CRLF on Windows),
matching the S35-S38 house style verbatim.

The functional fix is unchanged from v1 -- one 5-line insert in moJumpToTab
so cache-hit jumps re-render the target tab and the _mdJump consumer fires.

Run on Windows-side:
    python scripts\\patch_md_v2_mdjump_cachehit_fix_s39_v2_2026_05_16.py --test
    python scripts\\patch_md_v2_mdjump_cachehit_fix_s39_v2_2026_05_16.py
    python scripts\\build_dashboard.py
    git add scripts\\build_dashboard.py index.html
    git commit -m "fix(MD V2): S39 - moJumpToTab cache-hit (set data-stale before switchTab so _mdJump consumer fires)"
    git push
"""
from __future__ import annotations
import ast
import datetime as _dt
import difflib
import hashlib
import os
import py_compile
import subprocess
import sys
import tempfile

REPO_ROOT_HINT = "master-dashboard"
TARGET_REL = os.path.join("scripts", "build_dashboard.py")
MARKER = "MD-V2-MDJUMP-CACHEHIT-FIX-S39"

ANCHOR = """  function moJumpToTab(rowKey) {
    var row = null;
    for (var i = 0; i < MO_ROWS.length; i++) if (MO_ROWS[i].key === rowKey) row = MO_ROWS[i];
    if (!row) return;
    window._mdJump = { tab: row.tabId };
    if (typeof window.switchTab === 'function') window.switchTab(row.tabId);
  }"""

REPLACEMENT = """  function moJumpToTab(rowKey) {
    var row = null;
    for (var i = 0; i < MO_ROWS.length; i++) if (MO_ROWS[i].key === rowKey) row = MO_ROWS[i];
    if (!row) return;
    window._mdJump = { tab: row.tabId };
    /* MD-V2-MDJUMP-CACHEHIT-FIX-S39: force re-render of target tab so the
       _mdJump consumer fires on cache-hit. Without this, switchTab serves the
       cached innerHTML and the chip filter never applies. S34 carry. */
    var _mdjTgt = document.getElementById('tab-' + row.tabId);
    if (_mdjTgt) _mdjTgt.setAttribute('data-stale', '1');
    if (typeof window.switchTab === 'function') window.switchTab(row.tabId);
  }"""


def _find_repo_root() -> str:
    cur = os.path.abspath(os.path.dirname(__file__))
    cand = os.path.abspath(os.path.join(cur, os.pardir))
    if os.path.basename(cand) == REPO_ROOT_HINT and os.path.exists(os.path.join(cand, ".git")):
        return cand
    walk = cur
    for _ in range(6):
        if os.path.exists(os.path.join(walk, ".git")):
            return walk
        walk = os.path.abspath(os.path.join(walk, os.pardir))
    raise SystemExit(f"[ABORT] cannot locate repo root from {cur}")


def _git_show_head_text(repo: str, rel: str) -> str:
    """HEAD blob, decoded as UTF-8 text (always LF -- git stores LF in blobs)."""
    rel_posix = rel.replace(os.sep, "/")
    out = subprocess.run(
        ["git", "show", f"HEAD:{rel_posix}"],
        cwd=repo, check=True, capture_output=True,
    )
    return out.stdout.decode("utf-8")


def _wt_text(repo: str, rel: str) -> str:
    """Working-tree file, text mode (Python universal-newlines: CRLF -> LF on read)."""
    p = os.path.join(repo, rel)
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read()


def _md5_text(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def main(argv: list[str]) -> int:
    test_mode = "--test" in argv
    repo = _find_repo_root()
    rel = TARGET_REL
    abs_target = os.path.join(repo, rel)

    print(f"[*] Repo root:      {repo}")
    print(f"[*] Target:         {rel}")
    print(f"[*] Mode:           {'DRY-RUN (--test)' if test_mode else 'WRITE'}")

    head_src = _git_show_head_text(repo, rel)
    print(f"[*] HEAD chars:     {len(head_src)}")
    print(f"[*] HEAD md5(text): {_md5_text(head_src)}")

    wt_src = _wt_text(repo, rel)
    print(f"[*] WT chars:       {len(wt_src)}")
    print(f"[*] WT md5(text):   {_md5_text(wt_src)}")

    if _md5_text(wt_src) != _md5_text(head_src):
        msg = "Working tree diverges from HEAD (text-normalized compare)."
        if test_mode:
            print(f"[WARN] {msg}")
            print(f"       Dry-run continues -- gates operate on HEAD source.")
        else:
            print(f"[ABORT] {msg}")
            print(f"        Run `git status` and `git diff -- {rel.replace(os.sep, '/')}` to investigate.")
            return 2

    if MARKER in head_src:
        print(f"[OK] MARKER already in HEAD -- this patch has already shipped. Nothing to do.")
        return 0
    if MARKER in wt_src:
        print(f"[OK] MARKER already in WT but not in HEAD -- patch applied but not committed yet.")
        print(f"     Run: git add {rel.replace(os.sep, '/')} && git commit && git push")
        return 0

    n = head_src.count(ANCHOR)
    print(f"[*] Anchor matches: {n} (expected 1)")
    if n != 1:
        print(f"[ABORT] Anchor count != 1 -- source may have drifted.")
        return 3

    new_src = head_src.replace(ANCHOR, REPLACEMENT, 1)
    assert MARKER in new_src, "[INTERNAL] MARKER missing after replace"
    assert new_src.count(REPLACEMENT) == 1, "[INTERNAL] Replacement count != 1"
    delta = len(new_src) - len(head_src)
    print(f"[*] Char delta:     +{delta}")
    print(f"[*] New md5(text):  {_md5_text(new_src)}")

    try:
        ast.parse(new_src)
    except SyntaxError as e:
        print(f"[ABORT] ast.parse failed on new source: {e}")
        return 4

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tf:
        tf.write(new_src)
        tmp_py = tf.name
    try:
        py_compile.compile(tmp_py, doraise=True)
        print(f"[*] py_compile:     OK")
    except py_compile.PyCompileError as e:
        print(f"[ABORT] py_compile failed: {e}")
        return 5
    finally:
        try:
            os.unlink(tmp_py)
        except OSError:
            pass

    print("\n--- DIFF (unified, on LF-normalized text) ---")
    diff = difflib.unified_diff(
        head_src.splitlines(keepends=True),
        new_src.splitlines(keepends=True),
        fromfile=f"HEAD:{rel}",
        tofile=f"PATCHED:{rel}",
        n=2,
    )
    sys.stdout.writelines(diff)
    print("--- END DIFF ---\n")

    if test_mode:
        print("[OK] DRY-RUN: gates passed. Re-run without --test to write.")
        return 0

    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = abs_target + f".bak-pre-mdjump-cachehit-v2-{ts}"
    # Backup the WT as-is (preserving CRLF if present) via binary copy
    with open(abs_target, "rb") as src_fh, open(bak, "wb") as bak_fh:
        bak_fh.write(src_fh.read())
    print(f"[*] Backup:         {os.path.relpath(bak, repo)}")

    # Write via text mode -- on Windows this writes CRLF, on Linux LF.
    # Atomic swap via os.replace.
    target_dir = os.path.dirname(abs_target)
    fd, tmp_out = tempfile.mkstemp(prefix=".bd-patch-", suffix=".tmp", dir=target_dir)
    os.close(fd)
    with open(tmp_out, "w", encoding="utf-8") as fh:
        fh.write(new_src)
    os.replace(tmp_out, abs_target)

    # Post-write verify -- read back in text mode (universal newlines) and
    # compare LF-normalized md5 to the new_src we just wrote.
    after = _wt_text(repo, rel)
    if _md5_text(after) != _md5_text(new_src):
        print("[ABORT] Post-write text-md5 mismatch -- file did NOT land as expected!")
        print(f"        Restore from sidecar: {os.path.relpath(bak, repo)}")
        return 6
    if MARKER not in after:
        print("[ABORT] Post-write MARKER missing.")
        return 7

    # Also report on-disk bytes (will differ from char count on Windows due to CRLF)
    disk_bytes = os.path.getsize(abs_target)
    print(f"[OK] WRITE complete. {len(after)} chars, {disk_bytes} bytes on disk. MARKER present.")
    print(f"[OK] Next: python scripts/build_dashboard.py")
    print(f"[OK]       git add scripts/build_dashboard.py index.html")
    print(f"[OK]       git commit -m \"fix(MD V2): S39 - moJumpToTab cache-hit\" && git push")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
