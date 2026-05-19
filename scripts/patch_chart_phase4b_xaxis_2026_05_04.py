"""
patch_chart_phase4b_xaxis_2026_05_04.py

Phase 4b: Cleaner x-axis with major/minor gridline hierarchy + adaptive date labels.

Strategy:
- Determine zoom tier from `n` (number of bars visible).
- Major gridlines: anchor on the next-coarser unit than the label tier.
- Minor gridlines: anchor on the label tier itself, lighter weight, no labels.
- Single label row (avoid the current double-row "23-Apr / APRIL" overlap).

Tier table (per research note Section 2):
  bars       | major grid     | major label      | minor grid       | label tier
  -----------|----------------|------------------|------------------|------------
  <=25  (1M) | week (Mon)     | D-Mon (5-May)    | day              | day
  <=70  (3M) | month start    | Mon (MAR)        | week (Mon)       | week
  <=140 (6M) | month start    | Mon (MAR)        | week (Mon)       | week
  <=280(12M) | quarter start  | Mon-YY (JAN-26)  | month start      | month
  <=520 (2Y) | quarter start  | Mon-YY           | month start      | quarter
  <=800 (3Y) | year start     | YYYY             | quarter start    | quarter
  >800       | year start     | YYYY             | quarter start    | year

Replaces the current "Monthly + weekly gridlines" block (lines ~919-925) and the
month label + date label blocks (~993-1006).
"""

