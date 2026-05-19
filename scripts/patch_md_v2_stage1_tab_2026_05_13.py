r"""
Patcher: STAGE 1 tab — MD V2 (13-May-26)

Injects the Stage 1 tab into build_dashboard.py per locked universal pattern
(handoff-2026-05-13-stage1-mockup-signed-off.md).

Idempotent. Pre-write backup. py_compile verification. FUSE truncation guard.
Operates on BYTES to preserve Windows CRLF and Unicode em-dashes.

Six injection sites:
  1. TABS list — insert Stage 1 between SUMMARY and Data/reference tabs
  2. IMPLEMENTED_TABS — add "stage_1"
  3. renderTab dispatch — add stage_1 branch
  4. JS module — inject contents of _stage1_tab_module.js before renderTab fn
  5. CSS — inject Stage 1-specific styles
  6. (No pre-compute hook needed — module reads MASTER_DATA directly)

MUST run Windows-side. FUSE truncation guard refuses Cowork-side execution.

Run:
  cd C:\Users\richb\Documents\COWORK\master-dashboard
  python scripts\patch_md_v2_stage1_tab_2026_05_13.py
"""
import os
import shutil
import py_compile
import sys
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent.resolve()
DASH_PY = SCRIPT_DIR / "build_dashboard.py"
MODULE_JS = SCRIPT_DIR / "_stage1_tab_module.js"
MARKER_BYTES = b"MD-V2-STAGE1-MARKER"

EM = "—".encode("utf-8")
CRLF = b"\r\n"


def fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


def check_fuse_environment():
    """Refuse to run from Cowork/FUSE mount — must be Windows-side."""
    here = str(SCRIPT_DIR).replace("\\", "/")
    if "/sessions/" in here or here.startswith("/tmp"):
        fail("Refusing to run from Cowork/FUSE mount. Run Windows-side from C:\\Users\\richb\\Documents\\COWORK\\master-dashboard")


def read_bytes(p):
    if not p.exists():
        fail(f"File not found: {p}")
    return p.read_bytes()


def assert_unique(content, anchor, label):
    n = content.count(anchor)
    if n == 0:
        fail(f"Anchor not found ({label}): {anchor[:80]!r}")
    if n > 1:
        fail(f"Anchor not unique ({label}): {n} occurrences")


def assert_present(content, anchor, label):
    if content.count(anchor) == 0:
        fail(f"Anchor not found ({label}): {anchor[:80]!r}")


# ============================================================================
# Anchor 1: TABS list — insert Stage 1 between SUMMARY tab and "Data / reference tabs" comment
# ============================================================================
ANCHOR_TABS = (
    b'    # SUMMARY-TAB-MARKER ' + EM + b' synoptic view, default landing tab (D-MD-UI-38)' + CRLF
    + b'    {"id": "summary",   "label": "SUMMARY",          "accent": "#4a5568"},' + CRLF
    + b'    # Data / reference tabs' + CRLF
)

REPLACE_TABS = (
    b'    # SUMMARY-TAB-MARKER ' + EM + b' synoptic view, default landing tab (D-MD-UI-38)' + CRLF
    + b'    {"id": "summary",   "label": "SUMMARY",          "accent": "#4a5568"},' + CRLF
    + b'    # MD-V2-STAGE1-MARKER ' + EM + b' Stage 1 (Consolidating/Basing) tab' + CRLF
    + b'    {"id": "stage_1",   "label": "Stage 1",           "accent": "#1b5e20"},' + CRLF
    + b'    # Data / reference tabs' + CRLF
)


# ============================================================================
# Anchor 2: IMPLEMENTED_TABS — add stage_1
# ============================================================================
ANCHOR_IMPL = (
    b'IMPLEMENTED_TABS = [' + CRLF
    + b'    "summary",' + CRLF
    + b'    "mm99", "bp", "pb", "utr", "vcp", "tech", "combos", "changes", "positions",' + CRLF
    + b'    "ssem", "val",' + CRLF
    + b']'
)

