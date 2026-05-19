"""
=============================================================================
PATCHER — setups_healthy_retest dashboard tab (Healthy Retest of MA)
=============================================================================
Project: SA - Master Dashboard
Session: S47 (18-May-2026), Task 2 (§6.1)
Decision: D-MD-V2-108 (locked 18-May-2026), extends S46 pipeline work
Author: [W] Watson (SYSTEMS ARCHITECT role) under Richard's direction
Template: PATCHER-TEMPLATE.py (D-MD-INFRA-5 text-mode I/O)

WHAT THIS PATCHER DOES
----------------------
Adds a new standalone dashboard tab "setups_healthy_retest" rendering the
S46 pipeline's md["tests"]["healthy_retest"] 13-criterion test.

Changes made to build_dashboard.py:
  1. TABS array entry (after the existing "tests" entry)
  2. IMPLEMENTED_TABS entry
  3. Nav button in the Capital deployment group
  4. Chart wiring in _v2chartTabs and _v2ct objects
  5. CSS block for #tab-setups_healthy_retest
  6. Self-contained render module (IIFE) modelled on the existing renderTests
  7. renderTab dispatcher case
  8. CSS selectors for V2 tab chrome (legacy suppression, nav, header, etc.)

Data source: md_v2.tests.healthy_retest per stock, with 13 criteria:
  Group A (hard precondition): g1_stage_2_qualifies
  Group B.1 (MT uptrend):     g2_b1_50d_rising, g2_b2_150d_rising
  Group B.2 (NT pullback):    g2_b3_5d_declining, g2_b4_10d_declining
  Group C (setup):             g3_c1 through g3_c6 (6 healthy-retest setup tests)
  Group D (trigger):           g4_d1_reclaimed_ma, g4_d2_confirmation_close_ge2pct

Rating ladder:
  Qualified = Probable + g4_d2 (i.e. Plausible + d1 + d2)
  Probable  = Plausible + g4_d1
  Plausible = g1 + g2_b1 + g2_b2 + g2_b3 + g2_b4 + any 3/6 of g3_c1..c6
  Possible  = g1 + g2_b1 + g2_b2 + g2_b3 + g2_b4
  None      = anything else

WHAT THIS PATCHER DOES NOT DO
-----------------------------
- Does NOT modify generate_master_data.py (pipeline already has the test)
- Does NOT remove the legacy "tests" tab (coexistence during transition)
- Does NOT add the "when qualified" day-and-date column (deferred)

USAGE
-----
1. Dry-run:  python3 scripts/patch_md_v2_tab_healthy_retest_s47_2026_05_18.py --test
2. Apply:    python scripts/patch_md_v2_tab_healthy_retest_s47_2026_05_18.py
             python scripts/build_dashboard.py
             git add scripts/build_dashboard.py index.html
             git commit -m "feat(MD V2 S47): healthy-retest standalone tab (13-criterion, S46 pipeline)"
=============================================================================
"""
from __future__ import annotations
import ast
import datetime as _dt
import difflib
import hashlib
import os
import py_compile
import subprocess
import sys
import tempfile

# ============ CONFIGURE ME ============================================
REPO_ROOT_HINT = "master-dashboard"
TARGET_REL     = os.path.join("scripts", "build_dashboard.py")
MARKER         = "MD-V2-S47-TAB-HEALTHY-RETEST-MARKER"
BAK_TAG        = "s47-tab-hr"
ENABLE_PY_COMPILE = True
# ======================================================================

# --- Seven anchors, seven replacements (one per insertion point) -------

# 1. TABS array: insert after the existing tests entry
ANCHOR_1 = '    # MD-V2-TESTS-MARKER - Capital qualification tests (3 tests)\n    {"id": "tests", "label": "Tests", "accent": "#0F6E56"},'
REPLACE_1 = ('    # MD-V2-TESTS-MARKER - Capital qualification tests (3 tests)\n'
             '    {"id": "tests", "label": "Tests", "accent": "#0F6E56"},\n'
             '    # MD-V2-S47-TAB-HEALTHY-RETEST-MARKER - Healthy Retest of MA (13-criterion standalone)\n'
             '    {"id": "setups_healthy_retest", "label": "Healthy Retest", "accent": "#2E7D32"},')

# 2. IMPLEMENTED_TABS: insert after "tests"
ANCHOR_2 = '    "tests",  # MD-V2-TESTS-MARKER'
REPLACE_2 = ('    "tests",  # MD-V2-TESTS-MARKER\n'
             '    "setups_healthy_retest",  # MD-V2-S47-TAB-HEALTHY-RETEST-MARKER')

# 3. Nav button: insert after the existing "Capital deployment tests" button
ANCHOR_3 = "      + '<button class=\"v2-nav-btn v2-grp-tests\" data-v2-tab=\"tests\" onclick=\"switchTab(\\'tests\\')\">Capital deployment tests</button>'"
REPLACE_3 = ("      + '<button class=\"v2-nav-btn v2-grp-tests\" data-v2-tab=\"tests\" onclick=\"switchTab(\\'tests\\')\">Capital deployment tests</button>'\n"
             "      + '<button class=\"v2-nav-btn v2-grp-tests\" data-v2-tab=\"setups_healthy_retest\" onclick=\"switchTab(\\'setups_healthy_retest\\')\">Healthy Retest</button>'  /* MD-V2-S47-TAB-HEALTHY-RETEST-MARKER */")

# 4. Chart wiring - _v2chartTabs object (line ~2702)
ANCHOR_4 = 'var _v2chartTabs={stage_1:1,stage_2:1,stage_3:1,stage_4:1,pre_indicators:1,post_indicators:1,setups_s1pb:1,setups_s2vcp:1,tests:1,master_overview:1};'
REPLACE_4 = 'var _v2chartTabs={stage_1:1,stage_2:1,stage_3:1,stage_4:1,pre_indicators:1,post_indicators:1,setups_s1pb:1,setups_s2vcp:1,tests:1,setups_healthy_retest:1,master_overview:1};  /* MD-V2-S47-TAB-HEALTHY-RETEST-MARKER */'

# 5. Chart wiring - _v2ct object (line ~2789)
ANCHOR_5 = 'var _v2ct={stage_1:1,stage_2:1,stage_3:1,stage_4:1,pre_indicators:1,post_indicators:1,setups_s1pb:1,setups_s2vcp:1,tests:1,master_overview:1};'
REPLACE_5 = 'var _v2ct={stage_1:1,stage_2:1,stage_3:1,stage_4:1,pre_indicators:1,post_indicators:1,setups_s1pb:1,setups_s2vcp:1,tests:1,setups_healthy_retest:1,master_overview:1};  /* MD-V2-S47-TAB-HEALTHY-RETEST-MARKER */'

# 6. renderTab dispatcher: insert after the tests case
ANCHOR_6 = "  else if(id===\"tests\")renderTests();  /* MD-V2-TESTS-MARKER MD-V2-TESTS-S27-MARKER: was renderCapTests (undefined) */"
REPLACE_6 = ("  else if(id===\"tests\")renderTests();  /* MD-V2-TESTS-MARKER MD-V2-TESTS-S27-MARKER: was renderCapTests (undefined) */\n"
             "  else if(id===\"setups_healthy_retest\")renderHealthyRetest();  /* MD-V2-S47-TAB-HEALTHY-RETEST-MARKER */")

# 7. CSS selectors - add new tab to all the V2 chrome selector lists
#    We add the new tab alongside the existing "tests" selectors.
#    This covers: legacy chrome suppression, V2 nav display, header/body
#    resets, controls, table-wrap, and v2-hscroll.

# 8. CSS block + render module: insert before MD-V2-MASTER-OVERVIEW-MARKER-MODULE-START
ANCHOR_8 = '/* MD-V2-MASTER-OVERVIEW-MARKER-MODULE-START */'

