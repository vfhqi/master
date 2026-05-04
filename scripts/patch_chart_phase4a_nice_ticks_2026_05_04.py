"""
patch_chart_phase4a_nice_ticks_2026_05_04.py

Phase 4a: Nice-number y-axis ticks for price and volume.
- Adds niceNum() and niceTicks() helpers using {1, 2, 5} step set per Richard's spec
  (no 2.5 — keeps ticks even cleaner).
- Replaces price grid loop (line ~909) with nice-tick driven loop. priceMin/priceMax
  expanded slightly to nearest nice number for headroom.
- Replaces volume tick loop (line ~929-932) with nice-tick driven loop using same
  algorithm. volTickMax now derived from niceTicks rather than ad-hoc niceVolMax.
- Upgrades fmtVol() for B suffix and integer M (15M, not 15.0M).

Pre-write backup, anchor-string find+replace, idempotent.
"""

import shutil
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "build_dashboard.py"
TS = datetime.now().strftime("%Y%m%d-%H%M%S")
BAK = SRC.with_suffix(f".py.bak-pre-chart-phase4a-{TS}")


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

    # --- 1. Add niceNum + niceTicks helpers (place near fmtVol) ----------
    # Anchor: existing fmtVol definition.
    text = patch(
        text,
        find=(
            'function fmtVol(v){if(v>=1000000)return(v/1000000).toFixed(1)+"M";if(v>=1000)return(v/1000).toFixed(0)+"K";return v.toFixed(0)}'
        ),
        replace=(
            '// PHASE-4A 2026-05-04: nice-number tick algorithm (Heckbert 1990, {1,2,5} step set per Richard).\n'
            'function niceNum(range,round){if(range<=0)return 1;var exponent=Math.floor(Math.log10(range));var fraction=range/Math.pow(10,exponent);var nf;if(round){if(fraction<1.5)nf=1;else if(fraction<3.5)nf=2;else if(fraction<7.5)nf=5;else nf=10}else{if(fraction<=1)nf=1;else if(fraction<=2)nf=2;else if(fraction<=5)nf=5;else nf=10}return nf*Math.pow(10,exponent)}\n'
            'function niceTicks(min,max,maxTicks){if(!isFinite(min)||!isFinite(max)||max<=min)return{ticks:[min],min:min,max:max+1,step:1};var range=niceNum(max-min,false);var step=niceNum(range/(maxTicks-1),true);var nMin=Math.floor(min/step)*step;var nMax=Math.ceil(max/step)*step;var ticks=[];for(var t=nMin;t<=nMax+step/2;t+=step)ticks.push(t);return{ticks:ticks,min:nMin,max:nMax,step:step}}\n'
            '// PHASE-4A 2026-05-04: B suffix + integer M (15M, not 15.0M).\n'
            'function fmtVol(v){if(v==null)return"";var a=Math.abs(v);if(a>=1e9)return(v/1e9).toFixed(1)+"B";if(a>=1e6)return Math.round(v/1e6)+"M";if(a>=1e3)return Math.round(v/1e3)+"K";return Math.round(v).toString()}'
        ),
        label="Add niceNum + niceTicks helpers, upgrade fmtVol for B suffix",
    )

    # --- 2. Replace price grid loop with nice-tick driven loop -----------
    # Anchor: the existing 'Price grid' block.
    text = patch(
        text,
        find=(
            "  // Price grid\n"
            "  var gridCount=H>500?10:6;\n"
            "  for(var g=0;g<=gridCount;g++){\n"
            "    var gy=pad.t+plotH*g/gridCount;\n"
            "    ctx.strokeStyle=gridCol;ctx.lineWidth=0.8;\n"
            "    ctx.beginPath();ctx.moveTo(pad.l,gy);ctx.lineTo(W-pad.r,gy);ctx.stroke();\n"
            "    var gv=priceMax-(priceRange*g/gridCount);\n"
            "    ctx.fillStyle=textCol;ctx.font=\"13px monospace\";ctx.textAlign=\"left\";\n"
            "    ctx.fillText(gv.toFixed(gv<10?2:gv<100?1:0),W-pad.r+6,gy+4);\n"
            "  }"
        ),
        replace=(
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
        label="Replace price grid with nice-tick driven loop",
    )

    # --- 3. Replace volume axis ticks with nice-tick driven loop ---------
    # Anchor: niceVolMax + 4-tick loop.
    text = patch(
        text,
        find=(
            "  // Volume axis\n"
            "  function niceVolMax(v){if(v<=0)return 1;var mag=Math.pow(10,Math.floor(Math.log10(v)));var lead=v/mag;var nice;if(lead<=1)nice=1;else if(lead<=2)nice=2;else if(lead<=3)nice=3;else if(lead<=5)nice=5;else nice=10;return nice*mag}\n"
            "  var volTickMax=niceVolMax(volMax);\n"
            "  ctx.fillStyle=textCol;ctx.font=\"12px monospace\";ctx.textAlign=\"right\";\n"
            "  for(var vg=0;vg<=3;vg++){var vVal=volTickMax*vg/3;var vy=volY(vVal);ctx.fillText(fmtVol(vVal),pad.l-8,vy+4)}"
        ),
        replace=(
            "  // PHASE-4A 2026-05-04: volume axis uses niceTicks too. Volume always anchored at zero.\n"
            "  var volNT=niceTicks(0,volMax,4);\n"
            "  var volTickMax=volNT.max;\n"
            "  // Reassign volMax so the volY/volMALineY closures (declared above) pick up the nice-tick max.\n"
            "  // This keeps bar heights and tick positions in sync (avoids bars hugging zone top).\n"
            "  volMax=volTickMax;\n"
            "  ctx.fillStyle=textCol;ctx.font=\"12px monospace\";ctx.textAlign=\"right\";\n"
            "  for(var vti=0;vti<volNT.ticks.length;vti++){\n"
            "    var vVal=volNT.ticks[vti];var vy=volY(vVal);\n"
            "    if(vy<pad.t+plotH-volZoneH-1||vy>pad.t+plotH+1)continue;\n"
            "    ctx.fillText(fmtVol(vVal),pad.l-8,vy+4);\n"
            "  }"
        ),
        label="Replace volume tick loop with nice-tick driven loop",
    )

    # Write
    SRC.write_text(text, encoding="utf-8")
    print(f"\nWrote: {SRC}  ({SRC.stat().st_size:,} bytes)")
    print(f"Backup: {BAK}")
    tail = text[-200:]
    assert "if __name__ == \"__main__\":" in tail, "tail truncated -- aborting"
    print("Tail check: OK")


if __name__ == "__main__":
    main()