REPLACE_IMPL = (
    b'IMPLEMENTED_TABS = [' + CRLF
    + b'    "summary",' + CRLF
    + b'    "stage_1",  # MD-V2-STAGE1-MARKER' + CRLF
    + b'    "mm99", "bp", "pb", "utr", "vcp", "tech", "combos", "changes", "positions",' + CRLF
    + b'    "ssem", "val",' + CRLF
    + b']'
)


# ============================================================================
# Anchor 3: renderTab dispatch — add stage_1 branch as 2nd condition
# ============================================================================
ANCHOR_RENDERTAB = (
    b'function renderTab(id){' + CRLF
    + b'  try{' + CRLF
    + b'  if(id==="summary")renderSummary();' + CRLF
    + b'  else if(id==="mm99")renderMM99();'
)

REPLACE_RENDERTAB = (
    b'function renderTab(id){' + CRLF
    + b'  try{' + CRLF
    + b'  if(id==="summary")renderSummary();' + CRLF
    + b'  else if(id==="stage_1")renderStage1();  /* MD-V2-STAGE1-MARKER */' + CRLF
    + b'  else if(id==="mm99")renderMM99();'
)


# ============================================================================
# Anchor 4: CSS injection — Stage 1-specific styles before </style>
# ============================================================================
S1_CSS = b'''
/* MD-V2-STAGE1-MARKER-CSS-START */
.s1-intro { background: var(--bg-card, #fbfaf5); border: 1px solid var(--border, #e0dcc8); border-radius: 4px; padding: 12px 16px; margin-bottom: 14px; font-size: 12px; color: var(--text-muted, #666); max-width: 920px; }
.s1-intro b { color: #2a2a2a; }
.s1-controls { display: flex; gap: 14px; flex-wrap: wrap; align-items: center; margin-bottom: 12px; padding: 9px 14px; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }
.s1-controls .ctrl-grp { display: flex; align-items: center; gap: 5px; padding-right: 14px; border-right: 1px solid #e0dcc8; }
.s1-controls .ctrl-grp:last-child { border-right: none; padding-right: 0; }
.s1-controls .ctrl-label { font-size: 9px; text-transform: uppercase; letter-spacing: 0.5px; color: #999; font-weight: 600; margin-right: 4px; }
.s1-controls .toggle-btn { background: #f3efe2; border: 1px solid #e0dcc8; color: #2a2a2a; padding: 3px 9px; font-size: 11px; font-family: inherit; border-radius: 3px; cursor: pointer; transition: all 0.12s; }
.s1-controls .toggle-btn:hover:not(.disabled) { background: #ebe5d2; }
.s1-controls .toggle-btn.active { background: #1b5e20; color: #fff; border-color: #1b5e20; }
.s1-controls .toggle-btn.disabled { background: #f0ebd9; color: #bbb; cursor: not-allowed; border-style: dashed; }

.s1-rating-tiles { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-bottom: 12px; }
.s1-rating-tiles .rating-tile { background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; padding: 11px 14px; cursor: pointer; transition: all 0.12s; }
.s1-rating-tiles .rating-tile:hover { transform: translateY(-1px); box-shadow: 0 2px 6px rgba(0,0,0,0.08); }
.s1-rating-tiles .rating-tile.active { background: #1b5e20; color: #fff; border-color: #1b5e20; }
.s1-rating-tiles .rating-tile.active .rt-label, .s1-rating-tiles .rating-tile.active .rt-count { color: #fff; }
.s1-rating-tiles .rating-tile.active .rt-sub { color: rgba(255,255,255,0.75); }
.s1-rating-tiles .rt-label { font-size: 11px; font-weight: 600; color: #666; letter-spacing: 0.2px; }
.s1-rating-tiles .rt-count { font-size: 22px; font-weight: 700; color: #2a2a2a; margin-top: 3px; line-height: 1; font-variant-numeric: tabular-nums; }
.s1-rating-tiles .rt-sub { font-size: 10px; color: #999; margin-top: 3px; }
.s1-rating-tiles .rt-strip { height: 3px; border-radius: 2px; margin-top: 7px; }
.s1-rating-tiles .rt-strip-pl  { background: #14501c; }
.s1-rating-tiles .rt-strip-pe  { background: #4a9658; }
.s1-rating-tiles .rt-strip-pla { background: #6b8a98; }
.s1-rating-tiles .rt-strip-pos { background: #c4c0b0; }
.s1-rating-tiles .rt-strip-none { background: #e0ddd0; }
.s1-rating-tiles .rating-tile.tint-pl   { background: rgba(20, 87, 24, 0.08); }
.s1-rating-tiles .rating-tile.tint-pe   { background: rgba(74, 150, 88, 0.08); }
.s1-rating-tiles .rating-tile.tint-pla  { background: rgba(107, 138, 152, 0.08); }
.s1-rating-tiles .rating-tile.tint-pos  { background: rgba(196, 192, 176, 0.18); }
.s1-rating-tiles .rating-tile.tint-none { background: rgba(224, 221, 208, 0.30); }

#tab-stage_1 .group-captions { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 10px; margin-bottom: 10px; }
#tab-stage_1 .gcap { background: #fbfaf5; border-left: 3px solid; padding: 9px 12px; font-size: 11px; color: #2a2a2a; line-height: 1.45; border-radius: 0 3px 3px 0; }
#tab-stage_1 .gcap b { display: block; font-size: 11px; font-weight: 700; margin-bottom: 3px; letter-spacing: 0.2px; }
#tab-stage_1 .gcap-g1 { border-color: #b08a4e; } #tab-stage_1 .gcap-g1 b { color: #b08a4e; }
#tab-stage_1 .gcap-g2 { border-color: #5a8a6a; } #tab-stage_1 .gcap-g2 b { color: #5a8a6a; }
#tab-stage_1 .gcap-g3 { border-color: #4a6a8a; } #tab-stage_1 .gcap-g3 b { color: #4a6a8a; }
#tab-stage_1 .gcap-g4 { border-color: #8a5a6a; } #tab-stage_1 .gcap-g4 b { color: #8a5a6a; }

#s1-main-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 11px; table-layout: fixed; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }
#s1-main-table thead { position: sticky; top: 0; z-index: 50; background: #fbfaf5; box-shadow: 0 2px 4px rgba(0,0,0,0.06); }
#s1-main-table thead th { background: #fbfaf5 !important; border-bottom: 1px solid #e0dcc8; padding: 7px 3px; text-align: center; font-weight: 600; font-size: 10px; color: #666; letter-spacing: 0.2px; cursor: pointer; user-select: none; line-height: 1.25; vertical-align: middle; }
#s1-main-table thead th:hover { background: #f0ebd9 !important; }
#s1-main-table thead .group-header-row th { background: #f3efe2 !important; font-size: 9px; text-transform: uppercase; font-weight: 700; letter-spacing: 0.4px; padding: 5px 3px; cursor: default; white-space: normal; line-height: 1.25; }
#s1-main-table thead .group-header-row th:hover { background: #f3efe2 !important; }
#s1-main-table thead tr.group-header-row th { position: sticky; top: 0; }
#s1-main-table thead tr.col-header-row  th { position: sticky; top: 28px; border-top: 1px solid #e0dcc8; }
#s1-main-table thead .gh-inputs { color: #555; }
#s1-main-table thead .gh-rating, #s1-main-table thead .gh-persist { color: #1b5e20; }
#s1-main-table thead .gh-g1 { color: #b08a4e; }
#s1-main-table thead .gh-g2 { color: #5a8a6a; }
#s1-main-table thead .gh-g3 { color: #4a6a8a; }
#s1-main-table thead .gh-g4 { color: #8a5a6a; }
#s1-main-table .hd { display: inline-flex; align-items: center; justify-content: center; gap: 3px; width: 100%; }
#s1-main-table .hd .lbl { white-space: normal; word-break: break-word; }
#s1-main-table .hd .sort-arrow { font-size: 9px; color: #1b5e20; flex: 0 0 auto; line-height: 1; }
#s1-main-table .hd .sort-placeholder { width: 9px; flex: 0 0 auto; }

#s1-main-table td { padding: 5px 4px; border-bottom: 1px solid #efece0; text-align: center; vertical-align: middle; height: 38px; box-sizing: border-box; font-variant-numeric: tabular-nums; }
#s1-main-table tr:hover { background: rgba(27,94,32,0.04); }

#s1-main-table td.grp-start-g1, #s1-main-table th.grp-start-g1 { border-left: 2px solid rgba(176,138,78,0.35); }
#s1-main-table td.grp-start-g2, #s1-main-table th.grp-start-g2 { border-left: 2px solid rgba(90,138,106,0.35); }
#s1-main-table td.grp-start-g3, #s1-main-table th.grp-start-g3 { border-left: 2px solid rgba(74,106,138,0.35); }
#s1-main-table td.grp-start-g4, #s1-main-table th.grp-start-g4 { border-left: 2px solid rgba(138,90,106,0.35); }
#s1-main-table td.grp-start-rating, #s1-main-table th.grp-start-rating { border-left: 2px solid rgba(27,94,32,0.35); }
#s1-main-table td.grp-start-persist, #s1-main-table th.grp-start-persist { border-left: 2px solid rgba(27,94,32,0.35); }
#s1-main-table td.grp-end-g1, #s1-main-table th.grp-end-g1 { border-right: 2px solid rgba(176,138,78,0.35); }
#s1-main-table td.grp-end-g2, #s1-main-table th.grp-end-g2 { border-right: 2px solid rgba(90,138,106,0.35); }
#s1-main-table td.grp-end-g3, #s1-main-table th.grp-end-g3 { border-right: 2px solid rgba(74,106,138,0.35); }
#s1-main-table td.grp-end-g4, #s1-main-table th.grp-end-g4 { border-right: 2px solid rgba(138,90,106,0.35); }
#s1-main-table td.test-pass { background: rgba(27,94,32,0.08); color: #1b5e20; font-weight: 700; }
#s1-main-table td.test-fail { color: #999; }
#s1-main-table td.test-val  { font-size: 10px; }
#s1-main-table td.name-cell { text-align: left; padding: 4px 4px 4px 8px; line-height: 1.15; }
#s1-main-table td.name-cell .co { font-weight: 700; font-size: 11px; color: #2a2a2a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#s1-main-table td.name-cell .tk { font-size: 9px; color: #999; font-weight: 500; margin-top: 1px; }
#s1-main-table td.name-cell .live-dot { color: #1b5e20; font-weight: 700; margin-right: 4px; display: inline-block; vertical-align: middle; line-height: 1; font-size: 10px; }
#s1-main-table td.taxon { text-align: left; font-size: 9px; line-height: 1.2; padding: 4px; }
#s1-main-table td.taxon .ind { color: #666; font-weight: 500; }
#s1-main-table td.taxon .sec { color: #999; }

#s1-main-table col.c-name { width: 130px; }
#s1-main-table col.c-taxon { width: 170px; }
#s1-main-table col.c-price { width: 56px; }
#s1-main-table col.c-52wh { width: 54px; }
#s1-main-table col.c-52wl { width: 54px; }
#s1-main-table col.c-ma150 { width: 54px; }
#s1-main-table col.c-ma200 { width: 54px; }
#s1-main-table col.c-rating { width: 100px; }
#s1-main-table col.c-score { width: 86px; }
#s1-main-table col.c-test { width: 50px; }
#s1-main-table col.c-persist { width: 110px; }

#s1-main-table .pill { display: inline-block; padding: 3px 9px; border-radius: 11px; font-weight: 700; font-size: 10px; color: white; letter-spacing: 0.3px; white-space: nowrap; }
#s1-main-table .pill-pl-5 { background: #2e7d32; color: #fff; }
#s1-main-table .pill-pl-6 { background: #1e6a25; color: #fff; }
#s1-main-table .pill-pl-7 { background: #145718; color: #fff; }
#s1-main-table .pill-pl-8 { background: #08400d; color: #fff; }
#s1-main-table .pill-pe   { background: #4a9658; color: #fff; }
#s1-main-table .pill-pla  { background: #6b8a98; color: #fff; }
#s1-main-table .pill-pos  { background: #c4c0b0; color: #5a5a4a; font-weight: 600; }
#s1-main-table .pill-none { background: #e0ddd0; color: #8a8676; font-weight: 600; }

#s1-main-table .score-pip-row { display: inline-flex; gap: 2px; align-items: center; }
#s1-main-table .pip { width: 7px; height: 7px; border-radius: 50%; background: #ddd; display: inline-block; }
#s1-main-table .pip.on { background: #1b5e20; }
#s1-main-table .score-num { font-weight: 700; color: #1b5e20; margin-left: 5px; font-size: 11px; font-variant-numeric: tabular-nums; }

#s1-main-table .persist-row { display: inline-flex; gap: 1px; align-items: center; }
#s1-main-table .persist-cell { width: 7px; height: 11px; background: #ece8d8; border-radius: 1px; }
#s1-main-table .persist-cell.r-pos  { background: #c4c0b0; }
#s1-main-table .persist-cell.r-pla  { background: #6b8a98; }
#s1-main-table .persist-cell.r-pe   { background: #4a9658; }
#s1-main-table .persist-cell.r-pl   { background: #145718; width: 8px; height: 13px; box-shadow: inset 0 0 0 1px #08400d; }
#s1-main-table .persist-cell.r-none { background: #ece8d8; }

#s1-main-table tr.tint-row td.name-cell, #s1-main-table tr.tint-row td.taxon { background: var(--tint-bg) !important; }
#s1-main-table tr.portfolio-band td:last-child { border-right: 4px solid var(--portfolio-color); }
#s1-main-table tr.portfolio-tint { background: var(--portfolio-bg); }
#s1-main-table tr.portfolio-tint:hover { background: var(--portfolio-bg-hover); }
/* MD-V2-STAGE1-MARKER-CSS-END */
'''

