// =============================================================================
// SUMMARY TAB MODULE — V1.2 (12-May-26)
// =============================================================================
// SUMMARY-TAB-MARKER — idempotency marker for patcher detection
//
// V1.2 changes vs V1.1:
//   - Qualified Stocks table built to FULL spec: 29 columns
//     * Inputs (4): Ticker, Company, Industry, Sector
//     * TM Stage 1 (2): BP, PB stage pills
//     * TM Stage 2 (3): VCP, MM99, UTR stage pills
//     * TM Stage 3 (1): Topping pill
//     * TM Stage 4 (2): Declining, Collapse pills
//     * TM RS (4): rs_percentile, rs_vs_sector, rs_vs_industry, rs_excess_market
//     * SSEM (5): 1M / 3M / 6M / 12M timeframe scores + Total
//     * Valuation (2): pe_percentile + buildRangeBar sparkline
//     * Master Ratings (6): TM, Them, Fund, ICBB, SSEM, Val
//   - 3-row header: Group / Sub-group / Column name
//   - Conditional colour on all pill, RS, SSEM, Valuation cells
//   - No internal scroll on Qualified Stocks (per Richard Q14)
//
// V1 spec: decisions.md D-MD-UI-38..47
// =============================================================================

/* SUMMARY-TAB-MARKER-START */

var masterRatingsMap = {};
var summaryFilters = {tm:"",thematic:"",fund_chg:"",icbb:"",ssem:"",val:""};
var summarySectorGrouping = false;

var SUM_RATINGS = ["tm","thematic","fund_chg","icbb","ssem","val"];
var SUM_RATING_LABELS = {tm:"Technical Momentum",thematic:"Thematic Fit",fund_chg:"Fundamental Change",icbb:"ICBB",ssem:"SSEM",val:"Valuation"};
var SUM_RATING_SHORT = {tm:"TM",thematic:"Them",fund_chg:"Fund",icbb:"ICBB",ssem:"SSEM",val:"Val"};
var SUM_PLACEHOLDER_TOOLTIP = "Placeholder pending REPOSITORY A&J memo rollout";

// TM stage column order
var SUM_STAGE_COLS = [
  {id:"basing_plateau",  label:"BP",   stage:1},
  {id:"probing_bet",     label:"PB",   stage:1},
  {id:"vcp",             label:"VCP",  stage:2},
  {id:"mm99",            label:"MM99", stage:2},
  {id:"uptrend_retest",  label:"UTR",  stage:2},
  {id:"s3_topping",      label:"Top",  stage:3},
  {id:"s4_declining",    label:"Dec",  stage:4},
  {id:"collapse",        label:"Col",  stage:4}
];
var SUM_RS_COLS = [
  {key:"rs_percentile",     label:"RS%",     format:"pct100"},
  {key:"rs_vs_sector",      label:"vs Sec",  format:"pct100"},
  {key:"rs_vs_industry",    label:"vs Ind",  format:"pct100"},
  {key:"rs_excess_market",  label:"vs Mkt",  format:"signedPct"}
];
var SUM_SSEM_TIMEFRAMES = ["1m","3m","6m","12m"];
var SUM_SSEM_DIMS = ["eps","ebitda","sales","tp","buy"];

// V1 TM rating logic per Richard 12-May-26
function SUM_v1TmRating(tk) {
  var fm = (typeof filterMap !== "undefined") ? filterMap[tk] : null;
  if (!fm) return "-";
  var s = function(k) { return (fm[k] && fm[k].stage) ? fm[k].stage : null; };
  if (s("s4_declining") === "Capital" || s("collapse") === "Capital") return "F";
  if (s("s3_topping") === "Capital") return "D";
  if (s("mm99") === "Capital" || s("vcp") === "Capital" || s("uptrend_retest") === "Capital") return "A";
  if (s("probing_bet") === "Capital") return "B";
  if (s("basing_plateau") === "Capital") return "C";
  if (s("mm99") === "Late" || s("vcp") === "Late" || s("uptrend_retest") === "Late") return "C";
  return "-";
}

// SSEM per-timeframe total: sum signed scores across 5 dimensions for ONE timeframe
// Mirrors the existing ssemDimScore logic but for a single lookback.
function SUM_ssemTimeframeTotal(ss, tf) {
  if (!ss) return null;
  // tf = "1m" | "3m" | "6m" | "12m"
  // ss.eps_rev.L1M / L3M / L6M / L12M structure
  var keyMap = {"1m":"L1M","3m":"L3M","6m":"L6M","12m":"L12M"};
  var lookbackKey = keyMap[tf];
  if (!lookbackKey) return null;
  var total = 0;
  var hasAny = false;
  for (var di = 0; di < SUM_SSEM_DIMS.length; di++) {
    var dim = SUM_SSEM_DIMS[di];
    var revKey = dim + "_rev";
    var data = ss[revKey];
    if (!data) continue;
    var v = data[lookbackKey];
    if (v == null) continue;
    hasAny = true;
    // Sign-based scoring: positive = +1, negative = -1, zero = 0
    if (v > 0.001) total += 1;
    else if (v < -0.001) total -= 1;
  }
  return hasAny ? total : null;
}

