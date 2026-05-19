"""
=============================================================================
PATCHER — tests_probing_bet dashboard tab (Probing Bets: Stages 1+2)
=============================================================================
Project: SA - Master Dashboard
Session: S47 (18-May-2026), Task 2 (§6.1)
Decision: D-MD-V2-108 + D-MD-V2-110 (locked 18-May-2026)
Author: [W] Watson (SYSTEMS ARCHITECT role) under Richard's direction
Template: PATCHER-TEMPLATE.py (D-MD-INFRA-5 text-mode I/O)

WHAT THIS PATCHER DOES
----------------------
Adds a new dashboard tab "tests_probing_bet" rendering two S46 pipeline
test variants side-by-side:
  - probing_bet_s1 (Stage 1 early probing bet) — 6 criteria
  - probing_bet_s2 (Stage 2 idiosyncratic probing bet) — 6 criteria

Changes made to build_dashboard.py:
  1. TABS array entry
  2. IMPLEMENTED_TABS entry
  3. Nav button in Capital deployment group
  4. Chart wiring in _v2chartTabs and _v2ct objects
  5. CSS block for #tab-tests_probing_bet
  6. Self-contained render module (IIFE) — two patterns on one tab
  7. renderTab dispatcher case
  8. CSS selectors for V2 tab chrome

DEPENDS ON: Patcher 1 (setups_healthy_retest) having been applied first,
because this patcher's anchors include MARKER text from Patcher 1.

USAGE
-----
1. Dry-run:  python3 scripts/patch_md_v2_tab_probing_bet_s47_2026_05_18.py --test
2. Apply:    python scripts/patch_md_v2_tab_probing_bet_s47_2026_05_18.py
             python scripts/build_dashboard.py
             git add scripts/build_dashboard.py index.html
             git commit -m "feat(MD V2 S47): probing-bet tab S1+S2 (6-criterion x2, S46 pipeline)"
=============================================================================
"""
from __future__ import annotations
import ast
import datetime as _dt
import difflib
import hashlib
import os
import py_compile
import re
import subprocess
import sys
import tempfile

# ============ CONFIGURE ME ============================================
REPO_ROOT_HINT = "master-dashboard"
TARGET_REL     = os.path.join("scripts", "build_dashboard.py")
MARKER         = "MD-V2-S47-TAB-PROBING-BET-MARKER"
# Patcher 1 must have been applied first
PREREQ_MARKER  = "MD-V2-S47-TAB-HEALTHY-RETEST-MARKER"
BAK_TAG        = "s47-tab-pb"
ENABLE_PY_COMPILE = True
# ======================================================================

# 1. TABS array: insert after setups_healthy_retest entry
ANCHOR_1 = '    {"id": "setups_healthy_retest", "label": "Healthy Retest", "accent": "#2E7D32"},'
REPLACE_1 = ('    {"id": "setups_healthy_retest", "label": "Healthy Retest", "accent": "#2E7D32"},\n'
             '    # MD-V2-S47-TAB-PROBING-BET-MARKER - Probing Bets S1+S2 (6-criterion x2)\n'
             '    {"id": "tests_probing_bet", "label": "Probing Bets", "accent": "#6b46c1"},')

# 2. IMPLEMENTED_TABS: insert after setups_healthy_retest
ANCHOR_2 = '    "setups_healthy_retest",  # MD-V2-S47-TAB-HEALTHY-RETEST-MARKER'
REPLACE_2 = ('    "setups_healthy_retest",  # MD-V2-S47-TAB-HEALTHY-RETEST-MARKER\n'
             '    "tests_probing_bet",  # MD-V2-S47-TAB-PROBING-BET-MARKER')

# 3. Nav button: insert after healthy retest button
ANCHOR_3 = "      + '<button class=\"v2-nav-btn v2-grp-tests\" data-v2-tab=\"setups_healthy_retest\" onclick=\"switchTab(\\'setups_healthy_retest\\')\">Healthy Retest</button>'  /* MD-V2-S47-TAB-HEALTHY-RETEST-MARKER */"
REPLACE_3 = ("      + '<button class=\"v2-nav-btn v2-grp-tests\" data-v2-tab=\"setups_healthy_retest\" onclick=\"switchTab(\\'setups_healthy_retest\\')\">Healthy Retest</button>'  /* MD-V2-S47-TAB-HEALTHY-RETEST-MARKER */\n"
             "      + '<button class=\"v2-nav-btn v2-grp-tests\" data-v2-tab=\"tests_probing_bet\" onclick=\"switchTab(\\'tests_probing_bet\\')\">Probing Bets</button>'  /* MD-V2-S47-TAB-PROBING-BET-MARKER */")

# 4. Chart wiring _v2chartTabs
ANCHOR_4 = 'var _v2chartTabs={stage_1:1,stage_2:1,stage_3:1,stage_4:1,pre_indicators:1,post_indicators:1,setups_s1pb:1,setups_s2vcp:1,tests:1,setups_healthy_retest:1,master_overview:1};  /* MD-V2-S47-TAB-HEALTHY-RETEST-MARKER */'
REPLACE_4 = 'var _v2chartTabs={stage_1:1,stage_2:1,stage_3:1,stage_4:1,pre_indicators:1,post_indicators:1,setups_s1pb:1,setups_s2vcp:1,tests:1,setups_healthy_retest:1,tests_probing_bet:1,master_overview:1};  /* MD-V2-S47-TAB-PROBING-BET-MARKER */'

# 5. Chart wiring _v2ct
ANCHOR_5 = 'var _v2ct={stage_1:1,stage_2:1,stage_3:1,stage_4:1,pre_indicators:1,post_indicators:1,setups_s1pb:1,setups_s2vcp:1,tests:1,setups_healthy_retest:1,master_overview:1};  /* MD-V2-S47-TAB-HEALTHY-RETEST-MARKER */'
REPLACE_5 = 'var _v2ct={stage_1:1,stage_2:1,stage_3:1,stage_4:1,pre_indicators:1,post_indicators:1,setups_s1pb:1,setups_s2vcp:1,tests:1,setups_healthy_retest:1,tests_probing_bet:1,master_overview:1};  /* MD-V2-S47-TAB-PROBING-BET-MARKER */'

# 6. renderTab dispatcher: insert after healthy retest case
ANCHOR_6 = "  else if(id===\"setups_healthy_retest\")renderHealthyRetest();  /* MD-V2-S47-TAB-HEALTHY-RETEST-MARKER */"
REPLACE_6 = ("  else if(id===\"setups_healthy_retest\")renderHealthyRetest();  /* MD-V2-S47-TAB-HEALTHY-RETEST-MARKER */\n"
             "  else if(id===\"tests_probing_bet\")renderProbingBet();  /* MD-V2-S47-TAB-PROBING-BET-MARKER */")

# 7. CSS + module: insert before MD-V2-MASTER-OVERVIEW-MARKER-MODULE-START
ANCHOR_7 = '/* MD-V2-MASTER-OVERVIEW-MARKER-MODULE-START */'

