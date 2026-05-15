#!/usr/bin/env python3
"""
MD V2 — Split Capital qualification tests tab into two tabs.
  tests_s1pb  : "Stage 1 & N PBs"   — Probing bet (G1) + VCP after S1->2 (G2)
  tests_s2vcp : "S2 VCPs & Retests" — VCP after S2 base (G1) + MA retest (G2)

Run order: this patcher -> build_dashboard.py -> git add -A -> commit -> push
Prerequisite: backup already taken as build_dashboard.py.bak-pre-tests-split-2026-05-15
"""
import sys, os, re, ast, subprocess

MARKER   = 'MD-V2-TESTS-SPLIT-MARKER'
SRC      = 'scripts/build_dashboard.py'

# Locate git root
GIT_ROOT = os.path.dirname(os.path.abspath(__file__))
while not os.path.isdir(os.path.join(GIT_ROOT, '.git')):
    parent = os.path.dirname(GIT_ROOT)
    if parent == GIT_ROOT:
        sys.exit('ERROR: Could not find .git root')
    GIT_ROOT = parent

# ---- Read authoritative copy from git object store ----
result = subprocess.run(['git', 'show', f'HEAD:{SRC}'],
                        capture_output=True, encoding='utf-8', cwd=GIT_ROOT)
if result.returncode != 0:
    sys.exit(f'ERROR: git show failed:\n{result.stderr}')
src = result.stdout

# ---- Idempotency check ----
if MARKER in src:
    print('ALREADY APPLIED — nothing to do.')
    sys.exit(0)

errors = []
applied = []

def replace_one(label, old, new):
    global src
    count = src.count(old)
    if count != 1:
        errors.append(f'  {label}: expected 1 occurrence, found {count}')
        return
    src = src.replace(old, new, 1)
    applied.append(label)

def replace_all(label, old, new):
    global src
    count = src.count(old)
    if count == 0:
        errors.append(f'  {label}: 0 occurrences found (expected >=1)')
        return
    src = src.replace(old, new)
    applied.append(f'{label} ({count}x)')

# ============================================================
# PRE-STEP: Extract the 4 CT pattern objects from the source
# (avoids duplicating large text in this patcher)
# ============================================================
ct_arr_start_tag = '  var CT_PATTERNS = [\n'
ct_arr_end_tag   = '\n  ];\n\n  // Tone -> CSS class fragments'
try:
    ct_s = src.index(ct_arr_start_tag) + len(ct_arr_start_tag)
    ct_e = src.index(ct_arr_end_tag)
    ct_body = src[ct_s:ct_e]
    # Split into 4 pattern objects on the inter-object separator
    raw_pats = re.split(r',\n    (?=\{)', ct_body)
    if len(raw_pats) != 4:
        errors.append(f'PRE-STEP: Expected 4 CT patterns, found {len(raw_pats)}')
    else:
        PAT_MA = raw_pats[0].strip()   # ma_retest_upwards  (original G1)
        PAT_S1 = raw_pats[1].strip()   # vcp_deploy_s1      (original G2)
        PAT_S2 = raw_pats[2].strip()   # vcp_deploy_s2      (original G3)
        PAT_PB = raw_pats[3].strip()   # probing_bet        (original G4)
        # Sanity check keys
        for (p, k) in [(PAT_MA,'ma_retest_upwards'),(PAT_S1,'vcp_deploy_s1'),
                       (PAT_S2,'vcp_deploy_s2'),(PAT_PB,'probing_bet')]:
            if f'"key": "{k}"' not in p:
                errors.append(f'PRE-STEP: Pattern key "{k}" not found in expected slot')
except (ValueError, IndexError) as e:
    errors.append(f'PRE-STEP: {e}')
    PAT_MA = PAT_S1 = PAT_S2 = PAT_PB = ''

# ============================================================
# E1: TABS array — replace single tests entry with two
# ============================================================
replace_one('E1:TABS',
    '    {"id": "tests", "label": "Tests", "accent": "#0F6E56"},',
    '    {"id": "tests_s1pb",  "label": "Stage 1 & N PBs",   "accent": "#BA7517"},  # MD-V2-TESTS-SPLIT-MARKER\n'
    '    {"id": "tests_s2vcp", "label": "S2 VCPs & Retests", "accent": "#185FA5"},  # MD-V2-TESTS-SPLIT-MARKER'
)

