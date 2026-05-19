"""
SA - Master Dashboard | Patcher: T-C test-history seed depth 6 -> 20 (S39, S34 carry)

What this changes:
    Three documentation strings in `scripts/generate_master_data.py`. No code-
    enforced limit exists; the "cap 6" was a 14-May-26 shake-out-phase
    convention. Pipeline already supports up to 20 (TEST_HISTORY_WINDOWS["l20d"]
    = 20; TEST_HISTORY_MAX_KEEP = 30).

After this patch ships, Richard runs ONCE on Windows-side:
    python scripts\\generate_master_data.py --seed-test-history 20

That call back-creates 20 days of historical per-test qualify records into
`data/test-history.json`. From then on, the daily pipeline appends today,
and the L5D/L20D window fields in the dashboard read fully-populated history.

Built from PROJECTS/SA - Master Dashboard/PATCHER-TEMPLATE.py (16-May-26).
Text-mode I/O throughout per D-MD-INFRA-5.

Three sequential edits in a single patcher:
    EDIT 1: header comment "Per Richard 14-May-26: ... 6 days for the shake-out"
    EDIT 2: TEST_HISTORY_WINDOWS docstring "smaller knob (Richard: 6 for now)"
    EDIT 3: CLI arg help text "(Richard cap: 6)"

Run order on Windows-side:
    python scripts\\patch_md_v2_tc_seed_depth_20_s39_2026_05_16.py --test
    python scripts\\patch_md_v2_tc_seed_depth_20_s39_2026_05_16.py
    python scripts\\generate_master_data.py --seed-test-history 20   # one-off backfill
    python scripts\\build_dashboard.py
    git add scripts/generate_master_data.py data/test-history.json index.html
    git commit -m "feat(MD V2): S39 T-C - bump test-history seed depth 6 -> 20 + backfill"
    git push
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
TARGET_REL = os.path.join("scripts", "generate_master_data.py")
MARKER = "MD-V2-S39-T-C-SEED-DEPTH-20"
BAK_TAG = "tc-seed-depth-20"

# --- EDIT 1: header comment block ---
ANCHOR_1 = """# The one-off SEED (apply_test_history with seed=N) re-evaluates the 4
# deployment tests at recent historical bar slices to back-create history.
# Per Richard 14-May-26: seed depth capped at 6 days for the shake-out
# phase (cheap to regenerate if a test definition changes); the format and
# the dashboard degradation handle up to 20, so a later full backfill is
# just a deeper seed run, no re-architecting."""

REPLACEMENT_1 = """# The one-off SEED (apply_test_history with seed=N) re-evaluates the 4
# deployment tests at recent historical bar slices to back-create history.
# Per Richard 16-May-26 (S39 T-C, MD-V2-S39-T-C-SEED-DEPTH-20): seed depth
# bumped from 6 to 20 days now that the shake-out phase is done. Run
# --seed-test-history 20 once Windows-side to fully populate; daily pipeline
# appends from there. Format supports up to 20 natively; TEST_HISTORY_MAX_KEEP
# (30 days) gives one week of cushion before the rolling-window trim kicks in."""

# --- EDIT 2: TEST_HISTORY_WINDOWS docstring ---
ANCHOR_2 = """# Window sizes (trading days). Format supports up to 20; seed depth is a
# separate, smaller knob (Richard: 6 for now)."""

REPLACEMENT_2 = """# Window sizes (trading days). Format supports up to 20; seed depth knob
# bumped to 20 per S39 T-C (Richard 16-May-26). See header comment above."""

# --- EDIT 3: CLI help text ---
ANCHOR_3 = """    parser.add_argument("--seed-test-history", type=int, default=0, metavar="N", help="MD-V2-TESTS-S27-MARKER: one-off - back-create N days of deployment-test history (Richard cap: 6)")"""

REPLACEMENT_3 = """    parser.add_argument("--seed-test-history", type=int, default=0, metavar="N", help="MD-V2-TESTS-S27-MARKER: one-off - back-create N days of deployment-test history (Richard cap: 20 per S39 T-C, MD-V2-S39-T-C-SEED-DEPTH-20)")"""


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

    # --- 3 sequential anchor checks ---
    edits = [
        ("EDIT 1 (header comment)", ANCHOR_1, REPLACEMENT_1),
        ("EDIT 2 (windows docstring)", ANCHOR_2, REPLACEMENT_2),
        ("EDIT 3 (CLI help)", ANCHOR_3, REPLACEMENT_3),
    ]
    new_src = head_src
    for label, anchor, replacement in edits:
        n = new_src.count(anchor)
        print(f"[*] {label}: anchor matches = {n} (expected 1)")
        if n != 1:
            print(f"[ABORT] {label}: anchor count != 1")
            return 3
        new_src = new_src.replace(anchor, replacement, 1)
        assert new_src.count(replacement) == 1, f"[INTERNAL] {label}: replacement count != 1"

    assert MARKER in new_src, "[INTERNAL] MARKER missing after replace"
    delta = len(new_src) - len(head_src)
    print(f"[*] Char delta:     {delta:+d}")
    print(f"[*] New md5(text):  {_md5_text(new_src)}")

    # py_compile gate
    try:
        ast.parse(new_src)
    except SyntaxError as e:
        print(f"[ABORT] ast.parse failed: {e}")
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

    print("\n--- DIFF (unified) ---")
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
    print(f"[OK] Next: python scripts/generate_master_data.py --seed-test-history 20   # one-off backfill")
    print(f"[OK]       python scripts/build_dashboard.py")
    print(f"[OK]       git add scripts/generate_master_data.py data/test-history.json index.html")
    print(f"[OK]       git commit -m \"feat(MD V2): S39 T-C - bump test-history seed depth 6 -> 20 + backfill\" && git push")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
