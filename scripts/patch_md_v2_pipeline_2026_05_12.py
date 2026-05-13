r"""
Patcher: MD V2 Pipeline (12-May-26)

Adds Master Dashboard V2 screens to generate_master_data.py:
  1. Historical MA samples (150D / 200D / 20D / Volume 200D) — 12-month detail
  2. Higher-lows / lower-lows pattern recognition
  3. Base count since 52W low (15% fall + 20 days below + breakthrough)
  4. RS percentile at M=-3
  5. Recent pullback % from swing high
  6. NEW function compute_master_dashboard_screens() — 4 stages + 7 indicators + 4 setups + 3 tests + persistence

Idempotent. Pre-write backup. py_compile verification. FUSE truncation guard.
Operates on BYTES to preserve Windows CRLF line endings.

MUST run Windows-side.

Run:
  cd C:\Users\richb\Documents\COWORK\master-dashboard
  python scripts\patch_md_v2_pipeline_2026_05_12.py
"""
import sys
import os
import shutil
import py_compile
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent.resolve()
TARGET = SCRIPT_DIR / "generate_master_data.py"
MARKER_BYTES = b"MD-V2-PIPELINE-MARKER"
CRLF = b"\r\n"

# ── Sidecar file paths (next to patcher, written by patcher) ──
# The parts are embedded below as multi-line strings and re-emitted at injection time.

