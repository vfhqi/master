#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# patch_md_v2_s38_sections_overview_2026_05_16.py
# =============================================================================
# MD V2 Master Dashboard - Session 38 (16-May-26)
#
# Two asks, one patcher:
#
# 1. Overview supergroup visual grouping made COMPREHENSIVE - left AND right
#    borders on every supergroup column block, applied to BOTH the top
#    summary table and the matrix below. Softer 2px borders with reduced-alpha
#    section colours. Very subtle background tint on each supergroup header
#    cell, towards its text colour. (Richard: continue the colouring more
#    comprehensively, include Capital Deployment Tests, pick slightly more
#    subtle colours, very slightly colour the supergroup headers towards the
#    colour of the text. Logic: visually distinguish the supergroups a little
#    more.)
#
# 2. Two remaining user-visible "Master Overview" strings renamed to
#    "Overview" - the v2-nav button label (the active tab button on the right
#    of the nav row), and the Overview tab's page-intro first sentence.
#    Internal code comments containing "Master Overview" are left as-is - not
#    user-visible. (Richard: I still see MASTER OVERVIEW in top right.
#    Change universally please.)
#
# Same house style (FUSE-immune source via `git show HEAD:`, idempotent on
# MARKER, working-tree-vs-HEAD safety gate, exact anchor count assertions,
# py_compile pre-write, pre-write backup).
#
# Usage:
#   python scripts/patch_md_v2_s38_sections_overview_2026_05_16.py
#   python scripts/patch_md_v2_s38_sections_overview_2026_05_16.py --test SRC OUT
# =============================================================================
import sys, os, subprocess, hashlib, py_compile, datetime

MARKER = "MD-V2-S38-SECTIONS-OVERVIEW-MARKER"
TARGET = os.path.join("scripts", "build_dashboard.py")


# ---------- Edit 1: replace the S36 CSS block with the comprehensive version ----------
CSS_OLD = (
    "/* MD-V2-S36-BRIEF-MARKER: Overview matrix visual supergroup grouping - a coloured\n"
    "   left border on the first body cell of each section bands the section all the\n"
    "   way down through the matrix, matching the thead group-band colours. */\n"
    "#mo-matrix-table tbody td.mo-sec-start-stages   { border-left: 3px solid #1b5e20; }\n"
    "#mo-matrix-table tbody td.mo-sec-start-pretest  { border-left: 3px solid #0F6E56; }\n"
    "#mo-matrix-table tbody td.mo-sec-start-posttest { border-left: 3px solid #A32D2D; }\n"
    "#mo-matrix-table tbody td.mo-sec-start-setups   { border-left: 3px solid #BA7517; }\n"
    "#mo-matrix-table tbody td.mo-sec-start-tests    { border-left: 3px solid #185FA5; }\n"
    "#mo-main-table   tbody td.mo-sec-start-stages   { border-left: 3px solid #1b5e20; }\n"
    "#mo-main-table   tbody td.mo-sec-start-pretest  { border-left: 3px solid #0F6E56; }\n"
    "#mo-main-table   tbody td.mo-sec-start-posttest { border-left: 3px solid #A32D2D; }\n"
    "#mo-main-table   tbody td.mo-sec-start-setups   { border-left: 3px solid #BA7517; }\n"
    "#mo-main-table   tbody td.mo-sec-start-tests    { border-left: 3px solid #185FA5; }"
)
CSS_NEW = (
    "/* MD-V2-S38-SECTIONS-OVERVIEW-MARKER: comprehensive Overview supergroup grouping.\n"
    "   Each supergroup column block gets BOTH a left border on its first cell and a\n"
    "   right border on its last cell, on BOTH tables (summary + matrix). 2px wide,\n"
    "   ~45% alpha so the bracketing reads as a guide rather than a hard line.\n"
    "   The supergroup header cells also get a very subtle (~7% alpha) background\n"
    "   tint towards their text colour, so the supergroup is visible even where the\n"
    "   body cells happen to all be the same tier-tint. */\n"
    "/* body-cell left borders (first column of each section) */\n"
    "#mo-matrix-table tbody td.mo-sec-start-stages,   #mo-main-table tbody td.mo-sec-start-stages   { border-left: 2px solid rgba(27,94,32,0.45); }\n"
    "#mo-matrix-table tbody td.mo-sec-start-pretest,  #mo-main-table tbody td.mo-sec-start-pretest  { border-left: 2px solid rgba(15,110,86,0.45); }\n"
    "#mo-matrix-table tbody td.mo-sec-start-posttest, #mo-main-table tbody td.mo-sec-start-posttest { border-left: 2px solid rgba(163,45,45,0.45); }\n"
    "#mo-matrix-table tbody td.mo-sec-start-setups,   #mo-main-table tbody td.mo-sec-start-setups   { border-left: 2px solid rgba(186,117,23,0.45); }\n"
    "#mo-matrix-table tbody td.mo-sec-start-tests,    #mo-main-table tbody td.mo-sec-start-tests    { border-left: 2px solid rgba(24,95,165,0.45); }\n"
    "/* body-cell right borders (last column of each section) */\n"
    "#mo-matrix-table tbody td.mo-sec-end-stages,   #mo-main-table tbody td.mo-sec-end-stages   { border-right: 2px solid rgba(27,94,32,0.45); }\n"
    "#mo-matrix-table tbody td.mo-sec-end-pretest,  #mo-main-table tbody td.mo-sec-end-pretest  { border-right: 2px solid rgba(15,110,86,0.45); }\n"
    "#mo-matrix-table tbody td.mo-sec-end-posttest, #mo-main-table tbody td.mo-sec-end-posttest { border-right: 2px solid rgba(163,45,45,0.45); }\n"
    "#mo-matrix-table tbody td.mo-sec-end-setups,   #mo-main-table tbody td.mo-sec-end-setups   { border-right: 2px solid rgba(186,117,23,0.45); }\n"
    "#mo-matrix-table tbody td.mo-sec-end-tests,    #mo-main-table tbody td.mo-sec-end-tests    { border-right: 2px solid rgba(24,95,165,0.45); }\n"
    "/* very subtle header tint on each supergroup group-band cell */\n"
    "#mo-matrix-table thead tr.mo-mx-group-row th.mo-mx-g-stages,\n"
    "#mo-main-table   thead tr.mo-group-row    th.mo-mx-g-stages   { background-color: rgba(27,94,32,0.07); }\n"
    "#mo-matrix-table thead tr.mo-mx-group-row th.mo-mx-g-pretest,\n"
    "#mo-main-table   thead tr.mo-group-row    th.mo-mx-g-pretest  { background-color: rgba(15,110,86,0.07); }\n"
    "#mo-matrix-table thead tr.mo-mx-group-row th.mo-mx-g-posttest,\n"
    "#mo-main-table   thead tr.mo-group-row    th.mo-mx-g-posttest { background-color: rgba(163,45,45,0.07); }\n"
    "#mo-matrix-table thead tr.mo-mx-group-row th.mo-mx-g-setups,\n"
    "#mo-main-table   thead tr.mo-group-row    th.mo-mx-g-setups   { background-color: rgba(186,117,23,0.07); }\n"
    "#mo-matrix-table thead tr.mo-mx-group-row th.mo-mx-g-tests,\n"
    "#mo-main-table   thead tr.mo-group-row    th.mo-mx-g-tests    { background-color: rgba(24,95,165,0.07); }"
)

