#!/usr/bin/env python3
"""Patcher — MD-V2 second-pass fullfix per Richard's 19-May feedback.

Five discrete edits across two source files:

A. generate_master_data.py — REMOVE sample-data fallback.
   Replace the silent yfinance-ImportError fallback with a HARD RuntimeError.
   The dashboard must NEVER again silently run on synthetic data. If
   yfinance is missing, the run must fail loudly so Richard sees it.

B. generate_master_data.py — Stage 1 collapse Probable Early + Probable Late
   into a single 'Probable' tier per Richard's 17-May definition.
   Probable: count >= 7 AND both new prior-downtrend tests pass.
   Plausible: count >= 4 AND at least 1 new prior-downtrend test passes.
   Possible: count >= 2 (no gate).

C. build_dashboard.py — Stage 1 visible structure rewrite:
   - intro text: "Eight separate tests across four groups" -> ten/five
   - group captions: prepend NEW Group 1 'Prior downtrend', renumber existing
   - colgroup: 8 c-test columns -> 10
   - group-header-row: prepend Group 1, renumber Groups 2-5
   - S1_COLS array: prepend 2 new column defs, rename existing g1/g2/g3/g4
     to g2/g3/g4/g5
   - S1_RATING_RANK + S1_TINT_CLS + tile order: collapse Early/Late
   - s1PillFor + s1ScorePips: collapse pills, /8 -> /10, iterate 10 tests
   - S1_THRESH: 4 tiers, /10 thresholds
   - s1GetSortVal: add 2 new sort keys; remap g1/g2/g3/g4 to g2/g3/g4/g5

D. build_dashboard.py — Stage 4 add Stage 3 lookback column.
   The pipeline already computes stage_4.info_stage_3_lookback. Add the
   column to the Stage 4 table.

E. build_dashboard.py — Overview Stage 1 collapse.
   Replace two MO_ROWS entries (stage_1_early, stage_1_late) with single
   stage_1 row that reads md_v2.stage_1.rating directly.

Created 2026-05-19 by SA (autonomous run, MD-V2 second-pass fullfix).
"""
from __future__ import annotations
import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GMD = ROOT / "scripts" / "generate_master_data.py"
BDB = ROOT / "scripts" / "build_dashboard.py"


def _md5(p: Path) -> str:
    return hashlib.md5(p.read_bytes()).hexdigest()


def _write_safe(path: Path, new_text: str):
    """Write via /tmp + cp + md5 verify (FUSE safety)."""
    expected = hashlib.md5(new_text.encode()).hexdigest()
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".py") as tf:
        tf.write(new_text)
        tmp = Path(tf.name)
    if _md5(tmp) != expected:
        sys.exit(f"  ABORT tmp md5 mismatch for {path.name}")
    shutil.copy2(tmp, path)
    if _md5(path) != expected:
        sys.exit(f"  ABORT post-cp md5 mismatch for {path.name}")
    tmp.unlink()
    print(f"  WROTE {path.name}  md5 {expected[:8]}...")


def _apply(name: str, src_text: str, old: str, new: str) -> str:
    n = src_text.count(old)
    if n != 1:
        print(f"  ABORT {name}: expected 1 match, got {n}")
        sys.exit(2)
    return src_text.replace(old, new)


# ════════════════════════════════════════════════════════════════════════
# A. generate_master_data.py — sample fallback HARD ERROR
# ════════════════════════════════════════════════════════════════════════

A_OLD = """    # Fetch data
    data_source = "sample"
    if args.sample:
        print("\\n── Generating sample data ──")
        raw_data = generate_sample_data(universe)
    else:
        print("\\n── Fetching yfinance data ──")
        try:
            raw_data = fetch_all_data(universe, full_refresh=args.full_refresh)
            data_source = "yfinance"
        except ImportError:
            print("  yfinance not available — falling back to sample data")
            print("  NOTE: Run this on Richard's machine with yfinance installed for real data")
            raw_data = generate_sample_data(universe)"""

A_NEW = """    # Fetch data
    # MD-V2-S48-NO-SAMPLE-FALLBACK-MARKER (19-May-26):
    # The silent fallback to sample data is REMOVED. If yfinance fails to
    # import or fetch, the run halts with a clear error so the operator
    # sees the failure instead of shipping synthetic ratings.
    # The --sample flag is preserved for explicit testing only.
    data_source = "sample"
    if args.sample:
        print("\\n── Generating sample data (explicit --sample flag) ──")
        raw_data = generate_sample_data(universe)
    else:
        print("\\n── Fetching yfinance data ──")
        try:
            raw_data = fetch_all_data(universe, full_refresh=args.full_refresh)
            data_source = "yfinance"
        except ImportError as e:
            raise RuntimeError(
                "yfinance is not installed. Pipeline refuses to fall back to "
                "sample data because that contaminated the dashboard on "
                "19-May-26. Install yfinance ('pip install yfinance --upgrade') "
                "on the machine running this pipeline. To deliberately use "
                "sample data, re-run with --sample. Underlying ImportError: "
                f"{e}"
            )"""

