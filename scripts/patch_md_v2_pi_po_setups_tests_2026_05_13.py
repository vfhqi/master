r"""
Patcher: PI + PO modules rebuilt with constituent tests as columns,
         plus Setups tab + Capital Tests tab end-to-end.
(13-May-26 PM, Session 24 final delivery)

Operations:
  (A) Replace PI module body with new constituent-tests version.
  (B) Replace PO module body with new constituent-tests version.
  (C) Add Setups tab: OLD_TABS entry + V2 nav button swap + IMPL + dispatch + module + CSS.
  (D) Add Capital Tests tab: same 5-step routine.
  (E) Update PI + PO CSS to use new test-column classes (.pi-pass, .po-pass-bull/bear).
  (F) Atomic write, no marker-plant step.

MUST run Windows-side. Refuses FUSE.
"""
import os, shutil, py_compile, sys
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent.resolve()
DASH_PY = SCRIPT_DIR / "build_dashboard.py"
PI_MODULE = SCRIPT_DIR / "_pre_indicators_tab_module.js"
PO_MODULE = SCRIPT_DIR / "_post_indicators_tab_module.js"
ST_MODULE = SCRIPT_DIR / "_setups_tab_module.js"
TS_MODULE = SCRIPT_DIR / "_tests_tab_module.js"

CRLF = b"\r\n"

PI_MARKER = b"MD-V2-PRE-INDICATORS-MARKER"
PO_MARKER = b"MD-V2-POST-INDICATORS-MARKER"
ST_MARKER = b"MD-V2-SETUPS-MARKER"
TS_MARKER = b"MD-V2-TESTS-MARKER"


def fail(msg):
    print("FAIL: " + msg)
    sys.exit(1)


def check_fuse_environment():
    here = str(SCRIPT_DIR).replace("\\", "/")
    if "/sessions/" in here or here.startswith("/tmp"):
        fail("Refusing to run from Cowork/FUSE mount.")


