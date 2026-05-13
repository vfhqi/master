r"""
Patcher: STAGE 2 tab — MD V2 (13-May-26)

Identical pattern to patch_md_v2_stage1_tab_2026_05_13.py.
Reuses Stage 1 CSS via #s1- selector aliases — adds only the few Stage 2-specific overrides
(Group 5 colour, Probable pill ramp 7-10, 4-rating tile palette).

MUST run Windows-side. Idempotent. Supports --force.
"""
import os, shutil, py_compile, sys
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent.resolve()
DASH_PY = SCRIPT_DIR / "build_dashboard.py"
MODULE_JS = SCRIPT_DIR / "_stage2_tab_module.js"
MARKER_BYTES = b"MD-V2-STAGE2-MARKER"

EM = "—".encode("utf-8")
CRLF = b"\r\n"


def fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


def check_fuse_environment_DISABLED():
    here = str(SCRIPT_DIR).replace("\\", "/")
    if "/sessions/" in here or here.startswith("/tmp"):
        fail("Refusing to run from Cowork/FUSE mount.")


ANCHOR_TABS = (
    b'    # MD-V2-STAGE1-MARKER ' + EM + b' Stage 1 (Consolidating/Basing) tab' + CRLF
    + b'    {"id": "stage_1",   "label": "Stage 1",           "accent": "#1b5e20"},' + CRLF
)
REPLACE_TABS = (
    b'    # MD-V2-STAGE1-MARKER ' + EM + b' Stage 1 (Consolidating/Basing) tab' + CRLF
    + b'    {"id": "stage_1",   "label": "Stage 1",           "accent": "#1b5e20"},' + CRLF
    + b'    # MD-V2-STAGE2-MARKER ' + EM + b' Stage 2 (Confirmed uptrend) tab' + CRLF
    + b'    {"id": "stage_2",   "label": "Stage 2",           "accent": "#2e7d32"},' + CRLF
)

ANCHOR_IMPL = (
    b'IMPLEMENTED_TABS = [' + CRLF
    + b'    "summary",' + CRLF
    + b'    "stage_1",  # MD-V2-STAGE1-MARKER' + CRLF
    + b'    "mm99", "bp", "pb", "utr", "vcp", "tech", "combos", "changes", "positions",' + CRLF
    + b'    "ssem", "val",' + CRLF
    + b']'
)
REPLACE_IMPL = (
    b'IMPLEMENTED_TABS = [' + CRLF
    + b'    "summary",' + CRLF
    + b'    "stage_1",  # MD-V2-STAGE1-MARKER' + CRLF
    + b'    "stage_2",  # MD-V2-STAGE2-MARKER' + CRLF
    + b'    "mm99", "bp", "pb", "utr", "vcp", "tech", "combos", "changes", "positions",' + CRLF
    + b'    "ssem", "val",' + CRLF
    + b']'
)

ANCHOR_RENDERTAB = (
    b'  if(id==="summary")renderSummary();' + CRLF
    + b'  else if(id==="stage_1")renderStage1();  /* MD-V2-STAGE1-MARKER */' + CRLF
)
REPLACE_RENDERTAB = (
    b'  if(id==="summary")renderSummary();' + CRLF
    + b'  else if(id==="stage_1")renderStage1();  /* MD-V2-STAGE1-MARKER */' + CRLF
    + b'  else if(id==="stage_2")renderStage2();  /* MD-V2-STAGE2-MARKER */' + CRLF
)

