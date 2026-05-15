#!/usr/bin/env python3
# patch_md_v2_chart_wiring_2026_05_15.py
# -----------------------------------------------------------------------------
# Wires the existing chart panel onto the 9 MD V2 tabs.
#   - Clicking a company/ticker name-cell opens that stock's chart (the ONLY
#     chart entry point on V2 tabs; the legacy top-right "Chart" button is
#     hidden on V2 tabs via CSS).
#   - On V2 tabs the panel slides in from the LEFT; legacy tabs keep the right.
#   - The table shifts right (.main margin); the V2 ribbon and the Master
#     Overview frozen first column re-pin to the panel edge while open.
#   - Per-tab open defaults: Stage tabs open 2Y with 5D/10D MAs off; the other
#     V2 tabs open 6M with 5D/10D MAs on; everything else on. (Re-renders from
#     setChartZoom/setChartScaleMode do NOT reset the zoom.)
#   - Default width 50% (unchanged from legacy).
# Dashboard-only change. No pipeline / data change. Idempotent (MARKER guard).
# Authored against git-HEAD copy of build_dashboard.py; run Windows-side.
# Usage: python patch_md_v2_chart_wiring_2026_05_15.py [path-to-build_dashboard.py]
# -----------------------------------------------------------------------------
import sys, os, hashlib, time, py_compile

MARKER = "MD-CHART-V2-WIRING-MARKER"

OLD1 = """.chart-open .main{margin-right:25%;transition:margin-right .3s ease}"""

NEW1 = """.chart-open .main{margin-right:25%;transition:margin-right .3s ease,margin-left .3s ease}
/* MD-CHART-V2-WIRING-MARKER: chart panel slides in from the LEFT on V2 tabs (legacy keeps the right). */
body.chart-from-left .chart-panel{left:0;right:auto;border-left:none;border-right:1px solid var(--border);transform:translateX(-100%)}
body.chart-from-left .chart-panel.open{transform:translateX(0)}
#s1-main-table td.name-cell,#s2-main-table td.name-cell,#s3-main-table td.name-cell,#s4-main-table td.name-cell,#pi-main-table td.name-cell,#po-main-table td.name-cell,#st-main-table td.name-cell,#ct-main-table td.name-cell,#mo-matrix-table td.mo-mx-name-cell{cursor:pointer}
body[data-active-tab^="stage_"] #hdr-chart-btn,body[data-active-tab="pre_indicators"] #hdr-chart-btn,body[data-active-tab="post_indicators"] #hdr-chart-btn,body[data-active-tab="setups"] #hdr-chart-btn,body[data-active-tab="tests"] #hdr-chart-btn,body[data-active-tab="master_overview"] #hdr-chart-btn{display:none!important}
body.chart-from-left .s1-controls{left:var(--chart-panel-w,0)!important;transition:left .3s ease}
body.chart-from-left #mo-matrix-table tbody td.mo-mx-name-cell,body.chart-from-left #mo-matrix-table thead th.mo-mx-screen-col{left:var(--chart-panel-w,0)!important;transition:left .3s ease}"""

OLD2 = r'''<button class="ctrl-btn" onclick="openChart(\'Overview\')">Chart</button>'''
NEW2 = r'''<button class="ctrl-btn" id="hdr-chart-btn" onclick="openChart(\'Overview\')">Chart</button>'''

OLD3A = """  chartTicker=t;
  var p=document.getElementById("chart-panel");
  // Default chart width: 50%
  p.style.width="50%";
  p.classList.add("open");
  document.body.classList.add("chart-open");
  document.querySelector(".main").style.marginRight="50%";"""

