#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# patch_md_v2_overview_transpose_cooccurrence_s35_2026_05_15.py
# =============================================================================
# MD V2 Master Dashboard - Session 35 (15-May-26)
# Requests 2 + 3 (Richard's brief) on the Master Overview ("Overview") tab:
#
#   Request 2 - transpose the top summary table so the four rating tiers (plus
#   a Total rated row) run DOWN as rows and the 20 screens run ACROSS as
#   columns, in the same order and at the same column widths (190px + 20x64px)
#   as the matrix below, so the two tables line up under the shared page-body
#   horizontal scroll.
#
#   Request 3 - make the summary table a co-occurrence selector: clicking a
#   count cell selects that screen-and-tier as a criterion (multiple cells
#   selectable); every cell then shows the count of stocks meeting ALL selected
#   criteria AND its own; the matrix below filters to that set. Tiers within
#   one screen combine as OR, screens combine as AND. The Wave 3 per-column
#   filter chips are removed - the summary table is now the single shared
#   filter for both tables. The cell click is the selector, so "jump to that
#   screen's tab" moves onto a click of the screen-name column header (in both
#   the summary table and the matrix). A "Clear all" control resets selection.
#
# This patcher replaces the whole Master Overview JS module (between
# MD-V2-MASTER-OVERVIEW-MARKER-START and -END) and the whole #mo-main-table CSS
# block (between MD-V2-MASTER-OVERVIEW-MARKER-CSS-START and -END), and adjusts
# two matrix sticky-header `top:` offsets to absorb the removed chip row. The
# inert `.mo-mx-chip*` CSS rules are deliberately LEFT in place as dead rules:
# they match no elements once the chip row stops being rendered, and removing
# them was judged not worth the multi-line anchor risk in the fragile matrix
# CSS region (S29 Wave 3b/3c lesson). They can go in a later cosmetic pass.
#
# Independent of the Request 1 patcher (post-test indicator ratingPath fix):
# this module rewrite already carries the corrected MO_ROWS ratingPaths
# ('group:post_indicators:'), so the two patchers may be run in either order.
#
# Discipline (S33 / Request-1 patcher house style):
#  - Reads SOURCE from `git show HEAD:scripts/build_dashboard.py` (git object
#    store, immune to the COWORK FUSE stale-cache bug).
#  - Idempotent: exits 0 if MARKER already present in the working tree.
#  - Safety gate: aborts if the working-tree build_dashboard.py differs from
#    HEAD and the marker is absent (run Windows-side, where wt == HEAD).
#  - Every splice asserts its anchors are present and unique; py_compile
#    validates the result before it is written; pre-write backup taken.
#
# Usage:
#   python scripts/patch_md_v2_overview_transpose_cooccurrence_s35_2026_05_15.py
#   python scripts/patch_md_v2_overview_transpose_cooccurrence_s35_2026_05_15.py --test SRC OUT
# =============================================================================
import sys, os, subprocess, hashlib, py_compile, datetime

MARKER  = "MD-V2-OVERVIEW-COOCCURRENCE-S35-MARKER"
TARGET  = os.path.join("scripts", "build_dashboard.py")

CSS_START = "/* MD-V2-MASTER-OVERVIEW-MARKER-CSS-START */"
CSS_END   = "/* MD-V2-MASTER-OVERVIEW-MARKER-CSS-END */"
JS_START  = "/* MD-V2-MASTER-OVERVIEW-MARKER-START */"
JS_END    = "/* MD-V2-MASTER-OVERVIEW-MARKER-END */"

# matrix sticky-header offsets: the chip row is gone, so the section-group row
# moves up to the base offset and the column-title row sits one group-row
# height (22px - the original author's measured value) below it.
OFF_OLD_GROUP = "top: calc(var(--header-height) + var(--v2-ribbon-h) + 56px);"
OFF_NEW_GROUP = "top: calc(var(--header-height) + var(--v2-ribbon-h));"
OFF_OLD_COL   = "top: calc(var(--header-height) + var(--v2-ribbon-h) + 78px);"
OFF_NEW_COL   = "top: calc(var(--header-height) + var(--v2-ribbon-h) + 22px);"


