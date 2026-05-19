#!/usr/bin/env python3
"""
Patcher: CHANGES tab visual refinements (D-MD-UI-19 iteration)
4 changes:
  1. Column group border colours matching MM99 pattern (grp-*-first/last CSS)
  2. Column order confirmation (already 1M→1W→1D→Now — no change needed)
  3. Full filter names in group headers (BP→Basing Plateau, etc.)
  4. "Now" column emphasis — darker background, bolder text + header

Follows D-MD-PROCESS-1 patcher discipline.
"""
import os, sys, shutil, datetime

SCRIPT = os.path.join(os.path.dirname(__file__), "build_dashboard.py")
if not os.path.isfile(SCRIPT):
    print("ERROR: build_dashboard.py not found at", SCRIPT)
    sys.exit(1)

src = open(SCRIPT, "r", encoding="utf-8").read()

# --- Idempotency check ---
if "CHANGES-V2-MARKER" in src:
    print("SKIP: patch already applied (CHANGES-V2-MARKER found)")
    sys.exit(0)

# --- Pre-write backup ---
ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
bak = SCRIPT + ".bak-pre-changes-v2-" + ts
shutil.copy2(SCRIPT, bak)
print("Backup:", bak)


# ============================================================
# STEP 1: Add CSS for CHANGES tab column group borders + Now emphasis
# ============================================================
# Inject after the last grp-tight CSS block, before the col-num/col-txt rules.

ANCHOR_CSS = (
    'th.grp-tight-first,th.grp-tight-last{border-top:2px solid rgba(50,150,50,0.25)}\n'
    '\n'
    'table.data-table th.col-num'
)

# Colour assignments for 5 filter groups (matching group-header-row bg colours but at 0.25 alpha for borders):
# BP = green rgba(39,103,73)
# PB = purple rgba(107,70,193)
# MM99 = navy rgba(27,61,92)
# VCP = brown rgba(156,66,33)
# UTR = amber rgba(116,66,16)

REPLACE_CSS = (
    'th.grp-tight-first,th.grp-tight-last{border-top:2px solid rgba(50,150,50,0.25)}\n'
    '/* CHANGES-V2-MARKER: column group borders for CHANGES tab */\n'
    '.grp-chg-bp-first{border-left:2px solid rgba(39,103,73,0.25)}\n'
    '.grp-chg-bp-last{border-right:2px solid rgba(39,103,73,0.25)}\n'
    'th.grp-chg-bp-first,th.grp-chg-bp-last{border-top:2px solid rgba(39,103,73,0.25)}\n'
    '.grp-chg-pb-first{border-left:2px solid rgba(107,70,193,0.25)}\n'
    '.grp-chg-pb-last{border-right:2px solid rgba(107,70,193,0.25)}\n'
    'th.grp-chg-pb-first,th.grp-chg-pb-last{border-top:2px solid rgba(107,70,193,0.25)}\n'
    '.grp-chg-mm99-first{border-left:2px solid rgba(27,61,92,0.25)}\n'
    '.grp-chg-mm99-last{border-right:2px solid rgba(27,61,92,0.25)}\n'
    'th.grp-chg-mm99-first,th.grp-chg-mm99-last{border-top:2px solid rgba(27,61,92,0.25)}\n'
    '.grp-chg-vcp-first{border-left:2px solid rgba(156,66,33,0.25)}\n'
    '.grp-chg-vcp-last{border-right:2px solid rgba(156,66,33,0.25)}\n'
    'th.grp-chg-vcp-first,th.grp-chg-vcp-last{border-top:2px solid rgba(156,66,33,0.25)}\n'
    '.grp-chg-utr-first{border-left:2px solid rgba(116,66,16,0.25)}\n'
    '.grp-chg-utr-last{border-right:2px solid rgba(116,66,16,0.25)}\n'
    'th.grp-chg-utr-first,th.grp-chg-utr-last{border-top:2px solid rgba(116,66,16,0.25)}\n'
    '/* Now-column emphasis */\n'
    '.chg-now-cell{background:rgba(0,0,0,0.04)}\n'
    '.chg-now-cell .badge{font-weight:700}\n'
    'th.chg-now-th{font-weight:700}\n'
    '\n'
    'table.data-table th.col-num'
)

assert src.count(ANCHOR_CSS) == 1, f"CSS anchor count = {src.count(ANCHOR_CSS)}"
src = src.replace(ANCHOR_CSS, REPLACE_CSS)
print("STEP 1: CSS column group borders + Now emphasis added")


# ============================================================
# STEP 2: Update FILTER_COLS to full names
# ============================================================

ANCHOR_NAMES = 'var FILTER_COLS={"basing_plateau":"BP","probing_bet":"PB","mm99":"MM99","vcp":"VCP","uptrend_retest":"UTR"};'
REPLACE_NAMES = 'var FILTER_COLS={"basing_plateau":"Basing Plateau","probing_bet":"Probing Bet","mm99":"MM99","vcp":"VCP","uptrend_retest":"Uptrend Retest"};'

