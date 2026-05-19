#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MD V2 — Wave 2 patcher (14-May-26)
Capital deployment tests tab only. Two fixes in build_dashboard.py:

  (a) SUB-GROUP ROW. Insert a third header row between the group-header
      row and the col-header row that visually splits each pattern's
      column block into four labelled sub-groups:
        Rating   - the rating + score columns (colspan 2)
        Setup    - the setup / gate / VCP test columns (the "is it set up?"
                   columns) -- colspan = count of tests with group in
                   {setup, gate, vcp}
        Trigger  - the trigger test columns (the "has it just fired?"
                   columns) -- colspan = count of tests with group=trigger
        Context  - the Probing-bet Collapsing-rating info column (when
                   present) + the two L5D/L20D window columns
      Inputs and Stage ratings get a single empty sub-group spacer cell
      each so every column sits under exactly one sub-group cell.
      The CT header stack becomes 3 rows: group-header -> sub-group ->
      col-header. The Wave 1 CT sticky CSS is re-stacked to match.

  (b) RIGHT-EDGE OVERFLOW. The CT table is ~3340px wide but its
      `.table-wrap` had `overflow: visible` and no width handling, so
      ~1450px of columns spilled off the right edge unreachable. Fix:
      `.table-wrap { overflow-x: auto }` scoped to all V2 tabs (fixes CT
      now; PO/Setups proactively, they can overflow on narrower screens).
      overflow-y stays visible so the Wave 1 viewport-anchored sticky
      `top:` offsets are unaffected -- the wrap scrolls horizontally only.

