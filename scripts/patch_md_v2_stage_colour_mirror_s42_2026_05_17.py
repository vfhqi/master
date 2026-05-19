"""
S42 PATCHER -- Stage 3 + Stage 4 caption colour mirror

Brief item #20 (16-May-26): "Mirror Stage 2 supergroup colour pattern onto
Stage 1/3/4." Diagnosis (17-May-26 SA session):
 - Stage 1 captions show correct per-group colors (own #tab-stage_1 CSS block at L687-690).
 - Stage 2 captions show correct per-group colors (rules at L1186-1191 in shared block).
 - Stage 3 + Stage 4 captions all show gold (default #b08a4e), bug.
The Stage 3 + Stage 4 per-group .gcap-g{N} accent rules at L875-884 and L990-994
have IDENTICAL specificity to the shared default rule at L1163 but come EARLIER
in source, so the shared default's `border-left: 3px solid #b08a4e` wins.

FIX
---
Insert per-stage accent overrides for stage_3 (g1-g5) and stage_4 (g1-g3) into
the shared block right after the existing stage_2 rules, immediately before the
`/* MD-V2-CHROME-PARITY-MARKER-CSS-END */` marker. Source order is now AFTER
the default rule, so the accents win.

Colors match each stage's existing .gh-g{N} header text-colors:
 - stage_3: orange-to-red palette (d97706 / c2410c / b91c1c / 7c2d12 / 6a5a8a)
 - stage_4: red palette (991b1b / 7f1d1d / 6a5a8a)
"""
from __future__ import annotations
import ast, datetime as _dt, hashlib, os, py_compile, subprocess, sys, tempfile

REPO_ROOT_HINT = "master-dashboard"
TARGET_REL     = os.path.join("scripts", "build_dashboard.py")
MARKER         = "MD-V2-S42-STAGE-COLOUR-MIRROR-MARKER"
BAK_TAG        = "s42-stage-colour-mirror"

ANCHOR = "/* MD-V2-CHROME-PARITY-MARKER-CSS-END */"
REPLACEMENT = """/* MD-V2-S42-STAGE-COLOUR-MIRROR-MARKER -- stage_3 and stage_4 per-group caption accents placed AFTER the shared default rule (#tab-stage_3 .group-captions .gcap { border-left: 3px solid #b08a4e; }) so cascade source order makes them win. The original per-stage accent rules at L875-884 (stage_3) and L990-994 (stage_4) had identical specificity to the shared default but came EARLIER in source, so the gold default was overriding the orange/red palettes. Colours match each stage's existing .gh-g{N} thead text-colors. */
#tab-stage_3 .group-captions .gcap-g1 { border-left-color: #d97706; }
#tab-stage_3 .group-captions .gcap-g1 b { color: #b45309; }
#tab-stage_3 .group-captions .gcap-g2 { border-left-color: #c2410c; }
#tab-stage_3 .group-captions .gcap-g2 b { color: #9a3412; }
#tab-stage_3 .group-captions .gcap-g3 { border-left-color: #b91c1c; }
#tab-stage_3 .group-captions .gcap-g3 b { color: #991b1b; }
#tab-stage_3 .group-captions .gcap-g4 { border-left-color: #7c2d12; }
#tab-stage_3 .group-captions .gcap-g4 b { color: #7c2d12; }
#tab-stage_3 .group-captions .gcap-g5 { border-left-color: #6a5a8a; }
#tab-stage_3 .group-captions .gcap-g5 b { color: #6a5a8a; }
#tab-stage_4 .group-captions .gcap-g1 { border-left-color: #991b1b; }
#tab-stage_4 .group-captions .gcap-g1 b { color: #991b1b; }
#tab-stage_4 .group-captions .gcap-g2 { border-left-color: #7f1d1d; }
#tab-stage_4 .group-captions .gcap-g2 b { color: #7f1d1d; }
#tab-stage_4 .group-captions .gcap-g3 { border-left-color: #6a5a8a; }
#tab-stage_4 .group-captions .gcap-g3 b { color: #6a5a8a; }
/* MD-V2-CHROME-PARITY-MARKER-CSS-END */"""

def _find_repo_root():
    cur = os.path.abspath(os.path.dirname(__file__))
    cand = os.path.abspath(os.path.join(cur, os.pardir))
    if os.path.basename(cand) == REPO_ROOT_HINT and os.path.exists(os.path.join(cand, ".git")):
        return cand
    raise SystemExit("[ABORT] cannot locate repo root from " + cur)

def _git_show(repo, rel):
    return subprocess.run(["git","show","HEAD:"+rel.replace(os.sep,"/")], cwd=repo, check=True, capture_output=True).stdout.decode("utf-8")

def _wt(repo, rel):
    with open(os.path.join(repo, rel), "r", encoding="utf-8") as f: return f.read()

def _md5(s): return hashlib.md5(s.encode("utf-8")).hexdigest()

def main(argv):
    test_mode = "--test" in argv
    repo = _find_repo_root()
    rel = TARGET_REL
    abs_target = os.path.join(repo, rel)
    head_src = _git_show(repo, rel)
    wt_src = _wt(repo, rel)
    print("[*] HEAD: %d chars | WT: %d chars" % (len(head_src), len(wt_src)))
    if _md5(wt_src) != _md5(head_src):
        if test_mode:
            print("[WARN] WT diverges from HEAD; dry-run on HEAD source.")
        else:
            print("[ABORT] WT diverges from HEAD."); return 2
    if MARKER in head_src:
        print("[OK] MARKER already in HEAD."); return 0
    if MARKER in wt_src:
        print("[OK] MARKER in WT, not yet committed."); return 0
    n = head_src.count(ANCHOR)
    print("[*] Anchor matches: %d (expected 1)" % n)
    if n != 1: print("[ABORT] Anchor count != 1."); return 3
    new_src = head_src.replace(ANCHOR, REPLACEMENT, 1)
    assert MARKER in new_src
    ast.parse(new_src)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tf:
        tf.write(new_src); tmp_py = tf.name
    try: py_compile.compile(tmp_py, doraise=True); print("[*] py_compile: OK")
    finally:
        try: os.unlink(tmp_py)
        except OSError: pass
    if test_mode:
        print("[OK] DRY-RUN gates passed."); return 0
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = abs_target + ".bak-pre-" + BAK_TAG + "-" + ts
    with open(bak, "w", encoding="utf-8") as f: f.write(wt_src)
    fd, tmp_out = tempfile.mkstemp(prefix=".patch-", suffix=".tmp", dir=os.path.dirname(abs_target))
    os.close(fd)
    with open(tmp_out, "w", encoding="utf-8") as f: f.write(new_src)
    os.replace(tmp_out, abs_target)
    after = _wt(repo, rel)
    if _md5(after) != _md5(new_src): print("[ABORT] md5 mismatch."); return 6
    if MARKER not in after: print("[ABORT] MARKER missing."); return 7
    print("[OK] WRITE complete. %d chars on disk." % len(after))
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
