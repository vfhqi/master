r"""
Patcher: STAGE 4 tab — MD V2 (13-May-26)

Chains after Stage 3 patcher. Anchors land on the post-Stage-3 build_dashboard.py
shape. Stage 4 uses a deep-red palette (the heaviest bearish tone), 7 tests
across 3 groups.

MUST run Windows-side. Idempotent. Supports --force.
"""
import os, shutil, py_compile, sys
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent.resolve()
DASH_PY = SCRIPT_DIR / "build_dashboard.py"
MODULE_JS = SCRIPT_DIR / "_stage4_tab_module.js"
MARKER_BYTES = b"MD-V2-STAGE4-MARKER"

EM = "\xe2\x80\x94".encode("latin-1")  # em-dash literal bytes \xe2\x80\x94 (UTF-8 for U+2014)
CRLF = b"\r\n"


def fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


def check_fuse_environment():
    here = str(SCRIPT_DIR).replace("\\", "/")
    if "/sessions/" in here or here.startswith("/tmp"):
        fail("Refusing to run from Cowork/FUSE mount.")


# Anchor lands AFTER Stage 3 patcher has applied. Stage 4 inserts after Stage 3.
ANCHOR_TABS = (
    b'    # MD-V2-STAGE3-MARKER ' + EM + b' Stage 3 (Topping / Invalidation) tab' + CRLF
    + b'    {"id": "stage_3",   "label": "Stage 3",           "accent": "#b45309"},' + CRLF
)
REPLACE_TABS = (
    b'    # MD-V2-STAGE3-MARKER ' + EM + b' Stage 3 (Topping / Invalidation) tab' + CRLF
    + b'    {"id": "stage_3",   "label": "Stage 3",           "accent": "#b45309"},' + CRLF
    + b'    # MD-V2-STAGE4-MARKER ' + EM + b' Stage 4 (Decline / Capitulation) tab' + CRLF
    + b'    {"id": "stage_4",   "label": "Stage 4",           "accent": "#991b1b"},' + CRLF
)

ANCHOR_IMPL = (
    b'IMPLEMENTED_TABS = [' + CRLF
    + b'    "summary",' + CRLF
    + b'    "stage_1",  # MD-V2-STAGE1-MARKER' + CRLF
    + b'    "stage_2",  # MD-V2-STAGE2-MARKER' + CRLF
    + b'    "stage_3",  # MD-V2-STAGE3-MARKER' + CRLF
    + b'    "mm99", "bp", "pb", "utr", "vcp", "tech", "combos", "changes", "positions",' + CRLF
    + b'    "ssem", "val",' + CRLF
    + b']'
)
REPLACE_IMPL = (
    b'IMPLEMENTED_TABS = [' + CRLF
    + b'    "summary",' + CRLF
    + b'    "stage_1",  # MD-V2-STAGE1-MARKER' + CRLF
    + b'    "stage_2",  # MD-V2-STAGE2-MARKER' + CRLF
    + b'    "stage_3",  # MD-V2-STAGE3-MARKER' + CRLF
    + b'    "stage_4",  # MD-V2-STAGE4-MARKER' + CRLF
    + b'    "mm99", "bp", "pb", "utr", "vcp", "tech", "combos", "changes", "positions",' + CRLF
    + b'    "ssem", "val",' + CRLF
    + b']'
)

ANCHOR_RENDERTAB = (
    b'  if(id==="summary")renderSummary();' + CRLF
    + b'  else if(id==="stage_1")renderStage1();  /* MD-V2-STAGE1-MARKER */' + CRLF
    + b'  else if(id==="stage_2")renderStage2();  /* MD-V2-STAGE2-MARKER */' + CRLF
    + b'  else if(id==="stage_3")renderStage3();  /* MD-V2-STAGE3-MARKER */' + CRLF
)
REPLACE_RENDERTAB = (
    b'  if(id==="summary")renderSummary();' + CRLF
    + b'  else if(id==="stage_1")renderStage1();  /* MD-V2-STAGE1-MARKER */' + CRLF
    + b'  else if(id==="stage_2")renderStage2();  /* MD-V2-STAGE2-MARKER */' + CRLF
    + b'  else if(id==="stage_3")renderStage3();  /* MD-V2-STAGE3-MARKER */' + CRLF
    + b'  else if(id==="stage_4")renderStage4();  /* MD-V2-STAGE4-MARKER */' + CRLF
)