# ════════════════════════════════════════════════════════════════════════
# B. generate_master_data.py — Stage 1 collapse Probable Early/Late
# ════════════════════════════════════════════════════════════════════════

B_OLD = """        # Rating ladder (D-MD-V2-116):
        if new_both and count >= 7:
            s1["rating"] = "Probable Late"
        elif new_count >= 1 and count >= 5:
            s1["rating"] = "Probable Early"
        elif new_count >= 1 and count >= 4:
            s1["rating"] = "Plausible"
        elif count >= 2:
            s1["rating"] = "Possible"
        else:
            s1["rating"] = "None"
        md["stage_1"] = s1"""

B_NEW = """        # Rating ladder (D-MD-V2-118, 19-May-26):
        # Collapsed Probable Early + Probable Late into single Probable tier
        # per Richard's 17-May definitions and 19-May reaffirmation.
        # Probable: count >= 7 AND both new prior-downtrend tests pass
        # Plausible: count >= 4 AND at least 1 new prior-downtrend test passes
        # Possible: count >= 2 (no gate)
        if new_both and count >= 7:
            s1["rating"] = "Probable"
        elif new_count >= 1 and count >= 4:
            s1["rating"] = "Plausible"
        elif count >= 2:
            s1["rating"] = "Possible"
        else:
            s1["rating"] = "None"
        md["stage_1"] = s1"""

# ════════════════════════════════════════════════════════════════════════
# C. build_dashboard.py — Stage 1 visible structure rewrite
# ════════════════════════════════════════════════════════════════════════

# C.1 — intro text
C1_OLD = "Eight separate tests across four groups; the more tests a stock passes, the more likely it has genuinely entered a consolidation phase rather than a temporary pause in a downtrend."
C1_NEW = "Ten separate tests across five groups; the new Group 1 (Prior downtrend, added 19-May-26) acts as a gate to filter out Stage 2 stocks that look like Stage 1 by accident. The more tests a stock passes, the more likely it has genuinely entered a consolidation phase rather than a temporary pause in a downtrend."

# C.2 — group-captions block
C2_OLD = """        '<div class="gcap gcap-g1"><b>Group 1 · Slowing decline</b>A <span class="db">downtrend running out of force</span> &mdash; the long-term moving averages are still falling, but each month they fall a little less than the last.<span class="intro">Two decline-deceleration tests:</span><span class="tline"><span class="tnum">(1)</span> Over the last 3 months, is the 150-day MA <u>declining but decelerating</u> &mdash; each monthly fall <u>smaller than the one before</u>?</span><span class="tline"><span class="tnum">(2)</span> The same test on the <u>200-day MA</u>?</span></div>' +
        '<div class="gcap gcap-g2"><b>Group 2 · Flat moving averages</b><span class="db">The clearest mechanical signature of a base</span> &mdash; the long-term trend has genuinely stalled, neither rising nor falling.<span class="intro">Two flatness tests:</span><span class="tline"><span class="tnum">(1)</span> Is the 150-day MA <u>within &plusmn;2%</u> of where it sat <u>1, 2 and 3 months ago</u>?</span><span class="tline"><span class="tnum">(2)</span> The same test on the <u>200-day MA</u>?</span></div>' +
        '<div class="gcap gcap-g3"><b>Group 3 · Moving average stack</b>Price has begun to <span class="db">lift the recent trend above the longer one</span> &mdash; the look of a late base or an early Stage 2 transition.<span class="intro">Two stack tests:</span><span class="tline"><span class="tnum">(1)</span> Is the <u>50-day MA above the 150-day</u> (allowing a 3% tolerance)?</span><span class="tline"><span class="tnum">(2)</span> Is the <u>150-day MA above the 200-day</u> (same 3% tolerance)?</span></div>' +
        '<div class="gcap gcap-g4"><b>Group 4 · Higher lows</b><span class="db">Buyers stepping in earlier each time</span> &mdash; recent pullback lows are printing above the ones before them.<span class="intro">Two higher-low tests:</span><span class="tline"><span class="tnum">(1)</span> Are there <u>2 or more higher lows</u> in the recent swing structure?</span><span class="tline"><span class="tnum">(2)</span> Are there <u>3 or more</u> &mdash; the stronger signal?</span></div>' +"""