PARTS_1_2_INDENTED = '''
        # ── MD-V2-PIPELINE-MARKER: Historical MA samples + base detection ──
        # ── MD V2: 12-month MA samples (150D, 200D) + Volume 200D-MA trend ──
        def _sample_monthly_ma(rows, sma_key, n_months=13):
            samples = []
            for mi in range(n_months):
                idx = len(rows) - 1 - (mi * 21)
                if idx >= 0 and rows[idx].get(sma_key) is not None:
                    samples.append(rows[idx][sma_key])
                else:
                    samples.append(None)
            samples.reverse()
            return samples

        def _decline_rates(samples):
            rates = []
            for i in range(1, len(samples)):
                if samples[i] is None or samples[i - 1] is None or samples[i - 1] == 0:
                    rates.append(None)
                else:
                    rates.append((samples[i] - samples[i - 1]) / samples[i - 1])
            return rates

        ma150_samples = _sample_monthly_ma(rows_with_sma, "sma_150") if len(rows_with_sma) >= 252 else [None] * 13
        ma200_samples = _sample_monthly_ma(rows_with_sma, "sma_200") if len(rows_with_sma) >= 252 else [None] * 13
        ma150_mom_rates = _decline_rates(ma150_samples)
        ma200_mom_rates = _decline_rates(ma200_samples)

        # Volume MA-200 trend
        vol200_samples = []
        volumes = [r["volume"] for r in rows_with_sma]
        for mi in range(13):
            idx = len(rows_with_sma) - 1 - (mi * 21)
            if idx >= 199:
                v200 = sum(volumes[idx - 199:idx + 1]) / 200.0
                vol200_samples.append(v200)
            else:
                vol200_samples.append(None)
        vol200_samples.reverse()
        vol_ma200_month_detail = []
        vol_ma200_months_rising = 0
        for mi in range(1, len(vol200_samples)):
            if vol200_samples[mi] is not None and vol200_samples[mi - 1] is not None:
                rising = vol200_samples[mi] > vol200_samples[mi - 1]
                vol_ma200_month_detail.append(rising)
                if rising:
                    vol_ma200_months_rising += 1
            else:
                vol_ma200_month_detail.append(False)

        # 20D MA monthly history
        ma20_samples = _sample_monthly_ma(rows_with_sma, "sma_20") if len(rows_with_sma) >= 32 else [None] * 13
        ma20_month_detail = []
        ma20_months_rising = 0
        for mi in range(1, len(ma20_samples)):
            if ma20_samples[mi] is not None and ma20_samples[mi - 1] is not None:
                rising = ma20_samples[mi] > ma20_samples[mi - 1]
                ma20_month_detail.append(rising)
                if rising:
                    ma20_months_rising += 1
            else:
                ma20_month_detail.append(False)

        # ── Base count since 52W low (15% fall + 20 days below high + breakthrough) ──
        base_count_since_52wl = 0
        if len(rows_with_sma) >= 252:
            last_252 = rows_with_sma[-252:]
            lows_252 = [r["low"] for r in last_252]
            min_low_idx_rel = lows_252.index(min(lows_252))
            start_idx_global = len(rows_with_sma) - 252 + min_low_idx_rel
            swing_window_bp = 5
            completed_swing_highs = []
            for sj in range(start_idx_global + swing_window_bp, len(rows_with_sma) - swing_window_bp):
                candidate = rows_with_sma[sj]["high"]
                is_peak = True
                for sk in range(sj - swing_window_bp, sj + swing_window_bp + 1):
                    if sk != sj and rows_with_sma[sk]["high"] > candidate:
                        is_peak = False
                        break
                if is_peak:
                    completed_swing_highs.append((sj, candidate))
            for sj_idx, sj_high in completed_swing_highs:
                sub_end = len(rows_with_sma)
                for nh_idx, _ in completed_swing_highs:
                    if nh_idx > sj_idx:
                        sub_end = nh_idx
                        break
                sub_window = rows_with_sma[sj_idx + 1:sub_end]
                if not sub_window:
                    continue
                sub_low = min(r["low"] for r in sub_window)
                if sub_low > sj_high * 0.85:
                    continue
                days_below = sum(1 for r in sub_window if r["high"] < sj_high)
                if days_below < 20:
                    continue
                sub_low_idx_in_sub = next(i for i, r in enumerate(sub_window) if r["low"] == sub_low)
                post_low_window = sub_window[sub_low_idx_in_sub:]
                breakthrough = any(r["high"] > sj_high for r in post_low_window)
                if breakthrough:
                    base_count_since_52wl += 1

        # ── Higher-lows / Lower-lows count (last 6 months) ──
        higher_lows_count = 0
        lower_lows_count = 0
        if len(rows_with_sma) >= 126:
            trough_window = 5
            swing_lows = []
            recent_180 = rows_with_sma[-180:] if len(rows_with_sma) >= 180 else rows_with_sma
            for ti in range(trough_window, len(recent_180) - trough_window):
                candidate = recent_180[ti]["low"]
                is_trough = True
                for tj in range(ti - trough_window, ti + trough_window + 1):
                    if tj != ti and recent_180[tj]["low"] < candidate:
                        is_trough = False
                        break
                if is_trough:
                    swing_lows.append((ti, candidate))
            if len(swing_lows) >= 2:
                higher_lows_count = 1
                for k in range(len(swing_lows) - 1, 0, -1):
                    if swing_lows[k][1] > swing_lows[k - 1][1]:
                        higher_lows_count += 1
                    else:
                        break
                lower_lows_count = 1
                for k in range(len(swing_lows) - 1, 0, -1):
                    if swing_lows[k][1] < swing_lows[k - 1][1]:
                        lower_lows_count += 1
                    else:
                        break

        # ── RS at M=-3 (composite-only; percentile computed in second pass) ──
        rs_at_m3 = None
        if len(rows_with_sma) >= 126 and benchmark_rows and len(benchmark_rows) >= 126:
            try:
                sliced_stock = rows_with_sma[:-63]
                sliced_bench = benchmark_rows[:len(sliced_stock)] if len(benchmark_rows) >= len(sliced_stock) else benchmark_rows
                if len(sliced_stock) >= 252 and len(sliced_bench) >= 252:
                    rs_m3_composite, _ = compute_rs_composite(sliced_stock, sliced_bench)
                    rs_at_m3 = rs_m3_composite
            except Exception:
                rs_at_m3 = None

        # ── Recent pullback % from swing high ──
        recent_pullback_pct = None
        if swing_high and swing_high > 0:
            recent_pullback_pct = round((swing_high - latest["close"]) / swing_high, 4)
        # ── END MD-V2-PIPELINE-MARKER block ──
'''

