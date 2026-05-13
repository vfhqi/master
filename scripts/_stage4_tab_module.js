// =============================================================================
// STAGE 4 TAB MODULE — Master Dashboard V2
// =============================================================================
// MD-V2-STAGE4-MARKER — idempotency marker for patcher detection
//
// Stage 4 = Decline / Capitulation. 7 tests across 3 groups.
// Ratings:
//   None       (0)
//   Possible   (1)
//   Plausible  (2)
//   Probable   (3+)
// =============================================================================

/* MD-V2-STAGE4-MARKER-START */

(function() {
  'use strict';

  var s4State = {
    mode: { inputs: 'pct', tests: 'tick' },
    scope: 'all', ratingFilter: null, tint: 'none', port: 'off',
    sort: { col: 'count', dir: 'desc' }
  };

  var S4_COLS = [
    { id:'name',     label:'Company · Ticker',          sortKey:'company', cls:'name-cell' },
    { id:'taxon',    label:'Industry · Sector',         sortKey:'sector', cls:'taxon' },
    { id:'price',    label:'Price',                     sortKey:'price', cls:'num' },
    { id:'high_52w', label:'52 week high',              sortKey:'high_52w', cls:'num' },
    { id:'low_52w',  label:'52 week low',               sortKey:'low_52w', cls:'num' },
    { id:'ma_150',   label:'150 day moving average',    sortKey:'ma_150', cls:'num' },
    { id:'ma_200',   label:'200 day moving average',    sortKey:'ma_200', cls:'num' },
    { id:'rating',   label:'Rating',                    sortKey:'rating_rank', cls:'grp-start-rating' },
    { id:'count',    label:'Score',                     sortKey:'count', cls:'' },
    { id:'g1_t1',    label:'200-day declining',                       sortKey:'g1_t1', cls:'grp-start-g1', testGroup:'g1_price_trends', testKey:'T1' },
    { id:'g1_t2',    label:'200-day decline accelerating',            sortKey:'g1_t2', cls:'grp-end-g1', testGroup:'g1_price_trends', testKey:'T2' },
    { id:'g2_t3',    label:'Full MA stack inverted (P<50<150<200)',   sortKey:'g2_t3', cls:'grp-start-g2', testGroup:'g2_ma_stack', testKey:'T3' },
    { id:'g2_t4',    label:'150-day below 200-day',                   sortKey:'g2_t4', cls:'', testGroup:'g2_ma_stack', testKey:'T4' },
    { id:'g2_t5',    label:'50-day below 150-day',                    sortKey:'g2_t5', cls:'grp-end-g2', testGroup:'g2_ma_stack', testKey:'T5' },
    { id:'g3_t6',    label:'RS absolute weak (vs ind or pctile < 50)', sortKey:'g3_t6', cls:'grp-start-g3', testGroup:'g3_rs', testKey:'T6' },
    { id:'g3_t7',    label:'RS trend weak (3m < -5%)',                 sortKey:'g3_t7', cls:'grp-end-g3', testGroup:'g3_rs', testKey:'T7' },
    { id:'persist',  label:'Last 12 months',            sortKey:'persistence_count', cls:'grp-start-persist' }
  ];
  var S4_RATING_RANK = { 'Probable':4, 'Plausible':3, 'Possible':2, 'None':1 };
  var S4_TINT_CLS = { 'Probable':'tint-prob','Plausible':'tint-pla','Possible':'tint-pos','None':'tint-none' };

  function s4PricesLookup() {
    if (window._s4PricesByTicker) return window._s4PricesByTicker;
    var out = {};
    var arr = (window.MASTER_DATA && MASTER_DATA.prices) || [];
    for (var i = 0; i < arr.length; i++) if (arr[i] && arr[i].ticker) out[arr[i].ticker] = arr[i];
    window._s4PricesByTicker = out;
    return out;
  }
  function s4LiveTickers() {
    var out = {};
    var inv = (window.MASTER_DATA && MASTER_DATA.positions && MASTER_DATA.positions.investments) || [];
    for (var i = 0; i < inv.length; i++) if (inv[i].ticker) out[inv[i].ticker] = true;
    return out;
  }
  function s4LiveSectors() {
    var out = {}, t, prices = s4PricesLookup(), tickers = s4LiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.sector) out[p.sector] = true; }
    return out;
  }
  function s4LiveIndustries() {
    var out = {}, t, prices = s4PricesLookup(), tickers = s4LiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.industry) out[p.industry] = true; }
    return out;
  }
  function s4GetRows() {
    var raw = (window.MASTER_DATA && MASTER_DATA.filters) || [];
    var prices = s4PricesLookup();
    var live = s4LiveTickers(), liveS = s4LiveSectors(), liveI = s4LiveIndustries();
    var rows = [];
    for (var i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || !s.md_v2 || !s.md_v2.stage_4) continue;
      var p = prices[s.ticker] || {};
      var s4 = s.md_v2.stage_4;
      var pers = (s.md_v2.persistence && s.md_v2.persistence.stage_4_persistence) || [];
      var mas = p.mas || {};
      rows.push({
        ticker: s.ticker, company: p.company_name || s.ticker,
        sector: p.sector || '', industry: p.industry || '',
        price: p.price, high_52w: p.high_52w, low_52w: p.low_52w,
        ma_50: mas['50D'], ma_150: mas['150D'], ma_200: mas['200D'],
        rating: s4.rating, count: s4.count,
        tests: s4.tests || {}, groups: s4.groups || {}, persistence: pers,
        rs_sector: p.rs_vs_sector_pct, rs_industry: p.rs_vs_industry_pct, rs_market: p.rs_market_pct,
        is_live: !!live[s.ticker],
        sector_in_portfolio: !!liveS[p.sector],
        industry_in_portfolio: !!liveI[p.industry]
      });
    }
    return rows;
  }
  function s4UniverseCounts(rows) {
    var c = {'Probable':0,'Plausible':0,'Possible':0,'None':0};
    for (var i = 0; i < rows.length; i++) if (c[rows[i].rating] !== undefined) c[rows[i].rating]++;
    return c;
  }

  function s4FmtNum(n) {
    if (n == null || isNaN(n)) return '—';
    var abs = Math.abs(n);
    var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);
    var f = abs.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });
    return n < 0 ? '(' + f + ')' : f;
  }
  function s4FmtPct(p) {
    if (p == null || isNaN(p)) return '—';
    var r = Math.round(p), abs = Math.abs(r);
    return r < 0 ? '(' + abs + ')%' : r + '%';
  }
  // Stage 4 INVERTED scale (same logic as Stage 3 — bearish passes coloured red)
  function s4ColourForIntensity(i) {
    if (i >= 0.6) return '#8b1a1a';
    if (i >= 0.25) return '#a83232';
    if (i >= 0.05) return '#c66666';
    if (i <= -0.6) return '#0a4012';
    if (i <= -0.25) return '#1f6325';
    if (i <= -0.05) return '#4a8050';
    return '#666';
  }
  function s4InputCell(row, key, extraCls) {
    extraCls = extraCls || '';
    var v = row[key];
    if (key === 'price') return '<td class="num ' + extraCls + '">' + s4FmtNum(v) + '</td>';
    if (v == null || row.price == null) return '<td class="num ' + extraCls + '">—</td>';
    var pct = (row.price - v) / v * 100;
    var intensity = 0;
    if (key === 'high_52w') intensity = Math.max(-1, Math.min(1, (-pct - 10) / 20));   // far below high = bearish
    else if (key === 'low_52w') intensity = Math.max(-1, Math.min(1, (20 - pct) / 30)); // near low = bearish
    else if (key === 'ma_150' || key === 'ma_200') intensity = Math.max(-1, Math.min(1, -pct / 10));
    var colour = s4ColourForIntensity(intensity);
    var text = (s4State.mode.inputs === 'pct') ? s4FmtPct(pct) : s4FmtNum(v);
    return '<td class="num ' + extraCls + '" style="color:' + colour + '">' + text + '</td>';
  }

  function s4TestValueFor(row, col) {
    var k = col.testKey;
    var t = row.tests || {};
    // G1: 200D declining + accelerating (binary derived)
    if (k === 'T1') return t.T1_200D_declining ? 'declining' : 'rising/flat';
    if (k === 'T2') return t.T2_200D_decline_accelerating ? 'accel.' : '—';
    // G2: MA stack — show pct gaps
    if (k === 'T3') return t.T3_total_stack_down ? 'P<50<150<200' : '—';
    if (k === 'T4') return row.ma_150 != null && row.ma_200 != null ? s4FmtPct((row.ma_150 - row.ma_200) / row.ma_200 * 100) : '—';
    if (k === 'T5') return row.ma_50 != null && row.ma_150 != null ? s4FmtPct((row.ma_50 - row.ma_150) / row.ma_150 * 100) : '—';
    // G3: RS values
    if (k === 'T6') {
      var bits = [];
      if (row.rs_industry != null) bits.push('ind ' + Math.round(row.rs_industry));
      if (row.rs_sector  != null) bits.push('sec ' + Math.round(row.rs_sector));
      return bits.length ? bits.join(' · ') : '—';
    }
    if (k === 'T7') return t.T7_RS_trend_weak ? '< -5%' : '—';
    return '—';
  }
  function s4TestCell(row, col) {
    var grp = (row.groups || {})[col.testGroup] || {};
    var pass = !!grp[col.testKey];
    var extra = col.cls || '';
    if (s4State.mode.tests === 'val') {
      var v = s4TestValueFor(row, col);
      // Stage 4 passes are BEARISH — colour pass red, fail neutral grey
      var colour = pass ? s4ColourForIntensity(0.7) : '#999';
      return '<td class="test-val ' + extra + '" style="color:' + colour + '">' + v + '</td>';
    }
    if (pass) return '<td class="test-pass-bear ' + extra + '"><span class="tick">✓</span></td>';
    return '<td class="test-fail ' + extra + '">·</td>';
  }

  function s4PillFor(rating, count) {
    if (rating === 'Probable') {
      var c = Math.min(Math.max(count, 3), 7);
      return '<span class="pill pill-prob-' + c + '">Probable</span>';
    }
    if (rating === 'Plausible') return '<span class="pill pill-pla">Plausible</span>';
    if (rating === 'Possible') return '<span class="pill pill-pos">Possible</span>';
    return '<span class="pill pill-none">None</span>';
  }
  function s4ScorePips(row) {
    var t = row.tests;
    var passed = [
      !!t.T1_200D_declining, !!t.T2_200D_decline_accelerating,
      !!t.T3_total_stack_down, !!t.T4_150_below_200, !!t.T5_50_below_150,
      !!t.T6_RS_absolute_weak, !!t.T7_RS_trend_weak
    ];
    var count = passed.filter(Boolean).length;
    var s = '';
    for (var i = 0; i < 7; i++) s += '<span class="pip pip-bear ' + (passed[i] ? 'on' : '') + '"></span>';
    return '<div class="score-pip-row">' + s + '<span class="score-num">' + count + '/7</span></div>';
  }
  function s4PersistCells(arr, rating) {
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

  function s4HashColor(label, alpha) {
    if (!label) return null;
    var h = 0;
    for (var i = 0; i < label.length; i++) h = (h * 31 + label.charCodeAt(i)) & 0xffff;
    return 'hsla(' + (h % 360) + ', 35%, 55%, ' + alpha + ')';
  }
  function s4PortfolioInfo(row) {
    if (row.is_live) return { color:'#1b5e20', bg:'rgba(27,94,32,0.10)', bgHover:'rgba(27,94,32,0.14)' };
    if (row.sector_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.05)', bgHover:'rgba(27,94,32,0.08)' };
    if (row.industry_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.025)', bgHover:'rgba(27,94,32,0.05)' };
    return null;
  }

  function s4GetSortVal(row, key) {
    if (key === 'rating_rank') return S4_RATING_RANK[row.rating] || 0;
    if (key === 'persistence_count') return (row.persistence || []).filter(Boolean).length;
    if (key.indexOf('g') === 0 && key.indexOf('_t') > 0) {
      var col = S4_COLS.find(function(c) { return c.sortKey === key; });
      if (col) {
        var grp = (row.groups || {})[col.testGroup] || {};
        return grp[col.testKey] ? 1 : 0;
      }
    }
    var PCT_KEYS = ['high_52w','low_52w','ma_150','ma_200'];
    if (PCT_KEYS.indexOf(key) > -1 && s4State.mode.inputs === 'pct') {
      var ref = row[key];
      if (ref == null || row.price == null || ref === 0) return -Infinity;
      return (row.price - ref) / ref * 100;
    }
    if (key in row) return row[key];
    return 0;
  }
  function s4OnSort(key) {
    if (s4State.sort.col === key) s4State.sort.dir = s4State.sort.dir === 'desc' ? 'asc' : 'desc';
    else s4State.sort = { col: key, dir: 'desc' };
    s4BuildHeaderRow();
    s4RenderRows();
  }

  function s4BuildHeaderRow() {
    var tr = document.getElementById('s4-col-header-row');
    if (!tr) return;
    var h = '';
    for (var i = 0; i < S4_COLS.length; i++) {
      var c = S4_COLS[i];
      var isSort = s4State.sort.col === c.sortKey;
      var arrow = isSort
        ? '<span class="sort-arrow">' + (s4State.sort.dir === 'desc' ? '▼' : '▲') + '</span>'
        : '<span class="sort-placeholder"></span>';
      h += '<th class="' + (c.cls || '') + '" data-sort-key="' + c.sortKey + '" title="' + c.label + '">' +
           '<span class="hd"><span class="lbl">' + c.label + '</span>' + arrow + '</span></th>';
    }
    tr.innerHTML = h;
  }
  function s4RatingTiles(rows) {
    var tiles = document.getElementById('s4-rating-tiles');
    if (!tiles) return;
    var uc = s4UniverseCounts(rows);
    var total = rows.length;
    var order = ['None','Possible','Plausible','Probable'];
    var strip = {'Probable':'prob','Plausible':'pla','Possible':'pos','None':'none'};
    var h = '';
    for (var i = 0; i < order.length; i++) {
      var r = order[i], cnt = uc[r] || 0;
      var act = s4State.ratingFilter === r ? ' active' : '';
      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;
      h += '<div class="rating-tile ' + S4_TINT_CLS[r] + act + '" data-rating="' + r + '">' +
           '<div class="rt-label">' + r + '</div>' +
           '<div class="rt-count">' + cnt.toLocaleString('en-GB') + '</div>' +
           '<div class="rt-sub">of ' + total.toLocaleString('en-GB') + ' · ' + pct + '%</div>' +
           '<div class="rt-strip rt-strip-' + strip[r] + '"></div>' +
           '</div>';
    }
    tiles.innerHTML = h;
  }
  function s4UpdateScopeCounts(rows) {
    function set(id, n) { var el = document.getElementById(id); if (el) el.textContent = '(' + n + ')'; }
    set('s4-cnt-all',      rows.length);
    set('s4-cnt-live',     rows.filter(function(r){ return r.is_live; }).length);
    set('s4-cnt-sector',   rows.filter(function(r){ return r.sector_in_portfolio; }).length);
    set('s4-cnt-industry', rows.filter(function(r){ return r.industry_in_portfolio; }).length);
  }

  function s4RenderRows() {
    var tbody = document.getElementById('s4-tbody');
    if (!tbody) return;
    var all = s4GetRows();
    s4UpdateScopeCounts(all);
    s4RatingTiles(all);
    var rows = all.slice();
    if (s4State.scope === 'live') rows = rows.filter(function(r){ return r.is_live; });
    else if (s4State.scope === 'sector') rows = rows.filter(function(r){ return r.sector_in_portfolio; });
    else if (s4State.scope === 'industry') rows = rows.filter(function(r){ return r.industry_in_portfolio; });
    if (s4State.ratingFilter) rows = rows.filter(function(r){ return r.rating === s4State.ratingFilter; });
    rows.sort(function(a,b) {
      var va = s4GetSortVal(a, s4State.sort.col), vb = s4GetSortVal(b, s4State.sort.col);
      var cmp = (typeof va === 'string') ? va.localeCompare(vb) : (va || 0) - (vb || 0);
      if (cmp === 0) cmp = a.ticker.localeCompare(b.ticker);
      return s4State.sort.dir === 'desc' ? -cmp : cmp;
    });
    var html = '';
    for (var i = 0; i < rows.length; i++) {
      var s = rows[i];
      var styles = [], cls = [];
      if (s4State.tint === 'industry') { styles.push('--tint-bg: ' + s4HashColor(s.industry, 0.16)); cls.push('tint-row'); }
      else if (s4State.tint === 'sector') { styles.push('--tint-bg: ' + s4HashColor(s.sector, 0.16)); cls.push('tint-row'); }
      if (s4State.port === 'on') {
        var pi = s4PortfolioInfo(s);
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
        s4InputCell(s, 'price') + s4InputCell(s, 'high_52w') + s4InputCell(s, 'low_52w') +
        s4InputCell(s, 'ma_150') + s4InputCell(s, 'ma_200') +
        '<td class="grp-start-rating">' + s4PillFor(s.rating, s.count) + '</td>' +
        '<td>' + s4ScorePips(s) + '</td>';
      for (var j = 9; j <= 15; j++) html += s4TestCell(s, S4_COLS[j]);
      html += '<td class="grp-start-persist">' + s4PersistCells(s.persistence, s.rating) + '</td>' +
        '</tr>';
    }
    tbody.innerHTML = html;
  }

  function s4SetMode(kind, val) {
    s4State.mode[kind] = val;
    var btns = document.querySelectorAll('button[data-s4-grp="' + kind + '"]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-s4-val') === val);
    s4RenderRows();
  }
  function s4SetScope(s) {
    s4State.scope = s;
    var btns = document.querySelectorAll('button[data-s4-scope]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-s4-scope') === s);
    s4RenderRows();
  }
  function s4SetTint(t) {
    s4State.tint = t;
    var btns = document.querySelectorAll('button[data-s4-tint]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-s4-tint') === t);
    s4RenderRows();
  }
  function s4SetPort(p) {
    s4State.port = p;
    var btns = document.querySelectorAll('button[data-s4-port]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-s4-port') === p);
    s4RenderRows();
  }
  function s4ToggleRating(r) {
    s4State.ratingFilter = (s4State.ratingFilter === r) ? null : r;
    s4RenderRows();
  }
  window.s4SetMode = s4SetMode;
  window.s4SetScope = s4SetScope;
  window.s4SetTint = s4SetTint;
  window.s4SetPort = s4SetPort;
  window.s4ToggleRating = s4ToggleRating;
  window.s4OnSort = s4OnSort;

  function s4BuildScaffold() {
    var host = document.getElementById('tab-stage_4');
    if (!host) return false;
    if (host.querySelector('#s4-main-table')) return true;
    var html = '' +
      '<div class="s1-intro">Stage 4 looks for stocks in confirmed decline: the 200-day moving average is falling and (often) accelerating downward, the full moving-average stack is inverted (price below 50-day below 150-day below 200-day), and relative strength is weak both in absolute level and trend. The aim is to identify capitulation candidates eligible for the pullback-tranche playbook on rebound, and to flag positions that should be exited if held. Seven tests across three groups: more tests passing means the decline is more entrenched.</div>' +
      '<div class="controls s1-controls">' +
        '<div class="ctrl-grp"><span class="ctrl-label">Inputs</span>' +
          '<button class="toggle-btn active" data-s4-grp="inputs" data-s4-val="pct" onclick="s4SetMode(\'inputs\',\'pct\')">show as %</button>' +
          '<button class="toggle-btn" data-s4-grp="inputs" data-s4-val="raw" onclick="s4SetMode(\'inputs\',\'raw\')">show as numbers</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Tests</span>' +
          '<button class="toggle-btn active" data-s4-grp="tests" data-s4-val="tick" onclick="s4SetMode(\'tests\',\'tick\')">show ticks</button>' +
          '<button class="toggle-btn" data-s4-grp="tests" data-s4-val="val" onclick="s4SetMode(\'tests\',\'val\')">show test values</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Scope</span>' +
          '<button class="toggle-btn active" data-s4-scope="all" onclick="s4SetScope(\'all\')">All <span id="s4-cnt-all"></span></button>' +
          '<button class="toggle-btn" data-s4-scope="live" onclick="s4SetScope(\'live\')">Live <span id="s4-cnt-live"></span></button>' +
          '<button class="toggle-btn" data-s4-scope="sector" onclick="s4SetScope(\'sector\')">Sectors <span id="s4-cnt-sector"></span></button>' +
          '<button class="toggle-btn" data-s4-scope="industry" onclick="s4SetScope(\'industry\')">Industries <span id="s4-cnt-industry"></span></button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Peers</button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Cohorts</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Colour by</span>' +
          '<button class="toggle-btn active" data-s4-tint="none" onclick="s4SetTint(\'none\')">Off</button>' +
          '<button class="toggle-btn" data-s4-tint="industry" onclick="s4SetTint(\'industry\')">Industry</button>' +
          '<button class="toggle-btn" data-s4-tint="sector" onclick="s4SetTint(\'sector\')">Sector</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Portfolio tint</span>' +
          '<button class="toggle-btn active" data-s4-port="off" onclick="s4SetPort(\'off\')">Off</button>' +
          '<button class="toggle-btn" data-s4-port="on" onclick="s4SetPort(\'on\')">On</button>' +
        '</div>' +
      '</div>' +
      '<div class="rating-tiles s1-rating-tiles" id="s4-rating-tiles" style="grid-template-columns: repeat(4, 1fr);"></div>' +
      '<div class="group-captions" style="grid-template-columns: repeat(3, 1fr);">' +
        '<div class="gcap gcap-g1"><b>Group 1 · Price trend down</b>Is the long-term trend confirmed down? The 200-day moving average is now lower month-on-month (T1), and the rate of decline is accelerating (T2). Two foundational decline signals.</div>' +
        '<div class="gcap gcap-g2"><b>Group 2 · Moving-average stack inverted</b>Three structural tests of an inverted MA stack: full inversion P&lt;50&lt;150&lt;200 (T3), 150-day below 200-day (T4), and 50-day below 150-day (T5). Together: the stock has rolled over across all three time-horizon trends.</div>' +
        '<div class="gcap gcap-g3"><b>Group 3 · Relative strength weak</b>Is relative strength weak both in absolute level and trend? RS percentile or vs-industry below 50 (T6), and three-month RS change worse than minus five percent (T7).</div>' +
      '</div>' +
      '<div class="table-wrap">' +
        '<table class="data-table" id="s4-main-table">' +
          '<colgroup>' +
            '<col class="c-name"><col class="c-taxon">' +
            '<col class="c-price"><col class="c-52wh"><col class="c-52wl">' +
            '<col class="c-ma150"><col class="c-ma200">' +
            '<col class="c-rating"><col class="c-score">' +
            '<col class="c-test"><col class="c-test"><col class="c-test"><col class="c-test"><col class="c-test"><col class="c-test"><col class="c-test">' +
            '<col class="c-persist">' +
          '</colgroup>' +
          '<thead>' +
            '<tr class="group-header-row">' +
              '<th class="gh-inputs" colspan="7">Inputs</th>' +
              '<th class="gh-rating grp-start-rating" colspan="2">Stage 4 rating · thresholds 1/7 · 2/7 · 3+/7</th>' +
              '<th class="gh-g1 grp-start-g1 grp-end-g1" colspan="2">Group 1 · Price trend down</th>' +
              '<th class="gh-g2 grp-start-g2 grp-end-g2" colspan="3">Group 2 · MA stack inverted</th>' +
              '<th class="gh-g3 grp-start-g3 grp-end-g3" colspan="2">Group 3 · RS weak</th>' +
              '<th class="gh-persist grp-start-persist" colspan="1">Stage Qualification persistence</th>' +
            '</tr>' +
            '<tr class="col-header-row" id="s4-col-header-row"></tr>' +
          '</thead>' +
          '<tbody id="s4-tbody"></tbody>' +
        '</table>' +
      '</div>';
    host.innerHTML = html;
    var tiles = document.getElementById('s4-rating-tiles');
    if (tiles) {
      tiles.addEventListener('click', function(e) {
        var tile = e.target.closest('.rating-tile');
        if (!tile) return;
        var r = tile.getAttribute('data-rating');
        if (r) s4ToggleRating(r);
      });
    }
    var hdr = document.getElementById('s4-col-header-row');
    if (hdr) {
      hdr.addEventListener('click', function(e) {
        var th = e.target.closest('th');
        if (!th) return;
        var key = th.getAttribute('data-sort-key');
        if (key) s4OnSort(key);
      });
    }
    return true;
  }

  function renderStage4() {
    if (!s4BuildScaffold()) return;
    s4BuildHeaderRow();
    s4RenderRows();
  }
  window.renderStage4 = renderStage4;

})();

/* MD-V2-STAGE4-MARKER-END */
