// =============================================================================
// STAGE 3 TAB MODULE — Master Dashboard V2
// =============================================================================
// MD-V2-STAGE3-MARKER — idempotency marker for patcher detection
//
// Stage 3 = Topping / Invalidation. 10 tests across 5 groups.
// Ratings:
//   None                     (<2)
//   Possible Topping         (2-3)
//   Plausible Invalidation   (4-5)
//   Probable Invalidation    (6+)
// =============================================================================

/* MD-V2-STAGE3-MARKER-START */

(function() {
  'use strict';

  var s3State = {
    mode: { inputs: 'pct', tests: 'tick' },
    scope: 'all', ratingFilter: null, tint: 'none', port: 'off',
    sort: { col: 'count', dir: 'desc' }
  };

  var S3_COLS = [
    { id:'name',     label:'Company · Ticker',          sortKey:'company', cls:'name-cell' },
    { id:'taxon',    label:'Industry · Sector',         sortKey:'sector', cls:'taxon' },
    { id:'price',    label:'Price',                     sortKey:'price', cls:'num' },
    { id:'high_52w', label:'52 week high',              sortKey:'high_52w', cls:'num' },
    { id:'low_52w',  label:'52 week low',               sortKey:'low_52w', cls:'num' },
    { id:'ma_150',   label:'150 day moving average',    sortKey:'ma_150', cls:'num' },
    { id:'ma_200',   label:'200 day moving average',    sortKey:'ma_200', cls:'num' },
    { id:'rating',   label:'Rating',                    sortKey:'rating_rank', cls:'grp-start-rating' },
    { id:'count',    label:'Score',                     sortKey:'count', cls:'' },
    { id:'g1_t1',    label:'3 or more bases since 52w low',           sortKey:'g1_t1', cls:'grp-start-g1', testGroup:'g1_base_count', testKey:'T1' },
    { id:'g1_t2',    label:'4 or more bases since 52w low',           sortKey:'g1_t2', cls:'grp-end-g1', testGroup:'g1_base_count', testKey:'T2' },
    { id:'g2_t3',    label:'200-day flattening',                       sortKey:'g2_t3', cls:'grp-start-g2', testGroup:'g2_price_trend', testKey:'T3' },
    { id:'g2_t4',    label:'50-day below 150-day',                     sortKey:'g2_t4', cls:'grp-end-g2', testGroup:'g2_price_trend', testKey:'T4' },
    { id:'g3_t5',    label:'Down volume exceeds up volume',            sortKey:'g3_t5', cls:'grp-start-g3', testGroup:'g3_debate', testKey:'T5' },
    { id:'g3_t6',    label:'Volatility increasing',                    sortKey:'g3_t6', cls:'', testGroup:'g3_debate', testKey:'T6' },
    { id:'g3_t7',    label:'No breakout (price near 50-day)',          sortKey:'g3_t7', cls:'grp-end-g3', testGroup:'g3_debate', testKey:'T7' },
    { id:'g4_t8',    label:'2+ lower lows in last month',              sortKey:'g4_t8', cls:'grp-start-g4', testGroup:'g4_lower_lows', testKey:'T8' },
    { id:'g4_t9',    label:'3+ lower lows in last 3 months',           sortKey:'g4_t9', cls:'grp-end-g4', testGroup:'g4_lower_lows', testKey:'T9' },
    { id:'g5_t10',   label:'RS trend weakening (3m < -5%)',            sortKey:'g5_t10', cls:'grp-start-g5 grp-end-g5', testGroup:'g5_rs_trend', testKey:'T10' },
    { id:'persist',  label:'Last 12 months',            sortKey:'persistence_count', cls:'grp-start-persist' }
  ];
  var S3_RATING_RANK = { 'Probable Invalidation':4, 'Plausible Invalidation':3, 'Possible Topping':2, 'None':1 };
  var S3_TINT_CLS = {
    'Probable Invalidation':'tint-prob',
    'Plausible Invalidation':'tint-pla',
    'Possible Topping':'tint-pos',
    'None':'tint-none'
  };

  function s3PricesLookup() {
    if (window._s3PricesByTicker) return window._s3PricesByTicker;
    var out = {};
    var arr = (window.MASTER_DATA && MASTER_DATA.prices) || [];
    for (var i = 0; i < arr.length; i++) if (arr[i] && arr[i].ticker) out[arr[i].ticker] = arr[i];
    window._s3PricesByTicker = out;
    return out;
  }
  function s3LiveTickers() {
    var out = {};
    var inv = (window.MASTER_DATA && MASTER_DATA.positions && MASTER_DATA.positions.investments) || [];
    for (var i = 0; i < inv.length; i++) if (inv[i].ticker) out[inv[i].ticker] = true;
    return out;
  }
  function s3LiveSectors() {
    var out = {}, t, prices = s3PricesLookup(), tickers = s3LiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.sector) out[p.sector] = true; }
    return out;
  }
  function s3LiveIndustries() {
    var out = {}, t, prices = s3PricesLookup(), tickers = s3LiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.industry) out[p.industry] = true; }
    return out;
  }
  function s3GetRows() {
    var raw = (window.MASTER_DATA && MASTER_DATA.filters) || [];
    var prices = s3PricesLookup();
    var live = s3LiveTickers(), liveS = s3LiveSectors(), liveI = s3LiveIndustries();
    var rows = [];
    for (var i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || !s.md_v2 || !s.md_v2.stage_3) continue;
      var p = prices[s.ticker] || {};
      var s3 = s.md_v2.stage_3;
      var pers = (s.md_v2.persistence && s.md_v2.persistence.stage_3_persistence) || [];
      var mas = p.mas || {};
      rows.push({
        ticker: s.ticker, company: p.company_name || s.ticker,
        sector: p.sector || '', industry: p.industry || '',
        price: p.price, high_52w: p.high_52w, low_52w: p.low_52w,
        ma_50: mas['50D'], ma_150: mas['150D'], ma_200: mas['200D'],
        rating: s3.rating, count: s3.count,
        tests: s3.tests || {}, groups: s3.groups || {}, persistence: pers,
        rs_sector: p.rs_vs_sector_pct, rs_industry: p.rs_vs_industry_pct, rs_market: p.rs_market_pct,
        is_live: !!live[s.ticker],
        sector_in_portfolio: !!liveS[p.sector],
        industry_in_portfolio: !!liveI[p.industry]
      });
    }
    return rows;
  }
  function s3UniverseCounts(rows) {
    var c = {'Probable Invalidation':0,'Plausible Invalidation':0,'Possible Topping':0,'None':0};
    for (var i = 0; i < rows.length; i++) if (c[rows[i].rating] !== undefined) c[rows[i].rating]++;
    return c;
  }

  function s3FmtNum(n) {
    if (n == null || isNaN(n)) return '—';
    var abs = Math.abs(n);
    var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);
    var f = abs.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });
    return n < 0 ? '(' + f + ')' : f;
  }
  function s3FmtPct(p) {
    if (p == null || isNaN(p)) return '—';
    var r = Math.round(p), abs = Math.abs(r);
    return r < 0 ? '(' + abs + ')%' : r + '%';
  }
  // Stage 3 intensity scale — INVERTED relative to Stage 1/2.
  // Bearish/topping signals are bad → use red colour scale for "passed".
  // Pass colour ramps red; fail stays neutral grey.
  function s3ColourForIntensity(i) {
    if (i >= 0.6) return '#8b1a1a';
    if (i >= 0.25) return '#a83232';
    if (i >= 0.05) return '#c66666';
    if (i <= -0.6) return '#0a4012';
    if (i <= -0.25) return '#1f6325';
    if (i <= -0.05) return '#4a8050';
    return '#666';
  }
  function s3InputCell(row, key, extraCls) {
    extraCls = extraCls || '';
    var v = row[key];
    if (key === 'price') return '<td class="num ' + extraCls + '">' + s3FmtNum(v) + '</td>';
    if (v == null || row.price == null) return '<td class="num ' + extraCls + '">—</td>';
    var pct = (row.price - v) / v * 100;
    // For Stage 3 (topping/invalidation), the bearish interpretation:
    // - Price below 52w high (negative pct vs high) is bearish
    // - Price near 52w low is bearish
    // - Price below 150D / 200D is bearish
    // Intensity: positive = "looks bearish" → red colour via inverted scale.
    var intensity = 0;
    if (key === 'high_52w') intensity = Math.max(-1, Math.min(1, (-pct - 10) / 20));   // below 52w high = bearish
    else if (key === 'low_52w') intensity = Math.max(-1, Math.min(1, (20 - pct) / 30)); // near 52w low = bearish
    else if (key === 'ma_150' || key === 'ma_200') intensity = Math.max(-1, Math.min(1, -pct / 10));
    var colour = s3ColourForIntensity(intensity);
    var text = (s3State.mode.inputs === 'pct') ? s3FmtPct(pct) : s3FmtNum(v);
    return '<td class="num ' + extraCls + '" style="color:' + colour + '">' + text + '</td>';
  }

  function s3TestValueFor(row, col) {
    var k = col.testKey;
    var t = row.tests || {};
    // G1: base counts (binary thresholds — no continuous value, show ✓/✗ only)
    if (k === 'T1' || k === 'T2') return t[k === 'T1' ? 'T1_3_plus_bases' : 'T2_4_plus_bases'] ? 'pass' : 'fail';
    // G2 T3: 200D flattening (binary derived) — no continuous % to show
    if (k === 'T3') return t.T3_200D_flattening ? 'flat' : '—';
    // G2 T4: 50D < 150D — show pct gap
    if (k === 'T4') return row.ma_50 != null && row.ma_150 != null ? s3FmtPct((row.ma_50 - row.ma_150) / row.ma_150 * 100) : '—';
    // G3 T5: volume down/up ratio (binary)
    if (k === 'T5') return t.T5_volume_down_up_ratio ? '≥1.1x' : '—';
    // G3 T6: volatility increase (binary)
    if (k === 'T6') return t.T6_volatility_increase ? '≥1.1x' : '—';
    // G3 T7: no breakout — price within 5% of 50D
    if (k === 'T7') return row.price != null && row.ma_50 != null ? s3FmtPct((row.price - row.ma_50) / row.ma_50 * 100) : '—';
    // G4 T8/T9: lower lows counts (binary)
    if (k === 'T8') return t.T8_lower_lows_1m ? '≥2' : '—';
    if (k === 'T9') return t.T9_lower_lows_3m ? '≥3' : '—';
    // G5 T10: RS trend weakening
    if (k === 'T10') return t.T10_RS_trend_weakening ? '< -5%' : '—';
    return '—';
  }
  function s3TestCell(row, col) {
    var grp = (row.groups || {})[col.testGroup] || {};
    var pass = !!grp[col.testKey];
    var extra = col.cls || '';
    if (s3State.mode.tests === 'val') {
      var v = s3TestValueFor(row, col);
      // Stage 3 passes are BEARISH — colour pass red, fail neutral grey
      var colour = pass ? s3ColourForIntensity(0.7) : '#999';
      return '<td class="test-val ' + extra + '" style="color:' + colour + '">' + v + '</td>';
    }
    if (pass) return '<td class="test-pass-bear ' + extra + '"><span class="tick">✓</span></td>';
    return '<td class="test-fail ' + extra + '">·</td>';
  }

  function s3PillFor(rating, count) {
    if (rating === 'Probable Invalidation') {
      var c = Math.min(Math.max(count, 6), 10);
      return '<span class="pill pill-prob-inv-' + c + '">Probable Inv.</span>';
    }
    if (rating === 'Plausible Invalidation') return '<span class="pill pill-pla-inv">Plausible Inv.</span>';
    if (rating === 'Possible Topping') return '<span class="pill pill-pos-top">Possible Top.</span>';
    return '<span class="pill pill-none">None</span>';
  }
  function s3ScorePips(row) {
    var t = row.tests;
    var passed = [
      !!t.T1_3_plus_bases, !!t.T2_4_plus_bases,
      !!t.T3_200D_flattening, !!t.T4_50_below_150,
      !!t.T5_volume_down_up_ratio, !!t.T6_volatility_increase, !!t.T7_no_breakout,
      !!t.T8_lower_lows_1m, !!t.T9_lower_lows_3m,
      !!t.T10_RS_trend_weakening
    ];
    var count = passed.filter(Boolean).length;
    var s = '';
    for (var i = 0; i < 10; i++) s += '<span class="pip pip-bear ' + (passed[i] ? 'on' : '') + '"></span>';
    return '<div class="score-pip-row">' + s + '<span class="score-num">' + count + '/10</span></div>';
  }
  function s3PersistCells(arr, rating) {
    var h = '';
    for (var i = 0; i < 12; i++) {
      if (i === 11 && arr && arr[11]) {
        var cls = rating === 'Probable Invalidation' ? 'r-prob-inv' :
                  rating === 'Plausible Invalidation' ? 'r-pla-inv' :
                  rating === 'Possible Topping' ? 'r-pos-top' : 'r-none';
        h += '<span class="persist-cell ' + cls + '" title="Current month: ' + rating + '"></span>';
      } else {
        h += '<span class="persist-cell r-none" title="Month -' + (11 - i) + ': not yet backfilled"></span>';
      }
    }
    return '<div class="persist-row">' + h + '</div>';
  }

  function s3HashColor(label, alpha) {
    if (!label) return null;
    var h = 0;
    for (var i = 0; i < label.length; i++) h = (h * 31 + label.charCodeAt(i)) & 0xffff;
    return 'hsla(' + (h % 360) + ', 35%, 55%, ' + alpha + ')';
  }
  function s3PortfolioInfo(row) {
    if (row.is_live) return { color:'#1b5e20', bg:'rgba(27,94,32,0.10)', bgHover:'rgba(27,94,32,0.14)' };
    if (row.sector_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.05)', bgHover:'rgba(27,94,32,0.08)' };
    if (row.industry_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.025)', bgHover:'rgba(27,94,32,0.05)' };
    return null;
  }

  function s3GetSortVal(row, key) {
    if (key === 'rating_rank') return S3_RATING_RANK[row.rating] || 0;
    if (key === 'persistence_count') return (row.persistence || []).filter(Boolean).length;
    if (key.indexOf('g') === 0 && key.indexOf('_t') > 0) {
      var col = S3_COLS.find(function(c) { return c.sortKey === key; });
      if (col) {
        var grp = (row.groups || {})[col.testGroup] || {};
        return grp[col.testKey] ? 1 : 0;
      }
    }
    var PCT_KEYS = ['high_52w','low_52w','ma_150','ma_200'];
    if (PCT_KEYS.indexOf(key) > -1 && s3State.mode.inputs === 'pct') {
      var ref = row[key];
      if (ref == null || row.price == null || ref === 0) return -Infinity;
      return (row.price - ref) / ref * 100;
    }
    if (key in row) return row[key];
    return 0;
  }
  function s3OnSort(key) {
    if (s3State.sort.col === key) s3State.sort.dir = s3State.sort.dir === 'desc' ? 'asc' : 'desc';
    else s3State.sort = { col: key, dir: 'desc' };
    s3BuildHeaderRow();
    s3RenderRows();
  }

  function s3BuildHeaderRow() {
    var tr = document.getElementById('s3-col-header-row');
    if (!tr) return;
    var h = '';
    for (var i = 0; i < S3_COLS.length; i++) {
      var c = S3_COLS[i];
      var isSort = s3State.sort.col === c.sortKey;
      var arrow = isSort
        ? '<span class="sort-arrow">' + (s3State.sort.dir === 'desc' ? '▼' : '▲') + '</span>'
        : '<span class="sort-placeholder"></span>';
      h += '<th class="' + (c.cls || '') + '" data-sort-key="' + c.sortKey + '" title="' + c.label + '">' +
           '<span class="hd"><span class="lbl">' + c.label + '</span>' + arrow + '</span></th>';
    }
    tr.innerHTML = h;
  }
  function s3RatingTiles(rows) {
    var tiles = document.getElementById('s3-rating-tiles');
    if (!tiles) return;
    var uc = s3UniverseCounts(rows);
    var total = rows.length;
    var order = ['None','Possible Topping','Plausible Invalidation','Probable Invalidation'];
    var strip = {
      'Probable Invalidation':'prob-inv',
      'Plausible Invalidation':'pla-inv',
      'Possible Topping':'pos-top',
      'None':'none'
    };
    var h = '';
    for (var i = 0; i < order.length; i++) {
      var r = order[i], cnt = uc[r] || 0;
      var act = s3State.ratingFilter === r ? ' active' : '';
      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;
      h += '<div class="rating-tile ' + S3_TINT_CLS[r] + act + '" data-rating="' + r + '">' +
           '<div class="rt-label">' + r + '</div>' +
           '<div class="rt-count">' + cnt.toLocaleString('en-GB') + '</div>' +
           '<div class="rt-sub">of ' + total.toLocaleString('en-GB') + ' · ' + pct + '%</div>' +
           '<div class="rt-strip rt-strip-' + strip[r] + '"></div>' +
           '</div>';
    }
    tiles.innerHTML = h;
  }
  function s3UpdateScopeCounts(rows) {
    function set(id, n) { var el = document.getElementById(id); if (el) el.textContent = '(' + n + ')'; }
    set('s3-cnt-all',      rows.length);
    set('s3-cnt-live',     rows.filter(function(r){ return r.is_live; }).length);
    set('s3-cnt-sector',   rows.filter(function(r){ return r.sector_in_portfolio; }).length);
    set('s3-cnt-industry', rows.filter(function(r){ return r.industry_in_portfolio; }).length);
  }

  function s3RenderRows() {
    var tbody = document.getElementById('s3-tbody');
    if (!tbody) return;
    var all = s3GetRows();
    s3UpdateScopeCounts(all);
    s3RatingTiles(all);
    var rows = all.slice();
    if (s3State.scope === 'live') rows = rows.filter(function(r){ return r.is_live; });
    else if (s3State.scope === 'sector') rows = rows.filter(function(r){ return r.sector_in_portfolio; });
    else if (s3State.scope === 'industry') rows = rows.filter(function(r){ return r.industry_in_portfolio; });
    if (s3State.ratingFilter) rows = rows.filter(function(r){ return r.rating === s3State.ratingFilter; });
    rows.sort(function(a,b) {
      var va = s3GetSortVal(a, s3State.sort.col), vb = s3GetSortVal(b, s3State.sort.col);
      var cmp = (typeof va === 'string') ? va.localeCompare(vb) : (va || 0) - (vb || 0);
      if (cmp === 0) cmp = a.ticker.localeCompare(b.ticker);
      return s3State.sort.dir === 'desc' ? -cmp : cmp;
    });
    var html = '';
    for (var i = 0; i < rows.length; i++) {
      var s = rows[i];
      var styles = [], cls = [];
      if (s3State.tint === 'industry') { styles.push('--tint-bg: ' + s3HashColor(s.industry, 0.16)); cls.push('tint-row'); }
      else if (s3State.tint === 'sector') { styles.push('--tint-bg: ' + s3HashColor(s.sector, 0.16)); cls.push('tint-row'); }
      if (s3State.port === 'on') {
        var pi = s3PortfolioInfo(s);
        if (pi) {
          styles.push('--portfolio-color: ' + pi.color);
          styles.push('--portfolio-bg: ' + pi.bg);
          styles.push('--portfolio-bg-hover: ' + pi.bg);
          cls.push('portfolio-band'); cls.push('portfolio-tint');
        }
      }
      var styleAttr = styles.length ? ' style="' + styles.join(';') + '"' : '';
      var clsAttr = cls.length ? ' class="' + cls.join(' ') + '"' : '';
      var liveDot = s.is_live ? '<span class="live-dot">●</span>' : '';
      html += '<tr' + clsAttr + styleAttr + '>' +
        '<td class="name-cell"><div class="co">' + liveDot + (s.company || s.ticker) + '</div><div class="tk">' + s.ticker + '</div></td>' +
        '<td class="taxon"><div class="ind">' + (s.industry || '') + '</div><div class="sec">' + (s.sector || '') + '</div></td>' +
        s3InputCell(s, 'price') + s3InputCell(s, 'high_52w') + s3InputCell(s, 'low_52w') +
        s3InputCell(s, 'ma_150') + s3InputCell(s, 'ma_200') +
        '<td class="grp-start-rating">' + s3PillFor(s.rating, s.count) + '</td>' +
        '<td>' + s3ScorePips(s) + '</td>';
      for (var j = 9; j <= 18; j++) html += s3TestCell(s, S3_COLS[j]);
      html += '<td class="grp-start-persist">' + s3PersistCells(s.persistence, s.rating) + '</td>' +
        '</tr>';
    }
    tbody.innerHTML = html;
  }

  function s3SetMode(kind, val) {
    s3State.mode[kind] = val;
    var btns = document.querySelectorAll('button[data-s3-grp="' + kind + '"]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-s3-val') === val);
    s3RenderRows();
  }
  function s3SetScope(s) {
    s3State.scope = s;
    var btns = document.querySelectorAll('button[data-s3-scope]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-s3-scope') === s);
    s3RenderRows();
  }
  function s3SetTint(t) {
    s3State.tint = t;
    var btns = document.querySelectorAll('button[data-s3-tint]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-s3-tint') === t);
    s3RenderRows();
  }
  function s3SetPort(p) {
    s3State.port = p;
    var btns = document.querySelectorAll('button[data-s3-port]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-s3-port') === p);
    s3RenderRows();
  }
  function s3ToggleRating(r) {
    s3State.ratingFilter = (s3State.ratingFilter === r) ? null : r;
    s3RenderRows();
  }
  window.s3SetMode = s3SetMode;
  window.s3SetScope = s3SetScope;
  window.s3SetTint = s3SetTint;
  window.s3SetPort = s3SetPort;
  window.s3ToggleRating = s3ToggleRating;
  window.s3OnSort = s3OnSort;

  function s3BuildScaffold() {
    var host = document.getElementById('tab-stage_3');
    if (!host) return false;
    if (host.querySelector('#s3-main-table')) return true;
    var html = '' +
      '<div class="s1-intro">Stage 3 looks for stocks where the prior uptrend is rolling over: multiple bases stacked since the 52-week low, the 200-day moving average flattening, distribution showing up in down-volume and volatility, lower lows accumulating, and relative strength weakening. The aim is to spot positions to lighten or candidates approaching invalidation. Ten tests across five groups: more tests passing means the topping case is firmer.</div>' +
      '<div class="controls s1-controls">' +
        '<div class="ctrl-grp"><span class="ctrl-label">Inputs</span>' +
          '<button class="toggle-btn active" data-s3-grp="inputs" data-s3-val="pct" onclick="s3SetMode(\'inputs\',\'pct\')">show as %</button>' +
          '<button class="toggle-btn" data-s3-grp="inputs" data-s3-val="raw" onclick="s3SetMode(\'inputs\',\'raw\')">show as numbers</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Tests</span>' +
          '<button class="toggle-btn active" data-s3-grp="tests" data-s3-val="tick" onclick="s3SetMode(\'tests\',\'tick\')">show ticks</button>' +
          '<button class="toggle-btn" data-s3-grp="tests" data-s3-val="val" onclick="s3SetMode(\'tests\',\'val\')">show test values</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Scope</span>' +
          '<button class="toggle-btn active" data-s3-scope="all" onclick="s3SetScope(\'all\')">All <span id="s3-cnt-all"></span></button>' +
          '<button class="toggle-btn" data-s3-scope="live" onclick="s3SetScope(\'live\')">Live <span id="s3-cnt-live"></span></button>' +
          '<button class="toggle-btn" data-s3-scope="sector" onclick="s3SetScope(\'sector\')">Sectors <span id="s3-cnt-sector"></span></button>' +
          '<button class="toggle-btn" data-s3-scope="industry" onclick="s3SetScope(\'industry\')">Industries <span id="s3-cnt-industry"></span></button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Peers</button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Cohorts</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Colour by</span>' +
          '<button class="toggle-btn active" data-s3-tint="none" onclick="s3SetTint(\'none\')">Off</button>' +
          '<button class="toggle-btn" data-s3-tint="industry" onclick="s3SetTint(\'industry\')">Industry</button>' +
          '<button class="toggle-btn" data-s3-tint="sector" onclick="s3SetTint(\'sector\')">Sector</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Portfolio tint</span>' +
          '<button class="toggle-btn active" data-s3-port="off" onclick="s3SetPort(\'off\')">Off</button>' +
          '<button class="toggle-btn" data-s3-port="on" onclick="s3SetPort(\'on\')">On</button>' +
        '</div>' +
      '</div>' +
      '<div class="rating-tiles s1-rating-tiles" id="s3-rating-tiles" style="grid-template-columns: repeat(4, 1fr);"></div>' +
      '<div class="group-captions" style="grid-template-columns: repeat(5, 1fr);">' +
        '<div class="gcap gcap-g1"><b>Group 1 · Base count</b>How many bases has the stock built since its 52-week low? Three or more (T1) signals a maturing run; four or more (T2) is the classic "late-stage base" warning.</div>' +
        '<div class="gcap gcap-g2"><b>Group 2 · Price trend rolling over</b>Is the price trend losing momentum? The 200-day moving average is flattening (recent month-on-month change near zero and decelerating), and the 50-day has crossed below the 150-day.</div>' +
        '<div class="gcap gcap-g3"><b>Group 3 · The debate</b>Three confirming distribution signals: down-volume now exceeds up-volume on a 10-day window, recent volatility is rising versus a year-ago baseline, and the price is still within 5% of the 50-day (no decisive breakout up or down).</div>' +
        '<div class="gcap gcap-g4"><b>Group 4 · Lower lows</b>Lower lows count: two or more lower lows in the last month (T8), or three or more in the last three months (T9). Confirms downside structure is forming.</div>' +
        '<div class="gcap gcap-g5"><b>Group 5 · RS trend</b>Has relative strength turned down? Three-month RS change worse than minus five percent. A single test, but on a leading indicator that often turns ahead of price.</div>' +
      '</div>' +
      '<div class="table-wrap">' +
        '<table class="data-table" id="s3-main-table">' +
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
              '<th class="gh-rating grp-start-rating" colspan="2">Stage 3 rating · thresholds 2/10 · 4/10 · 6+/10</th>' +
              '<th class="gh-g1 grp-start-g1 grp-end-g1" colspan="2">Group 1 · Base count</th>' +
              '<th class="gh-g2 grp-start-g2 grp-end-g2" colspan="2">Group 2 · Price trend rolling over</th>' +
              '<th class="gh-g3 grp-start-g3 grp-end-g3" colspan="3">Group 3 · The debate</th>' +
              '<th class="gh-g4 grp-start-g4 grp-end-g4" colspan="2">Group 4 · Lower lows</th>' +
              '<th class="gh-g5 grp-start-g5 grp-end-g5" colspan="1">Group 5 · RS trend</th>' +
              '<th class="gh-persist grp-start-persist" colspan="1">Stage Qualification persistence</th>' +
            '</tr>' +
            '<tr class="col-header-row" id="s3-col-header-row"></tr>' +
          '</thead>' +
          '<tbody id="s3-tbody"></tbody>' +
        '</table>' +
      '</div>';
    host.innerHTML = html;
    var tiles = document.getElementById('s3-rating-tiles');
    if (tiles) {
      tiles.addEventListener('click', function(e) {
        var tile = e.target.closest('.rating-tile');
        if (!tile) return;
        var r = tile.getAttribute('data-rating');
        if (r) s3ToggleRating(r);
      });
    }
    var hdr = document.getElementById('s3-col-header-row');
    if (hdr) {
      hdr.addEventListener('click', function(e) {
        var th = e.target.closest('th');
        if (!th) return;
        var key = th.getAttribute('data-sort-key');
        if (key) s3OnSort(key);
      });
    }
    return true;
  }

  function renderStage3() {
    if (!s3BuildScaffold()) return;
    s3BuildHeaderRow();
    s3RenderRows();
  }
  window.renderStage3 = renderStage3;

})();

/* MD-V2-STAGE3-MARKER-END */
