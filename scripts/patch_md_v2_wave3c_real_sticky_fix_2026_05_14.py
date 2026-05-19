#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_md_v2_wave3c_real_sticky_fix_2026_05_14.py

SA - Master Dashboard | MD V2 | Wave 3c - the REAL sticky-header fix.

WHY 3c EXISTS
-------------
Wave 3b restored .table-wrap to overflow:visible and moved the horizontal
scroll to an inner .v2-hscroll div - on the theory that a "horizontal-only"
scroll container does not trap vertical sticky positioning. That theory was
WRONG. CSS coerces `overflow-x: auto; overflow-y: visible` to effectively
`overflow: auto auto` - .v2-hscroll became a full (both-axis) scroll
container and trapped the sticky thead rows exactly as .table-wrap did.
Confirmed on the live build: matrix header rows still at viewportTop -787,
not pinned.

THE ACTUAL CONSTRAINT
---------------------
A position:sticky thead row anchors to its NEAREST scroll-container
ancestor. The table is both taller and wider than the viewport, so SOMETHING
must scroll on each axis. For the headers to freeze, the VERTICAL scroller
must be the viewport/body (no intermediate container). Any intermediate
element with overflow-x:auto ALSO gets overflow-y:auto (coercion) and steals
the role. Therefore the horizontal scroll cannot live on an intermediate
div at all - it must live on `body` itself.

THE FIX (verified by live in-page simulation)
----------------------------------------------
  1. Scope `body { overflow-x: auto }` to the 6 V2 tab-states. The PAGE
     becomes the horizontal scroller; there is no intermediate scroll
     container, so the body remains the single scroll container on BOTH
     axes and the sticky thead rows anchor to it correctly. (Legacy tabs
     are untouched - their body stays overflow-x:hidden.)
  2. Neutralise `.v2-hscroll` to `overflow: visible` - it stops being a
     scroll container. The Wave 3b inner divs stay in the markup but are
     now inert pass-through wrappers (harmless; not worth ripping out).
  3. Pin the sticky ribbon horizontally (`left: 0`) so it does not drift
     sideways when the page is scrolled horizontally. (The fixed nav header
     already stays put; only the sticky ribbon needed this.)

Live simulation result with 1+2+3 applied: all three matrix header rows pin
at viewportTop 113 / 169 / 191 (the Wave 1 offset ladder), and stay pinned
after horizontal scroll; the fixed nav header stays at left:0; legacy tabs
show no unwanted horizontal scrollbar.

EDITS to scripts/build_dashboard.py (3 total):
  (1) replace the .v2-hscroll rule body: overflow-x:auto/overflow-y:visible
      -> overflow:visible.
  (2) append a `body[...] { overflow-x: auto }` rule scoped to the 6 V2
      tab-states, immediately after the (now-neutralised) .v2-hscroll rule.
  (3) add `left: 0;` to the sticky-ribbon rule body.

Idempotent via MD-V2-WAVE3C-REAL-STICKY-FIX-MARKER. ASCII-only.
Patcher discipline: utf-8 IO, temp files beside patcher, atomic write,
dry-run support, MD5 self-report, per-anchor uniqueness assertion.

Usage:
    python patch_md_v2_wave3c_real_sticky_fix_2026_05_14.py
    python patch_md_v2_wave3c_real_sticky_fix_2026_05_14.py --dry-run