# ----------------------------------------------------------------------------
# NEW CSS - the transposed #mo-main-table. Column widths mirror the matrix
# exactly (190px first column, 64px screen columns) via the same
# width/min/max-width mechanism the matrix uses, so the two tables line up.
# ----------------------------------------------------------------------------
NEW_CSS = r"""
/* MD-V2-OVERVIEW-COOCCURRENCE-S35-MARKER: Master Overview summary table -
   transposed (the four rating tiers + a Total rated row run DOWN, the 20
   screens run ACROSS) and sized to the matrix's exact column widths
   (190px + 20x64px) so the two tables line up under the shared page-body
   horizontal scroll. The summary table is now a co-occurrence selector:
   clicking a count cell selects that screen-and-tier criterion; every cell
   then shows the count of stocks meeting all selected criteria AND its own;
   the matrix below filters to that set. Replaces the Wave 3 per-column chip
   filter (chips removed; the chip CSS above is now inert/dead). */
#mo-main-table { border-collapse: separate; border-spacing: 0; font-size: 12px; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }
#mo-main-table thead { position: static; }
#mo-main-table thead th { background: #f3efe2; border-bottom: 1px solid #e0dcc8; }
/* section-group band - reuses the matrix mo-mx-g-* colour hooks */
#mo-main-table thead tr.mo-group-row th { font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; padding: 5px 6px; text-align: center; border-left: 1px solid #e0dcc8; }
#mo-main-table thead tr.mo-group-row th.mo-mx-g-stages   { color: #1b5e20; }
#mo-main-table thead tr.mo-group-row th.mo-mx-g-pretest  { color: #0F6E56; }
#mo-main-table thead tr.mo-group-row th.mo-mx-g-posttest { color: #A32D2D; }
#mo-main-table thead tr.mo-group-row th.mo-mx-g-setups   { color: #BA7517; }
#mo-main-table thead tr.mo-group-row th.mo-mx-g-tests    { color: #185FA5; }
/* column-title row - one cell per screen, labels WRAP, click to open the tab */
#mo-main-table thead tr.mo-col-row th { width: 64px; min-width: 64px; max-width: 64px; font-size: 9.5px; font-weight: 700; color: #555; padding: 5px 4px; text-align: center; vertical-align: bottom; line-height: 1.2; white-space: normal; word-break: normal; overflow-wrap: break-word; cursor: pointer; }
#mo-main-table thead tr.mo-col-row th:hover { color: #0F6E56; text-decoration: underline; }
/* sticky-left first column - aligns with the matrix 190px Stock column */
#mo-main-table thead th.mo-corner { position: sticky; left: 0; z-index: 6; width: 190px; min-width: 190px; max-width: 190px; text-align: left; vertical-align: bottom; padding: 5px 10px; border-right: 1px solid #e0dcc8; font-size: 9px; color: #9a9582; text-transform: uppercase; letter-spacing: 0.4px; }
#mo-main-table tbody td { padding: 7px 6px; border-bottom: 1px solid #efece0; text-align: center; vertical-align: middle; font-variant-numeric: tabular-nums; }
#mo-main-table tbody td.mo-tier-label { position: sticky; left: 0; z-index: 5; background: #fbfaf5; text-align: left; font-weight: 600; color: #2a2a2a; padding: 7px 10px; border-right: 1px solid #e0dcc8; }
#mo-main-table tbody tr:hover td.mo-tier-label { background: #f4f1e6; }
#mo-main-table tbody tr.mo-data-row:hover { background: rgba(15,110,86,0.05); }
#mo-main-table td.mo-cell { cursor: pointer; font-weight: 600; transition: filter 0.12s; }
#mo-main-table td.mo-cell:hover { filter: brightness(0.94); outline: 1.5px solid rgba(15,110,86,0.4); outline-offset: -1.5px; }
#mo-main-table td.mo-cell.mo-zero { color: #c4c0b0; font-weight: 400; }
#mo-main-table td.mo-t-none.mo-has  { background: #f0ede1; color: #999; }
#mo-main-table td.mo-t-pos.mo-has   { background: rgba(15,110,86,0.10); color: #3a6a5a; }
#mo-main-table td.mo-t-pla.mo-has   { background: rgba(15,110,86,0.20); color: #1a5446; }
#mo-main-table td.mo-t-prob.mo-has  { background: rgba(15,110,86,0.34); color: #0a3a2e; }
/* a selected co-occurrence cell */
#mo-main-table td.mo-cell.mo-cell-sel { outline: 2.5px solid #BA7517; outline-offset: -2.5px; box-shadow: inset 0 0 0 2px rgba(186,117,23,0.20); font-weight: 700; color: #6e4310; }
#mo-main-table td.mo-cell.mo-cell-sel:hover { filter: none; outline: 2.5px solid #BA7517; }
/* Total rated row */
#mo-main-table tr.mo-total-row td { border-top: 2px solid #e0dcc8; }
#mo-main-table tr.mo-total-row td.mo-total-cell { color: #777; font-weight: 700; background: #faf8f0; }
#mo-main-table tr.mo-total-row td.mo-tier-label { color: #777; }
/* the Clear-all button shows armed when a selection is active */
#mo-clear-btn.active { background: #BA7517; border-color: #BA7517; color: #fff; }
"""


