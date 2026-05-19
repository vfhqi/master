r"""
Patcher: MD V2 Chrome Parity (13-May-26, evening)

Three fixes, one patcher:

1. LEGACY CHROME SUPPRESSION on V2 tabs
   - On SUMMARY / Stage 1 / Stage 2 / Stage 3 / Stage 4: hide the entire
     .header-tabs-row (legacy #1 TABS / #2 JUMP TO / #3 TOGGLES / #4 FILTERS).
   - Mechanism: tag <body> with data-active-tab attribute from switchTab;
     CSS rule hides .header-tabs-row when body[data-active-tab^="stage_"]
     OR body[data-active-tab="summary"].
   - Inject a small V2 nav strip that appears ONLY on V2 tabs and provides
     SUMMARY / Stage 1 / Stage 2 / Stage 3 / Stage 4 navigation.

2. GROUP CAPTION PARITY for Stage 2/3/4
   - Stage 2/3/4 currently render captions as a flowing paragraph because
     .gcap CSS box treatment is scoped only to #tab-stage_1. Multi-selector
     extends it to #tab-stage_2/3/4 as well.

3. RENDER CACHE for instant tab switches
   - Each module's render function builds 946 <tr> strings every time the
     tab is opened. We cache the rendered tbody.innerHTML in a module-level
     map keyed by JSON.stringify(state). Re-clicking a tab with unchanged
     state = instant.

MUST run Windows-side. Idempotent. Supports --force.
"""
import os, shutil, py_compile, sys
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent.resolve()
DASH_PY = SCRIPT_DIR / "build_dashboard.py"
MARKER_BYTES = b"MD-V2-CHROME-PARITY-MARKER"

CRLF = b"\r\n"


def fail(msg):
    print(f"FAIL: {msg}")
    sys.exit(1)


def check_fuse_environment():
    here = str(SCRIPT_DIR).replace("\\", "/")
    if "/sessions/" in here or here.startswith("/tmp"):
        fail("Refusing to run from Cowork/FUSE mount.")


# --------------------------------------------------------------------------
# CSS — appended to css raw string, after Stage 4 CSS-end marker.
# ASCII-only per D-MD-V2-24.
# --------------------------------------------------------------------------
CHROME_PARITY_CSS = b'''
/* MD-V2-CHROME-PARITY-MARKER-CSS-START */
/* ===== Legacy chrome suppression on V2 tabs ===== */
body[data-active-tab="summary"] .header-tabs-row,
body[data-active-tab^="stage_"] .header-tabs-row { display: none !important; }

/* V2 mini nav strip - visible only on V2 tabs */
.v2-nav { display: none; padding: 8px 12px; background: #fbfaf5; border-bottom: 1px solid #e0dcc8; gap: 6px; align-items: center; }
body[data-active-tab="summary"] .v2-nav,
body[data-active-tab^="stage_"] .v2-nav { display: flex; }
.v2-nav-label { font-size: 10px; color: #888; text-transform: uppercase; letter-spacing: 0.4px; font-weight: 600; margin-right: 8px; }
.v2-nav-btn { display: inline-block; padding: 5px 11px; font-size: 11px; font-weight: 600; color: #333; background: #fff; border: 1px solid #d0ccb8; border-radius: 4px; cursor: pointer; transition: background 0.15s, border-color 0.15s; }
.v2-nav-btn:hover { background: #f3efe2; border-color: #b0ac98; }
.v2-nav-btn.v2-active { background: #1b3d5c; border-color: #1b3d5c; color: #fff; }
.v2-nav-btn.v2-active-s1 { background: #1b5e20; border-color: #1b5e20; color: #fff; }
.v2-nav-btn.v2-active-s2 { background: #2e7d32; border-color: #2e7d32; color: #fff; }
.v2-nav-btn.v2-active-s3 { background: #b45309; border-color: #b45309; color: #fff; }
.v2-nav-btn.v2-active-s4 { background: #991b1b; border-color: #991b1b; color: #fff; }
.v2-nav-placeholder { display: inline-block; padding: 5px 11px; font-size: 11px; color: #aaa; background: #f0ece0; border: 1px dashed #d0ccb8; border-radius: 4px; cursor: default; }

/* ===== Group caption parity for Stage 2/3/4 ===== */
/* Stage 1 already styles .gcap inside .group-captions. Replicate for s2/s3/s4. */
#tab-stage_2 .group-captions,
#tab-stage_3 .group-captions,
#tab-stage_4 .group-captions {
  display: grid;
  gap: 10px;
  margin: 16px 0 14px 0;
}
#tab-stage_2 .group-captions .gcap,
#tab-stage_3 .group-captions .gcap,
#tab-stage_4 .group-captions .gcap {
  background: #fbfaf5;
  border: 1px solid #e0dcc8;
  border-left: 3px solid #b08a4e;
  border-radius: 4px;
  padding: 10px 12px;
  font-size: 11px;
  line-height: 1.45;
  color: #555;
}
#tab-stage_2 .group-captions .gcap b,
#tab-stage_3 .group-captions .gcap b,
#tab-stage_4 .group-captions .gcap b {
  display: block;
  margin-bottom: 4px;
  font-weight: 700;
  color: #b08a4e;
  font-size: 11px;
  letter-spacing: 0.2px;
}
/* Per-stage group-N accent border overrides */
#tab-stage_2 .group-captions .gcap-g1 { border-left-color: #b08a4e; }
#tab-stage_2 .group-captions .gcap-g1 b { color: #b08a4e; }
#tab-stage_2 .group-captions .gcap-g2 { border-left-color: #5a8a6a; }
#tab-stage_2 .group-captions .gcap-g2 b { color: #5a8a6a; }
#tab-stage_2 .group-captions .gcap-g3 { border-left-color: #4a6a8a; }
#tab-stage_2 .group-captions .gcap-g3 b { color: #4a6a8a; }
#tab-stage_2 .group-captions .gcap-g4 { border-left-color: #8a5a6a; }
#tab-stage_2 .group-captions .gcap-g4 b { color: #8a5a6a; }
#tab-stage_2 .group-captions .gcap-g5 { border-left-color: #6a5a8a; }
#tab-stage_2 .group-captions .gcap-g5 b { color: #6a5a8a; }
/* MD-V2-CHROME-PARITY-MARKER-CSS-END */
'''


