#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# patch_md_v2_s36_brief_2026_05_15.py
# =============================================================================
# MD V2 Master Dashboard - Session 36 (15-May-26)
# Bulk integration of Richard's 15-May brief. UI-only relabels (Richard
# confirmed Q1: keep data/code keys as-is, change labels only). Plus targeted
# CSS layout fixes and one Stage 3 text fix.
#
# Items in this patcher:
#   * Master Overview -> Overview (tab label, header title is left as
#     "Master Dashboard" - Richard didn't ask to change that).
#   * Pre-indicators -> Pre-farfalle (tab nav buttons, v2-nav group buttons,
#     MO_ROWS sections, group-label maps). Same for Post.
#   * "Basing" tile label -> "Basing in a MT/LT uptrend" (MO_ROWS label only;
#     pre_indicators tab tile title also gets renamed if its anchor exists).
#   * "Breakdown 50D/150D/200D" -> "Negatively breaking through ST/MT/LT trend
#     (50D/150D/200D MA)" (MO_ROWS labels + post-indicators tile shortLabels).
#   * v2-nav group renames: "Stages" -> "Stages - MT/LT trends",
#     "Indicators" -> "Early-stage indicators",
#     "Capital qualification" -> "Late-stage capital qualification".
#   * v2-nav separators "|" pipes -> left-to-right arrows (CSS rule change).
#   * Stage 3 pill labels "Probable Inv." -> "Probable Invalidation",
#     "Plausible Inv." -> "Plausible Invalidation".
#   * Stage 3 "The debate" -> "Investor/holder debate" (every occurrence).
#   * Stage 3 200D flattening test value: was 'flat'/'-' (only one state had
#     text), now 'flat'/'rising' (both states meaningful) so the "show test
#     values" toggle is readable on that column.
#   * Healthy retest setup tile colour: was red (pi-tile-collapsing), now
#     navy (pi-tile-navy) - the existing positive-neutral palette class with
#     full chip/strip/tile CSS already defined for setups.
#   * Header HTML: "Updated:" relabelled "Price data updated:"; new
#     "Stock universe updated:" span added; load_data() bakes
#     meta.universe_updated from data/universe.json mtime; init JS populates
#     #stat-universe-updated.
#   * CSS: group-header-row text-transform: uppercase removed (Richard:
#     all-caps fine for SUPERGROUP titles but not group column titles).
#     Super-group rows untouched.
#   * CSS: tab-scoped .s1-rating-tiles grid-template-columns repeat(3, 1fr)
#     -> repeat(auto-fit, minmax(170px, 1fr)) so 5-tile tabs (post_indicators)
#     fit on one row when there is width for it (Richard's "summary tiles
#     wrap to one row" ask).
#   * CSS: tab-scoped .group-captions grid-template-columns repeat(3, 1fr)
#     -> repeat(auto-fit, minmax(280px, 1fr)) so caption tiles use the full
#     row width and stack less tall.
#   * CSS: Overview matrix tbody visual section grouping - coloured left
#     border on the first body cell of each supergroup section, matching the
#     existing thead group-band colour hooks.
#
# DEFERRED to follow-ups (captured in the carried backlog):
#   * Default tile click = Probable only (JS behavioural change)
#   * Tier chips always show {Possible, Plausible, Probable} including zeros
#   * Per-tile thresholds (move from group caption to per-rating-tile)
#   * Inputs supergroup header showing live stock count
#   * Caption rewrites across all tabs (with the before/after review doc
#     Richard asked for at the end)
#   * Probing bet description correction (Richard parked at his request)
#   * Sticky inputs/scope ribbon
#   * Responsive contracted column headers
#   * Android tablet header overflow
#   * Combine indicator/setup/test buttons (Richard "Hold off")
#
# Discipline (S33 / S35 / S35B house style):
#  - Reads SOURCE via `git show HEAD:` (FUSE-immune).
#  - Idempotent on MARKER.
#  - Working-tree-vs-HEAD safety gate.
#  - Every edit asserts an exact occurrence count; mismatch aborts the run
#    so partial application can never happen.
#  - py_compile validates result before write; pre-write backup taken.
#
# Usage:
#   python scripts/patch_md_v2_s36_brief_2026_05_15.py
#   python scripts/patch_md_v2_s36_brief_2026_05_15.py --test SRC OUT
# =============================================================================
import sys, os, subprocess, hashlib, py_compile, datetime

