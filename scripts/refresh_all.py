"""
Master Dashboard — Full data refresh orchestrator
=================================================

Single command runs the complete data pipeline with backup-and-restore
atomicity at the orchestrator layer.

Steps (in order):
  1. Backup data/*.json to data/.pre-refresh-{timestamp}/
  2. generate_master_data.py --full-universe --with-history
  3. validate_filter_history.py        ← HARD GATE (exit 2 = restore + abort)
  4. generate_chart_data.py --live     (skipped if --skip-charts or --dry-run)
  5. build_dashboard.py                (skipped if --dry-run)

If any step fails, the pre-run backup is restored so previous good data
stays in place.

Flags:
  --skip-charts   Skip step 4 (use for table-only refreshes; ~10x faster)
  --dry-run       Run steps 1-3 only; skip step 4 and step 5
  --no-restore    Don't restore backup on failure (debugging only)
  --quiet         Reduce per-step logging

Exit codes:
  0 = all steps clean
  1 = validation passed with warnings
  2 = validation or build failed (backup restored unless --no-restore)
  3 = upstream script (gen-master-data / gen-chart-data) failed

Authored: 11-May-26. See D-MD-INFRA-1, C17.
"""

import argparse
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"

# Files that get backed up before refresh and restored on failure.
BACKED_UP_FILES = [
    "prices.json",
    "filter-results.json",
    "filter-history.json",
    "stage-snapshots.json",
]


def fmt_size(n):
    """Human-readable byte count."""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}TB"


def fmt_elapsed(s):
    if s < 60:
        return f"{s:.1f}s"
    m, s = divmod(s, 60)
    return f"{int(m)}m{int(s):02d}s"


def step(label, n_total, n, args):
    print()
    print(f"━━━ STEP {n}/{n_total}: {label}")


def run_script(script_name, script_args, args):
    """Run a script as subprocess. Returns (exit_code, elapsed_seconds)."""
    cmd = [sys.executable, str(SCRIPT_DIR / script_name)] + list(script_args)
    t0 = time.time()
    print(f"  exec: {' '.join(cmd[1:])}")
    try:
        r = subprocess.run(cmd, cwd=str(PROJECT_DIR), check=False)
        elapsed = time.time() - t0
        print(f"  exit code: {r.returncode}  elapsed: {fmt_elapsed(elapsed)}")
        return r.returncode, elapsed
    except Exception as e:
        elapsed = time.time() - t0
        print(f"  EXCEPTION: {e}  elapsed: {fmt_elapsed(elapsed)}")
        return -1, elapsed


def make_backup(args):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = DATA_DIR / f".pre-refresh-{ts}"
    backup_dir.mkdir(exist_ok=False)
    backed = []
    for f in BACKED_UP_FILES:
        src = DATA_DIR / f
        if src.exists():
            dst = backup_dir / f
            shutil.copy2(src, dst)
            backed.append((f, src.stat().st_size))
    print(f"  backup dir: {backup_dir}")
    for name, size in backed:
        print(f"    {name:32s} {fmt_size(size)}")
    return backup_dir


def restore_backup(backup_dir, args):
    print(f"\n  RESTORING from {backup_dir}")
    restored = []
    for f in BACKED_UP_FILES:
        src = backup_dir / f
        if src.exists():
            dst = DATA_DIR / f
            shutil.copy2(src, dst)
            restored.append(f)
    print(f"  restored {len(restored)} file(s)")