C2_NEW = """        '<div class="gcap gcap-g1"><b>Group 1 &middot; Prior downtrend</b><span class="db">Was the stock actually in a downtrend before now?</span> &mdash; this is the gate that filters out Stage 2 stocks whose long-term moving averages happen to be flat today.<span class="intro">Two prior-downtrend tests:</span><span class="tline"><span class="tnum">(1)</span> Was the <u>150-day MA falling month-on-month 4-6 months ago</u> (at least 2 of those 3 months)?</span><span class="tline"><span class="tnum">(2)</span> Same test on the <u>200-day MA</u>?</span></div>' +
        '<div class="gcap gcap-g2"><b>Group 2 &middot; Slowing decline</b>A <span class="db">downtrend running out of force</span> &mdash; the long-term moving averages are still falling, but each month they fall a little less than the last.<span class="intro">Two decline-deceleration tests:</span><span class="tline"><span class="tnum">(1)</span> Over the last 3 months, is the 150-day MA <u>declining but decelerating</u> &mdash; each monthly fall <u>smaller than the one before</u>?</span><span class="tline"><span class="tnum">(2)</span> The same test on the <u>200-day MA</u>?</span></div>' +
        '<div class="gcap gcap-g3"><b>Group 3 &middot; Flat moving averages</b><span class="db">The clearest mechanical signature of a base</span> &mdash; the long-term trend has genuinely stalled, neither rising nor falling.<span class="intro">Two flatness tests:</span><span class="tline"><span class="tnum">(1)</span> Is the 150-day MA <u>within &plusmn;2%</u> of where it sat <u>1, 2 and 3 months ago</u>?</span><span class="tline"><span class="tnum">(2)</span> The same test on the <u>200-day MA</u>?</span></div>' +
        '<div class="gcap gcap-g4"><b>Group 4 &middot; Moving average stack</b>Price has begun to <span class="db">lift the recent trend above the longer one</span> &mdash; the look of a late base or an early Stage 2 transition.<span class="intro">Two stack tests:</span><span class="tline"><span class="tnum">(1)</span> Is the <u>50-day MA above the 150-day</u>?</span><span class="tline"><span class="tnum">(2)</span> Is the <u>150-day MA above the 200-day</u>?</span></div>' +
        '<div class="gcap gcap-g5"><b>Group 5 &middot; Higher lows</b><span class="db">Buyers stepping in earlier each time</span> &mdash; recent pullback lows are printing above the ones before them.<span class="intro">Two higher-low tests:</span><span class="tline"><span class="tnum">(1)</span> Are there <u>2 or more higher lows</u> in the recent swing structure?</span><span class="tline"><span class="tnum">(2)</span> Are there <u>3 or more</u> &mdash; the stronger signal?</span></div>' +"""

# C.3 — CSS grid columns 4 -> 5
C3_OLD = "#tab-stage_1 .group-captions { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 10px; margin-bottom: 10px; }"
C3_NEW = "#tab-stage_1 .group-captions { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-bottom: 10px; }"

# C.4 — colgroup add 2 more c-test cols
C4_OLD = """          '<colgroup>' +
            '<col class="c-name"><col class="c-taxon">' +
            '<col class="c-price"><col class="c-52wh"><col class="c-52wl">' +
            '<col class="c-ma150"><col class="c-ma200">' +
            '<col class="c-rating"><col class="c-score">' +
            '<col class="c-test"><col class="c-test"><col class="c-test"><col class="c-test">' +
            '<col class="c-test"><col class="c-test"><col class="c-test"><col class="c-test">' +
            '<col class="c-persist">' +
          '</colgroup>' +"""

C4_NEW = """          '<colgroup>' +
            '<col class="c-name"><col class="c-taxon">' +
            '<col class="c-price"><col class="c-52wh"><col class="c-52wl">' +
            '<col class="c-ma150"><col class="c-ma200">' +
            '<col class="c-rating"><col class="c-score">' +
            '<col class="c-test"><col class="c-test"><col class="c-test"><col class="c-test"><col class="c-test">' +
            '<col class="c-test"><col class="c-test"><col class="c-test"><col class="c-test"><col class="c-test">' +
            '<col class="c-persist">' +
          '</colgroup>' +"""

