#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# patch_md_v2_overview_colalign_s35b_2026_05_15.py
# =============================================================================
# MD V2 Master Dashboard - Session 35 corrective (15-May-26)
# Defect surfaced by Chrome verification of commit 5d1a99a: the transposed
# Overview summary table and the matrix beneath it DO NOT line up. Both tables
# use auto table-layout, so column widths are content-driven and diverge:
#   * summary first column rendered 242px, matrix Stock column 554px
#     (a couple of long company names with white-space:nowrap forced the matrix
#      first column to ~554px under auto layout)
#   * summary screen columns 81px, matrix screen columns 73px
# Result: same column ORDER, no column alignment - the "Logic: visual
# consistency" requirement is not met.
#
# Fix: switch BOTH tables to `table-layout: fixed` and give both an explicit
# shared <colgroup> (240px first column + 20x76px screen columns = 1760px).
# Under fixed layout + colgroup, column widths are unambiguous and identical
# across the two tables, so the page-body horizontal scroll moves them as one.
# To keep the matrix's long company names usable under a fixed 240px first
# column, .mo-mx-name-cell gets `overflow: hidden; text-overflow: ellipsis;`
# (the existing `white-space: nowrap` handles the truncation cue). 98% of the
# 946 names fit in 240px naturally (measured live); the rest (e.g. the
# Unibail-Rodamco-Westfield long form) ellipsis cleanly. 76px holds the matrix
# "Plausible" pill (60px) + cell padding comfortably (was rendering at 73px).
#
# Discipline (S33 / S35 patcher house style):
#  - Reads SOURCE via `git show HEAD:` (FUSE-immune).
#  - Idempotent on MARKER; working-tree-vs-HEAD safety gate; py_compile gate;
#    pre-write backup.
#  - Each edit anchors on a unique substring (verified count == 1) and asserts
#    that count before applying.
#
# Independent of the S35 base patcher and the Request 1 patcher (both already
# shipped). Operates on top of commits 5d1a99a / 9c262bd; either is fine
# because the automated 9c262bd refresh did not touch build_dashboard.py
# (byte-identical at both commits).
#
# Usage:
#   python scripts/patch_md_v2_overview_colalign_s35b_2026_05_15.py
#   python scripts/patch_md_v2_overview_colalign_s35b_2026_05_15.py --test SRC OUT
# =============================================================================
import sys, os, subprocess, hashlib, py_compile, datetime

MARKER = "MD-V2-OVERVIEW-COLALIGN-S35B-MARKER"
TARGET = os.path.join("scripts", "build_dashboard.py")


# --- 1. summary table: add table-layout:fixed ---
CSS1_OLD = "#mo-main-table { border-collapse: separate; border-spacing: 0; font-size: 12px; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }"
CSS1_NEW = "#mo-main-table { border-collapse: separate; border-spacing: 0; font-size: 12px; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; table-layout: fixed; }"

# --- 2. matrix table: add table-layout:fixed ---
CSS2_OLD = "#mo-matrix-table { border-collapse: separate; border-spacing: 0; font-size: 12px; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }"
CSS2_NEW = "#mo-matrix-table { border-collapse: separate; border-spacing: 0; font-size: 12px; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; table-layout: fixed; }"

# --- 3. matrix name cell: ellipsis under fixed column width ---
CSS3_OLD = ("#mo-matrix-table tbody td.mo-mx-name-cell {\n"
            "  position: sticky; left: 0; z-index: 5;\n"
            "  background: #fbfaf5; text-align: left; white-space: nowrap;\n"
            "  padding: 4px 10px; border-right: 1px solid #e0dcc8;\n"
            "}")
CSS3_NEW = ("#mo-matrix-table tbody td.mo-mx-name-cell {\n"
            "  position: sticky; left: 0; z-index: 5;\n"
            "  background: #fbfaf5; text-align: left; white-space: nowrap;\n"
            "  padding: 4px 10px; border-right: 1px solid #e0dcc8;\n"
            "  overflow: hidden; text-overflow: ellipsis;\n"
            "}")

# --- 4. shared colgroup widths (append after the Clear button rule, before CSS-END) ---
CSS4_OLD = "#mo-clear-btn.active { background: #BA7517; border-color: #BA7517; color: #fff; }"
CSS4_NEW = ("#mo-clear-btn.active { background: #BA7517; border-color: #BA7517; color: #fff; }\n"
            "/* MD-V2-OVERVIEW-COLALIGN-S35B-MARKER: shared colgroup widths -\n"
            "   240px first column + 20x76px screen columns; combined with\n"
            "   table-layout:fixed on both tables, this is what makes the\n"
            "   summary table line up column-for-column with the matrix. */\n"
            "col.mo-cg-label  { width: 240px; }\n"
            "col.mo-cg-screen { width: 76px; }")

