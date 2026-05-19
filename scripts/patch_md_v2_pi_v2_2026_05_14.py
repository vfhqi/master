#!/usr/bin/env python3
# =============================================================================
# patch_md_v2_pi_v2_2026_05_14.py
# -----------------------------------------------------------------------------
# Session 25 (14-May-26) Master Dashboard V2 patcher. Locked decisions
# D-MD-V2-46 through D-MD-V2-58. Edits build_dashboard.py only.
#
#   EDIT 1 (Block A, D-MD-V2-47) - header chrome shrink on V2 tabs.
#   EDIT 2 (Block B, D-MD-V2-48 + D-MD-V2-46) - rewrite ensureV2Nav() with
#          tier grouping + terminology rename.
#   EDIT 3 (Block B CSS) - nav-grouping CSS (group labels, separators, tones).
#   EDIT 4 (Blocks C-I) - replace the Pre-test indicators CSS block.
#   EDIT 5 (Blocks C-I) - replace the Pre-test indicators JS module block.
#
# Payload files (must sit alongside this patcher in scripts/):
#   _pi_v2_module.js   - the new Pre-test indicators JS module
#   _pi_v2_css.txt     - the new Pre-test indicators CSS block
#
# Discipline (D-MD-V2-43): patcher authored via heredoc -> /tmp -> atomic cp
#   -> MD5 byte-verify. Patcher itself: idempotent, anchor-string replace,
#   pre-write backup, atomic write at END, post-write verification.
#   Edit tool BANNED on build_dashboard.py (>20KB FUSE) - this patcher IS the
#   only sanctioned mutation path.
# =============================================================================
import sys, os, shutil, py_compile, tempfile
from datetime import datetime

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(SCRIPTS_DIR, "build_dashboard.py")
PI_MODULE_PAYLOAD = os.path.join(SCRIPTS_DIR, "_pi_v2_module.js")
PI_CSS_PAYLOAD = os.path.join(SCRIPTS_DIR, "_pi_v2_css.txt")
MARKER = "MD-V2-PI-V2-S25-MARKER"

