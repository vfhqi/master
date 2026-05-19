"""
Patcher E — STAGE REFACTOR (11-May-26)
======================================

Introduces Minervini-style 4-stage taxonomy as the top-level
organisation primitive for the 8 filter screens.

Stage map (D-MD-UI-25, locked):
  Stage 1 - Basing/bottoming:     Basing Plateau, Probing Bet
  Stage 2 - Markup/breakout:      VCP, MM99, Uptrend Retest
  Stage 3 - Topping:              Topping            (placeholder)
  Stage 4 - Decline/capitulation: Declining, Collapse (placeholders)

Changes:
  1. TABS list re-ordered + 3 placeholder tabs added (8 filter tabs total).
  2. Tab-button builder updated:
     - Stage banners around each stage group (D-MD-UI-26 / Gap 1 Option ii)
     - Placeholder tabs greyed-out (50% opacity, cursor:default, no click)
  3. FILTER_ORDER re-sequenced (Collapse from far-left to far-right).
  4. CHANGES tiles V3 replaces V2:
     - Current-state-first (Month / Week / **Now** columns; Now is bold/primary)
     - 5 sub-group bands per tile by signal strength
     - Row 1 = Stage 4 + Stage 1, Row 2 = Stage 2 + Stage 3 (D-MD-UI-27)
     - Stage banners span each stage's tile pair within a row
  5. Summary Bar: re-ordered only (no banners) per D-MD-UI-28.
  6. CHANGES main table: column re-order + add stage column-group headers.

Pre-write backup, idempotency marker STAGE-REFACTOR-V3-MARKER, py_compile.

Usage:
  cd C:\\Users\\richb\\Documents\\COWORK\\master-dashboard
  python scripts\\patch_stage_refactor_2026_05_11.py
  python scripts\\build_dashboard.py
"""

import sys
import shutil
import re
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
TARGET = PROJECT_DIR / "scripts" / "build_dashboard.py"

MARKER = "STAGE-REFACTOR-V3-MARKER"


def backup(p):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = p.with_suffix(p.suffix + f".bak-pre-stage-refactor-{ts}")
    shutil.copy2(p, bak)
    print(f"  backup -> {bak.name}")


def replace_once(content, old, new, label):
    n = content.count(old)
    if n == 0:
        print(f"  [{label}] anchor NOT FOUND")
        sys.exit(1)
    if n > 1:
        print(f"  [{label}] anchor matches {n} times (must be unique)")
        sys.exit(1)
    return content.replace(old, new)


# ============================================================
# EDIT 1 - TABS list re-order + 3 placeholder tabs
# ============================================================
OLD_TABS_LIST = '''TABS = [
    # Group 1: Technical filter tabs
    {"id": "bp",        "label": "Basing Plateau",   "accent": "#276749"},
    {"id": "pb",        "label": "Probing Bet",      "accent": "#6b46c1"},
    {"id": "mm99",      "label": "MM 99",            "accent": "#1b3d5c"},
    {"id": "vcp",       "label": "VCP",              "accent": "#9c4221"},
    {"id": "utr",       "label": "Uptrend Retest",   "accent": "#744210"},
    # Group 2: Data / reference tabs
    {"id": "tech",      "label": "Technical Data",   "accent": "#2c5282"},
    {"id": "ssem",      "label": "SS Earnings Momentum", "accent": "#2b6cb0"},
    {"id": "val",       "label": "Valuation",        "accent": "#38a169"},
    {"id": "combos",    "label": "TIMELINESS",       "accent": "#dd6b20"},
    {"id": "changes",   "label": "CHANGES",          "accent": "#c53030"},  # CHANGES-TAB-MARKER
    {"id": "positions", "label": "Live Investments",  "accent": "#319795"},
]'''

