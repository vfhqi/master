"""
=============================================================================
S43 Item #4 — Breaking Out rating override (no "Possible" tier)
=============================================================================
Date:    2026-05-17
Origin:  Richard's brief, Session 43 (autonomous batch)

WHAT THIS CHANGES
-----------------
Replaces the default _pre_rating ladder for the "breakout" indicator
specifically with a tighter custom rating:

  - 2/2 (price AND volume confirm) → "Probable"
  - Only T1 passes (price up 8%+ above 5D MA, no volume)  → "Plausible"
  - Only T2 passes (volume only, no price move)            → "None"
  - 0/2                                                     → "None"

Volume alone (T2 without T1) does NOT make a breakout — it's volume noise.
Volume ALONE used to fire "Possible" via the default ladder; that "Possible"
tier is deprecated for this indicator per Richard's 17-May-26 brief.

`ind["breakout"]` (the boolean fed into Probing Bet / VCP / Healthy Retest
qualification logic downstream) is UNCHANGED — still requires both tests.

WHAT THIS DOES NOT CHANGE
--------------------------
- The two underlying tests (price > MA5 × 1.08; up/down vol ≥ 1.10).
- The 5D MA-of-volume window (10D up/down volume).
- The _pre_rating ladder used by other indicators (advancing, breakdowns,
  collapsing, basing, pulling_back_uptrend, probing_bet, healthy_retest,
  vcp_after_s1_plateau, vcp_after_s2_base).
- ind["breakout"] boolean (still both-tests-pass).

DOWNSTREAM IMPACT
-----------------
After this patcher applies and refresh_all.py runs:
- Stocks currently rated "Possible Breakout" with only volume confirming will
  flip to "None" — they are NOT breakouts.
- Stocks currently rated "Possible Breakout" with only the price test
  passing will flip to "Plausible" — visible breakout, awaiting volume.
- "Probable Breakout" count unchanged (was 2/2; still 2/2).

ROLLBACK
--------
git revert <commit>, then run refresh_all.py.
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
MARKER         = "MD-V2-S43-BREAKOUT-RATING-OVERRIDE-MARKER"
BAK_TAG        = "breakout-rating-override-s43"
ENABLE_PY_COMPILE = True
# ======================================================================

ANCHOR = """        # ---- Indicator: Breakout (2 tests) ----
        bo_t1_price = bool(price is not None and ma5 is not None and ma5 > 0 and price > ma5 * 1.08)
        bo_t2_vol = bool(adv_10d_up_v > 0 and adv_10d_dn_v > 0 and adv_10d_up_v >= adv_10d_dn_v * 1.10)
        bo_tests = {"t1_price_gt_108pct_5dma": bo_t1_price, "t2_updown_vol_ge110": bo_t2_vol}
        bo_count = sum(1 for v in bo_tests.values() if v)
        ind["breakout"] = bool(bo_count == 2)"""

REPLACEMENT = """        # ---- Indicator: Breakout (2 tests) ----  MD-V2-S43-BREAKOUT-RATING-OVERRIDE-MARKER
        # S43 (17-May-26, brief Item #4): the default 3-tier _pre_rating ladder
        # is REPLACED with a custom 3-tier rating that deprecates "Possible":
        #   - 2/2 (price AND volume)               → "Probable"
        #   - Only T1 (price up 8%, no volume)     → "Plausible"
        #   - Only T2 (volume only, no price)      → "None"
        #   - 0/2                                  → "None"
        # Rationale: volume alone is NOT a breakout - it's volume noise. The
        # price test is necessary; the volume test is the confirming condition.
        # Downstream ind["breakout"] boolean is unchanged - still requires both.
        bo_t1_price = bool(price is not None and ma5 is not None and ma5 > 0 and price > ma5 * 1.08)
        bo_t2_vol = bool(adv_10d_up_v > 0 and adv_10d_dn_v > 0 and adv_10d_up_v >= adv_10d_dn_v * 1.10)
        bo_tests = {"t1_price_gt_108pct_5dma": bo_t1_price, "t2_updown_vol_ge110": bo_t2_vol}
        bo_count = sum(1 for v in bo_tests.values() if v)
        if bo_t1_price and bo_t2_vol:
            bo_rating_s43 = "Probable"
        elif bo_t1_price:
            bo_rating_s43 = "Plausible"
        else:
            bo_rating_s43 = "None"
        ind["breakout"] = bool(bo_count == 2)"""
# ======================================================================

# Second edit: the post_indicators breakout block uses _pre_rating; swap to bo_rating_s43
ANCHOR_PI = """            "breakout": {
                "tests": bo_tests, "count": bo_count, "total": 2,
                "rating": _pre_rating(bo_count, 2), "qualifies": ind["breakout"],"""

REPLACEMENT_PI = """            "breakout": {
                "tests": bo_tests, "count": bo_count, "total": 2,
                "rating": bo_rating_s43, "qualifies": ind["breakout"],"""


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


def _git_show_head_text(repo, rel):
    rel_posix = rel.replace(os.sep, "/")
    out = subprocess.run(["git", "show", f"HEAD:{rel_posix}"], cwd=repo, check=True, capture_output=True)
    return out.stdout.decode("utf-8")


def _wt_text(repo, rel):
    with open(os.path.join(repo, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def _md5_text(s): return hashlib.md5(s.encode("utf-8")).hexdigest()


def main(argv):
    test_mode = "--test" in argv
    repo = _find_repo_root()
    rel = TARGET_REL
    abs_target = os.path.join(repo, rel)

    print(f"[*] Repo:           {repo}")
    print(f"[*] Target:         {rel}")
    print(f"[*] Marker:         {MARKER}")
    print(f"[*] Mode:           {'DRY-RUN' if test_mode else 'WRITE'}")

    head_src = _git_show_head_text(repo, rel)
    wt_src   = _wt_text(repo, rel)
    print(f"[*] HEAD chars:     {len(head_src)}")
    print(f"[*] WT chars:       {len(wt_src)}")

    if _md5_text(wt_src) != _md5_text(head_src):
        msg = "Working tree diverges from HEAD (text-normalized compare)."
        if test_mode:
            print(f"[WARN] {msg}")
            print("       Dry-run continues -- gates operate on HEAD source.")
        else:
            print(f"[ABORT] {msg}")
            return 2

    if MARKER in head_src:
        print(f"[OK] MARKER already in HEAD -- this patch has already shipped.")
        return 0
    if MARKER in wt_src:
        print(f"[OK] MARKER already in WT but not in HEAD.")
        return 0

    n1 = head_src.count(ANCHOR)
    n2 = head_src.count(ANCHOR_PI)
    print(f"[*] Anchor 1 matches: {n1} (expected 1)")
    print(f"[*] Anchor 2 matches: {n2} (expected 1)")
    if n1 != 1 or n2 != 1:
        print(f"[ABORT] anchor count mismatch")
        return 3

    new_src = head_src.replace(ANCHOR, REPLACEMENT, 1).replace(ANCHOR_PI, REPLACEMENT_PI, 1)
    assert MARKER in new_src, "[INTERNAL] MARKER missing after replace"

    print(f"[*] Char delta:     {len(new_src) - len(head_src):+d}")

    if ENABLE_PY_COMPILE:
        try:
            ast.parse(new_src)
        except SyntaxError as e:
            print(f"[ABORT] ast.parse failed: {e}")
            return 4
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tf:
            tf.write(new_src); tmp_py = tf.name
        try:
            py_compile.compile(tmp_py, doraise=True)
            print(f"[*] py_compile:     OK")
        except py_compile.PyCompileError as e:
            print(f"[ABORT] py_compile: {e}")
            return 5
        finally:
            try: os.unlink(tmp_py)
            except OSError: pass

    print("\n--- DIFF (unified) ---")
    sys.stdout.writelines(difflib.unified_diff(
        head_src.splitlines(keepends=True),
        new_src.splitlines(keepends=True),
        fromfile=f"HEAD:{rel}", tofile=f"PATCHED:{rel}", n=2,
    ))
    print("--- END DIFF ---\n")

    if test_mode:
        print("[OK] DRY-RUN: gates passed.")
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
        print(f"[ABORT] post-write md5 mismatch. Restore: {os.path.relpath(bak, repo)}")
        return 6
    if MARKER not in after:
        print("[ABORT] MARKER missing post-write.")
        return 7

    print(f"[OK] WRITE complete. {len(after)} chars. MARKER present.")
    print(f"[OK] Next: run refresh_all.py (Windows-side, ~17 min), Chrome-verify, commit, push.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