def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def main():
    for pth in (TARGET, PI_MODULE_PAYLOAD, PI_CSS_PAYLOAD):
        if not os.path.exists(pth):
            print("ERROR: required file not found: %s" % pth); sys.exit(1)

    src = read(TARGET)
    pi_module = read(PI_MODULE_PAYLOAD).rstrip("\n")
    pi_css = read(PI_CSS_PAYLOAD).rstrip("\n")

    if MARKER in src:
        print("IDEMPOTENT: %s already present. No-op." % MARKER)
        sys.exit(0)

    orig_len = len(src)

    # -------------------------------------------------------------------------
    # EDIT 1 - Block A: header chrome shrink on V2 tabs (D-MD-V2-47).
    # Anchor on the existing chrome-parity .header-controls-row suppression
    # block, append the V2-tab header-shrink rules right after it.
    # -------------------------------------------------------------------------
    anchor1 = (
        "body[data-active-tab^=\"stage_\"] .header-controls-row,\n"
        "body[data-active-tab=\"pre_indicators\"] .header-controls-row,\n"
        "body[data-active-tab=\"post_indicators\"] .header-controls-row,\n"
        "body[data-active-tab=\"setups\"] .header-controls-row,\n"
        "body[data-active-tab=\"tests\"] .header-controls-row,\n"
        "body[data-active-tab=\"master_overview\"] .header-controls-row { display: none !important; }\n"
    )
    edit1_block = (
        anchor1 +
        "/* " + MARKER + ": EDIT 1 - Block A header chrome shrink on V2 tabs (D-MD-V2-47).\n"
        "   Legacy header is sized for 3 rows; V2 tabs show only header-top + v2-nav.\n"
        "   Shrink the fixed header + override --header-height so the table does not\n"
        "   float up under it, and tighten the v2-nav padding. CSS-only, no HTML change. */\n"
        "body[data-active-tab^=\"stage_\"] .header,\n"
        "body[data-active-tab=\"pre_indicators\"] .header,\n"
        "body[data-active-tab=\"post_indicators\"] .header,\n"
        "body[data-active-tab=\"setups\"] .header,\n"
        "body[data-active-tab=\"tests\"] .header,\n"
        "body[data-active-tab=\"master_overview\"] .header { padding-bottom: 0 !important; }\n"
        "body[data-active-tab^=\"stage_\"],\n"
        "body[data-active-tab=\"pre_indicators\"],\n"
        "body[data-active-tab=\"post_indicators\"],\n"
        "body[data-active-tab=\"setups\"],\n"
        "body[data-active-tab=\"tests\"],\n"
        "body[data-active-tab=\"master_overview\"] { --header-height: 70px; }\n"
        "body[data-active-tab^=\"stage_\"] .v2-nav,\n"
        "body[data-active-tab=\"pre_indicators\"] .v2-nav,\n"
        "body[data-active-tab=\"post_indicators\"] .v2-nav,\n"
        "body[data-active-tab=\"setups\"] .v2-nav,\n"
        "body[data-active-tab=\"tests\"] .v2-nav,\n"
        "body[data-active-tab=\"master_overview\"] .v2-nav { padding-top: 4px !important; padding-bottom: 4px !important; }\n"
    )
    if anchor1 not in src:
        print("ERROR: EDIT 1 anchor not found (chrome-parity header-controls-row block)."); sys.exit(1)
    src = src.replace(anchor1, edit1_block, 1)

    # -------------------------------------------------------------------------
    # EDIT 2 - Block B: rewrite ensureV2Nav() with tier grouping + terminology
    # (D-MD-V2-48 + D-MD-V2-46). Replace the whole innerHTML assignment.
    # -------------------------------------------------------------------------
    anchor2 = (
        "    nav.innerHTML = ''\n"
        "      + '<span class=\"v2-nav-label\">MD V2</span>'\n"
        "      + '<button class=\"v2-nav-btn\" data-v2-tab=\"stage_1\" onclick=\"switchTab(\\'stage_1\\')\">Stage 1 (Basing)</button>'\n"
        "      + '<button class=\"v2-nav-btn\" data-v2-tab=\"stage_2\" onclick=\"switchTab(\\'stage_2\\')\">Stage 2 (Uptrend)</button>'\n"
        "      + '<button class=\"v2-nav-btn\" data-v2-tab=\"stage_3\" onclick=\"switchTab(\\'stage_3\\')\">Stage 3 (Topping)</button>'\n"
        "      + '<button class=\"v2-nav-btn\" data-v2-tab=\"stage_4\" onclick=\"switchTab(\\'stage_4\\')\">Stage 4 (Decline)</button>'\n"
        "      + '<button class=\"v2-nav-btn\" data-v2-tab=\"pre_indicators\" onclick=\"switchTab(\\'pre_indicators\\')\">Pre-indicators</button>'\n"
        "      + '<button class=\"v2-nav-btn\" data-v2-tab=\"post_indicators\" onclick=\"switchTab(\\'post_indicators\\')\">Post-indicators</button>'\n"
        "      + '<button class=\"v2-nav-btn\" data-v2-tab=\"setups\" onclick=\"switchTab(\\'setups\\')\">Setups</button>'\n"
        "      + '<button class=\"v2-nav-btn\" data-v2-tab=\"tests\" onclick=\"switchTab(\\'tests\\')\">Tests</button>'\n"
        "      + '<span class=\"v2-nav-placeholder\" title=\"Coming soon\">Master Overview</span>';\n"
    )
    edit2_block = (
        "    // " + MARKER + ": EDIT 2 - Block B nav tier grouping + terminology\n"
        "    // (D-MD-V2-48 + D-MD-V2-46). Group labels + separators between tiers;\n"
        "    // internal tab keys unchanged (display-only rename).\n"
        "    nav.innerHTML = ''\n"
        "      + '<span class=\"v2-nav-label\">MD V2</span>'\n"
        "      + '<span class=\"v2-nav-grp-label\">Stages</span>'\n"
        "      + '<button class=\"v2-nav-btn v2-grp-stages\" data-v2-tab=\"stage_1\" onclick=\"switchTab(\\'stage_1\\')\">Stage 1 (Basing)</button>'\n"
        "      + '<button class=\"v2-nav-btn v2-grp-stages\" data-v2-tab=\"stage_2\" onclick=\"switchTab(\\'stage_2\\')\">Stage 2 (Uptrend)</button>'\n"
        "      + '<button class=\"v2-nav-btn v2-grp-stages\" data-v2-tab=\"stage_3\" onclick=\"switchTab(\\'stage_3\\')\">Stage 3 (Topping)</button>'\n"
        "      + '<button class=\"v2-nav-btn v2-grp-stages\" data-v2-tab=\"stage_4\" onclick=\"switchTab(\\'stage_4\\')\">Stage 4 (Decline)</button>'\n"
        "      + '<span class=\"v2-nav-sep\"></span>'\n"
        "      + '<span class=\"v2-nav-grp-label\">Indicators</span>'\n"
        "      + '<button class=\"v2-nav-btn v2-grp-indicators\" data-v2-tab=\"pre_indicators\" onclick=\"switchTab(\\'pre_indicators\\')\">Pre-test indicators</button>'\n"
        "      + '<button class=\"v2-nav-btn v2-grp-indicators\" data-v2-tab=\"post_indicators\" onclick=\"switchTab(\\'post_indicators\\')\">Post-test indicators</button>'\n"
        "      + '<span class=\"v2-nav-sep\"></span>'\n"
        "      + '<span class=\"v2-nav-grp-label\">Capital qualification</span>'\n"
        "      + '<button class=\"v2-nav-btn v2-grp-setups\" data-v2-tab=\"setups\" onclick=\"switchTab(\\'setups\\')\">Capital qualification setups</button>'\n"
        "      + '<span class=\"v2-nav-sep\"></span>'\n"
        "      + '<span class=\"v2-nav-grp-label\">Capital deployment</span>'\n"
        "      + '<button class=\"v2-nav-btn v2-grp-tests\" data-v2-tab=\"tests\" onclick=\"switchTab(\\'tests\\')\">Capital deployment tests</button>'\n"
        "      + '<span class=\"v2-nav-sep\"></span>'\n"
        "      + '<span class=\"v2-nav-placeholder\" title=\"Coming soon\">Master Overview</span>';\n"
    )
    if anchor2 not in src:
        print("ERROR: EDIT 2 anchor not found (ensureV2Nav innerHTML block)."); sys.exit(1)
    src = src.replace(anchor2, edit2_block, 1)

    # -------------------------------------------------------------------------
    # EDIT 3 - Block B CSS: nav-grouping styles. Anchor on the existing
    # .v2-nav-placeholder CSS rule, append the new grouping rules after it.
    # -------------------------------------------------------------------------
    anchor3 = ".v2-nav-placeholder { display: inline-block; padding: 5px 11px; font-size: 11px; color: #aaa; background: #f0ece0; border: 1px dashed #d0ccb8; border-radius: 4px; cursor: default; }\n"
    edit3_block = (
        anchor3 +
        "/* " + MARKER + ": EDIT 3 - Block B nav tier-grouping CSS (D-MD-V2-48). */\n"
        ".v2-nav-grp-label { font-size: 9px; color: #8a8674; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 700; margin: 0 4px 0 0; }\n"
        ".v2-nav-sep { display: inline-block; width: 1px; height: 18px; background: #d8d4c2; margin: 0 8px; }\n"
        ".v2-nav-btn.v2-grp-stages { border-bottom: 2px solid rgba(27,61,92,0.30); }\n"
        ".v2-nav-btn.v2-grp-indicators { border-bottom: 2px solid rgba(15,110,86,0.45); }\n"
        ".v2-nav-btn.v2-grp-setups { border-bottom: 2px solid rgba(123,104,174,0.55); }\n"
        ".v2-nav-btn.v2-grp-tests { border-bottom: 2px solid rgba(180,83,9,0.55); }\n"
        ".v2-nav-btn.v2-grp-indicators:hover { background: #e8f2ee; }\n"
        ".v2-nav-btn.v2-grp-setups:hover { background: #efecf6; }\n"
        ".v2-nav-btn.v2-grp-tests:hover { background: #f6efe6; }\n"
    )
    if anchor3 not in src:
        print("ERROR: EDIT 3 anchor not found (.v2-nav-placeholder CSS rule)."); sys.exit(1)
    src = src.replace(anchor3, edit3_block, 1)

    # -------------------------------------------------------------------------
    # EDIT 4 - replace the Pre-test indicators CSS block (marker-delimited).
    # -------------------------------------------------------------------------
    css_start = "/* MD-V2-PRE-INDICATORS-MARKER-CSS-START */"
    css_end = "/* MD-V2-PRE-INDICATORS-MARKER-CSS-END */"
    i0 = src.find(css_start)
    i1 = src.find(css_end)
    if i0 == -1 or i1 == -1 or i1 < i0:
        print("ERROR: EDIT 4 - PI CSS marker block not found or malformed."); sys.exit(1)
    i1_end = i1 + len(css_end)
    src = src[:i0] + pi_css + src[i1_end:]

    # -------------------------------------------------------------------------
    # EDIT 5 - replace the Pre-test indicators JS module block (marker-delimited).
    # The module sits between MODULE-START and MODULE-END; the payload itself
    # carries the inner START/END markers, so we keep the MODULE-* wrappers.
    # -------------------------------------------------------------------------
    mod_start = "/* MD-V2-PRE-INDICATORS-MARKER-MODULE-START */"
    mod_end = "/* MD-V2-PRE-INDICATORS-MARKER-MODULE-END */"
    j0 = src.find(mod_start)
    j1 = src.find(mod_end)
    if j0 == -1 or j1 == -1 or j1 < j0:
        print("ERROR: EDIT 5 - PI module marker block not found or malformed."); sys.exit(1)
    j1_end = j1 + len(mod_end)
    new_module_block = mod_start + "\n" + pi_module + "\n" + mod_end
    src = src[:j0] + new_module_block + src[j1_end:]

    # -------------------------------------------------------------------------
    # Plant the patcher marker (idempotency) - inside a comment near EDIT 1.
    # Already planted via the EDIT comment lines (MARKER appears in EDIT 1-5
    # comments), so the `if MARKER in src` check at top will catch re-runs.
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # Validate in /tmp, pre-write backup, atomic write, post-write verify.
    # -------------------------------------------------------------------------
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".py", prefix="bd_patch_")
    os.close(tmp_fd)
    with open(tmp_path, "w", encoding="utf-8") as f:
        f.write(src)

    try:
        py_compile.compile(tmp_path, doraise=True)
    except py_compile.PyCompileError as e:
        print("ERROR: patched build_dashboard.py fails py_compile:\n%s" % e)
        os.unlink(tmp_path)
        sys.exit(1)

    if b"\x00" in src.encode("utf-8"):
        print("ERROR: null bytes detected in patched source - aborting.")
        os.unlink(tmp_path)
        sys.exit(1)

    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = TARGET + ".bak-pre-md-v2-pi-v2-s25-" + ts
    shutil.copy2(TARGET, backup)
    print("Pre-write backup: %s" % backup)

    shutil.copy2(tmp_path, TARGET)
    os.unlink(tmp_path)

    new_len = len(src)
    print("OK: build_dashboard.py patched.")
    print("    %d bytes -> %d bytes (delta %+d)" % (orig_len, new_len, new_len - orig_len))
    print("    marker: %s" % MARKER)

    # post-write verification
    check = read(TARGET)
    if MARKER not in check:
        print("ERROR: post-write verification failed - marker missing!"); sys.exit(1)
    checks = [
        ("EDIT 1 header shrink", "--header-height: 70px"),
        ("EDIT 2 nav terminology", "Capital qualification setups"),
        ("EDIT 2 nav terminology", "Pre-test indicators"),
        ("EDIT 3 nav grouping CSS", "v2-nav-grp-label"),
        ("EDIT 4 PI CSS rebuild", "rt-breakdown"),
        ("EDIT 4 PI CSS rebuild", "sg-positive"),
        ("EDIT 5 PI module rebuild", "pulling_back_uptrend"),
        ("EDIT 5 PI module rebuild", "renderPreIndicators"),
    ]
    for name, token in checks:
        if token not in check:
            print("ERROR: post-write verification - %s missing token '%s'" % (name, token)); sys.exit(1)
    # marker-block integrity
    for m in ("MD-V2-PRE-INDICATORS-MARKER-CSS-START", "MD-V2-PRE-INDICATORS-MARKER-CSS-END",
              "MD-V2-PRE-INDICATORS-MARKER-MODULE-START", "MD-V2-PRE-INDICATORS-MARKER-MODULE-END",
              "MD-V2-PRE-INDICATORS-MARKER-START", "MD-V2-PRE-INDICATORS-MARKER-END"):
        if check.count(m) != 1:
            print("ERROR: post-write verification - marker '%s' count = %d (expected 1)" % (m, check.count(m))); sys.exit(1)
    if not check.rstrip().endswith("</html>'"):
        # build_dashboard.py is a python script that ENDS with the main() guard,
        # not </html> - this check is just a guard against accidental truncation.
        tail = check.rstrip()[-40:]
        if "__main__" not in check[-200:]:
            print("WARNING: build_dashboard.py tail unexpected: ...%s" % tail)
    print("Post-write verification: PASS (marker + all 5 edits + 6 marker-blocks intact).")

if __name__ == "__main__":
    main()