# STAGE-REFACTOR: re-order + add placeholders (s3_topping, s4_declining, collapse)
# Stages: 1=BP,PB | 2=VCP,MM99,UTR | 3=Topping | 4=Declining,Collapse
NEW_TABS_LIST = '''TABS = [
    # ''' + MARKER + ''' — 8 filter tabs grouped by Minervini-style stage
    # Stage 1 — Basing/bottoming
    {"id": "bp",        "label": "Basing Plateau",   "accent": "#276749", "stage": 1},
    {"id": "pb",        "label": "Probing Bet",      "accent": "#6b46c1", "stage": 1},
    # Stage 2 — Markup/breakout
    {"id": "vcp",       "label": "VCP",              "accent": "#9c4221", "stage": 2},
    {"id": "mm99",      "label": "MM 99",            "accent": "#1b3d5c", "stage": 2},
    {"id": "utr",       "label": "Uptrend Retest",   "accent": "#744210", "stage": 2},
    # Stage 3 — Topping (placeholder)
    {"id": "s3_topping",   "label": "Topping",       "accent": "#b45309", "stage": 3, "placeholder": True},
    # Stage 4 — Decline/capitulation (placeholders)
    {"id": "s4_declining", "label": "Declining",     "accent": "#991b1b", "stage": 4, "placeholder": True},
    {"id": "collapse",     "label": "Collapse",      "accent": "#7f1d1d", "stage": 4, "placeholder": True},
    # Data / reference tabs
    {"id": "tech",      "label": "Technical Data",   "accent": "#2c5282"},
    {"id": "ssem",      "label": "SS Earnings Momentum", "accent": "#2b6cb0"},
    {"id": "val",       "label": "Valuation",        "accent": "#38a169"},
    {"id": "combos",    "label": "TIMELINESS",       "accent": "#dd6b20"},
    {"id": "changes",   "label": "CHANGES",          "accent": "#c53030"},  # CHANGES-TAB-MARKER
    {"id": "positions", "label": "Live Investments",  "accent": "#319795"},
]'''


# ============================================================
# EDIT 2 - TECHNICAL_TABS set + tab-button builder loop
# Replaces the existing technical-group-vs-data-group framing with
# 4 stage banners around the 8 filter tabs.
# ============================================================
OLD_BUILDER = '''    # FIX-S4-HDR: Two visual groups of tabs with border grouping
    TECHNICAL_TABS = {"bp", "pb", "vcp", "mm99", "utr"}
    tab_buttons = '<div class="tab-group" style="border:1.5px solid rgba(200,50,50,0.25);border-radius:6px;padding:2px 4px;display:inline-flex;gap:2px">'
    for t in TABS:
        # Switch group when we hit the first data/reference tab (Tech Data)
        if t["id"] not in TECHNICAL_TABS and t["id"] == "tech":
            tab_buttons += '</div><div class="tab-group" style="border:1.5px solid rgba(120,80,200,0.25);border-radius:6px;padding:2px 4px;display:inline-flex;gap:2px;margin-left:6px">'
        active = ' tab-active' if t["id"] == "changes" else ''
        # SESSION 9 Pass 1.1: TIMELINESS gets emphasis treatment (uppercase + bold)
        emphasis = ' tab-emphasis' if t["id"] == "combos" else ''
        bg_tint = hex_to_rgba(t["accent"], 0.1)
        border_tint = hex_to_rgba(t["accent"], 0.3)
        tab_buttons += (
            '<button class="tab-btn' + active + emphasis + '" data-tab="' + t["id"] + '" '
            'style="--tab-accent:' + t["accent"] + ';background:' + bg_tint + ';border-color:' + border_tint + '" '
            'onclick="switchTab(\\'' + t["id"] + '\\')">' + t["label"] + '</button>'
        )
    tab_buttons += '</div>'
'''