NEW_ENTRY_FIELDS = '''            # MD V2 historical fields
            "ma150_samples": [round(s, 4) if s is not None else None for s in ma150_samples],
            "ma200_samples": [round(s, 4) if s is not None else None for s in ma200_samples],
            "ma150_mom_rates": [round(r, 5) if r is not None else None for r in ma150_mom_rates],
            "ma200_mom_rates": [round(r, 5) if r is not None else None for r in ma200_mom_rates],
            "vol_ma200_month_detail": vol_ma200_month_detail,
            "vol_ma200_months_rising": vol_ma200_months_rising,
            "ma20_month_detail": ma20_month_detail,
            "ma20_months_rising": ma20_months_rising,
            "base_count_since_52wl": base_count_since_52wl,
            "higher_lows_count": higher_lows_count,
            "lower_lows_count": lower_lows_count,
            "rs_at_m3": rs_at_m3,
            "recent_pullback_pct": recent_pullback_pct,
'''

# COMPUTE_MD_SCREENS_FN is loaded from sidecar file at runtime (too large to inline cleanly here).
# Located at scripts/_md_v2_screens.py (must be present alongside this patcher).

# ── ANCHORS (exact bytes from the baseline file) ──
ANCHOR_HISTORY_INJECTION = (
    b'utr_retest_counts[_ma_label] = _count' + CRLF
    + CRLF
    + b'        entry = {'
)

ANCHOR_ENTRY_FIELDS_INJECTION = (
    b'            "utr_retest_counts": utr_retest_counts,   # {"50D": N, "100D": N, "150D": N}' + CRLF
    + b'        }' + CRLF
    + b'        prices.append(entry)'
)

ANCHOR_FN_INJECTION = (
    b'    return results' + CRLF
    + CRLF
    + CRLF
    + b'# \xe2\x94\x80\xe2\x94\x80 Historical Stage Computation (D-MD-DATA-6) '
)  # bytes of "── " unicode are e2 94 80

ANCHOR_MAIN_CALL_INJECTION = (
    b'    filter_results = compute_all_filters(prices)' + CRLF
    + b'    with open(DATA_DIR / "filter-results.json", "w") as f:'
)


def fail(msg):
    print(f"ERROR: {msg}")
    sys.exit(1)


