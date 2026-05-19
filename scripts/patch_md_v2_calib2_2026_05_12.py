r"""
Patcher: MD V2 calibration round 2 (12-May-26)

Changes after Phase A.5 validation:
  - Patch C1: Add adv_10d_up / adv_10d_dn fields to prices.json (10D volume split)
  - Patch C2: Change Breakout indicator to use T10D up/down volume window
  - Patch C3: Drop breakout requirement from all 4 setups; setups are now PRECONDITIONS only

Operates on BYTES, CRLF-preserving, idempotent, FUSE-guarded.

MUST run Windows-side.
"""
import sys
import os
import shutil
import py_compile
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent.resolve()
TARGET = SCRIPT_DIR / "generate_master_data.py"
MARKER_BYTES = b"MD-V2-CALIB2-MARKER"
CRLF = b"\r\n"

# ── Anchors + Replacements ──

ANCHOR_VOL_SPLIT = (
    b'adv_1m_up, adv_1m_dn = _split_vol(recent_20)' + CRLF
    + b'        adv_3m_up, adv_3m_dn = _split_vol(recent_60)'
)
REPLACE_VOL_SPLIT = (
    b'adv_1m_up, adv_1m_dn = _split_vol(recent_20)' + CRLF
    + b'        adv_3m_up, adv_3m_dn = _split_vol(recent_60)' + CRLF
    + b'        # MD-V2-CALIB2-MARKER: 10D up/down volume split (added for Breakout indicator)' + CRLF
    + b'        recent_10 = rows_with_sma[-10:] if len(rows_with_sma) >= 10 else rows_with_sma' + CRLF
    + b'        adv_10d_up, adv_10d_dn = _split_vol(recent_10)'
)

ANCHOR_VOL_FIELDS_END = (
    b'"adv_3m_up": adv_3m_up,' + CRLF
    + b'            "adv_3m_dn": adv_3m_dn,'
)
REPLACE_VOL_FIELDS_END = (
    b'"adv_3m_up": adv_3m_up,' + CRLF
    + b'            "adv_3m_dn": adv_3m_dn,' + CRLF
    + b'            "adv_10d_up": adv_10d_up,' + CRLF
    + b'            "adv_10d_dn": adv_10d_dn,'
)

ANCHOR_BREAKOUT = (
    b'breakout_price = (price is not None and ma5 is not None and ma5 > 0 and price > ma5 * 1.08)' + CRLF
    + b'        breakout_vol = (adv_1m_up > 0 and adv_1m_dn > 0 and adv_1m_up >= adv_1m_dn * 1.10)' + CRLF
    + b'        ind["breakout"] = bool(breakout_price and breakout_vol)'
)
REPLACE_BREAKOUT = (
    b'breakout_price = (price is not None and ma5 is not None and ma5 > 0 and price > ma5 * 1.08)' + CRLF
    + b'        # MD-V2-CALIB2: use T10D up/down volume window (was 20D)' + CRLF
    + b'        adv_10d_up_v = p.get("adv_10d_up", 0) or 0' + CRLF
    + b'        adv_10d_dn_v = p.get("adv_10d_dn", 0) or 0' + CRLF
    + b'        breakout_vol = (adv_10d_up_v > 0 and adv_10d_dn_v > 0 and adv_10d_up_v >= adv_10d_dn_v * 1.10)' + CRLF
    + b'        ind["breakout"] = bool(breakout_price and breakout_vol)'
)

ANCHOR_SETUPS_BLOCK = (
    b'setups["probing_bet"] = bool(' + CRLF
    + b'            (s1_qualifying or s3_qualifying or s4_qualifying or ind["collapsing"]) and' + CRLF
    + b'            ind["breakout"]' + CRLF
    + b'        )'
)
REPLACE_SETUPS_BLOCK = (
    b'# MD-V2-CALIB2: setups are PRECONDITIONS only (no breakout requirement)' + CRLF
    + b'        setups["probing_bet"] = bool(' + CRLF
    + b'            (s1_qualifying or s3_qualifying or s4_qualifying or ind["collapsing"])' + CRLF
    + b'        )'
)