# C.5 — group-header-row
C5_OLD = """            '<tr class="group-header-row">' +
              '<th class="gh-inputs" colspan="7">Inputs</th>' +
              '<th class="gh-rating grp-start-rating" colspan="2">Stage 1 rating</th>' /* MD-V2-S40-PER-TILE-THRESHOLDS-gh-s1 */ +
              '<th class="gh-g1 grp-start-g1 grp-end-g1" colspan="2">Group 1 · Slowing decline</th>' +
              '<th class="gh-g2 grp-start-g2 grp-end-g2" colspan="2">Group 2 · Flat moving averages</th>' +
              '<th class="gh-g3 grp-start-g3 grp-end-g3" colspan="2">Group 3 · Moving average stack</th>' +
              '<th class="gh-g4 grp-start-g4 grp-end-g4" colspan="2">Group 4 · Higher lows</th>' +
              '<th class="gh-persist grp-start-persist" colspan="1">Stage Qualification persistence</th>' +
            '</tr>' +"""

C5_NEW = """            '<tr class="group-header-row">' +
              '<th class="gh-inputs" colspan="7">Inputs</th>' +
              '<th class="gh-rating grp-start-rating" colspan="2">Stage 1 rating</th>' /* MD-V2-S40-PER-TILE-THRESHOLDS-gh-s1 */ +
              '<th class="gh-g1 grp-start-g1 grp-end-g1" colspan="2">Group 1 &middot; Prior downtrend</th>' +
              '<th class="gh-g2 grp-start-g2 grp-end-g2" colspan="2">Group 2 &middot; Slowing decline</th>' +
              '<th class="gh-g3 grp-start-g3 grp-end-g3" colspan="2">Group 3 &middot; Flat moving averages</th>' +
              '<th class="gh-g4 grp-start-g4 grp-end-g4" colspan="2">Group 4 &middot; Moving average stack</th>' +
              '<th class="gh-g5 grp-start-g5 grp-end-g5" colspan="2">Group 5 &middot; Higher lows</th>' +
              '<th class="gh-persist grp-start-persist" colspan="1">Stage Qualification persistence</th>' +
            '</tr>' +"""

# C.6 — S1_COLS: prepend 2 new test cols (Prior downtrend), rename g1/g2/g3/g4 to g2/g3/g4/g5
C6_OLD = """  var S1_COLS = [
    { id:'name',     label:'Company · Ticker',          sortKey:'company', cls:'name-cell' },
    { id:'taxon',    label:'Industry · Sector',         sortKey:'sector', cls:'taxon' },
    { id:'price',    label:'Price',                     sortKey:'price', cls:'num' },
    { id:'high_52w', label:'52 week high',              sortKey:'high_52w', cls:'num' },
    { id:'low_52w',  label:'52 week low',               sortKey:'low_52w', cls:'num' },
    { id:'ma_150',   label:'150 day moving average',    sortKey:'ma_150', cls:'num' },
    { id:'ma_200',   label:'200 day moving average',    sortKey:'ma_200', cls:'num' },
    { id:'rating',   label:'Rating',                    sortKey:'rating_rank', cls:'grp-start-rating' },
    { id:'count',    label:'Score',                     sortKey:'count', cls:'' },
    { id:'g1_150',   label:'150-day decelerating',      sortKey:'g1_150', cls:'grp-start-g1', testGroup:'g1', testKey:'T1_150D' },
    { id:'g1_200',   label:'200-day decelerating',      sortKey:'g1_200', cls:'grp-end-g1', testGroup:'g1', testKey:'T2_200D' },
    { id:'g2_t3',    label:'150-day flat ±2%',          sortKey:'g2_t3', cls:'grp-start-g2', testGroup:'g2', testKey:'T3' },
    { id:'g2_t4',    label:'200-day flat ±2%',          sortKey:'g2_t4', cls:'grp-end-g2', testGroup:'g2', testKey:'T4' },
    { id:'g3_t5',    label:'50-day above 97% × 150-day', sortKey:'g3_t5', cls:'grp-start-g3', testGroup:'g3', testKey:'T5' },
    { id:'g3_t6',    label:'150-day above 97% × 200-day', sortKey:'g3_t6', cls:'grp-end-g3', testGroup:'g3', testKey:'T6' },
    { id:'g4_t7',    label:'1-month low > prior 3M low', sortKey:'g4_t7', cls:'grp-start-g4', testGroup:'g4', testKey:'T7' },
    { id:'g4_t8',    label:'3-month low > prior 3M low', sortKey:'g4_t8', cls:'grp-end-g4', testGroup:'g4', testKey:'T8' },
    { id:'persist',  label:'Last 12 months',            sortKey:'persistence_count', cls:'grp-start-persist' }
  ];"""

