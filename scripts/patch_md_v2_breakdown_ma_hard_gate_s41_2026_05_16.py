"""
=============================================================================
PATCHER — S41 — Break-down indicators: HARD MA-precondition gate (Diasorin fix)
=============================================================================
Brief items #8 / #9 / #10 (Session 41, 16-May-26):

  #8  200D break down: HARD GATE on (MA20 > MA200). If the gate FAILS,
                       force rating to "None" and qualifies=False regardless
                       of T1/T2. Filters DIASORIN-class false positives
                       out of the rated universe entirely.
  #9  150D break down: same HARD GATE on (MA10 > MA150).
  #10 50D  break down: same HARD GATE on (MA5  > MA50).

WHY HARD GATE NOT THIRD TEST
----------------------------
A previous version of this patcher (.SUPERSEDED-pollutes-plausible-bucket)
added the MA-precondition as a counted THIRD TEST with total=3. Preview run
on real data showed that this elevates ~500 stocks per indicator from
Possible to Plausible — because a stock with MA-short above MA-long and
ONE of T1/T2 partially firing now scores 2/3 = 66.7%, the Plausible
threshold. That's semantically wrong: "Plausible breakdown" should mean
"close to a real breakdown", not "this stock's short MA is above its long
MA". The third-test version polluted the Plausible bucket.

Hard gate: T3 is NOT in the count. It's a precondition. Tests stay /2,
rating ladder unchanged. If T3 fails, rating is forced to "None" and
qualifies=False. The T3 result is still emitted in test_values so the
filter mechanism is transparent in per-test displays.

TARGET
------
master-dashboard/scripts/generate_master_data.py — both:
  (a) the three breakdown_{50D,150D,200D} blocks at L2146-2165, and
  (b) the post_indicators dict at L2190-2213.

POST-RUN
--------
    python scripts/refresh_all.py
    python scripts/build_dashboard.py
    git add scripts/generate_master_data.py scripts/build_dashboard.py index.html data/
    git commit -m "S41 break-down MA hard gate (#8/#9/#10) — Diasorin fix"
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
MARKER         = "MD-V2-S41-BREAKDOWN-MA-HARD-GATE-MARKER"
BAK_TAG        = "s41-breakdown-ma-hard-gate"
ENABLE_PY_COMPILE = True
# ======================================================================

# ============ EDIT 1: the breakdown indicator block ===================
ANCHOR_1 = """        # ---- Indicator: Breakdown 50D (2 tests) ----
        bd50_t1 = bool(price is not None and ma50 is not None and price < ma50)
        bd50_t2 = bool(ma50_prev_v is not None and ma50_prev_v > 0 and _price_prev >= ma50_prev_v * 0.99)
        bd50_tests = {"t1_price_below_50dma": bd50_t1, "t2_prev_at_or_above_50dma": bd50_t2}
        bd50_count = sum(1 for v in bd50_tests.values() if v)
        ind["breakdown_50D"] = bool(bd50_count == 2)

        # ---- Indicator: Breakdown 150D (2 tests) ----
        bd150_t1 = bool(price is not None and ma150 is not None and price < ma150)
        bd150_t2 = bool(ma150_prev_v is not None and ma150_prev_v > 0 and _price_prev >= ma150_prev_v * 0.99)
        bd150_tests = {"t1_price_below_150dma": bd150_t1, "t2_prev_at_or_above_150dma": bd150_t2}
        bd150_count = sum(1 for v in bd150_tests.values() if v)
        ind["breakdown_150D"] = bool(bd150_count == 2)

        # ---- Indicator: Breakdown 200D (2 tests) ----
        bd200_t1 = bool(price is not None and ma200 is not None and price < ma200)
        bd200_t2 = bool(ma200_prev_v is not None and ma200_prev_v > 0 and _price_prev >= ma200_prev_v * 0.99)
        bd200_tests = {"t1_price_below_200dma": bd200_t1, "t2_prev_at_or_above_200dma": bd200_t2}
        bd200_count = sum(1 for v in bd200_tests.values() if v)
        ind["breakdown_200D"] = bool(bd200_count == 2)"""

REPLACEMENT_1 = """        # ---- Indicator: Breakdown 50D (2 tests + MA hard gate) ----  MD-V2-S41-BREAKDOWN-MA-HARD-GATE-MARKER
        # S41 (16-May-26, brief #10): MA-precondition HARD GATE on bd_50D_ma_gate
        # = (MA5 > MA50). NOT a counted test — if the gate fails, the indicator
        # is force-filtered (qualifies=False and rating="None" downstream).
        # Filters DIASORIN-class false positives (price nicks above MA from
        # below, falls back, T1+T2 trip without a real prior uptrend).
        ma5_v_bd = mas.get("5D")
        bd50_t1 = bool(price is not None and ma50 is not None and price < ma50)
        bd50_t2 = bool(ma50_prev_v is not None and ma50_prev_v > 0 and _price_prev >= ma50_prev_v * 0.99)
        bd50_ma_gate = bool(ma5_v_bd is not None and ma50 is not None and ma5_v_bd > ma50)
        bd50_tests = {"t1_price_below_50dma": bd50_t1, "t2_prev_at_or_above_50dma": bd50_t2}
        bd50_count = sum(1 for v in bd50_tests.values() if v)
        ind["breakdown_50D"] = bool(bd50_count == 2 and bd50_ma_gate)

        # ---- Indicator: Breakdown 150D (2 tests + MA hard gate) ----
        # S41 (16-May-26, brief #9): MA-precondition HARD GATE on
        # bd_150D_ma_gate = (MA10 > MA150). Same logic at MT timeframe.
        ma10_v_bd = mas.get("10D")
        bd150_t1 = bool(price is not None and ma150 is not None and price < ma150)
        bd150_t2 = bool(ma150_prev_v is not None and ma150_prev_v > 0 and _price_prev >= ma150_prev_v * 0.99)
        bd150_ma_gate = bool(ma10_v_bd is not None and ma150 is not None and ma10_v_bd > ma150)
        bd150_tests = {"t1_price_below_150dma": bd150_t1, "t2_prev_at_or_above_150dma": bd150_t2}
        bd150_count = sum(1 for v in bd150_tests.values() if v)
        ind["breakdown_150D"] = bool(bd150_count == 2 and bd150_ma_gate)

        # ---- Indicator: Breakdown 200D (2 tests + MA hard gate) ----
        # S41 (16-May-26, brief #8): MA-precondition HARD GATE on
        # bd_200D_ma_gate = (MA20 > MA200). THE DIASORIN FIX.
        ma20_v_bd = mas.get("20D")
        bd200_t1 = bool(price is not None and ma200 is not None and price < ma200)
        bd200_t2 = bool(ma200_prev_v is not None and ma200_prev_v > 0 and _price_prev >= ma200_prev_v * 0.99)
        bd200_ma_gate = bool(ma20_v_bd is not None and ma200 is not None and ma20_v_bd > ma200)
        bd200_tests = {"t1_price_below_200dma": bd200_t1, "t2_prev_at_or_above_200dma": bd200_t2}
        bd200_count = sum(1 for v in bd200_tests.values() if v)
        ind["breakdown_200D"] = bool(bd200_count == 2 and bd200_ma_gate)"""

# ============ EDIT 2: the post_indicators dict ========================
# Wrap _pre_rating(count, 2) so the hard gate forces "None" when MA gate fails.
# Also surface the gate value in test_values for transparency in per-test display.
ANCHOR_2 = """            "breakdown_50D": {
                "tests": bd50_tests, "count": bd50_count, "total": 2,
                "rating": _pre_rating(bd50_count, 2), "qualifies": ind["breakdown_50D"],
                "test_values": {
                    "t1_price_below_50dma": _md_v2_pct_gap(price, ma50),
                    "t2_prev_at_or_above_50dma": _md_v2_pct_gap(_price_prev, ma50_prev_v),
                },
            },
            "breakdown_150D": {
                "tests": bd150_tests, "count": bd150_count, "total": 2,
                "rating": _pre_rating(bd150_count, 2), "qualifies": ind["breakdown_150D"],
                "test_values": {
                    "t1_price_below_150dma": _md_v2_pct_gap(price, ma150),
                    "t2_prev_at_or_above_150dma": _md_v2_pct_gap(_price_prev, ma150_prev_v),
                },
            },
            "breakdown_200D": {
                "tests": bd200_tests, "count": bd200_count, "total": 2,
                "rating": _pre_rating(bd200_count, 2), "qualifies": ind["breakdown_200D"],
                "test_values": {
                    "t1_price_below_200dma": _md_v2_pct_gap(price, ma200),
                    "t2_prev_at_or_above_200dma": _md_v2_pct_gap(_price_prev, ma200_prev_v),
                },
            },"""

REPLACEMENT_2 = """            "breakdown_50D": {
                "tests": bd50_tests, "count": bd50_count, "total": 2,
                "rating": _pre_rating(bd50_count, 2) if bd50_ma_gate else "None",
                "qualifies": ind["breakdown_50D"],
                "ma_gate": {"name": "ma5_above_ma50", "passes": bd50_ma_gate},
                "test_values": {
                    "t1_price_below_50dma": _md_v2_pct_gap(price, ma50),
                    "t2_prev_at_or_above_50dma": _md_v2_pct_gap(_price_prev, ma50_prev_v),
                    "ma_gate_ma5_above_ma50": _md_v2_pct_gap(ma5_v_bd, ma50),
                },
            },
            "breakdown_150D": {
                "tests": bd150_tests, "count": bd150_count, "total": 2,
                "rating": _pre_rating(bd150_count, 2) if bd150_ma_gate else "None",
                "qualifies": ind["breakdown_150D"],
                "ma_gate": {"name": "ma10_above_ma150", "passes": bd150_ma_gate},
                "test_values": {
                    "t1_price_below_150dma": _md_v2_pct_gap(price, ma150),
                    "t2_prev_at_or_above_150dma": _md_v2_pct_gap(_price_prev, ma150_prev_v),
                    "ma_gate_ma10_above_ma150": _md_v2_pct_gap(ma10_v_bd, ma150),
                },
            },
            "breakdown_200D": {
                "tests": bd200_tests, "count": bd200_count, "total": 2,
                "rating": _pre_rating(bd200_count, 2) if bd200_ma_gate else "None",
                "qualifies": ind["breakdown_200D"],
                "ma_gate": {"name": "ma20_above_ma200", "passes": bd200_ma_gate},
                "test_values": {
                    "t1_price_below_200dma": _md_v2_pct_gap(price, ma200),
                    "t2_prev_at_or_above_200dma": _md_v2_pct_gap(_price_prev, ma200_prev_v),
                    "ma_gate_ma20_above_ma200": _md_v2_pct_gap(ma20_v_bd, ma200),
                },
            },"""
# ======================================================================


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


def main(argv: list[str]) -> int:
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
            return 2

    if MARKER in head_src:
        print(f"[OK] MARKER already in HEAD -- this patch has already shipped.")
        return 0
    if MARKER in wt_src:
        print(f"[OK] MARKER already in WT but not in HEAD -- applied but not committed yet.")
        return 0

    # Apply both edits
    n1 = head_src.count(ANCHOR_1)
    n2 = head_src.count(ANCHOR_2)
    print(f"[*] Anchor_1 matches: {n1} (expected 1)")
    print(f"[*] Anchor_2 matches: {n2} (expected 1)")
    if n1 != 1 or n2 != 1:
        print(f"[ABORT] Anchor count != 1 for at least one anchor -- source may have drifted.")
        return 3

    new_src = head_src.replace(ANCHOR_1, REPLACEMENT_1, 1)
    new_src = new_src.replace(ANCHOR_2, REPLACEMENT_2, 1)
    assert MARKER in new_src, "[INTERNAL] MARKER missing after replace"
    assert new_src.count(REPLACEMENT_1) == 1, "[INTERNAL] Replacement_1 count != 1"
    assert new_src.count(REPLACEMENT_2) == 1, "[INTERNAL] Replacement_2 count != 1"

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
    print(f"[OK] NEXT STEPS:")
    print(f"     1. python scripts/refresh_all.py        # full pipeline run (~17 min)")
    print(f"     2. python scripts/build_dashboard.py    # rebuild index.html")
    print(f"     3. git add scripts/generate_master_data.py scripts/build_dashboard.py index.html data/")
    print(f"     4. git commit -m 'S41 break-down MA hard gate (#8/#9/#10) — Diasorin fix'")
    print(f"     5. git push")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
