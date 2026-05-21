"""
=============================================================================
PATCHER — S63 Single Stock View page
=============================================================================
Project: SA - Master Dashboard
Session: S63 (21-May-2026)
Author: [W] Watson (SYSTEMS ARCHITECT role)

WHAT THIS PATCHER DOES
----------------------
Adds a new full-screen "Stock View" overlay page to the Master Dashboard.

Triggered by an amber/gold button in the header (next to SOI List).

Layout (per mockup v3, approved by Richard):
  H  = Header row: search box + close button (within overlay)
  T  = Full-width single-stock info table (one row for selected stock)
  C/I= Lower band: Chart (left ~52%) | Sector/Industry/Cohort/Geography tile (right)
       Both panes expand to fill full viewport height.

Table columns (28 total):
  Fixed (4): Name·Ticker | Price | Pullback distance
  Stages (8 = 4 pairs): S1 Basing | S2 Uptrend | S3 Topping | S4 Decline
  PPI (4 = 2 pairs): Pulling back within MT/LT uptrend | Basing
  NPI (2 = 1 pair): Collapsing
  Setups/Tests (10 = 5 pairs): Healthy Retest | PB Stage 1 | PB Stage 2 | Speculative Bets | Healthy VCP

Cohort tile (4 columns):
  #1 Industry  — all stocks in same industry (from prices data)
  #2 Sector    — all stocks in same sector
  #3 Named cohort — Section D cohort from cohorts-v2.json + thematic cohort memberships
  #4 Geography — stocks from same country (ticker suffix)

Colour row tint rule (Watson-defined):
  Green  = S2 Probable AND any Setup/Test Probable
  Amber  = (S2 Plausible+) AND (PPI pulling_back OR basing Possible+)
  Blue   = S1 Probable or Plausible
  Red    = NPI collapsing Possible+ OR S3 Probable OR S4 Probable
  Neutral = else

Changes to build_dashboard.py:
  1. Cohort data embedding (SSP_COHORTS var) in data_js
  2. CSS block for .ssp-overlay and all SSP UI elements
  3. HTML: .ssp-overlay div before chart-panel div
  4. JS: self-contained IIFE module
  5. Header: "Stock View" amber button after SOI List

Idempotency marker: MD-V2-S63-STOCK-VIEW-MARKER
=============================================================================
"""
from __future__ import annotations
import os, sys, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.normpath(os.path.join(HERE, "build_dashboard.py"))
MARKER = "/* MD-V2-S63-STOCK-VIEW-MARKER */"


def must_replace(text, old, new, label):
    n = text.count(old)
    if n != 1:
        sys.stderr.write("ERROR: anchor '{}' found {} times (expected 1).\n".format(label, n))
        sys.stderr.write("First 200 chars:\n{}\n".format(repr(old[:200])))
        sys.exit(2)
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# CSS block
# ---------------------------------------------------------------------------
SSP_CSS = r"""
/* =====================================================================
   MD-V2-S63 STOCK VIEW OVERLAY
   ===================================================================== */
/* Amber/gold Stock View header button */
.ctrl-btn.ssp-btn{background:rgba(180,100,0,0.08);border-color:rgba(180,100,0,0.4);color:#92400e}
.ctrl-btn.ssp-btn:hover{background:rgba(180,100,0,0.18);border-color:#b45309;color:#78350f}

/* Full-screen overlay */
.ssp-overlay{position:fixed;inset:0;z-index:9900;background:var(--bg);display:none;flex-direction:column;overflow:hidden}
.ssp-overlay.open{display:flex}

/* Overlay header row */
.ssp-hdr{display:flex;align-items:center;gap:8px;padding:7px 14px;background:var(--card);border-bottom:1px solid var(--border);flex-shrink:0}
.ssp-hdr-title{font-size:13px;font-weight:700;color:var(--text-bright);margin-right:4px;white-space:nowrap}
.ssp-search-wrap{position:relative;flex:0 0 320px}
.ssp-search{width:100%;box-sizing:border-box;padding:4px 8px;border:1px solid var(--border);border-radius:4px;background:var(--card);color:var(--text-bright);font-family:var(--font);font-size:11px}
.ssp-search:focus{outline:none;border-color:#b45309}
.ssp-dropdown{position:absolute;top:calc(100% + 2px);left:0;right:0;background:var(--card);border:1px solid var(--border);border-radius:4px;max-height:220px;overflow-y:auto;z-index:9901;box-shadow:0 4px 12px rgba(0,0,0,0.15)}
.ssp-dd-item{padding:5px 10px;font-size:11px;cursor:pointer;color:var(--text-dim)}
.ssp-dd-item:hover,.ssp-dd-item.active{background:rgba(180,100,0,0.08);color:var(--text-bright)}
.ssp-dd-ticker{font-weight:700;color:#92400e;margin-right:5px}
.ssp-hdr-stock{font-size:12px;font-weight:700;color:var(--text-bright);margin-left:8px;white-space:nowrap}
.ssp-hdr-company{font-size:11px;color:var(--text-dim);white-space:nowrap}
.ssp-close-btn{margin-left:auto;background:none;border:1px solid var(--border);color:var(--text-dim);font-size:15px;line-height:1;padding:2px 7px;border-radius:4px;cursor:pointer}
.ssp-close-btn:hover{color:var(--text-bright);border-color:#bbb}

/* Stock info table band */
.ssp-tbl-band{flex-shrink:0;padding:6px 14px 4px;overflow:hidden}
.ssp-tbl-outer{width:100%;overflow:hidden}
.ssp-tbl{border-collapse:collapse;width:100%;table-layout:fixed;font-size:10px}
.ssp-tbl colgroup col{} /* widths set inline */
/* Group header row */
.ssp-tbl .ssp-gh{background:#f3efe2;font-size:9px;font-weight:700;text-align:center;padding:2px 3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
/* Column header row */
.ssp-tbl .ssp-ch{background:#f7f5ee;font-size:8.5px;font-weight:600;color:#555;text-align:center;padding:2px 2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
/* Data cells */
.ssp-tbl td{padding:3px 3px;vertical-align:middle;text-align:center;border-bottom:1px solid #e8e4d8;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ssp-tbl td.ssp-name-cell{text-align:left;font-size:10px;font-weight:600;color:var(--text-bright)}
.ssp-tbl .ssp-ticker{font-size:9px;font-weight:700;color:#555;display:block}
.ssp-tbl .ssp-price{font-size:10px;font-weight:600;color:var(--text-bright)}
.ssp-tbl .ssp-pb{font-size:10px;color:#555}
/* Group-start borders (thicker left border signals new group) */
.ssp-tbl .ssp-gs-stages{border-left:2px solid #1e3a5f}
.ssp-tbl .ssp-gs-ppi{border-left:2px solid #0f6e56}
.ssp-tbl .ssp-gs-npi{border-left:2px solid #a32d2d}
.ssp-tbl .ssp-gs-setups{border-left:2px solid #4c1d95}
/* Pair divider (thin border between rating and score within a pair, and between pairs) */
.ssp-tbl .ssp-pair-div{border-left:1px solid #c8c0a8}
/* Rating pills */
.ssp-pill{display:inline-block;padding:1px 4px;border-radius:3px;font-size:8.5px;font-weight:700;text-align:center;line-height:1.3;white-space:nowrap}
.ssp-pill-prob{background:#bbf7d0;color:#14532d}
.ssp-pill-pla{background:#d1fae5;color:#166534}
.ssp-pill-pos{background:#fef3c7;color:#78350f}
.ssp-pill-none{background:#e5e7eb;color:#374151}
.ssp-pill-qual{background:#bfdbfe;color:#1e40af}
/* Score pips */
.ssp-pips{display:inline-flex;gap:1.5px;vertical-align:middle}
.ssp-pip{width:6px;height:6px;border-radius:50%;background:#d1d5db}
.ssp-pip.on{background:#6b7280}
.ssp-pip.on-prob{background:#14532d}
.ssp-pip.on-pla{background:#166534}
.ssp-pip.on-pos{background:#78350f}
.ssp-pip.on-red{background:#991b1b}
.ssp-pip.on-blue{background:#1e40af}
/* Row colour tints */
.ssp-row-green{background:rgba(20,83,45,0.07)}
.ssp-row-amber{background:rgba(180,100,0,0.06)}
.ssp-row-blue{background:rgba(30,58,138,0.06)}
.ssp-row-red{background:rgba(153,27,27,0.07)}
/* Legend */
.ssp-legend{display:flex;gap:10px;padding:3px 14px;font-size:9px;color:var(--text-dim);flex-shrink:0;border-top:1px solid var(--border)}
.ssp-legend-item{display:flex;align-items:center;gap:4px}
.ssp-legend-dot{width:10px;height:10px;border-radius:2px;flex-shrink:0}

/* Lower band: chart + cohort tile */
.ssp-lower{flex:1;min-height:0;display:flex;gap:8px;padding:6px 14px;overflow:hidden}
/* Chart pane */
.ssp-chart-pane{flex:0 0 52%;min-height:0;display:flex;flex-direction:column;background:var(--card);border:1px solid var(--border);border-radius:4px;overflow:hidden}
.ssp-chart-hdr{padding:5px 10px;font-size:11px;font-weight:700;color:var(--text-bright);border-bottom:1px solid var(--border);flex-shrink:0;display:flex;align-items:center;gap:6px}
.ssp-chart-body{flex:1;min-height:0;overflow:hidden;position:relative;padding:6px}
#ssp-chart-canvas{width:100%;height:100%;display:block}
.ssp-chart-loading{padding:20px;color:var(--text-dim);font-size:11px;text-align:center}
/* Cohort pane */
.ssp-cohort-pane{flex:1;min-height:0;display:flex;flex-direction:column;background:var(--card);border:1px solid var(--border);border-radius:4px;overflow:hidden}
.ssp-cohort-hdr{padding:5px 10px;font-size:11px;font-weight:700;color:var(--text-bright);border-bottom:1px solid var(--border);flex-shrink:0}
.ssp-cohort-body{flex:1;min-height:0;display:grid;grid-template-columns:repeat(4,1fr);gap:0;overflow:hidden}
.ssp-cohort-col{display:flex;flex-direction:column;border-right:1px solid var(--border);overflow:hidden}
.ssp-cohort-col:last-child{border-right:none}
.ssp-cohort-col-hdr{padding:4px 8px;font-size:9.5px;font-weight:700;color:#555;background:#f7f5ee;border-bottom:1px solid var(--border);flex-shrink:0;white-space:nowrap}
.ssp-cohort-names{flex:1;min-height:0;overflow-y:auto;padding:4px 0}
.ssp-cohort-name{display:block;padding:2px 8px;font-size:10px;color:var(--text-dim);cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ssp-cohort-name:hover{background:rgba(180,100,0,0.06);color:var(--text-bright)}
.ssp-cohort-name.self{font-weight:700;color:var(--text-bright);background:rgba(180,100,0,0.06)}
.ssp-cohort-name.self:hover{background:rgba(180,100,0,0.12)}
.ssp-cohort-group-hdr{display:block;padding:3px 8px;font-size:8.5px;font-weight:700;color:#999;text-transform:uppercase;letter-spacing:0.04em;margin-top:4px}
/* MD-V2-S63-STOCK-VIEW-CSS-END */
"""

