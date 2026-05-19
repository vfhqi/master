"""
=============================================================================
PATCHER S47B — Stage 2 Probable threshold tighten from 10/13 to 11/13
=============================================================================
Project: SA - Master Dashboard
Session: S47b (19-May-2026)
Decision: D-MD-V2-113 audit hook (locked 18-May-2026; hook fired 19-May-2026)
Author: [W] Watson (Systems Architect role) under Richard's direction
Template: PATCHER-TEMPLATE.py (D-MD-INFRA-5 text-mode I/O)

WHAT THIS PATCHER DOES
----------------------
Tightens the Stage 2 Probable threshold from `s2_count >= 10` to
`s2_count >= 11` in scripts/generate_master_data.py. This is the audit-
hook tightening locked in D-MD-V2-113: if the post-apply Probable count
exceeds 20 percent of universe, the threshold tightens to 11 of 13.

Verify result on 19-May-2026: Stage 2 Probable at 29.2 percent of the
946-stock universe (276 stocks). The hook fires.

WHAT THIS PATCHER DOES NOT DO
-----------------------------
- Does NOT change the Plausible threshold (stays at 9 of 13).
- Does NOT change the Possible threshold (stays at 8 of 13).
- Does NOT change the test composition (still 13 tests: T1 to T13).
- Does NOT change the test logic of any T1 to T13.
- Does NOT touch any other Stage's threshold.

WHAT HAPPENS TO STOCKS AT count=10 AFTER THIS PATCH
---------------------------------------------------
Previously at "Probable" (count was exactly 10). Now: count=10 falls into
the `s2_count >= 9` branch, so the rating becomes "Plausible". Plausible
tier grows; Probable tier shrinks.

USAGE
-----
1. Dry-run from sandbox:
       python3 scripts/patch_md_v2_stage2_tighten_11of13_s47b_2026_05_19.py --test
2. Apply Windows-side (clean WT, per-patcher commit cycle):
       python scripts/patch_md_v2_stage2_tighten_11of13_s47b_2026_05_19.py
       git add scripts/generate_master_data.py
       git commit -m "feat(MD V2 S47b): tighten Stage 2 Probable to 11/13 per audit hook (D-MD-V2-113 hook)"
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
MARKER         = "MD-V2-S47B-S2-TIGHTEN-11OF13-MARKER"
BAK_TAG        = "s47b-s2-tighten"
ENABLE_PY_COMPILE = True
# ======================================================================

ANCHOR = """\
        # Composite count — 13 tests (was 10; +T11, +T12, +T13 per D-MD-V2-113)
        s2_count = sum(1 for t in [s2_t1, s2_t2, s2_t3, s2_t4, s2_t5, s2_t6, s2_t7, s2_t8, s2_t9, s2_t10, s2_t11, s2_t12, s2_t13] if t)
        s2["count"] = s2_count
        s2["total"] = 13
        if s2_count >= 10:
            s2["rating"] = "Probable"
        elif s2_count >= 9:
            s2["rating"] = "Plausible"
        elif s2_count >= 8:
            s2["rating"] = "Possible"
        else:"""

REPLACEMENT = """\
        # Composite count — 13 tests (was 10; +T11, +T12, +T13 per D-MD-V2-113)
        s2_count = sum(1 for t in [s2_t1, s2_t2, s2_t3, s2_t4, s2_t5, s2_t6, s2_t7, s2_t8, s2_t9, s2_t10, s2_t11, s2_t12, s2_t13] if t)
        s2["count"] = s2_count
        s2["total"] = 13
        # MD-V2-S47B-S2-TIGHTEN-11OF13-MARKER (19-May-26, D-MD-V2-113 audit hook):
        # Probable threshold tightened from 10/13 to 11/13. Audit hook fired
        # on 19-May post-Task-3 refresh: Probable was 29.2% > 20% ceiling.
        # Stocks at count=10 now demote to Plausible.
        if s2_count >= 11:
            s2["rating"] = "Probable"
        elif s2_count >= 9:
            s2["rating"] = "Plausible"
        elif s2_count >= 8:
            s2["rating"] = "Possible"
        else:"""


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
    print(f"[OK] Next: git add scripts/generate_master_data.py && git commit -m 'feat(MD V2 S47b): tighten Stage 2 Probable to 11/13 per audit hook (D-MD-V2-113 hook)'")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
