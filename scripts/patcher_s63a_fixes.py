"""
=============================================================================
PATCHER — S63a Three SSP Bug Fixes
=============================================================================
Session: S63a (21-May-2026)

BUG 1: Header hidden
  .ssp-overlay used inset:0, covering the fixed main dashboard header.
  Fix: top:var(--header-height) so the overlay starts below the header.

BUG 2: Chart never loads
  loadChartData() is defined inside the main JS IIFE — not on window.
  The SSP IIFE (separate scope) gets a silent ReferenceError when it calls
  loadChartData(), so the callback never fires and the spinner hangs forever.
  Fix: expose window.loadChartData = loadChartData inside the main IIFE,
       and also expose window._dashChartZoom getter for zoom sync.
       Update SSP to call window.loadChartData safely.

BUG 3: Healthy Retest uses wrong data key
  SSP was using tests.healthy_retest (13-test composite, rating=None for
  most stocks) instead of tests.ma_retest_upwards (8-test deployment test,
  the key used by the Overview tab for "MA retest").
  Fix: change SSP key from 'healthy_retest' to 'ma_retest_upwards'.
=============================================================================
"""
from __future__ import annotations
import os, sys, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.normpath(os.path.join(HERE, "build_dashboard.py"))


def must_replace(text, old, new, label):
    n = text.count(old)
    if n != 1:
        sys.stderr.write("ERROR: anchor '{}' found {} times (expected 1).\n".format(label, n))
        sys.stderr.write("First 120 chars of anchor: {}\n".format(repr(old[:120])))
        sys.exit(2)
    return text.replace(old, new, 1)


with open(TARGET, 'r', encoding='utf-8') as f:
    src = f.read()

print("MD5 before: {}".format(hashlib.md5(src.encode()).hexdigest()))

# ===========================================================================
# FIX 1: CSS — overlay starts below main header, not at top:0
# ===========================================================================
src = must_replace(
    src,
    '.ssp-overlay{position:fixed;inset:0;z-index:9900;',
    '.ssp-overlay{position:fixed;top:var(--header-height);left:0;right:0;bottom:0;z-index:9900;',
    'FIX1 ssp-overlay CSS inset'
)
print("[fix 1] Header visibility: overlay now starts at --header-height")

# ===========================================================================
# FIX 2a: Expose loadChartData + chartZoom getter inside main IIFE
# ===========================================================================
OLD_EXPOSE = "window.TAB_LABELS = TAB_LABELS;\n})();  /* close main IIFE */"
NEW_EXPOSE = (
    "window.TAB_LABELS = TAB_LABELS;\n"
    "/* MD-V2-S63A: expose chart loader + zoom for SSP overlay */\n"
    "window.loadChartData = loadChartData;\n"
    "window._dashChartZoom = function(){ return chartZoom; };\n"
    "})();  /* close main IIFE */"
)
src = must_replace(src, OLD_EXPOSE, NEW_EXPOSE, "FIX2a expose loadChartData")
print("[fix 2a] loadChartData exposed on window")

# ===========================================================================
# FIX 2b: SSP calls window.loadChartData safely (not bare loadChartData)
# ===========================================================================
OLD_LOAD_CALL = "  loadChartData(ticker, function(data){"
NEW_LOAD_CALL = (
    "  var _lc = window.loadChartData;\n"
    "  if(!_lc){ loading.textContent='Chart loader unavailable'; return; }\n"
    "  _lc(ticker, function(data){"
)
src = must_replace(src, OLD_LOAD_CALL, NEW_LOAD_CALL, "FIX2b SSP loadChartData call")
print("[fix 2b] SSP uses window.loadChartData with null guard")

# Also update chartZoom reference in _sspDrawChart to use the getter
OLD_ZOOM = "  var zoom = (typeof chartZoom !== 'undefined') ? chartZoom : '1Y';"
NEW_ZOOM = "  var zoom = (typeof window._dashChartZoom === 'function') ? window._dashChartZoom() : '1Y';"
src = must_replace(src, OLD_ZOOM, NEW_ZOOM, "FIX2c SSP chartZoom via getter")
print("[fix 2c] SSP reads chartZoom via window._dashChartZoom()")

# ===========================================================================
# FIX 3: Healthy Retest — use ma_retest_upwards (Overview key), not healthy_retest
# ===========================================================================
OLD_HR_RATING = "  var hrO=_sspTestRating(md2,'healthy_retest'),   hrC=_sspTestCount(md2,'healthy_retest');"
NEW_HR_RATING = "  var hrO=_sspTestRating(md2,'ma_retest_upwards'), hrC=_sspTestCount(md2,'ma_retest_upwards');"
src = must_replace(src, OLD_HR_RATING, NEW_HR_RATING, "FIX3 Healthy Retest key")
print("[fix 3] Healthy Retest key: healthy_retest → ma_retest_upwards")

# ===========================================================================
# Write
# ===========================================================================
import tempfile, shutil
tmp = TARGET + '.s63a-tmp'
with open(tmp, 'w', encoding='utf-8') as f:
    f.write(src)
with open(tmp, 'r', encoding='utf-8') as f:
    verify = f.read()
if hashlib.md5(verify.encode()).hexdigest() != hashlib.md5(src.encode()).hexdigest():
    sys.stderr.write("ERROR: write verify failed\n"); sys.exit(3)
shutil.move(tmp, TARGET)

print("MD5 after:  {}".format(hashlib.md5(src.encode()).hexdigest()))
print("[done] S63a fixes applied. {} bytes written.".format(len(src.encode())))
print("Next: python scripts/build_dashboard.py")
