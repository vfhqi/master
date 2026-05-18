"""
=============================================================================
PATCHER C — Extend `mas` dict with 5-day-ago and 6-day-ago MA lookups
=============================================================================
Project: SA - Master Dashboard
Session: S46 (18-May-2026)
Author: [W] Watson (SYSTEMS ARCHITECT role)
Template: PATCHER-TEMPLATE.py (D-MD-INFRA-5 text-mode I/O)

WHAT THIS PATCHER DOES
----------------------
Adds two lines to the `mas` dict builder in `generate_master_data.py`
(line ~387) that expose the moving-average value from 5 trading days ago
and 6 trading days ago for every SMA period. The new keys are:
  mas[f"{p}D_5d_ago"]   -> the SMA value 5 trading days ago
  mas[f"{p}D_6d_ago"]   -> the SMA value 6 trading days ago

WHY
---
Prerequisite for the Probing/Speculative Bet test (Patcher D / D-MD-V2-108).
That test's criterion 5 ("20D MA is rising AND was falling 5 days ago")
needs the 20D MA from 5 and 6 trading days ago to detect a recent MA turn.
The mas dict currently only carries today + yesterday. This patcher closes
that gap.

Data source: `rows_with_sma[-6]` and `rows_with_sma[-7]` (already in scope
where mas is built; no upstream filter changes required). Returns None when
history is shorter than 7 rows.

WHAT THIS PATCHER DOES NOT DO
-----------------------------
- Does NOT touch dashboard rendering.
- Does NOT touch any tests or indicators that use the existing mas keys.
- Does NOT change any default behaviour. Adds new keys only.

USAGE
-----
1. Dry-run from sandbox:
       python3 scripts/patch_md_v2_mas_5d_lookback_s46_2026_05_18.py --test
2. Apply Windows-side (clean WT):
       python scripts/patch_md_v2_mas_5d_lookback_s46_2026_05_18.py
       python scripts/refresh_all.py     (~17 min — regenerates filter-results.json)
       (No build needed unless other patchers also applied)
       git add scripts/generate_master_data.py
       git commit -m "feat(MD V2 S46): expose 5d-ago + 6d-ago MA lookups in mas dict (prereq for D-MD-V2-108)"
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
MARKER         = "MD-V2-S46-MAS-5D-LOOKBACK-MARKER"
BAK_TAG        = "s46-mas-5d-lookback"
ENABLE_PY_COMPILE = True

ANCHOR = """        # Build MAs dict (current + previous day for DoD comparison)
        mas = {}
        for p in SMA_PERIODS:
            key = f"sma_{p}"
            mas[f"{p}D"] = latest.get(key)
            mas[f"{p}D_prev"] = prev.get(key)"""

REPLACEMENT = """        # Build MAs dict (current + previous day for DoD comparison)
        # MD-V2-S46-MAS-5D-LOOKBACK-MARKER (18-May-26): also expose 5d-ago + 6d-ago
        # MA values to enable the Probing/Spec test (D-MD-V2-108) criterion 5
        # ("20D MA rising AND was falling 5 days ago" -> 5-day actionability window).
        mas = {}
        for p in SMA_PERIODS:
            key = f"sma_{p}"
            mas[f"{p}D"] = latest.get(key)
            mas[f"{p}D_prev"] = prev.get(key)
            mas[f"{p}D_5d_ago"] = rows_with_sma[-6].get(key) if len(rows_with_sma) >= 6 else None
            mas[f"{p}D_6d_ago"] = rows_with_sma[-7].get(key) if len(rows_with_sma) >= 7 else None"""


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