assert src.count(ANCHOR_NAMES) == 1, f"FILTER_COLS anchor count = {src.count(ANCHOR_NAMES)}"
src = src.replace(ANCHOR_NAMES, REPLACE_NAMES)
print("STEP 2: Full filter names in FILTER_COLS")


# ============================================================
# STEP 3: Update group-header-row to use border CSS classes via grp key map
# ============================================================
# The current group-header-row uses inline background but no CSS class for borders.
# We need to: (a) add a CSS class key per filter, (b) apply grp-chg-*-first/last to columns.

# Also add the GRP_CSS_KEY map and modify how column headers + data cells render.

# Replace the entire section from group-header-row through the data row rendering.

ANCHOR_TABLE = (
    "  // Group header row\n"
    "  h+='<tr class=\"group-header-row\">';\n"
    "  h+='<th colspan=\"3\" style=\"background:rgba(100,100,100,0.06)\">Inputs</th>';\n"
    "  FILTER_ORDER.forEach(function(f){\n"
    "    var lab=FILTER_COLS[f];\n"
    "    var bg=f===\"mm99\"?\"rgba(27,61,92,0.08)\":f===\"basing_plateau\"?\"rgba(39,103,73,0.08)\":f===\"probing_bet\"?\"rgba(107,70,193,0.08)\":f===\"vcp\"?\"rgba(156,66,33,0.08)\":\"rgba(116,66,16,0.08)\";\n"
    "    h+='<th colspan=\"4\" style=\"background:'+bg+'\">'+lab+'</th>';\n"
    "  });\n"
    "  h+='</tr>';\n"
    "\n"
    "  // Column header row\n"
    "  h+='<tr>';\n"
    "  h+='<th class=\"col-txt col-filter\">Ticker</th>';\n"
    "  h+='<th class=\"col-txt col-filter\">Sector</th>';\n"
    "  h+='<th class=\"col-txt col-filter\">Industry</th>';\n"
    "  FILTER_ORDER.forEach(function(f){\n"
    "    TIME_LABELS.forEach(function(tl){\n"
    "      h+='<th class=\"col-txt col-filter\" style=\"font-size:11px;min-width:44px\">'+tl+'</th>';\n"
    "    });\n"
    "  });\n"
    "  h+='</tr></thead><tbody>';"
)

REPLACE_TABLE = (
    "  // CSS key map for column group borders\n"
    "  var GRP_KEY={\"basing_plateau\":\"bp\",\"probing_bet\":\"pb\",\"mm99\":\"mm99\",\"vcp\":\"vcp\",\"uptrend_retest\":\"utr\"};\n"
    "\n"
    "  // Group header row\n"
    "  h+='<tr class=\"group-header-row\">';\n"
    "  h+='<th colspan=\"3\" style=\"background:rgba(100,100,100,0.06)\">Inputs</th>';\n"
    "  FILTER_ORDER.forEach(function(f){\n"
    "    var lab=FILTER_COLS[f];\n"
    "    var bg=f===\"mm99\"?\"rgba(27,61,92,0.08)\":f===\"basing_plateau\"?\"rgba(39,103,73,0.08)\":f===\"probing_bet\"?\"rgba(107,70,193,0.08)\":f===\"vcp\"?\"rgba(156,66,33,0.08)\":\"rgba(116,66,16,0.08)\";\n"
    "    var gk=GRP_KEY[f];\n"
    "    h+='<th colspan=\"4\" class=\"grp-chg-'+gk+'-first grp-chg-'+gk+'-last\" style=\"background:'+bg+'\">'+lab+'</th>';\n"
    "  });\n"
    "  h+='</tr>';\n"
    "\n"
    "  // Column header row\n"
    "  h+='<tr>';\n"
    "  h+='<th class=\"col-txt col-filter\">Ticker</th>';\n"
    "  h+='<th class=\"col-txt col-filter\">Sector</th>';\n"
    "  h+='<th class=\"col-txt col-filter\">Industry</th>';\n"
    "  FILTER_ORDER.forEach(function(f){\n"
    "    var gk=GRP_KEY[f];\n"
    "    TIME_LABELS.forEach(function(tl,ti){\n"
    "      var isFirst=(ti===0);var isLast=(ti===3);\n"
    "      var isNow=(ti===3);\n"
    "      var cls='col-txt col-filter';\n"
    "      if(isFirst)cls+=' grp-chg-'+gk+'-first';\n"
    "      if(isLast)cls+=' grp-chg-'+gk+'-last';\n"
    "      if(isNow)cls+=' chg-now-th';\n"
    "      h+='<th class=\"'+cls+'\" style=\"font-size:11px;min-width:44px\">'+tl+'</th>';\n"
    "    });\n"
    "  });\n"
    "  h+='</tr></thead><tbody>';"
)

