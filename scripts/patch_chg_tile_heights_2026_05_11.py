"""
Patcher C — CHANGES tile height + equal-row fixup (11-May-26)
=============================================================

Issue diagnosed post-Patcher-B:
  - Each tile-row uses flex:1 + flex-grow + no height constraint
  - Probing Bet tile has 484 stocks (T-0 PB Capital count) which
    makes the row 10,498px tall; Collapse / VCP / S3 / S4 tiles
    in that row inherit the same height as empty whitespace
  - Net: huge vertical waste, unusable scroll experience

Fix:
  - Apply max-height:480px + overflow-y:auto INSIDE each tile's
    stock-grid section (the rows live inside a wrapper div which
    becomes the scrollport, leaving the tile header fixed)
  - Tile box itself stays at natural height; tall tiles cap at
    ~520px (header + 480px grid); short tiles stay short
  - Add align-items:flex-start on tile-row so short tiles don't
    visually stretch to match tall ones
  - Add a small min-height to tile-row content for zero-change
    tiles so they don't look orphaned ("No changes in last month")

Idempotent via marker. Surgical replacement of the row container
opener and the grid container opener in renderChanges V2 block.

Usage:
  cd C:\\Users\\richb\\Documents\\COWORK\\master-dashboard
  python scripts\\patch_chg_tile_heights_2026_05_11.py
  python scripts\\build_dashboard.py
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
TARGET = PROJECT_DIR / "scripts" / "build_dashboard.py"

MARKER = "CHG-TILE-HEIGHTS-FIXUP"


def backup(p):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = p.with_suffix(p.suffix + f".bak-pre-chg-tile-heights-{ts}")
    shutil.copy2(p, bak)
    print(f"  backup -> {bak.name}")


def replace_once(content, old, new, label):
    n = content.count(old)
    if n == 0:
        print(f"  [{label}] anchor not found")
        sys.exit(1)
    if n > 1:
        print(f"  [{label}] anchor matches {n} times (must be unique)")
        sys.exit(1)
    return content.replace(old, new)


def main():
    print(f"Patching: {TARGET}")
    if not TARGET.exists():
        print("  ERROR: target not found")
        sys.exit(1)

    content = TARGET.read_text(encoding="utf-8")
    if MARKER in content:
        print(f"  marker present; nothing to do")
        sys.exit(0)

    backup(TARGET)
    original_len = len(content)

    # --- Edit 1: tile-row container ---
    # Add align-items:flex-start so tall tiles don't force short tiles to stretch.
    OLD_ROW = "var out='<div style=\"display:flex;gap:12px;margin-bottom:12px\">';"
    NEW_ROW = (
        "/* " + MARKER + " */"
        "var out='<div style=\"display:flex;gap:12px;margin-bottom:12px;align-items:flex-start\">';"
    )
    content = replace_once(content, OLD_ROW, NEW_ROW, "Edit 1 (tile-row align)")

    # --- Edit 2: tile box itself — cap max-height; flex column with header + scrolling body ---
    OLD_TILE_OPEN = "out+='<div style=\"flex:1;min-width:0;background:var(--bg-secondary);border:2px solid '+borderCol+';border-radius:8px;padding:10px 12px;display:flex;flex-direction:column\">';"
    NEW_TILE_OPEN = (
        "out+='<div style=\"flex:1;min-width:0;max-height:560px;background:var(--bg-secondary);border:2px solid '+borderCol+';border-radius:8px;padding:10px 12px;display:flex;flex-direction:column;overflow:hidden\">';"
    )
    content = replace_once(content, OLD_TILE_OPEN, NEW_TILE_OPEN, "Edit 2 (tile max-height cap)")

    # --- Edit 3: the body grid — make it the internal scrollport ---
    # The body grid is the second grid container — the one for data rows (not the column headers).
    # Verbatim from Patcher B:
    OLD_BODY_GRID = (
        "out+='<div style=\"display:grid;grid-template-columns:1fr 44px 44px;gap:3px 6px;align-items:center;padding-top:4px\">';"
    )
    NEW_BODY_GRID = (
        "out+='<div style=\"display:grid;grid-template-columns:1fr 44px 44px;gap:3px 6px;align-items:center;padding-top:4px;overflow-y:auto;flex:1;min-height:0\">';"
    )
    content = replace_once(content, OLD_BODY_GRID, NEW_BODY_GRID, "Edit 3 (body grid scrollport)")

    # --- Edit 4: cap empty-state tile so it doesn't unnaturally stretch ---
    # When rows.length===0 we currently emit a placeholder. Already minimal — just ensure
    # the tile shows the placeholder centred vertically by making the tile a flex column.
    # (No code change needed beyond Edit 2's display:flex on tile box.)

    TARGET.write_text(content, encoding="utf-8")
    new_len = len(content)
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
