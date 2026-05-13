r"""
Patcher: PRE-INDICATORS tab — MD V2 (13-May-26, Session 24)

Chains after Stage 4 + Chrome Parity + Chrome Parity Followup + SUMMARY removal +
Bootstrap default-tab fix. Anchors land on the post-bootstrap-fix build_dashboard.py
shape.

Pre-indicators uses Option B layout (Richard's choice 13-May-26):
  - 3 pattern tiles (Pullback / Basing / Collapsing) - click filters table
  - 3 tick columns + 0/3 score column
  - Teal accent palette

MUST run Windows-side. Idempotent. Supports --force.
"""
import os, shutil, py_compile, sys
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent.resolve()
DASH_PY = SCRIPT_DIR / "build_dashboard.py"
MODULE_JS = SCRIPT_DIR / "_pre_indicators_tab_module.js"
MARKER_BYTES = b"MD-V2-PRE-INDICATORS-MARKER"

CRLF = b"\r\n"


def fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


def check_fuse_environment():
    here = str(SCRIPT_DIR).replace("\\", "/")
    if "/sessions/" in here or here.startswith("/tmp"):
        fail("Refusing to run from Cowork/FUSE mount.")


# ----------------------------------------------------------------------------
# Anchor 1: TABS list - append pre_indicators after stage_4 entry
# (Comment uses plain ASCII " - " not em-dash, per D-MD-V2-24 / D-MD-V2-28.)
# ----------------------------------------------------------------------------
ANCHOR_TABS = (
    b'    # MD-V2-STAGE4-MARKER \xe2\x80\x94 Stage 4 (Decline / Capitulation) tab' + CRLF
    + b'    {"id": "stage_4",   "label": "Stage 4",           "accent": "#991b1b"},' + CRLF
)
REPLACE_TABS = (
    b'    # MD-V2-STAGE4-MARKER \xe2\x80\x94 Stage 4 (Decline / Capitulation) tab' + CRLF
    + b'    {"id": "stage_4",   "label": "Stage 4",           "accent": "#991b1b"},' + CRLF
    + b'    # MD-V2-PRE-INDICATORS-MARKER - Pre-indicators (3 leading binary patterns)' + CRLF
    + b'    {"id": "pre_indicators", "label": "Pre-indicators", "accent": "#0F6E56"},' + CRLF
)

# ----------------------------------------------------------------------------
# Anchor 2: IMPLEMENTED_TABS - post-SUMMARY-removal shape (no "summary" entry).
# ----------------------------------------------------------------------------
ANCHOR_IMPL = (
    b'IMPLEMENTED_TABS = [' + CRLF
    + b'    "stage_1",  # MD-V2-STAGE1-MARKER' + CRLF
    + b'    "stage_2",  # MD-V2-STAGE2-MARKER' + CRLF
    + b'    "stage_3",  # MD-V2-STAGE3-MARKER' + CRLF
    + b'    "stage_4",  # MD-V2-STAGE4-MARKER' + CRLF
    + b'    "mm99", "bp", "pb", "utr", "vcp", "tech", "combos", "changes", "positions",' + CRLF
    + b'    "ssem", "val",' + CRLF
    + b']'
)
REPLACE_IMPL = (
    b'IMPLEMENTED_TABS = [' + CRLF
    + b'    "stage_1",  # MD-V2-STAGE1-MARKER' + CRLF
    + b'    "stage_2",  # MD-V2-STAGE2-MARKER' + CRLF
    + b'    "stage_3",  # MD-V2-STAGE3-MARKER' + CRLF
    + b'    "stage_4",  # MD-V2-STAGE4-MARKER' + CRLF
    + b'    "pre_indicators",  # MD-V2-PRE-INDICATORS-MARKER' + CRLF
    + b'    "mm99", "bp", "pb", "utr", "vcp", "tech", "combos", "changes", "positions",' + CRLF
    + b'    "ssem", "val",' + CRLF
    + b']'
)

