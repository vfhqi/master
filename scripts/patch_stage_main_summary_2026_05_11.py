"""
Patcher G - Stage groupings on MAIN table + SUMMARY + sort + sector grouping (11-May-26)
=======================================================================================

Four logical edits (D-MD-UI-32 / D-MD-UI-33 / D-MD-UI-34):

EDIT 1 - MAIN CHANGES TABLE:
  * Add stage column-group header row ABOVE the existing 8-filter group-header row.
    4 stage banners (STAGE 1 / 2 / 3 / 4) span the relevant filter groups.
  * Adjust colgroup widths: Ticker 70 -> 110, Industry 80 -> 160, Sector 80 -> 160.
  * Replace default sort with 5-filter cascade (UTR > MM99 > VCP > PB > BP, then ticker).
    Implemented via virtual `chg_stage_cascade` projected key on each row.

EDIT 2 - SUMMARY BAR:
  * Wrap the 8 filter columns in 4 stage-bordered containers matching the colour
    palette used on the header bar and main table.

EDIT 3 - TILE SECTOR GROUPING + SUFFIX:
  * Within each band, sort tickers by (canonical-sector, ticker) instead of plain ticker.
  * Insert tiny sector sub-header strip between groups within each band.
  * Append small-grey sector suffix to each stock name on the same line.

EDIT 4 - currentSort initial default:
  * Change "var currentTab=...currentSort={col:'chg_score'..." (Patcher A set) to use
    'chg_stage_cascade' as the default sort column so the cascade fires on page load.

Pre-write backup. Marker STAGE-MAIN-SUMMARY-V1-MARKER. py_compile.

Usage (Windows-side):
  cd C:\\Users\\richb\\Documents\\COWORK\\master-dashboard
  python scripts\\patch_stage_main_summary_2026_05_11.py
  python scripts\\build_dashboard.py
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
TARGET = PROJECT_DIR / "scripts" / "build_dashboard.py"

MARKER = "STAGE-MAIN-SUMMARY-V1-MARKER"


def backup(p):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = p.with_suffix(p.suffix + f".bak-pre-stage-main-summary-{ts}")
    shutil.copy2(p, bak)
    print(f"  backup -> {bak.name}")


def replace_once(content, old, new, label):
    n = content.count(old)
    if n == 0:
        print(f"  [{label}] anchor NOT FOUND")
        print(f"    looking for: {old[:160]!r}...")
        sys.exit(1)
    if n > 1:
        print(f"  [{label}] anchor matches {n} times (must be unique)")
        sys.exit(1)
    return content.replace(old, new)


# ============================================================
# EDIT 1A - currentSort default changes 'chg_score' to 'chg_stage_cascade'
# ============================================================
OLD_CURRENT_TAB = 'var currentTab="changes",currentSort={col:"chg_score",dir:"desc"};'
NEW_CURRENT_TAB = 'var currentTab="changes",currentSort={col:"chg_stage_cascade",dir:"desc"}; /* ' + MARKER + ' */'


# ============================================================
# EDIT 1B - chgRows projection + sort logic
# Replace the existing row build, sort decision, and sector-group-on-default block.
# ============================================================
OLD_CHGROW_BUILD = '''  // Build row objects with projected stage values for sorting
  var TIME_SUFFIXES=["1m","1w","1d","now"];
  var chgRows=[];
  for(var tk in t0){
    var changed=false;
    for(var fi=0;fi<FILTER_ORDER.length;fi++){
      var f=FILTER_ORDER[fi];
      var s0=t0[tk]?t0[tk][f]:null;
      var s1=t1[tk]?t1[tk][f]:null;
      var s5=t5[tk]?t5[tk][f]:null;
      var s22=t22[tk]?t22[tk][f]:null;
      if(s0!==s22||s0!==s5||s0!==s1){changed=true;break}
    }
    if(!changed)continue;
    var meta=metaLookup[tk]||{};
    var row={ticker:tk,sector:meta.sector||'',industry:meta.industry||''};
    // Project stage values as sortable keys: chg_{filter}_{time}
    var chgScore=0;
    FILTER_ORDER.forEach(function(f){
      var gk=GRP_KEY[f];
      var tps=[t22,t5,t1,t0];
      var vals=new Set();
      tps.forEach(function(tp,ti){
        var st=(tp[tk]&&tp[tk][f])?tp[tk][f]:null;
        row["chg_"+gk+"_"+TIME_SUFFIXES[ti]]=st;
        if(st!=null)vals.add(st);else vals.add(null);
      });
      chgScore+=vals.size-1;
    });
    row.chg_score=chgScore;
    chgRows.push(row);
  }
  // Sort: single sort
  var _usingDefault=false;
  if(currentSort.col&&currentSort.col.indexOf("chg_")===0){
    chgRows=sortData(chgRows,currentSort.col,currentSort.dir);
  }else if(currentSort.col==="ticker"||currentSort.col==="industry"){
    chgRows=sortData(chgRows,currentSort.col,currentSort.dir);
  }else if(currentSort.col==="sector"){
    chgRows=sortData(chgRows,"sector",currentSort.dir);
  }else{
    chgRows=sortData(chgRows,"chg_score","desc");
    _usingDefault=true;
  }
  // Only group by sector when using default sort (chg_score) — explicit column sorts are flat
  if(_usingDefault){
    chgRows.sort(function(a,b){
      var sa3=a.sector.toLowerCase(),sb3=b.sector.toLowerCase();
      if(sa3<sb3)return -1;if(sa3>sb3)return 1;return 0;
    });
  }'''

NEW_CHGROW_BUILD = '''  // ''' + MARKER + ''' — Build row objects with projected stage keys + 5-filter cascade rank
  var TIME_SUFFIXES=["1m","1w","1d","now"];
  // Cascade priority: UTR > MM99 > VCP > PB > BP (5 bits, MSB to LSB)
  var CASCADE_FILTERS=["uptrend_retest","mm99","vcp","probing_bet","basing_plateau"];
  var chgRows=[];
  for(var tk in t0){
    var changed=false;
    for(var fi=0;fi<FILTER_ORDER.length;fi++){
      var f=FILTER_ORDER[fi];
      var s0=t0[tk]?t0[tk][f]:null;
      var s1=t1[tk]?t1[tk][f]:null;
      var s5=t5[tk]?t5[tk][f]:null;
      var s22=t22[tk]?t22[tk][f]:null;
      if(s0!==s22||s0!==s5||s0!==s1){changed=true;break}
    }
    if(!changed)continue;
    var meta=metaLookup[tk]||{};
    var row={ticker:tk,sector:meta.sector||'',industry:meta.industry||''};
    // Project stage values as sortable keys: chg_{filter}_{time}
    var chgScore=0;
    FILTER_ORDER.forEach(function(f){
      var gk=GRP_KEY[f];
      var tps=[t22,t5,t1,t0];
      var vals=new Set();
      tps.forEach(function(tp,ti){
        var st=(tp[tk]&&tp[tk][f])?tp[tk][f]:null;
        row["chg_"+gk+"_"+TIME_SUFFIXES[ti]]=st;
        if(st!=null)vals.add(st);else vals.add(null);
      });
      chgScore+=vals.size-1;
    });
    row.chg_score=chgScore;
    // Compute cascade rank: 5-bit number, UTR-Capital=16, MM99-Capital=8, VCP=4, PB=2, BP=1
    var cascade=0;
    CASCADE_FILTERS.forEach(function(f, idx){
      var bitWeight = 1 << (CASCADE_FILTERS.length - 1 - idx);  // MSB first
      if(t0[tk] && t0[tk][f] === "Capital") cascade += bitWeight;
    });
    row.chg_stage_cascade = cascade;
    chgRows.push(row);
  }
  // Sort: cascade default fires when currentSort.col is chg_stage_cascade OR not a chg_/ticker/industry/sector key
  var _usingDefault=false;
  if(currentSort.col === "chg_stage_cascade"){
    // Cascade is desc by definition (higher rank = more qualified). Then alpha by ticker.
    chgRows.sort(function(a,b){
      if(a.chg_stage_cascade !== b.chg_stage_cascade) return b.chg_stage_cascade - a.chg_stage_cascade;
      return a.ticker < b.ticker ? -1 : 1;
    });
    _usingDefault=true;
  }else if(currentSort.col && currentSort.col.indexOf("chg_") === 0){
    chgRows=sortData(chgRows,currentSort.col,currentSort.dir);
  }else if(currentSort.col === "ticker" || currentSort.col === "industry"){
    chgRows=sortData(chgRows,currentSort.col,currentSort.dir);
  }else if(currentSort.col === "sector"){
    chgRows=sortData(chgRows,"sector",currentSort.dir);
  }else{
    // Fallback if currentSort somehow null
    chgRows.sort(function(a,b){
      if(a.chg_stage_cascade !== b.chg_stage_cascade) return b.chg_stage_cascade - a.chg_stage_cascade;
      return a.ticker < b.ticker ? -1 : 1;
    });
    _usingDefault=true;
  }
  // Sector-grouping toggle still applies — secondary alpha-by-sector pass overrides cascade
  // ONLY when user has explicitly enabled chgSectorGrouping (existing toggle preserved).
  // We do NOT re-sort by sector on default any more — cascade is the default.'''


# ============================================================
# EDIT 1C - colgroup widths (Ticker / Industry / Sector)
# ============================================================
OLD_COLGROUP = '''  h+='<colgroup><col style="width:70px"><col style="width:80px"><col style="width:80px">';
  for(var ci=0;ci<32;ci++)h+='<col>';
  h+='</colgroup><thead>';'''
NEW_COLGROUP = '''  h+='<colgroup><col style="width:110px"><col style="width:160px"><col style="width:160px">';
  for(var ci=0;ci<32;ci++)h+='<col>';
  h+='</colgroup><thead>';'''


# ============================================================
# EDIT 1D - Insert stage column-group header row ABOVE the existing filter-group-header row.
# We REPLACE the existing single group-header-row (which has Inputs + 8 filter columns) with
# TWO rows: a stage-banner row, then the existing filter-group row unchanged.
# ============================================================
OLD_MAIN_GROUP_HDR = '''  // Group header row
  h+='<tr class="group-header-row">';
  h+='<th colspan="3" style="background:rgba(100,100,100,0.06)">Inputs</th>';
  FILTER_ORDER.forEach(function(f){
    var lab=FILTER_COLS[f];
    var BG_MAP={"collapse":"rgba(180,30,30,0.08)","basing_plateau":"rgba(39,103,73,0.08)","probing_bet":"rgba(107,70,193,0.08)","mm99":"rgba(27,61,92,0.08)","vcp":"rgba(156,66,33,0.08)","uptrend_retest":"rgba(116,66,16,0.08)","s3_topping":"rgba(200,100,0,0.08)","s4_declining":"rgba(150,20,20,0.08)"};
    var bg=BG_MAP[f]||"rgba(100,100,100,0.08)";
    var gk=GRP_KEY[f];
    h+='<th colspan="4" class="grp-chg-'+gk+'-first grp-chg-'+gk+'-last" style="background:'+bg+'">'+lab+'</th>';
  });
  h+='</tr>';'''

NEW_MAIN_GROUP_HDR = '''  // Stage column-group header row (STAGE 1 / 2 / 3 / 4) - ''' + MARKER + '''
  // Stage spans (in FILTER_ORDER): S1 = BP+PB (2 filters × 4 cols = 8), S2 = VCP+MM99+UTR (3 × 4 = 12),
  // S3 = Topping (1 × 4 = 4), S4 = Declining+Collapse (2 × 4 = 8). Total 32 filter cols + 3 Inputs.
  var STAGE_HDR_BG = {1:"rgba(39,103,73,0.18)",2:"rgba(27,61,92,0.18)",3:"rgba(180,83,9,0.18)",4:"rgba(153,27,27,0.18)"};
  var STAGE_HDR_BORDER = {1:"rgba(39,103,73,0.55)",2:"rgba(27,61,92,0.55)",3:"rgba(180,83,9,0.55)",4:"rgba(153,27,27,0.55)"};
  h+='<tr class="group-header-row">';
  h+='<th colspan="3" style="background:rgba(100,100,100,0.04);border-bottom:1px solid var(--border)"></th>';
  h+='<th colspan="8" style="background:'+STAGE_HDR_BG[1]+';border:2px solid '+STAGE_HDR_BORDER[1]+';border-bottom:none;font-weight:800;font-size:10px;letter-spacing:.5px;color:#1a1a1a">STAGE 1 - Basing</th>';
  h+='<th colspan="12" style="background:'+STAGE_HDR_BG[2]+';border:2px solid '+STAGE_HDR_BORDER[2]+';border-bottom:none;font-weight:800;font-size:10px;letter-spacing:.5px;color:#1a1a1a">STAGE 2 - Markup</th>';
  h+='<th colspan="4" style="background:'+STAGE_HDR_BG[3]+';border:2px solid '+STAGE_HDR_BORDER[3]+';border-bottom:none;font-weight:800;font-size:10px;letter-spacing:.5px;color:#1a1a1a">STAGE 3 - Topping</th>';
  h+='<th colspan="8" style="background:'+STAGE_HDR_BG[4]+';border:2px solid '+STAGE_HDR_BORDER[4]+';border-bottom:none;font-weight:800;font-size:10px;letter-spacing:.5px;color:#1a1a1a">STAGE 4 - Decline</th>';
  h+='</tr>';

  // Filter group header row (existing)
  h+='<tr class="group-header-row">';
  h+='<th colspan="3" style="background:rgba(100,100,100,0.06)">Inputs</th>';
  FILTER_ORDER.forEach(function(f){
    var lab=FILTER_COLS[f];
    var BG_MAP={"collapse":"rgba(180,30,30,0.08)","basing_plateau":"rgba(39,103,73,0.08)","probing_bet":"rgba(107,70,193,0.08)","mm99":"rgba(27,61,92,0.08)","vcp":"rgba(156,66,33,0.08)","uptrend_retest":"rgba(116,66,16,0.08)","s3_topping":"rgba(200,100,0,0.08)","s4_declining":"rgba(150,20,20,0.08)"};
    var bg=BG_MAP[f]||"rgba(100,100,100,0.08)";
    var gk=GRP_KEY[f];
    h+='<th colspan="4" class="grp-chg-'+gk+'-first grp-chg-'+gk+'-last" style="background:'+bg+'">'+lab+'</th>';
  });
  h+='</tr>';'''


# ============================================================
# EDIT 2 - SUMMARY BAR: wrap 8 filter columns into 4 stage-bordered containers.
# Anchor on the per-filter forEach loop opener inserted by Patcher F.
# ============================================================
OLD_SB_LEFT = '''  h+='<div id="section-summarybar" style="display:flex;gap:12px;margin:12px 0;padding:10px 12px;background:var(--bg-secondary);border:1px solid var(--border);border-radius:8px;align-items:stretch">';
  // Left side: 8 filter columns (~65%) — band aggregates
  h+='<div style="display:flex;gap:1px;flex:7">';
  FILTER_ORDER.forEach(function(f){
    var lab=FILTER_COLS[f];
    var bg=BG_MAP_SB[f]||"rgba(100,100,100,0.08)";
    var ba=bandAgg[f];
    var isPh = (f==='s3_topping' || f==='s4_declining' || f==='collapse');
    var phOp = isPh ? ';opacity:0.55' : '';
    h+='<div style="flex:1;text-align:center;padding:6px 3px;border-radius:4px;background:'+bg+phOp+'">';
    h+='<div style="font-size:10px;font-weight:700;color:var(--text-primary);margin-bottom:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+lab+'</div>';
    h+='<div style="font-size:18px;font-weight:800;color:#1b3d5c;line-height:1">'+ba.qual+'</div>';
    h+='<div style="font-size:8px;color:var(--text-secondary);margin-bottom:3px;letter-spacing:.3px;text-transform:uppercase">Qualified</div>';
    h+='<div style="font-size:9px;line-height:1.4;color:var(--text-secondary)">';
    h+='<div><span style="color:#38a169;font-weight:700">+'+ba.newW+'</span> wk</div>';
    h+='<div><span style="color:#68d391;font-weight:700">+'+ba.newM+'</span> mo</div>';
    h+='<div><span style="color:#e53e3e;font-weight:700">-'+ba.lostW+'</span> recent</div>';
    h+='<div><span style="color:#a0aec0;font-weight:700">-'+ba.lostM+'</span> &ge;1mo</div>';
    h+='</div>';
    h+='</div>';
  });
  h+='</div>';'''

NEW_SB_LEFT = '''  h+='<div id="section-summarybar" style="display:flex;gap:12px;margin:12px 0;padding:10px 12px;background:var(--bg-secondary);border:1px solid var(--border);border-radius:8px;align-items:stretch">';
  // ''' + MARKER + ''' — Left side: 4 stage groups containing 8 filter columns
  h+='<div style="display:flex;gap:8px;flex:7;align-items:stretch">';
  var STAGE_OF_SB = {"basing_plateau":1,"probing_bet":1,"vcp":2,"mm99":2,"uptrend_retest":2,"s3_topping":3,"s4_declining":4,"collapse":4};
  var STAGE_BORDER_SB = {1:"rgba(39,103,73,0.5)",2:"rgba(27,61,92,0.5)",3:"rgba(180,83,9,0.5)",4:"rgba(153,27,27,0.5)"};
  var STAGE_LBL_SB = {1:"STAGE 1",2:"STAGE 2",3:"STAGE 3",4:"STAGE 4"};
  // Render one stage box at a time, containing its filter columns
  function _sbRenderFilterCol(f){
    var lab=FILTER_COLS[f];
    var bg=BG_MAP_SB[f]||"rgba(100,100,100,0.08)";
    var ba=bandAgg[f];
    var isPh = (f==='s3_topping' || f==='s4_declining' || f==='collapse');
    var phOp = isPh ? ';opacity:0.55' : '';
    var s='<div style="flex:1;min-width:0;text-align:center;padding:5px 3px;border-radius:3px;background:'+bg+phOp+'">';
    s+='<div style="font-size:9.5px;font-weight:700;color:var(--text-primary);margin-bottom:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+lab+'</div>';
    s+='<div style="font-size:17px;font-weight:800;color:#1b3d5c;line-height:1">'+ba.qual+'</div>';
    s+='<div style="font-size:7.5px;color:var(--text-secondary);margin-bottom:2px;letter-spacing:.3px;text-transform:uppercase">Qualified</div>';
    s+='<div style="font-size:9px;line-height:1.35;color:var(--text-secondary)">';
    s+='<div><span style="color:#38a169;font-weight:700">+'+ba.newW+'</span> wk</div>';
    s+='<div><span style="color:#68d391;font-weight:700">+'+ba.newM+'</span> mo</div>';
    s+='<div><span style="color:#e53e3e;font-weight:700">-'+ba.lostW+'</span> recent</div>';
    s+='<div><span style="color:#a0aec0;font-weight:700">-'+ba.lostM+'</span> &ge;1mo</div>';
    s+='</div>';
    s+='</div>';
    return s;
  }
  [1,2,3,4].forEach(function(stageId){
    var stageFilters = FILTER_ORDER.filter(function(f){return STAGE_OF_SB[f] === stageId});
    if(stageFilters.length === 0) return;
    var flexGrow = stageFilters.length;
    h+='<div style="flex:'+flexGrow+' 1 0;min-width:0;border:1.5px solid '+STAGE_BORDER_SB[stageId]+';border-radius:6px;padding:3px 4px 5px;background:rgba(0,0,0,0.012);display:flex;flex-direction:column">';
    h+='<div style="font-size:8px;font-weight:700;color:#4a4a4a;letter-spacing:.5px;text-align:center;padding:0 0 3px">'+STAGE_LBL_SB[stageId]+'</div>';
    h+='<div style="display:flex;gap:2px;flex:1">';
    stageFilters.forEach(function(f){ h += _sbRenderFilterCol(f); });
    h+='</div></div>';
  });
  h+='</div>';'''


# ============================================================
# EDIT 3 - TILE BANDS: secondary sort by sector + sub-headers + sector suffix on stock rows
# Anchor on the existing band-rendering loop in chgRenderTile.
# ============================================================
OLD_BAND_LOOP = '''    // Sort tickers alphabetically within each band
    for(var bi=1; bi<=5; bi++) bands[bi].sort();'''

NEW_BAND_LOOP = '''    // ''' + MARKER + ''' — sort by (canonical-sector, ticker) within each band
    function _secKey(tk){
      var m = metaLookup[tk] || {};
      var s = m.sector || 'zzzz_unknown';
      return s.toLowerCase();
    }
    for(var bi=1; bi<=5; bi++){
      bands[bi].sort(function(a,b){
        var sa = _secKey(a), sb = _secKey(b);
        if(sa !== sb) return sa < sb ? -1 : 1;
        return a < b ? -1 : 1;
      });
    }'''


OLD_BAND_RENDER = '''    for(var bandId = 1; bandId <= 5; bandId++){
      var bandTickers = bands[bandId];
      if(bandTickers.length === 0) continue;
      var bm = BAND_META[bandId];
      // Band header strip
      var bandHeaderStyle = bandId === 5
        ? 'background:#f5f5f4;color:#737373;font-style:italic'
        : 'background:' + bm.accent + '1a;color:' + bm.accent + ';font-weight:700';
      out += '<div style="' + bandHeaderStyle + ';font-size:9px;letter-spacing:.3px;padding:3px 6px;margin:5px 0 2px;border-radius:3px;border-left:3px solid ' + bm.accent + '">' + bm.label + ' (' + bandTickers.length + ')</div>';
      // Band rows in a fresh grid
      out += '<div style="display:grid;grid-template-columns:1fr 36px 36px 44px;gap:2px 4px;align-items:center">';
      bandTickers.forEach(function(tk){
        var meta = metaLookup[tk] || {};
        var dn = (displayMode === 'company') ? (meta.company || tk) : tk;
        var rowColor = (bandId === 5) ? '#737373' : (bandId <= 3 ? '#1a1a1a' : '#9b2c2c');
        var rowOpacity = (bandId === 5) ? '0.7' : '1';

        // Determine cell states for this ticker
        var c0  = t0[tk]  && t0[tk][filt]  === "Capital";
        var c5  = t5[tk]  && t5[tk][filt]  === "Capital";
        var c22 = t22[tk] && t22[tk][filt] === "Capital";
        var monthCell = chgPill(c22 ? 'in' : 'out', false);
        var weekCell  = chgPill(c5  ? 'in' : 'out', false);
        var nowCell   = chgPill(c0  ? 'in' : 'out', true);

        out += '<div class="chg-tile-stock" data-ticker="' + tk + '" data-tab="' + tabId + '" style="font-size:10.5px;font-weight:600;color:' + rowColor + ';opacity:' + rowOpacity + ';cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="' + (meta.company || tk) + '">' + dn + '</div>';
        out += '<div style="text-align:center">' + monthCell + '</div>';
        out += '<div style="text-align:center">' + weekCell + '</div>';
        out += '<div style="text-align:center">' + nowCell + '</div>';
      });
      out += '</div>';
    }'''

NEW_BAND_RENDER = '''    for(var bandId = 1; bandId <= 5; bandId++){
      var bandTickers = bands[bandId];
      if(bandTickers.length === 0) continue;
      var bm = BAND_META[bandId];
      // Band header strip
      var bandHeaderStyle = bandId === 5
        ? 'background:#f5f5f4;color:#737373;font-style:italic'
        : 'background:' + bm.accent + '1a;color:' + bm.accent + ';font-weight:700';
      out += '<div style="' + bandHeaderStyle + ';font-size:9px;letter-spacing:.3px;padding:3px 6px;margin:5px 0 2px;border-radius:3px;border-left:3px solid ' + bm.accent + '">' + bm.label + ' (' + bandTickers.length + ')</div>';

      // Group tickers by canonical sector within this band
      var _secGroups = {};
      var _secOrder = [];
      bandTickers.forEach(function(tk){
        var m = metaLookup[tk] || {};
        var sec = m.sector || 'Unknown';
        if(!_secGroups[sec]){ _secGroups[sec] = []; _secOrder.push(sec); }
        _secGroups[sec].push(tk);
      });

      // Render each sector subgroup with its mini-header
      _secOrder.forEach(function(sec){
        var secTickers = _secGroups[sec];
        // Sector sub-header: tiny grey strip
        out += '<div style="font-size:8.5px;color:#737373;font-weight:600;letter-spacing:.2px;padding:3px 4px 1px;margin-top:3px;border-bottom:1px dotted #d4d4d4">' + sec + ' <span style="font-weight:400;color:#a3a3a3">(' + secTickers.length + ')</span></div>';
        // Body grid for this sector
        out += '<div style="display:grid;grid-template-columns:1fr 38px 38px 48px;gap:2px 4px;align-items:center;padding-top:1px">';
        secTickers.forEach(function(tk){
          var meta = metaLookup[tk] || {};
          var dn = (displayMode === 'company') ? (meta.company || tk) : tk;
          var rowColor = (bandId === 5) ? '#737373' : (bandId <= 3 ? '#1a1a1a' : '#9b2c2c');
          var rowOpacity = (bandId === 5) ? '0.7' : '1';
          var secSuffix = sec ? ' <span style="font-weight:400;font-size:9px;color:#a3a3a3">' + sec + '</span>' : '';

          // Determine cell states for this ticker
          var c0  = t0[tk]  && t0[tk][filt]  === "Capital";
          var c5  = t5[tk]  && t5[tk][filt]  === "Capital";
          var c22 = t22[tk] && t22[tk][filt] === "Capital";
          var monthCell = chgPill(c22 ? 'in' : 'out', false);
          var weekCell  = chgPill(c5  ? 'in' : 'out', false);
          var nowCell   = chgPill(c0  ? 'in' : 'out', true);

          out += '<div class="chg-tile-stock" data-ticker="' + tk + '" data-tab="' + tabId + '" style="font-size:10.5px;font-weight:600;color:' + rowColor + ';opacity:' + rowOpacity + ';cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="' + (meta.company || tk) + ' - ' + sec + '">' + dn + secSuffix + '</div>';
          out += '<div style="text-align:center">' + monthCell + '</div>';
          out += '<div style="text-align:center">' + weekCell + '</div>';
          out += '<div style="text-align:center">' + nowCell + '</div>';
        });
        out += '</div>';
      });
    }'''


# Also need to adjust the column header grid widths in chgRenderTile (line ~4322-4324) to match the new 38/38/48 grid
OLD_TILE_COLHDR = '''    // Column headers: Stock | Month | Week | NOW
    out += '<div style="display:grid;grid-template-columns:1fr 36px 36px 44px;gap:3px 4px;align-items:center;font-size:9px;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.4px;font-weight:700;padding-bottom:3px;border-bottom:1px solid var(--border)">';
    out += '<div>Stock</div><div style="text-align:center">Month</div><div style="text-align:center">Week</div><div style="text-align:center;color:#1b3d5c">Now</div>';
    out += '</div>';'''
NEW_TILE_COLHDR = '''    // Column headers: Stock | Month | Week | NOW (widths match band-body grid)
    out += '<div style="display:grid;grid-template-columns:1fr 38px 38px 48px;gap:3px 4px;align-items:center;font-size:9px;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.4px;font-weight:700;padding-bottom:3px;border-bottom:1px solid var(--border)">';
    out += '<div>Stock</div><div style="text-align:center">Month</div><div style="text-align:center">Week</div><div style="text-align:center;color:#1b3d5c">Now</div>';
    out += '</div>';'''


# ============================================================
# Main
# ============================================================
def main():
    print(f"Patching: {TARGET}")
    if not TARGET.exists():
        print("  ERROR: target not found")
        sys.exit(1)

    content = TARGET.read_text(encoding="utf-8")
    if MARKER in content:
        print(f"  marker '{MARKER}' present; nothing to do")
        sys.exit(0)

    backup(TARGET)
    original_len = len(content)

    print("  Edit 1A: currentSort default = chg_stage_cascade")
    content = replace_once(content, OLD_CURRENT_TAB, NEW_CURRENT_TAB, "Edit 1A")

    print("  Edit 1B: chgRows projection + cascade sort")
    content = replace_once(content, OLD_CHGROW_BUILD, NEW_CHGROW_BUILD, "Edit 1B")

    print("  Edit 1C: colgroup widths Ticker/Industry/Sector 110/160/160")
    content = replace_once(content, OLD_COLGROUP, NEW_COLGROUP, "Edit 1C")

    print("  Edit 1D: stage column-group header row above filter group row")
    content = replace_once(content, OLD_MAIN_GROUP_HDR, NEW_MAIN_GROUP_HDR, "Edit 1D")

    print("  Edit 2: Summary Bar stage-bordered containers")
    content = replace_once(content, OLD_SB_LEFT, NEW_SB_LEFT, "Edit 2")

    print("  Edit 3A: tile band sort by (sector, ticker)")
    content = replace_once(content, OLD_BAND_LOOP, NEW_BAND_LOOP, "Edit 3A")

    print("  Edit 3B: tile column header widths align with new body grid")
    content = replace_once(content, OLD_TILE_COLHDR, NEW_TILE_COLHDR, "Edit 3B")

    print("  Edit 3C: tile band render with sector sub-groups + name suffix")
    content = replace_once(content, OLD_BAND_RENDER, NEW_BAND_RENDER, "Edit 3C")

    TARGET.write_text(content, encoding="utf-8")
    new_len = len(content)
    print(f"  wrote {new_len:,} bytes (delta {new_len - original_len:+,})")

    import py_compile
    try:
        py_compile.compile(str(TARGET), doraise=True)
        print("  py_compile: OK")
    except py_compile.PyCompileError as e:
        print(f"  py_compile FAILED: {e}")
        sys.exit(1)

    print(f"  done. Marker '{MARKER}' injected.")
    print("  Next: python scripts\\build_dashboard.py")


if __name__ == "__main__":
    main()
