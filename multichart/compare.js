/* compare.js v1.0: the Master Dashboard's multi-chart visual display (10-Nov-2026, Ricardinho, Systems Architect; project SA - Master Dashboard).
   Richard, 10-Nov-2026: two stocks per screen, price and moving averages on the left, volume on the right, adapted from the six-panel view;
   a frozen header of short dropdowns; every stock in the chosen population listed on the right; full width, no scrolling.
   His answers: choices in different dropdowns narrow each other ("Q5 = B"); default order closest to target moving average ("Q6 = B").
   His changes to mock-up 1 (13:00): columns of equal width; the volume window follows the price chart at 1W, 1M and 3M, and keeps the
   volume default for longer zooms; no explanatory footer; a coloured callout on any stock where a capital deployment or an exit is in play.
   Data: populations.json (master-dashboard/scripts/build_multichart.py, nightly); each stock's Per-stock Dashboard file (the PMS site:
   ratings/pms/data/latest/ for a stock we hold, pms-universe/ for any other); the Master Dashboard's chart files (master/charts/).
   Drawing: the six-panel view's own code (chart-renderer-dashboard.js drawMasterChart; compare-vol.js, generated from onescreen.js drawVol). */
(function () {
  'use strict';
  var BASE = window.MC_BASE || '/';
  var HELD_URL = BASE + 'ratings/pms/data/latest/', UNI_URL = BASE + 'pms-universe/';
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); };
  var MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  var dmy = function (s) { if (!s) return ''; var d = new Date(s + 'T00:00:00Z'); return d.getUTCDate() + '-' + MON[d.getUTCMonth()]; };
  var fileOf = function (t) { return t.replace(/[.\/]/g, '_') + '.json'; };
  var P, S, META, DD = {}, DES = {}, LBL = {}, GK;

  /* ---------- 1W on the price chart: the shared renderer knows 1M to 5Y, so the slice for 1W (the last five sessions) is added here ---------- */
  var _slice = window.getChartSlice;
  if (typeof _slice === 'function') window.getChartSlice = function (chart, zoom) { return zoom === '1W' ? chart.slice(Math.max(0, chart.length - 5)) : _slice(chart, zoom); };

  /* ---------- settings kept in this browser ---------- */
  var KEY = 'mcSettings', st = { sort: 'tma', vol: 'L3M', zoom: '12M', scale: 'lin', mas: null, sel: {} };
  try { var o = JSON.parse(localStorage.getItem(KEY) || 'null'); if (o) for (var k in st) if (o[k] != null) st[k] = o[k]; } catch (e) { /* not kept */ }
  function save() { try { st.zoom = chartZoom; st.scale = chartScaleMode; st.mas = {}; ['ma5','ma10','ma20','ma50','ma100','ma150','ma200'].forEach(function (k) { st.mas[k] = !!chartVis[k]; }); localStorage.setItem(KEY, JSON.stringify(st)); } catch (e) { /* not kept */ } }
  chartZoom = st.zoom; chartScaleMode = st.scale;
  ['obv', 'vol', 'vol20', 'vol50'].forEach(function (k) { chartVis[k] = false; });
  if (st.mas) for (var mk in st.mas) chartVis[mk] = !!st.mas[mk];
  /* the volume window: the price chart's at 1W, 1M and 3M; for longer zooms the volume default (L3M unless changed) */
  var FOLLOW = { '1W': 'L1W', '1M': 'L1M', '3M': 'L3M' };
  function volWin() { return FOLLOW[chartZoom] || st.vol; }

  /* ---------- the designations: the Master Dashboard Overview's own list of 18 (build_dashboard.py, the registry with ratingPath and tabId) ---------- */
  var REG = [
    ['Stages', [['stage_1', 'Stage 1 — Basing'], ['stage_2', 'Stage 2 — Uptrend'], ['stage_3', 'Stage 3 — Topping'], ['stage_4', 'Stage 4 — Decline']]],
    ['Early-stage pre-test indicators', [['pulling_back', 'Pulling back within MT/LT uptrend'], ['basing', 'Basing in a MT/LT uptrend'], ['collapsing', 'Collapsing']]],
    ['Late-stage capital qualification setups and tests', [['probing_bet_s1', 'Stage 1 — Speculative bet'], ['probing_bet_s2', 'Stage 2 — Probing bet'], ['healthy_retest', 'S2 — Retest setup'], ['vcp_deploy_s2', 'S2 — VCP deploy'], ['speculative_bet_s3', 'Stage 3 — Speculative bet'], ['speculative_bet_s4', 'Stage 4 — Speculative bet']]],
    ['Bullish post-setup/tests technical behaviour', [['breakout', 'Breakout'], ['advancing', 'Advancing']]],
    ['Negative breaking through key MAs', [['breakdown_50D', 'Breaking through 50D MA'], ['breakdown_150D', 'Breaking through 150D MA'], ['breakdown_200D', 'Breaking through 200D MA']]]];
  REG.forEach(function (g) { g[1].forEach(function (x) { LBL[x[0]] = x[1]; }); });
  var GRADE = ['None', 'Possible', 'Plausible', 'Probable', 'Qualified'];

  /* ---------- the callouts (Richard, 10-Nov 13:00: "a visual coloured callout for any stock that is potentially triggering a
     "capital deployment" or "exit" being plausible (even if the page selected is not for one of those two drop downs)").
     Capital deployment: one of the Master Dashboard's six capital qualification tests graded Probable or Qualified.
     (Plausible is left out: 651 of 1,358 stocks hold a Plausible or better on one of the six, so a callout there would mark half of every list.)
     Exit (live stocks only): the PMS book's own reading of what the rules do today; a SELL of any kind red, a stop-loss release window
     or a tranche within 5% of its nearer exit line amber. ---------- */
  var CAP = REG[2][1];
  var capCache = {};
  function capOf(t) {
    if (capCache[t] !== undefined) return capCache[t];
    var hits = [];
    CAP.forEach(function (x) { var d = DES[x[0]], r = d && d.now[t]; if (r >= 3) hits.push({ r: r, lab: x[1] }); });
    hits.sort(function (a, b) { return b.r - a.r; });
    return (capCache[t] = hits.length ? hits : null);
  }
  function exitOf(t) { var e = S[t] && S[t].exit; return e && e.lvl ? e : null; }
  function mark(t) { var e = exitOf(t), c = capOf(t); return e ? e.lvl : c ? 'cap' : ''; }
  function calloutHTML(t) {
    var h = '', c = capOf(t), e = exitOf(t);
    if (e) h += '<span class="co ' + e.lvl + '" title="' + esc(e.full + (e.near ? '. Nearest exit line: ' + e.near[0].toFixed(1) + '% below the price (' + e.near[1] + ')' : '')) + '">' + (e.lvl === 'sell' ? 'Exit: ' : 'Exit watch: ') + esc(e.short) + '</span>';
    if (c) h += '<span class="co cap g' + c[0].r + '" title="' + esc(c.map(function (x) { return x.lab + ': ' + GRADE[x.r]; }).join('; ') + ' (the Master Dashboard\'s capital qualification tests)') + '">Capital deployment: ' + esc(c[0].lab) + ', ' + GRADE[c[0].r] + (c.length > 1 ? ' +' + (c.length - 1) : '') + '</span>';
    return h;
  }

  /* ---------- the dropdowns ---------- */
  var ORDER = ['live', 'watch', 'interest', 'range', 'exit', 'events', 'ig'];
  function selectHTML(g) {
    return '<select class="f" data-g="' + g.id + '" title="' + esc(g.label) + '"><option value="">' + esc(g.label) + '</option>' +
      g.options.map(function (o) { return '<option value="' + o.id + '">' + esc(o.label) + ' (' + o.tickers.length + ')</option>'; }).join('') + '</select>';
  }
  function desHTML() {
    var h = '<select class="f" id="f-des" title="Master Dashboard designation"><option value="">Master Dashboard designation</option>';
    REG.forEach(function (g) { h += '<optgroup label="' + esc(g[0]) + '">' + g[1].filter(function (x) { return DES[x[0]]; }).map(function (x) { return '<option value="' + x[0] + '">' + esc(x[1]) + '</option>'; }).join('') + '</optgroup>'; });
    return h + '</select><select class="f g" id="f-grade" title="Grade"><option value="3">Probable</option><option value="2">Plausible</option><option value="1">Possible</option><option value="4">Qualified</option><option value="2+">Plausible or better</option><option value="1+">Possible or better</option></select>' +
      '<label class="nw" title="Only stocks whose grade rose into this grade in the last 5 trading days (since ' + dmy(META.ago5) + ')"><input type="checkbox" id="f-new"> risen in last 5 days</label>';
  }
  function grpHTML() {
    return '<select class="f" id="f-gk" title="Groupings"><option value="">Groupings</option>' + Object.keys(GK).map(function (k) { return '<option value="' + k + '">' + k + ' (' + GK[k].length + ')</option>'; }).join('') + '</select>' +
      '<select class="f" id="f-gv" title="Choose one" disabled><option value="">choose one</option></select>';
  }
  function fillGroupValues() {
    var k = $('f-gk').value, sel = $('f-gv');
    if (!k) { sel.innerHTML = '<option value="">choose one</option>'; sel.disabled = true; return; }
    sel.disabled = false;
    var items = GK[k];
    if (k === 'Cohort') {   /* 486 Cohorts: listed under their Sector so the list can be scanned */
      var by = {}; items.forEach(function (o) { var p = o.label.split('|'); (by[p[0]] = by[p[0]] || []).push(o); });
      sel.innerHTML = '<option value="">choose a Cohort</option>' + Object.keys(by).sort().map(function (sec) { return '<optgroup label="' + esc(sec) + '">' + by[sec].map(function (o) { return '<option value="' + esc(o.id) + '">' + esc(o.label.split('|')[1]) + ' (' + o.tickers.length + ')</option>'; }).join('') + '</optgroup>'; }).join('');
    } else sel.innerHTML = '<option value="">choose ' + (k === 'Industry' ? 'an' : 'a') + ' ' + k + '</option>' + items.map(function (o) { return '<option value="' + esc(o.id) + '">' + esc(o.label) + ' (' + o.tickers.length + ')</option>'; }).join('');
  }

  /* ---------- the population: every choice made narrows it ---------- */
  function population() {
    var sets = [], notes = [];
    document.querySelectorAll('select.f[data-g]').forEach(function (s) {
      if (!s.value) return; var o = DD[s.dataset.g].options.filter(function (x) { return x.id === s.value; })[0]; if (!o) return;
      sets.push(o.tickers); notes.push('<b>' + esc(DD[s.dataset.g].label) + ':</b> ' + esc(o.label) + (o.note ? ' <span class="mut">(' + esc(o.note) + ')</span>' : ''));
    });
    var di = $('f-des').value;
    if (di && DES[di]) {
      var d = DES[di], g = $('f-grade').value, lo = parseInt(g, 10), plus = /\+$/.test(g), nw = $('f-new').checked;
      var ok = function (r) { return r != null && (plus ? r >= lo : r === lo); };   /* a stock absent from 'now' holds no grade (None) */
      sets.push(Object.keys(d.now).filter(function (t) { return ok(d.now[t]) && (!nw || !ok(d.ago5[t] || 0)); }));
      notes.push('<b>' + esc(LBL[di]) + ':</b> ' + esc($('f-grade').selectedOptions[0].textContent) + (nw ? ', risen into it since ' + dmy(META.ago5) : ''));
    }
    var gv = $('f-gv').value;
    if (gv) { var gk = $('f-gk').value, go = GK[gk].filter(function (x) { return x.id === gv; })[0]; if (go) { sets.push(go.tickers); notes.push('<b>' + gk + ':</b> ' + esc(go.label.replace('|', ': '))); } }
    var pop = null;
    sets.forEach(function (ts) { var set = {}; ts.forEach(function (t) { set[t] = 1; }); pop = pop === null ? ts.slice() : pop.filter(function (t) { return set[t]; }); });
    return { list: (pop || []).filter(function (t) { return S[t]; }), notes: notes, any: sets.length > 0 };
  }
  var SORTS = {
    tma: function (a, b) { var x = S[a].dist, y = S[b].dist; return (x == null ? 9 : Math.abs(x)) - (y == null ? 9 : Math.abs(y)); },
    rs: function (a, b) { return (S[b].rs == null ? -1 : S[b].rs) - (S[a].rs == null ? -1 : S[a].rs); },
    sec: function (a, b) { return (S[a].sec + S[a].n).localeCompare(S[b].sec + S[b].n); },
    res: function (a, b) { return (S[a].nr || '9999') < (S[b].nr || '9999') ? -1 : (S[a].nr || '9999') > (S[b].nr || '9999') ? 1 : 0; }
  };

  /* ---------- state ---------- */
  var POP = [], at = 0, LASTSEL = null;
  /* the empty-list button: clear every choice except the one just made (a choice in a new dropdown narrows the last one) */
  function keepLast() {
    var keepIds = LASTSEL.id === 'f-des' || LASTSEL.id === 'f-grade' ? ['f-des', 'f-grade'] : LASTSEL.id === 'f-gv' || LASTSEL.id === 'f-gk' ? ['f-gk', 'f-gv'] : [];
    document.querySelectorAll('select.f').forEach(function (s) { if (s !== LASTSEL && keepIds.indexOf(s.id) < 0 && s.id !== 'f-grade') s.value = ''; });
    if (keepIds[0] !== 'f-des') $('f-new').checked = false;
    if (keepIds[0] !== 'f-gk') fillGroupValues();
    refresh();
  }
  function refresh() {
    var p = population();
    POP = p.list.slice().sort(SORTS[$('f-sort').value] || SORTS.tma);
    at = 0;
    $('notes').innerHTML = p.any ? p.notes.join(' <span class="and">and</span> ') : '<span class="mut">Choose a population from any dropdown; choices in different dropdowns narrow each other.</span>';
    st.sel = {}; document.querySelectorAll('select.f').forEach(function (s) { st.sel[s.id || ('g:' + s.dataset.g)] = s.value; }); st.sel.fnew = $('f-new').checked; st.sort = $('f-sort').value; save();
    document.querySelectorAll('select.f').forEach(function (s) { s.classList.toggle('on', !!s.value && s.id !== 'f-grade'); });
    show();
  }
  function list() {
    $('cnt').textContent = POP.length + (POP.length === 1 ? ' stock' : ' stocks');
    $('lst').innerHTML = POP.map(function (t, i) {
      var s = S[t], d = s.dist, dc = d == null ? '' : (d >= -0.01 && d <= 0.03) ? 'nr' : d < 0 ? 'neg' : '', mk = mark(t);
      return '<div class="it' + (i === at || i === at + 1 ? ' cur' : '') + '" data-i="' + i + '" title="' + esc(s.n + ' (' + t + '), ' + s.sec) + '"><span class="no">' + (i + 1) + '</span><span class="mk ' + mk + '"></span><span class="nm">' + esc(s.n) + (s.held ? ' <span class="hd">held</span>' : '') + '</span><span class="dv ' + dc + '">' + (d == null ? '' : (d >= 0 ? '+' : '') + (d * 100).toFixed(1) + '%') + '</span></div>';
    }).join('') || (LASTSEL && document.querySelectorAll('select.f.on').length > 1
      ? '<div class="empty">No stock meets every choice. Choices in different dropdowns narrow each other.<br><button class="nb" id="keep1">Keep only the last choice</button></div>'
      : '<div class="empty">' + (document.querySelectorAll('select.f.on').length ? 'No stock in this list this week.' : 'Choose a population from any dropdown above.') + '</div>');
    var k1 = $('keep1'); if (k1) k1.onclick = keepLast;
    var c = $('lst').querySelector('.it.cur'); if (c) c.scrollIntoView({ block: 'nearest' });
  }
  function pager() {
    var n = POP.length;
    $('pg').textContent = n ? (at + 1) + (at + 1 < n ? '-' + (at + 2) : '') + ' of ' + n : '';
    $('prev').disabled = at <= 0; $('next').disabled = at + 2 >= n;
  }

  /* ---------- each stock's data: its Per-stock Dashboard file and its chart file ---------- */
  var MODELS = {}, LOADING = {};
  function loadStock(t) {
    if (MODELS[t]) return Promise.resolve(MODELS[t]);
    if (LOADING[t]) return LOADING[t];
    var inline = window.MC_PMS && window.MC_PMS[t];
    var url = (S[t] && S[t].held ? HELD_URL : UNI_URL) + fileOf(t) + '?v=' + encodeURIComponent((META.built || '').slice(0, 10));
    var pData = inline ? Promise.resolve(JSON.parse(JSON.stringify(inline))) : fetch(url).then(function (r) { if (!r.ok) throw new Error('the Per-stock Dashboard file answered ' + r.status); return r.json(); });
    var pChart = new Promise(function (res) { loadChartData(t, function (rows) { res(rows); }); });
    LOADING[t] = Promise.all([pData, pChart]).then(function (x) {
      if (!x[1] || !x[1].length) throw new Error('no chart file');
      MODELS[t] = DASH.model(x[0]); delete LOADING[t]; return MODELS[t];
    }).catch(function (e) { delete LOADING[t]; throw e; });
    return LOADING[t];
  }

  /* ---------- the two rows ---------- */
  function strip(t) {
    var s = S[t], d = s.dist;
    var stg = s.s.map(function (r, i) { return r && r !== 'None' ? '<span class="sg s' + (i + 1) + '">Stage ' + (i + 1) + ' ' + r + '</span>' : ''; }).join('');
    return '<span class="nm">' + esc(s.n) + '</span><span class="tk">' + esc(t) + '</span>' + calloutHTML(t) +
      '<span class="more">' +
      (s.held ? '<span class="pill held" title="' + esc((s.exit && s.exit.kind) || 'Held') + '">Held</span>' : '<span class="pill">Not held</span>') +
      (s.int ? '<span class="pill int">Interest ' + s.int + '</span>' : '') + stg +
      '<span class="kv">RS: stock <b>' + (s.rs == null ? 'n/a' : s.rs) + '</b>, sector ' + (s.srs == null ? 'n/a' : s.srs) + ', industry ' + (s.irs == null ? 'n/a' : s.irs) + '</span>' +
      '<span class="kv">' + s.tma + ' target' + (s.tma_assumed ? ' <i>(50D assumed)</i>' : '') + ': <b class="' + (d == null ? '' : d >= -0.01 && d <= 0.03 ? 'nr' : d < 0 ? 'neg' : '') + '">' + (d == null ? 'n/a' : (d >= 0 ? '+' : '') + (d * 100).toFixed(1) + '%') + '</b></span>' +
      (s.nr ? (s.nr <= META.asof ? '<span class="kv">Reported <b>' + dmy(s.nr) + '</b></span>' : '<span class="kv">Results <b>' + dmy(s.nr) + '</b> <span class="mut">' + esc((s.nrs || '').toLowerCase()) + '</span></span>') : '') +
      '<span class="mut secn">' + esc(s.sec) + '</span></span>';
  }
  var drawSeq = 0;
  function drawRow(k, t, m) {
    var row = $('row' + k), pc = row.querySelector('.cp'), vc = row.querySelector('.vp .q4');
    pc.innerHTML = '<div id="cc' + k + '" class="cc"><canvas id="cv' + k + '" style="width:100%;display:block"></canvas></div>';
    var hh = pc.getBoundingClientRect().height;
    /* at 1W and 1M most moving averages sit off the price scale; their end labels stack outward from the plot's edge, so the plot
       gives them room there rather than letting the canvas cut them off */
    var sh = chartZoom === '1W' || chartZoom === '1M';
    /* a held stock's tranche dates: with 40px or more above the plot the renderer writes them there, clear of the price scale */
    var ov = DASH.overlayFor(m, true), top = sh || (ov && ov.marks && ov.marks.length) ? 46 : 22;
    /* a right margin of 212px puts the renderer in its wide mode: the exit lines' and the 52-week-high line's names are written in
       their own column beside the price scale, never over the lines in the plot (Richard, 28-Oct-2026, PMS-DASH 15) */
    drawMasterChart(t, { canvasId: 'cv' + k, containerId: 'cc' + k, height: Math.max(160, Math.floor(hh)), upto: m.asof, overlay: ov, pad: { t: top, r: 212, b: sh ? 50 : 28, l: 6 }, priceTicks: 10 });
    MCVOL.draw(vc, m, volWin());
  }
  function show() {
    var seq = ++drawSeq;
    pager(); list();
    [0, 1].forEach(function (k) {
      var row = $('row' + k), t = POP[at + k];
      row.className = 'row';
      if (!t) { row.style.visibility = 'hidden'; return; }
      row.style.visibility = 'visible';
      row.classList.add('mk-' + (mark(t) || 'none'));
      row.querySelector('.strip').innerHTML = strip(t);
      /* the strip never cuts a word: what does not fit is left out, from the end (the Sector first) */
      var more = row.querySelector('.strip .more'), kids = more ? Array.prototype.slice.call(more.children) : [];
      for (var q = kids.length - 1; q >= 0 && more.scrollWidth > more.clientWidth + 1; q--) kids[q].style.display = 'none';
      var pc = row.querySelector('.cp'), vc = row.querySelector('.vp .q4');
      if (MODELS[t]) { drawRow(k, t, MODELS[t]); return; }
      pc.innerHTML = '<div class="nod">Loading ' + esc(S[t].n) + '&hellip;</div>'; vc.innerHTML = '';
      loadStock(t).then(function (m) { if (seq === drawSeq) drawRow(k, t, m); })
        .catch(function (e) { if (seq !== drawSeq) return; pc.innerHTML = '<div class="nod">No chart for ' + esc(S[t].n) + ' (' + esc(t) + '): ' + esc(e.message) + '.</div>'; vc.innerHTML = ''; });
    });
    /* the next pair is fetched ahead, so the Down arrow shows it at once */
    [2, 3].forEach(function (k) { var t = POP[at + k]; if (t && !MODELS[t]) loadStock(t).catch(function () { /* shown when reached */ }); });
  }
  function go(n) { var mx = Math.max(0, POP.length - 2); var to = Math.max(0, Math.min(mx, n)); if (to === at && $('row0').style.visibility === 'visible') return; at = to; show(); }

  /* ---------- the chart settings line: one set for both rows, kept for next time ---------- */
  function btns(host, list, cur, pick, dis) { host.innerHTML = list.map(function (k) { return '<button class="' + (k[0] === cur ? 'on' : '') + '" data-k="' + k[0] + '"' + (dis ? ' disabled' : '') + '>' + k[1] + '</button>'; }).join(''); host.onclick = function (e) { var b = e.target.closest('button'); if (b && !b.disabled) pick(b.dataset.k); }; }
  var MAS = [['ma5', '5D', '#8b0000'], ['ma10', '10D', '#e88a9a'], ['ma20', '20D', '#e74c3c'], ['ma50', '50D', '#ff8c00'], ['ma100', '100D', '#2ca02c'], ['ma150', '150D', '#1a5276'], ['ma200', '200D', '#4a3d9e']];
  function redraw() { [0, 1].forEach(function (k) { var t = POP[at + k]; if (t && MODELS[t]) drawRow(k, t, MODELS[t]); }); }
  function controls() {
    btns($('zoom'), ['1W', '1M', '3M', '6M', '12M', '2Y', '3Y', '5Y'].map(function (k) { return [k, k]; }), chartZoom, function (k) { chartZoom = k; save(); controls(); redraw(); });
    btns($('scale'), [['lin', 'LIN'], ['log', 'LOG']], chartScaleMode, function (k) { chartScaleMode = k; save(); controls(); redraw(); });
    $('mas').innerHTML = MAS.map(function (a) { var on = chartVis[a[0]]; return '<button class="ma' + (on ? ' on' : '') + '" data-k="' + a[0] + '" style="color:' + a[2] + ';border-color:' + (on ? a[2] : 'transparent') + '">' + a[1] + '</button>'; }).join('');
    $('mas').onclick = function (e) { var b = e.target.closest('button'); if (!b) return; chartVis[b.dataset.k] = !chartVis[b.dataset.k]; save(); controls(); redraw(); };
    var f = FOLLOW[chartZoom];
    btns($('volw'), (f === 'L1W' ? [['L1W', 'L1W']] : []).concat([['L1M', 'L1M'], ['L3M', 'L3M']]), volWin(), function (k) { st.vol = k; save(); controls(); redraw(); }, !!f);
    $('volw').title = f ? 'Set by the price chart: at 1W, 1M and 3M the volume charts show the same window' : 'The volume window for price zooms of 6M and longer';
  }

  /* ---------- start ---------- */
  function start(pop) {
    P = pop; S = P.stocks; META = P.meta; GK = null;
    P.dropdowns.forEach(function (g) { DD[g.id] = g; if (g.kinds) GK = g.kinds; });
    P.designations.forEach(function (d) { DES[d.id] = d; });
    $('dds').innerHTML = ORDER.filter(function (id) { return DD[id]; }).map(function (id) { return selectHTML(DD[id]); }).join('') + desHTML() + grpHTML();
    $('asof').textContent = 'readings at the ' + dmy(META.asof) + ' close';
    $('asof').title = 'Populations built ' + META.built.replace('T', ' ').slice(0, 16) + ' from the Master Dashboard (' + META.universe + ' stocks), the Per-stock Dashboard files and the weekly lists. The % beside each name is the price against its target moving average (the 50-day where none is set in Notion).';
    document.querySelectorAll('select.f').forEach(function (s) { s.addEventListener('change', function () { LASTSEL = s; if (s.id === 'f-gk') fillGroupValues(); refresh(); }); });
    $('f-new').addEventListener('change', refresh);
    $('f-sort').addEventListener('change', refresh);
    $('clear').onclick = function () { document.querySelectorAll('select.f').forEach(function (s) { if (s.id !== 'f-grade') s.value = ''; }); $('f-new').checked = false; fillGroupValues(); refresh(); };
    $('prev').onclick = function () { go(at - 2); }; $('next').onclick = function () { go(at + 2); };
    $('lst').onclick = function (e) { var it = e.target.closest('.it'); if (it) go(parseInt(it.dataset.i, 10)); };
    document.addEventListener('keydown', function (e) {
      if (/^(SELECT|INPUT)$/.test((document.activeElement || {}).tagName || '')) return;
      if (e.key === 'ArrowDown' || e.key === 'PageDown' || e.key === 'ArrowRight') { go(at + 2); e.preventDefault(); }
      if (e.key === 'ArrowUp' || e.key === 'PageUp' || e.key === 'ArrowLeft') { go(at - 2); e.preventDefault(); }
    });
    /* a kept choice wins; otherwise it opens on the Ideas Bench, closest to its target moving average first */
    var kept = st.sel && Object.keys(st.sel).some(function (k) { return k !== 'fnew' && k !== 'f-grade' && st.sel[k]; });
    if (kept) {
      document.querySelectorAll('select.f').forEach(function (s) { var k = s.id || ('g:' + s.dataset.g); if (st.sel[k] == null) return; if (s.id === 'f-gv') fillGroupValues(); s.value = st.sel[k]; if (s.value !== st.sel[k]) s.value = ''; });
      $('f-new').checked = !!st.sel.fnew;
    } else { var w = document.querySelector('select.f[data-g="watch"]'); if (w) w.value = 'w_bench'; }
    $('f-sort').value = SORTS[st.sort] ? st.sort : 'tma';
    controls(); refresh();
    var tm; window.addEventListener('resize', function () { clearTimeout(tm); tm = setTimeout(redraw, 200); });
    window.MC = { go: go, pop: function () { return POP; }, at: function () { return at; }, mark: mark };
  }
  fetch(BASE + 'ratings/pms/data/mechanical-volume-days.json').then(function (r) { return r.ok ? r.json() : null; }).then(function (j) { if (j && window.MCVOL && MCVOL.setMech) MCVOL.setMech(j); }).catch(function () { /* optional: only the hover note */ });
  (window.MC_POP ? Promise.resolve(window.MC_POP) : fetch('populations.json', { cache: 'no-cache' }).then(function (r) { if (!r.ok) throw new Error('populations.json answered ' + r.status); return r.json(); }))
    .then(start)
    .catch(function (e) { $('notes').innerHTML = '<span class="err">The populations could not be loaded (' + esc(e.message) + '). They are rebuilt with the Master Dashboard each evening.</span>'; });
})();
