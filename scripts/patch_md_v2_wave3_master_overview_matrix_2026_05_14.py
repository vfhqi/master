#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
patch_md_v2_wave3_master_overview_matrix_2026_05_14.py

SA - Master Dashboard | MD V2 | Wave 3 - Master Overview full rating matrix.

Appends a SECOND table below the existing 20-row Master Overview distribution
table (which stays untouched). The new matrix:
  - Y-axis: every md_v2 stock (company name + ticker), sticky first column.
  - X-axis: the 20 screens already in MO_ROWS, grouped under their 5 sections.
  - Cells: a coloured rating pill per stock x screen; "-" where None.
  - Per-column filter: three small chips stacked VERTICALLY above each
    screen column (Prob / Pla / Pos), toned down so they read as controls.
    Click to restrict that column; multiple chips in one column OR together;
    columns AND together; nothing selected = all rows.
  - Sticky header stack: nav (fixed) -> ribbon (sticky) -> chip row ->
    section-group row -> column-title row. Column titles WRAP (no rotation).
  - Renders ALL stocks (Richard: "All" - no narrowed default view).

Three edits to scripts/build_dashboard.py:
  (1) CSS  - injected immediately before the Wave 1 CSS end marker so it is
             last in source order and wins the cascade (D-MD-V2-76 lesson).
  (2) JS   - moGetRows() extended to carry the company name.
  (3) JS   - the Master Overview IIFE extended with moRenderMatrix() + filter
             state + handlers; renderMasterOverview() calls both renders.

Idempotent via MD-V2-WAVE3-MASTER-OVERVIEW-MATRIX-MARKER. ASCII-only literals.
Patcher discipline: utf-8 IO, temp/validation files beside the patcher,
atomic write at end, dry-run support, MD5 self-report.

Usage:
    python patch_md_v2_wave3_master_overview_matrix_2026_05_14.py            # patch in place
    python patch_md_v2_wave3_master_overview_matrix_2026_05_14.py --dry-run  # write .patched copy beside patcher, do not touch source
"""

import os
import sys
import hashlib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(SCRIPT_DIR, "build_dashboard.py")
MARKER = "MD-V2-WAVE3-MASTER-OVERVIEW-MATRIX-MARKER"

# Anchors -------------------------------------------------------------------
CSS_END_ANCHOR = "/* MD-V2-WAVE1-FROZEN-HEADERS-MARKER-CSS-END */"

MOGETROWS_ANCHOR = (
    "      var p = prices[s.ticker] || {};\n"
    "      rows.push({ ticker: s.ticker, md_v2: s.md_v2, is_live: !!live[s.ticker] });"
)
MOGETROWS_REPLACEMENT = (
    "      var p = prices[s.ticker] || {};\n"
    "      /* " + MARKER + ": carry company name for the matrix Y-axis labels. */\n"
    "      rows.push({ ticker: s.ticker, company: p.company_name || s.ticker, md_v2: s.md_v2, is_live: !!live[s.ticker] });"
)

RENDER_ANCHOR = (
    "  function renderMasterOverview() {\n"
    "    moRenderTable();\n"
    "  }\n"
    "  window.renderMasterOverview = renderMasterOverview;"
)

# ---------------------------------------------------------------------------
# (1) CSS block - injected immediately BEFORE the Wave 1 CSS end marker.
# ---------------------------------------------------------------------------
CSS_BLOCK = r"""/* """ + MARKER + r""": Wave 3 (14-May-26) - Master Overview full rating
   matrix. A second table appended below the existing distribution table.
   Lives inside the Wave 1 CSS block so it is last in source order and wins
   the cascade against the base #mo-main-table rules (D-MD-V2-76 lesson).
   Sticky header stack reuses the Wave 1 --header-height + --v2-ribbon-h
   ladder: chip row -> section-group row -> column-title row. */
