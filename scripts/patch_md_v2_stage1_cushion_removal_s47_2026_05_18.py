"""
=============================================================================
PATCHER S1 — Stage 1 Path B cushion removal
=============================================================================
Project: SA - Master Dashboard
Session: S47 (18-May-2026)
Decision: D-MD-V2-112 (locked 18-May-2026)
Author: [W] Watson (SYSTEMS ARCHITECT role) under Richard's direction
Template: PATCHER-TEMPLATE.py (D-MD-INFRA-5 text-mode I/O)

WHAT THIS PATCHER DOES
----------------------
Removes the ×0.97 cushion from Stage 1 Group 3 tests T5 and T6 in
generate_master_data.py. The cushion allowed stocks with a 50D MA up to
3% below the 150D (and 150D up to 3% below 200D) to still pass these
tests. With the cushion removed, T5 and T6 require a strict positive
stack: 50D must be ABOVE 150D, and 150D must be ABOVE 200D.

This is Path B of the audit memo Recommendation 1 — a surgical two-line
fix that closes the AG Barr-class Stage 1 + Stage 4 collision zone.
Stocks sitting in the cushion zone (50D within 3% below 150D) will now
fail G3 strictly, lose those test-count points, and drop one or more
rating tiers. They can no longer accumulate enough Stage 1 score to
reach Probable while simultaneously sitting in the Stage 4 bearish-
order zone.

Path A (structural ladder rewrite) is deferred to a later session per
Phase B5 of the audit memo.

WHAT THIS PATCHER DOES NOT DO
-----------------------------
- Does NOT change the column structure on the Stage 1 page.
- Does NOT change the rating ladder thresholds (still 5→Probable Late,
  4→Probable Early, 3→Plausible, 2→Possible, else→None).
- Does NOT change the test key names (T5_50_above_150x97 and
  T6_150_above_200x97 keep their legacy key names for backward
  compatibility with the dashboard display layer — the key name is a
  label artifact, the test logic changes).
- Does NOT touch build_dashboard.py.

USAGE
-----
1. Dry-run from sandbox:
       python3 scripts/patch_md_v2_stage1_cushion_removal_s47_2026_05_18.py --test
2. Apply Windows-side (clean WT, per-patcher commit cycle):
       python scripts/patch_md_v2_stage1_cushion_removal_s47_2026_05_18.py
       git add scripts/generate_master_data.py
       git commit -m "feat(MD V2 S47): Stage 1 Path B — remove x0.97 cushion from G3 T5/T6 (D-MD-V2-112)"
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
TARGET_REL     = os.path.join("scripts", "generate_master_data.py")
MARKER         = "MD-V2-S47-S1-CUSHION-REMOVAL-MARKER"
BAK_TAG        = "s47-s1-cushion"
ENABLE_PY_COMPILE = True
# ======================================================================

ANCHOR = """\
        # Group 3 — Positively stacked MAs
        s1_t5 = (ma50 is not None and ma150 is not None and ma150 > 0 and ma50 > ma150 * 0.97)
        s1_t6 = (ma150 is not None and ma200 is not None and ma200 > 0 and ma150 > ma200 * 0.97)
        s1["tests"]["T5_50_above_150x97"] = s1_t5
        s1["tests"]["T6_150_above_200x97"] = s1_t6
        s1["groups"]["g3_stack"] = {"T5": s1_t5, "T6": s1_t6}"""

REPLACEMENT = """\
        # Group 3 — Positively stacked MAs
        # MD-V2-S47-S1-CUSHION-REMOVAL-MARKER (18-May-26, D-MD-V2-112):
        # Path B — strict positive stack. Removed x0.97 cushion from T5/T6.
        # 50D must be ABOVE 150D; 150D must be ABOVE 200D. No 3% tolerance.
        s1_t5 = (ma50 is not None and ma150 is not None and ma50 > ma150)
        s1_t6 = (ma150 is not None and ma200 is not None and ma150 > ma200)
        s1["tests"]["T5_50_above_150x97"] = s1_t5
        s1["tests"]["T6_150_above_200x97"] = s1_t6
        s1["groups"]["g3_stack"] = {"T5": s1_t5, "T6": s1_t6}"""


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

    if MARKER in head_src:
        print(f"[OK] MARKER already in HEAD -- this patch has already shipped.")
        return 0
    if MARKER in wt_src:
        print(f"[OK] MARKER already in WT but not in HEAD -- applied but not committed yet.")
        return 0

    n = head_src.count(ANCHOR)
    print(f"[*] Anchor matches: {n} (expected 1)")
    if n != 1:
        print(f"[ABORT] Anchor count != 1 -- source may have drifted since patcher was authored.")
        return 3

    new_src = head_src.replace(ANCHOR, REPLACEMENT, 1)
    assert MARKER in new_src, "[INTERNAL] MARKER missing after replace"
    assert new_src.count(REPLACEMENT) == 1, "[INTERNAL] Replacement count != 1"

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
        fromfile=f"HEAD:{rel}", tofile=f"PATCHED:{rel}", n=2,
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
    print(f"[OK] Next: git add scripts/generate_master_data.py && git commit -m 'feat(MD V2 S47): Stage 1 Path B — remove x0.97 cushion from G3 T5/T6 (D-MD-V2-112)'")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
