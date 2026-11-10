/* compare-vol.js: GENERATED nightly by master-dashboard/scripts/build_multichart.py; do not edit.
   The six-panel view's panel 2 (Volume) from pms-data/dashboard/site/onescreen.js, function drawVol, word for word,
   given a host element and a model so two stocks can be drawn on one screen (the Multi-stock Dashboard). */
(function () {
  'use strict';
  var C = DASH.C, NS = 'http://www.w3.org/2000/svg', MON = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  function el(tag, a, p) { var e = document.createElementNS(NS, tag); for (var k in a) e.setAttribute(k, a[k]); if (p) p.appendChild(e); return e; }
  function txt(p, x, y, s, a) { a = a || {}; var halo = a.halo; delete a.halo; var b = { x: x, y: y, 'font-size': 10, fill: C.ink2, 'font-family': 'Segoe UI, system-ui, sans-serif' }; for (var k in a) b[k] = a[k]; var t = el('text', b, p); if (halo) { t.setAttribute('stroke', '#fff'); t.setAttribute('stroke-width', 3); t.setAttribute('paint-order', 'stroke'); t.setAttribute('stroke-linejoin', 'round'); } t.textContent = s; return t; }
  function D(s) { return new Date(s + 'T00:00:00Z'); }
  function addDays(s, n) { var d = D(s); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); }
  function fmtD(s) { var d = D(s); return d.getUTCDate() + '-' + MON[d.getUTCMonth()]; }
  function fmtDY(s) { return fmtD(s) + '-' + D(s).getUTCFullYear(); }
  function br(v, s) { return v < 0 ? '(' + s + ')' : s; }
  function pctS(v) { if (v == null) return 'n/a'; var r = Math.round(v * 100); return r > 0 ? '+' + r + '%' : r < 0 ? '(' + (-r) + '%)' : '0%'; }
  function pctS1(c) { if (c == null) return 'n/a'; var v = Math.round(c * 1000) / 10; return v > 0 ? '+' + v.toFixed(1) + '%' : v < 0 ? '(' + Math.abs(v).toFixed(1) + '%)' : '0.0%'; }
  function fmtN(v) { if (v == null) return 'n/a'; var a = Math.abs(v), s = a >= 1000 ? Math.round(a).toLocaleString('en-GB') : a >= 100 ? a.toFixed(0) : a >= 10 ? a.toFixed(1) : a.toFixed(2); return br(v, s); }
  function fmtVol(v) { if (v == null) return 'n/a'; var a = Math.abs(v); return a >= 1e6 ? (v / 1e6).toFixed(1) + 'M' : a >= 1e3 ? Math.round(v / 1e3) + 'K' : String(Math.round(v)); }
  var niceTicks = DASH.niceTicks;
  function weekday(s) { var g = D(s).getUTCDay(); return g > 0 && g < 6; }
  function sizeOf(e) { var r = e.getBoundingClientRect(); return { w: Math.floor(r.width), h: Math.floor(r.height) }; }
  function buttons(host, list, cur, onPick, label) {
    host.innerHTML = (label ? '<span class="lb">' + label + '</span>' : '') + list.map(function (k) { return '<button class="' + (k[0] === cur ? 'on' : '') + '" data-k="' + k[0] + '">' + k[1] + '</button>'; }).join('');
    host.onclick = function (e) { var b = e.target.closest('button'); if (b) onPick(b.dataset.k); };
  }
  var TRC = { up: '#1a7f37', dn: '#cf222e', flat: '#6e7781' }, TRBG = { up: 'rgba(26,127,55,0.07)', dn: 'rgba(207,34,46,0.07)', flat: null };
  var FYDASH = ['', '7 4', '2 3'], FYW = [2.4, 2.0, 2.0];
  function trKind(c, band) { return c == null ? 'flat' : c <= -band ? 'dn' : c >= band ? 'up' : 'flat'; }
  var MECHD = {}, WIN = { L1W: 7, L1M: 30, L3M: 91, L6M: 182 };
  function subCell(host) { var c = document.createElement('div'); c.className = 'sub'; c.innerHTML = '<div class="sb"></div>'; host.appendChild(c); return c.querySelector('.sb'); }
  function cardH(sb, html, left, wide) { var d = ov(sb, html, left, null, null, wide); return d.offsetHeight + 6; }
  function ov(sb, html, left, place, pad, wide) { var d = document.createElement('div'); d.className = 'ov6'; d.innerHTML = html; d.style.left = (wide ? 2 : left + 2) + 'px'; if (wide) { d.style.right = '2px'; d.style.maxWidth = 'none'; } if (place === 'bottom') d.style.bottom = ((pad == null ? 28 : pad) + 2) + 'px'; else d.style.top = '2px'; sb.appendChild(d); return d; }
  function drawVolInto(host, m, win) {
    host.innerHTML = '';
    var V = m.H.volume, from = addDays(m.asof, -WIN[win]), rows = V.filter(function (q) { return q.d > from && q.d <= m.asof; }), n = rows.length;
    var DL = {}; m.daily.forEach(function (q) { DL[q.d] = q; });
    var q0 = rows[n - 1] || {};
    var hA = subCell(host), hB = subCell(host), hC = subCell(host), hD = subCell(host);
    var GREEN = '#1a7f37';
    function frame(hh, padR) { var sz = sizeOf(hh), W = sz.w, H = sz.h, pad = { l: 34, r: padR }, bw = (W - pad.l - pad.r) / n; var svg = el('svg', { width: W, height: H, viewBox: '0 0 ' + W + ' ' + H, style: 'display:block;font-family:Segoe UI,system-ui,sans-serif' }, hh);
      var ds = rows.map(function (q) { return D(q.d); }), mon = function (i) { if (!i) return true; return ds[i].getUTCDay() < ds[i - 1].getUTCDay() || (ds[i] - ds[i - 1]) / 864e5 >= 7; }, mst = function (i) { return i > 0 && ds[i].getUTCMonth() !== ds[i - 1].getUTCMonth(); };
      var F = { W: W, H: H, pad: pad, bw: bw, n: n, svg: svg, top: 6, ph: H - 6 - 26, xi: function (i) { return pad.l + i * bw + bw / 2; }, edge: function (i) { return pad.l + i * bw; }, ds: ds, mon: mon, mst: mst };
      /* alternate weeks shaded, a line each Monday, firmer at a month, quarter and year: the live panes' time furniture */
      var wk = 0, ws = 0; for (var i = 0; i <= n; i++) { if (i === n || (i > 0 && mon(i))) { if (wk % 2 === 1) el('rect', { x: F.edge(ws), y: F.top, width: F.edge(i) - F.edge(ws), height: F.ph, fill: 'rgba(31,35,40,0.035)' }, svg); wk++; ws = i; } }
      for (var j = 1; j < n; j++) { if (!mon(j) && !mst(j)) continue; var ms = mst(j), mo = ds[j].getUTCMonth(); el('line', { x1: F.edge(j), x2: F.edge(j), y1: F.top, y2: F.top + F.ph, stroke: ms && mo === 0 ? 'rgba(31,35,40,0.55)' : ms && mo % 3 === 0 ? 'rgba(31,35,40,0.36)' : ms ? 'rgba(31,35,40,0.22)' : 'rgba(31,35,40,0.08)', 'stroke-width': ms && mo % 3 === 0 ? 1.4 : 1 }, svg); }
      m.tranches.forEach(function (tr) { var k = -1; for (var i2 = 0; i2 < n; i2++) if (rows[i2].d >= tr.entry_date) { k = i2; break; } if (k < 0 || rows[0].d > tr.entry_date) return; el('line', { x1: F.xi(k), x2: F.xi(k), y1: F.top, y2: F.top + F.ph, stroke: C.entry, 'stroke-dasharray': '3 3', 'stroke-width': 1 }, svg); });
      return F; }
    function dates(F) { var y = F.top + F.ph + 11, every = F.bw >= 13, c = 0, lastX = -99;
      for (var i = 0; i < F.n; i++) { var isMon = F.mon(i), d = F.ds[i].getUTCDate(); if (every) { txt(F.svg, F.xi(i), y, String(d), { 'text-anchor': 'middle', 'font-size': 9, fill: isMon ? C.ink : C.ink3, 'font-weight': isMon ? 700 : 400 }); continue; } if (isMon && (c++ % (F.bw * 5 >= 22 ? 1 : 2) === 0) && F.xi(i) - lastX >= 16) { lastX = F.xi(i); txt(F.svg, F.xi(i), y, String(d), { 'text-anchor': 'middle', 'font-size': 9, fill: C.ink2 }); } }
      var ms = 0; for (var q = 1; q <= F.n; q++) { if (q < F.n && !F.mst(q)) continue; var x0 = F.edge(ms), x1 = F.edge(q), mo = F.ds[ms].getUTCMonth(), nm = x1 - x0 > 44 ? MON[mo] + ' ' + String(F.ds[ms].getUTCFullYear()).slice(2) : x1 - x0 > 20 ? MON[mo] : ''; if (nm) txt(F.svg, (x0 + x1) / 2, y + 11, nm, { 'text-anchor': 'middle', 'font-size': 9.5, fill: C.ink, 'font-weight': mo % 3 === 0 ? 700 : 500 }); ms = q; }
      el('line', { x1: F.pad.l, x2: F.W - F.pad.r, y1: F.top + F.ph, y2: F.top + F.ph, stroke: C.border }, F.svg); }
    function hover(hh, F, html) { var cross = el('line', { x1: 0, x2: 0, y1: F.top, y2: F.top + F.ph, stroke: C.ink3, 'stroke-dasharray': '2 2', opacity: 0 }, F.svg); var tip = document.createElement('div'); tip.className = 'tip'; tip.style.display = 'none'; hh.appendChild(tip);
      F.svg.addEventListener('mousemove', function (ev) { var r = F.svg.getBoundingClientRect(), px = ev.clientX - r.left, i = Math.floor((px - F.pad.l) / F.bw); if (i < 0 || i >= F.n) { tip.style.display = 'none'; cross.setAttribute('opacity', 0); return; } cross.setAttribute('x1', F.xi(i)); cross.setAttribute('x2', F.xi(i)); cross.setAttribute('opacity', 1); tip.innerHTML = '<b>' + fmtDY(rows[i].d) + '</b>' + html(i); tip.style.display = 'block'; tip.style.left = Math.max(0, Math.min(px + 12, F.W - 250)) + 'px'; tip.style.top = Math.min(ev.clientY - r.top + 10, F.H - 50) + 'px'; });
      F.svg.addEventListener('mouseleave', function () { tip.style.display = 'none'; cross.setAttribute('opacity', 0); }); }
    function endLab(F, list) { list.sort(function (a, b) { return a.y - b.y; }); for (var i = 1; i < list.length; i++) if (list[i].y - list[i - 1].y < 11) list[i].y = list[i - 1].y + 11; list.forEach(function (e) { txt(F.svg, F.W - F.pad.r + 4, e.y, e.t, { fill: e.c, 'font-size': 9.5, 'font-weight': 650 }); }); }
    /* pane A: daily volume */
    var cA = cardH(hA, '<b>Daily volume</b> &#9660; distribution, &#9650; accumulation day', 34);
    var F = frame(hA, 30); el('defs', {}, F.svg).innerHTML = '<pattern id="vhatch" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="4" stroke="#57606a" stroke-width="1.5" opacity="0.75"/></pattern>'; var vmax = Math.max.apply(null, rows.map(function (q) { return q.v; }).concat([1])), v50m = Math.max.apply(null, rows.map(function (q) { return q.v50 || 0; }).concat([1]));
    var capRaw = Math.min(vmax, 3 * v50m) * 1.05, NT = niceTicks(0, capRaw, 3), cap = NT[NT.length - 1] >= capRaw ? NT[NT.length - 1] : capRaw, yA = function (v) { return F.top + F.ph - Math.min(v, cap) / cap * (F.ph - cA); };
    NT.forEach(function (v) { if (v > cap) return; el('line', { x1: F.pad.l, x2: F.W - F.pad.r, y1: yA(v), y2: yA(v), stroke: C.grid }, F.svg); txt(F.svg, F.pad.l - 4, yA(v) + 3.5, v ? fmtVol(v) : '0', { 'text-anchor': 'end', 'font-size': 9.5, fill: C.ink3 }); });
    if (q0.v50) [0.5, 1, 1.25, 2, 3].forEach(function (k) { var v = k * q0.v50; if (v > cap) return; txt(F.svg, F.W - F.pad.r + 3, yA(v) + 3.5, k + 'x', { 'font-size': 9, fill: k === 1.25 ? C.red : C.ink3, 'font-weight': k === 1.25 ? 700 : 400 }); });
    var bwx = Math.max(1, Math.min(F.bw * 0.72, 14));
    rows.forEach(function (q, i) { var hgt = Math.max(1, F.top + F.ph - yA(q.v)), r = q.v50 > 0 ? q.v / q.v50 : null, dist = !q.up && r > 1.25, acc = q.up && r > 1.25, quiet = r != null && r < 0.5, mech = MECHD[q.d];
      var fill = dist ? 'rgba(207,34,46,0.95)' : acc ? 'rgba(26,127,55,0.95)' : quiet ? (q.up ? 'rgba(26,127,55,0.20)' : 'rgba(207,34,46,0.17)') : q.up ? 'rgba(26,127,55,0.50)' : 'rgba(207,34,46,0.40)';
      el('rect', { x: F.xi(i) - bwx / 2, y: F.top + F.ph - hgt, width: bwx, height: hgt, fill: fill }, F.svg);
      if (mech) el('rect', { x: F.xi(i) - bwx / 2, y: F.top + F.ph - hgt, width: bwx, height: hgt, fill: 'url(#vhatch)' }, F.svg);
      if (dist || acc) txt(F.svg, F.xi(i), Math.max(F.top + 8, F.top + F.ph - hgt - 2), dist ? '▼' : '▲', { 'text-anchor': 'middle', 'font-size': F.bw >= 6 ? 9 : 7.5, fill: dist ? C.red : GREEN }); });
    var dp = ''; rows.forEach(function (q, i) { if (q.v50) dp += (dp ? 'L' : 'M') + F.xi(i).toFixed(1) + ',' + yA(q.v50 * 1.25).toFixed(1); }); if (dp) el('path', { d: dp, fill: 'none', stroke: C.red, 'stroke-width': 1.1, 'stroke-dasharray': '2 3', opacity: 0.75 }, F.svg);
    dates(F); hover(hA, F, function (i) { var q = rows[i], rr = q.v50 > 0 ? q.v / q.v50 : null; return '<div>volume ' + fmtVol(q.v) + (rr != null ? ', ' + rr.toFixed(2) + ' times the 50D average' : '') + ' (' + (q.up ? 'an up day' : 'a down day') + ')</div>' + (MECHD[q.d] ? '<div>an index review or option expiry day</div>' : ''); });
    /* pane B: average volume per day, up days against down days (the house convention: the last N rows, every day included) */
    var VV = V.filter(function (q) { return q && q.v != null; }), UD = {};
    for (var k = 0; k < VV.length; k++) { if (VV[k].d <= from) continue; var o = {}; [20, 50].forEach(function (N) { var su = 0, nu = 0, sd = 0, nd = 0; for (var j = Math.max(1, k - N + 2); j <= k; j++) { if (VV[j].up) { su += VV[j].v; nu++; } else { sd += VV[j].v; nd++; } } o['u' + N] = nu ? su / nu : null; o['d' + N] = nd ? sd / nd : null; }); UD[VV[k].d] = o; }
    var ser = function (key) { return rows.map(function (q) { return UD[q.d] ? UD[q.d][key] : null; }); }, u20 = ser('u20'), d20 = ser('d20'), u50 = ser('u50'), d50 = ser('d50');
    var cB = cardH(hB, '<b>Average volume, up against down days</b>; solid 20, dashed 50 sessions', 34);
    F = frame(hB, 40); var bv = u20.concat(d20, u50, d50).filter(function (v) { return v != null; }), bLo = Math.min.apply(null, bv), bHi = Math.max.apply(null, bv), bp = (bHi - bLo) * 0.1 || bHi * 0.05; bLo = Math.max(0, bLo - bp); bHi += bp;
    var yB = function (v) { return F.top + F.ph - (v - bLo) / (bHi - bLo) * (F.ph - cB); };
    niceTicks(bLo, bHi, 3).forEach(function (v) { if (v < bLo) return; el('line', { x1: F.pad.l, x2: F.W - F.pad.r, y1: yB(v), y2: yB(v), stroke: C.grid }, F.svg); txt(F.svg, F.pad.l - 4, yB(v) + 3.5, fmtVol(v), { 'text-anchor': 'end', 'font-size': 9.5, fill: C.ink3 }); });
    for (var i2 = 0; i2 < n; i2++) { if (u20[i2] == null || d20[i2] == null) continue; el('rect', { x: F.edge(i2), y: Math.min(yB(u20[i2]), yB(d20[i2])), width: F.bw + 0.4, height: Math.max(0.5, Math.abs(yB(u20[i2]) - yB(d20[i2]))), fill: u20[i2] >= d20[i2] ? 'rgba(26,127,55,0.16)' : 'rgba(207,34,46,0.16)' }, F.svg); }
    var path = function (vals, col, w, dash) { var d = ''; vals.forEach(function (v, i) { if (v == null) return; d += (d ? 'L' : 'M') + F.xi(i).toFixed(1) + ',' + yB(v).toFixed(1); }); if (d) el('path', { d: d, fill: 'none', stroke: col, 'stroke-width': w, 'stroke-dasharray': dash || '', 'stroke-linejoin': 'round' }, F.svg); };
    path(u50, GREEN, 1.4, '6 3'); path(d50, C.red, 1.4, '6 3'); path(u20, GREEN, 2); path(d20, C.red, 2);
    endLab(F, [[u20, GREEN], [d20, C.red]].map(function (a) { return { y: yB(a[0][n - 1]) + 3.5, t: fmtVol(a[0][n - 1]), c: a[1] }; }));
    dates(F); hover(hB, F, function (i) { return '<div>last 20 sessions: up days ' + fmtVol(u20[i]) + ', down days ' + fmtVol(d20[i]) + '</div><div>last 50 sessions: up days ' + fmtVol(u50[i]) + ', down days ' + fmtVol(d50[i]) + '</div>'; });
    /* pane C: distribution days, and below them the up days less the down days over the same last 25 sessions (Richard, 10-Nov-2026: "add in a
       visual communication of the # of up days vs. down days on a trailing 20-25D basis"; 25 so the pane reads as one window, and a distribution day is
       one of the down days). An up day: close at or above the previous close, as the bars are coloured. */
    var cC = cardH(hC, '<b>Distribution days, last 25 sessions</b>; warning at 6', 34);
    F = frame(hC, 30); var sH = Math.max(30, Math.round((F.ph - cC) * 0.34)), baseC = F.top + F.ph - sH - 5;
    var dmax = Math.max(8, Math.max.apply(null, rows.map(function (q) { return q.dist25 || 0; }))), yC = function (v) { return baseC - v / dmax * (baseC - F.top - cC); };
    [0, 3, 6].forEach(function (v) { el('line', { x1: F.pad.l, x2: F.W - F.pad.r, y1: yC(v), y2: yC(v), stroke: v === 6 ? C.red : C.grid, 'stroke-dasharray': v === 6 ? '5 3' : '', opacity: v === 6 ? 0.7 : 1 }, F.svg); txt(F.svg, F.pad.l - 4, yC(v) + 3.5, String(v), { 'text-anchor': 'end', 'font-size': 9.5, fill: v === 6 ? C.red : C.ink3, 'font-weight': v === 6 ? 700 : 400 }); });
    var dd = ''; rows.forEach(function (q, i) { if (q.dist25 == null) return; dd += (dd ? 'L' : 'M') + F.edge(i).toFixed(1) + ',' + yC(q.dist25).toFixed(1) + 'L' + F.edge(i + 1).toFixed(1) + ',' + yC(q.dist25).toFixed(1); });
    if (dd) { el('path', { d: dd + 'L' + (F.W - F.pad.r) + ',' + baseC + 'L' + F.pad.l + ',' + baseC + 'Z', fill: 'rgba(207,34,46,0.10)' }, F.svg); el('path', { d: dd, fill: 'none', stroke: C.red, 'stroke-width': 1.7 }, F.svg); }
    var udN = {}; for (var k2 = 0; k2 < VV.length; k2++) { if (VV[k2].d <= from || k2 < 24) continue; var nu2 = 0; for (var j2 = k2 - 24; j2 <= k2; j2++) if (VV[j2].up) nu2++; udN[VV[k2].d] = { u: nu2, n: 25 - nu2 }; }
    var ud = rows.map(function (q) { return udN[q.d] || null; }), net = ud.map(function (o) { return o ? o.u - o.n : null; }), nv = net.filter(function (v) { return v != null; });
    var sMax = Math.max(5, Math.ceil(Math.max.apply(null, nv.map(Math.abs).concat([0])) / 5) * 5), sMid = F.top + F.ph - sH / 2, yS = function (v) { return sMid - v / sMax * (sH / 2 - 2); };
    el('line', { x1: F.pad.l, x2: F.W - F.pad.r, y1: F.top + F.ph - sH - 2.5, y2: F.top + F.ph - sH - 2.5, stroke: C.border }, F.svg);
    el('line', { x1: F.pad.l, x2: F.W - F.pad.r, y1: sMid, y2: sMid, stroke: C.ink3, 'stroke-width': 0.8 }, F.svg);
    txt(F.svg, F.pad.l - 4, sMid + 3.5, '0', { 'text-anchor': 'end', 'font-size': 9.5, fill: C.ink3 });
    [sMax, -sMax].forEach(function (v) { txt(F.svg, F.pad.l - 4, yS(v) + (v > 0 ? 6 : 1), v > 0 ? '+' + v : '(' + (-v) + ')', { 'text-anchor': 'end', 'font-size': 8.5, fill: v > 0 ? GREEN : C.red }); });
    for (var i3 = 0; i3 < n; i3++) { var v3 = net[i3]; if (v3 == null || v3 === 0) continue; el('rect', { x: F.edge(i3), y: Math.min(sMid, yS(v3)), width: F.bw + 0.4, height: Math.abs(yS(v3) - sMid), fill: v3 > 0 ? 'rgba(26,127,55,0.55)' : 'rgba(207,34,46,0.55)' }, F.svg); }
    var uL = ud[n - 1];
    if (uL) txt(F.svg, F.pad.l + 3, F.top + F.ph - sH + 8, 'up days less down days: ' + uL.u + ' up, ' + uL.n + ' down', { 'font-size': 9, fill: C.ink2, halo: true });
    var ends = [{ y: yC(q0.dist25) + 3.5, t: String(q0.dist25), c: C.red }]; if (net[n - 1] != null) ends.push({ y: Math.max(yS(net[n - 1]), F.top + F.ph - sH + 8) + 3.5, t: net[n - 1] > 0 ? '+' + net[n - 1] : net[n - 1] < 0 ? '(' + (-net[n - 1]) + ')' : '0', c: net[n - 1] > 0 ? GREEN : net[n - 1] < 0 ? C.red : C.ink3 });
    endLab(F, ends);
    dates(F); hover(hC, F, function (i) { return '<div>distribution days in 25 sessions: ' + rows[i].dist25 + '</div>' + (ud[i] ? '<div>in the same 25 sessions: ' + ud[i].u + ' up days, ' + ud[i].n + ' down days</div>' : ''); });
    /* pane D: relative price against its 52W high */
    var dD = ov(hD, '<b>Relative price against its 52W high</b>; sell line (25%)', 34, 'bottom'), cD = dD.offsetHeight + 6;
    F = frame(hD, 36); var rd = rows.map(function (q) { var x_ = DL[q.d]; return x_ && x_.rdh != null ? x_.rdh * 100 : null; }), rdv = rd.filter(function (v) { return v != null; });
    var dLo = Math.min(-35, Math.floor((Math.min.apply(null, rdv.concat([0])) - 3) / 5) * 5), yD = function (v) { return F.top + F.ph - cD - (v - dLo) / (0 - dLo) * (F.ph - cD); };
    for (var t = 0; t >= dLo; t -= 10) { el('line', { x1: F.pad.l, x2: F.W - F.pad.r, y1: yD(t), y2: yD(t), stroke: C.grid }, F.svg); txt(F.svg, F.pad.l - 4, yD(t) + 3.5, t ? '(' + (-t) + '%)' : '0%', { 'text-anchor': 'end', 'font-size': 9.5, fill: C.ink3 }); }
    el('rect', { x: F.pad.l, y: yD(-25), width: F.W - F.pad.l - F.pad.r, height: yD(dLo) - yD(-25), fill: 'rgba(207,34,46,0.06)' }, F.svg);
    el('line', { x1: F.pad.l, x2: F.W - F.pad.r, y1: yD(-25), y2: yD(-25), stroke: C.red, 'stroke-dasharray': '3 2', 'stroke-width': 1.3 }, F.svg);
    txt(F.svg, F.pad.l - 4, yD(-25) + 3.5, '(25%)', { 'text-anchor': 'end', 'font-size': 9.5, fill: C.red, 'font-weight': 700 });
    var dr = ''; rd.forEach(function (v, i) { if (v == null) return; dr += (dr ? 'L' : 'M') + F.xi(i).toFixed(1) + ',' + yD(v).toFixed(1); }); if (dr) el('path', { d: dr, fill: 'none', stroke: C.rel, 'stroke-width': 1.8 }, F.svg);
    var lr = rd[n - 1]; if (lr != null) endLab(F, [{ y: yD(lr) + 3.5, t: '(' + Math.round(-lr) + '%)', c: C.rel }]);
    dates(F); hover(hD, F, function (i) { return rd[i] != null ? '<div>relative price (' + Math.round(-rd[i]) + '%) below its 52W high</div>' : ''; });
  }
  window.MCVOL = { draw: drawVolInto, setMech: function (j) { MECHD = {}; ((j && j.dates) || []).forEach(function (q) { MECHD[q.date] = q.why; }); } };
})();