function deriveMasterRatings() {
  if (!D || !D.prices) return;
  var valElig = [];
  if (D.valuation) {
    for (var tk in D.valuation) {
      if (!D.valuation.hasOwnProperty(tk)) continue;
      if (tk === "_meta") continue;
      var v = D.valuation[tk];
      if (v && v.pe_percentile != null) valElig.push({ticker: tk, pct: v.pe_percentile});
    }
  }
  valElig.sort(function(a,b){
    if (a.pct !== b.pct) return a.pct - b.pct;
    return (a.ticker || "").localeCompare(b.ticker || "");
  });
  var nVal = valElig.length;
  var vA = Math.ceil(nVal*0.10), vB = vA+Math.ceil(nVal*0.15), vC = vB+Math.ceil(nVal*0.25), vD = vC+Math.ceil(nVal*0.25);
  var valBuckets = {};
  for (var vi = 0; vi < nVal; vi++) {
    var vr;
    if (vi < vA) vr = "A";
    else if (vi < vB) vr = "B";
    else if (vi < vC) vr = "C";
    else if (vi < vD) vr = "D";
    else vr = "F";
    valBuckets[valElig[vi].ticker] = vr;
  }
  masterRatingsMap = {};
  for (var pi = 0; pi < D.prices.length; pi++) {
    var p = D.prices[pi];
    var tkr = p.ticker;
    masterRatingsMap[tkr] = {
      tm:       SUM_v1TmRating(tkr),
      thematic: "C",
      fund_chg: "C",
      icbb:     "C",
      ssem:     (typeof ssemRatingMap !== "undefined" && ssemRatingMap[tkr]) ? ssemRatingMap[tkr] : "-",
      val:      valBuckets[tkr] != null ? valBuckets[tkr] : "-"
    };
  }
}

function SUM_ratingSortKey(g) {
  var order = {A:5,B:4,C:3,D:2,F:1,"-":0};
  return order[g] != null ? order[g] : -1;
}

function SUM_passesFilter(rating, filterState) {
  if (filterState === "") return true;
  if (filterState === "A") return rating === "A";
  if (filterState === "AB") return rating === "A" || rating === "B";
  return true;
}

function SUM_ratingPill(grade, isPlaceholder) {
  var key = (grade === "-") ? "N" : grade;
  var label = (grade === "-") ? "&mdash;" : grade;
  var ttl = isPlaceholder ? ' title="' + SUM_PLACEHOLDER_TOOLTIP + '"' : "";
  return '<span class="ssem-rating-pill ssem-rating-' + key + '"' + ttl + '>' + label + '</span>';
}

// Stage status pill (Cap green / Late amber / Early pink / dash)
function SUM_stagePill(stage) {
  if (!stage || stage === "None") return '<span style="color:#888">&mdash;</span>';
  if (stage === "Capital") return '<span style="display:inline-block;padding:2px 6px;background:#E1F5EE;color:#085041;border-radius:10px;font-size:9px;font-weight:600">Cap</span>';
  if (stage === "Late")    return '<span style="display:inline-block;padding:2px 6px;background:#FAEEDA;color:#633806;border-radius:10px;font-size:9px;font-weight:600">Late</span>';
  if (stage === "Early")   return '<span style="display:inline-block;padding:2px 6px;background:#FBEAF0;color:#4B1528;border-radius:10px;font-size:9px;font-weight:600">Early</span>';
  return '<span style="color:#888">&mdash;</span>';
}

// 5-step conditional colour helper for percentile-like values (0-100; higher = better)
function SUM_pctileBucketStyle(v) {
  if (v == null) return "";
  if (v >= 85) return "background:#97C459;color:#173404;";
  if (v >= 70) return "background:#C0DD97;color:#173404;";
  if (v >= 50) return "background:#EAF3DE;color:#173404;";
  if (v >= 30) return "background:#FAEEDA;color:#412402;";
  return "background:#FCEBEB;color:#501313;";
}

// Conditional colour for inverted percentile (lower = better, e.g. PE percentile)
function SUM_invPctileBucketStyle(v) {
  if (v == null) return "";
  if (v <= 15) return "background:#97C459;color:#173404;";
  if (v <= 30) return "background:#C0DD97;color:#173404;";
  if (v <= 60) return "background:#EAF3DE;color:#173404;";
  if (v <= 80) return "background:#FAEEDA;color:#412402;";
  return "background:#FCEBEB;color:#501313;";
}

// Conditional colour for signed integer scores (e.g. SSEM scores -5 to +5)
function SUM_signedBucketStyle(v) {
  if (v == null) return "";
  if (v >= 4) return "background:#97C459;color:#173404;";
  if (v >= 2) return "background:#C0DD97;color:#173404;";
  if (v >= 1) return "background:#EAF3DE;color:#173404;";
  if (v === 0) return "";
  if (v >= -1) return "background:#FAEEDA;color:#412402;";
  return "background:#FCEBEB;color:#501313;";
}

