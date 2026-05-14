// =============================================================================
// POST-INDICATORS TAB MODULE - Master Dashboard V2
// =============================================================================
// MD-V2-POST-INDICATORS-MARKER - idempotency marker for patcher detection
//
// Post-indicators = 5 trailing binary patterns from _md_v2_screens.py.
// Each pattern is the AND of constituent tests; each test gets its own column.
//
// PATTERNS AND CONSTITUENT TESTS:
//   Breakout (bull, 2 tests):
//     - Price > 1.08x 5D MA
//     - Up-volume >= 1.10x down-volume
//   Advancing (bull, 3 tests):
//     - Price > 20D MA
//     - 20D MA rising (vs 20D_prev)
//     - NOT in breakout (catch-all gate)
//   Breakdown 50D (bear, 2 tests):
//     - Price < 50D MA
//     - Price_prev was at/above 50D_prev (recently above)
//   Breakdown 150D (bear, 2 tests):
//     - Price < 150D MA
//     - Price_prev was at/above 150D_prev
//   Breakdown 200D (bear, 2 tests):
//     - Price < 200D MA
//     - Price_prev was at/above 200D_prev
// =============================================================================

/* MD-V2-POST-INDICATORS-MARKER-START */

(function() {
  'use strict';

  var poState = {
    mode: { inputs: 'pct' },
    scope: 'all',
    patternFilter: null,
    tint: 'none',
    port: 'off',
    sort: { col: 'company', dir: 'asc' }
  };

  var PO_PATTERNS = [
    {
      key: 'breakout', label: 'Breakout', sign: 'bull',
      tooltip: 'Price > 1.08x 5-day MA AND up-volume > 1.10x down-volume',
      tests: [
        { key: 'price_gt_108_ma5',    label: 'Price > 1.08x 5D MA', tooltip: 'Current price is more than 1.08 times the 5-day moving average' },
        { key: 'adv_up_ge_110_adv_dn', label: 'Up vol >= 1.10x down vol', tooltip: '1-month up-volume is at least 1.10x 1-month down-volume' }
      ]
    },
    {
      key: 'advancing', label: 'Advancing', sign: 'bull',
      tooltip: 'Price above rising 20-day MA, not in breakout (catch-all positive trend)',
      tests: [
        { key: 'price_gt_ma20',  label: 'Price > 20D MA',  tooltip: 'Current price above the 20-day moving average' },
        { key: 'ma20_rising',     label: '20D MA rising',   tooltip: '20-day MA today is higher than the 20-day MA one period prior' },
        { key: 'not_in_breakout', label: 'Not in breakout', tooltip: 'Excludes stocks already passing the Breakout pattern, to avoid double-counting' }
      ]
    },
    {
      key: 'breakdown_50D', label: 'Breakdown 50D', sign: 'bear',
      tooltip: 'Price has crossed below 50-day MA from above',
      tests: [
        { key: 'price_lt_ma50',          label: 'Price < 50D MA',     tooltip: 'Current price below the 50-day moving average' },
        { key: 'price_prev_at_or_above_ma50_prev', label: 'Was above 50D recently', tooltip: 'Previous price was at or above 99% of the previous 50-day MA' }
      ]
    },
    {
      key: 'breakdown_150D', label: 'Breakdown 150D', sign: 'bear',
      tooltip: 'Price has crossed below 150-day MA from above',
      tests: [
        { key: 'price_lt_ma150',          label: 'Price < 150D MA',     tooltip: 'Current price below the 150-day moving average' },
        { key: 'price_prev_at_or_above_ma150_prev', label: 'Was above 150D recently', tooltip: 'Previous price was at or above 99% of the previous 150-day MA' }
      ]
    },
    {
      key: 'breakdown_200D', label: 'Breakdown 200D', sign: 'bear',
      tooltip: 'Price has crossed below 200-day MA from above',
      tests: [
        { key: 'price_lt_ma200',          label: 'Price < 200D MA',     tooltip: 'Current price below the 200-day moving average' },
        { key: 'price_prev_at_or_above_ma200_prev', label: 'Was above 200D recently', tooltip: 'Previous price was at or above 99% of the previous 200-day MA' }
      ]
    }
  ];

  function buildCols() {
    var cols = [
      { id:'name',    label:'Company - Ticker',     sortKey:'company',  cls:'name-cell' },
      { id:'taxon',   label:'Industry - Sector',    sortKey:'sector',   cls:'taxon' },
      { id:'price',   label:'Price',                sortKey:'price',    cls:'num' },
      { id:'ma_5',    label:'5 day MA',             sortKey:'ma_5',     cls:'num' },
      { id:'ma_20',   label:'20 day MA',            sortKey:'ma_20',    cls:'num' },
      { id:'ma_50',   label:'50 day MA',            sortKey:'ma_50',    cls:'num' },
      { id:'ma_150',  label:'150 day MA',           sortKey:'ma_150',   cls:'num' },
      { id:'ma_200',  label:'200 day MA',           sortKey:'ma_200',   cls:'num' }
    ];
    for (var p = 0; p < PO_PATTERNS.length; p++) {
      var pat = PO_PATTERNS[p];
      for (var t = 0; t < pat.tests.length; t++) {
        var test = pat.tests[t];
        var firstInGroup = (t === 0);
        var lastInGroup = (t === pat.tests.length - 1);
        var cls = '';
        if (firstInGroup) cls += 'grp-start-g' + (p+1) + ' ';
        if (lastInGroup) cls += 'grp-end-g' + (p+1);
        cols.push({
          id: 'p' + (p+1) + 't' + (t+1),
          label: test.label,
          sortKey: pat.key + '__' + test.key,
          cls: cls.trim(),
          tooltip: test.tooltip,
          patternKey: pat.key,
          testKey: test.key,
          sign: pat.sign
        });
      }
    }
    return cols;
  }
  var PO_COLS = buildCols();

  function poPricesLookup() {
    if (window._poPricesByTicker) return window._poPricesByTicker;
    var out = {};
    var arr = (window.MASTER_DATA && MASTER_DATA.prices) || [];
    for (var i = 0; i < arr.length; i++) if (arr[i] && arr[i].ticker) out[arr[i].ticker] = arr[i];
    window._poPricesByTicker = out;
    return out;
  }
  function poLiveTickers() {
    var out = {};
    var inv = (window.MASTER_DATA && MASTER_DATA.positions && MASTER_DATA.positions.investments) || [];
    for (var i = 0; i < inv.length; i++) if (inv[i].ticker) out[inv[i].ticker] = true;
    return out;
  }
  function poLiveSectors() {
    var out = {}, t, prices = poPricesLookup(), tickers = poLiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.sector) out[p.sector] = true; }
    return out;
  }
  function poLiveIndustries() {
    var out = {}, t, prices = poPricesLookup(), tickers = poLiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.industry) out[p.industry] = true; }
    return out;
  }

  function poEvalTest(row, testKey) {
    var p = row;
    if (testKey === 'price_gt_108_ma5') {
      return p.price != null && p.ma_5 != null && p.ma_5 > 0 && p.price > p.ma_5 * 1.08;
    }
    if (testKey === 'adv_up_ge_110_adv_dn') {
      return p.adv_1m_up != null && p.adv_1m_dn != null && p.adv_1m_up > 0 && p.adv_1m_dn > 0 && p.adv_1m_up >= p.adv_1m_dn * 1.10;
    }
    if (testKey === 'price_gt_ma20') {
      return p.price != null && p.ma_20 != null && p.price > p.ma_20;
    }
    if (testKey === 'ma20_rising') {
      return p.ma_20 != null && p.ma_20_prev != null && p.ma_20 > p.ma_20_prev;
    }
    if (testKey === 'not_in_breakout') {
      var bo = (p.indicators && p.indicators.breakout) === true;
      return !bo;
    }
    if (testKey === 'price_lt_ma50') {
      return p.price != null && p.ma_50 != null && p.price < p.ma_50;
    }
    if (testKey === 'price_prev_at_or_above_ma50_prev') {
      return p.price_prev != null && p.ma_50_prev != null && p.ma_50_prev > 0 && p.price_prev >= p.ma_50_prev * 0.99;
    }
    if (testKey === 'price_lt_ma150') {
      return p.price != null && p.ma_150 != null && p.price < p.ma_150;
    }
    if (testKey === 'price_prev_at_or_above_ma150_prev') {
      return p.price_prev != null && p.ma_150_prev != null && p.ma_150_prev > 0 && p.price_prev >= p.ma_150_prev * 0.99;
    }
    if (testKey === 'price_lt_ma200') {
      return p.price != null && p.ma_200 != null && p.price < p.ma_200;
    }
    if (testKey === 'price_prev_at_or_above_ma200_prev') {
      return p.price_prev != null && p.ma_200_prev != null && p.ma_200_prev > 0 && p.price_prev >= p.ma_200_prev * 0.99;
    }
    return false;
  }

  function poGetRows() {
    var raw = (window.MASTER_DATA && MASTER_DATA.filters) || [];
    var prices = poPricesLookup();
    var live = poLiveTickers(), liveS = poLiveSectors(), liveI = poLiveIndustries();
    var rows = [];
    for (var i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || !s.md_v2 || !s.md_v2.indicators) continue;
      var p = prices[s.ticker] || {};
      var ind = s.md_v2.indicators || {};
      var mas = p.mas || {};
      rows.push({
        ticker: s.ticker, company: p.company_name || s.ticker,
        sector: p.sector || '', industry: p.industry || '',
        price: p.price,
        price_prev: p.price_prev,
        adv_1m_up: p.adv_1m_up, adv_1m_dn: p.adv_1m_dn,
        ma_5: mas['5D'],
        ma_20: mas['20D'], ma_20_prev: mas['20D_prev'],
        ma_50: mas['50D'], ma_50_prev: mas['50D_prev'],
        ma_150: mas['150D'], ma_150_prev: mas['150D_prev'],
        ma_200: mas['200D'], ma_200_prev: mas['200D_prev'],
        indicators: ind,
        is_live: !!live[s.ticker],
        sector_in_portfolio: !!liveS[p.sector],
        industry_in_portfolio: !!liveI[p.industry]
      });
    }
    return rows;
  }
  function poPatternCounts(rows) {
    var c = {};
    for (var k = 0; k < PO_PATTERNS.length; k++) c[PO_PATTERNS[k].key] = 0;
    for (var i = 0; i < rows.length; i++) {
      var ind = rows[i].indicators || {};
      for (var key in c) if (ind[key]) c[key]++;
    }
    return c;
  }

  function poFmtNum(n) {
    if (n == null || isNaN(n)) return '-';
    var abs = Math.abs(n);
    var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);
    var f = abs.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });
    return n < 0 ? '(' + f + ')' : f;
  }
  function poFmtPct(p) {
    if (p == null || isNaN(p)) return '-';
    var r = Math.round(p), abs = Math.abs(r);
    return r < 0 ? '(' + abs + ')%' : r + '%';
  }
  function poColourForIntensity(i) {
    if (i >= 0.6) return '#0F6E56';
    if (i >= 0.25) return '#1D9E75';
    if (i >= 0.05) return '#5DCAA5';
    if (i <= -0.6) return '#A32D2D';
    if (i <= -0.25) return '#E24B4A';
    if (i <= -0.05) return '#F09595';
    return '#888';
  }
  function poInputCell(row, key, extraCls) {
    extraCls = extraCls || '';
    var v = row[key];
    if (key === 'price') return '<td class="num ' + extraCls + '">' + poFmtNum(v) + '</td>';
    if (v == null || row.price == null) return '<td class="num ' + extraCls + '">-</td>';
    var pct = (row.price - v) / v * 100;
    var intensity = Math.max(-1, Math.min(1, pct / 10));
    var colour = poColourForIntensity(intensity);
    var text = (poState.mode.inputs === 'pct') ? poFmtPct(pct) : poFmtNum(v);
    return '<td class="num ' + extraCls + '" style="color:' + colour + '">' + text + '</td>';
  }

  function poTestCell(row, col) {
    var pass = poEvalTest(row, col.testKey);
    var extra = col.cls || '';
    if (pass) {
      var cls = col.sign === 'bull' ? 'po-pass-bull' : 'po-pass-bear';
      return '<td class="' + cls + ' ' + extra + '"><span class="tick">' + String.fromCharCode(10003) + '</span></td>';
    }
    return '<td class="po-fail ' + extra + '">.</td>';
  }

  function poHashColor(label, alpha) {
    if (!label) return null;
    var h = 0;
    for (var i = 0; i < label.length; i++) h = (h * 31 + label.charCodeAt(i)) & 0xffff;
    return 'hsla(' + (h % 360) + ', 35%, 55%, ' + alpha + ')';
  }
  function poPortfolioInfo(row) {
    if (row.is_live) return { color:'#1b5e20', bg:'rgba(27,94,32,0.10)', bgHover:'rgba(27,94,32,0.14)' };
    if (row.sector_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.05)', bgHover:'rgba(27,94,32,0.08)' };
    if (row.industry_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.025)', bgHover:'rgba(27,94,32,0.05)' };
    return null;
  }

  function poGetSortVal(row, key) {
    if (key.indexOf('__') > 0) {
      var parts = key.split('__');
      return poEvalTest(row, parts[1]) ? 1 : 0;
    }
    var PCT_KEYS = ['ma_5','ma_20','ma_50','ma_150','ma_200'];
    if (PCT_KEYS.indexOf(key) > -1 && poState.mode.inputs === 'pct') {
      var ref = row[key];
      if (ref == null || row.price == null || ref === 0) return -Infinity;
      return (row.price - ref) / ref * 100;
    }
    if (key in row) return row[key];
    return 0;
  }
  function poOnSort(key) {
    if (poState.sort.col === key) poState.sort.dir = poState.sort.dir === 'desc' ? 'asc' : 'desc';
    else poState.sort = { col: key, dir: key === 'company' ? 'asc' : 'desc' };
    poBuildHeaderRow();
    poRenderRows();
  }

  function poBuildHeaderRow() {
    var tr = document.getElementById('po-col-header-row');
    if (!tr) return;
    var h = '';
    for (var i = 0; i < PO_COLS.length; i++) {
      var c = PO_COLS[i];
      var isSort = poState.sort.col === c.sortKey;
      var arrow = isSort
        ? '<span class="sort-arrow">' + (poState.sort.dir === 'desc' ? String.fromCharCode(9660) : String.fromCharCode(9650)) + '</span>'
        : '<span class="sort-placeholder"></span>';
      var title = c.tooltip || c.label;
      h += '<th class="' + (c.cls || '') + '" data-sort-key="' + c.sortKey + '" title="' + title + '">' +
           '<span class="hd"><span class="lbl">' + c.label + '</span>' + arrow + '</span></th>';
    }
    tr.innerHTML = h;
  }

  function poPatternTiles(rows) {
    var tiles = document.getElementById('po-pattern-tiles');
    if (!tiles) return;
    var counts = poPatternCounts(rows);
    var total = rows.length;
    var h = '';
    for (var i = 0; i < PO_PATTERNS.length; i++) {
      var pat = PO_PATTERNS[i];
      var cnt = counts[pat.key] || 0;
      var act = poState.patternFilter === pat.key ? ' active' : '';
      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;
      var tileCls = pat.sign === 'bull' ? 'po-tile-bull' : 'po-tile-bear';
      var stripCls = pat.sign === 'bull' ? 'po-strip-bull' : 'po-strip-bear';
      h += '<div class="rating-tile ' + tileCls + act + '" data-pattern="' + pat.key + '" title="' + pat.tooltip + '">' +
           '<div class="rt-label">' + pat.label + '</div>' +
           '<div class="rt-count">' + cnt.toLocaleString('en-GB') + '</div>' +
           '<div class="rt-sub">of ' + total.toLocaleString('en-GB') + ' . ' + pct + '%</div>' +
           '<div class="rt-strip ' + stripCls + '"></div>' +
           '</div>';
    }
    tiles.innerHTML = h;
  }

  function poUpdateScopeCounts(rows) {
    function set(id, n) { var el = document.getElementById(id); if (el) el.textContent = '(' + n + ')'; }
    set('po-cnt-all',      rows.length);
    set('po-cnt-live',     rows.filter(function(r){ return r.is_live; }).length);
    set('po-cnt-sector',   rows.filter(function(r){ return r.sector_in_portfolio; }).length);
    set('po-cnt-industry', rows.filter(function(r){ return r.industry_in_portfolio; }).length);
  }

  function poRenderRows() {
    var tbody = document.getElementById('po-tbody');
    if (!tbody) return;
    var all = poGetRows();
    poUpdateScopeCounts(all);
    poPatternTiles(all);
    var rows = all.slice();
    if (poState.scope === 'live') rows = rows.filter(function(r){ return r.is_live; });
    else if (poState.scope === 'sector') rows = rows.filter(function(r){ return r.sector_in_portfolio; });
    else if (poState.scope === 'industry') rows = rows.filter(function(r){ return r.industry_in_portfolio; });
    if (poState.patternFilter) {
      var key = poState.patternFilter;
      rows = rows.filter(function(r){ return !!(r.indicators || {})[key]; });
    }
    rows.sort(function(a,b) {
      var va = poGetSortVal(a, poState.sort.col), vb = poGetSortVal(b, poState.sort.col);
      var cmp = (typeof va === 'string') ? va.localeCompare(vb) : (va || 0) - (vb || 0);
      if (cmp === 0) cmp = a.ticker.localeCompare(b.ticker);
      return poState.sort.dir === 'desc' ? -cmp : cmp;
    });
    var html = '';
    for (var i = 0; i < rows.length; i++) {
      var s = rows[i];
      var styles = [], cls = [];
      if (poState.tint === 'industry') { styles.push('--tint-bg: ' + poHashColor(s.industry, 0.16)); cls.push('tint-row'); }
      else if (poState.tint === 'sector') { styles.push('--tint-bg: ' + poHashColor(s.sector, 0.16)); cls.push('tint-row'); }
      if (poState.port === 'on') {
        var pi = poPortfolioInfo(s);
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
        poInputCell(s, 'price') + poInputCell(s, 'ma_5') + poInputCell(s, 'ma_20') +
        poInputCell(s, 'ma_50') + poInputCell(s, 'ma_150') + poInputCell(s, 'ma_200');
      for (var j = 8; j < PO_COLS.length; j++) html += poTestCell(s, PO_COLS[j]);
      html += '</tr>';
    }
    tbody.innerHTML = html;
  }

  function poSetMode(kind, val) {
    poState.mode[kind] = val;
    var btns = document.querySelectorAll('button[data-po-grp="' + kind + '"]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-po-val') === val);
    poRenderRows();
  }
  function poSetScope(s) {
    poState.scope = s;
    var btns = document.querySelectorAll('button[data-po-scope]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-po-scope') === s);
    poRenderRows();
  }
  function poSetTint(t) {
    poState.tint = t;
    var btns = document.querySelectorAll('button[data-po-tint]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-po-tint') === t);
    poRenderRows();
  }
  function poSetPort(p) {
    poState.port = p;
    var btns = document.querySelectorAll('button[data-po-port]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-po-port') === p);
    poRenderRows();
  }
  function poTogglePattern(k) {
    poState.patternFilter = (poState.patternFilter === k) ? null : k;
    poRenderRows();
  }
  window.poSetMode = poSetMode;
  window.poSetScope = poSetScope;
  window.poSetTint = poSetTint;
  window.poSetPort = poSetPort;
  window.poTogglePattern = poTogglePattern;
  window.poOnSort = poOnSort;

  function poBuildScaffold() {
    var host = document.getElementById('tab-post_indicators');
    if (!host) return false;
    if (host.querySelector('#po-main-table')) return true;

    var colgroupHtml = '<col class="c-name"><col class="c-taxon"><col class="c-price"><col class="c-ma"><col class="c-ma"><col class="c-ma"><col class="c-ma"><col class="c-ma">';
    var inputsColspan = 8;
    var groupHeaderHtml = '<th class="gh-inputs" colspan="' + inputsColspan + '">Inputs</th>';
    for (var p = 0; p < PO_PATTERNS.length; p++) {
      var pat = PO_PATTERNS[p];
      var n = pat.tests.length;
      for (var t = 0; t < n; t++) colgroupHtml += '<col class="c-test">';
      var startCls = 'grp-start-g' + (p+1);
      var endCls = 'grp-end-g' + (p+1);
      groupHeaderHtml += '<th class="gh-g' + (p+1) + ' ' + startCls + ' ' + endCls + '" colspan="' + n + '">' + pat.label + '</th>';
    }

    var html = '' +
      '<div class="s1-intro">Post-indicators are five trailing binary patterns. Each pattern is the AND of two or three constituent tests, shown as individual tick columns. Bullish: Breakout (price > 1.08x 5D MA AND up-volume >= 1.10x down) and Advancing (price above rising 20D MA, not already in breakout). Bearish: Breakdown 50D / 150D / 200D (price has crossed below the respective MA from above). Click a tile to filter the table to the parent pattern; click again to clear.</div>' +
      '<div class="controls s1-controls">' +
        '<div class="ctrl-grp"><span class="ctrl-label">Inputs</span>' +
          '<button class="toggle-btn active" data-po-grp="inputs" data-po-val="pct" onclick="poSetMode(\'inputs\',\'pct\')">show as %</button>' +
          '<button class="toggle-btn" data-po-grp="inputs" data-po-val="raw" onclick="poSetMode(\'inputs\',\'raw\')">show as numbers</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Scope</span>' +
          '<button class="toggle-btn active" data-po-scope="all" onclick="poSetScope(\'all\')">All <span id="po-cnt-all"></span></button>' +
          '<button class="toggle-btn" data-po-scope="live" onclick="poSetScope(\'live\')">Live <span id="po-cnt-live"></span></button>' +
          '<button class="toggle-btn" data-po-scope="sector" onclick="poSetScope(\'sector\')">Sectors <span id="po-cnt-sector"></span></button>' +
          '<button class="toggle-btn" data-po-scope="industry" onclick="poSetScope(\'industry\')">Industries <span id="po-cnt-industry"></span></button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Peers</button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Cohorts</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Colour by</span>' +
          '<button class="toggle-btn active" data-po-tint="none" onclick="poSetTint(\'none\')">Off</button>' +
          '<button class="toggle-btn" data-po-tint="industry" onclick="poSetTint(\'industry\')">Industry</button>' +
          '<button class="toggle-btn" data-po-tint="sector" onclick="poSetTint(\'sector\')">Sector</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Portfolio tint</span>' +
          '<button class="toggle-btn active" data-po-port="off" onclick="poSetPort(\'off\')">Off</button>' +
          '<button class="toggle-btn" data-po-port="on" onclick="poSetPort(\'on\')">On</button>' +
        '</div>' +
      '</div>' +
      '<div class="rating-tiles s1-rating-tiles" id="po-pattern-tiles"></div>' +
      '<div class="group-captions">' +
        '<div class="gcap gcap-g1"><b>Breakout</b>Price > 1.08x the 5-day moving average AND up-volume > 1.10x down-volume. Two tests.</div>' +
        '<div class="gcap gcap-g1"><b>Advancing</b>Price above rising 20-day MA, not already in breakout. Three tests (catch-all positive trend).</div>' +
        '<div class="gcap gcap-g2"><b>Breakdown 50D</b>Price has crossed below the 50-day MA from above. Two tests.</div>' +
        '<div class="gcap gcap-g2"><b>Breakdown 150D</b>Price has crossed below the 150-day MA. Two tests.</div>' +
        '<div class="gcap gcap-g2"><b>Breakdown 200D</b>Price has crossed below the 200-day MA. Two tests.</div>' +
      '</div>' +
      '<div class="table-wrap">' +
        '<table class="data-table" id="po-main-table">' +
          '<colgroup>' + colgroupHtml + '</colgroup>' +
          '<thead>' +
            '<tr class="group-header-row">' + groupHeaderHtml + '</tr>' +
            '<tr class="col-header-row" id="po-col-header-row"></tr>' +
          '</thead>' +
          '<tbody id="po-tbody"></tbody>' +
        '</table>' +
      '</div>';
    host.innerHTML = html;
    var tiles = document.getElementById('po-pattern-tiles');
    if (tiles) {
      tiles.addEventListener('click', function(e) {
        var tile = e.target.closest('.rating-tile');
        if (!tile) return;
        var k = tile.getAttribute('data-pattern');
        if (k) poTogglePattern(k);
      });
    }
    var hdr = document.getElementById('po-col-header-row');
    if (hdr) {
      hdr.addEventListener('click', function(e) {
        var th = e.target.closest('th');
        if (!th) return;
        var key = th.getAttribute('data-sort-key');
        if (key) poOnSort(key);
      });
    }
    return true;
  }

  function renderPostIndicators() {
    if (!poBuildScaffold()) return;
    poBuildHeaderRow();
    poRenderRows();
  }
  window.renderPostIndicators = renderPostIndicators;

})();

/* MD-V2-POST-INDICATORS-MARKER-END */