# ---------------------------------------------------------------------------
# HTML overlay div
# ---------------------------------------------------------------------------
SSP_HTML = (
    '<!-- MD-V2-S63-STOCK-VIEW-HTML-MARKER -->\n'
    '<div class="ssp-overlay" id="ssp-overlay">\n'
    '  <div class="ssp-hdr">\n'
    '    <span class="ssp-hdr-title">Stock View</span>\n'
    '    <div class="ssp-search-wrap">\n'
    '      <input class="ssp-search" id="ssp-search" type="text" placeholder="Search ticker or company name..." autocomplete="off"\n'
    '        oninput="sspOnInput(this.value)" onkeydown="sspKeydown(event)">\n'
    '      <div class="ssp-dropdown" id="ssp-dropdown" style="display:none"></div>\n'
    '    </div>\n'
    '    <span class="ssp-hdr-stock" id="ssp-hdr-ticker"></span>\n'
    '    <span class="ssp-hdr-company" id="ssp-hdr-company"></span>\n'
    '    <button class="ssp-close-btn" onclick="closeStockView()" title="Close Stock View">&times;</button>\n'
    '  </div>\n'
    '  <div class="ssp-tbl-band" id="ssp-tbl-band"></div>\n'
    '  <div class="ssp-legend" id="ssp-legend">\n'
    '    <span class="ssp-legend-item"><span class="ssp-legend-dot" style="background:rgba(20,83,45,0.3)"></span>Green: S2 Probable + Setup Probable</span>\n'
    '    <span class="ssp-legend-item"><span class="ssp-legend-dot" style="background:rgba(180,100,0,0.25)"></span>Amber: S2 Plausible+ + PPI active</span>\n'
    '    <span class="ssp-legend-item"><span class="ssp-legend-dot" style="background:rgba(30,58,138,0.2)"></span>Blue: S1 Probable/Plausible</span>\n'
    '    <span class="ssp-legend-item"><span class="ssp-legend-dot" style="background:rgba(153,27,27,0.25)"></span>Red: NPI active / S3 or S4 Probable</span>\n'
    '    <span class="ssp-legend-item"><span class="ssp-legend-dot" style="background:#e5e7eb"></span>Neutral</span>\n'
    '  </div>\n'
    '  <div class="ssp-lower">\n'
    '    <div class="ssp-chart-pane">\n'
    '      <div class="ssp-chart-hdr" id="ssp-chart-hdr">Chart</div>\n'
    '      <div class="ssp-chart-body" id="ssp-chart-body">\n'
    '        <div class="ssp-chart-loading" id="ssp-chart-loading">Select a stock to view chart</div>\n'
    '        <canvas id="ssp-chart-canvas" style="display:none"></canvas>\n'
    '      </div>\n'
    '    </div>\n'
    '    <div class="ssp-cohort-pane">\n'
    '      <div class="ssp-cohort-hdr">Sector, industry, cohort and geography</div>\n'
    '      <div class="ssp-cohort-body" id="ssp-cohort-body">\n'
    '        <div class="ssp-cohort-col"><div class="ssp-cohort-col-hdr">Industry</div><div class="ssp-cohort-names" id="ssp-col-industry"></div></div>\n'
    '        <div class="ssp-cohort-col"><div class="ssp-cohort-col-hdr">Sector</div><div class="ssp-cohort-names" id="ssp-col-sector"></div></div>\n'
    '        <div class="ssp-cohort-col"><div class="ssp-cohort-col-hdr">Named cohort</div><div class="ssp-cohort-names" id="ssp-col-cohort"></div></div>\n'
    '        <div class="ssp-cohort-col"><div class="ssp-cohort-col-hdr">Geography</div><div class="ssp-cohort-names" id="ssp-col-geo"></div></div>\n'
    '      </div>\n'
    '    </div>\n'
    '  </div>\n'
    '</div>\n'
)