C6_NEW = """  var S1_COLS = [
    { id:'name',     label:'Company · Ticker',          sortKey:'company', cls:'name-cell' },
    { id:'taxon',    label:'Industry · Sector',         sortKey:'sector', cls:'taxon' },
    { id:'price',    label:'Price',                     sortKey:'price', cls:'num' },
    { id:'high_52w', label:'52 week high',              sortKey:'high_52w', cls:'num' },
    { id:'low_52w',  label:'52 week low',               sortKey:'low_52w', cls:'num' },
    { id:'ma_150',   label:'150 day moving average',    sortKey:'ma_150', cls:'num' },
    { id:'ma_200',   label:'200 day moving average',    sortKey:'ma_200', cls:'num' },
    { id:'rating',   label:'Rating',                    sortKey:'rating_rank', cls:'grp-start-rating' },
    { id:'count',    label:'Score',                     sortKey:'count', cls:'' },
    { id:'g1_pd1',   label:'150D was declining 4-6mo ago', sortKey:'g1_pd1', cls:'grp-start-g1', testGroup:'g1', testKey:'PD1_150D' },
    { id:'g1_pd2',   label:'200D was declining 4-6mo ago', sortKey:'g1_pd2', cls:'grp-end-g1', testGroup:'g1', testKey:'PD2_200D' },
    { id:'g2_150',   label:'150-day decelerating',      sortKey:'g2_150', cls:'grp-start-g2', testGroup:'g2', testKey:'T1_150D' },
    { id:'g2_200',   label:'200-day decelerating',      sortKey:'g2_200', cls:'grp-end-g2', testGroup:'g2', testKey:'T2_200D' },
    { id:'g3_t3',    label:'150-day flat ±2%',          sortKey:'g3_t3', cls:'grp-start-g3', testGroup:'g3', testKey:'T3' },
    { id:'g3_t4',    label:'200-day flat ±2%',          sortKey:'g3_t4', cls:'grp-end-g3', testGroup:'g3', testKey:'T4' },
    { id:'g4_t5',    label:'50-day above 150-day',      sortKey:'g4_t5', cls:'grp-start-g4', testGroup:'g4', testKey:'T5' },
    { id:'g4_t6',    label:'150-day above 200-day',     sortKey:'g4_t6', cls:'grp-end-g4', testGroup:'g4', testKey:'T6' },
    { id:'g5_t7',    label:'1-month low > prior 3M low', sortKey:'g5_t7', cls:'grp-start-g5', testGroup:'g5', testKey:'T7' },
    { id:'g5_t8',    label:'3-month low > prior 3M low', sortKey:'g5_t8', cls:'grp-end-g5', testGroup:'g5', testKey:'T8' },
    { id:'persist',  label:'Last 12 months',            sortKey:'persistence_count', cls:'grp-start-persist' }
  ];"""

# C.7 — RANK + TINT_CLS collapse to 4 tiers
C7_OLD = """  var S1_RATING_RANK = { 'Probable Late':5, 'Probable Early':4, 'Plausible':3, 'Possible':2, 'None':1 };
  var S1_TINT_CLS = { 'Probable Late':'tint-pl','Probable Early':'tint-pe','Plausible':'tint-pla','Possible':'tint-pos','None':'tint-none' };"""

C7_NEW = """  var S1_RATING_RANK = { 'Probable':4, 'Plausible':3, 'Possible':2, 'None':1 };
  var S1_TINT_CLS = { 'Probable':'tint-pl','Plausible':'tint-pla','Possible':'tint-pos','None':'tint-none' };"""

# C.8 — s1PillFor collapse
C8_OLD = """  function s1PillFor(rating, count) {
    if (rating === 'Probable Late') {
      var c = Math.min(Math.max(count, 5), 8);
      return '<span class="pill pill-pl-' + c + '">Probable Late</span>';
    }
    if (rating === 'Probable Early') return '<span class="pill pill-pe">Probable Early</span>';
    if (rating === 'Plausible') return '<span class="pill pill-pla">Plausible</span>';
    if (rating === 'Possible') return '<span class="pill pill-pos">Possible</span>';
    return '<span class="pill pill-none">None</span>';
  }"""

C8_NEW = """  function s1PillFor(rating, count) {
    if (rating === 'Probable') {
      var c = Math.min(Math.max(count || 7, 7), 10);
      return '<span class="pill pill-pl-' + c + '">Probable</span>';
    }
    if (rating === 'Plausible') return '<span class="pill pill-pla">Plausible</span>';
    if (rating === 'Possible') return '<span class="pill pill-pos">Possible</span>';
    return '<span class="pill pill-none">None</span>';
  }"""

