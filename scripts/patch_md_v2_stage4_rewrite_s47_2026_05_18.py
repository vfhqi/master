"""
=============================================================================
PATCHER S4 — Stage 4 criteria rewrite + Stage-3 lookback INFO column
=============================================================================
Project: SA - Master Dashboard
Session: S47 (18-May-2026)
Decision: D-MD-V2-115 (locked 18-May-2026)
Author: [W] Watson (SYSTEMS ARCHITECT role) under Richard's direction
Template: PATCHER-TEMPLATE.py (D-MD-INFRA-5 text-mode I/O) — multi-anchor variant

WHAT THIS PATCHER DOES
----------------------
Two changes in generate_master_data.py, plus one infrastructure extension:

1. CRITERIA REWRITE — specific-combinations ladder:
   - t1 (200D declining) + t3 (total stack down) + t4 (150 < 200) + t5 (50 < 150) → Probable
   - If t2 (200D decline accelerating) also holds → "Probable (Accelerating)"
   - t4 + t5 → Plausible
   - t4 OR t5 → Possible
   - else → None
   Replaces the old count-based ladder (3/7→Probable, 2/7→Plausible, 1/7→Possible).

2. STAGE-3 LOOKBACK INFO COLUMN (display only, does NOT gate rating):
   Helper function `_stage_3_fired_in_last_60d(ticker, snapshots)` reads
   `data/stage-snapshots.json` for Stage 3 lifecycle rating history.
   Returns (fired_bool, days_ago, history_depth_ok).
   Result stored on md["stage_4"]["info_stage_3_lookback"].

3. INFRASTRUCTURE — extend `_save_daily_snapshot` to also persist
   Stage 3 lifecycle ratings alongside existing setup-stage data.
   This builds up the history the lookback helper reads. Until enough
   history accumulates (>=10 days), the column displays "insufficient
   history".

WHAT THIS PATCHER DOES NOT DO
-----------------------------
- Does NOT use the Stage-3 lookback to modify the Stage 4 rating.
  The brief explicitly excludes the Probable-to-Plausible demotion.
  The lookback is INFORMATIONAL ONLY.
- Does NOT touch build_dashboard.py.
- Does NOT touch any other Stage block.

USAGE
-----
1. Dry-run:
       python3 scripts/patch_md_v2_stage4_rewrite_s47_2026_05_18.py --test
2. Apply (clean WT, per-patcher commit cycle):
       python scripts/patch_md_v2_stage4_rewrite_s47_2026_05_18.py
       git add scripts/generate_master_data.py
       git commit -m "feat(MD V2 S47): Stage 4 — specific-combinations ladder + S3 lookback INFO col (D-MD-V2-115)"
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
MARKER         = "MD-V2-S47-S4-REWRITE-MARKER"
BAK_TAG        = "s47-s4-rewrite"
ENABLE_PY_COMPILE = True
# ======================================================================

# ── ANCHOR/REPLACEMENT PAIR 1: Stage 4 rating ladder rewrite ──

ANCHOR_1 = """\
        s4_count = sum(1 for t in [s4_t1, s4_t2, s4_t3, s4_t4, s4_t5, s4_t6, s4_t7] if t)
        s4["count"] = s4_count
        if s4_count >= 3:
            s4["rating"] = "Probable"
        elif s4_count == 2:
            s4["rating"] = "Plausible"
        elif s4_count == 1:
            s4["rating"] = "Possible"
        else:
            s4["rating"] = "None"
        md["stage_4"] = s4"""

REPLACEMENT_1 = """\
        s4_count = sum(1 for t in [s4_t1, s4_t2, s4_t3, s4_t4, s4_t5, s4_t6, s4_t7] if t)
        s4["count"] = s4_count

        # MD-V2-S47-S4-REWRITE-MARKER (18-May-26, D-MD-V2-115):
        # Specific-combinations ladder per Richard's 17-May definitions.
        # Replaces old count-based ladder (3/7, 2/7, 1/7).
        if s4_t1 and s4_t3 and s4_t4 and s4_t5:
            s4["rating"] = "Probable"
            if s4_t2:
                s4["rating"] = "Probable (Accelerating)"
        elif s4_t4 and s4_t5:
            s4["rating"] = "Plausible"
        elif s4_t4 or s4_t5:
            s4["rating"] = "Possible"
        else:
            s4["rating"] = "None"

        # Stage-3 lookback INFO column (D-MD-V2-115):
        # Does NOT modify Stage 4 rating — informational only.
        s3_lookback = _stage_3_fired_in_last_60d(ticker, _s47_stage3_snapshots)
        s4["info_stage_3_lookback"] = s3_lookback
        s4["test_values"] = {
            "s3_fired_in_60d": s3_lookback["fired"],
            "s3_days_ago": s3_lookback["days_ago"],
            "s3_history_depth_ok": s3_lookback["history_depth_ok"],
        }

        md["stage_4"] = s4"""

# ── ANCHOR/REPLACEMENT PAIR 2: Insert helper function + snapshot extension ──
# Insert just before _save_daily_snapshot function definition.

ANCHOR_2 = """\
def _save_daily_snapshot(filter_results):
    \"\"\"Append today's stage assignments to data/stage-snapshots.json.

    This builds up real day-by-day history over time. Each entry is keyed
    by date so re-running on the same day overwrites (idempotent).
    \"\"\"
    FILTERS = ["basing_plateau", "probing_bet", "mm99", "vcp", "uptrend_retest"]
    snapshot_path = DATA_DIR / "stage-snapshots.json"

    # Load existing snapshots
    existing = {}
    if snapshot_path.exists():
        try:
            with open(snapshot_path) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            existing = {}

    # Build today's snapshot
    today = date.today().strftime("%Y-%m-%d")
    today_stages = {}
    for r in filter_results:
        today_stages[r["ticker"]] = {f: r[f].get("stage") for f in FILTERS}

    existing[today] = today_stages

    # Write back
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(snapshot_path, "w") as f:
        json.dump(existing, f, separators=(",", ":"))

    print(f"  Daily snapshot saved: {today} ({len(today_stages)} stocks, {len(existing)} total days)")"""

REPLACEMENT_2 = """\
# ── Stage 3 lifecycle lookback infrastructure (D-MD-V2-115) ──

