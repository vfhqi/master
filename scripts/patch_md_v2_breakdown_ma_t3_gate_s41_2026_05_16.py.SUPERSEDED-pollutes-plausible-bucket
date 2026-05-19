"""
=============================================================================
PATCHER — S41 — Break-down indicators: add MA-precondition T3 gate (Diasorin fix)
=============================================================================
Brief items #8 / #9 / #10 (Session 41, 16-May-26):

  #8  200D break down: add T3 = (MA20 > MA200). All 3 tests must pass for
                       a "Probable" rating. DIASORIN-class (T1+T2 pass but
                       no real prior uptrend) demotes to "Plausible".
  #9  150D break down: add T3 = (MA10 > MA150). Same demotion logic.
  #10 50D  break down: add T3 = (MA5  > MA50).  Same demotion logic.

DESIGN RATIONALE
----------------
The post_indicators rating ladder is the surface Richard sees on the
dashboard (`md["post_indicators"]["breakdown_<N>D"]["rating"]`). This
target (generate_master_data.py lines ~2146-2214) is the canonical source
of that rating.

Adding the MA-precondition as a THIRD TEST (rather than a hard precondition
gate that forces None) preserves visibility: stocks that fail T3 but pass
T1+T2 demote from "Probable" (3/3) to "Plausible" (2/3 = 0.667 >= 0.667),
so they remain in the rated universe at a lower confidence tier. The T3
test surfaces in the per-test display so the demotion mechanism is
transparent. Richard can still filter to "Probable only" via the chip
controls if he wants only high-confidence breakdowns.

ALTERNATIVE (if Richard prefers): hard-gate variant — `rating = "None"
and qualifies = False` whenever T3 fails. Would filter DIASORIN-class
stocks out of the rated universe entirely. Easy to switch to if the
"Plausible-tier" volume after this ship is too noisy.

TARGET
------
master-dashboard/scripts/generate_master_data.py — the three breakdown_{50D,
150D,200D} blocks under "Post-test trailing indicators" (lines ~2146-2214
at HEAD da98031).

POST-RUN
--------
    python scripts/refresh_all.py
    python scripts/build_dashboard.py
    git add scripts/generate_master_data.py scripts/build_dashboard.py index.html data/
    git commit -m "S41 break-down MA T3 gate (#8/#9/#10) — Diasorin fix"
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
MARKER         = "MD-V2-S41-BREAKDOWN-MA-T3-GATE-MARKER"
BAK_TAG        = "s41-breakdown-ma-t3-gate"
ENABLE_PY_COMPILE = True
# ======================================================================

# ============ EDIT: the actual textual change =========================
ANCHOR = """        # ---- Indicator: Breakdown 50D (2 tests) ----
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

REPLACEMENT = """        # ---- Indicator: Breakdown 50D (3 tests) ----  MD-V2-S41-BREAKDOWN-MA-T3-GATE-MARKER
        # S41 (16-May-26, brief #10): added T3 = MA5 > MA50 — confirms stock
        # was in a short-term uptrend BEFORE breaking down. Without this gate,
        # a stock that nicks above the MA from below for one day then falls
        # back trips T1+T2 as "Probable" (the DIASORIN-class false positive
        # at 200D; same shape applies at 50D).
        ma5_v_bd = mas.get("5D")
        bd50_t1 = bool(price is not None and ma50 is not None and price < ma50)
        bd50_t2 = bool(ma50_prev_v is not None and ma50_prev_v > 0 and _price_prev >= ma50_prev_v * 0.99)
        bd50_t3 = bool(ma5_v_bd is not None and ma50 is not None and ma5_v_bd > ma50)
        bd50_tests = {"t1_price_below_50dma": bd50_t1, "t2_prev_at_or_above_50dma": bd50_t2, "t3_ma5_above_ma50": bd50_t3}
        bd50_count = sum(1 for v in bd50_tests.values() if v)
        ind["breakdown_50D"] = bool(bd50_count == 3)

        # ---- Indicator: Breakdown 150D (3 tests) ----
        # S41 (16-May-26, brief #9): added T3 = MA10 > MA150 — same MT-trend gate.
        ma10_v_bd = mas.get("10D")
        bd150_t1 = bool(price is not None and ma150 is not None and price < ma150)
        bd150_t2 = bool(ma150_prev_v is not None and ma150_prev_v > 0 and _price_prev >= ma150_prev_v * 0.99)
        bd150_t3 = bool(ma10_v_bd is not None and ma150 is not None and ma10_v_bd > ma150)
        bd150_tests = {"t1_price_below_150dma": bd150_t1, "t2_prev_at_or_above_150dma": bd150_t2, "t3_ma10_above_ma150": bd150_t3}
        bd150_count = sum(1 for v in bd150_tests.values() if v)
        ind["breakdown_150D"] = bool(bd150_count == 3)

        # ---- Indicator: Breakdown 200D (3 tests) ----
        # S41 (16-May-26, brief #8): added T3 = MA20 > MA200 — the DIASORIN
        # fix. The original (T1+T2 only) test fires on any stock that ticks
        # above 200D from below for one day then falls back. T3 requires
        # the 20D MA to actually be above the 200D MA, confirming a real
        # LT uptrend was in place before today's break.
        ma20_v_bd = mas.get("20D")
        bd200_t1 = bool(price is not None and ma200 is not None and price < ma200)
        bd200_t2 = bool(ma200_prev_v is not None and ma200_prev_v > 0 and _price_prev >= ma200_prev_v * 0.99)
        bd200_t3 = bool(ma20_v_bd is not None and ma200 is not None and ma20_v_bd > ma200)
        bd200_tests = {"t1_price_below_200dma": bd200_t1, "t2_prev_at_or_above_200dma": bd200_t2, "t3_ma20_above_ma200": bd200_t3}
        bd200_count = sum(1 for v in bd200_tests.values() if v)
        ind["breakdown_200D"] = bool(bd200_count == 3)"""
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
    print(f"[OK] NEXT STEPS:")
    print(f"     1. python scripts/refresh_all.py        # full pipeline run (~17 min)")
    print(f"     2. python scripts/build_dashboard.py    # rebuild index.html")
    print(f"     3. git add scripts/generate_master_data.py scripts/build_dashboard.py index.html data/")
    print(f"     4. git commit -m 'S41 break-down MA T3 gate (#8/#9/#10) — Diasorin fix'")
    print(f"     5. git push")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