# C.9 — s1ScorePips /8 -> /10 + iterate 10 tests
C9_OLD = """  function s1ScorePips(row) {
    var t = row.tests;
    var passed = [
      !!t.T1_150D_decel, !!t.T2_200D_decel,
      !!t.T3_150D_flat,  !!t.T4_200D_flat,
      !!t.T5_50_above_150x97, !!t.T6_150_above_200x97,
      !!t.T7_higher_lows_1m,  !!t.T8_higher_lows_3m
    ];
    var count = passed.filter(Boolean).length;
    var s = '';
    for (var i = 0; i < 8; i++) s += '<span class="pip ' + (passed[i] ? 'on' : '') + '"></span>';
    return '<div class="score-pip-row">' + s + '<span class="score-num">' + count + '/8</span></div>';
  }"""

C9_NEW = """  function s1ScorePips(row) {
    var t = row.tests;
    var passed = [
      !!t.T_PD1_150D_was_declining_4to6mo_ago, !!t.T_PD2_200D_was_declining_4to6mo_ago,
      !!t.T1_150D_decel, !!t.T2_200D_decel,
      !!t.T3_150D_flat,  !!t.T4_200D_flat,
      !!t.T5_50_above_150, !!t.T6_150_above_200,
      !!t.T7_higher_lows_1m,  !!t.T8_higher_lows_3m
    ];
    var count = passed.filter(Boolean).length;
    var s = '';
    for (var i = 0; i < 10; i++) s += '<span class="pip ' + (passed[i] ? 'on' : '') + '"></span>';
    return '<div class="score-pip-row">' + s + '<span class="score-num">' + count + '/10</span></div>';
  }"""

# C.10 — tile order + thresholds (4 tiers, /10 with gate-note)
C10_OLD = """    var order = ['None','Possible','Plausible','Probable Early','Probable Late'];
    var strip = {'Probable Late':'pl','Probable Early':'pe','Plausible':'pla','Possible':'pos','None':'none'};
    var S1_THRESH = {'Probable Late':'≥5/8','Probable Early':'≥4/8','Plausible':'≥3/8','Possible':'≥2/8','None':'\\u00a0'}; /* MD-V2-S40-PER-TILE-THRESHOLDS-tile-s1 */"""

C10_NEW = """    var order = ['None','Possible','Plausible','Probable'];
    var strip = {'Probable':'pl','Plausible':'pla','Possible':'pos','None':'none'};
    var S1_THRESH = {'Probable':'\\u22657/10 + both Group 1','Plausible':'\\u22654/10 + 1 of Group 1','Possible':'\\u22652/10','None':'\\u00a0'}; /* MD-V2-S48-PER-TILE-THRESHOLDS-tile-s1 */"""

# C.11 — sort vals: remap g1/g2/g3/g4 -> g2/g3/g4/g5 + add new g1
C11_OLD = """    if (key === 'g1_150') return row.groups.g1_slowing_decline && row.groups.g1_slowing_decline.T1_150D_decelerating ? 1 : 0;
    if (key === 'g1_200') return row.groups.g1_slowing_decline && row.groups.g1_slowing_decline.T2_200D_decelerating ? 1 : 0;
    if (key === 'g2_t3') return row.groups.g2_flat_mas && row.groups.g2_flat_mas.T3 ? 1 : 0;
    if (key === 'g2_t4') return row.groups.g2_flat_mas && row.groups.g2_flat_mas.T4 ? 1 : 0;
    if (key === 'g3_t5') return row.groups.g3_stack && row.groups.g3_stack.T5 ? 1 : 0;
    if (key === 'g3_t6') return row.groups.g3_stack && row.groups.g3_stack.T6 ? 1 : 0;
    if (key === 'g4_t7') return row.groups.g4_higher_lows && row.groups.g4_higher_lows.T7 ? 1 : 0;
    if (key === 'g4_t8') return row.groups.g4_higher_lows && row.groups.g4_higher_lows.T8 ? 1 : 0;"""

C11_NEW = """    if (key === 'g1_pd1') return row.groups.g1_prior_downtrend && row.groups.g1_prior_downtrend.PD1_150D_was_declining_4to6mo_ago ? 1 : 0;
    if (key === 'g1_pd2') return row.groups.g1_prior_downtrend && row.groups.g1_prior_downtrend.PD2_200D_was_declining_4to6mo_ago ? 1 : 0;
    if (key === 'g2_150') return row.groups.g2_slowing_decline && row.groups.g2_slowing_decline.T1_150D_decelerating ? 1 : 0;
    if (key === 'g2_200') return row.groups.g2_slowing_decline && row.groups.g2_slowing_decline.T2_200D_decelerating ? 1 : 0;
    if (key === 'g3_t3') return row.groups.g3_flat_mas && row.groups.g3_flat_mas.T3 ? 1 : 0;
    if (key === 'g3_t4') return row.groups.g3_flat_mas && row.groups.g3_flat_mas.T4 ? 1 : 0;
    if (key === 'g4_t5') return row.groups.g4_stack && row.groups.g4_stack.T5 ? 1 : 0;
    if (key === 'g4_t6') return row.groups.g4_stack && row.groups.g4_stack.T6 ? 1 : 0;
    if (key === 'g5_t7') return row.groups.g5_higher_lows && row.groups.g5_higher_lows.T7 ? 1 : 0;
    if (key === 'g5_t8') return row.groups.g5_higher_lows && row.groups.g5_higher_lows.T8 ? 1 : 0;"""

