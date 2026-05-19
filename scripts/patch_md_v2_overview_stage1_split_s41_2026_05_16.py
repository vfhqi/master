"""
S41 PATCHER -- Overview Stage 1 Basing: split Probable Early / Probable Late
into two adjacent columns in BOTH the summary table and the matrix table.

Brief item #4 (16-May-26): "the Stage 1 Uptrend [Basing] column should
differentiate Probable Early and Probable Late in the main table and the
summary table. Logic: They are quite different."

DESIGN
------
The pipeline (_md_v2_screens.py L135-144) already emits "Probable Early"
(count==4) and "Probable Late" (count>=5) as distinct Stage 1 ratings.
The Overview today collapses both into one "Probable" column via the
moNormaliseTier folding (L12349-12355: any "Probable*" -> "Probable").

This patcher:
 (1) Splits the MO_ROWS Stage 1 entry into two adjacent rows each carrying
     a `subTier` field ('Probable Early' / 'Probable Late').
 (2) Teaches moNormaliseTier(raw, subTier) to honour subTier: when set,
     the cell shows "Probable" ONLY when raw === subTier; the OTHER
     Probable variant downgrades to "Plausible" (so it stays visible in
     the cell but at a different visual tier); Plausible/Possible/None
     are unchanged from today.
 (3) Updates the 3 call sites that consume moNormaliseTier to pass the
     row's subTier as the second argument.

NET BEHAVIOUR
-------------
- A stock at rating "Probable Late":
    Early column shows -> "Plausible"
    Late  column shows -> "Probable"
- A stock at rating "Probable Early":
    Early column shows -> "Probable"
    Late  column shows -> "Plausible"
- A stock at rating "Plausible" / "Possible" / "None":
    Both columns show the same lower tier as today.

Summary-table counts split cleanly across the two new columns.
"""
from __future__ import annotations
import ast, datetime as _dt, difflib, hashlib, os, py_compile, subprocess, sys, tempfile

REPO_ROOT_HINT = "master-dashboard"
TARGET_REL     = os.path.join("scripts", "build_dashboard.py")
MARKER         = "MD-V2-S41-OVERVIEW-STAGE1-SPLIT-MARKER"
BAK_TAG        = "s41-overview-stage1-split"
ENABLE_PY_COMPILE = True

# ===== EDIT 1: MO_ROWS Stage 1 entry -> two entries =====
ANCHOR_1 = """    { section:'Stages', key:'stage_1', label:'Stage 1 - Basing', short:'S1 Basing', ratingPath:'stage:stage_1', tabId:'stage_1', patternKey:null },
    { section:'Stages', key:'stage_2', label:'Stage 2 - Uptrend', short:'S2 Uptrend', ratingPath:'stage:stage_2', tabId:'stage_2', patternKey:null },"""

REPLACEMENT_1 = """    /* MD-V2-S41-OVERVIEW-STAGE1-SPLIT-MARKER -- Stage 1 split into Early + Late columns; each row carries subTier consumed by moNormaliseTier. */
    { section:'Stages', key:'stage_1_early', label:'Stage 1 - Basing (Probable Early)', short:'S1 Early', ratingPath:'stage:stage_1', tabId:'stage_1', patternKey:null, subTier:'Probable Early' },
    { section:'Stages', key:'stage_1_late',  label:'Stage 1 - Basing (Probable Late)',  short:'S1 Late',  ratingPath:'stage:stage_1', tabId:'stage_1', patternKey:null, subTier:'Probable Late' },
    { section:'Stages', key:'stage_2', label:'Stage 2 - Uptrend', short:'S2 Uptrend', ratingPath:'stage:stage_2', tabId:'stage_2', patternKey:null },"""

# ===== EDIT 2: moNormaliseTier -- accept subTier =====
ANCHOR_2 = """  function moNormaliseTier(raw) {
    if (!raw) return 'None';
    if (raw.indexOf('Probable') === 0) return 'Probable';
    if (raw.indexOf('Plausible') === 0) return 'Plausible';
    if (raw.indexOf('Possible') === 0) return 'Possible';
    return 'None';
  }"""

REPLACEMENT_2 = """  function moNormaliseTier(raw, subTier) {
    if (!raw) return 'None';
    // MD-V2-S41-OVERVIEW-STAGE1-SPLIT: subTier-aware normalisation. When the
    // row carries a subTier (Stage 1 Early/Late split), the cell shows
    // "Probable" only when raw matches that specific tier; the OTHER Probable
    // variant downgrades to Plausible (visible-but-not-top-tier).
    if (subTier) {
      if (raw === subTier) return 'Probable';
      if (raw.indexOf('Probable') === 0) return 'Plausible';
    }
    if (raw.indexOf('Probable') === 0) return 'Probable';
    if (raw.indexOf('Plausible') === 0) return 'Plausible';
    if (raw.indexOf('Possible') === 0) return 'Possible';
    return 'None';
  }"""

