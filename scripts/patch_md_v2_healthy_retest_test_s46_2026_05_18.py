"""
=============================================================================
PATCHER — Healthy Retest of Upwards MA test (new test added alongside ma_retest_upwards)
=============================================================================
Project: SA - Master Dashboard
Session: S46 (18-May-2026)
Decision: D-MD-V2-108 + D-MD-V2-109 + D-MD-V2-111 (locked 18-May-2026)
Author: [W] Watson (SYSTEMS ARCHITECT role) under Richard's direction
Template: PATCHER-TEMPLATE.py (D-MD-INFRA-5 text-mode I/O)

WHAT THIS PATCHER DOES
----------------------
INSERTS a new test entry "healthy_retest" into md["tests"] in
`generate_master_data.py`, immediately after the existing
tests["ma_retest_upwards"] block. The existing ma_retest_upwards test is
LEFT UNCHANGED to preserve the current capital deployment test page during
the transition; both will coexist until the dashboard side is updated to
render the new healthy_retest test and the old ma_retest_upwards test
is retired in a follow-up patcher.

The new healthy_retest test implements Richard's S46 brief §8.2 spec:

  Group A: Stage 2 hard precondition (rating Probable or Plausible)
  Group B: pulling-back-uptrend inlined (4 tests; all 4 required for Possible+)
  Group C: 6 healthy-retest setup tests (reuse mr_setup_t1-t6 above)
  Group D: reclaim + confirmation triggers (reuse mr_trig_* above)
  13 criteria total; stage gate is hard precondition (D-MD-V2-109)

Rating ladder (per S46 brief §8.2):
  Qualified  = stage OK + Group B all + Group C ≥ 3/6 + Reclaim + Confirmation
  Probable   = stage OK + Group B all + Group C ≥ 3/6 + Reclaim
  Plausible  = stage OK + Group B all + Group C ≥ 3/6
  Possible   = stage OK + Group B all
  None       = otherwise (stage failed OR Group B not all true)

Qualifies-gate: True iff rating == "Qualified".

REUSE OF EXISTING UPSTREAM COMPUTE
-----------------------------------
Because healthy_retest is inserted in the same function scope IMMEDIATELY
AFTER the ma_retest_upwards block, all the upstream local variables are
still in scope and reused without recomputation:

  pb_t1_50d_rising, pb_t2_150d_rising, pb_t3_5d_rolling, pb_t4_10d_rolling
    -> Group B (4 pulling-back tests; computed earlier in the function)
  mr_setup_t1_vol_contracting ... mr_setup_t6_buying_l10d
    -> Group C (6 healthy-retest setup tests; computed in ma_retest_upwards)
  mr_trig_reclaim, mr_trig_confirmation
    -> Group D (2 trigger tests; computed in ma_retest_upwards)
  utr_test_ma, utr_retest_counts, utr_vol_trend, utr_updown_ratio,
  utr_dist_days, utr_pullback_contraction, utr_candle_quality_10d
    -> info + test_values display fields (already filter-output upstream)
  _test_ma_val, price, close_pct_change_today, s2
    -> already in scope

KNOWN LIMITATION — criterion 12 (reclaim) is NOT yet 10-day windowed
---------------------------------------------------------------------
Richard's brief §8.2 specifies criterion 12 as "Reclaimed the MA in last
10 days". The existing mr_trig_reclaim is `price > _test_ma_val` (price now
above the test MA) with NO 10-day window. Adding the window requires a new
field in the upstream uptrend_retest filter ("days since price was last
below the test MA"). v1 ships with the simple reclaim check; the window
enhancement is a follow-up patcher. Recorded in info_window_note inside
the test entry.

WHAT THIS PATCHER DOES NOT DO
-----------------------------
- Does NOT modify ma_retest_upwards.
- Does NOT modify build_dashboard.py. The new test field appears in JSON
  but the dashboard does not render it yet. The dashboard tab build is a
  follow-up patcher (Patcher D / Patcher E in the S46 sequence).
- Does NOT change the existing test ordering, only inserts between
  ma_retest_upwards and vcp_deploy_s1.

USAGE
-----
1. Dry-run from sandbox:
       python3 scripts/patch_md_v2_healthy_retest_test_s46_2026_05_18.py --test
2. Apply Windows-side (clean WT):
       python scripts/patch_md_v2_healthy_retest_test_s46_2026_05_18.py
       python scripts/refresh_all.py     (~17 min)
       python scripts/build_dashboard.py
       git add scripts/generate_master_data.py index.html
       git commit -m "feat(MD V2 S46): add healthy_retest test (D-MD-V2-108)"
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
MARKER         = "MD-V2-S46-HEALTHY-RETEST-MARKER"
BAK_TAG        = "s46-healthy-retest"
ENABLE_PY_COMPILE = True
# ======================================================================

ANCHOR = """                "x2_confirmation_close_ge2pct": _md_v2_round(close_pct_change_today),
            },
        }

        # ---- Test: VCP after Stage 1->2 (vcp_deploy_s1) ----  D-MD-V2-64/65"""

