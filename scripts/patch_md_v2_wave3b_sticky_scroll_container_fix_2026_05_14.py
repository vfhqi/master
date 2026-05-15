#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_md_v2_wave3b_sticky_scroll_container_fix_2026_05_14.py

SA - Master Dashboard | MD V2 | Wave 3b - corrective: fix the V2 sticky-header
scroll-container bug.

THE BUG
-------
Wave 2 added `.table-wrap { overflow-x: auto; overflow-y: visible }` to give
wide V2 tables a horizontal scrollbar. But CSS coerces a `visible` overflow on
one axis to `auto` when the other axis is non-`visible` - so every V2
`.table-wrap` is effectively `overflow: auto auto`, i.e. a scroll container.
A `position: sticky` element only sticks within its nearest scroll-container
ancestor, NOT the viewport - so Wave 1's frozen table headers (and Wave 3's
matrix headers) never actually pin on scroll. Confirmed on the live build
across Stage 1-4, Pre-test indicators, Post-test indicators, Capital
qualification setups, Capital deployment tests, and the new Master Overview
matrix: the header rows scroll off the top of the viewport.

THE FIX (Option 3 - the comprehensive one)
-------------------------------------------
Restore `.table-wrap` to `overflow: visible` so it is NOT a scroll container
- the sticky thead rows then anchor to the viewport and freeze correctly.
Move the horizontal scroll onto a NEW inner wrapper `<div class="v2-hscroll">`
placed between `.table-wrap` and the `<table>`. `.v2-hscroll` carries
`overflow-x: auto; overflow-y: visible` - it IS a scroll container, but it
scrolls HORIZONTALLY only, and a horizontal-only scroll container does not
become the containing block for VERTICAL sticky positioning. So wide tables
still scroll sideways AND the headers still freeze.

This is purely structural - it wraps each of the 10 V2 tables in one extra
div. No header offsets change; the Wave 1 `--header-height + --v2-ribbon-h`
ladder is untouched and now actually takes effect.

EDITS to scripts/build_dashboard.py (22 total):
  (A)  1x - replace the Wave 2 `.table-wrap` overflow rule body so .table-wrap
            is overflow:visible again, and append the new `.v2-hscroll` rule.
  (B) 10x - insert `<div class="v2-hscroll">` immediately after each V2
            table's opening `<div class="table-wrap">` (8 module tables +
            mo-main-table + mo-matrix-table).
  (C) 10x - insert the matching `</div>` immediately after each V2 table's
            closing `</table>`.

Each (B)/(C) edit is anchored on that table's UNIQUE id / tbody id, so the
22 replacements are individually unambiguous.

Idempotent via MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER. ASCII-only.
Patcher discipline: utf-8 IO, temp files beside the patcher, atomic write,
dry-run support, MD5 self-report, per-anchor uniqueness assertion.

Usage:
    python patch_md_v2_wave3b_sticky_scroll_container_fix_2026_05_14.py
    python patch_md_v2_wave3b_sticky_scroll_container_fix_2026_05_14.py --dry-run
