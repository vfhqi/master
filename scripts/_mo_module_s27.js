/* MD-V2-MASTER-OVERVIEW-MARKER-START */

(function() {
  'use strict';

  // MD-V2-MASTER-OVERVIEW-S27-MARKER: Master Overview tab - Session 27.
  // A synoptic rating matrix: every screen across the MD V2 system as a row,
  // the 4 rating tiers as columns, count of stocks per cell. The default
  // landing tab. Cells are clickable - they jump to the underlying tab and
  // stash the (pattern, tier) intent in window._mdJump so the target tab can
  // pre-apply the chip filter once its _mdJump consumer wiring lands (a small
  // separate follow-up; the jump itself works now). Per Richard, the funnel
  // banner and other visualisations are PARKED - this is the basic table.

  var moState = { scope: 'all' };

  // Row model: { section, key, label, ratingPath, tabId, patternKey }
  //   ratingPath - how to read this screen's rating from a stock's md_v2:
  //     'stage:<k>'    -> md_v2[k].rating
  //     'group:<g>:<k>'-> md_v2[<g>][<k>].rating  (pre_indicators/indicators/setups/tests)
  //   tabId / patternKey - where a cell click jumps to, and which chip to arm.
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
    // -- Post-test indicators --
    { section:'Post-test indicators', key:'breakout', label:'Breakout', ratingPath:'group:indicators:breakout', tabId:'post_indicators', patternKey:'breakout' },
    { section:'Post-test indicators', key:'advancing', label:'Advancing', ratingPath:'group:indicators:advancing', tabId:'post_indicators', patternKey:'advancing' },
    { section:'Post-test indicators', key:'breakdown_50D', label:'Breakdown 50D', ratingPath:'group:indicators:breakdown_50D', tabId:'post_indicators', patternKey:'breakdown_50D' },
    { section:'Post-test indicators', key:'breakdown_150D', label:'Breakdown 150D', ratingPath:'group:indicators:breakdown_150D', tabId:'post_indicators', patternKey:'breakdown_150D' },
    { section:'Post-test indicators', key:'breakdown_200D', label:'Breakdown 200D', ratingPath:'group:indicators:breakdown_200D', tabId:'post_indicators', patternKey:'breakdown_200D' },
    // -- Capital qualification setups --
    { section:'Capital qualification setups', key:'probing_bet', label:'Probing bet', ratingPath:'group:setups:probing_bet', tabId:'setups', patternKey:'probing_bet' },
    { section:'Capital qualification setups', key:'vcp_after_s1_plateau', label:'VCP after Stage 1->2 plateau', ratingPath:'group:setups:vcp_after_s1_plateau', tabId:'setups', patternKey:'vcp_after_s1_plateau' },
    { section:'Capital qualification setups', key:'healthy_retest', label:'Healthy retest within MT/LT uptrend', ratingPath:'group:setups:healthy_retest', tabId:'setups', patternKey:'healthy_retest' },
    { section:'Capital qualification setups', key:'vcp_after_s2_base', label:'VCP after Stage 2 base', ratingPath:'group:setups:vcp_after_s2_base', tabId:'setups', patternKey:'vcp_after_s2_base' },
    // -- Capital deployment tests (S27 4-test structure) --
    { section:'Capital deployment tests', key:'ma_retest_upwards', label:'Upwards moving average retest', ratingPath:'group:tests:ma_retest_upwards', tabId:'tests', patternKey:'ma_retest_upwards' },
    { section:'Capital deployment tests', key:'vcp_deploy_s1', label:'VCP after Stage 1->2', ratingPath:'group:tests:vcp_deploy_s1', tabId:'tests', patternKey:'vcp_deploy_s1' },
    { section:'Capital deployment tests', key:'vcp_deploy_s2', label:'VCP after Stage 2 base', ratingPath:'group:tests:vcp_deploy_s2', tabId:'tests', patternKey:'vcp_deploy_s2' },
    { section:'Capital deployment tests', key:'probing_bet_test', label:'Probing bet', ratingPath:'group:tests:probing_bet', tabId:'tests', patternKey:'probing_bet' }
  ];

  // The 4 rating-tier columns. Stage 1 alone splits Probable into Early/Late
  // in the pipeline; for the matrix we fold both into the Probable column
  // (the count helper normalises that).
  var MO_TIERS = ['None', 'Possible', 'Plausible', 'Probable'];

  var MO_SECTION_TONE = {
    'Stages': 'mo-sec-stages',
    'Pre-test indicators': 'mo-sec-pretest',
    'Post-test indicators': 'mo-sec-posttest',
    'Capital qualification setups': 'mo-sec-setups',
    'Capital deployment tests': 'mo-sec-tests'
  };

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
  // Normalise any raw rating string to one of the 4 matrix tiers.
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
      rows.push({ ticker: s.ticker, md_v2: s.md_v2, is_live: !!live[s.ticker] });
    }
    return rows;
  }
  // Build the count matrix: { rowKey: { tier: count } } for the scoped rows.
  function moBuildMatrix(rows) {
    var m = {};
    for (var r = 0; r < MO_ROWS.length; r++) {
      m[MO_ROWS[r].key] = { 'None':0, 'Possible':0, 'Plausible':0, 'Probable':0 };
    }
    for (var i = 0; i < rows.length; i++) {
      var md = rows[i].md_v2;
      for (var k = 0; k < MO_ROWS.length; k++) {
        var row = MO_ROWS[k];
        var tier = moNormaliseTier(moReadRating(md, row.ratingPath));
        m[row.key][tier]++;
      }
    }
    return m;
  }
  function moApplyScope(all) {
    if (moState.scope === 'live') return all.filter(function(r){ return r.is_live; });
    return all;
  }

  // Cell click: stash the jump intent and switch tab. The target tab's
  // _mdJump consumer (small follow-up wiring) reads window._mdJump on render
  // and pre-applies the chip filter. Until that lands, the jump still works -
  // it just lands on the unfiltered tab.
  function moCellClick(rowKey, tier) {
    var row = null;
    for (var i = 0; i < MO_ROWS.length; i++) if (MO_ROWS[i].key === rowKey) row = MO_ROWS[i];
    if (!row) return;
    if (row.patternKey && tier !== 'None') {
      window._mdJump = { tab: row.tabId, patternKey: row.patternKey, tier: tier };
    } else {
      window._mdJump = { tab: row.tabId };
    }
    if (typeof window.switchTab === 'function') window.switchTab(row.tabId);
  }
  window.moCellClick = moCellClick;

  function moSetScope(s) {
    moState.scope = s;
    var btns = document.querySelectorAll('button[data-mo-scope]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-mo-scope') === s);
    moRenderTable();
  }
  window.moSetScope = moSetScope;

  var MO_TIER_CLS = { 'None':'mo-t-none', 'Possible':'mo-t-pos', 'Plausible':'mo-t-pla', 'Probable':'mo-t-prob' };

  function moRenderTable() {
    var host = document.getElementById('tab-master_overview');
    if (!host) return;
    if (!host.querySelector('#mo-main-table')) {
      var intro = '<div class="s1-intro">Master Overview is the synoptic view of the whole MD V2 system: every screen - the four stages, the pre-test and post-test indicators, the capital qualification setups and the capital deployment tests - as a row, with the count of stocks at each rating tier. Click any count to jump to that screen&apos;s tab. The funnel banner and other visualisations are deferred; this is the rating matrix.</div>';
      var controls = '<div class="controls s1-controls">' +
        '<div class="ctrl-grp"><span class="ctrl-label">Scope</span>' +
          '<button class="toggle-btn active" data-mo-scope="all" onclick="moSetScope(\'all\')">All</button>' +
          '<button class="toggle-btn" data-mo-scope="live" onclick="moSetScope(\'live\')">Live investments</button>' +
        '</div></div>';
      var table = '<div class="table-wrap"><table class="data-table" id="mo-main-table">' +
        '<thead><tr class="mo-head-row"><th class="mo-screen-col">Screen</th>';
      for (var t = 0; t < MO_TIERS.length; t++) table += '<th class="mo-tier-col">' + MO_TIERS[t] + '</th>';
      table += '<th class="mo-total-col">Total rated</th></tr></thead><tbody id="mo-tbody"></tbody></table></div>';
      host.innerHTML = intro + controls + table;
    }
    var all = moGetRows();
    var rows = moApplyScope(all);
    var matrix = moBuildMatrix(rows);
    var tbody = document.getElementById('mo-tbody');
    if (!tbody) return;
    var html = '';
    var lastSection = null;
    for (var r = 0; r < MO_ROWS.length; r++) {
      var row = MO_ROWS[r];
      if (row.section !== lastSection) {
        html += '<tr class="mo-section-row ' + (MO_SECTION_TONE[row.section] || '') + '">' +
                '<td class="mo-section-cell" colspan="' + (MO_TIERS.length + 2) + '">' + row.section + '</td></tr>';
        lastSection = row.section;
      }
      var counts = matrix[row.key];
      var ratedTotal = counts['Possible'] + counts['Plausible'] + counts['Probable'];
      html += '<tr class="mo-data-row">' +
              '<td class="mo-screen-cell">' + row.label + '</td>';
      for (var t2 = 0; t2 < MO_TIERS.length; t2++) {
        var tier = MO_TIERS[t2];
        var c = counts[tier];
        var clickable = (row.patternKey || tier === 'None') ? '' : '';
        var cls = 'mo-cell ' + MO_TIER_CLS[tier] + (c > 0 ? ' mo-has' : ' mo-zero');
        html += '<td class="' + cls + '" onclick="moCellClick(\'' + row.key + '\',\'' + tier + '\')" ' +
                'title="' + c + ' stock(s) - ' + row.label + ' / ' + tier + ' (click to open)">' +
                (c > 0 ? c.toLocaleString('en-GB') : '-') + '</td>';
      }
      html += '<td class="mo-total-cell">' + ratedTotal.toLocaleString('en-GB') + '</td>';
      html += '</tr>';
    }
    tbody.innerHTML = html;
  }

  function renderMasterOverview() {
    moRenderTable();
  }
  window.renderMasterOverview = renderMasterOverview;

})();

/* MD-V2-MASTER-OVERVIEW-MARKER-END */
