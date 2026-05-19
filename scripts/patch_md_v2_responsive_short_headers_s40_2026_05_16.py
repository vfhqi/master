"""
=============================================================================
PATCHER — P3 (S40, 16-May-26) — Responsive contracted column headers (A3)
=============================================================================
At narrow viewports (<= 1200px), swap each of the 20 Master Overview
matrix screen-column headers from their full label to a short form, so
they fit cleanly in the 76px column without consuming 3-4 vertical lines.

Mechanism: each MO_ROWS entry carries both `label` (existing) and `short`
(new); the matrix + summary-table column-header emits add a
`data-short="..."` attribute and wrap the long label in
`<span class="mo-col-long">`. A scoped @media query at max-width:1200px
hides the long span and emits the short via `::before { content: attr(data-short); }`.

EDIT 1: MO_ROWS array literal — add `short:` to each of 20 entries.
EDIT 2: summary-table column-header emit (moRenderTable, ~line 12405).
EDIT 3: matrix column-header emit (moMxBuildHead, ~line 12488).
EDIT 4: append the @media CSS rule alongside the v2-nav-grp-label CSS.

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
MARKER         = "MD-V2-S40-RESPONSIVE-SHORT-HEADERS"
BAK_TAG        = "responsive-short-headers"
ENABLE_PY_COMPILE = True

# ============ EDIT 1: rewrite MO_ROWS with `short` field on every entry ====
MO_ROWS_ANCHOR = """  var MO_ROWS = [
    // -- Stages --
    { section:'Stages', key:'stage_1', label:'Stage 1 - Basing', ratingPath:'stage:stage_1', tabId:'stage_1', patternKey:null },
    { section:'Stages', key:'stage_2', label:'Stage 2 - Uptrend', ratingPath:'stage:stage_2', tabId:'stage_2', patternKey:null },
    { section:'Stages', key:'stage_3', label:'Stage 3 - Topping', ratingPath:'stage:stage_3', tabId:'stage_3', patternKey:null },
    { section:'Stages', key:'stage_4', label:'Stage 4 - Decline', ratingPath:'stage:stage_4', tabId:'stage_4', patternKey:null },
    // -- Pre-test indicators --
    { section:'Pre-farfalle indicators', key:'pulling_back_uptrend', label:'Pulling back within MT/LT uptrend', ratingPath:'group:pre_indicators:pulling_back_uptrend', tabId:'pre_indicators', patternKey:'pulling_back_uptrend' },
    { section:'Pre-farfalle indicators', key:'basing', label:'Basing in a MT/LT uptrend', ratingPath:'group:pre_indicators:basing', tabId:'pre_indicators', patternKey:'basing' },
    { section:'Pre-farfalle indicators', key:'collapsing', label:'Collapsing', ratingPath:'group:pre_indicators:collapsing', tabId:'pre_indicators', patternKey:'collapsing' },
    // -- Post-test indicators (ratingPath -> md_v2.post_indicators.<k>.rating;
    //    md_v2.indicators.<k> is a bare boolean and has no .rating - Request 1) --
    { section:'Post-farfalle indicators', key:'breakout', label:'Breakout', ratingPath:'group:post_indicators:breakout', tabId:'post_indicators', patternKey:'breakout' },
    { section:'Post-farfalle indicators', key:'advancing', label:'Advancing', ratingPath:'group:post_indicators:advancing', tabId:'post_indicators', patternKey:'advancing' },
    { section:'Post-farfalle indicators', key:'breakdown_50D', label:'Negatively breaking through ST trend (50D MA)', ratingPath:'group:post_indicators:breakdown_50D', tabId:'post_indicators', patternKey:'breakdown_50D' },
    { section:'Post-farfalle indicators', key:'breakdown_150D', label:'Negatively breaking through MT trend (150D MA)', ratingPath:'group:post_indicators:breakdown_150D', tabId:'post_indicators', patternKey:'breakdown_150D' },
    { section:'Post-farfalle indicators', key:'breakdown_200D', label:'Negatively breaking through LT trend (200D MA)', ratingPath:'group:post_indicators:breakdown_200D', tabId:'post_indicators', patternKey:'breakdown_200D' },
    // -- Capital qualification setups --
    { section:'Capital qualification setups', key:'probing_bet', label:'Probing bet', ratingPath:'group:setups:probing_bet', tabId:'setups_s1pb', patternKey:'probing_bet' },
    { section:'Capital qualification setups', key:'vcp_after_s1_plateau', label:'VCP after Stage 1->2 plateau', ratingPath:'group:setups:vcp_after_s1_plateau', tabId:'setups_s1pb', patternKey:'vcp_after_s1_plateau' },
    { section:'Capital qualification setups', key:'healthy_retest', label:'Healthy retest within MT/LT uptrend', ratingPath:'group:setups:healthy_retest', tabId:'setups_s2vcp', patternKey:'healthy_retest' },
    { section:'Capital qualification setups', key:'vcp_after_s2_base', label:'VCP after Stage 2 base', ratingPath:'group:setups:vcp_after_s2_base', tabId:'setups_s2vcp', patternKey:'vcp_after_s2_base' },
    // -- Capital deployment tests --
    { section:'Capital deployment tests', key:'ma_retest_upwards', label:'Upwards moving average retest', ratingPath:'group:tests:ma_retest_upwards', tabId:'tests', patternKey:'ma_retest_upwards' },
    { section:'Capital deployment tests', key:'vcp_deploy_s1', label:'VCP after Stage 1->2', ratingPath:'group:tests:vcp_deploy_s1', tabId:'tests', patternKey:'vcp_deploy_s1' },
    { section:'Capital deployment tests', key:'vcp_deploy_s2', label:'VCP after Stage 2 base', ratingPath:'group:tests:vcp_deploy_s2', tabId:'tests', patternKey:'vcp_deploy_s2' },
    { section:'Capital deployment tests', key:'probing_bet_test', label:'Probing bet', ratingPath:'group:tests:probing_bet', tabId:'tests', patternKey:'probing_bet' }
  ];"""

MO_ROWS_REPLACEMENT = """  var MO_ROWS = [
    // -- Stages --
    { section:'Stages', key:'stage_1', label:'Stage 1 - Basing', short:'S1 Basing', ratingPath:'stage:stage_1', tabId:'stage_1', patternKey:null },
    { section:'Stages', key:'stage_2', label:'Stage 2 - Uptrend', short:'S2 Uptrend', ratingPath:'stage:stage_2', tabId:'stage_2', patternKey:null },
    { section:'Stages', key:'stage_3', label:'Stage 3 - Topping', short:'S3 Topping', ratingPath:'stage:stage_3', tabId:'stage_3', patternKey:null },
    { section:'Stages', key:'stage_4', label:'Stage 4 - Decline', short:'S4 Decline', ratingPath:'stage:stage_4', tabId:'stage_4', patternKey:null },
    // -- Pre-test indicators --
    { section:'Pre-farfalle indicators', key:'pulling_back_uptrend', label:'Pulling back within MT/LT uptrend', short:'Pulling back', ratingPath:'group:pre_indicators:pulling_back_uptrend', tabId:'pre_indicators', patternKey:'pulling_back_uptrend' },
    { section:'Pre-farfalle indicators', key:'basing', label:'Basing in a MT/LT uptrend', short:'Basing', ratingPath:'group:pre_indicators:basing', tabId:'pre_indicators', patternKey:'basing' },
    { section:'Pre-farfalle indicators', key:'collapsing', label:'Collapsing', short:'Collapsing', ratingPath:'group:pre_indicators:collapsing', tabId:'pre_indicators', patternKey:'collapsing' },
    // -- Post-test indicators (ratingPath -> md_v2.post_indicators.<k>.rating;
    //    md_v2.indicators.<k> is a bare boolean and has no .rating - Request 1) --
    { section:'Post-farfalle indicators', key:'breakout', label:'Breakout', short:'Breakout', ratingPath:'group:post_indicators:breakout', tabId:'post_indicators', patternKey:'breakout' },
    { section:'Post-farfalle indicators', key:'advancing', label:'Advancing', short:'Advancing', ratingPath:'group:post_indicators:advancing', tabId:'post_indicators', patternKey:'advancing' },
    { section:'Post-farfalle indicators', key:'breakdown_50D', label:'Negatively breaking through ST trend (50D MA)', short:'Breaking 50D', ratingPath:'group:post_indicators:breakdown_50D', tabId:'post_indicators', patternKey:'breakdown_50D' },
    { section:'Post-farfalle indicators', key:'breakdown_150D', label:'Negatively breaking through MT trend (150D MA)', short:'Breaking 150D', ratingPath:'group:post_indicators:breakdown_150D', tabId:'post_indicators', patternKey:'breakdown_150D' },
    { section:'Post-farfalle indicators', key:'breakdown_200D', label:'Negatively breaking through LT trend (200D MA)', short:'Breaking 200D', ratingPath:'group:post_indicators:breakdown_200D', tabId:'post_indicators', patternKey:'breakdown_200D' },
    // -- Capital qualification setups --
    { section:'Capital qualification setups', key:'probing_bet', label:'Probing bet', short:'Probing bet', ratingPath:'group:setups:probing_bet', tabId:'setups_s1pb', patternKey:'probing_bet' },
    { section:'Capital qualification setups', key:'vcp_after_s1_plateau', label:'VCP after Stage 1->2 plateau', short:'VCP S1 plateau', ratingPath:'group:setups:vcp_after_s1_plateau', tabId:'setups_s1pb', patternKey:'vcp_after_s1_plateau' },
    { section:'Capital qualification setups', key:'healthy_retest', label:'Healthy retest within MT/LT uptrend', short:'Healthy retest', ratingPath:'group:setups:healthy_retest', tabId:'setups_s2vcp', patternKey:'healthy_retest' },
    { section:'Capital qualification setups', key:'vcp_after_s2_base', label:'VCP after Stage 2 base', short:'VCP S2 base', ratingPath:'group:setups:vcp_after_s2_base', tabId:'setups_s2vcp', patternKey:'vcp_after_s2_base' },
    // -- Capital deployment tests --
    { section:'Capital deployment tests', key:'ma_retest_upwards', label:'Upwards moving average retest', short:'MA retest', ratingPath:'group:tests:ma_retest_upwards', tabId:'tests', patternKey:'ma_retest_upwards' },
    { section:'Capital deployment tests', key:'vcp_deploy_s1', label:'VCP after Stage 1->2', short:'VCP S1 deploy', ratingPath:'group:tests:vcp_deploy_s1', tabId:'tests', patternKey:'vcp_deploy_s1' },
    { section:'Capital deployment tests', key:'vcp_deploy_s2', label:'VCP after Stage 2 base', short:'VCP S2 deploy', ratingPath:'group:tests:vcp_deploy_s2', tabId:'tests', patternKey:'vcp_deploy_s2' },
    { section:'Capital deployment tests', key:'probing_bet_test', label:'Probing bet', short:'PB deploy', ratingPath:'group:tests:probing_bet', tabId:'tests', patternKey:'probing_bet' }
  ]; /* """ + MARKER + """ — short forms added */"""

# ============ EDIT 2: summary table col-header emit ====
SUM_ANCHOR = """      var colTr = '<tr class="mo-col-row">';
      for (var t = 0; t < MO_ROWS.length; t++) {
        colTr += '<th title="' + moMxAttr(MO_ROWS[t].label + ' - open this screen\\'s tab') + '" ' +
          'onclick="moJumpToTab(\\'' + moMxAttr(MO_ROWS[t].key) + '\\')">' +
          moMxText(MO_ROWS[t].label) + '</th>';
      }"""

SUM_REPLACEMENT = """      var colTr = '<tr class="mo-col-row">';
      for (var t = 0; t < MO_ROWS.length; t++) {
        colTr += '<th class="mo-col-with-short" title="' + moMxAttr(MO_ROWS[t].label + ' - open this screen\\'s tab') + '" ' +
          'data-short="' + moMxAttr(MO_ROWS[t].short || MO_ROWS[t].label) + '" ' +
          'onclick="moJumpToTab(\\'' + moMxAttr(MO_ROWS[t].key) + '\\')">' +
          '<span class="mo-col-long">' + moMxText(MO_ROWS[t].label) + '</span></th>';
      }"""

# ============ EDIT 3: matrix col-header emit ====
MX_ANCHOR = """    var colTr = '<tr class="mo-mx-col-row"><th class="mo-mx-screen-col">Stock</th>';
    for (var t = 0; t < MO_ROWS.length; t++) {
      colTr += '<th title="' + moMxAttr(MO_ROWS[t].label + ' - open this screen\\'s tab') + '" ' +
        'onclick="moJumpToTab(\\'' + moMxAttr(MO_ROWS[t].key) + '\\')" style="cursor:pointer">' +
        moMxText(MO_ROWS[t].label) + '</th>';
    }"""

MX_REPLACEMENT = """    var colTr = '<tr class="mo-mx-col-row"><th class="mo-mx-screen-col">Stock</th>';
    for (var t = 0; t < MO_ROWS.length; t++) {
      colTr += '<th class="mo-col-with-short" title="' + moMxAttr(MO_ROWS[t].label + ' - open this screen\\'s tab') + '" ' +
        'data-short="' + moMxAttr(MO_ROWS[t].short || MO_ROWS[t].label) + '" ' +
        'onclick="moJumpToTab(\\'' + moMxAttr(MO_ROWS[t].key) + '\\')" style="cursor:pointer">' +
        '<span class="mo-col-long">' + moMxText(MO_ROWS[t].label) + '</span></th>';
    }"""

# ============ EDIT 4: CSS @media query anchor on the P2-introduced Android block end ====
# Place this AFTER the P2 Android block (assumes P2 has shipped before P3, which
# matches the proposed batch ordering). For decoupling, anchor instead on the
# v2-nav-btn.v2-grp-tests:hover line at the end of the v2-nav CSS, then add the
# rule there. We use the original end-of-v2-nav-CSS anchor (same as P2's anchor
# would be in HEAD if P2 had not yet shipped) — but to keep this patcher
# independent of P2, use a different anchor: the start of the
# /* ===== Group caption parity for Stage 2/3/4 ===== */ block.
CSS_ANCHOR = """/* ===== Group caption parity for Stage 2/3/4 ===== */
/* Stage 1 already styles .gcap inside .group-captions. Replicate for s2/s3/s4. */"""

CSS_REPLACEMENT = """/* """ + MARKER + """: at narrow viewports (tablet + smaller), hide the long
   column-header label and show the short form via attr(data-short).
   Each MO_ROWS entry now carries `short:` alongside `label:`. */
@media (max-width: 1200px) {
  th.mo-col-with-short .mo-col-long { display: none; }
  th.mo-col-with-short::before { content: attr(data-short); }
}

/* ===== Group caption parity for Stage 2/3/4 ===== */
/* Stage 1 already styles .gcap inside .group-captions. Replicate for s2/s3/s4. */"""

EDITS: list[tuple[str, str, str]] = [
    ("MO_ROWS",   MO_ROWS_ANCHOR,   MO_ROWS_REPLACEMENT),
    ("SUM_HDR",   SUM_ANCHOR,       SUM_REPLACEMENT),
    ("MX_HDR",    MX_ANCHOR,        MX_REPLACEMENT),
    ("CSS_MEDIA", CSS_ANCHOR,       CSS_REPLACEMENT),
]
EXPECTED_EDITS = len(EDITS)


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
    print(f"[*] Edits:          {EXPECTED_EDITS}")
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
    for name, anchor, replacement in EDITS:
        n = new_src.count(anchor)
        print(f"[*] {name:<10} anchor matches: {n} (expected 1)")
        if n != 1:
            print(f"[ABORT] {name} anchor count != 1.")
            return 3
        new_src = new_src.replace(anchor, replacement, 1)

    n_marker = new_src.count(MARKER)
    expected_marker = 2  # one in MO_ROWS comment, one in CSS comment
    if n_marker != expected_marker:
        print(f"[ABORT] expected {expected_marker} MARKER occurrences, got {n_marker}")
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

    print("\n--- DIFF (unified, text-normalized; first 60 lines) ---")
    diff_text = "".join(difflib.unified_diff(
        head_src.splitlines(keepends=True),
        new_src.splitlines(keepends=True),
        fromfile=f"HEAD:{rel}", tofile=f"PATCHED:{rel}", n=2,
    ))
    sys.stdout.write(diff_text)
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
    print(f"[OK] Next: python scripts/build_dashboard.py && git add scripts/build_dashboard.py index.html && git commit && git push")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