NEW3A = """  var _prevChartTicker=chartTicker;
  chartTicker=t;
  var p=document.getElementById("chart-panel");
  // MD-CHART-V2-WIRING-MARKER: V2 tabs slide the chart panel in from the LEFT; legacy keeps the right.
  var _v2chartTabs={stage_1:1,stage_2:1,stage_3:1,stage_4:1,pre_indicators:1,post_indicators:1,setups:1,tests:1,master_overview:1};
  var _isV2chart=!!_v2chartTabs[currentTab];
  var _isStageChart=/^stage_[1-4]$/.test(currentTab);
  var _wasChartOpen=p.classList.contains("open");
  var _freshChart=(_prevChartTicker!==t)||!_wasChartOpen;
  var _bodyCl=document.body.classList;
  if(!_wasChartOpen||(_bodyCl.contains("chart-from-left")!==_isV2chart)){
    p.style.transition="none";
    if(_isV2chart)_bodyCl.add("chart-from-left");else _bodyCl.remove("chart-from-left");
    void p.offsetWidth;
    p.style.transition="";
  }
  // Default chart width: 50%
  p.style.width="50%";
  document.documentElement.style.setProperty("--chart-panel-w","50vw");
  p.classList.add("open");
  document.body.classList.add("chart-open");
  var _chartMain=document.querySelector(".main");
  if(_isV2chart){_chartMain.style.marginRight="0";_chartMain.style.marginLeft="50%";}
  else{_chartMain.style.marginLeft="0";_chartMain.style.marginRight="50%";}"""

OLD3B = """  if(currentTab==="pb"){chartVis.ma5=true;chartVis.ma10=true}else{chartVis.ma5=false;chartVis.ma10=false}"""

NEW3B = """  // MD-CHART-V2-WIRING-MARKER: 5D+10D MAs on for PB (legacy) + non-Stage V2 tabs; off elsewhere.
  if(currentTab==="pb"||(_isV2chart&&!_isStageChart)){chartVis.ma5=true;chartVis.ma10=true}else{chartVis.ma5=false;chartVis.ma10=false}
  // Fresh open from a V2 tab resets zoom + the always-on series to the per-tab defaults.
  if(_freshChart&&_isV2chart){
    chartZoom=_isStageChart?"2Y":"6M";
    chartVis.ma20=true;chartVis.ma50=true;chartVis.ma100=true;chartVis.ma150=true;chartVis.ma200=true;
    chartVis.obv=true;chartVis.vol=true;chartVis.vol20=true;chartVis.vol50=true;
  }"""

OLD4 = """window.closeChart=function(){
  document.getElementById("chart-panel").classList.remove("open");
  document.body.classList.remove("chart-open");
  document.querySelector(".main").style.marginRight="0";
};"""

NEW4 = """window.closeChart=function(){
  document.getElementById("chart-panel").classList.remove("open");
  document.body.classList.remove("chart-open");
  var _ccMain=document.querySelector(".main");
  _ccMain.style.marginRight="0";
  _ccMain.style.marginLeft="0";
  document.documentElement.style.setProperty("--chart-panel-w","0px");
};"""

OLD5 = """window.setChartWidth=function(p){
  var pn=document.getElementById("chart-panel");
  pn.style.width=p+"%";
  document.querySelector(".main").style.marginRight=p+"%";
  var b=document.querySelectorAll(".chart-width-btn");
  for(var j=0;j<b.length;j++)b[j].classList.remove("active");
  if(event&&event.target)event.target.classList.add("active");
  // Redraw chart at new panel width after transition
  if(chartTicker)setTimeout(function(){drawMasterChart(chartTicker)},350);
};"""

NEW5 = """window.setChartWidth=function(p){
  var pn=document.getElementById("chart-panel");
  pn.style.width=p+"%";
  document.documentElement.style.setProperty("--chart-panel-w",p+"vw");
  var _cwMain=document.querySelector(".main");
  if(document.body.classList.contains("chart-from-left")){_cwMain.style.marginLeft=p+"%";_cwMain.style.marginRight="0";}
  else{_cwMain.style.marginRight=p+"%";_cwMain.style.marginLeft="0";}
  var b=document.querySelectorAll(".chart-width-btn");
  for(var j=0;j<b.length;j++)b[j].classList.remove("active");
  if(event&&event.target)event.target.classList.add("active");
  // Redraw chart at new panel width after transition
  if(chartTicker)setTimeout(function(){drawMasterChart(chartTicker)},350);
};"""