# ----------------------------------------------------------------------------
# NEW JS module - clean rewrite (S33 module-rewrite pattern). Shared helpers
# (moPricesLookup / moLiveTickers / moNormaliseTier / moReadRating / moGetRows /
# moApplyScope) are unchanged; MO_ROWS carries the corrected post-test
# ratingPaths; the chip filter is replaced by the moSel co-occurrence selection.
# ----------------------------------------------------------------------------
NEW_JS = r"""
(function() {
  'use strict';

  // MD-V2-OVERVIEW-COOCCURRENCE-S35-MARKER: Master Overview ("Overview") tab.
  // Two stacked, column-aligned tables:
  //  - the summary table (transposed): the four rating tiers + a Total rated
  //    row run down; the 20 screens run across. It is a co-occurrence selector
  //    - click a count cell to select that screen-and-tier as a criterion;
  //    every cell then shows the count of stocks meeting ALL selected criteria
  //    AND its own; tiers within one screen OR, screens AND. Click a screen
  //    name to open that screen's own tab. "Clear all" resets the selection.
  //  - the full rating matrix: every md_v2 stock down the Y-axis, the 20
  //    screens across, a rating pill per cell. It filters to the stocks that
  //    match the summary table's selection.
  // The Wave 3 per-column filter chips are removed - the summary table is the
  // single shared filter for both tables.

  var moState = { scope: 'all' };

  // Row model: { section, key, label, ratingPath, tabId, patternKey }
  //   ratingPath - how to read this screen's rating from a stock's md_v2:
  //     'stage:<k>'     -> md_v2[k].rating
  //     'group:<g>:<k>' -> md_v2[<g>][<k>].rating
  //       (pre_indicators / post_indicators / setups / tests)
  //   tabId - the tab a screen-name click opens.
  var MO_ROWS = [
    // -- Stages --
    { section:'Stages', key:'stage_1', label:'Stage 1 - Basing', ratingPath:'stage:stage_1', tabId:'stage_1', patternKey:null },
    { section:'Stages', key:'stage_2', label:'Stage 2 - Uptrend', ratingPath:'stage:stage_2', tabId:'stage_2', patternKey:null },
    { section:'Stages', key:'stage_3', label:'Stage 3 - Topping', ratingPath:'stage:stage_3', tabId:'stage_3', patternKey:null },
    { section:'Stages', key:'stage_4', label:'Stage 4 - Decline', ratingPath:'stage:stage_4', tabId:'stage_4', patternKey:null },
    // -- Pre-test indicators --
    { section:'Pre-test indicators', key:'pulling_back_uptrend', label:'Pulling back within MT/LT uptrend', ratingPath:'group:pre_indicators:pulling_back_uptrend', tabId:'pre_indicators', patternKey:'pulling_back_uptrend' },
    { section:'Pre-test indicators', key:'basing', label:'Basing', ratingPath:'group:pre_indicators:basing', tabId:'pre_indicators', patternKey:'basing' },
    { section:'Pre-test indicators', key:'collapsing', label:'Collapsing', ratingPath:'group:pre_indicators:collapsing', tabId:'pre_indicators', patternKey:'collapsing' },
    // -- Post-test indicators (ratingPath -> md_v2.post_indicators.<k>.rating;
    //    md_v2.indicators.<k> is a bare boolean and has no .rating - Request 1) --
    { section:'Post-test indicators', key:'breakout', label:'Breakout', ratingPath:'group:post_indicators:breakout', tabId:'post_indicators', patternKey:'breakout' },
    { section:'Post-test indicators', key:'advancing', label:'Advancing', ratingPath:'group:post_indicators:advancing', tabId:'post_indicators', patternKey:'advancing' },
    { section:'Post-test indicators', key:'breakdown_50D', label:'Breakdown 50D', ratingPath:'group:post_indicators:breakdown_50D', tabId:'post_indicators', patternKey:'breakdown_50D' },
    { section:'Post-test indicators', key:'breakdown_150D', label:'Breakdown 150D', ratingPath:'group:post_indicators:breakdown_150D', tabId:'post_indicators', patternKey:'breakdown_150D' },
    { section:'Post-test indicators', key:'breakdown_200D', label:'Breakdown 200D', ratingPath:'group:post_indicators:breakdown_200D', tabId:'post_indicators', patternKey:'breakdown_200D' },
    // -- Capital qualification setups --
    { section:'Capital qualification setups', key:'probing_bet', label:'Probing bet', ratingPath:'group:setups:probing_bet', tabId:'setups_s1pb', patternKey:'probing_bet' },
    { section:'Capital qualification setups', key:'vcp_after_s1_plateau', label:'VCP after Stage 1->2 plateau', ratingPath:'group:setups:vcp_after_s1_plateau', tabId:'setups_s1pb', patternKey:'vcp_after_s1_plateau' },
    { section:'Capital qualification setups', key:'healthy_retest', label:'Healthy retest within MT/LT uptrend', ratingPath:'group:setups:healthy_retest', tabId:'setups_s2vcp', patternKey:'healthy_retest' },
    { section:'Capital qualification setups', key:'vcp_after_s2_base', label:'VCP after Stage 2 base', ratingPath:'group:setups:vcp_after_s2_base', tabId:'setups_s2vcp', patternKey:'vcp_after_s2_base' },
    // -- Capital deployment tests --
    { section:'Capital deployment tests', key:'ma_retest_upwards', label:'Upwards moving average retest', ratingPath:'group:tests:ma_retest_upwards', tabId:'tests', patternKey:'ma_retest_upwards' },
    { section:'Capital deployment tests', key:'vcp_deploy_s1', label:'VCP after Stage 1->2', ratingPath:'group:tests:vcp_deploy_s1', tabId:'tests', patternKey:'vcp_deploy_s1' },
    { section:'Capital deployment tests', key:'vcp_deploy_s2', label:'VCP after Stage 2 base', ratingPath:'group:tests:vcp_deploy_s2', tabId:'tests', patternKey:'vcp_deploy_s2' },
    { section:'Capital deployment tests', key:'probing_bet_test', label:'Probing bet', ratingPath:'group:tests:probing_bet', tabId:'tests', patternKey:'probing_bet' }
  ];

  // The 4 rating tiers (Stage 1 splits Probable into Early/Late upstream; the
  // normaliser folds both into Probable).
  var MO_TIERS = ['None', 'Possible', 'Plausible', 'Probable'];
  var MO_TIER_CLS = { 'None':'mo-t-none', 'Possible':'mo-t-pos', 'Plausible':'mo-t-pla', 'Probable':'mo-t-prob' };

  // section -> group-band colour-hook class (shared by both tables)
  var MO_GROUP_CLS = {
    'Stages': 'mo-mx-g-stages',
    'Pre-test indicators': 'mo-mx-g-pretest',
    'Post-test indicators': 'mo-mx-g-posttest',
    'Capital qualification setups': 'mo-mx-g-setups',
    'Capital deployment tests': 'mo-mx-g-tests'
  };
  // short section labels for the group band - the full names are long.
  var MO_GROUP_LABEL = {
    'Stages': 'Stages',
    'Pre-test indicators': 'Pre-test',
    'Post-test indicators': 'Post-test',
    'Capital qualification setups': 'Qualification setups',
    'Capital deployment tests': 'Deployment tests'
  };
  var MO_MX_TIER_PILL = {
    'None': 'mo-mx-p-none', 'Possible': 'mo-mx-p-pos',
    'Plausible': 'mo-mx-p-pla', 'Probable': 'mo-mx-p-prob'
  };

  // ----- shared helpers (unchanged from S27 / Wave 3) -----
  function moPricesLookup() {
    if (window._moPricesByTicker) return window._moPricesByTicker;
    var out = {};
    var arr = (window.MASTER_DATA && MASTER_DATA.prices) || [];
    for (var i = 0; i < arr.length; i++) if (arr[i] && arr[i].ticker) out[arr[i].ticker] = arr[i];
    window._moPricesByTicker = out;
    return out;
  }
  function moLiveTickers() {
    var out = {};
    var inv = (window.MASTER_DATA && MASTER_DATA.positions && MASTER_DATA.positions.investments) || [];
    for (var i = 0; i < inv.length; i++) if (inv[i].ticker) out[inv[i].ticker] = true;
    return out;
  }
  function moNormaliseTier(raw) {
    if (!raw) return 'None';
    if (raw.indexOf('Probable') === 0) return 'Probable';
    if (raw.indexOf('Plausible') === 0) return 'Plausible';
    if (raw.indexOf('Possible') === 0) return 'Possible';
    return 'None';
  }
  function moReadRating(md, ratingPath) {
    if (!md) return 'None';
    var parts = ratingPath.split(':');
    if (parts[0] === 'stage') {
      var st = md[parts[1]];
      return (st && st.rating) || 'None';
    }
    if (parts[0] === 'group') {
      var grp = md[parts[1]];
      var rec = grp && grp[parts[2]];
      return (rec && rec.rating) || 'None';
    }
    return 'None';
  }
  function moGetRows() {
    var raw = (window.MASTER_DATA && MASTER_DATA.filters) || [];
    var prices = moPricesLookup();
    var live = moLiveTickers();
    var rows = [];
    for (var i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || !s.md_v2) continue;
      var p = prices[s.ticker] || {};
      rows.push({ ticker: s.ticker, company: p.company_name || s.ticker, md_v2: s.md_v2, is_live: !!live[s.ticker] });
    }
    return rows;
  }
  function moApplyScope(all) {
    if (moState.scope === 'live') return all.filter(function(r){ return r.is_live; });
    return all;
  }
  function moMxAttr(s) {
    return String(s).replace(/&/g, '&amp;').replace(/'/g, '&#39;').replace(/"/g, '&quot;');
  }
  function moMxText(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  // ----- co-occurrence selection state (replaces the Wave 3 chip filter) -----
  // moSel[rowKey] = { tier: true, ... } - only present tier keys are active; a
  // screen with no entry is unconstrained.
  var moSel = {};

  function moSelActive() {
    for (var k in moSel) {
      if (!moSel.hasOwnProperty(k)) continue;
      var f = moSel[k];
      for (var t in f) { if (f.hasOwnProperty(t) && f[t]) return true; }
    }
    return false;
  }
  // A stock passes if, for every screen with >=1 selected tier, the stock's
  // normalised tier for that screen is one of the selected tiers (OR within a
  // screen). Screens with no selection pass freely (AND across screens).
  function moSelRowPasses(md) {
    for (var r = 0; r < MO_ROWS.length; r++) {
      var row = MO_ROWS[r];
      var f = moSel[row.key];
      if (!f) continue;
      var keys = [];
      for (var kk in f) { if (f.hasOwnProperty(kk) && f[kk]) keys.push(kk); }
      if (keys.length === 0) continue;
      var tier = moNormaliseTier(moReadRating(md, row.ratingPath));
      var hit = false;
      for (var j = 0; j < keys.length; j++) { if (keys[j] === tier) { hit = true; break; } }
      if (!hit) return false;
    }
    return true;
  }
  function moSelIsOn(rowKey, tier) {
    var f = moSel[rowKey];
    return !!(f && f[tier]);
  }
  // Toggle one screen x tier cell in the selection, then re-render both tables.
  function moCellClick(rowKey, tier) {
    var f = moSel[rowKey];
    if (!f) { f = {}; moSel[rowKey] = f; }
    if (f[tier]) {
      delete f[tier];
      var anyLeft = false;
      for (var t in f) { if (f.hasOwnProperty(t) && f[t]) anyLeft = true; }
      if (!anyLeft) delete moSel[rowKey];
    } else {
      f[tier] = true;
    }
    moRenderTable();
    moRenderMatrix();
  }
  window.moCellClick = moCellClick;

  function moClearSel() {
    moSel = {};
    moRenderTable();
    moRenderMatrix();
  }
  window.moClearSel = moClearSel;

  // Screen-name click: open that screen's own tab (the relocated jump - the
  // cell click is now the co-occurrence selector). _mdJump carries the tab
  // only; there is no tier context from a label click.
  function moJumpToTab(rowKey) {
    var row = null;
    for (var i = 0; i < MO_ROWS.length; i++) if (MO_ROWS[i].key === rowKey) row = MO_ROWS[i];
    if (!row) return;
    window._mdJump = { tab: row.tabId };
    if (typeof window.switchTab === 'function') window.switchTab(row.tabId);
  }
  window.moJumpToTab = moJumpToTab;

  function moSetScope(s) {
    moState.scope = s;
    var btns = document.querySelectorAll('button[data-mo-scope]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-mo-scope') === s);
    moRenderTable();
  }
  window.moSetScope = moSetScope;

  // ----- transposed summary table -----
  function moRenderTable() {
    var host = document.getElementById('tab-master_overview');
    if (!host) return;
    if (!host.querySelector('#mo-main-table')) {
      var intro = '<div class="s1-intro">Master Overview is the synoptic view of the whole MD V2 system. The summary table below is the control surface: every rating tier as a row, every screen - the four stages, the pre-test and post-test indicators, the capital qualification setups and the capital deployment tests - as a column, lined up with the full matrix beneath it. Click any count cell to select that screen-and-tier as a criterion; every cell then shows how many stocks meet all the criteria you have selected AND its own (the &quot;patterns&quot; you are looking for), and the matrix below filters to that set. Click multiple cells to build a pattern - tiers within one screen combine as OR, screens combine as AND. Click a screen name to open that screen&apos;s own tab. Use &quot;Clear all&quot; to reset.</div>';
      var controls = '<div class="controls s1-controls">' +
        '<div class="ctrl-grp"><span class="ctrl-label">Scope</span>' +
          '<button class="toggle-btn active" data-mo-scope="all" onclick="moSetScope(\'all\')">All</button>' +
          '<button class="toggle-btn" data-mo-scope="live" onclick="moSetScope(\'live\')">Live investments</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Pattern selection</span>' +
          '<button class="toggle-btn" id="mo-clear-btn" onclick="moClearSel()">Clear all</button>' +
        '</div></div>';
      // transposed thead: section-group band + column-title row.
      var groupTr = '<tr class="mo-group-row"><th class="mo-corner" rowspan="2">Rated tier</th>';
      var gi = 0;
      while (gi < MO_ROWS.length) {
        var sec = MO_ROWS[gi].section;
        var span = 0;
        while (gi + span < MO_ROWS.length && MO_ROWS[gi + span].section === sec) span++;
        groupTr += '<th colspan="' + span + '" class="' + (MO_GROUP_CLS[sec] || '') + '">' +
          moMxText(MO_GROUP_LABEL[sec] || sec) + '</th>';
        gi += span;
      }
      groupTr += '</tr>';
      var colTr = '<tr class="mo-col-row">';
      for (var t = 0; t < MO_ROWS.length; t++) {
        colTr += '<th title="' + moMxAttr(MO_ROWS[t].label + ' - open this screen\'s tab') + '" ' +
          'onclick="moJumpToTab(\'' + moMxAttr(MO_ROWS[t].key) + '\')">' +
          moMxText(MO_ROWS[t].label) + '</th>';
      }
      colTr += '</tr>';
      var table = '<div class="table-wrap"><div class="v2-hscroll"><table class="data-table" id="mo-main-table">' +  /* MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER */
        '<thead>' + groupTr + colTr + '</thead><tbody id="mo-tbody"></tbody></table></div></div>';  /* MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER */
      host.innerHTML = intro + controls + table;
    }

    var rows = moApplyScope(moGetRows());
    // tally co-occurrence counts: only stocks passing the selection filter are
    // counted, so each cell shows stocks meeting ALL selected criteria AND its
    // own. With nothing selected every stock passes -> plain counts.
    var counts = {};
    for (var r0 = 0; r0 < MO_ROWS.length; r0++) {
      counts[MO_ROWS[r0].key] = { 'None':0, 'Possible':0, 'Plausible':0, 'Probable':0 };
    }
    for (var i = 0; i < rows.length; i++) {
      var md = rows[i].md_v2;
      if (!moSelRowPasses(md)) continue;
      for (var k = 0; k < MO_ROWS.length; k++) {
        var rw = MO_ROWS[k];
        var tr = moNormaliseTier(moReadRating(md, rw.ratingPath));
        counts[rw.key][tr]++;
      }
    }

    var tbody = document.getElementById('mo-tbody');
    if (!tbody) return;
    var html = '';
    var anySel = moSelActive();
    for (var ti = 0; ti < MO_TIERS.length; ti++) {
      var tier = MO_TIERS[ti];
      html += '<tr class="mo-data-row"><td class="mo-tier-label">' + tier + '</td>';
      for (var c = 0; c < MO_ROWS.length; c++) {
        var rowDef = MO_ROWS[c];
        var n = counts[rowDef.key][tier];
        var sel = moSelIsOn(rowDef.key, tier);
        var cls = 'mo-cell ' + MO_TIER_CLS[tier] + (n > 0 ? ' mo-has' : ' mo-zero') + (sel ? ' mo-cell-sel' : '');
        var tip = rowDef.label + ' / ' + tier + ' - ' + n + ' stock(s)' +
          (anySel ? ' meeting the selected pattern' : '') +
          (sel ? '; selected (click to remove)' : '; click to add to the pattern');
        html += '<td class="' + cls + '" onclick="moCellClick(\'' + rowDef.key + '\',\'' + tier + '\')" ' +
          'title="' + moMxAttr(tip) + '">' + n.toLocaleString('en-GB') + '</td>';
      }
      html += '</tr>';
    }
    // Total rated row = Possible + Plausible + Probable per screen (tracks the
    // active selection automatically). Not selectable - it is a derived total.
    html += '<tr class="mo-total-row"><td class="mo-tier-label mo-total-label">Total rated</td>';
    for (var c2 = 0; c2 < MO_ROWS.length; c2++) {
      var ck = MO_ROWS[c2].key;
      var tot = counts[ck]['Possible'] + counts[ck]['Plausible'] + counts[ck]['Probable'];
      html += '<td class="mo-total-cell" title="' + moMxAttr(MO_ROWS[c2].label + ' - ' + tot + ' rated' + (anySel ? ' within the selected pattern' : '')) + '">' +
        tot.toLocaleString('en-GB') + '</td>';
    }
    html += '</tr>';
    tbody.innerHTML = html;

    var clr = document.getElementById('mo-clear-btn');
    if (clr) clr.classList.toggle('active', anySel);
  }

  // ----- the full rating matrix (Wave 3; chip row removed in S35) -----
  // Build the two sticky header rows once: section-group row, column-title row.
  function moMxBuildHead(thead) {
    // section-group row: one cell per contiguous section run.
    var groupTr = '<tr class="mo-mx-group-row"><th class="mo-mx-corner mo-mx-screen-col"></th>';
    var gi = 0;
    while (gi < MO_ROWS.length) {
      var sec = MO_ROWS[gi].section;
      var span = 0;
      while (gi + span < MO_ROWS.length && MO_ROWS[gi + span].section === sec) span++;
      groupTr += '<th colspan="' + span + '" class="' + (MO_GROUP_CLS[sec] || '') + '">' +
        moMxText(MO_GROUP_LABEL[sec] || sec) + '</th>';
      gi += span;
    }
    groupTr += '</tr>';

    // column-title row: one cell per screen, labels WRAP; click opens the tab.
    var colTr = '<tr class="mo-mx-col-row"><th class="mo-mx-screen-col">Stock</th>';
    for (var t = 0; t < MO_ROWS.length; t++) {
      colTr += '<th title="' + moMxAttr(MO_ROWS[t].label + ' - open this screen\'s tab') + '" ' +
        'onclick="moJumpToTab(\'' + moMxAttr(MO_ROWS[t].key) + '\')" style="cursor:pointer">' +
        moMxText(MO_ROWS[t].label) + '</th>';
    }
    colTr += '</tr>';

    thead.innerHTML = groupTr + colTr;
  }

  function moRenderMatrix() {
    var host = document.getElementById('tab-master_overview');
    if (!host) return;
    var wrap = host.querySelector('#mo-matrix-wrap');
    if (!wrap) {
      wrap = document.createElement('div');
      wrap.id = 'mo-matrix-wrap';
      wrap.innerHTML =
        '<div id="mo-matrix-caption">Full rating matrix: every stock against every screen. ' +
        'Each cell is the stock\'s rating for that screen; &#8211; where it does not qualify. ' +
        'Filtered by the pattern you select in the summary table above; click a screen ' +
        'name to open that screen\'s own tab.</div>' +
        '<div class="table-wrap"><div class="v2-hscroll"><table class="data-table" id="mo-matrix-table">' +  /* MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER */
        '<thead></thead><tbody id="mo-matrix-tbody"></tbody></table></div></div>' +  /* MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER */
        '<div id="mo-matrix-foot"></div>';
      host.appendChild(wrap);
    }
    var table = wrap.querySelector('#mo-matrix-table');
    var thead = table ? table.querySelector('thead') : null;
    var tbody = wrap.querySelector('#mo-matrix-tbody');
    if (!thead || !tbody) return;
    if (!thead.querySelector('tr.mo-mx-col-row')) moMxBuildHead(thead);

    // the matrix renders ALL md_v2 stocks; the summary-table selection filters
    // which rows are shown.
    var all = moGetRows();
    all.sort(function(a, b) {
      var an = (a.company || a.ticker).toLowerCase();
      var bn = (b.company || b.ticker).toLowerCase();
      return an < bn ? -1 : (an > bn ? 1 : 0);
    });

    var colCount = MO_ROWS.length + 1;
    var html = '';
    var shown = 0;
    for (var i = 0; i < all.length; i++) {
      var rec = all[i];
      var md = rec.md_v2;
      if (!moSelRowPasses(md)) continue;
      shown++;
      html += '<tr><td class="mo-mx-name-cell">' +
        '<span class="mo-mx-co">' + moMxText(rec.company || rec.ticker) + '</span>' +
        '<span class="mo-mx-tk">' + moMxText(rec.ticker) + '</span></td>';
      for (var r = 0; r < MO_ROWS.length; r++) {
        var tier = moNormaliseTier(moReadRating(md, MO_ROWS[r].ratingPath));
        if (tier === 'None') {
          html += '<td><span class="mo-mx-pill mo-mx-p-none">&#8211;</span></td>';
        } else {
          html += '<td><span class="mo-mx-pill ' + MO_MX_TIER_PILL[tier] + '">' + tier + '</span></td>';
        }
      }
      html += '</tr>';
    }
    if (shown === 0) {
      html = '<tr class="mo-mx-empty"><td colspan="' + colCount + '">' +
        'No stocks match the selected pattern.</td></tr>';
    }
    tbody.innerHTML = html;

    var foot = wrap.querySelector('#mo-matrix-foot');
    if (foot) {
      if (moSelActive()) {
        foot.textContent = shown.toLocaleString('en-GB') + ' of ' +
          all.length.toLocaleString('en-GB') + ' stocks match the selected pattern.';
        foot.className = 'mo-foot-active';
      } else {
        foot.textContent = 'Showing all ' + all.length.toLocaleString('en-GB') +
          ' stocks. Select cells in the summary table above to filter.';
        foot.className = '';
      }
    }
  }
  window.moRenderMatrix = moRenderMatrix;

  function renderMasterOverview() {
    moRenderTable();
    moRenderMatrix();
  }
  window.renderMasterOverview = renderMasterOverview;

})();
"""