# Stage 4 CSS - deep red palette. CSS literal MUST be ASCII-only per D-MD-V2-24.
# All comments use plain ASCII hyphens (no em-dashes) to avoid null-byte FUSE bug.
S4_CSS = b'''
/* MD-V2-STAGE4-MARKER-CSS-START */
/* Stage 4 (Decline / Capitulation) - deep-red palette across all 3 groups. */
#tab-stage_4 .group-captions .gcap-g1 { border-color: #991b1b; }
#tab-stage_4 .group-captions .gcap-g1 b { color: #991b1b; }
#tab-stage_4 .group-captions .gcap-g2 { border-color: #7f1d1d; }
#tab-stage_4 .group-captions .gcap-g2 b { color: #7f1d1d; }
#tab-stage_4 .group-captions .gcap-g3 { border-color: #6a5a8a; }
#tab-stage_4 .group-captions .gcap-g3 b { color: #6a5a8a; }

/* Rating tile tints - deep red */
#tab-stage_4 .s1-rating-tiles .rating-tile.tint-prob { background: rgba(127, 29, 29, 0.12); }
#tab-stage_4 .s1-rating-tiles .rating-tile.tint-pla  { background: rgba(153, 27, 27, 0.10); }
#tab-stage_4 .s1-rating-tiles .rating-tile.tint-pos  { background: rgba(180, 83, 9, 0.10); }
#tab-stage_4 .s1-rating-tiles .rating-tile.tint-none { background: rgba(224, 221, 208, 0.30); }
#tab-stage_4 .s1-rating-tiles .rt-strip-prob { background: #5a0808; }
#tab-stage_4 .s1-rating-tiles .rt-strip-pla  { background: #991b1b; }
#tab-stage_4 .s1-rating-tiles .rt-strip-pos  { background: #b45309; }
#tab-stage_4 .s1-rating-tiles .rt-strip-none { background: #e0ddd0; }

/* Stage 4 main table - mirror all #s1-main-table styles via duplicate selectors */
#s4-main-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 11px; table-layout: fixed; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }
#s4-main-table thead { position: sticky; top: 0; z-index: 50; background: #fbfaf5; box-shadow: 0 2px 4px rgba(0,0,0,0.06); }
#s4-main-table thead th { background: #fbfaf5 !important; border-bottom: 1px solid #e0dcc8; padding: 7px 3px; text-align: center; font-weight: 600; font-size: 10px; color: #666; letter-spacing: 0.2px; cursor: pointer; user-select: none; line-height: 1.25; vertical-align: middle; }
#s4-main-table thead th:hover { background: #f0ebd9 !important; }
#s4-main-table thead .group-header-row th { background: #f3efe2 !important; font-size: 9px; text-transform: uppercase; font-weight: 700; letter-spacing: 0.4px; padding: 5px 3px; cursor: default; white-space: normal; line-height: 1.25; }
#s4-main-table thead .group-header-row th:hover { background: #f3efe2 !important; }
#s4-main-table thead tr.group-header-row th { position: sticky; top: 0; }
#s4-main-table thead tr.col-header-row  th { position: sticky; top: 28px; border-top: 1px solid #e0dcc8; }
#s4-main-table thead .gh-inputs { color: #555; }
#s4-main-table thead .gh-rating, #s4-main-table thead .gh-persist { color: #991b1b; }
#s4-main-table thead .gh-g1 { color: #991b1b; }
#s4-main-table thead .gh-g2 { color: #7f1d1d; }
#s4-main-table thead .gh-g3 { color: #6a5a8a; }
#s4-main-table .hd { display: inline-flex; align-items: center; justify-content: center; gap: 3px; width: 100%; }
#s4-main-table .hd .lbl { white-space: normal; word-break: break-word; }
#s4-main-table .hd .sort-arrow { font-size: 9px; color: #991b1b; flex: 0 0 auto; line-height: 1; }
#s4-main-table .hd .sort-placeholder { width: 9px; flex: 0 0 auto; }
#s4-main-table td { padding: 5px 4px; border-bottom: 1px solid #efece0; text-align: center; vertical-align: middle; height: 38px; box-sizing: border-box; font-variant-numeric: tabular-nums; }
#s4-main-table tr:hover { background: rgba(153,27,27,0.05); }

/* Group borders - deep red palette */
#s4-main-table td.grp-start-g1, #s4-main-table th.grp-start-g1 { border-left: 2px solid rgba(153,27,27,0.40); }
#s4-main-table td.grp-start-g2, #s4-main-table th.grp-start-g2 { border-left: 2px solid rgba(127,29,29,0.40); }
#s4-main-table td.grp-start-g3, #s4-main-table th.grp-start-g3 { border-left: 2px solid rgba(106,90,138,0.35); }
#s4-main-table td.grp-start-rating, #s4-main-table th.grp-start-rating { border-left: 2px solid rgba(153,27,27,0.35); }
#s4-main-table td.grp-start-persist, #s4-main-table th.grp-start-persist { border-left: 2px solid rgba(153,27,27,0.35); }
#s4-main-table td.grp-end-g1, #s4-main-table th.grp-end-g1 { border-right: 2px solid rgba(153,27,27,0.40); }
#s4-main-table td.grp-end-g2, #s4-main-table th.grp-end-g2 { border-right: 2px solid rgba(127,29,29,0.40); }
#s4-main-table td.grp-end-g3, #s4-main-table th.grp-end-g3 { border-right: 2px solid rgba(106,90,138,0.35); }

/* Test cells - bearish: pass = deep-red-tinted */
#s4-main-table td.test-pass-bear { background: rgba(127,29,29,0.10); color: #7f1d1d; font-weight: 700; }
#s4-main-table td.test-fail { color: #999; }
#s4-main-table td.test-val  { font-size: 10px; }

#s4-main-table td.name-cell { text-align: left; padding: 4px 4px 4px 8px; line-height: 1.15; }
#s4-main-table td.name-cell .co { font-weight: 700; font-size: 11px; color: #2a2a2a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#s4-main-table td.name-cell .tk { font-size: 9px; color: #999; font-weight: 500; margin-top: 1px; }
#s4-main-table td.name-cell .live-dot { color: #2e7d32; font-weight: 700; margin-right: 4px; display: inline-block; vertical-align: middle; line-height: 1; font-size: 10px; }
#s4-main-table td.taxon { text-align: left; font-size: 9px; line-height: 1.2; padding: 4px; }
#s4-main-table td.taxon .ind { color: #666; font-weight: 500; }
#s4-main-table td.taxon .sec { color: #999; }
#s4-main-table col.c-name { width: 130px; }
#s4-main-table col.c-taxon { width: 170px; }
#s4-main-table col.c-price { width: 56px; }
#s4-main-table col.c-52wh { width: 54px; }
#s4-main-table col.c-52wl { width: 54px; }
#s4-main-table col.c-ma150 { width: 54px; }
#s4-main-table col.c-ma200 { width: 54px; }
#s4-main-table col.c-rating { width: 100px; }
#s4-main-table col.c-score { width: 84px; }
#s4-main-table col.c-test { width: 48px; }
#s4-main-table col.c-persist { width: 110px; }

/* Pills - deep red ramp. Probable ramps 3-7 tests passed. */
#s4-main-table .pill { display: inline-block; padding: 3px 9px; border-radius: 11px; font-weight: 700; font-size: 10px; color: white; letter-spacing: 0.3px; white-space: nowrap; }
#s4-main-table .pill-prob-3 { background: #991b1b; color: #fff; }
#s4-main-table .pill-prob-4 { background: #8b1414; color: #fff; }
#s4-main-table .pill-prob-5 { background: #7f1d1d; color: #fff; }
#s4-main-table .pill-prob-6 { background: #6e0f0f; color: #fff; }
#s4-main-table .pill-prob-7 { background: #5a0808; color: #fff; }
#s4-main-table .pill-pla    { background: #b45309; color: #fff; }
#s4-main-table .pill-pos    { background: #d97706; color: #fff; font-weight: 600; }
#s4-main-table .pill-none   { background: #e0ddd0; color: #8a8676; font-weight: 600; }

/* Score pips - deep red */
#s4-main-table .score-pip-row { display: inline-flex; gap: 2px; align-items: center; }
#s4-main-table .pip.pip-bear { width: 6px; height: 6px; border-radius: 50%; background: #ddd; display: inline-block; }
#s4-main-table .pip.pip-bear.on { background: #7f1d1d; }
#s4-main-table .score-num { font-weight: 700; color: #7f1d1d; margin-left: 5px; font-size: 11px; font-variant-numeric: tabular-nums; }

/* Persistence cells - deep red */
#s4-main-table .persist-row { display: inline-flex; gap: 1px; align-items: center; }
#s4-main-table .persist-cell { width: 7px; height: 11px; background: #ece8d8; border-radius: 1px; }
#s4-main-table .persist-cell.r-prob { background: #5a0808; width: 8px; height: 13px; box-shadow: inset 0 0 0 1px #3a0202; }
#s4-main-table .persist-cell.r-pla  { background: #991b1b; }
#s4-main-table .persist-cell.r-pos  { background: #b45309; }
#s4-main-table .persist-cell.r-none { background: #ece8d8; }

#s4-main-table tr.tint-row td.name-cell, #s4-main-table tr.tint-row td.taxon { background: var(--tint-bg) !important; }
#s4-main-table tr.portfolio-band td:last-child { border-right: 4px solid var(--portfolio-color); }
#s4-main-table tr.portfolio-tint { background: var(--portfolio-bg); }
#s4-main-table tr.portfolio-tint:hover { background: var(--portfolio-bg-hover); }
/* MD-V2-STAGE4-MARKER-CSS-END */
'''

