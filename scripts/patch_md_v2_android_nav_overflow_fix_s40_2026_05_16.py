"""
=============================================================================
PATCHER — P2 (S40, 16-May-26) — Android tablet header overflow fix (A4)
=============================================================================
Fixes: "Capital deployment" v2-nav group label (and others) overflow the
fixed 70px-tall V2 header at narrow tablet viewport widths.

Approach: SCOPED @media query that shrinks v2-nav components proportionally
when viewport < 1024px wide — does NOT wrap, because the header has a fixed
height (--header-height:70px on V2 tabs, line 1191) and wrap would push
content out of the clip rectangle.

Components shrunk: .v2-nav gap+padding, .v2-nav-grp-label font-size +
letter-spacing + margin, .v2-nav-btn padding + font-size, .v2-nav-sep
margin + font-size. Each reduction is conservative (~20-25%) so the nav
remains readable while fitting comfortably on iPad-portrait (768px) and
Android-tablet portrait/landscape (810-1024px) widths.

Anchored after the last v2-nav CSS rule (.v2-nav-btn.v2-grp-tests:hover).
Idempotent on MARKER. Per D-MD-INFRA-5: text-mode I/O.
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
MARKER         = "MD-V2-S40-ANDROID-NAV-OVERFLOW-FIX"
BAK_TAG        = "android-nav-overflow"
ENABLE_PY_COMPILE = True

ANCHOR = (
    ".v2-nav-btn.v2-grp-indicators:hover { background: #e8f2ee; }\n"
    ".v2-nav-btn.v2-grp-setups:hover { background: #efecf6; }\n"
    ".v2-nav-btn.v2-grp-tests:hover { background: #f6efe6; }\n"
)

REPLACEMENT = (
    ".v2-nav-btn.v2-grp-indicators:hover { background: #e8f2ee; }\n"
    ".v2-nav-btn.v2-grp-setups:hover { background: #efecf6; }\n"
    ".v2-nav-btn.v2-grp-tests:hover { background: #f6efe6; }\n"
    "/* " + MARKER + ": shrink v2-nav components on tablet widths so all\n"
    "   group labels (incl. 'Capital deployment') and buttons fit on one row\n"
    "   within the 70px fixed header without overflowing horizontally. */\n"
    "@media (max-width: 1024px) {\n"
    "  .v2-nav { gap: 4px; padding: 6px 8px; }\n"
    "  .v2-nav-grp-label { font-size: 8px; letter-spacing: 0.2px; margin: 0 2px 0 0; }\n"
    "  .v2-nav-btn { padding: 4px 8px; font-size: 10px; }\n"
    "  .v2-nav-sep { margin: 0 3px; font-size: 11px; }\n"
    "  .v2-nav-label { font-size: 9px; margin-right: 4px; }\n"
    "}\n"
)


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
    print(f"[OK] WRITE complete. {len(after)} chars, {disk_bytes} bytes on disk.")
    print(f"[OK] Next: python scripts/build_dashboard.py && git add scripts/build_dashboard.py index.html && git commit && git push")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
