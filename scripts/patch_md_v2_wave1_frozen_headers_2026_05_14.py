#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MD V2 — Wave 1 patcher (14-May-26)
Three fixes across all 9 V2 tabs, all in build_dashboard.py:

  (a) FROZEN HEADERS — table thead sticky `top:` offsets were anchored at
      viewport 0, sliding the supergroup + column-header rows UNDER the
      70px fixed page header on scroll. Re-anchor every V2 table's sticky
      rows off var(--header-height) PLUS the sticky ribbon height
      (--v2-ribbon-h), and lift thead z-index above the ribbon.

  (b) STICKY RIBBON — the .controls.s1-controls ribbon (Inputs / Scope /
      Colour by / ...) is made position:sticky directly under the MD V2
      nav so it stays visible while the 946-row table scrolls.

  (c) TILE-CLICK DEFAULT — a click on a tile BODY (PI/PO/Setups/Tests)
      previously selected ALL rating tiers. Now it selects only
      ['Probable']; clicking again when exactly ['Probable'] is selected
      clears it. Individual tier CHIPS keep working as direct
      multi-select toggles (piToggleTier etc. are untouched).

Platform discipline (S27 lessons): force encoding="utf-8" on all IO;
temp/validation files written beside the patcher, never /tmp; atomic
write at end; idempotent via marker; ASCII-only literals.
"""

import os, sys, hashlib

MARKER = "MD-V2-WAVE1-FROZEN-HEADERS-MARKER"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(SCRIPT_DIR, "build_dashboard.py")

# ----------------------------------------------------------------------
# Block 1 — CSS appended at the end of the CHROME-PARITY-FOLLOWUP CSS block.
# Anchored on that block's CSS-END marker (stable across S24-S27).
# ----------------------------------------------------------------------
CSS_ANCHOR = "/* MD-V2-CHROME-PARITY-FOLLOWUP-MARKER-CSS-END */"

CSS_NEW = """/* MD-V2-CHROME-PARITY-FOLLOWUP-MARKER-CSS-END */
/* {MARKER}-CSS-START */
/* Wave 1 (14-May-26): sticky ribbon + corrected frozen-header offsets.
   --header-height is 70px on V2 tabs. --v2-ribbon-h is measured at render
   time by the JS helper below (the ribbon wraps at narrow widths so a
   fixed guess is fragile); it falls back to 46px before first measure. */
body[data-active-tab^="stage_"],
body[data-active-tab="pre_indicators"],
body[data-active-tab="post_indicators"],
body[data-active-tab="setups"],
body[data-active-tab="tests"],
body[data-active-tab="master_overview"] { --v2-ribbon-h: 46px; }

/* The ribbon: sticky directly under the fixed MD V2 nav header. */
body[data-active-tab^="stage_"] .controls.s1-controls,
body[data-active-tab="pre_indicators"] .controls.s1-controls,
body[data-active-tab="post_indicators"] .controls.s1-controls,
body[data-active-tab="setups"] .controls.s1-controls,
body[data-active-tab="tests"] .controls.s1-controls,
body[data-active-tab="master_overview"] .controls.s1-controls {
  position: sticky;
  top: var(--header-height);
  z-index: 60;
  box-shadow: 0 2px 5px rgba(0,0,0,0.07);
}

/* Frozen table headers: re-anchor every V2 table's sticky rows below the
   fixed header AND the sticky ribbon. Stage 1-4 tables have 2 header rows
   (group-header + col-header); PI/PO/ST have 3 (super-group + group +
   col); CT has 2. Each row stacks on the one above it. z-index lifted
   above the ribbon's 60. The thead's own sticky/top is neutralised so the
   per-ROW offsets are what take effect. */
