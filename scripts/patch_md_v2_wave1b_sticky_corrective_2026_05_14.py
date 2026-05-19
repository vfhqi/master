#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MD V2 — Wave 1b CORRECTIVE patcher (14-May-26)

Chrome-MCP verification of Wave 1 (commit c5f618a) found the sticky fix
not taking effect. Two root causes, both fixed here:

  (1) CASCADE ORDER. The Wave 1 CSS block was inserted at the end of the
      CHROME-PARITY-FOLLOWUP CSS block (~line 1170), but the
      PRE/POST/SETUPS/TESTS table-CSS blocks come AFTER it (lines 1262+).
      The original `top: 0/24/48px` sticky-row rules have identical
      specificity AND appear later -> they win. Fix: physically MOVE the
      Wave 1 CSS block to the very end of the TESTS CSS block (the last
      V2 CSS block), so it is last in source order and wins.

  (2) --v2-ribbon-h NEVER SET. measureV2Ribbon() was hooked only into
      syncV2State via a double-rAF, but syncV2State runs BEFORE the tab
      pane's renderX() builds the scaffold -> the ribbon does not exist
      (or is not laid out) when the rAF fires, so the property stays at
      its 46px CSS fallback while the real ribbon is ~80px. Fix: also
      call measureV2Ribbon() at the END of all 8 V2 render functions
      (renderStage1-4, renderPreIndicators, renderPostIndicators,
      renderSetups, renderTests), where the scaffold + ribbon exist and
      are laid out.