// Conditional colour for excess-return decimals (e.g. rs_excess_market)
function SUM_excessBucketStyle(v) {
  if (v == null) return "";
  if (v >= 0.30) return "background:#97C459;color:#173404;";
  if (v >= 0.15) return "background:#C0DD97;color:#173404;";
  if (v >= 0.05) return "background:#EAF3DE;color:#173404;";
  if (v > -0.05) return "";
  if (v > -0.15) return "background:#FAEEDA;color:#412402;";
  return "background:#FCEBEB;color:#501313;";
}

// Format a signed percentile as +X% or -X%
function SUM_fmtSignedPct(v) {
  if (v == null) return "&mdash;";
  var pct = Math.round(v * 100);
  return (pct >= 0 ? "+" : "") + pct + "%";
}

// Format a signed integer score
function SUM_fmtSignedInt(v) {
  if (v == null) return "&mdash;";
  return (v > 0 ? "+" : "") + v;
}


window.cycleSummaryFilter = function(ratingId) {
  var cur = summaryFilters[ratingId];
  summaryFilters[ratingId] = cur === "" ? "A" : (cur === "A" ? "AB" : "");
  renderSummary();
};

window.toggleSummarySectorGrouping = function() {
  summarySectorGrouping = !summarySectorGrouping;
  renderSummary();
};

window.resetSummaryFilters = function() {
  summaryFilters = {tm:"",thematic:"",fund_chg:"",icbb:"",ssem:"",val:""};
  summarySectorGrouping = false;
  renderSummary();
};

function SUM_getTaxonomy(tkr) {
  if (typeof getTaxonomy === "function") return getTaxonomy(tkr);
  var tm = (D && D.ticker_mapping) ? D.ticker_mapping[tkr] : null;
  return {industry: tm ? tm.industry : "", sector: tm ? tm.sector : ""};
}

function SUM_filterToggleHTML(ratingId) {
  var state = summaryFilters[ratingId];
  var label = SUM_RATING_SHORT[ratingId];
  var stateLabel = state === "" ? "all" : (state === "A" ? "A" : "A|B");
  var activeClass = state === "" ? "" : "sum-tog-active";
  var bgStyle = state === "A" ? "background:#EAF3DE;border-color:#639922" :
                state === "AB" ? "background:#C0DD97;border-color:#639922" : "";
  return '<button class="tog sum-tog ' + activeClass + '" onclick="cycleSummaryFilter(\'' + ratingId + '\')" ' +
         'title="' + SUM_RATING_LABELS[ratingId] + ' filter: No filter -> A only -> A or B" ' +
         'style="display:inline-flex;align-items:center;gap:4px;padding:3px 8px;font-size:11px;' + bgStyle + '">' +
         '<span style="font-weight:700">' + label + '</span>' +
         '<span style="font-weight:600;font-size:10px">' + stateLabel + '</span></button>';
}

function renderSummary() {
  buildHeaderControls("summary");
  var container = document.getElementById("tab-summary");
  if (!container) return;
  if (Object.keys(masterRatingsMap).length === 0) deriveMasterRatings();
  var h = "";

  // Section 1: Header controls
  h += '<div class="summary-controls" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:8px 12px;background:rgba(100,100,100,0.04);border-bottom:1px solid var(--border);margin-bottom:8px">';
  h += '<div style="font-size:11px;color:var(--text-secondary);font-weight:600;letter-spacing:.3px">MASTER RATING FILTERS:</div>';
  for (var ri = 0; ri < SUM_RATINGS.length; ri++) h += SUM_filterToggleHTML(SUM_RATINGS[ri]);
  var sgActive = summarySectorGrouping ? "sum-tog-active" : "";
  var sgLabel = summarySectorGrouping ? "ON" : "OFF";
  h += '<span style="color:var(--text-secondary);font-size:11px">|</span>';
  h += '<button class="tog sum-tog ' + sgActive + '" onclick="toggleSummarySectorGrouping()" style="padding:3px 8px;font-size:11px"><span style="font-weight:700">Sector grouping</span> <span style="color:#666;font-size:10px">' + sgLabel + '</span></button>';
  h += '<button class="tog" onclick="resetSummaryFilters()" style="padding:3px 8px;font-size:11px;margin-left:auto">Reset filters</button>';
  h += '</div>';

  // V1 watermark
  h += '<div style="padding:4px 12px;font-size:10px;color:var(--text-secondary);font-style:italic;background:rgba(180,120,30,0.06);border-bottom:1px solid rgba(180,120,30,0.15)">';
  h += 'V1: Technical Momentum uses placeholder dichotomy. Thematic Fit / Fundamental Change / ICBB use placeholder "C" (uniform). Bell-curve methodology and REPOSITORY rating sources are in development.';
  h += '</div>';

  h += SUM_renderWaterfall();
  h += SUM_renderIndustriesFlow();
  h += SUM_renderSectorsFlow();
  h += SUM_renderQualifiedStocks();
  container.innerHTML = h;
}

