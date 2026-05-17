"""
S41 PATCHER -- Chart panel slides from RIGHT (was LEFT on V2 tabs) +
freeze company/ticker first column on the LEFT across all V2 tabs.

Brief item (16-May-26): "Chart in from right. Freeze company name column on
left. Logic: Means I can see the chart at all times, company names at all
times, and just scroll the cells with data."

DESIGN
------
Today: D-MD-V2-83 had the chart panel slide from the LEFT on V2 tabs (table
shifts right via margin-left). Reason at the time: avoid the chart covering
the rightmost columns of wide V2 tables. Richard's new design solves that
problem differently:
 - chart goes back to default right-slide (mirrors legacy tabs)
 - first column (company/ticker, .name-cell) gets sticky-left on every V2
   tab, so it always stays in view
 - horizontal scroll (body{overflow-x:auto} from D-MD-V2-81) lets columns
   that the chart panel covers be reached by scrolling further

CHANGES
-------
EDIT 1: openChart -- remove the "if V2 chart, add chart-from-left class"
        branch; always remove the class instead.
EDIT 2: openChart -- simplify the .main margin set: always margin-RIGHT,
        never margin-LEFT (matches legacy behaviour).
EDIT 3: setChartWidth -- same simplification: always right-margin.
EDIT 4: insert a new CSS block sticky-left'ing the .name-cell in tbody +
        the first th in col-header-row, for all 8 V2 tabs (Stage 1-4, PI,
        PO, ST = setups, CT = tests).

The existing line 537 `body.chart-from-left ... left:var(--chart-panel-w,0)`
rules become inert (no V2 tab adds the class) and are left in place as
dead CSS for separate hygiene. The Master Overview matrix retains its
existing mo-mx-name-cell sticky-first-column behaviour unchanged.
"""
from __future__ import annotations
import ast, datetime as _dt, difflib, hashlib, os, py_compile, subprocess, sys, tempfile

REPO_ROOT_HINT = "master-dashboard"
TARGET_REL     = os.path.join("scripts", "build_dashboard.py")
MARKER         = "MD-V2-S41-CHART-RIGHT-FREEZE-COL-MARKER"
BAK_TAG        = "s41-chart-right-freeze-col"
ENABLE_PY_COMPILE = True

# ===== EDIT 1: openChart -- always remove chart-from-left =====
ANCHOR_1 = """  if(!_wasChartOpen||(_bodyCl.contains("chart-from-left")!==_isV2chart)){
    p.style.transition="none";
    if(_isV2chart)_bodyCl.add("chart-from-left");else _bodyCl.remove("chart-from-left");
    void p.offsetWidth;
    p.style.transition="";
  }"""

REPLACEMENT_1 = """  // MD-V2-S41-CHART-RIGHT-FREEZE-COL-MARKER -- V2 tabs no longer slide chart from LEFT; always use default right-slide so the new sticky-first-column on V2 tables keeps company/ticker visible while data cells scroll behind the chart panel.
  if(_bodyCl.contains("chart-from-left")){
    p.style.transition="none";
    _bodyCl.remove("chart-from-left");
    void p.offsetWidth;
    p.style.transition="";
  }"""

# ===== EDIT 2: openChart margin push =====
ANCHOR_2 = """  if(_isV2chart){_chartMain.style.marginRight="0";_chartMain.style.marginLeft="50%";}
  else{_chartMain.style.marginLeft="0";_chartMain.style.marginRight="50%";}"""

REPLACEMENT_2 = """  // S41: always push the table to the LEFT with margin-right; chart slides from right on all tabs now.
  _chartMain.style.marginLeft="0";_chartMain.style.marginRight="50%";"""

# ===== EDIT 3: setChartWidth margin =====
ANCHOR_3 = """  if(document.body.classList.contains("chart-from-left")){_cwMain.style.marginLeft=p+"%";_cwMain.style.marginRight="0";}
  else{_cwMain.style.marginRight=p+"%";_cwMain.style.marginLeft="0";}"""

REPLACEMENT_3 = """  // S41: always right-margin push (chart-from-left is dead post-S41).
  _cwMain.style.marginRight=p+"%";_cwMain.style.marginLeft="0";"""

# ===== EDIT 4: insert CSS block for sticky-first-column on V2 tabs =====
# Anchor on the existing rule for the cursor:pointer on V2 name cells; insert AFTER it.
ANCHOR_4 = """#s1-main-table td.name-cell,#s2-main-table td.name-cell,#s3-main-table td.name-cell,#s4-main-table td.name-cell,#pi-main-table td.name-cell,#po-main-table td.name-cell,.st-main-table td.name-cell,#ct-main-table td.name-cell,#mo-matrix-table td.mo-mx-name-cell{cursor:pointer}"""