# ----------------------------------------------------------------------------
# Anchor 3: renderTab dispatch - append pre_indicators after stage_4.
# Note: in live HTML the SUMMARY removal patcher leaves the renderSummary line
# as a dead-but-reachable entry. We anchor on the stage_4 line which is stable.
# ----------------------------------------------------------------------------
ANCHOR_RENDERTAB_LF = (
    b'  else if(id==="stage_4")renderStage4();  /* MD-V2-STAGE4-MARKER */\n'
)
REPLACE_RENDERTAB_LF = (
    b'  else if(id==="stage_4")renderStage4();  /* MD-V2-STAGE4-MARKER */\n'
    b'  else if(id==="pre_indicators")renderPreIndicators();  /* MD-V2-PRE-INDICATORS-MARKER */\n'
)
ANCHOR_RENDERTAB_CRLF = ANCHOR_RENDERTAB_LF.replace(b'\n', b'\r\n')
REPLACE_RENDERTAB_CRLF = REPLACE_RENDERTAB_LF.replace(b'\n', b'\r\n')

# ----------------------------------------------------------------------------
# Anchor 4: CSS injection. Anchor on the FOLLOWUP CSS-END marker (final marker
# laid down by chrome-parity-followup patcher, before SUMMARY removal patcher
# only adds an idempotency comment after it).
# Bootstrap-default-tab-fix patcher also plants a marker after FOLLOWUP, so we
# anchor on that newer marker if present; else fall back to FOLLOWUP.
# ----------------------------------------------------------------------------
PI_CSS = b'''
/* MD-V2-PRE-INDICATORS-MARKER-CSS-START */
/* Pre-indicators (3 leading patterns) - teal palette across all 3 patterns. */
#tab-pre_indicators .group-captions .gcap-g1 { border-color: #0F6E56; }
#tab-pre_indicators .group-captions .gcap-g1 b { color: #0F6E56; }
#tab-pre_indicators .group-captions .gcap-g2 { border-color: #854F0B; }
#tab-pre_indicators .group-captions .gcap-g2 b { color: #854F0B; }
#tab-pre_indicators .group-captions .gcap-g3 { border-color: #A32D2D; }
#tab-pre_indicators .group-captions .gcap-g3 b { color: #A32D2D; }

/* Pattern tile tints - Option B: one tile per pattern */
#tab-pre_indicators .s1-rating-tiles .pi-tile-pullback   { background: rgba(15, 110, 86, 0.10); border-color: rgba(15,110,86,0.25); }
#tab-pre_indicators .s1-rating-tiles .pi-tile-basing     { background: rgba(133, 79, 11, 0.10); border-color: rgba(133,79,11,0.25); }
#tab-pre_indicators .s1-rating-tiles .pi-tile-collapsing { background: rgba(163, 45, 45, 0.10); border-color: rgba(163,45,45,0.25); }
#tab-pre_indicators .s1-rating-tiles .pi-tile-pullback.active   { background: rgba(15, 110, 86, 0.22); border: 1.5px solid #0F6E56; }
#tab-pre_indicators .s1-rating-tiles .pi-tile-basing.active     { background: rgba(133, 79, 11, 0.22); border: 1.5px solid #854F0B; }
#tab-pre_indicators .s1-rating-tiles .pi-tile-collapsing.active { background: rgba(163, 45, 45, 0.22); border: 1.5px solid #A32D2D; }
#tab-pre_indicators .s1-rating-tiles .pi-strip-pullback   { background: #0F6E56; }
#tab-pre_indicators .s1-rating-tiles .pi-strip-basing     { background: #854F0B; }
#tab-pre_indicators .s1-rating-tiles .pi-strip-collapsing { background: #A32D2D; }

/* Pre-indicators main table */
#pi-main-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 11px; table-layout: fixed; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }
#pi-main-table thead { position: sticky; top: 0; z-index: 50; background: #fbfaf5; box-shadow: 0 2px 4px rgba(0,0,0,0.06); }
#pi-main-table thead th { background: #fbfaf5 !important; border-bottom: 1px solid #e0dcc8; padding: 7px 3px; text-align: center; font-weight: 600; font-size: 10px; color: #666; letter-spacing: 0.2px; cursor: pointer; user-select: none; line-height: 1.25; vertical-align: middle; }
#pi-main-table thead th:hover { background: #f0ebd9 !important; }
#pi-main-table thead .group-header-row th { background: #f3efe2 !important; font-size: 9px; text-transform: uppercase; font-weight: 700; letter-spacing: 0.4px; padding: 5px 3px; cursor: default; white-space: normal; line-height: 1.25; }
#pi-main-table thead .group-header-row th:hover { background: #f3efe2 !important; }
#pi-main-table thead tr.group-header-row th { position: sticky; top: 0; }
#pi-main-table thead tr.col-header-row  th { position: sticky; top: 28px; border-top: 1px solid #e0dcc8; }
#pi-main-table thead .gh-inputs { color: #555; }
#pi-main-table thead .gh-rating { color: #0F6E56; }
#pi-main-table thead .gh-g1 { color: #0F6E56; }
#pi-main-table thead .gh-g2 { color: #854F0B; }
#pi-main-table thead .gh-g3 { color: #A32D2D; }
#pi-main-table .hd { display: inline-flex; align-items: center; justify-content: center; gap: 3px; width: 100%; }
#pi-main-table .hd .lbl { white-space: normal; word-break: break-word; }
#pi-main-table .hd .sort-arrow { font-size: 9px; color: #0F6E56; flex: 0 0 auto; line-height: 1; }
#pi-main-table .hd .sort-placeholder { width: 9px; flex: 0 0 auto; }
#pi-main-table td { padding: 5px 4px; border-bottom: 1px solid #efece0; text-align: center; vertical-align: middle; height: 38px; box-sizing: border-box; font-variant-numeric: tabular-nums; }
#pi-main-table tr:hover { background: rgba(15,110,86,0.05); }

/* Group borders - teal/amber/red palette per pattern */
#pi-main-table td.grp-start-g1, #pi-main-table th.grp-start-g1 { border-left: 2px solid rgba(15,110,86,0.40); }
#pi-main-table td.grp-end-g1,   #pi-main-table th.grp-end-g1   { border-right: 2px solid rgba(15,110,86,0.40); }
#pi-main-table td.grp-start-g2, #pi-main-table th.grp-start-g2 { border-left: 2px solid rgba(133,79,11,0.40); }
#pi-main-table td.grp-end-g2,   #pi-main-table th.grp-end-g2   { border-right: 2px solid rgba(133,79,11,0.40); }
#pi-main-table td.grp-start-g3, #pi-main-table th.grp-start-g3 { border-left: 2px solid rgba(163,45,45,0.40); }
#pi-main-table td.grp-end-g3,   #pi-main-table th.grp-end-g3   { border-right: 2px solid rgba(163,45,45,0.40); }
#pi-main-table td.grp-start-rating, #pi-main-table th.grp-start-rating { border-left: 2px solid rgba(15,110,86,0.35); }

/* Pattern cells - pass tinted teal */
#pi-main-table td.pi-pass { background: rgba(15,110,86,0.12); color: #0F6E56; font-weight: 700; }
#pi-main-table td.pi-fail { color: #999; }

#pi-main-table td.name-cell { text-align: left; padding: 4px 4px 4px 8px; line-height: 1.15; }
#pi-main-table td.name-cell .co { font-weight: 700; font-size: 11px; color: #2a2a2a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#pi-main-table td.name-cell .tk { font-size: 9px; color: #999; font-weight: 500; margin-top: 1px; }
#pi-main-table td.name-cell .live-dot { color: #2e7d32; font-weight: 700; margin-right: 4px; display: inline-block; vertical-align: middle; line-height: 1; font-size: 10px; }
#pi-main-table td.taxon { text-align: left; font-size: 9px; line-height: 1.2; padding: 4px; }
#pi-main-table td.taxon .ind { color: #666; font-weight: 500; }
#pi-main-table td.taxon .sec { color: #999; }
#pi-main-table col.c-name { width: 130px; }
#pi-main-table col.c-taxon { width: 170px; }
#pi-main-table col.c-price { width: 56px; }
#pi-main-table col.c-52wh { width: 54px; }
#pi-main-table col.c-pullback { width: 64px; }
#pi-main-table col.c-ma150 { width: 54px; }
#pi-main-table col.c-ma200 { width: 54px; }
#pi-main-table col.c-score { width: 90px; }
#pi-main-table col.c-pattern { width: 70px; }

/* Score pip row */
#pi-main-table .score-pip-row { display: inline-flex; gap: 4px; align-items: center; }
#pi-main-table .pip.pip-pi { width: 7px; height: 7px; border-radius: 50%; background: #ddd; display: inline-block; }
#pi-main-table .pip.pip-pi.on { background: #0F6E56; }
#pi-main-table .pi-count-pill { display: inline-block; padding: 2px 7px; border-radius: 9px; font-weight: 700; font-size: 10px; min-width: 28px; letter-spacing: 0.2px; }
#pi-main-table .pi-count-0 { background: #e0ddd0; color: #8a8676; font-weight: 600; }
#pi-main-table .pi-count-1 { background: #E1F5EE; color: #0F6E56; }
#pi-main-table .pi-count-2 { background: #5DCAA5; color: #04342C; }
#pi-main-table .pi-count-3 { background: #0F6E56; color: #fff; }

#pi-main-table tr.tint-row td.name-cell, #pi-main-table tr.tint-row td.taxon { background: var(--tint-bg) !important; }
#pi-main-table tr.portfolio-band td:last-child { border-right: 4px solid var(--portfolio-color); }
#pi-main-table tr.portfolio-tint { background: var(--portfolio-bg); }
#pi-main-table tr.portfolio-tint:hover { background: var(--portfolio-bg-hover); }
/* MD-V2-PRE-INDICATORS-MARKER-CSS-END */
'''

