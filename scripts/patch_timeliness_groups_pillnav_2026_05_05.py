#!/usr/bin/env python3
"""
Patcher: TIMELINESS tab -- column groups + pill-click navigation
D-MD-UI-17: Add group-header-row with 3 groups (INPUTS, MASTER, QUALIFICATION SCREENS)
D-MD-UI-18: Pill-click in Group 3 navigates to respective tab with stock at top

Follows D-MD-PROCESS-1 patcher discipline.
"""
import os, sys, shutil, datetime

SCRIPT = os.path.join(os.path.dirname(__file__), "build_dashboard.py")
if not os.path.isfile(SCRIPT):
    print("ERROR: build_dashboard.py not found at", SCRIPT)
    sys.exit(1)

src = open(SCRIPT, "r", encoding="utf-8").read()

# --- Idempotency check ---
if "TIMELINESS-GROUP-HEADER" in src:
    print("SKIP: patch already applied (TIMELINESS-GROUP-HEADER marker found)")
    sys.exit(0)

# --- Pre-write backup ---
ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
bak = SCRIPT + ".bak-pre-timeliness-groups-" + ts
shutil.copy2(SCRIPT, bak)
print("Backup:", bak)


# ============================================================
# STEP 1: Inject navBadge() + scrollToTicker() + event delegation
# ============================================================
# navBadge uses data attributes instead of inline onclick to avoid quote hell.
# Event delegation on document catches clicks on [data-nav-tab] badges.

ANCHOR_BADGE = (
    'function badge(s){if(!s)return\'<span class="badge badge-fail">&mdash;</span>\';'
    'if(s==="Capital")return\'<span class="badge badge-capital">Capital</span>\';'
    'if(s==="Late")return\'<span class="badge badge-late">Late</span>\';'
    'if(s==="Early")return\'<span class="badge badge-early">Early</span>\';'
    'return\'<span class="badge badge-fail">\'+s+\'</span>\'}'
)

assert src.count(ANCHOR_BADGE) == 1, f"badge() anchor count = {src.count(ANCHOR_BADGE)}"

INJECT_AFTER_BADGE = ANCHOR_BADGE + r"""
// D-MD-UI-18: Navigable badge for TIMELINESS Qualification Screens columns.
// Uses data-nav-tab + data-nav-ticker attributes; event delegation handles click.
function navBadge(stage,ticker,tabId){
  if(!stage)return'<span class="badge badge-fail">&mdash;</span>';
  var cls=stage==="Capital"?"badge-capital":stage==="Late"?"badge-late":stage==="Early"?"badge-early":"badge-fail";
  return'<span class="badge '+cls+' nav-badge" data-nav-tab="'+tabId+'" data-nav-ticker="'+ticker+'" title="Go to '+tabId.toUpperCase()+' tab" style="cursor:pointer">'+stage+'</span>';
}
// D-MD-UI-18: Scroll a ticker row to the top of the visible table on the active tab.
window.scrollToTicker=function(ticker){
  var active=document.querySelector('.tab-content[style*="display: block"], .tab-content[style*="display:block"]');
  if(!active)return;
  var rows=active.querySelectorAll('tr[data-ticker="'+ticker+'"]');
  if(rows.length===0)return;
  var target=rows[rows.length>1?1:0]; // prefer QS row (2nd) over LP row (1st) if both exist
  target.scrollIntoView({block:'start',behavior:'smooth'});
  target.style.transition='background 0.3s';target.style.background='rgba(221,107,32,0.18)';
  setTimeout(function(){target.style.background=''},2000);
};
// D-MD-UI-18: Event delegation for nav-badge clicks — switch tab + scroll to ticker.
document.addEventListener('click',function(e){
  var el=e.target.closest('.nav-badge[data-nav-tab]');
  if(!el)return;
  e.stopPropagation(); // prevent row-level openChart
  var tabId=el.getAttribute('data-nav-tab');
  var ticker=el.getAttribute('data-nav-ticker');
  switchTab(tabId);
  setTimeout(function(){scrollToTicker(ticker)},120);
});"""

src = src.replace(ANCHOR_BADGE, INJECT_AFTER_BADGE)
print("STEP 1: navBadge + scrollToTicker + event delegation injected")


# ============================================================
# STEP 2: Add data-ticker to ALL table rows (for scrollToTicker)
# ============================================================
# Pattern: onclick="openChart('TICKER')" style="cursor:pointer">
# We add data-ticker="TICKER" so scrollToTicker can find the row.

