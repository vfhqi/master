/* MD-V2-POST-INDICATORS-MARKER-START */

(function() {
  'use strict';

  // MD-V2-S26-CHIPS-MARKER: po tab module - rating-tier multi-select chip
  // filter + per-pattern rating/score/test columns, structured identically to
  // the proven Pre-test indicators module. Reads md_v2.post_indicators.

  var poState = {
    mode: { inputs: 'pct' },
    scope: 'all',
    tierFilter: {},
    tint: 'none',
    port: 'off',
    sort: { col: 'company', dir: 'asc' }
  };

  var PO_PATTERNS = [
  {
    "key": "breakout",
    "label": "Breakout",
    "shortLabel": "Breakout",
    "supergroup": "bull",
    "tierLadder": [
      "Possible",
      "Probable"
    ],
    "total": 2,
    "tooltip": "Price more than 8% above its 5-day average, with up-day volume at least 10% above down-day volume.",
    "caption": "A confirmed upside break. Two tests, both must pass: price more than 8% above the 5-day moving average AND recent up-day volume at least 10% higher than down-day volume.",
    "tests": [
      {
        "key": "t1_price_gt_108pct_5dma",
        "label": "Price 8%+ above 5-day MA",
        "tooltip": "Current price is more than 8% above the 5-day moving average"
      },
      {
        "key": "t2_updown_vol_ge110",
        "label": "Up-volume 10%+ above down-volume",
        "tooltip": "Recent up-day trading volume is at least 10% higher than down-day volume"
      }
    ]
  },
  {
    "key": "advancing",
    "label": "Advancing",
    "shortLabel": "Advancing",
    "supergroup": "bull",
    "tierLadder": [
      "Possible",
      "Plausible",
      "Probable"
    ],
    "total": 3,
    "tooltip": "Price above its 20-day average and the 20-day average rising - a steady advance without a breakout spike.",
    "caption": "A steady advance without a breakout spike. Qualifies on three tests (price above the 20-day moving average, 20-day moving average rising, and not currently in a breakout) - the not-in-breakout test is part of the logic but not shown as a column.",
    "tests": [
      {
        "key": "t1_price_above_20dma",
        "label": "Price above 20-day MA",
        "tooltip": "Current price is above the 20-day moving average"
      },
      {
        "key": "t2_20dma_rising",
        "label": "20-day MA rising",
        "tooltip": "20-day moving average is higher today than yesterday"
      }
    ]
  },
  {
    "key": "breakdown_50D",
    "label": "Breakdown through 50-day MA",
    "shortLabel": "Breakdown 50D",
    "supergroup": "bear",
    "tierLadder": [
      "Possible",
      "Probable"
    ],
    "total": 2,
    "tooltip": "Price has dropped below its 50-day average, having been at or above it on the prior bar.",
    "caption": "A fresh break below medium-term support. Two tests, both must pass: price below the 50-day moving average AND price was at or above the 50-day moving average on the prior bar.",
    "tests": [
      {
        "key": "t1_price_below_50dma",
        "label": "Price below 50-day MA",
        "tooltip": "Current price is below the 50-day moving average"
      },
      {
        "key": "t2_prev_at_or_above_50dma",
        "label": "Was at/above 50-day MA",
        "tooltip": "Price was at or above the 50-day moving average on the prior bar - confirms this is a fresh break"
      }
    ]
  },
  {
    "key": "breakdown_150D",
    "label": "Breakdown through 150-day MA",
    "shortLabel": "Breakdown 150D",
    "supergroup": "bear",
    "tierLadder": [
      "Possible",
      "Probable"
    ],
    "total": 2,
    "tooltip": "Price has dropped below its 150-day average, having been at or above it on the prior bar.",
    "caption": "A fresh break below the medium/long-term trend. Two tests, both must pass: price below the 150-day moving average AND price was at or above the 150-day moving average on the prior bar.",
    "tests": [
      {
        "key": "t1_price_below_150dma",
        "label": "Price below 150-day MA",
        "tooltip": "Current price is below the 150-day moving average"
      },
      {
        "key": "t2_prev_at_or_above_150dma",
        "label": "Was at/above 150-day MA",
        "tooltip": "Price was at or above the 150-day moving average on the prior bar"
      }
    ]
  },
  {
    "key": "breakdown_200D",
    "label": "Breakdown through 200-day MA",
    "shortLabel": "Breakdown 200D",
    "supergroup": "bear",
    "tierLadder": [
      "Possible",
      "Probable"
    ],
    "total": 2,
    "tooltip": "Price has dropped below its 200-day average, having been at or above it on the prior bar.",
    "caption": "A fresh break below the long-term trend - the most serious of the three. Two tests, both must pass: price below the 200-day moving average AND price was at or above the 200-day moving average on the prior bar.",
    "tests": [
      {
        "key": "t1_price_below_200dma",
        "label": "Price below 200-day MA",
        "tooltip": "Current price is below the 200-day moving average"
      },
      {
        "key": "t2_prev_at_or_above_200dma",
        "label": "Was at/above 200-day MA",
        "tooltip": "Price was at or above the 200-day moving average on the prior bar"
      }
    ]
  }
];
  var PO_SUPERGROUPS = [{"key": "bull", "label": "Bullish post-test indicators", "cls": "sg-positive"}, {"key": "bear", "label": "Bearish post-test indicators", "cls": "sg-negative"}];
  var PO_TONE = {"breakout": "pi-tile-pullback", "advancing": "pi-tile-basing", "breakdown_50D": "pi-tile-collapsing", "breakdown_150D": "pi-tile-amber", "breakdown_200D": "pi-tile-navy"};
  var PO_STRIP = {"breakout": "pi-strip-pullback", "advancing": "pi-strip-basing", "breakdown_50D": "pi-strip-collapsing", "breakdown_150D": "pi-strip-amber", "breakdown_200D": "pi-strip-navy"};
  var PO_CHIP = {"breakout": "pullback", "advancing": "basing", "breakdown_50D": "collapsing", "breakdown_150D": "amber", "breakdown_200D": "navy"};

  // init tierFilter keyed by pattern
  for (var _ip = 0; _ip < PO_PATTERNS.length; _ip++) {
    poState.tierFilter[PO_PATTERNS[_ip].key] = [];
  }

  var PO_RATING_RANK = { 'Probable':4, 'Plausible':3, 'Possible':2, 'None':1 };
  var PO_RATING_CLS  = { 'Probable':'tint-prob', 'Plausible':'tint-pla', 'Possible':'tint-pos', 'None':'tint-none' };

  function poBuildCols() {
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
    for (var p = 0; p < PO_PATTERNS.length; p++) {
      var pat = PO_PATTERNS[p];
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
  var PO_COLS = poBuildCols();

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

  function poPatternRec(row, patternKey) {
    var dk = row.md_v2 && row.md_v2.post_indicators;
    return (dk && dk[patternKey]) || null;
  }
  function poEvalTest(row, patternKey, testKey) {
    var rec = poPatternRec(row, patternKey);
    if (!rec || !rec.tests) return false;
    return !!rec.tests[testKey];
  }
  function poRowRating(row, patternKey) {
    var rec = poPatternRec(row, patternKey);
    return rec ? (rec.rating || 'None') : 'None';
  }

  function poGetRows() {
    var raw = (window.MASTER_DATA && MASTER_DATA.filters) || [];
    var prices = poPricesLookup();
    var live = poLiveTickers(), liveS = poLiveSectors(), liveI = poLiveIndustries();
    var rows = [];
    for (var i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || !s.md_v2 || !s.md_v2.post_indicators) continue;
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

  function poPatternCounts(rows) {
    var c = {};
    for (var pi = 0; pi < PO_PATTERNS.length; pi++) c[PO_PATTERNS[pi].key] = 0;
    for (var i = 0; i < rows.length; i++) {
      for (var p = 0; p < PO_PATTERNS.length; p++) {
        var rec = poPatternRec(rows[i], PO_PATTERNS[p].key);
        if (rec && rec.qualifies) c[PO_PATTERNS[p].key]++;
      }
    }
    return c;
  }
  function poPassHistogram(rows, patternKey, total) {
    var h = [];
    for (var k = 0; k <= total; k++) h[k] = 0;
    for (var i = 0; i < rows.length; i++) {
      var rec = poPatternRec(rows[i], patternKey);
      var cnt = rec ? (rec.count || 0) : 0;
      if (cnt >= 0 && cnt <= total) h[cnt]++;
    }
    return h;
  }
  function poTierCounts(rows, patternKey) {
    var c = { 'Possible':0, 'Plausible':0, 'Probable':0, 'None':0 };
    for (var i = 0; i < rows.length; i++) {
      var r = poRowRating(rows[i], patternKey);
      if (c[r] != null) c[r]++;
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
    if (key === 'recent_pullback') {
      if (v == null || isNaN(v)) return '<td class="num ' + extraCls + '">-</td>';
      var pctVal = v * 100;
      var pi_intensity = Math.max(-1, Math.min(1, (pctVal - 5) / 20));
      var col = poColourForIntensity(-pi_intensity);
      return '<td class="num ' + extraCls + '" style="color:' + col + '">' + Math.round(pctVal) + '%</td>';
    }
    if (v == null || row.price == null) return '<td class="num ' + extraCls + '">-</td>';
    var pct = (row.price - v) / v * 100;
    var intensity = 0;
    if (key === 'high_52w') intensity = Math.max(-1, Math.min(1, (-pct - 5) / 20));
    else if (key === 'low_52w') intensity = Math.max(-1, Math.min(1, (pct - 20) / 30));
    else if (key === 'ma_150' || key === 'ma_200') intensity = Math.max(-1, Math.min(1, pct / 10));
    var colour = poColourForIntensity(intensity);
    var text = (poState.mode.inputs === 'pct') ? poFmtPct(pct) : poFmtNum(v);
    return '<td class="num ' + extraCls + '" style="color:' + colour + '">' + text + '</td>';
  }
  function poTestCell(row, col) {
    var pass = poEvalTest(row, col.patternKey, col.testKey);
    var extra = col.cls || '';
    if (pass) return '<td class="pi-pass ' + extra + '"><span class="tick">' + String.fromCharCode(10003) + '</span></td>';
    return '<td class="pi-fail ' + extra + '">.</td>';
  }
  function poRatingCell(row, col) {
    var rating = poRowRating(row, col.patternKey);
    var rcls = PO_RATING_CLS[rating] || 'tint-none';
    return '<td class="' + (col.cls || '') + ' pi-rating-cell ' + rcls + '"><span class="pi-pill pi-pill-' + rcls + '">' + rating + '</span></td>';
  }
  function poScoreCell(row, col) {
    var rec = poPatternRec(row, col.patternKey);
    var cnt = rec ? (rec.count || 0) : 0;
    var tot = rec ? (rec.total || 0) : 0;
    var s = '';
    for (var i = 0; i < tot; i++) s += '<span class="pip ' + (i < cnt ? 'on' : '') + '"></span>';
    return '<td class="' + (col.cls || '') + ' pi-score-cell"><div class="pi-pip-row">' + s +
           '<span class="pi-score-num">' + cnt + '/' + tot + '</span></div></td>';
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
      var patternKey = parts[0], sub = parts[1];
      var rec = poPatternRec(row, patternKey);
      if (sub === 'rating') return rec ? (PO_RATING_RANK[rec.rating] || 0) : 0;
      if (sub === 'score')  return rec ? (rec.count || 0) : 0;
      return poEvalTest(row, patternKey, sub) ? 1 : 0;
    }
    if (key === 'recent_pullback') return row.recent_pullback == null ? -Infinity : row.recent_pullback;
    var PCT_KEYS = ['high_52w','low_52w','ma_150','ma_200'];
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
  function poPatternTiles(scopeRows) {
    var tiles = document.getElementById('po-pattern-tiles');
    if (!tiles) return;
    var counts = poPatternCounts(scopeRows);
    var total = scopeRows.length;
    var h = '';
    for (var i = 0; i < PO_PATTERNS.length; i++) {
      var pat = PO_PATTERNS[i];
      var cnt = counts[pat.key] || 0;
      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;
      var sel = poState.tierFilter[pat.key] || [];
      var anySel = sel.length > 0;
      var tierCounts = poTierCounts(scopeRows, pat.key);
      var headline = cnt, headSub = 'of ' + total.toLocaleString('en-GB') + ' &middot; ' + pct + '%';
      if (anySel) {
        var ft = 0;
        for (var z = 0; z < sel.length; z++) ft += (tierCounts[sel[z]] || 0);
        headline = ft;
        headSub = sel.join(' + ') + ' &middot; filtered';
      }
      var hist = poPassHistogram(scopeRows, pat.key, pat.total);
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
        chips += '<span class="pi-tier-chip pi-chip-' + PO_CHIP[pat.key] +
                 (on ? ' on' : '') + '" data-pattern="' + pat.key + '" data-tier="' + tier + '">' +
                 tier + ' ' + tc.toLocaleString('en-GB') + (on ? ' ' + String.fromCharCode(10003) : '') + '</span>';
      }
      var activeCls = anySel ? ' active' : '';
      h += '<div class="rating-tile ' + PO_TONE[pat.key] + activeCls + '" data-pattern="' + pat.key + '" title="' + pat.tooltip + '">' +
           '<div class="rt-label">' + pat.shortLabel + '</div>' +
           '<div class="rt-count">' + headline.toLocaleString('en-GB') + '</div>' +
           '<div class="rt-sub">' + headSub + '</div>' +
           '<div class="rt-breakdown">' + breakdown + '</div>' +
           '<div class="pi-tier-chips" data-pattern="' + pat.key + '">' + chips + '</div>' +
           '<div class="rt-strip ' + PO_STRIP[pat.key] + '"></div>' +
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
  function poApplyScope(all) {
    var rows = all.slice();
    if (poState.scope === 'live') rows = rows.filter(function(r){ return r.is_live; });
    else if (poState.scope === 'sector') rows = rows.filter(function(r){ return r.sector_in_portfolio; });
    else if (poState.scope === 'industry') rows = rows.filter(function(r){ return r.industry_in_portfolio; });
    return rows;
  }
  function poApplyTierFilter(rows) {
    var active = [];
    for (var p = 0; p < PO_PATTERNS.length; p++) {
      var k = PO_PATTERNS[p].key;
      var sel = poState.tierFilter[k] || [];
      if (sel.length > 0) active.push({ key: k, tiers: sel });
    }
    if (active.length === 0) return rows;
    return rows.filter(function(r) {
      for (var a = 0; a < active.length; a++) {
        var rating = poRowRating(r, active[a].key);
        if (active[a].tiers.indexOf(rating) === -1) return false;
      }
      return true;
    });
  }
  function poRenderRows() {
    var tbody = document.getElementById('po-tbody');
    if (!tbody) return;
    var all = poGetRows();
    var scopeRows = poApplyScope(all);
    poUpdateScopeCounts(all);
    poPatternTiles(scopeRows);
    var rows = poApplyTierFilter(scopeRows);
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
        var pinf = poPortfolioInfo(s);
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
        poInputCell(s, 'price') + poInputCell(s, 'high_52w') + poInputCell(s, 'low_52w') +
        poInputCell(s, 'ma_150') + poInputCell(s, 'ma_200') + poInputCell(s, 'recent_pullback');
      for (var j = 8; j < PO_COLS.length; j++) {
        var col = PO_COLS[j];
        if (col.kind === 'rating') html += poRatingCell(s, col);
        else if (col.kind === 'score') html += poScoreCell(s, col);
        else html += poTestCell(s, col);
      }
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
  function poToggleTier(patternKey, tier) {
    var sel = poState.tierFilter[patternKey] || [];
    var idx = sel.indexOf(tier);
    if (idx > -1) sel.splice(idx, 1);
    else sel.push(tier);
    poState.tierFilter[patternKey] = sel;
    poRenderRows();
  }
  function poSelectAllTiers(patternKey) {
    var pat = null;
    for (var p = 0; p < PO_PATTERNS.length; p++) if (PO_PATTERNS[p].key === patternKey) pat = PO_PATTERNS[p];
    if (!pat) return;
    var sel = poState.tierFilter[patternKey] || [];
    var allOn = sel.length === pat.tierLadder.length;
    poState.tierFilter[patternKey] = allOn ? [] : pat.tierLadder.slice();
    poRenderRows();
  }
  window.poSetMode = poSetMode;
  window.poSetScope = poSetScope;
  window.poSetTint = poSetTint;
  window.poSetPort = poSetPort;
  window.poToggleTier = poToggleTier;
  window.poSelectAllTiers = poSelectAllTiers;
  window.poOnSort = poOnSort;

  function poBuildScaffold() {
    var host = document.getElementById('tab-post_indicators');
    if (!host) return false;
    if (host.querySelector('#po-main-table')) return true;

    var colgroupHtml = '<col class="c-name"><col class="c-taxon">' +
                       '<col class="c-price"><col class="c-52wh"><col class="c-52wl">' +
                       '<col class="c-ma150"><col class="c-ma200"><col class="c-pullback">';
    var inputsColspan = 8;
    var hasSuper = PO_SUPERGROUPS.length > 0;
    var superHtml = '<th class="gh-inputs sg-spacer" colspan="' + inputsColspan + '"></th>';
    var groupHtml = '<th class="gh-inputs" colspan="' + inputsColspan + '">Inputs</th>';

    if (hasSuper) {
      var sgCols = {};
      for (var sgi = 0; sgi < PO_SUPERGROUPS.length; sgi++) sgCols[PO_SUPERGROUPS[sgi].key] = 0;
      for (var sp = 0; sp < PO_PATTERNS.length; sp++) {
        var cspan = 2 + PO_PATTERNS[sp].tests.length;
        sgCols[PO_PATTERNS[sp].supergroup] += cspan;
      }
      for (var sgj = 0; sgj < PO_SUPERGROUPS.length; sgj++) {
        var sg = PO_SUPERGROUPS[sgj];
        superHtml += '<th class="' + sg.cls + '" colspan="' + sgCols[sg.key] + '">' + sg.label + '</th>';
      }
    }

    for (var p = 0; p < PO_PATTERNS.length; p++) {
      var pat = PO_PATTERNS[p];
      var gi = p + 1;
      var n = pat.tests.length;
      colgroupHtml += '<col class="c-rating"><col class="c-score">';
      for (var t = 0; t < n; t++) colgroupHtml += '<col class="c-test">';
      groupHtml += '<th class="gh-g' + gi + ' grp-start-g' + gi + '" colspan="' + (n + 2) + '">' + pat.label + '</th>';
    }

    var captionsHtml = '';
    for (var cp = 0; cp < PO_PATTERNS.length; cp++) {
      var cpat = PO_PATTERNS[cp];
      captionsHtml += '<div class="gcap gcap-g' + (cp+1) + '"><b>' + cpat.label + '</b>' + cpat.caption + '</div>';
    }

    var theadRows = '';
    if (hasSuper) theadRows += '<tr class="super-group-row">' + superHtml + '</tr>';
    theadRows += '<tr class="group-header-row">' + groupHtml + '</tr>';
    theadRows += '<tr class="col-header-row" id="po-col-header-row"></tr>';

    var html = '' +
      '<div class="s1-intro">Post-test indicators are five trailing price-action patterns that confirm what price has just done. Each pattern is the AND of its named constituent tests, shown below as individual tick columns alongside a per-pattern rating and score. The two bullish patterns (Breakout, Advancing) sit under one super-group; the three Breakdown patterns sit under the bearish super-group. Each tile has a rating-tier filter row: click a tier chip to show only stocks at that tier, or click the tile body to select all tiers. Tier selections within a pattern combine as OR; selections across patterns combine as AND.</div>' +
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
      '<div class="group-captions">' + captionsHtml + '</div>' +
      '<div class="table-wrap">' +
        '<table class="data-table" id="po-main-table">' +
          '<colgroup>' + colgroupHtml + '</colgroup>' +
          '<thead>' + theadRows + '</thead>' +
          '<tbody id="po-tbody"></tbody>' +
        '</table>' +
      '</div>';
    host.innerHTML = html;
    var tiles = document.getElementById('po-pattern-tiles');
    if (tiles) {
      tiles.addEventListener('click', function(e) {
        var chip = e.target.closest('.pi-tier-chip');
        if (chip) {
          var cp = chip.getAttribute('data-pattern');
          var ct = chip.getAttribute('data-tier');
          if (cp && ct) poToggleTier(cp, ct);
          return;
        }
        var tile = e.target.closest('.rating-tile');
        if (!tile) return;
        var k = tile.getAttribute('data-pattern');
        if (k) poSelectAllTiers(k);
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