# ============================================================
# E2: CSS body[data-active-tab="tests"] — global replace (12 occurrences)
# ============================================================
replace_all('E2:CSS-body-selectors',
    'body[data-active-tab="tests"]',
    'body[data-active-tab^="tests_"]'
)

# ============================================================
# E3: _v2chartTabs
# ============================================================
replace_one('E3:_v2chartTabs',
    '  var _v2chartTabs={stage_1:1,stage_2:1,stage_3:1,stage_4:1,pre_indicators:1,post_indicators:1,setups:1,tests:1,master_overview:1};',
    '  var _v2chartTabs={stage_1:1,stage_2:1,stage_3:1,stage_4:1,pre_indicators:1,post_indicators:1,setups:1,tests_s1pb:1,tests_s2vcp:1,master_overview:1};  /* MD-V2-TESTS-SPLIT-MARKER */'
)

# ============================================================
# E4: _v2ct
# ============================================================
replace_one('E4:_v2ct',
    'var _v2ct={stage_1:1,stage_2:1,stage_3:1,stage_4:1,pre_indicators:1,post_indicators:1,setups:1,tests:1,master_overview:1};',
    'var _v2ct={stage_1:1,stage_2:1,stage_3:1,stage_4:1,pre_indicators:1,post_indicators:1,setups:1,tests_s1pb:1,tests_s2vcp:1,master_overview:1};  /* MD-V2-TESTS-SPLIT-MARKER */'
)

# ============================================================
# E5: V2 mini-nav button for "tests" -> two buttons
# ============================================================
replace_one('E5:V2-nav-buttons',
    """      + '<button class="v2-nav-btn v2-grp-tests" data-v2-tab="tests" onclick="switchTab(\\'tests\\')">Capital deployment tests</button>'""",
    """      + '<button class="v2-nav-btn v2-grp-tests" data-v2-tab="tests_s1pb" onclick="switchTab(\\'tests_s1pb\\')">Stage 1 &amp; N PBs</button>'  /* MD-V2-TESTS-SPLIT-MARKER */\n"""
    """      + '<button class="v2-nav-btn v2-grp-tests" data-v2-tab="tests_s2vcp" onclick="switchTab(\\'tests_s2vcp\\')">S2 VCPs &amp; Retests</button>'"""
)

# ============================================================
# E6: CT module IIFE opening -> factory function signature
# ============================================================
replace_one('E6:CT-IIFE-open',
    "(function() {\n  'use strict';\n\n  // MD-V2-TESTS-S27-MARKER: Capital deployment tests tab",
    "function _buildCTModule(tabId, initPatterns) {  /* MD-V2-TESTS-SPLIT-MARKER */\n  'use strict';\n\n  // MD-V2-TESTS-S27-MARKER: Capital deployment tests tab"
)

# ============================================================
# E7: CT_PATTERNS = [...] -> CT_PATTERNS = initPatterns
# (replace the entire array literal)
# ============================================================
replace_one('E7:CT_PATTERNS-literal',
    ct_arr_start_tag + ct_body + ct_arr_end_tag,
    '  var CT_PATTERNS = initPatterns;  /* MD-V2-TESTS-SPLIT-MARKER: populated by factory caller */\n\n  // Tone -> CSS class fragments'
)

# ============================================================
# E8: Add var _host = null after the tierFilter init loop
# ============================================================
replace_one('E8:_host-init',
    '  var CT_RATING_RANK = { \'Probable\':5,',
    '  var _host = null;  /* MD-V2-TESTS-SPLIT-MARKER: scoped host-element reference */\n  var CT_RATING_RANK = { \'Probable\':5,'
)

# ============================================================
# E9: ctBuildHeaderRow — getElementById -> _host.querySelector
# ============================================================
replace_one('E9:ctBuildHeaderRow-getElementById',
    "    var tr = document.getElementById('ct-col-header-row');\n    if (!tr) return;",
    "    var tr = _host ? _host.querySelector('#ct-col-header-row') : null;  /* MD-V2-TESTS-SPLIT-MARKER */\n    if (!tr) return;"
)

