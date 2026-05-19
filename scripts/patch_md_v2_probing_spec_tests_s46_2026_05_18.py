"""
=============================================================================
PATCHER D — Probing / Speculative Bet four-variant test (S46)
=============================================================================
Project: SA - Master Dashboard
Session: S46 (18-May-2026)
Decisions: D-MD-V2-108, D-MD-V2-109, D-MD-V2-110, D-MD-V2-111 (locked 18-May-2026)
Divergence 1 resolution: Option A (5D + 10D rising as test-internal criteria)
Prerequisite: Patcher C (MD-V2-S46-MAS-5D-LOOKBACK-MARKER) must be applied first
Author: [W] Watson (SYSTEMS ARCHITECT role) under Richard's direction
Template: PATCHER-TEMPLATE.py (D-MD-INFRA-5 text-mode I/O)

WHAT THIS PATCHER DOES
----------------------
Inserts four new test entries into md["tests"] in `generate_master_data.py`,
between the existing tests["vcp"] back-compat alias and `md["tests"] = tests`.
The four are stage-parameterised variants of one underlying test:

  tests["probing_bet_s1"]      -- Stage 1 MT troughing trend + breakout
  tests["probing_bet_s2"]      -- Stage 2 MT/LT uptrend + breakout
  tests["speculative_bet_s3"]  -- Stage 3 MT breaking-down trend + breakout
  tests["speculative_bet_s4"]  -- Stage 4 MT/LT downtrend + breakout

Underlying test (same logic across all four variants):
  Group A: Stage X hard precondition (D-MD-V2-109; the stage gate is which
           variant fires for which stock — see "Stage gate" below)
  Group B: 5D MA rising + 10D MA rising (test-internal per Divergence 1
           Option A locked S46; NOT promoted to pre-indicators)
  Group C: Price > 20D MA + 20D MA turn + today's-close follow-through
           (where "turn" = 20D rising now AND was falling 5 days ago,
           giving a 5-day actionability window per Richard's S46 brief §8.1)

6 criteria total per variant. Today's-close confirmation per D-MD-V2-111.
Stage gate per D-MD-V2-109 (hard precondition; stock outside the named stage
gets rating None regardless of other criteria).

RATING LADDER (per S46 brief §8.1)
-----------------------------------
  Qualified = Group B both + C1 + C2 + C3 (all 5 scored criteria)
  Probable  = Group B both + C1 + C2
  Plausible = Group B both AND (C1 OR C2)
  Possible  = Group B both
  None      = stage gate failed OR Group B not both true

Qualifies-gate: True iff rating == "Qualified".

STAGE GATE SEMANTICS
--------------------
For each variant, the stage gate fires if the stock's matching stage rating
is at any non-None level (Possible / Plausible / Probable). This is a wide
gate by design — the variant LABELS the bet by stage rather than restricting
it to one tier. v1 will overlap with the Core MM trade pages for Stage 2
stocks that also pass the Healthy Retest or Basing/VCP tests; this overlap
is accepted in v1 and may be refined in v2 (e.g. exclude Stage 2 stocks that
already pass a Core MM trade test).

PREREQUISITE
------------
Patcher C (MD-V2-S46-MAS-5D-LOOKBACK-MARKER) must be applied first; this
patcher consumes mas[f"{p}D_5d_ago"] and mas[f"{p}D_6d_ago"]. Patcher D's
own gates do NOT check this (no anchor in the mas dict); if Patcher C is
not applied, the test logic here will read None from the missing mas keys
and the 20D turn check will always be False. Recommend apply order:
  1. Patcher A (pulling-back ladder)
  2. Patcher B (healthy retest test)
  3. Patcher C (mas 5d lookback)   <-- BEFORE Patcher D
  4. Patcher D (probing/spec tests) <-- THIS PATCHER

REPLACES the existing tests["probing_bet"]? NO.
---------------------------------------------------
The existing tests["probing_bet"] block (the legacy 3-test version)
remains in place untouched. Both will coexist in md["tests"] during the
transition. The dashboard will be updated in a follow-up patcher to render
the four new entries and (eventually) remove the legacy probing_bet.

USAGE
-----
1. Dry-run from sandbox:
       python3 scripts/patch_md_v2_probing_spec_tests_s46_2026_05_18.py --test
2. Apply Windows-side (clean WT, Patcher C already applied):
       python scripts/patch_md_v2_probing_spec_tests_s46_2026_05_18.py
       python scripts/refresh_all.py     (~17 min)
       python scripts/build_dashboard.py
       git add scripts/generate_master_data.py index.html
       git commit -m "feat(MD V2 S46): add probing_bet_s1/s2 + speculative_bet_s3/s4 tests (D-MD-V2-108/110)"
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

REPO_ROOT_HINT = "master-dashboard"
TARGET_REL     = os.path.join("scripts", "generate_master_data.py")
MARKER         = "MD-V2-S46-PROBING-SPEC-MARKER"
BAK_TAG        = "s46-probing-spec"
ENABLE_PY_COMPILE = True

ANCHOR = """        tests["vcp"] = {
            "qualifies": bool(vd1_qualifies or vd2_qualifies),
            "_note": "S27: vcp test split into vcp_deploy_s1 + vcp_deploy_s2; this alias = OR of both.",
        }

        md["tests"] = tests"""

REPLACEMENT = """        tests["vcp"] = {
            "qualifies": bool(vd1_qualifies or vd2_qualifies),
            "_note": "S27: vcp test split into vcp_deploy_s1 + vcp_deploy_s2; this alias = OR of both.",
        }

        # ---- Tests: Probing bet (S1, S2) + Speculative bet (S3, S4) ----
        # MD-V2-S46-PROBING-SPEC-MARKER (18-May-26, D-MD-V2-108 + D-MD-V2-110)
        # Four stage-parameterised variants of one underlying test per Richard's
        # S46 brief §8.1. Architecture:
        #   Group A: Stage X hard precondition (D-MD-V2-109; variant differs by stage)
        #   Group B: 5D rising + 10D rising (test-internal per Divergence 1 Option A)
        #   Group C: P > 20D + 20D turn (rising now + was falling 5d ago) + today's close +2%
        # 6 criteria. Today's-close confirmation per D-MD-V2-111.
        # PREREQUISITE: requires Patcher C (MD-V2-S46-MAS-5D-LOOKBACK-MARKER)
        # for mas["20D_5d_ago"] / mas["20D_6d_ago"]. Without Patcher C, the
        # 20D turn check reads None and is always False (degrades gracefully;
        # tests still compute but never reach Probable+).
        ps_ma5_now = mas.get("5D")
        ps_ma5_prev = mas.get("5D_prev")
        ps_ma10_now = mas.get("10D")
        ps_ma10_prev = mas.get("10D_prev")
        ps_ma20_now = mas.get("20D")
        ps_ma20_prev = mas.get("20D_prev")
        ps_ma20_5d_ago = mas.get("20D_5d_ago")
        ps_ma20_6d_ago = mas.get("20D_6d_ago")
        ps_b1_5d_rising = bool(ps_ma5_now is not None and ps_ma5_prev is not None and ps_ma5_now > ps_ma5_prev)
        ps_b2_10d_rising = bool(ps_ma10_now is not None and ps_ma10_prev is not None and ps_ma10_now > ps_ma10_prev)
        ps_c1_price_gt_20d = bool(price is not None and ps_ma20_now is not None and price > ps_ma20_now)
        ps_c2_ma20_now_rising = bool(ps_ma20_now is not None and ps_ma20_prev is not None and ps_ma20_now > ps_ma20_prev)
        ps_c2_ma20_was_falling_5d_ago = bool(ps_ma20_5d_ago is not None and ps_ma20_6d_ago is not None and ps_ma20_5d_ago < ps_ma20_6d_ago)
        ps_c2_ma20_turn = bool(ps_c2_ma20_now_rising and ps_c2_ma20_was_falling_5d_ago)
        ps_c3_followthrough = bool(close_pct_change_today is not None and close_pct_change_today >= 0.02)

        def _ps_rating(stage_qualifies):
            if not stage_qualifies:
                return "None"
            if not (ps_b1_5d_rising and ps_b2_10d_rising):
                return "None"
            if ps_c1_price_gt_20d and ps_c2_ma20_turn and ps_c3_followthrough:
                return "Qualified"
            if ps_c1_price_gt_20d and ps_c2_ma20_turn:
                return "Probable"
            if ps_c1_price_gt_20d or ps_c2_ma20_turn:
                return "Plausible"
            return "Possible"

        def _ps_build(stage_qualifies, variant_key, stage_rating_value):
            ps_tests = {
                "g1_stage_qualifies": stage_qualifies,
                "g2_5d_rising": ps_b1_5d_rising,
                "g3_10d_rising": ps_b2_10d_rising,
                "g4_price_gt_20d": ps_c1_price_gt_20d,
                "g5_20d_turn_last_5d": ps_c2_ma20_turn,
                "g6_followthrough_close_ge2pct": ps_c3_followthrough,
            }
            ps_count = sum(1 for v in ps_tests.values() if v)
            ps_rating = _ps_rating(stage_qualifies)
            return {
                "tests": ps_tests, "count": ps_count, "total": 6,
                "rating": ps_rating,
                "qualifies": bool(ps_rating == "Qualified"),
                "info_variant": variant_key,
                "info_stage_rating": stage_rating_value,
                "test_values": {
                    "g1_stage_qualifies": (stage_rating_value if stage_qualifies else "not in stage"),
                    "g2_5d_rising": ("rising" if ps_b1_5d_rising else "not rising"),
                    "g3_10d_rising": ("rising" if ps_b2_10d_rising else "not rising"),
                    "g4_price_gt_20d": _md_v2_pct_gap(price, ps_ma20_now),
                    "g5_20d_turn_last_5d": (
                        "turn (rising now, falling 5d ago)" if ps_c2_ma20_turn
                        else "rising but no recent turn" if ps_c2_ma20_now_rising
                        else "not rising"
                    ),
                    "g6_followthrough_close_ge2pct": _md_v2_round(close_pct_change_today),
                },
            }

        # Stage gates per variant. Stage X must be at any non-None rating
        # (Possible+/Plausible+/Probable+) for the variant to fire.
        _s1_rating_val = s1.get("rating") if isinstance(s1, dict) else None
        _s2_rating_val = s2.get("rating") if isinstance(s2, dict) else None
        _s3_rating_val = s3.get("rating") if isinstance(s3, dict) else None
        _s4_rating_val = s4.get("rating") if isinstance(s4, dict) else None
        _s1_in = bool(_s1_rating_val not in (None, "None"))
        _s2_in = bool(_s2_rating_val not in (None, "None"))
        _s3_in = bool(_s3_rating_val not in (None, "None"))
        _s4_in = bool(_s4_rating_val not in (None, "None"))

        tests["probing_bet_s1"] = _ps_build(_s1_in, "probing_bet_s1", _s1_rating_val)
        tests["probing_bet_s2"] = _ps_build(_s2_in, "probing_bet_s2", _s2_rating_val)
        tests["speculative_bet_s3"] = _ps_build(_s3_in, "speculative_bet_s3", _s3_rating_val)
        tests["speculative_bet_s4"] = _ps_build(_s4_in, "speculative_bet_s4", _s4_rating_val)

        md["tests"] = tests"""


def _find_repo_root():
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


def _md5_text(s):
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
    wt_src = _wt_text(repo, rel)
    print(f"[*] HEAD chars:     {len(head_src)}")
    print(f"[*] WT chars:       {len(wt_src)}")
    print(f"[*] HEAD md5(text): {_md5_text(head_src)}")
    print(f"[*] WT md5(text):   {_md5_text(wt_src)}")
    if _md5_text(wt_src) != _md5_text(head_src):
        msg = "Working tree diverges from HEAD (text-normalized compare)."
        if test_mode:
            print(f"[WARN] {msg}\n       Dry-run continues -- gates operate on HEAD source.")
        else:
            print(f"[ABORT] {msg}")
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
    assert MARKER in new_src
    print(f"[*] Char delta:     {len(new_src) - len(head_src):+d}")
    print(f"[*] New md5(text):  {_md5_text(new_src)}")
    if ENABLE_PY_COMPILE:
        ast.parse(new_src)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tf:
            tf.write(new_src); tmp_py = tf.name
        try:
            py_compile.compile(tmp_py, doraise=True)
            print(f"[*] py_compile:     OK")
        finally:
            try: os.unlink(tmp_py)
            except OSError: pass
    print("\n--- DIFF (unified, text-normalized) ---")
    sys.stdout.writelines(difflib.unified_diff(
        head_src.splitlines(keepends=True), new_src.splitlines(keepends=True),
        fromfile=f"HEAD:{rel}", tofile=f"PATCHED:{rel}", n=2))
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
    assert _md5_text(after) == _md5_text(new_src) and MARKER in after
    print(f"[OK] WRITE complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