# The render module (IIFE) and CSS for the healthy-retest tab.
# Built by modelling on the existing tests module (CT_PATTERNS etc).
HR_CSS = r"""
/* MD-V2-S47-TAB-HEALTHY-RETEST-MARKER-CSS-START */
/* Healthy Retest of MA — standalone 13-criterion test tab (S47) */
#tab-setups_healthy_retest .group-captions { display: grid; grid-template-columns: 1fr; gap: 10px; margin: 16px 0 14px 0; }
#tab-setups_healthy_retest .group-captions .gcap { background: #fbfaf5; border: 1px solid #e0dcc8; border-left: 3px solid #2E7D32; border-radius: 4px; padding: 10px 12px; font-size: 11px; line-height: 1.45; color: #555; }
#tab-setups_healthy_retest .group-captions .gcap b { display: block; margin-bottom: 4px; font-weight: 700; color: #2E7D32; font-size: 11px; letter-spacing: 0.2px; }
#tab-setups_healthy_retest .s1-rating-tiles { display: grid; grid-template-columns: 1fr; gap: 8px; }
#tab-setups_healthy_retest .s1-rating-tiles .pi-tile-pullback { background: rgba(46,125,50,0.10); border: 1px solid rgba(46,125,50,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
#tab-setups_healthy_retest .s1-rating-tiles .pi-tile-pullback.active { background: rgba(46,125,50,0.22); border: 1.5px solid #2E7D32; }
#tab-setups_healthy_retest .s1-rating-tiles .pi-strip-pullback { background: #2E7D32; height: 4px; margin-top: 6px; border-radius: 2px; }
#tab-setups_healthy_retest .s1-rating-tiles .rt-breakdown { font-size: 9px; color: #888; margin-top: 4px; line-height: 1.35; }
#tab-setups_healthy_retest .pi-tier-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 7px; }
#tab-setups_healthy_retest .pi-tier-chip { font-size: 10px; padding: 2px 6px; border-radius: 4px; cursor: pointer; user-select: none; border: 0.5px solid; line-height: 1.4; white-space: nowrap; transition: background 0.12s, color 0.12s; }
#tab-setups_healthy_retest .pi-chip-pullback { background: #E1F5EE; color: #2E7D32; border-color: #9FE1CB; }
#tab-setups_healthy_retest .pi-chip-pullback.on { background: #2E7D32; color: #fff; border-color: #2E7D32; font-weight: 500; }
#tab-setups_healthy_retest .pi-tier-chip:hover { filter: brightness(0.96); }
#tab-setups_healthy_retest .s1-rating-tiles .rating-tile.active { box-shadow: inset 0 0 0 1.5px currentColor; }
/* Re-use the ct-main-table styles via shared class — table uses id="hr-main-table" */
#hr-main-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 11px; table-layout: fixed; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }
#hr-main-table thead { position: sticky; top: 0; z-index: 50; background: #fbfaf5; box-shadow: 0 2px 4px rgba(0,0,0,0.06); }
#hr-main-table thead th { background: #fbfaf5 !important; border-bottom: 1px solid #e0dcc8; padding: 7px 3px; text-align: center; font-weight: 600; font-size: 10px; color: #666; cursor: pointer; user-select: none; line-height: 1.25; vertical-align: middle; }
#hr-main-table thead th:hover { background: #f0ebd9 !important; }
#hr-main-table thead .group-header-row th { background: #f3efe2 !important; font-size: 9.5px; text-transform: none; font-weight: 700; letter-spacing: 0.2px; padding: 5px 3px; cursor: default; line-height: 1.25; }
#hr-main-table thead .group-header-row th:hover { background: #f3efe2 !important; }
#hr-main-table thead tr.group-header-row th { position: sticky; top: 0; }
#hr-main-table thead tr.sub-group-row th { position: sticky; top: 24px; font-size: 9px; text-transform: uppercase; letter-spacing: 0.3px; color: #888; padding: 3px; font-weight: 600; background: #f8f6ee !important; border-bottom: 1px solid #e0dcc8; }
#hr-main-table thead tr.col-header-row th { position: sticky; top: 44px; border-top: 1px solid #e0dcc8; }
#hr-main-table thead .gh-inputs { color: #555; }
#hr-main-table thead .gh-stageinfo { color: #7a6a3a; }
#hr-main-table thead .gh-tests { color: #2E7D32; }
#hr-main-table .hd { display: inline-flex; align-items: center; justify-content: center; gap: 3px; width: 100%; }
#hr-main-table .hd .lbl { white-space: normal; word-break: break-word; }
#hr-main-table .hd .sort-arrow { font-size: 9px; color: #2E7D32; flex: 0 0 auto; line-height: 1; }
#hr-main-table .hd .sort-placeholder { width: 9px; flex: 0 0 auto; }
#hr-main-table td { padding: 5px 4px; border-bottom: 1px solid #efece0; text-align: center; vertical-align: middle; height: 38px; box-sizing: border-box; font-variant-numeric: tabular-nums; }
#hr-main-table tr:hover { background: rgba(46,125,50,0.05); }
#hr-main-table td.grp-start-stageinfo, #hr-main-table th.grp-start-stageinfo { border-left: 2px solid rgba(122,106,58,0.40); }
#hr-main-table td.grp-start-rating, #hr-main-table th.grp-start-rating { border-left: 2px solid rgba(46,125,50,0.40); }
#hr-main-table td.grp-start-tests, #hr-main-table th.grp-start-tests { border-left: 2px solid rgba(46,125,50,0.40); }
#hr-main-table td.pi-pass { background: rgba(46,125,50,0.12); color: #2E7D32; font-weight: 700; }
#hr-main-table td.pi-fail { color: #999; }
#hr-main-table td.pi-rating-cell { padding: 3px 4px; }
#hr-main-table .pi-pill { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 9px; font-weight: 700; line-height: 1.3; white-space: nowrap; }
#hr-main-table .pi-pill-tint-qualified { background: #1b5e20; color: #fff; }
#hr-main-table .pi-pill-tint-prob { background: #2E7D32; color: #fff; }
#hr-main-table .pi-pill-tint-pla  { background: rgba(46,125,50,0.30); color: #0a4a3a; }
#hr-main-table .pi-pill-tint-pos  { background: rgba(46,125,50,0.14); color: #3a6a5a; }
#hr-main-table .pi-pill-tint-none { background: #ece9dd; color: #999; }
#hr-main-table td.pi-score-cell { padding: 4px 3px; }
#hr-main-table .pi-pip-row { display: inline-flex; align-items: center; gap: 2px; justify-content: center; }
#hr-main-table .pi-pip-row .pip { width: 6px; height: 6px; border-radius: 50%; background: #d8d4c4; display: inline-block; }
#hr-main-table .pi-pip-row .pip.on { background: #2E7D32; }
#hr-main-table .pi-pip-row .pi-score-num { font-size: 9px; color: #777; margin-left: 3px; font-weight: 600; }
#hr-main-table td.ct-stage-info-cell { padding: 3px 4px; }
#hr-main-table .ct-info-label { display: inline-block; padding: 2px 5px; border-radius: 3px; font-size: 9px; font-weight: 600; line-height: 1.3; white-space: nowrap; }
#hr-main-table td.ct-stage-info-cell.tint-prob .ct-info-label { background: rgba(46,125,50,0.22); color: #0a4a3a; }
#hr-main-table td.ct-stage-info-cell.tint-pla  .ct-info-label { background: rgba(46,125,50,0.13); color: #3a6a5a; }
#hr-main-table td.ct-stage-info-cell.tint-pos  .ct-info-label { background: rgba(46,125,50,0.07); color: #6a7a72; }
#hr-main-table td.ct-stage-info-cell.tint-none .ct-info-label { background: #f0ede1; color: #aaa; }
#hr-main-table td.ct-window-col { padding: 3px 4px; font-size: 10px; }
#hr-main-table td.ct-window-fired-recent { background: rgba(46,125,50,0.16); }
#hr-main-table td.ct-window-fired-recent .ct-window-label { color: #0a4a3a; font-weight: 700; }
#hr-main-table td.ct-window-fired-older { background: rgba(186,117,23,0.14); }
#hr-main-table td.ct-window-fired-older .ct-window-label { color: #7a4e0a; font-weight: 600; }
#hr-main-table td.ct-window-none { color: #bbb; }
#hr-main-table td.ct-window-building { color: #b59a5a; font-style: italic; font-size: 9px; }
#hr-main-table td.ct-window-na { color: #ccc; }
#hr-main-table td.name-cell { text-align: left; padding: 4px 4px 4px 8px; line-height: 1.15; }
#hr-main-table td.name-cell .co { font-weight: 700; font-size: 11px; color: #2a2a2a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#hr-main-table td.name-cell .tk { font-size: 9px; color: #999; font-weight: 500; margin-top: 1px; }
#hr-main-table td.name-cell .live-dot { color: #2e7d32; font-weight: 700; margin-right: 4px; display: inline-block; vertical-align: middle; line-height: 1; font-size: 10px; }
#hr-main-table td.taxon { text-align: left; font-size: 9px; line-height: 1.2; padding: 4px; }
#hr-main-table td.taxon .ind { color: #666; font-weight: 500; }
#hr-main-table td.taxon .sec { color: #999; }
#hr-main-table col.c-name { width: 124px; }
#hr-main-table col.c-taxon { width: 150px; }
#hr-main-table col.c-price { width: 50px; }
#hr-main-table col.c-52wh { width: 48px; }
#hr-main-table col.c-52wl { width: 48px; }
#hr-main-table col.c-ma150 { width: 48px; }
#hr-main-table col.c-ma200 { width: 48px; }
#hr-main-table col.c-pullback { width: 58px; }
#hr-main-table col.c-stageinfo { width: 56px; }
#hr-main-table col.c-rating { width: 64px; }
#hr-main-table col.c-score { width: 52px; }
#hr-main-table col.c-test { width: 64px; }
#hr-main-table col.c-window { width: 52px; }
#hr-main-table tr.tint-row td.name-cell, #hr-main-table tr.tint-row td.taxon { background: var(--tint-bg) !important; }
#hr-main-table tr.portfolio-band td:last-child { border-right: 4px solid var(--portfolio-color); }
#hr-main-table tr.portfolio-tint { background: var(--portfolio-bg); }
#hr-main-table tr.portfolio-tint:hover { background: var(--portfolio-bg-hover); }
/* MD-V2-S47-TAB-HEALTHY-RETEST-MARKER-CSS-END */
"""