def _splice(s, start_anchor, end_anchor, new_inner, label):
    """Replace the text strictly BETWEEN start_anchor and end_anchor (the
    anchors themselves are preserved). Both anchors must be present exactly
    once."""
    cs, ce = s.count(start_anchor), s.count(end_anchor)
    if cs != 1:
        raise AssertionError("[%s] start anchor count %d (expected 1): %r" % (label, cs, start_anchor))
    if ce != 1:
        raise AssertionError("[%s] end anchor count %d (expected 1): %r" % (label, ce, end_anchor))
    i = s.index(start_anchor) + len(start_anchor)
    j = s.index(end_anchor, i)
    if j < i:
        raise AssertionError("[%s] end anchor precedes start anchor" % label)
    return s[:i] + new_inner + s[j:]


def _rep(s, old, new, count, label):
    c = s.count(old)
    if c != count:
        raise AssertionError("[%s] expected %d occurrence(s), found %d -- anchor: %r"
                             % (label, count, c, old[:90]))
    return s.replace(old, new)


def transform(src):
    if MARKER in src:
        raise AssertionError("MARKER already present -- source is already patched")
    out = src
    # 1. transposed-table CSS block
    out = _splice(out, CSS_START, CSS_END, NEW_CSS, "css-block")
    # 2. matrix sticky-header offsets (chip row removed)
    out = _rep(out, OFF_OLD_GROUP, OFF_NEW_GROUP, 1, "matrix-group-row-offset")
    out = _rep(out, OFF_OLD_COL,   OFF_NEW_COL,   1, "matrix-col-row-offset")
    # 3. Master Overview JS module
    out = _splice(out, JS_START, JS_END, NEW_JS, "js-module")
    # post-conditions
    if MARKER not in out:
        raise AssertionError("MARKER missing from output -- splice failed")
    if out.count(MARKER) != 2:
        raise AssertionError("MARKER count %d in output (expected 2: CSS + JS)" % out.count(MARKER))
    if "moMxToggleChip" in out or "moMxFilters" in out or "mo-mx-chip-row" in out.replace(".mo-mx-chip", "X"):
        # the .mo-mx-chip* CSS rules are intentionally kept as inert dead rules;
        # but no JS reference to the chip system should survive.
        if "moMxToggleChip" in out or "moMxFilters" in out:
            raise AssertionError("chip-system JS reference survived the module rewrite")
    return out