# CSS additions: append to Setups + Tests tabs (PI/PO CSS already present from earlier patcher)
ST_CSS = (
    b'\n/* MD-V2-SETUPS-MARKER-CSS-START */\n'
    b'#tab-setups .group-captions { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 16px 0 14px 0; }\n'
    b'#tab-setups .group-captions .gcap { background: #fbfaf5; border: 1px solid #e0dcc8; border-left: 3px solid #b08a4e; border-radius: 4px; padding: 10px 12px; font-size: 11px; line-height: 1.45; color: #555; }\n'
    b'#tab-setups .group-captions .gcap b { display: block; margin-bottom: 4px; font-weight: 700; color: #b08a4e; font-size: 11px; letter-spacing: 0.2px; }\n'
    b'#tab-setups .group-captions .gcap-g1 { border-left-color: #BA7517; }\n'
    b'#tab-setups .group-captions .gcap-g1 b { color: #854F0B; }\n'
    b'#tab-setups .group-captions .gcap-g2 { border-left-color: #639922; }\n'
    b'#tab-setups .group-captions .gcap-g2 b { color: #3B6D11; }\n'
    b'#tab-setups .group-captions .gcap-g3 { border-left-color: #0F6E56; }\n'
    b'#tab-setups .group-captions .gcap-g3 b { color: #0F6E56; }\n'
    b'#tab-setups .group-captions .gcap-g4 { border-left-color: #185FA5; }\n'
    b'#tab-setups .group-captions .gcap-g4 b { color: #0C447C; }\n'
    b'\n'
    b'#tab-setups .s1-rating-tiles { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }\n'
    b'#tab-setups .s1-rating-tiles .st-tile-amber { background: rgba(186,117,23,0.10); border: 1px solid rgba(186,117,23,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }\n'
    b'#tab-setups .s1-rating-tiles .st-tile-green { background: rgba(99,153,34,0.10); border: 1px solid rgba(99,153,34,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }\n'
    b'#tab-setups .s1-rating-tiles .st-tile-teal  { background: rgba(15,110,86,0.10); border: 1px solid rgba(15,110,86,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }\n'
    b'#tab-setups .s1-rating-tiles .st-tile-navy  { background: rgba(24,95,165,0.10); border: 1px solid rgba(24,95,165,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }\n'
    b'#tab-setups .s1-rating-tiles .st-tile-amber.active { background: rgba(186,117,23,0.22); border: 1.5px solid #BA7517; }\n'
    b'#tab-setups .s1-rating-tiles .st-tile-green.active { background: rgba(99,153,34,0.22); border: 1.5px solid #639922; }\n'
    b'#tab-setups .s1-rating-tiles .st-tile-teal.active  { background: rgba(15,110,86,0.22); border: 1.5px solid #0F6E56; }\n'
    b'#tab-setups .s1-rating-tiles .st-tile-navy.active  { background: rgba(24,95,165,0.22); border: 1.5px solid #185FA5; }\n'
    b'#tab-setups .s1-rating-tiles .st-strip-amber { background: #BA7517; height: 4px; margin-top: 6px; border-radius: 2px; }\n'
    b'#tab-setups .s1-rating-tiles .st-strip-green { background: #639922; height: 4px; margin-top: 6px; border-radius: 2px; }\n'
    b'#tab-setups .s1-rating-tiles .st-strip-teal  { background: #0F6E56; height: 4px; margin-top: 6px; border-radius: 2px; }\n'
    b'#tab-setups .s1-rating-tiles .st-strip-navy  { background: #185FA5; height: 4px; margin-top: 6px; border-radius: 2px; }\n'
    b'\n'
    b'#st-main-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 11px; table-layout: fixed; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }\n'
    b'#st-main-table thead { position: sticky; top: 0; z-index: 50; background: #fbfaf5; box-shadow: 0 2px 4px rgba(0,0,0,0.06); }\n'
    b'#st-main-table thead th { background: #fbfaf5 !important; border-bottom: 1px solid #e0dcc8; padding: 7px 3px; text-align: center; font-weight: 600; font-size: 10px; color: #666; cursor: pointer; user-select: none; line-height: 1.25; vertical-align: middle; }\n'
    b'#st-main-table thead th:hover { background: #f0ebd9 !important; }\n'
    b'#st-main-table thead .group-header-row th { background: #f3efe2 !important; font-size: 9px; text-transform: uppercase; font-weight: 700; letter-spacing: 0.4px; padding: 5px 3px; cursor: default; line-height: 1.25; }\n'
    b'#st-main-table thead tr.group-header-row th { position: sticky; top: 0; }\n'
    b'#st-main-table thead tr.col-header-row th { position: sticky; top: 28px; border-top: 1px solid #e0dcc8; }\n'
    b'#st-main-table thead .gh-inputs { color: #555; }\n'
    b'#st-main-table thead .gh-g1 { color: #854F0B; }\n'
    b'#st-main-table thead .gh-g2 { color: #3B6D11; }\n'
    b'#st-main-table thead .gh-g3 { color: #0F6E56; }\n'
    b'#st-main-table thead .gh-g4 { color: #0C447C; }\n'
    b'#st-main-table .hd { display: inline-flex; align-items: center; justify-content: center; gap: 3px; width: 100%; }\n'
    b'#st-main-table .hd .lbl { white-space: normal; word-break: break-word; }\n'
    b'#st-main-table .hd .sort-arrow { font-size: 9px; color: #0F6E56; flex: 0 0 auto; line-height: 1; }\n'
    b'#st-main-table .hd .sort-placeholder { width: 9px; flex: 0 0 auto; }\n'
    b'#st-main-table td { padding: 5px 4px; border-bottom: 1px solid #efece0; text-align: center; vertical-align: middle; height: 38px; box-sizing: border-box; font-variant-numeric: tabular-nums; }\n'
    b'#st-main-table tr:hover { background: rgba(15,110,86,0.04); }\n'
    b'#st-main-table td.grp-start-g1, #st-main-table th.grp-start-g1 { border-left: 2px solid rgba(186,117,23,0.40); }\n'
    b'#st-main-table td.grp-end-g1,   #st-main-table th.grp-end-g1   { border-right: 2px solid rgba(186,117,23,0.40); }\n'
    b'#st-main-table td.grp-start-g2, #st-main-table th.grp-start-g2 { border-left: 2px solid rgba(99,153,34,0.40); }\n'
    b'#st-main-table td.grp-end-g2,   #st-main-table th.grp-end-g2   { border-right: 2px solid rgba(99,153,34,0.40); }\n'
    b'#st-main-table td.grp-start-g3, #st-main-table th.grp-start-g3 { border-left: 2px solid rgba(15,110,86,0.40); }\n'
    b'#st-main-table td.grp-end-g3,   #st-main-table th.grp-end-g3   { border-right: 2px solid rgba(15,110,86,0.40); }\n'
    b'#st-main-table td.grp-start-g4, #st-main-table th.grp-start-g4 { border-left: 2px solid rgba(24,95,165,0.40); }\n'
    b'#st-main-table td.grp-end-g4,   #st-main-table th.grp-end-g4   { border-right: 2px solid rgba(24,95,165,0.40); }\n'
    b'#st-main-table td.st-pass.st-tone-amber { background: rgba(186,117,23,0.12); color: #854F0B; font-weight: 700; }\n'
    b'#st-main-table td.st-pass.st-tone-green { background: rgba(99,153,34,0.12); color: #3B6D11; font-weight: 700; }\n'
    b'#st-main-table td.st-pass.st-tone-teal  { background: rgba(15,110,86,0.12); color: #0F6E56; font-weight: 700; }\n'
    b'#st-main-table td.st-pass.st-tone-navy  { background: rgba(24,95,165,0.12); color: #0C447C; font-weight: 700; }\n'
    b'#st-main-table td.st-fail { color: #999; }\n'
    b'#st-main-table td.name-cell { text-align: left; padding: 4px 4px 4px 8px; line-height: 1.15; }\n'
    b'#st-main-table td.name-cell .co { font-weight: 700; font-size: 11px; color: #2a2a2a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }\n'
    b'#st-main-table td.name-cell .tk { font-size: 9px; color: #999; font-weight: 500; margin-top: 1px; }\n'
    b'#st-main-table td.name-cell .live-dot { color: #2e7d32; font-weight: 700; margin-right: 4px; display: inline-block; vertical-align: middle; line-height: 1; font-size: 10px; }\n'
    b'#st-main-table td.taxon { text-align: left; font-size: 9px; line-height: 1.2; padding: 4px; }\n'
    b'#st-main-table td.taxon .ind { color: #666; font-weight: 500; }\n'
    b'#st-main-table td.taxon .sec { color: #999; }\n'
    b'#st-main-table col.c-name { width: 130px; }\n'
    b'#st-main-table col.c-taxon { width: 150px; }\n'
    b'#st-main-table col.c-price { width: 52px; }\n'
    b'#st-main-table col.c-52wh { width: 50px; }\n'
    b'#st-main-table col.c-pullback { width: 56px; }\n'
    b'#st-main-table col.c-hlow { width: 50px; }\n'
    b'#st-main-table col.c-test { width: 72px; }\n'
    b'#st-main-table tr.tint-row td.name-cell, #st-main-table tr.tint-row td.taxon { background: var(--tint-bg) !important; }\n'
    b'#st-main-table tr.portfolio-band td:last-child { border-right: 4px solid var(--portfolio-color); }\n'
    b'#st-main-table tr.portfolio-tint { background: var(--portfolio-bg); }\n'
    b'#st-main-table tr.portfolio-tint:hover { background: var(--portfolio-bg-hover); }\n'
    b'/* MD-V2-SETUPS-MARKER-CSS-END */\n'
)