REPLACEMENT = """                "x2_confirmation_close_ge2pct": _md_v2_round(close_pct_change_today),
            },
        }

        # ---- Test: Healthy retest of upwards MA (healthy_retest) ----
        # MD-V2-S46-HEALTHY-RETEST-MARKER (18-May-26, D-MD-V2-108)
        # New "Core MM trade" test per Richard's S46 brief §8.2. Coexists
        # with ma_retest_upwards above during transition; dashboard render
        # is a follow-up patcher. Architecture per D-MD-V2-108:
        #   Group A: Stage 2 hard precondition (D-MD-V2-109)
        #   Group B: pulling-back-uptrend inlined (4 tests, all required)
        #   Group C: 6 healthy-retest setup tests (reuse mr_setup_t1-t6)
        #   Group D: reclaim + confirmation (reuse mr_trig_* above)
        # 13 criteria total. Today's-close confirmation per D-MD-V2-111.
        # v1: criterion 12 (reclaim) uses mr_trig_reclaim ("price > MA now");
        # the 10-day window enhancement is a follow-up patcher (needs new
        # upstream field in uptrend_retest filter).
        hr_stage_qualifies = bool(s2.get("rating") in ("Probable", "Plausible"))
        hr_b1_50d_rising = bool(pb_t1_50d_rising)
        hr_b2_150d_rising = bool(pb_t2_150d_rising)
        hr_b3_5d_declining = bool(pb_t3_5d_rolling)
        hr_b4_10d_declining = bool(pb_t4_10d_rolling)
        hr_tests = {
            "g1_stage_2_qualifies": hr_stage_qualifies,
            "g2_b1_50d_rising": hr_b1_50d_rising,
            "g2_b2_150d_rising": hr_b2_150d_rising,
            "g2_b3_5d_declining": hr_b3_5d_declining,
            "g2_b4_10d_declining": hr_b4_10d_declining,
            "g3_c1_volume_contracting": mr_setup_t1_vol_contracting,
            "g3_c2_up_vol_gt_down_vol": mr_setup_t2_updown_ge105,
            "g3_c3_few_distribution_days": mr_setup_t3_few_dist_days,
            "g3_c4_volatility_reducing": mr_setup_t4_volatility_contracting,
            "g3_c5_testing_meaningful_ma": mr_setup_t5_testing_ma,
            "g3_c6_buying_through_l10d": mr_setup_t6_buying_l10d,
            "g4_d1_reclaimed_ma": mr_trig_reclaim,
            "g4_d2_confirmation_close_ge2pct": mr_trig_confirmation,
        }
        hr_count = sum(1 for v in hr_tests.values() if v)
        _hr_group_b_all = bool(hr_b1_50d_rising and hr_b2_150d_rising and
                               hr_b3_5d_declining and hr_b4_10d_declining)
        _hr_group_c_count = sum([
            1 if mr_setup_t1_vol_contracting else 0,
            1 if mr_setup_t2_updown_ge105 else 0,
            1 if mr_setup_t3_few_dist_days else 0,
            1 if mr_setup_t4_volatility_contracting else 0,
            1 if mr_setup_t5_testing_ma else 0,
            1 if mr_setup_t6_buying_l10d else 0,
        ])
        if not hr_stage_qualifies:
            hr_rating = "None"
        elif not _hr_group_b_all:
            hr_rating = "None"
        elif _hr_group_c_count < 3:
            hr_rating = "Possible"
        elif not mr_trig_reclaim:
            hr_rating = "Plausible"
        elif not mr_trig_confirmation:
            hr_rating = "Probable"
        else:
            hr_rating = "Qualified"
        hr_qualifies = bool(hr_rating == "Qualified")
        tests["healthy_retest"] = {
            "tests": hr_tests, "count": hr_count, "total": 13,
            "rating": hr_rating,
            "qualifies": hr_qualifies,
            "info_ma_retested": utr_test_ma,
            "info_retest_count": (utr_retest_counts.get(utr_test_ma) if utr_test_ma else None),
            "info_window_note": "v1: criterion 12 is 'price > MA now'; 10-day window enhancement deferred to follow-up patcher",
            "test_values": {
                "g1_stage_2_qualifies": (s2.get("rating") if hr_stage_qualifies else "not S2 P/P"),
                "g2_b1_50d_rising": ("rising" if hr_b1_50d_rising else "not rising"),
                "g2_b2_150d_rising": ("rising" if hr_b2_150d_rising else "not rising"),
                "g2_b3_5d_declining": ("declining" if hr_b3_5d_declining else "not declining"),
                "g2_b4_10d_declining": ("declining" if hr_b4_10d_declining else "not declining"),
                "g3_c1_volume_contracting": _md_v2_round(utr_vol_trend, 3),
                "g3_c2_up_vol_gt_down_vol": _md_v2_round(utr_updown_ratio, 3),
                "g3_c3_few_distribution_days": utr_dist_days,
                "g3_c4_volatility_reducing": _md_v2_round(utr_pullback_contraction, 3),
                "g3_c5_testing_meaningful_ma": (utr_test_ma if utr_test_ma else "none"),
                "g3_c6_buying_through_l10d": _md_v2_round(utr_candle_quality_10d, 3),
                "g4_d1_reclaimed_ma": _md_v2_pct_gap(price, _test_ma_val),
                "g4_d2_confirmation_close_ge2pct": _md_v2_round(close_pct_change_today),
            },
        }

        # ---- Test: VCP after Stage 1->2 (vcp_deploy_s1) ----  D-MD-V2-64/65"""


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