import shutil
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "build_dashboard.py"
TS = datetime.now().strftime("%Y%m%d-%H%M%S")
BAK = SRC.with_suffix(f".py.bak-pre-chart-phase4b-{TS}")


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

    # --- 1. Replace gridline block (Monthly + weekly) with tiered logic ---
    text = patch(
        text,
        find=(
            "  // Monthly + weekly gridlines\n"
            "  var lastMonth2=-1;\n"
            "  for(j=0;j<dates.length;j++){\n"
            "    var x=xPos(j);var m=dates[j].getMonth();var dow=dates[j].getDay();\n"
            "    if(m!==lastMonth2&&j>0){ctx.strokeStyle=gridColMonth;ctx.lineWidth=1.2;ctx.beginPath();ctx.moveTo(x,pad.t);ctx.lineTo(x,pad.t+plotH+52);ctx.stroke()}\n"
            "    lastMonth2=m;\n"
            "    if(dow===1&&j>0){ctx.strokeStyle=gridColWeek;ctx.lineWidth=0.6;ctx.beginPath();ctx.moveTo(x,pad.t);ctx.lineTo(x,pad.t+plotH+20);ctx.stroke()}\n"
            "  }"
        ),
        replace=(
            "  // PHASE-4B 2026-05-04: tiered x-axis gridlines + labels.\n"
            "  // Determine tier from n.\n"
            "  var xt;\n"
            "  if(n<=25)      xt={major:'week',  label:'D-Mon',  minor:'day',     labelTier:'day'};\n"
            "  else if(n<=70) xt={major:'month', label:'Mon',    minor:'week',    labelTier:'week'};\n"
            "  else if(n<=140)xt={major:'month', label:'Mon',    minor:'week',    labelTier:'week'};\n"
            "  else if(n<=280)xt={major:'quarter',label:'Mon-YY',minor:'month',   labelTier:'month'};\n"
            "  else if(n<=520)xt={major:'quarter',label:'Mon-YY',minor:'month',   labelTier:'quarter'};\n"
            "  else if(n<=800)xt={major:'year',  label:'YYYY',   minor:'quarter', labelTier:'quarter'};\n"
            "  else           xt={major:'year',  label:'YYYY',   minor:'quarter', labelTier:'year'};\n"
            "  function _isMon(d){return d.getDay()===1}\n"
            "  function _isMonthStart(d,prev){return !prev||d.getMonth()!==prev.getMonth()}\n"
            "  function _isQuarterStart(d,prev){return !prev||(d.getMonth()!==prev.getMonth()&&[0,3,6,9].indexOf(d.getMonth())>=0)}\n"
            "  function _isYearStart(d,prev){return !prev||d.getFullYear()!==prev.getFullYear()}\n"
            "  function _isMajor(d,prev){if(xt.major==='week')return _isMon(d);if(xt.major==='month')return _isMonthStart(d,prev);if(xt.major==='quarter')return _isQuarterStart(d,prev);return _isYearStart(d,prev)}\n"
            "  function _isMinor(d,prev){if(xt.minor==='day')return true;if(xt.minor==='week')return _isMon(d);if(xt.minor==='month')return _isMonthStart(d,prev);return _isQuarterStart(d,prev)}\n"
            "  // Cap minor gridlines at ~30 across plot to avoid noise.\n"
            "  var minorIdx=[];for(j=1;j<dates.length;j++){if(_isMinor(dates[j],dates[j-1]))minorIdx.push(j)}\n"
            "  var minorSkip=Math.max(1,Math.ceil(minorIdx.length/30));\n"
            "  for(var mi=0;mi<minorIdx.length;mi+=minorSkip){var jx=minorIdx[mi];var mxx=xPos(jx);ctx.strokeStyle='rgba(0,0,0,0.04)';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(mxx,pad.t);ctx.lineTo(mxx,pad.t+plotH);ctx.stroke()}\n"
            "  // Major gridlines drawn on top of minors.\n"
            "  var majorIdx=[];for(j=1;j<dates.length;j++){if(_isMajor(dates[j],dates[j-1]))majorIdx.push(j)}\n"
            "  for(var mj=0;mj<majorIdx.length;mj++){var jx2=majorIdx[mj];var mxx2=xPos(jx2);ctx.strokeStyle='rgba(0,0,0,0.10)';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(mxx2,pad.t);ctx.lineTo(mxx2,pad.t+plotH+8);ctx.stroke()}"
        ),
        label="Replace gridline block with tiered major/minor logic",
    )

    # --- 2. Replace centred-month + date-label blocks with single tiered label row ---
    text = patch(
        text,
        find=(
            "  // X-axis: centred month labels with overlap guard\n"
            "  var monthSpans2=[];var curMS=0,curM2=dates[0]?dates[0].getMonth():-1;\n"
            "  for(j=0;j<dates.length;j++){var m3=dates[j].getMonth();if(m3!==curM2){if(curM2>=0)monthSpans2.push({m:curM2,start:curMS,end:j-1});curMS=j;curM2=m3}}\n"
            "  if(curM2>=0)monthSpans2.push({m:curM2,start:curMS,end:n-1});\n"
            "  ctx.font=\"bold 12px sans-serif\";ctx.fillStyle=textColBright;ctx.textAlign=\"center\";\n"
            "  var lastMR=-999;\n"
            "  for(j=0;j<monthSpans2.length;j++){var sp=monthSpans2[j];var mcx=(xPos(sp.start)+xPos(sp.end))/2;var mw2=ctx.measureText(monthFull[sp.m]).width;\n"
            "    if((mcx-mw2/2)>(lastMR+8)){ctx.fillText(monthFull[sp.m],mcx,pad.t+plotH+48);lastMR=mcx+mw2/2}}\n"
            "\n"
            "  // Date labels (day-month format, spaced)\n"
            "  var labelEvery=1;if(n>60)labelEvery=5;else if(n>25)labelEvery=2;\n"
            "  var lastLabelX=-999;ctx.font=\"12px sans-serif\";ctx.fillStyle=textCol;ctx.textAlign=\"center\";\n"
            "  for(j=0;j<dates.length;j++){if(j%labelEvery===0){var x3=xPos(j);if(x3-lastLabelX>34){\n"
            "    var dateStr=dates[j].getDate()+\"-\"+monthShort[dates[j].getMonth()];ctx.fillText(dateStr,x3,pad.t+plotH+16);lastLabelX=x3}}}"
        ),
        replace=(
            "  // PHASE-4B 2026-05-04: single tiered x-axis label row, anchored on major gridlines.\n"
            "  // Format determined by xt.label.\n"
            "  function _fmtLabel(d){\n"
            "    if(xt.label==='D-Mon')return d.getDate()+'-'+monthShort[d.getMonth()];\n"
            "    if(xt.label==='Mon')return monthShort[d.getMonth()].toUpperCase();\n"
            "    if(xt.label==='Mon-YY')return monthShort[d.getMonth()].toUpperCase()+'-'+String(d.getFullYear()).slice(-2);\n"
            "    return String(d.getFullYear());\n"
            "  }\n"
            "  ctx.font='bold 12px sans-serif';ctx.fillStyle=textColBright;ctx.textAlign='center';\n"
            "  // Anti-overlap: estimate per-label pixel width; drop alternating labels until labels fit.\n"
            "  var sampleW=ctx.measureText(_fmtLabel(dates[majorIdx[0]||0])||'').width||30;\n"
            "  var safeMin=sampleW+12;\n"
            "  var lastLX=-9999;\n"
            "  for(var li=0;li<majorIdx.length;li++){\n"
            "    var jx3=majorIdx[li];var lxx=xPos(jx3);\n"
            "    if(lxx-lastLX<safeMin)continue;\n"
            "    var lblTxt=_fmtLabel(dates[jx3]);\n"
            "    ctx.fillText(lblTxt,lxx,pad.t+plotH+22);\n"
            "    lastLX=lxx;\n"
            "  }"
        ),
        label="Replace dual label rows with single tiered label row",
    )

    SRC.write_text(text, encoding="utf-8")
    print(f"\nWrote: {SRC}  ({SRC.stat().st_size:,} bytes)")
    print(f"Backup: {BAK}")
    tail = text[-200:]
    assert "if __name__ == \"__main__\":" in tail, "tail truncated"
    print("Tail check: OK")


if __name__ == "__main__":
    main()
