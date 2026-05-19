r"""
Patcher: Pre-indicators restyle + Post-indicators tab (13-May-26, Session 24)

Bundled patcher for Richard's QC of Pre-indicators:
  (A) Broaden chrome-parity CSS scope so legacy chrome is hidden on ALL V2 tabs.
  (B) Replace embedded PI module (drops aggregate count column + score pips).
  (C) Rebuild PI CSS to match Stage 1-4 .gcap visual style.
  (D) Add Post-indicators tab end-to-end (nav button + IMPL + dispatch + module + CSS).
  (E) Atomic write, no marker-plant step (anchor disappearance = idempotency).

MUST run Windows-side. Refuses Cowork/FUSE mount.
"""
import os, shutil, py_compile, sys
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent.resolve()
DASH_PY = SCRIPT_DIR / "build_dashboard.py"
PI_MODULE_JS = SCRIPT_DIR / "_pre_indicators_tab_module.js"
PO_MODULE_JS = SCRIPT_DIR / "_post_indicators_tab_module.js"

CRLF = b"\r\n"
PI_MARKER = b"MD-V2-PRE-INDICATORS-MARKER"
PO_MARKER = b"MD-V2-POST-INDICATORS-MARKER"


def fail(msg):
    print("FAIL: " + msg)
    sys.exit(1)


def check_fuse_environment():
    here = str(SCRIPT_DIR).replace("\\", "/")
    if "/sessions/" in here or here.startswith("/tmp"):
        fail("Refusing to run from Cowork/FUSE mount.")


# (A) Chrome-parity broadening rules
CHROME_RULES = [
    (
        b'body[data-active-tab^="stage_"] .header-tabs-row { display: none !important; }',
        b'body[data-active-tab^="stage_"] .header-tabs-row,\n'
        b'body[data-active-tab="pre_indicators"] .header-tabs-row,\n'
        b'body[data-active-tab="post_indicators"] .header-tabs-row,\n'
        b'body[data-active-tab="setups"] .header-tabs-row,\n'
        b'body[data-active-tab="tests"] .header-tabs-row,\n'
        b'body[data-active-tab="master_overview"] .header-tabs-row { display: none !important; }',
    ),
    (
        b'body[data-active-tab^="stage_"] .v2-nav { display: flex; }',
        b'body[data-active-tab^="stage_"] .v2-nav,\n'
        b'body[data-active-tab="pre_indicators"] .v2-nav,\n'
        b'body[data-active-tab="post_indicators"] .v2-nav,\n'
        b'body[data-active-tab="setups"] .v2-nav,\n'
        b'body[data-active-tab="tests"] .v2-nav,\n'
        b'body[data-active-tab="master_overview"] .v2-nav { display: flex; }',
    ),
    (
        b'body[data-active-tab^="stage_"] .header-controls-row { display: none !important; }',
        b'body[data-active-tab^="stage_"] .header-controls-row,\n'
        b'body[data-active-tab="pre_indicators"] .header-controls-row,\n'
        b'body[data-active-tab="post_indicators"] .header-controls-row,\n'
        b'body[data-active-tab="setups"] .header-controls-row,\n'
        b'body[data-active-tab="tests"] .header-controls-row,\n'
        b'body[data-active-tab="master_overview"] .header-controls-row { display: none !important; }',
    ),
]


