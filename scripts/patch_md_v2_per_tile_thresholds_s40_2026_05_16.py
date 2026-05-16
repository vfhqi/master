"""
=============================================================================
PATCHER — P4 (S40, 16-May-26) — Per-tile thresholds for Stage tabs (A2)
=============================================================================
Moves the "thresholds X/X · X/X · X/X" string from the Stage column-group
header into each rating-tier tile, as a small line below the rt-sub.

Edits:
  4 group-header edits  — strip "· thresholds ..." suffix from
                          "Stage N rating" cell (one per Stage 1/2/3/4)
  4 rating-tile edits   — insert S{N}_THRESH lookup + a new `<div class=
                          "rt-thresh">≥X/Y</div>` line below rt-sub.
                          Each Stage emits the threshold per tier.
  1 CSS edit            — append .rt-thresh styling alongside .rt-sub.

Thresholds (lifted verbatim from the old group-header strings):
  Stage 1: Possible 2/8, Plausible 3/8, Prob.Early 4/8, Prob.Late 5+/8
  Stage 2: Possible 5/10, Plausible 6/10, Probable 7+/10
  Stage 3: Possible Topping 2/10, Plausible Inv. 4/10, Prob.Inv. 6+/10
  Stage 4: Possible 1/7, Plausible 2/7, Probable 3+/7

None tier shows U+00A0 (non-breaking space) to keep tile heights aligned.

Per D-MD-INFRA-5: text-mode I/O.
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
MARKER         = "MD-V2-S40-PER-TILE-THRESHOLDS"
BAK_TAG        = "per-tile-thresholds"
ENABLE_PY_COMPILE = True

# ----- Group-header anchors / replacements -----
GH_S1_A = "'<th class=\"gh-rating grp-start-rating\" colspan=\"2\">Stage 1 rating · thresholds 2/8 · 3/8 · 4/8 · 5+/8</th>'"
GH_S1_R = "'<th class=\"gh-rating grp-start-rating\" colspan=\"2\">Stage 1 rating</th>' /* " + MARKER + "-gh-s1 */"

GH_S2_A = "'<th class=\"gh-rating grp-start-rating\" colspan=\"2\">Stage 2 rating · thresholds 5/10 · 6/10 · 7+/10</th>'"
GH_S2_R = "'<th class=\"gh-rating grp-start-rating\" colspan=\"2\">Stage 2 rating</th>' /* " + MARKER + "-gh-s2 */"

GH_S3_A = "'<th class=\"gh-rating grp-start-rating\" colspan=\"2\">Stage 3 rating · thresholds 2/10 · 4/10 · 6+/10</th>'"
GH_S3_R = "'<th class=\"gh-rating grp-start-rating\" colspan=\"2\">Stage 3 rating</th>' /* " + MARKER + "-gh-s3 */"

GH_S4_A = "'<th class=\"gh-rating grp-start-rating\" colspan=\"2\">Stage 4 rating · thresholds 1/7 · 2/7 · 3+/7</th>'"
GH_S4_R = "'<th class=\"gh-rating grp-start-rating\" colspan=\"2\">Stage 4 rating</th>' /* " + MARKER + "-gh-s4 */"

# ----- Stage 1 rating-tile populator (5 tiers, var r=..;var cnt=..; on separate lines) -----
S1_TILE_A = (
    "    var order = ['None','Possible','Plausible','Probable Early','Probable Late'];\n"
    "    var strip = {'Probable Late':'pl','Probable Early':'pe','Plausible':'pla','Possible':'pos','None':'none'};\n"
    "    var h = '';\n"
    "    for (var i = 0; i < order.length; i++) {\n"
    "      var r = order[i];\n"
    "      var cnt = uc[r] || 0;\n"
    "      var act = s1State.ratingFilter === r ? ' active' : '';\n"
    "      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;\n"
    "      h += '<div class=\"rating-tile ' + S1_TINT_CLS[r] + act + '\" data-rating=\"' + r + '\">' +\n"
    "           '<div class=\"rt-label\">' + r + '</div>' +\n"
    "           '<div class=\"rt-count\">' + cnt.toLocaleString('en-GB') + '</div>' +\n"
    "           '<div class=\"rt-sub\">of ' + total.toLocaleString('en-GB') + ' · ' + pct + '%</div>' +\n"
    "           '<div class=\"rt-strip rt-strip-' + strip[r] + '\"></div>' +\n"
    "           '</div>';\n"
    "    }"
)
S1_TILE_R = (
    "    var order = ['None','Possible','Plausible','Probable Early','Probable Late'];\n"
    "    var strip = {'Probable Late':'pl','Probable Early':'pe','Plausible':'pla','Possible':'pos','None':'none'};\n"
    "    var S1_THRESH = {'Probable Late':'≥5/8','Probable Early':'≥4/8','Plausible':'≥3/8','Possible':'≥2/8','None':'\\u00a0'}; /* " + MARKER + "-tile-s1 */\n"
    "    var h = '';\n"
    "    for (var i = 0; i < order.length; i++) {\n"
    "      var r = order[i];\n"
    "      var cnt = uc[r] || 0;\n"
    "      var act = s1State.ratingFilter === r ? ' active' : '';\n"
    "      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;\n"
    "      h += '<div class=\"rating-tile ' + S1_TINT_CLS[r] + act + '\" data-rating=\"' + r + '\">' +\n"
    "           '<div class=\"rt-label\">' + r + '</div>' +\n"
    "           '<div class=\"rt-count\">' + cnt.toLocaleString('en-GB') + '</div>' +\n"
    "           '<div class=\"rt-sub\">of ' + total.toLocaleString('en-GB') + ' · ' + pct + '%</div>' +\n"
    "           '<div class=\"rt-thresh\">' + (S1_THRESH[r] || '\\u00a0') + '</div>' +\n"
    "           '<div class=\"rt-strip rt-strip-' + strip[r] + '\"></div>' +\n"
    "           '</div>';\n"
    "    }"
)

# ----- Stage 2 populator (4 tiers, combined var r/cnt) -----
S2_TILE_A = (
    "    var order = ['None','Possible','Plausible','Probable'];\n"
    "    var strip = {'Probable':'prob','Plausible':'pla','Possible':'pos','None':'none'};\n"
    "    var h = '';\n"
    "    for (var i = 0; i < order.length; i++) {\n"
    "      var r = order[i], cnt = uc[r] || 0;\n"
    "      var act = s2State.ratingFilter === r ? ' active' : '';\n"
    "      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;\n"
    "      h += '<div class=\"rating-tile ' + S2_TINT_CLS[r] + act + '\" data-rating=\"' + r + '\">' +\n"
    "           '<div class=\"rt-label\">' + r + '</div>' +\n"
    "           '<div class=\"rt-count\">' + cnt.toLocaleString('en-GB') + '</div>' +\n"
    "           '<div class=\"rt-sub\">of ' + total.toLocaleString('en-GB') + ' · ' + pct + '%</div>' +\n"
    "           '<div class=\"rt-strip rt-strip-' + strip[r] + '\"></div>' +\n"
    "           '</div>';\n"
    "    }"
)
S2_TILE_R = (
    "    var order = ['None','Possible','Plausible','Probable'];\n"
    "    var strip = {'Probable':'prob','Plausible':'pla','Possible':'pos','None':'none'};\n"
    "    var S2_THRESH = {'Probable':'≥7/10','Plausible':'≥6/10','Possible':'≥5/10','None':'\\u00a0'}; /* " + MARKER + "-tile-s2 */\n"
    "    var h = '';\n"
    "    for (var i = 0; i < order.length; i++) {\n"
    "      var r = order[i], cnt = uc[r] || 0;\n"
    "      var act = s2State.ratingFilter === r ? ' active' : '';\n"
    "      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;\n"
    "      h += '<div class=\"rating-tile ' + S2_TINT_CLS[r] + act + '\" data-rating=\"' + r + '\">' +\n"
    "           '<div class=\"rt-label\">' + r + '</div>' +\n"
    "           '<div class=\"rt-count\">' + cnt.toLocaleString('en-GB') + '</div>' +\n"
    "           '<div class=\"rt-sub\">of ' + total.toLocaleString('en-GB') + ' · ' + pct + '%</div>' +\n"
    "           '<div class=\"rt-thresh\">' + (S2_THRESH[r] || '\\u00a0') + '</div>' +\n"
    "           '<div class=\"rt-strip rt-strip-' + strip[r] + '\"></div>' +\n"
    "           '</div>';\n"
    "    }"
)

# ----- Stage 3 populator (4 tiers, different tier names) -----
S3_TILE_A = (
    "    var order = ['None','Possible Topping','Plausible Invalidation','Probable Invalidation'];\n"
    "    var strip = {\n"
    "      'Probable Invalidation':'prob-inv',\n"
    "      'Plausible Invalidation':'pla-inv',\n"
    "      'Possible Topping':'pos-top',\n"
    "      'None':'none'\n"
    "    };\n"
    "    var h = '';\n"
    "    for (var i = 0; i < order.length; i++) {\n"
    "      var r = order[i], cnt = uc[r] || 0;\n"
    "      var act = s3State.ratingFilter === r ? ' active' : '';\n"
    "      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;\n"
    "      h += '<div class=\"rating-tile ' + S3_TINT_CLS[r] + act + '\" data-rating=\"' + r + '\">' +\n"
    "           '<div class=\"rt-label\">' + r + '</div>' +\n"
    "           '<div class=\"rt-count\">' + cnt.toLocaleString('en-GB') + '</div>' +\n"
    "           '<div class=\"rt-sub\">of ' + total.toLocaleString('en-GB') + ' · ' + pct + '%</div>' +\n"
    "           '<div class=\"rt-strip rt-strip-' + strip[r] + '\"></div>' +\n"
    "           '</div>';\n"
    "    }"
)
S3_TILE_R = (
    "    var order = ['None','Possible Topping','Plausible Invalidation','Probable Invalidation'];\n"
    "    var strip = {\n"
    "      'Probable Invalidation':'prob-inv',\n"
    "      'Plausible Invalidation':'pla-inv',\n"
    "      'Possible Topping':'pos-top',\n"
    "      'None':'none'\n"
    "    };\n"
    "    var S3_THRESH = {'Probable Invalidation':'≥6/10','Plausible Invalidation':'≥4/10','Possible Topping':'≥2/10','None':'\\u00a0'}; /* " + MARKER + "-tile-s3 */\n"
    "    var h = '';\n"
    "    for (var i = 0; i < order.length; i++) {\n"
    "      var r = order[i], cnt = uc[r] || 0;\n"
    "      var act = s3State.ratingFilter === r ? ' active' : '';\n"
    "      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;\n"
    "      h += '<div class=\"rating-tile ' + S3_TINT_CLS[r] + act + '\" data-rating=\"' + r + '\">' +\n"
    "           '<div class=\"rt-label\">' + r + '</div>' +\n"
    "           '<div class=\"rt-count\">' + cnt.toLocaleString('en-GB') + '</div>' +\n"
    "           '<div class=\"rt-sub\">of ' + total.toLocaleString('en-GB') + ' · ' + pct + '%</div>' +\n"
    "           '<div class=\"rt-thresh\">' + (S3_THRESH[r] || '\\u00a0') + '</div>' +\n"
    "           '<div class=\"rt-strip rt-strip-' + strip[r] + '\"></div>' +\n"
    "           '</div>';\n"
    "    }"
)

# ----- Stage 4 populator (4 tiers, combined var r/cnt) -----
S4_TILE_A = (
    "    var order = ['None','Possible','Plausible','Probable'];\n"
    "    var strip = {'Probable':'prob','Plausible':'pla','Possible':'pos','None':'none'};\n"
    "    var h = '';\n"
    "    for (var i = 0; i < order.length; i++) {\n"
    "      var r = order[i], cnt = uc[r] || 0;\n"
    "      var act = s4State.ratingFilter === r ? ' active' : '';\n"
    "      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;\n"
    "      h += '<div class=\"rating-tile ' + S4_TINT_CLS[r] + act + '\" data-rating=\"' + r + '\">' +\n"
    "           '<div class=\"rt-label\">' + r + '</div>' +\n"
    "           '<div class=\"rt-count\">' + cnt.toLocaleString('en-GB') + '</div>' +\n"
    "           '<div class=\"rt-sub\">of ' + total.toLocaleString('en-GB') + ' · ' + pct + '%</div>' +\n"
    "           '<div class=\"rt-strip rt-strip-' + strip[r] + '\"></div>' +\n"
    "           '</div>';\n"
    "    }"
)
S4_TILE_R = (
    "    var order = ['None','Possible','Plausible','Probable'];\n"
    "    var strip = {'Probable':'prob','Plausible':'pla','Possible':'pos','None':'none'};\n"
    "    var S4_THRESH = {'Probable':'≥3/7','Plausible':'≥2/7','Possible':'≥1/7','None':'\\u00a0'}; /* " + MARKER + "-tile-s4 */\n"
    "    var h = '';\n"
    "    for (var i = 0; i < order.length; i++) {\n"
    "      var r = order[i], cnt = uc[r] || 0;\n"
    "      var act = s4State.ratingFilter === r ? ' active' : '';\n"
    "      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;\n"
    "      h += '<div class=\"rating-tile ' + S4_TINT_CLS[r] + act + '\" data-rating=\"' + r + '\">' +\n"
    "           '<div class=\"rt-label\">' + r + '</div>' +\n"
    "           '<div class=\"rt-count\">' + cnt.toLocaleString('en-GB') + '</div>' +\n"
    "           '<div class=\"rt-sub\">of ' + total.toLocaleString('en-GB') + ' · ' + pct + '%</div>' +\n"
    "           '<div class=\"rt-thresh\">' + (S4_THRESH[r] || '\\u00a0') + '</div>' +\n"
    "           '<div class=\"rt-strip rt-strip-' + strip[r] + '\"></div>' +\n"
    "           '</div>';\n"
    "    }"
)

# ----- CSS for .rt-thresh — anchor after rt-sub rule -----
CSS_A = ".s1-rating-tiles .rt-sub { font-size: 10px; color: #999; margin-top: 3px; }"
CSS_R = (
    ".s1-rating-tiles .rt-sub { font-size: 10px; color: #999; margin-top: 3px; }\n"
    "/* " + MARKER + ": per-tile threshold line beneath rt-sub; shows the\n"
    "   pass-count threshold for each tier (≥X/Y). None tier emits NBSP to\n"
    "   preserve vertical rhythm. Applies to all 4 Stage tabs via the\n"
    "   s1-rating-tiles class (shared by Stage 2/3/4 grids). */\n"
    ".s1-rating-tiles .rt-thresh { font-size: 10px; font-weight: 600; color: #777; margin-top: 4px; letter-spacing: 0.1px; }\n"
    ".s1-rating-tiles .rating-tile.active .rt-thresh { color: rgba(255,255,255,0.85); }"
)

EDITS: list[tuple[str, str, str]] = [
    ("GH_S1",   GH_S1_A,   GH_S1_R),
    ("GH_S2",   GH_S2_A,   GH_S2_R),
    ("GH_S3",   GH_S3_A,   GH_S3_R),
    ("GH_S4",   GH_S4_A,   GH_S4_R),
    ("TILE_S1", S1_TILE_A, S1_TILE_R),
    ("TILE_S2", S2_TILE_A, S2_TILE_R),
    ("TILE_S3", S3_TILE_A, S3_TILE_R),
    ("TILE_S4", S4_TILE_A, S4_TILE_R),
    ("CSS",     CSS_A,     CSS_R),
]
EXPECTED_MARKER_COUNT = 9  # 4 GH + 4 TILE + 1 CSS = 9 marker occurrences


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
    print(f"[*] Edits:          {len(EDITS)}")
    print(f"[*] Mode:           {'DRY-RUN (--test)' if test_mode else 'WRITE'}")

    head_src = _git_show_head_text(repo, rel)
    wt_src   = _wt_text(repo, rel)
    print(f"[*] HEAD chars:     {len(head_src)}")
    print(f"[*] WT chars:       {len(wt_src)}")

    if _md5_text(wt_src) != _md5_text(head_src):
        msg = "Working tree diverges from HEAD (text-normalized compare)."
        if test_mode:
            print(f"[WARN] {msg}")
            print("       Dry-run continues -- gates operate on HEAD source.")
        else:
            print(f"[ABORT] {msg}")
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
        print(f"[*] {name:<9} anchor matches: {n} (expected 1)")
        if n != 1:
            print(f"[ABORT] {name} anchor count != 1.")
            return 3
        new_src = new_src.replace(anchor, replacement, 1)

    n_marker = new_src.count(MARKER)
    if n_marker != EXPECTED_MARKER_COUNT:
        print(f"[ABORT] expected {EXPECTED_MARKER_COUNT} MARKER occurrences, got {n_marker}")
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

    print("\n--- DIFF first 80 lines ---")
    diff_text = "".join(difflib.unified_diff(
        head_src.splitlines(keepends=True),
        new_src.splitlines(keepends=True),
        fromfile=f"HEAD:{rel}", tofile=f"PATCHED:{rel}", n=1,
    ))
    print("".join(diff_text.splitlines(keepends=True)[:80]))
    print("--- END DIFF (truncated) ---\n")

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
