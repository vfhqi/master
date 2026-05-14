#!/usr/bin/env python3
# =============================================================================
# patch_md_v2_pipeline_fields_2026_05_14.py
# -----------------------------------------------------------------------------
# Adds pipeline fields required by the Pre-test indicators V2 rebuild
# (Session 25, 14-May-26). Locked decisions D-MD-V2-49 through D-MD-V2-54.
#
# New fields added to generate_master_data.py per-stock `entry` dict:
#   max_pullback_since_swing_high  - max drawdown from swing high (D-MD-V2-49 t1)
#   days_below_swing_high          - trading days price has been below swing high (t2)
#   utr_candle_quality_10d         - 10-day candle quality (D-MD-V2-51 t6)
#   utr_candle_quality_3d          - 3-day candle quality (D-MD-V2-52 t3)
#   utr_updown_ratio_5d            - 5-day up/down volume ratio (D-MD-V2-52 t4)
#   close_pct_change_today         - (close - prev_close)/prev_close (D-MD-V2-52 t5)
#
# Discipline (D-MD-V2-43): this file authored via heredoc -> /tmp -> atomic cp
#   -> MD5 byte-verify. Patcher itself: idempotent, anchor-string replace,
#   pre-write backup, py_compile clean, atomic write at END.
# =============================================================================
import sys, os, shutil, hashlib, py_compile, tempfile
from datetime import datetime

TARGET = os.path.join(os.path.dirname(os.path.abspath(__file__)), "generate_master_data.py")
MARKER = "MD-V2-PIPELINE-FIELDS-S25-MARKER"

def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()

