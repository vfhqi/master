// =============================================================================
// STAGE 2 TAB MODULE — Master Dashboard V2
// =============================================================================
// MD-V2-STAGE2-MARKER — idempotency marker for patcher detection
//
// Stage 2 = Confirmed uptrend. 10 tests across 5 groups.
// Ratings: None (<5) / Possible (5) / Plausible (6) / Probable (7+).
// =============================================================================

/* MD-V2-STAGE2-MARKER-START */

(function() {
  'use strict';

  var s2State = {
    mode: { inputs: 'pct', tests: 'tick' },
    scope: 'all', ratingFilter: null, tint: 'none', port: 'off',
    sort: { col: 'count', dir: 'desc' }
  };

  var S2_COLS = [
    { id:'name',     label:'Company · Ticker',          sortKey:'company', cls:'name-cell' },
    { id:'taxon',    label:'Industry · Sector',         sortKey:'sector', cls:'taxon' },
    { id:'price',    label:'Price',                     sortKey:'price', cls:'num' },
    { id:'high_52w', label:'52 week high',              sortKey:'high_52w', cls:'num' },
    { id:'low_52w',  label:'52 week low',               sortKey:'low_52w', cls:'num' },
    { id:'ma_150',   label:'150 day moving average',    sortKey:'ma_150', cls:'num' },
    { id:'ma_200',   label:'200 day moving average',    sortKey:'ma_200', cls:'num' },
    { id:'rating',   label:'Rating',                    sortKey:'rating_rank', cls:'grp-start-rating' },
    { id:'count',    label:'Score',                     sortKey:'count', cls:'' },
    { id:'g1_t1',    label:'Price above 200-day',                sortKey:'g1_t1', cls:'grp-start-g1', testGroup:'g1_lt_trend', testKey:'T1' },
    { id:'g1_t2',    label:'200-day rising month-on-month',      sortKey:'g1_t2', cls:'grp-end-g1', testGroup:'g1_lt_trend', testKey:'T2' },
    { id:'g2_t3',    label:'Price above 150-day',                sortKey:'g2_t3', cls:'grp-start-g2', testGroup:'g2_mt_trend', testKey:'T3' },
    { id:'g2_t4',    label:'150-day above 200-day',              sortKey:'g2_t4', cls:'grp-end-g2', testGroup:'g2_mt_trend', testKey:'T4' },
    { id:'g3_t5',    label:'50-day above 150-day',               sortKey:'g3_t5', cls:'grp-start-g3 grp-end-g3', testGroup:'g3_st_trend', testKey:'T5' },
    { id:'g4_t6',    label:'Within 25% of 52w high',             sortKey:'g4_t6', cls:'grp-start-g4', testGroup:'g4_price_leadership', testKey:'T6' },
    { id:'g4_t7',    label:'More than 25% above 52w low',        sortKey:'g4_t7', cls:'grp-end-g4', testGroup:'g4_price_leadership', testKey:'T7' },
    { id:'g5_t8',    label:'RS vs sector > 70',                  sortKey:'g5_t8', cls:'grp-start-g5', testGroup:'g5_rs', testKey:'T8' },
    { id:'g5_t9',    label:'RS vs industry > 70',                sortKey:'g5_t9', cls:'', testGroup:'g5_rs', testKey:'T9' },
    { id:'g5_t10',   label:'RS vs market > 70',                  sortKey:'g5_t10', cls:'grp-end-g5', testGroup:'g5_rs', testKey:'T10' },
    { id:'persist',  label:'Last 12 months',            sortKey:'persistence_count', cls:'grp-start-persist' }
  ];
  var S2_RATING_RANK = { 'Probable':4, 'Plausible':3, 'Possible':2, 'None':1 };
  var S2_TINT_CLS = { 'Probable':'tint-prob','Plausible':'tint-pla','Possible':'tint-pos','None':'tint-none' };

  function s2PricesLookup() {
    if (window._s2PricesByTicker) return window._s2PricesByTicker;
    var out = {};
    var arr = (window.MASTER_DATA && MASTER_DATA.prices) || [];
    for (var i = 0; i < arr.length; i++) if (arr[i] && arr[i].ticker) out[arr[i].ticker] = arr[i];
    window._s2PricesByTicker = out;
    return out;
  }
  function s2LiveTickers() {
    var out = {};
    var inv = (window.MASTER_DATA && MASTER_DATA.positions && MASTER_DATA.positions.investments) || [];
    for (var i = 0; i < inv.length; i++) if (inv[i].ticker) out[inv[i].ticker] = true;
    return out;
  }
  function s2LiveSectors() {
    var out = {}, t, prices = s2PricesLookup(), tickers = s2LiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.sector) out[p.sector] = true; }
    return out;
  }
  function s2LiveIndustries() {
    var out = {}, t, prices = s2PricesLookup(), tickers = s2LiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.industry) out[p.industry] = true; }
    return out;
  }
  function s2GetRows() {
    var raw = (window.MASTER_DATA && MASTER_DATA.filters) || [];
    var prices = s2PricesLookup();
    var live = s2LiveTickers(), liveS = s2LiveSectors(), liveI = s2LiveIndustries();
    var rows = [];
    for (var i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || !s.md_v2 || !s.md_v2.stage_2) continue;
      var p = prices[s.ticker] || {};
      var s2 = s.md_v2.stage_2;
      var pers = (s.md_v2.persistence && s.md_v2.persistence.stage_2_persistence) || [];
      var mas = p.mas || {};
      rows.push({
        ticker: s.ticker, company: p.company_name || s.ticker,
        sector: p.sector || '', industry: p.industry || '',
        price: p.price, high_52w: p.high_52w, low_52w: p.low_52w,
        ma_50: mas['50D'], ma_150: mas['150D'], ma_200: mas['200D'],
        rating: s2.rating, count: s2.count,
        tests: s2.tests || {}, groups: s2.groups || {}, persistence: pers,
        rs_sector: p.rs_vs_sector_pct, rs_industry: p.rs_vs_industry_pct, rs_market: p.rs_market_pct,
        is_live: !!live[s.ticker],
        sector_in_portfolio: !!liveS[p.sector],
        industry_in_portfolio: !!liveI[p.industry]
      });
    }
    return rows;
  }
  function s2UniverseCounts(rows) {
    var c = {'Probable':0,'Plausible':0,'Possible':0,'None':0};
    for (var i = 0; i < rows.length; i++) if (c[rows[i].rating] !== undefined) c[rows[i].rating]++;
    return c;
  }

  function s2FmtNum(n) {
    if (n == null || isNaN(n)) return '—';
    var abs = Math.abs(n);
    var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);
    var f = abs.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });
    return n < 0 ? '(' + f + ')' : f;
  }
  function s2FmtPct(p) {
    if (p == null || isNaN(p)) return '—';
    var r = Math.round(p), abs = Math.abs(r);
    return r < 0 ? '(' + abs + ')%' : r + '%';
  }
  function s2ColourForIntensity(i) {
    if (i >= 0.6) return '#0a4012';
    if (i >= 0.25) return '#1f6325';
    if (i >= 0.05) return '#4a8050';
    if (i <= -0.6) return '#8b1a1a';
    if (i <= -0.25) return '#a83232';
    if (i <= -0.05) return '#c66666';
    return '#666';
  }
  function s2InputCell(row, key, extraCls) {
    extraCls = extraCls || '';
    var v = row[key];
    if (key === 'price') return '<td class="num ' + extraCls + '">' + s2FmtNum(v) + '</td>';
    if (v == null || row.price == null) return '<td class="num ' + extraCls + '">—</td>';
    var pct = (row.price - v) / v * 100;
    var intensity = 0;
    if (key === 'high_52w') intensity = Math.max(-1, Math.min(1, (pct + 20) / 20));
    else if (key === 'low_52w') intensity = Math.max(-1, Math.min(1, (pct - 20) / 30));
    else if (key === 'ma_150' || key === 'ma_200') intensity = Math.max(-1, Math.min(1, pct / 10));
    var colour = s2ColourForIntensity(intensity);
    var text = (s2State.mode.inputs === 'pct') ? s2FmtPct(pct) : s2FmtNum(v);
    return '<td class="num ' + extraCls + '" style="color:' + colour + '">' + text + '</td>';
  }

  function s2TestValueFor(row, col) {
    var k = col.testKey;
    if (k === 'T1') return row.price != null && row.ma_200 != null ? s2FmtPct((row.price - row.ma_200) / row.ma_200 * 100) : '—';
    if (k === 'T3') return row.price != null && row.ma_150 != null ? s2FmtPct((row.price - row.ma_150) / row.ma_150 * 100) : '—';
    if (k === 'T4') return row.ma_150 != null && row.ma_200 != null ? s2FmtPct((row.ma_150 - row.ma_200) / row.ma_200 * 100) : '—';
    if (k === 'T5') return row.ma_50 != null && row.ma_150 != null ? s2FmtPct((row.ma_50 - row.ma_150) / row.ma_150 * 100) : '—';
    if (k === 'T6') return row.price != null && row.high_52w != null ? s2FmtPct((row.price - row.high_52w) / row.high_52w * 100) : '—';
    if (k === 'T7') return row.price != null && row.low_52w != null ? s2FmtPct((row.price - row.low_52w) / row.low_52w * 100) : '—';
    if (k === 'T8' && row.rs_sector != null) return Math.round(row.rs_sector) + '';
    if (k === 'T9' && row.rs_industry != null) return Math.round(row.rs_industry) + '';
    if (k === 'T10' && row.rs_market != null) return Math.round(row.rs_market) + '';
    return '—';
  }
  function s2TestCell(row, col) {
    var grp = (row.groups || {})[col.testGroup] || {};
    var pass = !!grp[col.testKey];
    var extra = col.cls || '';
    if (s2State.mode.tests === 'val') {
      var v = s2TestValueFor(row, col);
      var colour = pass ? s2ColourForIntensity(0.7) : s2ColourForIntensity(-0.4);
      return '<td class="test-val ' + extra + '" style="color:' + colour + '">' + v + '</td>';
    }
    if (pass) return '<td class="test-pass ' + extra + '"><span class="tick">✓</span></td>';
    return '<td class="test-fail ' + extra + '">·</td>';
  }

  function s2PillFor(rating, count) {
    if (rating === 'Probable') {
      var c = Math.min(Math.max(count, 7), 10);
      return '<span class="pill pill-prob-' + c + '">Probable</span>';
    }
    if (rating === 'Plausible') return '<span class="pill pill-pla">Plausible</span>';
    if (rating === 'Possible') return '<span class="pill pill-pos">Possible</span>';
    return '<span class="pill pill-none">None</span>';
  }
  function s2ScorePips(row) {
    var t = row.tests;
    var passed = [
      !!t.T1_P_above_200D, !!t.T2_200D_rising_MoM,
      !!t.T3_P_above_150D, !!t.T4_150_above_200,
      !!t.T5_50_above_150,
      !!t.T6_within_25pct_52WH, !!t.T7_above_25pct_52WL,
      !!t.T8_RS_vs_sector_70, !!t.T9_RS_vs_industry_70, !!t.T10_RS_vs_market_70
    ];
    var count = passed.filter(Boolean).length;
    var s = '';
    for (var i = 0; i < 10; i++) s += '<span class="pip ' + (passed[i] ? 'on' : '') + '"></span>';
    return '<div class="score-pip-row">' + s + '<span class="score-num">' + count + '/10</span></div>';
  }
  function s2PersistCells(arr, rating) {
    var h = '';
    for (var i = 0; i < 12; i++) {
      if (i === 11 && arr && arr[11]) {
        var cls = rating === 'Probable' ? 'r-prob' :
                  rating === 'Plausible' ? 'r-pla' :
                  rating === 'Possible' ? 'r-pos' : 'r-none';
        h += '<span class="persist-cell ' + cls + '" title="Current month: ' + rating + '"></span>';
      } else {
        h += '<span class="persist-cell r-none" title="Month -' + (11 - i) + ': not yet backfilled"></span>';
      }
    }
    return '<div class="persist-row">' + h + '</div>';
  }

  function s2HashColor(label, alpha) {
    if (!label) return null;
    var h = 0;
    for (var i = 0; i < label.length; i++) h = (h * 31 + label.charCodeAt(i)) & 0xffff;
    return 'hsla(' + (h % 360) + ', 35%, 55%, ' + alpha + ')';
  }
  function s2PortfolioInfo(row) {
    if (row.is_live) return { color:'#1b5e20', bg:'rgba(27,94,32,0.10)', bgHover:'rgba(27,94,32,0.14)' };
    if (row.sector_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.05)', bgHover:'rgba(27,94,32,0.08)' };
    if (row.industry_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.025)', bgHover:'rgba(27,94,32,0.05)' };
    return null;
  }

  function s2GetSortVal(row, key) {
    if (key === 'rating_rank') return S2_RATING_RANK[row.rating] || 0;
    if (key === 'persistence_count') return (row.persistence || []).filter(Boolean).length;
    if (key.indexOf('g') === 0 && key.indexOf('_t') > 0) {
      var col = S2_COLS.find(function(c) { return c.sortKey === key; });
      if (col) {
        var grp = (row.groups || {})[col.testGroup] || {};
        return grp[col.testKey] ? 1 : 0;
      }
    }
    var PCT_KEYS = ['high_52w','low_52w','ma_150','ma_200'];
    if (PCT_KEYS.indexOf(key) > -1 && s2State.mode.inputs === 'pct') {
      var ref = row[key];
      if (ref == null || row.price == null || ref === 0) return -Infinity;
      return (row.price - ref) / ref * 100;
    }
    if (key in row) return row[key];
    return 0;
  }
  function s2OnSort(key) {
    if (s2State.sort.col === key) s2State.sort.dir = s2State.sort.dir === 'desc' ? 'asc' : 'desc';
    else s2State.sort = { col: key, dir: 'desc' };
    s2BuildHeaderRow();
    s2RenderRows();
  }

  function s2BuildHeaderRow() {
    var tr = document.getElementById('s2-col-header-row');
    if (!tr) return;
    var h = '';
    for (var i = 0; i < S2_COLS.length; i++) {
      var c = S2_COLS[i];
      var isSort = s2State.sort.col === c.sortKey;
      var arrow = isSort
        ? '<span class="sort-arrow">' + (s2State.sort.dir === 'desc' ? '▼' : '▲') + '</span>'
        : '<span class="sort-placeholder"></span>';
      h += '<th class="' + (c.cls || '') + '" data-sort-key="' + c.sortKey + '" title="' + c.label + '">' +
           '<span class="hd"><span class="lbl">' + c.label + '</span>' + arrow + '</span></th>';
    }
    tr.innerHTML = h;
  }
  function s2RatingTiles(rows) {
    var tiles = document.getElementById('s2-rating-tiles');
    if (!tiles) return;
    var uc = s2UniverseCounts(rows);
    var total = rows.length;
    var order = ['None','Possible','Plausible','Probable'];
    var strip = {'Probable':'prob','Plausible':'pla','Possible':'pos','None':'none'};
    var h = '';
    for (var i = 0; i < order.length; i++) {
      var r = order[i], cnt = uc[r] || 0;
      var act = s2State.ratingFilter === r ? ' active' : '';
      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;
      h += '<div class="rating-tile ' + S2_TINT_CLS[r] + act + '" data-rating="' + r + '">' +
           '<div class="rt-label">' + r + '</div>' +
           '<div class="rt-count">' + cnt.toLocaleString('en-GB') + '</div>' +
           '<div class="rt-sub">of ' + total.toLocaleString('en-GB') + ' · ' + pct + '%</div>' +
           '<div class="rt-strip rt-strip-' + strip[r] + '"></div>' +
           '</div>';
    }
    tiles.innerHTML = h;
  }
  function s2UpdateScopeCounts(rows) {
    function set(id, n) { var el = document.getElementById(id); if (el) el.textContent = '(' + n + ')'; }
    set('s2-cnt-all',      rows.length);
    set('s2-cnt-live',     rows.filter(function(r){ return r.is_live; }).length);
    set('s2-cnt-sector',   rows.filter(function(r){ return r.sector_in_portfolio; }).length);
    set('s2-cnt-industry', rows.filter(function(r){ return r.industry_in_portfolio; }).length);
  }

  function s2RenderRows() {
    var tbody = document.getElementById('s2-tbody');
    if (!tbody) return;
    var all = s2GetRows();
    s2UpdateScopeCounts(all);
    s2RatingTiles(all);
    var rows = all.slice();
    if (s2State.scope === 'live') rows = rows.filter(function(r){ return r.is_live; });
    else if (s2State.scope === 'sector') rows = rows.filter(function(r){ return r.sector_in_portfolio; });
    else if (s2State.scope === 'industry') rows = rows.filter(function(r){ return r.industry_in_portfolio; });
    if (s2State.ratingFilter) rows = rows.filter(function(r){ return r.rating === s2State.ratingFilter; });
    rows.sort(function(a,b) {
      var va = s2GetSortVal(a, s2State.sort.col), vb = s2GetSortVal(b, s2State.sort.col);
      var cmp = (typeof va === 'string') ? va.localeCompare(vb) : (va || 0) - (vb || 0);
      if (cmp === 0) cmp = a.ticker.localeCompare(b.ticker);
      return s2State.sort.dir === 'desc' ? -cmp : cmp;
    });
    var html = '';
    for (var i = 0; i < rows.length; i++) {
      var s = rows[i];
      var styles = [], cls = [];
      if (s2State.tint === 'industry') { styles.push('--tint-bg: ' + s2HashColor(s.industry, 0.16)); cls.push('tint-row'); }
      else if (s2State.tint === 'sector') { styles.push('--tint-bg: ' + s2HashColor(s.sector, 0.16)); cls.push('tint-row'); }
      if (s2State.port === 'on') {
        var pi = s2PortfolioInfo(s);
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
        s2InputCell(s, 'price') + s2InputCell(s, 'high_52w') + s2InputCell(s, 'low_52w') +
        s2InputCell(s, 'ma_150') + s2InputCell(s, 'ma_200') +
        '<td class="grp-start-rating">' + s2PillFor(s.rating, s.count) + '</td>' +
        '<td>' + s2ScorePips(s) + '</td>';
      for (var j = 9; j <= 18; j++) html += s2TestCell(s, S2_COLS[j]);
      html += '<td class="grp-start-persist">' + s2PersistCells(s.persistence, s.rating) + '</td>' +
        '</tr>';
    }
    tbody.innerHTML = html;
  }

  function s2SetMode(kind, val) {
    s2State.mode[kind] = val;
    var btns = document.querySelectorAll('button[data-s2-grp="' + kind + '"]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-s2-val') === val);
    s2RenderRows();
  }
  function s2SetScope(s) {
    s2State.scope = s;
    var btns = document.querySelectorAll('button[data-s2-scope]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-s2-scope') === s);
    s2RenderRows();
  }
  function s2SetTint(t) {
    s2State.tint = t;
    var btns = document.querySelectorAll('button[data-s2-tint]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-s2-tint') === t);
    s2RenderRows();
  }
  function s2SetPort(p) {
    s2State.port = p;
    var btns = document.querySelectorAll('button[data-s2-port]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-s2-port') === p);
    s2RenderRows();
  }
  function s2ToggleRating(r) {
    s2State.ratingFilter = (s2State.ratingFilter === r) ? null : r;
    s2RenderRows();
  }
  window.s2SetMode = s2SetMode;
  window.s2SetScope = s2SetScope;
  window.s2SetTint = s2SetTint;
  window.s2SetPort = s2SetPort;
  window.s2ToggleRating = s2ToggleRating;
  window.s2OnSort = s2OnSort;

  function s2BuildScaffold() {
    var host = document.getElementById('tab-stage_2');
    if (!host) return false;
    if (host.querySelector('#s2-main-table')) return true;
    var html = '' +
      '<div class="s1-intro">Stage 2 looks for stocks already in a clear uptrend across long, medium, and short-term moving averages, with price near recent highs, and showing relative strength against sector, industry, and the broader market. The aim is to identify quality holdings to add to or hold core positions in. Ten tests across five groups: the more tests passing, the more confirmed the uptrend.</div>' +
      '<div class="controls s1-controls">' +
        '<div class="ctrl-grp"><span class="ctrl-label">Inputs</span>' +
          '<button class="toggle-btn active" data-s2-grp="inputs" data-s2-val="pct" onclick="s2SetMode(\'inputs\',\'pct\')">show as %</button>' +
          '<button class="toggle-btn" data-s2-grp="inputs" data-s2-val="raw" onclick="s2SetMode(\'inputs\',\'raw\')">show as numbers</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Tests</span>' +
          '<button class="toggle-btn active" data-s2-grp="tests" data-s2-val="tick" onclick="s2SetMode(\'tests\',\'tick\')">show ticks</button>' +
          '<button class="toggle-btn" data-s2-grp="tests" data-s2-val="val" onclick="s2SetMode(\'tests\',\'val\')">show test values</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Scope</span>' +
          '<button class="toggle-btn active" data-s2-scope="all" onclick="s2SetScope(\'all\')">All <span id="s2-cnt-all"></span></button>' +
          '<button class="toggle-btn" data-s2-scope="live" onclick="s2SetScope(\'live\')">Live <span id="s2-cnt-live"></span></button>' +
          '<button class="toggle-btn" data-s2-scope="sector" onclick="s2SetScope(\'sector\')">Sectors <span id="s2-cnt-sector"></span></button>' +
          '<button class="toggle-btn" data-s2-scope="industry" onclick="s2SetScope(\'industry\')">Industries <span id="s2-cnt-industry"></span></button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Peers</button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Cohorts</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Colour by</span>' +
          '<button class="toggle-btn active" data-s2-tint="none" onclick="s2SetTint(\'none\')">Off</button>' +
          '<button class="toggle-btn" data-s2-tint="industry" onclick="s2SetTint(\'industry\')">Industry</button>' +
          '<button class="toggle-btn" data-s2-tint="sector" onclick="s2SetTint(\'sector\')">Sector</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Portfolio tint</span>' +
          '<button class="toggle-btn active" data-s2-port="off" onclick="s2SetPort(\'off\')">Off</button>' +
          '<button class="toggle-btn" data-s2-port="on" onclick="s2SetPort(\'on\')">On</button>' +
        '</div>' +
      '</div>' +
      '<div class="rating-tiles s1-rating-tiles" id="s2-rating-tiles" style="grid-template-columns: repeat(4, 1fr);"></div>' +
      '<div class="group-captions" style="grid-template-columns: repeat(5, 1fr);">' +
        '<div class="gcap gcap-g1"><b>Group 1 · Long-term trend</b>Is the long-term trend up? Price above the 200-day moving average, and the 200-day rising month-on-month. The two foundational uptrend signals.</div>' +
        '<div class="gcap gcap-g2"><b>Group 2 · Medium-term trend</b>Is the medium-term trend up? Price above the 150-day moving average, and the 150-day above the 200-day. Confirms the long-term trend is supported by a healthy medium-term picture.</div>' +
        '<div class="gcap gcap-g3"><b>Group 3 · Short-term trend</b>Is the short-term trend up? 50-day moving average above the 150-day. The fastest of the trend signals; turns positive at the inflection from base to breakout.</div>' +
        '<div class="gcap gcap-g4"><b>Group 4 · Price leadership</b>Is the stock leading on price? Within 25% of its 52-week high, and at least 25% above its 52-week low. Together: strength near highs, well off the bottom.</div>' +
        '<div class="gcap gcap-g5" style="border-left-color:#6a5a8a"><b style="color:#6a5a8a">Group 5 · Relative strength</b>Is the stock outperforming peers? Relative strength above 70th percentile vs sector, industry, and market. Three independent strength signals across different peer groups.</div>' +
      '</div>' +
      '<div class="table-wrap">' +
        '<table class="data-table" id="s2-main-table">' +
          '<colgroup>' +
            '<col class="c-name"><col class="c-taxon">' +
            '<col class="c-price"><col class="c-52wh"><col class="c-52wl">' +
            '<col class="c-ma150"><col class="c-ma200">' +
            '<col class="c-rating"><col class="c-score">' +
            '<col class="c-test"><col class="c-test"><col class="c-test"><col class="c-test"><col class="c-test">' +
            '<col class="c-test"><col class="c-test"><col class="c-test"><col class="c-test"><col class="c-test">' +
            '<col class="c-persist">' +
          '</colgroup>' +
          '<thead>' +
            '<tr class="group-header-row">' +
              '<th class="gh-inputs" colspan="7">Inputs</th>' +
              '<th class="gh-rating grp-start-rating" colspan="2">Stage 2 rating · thresholds 5/10 · 6/10 · 7+/10</th>' +
              '<th class="gh-g1 grp-start-g1 grp-end-g1" colspan="2">Group 1 · Long-term trend</th>' +
              '<th class="gh-g2 grp-start-g2 grp-end-g2" colspan="2">Group 2 · Medium-term trend</th>' +
              '<th class="gh-g3 grp-start-g3 grp-end-g3" colspan="1">Group 3 · Short-term trend</th>' +
              '<th class="gh-g4 grp-start-g4 grp-end-g4" colspan="2">Group 4 · Price leadership</th>' +
              '<th class="gh-g5 grp-start-g5 grp-end-g5" colspan="3" style="color:#6a5a8a; background:rgba(106,90,138,0.06)!important; border-left:2px solid #6a5a8a!important">Group 5 · Relative strength</th>' +
              '<th class="gh-persist grp-start-persist" colspan="1">Stage Qualification persistence</th>' +
            '</tr>' +
            '<tr class="col-header-row" id="s2-col-header-row"></tr>' +
          '</thead>' +
          '<tbody id="s2-tbody"></tbody>' +
        '</table>' +
      '</div>';
    host.innerHTML = html;
    var tiles = document.getElementById('s2-rating-tiles');
    if (tiles) {
      tiles.addEventListener('click', function(e) {
        var tile = e.target.closest('.rating-tile');
        if (!tile) return;
        var r = tile.getAttribute('data-rating');
        if (r) s2ToggleRating(r);
      });
    }
    var hdr = document.getElementById('s2-col-header-row');
    if (hdr) {
      hdr.addEventListener('click', function(e) {
        var th = e.target.closest('th');
        if (!th) return;
        var key = th.getAttribute('data-sort-key');
        if (key) s2OnSort(key);
      });
    }
    return true;
  }

  function renderStage2() {
    if (!s2BuildScaffold()) return;
    s2BuildHeaderRow();
    s2RenderRows();
  }
  window.renderStage2 = renderStage2;

})();

/* MD-V2-STAGE2-MARKER-END */
