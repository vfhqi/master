#!/usr/bin/env python3
"""
patch_ssp_s64d.py — F16: fix SSP chartZoom scope isolation
F16a: expose window._dashSetChartZoom setter (alongside existing getter at IIFE close)
F16b: sspRenderChart — use window._sspChartZoom||252 instead of bare chartZoom
F16c: sspSetChartZoom — update window._sspChartZoom AND call _dashSetChartZoom(string)
      so drawMasterChart inside the IIFE sees the correct zoom level
"""
import hashlib, os, sys

COWORK   = "/sessions/friendly-charming-lamport/mnt/COWORK"
OUT_PATH = f"{COWORK}/master-dashboard/scripts/build_dashboard.py"

def log(msg): print(f"[patch-d] {msg}", flush=True)

log("Reading current FUSE file...")
with open(OUT_PATH, "r", encoding="utf-8") as f:
    src = f.read()
orig_len = len(src)
log(f"Read {orig_len:,} bytes")

failures = []
def patch(src, old, new, tag):
    if old not in src:
        failures.append(tag)
        log(f"  !! NOT FOUND: {tag}")
        return src
    count = src.count(old)
    if count > 1:
        failures.append(tag)
        log(f"  !! AMBIGUOUS ({count}): {tag}")
        return src
    log(f"  ok  {tag}")
    return src.replace(old, new, 1)

# F16a — add _dashSetChartZoom setter at IIFE close (alongside existing getter)
OLD_GETTER = "window._dashChartZoom = function(){ return chartZoom; };"
NEW_GETTER_AND_SETTER = (
    "window._dashChartZoom = function(){ return chartZoom; };\n"
    "window._dashSetChartZoom = function(z){ chartZoom=z; };"
)
src = patch(src, OLD_GETTER, NEW_GETTER_AND_SETTER,
            "F16a: add _dashSetChartZoom setter at IIFE close")

# F16b — sspRenderChart: replace bare `chartZoom` lookup with safe window._sspChartZoom
OLD_ZBLOOKUP = (
    "  document.querySelectorAll('.ssp-czb').forEach(function(b){b.classList.remove('on');});\n"
    "  var _zb=document.getElementById(_zm[chartZoom]); if(_zb)_zb.classList.add('on');\n"
)
NEW_ZBLOOKUP = (
    "  document.querySelectorAll('.ssp-czb').forEach(function(b){b.classList.remove('on');});\n"
    "  var _sspcz=window._sspChartZoom||252;\n"
    "  var _zb=document.getElementById(_zm[_sspcz]); if(_zb)_zb.classList.add('on');\n"
)
src = patch(src, OLD_ZBLOOKUP, NEW_ZBLOOKUP,
            "F16b: sspRenderChart safe chartZoom access")

# F16c — sspSetChartZoom: set _sspChartZoom + call _dashSetChartZoom with string equiv
OLD_SETZ = "function sspSetChartZoom(z){\n  chartZoom=z;\n"
NEW_SETZ = (
    "function sspSetChartZoom(z){\n"
    "  window._sspChartZoom=z;\n"
    "  var _n2s={126:'6M',252:'1Y',504:'2Y',756:'3Y',1260:'5Y',99999:'All'};\n"
    "  if(window._dashSetChartZoom) window._dashSetChartZoom(_n2s[z]||'1Y');\n"
)
src = patch(src, OLD_SETZ, NEW_SETZ,
            "F16c: sspSetChartZoom update both zoom stores")

if failures:
    log(f"\nFAILED — {len(failures)} anchor(s):")
    for f in failures: log(f"  {f}")
    sys.exit(1)

patched_len = len(src)
log(f"\nPatched: {patched_len:,} bytes (delta: +{patched_len - orig_len:,})")

log("Syntax check...")
try:
    compile(src, "build_dashboard.py", "exec")
    log("  OK")
except SyntaxError as e:
    log(f"  !! SYNTAX ERROR: {e}"); sys.exit(1)

log("Writing...")
with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(src)

written = os.path.getsize(OUT_PATH)
log(f"On-disk: {written:,} bytes")
if written < patched_len * 0.99:
    log("!! SIZE MISMATCH"); sys.exit(1)

md5_mem  = hashlib.md5(src.encode("utf-8")).hexdigest()
with open(OUT_PATH, "rb") as ff:
    md5_disk = hashlib.md5(ff.read()).hexdigest()
if md5_mem != md5_disk:
    log(f"!! MD5 MISMATCH mem={md5_mem} disk={md5_disk}"); sys.exit(1)

log(f"MD5 OK: {md5_disk}")
log("Done — F16a/b/c applied.")