# ============================================================
# E10: ctPatternTiles — getElementById -> _host.querySelector
# ============================================================
replace_one('E10:ctPatternTiles-getElementById',
    "    var tiles = document.getElementById('ct-pattern-tiles');\n    if (!tiles) return;\n    var counts = ctPatternCounts",
    "    var tiles = _host ? _host.querySelector('#ct-pattern-tiles') : null;  /* MD-V2-TESTS-SPLIT-MARKER */\n    if (!tiles) return;\n    var counts = ctPatternCounts"
)

# ============================================================
# E11: ctUpdateScopeCounts — getElementById(id) -> _host.querySelector
# ============================================================
replace_one('E11:ctUpdateScopeCounts-getElementById',
    "    function set(id, n) { var el = document.getElementById(id); if (el) el.textContent = '(' + n + ')'; }\n"
    "    set('ct-cnt-all',      rows.length);",
    "    function set(id, n) { var el = _host ? _host.querySelector('#' + id) : null; if (el) el.textContent = '(' + n + ')'; }  /* MD-V2-TESTS-SPLIT-MARKER */\n"
    "    set('ct-cnt-all',      rows.length);"
)

# ============================================================
# E12: ctRenderRows — getElementById -> _host.querySelector
# ============================================================
replace_one('E12:ctRenderRows-getElementById',
    "    var tbody = document.getElementById('ct-tbody');\n    if (!tbody) return;",
    "    var tbody = _host ? _host.querySelector('#ct-tbody') : null;  /* MD-V2-TESTS-SPLIT-MARKER */\n    if (!tbody) return;"
)

# ============================================================
# E13-E16: Control setters — document.querySelectorAll -> _host.querySelectorAll
# ============================================================
replace_one('E13:ctSetMode-querySelectorAll',
    "    var btns = document.querySelectorAll('button[data-ct-grp=\"' + kind + '\"]');",
    "    var btns = _host ? _host.querySelectorAll('button[data-ct-grp=\"' + kind + '\"]') : [];  /* MD-V2-TESTS-SPLIT-MARKER */"
)
replace_one('E14:ctSetScope-querySelectorAll',
    "    var btns = document.querySelectorAll('button[data-ct-scope]');",
    "    var btns = _host ? _host.querySelectorAll('button[data-ct-scope]') : [];  /* MD-V2-TESTS-SPLIT-MARKER */"
)
replace_one('E15:ctSetTint-querySelectorAll',
    "    var btns = document.querySelectorAll('button[data-ct-tint]');",
    "    var btns = _host ? _host.querySelectorAll('button[data-ct-tint]') : [];  /* MD-V2-TESTS-SPLIT-MARKER */"
)
replace_one('E16:ctSetPort-querySelectorAll',
    "    var btns = document.querySelectorAll('button[data-ct-port]');",
    "    var btns = _host ? _host.querySelectorAll('button[data-ct-port]') : [];  /* MD-V2-TESTS-SPLIT-MARKER */"
)

# ============================================================
# E17: ctBuildScaffold host lookup — getElementById + set _host
# ============================================================
replace_one('E17:ctBuildScaffold-host',
    "    var host = document.getElementById('tab-tests');\n    if (!host) return false;\n    if (host.querySelector('#ct-main-table')) return true;",
    "    var host = document.getElementById('tab-' + tabId);  /* MD-V2-TESTS-SPLIT-MARKER */\n    if (!host) return false;\n    _host = host;\n    if (host.querySelector('#ct-main-table')) return true;"
)

# ============================================================
# E18: ctBuildScaffold event listener — getElementById('ct-pattern-tiles')
# (after host.innerHTML = html; — uses host directly since it's in scope)
# ============================================================
replace_one('E18:ctBuildScaffold-tiles-listener',
    "    host.innerHTML = html;\n    var tiles = document.getElementById('ct-pattern-tiles');\n    if (tiles) {\n      tiles.addEventListener",
    "    host.innerHTML = html;\n    var tiles = host.querySelector('#ct-pattern-tiles');  /* MD-V2-TESTS-SPLIT-MARKER */\n    if (tiles) {\n      tiles.addEventListener"
)