def main():
    if not os.path.exists(TARGET):
        print("ERROR: target not found: %s" % TARGET); sys.exit(1)

    with open(TARGET, "r", encoding="utf-8") as f:
        src = f.read()

    if MARKER in src:
        print("IDEMPOTENT: %s already present. No-op." % MARKER)
        sys.exit(0)

    orig_len = len(src)

    # -------------------------------------------------------------------------
    # EDIT 1 - capture swing-high index in the swing-high detection block.
    # Anchor: the swing-high loop sets `swing_high = candidate` then `break`.
    # We add an index capture alongside.
    # -------------------------------------------------------------------------
    anchor1 = (
        "        swing_high = high_52w  # fallback to 52W high\n"
        "        lookback_for_swing = rows_with_sma[-126:] if len(rows_with_sma) >= 126 else rows_with_sma  # 6 months\n"
        "        swing_window = 5  # days on each side\n"
        "        for si in range(len(lookback_for_swing) - 1, swing_window - 1, -1):\n"
        "            candidate = lookback_for_swing[si][\"high\"]\n"
        "            is_peak = True\n"
        "            for sj in range(max(0, si - swing_window), min(len(lookback_for_swing), si + swing_window + 1)):\n"
        "                if sj != si and lookback_for_swing[sj][\"high\"] > candidate:\n"
        "                    is_peak = False\n"
        "                    break\n"
        "            if is_peak:\n"
        "                swing_high = candidate\n"
        "                break\n"
    )
    replace1 = (
        "        swing_high = high_52w  # fallback to 52W high\n"
        "        lookback_for_swing = rows_with_sma[-126:] if len(rows_with_sma) >= 126 else rows_with_sma  # 6 months\n"
        "        swing_window = 5  # days on each side\n"
        "        swing_high_global_idx = None  # " + MARKER + ": index into rows_with_sma of the swing high\n"
        "        for si in range(len(lookback_for_swing) - 1, swing_window - 1, -1):\n"
        "            candidate = lookback_for_swing[si][\"high\"]\n"
        "            is_peak = True\n"
        "            for sj in range(max(0, si - swing_window), min(len(lookback_for_swing), si + swing_window + 1)):\n"
        "                if sj != si and lookback_for_swing[sj][\"high\"] > candidate:\n"
        "                    is_peak = False\n"
        "                    break\n"
        "            if is_peak:\n"
        "                swing_high = candidate\n"
        "                # map local swing index -> global index into rows_with_sma\n"
        "                swing_high_global_idx = len(rows_with_sma) - len(lookback_for_swing) + si\n"
        "                break\n"
    )
    if anchor1 not in src:
        print("ERROR: EDIT 1 anchor not found (swing-high detection block)."); sys.exit(1)
    src = src.replace(anchor1, replace1, 1)

    # -------------------------------------------------------------------------
    # EDIT 2 - compute the new fields. Anchor on the existing
    # "Recent pullback %" block inside the MD-V2-PIPELINE-MARKER region.
    # -------------------------------------------------------------------------
    anchor2 = (
        "        # ── Recent pullback % from swing high ──\n"
        "        recent_pullback_pct = None\n"
        "        if swing_high and swing_high > 0:\n"
        "            recent_pullback_pct = round((swing_high - latest[\"close\"]) / swing_high, 4)\n"
        "        # ── END MD-V2-PIPELINE-MARKER block ──\n"
    )
    replace2 = (
        "        # ── Recent pullback % from swing high ──\n"
        "        recent_pullback_pct = None\n"
        "        if swing_high and swing_high > 0:\n"
        "            recent_pullback_pct = round((swing_high - latest[\"close\"]) / swing_high, 4)\n"
        "\n"
        "        # ── " + MARKER + ": Session 25 pipeline fields ──\n"
        "        # max_pullback_since_swing_high (D-MD-V2-49 test 1): the DEEPEST drawdown\n"
        "        # from the swing high reached on/after the swing-high day - even if price\n"
        "        # has since reclawed some of the loss. recent_pullback_pct measures only\n"
        "        # the CURRENT distance, which is insufficient for the Basing test.\n"
        "        max_pullback_since_swing_high = None\n"
        "        days_below_swing_high = None\n"
        "        if swing_high and swing_high > 0 and swing_high_global_idx is not None:\n"
        "            _post_rows = rows_with_sma[swing_high_global_idx:]\n"
        "            if _post_rows:\n"
        "                _min_low = min(r[\"low\"] for r in _post_rows)\n"
        "                max_pullback_since_swing_high = round((swing_high - _min_low) / swing_high, 4)\n"
        "            # days_below_swing_high (D-MD-V2-49 test 2): count trailing trading days\n"
        "            # where the close has been below the swing high. Counts back from the\n"
        "            # latest row until a day closes at/above the swing high.\n"
        "            _dbsh = 0\n"
        "            for _r in reversed(rows_with_sma):\n"
        "                if _r[\"close\"] < swing_high:\n"
        "                    _dbsh += 1\n"
        "                else:\n"
        "                    break\n"
        "            days_below_swing_high = _dbsh\n"
        "\n"
        "        # utr_candle_quality_10d / _3d (D-MD-V2-51 t6 / D-MD-V2-52 t3):\n"
        "        # same logic as the existing 20-day utr_candle_quality - proportion of\n"
        "        # days whose close sits in the UPPER 40% of the daily range\n"
        "        # (close >= low + 0.6 * range). Windowed to 10 and 3 trading days.\n"
        "        def _candle_quality(window):\n"
        "            _uc = 0\n"
        "            _vd = 0\n"
        "            for _cr in window:\n"
        "                _rng = _cr[\"high\"] - _cr[\"low\"]\n"
        "                if _rng > 0:\n"
        "                    _vd += 1\n"
        "                    if _cr[\"close\"] >= _cr[\"low\"] + 0.6 * _rng:\n"
        "                        _uc += 1\n"
        "            return round(_uc / _vd, 4) if _vd > 0 else None\n"
        "        _cq10_window = rows_with_sma[-10:] if len(rows_with_sma) >= 10 else rows_with_sma\n"
        "        _cq3_window = rows_with_sma[-3:] if len(rows_with_sma) >= 3 else rows_with_sma\n"
        "        utr_candle_quality_10d = _candle_quality(_cq10_window)\n"
        "        utr_candle_quality_3d = _candle_quality(_cq3_window)\n"
        "\n"
        "        # utr_updown_ratio_5d (D-MD-V2-52 t4): up-day vol / down-day vol over the\n"
        "        # last 5 trading days only. Reuses the existing _split_vol helper.\n"
        "        _recent_5 = rows_with_sma[-5:] if len(rows_with_sma) >= 5 else rows_with_sma\n"
        "        _adv_5d_up, _adv_5d_dn = _split_vol(_recent_5)\n"
        "        utr_updown_ratio_5d = round(_adv_5d_up / _adv_5d_dn, 4) if _adv_5d_dn > 0 else None\n"
        "\n"
        "        # close_pct_change_today (D-MD-V2-52 t5 confirmation): today's close vs\n"
        "        # yesterday's close as a fraction. >= 0.02 satisfies the confirmation test.\n"
        "        close_pct_change_today = None\n"
        "        if prev[\"close\"] and prev[\"close\"] > 0:\n"
        "            close_pct_change_today = round((latest[\"close\"] - prev[\"close\"]) / prev[\"close\"], 4)\n"
        "        # ── END " + MARKER + " block ──\n"
        "        # ── END MD-V2-PIPELINE-MARKER block ──\n"
    )
    if anchor2 not in src:
        print("ERROR: EDIT 2 anchor not found (Recent pullback %% block)."); sys.exit(1)
    src = src.replace(anchor2, replace2, 1)

    # -------------------------------------------------------------------------
    # EDIT 3 - add the new fields to the `entry` dict.
    # Anchor on the existing recent_pullback_pct entry-dict line.
    # -------------------------------------------------------------------------
    anchor3 = '            "recent_pullback_pct": recent_pullback_pct,\n        }\n'
    replace3 = (
        '            "recent_pullback_pct": recent_pullback_pct,\n'
        "            # " + MARKER + ": Session 25 fields\n"
        '            "max_pullback_since_swing_high": max_pullback_since_swing_high,\n'
        '            "days_below_swing_high": days_below_swing_high,\n'
        '            "utr_candle_quality_10d": utr_candle_quality_10d,\n'
        '            "utr_candle_quality_3d": utr_candle_quality_3d,\n'
        '            "utr_updown_ratio_5d": utr_updown_ratio_5d,\n'
        '            "close_pct_change_today": close_pct_change_today,\n'
        "        }\n"
    )
    if anchor3 not in src:
        print("ERROR: EDIT 3 anchor not found (entry dict recent_pullback_pct line)."); sys.exit(1)
    src = src.replace(anchor3, replace3, 1)

    # -------------------------------------------------------------------------
    # Validate in /tmp, then pre-write backup, then atomic write.
    # -------------------------------------------------------------------------
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".py", prefix="gmd_patch_")
    os.close(tmp_fd)
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(src)

    try:
        py_compile.compile(tmp_path, doraise=True)
    except py_compile.PyCompileError as e:
        print("ERROR: patched source fails py_compile:\n%s" % e)
        os.unlink(tmp_path)
        sys.exit(1)

    if b"\x00" in src.encode("utf-8"):
        print("ERROR: null bytes detected in patched source - aborting.")
        os.unlink(tmp_path)
        sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = TARGET + ".bak-pre-md-v2-pipeline-fields-s25-" + ts
    shutil.copy2(TARGET, backup)
    print("Pre-write backup: %s" % backup)

    shutil.copy2(tmp_path, TARGET)
    os.unlink(tmp_path)

    new_len = len(src)
    print("OK: generate_master_data.py patched.")
    print("    %d bytes -> %d bytes (delta +%d)" % (orig_len, new_len, new_len - orig_len))
    print("    marker: %s" % MARKER)

    # post-write verification
    with open(TARGET, "r", encoding="utf-8") as f:
        check = f.read()
    if MARKER not in check:
        print("ERROR: post-write verification failed - marker missing!"); sys.exit(1)
    if check.count("max_pullback_since_swing_high") < 3:
        print("ERROR: post-write verification - expected >=3 mentions of max_pullback_since_swing_high"); sys.exit(1)
    print("Post-write verification: PASS (marker present, 3 edits applied).")

if __name__ == "__main__":
    main()