NEW_BUILDER = '''    # ''' + MARKER + ''' — 4 stage banners + 1 reference banner
    STAGE_INFO = {
        1: {"label": "STAGE 1", "color": "rgba(39,103,73,0.35)"},   # green — basing/bottoming
        2: {"label": "STAGE 2", "color": "rgba(27,61,92,0.35)"},    # navy — markup/breakout
        3: {"label": "STAGE 3", "color": "rgba(180,83,9,0.35)"},    # amber — topping
        4: {"label": "STAGE 4", "color": "rgba(153,27,27,0.35)"},   # red — decline
    }
    tab_buttons = ""
    current_stage = None
    in_filter_section = True
    for t in TABS:
        stage = t.get("stage")
        is_filter_tab = stage is not None
        if is_filter_tab:
            # Open a new stage group when stage changes
            if stage != current_stage:
                if current_stage is not None:
                    tab_buttons += '</div>'  # close previous group
                si = STAGE_INFO[stage]
                tab_buttons += (
                    '<div class="tab-stage-group" style="display:inline-flex;flex-direction:column;'
                    'border:1.5px solid ' + si["color"] + ';border-radius:6px;padding:1px 4px 2px;margin-right:6px">'
                    '<div style="font-size:8px;font-weight:700;color:#6b6b6b;letter-spacing:.5px;'
                    'text-align:center;padding:0 2px 1px">' + si["label"] + '</div>'
                    '<div style="display:inline-flex;gap:2px">'
                )
                current_stage = stage
        else:
            # Closing the filter section, switching to reference tabs
            if in_filter_section:
                if current_stage is not None:
                    tab_buttons += '</div></div>'  # close inner + outer of last stage group
                # Open the reference-tabs group
                tab_buttons += (
                    '<div class="tab-group" style="border:1.5px solid rgba(120,80,200,0.25);'
                    'border-radius:6px;padding:2px 4px;display:inline-flex;gap:2px;margin-left:6px">'
                )
                in_filter_section = False
        active = ' tab-active' if t["id"] == "changes" else ''
        emphasis = ' tab-emphasis' if t["id"] == "combos" else ''
        bg_tint = hex_to_rgba(t["accent"], 0.1)
        border_tint = hex_to_rgba(t["accent"], 0.3)
        is_placeholder = t.get("placeholder", False)
        ph_class = ' tab-placeholder' if is_placeholder else ''
        ph_style = ';opacity:0.45;cursor:default' if is_placeholder else ''
        onclick = '' if is_placeholder else 'onclick="switchTab(\\'' + t["id"] + '\\')"'
        tab_buttons += (
            '<button class="tab-btn' + active + emphasis + ph_class + '" data-tab="' + t["id"] + '" '
            'style="--tab-accent:' + t["accent"] + ';background:' + bg_tint + ';border-color:' + border_tint + ph_style + '" '
            + onclick + '>' + t["label"] + '</button>'
        )
    # Close the final open container (reference group)
    tab_buttons += '</div>'
'''


# ============================================================
# EDIT 3 - FILTER_ORDER constant re-sequenced
# ============================================================
OLD_FILTER_ORDER = 'var FILTER_ORDER=["collapse","basing_plateau","probing_bet","vcp","mm99","uptrend_retest","s3_topping","s4_declining"];'
NEW_FILTER_ORDER = 'var FILTER_ORDER=["basing_plateau","probing_bet","vcp","mm99","uptrend_retest","s3_topping","s4_declining","collapse"]; /* ' + MARKER + ' */'