OLD6 = """window.setChartScaleMode=function(m){
  if(m!=="lin"&&m!=="log")return;
  chartScaleMode=m;
  if(chartTicker)openChart(chartTicker);
};"""

NEW6 = """window.setChartScaleMode=function(m){
  if(m!=="lin"&&m!=="log")return;
  chartScaleMode=m;
  if(chartTicker)openChart(chartTicker);
};
// MD-CHART-V2-WIRING-MARKER: V2 tabs - clicking a company/ticker name-cell opens that stock's chart.
// This is the only chart entry point on V2 tabs (the header "Chart" button is hidden there via CSS).
document.addEventListener("click",function(e){
  var _v2ct={stage_1:1,stage_2:1,stage_3:1,stage_4:1,pre_indicators:1,post_indicators:1,setups:1,tests:1,master_overview:1};
  if(!_v2ct[document.body.getAttribute("data-active-tab")])return;
  var _nameCell=e.target.closest("td.name-cell, td.mo-mx-name-cell");
  if(!_nameCell)return;
  var _tkEl=_nameCell.querySelector(".tk, .mo-mx-tk");
  var _tk=_tkEl?(_tkEl.textContent||"").trim():"";
  if(_tk)openChart(_tk);
});"""

EDITS = [
    ("EDIT 1  CSS: left-slide variant + name-cell cursor + hide header Chart btn + ribbon/matrix re-pin", OLD1, NEW1),
    ("EDIT 2  header 'Chart' button gets id=hdr-chart-btn (so CSS can hide it on V2 tabs)", OLD2, NEW2),
    ("EDIT 3a openChart: V2 detection + left-side placement + table shift", OLD3A, NEW3A),
    ("EDIT 3b openChart: per-tab zoom + 5D/10D MA defaults", OLD3B, NEW3B),
    ("EDIT 4  closeChart: clear both margins + reset --chart-panel-w", OLD4, NEW4),
    ("EDIT 5  setChartWidth: side-aware margin + --chart-panel-w", OLD5, NEW5),
    ("EDIT 6  delegated name-cell click listener -> openChart", OLD6, NEW6),
]

def md5(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "build_dashboard.py")
    if not os.path.isfile(path):
        print("ERROR: target not found: %s" % path); sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    print("Target : %s" % path)
    print("Before : %d bytes  md5 %s" % (len(content.encode("utf-8")), md5(content)))

    if MARKER in content:
        print("Already patched (MARKER present) -- no-op, exiting clean.")
        sys.exit(0)

    for label, old, new in EDITS:
        n = content.count(old)
        if n != 1:
            print("ERROR: %s -- anchor found %d times (expected 1). Aborting, file untouched." % (label, n))
            sys.exit(2)
        content = content.replace(old, new, 1)
        print("  ok  %s" % label)

    mk = content.count(MARKER)
    if mk != 4:
        print("ERROR: MARKER count is %d (expected 4). Aborting, file untouched." % mk)
        sys.exit(3)

    tmp = path + ".tmp-chartwiring"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    try:
        py_compile.compile(tmp, doraise=True)
    except py_compile.PyCompileError as e:
        print("ERROR: patched file fails py_compile -- aborting. %s" % e)
        os.remove(tmp); sys.exit(4)

    bak = path + ".bak-pre-chart-v2-wiring-" + time.strftime("%Y%m%d-%H%M%S")
    with open(path, "r", encoding="utf-8") as f:
        orig = f.read()
    with open(bak, "w", encoding="utf-8") as f:
        f.write(orig)
    os.replace(tmp, path)

    with open(path, "r", encoding="utf-8") as f:
        final = f.read()
    print("After  : %d bytes  md5 %s" % (len(final.encode("utf-8")), md5(final)))
    print("Backup : %s" % bak)
    print("MARKER occurrences: %d   py_compile: OK" % final.count(MARKER))
    print("DONE -- 7 edits applied. Next: python scripts/build_dashboard.py")

if __name__ == "__main__":
    main()