ANCHOR_CSS = (
    b'.filter-pill{transition:opacity 0.2s}.filter-pill:hover{opacity:0.8}' + CRLF
    + b'"""' + CRLF
)
REPLACE_CSS_PREFIX = (
    b'.filter-pill{transition:opacity 0.2s}.filter-pill:hover{opacity:0.8}' + CRLF
)
REPLACE_CSS_SUFFIX = (
    b'"""' + CRLF
)


# ============================================================================
# Anchor 5: JS module — inject before "function renderTab"
# ============================================================================
ANCHOR_RENDERTAB_FN = b'function renderTab(id){'


def main():
    check_fuse_environment()

    print(f"[stage1-patch] working dir: {SCRIPT_DIR}")
    if not DASH_PY.exists():
        fail(f"build_dashboard.py not found at {DASH_PY}")
    if not MODULE_JS.exists():
        fail(f"_stage1_tab_module.js not found at {MODULE_JS}")

    src = DASH_PY.read_bytes()
    module_js = MODULE_JS.read_bytes()
    orig_size = len(src)
    print(f"[stage1-patch] build_dashboard.py: {orig_size} bytes")
    print(f"[stage1-patch] _stage1_tab_module.js: {len(module_js)} bytes")

    # Idempotency check — if already applied, refuse unless --force given
    if MARKER_BYTES in src:
        if "--force" in sys.argv:
            print(f"[stage1-patch] marker present but --force flag given. Reverting to most recent backup and re-applying.")
            # Find most recent backup
            baks = sorted(SCRIPT_DIR.glob("build_dashboard.py.bak-pre-md-v2-stage1-*"), reverse=True)
            if not baks:
                fail("No pre-patch backup found to revert to. Cannot --force.")
            print(f"[stage1-patch] reverting from {baks[0].name}")
            shutil.copy2(baks[0], DASH_PY)
            src = DASH_PY.read_bytes()
            if MARKER_BYTES in src:
                fail("Backup also contains marker — cannot find pre-patch state.")
        else:
            print(f"[stage1-patch] marker {MARKER_BYTES!r} already present — patch already applied. No-op.")
            print(f"[stage1-patch] Use --force to revert from backup and re-apply with the latest module.")
            return

    # Pre-write backup
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = DASH_PY.with_suffix(f".py.bak-pre-md-v2-stage1-{ts}")
    shutil.copy2(DASH_PY, bak)
    print(f"[stage1-patch] backup: {bak.name}")

    # Verify all anchors are unique before any mutation
    assert_unique(src, ANCHOR_TABS,        "TABS list")
    assert_unique(src, ANCHOR_IMPL,        "IMPLEMENTED_TABS")
    assert_unique(src, ANCHOR_RENDERTAB,   "renderTab dispatch")
    assert_present(src, ANCHOR_CSS,        "</style>")
    assert_present(src, ANCHOR_RENDERTAB_FN, "function renderTab")

    # Apply mutations in order
    src = src.replace(ANCHOR_TABS, REPLACE_TABS, 1)
    src = src.replace(ANCHOR_IMPL, REPLACE_IMPL, 1)
    src = src.replace(ANCHOR_RENDERTAB, REPLACE_RENDERTAB, 1)
    # CSS — inject Stage 1 CSS at the end of the dashboard's `css = r"""...."""` block
    # Anchor is the last line of the css raw string + its closing triple-quote.
    if src.count(ANCHOR_CSS) != 1:
        fail(f"CSS anchor not unique: {src.count(ANCHOR_CSS)} occurrences")
    css_repl = REPLACE_CSS_PREFIX + S1_CSS + REPLACE_CSS_SUFFIX
    src = src.replace(ANCHOR_CSS, css_repl, 1)
    # Module JS goes before "function renderTab"
    module_block = (
        b'\n/* MD-V2-STAGE1-MARKER-MODULE-START */\n'
        + module_js
        + b'\n/* MD-V2-STAGE1-MARKER-MODULE-END */\n\n'
    )
    rt_idx = src.find(ANCHOR_RENDERTAB_FN)
    if rt_idx == -1:
        fail("Could not locate function renderTab")
    src = src[:rt_idx] + module_block + src[rt_idx:]

    # Atomic write
    tmp = DASH_PY.with_suffix(f".py.tmp-{ts}")
    tmp.write_bytes(src)

    # py_compile verify before replacing
    try:
        py_compile.compile(str(tmp), doraise=True)
    except py_compile.PyCompileError as e:
        tmp.unlink(missing_ok=True)
        fail(f"py_compile failed on patched output: {e}")

    os.replace(str(tmp), str(DASH_PY))
    final_size = DASH_PY.stat().st_size
    growth = final_size - orig_size
    print(f"[stage1-patch] OK. New size: {final_size} bytes (+{growth} delta)")

    # Tail check
    tail = DASH_PY.read_bytes()[-200:]
    if b'if __name__' not in tail and b'build_html' not in tail:
        print(f"[stage1-patch] WARN: tail looks unusual: {tail!r}")
    else:
        print(f"[stage1-patch] tail OK")

    # Marker count
    final = DASH_PY.read_bytes()
    n_markers = final.count(MARKER_BYTES)
    print(f"[stage1-patch] marker count in final: {n_markers} (expect >=5)")

    print("[stage1-patch] DONE. Next: python scripts\\build_dashboard.py")


if __name__ == "__main__":
    main()