# ============================================================
# E19: ctBuildScaffold event listener — getElementById('ct-col-header-row')
# ============================================================
replace_one('E19:ctBuildScaffold-hdr-listener',
    "    var hdr = document.getElementById('ct-col-header-row');\n    if (hdr) {\n      hdr.addEventListener",
    "    var hdr = host.querySelector('#ct-col-header-row');  /* MD-V2-TESTS-SPLIT-MARKER */\n    if (hdr) {\n      hdr.addEventListener"
)

# ============================================================
# E20: Remove window.ctSet* exports from inside the factory
# (they'll be replaced by global dispatchers outside the factory)
# ============================================================
replace_one('E20:remove-window-ct-exports',
    "  window.ctSetMode = ctSetMode;\n"
    "  window.ctSetScope = ctSetScope;\n"
    "  window.ctSetTint = ctSetTint;\n"
    "  window.ctSetPort = ctSetPort;\n"
    "  window.ctToggleTier = ctToggleTier;\n"
    "  window.ctSelectAllTiers = ctSelectAllTiers;\n"
    "  window.ctOnSort = ctOnSort;\n"
    "\n"
    "  // --- scaffold ---",
    "  /* MD-V2-TESTS-SPLIT-MARKER: window.ct* dispatchers moved outside factory — see end of module */\n"
    "\n"
    "  // --- scaffold ---"
)

# ============================================================
# E21: _mdJump tab check — 'tests' -> tabId
# ============================================================
replace_one('E21:_mdJump-tab-check',
    "      if (j && j.tab === 'tests') {",
    "      if (j && j.tab === tabId) {  /* MD-V2-TESTS-SPLIT-MARKER */"
)

# ============================================================
# E22: Closing IIFE + window exports -> factory return + calls + dispatchers
# ============================================================
# Tab 1: PB (G1) + VCP_S1 (G2)   Tab 2: VCP_S2 (G1) + MA_retest (G2)
factory_calls = (
    "  return {\n"
    "    render: renderTests,\n"
    "    setMode: ctSetMode, setScope: ctSetScope, setTint: ctSetTint, setPort: ctSetPort,\n"
    "    toggleTier: ctToggleTier, selectAllTiers: ctSelectAllTiers, onSort: ctOnSort\n"
    "  };\n"
    "}  /* end _buildCTModule  MD-V2-TESTS-SPLIT-MARKER */\n"
    "\n"
    "/* MD-V2-TESTS-SPLIT-MARKER: Two-tab split — factory instantiations */\n"
    "var _ctMods = {};\n"
    "\n"
    "/* Tab 1: Stage 1 & N PBs — Probing bet (G1) + VCP after S1->2 (G2) */\n"
    "var _ctModS1pb = _buildCTModule('tests_s1pb', [\n"
    "    " + PAT_PB + ",\n"
    "    " + PAT_S1 + "\n"
    "]);\n"
    "\n"
    "/* Tab 2: S2 VCPs & Retests — VCP after S2 base (G1) + MA retest (G2) */\n"
    "var _ctModS2vcp = _buildCTModule('tests_s2vcp', [\n"
    "    " + PAT_S2 + ",\n"
    "    " + PAT_MA + "\n"
    "]);\n"
    "\n"
    "_ctMods['tests_s1pb']  = _ctModS1pb;\n"
    "_ctMods['tests_s2vcp'] = _ctModS2vcp;\n"
    "\n"
    "/* Global render exports */\n"
    "window.renderTestsS1pb  = _ctModS1pb.render;\n"
    "window.renderTestsS2vcp = _ctModS2vcp.render;\n"
    "window.renderTests      = _ctModS1pb.render;  /* backward compat */\n"
    "window.renderCapTests   = _ctModS1pb.render;  /* backward compat */\n"
    "\n"
    "/* Global control dispatchers — route to whichever CT module is active */\n"
    "window.ctSetMode        = function(k,v){ var m=_ctMods[currentTab]; if(m) m.setMode(k,v); };\n"
    "window.ctSetScope       = function(s){ var m=_ctMods[currentTab]; if(m) m.setScope(s); };\n"
    "window.ctSetTint        = function(t){ var m=_ctMods[currentTab]; if(m) m.setTint(t); };\n"
    "window.ctSetPort        = function(p){ var m=_ctMods[currentTab]; if(m) m.setPort(p); };\n"
    "window.ctToggleTier     = function(pk,t){ var m=_ctMods[currentTab]; if(m) m.toggleTier(pk,t); };\n"
    "window.ctSelectAllTiers = function(pk){ var m=_ctMods[currentTab]; if(m) m.selectAllTiers(pk); };\n"
    "window.ctOnSort         = function(k){ var m=_ctMods[currentTab]; if(m) m.onSort(k); };\n"
    "\n"
    "/* MD-V2-TESTS-MARKER-END */"
)

