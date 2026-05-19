"""
Patcher A-fixup — Two corrections to patch_dashboard_minor (11-May-26)
=====================================================================

Two surgical fixes:

  FIX 1: Bootstrap render of default tab.
    MM99 used to be the default, and its full content was injected
    INTO the HTML at build time by the Python builder (~8.6 MB of
    pre-rendered HTML in tab-mm99). Every other tab renders lazily
    on first switchTab() click via renderTab(id).
    When default flipped to "changes", the page now boots with an
    empty #tab-changes container because nothing called renderTab
    for it. Fix: add window.switchTab(currentTab) call right after
    the IIFE installs window.switchTab, so the page bootstraps the
    new default lazily.

  FIX 2: Active-tab CSS specificity.
    Tab buttons carry an INLINE style="...;background:rgba(...,0.1);
    border-color:rgba(...,0.3)" from the Python builder. Inline styles
    beat class rules, so .tab-btn.tab-active { background: var(...) }
    loses the cascade. Fix: add !important to background and
    border-color in the active rule so the accent fills properly.

Idempotent via FIX-1-MARKER and FIX-2-MARKER comments. Pre-write
backup.

Usage:
  cd C:\\Users\\richb\\Documents\\COWORK\\master-dashboard
  python scripts\\patch_dashboard_minor_fixup_2026_05_11.py
  python scripts\\build_dashboard.py
"""

import sys
import shutil
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
TARGET = PROJECT_DIR / "scripts" / "build_dashboard.py"

FIX1_MARKER = "BOOTSTRAP-DEFAULT-TAB-FIX-1"
FIX2_MARKER = "ACTIVE-TAB-SPECIFICITY-FIX-2"


def backup(p):
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = p.with_suffix(p.suffix + f".bak-pre-minor-fixup-{ts}")
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

    if FIX1_MARKER in content and FIX2_MARKER in content:
        print("  both fixup markers present; nothing to do")
        sys.exit(0)

    backup(TARGET)
    original_len = len(content)

    # ---- FIX 1: bootstrap default-tab render ----
    # We anchor on the existing line: `window.switchTab=function(id){`
    # and inject a self-invoking bootstrap call right after the function
    # definition closes. The function spans many lines, so we anchor
    # on its definition opener and the matching `};` close pattern.
    #
    # Safer: add a window.addEventListener("DOMContentLoaded", ...) block
    # after the function definition. To find a uniqueness anchor, we'll
    # use the well-defined currentTab declaration we just changed.
    if FIX1_MARKER not in content:
        anchor = 'var currentTab="changes",currentSort={col:"chg_score",dir:"desc"};'
        if anchor not in content:
            print("  [FIX 1] currentTab anchor not found — Patcher A may not have run")
            sys.exit(1)
        # Inject a one-shot bootstrap call. Wrap in setTimeout to ensure
        # the IIFE has finished installing window.switchTab and data is loaded.
        # Use a load-state guard so we only fire once.
        bootstrap = anchor + (
            '\\n'
            '/* ' + FIX1_MARKER + ' */\\n'
            'if(typeof window!=="undefined"){'
            'window.__chgBootstrapDone=window.__chgBootstrapDone||false;'
            'var __chgBoot=function(){'
            'if(window.__chgBootstrapDone)return;'
            'if(typeof window.switchTab!=="function"){setTimeout(__chgBoot,30);return;}'
            'window.__chgBootstrapDone=true;'
            'try{window.switchTab(currentTab);}catch(e){console.error("bootstrap switchTab failed",e);}'
            '};'
            'if(document.readyState==="loading"){document.addEventListener("DOMContentLoaded",__chgBoot);}'
            'else{setTimeout(__chgBoot,30);}'
            '}'
        )
        # The injected code lives inside the JS string; need to write
        # the real newlines, not the literal backslash-n the heredoc
        # produces. Replace the visible '\\n' tokens with real newlines.
        bootstrap = bootstrap.replace('\\n', '\n')
        content = replace_once(content, anchor, bootstrap, "FIX 1 (bootstrap default-tab render)")

    # ---- FIX 2: active-tab CSS specificity (inline-style override) ----
    # Current rule (from Patcher A) — exact verbatim:
    OLD_RULE = (
        ".tab-btn.tab-active{"
        "background:var(--tab-accent,#1b3d5c);"
        "color:#fff;font-weight:700;"
        "border:1px solid var(--tab-accent,#1b3d5c);"
        "border-left:5px solid var(--tab-accent,#1b3d5c);"
        "box-shadow:0 2px 6px rgba(0,0,0,0.18),inset 0 -2px 0 rgba(255,255,255,0.25);"
        "transform:translateY(-1px);"
        "letter-spacing:.3px;"
        "padding:5px 12px;"
        "position:relative;z-index:2}"
        ".tab-btn.tab-active:hover{background:var(--tab-accent,#1b3d5c);color:#fff;border-color:var(--tab-accent,#1b3d5c)}"
    )
    NEW_RULE = (
        "/* " + FIX2_MARKER + " */"
        ".tab-btn.tab-active{"
        "background:var(--tab-accent,#1b3d5c) !important;"
        "color:#fff !important;font-weight:700;"
        "border:1px solid var(--tab-accent,#1b3d5c) !important;"
        "border-left:5px solid var(--tab-accent,#1b3d5c) !important;"
        "box-shadow:0 2px 6px rgba(0,0,0,0.18),inset 0 -2px 0 rgba(255,255,255,0.25);"
        "transform:translateY(-1px);"
        "letter-spacing:.3px;"
        "padding:5px 12px;"
        "position:relative;z-index:2}"
        ".tab-btn.tab-active:hover{background:var(--tab-accent,#1b3d5c) !important;color:#fff !important;border-color:var(--tab-accent,#1b3d5c) !important}"
    )
    if FIX2_MARKER not in content:
        content = replace_once(content, OLD_RULE, NEW_RULE, "FIX 2 (active-tab specificity)")

    TARGET.write_text(content, encoding="utf-8")
    new_len = len(content)
    delta = new_len - original_len
    print(f"  wrote {new_len:,} bytes (delta {delta:+,})")

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
