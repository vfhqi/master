#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MD V2 - Wave 4 pipeline patcher: emit a `test_values` dict per V2 pattern.

For every md_v2 indicator / setup / deployment-test pattern emitted by
compute_master_dashboard_screens(), add a `test_values` dict alongside the
existing `tests` dict. Each entry is keyed by the SAME test key as `tests`,
and carries either the underlying numeric value used in the boolean
comparison, OR a short label string where the test is inherently binary.

This is the data half of D-MD-V2 Wave 4 (the "Show test values" toggle).
The dashboard half (build_dashboard.py) reads rec.test_values[testKey].

Patcher discipline: utf-8 IO; temp file beside the patcher; atomic replace;
dry-run against git HEAD copy; idempotent MARKER guard; per-anchor uniqueness
assertion; ast.parse compile-check; MD5 self-report. ASCII-only literals.
"""

import ast
import hashlib
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(SCRIPT_DIR, "generate_master_data.py")
TMP = os.path.join(SCRIPT_DIR, ".patch_wave4_pipeline.tmp")
MARKER = "MD-V2-WAVE4-TEST-VALUES-MARKER"

HELPER_ANCHOR = "        # ── END MD-V2-SCREENS-S26-MARKER VCP helper ──\n"

HELPER_COMBINED = (
    "        # ── END MD-V2-SCREENS-S26-MARKER VCP helper ──\n"
    "\n"
    "        # ── " + MARKER + ": per-pattern numeric test values (D-MD-V2 Wave 4) ──\n"
    "        # For each md_v2 pattern, build a parallel dict keyed by the SAME\n"
    "        # test keys as `tests`, carrying the underlying number where one\n"
    "        # exists or a short label where the test is inherently binary.\n"
    "        # Computed here, in the same pass, from the same locals that\n"
    "        # produced the booleans, so value and boolean cannot drift apart.\n"
    "        def _md_v2_round(x, nd=4):\n"
    "            try:\n"
    "                if x is None:\n"
    "                    return None\n"
    "                return round(float(x), nd)\n"
    "            except (TypeError, ValueError):\n"
    "                return None\n"
    "\n"
    "        def _md_v2_pct_gap(a, b):\n"
    "            try:\n"
    "                if a is None or b is None or b == 0:\n"
    "                    return None\n"
    "                return round((float(a) - float(b)) / float(b), 4)\n"
    "            except (TypeError, ValueError):\n"
    "                return None\n"
    "\n"
    "        def _md_v2_vcp_values(vt, contractions):\n"
    "            n = len(contractions)\n"
    "            return {\n"
    "                \"t1_narrowing_contractions\": (\n"
    "                    \"narrowing\" if vt.get(\"t1_narrowing_contractions\") else \"not narrowing\"),\n"
    "                \"t2_sufficient_count\": n,\n"
    "                \"t3_volume_declining\": (\n"
    "                    \"declining\" if vt.get(\"t3_volume_declining\") else \"not declining\"),\n"
    "                \"t4_higher_lows\": (\n"
    "                    \"higher lows\" if vt.get(\"t4_higher_lows\") else \"not higher\"),\n"
    "            }\n"
    "        # ── END " + MARKER + " helper ──\n"
)

EDITS = []
# --- EDIT: pre_indicators ---
EDITS.append((
    '        md["pre_indicators"] = {\n            "pulling_back_uptrend": {\n                "tests": pb_tests, "count": pb_count, "total": 4,\n                "rating": _pre_rating(pb_count, 4), "qualifies": ind["pulling_back_uptrend"],\n            },\n            "basing": {\n                "tests": ba_tests, "count": ba_count, "total": 4,\n                "rating": _pre_rating(ba_count, 4), "qualifies": ind["basing"],\n            },\n            "collapsing": {\n                "tests": co_tests, "count": co_count, "total": 2,\n                "rating": _pre_rating(co_count, 2), "qualifies": ind["collapsing"],\n            },\n        }',
    '        md["pre_indicators"] = {\n            "pulling_back_uptrend": {\n                "tests": pb_tests, "count": pb_count, "total": 4,\n                "rating": _pre_rating(pb_count, 4), "qualifies": ind["pulling_back_uptrend"],\n                "test_values": {\n                    "t1_50d_rising": "rising" if pb_t1_50d_rising else "not rising",\n                    "t2_150d_rising": "rising" if pb_t2_150d_rising else "not rising",\n                    "t3_5d_rolling_over": "rolling over" if pb_t3_5d_rolling else "not rolling",\n                    "t4_10d_rolling_over": "rolling over" if pb_t4_10d_rolling else "not rolling",\n                },\n            },\n            "basing": {\n                "tests": ba_tests, "count": ba_count, "total": 4,\n                "rating": _pre_rating(ba_count, 4), "qualifies": ind["basing"],\n                "test_values": {\n                    "t1_price_pullback_ge15": _md_v2_round(max_pullback_ssh),\n                    "t2_time_below_high_ge20d": days_below_sh,\n                    "t3_price_above_200d": _md_v2_pct_gap(price, ma200),\n                    "t4_200d_rising": _md_v2_pct_gap(ma200, ma200_prev),\n                },\n            },\n            "collapsing": {\n                "tests": co_tests, "count": co_count, "total": 2,\n                "rating": _pre_rating(co_count, 2), "qualifies": ind["collapsing"],\n                "test_values": {\n                    "t1_price_le_70pct_52wh": _md_v2_pct_gap(price, h52),\n                    "t2_pullback_ge20": _md_v2_round(recent_pullback),\n                },\n            },\n        }',
))

# --- EDIT: post_indicators ---
EDITS.append((
    '        md["post_indicators"] = {\n            "breakout": {\n                "tests": bo_tests, "count": bo_count, "total": 2,\n                "rating": _pre_rating(bo_count, 2), "qualifies": ind["breakout"],\n            },\n            "advancing": {\n                "tests": ad_tests, "count": ad_count, "total": 3,\n                "rating": _pre_rating(ad_count, 3), "qualifies": ind["advancing"],\n            },\n            "breakdown_50D": {\n                "tests": bd50_tests, "count": bd50_count, "total": 2,\n                "rating": _pre_rating(bd50_count, 2), "qualifies": ind["breakdown_50D"],\n            },\n            "breakdown_150D": {\n                "tests": bd150_tests, "count": bd150_count, "total": 2,\n                "rating": _pre_rating(bd150_count, 2), "qualifies": ind["breakdown_150D"],\n            },\n            "breakdown_200D": {\n                "tests": bd200_tests, "count": bd200_count, "total": 2,\n                "rating": _pre_rating(bd200_count, 2), "qualifies": ind["breakdown_200D"],\n            },\n        }',
    '        md["post_indicators"] = {\n            "breakout": {\n                "tests": bo_tests, "count": bo_count, "total": 2,\n                "rating": _pre_rating(bo_count, 2), "qualifies": ind["breakout"],\n                "test_values": {\n                    "t1_price_gt_108pct_5dma": _md_v2_pct_gap(price, ma5),\n                    "t2_updown_vol_ge110": (_md_v2_round(adv_10d_up_v / adv_10d_dn_v, 3)\n                                            if adv_10d_dn_v else None),\n                },\n            },\n            "advancing": {\n                "tests": ad_tests, "count": ad_count, "total": 3,\n                "rating": _pre_rating(ad_count, 3), "qualifies": ind["advancing"],\n                "test_values": {\n                    "t1_price_above_20dma": _md_v2_pct_gap(price, ma20),\n                    "t2_20dma_rising": _md_v2_pct_gap(ma20, ma20_prev),\n                    "t3_not_in_breakout": "not in breakout" if ad_t3_not_breakout else "in breakout",\n                },\n            },\n            "breakdown_50D": {\n                "tests": bd50_tests, "count": bd50_count, "total": 2,\n                "rating": _pre_rating(bd50_count, 2), "qualifies": ind["breakdown_50D"],\n                "test_values": {\n                    "t1_price_below_50dma": _md_v2_pct_gap(price, ma50),\n                    "t2_prev_at_or_above_50dma": _md_v2_pct_gap(_price_prev, ma50_prev_v),\n                },\n            },\n            "breakdown_150D": {\n                "tests": bd150_tests, "count": bd150_count, "total": 2,\n                "rating": _pre_rating(bd150_count, 2), "qualifies": ind["breakdown_150D"],\n                "test_values": {\n                    "t1_price_below_150dma": _md_v2_pct_gap(price, ma150),\n                    "t2_prev_at_or_above_150dma": _md_v2_pct_gap(_price_prev, ma150_prev_v),\n                },\n            },\n            "breakdown_200D": {\n                "tests": bd200_tests, "count": bd200_count, "total": 2,\n                "rating": _pre_rating(bd200_count, 2), "qualifies": ind["breakdown_200D"],\n                "test_values": {\n                    "t1_price_below_200dma": _md_v2_pct_gap(price, ma200),\n                    "t2_prev_at_or_above_200dma": _md_v2_pct_gap(_price_prev, ma200_prev_v),\n                },\n            },\n        }',
))

# --- EDIT: setup_probing_bet ---
EDITS.append((
    '        setups["probing_bet"] = {\n            "tests": pbs_tests, "count": pbs_count, "total": 2,\n            "rating": _pre_rating(pbs_count, 2), "qualifies": bool(pbs_count == 2),\n        }',
    '        setups["probing_bet"] = {\n            "tests": pbs_tests, "count": pbs_count, "total": 2,\n            "rating": _pre_rating(pbs_count, 2), "qualifies": bool(pbs_count == 2),\n            "test_values": {\n                "t1_stage_qualifying_or_collapsing": (\n                    "qualifying" if pbs_t1_stage_or_collapsing else "not qualifying"),\n                "t2_breakout": "breakout" if pbs_t2_breakout else "no breakout",\n            },\n        }',
))

# --- EDIT: setup_vcp_s1 ---
EDITS.append((
    '        setups["vcp_after_s1_plateau"] = {\n            "tests": vcp_s1_tests, "count": vcp_s1_count, "total": 4,\n            "rating": _pre_rating(vcp_s1_count, 4),\n            "qualifies": bool(vcp_qualifies and s1_to_2_transition),\n            "info_stage_gate": bool(s1_to_2_transition),\n            "info_contraction_count": len(vcp_contractions),\n        }',
    '        setups["vcp_after_s1_plateau"] = {\n            "tests": vcp_s1_tests, "count": vcp_s1_count, "total": 4,\n            "rating": _pre_rating(vcp_s1_count, 4),\n            "qualifies": bool(vcp_qualifies and s1_to_2_transition),\n            "info_stage_gate": bool(s1_to_2_transition),\n            "info_contraction_count": len(vcp_contractions),\n            "test_values": _md_v2_vcp_values(vcp_tests, vcp_contractions),\n        }',
))

# --- EDIT: setup_healthy_retest ---
EDITS.append((
    '        setups["healthy_retest"] = {\n            "tests": hr_tests, "count": hr_count, "total": 6,\n            "rating": _pre_rating(hr_count, 6),\n            "qualifies": bool(hr_count == 6),\n            "info_ma_retested": utr_test_ma,\n            "info_ma_dist_pct": utr_test_ma_dist,\n            "info_retest_count": hr_retest_count,\n        }',
    '        setups["healthy_retest"] = {\n            "tests": hr_tests, "count": hr_count, "total": 6,\n            "rating": _pre_rating(hr_count, 6),\n            "qualifies": bool(hr_count == 6),\n            "info_ma_retested": utr_test_ma,\n            "info_ma_dist_pct": utr_test_ma_dist,\n            "info_retest_count": hr_retest_count,\n            "test_values": {\n                "t1_volume_contracting": _md_v2_round(utr_vol_trend, 3),\n                "t2_updown_vol_ge105": _md_v2_round(utr_updown_ratio, 3),\n                "t3_few_distribution_days": utr_dist_days,\n                "t4_volatility_contracting": _md_v2_round(utr_pullback_contraction, 3),\n                "t5_testing_meaningful_ma": (utr_test_ma if utr_test_ma else "none"),\n                "t6_buying_through_l10d": _md_v2_round(utr_candle_quality_10d, 3),\n            },\n        }',
))

# --- EDIT: setup_vcp_s2 ---
EDITS.append((
    '        setups["vcp_after_s2_base"] = {\n            "tests": vcp_s2_tests, "count": vcp_s2_count, "total": 4,\n            "rating": _pre_rating(vcp_s2_count, 4),\n            "qualifies": bool(vcp_qualifies and _s2_base_gate),\n            "info_stage_gate": _s2_base_gate,\n            "info_contraction_count": len(vcp_contractions),\n        }',
    '        setups["vcp_after_s2_base"] = {\n            "tests": vcp_s2_tests, "count": vcp_s2_count, "total": 4,\n            "rating": _pre_rating(vcp_s2_count, 4),\n            "qualifies": bool(vcp_qualifies and _s2_base_gate),\n            "info_stage_gate": _s2_base_gate,\n            "info_contraction_count": len(vcp_contractions),\n            "test_values": _md_v2_vcp_values(vcp_tests, vcp_contractions),\n        }',
))

# --- EDIT: test_ma_retest ---
EDITS.append((
    '        tests["ma_retest_upwards"] = {\n            "tests": mr_tests, "count": mr_count, "total": 8,\n            "rating": _pre_rating(mr_count, 8),\n            "qualifies": mr_qualifies,\n            "info_ma_retested": utr_test_ma,\n            "info_retest_count": (utr_retest_counts.get(utr_test_ma) if utr_test_ma else None),\n        }',
    '        tests["ma_retest_upwards"] = {\n            "tests": mr_tests, "count": mr_count, "total": 8,\n            "rating": _pre_rating(mr_count, 8),\n            "qualifies": mr_qualifies,\n            "info_ma_retested": utr_test_ma,\n            "info_retest_count": (utr_retest_counts.get(utr_test_ma) if utr_test_ma else None),\n            "test_values": {\n                "s1_volume_contracting": _md_v2_round(utr_vol_trend, 3),\n                "s2_updown_vol_ge105": _md_v2_round(utr_updown_ratio, 3),\n                "s3_few_distribution_days": utr_dist_days,\n                "s4_volatility_contracting": _md_v2_round(utr_pullback_contraction, 3),\n                "s5_testing_meaningful_ma": (utr_test_ma if utr_test_ma else "none"),\n                "s6_buying_through_l10d": _md_v2_round(utr_candle_quality_10d, 3),\n                "x1_reclaim_close_above_ma": _md_v2_pct_gap(price, _test_ma_val),\n                "x2_confirmation_close_ge2pct": _md_v2_round(close_pct_change_today),\n            },\n        }',
))

# --- EDIT: test_vcp_deploy_s1 ---
EDITS.append((
    '        tests["vcp_deploy_s1"] = {\n            "tests": vd1_tests, "count": vd1_count, "total": 7,\n            "rating": _pre_rating(vd1_count, 7),\n            "qualifies": vd1_qualifies,\n            "info_contraction_count": len(vcp_contractions),\n        }',
    '        tests["vcp_deploy_s1"] = {\n            "tests": vd1_tests, "count": vd1_count, "total": 7,\n            "rating": _pre_rating(vd1_count, 7),\n            "qualifies": vd1_qualifies,\n            "info_contraction_count": len(vcp_contractions),\n            "test_values": dict({\n                "g1_stage1_probable": (s1["rating"] if vd1_gate_s1_probable else "not probable"),\n                "x1_breakout": "breakout" if vd1_trig_breakout else "no breakout",\n                "x2_confirmation_close_ge2pct": _md_v2_round(close_pct_change_today),\n            }, **{("v" + k[1:]): v for k, v in\n                  _md_v2_vcp_values(vcp_tests, vcp_contractions).items()}),\n        }',
))

# --- EDIT: test_vcp_deploy_s2 ---
EDITS.append((
    '        tests["vcp_deploy_s2"] = {\n            "tests": vd2_tests, "count": vd2_count, "total": 7,\n            "rating": _pre_rating(vd2_count, 7),\n            "qualifies": vd2_qualifies,\n            "info_contraction_count": len(vcp_contractions),\n        }',
    '        tests["vcp_deploy_s2"] = {\n            "tests": vd2_tests, "count": vd2_count, "total": 7,\n            "rating": _pre_rating(vd2_count, 7),\n            "qualifies": vd2_qualifies,\n            "info_contraction_count": len(vcp_contractions),\n            "test_values": dict({\n                "g1_stage2_basing": ("S2 + basing" if vd2_gate_s2_basing else "gate not met"),\n                "x1_breakout": "breakout" if vd2_trig_breakout else "no breakout",\n                "x2_confirmation_close_ge2pct": _md_v2_round(close_pct_change_today),\n            }, **{("v" + k[1:]): v for k, v in\n                  _md_v2_vcp_values(vcp_tests, vcp_contractions).items()}),\n        }',
))

# --- EDIT: test_probing_bet ---
EDITS.append((
    '        tests["probing_bet"] = {\n            "tests": pbt_tests, "count": pbt_count, "total": 3,\n            "rating": _pre_rating(pbt_count, 3),\n            "qualifies": pbt_qualifies,\n            "info_pb_stage": pb_stage,\n            "info_collapsing_rating": _collapsing_rec.get("rating", "None"),\n        }',
    '        tests["probing_bet"] = {\n            "tests": pbt_tests, "count": pbt_count, "total": 3,\n            "rating": _pre_rating(pbt_count, 3),\n            "qualifies": pbt_qualifies,\n            "info_pb_stage": pb_stage,\n            "info_collapsing_rating": _collapsing_rec.get("rating", "None"),\n            "test_values": {\n                "s1_pb_stage_late_or_capital": (pb_stage if pb_stage else "none"),\n                "x1_breakout": "breakout" if pbt_trig_breakout else "no breakout",\n                "x2_confirmation_close_ge2pct": _md_v2_round(close_pct_change_today),\n            },\n        }',
))


def main():
    if not os.path.exists(TARGET):
        sys.exit("ERROR: target not found: %s" % TARGET)
    with open(TARGET, "r", encoding="utf-8") as fh:
        disk_src = fh.read()

    try:
        git_src = subprocess.check_output(
            ["git", "show", "HEAD:scripts/generate_master_data.py"],
            cwd=SCRIPT_DIR, stderr=subprocess.STDOUT,
        ).decode("utf-8")
    except subprocess.CalledProcessError as exc:
        sys.exit("ERROR: could not read git HEAD copy: %s"
                 % exc.output.decode("utf-8", "replace"))

    if MARKER in disk_src:
        print("MARKER already present in working-tree copy -- no-op.")
        return
    if MARKER in git_src:
        print("MARKER already present in git HEAD copy -- no-op.")
        return

    def apply_all(src, label):
        out = src
        cnt = out.count(HELPER_ANCHOR)
        if cnt != 1:
            sys.exit("ERROR [%s]: helper anchor count = %d (expected 1)" % (label, cnt))
        out = out.replace(HELPER_ANCHOR, HELPER_COMBINED, 1)
        for i, (anchor, repl) in enumerate(EDITS):
            c = out.count(anchor)
            if c != 1:
                sys.exit("ERROR [%s]: EDIT %d anchor count = %d (expected 1)"
                         % (label, i, c))
            out = out.replace(anchor, repl, 1)
        return out

    _ = apply_all(git_src, "git-dry-run")
    print("Dry-run against git HEAD copy: all %d anchors matched uniquely."
          % (len(EDITS) + 1))

    patched = apply_all(disk_src, "working-tree")

    try:
        ast.parse(patched)
    except SyntaxError as exc:
        sys.exit("ERROR: patched source fails ast.parse: %s" % exc)
    print("ast.parse compile-check: OK")

    with open(TMP, "w", encoding="utf-8") as fh:
        fh.write(patched)
    os.replace(TMP, TARGET)

    new_md5 = hashlib.md5(patched.encode("utf-8")).hexdigest()
    print("WROTE " + TARGET)
    print("  new size : %d bytes" % len(patched.encode("utf-8")))
    print("  new md5  : " + new_md5)
    print("  edits    : 1 helper block + %d pattern dicts" % len(EDITS))
    print("DONE.")


if __name__ == "__main__":
    main()
