"""
Patcher F — Terminology refactor + Summary Bar redesign + section title (11-May-26)
==================================================================================

Three logical edits (D-MD-UI-29, D-MD-UI-30, D-MD-UI-31):

EDIT 1 — Terminology refactor inside renderChanges() tile V3 block:
  * BAND_META labels:
      'Sustained Capital'              -> 'Sustained qualification'
      'Newly Capital — this week'      -> 'Newly qualified — this week'
      'Newly Capital — this month'     -> 'Newly qualified — this month'
      'Recently lost'                  -> 'Recently un-qualified'
      'Lost ≥ 1 month'                 -> 'Un-qualified ≥ 1 month'
  * Pill text in Month/Week columns (past qualification): 'IN' -> 'QUAL'
  * Pill text in Now column (current state):              'NOW' kept
  * Tile counter line:
      'Now N / -M' -> 'Qual N / Un-qual -M'
  * Empty-state copy:
      'No qualifying stocks in last month.' kept (already correct)
      'Filter logic pending (Pass 2 parked).' kept (already correct)

EDIT 2 — Section title rename + sub-label restructure:
  * 'Changes over last week — DD-Mon to DD-Mon (pipeline run DD-Mon)' becomes
    'CHANGES PER SCREEN/STAGE — DD-Mon to DD-Mon' with pipeline-run date
    as smaller right-aligned sub-label (keeps staleness warning).

EDIT 3 — Summary Bar re-pivoted from Capital/Late/Early to band aggregates:
  * Per-filter column shows: Qualified now (big) + +N week / +N month / -N un-qual
  * 'Multi-Qualification' box renamed 'Multi-Qualified Stocks'
  * Internal text "qualify for Capital in 2+ filters" -> "qualify in 2+ screens"

Pre-write backup. Idempotency marker TERMINOLOGY-V1-MARKER.

Usage (Windows-side):
  cd C:\\Users\\richb\\Documents\\COWORK\\master-dashboard
  python scripts\\patch_terminology_summary_2026_05_11.py
  python scripts\\build_dashboard.py
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
TARGET = PROJECT_DIR / "scripts" / "build_dashboard.py"

MARKER = "TERMINOLOGY-V1-MARKER"


def backup(p):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = p.with_suffix(p.suffix + f".bak-pre-terminology-{ts}")
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
# EDIT 1A — BAND_META labels (5 labels in one dict literal)
# ============================================================
OLD_BAND_META = """  // Band-level metadata: label, accent colour, default-visible
  var BAND_META = {
    1: {label:'Sustained Capital',  accent:'#276749', desc:'In all three periods'},
    2: {label:'Newly Capital — this week', accent:'#48bb78', desc:'Gained since last week'},
    3: {label:'Newly Capital — this month', accent:'#68d391', desc:'Gained within the month, still in'},
    4: {label:'Recently lost',       accent:'#e53e3e', desc:'Was Capital recently, no longer'},
    5: {label:'Lost ≥ 1 month',   accent:'#a0aec0', desc:'Was Capital a month ago, gone since'}
  };"""

NEW_BAND_META = """  // Band-level metadata: label, accent colour, default-visible — """ + MARKER + """
  var BAND_META = {
    1: {label:'Sustained qualification',  accent:'#276749', desc:'Qualified in all three periods'},
    2: {label:'Newly qualified — this week', accent:'#48bb78', desc:'Newly qualified since last week'},
    3: {label:'Newly qualified — this month', accent:'#68d391', desc:'Newly qualified within the month, still qualified'},
    4: {label:'Recently un-qualified',  accent:'#e53e3e', desc:'Was qualified recently, no longer'},
    5: {label:'Un-qualified ≥ 1 month',   accent:'#a0aec0', desc:'Was qualified a month ago, gone since'}
  };"""


# ============================================================
# EDIT 1B — Pill labels: IN/NOW in chgPill function
# ============================================================
OLD_CHGPILL = """  function chgPill(state, isPrimary){
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
  }"""

NEW_CHGPILL = """  function chgPill(state, isPrimary){
    // state: 'in' (qualified), 'out' (not qualified)
    if(state === 'out'){
      return '<span style="display:inline-block;min-width:38px;text-align:center;font-size:9px;color:#cbd5e0">—</span>';
    }
    var size = isPrimary ? {pad:'2px 8px',fs:'10px',mw:'44px'} : {pad:'1px 6px',fs:'9px',mw:'38px'};
    var bg = isPrimary ? '#1b3d5c' : '#276749';
    var fg = '#fff';
    var label = isPrimary ? 'NOW' : 'QUAL';
    var weight = isPrimary ? 800 : 700;
    return '<span style="display:inline-block;min-width:'+size.mw+';text-align:center;font-size:'+size.fs+';font-weight:'+weight+';padding:'+size.pad+';border-radius:3px;background:'+bg+';color:'+fg+';letter-spacing:.3px">'+label+'</span>';
  }"""


# ============================================================
# EDIT 1C — Tile header counter line: "Now N / -M" -> "Qual N / Un-qual -M"
# ============================================================
OLD_TILE_COUNTER = "    out += '<span style=\"font-size:11px;font-weight:500\"><span style=\"color:#1b3d5c\">Now ' + nNow + '</span> <span style=\"color:#a0aec0\">/</span> <span style=\"color:#9b2c2c\">-' + nGone + '</span></span>';"
NEW_TILE_COUNTER = "    out += '<span style=\"font-size:11px;font-weight:500\"><span style=\"color:#1b3d5c\">Qual ' + nNow + '</span> <span style=\"color:#a0aec0\">/</span> <span style=\"color:#9b2c2c\">Un-qual ' + nGone + '</span></span>';"


# ============================================================
# EDIT 1D — Tile body empty state copy
# ============================================================
OLD_EMPTY_BODY = "      out += '<div style=\"font-size:11px;color:var(--text-secondary);font-style:italic;padding:6px 0\">No qualifying stocks in last month.</div>';"
NEW_EMPTY_BODY = "      out += '<div style=\"font-size:11px;color:var(--text-secondary);font-style:italic;padding:6px 0\">No qualification activity in last month.</div>';"


# ============================================================
# EDIT 1E — Column header on body grid: "Now" stays, but ensure caption alignment
# ============================================================
# (no change needed; column headers already say MONTH / WEEK / NOW which is correct)


# ============================================================
# EDIT 2 — Section title (the long single-line h3 from Patcher A)
# ============================================================
OLD_SECTION_TITLE = """  var _ageDays=Math.round((new Date()-t0D)/86400000);var _ageNote=_ageDays<=1?'':_ageDays<=3?' &middot; <span style="color:#d69e2e">data '+_ageDays+'d old</span>':' &middot; <span style="color:#c53030;font-weight:700">data '+_ageDays+'d old &mdash; re-run pipeline</span>';h+='<h3 id="section-summary" style="margin:16px 0 8px;font-size:15px;font-weight:600;color:var(--text-primary)">Changes over last week &mdash; '+fmtDDM(t5D)+' to '+fmtDDM(t0D)+' <span style="font-size:11px;font-weight:400;color:var(--text-secondary)">(pipeline run '+fmtDDM(t0D)+')</span>'+_ageNote+'</h3>';"""

NEW_SECTION_TITLE = """  var _ageDays=Math.round((new Date()-t0D)/86400000);var _ageNote=_ageDays<=1?'':_ageDays<=3?' &middot; <span style="color:#d69e2e">data '+_ageDays+'d old</span>':' &middot; <span style="color:#c53030;font-weight:700">data '+_ageDays+'d old &mdash; re-run pipeline</span>';h+='<h3 id="section-summary" style="margin:16px 0 8px;font-size:15px;font-weight:700;color:var(--text-primary);letter-spacing:.4px;display:flex;align-items:baseline;justify-content:space-between;flex-wrap:wrap;gap:8px"><span>CHANGES PER SCREEN/STAGE <span style="font-weight:500;color:var(--text-secondary);font-size:13px">&mdash; '+fmtDDM(t5D)+' to '+fmtDDM(t0D)+'</span></span><span style="font-size:11px;font-weight:400;color:var(--text-secondary);text-align:right">pipeline run '+fmtDDM(t0D)+_ageNote+'</span></h3>';"""


# ============================================================
# EDIT 3 — Summary Bar re-pivot (band aggregates + Multi-Qualified Stocks rename)
# Replaces the per-filter Capital/Late/Early column block AND the multi-qual box.
# ============================================================
OLD_SUMMARY_BAR = """  // Build summary bar HTML
  var BG_MAP_SB={"collapse":"rgba(180,30,30,0.08)","basing_plateau":"rgba(39,103,73,0.08)","probing_bet":"rgba(107,70,193,0.08)","mm99":"rgba(27,61,92,0.08)","vcp":"rgba(156,66,33,0.08)","uptrend_retest":"rgba(116,66,16,0.08)","s3_topping":"rgba(200,100,0,0.08)","s4_declining":"rgba(150,20,20,0.08)"};
  h+='<div id="section-summarybar" style="display:flex;gap:12px;margin:12px 0;padding:10px 12px;background:var(--bg-secondary);border:1px solid var(--border);border-radius:8px;align-items:stretch">';
  // Left side: 8 filter columns (~65%)
  h+='<div style="display:flex;gap:1px;flex:7">';
  FILTER_ORDER.forEach(function(f){
    var lab=FILTER_COLS[f];
    var bg=BG_MAP_SB[f]||"rgba(100,100,100,0.08)";
    var sc=stageCounts[f];
    h+='<div style="flex:1;text-align:center;padding:6px 2px;border-radius:4px;background:'+bg+'">';
    h+='<div style="font-size:10px;font-weight:700;color:var(--text-primary);margin-bottom:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+lab+'</div>';
    h+='<div style="font-size:16px;font-weight:700;color:#38a169">'+sc.Capital+'</div>';
    h+='<div style="font-size:9px;color:var(--text-secondary);margin-bottom:3px">Capital</div>';
    h+='<div style="display:flex;justify-content:center;gap:8px">';
    h+='<div><span style="font-size:12px;font-weight:600;color:#d69e2e">'+sc.Late+'</span><div style="font-size:8px;color:var(--text-secondary)">Late</div></div>';
    h+='<div><span style="font-size:12px;font-weight:600;color:#dd6b20">'+sc.Early+'</span><div style="font-size:8px;color:var(--text-secondary)">Early</div></div>';
    h+='</div></div>';
  });
  h+='</div>';
  // Right side: Multi-qualification insight (~35%)
  h+='<div style="flex:3;padding:6px 10px;border-left:1px solid var(--border)">';
  h+='<div style="font-size:11px;font-weight:700;color:var(--text-primary);margin-bottom:6px">Multi-Qualification</div>';
  if(multiTickers.length===0){
    h+='<div style="font-size:11px;color:var(--text-secondary)">No stocks currently qualify for Capital across multiple filters.</div>';
  }else{
    h+='<div style="font-size:11px;color:var(--text-secondary);margin-bottom:4px"><strong>'+multiTickers.length+'</strong> stocks qualify for Capital in 2+ filters simultaneously.</div>';"""

NEW_SUMMARY_BAR = """  // """ + MARKER + """ — Build summary bar HTML (band-aggregate digest)
  var BG_MAP_SB={"collapse":"rgba(180,30,30,0.08)","basing_plateau":"rgba(39,103,73,0.08)","probing_bet":"rgba(107,70,193,0.08)","mm99":"rgba(27,61,92,0.08)","vcp":"rgba(156,66,33,0.08)","uptrend_retest":"rgba(116,66,16,0.08)","s3_topping":"rgba(200,100,0,0.08)","s4_declining":"rgba(150,20,20,0.08)"};
  // Pre-compute band aggregates per filter (mirrors chgClassify logic in tiles)
  var bandAgg={};
  FILTER_ORDER.forEach(function(f){bandAgg[f]={qual:0, newW:0, newM:0, lostW:0, lostM:0};});
  for(var tk_sb in t0){
    FILTER_ORDER.forEach(function(f){
      var c0  = t0[tk_sb]  && t0[tk_sb][f]  === "Capital";
      var c5  = t5[tk_sb]  && t5[tk_sb][f]  === "Capital";
      var c22 = t22[tk_sb] && t22[tk_sb][f] === "Capital";
      if(c0) bandAgg[f].qual++;
      if(c0 && !c5 && !c22) bandAgg[f].newW++;
      else if(c0 && c5 && !c22) bandAgg[f].newM++;
      if(!c0 && c5) bandAgg[f].lostW++;
      else if(!c0 && !c5 && c22) bandAgg[f].lostM++;
    });
  }
  h+='<div id="section-summarybar" style="display:flex;gap:12px;margin:12px 0;padding:10px 12px;background:var(--bg-secondary);border:1px solid var(--border);border-radius:8px;align-items:stretch">';
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
  h+='</div>';
  // Right side: Multi-Qualified Stocks (~35%)
  h+='<div style="flex:3;padding:6px 10px;border-left:1px solid var(--border)">';
  h+='<div style="font-size:11px;font-weight:700;color:var(--text-primary);margin-bottom:6px">Multi-Qualified Stocks</div>';
  if(multiTickers.length===0){
    h+='<div style="font-size:11px;color:var(--text-secondary)">No stocks currently qualify in multiple screens.</div>';
  }else{
    h+='<div style="font-size:11px;color:var(--text-secondary);margin-bottom:4px"><strong>'+multiTickers.length+'</strong> stocks qualify in 2+ screens simultaneously.</div>';"""


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

    print("  Edit 1A: BAND_META labels (qualification verb-form)")
    content = replace_once(content, OLD_BAND_META, NEW_BAND_META, "Edit 1A")

    print("  Edit 1B: chgPill IN -> QUAL")
    content = replace_once(content, OLD_CHGPILL, NEW_CHGPILL, "Edit 1B")

    print("  Edit 1C: tile counter 'Now N / -M' -> 'Qual N / Un-qual -M'")
    content = replace_once(content, OLD_TILE_COUNTER, NEW_TILE_COUNTER, "Edit 1C")

    print("  Edit 1D: empty-state copy")
    content = replace_once(content, OLD_EMPTY_BODY, NEW_EMPTY_BODY, "Edit 1D")

    print("  Edit 2: section title CHANGES PER SCREEN/STAGE")
    content = replace_once(content, OLD_SECTION_TITLE, NEW_SECTION_TITLE, "Edit 2")

    print("  Edit 3: Summary Bar re-pivot to band aggregates + Multi-Qualified Stocks")
    content = replace_once(content, OLD_SUMMARY_BAR, NEW_SUMMARY_BAR, "Edit 3")

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
