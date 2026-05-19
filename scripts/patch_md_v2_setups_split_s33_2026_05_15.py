#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# patch_md_v2_setups_split_s33_2026_05_15.py
# =============================================================================
# MD V2 Master Dashboard - Session 33 (15-May-26)
# Splits the single "Capital qualification setups" tab (id: setups) into TWO tabs:
#   setups_s1pb   "Stage 1 and Stage N PBs"     -> probing_bet, vcp_after_s1_plateau
#   setups_s2vcp  "Stage 2 VCPs and retests"    -> healthy_retest, vcp_after_s2_base
# Reason (Richard's brief): the single tab has too many columns.
#
# Design: the ~745-line setups module is rewritten in place to be tab-parameterised
# - one shared renderer driven by a per-tab context object (stCur). No per-tab
# bespoke code; honours Invariant 8 (shared base renderer).
#
# Discipline:
#  - Reads SOURCE from `git show HEAD:scripts/build_dashboard.py` (git object store,
#    immune to the COWORK FUSE stale-cache bug). Never reads the working-tree file.
#  - Idempotent: exits 0 if MARKER already present.
#  - Safety gate: aborts if the working-tree build_dashboard.py differs from HEAD
#    and the marker is absent (unexpected state - resolve before patching).
#  - Every anchor edit asserts an exact occurrence count; any miss aborts the run.
#  - py_compile validates the result before it is written.
#  - Backs up the working-tree file to .bak-pre-setups-split-s33-<ts> first.
#
# Usage:
#   python scripts/patch_md_v2_setups_split_s33_2026_05_15.py
#   python scripts/patch_md_v2_setups_split_s33_2026_05_15.py --test SRC OUT
# =============================================================================
import sys, os, re, subprocess, hashlib, py_compile, datetime

MARKER    = "MD-V2-SETUPS-SPLIT-S33-MARKER"
MOD_START = "/* MD-V2-SETUPS-MARKER-MODULE-START */"
MOD_END   = "/* MD-V2-SETUPS-MARKER-MODULE-END */"
TARGET    = os.path.join("scripts", "build_dashboard.py")


def _rep(s, old, new, count, label):
    c = s.count(old)
    if c != count:
        raise AssertionError("[%s] expected %d occurrence(s), found %d -- anchor: %r"
                             % (label, count, c, old[:90]))
    return s.replace(old, new)


# ----------------------------------------------------------------------------
# JS inserted just after the `var ST_CHIP = {...};` line: per-tab definitions,
# the pattern-subset helper, the per-tab context map, and the stCur pointer.
# ----------------------------------------------------------------------------
INSERT_TABDEFS = """

  // MD-V2-SETUPS-SPLIT-S33-MARKER: the single "Capital qualification setups" tab
  // is split into two tabs, each rendering a 2-pattern subset. The renderer below
  // is fully shared - it reads the active tab's context (patterns, columns,
  // element ids, intro) from stCur.
  var ST_TAB_DEFS = [
    {
      tabId: 'setups_s1pb',
      patternKeys: ['probing_bet', 'vcp_after_s1_plateau'],
      intro: 'Stage 1 and Stage N probing-bet setups - the probing bet and the VCP after a Stage 1-to-2 plateau. Each setup is the AND of its named constituent tests, shown as individual tick columns alongside a per-pattern rating and score. Each tile has a rating-tier filter row: click a tier chip to show only stocks at that tier, or click the tile body to select all tiers. Tier selections within a setup combine as OR; selections across setups combine as AND.'
    },
    {
      tabId: 'setups_s2vcp',
      patternKeys: ['healthy_retest', 'vcp_after_s2_base'],
      intro: 'Stage 2 VCP and retest setups - the healthy retest within a medium or long-term uptrend and the VCP after a Stage 2 base. Each setup is the AND of its named constituent tests, shown as individual tick columns alongside a per-pattern rating and score. Each tile has a rating-tier filter row: click a tier chip to show only stocks at that tier, or click the tile body to select all tiers. Tier selections within a setup combine as OR; selections across setups combine as AND.'
    }
  ];
  function stPatternsForKeys(keys) {
    var out = [];
    for (var _k = 0; _k < keys.length; _k++) {
      for (var _p = 0; _p < ST_PATTERNS_ALL.length; _p++) {
        if (ST_PATTERNS_ALL[_p].key === keys[_k]) { out.push(ST_PATTERNS_ALL[_p]); break; }
      }
    }
    return out;
  }
  var ST_CTX = {};
  for (var _ic = 0; _ic < ST_TAB_DEFS.length; _ic++) {
    var _td = ST_TAB_DEFS[_ic];
    ST_CTX[_td.tabId] = {
      tabId:    _td.tabId,
      hostId:   'tab-' + _td.tabId,
      idp:      _td.tabId,
      patterns: stPatternsForKeys(_td.patternKeys),
      intro:    _td.intro,
      cols:     null,
      sort:     null
    };
  }
  var stCur = null;"""