PB_CSS = r"""
/* MD-V2-S47-TAB-PROBING-BET-MARKER-CSS-START */
/* Probing Bets (S1+S2) — two 6-criterion test variants on one tab (S47) */
#tab-tests_probing_bet .group-captions { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin: 16px 0 14px 0; }
#tab-tests_probing_bet .group-captions .gcap { background: #fbfaf5; border: 1px solid #e0dcc8; border-left: 3px solid #6b46c1; border-radius: 4px; padding: 10px 12px; font-size: 11px; line-height: 1.45; color: #555; }
#tab-tests_probing_bet .group-captions .gcap b { display: block; margin-bottom: 4px; font-weight: 700; color: #6b46c1; font-size: 11px; letter-spacing: 0.2px; }
#tab-tests_probing_bet .group-captions .gcap-g1 { border-left-color: #6b46c1; }
#tab-tests_probing_bet .group-captions .gcap-g1 b { color: #6b46c1; }
#tab-tests_probing_bet .group-captions .gcap-g2 { border-left-color: #7c3aed; }
#tab-tests_probing_bet .group-captions .gcap-g2 b { color: #7c3aed; }
#tab-tests_probing_bet .s1-rating-tiles { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
#tab-tests_probing_bet .s1-rating-tiles .pi-tile-s1 { background: rgba(107,70,193,0.10); border: 1px solid rgba(107,70,193,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
#tab-tests_probing_bet .s1-rating-tiles .pi-tile-s1.active { background: rgba(107,70,193,0.22); border: 1.5px solid #6b46c1; }
#tab-tests_probing_bet .s1-rating-tiles .pi-strip-s1 { background: #6b46c1; height: 4px; margin-top: 6px; border-radius: 2px; }
#tab-tests_probing_bet .s1-rating-tiles .pi-tile-s2 { background: rgba(124,58,237,0.10); border: 1px solid rgba(124,58,237,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
#tab-tests_probing_bet .s1-rating-tiles .pi-tile-s2.active { background: rgba(124,58,237,0.22); border: 1.5px solid #7c3aed; }
#tab-tests_probing_bet .s1-rating-tiles .pi-strip-s2 { background: #7c3aed; height: 4px; margin-top: 6px; border-radius: 2px; }
#tab-tests_probing_bet .s1-rating-tiles .rt-breakdown { font-size: 9px; color: #888; margin-top: 4px; line-height: 1.35; }
#tab-tests_probing_bet .pi-tier-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 7px; }
#tab-tests_probing_bet .pi-tier-chip { font-size: 10px; padding: 2px 6px; border-radius: 4px; cursor: pointer; user-select: none; border: 0.5px solid; line-height: 1.4; white-space: nowrap; transition: background 0.12s, color 0.12s; }
#tab-tests_probing_bet .pi-chip-s1 { background: #EDE9F9; color: #6b46c1; border-color: #C4B5FD; }
#tab-tests_probing_bet .pi-chip-s1.on { background: #6b46c1; color: #fff; border-color: #6b46c1; font-weight: 500; }
#tab-tests_probing_bet .pi-chip-s2 { background: #EDE9F9; color: #7c3aed; border-color: #C4B5FD; }
#tab-tests_probing_bet .pi-chip-s2.on { background: #7c3aed; color: #fff; border-color: #7c3aed; font-weight: 500; }
#tab-tests_probing_bet .pi-tier-chip:hover { filter: brightness(0.96); }
/* Table styles — clone ct-main-table with purple accent */
#pb-main-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 11px; table-layout: fixed; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }
#pb-main-table thead { position: sticky; top: 0; z-index: 50; background: #fbfaf5; box-shadow: 0 2px 4px rgba(0,0,0,0.06); }
#pb-main-table thead th { background: #fbfaf5 !important; border-bottom: 1px solid #e0dcc8; padding: 7px 3px; text-align: center; font-weight: 600; font-size: 10px; color: #666; cursor: pointer; user-select: none; line-height: 1.25; vertical-align: middle; }
#pb-main-table thead th:hover { background: #f0ebd9 !important; }
#pb-main-table thead .group-header-row th { background: #f3efe2 !important; font-size: 9.5px; text-transform: none; font-weight: 700; letter-spacing: 0.2px; padding: 5px 3px; cursor: default; line-height: 1.25; }
#pb-main-table thead tr.group-header-row th { position: sticky; top: 0; }
#pb-main-table thead tr.sub-group-row th { position: sticky; top: 24px; font-size: 9px; text-transform: uppercase; letter-spacing: 0.3px; color: #888; padding: 3px; font-weight: 600; background: #f8f6ee !important; border-bottom: 1px solid #e0dcc8; }
#pb-main-table thead tr.col-header-row th { position: sticky; top: 44px; border-top: 1px solid #e0dcc8; }
#pb-main-table thead .gh-inputs { color: #555; }
#pb-main-table thead .gh-stageinfo { color: #7a6a3a; }
#pb-main-table thead .gh-g1 { color: #6b46c1; }
#pb-main-table thead .gh-g2 { color: #7c3aed; }
#pb-main-table .hd { display: inline-flex; align-items: center; justify-content: center; gap: 3px; width: 100%; }
#pb-main-table .hd .lbl { white-space: normal; word-break: break-word; }
#pb-main-table .hd .sort-arrow { font-size: 9px; color: #6b46c1; flex: 0 0 auto; line-height: 1; }
#pb-main-table .hd .sort-placeholder { width: 9px; flex: 0 0 auto; }
#pb-main-table td { padding: 5px 4px; border-bottom: 1px solid #efece0; text-align: center; vertical-align: middle; height: 38px; box-sizing: border-box; font-variant-numeric: tabular-nums; }
#pb-main-table tr:hover { background: rgba(107,70,193,0.05); }
#pb-main-table td.grp-start-stageinfo, #pb-main-table th.grp-start-stageinfo { border-left: 2px solid rgba(122,106,58,0.40); }
#pb-main-table td.grp-start-g1, #pb-main-table th.grp-start-g1 { border-left: 2px solid rgba(107,70,193,0.40); }
#pb-main-table td.grp-start-g2, #pb-main-table th.grp-start-g2 { border-left: 2px solid rgba(124,58,237,0.40); }
#pb-main-table td.pi-pass { background: rgba(107,70,193,0.12); color: #6b46c1; font-weight: 700; }
#pb-main-table td.pi-fail { color: #999; }
#pb-main-table td.pi-rating-cell { padding: 3px 4px; }
#pb-main-table .pi-pill { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 9px; font-weight: 700; line-height: 1.3; white-space: nowrap; }
#pb-main-table .pi-pill-tint-qualified { background: #4c1d95; color: #fff; }
#pb-main-table .pi-pill-tint-prob { background: #6b46c1; color: #fff; }
#pb-main-table .pi-pill-tint-pla  { background: rgba(107,70,193,0.30); color: #3b1f7a; }
#pb-main-table .pi-pill-tint-pos  { background: rgba(107,70,193,0.14); color: #5a4a7a; }
#pb-main-table .pi-pill-tint-none { background: #ece9dd; color: #999; }
#pb-main-table td.pi-score-cell { padding: 4px 3px; }
#pb-main-table .pi-pip-row { display: inline-flex; align-items: center; gap: 2px; justify-content: center; }
#pb-main-table .pi-pip-row .pip { width: 6px; height: 6px; border-radius: 50%; background: #d8d4c4; display: inline-block; }
#pb-main-table .pi-pip-row .pip.on { background: #6b46c1; }
#pb-main-table .pi-pip-row .pi-score-num { font-size: 9px; color: #777; margin-left: 3px; font-weight: 600; }
#pb-main-table td.ct-stage-info-cell { padding: 3px 4px; }
#pb-main-table .ct-info-label { display: inline-block; padding: 2px 5px; border-radius: 3px; font-size: 9px; font-weight: 600; line-height: 1.3; white-space: nowrap; }
#pb-main-table td.ct-stage-info-cell.tint-prob .ct-info-label { background: rgba(107,70,193,0.22); color: #3b1f7a; }
#pb-main-table td.ct-stage-info-cell.tint-pla  .ct-info-label { background: rgba(107,70,193,0.13); color: #5a4a7a; }
#pb-main-table td.ct-stage-info-cell.tint-pos  .ct-info-label { background: rgba(107,70,193,0.07); color: #6a7a72; }
#pb-main-table td.ct-stage-info-cell.tint-none .ct-info-label { background: #f0ede1; color: #aaa; }
#pb-main-table td.ct-window-col { padding: 3px 4px; font-size: 10px; }
#pb-main-table td.ct-window-fired-recent { background: rgba(107,70,193,0.16); }
#pb-main-table td.ct-window-fired-recent .ct-window-label { color: #3b1f7a; font-weight: 700; }
#pb-main-table td.ct-window-fired-older { background: rgba(186,117,23,0.14); }
#pb-main-table td.ct-window-fired-older .ct-window-label { color: #7a4e0a; font-weight: 600; }
#pb-main-table td.ct-window-none { color: #bbb; }
#pb-main-table td.ct-window-building { color: #b59a5a; font-style: italic; font-size: 9px; }
#pb-main-table td.name-cell { text-align: left; padding: 4px 4px 4px 8px; line-height: 1.15; }
#pb-main-table td.name-cell .co { font-weight: 700; font-size: 11px; color: #2a2a2a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#pb-main-table td.name-cell .tk { font-size: 9px; color: #999; font-weight: 500; margin-top: 1px; }
#pb-main-table td.name-cell .live-dot { color: #2e7d32; font-weight: 700; margin-right: 4px; }
#pb-main-table td.taxon { text-align: left; font-size: 9px; line-height: 1.2; padding: 4px; }
#pb-main-table td.taxon .ind { color: #666; font-weight: 500; }
#pb-main-table td.taxon .sec { color: #999; }
#pb-main-table col.c-name { width: 124px; }
#pb-main-table col.c-taxon { width: 150px; }
#pb-main-table col.c-price { width: 50px; }
#pb-main-table col.c-52wh { width: 48px; }
#pb-main-table col.c-52wl { width: 48px; }
#pb-main-table col.c-ma150 { width: 48px; }
#pb-main-table col.c-ma200 { width: 48px; }
#pb-main-table col.c-pullback { width: 58px; }
#pb-main-table col.c-stageinfo { width: 56px; }
#pb-main-table col.c-rating { width: 64px; }
#pb-main-table col.c-score { width: 52px; }
#pb-main-table col.c-test { width: 64px; }
#pb-main-table col.c-window { width: 52px; }
#pb-main-table tr.tint-row td.name-cell, #pb-main-table tr.tint-row td.taxon { background: var(--tint-bg) !important; }
#pb-main-table tr.portfolio-band td:last-child { border-right: 4px solid var(--portfolio-color); }
#pb-main-table tr.portfolio-tint { background: var(--portfolio-bg); }
#pb-main-table tr.portfolio-tint:hover { background: var(--portfolio-bg-hover); }
/* MD-V2-S47-TAB-PROBING-BET-MARKER-CSS-END */
"""

