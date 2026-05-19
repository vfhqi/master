"""
Patcher E-fixup — Tab header layout fix (11-May-26)
==================================================

Problem: 4 stage groups in the #1 TABS row stacked vertically instead
of flowing horizontally. Each .tab-stage-group is a flex-column block
that broke the natural inline-flex behaviour of the .tab-nav parent.

Root causes:
  1. Outer wrapper around stage groups lacks display:inline-flex —
     so under .tab-nav's overflow-x:auto each child .tab-stage-group
     claims a full row.
  2. The STAGE banner label was a separate column row inside each
     group, doubling header height.

Fix:
  - Wrap the whole filter-tabs region in a single inline-flex row
    wrapper so stage groups sit side-by-side.
  - Compact the STAGE banner to a tiny strip ABOVE the buttons,
    visually a label, not a row.

Surgical replacement of the tab_buttons builder block.
Idempotent via marker STAGE-HEADER-FIXUP.

Usage:
  cd C:\\Users\\richb\\Documents\\COWORK\\master-dashboard
  python scripts\\patch_stage_header_fixup_2026_05_11.py
  python scripts\\build_dashboard.py
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
TARGET = PROJECT_DIR / "scripts" / "build_dashboard.py"

MARKER = "STAGE-HEADER-FIXUP"

# The current (broken) NEW_BUILDER block from Patcher E.
OLD_BUILDER = '''    # STAGE-REFACTOR-V3-MARKER — 4 stage banners + 1 reference banner
    STAGE_INFO = {
        1: {"label": "STAGE 1", "color": "rgba(39,103,73,0.35)"},   # green — basing/bottoming
        2: {"label": "STAGE 2", "color": "rgba(27,61,92,0.35)"},    # navy — markup/breakout
        3: {"label": "STAGE 3", "color": "rgba(180,83,9,0.35)"},    # amber — topping
        4: {"label": "STAGE 4", "color": "rgba(153,27,27,0.35)"},   # red — decline
    }
    tab_buttons = ""
    current_stage = None
    in_filter_section = True
    for t in TABS:
        stage = t.get("stage")
        is_filter_tab = stage is not None
        if is_filter_tab:
            # Open a new stage group when stage changes
            if stage != current_stage:
                if current_stage is not None:
                    tab_buttons += '</div>'  # close previous group
                si = STAGE_INFO[stage]
                tab_buttons += (
                    '<div class="tab-stage-group" style="display:inline-flex;flex-direction:column;'
                    'border:1.5px solid ' + si["color"] + ';border-radius:6px;padding:1px 4px 2px;margin-right:6px">'
                    '<div style="font-size:8px;font-weight:700;color:#6b6b6b;letter-spacing:.5px;'
                    'text-align:center;padding:0 2px 1px">' + si["label"] + '</div>'
                    '<div style="display:inline-flex;gap:2px">'
                )
                current_stage = stage
        else:
            # Closing the filter section, switching to reference tabs
            if in_filter_section:
                if current_stage is not None:
                    tab_buttons += '</div></div>'  # close inner + outer of last stage group
                # Open the reference-tabs group
                tab_buttons += (
                    '<div class="tab-group" style="border:1.5px solid rgba(120,80,200,0.25);'
                    'border-radius:6px;padding:2px 4px;display:inline-flex;gap:2px;margin-left:6px">'
                )
                in_filter_section = False
        active = ' tab-active' if t["id"] == "changes" else ''
        emphasis = ' tab-emphasis' if t["id"] == "combos" else ''
        bg_tint = hex_to_rgba(t["accent"], 0.1)
        border_tint = hex_to_rgba(t["accent"], 0.3)
        is_placeholder = t.get("placeholder", False)
        ph_class = ' tab-placeholder' if is_placeholder else ''
        ph_style = ';opacity:0.45;cursor:default' if is_placeholder else ''
        onclick = '' if is_placeholder else 'onclick="switchTab(\\'' + t["id"] + '\\')"'
        tab_buttons += (
            '<button class="tab-btn' + active + emphasis + ph_class + '" data-tab="' + t["id"] + '" '
            'style="--tab-accent:' + t["accent"] + ';background:' + bg_tint + ';border-color:' + border_tint + ph_style + '" '
            + onclick + '>' + t["label"] + '</button>'
        )
    # Close the final open container (reference group)
    tab_buttons += '</div>'
'''

NEW_BUILDER = '''    # ''' + MARKER + ''' — single-row inline-flex parent containing stage groups + reference group
    STAGE_INFO = {
        1: {"label": "STAGE 1", "color": "rgba(39,103,73,0.55)"},
        2: {"label": "STAGE 2", "color": "rgba(27,61,92,0.55)"},
        3: {"label": "STAGE 3", "color": "rgba(180,83,9,0.55)"},
        4: {"label": "STAGE 4", "color": "rgba(153,27,27,0.55)"},
    }
    # Outer wrapper guarantees horizontal flow regardless of .tab-nav rules
    tab_buttons = '<div style="display:inline-flex;align-items:flex-end;gap:6px;flex-wrap:nowrap">'
    current_stage = None
    in_filter_section = True
    for t in TABS:
        stage = t.get("stage")
        is_filter_tab = stage is not None
        if is_filter_tab:
            if stage != current_stage:
                if current_stage is not None:
                    tab_buttons += '</div></div>'  # close prior group inner+outer
                si = STAGE_INFO[stage]
                # Stage group: inline-flex column. STAGE label is a 9px strip above
                # the tab buttons row. Compact — adds ~10px height not 20.
                tab_buttons += (
                    '<div class="tab-stage-group" style="display:inline-flex;flex-direction:column;'
                    'border:1.5px solid ' + si["color"] + ';border-radius:5px;padding:0 3px 2px;background:rgba(255,255,255,0.4)">'
                    '<div style="font-size:8px;font-weight:700;color:#4a4a4a;letter-spacing:.6px;'
                    'text-align:center;padding:1px 2px 1px;line-height:1.1">' + si["label"] + '</div>'
                    '<div style="display:inline-flex;gap:2px">'
                )
                current_stage = stage
        else:
            if in_filter_section:
                if current_stage is not None:
                    tab_buttons += '</div></div>'  # close last stage group
                # Reference-tabs group — wrapped so it sits inline with the stage groups
                tab_buttons += (
                    '<div class="tab-group" style="display:inline-flex;align-items:flex-end;'
                    'border:1.5px solid rgba(120,80,200,0.4);border-radius:5px;padding:0 4px 2px;'
                    'gap:2px;margin-left:4px;align-self:flex-end">'
                )
                in_filter_section = False
        active = ' tab-active' if t["id"] == "changes" else ''
        emphasis = ' tab-emphasis' if t["id"] == "combos" else ''
        bg_tint = hex_to_rgba(t["accent"], 0.1)
        border_tint = hex_to_rgba(t["accent"], 0.3)
        is_placeholder = t.get("placeholder", False)
        ph_class = ' tab-placeholder' if is_placeholder else ''
        ph_style = ';opacity:0.45;cursor:default' if is_placeholder else ''
        onclick = '' if is_placeholder else 'onclick="switchTab(\\'' + t["id"] + '\\')"'
        tab_buttons += (
            '<button class="tab-btn' + active + emphasis + ph_class + '" data-tab="' + t["id"] + '" '
            'style="--tab-accent:' + t["accent"] + ';background:' + bg_tint + ';border-color:' + border_tint + ph_style + '" '
            + onclick + '>' + t["label"] + '</button>'
        )
    # Close the final open container (reference group)
    tab_buttons += '</div></div>'  # close reference group + outer wrapper
'''


def main():
    print(f"Patching: {TARGET}")
    if not TARGET.exists():
        print("  ERROR: target not found")
        sys.exit(1)

    content = TARGET.read_text(encoding="utf-8")
    if MARKER in content:
        print(f"  marker present; nothing to do")
        sys.exit(0)

    n = content.count(OLD_BUILDER)
    if n == 0:
        print("  ERROR: tab-builder anchor not found (Patcher E may not have run, or fixup ran already)")
        sys.exit(1)
    if n > 1:
        print(f"  ERROR: anchor matches {n} times (must be unique)")
        sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = TARGET.with_suffix(TARGET.suffix + f".bak-pre-stage-header-fixup-{ts}")
    shutil.copy2(TARGET, bak)
    print(f"  backup -> {bak.name}")

    original_len = len(content)
    content = content.replace(OLD_BUILDER, NEW_BUILDER, 1)
    TARGET.write_text(content, encoding="utf-8")
    print(f"  wrote {len(content):,} bytes (delta {len(content) - original_len:+,})")

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