# ----------------------------------------------------------------------------
# JS that replaces the old single `renderSetups()` function + its window export.
# ----------------------------------------------------------------------------
INSERT_RENDER = """  // MD-V2-SETUPS-SPLIT-S33-MARKER: control-bar state is shared across both setups
  // tabs; stSyncControls re-syncs a freshly-built tab's buttons to stState.
  function stSyncControls() {
    var gb = document.querySelectorAll('button[data-st-grp]');
    for (var i = 0; i < gb.length; i++) {
      var g = gb[i].getAttribute('data-st-grp');
      gb[i].classList.toggle('active', gb[i].getAttribute('data-st-val') === stState.mode[g]);
    }
    function syncAttr(attr, val) {
      var b = document.querySelectorAll('button[' + attr + ']');
      for (var k = 0; k < b.length; k++)
        b[k].classList.toggle('active', b[k].getAttribute(attr) === val);
    }
    syncAttr('data-st-scope', stState.scope);
    syncAttr('data-st-tint',  stState.tint);
    syncAttr('data-st-port',  stState.port);
  }
  // Resolve the active tab's render context into stCur. Cheap and idempotent.
  function stResolveCtx(tabId) {
    stCur = ST_CTX[tabId];
    if (!stCur) return false;
    if (!stCur.cols) stCur.cols = stBuildCols();
    stCur.sort = stState.sortByTab[tabId];
    return true;
  }
  // Event handlers can fire without a renderTab call when switchTab serves a
  // cached tab; stEnsureCur points stCur at whichever setups tab is active.
  function stEnsureCur() {
    var active = document.body.getAttribute('data-active-tab') || '';
    if (ST_CTX[active]) stResolveCtx(active);
  }
  function stRenderActive() {
    if (!stCur) return;
    if (!stBuildScaffold()) return;
    stSyncControls();
    stBuildHeaderRow();
    stRenderRows();
    if (window.measureV2Ribbon) measureV2Ribbon();  /* MD-V2-WAVE1B-STICKY-CORRECTIVE-MARKER */
  }
  // MD-V2-MDJUMP-CONSUMER-S27-MARKER: Master Overview cell-click handoff. Read
  // window._mdJump once; if it targets this tab, arm the chip filter for the
  // named pattern, then clear it so it fires exactly once.
  function stRenderTab(tabId) {
    if (!stResolveCtx(tabId)) return;
    var j = window._mdJump;
    if (j && j.tab === tabId) {
      if (j.patternKey && j.tier && stState.tierFilter &&
          stState.tierFilter.hasOwnProperty(j.patternKey)) {
        stState.tierFilter[j.patternKey] = [j.tier];
      }
      window._mdJump = null;
    }
    stRenderActive();
  }
  function renderSetupsS1PB()  { stRenderTab('setups_s1pb'); }
  function renderSetupsS2VCP() { stRenderTab('setups_s2vcp'); }
  window.renderSetupsS1PB  = renderSetupsS1PB;
  window.renderSetupsS2VCP = renderSetupsS2VCP;"""