# --- 5. JS: define MO_COLGROUP after MO_MX_TIER_PILL ---
JS5_OLD = ("  var MO_MX_TIER_PILL = {\n"
           "    'None': 'mo-mx-p-none', 'Possible': 'mo-mx-p-pos',\n"
           "    'Plausible': 'mo-mx-p-pla', 'Probable': 'mo-mx-p-prob'\n"
           "  };")
JS5_NEW = ("  var MO_MX_TIER_PILL = {\n"
           "    'None': 'mo-mx-p-none', 'Possible': 'mo-mx-p-pos',\n"
           "    'Plausible': 'mo-mx-p-pla', 'Probable': 'mo-mx-p-prob'\n"
           "  };\n"
           "\n"
           "  // MD-V2-OVERVIEW-COLALIGN-S35B-MARKER: shared colgroup string.\n"
           "  // Both the summary table and the matrix emit this same colgroup\n"
           "  // so their columns share identical fixed widths under\n"
           "  // table-layout:fixed - that is what makes the two tables align.\n"
           "  var MO_COLGROUP = (function(){\n"
           "    var s = '<col class=\"mo-cg-label\">';\n"
           "    for (var i = 0; i < MO_ROWS.length; i++) s += '<col class=\"mo-cg-screen\">';\n"
           "    return s;\n"
           "  })();")

# --- 6. summary table HTML: insert <colgroup> before <thead> ---
JS6_OLD = "'<thead>' + groupTr + colTr + '</thead><tbody id=\"mo-tbody\">"
JS6_NEW = "'<colgroup>' + MO_COLGROUP + '</colgroup><thead>' + groupTr + colTr + '</thead><tbody id=\"mo-tbody\">"

# --- 7. matrix scaffold HTML: insert <colgroup> before <thead> ---
JS7_OLD = "'<thead></thead><tbody id=\"mo-matrix-tbody\">"
JS7_NEW = "'<colgroup>' + MO_COLGROUP + '</colgroup><thead></thead><tbody id=\"mo-matrix-tbody\">"


EDITS = [
    ("css-main-table-layout-fixed",    CSS1_OLD, CSS1_NEW),
    ("css-matrix-table-layout-fixed",  CSS2_OLD, CSS2_NEW),
    ("css-matrix-namecell-ellipsis",   CSS3_OLD, CSS3_NEW),
    ("css-shared-colgroup-widths",     CSS4_OLD, CSS4_NEW),
    ("js-mo-colgroup-const",           JS5_OLD, JS5_NEW),
    ("js-summary-table-colgroup",      JS6_OLD, JS6_NEW),
    ("js-matrix-scaffold-colgroup",    JS7_OLD, JS7_NEW),
]


def transform(src):
    if MARKER in src:
        raise AssertionError("MARKER already present -- source is already patched")
    out = src
    for label, old, new in EDITS:
        c = out.count(old)
        if c != 1:
            raise AssertionError("[%s] expected 1 occurrence, found %d -- anchor: %r"
                                 % (label, c, old[:120]))
        out = out.replace(old, new)
    # post-conditions
    if MARKER not in out:
        raise AssertionError("MARKER missing from output -- edits failed")
    if out.count(MARKER) != 2:
        raise AssertionError("MARKER count %d (expected 2: CSS preamble + JS preamble)" % out.count(MARKER))
    if "MO_COLGROUP" not in out:
        raise AssertionError("MO_COLGROUP not present after patch")
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
        print("ERROR: run from the master-dashboard repo root (scripts/build_dashboard.py not found).")
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
        print("ABORT: working-tree build_dashboard.py does not match HEAD and the")
        print("       S35B marker is absent. Unexpected state -- resolve before patching.")
        print("       working-tree md5: %s" % wt_md5)
        print("       HEAD         md5: %s" % head_md5)
        print("       (If HEAD is clean, run `git checkout -- scripts/build_dashboard.py` first.)")
        return 3

    out = transform(head_src)

    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = TARGET + ".bak-pre-overview-colalign-s35b-" + ts
    with open(bak, "w", encoding="utf-8") as f:
        f.write(wt)
    tmp = TARGET + ".tmp-s35b-colalign"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(out)
    py_compile.compile(tmp, doraise=True)
    os.replace(tmp, TARGET)

    print("OK: Overview column-alignment fix applied (table-layout:fixed + shared colgroup).")
    print("    backup : %s" % bak)
    print("    target : %s  (%d -> %d chars)" % (TARGET, len(head_src), len(out)))
    print("    next   : python scripts/build_dashboard.py  ->  git add -A  ->  commit  ->  push")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
