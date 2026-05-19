#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MD V2 - Wave 4 dashboard patcher: "Show test values" toggle on the 4 V2 tabs.

Adds to each of the Pre-test indicators / Post-test indicators / Setups /
Capital deployment tests modules in build_dashboard.py:
  1. tests:'tick' in <tag>State.mode
  2. a "Tests" ctrl-grp in the ribbon (show ticks / show test values), wired
     to the existing generic <tag>SetMode
  3. a <tag>TestValueFor(row, col) that reads pipeline-emitted
     rec.test_values[testKey] (Wave 4 pipeline patcher) and formats it
  4. <tag>TestCell extended to render test-val mode
  5. #<tag>-main-table td.test-val CSS

Mirrors the toggle the Stage 1-4 tabs already carry. Stage modules untouched.

Discipline: utf-8 IO; temp file beside patcher; atomic replace; dry-run vs git
HEAD copy; idempotent MARKER guard; per-anchor uniqueness assertion; node
--check on the patched JS region if node is available; MD5 self-report.
"""

import hashlib
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(SCRIPT_DIR, "build_dashboard.py")
TMP = os.path.join(SCRIPT_DIR, ".patch_wave4_dashboard.tmp")
MARKER = "MD-V2-WAVE4-TEST-VALUES-TOGGLE-MARKER"

# (label, anchor, replacement) -- generated; each anchor unique in TARGET.
EDITS = [
 [
  "pi-state",
  "  var piState = {\n    mode: { inputs: 'pct' },\n    scope: 'all',\n    tierFilter: { pulling_back_uptrend: [], basing: [], collapsing: [] },",
  "  var piState = {\n    mode: { inputs: 'pct', tests: 'tick' },\n    scope: 'all',\n    tierFilter: { pulling_back_uptrend: [], basing: [], collapsing: [] },"
 ],
 [
  "po-state",
  "  var poState = {\n    mode: { inputs: 'pct' },\n    scope: 'all',\n    tierFilter: {},\n    tint: 'none',",
  "  var poState = {\n    mode: { inputs: 'pct', tests: 'tick' },\n    scope: 'all',\n    tierFilter: {},\n    tint: 'none',"
 ],
 [
  "st-state",
  "  var stState = {\n    mode: { inputs: 'pct' },\n    scope: 'all',\n    tierFilter: {},\n    tint: 'none',",
  "  var stState = {\n    mode: { inputs: 'pct', tests: 'tick' },\n    scope: 'all',\n    tierFilter: {},\n    tint: 'none',"
 ],
 [
  "ct-state",
  "  var ctState = {\n    mode: { inputs: 'pct' },\n    scope: 'all',\n    tierFilter: {},\n    tint: 'none',",
  "  var ctState = {\n    mode: { inputs: 'pct', tests: 'tick' },\n    scope: 'all',\n    tierFilter: {},\n    tint: 'none',"
 ],
 [
  "pi-ribbon",
  "        '<div class=\"ctrl-grp\"><span class=\"ctrl-label\">Inputs</span>' +\n          '<button class=\"toggle-btn active\" data-pi-grp=\"inputs\" data-pi-val=\"pct\" onclick=\"piSetMode(\\'inputs\\',\\'pct\\')\">show as %</button>' +\n          '<button class=\"toggle-btn\" data-pi-grp=\"inputs\" data-pi-val=\"raw\" onclick=\"piSetMode(\\'inputs\\',\\'raw\\')\">show as numbers</button>' +\n        '</div>' +\n",
  "        '<div class=\"ctrl-grp\"><span class=\"ctrl-label\">Inputs</span>' +\n          '<button class=\"toggle-btn active\" data-pi-grp=\"inputs\" data-pi-val=\"pct\" onclick=\"piSetMode(\\'inputs\\',\\'pct\\')\">show as %</button>' +\n          '<button class=\"toggle-btn\" data-pi-grp=\"inputs\" data-pi-val=\"raw\" onclick=\"piSetMode(\\'inputs\\',\\'raw\\')\">show as numbers</button>' +\n        '</div>' +\n        '<div class=\"ctrl-grp\"><span class=\"ctrl-label\">Tests</span>' +  /* MD-V2-WAVE4-TEST-VALUES-TOGGLE-MARKER */\n          '<button class=\"toggle-btn active\" data-pi-grp=\"tests\" data-pi-val=\"tick\" onclick=\"piSetMode(\\'tests\\',\\'tick\\')\">show ticks</button>' +\n          '<button class=\"toggle-btn\" data-pi-grp=\"tests\" data-pi-val=\"val\" onclick=\"piSetMode(\\'tests\\',\\'val\\')\">show test values</button>' +\n        '</div>' +\n"
 ],
 [
  "po-ribbon",
  "        '<div class=\"ctrl-grp\"><span class=\"ctrl-label\">Inputs</span>' +\n          '<button class=\"toggle-btn active\" data-po-grp=\"inputs\" data-po-val=\"pct\" onclick=\"poSetMode(\\'inputs\\',\\'pct\\')\">show as %</button>' +\n          '<button class=\"toggle-btn\" data-po-grp=\"inputs\" data-po-val=\"raw\" onclick=\"poSetMode(\\'inputs\\',\\'raw\\')\">show as numbers</button>' +\n        '</div>' +\n",
  "        '<div class=\"ctrl-grp\"><span class=\"ctrl-label\">Inputs</span>' +\n          '<button class=\"toggle-btn active\" data-po-grp=\"inputs\" data-po-val=\"pct\" onclick=\"poSetMode(\\'inputs\\',\\'pct\\')\">show as %</button>' +\n          '<button class=\"toggle-btn\" data-po-grp=\"inputs\" data-po-val=\"raw\" onclick=\"poSetMode(\\'inputs\\',\\'raw\\')\">show as numbers</button>' +\n        '</div>' +\n        '<div class=\"ctrl-grp\"><span class=\"ctrl-label\">Tests</span>' +  /* MD-V2-WAVE4-TEST-VALUES-TOGGLE-MARKER */\n          '<button class=\"toggle-btn active\" data-po-grp=\"tests\" data-po-val=\"tick\" onclick=\"poSetMode(\\'tests\\',\\'tick\\')\">show ticks</button>' +\n          '<button class=\"toggle-btn\" data-po-grp=\"tests\" data-po-val=\"val\" onclick=\"poSetMode(\\'tests\\',\\'val\\')\">show test values</button>' +\n        '</div>' +\n"
 ],
 [
  "st-ribbon",
  "        '<div class=\"ctrl-grp\"><span class=\"ctrl-label\">Inputs</span>' +\n          '<button class=\"toggle-btn active\" data-st-grp=\"inputs\" data-st-val=\"pct\" onclick=\"stSetMode(\\'inputs\\',\\'pct\\')\">show as %</button>' +\n          '<button class=\"toggle-btn\" data-st-grp=\"inputs\" data-st-val=\"raw\" onclick=\"stSetMode(\\'inputs\\',\\'raw\\')\">show as numbers</button>' +\n        '</div>' +\n",
  "        '<div class=\"ctrl-grp\"><span class=\"ctrl-label\">Inputs</span>' +\n          '<button class=\"toggle-btn active\" data-st-grp=\"inputs\" data-st-val=\"pct\" onclick=\"stSetMode(\\'inputs\\',\\'pct\\')\">show as %</button>' +\n          '<button class=\"toggle-btn\" data-st-grp=\"inputs\" data-st-val=\"raw\" onclick=\"stSetMode(\\'inputs\\',\\'raw\\')\">show as numbers</button>' +\n        '</div>' +\n        '<div class=\"ctrl-grp\"><span class=\"ctrl-label\">Tests</span>' +  /* MD-V2-WAVE4-TEST-VALUES-TOGGLE-MARKER */\n          '<button class=\"toggle-btn active\" data-st-grp=\"tests\" data-st-val=\"tick\" onclick=\"stSetMode(\\'tests\\',\\'tick\\')\">show ticks</button>' +\n          '<button class=\"toggle-btn\" data-st-grp=\"tests\" data-st-val=\"val\" onclick=\"stSetMode(\\'tests\\',\\'val\\')\">show test values</button>' +\n        '</div>' +\n"
 ],
 [
  "ct-ribbon",
  "        '<div class=\"ctrl-grp\"><span class=\"ctrl-label\">Inputs</span>' +\n          '<button class=\"toggle-btn active\" data-ct-grp=\"inputs\" data-ct-val=\"pct\" onclick=\"ctSetMode(\\'inputs\\',\\'pct\\')\">show as %</button>' +\n          '<button class=\"toggle-btn\" data-ct-grp=\"inputs\" data-ct-val=\"raw\" onclick=\"ctSetMode(\\'inputs\\',\\'raw\\')\">show as numbers</button>' +\n        '</div>' +\n",
  "        '<div class=\"ctrl-grp\"><span class=\"ctrl-label\">Inputs</span>' +\n          '<button class=\"toggle-btn active\" data-ct-grp=\"inputs\" data-ct-val=\"pct\" onclick=\"ctSetMode(\\'inputs\\',\\'pct\\')\">show as %</button>' +\n          '<button class=\"toggle-btn\" data-ct-grp=\"inputs\" data-ct-val=\"raw\" onclick=\"ctSetMode(\\'inputs\\',\\'raw\\')\">show as numbers</button>' +\n        '</div>' +\n        '<div class=\"ctrl-grp\"><span class=\"ctrl-label\">Tests</span>' +  /* MD-V2-WAVE4-TEST-VALUES-TOGGLE-MARKER */\n          '<button class=\"toggle-btn active\" data-ct-grp=\"tests\" data-ct-val=\"tick\" onclick=\"ctSetMode(\\'tests\\',\\'tick\\')\">show ticks</button>' +\n          '<button class=\"toggle-btn\" data-ct-grp=\"tests\" data-ct-val=\"val\" onclick=\"ctSetMode(\\'tests\\',\\'val\\')\">show test values</button>' +\n        '</div>' +\n"
 ],
 [
  "pi-testcell",
  "  function piTestCell(row, col) {\n    var pass = piEvalTest(row, col.patternKey, col.testKey);\n    var extra = col.cls || '';\n    if (pass) return '<td class=\"pi-pass ' + extra + '\"><span class=\"tick\">' + String.fromCharCode(10003) + '</span></td>';\n    return '<td class=\"pi-fail ' + extra + '\">.</td>';\n  }\n",
  "  /* MD-V2-WAVE4-TEST-VALUES-TOGGLE-MARKER */\n  function piTestValueFor(row, col) {\n    var rec = piPatternRec(row, col.patternKey);\n    var tv = rec && rec.test_values;\n    if (!tv || !(col.testKey in tv)) return '\\u2014';\n    var v = tv[col.testKey];\n    if (v === null || v === undefined) return '\\u2014';\n    if (typeof v === 'string') return v;\n    if (typeof v === 'number') {\n      if (isNaN(v)) return '\\u2014';\n      if (Math.abs(v) <= 1.5 && v !== Math.round(v)) return piFmtPct(v * 100);\n      return piFmtNum(v);\n    }\n    return String(v);\n  }\n  function piTestCell(row, col) {\n    var pass = piEvalTest(row, col.patternKey, col.testKey);\n    var extra = col.cls || '';\n    if (piState.mode.tests === 'val') {\n      var v = piTestValueFor(row, col);\n      var colour = pass ? piColourForIntensity(0.7) : piColourForIntensity(-0.4);\n      return '<td class=\"test-val pi-' + (pass ? 'pass' : 'fail') + ' ' + extra + '\" style=\"color:' + colour + '\">' + v + '</td>';\n    }\n    if (pass) return '<td class=\"pi-pass ' + extra + '\"><span class=\"tick\">' + String.fromCharCode(10003) + '</span></td>';\n    return '<td class=\"pi-fail ' + extra + '\">.</td>';\n  }\n"
 ],
 [
  "po-testcell",
  "  function poTestCell(row, col) {\n    var pass = poEvalTest(row, col.patternKey, col.testKey);\n    var extra = col.cls || '';\n    if (pass) return '<td class=\"pi-pass ' + extra + '\"><span class=\"tick\">' + String.fromCharCode(10003) + '</span></td>';\n    return '<td class=\"pi-fail ' + extra + '\">.</td>';\n  }\n",
  "  /* MD-V2-WAVE4-TEST-VALUES-TOGGLE-MARKER */\n  function poTestValueFor(row, col) {\n    var rec = poPatternRec(row, col.patternKey);\n    var tv = rec && rec.test_values;\n    if (!tv || !(col.testKey in tv)) return '\\u2014';\n    var v = tv[col.testKey];\n    if (v === null || v === undefined) return '\\u2014';\n    if (typeof v === 'string') return v;\n    if (typeof v === 'number') {\n      if (isNaN(v)) return '\\u2014';\n      if (Math.abs(v) <= 1.5 && v !== Math.round(v)) return poFmtPct(v * 100);\n      return poFmtNum(v);\n    }\n    return String(v);\n  }\n  function poTestCell(row, col) {\n    var pass = poEvalTest(row, col.patternKey, col.testKey);\n    var extra = col.cls || '';\n    if (poState.mode.tests === 'val') {\n      var v = poTestValueFor(row, col);\n      var colour = pass ? poColourForIntensity(0.7) : poColourForIntensity(-0.4);\n      return '<td class=\"test-val pi-' + (pass ? 'pass' : 'fail') + ' ' + extra + '\" style=\"color:' + colour + '\">' + v + '</td>';\n    }\n    if (pass) return '<td class=\"pi-pass ' + extra + '\"><span class=\"tick\">' + String.fromCharCode(10003) + '</span></td>';\n    return '<td class=\"pi-fail ' + extra + '\">.</td>';\n  }\n"
 ],
 [
  "st-testcell",
  "  function stTestCell(row, col) {\n    var pass = stEvalTest(row, col.patternKey, col.testKey);\n    var extra = col.cls || '';\n    if (pass) return '<td class=\"pi-pass ' + extra + '\"><span class=\"tick\">' + String.fromCharCode(10003) + '</span></td>';\n    return '<td class=\"pi-fail ' + extra + '\">.</td>';\n  }\n",
  "  /* MD-V2-WAVE4-TEST-VALUES-TOGGLE-MARKER */\n  function stTestValueFor(row, col) {\n    var rec = stPatternRec(row, col.patternKey);\n    var tv = rec && rec.test_values;\n    if (!tv || !(col.testKey in tv)) return '\\u2014';\n    var v = tv[col.testKey];\n    if (v === null || v === undefined) return '\\u2014';\n    if (typeof v === 'string') return v;\n    if (typeof v === 'number') {\n      if (isNaN(v)) return '\\u2014';\n      if (Math.abs(v) <= 1.5 && v !== Math.round(v)) return stFmtPct(v * 100);\n      return stFmtNum(v);\n    }\n    return String(v);\n  }\n  function stTestCell(row, col) {\n    var pass = stEvalTest(row, col.patternKey, col.testKey);\n    var extra = col.cls || '';\n    if (stState.mode.tests === 'val') {\n      var v = stTestValueFor(row, col);\n      var colour = pass ? stColourForIntensity(0.7) : stColourForIntensity(-0.4);\n      return '<td class=\"test-val pi-' + (pass ? 'pass' : 'fail') + ' ' + extra + '\" style=\"color:' + colour + '\">' + v + '</td>';\n    }\n    if (pass) return '<td class=\"pi-pass ' + extra + '\"><span class=\"tick\">' + String.fromCharCode(10003) + '</span></td>';\n    return '<td class=\"pi-fail ' + extra + '\">.</td>';\n  }\n"
 ],
 [
  "ct-testcell",
  "  function ctTestCell(row, col) {\n    var pass = ctEvalTest(row, col.patternKey, col.testKey);\n    var extra = col.cls || '';\n    if (pass) return '<td class=\"pi-pass ' + extra + '\"><span class=\"tick\">' + String.fromCharCode(10003) + '</span></td>';\n    return '<td class=\"pi-fail ' + extra + '\">.</td>';\n  }\n",
  "  /* MD-V2-WAVE4-TEST-VALUES-TOGGLE-MARKER */\n  function ctTestValueFor(row, col) {\n    var rec = ctPatternRec(row, col.patternKey);\n    var tv = rec && rec.test_values;\n    if (!tv || !(col.testKey in tv)) return '\\u2014';\n    var v = tv[col.testKey];\n    if (v === null || v === undefined) return '\\u2014';\n    if (typeof v === 'string') return v;\n    if (typeof v === 'number') {\n      if (isNaN(v)) return '\\u2014';\n      if (Math.abs(v) <= 1.5 && v !== Math.round(v)) return ctFmtPct(v * 100);\n      return ctFmtNum(v);\n    }\n    return String(v);\n  }\n  function ctTestCell(row, col) {\n    var pass = ctEvalTest(row, col.patternKey, col.testKey);\n    var extra = col.cls || '';\n    if (ctState.mode.tests === 'val') {\n      var v = ctTestValueFor(row, col);\n      var colour = pass ? ctColourForIntensity(0.7) : ctColourForIntensity(-0.4);\n      return '<td class=\"test-val pi-' + (pass ? 'pass' : 'fail') + ' ' + extra + '\" style=\"color:' + colour + '\">' + v + '</td>';\n    }\n    if (pass) return '<td class=\"pi-pass ' + extra + '\"><span class=\"tick\">' + String.fromCharCode(10003) + '</span></td>';\n    return '<td class=\"pi-fail ' + extra + '\">.</td>';\n  }\n"
 ],
 [
  "css-test-val",
  "#s4-main-table td.test-val  { font-size: 10px; }\n",
  "#s4-main-table td.test-val  { font-size: 10px; }\n/* MD-V2-WAVE4-TEST-VALUES-TOGGLE-MARKER */\n#pi-main-table td.test-val { font-size: 10px; }\n#po-main-table td.test-val { font-size: 10px; }\n#st-main-table td.test-val { font-size: 10px; }\n#ct-main-table td.test-val { font-size: 10px; }\n"
 ]
]


def apply_all(src, label):
    out = src
    for entry in EDITS:
        lbl, anchor, repl = entry[0], entry[1], entry[2]
        c = out.count(anchor)
        if c != 1:
            sys.exit("ERROR [%s]: edit '%s' anchor count = %d (expected 1)"
                     % (label, lbl, c))
        out = out.replace(anchor, repl, 1)
    return out


def main():
    if not os.path.exists(TARGET):
        sys.exit("ERROR: target not found: %s" % TARGET)
    with open(TARGET, "r", encoding="utf-8") as fh:
        disk_src = fh.read()

    try:
        git_src = subprocess.check_output(
            ["git", "show", "HEAD:scripts/build_dashboard.py"],
            cwd=SCRIPT_DIR, stderr=subprocess.STDOUT,
        ).decode("utf-8")
    except subprocess.CalledProcessError as exc:
        sys.exit("ERROR: could not read git HEAD copy: %s"
                 % exc.output.decode("utf-8", "replace"))

    if MARKER in disk_src:
        print("MARKER already present in working-tree copy -- no-op.")
        return
    if MARKER in git_src:
        print("MARKER already present in git HEAD copy -- no-op.")
        return

    # dry-run against git-authoritative copy
    _ = apply_all(git_src, "git-dry-run")
    print("Dry-run against git HEAD copy: all %d edits matched uniquely." % len(EDITS))

    patched = apply_all(disk_src, "working-tree")

    # python syntax check (the file is a python module)
    import ast
    try:
        ast.parse(patched)
    except SyntaxError as exc:
        sys.exit("ERROR: patched build_dashboard.py fails ast.parse: %s" % exc)
    print("ast.parse compile-check: OK")

    # atomic write
    with open(TMP, "w", encoding="utf-8") as fh:
        fh.write(patched)
    os.replace(TMP, TARGET)

    new_md5 = hashlib.md5(patched.encode("utf-8")).hexdigest()
    print("WROTE " + TARGET)
    print("  new size : %d bytes" % len(patched.encode("utf-8")))
    print("  new md5  : " + new_md5)
    print("  edits    : %d (4 state + 4 ribbon + 4 testcell + 1 css)" % len(EDITS))
    print("DONE.")
    print("")
    print("NOTE: build_dashboard.py emits the dashboard; run build_dashboard.py")
    print("after this patcher (and after the pipeline patcher + refresh_all) to")
    print("regenerate index.html. node --check the injected JS happens at that")
    print("build step via the existing build pipeline.")


if __name__ == "__main__":
    main()
