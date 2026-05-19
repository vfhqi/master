"""
SA - Master Dashboard | Patcher: broaden gitignore (S39b, 16-May-26)

Extends the S39 `.gitignore` hygiene block to cover the remaining 9 tracked
sidecar files outside scripts/:
  * data/*.bak  (8 files: universe/ssem/stage-snapshots/ticker_mapping backups)
  * data/*.bak-*
  * ic-ratings-dashboard.bak-*.html  (1 file, repo root)

Same scope as S39a (gitignore scripts/*.bak*) but broader. Built on the proven
S35-S38 text-mode I/O house style (D-MD-INFRA-5).

Run order on Windows-side:
    python scripts\\patch_md_gitignore_broaden_s39b_2026_05_16.py --test
    python scripts\\patch_md_gitignore_broaden_s39b_2026_05_16.py
    git ls-files 'data/*.bak*' 'ic-ratings-dashboard.bak-*' | %{ git rm --cached -- $_ }
    git status   # expect: modified .gitignore + 9 deletions
    git add .gitignore
    git commit -m "chore: broaden gitignore + untrack data/*.bak* + root *.bak-* (S39b)"
    git push
"""
from __future__ import annotations
import datetime as _dt
import hashlib
import os
import subprocess
import sys
import tempfile

REPO_ROOT_HINT = "master-dashboard"
TARGET_REL = ".gitignore"
MARKER = "# MD-V2-S39B-GITIGNORE-BROADER"

APPEND_BLOCK = """
# MD-V2-S39B-GITIGNORE-BROADER (16-May-26)
# Broader scope than S39a -- catches data/ pipeline sidecar backups and the
# root-level ic-ratings-dashboard html backup. Pure local-recovery artefacts;
# 9 already-tracked files removed via git rm --cached in the same commit.
data/*.bak
data/*.bak-*
ic-ratings-dashboard.bak-*.html
"""

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
    out = subprocess.run(
        ["git", "show", f"HEAD:{rel.replace(os.sep, '/')}"],
        cwd=repo, check=True, capture_output=True,
    )
    return out.stdout.decode("utf-8")

def _wt_text(repo: str, rel: str) -> str:
    with open(os.path.join(repo, rel), "r", encoding="utf-8") as fh:
        return fh.read()

def _md5_text(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()

def _git_tracked_extra_bak(repo: str) -> list[str] | None:
    """Return tracked files matching data/*.bak* OR ic-ratings-dashboard.bak-*.
    Returns None if `git ls-files` fails for environmental reasons (e.g. sandbox
    git can't read a Windows-side index extension). The list is purely informational;
    the patcher proceeds regardless.
    """
    try:
        out = subprocess.run(["git", "ls-files"], cwd=repo, capture_output=True)
        if out.returncode != 0:
            return None
        matched = []
        for line in out.stdout.decode("utf-8", errors="replace").splitlines():
            if line.startswith("data/"):
                base = os.path.basename(line)
                if base.endswith(".bak") or ".bak-" in base:
                    matched.append(line)
            elif line.startswith("ic-ratings-dashboard.bak-"):
                matched.append(line)
        return sorted(matched)
    except Exception:
        return None

def main(argv: list[str]) -> int:
    test_mode = "--test" in argv
    repo = _find_repo_root()
    rel = TARGET_REL
    abs_target = os.path.join(repo, rel)

    print(f"[*] Repo root:      {repo}")
    print(f"[*] Target:         {rel}")
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
        else:
            print(f"[ABORT] {msg}")
            return 2

    if MARKER in head_src:
        print(f"[OK] MARKER already in HEAD -- already shipped.")
        return 0
    if MARKER in wt_src:
        print(f"[OK] MARKER already in WT -- applied but not committed yet.")
        return 0

    tracked = _git_tracked_extra_bak(repo)
    if tracked is None:
        print(f"\n[*] Tracked-files list: unavailable in this environment (sandbox git can't read")
        print(f"    Windows-side index). Will work Windows-side. Run this AFTER patch applies:")
        print(f"      git ls-files 'data/*.bak*' 'ic-ratings-dashboard.bak-*'")
        tracked = []
        total_bytes = 0
    else:
        total_bytes = sum(os.path.getsize(os.path.join(repo, p)) for p in tracked if os.path.exists(os.path.join(repo, p)))
        print(f"\n[*] Tracked files that would be covered: {len(tracked)} ({total_bytes:,} bytes)")
        for p in tracked:
            print(f"      {p}")

    new_src = head_src.rstrip("\n") + "\n" + APPEND_BLOCK
    print(f"\n[*] Char delta:     +{len(new_src) - len(head_src)}")
    print(f"[*] New md5(text):  {_md5_text(new_src)}")

    print("\n--- DIFF ---")
    import difflib
    sys.stdout.writelines(difflib.unified_diff(
        head_src.splitlines(keepends=True),
        new_src.splitlines(keepends=True),
        fromfile=f"HEAD:{rel}", tofile=f"PATCHED:{rel}", n=2,
    ))
    print("--- END DIFF ---\n")

    if test_mode:
        print("[OK] DRY-RUN: gates passed. Re-run without --test to write.")
        if tracked:
            print(f"\n    After write, run this to untrack the {len(tracked)} files:")
            print(f"      # PowerShell:")
            print(f"      git ls-files 'data/*.bak*' 'ic-ratings-dashboard.bak-*' | %{{ git rm --cached -- $_ }}")
        return 0

    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = abs_target + f".bak-pre-gitignore-broader-{ts}"
    with open(bak, "w", encoding="utf-8") as fh:
        fh.write(wt_src)
    print(f"[*] Backup:         {os.path.relpath(bak, repo)}")

    target_dir = os.path.dirname(abs_target) or repo
    fd, tmp_out = tempfile.mkstemp(prefix=".gi-patch-", suffix=".tmp", dir=target_dir)
    os.close(fd)
    with open(tmp_out, "w", encoding="utf-8") as fh:
        fh.write(new_src)
    os.replace(tmp_out, abs_target)

    after = _wt_text(repo, rel)
    if _md5_text(after) != _md5_text(new_src):
        print("[ABORT] Post-write text-md5 mismatch!")
        return 6
    if MARKER not in after:
        print("[ABORT] Post-write MARKER missing.")
        return 7
    print(f"[OK] WRITE complete. {len(after)} chars. MARKER present.")

    if tracked:
        print(f"\n[*] Next: untrack the {len(tracked)} files:")
        print(f"      git ls-files 'data/*.bak*' 'ic-ratings-dashboard.bak-*' | %{{ git rm --cached -- $_ }}")
        print(f"\n[*] Then:")
        print(f"      git add .gitignore && git status && git commit -m \"chore: broaden gitignore (S39b)\" && git push")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
