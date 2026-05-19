/* MD-V2-SETUPS-MARKER-START */

(function() {
  'use strict';

  // MD-V2-S26-CHIPS-MARKER: st tab module - rating-tier multi-select chip
  // filter + per-pattern rating/score/test columns, structured identically to
  // the proven Pre-test indicators module. Reads md_v2.setups.

  var stState = {
    mode: { inputs: 'pct' },
    scope: 'all',
    tierFilter: {},
    tint: 'none',
    port: 'off',
    sort: { col: 'company', dir: 'asc' }
  };

  var ST_PATTERNS = [
  {
    "key": "probing_bet",
    "label": "Probing bet",
    "shortLabel": "Probing bet",
    "supergroup": null,
    "tierLadder": [
      "Possible",
      "Probable"
    ],
    "total": 2,
    "tooltip": "A stock in a weak or basing stage (or collapsing) that is showing a fresh breakout - worth a small starter position.",
    "caption": "A small initial allocation when a stock has collapsed or is in a struggling stage but shows a fresh breakout. Two tests: a qualifying stage or collapsing indicator AND a breakout.",
    "tests": [
      {
        "key": "t1_stage_qualifying_or_collapsing",
        "label": "Qualifying stage or Collapsing",
        "tooltip": "Stage 1 plausible-or-better, OR Stage 3 invalidating, OR Stage 4 plausible-or-better, OR the Collapsing indicator fires"
      },
      {
        "key": "t2_breakout",
        "label": "Breakout",
        "tooltip": "The Breakout post-test indicator fires"
      }
    ]
  },
  {
    "key": "vcp_after_s1_plateau",
    "label": "VCP after Stage 1-to-2 plateau",
    "shortLabel": "VCP after S1-2",
    "supergroup": null,
    "tierLadder": [
      "Possible",
      "Plausible",
      "Probable"
    ],
    "total": 4,
    "tooltip": "A stock transitioning from Stage 1 to Stage 2 showing a genuine volatility-contraction pattern.",
    "caption": "A core position setup - a stock coming out of a base into a new uptrend with a genuine volatility-contraction pattern. Four VCP tests, all must pass; qualification also needs the Stage 1-to-2 transition (shown as an info column).",
    "tests": [
      {
        "key": "t1_narrowing_contractions",
        "label": "Narrowing contractions",
        "tooltip": "Each price contraction is strictly shallower than the one before it"
      },
      {
        "key": "t2_sufficient_count",
        "label": "2-4 contractions",
        "tooltip": "Between two and four contractions in the base"
      },
      {
        "key": "t3_volume_declining",
        "label": "Volume declining",
        "tooltip": "Average volume falls across successive contractions"
      },
      {
        "key": "t4_higher_lows",
        "label": "Higher lows",
        "tooltip": "Each contraction low sits above the previous contraction low"
      }
    ]
  },
  {
    "key": "healthy_retest",
    "label": "Healthy retest within MT/LT uptrend",
    "shortLabel": "Healthy retest",
    "supergroup": null,
    "tierLadder": [
      "Possible",
      "Plausible",
      "Probable"
    ],
    "total": 6,
    "tooltip": "A stock in a real uptrend whose pullback toward a moving average is orderly and healthy.",
    "caption": "A core position setup - a stock in a genuine uptrend whose pullback toward a moving average is orderly: contracting volume, contracting volatility, few distribution days, buying through the last ten days. Six tests, all must pass.",
    "tests": [
      {
        "key": "t1_volume_contracting",
        "label": "Volume contracting",
        "tooltip": "10-day average volume is below the 50-day average volume"
      },
      {
        "key": "t2_updown_vol_ge105",
        "label": "Up-volume 5%+ above down",
        "tooltip": "Up-day volume is at least 5% above down-day volume"
      },
      {
        "key": "t3_few_distribution_days",
        "label": "Few distribution days",
        "tooltip": "Three or fewer distribution days in the last 25 sessions"
      },
      {
        "key": "t4_volatility_contracting",
        "label": "Volatility contracting",
        "tooltip": "Short-term volatility range is narrower than the medium-term range"
      },
      {
        "key": "t5_testing_meaningful_ma",
        "label": "Testing a meaningful MA",
        "tooltip": "Price has come down to within range of a 50/100/150/200-day moving average"
      },
      {
        "key": "t6_buying_through_l10d",
        "label": "Buying through last 10 days",
        "tooltip": "At least half of the last 10 days closed in the upper 40% of their daily range"
      }
    ]
  },
  {
    "key": "vcp_after_s2_base",
    "label": "VCP after Stage 2 base",
    "shortLabel": "VCP after S2",
    "supergroup": null,
    "tierLadder": [
      "Possible",
      "Plausible",
      "Probable"
    ],
    "total": 4,
    "tooltip": "A stock already in an uptrend that has built a fresh base with a genuine volatility-contraction pattern.",
    "caption": "A core position setup - a stock already in a Stage 2 uptrend that has built a fresh base with a genuine volatility-contraction pattern. Four VCP tests, all must pass; qualification also needs the Stage 2 base (shown as an info column).",
    "tests": [
      {
        "key": "t1_narrowing_contractions",
        "label": "Narrowing contractions",
        "tooltip": "Each price contraction is strictly shallower than the one before it"
      },
      {
        "key": "t2_sufficient_count",
        "label": "2-4 contractions",
        "tooltip": "Between two and four contractions in the base"
      },
      {
        "key": "t3_volume_declining",
        "label": "Volume declining",
        "tooltip": "Average volume falls across successive contractions"
      },
      {
        "key": "t4_higher_lows",
        "label": "Higher lows",
        "tooltip": "Each contraction low sits above the previous contraction low"
      }
    ]
  }
];
  var ST_SUPERGROUPS = [];
  var ST_TONE = {"probing_bet": "pi-tile-pullback", "vcp_after_s1_plateau": "pi-tile-basing", "healthy_retest": "pi-tile-collapsing", "vcp_after_s2_base": "pi-tile-amber"};
  var ST_STRIP = {"probing_bet": "pi-strip-pullback", "vcp_after_s1_plateau": "pi-strip-basing", "healthy_retest": "pi-strip-collapsing", "vcp_after_s2_base": "pi-strip-amber"};
  var ST_CHIP = {"probing_bet": "pullback", "vcp_after_s1_plateau": "basing", "healthy_retest": "collapsing", "vcp_after_s2_base": "amber"};

  // init tierFilter keyed by pattern
  for (var _ip = 0; _ip < ST_PATTERNS.length; _ip++) {
    stState.tierFilter[ST_PATTERNS[_ip].key] = [];
  }

  var ST_RATING_RANK = { 'Probable':4, 'Plausible':3, 'Possible':2, 'None':1 };
  var ST_RATING_CLS  = { 'Probable':'tint-prob', 'Plausible':'tint-pla', 'Possible':'tint-pos', 'None':'tint-none' };

  function stBuildCols() {
    var cols = [
      { id:'name',     label:'Company - Ticker',       sortKey:'company',         cls:'name-cell', kind:'input' },
      { id:'taxon',    label:'Industry - Sector',      sortKey:'sector',          cls:'taxon',     kind:'input' },
      { id:'price',    label:'Price',                  sortKey:'price',           cls:'num',       kind:'input' },
      { id:'high_52w', label:'52 week high',           sortKey:'high_52w',        cls:'num',       kind:'input' },
      { id:'low_52w',  label:'52 week low',            sortKey:'low_52w',         cls:'num',       kind:'input' },
      { id:'ma_150',   label:'150 day moving average', sortKey:'ma_150',          cls:'num',       kind:'input' },
      { id:'ma_200',   label:'200 day moving average', sortKey:'ma_200',          cls:'num',       kind:'input' },
      { id:'pullback', label:'Recent pullback',        sortKey:'recent_pullback', cls:'num',       kind:'input' }
    ];
    for (var p = 0; p < ST_PATTERNS.length; p++) {
      var pat = ST_PATTERNS[p];
      var gi = p + 1;
      cols.push({ id:'p'+gi+'_rating', label:'Rating', sortKey:pat.key+'__rating', cls:'grp-start-g'+gi+' pi-rating-col', kind:'rating', patternKey:pat.key });
      cols.push({ id:'p'+gi+'_score',  label:'Score',  sortKey:pat.key+'__score',  cls:'pi-score-col',                   kind:'score',  patternKey:pat.key });
      for (var t = 0; t < pat.tests.length; t++) {
        var test = pat.tests[t];
        cols.push({
          id: 'p'+gi+'t'+(t+1), label: test.label, sortKey: pat.key + '__' + test.key,
          cls: '', tooltip: test.tooltip, kind: 'test', patternKey: pat.key, testKey: test.key
        });
      }
    }
    return cols;
  }
  var ST_COLS = stBuildCols();

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

  function stPatternRec(row, patternKey) {
    var dk = row.md_v2 && row.md_v2.setups;
    return (dk && dk[patternKey]) || null;
  }
  function stEvalTest(row, patternKey, testKey) {
    var rec = stPatternRec(row, patternKey);
    if (!rec || !rec.tests) return false;
    return !!rec.tests[testKey];
  }
  function stRowRating(row, patternKey) {
    var rec = stPatternRec(row, patternKey);
    return rec ? (rec.rating || 'None') : 'None';
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
      var mas = p.mas || {};
      rows.push({
        ticker: s.ticker, company: p.company_name || s.ticker,
        sector: p.sector || '', industry: p.industry || '',
        price: p.price, high_52w: p.high_52w, low_52w: p.low_52w,
        recent_pullback: p.recent_pullback_pct,
        ma_150: mas['150D'], ma_200: mas['200D'],
        md_v2: s.md_v2,
        is_live: !!live[s.ticker],
        sector_in_portfolio: !!liveS[p.sector],
        industry_in_portfolio: !!liveI[p.industry]
      });
    }
    return rows;
  }

  function stPatternCounts(rows) {
    var c = {};
    for (var pi = 0; pi < ST_PATTERNS.length; pi++) c[ST_PATTERNS[pi].key] = 0;
    for (var i = 0; i < rows.length; i++) {
      for (var p = 0; p < ST_PATTERNS.length; p++) {
        var rec = stPatternRec(rows[i], ST_PATTERNS[p].key);
        if (rec && rec.qualifies) c[ST_PATTERNS[p].key]++;
      }
    }
    return c;
  }
  function stPassHistogram(rows, patternKey, total) {
    var h = [];
    for (var k = 0; k <= total; k++) h[k] = 0;
    for (var i = 0; i < rows.length; i++) {
      var rec = stPatternRec(rows[i], patternKey);
      var cnt = rec ? (rec.count || 0) : 0;
      if (cnt >= 0 && cnt <= total) h[cnt]++;
    }
    return h;
  }
  function stTierCounts(rows, patternKey) {
    var c = { 'Possible':0, 'Plausible':0, 'Probable':0, 'None':0 };
    for (var i = 0; i < rows.length; i++) {
      var r = stRowRating(rows[i], patternKey);
      if (c[r] != null) c[r]++;
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
    if (key === 'recent_pullback') {
      if (v == null || isNaN(v)) return '<td class="num ' + extraCls + '">-</td>';
      var pctVal = v * 100;
      var pi_intensity = Math.max(-1, Math.min(1, (pctVal - 5) / 20));
      var col = stColourForIntensity(-pi_intensity);
      return '<td class="num ' + extraCls + '" style="color:' + col + '">' + Math.round(pctVal) + '%</td>';
    }
    if (v == null || row.price == null) return '<td class="num ' + extraCls + '">-</td>';
    var pct = (row.price - v) / v * 100;
    var intensity = 0;
    if (key === 'high_52w') intensity = Math.max(-1, Math.min(1, (-pct - 5) / 20));
    else if (key === 'low_52w') intensity = Math.max(-1, Math.min(1, (pct - 20) / 30));
    else if (key === 'ma_150' || key === 'ma_200') intensity = Math.max(-1, Math.min(1, pct / 10));
    var colour = stColourForIntensity(intensity);
    var text = (stState.mode.inputs === 'pct') ? stFmtPct(pct) : stFmtNum(v);
    return '<td class="num ' + extraCls + '" style="color:' + colour + '">' + text + '</td>';
  }
  function stTestCell(row, col) {
    var pass = stEvalTest(row, col.patternKey, col.testKey);
    var extra = col.cls || '';
    if (pass) return '<td class="pi-pass ' + extra + '"><span class="tick">' + String.fromCharCode(10003) + '</span></td>';
    return '<td class="pi-fail ' + extra + '">.</td>';
  }
  function stRatingCell(row, col) {
    var rating = stRowRating(row, col.patternKey);
    var rcls = ST_RATING_CLS[rating] || 'tint-none';
    return '<td class="' + (col.cls || '') + ' pi-rating-cell ' + rcls + '"><span class="pi-pill pi-pill-' + rcls + '">' + rating + '</span></td>';
  }
  function stScoreCell(row, col) {
    var rec = stPatternRec(row, col.patternKey);
    var cnt = rec ? (rec.count || 0) : 0;
    var tot = rec ? (rec.total || 0) : 0;
    var s = '';
    for (var i = 0; i < tot; i++) s += '<span class="pip ' + (i < cnt ? 'on' : '') + '"></span>';
    return '<td class="' + (col.cls || '') + ' pi-score-cell"><div class="pi-pip-row">' + s +
           '<span class="pi-score-num">' + cnt + '/' + tot + '</span></div></td>';
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
      var patternKey = parts[0], sub = parts[1];
      var rec = stPatternRec(row, patternKey);
      if (sub === 'rating') return rec ? (ST_RATING_RANK[rec.rating] || 0) : 0;
      if (sub === 'score')  return rec ? (rec.count || 0) : 0;
      return stEvalTest(row, patternKey, sub) ? 1 : 0;
    }
    if (key === 'recent_pullback') return row.recent_pullback == null ? -Infinity : row.recent_pullback;
    var PCT_KEYS = ['high_52w','low_52w','ma_150','ma_200'];
    if (PCT_KEYS.indexOf(key) > -1 && stState.mode.inputs === 'pct') {
      var ref = row[key];
      if (ref == null || row.price == null || ref === 0) return -Infinity;
      return (row.price - ref) / ref * 100;
    }
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
  function stPatternTiles(scopeRows) {
    var tiles = document.getElementById('st-pattern-tiles');
    if (!tiles) return;
    var counts = stPatternCounts(scopeRows);
    var total = scopeRows.length;
    var h = '';
    for (var i = 0; i < ST_PATTERNS.length; i++) {
      var pat = ST_PATTERNS[i];
      var cnt = counts[pat.key] || 0;
      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;
      var sel = stState.tierFilter[pat.key] || [];
      var anySel = sel.length > 0;
      var tierCounts = stTierCounts(scopeRows, pat.key);
      var headline = cnt, headSub = 'of ' + total.toLocaleString('en-GB') + ' &middot; ' + pct + '%';
      if (anySel) {
        var ft = 0;
        for (var z = 0; z < sel.length; z++) ft += (tierCounts[sel[z]] || 0);
        headline = ft;
        headSub = sel.join(' + ') + ' &middot; filtered';
      }
      var hist = stPassHistogram(scopeRows, pat.key, pat.total);
      var breakdown = '';
      for (var k = 1; k <= pat.total; k++) {
        if (k > 1) breakdown += ' &middot; ';
        breakdown += k + ' of ' + pat.total + ': ' + (hist[k] || 0).toLocaleString('en-GB');
      }
      var chips = '';
      for (var c = 0; c < pat.tierLadder.length; c++) {
        var tier = pat.tierLadder[c];
        var on = sel.indexOf(tier) > -1;
        var tc = tierCounts[tier] || 0;
        chips += '<span class="pi-tier-chip pi-chip-' + ST_CHIP[pat.key] +
                 (on ? ' on' : '') + '" data-pattern="' + pat.key + '" data-tier="' + tier + '">' +
                 tier + ' ' + tc.toLocaleString('en-GB') + (on ? ' ' + String.fromCharCode(10003) : '') + '</span>';
      }
      var activeCls = anySel ? ' active' : '';
      h += '<div class="rating-tile ' + ST_TONE[pat.key] + activeCls + '" data-pattern="' + pat.key + '" title="' + pat.tooltip + '">' +
           '<div class="rt-label">' + pat.shortLabel + '</div>' +
           '<div class="rt-count">' + headline.toLocaleString('en-GB') + '</div>' +
           '<div class="rt-sub">' + headSub + '</div>' +
           '<div class="rt-breakdown">' + breakdown + '</div>' +
           '<div class="pi-tier-chips" data-pattern="' + pat.key + '">' + chips + '</div>' +
           '<div class="rt-strip ' + ST_STRIP[pat.key] + '"></div>' +
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
  function stApplyScope(all) {
    var rows = all.slice();
    if (stState.scope === 'live') rows = rows.filter(function(r){ return r.is_live; });
    else if (stState.scope === 'sector') rows = rows.filter(function(r){ return r.sector_in_portfolio; });
    else if (stState.scope === 'industry') rows = rows.filter(function(r){ return r.industry_in_portfolio; });
    return rows;
  }
  function stApplyTierFilter(rows) {
    var active = [];
    for (var p = 0; p < ST_PATTERNS.length; p++) {
      var k = ST_PATTERNS[p].key;
      var sel = stState.tierFilter[k] || [];
      if (sel.length > 0) active.push({ key: k, tiers: sel });
    }
    if (active.length === 0) return rows;
    return rows.filter(function(r) {
      for (var a = 0; a < active.length; a++) {
        var rating = stRowRating(r, active[a].key);
        if (active[a].tiers.indexOf(rating) === -1) return false;
      }
      return true;
    });
  }
  function stRenderRows() {
    var tbody = document.getElementById('st-tbody');
    if (!tbody) return;
    var all = stGetRows();
    var scopeRows = stApplyScope(all);
    stUpdateScopeCounts(all);
    stPatternTiles(scopeRows);
    var rows = stApplyTierFilter(scopeRows);
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
        var pinf = stPortfolioInfo(s);
        if (pinf) {
          styles.push('--portfolio-color: ' + pinf.color);
          styles.push('--portfolio-bg: ' + pinf.bg);
          styles.push('--portfolio-bg-hover: ' + pinf.bgHover);
          cls.push('portfolio-band'); cls.push('portfolio-tint');
        }
      }
      var styleAttr = styles.length ? ' style="' + styles.join(';') + '"' : '';
      var clsAttr = cls.length ? ' class="' + cls.join(' ') + '"' : '';
      var liveDot = s.is_live ? '<span class="live-dot">' + String.fromCharCode(9679) + '</span>' : '';
      html += '<tr' + clsAttr + styleAttr + '>' +
        '<td class="name-cell"><div class="co">' + liveDot + (s.company || s.ticker) + '</div><div class="tk">' + s.ticker + '</div></td>' +
        '<td class="taxon"><div class="ind">' + (s.industry || '') + '</div><div class="sec">' + (s.sector || '') + '</div></td>' +
        stInputCell(s, 'price') + stInputCell(s, 'high_52w') + stInputCell(s, 'low_52w') +
        stInputCell(s, 'ma_150') + stInputCell(s, 'ma_200') + stInputCell(s, 'recent_pullback');
      for (var j = 8; j < ST_COLS.length; j++) {
        var col = ST_COLS[j];
        if (col.kind === 'rating') html += stRatingCell(s, col);
        else if (col.kind === 'score') html += stScoreCell(s, col);
        else html += stTestCell(s, col);
      }
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
  function stToggleTier(patternKey, tier) {
    var sel = stState.tierFilter[patternKey] || [];
    var idx = sel.indexOf(tier);
    if (idx > -1) sel.splice(idx, 1);
    else sel.push(tier);
    stState.tierFilter[patternKey] = sel;
    stRenderRows();
  }
  function stSelectAllTiers(patternKey) {
    var pat = null;
    for (var p = 0; p < ST_PATTERNS.length; p++) if (ST_PATTERNS[p].key === patternKey) pat = ST_PATTERNS[p];
    if (!pat) return;
    var sel = stState.tierFilter[patternKey] || [];
    var allOn = sel.length === pat.tierLadder.length;
    stState.tierFilter[patternKey] = allOn ? [] : pat.tierLadder.slice();
    stRenderRows();
  }
  window.stSetMode = stSetMode;
  window.stSetScope = stSetScope;
  window.stSetTint = stSetTint;
  window.stSetPort = stSetPort;
  window.stToggleTier = stToggleTier;
  window.stSelectAllTiers = stSelectAllTiers;
  window.stOnSort = stOnSort;

  function stBuildScaffold() {
    var host = document.getElementById('tab-setups');
    if (!host) return false;
    if (host.querySelector('#st-main-table')) return true;

    var colgroupHtml = '<col class="c-name"><col class="c-taxon">' +
                       '<col class="c-price"><col class="c-52wh"><col class="c-52wl">' +
                       '<col class="c-ma150"><col class="c-ma200"><col class="c-pullback">';
    var inputsColspan = 8;
    var hasSuper = ST_SUPERGROUPS.length > 0;
    var superHtml = '<th class="gh-inputs sg-spacer" colspan="' + inputsColspan + '"></th>';
    var groupHtml = '<th class="gh-inputs" colspan="' + inputsColspan + '">Inputs</th>';

    if (hasSuper) {
      var sgCols = {};
      for (var sgi = 0; sgi < ST_SUPERGROUPS.length; sgi++) sgCols[ST_SUPERGROUPS[sgi].key] = 0;
      for (var sp = 0; sp < ST_PATTERNS.length; sp++) {
        var cspan = 2 + ST_PATTERNS[sp].tests.length;
        sgCols[ST_PATTERNS[sp].supergroup] += cspan;
      }
      for (var sgj = 0; sgj < ST_SUPERGROUPS.length; sgj++) {
        var sg = ST_SUPERGROUPS[sgj];
        superHtml += '<th class="' + sg.cls + '" colspan="' + sgCols[sg.key] + '">' + sg.label + '</th>';
      }
    }

    for (var p = 0; p < ST_PATTERNS.length; p++) {
      var pat = ST_PATTERNS[p];
      var gi = p + 1;
      var n = pat.tests.length;
      colgroupHtml += '<col class="c-rating"><col class="c-score">';
      for (var t = 0; t < n; t++) colgroupHtml += '<col class="c-test">';
      groupHtml += '<th class="gh-g' + gi + ' grp-start-g' + gi + '" colspan="' + (n + 2) + '">' + pat.label + '</th>';
    }

    var captionsHtml = '';
    for (var cp = 0; cp < ST_PATTERNS.length; cp++) {
      var cpat = ST_PATTERNS[cp];
      captionsHtml += '<div class="gcap gcap-g' + (cp+1) + '"><b>' + cpat.label + '</b>' + cpat.caption + '</div>';
    }

    var theadRows = '';
    if (hasSuper) theadRows += '<tr class="super-group-row">' + superHtml + '</tr>';
    theadRows += '<tr class="group-header-row">' + groupHtml + '</tr>';
    theadRows += '<tr class="col-header-row" id="st-col-header-row"></tr>';

    var html = '' +
      '<div class="s1-intro">Capital qualification setups sit on top of the indicators - each one says a stock looks ready for you to consider deploying capital. Each setup is the AND of its named constituent tests, shown as individual tick columns alongside a per-pattern rating and score. Each tile has a rating-tier filter row: click a tier chip to show only stocks at that tier, or click the tile body to select all tiers. Tier selections within a setup combine as OR; selections across setups combine as AND.</div>' +
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
      '<div class="rating-tiles s1-rating-tiles" id="st-pattern-tiles"></div>' +
      '<div class="group-captions">' + captionsHtml + '</div>' +
      '<div class="table-wrap">' +
        '<table class="data-table" id="st-main-table">' +
          '<colgroup>' + colgroupHtml + '</colgroup>' +
          '<thead>' + theadRows + '</thead>' +
          '<tbody id="st-tbody"></tbody>' +
        '</table>' +
      '</div>';
    host.innerHTML = html;
    var tiles = document.getElementById('st-pattern-tiles');
    if (tiles) {
      tiles.addEventListener('click', function(e) {
        var chip = e.target.closest('.pi-tier-chip');
        if (chip) {
          var cp = chip.getAttribute('data-pattern');
          var ct = chip.getAttribute('data-tier');
          if (cp && ct) stToggleTier(cp, ct);
          return;
        }
        var tile = e.target.closest('.rating-tile');
        if (!tile) return;
        var k = tile.getAttribute('data-pattern');
        if (k) stSelectAllTiers(k);
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
