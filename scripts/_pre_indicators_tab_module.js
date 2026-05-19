// =============================================================================
// PRE-INDICATORS TAB MODULE - Master Dashboard V2
// =============================================================================
// MD-V2-PRE-INDICATORS-MARKER - idempotency marker for patcher detection
//
// Pre-indicators = 3 leading binary patterns from _md_v2_screens.py.
// Each pattern is computed in Python as an AND of constituent tests; this
// module surfaces EACH TEST as its own tick column.
//
// PATTERNS AND THEIR CONSTITUENT TESTS:
//   Pullback to retest (3 tests):
//     - S2 uptrend (Stage 2 = Probable/Plausible)
//     - Pullback 5-25%
//     - Price > 200D MA
//   Basing below recent high (3 tests):
//     - S2 uptrend
//     - Pullback >= 15%
//     - Price < swing high
//   Collapsing (2 tests):
//     - Price <= 70% of 52W high (30%+ below)
//     - Pullback >= 20%
// =============================================================================

/* MD-V2-PRE-INDICATORS-MARKER-START */

(function() {
  'use strict';

  var piState = {
    mode: { inputs: 'pct' },
    scope: 'all',
    patternFilter: null,
    tint: 'none',
    port: 'off',
    sort: { col: 'company', dir: 'asc' }
  };

  // The 3 patterns and the tests that compose each one.
  // testKey values must match keys handled by piEvalTest().
  var PI_PATTERNS = [
    {
      key: 'pullback_to_retest',
      label: 'Pullback',
      tooltip: 'Stock in plausible/probable Stage 2 uptrend, pulled back 5-25% from swing high, still above 200-day moving average',
      tests: [
        { key: 'is_s2_uptrend', label: 'S2 uptrend', tooltip: 'Stage 2 rating = Probable or Plausible' },
        { key: 'in_pullback_range', label: 'Pullback 5-25%', tooltip: 'Recent pullback from swing high is between 5% and 25%' },
        { key: 'above_ma200', label: 'Price > 200D MA', tooltip: 'Current price is above the 200-day moving average' }
      ]
    },
    {
      key: 'basing_below_high',
      label: 'Basing',
      tooltip: 'Stock in plausible/probable Stage 2 uptrend, 15%+ below recent high',
      tests: [
        { key: 'is_s2_uptrend',         label: 'S2 uptrend',     tooltip: 'Stage 2 rating = Probable or Plausible' },
        { key: 'pullback_ge_15',        label: 'Pullback >= 15%', tooltip: 'Recent pullback from swing high is at least 15%' },
        { key: 'price_below_swing_high', label: 'Below swing high', tooltip: 'Current price is below the recent swing high' }
      ]
    },
    {
      key: 'collapsing',
      label: 'Collapsing',
      tooltip: 'Price 30%+ below 52-week high AND stock 20%+ off recent three-month high',
      tests: [
        { key: 'price_le_70pct_52wh', label: 'Price <= 70% of 52W high', tooltip: 'Current price is 30%+ below the 52-week high' },
        { key: 'pullback_ge_20',      label: 'Pullback >= 20%',          tooltip: 'Recent pullback from recent three-month high is at least 20%' }
      ]
    }
  ];

  // Build column list dynamically: inputs + per-pattern test columns
  function buildCols() {
    var cols = [
      { id:'name',     label:'Company - Ticker',        sortKey:'company',         cls:'name-cell' },
      { id:'taxon',    label:'Industry - Sector',       sortKey:'sector',          cls:'taxon' },
      { id:'price',    label:'Price',                   sortKey:'price',           cls:'num' },
      { id:'high_52w', label:'52 week high',            sortKey:'high_52w',        cls:'num' },
      { id:'pullback', label:'Recent pullback',         sortKey:'recent_pullback', cls:'num' },
      { id:'ma_200',   label:'200 day moving average',  sortKey:'ma_200',          cls:'num' }
    ];
    for (var p = 0; p < PI_PATTERNS.length; p++) {
      var pat = PI_PATTERNS[p];
      for (var t = 0; t < pat.tests.length; t++) {
        var test = pat.tests[t];
        var firstInGroup = (t === 0);
        cols.push({
          id: 'p' + (p+1) + 't' + (t+1),
          label: test.label,
          sortKey: pat.key + '__' + test.key,
          cls: firstInGroup ? ('grp-start-g' + (p+1)) : '',
          tooltip: test.tooltip,
          patternKey: pat.key,
          testKey: test.key
        });
      }
    }
    return cols;
  }
  var PI_COLS = buildCols();

  function piPricesLookup() {
    if (window._piPricesByTicker) return window._piPricesByTicker;
    var out = {};
    var arr = (window.MASTER_DATA && MASTER_DATA.prices) || [];
    for (var i = 0; i < arr.length; i++) if (arr[i] && arr[i].ticker) out[arr[i].ticker] = arr[i];
    window._piPricesByTicker = out;
    return out;
  }
  function piLiveTickers() {
    var out = {};
    var inv = (window.MASTER_DATA && MASTER_DATA.positions && MASTER_DATA.positions.investments) || [];
    for (var i = 0; i < inv.length; i++) if (inv[i].ticker) out[inv[i].ticker] = true;
    return out;
  }
  function piLiveSectors() {
    var out = {}, t, prices = piPricesLookup(), tickers = piLiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.sector) out[p.sector] = true; }
    return out;
  }
  function piLiveIndustries() {
    var out = {}, t, prices = piPricesLookup(), tickers = piLiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.industry) out[p.industry] = true; }
    return out;
  }

  // Evaluate a single test against a row.
  // Mirrors the boolean logic in _md_v2_screens.py.
  function piEvalTest(row, testKey) {
    var p = row;
    if (testKey === 'is_s2_uptrend') {
      var r = (row.md_v2 && row.md_v2.stage_2 && row.md_v2.stage_2.rating);
      return r === 'Probable' || r === 'Plausible';
    }
    if (testKey === 'in_pullback_range') {
      return p.recent_pullback != null && p.recent_pullback >= 0.05 && p.recent_pullback <= 0.25;
    }
    if (testKey === 'above_ma200') {
      return p.price != null && p.ma_200 != null && p.price > p.ma_200;
    }
    if (testKey === 'pullback_ge_15') {
      return p.recent_pullback != null && p.recent_pullback >= 0.15;
    }
    if (testKey === 'price_below_swing_high') {
      return p.price != null && p.swing_high != null && p.price < p.swing_high;
    }
    if (testKey === 'price_le_70pct_52wh') {
      return p.price != null && p.high_52w != null && p.high_52w > 0 && p.price <= p.high_52w * 0.70;
    }
    if (testKey === 'pullback_ge_20') {
      return p.recent_pullback != null && p.recent_pullback >= 0.20;
    }
    return false;
  }

  function piGetRows() {
    var raw = (window.MASTER_DATA && MASTER_DATA.filters) || [];
    var prices = piPricesLookup();
    var live = piLiveTickers(), liveS = piLiveSectors(), liveI = piLiveIndustries();
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
        price: p.price, high_52w: p.high_52w,
        recent_pullback: p.recent_pullback_pct,
        swing_high: p.swing_high,
        ma_150: mas['150D'], ma_200: mas['200D'],
        indicators: ind,
        md_v2: s.md_v2,
        is_live: !!live[s.ticker],
        sector_in_portfolio: !!liveS[p.sector],
        industry_in_portfolio: !!liveI[p.industry]
      });
    }
    return rows;
  }
  function piPatternCounts(rows) {
    var c = { 'pullback_to_retest':0, 'basing_below_high':0, 'collapsing':0 };
    for (var i = 0; i < rows.length; i++) {
      var ind = rows[i].indicators || {};
      for (var k in c) if (ind[k]) c[k]++;
    }
    return c;
  }

  function piFmtNum(n) {
    if (n == null || isNaN(n)) return '-';
    var abs = Math.abs(n);
    var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);
    var f = abs.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });
    return n < 0 ? '(' + f + ')' : f;
  }
  function piFmtPct(p) {
    if (p == null || isNaN(p)) return '-';
    var r = Math.round(p), abs = Math.abs(r);
    return r < 0 ? '(' + abs + ')%' : r + '%';
  }
  function piColourForIntensity(i) {
    if (i >= 0.6) return '#0F6E56';
    if (i >= 0.25) return '#1D9E75';
    if (i >= 0.05) return '#5DCAA5';
    if (i <= -0.6) return '#A32D2D';
    if (i <= -0.25) return '#E24B4A';
    if (i <= -0.05) return '#F09595';
    return '#888';
  }
  function piInputCell(row, key, extraCls) {
    extraCls = extraCls || '';
    var v = row[key];
    if (key === 'price') return '<td class="num ' + extraCls + '">' + piFmtNum(v) + '</td>';
    if (key === 'recent_pullback') {
      if (v == null || isNaN(v)) return '<td class="num ' + extraCls + '">-</td>';
      var pctVal = v * 100;
      var pi_intensity = Math.max(-1, Math.min(1, (pctVal - 5) / 20));
      var col = piColourForIntensity(-pi_intensity);
      return '<td class="num ' + extraCls + '" style="color:' + col + '">' + Math.round(pctVal) + '%</td>';
    }
    if (v == null || row.price == null) return '<td class="num ' + extraCls + '">-</td>';
    var pct = (row.price - v) / v * 100;
    var intensity = 0;
    if (key === 'high_52w') intensity = Math.max(-1, Math.min(1, (-pct - 5) / 20));
    else if (key === 'ma_150' || key === 'ma_200') intensity = Math.max(-1, Math.min(1, pct / 10));
    var colour = piColourForIntensity(intensity);
    var text = (piState.mode.inputs === 'pct') ? piFmtPct(pct) : piFmtNum(v);
    return '<td class="num ' + extraCls + '" style="color:' + colour + '">' + text + '</td>';
  }

  function piTestCell(row, col) {
    var pass = piEvalTest(row, col.testKey);
    var extra = col.cls || '';
    if (pass) return '<td class="pi-pass ' + extra + '"><span class="tick">' + String.fromCharCode(10003) + '</span></td>';
    return '<td class="pi-fail ' + extra + '">.</td>';
  }

  function piHashColor(label, alpha) {
    if (!label) return null;
    var h = 0;
    for (var i = 0; i < label.length; i++) h = (h * 31 + label.charCodeAt(i)) & 0xffff;
    return 'hsla(' + (h % 360) + ', 35%, 55%, ' + alpha + ')';
  }
  function piPortfolioInfo(row) {
    if (row.is_live) return { color:'#1b5e20', bg:'rgba(27,94,32,0.10)', bgHover:'rgba(27,94,32,0.14)' };
    if (row.sector_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.05)', bgHover:'rgba(27,94,32,0.08)' };
    if (row.industry_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.025)', bgHover:'rgba(27,94,32,0.05)' };
    return null;
  }

  function piGetSortVal(row, key) {
    // pattern__test sort keys
    if (key.indexOf('__') > 0) {
      var parts = key.split('__');
      return piEvalTest(row, parts[1]) ? 1 : 0;
    }
    if (key === 'recent_pullback') {
      return row.recent_pullback == null ? -Infinity : row.recent_pullback;
    }
    var PCT_KEYS = ['high_52w','ma_150','ma_200'];
    if (PCT_KEYS.indexOf(key) > -1 && piState.mode.inputs === 'pct') {
      var ref = row[key];
      if (ref == null || row.price == null || ref === 0) return -Infinity;
      return (row.price - ref) / ref * 100;
    }
    if (key in row) return row[key];
    return 0;
  }
  function piOnSort(key) {
    if (piState.sort.col === key) piState.sort.dir = piState.sort.dir === 'desc' ? 'asc' : 'desc';
    else piState.sort = { col: key, dir: key === 'company' ? 'asc' : 'desc' };
    piBuildHeaderRow();
    piRenderRows();
  }

  function piBuildHeaderRow() {
    var tr = document.getElementById('pi-col-header-row');
    if (!tr) return;
    var h = '';
    for (var i = 0; i < PI_COLS.length; i++) {
      var c = PI_COLS[i];
      var isSort = piState.sort.col === c.sortKey;
      var arrow = isSort
        ? '<span class="sort-arrow">' + (piState.sort.dir === 'desc' ? String.fromCharCode(9660) : String.fromCharCode(9650)) + '</span>'
        : '<span class="sort-placeholder"></span>';
      var title = c.tooltip || c.label;
      h += '<th class="' + (c.cls || '') + '" data-sort-key="' + c.sortKey + '" title="' + title + '">' +
           '<span class="hd"><span class="lbl">' + c.label + '</span>' + arrow + '</span></th>';
    }
    tr.innerHTML = h;
  }

  function piPatternTiles(rows) {
    var tiles = document.getElementById('pi-pattern-tiles');
    if (!tiles) return;
    var counts = piPatternCounts(rows);
    var total = rows.length;
    var stripCls = { 'pullback_to_retest':'pi-strip-pullback', 'basing_below_high':'pi-strip-basing', 'collapsing':'pi-strip-collapsing' };
    var tintCls  = { 'pullback_to_retest':'pi-tile-pullback', 'basing_below_high':'pi-tile-basing', 'collapsing':'pi-tile-collapsing' };
    var h = '';
    for (var i = 0; i < PI_PATTERNS.length; i++) {
      var pat = PI_PATTERNS[i];
      var cnt = counts[pat.key] || 0;
      var act = piState.patternFilter === pat.key ? ' active' : '';
      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;
      h += '<div class="rating-tile ' + tintCls[pat.key] + act + '" data-pattern="' + pat.key + '" title="' + pat.tooltip + '">' +
           '<div class="rt-label">' + pat.label + '</div>' +
           '<div class="rt-count">' + cnt.toLocaleString('en-GB') + '</div>' +
           '<div class="rt-sub">of ' + total.toLocaleString('en-GB') + ' . ' + pct + '%</div>' +
           '<div class="rt-strip ' + stripCls[pat.key] + '"></div>' +
           '</div>';
    }
    tiles.innerHTML = h;
  }

  function piUpdateScopeCounts(rows) {
    function set(id, n) { var el = document.getElementById(id); if (el) el.textContent = '(' + n + ')'; }
    set('pi-cnt-all',      rows.length);
    set('pi-cnt-live',     rows.filter(function(r){ return r.is_live; }).length);
    set('pi-cnt-sector',   rows.filter(function(r){ return r.sector_in_portfolio; }).length);
    set('pi-cnt-industry', rows.filter(function(r){ return r.industry_in_portfolio; }).length);
  }

  function piRenderRows() {
    var tbody = document.getElementById('pi-tbody');
    if (!tbody) return;
    var all = piGetRows();
    piUpdateScopeCounts(all);
    piPatternTiles(all);
    var rows = all.slice();
    if (piState.scope === 'live') rows = rows.filter(function(r){ return r.is_live; });
    else if (piState.scope === 'sector') rows = rows.filter(function(r){ return r.sector_in_portfolio; });
    else if (piState.scope === 'industry') rows = rows.filter(function(r){ return r.industry_in_portfolio; });
    if (piState.patternFilter) {
      var key = piState.patternFilter;
      rows = rows.filter(function(r){ return !!(r.indicators || {})[key]; });
    }
    rows.sort(function(a,b) {
      var va = piGetSortVal(a, piState.sort.col), vb = piGetSortVal(b, piState.sort.col);
      var cmp = (typeof va === 'string') ? va.localeCompare(vb) : (va || 0) - (vb || 0);
      if (cmp === 0) cmp = a.ticker.localeCompare(b.ticker);
      return piState.sort.dir === 'desc' ? -cmp : cmp;
    });
    var html = '';
    for (var i = 0; i < rows.length; i++) {
      var s = rows[i];
      var styles = [], cls = [];
      if (piState.tint === 'industry') { styles.push('--tint-bg: ' + piHashColor(s.industry, 0.16)); cls.push('tint-row'); }
      else if (piState.tint === 'sector') { styles.push('--tint-bg: ' + piHashColor(s.sector, 0.16)); cls.push('tint-row'); }
      if (piState.port === 'on') {
        var pi = piPortfolioInfo(s);
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
        piInputCell(s, 'price') + piInputCell(s, 'high_52w') + piInputCell(s, 'recent_pullback') +
        piInputCell(s, 'ma_200');
      // Per-test tick columns
      for (var j = 6; j < PI_COLS.length; j++) html += piTestCell(s, PI_COLS[j]);
      html += '</tr>';
    }
    tbody.innerHTML = html;
  }

  function piSetMode(kind, val) {
    piState.mode[kind] = val;
    var btns = document.querySelectorAll('button[data-pi-grp="' + kind + '"]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-pi-val') === val);
    piRenderRows();
  }
  function piSetScope(s) {
    piState.scope = s;
    var btns = document.querySelectorAll('button[data-pi-scope]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-pi-scope') === s);
    piRenderRows();
  }
  function piSetTint(t) {
    piState.tint = t;
    var btns = document.querySelectorAll('button[data-pi-tint]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-pi-tint') === t);
    piRenderRows();
  }
  function piSetPort(p) {
    piState.port = p;
    var btns = document.querySelectorAll('button[data-pi-port]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-pi-port') === p);
    piRenderRows();
  }
  function piTogglePattern(k) {
    piState.patternFilter = (piState.patternFilter === k) ? null : k;
    piRenderRows();
  }
  window.piSetMode = piSetMode;
  window.piSetScope = piSetScope;
  window.piSetTint = piSetTint;
  window.piSetPort = piSetPort;
  window.piTogglePattern = piTogglePattern;
  window.piOnSort = piOnSort;

  function piBuildScaffold() {
    var host = document.getElementById('tab-pre_indicators');
    if (!host) return false;
    if (host.querySelector('#pi-main-table')) return true;

    // Build dynamic colgroup + group header colspans
    var colgroupHtml = '<col class="c-name"><col class="c-taxon">' +
                      '<col class="c-price"><col class="c-52wh"><col class="c-pullback"><col class="c-ma200">';
    var inputsColspan = 6;
    var groupHeaderHtml = '<th class="gh-inputs" colspan="' + inputsColspan + '">Inputs</th>';
    for (var p = 0; p < PI_PATTERNS.length; p++) {
      var pat = PI_PATTERNS[p];
      var n = pat.tests.length;
      for (var t = 0; t < n; t++) colgroupHtml += '<col class="c-test">';
      var startCls = 'grp-start-g' + (p+1);
      var endCls = 'grp-end-g' + (p+1);
      groupHeaderHtml += '<th class="gh-g' + (p+1) + ' ' + startCls + ' ' + endCls + '" colspan="' + n + '">' + pat.label + '</th>';
    }

    var html = '' +
      '<div class="s1-intro">Pre-indicators are three leading binary patterns drawn directly from price and stage data. Each pattern is the AND of two or three constituent tests, shown below as individual tick columns. Pullback (Stage 2 uptrend + pullback 5-25% + price above 200-day MA), Basing (Stage 2 uptrend + pullback >=15% + price below recent swing high), and Collapsing (price >=30% below 52-week high + pullback >=20%). Click a tile to filter the table to the parent pattern; click again to clear.</div>' +
      '<div class="controls s1-controls">' +
        '<div class="ctrl-grp"><span class="ctrl-label">Inputs</span>' +
          '<button class="toggle-btn active" data-pi-grp="inputs" data-pi-val="pct" onclick="piSetMode(\'inputs\',\'pct\')">show as %</button>' +
          '<button class="toggle-btn" data-pi-grp="inputs" data-pi-val="raw" onclick="piSetMode(\'inputs\',\'raw\')">show as numbers</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Scope</span>' +
          '<button class="toggle-btn active" data-pi-scope="all" onclick="piSetScope(\'all\')">All <span id="pi-cnt-all"></span></button>' +
          '<button class="toggle-btn" data-pi-scope="live" onclick="piSetScope(\'live\')">Live <span id="pi-cnt-live"></span></button>' +
          '<button class="toggle-btn" data-pi-scope="sector" onclick="piSetScope(\'sector\')">Sectors <span id="pi-cnt-sector"></span></button>' +
          '<button class="toggle-btn" data-pi-scope="industry" onclick="piSetScope(\'industry\')">Industries <span id="pi-cnt-industry"></span></button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Peers</button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Cohorts</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Colour by</span>' +
          '<button class="toggle-btn active" data-pi-tint="none" onclick="piSetTint(\'none\')">Off</button>' +
          '<button class="toggle-btn" data-pi-tint="industry" onclick="piSetTint(\'industry\')">Industry</button>' +
          '<button class="toggle-btn" data-pi-tint="sector" onclick="piSetTint(\'sector\')">Sector</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Portfolio tint</span>' +
          '<button class="toggle-btn active" data-pi-port="off" onclick="piSetPort(\'off\')">Off</button>' +
          '<button class="toggle-btn" data-pi-port="on" onclick="piSetPort(\'on\')">On</button>' +
        '</div>' +
      '</div>' +
      '<div class="rating-tiles s1-rating-tiles" id="pi-pattern-tiles"></div>' +
      '<div class="group-captions">' +
        '<div class="gcap gcap-g1"><b>Pullback to retest</b>Stock in plausible/probable Stage 2 uptrend, recently pulled back 5-25% from its swing high, still above its 200-day moving average. Three tests: S2 uptrend AND pullback range AND above 200-day MA.</div>' +
        '<div class="gcap gcap-g2"><b>Basing below recent high</b>Stock in plausible/probable Stage 2 uptrend but 15%+ below recent swing high. Three tests: S2 uptrend AND pullback >=15% AND price below swing high.</div>' +
        '<div class="gcap gcap-g3"><b>Collapsing</b>Price 30%+ below its 52-week high AND stock 20%+ off its recent three-month high. Two tests: price <=70% of 52W high AND pullback >=20%.</div>' +
      '</div>' +
      '<div class="table-wrap">' +
        '<table class="data-table" id="pi-main-table">' +
          '<colgroup>' + colgroupHtml + '</colgroup>' +
          '<thead>' +
            '<tr class="group-header-row">' + groupHeaderHtml + '</tr>' +
            '<tr class="col-header-row" id="pi-col-header-row"></tr>' +
          '</thead>' +
          '<tbody id="pi-tbody"></tbody>' +
        '</table>' +
      '</div>';
    host.innerHTML = html;
    var tiles = document.getElementById('pi-pattern-tiles');
    if (tiles) {
      tiles.addEventListener('click', function(e) {
        var tile = e.target.closest('.rating-tile');
        if (!tile) return;
        var k = tile.getAttribute('data-pattern');
        if (k) piTogglePattern(k);
      });
    }
    var hdr = document.getElementById('pi-col-header-row');
    if (hdr) {
      hdr.addEventListener('click', function(e) {
        var th = e.target.closest('th');
        if (!th) return;
        var key = th.getAttribute('data-sort-key');
        if (key) piOnSort(key);
      });
    }
    return true;
  }

  function renderPreIndicators() {
    if (!piBuildScaffold()) return;
    piBuildHeaderRow();
    piRenderRows();
  }
  window.renderPreIndicators = renderPreIndicators;

})();

/* MD-V2-PRE-INDICATORS-MARKER-END */