function SUM_renderWaterfall() {
  var tickers = [];
  for (var pi = 0; pi < D.prices.length; pi++) tickers.push(D.prices[pi].ticker);
  var Y = (D.meta && D.meta.stock_count) ? D.meta.stock_count : tickers.length;
  var THR = [
    {key:"A",   label:"A only",      passSet:{A:1}},
    {key:"AB",  label:"A or B",      passSet:{A:1,B:1}},
    {key:"ABC", label:"A or B or C", passSet:{A:1,B:1,C:1}}
  ];
  var rows = [];
  for (var ti = 0; ti < THR.length; ti++) {
    var thr = THR[ti], surv = tickers.slice(), cells = [];
    for (var ci = 0; ci < SUM_RATINGS.length; ci++) {
      var rid = SUM_RATINGS[ci], next = [], folded = 0;
      for (var si = 0; si < surv.length; si++) {
        var tkr = surv[si], mr = masterRatingsMap[tkr], rg = mr ? mr[rid] : "-";
        if (rg === "-") { next.push(tkr); folded++; }
        else if (thr.passSet[rg]) next.push(tkr);
      }
      cells.push({count:next.length, foldForwarded:folded});
      surv = next;
    }
    rows.push({key:thr.key, label:thr.label, cells:cells, muted:(thr.key==="ABC")});
  }
  var h = '<div class="summary-section" style="margin:8px 12px 16px 12px">';
  h += '<div style="font-size:13px;font-weight:700;color:var(--text-primary);margin-bottom:6px">Funnel - multi-rating pass-through</div>';
  h += '<div style="font-size:11px;color:var(--text-secondary);margin-bottom:6px;font-style:italic">Stocks without a rating in a column are folded forward (counted as passing). Row 3 (A/B/C) is greyed as cross-reference only.</div>';
  h += '<table class="data-table" style="width:100%;table-layout:fixed">';
  h += '<colgroup><col style="width:90px">';
  for (var cj = 0; cj < 6; cj++) h += '<col>';
  h += '</colgroup>';
  h += '<thead><tr><th style="background:rgba(100,100,100,0.06);text-align:left;padding:6px 8px">Threshold</th>';
  for (var rii = 0; rii < SUM_RATINGS.length; rii++) h += '<th style="background:rgba(100,100,100,0.06);font-size:11px;font-weight:700;text-align:center;padding:6px 8px">' + SUM_RATING_LABELS[SUM_RATINGS[rii]] + '</th>';
  h += '</tr></thead><tbody>';
  var ROW_BG = ["rgba(39,103,73,0.18)","rgba(56,161,105,0.10)","rgba(180,180,180,0.18)"];
  var ROW_TEXT = ["#1a4731","#22543d","#777"];
  for (var rri = 0; rri < rows.length; rri++) {
    var row = rows[rri];
    h += '<tr><td style="font-weight:700;padding:6px 8px;background:' + ROW_BG[rri] + ';color:' + ROW_TEXT[rri] + ';text-align:center;font-size:11px;letter-spacing:.3px">' + row.label + '</td>';
    for (var cn = 0; cn < row.cells.length; cn++) {
      var c = row.cells[cn];
      var cs = 'text-align:center;padding:8px;font-family:Menlo,monospace;font-size:13px;font-weight:600;';
      if (row.muted) cs += 'color:#777;background:rgba(200,200,200,0.06);';
      else cs += 'color:#1a4731;background:' + ROW_BG[rri] + ';';
      var ttl = c.foldForwarded > 0 ? c.foldForwarded + ' of these ' + c.count + ' stocks passed via missing-rating fold-forward' : 'No fold-forward in this cell';
      h += '<td style="' + cs + '" title="' + ttl + '">' + c.count + ' / ' + Y + '</td>';
    }
    h += '</tr>';
  }
  h += '</tbody></table></div>';
  return h;
}