assert src.count(ANCHOR_TABLE) == 1, f"Table header anchor count = {src.count(ANCHOR_TABLE)}"
src = src.replace(ANCHOR_TABLE, REPLACE_TABLE)
print("STEP 3: Group header row + column headers updated with border classes + Now emphasis")


# ============================================================
# STEP 4: Update data row cells with group border classes + Now emphasis
# ============================================================

ANCHOR_CELLS = (
    "    FILTER_ORDER.forEach(function(f){\n"
    "      var stages_at=[];\n"
    "      TIME_KEYS.forEach(function(tkey){\n"
    "        var tdata={\"T-22\":t22,\"T-5\":t5,\"T-1\":t1,\"T-0\":t0}[tkey];\n"
    "        var st=(tdata&&tdata[tk])?tdata[tk][f]:null;\n"
    "        stages_at.push(st);\n"
    "      });\n"
    "      // Render 4 cells with change highlighting\n"
    "      for(var ci=0;ci<4;ci++){\n"
    "        var st=stages_at[ci];\n"
    "        var prev_st=ci>0?stages_at[ci-1]:null;\n"
    "        var cellStyle='';\n"
    "        if(ci>0&&st!==prev_st){\n"
    "          var r0=stRank(st);var r1=stRank(prev_st);\n"
    "          if(r0>r1)cellStyle='background:rgba(56,161,105,0.15)';  // upgrade = green\n"
    "          else if(r0<r1)cellStyle='background:rgba(229,62,62,0.15)';  // downgrade = red\n"
    "        }\n"
    "        var badge_cls=st===\"Capital\"?\"badge-capital\":st===\"Late\"?\"badge-late\":st===\"Early\"?\"badge-early\":\"badge-fail\";\n"
    "        var badge_txt=st||'&mdash;';\n"
    "        h+='<td class=\"col-txt\" style=\"'+cellStyle+';text-align:center\"><span class=\"badge '+badge_cls+'\" style=\"font-size:10px\">'+badge_txt+'</span></td>';\n"
    "      }\n"
    "    });"
)

REPLACE_CELLS = (
    "    FILTER_ORDER.forEach(function(f){\n"
    "      var gk=GRP_KEY[f];\n"
    "      var stages_at=[];\n"
    "      TIME_KEYS.forEach(function(tkey){\n"
    "        var tdata={\"T-22\":t22,\"T-5\":t5,\"T-1\":t1,\"T-0\":t0}[tkey];\n"
    "        var st=(tdata&&tdata[tk])?tdata[tk][f]:null;\n"
    "        stages_at.push(st);\n"
    "      });\n"
    "      // Render 4 cells with change highlighting + group borders + Now emphasis\n"
    "      for(var ci=0;ci<4;ci++){\n"
    "        var st=stages_at[ci];\n"
    "        var prev_st=ci>0?stages_at[ci-1]:null;\n"
    "        var cellStyle='';\n"
    "        if(ci>0&&st!==prev_st){\n"
    "          var r0=stRank(st);var r1=stRank(prev_st);\n"
    "          if(r0>r1)cellStyle='background:rgba(56,161,105,0.15)';  // upgrade = green\n"
    "          else if(r0<r1)cellStyle='background:rgba(229,62,62,0.15)';  // downgrade = red\n"
    "        }\n"
    "        var isFirst=(ci===0);var isLast=(ci===3);var isNow=(ci===3);\n"
    "        var tdCls='col-txt';\n"
    "        if(isFirst)tdCls+=' grp-chg-'+gk+'-first';\n"
    "        if(isLast)tdCls+=' grp-chg-'+gk+'-last';\n"
    "        if(isNow)tdCls+=' chg-now-cell';\n"
    "        var badge_cls=st===\"Capital\"?\"badge-capital\":st===\"Late\"?\"badge-late\":st===\"Early\"?\"badge-early\":\"badge-fail\";\n"
    "        var badge_txt=st||'&mdash;';\n"
    "        h+='<td class=\"'+tdCls+'\" style=\"'+cellStyle+';text-align:center\"><span class=\"badge '+badge_cls+'\" style=\"font-size:10px\">'+badge_txt+'</span></td>';\n"
    "      }\n"
    "    });"
)

assert src.count(ANCHOR_CELLS) == 1, f"Data cells anchor count = {src.count(ANCHOR_CELLS)}"
src = src.replace(ANCHOR_CELLS, REPLACE_CELLS)
print("STEP 4: Data cells updated with group border classes + Now emphasis")


# ============================================================
# WRITE
# ============================================================
with open(SCRIPT, "w", encoding="utf-8") as f:
    f.write(src)

sz = len(src)
print(f"\nWrote {sz:,} bytes to {SCRIPT}")
print("Patch complete. Run build_dashboard.py to regenerate index.html.")
