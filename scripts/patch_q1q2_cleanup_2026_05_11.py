"""
Patcher H — Q1+Q2 cleanup (11-May-26)
=====================================

Two surgical edits:

Q1 — Replace cascade sort with sum-of-Capital-qualifications:
  * `chg_stage_cascade` virtual key dropped
  * New `chg_qual_count` virtual key = count of Capital-now across BP/PB/VCP/MM99/UTR
  * Default sort key + comparator + currentSort initial value all updated

Q2 — Filter label cosmetics:
  * FILTER_COLS dict: "mm99":"MM99" -> "MM 99"
                     "s3_topping":"S3 Topping" -> "Topping"
                     "s4_declining":"S4 Declining" -> "Declining"

Pre-write backup. Marker Q1Q2-CLEANUP-V1.

Usage (Windows-side):
  cd C:\\Users\\richb\\Documents\\COWORK\\master-dashboard
  python scripts\\patch_q1q2_cleanup_2026_05_11.py
  python scripts\\build_dashboard.py
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
TARGET = PROJECT_DIR / "scripts" / "build_dashboard.py"

MARKER = "Q1Q2-CLEANUP-V1"


def backup(p):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = p.with_suffix(p.suffix + f".bak-pre-q1q2-cleanup-{ts}")
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


# Q1 EDIT 1 — currentSort initial value
OLD_CURRENT_SORT = 'var currentTab="changes",currentSort={col:"chg_stage_cascade",dir:"desc"}; /* STAGE-MAIN-SUMMARY-V1-MARKER */'
NEW_CURRENT_SORT = 'var currentTab="changes",currentSort={col:"chg_qual_count",dir:"desc"}; /* ' + MARKER + ' */'


# Q1 EDIT 2 — Sort key construction and comparator block
OLD_SORT_BLOCK = '''  // STAGE-MAIN-SUMMARY-V1-MARKER — Build row objects with projected stage keys + 5-filter cascade rank
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

NEW_SORT_BLOCK = '''  // ''' + MARKER + ''' — Build row objects with projected stage keys + sum-of-Capital-qualifications rank
  var TIME_SUFFIXES=["1m","1w","1d","now"];
  // Sum-of-bits: count Capital qualifications across BP/PB/VCP/MM99/UTR.
  // Stocks qualified in more screens rank higher regardless of WHICH screens.
  var QUAL_FILTERS=["basing_plateau","probing_bet","vcp","mm99","uptrend_retest"];
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
    // Compute sum-of-bits qualification count (0-5 inclusive)
    var qualCount=0;
    QUAL_FILTERS.forEach(function(f){
      if(t0[tk] && t0[tk][f] === "Capital") qualCount++;
    });
    row.chg_qual_count = qualCount;
    chgRows.push(row);
  }
  // Sort: default uses chg_qual_count desc, ticker alpha as tiebreak. Explicit column sorts override.
  var _usingDefault=false;
  if(currentSort.col === "chg_qual_count"){
    chgRows.sort(function(a,b){
      if(a.chg_qual_count !== b.chg_qual_count) return b.chg_qual_count - a.chg_qual_count;
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
    chgRows.sort(function(a,b){
      if(a.chg_qual_count !== b.chg_qual_count) return b.chg_qual_count - a.chg_qual_count;
      return a.ticker < b.ticker ? -1 : 1;
    });
    _usingDefault=true;
  }
  // Sector-grouping toggle still applies — alpha-by-sector pass only when user explicitly enables it.'''


# Q2 — FILTER_COLS dict relabel
OLD_FILTER_COLS = '  var FILTER_COLS={"collapse":"Collapse","basing_plateau":"Basing Plateau","probing_bet":"Probing Bet","mm99":"MM99","vcp":"VCP","uptrend_retest":"Uptrend Retest","s3_topping":"S3 Topping","s4_declining":"S4 Declining"};'
NEW_FILTER_COLS = '  var FILTER_COLS={"collapse":"Collapse","basing_plateau":"Basing Plateau","probing_bet":"Probing Bet","mm99":"MM 99","vcp":"VCP","uptrend_retest":"Uptrend Retest","s3_topping":"Topping","s4_declining":"Declining"}; /* ' + MARKER + ' */'


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

    print("  Edit Q1-A: currentSort default = chg_qual_count")
    content = replace_once(content, OLD_CURRENT_SORT, NEW_CURRENT_SORT, "Q1-A")

    print("  Edit Q1-B: sort block replaced (cascade -> sum-of-bits)")
    content = replace_once(content, OLD_SORT_BLOCK, NEW_SORT_BLOCK, "Q1-B")

    print("  Edit Q2: FILTER_COLS labels normalised (MM 99, Topping, Declining)")
    content = replace_once(content, OLD_FILTER_COLS, NEW_FILTER_COLS, "Q2")

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