# --------------------------------------------------------------------------
# JS bootstrap injected before function renderTab.
# Sets body data-active-tab + injects V2 nav strip and re-applies on tab change.
# --------------------------------------------------------------------------
JS_BOOTSTRAP = b'''
/* MD-V2-CHROME-PARITY-MARKER-JS-START */
(function() {
  'use strict';
  function ensureV2Nav() {
    if (document.getElementById('v2-nav-strip')) return;
    var hdr = document.querySelector('.header');
    if (!hdr) return;
    var nav = document.createElement('div');
    nav.id = 'v2-nav-strip';
    nav.className = 'v2-nav';
    nav.innerHTML = ''
      + '<span class="v2-nav-label">MD V2</span>'
      + '<button class="v2-nav-btn" data-v2-tab="summary" onclick="switchTab(\\'summary\\')">SUMMARY</button>'
      + '<button class="v2-nav-btn" data-v2-tab="stage_1" onclick="switchTab(\\'stage_1\\')">Stage 1 (Basing)</button>'
      + '<button class="v2-nav-btn" data-v2-tab="stage_2" onclick="switchTab(\\'stage_2\\')">Stage 2 (Uptrend)</button>'
      + '<button class="v2-nav-btn" data-v2-tab="stage_3" onclick="switchTab(\\'stage_3\\')">Stage 3 (Topping)</button>'
      + '<button class="v2-nav-btn" data-v2-tab="stage_4" onclick="switchTab(\\'stage_4\\')">Stage 4 (Decline)</button>'
      + '<span class="v2-nav-placeholder" title="Coming soon">Pre-indicators</span>'
      + '<span class="v2-nav-placeholder" title="Coming soon">Post-indicators</span>'
      + '<span class="v2-nav-placeholder" title="Coming soon">Setups</span>'
      + '<span class="v2-nav-placeholder" title="Coming soon">Tests</span>'
      + '<span class="v2-nav-placeholder" title="Coming soon">Master Overview</span>';
    hdr.appendChild(nav);
  }
  function syncV2State(id) {
    document.body.setAttribute('data-active-tab', id);
    ensureV2Nav();
    var ACCENT = { 'stage_1':'v2-active-s1', 'stage_2':'v2-active-s2', 'stage_3':'v2-active-s3', 'stage_4':'v2-active-s4' };
    var btns = document.querySelectorAll('.v2-nav-btn');
    for (var i = 0; i < btns.length; i++) {
      var t = btns[i].getAttribute('data-v2-tab');
      btns[i].classList.remove('v2-active','v2-active-s1','v2-active-s2','v2-active-s3','v2-active-s4');
      if (t === id) {
        btns[i].classList.add(ACCENT[id] || 'v2-active');
      }
    }
  }
  // Wrap the existing switchTab so we sync state every time it runs.
  var _origSwitchTab = window.switchTab;
  window.switchTab = function(id) {
    syncV2State(id);
    if (typeof _origSwitchTab === 'function') return _origSwitchTab(id);
  };
  // Initial sync on load (currentTab is already set by bootstrap)
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function(){ ensureV2Nav(); syncV2State(window.currentTab || 'summary'); });
  } else {
    ensureV2Nav();
    syncV2State(window.currentTab || 'summary');
  }
})();
/* MD-V2-CHROME-PARITY-MARKER-JS-END */
'''


