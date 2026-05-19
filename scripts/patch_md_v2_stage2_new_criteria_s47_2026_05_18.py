"""
=============================================================================
PATCHER S2 — Stage 2 three new criteria + new rating ladder
=============================================================================
Project: SA - Master Dashboard
Session: S47 (18-May-2026)
Decision: D-MD-V2-113 (locked 18-May-2026)
Author: [W] Watson (SYSTEMS ARCHITECT role) under Richard's direction
Template: PATCHER-TEMPLATE.py (D-MD-INFRA-5 text-mode I/O)

WHAT THIS PATCHER DOES
----------------------
Adds three new Minervini-canonical tests to the Stage 2 block and
adjusts the rating ladder from 10 tests to 13 tests:

  T11 (Group 3): 50D MA > 200D MA
  T12 (Group 3): 50D MA rising (day-over-day: ma50 > ma50_prev)
  T13 (Group 2): 150D MA rising (day-over-day: ma150 > ma150_prev)

EXCLUSION: "Price > 50D" is NOT added — Stage tests are about MT/LT
trends, not NT trends (Richard's framing).

New rating ladder:
  Probable  = 10/13
  Plausible = 9/13
  Possible  = 8/13
  None      = below 8/13

Audit hook (post-apply, not in patcher): if Probable > 20% of universe
(~190 stocks of 946), tighten Probable threshold to 11/13 and re-run.

WHAT THIS PATCHER DOES NOT DO
-----------------------------
- Does NOT add "Price > 50D" test (excluded per Richard's spec).
- Does NOT touch the dashboard side (build_dashboard.py).
- Does NOT touch any other Stage block.
- Does NOT apply the audit-hook threshold tightening (that decision is
  made post-apply based on the verify script's distribution check).

USAGE
-----
1. Dry-run:
       python3 scripts/patch_md_v2_stage2_new_criteria_s47_2026_05_18.py --test
2. Apply (clean WT, per-patcher commit cycle):
       python scripts/patch_md_v2_stage2_new_criteria_s47_2026_05_18.py
       git add scripts/generate_master_data.py
       git commit -m "feat(MD V2 S47): Stage 2 — add T11/T12/T13 + new 13-test ladder (D-MD-V2-113)"
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
MARKER         = "MD-V2-S47-S2-NEW-CRITERIA-MARKER"
BAK_TAG        = "s47-s2-criteria"
ENABLE_PY_COMPILE = True
# ======================================================================

# Anchor: the entire section from Group 3 through to md["stage_2"] = s2
# This captures the ST trend group, price leadership, RS, count and ladder.
ANCHOR = """\
        # Group 3 — ST trend
        s2_t5 = (ma50 is not None and ma150 is not None and ma50 > ma150)
        s2["tests"]["T5_50_above_150"] = s2_t5
        s2["groups"]["g3_st_trend"] = {"T5": s2_t5}

        # Group 4 — Price leadership
        s2_t6 = (price is not None and h52 is not None and h52 > 0 and price >= h52 * 0.75)
        s2_t7 = (price is not None and l52 is not None and l52 > 0 and price > l52 * 1.25)
        s2["tests"]["T6_within_25pct_52WH"] = s2_t6
        s2["tests"]["T7_above_25pct_52WL"] = s2_t7
        s2["groups"]["g4_price_leadership"] = {"T6": s2_t6, "T7": s2_t7}

        # Group 5 — Relative strength
        s2_t8 = (rs_vs_sec is not None and rs_vs_sec >= 70)
        s2_t9 = (rs_vs_ind is not None and rs_vs_ind >= 70)
        s2_t10 = (rs_pct is not None and rs_pct >= 70)
        s2["tests"]["T8_RS_vs_sector_70"] = s2_t8
        s2["tests"]["T9_RS_vs_industry_70"] = s2_t9
        s2["tests"]["T10_RS_vs_market_70"] = s2_t10
        s2["groups"]["g5_rs"] = {"T8": s2_t8, "T9": s2_t9, "T10": s2_t10}

        s2_count = sum(1 for t in [s2_t1, s2_t2, s2_t3, s2_t4, s2_t5, s2_t6, s2_t7, s2_t8, s2_t9, s2_t10] if t)
        s2["count"] = s2_count
        if s2_count >= 7:
            s2["rating"] = "Probable"
        elif s2_count == 6:
            s2["rating"] = "Plausible"
        elif s2_count == 5:
            s2["rating"] = "Possible"
        else:
            s2["rating"] = "None"
        md["stage_2"] = s2"""

REPLACEMENT = """\
        # Group 3 — ST trend
        # MD-V2-S47-S2-NEW-CRITERIA-MARKER (18-May-26, D-MD-V2-113):
        # Added T11 (50D>200D), T12 (50D rising d/d), moved to Group 3.
        # T13 (150D rising d/d) added to Group 2 below.
        s2_t5 = (ma50 is not None and ma150 is not None and ma50 > ma150)
        s2_t11 = (ma50 is not None and ma200 is not None and ma50 > ma200)
        s2_t12 = (ma50 is not None and ma50_prev is not None and ma50 > ma50_prev)
        s2["tests"]["T5_50_above_150"] = s2_t5
        s2["tests"]["T11_50_above_200"] = s2_t11
        s2["tests"]["T12_50D_rising"] = s2_t12
        s2["groups"]["g3_st_trend"] = {"T5": s2_t5, "T11": s2_t11, "T12": s2_t12}

        # T13 — 150D MA rising (day-over-day). Logically belongs to Group 2
        # (MT trend) but added here to keep diff localised. Appended to g2.
        s2_t13 = (ma150 is not None and ma150_prev is not None and ma150 > ma150_prev)
        s2["tests"]["T13_150D_rising"] = s2_t13
        s2["groups"]["g2_mt_trend"]["T13"] = s2_t13

        # Group 4 — Price leadership
        s2_t6 = (price is not None and h52 is not None and h52 > 0 and price >= h52 * 0.75)
        s2_t7 = (price is not None and l52 is not None and l52 > 0 and price > l52 * 1.25)
        s2["tests"]["T6_within_25pct_52WH"] = s2_t6
        s2["tests"]["T7_above_25pct_52WL"] = s2_t7
        s2["groups"]["g4_price_leadership"] = {"T6": s2_t6, "T7": s2_t7}

        # Group 5 — Relative strength
        s2_t8 = (rs_vs_sec is not None and rs_vs_sec >= 70)
        s2_t9 = (rs_vs_ind is not None and rs_vs_ind >= 70)
        s2_t10 = (rs_pct is not None and rs_pct >= 70)
        s2["tests"]["T8_RS_vs_sector_70"] = s2_t8
        s2["tests"]["T9_RS_vs_industry_70"] = s2_t9
        s2["tests"]["T10_RS_vs_market_70"] = s2_t10
        s2["groups"]["g5_rs"] = {"T8": s2_t8, "T9": s2_t9, "T10": s2_t10}

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
        else:
            s2["rating"] = "None"
        md["stage_2"] = s2"""


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
    print(f"[OK] Next: git add scripts/generate_master_data.py && git commit -m 'feat(MD V2 S47): Stage 2 — add T11/T12/T13 + new 13-test ladder (D-MD-V2-113)'")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