function SUM_buildGroupAggregates(groupKey) {
  var groups = {};
  for (var pi = 0; pi < D.prices.length; pi++) {
    var p = D.prices[pi], tax = SUM_getTaxonomy(p.ticker), gn = tax[groupKey];
    if (!gn) continue;
    if (!groups[gn]) {
      groups[gn] = {groupName:gn, total:0, perRating:{}};
      for (var ri = 0; ri < SUM_RATINGS.length; ri++) groups[gn].perRating[SUM_RATINGS[ri]] = {A:0,B:0,C:0,D:0,F:0,dash:0};
    }
    groups[gn].total++;
    var mr = masterRatingsMap[p.ticker];
    if (!mr) continue;
    for (var rj = 0; rj < SUM_RATINGS.length; rj++) {
      var rid = SUM_RATINGS[rj], g = mr[rid];
      if (g === "-") groups[gn].perRating[rid].dash++;
      else if (g === "A" || g === "B" || g === "C" || g === "D" || g === "F") groups[gn].perRating[rid][g]++;
    }
  }
  var out = [];
  for (var gn2 in groups) {
    if (!groups.hasOwnProperty(gn2)) continue;
    var g2 = groups[gn2];
    for (var rk = 0; rk < SUM_RATINGS.length; rk++) {
      var pr = g2.perRating[SUM_RATINGS[rk]];
      pr.pct_AB = g2.total > 0 ? (pr.A + pr.B) / g2.total : 0;
    }
    out.push(g2);
  }
  out.sort(function(a,b){
    var ka = a.perRating.tm.pct_AB, kb = b.perRating.tm.pct_AB;
    if (ka !== kb) return kb - ka;
    var k2a = a.perRating.thematic.pct_AB, k2b = b.perRating.thematic.pct_AB;
    if (k2a !== k2b) return k2b - k2a;
    var k3a = a.perRating.fund_chg.pct_AB, k3b = b.perRating.fund_chg.pct_AB;
    if (k3a !== k3b) return k3b - k3a;
    return (a.groupName || "").localeCompare(b.groupName || "");
  });
  return out;
}

function SUM_heatmapCellColor(pct) {
  if (pct <= 0) return "background:#fafafa";
  var t = Math.min(pct, 1), alpha = 0.05 + t * 0.60;
  return "background:rgba(56,161,105," + alpha.toFixed(2) + ")";
}