HR_MODULE = r"""
/* MD-V2-S47-TAB-HEALTHY-RETEST-MARKER-MODULE-START */
// =============================================================================
// HEALTHY RETEST OF MA — STANDALONE TAB MODULE (S47)
// =============================================================================
// MD-V2-S47-TAB-HEALTHY-RETEST-MARKER — idempotency marker for patcher detection
//
// Renders md_v2.tests.healthy_retest — the 13-criterion S46 test:
//   Group A: Stage 2 hard precondition (1 criterion)
//   Group B: Early-stage indicators (4 criteria: 2 uptrend + 2 pullback)
//   Group C: Healthy-retest setup (6 criteria)
//   Group D: Capital deployment trigger (2 criteria)
// =============================================================================

(function() {
  'use strict';

  var HR_KEY = 'healthy_retest';

  // Tier ladder includes Qualified (above Probable)
  var HR_TIERS = ['None', 'Possible', 'Plausible', 'Probable', 'Qualified'];
  var HR_TIER_DISPLAY = ['Possible', 'Plausible', 'Probable', 'Qualified'];
  var HR_RATING_RANK = { 'Qualified':6, 'Probable':5, 'Plausible':3, 'Possible':2, 'None':1 };
  var HR_RATING_CLS  = { 'Qualified':'tint-qualified', 'Probable':'tint-prob', 'Plausible':'tint-pla', 'Possible':'tint-pos', 'None':'tint-none' };

  // The 13 tests in order, with group labels for sub-group row
  var HR_TESTS = [
    { key: 'g1_stage_2_qualifies',         label: 'Stage 2 qualifies',        group: 'precondition', tooltip: 'Stage 2 rating is Probable or Plausible — hard precondition' },
    { key: 'g2_b1_50d_rising',             label: '50D MA rising',            group: 'indicator',    tooltip: '50-day moving average is rising day-over-day' },
    { key: 'g2_b2_150d_rising',            label: '150D MA rising',           group: 'indicator',    tooltip: '150-day moving average is rising day-over-day' },
    { key: 'g2_b3_5d_declining',           label: '5D MA declining',          group: 'indicator',    tooltip: '5-day moving average is declining — pulling back' },
    { key: 'g2_b4_10d_declining',          label: '10D MA declining',         group: 'indicator',    tooltip: '10-day moving average is declining — pulling back' },
    { key: 'g3_c1_volume_contracting',     label: 'Volume contracting',       group: 'setup',        tooltip: '10-day average volume below the 50-day — selling drying up' },
    { key: 'g3_c2_up_vol_gt_down_vol',     label: 'Up-vol > down-vol',        group: 'setup',        tooltip: 'Up-day volume exceeds down-day volume over the last month' },
    { key: 'g3_c3_few_distribution_days',  label: 'Few distribution days',    group: 'setup',        tooltip: 'Three or fewer distribution days over the last 25 sessions' },
    { key: 'g3_c4_volatility_reducing',    label: 'Volatility reducing',      group: 'setup',        tooltip: '10-day ATR below the 20-day — orderly pullback' },
    { key: 'g3_c5_testing_meaningful_ma',  label: 'Testing a meaningful MA',  group: 'setup',        tooltip: 'Price has come down to within range of a 50/100/150/200-day MA' },
    { key: 'g3_c6_buying_through_l10d',    label: 'Buying through 10 days',   group: 'setup',        tooltip: 'At least half of the last 10 days closed in the upper 40% of range' },
    { key: 'g4_d1_reclaimed_ma',           label: 'Reclaimed the MA',         group: 'trigger',      tooltip: 'Current price is back above the moving average being tested' },
    { key: 'g4_d2_confirmation_close_ge2pct', label: 'Confirm: close 2%+ up', group: 'trigger',      tooltip: 'Today\'s close is at least 2% above yesterday\'s' }
  ];

  var hrState = {
    mode: { inputs: 'pct', tests: 'tick' },
    scope: 'all',
    tierFilter: [],
    tint: 'none',
    port: 'off',
    sort: { col: 'company', dir: 'asc' }
  };

  // --- data lookups (reuse from ct module where exported, else standalone) ---
  function hrPricesLookup() {
    if (window._ctPricesByTicker) return window._ctPricesByTicker;
    var out = {};
    var arr = (window.MASTER_DATA && MASTER_DATA.prices) || [];
    for (var i = 0; i < arr.length; i++) if (arr[i] && arr[i].ticker) out[arr[i].ticker] = arr[i];
    window._ctPricesByTicker = out;
    return out;
  }
  function hrLiveTickers() {
    var out = {};
    var inv = (window.MASTER_DATA && MASTER_DATA.positions && MASTER_DATA.positions.investments) || [];
    for (var i = 0; i < inv.length; i++) if (inv[i].ticker) out[inv[i].ticker] = true;
    return out;
  }
  function hrLiveSectors() {
    var out = {}, prices = hrPricesLookup(), tickers = hrLiveTickers();
    for (var t in tickers) { var p = prices[t]; if (p && p.sector) out[p.sector] = true; }
    return out;
  }
  function hrLiveIndustries() {
    var out = {}, prices = hrPricesLookup(), tickers = hrLiveTickers();
    for (var t in tickers) { var p = prices[t]; if (p && p.industry) out[p.industry] = true; }
    return out;
  }
  function hrGetRec(row) {
    var dk = row.md_v2 && row.md_v2.tests;
    return (dk && dk[HR_KEY]) || null;
  }
  function hrEvalTest(row, testKey) {
    var rec = hrGetRec(row);
    if (!rec || !rec.tests) return false;
    return !!rec.tests[testKey];
  }
  function hrRowRating(row) {
    var rec = hrGetRec(row);
    return rec ? (rec.rating || 'None') : 'None';
  }
  function hrStageRating(row, stageKey) {
    var md = row.md_v2 || {};
    var st = md[stageKey];
    return (st && st.rating) || 'None';
  }
  function hrGetRows() {
    var raw = (window.MASTER_DATA && MASTER_DATA.filters) || [];
    var prices = hrPricesLookup();
    var live = hrLiveTickers(), liveS = hrLiveSectors(), liveI = hrLiveIndustries();
    var rows = [];
    for (var i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || !s.md_v2 || !s.md_v2.tests) continue;
      var rec = s.md_v2.tests[HR_KEY];
      if (!rec) continue;
      var p = prices[s.ticker] || {};
      var mas = p.mas || {};
      rows.push({
        ticker: s.ticker, company: p.company_name || s.ticker,
        sector: p.sector || '', industry: p.industry || '',
        price: p.price, high_52w: p.high_52w, low_52w: p.low_52w,
        recent_pullback: p.recent_pullback_pct,
        ma_150: mas['150D'], ma_200: mas['200D'],
        md_v2: s.md_v2,
        is_live: !!live[s.ticker],
        sector_in_portfolio: !!liveS[p.sector],
        industry_in_portfolio: !!liveI[p.industry]
      });
    }
    return rows;
  }

  // --- counts ---
  function hrTierCounts(rows) {
    var c = {};
    for (var i = 0; i < HR_TIERS.length; i++) c[HR_TIERS[i]] = 0;
    for (var j = 0; j < rows.length; j++) {
      var r = hrRowRating(rows[j]);
      if (c[r] != null) c[r]++;
    }
    return c;
  }
  function hrPassHistogram(rows) {
    var h = [];
    for (var k = 0; k <= 13; k++) h[k] = 0;
    for (var i = 0; i < rows.length; i++) {
      var rec = hrGetRec(rows[i]);
      var cnt = rec ? (rec.count || 0) : 0;
      if (cnt >= 0 && cnt <= 13) h[cnt]++;
    }
    return h;
  }

  // --- formatting helpers (standalone copies to avoid cross-module deps) ---
  function hrFmtNum(n) {
    if (n == null || isNaN(n)) return '-';
    var abs = Math.abs(n);
    var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);
    if (Math.abs(n - Math.round(n)) < 1e-9) dp = 0;
    var f = abs.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });
    return n < 0 ? '(' + f + ')' : f;
  }
  function hrFmtPct(p) {
    if (p == null || isNaN(p)) return '-';
    var r = Math.round(p), abs = Math.abs(r);
    return r < 0 ? '(' + abs + ')%' : r + '%';
  }
  function hrColourForIntensity(i) {
    if (i >= 0.6) return '#2E7D32';
    if (i >= 0.25) return '#4CAF50';
    if (i >= 0.05) return '#81C784';
    if (i <= -0.6) return '#A32D2D';
    if (i <= -0.25) return '#E24B4A';
    if (i <= -0.05) return '#F09595';
    return '#888';
  }
  function hrInputCell(row, key, extraCls) {
    extraCls = extraCls || '';
    var v = row[key];
    if (key === 'price') return '<td class="num ' + extraCls + '">' + hrFmtNum(v) + '</td>';
    if (key === 'recent_pullback') {
      if (v == null || isNaN(v)) return '<td class="num ' + extraCls + '">-</td>';
      var pctVal = v * 100;
      var pi_intensity = Math.max(-1, Math.min(1, (pctVal - 5) / 20));
      var col = hrColourForIntensity(-pi_intensity);
      return '<td class="num ' + extraCls + '" style="color:' + col + '">' + Math.round(pctVal) + '%</td>';
    }
    if (v == null || row.price == null) return '<td class="num ' + extraCls + '">-</td>';
    var pct = (row.price - v) / v * 100;
    var intensity = 0;
    if (key === 'high_52w') intensity = Math.max(-1, Math.min(1, (-pct - 5) / 20));
    else if (key === 'low_52w') intensity = Math.max(-1, Math.min(1, (pct - 20) / 30));
    else if (key === 'ma_150' || key === 'ma_200') intensity = Math.max(-1, Math.min(1, pct / 10));
    var colour = hrColourForIntensity(intensity);
    var text = (hrState.mode.inputs === 'pct') ? hrFmtPct(pct) : hrFmtNum(v);
    return '<td class="num ' + extraCls + '" style="color:' + colour + '">' + text + '</td>';
  }
  function hrStageInfoCell(row, stageKey, cls) {
    var rating = hrStageRating(row, stageKey);
    var rcls = HR_RATING_CLS[rating] || (rating.indexOf('Probable') === 0 ? 'tint-prob'
              : rating.indexOf('Plausible') === 0 ? 'tint-pla'
              : rating.indexOf('Possible') === 0 ? 'tint-pos' : 'tint-none');
    return '<td class="' + (cls || '') + ' ct-stage-info-cell ' + rcls + '">' +
           '<span class="ct-info-label">' + rating + '</span></td>';
  }
  function hrTestValueFor(row, testKey) {
    var rec = hrGetRec(row);
    var tv = rec && rec.test_values;
    if (!tv || !(testKey in tv)) return '—';
    var v = tv[testKey];
    if (v === null || v === undefined) return '—';
    if (typeof v === 'string') return v;
    if (typeof v === 'number') {
      if (isNaN(v)) return '—';
      if (Math.abs(v) <= 1.5 && v !== Math.round(v)) return hrFmtPct(v * 100);
      return hrFmtNum(v);
    }
    return String(v);
  }
  function hrTestCell(row, testKey, cls) {
    var pass = hrEvalTest(row, testKey);
    var extra = cls || '';
    if (hrState.mode.tests === 'val') {
      var v = hrTestValueFor(row, testKey);
      var colour = pass ? hrColourForIntensity(0.7) : hrColourForIntensity(-0.4);
      return '<td class="test-val pi-' + (pass ? 'pass' : 'fail') + ' ' + extra + '" style="color:' + colour + '">' + v + '</td>';
    }
    if (pass) return '<td class="pi-pass ' + extra + '"><span class="tick">' + String.fromCharCode(10003) + '</span></td>';
    return '<td class="pi-fail ' + extra + '">.</td>';
  }
  function hrRatingCell(row, cls) {
    var rating = hrRowRating(row);
    var rcls = HR_RATING_CLS[rating] || 'tint-none';
    return '<td class="' + (cls || '') + ' pi-rating-cell ' + rcls + '"><span class="pi-pill pi-pill-' + rcls + '">' + rating + '</span></td>';
  }
  function hrScoreCell(row, cls) {
    var rec = hrGetRec(row);
    var cnt = rec ? (rec.count || 0) : 0;
    var tot = rec ? (rec.total || 0) : 0;
    var s = '';
    for (var i = 0; i < tot; i++) s += '<span class="pip ' + (i < cnt ? 'on' : '') + '"></span>';
    return '<td class="' + (cls || '') + ' pi-score-cell"><div class="pi-pip-row">' + s +
           '<span class="pi-score-num">' + cnt + '/' + tot + '</span></div></td>';
  }
  function hrWindowCell(row, windowKey, cls) {
    var rec = hrGetRec(row);
    var extra = cls || '';
    if (!rec) return '<td class="' + extra + ' ct-window-na">-</td>';
    var depth = rec.history_depth || 0;
    var windowDays = (windowKey === 'l5d') ? 5 : 20;
    if (depth < windowDays) {
      return '<td class="' + extra + ' ct-window-building" title="' + depth +
             ' of ' + windowDays + ' days of history accumulated">building</td>';
    }
    var fired = (windowKey === 'l5d') ? !!rec.fired_l5d : !!rec.fired_l20d;
    if (!fired) return '<td class="' + extra + ' ct-window-none">-</td>';
    var ds = rec.days_since_fired;
    var label;
    if (ds === 0) label = 'today';
    else if (ds === 1) label = '1d ago';
    else if (ds != null) label = ds + 'd ago';
    else label = 'fired';
    var shadeCls = (ds != null && ds <= 5) ? 'ct-window-fired-recent' : 'ct-window-fired-older';
    return '<td class="' + extra + ' ' + shadeCls + '" title="most recent fire ' + label + '">' +
           '<span class="ct-window-label">' + label + '</span></td>';
  }
  function hrHashColor(label, alpha) {
    if (!label) return null;
    var h = 0;
    for (var i = 0; i < label.length; i++) h = (h * 31 + label.charCodeAt(i)) & 0xffff;
    return 'hsla(' + (h % 360) + ', 35%, 55%, ' + alpha + ')';
  }
  function hrPortfolioInfo(row) {
    if (row.is_live) return { color:'#1b5e20', bg:'rgba(27,94,32,0.10)', bgHover:'rgba(27,94,32,0.14)' };
    if (row.sector_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.05)', bgHover:'rgba(27,94,32,0.08)' };
    if (row.industry_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.025)', bgHover:'rgba(27,94,32,0.05)' };
    return null;
  }

  // --- sorting ---
  var HR_COL_MODEL = null;
  function hrBuildColModel() {
    if (HR_COL_MODEL) return HR_COL_MODEL;
    var cols = [
      { id:'name',     sortKey:'company',         kind:'input' },
      { id:'taxon',    sortKey:'sector',           kind:'input' },
      { id:'price',    sortKey:'price',            kind:'input' },
      { id:'high_52w', sortKey:'high_52w',         kind:'input' },
      { id:'low_52w',  sortKey:'low_52w',          kind:'input' },
      { id:'ma_150',   sortKey:'ma_150',           kind:'input' },
      { id:'ma_200',   sortKey:'ma_200',           kind:'input' },
      { id:'pullback', sortKey:'recent_pullback',  kind:'input' }
    ];
    var STAGES = ['stage_1','stage_2','stage_3','stage_4'];
    for (var si = 0; si < STAGES.length; si++) {
      cols.push({ id:'info_'+STAGES[si], sortKey:'stageinfo__'+STAGES[si], kind:'stageinfo', stageKey:STAGES[si] });
    }
    cols.push({ id:'hr_rating', sortKey:'hr__rating', kind:'rating' });
    cols.push({ id:'hr_score',  sortKey:'hr__score',  kind:'score' });
    for (var t = 0; t < HR_TESTS.length; t++) {
      cols.push({ id:'hr_t'+(t+1), sortKey:'hr__'+HR_TESTS[t].key, kind:'test', testKey:HR_TESTS[t].key, group:HR_TESTS[t].group });
    }
    cols.push({ id:'hr_l5d',  sortKey:'hr__l5d',  kind:'window', windowKey:'l5d' });
    cols.push({ id:'hr_l20d', sortKey:'hr__l20d', kind:'window', windowKey:'l20d' });
    HR_COL_MODEL = cols;
    return cols;
  }
  function hrGetSortVal(row, key) {
    if (key.indexOf('stageinfo__') === 0) {
      var sk = key.split('__')[1];
      return HR_RATING_RANK[hrStageRating(row, sk)] || 0;
    }
    if (key === 'hr__rating') return HR_RATING_RANK[hrRowRating(row)] || 0;
    if (key === 'hr__score') { var rec = hrGetRec(row); return rec ? (rec.count || 0) : 0; }
    if (key === 'hr__l5d' || key === 'hr__l20d') {
      var rec2 = hrGetRec(row);
      if (!rec2) return -1;
      var sub = key.split('__')[1];
      var windowDays = (sub === 'l5d') ? 5 : 20;
      var depth = rec2.history_depth || 0;
      if (depth < windowDays) return -2;
      var fired = (sub === 'l5d') ? rec2.fired_l5d : rec2.fired_l20d;
      if (!fired) return -1;
      var ds = rec2.days_since_fired;
      return (ds == null) ? 0 : (1000 - ds);
    }
    if (key.indexOf('hr__') === 0) {
      var testKey = key.substring(4);
      return hrEvalTest(row, testKey) ? 1 : 0;
    }
    if (key === 'recent_pullback') return row.recent_pullback == null ? -Infinity : row.recent_pullback;
    var PCT_KEYS = ['high_52w','low_52w','ma_150','ma_200'];
    if (PCT_KEYS.indexOf(key) > -1 && hrState.mode.inputs === 'pct') {
      var ref = row[key];
      if (ref == null || row.price == null || ref === 0) return -Infinity;
      return (row.price - ref) / ref * 100;
    }
    if (key in row) return row[key];
    return 0;
  }
  function hrOnSort(key) {
    if (hrState.sort.col === key) hrState.sort.dir = hrState.sort.dir === 'desc' ? 'asc' : 'desc';
    else hrState.sort = { col: key, dir: key === 'company' ? 'asc' : 'desc' };
    hrBuildHeaderRow();
    hrRenderRows();
  }

  // --- header row ---
  function hrBuildHeaderRow() {
    var tr = document.getElementById('hr-col-header-row');
    if (!tr) return;
    var cols = hrBuildColModel();
    var INPUT_LABELS = ['Company - Ticker','Industry - Sector','Price','52wk high','52wk low','150D MA','200D MA','Pullback'];
    var STAGE_LABELS = ['Stage 1','Stage 2','Stage 3','Stage 4'];
    var h = '';
    for (var i = 0; i < cols.length; i++) {
      var c = cols[i];
      var isSort = hrState.sort.col === c.sortKey;
      var arrow = isSort
        ? '<span class="sort-arrow">' + (hrState.sort.dir === 'desc' ? String.fromCharCode(9660) : String.fromCharCode(9650)) + '</span>'
        : '<span class="sort-placeholder"></span>';
      var label, title, cls = '';
      if (c.kind === 'input') { label = INPUT_LABELS[i]; title = label; }
      else if (c.kind === 'stageinfo') { label = STAGE_LABELS[i - 8]; title = label + ' rating'; cls = (i === 8 ? 'grp-start-stageinfo ' : ''); }
      else if (c.kind === 'rating') { label = 'Rating'; title = 'Healthy Retest rating'; cls = 'grp-start-rating '; }
      else if (c.kind === 'score') { label = 'Score'; title = 'Pass count out of 13'; }
      else if (c.kind === 'test') { var tDef = HR_TESTS[i - 14]; label = tDef.label; title = tDef.tooltip; cls = (i === 14 ? 'grp-start-tests ' : ''); }
      else if (c.kind === 'window') { label = c.windowKey === 'l5d' ? 'Fired 5d' : 'Fired 20d'; title = label; cls = 'ct-window-col'; }
      else { label = '?'; title = ''; }
      h += '<th class="' + cls + '" data-sort-key="' + c.sortKey + '" title="' + title + '">' +
           '<span class="hd"><span class="lbl">' + label + '</span>' + arrow + '</span></th>';
    }
    tr.innerHTML = h;
  }

  // --- tile ---
  function hrPatternTile(scopeRows) {
    var tiles = document.getElementById('hr-pattern-tiles');
    if (!tiles) return;
    var tierCounts = hrTierCounts(scopeRows);
    var total = scopeRows.length;
    var cnt = total - (tierCounts['None'] || 0);
    var pct = total > 0 ? Math.round(cnt / total * 100) : 0;
    var sel = hrState.tierFilter;
    var anySel = sel.length > 0;
    var headline = cnt, headSub = 'of ' + total.toLocaleString('en-GB') + ' · ' + pct + '%';
    if (anySel) {
      var ft = 0;
      for (var z = 0; z < sel.length; z++) ft += (tierCounts[sel[z]] || 0);
      headline = ft;
      headSub = sel.join(' + ') + ' · filtered';
    }
    var hist = hrPassHistogram(scopeRows);
    var breakdown = '';
    for (var k = 1; k <= 13; k++) {
      if (k > 1) breakdown += ' · ';
      breakdown += k + '/13: ' + (hist[k] || 0).toLocaleString('en-GB');
    }
    var chips = '';
    for (var c = 0; c < HR_TIER_DISPLAY.length; c++) {
      var tier = HR_TIER_DISPLAY[c];
      var on = sel.indexOf(tier) > -1;
      var tc = tierCounts[tier] || 0;
      chips += '<span class="pi-tier-chip pi-chip-pullback' +
               (on ? ' on' : '') + '" data-tier="' + tier + '">' +
               tier + ' ' + tc.toLocaleString('en-GB') + (on ? ' ' + String.fromCharCode(10003) : '') + '</span>';
    }
    var activeCls = anySel ? ' active' : '';
    tiles.innerHTML = '<div class="rating-tile pi-tile-pullback' + activeCls + '" title="Healthy Retest of Upwards MA — 13-criterion test">' +
         '<div class="rt-label">Healthy Retest</div>' +
         '<div class="rt-count">' + headline.toLocaleString('en-GB') + '</div>' +
         '<div class="rt-sub">' + headSub + '</div>' +
         '<div class="rt-breakdown">' + breakdown + '</div>' +
         '<div class="pi-tier-chips">' + chips + '</div>' +
         '<div class="rt-strip pi-strip-pullback"></div>' +
         '</div>';
  }

  // --- scope / filter ---
  function hrUpdateScopeCounts(rows) {
    function set(id, n) { var el = document.getElementById(id); if (el) el.textContent = '(' + n + ')'; }
    set('hr-cnt-all',      rows.length);
    set('hr-cnt-live',     rows.filter(function(r){ return r.is_live; }).length);
    set('hr-cnt-sector',   rows.filter(function(r){ return r.sector_in_portfolio; }).length);
    set('hr-cnt-industry', rows.filter(function(r){ return r.industry_in_portfolio; }).length);
  }
  function hrApplyScope(all) {
    var rows = all.slice();
    if (hrState.scope === 'live') rows = rows.filter(function(r){ return r.is_live; });
    else if (hrState.scope === 'sector') rows = rows.filter(function(r){ return r.sector_in_portfolio; });
    else if (hrState.scope === 'industry') rows = rows.filter(function(r){ return r.industry_in_portfolio; });
    return rows;
  }
  function hrApplyTierFilter(rows) {
    var sel = hrState.tierFilter;
    if (sel.length === 0) return rows;
    return rows.filter(function(r) {
      var rating = hrRowRating(r);
      return sel.indexOf(rating) > -1;
    });
  }

  // --- main render ---
  function hrRenderRows() {
    var tbody = document.getElementById('hr-tbody');
    if (!tbody) return;
    var all = hrGetRows();
    var scopeRows = hrApplyScope(all);
    hrUpdateScopeCounts(all);
    hrPatternTile(scopeRows);
    var rows = hrApplyTierFilter(scopeRows);
    rows.sort(function(a,b) {
      var va = hrGetSortVal(a, hrState.sort.col), vb = hrGetSortVal(b, hrState.sort.col);
      var cmp = (typeof va === 'string') ? va.localeCompare(vb) : (va || 0) - (vb || 0);
      if (cmp === 0) cmp = a.ticker.localeCompare(b.ticker);
      return hrState.sort.dir === 'desc' ? -cmp : cmp;
    });
    var STAGES = ['stage_1','stage_2','stage_3','stage_4'];
    var html = '';
    for (var i = 0; i < rows.length; i++) {
      var s = rows[i];
      var styles = [], cls = [];
      if (hrState.tint === 'industry') { styles.push('--tint-bg: ' + hrHashColor(s.industry, 0.16)); cls.push('tint-row'); }
      else if (hrState.tint === 'sector') { styles.push('--tint-bg: ' + hrHashColor(s.sector, 0.16)); cls.push('tint-row'); }
      if (hrState.port === 'on') {
        var pinf = hrPortfolioInfo(s);
        if (pinf) {
          styles.push('--portfolio-color: ' + pinf.color);
          styles.push('--portfolio-bg: ' + pinf.bg);
          styles.push('--portfolio-bg-hover: ' + pinf.bgHover);
          cls.push('portfolio-band'); cls.push('portfolio-tint');
        }
      }
      var styleAttr = styles.length ? ' style="' + styles.join(';') + '"' : '';
      var clsAttr = cls.length ? ' class="' + cls.join(' ') + '"' : '';
      var liveDot = s.is_live ? '<span class="live-dot">' + String.fromCharCode(9679) + '</span>' : '';
      html += '<tr' + clsAttr + styleAttr + '>' +
        '<td class="name-cell"><div class="co">' + liveDot + (s.company || s.ticker) + '</div><div class="tk">' + s.ticker + '</div></td>' +
        '<td class="taxon"><div class="ind">' + (s.industry || '') + '</div><div class="sec">' + (s.sector || '') + '</div></td>' +
        hrInputCell(s, 'price') + hrInputCell(s, 'high_52w') + hrInputCell(s, 'low_52w') +
        hrInputCell(s, 'ma_150') + hrInputCell(s, 'ma_200') + hrInputCell(s, 'recent_pullback');
      // 4-stage info block
      for (var si = 0; si < STAGES.length; si++) {
        html += hrStageInfoCell(s, STAGES[si], si === 0 ? 'grp-start-stageinfo' : '');
      }
      // Rating + score
      html += hrRatingCell(s, 'grp-start-rating');
      html += hrScoreCell(s, '');
      // 13 test columns
      for (var ti = 0; ti < HR_TESTS.length; ti++) {
        var tCls = (ti === 0) ? 'grp-start-tests' : '';
        html += hrTestCell(s, HR_TESTS[ti].key, tCls);
      }
      // L5D / L20D
      html += hrWindowCell(s, 'l5d', 'ct-window-col');
      html += hrWindowCell(s, 'l20d', 'ct-window-col');
      html += '</tr>';
    }
    tbody.innerHTML = html;
  }

  // --- control setters ---
  window.hrSetMode = function(kind, val) {
    hrState.mode[kind] = val;
    var btns = document.querySelectorAll('button[data-hr-grp="' + kind + '"]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-hr-val') === val);
    hrRenderRows();
  };
  window.hrSetScope = function(s) {
    hrState.scope = s;
    var btns = document.querySelectorAll('button[data-hr-scope]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-hr-scope') === s);
    hrRenderRows();
  };
  window.hrSetTint = function(t) {
    hrState.tint = t;
    var btns = document.querySelectorAll('button[data-hr-tint]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-hr-tint') === t);
    hrRenderRows();
  };
  window.hrSetPort = function(p) {
    hrState.port = p;
    var btns = document.querySelectorAll('button[data-hr-port]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-hr-port') === p);
    hrRenderRows();
  };
  window.hrToggleTier = function(tier) {
    var sel = hrState.tierFilter;
    var idx = sel.indexOf(tier);
    if (idx > -1) sel.splice(idx, 1);
    else sel.push(tier);
    hrRenderRows();
  };
  window.hrSelectAllTiers = function() {
    var sel = hrState.tierFilter;
    var onlyProb = (sel.length === 1 && sel[0] === 'Probable');
    hrState.tierFilter = onlyProb ? [] : ['Probable'];
    hrRenderRows();
  };
  window.hrOnSort = hrOnSort;

  // --- scaffold ---
  function hrBuildScaffold() {
    var host = document.getElementById('tab-setups_healthy_retest');
    if (!host) return false;
    if (host.querySelector('#hr-main-table')) return true;

    // colgroup
    var cg = '<col class="c-name"><col class="c-taxon">' +
             '<col class="c-price"><col class="c-52wh"><col class="c-52wl">' +
             '<col class="c-ma150"><col class="c-ma200"><col class="c-pullback">';
    for (var si = 0; si < 4; si++) cg += '<col class="c-stageinfo">';
    cg += '<col class="c-rating"><col class="c-score">';
    for (var ti = 0; ti < 13; ti++) cg += '<col class="c-test">';
    cg += '<col class="c-window"><col class="c-window">';

    // group-header row
    var gHdr = '<th class="gh-inputs" colspan="8">Inputs</th>' +
               '<th class="gh-stageinfo grp-start-stageinfo" colspan="4">Stage ratings</th>' +
               '<th class="gh-tests grp-start-rating" colspan="' + (2 + 13 + 2) + '">Healthy Retest of Upwards MA</th>';

    // sub-group row
    var subGrp = '<th class="sg-spacer" colspan="8"></th>' +
                 '<th class="sg-spacer" colspan="4"></th>' +
                 '<th class="sub-g" colspan="2">Rating</th>' +
                 '<th class="sub-g" colspan="1">Gate</th>' +
                 '<th class="sub-g" colspan="4">Indicator</th>' +
                 '<th class="sub-g" colspan="6">Setup</th>' +
                 '<th class="sub-g" colspan="2">Trigger</th>' +
                 '<th class="sub-g" colspan="2">Context</th>';

    var theadRows = '<tr class="group-header-row">' + gHdr + '</tr>' +
                    '<tr class="sub-group-row">' + subGrp + '</tr>' +
                    '<tr class="col-header-row" id="hr-col-header-row"></tr>';

    var captionHtml = '<div class="gcap"><b>Healthy Retest of Upwards MA</b>' +
      '<span class="db">The trigger that pairs with the Healthy retest setup — a stock pulling back to an upwards-moving MA in a Stage 2 uptrend, then reclaiming it on healthy volume and volatility.</span>' +
      '<span class="intro">13 criteria across 4 groups:</span>' +
      '<span class="tline"><span class="tnum">(A)</span> <u>Stage 2 hard precondition</u> — Probable or Plausible</span>' +
      '<span class="tline"><span class="tnum">(B)</span> <u>Early-stage indicators</u> — 50D and 150D rising (uptrend) + 5D and 10D declining (pullback)</span>' +
      '<span class="tline"><span class="tnum">(C)</span> <u>Healthy-retest setup</u> — volume contracting, up-vol beats down-vol, few distribution days, volatility reducing, testing a meaningful MA, buying through 10 days</span>' +
      '<span class="tline"><span class="tnum">(D)</span> <u>Trigger</u> — reclaimed the MA + confirmation close 2%+ above yesterday</span>' +
      '</div>';

    var html = '' +
      '<div class="s1-intro">Healthy Retest of Upwards MA — the 13-criterion test for a Core Minervini trade. A stock must be in a Stage 2 uptrend (Probable or Plausible), pulling back towards an upwards-moving MA on healthy volume and volatility characteristics, then reclaiming the MA with a confirming up-day. Rating tiers: Qualified (all 13), Probable (12 of 13 — missing only the confirmation), Plausible (gate + indicators + 3 of 6 setup criteria), Possible (gate + indicators only). Click a tier chip to filter. Click the tile body to select Probable.</div>' +
      '<div class="controls s1-controls">' +
        '<div class="ctrl-grp"><span class="ctrl-label">Inputs</span>' +
          '<button class="toggle-btn active" data-hr-grp="inputs" data-hr-val="pct" onclick="hrSetMode(\'inputs\',\'pct\')">show as %</button>' +
          '<button class="toggle-btn" data-hr-grp="inputs" data-hr-val="raw" onclick="hrSetMode(\'inputs\',\'raw\')">show as numbers</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Tests</span>' +
          '<button class="toggle-btn active" data-hr-grp="tests" data-hr-val="tick" onclick="hrSetMode(\'tests\',\'tick\')">show ticks</button>' +
          '<button class="toggle-btn" data-hr-grp="tests" data-hr-val="val" onclick="hrSetMode(\'tests\',\'val\')">show test values</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Scope</span>' +
          '<button class="toggle-btn active" data-hr-scope="all" onclick="hrSetScope(\'all\')">All <span id="hr-cnt-all"></span></button>' +
          '<button class="toggle-btn" data-hr-scope="live" onclick="hrSetScope(\'live\')">Live <span id="hr-cnt-live"></span></button>' +
          '<button class="toggle-btn" data-hr-scope="sector" onclick="hrSetScope(\'sector\')">Sectors <span id="hr-cnt-sector"></span></button>' +
          '<button class="toggle-btn" data-hr-scope="industry" onclick="hrSetScope(\'industry\')">Industries <span id="hr-cnt-industry"></span></button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Peers</button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Cohorts</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Colour by</span>' +
          '<button class="toggle-btn active" data-hr-tint="none" onclick="hrSetTint(\'none\')">Off</button>' +
          '<button class="toggle-btn" data-hr-tint="industry" onclick="hrSetTint(\'industry\')">Industry</button>' +
          '<button class="toggle-btn" data-hr-tint="sector" onclick="hrSetTint(\'sector\')">Sector</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Portfolio tint</span>' +
          '<button class="toggle-btn active" data-hr-port="off" onclick="hrSetPort(\'off\')">Off</button>' +
          '<button class="toggle-btn" data-hr-port="on" onclick="hrSetPort(\'on\')">On</button>' +
        '</div>' +
      '</div>' +
      '<div class="rating-tiles s1-rating-tiles" id="hr-pattern-tiles"></div>' +
      '<div class="group-captions">' + captionHtml + '</div>' +
      '<div class="table-wrap"><div class="v2-hscroll">' +
        '<table class="data-table" id="hr-main-table">' +
          '<colgroup>' + cg + '</colgroup>' +
          '<thead>' + theadRows + '</thead>' +
          '<tbody id="hr-tbody"></tbody>' +
        '</table>' +
      '</div></div>';
    host.innerHTML = html;

    // Tile click events
    var tiles = document.getElementById('hr-pattern-tiles');
    if (tiles) {
      tiles.addEventListener('click', function(e) {
        var chip = e.target.closest('.pi-tier-chip');
        if (chip) {
          var ct = chip.getAttribute('data-tier');
          if (ct) hrToggleTier(ct);
          return;
        }
        var tile = e.target.closest('.rating-tile');
        if (tile) hrSelectAllTiers();
      });
    }
    // Header sort events
    var hdr = document.getElementById('hr-col-header-row');
    if (hdr) {
      hdr.addEventListener('click', function(e) {
        var th = e.target.closest('th');
        if (!th) return;
        var key = th.getAttribute('data-sort-key');
        if (key) hrOnSort(key);
      });
    }
    return true;
  }

  function renderHealthyRetest() {
    if (!hrBuildScaffold()) return;
    hrBuildHeaderRow();
    hrRenderRows();
    if (window.measureV2Ribbon) measureV2Ribbon();
  }
  window.renderHealthyRetest = renderHealthyRetest;

})();

/* MD-V2-S47-TAB-HEALTHY-RETEST-MARKER-MODULE-END */

"""