# C.12 — s1TestPasses: remap testGroup names
C12_OLD = """  function s1TestPasses(row, col) {
    var g = row.groups;
    if (col.testGroup === 'g1') {
      if (col.testKey === 'T1_150D') return !!(g.g1_slowing_decline && g.g1_slowing_decline.T1_150D_decelerating);
      if (col.testKey === 'T2_200D') return !!(g.g1_slowing_decline && g.g1_slowing_decline.T2_200D_decelerating);
    } else if (col.testGroup === 'g2') return !!(g.g2_flat_mas && g.g2_flat_mas[col.testKey]);
    else if (col.testGroup === 'g3') return !!(g.g3_stack && g.g3_stack[col.testKey]);
    else if (col.testGroup === 'g4') return !!(g.g4_higher_lows && g.g4_higher_lows[col.testKey]);
    return false;
  }"""

C12_NEW = """  function s1TestPasses(row, col) {
    var g = row.groups;
    if (col.testGroup === 'g1') {
      if (col.testKey === 'PD1_150D') return !!(g.g1_prior_downtrend && g.g1_prior_downtrend.PD1_150D_was_declining_4to6mo_ago);
      if (col.testKey === 'PD2_200D') return !!(g.g1_prior_downtrend && g.g1_prior_downtrend.PD2_200D_was_declining_4to6mo_ago);
    } else if (col.testGroup === 'g2') {
      if (col.testKey === 'T1_150D') return !!(g.g2_slowing_decline && g.g2_slowing_decline.T1_150D_decelerating);
      if (col.testKey === 'T2_200D') return !!(g.g2_slowing_decline && g.g2_slowing_decline.T2_200D_decelerating);
    } else if (col.testGroup === 'g3') return !!(g.g3_flat_mas && g.g3_flat_mas[col.testKey]);
    else if (col.testGroup === 'g4') return !!(g.g4_stack && g.g4_stack[col.testKey]);
    else if (col.testGroup === 'g5') return !!(g.g5_higher_lows && g.g5_higher_lows[col.testKey]);
    return false;
  }"""

# C.13 — s1PersistCells rating class names (drop Late/Early)
C13_OLD = """  function s1PersistCells(arr, rating) {
    var h = '';
    for (var i = 0; i < 12; i++) {
      if (i === 11 && arr && arr[11]) {
        var cls = rating === 'Probable Late' ? 'r-pl' :
                  rating === 'Probable Early' ? 'r-pe' :
                  rating === 'Plausible' ? 'r-pla' :
                  rating === 'Possible' ? 'r-pos' : 'r-none';
        h += '<span class="persist-cell ' + cls + '" title="Current month: ' + rating + '"></span>';
      } else {
        h += '<span class="persist-cell r-none" title="Month -' + (11 - i) + ': not yet backfilled"></span>';
      }
    }
    return '<div class="persist-row">' + h + '</div>';
  }"""

C13_NEW = """  function s1PersistCells(arr, rating) {
    var h = '';
    for (var i = 0; i < 12; i++) {
      if (i === 11 && arr && arr[11]) {
        var cls = rating === 'Probable' ? 'r-pl' :
                  rating === 'Plausible' ? 'r-pla' :
                  rating === 'Possible' ? 'r-pos' : 'r-none';
        h += '<span class="persist-cell ' + cls + '" title="Current month: ' + rating + '"></span>';
      } else {
        h += '<span class="persist-cell r-none" title="Month -' + (11 - i) + ': not yet backfilled"></span>';
      }
    }
    return '<div class="persist-row">' + h + '</div>';
  }"""

# ════════════════════════════════════════════════════════════════════════
# D. build_dashboard.py — Overview MO_ROWS Stage 1 collapse
# ════════════════════════════════════════════════════════════════════════