#s1-main-table thead, #s2-main-table thead, #s3-main-table thead,
#s4-main-table thead, #pi-main-table thead, #po-main-table thead,
#st-main-table thead, #ct-main-table thead {
  position: static !important;
  z-index: auto !important;
  box-shadow: none !important;
}
/* Stage 1-4: group-header row height ~28px (matches old col-header top). */
#s1-main-table thead tr.group-header-row th,
#s2-main-table thead tr.group-header-row th,
#s3-main-table thead tr.group-header-row th,
#s4-main-table thead tr.group-header-row th {
  position: sticky;
  top: calc(var(--header-height) + var(--v2-ribbon-h));
  z-index: 70;
}
#s1-main-table thead tr.col-header-row th,
#s2-main-table thead tr.col-header-row th,
#s3-main-table thead tr.col-header-row th,
#s4-main-table thead tr.col-header-row th {
  position: sticky;
  top: calc(var(--header-height) + var(--v2-ribbon-h) + 28px);
  z-index: 70;
}
/* PI / PO / ST: 3 header rows. Row heights 24px (super-group) + 24px
   (group-header) measured from the existing 0/24/48 ladder. */
#pi-main-table thead tr.super-group-row th,
#po-main-table thead tr.super-group-row th,
#st-main-table thead tr.super-group-row th {
  position: sticky;
  top: calc(var(--header-height) + var(--v2-ribbon-h));
  z-index: 72;
}
#pi-main-table thead tr.group-header-row th,
#po-main-table thead tr.group-header-row th,
#st-main-table thead tr.group-header-row th {
  position: sticky;
  top: calc(var(--header-height) + var(--v2-ribbon-h) + 24px);
  z-index: 71;
}
#pi-main-table thead tr.col-header-row th,
#po-main-table thead tr.col-header-row th,
#st-main-table thead tr.col-header-row th {
  position: sticky;
  top: calc(var(--header-height) + var(--v2-ribbon-h) + 48px);
  z-index: 70;
}
/* CT (Capital deployment tests): 2 header rows today. Wave 2 adds a 3rd
   (sub-group) row and will re-stack these — this is the 2-row state. */