TS_CSS = (
    b'\n/* MD-V2-TESTS-MARKER-CSS-START */\n'
    b'#tab-tests .group-captions { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 16px 0 14px 0; }\n'
    b'#tab-tests .group-captions .gcap { background: #fbfaf5; border: 1px solid #e0dcc8; border-left: 3px solid #b08a4e; border-radius: 4px; padding: 10px 12px; font-size: 11px; line-height: 1.45; color: #555; }\n'
    b'#tab-tests .group-captions .gcap b { display: block; margin-bottom: 4px; font-weight: 700; color: #b08a4e; font-size: 11px; letter-spacing: 0.2px; }\n'
    b'#tab-tests .group-captions .gcap-g1 { border-left-color: #BA7517; }\n'
    b'#tab-tests .group-captions .gcap-g1 b { color: #854F0B; }\n'
    b'#tab-tests .group-captions .gcap-g2 { border-left-color: #0F6E56; }\n'
    b'#tab-tests .group-captions .gcap-g2 b { color: #0F6E56; }\n'
    b'#tab-tests .group-captions .gcap-g3 { border-left-color: #185FA5; }\n'
    b'#tab-tests .group-captions .gcap-g3 b { color: #0C447C; }\n'
    b'\n'
    b'#tab-tests .s1-rating-tiles { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }\n'
    b'#tab-tests .s1-rating-tiles .ts-tile-amber { background: rgba(186,117,23,0.10); border: 1px solid rgba(186,117,23,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }\n'
    b'#tab-tests .s1-rating-tiles .ts-tile-teal  { background: rgba(15,110,86,0.10); border: 1px solid rgba(15,110,86,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }\n'
    b'#tab-tests .s1-rating-tiles .ts-tile-navy  { background: rgba(24,95,165,0.10); border: 1px solid rgba(24,95,165,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }\n'
    b'#tab-tests .s1-rating-tiles .ts-tile-amber.active { background: rgba(186,117,23,0.22); border: 1.5px solid #BA7517; }\n'
    b'#tab-tests .s1-rating-tiles .ts-tile-teal.active  { background: rgba(15,110,86,0.22); border: 1.5px solid #0F6E56; }\n'
    b'#tab-tests .s1-rating-tiles .ts-tile-navy.active  { background: rgba(24,95,165,0.22); border: 1.5px solid #185FA5; }\n'
    b'#tab-tests .s1-rating-tiles .ts-strip-amber { background: #BA7517; height: 4px; margin-top: 6px; border-radius: 2px; }\n'
    b'#tab-tests .s1-rating-tiles .ts-strip-teal  { background: #0F6E56; height: 4px; margin-top: 6px; border-radius: 2px; }\n'
    b'#tab-tests .s1-rating-tiles .ts-strip-navy  { background: #185FA5; height: 4px; margin-top: 6px; border-radius: 2px; }\n'
    b'\n'
    b'#ts-main-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 11px; table-layout: fixed; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }\n'
    b'#ts-main-table thead { position: sticky; top: 0; z-index: 50; background: #fbfaf5; box-shadow: 0 2px 4px rgba(0,0,0,0.06); }\n'
    b'#ts-main-table thead th { background: #fbfaf5 !important; border-bottom: 1px solid #e0dcc8; padding: 7px 3px; text-align: center; font-weight: 600; font-size: 10px; color: #666; cursor: pointer; user-select: none; line-height: 1.25; vertical-align: middle; }\n'
    b'#ts-main-table thead th:hover { background: #f0ebd9 !important; }\n'
    b'#ts-main-table thead .group-header-row th { background: #f3efe2 !important; font-size: 9px; text-transform: uppercase; font-weight: 700; letter-spacing: 0.4px; padding: 5px 3px; cursor: default; line-height: 1.25; }\n'
    b'#ts-main-table thead tr.group-header-row th { position: sticky; top: 0; }\n'
    b'#ts-main-table thead tr.col-header-row th { position: sticky; top: 28px; border-top: 1px solid #e0dcc8; }\n'
    b'#ts-main-table thead .gh-inputs { color: #555; }\n'
    b'#ts-main-table thead .gh-g1 { color: #854F0B; }\n'
    b'#ts-main-table thead .gh-g2 { color: #0F6E56; }\n'
    b'#ts-main-table thead .gh-g3 { color: #0C447C; }\n'
    b'#ts-main-table .hd { display: inline-flex; align-items: center; justify-content: center; gap: 3px; width: 100%; }\n'
    b'#ts-main-table .hd .lbl { white-space: normal; word-break: break-word; }\n'
    b'#ts-main-table .hd .sort-arrow { font-size: 9px; color: #0F6E56; flex: 0 0 auto; line-height: 1; }\n'
    b'#ts-main-table .hd .sort-placeholder { width: 9px; flex: 0 0 auto; }\n'
    b'#ts-main-table td { padding: 5px 4px; border-bottom: 1px solid #efece0; text-align: center; vertical-align: middle; height: 38px; box-sizing: border-box; font-variant-numeric: tabular-nums; }\n'
    b'#ts-main-table tr:hover { background: rgba(15,110,86,0.04); }\n'
    b'#ts-main-table td.grp-start-g1, #ts-main-table th.grp-start-g1 { border-left: 2px solid rgba(186,117,23,0.40); }\n'
    b'#ts-main-table td.grp-end-g1,   #ts-main-table th.grp-end-g1   { border-right: 2px solid rgba(186,117,23,0.40); }\n'
    b'#ts-main-table td.grp-start-g2, #ts-main-table th.grp-start-g2 { border-left: 2px solid rgba(15,110,86,0.40); }\n'
    b'#ts-main-table td.grp-end-g2,   #ts-main-table th.grp-end-g2   { border-right: 2px solid rgba(15,110,86,0.40); }\n'
    b'#ts-main-table td.grp-start-g3, #ts-main-table th.grp-start-g3 { border-left: 2px solid rgba(24,95,165,0.40); }\n'
    b'#ts-main-table td.grp-end-g3,   #ts-main-table th.grp-end-g3   { border-right: 2px solid rgba(24,95,165,0.40); }\n'
    b'#ts-main-table td.ts-pass.ts-tone-amber { background: rgba(186,117,23,0.12); color: #854F0B; font-weight: 700; }\n'
    b'#ts-main-table td.ts-pass.ts-tone-teal  { background: rgba(15,110,86,0.12); color: #0F6E56; font-weight: 700; }\n'
    b'#ts-main-table td.ts-pass.ts-tone-navy  { background: rgba(24,95,165,0.12); color: #0C447C; font-weight: 700; }\n'
    b'#ts-main-table td.ts-fail { color: #999; }\n'
    b'#ts-main-table td.name-cell { text-align: left; padding: 4px 4px 4px 8px; line-height: 1.15; }\n'
    b'#ts-main-table td.name-cell .co { font-weight: 700; font-size: 11px; color: #2a2a2a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }\n'
    b'#ts-main-table td.name-cell .tk { font-size: 9px; color: #999; font-weight: 500; margin-top: 1px; }\n'
    b'#ts-main-table td.name-cell .live-dot { color: #2e7d32; font-weight: 700; margin-right: 4px; display: inline-block; vertical-align: middle; line-height: 1; font-size: 10px; }\n'
    b'#ts-main-table td.taxon { text-align: left; font-size: 9px; line-height: 1.2; padding: 4px; }\n'
    b'#ts-main-table td.taxon .ind { color: #666; font-weight: 500; }\n'
    b'#ts-main-table td.taxon .sec { color: #999; }\n'
    b'#ts-main-table col.c-name { width: 130px; }\n'
    b'#ts-main-table col.c-taxon { width: 150px; }\n'
    b'#ts-main-table col.c-price { width: 52px; }\n'
    b'#ts-main-table col.c-hlow { width: 50px; }\n'
    b'#ts-main-table col.c-vol { width: 56px; }\n'
    b'#ts-main-table col.c-vcpstg { width: 60px; }\n'
    b'#ts-main-table col.c-pbstg { width: 60px; }\n'
    b'#ts-main-table col.c-utrstg { width: 60px; }\n'
    b'#ts-main-table col.c-test { width: 92px; }\n'
    b'#ts-main-table tr.tint-row td.name-cell, #ts-main-table tr.tint-row td.taxon { background: var(--tint-bg) !important; }\n'
    b'/* MD-V2-TESTS-MARKER-CSS-END */\n'
)