#mo-matrix-wrap { margin-top: 18px; }
#mo-matrix-caption { font-size: 11px; color: #7a7560; margin: 0 0 6px 2px; }
#mo-matrix-table { border-collapse: separate; border-spacing: 0; font-size: 12px; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }
#mo-matrix-table thead { position: static; }
/* chip row - the per-column vertical filter chips, topmost sticky header row */
#mo-matrix-table thead tr.mo-mx-chip-row th {
  position: sticky;
  top: calc(var(--header-height) + var(--v2-ribbon-h));
  z-index: 72;
  background: #f3efe2;
  padding: 4px 3px 5px;
  vertical-align: bottom;
}
#mo-matrix-table thead tr.mo-mx-chip-row th.mo-mx-corner {
  left: 0;
  z-index: 75;
  text-align: left;
  padding: 4px 10px 5px;
  border-right: 1px solid #e0dcc8;
}
#mo-matrix-table thead tr.mo-mx-chip-row th.mo-mx-corner .mo-mx-corner-lbl {
  font-size: 9px; color: #9a9582; text-transform: uppercase; letter-spacing: 0.4px;
}
/* section-group row */
#mo-matrix-table thead tr.mo-mx-group-row th {
  position: sticky;
  top: calc(var(--header-height) + var(--v2-ribbon-h) + 56px);
  z-index: 71;
  background: #f3efe2;
  font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px;
  padding: 5px 6px; text-align: center;
  border-left: 1px solid #e0dcc8;
}
#mo-matrix-table thead tr.mo-mx-group-row th.mo-mx-corner {
  left: 0; z-index: 74; border-right: 1px solid #e0dcc8; border-left: none;
}
#mo-matrix-table thead tr.mo-mx-group-row th.mo-mx-g-stages   { color: #1b5e20; }
#mo-matrix-table thead tr.mo-mx-group-row th.mo-mx-g-pretest  { color: #0F6E56; }
#mo-matrix-table thead tr.mo-mx-group-row th.mo-mx-g-posttest { color: #A32D2D; }
#mo-matrix-table thead tr.mo-mx-group-row th.mo-mx-g-setups   { color: #BA7517; }
#mo-matrix-table thead tr.mo-mx-group-row th.mo-mx-g-tests    { color: #185FA5; }
/* column-title row - labels WRAP (no rotation), columns stay pill-width */
#mo-matrix-table thead tr.mo-mx-col-row th {
  position: sticky;
  top: calc(var(--header-height) + var(--v2-ribbon-h) + 78px);
  z-index: 70;
  background: #f3efe2;
  font-size: 9.5px; font-weight: 700; color: #555;
  padding: 5px 4px; text-align: center; vertical-align: bottom;
  line-height: 1.2; width: 64px; min-width: 64px; max-width: 64px;
  white-space: normal; word-break: normal; overflow-wrap: break-word;
}
#mo-matrix-table thead tr.mo-mx-col-row th.mo-mx-screen-col {
  left: 0; z-index: 73;
  text-align: left; width: 190px; min-width: 190px; max-width: 190px;
  font-size: 10px; text-transform: uppercase; letter-spacing: 0.4px;
  border-right: 1px solid #e0dcc8;
}
/* the sticky first column needs an opaque bg on every header row it spans */
#mo-matrix-table thead th.mo-mx-corner,
#mo-matrix-table thead th.mo-mx-screen-col { background: #f3efe2; }
/* vertical chip stack */
.mo-mx-chip-stack { display: flex; flex-direction: column; gap: 2px; align-items: center; }
.mo-mx-chip {
  width: 30px; padding: 1px 0; border-radius: 7px;
  font-size: 8.5px; line-height: 1.4; font-weight: 400; cursor: pointer;
  border: 0.5px solid #d8d3bf; background: transparent; color: #9a9582;
  font-family: inherit; transition: background 0.1s, color 0.1s, border-color 0.1s;
}
.mo-mx-chip:hover { border-color: #b8b29a; color: #6f6a58; }
.mo-mx-chip.mo-mx-chip-on { font-weight: 500; }
.mo-mx-chip.mo-mx-chip-on.mo-mx-chip-prob { background: #e6f1fb; color: #185FA5; border-color: #cfe3f5; }
.mo-mx-chip.mo-mx-chip-on.mo-mx-chip-pla  { background: #eef5fc; color: #3778b0; border-color: #dcebf7; }
.mo-mx-chip.mo-mx-chip-on.mo-mx-chip-pos  { background: #fbf3e4; color: #a8761f; border-color: #f1e6cf; }
/* body cells + pills */
#mo-matrix-table tbody td { padding: 4px 6px; border-bottom: 1px solid #efece0; text-align: center; vertical-align: middle; }
#mo-matrix-table tbody tr:hover { background: rgba(15,110,86,0.05); }
#mo-matrix-table tbody td.mo-mx-name-cell {
  position: sticky; left: 0; z-index: 5;
  background: #fbfaf5; text-align: left; white-space: nowrap;
  padding: 4px 10px; border-right: 1px solid #e0dcc8;
}
#mo-matrix-table tbody tr:hover td.mo-mx-name-cell { background: #f4f1e6; }
#mo-matrix-table tbody td.mo-mx-name-cell .mo-mx-co { font-weight: 600; color: #2a2a2a; }
#mo-matrix-table tbody td.mo-mx-name-cell .mo-mx-tk { color: #a39d88; font-size: 10px; margin-left: 5px; }
.mo-mx-pill {
  display: inline-block; min-width: 20px; padding: 2px 8px;
  border-radius: 10px; font-size: 11px; font-weight: 600;
}
.mo-mx-pill.mo-mx-p-none { background: #f0ede1; color: #b4ae9a; font-weight: 400; }
.mo-mx-pill.mo-mx-p-pos  { background: rgba(15,110,86,0.10); color: #3a6a5a; }
.mo-mx-pill.mo-mx-p-pla  { background: rgba(15,110,86,0.20); color: #1a5446; }
.mo-mx-pill.mo-mx-p-prob { background: rgba(15,110,86,0.34); color: #0a3a2e; }
#mo-matrix-table tbody tr.mo-mx-empty td {
  text-align: center; color: #9a9582; font-size: 11px;
  padding: 14px 10px; background: #faf8f0;
}
#mo-matrix-foot { font-size: 11px; color: #7a7560; margin: 6px 0 0 2px; }
"""

# ---------------------------------------------------------------------------
# (3) JS - moRenderMatrix() + filter state/handlers + renderMasterOverview()
#          calling both. Replaces the RENDER_ANCHOR block.
# ---------------------------------------------------------------------------
JS_BLOCK = r"""  /* """ + MARKER + r""": Wave 3 (14-May-26) - the full rating matrix.
     A second table below the distribution table: every md_v2 stock down the
     Y-axis, the 20 MO_ROWS screens across the X-axis grouped by section, a
     coloured rating pill per cell. Each screen column carries three small
     vertically-stacked filter chips (Prob/Pla/Pos) above the section-group
     band; clicking restricts that column. Chips within one column OR
     together; columns AND together; nothing selected = all rows. Renders
     all md_v2 stocks (Richard chose "All" - no narrowed default). */

  /* moMxFilters[rowKey] = { Possible:true, Plausible:true, ... } - only the
     keys that are present are active. Empty/absent = column unconstrained. */
  var moMxFilters = {};

  var MO_MX_TIER_PILL = {
    'None': 'mo-mx-p-none', 'Possible': 'mo-mx-p-pos',
    'Plausible': 'mo-mx-p-pla', 'Probable': 'mo-mx-p-prob'
  };
  /* chip render order: Probable at the top of the vertical stack, then
     Plausible, then Possible. */
  var MO_MX_CHIPS = [
    { tier: 'Probable',  short: 'Prob', cls: 'mo-mx-chip-prob' },
    { tier: 'Plausible', short: 'Pla',  cls: 'mo-mx-chip-pla'  },
    { tier: 'Possible',  short: 'Pos',  cls: 'mo-mx-chip-pos'  }
  ];
  var MO_MX_GROUP_CLS = {
    'Stages': 'mo-mx-g-stages',
    'Pre-test indicators': 'mo-mx-g-pretest',
    'Post-test indicators': 'mo-mx-g-posttest',
    'Capital qualification setups': 'mo-mx-g-setups',
    'Capital deployment tests': 'mo-mx-g-tests'
  };
  /* short section labels for the group band - the full names are long. */
  var MO_MX_GROUP_LABEL = {
    'Stages': 'Stages',
    'Pre-test indicators': 'Pre-test',
    'Post-test indicators': 'Post-test',
    'Capital qualification setups': 'Qualification setups',
    'Capital deployment tests': 'Deployment tests'
  };

  function moMxAttr(s) {
    return String(s).replace(/&/g, '&amp;').replace(/'/g, '&#39;').replace(/"/g, '&quot;');
  }
  function moMxText(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  /* toggle one chip in one column's filter set, then re-render. */
  function moMxToggleChip(rowKey, tier) {
    var f = moMxFilters[rowKey];
    if (!f) { f = {}; moMxFilters[rowKey] = f; }
    if (f[tier]) { delete f[tier]; } else { f[tier] = true; }
    moRenderMatrix();
  }
  window.moMxToggleChip = moMxToggleChip;

  /* a stock row passes if, for every screen column that has an active
     filter set, the stock's tier for that column is one of the selected
     tiers (OR within a column). Columns with no active filter pass freely
     (AND across columns). */
  function moMxRowPasses(md) {
    for (var r = 0; r < MO_ROWS.length; r++) {
      var row = MO_ROWS[r];
      var f = moMxFilters[row.key];
      if (!f) continue;
      var keys = [];
      for (var kk in f) { if (f.hasOwnProperty(kk) && f[kk]) keys.push(kk); }
      if (keys.length === 0) continue;
      var tier = moNormaliseTier(moReadRating(md, row.ratingPath));
      var hit = false;
      for (var j = 0; j < keys.length; j++) { if (keys[j] === tier) { hit = true; break; } }
      if (!hit) return false;
    }
    return true;
  }

  function moMxAnyFilterActive() {
    for (var k in moMxFilters) {
      if (!moMxFilters.hasOwnProperty(k)) continue;
      var f = moMxFilters[k];
      for (var t in f) { if (f.hasOwnProperty(t) && f[t]) return true; }
    }
    return false;
  }

  /* build the three sticky header rows once (chip row, section-group row,
     column-title row). Called on first render; chip on/off state is
     repainted every render by moMxPaintChips(). */
  function moMxBuildHead(thead) {
    /* --- chip row --- */
    var chipTr = '<tr class="mo-mx-chip-row">' +
      '<th class="mo-mx-corner mo-mx-screen-col"><span class="mo-mx-corner-lbl">Filters &#8595;</span></th>';
    for (var c = 0; c < MO_ROWS.length; c++) {
      var rk = MO_ROWS[c].key;
      chipTr += '<th><div class="mo-mx-chip-stack">';
      for (var ci = 0; ci < MO_MX_CHIPS.length; ci++) {
        var ch = MO_MX_CHIPS[ci];
        chipTr += '<button type="button" class="mo-mx-chip ' + ch.cls + '" ' +
          'data-mx-col="' + moMxAttr(rk) + '" data-mx-tier="' + ch.tier + '" ' +
          'onclick="moMxToggleChip(\'' + moMxAttr(rk) + '\',\'' + ch.tier + '\')" ' +
          'title="' + moMxAttr(MO_ROWS[c].label + ' - ' + ch.tier) + '">' + ch.short + '</button>';
      }
      chipTr += '</div></th>';
    }
    chipTr += '</tr>';

    /* --- section-group row: one cell per contiguous section run --- */
    var groupTr = '<tr class="mo-mx-group-row"><th class="mo-mx-corner mo-mx-screen-col"></th>';
    var gi = 0;
    while (gi < MO_ROWS.length) {
      var sec = MO_ROWS[gi].section;
      var span = 0;
      while (gi + span < MO_ROWS.length && MO_ROWS[gi + span].section === sec) span++;
      groupTr += '<th colspan="' + span + '" class="' + (MO_MX_GROUP_CLS[sec] || '') + '">' +
        moMxText(MO_MX_GROUP_LABEL[sec] || sec) + '</th>';
      gi += span;
    }
    groupTr += '</tr>';

    /* --- column-title row: one cell per screen, labels WRAP --- */
    var colTr = '<tr class="mo-mx-col-row"><th class="mo-mx-screen-col">Stock</th>';
    for (var t = 0; t < MO_ROWS.length; t++) {
      colTr += '<th title="' + moMxAttr(MO_ROWS[t].label) + '">' + moMxText(MO_ROWS[t].label) + '</th>';
    }
    colTr += '</tr>';

    thead.innerHTML = chipTr + groupTr + colTr;
  }

  /* repaint chip on/off classes from moMxFilters (state survives re-render). */
  function moMxPaintChips(thead) {
    var chips = thead.querySelectorAll('button.mo-mx-chip');
    for (var i = 0; i < chips.length; i++) {
      var btn = chips[i];
      var col = btn.getAttribute('data-mx-col');
      var tier = btn.getAttribute('data-mx-tier');
      var f = moMxFilters[col];
      var on = !!(f && f[tier]);
      btn.classList.toggle('mo-mx-chip-on', on);
    }
  }

  function moRenderMatrix() {
    var host = document.getElementById('tab-master_overview');
    if (!host) return;
    var wrap = host.querySelector('#mo-matrix-wrap');
    if (!wrap) {
      /* append the matrix scaffold AFTER the existing distribution table's
         .table-wrap. The existing scaffold is intro + controls + table. */
      wrap = document.createElement('div');
      wrap.id = 'mo-matrix-wrap';
      wrap.innerHTML =
        '<div id="mo-matrix-caption">Full rating matrix: every stock against every screen. ' +
        'Each cell is the stock\'s rating for that screen; &#8211; where it does not qualify. ' +
        'Use the chips above any column to filter - multiple chips in a column widen it, ' +
        'columns combine.</div>' +
        '<div class="table-wrap"><table class="data-table" id="mo-matrix-table">' +
        '<thead></thead><tbody id="mo-matrix-tbody"></tbody></table></div>' +
        '<div id="mo-matrix-foot"></div>';
      host.appendChild(wrap);
    }
    var table = wrap.querySelector('#mo-matrix-table');
    var thead = table ? table.querySelector('thead') : null;
    var tbody = wrap.querySelector('#mo-matrix-tbody');
    if (!thead || !tbody) return;
    if (!thead.querySelector('tr.mo-mx-chip-row')) moMxBuildHead(thead);
    moMxPaintChips(thead);

    /* the matrix renders ALL md_v2 stocks - scope toggle drives the
       distribution table only, per the Wave 3 spec. */
    var all = moGetRows();
    all.sort(function(a, b) {
      var an = (a.company || a.ticker).toLowerCase();
      var bn = (b.company || b.ticker).toLowerCase();
      return an < bn ? -1 : (an > bn ? 1 : 0);
    });

    var colCount = MO_ROWS.length + 1;
    var html = '';
    var shown = 0;
    for (var i = 0; i < all.length; i++) {
      var rec = all[i];
      var md = rec.md_v2;
      if (!moMxRowPasses(md)) continue;
      shown++;
      html += '<tr><td class="mo-mx-name-cell">' +
        '<span class="mo-mx-co">' + moMxText(rec.company || rec.ticker) + '</span>' +
        '<span class="mo-mx-tk">' + moMxText(rec.ticker) + '</span></td>';
      for (var r = 0; r < MO_ROWS.length; r++) {
        var tier = moNormaliseTier(moReadRating(md, MO_ROWS[r].ratingPath));
        if (tier === 'None') {
          html += '<td><span class="mo-mx-pill mo-mx-p-none">&#8211;</span></td>';
        } else {
          html += '<td><span class="mo-mx-pill ' + MO_MX_TIER_PILL[tier] + '">' + tier + '</span></td>';
        }
      }
      html += '</tr>';
    }
    if (shown === 0) {
      html = '<tr class="mo-mx-empty"><td colspan="' + colCount + '">' +
        'No stocks match the active column filters.</td></tr>';
    }
    tbody.innerHTML = html;

    var foot = wrap.querySelector('#mo-matrix-foot');
    if (foot) {
      if (moMxAnyFilterActive()) {
        foot.textContent = shown.toLocaleString('en-GB') + ' of ' +
          all.length.toLocaleString('en-GB') + ' stocks match the active column filters.';
      } else {
        foot.textContent = 'Showing all ' + all.length.toLocaleString('en-GB') + ' stocks.';
      }
    }
  }
  window.moRenderMatrix = moRenderMatrix;

  function renderMasterOverview() {
    moRenderTable();
    moRenderMatrix();
  }
  window.renderMasterOverview = renderMasterOverview;"""


def sha(b):
    return hashlib.md5(b).hexdigest()


def main():
    dry = "--dry-run" in sys.argv

    if not os.path.isfile(TARGET):
        print("ERROR: target not found: %s" % TARGET)
        return 1

    with open(TARGET, "r", encoding="utf-8") as fh:
        src = fh.read()

    print("Target : %s" % TARGET)
    print("Before : %d bytes, %d lines, md5 %s" % (len(src.encode("utf-8")), src.count("\n") + 1, sha(src.encode("utf-8"))))

    if MARKER in src:
        print("\nMARKER already present - patch is idempotent, nothing to do.")
        return 0

    # --- locate all three anchors before touching anything ---
    problems = []
    if CSS_END_ANCHOR not in src:
        problems.append("CSS end anchor not found: %s" % CSS_END_ANCHOR)
    elif src.count(CSS_END_ANCHOR) != 1:
        problems.append("CSS end anchor not unique (%d hits)" % src.count(CSS_END_ANCHOR))

    if MOGETROWS_ANCHOR not in src:
        problems.append("moGetRows anchor not found")
    elif src.count(MOGETROWS_ANCHOR) != 1:
        problems.append("moGetRows anchor not unique (%d hits)" % src.count(MOGETROWS_ANCHOR))

    if RENDER_ANCHOR not in src:
        problems.append("renderMasterOverview anchor not found")
    elif src.count(RENDER_ANCHOR) != 1:
        problems.append("renderMasterOverview anchor not unique (%d hits)" % src.count(RENDER_ANCHOR))

    if problems:
        print("\nABORT - anchor problems:")
        for p in problems:
            print("  - %s" % p)
        return 1

    out = src

    # --- edit (1): CSS injected immediately before the Wave 1 CSS end marker ---
    css_inject = CSS_BLOCK
    if not css_inject.endswith("\n"):
        css_inject += "\n"
    out = out.replace(CSS_END_ANCHOR, css_inject + CSS_END_ANCHOR, 1)

    # --- edit (2): moGetRows carries company name ---
    out = out.replace(MOGETROWS_ANCHOR, MOGETROWS_REPLACEMENT, 1)

    # --- edit (3): extend the Master Overview IIFE ---
    out = out.replace(RENDER_ANCHOR, JS_BLOCK, 1)

    # --- sanity checks on the result ---
    checks = []
    if out == src:
        checks.append("output identical to source - no edit applied")
    if out.count(MARKER) < 3:
        checks.append("expected >=3 MARKER occurrences, found %d" % out.count(MARKER))
    if "\x00" in out:
        checks.append("null byte present in output")
    if out.count(CSS_END_ANCHOR) != 1:
        checks.append("CSS end anchor count changed to %d" % out.count(CSS_END_ANCHOR))
    if "window.moRenderMatrix" not in out:
        checks.append("moRenderMatrix not exported in output")
    if "moRenderMatrix();" not in out:
        checks.append("renderMasterOverview does not call moRenderMatrix")
    if checks:
        print("\nABORT - post-edit sanity checks failed:")
        for c in checks:
            print("  - %s" % c)
        return 1

    out_bytes = out.encode("utf-8")
    print("After  : %d bytes, %d lines, md5 %s" % (len(out_bytes), out.count("\n") + 1, sha(out_bytes)))
    print("Delta  : +%d bytes, +%d lines" % (len(out_bytes) - len(src.encode("utf-8")), out.count("\n") - src.count("\n")))

    if dry:
        dest = os.path.join(SCRIPT_DIR, "build_dashboard.py.wave3-patched")
        tmp = dest + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="") as fh:
            fh.write(out)
        os.replace(tmp, dest)
        print("\nDRY-RUN: wrote patched copy to %s" % dest)
        print("Source UNCHANGED. Inspect / node --check, then re-run without --dry-run.")
        return 0

    # atomic write into place
    tmp = TARGET + ".wave3.tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as fh:
        fh.write(out)
    os.replace(tmp, TARGET)

    with open(TARGET, "r", encoding="utf-8") as fh:
        verify = fh.read()
    print("\nPATCHED in place. Re-read md5 %s (%d bytes)" % (sha(verify.encode("utf-8")), len(verify.encode("utf-8"))))
    if verify != out:
        print("WARNING: re-read does not match intended output - investigate before committing.")
        return 1
    print("OK - re-read matches intended output.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