"""

import os
import sys
import hashlib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(SCRIPT_DIR, "build_dashboard.py")
MARKER = "MD-V2-WAVE3C-REAL-STICKY-FIX-MARKER"

# --- EDIT 1: neutralise the .v2-hscroll rule body --------------------------
# Anchored on the full rule (selector list + body) so it is unambiguous.
VH_OLD = (
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
VH_NEW = (
    "/* " + MARKER + ": Wave 3c (14-May-26). Wave 3b's theory was wrong - CSS\n"
    "   coerces overflow-x:auto + overflow-y:visible to overflow:auto/auto, so\n"
    "   .v2-hscroll became a full scroll container and trapped sticky just like\n"
    "   .table-wrap did. Neutralise .v2-hscroll to overflow:visible (inert\n"
    "   pass-through wrapper) and move the horizontal scroll to `body` itself -\n"
    "   the only non-trapping option, since any intermediate overflow-x:auto\n"
    "   ancestor also gets overflow-y:auto and steals the sticky anchor. */\n"
    "body[data-active-tab^=\"stage_\"] .v2-hscroll,\n"
    "body[data-active-tab=\"pre_indicators\"] .v2-hscroll,\n"
    "body[data-active-tab=\"post_indicators\"] .v2-hscroll,\n"
    "body[data-active-tab=\"setups\"] .v2-hscroll,\n"
    "body[data-active-tab=\"tests\"] .v2-hscroll,\n"
    "body[data-active-tab=\"master_overview\"] .v2-hscroll {\n"
    "  overflow: visible;\n"
    "}\n"
    "/* " + MARKER + ": the page itself is the horizontal scroller on V2 tabs.\n"
    "   Scoped to the 6 V2 tab-states so legacy tabs keep body overflow-x:hidden. */\n"
    "body[data-active-tab^=\"stage_\"],\n"
    "body[data-active-tab=\"pre_indicators\"],\n"
    "body[data-active-tab=\"post_indicators\"],\n"
    "body[data-active-tab=\"setups\"],\n"
    "body[data-active-tab=\"tests\"],\n"
    "body[data-active-tab=\"master_overview\"] {\n"
    "  overflow-x: auto;\n"
    "}"
)

# --- EDIT 2: pin the sticky ribbon horizontally ----------------------------
RIBBON_OLD = (
    "body[data-active-tab=\"master_overview\"] .controls.s1-controls {\n"
    "  position: sticky;\n"
    "  top: var(--header-height);\n"
    "  z-index: 60;\n"
    "  box-shadow: 0 2px 5px rgba(0,0,0,0.07);\n"
    "}"
)
RIBBON_NEW = (
    "body[data-active-tab=\"master_overview\"] .controls.s1-controls {\n"
    "  position: sticky;\n"
    "  top: var(--header-height);\n"
    "  left: 0;  /* " + MARKER + ": pin horizontally so the ribbon does not drift on horizontal page scroll */\n"
    "  z-index: 60;\n"
    "  box-shadow: 0 2px 5px rgba(0,0,0,0.07);\n"
    "}"
)


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

    edits = [
        ("neutralise .v2-hscroll + add body overflow-x", VH_OLD, VH_NEW),
        ("pin sticky ribbon left:0", RIBBON_OLD, RIBBON_NEW),
    ]

    problems = []
    for label, old, new in edits:
        n = src.count(old)
        if n != 1:
            problems.append("%-44s anchor count = %d (need 1)" % (label, n))
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
    # the OLD trapping .v2-hscroll body must be GONE
    if ".v2-hscroll {\n  overflow-x: auto;\n  overflow-y: visible;\n}" in out:
        checks.append("old .v2-hscroll overflow-x:auto rule body still present")
    # the neutralised .v2-hscroll rule must be present
    if "body[data-active-tab=\"master_overview\"] .v2-hscroll {\n  overflow: visible;\n}" not in out:
        checks.append(".v2-hscroll not neutralised to overflow:visible")
    # the new body overflow-x rule must be present
    if "body[data-active-tab=\"master_overview\"] {\n  overflow-x: auto;\n}" not in out:
        checks.append("body overflow-x:auto V2-scoped rule not present")
    # the ribbon must now carry left:0
    if "left: 0;  /* " + MARKER not in out:
        checks.append("sticky ribbon left:0 not applied")
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
        dest = os.path.join(SCRIPT_DIR, "build_dashboard.py.wave3c-patched")
        tmp = dest + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as fh:
            fh.write(out)
        os.replace(tmp, dest)
        print("\nDRY-RUN: wrote patched copy to %s" % dest)
        print("Source UNCHANGED. Inspect, then re-run without --dry-run.")
        return 0

    tmp = TARGET + ".wave3c.tmp"
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