ANCHOR_SETUP2 = (
    b'setups["vcp_after_s1_plateau"] = bool(' + CRLF
    + b'            s1_to_2_transition and has_vcp_pattern and ind["breakout"]' + CRLF
    + b'        )'
)
REPLACE_SETUP2 = (
    b'setups["vcp_after_s1_plateau"] = bool(' + CRLF
    + b'            s1_to_2_transition and has_vcp_pattern' + CRLF
    + b'        )'
)

ANCHOR_SETUP3 = (
    b'setups["utr_after_s2_pullback"] = bool(' + CRLF
    + b'            is_s2_uptrend and ind["pullback_to_retest"] and (utr_capital or ind["breakout"])' + CRLF
    + b'        )'
)
REPLACE_SETUP3 = (
    b'setups["utr_after_s2_pullback"] = bool(' + CRLF
    + b'            is_s2_uptrend and ind["pullback_to_retest"]' + CRLF
    + b'        )'
)

ANCHOR_SETUP4 = (
    b'setups["vcp_after_s2_base"] = bool(' + CRLF
    + b'            is_s2_uptrend and ind["basing_below_high"] and has_vcp_pattern and ind["breakout"]' + CRLF
    + b'        )'
)
REPLACE_SETUP4 = (
    b'setups["vcp_after_s2_base"] = bool(' + CRLF
    + b'            is_s2_uptrend and ind["basing_below_high"] and has_vcp_pattern' + CRLF
    + b'        )'
)


def fail(msg):
    print(f"ERROR: {msg}")
    sys.exit(1)


def main():
    if not TARGET.exists():
        fail(f"{TARGET} not found")

    on_disk_size = os.path.getsize(TARGET)
    with open(TARGET, "rb") as f:
        orig = f.read()
    if on_disk_size != len(orig):
        fail(f"FUSE truncation: disk={on_disk_size} read={len(orig)}. Run Windows-side.")

    if MARKER_BYTES in orig:
        print(f"Idempotent no-op: MD-V2-CALIB2-MARKER already present ({on_disk_size} bytes)")
        return 0

    if b"MD-V2-PIPELINE-MARKER" not in orig:
        fail("Pipeline base MD-V2-PIPELINE-MARKER not found. Run patch_md_v2_pipeline first.")

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = TARGET.with_suffix(f".py.bak-pre-calib2-{ts}")
    shutil.copy2(TARGET, bak)
    print(f"Backup: {bak.name} ({len(orig):,} bytes)")

    patches = [
        ("C1a-vol-split-compute",    ANCHOR_VOL_SPLIT,       REPLACE_VOL_SPLIT),
        ("C1b-vol-fields-in-entry",  ANCHOR_VOL_FIELDS_END,  REPLACE_VOL_FIELDS_END),
        ("C2-breakout-10d-window",   ANCHOR_BREAKOUT,        REPLACE_BREAKOUT),
        ("C3a-setup-pb",             ANCHOR_SETUPS_BLOCK,    REPLACE_SETUPS_BLOCK),
        ("C3b-setup-vcp-s1",         ANCHOR_SETUP2,          REPLACE_SETUP2),
        ("C3c-setup-utr",            ANCHOR_SETUP3,          REPLACE_SETUP3),
        ("C3d-setup-vcp-s2",         ANCHOR_SETUP4,          REPLACE_SETUP4),
    ]

    new = orig
    applied = 0
    for name, anchor, replace in patches:
        c = new.count(anchor)
        if c == 0:
            fail(f"Anchor '{name}' not found")
        if c > 1:
            fail(f"Anchor '{name}' matched {c}x (expected 1)")
        new = new.replace(anchor, replace, 1)
        applied += 1
        print(f"  Applied: {name}")

    print(f"\nSize: {len(orig):,} -> {len(new):,} (+{len(new) - len(orig):,} bytes)")

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
    if os.path.getsize(TARGET) != len(final):
        shutil.copy2(bak, TARGET)
        fail(f"Post-write truncation. Restored.")

    print(f"\nSUCCESS. {TARGET.name} now {os.path.getsize(TARGET):,} bytes ({applied} patches applied).")
    print(f"\nNext: re-run pipeline Windows-side:")
    print(f"  python scripts\\generate_master_data.py --full-universe --with-history")
    return 0


if __name__ == "__main__":
    sys.exit(main())