# (C) Pre-indicators CSS - matches Stage 1-4 .gcap visual style.
PI_CSS_NEW = (
    b'/* MD-V2-PRE-INDICATORS-MARKER-CSS-START */\n'
    b'#tab-pre_indicators .group-captions { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 16px 0 14px 0; }\n'
    b'#tab-pre_indicators .group-captions .gcap { background: #fbfaf5; border: 1px solid #e0dcc8; border-left: 3px solid #b08a4e; border-radius: 4px; padding: 10px 12px; font-size: 11px; line-height: 1.45; color: #555; }\n'
    b'#tab-pre_indicators .group-captions .gcap b { display: block; margin-bottom: 4px; font-weight: 700; color: #b08a4e; font-size: 11px; letter-spacing: 0.2px; }\n'
    b'#tab-pre_indicators .group-captions .gcap-g1 { border-left-color: #0F6E56; }\n'
    b'#tab-pre_indicators .group-captions .gcap-g1 b { color: #0F6E56; }\n'
    b'#tab-pre_indicators .group-captions .gcap-g2 { border-left-color: #854F0B; }\n'
    b'#tab-pre_indicators .group-captions .gcap-g2 b { color: #854F0B; }\n'
    b'#tab-pre_indicators .group-captions .gcap-g3 { border-left-color: #A32D2D; }\n'
    b'#tab-pre_indicators .group-captions .gcap-g3 b { color: #A32D2D; }\n'
    b'\n'
    b'#tab-pre_indicators .s1-rating-tiles { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }\n'
    b'#tab-pre_indicators .s1-rating-tiles .pi-tile-pullback   { background: rgba(15, 110, 86, 0.10); border: 1px solid rgba(15,110,86,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }\n'
    b'#tab-pre_indicators .s1-rating-tiles .pi-tile-basing     { background: rgba(133, 79, 11, 0.10); border: 1px solid rgba(133,79,11,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }\n'
    b'#tab-pre_indicators .s1-rating-tiles .pi-tile-collapsing { background: rgba(163, 45, 45, 0.10); border: 1px solid rgba(163,45,45,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }\n'
    b'#tab-pre_indicators .s1-rating-tiles .pi-tile-pullback.active   { background: rgba(15, 110, 86, 0.22); border: 1.5px solid #0F6E56; }\n'
    b'#tab-pre_indicators .s1-rating-tiles .pi-tile-basing.active     { background: rgba(133, 79, 11, 0.22); border: 1.5px solid #854F0B; }\n'
    b'#tab-pre_indicators .s1-rating-tiles .pi-tile-collapsing.active { background: rgba(163, 45, 45, 0.22); border: 1.5px solid #A32D2D; }\n'
    b'#tab-pre_indicators .s1-rating-tiles .pi-strip-pullback   { background: #0F6E56; height: 4px; margin-top: 6px; border-radius: 2px; }\n'
    b'#tab-pre_indicators .s1-rating-tiles .pi-strip-basing     { background: #854F0B; height: 4px; margin-top: 6px; border-radius: 2px; }\n'
    b'#tab-pre_indicators .s1-rating-tiles .pi-strip-collapsing { background: #A32D2D; height: 4px; margin-top: 6px; border-radius: 2px; }\n'
    b'\n'
    b'#pi-main-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 11px; table-layout: fixed; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }\n'
    b'#pi-main-table thead { position: sticky; top: 0; z-index: 50; background: #fbfaf5; box-shadow: 0 2px 4px rgba(0,0,0,0.06); }\n'
    b'#pi-main-table thead th { background: #fbfaf5 !important; border-bottom: 1px solid #e0dcc8; padding: 7px 3px; text-align: center; font-weight: 600; font-size: 10px; color: #666; cursor: pointer; user-select: none; line-height: 1.25; vertical-align: middle; }\n'
    b'#pi-main-table thead th:hover { background: #f0ebd9 !important; }\n'
    b'#pi-main-table thead .group-header-row th { background: #f3efe2 !important; font-size: 9px; text-transform: uppercase; font-weight: 700; letter-spacing: 0.4px; padding: 5px 3px; cursor: default; line-height: 1.25; }\n'
    b'#pi-main-table thead .group-header-row th:hover { background: #f3efe2 !important; }\n'
    b'#pi-main-table thead tr.group-header-row th { position: sticky; top: 0; }\n'
    b'#pi-main-table thead tr.col-header-row  th { position: sticky; top: 28px; border-top: 1px solid #e0dcc8; }\n'
    b'#pi-main-table thead .gh-inputs { color: #555; }\n'
    b'#pi-main-table thead .gh-g1 { color: #0F6E56; }\n'
    b'#pi-main-table thead .gh-g2 { color: #854F0B; }\n'
    b'#pi-main-table thead .gh-g3 { color: #A32D2D; }\n'
    b'#pi-main-table .hd { display: inline-flex; align-items: center; justify-content: center; gap: 3px; width: 100%; }\n'
    b'#pi-main-table .hd .lbl { white-space: normal; word-break: break-word; }\n'
    b'#pi-main-table .hd .sort-arrow { font-size: 9px; color: #0F6E56; flex: 0 0 auto; line-height: 1; }\n'
    b'#pi-main-table .hd .sort-placeholder { width: 9px; flex: 0 0 auto; }\n'
    b'#pi-main-table td { padding: 5px 4px; border-bottom: 1px solid #efece0; text-align: center; vertical-align: middle; height: 38px; box-sizing: border-box; font-variant-numeric: tabular-nums; }\n'
    b'#pi-main-table tr:hover { background: rgba(15,110,86,0.05); }\n'
    b'#pi-main-table td.grp-start-g1, #pi-main-table th.grp-start-g1 { border-left: 2px solid rgba(15,110,86,0.40); }\n'
    b'#pi-main-table td.grp-start-g2, #pi-main-table th.grp-start-g2 { border-left: 2px solid rgba(133,79,11,0.40); }\n'
    b'#pi-main-table td.grp-start-g3, #pi-main-table th.grp-start-g3 { border-left: 2px solid rgba(163,45,45,0.40); }\n'
    b'#pi-main-table td.pi-pass { background: rgba(15,110,86,0.12); color: #0F6E56; font-weight: 700; }\n'
    b'#pi-main-table td.pi-fail { color: #999; }\n'
    b'#pi-main-table td.name-cell { text-align: left; padding: 4px 4px 4px 8px; line-height: 1.15; }\n'
    b'#pi-main-table td.name-cell .co { font-weight: 700; font-size: 11px; color: #2a2a2a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }\n'
    b'#pi-main-table td.name-cell .tk { font-size: 9px; color: #999; font-weight: 500; margin-top: 1px; }\n'
    b'#pi-main-table td.name-cell .live-dot { color: #2e7d32; font-weight: 700; margin-right: 4px; display: inline-block; vertical-align: middle; line-height: 1; font-size: 10px; }\n'
    b'#pi-main-table td.taxon { text-align: left; font-size: 9px; line-height: 1.2; padding: 4px; }\n'
    b'#pi-main-table td.taxon .ind { color: #666; font-weight: 500; }\n'
    b'#pi-main-table td.taxon .sec { color: #999; }\n'
    b'#pi-main-table col.c-name { width: 130px; }\n'
    b'#pi-main-table col.c-taxon { width: 170px; }\n'
    b'#pi-main-table col.c-price { width: 56px; }\n'
    b'#pi-main-table col.c-52wh { width: 54px; }\n'
    b'#pi-main-table col.c-pullback { width: 64px; }\n'
    b'#pi-main-table col.c-ma150 { width: 54px; }\n'
    b'#pi-main-table col.c-ma200 { width: 54px; }\n'
    b'#pi-main-table col.c-pattern { width: 75px; }\n'
    b'#pi-main-table tr.tint-row td.name-cell, #pi-main-table tr.tint-row td.taxon { background: var(--tint-bg) !important; }\n'
    b'#pi-main-table tr.portfolio-band td:last-child { border-right: 4px solid var(--portfolio-color); }\n'
    b'#pi-main-table tr.portfolio-tint { background: var(--portfolio-bg); }\n'
    b'#pi-main-table tr.portfolio-tint:hover { background: var(--portfolio-bg-hover); }\n'
    b'/* MD-V2-PRE-INDICATORS-MARKER-CSS-END */\n'
)