def transform_module(mod):
    """Rewrite the extracted setups module block to be tab-parameterised."""

    # M1: drop the top-level `var ST_COLS = stBuildCols();` line (cols are now
    # built per-tab into stCur.cols).
    mod = _rep(mod, "\n  var ST_COLS = stBuildCols();\n", "\n", 1, "M1 ST_COLS decl")

    # M2: remaining ST_COLS references -> stCur.cols (stBuildHeaderRow + stRenderRows)
    mod, c = re.subn(r"\bST_COLS\b", "stCur.cols", mod)
    assert c == 4, "M2 ST_COLS refs: expected 4, found %d" % c

    # M3: rename the pattern array declaration.
    mod = _rep(mod, "  var ST_PATTERNS = [", "  var ST_PATTERNS_ALL = [",
               1, "M3 ST_PATTERNS decl")

    # M4: tierFilter init loop -> ST_PATTERNS_ALL, and append per-tab sort init.
    old_init = ("  // init tierFilter keyed by pattern\n"
                "  for (var _ip = 0; _ip < ST_PATTERNS.length; _ip++) {\n"
                "    stState.tierFilter[ST_PATTERNS[_ip].key] = [];\n"
                "  }\n")
    new_init = ("  // init tierFilter keyed by pattern (all patterns, both tabs)\n"
                "  for (var _ip = 0; _ip < ST_PATTERNS_ALL.length; _ip++) {\n"
                "    stState.tierFilter[ST_PATTERNS_ALL[_ip].key] = [];\n"
                "  }\n"
                "  // MD-V2-SETUPS-SPLIT-S33-MARKER: per-tab sort state\n"
                "  for (var _it = 0; _it < ST_TAB_DEFS.length; _it++) {\n"
                "    stState.sortByTab[ST_TAB_DEFS[_it].tabId] = { col: 'company', dir: 'asc' };\n"
                "  }\n")
    mod = _rep(mod, old_init, new_init, 1, "M4 tierFilter init")

    # M5: stSelectAllTiers pattern lookup -> ST_PATTERNS_ALL
    old_sel = ("    for (var p = 0; p < ST_PATTERNS.length; p++) "
               "if (ST_PATTERNS[p].key === patternKey) pat = ST_PATTERNS[p];")
    new_sel = ("    for (var p = 0; p < ST_PATTERNS_ALL.length; p++) "
               "if (ST_PATTERNS_ALL[p].key === patternKey) pat = ST_PATTERNS_ALL[p];")
    mod = _rep(mod, old_sel, new_sel, 1, "M5 stSelectAllTiers")

    # M6: every remaining bare ST_PATTERNS -> stCur.patterns  (\b excludes _ALL)
    mod, c = re.subn(r"\bST_PATTERNS\b", "stCur.patterns", mod)
    assert c == 18, "M6 ST_PATTERNS residual: expected 18, found %d" % c

    # M7: stState - per-tab sort.
    mod = _rep(mod,
               "    sort: { col: 'company', dir: 'asc' }\n  };",
               "    sortByTab: {}\n  };",
               1, "M7 stState.sort")

    # M8: insert per-tab defs / context after the ST_CHIP line.
    st_chip = ('  var ST_CHIP = {"probing_bet": "pullback", '
               '"vcp_after_s1_plateau": "basing", '
               '"healthy_retest": "collapsing", "vcp_after_s2_base": "amber"};')
    mod = _rep(mod, st_chip, st_chip + INSERT_TABDEFS, 1, "M8 ST_CHIP insert")

    # M9: stOnSort rewritten to mutate the active tab's sort object in place.
    old_onsort = ("  function stOnSort(key) {\n"
                  "    if (stState.sort.col === key) stState.sort.dir = stState.sort.dir === 'desc' ? 'asc' : 'desc';\n"
                  "    else stState.sort = { col: key, dir: key === 'company' ? 'asc' : 'desc' };\n"
                  "    stBuildHeaderRow();\n"
                  "    stRenderRows();\n"
                  "  }\n")
    new_onsort = ("  function stOnSort(key) {\n"
                  "    stEnsureCur();\n"
                  "    var srt = stCur.sort;\n"
                  "    if (srt.col === key) srt.dir = srt.dir === 'desc' ? 'asc' : 'desc';\n"
                  "    else { srt.col = key; srt.dir = key === 'company' ? 'asc' : 'desc'; }\n"
                  "    stBuildHeaderRow();\n"
                  "    stRenderRows();\n"
                  "  }\n")
    mod = _rep(mod, old_onsort, new_onsort, 1, "M9 stOnSort")

    # M10: remaining stState.sort -> stCur.sort  (\b excludes stState.sortByTab)
    mod, c = re.subn(r"\bstState\.sort\b", "stCur.sort", mod)
    assert c == 5, "M10 stState.sort residual: expected 5, found %d" % c

    # M11: element-id strings -> per-tab ids resolved from stCur.
    # 11a. getElementById(...) call sites
    mod = _rep(mod, "document.getElementById('st-col-header-row')",
               "document.getElementById(stCur.idp + '-col-header-row')",
               2, "M11a col-header-row getter")
    mod = _rep(mod, "document.getElementById('st-pattern-tiles')",
               "document.getElementById(stCur.idp + '-pattern-tiles')",
               2, "M11b pattern-tiles getter")
    mod = _rep(mod, "document.getElementById('st-tbody')",
               "document.getElementById(stCur.idp + '-tbody')",
               1, "M11c tbody getter")
    mod = _rep(mod, "var host = document.getElementById('tab-setups');",
               "var host = document.getElementById(stCur.hostId);",
               1, "M11d host getter")
    mod = _rep(mod, "if (host.querySelector('#st-main-table')) return true;",
               "if (host.querySelector('.st-main-table')) return true;",
               1, "M11e scaffold-exists check")
    # 11f. stUpdateScopeCounts set(...) call sites
    for suf in ("all", "live", "sector", "industry"):
        mod = _rep(mod, "set('st-cnt-%s'," % suf,
                   "set(stCur.idp + '-cnt-%s'," % suf,
                   1, "M11f set st-cnt-%s" % suf)
    # 11g. scaffold HTML id="" attributes (split the JS string to inject stCur.idp)
    for suf in ("col-header-row", "cnt-all", "cnt-live", "cnt-sector",
                "cnt-industry", "pattern-tiles", "tbody"):
        old_id = 'id="st-%s"' % suf
        new_id = "id=\"' + stCur.idp + '-%s\"" % suf
        mod = _rep(mod, old_id, new_id, 1, "M11g id=%s" % suf)
    # 11h. the main table: keep CSS hook as a class, make the id per-tab.
    mod = _rep(mod,
               'class="data-table" id="st-main-table"',
               "class=\"data-table st-main-table\" id=\"' + stCur.idp + '-main-table\"",
               1, "M11h main-table id+class")

    # M12: scaffold intro text -> per-tab intro from stCur.
    old_intro = ("      '<div class=\"s1-intro\">Capital qualification setups sit on top "
                 "of the indicators - each one says a stock looks ready for you to "
                 "consider deploying capital. Each setup is the AND of its named "
                 "constituent tests, shown as individual tick columns alongside a "
                 "per-pattern rating and score. Each tile has a rating-tier filter "
                 "row: click a tier chip to show only stocks at that tier, or click "
                 "the tile body to select all tiers. Tier selections within a setup "
                 "combine as OR; selections across setups combine as AND.</div>' +")
    new_intro = "      '<div class=\"s1-intro\">' + stCur.intro + '</div>' +"
    mod = _rep(mod, old_intro, new_intro, 1, "M12 intro text")

    # M13: stEnsureCur() guard at the top of each event-handler entry point.
    mod = _rep(mod,
               "  function stSetMode(kind, val) {\n    stState.mode[kind] = val;",
               "  function stSetMode(kind, val) {\n    stEnsureCur();\n    stState.mode[kind] = val;",
               1, "M13a stSetMode")
    mod = _rep(mod,
               "  function stSetScope(s) {\n    stState.scope = s;",
               "  function stSetScope(s) {\n    stEnsureCur();\n    stState.scope = s;",
               1, "M13b stSetScope")
    mod = _rep(mod,
               "  function stSetTint(t) {\n    stState.tint = t;",
               "  function stSetTint(t) {\n    stEnsureCur();\n    stState.tint = t;",
               1, "M13c stSetTint")
    mod = _rep(mod,
               "  function stSetPort(p) {\n    stState.port = p;",
               "  function stSetPort(p) {\n    stEnsureCur();\n    stState.port = p;",
               1, "M13d stSetPort")
    mod = _rep(mod,
               "  function stToggleTier(patternKey, tier) {\n    var sel = stState.tierFilter[patternKey] || [];",
               "  function stToggleTier(patternKey, tier) {\n    stEnsureCur();\n    var sel = stState.tierFilter[patternKey] || [];",
               1, "M13e stToggleTier")
    mod = _rep(mod,
               "  function stSelectAllTiers(patternKey) {\n    // MD-V2-WAVE1-FROZEN-HEADERS-MARKER:",
               "  function stSelectAllTiers(patternKey) {\n    stEnsureCur();\n    // MD-V2-WAVE1-FROZEN-HEADERS-MARKER:",
               1, "M13f stSelectAllTiers")

    # M14: replace renderSetups() + its window export with the new entry points.
    old_render_start = "  function renderSetups() {"
    idx = mod.index(old_render_start)
    end_anchor = "  window.renderSetups = renderSetups;"
    end_idx = mod.index(end_anchor) + len(end_anchor)
    mod = mod[:idx] + INSERT_RENDER + mod[end_idx:]
    assert "function renderSetups(" not in mod, "M14: stray renderSetups remains"
    assert "renderSetupsS1PB" in mod and "renderSetupsS2VCP" in mod, "M14: new entries missing"

    return mod


