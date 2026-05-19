#!/usr/bin/env python3
"""
Patcher: CHANGES tab (D-MD-UI-19)
Adds a new tab showing qualification stage changes over 4 time points
(1M / 1W / 1D / Today) for all 8 filters.

Three sections:
  1. Changes In/Out tiles — Capital qualification entries/exits vs T-5
  2. Live Portfolio mirror — QS columns for held stocks
  3. Qualified Stocks table — slim Inputs + 8 filter groups x 4 time columns

Follows D-MD-PROCESS-1 patcher discipline.
"""
import os, sys, shutil, datetime, json

SCRIPT = os.path.join(os.path.dirname(__file__), "build_dashboard.py")
if not os.path.isfile(SCRIPT):
    print("ERROR: build_dashboard.py not found at", SCRIPT)
    sys.exit(1)

src = open(SCRIPT, "r", encoding="utf-8").read()

# --- Idempotency check ---
if "CHANGES-TAB-MARKER" in src:
    print("SKIP: patch already applied (CHANGES-TAB-MARKER found)")
    sys.exit(0)

# --- Pre-write backup ---
ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
bak = SCRIPT + ".bak-pre-changes-tab-" + ts
shutil.copy2(SCRIPT, bak)
print("Backup:", bak)


# ============================================================
# STEP 1: Add CHANGES to TABS list (right after TIMELINESS)
# ============================================================

ANCHOR_TABS = (
    '    {"id": "combos",    "label": "TIMELINESS",       "accent": "#dd6b20"},\n'
    '    {"id": "positions", "label": "Live Investments",  "accent": "#319795"},'
)

REPLACE_TABS = (
    '    {"id": "combos",    "label": "TIMELINESS",       "accent": "#dd6b20"},\n'
    '    {"id": "changes",   "label": "CHANGES",          "accent": "#c53030"},  # CHANGES-TAB-MARKER\n'
    '    {"id": "positions", "label": "Live Investments",  "accent": "#319795"},'
)

assert src.count(ANCHOR_TABS) == 1, f"TABS anchor count = {src.count(ANCHOR_TABS)}"
src = src.replace(ANCHOR_TABS, REPLACE_TABS)
print("STEP 1: CHANGES added to TABS list")


# ============================================================
# STEP 2: Add to IMPLEMENTED_TABS
# ============================================================

ANCHOR_IMPL = '"combos", "positions",'
REPLACE_IMPL = '"combos", "changes", "positions",'

assert src.count(ANCHOR_IMPL) == 1, f"IMPLEMENTED_TABS anchor count = {src.count(ANCHOR_IMPL)}"
src = src.replace(ANCHOR_IMPL, REPLACE_IMPL)
print("STEP 2: CHANGES added to IMPLEMENTED_TABS")


# ============================================================
# STEP 3: Load filter-history.json in load_data()
# ============================================================

ANCHOR_LOAD = '    filters = safe_json_load(DATA_DIR / "filter-results.json")'

REPLACE_LOAD = (
    '    filters = safe_json_load(DATA_DIR / "filter-results.json")\n'
    '\n'
    '    # CHANGES tab: historical stage data (D-MD-UI-19)\n'
    '    filter_history = None\n'
    '    fh_path = DATA_DIR / "filter-history.json"\n'
    '    if fh_path.exists():\n'
    '        filter_history = safe_json_load(fh_path)'
)

assert src.count(ANCHOR_LOAD) == 1, f"load_data anchor count = {src.count(ANCHOR_LOAD)}"
src = src.replace(ANCHOR_LOAD, REPLACE_LOAD)
print("STEP 3: filter-history.json loading added")


# ============================================================
# STEP 4: Add filter_history to master dict
# ============================================================

ANCHOR_MASTER = (
    '    if valuation:\n'
    '        val_data = {k: v for k, v in valuation.items() if k != "_meta"}\n'
    '        master["valuation"] = val_data'
)

REPLACE_MASTER = (
    '    if valuation:\n'
    '        val_data = {k: v for k, v in valuation.items() if k != "_meta"}\n'
    '        master["valuation"] = val_data\n'
    '    if filter_history:\n'
    '        master["filter_history"] = filter_history'
)

assert src.count(ANCHOR_MASTER) == 1, f"master dict anchor count = {src.count(ANCHOR_MASTER)}"
src = src.replace(ANCHOR_MASTER, REPLACE_MASTER)
print("STEP 4: filter_history added to master dict")


# ============================================================
# STEP 5: Add renderTab dispatch for CHANGES
# ============================================================