PO_CSS = (
    b'\n/* MD-V2-POST-INDICATORS-MARKER-CSS-START */\n'
    b'#tab-post_indicators .group-captions { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin: 16px 0 14px 0; }\n'
    b'#tab-post_indicators .group-captions .gcap { background: #fbfaf5; border: 1px solid #e0dcc8; border-left: 3px solid #b08a4e; border-radius: 4px; padding: 10px 12px; font-size: 11px; line-height: 1.45; color: #555; }\n'
    b'#tab-post_indicators .group-captions .gcap b { display: block; margin-bottom: 4px; font-weight: 700; color: #b08a4e; font-size: 11px; letter-spacing: 0.2px; }\n'
    b'#tab-post_indicators .group-captions .gcap-g1 { border-left-color: #0F6E56; }\n'
    b'#tab-post_indicators .group-captions .gcap-g1 b { color: #0F6E56; }\n'
    b'#tab-post_indicators .group-captions .gcap-g2 { border-left-color: #A32D2D; }\n'
    b'#tab-post_indicators .group-captions .gcap-g2 b { color: #A32D2D; }\n'
    b'\n'
    b'#tab-post_indicators .s1-rating-tiles { display: grid; grid-template-columns: repeat(5, 1fr); gap: 8px; }\n'
    b'#tab-post_indicators .s1-rating-tiles .po-tile-bull { background: rgba(15, 110, 86, 0.10); border: 1px solid rgba(15,110,86,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }\n'
    b'#tab-post_indicators .s1-rating-tiles .po-tile-bear { background: rgba(163, 45, 45, 0.10); border: 1px solid rgba(163,45,45,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }\n'
    b'#tab-post_indicators .s1-rating-tiles .po-tile-bull.active { background: rgba(15, 110, 86, 0.22); border: 1.5px solid #0F6E56; }\n'
    b'#tab-post_indicators .s1-rating-tiles .po-tile-bear.active { background: rgba(163, 45, 45, 0.22); border: 1.5px solid #A32D2D; }\n'
    b'#tab-post_indicators .s1-rating-tiles .po-strip-bull { background: #0F6E56; height: 4px; margin-top: 6px; border-radius: 2px; }\n'
    b'#tab-post_indicators .s1-rating-tiles .po-strip-bear { background: #A32D2D; height: 4px; margin-top: 6px; border-radius: 2px; }\n'
    b'\n'
    b'#po-main-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 11px; table-layout: fixed; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }\n'
    b'#po-main-table thead { position: sticky; top: 0; z-index: 50; background: #fbfaf5; box-shadow: 0 2px 4px rgba(0,0,0,0.06); }\n'
    b'#po-main-table thead th { background: #fbfaf5 !important; border-bottom: 1px solid #e0dcc8; padding: 7px 3px; text-align: center; font-weight: 600; font-size: 10px; color: #666; cursor: pointer; user-select: none; line-height: 1.25; vertical-align: middle; }\n'
    b'#po-main-table thead th:hover { background: #f0ebd9 !important; }\n'
    b'#po-main-table thead .group-header-row th { background: #f3efe2 !important; font-size: 9px; text-transform: uppercase; font-weight: 700; letter-spacing: 0.4px; padding: 5px 3px; cursor: default; line-height: 1.25; }\n'
    b'#po-main-table thead tr.group-header-row th { position: sticky; top: 0; }\n'
    b'#po-main-table thead tr.col-header-row th { position: sticky; top: 28px; border-top: 1px solid #e0dcc8; }\n'
    b'#po-main-table thead .gh-inputs { color: #555; }\n'
    b'#po-main-table thead .gh-g1 { color: #0F6E56; }\n'
    b'#po-main-table thead .gh-g2 { color: #A32D2D; }\n'
    b'#po-main-table .hd { display: inline-flex; align-items: center; justify-content: center; gap: 3px; width: 100%; }\n'
    b'#po-main-table .hd .lbl { white-space: normal; word-break: break-word; }\n'
    b'#po-main-table .hd .sort-arrow { font-size: 9px; color: #0F6E56; flex: 0 0 auto; line-height: 1; }\n'
    b'#po-main-table .hd .sort-placeholder { width: 9px; flex: 0 0 auto; }\n'
    b'#po-main-table td { padding: 5px 4px; border-bottom: 1px solid #efece0; text-align: center; vertical-align: middle; height: 38px; box-sizing: border-box; font-variant-numeric: tabular-nums; }\n'
    b'#po-main-table tr:hover { background: rgba(15,110,86,0.04); }\n'
    b'#po-main-table td.grp-start-g1, #po-main-table th.grp-start-g1 { border-left: 2px solid rgba(15,110,86,0.40); }\n'
    b'#po-main-table td.grp-end-g1,   #po-main-table th.grp-end-g1   { border-right: 2px solid rgba(15,110,86,0.40); }\n'
    b'#po-main-table td.grp-start-g2, #po-main-table th.grp-start-g2 { border-left: 2px solid rgba(163,45,45,0.40); }\n'
    b'#po-main-table td.grp-end-g2,   #po-main-table th.grp-end-g2   { border-right: 2px solid rgba(163,45,45,0.40); }\n'
    b'#po-main-table td.po-pass-bull { background: rgba(15,110,86,0.12); color: #0F6E56; font-weight: 700; }\n'
    b'#po-main-table td.po-pass-bear { background: rgba(163,45,45,0.12); color: #A32D2D; font-weight: 700; }\n'
    b'#po-main-table td.po-fail { color: #999; }\n'
    b'#po-main-table td.name-cell { text-align: left; padding: 4px 4px 4px 8px; line-height: 1.15; }\n'
    b'#po-main-table td.name-cell .co { font-weight: 700; font-size: 11px; color: #2a2a2a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }\n'
    b'#po-main-table td.name-cell .tk { font-size: 9px; color: #999; font-weight: 500; margin-top: 1px; }\n'
    b'#po-main-table td.name-cell .live-dot { color: #2e7d32; font-weight: 700; margin-right: 4px; display: inline-block; vertical-align: middle; line-height: 1; font-size: 10px; }\n'
    b'#po-main-table td.taxon { text-align: left; font-size: 9px; line-height: 1.2; padding: 4px; }\n'
    b'#po-main-table td.taxon .ind { color: #666; font-weight: 500; }\n'
    b'#po-main-table td.taxon .sec { color: #999; }\n'
    b'#po-main-table col.c-name { width: 130px; }\n'
    b'#po-main-table col.c-taxon { width: 150px; }\n'
    b'#po-main-table col.c-price { width: 52px; }\n'
    b'#po-main-table col.c-ma { width: 48px; }\n'
    b'#po-main-table col.c-pattern { width: 64px; }\n'
    b'#po-main-table tr.tint-row td.name-cell, #po-main-table tr.tint-row td.taxon { background: var(--tint-bg) !important; }\n'
    b'#po-main-table tr.portfolio-band td:last-child { border-right: 4px solid var(--portfolio-color); }\n'
    b'#po-main-table tr.portfolio-tint { background: var(--portfolio-bg); }\n'
    b'#po-main-table tr.portfolio-tint:hover { background: var(--portfolio-bg-hover); }\n'
    b'/* MD-V2-POST-INDICATORS-MARKER-CSS-END */\n'
)