def replace_one(src, anchor, replacement, label):
    a_lf = anchor
    a_crlf = anchor.replace(b'\n', b'\r\n').replace(b'\r\r\n', b'\r\n')
    r_lf = replacement
    r_crlf = replacement.replace(b'\n', b'\r\n').replace(b'\r\r\n', b'\r\n')
    n_lf = src.count(a_lf)
    n_crlf = src.count(a_crlf) if a_crlf != a_lf else 0
    if n_lf == 1: return src.replace(a_lf, r_lf, 1)
    if n_crlf == 1: return src.replace(a_crlf, r_crlf, 1)
    fail("Anchor [" + label + "] count = (LF " + str(n_lf) + ", CRLF " + str(n_crlf) + "). Expected 1.")


def main():
    check_fuse_environment()
    print("[pi-po-setups-tests] working dir: " + str(SCRIPT_DIR))
    if not DASH_PY.exists(): fail("build_dashboard.py not found")
    for m in [PI_MODULE, PO_MODULE, ST_MODULE, TS_MODULE]:
        if not m.exists(): fail(str(m.name) + " not found")

    src = DASH_PY.read_bytes()
    orig_size = len(src)
    pi_mod = PI_MODULE.read_bytes()
    po_mod = PO_MODULE.read_bytes()
    st_mod = ST_MODULE.read_bytes()
    ts_mod = TS_MODULE.read_bytes()

    print("[pi-po-setups-tests] build_dashboard.py: " + str(orig_size))
    print("[pi-po-setups-tests] PI: " + str(len(pi_mod)) + " | PO: " + str(len(po_mod)) + " | ST: " + str(len(st_mod)) + " | TS: " + str(len(ts_mod)))

    # Pre-flight
    if PI_MARKER not in src: fail("PI marker missing - prerequisite patcher not run")
    if PO_MARKER not in src: fail("PO marker missing - prerequisite patcher not run")
    if ST_MARKER in src: fail("Setups marker already present")
    if TS_MARKER in src: fail("Tests marker already present")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = DASH_PY.with_suffix(".py.bak-pre-pi-po-setups-tests-" + ts)
    shutil.copy2(DASH_PY, bak)
    print("[pi-po-setups-tests] backup: " + bak.name)

    # ===== (A) Replace PI module body =====
    pi_start = b'/* MD-V2-PRE-INDICATORS-MARKER-MODULE-START */'
    pi_end   = b'/* MD-V2-PRE-INDICATORS-MARKER-MODULE-END */'
    s_start = src.find(pi_start)
    s_end_pos = src.find(pi_end)
    if s_start < 0 or s_end_pos < 0: fail("PI module markers missing")
    pi_block = pi_start + b'\n' + pi_mod + b'\n' + pi_end
    src = src[:s_start] + pi_block + src[s_end_pos + len(pi_end):]
    print("[pi-po-setups-tests]   (A) PI module body replaced")

    # ===== (B) Replace PO module body =====
    po_start = b'/* MD-V2-POST-INDICATORS-MARKER-MODULE-START */'
    po_end   = b'/* MD-V2-POST-INDICATORS-MARKER-MODULE-END */'
    s_start = src.find(po_start)
    s_end_pos = src.find(po_end)
    if s_start < 0 or s_end_pos < 0: fail("PO module markers missing")
    po_block = po_start + b'\n' + po_mod + b'\n' + po_end
    src = src[:s_start] + po_block + src[s_end_pos + len(po_end):]
    print("[pi-po-setups-tests]   (B) PO module body replaced")

    # ===== (C) SETUPS tab end-to-end =====
    # C1 OLD_TABS entry (drives host div)
    src = replace_one(
        src,
        b'    # MD-V2-POST-INDICATORS-MARKER - Post-indicators (5 trailing binary patterns)\n'
        b'    {"id": "post_indicators", "label": "Post-indicators", "accent": "#A32D2D"},\n',
        b'    # MD-V2-POST-INDICATORS-MARKER - Post-indicators (5 trailing binary patterns)\n'
        b'    {"id": "post_indicators", "label": "Post-indicators", "accent": "#A32D2D"},\n'
        b'    # MD-V2-SETUPS-MARKER - Setups (4 capital-deployment-eligibility patterns)\n'
        b'    {"id": "setups", "label": "Setups", "accent": "#BA7517"},\n',
        "Setups OLD_TABS"
    )
    print("[pi-po-setups-tests]   (C1) Setups OLD_TABS entry added")

    # C2 V2 nav button
    src = replace_one(
        src,
        b'      + \'<span class="v2-nav-placeholder" title="Coming soon">Setups</span>\'\n',
        b'      + \'<button class="v2-nav-btn" data-v2-tab="setups" onclick="switchTab(\\\'setups\\\')">Setups</button>\'\n',
        "Setups nav button"
    )
    print("[pi-po-setups-tests]   (C2) Setups V2-nav button wired")

    # C3 IMPLEMENTED_TABS
    src = replace_one(
        src,
        b'    "post_indicators",  # MD-V2-POST-INDICATORS-MARKER\n'
        b'    "mm99", "bp", "pb", "utr", "vcp", "tech", "combos", "changes", "positions",\n',
        b'    "post_indicators",  # MD-V2-POST-INDICATORS-MARKER\n'
        b'    "setups",  # MD-V2-SETUPS-MARKER\n'
        b'    "mm99", "bp", "pb", "utr", "vcp", "tech", "combos", "changes", "positions",\n',
        "Setups IMPL"
    )
    print("[pi-po-setups-tests]   (C3) Setups IMPLEMENTED_TABS entry added")

    # C4 renderTab dispatch
    src = replace_one(
        src,
        b'  else if(id==="post_indicators")renderPostIndicators();  /* MD-V2-POST-INDICATORS-MARKER */\n',
        b'  else if(id==="post_indicators")renderPostIndicators();  /* MD-V2-POST-INDICATORS-MARKER */\n'
        b'  else if(id==="setups")renderSetups();  /* MD-V2-SETUPS-MARKER */\n',
        "Setups renderTab dispatch"
    )
    print("[pi-po-setups-tests]   (C4) Setups dispatch wired")

    # C5 Module + CSS
    po_module_end = src.rfind(po_end)
    if po_module_end < 0: fail("PO module END marker missing")
    st_block = (
        b'\n/* MD-V2-SETUPS-MARKER-MODULE-START */\n'
        + st_mod
        + b'\n/* MD-V2-SETUPS-MARKER-MODULE-END */\n'
    )
    insertion_point = po_module_end + len(po_end)
    src = src[:insertion_point] + st_block + src[insertion_point:]
    print("[pi-po-setups-tests]   (C5a) Setups module inlined")

    # Inject Setups CSS at end of PO CSS block
    po_css_end = b'/* MD-V2-POST-INDICATORS-MARKER-CSS-END */'
    po_css_end_pos = src.rfind(po_css_end)
    if po_css_end_pos < 0: fail("PO CSS END marker missing")
    insertion_point = po_css_end_pos + len(po_css_end)
    src = src[:insertion_point] + ST_CSS + src[insertion_point:]
    print("[pi-po-setups-tests]   (C5b) Setups CSS injected")

    # ===== (D) TESTS tab end-to-end =====
    # D1 OLD_TABS
    src = replace_one(
        src,
        b'    # MD-V2-SETUPS-MARKER - Setups (4 capital-deployment-eligibility patterns)\n'
        b'    {"id": "setups", "label": "Setups", "accent": "#BA7517"},\n',
        b'    # MD-V2-SETUPS-MARKER - Setups (4 capital-deployment-eligibility patterns)\n'
        b'    {"id": "setups", "label": "Setups", "accent": "#BA7517"},\n'
        b'    # MD-V2-TESTS-MARKER - Capital qualification tests (3 tests)\n'
        b'    {"id": "tests", "label": "Tests", "accent": "#0F6E56"},\n',
        "Tests OLD_TABS"
    )
    print("[pi-po-setups-tests]   (D1) Tests OLD_TABS entry added")

    # D2 V2 nav button (note: original placeholder label was "Tests")
    src = replace_one(
        src,
        b'      + \'<span class="v2-nav-placeholder" title="Coming soon">Tests</span>\'\n',
        b'      + \'<button class="v2-nav-btn" data-v2-tab="tests" onclick="switchTab(\\\'tests\\\')">Tests</button>\'\n',
        "Tests nav button"
    )
    print("[pi-po-setups-tests]   (D2) Tests V2-nav button wired")

    # D3 IMPLEMENTED_TABS
    src = replace_one(
        src,
        b'    "setups",  # MD-V2-SETUPS-MARKER\n'
        b'    "mm99", "bp", "pb", "utr", "vcp", "tech", "combos", "changes", "positions",\n',
        b'    "setups",  # MD-V2-SETUPS-MARKER\n'
        b'    "tests",  # MD-V2-TESTS-MARKER\n'
        b'    "mm99", "bp", "pb", "utr", "vcp", "tech", "combos", "changes", "positions",\n',
        "Tests IMPL"
    )
    print("[pi-po-setups-tests]   (D3) Tests IMPLEMENTED_TABS entry added")

    # D4 renderTab dispatch
    src = replace_one(
        src,
        b'  else if(id==="setups")renderSetups();  /* MD-V2-SETUPS-MARKER */\n',
        b'  else if(id==="setups")renderSetups();  /* MD-V2-SETUPS-MARKER */\n'
        b'  else if(id==="tests")renderCapTests();  /* MD-V2-TESTS-MARKER */\n',
        "Tests renderTab dispatch"
    )
    print("[pi-po-setups-tests]   (D4) Tests dispatch wired")

    # D5 Module + CSS
    st_module_end = src.rfind(b'/* MD-V2-SETUPS-MARKER-MODULE-END */')
    if st_module_end < 0: fail("Setups module END marker missing")
    ts_block = (
        b'\n/* MD-V2-TESTS-MARKER-MODULE-START */\n'
        + ts_mod
        + b'\n/* MD-V2-TESTS-MARKER-MODULE-END */\n'
    )
    insertion_point = st_module_end + len(b'/* MD-V2-SETUPS-MARKER-MODULE-END */')
    src = src[:insertion_point] + ts_block + src[insertion_point:]
    print("[pi-po-setups-tests]   (D5a) Tests module inlined")

    st_css_end = b'/* MD-V2-SETUPS-MARKER-CSS-END */'
    st_css_end_pos = src.rfind(st_css_end)
    if st_css_end_pos < 0: fail("Setups CSS END marker missing")
    insertion_point = st_css_end_pos + len(st_css_end)
    src = src[:insertion_point] + TS_CSS + src[insertion_point:]
    print("[pi-po-setups-tests]   (D5b) Tests CSS injected")

    # ===== Chrome scope broadening already handles setups + tests (done earlier) =====

    # Atomic write + py_compile
    tmp = DASH_PY.with_suffix(".py.tmp-" + ts)
    tmp.write_bytes(src)
    try:
        py_compile.compile(str(tmp), doraise=True)
    except py_compile.PyCompileError as e:
        tmp.unlink(missing_ok=True)
        fail("py_compile failed: " + str(e))
    os.replace(str(tmp), str(DASH_PY))
    new_size = DASH_PY.stat().st_size
    print("[pi-po-setups-tests] OK. New size: " + str(new_size) + " (delta " + str(new_size - orig_size) + ")")

    final = DASH_PY.read_bytes()
    print('[pi-po-setups-tests] markers: PI=' + str(final.count(PI_MARKER)) + ' PO=' + str(final.count(PO_MARKER)) + ' ST=' + str(final.count(ST_MARKER)) + ' TS=' + str(final.count(TS_MARKER)))
    print('[pi-po-setups-tests] V2 nav: setups=' + str(b'data-v2-tab="setups"' in final) + ' tests=' + str(b'data-v2-tab="tests"' in final))
    print("[pi-po-setups-tests] DONE. Next: python scripts\\build_dashboard.py")


if __name__ == "__main__":
    main()