PB_MODULE = r"""
/* MD-V2-S47-TAB-PROBING-BET-MARKER-MODULE-START */
// =============================================================================
// PROBING BETS (S1+S2) — TAB MODULE (S47)
// =============================================================================
// MD-V2-S47-TAB-PROBING-BET-MARKER
// Two 6-criterion test variants on one tab:
//   probing_bet_s1: Stage 1 MT troughing + breakout => S1 early probing bet
//   probing_bet_s2: Stage 2 MT/LT uptrend + breakout => S2 idiosyncratic probing bet
// =============================================================================

(function() {
  'use strict';

  var PB_PATTERNS = [
    {
      key: 'probing_bet_s1',
      label: 'Stage 1 MT troughing trend + breakout ⇒ S1 early probing bet',
      shortLabel: 'S1 Probing',
      tone: 's1',
      tierLadder: ['Possible', 'Plausible', 'Probable', 'Qualified'],
      total: 6,
      tooltip: 'A breakout on a Stage 1 (basing/troughing) stock — a probing position to see if the trend is turning.',
      caption: '<span class="db">A positive breakout on a Stage 1 stock.</span> The 5D and 10D MAs must be rising. Price must be above the 20D MA, and the 20D MA must have turned up in the last 5 days. Confirmation requires a close 2%+ above yesterday.',
      tests: [
        { key: 'g1_stage_qualifies',            label: 'Stage 1 qualifies',    group: 'gate',    tooltip: 'Stage 1 rating is Probable or Plausible — hard precondition' },
        { key: 'g2_5d_rising',                   label: '5D MA rising',         group: 'setup',   tooltip: '5-day moving average is rising day-over-day' },
        { key: 'g3_10d_rising',                  label: '10D MA rising',        group: 'setup',   tooltip: '10-day moving average is rising day-over-day' },
        { key: 'g4_price_gt_20d',                label: 'Price > 20D MA',       group: 'trigger', tooltip: 'Current price is above the 20-day moving average' },
        { key: 'g5_20d_turn_last_5d',            label: '20D MA turned up',     group: 'trigger', tooltip: '20D MA is rising now AND was falling 5 days ago — the turn' },
        { key: 'g6_followthrough_close_ge2pct',  label: 'Confirm: close 2%+',   group: 'trigger', tooltip: 'Today close at least 2% above yesterday — follow-through confirmation' }
      ]
    },
    {
      key: 'probing_bet_s2',
      label: 'Stage 2 MT/LT uptrend + breakout ⇒ S2 idiosyncratic probing bet',
      shortLabel: 'S2 Probing',
      tone: 's2',
      tierLadder: ['Possible', 'Plausible', 'Probable', 'Qualified'],
      total: 6,
      tooltip: 'A breakout on a Stage 2 (uptrend) stock that did not base or pull back — a probing position, often event-driven.',
      caption: '<span class="db">A positive breakout on a Stage 2 stock without the standard pullback or basing pattern.</span> Same criteria as S1 probing bet, but the stock is in a confirmed MT/LT uptrend. Often triggered by an event or news.',
      tests: [
        { key: 'g1_stage_qualifies',            label: 'Stage 2 qualifies',    group: 'gate',    tooltip: 'Stage 2 rating is Probable or Plausible — hard precondition' },
        { key: 'g2_5d_rising',                   label: '5D MA rising',         group: 'setup',   tooltip: '5-day moving average is rising day-over-day' },
        { key: 'g3_10d_rising',                  label: '10D MA rising',        group: 'setup',   tooltip: '10-day moving average is rising day-over-day' },
        { key: 'g4_price_gt_20d',                label: 'Price > 20D MA',       group: 'trigger', tooltip: 'Current price is above the 20-day moving average' },
        { key: 'g5_20d_turn_last_5d',            label: '20D MA turned up',     group: 'trigger', tooltip: '20D MA is rising now AND was falling 5 days ago — the turn' },
        { key: 'g6_followthrough_close_ge2pct',  label: 'Confirm: close 2%+',   group: 'trigger', tooltip: 'Today close at least 2% above yesterday — follow-through confirmation' }
      ]
    }
  ];

  var PB_TONE_TILE  = { s1:'pi-tile-s1', s2:'pi-tile-s2' };
  var PB_TONE_STRIP = { s1:'pi-strip-s1', s2:'pi-strip-s2' };
  var PB_TONE_CHIP  = { s1:'s1', s2:'s2' };

  var pbState = {
    mode: { inputs: 'pct', tests: 'tick' },
    scope: 'all',
    tierFilter: {},
    tint: 'none',
    port: 'off',
    sort: { col: 'company', dir: 'asc' }
  };
  for (var _ip = 0; _ip < PB_PATTERNS.length; _ip++) pbState.tierFilter[PB_PATTERNS[_ip].key] = [];

  var PB_RATING_RANK = { 'Qualified':6, 'Probable':5, 'Plausible':3, 'Possible':2, 'None':1 };
  var PB_RATING_CLS  = { 'Qualified':'tint-qualified', 'Probable':'tint-prob', 'Plausible':'tint-pla', 'Possible':'tint-pos', 'None':'tint-none' };

  // --- data lookups ---
  function pbPricesLookup() {
    if (window._ctPricesByTicker) return window._ctPricesByTicker;
    var out = {};
    var arr = (window.MASTER_DATA && MASTER_DATA.prices) || [];
    for (var i = 0; i < arr.length; i++) if (arr[i] && arr[i].ticker) out[arr[i].ticker] = arr[i];
    window._ctPricesByTicker = out;
    return out;
  }
  function pbLiveTickers() { var o = {}; var inv = (window.MASTER_DATA && MASTER_DATA.positions && MASTER_DATA.positions.investments) || []; for (var i = 0; i < inv.length; i++) if (inv[i].ticker) o[inv[i].ticker] = true; return o; }
  function pbLiveSectors() { var o = {}, p = pbPricesLookup(), t = pbLiveTickers(); for (var k in t) { var px = p[k]; if (px && px.sector) o[px.sector] = true; } return o; }
  function pbLiveIndustries() { var o = {}, p = pbPricesLookup(), t = pbLiveTickers(); for (var k in t) { var px = p[k]; if (px && px.industry) o[px.industry] = true; } return o; }
  function pbPatternRec(row, patternKey) { var dk = row.md_v2 && row.md_v2.tests; return (dk && dk[patternKey]) || null; }
  function pbEvalTest(row, patternKey, testKey) { var rec = pbPatternRec(row, patternKey); if (!rec || !rec.tests) return false; return !!rec.tests[testKey]; }
  function pbRowRating(row, patternKey) { var rec = pbPatternRec(row, patternKey); return rec ? (rec.rating || 'None') : 'None'; }
  function pbStageRating(row, stageKey) { var md = row.md_v2 || {}; var st = md[stageKey]; return (st && st.rating) || 'None'; }
  function pbGetRows() {
    var raw = (window.MASTER_DATA && MASTER_DATA.filters) || [];
    var prices = pbPricesLookup();
    var live = pbLiveTickers(), liveS = pbLiveSectors(), liveI = pbLiveIndustries();
    var rows = [];
    for (var i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || !s.md_v2 || !s.md_v2.tests) continue;
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
  function pbTierCounts(rows, patternKey) { var c = { 'Qualified':0, 'Probable':0, 'Plausible':0, 'Possible':0, 'None':0 }; for (var i = 0; i < rows.length; i++) { var r = pbRowRating(rows[i], patternKey); if (c[r] != null) c[r]++; } return c; }
  function pbPassHistogram(rows, patternKey) { var h = []; for (var k = 0; k <= 6; k++) h[k] = 0; for (var i = 0; i < rows.length; i++) { var rec = pbPatternRec(rows[i], patternKey); var cnt = rec ? (rec.count || 0) : 0; if (cnt >= 0 && cnt <= 6) h[cnt]++; } return h; }

  // --- formatting helpers ---
  function pbFmtNum(n) { if (n == null || isNaN(n)) return '-'; var abs = Math.abs(n); var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2); if (Math.abs(n - Math.round(n)) < 1e-9) dp = 0; var f = abs.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp }); return n < 0 ? '(' + f + ')' : f; }
  function pbFmtPct(p) { if (p == null || isNaN(p)) return '-'; var r = Math.round(p), abs = Math.abs(r); return r < 0 ? '(' + abs + ')%' : r + '%'; }
  function pbColourForIntensity(i) { if (i >= 0.6) return '#6b46c1'; if (i >= 0.25) return '#7c3aed'; if (i >= 0.05) return '#a78bfa'; if (i <= -0.6) return '#A32D2D'; if (i <= -0.25) return '#E24B4A'; if (i <= -0.05) return '#F09595'; return '#888'; }
  function pbInputCell(row, key, extraCls) {
    extraCls = extraCls || '';
    var v = row[key];
    if (key === 'price') return '<td class="num ' + extraCls + '">' + pbFmtNum(v) + '</td>';
    if (key === 'recent_pullback') { if (v == null || isNaN(v)) return '<td class="num ' + extraCls + '">-</td>'; var pctVal = v * 100; var pi_i = Math.max(-1, Math.min(1, (pctVal - 5) / 20)); return '<td class="num ' + extraCls + '" style="color:' + pbColourForIntensity(-pi_i) + '">' + Math.round(pctVal) + '%</td>'; }
    if (v == null || row.price == null) return '<td class="num ' + extraCls + '">-</td>';
    var pct = (row.price - v) / v * 100;
    var intensity = 0;
    if (key === 'high_52w') intensity = Math.max(-1, Math.min(1, (-pct - 5) / 20));
    else if (key === 'low_52w') intensity = Math.max(-1, Math.min(1, (pct - 20) / 30));
    else if (key === 'ma_150' || key === 'ma_200') intensity = Math.max(-1, Math.min(1, pct / 10));
    var text = (pbState.mode.inputs === 'pct') ? pbFmtPct(pct) : pbFmtNum(v);
    return '<td class="num ' + extraCls + '" style="color:' + pbColourForIntensity(intensity) + '">' + text + '</td>';
  }
  function pbStageInfoCell(row, stageKey, cls) { var rating = pbStageRating(row, stageKey); var rcls = PB_RATING_CLS[rating] || (rating.indexOf('Probable') === 0 ? 'tint-prob' : rating.indexOf('Plausible') === 0 ? 'tint-pla' : rating.indexOf('Possible') === 0 ? 'tint-pos' : 'tint-none'); return '<td class="' + (cls || '') + ' ct-stage-info-cell ' + rcls + '"><span class="ct-info-label">' + rating + '</span></td>'; }
  function pbTestValueFor(row, patternKey, testKey) { var rec = pbPatternRec(row, patternKey); var tv = rec && rec.test_values; if (!tv || !(testKey in tv)) return '—'; var v = tv[testKey]; if (v === null || v === undefined) return '—'; if (typeof v === 'string') return v; if (typeof v === 'number') { if (isNaN(v)) return '—'; if (Math.abs(v) <= 1.5 && v !== Math.round(v)) return pbFmtPct(v * 100); return pbFmtNum(v); } return String(v); }
  function pbTestCell(row, patternKey, testKey, cls) {
    var pass = pbEvalTest(row, patternKey, testKey);
    var extra = cls || '';
    if (pbState.mode.tests === 'val') { var v = pbTestValueFor(row, patternKey, testKey); var colour = pass ? pbColourForIntensity(0.7) : pbColourForIntensity(-0.4); return '<td class="test-val pi-' + (pass ? 'pass' : 'fail') + ' ' + extra + '" style="color:' + colour + '">' + v + '</td>'; }
    if (pass) return '<td class="pi-pass ' + extra + '"><span class="tick">' + String.fromCharCode(10003) + '</span></td>';
    return '<td class="pi-fail ' + extra + '">.</td>';
  }
  function pbRatingCell(row, patternKey, cls) { var rating = pbRowRating(row, patternKey); var rcls = PB_RATING_CLS[rating] || 'tint-none'; return '<td class="' + (cls || '') + ' pi-rating-cell ' + rcls + '"><span class="pi-pill pi-pill-' + rcls + '">' + rating + '</span></td>'; }
  function pbScoreCell(row, patternKey, cls) { var rec = pbPatternRec(row, patternKey); var cnt = rec ? (rec.count || 0) : 0; var tot = rec ? (rec.total || 0) : 0; var s = ''; for (var i = 0; i < tot; i++) s += '<span class="pip ' + (i < cnt ? 'on' : '') + '"></span>'; return '<td class="' + (cls || '') + ' pi-score-cell"><div class="pi-pip-row">' + s + '<span class="pi-score-num">' + cnt + '/' + tot + '</span></div></td>'; }
  function pbWindowCell(row, patternKey, windowKey, cls) { var rec = pbPatternRec(row, patternKey); var extra = cls || ''; if (!rec) return '<td class="' + extra + ' ct-window-na">-</td>'; var depth = rec.history_depth || 0; var windowDays = (windowKey === 'l5d') ? 5 : 20; if (depth < windowDays) return '<td class="' + extra + ' ct-window-building" title="' + depth + ' of ' + windowDays + ' days of history accumulated">building</td>'; var fired = (windowKey === 'l5d') ? !!rec.fired_l5d : !!rec.fired_l20d; if (!fired) return '<td class="' + extra + ' ct-window-none">-</td>'; var ds = rec.days_since_fired; var label; if (ds === 0) label = 'today'; else if (ds === 1) label = '1d ago'; else if (ds != null) label = ds + 'd ago'; else label = 'fired'; var shadeCls = (ds != null && ds <= 5) ? 'ct-window-fired-recent' : 'ct-window-fired-older'; return '<td class="' + extra + ' ' + shadeCls + '"><span class="ct-window-label">' + label + '</span></td>'; }
  function pbHashColor(label, alpha) { if (!label) return null; var h = 0; for (var i = 0; i < label.length; i++) h = (h * 31 + label.charCodeAt(i)) & 0xffff; return 'hsla(' + (h % 360) + ', 35%, 55%, ' + alpha + ')'; }
  function pbPortfolioInfo(row) { if (row.is_live) return { color:'#1b5e20', bg:'rgba(27,94,32,0.10)', bgHover:'rgba(27,94,32,0.14)' }; if (row.sector_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.05)', bgHover:'rgba(27,94,32,0.08)' }; if (row.industry_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.025)', bgHover:'rgba(27,94,32,0.05)' }; return null; }

  // --- column model (built dynamically like ct module) ---
  function pbBuildCols() {
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
    for (var si = 0; si < STAGES.length; si++) cols.push({ id:'info_'+STAGES[si], sortKey:'stageinfo__'+STAGES[si], kind:'stageinfo', stageKey:STAGES[si] });
    for (var p = 0; p < PB_PATTERNS.length; p++) {
      var pat = PB_PATTERNS[p];
      var gi = p + 1;
      cols.push({ id:'p'+gi+'_rating', sortKey:pat.key+'__rating', kind:'rating', patternKey:pat.key });
      cols.push({ id:'p'+gi+'_score',  sortKey:pat.key+'__score',  kind:'score',  patternKey:pat.key });
      for (var t = 0; t < pat.tests.length; t++) {
        cols.push({ id:'p'+gi+'t'+(t+1), sortKey:pat.key+'__'+pat.tests[t].key, kind:'test', patternKey:pat.key, testKey:pat.tests[t].key, group:pat.tests[t].group, label:pat.tests[t].label, tooltip:pat.tests[t].tooltip });
      }
      cols.push({ id:'p'+gi+'_l5d',  sortKey:pat.key+'__l5d',  kind:'window', patternKey:pat.key, windowKey:'l5d' });
      cols.push({ id:'p'+gi+'_l20d', sortKey:pat.key+'__l20d', kind:'window', patternKey:pat.key, windowKey:'l20d' });
    }
    return cols;
  }
  var PB_COLS = pbBuildCols();
  var PB_INPUT_COUNT = 8;
  var PB_STAGEINFO_COUNT = 4;

  // --- sorting ---
  function pbGetSortVal(row, key) {
    if (key.indexOf('stageinfo__') === 0) { var sk = key.split('__')[1]; return PB_RATING_RANK[pbStageRating(row, sk)] || 0; }
    if (key.indexOf('__') > 0) {
      var parts = key.split('__'); var patKey = parts[0], sub = parts[1];
      var rec = pbPatternRec(row, patKey);
      if (sub === 'rating') return rec ? (PB_RATING_RANK[rec.rating] || 0) : 0;
      if (sub === 'score')  return rec ? (rec.count || 0) : 0;
      if (sub === 'l5d' || sub === 'l20d') { if (!rec) return -1; var wd = (sub === 'l5d') ? 5 : 20; if ((rec.history_depth || 0) < wd) return -2; var fired = (sub === 'l5d') ? rec.fired_l5d : rec.fired_l20d; if (!fired) return -1; var ds = rec.days_since_fired; return (ds == null) ? 0 : (1000 - ds); }
      return pbEvalTest(row, patKey, sub) ? 1 : 0;
    }
    if (key === 'recent_pullback') return row.recent_pullback == null ? -Infinity : row.recent_pullback;
    var PCT_KEYS = ['high_52w','low_52w','ma_150','ma_200'];
    if (PCT_KEYS.indexOf(key) > -1 && pbState.mode.inputs === 'pct') { var ref = row[key]; if (ref == null || row.price == null || ref === 0) return -Infinity; return (row.price - ref) / ref * 100; }
    if (key in row) return row[key];
    return 0;
  }
  function pbOnSort(key) {
    if (pbState.sort.col === key) pbState.sort.dir = pbState.sort.dir === 'desc' ? 'asc' : 'desc';
    else pbState.sort = { col: key, dir: key === 'company' ? 'asc' : 'desc' };
    pbBuildHeaderRow();
    pbRenderRows();
  }
  function pbBuildHeaderRow() {
    var tr = document.getElementById('pb-col-header-row');
    if (!tr) return;
    var INPUT_LABELS = ['Company - Ticker','Industry - Sector','Price','52wk high','52wk low','150D MA','200D MA','Pullback'];
    var STAGE_LABELS = ['Stage 1','Stage 2','Stage 3','Stage 4'];
    var h = '';
    for (var i = 0; i < PB_COLS.length; i++) {
      var c = PB_COLS[i];
      var isSort = pbState.sort.col === c.sortKey;
      var arrow = isSort ? '<span class="sort-arrow">' + (pbState.sort.dir === 'desc' ? String.fromCharCode(9660) : String.fromCharCode(9650)) + '</span>' : '<span class="sort-placeholder"></span>';
      var label, title, cls = '';
      if (c.kind === 'input') { label = INPUT_LABELS[i]; title = label; }
      else if (c.kind === 'stageinfo') { label = STAGE_LABELS[i - PB_INPUT_COUNT]; title = label + ' rating'; cls = (i === PB_INPUT_COUNT ? 'grp-start-stageinfo ' : ''); }
      else if (c.kind === 'rating') { label = 'Rating'; title = c.patternKey + ' rating'; cls = 'grp-start-g' + (PB_PATTERNS.indexOf(PB_PATTERNS.filter(function(p){return p.key===c.patternKey})[0]) + 1) + ' '; }
      else if (c.kind === 'score') { label = 'Score'; title = 'Pass count out of 6'; }
      else if (c.kind === 'test') { label = c.label; title = c.tooltip || c.label; }
      else if (c.kind === 'window') { label = c.windowKey === 'l5d' ? 'Fired 5d' : 'Fired 20d'; title = label; cls = 'ct-window-col'; }
      else { label = '?'; title = ''; }
      h += '<th class="' + cls + '" data-sort-key="' + c.sortKey + '" title="' + title + '"><span class="hd"><span class="lbl">' + label + '</span>' + arrow + '</span></th>';
    }
    tr.innerHTML = h;
  }

  // --- tiles ---
  function pbPatternTiles(scopeRows) {
    var tiles = document.getElementById('pb-pattern-tiles');
    if (!tiles) return;
    var total = scopeRows.length;
    var h = '';
    for (var i = 0; i < PB_PATTERNS.length; i++) {
      var pat = PB_PATTERNS[i];
      var tierCounts = pbTierCounts(scopeRows, pat.key);
      var cnt = total - (tierCounts['None'] || 0);
      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;
      var sel = pbState.tierFilter[pat.key] || [];
      var anySel = sel.length > 0;
      var headline = cnt, headSub = 'of ' + total.toLocaleString('en-GB') + ' · ' + pct + '%';
      if (anySel) { var ft = 0; for (var z = 0; z < sel.length; z++) ft += (tierCounts[sel[z]] || 0); headline = ft; headSub = sel.join(' + ') + ' · filtered'; }
      var hist = pbPassHistogram(scopeRows, pat.key);
      var breakdown = '';
      for (var k = 1; k <= 6; k++) { if (k > 1) breakdown += ' · '; breakdown += k + '/6: ' + (hist[k] || 0).toLocaleString('en-GB'); }
      var chips = '';
      var TIERS = ['Possible','Plausible','Probable','Qualified'];
      for (var c = 0; c < TIERS.length; c++) {
        var tier = TIERS[c]; var on = sel.indexOf(tier) > -1; var tc = tierCounts[tier] || 0;
        chips += '<span class="pi-tier-chip pi-chip-' + PB_TONE_CHIP[pat.tone] + (on ? ' on' : '') + '" data-pattern="' + pat.key + '" data-tier="' + tier + '">' + tier + ' ' + tc.toLocaleString('en-GB') + (on ? ' ' + String.fromCharCode(10003) : '') + '</span>';
      }
      var activeCls = anySel ? ' active' : '';
      h += '<div class="rating-tile ' + PB_TONE_TILE[pat.tone] + activeCls + '" data-pattern="' + pat.key + '" title="' + pat.tooltip + '">' +
           '<div class="rt-label">' + pat.shortLabel + '</div><div class="rt-count">' + headline.toLocaleString('en-GB') + '</div><div class="rt-sub">' + headSub + '</div>' +
           '<div class="rt-breakdown">' + breakdown + '</div><div class="pi-tier-chips" data-pattern="' + pat.key + '">' + chips + '</div>' +
           '<div class="rt-strip ' + PB_TONE_STRIP[pat.tone] + '"></div></div>';
    }
    tiles.innerHTML = h;
  }

  // --- scope / filter ---
  function pbUpdateScopeCounts(rows) { function set(id, n) { var el = document.getElementById(id); if (el) el.textContent = '(' + n + ')'; } set('pb2-cnt-all', rows.length); set('pb2-cnt-live', rows.filter(function(r){return r.is_live}).length); set('pb2-cnt-sector', rows.filter(function(r){return r.sector_in_portfolio}).length); set('pb2-cnt-industry', rows.filter(function(r){return r.industry_in_portfolio}).length); }
  function pbApplyScope(all) { var rows = all.slice(); if (pbState.scope === 'live') rows = rows.filter(function(r){return r.is_live}); else if (pbState.scope === 'sector') rows = rows.filter(function(r){return r.sector_in_portfolio}); else if (pbState.scope === 'industry') rows = rows.filter(function(r){return r.industry_in_portfolio}); return rows; }
  function pbApplyTierFilter(rows) {
    var active = [];
    for (var p = 0; p < PB_PATTERNS.length; p++) { var k = PB_PATTERNS[p].key; var sel = pbState.tierFilter[k] || []; if (sel.length > 0) active.push({ key: k, tiers: sel }); }
    if (active.length === 0) return rows;
    return rows.filter(function(r) { for (var a = 0; a < active.length; a++) { var rating = pbRowRating(r, active[a].key); if (active[a].tiers.indexOf(rating) === -1) return false; } return true; });
  }

  // --- main render ---
  function pbRenderRows() {
    var tbody = document.getElementById('pb-tbody');
    if (!tbody) return;
    var all = pbGetRows();
    var scopeRows = pbApplyScope(all);
    pbUpdateScopeCounts(all);
    pbPatternTiles(scopeRows);
    var rows = pbApplyTierFilter(scopeRows);
    rows.sort(function(a,b) { var va = pbGetSortVal(a, pbState.sort.col), vb = pbGetSortVal(b, pbState.sort.col); var cmp = (typeof va === 'string') ? va.localeCompare(vb) : (va || 0) - (vb || 0); if (cmp === 0) cmp = a.ticker.localeCompare(b.ticker); return pbState.sort.dir === 'desc' ? -cmp : cmp; });
    var STAGES = ['stage_1','stage_2','stage_3','stage_4'];
    var html = '';
    for (var i = 0; i < rows.length; i++) {
      var s = rows[i];
      var styles = [], cls = [];
      if (pbState.tint === 'industry') { styles.push('--tint-bg: ' + pbHashColor(s.industry, 0.16)); cls.push('tint-row'); }
      else if (pbState.tint === 'sector') { styles.push('--tint-bg: ' + pbHashColor(s.sector, 0.16)); cls.push('tint-row'); }
      if (pbState.port === 'on') { var pinf = pbPortfolioInfo(s); if (pinf) { styles.push('--portfolio-color: ' + pinf.color); styles.push('--portfolio-bg: ' + pinf.bg); styles.push('--portfolio-bg-hover: ' + pinf.bgHover); cls.push('portfolio-band'); cls.push('portfolio-tint'); } }
      var styleAttr = styles.length ? ' style="' + styles.join(';') + '"' : '';
      var clsAttr = cls.length ? ' class="' + cls.join(' ') + '"' : '';
      var liveDot = s.is_live ? '<span class="live-dot">' + String.fromCharCode(9679) + '</span>' : '';
      html += '<tr' + clsAttr + styleAttr + '>' +
        '<td class="name-cell"><div class="co">' + liveDot + (s.company || s.ticker) + '</div><div class="tk">' + s.ticker + '</div></td>' +
        '<td class="taxon"><div class="ind">' + (s.industry || '') + '</div><div class="sec">' + (s.sector || '') + '</div></td>' +
        pbInputCell(s, 'price') + pbInputCell(s, 'high_52w') + pbInputCell(s, 'low_52w') + pbInputCell(s, 'ma_150') + pbInputCell(s, 'ma_200') + pbInputCell(s, 'recent_pullback');
      for (var si = 0; si < STAGES.length; si++) html += pbStageInfoCell(s, STAGES[si], si === 0 ? 'grp-start-stageinfo' : '');
      for (var pi = 0; pi < PB_PATTERNS.length; pi++) {
        var pat = PB_PATTERNS[pi];
        var gi = pi + 1;
        html += pbRatingCell(s, pat.key, 'grp-start-g' + gi);
        html += pbScoreCell(s, pat.key, '');
        for (var ti = 0; ti < pat.tests.length; ti++) html += pbTestCell(s, pat.key, pat.tests[ti].key, '');
        html += pbWindowCell(s, pat.key, 'l5d', 'ct-window-col');
        html += pbWindowCell(s, pat.key, 'l20d', 'ct-window-col');
      }
      html += '</tr>';
    }
    tbody.innerHTML = html;
  }

  // --- control setters ---
  window.pb2SetMode = function(kind, val) { pbState.mode[kind] = val; var btns = document.querySelectorAll('button[data-pb2-grp="' + kind + '"]'); for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-pb2-val') === val); pbRenderRows(); };
  window.pb2SetScope = function(s) { pbState.scope = s; var btns = document.querySelectorAll('button[data-pb2-scope]'); for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-pb2-scope') === s); pbRenderRows(); };
  window.pb2SetTint = function(t) { pbState.tint = t; var btns = document.querySelectorAll('button[data-pb2-tint]'); for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-pb2-tint') === t); pbRenderRows(); };
  window.pb2SetPort = function(p) { pbState.port = p; var btns = document.querySelectorAll('button[data-pb2-port]'); for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-pb2-port') === p); pbRenderRows(); };
  window.pb2ToggleTier = function(patternKey, tier) { var sel = pbState.tierFilter[patternKey] || []; var idx = sel.indexOf(tier); if (idx > -1) sel.splice(idx, 1); else sel.push(tier); pbState.tierFilter[patternKey] = sel; pbRenderRows(); };
  window.pb2SelectAllTiers = function(patternKey) { var sel = pbState.tierFilter[patternKey] || []; var onlyProb = (sel.length === 1 && sel[0] === 'Probable'); pbState.tierFilter[patternKey] = onlyProb ? [] : ['Probable']; pbRenderRows(); };
  window.pb2OnSort = pbOnSort;

  // --- scaffold ---
  function pbPatternBlockSpan(pat) { return 2 + pat.tests.length + 2; }
  function pbBuildScaffold() {
    var host = document.getElementById('tab-tests_probing_bet');
    if (!host) return false;
    if (host.querySelector('#pb-main-table')) return true;
    var cg = '<col class="c-name"><col class="c-taxon"><col class="c-price"><col class="c-52wh"><col class="c-52wl"><col class="c-ma150"><col class="c-ma200"><col class="c-pullback">';
    for (var sgc = 0; sgc < PB_STAGEINFO_COUNT; sgc++) cg += '<col class="c-stageinfo">';
    var groupHtml = '<th class="gh-inputs" colspan="' + PB_INPUT_COUNT + '">Inputs</th><th class="gh-stageinfo grp-start-stageinfo" colspan="' + PB_STAGEINFO_COUNT + '">Stage ratings</th>';
    var subGroupHtml = '<th class="sg-spacer" colspan="' + PB_INPUT_COUNT + '"></th><th class="sg-spacer" colspan="' + PB_STAGEINFO_COUNT + '"></th>';
    for (var p = 0; p < PB_PATTERNS.length; p++) {
      var pat = PB_PATTERNS[p]; var gi = p + 1; var span = pbPatternBlockSpan(pat);
      cg += '<col class="c-rating"><col class="c-score">'; for (var t = 0; t < pat.tests.length; t++) cg += '<col class="c-test">'; cg += '<col class="c-window"><col class="c-window">';
      groupHtml += '<th class="gh-g' + gi + ' grp-start-g' + gi + '" colspan="' + span + '">' + pat.shortLabel + '</th>';
      var setupCount = 0, triggerCount = 0; for (var st = 0; st < pat.tests.length; st++) { if (pat.tests[st].group === 'trigger') triggerCount++; else setupCount++; }
      subGroupHtml += '<th class="sub-g sub-g-rating sub-g' + gi + '" colspan="2">Rating</th>';
      if (setupCount > 0) subGroupHtml += '<th class="sub-g sub-g-setup sub-g' + gi + '" colspan="' + setupCount + '">Setup</th>';
      if (triggerCount > 0) subGroupHtml += '<th class="sub-g sub-g-trigger sub-g' + gi + '" colspan="' + triggerCount + '">Trigger</th>';
      subGroupHtml += '<th class="sub-g sub-g-context sub-g' + gi + '" colspan="2">Context</th>';
    }
    var captionsHtml = '';
    for (var cp = 0; cp < PB_PATTERNS.length; cp++) { var cpat = PB_PATTERNS[cp]; captionsHtml += '<div class="gcap gcap-g' + (cp+1) + '"><b>' + cpat.shortLabel + '</b>' + cpat.caption + '</div>'; }
    var theadRows = '<tr class="group-header-row">' + groupHtml + '</tr><tr class="sub-group-row">' + subGroupHtml + '</tr><tr class="col-header-row" id="pb-col-header-row"></tr>';
    var html = '<div class="s1-intro">Probing Bets — Stage 1 and Stage 2 breakout tests. A probing bet is a small starter position on a stock that breaks out positively without first completing a full basing or pullback pattern. In Stage 1 (troughing), this probes whether the trend is turning. In Stage 2 (uptrend), this catches idiosyncratic or event-driven breakouts. Both use the same 6-criterion template: stage gate + 5D/10D MAs rising + price above 20D + 20D MA turned up in last 5 days + confirmation close. The 5-day turn window ensures only fresh breakouts appear.</div>' +
      '<div class="controls s1-controls">' +
        '<div class="ctrl-grp"><span class="ctrl-label">Inputs</span><button class="toggle-btn active" data-pb2-grp="inputs" data-pb2-val="pct" onclick="pb2SetMode(\'inputs\',\'pct\')">show as %</button><button class="toggle-btn" data-pb2-grp="inputs" data-pb2-val="raw" onclick="pb2SetMode(\'inputs\',\'raw\')">show as numbers</button></div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Tests</span><button class="toggle-btn active" data-pb2-grp="tests" data-pb2-val="tick" onclick="pb2SetMode(\'tests\',\'tick\')">show ticks</button><button class="toggle-btn" data-pb2-grp="tests" data-pb2-val="val" onclick="pb2SetMode(\'tests\',\'val\')">show test values</button></div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Scope</span><button class="toggle-btn active" data-pb2-scope="all" onclick="pb2SetScope(\'all\')">All <span id="pb2-cnt-all"></span></button><button class="toggle-btn" data-pb2-scope="live" onclick="pb2SetScope(\'live\')">Live <span id="pb2-cnt-live"></span></button><button class="toggle-btn" data-pb2-scope="sector" onclick="pb2SetScope(\'sector\')">Sectors <span id="pb2-cnt-sector"></span></button><button class="toggle-btn" data-pb2-scope="industry" onclick="pb2SetScope(\'industry\')">Industries <span id="pb2-cnt-industry"></span></button></div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Colour by</span><button class="toggle-btn active" data-pb2-tint="none" onclick="pb2SetTint(\'none\')">Off</button><button class="toggle-btn" data-pb2-tint="industry" onclick="pb2SetTint(\'industry\')">Industry</button><button class="toggle-btn" data-pb2-tint="sector" onclick="pb2SetTint(\'sector\')">Sector</button></div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Portfolio tint</span><button class="toggle-btn active" data-pb2-port="off" onclick="pb2SetPort(\'off\')">Off</button><button class="toggle-btn" data-pb2-port="on" onclick="pb2SetPort(\'on\')">On</button></div>' +
      '</div>' +
      '<div class="rating-tiles s1-rating-tiles" id="pb-pattern-tiles"></div>' +
      '<div class="group-captions">' + captionsHtml + '</div>' +
      '<div class="table-wrap"><div class="v2-hscroll"><table class="data-table" id="pb-main-table"><colgroup>' + cg + '</colgroup><thead>' + theadRows + '</thead><tbody id="pb-tbody"></tbody></table></div></div>';
    host.innerHTML = html;
    var tilesEl = document.getElementById('pb-pattern-tiles');
    if (tilesEl) { tilesEl.addEventListener('click', function(e) { var chip = e.target.closest('.pi-tier-chip'); if (chip) { var cp = chip.getAttribute('data-pattern'); var ct = chip.getAttribute('data-tier'); if (cp && ct) pb2ToggleTier(cp, ct); return; } var tile = e.target.closest('.rating-tile'); if (!tile) return; var k = tile.getAttribute('data-pattern'); if (k) pb2SelectAllTiers(k); }); }
    var hdr = document.getElementById('pb-col-header-row');
    if (hdr) { hdr.addEventListener('click', function(e) { var th = e.target.closest('th'); if (!th) return; var key = th.getAttribute('data-sort-key'); if (key) pb2OnSort(key); }); }
    return true;
  }

  function renderProbingBet() {
    if (!pbBuildScaffold()) return;
    pbBuildHeaderRow();
    pbRenderRows();
    if (window.measureV2Ribbon) measureV2Ribbon();
  }
  window.renderProbingBet = renderProbingBet;

})();

/* MD-V2-S47-TAB-PROBING-BET-MARKER-MODULE-END */

"""


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
    return subprocess.run(["git", "show", f"HEAD:{rel_posix}"], cwd=repo, check=True, capture_output=True).stdout.decode("utf-8")

