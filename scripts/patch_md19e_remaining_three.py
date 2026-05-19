#!/usr/bin/env python3
"""Patcher — three remaining items:

A. Stage 3 dashboard column for the prior-uptrend gate (so high-scorers
   with rating None are visibly explained).
B. Stage 4 dashboard column for the Stage 3 lookback (was S3 firing in
   last 60 days).
C. Per-tile criteria text on Stage 2 / Stage 3 / Stage 4 (Stage 1 already
   shipped).

Implementation notes:
- Items A and B require the pipeline to expose the data inside the
  groups dict so the existing s3TestCell / s4TestCell row renderer reads
  it. Two small pipeline edits plus two dashboard column-list edits.

Created 2026-05-19 by SA (autonomous final run, "fix it all" round 5).
"""
import hashlib, shutil, sys, tempfile
from pathlib import Path

ROOT = Path("/sessions/admiring-jolly-noether/mnt/COWORK/master-dashboard")
GMD = ROOT / "scripts" / "generate_master_data.py"
BDB = ROOT / "scripts" / "build_dashboard.py"


def _md5(p): return hashlib.md5(p.read_bytes()).hexdigest()


def _safe_write(path, text):
    exp = hashlib.md5(text.encode()).hexdigest()
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".py") as tf:
        tf.write(text); tmp = Path(tf.name)
    if _md5(tmp) != exp: sys.exit(f"tmp md5 mismatch {path.name}")
    shutil.copy2(tmp, path)
    if _md5(path) != exp: sys.exit(f"post-cp md5 mismatch {path.name}")
    tmp.unlink()
    print(f"  WROTE {path.name}  md5 {exp[:8]}")


def _apply(name, txt, old, new):
    n = txt.count(old)
    if n != 1: sys.exit(f"  ABORT {name}: matched {n}x")
    print(f"  {name}: applied")
    return txt.replace(old, new)


# ── A1. pipeline — expose prior_uptrend in s3.groups ──────────────────
A1_OLD = """        s3["prior_uptrend"] = prior_uptrend"""

A1_NEW = """        s3["prior_uptrend"] = prior_uptrend
        # MD-V2-S48-PRIOR-UPTREND-VISIBLE-MARKER (19-May-26):
        # Expose prior_uptrend in groups so dashboard can render as visible
        # column. The hard precondition forces rating to None when False
        # even if test count is high — without visibility users see a
        # high-scoring 'None' and assume the dashboard is broken.
        s3["groups"]["g6_prior_uptrend_gate"] = {"PU": bool(prior_uptrend)}
        s3["tests"]["G_prior_uptrend_gate_passed"] = bool(prior_uptrend)"""

# ── B1. pipeline — expose s3_lookback in s4.groups ────────────────────
B1_OLD = """        s4["test_values"] = {
            "s3_fired_in_60d": s3_lookback["fired"],
            "s3_days_ago": s3_lookback["days_ago"],
            "s3_history_depth_ok": s3_lookback["history_depth_ok"],
        }"""

B1_NEW = """        s4["test_values"] = {
            "s3_fired_in_60d": s3_lookback["fired"],
            "s3_days_ago": s3_lookback["days_ago"],
            "s3_history_depth_ok": s3_lookback["history_depth_ok"],
        }
        # MD-V2-S48-S3-LOOKBACK-VISIBLE-MARKER (19-May-26):
        # Expose s3_lookback as a group/test so the dashboard renders a
        # visible column on the Stage 4 tab (D-MD-V2-115 originally made
        # this INFO-only but Richard wants it visible for audit).
        s4["groups"]["g4_s3_lookback"] = {"S3_fired_60d": bool(s3_lookback["fired"])}
        s4["tests"]["INFO_S3_fired_in_last_60d"] = bool(s3_lookback["fired"])"""

# ── A2. build_dashboard — add prior_uptrend column to S3_COLS ─────────
A2_OLD = """    { id:'g5_t10',   label:'RS trend weakening (3m < -5%)',            sortKey:'g5_t10', cls:'grp-start-g5 grp-end-g5', testGroup:'g5_rs_trend', testKey:'T10' },
    { id:'persist',  label:'Last 12 months',            sortKey:'persistence_count', cls:'grp-start-persist' }
  ];
  var S3_RATING_RANK"""

A2_NEW = """    { id:'g5_t10',   label:'RS trend weakening (3m < -5%)',            sortKey:'g5_t10', cls:'grp-start-g5 grp-end-g5', testGroup:'g5_rs_trend', testKey:'T10' },
    /* MD-V2-S48-PRIOR-UPTREND-COLUMN-MARKER (19-May-26):
       Prior-uptrend gate visibility column. When PU = false, the rating
       is forced to None regardless of test count. This column exposes
       the gate state so high-scoring stocks rated None are explained. */
    { id:'g6_pu',    label:'Prior uptrend? (200D rising 6-7mo ago)',  sortKey:'g6_pu', cls:'grp-start-g6 grp-end-g6', testGroup:'g6_prior_uptrend_gate', testKey:'PU' },
    { id:'persist',  label:'Last 12 months',            sortKey:'persistence_count', cls:'grp-start-persist' }
  ];
  var S3_RATING_RANK"""