# Stage 2 CSS — only what's different from Stage 1 (sticks the existing #s1- styles).
# Also need #tab-stage_2 versions of the layout selectors, plus #s2-main-table table styling.
# Simplest: alias #s2-main-table to share #s1-main-table rules by adding a multi-selector.
# But we can't easily do that with text-injection — so duplicate the core table CSS.
S2_CSS = b'''
/* MD-V2-STAGE2-MARKER-CSS-START */
/* Reuse #s1-* class names - Stage 2 uses the SAME chrome classes.
   Add only: Group 5 purple band; Probable pill ramp 7 to 10; 4-rating tile tints;
   Stage 2 table selectors mirroring #s1-main-table. */
#tab-stage_2 .group-captions .gcap-g5 { border-color: #6a5a8a; }
#tab-stage_2 .group-captions .gcap-g5 b { color: #6a5a8a; }
#tab-stage_2 .s1-rating-tiles .rating-tile.tint-prob { background: rgba(20, 87, 24, 0.08); }
#tab-stage_2 .s1-rating-tiles .rating-tile.tint-pla  { background: rgba(107, 138, 152, 0.08); }
#tab-stage_2 .s1-rating-tiles .rating-tile.tint-pos  { background: rgba(196, 192, 176, 0.18); }
#tab-stage_2 .s1-rating-tiles .rating-tile.tint-none { background: rgba(224, 221, 208, 0.30); }
#tab-stage_2 .s1-rating-tiles .rt-strip-prob { background: #145718; }
#tab-stage_2 .s1-rating-tiles .rt-strip-pla  { background: #6b8a98; }
#tab-stage_2 .s1-rating-tiles .rt-strip-pos  { background: #c4c0b0; }
#tab-stage_2 .s1-rating-tiles .rt-strip-none { background: #e0ddd0; }

/* Stage 2 main table - mirror all #s1-main-table styles via duplicate selectors */
#s2-main-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 11px; table-layout: fixed; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }
#s2-main-table thead { position: sticky; top: 0; z-index: 50; background: #fbfaf5; box-shadow: 0 2px 4px rgba(0,0,0,0.06); }
#s2-main-table thead th { background: #fbfaf5 !important; border-bottom: 1px solid #e0dcc8; padding: 7px 3px; text-align: center; font-weight: 600; font-size: 10px; color: #666; letter-spacing: 0.2px; cursor: pointer; user-select: none; line-height: 1.25; vertical-align: middle; }
#s2-main-table thead th:hover { background: #f0ebd9 !important; }
#s2-main-table thead .group-header-row th { background: #f3efe2 !important; font-size: 9px; text-transform: uppercase; font-weight: 700; letter-spacing: 0.4px; padding: 5px 3px; cursor: default; white-space: normal; line-height: 1.25; }
#s2-main-table thead .group-header-row th:hover { background: #f3efe2 !important; }
#s2-main-table thead tr.group-header-row th { position: sticky; top: 0; }
#s2-main-table thead tr.col-header-row  th { position: sticky; top: 28px; border-top: 1px solid #e0dcc8; }
#s2-main-table thead .gh-inputs { color: #555; }
#s2-main-table thead .gh-rating, #s2-main-table thead .gh-persist { color: #2e7d32; }
#s2-main-table thead .gh-g1 { color: #b08a4e; }
#s2-main-table thead .gh-g2 { color: #5a8a6a; }
#s2-main-table thead .gh-g3 { color: #4a6a8a; }
#s2-main-table thead .gh-g4 { color: #8a5a6a; }
#s2-main-table thead .gh-g5 { color: #6a5a8a; }
#s2-main-table .hd { display: inline-flex; align-items: center; justify-content: center; gap: 3px; width: 100%; }
#s2-main-table .hd .lbl { white-space: normal; word-break: break-word; }
#s2-main-table .hd .sort-arrow { font-size: 9px; color: #2e7d32; flex: 0 0 auto; line-height: 1; }
#s2-main-table .hd .sort-placeholder { width: 9px; flex: 0 0 auto; }
#s2-main-table td { padding: 5px 4px; border-bottom: 1px solid #efece0; text-align: center; vertical-align: middle; height: 38px; box-sizing: border-box; font-variant-numeric: tabular-nums; }
#s2-main-table tr:hover { background: rgba(27,94,32,0.04); }
#s2-main-table td.grp-start-g1, #s2-main-table th.grp-start-g1 { border-left: 2px solid rgba(176,138,78,0.35); }
#s2-main-table td.grp-start-g2, #s2-main-table th.grp-start-g2 { border-left: 2px solid rgba(90,138,106,0.35); }
#s2-main-table td.grp-start-g3, #s2-main-table th.grp-start-g3 { border-left: 2px solid rgba(74,106,138,0.35); }
#s2-main-table td.grp-start-g4, #s2-main-table th.grp-start-g4 { border-left: 2px solid rgba(138,90,106,0.35); }
#s2-main-table td.grp-start-g5, #s2-main-table th.grp-start-g5 { border-left: 2px solid rgba(106,90,138,0.35); }
#s2-main-table td.grp-start-rating, #s2-main-table th.grp-start-rating { border-left: 2px solid rgba(27,94,32,0.35); }
#s2-main-table td.grp-start-persist, #s2-main-table th.grp-start-persist { border-left: 2px solid rgba(27,94,32,0.35); }
#s2-main-table td.grp-end-g1, #s2-main-table th.grp-end-g1 { border-right: 2px solid rgba(176,138,78,0.35); }
#s2-main-table td.grp-end-g2, #s2-main-table th.grp-end-g2 { border-right: 2px solid rgba(90,138,106,0.35); }
#s2-main-table td.grp-end-g3, #s2-main-table th.grp-end-g3 { border-right: 2px solid rgba(74,106,138,0.35); }
#s2-main-table td.grp-end-g4, #s2-main-table th.grp-end-g4 { border-right: 2px solid rgba(138,90,106,0.35); }
#s2-main-table td.grp-end-g5, #s2-main-table th.grp-end-g5 { border-right: 2px solid rgba(106,90,138,0.35); }
#s2-main-table td.test-pass { background: rgba(27,94,32,0.08); color: #1b5e20; font-weight: 700; }
#s2-main-table td.test-fail { color: #999; }
#s2-main-table td.test-val  { font-size: 10px; }
#s2-main-table td.name-cell { text-align: left; padding: 4px 4px 4px 8px; line-height: 1.15; }
#s2-main-table td.name-cell .co { font-weight: 700; font-size: 11px; color: #2a2a2a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#s2-main-table td.name-cell .tk { font-size: 9px; color: #999; font-weight: 500; margin-top: 1px; }
#s2-main-table td.name-cell .live-dot { color: #2e7d32; font-weight: 700; margin-right: 4px; display: inline-block; vertical-align: middle; line-height: 1; font-size: 10px; }
#s2-main-table td.taxon { text-align: left; font-size: 9px; line-height: 1.2; padding: 4px; }
#s2-main-table td.taxon .ind { color: #666; font-weight: 500; }
#s2-main-table td.taxon .sec { color: #999; }
#s2-main-table col.c-name { width: 130px; }
#s2-main-table col.c-taxon { width: 170px; }
#s2-main-table col.c-price { width: 56px; }
#s2-main-table col.c-52wh { width: 54px; }
#s2-main-table col.c-52wl { width: 54px; }
#s2-main-table col.c-ma150 { width: 54px; }
#s2-main-table col.c-ma200 { width: 54px; }
#s2-main-table col.c-rating { width: 100px; }
#s2-main-table col.c-score { width: 96px; }
#s2-main-table col.c-test { width: 44px; }
#s2-main-table col.c-persist { width: 110px; }
#s2-main-table .pill { display: inline-block; padding: 3px 9px; border-radius: 11px; font-weight: 700; font-size: 10px; color: white; letter-spacing: 0.3px; white-space: nowrap; }
#s2-main-table .pill-prob-7  { background: #2e7d32; color: #fff; }
#s2-main-table .pill-prob-8  { background: #1e6a25; color: #fff; }
#s2-main-table .pill-prob-9  { background: #145718; color: #fff; }
#s2-main-table .pill-prob-10 { background: #08400d; color: #fff; }
#s2-main-table .pill-pla     { background: #6b8a98; color: #fff; }
#s2-main-table .pill-pos     { background: #c4c0b0; color: #5a5a4a; font-weight: 600; }
#s2-main-table .pill-none    { background: #e0ddd0; color: #8a8676; font-weight: 600; }
#s2-main-table .score-pip-row { display: inline-flex; gap: 2px; align-items: center; }
#s2-main-table .pip { width: 6px; height: 6px; border-radius: 50%; background: #ddd; display: inline-block; }
#s2-main-table .pip.on { background: #2e7d32; }
#s2-main-table .score-num { font-weight: 700; color: #2e7d32; margin-left: 5px; font-size: 11px; font-variant-numeric: tabular-nums; }
#s2-main-table .persist-row { display: inline-flex; gap: 1px; align-items: center; }
#s2-main-table .persist-cell { width: 7px; height: 11px; background: #ece8d8; border-radius: 1px; }
#s2-main-table .persist-cell.r-prob { background: #145718; width: 8px; height: 13px; box-shadow: inset 0 0 0 1px #08400d; }
#s2-main-table .persist-cell.r-pla  { background: #6b8a98; }
#s2-main-table .persist-cell.r-pos  { background: #c4c0b0; }
#s2-main-table .persist-cell.r-none { background: #ece8d8; }
#s2-main-table tr.tint-row td.name-cell, #s2-main-table tr.tint-row td.taxon { background: var(--tint-bg) !important; }
#s2-main-table tr.portfolio-band td:last-child { border-right: 4px solid var(--portfolio-color); }
#s2-main-table tr.portfolio-tint { background: var(--portfolio-bg); }
#s2-main-table tr.portfolio-tint:hover { background: var(--portfolio-bg-hover); }
/* MD-V2-STAGE2-MARKER-CSS-END */
'''