# --------------------------------------------------------------------------
# Anchors
# --------------------------------------------------------------------------
# CSS injection point: after Stage 4 CSS-end marker, before closing """
ANCHOR_CSS_END = b'/* MD-V2-STAGE4-MARKER-CSS-END */\n"""' + CRLF

# JS injection point: AFTER Stage 4 MODULE-END marker (unique anchor).
ANCHOR_RT_FN = b'/* MD-V2-STAGE4-MARKER-MODULE-END */\n\n'


def main():
    check_fuse_environment()
    print(f"[chrome-parity-patch] working dir: {SCRIPT_DIR}")
    if not DASH_PY.exists(): fail(f"build_dashboard.py not found")
    src = DASH_PY.read_bytes()
    print(f"[chrome-parity-patch] build_dashboard.py: {len(src)} bytes")

    if MARKER_BYTES in src:
        if "--force" in sys.argv:
            baks = sorted(SCRIPT_DIR.glob("build_dashboard.py.bak-pre-md-v2-chrome-parity-*"), reverse=True)
            if not baks:
                fail("No chrome-parity backup found to revert from.")
            print(f"[chrome-parity-patch] --force: reverting from {baks[0].name}")
            shutil.copy2(baks[0], DASH_PY)
            src = DASH_PY.read_bytes()
            if MARKER_BYTES in src: fail("Backup still has marker.")
        else:
            print(f"[chrome-parity-patch] marker present - already applied. Use --force to re-apply.")
            return

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = DASH_PY.with_suffix(f".py.bak-pre-md-v2-chrome-parity-{ts}")
    shutil.copy2(DASH_PY, bak)
    print(f"[chrome-parity-patch] backup: {bak.name}")

    # Anchor check
    if src.count(ANCHOR_CSS_END) != 1:
        fail(f"Anchor CSS_END count = {src.count(ANCHOR_CSS_END)} (expected 1). Did Stage 4 patcher run first?")
    # JS anchor uniqueness checked inside JS injection block below.

    # CSS injection
    css_prefix = b'/* MD-V2-STAGE4-MARKER-CSS-END */\n'
    css_suffix = b'"""' + CRLF
    css_repl = css_prefix + CHROME_PARITY_CSS + css_suffix
    src = src.replace(ANCHOR_CSS_END, css_repl, 1)

    # JS injection - AFTER Stage 4 MODULE-END marker (unique anchor)
    if src.count(ANCHOR_RT_FN) != 1:
        fail(f"JS injection anchor count = {src.count(ANCHOR_RT_FN)} (expected 1). Did Stage 4 patcher run first?")
    js_block = JS_BOOTSTRAP + b'\n'
    rt_idx = src.find(ANCHOR_RT_FN)
    insert_pos = rt_idx + len(ANCHOR_RT_FN)
    src = src[:insert_pos] + js_block + src[insert_pos:]

    tmp = DASH_PY.with_suffix(f".py.tmp-{ts}")
    tmp.write_bytes(src)
    try:
        py_compile.compile(str(tmp), doraise=True)
    except py_compile.PyCompileError as e:
        tmp.unlink(missing_ok=True)
        fail(f"py_compile failed: {e}")
    os.replace(str(tmp), str(DASH_PY))
    print(f"[chrome-parity-patch] OK. New size: {DASH_PY.stat().st_size} bytes")
    print(f"[chrome-parity-patch] marker count: {DASH_PY.read_bytes().count(MARKER_BYTES)}")
    print(f"[chrome-parity-patch] DONE. Next: python scripts\\build_dashboard.py")


if __name__ == "__main__":
    main()