# Add data-ticker to ALL row patterns using exact string replacement per variant.
# Exact patterns extracted from the file (repr-verified).
total_dt = 0
for varexpr in ["r.ticker", "rk.ticker", "inv.ticker", "posRows[j].ticker"]:
    old = 'onclick="openChart(\\\'\'+'+ varexpr +'+\'\\\')" style="cursor:pointer">'
    new = 'onclick="openChart(\\\'\'+'+ varexpr +'+\'\\\')" style="cursor:pointer" data-ticker="\'+'+ varexpr +'+\'">'
    c_dt = src.count(old)
    if c_dt > 0:
        src = src.replace(old, new)
        print(f"STEP 2: data-ticker on '{varexpr}' rows: {c_dt} occurrences")
        total_dt += c_dt
print(f"STEP 2 total: {total_dt} rows patched")


# ============================================================
# STEP 3: QS table -- add group-header-row to TIMELINESS tab
# ============================================================

ANCHOR_QS = (
    """h+='<div class="data-table-wrap"><table class="data-table"><thead><tr>';\n"""
    """  // SESSION 9 Pass 1.1: Final col order per D-MD-FILTER-8"""
)

assert src.count(ANCHOR_QS) == 1, f"QS thead anchor count = {src.count(ANCHOR_QS)}"

REPLACE_QS = (
    """h+='<div class="data-table-wrap"><table class="data-table"><thead>';\n"""
    """  // TIMELINESS-GROUP-HEADER (D-MD-UI-17)\n"""
    """  h+='<tr class="group-header-row">';\n"""
    """  h+='<th colspan="10" style="background:rgba(100,100,100,0.06)">Inputs</th>';\n"""
    """  h+='<th colspan="1" style="background:rgba(221,107,32,0.12)">Master</th>';\n"""
    """  h+='<th colspan="8" style="background:rgba(120,80,200,0.08)">Qualification Screens</th>';\n"""
    """  h+=ratingsColHeaders().length>0?'<th colspan="8" class="col-ratings">Ratings</th>':'';\n"""
    """  h+='</tr><tr>';\n"""
    """  // SESSION 9 Pass 1.1: Final col order per D-MD-FILTER-8"""
)

src = src.replace(ANCHOR_QS, REPLACE_QS)
print("STEP 3: QS group-header-row applied")


# ============================================================
# STEP 4: LP table (combos branch) -- add group-header-row
# ============================================================
# The LP combos branch writes column headers into an already-open <tr>.
# We close that <tr>, emit group-header-row, then re-open <tr> for columns.

ANCHOR_LP = (
    """    h+=commonCols()\n"""
    """      +'<th class="col-txt col-filter">Timeliness</th>'\n"""
    """      +'<th class="col-txt col-filter combo-col-pending">Collapse</th>'\n"""
    """      +'<th class="col-txt col-filter">Basing Plateau</th>'"""
)

assert src.count(ANCHOR_LP) == 1, f"LP columns anchor count = {src.count(ANCHOR_LP)}"

REPLACE_LP = (
    """    // TIMELINESS-GROUP-HEADER LP (D-MD-UI-17)\n"""
    """    h+='</tr><tr class="group-header-row">';\n"""
    """    h+='<th colspan="10" style="background:rgba(100,100,100,0.06)">Inputs</th>';\n"""
    """    h+='<th colspan="1" style="background:rgba(221,107,32,0.12)">Master</th>';\n"""
    """    h+='<th colspan="8" style="background:rgba(120,80,200,0.08)">Qualification Screens</th>';\n"""
    """    h+=ratingsColHeaders().length>0?'<th colspan="8" class="col-ratings">Ratings</th>':'';\n"""
    """    h+='</tr><tr>';\n"""
    """    h+=commonCols()\n"""
    """      +'<th class="col-txt col-filter">Timeliness</th>'\n"""
    """      +'<th class="col-txt col-filter combo-col-pending">Collapse</th>'\n"""
    """      +'<th class="col-txt col-filter">Basing Plateau</th>'"""
)

src = src.replace(ANCHOR_LP, REPLACE_LP)
print("STEP 4: LP group-header-row applied")


# ============================================================
# STEP 5: QS rows -- badge() -> navBadge() for Group 3 columns
# ============================================================
# We replace badge(r.xx_stage) with navBadge(r.xx_stage,r.ticker,"tabId")
# in the renderCombos QS row block only.