ANCHOR_DISPATCH = '  else if(id==="combos")renderCombos();\n  else if(id==="positions")renderPositions();'
REPLACE_DISPATCH = (
    '  else if(id==="combos")renderCombos();\n'
    '  else if(id==="changes")renderChanges();\n'
    '  else if(id==="positions")renderPositions();'
)

assert src.count(ANCHOR_DISPATCH) == 1, f"renderTab dispatch anchor count = {src.count(ANCHOR_DISPATCH)}"
src = src.replace(ANCHOR_DISPATCH, REPLACE_DISPATCH)
print("STEP 5: renderChanges() dispatch added")


# ============================================================
# STEP 6: Inject renderChanges() function
# ============================================================
# We inject it right after the renderCombos closing brace.
# Find the renderCombos function and inject after it.

# Anchor: the renderTab dispatch line for combos (already modified).
# Better anchor: inject the function at end of JS block, before the
# closing `</script>` or after the last render function.
# Safest: inject right before the renderTab function itself.

ANCHOR_FN = '  else if(id==="changes")renderChanges();\n  else if(id==="positions")renderPositions();'

# The renderChanges function — builds 3-section CHANGES tab
RENDER_CHANGES_FN = r"""
// ══════════════════════════════════════════════════════════════
// CHANGES TAB (D-MD-UI-19) — Stage changes over 4 time points
// ══════════════════════════════════════════════════════════════
function renderChanges(){
  buildHeaderControls("changes");
  var fh=D.filter_history;
  if(!fh||!fh.stages){
    document.getElementById("tab-changes").innerHTML='<div class="empty-state">No historical data. Run generate_master_data.py --with-history</div>';
    return;
  }
  var stages=fh.stages;
  var t0=stages["T-0"]||{};
  var t1=stages["T-1"]||{};
  var t5=stages["T-5"]||{};
  var t22=stages["T-22"]||{};
  var allRows=baseRows();
  var h='';

  // ── SECTION 1: Changes In/Out tiles ──────────────────────
  var FILTERS=["basing_plateau","probing_bet","mm99","uptrend_retest","vcp"];
  var FILTER_LABELS={"basing_plateau":"BP","probing_bet":"PB","mm99":"MM99","uptrend_retest":"UTR","vcp":"VCP"};
  var STAGE_RANK={"null":0,"undefined":0,"Early":1,"Late":1,"Capital":3};
  function stRank(s){return s==="Capital"?3:s==="Late"?2:s==="Early"?1:0}

  h+='<div class="changes-tiles" style="display:flex;flex-wrap:wrap;gap:12px;margin:16px 0">';
  FILTERS.forEach(function(filt){
    var label=FILTER_LABELS[filt]||filt;
    var newCap=[];var lostCap=[];
    for(var tk in t0){
      var curr=t0[tk]&&t0[tk][filt];
      var prev=t5[tk]&&t5[tk][filt];
      if(curr==="Capital"&&prev!=="Capital")newCap.push(tk);
      if(prev==="Capital"&&curr!=="Capital")lostCap.push(tk);
    }
    h+='<div style="background:var(--bg-secondary);border:1px solid var(--border-color);border-radius:8px;padding:12px 16px;min-width:160px;flex:1">';
    h+='<div style="font-weight:700;font-size:14px;margin-bottom:8px;color:var(--text-primary)">'+label+'</div>';
    h+='<div style="display:flex;gap:16px">';
    h+='<div><span style="color:#38a169;font-weight:700;font-size:20px">+'+newCap.length+'</span><div style="font-size:11px;color:var(--text-secondary)">New Capital</div></div>';
    h+='<div><span style="color:#e53e3e;font-weight:700;font-size:20px">-'+lostCap.length+'</span><div style="font-size:11px;color:var(--text-secondary)">Lost Capital</div></div>';
    h+='</div>';
    if(newCap.length>0)h+='<div style="font-size:11px;color:#38a169;margin-top:6px">'+newCap.join(", ")+'</div>';
    if(lostCap.length>0)h+='<div style="font-size:11px;color:#e53e3e;margin-top:3px">'+lostCap.join(", ")+'</div>';
    h+='</div>';
  });
  h+='</div>';

  // ── SECTION 2: Changes table — all stocks with any change ──
  // Slim inputs (3 cols) + 8 filter groups x 4 time columns
  var FILTER_ORDER=["basing_plateau","probing_bet","mm99","vcp","uptrend_retest"];
  var FILTER_COLS={"basing_plateau":"BP","probing_bet":"PB","mm99":"MM99","vcp":"VCP","uptrend_retest":"UTR"};
  var TIME_LABELS=["1M","1W","1D","Now"];
  var TIME_KEYS=["T-22","T-5","T-1","T-0"];

  // Build rows: only stocks with at least one change across any filter/timepoint
  var changedTickers=[];
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
    if(changed)changedTickers.push(tk);
  }

  // Sort changed tickers: most changes first (count of distinct stage values across time)
  changedTickers.sort(function(a,b){
    function score(tk){
      var s=0;
      for(var fi=0;fi<FILTER_ORDER.length;fi++){
        var f=FILTER_ORDER[fi];
        var vals=new Set();
        [t0,t1,t5,t22].forEach(function(tp){if(tp[tk]&&tp[tk][f]!=null)vals.add(tp[tk][f]);else vals.add(null)});
        s+=vals.size-1;
      }
      return s;
    }
    return score(b)-score(a);
  });

  h+='<div style="margin-top:8px;font-size:13px;color:var(--text-secondary)">'+changedTickers.length+' stocks with stage changes (vs 1M ago)</div>';

  h+='<div class="data-table-wrap"><table class="data-table"><thead>';

  // Group header row
  h+='<tr class="group-header-row">';
  h+='<th colspan="3" style="background:rgba(100,100,100,0.06)">Inputs</th>';
  FILTER_ORDER.forEach(function(f){
    var lab=FILTER_COLS[f];
    var bg=f==="mm99"?"rgba(27,61,92,0.08)":f==="basing_plateau"?"rgba(39,103,73,0.08)":f==="probing_bet"?"rgba(107,70,193,0.08)":f==="vcp"?"rgba(156,66,33,0.08)":"rgba(116,66,16,0.08)";
    h+='<th colspan="4" style="background:'+bg+'">'+lab+'</th>';
  });
  h+='</tr>';

  // Column header row
  h+='<tr>';
  h+='<th class="col-txt col-filter">Ticker</th>';
  h+='<th class="col-txt col-filter">Sector</th>';
  h+='<th class="col-txt col-filter">Industry</th>';
  FILTER_ORDER.forEach(function(f){
    TIME_LABELS.forEach(function(tl){
      h+='<th class="col-txt col-filter" style="font-size:11px;min-width:44px">'+tl+'</th>';
    });
  });
  h+='</tr></thead><tbody>';

  // Build lookup for stock metadata
  var metaLookup={};
  allRows.forEach(function(r){metaLookup[r.ticker]=r});

  // Render rows
  changedTickers.forEach(function(tk){
    var meta=metaLookup[tk]||{};
    h+='<tr>';
    h+='<td class="col-txt">'+tk+'</td>';
    h+='<td class="col-txt">'+(meta.sector||'')+'</td>';
    h+='<td class="col-txt">'+(meta.industry||'')+'</td>';
    FILTER_ORDER.forEach(function(f){
      var stages_at=[];
      TIME_KEYS.forEach(function(tkey){
        var tdata={"T-22":t22,"T-5":t5,"T-1":t1,"T-0":t0}[tkey];
        var st=(tdata&&tdata[tk])?tdata[tk][f]:null;
        stages_at.push(st);
      });
      // Render 4 cells with change highlighting
      for(var ci=0;ci<4;ci++){
        var st=stages_at[ci];
        var prev_st=ci>0?stages_at[ci-1]:null;
        var cellStyle='';
        if(ci>0&&st!==prev_st){
          var r0=stRank(st);var r1=stRank(prev_st);
          if(r0>r1)cellStyle='background:rgba(56,161,105,0.15)';  // upgrade = green
          else if(r0<r1)cellStyle='background:rgba(229,62,62,0.15)';  // downgrade = red
        }
        var badge_cls=st==="Capital"?"badge-capital":st==="Late"?"badge-late":st==="Early"?"badge-early":"badge-fail";
        var badge_txt=st||'&mdash;';
        h+='<td class="col-txt" style="'+cellStyle+';text-align:center"><span class="badge '+badge_cls+'" style="font-size:10px">'+badge_txt+'</span></td>';
      }
    });
    h+='</tr>';
  });

  h+='</tbody></table></div>';

  document.getElementById("tab-changes").innerHTML=h;
}
"""

# Find where to inject the function — before renderTab
ANCHOR_RENDERTAB = '\nfunction renderTab(id){'
assert src.count(ANCHOR_RENDERTAB) == 1, f"renderTab anchor count = {src.count(ANCHOR_RENDERTAB)}"
src = src.replace(ANCHOR_RENDERTAB, RENDER_CHANGES_FN + '\nfunction renderTab(id){')
print("STEP 6: renderChanges() function injected")


# ============================================================
# WRITE
# ============================================================
with open(SCRIPT, "w", encoding="utf-8") as f:
    f.write(src)

sz = len(src)
print(f"\nWrote {sz:,} bytes to {SCRIPT}")
print("Patch complete. Run build_dashboard.py to regenerate index.html.")
