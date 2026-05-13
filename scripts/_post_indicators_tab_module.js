// =============================================================================
// POST-INDICATORS TAB MODULE — Master Dashboard V2
// =============================================================================
// MD-V2-POST-INDICATORS-MARKER — idempotency marker for patcher detection
//
// Post-indicators = 5 trailing binary patterns from _md_v2_screens.py:
//   Bullish pair (teal palette):
//     1. Breakout          (breakout)
//     2. Advancing         (advancing)
//   Bearish trio (red palette):
//     3. Breakdown 50D     (breakdown_50D)
//     4. Breakdown 150D    (breakdown_150D)
//     5. Breakdown 200D    (breakdown_200D)
//
// Option B layout (Richard's choice 13-May-26):
//   - Top row = 5 tiles, one per pattern, with count + plain-English caption
//   - Click a tile → table filters to stocks with that pattern
//   - Click again → clear filter
//   - Table shows ONE COLUMN PER PATTERN with tick/no-tick — no aggregate score column
//   - Default sort: Company name ascending
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
    { key: 'breakout',       label: 'Breakout',       sign: 'bull', tooltip: 'Price > 1.08x 5-day moving average AND up-volume > 1.10x down-volume' },
    { key: 'advancing',      label: 'Advancing',      sign: 'bull', tooltip: 'Price above rising 20-day MA, no breakout-spike — catch-all positive trend' },
    { key: 'breakdown_50D',  label: 'Breakdown 50D',  sign: 'bear', tooltip: 'Price has crossed below its 50-day moving average from above' },
    { key: 'breakdown_150D', label: 'Breakdown 150D', sign: 'bear', tooltip: 'Price has crossed below its 150-day moving average from above' },
    { key: 'breakdown_200D', label: 'Breakdown 200D', sign: 'bear', tooltip: 'Price has crossed below its 200-day moving average from above' }
  ];

  var PO_COLS = [
    { id:'name',     label:'Company · Ticker',          sortKey:'company',          cls:'name-cell' },
    { id:'taxon',    label:'Industry · Sector',         sortKey:'sector',           cls:'taxon' },
    { id:'price',    label:'Price',                     sortKey:'price',            cls:'num' },
    { id:'ma_5',     label:'5 day moving average',      sortKey:'ma_5',             cls:'num' },
    { id:'ma_20',    label:'20 day moving average',     sortKey:'ma_20',            cls:'num' },
    { id:'ma_50',    label:'50 day moving average',     sortKey:'ma_50',            cls:'num' },
    { id:'ma_150',   label:'150 day moving average',    sortKey:'ma_150',           cls:'num' },
    { id:'ma_200',   label:'200 day moving average',    sortKey:'ma_200',           cls:'num' },
    { id:'p1',       label:'Breakout',                  sortKey:'p1',               cls:'grp-start-g1', patternKey:'breakout' },
    { id:'p2',       label:'Advancing',                 sortKey:'p2',               cls:'grp-end-g1',   patternKey:'advancing' },
    { id:'p3',       label:'Breakdown 50D',             sortKey:'p3',               cls:'grp-start-g2', patternKey:'breakdown_50D' },
    { id:'p4',       label:'Breakdown 150D',            sortKey:'p4',               cls:'',             patternKey:'breakdown_150D' },
    { id:'p5',       label:'Breakdown 200D',            sortKey:'p5',               cls:'grp-end-g2',   patternKey:'breakdown_200D' }
  ];

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
        ma_5: mas['5D'], ma_20: mas['20D'], ma_50: mas['50D'], ma_150: mas['150D'], ma_200: mas['200D'],
        indicators: ind,
        p1: ind.breakout       ? 1 : 0,
        p2: ind.advancing      ? 1 : 0,
        p3: ind.breakdown_50D  ? 1 : 0,
        p4: ind.breakdown_150D ? 1 : 0,
        p5: ind.breakdown_200D ? 1 : 0,
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
    if (n == null || isNaN(n)) return '—';
    var abs = Math.abs(n);
    var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);
    var f = abs.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });
    return n < 0 ? '(' + f + ')' : f;
  }
  function poFmtPct(p) {
    if (p == null || isNaN(p)) return '—';
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
    if (v == null || row.price == null) return '<td class="num ' + extraCls + '">—</td>';
    var pct = (row.price - v) / v * 100;
    // For all MA columns: price > MA is bullish (positive intensity = teal)
    var intensity = Math.max(-1, Math.min(1, pct / 10));
    var colour = poColourForIntensity(intensity);
    var text = (poState.mode.inputs === 'pct') ? poFmtPct(pct) : poFmtNum(v);
    return '<td class="num ' + extraCls + '" style="color:' + colour + '">' + text + '</td>';
  }

  function poPatternCell(row, col) {
    var pass = !!(row.indicators || {})[col.patternKey];
    var extra = col.cls || '';
    // Determine if this pattern is bullish or bearish for the colour
    var pat = PO_PATTERNS.find(function(p){ return p.key === col.patternKey; });
    var sign = pat ? pat.sign : 'bull';
    if (pass) {
      var cls = sign === 'bull' ? 'po-pass-bull' : 'po-pass-bear';
      return '<td class="' + cls + ' ' + extra + '"><span class="tick">✓</span></td>';
    }
    return '<td class="po-fail ' + extra + '">·</td>';
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
    if (key.indexOf('p') === 0 && key.length === 2) return row[key] || 0;
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
        ? '<span class="sort-arrow">' + (poState.sort.dir === 'desc' ? '▼' : '▲') + '</span>'
        : '<span class="sort-placeholder"></span>';
      h += '<th class="' + (c.cls || '') + '" data-sort-key="' + c.sortKey + '" title="' + c.label + '">' +
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
           '<div class="rt-sub">of ' + total.toLocaleString('en-GB') + ' · ' + pct + '%</div>' +
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
      var liveDot = s.is_live ? '<span class="live-dot">●</span>' : '';
      html += '<tr' + clsAttr + styleAttr + '>' +
        '<td class="name-cell"><div class="co">' + liveDot + (s.company || s.ticker) + '</div><div class="tk">' + s.ticker + '</div></td>' +
        '<td class="taxon"><div class="ind">' + (s.industry || '') + '</div><div class="sec">' + (s.sector || '') + '</div></td>' +
        poInputCell(s, 'price') + poInputCell(s, 'ma_5') + poInputCell(s, 'ma_20') +
        poInputCell(s, 'ma_50') + poInputCell(s, 'ma_150') + poInputCell(s, 'ma_200');
      // Per-pattern tick columns
      for (var j = 8; j <= 12; j++) html += poPatternCell(s, PO_COLS[j]);
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
    var html = '' +
      '<div class="s1-intro">Post-indicators are five trailing binary patterns drawn from price and moving-average data. The first two are bullish: Breakout (price > 1.08x the 5-day moving average AND up-volume > 1.10x down-volume) and Advancing (price above a rising 20-day moving average, no breakout spike). The remaining three are bearish: Breakdown through the 50-day / 150-day / 200-day moving averages (price has crossed below the respective MA from above). Each tile below shows the count of stocks with that pattern. Click a tile to filter the table; click again to clear.</div>' +
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
        '<div class="gcap gcap-g1"><b>Breakout</b>Price > 1.08x the 5-day moving average AND up-volume > 1.10x down-volume. Pattern points to a fresh momentum push - typically the trigger for capital deployment when other conditions align.</div>' +
        '<div class="gcap gcap-g1"><b>Advancing</b>Price above a rising 20-day moving average, without breakout-spike. Catch-all positive-trend pattern - the stock is moving up quietly rather than via a sharp breakout.</div>' +
        '<div class="gcap gcap-g2"><b>Breakdown 50D</b>Price has crossed below its 50-day moving average from above. Earliest of the three breakdown signals - watch as warning sign for short-term loss of trend.</div>' +
        '<div class="gcap gcap-g2"><b>Breakdown 150D</b>Price has crossed below its 150-day moving average. Medium-term trend has broken - typically a more serious signal than the 50-day breakdown.</div>' +
        '<div class="gcap gcap-g2"><b>Breakdown 200D</b>Price has crossed below its 200-day moving average. Long-term trend has broken - the most significant of the three breakdowns.</div>' +
      '</div>' +
      '<div class="table-wrap">' +
        '<table class="data-table" id="po-main-table">' +
          '<colgroup>' +
            '<col class="c-name"><col class="c-taxon">' +
            '<col class="c-price"><col class="c-ma"><col class="c-ma"><col class="c-ma"><col class="c-ma"><col class="c-ma">' +
            '<col class="c-pattern"><col class="c-pattern">' +
            '<col class="c-pattern"><col class="c-pattern"><col class="c-pattern">' +
          '</colgroup>' +
          '<thead>' +
            '<tr class="group-header-row">' +
              '<th class="gh-inputs" colspan="8">Inputs</th>' +
              '<th class="gh-g1 grp-start-g1 grp-end-g1" colspan="2">Bullish post-indicators</th>' +
              '<th class="gh-g2 grp-start-g2 grp-end-g2" colspan="3">Bearish post-indicators</th>' +
            '</tr>' +
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
