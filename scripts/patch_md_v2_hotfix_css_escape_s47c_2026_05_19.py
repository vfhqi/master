"""
=============================================================================
PATCHER S47C HOTFIX — wrap misplaced CSS blocks in <style> tags
=============================================================================
Project: SA - Master Dashboard
Session: S47c (19-May-2026 hotfix)
Author: [W] Watson (Systems Architect role) under Richard's direction
Template: PATCHER-TEMPLATE.py (D-MD-INFRA-5 text-mode I/O)

WHAT THIS PATCHER DOES
----------------------
Hotfixes a design bug in Task 2 patchers 1/2/3. Each Task 2 patcher
inserted both a CSS block AND a JS render module before the
MD-V2-MASTER-OVERVIEW-MARKER-MODULE-START anchor. That anchor sits
INSIDE the raw triple-quoted js string in build_dashboard.py, which
emits into a script element in the rendered HTML.

Result: the CSS rules (#tab-setups_healthy_retest .group-captions, etc.)
end up inside a <script> tag. The JavaScript parser reads `#tab` as a
private class field reference outside a class, throws SyntaxError on
the first occurrence, every script below dies.

Symptom: live dashboard rendered with empty content area and
"Stocks: —" indicators. Caught 19-May-2026 ~06:30 UK by Richard.

This hotfix wraps each of the three misplaced CSS blocks with
`</script><style>` before the CSS-START marker and `</style><script>`
after the CSS-END marker. The CSS now sits in proper <style> context;
the JS modules that follow each CSS block sit in proper <script>
context (a new <script> tag that opens right after </style>).

Three CSS blocks fixed:
- MD-V2-S47-TAB-HEALTHY-RETEST-MARKER-CSS-START / -CSS-END
- MD-V2-S47-TAB-PROBING-BET-MARKER-CSS-START / -CSS-END
- MD-V2-S47-TAB-SPECULATIVE-BET-MARKER-CSS-START / -CSS-END

WHAT THIS PATCHER DOES NOT DO
-----------------------------
- Does NOT redesign the Task 2 patchers. The underlying design bug
  (CSS at JS-context anchor) remains in the original patcher source
  files; this hotfix corrects only the emitted output. A separate
  refactor of the Task 2 patcher sources is queued as a follow-up.
- Does NOT touch any other CSS block. Only the three S47 Task 2
  blocks are wrapped.
- Does NOT add new functionality. Pure structural fix.

WHY SPLITTING THE <script> ELEMENT IS SAFE
-------------------------------------------
The original `<script>` element contains many top-level `var`
declarations and IIFEs. Top-level `var` in a classic script tag
attaches to window, so it survives across script tags. IIFEs are
self-contained and don't need outside access. Script tags execute
synchronously in document order, so any subsequent script can rely
on prior script's window properties.

USAGE
-----
1. Dry-run from sandbox:
       python3 scripts/patch_md_v2_hotfix_css_escape_s47c_2026_05_19.py --test
2. Apply Windows-side (clean WT, per-patcher commit cycle):
       python scripts/patch_md_v2_hotfix_css_escape_s47c_2026_05_19.py
       git add scripts/build_dashboard.py
       git commit -m "feat(MD V2 S47c): hotfix — wrap Task 2 CSS blocks in <style> tags (live SyntaxError fix)"
       python scripts/build_dashboard.py
       (then push-dashboard.sh AFTER UI QC clean)
=============================================================================
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

# ============ CONFIGURE ME ============================================
REPO_ROOT_HINT = "master-dashboard"
TARGET_REL     = os.path.join("scripts", "build_dashboard.py")
MARKER         = "MD-V2-S47C-CSS-ESCAPE-MARKER"
BAK_TAG        = "s47c-css-escape"
ENABLE_PY_COMPILE = True
# ======================================================================

# Six anchor-replace pairs. Each CSS-START marker gets prepended with
# </script>\n<style>\n. Each CSS-END marker gets appended with
# \n</style>\n<script>. The hotfix marker is added near the end so
# idempotency check passes on re-apply.

ANCHOR_1A = "/* MD-V2-S47-TAB-HEALTHY-RETEST-MARKER-CSS-START */"
REPLACE_1A = "</script>\n<style>\n/* MD-V2-S47-TAB-HEALTHY-RETEST-MARKER-CSS-START */"

ANCHOR_1B = "/* MD-V2-S47-TAB-HEALTHY-RETEST-MARKER-CSS-END */"
REPLACE_1B = "/* MD-V2-S47-TAB-HEALTHY-RETEST-MARKER-CSS-END */\n</style>\n<script>"

ANCHOR_2A = "/* MD-V2-S47-TAB-PROBING-BET-MARKER-CSS-START */"
REPLACE_2A = "</script>\n<style>\n/* MD-V2-S47-TAB-PROBING-BET-MARKER-CSS-START */"

ANCHOR_2B = "/* MD-V2-S47-TAB-PROBING-BET-MARKER-CSS-END */"
REPLACE_2B = "/* MD-V2-S47-TAB-PROBING-BET-MARKER-CSS-END */\n</style>\n<script>"

ANCHOR_3A = "/* MD-V2-S47-TAB-SPECULATIVE-BET-MARKER-CSS-START */"
REPLACE_3A = "</script>\n<style>\n/* MD-V2-S47-TAB-SPECULATIVE-BET-MARKER-CSS-START */"

ANCHOR_3B = "/* MD-V2-S47-TAB-SPECULATIVE-BET-MARKER-CSS-END */"
REPLACE_3B = "/* MD-V2-S47-TAB-SPECULATIVE-BET-MARKER-CSS-END */\n</style>\n<script>\n/* MD-V2-S47C-CSS-ESCAPE-MARKER (19-May-26): live SyntaxError hotfix — wrapped 3 Task-2 CSS blocks in <style> elements. */"

ANCHORS = [
    ("HealthyRetest CSS-START", ANCHOR_1A, REPLACE_1A),
    ("HealthyRetest CSS-END",   ANCHOR_1B, REPLACE_1B),
    ("ProbingBet CSS-START",    ANCHOR_2A, REPLACE_2A),
    ("ProbingBet CSS-END",      ANCHOR_2B, REPLACE_2B),
    ("SpeculativeBet CSS-START", ANCHOR_3A, REPLACE_3A),
    ("SpeculativeBet CSS-END",   ANCHOR_3B, REPLACE_3B),
]


# ---------- BOILERPLATE — DO NOT EDIT BELOW ---------------------------

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
    rel_posix = rel.replace(os.sep, "/")
    out = subprocess.run(
        ["git", "show", f"HEAD:{rel_posix}"],
        cwd=repo, check=True, capture_output=True,
    )
    return out.stdout.decode("utf-8")


def _wt_text(repo: str, rel: str) -> str:
    with open(os.path.join(repo, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def _md5_text(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def main(argv):
    test_mode = "--test" in argv
    repo = _find_repo_root()
    rel = TARGET_REL
    abs_target = os.path.join(repo, rel)

    print(f"[*] Repo root:      {repo}")
    print(f"[*] Target:         {rel}")
    print(f"[*] Marker:         {MARKER}")
    print(f"[*] Mode:           {'DRY-RUN (--test)' if test_mode else 'WRITE'}")

    head_src = _git_show_head_text(repo, rel)
    wt_src   = _wt_text(repo, rel)
    print(f"[*] HEAD chars:     {len(head_src)}")
    print(f"[*] WT chars:       {len(wt_src)}")
    print(f"[*] HEAD md5(text): {_md5_text(head_src)}")
    print(f"[*] WT md5(text):   {_md5_text(wt_src)}")

    if _md5_text(wt_src) != _md5_text(head_src):
        msg = "Working tree diverges from HEAD (text-normalized compare)."
        if test_mode:
            print(f"[WARN] {msg}")
            print("       Dry-run continues -- gates operate on HEAD source.")
        else:
            print(f"[ABORT] {msg}")
            print(f"        Run `git status` and `git diff -- {rel.replace(os.sep, '/')}` to investigate.")
            return 2

    src = head_src

    if MARKER in src:
        print(f"[OK] MARKER already in HEAD -- hotfix has already shipped.")
        return 0

    print()
    for label, anchor, replacement in ANCHORS:
        n = src.count(anchor)
        print(f"[*] {label}: anchor matches = {n} (expected 1)")
        if n != 1:
            print(f"[ABORT] Anchor count != 1 for '{label}'. Source may have drifted.")
            return 3
        src = src.replace(anchor, replacement, 1)

    new_src = src
    assert MARKER in new_src, "[INTERNAL] MARKER missing after replace"

    print()
    print(f"[*] Char delta:     {len(new_src) - len(head_src):+d}")
    print(f"[*] New md5(text):  {_md5_text(new_src)}")

    if ENABLE_PY_COMPILE:
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
            try: os.unlink(tmp_py)
            except OSError: pass

    print("\n--- DIFF (unified, text-normalized) ---")
    sys.stdout.writelines(difflib.unified_diff(
        head_src.splitlines(keepends=True),
        new_src.splitlines(keepends=True),
        fromfile=f"HEAD:{rel}", tofile=f"PATCHED:{rel}", n=1,
    ))
    print("--- END DIFF ---\n")

    if test_mode:
        print("[OK] DRY-RUN: gates passed. Re-run without --test to write.")
        return 0

    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = abs_target + f".bak-pre-{BAK_TAG}-{ts}"
    with open(bak, "w", encoding="utf-8") as fh:
        fh.write(wt_src)
    print(f"[*] Backup:         {os.path.relpath(bak, repo)}")

    target_dir = os.path.dirname(abs_target)
    fd, tmp_out = tempfile.mkstemp(prefix=".patch-", suffix=".tmp", dir=target_dir)
    os.close(fd)
    with open(tmp_out, "w", encoding="utf-8") as fh:
        fh.write(new_src)
    os.replace(tmp_out, abs_target)

    after = _wt_text(repo, rel)
    if _md5_text(after) != _md5_text(new_src):
        print(f"[ABORT] Post-write text-md5 mismatch! Restore: {os.path.relpath(bak, repo)}")
        return 6
    if MARKER not in after:
        print("[ABORT] Post-write MARKER missing.")
        return 7

    disk_bytes = os.path.getsize(abs_target)
    print(f"[OK] WRITE complete. {len(after)} chars, {disk_bytes} bytes on disk. MARKER present.")
    print(f"[OK] Next: git add scripts/build_dashboard.py && git commit -m 'feat(MD V2 S47c): hotfix — wrap Task 2 CSS blocks in <style> tags (live SyntaxError fix)'")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
