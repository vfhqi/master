"""
patch_chart_phase4d_log_tick_fix_2026_05_04.py

Phase 4d: Fix log-tick generation for tight ranges.

Problem (observed in Phase 4c verification):
- AKER-NO 5Y log mode: y-axis showed no tick labels (ticker last-close annotations only)
- AZN-GB 1M log mode: same — no y-axis ticks visible

Root cause:
The Phase 4c log-tick generator only produces ticks at {1, 2, 5} * 10^N. For tight
price ranges (e.g. 13239-14608 for AZN at 1M zoom) there are no decade-multiple
ticks that fall inside the range. Result: priceTickList is empty, no horizontal
gridlines drawn, no labels rendered.

Fix:
Two-stage tick generation:
1. Try the {1, 2, 5} log ticks. If we get >=2 ticks, use them.
2. Otherwise, fall back to a denser {1, 1.5, 2, 3, 5, 7} sub-tick set.
3. If still <2 ticks, fall back to the linear nice-tick algorithm — even in log
   visualisation mode, having tick labels is more important than perfect log spacing.

Also: clip priceMin/priceMax to actual data extents (don't expand to ±10% of the
nearest decade boundary, which was making the chart compress unnecessarily).
"""

import shutil
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "build_dashboard.py"
TS = datetime.now().strftime("%Y%m%d-%H%M%S")
BAK = SRC.with_suffix(f".py.bak-pre-chart-phase4d-{TS}")


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

    # Replace the log-mode tick generation block with denser fallbacks.
    text = patch(
        text,
        find=(
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
        ),
        replace=(
            "  if(chartScaleMode==='log'){\n"
            "    // PHASE-4D 2026-05-04: log-tick generation with cascading fallbacks for tight ranges.\n"
            "    var loSafe=priceLo>0?priceLo:0.01;\n"
            "    var hiSafe=priceHi>loSafe?priceHi:loSafe*1.1;\n"
            "    // priceMin/priceMax track the ACTUAL data extents (not snapped to decades),\n"
            "    // so the chart fills the available height regardless of where ticks land.\n"
            "    priceMin=loSafe*0.97;priceMax=hiSafe*1.03;priceRange=priceMax-priceMin||1;\n"
            "    var minExp=Math.floor(Math.log10(loSafe));\n"
            "    var maxExp=Math.ceil(Math.log10(hiSafe));\n"
            "    function _logTicks(mults){var out=[];for(var ee=minExp;ee<=maxExp;ee++){var base=Math.pow(10,ee);for(var mi2=0;mi2<mults.length;mi2++){var vv=mults[mi2]*base;if(vv>=priceMin&&vv<=priceMax)out.push(vv)}}return out}\n"
            "    // Cascade: coarse {1,2,5} -> medium {1,1.5,2,3,5,7} -> dense {1..9}.\n"
            "    priceTickList=_logTicks([1,2,5]);\n"
            "    if(priceTickList.length<3)priceTickList=_logTicks([1,1.5,2,3,5,7]);\n"
            "    if(priceTickList.length<3)priceTickList=_logTicks([1,2,3,4,5,6,7,8,9]);\n"
            "    // Final fallback: if STILL no ticks (price range smaller than one decade with no integer multipliers),\n"
            "    // compute linear nice-ticks and use those even in log-render mode. Labels are the priority.\n"
            "    if(priceTickList.length<2){\n"
            "      var fbNT=niceTicks(priceLo,priceHi,H>500?9:6);\n"
            "      priceTickList=fbNT.ticks;\n"
            "    }\n"
            "  }else{\n"
        ),
        label="Replace log-tick generation with cascading fallbacks",
    )

    SRC.write_text(text, encoding="utf-8")
    print(f"\nWrote: {SRC}  ({SRC.stat().st_size:,} bytes)")
    print(f"Backup: {BAK}")
    tail = text[-200:]
    assert "if __name__ == \"__main__\":" in tail, "tail truncated"
    print("Tail check: OK")


if __name__ == "__main__":
    main()