# ============================================================
# EDIT 4 - Replace the entire V2 tiles block with V3 (stage-banded,
# current-state-first, sub-group bands).
#
# The OLD block spans from the V2 marker comment down to the closing
# `h+='</div>';` that ends the .changes-tiles-v2 wrapper.
# ============================================================
OLD_V2_BLOCK = '''  // CHG-TILES-V2-MARKER
  // Tile rendering V2 (11-May-26): 2 rows x 4 tiles, each tile shows
  // BOTH "Last Month" (T-22) and "Last Week" (T-5) columns with
  // colour-coded persistence indicators.
  // Row 1: Collapse | Basing Plateau | Probing Bet | VCP
  // Row 2: MM99 | Uptrend Retest | S3 Topping | S4 Declining

  var FILT_TAB={"basing_plateau":"bp","probing_bet":"pb","mm99":"mm99","vcp":"vcp","uptrend_retest":"utr"};

  // Compute newCap/lostCap for both T-5 (week) and T-22 (month) windows per filter
  function chgComputeSets(filt){
    var newW=[],lostW=[],newM=[],lostM=[];
    for(var tk in t0){
      var c0=t0[tk]&&t0[tk][filt];
      var c5=t5[tk]&&t5[tk][filt];
      var c22=t22[tk]&&t22[tk][filt];
      // Last Week: T-0 vs T-5
      if(c0==="Capital"&&c5!=="Capital")newW.push(tk);
      if(c5==="Capital"&&c0!=="Capital")lostW.push(tk);
      // Last Month: T-0 vs T-22
      if(c0==="Capital"&&c22!=="Capital")newM.push(tk);
      if(c22==="Capital"&&c0!=="Capital")lostM.push(tk);
    }
    if(chgHighestQual){
      newW=newW.filter(function(tk){return _hqMap[tk]===filt});
      newM=newM.filter(function(tk){return _hqMap[tk]===filt});
    }
    return {newW:newW,lostW:lostW,newM:newM,lostM:lostM};
  }

  // Union the four sets into rows. Each row has flags: w (in week), m (in month), lostW, lostM.
  function chgBuildRows(sets){
    var byTk={};
    sets.newW.forEach(function(tk){byTk[tk]=byTk[tk]||{};byTk[tk].w=true;byTk[tk].kind='new';});
    sets.newM.forEach(function(tk){byTk[tk]=byTk[tk]||{};byTk[tk].m=true;byTk[tk].kind='new';});
    sets.lostW.forEach(function(tk){byTk[tk]=byTk[tk]||{};byTk[tk].lostW=true;byTk[tk].kind='lost';});
    sets.lostM.forEach(function(tk){byTk[tk]=byTk[tk]||{};byTk[tk].lostM=true;byTk[tk].kind='lost';});
    var rows=[];
    for(var tk in byTk){
      var r=byTk[tk];r.tk=tk;
      // Sort priority: 0=both, 1=week-only, 2=month-only (within kind)
      if(r.kind==='new'){
        r.prio = (r.w&&r.m)?0:(r.w?1:2);
      }else{
        r.prio = (r.lostW&&r.lostM)?0:(r.lostW?1:2);
      }
      rows.push(r);
    }
    rows.sort(function(a,b){
      // 'new' rows above 'lost' rows; within each, BOTH > WEEK > MONTH; then alpha by ticker
      if(a.kind!==b.kind)return a.kind==='new'?-1:1;
      if(a.prio!==b.prio)return a.prio-b.prio;
      return a.tk<b.tk?-1:1;
    });
    return rows;
  }

  // Colour palette for the persistence cells (8 distinct states)
  // NEW (gained Capital): green family
  //   both periods    -> deep green solid pill in BOTH cells       (sustained ~1 month)
  //   week-only       -> bright green pill in WEEK; empty in MONTH (fresh signal)
  //   month-only      -> amber pill in MONTH; empty in WEEK        (was-new-now-faded — became Capital >1w but not still gaining)
  // LOST (gave back Capital): red family
  //   both periods    -> deep red solid pill in BOTH cells         (gone for >1w)
  //   week-only       -> bright red pill in WEEK; empty in MONTH   (just lost)
  //   month-only      -> muted red in MONTH; empty in WEEK         (lost a month ago, still gone)
  function chgCell(state){
    // state: 'new-both' | 'new-only' | 'lost-both' | 'lost-only' | 'empty'
    var s={
      'new-both':  {bg:'#276749',fg:'#fff',label:'NEW'},
      'new-only':  {bg:'#48bb78',fg:'#fff',label:'NEW'},
      'new-faded': {bg:'#f6e05e',fg:'#744210',label:'WAS'},
      'lost-both': {bg:'#9b2c2c',fg:'#fff',label:'LOST'},
      'lost-only': {bg:'#f56565',fg:'#fff',label:'LOST'},
      'lost-faded':{bg:'#fed7d7',fg:'#9b2c2c',label:'GONE'},
      'empty':     {bg:'transparent',fg:'#cbd5e0',label:'\\u2014'}
    }[state]||{bg:'transparent',fg:'#cbd5e0',label:'\\u2014'};
    return '<span style="display:inline-block;min-width:36px;text-align:center;font-size:9px;font-weight:700;padding:1px 6px;border-radius:3px;background:'+s.bg+';color:'+s.fg+';letter-spacing:.3px">'+s.label+'</span>';
  }

  // Map row state -> (monthCell, weekCell)
  function chgRowCells(r){
    if(r.kind==='new'){
      if(r.w&&r.m)return [chgCell('new-both'), chgCell('new-both')];
      if(r.w)     return [chgCell('empty'),    chgCell('new-only')];
      return         [chgCell('new-faded'),chgCell('empty')];
    }else{
      if(r.lostW&&r.lostM)return [chgCell('lost-both'), chgCell('lost-both')];
      if(r.lostW)         return [chgCell('empty'),     chgCell('lost-only')];
      return                  [chgCell('lost-faded'), chgCell('empty')];
    }
  }

  function chgRenderTileRow(filterKeys){
    /* CHG-TILE-HEIGHTS-FIXUP */var out='<div style="display:flex;gap:12px;margin-bottom:12px;align-items:flex-start">';
    filterKeys.forEach(function(filt){
      var label=FILTER_COLS[filt]||filt;
      var borderCol=TILE_BORDER[filt]||'rgba(100,100,100,0.25)';
      var sets=chgComputeSets(filt);
      var rows=chgBuildRows(sets);
      var nNew=rows.filter(function(r){return r.kind==='new'}).length;
      var nLost=rows.filter(function(r){return r.kind==='lost'}).length;
      var tabId=FILT_TAB[filt]||'';

      out+='<div style="flex:1;min-width:0;max-height:560px;background:var(--bg-secondary);border:2px solid '+borderCol+';border-radius:8px;padding:10px 12px;display:flex;flex-direction:column;overflow:hidden">';
      // Header: filter label + counts
      out+='<div style="font-weight:700;font-size:13px;margin-bottom:6px;color:var(--text-primary);display:flex;justify-content:space-between;align-items:baseline">';
      out+='<span>'+label+'</span>';
      out+='<span style="font-size:11px;font-weight:500"><span style="color:#38a169">+'+nNew+'</span> <span style="color:#a0aec0">/</span> <span style="color:#e53e3e">-'+nLost+'</span></span>';
      out+='</div>';

      if(rows.length===0){
        out+='<div style="font-size:11px;color:var(--text-secondary);font-style:italic;padding:4px 0">No changes in last month.</div>';
        out+='</div>';
        return;
      }

      // Column headers
      out+='<div style="display:grid;grid-template-columns:1fr 44px 44px;gap:4px 6px;align-items:center;font-size:9px;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.4px;font-weight:700;padding-bottom:3px;border-bottom:1px solid var(--border)">';
      out+='<div>Stock</div><div style="text-align:center">Month</div><div style="text-align:center">Week</div>';
      out+='</div>';

      // Render rows; insert divider between 'new' and 'lost' clusters
      var seenLost=false;
      out+='<div style="display:grid;grid-template-columns:1fr 44px 44px;gap:3px 6px;align-items:center;padding-top:4px;overflow-y:auto;flex:1;min-height:0">';
      rows.forEach(function(r){
        if(r.kind==='lost'&&!seenLost){
          // Divider row spanning all 3 cols
          out+='<div style="grid-column:1 / span 3;border-top:1px solid var(--border);margin:3px 0 1px"></div>';
          seenLost=true;
        }
        var meta=metaLookup[r.tk]||{};
        var dn=(displayMode==='company')?(meta.company||r.tk):r.tk;
        var color=r.kind==='new'?'#276749':'#9b2c2c';
        var cells=chgRowCells(r);
        out+='<div class="chg-tile-stock" data-ticker="'+r.tk+'" data-tab="'+tabId+'" style="font-size:10.5px;font-weight:600;color:'+color+';cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="'+(meta.company||r.tk)+'">'+dn+'</div>';
        out+='<div style="text-align:center">'+cells[0]+'</div>';
        out+='<div style="text-align:center">'+cells[1]+'</div>';
      });
      out+='</div>';

      out+='</div>'; // end tile
    });
    out+='</div>'; // end tile row
    return out;
  }

  // Two rows of four tiles each, matching FILTER_ORDER
  h+='<div class="changes-tiles-v2">';
  h+=chgRenderTileRow(FILTER_ORDER.slice(0,4));  // Collapse, BP, PB, VCP
  h+=chgRenderTileRow(FILTER_ORDER.slice(4,8));  // MM99, UTR, S3, S4
  h+='</div>';
'''