# CSS anchor: chain on chrome-parity-followup CSS-END (the most recent marker
# before bootstrap-default-tab-fix, which only adds a comment, not a new marker).
# Bootstrap-default-tab-fix DOES add a marker comment after the followup CSS-END,
# but it does so by replacing the followup marker line with marker+comment, so
# the followup marker is still present and unique. We anchor on it.
ANCHOR_CSS_END_LF   = b'/* MD-V2-CHROME-PARITY-FOLLOWUP-MARKER-CSS-END */\n'
ANCHOR_CSS_END_CRLF = b'/* MD-V2-CHROME-PARITY-FOLLOWUP-MARKER-CSS-END */\r\n'

ANCHOR_RT_FN = b'function renderTab(id){'


def replace_one(src, anchor_lf, anchor_crlf, replacement_lf, replacement_crlf, label):
    n_lf = src.count(anchor_lf)
    n_crlf = src.count(anchor_crlf) if anchor_crlf != anchor_lf else 0
    if n_lf == 1:
        return src.replace(anchor_lf, replacement_lf, 1)
    if n_crlf == 1:
        return src.replace(anchor_crlf, replacement_crlf, 1)
    fail(f"Anchor {label}: count = (LF {n_lf}, CRLF {n_crlf}), expected exactly 1 in one form. Head: {anchor_lf[:120]!r}")


