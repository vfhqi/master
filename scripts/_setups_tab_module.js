// =============================================================================
// SETUPS TAB MODULE - Master Dashboard V2
// =============================================================================
// MD-V2-SETUPS-MARKER - idempotency marker for patcher detection
//
// Setups = 4 capital-deployment-eligibility patterns from _md_v2_screens.py.
// Each setup is the AND of constituent tests; each test gets its own column.
//
// SETUPS:
//   Probing Bet (2 tests):
//     - Any-of: S1 qualifying OR S3 invalidation OR S4 qualifying OR Collapsing
//     - Breakout pattern
//   VCP after S1->2 plateau (3 tests):
//     - S1 to S2 transition
//     - Higher-lows >= 2 (VCP pattern)
//     - Breakout
//   UTR after S2 pullback (3 tests):
//     - S2 uptrend
//     - Pullback-to-retest pattern
//     - UTR capital stage OR Breakout
//   VCP after S2 base (4 tests):
//     - S2 uptrend
//     - Basing-below-high pattern
//     - Higher-lows >= 2 (VCP pattern)
//     - Breakout
// =============================================================================

/* MD-V2-SETUPS-MARKER-START */

(function() {
  'use strict';

  var stState = {
    mode: { inputs: 'pct' },
    scope: 'all',
    setupFilter: null,
    tint: 'none',
    port: 'off',
    sort: { col: 'company', dir: 'asc' }
  };

  var ST_SETUPS = [
    {
      key: 'probing_bet', label: 'Probing Bet', tone: 'amber',
      tooltip: 'Stage 1/3/4 qualifying OR Collapsing indicator, plus Breakout',
      tests: [
        { key: 'any_of_s1_s3_s4_collapsing', label: 'S1/S3/S4 qual or Collapsing', tooltip: 'Stage 1 in Plausible/ProbableEarly/ProbableLate OR Stage 3 in Plausible/ProbableInvalidation OR Stage 4 in Plausible/Probable OR Collapsing indicator' },
        { key: 'breakout',                    label: 'Breakout',                  tooltip: 'Breakout pattern (parent post-indicator)' }
      ]
    },
    {
      key: 'vcp_after_s1_plateau', label: 'VCP after S1->2 plateau', tone: 'green',
      tooltip: 'S1 in Probable Early/Late AND S2 in Possible/Plausible AND VCP pattern (higher lows >= 2) AND Breakout',
      tests: [
        { key: 's1_to_s2_transition', label: 'S1->2 transition', tooltip: 'Stage 1 in Probable Early/Late AND Stage 2 in Possible/Plausible' },
        { key: 'higher_lows_ge_2',    label: 'Higher lows >= 2', tooltip: 'At least 2 unbroken higher lows (VCP pattern)' },
        { key: 'breakout',            label: 'Breakout',         tooltip: 'Breakout pattern' }
      ]
    },
    {
      key: 'utr_after_s2_pullback', label: 'UTR after S2 pullback', tone: 'teal',
      tooltip: 'S2 uptrend AND Pullback indicator AND (UTR capital stage OR Breakout)',
      tests: [
        { key: 'is_s2_uptrend',           label: 'S2 uptrend',           tooltip: 'Stage 2 in Probable or Plausible' },
        { key: 'pullback_to_retest',      label: 'Pullback indicator',   tooltip: 'Pullback-to-retest pattern (parent pre-indicator)' },
        { key: 'utr_capital_or_breakout', label: 'UTR Capital or Breakout', tooltip: 'Uptrend-retest stage = Capital OR Breakout pattern fires' }
      ]
    },
    {
      key: 'vcp_after_s2_base', label: 'VCP after S2 base', tone: 'navy',
      tooltip: 'S2 uptrend AND Basing indicator AND VCP pattern AND Breakout',
      tests: [
        { key: 'is_s2_uptrend',       label: 'S2 uptrend',        tooltip: 'Stage 2 in Probable or Plausible' },
        { key: 'basing_below_high',   label: 'Basing indicator',  tooltip: 'Basing-below-high pattern' },
        { key: 'higher_lows_ge_2',    label: 'Higher lows >= 2',  tooltip: 'At least 2 unbroken higher lows (VCP pattern)' },
        { key: 'breakout',            label: 'Breakout',          tooltip: 'Breakout pattern' }
      ]
    }
  ];

  function buildCols() {
    var cols = [
      { id:'name',     label:'Company - Ticker',     sortKey:'company',  cls:'name-cell' },
      { id:'taxon',    label:'Industry - Sector',    sortKey:'sector',   cls:'taxon' },
      { id:'price',    label:'Price',                sortKey:'price',    cls:'num' },
      { id:'high_52w', label:'52 week high',         sortKey:'high_52w', cls:'num' },
      { id:'pullback', label:'Recent pullback',      sortKey:'recent_pullback', cls:'num' },
      { id:'hlow',     label:'Higher lows',          sortKey:'higher_lows', cls:'num' }
    ];
    for (var s = 0; s < ST_SETUPS.length; s++) {
      var setup = ST_SETUPS[s];
      for (var t = 0; t < setup.tests.length; t++) {
        var test = setup.tests[t];
        var firstInGroup = (t === 0);
        var lastInGroup = (t === setup.tests.length - 1);
        var cls = '';
        if (firstInGroup) cls += 'grp-start-g' + (s+1) + ' ';
        if (lastInGroup) cls += 'grp-end-g' + (s+1);
        cols.push({
          id: 's' + (s+1) + 't' + (t+1),
          label: test.label,
          sortKey: setup.key + '__' + test.key,
          cls: cls.trim(),
          tooltip: test.tooltip,
          setupKey: setup.key,
          testKey: test.key,
          tone: setup.tone
        });
      }
    }
    return cols;
  }
  var ST_COLS = buildCols();

  function stPricesLookup() {
    if (window._stPricesByTicker) return window._stPricesByTicker;
    var out = {};
    var arr = (window.MASTER_DATA && MASTER_DATA.prices) || [];
    for (var i = 0; i < arr.length; i++) if (arr[i] && arr[i].ticker) out[arr[i].ticker] = arr[i];
    window._stPricesByTicker = out;
    return out;
  }
  function stLiveTickers() {
    var out = {};
    var inv = (window.MASTER_DATA && MASTER_DATA.positions && MASTER_DATA.positions.investments) || [];
    for (var i = 0; i < inv.length; i++) if (inv[i].ticker) out[inv[i].ticker] = true;
    return out;
  }
  function stLiveSectors() {
    var out = {}, t, prices = stPricesLookup(), tickers = stLiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.sector) out[p.sector] = true; }
    return out;
  }
  function stLiveIndustries() {
    var out = {}, t, prices = stPricesLookup(), tickers = stLiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.industry) out[p.industry] = true; }
    return out;
  }

  function stEvalTest(row, testKey) {
    var ind = row.indicators || {};
    var md = row.md_v2 || {};
    var s1r = (md.stage_1 && md.stage_1.rating) || '';
    var s2r = (md.stage_2 && md.stage_2.rating) || '';
    var s3r = (md.stage_3 && md.stage_3.rating) || '';
    var s4r = (md.stage_4 && md.stage_4.rating) || '';
    if (testKey === 'any_of_s1_s3_s4_collapsing') {
      var s1q = s1r === 'Plausible' || s1r === 'Probable Early' || s1r === 'Probable Late';
      var s3q = s3r === 'Plausible Invalidation' || s3r === 'Probable Invalidation';
      var s4q = s4r === 'Plausible' || s4r === 'Probable';
      return s1q || s3q || s4q || !!ind.collapsing;
    }
    if (testKey === 'breakout') return !!ind.breakout;
    if (testKey === 'is_s2_uptrend') return s2r === 'Probable' || s2r === 'Plausible';
    if (testKey === 's1_to_s2_transition') {
      var s1t = s1r === 'Probable Late' || s1r === 'Probable Early';
      var s2t = s2r === 'Possible' || s2r === 'Plausible';
      return s1t && s2t;
    }
    if (testKey === 'higher_lows_ge_2') {
      return (row.higher_lows != null) && row.higher_lows >= 2;
    }
    if (testKey === 'pullback_to_retest') return !!ind.pullback_to_retest;
    if (testKey === 'utr_capital_or_breakout') {
      var utrCap = row.utr_stage === 'Capital';
      return utrCap || !!ind.breakout;
    }
    if (testKey === 'basing_below_high') return !!ind.basing_below_high;
    return false;
  }

  function stGetRows() {
    var raw = (window.MASTER_DATA && MASTER_DATA.filters) || [];
    var prices = stPricesLookup();
    var live = stLiveTickers(), liveS = stLiveSectors(), liveI = stLiveIndustries();
    var rows = [];
    for (var i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || !s.md_v2 || !s.md_v2.setups) continue;
      var p = prices[s.ticker] || {};
      var utr = (s.uptrend_retest && s.uptrend_retest.stage) || null;
      rows.push({
        ticker: s.ticker, company: p.company_name || s.ticker,
        sector: p.sector || '', industry: p.industry || '',
        price: p.price, high_52w: p.high_52w,
        recent_pullback: p.recent_pullback_pct,
        higher_lows: p.higher_lows,
        utr_stage: utr,
        indicators: s.md_v2.indicators || {},
        setups: s.md_v2.setups || {},
        md_v2: s.md_v2,
        is_live: !!live[s.ticker],
        sector_in_portfolio: !!liveS[p.sector],
        industry_in_portfolio: !!liveI[p.industry]
      });
    }
    return rows;
  }
  function stSetupCounts(rows) {
    var c = {};
    for (var k = 0; k < ST_SETUPS.length; k++) c[ST_SETUPS[k].key] = 0;
    for (var i = 0; i < rows.length; i++) {
      var su = rows[i].setups || {};
      for (var key in c) if (su[key]) c[key]++;
    }
    return c;
  }

  function stFmtNum(n) {
    if (n == null || isNaN(n)) return '-';
    var abs = Math.abs(n);
    var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);
    var f = abs.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });
    return n < 0 ? '(' + f + ')' : f;
  }
  function stFmtPct(p) {
    if (p == null || isNaN(p)) return '-';
    var r = Math.round(p), abs = Math.abs(r);
    return r < 0 ? '(' + abs + ')%' : r + '%';
  }
  function stColourForIntensity(i) {
    if (i >= 0.6) return '#0F6E56';
    if (i >= 0.25) return '#1D9E75';
    if (i >= 0.05) return '#5DCAA5';
    if (i <= -0.6) return '#A32D2D';
    if (i <= -0.25) return '#E24B4A';
    if (i <= -0.05) return '#F09595';
    return '#888';
  }
  function stInputCell(row, key, extraCls) {
    extraCls = extraCls || '';
    var v = row[key];
    if (key === 'price') return '<td class="num ' + extraCls + '">' + stFmtNum(v) + '</td>';
    if (key === 'higher_lows') {
      if (v == null) return '<td class="num ' + extraCls + '">-</td>';
      return '<td class="num ' + extraCls + '">' + v + '</td>';
    }
    if (key === 'recent_pullback') {
      if (v == null) return '<td class="num ' + extraCls + '">-</td>';
      var pctVal = v * 100;
      return '<td class="num ' + extraCls + '">' + Math.round(pctVal) + '%</td>';
    }
    if (v == null || row.price == null) return '<td class="num ' + extraCls + '">-</td>';
    var pct = (row.price - v) / v * 100;
    var text = (stState.mode.inputs === 'pct') ? stFmtPct(pct) : stFmtNum(v);
    return '<td class="num ' + extraCls + '">' + text + '</td>';
  }

  function stTestCell(row, col) {
    var pass = stEvalTest(row, col.testKey);
    var extra = col.cls || '';
    if (pass) return '<td class="st-pass st-tone-' + (col.tone || 'amber') + ' ' + extra + '"><span class="tick">' + String.fromCharCode(10003) + '</span></td>';
    return '<td class="st-fail ' + extra + '">.</td>';
  }

  function stHashColor(label, alpha) {
    if (!label) return null;
    var h = 0;
    for (var i = 0; i < label.length; i++) h = (h * 31 + label.charCodeAt(i)) & 0xffff;
    return 'hsla(' + (h % 360) + ', 35%, 55%, ' + alpha + ')';
  }
  function stPortfolioInfo(row) {
    if (row.is_live) return { color:'#1b5e20', bg:'rgba(27,94,32,0.10)', bgHover:'rgba(27,94,32,0.14)' };
    if (row.sector_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.05)', bgHover:'rgba(27,94,32,0.08)' };
    if (row.industry_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.025)', bgHover:'rgba(27,94,32,0.05)' };
    return null;
  }

  function stGetSortVal(row, key) {
    if (key.indexOf('__') > 0) {
      var parts = key.split('__');
      return stEvalTest(row, parts[1]) ? 1 : 0;
    }
    if (key === 'recent_pullback') return row.recent_pullback == null ? -Infinity : row.recent_pullback;
    if (key === 'higher_lows')     return row.higher_lows == null ? -Infinity : row.higher_lows;
    if (key in row) return row[key];
    return 0;
  }
  function stOnSort(key) {
    if (stState.sort.col === key) stState.sort.dir = stState.sort.dir === 'desc' ? 'asc' : 'desc';
    else stState.sort = { col: key, dir: key === 'company' ? 'asc' : 'desc' };
    stBuildHeaderRow();
    stRenderRows();
  }

  function stBuildHeaderRow() {
    var tr = document.getElementById('st-col-header-row');
    if (!tr) return;
    var h = '';
    for (var i = 0; i < ST_COLS.length; i++) {
      var c = ST_COLS[i];
      var isSort = stState.sort.col === c.sortKey;
      var arrow = isSort
        ? '<span class="sort-arrow">' + (stState.sort.dir === 'desc' ? String.fromCharCode(9660) : String.fromCharCode(9650)) + '</span>'
        : '<span class="sort-placeholder"></span>';
      var title = c.tooltip || c.label;
      h += '<th class="' + (c.cls || '') + '" data-sort-key="' + c.sortKey + '" title="' + title + '">' +
           '<span class="hd"><span class="lbl">' + c.label + '</span>' + arrow + '</span></th>';
    }
    tr.innerHTML = h;
  }

  function stSetupTiles(rows) {
    var tiles = document.getElementById('st-setup-tiles');
    if (!tiles) return;
    var counts = stSetupCounts(rows);
    var total = rows.length;
    var h = '';
    for (var i = 0; i < ST_SETUPS.length; i++) {
      var setup = ST_SETUPS[i];
      var cnt = counts[setup.key] || 0;
      var act = stState.setupFilter === setup.key ? ' active' : '';
      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;
      h += '<div class="rating-tile st-tile-' + setup.tone + act + '" data-setup="' + setup.key + '" title="' + setup.tooltip + '">' +
           '<div class="rt-label">' + setup.label + '</div>' +
           '<div class="rt-count">' + cnt.toLocaleString('en-GB') + '</div>' +
           '<div class="rt-sub">of ' + total.toLocaleString('en-GB') + ' . ' + pct + '%</div>' +
           '<div class="rt-strip st-strip-' + setup.tone + '"></div>' +
           '</div>';
    }
    tiles.innerHTML = h;
  }

  function stUpdateScopeCounts(rows) {
    function set(id, n) { var el = document.getElementById(id); if (el) el.textContent = '(' + n + ')'; }
    set('st-cnt-all',      rows.length);
    set('st-cnt-live',     rows.filter(function(r){ return r.is_live; }).length);
    set('st-cnt-sector',   rows.filter(function(r){ return r.sector_in_portfolio; }).length);
    set('st-cnt-industry', rows.filter(function(r){ return r.industry_in_portfolio; }).length);
  }

  function stRenderRows() {
    var tbody = document.getElementById('st-tbody');
    if (!tbody) return;
    var all = stGetRows();
    stUpdateScopeCounts(all);
    stSetupTiles(all);
    var rows = all.slice();
    if (stState.scope === 'live') rows = rows.filter(function(r){ return r.is_live; });
    else if (stState.scope === 'sector') rows = rows.filter(function(r){ return r.sector_in_portfolio; });
    else if (stState.scope === 'industry') rows = rows.filter(function(r){ return r.industry_in_portfolio; });
    if (stState.setupFilter) {
      var key = stState.setupFilter;
      rows = rows.filter(function(r){ return !!(r.setups || {})[key]; });
    }
    rows.sort(function(a,b) {
      var va = stGetSortVal(a, stState.sort.col), vb = stGetSortVal(b, stState.sort.col);
      var cmp = (typeof va === 'string') ? va.localeCompare(vb) : (va || 0) - (vb || 0);
      if (cmp === 0) cmp = a.ticker.localeCompare(b.ticker);
      return stState.sort.dir === 'desc' ? -cmp : cmp;
    });
    var html = '';
    for (var i = 0; i < rows.length; i++) {
      var s = rows[i];
      var styles = [], cls = [];
      if (stState.tint === 'industry') { styles.push('--tint-bg: ' + stHashColor(s.industry, 0.16)); cls.push('tint-row'); }
      else if (stState.tint === 'sector') { styles.push('--tint-bg: ' + stHashColor(s.sector, 0.16)); cls.push('tint-row'); }
      if (stState.port === 'on') {
        var pi = stPortfolioInfo(s);
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
        stInputCell(s, 'price') + stInputCell(s, 'high_52w') + stInputCell(s, 'recent_pullback') + stInputCell(s, 'higher_lows');
      for (var j = 6; j < ST_COLS.length; j++) html += stTestCell(s, ST_COLS[j]);
      html += '</tr>';
    }
    tbody.innerHTML = html;
  }

  function stSetMode(kind, val) {
    stState.mode[kind] = val;
    var btns = document.querySelectorAll('button[data-st-grp="' + kind + '"]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-st-val') === val);
    stRenderRows();
  }
  function stSetScope(s) {
    stState.scope = s;
    var btns = document.querySelectorAll('button[data-st-scope]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-st-scope') === s);
    stRenderRows();
  }
  function stSetTint(t) {
    stState.tint = t;
    var btns = document.querySelectorAll('button[data-st-tint]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-st-tint') === t);
    stRenderRows();
  }
  function stSetPort(p) {
    stState.port = p;
    var btns = document.querySelectorAll('button[data-st-port]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-st-port') === p);
    stRenderRows();
  }
  function stToggleSetup(k) {
    stState.setupFilter = (stState.setupFilter === k) ? null : k;
    stRenderRows();
  }
  window.stSetMode = stSetMode;
  window.stSetScope = stSetScope;
  window.stSetTint = stSetTint;
  window.stSetPort = stSetPort;
  window.stToggleSetup = stToggleSetup;
  window.stOnSort = stOnSort;

  function stBuildScaffold() {
    var host = document.getElementById('tab-setups');
    if (!host) return false;
    if (host.querySelector('#st-main-table')) return true;

    var colgroupHtml = '<col class="c-name"><col class="c-taxon"><col class="c-price"><col class="c-52wh"><col class="c-pullback"><col class="c-hlow">';
    var inputsColspan = 6;
    var groupHeaderHtml = '<th class="gh-inputs" colspan="' + inputsColspan + '">Inputs</th>';
    for (var s = 0; s < ST_SETUPS.length; s++) {
      var setup = ST_SETUPS[s];
      var n = setup.tests.length;
      for (var t = 0; t < n; t++) colgroupHtml += '<col class="c-test">';
      var startCls = 'grp-start-g' + (s+1);
      var endCls = 'grp-end-g' + (s+1);
      groupHeaderHtml += '<th class="gh-g' + (s+1) + ' ' + startCls + ' ' + endCls + '" colspan="' + n + '">' + setup.label + '</th>';
    }

    var html = '' +
      '<div class="s1-intro">Setups are four capital-deployment-eligibility patterns. Each setup is the AND of two to four constituent tests, shown as individual tick columns. Probing Bet (stage qualifying or Collapsing + Breakout) suggests a rebound candidate; the three Core MM setups (VCP after S1->2 plateau, UTR after S2 pullback, VCP after S2 base) suggest a stock ready for full position deployment. Click a tile to filter the table to the parent setup; click again to clear.</div>' +
      '<div class="controls s1-controls">' +
        '<div class="ctrl-grp"><span class="ctrl-label">Inputs</span>' +
          '<button class="toggle-btn active" data-st-grp="inputs" data-st-val="pct" onclick="stSetMode(\'inputs\',\'pct\')">show as %</button>' +
          '<button class="toggle-btn" data-st-grp="inputs" data-st-val="raw" onclick="stSetMode(\'inputs\',\'raw\')">show as numbers</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Scope</span>' +
          '<button class="toggle-btn active" data-st-scope="all" onclick="stSetScope(\'all\')">All <span id="st-cnt-all"></span></button>' +
          '<button class="toggle-btn" data-st-scope="live" onclick="stSetScope(\'live\')">Live <span id="st-cnt-live"></span></button>' +
          '<button class="toggle-btn" data-st-scope="sector" onclick="stSetScope(\'sector\')">Sectors <span id="st-cnt-sector"></span></button>' +
          '<button class="toggle-btn" data-st-scope="industry" onclick="stSetScope(\'industry\')">Industries <span id="st-cnt-industry"></span></button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Peers</button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Cohorts</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Colour by</span>' +
          '<button class="toggle-btn active" data-st-tint="none" onclick="stSetTint(\'none\')">Off</button>' +
          '<button class="toggle-btn" data-st-tint="industry" onclick="stSetTint(\'industry\')">Industry</button>' +
          '<button class="toggle-btn" data-st-tint="sector" onclick="stSetTint(\'sector\')">Sector</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Portfolio tint</span>' +
          '<button class="toggle-btn active" data-st-port="off" onclick="stSetPort(\'off\')">Off</button>' +
          '<button class="toggle-btn" data-st-port="on" onclick="stSetPort(\'on\')">On</button>' +
        '</div>' +
      '</div>' +
      '<div class="rating-tiles s1-rating-tiles" id="st-setup-tiles"></div>' +
      '<div class="group-captions">' +
        '<div class="gcap gcap-g1"><b>Probing Bet</b>Setup for the probing-bet tranche - a small initial allocation when a stock has collapsed or is in a struggling stage but shows a fresh breakout. Two tests.</div>' +
        '<div class="gcap gcap-g2"><b>VCP after S1->2 plateau</b>Core MM setup - stock transitioning from Stage 1 to Stage 2 with a VCP (volatility contraction) pattern and a fresh breakout. Three tests.</div>' +
        '<div class="gcap gcap-g3"><b>UTR after S2 pullback</b>Core MM setup - stock in established Stage 2 uptrend, has pulled back to retest a moving average, and is now breaking back up. Three tests.</div>' +
        '<div class="gcap gcap-g4"><b>VCP after S2 base</b>Core MM setup - stock in Stage 2 uptrend, has built a base (15%+ pullback) with VCP pattern, and is now breaking out. Four tests.</div>' +
      '</div>' +
      '<div class="table-wrap">' +
        '<table class="data-table" id="st-main-table">' +
          '<colgroup>' + colgroupHtml + '</colgroup>' +
          '<thead>' +
            '<tr class="group-header-row">' + groupHeaderHtml + '</tr>' +
            '<tr class="col-header-row" id="st-col-header-row"></tr>' +
          '</thead>' +
          '<tbody id="st-tbody"></tbody>' +
        '</table>' +
      '</div>';
    host.innerHTML = html;
    var tiles = document.getElementById('st-setup-tiles');
    if (tiles) {
      tiles.addEventListener('click', function(e) {
        var tile = e.target.closest('.rating-tile');
        if (!tile) return;
        var k = tile.getAttribute('data-setup');
        if (k) stToggleSetup(k);
      });
    }
    var hdr = document.getElementById('st-col-header-row');
    if (hdr) {
      hdr.addEventListener('click', function(e) {
        var th = e.target.closest('th');
        if (!th) return;
        var key = th.getAttribute('data-sort-key');
        if (key) stOnSort(key);
      });
    }
    return true;
  }

  function renderSetups() {
    if (!stBuildScaffold()) return;
    stBuildHeaderRow();
    stRenderRows();
  }
  window.renderSetups = renderSetups;

})();

/* MD-V2-SETUPS-MARKER-END */