Idempotent via MARKER. Platform discipline: encoding="utf-8" on all IO;
temp file beside patcher; atomic write at end; ASCII-only literals.
"""

import os, sys, hashlib

MARKER = "MD-V2-WAVE1B-STICKY-CORRECTIVE-MARKER"
W1 = "MD-V2-WAVE1-FROZEN-HEADERS-MARKER"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(SCRIPT_DIR, "build_dashboard.py")

# The Wave 1 CSS block, delimited by its own START/END markers. We cut it
# out wherever it currently is and re-insert it after the TESTS CSS-END.
W1_CSS_START = "/* " + W1 + "-CSS-START */"
W1_CSS_END   = "/* " + W1 + "-CSS-END */"

TESTS_CSS_END = "/* MD-V2-TESTS-MARKER-CSS-END */"

# Render-function anchors: 7 share the BuildHeaderRow 4-line tail; Tests
# has its own. We append `  <prefix>MeasureRibbon hook` right after the
# final RenderRows() call inside each function body.
RENDER_HOOKS = [
    # (prefix-for-comment, anchor 4-line block, replacement)
    ("s1", "Stage1"), ("s2", "Stage2"), ("s3", "Stage3"), ("s4", "Stage4"),
    ("pi", "PreIndicators"), ("po", "PostIndicators"), ("st", "Setups"),
]

HOOK_LINE = ("\n    if (window.measureV2Ribbon) measureV2Ribbon();"
             "  /* " + MARKER + " */")


def build_render_anchor(prefix, render_name):
    return ("    %sBuildHeaderRow();\n"
            "    %sRenderRows();\n"
            "  }\n"
            "  window.render%s = render%s;") % (prefix, prefix, render_name, render_name)

def build_render_replacement(prefix, render_name):
    return ("    %sBuildHeaderRow();\n"
            "    %sRenderRows();%s\n"
            "  }\n"
            "  window.render%s = render%s;") % (prefix, prefix, HOOK_LINE, render_name, render_name)

# Tests render function has a different tail.
CT_ANCHOR = ("    ctBuildHeaderRow();\n"
             "    ctRenderRows();\n"
             "  }\n"
             "  // MD-V2-TESTS-S27-MARKER:")
CT_REPLACEMENT = ("    ctBuildHeaderRow();\n"
                  "    ctRenderRows();%s\n"
                  "  }\n"
                  "  // MD-V2-TESTS-S27-MARKER:") % HOOK_LINE


def main():
    if not os.path.exists(TARGET):
        print("ERROR: target not found: %s" % TARGET)
        sys.exit(1)

    with open(TARGET, "r", encoding="utf-8") as f:
        src = f.read()

    if MARKER in src:
        print("SKIP: %s already present - patch already applied." % MARKER)
        sys.exit(0)

    if W1 not in src:
        print("ERROR: Wave 1 marker not found - run Wave 1 patcher first.")
        sys.exit(1)

    edits = []

    # ----- Edit 1: relocate the Wave 1 CSS block -----
    si = src.find(W1_CSS_START)
    ei = src.find(W1_CSS_END)
    if si == -1 or ei == -1 or ei < si:
        print("ERROR: Wave 1 CSS START/END markers not found or misordered.")
        sys.exit(1)
    ei_full = ei + len(W1_CSS_END)
    css_block = src[si:ei_full]  # the block itself, markers inclusive

    # Excise it (plus a single trailing newline if present) from current spot.
    after = src[ei_full:]
    lead_nl = ""
    if after.startswith("\n"):
        after = after[1:]
        lead_nl = "\n"
    src_without = src[:si] + after

    # Tag the relocated block so we can tell it moved (idempotency belt-and-braces).
    css_block_tagged = css_block.replace(
        W1_CSS_START,
        W1_CSS_START + "\n/* " + MARKER + ": relocated after TESTS CSS so it wins the cascade */",
        1)

    # Re-insert after TESTS CSS-END.
    if TESTS_CSS_END not in src_without:
        print("ERROR: TESTS CSS-END anchor not found.")
        sys.exit(1)
    if src_without.count(TESTS_CSS_END) != 1:
        print("ERROR: TESTS CSS-END anchor not unique.")
        sys.exit(1)
    src = src_without.replace(
        TESTS_CSS_END,
        TESTS_CSS_END + "\n" + css_block_tagged,
        1)
    edits.append("relocated Wave 1 CSS block to after TESTS CSS-END")

    # ----- Edit 2: measureV2Ribbon hooks in 8 render functions -----
    for prefix, render_name in RENDER_HOOKS:
        anchor = build_render_anchor(prefix, render_name)
        repl = build_render_replacement(prefix, render_name)
        if anchor not in src:
            print("ERROR: render anchor for %s not found." % render_name)
            sys.exit(1)
        if src.count(anchor) != 1:
            print("ERROR: render anchor for %s not unique (%d)." % (render_name, src.count(anchor)))
            sys.exit(1)
        src = src.replace(anchor, repl, 1)
        edits.append("measureV2Ribbon hook in render%s" % render_name)

    if CT_ANCHOR not in src:
        print("ERROR: renderTests (ct) anchor not found.")
        sys.exit(1)
    if src.count(CT_ANCHOR) != 1:
        print("ERROR: renderTests (ct) anchor not unique (%d)." % src.count(CT_ANCHOR))
        sys.exit(1)
    src = src.replace(CT_ANCHOR, CT_REPLACEMENT, 1)
    edits.append("measureV2Ribbon hook in renderTests")

    # ----- validate -----
    tmp = os.path.join(SCRIPT_DIR, "_wave1b_validate.s14check")
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

    # ----- atomic write -----
    final_tmp = TARGET + ".wave1btmp"
    with open(final_tmp, "w", encoding="utf-8") as f:
        f.write(src)
    os.replace(final_tmp, TARGET)

    # ----- post-write verification -----
    with open(TARGET, "r", encoding="utf-8") as f:
        check = f.read()
    print("")
    print("Edits applied:")
    for e in edits:
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
    # CSS block must now appear AFTER the TESTS CSS-END, not before it.
    pos_tests_end = check.find(TESTS_CSS_END)
    pos_w1_css = check.find(W1_CSS_START)
    chk("Wave 1 CSS now after TESTS CSS-END",
        pos_w1_css > pos_tests_end and pos_tests_end > -1)
    chk("exactly one Wave 1 CSS-START", check.count(W1_CSS_START) == 1)
    chk("exactly one Wave 1 CSS-END", check.count(W1_CSS_END) == 1)
    chk("relocation tag present", (MARKER + ": relocated after TESTS CSS") in check)
    chk("8 measureV2Ribbon render hooks",
        check.count("if (window.measureV2Ribbon) measureV2Ribbon();  /* " + MARKER + " */") == 8)
    chk("ends with newline", check.endswith("\n"))
    md5 = hashlib.md5(check.encode("utf-8")).hexdigest()
    print("")
    print("  build_dashboard.py md5: %s" % md5)
    print("  size: %d bytes" % len(check.encode("utf-8")))
    if not ok:
        print("\nONE OR MORE CHECKS FAILED - inspect before building.")
        sys.exit(1)
    print("\nWave 1b corrective patch applied cleanly.")


if __name__ == "__main__":
    main()