Idempotent via MARKER. Platform discipline: encoding="utf-8" on all IO;
temp file beside patcher; atomic write at end; ASCII-only literals.
"""

import os, sys, hashlib

MARKER = "MD-V2-WAVE2-TESTS-SUBGROUP-MARKER"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(SCRIPT_DIR, "build_dashboard.py")

# ----------------------------------------------------------------------
# Edit 1 - scaffold: build subGroupHtml and insert the <tr>.
# Anchor: the two theadRows += lines for the CT table (unique - the only
# group-header/col-header pair that references "ct-col-header-row").
# ----------------------------------------------------------------------
SCAFFOLD_ANCHOR = (
    "    theadRows += '<tr class=\"group-header-row\">' + groupHtml + '</tr>';\n"
    "    theadRows += '<tr class=\"col-header-row\" id=\"ct-col-header-row\"></tr>';"
)

SCAFFOLD_NEW = (
    "    // " + MARKER + ": build the sub-group row. Each pattern block\n"
    "    // splits into Rating | Setup | Trigger | Context sub-groups.\n"
    "    // group in {setup,gate,vcp} -> Setup; group=trigger -> Trigger.\n"
    "    var subGroupHtml = '<th class=\"sg-spacer\" colspan=\"' + CT_INPUT_COUNT + '\"></th>' +\n"
    "                       '<th class=\"sg-spacer\" colspan=\"' + CT_STAGEINFO_COUNT + '\"></th>';\n"
    "    for (var sp = 0; sp < CT_PATTERNS.length; sp++) {\n"
    "      var spat = CT_PATTERNS[sp];\n"
    "      var sgi = sp + 1;\n"
    "      var setupCount = 0, triggerCount = 0;\n"
    "      for (var st = 0; st < spat.tests.length; st++) {\n"
    "        var grp = spat.tests[st].group;\n"
    "        if (grp === 'trigger') triggerCount++;\n"
    "        else setupCount++;\n"
    "      }\n"
    "      var contextCount = 2 + (spat.key === 'probing_bet' ? 1 : 0);\n"
    "      subGroupHtml += '<th class=\"sub-g sub-g-rating sub-g' + sgi + '\" colspan=\"2\">Rating</th>';\n"
    "      if (setupCount > 0) subGroupHtml += '<th class=\"sub-g sub-g-setup sub-g' + sgi + '\" colspan=\"' + setupCount + '\">Setup</th>';\n"
    "      if (triggerCount > 0) subGroupHtml += '<th class=\"sub-g sub-g-trigger sub-g' + sgi + '\" colspan=\"' + triggerCount + '\">Trigger</th>';\n"
    "      subGroupHtml += '<th class=\"sub-g sub-g-context sub-g' + sgi + '\" colspan=\"' + contextCount + '\">Context</th>';\n"
    "    }\n"
    "    theadRows += '<tr class=\"group-header-row\">' + groupHtml + '</tr>';\n"
    "    theadRows += '<tr class=\"sub-group-row\">' + subGroupHtml + '</tr>';\n"
    "    theadRows += '<tr class=\"col-header-row\" id=\"ct-col-header-row\"></tr>';"
)

# ----------------------------------------------------------------------
# Edit 2 - CSS: replace the Wave 1 CT 2-row sticky block with a 3-row
# stack, and add sub-group-row styling. Anchor: the exact Wave 1 CT block
# (the comment + the two rules), which is unique.
# ----------------------------------------------------------------------
CSS_CT_ANCHOR = (
    "/* CT (Capital deployment tests): 2 header rows today. Wave 2 adds a 3rd\n"
    "   (sub-group) row and will re-stack these \xe2\x80\x94 this is the 2-row state. */\n"
    "#ct-main-table thead tr.group-header-row th {\n"
    "  position: sticky;\n"
    "  top: calc(var(--header-height) + var(--v2-ribbon-h));\n"
    "  z-index: 71;\n"
    "}\n"
    "#ct-main-table thead tr.col-header-row th {\n"
    "  position: sticky;\n"
    "  top: calc(var(--header-height) + var(--v2-ribbon-h) + 24px);\n"
    "  z-index: 70;\n"
    "}"
).replace("\xe2\x80\x94", "—")

CSS_CT_NEW = (
    "/* " + MARKER + ": CT now has 3 header rows -\n"
    "   group-header -> sub-group -> col-header. Re-stacked from the Wave 1\n"
    "   2-row state. Row heights: group ~24px, sub-group ~22px. */\n"
    "#ct-main-table thead tr.group-header-row th {\n"
    "  position: sticky;\n"
    "  top: calc(var(--header-height) + var(--v2-ribbon-h));\n"
    "  z-index: 72;\n"
    "}\n"
    "#ct-main-table thead tr.sub-group-row th {\n"
    "  position: sticky;\n"
    "  top: calc(var(--header-height) + var(--v2-ribbon-h) + 24px);\n"
    "  z-index: 71;\n"
    "  background: #f7f3e6 !important;\n"
    "  font-size: 8.5px;\n"
    "  text-transform: uppercase;\n"
    "  font-weight: 700;\n"
    "  letter-spacing: 0.5px;\n"
    "  padding: 4px 3px;\n"
    "  cursor: default;\n"
    "  line-height: 1.2;\n"
    "  color: #7a7560;\n"
    "}\n"
    "#ct-main-table thead tr.sub-group-row th:hover { background: #f7f3e6 !important; }\n"
    "#ct-main-table thead tr.sub-group-row th.sg-spacer { background: #fbfaf5 !important; }\n"
    "#ct-main-table thead tr.sub-group-row th.sub-g-rating  { color: #555; }\n"
    "#ct-main-table thead tr.sub-group-row th.sub-g-setup   { color: #4a6a8a; border-bottom: 2px solid rgba(74,106,138,0.40); }\n"
    "#ct-main-table thead tr.sub-group-row th.sub-g-trigger { color: #9a5a2a; border-bottom: 2px solid rgba(154,90,42,0.45); }\n"
    "#ct-main-table thead tr.sub-group-row th.sub-g-context { color: #8a8674; }\n"
    "#ct-main-table thead tr.col-header-row th {\n"
    "  position: sticky;\n"
    "  top: calc(var(--header-height) + var(--v2-ribbon-h) + 46px);\n"
    "  z-index: 70;\n"
    "}"
)

# ----------------------------------------------------------------------
# Edit 3 - CSS: .table-wrap overflow-x:auto for all V2 tabs. Insert just
# before the Wave 1 CSS-END marker so it lives inside the (cascade-winning)
# relocated Wave 1 block.
# ----------------------------------------------------------------------
CSS_OVERFLOW_ANCHOR = "/* MD-V2-WAVE1-FROZEN-HEADERS-MARKER-CSS-END */"

CSS_OVERFLOW_NEW = (
    "/* " + MARKER + ": horizontal scroll on the table wrap for every V2\n"
    "   tab. The CT table is ~3340px wide; .table-wrap had overflow:visible\n"
    "   so the right-hand columns spilled off-screen unreachable. overflow-x\n"
    "   auto gives a horizontal scrollbar; overflow-y stays visible so the\n"
    "   viewport-anchored sticky header `top:` offsets are unaffected. */\n"
    "body[data-active-tab^=\"stage_\"] .table-wrap,\n"
    "body[data-active-tab=\"pre_indicators\"] .table-wrap,\n"
    "body[data-active-tab=\"post_indicators\"] .table-wrap,\n"
    "body[data-active-tab=\"setups\"] .table-wrap,\n"
    "body[data-active-tab=\"tests\"] .table-wrap,\n"
    "body[data-active-tab=\"master_overview\"] .table-wrap {\n"
    "  overflow-x: auto;\n"
    "  overflow-y: visible;\n"
    "}\n"
    "/* MD-V2-WAVE1-FROZEN-HEADERS-MARKER-CSS-END */"
)


def main():
    if not os.path.exists(TARGET):
        print("ERROR: target not found: %s" % TARGET)
        sys.exit(1)

    with open(TARGET, "r", encoding="utf-8") as f:
        src = f.read()

    if MARKER in src:
        print("SKIP: %s already present - patch already applied." % MARKER)
        sys.exit(0)

    if "MD-V2-WAVE1-FROZEN-HEADERS-MARKER" not in src:
        print("ERROR: Wave 1 marker not found - run Wave 1 + 1b patchers first.")
        sys.exit(1)

    edits = []

    # --- Edit 1: scaffold sub-group row ---
    if SCAFFOLD_ANCHOR not in src:
        print("ERROR: CT scaffold theadRows anchor not found.")
        sys.exit(1)
    if src.count(SCAFFOLD_ANCHOR) != 1:
        print("ERROR: CT scaffold anchor not unique (%d)." % src.count(SCAFFOLD_ANCHOR))
        sys.exit(1)
    src = src.replace(SCAFFOLD_ANCHOR, SCAFFOLD_NEW, 1)
    edits.append("CT scaffold: sub-group <tr> inserted")

    # --- Edit 2: CT CSS re-stack to 3 rows ---
    if CSS_CT_ANCHOR not in src:
        print("ERROR: Wave 1 CT CSS block anchor not found.")
        sys.exit(1)
    if src.count(CSS_CT_ANCHOR) != 1:
        print("ERROR: Wave 1 CT CSS anchor not unique (%d)." % src.count(CSS_CT_ANCHOR))
        sys.exit(1)
    src = src.replace(CSS_CT_ANCHOR, CSS_CT_NEW, 1)
    edits.append("CT CSS: re-stacked to 3 header rows + sub-group styling")

    # --- Edit 3: overflow-x on .table-wrap ---
    if CSS_OVERFLOW_ANCHOR not in src:
        print("ERROR: Wave 1 CSS-END anchor not found.")
        sys.exit(1)
    if src.count(CSS_OVERFLOW_ANCHOR) != 1:
        print("ERROR: Wave 1 CSS-END anchor not unique (%d)." % src.count(CSS_OVERFLOW_ANCHOR))
        sys.exit(1)
    src = src.replace(CSS_OVERFLOW_ANCHOR, CSS_OVERFLOW_NEW, 1)
    edits.append(".table-wrap overflow-x:auto for all V2 tabs")

    # --- validate ---
    tmp = os.path.join(SCRIPT_DIR, "_wave2_validate.s14check")
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
    final_tmp = TARGET + ".wave2tmp"
    with open(final_tmp, "w", encoding="utf-8") as f:
        f.write(src)
    os.replace(final_tmp, TARGET)

    # --- post-write verification ---
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
    chk("sub-group <tr> in scaffold",
        "theadRows += '<tr class=\"sub-group-row\">' + subGroupHtml + '</tr>';" in check)
    chk("subGroupHtml builder present", "var subGroupHtml =" in check)
    chk("4 sub-group labels present",
        all(s in check for s in ['>Rating</th>', '>Setup</th>', '>Trigger</th>', '>Context</th>']))
    chk("CT 3-row stack: sub-group-row sticky rule",
        "#ct-main-table thead tr.sub-group-row th {" in check)
    chk("CT col-header re-stacked to +46px",
        "top: calc(var(--header-height) + var(--v2-ribbon-h) + 46px);" in check)
    chk("old Wave 1 CT 2-row comment gone",
        "this is the 2-row state" not in check)
    chk(".table-wrap overflow-x rule present",
        'body[data-active-tab="tests"] .table-wrap,' in check and "overflow-x: auto;" in check)
    chk("ends with newline", check.endswith("\n"))
    md5 = hashlib.md5(check.encode("utf-8")).hexdigest()
    print("")
    print("  build_dashboard.py md5: %s" % md5)
    print("  size: %d bytes" % len(check.encode("utf-8")))
    if not ok:
        print("\nONE OR MORE CHECKS FAILED - inspect before building.")
        sys.exit(1)
    print("\nWave 2 patch applied cleanly.")


if __name__ == "__main__":
    main()