REPLACEMENT_4 = """#s1-main-table td.name-cell,#s2-main-table td.name-cell,#s3-main-table td.name-cell,#s4-main-table td.name-cell,#pi-main-table td.name-cell,#po-main-table td.name-cell,.st-main-table td.name-cell,#ct-main-table td.name-cell,#mo-matrix-table td.mo-mx-name-cell{cursor:pointer}
/* MD-V2-S41-CHART-RIGHT-FREEZE-COL-MARKER CSS -- freeze company/ticker first column on the LEFT across all V2 tabs (Stage 1-4, PI, PO, ST, CT). Pattern mirrors #mo-matrix-table td.mo-mx-name-cell at L1930. The first th in col-header-row gets sticky-left + higher z-index so the column header pins above tbody. Group-header row first th (supergroup label, has colspan>=2) is NOT sticky-left -- it would visually overlap neighbouring supergroup labels on horizontal scroll. */
#s1-main-table tbody td.name-cell,#s2-main-table tbody td.name-cell,#s3-main-table tbody td.name-cell,#s4-main-table tbody td.name-cell,#pi-main-table tbody td.name-cell,#po-main-table tbody td.name-cell,.st-main-table tbody td.name-cell,#ct-main-table tbody td.name-cell{position:sticky;left:0;z-index:5;background:#fbfaf5;border-right:1px solid #e0dcc8}
#s1-main-table tbody tr:hover td.name-cell,#s2-main-table tbody tr:hover td.name-cell,#s3-main-table tbody tr:hover td.name-cell,#s4-main-table tbody tr:hover td.name-cell,#pi-main-table tbody tr:hover td.name-cell,#po-main-table tbody tr:hover td.name-cell,.st-main-table tbody tr:hover td.name-cell,#ct-main-table tbody tr:hover td.name-cell{background:#f4f1e6}
#s1-main-table thead tr.col-header-row th:first-child,#s2-main-table thead tr.col-header-row th:first-child,#s3-main-table thead tr.col-header-row th:first-child,#s4-main-table thead tr.col-header-row th:first-child,#pi-main-table thead tr.col-header-row th:first-child,#po-main-table thead tr.col-header-row th:first-child,.st-main-table thead tr.col-header-row th:first-child,#ct-main-table thead tr.col-header-row th:first-child{position:sticky;left:0;z-index:70;background:#fbfaf5;border-right:1px solid #e0dcc8}"""

EDITS = [
    (ANCHOR_1, REPLACEMENT_1, "openChart remove chart-from-left"),
    (ANCHOR_2, REPLACEMENT_2, "openChart margin push (right only)"),
    (ANCHOR_3, REPLACEMENT_3, "setChartWidth margin push (right only)"),
    (ANCHOR_4, REPLACEMENT_4, "CSS sticky-first-column for V2 tabs"),
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
            print("[ABORT] WT diverges from HEAD."); return 2
    if MARKER in head_src: print("[OK] MARKER already in HEAD."); return 0
    if MARKER in wt_src:   print("[OK] MARKER in WT, not HEAD."); return 0

    new_src = head_src
    for i, (a, r, label) in enumerate(EDITS):
        n = new_src.count(a)
        print("[*] Edit[%d] %-40s matches: %d (expected 1)" % (i+1, label, n))
        if n != 1:
            print("[ABORT] Edit[%d] anchor count != 1" % (i+1)); return 3
        new_src = new_src.replace(a, r, 1)
    assert MARKER in new_src
    print("[*] Char delta: %+d" % (len(new_src) - len(head_src)))

    if ENABLE_PY_COMPILE:
        try: ast.parse(new_src)
        except SyntaxError as e: print("[ABORT] ast.parse: " + str(e)); return 4
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tf:
            tf.write(new_src); tmp_py = tf.name
        try: py_compile.compile(tmp_py, doraise=True); print("[*] py_compile: OK")
        except py_compile.PyCompileError as e: print("[ABORT] py_compile: " + str(e)); return 5
        finally:
            try: os.unlink(tmp_py)
            except OSError: pass

    print("\n--- DIFF (n=2) ---")
    sys.stdout.writelines(difflib.unified_diff(head_src.splitlines(keepends=True), new_src.splitlines(keepends=True), fromfile="HEAD:" + rel, tofile="PATCHED:" + rel, n=2))
    print("--- END DIFF ---\n")

    if test_mode: print("[OK] DRY-RUN gates passed."); return 0
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