def _git_head_source():
    out = subprocess.check_output(["git", "show", "HEAD:scripts/build_dashboard.py"])
    return out.decode("utf-8")


def main(argv):
    # ---- test mode ----
    if len(argv) >= 1 and argv[0] == "--test":
        src_path, out_path = argv[1], argv[2]
        with open(src_path, "r", encoding="utf-8") as f:
            src = f.read()
        out = transform(src)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(out)
        py_compile.compile(out_path, doraise=True)
        print("[--test] OK  in=%d  out=%d  -> %s" % (len(src), len(out), out_path))
        return 0

    # ---- production mode ----
    if not os.path.isfile(TARGET):
        print("ERROR: run from the master-dashboard repo root (scripts/build_dashboard.py not found).")
        return 2

    with open(TARGET, "r", encoding="utf-8", errors="replace") as f:
        wt = f.read()
    if MARKER in wt:
        print("Already patched (MARKER present in working tree). Nothing to do.")
        return 0

    head_src = _git_head_source()
    wt_md5  = hashlib.md5(wt.encode("utf-8", "replace")).hexdigest()
    head_md5 = hashlib.md5(head_src.encode("utf-8")).hexdigest()
    if wt_md5 != head_md5:
        print("ABORT: working-tree build_dashboard.py does not match HEAD and the")
        print("       S35 marker is absent. Unexpected state -- resolve before patching.")
        print("       working-tree md5: %s" % wt_md5)
        print("       HEAD         md5: %s" % head_md5)
        print("       (If HEAD is clean, run `git checkout -- scripts/build_dashboard.py` first.)")
        return 3

    out = transform(head_src)

    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = TARGET + ".bak-pre-overview-cooccurrence-s35-" + ts
    with open(bak, "w", encoding="utf-8") as f:
        f.write(wt)
    tmp = TARGET + ".tmp-s35-overview"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(out)
    py_compile.compile(tmp, doraise=True)
    os.replace(tmp, TARGET)

    print("OK: Overview transpose + co-occurrence applied.")
    print("    backup : %s" % bak)
    print("    target : %s  (%d -> %d chars)" % (TARGET, len(head_src), len(out)))
    print("    next   : python scripts/build_dashboard.py  ->  git add -A  ->  commit  ->  push")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