def main():
    if not TARGET.exists():
        fail(f"generate_master_data.py not found at {TARGET}")

    sidecar = SCRIPT_DIR / "_md_v2_screens.py"
    if not sidecar.exists():
        fail(f"Sidecar function file not found: {sidecar}")
    with open(sidecar, "rb") as f:
        screens_fn = f.read()
    print(f"Sidecar function file: {len(screens_fn):,} bytes")

    on_disk_size = os.path.getsize(TARGET)
    with open(TARGET, "rb") as f:
        orig = f.read()
    orig_size = len(orig)
    if on_disk_size != orig_size:
        fail(f"FUSE TRUNCATION DETECTED. disk={on_disk_size} read={orig_size}. Run Windows-side.")

    EXPECTED_BASELINE_SIZE = 77974
    if orig_size < EXPECTED_BASELINE_SIZE - 100:
        fail(f"Size {orig_size} below baseline {EXPECTED_BASELINE_SIZE}.")

    if MARKER_BYTES in orig:
        print(f"Idempotent no-op: MD-V2-PIPELINE-MARKER already present ({orig_size} bytes).")
        return 0

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = TARGET.with_suffix(f".py.bak-pre-md-v2-{ts}")
    shutil.copy2(TARGET, bak)
    print(f"Backup: {bak.name} ({orig_size:,} bytes)")

    # Normalize the embedded strings to CRLF (source file is CRLF)
    parts12 = PARTS_1_2_INDENTED.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
    entry_fields = NEW_ENTRY_FIELDS.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
    screens_fn_crlf = screens_fn.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")

    new = orig
    patches_applied = 0

    # Patch 1: Inject parts 1+2 into build_prices_json before "entry = {"
    if new.count(ANCHOR_HISTORY_INJECTION) != 1:
        fail(f"ANCHOR_HISTORY_INJECTION matches {new.count(ANCHOR_HISTORY_INJECTION)}x. Expected 1.")
    replacement_1 = (
        b'utr_retest_counts[_ma_label] = _count' + CRLF
        + CRLF
        + parts12
        + CRLF
        + b'        entry = {'
    )
    new = new.replace(ANCHOR_HISTORY_INJECTION, replacement_1, 1)
    patches_applied += 1
    print("  Applied: History injection into build_prices_json")

    # Patch 2: Inject new fields into entry dict
    if new.count(ANCHOR_ENTRY_FIELDS_INJECTION) != 1:
        fail(f"ANCHOR_ENTRY_FIELDS_INJECTION matches {new.count(ANCHOR_ENTRY_FIELDS_INJECTION)}x.")
    replacement_2 = (
        b'            "utr_retest_counts": utr_retest_counts,   # {"50D": N, "100D": N, "150D": N}' + CRLF
        + entry_fields
        + b'        }' + CRLF
        + b'        prices.append(entry)'
    )
    new = new.replace(ANCHOR_ENTRY_FIELDS_INJECTION, replacement_2, 1)
    patches_applied += 1
    print("  Applied: Entry-dict new fields injection")

    # Patch 3: Insert compute_master_dashboard_screens function before compute_historical_stages
    if new.count(ANCHOR_FN_INJECTION) != 1:
        fail(f"ANCHOR_FN_INJECTION matches {new.count(ANCHOR_FN_INJECTION)}x.")
    replacement_3 = (
        b'    return results' + CRLF
        + CRLF
        + CRLF
        + screens_fn_crlf + CRLF
        + CRLF
        + b'# \xe2\x94\x80\xe2\x94\x80 Historical Stage Computation (D-MD-DATA-6) '
    )
    new = new.replace(ANCHOR_FN_INJECTION, replacement_3, 1)
    patches_applied += 1
    print("  Applied: compute_master_dashboard_screens function injection")

    # Patch 4: Wire it into main() after compute_all_filters call
    if new.count(ANCHOR_MAIN_CALL_INJECTION) != 1:
        fail(f"ANCHOR_MAIN_CALL_INJECTION matches {new.count(ANCHOR_MAIN_CALL_INJECTION)}x.")
    replacement_4 = (
        b'    filter_results = compute_all_filters(prices)' + CRLF
        + b'    print("\\n\xe2\x94\x80\xe2\x94\x80 Computing MD V2 screens \xe2\x94\x80\xe2\x94\x80")' + CRLF
        + b'    filter_results = compute_master_dashboard_screens(prices, filter_results)' + CRLF
        + b'    print(f"  Attached md_v2 to {len(filter_results)} stocks")' + CRLF
        + b'    with open(DATA_DIR / "filter-results.json", "w") as f:'
    )
    new = new.replace(ANCHOR_MAIN_CALL_INJECTION, replacement_4, 1)
    patches_applied += 1
    print("  Applied: main() wiring for MD V2 screens")

    new_size = len(new)
    delta = new_size - orig_size
    print(f"\nSize: {orig_size:,} -> {new_size:,} (+{delta:,} bytes)")

    expected_min = len(parts12) + len(entry_fields) + len(screens_fn_crlf) + 100
    expected_max = expected_min + 1000
    if delta < expected_min or delta > expected_max:
        fail(f"Delta {delta} outside [{expected_min}, {expected_max}].")

    with open(TARGET, "wb") as f:
        f.write(new)

    try:
        py_compile.compile(str(TARGET), doraise=True)
        print("py_compile: OK")
    except py_compile.PyCompileError as e:
        shutil.copy2(bak, TARGET)
        fail(f"py_compile FAILED. Backup restored.\n{e}")

    with open(TARGET, "rb") as f:
        final = f.read()
    if MARKER_BYTES not in final:
        shutil.copy2(bak, TARGET)
        fail("Marker missing after write. Backup restored.")

    final_disk = os.path.getsize(TARGET)
    if final_disk != len(final):
        shutil.copy2(bak, TARGET)
        fail(f"Post-write truncation (disk={final_disk} read={len(final)}). Restored.")

    print(f"\nSUCCESS. {TARGET.name} now {final_disk:,} bytes ({patches_applied} patches applied).")
    print(f"\nNext: re-run the data pipeline Windows-side:")
    print(f"  python scripts\\generate_master_data.py --full-universe --with-history")
    return 0


if __name__ == "__main__":
    sys.exit(main())