# ---------- Edit 2: extend the JS moIsSectionStart block with the matching End helper + map ----------
JS_HELPER_OLD = (
    "  var MO_SECTION_BORDER_CLS = {\n"
    "    'Stages': 'mo-sec-start-stages',\n"
    "    'Pre-farfalle indicators': 'mo-sec-start-pretest',\n"
    "    'Post-farfalle indicators': 'mo-sec-start-posttest',\n"
    "    'Capital qualification setups': 'mo-sec-start-setups',\n"
    "    'Capital deployment tests': 'mo-sec-start-tests'\n"
    "  };\n"
    "  function moIsSectionStart(idx){\n"
    "    if (idx === 0) return MO_ROWS[0].section;\n"
    "    if (MO_ROWS[idx].section !== MO_ROWS[idx-1].section) return MO_ROWS[idx].section;\n"
    "    return null;\n"
    "  }"
)
JS_HELPER_NEW = (
    "  var MO_SECTION_BORDER_CLS = {\n"
    "    'Stages': 'mo-sec-start-stages',\n"
    "    'Pre-farfalle indicators': 'mo-sec-start-pretest',\n"
    "    'Post-farfalle indicators': 'mo-sec-start-posttest',\n"
    "    'Capital qualification setups': 'mo-sec-start-setups',\n"
    "    'Capital deployment tests': 'mo-sec-start-tests'\n"
    "  };\n"
    "  // MD-V2-S38-SECTIONS-OVERVIEW-MARKER: matching end-of-section map.\n"
    "  var MO_SECTION_END_BORDER_CLS = {\n"
    "    'Stages': 'mo-sec-end-stages',\n"
    "    'Pre-farfalle indicators': 'mo-sec-end-pretest',\n"
    "    'Post-farfalle indicators': 'mo-sec-end-posttest',\n"
    "    'Capital qualification setups': 'mo-sec-end-setups',\n"
    "    'Capital deployment tests': 'mo-sec-end-tests'\n"
    "  };\n"
    "  function moIsSectionStart(idx){\n"
    "    if (idx === 0) return MO_ROWS[0].section;\n"
    "    if (MO_ROWS[idx].section !== MO_ROWS[idx-1].section) return MO_ROWS[idx].section;\n"
    "    return null;\n"
    "  }\n"
    "  function moIsSectionEnd(idx){\n"
    "    if (idx === MO_ROWS.length - 1) return MO_ROWS[idx].section;\n"
    "    if (MO_ROWS[idx].section !== MO_ROWS[idx+1].section) return MO_ROWS[idx].section;\n"
    "    return null;\n"
    "  }\n"
    "  function moSectionEdgeCls(idx){\n"
    "    var a = moIsSectionStart(idx), b = moIsSectionEnd(idx);\n"
    "    var s = '';\n"
    "    if (a) s += ' ' + MO_SECTION_BORDER_CLS[a];\n"
    "    if (b) s += ' ' + MO_SECTION_END_BORDER_CLS[b];\n"
    "    return s;\n"
    "  }"
)