# ── B2. build_dashboard — add S3 lookback column to S4_COLS ───────────
B2_OLD = """    { id:'g3_t7',    label:'RS trend weak (3m < -5%)',                 sortKey:'g3_t7', cls:'grp-end-g3', testGroup:'g3_rs', testKey:'T7' },
    { id:'persist',  label:'Last 12 months',            sortKey:'persistence_count', cls:'grp-start-persist' }
  ];
  var S4_RATING_RANK"""

B2_NEW = """    { id:'g3_t7',    label:'RS trend weak (3m < -5%)',                 sortKey:'g3_t7', cls:'grp-end-g3', testGroup:'g3_rs', testKey:'T7' },
    /* MD-V2-S48-S3-LOOKBACK-COLUMN-MARKER (19-May-26):
       Stage 3 lookback INFO column — did Stage 3 fire on this stock in
       the last 60 trading days? Per D-MD-V2-115 this stays INFO-only
       (does not modify Stage 4 rating) but is now visible for audit. */
    { id:'g4_s3lb',  label:'Stage 3 fired in last 60d?',             sortKey:'g4_s3lb', cls:'grp-start-g4 grp-end-g4', testGroup:'g4_s3_lookback', testKey:'S3_fired_60d' },
    { id:'persist',  label:'Last 12 months',            sortKey:'persistence_count', cls:'grp-start-persist' }
  ];
  var S4_RATING_RANK"""

# ── C1. S2_THRESH — full criteria ─────────────────────────────────────
C1_OLD = """    var S2_THRESH = {'Probable':'≥7/10','Plausible':'≥6/10','Possible':'≥5/10','None':'\\u00a0'}; /* MD-V2-S40-PER-TILE-THRESHOLDS-tile-s2 */"""
C1_NEW = """    var S2_THRESH = {
      'Probable':'\\u22657 of 10 tests pass (LT/MT/ST trend up + RS strong + base depth)',
      'Plausible':'\\u22656 of 10 tests pass',
      'Possible':'\\u22655 of 10 tests pass',
      'None':'<5 of 10 tests'
    }; /* MD-V2-S48b-PER-TILE-CRITERIA-tile-s2 */"""

# ── C2. S3_THRESH ─────────────────────────────────────────────────────
C2_OLD = """    var S3_THRESH = {'Probable Invalidation':'≥6/10','Plausible Invalidation':'≥4/10','Possible Topping':'≥2/10','None':'\\u00a0'}; /* MD-V2-S40-PER-TILE-THRESHOLDS-tile-s3 */"""
C2_NEW = """    var S3_THRESH = {
      'Probable Invalidation':'\\u22656 of 10 tests AND prior-uptrend gate passed',
      'Plausible Invalidation':'\\u22654 of 10 tests AND prior-uptrend gate passed',
      'Possible Topping':'\\u22652 of 10 tests AND prior-uptrend gate passed',
      'None':'<2 of 10 tests OR prior-uptrend gate failed (200D not rising 6-7mo ago)'
    }; /* MD-V2-S48b-PER-TILE-CRITERIA-tile-s3 */"""

# ── C3. S4_THRESH ─────────────────────────────────────────────────────
C3_OLD = """    var S4_THRESH = {'Probable':'≥3/7','Plausible':'≥2/7','Possible':'≥1/7','None':'\\u00a0'}; /* MD-V2-S40-PER-TILE-THRESHOLDS-tile-s4 */"""
C3_NEW = """    var S4_THRESH = {
      'Probable':'200D declining AND full MA stack inverted (price<50<150<200) AND 150<200 AND 50<150',
      'Plausible':'150-day below 200-day AND 50-day below 150-day',
      'Possible':'150-day below 200-day OR 50-day below 150-day',
      'None':'No stack inversion'
    }; /* MD-V2-S48b-PER-TILE-CRITERIA-tile-s4 */"""


def main():
    print("=" * 60)
    print("Patcher MD-V2 Round E — remaining 3 items")
    print("=" * 60)

    print("\n--- generate_master_data.py edits ---")
    g = GMD.read_text(encoding="utf-8")
    g = _apply("A1 prior_uptrend in groups", g, A1_OLD, A1_NEW)
    g = _apply("B1 s3_lookback in groups", g, B1_OLD, B1_NEW)
    _safe_write(GMD, g)

    print("\n--- build_dashboard.py edits ---")
    b = BDB.read_text(encoding="utf-8")
    b = _apply("A2 S3 prior_uptrend column", b, A2_OLD, A2_NEW)
    b = _apply("B2 S4 lookback column", b, B2_OLD, B2_NEW)
    b = _apply("C1 S2 per-tile criteria", b, C1_OLD, C1_NEW)
    b = _apply("C2 S3 per-tile criteria", b, C2_OLD, C2_NEW)
    b = _apply("C3 S4 per-tile criteria", b, C3_OLD, C3_NEW)
    _safe_write(BDB, b)

    print("\n--- syntax checks ---")
    import py_compile
    for fp in (GMD, BDB):
        py_compile.compile(str(fp), doraise=True)
        print(f"  py_compile OK: {fp.name}")

    print("\n" + "=" * 60)
    print("Patcher SUCCESS — 7 edits applied across 2 files")
    print("=" * 60)


if __name__ == "__main__":
    main()