# ---------------------------------------------------------------------------
# JS module
# ---------------------------------------------------------------------------
SSP_JS = r"""
/* MD-V2-S63-STOCK-VIEW-MARKER */
(function(){
'use strict';

/* ---- state ---- */
var _sspOpen = false;
var _sspTicker = null;
var _sspDdSel = -1;
var _sspDdItems = [];

/* ---- price/filter lookup (cached) ---- */
function _sspPrices(){
  if(window._sspPriceMap) return window._sspPriceMap;
  var out={}, arr=(window.MASTER_DATA&&MASTER_DATA.prices)||[];
  for(var i=0;i<arr.length;i++) if(arr[i]&&arr[i].ticker) out[arr[i].ticker]=arr[i];
  return (window._sspPriceMap=out);
}
function _sspFilters(){
  if(window._sspFilterMap) return window._sspFilterMap;
  var out={}, arr=(window.MASTER_DATA&&MASTER_DATA.filters)||[];
  for(var i=0;i<arr.length;i++) if(arr[i]&&arr[i].ticker) out[arr[i].ticker]=arr[i];
  return (window._sspFilterMap=out);
}
function _sspUniverse(){
  if(window._sspUnivMap) return window._sspUnivMap;
  var out={}, arr=(window.MASTER_DATA&&MASTER_DATA.universe)||[];
  for(var i=0;i<arr.length;i++) if(arr[i]&&arr[i].ticker) out[arr[i].ticker]=arr[i];
  return (window._sspUnivMap=out);
}

/* ---- cohort index (built once from SSP_COHORTS) ---- */
var _sspCohortBuilt = false;
var _sspTickerToD = {};    // ticker -> [{id,name,members}]
var _sspIndustryMap = {};  // industry -> [{ticker,company}]
var _sspSectorMap   = {};  // sector   -> [{ticker,company}]
var _sspGeoMap      = {};  // suffix   -> [{ticker,company}]

function _sspBuildCohortIndex(){
  if(_sspCohortBuilt) return;
  _sspCohortBuilt = true;

  /* Section D cohorts */
  var co = window.SSP_COHORTS;
  if(co && co.section_d_cohorts){
    var dList = co.section_d_cohorts;
    for(var i=0;i<dList.length;i++){
      var d = dList[i];
      if(!d.members) continue;
      for(var j=0;j<d.members.length;j++){
        var tk = d.members[j].ticker;
        if(!_sspTickerToD[tk]) _sspTickerToD[tk]=[];
        _sspTickerToD[tk].push({id:d.id, name:d.name, members:d.members});
      }
    }
  }

  /* Industry / sector / geo maps from prices */
  var prices = _sspPrices();
  var univ   = _sspUniverse();
  for(var t in prices){
    var p = prices[t], u = univ[t];
    var company = (p&&p.company_name) || (u&&u.company_name) || t;
    var ind = p&&p.industry, sec = p&&p.sector;
    if(ind){ if(!_sspIndustryMap[ind]) _sspIndustryMap[ind]=[]; _sspIndustryMap[ind].push({ticker:t,company:company}); }
    if(sec){ if(!_sspSectorMap[sec])   _sspSectorMap[sec]=[];   _sspSectorMap[sec].push({ticker:t,company:company}); }
    /* geo from ticker suffix */
    var parts = t.split('-');
    var suffix = parts.length>1 ? parts[parts.length-1] : 'XX';
    if(!_sspGeoMap[suffix]) _sspGeoMap[suffix]=[];
    _sspGeoMap[suffix].push({ticker:t,company:company});
  }
}

/* ---- open / close ---- */
window.openStockView = function(initialTicker){
  _sspBuildCohortIndex();
  document.getElementById('ssp-overlay').classList.add('open');
  _sspOpen = true;
  if(typeof closeChart === 'function') closeChart();
  document.body.classList.add('ssp-open');
  if(initialTicker){
    document.getElementById('ssp-search').value = initialTicker;
    sspSetStock(initialTicker);
  } else {
    document.getElementById('ssp-search').focus();
  }
};
window.closeStockView = function(){
  document.getElementById('ssp-overlay').classList.remove('open');
  _sspOpen = false;
  document.body.classList.remove('ssp-open');
  _sspHideDd();
};

/* ---- search ---- */
window.sspOnInput = function(val){
  val = val.trim();
  if(!val){ _sspHideDd(); return; }
  var q = val.toLowerCase();
  var univ = (window.MASTER_DATA&&MASTER_DATA.universe)||[];
  var matches = [];
  for(var i=0;i<univ.length&&matches.length<20;i++){
    var s = univ[i];
    if(!s) continue;
    var tk = (s.ticker||'').toLowerCase();
    var cn = (s.company_name||'').toLowerCase();
    if(tk.indexOf(q)===0 || cn.indexOf(q)===0) matches.push(s);
    else if(tk.indexOf(q)>0 || cn.indexOf(q)>0) matches.push(s);
  }
  matches = matches.slice(0,15);
  _sspDdItems = matches;
  _sspDdSel = -1;
  _sspShowDd(matches);
};
window.sspKeydown = function(e){
  var dd = document.getElementById('ssp-dropdown');
  var items = dd.querySelectorAll('.ssp-dd-item');
  if(e.key==='ArrowDown'){ e.preventDefault(); _sspDdSel=Math.min(_sspDdSel+1,items.length-1); _sspHighlightDd(items); }
  else if(e.key==='ArrowUp'){ e.preventDefault(); _sspDdSel=Math.max(_sspDdSel-1,-1); _sspHighlightDd(items); }
  else if(e.key==='Enter'){
    e.preventDefault();
    if(_sspDdSel>=0 && _sspDdItems[_sspDdSel]){ sspSelectStock(_sspDdItems[_sspDdSel].ticker); }
    else if(_sspDdItems.length>0){ sspSelectStock(_sspDdItems[0].ticker); }
  }
  else if(e.key==='Escape'){ _sspHideDd(); }
};
function _sspShowDd(matches){
  var dd = document.getElementById('ssp-dropdown');
  if(!matches.length){ dd.style.display='none'; return; }
  var h='';
  for(var i=0;i<matches.length;i++){
    h+='<div class="ssp-dd-item" onclick="sspSelectStock(\''+_sspEsc(matches[i].ticker)+'\')">'+
       '<span class="ssp-dd-ticker">'+_sspHtml(matches[i].ticker)+'</span>'+
       _sspHtml(matches[i].company_name||'')+'</div>';
  }
  dd.innerHTML=h;
  dd.style.display='block';
}
function _sspHighlightDd(items){
  for(var i=0;i<items.length;i++) items[i].classList.toggle('active',i===_sspDdSel);
}
function _sspHideDd(){
  var dd=document.getElementById('ssp-dropdown');
  if(dd){ dd.style.display='none'; }
}
window.sspSelectStock = function(ticker){
  _sspHideDd();
  var univ=_sspUniverse();
  var u=univ[ticker];
  document.getElementById('ssp-search').value = ticker + (u&&u.company_name?' — '+u.company_name:'');
  sspSetStock(ticker);
};

/* ---- set stock (main render entry point) ---- */
function sspSetStock(ticker){
  _sspTicker = ticker;
  var prices  = _sspPrices();
  var filters = _sspFilters();
  var p = prices[ticker]  || {};
  var f = filters[ticker] || {};
  var md2 = f.md_v2 || {};

  /* update header */
  var univ = _sspUniverse();
  var u = univ[ticker]||{};
  var company = p.company_name || u.company_name || ticker;
  document.getElementById('ssp-hdr-ticker').textContent = ticker;
  document.getElementById('ssp-hdr-company').textContent = company;

  sspRenderTable(ticker, p, md2);
  sspRenderCohort(ticker, p);
  sspRenderChart(ticker, company);
}

/* ---- rating helpers ---- */
var RATING_RANK = {'Qualified':6,'Probable':5,'Plausible':3,'Possible':2,'None':1};
function _sspStageRating(md2, key){ var s=md2[key]; return s?s.rating||'None':'None'; }
function _sspStageCount(md2, key){ var s=md2[key]; return s?s.count||0:0; }
function _sspPreRating(md2, patKey){
  var pi=md2.pre_indicators; if(!pi) return 'None';
  var r=pi[patKey]; return r?r.rating||'None':'None';
}
function _sspPreCount(md2, patKey){
  var pi=md2.pre_indicators; if(!pi) return {c:0,t:0};
  var r=pi[patKey]; return r?{c:r.count||0,t:r.total||0}:{c:0,t:0};
}
function _sspTestRating(md2, patKey){
  var tk=md2.tests; if(!tk) return 'None';
  var r=tk[patKey]; return r?r.rating||'None':'None';
}
function _sspTestCount(md2, patKey){
  var tk=md2.tests; if(!tk) return {c:0,t:0};
  var r=tk[patKey]; return r?{c:r.count||0,t:r.total||0}:{c:0,t:0};
}
/* Speculative Bets: pick higher rating between s3 and s4 */
function _sspSbRating(md2){
  var r3=_sspTestRating(md2,'speculative_bet_s3');
  var r4=_sspTestRating(md2,'speculative_bet_s4');
  return (RATING_RANK[r3]||0)>=(RATING_RANK[r4]||0)?r3:r4;
}
function _sspSbCount(md2){
  var c3=_sspTestCount(md2,'speculative_bet_s3');
  var c4=_sspTestCount(md2,'speculative_bet_s4');
  return (RATING_RANK[_sspTestRating(md2,'speculative_bet_s3')]||0)>=(RATING_RANK[_sspTestRating(md2,'speculative_bet_s4')]||0)?c3:c4;
}

/* ---- pill + pips ---- */
function _sspPillCls(rating){
  if(rating==='Probable'||rating==='Probable Late'||rating==='Probable Early') return 'ssp-pill-prob';
  if(rating==='Plausible') return 'ssp-pill-pla';
  if(rating==='Possible')  return 'ssp-pill-pos';
  if(rating==='Qualified') return 'ssp-pill-qual';
  return 'ssp-pill-none';
}
function _sspPillLabel(rating){
  if(rating==='Probable Late'||rating==='Probable Early') return 'Probable';
  return rating||'None';
}
function _sspPill(rating){
  var cls=_sspPillCls(rating);
  return '<span class="ssp-pill '+cls+'">'+_sspHtml(_sspPillLabel(rating))+'</span>';
}
function _sspPipsCls(rating){
  if(rating==='Probable'||rating==='Probable Late'||rating==='Probable Early') return 'on-prob';
  if(rating==='Plausible') return 'on-pla';
  if(rating==='Possible')  return 'on-pos';
  if(rating==='Qualified') return 'on-blue';
  return 'on';
}
function _sspPips(count, total, rating){
  if(!total) return '';
  var on=_sspPipsCls(rating);
  var s='<span class="ssp-pips">';
  for(var i=0;i<total;i++) s+='<span class="ssp-pip'+(i<count?' '+on:'')+'"></span>';
  s+='</span>';
  return s;
}

/* ---- row colour ---- */
function _sspRowCls(md2){
  var s2r = _sspStageRating(md2,'stage_2');
  var s1r = _sspStageRating(md2,'stage_1');
  var s3r = _sspStageRating(md2,'stage_3');
  var s4r = _sspStageRating(md2,'stage_4');
  var npiR= _sspPreRating(md2,'collapsing');
  var rankOf = function(r){ return RATING_RANK[r]||0; };
  /* Red: NPI collapsing or S3/S4 Probable */
  if(rankOf(npiR)>=2 || s3r==='Probable' || s4r==='Probable') return 'ssp-row-red';
  /* Green: S2 Probable AND any setup/test probable */
  if(s2r==='Probable'){
    var setups=['healthy_retest','probing_bet_s1','probing_bet_s2','vcp_deploy_s2'];
    for(var si=0;si<setups.length;si++) if(_sspTestRating(md2,setups[si])==='Probable') return 'ssp-row-green';
    if(_sspSbRating(md2)==='Probable') return 'ssp-row-green';
  }
  /* Amber: S2 Plausible+ AND PPI active */
  if(rankOf(s2r)>=3){
    if(rankOf(_sspPreRating(md2,'pulling_back_uptrend'))>=2||rankOf(_sspPreRating(md2,'basing'))>=2) return 'ssp-row-amber';
  }
  /* Blue: S1 Probable or Plausible */
  if(s1r==='Probable'||s1r==='Probable Late'||s1r==='Probable Early'||s1r==='Plausible') return 'ssp-row-blue';
  return '';
}

/* ---- render table ---- */
function sspRenderTable(ticker, p, md2){
  var band = document.getElementById('ssp-tbl-band');
  if(!band) return;

  var price = p.price!=null ? p.price.toFixed(2) : '—';
  var pbPct = p.recent_pullback_pct!=null ? Math.round(p.recent_pullback_pct*100)+'%' : '—';
  var company = p.company_name || ticker;
  var rowCls = _sspRowCls(md2);

  /* stage data */
  var s1r=_sspStageRating(md2,'stage_1'), s1c=_sspStageCount(md2,'stage_1');
  var s2r=_sspStageRating(md2,'stage_2'), s2c=_sspStageCount(md2,'stage_2');
  var s3r=_sspStageRating(md2,'stage_3'), s3c=_sspStageCount(md2,'stage_3');
  var s4r=_sspStageRating(md2,'stage_4'), s4c=_sspStageCount(md2,'stage_4');

  /* PPI */
  var pbrO=_sspPreRating(md2,'pulling_back_uptrend'), pbrC=_sspPreCount(md2,'pulling_back_uptrend');
  var pbsO=_sspPreRating(md2,'basing'),               pbsC=_sspPreCount(md2,'basing');

  /* NPI */
  var npiO=_sspPreRating(md2,'collapsing'), npiC=_sspPreCount(md2,'collapsing');

  /* Setups/Tests */
  var hrO=_sspTestRating(md2,'healthy_retest'),   hrC=_sspTestCount(md2,'healthy_retest');
  var pb1O=_sspTestRating(md2,'probing_bet_s1'),  pb1C=_sspTestCount(md2,'probing_bet_s1');
  var pb2O=_sspTestRating(md2,'probing_bet_s2'),  pb2C=_sspTestCount(md2,'probing_bet_s2');
  var sbO=_sspSbRating(md2),                      sbC=_sspSbCount(md2);
  var vcpO=_sspTestRating(md2,'vcp_deploy_s2'),   vcpC=_sspTestCount(md2,'vcp_deploy_s2');

  /* col widths: 4 fixed + 12 pair groups (each = 2 cols = rating+score) */
  /* Total 28 cols. At 1920px body - 28px padding = 1892px / 28 = ~67.6px each data col */
  /* Fixed: Name=8%, Ticker used inside name cell, Price=3.2%, PB=3.8% */
  /* 24 data cols (12 pairs × 2): each = (100-8-3.2-3.8)/24 = 85/24 = 3.54% */
  var cg = '<colgroup>';
  cg += '<col style="width:8%">';   /* name */
  cg += '<col style="width:3.2%">'; /* price */
  cg += '<col style="width:3.8%">'; /* pullback */
  var dataPct = '3.54%';
  for(var ci=0;ci<24;ci++) cg += '<col style="width:'+dataPct+'">';
  cg += '</colgroup>';

  /* Group header row */
  var gh = '<tr>';
  gh += '<th class="ssp-gh" colspan="3"></th>';
  gh += '<th class="ssp-gh ssp-gs-stages" colspan="8" style="color:#1e3a5f;border-top:2px solid #1e3a5f">STAGES</th>';
  gh += '<th class="ssp-gh ssp-gs-ppi" colspan="4" style="color:#0a2a20;border-top:2px solid #0f6e56">POSITIVE PRE-SETUP INDICATORS</th>';
  gh += '<th class="ssp-gh ssp-gs-npi" colspan="2" style="color:#3a1010;border-top:2px solid #a32d2d">NEGATIVE PRE-SETUP INDICATORS</th>';
  gh += '<th class="ssp-gh ssp-gs-setups" colspan="10" style="color:#2e1a5e;border-top:2px solid #4c1d95">SETUPS &amp; TESTS</th>';
  gh += '</tr>';

  /* Column header row — sub-group labels */
  var ch = '<tr>';
  ch += '<th class="ssp-ch" colspan="3"></th>';
  ch += '<th class="ssp-ch ssp-gs-stages" colspan="2">Stage 1 — Basing</th>';
  ch += '<th class="ssp-ch ssp-pair-div" colspan="2">Stage 2 — Uptrend</th>';
  ch += '<th class="ssp-ch ssp-pair-div" colspan="2">Stage 3 — Topping</th>';
  ch += '<th class="ssp-ch ssp-pair-div" colspan="2">Stage 4 — Decline</th>';
  ch += '<th class="ssp-ch ssp-gs-ppi" colspan="2">Pulling back within MT/LT uptrend</th>';
  ch += '<th class="ssp-ch ssp-pair-div" colspan="2">Basing in a MT/LT uptrend</th>';
  ch += '<th class="ssp-ch ssp-gs-npi" colspan="2">Collapsing patterns</th>';
  ch += '<th class="ssp-ch ssp-gs-setups" colspan="2">Healthy Retest of Moving Average</th>';
  ch += '<th class="ssp-ch ssp-pair-div" colspan="2">Probing Bet — Stage 1</th>';
  ch += '<th class="ssp-ch ssp-pair-div" colspan="2">Probing Bet — Stage 2</th>';
  ch += '<th class="ssp-ch ssp-pair-div" colspan="2">Speculative Bets</th>';
  ch += '<th class="ssp-ch ssp-pair-div" colspan="2">Healthy VCP</th>';
  ch += '</tr>';

  /* Rating/Score column header row */
  var rh = '<tr>';
  rh += '<th class="ssp-ch" style="text-align:left">Name</th>';
  rh += '<th class="ssp-ch">Price</th>';
  rh += '<th class="ssp-ch">Pullback</th>';
  /* 12 pairs */
  var pairHdrs = [
    ['ssp-gs-stages','Rating','Score'],
    ['ssp-pair-div','Rating','Score'],
    ['ssp-pair-div','Rating','Score'],
    ['ssp-pair-div','Rating','Score'],
    ['ssp-gs-ppi','Rating','Score'],
    ['ssp-pair-div','Rating','Score'],
    ['ssp-gs-npi','Rating','Score'],
    ['ssp-gs-setups','Rating','Score'],
    ['ssp-pair-div','Rating','Score'],
    ['ssp-pair-div','Rating','Score'],
    ['ssp-pair-div','Rating','Score'],
    ['ssp-pair-div','Rating','Score']
  ];
  for(var pi=0;pi<pairHdrs.length;pi++){
    rh += '<th class="ssp-ch '+pairHdrs[pi][0]+'">'+pairHdrs[pi][1]+'</th>';
    rh += '<th class="ssp-ch">'+pairHdrs[pi][2]+'</th>';
  }
  rh += '</tr>';

  /* Data row */
  var dr = '<tr class="'+rowCls+'">';
  dr += '<td class="ssp-name-cell ssp-gs-stages" style="border-left:none"><span>'+_sspHtml(company)+'</span><span class="ssp-ticker">'+_sspHtml(ticker)+'</span></td>';
  dr += '<td class="ssp-price">'+_sspHtml(price)+'</td>';
  dr += '<td class="ssp-pb">'+_sspHtml(pbPct)+'</td>';

  /* Stage 1 */
  dr += '<td class="ssp-gs-stages">'+_sspPill(s1r)+'</td>';
  dr += '<td>'+_sspPips(s1c,8,s1r)+'</td>';
  /* Stage 2 */
  dr += '<td class="ssp-pair-div">'+_sspPill(s2r)+'</td>';
  dr += '<td>'+_sspPips(s2c,10,s2r)+'</td>';
  /* Stage 3 */
  dr += '<td class="ssp-pair-div">'+_sspPill(s3r)+'</td>';
  dr += '<td>'+_sspPips(s3c,10,s3r)+'</td>';
  /* Stage 4 */
  dr += '<td class="ssp-pair-div">'+_sspPill(s4r)+'</td>';
  dr += '<td>'+_sspPips(s4c,7,s4r)+'</td>';
  /* PPI pull back */
  dr += '<td class="ssp-gs-ppi">'+_sspPill(pbrO)+'</td>';
  dr += '<td>'+_sspPips(pbrC.c,pbrC.t,pbrO)+'</td>';
  /* PPI basing */
  dr += '<td class="ssp-pair-div">'+_sspPill(pbsO)+'</td>';
  dr += '<td>'+_sspPips(pbsC.c,pbsC.t,pbsO)+'</td>';
  /* NPI collapsing */
  dr += '<td class="ssp-gs-npi">'+_sspPill(npiO)+'</td>';
  dr += '<td>'+_sspPips(npiC.c,npiC.t,npiO)+'</td>';
  /* Healthy Retest */
  dr += '<td class="ssp-gs-setups">'+_sspPill(hrO)+'</td>';
  dr += '<td>'+_sspPips(hrC.c,hrC.t,hrO)+'</td>';
  /* PB S1 */
  dr += '<td class="ssp-pair-div">'+_sspPill(pb1O)+'</td>';
  dr += '<td>'+_sspPips(pb1C.c,pb1C.t,pb1O)+'</td>';
  /* PB S2 */
  dr += '<td class="ssp-pair-div">'+_sspPill(pb2O)+'</td>';
  dr += '<td>'+_sspPips(pb2C.c,pb2C.t,pb2O)+'</td>';
  /* Spec Bets */
  dr += '<td class="ssp-pair-div">'+_sspPill(sbO)+'</td>';
  dr += '<td>'+_sspPips(sbC.c,sbC.t,sbO)+'</td>';
  /* Healthy VCP */
  dr += '<td class="ssp-pair-div">'+_sspPill(vcpO)+'</td>';
  dr += '<td>'+_sspPips(vcpC.c,vcpC.t,vcpO)+'</td>';

  dr += '</tr>';

  band.innerHTML = '<div class="ssp-tbl-outer"><table class="ssp-tbl">'+cg+'<thead>'+gh+ch+rh+'</thead><tbody>'+dr+'</tbody></table></div>';
}

/* ---- render cohort tile ---- */
function sspRenderCohort(ticker, p){
  var industry = p.industry||'';
  var sector   = p.sector||'';

  /* industry peers */
  var indList = (_sspIndustryMap[industry]||[]).slice().sort(function(a,b){return a.company<b.company?-1:1;});
  var secList = (_sspSectorMap[sector]||[]).slice().sort(function(a,b){return a.company<b.company?-1:1;});

  /* named cohort peers */
  var cohortHtml = '';
  /* Section D */
  var dCohorts = _sspTickerToD[ticker]||[];
  if(dCohorts.length){
    for(var di=0;di<dCohorts.length;di++){
      var dc = dCohorts[di];
      cohortHtml += '<span class="ssp-cohort-group-hdr">'+_sspHtml(dc.id+' — '+dc.name)+'</span>';
      var dm = dc.members.slice().sort(function(a,b){return a.company<b.company?-1:1;});
      for(var dj=0;dj<dm.length;dj++){
        var isSelf = dm[dj].ticker===ticker;
        cohortHtml += '<span class="ssp-cohort-name'+(isSelf?' self':'')+'" onclick="sspSelectStock(\''+_sspEsc(dm[dj].ticker)+'\')">'+_sspHtml(dm[dj].company||dm[dj].ticker)+'</span>';
      }
    }
  }
  /* Thematic (from SSP_COHORTS.tickers) */
  var co = window.SSP_COHORTS;
  if(co && co.tickers && co.tickers[ticker]){
    var th = co.tickers[ticker];
    for(var ti2=0;ti2<th.length;ti2++){
      var tc = th[ti2];
      cohortHtml += '<span class="ssp-cohort-group-hdr">'+_sspHtml(tc.cohort||(tc.sub_cohort||''))+'</span>';
      if(tc.members){
        var tm = tc.members.slice().sort(function(a,b){return a.company<b.company?-1:1;});
        for(var tj=0;tj<tm.length;tj++){
          var isSelf2 = tm[tj].ticker===ticker;
          cohortHtml += '<span class="ssp-cohort-name'+(isSelf2?' self':'')+'" onclick="sspSelectStock(\''+_sspEsc(tm[tj].ticker)+'\')">'+_sspHtml(tm[tj].company||tm[tj].ticker)+'</span>';
        }
      }
    }
  }
  if(!cohortHtml) cohortHtml = '<span class="ssp-cohort-name" style="color:#aaa;cursor:default">No named cohort found</span>';

  /* Geography */
  var parts = ticker.split('-');
  var suffix = parts.length>1 ? parts[parts.length-1] : 'XX';
  var geoList = (_sspGeoMap[suffix]||[]).slice().sort(function(a,b){return a.company<b.company?-1:1;});
  var GEO_NAMES = {GB:'United Kingdom',DE:'Germany',SE:'Sweden',FR:'France',IT:'Italy',CH:'Switzerland',NO:'Norway',ES:'Spain',NL:'Netherlands',DK:'Denmark',BE:'Belgium',FI:'Finland',AT:'Austria',PL:'Poland',GR:'Greece',PT:'Portugal',IE:'Ireland',HU:'Hungary'};
  var geoLabel = GEO_NAMES[suffix]||suffix;

  function _listHtml(arr, selfTicker){
    var h='';
    for(var i=0;i<arr.length;i++){
      var isSelf = arr[i].ticker===selfTicker;
      h+='<span class="ssp-cohort-name'+(isSelf?' self':'')+'" onclick="sspSelectStock(\''+_sspEsc(arr[i].ticker)+'\')">'+_sspHtml(arr[i].company||arr[i].ticker)+'</span>';
    }
    return h||'<span class="ssp-cohort-name" style="color:#aaa;cursor:default">—</span>';
  }

  document.getElementById('ssp-col-industry').innerHTML = _listHtml(indList, ticker);
  document.getElementById('ssp-col-sector').innerHTML   = _listHtml(secList, ticker);
  document.getElementById('ssp-col-cohort').innerHTML   = cohortHtml;
  /* Geography column: add header with country name */
  var geoEl = document.getElementById('ssp-col-geo');
  /* update the column header to show country name */
  var geoColHdr = geoEl.closest('.ssp-cohort-col').querySelector('.ssp-cohort-col-hdr');
  if(geoColHdr) geoColHdr.textContent = 'Geography — '+geoLabel+' ('+suffix+')';
  geoEl.innerHTML = _listHtml(geoList, ticker);
}

/* ---- render chart ---- */
function sspRenderChart(ticker, company){
  var body = document.getElementById('ssp-chart-body');
  var loading = document.getElementById('ssp-chart-loading');
  var canvas  = document.getElementById('ssp-chart-canvas');
  if(!body||!loading||!canvas) return;

  /* Update chart header */
  var hdr = document.getElementById('ssp-chart-hdr');
  if(hdr) hdr.textContent = ticker + (company?' — '+company:'');

  loading.style.display='block';
  loading.textContent='Loading chart data for '+ticker+'...';
  canvas.style.display='none';

  loadChartData(ticker, function(data){
    if(!data){
      loading.textContent='No chart data available for '+ticker;
      return;
    }
    loading.style.display='none';
    canvas.style.display='block';

    /* Size canvas to container */
    var rect = body.getBoundingClientRect();
    var W = Math.floor(rect.width) - 12;
    var H = Math.floor(rect.height) - 12;
    if(W<100||H<60){ W=600; H=320; }
    canvas.width  = W;
    canvas.height = H;

    _sspDrawChart(data, canvas, W, H, ticker);
  });
}

function _sspDrawChart(data, canvas, W, H, ticker){
  var ctx = canvas.getContext('2d');
  if(!ctx) return;
  ctx.clearRect(0,0,W,H);

  /* Use same zoom/filter as user last used (chartZoom global) */
  var zoom = (typeof chartZoom !== 'undefined') ? chartZoom : '1Y';
  var cutMs = _sspZoomCutMs(zoom);
  var rows = data.filter(function(r){ return !cutMs || (new Date(r.d)).getTime() >= cutMs; });
  if(!rows.length) rows = data;

  var PAD = {t:12,r:16,b:28,l:52};
  var cW = W - PAD.l - PAD.r;
  var cH = H - PAD.t - PAD.b;

  /* Price range */
  var minP=Infinity, maxP=-Infinity;
  for(var i=0;i<rows.length;i++){
    var r=rows[i];
    if(r.l!=null&&r.l<minP) minP=r.l;
    if(r.h!=null&&r.h>maxP) maxP=r.h;
    var mas=[r.ma20,r.ma50,r.ma150,r.ma200];
    for(var m=0;m<mas.length;m++) if(mas[m]!=null){if(mas[m]<minP)minP=mas[m];if(mas[m]>maxP)maxP=mas[m];}
  }
  if(minP===Infinity||maxP===-Infinity){ctx.fillStyle='#999';ctx.font='11px sans-serif';ctx.fillText('No data',W/2-20,H/2);return;}
  var pRange = maxP-minP;
  if(pRange<0.001) pRange=0.001;
  var minY=minP - pRange*0.04;
  var maxY=maxP + pRange*0.04;
  var yRange=maxY-minY;

  function xOf(i){ return PAD.l + (i/(rows.length-1||1))*cW; }
  function yOf(v){ return PAD.t + (1-(v-minY)/yRange)*cH; }

  /* Background */
  ctx.fillStyle='#fbfaf5';
  ctx.fillRect(0,0,W,H);

  /* Grid lines */
  ctx.strokeStyle='#e8e4d8'; ctx.lineWidth=1;
  var nLines=4;
  for(var gi=0;gi<=nLines;gi++){
    var yv=minY+yRange*(gi/nLines);
    var yp=yOf(yv);
    ctx.beginPath(); ctx.moveTo(PAD.l,yp); ctx.lineTo(W-PAD.r,yp); ctx.stroke();
    ctx.fillStyle='#888'; ctx.font='9px sans-serif'; ctx.textAlign='right';
    ctx.fillText(yv>=1000?Math.round(yv):yv.toFixed(1), PAD.l-4, yp+3);
  }

  /* OHLC bars */
  var bw = Math.max(1, Math.floor(cW/rows.length*0.6));
  for(var bi=0;bi<rows.length;bi++){
    var br=rows[bi];
    if(br.o==null||br.c==null) continue;
    var bx=xOf(bi);
    var isUp = br.c>=br.o;
    ctx.fillStyle=isUp?'rgba(15,110,86,0.7)':'rgba(163,45,45,0.7)';
    ctx.strokeStyle=isUp?'rgba(15,110,86,0.9)':'rgba(163,45,45,0.9)';
    ctx.lineWidth=0.5;
    /* Wick */
    if(br.h!=null&&br.l!=null){
      ctx.beginPath(); ctx.moveTo(bx,yOf(br.h)); ctx.lineTo(bx,yOf(br.l)); ctx.stroke();
    }
    /* Body */
    var yOpen=yOf(br.o), yClose=yOf(br.c);
    var by=Math.min(yOpen,yClose), bh=Math.max(1,Math.abs(yOpen-yClose));
    ctx.fillRect(bx-bw/2, by, bw, bh);
  }

  /* MA lines */
  var maLines=[
    {key:'ma20',  color:'rgba(100,100,200,0.7)', lw:1},
    {key:'ma50',  color:'rgba(200,140,0,0.85)',  lw:1.2},
    {key:'ma150', color:'rgba(0,160,100,0.85)',  lw:1.4},
    {key:'ma200', color:'rgba(180,0,0,0.85)',    lw:1.6}
  ];
  for(var ml=0;ml<maLines.length;ml++){
    var mdef=maLines[ml]; var k=mdef.key;
    ctx.strokeStyle=mdef.color; ctx.lineWidth=mdef.lw;
    ctx.beginPath(); var started=false;
    for(var mi=0;mi<rows.length;mi++){
      var mv=rows[mi][k];
      if(mv==null){ started=false; continue; }
      if(!started){ ctx.moveTo(xOf(mi),yOf(mv)); started=true; }
      else ctx.lineTo(xOf(mi),yOf(mv));
    }
    ctx.stroke();
  }

  /* X-axis tick labels (sparse) */
  ctx.fillStyle='#888'; ctx.font='8px sans-serif'; ctx.textAlign='center';
  var tickStep=Math.max(1,Math.floor(rows.length/6));
  for(var xi=0;xi<rows.length;xi+=tickStep){
    var d=rows[xi].d; if(!d) continue;
    var label=d.slice(0,7); /* YYYY-MM */
    ctx.fillText(label, xOf(xi), H-PAD.b+12);
  }

  /* Ticker label */
  ctx.fillStyle='rgba(0,0,0,0.25)'; ctx.font='bold 11px sans-serif'; ctx.textAlign='left';
  ctx.fillText(ticker, PAD.l+4, PAD.t+12);
}

function _sspZoomCutMs(zoom){
  var now=Date.now();
  var map={'1M':30,'3M':91,'6M':183,'12M':365,'2Y':730,'3Y':1095,'5Y':1825};
  var days=map[zoom];
  if(!days) return 0;
  return now - days*86400000;
}

/* ---- util ---- */
function _sspHtml(s){
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
function _sspEsc(s){
  return String(s).replace(/'/g,"\\'").replace(/"/g,'&quot;');
}

/* Close on Escape key when overlay is open */
document.addEventListener('keydown', function(e){
  if(e.key==='Escape' && _sspOpen) closeStockView();
});

/* Close dropdown on click outside */
document.addEventListener('click', function(e){
  if(!e.target.closest('#ssp-search') && !e.target.closest('#ssp-dropdown')){
    _sspHideDd();
  }
});

})();
/* MD-V2-S63-STOCK-VIEW-MARKER-END */
"""


