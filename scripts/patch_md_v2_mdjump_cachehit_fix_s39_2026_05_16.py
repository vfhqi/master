"""
SA - Master Dashboard | Patcher: _mdJump cache-hit fix (S34 carry, S39 ship).

Problem (diagnosed S34):
    moJumpToTab sets window._mdJump then calls switchTab(row.tabId). switchTab
    only re-renders if the target tab element has no innerHTML or carries
    data-stale="1". On a cache-hit (visited-and-cached) tab, the cached
    innerHTML is served and the _mdJump consumer in renderTab never fires --
    user lands on the right tab, but unfiltered.

Fix:
    Before switchTab, mark the target tab element data-stale="1". switchTab
    will then re-render, the consumer fires, the chip filter applies.

Scope (post-S35 R2+3, commit 5d1a99a):
    Only moJumpToTab sets window._mdJump (cell-click is now the co-occurrence
    selector). Single anchor, single insert.

Doctrine compliance:
    - Reads source via `git show HEAD:` (FUSE-immune).
    - Idempotent on MARKER line.
    - Working-tree-vs-HEAD safety gate (aborts if WT diverges from HEAD).
    - Exact anchor count assertion (must match 1 place).
    - py_compile + ast.parse pre-write.
    - Pre-write backup as sidecar (.bak-pre-mdjump-cachehit-{TS}).
    - --test dry-run mode prints diff and exits without writing.

Run on Windows-side:
    python scripts\\patch_md_v2_mdjump_cachehit_fix_s39_2026_05_16.py --test
    python scripts\\patch_md_v2_mdjump_cachehit_fix_s39_2026_05_16.py
    python scripts\\build_dashboard.py
    git add -A
    git commit -m "fix(MD V2): S39 - moJumpToTab cache-hit fix (set data-stale before switchTab so _mdJump consumer fires)"
    git push
"""
from __future__ import annotations
import ast
import datetime as _dt
import hashlib
import os
import py_compile
import subprocess
import sys
import tempfile

REPO_ROOT_HINT = "master-dashboard"
TARGET_REL = "scripts/build_dashboard.py"
MARKER = "MD-V2-MDJUMP-CACHEHIT-FIX-S39"  # substring that appears once in the inserted comment

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
    # If invoked from scripts/, parent is repo root
    cand = os.path.abspath(os.path.join(cur, os.pardir))
    if os.path.basename(cand) == REPO_ROOT_HINT and os.path.exists(os.path.join(cand, ".git")):
        return cand
    # Otherwise: walk upward to find .git
    walk = cur
    for _ in range(6):
        if os.path.exists(os.path.join(walk, ".git")):
            return walk
        walk = os.path.abspath(os.path.join(walk, os.pardir))
    raise SystemExit(f"[ABORT] cannot locate repo root from {cur}")

def _git_show_head(repo: str, rel: str) -> bytes:
    out = subprocess.run(
        ["git", "show", f"HEAD:{rel}"],
        cwd=repo, check=True, capture_output=True,
    )
    return out.stdout

def _wt_bytes(repo: str, rel: str) -> bytes:
    with open(os.path.join(repo, rel), "rb") as fh:
        return fh.read()

def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def main(argv: list[str]) -> int:
    test_mode = "--test" in argv
    repo = _find_repo_root()
    rel = TARGET_REL
    abs_target = os.path.join(repo, rel)

    print(f"[*] Repo root:   {repo}")
    print(f"[*] Target:      {rel}")
    print(f"[*] Mode:        {'DRY-RUN (--test)' if test_mode else 'WRITE'}")

    # --- 1. Read HEAD source (FUSE-immune) ---
    head_src = _git_show_head(repo, rel)
    print(f"[*] HEAD bytes:  {len(head_src)}")
    print(f"[*] HEAD sha256: {_sha256(head_src)}")

    # --- 2. Working-tree safety gate ---
    wt_src = _wt_bytes(repo, rel)
    print(f"[*] WT bytes:    {len(wt_src)}")
    print(f"[*] WT sha256:   {_sha256(wt_src)}")
    if wt_src != head_src:
        if test_mode:
            print("[WARN] Working tree diverges from HEAD (likely FUSE stale-cache in sandbox).")
            print("       Dry-run continues -- gates operate on HEAD source.")
            print("       The WRITE path will still refuse if WT != HEAD.")
        else:
            print("[ABORT] Working tree diverges from HEAD. Refusing to patch.")
            print("        Run `git status` and resolve before re-running.")
            return 2

    src = head_src.decode("utf-8")

    # --- 3. Idempotency check ---
    if MARKER in src:
        print(f"[OK] MARKER already present ({MARKER!r}) - patch is idempotent, nothing to do.")
        return 0

    # --- 4. Exact-anchor count assertion ---
    n = src.count(ANCHOR)
    print(f"[*] Anchor matches: {n} (expected 1)")
    if n != 1:
        print("[ABORT] Anchor count != 1. Source may have drifted since patcher was authored.")
        return 3

    # --- 5. Apply replacement ---
    new_src = src.replace(ANCHOR, REPLACEMENT, 1)
    assert MARKER in new_src, "[INTERNAL] MARKER missing after replace"
    assert new_src.count(REPLACEMENT) == 1, "[INTERNAL] Replacement count != 1"
    delta = len(new_src) - len(src)
    print(f"[*] Byte delta:  +{delta}")
    print(f"[*] New sha256:  {_sha256(new_src.encode('utf-8'))}")

    # --- 6. Compile gates: ast.parse + py_compile on new source ---
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
        print(f"[*] py_compile:  OK")
    except py_compile.PyCompileError as e:
        print(f"[ABORT] py_compile failed: {e}")
        return 5
    finally:
        try:
            os.unlink(tmp_py)
        except OSError:
            pass

    # --- 7. Show diff snippet ---
    print("\n--- DIFF (unified) ---")
    import difflib
    diff = difflib.unified_diff(
        src.splitlines(keepends=True),
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

    # --- 8. Pre-write backup as sidecar ---
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = abs_target + f".bak-pre-mdjump-cachehit-{ts}"
    with open(bak, "wb") as fh:
        fh.write(wt_src)
    print(f"[*] Backup:      {os.path.relpath(bak, repo)}")

    # --- 9. Write via /tmp + os.replace (FUSE-safer atomic swap) ---
    target_dir = os.path.dirname(abs_target)
    fd, tmp_out = tempfile.mkstemp(prefix=".bd-patch-", dir=target_dir, text=False)
    os.close(fd)
    with open(tmp_out, "wb") as fh:
        fh.write(new_src.encode("utf-8"))
    os.replace(tmp_out, abs_target)

    # --- 10. Post-write byte-verify ---
    after = _wt_bytes(repo, rel)
    if _sha256(after) != _sha256(new_src.encode("utf-8")):
        print("[ABORT] Post-write sha256 mismatch -- file did NOT land as expected!")
        print("        Restore from the .bak-pre-* sidecar.")
        return 6
    if MARKER not in after.decode("utf-8"):
        print("[ABORT] Post-write MARKER missing.")
        return 7
    print(f"[OK] WRITE complete. {len(after)} bytes on disk. MARKER present.")
    print(f"[OK] Next: python scripts/build_dashboard.py && git add -A && git commit && git push")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