# ===== EDIT 3: moSelRowPasses -- pass row.subTier =====
ANCHOR_3 = "      var tier = moNormaliseTier(moReadRating(md, row.ratingPath));"
REPLACEMENT_3 = "      var tier = moNormaliseTier(moReadRating(md, row.ratingPath), row.subTier);  /* MD-V2-S41-OVERVIEW-STAGE1-SPLIT */"

# ===== EDIT 4: summary table builder -- pass rw.subTier =====
ANCHOR_4 = "        var tr = moNormaliseTier(moReadRating(md, rw.ratingPath));"
REPLACEMENT_4 = "        var tr = moNormaliseTier(moReadRating(md, rw.ratingPath), rw.subTier);  /* MD-V2-S41-OVERVIEW-STAGE1-SPLIT */"

# ===== EDIT 5: matrix builder -- pass MO_ROWS[r].subTier =====
ANCHOR_5 = "        var tier = moNormaliseTier(moReadRating(md, MO_ROWS[r].ratingPath));"
REPLACEMENT_5 = "        var tier = moNormaliseTier(moReadRating(md, MO_ROWS[r].ratingPath), MO_ROWS[r].subTier);  /* MD-V2-S41-OVERVIEW-STAGE1-SPLIT */"

EDITS = [
    (ANCHOR_1, REPLACEMENT_1, "MO_ROWS Stage 1 split"),
    (ANCHOR_2, REPLACEMENT_2, "moNormaliseTier subTier-aware"),
    (ANCHOR_3, REPLACEMENT_3, "moSelRowPasses subTier"),
    (ANCHOR_4, REPLACEMENT_4, "summary table subTier"),
    (ANCHOR_5, REPLACEMENT_5, "matrix builder subTier"),
]


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
    raise SystemExit("[ABORT] cannot locate repo root from " + cur)


def _git_show_head_text(repo, rel):
    rel_posix = rel.replace(os.sep, "/")
    out = subprocess.run(["git", "show", "HEAD:" + rel_posix], cwd=repo, check=True, capture_output=True)
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
    print("[*] Repo root: " + repo)
    print("[*] Target: " + rel)
    print("[*] Marker: " + MARKER)
    print("[*] Mode: " + ("DRY-RUN" if test_mode else "WRITE"))

    head_src = _git_show_head_text(repo, rel)
    wt_src = _wt_text(repo, rel)
    print("[*] HEAD chars: %d | WT chars: %d" % (len(head_src), len(wt_src)))
    if _md5_text(wt_src) != _md5_text(head_src):
        if test_mode:
            print("[WARN] WT diverges from HEAD; dry-run proceeds (gates on HEAD).")
        else:
            print("[ABORT] WT diverges from HEAD.")
            return 2
    if MARKER in head_src:
        print("[OK] MARKER already in HEAD.")
        return 0
    if MARKER in wt_src:
        print("[OK] MARKER in WT, not HEAD.")
        return 0

    new_src = head_src
    for i, (a, r, label) in enumerate(EDITS):
        n = new_src.count(a)
        print("[*] Edit[%d] %-30s matches: %d (expected 1)" % (i+1, label, n))
        if n != 1:
            print("[ABORT] Edit[%d] anchor count != 1" % (i+1))
            return 3
        new_src = new_src.replace(a, r, 1)

    assert MARKER in new_src, "[INTERNAL] MARKER missing after replacements"
    print("[*] Char delta: %+d" % (len(new_src) - len(head_src)))

    if ENABLE_PY_COMPILE:
        try:
            ast.parse(new_src)
        except SyntaxError as e:
            print("[ABORT] ast.parse: " + str(e)); return 4
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tf:
            tf.write(new_src); tmp_py = tf.name
        try:
            py_compile.compile(tmp_py, doraise=True); print("[*] py_compile: OK")
        except py_compile.PyCompileError as e:
            print("[ABORT] py_compile: " + str(e)); return 5
        finally:
            try: os.unlink(tmp_py)
            except OSError: pass

    print("\n--- DIFF (n=1) ---")
    sys.stdout.writelines(difflib.unified_diff(head_src.splitlines(keepends=True), new_src.splitlines(keepends=True), fromfile="HEAD:" + rel, tofile="PATCHED:" + rel, n=1))
    print("--- END DIFF ---\n")

    if test_mode:
        print("[OK] DRY-RUN gates passed."); return 0
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = abs_target + ".bak-pre-" + BAK_TAG + "-" + ts
    with open(bak, "w", encoding="utf-8") as fh: fh.write(wt_src)
    print("[*] Backup: " + os.path.relpath(bak, repo))
    fd, tmp_out = tempfile.mkstemp(prefix=".patch-", suffix=".tmp", dir=os.path.dirname(abs_target))
    os.close(fd)
    with open(tmp_out, "w", encoding="utf-8") as fh: fh.write(new_src)
    os.replace(tmp_out, abs_target)
    after = _wt_text(repo, rel)
    if _md5_text(after) != _md5_text(new_src): print("[ABORT] post-write md5 mismatch."); return 6
    if MARKER not in after: print("[ABORT] MARKER missing post-write."); return 7
    print("[OK] WRITE complete. %d chars on disk." % len(after))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
