#!/usr/bin/env python3
"""
patch_ssp_s64c.py — F15: restore missing ssp-hdr-ticker / ssp-hdr-company spans
F13 (s64b) removed both the duplicate AND the only set of those spans.
sspSetStock() crashes on null because neither element exists in the DOM.
Fix: re-insert them in the ssp-hdr, just before the close button.
"""
import hashlib, os, sys

COWORK   = "/sessions/friendly-charming-lamport/mnt/COWORK"
OUT_PATH = f"{COWORK}/master-dashboard/scripts/build_dashboard.py"

def log(msg): print(f"[patch-c] {msg}", flush=True)

log("Reading current FUSE file...")
with open(OUT_PATH, "r", encoding="utf-8") as f:
    src = f.read()
orig_len = len(src)
log(f"Read {orig_len:,} bytes")

failures = []
def patch(src, old, new, tag):
    if old not in src:
        failures.append(tag)
        log(f"  !! NOT FOUND: {tag}  [len={len(old)}]")
        return src
    count = src.count(old)
    if count > 1:
        failures.append(tag)
        log(f"  !! AMBIGUOUS ({count}): {tag}")
        return src
    log(f"  ok  {tag}")
    return src.replace(old, new, 1)

CLOSE_BTN = (
    "        '    <button class=\"ssp-close-btn\" onclick=\"closeStockView()\" "
    "title=\"Close Stock View\">&times;</button>\\n'\n"
)

SPANS_PLUS_CLOSE = (
    "        '    <span class=\"ssp-hdr-stock\" id=\"ssp-hdr-ticker\"></span>\\n'\n"
    "        '    <span class=\"ssp-hdr-company\" id=\"ssp-hdr-company\"></span>\\n'\n"
    + CLOSE_BTN
)

src = patch(src, CLOSE_BTN, SPANS_PLUS_CLOSE,
            "F15: restore ssp-hdr-ticker + ssp-hdr-company spans")

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

log(f"Writing...")
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
log("Done — F15 applied.")