def transform(src):
    """Apply the full set of edits to a clean HEAD copy of build_dashboard.py."""
    if MARKER in src:
        raise AssertionError("MARKER already present in source -- already patched?")

    # --- the module rewrite ---
    i = src.index(MOD_START)
    j = src.index(MOD_END) + len(MOD_END)
    src = src[:i] + transform_module(src[i:j]) + src[j:]

    # --- EDIT 1: TABS array ---
    src = _rep(src,
        '    {"id": "setups", "label": "Setups", "accent": "#BA7517"},',
        '    {"id": "setups_s1pb", "label": "Stage 1 and Stage N PBs", "accent": "#BA7517"},\n'
        '    {"id": "setups_s2vcp", "label": "Stage 2 VCPs and retests", "accent": "#BA7517"},',
        1, "E1 TABS array")

    # --- EDIT 2: IMPLEMENTED_TABS ---
    src = _rep(src,
        '    "setups",  # MD-V2-SETUPS-MARKER',
        '    "setups_s1pb", "setups_s2vcp",  # MD-V2-SETUPS-MARKER',
        1, "E2 IMPLEMENTED_TABS")

    # --- EDIT 3: chart-enabled V2 tab sets (_v2chartTabs + _v2ct) ---
    src = _rep(src, "setups:1,tests:1",
               "setups_s1pb:1,setups_s2vcp:1,tests:1", 2, "E3 v2 chart tab sets")

    # --- EDIT 4: measureV2Ribbon V2-tab test ---
    src = _rep(src,
        "active === 'post_indicators' || active === 'setups' ||",
        "active === 'post_indicators' || active.indexOf('setups') === 0 ||",
        1, "E4 measureV2Ribbon")

    # --- EDIT 5: v2-nav button (one -> two) ---
    e5_old = (r"""      + '<button class="v2-nav-btn v2-grp-setups" data-v2-tab="setups" onclick="switchTab(\'setups\')">Capital qualification setups</button>'""")
    e5_new = (r"""      + '<button class="v2-nav-btn v2-grp-setups" data-v2-tab="setups_s1pb" onclick="switchTab(\'setups_s1pb\')">Stage 1 and Stage N PBs</button>'
      + '<button class="v2-nav-btn v2-grp-setups" data-v2-tab="setups_s2vcp" onclick="switchTab(\'setups_s2vcp\')">Stage 2 VCPs and retests</button>'""")
    src = _rep(src, e5_old, e5_new, 1, "E5 v2-nav button")

    # --- EDIT 6: renderTab dispatch ---
    src = _rep(src,
        '  else if(id==="setups")renderSetups();  /* MD-V2-SETUPS-MARKER */',
        '  else if(id==="setups_s1pb")renderSetupsS1PB();  /* MD-V2-SETUPS-MARKER */\n'
        '  else if(id==="setups_s2vcp")renderSetupsS2VCP();  /* MD-V2-SETUPS-MARKER */',
        1, "E6 renderTab dispatch")

    # --- EDIT 7: Master Overview list -> per-pattern tabId ---
    src = _rep(src, "tabId:'setups', patternKey:'probing_bet'",
               "tabId:'setups_s1pb', patternKey:'probing_bet'", 1, "E7a MO probing_bet")
    src = _rep(src, "tabId:'setups', patternKey:'vcp_after_s1_plateau'",
               "tabId:'setups_s1pb', patternKey:'vcp_after_s1_plateau'", 1, "E7b MO vcp_s1")
    src = _rep(src, "tabId:'setups', patternKey:'healthy_retest'",
               "tabId:'setups_s2vcp', patternKey:'healthy_retest'", 1, "E7c MO healthy_retest")
    src = _rep(src, "tabId:'setups', patternKey:'vcp_after_s2_base'",
               "tabId:'setups_s2vcp', patternKey:'vcp_after_s2_base'", 1, "E7d MO vcp_s2")

    # --- EDIT 8: rating-tile / caption grids 3-col -> 2-col (each tab has 2 tiles) ---
    src = _rep(src,
        "#tab-setups .group-captions { display: grid; grid-template-columns: repeat(3, 1fr);",
        "#tab-setups .group-captions { display: grid; grid-template-columns: repeat(2, 1fr);",
        1, "E8a captions grid")
    src = _rep(src,
        "#tab-setups .s1-rating-tiles { display: grid; grid-template-columns: repeat(3, 1fr);",
        "#tab-setups .s1-rating-tiles { display: grid; grid-template-columns: repeat(2, 1fr);",
        1, "E8b tiles grid")

    # --- EDIT 9: CSS - #tab-setups -> [id^="tab-setups"] (matches both new hosts) ---
    n = src.count("#tab-setups")
    assert n == 41, "E9 #tab-setups: expected 41, found %d" % n
    src = src.replace("#tab-setups", '[id^="tab-setups"]')
    assert src.count("#tab-setups") == 0, "E9 residual #tab-setups"

    # --- EDIT 10: CSS - data-active-tab="setups" -> ^="setups" (matches both) ---
    n = src.count('data-active-tab="setups"')
    assert n == 12, 'E10 data-active-tab="setups": expected 12, found %d' % n
    src = src.replace('data-active-tab="setups"', 'data-active-tab^="setups"')
    assert src.count('data-active-tab="setups"') == 0, "E10 residual"

    # --- EDIT 11: CSS - #st-main-table -> .st-main-table (table now carries the class) ---
    # 73 occurrences in HEAD; the module's single querySelector('#st-main-table')
    # was already converted to '.st-main-table' by M11e, leaving 72 (all CSS).
    n = src.count("#st-main-table")
    assert n == 72, "E11 #st-main-table: expected 72, found %d" % n
    src = src.replace("#st-main-table", ".st-main-table")
    assert src.count("#st-main-table") == 0, "E11 residual #st-main-table"

    # --- final integrity assertions ---
    assert MARKER in src, "MARKER missing from output"
    assert src.count('"id": "setups_s1pb"') == 1 and src.count('"id": "setups_s2vcp"') == 1
    assert "renderSetups()" not in src, "stray renderSetups() call remains"
    assert "renderSetupsS1PB" in src and "renderSetupsS2VCP" in src
    return src


