// =============================================================================
// PRE-INDICATORS TAB MODULE — Master Dashboard V2
// =============================================================================
// MD-V2-PRE-INDICATORS-MARKER — idempotency marker for patcher detection
//
// Pre-indicators = 3 leading binary patterns from _md_v2_screens.py:
//   1. Pullback to retest         (pullback_to_retest)
//   2. Basing below recent high   (basing_below_high)
//   3. Collapsing                 (collapsing)
//
// Tab uses Option B (Richard's choice, 13-May-26):
//   - Top row = 3 tiles, one per pattern, with count + plain-English caption
//   - Click a tile → table filters to stocks with that pattern
//   - Click again → clear filter
//   - Table shows 3 tick columns + 0/3 score column
// =============================================================================

/* MD-V2-PRE-INDICATORS-MARKER-START */

(function() {
  'use strict';

  var piState = {
    mode: { inputs: 'pct' },
    scope: 'all',
    patternFilter: null,  // null | 'pullback_to_retest' | 'basing_below_high' | 'collapsing'
    tint: 'none',
    port: 'off',
    sort: { col: 'count', dir: 'desc' }
  };

  // The 3 patterns. Order = pullback, basing, collapsing (per _md_v2_screens.py order).
  var PI_PATTERNS = [
    { key: 'pullback_to_retest',  label: 'Pullback',   tooltip: 'Stock in S2 uptrend, pulled back 5-25% from swing high, still above 200D MA' },
    { key: 'basing_below_high',   label: 'Basing',     tooltip: 'Stock in S2 uptrend, ≥15% below recent high, still in plausible/probable S2' },
    { key: 'collapsing',          label: 'Collapsing', tooltip: 'Price ≥30% below 52W high AND ≥20% off recent 3M high (irrespective of stage)' }
  ];

  var PI_COLS = [
    { id:'name',     label:'Company · Ticker',          sortKey:'company',   cls:'name-cell' },
    { id:'taxon',    label:'Industry · Sector',         sortKey:'sector',    cls:'taxon' },
    { id:'price',    label:'Price',                     sortKey:'price',     cls:'num' },
    { id:'high_52w', label:'52 week high',              sortKey:'high_52w',  cls:'num' },
    { id:'pullback', label:'Recent pullback',           sortKey:'recent_pullback', cls:'num' },
    { id:'ma_150',   label:'150 day moving average',    sortKey:'ma_150',    cls:'num' },
    { id:'ma_200',   label:'200 day moving average',    sortKey:'ma_200',    cls:'num' },
    { id:'count',    label:'Patterns 0/3',              sortKey:'count',     cls:'grp-start-rating' },
    { id:'p1',       label:'Pullback',                  sortKey:'p1',        cls:'grp-start-g1 grp-end-g1', patternKey:'pullback_to_retest' },
    { id:'p2',       label:'Basing',                    sortKey:'p2',        cls:'grp-start-g2 grp-end-g2', patternKey:'basing_below_high' },
    { id:'p3',       label:'Collapsing',                sortKey:'p3',        cls:'grp-start-g3 grp-end-g3', patternKey:'collapsing' }
  ];

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
      var count = 0;
      for (var k = 0; k < PI_PATTERNS.length; k++) if (ind[PI_PATTERNS[k].key]) count++;
      rows.push({
        ticker: s.ticker, company: p.company_name || s.ticker,
        sector: p.sector || '', industry: p.industry || '',
        price: p.price, high_52w: p.high_52w,
        recent_pullback: p.recent_pullback_pct,
        ma_150: mas['150D'], ma_200: mas['200D'],
        indicators: ind, count: count,
        p1: ind.pullback_to_retest ? 1 : 0,
        p2: ind.basing_below_high  ? 1 : 0,
        p3: ind.collapsing          ? 1 : 0,
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
    if (n == null || isNaN(n)) return '—';
    var abs = Math.abs(n);
    var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);
    var f = abs.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });
    return n < 0 ? '(' + f + ')' : f;
  }
  function piFmtPct(p) {
    if (p == null || isNaN(p)) return '—';
    var r = Math.round(p), abs = Math.abs(r);
    return r < 0 ? '(' + abs + ')%' : r + '%';
  }
  // Teal colour ramp (Pre-indicators)
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
      if (v == null || isNaN(v)) return '<td class="num ' + extraCls + '">—</td>';
      var pctVal = v * 100;
      var pi_intensity = Math.max(-1, Math.min(1, (pctVal - 5) / 20));
      var col = piColourForIntensity(-pi_intensity);  // larger pullback = warmer
      return '<td class="num ' + extraCls + '" style="color:' + col + '">' + Math.round(pctVal) + '%</td>';
    }
    if (v == null || row.price == null) return '<td class="num ' + extraCls + '">—</td>';
    var pct = (row.price - v) / v * 100;
    var intensity = 0;
    if (key === 'high_52w') intensity = Math.max(-1, Math.min(1, (-pct - 5) / 20));   // below high — slight bearish tilt
    else if (key === 'ma_150' || key === 'ma_200') intensity = Math.max(-1, Math.min(1, pct / 10));  // above MA = bullish
    var colour = piColourForIntensity(intensity);
    var text = (piState.mode.inputs === 'pct') ? piFmtPct(pct) : piFmtNum(v);
    return '<td class="num ' + extraCls + '" style="color:' + colour + '">' + text + '</td>';
  }

  function piPatternCell(row, col) {
    var pass = !!(row.indicators || {})[col.patternKey];
    var extra = col.cls || '';
    if (pass) return '<td class="pi-pass ' + extra + '"><span class="tick">✓</span></td>';
    return '<td class="pi-fail ' + extra + '">·</td>';
  }

  function piScorePips(row) {
    var passed = [row.p1, row.p2, row.p3];
    var count = passed.filter(Boolean).length;
    var s = '';
    for (var i = 0; i < 3; i++) s += '<span class="pip pip-pi ' + (passed[i] ? 'on' : '') + '"></span>';
    var pillCls = count === 0 ? 'pi-count-0' : (count === 1 ? 'pi-count-1' : (count === 2 ? 'pi-count-2' : 'pi-count-3'));
    return '<div class="score-pip-row"><span class="pi-count-pill ' + pillCls + '">' + count + '/3</span>' + s + '</div>';
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
    if (key === 'count') return row.count || 0;
    if (key === 'p1' || key === 'p2' || key === 'p3') return row[key] || 0;
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
    else piState.sort = { col: key, dir: 'desc' };
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
        ? '<span class="sort-arrow">' + (piState.sort.dir === 'desc' ? '▼' : '▲') + '</span>'
        : '<span class="sort-placeholder"></span>';
      h += '<th class="' + (c.cls || '') + '" data-sort-key="' + c.sortKey + '" title="' + c.label + '">' +
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
           '<div class="rt-sub">of ' + total.toLocaleString('en-GB') + ' · ' + pct + '%</div>' +
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
      var liveDot = s.is_live ? '<span class="live-dot">●</span>' : '';
      html += '<tr' + clsAttr + styleAttr + '>' +
        '<td class="name-cell"><div class="co">' + liveDot + (s.company || s.ticker) + '</div><div class="tk">' + s.ticker + '</div></td>' +
        '<td class="taxon"><div class="ind">' + (s.industry || '') + '</div><div class="sec">' + (s.sector || '') + '</div></td>' +
        piInputCell(s, 'price') + piInputCell(s, 'high_52w') + piInputCell(s, 'recent_pullback') +
        piInputCell(s, 'ma_150') + piInputCell(s, 'ma_200') +
        '<td class="grp-start-rating">' + piScorePips(s) + '</td>';
      for (var j = 8; j <= 10; j++) html += piPatternCell(s, PI_COLS[j]);
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
    var html = '' +
      '<div class="s1-intro">Pre-indicators are three leading binary patterns drawn directly from price and stage data: Pullback (stock in an established uptrend, pulled back 5-25% from its swing high, still above its 200-day moving average), Basing (stock in an uptrend but ≥15% below its recent high, still in a plausible/probable Stage 2), and Collapsing (price ≥30% below its 52-week high AND ≥20% off its recent three-month high). Each tile below shows the count of stocks with that pattern. Click a tile to filter the table to just those stocks; click again to clear.</div>' +
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
      '<div class="rating-tiles s1-rating-tiles" id="pi-pattern-tiles" style="grid-template-columns: repeat(3, 1fr);"></div>' +
      '<div class="group-captions" style="grid-template-columns: repeat(3, 1fr);">' +
        '<div class="gcap gcap-g1"><b>Pullback to retest</b>Stock in plausible/probable Stage 2 uptrend, recently pulled back 5-25% from its swing high, still above its 200-day moving average. Pattern points to a healthy correction inside an established uptrend - the classic buy-the-dip setup.</div>' +
        '<div class="gcap gcap-g2"><b>Basing below recent high</b>Stock in plausible/probable Stage 2 uptrend but ≥15% below its recent swing high. Pattern points to a deeper consolidation while the broader uptrend remains intact - watch for a base completing.</div>' +
        '<div class="gcap gcap-g3"><b>Collapsing</b>Price ≥30% below its 52-week high AND the stock has fallen ≥20% from its recent three-month high. Pattern points to capitulation - irrespective of stage. Of interest as a potential probing-bet rebound candidate.</div>' +
      '</div>' +
      '<div class="table-wrap">' +
        '<table class="data-table" id="pi-main-table">' +
          '<colgroup>' +
            '<col class="c-name"><col class="c-taxon">' +
            '<col class="c-price"><col class="c-52wh"><col class="c-pullback">' +
            '<col class="c-ma150"><col class="c-ma200">' +
            '<col class="c-score">' +
            '<col class="c-pattern"><col class="c-pattern"><col class="c-pattern">' +
          '</colgroup>' +
          '<thead>' +
            '<tr class="group-header-row">' +
              '<th class="gh-inputs" colspan="7">Inputs</th>' +
              '<th class="gh-rating grp-start-rating" colspan="1">Patterns 0/3</th>' +
              '<th class="gh-g1 grp-start-g1 grp-end-g1" colspan="1">Pullback to retest</th>' +
              '<th class="gh-g2 grp-start-g2 grp-end-g2" colspan="1">Basing below high</th>' +
              '<th class="gh-g3 grp-start-g3 grp-end-g3" colspan="1">Collapsing</th>' +
            '</tr>' +
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