def _load_stage3_snapshots():
    \"\"\"Load Stage 3 lifecycle rating snapshots from data/stage-snapshots.json.

    Returns a dict keyed by date-string, where each value is a dict mapping
    ticker to its Stage 3 lifecycle rating (e.g. "Probable Invalidation",
    "Plausible Invalidation", "Possible Topping", "None", or null if not
    yet recorded). Returns empty dict on any load failure.
    \"\"\"
    snapshot_path = DATA_DIR / "stage-snapshots.json"
    if not snapshot_path.exists():
        return {}
    try:
        with open(snapshot_path) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}
    # Extract only the "stage_3_rating" field from each day's per-ticker dict.
    result = {}
    for day_str, tickers in data.items():
        day_ratings = {}
        for tk, fields in tickers.items():
            if isinstance(fields, dict):
                day_ratings[tk] = fields.get("stage_3_rating")
        result[day_str] = day_ratings
    return result


# Module-level cache — loaded once per run, used by all _stage_3_fired_in_last_60d calls.
_s47_stage3_snapshots = None


def _ensure_stage3_snapshots():
    \"\"\"Lazy-load the Stage 3 snapshot cache exactly once per pipeline run.\"\"\"
    global _s47_stage3_snapshots
    if _s47_stage3_snapshots is None:
        _s47_stage3_snapshots = _load_stage3_snapshots()
    return _s47_stage3_snapshots


