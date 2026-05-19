"""
Patcher B — CHANGES tab tile rebuild (11-May-26)
================================================

Restructures the 8 tile row in renderChanges() into:
  - 2 rows x 4 tiles
  - Each tile shows BOTH "Last Month" (T-22) and "Last Week" (T-5) columns
  - One row per stock (compact), with sort priority: BOTH > WEEK-only > MONTH-only
  - Colour coding per row:
       Both periods    -> solid green pill in both cells (sustained signal)
       Week only       -> green pill in WEEK cell, blank in MONTH
       Month only      -> amber pill in MONTH cell, blank in WEEK (deterioration)
  - Same logic mirrored for lostCap below a divider
       Lost both       -> deep-red pill in both cells
       Lost this week  -> red pill in WEEK
       Lost last month -> muted red in MONTH

Replaces a single contiguous block (~64 lines) in build_dashboard.py.
Pre-write backup + idempotency marker (CHG-TILES-V2-MARKER).

Usage (Windows-side):
  cd C:\\Users\\richb\\Documents\\COWORK\\master-dashboard
  python scripts\\patch_changes_tiles_v2_2026_05_11.py
  python scripts\\build_dashboard.py
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
TARGET = PROJECT_DIR / "scripts" / "build_dashboard.py"

MARKER = "CHG-TILES-V2-MARKER"  # idempotency

OLD_BLOCK = '''  h+='<div class="changes-tiles" style="display:flex;flex-wrap:wrap;gap:12px;margin:8px 0 16px">';
  FILTER_ORDER.forEach(function(filt){
    var label=FILTER_COLS[filt]||filt;
    var borderCol=TILE_BORDER[filt]||"rgba(100,100,100,0.25)";
    var newCap=[];var lostCap=[];
    // Only compute for filters that exist in the data (placeholder filters will have empty lists)
    for(var tk in t0){
      var curr=t0[tk]&&t0[tk][filt];
      var prev=t5[tk]&&t5[tk][filt];
      if(curr==="Capital"&&prev!=="Capital")newCap.push(tk);
      if(prev==="Capital"&&curr!=="Capital")lostCap.push(tk);
    }
    // Highest qualification: only show stock in its rightmost Capital filter tile
    // Applies to newCap only — lostCap always shows (losing Capital is a real change regardless)
    if(chgHighestQual){
      newCap=newCap.filter(function(tk){return _hqMap[tk]===filt});
    }
    h+='<div style="background:var(--bg-secondary);border:2px solid '+borderCol+';border-radius:8px;padding:12px 14px;min-width:140px;flex:1;max-width:220px">';
    h+='<div style="font-weight:700;font-size:13px;margin-bottom:8px;color:var(--text-primary)">'+label+'</div>';
    h+='<div style="display:flex;gap:16px;margin-bottom:6px">';
    h+='<div><span style="color:#38a169;font-weight:700;font-size:18px">+'+newCap.length+'</span><div style="font-size:10px;color:var(--text-secondary)">Newly qualified</div></div>';
    h+='<div><span style="color:#e53e3e;font-weight:700;font-size:18px">-'+lostCap.length+'</span><div style="font-size:10px;color:var(--text-secondary)">Previously qualified</div></div>';
    h+='</div>';
    // List stocks vertically with company/ticker toggle + industry/sector + qualification duration
    // Derive when qualification changed using T-0/T-1/T-5/T-22 data
    function qualInfo(tk,filt,isNew){
      // For "newly qualified": when did it become Capital?
      // For "previously qualified": when did it lose Capital?
      var c0=t0[tk]&&t0[tk][filt], c1=t1[tk]&&t1[tk][filt], c5=t5[tk]&&t5[tk][filt], c22=t22[tk]&&t22[tk][filt];
      if(isNew){
        // Stock is Capital now. When did it gain Capital?
        if(c1!=="Capital"){return{days:"~1d",since:fmtDDM(t0D)}}
        if(c5!=="Capital"){return{days:"~3d",since:fmtDDM(t1D)}}
        if(c22!=="Capital"){return{days:"~2w",since:fmtDDM(t5D)}}
        return{days:">1M",since:"before "+fmtDDM(t22D)};
      }else{
        // Stock lost Capital. When?
        if(c1==="Capital"){return{days:"~1d ago",since:fmtDDM(t0D)}}
        if(c5==="Capital"){return{days:"~3d ago",since:fmtDDM(t1D)}}
        return{days:">1w ago",since:fmtDDM(t5D)};
      }
    }
    // Map filter key → tab ID for double-click navigation
    var FILT_TAB={"basing_plateau":"bp","probing_bet":"pb","mm99":"mm99","vcp":"vcp","uptrend_retest":"utr"};
    function renderStockList(tickers,color,isNew){
      var out='';
      tickers.forEach(function(tk){
        var meta=metaLookup[tk]||{};
        var dn=(displayMode==="company")?(meta.company||tk):tk;
        var qi=qualInfo(tk,filt,isNew);
        var tabId=FILT_TAB[filt]||'';
        out+='<div style="margin-bottom:4px"><div class="chg-tile-stock" data-ticker="'+tk+'" data-tab="'+tabId+'" style="font-size:11px;font-weight:600;color:'+color+';cursor:pointer">'+dn+' <span style="font-weight:400;font-size:9px;color:#999">'+qi.days+' ('+qi.since+')</span></div>';
        var sub=meta.sector||(meta.industry||'');
        if(meta.sector&&meta.industry)sub=meta.industry+' / '+meta.sector;
        if(sub)out+='<div style="font-size:9px;color:#999;margin-top:-1px">'+sub+'</div>';
        out+='</div>';
      });
      return out;
    }
    if(newCap.length>0)h+=renderStockList(newCap,"#38a169",true);
    if(lostCap.length>0){if(newCap.length>0)h+='<div style="border-top:1px solid var(--border);margin:4px 0"></div>';h+=renderStockList(lostCap,"#e53e3e",false)}
    h+='</div>';
  });
  h+='</div>';
'''

NEW_BLOCK = '''  // ''' + MARKER + '''
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
    var out='<div style="display:flex;gap:12px;margin-bottom:12px">';
    filterKeys.forEach(function(filt){
      var label=FILTER_COLS[filt]||filt;
      var borderCol=TILE_BORDER[filt]||'rgba(100,100,100,0.25)';
      var sets=chgComputeSets(filt);
      var rows=chgBuildRows(sets);
      var nNew=rows.filter(function(r){return r.kind==='new'}).length;
      var nLost=rows.filter(function(r){return r.kind==='lost'}).length;
      var tabId=FILT_TAB[filt]||'';

      out+='<div style="flex:1;min-width:0;background:var(--bg-secondary);border:2px solid '+borderCol+';border-radius:8px;padding:10px 12px;display:flex;flex-direction:column">';
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
      out+='<div style="display:grid;grid-template-columns:1fr 44px 44px;gap:3px 6px;align-items:center;padding-top:4px">';
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


def backup(p):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = p.with_suffix(p.suffix + f".bak-pre-chg-tiles-v2-{ts}")
    shutil.copy2(p, bak)
    print(f"  backup -> {bak.name}")


def main():
    print(f"Patching: {TARGET}")
    if not TARGET.exists():
        print(f"  ERROR: target not found")
        sys.exit(1)

    content = TARGET.read_text(encoding="utf-8")

    # Idempotency check
    if MARKER in content:
        print(f"  marker '{MARKER}' already present — patch already applied. Skipping.")
        sys.exit(0)

    if OLD_BLOCK not in content:
        print(f"  ERROR: old tile block not found verbatim. Either build_dashboard.py")
        print(f"  has been modified since this patcher was authored, or the block")
        print(f"  was already replaced. Aborting to avoid corruption.")
        # Aid debugging: report what part of the head matched
        head = OLD_BLOCK.split("\n")[0]
        if head in content:
            print(f"  (head line of old block IS present — partial drift likely)")
        sys.exit(1)

    n_matches = content.count(OLD_BLOCK)
    if n_matches != 1:
        print(f"  ERROR: old tile block matches {n_matches} times (must be exactly 1).")
        sys.exit(1)

    backup(TARGET)

    original_len = len(content)
    content = content.replace(OLD_BLOCK, NEW_BLOCK, 1)
    new_len = len(content)
    delta = new_len - original_len

    TARGET.write_text(content, encoding="utf-8")
    print(f"  wrote {new_len:,} bytes (was {original_len:,}, delta {delta:+,})")

    import py_compile
    try:
        py_compile.compile(str(TARGET), doraise=True)
        print("  py_compile: OK")
    except py_compile.PyCompileError as e:
        print(f"  py_compile FAILED: {e}")
        sys.exit(1)

    print(f"  done. Marker '{MARKER}' injected for future idempotency.")
    print("  Next: python scripts\\build_dashboard.py")


if __name__ == "__main__":
    main()
