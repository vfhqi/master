"""
patch_chart_phase4c_log_toggle_2026_05_04.py

Phase 4c: LIN/LOG y-axis toggle for chart price panel.

Spec recap:
- Toggle in own button group, placed RIGHT of width buttons with ~12px gap before zoom buttons.
- Default LIN (linear).
- Session-only persistence (resets on full page reload).
- Log applies to price y-axis ONLY. Volume + OBV stay linear (per Richard's Q3 confirmation + research note).
- Test stock: DUST-SE.

Changes:
1. Add `chartScaleMode='lin'` global state var (next to chartZoom).
2. Add `setChartScaleMode(m)` window function.
3. Replace `priceY` function inside drawMasterChart with one that switches lin/log.
4. Replace nice-tick generation with log-tick generation when in log mode.
5. Insert LIN/LOG button group in chart panel header, between width and zoom button groups,
   with explicit margin to create the visual gap Richard requested.
"""

import shutil
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "build_dashboard.py"
TS = datetime.now().strftime("%Y%m%d-%H%M%S")
BAK = SRC.with_suffix(f".py.bak-pre-chart-phase4c-{TS}")


def patch(src_text: str, find: str, replace: str, label: str) -> str:
    if find not in src_text:
        if replace in src_text:
            print(f"  [skip] {label}: already applied")
            return src_text
        raise SystemExit(f"  [FAIL] {label}: anchor not found")
    if src_text.count(find) > 1:
        raise SystemExit(f"  [FAIL] {label}: anchor not unique ({src_text.count(find)} matches)")
    print(f"  [ok]   {label}")
    return src_text.replace(find, replace)