#ct-main-table thead tr.group-header-row th {
  position: sticky;
  top: calc(var(--header-height) + var(--v2-ribbon-h));
  z-index: 71;
}
#ct-main-table thead tr.col-header-row th {
  position: sticky;
  top: calc(var(--header-height) + var(--v2-ribbon-h) + 24px);
  z-index: 70;
}
/* {MARKER}-CSS-END */
""".replace("{MARKER}", MARKER)

# ----------------------------------------------------------------------
# Block 2 — JS ribbon-height measurement helper. Appended just before the
# ensureV2Nav function so it lives in the same chrome-parity IIFE scope.
# Re-measures on every syncV2State call + on window resize.
# ----------------------------------------------------------------------
JS_ANCHOR = "  function ensureV2Nav() {"

JS_NEW = """  // {MARKER}: measure the sticky ribbon's rendered height and publish it
  // as the --v2-ribbon-h custom property so the frozen-header `top:`
  // offsets are exact even when the ribbon wraps at narrow widths.
  function measureV2Ribbon() {
    var active = document.body.getAttribute('data-active-tab') || '';
    var v2 = (active.indexOf('stage_') === 0 || active === 'pre_indicators' ||
              active === 'post_indicators' || active === 'setups' ||
              active === 'tests' || active === 'master_overview');
    if (!v2) return;
    var pane = document.getElementById('tab-' + active);
    var ribbon = pane && pane.querySelector('.controls.s1-controls');
    if (!ribbon) return;
    var h = ribbon.getBoundingClientRect().height;
    if (h && h > 0) {
      document.body.style.setProperty('--v2-ribbon-h', Math.round(h) + 'px');
    }
  }
  window.measureV2Ribbon = measureV2Ribbon;
  if (!window._v2RibbonResizeWired) {
    window._v2RibbonResizeWired = true;
    window.addEventListener('resize', function() {
      // rAF-debounced so a drag-resize does not thrash layout.
      if (window._v2RibbonRaf) return;
      window._v2RibbonRaf = requestAnimationFrame(function() {
        window._v2RibbonRaf = 0;
        measureV2Ribbon();
      });
    });
  }
  function ensureV2Nav() {""".replace("{MARKER}", MARKER)

# ----------------------------------------------------------------------
# Block 3 — hook measureV2Ribbon into syncV2State so it runs on every tab
# switch (after the pane is rendered + visible). syncV2State currently
# ends by setting the data-active-tab attr + nav classes; we append the
# call right after the body attribute is set... but the pane renders
# AFTER syncV2State in switchTab. Safest: call it on a rAF from inside
# syncV2State so it runs once layout has settled.
# ----------------------------------------------------------------------
SYNC_ANCHOR = "  function syncV2State(id) {\n    document.body.setAttribute('data-active-tab', id);\n    ensureV2Nav();"

SYNC_NEW = """  function syncV2State(id) {
    document.body.setAttribute('data-active-tab', id);
    ensureV2Nav();
    // {MARKER}: re-measure the sticky ribbon once this tab's layout settles.
    requestAnimationFrame(function(){ requestAnimationFrame(measureV2Ribbon); });""".replace("{MARKER}", MARKER)

# ----------------------------------------------------------------------
# Block 4 — tile-click default: rewrite the 4 *SelectAllTiers functions so
# a tile-body click selects only ['Probable'] (toggle off if already
# exactly that). The chip handlers (*ToggleTier) are left untouched.
# Each function is byte-identical in structure across pi/po/st/ct.
# ----------------------------------------------------------------------
def select_probable_old(prefix, patterns, render):
    return (
        "  function %sSelectAllTiers(patternKey) {\n"
        "    var pat = null;\n"
        "    for (var p = 0; p < %s.length; p++) if (%s[p].key === patternKey) pat = %s[p];\n"
        "    if (!pat) return;\n"
        "    var sel = %sState.tierFilter[patternKey] || [];\n"
        "    var allOn = sel.length === pat.tierLadder.length;\n"
        "    %sState.tierFilter[patternKey] = allOn ? [] : pat.tierLadder.slice();\n"
        "    %s();\n"
        "  }"
    ) % (prefix, patterns, patterns, patterns, prefix, prefix, render)

def select_probable_new(prefix, patterns, render):
    return (
        "  function %sSelectAllTiers(patternKey) {\n"
        "    // {MARKER}: tile-body click selects ONLY the Probable tier\n"
        "    // (D-MD-V2-74). If exactly ['Probable'] is already selected,\n"
        "    // clear it (toggle off). Tier chips remain direct multi-select.\n"
        "    var pat = null;\n"
        "    for (var p = 0; p < %s.length; p++) if (%s[p].key === patternKey) pat = %s[p];\n"
        "    if (!pat) return;\n"
        "    var sel = %sState.tierFilter[patternKey] || [];\n"
        "    var probable = (pat.tierLadder.indexOf('Probable') > -1) ? 'Probable'\n"
        "                   : pat.tierLadder[pat.tierLadder.length - 1];\n"
        "    var onlyProbable = (sel.length === 1 && sel[0] === probable);\n"
        "    %sState.tierFilter[patternKey] = onlyProbable ? [] : [probable];\n"
        "    %s();\n"
        "  }"
    ).replace("{MARKER}", MARKER) % (prefix, patterns, patterns, patterns, prefix, prefix, render)

TILE_EDITS = [
    ("pi", "PI_PATTERNS", "piRenderRows"),
    ("po", "PO_PATTERNS", "poRenderRows"),
    ("st", "ST_PATTERNS", "stRenderRows"),
    ("ct", "CT_PATTERNS", "ctRenderRows"),
]


def main():
    if not os.path.exists(TARGET):
        print("ERROR: target not found: %s" % TARGET)
        sys.exit(1)

    with open(TARGET, "r", encoding="utf-8") as f:
        src = f.read()

    if MARKER in src:
        print("SKIP: %s already present - patch already applied." % MARKER)
        sys.exit(0)

    edits_applied = []

    # --- Edit 1: CSS block ---
    if CSS_ANCHOR not in src:
        print("ERROR: CSS anchor not found: %r" % CSS_ANCHOR)
        sys.exit(1)
    if src.count(CSS_ANCHOR) != 1:
        print("ERROR: CSS anchor not unique (%d matches)" % src.count(CSS_ANCHOR))
        sys.exit(1)
    src = src.replace(CSS_ANCHOR, CSS_NEW, 1)
    edits_applied.append("CSS sticky-header + ribbon block")

    # --- Edit 2: ribbon-measure JS helper ---
    if JS_ANCHOR not in src:
        print("ERROR: JS anchor (ensureV2Nav) not found")
        sys.exit(1)
    if src.count(JS_ANCHOR) != 1:
        print("ERROR: JS anchor not unique (%d matches)" % src.count(JS_ANCHOR))
        sys.exit(1)
    src = src.replace(JS_ANCHOR, JS_NEW, 1)
    edits_applied.append("measureV2Ribbon helper + resize listener")

    # --- Edit 3: hook into syncV2State ---
    if SYNC_ANCHOR not in src:
        print("ERROR: syncV2State anchor not found")
        sys.exit(1)
    if src.count(SYNC_ANCHOR) != 1:
        print("ERROR: syncV2State anchor not unique (%d matches)" % src.count(SYNC_ANCHOR))
        sys.exit(1)
    src = src.replace(SYNC_ANCHOR, SYNC_NEW, 1)
    edits_applied.append("syncV2State -> measureV2Ribbon hook")

    # --- Edit 4: tile-click -> Probable only (x4) ---
    for prefix, patterns, render in TILE_EDITS:
        old = select_probable_old(prefix, patterns, render)
        new = select_probable_new(prefix, patterns, render)
        if old not in src:
            print("ERROR: %sSelectAllTiers anchor not found (structure changed?)" % prefix)
            sys.exit(1)
        if src.count(old) != 1:
            print("ERROR: %sSelectAllTiers anchor not unique (%d)" % (prefix, src.count(old)))
            sys.exit(1)
        src = src.replace(old, new, 1)
        edits_applied.append("%sSelectAllTiers -> Probable-only" % prefix)

    # --- validate: py_compile in a temp file beside the patcher ---
    tmp = os.path.join(SCRIPT_DIR, "_wave1_validate.s14check")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(src)
    import py_compile
    try:
        py_compile.compile(tmp, doraise=True)
    except py_compile.PyCompileError as e:
        print("ERROR: patched source fails py_compile:\n%s" % e)
        os.remove(tmp)
        sys.exit(1)
    os.remove(tmp)

    # --- atomic write ---
    final_tmp = TARGET + ".wave1tmp"
    with open(final_tmp, "w", encoding="utf-8") as f:
        f.write(src)
    os.replace(final_tmp, TARGET)

    # --- post-write verification ---
    with open(TARGET, "r", encoding="utf-8") as f:
        check = f.read()
    print("")
    print("Edits applied:")
    for e in edits_applied:
        print("  [OK] %s" % e)
    print("")
    print("Post-write checks:")
    ok = True
    def chk(label, cond):
        nonlocal ok
        print("  [%s] %s" % ("OK" if cond else "FAIL", label))
        if not cond:
            ok = False
    chk("MARKER present", MARKER in check)
    chk("CSS-START present", (MARKER + "-CSS-START") in check)
    chk("CSS-END present", (MARKER + "-CSS-END") in check)
    chk("measureV2Ribbon defined", "function measureV2Ribbon()" in check)
    chk("syncV2State hook present", "requestAnimationFrame(measureV2Ribbon)" in check)
    chk("pi Probable-only", "var onlyProbable = (sel.length === 1 && sel[0] === probable);" in check)
    chk("4x SelectAllTiers rewritten",
        check.count("tile-body click selects ONLY the Probable tier") == 4)
    chk("ends with newline", check.endswith("\n"))
    md5 = hashlib.md5(check.encode("utf-8")).hexdigest()
    print("")
    print("  build_dashboard.py md5: %s" % md5)
    print("  size: %d bytes" % len(check.encode("utf-8")))
    if not ok:
        print("\nONE OR MORE CHECKS FAILED - inspect before building.")
        sys.exit(1)
    print("\nWave 1 patch applied cleanly.")


if __name__ == "__main__":
    main()