# 9. CSS selectors for V2 chrome. We need to add the new tab to every CSS
#    selector list that currently references "tests". We do this by finding
#    each 'body[data-active-tab="tests"]' and appending the new tab's
#    selector after it. However, since there are ~12 of these, a cleaner
#    approach is to do them all via a single bulk find-replace.

# Collect all the CSS selector pairs we need to extend:
CSS_SELECTORS_TO_EXTEND = [
    # Pattern: existing selector -> replacement with new tab added
    # (1) #hdr-chart-btn hide (line 539)
    ('body[data-active-tab="tests"] #hdr-chart-btn,body[data-active-tab="master_overview"] #hdr-chart-btn{display:none!important}',
     'body[data-active-tab="tests"] #hdr-chart-btn,body[data-active-tab="setups_healthy_retest"] #hdr-chart-btn,body[data-active-tab="master_overview"] #hdr-chart-btn{display:none!important}'),
    # (2-...) For the rest, the pattern is:
    #   'body[data-active-tab="tests"] .X,' or at end of selector
    # These all follow a pattern: add new tab selector after tests.
]


# ---------- BOILERPLATE — DO NOT EDIT BELOW ---------------------------

def _find_repo_root() -> str:
    cur = os.path.abspath(os.path.dirname(__file__))
    cand = os.path.abspath(os.path.join(cur, os.pardir))
    if os.path.basename(cand) == REPO_ROOT_HINT and os.path.exists(os.path.join(cand, ".git")):
        return cand
    walk = cur
    for _ in range(6):
        if os.path.exists(os.path.join(walk, ".git")):
            return walk
        walk = os.path.abspath(os.path.join(walk, os.pardir))
    raise SystemExit(f"[ABORT] cannot locate repo root from {cur}")