# ---------- Edit 3: matrix tbody cell emission - add both start and end classes ----------
MX_OLD = (
    "      for (var r = 0; r < MO_ROWS.length; r++) {\n"
    "        var tier = moNormaliseTier(moReadRating(md, MO_ROWS[r].ratingPath));\n"
    "        var secStart = moIsSectionStart(r);  /* MD-V2-S36-BRIEF-MARKER */\n"
    "        var tdCls = secStart ? (' class=\"' + MO_SECTION_BORDER_CLS[secStart] + '\"') : '';\n"
    "        if (tier === 'None') {\n"
    "          html += '<td' + tdCls + '><span class=\"mo-mx-pill mo-mx-p-none\">&#8211;</span></td>';\n"
    "        } else {\n"
    "          html += '<td' + tdCls + '><span class=\"mo-mx-pill ' + MO_MX_TIER_PILL[tier] + '\">' + tier + '</span></td>';\n"
    "        }\n"
    "      }"
)
MX_NEW = (
    "      for (var r = 0; r < MO_ROWS.length; r++) {\n"
    "        var tier = moNormaliseTier(moReadRating(md, MO_ROWS[r].ratingPath));\n"
    "        var edge = moSectionEdgeCls(r);  /* MD-V2-S38-SECTIONS-OVERVIEW-MARKER */\n"
    "        var tdCls = edge ? (' class=\"' + edge.replace(/^ /, '') + '\"') : '';\n"
    "        if (tier === 'None') {\n"
    "          html += '<td' + tdCls + '><span class=\"mo-mx-pill mo-mx-p-none\">&#8211;</span></td>';\n"
    "        } else {\n"
    "          html += '<td' + tdCls + '><span class=\"mo-mx-pill ' + MO_MX_TIER_PILL[tier] + '\">' + tier + '</span></td>';\n"
    "        }\n"
    "      }"
)

# ---------- Edit 4: summary table tier-row cell emission - include section edge classes ----------
SUM_TIER_OLD = (
    "        var cls = 'mo-cell ' + MO_TIER_CLS[tier] + (n > 0 ? ' mo-has' : ' mo-zero') + (sel ? ' mo-cell-sel' : '');\n"
    "        var tip = rowDef.label + ' / ' + tier + ' - ' + n + ' stock(s)' +\n"
    "          (anySel ? ' meeting the selected pattern' : '') +\n"
    "          (sel ? '; selected (click to remove)' : '; click to add to the pattern');\n"
    "        html += '<td class=\"' + cls + '\" onclick=\"moCellClick(\\'' + rowDef.key + '\\',\\'' + tier + '\\')\" ' +\n"
    "          'title=\"' + moMxAttr(tip) + '\">' + n.toLocaleString('en-GB') + '</td>';"
)
SUM_TIER_NEW = (
    "        var cls = 'mo-cell ' + MO_TIER_CLS[tier] + (n > 0 ? ' mo-has' : ' mo-zero') + (sel ? ' mo-cell-sel' : '') + moSectionEdgeCls(c);  /* MD-V2-S38-SECTIONS-OVERVIEW-MARKER */\n"
    "        var tip = rowDef.label + ' / ' + tier + ' - ' + n + ' stock(s)' +\n"
    "          (anySel ? ' meeting the selected pattern' : '') +\n"
    "          (sel ? '; selected (click to remove)' : '; click to add to the pattern');\n"
    "        html += '<td class=\"' + cls + '\" onclick=\"moCellClick(\\'' + rowDef.key + '\\',\\'' + tier + '\\')\" ' +\n"
    "          'title=\"' + moMxAttr(tip) + '\">' + n.toLocaleString('en-GB') + '</td>';"
)