def main():
    check_fuse_environment()
    print(f"[pre-indicators-patch] working dir: {SCRIPT_DIR}")
    if not DASH_PY.exists(): fail(f"build_dashboard.py not found")
    if not MODULE_JS.exists(): fail(f"_pre_indicators_tab_module.js not found")
    src = DASH_PY.read_bytes()
    mod = MODULE_JS.read_bytes()
    print(f"[pre-indicators-patch] build_dashboard.py: {len(src)} bytes")
    print(f"[pre-indicators-patch] _pre_indicators_tab_module.js: {len(mod)} bytes")

    if MARKER_BYTES in src:
        if "--force" in sys.argv:
            baks = sorted(SCRIPT_DIR.glob("build_dashboard.py.bak-pre-md-v2-pre-indicators-*"), reverse=True)
            if not baks:
                fail("No pre-indicators backup found to revert from.")
            print(f"[pre-indicators-patch] --force: reverting from {baks[0].name}")
            shutil.copy2(baks[0], DASH_PY)
            src = DASH_PY.read_bytes()
            if MARKER_BYTES in src: fail("Backup still has marker.")
        else:
            print(f"[pre-indicators-patch] marker present - already applied. Use --force to re-apply.")
            return

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = DASH_PY.with_suffix(f".py.bak-pre-md-v2-pre-indicators-{ts}")
    shutil.copy2(DASH_PY, bak)
    print(f"[pre-indicators-patch] backup: {bak.name}")

    # Pre-flight: confirm precursors are in place.
    if b"MD-V2-STAGE4-MARKER" not in src:
        fail("Stage 4 marker missing - run Stage 4 patcher first.")
    if b"MD-V2-CHROME-PARITY-FOLLOWUP-MARKER-CSS-END" not in src:
        fail("Chrome-parity-followup CSS-END marker missing - run followup patcher first.")
    # SUMMARY removal patcher must have run (otherwise IMPL anchor won't match)
    if b'IMPLEMENTED_TABS = [\r\n    "summary",' in src or b'IMPLEMENTED_TABS = [\n    "summary",' in src:
        fail("SUMMARY still in IMPLEMENTED_TABS - run summary-removal patcher first.")

    # Apply edits.
    src = replace_one(src, ANCHOR_TABS, ANCHOR_TABS.replace(b'\n', b'\r\n').replace(b'\r\r\n', b'\r\n'),
                      REPLACE_TABS, REPLACE_TABS.replace(b'\n', b'\r\n').replace(b'\r\r\n', b'\r\n'),
                      "TABS")
    print(f"[pre-indicators-patch]   edit 1/4: TABS applied")

    src = replace_one(src, ANCHOR_IMPL, ANCHOR_IMPL.replace(b'\n', b'\r\n').replace(b'\r\r\n', b'\r\n'),
                      REPLACE_IMPL, REPLACE_IMPL.replace(b'\n', b'\r\n').replace(b'\r\r\n', b'\r\n'),
                      "IMPL")
    print(f"[pre-indicators-patch]   edit 2/4: IMPL applied")

    src = replace_one(src, ANCHOR_RENDERTAB_LF, ANCHOR_RENDERTAB_CRLF,
                      REPLACE_RENDERTAB_LF, REPLACE_RENDERTAB_CRLF,
                      "RENDERTAB")
    print(f"[pre-indicators-patch]   edit 3/4: RENDERTAB applied")

    # CSS injection - prepend PI_CSS just before the closing FOLLOWUP marker line.
    # We replace the followup CSS-END marker with itself + our new CSS block, so
    # the followup marker stays in place AND our new CSS lives right before our
    # own new CSS-END marker.
    n_lf = src.count(ANCHOR_CSS_END_LF)
    n_crlf = src.count(ANCHOR_CSS_END_CRLF)
    if n_lf == 1:
        repl = ANCHOR_CSS_END_LF + PI_CSS.lstrip(b'\n')
        src = src.replace(ANCHOR_CSS_END_LF, repl, 1)
    elif n_crlf == 1:
        repl = ANCHOR_CSS_END_CRLF + PI_CSS.lstrip(b'\n').replace(b'\n', b'\r\n')
        src = src.replace(ANCHOR_CSS_END_CRLF, repl, 1)
    else:
        fail(f"CSS-END anchor count = (LF {n_lf}, CRLF {n_crlf}), expected 1.")
    print(f"[pre-indicators-patch]   edit 4/4: CSS injected")

    # Insert the module just before the renderTab function definition.
    if src.count(ANCHOR_RT_FN) != 1:
        fail(f"renderTab fn anchor count = {src.count(ANCHOR_RT_FN)} (expected 1).")
    module_block = (
        b'\n/* MD-V2-PRE-INDICATORS-MARKER-MODULE-START */\n'
        + mod
        + b'\n/* MD-V2-PRE-INDICATORS-MARKER-MODULE-END */\n\n'
    )
    rt_idx = src.find(ANCHOR_RT_FN)
    src = src[:rt_idx] + module_block + src[rt_idx:]
    print(f"[pre-indicators-patch]   module inlined")

    # Atomic write + py_compile check
    tmp = DASH_PY.with_suffix(f".py.tmp-{ts}")
    tmp.write_bytes(src)
    try:
        py_compile.compile(str(tmp), doraise=True)
    except py_compile.PyCompileError as e:
        tmp.unlink(missing_ok=True)
        fail(f"py_compile failed: {e}")
    os.replace(str(tmp), str(DASH_PY))
    new_size = DASH_PY.stat().st_size
    print(f"[pre-indicators-patch] OK. New size: {new_size} bytes")
    print(f"[pre-indicators-patch] marker count: {DASH_PY.read_bytes().count(MARKER_BYTES)}")
    print(f"[pre-indicators-patch] DONE. Next: python scripts\\build_dashboard.py")


if __name__ == "__main__":
    main()
