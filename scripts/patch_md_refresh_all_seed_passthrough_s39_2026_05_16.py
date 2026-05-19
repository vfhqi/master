"""
SA - Master Dashboard | Patcher: refresh_all.py --seed-test-history pass-through (S39 T-C)

Companion to patch_md_v2_tc_seed_depth_20_s39_2026_05_16.py.

Why this exists:
    MANIFEST Invariant 16 says all data writes go through refresh_all.py
    (D-MD-INFRA-4). Standalone generate_master_data.py runs are debug-only
    and must NOT be pushed. But refresh_all.py at HEAD does not accept
    --seed-test-history -- it hard-codes ["--full-universe", "--with-history"]
    when calling generate_master_data.py.

    For the T-C one-off seed (20-day backfill of test-history.json), Richard
    needs to run the seed through refresh_all.py to retain the orchestrator's
    backup + validate_filter_history HARD GATE + atomicity guarantees.

What this patches:
    EDIT A: add --seed-test-history N argparse arg to refresh_all.py
    EDIT B: pass the arg through to generate_master_data.py when N > 0

After this ships, the one-off backfill is:
    python scripts\\refresh_all.py --seed-test-history 20

That call gets the orchestrator's safety net AND the deeper seed in one go.

Run order on Windows-side (after the docs patcher has shipped):
    python scripts\\patch_md_refresh_all_seed_passthrough_s39_2026_05_16.py --test
    python scripts\\patch_md_refresh_all_seed_passthrough_s39_2026_05_16.py
    python scripts\\refresh_all.py --seed-test-history 20    # the actual backfill
    # refresh_all does its own commit-ready output -- normal git add/commit/push afterward
"""
from __future__ import annotations
import ast, datetime as _dt, difflib, hashlib, os, py_compile, subprocess, sys, tempfile

REPO_ROOT_HINT = "master-dashboard"
TARGET_REL = os.path.join("scripts", "refresh_all.py")
MARKER = "MD-V2-S39-T-C-REFRESH-PASSTHROUGH"
BAK_TAG = "refresh-seed-passthrough"

# --- EDIT A: add the argparse arg, inserted before `args = ap.parse_args()` ---
ANCHOR_A = """    ap.add_argument("--quiet", action="store_true", help="Reduce logging")
    args = ap.parse_args()"""

REPLACEMENT_A = """    ap.add_argument("--quiet", action="store_true", help="Reduce logging")
    ap.add_argument("--seed-test-history", type=int, default=0, metavar="N",
                    help="MD-V2-S39-T-C-REFRESH-PASSTHROUGH: pass-through to generate_master_data.py - back-create N days of test history (cap 20). 0 = no seeding (default)")
    args = ap.parse_args()"""

# --- EDIT B: pass --seed-test-history through to generate_master_data.py ---
ANCHOR_B = """    # ───── Step 2: generate_master_data.py ─────
    step("Regenerate master data (--full-universe --with-history)", n_total, 2, args)
    rc, elapsed = run_script(
        "generate_master_data.py",
        ["--full-universe", "--with-history"],
        args,
    )"""

REPLACEMENT_B = """    # ───── Step 2: generate_master_data.py ─────
    _gmd_args = ["--full-universe", "--with-history"]
    if getattr(args, "seed_test_history", 0) > 0:
        # MD-V2-S39-T-C-REFRESH-PASSTHROUGH: one-off seed backfill mode.
        _gmd_args.extend(["--seed-test-history", str(args.seed_test_history)])
        _label = "Regenerate master data (--full-universe --with-history --seed-test-history %d)" % args.seed_test_history
    else:
        _label = "Regenerate master data (--full-universe --with-history)"
    step(_label, n_total, 2, args)
    rc, elapsed = run_script(
        "generate_master_data.py",
        _gmd_args,
        args,
    )"""

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
    raise SystemExit("[ABORT] cannot locate repo root")

def _git_show_head_text(repo, rel):
    out = subprocess.run(["git", "show", f"HEAD:{rel.replace(os.sep,'/')}"], cwd=repo, check=True, capture_output=True)
    return out.stdout.decode("utf-8")

def _wt_text(repo, rel):
    with open(os.path.join(repo, rel), "r", encoding="utf-8") as f: return f.read()

def _md5(s): return hashlib.md5(s.encode("utf-8")).hexdigest()

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
    if _md5(wt_src) != _md5(head_src):
        if test_mode:
            print("[WARN] WT diverges from HEAD (text-normalized); dry-run continues.")
        else:
            print("[ABORT] WT diverges from HEAD")
            return 2

    if MARKER in head_src:
        print("[OK] MARKER already in HEAD -- already shipped.")
        return 0
    if MARKER in wt_src:
        print("[OK] MARKER already in WT not HEAD -- applied but not committed.")
        return 0

    edits = [("EDIT A (argparse)", ANCHOR_A, REPLACEMENT_A),
             ("EDIT B (pass-through)", ANCHOR_B, REPLACEMENT_B)]
    new_src = head_src
    for label, anchor, repl in edits:
        n = new_src.count(anchor)
        print(f"[*] {label}: anchor matches = {n} (expected 1)")
        if n != 1:
            print(f"[ABORT] {label}: anchor count != 1")
            return 3
        new_src = new_src.replace(anchor, repl, 1)

    assert MARKER in new_src, "INTERNAL: MARKER missing post-replace"
    print(f"[*] Char delta:     {len(new_src) - len(head_src):+d}")

    try: ast.parse(new_src)
    except SyntaxError as e:
        print(f"[ABORT] ast.parse failed: {e}"); return 4
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tf:
        tf.write(new_src); tmp_py = tf.name
    try: py_compile.compile(tmp_py, doraise=True); print("[*] py_compile:     OK")
    except py_compile.PyCompileError as e:
        print(f"[ABORT] py_compile failed: {e}"); return 5
    finally:
        try: os.unlink(tmp_py)
        except OSError: pass

    print("\n--- DIFF ---")
    sys.stdout.writelines(difflib.unified_diff(
        head_src.splitlines(keepends=True), new_src.splitlines(keepends=True),
        fromfile=f"HEAD:{rel}", tofile=f"PATCHED:{rel}", n=2))
    print("--- END DIFF ---\n")

    if test_mode:
        print("[OK] DRY-RUN: gates passed. Re-run without --test to write.")
        return 0

    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = abs_target + f".bak-pre-{BAK_TAG}-{ts}"
    with open(bak, "w", encoding="utf-8") as f: f.write(wt_src)
    print(f"[*] Backup:         {os.path.relpath(bak, repo)}")

    target_dir = os.path.dirname(abs_target)
    fd, tmp_out = tempfile.mkstemp(prefix=".patch-", suffix=".tmp", dir=target_dir)
    os.close(fd)
    with open(tmp_out, "w", encoding="utf-8") as f: f.write(new_src)
    os.replace(tmp_out, abs_target)

    after = _wt_text(repo, rel)
    if _md5(after) != _md5(new_src):
        print(f"[ABORT] post-write md5 mismatch! Restore: {os.path.relpath(bak, repo)}")
        return 6
    if MARKER not in after:
        print("[ABORT] post-write MARKER missing"); return 7

    print(f"[OK] WRITE complete. {len(after)} chars, {os.path.getsize(abs_target)} bytes. MARKER present.")
    print(f"[OK] Next: python scripts/refresh_all.py --seed-test-history 20")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