# Inject Stage 4 CSS at end of css raw-string.
# Anchor uses Stage 3 CSS-end marker as the join point (post-Stage-3 file shape).
ANCHOR_CSS_END = b'/* MD-V2-STAGE3-MARKER-CSS-END */\n"""' + CRLF

ANCHOR_RT_FN = b'function renderTab(id){'


def main():
    check_fuse_environment()
    print(f"[stage4-patch] working dir: {SCRIPT_DIR}")
    if not DASH_PY.exists(): fail(f"build_dashboard.py not found")
    if not MODULE_JS.exists(): fail(f"_stage4_tab_module.js not found")
    src = DASH_PY.read_bytes()
    mod = MODULE_JS.read_bytes()
    print(f"[stage4-patch] build_dashboard.py: {len(src)} bytes")
    print(f"[stage4-patch] _stage4_tab_module.js: {len(mod)} bytes")

    if MARKER_BYTES in src:
        if "--force" in sys.argv:
            baks = sorted(SCRIPT_DIR.glob("build_dashboard.py.bak-pre-md-v2-stage4-*"), reverse=True)
            if not baks:
                fail("No Stage 4 backup found to revert from.")
            print(f"[stage4-patch] --force: reverting from {baks[0].name}")
            shutil.copy2(baks[0], DASH_PY)
            src = DASH_PY.read_bytes()
            if MARKER_BYTES in src: fail("Backup still has marker.")
        else:
            print(f"[stage4-patch] marker present - already applied. Use --force to re-apply.")
            return

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = DASH_PY.with_suffix(f".py.bak-pre-md-v2-stage4-{ts}")
    shutil.copy2(DASH_PY, bak)
    print(f"[stage4-patch] backup: {bak.name}")

    # Check anchors - Stage 3 must have applied first
    for label, a in [("TABS", ANCHOR_TABS), ("IMPL", ANCHOR_IMPL), ("RENDERTAB", ANCHOR_RENDERTAB)]:
        if src.count(a) != 1:
            fail(f"Anchor {label} count = {src.count(a)} (expected 1). Did Stage 3 patcher run first?")
    if src.count(ANCHOR_CSS_END) != 1:
        fail("CSS end anchor not unique")
    if src.count(ANCHOR_RT_FN) != 1:
        fail("renderTab fn anchor not unique")

    src = src.replace(ANCHOR_TABS, REPLACE_TABS, 1)
    src = src.replace(ANCHOR_IMPL, REPLACE_IMPL, 1)
    src = src.replace(ANCHOR_RENDERTAB, REPLACE_RENDERTAB, 1)
    css_prefix = b'/* MD-V2-STAGE3-MARKER-CSS-END */\n'
    css_suffix = b'"""' + CRLF
    css_repl = css_prefix + S4_CSS + css_suffix
    src = src.replace(ANCHOR_CSS_END, css_repl, 1)
    module_block = (
        b'\n/* MD-V2-STAGE4-MARKER-MODULE-START */\n'
        + mod
        + b'\n/* MD-V2-STAGE4-MARKER-MODULE-END */\n\n'
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
    print(f"[stage4-patch] OK. New size: {DASH_PY.stat().st_size} bytes")
    print(f"[stage4-patch] marker count: {DASH_PY.read_bytes().count(MARKER_BYTES)}")
    print(f"[stage4-patch] DONE. Next: python scripts\\build_dashboard.py")


if __name__ == "__main__":
    main()