def main():
    ap = argparse.ArgumentParser(description="Master Dashboard data refresh orchestrator")
    ap.add_argument("--skip-charts", action="store_true", help="Skip chart regen (much faster)")
    ap.add_argument("--dry-run", action="store_true", help="Skip chart regen AND dashboard build")
    ap.add_argument("--no-restore", action="store_true", help="Don't restore backup on failure (debug only)")
    ap.add_argument("--quiet", action="store_true", help="Reduce logging")
    ap.add_argument("--seed-test-history", type=int, default=0, metavar="N",
                    help="MD-V2-S39-T-C-REFRESH-PASSTHROUGH: pass-through to generate_master_data.py - back-create N days of test history (cap 20). 0 = no seeding (default)")
    args = ap.parse_args()

    n_total = 5
    if args.skip_charts or args.dry_run:
        n_total -= 1
    if args.dry_run:
        n_total -= 1

    print("=" * 60)
    print(f"Master Dashboard refresh — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if args.dry_run:
        print("(DRY RUN — chart regen + dashboard build skipped)")
    elif args.skip_charts:
        print("(skipping chart regen)")
    print("=" * 60)

    t_start = time.time()

    # ───── Step 1: Backup ─────
    step("Backup existing data files", n_total, 1, args)
    try:
        backup_dir = make_backup(args)
    except FileExistsError:
        # Sub-second collision: append a counter
        for i in range(1, 10):
            try:
                backup_dir = DATA_DIR / f".pre-refresh-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{i}"
                backup_dir.mkdir(exist_ok=False)
                break
            except FileExistsError:
                continue
        backup_dir = make_backup(args)
    except Exception as e:
        print(f"  ERROR creating backup: {e}")
        sys.exit(3)

    # ───── Step 2: generate_master_data.py ─────
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
    )
    if rc != 0:
        print(f"  FAIL: generate_master_data.py exited with code {rc}")
        if not args.no_restore:
            restore_backup(backup_dir, args)
        sys.exit(3)

    # Report data file sizes
    print("  data file sizes after step 2:")
    for f in BACKED_UP_FILES:
        p = DATA_DIR / f
        if p.exists():
            print(f"    {f:32s} {fmt_size(p.stat().st_size)}")

    # ───── Step 3: validate_filter_history.py (HARD GATE) ─────
    step("Validate filter-history integrity", n_total, 3, args)
    rc, elapsed = run_script(
        "validate_filter_history.py",
        ["--quiet"] if args.quiet else [],
        args,
    )
    if rc == 2:
        print(f"  HARD FAIL: validator returned error exit code 2")
        if not args.no_restore:
            restore_backup(backup_dir, args)
        sys.exit(2)
    elif rc == 1:
        print(f"  validator returned warnings (exit 1) — proceeding")
    else:
        print(f"  validator clean (exit 0)")

    # ───── Step 4: generate_chart_data.py --live ─────
    if args.dry_run or args.skip_charts:
        print(f"\n━━━ STEP {'-'}/{n_total}: Chart regen — SKIPPED")
    else:
        step("Regenerate chart data (--live)", n_total, 4, args)
        rc, elapsed = run_script("generate_chart_data.py", ["--live"], args)
        if rc != 0:
            print(f"  FAIL: generate_chart_data.py exited with code {rc}")
            if not args.no_restore:
                restore_backup(backup_dir, args)
            sys.exit(3)

    # ───── Step 5: build_dashboard.py ─────
    if args.dry_run:
        print(f"\n━━━ STEP {'-'}/{n_total}: Dashboard build — SKIPPED (dry run)")
    else:
        last_step = 5 if not (args.skip_charts or args.dry_run) else 4
        step("Build dashboard (index.html)", n_total, last_step, args)
        rc, elapsed = run_script("build_dashboard.py", [], args)
        if rc != 0:
            print(f"  FAIL: build_dashboard.py exited with code {rc}")
            if not args.no_restore:
                restore_backup(backup_dir, args)
            sys.exit(3)
        # Final size
        idx = PROJECT_DIR / "index.html"
        if idx.exists():
            print(f"  index.html: {fmt_size(idx.stat().st_size)}")

    # ───── Done ─────
    total_elapsed = time.time() - t_start
    print()
    print("=" * 60)
    print(f"REFRESH COMPLETE — {fmt_elapsed(total_elapsed)}")
    print(f"Backup retained at: {backup_dir.relative_to(PROJECT_DIR)}")
    print("=" * 60)

    sys.exit(0)


if __name__ == "__main__":
    main()