# ---------- Edit 5: summary table total-row cell emission - include section edge classes ----------
SUM_TOT_OLD = (
    "      html += '<td class=\"mo-total-cell\" title=\"' + moMxAttr(MO_ROWS[c2].label + ' - ' + tot + ' rated' + (anySel ? ' within the selected pattern' : '')) + '\">' +\n"
    "        tot.toLocaleString('en-GB') + '</td>';"
)
SUM_TOT_NEW = (
    "      html += '<td class=\"mo-total-cell' + moSectionEdgeCls(c2) + '\" title=\"' + moMxAttr(MO_ROWS[c2].label + ' - ' + tot + ' rated' + (anySel ? ' within the selected pattern' : '')) + '\">' +  /* MD-V2-S38-SECTIONS-OVERVIEW-MARKER */\n"
    "        tot.toLocaleString('en-GB') + '</td>';"
)

# ---------- Edit 6: v2-nav button "Master Overview" -> "Overview" (visible button on the nav row) ----------
NAV_OLD = ">Master Overview</button>"
NAV_NEW = ">Overview</button>"

# ---------- Edit 7: Overview tab page intro "Master Overview is the synoptic..." -> "Overview is..." ----------
INTRO_OLD = "<div class=\"s1-intro\">Master Overview is the synoptic view of the whole MD V2 system."
INTRO_NEW = "<div class=\"s1-intro\">Overview is the synoptic view of the whole MD V2 system."


EDITS = [
    ("css-comprehensive-sections", CSS_OLD,       CSS_NEW,       1),
    ("js-section-end-helper",      JS_HELPER_OLD, JS_HELPER_NEW, 1),
    ("js-matrix-edges",            MX_OLD,        MX_NEW,        1),
    ("js-summary-tier-edges",      SUM_TIER_OLD,  SUM_TIER_NEW,  1),
    ("js-summary-total-edges",     SUM_TOT_OLD,   SUM_TOT_NEW,   1),
    ("nav-master-overview-btn",    NAV_OLD,       NAV_NEW,       1),
    ("intro-master-overview",      INTRO_OLD,     INTRO_NEW,     1),
]


def _rep(s, label, old, new, expected):
    c = s.count(old)
    if c != expected:
        raise AssertionError("[%s] expected %d occurrence(s), found %d -- anchor head: %r"
                             % (label, expected, c, old[:140]))
    return s.replace(old, new)


def transform(src):
    if MARKER in src:
        raise AssertionError("MARKER already present -- source is already patched")
    out = src
    for label, old, new, n in EDITS:
        out = _rep(out, label, old, new, n)
    if MARKER not in out:
        raise AssertionError("MARKER missing from output -- edits failed")
    return out


def _git_head_source():
    return subprocess.check_output(["git", "show", "HEAD:scripts/build_dashboard.py"]).decode("utf-8")


def main(argv):
    if len(argv) >= 1 and argv[0] == "--test":
        src_path, out_path = argv[1], argv[2]
        with open(src_path, "r", encoding="utf-8") as f:
            src = f.read()
        out = transform(src)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(out)
        py_compile.compile(out_path, doraise=True)
        print("[--test] OK  in=%d  out=%d  -> %s" % (len(src), len(out), out_path))
        return 0

    if not os.path.isfile(TARGET):
        print("ERROR: run from the master-dashboard repo root.")
        return 2

    with open(TARGET, "r", encoding="utf-8", errors="replace") as f:
        wt = f.read()
    if MARKER in wt:
        print("Already patched (MARKER present in working tree). Nothing to do.")
        return 0

    head_src = _git_head_source()
    wt_md5  = hashlib.md5(wt.encode("utf-8", "replace")).hexdigest()
    head_md5 = hashlib.md5(head_src.encode("utf-8")).hexdigest()
    if wt_md5 != head_md5:
        print("ABORT: working-tree build_dashboard.py does not match HEAD and the S38 marker is absent.")
        print("       working-tree md5: %s" % wt_md5)
        print("       HEAD         md5: %s" % head_md5)
        return 3

    out = transform(head_src)

    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = TARGET + ".bak-pre-s38-sections-overview-" + ts
    with open(bak, "w", encoding="utf-8") as f:
        f.write(wt)
    tmp = TARGET + ".tmp-s38"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(out)
    py_compile.compile(tmp, doraise=True)
    os.replace(tmp, TARGET)

    print("OK: S38 sections + Overview rename applied.")
    print("    backup : %s" % bak)
    print("    target : %s  (%d -> %d chars)" % (TARGET, len(head_src), len(out)))
    print("    next   : python scripts/build_dashboard.py  ->  git add -A  ->  commit  ->  push")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