NEW_V3_BLOCK = '''  // ''' + MARKER + '''
  // Tile rendering V3 (11-May-26): stage-banded, current-state-first.
  // Each tile shows 3-col grid: Month / Week / **Now** (Now bold + primary).
  // Sub-group bands top-to-bottom by signal strength:
  //   1. Sustained Capital      (M+W+Now all in)
  //   2. Newly Capital this week (in Now, not in Week — fresh gain since week-end)
  //   3. Newly Capital this month, still in (in Now + Week, not in Month — recent + settling)
  //   4. Recently lost           (not in Now, was in Week)
  //   5. Long-lost               (not in Now, not in Week, but was in Month — muted)
  // Edge cases fold into closest band.
  // Layout: Row 1 = Stage 4 + Stage 1, Row 2 = Stage 2 + Stage 3 (4 tiles per row),
  // with STAGE-labelled banners spanning each stage's tiles within a row.

  var FILT_TAB={"basing_plateau":"bp","probing_bet":"pb","mm99":"mm99","vcp":"vcp","uptrend_retest":"utr"};
  var STAGE_OF={"basing_plateau":1,"probing_bet":1,"vcp":2,"mm99":2,"uptrend_retest":2,"s3_topping":3,"s4_declining":4,"collapse":4};
  var STAGE_LABEL={1:"STAGE 1 - Basing/bottoming",2:"STAGE 2 - Markup/breakout",3:"STAGE 3 - Topping",4:"STAGE 4 - Decline"};
  var STAGE_COLOR={1:"rgba(39,103,73,0.5)",2:"rgba(27,61,92,0.5)",3:"rgba(180,83,9,0.5)",4:"rgba(153,27,27,0.5)"};

  // Classify each ticker per filter into a band.
  // Returns band id 1-5 or null if ticker has no recent activity in this filter.
  function chgClassify(tk, filt){
    var c0  = t0[tk]  && t0[tk][filt]  === "Capital";
    var c5  = t5[tk]  && t5[tk][filt]  === "Capital";
    var c22 = t22[tk] && t22[tk][filt] === "Capital";
    // Truth table for (M, W, Now):
    //   T T T -> Sustained (band 1)
    //   F F T -> Newly this week (band 2)  — fresh
    //   F T T -> Newly this month, still in (band 3)
    //   T T T already caught
    //   T F T -> flicker: was, gone last week, back now -> fold into band 2 (fresh, looks like just gained)
    //   T T F -> Recently lost (band 4)
    //   F T F -> in last week only, gone now -> band 4 (recently lost)
    //   T F F -> Long-lost (band 5)
    //   F F F -> nothing
    if(c0 && c5 && c22) return 1;
    if(c0 && !c5 && !c22) return 2;          // pure fresh gain
    if(c0 && c5 && !c22) return 3;            // gained within the month, still in
    if(c0 && !c5 && c22) return 2;            // flicker back -> treat as fresh
    if(!c0 && c5) return 4;                    // recently lost (covers TTF and FTF)
    if(!c0 && !c5 && c22) return 5;            // long-lost
    return null;
  }

  // Cell rendering — pill or empty. isPrimary = bolder/larger (the "Now" column).
  function chgPill(state, isPrimary){
    // state: 'in' (Capital), 'out' (not Capital)
    if(state === 'out'){
      return '<span style="display:inline-block;min-width:34px;text-align:center;font-size:9px;color:#cbd5e0">—</span>';
    }
    var size = isPrimary ? {pad:'2px 8px',fs:'10px',mw:'40px'} : {pad:'1px 6px',fs:'9px',mw:'34px'};
    var bg = isPrimary ? '#1b3d5c' : '#276749';
    var fg = '#fff';
    var label = isPrimary ? 'NOW' : 'IN';
    var weight = isPrimary ? 800 : 700;
    return '<span style="display:inline-block;min-width:'+size.mw+';text-align:center;font-size:'+size.fs+';font-weight:'+weight+';padding:'+size.pad+';border-radius:3px;background:'+bg+';color:'+fg+';letter-spacing:.3px">'+label+'</span>';
  }

  // Band-level metadata: label, accent colour, default-visible
  var BAND_META = {
    1: {label:'Sustained Capital',  accent:'#276749', desc:'In all three periods'},
    2: {label:'Newly Capital — this week', accent:'#48bb78', desc:'Gained since last week'},
    3: {label:'Newly Capital — this month', accent:'#68d391', desc:'Gained within the month, still in'},
    4: {label:'Recently lost',       accent:'#e53e3e', desc:'Was Capital recently, no longer'},
    5: {label:'Lost ≥ 1 month',   accent:'#a0aec0', desc:'Was Capital a month ago, gone since'}
  };

  // Render a single tile for one filter.
  function chgRenderTile(filt){
    var label = FILTER_COLS[filt] || filt;
    var borderCol = TILE_BORDER[filt] || 'rgba(100,100,100,0.25)';
    var tabId = FILT_TAB[filt] || '';
    var isPlaceholder = (filt === 's3_topping' || filt === 's4_declining' || filt === 'collapse');

    // Classify every ticker
    var bands = {1:[], 2:[], 3:[], 4:[], 5:[]};
    for(var tk in t0){
      var b = chgClassify(tk, filt);
      if(b !== null) bands[b].push(tk);
    }
    // Sort tickers alphabetically within each band
    for(var bi=1; bi<=5; bi++) bands[bi].sort();

    // Apply highest-qualification dedup: only applies to bands 1+2+3 (current-Capital tickers)
    if(chgHighestQual){
      [1,2,3].forEach(function(bi){
        bands[bi] = bands[bi].filter(function(tk){return _hqMap[tk]===filt});
      });
    }

    var nNow = bands[1].length + bands[2].length + bands[3].length;
    var nGone = bands[4].length + bands[5].length;
    var totalRows = nNow + nGone;

    var out = '<div style="flex:1;min-width:0;max-height:600px;background:var(--bg-secondary);border:2px solid '+borderCol+';border-radius:8px;padding:8px 10px;display:flex;flex-direction:column;overflow:hidden' + (isPlaceholder ? ';opacity:0.55' : '') + '">';

    // Header: filter label + Now/Gone counters
    out += '<div style="font-weight:700;font-size:13px;margin-bottom:5px;color:var(--text-primary);display:flex;justify-content:space-between;align-items:baseline">';
    out += '<span>' + label + '</span>';
    out += '<span style="font-size:11px;font-weight:500"><span style="color:#1b3d5c">Now ' + nNow + '</span> <span style="color:#a0aec0">/</span> <span style="color:#9b2c2c">-' + nGone + '</span></span>';
    out += '</div>';

    if(isPlaceholder){
      out += '<div style="font-size:11px;color:var(--text-secondary);font-style:italic;padding:6px 0">Filter logic pending (Pass 2 parked).</div>';
      out += '</div>';
      return out;
    }
    if(totalRows === 0){
      out += '<div style="font-size:11px;color:var(--text-secondary);font-style:italic;padding:6px 0">No qualifying stocks in last month.</div>';
      out += '</div>';
      return out;
    }

    // Column headers: Stock | Month | Week | NOW
    out += '<div style="display:grid;grid-template-columns:1fr 36px 36px 44px;gap:3px 4px;align-items:center;font-size:9px;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.4px;font-weight:700;padding-bottom:3px;border-bottom:1px solid var(--border)">';
    out += '<div>Stock</div><div style="text-align:center">Month</div><div style="text-align:center">Week</div><div style="text-align:center;color:#1b3d5c">Now</div>';
    out += '</div>';

    // Body: scrollport
    out += '<div style="overflow-y:auto;flex:1;min-height:0;padding-top:3px">';

    for(var bandId = 1; bandId <= 5; bandId++){
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
    }
    out += '</div>'; // end scrollport

    out += '</div>'; // end tile
    return out;
  }

  // Render one stage-pair row: a flex row containing 1-2 stage groups,
  // each group has its own STAGE banner + the tiles for that stage.
  function chgRenderStageRow(stageList){
    var out = '<div style="display:flex;gap:14px;margin-bottom:14px;align-items:flex-start">';
    stageList.forEach(function(stageId){
      // Find all filters belonging to this stage, in FILTER_ORDER order
      var stageFilters = FILTER_ORDER.filter(function(f){return STAGE_OF[f]===stageId});
      if(stageFilters.length === 0) return;
      var stageLabel = STAGE_LABEL[stageId];
      var stageColor = STAGE_COLOR[stageId];
      // Stage group: banner above its tiles
      // flex-grow weighted by tile count so 3-tile stages get more room
      var flexGrow = stageFilters.length;
      out += '<div style="flex:' + flexGrow + ' 1 0;min-width:0;border:1.5px solid ' + stageColor + ';border-radius:8px;padding:6px 8px 8px;background:rgba(0,0,0,0.015)">';
      out += '<div style="font-size:10px;font-weight:700;color:#1a1a1a;letter-spacing:.4px;padding:1px 4px 6px;text-transform:uppercase">' + stageLabel + '</div>';
      out += '<div style="display:flex;gap:8px;align-items:flex-start">';
      stageFilters.forEach(function(filt){
        out += chgRenderTile(filt);
      });
      out += '</div>';
      out += '</div>';
    });
    out += '</div>';
    return out;
  }

  // Two rows of stage pairs:
  //   Row 1: Stage 4 + Stage 1
  //   Row 2: Stage 2 + Stage 3
  h += '<div class="changes-tiles-v3">';
  h += chgRenderStageRow([4, 1]);
  h += chgRenderStageRow([2, 3]);
  h += '</div>';
'''


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

    print("  Edit 1: TABS list re-order + 3 placeholders")
    content = replace_once(content, OLD_TABS_LIST, NEW_TABS_LIST, "Edit 1")

    print("  Edit 2: tab-button builder with stage banners")
    content = replace_once(content, OLD_BUILDER, NEW_BUILDER, "Edit 2")

    print("  Edit 3: FILTER_ORDER re-sequence")
    content = replace_once(content, OLD_FILTER_ORDER, NEW_FILTER_ORDER, "Edit 3")

    print("  Edit 4: tiles V2 -> V3 (stage-banded, current-state-first)")
    content = replace_once(content, OLD_V2_BLOCK, NEW_V3_BLOCK, "Edit 4")

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