"""

import os
import sys
import hashlib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(SCRIPT_DIR, "build_dashboard.py")
MARKER = "MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER"

# ---------------------------------------------------------------------------
# (A) CSS - replace the Wave 2 .table-wrap overflow rule body, append .v2-hscroll
# ---------------------------------------------------------------------------
CSS_OLD = (
    "body[data-active-tab^=\"stage_\"] .table-wrap,\n"
    "body[data-active-tab=\"pre_indicators\"] .table-wrap,\n"
    "body[data-active-tab=\"post_indicators\"] .table-wrap,\n"
    "body[data-active-tab=\"setups\"] .table-wrap,\n"
    "body[data-active-tab=\"tests\"] .table-wrap,\n"
    "body[data-active-tab=\"master_overview\"] .table-wrap {\n"
    "  overflow-x: auto;\n"
    "  overflow-y: visible;\n"
    "}"
)
CSS_NEW = (
    "/* " + MARKER + ": Wave 3b (14-May-26) corrective. The Wave 2 rule put\n"
    "   overflow-x:auto on .table-wrap; CSS then coerces overflow-y to auto,\n"
    "   making .table-wrap a scroll container that TRAPS the Wave 1 sticky\n"
    "   thead rows so they never pin to the viewport. Fix: .table-wrap goes\n"
    "   back to overflow:visible (not a scroll container -> sticky anchors to\n"
    "   the viewport and freezes), and the horizontal scroll moves to a new\n"
    "   inner wrapper .v2-hscroll. .v2-hscroll IS a scroll container but it\n"
    "   scrolls HORIZONTALLY only; a horizontal-only scroll container does\n"
    "   not become the containing block for VERTICAL sticky positioning, so\n"
    "   the frozen headers keep working AND wide tables still scroll sideways. */\n"
    "body[data-active-tab^=\"stage_\"] .table-wrap,\n"
    "body[data-active-tab=\"pre_indicators\"] .table-wrap,\n"
    "body[data-active-tab=\"post_indicators\"] .table-wrap,\n"
    "body[data-active-tab=\"setups\"] .table-wrap,\n"
    "body[data-active-tab=\"tests\"] .table-wrap,\n"
    "body[data-active-tab=\"master_overview\"] .table-wrap {\n"
    "  overflow: visible;\n"
    "}\n"
    "body[data-active-tab^=\"stage_\"] .v2-hscroll,\n"
    "body[data-active-tab=\"pre_indicators\"] .v2-hscroll,\n"
    "body[data-active-tab=\"post_indicators\"] .v2-hscroll,\n"
    "body[data-active-tab=\"setups\"] .v2-hscroll,\n"
    "body[data-active-tab=\"tests\"] .v2-hscroll,\n"
    "body[data-active-tab=\"master_overview\"] .v2-hscroll {\n"
    "  overflow-x: auto;\n"
    "  overflow-y: visible;\n"
    "}"
)

# ---------------------------------------------------------------------------
# (B)/(C) per-table wrap insertions
# ---------------------------------------------------------------------------
MODULE_TABLE_IDS = [
    "s1-main-table", "s2-main-table", "s3-main-table", "s4-main-table",
    "pi-main-table", "po-main-table", "st-main-table", "ct-main-table",
]


def module_open_old(tid):
    return (
        "'<div class=\"table-wrap\">' +\n"
        "        '<table class=\"data-table\" id=\"" + tid + "\">' +"
    )


def module_open_new(tid):
    return (
        "'<div class=\"table-wrap\"><div class=\"v2-hscroll\">' +  /* " + MARKER + " */\n"
        "        '<table class=\"data-table\" id=\"" + tid + "\">' +"
    )


def module_close_old(tid):
    prefix = tid.split("-")[0]
    return (
        "'<tbody id=\"" + prefix + "-tbody\"></tbody>' +\n"
        "        '</table>' +\n"
        "      '</div>';"
    )


def module_close_new(tid):
    prefix = tid.split("-")[0]
    return (
        "'<tbody id=\"" + prefix + "-tbody\"></tbody>' +\n"
        "        '</table>' +\n"
        "      '</div></div>';  /* " + MARKER + " */"
    )


MO_MAIN_OPEN_OLD = "var table = '<div class=\"table-wrap\"><table class=\"data-table\" id=\"mo-main-table\">' +"
MO_MAIN_OPEN_NEW = "var table = '<div class=\"table-wrap\"><div class=\"v2-hscroll\"><table class=\"data-table\" id=\"mo-main-table\">' +  /* " + MARKER + " */"
MO_MAIN_CLOSE_OLD = "table += '<th class=\"mo-total-col\">Total rated</th></tr></thead><tbody id=\"mo-tbody\"></tbody></table></div>';"
MO_MAIN_CLOSE_NEW = "table += '<th class=\"mo-total-col\">Total rated</th></tr></thead><tbody id=\"mo-tbody\"></tbody></table></div></div>';  /* " + MARKER + " */"

MO_MX_OPEN_OLD = "'<div class=\"table-wrap\"><table class=\"data-table\" id=\"mo-matrix-table\">' +"
MO_MX_OPEN_NEW = "'<div class=\"table-wrap\"><div class=\"v2-hscroll\"><table class=\"data-table\" id=\"mo-matrix-table\">' +  /* " + MARKER + " */"
MO_MX_CLOSE_OLD = "'<thead></thead><tbody id=\"mo-matrix-tbody\"></tbody></table></div>' +"
MO_MX_CLOSE_NEW = "'<thead></thead><tbody id=\"mo-matrix-tbody\"></tbody></table></div></div>' +  /* " + MARKER + " */"


def sha(b):
    return hashlib.md5(b).hexdigest()


def main():
    dry = "--dry-run" in sys.argv

    if not os.path.isfile(TARGET):
        print("ERROR: target not found: %s" % TARGET)
        return 1

    with open(TARGET, "r", encoding="utf-8") as fh:
        src = fh.read()

    print("Target : %s" % TARGET)
    print("Before : %d bytes, %d lines, md5 %s" % (len(src.encode("utf-8")), src.count("\n") + 1, sha(src.encode("utf-8"))))

    if MARKER in src:
        print("\nMARKER already present - patch is idempotent, nothing to do.")
        return 0

    edits = []
    edits.append(("CSS .table-wrap rule + .v2-hscroll", CSS_OLD, CSS_NEW))
    for tid in MODULE_TABLE_IDS:
        edits.append(("open  " + tid, module_open_old(tid), module_open_new(tid)))
        edits.append(("close " + tid, module_close_old(tid), module_close_new(tid)))
    edits.append(("open  mo-main-table", MO_MAIN_OPEN_OLD, MO_MAIN_OPEN_NEW))
    edits.append(("close mo-main-table", MO_MAIN_CLOSE_OLD, MO_MAIN_CLOSE_NEW))
    edits.append(("open  mo-matrix-table", MO_MX_OPEN_OLD, MO_MX_OPEN_NEW))
    edits.append(("close mo-matrix-table", MO_MX_CLOSE_OLD, MO_MX_CLOSE_NEW))

    problems = []
    for label, old, new in edits:
        n = src.count(old)
        if n != 1:
            problems.append("%-32s anchor count = %d (need 1)" % (label, n))
    if problems:
        print("\nABORT - anchor problems:")
        for p in problems:
            print("  - %s" % p)
        return 1

    out = src
    for label, old, new in edits:
        before = out
        out = out.replace(old, new, 1)
        if out == before:
            print("\nABORT - edit applied no change: %s" % label)
            return 1

    checks = []
    if out == src:
        checks.append("output identical to source")
    marker_added = sum(new.count(MARKER) for _, _, new in edits)
    if out.count(MARKER) != marker_added:
        checks.append("expected %d MARKER occurrences, found %d" % (marker_added, out.count(MARKER)))
    if "\x00" in out:
        checks.append("null byte present in output")
    if "body[data-active-tab=\"master_overview\"] .table-wrap {\n  overflow: visible;\n}" not in out:
        checks.append(".table-wrap rule not rewritten to overflow:visible")
    if "body[data-active-tab=\"master_overview\"] .v2-hscroll {\n  overflow-x: auto;" not in out:
        checks.append(".v2-hscroll rule not present")
    if ".table-wrap {\n  overflow-x: auto;\n  overflow-y: visible;\n}" in out:
        checks.append("old .table-wrap overflow-x:auto rule body still present")
    vh_expected = CSS_NEW.count("v2-hscroll") + sum(
        new.count("v2-hscroll") for label, _, new in edits if label.startswith("open")
    )
    vh = out.count("v2-hscroll")
    if vh != vh_expected:
        checks.append("'v2-hscroll' literal count = %d (expected %d)" % (vh, vh_expected))
    if checks:
        print("\nABORT - post-edit sanity checks failed:")
        for c in checks:
            print("  - %s" % c)
        return 1

    out_bytes = out.encode("utf-8")
    print("After  : %d bytes, %d lines, md5 %s" % (len(out_bytes), out.count("\n") + 1, sha(out_bytes)))
    print("Delta  : +%d bytes, +%d lines, %d edits applied" % (
        len(out_bytes) - len(src.encode("utf-8")), out.count("\n") - src.count("\n"), len(edits)))

    if dry:
        dest = os.path.join(SCRIPT_DIR, "build_dashboard.py.wave3b-patched")
        tmp = dest + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as fh:
            fh.write(out)
        os.replace(tmp, dest)
        print("\nDRY-RUN: wrote patched copy to %s" % dest)
        print("Source UNCHANGED. Inspect / node --check, then re-run without --dry-run.")
        return 0

    tmp = TARGET + ".wave3b.tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(out)
    os.replace(tmp, TARGET)

    with open(TARGET, "r", encoding="utf-8") as fh:
        verify = fh.read()
    print("\nPATCHED in place. Re-read md5 %s (%d bytes)" % (sha(verify.encode("utf-8")), len(verify.encode("utf-8"))))
    if verify != out:
        print("WARNING: re-read does not match intended output - investigate before committing.")
        return 1
    print("OK - re-read matches intended output.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
