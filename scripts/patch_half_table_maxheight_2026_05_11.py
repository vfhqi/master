"""
Patcher D — .half-table .data-table-wrap max-height cap (11-May-26)
==================================================================

Issue: MM99 Industries tile renders at ~450px (15 rows), Sectors tile
renders at ~2,100px (87 rows). The min-height:450 cap I added in
Patcher A floored Industries correctly but doesn't constrain Sectors.

Fix: add max-height:600px so the table area caps at a consistent
height across all tabs (MM99 / BP / PB / UTR / TIMELINESS / SSEM /
CHANGES-aggregate tiles). The existing overflow-y:auto handles
internal scrolling. Industries (short) stays at min-height 450;
Sectors (long) caps at 600 with scrollbar — both visually balanced.

Idempotent via marker check. Surgical single-line edit.
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
TARGET = PROJECT_DIR / "scripts" / "build_dashboard.py"

MARKER = "HALF-TABLE-MAX-HEIGHT"


def main():
    print(f"Patching: {TARGET}")
    if not TARGET.exists():
        print("  ERROR: target not found")
        sys.exit(1)

    content = TARGET.read_text(encoding="utf-8")
    if MARKER in content:
        print("  marker present; nothing to do")
        sys.exit(0)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = TARGET.with_suffix(TARGET.suffix + f".bak-pre-half-table-maxh-{ts}")
    shutil.copy2(TARGET, bak)
    print(f"  backup -> {bak.name}")

    # The current line (from Patcher A which added min-height:450px):
    OLD = ".half-table .data-table-wrap{overflow-y:auto;overflow-x:hidden;min-height:450px}"
    NEW = "/*" + MARKER + "*/.half-table .data-table-wrap{overflow-y:auto;overflow-x:hidden;min-height:450px;max-height:600px}"

    n = content.count(OLD)
    if n == 0:
        print("  ERROR: anchor not found (was Patcher A run?)")
        sys.exit(1)
    if n > 1:
        print(f"  ERROR: anchor matches {n} times (must be unique)")
        sys.exit(1)

    original_len = len(content)
    content = content.replace(OLD, NEW, 1)
    new_len = len(content)

    TARGET.write_text(content, encoding="utf-8")
    print(f"  wrote {new_len:,} bytes (delta {new_len - original_len:+,})")

    import py_compile
    try:
        py_compile.compile(str(TARGET), doraise=True)
        print("  py_compile: OK")
    except py_compile.PyCompileError as e:
        print(f"  py_compile FAILED: {e}")
        sys.exit(1)

    print("  done. Run: python scripts\\build_dashboard.py")


if __name__ == "__main__":
    main()