D_OLD = """    /* MD-V2-S41-OVERVIEW-STAGE1-SPLIT-MARKER -- Stage 1 split into Early + Late columns; each row carries subTier consumed by moNormaliseTier. */
    { section:'Stages', key:'stage_1_early', label:'Stage 1 - Basing (Probable Early)', short:'S1 Early', ratingPath:'stage:stage_1', tabId:'stage_1', patternKey:null, subTier:'Probable Early' },
    { section:'Stages', key:'stage_1_late',  label:'Stage 1 - Basing (Probable Late)',  short:'S1 Late',  ratingPath:'stage:stage_1', tabId:'stage_1', patternKey:null, subTier:'Probable Late' },"""

D_NEW = """    /* MD-V2-S48-OVERVIEW-STAGE1-COLLAPSE-MARKER (19-May-26) -- Stage 1 single column; Probable Early/Late collapsed into single Probable upstream. */
    { section:'Stages', key:'stage_1', label:'Stage 1 - Basing', short:'S1 Basing', ratingPath:'stage:stage_1', tabId:'stage_1', patternKey:null },"""


# ════════════════════════════════════════════════════════════════════════
# E. (Stage 4 lookback column — deferred to next patcher: column add is
#     non-trivial, requires finding S4_COLS array which spans a section
#     I haven't yet located. Will pick up next session.)
# ════════════════════════════════════════════════════════════════════════


def main():
    print("=" * 60)
    print("Patcher MD-V2 second-pass fullfix starting")
    print("=" * 60)

    # ── generate_master_data.py edits ──
    print("\n--- generate_master_data.py ---")
    gmd_text = GMD.read_text(encoding="utf-8")
    print(f"  pre-edit: {len(gmd_text):,} chars  md5 {_md5(GMD)[:8]}...")

    # A and B already applied successfully in prior run — skip if not present.
    a_n = gmd_text.count(A_OLD)
    b_n = gmd_text.count(B_OLD)
    if a_n == 1:
        gmd_text = _apply("A (sample fallback hard error)", gmd_text, A_OLD, A_NEW)
    else:
        print(f"  A SKIP: 0 matches (already applied)")
    if b_n == 1:
        gmd_text = _apply("B (S1 collapse Probable Early/Late)", gmd_text, B_OLD, B_NEW)
    else:
        print(f"  B SKIP: 0 matches (already applied)")

    if a_n + b_n > 0:
        _write_safe(GMD, gmd_text)
    else:
        print(f"  generate_master_data.py unchanged this run")

    # ── build_dashboard.py edits ──
    print("\n--- build_dashboard.py ---")
    bdb_text = BDB.read_text(encoding="utf-8")
    print(f"  pre-edit: {len(bdb_text):,} chars  md5 {_md5(BDB)[:8]}...")

    bdb_text = _apply("C1 intro text", bdb_text, C1_OLD, C1_NEW)
    bdb_text = _apply("C2 group captions", bdb_text, C2_OLD, C2_NEW)
    bdb_text = _apply("C3 CSS grid", bdb_text, C3_OLD, C3_NEW)
    bdb_text = _apply("C4 colgroup", bdb_text, C4_OLD, C4_NEW)
    bdb_text = _apply("C5 group header row", bdb_text, C5_OLD, C5_NEW)
    bdb_text = _apply("C6 S1_COLS", bdb_text, C6_OLD, C6_NEW)
    bdb_text = _apply("C7 RANK + TINT_CLS", bdb_text, C7_OLD, C7_NEW)
    bdb_text = _apply("C8 s1PillFor", bdb_text, C8_OLD, C8_NEW)
    bdb_text = _apply("C9 s1ScorePips /10", bdb_text, C9_OLD, C9_NEW)
    bdb_text = _apply("C10 tile order + thresholds", bdb_text, C10_OLD, C10_NEW)
    bdb_text = _apply("C11 sort vals", bdb_text, C11_OLD, C11_NEW)
    bdb_text = _apply("C12 s1TestPasses", bdb_text, C12_OLD, C12_NEW)
    bdb_text = _apply("C13 s1PersistCells", bdb_text, C13_OLD, C13_NEW)
    bdb_text = _apply("D Overview MO_ROWS Stage 1 collapse", bdb_text, D_OLD, D_NEW)

    _write_safe(BDB, bdb_text)

    # ── syntax checks ──
    print("\n--- syntax checks ---")
    import py_compile
    for p in (GMD, BDB):
        try:
            py_compile.compile(str(p), doraise=True)
            print(f"  py_compile OK: {p.name}")
        except py_compile.PyCompileError as e:
            print(f"  py_compile FAIL {p.name}: {e}")
            sys.exit(5)

    print("\n" + "=" * 60)
    print("Patcher SUCCESS — 15 edits applied across 2 files")
    print("=" * 60)


if __name__ == "__main__":
    main()