def _git_show_head_text(repo: str, rel: str) -> str:
    rel_posix = rel.replace(os.sep, "/")
    out = subprocess.run(
        ["git", "show", f"HEAD:{rel_posix}"],
        cwd=repo, check=True, capture_output=True,
    )
    return out.stdout.decode("utf-8")


def _wt_text(repo: str, rel: str) -> str:
    with open(os.path.join(repo, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def _md5_text(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def _apply_css_selector_extensions(src: str) -> str:
    """Add the new tab to every CSS selector list that references 'tests'."""
    # Strategy: wherever we see 'data-active-tab="tests"' in a CSS context,
    # we duplicate the selector with the new tab name appended.
    # We use a targeted approach: after each occurrence of
    #   body[data-active-tab="tests"]
    # in a CSS line, we insert a comma + the new tab's selector.
    
    import re
    
    # Pattern: body[data-active-tab="tests"] followed by a CSS property/class
    # We need to handle multiple forms:
    #   body[data-active-tab="tests"] .header-tabs-row,
    #   body[data-active-tab="tests"] .v2-nav,
    #   body[data-active-tab="tests"] .header,
    #   body[data-active-tab="tests"],
    #   body[data-active-tab="tests"] .controls.s1-controls,
    #   body[data-active-tab="tests"] .table-wrap,
    #   body[data-active-tab="tests"] .v2-hscroll,
    #   body[data-active-tab="tests"] #hdr-chart-btn
    
    # For each line containing 'data-active-tab="tests"', add the new tab.
    # We match: body[data-active-tab="tests"]( .something)?(,| {)
    # And insert: ,\nbody[data-active-tab="setups_healthy_retest"]\1\2
    
    lines = src.split('\n')
    new_lines = []
    for line in lines:
        if 'data-active-tab="tests"' in line and 'data-active-tab="setups_healthy_retest"' not in line:
            # Don't modify lines that are inside JS (chart wiring) - those have var or ;
            if 'var ' in line or line.strip().startswith('//') or line.strip().startswith('/*') or MARKER in line:
                new_lines.append(line)
                continue
            # CSS line: duplicate each tests selector occurrence
            line = re.sub(
                r'body\[data-active-tab="tests"\](\s*[^,{\n]*?)([,{])',
                r'body[data-active-tab="tests"]\1\2\nbody[data-active-tab="setups_healthy_retest"]\1\2',
                line
            )
        new_lines.append(line)
    return '\n'.join(new_lines)


def main(argv):
    test_mode = "--test" in argv
    repo = _find_repo_root()
    rel = TARGET_REL
    abs_target = os.path.join(repo, rel)

    print(f"[*] Repo root:      {repo}")
    print(f"[*] Target:         {rel}")
    print(f"[*] Marker:         {MARKER}")
    print(f"[*] Mode:           {'DRY-RUN (--test)' if test_mode else 'WRITE'}")

    head_src = _git_show_head_text(repo, rel)
    wt_src   = _wt_text(repo, rel)
    print(f"[*] HEAD chars:     {len(head_src)}")
    print(f"[*] WT chars:       {len(wt_src)}")
    print(f"[*] HEAD md5(text): {_md5_text(head_src)}")
    print(f"[*] WT md5(text):   {_md5_text(wt_src)}")

    if _md5_text(wt_src) != _md5_text(head_src):
        msg = "Working tree diverges from HEAD (text-normalized compare)."
        if test_mode:
            print(f"[WARN] {msg}")
            print("       Dry-run continues -- gates operate on HEAD source.")
        else:
            print(f"[ABORT] {msg}")
            print(f"        Run `git status` and `git diff -- {rel.replace(os.sep, '/')}` to investigate.")
            return 2

    if MARKER in head_src:
        print(f"[OK] MARKER already in HEAD -- this patch has already shipped.")
        return 0
    if MARKER in wt_src:
        print(f"[OK] MARKER already in WT but not in HEAD -- applied but not committed yet.")
        return 0

    src = head_src

    # --- Apply 7 anchored replacements ---
    anchors = [
        ("TABS array entry",          ANCHOR_1, REPLACE_1),
        ("IMPLEMENTED_TABS entry",    ANCHOR_2, REPLACE_2),
        ("Nav button",                ANCHOR_3, REPLACE_3),
        ("Chart wiring _v2chartTabs", ANCHOR_4, REPLACE_4),
        ("Chart wiring _v2ct",        ANCHOR_5, REPLACE_5),
        ("renderTab dispatcher",      ANCHOR_6, REPLACE_6),
    ]

    for label, anchor, replacement in anchors:
        n = src.count(anchor)
        print(f"[*] {label}: anchor matches = {n} (expected 1)")
        if n != 1:
            print(f"[ABORT] Anchor count != 1 for '{label}' -- source may have drifted.")
            return 3
        src = src.replace(anchor, replacement, 1)

    # --- Insert CSS + module before the Master Overview module ---
    n8 = src.count(ANCHOR_8)
    print(f"[*] CSS+module insertion: anchor matches = {n8} (expected 1)")
    if n8 != 1:
        print(f"[ABORT] Anchor count != 1 for CSS+module insertion.")
        return 3
    src = src.replace(ANCHOR_8, HR_CSS + "\n" + HR_MODULE + "\n" + ANCHOR_8, 1)

    # --- Add CSS selector extensions for V2 chrome ---
    print("[*] Extending CSS selectors for V2 chrome...")
    src = _apply_css_selector_extensions(src)

    # --- Validate ---
    assert MARKER in src, "[INTERNAL] MARKER missing after all replacements"

    new_src = src
    print(f"[*] Char delta:     {len(new_src) - len(head_src):+d}")
    print(f"[*] New md5(text):  {_md5_text(new_src)}")

    # --- Syntax check (it's Python, so ast.parse will pass; real check is that
    #     the embedded JS is well-formed, which we verify by string containment) ---
    if ENABLE_PY_COMPILE:
        try:
            ast.parse(new_src)
        except SyntaxError as e:
            print(f"[ABORT] ast.parse failed on new source: {e}")
            return 4
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tf:
            tf.write(new_src)
            tmp_py = tf.name
        try:
            py_compile.compile(tmp_py, doraise=True)
            print(f"[*] py_compile:     OK")
        except py_compile.PyCompileError as e:
            print(f"[ABORT] py_compile failed: {e}")
            return 5
        finally:
            try: os.unlink(tmp_py)
            except OSError: pass

    # --- Diff ---
    print("\n--- DIFF SUMMARY (first 100 + last 50 lines) ---")
    diff_lines = list(difflib.unified_diff(
        head_src.splitlines(keepends=True),
        new_src.splitlines(keepends=True),
        fromfile=f"HEAD:{rel}", tofile=f"PATCHED:{rel}", n=2,
    ))
    total_diff = len(diff_lines)
    added = sum(1 for l in diff_lines if l.startswith('+') and not l.startswith('+++'))
    removed = sum(1 for l in diff_lines if l.startswith('-') and not l.startswith('---'))
    print(f"[*] Diff: {total_diff} lines total, +{added} added, -{removed} removed")
    for line in diff_lines[:100]:
        sys.stdout.write(line)
    if total_diff > 150:
        print(f"\n... ({total_diff - 150} lines omitted) ...\n")
        for line in diff_lines[-50:]:
            sys.stdout.write(line)
    else:
        for line in diff_lines[100:]:
            sys.stdout.write(line)
    print("--- END DIFF ---\n")

    if test_mode:
        print(f"[OK] DRY-RUN: all gates passed. +{added} lines, -{removed} removed. Re-run without --test to write.")
        return 0

    # --- Write ---
    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = abs_target + f".bak-pre-{BAK_TAG}-{ts}"
    with open(bak, "w", encoding="utf-8") as fh:
        fh.write(wt_src)
    print(f"[*] Backup:         {os.path.relpath(bak, repo)}")

    target_dir = os.path.dirname(abs_target)
    fd, tmp_out = tempfile.mkstemp(prefix=".patch-", suffix=".tmp", dir=target_dir)
    os.close(fd)
    with open(tmp_out, "w", encoding="utf-8") as fh:
        fh.write(new_src)
    os.replace(tmp_out, abs_target)

    after = _wt_text(repo, rel)
    if _md5_text(after) != _md5_text(new_src):
        print(f"[ABORT] Post-write text-md5 mismatch! Restore: {os.path.relpath(bak, repo)}")
        return 6
    if MARKER not in after:
        print("[ABORT] Post-write MARKER missing.")
        return 7

    disk_bytes = os.path.getsize(abs_target)
    print(f"[OK] WRITE complete. {len(after)} chars, {disk_bytes} bytes on disk. MARKER present.")
    print(f"[OK] Next: python scripts/build_dashboard.py && git add -A && git commit && git push")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