QS_BADGE = (
    """+'<td class="col-txt col-filter">'+badge(r.bp_stage)+'</td>'\n"""
    """      +'<td class="col-txt col-filter">'+badge(r.pb_stage)+'</td>'\n"""
    """      +'<td class="col-txt col-filter">'+badge(r.vcp_stage)+'</td>'\n"""
    """      +'<td class="col-txt col-filter combo-col-pending">'+pendBadge+'</td>'\n"""
    """      +'<td class="col-txt col-filter combo-col-pending">'+pendBadge+'</td>'\n"""
    """      +'<td class="col-txt col-filter">'+badge(r.mm_stage)+'</td>'\n"""
    """      +'<td class="col-txt col-filter">'+badge(r.utr_stage)+'</td>'"""
)

QS_NAVBADGE = (
    """+'<td class="col-txt col-filter">'+navBadge(r.bp_stage,r.ticker,"bp")+'</td>'\n"""
    """      +'<td class="col-txt col-filter">'+navBadge(r.pb_stage,r.ticker,"pb")+'</td>'\n"""
    """      +'<td class="col-txt col-filter">'+navBadge(r.vcp_stage,r.ticker,"vcp")+'</td>'\n"""
    """      +'<td class="col-txt col-filter combo-col-pending">'+pendBadge+'</td>'\n"""
    """      +'<td class="col-txt col-filter combo-col-pending">'+pendBadge+'</td>'\n"""
    """      +'<td class="col-txt col-filter">'+navBadge(r.mm_stage,r.ticker,"mm99")+'</td>'\n"""
    """      +'<td class="col-txt col-filter">'+navBadge(r.utr_stage,r.ticker,"utr")+'</td>'"""
)

qs_count = src.count(QS_BADGE)
print(f"STEP 5: QS badge->navBadge block found {qs_count} time(s)")
assert qs_count >= 1, "QS badge block not found"
src = src.replace(QS_BADGE, QS_NAVBADGE)


# ============================================================
# STEP 6: LP rows (combos branch) -- badge() -> navBadge()
# ============================================================
# LP uses 'rk' variable and 'pendBadgeLP'

LP_BADGE = (
    """+'<td class="col-txt col-filter">'+badge(rk.bp_stage)+'</td>'\n"""
    """        +'<td class="col-txt col-filter">'+badge(rk.pb_stage)+'</td>'\n"""
    """        +'<td class="col-txt col-filter">'+badge(rk.vcp_stage)+'</td>'\n"""
    """        +'<td class="col-txt col-filter combo-col-pending">'+pendBadgeLP+'</td>'\n"""
    """        +'<td class="col-txt col-filter combo-col-pending">'+pendBadgeLP+'</td>'\n"""
    """        +'<td class="col-txt col-filter">'+badge(rk.mm_stage)+'</td>'\n"""
    """        +'<td class="col-txt col-filter">'+badge(rk.utr_stage)+'</td>'"""
)

LP_NAVBADGE = (
    """+'<td class="col-txt col-filter">'+navBadge(rk.bp_stage,rk.ticker,"bp")+'</td>'\n"""
    """        +'<td class="col-txt col-filter">'+navBadge(rk.pb_stage,rk.ticker,"pb")+'</td>'\n"""
    """        +'<td class="col-txt col-filter">'+navBadge(rk.vcp_stage,rk.ticker,"vcp")+'</td>'\n"""
    """        +'<td class="col-txt col-filter combo-col-pending">'+pendBadgeLP+'</td>'\n"""
    """        +'<td class="col-txt col-filter combo-col-pending">'+pendBadgeLP+'</td>'\n"""
    """        +'<td class="col-txt col-filter">'+navBadge(rk.mm_stage,rk.ticker,"mm99")+'</td>'\n"""
    """        +'<td class="col-txt col-filter">'+navBadge(rk.utr_stage,rk.ticker,"utr")+'</td>'"""
)

lp_count = src.count(LP_BADGE)
if lp_count >= 1:
    src = src.replace(LP_BADGE, LP_NAVBADGE)
    print(f"STEP 6: LP badge->navBadge block applied ({lp_count} time(s))")
else:
    print("STEP 6: LP badge block (rk variant) not found -- may share QS pattern")


# ============================================================
# WRITE
# ============================================================
with open(SCRIPT, "w", encoding="utf-8") as f:
    f.write(src)

sz = len(src)
print(f"\nWrote {sz:,} bytes to {SCRIPT}")
print("Patch complete. Run build_dashboard.py to regenerate index.html.")
