/* MD-V2-PRE-INDICATORS-MARKER-START */

(function() {
  'use strict';

  // MD-V2-PI-CHIPS-S25-MARKER: rating-tier multi-select chip filter (D-MD-V2-59).
  // piState.tierFilter holds, per pattern, an array of selected rating tiers.
  // Empty array = no tier filter for that pattern (shows all). Intra-pattern
  // selections OR-combine; cross-pattern selections AND-combine.
  var piState = {
    mode: { inputs: 'pct' },
    scope: 'all',
    tierFilter: { pulling_back_uptrend: [], basing: [], collapsing: [] },
    tint: 'none',
    port: 'off',
    sort: { col: 'company', dir: 'asc' }
  };

  // The 3 pre-test indicator patterns. testKey values must match the keys in
  // md_v2.pre_indicators[patternKey].tests emitted by _md_v2_screens.py.
  // tierLadder: the Option A rating tiers this pattern can take (D-MD-V2-55).
  // 2-test patterns (Collapsing) have no Plausible tier.
  var PI_PATTERNS = [
    {
      key: 'pulling_back_uptrend',
      label: 'Pulling back within MT/LT uptrend',
      shortLabel: 'Pulling back',
      supergroup: 'positive',
      tierLadder: ['Possible', 'Plausible', 'Probable'],
      tooltip: 'Stock in a real medium/long-term uptrend (50-day and 150-day moving averages still rising) that is currently pulling back (5-day and 10-day moving averages rolling over).',
      caption: 'In a genuine medium/long-term uptrend AND currently inside a pullback. Four tests, all must pass: 50-day MA still rising AND 150-day MA still rising AND 5-day MA rolling over AND 10-day MA rolling over.',
      total: 4,
      tests: [
        { key: 't1_50d_rising',       label: '50-day MA still rising',  tooltip: '50-day moving average is higher today than yesterday' },
        { key: 't2_150d_rising',      label: '150-day MA still rising', tooltip: '150-day moving average is higher today than yesterday' },
        { key: 't3_5d_rolling_over',  label: '5-day MA rolling over',   tooltip: '5-day moving average is lower today than yesterday - confirms we are inside a pullback' },
        { key: 't4_10d_rolling_over', label: '10-day MA rolling over',  tooltip: '10-day moving average is lower today than yesterday' }
      ]
    },
    {
      key: 'basing',
      label: 'Basing',
      shortLabel: 'Basing',
      supergroup: 'positive',
      tierLadder: ['Possible', 'Plausible', 'Probable'],
      tooltip: 'Price fell at least 15% from a recent swing high to a recent low (even if partly reclawed since), has stayed below that high for at least 20 trading days, sits above its 200-day MA, and the 200-day MA is still rising.',
      caption: 'A genuine base forming within a long-term uptrend. Four tests, all must pass: price fell at least 15% from recent swing high AND price below that high for at least 20 trading days AND price above the 200-day MA AND the 200-day MA still rising month-on-month.',
      total: 4,
      tests: [
        { key: 't1_price_pullback_ge15',   label: 'Price pullback at least 15%',    tooltip: 'Deepest drawdown from the recent swing high reached at least 15% - even if price has since reclawed some of the loss' },
        { key: 't2_time_below_high_ge20d', label: 'Below high at least L20D',        tooltip: 'Price has been below the recent swing high for at least the last 20 trading days' },
        { key: 't3_price_above_200d',      label: 'Price above 200-day MA',          tooltip: 'Current price is above the 200-day moving average' },
        { key: 't4_200d_rising',           label: '200-day MA still rising',         tooltip: '200-day moving average is rising month-on-month (this month versus last month)' }
      ]
    },
    {
      key: 'collapsing',
      label: 'Collapsing',
      shortLabel: 'Collapsing',
      supergroup: 'negative',
      tierLadder: ['Possible', 'Probable'],
      tooltip: 'Price is 30% or more below its 52-week high AND has fallen at least 20% from its recent high.',
      caption: 'A stock in genuine breakdown. Two tests, both must pass: price 30%+ below the 52-week high AND price fallen at least 20% from its recent high.',
      total: 2,
      tests: [
        { key: 't1_price_le_70pct_52wh', label: 'Price 30%+ below 52W high', tooltip: 'Current price is 30% or more below the 52-week high' },
        { key: 't2_pullback_ge20',       label: 'Pullback at least 20%',     tooltip: 'Recent pullback from the recent high is at least 20%' }
      ]
    }
  ];

  var PI_RATING_RANK = { 'Probable':4, 'Plausible':3, 'Possible':2, 'None':1 };
  var PI_RATING_CLS  = { 'Probable':'tint-prob', 'Plausible':'tint-pla', 'Possible':'tint-pos', 'None':'tint-none' };

  function buildCols() {
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
    for (var p = 0; p < PI_PATTERNS.length; p++) {
      var pat = PI_PATTERNS[p];
      var gi = p + 1;
      cols.push({ id:'p'+gi+'_rating', label:'Rating', sortKey:pat.key+'__rating', cls:'grp-start-g'+gi+' pi-rating-col', kind:'rating', patternKey:pat.key });
      cols.push({ id:'p'+gi+'_score',  label:'Score',  sortKey:pat.key+'__score',  cls:'pi-score-col',                   kind:'score',  patternKey:pat.key });
      for (var t = 0; t < pat.tests.length; t++) {
        var test = pat.tests[t];
        cols.push({
          id: 'p'+gi+'t'+(t+1),
          label: test.label,
          sortKey: pat.key + '__' + test.key,
          cls: '',
          tooltip: test.tooltip,
          kind: 'test',
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

  function piPatternRec(row, patternKey) {
    var pi = row.md_v2 && row.md_v2.pre_indicators;
    return (pi && pi[patternKey]) || null;
  }
  function piEvalTest(row, patternKey, testKey) {
    var rec = piPatternRec(row, patternKey);
    if (!rec || !rec.tests) return false;
    return !!rec.tests[testKey];
  }
  function piRowRating(row, patternKey) {
    var rec = piPatternRec(row, patternKey);
    return rec ? (rec.rating || 'None') : 'None';
  }

  function piGetRows() {
    var raw = (window.MASTER_DATA && MASTER_DATA.filters) || [];
    var prices = piPricesLookup();
    var live = piLiveTickers(), liveS = piLiveSectors(), liveI = piLiveIndustries();
    var rows = [];
    for (var i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || !s.md_v2 || !s.md_v2.pre_indicators) continue;
      var p = prices[s.ticker] || {};
      var mas = p.mas || {};
      rows.push({
        ticker: s.ticker, company: p.company_name || s.ticker,
        sector: p.sector || '', industry: p.industry || '',
        price: p.price, high_52w: p.high_52w, low_52w: p.low_52w,
        recent_pullback: p.recent_pullback_pct,
        swing_high: p.swing_high,
        ma_150: mas['150D'], ma_200: mas['200D'],
        md_v2: s.md_v2,
        is_live: !!live[s.ticker],
        sector_in_portfolio: !!liveS[p.sector],
        industry_in_portfolio: !!liveI[p.industry]
      });
    }
    return rows;
  }

  // Per-pattern qualifying count (all tests pass).
  function piPatternCounts(rows) {
    var c = {};
    for (var pi = 0; pi < PI_PATTERNS.length; pi++) c[PI_PATTERNS[pi].key] = 0;
    for (var i = 0; i < rows.length; i++) {
      for (var p = 0; p < PI_PATTERNS.length; p++) {
        var rec = piPatternRec(rows[i], PI_PATTERNS[p].key);
        if (rec && rec.qualifies) c[PI_PATTERNS[p].key]++;
      }
    }
    return c;
  }
  // Per-pattern histogram of how many stocks pass exactly k tests (D-MD-V2-57).
  function piPassHistogram(rows, patternKey, total) {
    var h = [];
    for (var k = 0; k <= total; k++) h[k] = 0;
    for (var i = 0; i < rows.length; i++) {
      var rec = piPatternRec(rows[i], patternKey);
      var cnt = rec ? (rec.count || 0) : 0;
      if (cnt >= 0 && cnt <= total) h[cnt]++;
    }
    return h;
  }
  // MD-V2-PI-CHIPS-S25-MARKER: per-pattern, per-tier live counts (D-MD-V2-59).
  // Counted against the SCOPE-filtered row set (passed in) so chip counts
  // reflect what is currently in play, not the whole universe.
  function piTierCounts(rows, patternKey) {
    var c = { 'Possible':0, 'Plausible':0, 'Probable':0, 'None':0 };
    for (var i = 0; i < rows.length; i++) {
      var r = piRowRating(rows[i], patternKey);
      if (c[r] != null) c[r]++;
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
    else if (key === 'low_52w') intensity = Math.max(-1, Math.min(1, (pct - 20) / 30));
    else if (key === 'ma_150' || key === 'ma_200') intensity = Math.max(-1, Math.min(1, pct / 10));
    var colour = piColourForIntensity(intensity);
    var text = (piState.mode.inputs === 'pct') ? piFmtPct(pct) : piFmtNum(v);
    return '<td class="num ' + extraCls + '" style="color:' + colour + '">' + text + '</td>';
  }

  function piTestCell(row, col) {
    var pass = piEvalTest(row, col.patternKey, col.testKey);
    var extra = col.cls || '';
    if (pass) return '<td class="pi-pass ' + extra + '"><span class="tick">' + String.fromCharCode(10003) + '</span></td>';
    return '<td class="pi-fail ' + extra + '">.</td>';
  }
  function piRatingCell(row, col) {
    var rating = piRowRating(row, col.patternKey);
    var rcls = PI_RATING_CLS[rating] || 'tint-none';
    return '<td class="' + (col.cls || '') + ' pi-rating-cell ' + rcls + '"><span class="pi-pill pi-pill-' + rcls + '">' + rating + '</span></td>';
  }
  function piScoreCell(row, col) {
    var rec = piPatternRec(row, col.patternKey);
    var cnt = rec ? (rec.count || 0) : 0;
    var tot = rec ? (rec.total || 0) : 0;
    var s = '';
    for (var i = 0; i < tot; i++) s += '<span class="pip ' + (i < cnt ? 'on' : '') + '"></span>';
    return '<td class="' + (col.cls || '') + ' pi-score-cell"><div class="pi-pip-row">' + s +
           '<span class="pi-score-num">' + cnt + '/' + tot + '</span></div></td>';
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
    if (key.indexOf('__') > 0) {
      var parts = key.split('__');
      var patternKey = parts[0], sub = parts[1];
      var rec = piPatternRec(row, patternKey);
      if (sub === 'rating') return rec ? (PI_RATING_RANK[rec.rating] || 0) : 0;
      if (sub === 'score')  return rec ? (rec.count || 0) : 0;
      return piEvalTest(row, patternKey, sub) ? 1 : 0;
    }
    if (key === 'recent_pullback') {
      return row.recent_pullback == null ? -Infinity : row.recent_pullback;
    }
    var PCT_KEYS = ['high_52w','low_52w','ma_150','ma_200'];
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

  // MD-V2-PI-CHIPS-S25-MARKER: render pattern tiles + the rating-tier chip row.
  // The `scopeRows` argument is the SCOPE-filtered set (so chip counts and the
  // pass-count breakdown reflect the active scope), NOT the tier-filtered set.
  function piPatternTiles(scopeRows) {
    var tiles = document.getElementById('pi-pattern-tiles');
    if (!tiles) return;
    var counts = piPatternCounts(scopeRows);
    var total = scopeRows.length;
    var tintCls = { 'pulling_back_uptrend':'pi-tile-pullback', 'basing':'pi-tile-basing', 'collapsing':'pi-tile-collapsing' };
    var stripCls = { 'pulling_back_uptrend':'pi-strip-pullback', 'basing':'pi-strip-basing', 'collapsing':'pi-strip-collapsing' };
    var h = '';
    for (var i = 0; i < PI_PATTERNS.length; i++) {
      var pat = PI_PATTERNS[i];
      var cnt = counts[pat.key] || 0;
      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;
      var sel = piState.tierFilter[pat.key] || [];
      var anySel = sel.length > 0;
      // headline = filtered total when a tier filter is active, else the qualifying count
      var tierCounts = piTierCounts(scopeRows, pat.key);
      var headline = cnt, headSub = 'of ' + total.toLocaleString('en-GB') + ' &middot; ' + pct + '%';
      if (anySel) {
        var ft = 0;
        for (var z = 0; z < sel.length; z++) ft += (tierCounts[sel[z]] || 0);
        headline = ft;
        headSub = sel.join(' + ') + ' &middot; filtered';
      }
      // pass-count breakdown line (D-MD-V2-57)
      var hist = piPassHistogram(scopeRows, pat.key, pat.total);
      var breakdown = '';
      for (var k = 1; k <= pat.total; k++) {
        if (k > 1) breakdown += ' &middot; ';
        breakdown += k + ' of ' + pat.total + ': ' + (hist[k] || 0).toLocaleString('en-GB');
      }
      // rating-tier chip row (D-MD-V2-59)
      var chips = '';
      for (var c = 0; c < pat.tierLadder.length; c++) {
        var tier = pat.tierLadder[c];
        var on = sel.indexOf(tier) > -1;
        var tc = tierCounts[tier] || 0;
        chips += '<span class="pi-tier-chip pi-chip-' + tintCls[pat.key].replace('pi-tile-','') +
                 (on ? ' on' : '') + '" data-pattern="' + pat.key + '" data-tier="' + tier + '">' +
                 tier + ' ' + tc.toLocaleString('en-GB') + (on ? ' ' + String.fromCharCode(10003) : '') + '</span>';
      }
      var activeCls = anySel ? ' active' : '';
      h += '<div class="rating-tile ' + tintCls[pat.key] + activeCls + '" data-pattern="' + pat.key + '" title="' + pat.tooltip + '">' +
           '<div class="rt-label">' + pat.shortLabel + '</div>' +
           '<div class="rt-count">' + headline.toLocaleString('en-GB') + '</div>' +
           '<div class="rt-sub">' + headSub + '</div>' +
           '<div class="rt-breakdown">' + breakdown + '</div>' +
           '<div class="pi-tier-chips" data-pattern="' + pat.key + '">' + chips + '</div>' +
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

  // MD-V2-PI-CHIPS-S25-MARKER: apply scope, then the rating-tier filter.
  // Tier filter: for each pattern with a non-empty selected-tier list, the
  // row's rating for that pattern must be in the list (intra-pattern OR).
  // Patterns with non-empty lists AND-combine. Empty list = pattern ignored.
  function piApplyScope(all) {
    var rows = all.slice();
    if (piState.scope === 'live') rows = rows.filter(function(r){ return r.is_live; });
    else if (piState.scope === 'sector') rows = rows.filter(function(r){ return r.sector_in_portfolio; });
    else if (piState.scope === 'industry') rows = rows.filter(function(r){ return r.industry_in_portfolio; });
    return rows;
  }
  function piApplyTierFilter(rows) {
    var active = [];
    for (var p = 0; p < PI_PATTERNS.length; p++) {
      var k = PI_PATTERNS[p].key;
      var sel = piState.tierFilter[k] || [];
      if (sel.length > 0) active.push({ key: k, tiers: sel });
    }
    if (active.length === 0) return rows;
    return rows.filter(function(r) {
      for (var a = 0; a < active.length; a++) {
        var rating = piRowRating(r, active[a].key);
        if (active[a].tiers.indexOf(rating) === -1) return false;
      }
      return true;
    });
  }

  function piRenderRows() {
    var tbody = document.getElementById('pi-tbody');
    if (!tbody) return;
    var all = piGetRows();
    var scopeRows = piApplyScope(all);
    piUpdateScopeCounts(all);
    piPatternTiles(scopeRows);
    var rows = piApplyTierFilter(scopeRows);
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
        var pinf = piPortfolioInfo(s);
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
        piInputCell(s, 'price') + piInputCell(s, 'high_52w') + piInputCell(s, 'low_52w') +
        piInputCell(s, 'ma_150') + piInputCell(s, 'ma_200') + piInputCell(s, 'recent_pullback');
      for (var j = 8; j < PI_COLS.length; j++) {
        var col = PI_COLS[j];
        if (col.kind === 'rating') html += piRatingCell(s, col);
        else if (col.kind === 'score') html += piScoreCell(s, col);
        else html += piTestCell(s, col);
      }
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
  // MD-V2-PI-CHIPS-S25-MARKER: toggle a single rating tier for a pattern.
  function piToggleTier(patternKey, tier) {
    var sel = piState.tierFilter[patternKey] || [];
    var idx = sel.indexOf(tier);
    if (idx > -1) sel.splice(idx, 1);
    else sel.push(tier);
    piState.tierFilter[patternKey] = sel;
    piRenderRows();
  }
  // MD-V2-PI-CHIPS-S25-MARKER: tile-body click selects ALL tiers for a pattern
  // (D-MD-V2-59 Option A). If all are already selected, clear them (toggle off).
  function piSelectAllTiers(patternKey) {
    var pat = null;
    for (var p = 0; p < PI_PATTERNS.length; p++) if (PI_PATTERNS[p].key === patternKey) pat = PI_PATTERNS[p];
    if (!pat) return;
    var sel = piState.tierFilter[patternKey] || [];
    var allOn = sel.length === pat.tierLadder.length;
    piState.tierFilter[patternKey] = allOn ? [] : pat.tierLadder.slice();
    piRenderRows();
  }
  window.piSetMode = piSetMode;
  window.piSetScope = piSetScope;
  window.piSetTint = piSetTint;
  window.piSetPort = piSetPort;
  window.piToggleTier = piToggleTier;
  window.piSelectAllTiers = piSelectAllTiers;
  window.piOnSort = piOnSort;

  function piBuildScaffold() {
    var host = document.getElementById('tab-pre_indicators');
    if (!host) return false;
    if (host.querySelector('#pi-main-table')) return true;

    var colgroupHtml = '<col class="c-name"><col class="c-taxon">' +
                       '<col class="c-price"><col class="c-52wh"><col class="c-52wl">' +
                       '<col class="c-ma150"><col class="c-ma200"><col class="c-pullback">';
    var inputsColspan = 8;

    var superHtml = '<th class="gh-inputs sg-spacer" colspan="' + inputsColspan + '"></th>';
    var groupHtml = '<th class="gh-inputs" colspan="' + inputsColspan + '">Inputs</th>';

    var posCols = 0, negCols = 0;
    for (var sp = 0; sp < PI_PATTERNS.length; sp++) {
      var cspan = 2 + PI_PATTERNS[sp].tests.length;
      if (PI_PATTERNS[sp].supergroup === 'positive') posCols += cspan;
      else negCols += cspan;
    }
    superHtml += '<th class="sg-positive" colspan="' + posCols + '">Positive pre-test indicators</th>';
    superHtml += '<th class="sg-negative" colspan="' + negCols + '">Negative pre-test indicators</th>';

    for (var p = 0; p < PI_PATTERNS.length; p++) {
      var pat = PI_PATTERNS[p];
      var gi = p + 1;
      var n = pat.tests.length;
      colgroupHtml += '<col class="c-rating"><col class="c-score">';
      for (var t = 0; t < n; t++) colgroupHtml += '<col class="c-test">';
      groupHtml += '<th class="gh-g' + gi + ' grp-start-g' + gi + '" colspan="' + (n + 2) + '">' + pat.label + '</th>';
    }

    var captionsHtml = '';
    for (var cp = 0; cp < PI_PATTERNS.length; cp++) {
      var cpat = PI_PATTERNS[cp];
      captionsHtml += '<div class="gcap gcap-g' + (cp+1) + '"><b>' + cpat.label + '</b>' + cpat.caption + '</div>';
    }

    var html = '' +
      '<div class="s1-intro">Pre-test indicators are three leading price-action patterns drawn directly from price and moving-average data. Each pattern is the AND of its named constituent tests, shown below as individual tick columns alongside a per-pattern rating and score. The two positive patterns (Pulling back within a medium/long-term uptrend, and Basing) sit under one super-group; Collapsing sits under the negative super-group. Each tile has a rating-tier filter row: click a tier chip to show only stocks at that tier, or click the tile body to select all tiers. Tier selections within a pattern combine as OR; selections across patterns combine as AND.</div>' +
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
      '<div class="group-captions">' + captionsHtml + '</div>' +
      '<div class="table-wrap">' +
        '<table class="data-table" id="pi-main-table">' +
          '<colgroup>' + colgroupHtml + '</colgroup>' +
          '<thead>' +
            '<tr class="super-group-row">' + superHtml + '</tr>' +
            '<tr class="group-header-row">' + groupHtml + '</tr>' +
            '<tr class="col-header-row" id="pi-col-header-row"></tr>' +
          '</thead>' +
          '<tbody id="pi-tbody"></tbody>' +
        '</table>' +
      '</div>';
    host.innerHTML = html;
    // MD-V2-PI-CHIPS-S25-MARKER: tile click delegation - a chip click toggles
    // that tier; a click anywhere else on the tile selects all tiers (Option A).
    var tiles = document.getElementById('pi-pattern-tiles');
    if (tiles) {
      tiles.addEventListener('click', function(e) {
        var chip = e.target.closest('.pi-tier-chip');
        if (chip) {
          var cp = chip.getAttribute('data-pattern');
          var ct = chip.getAttribute('data-tier');
          if (cp && ct) piToggleTier(cp, ct);
          return;
        }
        var tile = e.target.closest('.rating-tile');
        if (!tile) return;
        var k = tile.getAttribute('data-pattern');
        if (k) piSelectAllTiers(k);
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