# Inject Stage 2 CSS at end of css raw-string (same pattern as Stage 1)
# CORRECTED 13-May-26 PM: post-Stage-1 patch displaces the .filter-pill anchor.
# Use Stage 1 CSS-end marker as the join point.
ANCHOR_CSS_END = b'/* MD-V2-STAGE1-MARKER-CSS-END */\n"""' + CRLF

ANCHOR_RT_FN = b'function renderTab(id){'


def main():
    pass  # disabled for dry-run
    print(f"[stage2-patch] working dir: {SCRIPT_DIR}")
    if not DASH_PY.exists(): fail(f"build_dashboard.py not found")
    if not MODULE_JS.exists(): fail(f"_stage2_tab_module.js not found")
    src = DASH_PY.read_bytes()
    mod = MODULE_JS.read_bytes()
    print(f"[stage2-patch] build_dashboard.py: {len(src)} bytes")
    print(f"[stage2-patch] _stage2_tab_module.js: {len(mod)} bytes")

    if MARKER_BYTES in src:
        if "--force" in sys.argv:
            baks = sorted(SCRIPT_DIR.glob("build_dashboard.py.bak-pre-md-v2-stage2-*"), reverse=True)
            if not baks:
                fail("No Stage 2 backup found to revert from.")
            print(f"[stage2-patch] --force: reverting from {baks[0].name}")
            shutil.copy2(baks[0], DASH_PY)
            src = DASH_PY.read_bytes()
            if MARKER_BYTES in src: fail("Backup still has marker.")
        else:
            print(f"[stage2-patch] marker present — already applied. Use --force to re-apply.")
            return

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = DASH_PY.with_suffix(f".py.bak-pre-md-v2-stage2-{ts}")
    shutil.copy2(DASH_PY, bak)
    print(f"[stage2-patch] backup: {bak.name}")

    # Check anchors
    for label, a in [("TABS", ANCHOR_TABS), ("IMPL", ANCHOR_IMPL), ("RENDERTAB", ANCHOR_RENDERTAB)]:
        if src.count(a) != 1:
            fail(f"Anchor {label} count = {src.count(a)} (expected 1). Did Stage 1 patcher run first?")
    if src.count(ANCHOR_CSS_END) != 1:
        fail("CSS end anchor not unique")
    if src.count(ANCHOR_RT_FN) != 1:
        fail("renderTab fn anchor not unique")

    src = src.replace(ANCHOR_TABS, REPLACE_TABS, 1)
    src = src.replace(ANCHOR_IMPL, REPLACE_IMPL, 1)
    src = src.replace(ANCHOR_RENDERTAB, REPLACE_RENDERTAB, 1)
    # CSS — inject before the `"""` that closes the css raw string
    css_prefix = b'/* MD-V2-STAGE1-MARKER-CSS-END */\n'
    css_suffix = b'"""' + CRLF
    css_repl = css_prefix + S2_CSS + css_suffix
    src = src.replace(ANCHOR_CSS_END, css_repl, 1)
    # Module — inject before function renderTab
    module_block = (
        b'\n/* MD-V2-STAGE2-MARKER-MODULE-START */\n'
        + mod
        + b'\n/* MD-V2-STAGE2-MARKER-MODULE-END */\n\n'
    )
    rt_idx = src.find(ANCHOR_RT_FN)
    src = src[:rt_idx] + module_block + src[rt_idx:]

    tmp = DASH_PY.with_suffix(f".py.tmp-{ts}")
    tmp.write_bytes(src)
    try:
        py_compile.compile(str(tmp), doraise=True)
    except py_compile.PyCompileError as e:
        tmp.unlink(missing_ok=True)
        fail(f"py_compile failed: {e}")
    os.replace(str(tmp), str(DASH_PY))
    print(f"[stage2-patch] OK. New size: {DASH_PY.stat().st_size} bytes")
    print(f"[stage2-patch] marker count: {DASH_PY.read_bytes().count(MARKER_BYTES)}")
    print(f"[stage2-patch] DONE. Next: python scripts\\build_dashboard.py")


if __name__ == "__main__":
    main()
