#!/usr/bin/env python3
"""Patcher — fix render-loop bounds after S3 + S4 column additions.

Stage 3 had 10 test columns (indexes 9-18, persist at 19 originally
incorrect). Now has 11 test columns with new prior-uptrend column.
Render loop must extend to index 18 inclusive (was 17 in test terms).

Stage 4 had 7 test columns (indexes 9-15). Now has 8 with new S3 lookback.
Render loop must extend to index 16.

Created 2026-05-19 by SA.
"""
import hashlib, shutil, sys, tempfile
from pathlib import Path

BDB = Path("/sessions/admiring-jolly-noether/mnt/COWORK/master-dashboard/scripts/build_dashboard.py")


def _md5(p): return hashlib.md5(p.read_bytes()).hexdigest()


def main():
    t = BDB.read_text(encoding="utf-8")

    # S3: was `j <= 18` (10 test cells, indexes 9-18) — now needs 11 cells, j <= 19? Actually let me think.
    # Original S3_COLS indices: 0..17 test cells; 18 was persist. Loop `j <= 18` includes persist.
    # New S3_COLS indices: 9..18 are now 10 test cells + 1 new prior-uptrend = 11 test cells (9..19), persist at 20.
    # Need loop `j <= 19` (covers all 11 tests, leaves persist for its own renderer)
    # But existing pattern `j <= 18` includes persist — that means existing render WAS including persist via test cell renderer. Odd.
    # Let me preserve the original "+1" extension since I added 1 column: 18 -> 19.

    edits = [
        ("S3 render loop", "for (var j = 9; j <= 18; j++) html += s3TestCell(s, S3_COLS[j]);",
                            "for (var j = 9; j <= 19; j++) html += s3TestCell(s, S3_COLS[j]);"),
        ("S4 render loop", "for (var j = 9; j <= 15; j++) html += s4TestCell(s, S4_COLS[j]);",
                            "for (var j = 9; j <= 16; j++) html += s4TestCell(s, S4_COLS[j]);"),
    ]
    for n, o, nw in edits:
        if t.count(o) != 1:
            sys.exit(f"  ABORT {n}")
        t = t.replace(o, nw)
        print(f"  {n}: applied")

    exp = hashlib.md5(t.encode()).hexdigest()
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".py") as tf:
        tf.write(t); tmp = Path(tf.name)
    if _md5(tmp) != exp: sys.exit("tmp mismatch")
    shutil.copy2(tmp, BDB)
    if _md5(BDB) != exp: sys.exit("post-cp mismatch")
    tmp.unlink()
    print(f"  WROTE  md5 {exp[:8]}")

    import py_compile
    py_compile.compile(str(BDB), doraise=True)
    print("  py_compile OK")


if __name__ == "__main__":
    main()
