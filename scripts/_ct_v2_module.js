/* MD-V2-TESTS-MARKER-START */

(function() {
  'use strict';

  // MD-V2-S26-CHIPS-MARKER: ct tab module - rating-tier multi-select chip
  // filter + per-pattern rating/score/test columns, structured identically to
  // the proven Pre-test indicators module. Reads md_v2.tests.

  var ctState = {
    mode: { inputs: 'pct' },
    scope: 'all',
    tierFilter: {},
    tint: 'none',
    port: 'off',
    sort: { col: 'company', dir: 'asc' }
  };

  var CT_PATTERNS = [
  {
    "key": "probing_bet",
    "label": "Probing bet deployment",
    "shortLabel": "Probing bet",
    "supergroup": null,
    "tierLadder": [
      "Possible",
      "Plausible",
      "Probable"
    ],
    "total": 3,
    "tooltip": "The probing-bet trigger - a qualifying probing-bet stage, a breakout, and a confirming up-day.",
    "caption": "The probing-bet go / no-go trigger. Three tests, all must pass: the probing-bet stage is late or capital, a breakout fires, and today's close confirms with a 2%+ gain over yesterday.",
    "tests": [
      {
        "key": "t1_pb_stage_late_or_capital",
        "label": "Probing-bet stage late/capital",
        "tooltip": "The existing probing-bet filter rates this stock Late or Capital"
      },
      {
        "key": "t2_breakout",
        "label": "Breakout",
        "tooltip": "The Breakout post-test indicator fires"
      },
      {
        "key": "t3_confirmation_close_ge2pct",
        "label": "Confirmation: close 2%+ up",
        "tooltip": "Today's close is at least 2% above yesterday's close - the confirmation test that avoids false starts"
      }
    ]
  },
  {
    "key": "vcp",
    "label": "VCP deployment",
    "shortLabel": "VCP",
    "supergroup": null,
    "tierLadder": [
      "Possible",
      "Plausible",
      "Probable"
    ],
    "total": 5,
    "tooltip": "The VCP trigger - a genuine volatility-contraction pattern plus a confirming up-day.",
    "caption": "The VCP go / no-go trigger. Five tests, all must pass: the four volatility-contraction tests plus today's close confirming with a 2%+ gain over yesterday.",
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
      },
      {
        "key": "t5_confirmation_close_ge2pct",
        "label": "Confirmation: close 2%+ up",
        "tooltip": "Today's close is at least 2% above yesterday's close - the confirmation test that avoids false starts"
      }
    ]
  },
  {
    "key": "ma_retest_upwards",
    "label": "Upwards moving average retest",
    "shortLabel": "MA retest",
    "supergroup": null,
    "tierLadder": [
      "Possible",
      "Plausible",
      "Probable"
    ],
    "total": 5,
    "tooltip": "The moving-average retest trigger - price reclaims a test MA on healthy volume with a confirming up-day.",
    "caption": "The moving-average retest go / no-go trigger. Pass logic: near a test MA AND closed back above it AND (closes near highs over 3 days OR strong 5-day up-volume) AND today's close confirms with a 2%+ gain. Five tests.",
    "tests": [
      {
        "key": "t1_near_test_ma",
        "label": "Near a test MA",
        "tooltip": "Price has come down to within range of a 50/100/150/200-day moving average"
      },
      {
        "key": "t2_close_above_test_ma",
        "label": "Closed above the test MA",
        "tooltip": "Current price is back above the moving average being tested"
      },
      {
        "key": "t3_closes_near_highs_l3d",
        "label": "Closes near highs (3 days)",
        "tooltip": "At least half of the last 3 days closed in the upper 40% of their daily range"
      },
      {
        "key": "t4_updown_vol_l5d",
        "label": "Strong 5-day up-volume",
        "tooltip": "Over the last 5 days, up-day volume is at least 10% above down-day volume"
      },
      {
        "key": "t5_confirmation_close_ge2pct",
        "label": "Confirmation: close 2%+ up",
        "tooltip": "Today's close is at least 2% above yesterday's close - the confirmation test that avoids false starts"
      }
    ]
  }
];
  var CT_SUPERGROUPS = [];
  var CT_TONE = {"probing_bet": "pi-tile-pullback", "vcp": "pi-tile-basing", "ma_retest_upwards": "pi-tile-collapsing"};
  var CT_STRIP = {"probing_bet": "pi-strip-pullback", "vcp": "pi-strip-basing", "ma_retest_upwards": "pi-strip-collapsing"};
  var CT_CHIP = {"probing_bet": "pullback", "vcp": "basing", "ma_retest_upwards": "collapsing"};

  // init tierFilter keyed by pattern
  for (var _ip = 0; _ip < CT_PATTERNS.length; _ip++) {
    ctState.tierFilter[CT_PATTERNS[_ip].key] = [];
  }

  var CT_RATING_RANK = { 'Probable':4, 'Plausible':3, 'Possible':2, 'None':1 };
  var CT_RATING_CLS  = { 'Probable':'tint-prob', 'Plausible':'tint-pla', 'Possible':'tint-pos', 'None':'tint-none' };

  function ctBuildCols() {
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
    for (var p = 0; p < CT_PATTERNS.length; p++) {
      var pat = CT_PATTERNS[p];
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
  var CT_COLS = ctBuildCols();

  function ctPricesLookup() {
    if (window._ctPricesByTicker) return window._ctPricesByTicker;
    var out = {};
    var arr = (window.MASTER_DATA && MASTER_DATA.prices) || [];
    for (var i = 0; i < arr.length; i++) if (arr[i] && arr[i].ticker) out[arr[i].ticker] = arr[i];
    window._ctPricesByTicker = out;
    return out;
  }
  function ctLiveTickers() {
    var out = {};
    var inv = (window.MASTER_DATA && MASTER_DATA.positions && MASTER_DATA.positions.investments) || [];
    for (var i = 0; i < inv.length; i++) if (inv[i].ticker) out[inv[i].ticker] = true;
    return out;
  }
  function ctLiveSectors() {
    var out = {}, t, prices = ctPricesLookup(), tickers = ctLiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.sector) out[p.sector] = true; }
    return out;
  }
  function ctLiveIndustries() {
    var out = {}, t, prices = ctPricesLookup(), tickers = ctLiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.industry) out[p.industry] = true; }
    return out;
  }

  function ctPatternRec(row, patternKey) {
    var dk = row.md_v2 && row.md_v2.tests;
    return (dk && dk[patternKey]) || null;
  }
  function ctEvalTest(row, patternKey, testKey) {
    var rec = ctPatternRec(row, patternKey);
    if (!rec || !rec.tests) return false;
    return !!rec.tests[testKey];
  }
  function ctRowRating(row, patternKey) {
    var rec = ctPatternRec(row, patternKey);
    return rec ? (rec.rating || 'None') : 'None';
  }

  function ctGetRows() {
    var raw = (window.MASTER_DATA && MASTER_DATA.filters) || [];
    var prices = ctPricesLookup();
    var live = ctLiveTickers(), liveS = ctLiveSectors(), liveI = ctLiveIndustries();
    var rows = [];
    for (var i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || !s.md_v2 || !s.md_v2.tests) continue;
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

  function ctPatternCounts(rows) {
    var c = {};
    for (var pi = 0; pi < CT_PATTERNS.length; pi++) c[CT_PATTERNS[pi].key] = 0;
    for (var i = 0; i < rows.length; i++) {
      for (var p = 0; p < CT_PATTERNS.length; p++) {
        var rec = ctPatternRec(rows[i], CT_PATTERNS[p].key);
        if (rec && rec.qualifies) c[CT_PATTERNS[p].key]++;
      }
    }
    return c;
  }
  function ctPassHistogram(rows, patternKey, total) {
    var h = [];
    for (var k = 0; k <= total; k++) h[k] = 0;
    for (var i = 0; i < rows.length; i++) {
      var rec = ctPatternRec(rows[i], patternKey);
      var cnt = rec ? (rec.count || 0) : 0;
      if (cnt >= 0 && cnt <= total) h[cnt]++;
    }
    return h;
  }
  function ctTierCounts(rows, patternKey) {
    var c = { 'Possible':0, 'Plausible':0, 'Probable':0, 'None':0 };
    for (var i = 0; i < rows.length; i++) {
      var r = ctRowRating(rows[i], patternKey);
      if (c[r] != null) c[r]++;
    }
    return c;
  }

  function ctFmtNum(n) {
    if (n == null || isNaN(n)) return '-';
    var abs = Math.abs(n);
    var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);
    var f = abs.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });
    return n < 0 ? '(' + f + ')' : f;
  }
  function ctFmtPct(p) {
    if (p == null || isNaN(p)) return '-';
    var r = Math.round(p), abs = Math.abs(r);
    return r < 0 ? '(' + abs + ')%' : r + '%';
  }
  function ctColourForIntensity(i) {
    if (i >= 0.6) return '#0F6E56';
    if (i >= 0.25) return '#1D9E75';
    if (i >= 0.05) return '#5DCAA5';
    if (i <= -0.6) return '#A32D2D';
    if (i <= -0.25) return '#E24B4A';
    if (i <= -0.05) return '#F09595';
    return '#888';
  }
  function ctInputCell(row, key, extraCls) {
    extraCls = extraCls || '';
    var v = row[key];
    if (key === 'price') return '<td class="num ' + extraCls + '">' + ctFmtNum(v) + '</td>';
    if (key === 'recent_pullback') {
      if (v == null || isNaN(v)) return '<td class="num ' + extraCls + '">-</td>';
      var pctVal = v * 100;
      var pi_intensity = Math.max(-1, Math.min(1, (pctVal - 5) / 20));
      var col = ctColourForIntensity(-pi_intensity);
      return '<td class="num ' + extraCls + '" style="color:' + col + '">' + Math.round(pctVal) + '%</td>';
    }
    if (v == null || row.price == null) return '<td class="num ' + extraCls + '">-</td>';
    var pct = (row.price - v) / v * 100;
    var intensity = 0;
    if (key === 'high_52w') intensity = Math.max(-1, Math.min(1, (-pct - 5) / 20));
    else if (key === 'low_52w') intensity = Math.max(-1, Math.min(1, (pct - 20) / 30));
    else if (key === 'ma_150' || key === 'ma_200') intensity = Math.max(-1, Math.min(1, pct / 10));
    var colour = ctColourForIntensity(intensity);
    var text = (ctState.mode.inputs === 'pct') ? ctFmtPct(pct) : ctFmtNum(v);
    return '<td class="num ' + extraCls + '" style="color:' + colour + '">' + text + '</td>';
  }
  function ctTestCell(row, col) {
    var pass = ctEvalTest(row, col.patternKey, col.testKey);
    var extra = col.cls || '';
    if (pass) return '<td class="pi-pass ' + extra + '"><span class="tick">' + String.fromCharCode(10003) + '</span></td>';
    return '<td class="pi-fail ' + extra + '">.</td>';
  }
  function ctRatingCell(row, col) {
    var rating = ctRowRating(row, col.patternKey);
    var rcls = CT_RATING_CLS[rating] || 'tint-none';
    return '<td class="' + (col.cls || '') + ' pi-rating-cell ' + rcls + '"><span class="pi-pill pi-pill-' + rcls + '">' + rating + '</span></td>';
  }
  function ctScoreCell(row, col) {
    var rec = ctPatternRec(row, col.patternKey);
    var cnt = rec ? (rec.count || 0) : 0;
    var tot = rec ? (rec.total || 0) : 0;
    var s = '';
    for (var i = 0; i < tot; i++) s += '<span class="pip ' + (i < cnt ? 'on' : '') + '"></span>';
    return '<td class="' + (col.cls || '') + ' pi-score-cell"><div class="pi-pip-row">' + s +
           '<span class="pi-score-num">' + cnt + '/' + tot + '</span></div></td>';
  }
  function ctHashColor(label, alpha) {
    if (!label) return null;
    var h = 0;
    for (var i = 0; i < label.length; i++) h = (h * 31 + label.charCodeAt(i)) & 0xffff;
    return 'hsla(' + (h % 360) + ', 35%, 55%, ' + alpha + ')';
  }
  function ctPortfolioInfo(row) {
    if (row.is_live) return { color:'#1b5e20', bg:'rgba(27,94,32,0.10)', bgHover:'rgba(27,94,32,0.14)' };
    if (row.sector_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.05)', bgHover:'rgba(27,94,32,0.08)' };
    if (row.industry_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.025)', bgHover:'rgba(27,94,32,0.05)' };
    return null;
  }
  function ctGetSortVal(row, key) {
    if (key.indexOf('__') > 0) {
      var parts = key.split('__');
      var patternKey = parts[0], sub = parts[1];
      var rec = ctPatternRec(row, patternKey);
      if (sub === 'rating') return rec ? (CT_RATING_RANK[rec.rating] || 0) : 0;
      if (sub === 'score')  return rec ? (rec.count || 0) : 0;
      return ctEvalTest(row, patternKey, sub) ? 1 : 0;
    }
    if (key === 'recent_pullback') return row.recent_pullback == null ? -Infinity : row.recent_pullback;
    var PCT_KEYS = ['high_52w','low_52w','ma_150','ma_200'];
    if (PCT_KEYS.indexOf(key) > -1 && ctState.mode.inputs === 'pct') {
      var ref = row[key];
      if (ref == null || row.price == null || ref === 0) return -Infinity;
      return (row.price - ref) / ref * 100;
    }
    if (key in row) return row[key];
    return 0;
  }
  function ctOnSort(key) {
    if (ctState.sort.col === key) ctState.sort.dir = ctState.sort.dir === 'desc' ? 'asc' : 'desc';
    else ctState.sort = { col: key, dir: key === 'company' ? 'asc' : 'desc' };
    ctBuildHeaderRow();
    ctRenderRows();
  }
  function ctBuildHeaderRow() {
    var tr = document.getElementById('ct-col-header-row');
    if (!tr) return;
    var h = '';
    for (var i = 0; i < CT_COLS.length; i++) {
      var c = CT_COLS[i];
      var isSort = ctState.sort.col === c.sortKey;
      var arrow = isSort
        ? '<span class="sort-arrow">' + (ctState.sort.dir === 'desc' ? String.fromCharCode(9660) : String.fromCharCode(9650)) + '</span>'
        : '<span class="sort-placeholder"></span>';
      var title = c.tooltip || c.label;
      h += '<th class="' + (c.cls || '') + '" data-sort-key="' + c.sortKey + '" title="' + title + '">' +
           '<span class="hd"><span class="lbl">' + c.label + '</span>' + arrow + '</span></th>';
    }
    tr.innerHTML = h;
  }
  function ctPatternTiles(scopeRows) {
    var tiles = document.getElementById('ct-pattern-tiles');
    if (!tiles) return;
    var counts = ctPatternCounts(scopeRows);
    var total = scopeRows.length;
    var h = '';
    for (var i = 0; i < CT_PATTERNS.length; i++) {
      var pat = CT_PATTERNS[i];
      var cnt = counts[pat.key] || 0;
      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;
      var sel = ctState.tierFilter[pat.key] || [];
      var anySel = sel.length > 0;
      var tierCounts = ctTierCounts(scopeRows, pat.key);
      var headline = cnt, headSub = 'of ' + total.toLocaleString('en-GB') + ' &middot; ' + pct + '%';
      if (anySel) {
        var ft = 0;
        for (var z = 0; z < sel.length; z++) ft += (tierCounts[sel[z]] || 0);
        headline = ft;
        headSub = sel.join(' + ') + ' &middot; filtered';
      }
      var hist = ctPassHistogram(scopeRows, pat.key, pat.total);
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
        chips += '<span class="pi-tier-chip pi-chip-' + CT_CHIP[pat.key] +
                 (on ? ' on' : '') + '" data-pattern="' + pat.key + '" data-tier="' + tier + '">' +
                 tier + ' ' + tc.toLocaleString('en-GB') + (on ? ' ' + String.fromCharCode(10003) : '') + '</span>';
      }
      var activeCls = anySel ? ' active' : '';
      h += '<div class="rating-tile ' + CT_TONE[pat.key] + activeCls + '" data-pattern="' + pat.key + '" title="' + pat.tooltip + '">' +
           '<div class="rt-label">' + pat.shortLabel + '</div>' +
           '<div class="rt-count">' + headline.toLocaleString('en-GB') + '</div>' +
           '<div class="rt-sub">' + headSub + '</div>' +
           '<div class="rt-breakdown">' + breakdown + '</div>' +
           '<div class="pi-tier-chips" data-pattern="' + pat.key + '">' + chips + '</div>' +
           '<div class="rt-strip ' + CT_STRIP[pat.key] + '"></div>' +
           '</div>';
    }
    tiles.innerHTML = h;
  }
  function ctUpdateScopeCounts(rows) {
    function set(id, n) { var el = document.getElementById(id); if (el) el.textContent = '(' + n + ')'; }
    set('ct-cnt-all',      rows.length);
    set('ct-cnt-live',     rows.filter(function(r){ return r.is_live; }).length);
    set('ct-cnt-sector',   rows.filter(function(r){ return r.sector_in_portfolio; }).length);
    set('ct-cnt-industry', rows.filter(function(r){ return r.industry_in_portfolio; }).length);
  }
  function ctApplyScope(all) {
    var rows = all.slice();
    if (ctState.scope === 'live') rows = rows.filter(function(r){ return r.is_live; });
    else if (ctState.scope === 'sector') rows = rows.filter(function(r){ return r.sector_in_portfolio; });
    else if (ctState.scope === 'industry') rows = rows.filter(function(r){ return r.industry_in_portfolio; });
    return rows;
  }
  function ctApplyTierFilter(rows) {
    var active = [];
    for (var p = 0; p < CT_PATTERNS.length; p++) {
      var k = CT_PATTERNS[p].key;
      var sel = ctState.tierFilter[k] || [];
      if (sel.length > 0) active.push({ key: k, tiers: sel });
    }
    if (active.length === 0) return rows;
    return rows.filter(function(r) {
      for (var a = 0; a < active.length; a++) {
        var rating = ctRowRating(r, active[a].key);
        if (active[a].tiers.indexOf(rating) === -1) return false;
      }
      return true;
    });
  }
  function ctRenderRows() {
    var tbody = document.getElementById('ct-tbody');
    if (!tbody) return;
    var all = ctGetRows();
    var scopeRows = ctApplyScope(all);
    ctUpdateScopeCounts(all);
    ctPatternTiles(scopeRows);
    var rows = ctApplyTierFilter(scopeRows);
    rows.sort(function(a,b) {
      var va = ctGetSortVal(a, ctState.sort.col), vb = ctGetSortVal(b, ctState.sort.col);
      var cmp = (typeof va === 'string') ? va.localeCompare(vb) : (va || 0) - (vb || 0);
      if (cmp === 0) cmp = a.ticker.localeCompare(b.ticker);
      return ctState.sort.dir === 'desc' ? -cmp : cmp;
    });
    var html = '';
    for (var i = 0; i < rows.length; i++) {
      var s = rows[i];
      var styles = [], cls = [];
      if (ctState.tint === 'industry') { styles.push('--tint-bg: ' + ctHashColor(s.industry, 0.16)); cls.push('tint-row'); }
      else if (ctState.tint === 'sector') { styles.push('--tint-bg: ' + ctHashColor(s.sector, 0.16)); cls.push('tint-row'); }
      if (ctState.port === 'on') {
        var pinf = ctPortfolioInfo(s);
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
        ctInputCell(s, 'price') + ctInputCell(s, 'high_52w') + ctInputCell(s, 'low_52w') +
        ctInputCell(s, 'ma_150') + ctInputCell(s, 'ma_200') + ctInputCell(s, 'recent_pullback');
      for (var j = 8; j < CT_COLS.length; j++) {
        var col = CT_COLS[j];
        if (col.kind === 'rating') html += ctRatingCell(s, col);
        else if (col.kind === 'score') html += ctScoreCell(s, col);
        else html += ctTestCell(s, col);
      }
      html += '</tr>';
    }
    tbody.innerHTML = html;
  }
  function ctSetMode(kind, val) {
    ctState.mode[kind] = val;
    var btns = document.querySelectorAll('button[data-ct-grp="' + kind + '"]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-ct-val') === val);
    ctRenderRows();
  }
  function ctSetScope(s) {
    ctState.scope = s;
    var btns = document.querySelectorAll('button[data-ct-scope]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-ct-scope') === s);
    ctRenderRows();
  }
  function ctSetTint(t) {
    ctState.tint = t;
    var btns = document.querySelectorAll('button[data-ct-tint]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-ct-tint') === t);
    ctRenderRows();
  }
  function ctSetPort(p) {
    ctState.port = p;
    var btns = document.querySelectorAll('button[data-ct-port]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-ct-port') === p);
    ctRenderRows();
  }
  function ctToggleTier(patternKey, tier) {
    var sel = ctState.tierFilter[patternKey] || [];
    var idx = sel.indexOf(tier);
    if (idx > -1) sel.splice(idx, 1);
    else sel.push(tier);
    ctState.tierFilter[patternKey] = sel;
    ctRenderRows();
  }
  function ctSelectAllTiers(patternKey) {
    var pat = null;
    for (var p = 0; p < CT_PATTERNS.length; p++) if (CT_PATTERNS[p].key === patternKey) pat = CT_PATTERNS[p];
    if (!pat) return;
    var sel = ctState.tierFilter[patternKey] || [];
    var allOn = sel.length === pat.tierLadder.length;
    ctState.tierFilter[patternKey] = allOn ? [] : pat.tierLadder.slice();
    ctRenderRows();
  }
  window.ctSetMode = ctSetMode;
  window.ctSetScope = ctSetScope;
  window.ctSetTint = ctSetTint;
  window.ctSetPort = ctSetPort;
  window.ctToggleTier = ctToggleTier;
  window.ctSelectAllTiers = ctSelectAllTiers;
  window.ctOnSort = ctOnSort;

  function ctBuildScaffold() {
    var host = document.getElementById('tab-tests');
    if (!host) return false;
    if (host.querySelector('#ct-main-table')) return true;

    var colgroupHtml = '<col class="c-name"><col class="c-taxon">' +
                       '<col class="c-price"><col class="c-52wh"><col class="c-52wl">' +
                       '<col class="c-ma150"><col class="c-ma200"><col class="c-pullback">';
    var inputsColspan = 8;
    var hasSuper = CT_SUPERGROUPS.length > 0;
    var superHtml = '<th class="gh-inputs sg-spacer" colspan="' + inputsColspan + '"></th>';
    var groupHtml = '<th class="gh-inputs" colspan="' + inputsColspan + '">Inputs</th>';

    if (hasSuper) {
      var sgCols = {};
      for (var sgi = 0; sgi < CT_SUPERGROUPS.length; sgi++) sgCols[CT_SUPERGROUPS[sgi].key] = 0;
      for (var sp = 0; sp < CT_PATTERNS.length; sp++) {
        var cspan = 2 + CT_PATTERNS[sp].tests.length;
        sgCols[CT_PATTERNS[sp].supergroup] += cspan;
      }
      for (var sgj = 0; sgj < CT_SUPERGROUPS.length; sgj++) {
        var sg = CT_SUPERGROUPS[sgj];
        superHtml += '<th class="' + sg.cls + '" colspan="' + sgCols[sg.key] + '">' + sg.label + '</th>';
      }
    }

    for (var p = 0; p < CT_PATTERNS.length; p++) {
      var pat = CT_PATTERNS[p];
      var gi = p + 1;
      var n = pat.tests.length;
      colgroupHtml += '<col class="c-rating"><col class="c-score">';
      for (var t = 0; t < n; t++) colgroupHtml += '<col class="c-test">';
      groupHtml += '<th class="gh-g' + gi + ' grp-start-g' + gi + '" colspan="' + (n + 2) + '">' + pat.label + '</th>';
    }

    var captionsHtml = '';
    for (var cp = 0; cp < CT_PATTERNS.length; cp++) {
      var cpat = CT_PATTERNS[cp];
      captionsHtml += '<div class="gcap gcap-g' + (cp+1) + '"><b>' + cpat.label + '</b>' + cpat.caption + '</div>';
    }

    var theadRows = '';
    if (hasSuper) theadRows += '<tr class="super-group-row">' + superHtml + '</tr>';
    theadRows += '<tr class="group-header-row">' + groupHtml + '</tr>';
    theadRows += '<tr class="col-header-row" id="ct-col-header-row"></tr>';

    var html = '' +
      '<div class="s1-intro">Capital deployment tests are the binary go / no-go triggers - the point at which a setup either passes its test (deploy capital) or fails it (wait or skip). Each test is the AND of its named constituent tests, shown as individual tick columns alongside a per-pattern rating and score. Each carries a mandatory confirmation test to avoid false starts. Each tile has a rating-tier filter row: click a tier chip to show only stocks at that tier, or click the tile body to select all tiers. Tier selections within a test combine as OR; selections across tests combine as AND.</div>' +
      '<div class="controls s1-controls">' +
        '<div class="ctrl-grp"><span class="ctrl-label">Inputs</span>' +
          '<button class="toggle-btn active" data-ct-grp="inputs" data-ct-val="pct" onclick="ctSetMode(\'inputs\',\'pct\')">show as %</button>' +
          '<button class="toggle-btn" data-ct-grp="inputs" data-ct-val="raw" onclick="ctSetMode(\'inputs\',\'raw\')">show as numbers</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Scope</span>' +
          '<button class="toggle-btn active" data-ct-scope="all" onclick="ctSetScope(\'all\')">All <span id="ct-cnt-all"></span></button>' +
          '<button class="toggle-btn" data-ct-scope="live" onclick="ctSetScope(\'live\')">Live <span id="ct-cnt-live"></span></button>' +
          '<button class="toggle-btn" data-ct-scope="sector" onclick="ctSetScope(\'sector\')">Sectors <span id="ct-cnt-sector"></span></button>' +
          '<button class="toggle-btn" data-ct-scope="industry" onclick="ctSetScope(\'industry\')">Industries <span id="ct-cnt-industry"></span></button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Peers</button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Cohorts</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Colour by</span>' +
          '<button class="toggle-btn active" data-ct-tint="none" onclick="ctSetTint(\'none\')">Off</button>' +
          '<button class="toggle-btn" data-ct-tint="industry" onclick="ctSetTint(\'industry\')">Industry</button>' +
          '<button class="toggle-btn" data-ct-tint="sector" onclick="ctSetTint(\'sector\')">Sector</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Portfolio tint</span>' +
          '<button class="toggle-btn active" data-ct-port="off" onclick="ctSetPort(\'off\')">Off</button>' +
          '<button class="toggle-btn" data-ct-port="on" onclick="ctSetPort(\'on\')">On</button>' +
        '</div>' +
      '</div>' +
      '<div class="rating-tiles s1-rating-tiles" id="ct-pattern-tiles"></div>' +
      '<div class="group-captions">' + captionsHtml + '</div>' +
      '<div class="table-wrap">' +
        '<table class="data-table" id="ct-main-table">' +
          '<colgroup>' + colgroupHtml + '</colgroup>' +
          '<thead>' + theadRows + '</thead>' +
          '<tbody id="ct-tbody"></tbody>' +
        '</table>' +
      '</div>';
    host.innerHTML = html;
    var tiles = document.getElementById('ct-pattern-tiles');
    if (tiles) {
      tiles.addEventListener('click', function(e) {
        var chip = e.target.closest('.pi-tier-chip');
        if (chip) {
          var cp = chip.getAttribute('data-pattern');
          var ct = chip.getAttribute('data-tier');
          if (cp && ct) ctToggleTier(cp, ct);
          return;
        }
        var tile = e.target.closest('.rating-tile');
        if (!tile) return;
        var k = tile.getAttribute('data-pattern');
        if (k) ctSelectAllTiers(k);
      });
    }
    var hdr = document.getElementById('ct-col-header-row');
    if (hdr) {
      hdr.addEventListener('click', function(e) {
        var th = e.target.closest('th');
        if (!th) return;
        var key = th.getAttribute('data-sort-key');
        if (key) ctOnSort(key);
      });
    }
    return true;
  }

  function renderTests() {
    if (!ctBuildScaffold()) return;
    ctBuildHeaderRow();
    ctRenderRows();
  }
  window.renderTests = renderTests;

})();

/* MD-V2-TESTS-MARKER-END */