def main():
    print(f"Reading: {SRC}")
    text = SRC.read_text(encoding="utf-8")
    print(f"  size: {len(text):,} bytes")
    print(f"Backup: {BAK}")
    shutil.copy2(SRC, BAK)

    # --- 1. Add chartScaleMode state var + setChartScaleMode setter ------
    text = patch(
        text,
        find='var chartZoom="2Y";',
        replace=(
            'var chartZoom="2Y";\n'
            '// PHASE-4C 2026-05-04: y-axis scale mode for price panel ("lin" or "log"). Session-only.\n'
            'var chartScaleMode="lin";'
        ),
        label="Add chartScaleMode global var",
    )

    # Add setter near setChartZoom.
    text = patch(
        text,
        find=(
            'window.setChartZoom=function(z){\n'
            '  chartZoom=z;\n'
            '  if(chartTicker)openChart(chartTicker);\n'
            '};'
        ),
        replace=(
            'window.setChartZoom=function(z){\n'
            '  chartZoom=z;\n'
            '  if(chartTicker)openChart(chartTicker);\n'
            '};\n'
            '// PHASE-4C 2026-05-04: set price-axis scale mode and re-render.\n'
            'window.setChartScaleMode=function(m){\n'
            '  if(m!=="lin"&&m!=="log")return;\n'
            '  chartScaleMode=m;\n'
            '  if(chartTicker)openChart(chartTicker);\n'
            '};'
        ),
        label="Add setChartScaleMode setter",
    )

    # --- 2. Insert LIN/LOG button group in chart panel header ------------
    # Anchor: end of width-buttons span + opening of zoom-buttons span.
    text = patch(
        text,
        find=(
            '  h+=\'</span>\';\n'
            '  h+=\'<span style="display:flex;gap:2px">\';\n'
            '  var zooms=["1M","3M","6M","12M","2Y","3Y","5Y"];'
        ),
        replace=(
            '  h+=\'</span>\';\n'
            '  // PHASE-4C 2026-05-04: LIN/LOG y-axis scale toggle. Own group with 12px gap on each side.\n'
            '  h+=\'<span style="display:flex;gap:2px;margin-left:12px;margin-right:12px">\';\n'
            '  var scales=[{k:"lin",l:"LIN"},{k:"log",l:"LOG"}];\n'
            '  for(var sci=0;sci<scales.length;sci++){\n'
            '    var sAct=scales[sci].k===chartScaleMode?" active":"";\n'
            '    h+=\'<button class="chart-width-btn\'+sAct+\'" onclick="setChartScaleMode(\\\'\'+scales[sci].k+\'\\\')">\'+scales[sci].l+\'</button>\';\n'
            '  }\n'
            '  h+=\'</span>\';\n'
            '  h+=\'<span style="display:flex;gap:2px">\';\n'
            '  var zooms=["1M","3M","6M","12M","2Y","3Y","5Y"];'
        ),
        label="Insert LIN/LOG button group between width and zoom buttons",
    )

    # --- 3. Replace priceY function + nice-tick generation with mode-aware variants ---
    # Anchor 1: the priceY function itself.
    text = patch(
        text,
        find=(
            '  function priceY(v){return pad.t+plotH*(1-(v-priceMin)/priceRange)}'
        ),
        replace=(
            '  // PHASE-4C 2026-05-04: priceY supports linear and log scales.\n'
            '  // Log path uses Math.log10; clipped at minimum positive value to avoid log(0).\n'
            '  function priceY(v){\n'
            '    if(chartScaleMode==="log"){\n'
            '      if(!(v>0))return pad.t+plotH;\n'
            '      var lv=Math.log10(v);\n'
            '      var lMin=Math.log10(priceMin>0?priceMin:0.01);\n'
            '      var lMax=Math.log10(priceMax>0?priceMax:1);\n'
            '      var lRange=lMax-lMin||1;\n'
            '      return pad.t+plotH*(1-(lv-lMin)/lRange);\n'
            '    }\n'
            '    return pad.t+plotH*(1-(v-priceMin)/priceRange);\n'
            '  }'
        ),
        label="Replace priceY with lin/log-aware variant",
    )

    # Anchor 2: the nice-tick generation block from Phase 4a — branch into log-tick path when mode=log.
    text = patch(
        text,
        find=(
            "  // PHASE-4A 2026-05-04: nice-number price ticks. priceMin/priceMax/priceRange recomputed.\n"
            "  // Use raw data extents (not pre-padded ones) so niceTicks creates its own headroom.\n"
            "  var priceLo=Math.min.apply(null,allVals);var priceHi=Math.max.apply(null,allVals);\n"
            "  var priceTickTarget=H>500?9:6;\n"
            "  var priceNT=niceTicks(priceLo,priceHi,priceTickTarget);\n"
            "  // Replace the earlier *0.98/*1.02 padded values so candles use the nice extents.\n"
            "  priceMin=priceNT.min;priceMax=priceNT.max;priceRange=priceMax-priceMin||1;\n"
            "  for(var pti=0;pti<priceNT.ticks.length;pti++){\n"
            "    var ptVal=priceNT.ticks[pti];var ptY=priceY(ptVal);\n"
            "    if(ptY<pad.t-1||ptY>pad.t+plotH+1)continue;\n"
            "    ctx.strokeStyle=gridCol;ctx.lineWidth=0.8;\n"
            "    ctx.beginPath();ctx.moveTo(pad.l,ptY);ctx.lineTo(W-pad.r,ptY);ctx.stroke();\n"
            "    var ptLabel=ptVal>=1000?Math.round(ptVal).toString():(ptVal<10?ptVal.toFixed(2):ptVal<100?ptVal.toFixed(1):Math.round(ptVal).toString());\n"
            "    ctx.fillStyle=textCol;ctx.font=\"13px monospace\";ctx.textAlign=\"left\";\n"
            "    ctx.fillText(ptLabel,W-pad.r+6,ptY+4);\n"
            "  }"
        ),
        replace=(
            "  // PHASE-4A 2026-05-04 + 4C 2026-05-04: nice-number ticks (linear mode) OR log ticks (log mode).\n"
            "  var priceLo=Math.min.apply(null,allVals);var priceHi=Math.max.apply(null,allVals);\n"
            "  var priceTickList;\n"
            "  if(chartScaleMode==='log'){\n"
            "    // Log mode: ticks at 1, 2, 5 within each decade between priceLo and priceHi.\n"
            "    var loSafe=priceLo>0?priceLo:0.01;\n"
            "    var hiSafe=priceHi>loSafe?priceHi:loSafe*1.1;\n"
            "    var minExp=Math.floor(Math.log10(loSafe));\n"
            "    var maxExp=Math.ceil(Math.log10(hiSafe));\n"
            "    priceTickList=[];\n"
            "    for(var e=minExp;e<=maxExp;e++){var base=Math.pow(10,e);[1,2,5].forEach(function(mult){var vv=mult*base;if(vv>=loSafe*0.95&&vv<=hiSafe*1.05)priceTickList.push(vv)})}\n"
            "    // Set priceMin/priceMax to the outer ticks so candles use the log extents.\n"
            "    priceMin=priceTickList.length>0?priceTickList[0]:loSafe;\n"
            "    priceMax=priceTickList.length>0?priceTickList[priceTickList.length-1]:hiSafe;\n"
            "    priceRange=priceMax-priceMin||1;\n"
            "  }else{\n"
            "    var priceTickTarget=H>500?9:6;\n"
            "    var priceNT=niceTicks(priceLo,priceHi,priceTickTarget);\n"
            "    priceMin=priceNT.min;priceMax=priceNT.max;priceRange=priceMax-priceMin||1;\n"
            "    priceTickList=priceNT.ticks;\n"
            "  }\n"
            "  for(var pti=0;pti<priceTickList.length;pti++){\n"
            "    var ptVal=priceTickList[pti];var ptY=priceY(ptVal);\n"
            "    if(ptY<pad.t-1||ptY>pad.t+plotH+1)continue;\n"
            "    ctx.strokeStyle=gridCol;ctx.lineWidth=0.8;\n"
            "    ctx.beginPath();ctx.moveTo(pad.l,ptY);ctx.lineTo(W-pad.r,ptY);ctx.stroke();\n"
            "    var ptLabel=ptVal>=1000?Math.round(ptVal).toString():(ptVal<10?ptVal.toFixed(2):ptVal<100?ptVal.toFixed(1):Math.round(ptVal).toString());\n"
            "    ctx.fillStyle=textCol;ctx.font=\"13px monospace\";ctx.textAlign=\"left\";\n"
            "    ctx.fillText(ptLabel,W-pad.r+6,ptY+4);\n"
            "  }"
        ),
        label="Branch price ticks to log-tick path when chartScaleMode='log'",
    )

    SRC.write_text(text, encoding="utf-8")
    print(f"\nWrote: {SRC}  ({SRC.stat().st_size:,} bytes)")
    print(f"Backup: {BAK}")
    tail = text[-200:]
    assert "if __name__ == \"__main__\":" in tail, "tail truncated"
    print("Tail check: OK")


if __name__ == "__main__":
    main()