function SUM_renderHeatmapMatrix(rows, title, maxVisibleRows, anchorId) {
  var h = '<div class="summary-section" style="margin:16px 12px" id="' + anchorId + '">';
  h += '<div style="font-size:13px;font-weight:700;color:var(--text-primary);margin-bottom:6px">' + title + '</div>';
  var wrapStyle = '';
  if (maxVisibleRows) wrapStyle = 'style="max-height:' + (maxVisibleRows*28+60) + 'px;overflow-y:auto;border:1px solid var(--border)"';
  h += '<div class="ind-sec-wrap" ' + wrapStyle + '>';
  h += '<table class="data-table" style="width:100%;table-layout:fixed">';
  h += '<colgroup><col style="width:30%">';
  for (var c = 0; c < 6; c++) h += '<col style="width:11.66%">';
  h += '</colgroup>';
  h += '<thead style="position:sticky;top:0;background:var(--bg-primary);z-index:2"><tr>';
  h += '<th style="background:rgba(100,100,100,0.06);text-align:left;padding:6px 8px;font-size:11px">' + title.replace(" flow","").replace(/s$/,"") + '</th>';
  for (var ri = 0; ri < SUM_RATINGS.length; ri++) h += '<th style="background:rgba(100,100,100,0.06);font-size:10px;font-weight:700;text-align:center;padding:6px 4px">' + SUM_RATING_SHORT[SUM_RATINGS[ri]] + '</th>';
  h += '</tr></thead><tbody>';
  for (var rr = 0; rr < rows.length; rr++) {
    var row = rows[rr];
    h += '<tr>';
    var nameAttr = row.groupName.replace(/'/g,"&#39;").replace(/"/g,"&quot;");
    h += '<td style="padding:4px 8px;font-size:11px;font-weight:600;color:var(--text-primary);cursor:default" title="' + nameAttr + ' (' + row.total + ' stocks)">' + row.groupName + ' <span style="color:var(--text-secondary);font-weight:400">(' + row.total + ')</span></td>';
    for (var rj = 0; rj < SUM_RATINGS.length; rj++) {
      var rid = SUM_RATINGS[rj], pr = row.perRating[rid], pct = pr.pct_AB;
      var color = SUM_heatmapCellColor(pct);
      var pctStr = pct > 0 ? Math.round(pct*100) + "%" : "-";
      var ttl = SUM_RATING_LABELS[rid] + ": A=" + pr.A + " B=" + pr.B + " C=" + pr.C + " D=" + pr.D + " F=" + pr.F + " of " + row.total;
      h += '<td style="text-align:center;padding:4px;font-family:Menlo,monospace;font-size:11px;font-weight:600;' + color + '" title="' + ttl + '">' + pctStr + '</td>';
    }
    h += '</tr>';
  }
  h += '</tbody></table></div></div>';
  return h;
}

function SUM_renderIndustriesFlow() { return SUM_renderHeatmapMatrix(SUM_buildGroupAggregates("industry"), "Industries flow", null, "sum-industries"); }
function SUM_renderSectorsFlow()    { return SUM_renderHeatmapMatrix(SUM_buildGroupAggregates("sector"),   "Sectors flow",    15,   "sum-sectors"); }


function SUM_renderQualifiedStocks() {
  // Build rows with all fields per stock
  var rows = [];
  for (var pi = 0; pi < D.prices.length; pi++) {
    var p = D.prices[pi];
    var mr = masterRatingsMap[p.ticker];
    if (!mr) continue;
    // Apply 6 master rating filters AND-combined
    var keep = true;
    for (var ri = 0; ri < SUM_RATINGS.length; ri++) {
      if (!SUM_passesFilter(mr[SUM_RATINGS[ri]], summaryFilters[SUM_RATINGS[ri]])) { keep = false; break; }
    }
    if (!keep) continue;

    var tax = SUM_getTaxonomy(p.ticker);
    var fm = (typeof filterMap !== "undefined") ? filterMap[p.ticker] : null;

    // TM stage statuses
    var stages = {};
    for (var sc = 0; sc < SUM_STAGE_COLS.length; sc++) {
      var sid = SUM_STAGE_COLS[sc].id;
      stages[sid] = (fm && fm[sid] && fm[sid].stage) ? fm[sid].stage : null;
    }

    // RS values
    var rsVals = {
      rs_percentile:    (p.rs_percentile != null) ? p.rs_percentile : null,
      rs_vs_sector:     (p.rs_vs_sector != null) ? p.rs_vs_sector : null,
      rs_vs_industry:   (p.rs_vs_industry != null) ? p.rs_vs_industry : null,
      rs_excess_market: (p.rs_excess_market != null) ? p.rs_excess_market : null
    };

    // SSEM per-timeframe totals
    var ssemTotals = {};
    var ssData = (D.ssem && D.ssem[p.ticker]) ? D.ssem[p.ticker] : null;
    var ssemGrand = 0, ssemHasAny = false;
    for (var ti = 0; ti < SUM_SSEM_TIMEFRAMES.length; ti++) {
      var tf = SUM_SSEM_TIMEFRAMES[ti];
      var t = SUM_ssemTimeframeTotal(ssData, tf);
      ssemTotals[tf] = t;
      if (t != null) { ssemGrand += t; ssemHasAny = true; }
    }
    ssemTotals.total = ssemHasAny ? ssemGrand : null;

    // Valuation
    var vl = (D.valuation && D.valuation[p.ticker]) ? D.valuation[p.ticker] : null;
    var valData = {
      pctile:   (vl && vl.pe_percentile != null) ? vl.pe_percentile : null,
      cur:      (vl && vl.pe_current != null) ? vl.pe_current : null,
      lo:       (vl && vl.pe_10y_low != null) ? vl.pe_10y_low : null,
      hi:       (vl && vl.pe_10y_high != null) ? vl.pe_10y_high : null
    };

    rows.push({
      ticker: p.ticker,
      company: p.company_name || p.ticker,
      industry: tax.industry || "",
      sector: tax.sector || "",
      mr: mr,
      stages: stages,
      rs: rsVals,
      ssem: ssemTotals,
      val: valData
    });
  }

  // Default 6-key cascade sort
  rows.sort(function(a,b){
    for (var k = 0; k < SUM_RATINGS.length; k++) {
      var rid = SUM_RATINGS[k];
      var ka = SUM_ratingSortKey(a.mr[rid]), kb = SUM_ratingSortKey(b.mr[rid]);
      if (ka !== kb) return kb - ka;
    }
    return (a.ticker || "").localeCompare(b.ticker || "");
  });

  // Optional sector grouping
  if (summarySectorGrouping) {
    rows.sort(function(a,b){
      var sa = a.sector || "zz_no_sector", sb = b.sector || "zz_no_sector";
      if (sa !== sb) return sa.localeCompare(sb);
      for (var k = 0; k < SUM_RATINGS.length; k++) {
        var rid = SUM_RATINGS[k];
        var ka = SUM_ratingSortKey(a.mr[rid]), kb = SUM_ratingSortKey(b.mr[rid]);
        if (ka !== kb) return kb - ka;
      }
      return (a.ticker || "").localeCompare(b.ticker || "");
    });
  }

  var h = '<div class="summary-section" style="margin:16px 12px" id="sum-qualified">';
  h += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">';
  h += '<div style="font-size:13px;font-weight:700;color:var(--text-primary)">Qualified Stocks</div>';
  h += '<div style="font-size:11px;color:var(--text-secondary)">' + rows.length + ' stocks pass all active filters</div>';
  h += '</div>';

  h += '<div style="max-height:700px;overflow-y:auto;overflow-x:auto;border:1px solid var(--border);border-radius:4px">';
  h += '<table class="data-table" style="font-size:10px;min-width:2400px">';

  // ROW 1 — Group header
  h += '<thead style="position:sticky;top:0;z-index:5;background:var(--bg-primary)"><tr>';
  h += '<th colspan="4" style="padding:6px 8px;background:#F1EFE8;color:#444441;text-align:left;font-weight:600;font-size:11px;letter-spacing:.3px;border-right:1px solid var(--border)">Inputs</th>';
  h += '<th colspan="12" style="padding:6px 8px;background:#EEEDFE;color:#3C3489;text-align:center;font-weight:600;font-size:11px;letter-spacing:.3px;border-right:1px solid var(--border)">Technical Momentum</th>';
  h += '<th colspan="5" style="padding:6px 8px;background:#E6F1FB;color:#0C447C;text-align:center;font-weight:600;font-size:11px;letter-spacing:.3px;border-right:1px solid var(--border)">SSEM</th>';
  h += '<th colspan="2" style="padding:6px 8px;background:#EAF3DE;color:#27500A;text-align:center;font-weight:600;font-size:11px;letter-spacing:.3px;border-right:1px solid var(--border)">Valuation</th>';
  h += '<th colspan="6" style="padding:6px 8px;background:#FAEEDA;color:#633806;text-align:center;font-weight:600;font-size:11px;letter-spacing:.3px">Master Ratings</th>';
  h += '</tr>';

  // ROW 2 — Sub-group header
  h += '<tr style="border-top:1px solid var(--border)">';
  h += '<th colspan="4" style="background:var(--bg-primary);border-right:1px solid var(--border)"></th>';
  h += '<th colspan="2" style="padding:4px;background:rgba(238,237,254,0.4);color:#3C3489;text-align:center;font-size:10px;font-weight:600;border-right:1px dashed var(--border)">Stage 1</th>';
  h += '<th colspan="3" style="padding:4px;background:rgba(238,237,254,0.4);color:#3C3489;text-align:center;font-size:10px;font-weight:600;border-right:1px dashed var(--border)">Stage 2</th>';
  h += '<th colspan="1" style="padding:4px;background:rgba(238,237,254,0.4);color:#3C3489;text-align:center;font-size:10px;font-weight:600;border-right:1px dashed var(--border)">Stage 3</th>';
  h += '<th colspan="2" style="padding:4px;background:rgba(238,237,254,0.4);color:#3C3489;text-align:center;font-size:10px;font-weight:600;border-right:1px dashed var(--border)">Stage 4</th>';
  h += '<th colspan="4" style="padding:4px;background:rgba(238,237,254,0.4);color:#3C3489;text-align:center;font-size:10px;font-weight:600;border-right:1px solid var(--border)">Relative Strength</th>';
  h += '<th colspan="5" style="background:var(--bg-primary);border-right:1px solid var(--border)"></th>';
  h += '<th colspan="2" style="background:var(--bg-primary);border-right:1px solid var(--border)"></th>';
  h += '<th colspan="6" style="background:var(--bg-primary)"></th>';
  h += '</tr>';

  // ROW 3 — Column header
  h += '<tr style="border-top:1px solid var(--border);background:rgba(100,100,100,0.04)">';
  h += '<th style="padding:5px 8px;text-align:left;font-size:10px;font-weight:600">Tkr</th>';
  h += '<th style="padding:5px 8px;text-align:left;font-size:10px;font-weight:600">Company</th>';
  h += '<th style="padding:5px 8px;text-align:left;font-size:10px;font-weight:600">Industry</th>';
  h += '<th style="padding:5px 8px;text-align:left;font-size:10px;font-weight:600;border-right:1px solid var(--border)">Sector</th>';
  for (var sc = 0; sc < SUM_STAGE_COLS.length; sc++) {
    var col = SUM_STAGE_COLS[sc];
    var rborder = (col.id === "probing_bet" || col.id === "uptrend_retest" || col.id === "s3_topping") ? "border-right:1px dashed var(--border);" : "";
    if (col.id === "collapse") rborder = "border-right:1px dashed var(--border);";
    h += '<th style="padding:5px 4px;text-align:center;font-size:10px;font-weight:600;' + rborder + '">' + col.label + '</th>';
  }
  for (var rs = 0; rs < SUM_RS_COLS.length; rs++) {
    var rsCol = SUM_RS_COLS[rs];
    var rb = (rs === SUM_RS_COLS.length - 1) ? "border-right:1px solid var(--border);" : "";
    h += '<th style="padding:5px 4px;text-align:center;font-size:10px;font-weight:600;' + rb + '">' + rsCol.label + '</th>';
  }
  for (var tf = 0; tf < SUM_SSEM_TIMEFRAMES.length; tf++) {
    h += '<th style="padding:5px 4px;text-align:center;font-size:10px;font-weight:600">' + SUM_SSEM_TIMEFRAMES[tf].toUpperCase() + '</th>';
  }
  h += '<th style="padding:5px 4px;text-align:center;font-size:10px;font-weight:600;border-right:1px solid var(--border)">Total</th>';
  h += '<th style="padding:5px 4px;text-align:center;font-size:10px;font-weight:600">Pctile</th>';
  h += '<th style="padding:5px 4px;text-align:center;font-size:10px;font-weight:600;border-right:1px solid var(--border)">P/E 10Y Range</th>';
  for (var rr = 0; rr < SUM_RATINGS.length; rr++) {
    h += '<th style="padding:5px 4px;text-align:center;font-size:10px;font-weight:600">' + SUM_RATING_SHORT[SUM_RATINGS[rr]] + '</th>';
  }
  h += '</tr></thead><tbody>';

  // Data rows
  var _prevSector = null;
  var colTotal = 4 + 12 + 5 + 2 + 6;
  for (var rwi = 0; rwi < rows.length; rwi++) {
    var row = rows[rwi];
    if (summarySectorGrouping && row.sector !== _prevSector) {
      var secCount = rows.filter(function(r){return r.sector === row.sector}).length;
      h += '<tr class="group-header-row"><td colspan="' + colTotal + '" style="background:rgba(100,100,100,0.06);font-weight:700;font-size:11px;padding:4px 8px;color:var(--text-primary)">' + (row.sector || "Unknown") + ' <span style="font-weight:400;color:var(--text-secondary)">(' + secCount + ')</span></td></tr>';
      _prevSector = row.sector;
    }
    h += '<tr>';
    h += '<td style="padding:4px 8px;font-size:10px;font-family:Menlo,monospace;font-weight:500">' + row.ticker + '</td>';
    h += '<td style="padding:4px 8px;font-size:10px">' + row.company + '</td>';
    h += '<td style="padding:4px 8px;font-size:9px;color:var(--text-secondary)">' + row.industry + '</td>';
    h += '<td style="padding:4px 8px;font-size:9px;color:var(--text-secondary);border-right:1px solid var(--border)">' + row.sector + '</td>';
    // Stage pills
    for (var sci = 0; sci < SUM_STAGE_COLS.length; sci++) {
      var col2 = SUM_STAGE_COLS[sci];
      var rb2 = (col2.id === "probing_bet" || col2.id === "uptrend_retest" || col2.id === "s3_topping" || col2.id === "collapse") ? "border-right:1px dashed var(--border);" : "";
      h += '<td style="padding:4px;text-align:center;' + rb2 + '">' + SUM_stagePill(row.stages[col2.id]) + '</td>';
    }
    // RS columns
    for (var rsi = 0; rsi < SUM_RS_COLS.length; rsi++) {
      var rsCol2 = SUM_RS_COLS[rsi];
      var v = row.rs[rsCol2.key];
      var style, content;
      if (rsCol2.format === "signedPct") {
        style = SUM_excessBucketStyle(v);
        content = SUM_fmtSignedPct(v);
      } else {
        style = SUM_pctileBucketStyle(v);
        content = (v != null) ? v : "&mdash;";
      }
      var rb3 = (rsi === SUM_RS_COLS.length - 1) ? "border-right:1px solid var(--border);" : "";
      h += '<td style="padding:4px;text-align:center;font-family:Menlo,monospace;font-size:10px;font-weight:600;' + style + rb3 + '">' + content + '</td>';
    }
    // SSEM timeframe cells
    for (var ti2 = 0; ti2 < SUM_SSEM_TIMEFRAMES.length; ti2++) {
      var tfv = row.ssem[SUM_SSEM_TIMEFRAMES[ti2]];
      var st = SUM_signedBucketStyle(tfv);
      h += '<td style="padding:4px;text-align:center;font-family:Menlo,monospace;font-size:10px;font-weight:600;' + st + '">' + SUM_fmtSignedInt(tfv) + '</td>';
    }
    // SSEM Total
    var totSt = SUM_signedBucketStyle(row.ssem.total);
    h += '<td style="padding:4px;text-align:center;font-family:Menlo,monospace;font-size:10px;font-weight:700;border-right:1px solid var(--border);' + totSt + '">' + SUM_fmtSignedInt(row.ssem.total) + '</td>';
    // Valuation percentile
    var valSt = SUM_invPctileBucketStyle(row.val.pctile);
    var valStr = row.val.pctile != null ? Math.round(row.val.pctile) + "%" : "&mdash;";
    h += '<td style="padding:4px;text-align:center;font-family:Menlo,monospace;font-size:10px;font-weight:600;' + valSt + '">' + valStr + '</td>';
    // Valuation sparkline (P/E 10Y range bar) — reuse buildRangeBar
    var sparkContent;
    if (row.val.lo != null && row.val.hi != null && row.val.cur != null && typeof buildRangeBar === "function") {
      sparkContent = buildRangeBar(row.val.lo, row.val.hi, row.val.cur);
    } else {
      sparkContent = '<span style="color:var(--text-tertiary)">&mdash;</span>';
    }
    h += '<td style="padding:4px;text-align:center;border-right:1px solid var(--border)">' + sparkContent + '</td>';
    // Master Ratings
    for (var mri = 0; mri < SUM_RATINGS.length; mri++) {
      var ridM = SUM_RATINGS[mri];
      var isPh = (ridM === "thematic" || ridM === "fund_chg" || ridM === "icbb");
      h += '<td style="padding:4px;text-align:center">' + SUM_ratingPill(row.mr[ridM], isPh) + '</td>';
    }
    h += '</tr>';
  }
  h += '</tbody></table></div></div>';
  return h;
}

/* SUMMARY-TAB-MARKER-END-V12 */