MARKER = "MD-V2-S36-BRIEF-MARKER"
TARGET = os.path.join("scripts", "build_dashboard.py")


# Each entry: (label, old_string, new_string, expected_count).
EDITS = [
    # ---- 1. Tab labels ----
    ("tab-overview-label",
     '{"id": "master_overview", "label": "Master Overview", "accent": "#1b3d5c"},',
     '{"id": "master_overview", "label": "Overview", "accent": "#1b3d5c"},',
     1),
    ("tab-pre-label",
     '{"id": "pre_indicators", "label": "Pre-indicators", "accent": "#0F6E56"},',
     '{"id": "pre_indicators", "label": "Pre-farfalle", "accent": "#0F6E56"},',
     1),
    ("tab-post-label",
     '{"id": "post_indicators", "label": "Post-indicators", "accent": "#A32D2D"},',
     '{"id": "post_indicators", "label": "Post-farfalle", "accent": "#A32D2D"},',
     1),

    # ---- 2. v2-nav group labels + button labels ----
    ("v2nav-stages-label",
     '<span class="v2-nav-grp-label">Stages</span>',
     '<span class="v2-nav-grp-label">Stages - MT/LT trends</span>',
     1),
    ("v2nav-indicators-label",
     '<span class="v2-nav-grp-label">Indicators</span>',
     '<span class="v2-nav-grp-label">Early-stage indicators</span>',
     1),
    ("v2nav-capqual-label",
     '<span class="v2-nav-grp-label">Capital qualification</span>',
     '<span class="v2-nav-grp-label">Late-stage capital qualification</span>',
     1),
    ("v2nav-pre-button",
     "onclick=\"switchTab(\\'pre_indicators\\')\">Pre-test indicators</button>",
     "onclick=\"switchTab(\\'pre_indicators\\')\">Pre-farfalle indicators</button>",
     1),
    ("v2nav-post-button",
     "onclick=\"switchTab(\\'post_indicators\\')\">Post-test indicators</button>",
     "onclick=\"switchTab(\\'post_indicators\\')\">Post-farfalle indicators</button>",
     1),

    # ---- 3. v2-nav separators: pipes -> arrows (CSS rule change) ----
    ("v2nav-sep-css-arrow",
     ".v2-nav-sep { display: inline-block; width: 1px; height: 18px; background: #d8d4c2; margin: 0 8px; }",
     ".v2-nav-sep { display: inline-block; width: auto; height: auto; background: none; margin: 0 6px; color: #8a8674; font-size: 13px; font-weight: 600; line-height: 1; vertical-align: middle; }\n.v2-nav-sep::before { content: \"\\2192\"; }  /* MD-V2-S36-BRIEF-MARKER right-arrow */",
     1),

    # ---- 4. MO_ROWS section labels (Overview matrix row model) ----
    # 'Pre-test indicators' appears 3x in MO_ROWS section field
    ("morows-section-pretest",
     "section:'Pre-test indicators',",
     "section:'Pre-farfalle indicators',",
     3),
    # 'Post-test indicators' appears 5x in MO_ROWS section field
    ("morows-section-posttest",
     "section:'Post-test indicators',",
     "section:'Pre-farfalle indicators TEMP_POSTTEST',",  # interim sentinel to avoid clashing with the previous pattern
     5),
    ("morows-section-posttest-final",
     "section:'Pre-farfalle indicators TEMP_POSTTEST',",
     "section:'Post-farfalle indicators',",
     5),
    # Basing label (single occurrence as 'Basing' in MO_ROWS, the column label)
    ("morows-basing-label",
     "key:'basing', label:'Basing',",
     "key:'basing', label:'Basing in a MT/LT uptrend',",
     1),
    # Breakdown labels
    ("morows-breakdown-50",
     "label:'Breakdown 50D'",
     "label:'Negatively breaking through ST trend (50D MA)'",
     1),
    ("morows-breakdown-150",
     "label:'Breakdown 150D'",
     "label:'Negatively breaking through MT trend (150D MA)'",
     1),
    ("morows-breakdown-200",
     "label:'Breakdown 200D'",
     "label:'Negatively breaking through LT trend (200D MA)'",
     1),

    # ---- 5. Overview-module group-label/section-tone maps (string keys) ----
    ("mo-group-cls-pretest-key",
     "'Pre-test indicators': 'mo-mx-g-pretest',",
     "'Pre-farfalle indicators': 'mo-mx-g-pretest',",
     1),
    ("mo-group-cls-posttest-key",
     "'Post-test indicators': 'mo-mx-g-posttest',",
     "'Post-farfalle indicators': 'mo-mx-g-posttest',",
     1),
    ("mo-group-label-pretest-kv",
     "'Pre-test indicators': 'Pre-test',",
     "'Pre-farfalle indicators': 'Pre-farfalle',",
     1),
    ("mo-group-label-posttest-kv",
     "'Post-test indicators': 'Post-test',",
     "'Post-farfalle indicators': 'Post-farfalle',",
     1),

    # ---- 6. Post-indicators tile shortLabels (pattern title used in tile + caption headers) ----
    ("po-shortlabel-bd50",
     '"shortLabel": "Breakdown 50D",',
     '"shortLabel": "Negatively breaking through ST trend (50D MA)",',
     1),
    ("po-shortlabel-bd150",
     '"shortLabel": "Breakdown 150D",',
     '"shortLabel": "Negatively breaking through MT trend (150D MA)",',
     1),
    ("po-shortlabel-bd200",
     '"shortLabel": "Breakdown 200D",',
     '"shortLabel": "Negatively breaking through LT trend (200D MA)",',
     1),

    # ---- 7. Stage 3 pill labels and "The debate" rename ----
    ("s3-pill-probable",
     '\'<span class="pill pill-prob-inv-\' + c + \'">Probable Inv.</span>\'',
     '\'<span class="pill pill-prob-inv-\' + c + \'">Probable Invalidation</span>\'',
     1),
    ("s3-pill-plausible",
     '\'<span class="pill pill-pla-inv">Plausible Inv.</span>\'',
     '\'<span class="pill pill-pla-inv">Plausible Invalidation</span>\'',
     1),
    # "Group 3 · The debate" appears in caption header and column-group header
    ("s3-debate-caption",
     "<b>Group 3 \xb7 The debate</b>",
     "<b>Group 3 \xb7 Investor/holder debate</b>",
     1),
    ("s3-debate-colgroup",
     "colspan=\"3\">Group 3 \xb7 The debate</th>",
     "colspan=\"3\">Group 3 \xb7 Investor/holder debate</th>",
     1),

    # ---- 8. Stage 3 200D flattening test value: 'flat' / '-' -> 'flat' / 'rising' ----
    ("s3-t3-200d-value",
     "if (k === 'T3') return t.T3_200D_flattening ? 'flat' : '—';",
     "if (k === 'T3') return t.T3_200D_flattening ? 'flat' : 'rising';",
     1),

    # ---- 9. Healthy retest setup colour: collapsing (red) -> navy (positive-neutral) ----
    ("st-tone-healthy",
     '"healthy_retest": "pi-tile-collapsing",',
     '"healthy_retest": "pi-tile-navy",',
     1),
    ("st-strip-healthy",
     '"healthy_retest": "pi-strip-collapsing",',
     '"healthy_retest": "pi-strip-navy",',
     1),
    ("st-chip-healthy",
     '"healthy_retest": "collapsing",',
     '"healthy_retest": "navy",',
     1),

    # ---- 10. Header HTML: "Updated:" relabel + Stock universe span ----
    ("header-updated-label",
     "'      <span>Updated: <span class=\"stat-value\" id=\"stat-updated\">&mdash;</span></span>\\n'",
     "'      <span>Price data updated: <span class=\"stat-value\" id=\"stat-updated\">&mdash;</span></span>\\n'\n"
     "        '      <span>Stock universe updated: <span class=\"stat-value\" id=\"stat-universe-updated\">&mdash;</span></span>\\n'",
     1),

    # ---- 11. load_data(): bake meta.universe_updated from data/universe.json mtime ----
    ("load-data-meta-block",
     "    master = {\n"
     "        \"meta\": {\n"
     "            \"generated\": prices[\"_meta\"][\"generated\"],\n"
     "            \"source\": prices[\"_meta\"][\"source\"],\n"
     "            \"stock_count\": prices[\"_meta\"][\"count\"],\n"
     "        },",
     "    # MD-V2-S36-BRIEF-MARKER: universe_updated = mtime of data/universe.json,\n"
     "    # formatted as 'YYYY-MM-DD HH:MM'. The file has no _meta field, so we use mtime.\n"
     "    try:\n"
     "        _u_mtime = (DATA_DIR / \"universe.json\").stat().st_mtime\n"
     "        _universe_updated = datetime.fromtimestamp(_u_mtime).strftime(\"%Y-%m-%d %H:%M\")\n"
     "    except Exception:\n"
     "        _universe_updated = \"—\"\n"
     "    master = {\n"
     "        \"meta\": {\n"
     "            \"generated\": prices[\"_meta\"][\"generated\"],\n"
     "            \"source\": prices[\"_meta\"][\"source\"],\n"
     "            \"stock_count\": prices[\"_meta\"][\"count\"],\n"
     "            \"universe_updated\": _universe_updated,\n"
     "        },",
     1),

    # ---- 12. Init JS: populate the new universe-updated span ----
    ("js-populate-universe-updated",
     'document.getElementById("stat-updated").textContent=D.meta.generated;',
     'document.getElementById("stat-updated").textContent=D.meta.generated;\n'
     'var _stUni=document.getElementById("stat-universe-updated");if(_stUni)_stUni.textContent=D.meta.universe_updated||"\\u2014";  /* MD-V2-S36-BRIEF-MARKER */',
     1),

    # ---- 13. CSS: all-caps off for group-header-row (group column titles) ----
    # The group-header-row CSS appears in 7 tab-specific blocks (s1, s2, s3, s4, pi, po, st, ct).
    # Use a sentinel-pair pattern to do this safely.
    ("css-grouphead-uppercase-off",
     "thead .group-header-row th { background: #f3efe2 !important; font-size: 9px; text-transform: uppercase; font-weight: 700; letter-spacing: 0.4px; padding: 5px 3px; cursor: default; white-space: normal; line-height: 1.25; }",
     "thead .group-header-row th { background: #f3efe2 !important; font-size: 9.5px; text-transform: none; font-weight: 700; letter-spacing: 0.2px; padding: 5px 3px; cursor: default; white-space: normal; line-height: 1.25; }",
     4),
    ("css-grouphead-uppercase-off-v2",
     "thead .group-header-row th { background: #f3efe2 !important; font-size: 9px; text-transform: uppercase; font-weight: 700; letter-spacing: 0.4px; padding: 5px 3px; cursor: default; line-height: 1.25; }",
     "thead .group-header-row th { background: #f3efe2 !important; font-size: 9.5px; text-transform: none; font-weight: 700; letter-spacing: 0.2px; padding: 5px 3px; cursor: default; line-height: 1.25; }",
     4),

    # ---- 14. CSS: group-captions grid - auto-fit so captions wrap full width ----
    # Anchor for pre_indicators / post_indicators / setups / tests + base rule
    ("css-groupcap-pre",
     "#tab-pre_indicators .group-captions { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 16px 0 14px 0; }",
     "#tab-pre_indicators .group-captions { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 10px; margin: 16px 0 14px 0; }",
     1),
    ("css-groupcap-post",
     "#tab-post_indicators .group-captions { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; margin: 16px 0 14px 0; }",
     "#tab-post_indicators .group-captions { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 10px; margin: 16px 0 14px 0; }",
     1),

    # ---- 15. CSS: rating tiles - auto-fit so tabs with 5 tiles fit on one row when width allows ----
    ("css-tiles-pre",
     "#tab-pre_indicators .s1-rating-tiles { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }",
     "#tab-pre_indicators .s1-rating-tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 8px; }",
     1),
    ("css-tiles-post",
     "#tab-post_indicators .s1-rating-tiles { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }",
     "#tab-post_indicators .s1-rating-tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 8px; }",
     1),

    # ---- 16. CSS: Overview matrix - visual supergroup grouping (coloured left border on first
    #         body cell of each section). Append as new rules tagged with the marker.
    ("css-overview-visual-sections",
     "#mo-clear-btn.active { background: #BA7517; border-color: #BA7517; color: #fff; }",
     "#mo-clear-btn.active { background: #BA7517; border-color: #BA7517; color: #fff; }\n"
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
     "#mo-main-table   tbody td.mo-sec-start-tests    { border-left: 3px solid #185FA5; }",
     1),

    # ---- 17. JS: add mo-sec-start-* class to the section-starting body cells in both Overview tables ----
    # Define a section -> class-suffix map, and apply it to the relevant td emission lines.
    ("js-overview-section-css-map",
     "  var MO_GROUP_CLS = {\n"
     "    'Stages': 'mo-mx-g-stages',\n"
     "    'Pre-farfalle indicators': 'mo-mx-g-pretest',\n"
     "    'Post-farfalle indicators': 'mo-mx-g-posttest',\n"
     "    'Capital qualification setups': 'mo-mx-g-setups',\n"
     "    'Capital deployment tests': 'mo-mx-g-tests'\n"
     "  };",
     "  var MO_GROUP_CLS = {\n"
     "    'Stages': 'mo-mx-g-stages',\n"
     "    'Pre-farfalle indicators': 'mo-mx-g-pretest',\n"
     "    'Post-farfalle indicators': 'mo-mx-g-posttest',\n"
     "    'Capital qualification setups': 'mo-mx-g-setups',\n"
     "    'Capital deployment tests': 'mo-mx-g-tests'\n"
     "  };\n"
     "  // MD-V2-S36-BRIEF-MARKER: per-section class suffix for the body-cell visual\n"
     "  // grouping border (CSS rule #mo-matrix-table tbody td.mo-sec-start-*).\n"
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
     "  }",
     1),

    # ---- 18. JS: add the border class to the matrix body cell at each section start ----
    ("js-matrix-section-border",
     "      for (var r = 0; r < MO_ROWS.length; r++) {\n"
     "        var tier = moNormaliseTier(moReadRating(md, MO_ROWS[r].ratingPath));\n"
     "        if (tier === 'None') {\n"
     "          html += '<td><span class=\"mo-mx-pill mo-mx-p-none\">&#8211;</span></td>';\n"
     "        } else {\n"
     "          html += '<td><span class=\"mo-mx-pill ' + MO_MX_TIER_PILL[tier] + '\">' + tier + '</span></td>';\n"
     "        }\n"
     "      }",
     "      for (var r = 0; r < MO_ROWS.length; r++) {\n"
     "        var tier = moNormaliseTier(moReadRating(md, MO_ROWS[r].ratingPath));\n"
     "        var secStart = moIsSectionStart(r);  /* MD-V2-S36-BRIEF-MARKER */\n"
     "        var tdCls = secStart ? (' class=\"' + MO_SECTION_BORDER_CLS[secStart] + '\"') : '';\n"
     "        if (tier === 'None') {\n"
     "          html += '<td' + tdCls + '><span class=\"mo-mx-pill mo-mx-p-none\">&#8211;</span></td>';\n"
     "        } else {\n"
     "          html += '<td' + tdCls + '><span class=\"mo-mx-pill ' + MO_MX_TIER_PILL[tier] + '\">' + tier + '</span></td>';\n"
     "        }\n"
     "      }",
     1),
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
        print("       S36 marker is absent. Unexpected state -- resolve before patching.")
        print("       working-tree md5: %s" % wt_md5)
        print("       HEAD         md5: %s" % head_md5)
        return 3

    out = transform(head_src)

    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = TARGET + ".bak-pre-s36-brief-" + ts
    with open(bak, "w", encoding="utf-8") as f:
        f.write(wt)
    tmp = TARGET + ".tmp-s36"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(out)
    py_compile.compile(tmp, doraise=True)
    os.replace(tmp, TARGET)

    print("OK: S36 brief patcher applied.")
    print("    backup : %s" % bak)
    print("    target : %s  (%d -> %d chars)" % (TARGET, len(head_src), len(out)))
    print("    next   : python scripts/build_dashboard.py  ->  git add -A  ->  commit  ->  push")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