replace_one('E22:CT-module-close',
    "  window.renderTests = renderTests;\n"
    "  window.renderCapTests = renderTests;\n"
    "\n"
    "})();\n"
    "\n"
    "/* MD-V2-TESTS-MARKER-END */",
    factory_calls
)

# ============================================================
# E23-E26: MO_ROWS tabId updates
# ============================================================
replace_one('E23:MO_ROWS-ma_retest',
    "tabId:'tests', patternKey:'ma_retest_upwards'",
    "tabId:'tests_s2vcp', patternKey:'ma_retest_upwards'  /* MD-V2-TESTS-SPLIT-MARKER */"
)
replace_one('E24:MO_ROWS-vcp_deploy_s1',
    "tabId:'tests', patternKey:'vcp_deploy_s1'",
    "tabId:'tests_s1pb', patternKey:'vcp_deploy_s1'  /* MD-V2-TESTS-SPLIT-MARKER */"
)
replace_one('E25:MO_ROWS-vcp_deploy_s2',
    "tabId:'tests', patternKey:'vcp_deploy_s2'",
    "tabId:'tests_s2vcp', patternKey:'vcp_deploy_s2'  /* MD-V2-TESTS-SPLIT-MARKER */"
)
replace_one('E26:MO_ROWS-probing_bet',
    "tabId:'tests', patternKey:'probing_bet'",
    "tabId:'tests_s1pb', patternKey:'probing_bet'  /* MD-V2-TESTS-SPLIT-MARKER */"
)

# ============================================================
# E27: renderTab dispatch — replace single tests line with two
# ============================================================
replace_one('E27:renderTab-dispatch',
    "  else if(id===\"tests\")renderTests();  /* MD-V2-TESTS-MARKER MD-V2-TESTS-S27-MARKER: was renderCapTests (undefined) */",
    "  else if(id===\"tests_s1pb\")renderTestsS1pb();  /* MD-V2-TESTS-SPLIT-MARKER */\n"
    "  else if(id===\"tests_s2vcp\")renderTestsS2vcp();  /* MD-V2-TESTS-SPLIT-MARKER */"
)

# ============================================================
# Report and bail if any errors
# ============================================================
if errors:
    print('ERRORS — patcher aborted, file NOT written:')
    for e in errors:
        print(e)
    sys.exit(1)

print(f'Applied {len(applied)} replacements:')
for a in applied:
    print(f'  {a}')

# ============================================================
# Sanity check: MARKER must now be present; "tests_s1pb" must exist
# ============================================================
assert MARKER in src, 'MARKER missing after apply — abort'
assert 'tests_s1pb' in src, 'tests_s1pb missing after apply — abort'
assert 'tests_s2vcp' in src, 'tests_s2vcp missing after apply — abort'
assert src.count(MARKER) >= 20, f'Expected >= 20 MARKER occurrences, got {src.count(MARKER)}'

# ============================================================
# py_compile validation
# ============================================================
import tempfile, py_compile
with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as tf:
    tf.write(src)
    tmp = tf.name
try:
    py_compile.compile(tmp, doraise=True)
    print('py_compile: OK')
except py_compile.PyCompileError as e:
    os.unlink(tmp)
    print(f'py_compile FAILED: {e}')
    sys.exit(1)
finally:
    if os.path.exists(tmp):
        os.unlink(tmp)

# ============================================================
# Write output
# ============================================================
out_path = os.path.join(GIT_ROOT, SRC)
with open(out_path, 'w', encoding='utf-8') as f:
    f.write(src)

import hashlib
md5 = hashlib.md5(src.encode('utf-8')).hexdigest()
print(f'Written: {out_path}')
print(f'MD5: {md5}')
print(f'Size: {len(src):,} bytes')
print('Done. Run: python scripts/build_dashboard.py')