def _wt_text(repo: str, rel: str) -> str:
    with open(os.path.join(repo, rel), "r", encoding="utf-8") as fh:
        return fh.read()

def _md5_text(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()

def _apply_css_selector_extensions(src: str) -> str:
    lines = src.split('\n')
    new_lines = []
    for line in lines:
        if 'data-active-tab="tests"' in line and 'data-active-tab="tests_probing_bet"' not in line:
            if 'var ' in line or line.strip().startswith('//') or line.strip().startswith('/*') or MARKER in line:
                new_lines.append(line)
                continue
            line = re.sub(
                r'body\[data-active-tab="tests"\](\s*[^,{\n]*?)([,{])',
                r'body[data-active-tab="tests"]\1\2\nbody[data-active-tab="tests_probing_bet"]\1\2',
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

    # This patcher requires Patcher 1 to have been applied first.
    # In dry-run mode, we simulate by applying Patcher 1's changes first.
    # In write mode, we require the WT to have Patcher 1's marker.
    if not test_mode:
        if PREREQ_MARKER not in wt_src:
            print(f"[ABORT] Prerequisite patcher not applied. Marker '{PREREQ_MARKER}' not found in working tree.")
            print(f"        Apply patch_md_v2_tab_healthy_retest_s47_2026_05_18.py first.")
            return 2
        if _md5_text(wt_src) != _md5_text(head_src) and MARKER not in wt_src:
            # WT diverges from HEAD and this patcher hasn't been applied yet - that's expected (Patcher 1 applied)
            src = wt_src
        else:
            src = wt_src
    else:
        # Dry-run: we need Patcher 1 to have been applied to the source we work on.
        # Check if WT has the prereq marker (Patcher 1 applied but not committed).
        if PREREQ_MARKER in wt_src:
            src = wt_src
            print(f"[*] Prerequisite marker found in WT (Patcher 1 applied, not committed). Using WT source.")
        elif PREREQ_MARKER in head_src:
            src = head_src
            print(f"[*] Prerequisite marker found in HEAD. Using HEAD source.")
        else:
            print(f"[ABORT] Prerequisite patcher not applied. Marker '{PREREQ_MARKER}' not found.")
            print(f"        Apply patch_md_v2_tab_healthy_retest_s47_2026_05_18.py first.")
            return 2

    if MARKER in src:
        print(f"[OK] MARKER already present -- this patch has already shipped.")
        return 0

    # --- Apply anchored replacements ---
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
            print(f"[ABORT] Anchor count != 1 for '{label}'.")
            return 3
        src = src.replace(anchor, replacement, 1)

    # --- Insert CSS + module ---
    n7 = src.count(ANCHOR_7)
    print(f"[*] CSS+module insertion: anchor matches = {n7} (expected 1)")
    if n7 != 1:
        print(f"[ABORT] Anchor count != 1 for CSS+module insertion.")
        return 3
    src = src.replace(ANCHOR_7, PB_CSS + "\n" + PB_MODULE + "\n" + ANCHOR_7, 1)

    # --- CSS selector extensions ---
    print("[*] Extending CSS selectors for V2 chrome...")
    src = _apply_css_selector_extensions(src)

    assert MARKER in src, "[INTERNAL] MARKER missing after all replacements"
    new_src = src
    print(f"[*] Char delta:     {len(new_src) - len(head_src):+d}")
    print(f"[*] New md5(text):  {_md5_text(new_src)}")

    if ENABLE_PY_COMPILE:
        try:
            ast.parse(new_src)
        except SyntaxError as e:
            print(f"[ABORT] ast.parse failed: {e}")
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

    diff_lines = list(difflib.unified_diff(head_src.splitlines(keepends=True), new_src.splitlines(keepends=True), fromfile=f"HEAD:{rel}", tofile=f"PATCHED:{rel}", n=2))
    added = sum(1 for l in diff_lines if l.startswith('+') and not l.startswith('+++'))
    removed = sum(1 for l in diff_lines if l.startswith('-') and not l.startswith('---'))
    print(f"\n[*] Diff: {len(diff_lines)} lines total, +{added} added, -{removed} removed")
    for line in diff_lines[:60]:
        sys.stdout.write(line)
    if len(diff_lines) > 80:
        print(f"\n... ({len(diff_lines) - 80} lines omitted) ...\n")
        for line in diff_lines[-20:]:
            sys.stdout.write(line)
    print("--- END DIFF ---\n")

    if test_mode:
        print(f"[OK] DRY-RUN: all gates passed. +{added} lines, -{removed} removed. Re-run without --test to write.")
        return 0

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
        print(f"[ABORT] Post-write md5 mismatch! Restore: {os.path.relpath(bak, repo)}")
        return 6
    if MARKER not in after:
        print("[ABORT] Post-write MARKER missing.")
        return 7
    print(f"[OK] WRITE complete. {len(after)} chars, {os.path.getsize(abs_target)} bytes on disk. MARKER present.")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
