"""
=============================================================================
PATCHER — P1 (S40, 16-May-26) — *FmtNum integer-display fix (A6 / T-E sub-item)
=============================================================================
Fixes Wave 4 integer-15.00 cosmetic: integer test values render with
spurious .00 decimals because *FmtNum hard-codes dp=2 when abs < 20.
Forces dp=0 when the input is integer-valued.

Touches all 8 in-page *FmtNum helpers (s1/s2/s3/s4 + pi/po/st/ct).
Each helper has small lexical variations (s1 uses `var formatted`, others
use `var f`; Stage tabs return em-dash, V2 tabs return hyphen) so the
edits are 8 explicit (anchor, replacement) pairs rather than a generator.

Pattern: one marker, 8 (anchor, replacement) pairs. Anchor count
asserted == 1 per edit. Per D-MD-INFRA-5: text-mode I/O.
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
TARGET_REL     = os.path.join("scripts", "build_dashboard.py")
MARKER         = "MD-V2-S40-FMTNUM-INT-FIX"
BAK_TAG        = "fmtnum-int-fix"
ENABLE_PY_COMPILE = True

# Stage 1 (uses `var formatted`, em-dash):
A_S1 = (
    "  function s1FmtNum(n) {\n"
    "    if (n == null || isNaN(n)) return '—';\n"
    "    var abs = Math.abs(n);\n"
    "    var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);\n"
    "    var formatted = abs.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });\n"
    "    return n < 0 ? '(' + formatted + ')' : formatted;\n"
    "  }"
)
R_S1 = (
    "  function s1FmtNum(n) {\n"
    "    if (n == null || isNaN(n)) return '—';\n"
    "    var abs = Math.abs(n);\n"
    "    var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);\n"
    "    if (n === Math.round(n)) dp = 0; /* " + MARKER + "-s1 */\n"
    "    var formatted = abs.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });\n"
    "    return n < 0 ? '(' + formatted + ')' : formatted;\n"
    "  }"
)

def _stage_pair(prefix: str) -> tuple[str, str]:
    """Stage 2/3/4 — em-dash + `var f`."""
    anchor = (
        f"  function {prefix}FmtNum(n) {{\n"
        f"    if (n == null || isNaN(n)) return '—';\n"
        f"    var abs = Math.abs(n);\n"
        f"    var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);\n"
        f"    var f = abs.toLocaleString('en-GB', {{ minimumFractionDigits: dp, maximumFractionDigits: dp }});\n"
        f"    return n < 0 ? '(' + f + ')' : f;\n"
        f"  }}"
    )
    replacement = (
        f"  function {prefix}FmtNum(n) {{\n"
        f"    if (n == null || isNaN(n)) return '—';\n"
        f"    var abs = Math.abs(n);\n"
        f"    var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);\n"
        f"    if (n === Math.round(n)) dp = 0; /* {MARKER}-{prefix} */\n"
        f"    var f = abs.toLocaleString('en-GB', {{ minimumFractionDigits: dp, maximumFractionDigits: dp }});\n"
        f"    return n < 0 ? '(' + f + ')' : f;\n"
        f"  }}"
    )
    return anchor, replacement

def _v2_pair(prefix: str) -> tuple[str, str]:
    """V2 tabs — hyphen + `var f`."""
    anchor = (
        f"  function {prefix}FmtNum(n) {{\n"
        f"    if (n == null || isNaN(n)) return '-';\n"
        f"    var abs = Math.abs(n);\n"
        f"    var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);\n"
        f"    var f = abs.toLocaleString('en-GB', {{ minimumFractionDigits: dp, maximumFractionDigits: dp }});\n"
        f"    return n < 0 ? '(' + f + ')' : f;\n"
        f"  }}"
    )
    replacement = (
        f"  function {prefix}FmtNum(n) {{\n"
        f"    if (n == null || isNaN(n)) return '-';\n"
        f"    var abs = Math.abs(n);\n"
        f"    var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);\n"
        f"    if (n === Math.round(n)) dp = 0; /* {MARKER}-{prefix} */\n"
        f"    var f = abs.toLocaleString('en-GB', {{ minimumFractionDigits: dp, maximumFractionDigits: dp }});\n"
        f"    return n < 0 ? '(' + f + ')' : f;\n"
        f"  }}"
    )
    return anchor, replacement

EDITS: list[tuple[str, str, str]] = [("s1", A_S1, R_S1)]
for p in ("s2", "s3", "s4"):
    a, r = _stage_pair(p)
    EDITS.append((p, a, r))
for p in ("pi", "po", "st", "ct"):
    a, r = _v2_pair(p)
    EDITS.append((p, a, r))

EXPECTED_EDITS = len(EDITS)  # 8


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
    print(f"[*] Edits:          {EXPECTED_EDITS} (one per *FmtNum across 8 modules)")
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

    new_src = head_src
    for prefix, anchor, replacement in EDITS:
        n = new_src.count(anchor)
        print(f"[*] {prefix}FmtNum anchor matches: {n} (expected 1)")
        if n != 1:
            print(f"[ABORT] {prefix}FmtNum anchor count != 1 -- source has drifted.")
            return 3
        new_src = new_src.replace(anchor, replacement, 1)

    n_marker = new_src.count(MARKER)
    if n_marker != EXPECTED_EDITS:
        print(f"[ABORT] expected {EXPECTED_EDITS} MARKER occurrences, got {n_marker}")
        return 4

    print(f"[*] Char delta:     {len(new_src) - len(head_src):+d}")
    print(f"[*] New md5(text):  {_md5_text(new_src)}")

    if ENABLE_PY_COMPILE:
        try:
            ast.parse(new_src)
        except SyntaxError as e:
            print(f"[ABORT] ast.parse failed on new source: {e}")
            return 5
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tf:
            tf.write(new_src)
            tmp_py = tf.name
        try:
            py_compile.compile(tmp_py, doraise=True)
            print(f"[*] py_compile:     OK")
        except py_compile.PyCompileError as e:
            print(f"[ABORT] py_compile failed: {e}")
            return 6
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
        return 7
    if MARKER not in after:
        print("[ABORT] Post-write MARKER missing.")
        return 8

    disk_bytes = os.path.getsize(abs_target)
    print(f"[OK] WRITE complete. {len(after)} chars, {disk_bytes} bytes on disk.")
    print(f"[OK] {after.count(MARKER)} MARKER occurrences (expected {EXPECTED_EDITS}).")
    print(f"[OK] Next: python scripts/build_dashboard.py && git add scripts/build_dashboard.py index.html && git commit && git push")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