def _git_head_source():
    out = subprocess.check_output(
        ["git", "show", "HEAD:scripts/build_dashboard.py"])
    return out.decode("utf-8")


def main(argv):
    # ---- test mode: transform a given file, write output, compile-check ----
    if len(argv) >= 1 and argv[0] == "--test":
        src_path, out_path = argv[1], argv[2]
        with open(src_path, "r", encoding="utf-8") as f:
            src = f.read()
        out = transform(src)
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(out)
        py_compile.compile(out_path, doraise=True)
        print("[--test] OK  in=%d bytes  out=%d bytes  -> %s"
              % (len(src), len(out), out_path))
        return 0

    # ---- production mode ----
    if not os.path.isfile(TARGET):
        print("ERROR: run from the master-dashboard repo root (scripts/build_dashboard.py not found).")
        return 2

    with open(TARGET, "r", encoding="utf-8", errors="replace") as f:
        wt = f.read()
    if MARKER in wt:
        print("Already patched (MARKER present in working tree). Nothing to do.")
        return 0

    head_src = _git_head_source()
    wt_md5, head_md5 = (hashlib.md5(wt.encode("utf-8", "replace")).hexdigest(),
                        hashlib.md5(head_src.encode("utf-8")).hexdigest())
    if wt_md5 != head_md5:
        print("ABORT: working-tree build_dashboard.py does not match HEAD and the")
        print("       S33 marker is absent. Unexpected state -- resolve before patching.")
        print("       working-tree md5: %s" % wt_md5)
        print("       HEAD         md5: %s" % head_md5)
        print("       (If HEAD is clean, run `git checkout -- scripts/build_dashboard.py` first.)")
        return 3

    out = transform(head_src)

    # backup the working-tree file, then write.
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = TARGET + ".bak-pre-setups-split-s33-" + ts
    with open(bak, "w", encoding="utf-8") as f:
        f.write(wt)
    tmp = TARGET + ".tmp-s33"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(out)
    py_compile.compile(tmp, doraise=True)
    os.replace(tmp, TARGET)

    print("OK: setups tab split applied.")
    print("    backup : %s" % bak)
    print("    target : %s  (%d -> %d bytes)" % (TARGET, len(head_src), len(out)))
    print("    next   : python scripts/build_dashboard.py  ->  git add -A  ->  commit  ->  push")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
