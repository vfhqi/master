"""
=============================================================================
PATCHER — pulling_back_uptrend pre-indicator rating ladder amendment
=============================================================================
Project: SA - Master Dashboard
Session: S46 (18-May-2026)
Decision: D-MD-V2-107 (locked 18-May-2026)
Author: [W] Watson (SYSTEMS ARCHITECT role) under Richard's direction
Template: PATCHER-TEMPLATE.py (D-MD-INFRA-5 text-mode I/O)

WHAT THIS PATCHER DOES
----------------------
Replaces the shared `_pre_rating(pb_count, 4)` call inside the
`pulling_back_uptrend` pre-indicator dict literal with a custom inline
rating ladder per Richard's amendment locked 18-May-2026:

  0 of 4 tests pass -> "None"
  1 of 4           -> "None"      (was "Possible")
  2 of 4           -> "Possible"
  3 of 4           -> "Plausible"
  4 of 4           -> "Probable"

Effect: raises the floor for "Possible" from 1/4 to 2/4. Stocks that barely
trigger fall off the page. Plausible and Probable bands unchanged. Custom
rating logic inline for this pre-indicator only; the shared `_pre_rating`
function continues to govern the other eight pre-indicators (basing,
collapsing, etc).

WHY
---
Briefed by Richard mid-session S46 as Divergence 2 amendment after Watson
flagged that Group B of the Healthy Retest of MA test exactly replicates
the four pulling_back_uptrend pre-indicator tests, but Richard's spec
implicitly requires all four for Possible whereas the existing ladder
trips at one of four. Solution: bring the pre-indicator's ladder in line
with the Healthy Retest spec at the pre-indicator layer, so the
pre-indicator boolean and the test's Group B agree on what "pulling back"
means.

WHAT THIS PATCHER DOES NOT DO
-----------------------------
- Does NOT change the four underlying tests (50D rising, 150D rising,
  5D rolling over, 10D rolling over). Tests stay as-is.
- Does NOT change the `qualifies` field. Still consumed by downstream
  setups/tests as today.
- Does NOT change the shared `_pre_rating` function. Other eight
  pre-indicators continue to use it.
- Does NOT touch the dashboard side (build_dashboard.py). The rating
  string change is consumed by whatever already reads the
  pre-indicators.pulling_back_uptrend.rating field.

USAGE
-----
1. Dry-run from sandbox:
       python3 scripts/patch_md_v2_pulling_back_uptrend_ladder_s46_2026_05_18.py --test
2. Apply Windows-side (clean WT):
       python scripts/patch_md_v2_pulling_back_uptrend_ladder_s46_2026_05_18.py
       python scripts/refresh_all.py     (~17 min — regenerates filter-results.json)
       python scripts/build_dashboard.py
       git add scripts/generate_master_data.py index.html
       git commit -m "feat(MD V2 S46): pulling_back_uptrend ladder 2/4-Possible 3/4-Plausible 4/4-Probable (D-MD-V2-107)"
       git push
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
MARKER         = "MD-V2-S46-PB-LADDER-MARKER"
BAK_TAG        = "s46-pb-ladder"
ENABLE_PY_COMPILE = True
# ======================================================================

ANCHOR = """            "pulling_back_uptrend": {
                "tests": pb_tests, "count": pb_count, "total": 4,
                "rating": _pre_rating(pb_count, 4), "qualifies": ind["pulling_back_uptrend"],
                "test_values": {
                    "t1_50d_rising": "rising" if pb_t1_50d_rising else "not rising",
                    "t2_150d_rising": "rising" if pb_t2_150d_rising else "not rising",
                    "t3_5d_rolling_over": "rolling over" if pb_t3_5d_rolling else "not rolling",
                    "t4_10d_rolling_over": "rolling over" if pb_t4_10d_rolling else "not rolling",
                },
            },"""

REPLACEMENT = """            # MD-V2-S46-PB-LADDER-MARKER (18-May-26, D-MD-V2-107):
            # Custom rating ladder for pulling_back_uptrend per Richard's spec.
            # 4/4 = Probable; 3/4 = Plausible; 2/4 = Possible; 0-1/4 = None.
            # Raises Possible floor from 1/4 to 2/4 vs the shared _pre_rating
            # function (which still governs the other eight pre-indicators).
            "pulling_back_uptrend": {
                "tests": pb_tests, "count": pb_count, "total": 4,
                "rating": ("Probable" if pb_count >= 4 else "Plausible" if pb_count >= 3 else "Possible" if pb_count >= 2 else "None"),
                "qualifies": ind["pulling_back_uptrend"],
                "test_values": {
                    "t1_50d_rising": "rising" if pb_t1_50d_rising else "not rising",
                    "t2_150d_rising": "rising" if pb_t2_150d_rising else "not rising",
                    "t3_5d_rolling_over": "rolling over" if pb_t3_5d_rolling else "not rolling",
                    "t4_10d_rolling_over": "rolling over" if pb_t4_10d_rolling else "not rolling",
                },
            },"""


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
    print(f"[OK] Next: python scripts/refresh_all.py && python scripts/build_dashboard.py && git add -A && git commit && git push")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
