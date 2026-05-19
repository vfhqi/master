// =============================================================================
// CAPITAL QUALIFICATION TESTS TAB MODULE - Master Dashboard V2
// =============================================================================
// MD-V2-TESTS-MARKER - idempotency marker for patcher detection
//
// 3 capital qualification tests from _md_v2_screens.py md["tests"]:
//   Probing Bet test: stage flag (existing probing_bet filter)
//   VCP test: composite with 4 constituent checks
//   Uptrend Retest test: stage flag (existing uptrend_retest filter)
//
// Each test's constituent checks are surfaced as individual tick columns.
// =============================================================================

/* MD-V2-TESTS-MARKER-START */

(function() {
  'use strict';

  var tsState = {
    mode: { inputs: 'pct' },
    scope: 'all',
    testFilter: null,
    tint: 'none',
    port: 'off',
    sort: { col: 'company', dir: 'asc' }
  };

  var TS_TESTS = [
    {
      key: 'probing_bet', label: 'Probing Bet', tone: 'amber',
      tooltip: 'Probing-bet filter qualifies when stage is Late or Capital',
      tests: [
        { key: 'pb_stage_late_or_capital', label: 'PB stage Late/Capital', tooltip: 'Probing-bet filter has reached Late or Capital stage' }
      ]
    },
    {
      key: 'vcp', label: 'VCP', tone: 'teal',
      tooltip: 'VCP qualification needs higher-lows >=2 AND volume declining AND S1/S2 stage gate met',
      tests: [
        { key: 'higher_lows_ge_2', label: 'Higher lows >= 2', tooltip: 'At least 2 unbroken higher lows (Early/Mid/Late stage)' },
        { key: 'vol_declining',    label: 'Volume declining', tooltip: '10-day vs 50-day average volume ratio < 1.0 (declining)' },
        { key: 's1_or_s2_gate',    label: 'S1 or S2 gate met', tooltip: 'Stage 1 in Plausible/ProbableEarly/ProbableLate OR (S2 uptrend AND pullback >=15%)' }
      ]
    },
    {
      key: 'uptrend_retest', label: 'Uptrend Retest', tone: 'navy',
      tooltip: 'UTR filter qualifies when stage is Late or Capital',
      tests: [
        { key: 'utr_stage_late_or_capital', label: 'UTR stage Late/Capital', tooltip: 'Uptrend-retest filter has reached Late or Capital stage' }
      ]
    }
  ];

  function buildCols() {
    var cols = [
      { id:'name',     label:'Company - Ticker',     sortKey:'company',  cls:'name-cell' },
      { id:'taxon',    label:'Industry - Sector',    sortKey:'sector',   cls:'taxon' },
      { id:'price',    label:'Price',                sortKey:'price',    cls:'num' },
      { id:'hlow',     label:'Higher lows',          sortKey:'higher_lows', cls:'num' },
      { id:'vol',      label:'Vol 10D/50D',          sortKey:'utr_vol_trend', cls:'num' },
      { id:'vcp_stg',  label:'VCP stage',            sortKey:'vcp_stage_label', cls:'num' },
      { id:'pb_stg',   label:'PB stage',             sortKey:'pb_stage', cls:'num' },
      { id:'utr_stg',  label:'UTR stage',            sortKey:'utr_stage', cls:'num' }
    ];
    for (var s = 0; s < TS_TESTS.length; s++) {
      var test = TS_TESTS[s];
      for (var t = 0; t < test.tests.length; t++) {
        var sub = test.tests[t];
        var firstInGroup = (t === 0);
        var lastInGroup = (t === test.tests.length - 1);
        var cls = '';
        if (firstInGroup) cls += 'grp-start-g' + (s+1) + ' ';
        if (lastInGroup) cls += 'grp-end-g' + (s+1);
        cols.push({
          id: 't' + (s+1) + 's' + (t+1),
          label: sub.label,
          sortKey: test.key + '__' + sub.key,
          cls: cls.trim(),
          tooltip: sub.tooltip,
          testKey: test.key,
          subKey: sub.key,
          tone: test.tone
        });
      }
    }
    return cols;
  }
  var TS_COLS = buildCols();

  function tsPricesLookup() {
    if (window._tsPricesByTicker) return window._tsPricesByTicker;
    var out = {};
    var arr = (window.MASTER_DATA && MASTER_DATA.prices) || [];
    for (var i = 0; i < arr.length; i++) if (arr[i] && arr[i].ticker) out[arr[i].ticker] = arr[i];
    window._tsPricesByTicker = out;
    return out;
  }
  function tsLiveTickers() {
    var out = {};
    var inv = (window.MASTER_DATA && MASTER_DATA.positions && MASTER_DATA.positions.investments) || [];
    for (var i = 0; i < inv.length; i++) if (inv[i].ticker) out[inv[i].ticker] = true;
    return out;
  }
  function tsLiveSectors() {
    var out = {}, t, prices = tsPricesLookup(), tickers = tsLiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.sector) out[p.sector] = true; }
    return out;
  }
  function tsLiveIndustries() {
    var out = {}, t, prices = tsPricesLookup(), tickers = tsLiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.industry) out[p.industry] = true; }
    return out;
  }

  function tsEvalSubTest(row, subKey) {
    if (subKey === 'pb_stage_late_or_capital') {
      return row.pb_stage === 'Late' || row.pb_stage === 'Capital';
    }
    if (subKey === 'utr_stage_late_or_capital') {
      return row.utr_stage === 'Late' || row.utr_stage === 'Capital';
    }
    if (subKey === 'higher_lows_ge_2') {
      return row.higher_lows != null && row.higher_lows >= 2;
    }
    if (subKey === 'vol_declining') {
      return row.utr_vol_trend != null && row.utr_vol_trend < 1.0;
    }
    if (subKey === 's1_or_s2_gate') {
      var md = row.md_v2 || {};
      var s1r = (md.stage_1 && md.stage_1.rating) || '';
      var s2r = (md.stage_2 && md.stage_2.rating) || '';
      var s1Gate = s1r === 'Plausible' || s1r === 'Probable Early' || s1r === 'Probable Late';
      var s2Gate = (s2r === 'Probable' || s2r === 'Plausible') && row.recent_pullback != null && row.recent_pullback >= 0.15;
      return s1Gate || s2Gate;
    }
    return false;
  }

  function tsGetRows() {
    var raw = (window.MASTER_DATA && MASTER_DATA.filters) || [];
    var prices = tsPricesLookup();
    var live = tsLiveTickers(), liveS = tsLiveSectors(), liveI = tsLiveIndustries();
    var rows = [];
    for (var i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || !s.md_v2 || !s.md_v2.tests) continue;
      var p = prices[s.ticker] || {};
      var tests = s.md_v2.tests || {};
      var pbTest = tests.probing_bet || {};
      var vcpTest = tests.vcp || {};
      var utrTest = tests.uptrend_retest || {};
      rows.push({
        ticker: s.ticker, company: p.company_name || s.ticker,
        sector: p.sector || '', industry: p.industry || '',
        price: p.price,
        higher_lows: p.higher_lows,
        utr_vol_trend: p.utr_vol_trend,
        recent_pullback: p.recent_pullback_pct,
        pb_stage: pbTest.stage,
        vcp_stage_label: vcpTest.stage || '',
        utr_stage: utrTest.stage,
        tests_qualifies: { probing_bet: !!pbTest.qualifies, vcp: !!vcpTest.qualifies, uptrend_retest: !!utrTest.qualifies },
        md_v2: s.md_v2,
        is_live: !!live[s.ticker],
        sector_in_portfolio: !!liveS[p.sector],
        industry_in_portfolio: !!liveI[p.industry]
      });
    }
    return rows;
  }
  function tsTestCounts(rows) {
    var c = {};
    for (var k = 0; k < TS_TESTS.length; k++) c[TS_TESTS[k].key] = 0;
    for (var i = 0; i < rows.length; i++) {
      var q = rows[i].tests_qualifies || {};
      for (var key in c) if (q[key]) c[key]++;
    }
    return c;
  }

  function tsFmtNum(n) {
    if (n == null || isNaN(n)) return '-';
    var abs = Math.abs(n);
    var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);
    var f = abs.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });
    return n < 0 ? '(' + f + ')' : f;
  }
  function tsInputCell(row, key, extraCls) {
    extraCls = extraCls || '';
    var v = row[key];
    if (v == null) return '<td class="num ' + extraCls + '">-</td>';
    if (key === 'higher_lows') return '<td class="num ' + extraCls + '">' + v + '</td>';
    if (key === 'utr_vol_trend') return '<td class="num ' + extraCls + '">' + tsFmtNum(v) + '</td>';
    if (key === 'pb_stage' || key === 'utr_stage' || key === 'vcp_stage_label') {
      return '<td class="num ' + extraCls + '">' + (v || '-') + '</td>';
    }
    return '<td class="num ' + extraCls + '">' + tsFmtNum(v) + '</td>';
  }

  function tsTestCell(row, col) {
    var pass = tsEvalSubTest(row, col.subKey);
    var extra = col.cls || '';
    if (pass) return '<td class="ts-pass ts-tone-' + (col.tone || 'amber') + ' ' + extra + '"><span class="tick">' + String.fromCharCode(10003) + '</span></td>';
    return '<td class="ts-fail ' + extra + '">.</td>';
  }

  function tsHashColor(label, alpha) {
    if (!label) return null;
    var h = 0;
    for (var i = 0; i < label.length; i++) h = (h * 31 + label.charCodeAt(i)) & 0xffff;
    return 'hsla(' + (h % 360) + ', 35%, 55%, ' + alpha + ')';
  }
  function tsPortfolioInfo(row) {
    if (row.is_live) return { color:'#1b5e20', bg:'rgba(27,94,32,0.10)', bgHover:'rgba(27,94,32,0.14)' };
    if (row.sector_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.05)', bgHover:'rgba(27,94,32,0.08)' };
    if (row.industry_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.025)', bgHover:'rgba(27,94,32,0.05)' };
    return null;
  }

  function tsGetSortVal(row, key) {
    if (key.indexOf('__') > 0) {
      var parts = key.split('__');
      return tsEvalSubTest(row, parts[1]) ? 1 : 0;
    }
    if (key === 'higher_lows')   return row.higher_lows == null ? -Infinity : row.higher_lows;
    if (key === 'utr_vol_trend') return row.utr_vol_trend == null ? -Infinity : row.utr_vol_trend;
    if (key in row) return row[key];
    return 0;
  }
  function tsOnSort(key) {
    if (tsState.sort.col === key) tsState.sort.dir = tsState.sort.dir === 'desc' ? 'asc' : 'desc';
    else tsState.sort = { col: key, dir: key === 'company' ? 'asc' : 'desc' };
    tsBuildHeaderRow();
    tsRenderRows();
  }

  function tsBuildHeaderRow() {
    var tr = document.getElementById('ts-col-header-row');
    if (!tr) return;
    var h = '';
    for (var i = 0; i < TS_COLS.length; i++) {
      var c = TS_COLS[i];
      var isSort = tsState.sort.col === c.sortKey;
      var arrow = isSort
        ? '<span class="sort-arrow">' + (tsState.sort.dir === 'desc' ? String.fromCharCode(9660) : String.fromCharCode(9650)) + '</span>'
        : '<span class="sort-placeholder"></span>';
      var title = c.tooltip || c.label;
      h += '<th class="' + (c.cls || '') + '" data-sort-key="' + c.sortKey + '" title="' + title + '">' +
           '<span class="hd"><span class="lbl">' + c.label + '</span>' + arrow + '</span></th>';
    }
    tr.innerHTML = h;
  }

  function tsTestTiles(rows) {
    var tiles = document.getElementById('ts-test-tiles');
    if (!tiles) return;
    var counts = tsTestCounts(rows);
    var total = rows.length;
    var h = '';
    for (var i = 0; i < TS_TESTS.length; i++) {
      var t = TS_TESTS[i];
      var cnt = counts[t.key] || 0;
      var act = tsState.testFilter === t.key ? ' active' : '';
      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;
      h += '<div class="rating-tile ts-tile-' + t.tone + act + '" data-test="' + t.key + '" title="' + t.tooltip + '">' +
           '<div class="rt-label">' + t.label + '</div>' +
           '<div class="rt-count">' + cnt.toLocaleString('en-GB') + '</div>' +
           '<div class="rt-sub">of ' + total.toLocaleString('en-GB') + ' . ' + pct + '%</div>' +
           '<div class="rt-strip ts-strip-' + t.tone + '"></div>' +
           '</div>';
    }
    tiles.innerHTML = h;
  }

  function tsUpdateScopeCounts(rows) {
    function set(id, n) { var el = document.getElementById(id); if (el) el.textContent = '(' + n + ')'; }
    set('ts-cnt-all',      rows.length);
    set('ts-cnt-live',     rows.filter(function(r){ return r.is_live; }).length);
    set('ts-cnt-sector',   rows.filter(function(r){ return r.sector_in_portfolio; }).length);
    set('ts-cnt-industry', rows.filter(function(r){ return r.industry_in_portfolio; }).length);
  }

  function tsRenderRows() {
    var tbody = document.getElementById('ts-tbody');
    if (!tbody) return;
    var all = tsGetRows();
    tsUpdateScopeCounts(all);
    tsTestTiles(all);
    var rows = all.slice();
    if (tsState.scope === 'live') rows = rows.filter(function(r){ return r.is_live; });
    else if (tsState.scope === 'sector') rows = rows.filter(function(r){ return r.sector_in_portfolio; });
    else if (tsState.scope === 'industry') rows = rows.filter(function(r){ return r.industry_in_portfolio; });
    if (tsState.testFilter) {
      var key = tsState.testFilter;
      rows = rows.filter(function(r){ return !!(r.tests_qualifies || {})[key]; });
    }
    rows.sort(function(a,b) {
      var va = tsGetSortVal(a, tsState.sort.col), vb = tsGetSortVal(b, tsState.sort.col);
      var cmp = (typeof va === 'string') ? va.localeCompare(vb) : (va || 0) - (vb || 0);
      if (cmp === 0) cmp = a.ticker.localeCompare(b.ticker);
      return tsState.sort.dir === 'desc' ? -cmp : cmp;
    });
    var html = '';
    for (var i = 0; i < rows.length; i++) {
      var s = rows[i];
      var styles = [], cls = [];
      if (tsState.tint === 'industry') { styles.push('--tint-bg: ' + tsHashColor(s.industry, 0.16)); cls.push('tint-row'); }
      else if (tsState.tint === 'sector') { styles.push('--tint-bg: ' + tsHashColor(s.sector, 0.16)); cls.push('tint-row'); }
      if (tsState.port === 'on') {
        var pi = tsPortfolioInfo(s);
        if (pi) {
          styles.push('--portfolio-color: ' + pi.color);
          styles.push('--portfolio-bg: ' + pi.bg);
          styles.push('--portfolio-bg-hover: ' + pi.bgHover);
          cls.push('portfolio-band'); cls.push('portfolio-tint');
        }
      }
      var styleAttr = styles.length ? ' style="' + styles.join(';') + '"' : '';
      var clsAttr = cls.length ? ' class="' + cls.join(' ') + '"' : '';
      var liveDot = s.is_live ? '<span class="live-dot">' + String.fromCharCode(9679) + '</span>' : '';
      html += '<tr' + clsAttr + styleAttr + '>' +
        '<td class="name-cell"><div class="co">' + liveDot + (s.company || s.ticker) + '</div><div class="tk">' + s.ticker + '</div></td>' +
        '<td class="taxon"><div class="ind">' + (s.industry || '') + '</div><div class="sec">' + (s.sector || '') + '</div></td>' +
        tsInputCell(s, 'price') + tsInputCell(s, 'higher_lows') + tsInputCell(s, 'utr_vol_trend') +
        tsInputCell(s, 'vcp_stage_label') + tsInputCell(s, 'pb_stage') + tsInputCell(s, 'utr_stage');
      for (var j = 8; j < TS_COLS.length; j++) html += tsTestCell(s, TS_COLS[j]);
      html += '</tr>';
    }
    tbody.innerHTML = html;
  }

  function tsSetMode(kind, val) {
    tsState.mode[kind] = val;
    var btns = document.querySelectorAll('button[data-ts-grp="' + kind + '"]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-ts-val') === val);
    tsRenderRows();
  }
  function tsSetScope(s) {
    tsState.scope = s;
    var btns = document.querySelectorAll('button[data-ts-scope]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-ts-scope') === s);
    tsRenderRows();
  }
  function tsSetTint(t) {
    tsState.tint = t;
    var btns = document.querySelectorAll('button[data-ts-tint]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-ts-tint') === t);
    tsRenderRows();
  }
  function tsSetPort(p) {
    tsState.port = p;
    var btns = document.querySelectorAll('button[data-ts-port]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-ts-port') === p);
    tsRenderRows();
  }
  function tsToggleTest(k) {
    tsState.testFilter = (tsState.testFilter === k) ? null : k;
    tsRenderRows();
  }
  window.tsSetMode = tsSetMode;
  window.tsSetScope = tsSetScope;
  window.tsSetTint = tsSetTint;
  window.tsSetPort = tsSetPort;
  window.tsToggleTest = tsToggleTest;
  window.tsOnSort = tsOnSort;

  function tsBuildScaffold() {
    var host = document.getElementById('tab-tests');
    if (!host) return false;
    if (host.querySelector('#ts-main-table')) return true;

    var colgroupHtml = '<col class="c-name"><col class="c-taxon"><col class="c-price"><col class="c-hlow"><col class="c-vol"><col class="c-vcpstg"><col class="c-pbstg"><col class="c-utrstg">';
    var inputsColspan = 8;
    var groupHeaderHtml = '<th class="gh-inputs" colspan="' + inputsColspan + '">Inputs</th>';
    for (var s = 0; s < TS_TESTS.length; s++) {
      var test = TS_TESTS[s];
      var n = test.tests.length;
      for (var t = 0; t < n; t++) colgroupHtml += '<col class="c-test">';
      var startCls = 'grp-start-g' + (s+1);
      var endCls = 'grp-end-g' + (s+1);
      groupHeaderHtml += '<th class="gh-g' + (s+1) + ' ' + startCls + ' ' + endCls + '" colspan="' + n + '">' + test.label + '</th>';
    }

    var html = '' +
      '<div class="s1-intro">Capital qualification tests feed the two trade tranches (probing-bet and core MM). Probing Bet and Uptrend Retest are gated on a single stage indicator each (Late/Capital). VCP is a composite of three constituent checks (higher-lows count, declining volume, and an S1-or-S2 stage gate). Each constituent check is shown as its own tick column. Click a tile to filter the table to the parent test; click again to clear.</div>' +
      '<div class="controls s1-controls">' +
        '<div class="ctrl-grp"><span class="ctrl-label">Scope</span>' +
          '<button class="toggle-btn active" data-ts-scope="all" onclick="tsSetScope(\'all\')">All <span id="ts-cnt-all"></span></button>' +
          '<button class="toggle-btn" data-ts-scope="live" onclick="tsSetScope(\'live\')">Live <span id="ts-cnt-live"></span></button>' +
          '<button class="toggle-btn" data-ts-scope="sector" onclick="tsSetScope(\'sector\')">Sectors <span id="ts-cnt-sector"></span></button>' +
          '<button class="toggle-btn" data-ts-scope="industry" onclick="tsSetScope(\'industry\')">Industries <span id="ts-cnt-industry"></span></button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Peers</button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Cohorts</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Colour by</span>' +
          '<button class="toggle-btn active" data-ts-tint="none" onclick="tsSetTint(\'none\')">Off</button>' +
          '<button class="toggle-btn" data-ts-tint="industry" onclick="tsSetTint(\'industry\')">Industry</button>' +
          '<button class="toggle-btn" data-ts-tint="sector" onclick="tsSetTint(\'sector\')">Sector</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Portfolio tint</span>' +
          '<button class="toggle-btn active" data-ts-port="off" onclick="tsSetPort(\'off\')">Off</button>' +
          '<button class="toggle-btn" data-ts-port="on" onclick="tsSetPort(\'on\')">On</button>' +
        '</div>' +
      '</div>' +
      '<div class="rating-tiles s1-rating-tiles" id="ts-test-tiles"></div>' +
      '<div class="group-captions">' +
        '<div class="gcap gcap-g1"><b>Probing Bet</b>Single stage gate from the probing-bet filter. Qualifies at Late or Capital stage. One test column.</div>' +
        '<div class="gcap gcap-g2"><b>VCP</b>Composite of three checks: higher-lows >=2 AND volume declining (10D/50D < 1) AND S1-or-S2 stage gate. Three test columns.</div>' +
        '<div class="gcap gcap-g3"><b>Uptrend Retest</b>Single stage gate from the uptrend-retest filter. Qualifies at Late or Capital stage. One test column.</div>' +
      '</div>' +
      '<div class="table-wrap">' +
        '<table class="data-table" id="ts-main-table">' +
          '<colgroup>' + colgroupHtml + '</colgroup>' +
          '<thead>' +
            '<tr class="group-header-row">' + groupHeaderHtml + '</tr>' +
            '<tr class="col-header-row" id="ts-col-header-row"></tr>' +
          '</thead>' +
          '<tbody id="ts-tbody"></tbody>' +
        '</table>' +
      '</div>';
    host.innerHTML = html;
    var tiles = document.getElementById('ts-test-tiles');
    if (tiles) {
      tiles.addEventListener('click', function(e) {
        var tile = e.target.closest('.rating-tile');
        if (!tile) return;
        var k = tile.getAttribute('data-test');
        if (k) tsToggleTest(k);
      });
    }
    var hdr = document.getElementById('ts-col-header-row');
    if (hdr) {
      hdr.addEventListener('click', function(e) {
        var th = e.target.closest('th');
        if (!th) return;
        var key = th.getAttribute('data-sort-key');
        if (key) tsOnSort(key);
      });
    }
    return true;
  }

  function renderCapTests() {
    if (!tsBuildScaffold()) return;
    tsBuildHeaderRow();
    tsRenderRows();
  }
  window.renderCapTests = renderCapTests;

})();

/* MD-V2-TESTS-MARKER-END */