def _stage_3_fired_in_last_60d(ticker, snapshots):
    \"\"\"Check if ticker had a Stage 3 Probable or Plausible rating in last 60 days.

    Args:
        ticker: stock ticker string
        snapshots: dict from _load_stage3_snapshots()

    Returns:
        dict with three fields:
        - fired (bool): True if any snapshot in the last 60 trading days shows
          this ticker at Stage 3 "Probable Invalidation" or "Plausible Invalidation".
        - days_ago (int or None): number of calendar days since the most recent
          Stage 3 firing, or None if no firing found in the window.
        - history_depth_ok (bool): True if >=10 days of snapshot history exist
          overall. If False, result should display "insufficient history".
    \"\"\"
    if not snapshots:
        return {"fired": False, "days_ago": None, "history_depth_ok": False}

    sorted_dates = sorted(snapshots.keys(), reverse=True)
    history_depth_ok = len(sorted_dates) >= 10

    today = date.today()
    cutoff = today - timedelta(days=60)
    qualifying_ratings = {"Probable Invalidation", "Plausible Invalidation"}

    fired = False
    days_ago = None

    for day_str in sorted_dates:
        try:
            day_date = datetime.strptime(day_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if day_date < cutoff:
            break  # Past the 60-day window

        rating = snapshots.get(day_str, {}).get(ticker)
        if rating in qualifying_ratings:
            fired = True
            delta = (today - day_date).days
            if days_ago is None or delta < days_ago:
                days_ago = delta

    return {"fired": fired, "days_ago": days_ago, "history_depth_ok": history_depth_ok}


def _save_daily_snapshot(filter_results):
    \"\"\"Append today's stage assignments to data/stage-snapshots.json.

    This builds up real day-by-day history over time. Each entry is keyed
    by date so re-running on the same day overwrites (idempotent).

    D-MD-V2-115 extension: also persists Stage 3 lifecycle rating
    alongside the existing setup-stage data, enabling the Stage 4
    lookback column.
    \"\"\"
    FILTERS = ["basing_plateau", "probing_bet", "mm99", "vcp", "uptrend_retest"]
    snapshot_path = DATA_DIR / "stage-snapshots.json"

    # Load existing snapshots
    existing = {}
    if snapshot_path.exists():
        try:
            with open(snapshot_path) as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            existing = {}

    # Build today's snapshot
    today = date.today().strftime("%Y-%m-%d")
    today_stages = {}
    for r in filter_results:
        entry = {f: r[f].get("stage") for f in FILTERS}
        # D-MD-V2-115: persist Stage 3 lifecycle rating for lookback
        md_v2 = r.get("md_v2", {})
        s3 = md_v2.get("stage_3", {})
        entry["stage_3_rating"] = s3.get("rating", "None")
        today_stages[r["ticker"]] = entry

    existing[today] = today_stages

    # Write back
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(snapshot_path, "w") as f:
        json.dump(existing, f, separators=(",", ":"))

    print(f"  Daily snapshot saved: {today} ({len(today_stages)} stocks, {len(existing)} total days)")"""

# ── ANCHOR/REPLACEMENT PAIR 3: Lazy-init the cache before the per-stock loop ──
# We need to call _ensure_stage3_snapshots() before the loop that computes
# Stage 4. The cleanest place is right where Stage 4 computation begins.

ANCHOR_3 = """\
        # ──────────────────────────────────────────────────────────────
        # STAGE 4 — Decline
        # ──────────────────────────────────────────────────────────────
        s4 = {"tests": {}, "groups": {}, "count": 0, "rating": "None"}"""

REPLACEMENT_3 = """\
        # ──────────────────────────────────────────────────────────────
        # STAGE 4 — Decline
        # ──────────────────────────────────────────────────────────────
        # D-MD-V2-115: ensure Stage 3 snapshot cache is loaded for lookback.
        _ensure_stage3_snapshots()
        s4 = {"tests": {}, "groups": {}, "count": 0, "rating": "None"}"""


# ---------- BOILERPLATE — MULTI-ANCHOR VARIANT ------------------------

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

    # Multi-anchor: apply all three replacements in sequence
    anchors = [
        ("ANCHOR_1 (S4 ladder rewrite)", ANCHOR_1, REPLACEMENT_1),
        ("ANCHOR_2 (helper + snapshot extension)", ANCHOR_2, REPLACEMENT_2),
        ("ANCHOR_3 (cache init at S4 block)", ANCHOR_3, REPLACEMENT_3),
    ]

    new_src = head_src
    for label, anchor, replacement in anchors:
        n = new_src.count(anchor)
        print(f"[*] {label}: matches={n} (expected 1)")
        if n != 1:
            print(f"[ABORT] {label} count != 1 -- source may have drifted.")
            return 3
        new_src = new_src.replace(anchor, replacement, 1)

    assert MARKER in new_src, "[INTERNAL] MARKER missing after all replacements"

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
    print(f"[OK] Next: git add scripts/generate_master_data.py && git commit -m 'feat(MD V2 S47): Stage 4 — specific-combinations ladder + S3 lookback INFO col (D-MD-V2-115)'")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