# ---------------------------------------------------------------------------
# Cohort data injection into data_js (Python-level)
# ---------------------------------------------------------------------------
OLD_CHART_REGISTRY = (
    '    data_js += "var CHART_REGISTRY = {};\\"\\n"\n'
    '    data_js += "var PB_STAGEINFO_COUNT = 0;\\"\\n"'
)

# Try alternate quoting (the actual file uses different quoting)
OLD_CHART_REGISTRY_ALT = (
    '    data_js += "var CHART_REGISTRY = {};\\"\\n"\n'
)


def main():
    with open(TARGET, "rb") as f:
        raw = f.read()
    src = raw.decode("utf-8")
    had_crlf = "\r\n" in src
    if had_crlf:
        src = src.replace("\r\n", "\n")

    if MARKER in src:
        print("[idempotency] marker '{}' already present; no-op.".format(MARKER))
        return

    # ------------------------------------------------------------------ #
    # 1.  Cohort data embedding in data_js                                 #
    # ------------------------------------------------------------------ #
    # Find the CHART_REGISTRY line (exact string from file)
    OLD_COHORT_ANCHOR = '    data_js += "var CHART_REGISTRY = {};\\"\\n"\n'
    if OLD_COHORT_ANCHOR not in src:
        # try raw string variant
        OLD_COHORT_ANCHOR = '    data_js += "var CHART_REGISTRY = {};"+"\\n"\n'
    if OLD_COHORT_ANCHOR not in src:
        # search more broadly
        idx = src.find('var CHART_REGISTRY = {}')
        if idx == -1:
            sys.stderr.write("ERROR: Cannot find CHART_REGISTRY anchor in data_js section.\n")
            sys.exit(2)
        # find the line start
        line_start = src.rfind('\n', 0, idx) + 1
        line_end   = src.find('\n', idx) + 1
        OLD_COHORT_ANCHOR = src[line_start:line_end]
        print("[info] Using dynamic CHART_REGISTRY anchor: {}".format(repr(OLD_COHORT_ANCHOR[:80])))

    NEW_COHORT_ANCHOR = OLD_COHORT_ANCHOR + (
        "    # MD-V2-S63: embed Section D cohort data for Stock View page\n"
        "    _cohorts_path = COWORK_ROOT / \"databases\" / \"data\" / \"cohorts-v2.json\"\n"
        "    if _cohorts_path.exists():\n"
        "        _cohorts_raw = safe_json_load(_cohorts_path)\n"
        "        data_js += \"var SSP_COHORTS = \" + json.dumps(_cohorts_raw, separators=(',', ':')) + \";\\n\"\n"
        "    else:\n"
        "        data_js += \"var SSP_COHORTS = null;\\n\"\n"
    )
    src = must_replace(src, OLD_COHORT_ANCHOR, NEW_COHORT_ANCHOR, "CHART_REGISTRY anchor")

    # ------------------------------------------------------------------ #
    # 2.  CSS block (before MD-V2-REMOVE-SUMMARY-MARKER)                  #
    # ------------------------------------------------------------------ #
    # Find the end of the CSS block
    OLD_CSS_END_SEARCH = '/* MD-V2-REMOVE-SUMMARY-MARKER'
    idx_css = src.find(OLD_CSS_END_SEARCH)
    if idx_css == -1:
        sys.stderr.write("ERROR: Cannot find CSS end marker '/* MD-V2-REMOVE-SUMMARY-MARKER'.\n")
        sys.exit(2)
    # Find line start
    line_start = src.rfind('\n', 0, idx_css) + 1
    OLD_CSS_END = src[line_start:idx_css + len(OLD_CSS_END_SEARCH)]
    NEW_CSS_END = SSP_CSS + "\n" + OLD_CSS_END
    src = must_replace(src, OLD_CSS_END, NEW_CSS_END, "CSS end marker")

    # ------------------------------------------------------------------ #
    # 3.  HTML overlay div (before chart-panel div)                        #
    # ------------------------------------------------------------------ #
    OLD_CHART_PANEL_HTML = (
        "'<div class=\"chart-panel\" id=\"chart-panel\">\\n'\n"
        "        '  <div id=\"chart-container\" style=\"width:100%;min-height:calc(100vh - 200px)\">Click a stock row to view chart</div>\\n'\n"
        "        '</div>\\n'"
    )
    NEW_CHART_PANEL_HTML = (
        "'" + SSP_HTML.replace("'", "\\'").replace("\n", "\\n'\n        '") + "'\n"
        "        '<div class=\"chart-panel\" id=\"chart-panel\">\\n'\n"
        "        '  <div id=\"chart-container\" style=\"width:100%;min-height:calc(100vh - 200px)\">Click a stock row to view chart</div>\\n'\n"
        "        '</div>\\n'"
    )
    src = must_replace(src, OLD_CHART_PANEL_HTML, NEW_CHART_PANEL_HTML, "chart-panel HTML anchor")

    # ------------------------------------------------------------------ #
    # 4.  JS module (before renderTab("mm99"))                             #
    # ------------------------------------------------------------------ #
    OLD_JS_END = 'renderTab("mm99");\n"""'
    NEW_JS_END = SSP_JS + '\nrenderTab("mm99");\n"""'
    src = must_replace(src, OLD_JS_END, NEW_JS_END, "JS end anchor (renderTab mm99)")

    # ------------------------------------------------------------------ #
    # 5.  Header button (after SOI List button)                            #
    # ------------------------------------------------------------------ #
    OLD_SOI_BTN = (
        "'      <a class=\"ctrl-btn\" href=\"../../databases/soi-list.html\" "
        "title=\"Standardised Stocks of Interest list\">SOI List</a>\\n'"
    )
    NEW_SOI_BTN = (
        "'      <a class=\"ctrl-btn\" href=\"../../databases/soi-list.html\" "
        "title=\"Standardised Stocks of Interest list\">SOI List</a>\\n'\n"
        "        '      <button class=\"ctrl-btn ssp-btn\" onclick=\"openStockView()\" "
        "title=\"Single stock view — all ratings at a glance\">Stock View</button>\\n'"
    )
    src = must_replace(src, OLD_SOI_BTN, NEW_SOI_BTN, "SOI List button anchor")

    # ------------------------------------------------------------------ #
    # Write output                                                          #
    # ------------------------------------------------------------------ #
    if had_crlf:
        src = src.replace("\n", "\r\n")
    out = src.encode("utf-8")
    md5_before = hashlib.md5(raw).hexdigest()
    md5_after  = hashlib.md5(out).hexdigest()
    print("MD5 before: {}".format(md5_before))
    print("MD5 after:  {}".format(md5_after))

    with open(TARGET, "wb") as f:
        f.write(out)
    print("[done] Patcher S63 applied. {} bytes written.".format(len(out)))
    print("Next: python scripts/build_dashboard.py")
    print("      grep -c 'ssp-overlay' master-dashboard/index.html  # should be >0")


if __name__ == "__main__":
    main()