def replace_one(src, anchor_text, replacement_text, label):
    a_lf = anchor_text
    a_crlf = anchor_text.replace(b'\n', b'\r\n').replace(b'\r\r\n', b'\r\n')
    r_lf = replacement_text
    r_crlf = replacement_text.replace(b'\n', b'\r\n').replace(b'\r\r\n', b'\r\n')
    n_lf = src.count(a_lf)
    n_crlf = src.count(a_crlf) if a_crlf != a_lf else 0
    if n_lf == 1:
        return src.replace(a_lf, r_lf, 1)
    if n_crlf == 1:
        return src.replace(a_crlf, r_crlf, 1)
    fail("Anchor [" + label + "] count = (LF " + str(n_lf) + ", CRLF " + str(n_crlf) + "). Expected 1.")


def main():
    check_fuse_environment()
    print("[pi-restyle+postind] working dir: " + str(SCRIPT_DIR))
    if not DASH_PY.exists(): fail("build_dashboard.py not found")
    if not PI_MODULE_JS.exists(): fail("_pre_indicators_tab_module.js not found")
    if not PO_MODULE_JS.exists(): fail("_post_indicators_tab_module.js not found")

    src = DASH_PY.read_bytes()
    orig_size = len(src)
    pi_mod = PI_MODULE_JS.read_bytes()
    po_mod = PO_MODULE_JS.read_bytes()
    print("[pi-restyle+postind] build_dashboard.py: " + str(orig_size) + " bytes")
    print("[pi-restyle+postind] PI module: " + str(len(pi_mod)) + " bytes")
    print("[pi-restyle+postind] PO module: " + str(len(po_mod)) + " bytes")

    if PI_MARKER not in src:
        fail("PI marker missing - run pre-indicators patcher + nav-button patcher first.")
    if PO_MARKER in src:
        fail("PO marker present - this patcher has run before. Revert and re-apply if needed.")
    if b'body[data-active-tab^="stage_"] .header-tabs-row { display: none !important; }' not in src:
        fail("Chrome-parity rule not in expected pre-broadening shape.")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = DASH_PY.with_suffix(".py.bak-pre-pi-restyle-postind-" + ts)
    shutil.copy2(DASH_PY, bak)
    print("[pi-restyle+postind] backup: " + bak.name)

    # (A) Chrome-parity broadening
    for i, (old, new) in enumerate(CHROME_RULES, 1):
        n = src.count(old)
        if n != 1:
            fail("Chrome rule " + str(i) + "/3 anchor count = " + str(n))
        src = src.replace(old, new, 1)
        print("[pi-restyle+postind]   (A) chrome rule " + str(i) + "/3 broadened")

    # (B) Replace PI module body
    pi_start = b'/* MD-V2-PRE-INDICATORS-MARKER-MODULE-START */'
    pi_end   = b'/* MD-V2-PRE-INDICATORS-MARKER-MODULE-END */'
    s_start = src.find(pi_start)
    s_end_pos = src.find(pi_end)
    if s_start < 0 or s_end_pos < 0:
        fail("PI module markers not found")
    pi_block = pi_start + b'\n' + pi_mod + b'\n' + pi_end
    src = src[:s_start] + pi_block + src[s_end_pos + len(pi_end):]
    print("[pi-restyle+postind]   (B) PI module body replaced")

    # (C) Replace PI CSS
    pi_css_start = b'/* MD-V2-PRE-INDICATORS-MARKER-CSS-START */'
    pi_css_end   = b'/* MD-V2-PRE-INDICATORS-MARKER-CSS-END */'
    c_start = src.find(pi_css_start)
    c_end_pos = src.find(pi_css_end)
    if c_start < 0 or c_end_pos < 0:
        fail("PI CSS markers not found")
    src = src[:c_start] + PI_CSS_NEW + src[c_end_pos + len(pi_css_end):]
    print("[pi-restyle+postind]   (C) PI CSS rebuilt")

    # (D1) PO V2 nav button
    src = replace_one(
        src,
        b'      + \'<span class="v2-nav-placeholder" title="Coming soon">Post-indicators</span>\'\n',
        b'      + \'<button class="v2-nav-btn" data-v2-tab="post_indicators" onclick="switchTab(\\\'post_indicators\\\')">Post-indicators</button>\'\n',
        "PO nav button"
    )
    print("[pi-restyle+postind]   (D1) PO V2-nav button wired")

    # (D2) IMPLEMENTED_TABS - add post_indicators after pre_indicators
    src = replace_one(
        src,
        b'    "stage_4",  # MD-V2-STAGE4-MARKER\n'
        b'    "pre_indicators",  # MD-V2-PRE-INDICATORS-MARKER\n'
        b'    "mm99", "bp", "pb", "utr", "vcp", "tech", "combos", "changes", "positions",\n'
        b'    "ssem", "val",\n'
        b']',
        b'    "stage_4",  # MD-V2-STAGE4-MARKER\n'
        b'    "pre_indicators",  # MD-V2-PRE-INDICATORS-MARKER\n'
        b'    "post_indicators",  # MD-V2-POST-INDICATORS-MARKER\n'
        b'    "mm99", "bp", "pb", "utr", "vcp", "tech", "combos", "changes", "positions",\n'
        b'    "ssem", "val",\n'
        b']',
        "PO IMPL"
    )
    print("[pi-restyle+postind]   (D2) PO IMPLEMENTED_TABS entry added")

    # (D3) renderTab dispatch
    src = replace_one(
        src,
        b'  else if(id==="pre_indicators")renderPreIndicators();  /* MD-V2-PRE-INDICATORS-MARKER */\n',
        b'  else if(id==="pre_indicators")renderPreIndicators();  /* MD-V2-PRE-INDICATORS-MARKER */\n'
        b'  else if(id==="post_indicators")renderPostIndicators();  /* MD-V2-POST-INDICATORS-MARKER */\n',
        "PO renderTab"
    )
    print("[pi-restyle+postind]   (D3) PO renderTab dispatch wired")

    # (D4) Insert PO module after PI module END marker
    pi_end_pos = src.rfind(pi_end)
    if pi_end_pos < 0:
        fail("PI module END marker not found for PO insertion")
    po_block = (
        b'\n/* MD-V2-POST-INDICATORS-MARKER-MODULE-START */\n'
        + po_mod
        + b'\n/* MD-V2-POST-INDICATORS-MARKER-MODULE-END */\n'
    )
    insertion_point = pi_end_pos + len(pi_end)
    src = src[:insertion_point] + po_block + src[insertion_point:]
    print("[pi-restyle+postind]   (D4) PO module inlined")

    # (D5) Inject PO CSS after PI CSS END marker
    pi_css_end_pos = src.rfind(pi_css_end)
    if pi_css_end_pos < 0:
        fail("PI CSS END marker not found for PO CSS insertion")
    insertion_point = pi_css_end_pos + len(pi_css_end)
    src = src[:insertion_point] + PO_CSS + src[insertion_point:]
    print("[pi-restyle+postind]   (D5) PO CSS injected")

    # Atomic write + py_compile gate
    tmp = DASH_PY.with_suffix(".py.tmp-" + ts)
    tmp.write_bytes(src)
    try:
        py_compile.compile(str(tmp), doraise=True)
    except py_compile.PyCompileError as e:
        tmp.unlink(missing_ok=True)
        fail("py_compile failed: " + str(e))
    os.replace(str(tmp), str(DASH_PY))
    new_size = DASH_PY.stat().st_size
    print("[pi-restyle+postind] OK. New size: " + str(new_size) + " bytes (delta " + str(new_size - orig_size) + ")")

    final = DASH_PY.read_bytes()
    po_btn_pat = b'data-v2-tab="post_indicators"'
    pre_ind_chrome_pat = b'pre_indicators"] .header-tabs-row'
    print("[pi-restyle+postind] PI marker count : " + str(final.count(PI_MARKER)))
    print("[pi-restyle+postind] PO marker count : " + str(final.count(PO_MARKER)))
    print("[pi-restyle+postind] PO V2 button OK : " + str(po_btn_pat in final))
    print("[pi-restyle+postind] PreInd chrome OK: " + str(final.count(pre_ind_chrome_pat) >= 1))
    print("[pi-restyle+postind] DONE. Next: python scripts\\build_dashboard.py")


if __name__ == "__main__":
    main()
