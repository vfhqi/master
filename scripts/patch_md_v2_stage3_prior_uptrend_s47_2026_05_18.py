"""
=============================================================================
PATCHER S3 — Stage 3 prior-uptrend gate + T7 tighten + display column
=============================================================================
Project: SA - Master Dashboard
Session: S47 (18-May-2026)
Decision: D-MD-V2-114 (locked 18-May-2026)
Author: [W] Watson (SYSTEMS ARCHITECT role) under Richard's direction
Template: PATCHER-TEMPLATE.py (D-MD-INFRA-5 text-mode I/O)

WHAT THIS PATCHER DOES
----------------------
Three changes to the Stage 3 block in generate_master_data.py:

1. HARD PRECONDITION — prior-uptrend gate:
   Computes ma200_m6 (200D MA six months ago) and ma200_m7 (seven months
   ago) from the existing ma200_samples monthly array. Derives
   prior_uptrend = bool(ma200_m6 > ma200_m7). After the existing rating
   computation, if prior_uptrend is False, forces rating to "None".
   Rationale: Stage 3 (topping) should only fire if the stock was
   previously in a Stage 2 uptrend. Closes the Tecqnion false-positive.

2. T7 TIGHTEN:
   Replaces the soft test `price <= ma50 * 1.05` with the strict
   `price < ma50 AND ma50 < ma50_prev` (both "price under the 50D"
   AND "50D rolling over" must hold).

3. DISPLAY COLUMN in test_values for Group 1:
   Emits both boolean (prior_uptrend) and numeric pct change of 200D
   MA between seven and six months ago in s3["test_values"]. The
   dashboard's existing %-vs-yes/no toggle handles display.

WHAT THIS PATCHER DOES NOT DO
-----------------------------
- Does NOT change the rating ladder thresholds (still 6→Probable,
  4→Plausible, 2→Possible, else→None).
- Does NOT touch build_dashboard.py.
- Does NOT touch any other Stage block.

USAGE
-----
1. Dry-run:
       python3 scripts/patch_md_v2_stage3_prior_uptrend_s47_2026_05_18.py --test
2. Apply (clean WT, per-patcher commit cycle):
       python scripts/patch_md_v2_stage3_prior_uptrend_s47_2026_05_18.py
       git add scripts/generate_master_data.py
       git commit -m "feat(MD V2 S47): Stage 3 — prior-uptrend gate + T7 tighten + display col (D-MD-V2-114)"
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
MARKER         = "MD-V2-S47-S3-PRIOR-UPTREND-MARKER"
BAK_TAG        = "s47-s3-uptrend"
ENABLE_PY_COMPILE = True
# ======================================================================

# Anchor: from the T7 line through md["stage_3"] = s3
# We need the T7 line and everything below it in the Stage 3 block.
ANCHOR = """\
        # No-breakout test #7 — price fails > 5% above 50D for 5+ days
        # Approximation: price within 5% of 50D currently
        s3_t7 = (price is not None and ma50 is not None and ma50 > 0 and price <= ma50 * 1.05)
        s3["tests"]["T5_volume_down_up_ratio"] = s3_t5
        s3["tests"]["T6_volatility_increase"] = s3_t6
        s3["tests"]["T7_no_breakout"] = s3_t7
        s3["groups"]["g3_debate"] = {"T5": s3_t5, "T6": s3_t6, "T7": s3_t7}

        # Group 4 — Lower lows
        s3_t8 = lower_lows >= 2
        s3_t9 = lower_lows >= 3
        s3["tests"]["T8_lower_lows_1m"] = s3_t8
        s3["tests"]["T9_lower_lows_3m"] = s3_t9
        s3["groups"]["g4_lower_lows"] = {"T8": s3_t8, "T9": s3_t9}

        # Group 5 — RS trend (current vs M-3 < 80%)
        # Use rs_returns 3M as proxy for relative RS-now vs RS-then. Negative 3M = weakening.
        s3_t10 = False
        rs_3m = rs_returns.get("3M")
        if rs_3m is not None:
            # Stock vs benchmark return last 3M is weak (< 80% means stock has lost ground)
            # Threshold: rs_3m < -0.05 (lost 5%+ vs benchmark in 3M) = trend weakening
            s3_t10 = rs_3m < -0.05
        s3["tests"]["T10_RS_trend_weakening"] = s3_t10
        s3["groups"]["g5_rs_trend"] = {"T10": s3_t10}

        s3_count = sum(1 for t in [s3_t1, s3_t2, s3_t3, s3_t4, s3_t5, s3_t6, s3_t7, s3_t8, s3_t9, s3_t10] if t)
        s3["count"] = s3_count
        if s3_count >= 6:
            s3["rating"] = "Probable Invalidation"
        elif s3_count >= 4:
            s3["rating"] = "Plausible Invalidation"
        elif s3_count >= 2:
            s3["rating"] = "Possible Topping"
        else:
            s3["rating"] = "None"
        md["stage_3"] = s3"""

REPLACEMENT = """\
        # MD-V2-S47-S3-PRIOR-UPTREND-MARKER (18-May-26, D-MD-V2-114):
        # T7 tightened: strict price < 50D AND 50D rolling over (was: price <= 50D * 1.05).
        s3_t7 = (price is not None and ma50 is not None and ma50_prev is not None
                 and price < ma50 and ma50 < ma50_prev)
        s3["tests"]["T5_volume_down_up_ratio"] = s3_t5
        s3["tests"]["T6_volatility_increase"] = s3_t6
        s3["tests"]["T7_price_below_50d_and_50d_rolling"] = s3_t7
        s3["groups"]["g3_debate"] = {"T5": s3_t5, "T6": s3_t6, "T7": s3_t7}

        # Group 4 — Lower lows
        s3_t8 = lower_lows >= 2
        s3_t9 = lower_lows >= 3
        s3["tests"]["T8_lower_lows_1m"] = s3_t8
        s3["tests"]["T9_lower_lows_3m"] = s3_t9
        s3["groups"]["g4_lower_lows"] = {"T8": s3_t8, "T9": s3_t9}

        # Group 5 — RS trend (current vs M-3 < 80%)
        # Use rs_returns 3M as proxy for relative RS-now vs RS-then. Negative 3M = weakening.
        s3_t10 = False
        rs_3m = rs_returns.get("3M")
        if rs_3m is not None:
            # Stock vs benchmark return last 3M is weak (< 80% means stock has lost ground)
            # Threshold: rs_3m < -0.05 (lost 5%+ vs benchmark in 3M) = trend weakening
            s3_t10 = rs_3m < -0.05
        s3["tests"]["T10_RS_trend_weakening"] = s3_t10
        s3["groups"]["g5_rs_trend"] = {"T10": s3_t10}

        s3_count = sum(1 for t in [s3_t1, s3_t2, s3_t3, s3_t4, s3_t5, s3_t6, s3_t7, s3_t8, s3_t9, s3_t10] if t)
        s3["count"] = s3_count
        if s3_count >= 6:
            s3["rating"] = "Probable Invalidation"
        elif s3_count >= 4:
            s3["rating"] = "Plausible Invalidation"
        elif s3_count >= 2:
            s3["rating"] = "Possible Topping"
        else:
            s3["rating"] = "None"

        # Prior-uptrend hard precondition (D-MD-V2-114):
        # Stage 3 should only fire if the stock was previously in Stage 2.
        # Proxy: 200D MA was rising 6-7 months ago (ma200_m6 > ma200_m7).
        ma200_m6 = ma200_samples[-7] if len(ma200_samples) >= 7 else None
        ma200_m7 = ma200_samples[-8] if len(ma200_samples) >= 8 else None
        prior_uptrend = bool(ma200_m6 is not None and ma200_m7 is not None and ma200_m6 > ma200_m7)
        if not prior_uptrend:
            s3["rating"] = "None"

        # Display column: prior_uptrend boolean + pct change for Group 1.
        # Dashboard's existing %-vs-yes/no toggle handles the display.
        prior_uptrend_pct = None
        if ma200_m6 is not None and ma200_m7 is not None and ma200_m7 > 0:
            prior_uptrend_pct = round(((ma200_m6 - ma200_m7) / ma200_m7) * 100, 2)
        s3["prior_uptrend"] = prior_uptrend
        s3["test_values"] = {
            "prior_uptrend": prior_uptrend,
            "prior_uptrend_pct": prior_uptrend_pct,
        }

        md["stage_3"] = s3"""


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
    print(f"[OK] Next: git add scripts/generate_master_data.py && git commit -m 'feat(MD V2 S47): Stage 3 — prior-uptrend gate + T7 tighten + display col (D-MD-V2-114)'")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
