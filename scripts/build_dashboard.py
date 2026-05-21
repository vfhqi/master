"""
Master Dashboard -- HTML Builder (Phase 4 + 16-Fix Rewrite)
==========================================================
Generates index.html with all technical tabs + SSEM + Valuation.
Implements FIX-1 through FIX-16 from 23-Apr-26 V3 review.

NO ES6 in output: var, function(){}, string concatenation only.
No const, let, arrow functions, template literals, spread operators.

Usage:
  python build_dashboard.py
"""

import json
import os
import shutil
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
PROJECT_DIR = SCRIPT_DIR.parent
DATA_DIR = PROJECT_DIR / "data"
OUTPUT_PATH = PROJECT_DIR / "index.html"

COWORK_ROOT = PROJECT_DIR.parent
POSITIONS_PATH = COWORK_ROOT / "positions.json"


def safe_json_load(path):
    """Load JSON, handling files with multiple concatenated docs."""
    with open(path) as f:
        content = f.read()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        dec = json.JSONDecoder()
        obj, _ = dec.raw_decode(content)
        return obj


def load_data():
    prices = safe_json_load(DATA_DIR / "prices.json")
    filters = safe_json_load(DATA_DIR / "filter-results.json")

    # CHANGES tab: historical stage data (D-MD-UI-19)
    filter_history = None
    fh_path = DATA_DIR / "filter-history.json"
    if fh_path.exists():
        filter_history = safe_json_load(fh_path)
    universe = safe_json_load(DATA_DIR / "universe.json")
    # Canonical taxonomy: prefer stock_mapping_final.json (full universe coverage).
    # Falls back to legacy ticker_mapping.json (29-stock crosswalk) only if canonical absent.
    sm_path = COWORK_ROOT / "stock_mapping_final.json"
    if sm_path.exists():
        sm_raw = safe_json_load(sm_path)
        ticker_mapping = {"stocks": {}}
        for tk, td in sm_raw.items():
            if isinstance(td, dict) and td.get("new_industry"):
                ticker_mapping["stocks"][tk] = {
                    "industry": td["new_industry"],
                    "sector":   td["new_sector"],
                }
        print(f"  Loaded canonical taxonomy: {len(ticker_mapping['stocks'])} entries from stock_mapping_final.json")
    else:
        ticker_mapping = safe_json_load(DATA_DIR / "ticker_mapping.json")
        print(f"  WARNING: stock_mapping_final.json not found, using legacy ticker_mapping.json ({len(ticker_mapping.get('stocks',{}))} entries)")

    # SSEM
    ssem = None
    ssem_path = DATA_DIR / "factset-ssem.json"
    if ssem_path.exists():
        ssem = safe_json_load(ssem_path)

    # Valuation
    valuation = None
    val_path = DATA_DIR / "factset-valuation.json"
    if val_path.exists():
        valuation = safe_json_load(val_path)

    # Positions
    positions = None
    if POSITIONS_PATH.exists():
        positions = safe_json_load(POSITIONS_PATH)

    # MD-V2-S36-BRIEF-MARKER: universe_updated = mtime of data/universe.json,
    # formatted as 'YYYY-MM-DD HH:MM'. The file has no _meta field, so we use mtime.
    try:
        _u_mtime = (DATA_DIR / "universe.json").stat().st_mtime
        _universe_updated = datetime.fromtimestamp(_u_mtime).strftime("%Y-%m-%d %H:%M")
    except Exception:
        _universe_updated = "—"
    master = {
        "meta": {
            "generated": prices["_meta"]["generated"],
            "source": prices["_meta"]["source"],
            "stock_count": prices["_meta"]["count"],
            "universe_updated": _universe_updated,
        },
        "universe": universe["stocks"],
        "prices": prices["stocks"],
        "filters": filters["stocks"],
        "ticker_mapping": ticker_mapping["stocks"],
    }
    if positions:
        master["positions"] = positions
    if ssem:
        ssem_data = {k: v for k, v in ssem.items() if k != "_meta"}
        master["ssem"] = ssem_data
    if valuation:
        val_data = {k: v for k, v in valuation.items() if k != "_meta"}
        master["valuation"] = val_data
    if filter_history:
        master["filter_history"] = filter_history

    # Qualitative ratings (from IC Ratings Dashboard memos)
    qual_path = DATA_DIR / "qualitative.json"
    if qual_path.exists():
        qual = safe_json_load(qual_path)
        master["qualitative"] = qual

    data_js = "var MASTER_DATA = " + json.dumps(master, separators=(",", ":")) + ";\n"

    # Chart data is NO LONGER embedded — lazy-loaded from charts/<TICKER>.js files
    # (was 185MB+ embedded, now ~200KB per ticker loaded on demand)
    data_js += "var CHART_DATA = {};\n"  # kept for backward compat — empty object
    data_js += "var CHART_REGISTRY = {};\n"
    data_js += "var PB_STAGEINFO_COUNT = 0;\n"  # referenced by SB and HVCP modules  # global so lazy-loaded chart files can register into it
    # S59: RDS_INDEX — most recent Developments Summariser date per ticker (embedded at patch time)
    data_js += 'var RDS_INDEX = {"AAF-GB":"2026-05-16","AKTR-GR":"2026-05-16","ALC":"2026-05-15","ALFEN-NL":"2026-05-16","ANOD.B":"2026-05-15","BARC-GB":"2026-05-16","BBY-GB":"2026-05-16","BG-AT":"2026-05-16","BRKN-CH":"2026-05-16","BUFAB-SE":"2026-05-16","CAF-ES":"2026-05-16","CEVI":"2026-05-15","CKN-GB":"2026-05-16","DANSKE-DK":"2026-05-16","DEC-FR":"2026-05-16","DHER":"2026-05-15","DHL-DE":"2026-05-16","DPLM-GB":"2026-05-16","EDP-PT":"2026-05-16","EDPR-PT":"2026-05-16","ELI-BE":"2026-05-16","EMSN-CH":"2026-05-16","ENEL-IT":"2026-05-16","ENG-PL":"2026-05-16","ENX-FR":"2026-05-16","EVN-AT":"2026-05-16","FORTUM-FI":"2026-05-16","FQT-AT":"2026-05-16","GALD-CH":"2026-05-16","GAW-GB":"2026-05-16","GEST-ES":"2026-05-16","GET-FR":"2026-05-16","HILS-GB":"2026-05-16","HOC-GB":"2026-05-16","HOLN-CH":"2026-05-16","HSX-GB":"2026-05-15","IBE-ES":"2026-05-16","III-GB":"2026-05-15","INCH-GB":"2026-05-16","INDT":"2026-05-15","IPN-FR":"2026-05-16","ITV-GB":"2026-05-16","KAMBI-SE":"2026-05-16","KWS-DE":"2026-05-16","LI-FR":"2026-05-16","MAIRE-IT":"2026-05-16","MOL-HU":"2026-05-16","MRL-ES":"2026-05-16","MVC-ES":"2026-05-16","NETC-DK":"2026-05-16","OHB-DE":"2026-05-15","ORSTED-DK":"2026-05-17","RHM":"2026-05-15","ROSE-GB":"2026-05-17","ROVI-ES":"2026-05-15","RUI-FR":"2026-05-17","RWE-DE":"2026-05-16","SAVE-SE":"2026-05-17","SCYR-ES":"2026-05-17","SEE-GB":"2026-05-16","SEM-PT":"2026-05-17","SFER-IT":"2026-05-17","SLR-ES":"2026-05-17","SMWH-GB":"2026-05-15","SOLB-BE":"2026-05-17","SSE-GB":"2026-05-16","SU-FR":"2026-05-16","SWED-SE":"2026-05-16","TATE-GB":"2026-05-16","TEMN-CH":"2026-05-17","TEP":"2026-05-15","TPRO-IT":"2026-05-15","TRE-ES":"2026-05-16","TRST-GB":"2026-05-17","UIE-DK":"2026-05-17","UNI-IT":"2026-05-17","VIE-FR":"2026-05-16","VIMIAN-SE":"2026-05-17","VIO-BE":"2026-05-15","VIRP-FR":"2026-05-17","VWS-DK":"2026-05-16","WOSG-GB":"2026-05-15","ZEG-GB":"2026-05-17"};\n'

    return data_js


# FIX-6: Each tab gets a unique accent colour
# Tab order: Group 1 = Technical filters, Group 2 = Data/Reference
TABS = [
    # STAGE-REFACTOR-V3-MARKER — 8 filter tabs grouped by Minervini-style stage
    # Stage 1 — Basing/bottoming
    {"id": "bp",        "label": "Basing Plateau",   "accent": "#276749", "stage": 1},
    {"id": "pb",        "label": "Probing Bet",      "accent": "#6b46c1", "stage": 1},
    # Stage 2 — Markup/breakout
    {"id": "vcp",       "label": "VCP",              "accent": "#9c4221", "stage": 2},
    {"id": "mm99",      "label": "MM 99",            "accent": "#1b3d5c", "stage": 2},
    {"id": "utr",       "label": "Uptrend Retest",   "accent": "#744210", "stage": 2},
    # Stage 3 — Topping (placeholder)
    {"id": "s3_topping",   "label": "Topping",       "accent": "#b45309", "stage": 3, "placeholder": True},
    # Stage 4 — Decline/capitulation (placeholders)
    {"id": "s4_declining", "label": "Declining",     "accent": "#991b1b", "stage": 4, "placeholder": True},
    {"id": "collapse",     "label": "Collapse",      "accent": "#7f1d1d", "stage": 4, "placeholder": True},
    # SUMMARY-TAB-MARKER — synoptic view, default landing tab (D-MD-UI-38)
    {"id": "summary",   "label": "SUMMARY",          "accent": "#4a5568"},
    # MD-V2-STAGE1-MARKER — Stage 1 (Consolidating/Basing) tab
    {"id": "stage_1",   "label": "Stage 1",           "accent": "#1b5e20"},
    # MD-V2-STAGE2-MARKER — Stage 2 (Confirmed uptrend) tab
    {"id": "stage_2",   "label": "Stage 2",           "accent": "#2e7d32"},
    # MD-V2-STAGE3-MARKER — Stage 3 (Topping / Invalidation) tab
    {"id": "stage_3",   "label": "Stage 3",           "accent": "#b45309"},
    # MD-V2-STAGE4-MARKER — Stage 4 (Decline / Capitulation) tab
    {"id": "stage_4",   "label": "Stage 4",           "accent": "#991b1b"},
    # MD-V2-PRE-INDICATORS-MARKER - Pre-indicators (3 leading binary patterns)
    {"id": "pre_indicators", "label": "Pre-Indicators", "accent": "#0F6E56"},
    # MD-V2-POST-INDICATORS-MARKER - Post-indicators (5 trailing binary patterns)
    {"id": "post_indicators", "label": "Post-Indicators", "accent": "#A32D2D"},
    # MD-V2-SETUPS-MARKER - Setups (4 capital-deployment-eligibility patterns)
    {"id": "setups_s1pb", "label": "S1 Basing Setups", "accent": "#BA7517"},
    {"id": "setups_s2vcp", "label": "S2 VCP Setups", "accent": "#BA7517"},
    # MD-V2-TESTS-MARKER - Capital qualification tests (3 tests)
    {"id": "tests", "label": "Capital Tests", "accent": "#0F6E56"},
    # MD-V2-S47-TAB-HEALTHY-RETEST-MARKER - Healthy Retest of MA (13-criterion standalone)
    {"id": "setups_healthy_retest", "label": "Healthy Retest", "accent": "#2E7D32"},
    # MD-V2-S59-TAB-PB-SPLIT-MARKER - S1 + S2 Probing Bet (separate pages)
    {"id": "tests_probing_bet_s1", "label": "S1 Probing Bet", "accent": "#1b5e20"},
    {"id": "tests_probing_bet_s2", "label": "S2 Probing Bet", "accent": "#2e7d32"},
    # MD-V2-S47-TAB-SPECULATIVE-BET-MARKER - Speculative Bets S3+S4 (6-criterion x2)
    {"id": "tests_speculative_bet", "label": "Speculative Bets", "accent": "#c62828"},
    # MD-V2-S48-TAB-HEALTHY-VCP-MARKER - Healthy VCP (Core MM Trade #2: Stage 2 basing + VCP + breakout)
    {"id": "tests_healthy_vcp", "label": "Healthy VCP", "accent": "#1565C0"},
    # MD-V2-MASTER-OVERVIEW-S27-MARKER - synoptic rating matrix, default landing tab
    {"id": "master_overview", "label": "Overview", "accent": "#1b3d5c"},
    # Data / reference tabs
    {"id": "tech",      "label": "Technical Data",   "accent": "#2c5282"},
    {"id": "ssem",      "label": "SS Earnings Momentum", "accent": "#2b6cb0"},
    {"id": "val",       "label": "Valuation",        "accent": "#38a169"},
    {"id": "combos",    "label": "TIMELINESS",       "accent": "#dd6b20"},
    {"id": "changes",   "label": "CHANGES",          "accent": "#c53030"},  # CHANGES-TAB-MARKER
    {"id": "positions", "label": "Live Investments",  "accent": "#319795"},
]

IMPLEMENTED_TABS = [
    "stage_1",  # MD-V2-STAGE1-MARKER
    "stage_2",  # MD-V2-STAGE2-MARKER
    "stage_3",  # MD-V2-STAGE3-MARKER
    "stage_4",  # MD-V2-STAGE4-MARKER
    "pre_indicators",  # MD-V2-PRE-INDICATORS-MARKER
    "post_indicators",  # MD-V2-POST-INDICATORS-MARKER
    "setups_s1pb", "setups_s2vcp",  # MD-V2-SETUPS-MARKER
    "tests",  # MD-V2-TESTS-MARKER
    "setups_healthy_retest",  # MD-V2-S47-TAB-HEALTHY-RETEST-MARKER
    "tests_probing_bet_s1",  # MD-V2-S59-TAB-PB-SPLIT-MARKER
    "tests_probing_bet_s2",  # MD-V2-S59-TAB-PB-SPLIT-MARKER
    "tests_speculative_bet",  # MD-V2-S47-TAB-SPECULATIVE-BET-MARKER
    "tests_healthy_vcp",  # MD-V2-S48-TAB-HEALTHY-VCP-MARKER
    "master_overview",  # MD-V2-MASTER-OVERVIEW-S27-MARKER
    "mm99", "bp", "pb", "utr", "vcp", "tech", "combos", "changes", "positions",
    "ssem", "val",
]


def build_html(data_js):
    # FIX-6: Build tab buttons with per-tab accent colour as inline style
    def hex_to_rgba(hex_color, alpha):
        """Convert hex like #6366f1 to rgba(99,102,241,0.1)"""
        h = hex_color.lstrip('#')
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        return f"rgba({r},{g},{b},{alpha})"

    # STAGE-HEADER-FIXUP — single-row inline-flex parent containing stage groups + reference group
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
        onclick = '' if is_placeholder else 'onclick="switchTab(\'' + t["id"] + '\')"'
        tab_buttons += (
            '<button class="tab-btn' + active + emphasis + ph_class + '" data-tab="' + t["id"] + '" '
            'style="--tab-accent:' + t["accent"] + ';background:' + bg_tint + ';border-color:' + border_tint + ph_style + '" '
            + onclick + '>' + t["label"] + '</button>'
        )
    # Close the final open container (reference group)
    tab_buttons += '</div></div>'  # close reference group + outer wrapper

    tab_containers = ""
    for t in TABS:
        display = "block" if t["id"] == "changes" else "none"
        tab_containers += '<div id="tab-' + t["id"] + '" class="tab-content" style="display:' + display + '"></div>\n    '

    tab_ids_js = ",".join(['"' + t["id"] + '"' for t in TABS])
    tab_labels_js = ",".join(['"' + t["label"] + '"' for t in TABS])
    tab_accents_js = ",".join(['"' + t["accent"] + '"' for t in TABS])

    # ---- CSS ----
    css = r"""
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#f7f5ef;--card:#fbfaf5;--card-hover:#f0ede3;--border:#e8e3d4;
  --text:#333333;--text-dim:#6b6b6b;--text-bright:#1a1a1a;
  --green:#2e7d32;--green-dim:#e8f5e9;--red:#c62828;--red-dim:#ffebee;
  --amber:#8d6e00;--amber-dim:#fff8e1;--blue:#1565c0;--purple:#7955bf;
  --header-height:145px;
  --font:'Aptos','Segoe UI',system-ui,-apple-system,sans-serif
}
body{font-family:var(--font);background:var(--bg);color:var(--text);font-size:13px;line-height:1.4;overflow-x:hidden}
.header{position:fixed;top:0;left:0;right:0;height:var(--header-height);background:var(--card);border-bottom:1px solid var(--border);z-index:100;display:flex;flex-direction:column}
/* FIX-5 Row 1: title + stats + Key + Chart */
.header-top{display:flex;align-items:center;padding:6px 16px;gap:16px}
.header-title{font-size:16px;font-weight:600;color:var(--text-bright);white-space:nowrap}
.header-stats{display:flex;gap:20px;font-size:12px;color:var(--text-dim)}
.header-stats .stat-value{color:var(--text-bright);font-weight:600}
/* FIX-1: Key + Chart pushed right */
.header-right-btns{display:flex;gap:6px;margin-left:auto}
.header-right-btns .ctrl-btn{background:var(--card);border:1px solid var(--border);color:var(--text-dim);font-family:var(--font);font-size:11px;padding:4px 10px;border-radius:4px;cursor:pointer;white-space:nowrap;transition:background .15s,color .15s,border-color .15s}
.header-right-btns .ctrl-btn:hover{color:var(--text-bright);border-color:#bbb;background:var(--card-hover)}
/* FIX-5 Row 2: TABS label + tab nav */
.header-tabs-row{display:flex;align-items:center;padding:0 16px 2px;gap:8px}
.header-tabs-row .row-label{font-size:11px;font-weight:700;color:var(--text-bright);text-transform:uppercase;letter-spacing:.5px;white-space:nowrap}
.tab-nav{display:flex;gap:2px;overflow-x:auto;-webkit-overflow-scrolling:touch}
/* FIX-6: Tab buttons — Group 1 colour: navy */
.tab-btn{background:rgba(27,61,92,0.04);border:1px solid var(--border);border-left:3px solid var(--tab-accent,#1b3d5c);color:var(--text-dim);font-family:var(--font);font-size:11px;font-weight:500;padding:4px 10px;border-radius:4px;cursor:pointer;white-space:nowrap;transition:background .15s,color .15s,border-color .15s}
.tab-btn:hover{background:var(--card-hover);color:var(--text-bright);border-color:#bbb}
/* ACTIVE-TAB-SPECIFICITY-FIX-2 */.tab-btn.tab-active{background:var(--tab-accent,#1b3d5c) !important;color:#fff !important;font-weight:700;border:1px solid var(--tab-accent,#1b3d5c) !important;border-left:5px solid var(--tab-accent,#1b3d5c) !important;box-shadow:0 2px 6px rgba(0,0,0,0.18),inset 0 -2px 0 rgba(255,255,255,0.25);transform:translateY(-1px);letter-spacing:.3px;padding:5px 12px;position:relative;z-index:2}.tab-btn.tab-active:hover{background:var(--tab-accent,#1b3d5c) !important;color:#fff !important;border-color:var(--tab-accent,#1b3d5c) !important}
.tab-btn.tab-emphasis{font-weight:700;letter-spacing:.6px;border-width:2px;text-transform:uppercase;font-size:11.5px}
/* FIX-5 Row 3: toggles label + controls */
.header-controls-row{display:flex;gap:6px;padding:0 16px 4px;align-items:center;flex-wrap:wrap}
.header-controls-row .row-label{font-size:11px;font-weight:700;color:var(--text-bright);text-transform:uppercase;letter-spacing:.5px;white-space:nowrap;min-width:80px}
/* Group 3 colour: teal */
.header-controls-row .ctrl-btn{background:rgba(0,128,128,0.04);border:1px solid var(--border);border-left:3px solid #5f9ea0;color:var(--text-dim);font-family:var(--font);font-size:11px;padding:4px 10px;border-radius:4px;cursor:pointer;white-space:nowrap;transition:background .15s,color .15s,border-color .15s}
.header-controls-row .ctrl-btn:hover{color:var(--text-bright);border-color:#bbb;background:var(--card-hover)}
.header-controls-row .ctrl-btn.active{background:#1b3d5c;color:#fff;border-color:#1b3d5c}
/* Group 2 colour: warm brown */
.anchor-links{display:flex;gap:4px;align-items:center}
.anchor-link{color:var(--text-dim);font-size:11px;text-decoration:none;cursor:pointer;padding:4px 10px;border:1px solid var(--border);border-left:3px solid #a08060;border-radius:4px;background:rgba(160,128,96,0.04);transition:background .15s,color .15s,border-color .15s}
.anchor-link:hover{color:var(--text-bright);border-color:#bbb;background:var(--card-hover)}
#header-tab-controls{display:inline-flex;gap:6px;align-items:center;flex-wrap:wrap}
.main{margin-top:var(--header-height);padding:12px 16px}
.tab-content{animation:fadeIn .2s ease}
@keyframes fadeIn{from{opacity:0}to{opacity:1}}
.summary-tile{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:16px;margin-bottom:12px}
.summary-tile h3{font-size:14px;font-weight:600;color:var(--text-bright);margin-bottom:8px}
.summary-tile .sub{font-size:12px;color:var(--text-dim);margin-bottom:8px}
.summary-stats{display:flex;gap:24px;flex-wrap:wrap}
.summary-stat{display:flex;flex-direction:column}
.summary-stat .label{font-size:11px;color:var(--text-dim);text-transform:uppercase;letter-spacing:.5px}
.summary-stat .value{font-size:20px;font-weight:700;color:var(--text-bright)}
.summary-stat .value.green{color:var(--green)}.summary-stat .value.red{color:var(--red)}.summary-stat .value.amber{color:var(--amber)}
.score-filter,.group-toggles{display:flex;gap:4px;flex-wrap:wrap}
/* Group 4 colour: indigo */
.score-btn,.group-toggle{background:rgba(75,0,130,0.04);border:1px solid var(--border);border-left:3px solid #7b68ae;color:var(--text-dim);font-family:var(--font);font-size:11px;padding:4px 10px;border-radius:4px;cursor:pointer;transition:background .15s,color .15s,border-color .15s}
.score-btn:hover,.group-toggle:hover{border-color:#bbb;color:var(--text-bright);background:var(--card-hover)}
.score-btn.active{background:#1b3d5c;color:#fff;border-color:#1b3d5c;font-weight:600}
.group-toggle.active{background:#1b3d5c;color:#fff;border-color:#1b3d5c;font-weight:600}

/* FIX-11: Fixed table layout, no horizontal scroll */
.data-table-wrap{overflow-x:clip;border-radius:8px;border:1px solid var(--border)}
table.data-table{width:100%;border-collapse:collapse;font-size:12px;table-layout:auto}
/* SESSION 10 — D-MD-UI-13: sticky thead replaces per-row top arithmetic. Browser stacks group-header-row and col-header-row natively below the page header. Works on every screen size, every zoom level, every device. Box-shadow gives the freeze-line a visible separator from rows below. background needed so row content scrolling underneath doesn't bleed through cell-border gaps. */
table.data-table thead{position:sticky;top:var(--header-height);z-index:8;background:#f0ede3;box-shadow:0 2px 4px rgba(0,0,0,0.06)}
table.data-table th{background:#f0ede3;color:#6b6b6b;font-weight:600;font-size:10px;text-transform:none;letter-spacing:.3px;padding:4px 4px;text-align:left;border-bottom:2px solid var(--border);z-index:5;cursor:pointer;white-space:nowrap;user-select:none;-webkit-user-select:none;overflow:hidden;text-overflow:ellipsis}
/* SESSION 9 Pass 1.2 — D-MD-UI-10: Live Portfolio table thead is non-sticky (it's short, no need to pin; pinning competes with Qualified Stocks thead) */
table.data-table.data-table-portfolio thead{position:static;box-shadow:none}
table.data-table.data-table-portfolio th{position:static}
table.data-table.data-table-portfolio .col-header-row th{position:static}
/* SESSION 10 — D-MD-UI-13b: Tile-style tables (industry/sector overview tiles, qualification group tiles) are short overview tables, not long scrollers. Sticky thead would cause the header to "follow" the page scroll and overlap mid-tile data. Exempt them. */
table.data-table.data-table-tile thead{position:static;box-shadow:none}
table.data-table.data-table-tile th{position:static}
table.data-table th:hover{color:var(--text)}
table.data-table th .sort-arrow{margin-left:2px;opacity:.4}
table.data-table th.sorted .sort-arrow{opacity:1;color:var(--amber)}
table.data-table td{padding:3px 4px;border-bottom:1px solid #e8e3d4;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
table.data-table tr:hover{background:var(--card-hover)}
/* FIX-9: Consistent text alignment */
.col-num{text-align:right}
.col-txt{text-align:left}
table.data-table th.col-num{text-align:right}
table.data-table th.col-txt{text-align:left}

/* SESSION 10: group-header-row + col-header-row no longer need per-row top arithmetic — sticky <thead> stacks them natively */
table.data-table .group-header-row th{background:#f5f3ec;font-size:9px;font-weight:600;padding:2px 4px;text-align:center;border-bottom:1px solid var(--border);cursor:default;letter-spacing:.4px;z-index:6;pointer-events:none}
table.data-table .col-header-row th{z-index:8}

/* Column group borders */
.grp-lt-first{border-left:2px solid rgba(200,50,50,0.25)}
.grp-lt-last{border-right:2px solid rgba(200,50,50,0.25)}
th.grp-lt-first,th.grp-lt-last{border-top:2px solid rgba(200,50,50,0.25)}
.grp-mt-first{border-left:2px solid rgba(200,150,0,0.25)}
.grp-mt-last{border-right:2px solid rgba(200,150,0,0.25)}
th.grp-mt-first,th.grp-mt-last{border-top:2px solid rgba(200,150,0,0.25)}
.grp-st-first{border-left:2px solid rgba(50,150,50,0.25)}
.grp-st-last{border-right:2px solid rgba(50,150,50,0.25)}
th.grp-st-first,th.grp-st-last{border-top:2px solid rgba(50,150,50,0.25)}
.grp-lead-first{border-left:2px solid rgba(50,100,200,0.25)}
.grp-lead-last{border-right:2px solid rgba(50,100,200,0.25)}
th.grp-lead-first,th.grp-lead-last{border-top:2px solid rgba(50,100,200,0.25)}
.grp-rs-first{border-left:2px solid rgba(120,80,200,0.25)}
.grp-rs-last{border-right:2px solid rgba(120,80,200,0.25)}
th.grp-rs-first,th.grp-rs-last{border-top:2px solid rgba(120,80,200,0.25)}
.grp-eps-first{border-left:2px solid rgba(50,150,50,0.25)}
.grp-eps-last{border-right:2px solid rgba(50,150,50,0.25)}
th.grp-eps-first,th.grp-eps-last{border-top:2px solid rgba(50,150,50,0.25)}
.grp-ebitda-first{border-left:2px solid rgba(50,100,200,0.25)}
.grp-ebitda-last{border-right:2px solid rgba(50,100,200,0.25)}
th.grp-ebitda-first,th.grp-ebitda-last{border-top:2px solid rgba(50,100,200,0.25)}
.grp-sales-first{border-left:2px solid rgba(200,150,0,0.25)}
.grp-sales-last{border-right:2px solid rgba(200,150,0,0.25)}
th.grp-sales-first,th.grp-sales-last{border-top:2px solid rgba(200,150,0,0.25)}
.grp-tp-first{border-left:2px solid rgba(120,80,200,0.25)}
.grp-tp-last{border-right:2px solid rgba(120,80,200,0.25)}
th.grp-tp-first,th.grp-tp-last{border-top:2px solid rgba(120,80,200,0.25)}
.grp-buy-first{border-left:2px solid rgba(200,50,50,0.25)}
.grp-buy-last{border-right:2px solid rgba(200,50,50,0.25)}
th.grp-buy-first,th.grp-buy-last{border-top:2px solid rgba(200,50,50,0.25)}
.grp-pe-first{border-left:2px solid rgba(50,150,50,0.25)}
.grp-pe-last{border-right:2px solid rgba(50,150,50,0.25)}
th.grp-pe-first,th.grp-pe-last{border-top:2px solid rgba(50,150,50,0.25)}
.grp-loose-first{border-left:2px solid rgba(50,100,200,0.25)}
.grp-loose-last{border-right:2px solid rgba(50,100,200,0.25)}
th.grp-loose-first,th.grp-loose-last{border-top:2px solid rgba(50,100,200,0.25)}
.grp-med-first{border-left:2px solid rgba(200,150,0,0.25)}
.grp-med-last{border-right:2px solid rgba(200,150,0,0.25)}
th.grp-med-first,th.grp-med-last{border-top:2px solid rgba(200,150,0,0.25)}
.grp-tight-first{border-left:2px solid rgba(50,150,50,0.25)}
.grp-tight-last{border-right:2px solid rgba(50,150,50,0.25)}
th.grp-tight-first,th.grp-tight-last{border-top:2px solid rgba(50,150,50,0.25)}
/* CHANGES-V2-MARKER: column group borders for CHANGES tab */
.grp-chg-bp-first{border-left:2px solid rgba(39,103,73,0.25)}
.grp-chg-bp-last{border-right:2px solid rgba(39,103,73,0.25)}
th.grp-chg-bp-first,th.grp-chg-bp-last{border-top:2px solid rgba(39,103,73,0.25)}
.grp-chg-pb-first{border-left:2px solid rgba(107,70,193,0.25)}
.grp-chg-pb-last{border-right:2px solid rgba(107,70,193,0.25)}
th.grp-chg-pb-first,th.grp-chg-pb-last{border-top:2px solid rgba(107,70,193,0.25)}
.grp-chg-mm99-first{border-left:2px solid rgba(27,61,92,0.25)}
.grp-chg-mm99-last{border-right:2px solid rgba(27,61,92,0.25)}
th.grp-chg-mm99-first,th.grp-chg-mm99-last{border-top:2px solid rgba(27,61,92,0.25)}
.grp-chg-vcp-first{border-left:2px solid rgba(156,66,33,0.25)}
.grp-chg-vcp-last{border-right:2px solid rgba(156,66,33,0.25)}
th.grp-chg-vcp-first,th.grp-chg-vcp-last{border-top:2px solid rgba(156,66,33,0.25)}
.grp-chg-utr-first{border-left:2px solid rgba(116,66,16,0.25)}
.grp-chg-utr-last{border-right:2px solid rgba(116,66,16,0.25)}
th.grp-chg-utr-first,th.grp-chg-utr-last{border-top:2px solid rgba(116,66,16,0.25)}
.grp-chg-col-first{border-left:2px solid rgba(180,30,30,0.25)}
.grp-chg-col-last{border-right:2px solid rgba(180,30,30,0.25)}
th.grp-chg-col-first,th.grp-chg-col-last{border-top:2px solid rgba(180,30,30,0.25)}
.grp-chg-s3-first{border-left:2px solid rgba(200,100,0,0.25)}
.grp-chg-s3-last{border-right:2px solid rgba(200,100,0,0.25)}
th.grp-chg-s3-first,th.grp-chg-s3-last{border-top:2px solid rgba(200,100,0,0.25)}
.grp-chg-s4-first{border-left:2px solid rgba(150,20,20,0.25)}
.grp-chg-s4-last{border-right:2px solid rgba(150,20,20,0.25)}
th.grp-chg-s4-first,th.grp-chg-s4-last{border-top:2px solid rgba(150,20,20,0.25)}
/* Now-column emphasis — strong differentiation */
.chg-now-cell{background:rgba(0,0,0,0.10);border-left:2px solid rgba(0,0,0,0.18)}
.chg-now-cell .badge{font-weight:800;font-size:11px !important}
th.chg-now-th{font-weight:800;background:rgba(0,0,0,0.08) !important;border-left:2px solid rgba(0,0,0,0.18);font-size:12px !important}
/* CHANGES tab: fit all 35 cols on one screen */
.chg-table-wrap{overflow-x:visible;overflow-y:visible;border-radius:8px;border:1px solid var(--border)}
.chg-table-wrap thead{position:sticky;top:var(--header-height);z-index:9;background:var(--bg-primary)}
table.data-table.chg-table{table-layout:fixed;width:100%}
table.data-table.chg-table th,table.data-table.chg-table td{padding:3px 2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:10px}
table.data-table.chg-table .badge{font-size:9px !important;padding:2px 3px}
table.data-table.chg-table .chg-now-cell .badge{font-size:10px !important;padding:2px 4px}
/* CHANGES tab badge colour overrides: Late=yellow, Early=orange, dash=grey */
table.data-table.chg-table .badge-late{background:#fff9c4;color:#f9a825;border-color:rgba(249,168,37,0.35)}
table.data-table.chg-table .badge-early{background:#fff3e0;color:#e65100;border-color:rgba(230,81,0,0.35)}
table.data-table.chg-table .badge-fail{background:rgba(232,227,212,0.3);color:rgba(180,172,150,0.5);border:1px solid rgba(200,192,170,0.15)}

table.data-table th.col-num,table.data-table td.col-num{text-align:right}
table.data-table th.col-txt,table.data-table td.col-txt{text-align:left}
table.data-table th.col-filter,table.data-table td.col-filter{text-align:center}
table.data-table th.col-rs,table.data-table td.col-rs{text-align:center}
table.data-table th.col-ref,table.data-table td.col-ref{text-align:center}
table.data-table th.col-ratings,table.data-table td.col-ratings{text-align:center}
table.data-table th.col-price,table.data-table td.col-price{text-align:right}
/* FIX-S4-COLW-V4: table-layout:auto — browser auto-sizes by content */
table.data-table td.col-identity{white-space:nowrap}
.col-price{background:rgba(21,101,192,.03)}.col-filter{background:rgba(141,110,0,.03)}.col-rs{background:rgba(121,85,191,.03)}.col-green{background:rgba(46,125,50,.03)}.col-ref{background:rgba(21,101,192,.03)}
.pass{color:var(--green)}.fail{color:var(--red)}.amber{color:var(--amber)}.neutral{color:var(--text-dim)}
.badge{display:inline-block;padding:2px 6px;border-radius:3px;font-size:10px;font-weight:600;text-transform:uppercase}
.badge-pass{background:var(--green-dim);color:var(--green)}.badge-fail{background:var(--red-dim);color:var(--red)}.badge-amber{background:var(--amber-dim);color:var(--amber)}
.badge-capital{background:#e8f5e9;color:var(--green);border:1px solid rgba(46,125,50,.3)}
.badge-late{background:#fff8e1;color:var(--amber);border:1px solid rgba(141,110,0,.3)}
.badge-early{background:#e3f2fd;color:var(--blue);border:1px solid rgba(21,101,192,.3)}
.tm-grade{display:inline-block;min-width:22px;padding:2px 6px;border-radius:3px;font-weight:700;font-size:11px;text-align:center;line-height:1.2}
.tm-A{background:#0d3817;color:#fff;border:1px solid #0d3817}
.tm-B{background:#2e7d32;color:#fff;border:1px solid #2e7d32}
.tm-C{background:#f2e1a5;color:#8d6e00;border:1px solid #d4b859}
.tm-D{background:#ffe0b2;color:#e65100;border:1px solid #f4a460}
.tm-F{background:#c62828;color:#fff;border:1px solid #b71c1c}
.tm-N{background:#eee;color:#888;border:1px solid #ddd}
.rating-pill{display:inline-block;min-width:22px;padding:2px 6px;border-radius:3px;font-weight:700;font-size:11px;text-align:center;line-height:1.2}
.pill-A{background:#0d3817;color:#fff;border:1px solid #0d3817}
.pill-B{background:#2e7d32;color:#fff;border:1px solid #2e7d32}
.pill-C{background:#f2e1a5;color:#8d6e00;border:1px solid #d4b859}
.pill-D{background:#ffe0b2;color:#e65100;border:1px solid #f4a460}
.pill-F{background:#c62828;color:#fff;border:1px solid #b71c1c}
.pill-N{background:#eee;color:#888;border:1px solid #ddd}
/* SESSION 9 Pass 1.1: COMBO summary recut — 2-pane grid layout */
.combo-summary-grid{display:grid;grid-template-columns:minmax(420px,2fr) minmax(220px,1fr);gap:18px;align-items:start;margin-top:8px}
.combo-summary-left{}
.combo-summary-right{}
.combo-grid{width:100%;border-collapse:collapse;font-size:11px}
.combo-grid th,.combo-grid td{padding:5px 8px;border-bottom:1px solid var(--border);text-align:left}
.combo-grid-corner{font-weight:700;color:var(--text-bright);background:rgba(27,61,92,0.04);text-transform:uppercase;letter-spacing:.4px;font-size:10px}
.combo-grid-colhdr{font-weight:700;color:var(--text-bright);text-align:center;text-transform:uppercase;letter-spacing:.4px;font-size:10px;background:rgba(27,61,92,0.04)}
.combo-grid-rowlabel{font-weight:600;color:var(--text);white-space:nowrap}
.combo-grid-note{font-weight:400;color:#999;font-size:9px;font-style:italic;margin-left:4px}
.combo-grid-cell{text-align:center;font-variant-numeric:tabular-nums;color:var(--text);font-weight:600}
.combo-grid-den{color:#999;font-weight:400;font-size:10px}
.combo-grid-zero{color:#bbb;font-weight:400}
.combo-grid-row-pending td,.combo-grid-row-pending th{opacity:.55}
.combo-grade-block{border:1px solid var(--border);border-radius:4px;padding:10px 12px;background:#fff}
.combo-grade-title{font-weight:700;font-size:10px;color:var(--text-bright);text-transform:uppercase;letter-spacing:.4px;padding-bottom:6px;border-bottom:1px solid var(--border);margin-bottom:8px}
.combo-grade-row{display:flex;align-items:center;gap:10px;padding:3px 0}
.combo-grade-count{font-weight:700;color:var(--text);font-variant-numeric:tabular-nums;font-size:13px;margin-left:auto}
.combo-grade-den{color:#999;font-weight:400;font-size:11px}
.combo-grade-foot{margin-top:8px;padding-top:6px;border-top:1px solid var(--border);font-size:10px;color:#888;font-style:italic}
.combo-col-pending{opacity:.55}
/* SESSION 9 Pass 1.2 — D-MD-UI-11: Grade filter buttons tinted with grade colour when active */
.grade-toggle{font-weight:700;letter-spacing:.5px;border-left-width:3px}
.grade-toggle.grade-toggle-A.active{background:#0d3817;color:#fff;border-color:#0d3817;border-left-color:#0d3817}
.grade-toggle.grade-toggle-B.active{background:#2e7d32;color:#fff;border-color:#2e7d32;border-left-color:#2e7d32}
.grade-toggle.grade-toggle-C.active{background:#f2e1a5;color:#8d6e00;border-color:#d4b859;border-left-color:#8d6e00}
.grade-toggle.grade-toggle-D.active{background:#ffe0b2;color:#e65100;border-color:#f4a460;border-left-color:#e65100}
.grade-toggle.grade-toggle-F.active{background:#c62828;color:#fff;border-color:#b71c1c;border-left-color:#b71c1c}
.grade-toggle.grade-toggle-A{border-left-color:#0d3817}
.grade-toggle.grade-toggle-B{border-left-color:#2e7d32}
.grade-toggle.grade-toggle-C{border-left-color:#8d6e00}
.grade-toggle.grade-toggle-D{border-left-color:#e65100}
.grade-toggle.grade-toggle-F{border-left-color:#b71c1c}
.tick{color:var(--green)}.cross{color:var(--red)}
.score-bar{display:inline-flex;gap:1px;vertical-align:middle}
.score-bar .pip{width:6px;height:12px;border-radius:2px}
.pip-on{background:var(--green)}.pip-off{background:#e0ddd3}
.pip-div{display:inline-block;width:1px;height:9px;background:rgba(120,110,90,0.30);margin:0 2px;vertical-align:middle;border-radius:1px} /* MD-V2-S49-PIP-DIV-MARKER: group separator in score-pip rows */
.pip-amber{background:var(--amber)}
/* BP daily duration strip — 63 bars (3 trading months) per group, narrower pip so 3 groups fit */
.bp-days-bar{display:inline-flex;gap:0;vertical-align:middle;align-items:center;line-height:1}
.bp-days-bar .day-pip{width:2px;height:11px;border-radius:0}
.day-pip-on{background:var(--green)}.day-pip-off{background:#e8e5d8}
.bp-days-frac{margin-left:5px;font-size:10px;color:#555;font-variant-numeric:tabular-nums}
.bp-days-streak{margin-left:4px;font-size:10px;font-weight:600;color:#1b5e20;font-variant-numeric:tabular-nums}
.bp-days-streak-zero{color:#999;font-weight:400}
.signal-bar{display:inline-flex;gap:1px;vertical-align:middle}
.signal-bar .seg{width:12px;height:16px;border-radius:2px}
.seg-pass{background:var(--green)}.seg-fail{background:var(--red-dim)}.seg-amber{background:var(--amber-dim)}
.combo-cell{text-align:center;font-weight:600}

/* Industry/Sector tiles */
.ind-sec-wrap{display:flex;gap:12px;margin-bottom:12px;align-items:flex-start}
.ind-sec-wrap .half-table{flex:1;min-width:0;display:flex;flex-direction:column;border:1px solid var(--border);border-radius:6px;padding:8px;background:var(--card)}
.half-table .half-title{font-size:13px;font-weight:600;color:var(--text-bright);margin-bottom:6px;flex-shrink:0}
/*HALF-TABLE-MAX-HEIGHT*/.half-table .data-table-wrap{overflow-y:auto;overflow-x:hidden;min-height:450px;max-height:600px}
.half-table table.data-table th{font-size:11px;text-transform:none;letter-spacing:0;white-space:normal;word-wrap:break-word}

.qual-tile{padding:12px 0;margin-bottom:8px;margin-top:24px}
.qual-tile h4{font-size:13px;font-weight:600;color:var(--text-bright);margin-bottom:8px}
.qualified-title{margin-top:20px}
.chart-panel{position:fixed;top:var(--header-height);right:0;bottom:0;width:25%;background:var(--card);border-left:1px solid var(--border);z-index:90;transform:translateX(100%);transition:transform .3s ease,width .3s ease;overflow-y:auto;padding:16px 24px 16px 16px}
.chart-panel.open{transform:translateX(0)}
.chart-open .main{margin-right:25%;transition:margin-right .3s ease,margin-left .3s ease}
/* MD-CHART-V2-WIRING-MARKER: chart panel slides in from the LEFT on V2 tabs (legacy keeps the right). */
body.chart-from-left .chart-panel{left:0;right:auto;border-left:none;border-right:1px solid var(--border);transform:translateX(-100%)}
body.chart-from-left .chart-panel.open{transform:translateX(0)}
#s1-main-table td.name-cell,#s2-main-table td.name-cell,#s3-main-table td.name-cell,#s4-main-table td.name-cell,#pi-main-table td.name-cell,#po-main-table td.name-cell,.st-main-table td.name-cell,#ct-main-table td.name-cell,#mo-matrix-table td.mo-mx-name-cell{cursor:pointer}
/* MD-V2-S41-CHART-RIGHT-FREEZE-COL-MARKER CSS -- freeze company/ticker first column on the LEFT across all V2 tabs (Stage 1-4, PI, PO, ST, CT). Pattern mirrors #mo-matrix-table td.mo-mx-name-cell at L1930. The first th in col-header-row gets sticky-left + higher z-index so the column header pins above tbody. Group-header row first th (supergroup label, has colspan>=2) is NOT sticky-left -- it would visually overlap neighbouring supergroup labels on horizontal scroll. */
#s1-main-table tbody td.name-cell,#s2-main-table tbody td.name-cell,#s3-main-table tbody td.name-cell,#s4-main-table tbody td.name-cell,#pi-main-table tbody td.name-cell,#po-main-table tbody td.name-cell,.st-main-table tbody td.name-cell,#ct-main-table tbody td.name-cell{position:sticky;left:0;z-index:5;background:#fbfaf5;border-right:1px solid #e0dcc8}
#s1-main-table tbody tr:hover td.name-cell,#s2-main-table tbody tr:hover td.name-cell,#s3-main-table tbody tr:hover td.name-cell,#s4-main-table tbody tr:hover td.name-cell,#pi-main-table tbody tr:hover td.name-cell,#po-main-table tbody tr:hover td.name-cell,.st-main-table tbody tr:hover td.name-cell,#ct-main-table tbody tr:hover td.name-cell{background:#f4f1e6}
#s1-main-table thead tr.col-header-row th:first-child,#s2-main-table thead tr.col-header-row th:first-child,#s3-main-table thead tr.col-header-row th:first-child,#s4-main-table thead tr.col-header-row th:first-child,#pi-main-table thead tr.col-header-row th:first-child,#po-main-table thead tr.col-header-row th:first-child,.st-main-table thead tr.col-header-row th:first-child,#ct-main-table thead tr.col-header-row th:first-child{position:sticky;left:0;z-index:70;background:#fbfaf5;border-right:1px solid #e0dcc8}
body[data-active-tab^="stage_"] #hdr-chart-btn,body[data-active-tab="pre_indicators"] #hdr-chart-btn,body[data-active-tab="post_indicators"] #hdr-chart-btn,body[data-active-tab^="setups"] #hdr-chart-btn,body[data-active-tab="tests"] #hdr-chart-btn,
body[data-active-tab="tests_healthy_vcp"] #hdr-chart-btn,
body[data-active-tab="tests_speculative_bet"] #hdr-chart-btn,
body[data-active-tab="tests_probing_bet_s1"] #hdr-chart-btn,
body[data-active-tab="tests_probing_bet_s2"] #hdr-chart-btn,
body[data-active-tab="setups_healthy_retest"] #hdr-chart-btn,body[data-active-tab="master_overview"] #hdr-chart-btn{display:none!important}
body.chart-from-left .s1-controls{left:var(--chart-panel-w,0)!important;transition:left .3s ease}
body.chart-from-left #mo-matrix-table tbody td.mo-mx-name-cell,body.chart-from-left #mo-matrix-table thead th.mo-mx-screen-col{left:var(--chart-panel-w,0)!important;transition:left .3s ease}
/* MD-V2-GROUP-CAPTIONS-MARKER: signposting + emphasis for the rewritten group-test captions */
.gcap .db{font-weight:600;}
.gcap u{text-decoration:underline;text-underline-offset:2px;text-decoration-color:#bbb;}
.gcap .intro{display:block;font-weight:600;margin:6px 0 3px;}
.gcap .tline{display:block;padding-left:16px;text-indent:-16px;margin-top:2px;}
.gcap .tnum{font-weight:600;}
.chart-panel .close-btn{position:absolute;top:8px;right:8px;background:var(--card-hover);border:1px solid var(--border);color:var(--text);width:28px;height:28px;border-radius:4px;cursor:pointer;font-size:16px}
.chart-width-btns{display:flex;gap:4px;margin-bottom:12px}
.chart-width-btn{background:var(--card);border:1px solid var(--border);color:var(--text-dim);font-family:var(--font);font-size:11px;padding:3px 8px;border-radius:3px;cursor:pointer}
.chart-width-btn.active{background:#1b3d5c;color:#fff;border-color:#1b3d5c}

/* FIX-16: graduated colours including grey neutral */
.grad-green{color:#2e7d32}.grad-lgreen{color:#558b2f}.grad-neutral{color:#6b6b6b}.grad-red{color:#c62828}.grad-dred{color:#b71c1c}
.sparkline-cell{vertical-align:middle}
.range-bar-cell{vertical-align:middle}

/* Key: floating tooltips near column headers */
.key-panel{display:none}
table.data-table th .key-tip{display:none;position:absolute;top:100%;left:0;z-index:20;background:#fbfaf5;border:1px solid #e8e3d4;border-radius:4px;padding:6px 10px;font-size:10px;font-weight:400;color:#6b6b6b;white-space:normal;min-width:160px;max-width:300px;box-shadow:0 2px 8px rgba(0,0,0,.08);text-transform:none;letter-spacing:0;line-height:1.35;pointer-events:none}
table.data-table.show-keys th .key-tip{display:block}
table.data-table.show-keys th{overflow:visible}
table.data-table th{position:relative}

/* FIX-3: Ratings columns toggle */
.ratings-hidden .col-ratings{display:none}

/* FIX-2: Qualified Stocks heading */
.qualified-title{font-size:14px;font-weight:600;color:var(--text-bright);margin:12px 0 8px;padding-left:4px}
.section-label-row td{font-size:13px;font-weight:600;color:var(--text-bright);padding:10px 6px 4px;border-bottom:1px solid var(--border);background:#f7f5ef}

/* UTR V2: Stage group borders (MM99 pattern) */
.utr-e-first{border-left:2px solid rgba(200,170,0,0.30)}
.utr-e-last{border-right:2px solid rgba(200,170,0,0.30)}
th.utr-e-first,th.utr-e-last{border-top:2px solid rgba(200,170,0,0.30)}
.utr-l-first{border-left:2px solid rgba(230,100,0,0.30)}
.utr-l-last{border-right:2px solid rgba(230,100,0,0.30)}
th.utr-l-first,th.utr-l-last{border-top:2px solid rgba(230,100,0,0.30)}
.utr-c-first{border-left:2px solid rgba(46,125,50,0.30)}
.utr-c-last{border-right:2px solid rgba(46,125,50,0.30)}
th.utr-c-first,th.utr-c-last{border-top:2px solid rgba(46,125,50,0.30)}
/* SESSION 11 — D-MD-SSEM-1..4 + SESSION 12 polish (D-MD-SSEM-5..7) */
/* Rating pill — palette canonicalised to D-MD-UI-2 / Ratings Dashboard (rgb values from live IC ratings dashboard) */
.ssem-rating-pill{display:inline-block;padding:4px 8px;border-radius:3px;font-weight:700;font-size:11px;text-align:center;min-width:28px;white-space:nowrap}
.ssem-rating-A{background:rgb(27,94,32);color:rgb(165,214,167)}
.ssem-rating-B{background:rgb(46,125,50);color:rgb(200,230,201)}
.ssem-rating-C{background:rgb(141,110,0);color:rgb(242,225,165)}
.ssem-rating-D{background:rgb(230,81,0);color:rgb(242,225,165)}
.ssem-rating-F{background:rgb(183,28,28);color:rgb(239,154,154)}
.ssem-rating-N{background:rgb(232,227,212);color:rgb(154,147,128)}
/* Score column — rating-keyed colour (D-MD-SSEM-6): A/B green, C neutral, D/F red */
.ssem-score-cell{font-weight:700;font-size:13px;text-align:right}
.ssem-score-rA{color:#1b5e20}
.ssem-score-rB{color:#2e7d32}
.ssem-score-rC{color:#333333}
.ssem-score-rD{color:#e65100}
.ssem-score-rF{color:#b71c1c}
.ssem-score-rN{color:#999}
/* Cell background heatmap (D-MD-SSEM-3): subtle green/neutral/red bg by % value sign+magnitude */
.ssem-cell-pos-strong{background:rgba(46,125,50,0.18)}
.ssem-cell-pos-mid{background:rgba(46,125,50,0.10)}
.ssem-cell-pos-weak{background:rgba(46,125,50,0.04)}
.ssem-cell-neutral{background:transparent}
.ssem-cell-neg-weak{background:rgba(198,40,40,0.04)}
.ssem-cell-neg-mid{background:rgba(198,40,40,0.10)}
.ssem-cell-neg-strong{background:rgba(198,40,40,0.18)}
/* Trend arrows on tile cells */
.ssem-trend-up{color:#2e7d32;font-weight:700}
.ssem-trend-flat{color:#888;font-weight:400}
.ssem-trend-down{color:#c62828;font-weight:700}
/* Skew glyphs */
.ssem-skew{font-family:ui-monospace,Consolas,monospace;font-size:10px;color:#666;letter-spacing:-.5px}
.ssem-tile-cell{font-size:10px;text-align:right;padding:2px 4px}
.ssem-tile-glyph{font-size:10px;text-align:center;padding:2px 4px;white-space:nowrap}
/* SSEM filter toggle row buttons (extending tab-emphasis style) */
.ssem-filter-row{display:inline-flex;gap:4px;align-items:center;flex-wrap:wrap}
.ssem-filter-divider{width:1px;height:18px;background:var(--border);margin:0 6px}
.ssem-filter-btn{padding:3px 9px;font-size:11px;font-weight:600;border:1px solid var(--border);background:var(--card);color:var(--text-dim);border-radius:4px;cursor:pointer;letter-spacing:.3px}
.ssem-filter-btn.active{background:#1b3d5c;color:#fff;border-color:#1b3d5c}
.ssem-rating-btn-A.active{background:rgb(27,94,32);border-color:rgb(27,94,32);color:rgb(165,214,167)}
.ssem-rating-btn-B.active{background:rgb(46,125,50);border-color:rgb(46,125,50);color:rgb(200,230,201)}
.ssem-rating-btn-C.active{background:rgb(141,110,0);border-color:rgb(141,110,0);color:rgb(242,225,165)}
.ssem-rating-btn-D.active{background:rgb(230,81,0);border-color:rgb(230,81,0);color:rgb(242,225,165)}
.ssem-rating-btn-F.active{background:rgb(183,28,28);border-color:rgb(183,28,28);color:rgb(239,154,154)}
.ssem-rating-btn-N.active{background:rgb(232,227,212);border-color:rgb(232,227,212);color:rgb(154,147,128)}
/* SESSION 12 — TYPE/TIME and Cumulative/Per-period toggle row (lives in #3 TOGGLES area) */
.ssem-mode-toggle-row{display:inline-flex;gap:4px;align-items:center;margin-right:6px}
.ssem-mode-btn{padding:3px 8px;font-size:10px;font-weight:600;border:1px solid var(--border);background:var(--card);color:var(--text-dim);border-radius:4px;cursor:pointer;letter-spacing:.3px}
.ssem-mode-btn.active{background:#1b3d5c;color:#fff;border-color:#1b3d5c}
.ssem-mode-label{font-size:10px;color:var(--text-dim);margin-right:4px}

/* UTR key description row above headers — SESSION 10: sticky <thead> handles vertical stacking, no per-row top needed */
.utr-key-row td,.gen-key-row td{font-size:9px;color:#8b8680;font-weight:400;font-style:italic;text-align:center;padding:2px 4px;white-space:normal;line-height:1.2;vertical-align:bottom;border-bottom:none;max-width:80px;overflow:hidden;text-overflow:ellipsis;z-index:5;background:#f7f5ef}
/* UTR: hide inputs columns */
.utr-inputs-hidden .col-input{display:none}
/* UTR: Test MA colour coding */
.ma-50d{color:#ff8c00;font-weight:700}.ma-100d{color:#2ca02c;font-weight:700}.ma-150d{color:#1a5276;font-weight:700}.ma-200d{color:#4a3d9e;font-weight:700}

@media(max-width:768px){.header-stats{display:none}.ind-sec-wrap{flex-direction:column}}
/* FEAT-5: Industry/sector filter highlight */
.ind-sec-highlight td.col-sector,.ind-sec-highlight td.col-industry{background:rgba(46,125,50,0.08)}
.filter-pill{transition:opacity 0.2s}.filter-pill:hover{opacity:0.8}

/* MD-V2-STAGE1-MARKER-CSS-START */
/* MD-V2-S37-FOLLOWUP-MARKER: .s1-intro is the page-description ribbon at the top of every tab. Dropped max-width so it wraps full-width and uses the row, rather than being a tall narrow column. */
.s1-intro { background: var(--bg-card, #fbfaf5); border: 1px solid var(--border, #e0dcc8); border-radius: 4px; padding: 12px 16px; margin-bottom: 14px; font-size: 12px; color: var(--text-muted, #666); }
.s1-intro b { color: #2a2a2a; }
.s1-controls { display: flex; gap: 14px; flex-wrap: wrap; align-items: center; margin-bottom: 12px; padding: 9px 14px; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }
.s1-controls .ctrl-grp { display: flex; align-items: center; gap: 5px; padding-right: 14px; border-right: 1px solid #e0dcc8; }
.s1-controls .ctrl-grp:last-child { border-right: none; padding-right: 0; }
.s1-controls .ctrl-label { font-size: 9px; text-transform: uppercase; letter-spacing: 0.5px; color: #999; font-weight: 600; margin-right: 4px; }
.s1-controls .toggle-btn { background: #f3efe2; border: 1px solid #e0dcc8; color: #2a2a2a; padding: 3px 9px; font-size: 11px; font-family: inherit; border-radius: 3px; cursor: pointer; transition: all 0.12s; }
.s1-controls .toggle-btn:hover:not(.disabled) { background: #ebe5d2; }
.s1-controls .toggle-btn.active { background: #1b5e20; color: #fff; border-color: #1b5e20; }
.s1-controls .toggle-btn.disabled { background: #f0ebd9; color: #bbb; cursor: not-allowed; border-style: dashed; }

.s1-rating-tiles { display: grid; grid-template-columns: repeat(5, 1fr); gap: 10px; margin-bottom: 12px; }
.s1-rating-tiles .rating-tile { background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; padding: 11px 14px; cursor: pointer; transition: all 0.12s; }
.s1-rating-tiles .rating-tile:hover { transform: translateY(-1px); box-shadow: 0 2px 6px rgba(0,0,0,0.08); }
.s1-rating-tiles .rating-tile.active { background: #1b5e20; color: #fff; border-color: #1b5e20; }
.s1-rating-tiles .rating-tile.active .rt-label, .s1-rating-tiles .rating-tile.active .rt-count { color: #fff; }
.s1-rating-tiles .rating-tile.active .rt-sub { color: rgba(255,255,255,0.75); }
.s1-rating-tiles .rt-label { font-size: 11px; font-weight: 600; color: #666; letter-spacing: 0.2px; }
.s1-rating-tiles .rt-count { font-size: 22px; font-weight: 700; color: #2a2a2a; margin-top: 3px; line-height: 1; font-variant-numeric: tabular-nums; }
.s1-rating-tiles .rt-sub { font-size: 10px; color: #999; margin-top: 3px; }
/* MD-V2-S40-PER-TILE-THRESHOLDS: per-tile threshold line beneath rt-sub; shows the
   pass-count threshold for each tier (≥X/Y). None tier emits NBSP to
   preserve vertical rhythm. Applies to all 4 Stage tabs via the
   s1-rating-tiles class (shared by Stage 2/3/4 grids). */
.s1-rating-tiles .rt-thresh { font-size: 10px; font-weight: 600; color: #777; margin-top: 4px; letter-spacing: 0.1px; }
.s1-rating-tiles .rating-tile.active .rt-thresh { color: rgba(255,255,255,0.85); }
.s1-rating-tiles .rt-strip { height: 3px; border-radius: 2px; margin-top: 7px; }
.s1-rating-tiles .rt-strip-pl  { background: #14501c; }
.s1-rating-tiles .rt-strip-pe  { background: #4a9658; }
.s1-rating-tiles .rt-strip-pla { background: #6b8a98; }
.s1-rating-tiles .rt-strip-pos { background: #c4c0b0; }
.s1-rating-tiles .rt-strip-none { background: #e0ddd0; }
.s1-rating-tiles .rating-tile.tint-pl   { background: rgba(20, 87, 24, 0.08); }
.s1-rating-tiles .rating-tile.tint-pe   { background: rgba(74, 150, 88, 0.08); }
.s1-rating-tiles .rating-tile.tint-pla  { background: rgba(107, 138, 152, 0.08); }
.s1-rating-tiles .rating-tile.tint-pos  { background: rgba(196, 192, 176, 0.18); }
.s1-rating-tiles .rating-tile.tint-none { background: rgba(224, 221, 208, 0.30); }

#tab-stage_1 .group-captions { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 10px; margin-bottom: 10px; }
#tab-stage_1 .gcap { background: #fbfaf5; border-left: 3px solid; padding: 9px 12px; font-size: 11px; color: #2a2a2a; line-height: 1.45; border-radius: 0 3px 3px 0; }
#tab-stage_1 .gcap b { display: block; font-size: 11px; font-weight: 700; margin-bottom: 3px; letter-spacing: 0.2px; }
#tab-stage_1 .gcap-g1 { border-color: #b08a4e; } #tab-stage_1 .gcap-g1 b { color: #b08a4e; }
#tab-stage_1 .gcap-g2 { border-color: #5a8a6a; } #tab-stage_1 .gcap-g2 b { color: #5a8a6a; }
#tab-stage_1 .gcap-g3 { border-color: #4a6a8a; } #tab-stage_1 .gcap-g3 b { color: #4a6a8a; }
#tab-stage_1 .gcap-g4 { border-color: #8a5a6a; } #tab-stage_1 .gcap-g4 b { color: #8a5a6a; }

#s1-main-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 11px; table-layout: fixed; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }
#s1-main-table thead { position: sticky; top: 0; z-index: 50; background: #fbfaf5; box-shadow: 0 2px 4px rgba(0,0,0,0.06); }
#s1-main-table thead th { background: #fbfaf5 !important; border-bottom: 1px solid #e0dcc8; padding: 7px 3px; text-align: center; font-weight: 600; font-size: 10px; color: #666; letter-spacing: 0.2px; cursor: pointer; user-select: none; line-height: 1.25; vertical-align: middle; }
#s1-main-table thead th:hover { background: #f0ebd9 !important; }
#s1-main-table thead .group-header-row th { background: #f3efe2 !important; font-size: 9.5px; text-transform: none; font-weight: 700; letter-spacing: 0.2px; padding: 5px 3px; cursor: default; white-space: normal; line-height: 1.25; }
#s1-main-table thead .group-header-row th:hover { background: #f3efe2 !important; }
#s1-main-table thead tr.group-header-row th { position: sticky; top: 0; }
#s1-main-table thead tr.col-header-row  th { position: sticky; top: 28px; border-top: 1px solid #e0dcc8; }
#s1-main-table thead .gh-inputs { color: #555; }
/* MD-V2-S40-INPUTS-LIVE-COUNT: live row count appended to 'Inputs' supergroup
   column-header. Slightly muted relative to the label. */
th.gh-inputs .inputs-count { font-weight: 500; color: #888; margin-left: 4px; font-variant-numeric: tabular-nums; }
#s1-main-table thead .gh-rating, #s1-main-table thead .gh-persist { color: #1b5e20; }
#s1-main-table thead .gh-g1 { color: #b08a4e; }
#s1-main-table thead .gh-g2 { color: #5a8a6a; }
#s1-main-table thead .gh-g3 { color: #4a6a8a; }
#s1-main-table thead .gh-g4 { color: #8a5a6a; }
#s1-main-table .hd { display: inline-flex; align-items: center; justify-content: center; gap: 3px; width: 100%; }
#s1-main-table .hd .lbl { white-space: normal; word-break: break-word; }
#s1-main-table .hd .sort-arrow { font-size: 9px; color: #1b5e20; flex: 0 0 auto; line-height: 1; }
#s1-main-table .hd .sort-placeholder { width: 9px; flex: 0 0 auto; }

#s1-main-table td { padding: 5px 4px; border-bottom: 1px solid #efece0; text-align: center; vertical-align: middle; height: 38px; box-sizing: border-box; font-variant-numeric: tabular-nums; }
#s1-main-table tr:hover { background: rgba(27,94,32,0.04); }

#s1-main-table td.grp-start-g1, #s1-main-table th.grp-start-g1 { border-left: 2px solid rgba(176,138,78,0.35); }
#s1-main-table td.grp-start-g2, #s1-main-table th.grp-start-g2 { border-left: 2px solid rgba(90,138,106,0.35); }
#s1-main-table td.grp-start-g3, #s1-main-table th.grp-start-g3 { border-left: 2px solid rgba(74,106,138,0.35); }
#s1-main-table td.grp-start-g4, #s1-main-table th.grp-start-g4 { border-left: 2px solid rgba(138,90,106,0.35); }
#s1-main-table td.grp-start-rating, #s1-main-table th.grp-start-rating { border-left: 2px solid rgba(27,94,32,0.35); }
#s1-main-table td.grp-start-persist, #s1-main-table th.grp-start-persist { border-left: 2px solid rgba(27,94,32,0.35); }
#s1-main-table td.grp-end-g1, #s1-main-table th.grp-end-g1 { border-right: 2px solid rgba(176,138,78,0.35); }
#s1-main-table td.grp-end-g2, #s1-main-table th.grp-end-g2 { border-right: 2px solid rgba(90,138,106,0.35); }
#s1-main-table td.grp-end-g3, #s1-main-table th.grp-end-g3 { border-right: 2px solid rgba(74,106,138,0.35); }
#s1-main-table td.grp-end-g4, #s1-main-table th.grp-end-g4 { border-right: 2px solid rgba(138,90,106,0.35); }
#s1-main-table td.test-pass { background: rgba(27,94,32,0.08); color: #1b5e20; font-weight: 700; }
#s1-main-table td.test-fail { color: #999; }
#s1-main-table td.test-val  { font-size: 10px; }
#s1-main-table td.name-cell { text-align: left; padding: 4px 4px 4px 8px; line-height: 1.15; }
#s1-main-table td.name-cell .co { font-weight: 700; font-size: 11px; color: #2a2a2a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#s1-main-table td.name-cell .tk { font-size: 9px; color: #999; font-weight: 500; margin-top: 1px; }
#s1-main-table td.name-cell .live-dot { color: #1b5e20; font-weight: 700; margin-right: 4px; display: inline-block; vertical-align: middle; line-height: 1; font-size: 10px; }
#s1-main-table td.taxon { text-align: left; font-size: 9px; line-height: 1.2; padding: 4px; }
#s1-main-table td.taxon .ind { color: #666; font-weight: 500; }
#s1-main-table td.taxon .sec { color: #999; }

#s1-main-table col.c-name { width: 130px; }
#s1-main-table col.c-taxon { width: 170px; }
#s1-main-table col.c-price { width: 56px; }
#s1-main-table col.c-52wh { width: 54px; }
#s1-main-table col.c-52wl { width: 54px; }
#s1-main-table col.c-ma150 { width: 54px; }
#s1-main-table col.c-ma200 { width: 54px; }
#s1-main-table col.c-rating { width: 100px; }
#s1-main-table col.c-score { width: 120px; }
#s1-main-table col.c-test { width: 50px; }
#s1-main-table col.c-persist { width: 110px; }

#s1-main-table .pill { display: inline-block; padding: 3px 9px; border-radius: 11px; font-weight: 700; font-size: 10px; color: white; letter-spacing: 0.3px; white-space: nowrap; }
#s1-main-table .pill-pl-5 { background: #2e7d32; color: #fff; }
#s1-main-table .pill-pl-6 { background: #1e6a25; color: #fff; }
#s1-main-table .pill-pl-7 { background: #145718; color: #fff; }
#s1-main-table .pill-pl-8 { background: #08400d; color: #fff; }
#s1-main-table .pill-pe   { background: #4a9658; color: #fff; }
#s1-main-table .pill-pla  { background: #6b8a98; color: #fff; }
#s1-main-table .pill-pos  { background: #c4c0b0; color: #5a5a4a; font-weight: 600; }
#s1-main-table .pill-none { background: #e0ddd0; color: #8a8676; font-weight: 600; }

#s1-main-table .score-pip-row { display: inline-flex; gap: 2px; align-items: center; }
#s1-main-table .pip { width: 7px; height: 7px; border-radius: 50%; background: #ddd; display: inline-block; }
#s1-main-table .pip.on { background: #1b5e20; }
#s1-main-table .pip.gate-ok{background:#1b5e20}
#s1-main-table .pip.gate-x{background:#8B0000;position:relative}
#s1-main-table .pip.gate-x::after{content:"\00D7";position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);color:#fff;font-size:6px;font-weight:900;line-height:1}
#s1-main-table .score-num { font-weight: 700; color: #1b5e20; margin-left: 5px; font-size: 11px; font-variant-numeric: tabular-nums; }

#s1-main-table .persist-row { display: inline-flex; gap: 1px; align-items: center; }
#s1-main-table .persist-cell { width: 7px; height: 11px; background: #ece8d8; border-radius: 1px; }
#s1-main-table .persist-cell.r-pos  { background: #c4c0b0; }
#s1-main-table .persist-cell.r-pla  { background: #6b8a98; }
#s1-main-table .persist-cell.r-pe   { background: #4a9658; }
#s1-main-table .persist-cell.r-pl   { background: #145718; width: 8px; height: 13px; box-shadow: inset 0 0 0 1px #08400d; }
#s1-main-table .persist-cell.r-none { background: #ece8d8; }

#s1-main-table tr.tint-row td.name-cell, #s1-main-table tr.tint-row td.taxon { background: var(--tint-bg) !important; }
#s1-main-table tr.portfolio-band td:last-child { border-right: 4px solid var(--portfolio-color); }
#s1-main-table tr.portfolio-tint { background: var(--portfolio-bg); }
#s1-main-table tr.portfolio-tint:hover { background: var(--portfolio-bg-hover); }
/* MD-V2-STAGE1-MARKER-CSS-END */

/* MD-V2-STAGE2-MARKER-CSS-START */
/* Reuse #s1-* class names - Stage 2 uses the SAME chrome classes.
   Add only: Group 5 purple band; Probable pill ramp 7 to 10; 4-rating tile tints;
   Stage 2 table selectors mirroring #s1-main-table. */
#tab-stage_2 .group-captions .gcap-g5 { border-color: #6a5a8a; }
#tab-stage_2 .group-captions .gcap-g5 b { color: #6a5a8a; }
#tab-stage_2 .s1-rating-tiles .rating-tile.tint-prob { background: rgba(20, 87, 24, 0.08); }
#tab-stage_2 .s1-rating-tiles .rating-tile.tint-pla  { background: rgba(107, 138, 152, 0.08); }
#tab-stage_2 .s1-rating-tiles .rating-tile.tint-pos  { background: rgba(196, 192, 176, 0.18); }
#tab-stage_2 .s1-rating-tiles .rating-tile.tint-none { background: rgba(224, 221, 208, 0.30); }
#tab-stage_2 .s1-rating-tiles .rt-strip-prob { background: #145718; }
#tab-stage_2 .s1-rating-tiles .rt-strip-pla  { background: #6b8a98; }
#tab-stage_2 .s1-rating-tiles .rt-strip-pos  { background: #c4c0b0; }
#tab-stage_2 .s1-rating-tiles .rt-strip-none { background: #e0ddd0; }

/* Stage 2 main table - mirror all #s1-main-table styles via duplicate selectors */
#s2-main-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 11px; table-layout: fixed; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }
#s2-main-table thead { position: sticky; top: 0; z-index: 50; background: #fbfaf5; box-shadow: 0 2px 4px rgba(0,0,0,0.06); }
#s2-main-table thead th { background: #fbfaf5 !important; border-bottom: 1px solid #e0dcc8; padding: 7px 3px; text-align: center; font-weight: 600; font-size: 10px; color: #666; letter-spacing: 0.2px; cursor: pointer; user-select: none; line-height: 1.25; vertical-align: middle; }
#s2-main-table thead th:hover { background: #f0ebd9 !important; }
#s2-main-table thead .group-header-row th { background: #f3efe2 !important; font-size: 9.5px; text-transform: none; font-weight: 700; letter-spacing: 0.2px; padding: 5px 3px; cursor: default; white-space: normal; line-height: 1.25; }
#s2-main-table thead .group-header-row th:hover { background: #f3efe2 !important; }
#s2-main-table thead tr.group-header-row th { position: sticky; top: 0; }
#s2-main-table thead tr.col-header-row  th { position: sticky; top: 28px; border-top: 1px solid #e0dcc8; }
#s2-main-table thead .gh-inputs { color: #555; }
#s2-main-table thead .gh-rating, #s2-main-table thead .gh-persist { color: #2e7d32; }
#s2-main-table thead .gh-g1 { color: #b08a4e; }
#s2-main-table thead .gh-g2 { color: #5a8a6a; }
#s2-main-table thead .gh-g3 { color: #4a6a8a; }
#s2-main-table thead .gh-g4 { color: #8a5a6a; }
#s2-main-table thead .gh-g5 { color: #6a5a8a; }
#s2-main-table .hd { display: inline-flex; align-items: center; justify-content: center; gap: 3px; width: 100%; }
#s2-main-table .hd .lbl { white-space: normal; word-break: break-word; }
#s2-main-table .hd .sort-arrow { font-size: 9px; color: #2e7d32; flex: 0 0 auto; line-height: 1; }
#s2-main-table .hd .sort-placeholder { width: 9px; flex: 0 0 auto; }
#s2-main-table td { padding: 5px 4px; border-bottom: 1px solid #efece0; text-align: center; vertical-align: middle; height: 38px; box-sizing: border-box; font-variant-numeric: tabular-nums; }
#s2-main-table tr:hover { background: rgba(27,94,32,0.04); }
#s2-main-table td.grp-start-g1, #s2-main-table th.grp-start-g1 { border-left: 2px solid rgba(176,138,78,0.35); }
#s2-main-table td.grp-start-g2, #s2-main-table th.grp-start-g2 { border-left: 2px solid rgba(90,138,106,0.35); }
#s2-main-table td.grp-start-g3, #s2-main-table th.grp-start-g3 { border-left: 2px solid rgba(74,106,138,0.35); }
#s2-main-table td.grp-start-g4, #s2-main-table th.grp-start-g4 { border-left: 2px solid rgba(138,90,106,0.35); }
#s2-main-table td.grp-start-g5, #s2-main-table th.grp-start-g5 { border-left: 2px solid rgba(106,90,138,0.35); }
#s2-main-table td.grp-start-rating, #s2-main-table th.grp-start-rating { border-left: 2px solid rgba(27,94,32,0.35); }
#s2-main-table td.grp-start-persist, #s2-main-table th.grp-start-persist { border-left: 2px solid rgba(27,94,32,0.35); }
#s2-main-table td.grp-end-g1, #s2-main-table th.grp-end-g1 { border-right: 2px solid rgba(176,138,78,0.35); }
#s2-main-table td.grp-end-g2, #s2-main-table th.grp-end-g2 { border-right: 2px solid rgba(90,138,106,0.35); }
#s2-main-table td.grp-end-g3, #s2-main-table th.grp-end-g3 { border-right: 2px solid rgba(74,106,138,0.35); }
#s2-main-table td.grp-end-g4, #s2-main-table th.grp-end-g4 { border-right: 2px solid rgba(138,90,106,0.35); }
#s2-main-table td.grp-end-g5, #s2-main-table th.grp-end-g5 { border-right: 2px solid rgba(106,90,138,0.35); }
#s2-main-table td.test-pass { background: rgba(27,94,32,0.08); color: #1b5e20; font-weight: 700; }
#s2-main-table td.test-fail { color: #999; }
#s2-main-table td.test-val  { font-size: 10px; }
#s2-main-table td.name-cell { text-align: left; padding: 4px 4px 4px 8px; line-height: 1.15; }
#s2-main-table td.name-cell .co { font-weight: 700; font-size: 11px; color: #2a2a2a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#s2-main-table td.name-cell .tk { font-size: 9px; color: #999; font-weight: 500; margin-top: 1px; }
#s2-main-table td.name-cell .live-dot { color: #2e7d32; font-weight: 700; margin-right: 4px; display: inline-block; vertical-align: middle; line-height: 1; font-size: 10px; }
#s2-main-table td.taxon { text-align: left; font-size: 9px; line-height: 1.2; padding: 4px; }
#s2-main-table td.taxon .ind { color: #666; font-weight: 500; }
#s2-main-table td.taxon .sec { color: #999; }
#s2-main-table col.c-name { width: 130px; }
#s2-main-table col.c-taxon { width: 170px; }
#s2-main-table col.c-price { width: 56px; }
#s2-main-table col.c-52wh { width: 54px; }
#s2-main-table col.c-52wl { width: 54px; }
#s2-main-table col.c-ma150 { width: 54px; }
#s2-main-table col.c-ma200 { width: 54px; }
#s2-main-table col.c-rating { width: 100px; }
#s2-main-table col.c-score { width: 96px; }
#s2-main-table col.c-test { width: 44px; }
#s2-main-table col.c-persist { width: 110px; }
#s2-main-table .pill { display: inline-block; padding: 3px 9px; border-radius: 11px; font-weight: 700; font-size: 10px; color: white; letter-spacing: 0.3px; white-space: nowrap; }
#s2-main-table .pill-prob-7  { background: #2e7d32; color: #fff; }
#s2-main-table .pill-prob-8  { background: #1e6a25; color: #fff; }
#s2-main-table .pill-prob-9  { background: #145718; color: #fff; }
#s2-main-table .pill-prob-10 { background: #08400d; color: #fff; }
#s2-main-table .pill-pla     { background: #6b8a98; color: #fff; }
#s2-main-table .pill-pos     { background: #c4c0b0; color: #5a5a4a; font-weight: 600; }
#s2-main-table .pill-none    { background: #e0ddd0; color: #8a8676; font-weight: 600; }
#s2-main-table .score-pip-row { display: inline-flex; gap: 2px; align-items: center; }
#s2-main-table .pip { width: 6px; height: 6px; border-radius: 50%; background: #ddd; display: inline-block; }
#s2-main-table .pip.on { background: #2e7d32; }
#s2-main-table .pip.rs-on { background: #6b46c1; } /* MD-V2-S49-RS-PIP-COLOUR: RS group (G5) pips purple */
#s2-main-table .pip.gate-ok{background:#2e7d32}
#s2-main-table .pip.gate-x{background:#8B0000;position:relative}
#s2-main-table .pip.gate-x::after{content:"\00D7";position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);color:#fff;font-size:5px;font-weight:900;line-height:1}
#s2-main-table .score-num { font-weight: 700; color: #2e7d32; margin-left: 5px; font-size: 11px; font-variant-numeric: tabular-nums; }
#s2-main-table .persist-row { display: inline-flex; gap: 1px; align-items: center; }
#s2-main-table .persist-cell { width: 7px; height: 11px; background: #ece8d8; border-radius: 1px; }
#s2-main-table .persist-cell.r-prob { background: #145718; width: 8px; height: 13px; box-shadow: inset 0 0 0 1px #08400d; }
#s2-main-table .persist-cell.r-pla  { background: #6b8a98; }
#s2-main-table .persist-cell.r-pos  { background: #c4c0b0; }
#s2-main-table .persist-cell.r-none { background: #ece8d8; }
#s2-main-table tr.tint-row td.name-cell, #s2-main-table tr.tint-row td.taxon { background: var(--tint-bg) !important; }
#s2-main-table tr.portfolio-band td:last-child { border-right: 4px solid var(--portfolio-color); }
#s2-main-table tr.portfolio-tint { background: var(--portfolio-bg); }
#s2-main-table tr.portfolio-tint:hover { background: var(--portfolio-bg-hover); }
/* MD-V2-STAGE2-MARKER-CSS-END */

/* MD-V2-STAGE3-MARKER-CSS-START */
/* Stage 3 (Topping / Invalidation) - bearish palette: amber to deep red. */
#tab-stage_3 .group-captions .gcap-g1 { border-color: #d97706; }
#tab-stage_3 .group-captions .gcap-g1 b { color: #b45309; }
#tab-stage_3 .group-captions .gcap-g2 { border-color: #c2410c; }
#tab-stage_3 .group-captions .gcap-g2 b { color: #9a3412; }
#tab-stage_3 .group-captions .gcap-g3 { border-color: #b91c1c; }
#tab-stage_3 .group-captions .gcap-g3 b { color: #991b1b; }
#tab-stage_3 .group-captions .gcap-g4 { border-color: #7c2d12; }
#tab-stage_3 .group-captions .gcap-g4 b { color: #7c2d12; }
#tab-stage_3 .group-captions .gcap-g5 { border-color: #6a5a8a; }
#tab-stage_3 .group-captions .gcap-g5 b { color: #6a5a8a; }

/* Rating tile tints - bearish */
#tab-stage_3 .s1-rating-tiles .rating-tile.tint-prob { background: rgba(153, 27, 27, 0.10); }
#tab-stage_3 .s1-rating-tiles .rating-tile.tint-pla  { background: rgba(180, 83, 9, 0.10); }
#tab-stage_3 .s1-rating-tiles .rating-tile.tint-pos  { background: rgba(217, 119, 6, 0.10); }
#tab-stage_3 .s1-rating-tiles .rating-tile.tint-none { background: rgba(224, 221, 208, 0.30); }
#tab-stage_3 .s1-rating-tiles .rt-strip-prob-inv { background: #7f1d1d; }
#tab-stage_3 .s1-rating-tiles .rt-strip-pla-inv  { background: #b45309; }
#tab-stage_3 .s1-rating-tiles .rt-strip-pos-top  { background: #d97706; }
#tab-stage_3 .s1-rating-tiles .rt-strip-none     { background: #e0ddd0; }

/* Stage 3 main table - mirror all #s1-main-table styles via duplicate selectors */
#s3-main-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 11px; table-layout: fixed; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }
#s3-main-table thead { position: sticky; top: 0; z-index: 50; background: #fbfaf5; box-shadow: 0 2px 4px rgba(0,0,0,0.06); }
#s3-main-table thead th { background: #fbfaf5 !important; border-bottom: 1px solid #e0dcc8; padding: 7px 3px; text-align: center; font-weight: 600; font-size: 10px; color: #666; letter-spacing: 0.2px; cursor: pointer; user-select: none; line-height: 1.25; vertical-align: middle; }
#s3-main-table thead th:hover { background: #f0ebd9 !important; }
#s3-main-table thead .group-header-row th { background: #f3efe2 !important; font-size: 9.5px; text-transform: none; font-weight: 700; letter-spacing: 0.2px; padding: 5px 3px; cursor: default; white-space: normal; line-height: 1.25; }
#s3-main-table thead .group-header-row th:hover { background: #f3efe2 !important; }
#s3-main-table thead tr.group-header-row th { position: sticky; top: 0; }
#s3-main-table thead tr.col-header-row  th { position: sticky; top: 28px; border-top: 1px solid #e0dcc8; }
#s3-main-table thead .gh-inputs { color: #555; }
#s3-main-table thead .gh-rating, #s3-main-table thead .gh-persist { color: #b45309; }
#s3-main-table thead .gh-g1 { color: #b45309; }
#s3-main-table thead .gh-g2 { color: #9a3412; }
#s3-main-table thead .gh-g3 { color: #991b1b; }
#s3-main-table thead .gh-g4 { color: #7c2d12; }
#s3-main-table thead .gh-g5 { color: #6a5a8a; }
#s3-main-table .hd { display: inline-flex; align-items: center; justify-content: center; gap: 3px; width: 100%; }
#s3-main-table .hd .lbl { white-space: normal; word-break: break-word; }
#s3-main-table .hd .sort-arrow { font-size: 9px; color: #b45309; flex: 0 0 auto; line-height: 1; }
#s3-main-table .hd .sort-placeholder { width: 9px; flex: 0 0 auto; }
#s3-main-table td { padding: 5px 4px; border-bottom: 1px solid #efece0; text-align: center; vertical-align: middle; height: 38px; box-sizing: border-box; font-variant-numeric: tabular-nums; }
#s3-main-table tr:hover { background: rgba(180,83,9,0.05); }

/* Group borders - bearish palette */
#s3-main-table td.grp-start-g1, #s3-main-table th.grp-start-g1 { border-left: 2px solid rgba(180,83,9,0.35); }
#s3-main-table td.grp-start-g2, #s3-main-table th.grp-start-g2 { border-left: 2px solid rgba(154,52,18,0.35); }
#s3-main-table td.grp-start-g3, #s3-main-table th.grp-start-g3 { border-left: 2px solid rgba(153,27,27,0.35); }
#s3-main-table td.grp-start-g4, #s3-main-table th.grp-start-g4 { border-left: 2px solid rgba(124,45,18,0.35); }
#s3-main-table td.grp-start-g5, #s3-main-table th.grp-start-g5 { border-left: 2px solid rgba(106,90,138,0.35); }
#s3-main-table td.grp-start-rating, #s3-main-table th.grp-start-rating { border-left: 2px solid rgba(180,83,9,0.35); }
#s3-main-table td.grp-start-persist, #s3-main-table th.grp-start-persist { border-left: 2px solid rgba(180,83,9,0.35); }
#s3-main-table td.grp-end-g1, #s3-main-table th.grp-end-g1 { border-right: 2px solid rgba(180,83,9,0.35); }
#s3-main-table td.grp-end-g2, #s3-main-table th.grp-end-g2 { border-right: 2px solid rgba(154,52,18,0.35); }
#s3-main-table td.grp-end-g3, #s3-main-table th.grp-end-g3 { border-right: 2px solid rgba(153,27,27,0.35); }
#s3-main-table td.grp-end-g4, #s3-main-table th.grp-end-g4 { border-right: 2px solid rgba(124,45,18,0.35); }
#s3-main-table td.grp-end-g5, #s3-main-table th.grp-end-g5 { border-right: 2px solid rgba(106,90,138,0.35); }

/* Test cells - bearish: pass = red-tinted (because passing a topping test is bad news) */
#s3-main-table td.test-pass-bear { background: rgba(153,27,27,0.08); color: #991b1b; font-weight: 700; }
#s3-main-table td.test-fail { color: #999; }
#s3-main-table td.test-val  { font-size: 10px; }

#s3-main-table td.name-cell { text-align: left; padding: 4px 4px 4px 8px; line-height: 1.15; }
#s3-main-table td.name-cell .co { font-weight: 700; font-size: 11px; color: #2a2a2a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#s3-main-table td.name-cell .tk { font-size: 9px; color: #999; font-weight: 500; margin-top: 1px; }
#s3-main-table td.name-cell .live-dot { color: #2e7d32; font-weight: 700; margin-right: 4px; display: inline-block; vertical-align: middle; line-height: 1; font-size: 10px; }
#s3-main-table td.taxon { text-align: left; font-size: 9px; line-height: 1.2; padding: 4px; }
#s3-main-table td.taxon .ind { color: #666; font-weight: 500; }
#s3-main-table td.taxon .sec { color: #999; }
#s3-main-table col.c-name { width: 130px; }
#s3-main-table col.c-taxon { width: 170px; }
#s3-main-table col.c-price { width: 56px; }
#s3-main-table col.c-52wh { width: 54px; }
#s3-main-table col.c-52wl { width: 54px; }
#s3-main-table col.c-ma150 { width: 54px; }
#s3-main-table col.c-ma200 { width: 54px; }
#s3-main-table col.c-rating { width: 110px; }
#s3-main-table col.c-score { width: 96px; }
#s3-main-table col.c-test { width: 44px; }
#s3-main-table col.c-persist { width: 110px; }

/* Pills - bearish ramp. Probable Inv. ramps deep red 6-10 tests passed. */
#s3-main-table .pill { display: inline-block; padding: 3px 9px; border-radius: 11px; font-weight: 700; font-size: 10px; color: white; letter-spacing: 0.3px; white-space: nowrap; }
#s3-main-table .pill-prob-inv-6  { background: #991b1b; color: #fff; }
#s3-main-table .pill-prob-inv-7  { background: #8b1414; color: #fff; }
#s3-main-table .pill-prob-inv-8  { background: #7f1d1d; color: #fff; }
#s3-main-table .pill-prob-inv-9  { background: #6e0f0f; color: #fff; }
#s3-main-table .pill-prob-inv-10 { background: #5a0808; color: #fff; }
#s3-main-table .pill-pla-inv     { background: #b45309; color: #fff; }
#s3-main-table .pill-pos-top     { background: #d97706; color: #fff; font-weight: 600; }
#s3-main-table .pill-none        { background: #e0ddd0; color: #8a8676; font-weight: 600; }

/* Score pips - bearish red */
#s3-main-table .score-pip-row { display: inline-flex; gap: 2px; align-items: center; }
#s3-main-table .pip.pip-bear { width: 6px; height: 6px; border-radius: 50%; background: #ddd; display: inline-block; }
#s3-main-table .pip.pip-bear.on { background: #991b1b; }
#s3-main-table .pip.pip-bear.gate-ok{background:#991b1b}
#s3-main-table .pip.pip-bear.gate-x{background:#8B0000;position:relative}
#s3-main-table .pip.pip-bear.gate-x::after{content:"\00D7";position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);color:#fff;font-size:5px;font-weight:900;line-height:1}
#s3-main-table .score-num { font-weight: 700; color: #991b1b; margin-left: 5px; font-size: 11px; font-variant-numeric: tabular-nums; }

/* Persistence cells - bearish */
#s3-main-table .persist-row { display: inline-flex; gap: 1px; align-items: center; }
#s3-main-table .persist-cell { width: 7px; height: 11px; background: #ece8d8; border-radius: 1px; }
#s3-main-table .persist-cell.r-prob-inv { background: #7f1d1d; width: 8px; height: 13px; box-shadow: inset 0 0 0 1px #5a0808; }
#s3-main-table .persist-cell.r-pla-inv  { background: #b45309; }
#s3-main-table .persist-cell.r-pos-top  { background: #d97706; }
#s3-main-table .persist-cell.r-none     { background: #ece8d8; }

#s3-main-table tr.tint-row td.name-cell, #s3-main-table tr.tint-row td.taxon { background: var(--tint-bg) !important; }
#s3-main-table tr.portfolio-band td:last-child { border-right: 4px solid var(--portfolio-color); }
#s3-main-table tr.portfolio-tint { background: var(--portfolio-bg); }
#s3-main-table tr.portfolio-tint:hover { background: var(--portfolio-bg-hover); }
/* MD-V2-STAGE3-MARKER-CSS-END */

/* MD-V2-STAGE4-MARKER-CSS-START */
/* Stage 4 (Decline / Capitulation) - deep-red palette across all 3 groups. */
#tab-stage_4 .group-captions .gcap-g1 { border-color: #991b1b; }
#tab-stage_4 .group-captions .gcap-g1 b { color: #991b1b; }
#tab-stage_4 .group-captions .gcap-g2 { border-color: #7f1d1d; }
#tab-stage_4 .group-captions .gcap-g2 b { color: #7f1d1d; }
#tab-stage_4 .group-captions .gcap-g3 { border-color: #6a5a8a; }
#tab-stage_4 .group-captions .gcap-g3 b { color: #6a5a8a; }

/* Rating tile tints - deep red */
#tab-stage_4 .s1-rating-tiles .rating-tile.tint-prob { background: rgba(127, 29, 29, 0.12); }
#tab-stage_4 .s1-rating-tiles .rating-tile.tint-pla  { background: rgba(153, 27, 27, 0.10); }
#tab-stage_4 .s1-rating-tiles .rating-tile.tint-pos  { background: rgba(180, 83, 9, 0.10); }
#tab-stage_4 .s1-rating-tiles .rating-tile.tint-none { background: rgba(224, 221, 208, 0.30); }
#tab-stage_4 .s1-rating-tiles .rt-strip-prob { background: #5a0808; }
#tab-stage_4 .s1-rating-tiles .rt-strip-pla  { background: #991b1b; }
#tab-stage_4 .s1-rating-tiles .rt-strip-pos  { background: #b45309; }
#tab-stage_4 .s1-rating-tiles .rt-strip-none { background: #e0ddd0; }

/* Stage 4 main table - mirror all #s1-main-table styles via duplicate selectors */
#s4-main-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 11px; table-layout: fixed; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }
#s4-main-table thead { position: sticky; top: 0; z-index: 50; background: #fbfaf5; box-shadow: 0 2px 4px rgba(0,0,0,0.06); }
#s4-main-table thead th { background: #fbfaf5 !important; border-bottom: 1px solid #e0dcc8; padding: 7px 3px; text-align: center; font-weight: 600; font-size: 10px; color: #666; letter-spacing: 0.2px; cursor: pointer; user-select: none; line-height: 1.25; vertical-align: middle; }
#s4-main-table thead th:hover { background: #f0ebd9 !important; }
#s4-main-table thead .group-header-row th { background: #f3efe2 !important; font-size: 9.5px; text-transform: none; font-weight: 700; letter-spacing: 0.2px; padding: 5px 3px; cursor: default; white-space: normal; line-height: 1.25; }
#s4-main-table thead .group-header-row th:hover { background: #f3efe2 !important; }
#s4-main-table thead tr.group-header-row th { position: sticky; top: 0; }
#s4-main-table thead tr.col-header-row  th { position: sticky; top: 28px; border-top: 1px solid #e0dcc8; }
#s4-main-table thead .gh-inputs { color: #555; }
#s4-main-table thead .gh-rating, #s4-main-table thead .gh-persist { color: #991b1b; }
#s4-main-table thead .gh-g1 { color: #991b1b; }
#s4-main-table thead .gh-g2 { color: #7f1d1d; }
#s4-main-table thead .gh-g3 { color: #6a5a8a; }
#s4-main-table .hd { display: inline-flex; align-items: center; justify-content: center; gap: 3px; width: 100%; }
#s4-main-table .hd .lbl { white-space: normal; word-break: break-word; }
#s4-main-table .hd .sort-arrow { font-size: 9px; color: #991b1b; flex: 0 0 auto; line-height: 1; }
#s4-main-table .hd .sort-placeholder { width: 9px; flex: 0 0 auto; }
#s4-main-table td { padding: 5px 4px; border-bottom: 1px solid #efece0; text-align: center; vertical-align: middle; height: 38px; box-sizing: border-box; font-variant-numeric: tabular-nums; }
#s4-main-table tr:hover { background: rgba(153,27,27,0.05); }

/* Group borders - deep red palette */
#s4-main-table td.grp-start-g1, #s4-main-table th.grp-start-g1 { border-left: 2px solid rgba(153,27,27,0.40); }
#s4-main-table td.grp-start-g2, #s4-main-table th.grp-start-g2 { border-left: 2px solid rgba(127,29,29,0.40); }
#s4-main-table td.grp-start-g3, #s4-main-table th.grp-start-g3 { border-left: 2px solid rgba(106,90,138,0.35); }
#s4-main-table td.grp-start-rating, #s4-main-table th.grp-start-rating { border-left: 2px solid rgba(153,27,27,0.35); }
#s4-main-table td.grp-start-persist, #s4-main-table th.grp-start-persist { border-left: 2px solid rgba(153,27,27,0.35); }
#s4-main-table td.grp-end-g1, #s4-main-table th.grp-end-g1 { border-right: 2px solid rgba(153,27,27,0.40); }
#s4-main-table td.grp-end-g2, #s4-main-table th.grp-end-g2 { border-right: 2px solid rgba(127,29,29,0.40); }
#s4-main-table td.grp-end-g3, #s4-main-table th.grp-end-g3 { border-right: 2px solid rgba(106,90,138,0.35); }

/* Test cells - bearish: pass = deep-red-tinted */
#s4-main-table td.test-pass-bear { background: rgba(127,29,29,0.10); color: #7f1d1d; font-weight: 700; }
#s4-main-table td.test-fail { color: #999; }
#s4-main-table td.test-val  { font-size: 10px; }
/* MD-V2-WAVE4-TEST-VALUES-TOGGLE-MARKER */
#pi-main-table td.test-val { font-size: 10px; }
#po-main-table td.test-val { font-size: 10px; }
.st-main-table td.test-val { font-size: 10px; }
#ct-main-table td.test-val { font-size: 10px; }

#s4-main-table td.name-cell { text-align: left; padding: 4px 4px 4px 8px; line-height: 1.15; }
#s4-main-table td.name-cell .co { font-weight: 700; font-size: 11px; color: #2a2a2a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#s4-main-table td.name-cell .tk { font-size: 9px; color: #999; font-weight: 500; margin-top: 1px; }
#s4-main-table td.name-cell .live-dot { color: #2e7d32; font-weight: 700; margin-right: 4px; display: inline-block; vertical-align: middle; line-height: 1; font-size: 10px; }
#s4-main-table td.taxon { text-align: left; font-size: 9px; line-height: 1.2; padding: 4px; }
#s4-main-table td.taxon .ind { color: #666; font-weight: 500; }
#s4-main-table td.taxon .sec { color: #999; }
#s4-main-table col.c-name { width: 130px; }
#s4-main-table col.c-taxon { width: 170px; }
#s4-main-table col.c-price { width: 56px; }
#s4-main-table col.c-52wh { width: 54px; }
#s4-main-table col.c-52wl { width: 54px; }
#s4-main-table col.c-ma150 { width: 54px; }
#s4-main-table col.c-ma200 { width: 54px; }
#s4-main-table col.c-rating { width: 100px; }
#s4-main-table col.c-score { width: 84px; }
#s4-main-table col.c-test { width: 48px; }
#s4-main-table col.c-persist { width: 110px; }

/* Pills - deep red ramp. Probable ramps 3-7 tests passed. */
#s4-main-table .pill { display: inline-block; padding: 3px 9px; border-radius: 11px; font-weight: 700; font-size: 10px; color: white; letter-spacing: 0.3px; white-space: nowrap; }
#s4-main-table .pill-prob-3 { background: #991b1b; color: #fff; }
#s4-main-table .pill-prob-4 { background: #8b1414; color: #fff; }
#s4-main-table .pill-prob-5 { background: #7f1d1d; color: #fff; }
#s4-main-table .pill-prob-6 { background: #6e0f0f; color: #fff; }
#s4-main-table .pill-prob-7 { background: #5a0808; color: #fff; }
#s4-main-table .pill-pla    { background: #b45309; color: #fff; }
#s4-main-table .pill-pos    { background: #d97706; color: #fff; font-weight: 600; }
#s4-main-table .pill-none   { background: #e0ddd0; color: #8a8676; font-weight: 600; }

/* Score pips - deep red */
#s4-main-table .score-pip-row { display: inline-flex; gap: 2px; align-items: center; }
#s4-main-table .pip.pip-bear { width: 6px; height: 6px; border-radius: 50%; background: #ddd; display: inline-block; }
#s4-main-table .pip.pip-bear.on { background: #7f1d1d; }
#s4-main-table .pip.pip-bear.gate-ok{background:#7f1d1d}
#s4-main-table .pip.pip-bear.gate-x{background:#8B0000;position:relative}
#s4-main-table .pip.pip-bear.gate-x::after{content:"\00D7";position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);color:#fff;font-size:5px;font-weight:900;line-height:1}
#s4-main-table .score-num { font-weight: 700; color: #7f1d1d; margin-left: 5px; font-size: 11px; font-variant-numeric: tabular-nums; }

/* Persistence cells - deep red */
#s4-main-table .persist-row { display: inline-flex; gap: 1px; align-items: center; }
#s4-main-table .persist-cell { width: 7px; height: 11px; background: #ece8d8; border-radius: 1px; }
#s4-main-table .persist-cell.r-prob { background: #5a0808; width: 8px; height: 13px; box-shadow: inset 0 0 0 1px #3a0202; }
#s4-main-table .persist-cell.r-pla  { background: #991b1b; }
#s4-main-table .persist-cell.r-pos  { background: #b45309; }
#s4-main-table .persist-cell.r-none { background: #ece8d8; }

#s4-main-table tr.tint-row td.name-cell, #s4-main-table tr.tint-row td.taxon { background: var(--tint-bg) !important; }
#s4-main-table tr.portfolio-band td:last-child { border-right: 4px solid var(--portfolio-color); }
#s4-main-table tr.portfolio-tint { background: var(--portfolio-bg); }
#s4-main-table tr.portfolio-tint:hover { background: var(--portfolio-bg-hover); }
/* MD-V2-STAGE4-MARKER-CSS-END */

/* MD-V2-CHROME-PARITY-MARKER-CSS-START */
/* ===== Legacy chrome suppression on V2 tabs ===== */
body[data-active-tab^="stage_"] .header-tabs-row,
body[data-active-tab="pre_indicators"] .header-tabs-row,
body[data-active-tab="post_indicators"] .header-tabs-row,
body[data-active-tab^="setups"] .header-tabs-row,
body[data-active-tab="tests"] .header-tabs-row,
body[data-active-tab="tests_healthy_vcp"] .header-tabs-row,
body[data-active-tab="tests_speculative_bet"] .header-tabs-row,
body[data-active-tab="tests_probing_bet_s1"] .header-tabs-row,
body[data-active-tab="tests_probing_bet_s2"] .header-tabs-row,
body[data-active-tab="setups_healthy_retest"] .header-tabs-row,
body[data-active-tab="master_overview"] .header-tabs-row { display: none !important; }

/* V2 mini nav strip - visible only on V2 tabs */
.v2-nav { display: none; padding: 8px 12px; background: #fbfaf5; border-bottom: 1px solid #e0dcc8; gap: 6px; align-items: center; }
body[data-active-tab^="stage_"] .v2-nav,
body[data-active-tab="pre_indicators"] .v2-nav,
body[data-active-tab="post_indicators"] .v2-nav,
body[data-active-tab^="setups"] .v2-nav,
body[data-active-tab="tests"] .v2-nav,
body[data-active-tab="tests_healthy_vcp"] .v2-nav,
body[data-active-tab="tests_speculative_bet"] .v2-nav,
body[data-active-tab="tests_probing_bet_s1"] .v2-nav,
body[data-active-tab="tests_probing_bet_s2"] .v2-nav,
body[data-active-tab="setups_healthy_retest"] .v2-nav,
body[data-active-tab="master_overview"] .v2-nav { display: flex; }
.v2-nav-label { font-size: 10px; color: #888; text-transform: uppercase; letter-spacing: 0.4px; font-weight: 600; margin-right: 8px; }
.v2-nav-btn { display: inline-block; padding: 5px 11px; font-size: 11px; font-weight: 600; color: #333; background: #fff; border: 1px solid #d0ccb8; border-radius: 4px; cursor: pointer; transition: background 0.15s, border-color 0.15s; }
.v2-nav-btn:hover { background: #f3efe2; border-color: #b0ac98; }
.v2-nav-btn.v2-active { background: #1b3d5c; border-color: #1b3d5c; color: #fff; }
.v2-nav-btn.v2-active-s1 { background: #1b5e20; border-color: #1b5e20; color: #fff; }
.v2-nav-btn.v2-active-s2 { background: #2e7d32; border-color: #2e7d32; color: #fff; }
.v2-nav-btn.v2-active-s3 { background: #b45309; border-color: #b45309; color: #fff; }
.v2-nav-btn.v2-active-s4 { background: #991b1b; border-color: #991b1b; color: #fff; }
.v2-nav-placeholder { display: inline-block; padding: 5px 11px; font-size: 11px; color: #aaa; background: #f0ece0; border: 1px dashed #d0ccb8; border-radius: 4px; cursor: default; }
/* MD-V2-PI-V2-S25-MARKER: EDIT 3 - Block B nav tier-grouping CSS (D-MD-V2-48). */
.v2-nav-grp-label { font-size: 9px; color: #8a8674; text-transform: uppercase; letter-spacing: 0.5px; font-weight: 700; margin: 0 4px 0 0; }
.v2-nav-sep { display: inline-block; width: auto; height: auto; background: none; margin: 0 6px; color: #8a8674; font-size: 13px; font-weight: 600; line-height: 1; vertical-align: middle; }
.v2-nav-sep::before { content: "\2192"; }  /* MD-V2-S36-BRIEF-MARKER right-arrow */
.v2-nav-btn.v2-grp-stages { border-bottom: 2px solid rgba(27,61,92,0.30); }
.v2-nav-btn.v2-grp-indicators { border-bottom: 2px solid rgba(15,110,86,0.45); }
.v2-nav-btn.v2-grp-setups { border-bottom: 2px solid rgba(123,104,174,0.55); }
.v2-nav-btn.v2-grp-tests { border-bottom: 2px solid rgba(180,83,9,0.55); }
.v2-nav-btn.v2-grp-indicators:hover { background: #e8f2ee; }
.v2-nav-btn.v2-grp-setups:hover { background: #efecf6; }
.v2-nav-btn.v2-grp-tests:hover { background: #f6efe6; }
/* MD-V2-S40-ANDROID-NAV-OVERFLOW-FIX: shrink v2-nav components on tablet widths so all
   group labels (incl. 'Capital deployment') and buttons fit on one row
   within the 70px fixed header without overflowing horizontally. */
@media (max-width: 1024px) {
  .v2-nav { gap: 4px; padding: 6px 8px; }
  .v2-nav-grp-label { font-size: 8px; letter-spacing: 0.2px; margin: 0 2px 0 0; }
  .v2-nav-btn { padding: 4px 8px; font-size: 10px; }
  .v2-nav-sep { margin: 0 3px; font-size: 11px; }
  .v2-nav-label { font-size: 9px; margin-right: 4px; }
}

/* MD-V2-S40-RESPONSIVE-SHORT-HEADERS: at narrow viewports (tablet + smaller), hide the long
   column-header label and show the short form via attr(data-short).
   Each MO_ROWS entry now carries `short:` alongside `label:`. */
@media (max-width: 1200px) {
  th.mo-col-with-short .mo-col-long { display: none; }
  th.mo-col-with-short::before { content: attr(data-short); }
}

/* ===== Group caption parity for Stage 2/3/4 ===== */
/* Stage 1 already styles .gcap inside .group-captions. Replicate for s2/s3/s4. */
#tab-stage_2 .group-captions,
#tab-stage_3 .group-captions,
#tab-stage_4 .group-captions {
  display: grid;
  gap: 10px;
  margin: 16px 0 14px 0;
}
#tab-stage_2 .group-captions .gcap,
#tab-stage_3 .group-captions .gcap,
#tab-stage_4 .group-captions .gcap {
  background: #fbfaf5;
  border: 1px solid #e0dcc8;
  border-left: 3px solid #b08a4e;
  border-radius: 4px;
  padding: 10px 12px;
  font-size: 11px;
  line-height: 1.45;
  color: #555;
}
#tab-stage_2 .group-captions .gcap b,
#tab-stage_3 .group-captions .gcap b,
#tab-stage_4 .group-captions .gcap b {
  display: block;
  margin-bottom: 4px;
  font-weight: 700;
  color: #b08a4e;
  font-size: 11px;
  letter-spacing: 0.2px;
}
/* Per-stage group-N accent border overrides */
#tab-stage_2 .group-captions .gcap-g1 { border-left-color: #b08a4e; }
#tab-stage_2 .group-captions .gcap-g1 b { color: #b08a4e; }
#tab-stage_2 .group-captions .gcap-g2 { border-left-color: #5a8a6a; }
#tab-stage_2 .group-captions .gcap-g2 b { color: #5a8a6a; }
#tab-stage_2 .group-captions .gcap-g3 { border-left-color: #4a6a8a; }
#tab-stage_2 .group-captions .gcap-g3 b { color: #4a6a8a; }
#tab-stage_2 .group-captions .gcap-g4 { border-left-color: #8a5a6a; }
#tab-stage_2 .group-captions .gcap-g4 b { color: #8a5a6a; }
#tab-stage_2 .group-captions .gcap-g5 { border-left-color: #6a5a8a; }
#tab-stage_2 .group-captions .gcap-g5 b { color: #6a5a8a; }
/* MD-V2-S42-STAGE-COLOUR-MIRROR-MARKER -- stage_3 and stage_4 per-group caption accents placed AFTER the shared default rule (#tab-stage_3 .group-captions .gcap { border-left: 3px solid #b08a4e; }) so cascade source order makes them win. The original per-stage accent rules at L875-884 (stage_3) and L990-994 (stage_4) had identical specificity to the shared default but came EARLIER in source, so the gold default was overriding the orange/red palettes. Colours match each stage's existing .gh-g{N} thead text-colors. */
#tab-stage_3 .group-captions .gcap-g1 { border-left-color: #d97706; }
#tab-stage_3 .group-captions .gcap-g1 b { color: #b45309; }
#tab-stage_3 .group-captions .gcap-g2 { border-left-color: #c2410c; }
#tab-stage_3 .group-captions .gcap-g2 b { color: #9a3412; }
#tab-stage_3 .group-captions .gcap-g3 { border-left-color: #b91c1c; }
#tab-stage_3 .group-captions .gcap-g3 b { color: #991b1b; }
#tab-stage_3 .group-captions .gcap-g4 { border-left-color: #7c2d12; }
#tab-stage_3 .group-captions .gcap-g4 b { color: #7c2d12; }
#tab-stage_3 .group-captions .gcap-g5 { border-left-color: #6a5a8a; }
#tab-stage_3 .group-captions .gcap-g5 b { color: #6a5a8a; }
#tab-stage_4 .group-captions .gcap-g1 { border-left-color: #991b1b; }
#tab-stage_4 .group-captions .gcap-g1 b { color: #991b1b; }
#tab-stage_4 .group-captions .gcap-g2 { border-left-color: #7f1d1d; }
#tab-stage_4 .group-captions .gcap-g2 b { color: #7f1d1d; }
#tab-stage_4 .group-captions .gcap-g3 { border-left-color: #6a5a8a; }
#tab-stage_4 .group-captions .gcap-g3 b { color: #6a5a8a; }
/* MD-V2-CHROME-PARITY-MARKER-CSS-END */

/* MD-V2-CHROME-PARITY-FOLLOWUP-MARKER-CSS-START */
/* Extend chrome suppression: also hide .header-controls-row (the #3 Toggles / #4 Filters row)
   on every V2 tab. The initial patch missed this row. */
body[data-active-tab^="stage_"] .header-controls-row,
body[data-active-tab="pre_indicators"] .header-controls-row,
body[data-active-tab="post_indicators"] .header-controls-row,
body[data-active-tab^="setups"] .header-controls-row,
body[data-active-tab="tests"] .header-controls-row,
body[data-active-tab="tests_healthy_vcp"] .header-controls-row,
body[data-active-tab="tests_speculative_bet"] .header-controls-row,
body[data-active-tab="tests_probing_bet_s1"] .header-controls-row,
body[data-active-tab="tests_probing_bet_s2"] .header-controls-row,
body[data-active-tab="setups_healthy_retest"] .header-controls-row,
body[data-active-tab="master_overview"] .header-controls-row { display: none !important; }
/* MD-V2-PI-V2-S25-MARKER: EDIT 1 - Block A header chrome shrink on V2 tabs (D-MD-V2-47).
   Legacy header is sized for 3 rows; V2 tabs show only header-top + v2-nav.
   Shrink the fixed header + override --header-height so the table does not
   float up under it, and tighten the v2-nav padding. CSS-only, no HTML change. */
body[data-active-tab^="stage_"] .header,
body[data-active-tab="pre_indicators"] .header,
body[data-active-tab="post_indicators"] .header,
body[data-active-tab^="setups"] .header,
body[data-active-tab="tests"] .header,
body[data-active-tab="tests_healthy_vcp"] .header,
body[data-active-tab="tests_speculative_bet"] .header,
body[data-active-tab="tests_probing_bet_s1"] .header,
body[data-active-tab="tests_probing_bet_s2"] .header,
body[data-active-tab="setups_healthy_retest"] .header,
body[data-active-tab="master_overview"] .header { padding-bottom: 0 !important; }
body[data-active-tab^="stage_"],
body[data-active-tab="pre_indicators"],
body[data-active-tab="post_indicators"],
body[data-active-tab^="setups"],
body[data-active-tab="tests"],
body[data-active-tab="tests_healthy_vcp"],
body[data-active-tab="tests_speculative_bet"],
body[data-active-tab="tests_probing_bet_s1"],
body[data-active-tab="tests_probing_bet_s2"],
body[data-active-tab="setups_healthy_retest"],
body[data-active-tab="master_overview"] { --header-height: 70px; }
body[data-active-tab^="stage_"] .v2-nav,
body[data-active-tab="pre_indicators"] .v2-nav,
body[data-active-tab="post_indicators"] .v2-nav,
body[data-active-tab^="setups"] .v2-nav,
body[data-active-tab="tests"] .v2-nav,
body[data-active-tab="tests_speculative_bet"] .v2-nav,
body[data-active-tab="tests_probing_bet_s1"] .v2-nav,
body[data-active-tab="tests_probing_bet_s2"] .v2-nav,
body[data-active-tab="setups_healthy_retest"] .v2-nav,
body[data-active-tab="master_overview"] .v2-nav { padding-top: 4px !important; padding-bottom: 4px !important; }
/* MD-V2-CHROME-PARITY-FOLLOWUP-MARKER-CSS-END */

/* MD-V2-PRE-INDICATORS-MARKER-CSS-START */
/* Session 25 rebuild (D-MD-V2-49,-50,-55,-56,-57,-58) */
#tab-pre_indicators .group-captions { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 10px; margin: 16px 0 14px 0; }
#tab-pre_indicators .group-captions .gcap { background: #fbfaf5; border: 1px solid #e0dcc8; border-left: 3px solid #b08a4e; border-radius: 4px; padding: 10px 12px; font-size: 11px; line-height: 1.45; color: #555; }
#tab-pre_indicators .group-captions .gcap b { display: block; margin-bottom: 4px; font-weight: 700; color: #b08a4e; font-size: 11px; letter-spacing: 0.2px; }
#tab-pre_indicators .group-captions .gcap-g1 { border-left-color: #0F6E56; }
#tab-pre_indicators .group-captions .gcap-g1 b { color: #0F6E56; }
#tab-pre_indicators .group-captions .gcap-g2 { border-left-color: #1D7A4E; }
#tab-pre_indicators .group-captions .gcap-g2 b { color: #1D7A4E; }
#tab-pre_indicators .group-captions .gcap-g3 { border-left-color: #A32D2D; }
#tab-pre_indicators .group-captions .gcap-g3 b { color: #A32D2D; }

#tab-pre_indicators .s1-rating-tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 8px; }
#tab-pre_indicators .s1-rating-tiles .pi-tile-pullback   { background: rgba(15, 110, 86, 0.10); border: 1px solid rgba(15,110,86,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
#tab-pre_indicators .s1-rating-tiles .pi-tile-basing     { background: rgba(29, 122, 78, 0.10); border: 1px solid rgba(29,122,78,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
#tab-pre_indicators .s1-rating-tiles .pi-tile-collapsing { background: rgba(163, 45, 45, 0.10); border: 1px solid rgba(163,45,45,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
#tab-pre_indicators .s1-rating-tiles .pi-tile-pullback.active   { background: rgba(15, 110, 86, 0.22); border: 1.5px solid #0F6E56; }
#tab-pre_indicators .s1-rating-tiles .pi-tile-basing.active     { background: rgba(29, 122, 78, 0.22); border: 1.5px solid #1D7A4E; }
#tab-pre_indicators .s1-rating-tiles .pi-tile-collapsing.active { background: rgba(163, 45, 45, 0.22); border: 1.5px solid #A32D2D; }
#tab-pre_indicators .s1-rating-tiles .pi-strip-pullback   { background: #0F6E56; height: 4px; margin-top: 6px; border-radius: 2px; }
#tab-pre_indicators .s1-rating-tiles .pi-strip-basing     { background: #1D7A4E; height: 4px; margin-top: 6px; border-radius: 2px; }
#tab-pre_indicators .s1-rating-tiles .pi-strip-collapsing { background: #A32D2D; height: 4px; margin-top: 6px; border-radius: 2px; }
/* D-MD-V2-57: pass-count breakdown line - smaller text than the master count */
#tab-pre_indicators .s1-rating-tiles .rt-breakdown { font-size: 9px; color: #888; margin-top: 4px; line-height: 1.35; }

#pi-main-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 11px; table-layout: fixed; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }
#pi-main-table thead { position: sticky; top: 0; z-index: 50; background: #fbfaf5; box-shadow: 0 2px 4px rgba(0,0,0,0.06); }
#pi-main-table thead th { background: #fbfaf5 !important; border-bottom: 1px solid #e0dcc8; padding: 7px 3px; text-align: center; font-weight: 600; font-size: 10px; color: #666; cursor: pointer; user-select: none; line-height: 1.25; vertical-align: middle; }
#pi-main-table thead th:hover { background: #f0ebd9 !important; }
/* Super-group banner row (D-MD-V2-56) */
#pi-main-table thead .super-group-row th { background: #f3efe2 !important; font-size: 9px; text-transform: uppercase; font-weight: 700; letter-spacing: 0.5px; padding: 5px 3px; cursor: default; line-height: 1.25; }
#pi-main-table thead .super-group-row th:hover { background: #f3efe2 !important; }
#pi-main-table thead .super-group-row th.sg-spacer { background: #fbfaf5 !important; }
#pi-main-table thead .super-group-row th.sg-positive { color: #0F6E56; border-bottom: 2px solid rgba(15,110,86,0.45); }
#pi-main-table thead .super-group-row th.sg-negative { color: #A32D2D; border-bottom: 2px solid rgba(163,45,45,0.45); }
#pi-main-table thead .group-header-row th { background: #f3efe2 !important; font-size: 9.5px; text-transform: none; font-weight: 700; letter-spacing: 0.2px; padding: 5px 3px; cursor: default; line-height: 1.25; }
#pi-main-table thead .group-header-row th:hover { background: #f3efe2 !important; }
#pi-main-table thead tr.super-group-row  th { position: sticky; top: 0; }
#pi-main-table thead tr.group-header-row th { position: sticky; top: 24px; }
#pi-main-table thead tr.col-header-row   th { position: sticky; top: 48px; border-top: 1px solid #e0dcc8; }
#pi-main-table thead .gh-inputs { color: #555; }
#pi-main-table thead .gh-g1 { color: #0F6E56; }
#pi-main-table thead .gh-g2 { color: #1D7A4E; }
#pi-main-table thead .gh-g3 { color: #A32D2D; }
#pi-main-table .hd { display: inline-flex; align-items: center; justify-content: center; gap: 3px; width: 100%; }
#pi-main-table .hd .lbl { white-space: normal; word-break: break-word; }
#pi-main-table .hd .sort-arrow { font-size: 9px; color: #0F6E56; flex: 0 0 auto; line-height: 1; }
#pi-main-table .hd .sort-placeholder { width: 9px; flex: 0 0 auto; }
#pi-main-table td { padding: 5px 4px; border-bottom: 1px solid #efece0; text-align: center; vertical-align: middle; height: 38px; box-sizing: border-box; font-variant-numeric: tabular-nums; }
#pi-main-table tr:hover { background: rgba(15,110,86,0.05); }
#pi-main-table td.grp-start-g1, #pi-main-table th.grp-start-g1 { border-left: 2px solid rgba(15,110,86,0.40); }
#pi-main-table td.grp-start-g2, #pi-main-table th.grp-start-g2 { border-left: 2px solid rgba(29,122,78,0.40); }
#pi-main-table td.grp-start-g3, #pi-main-table th.grp-start-g3 { border-left: 2px solid rgba(163,45,45,0.40); }
#pi-main-table td.pi-pass { background: rgba(15,110,86,0.12); color: #0F6E56; font-weight: 700; }
#pi-main-table td.pi-fail { color: #999; }
/* Rating + score column group per pattern (D-MD-V2-55) */
#pi-main-table td.pi-rating-cell { padding: 3px 4px; }
#pi-main-table .pi-pill { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 9px; font-weight: 700; line-height: 1.3; white-space: nowrap; }
#pi-main-table .pi-pill-tint-prob { background: #0F6E56; color: #fff; }
#pi-main-table .pi-pill-tint-pla  { background: rgba(15,110,86,0.30); color: #0a4a3a; }
#pi-main-table .pi-pill-tint-pos  { background: rgba(15,110,86,0.14); color: #3a6a5a; }
#pi-main-table .pi-pill-tint-none { background: #ece9dd; color: #999; }
#pi-main-table td.pi-score-cell { padding: 4px 3px; }
#pi-main-table .pi-pip-row { display: inline-flex; align-items: center; gap: 2px; justify-content: center; }
#pi-main-table .pi-pip-row .pip { width: 6px; height: 6px; border-radius: 50%; background: #d8d4c4; display: inline-block; }
#pi-main-table .pi-pip-row .pip.on { background: #0F6E56; }
#pi-main-table .pi-pip-row .pi-score-num { font-size: 9px; color: #777; margin-left: 3px; font-weight: 600; }
#pi-main-table td.name-cell { text-align: left; padding: 4px 4px 4px 8px; line-height: 1.15; }
#pi-main-table td.name-cell .co { font-weight: 700; font-size: 11px; color: #2a2a2a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#pi-main-table td.name-cell .tk { font-size: 9px; color: #999; font-weight: 500; margin-top: 1px; }
#pi-main-table td.name-cell .live-dot { color: #2e7d32; font-weight: 700; margin-right: 4px; display: inline-block; vertical-align: middle; line-height: 1; font-size: 10px; }
#pi-main-table td.taxon { text-align: left; font-size: 9px; line-height: 1.2; padding: 4px; }
#pi-main-table td.taxon .ind { color: #666; font-weight: 500; }
#pi-main-table td.taxon .sec { color: #999; }
#pi-main-table col.c-name { width: 124px; }
#pi-main-table col.c-taxon { width: 150px; }
#pi-main-table col.c-price { width: 50px; }
#pi-main-table col.c-52wh { width: 48px; }
#pi-main-table col.c-52wl { width: 48px; }
#pi-main-table col.c-ma150 { width: 48px; }
#pi-main-table col.c-ma200 { width: 48px; }
#pi-main-table col.c-pullback { width: 58px; }
#pi-main-table col.c-rating { width: 64px; }
#pi-main-table col.c-score { width: 52px; }
#pi-main-table col.c-test { width: 64px; }
#pi-main-table tr.tint-row td.name-cell, #pi-main-table tr.tint-row td.taxon { background: var(--tint-bg) !important; }
#pi-main-table tr.portfolio-band td:last-child { border-right: 4px solid var(--portfolio-color); }
#pi-main-table tr.portfolio-tint { background: var(--portfolio-bg); }
#pi-main-table tr.portfolio-tint:hover { background: var(--portfolio-bg-hover); }
/* MD-V2-PI-CHIPS-S25-MARKER: rating-tier multi-select chip filter (D-MD-V2-59) */
#tab-pre_indicators .s1-rating-tiles .pi-tier-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 7px; }
#tab-pre_indicators .pi-tier-chip { font-size: 10px; padding: 2px 6px; border-radius: var(--border-radius-md, 4px); cursor: pointer; user-select: none; border: 0.5px solid; line-height: 1.4; white-space: nowrap; transition: background 0.12s, color 0.12s; }
#tab-pre_indicators .pi-chip-pullback { background: #E1F5EE; color: #0F6E56; border-color: #9FE1CB; }
#tab-pre_indicators .pi-chip-pullback.on { background: #0F6E56; color: #fff; border-color: #0F6E56; font-weight: 500; }
#tab-pre_indicators .pi-chip-basing { background: #E1F5EE; color: #0F6E56; border-color: #9FE1CB; }
#tab-pre_indicators .pi-chip-basing.on { background: #1D7A4E; color: #fff; border-color: #1D7A4E; font-weight: 500; }
#tab-pre_indicators .pi-chip-collapsing { background: #FCEBEB; color: #A32D2D; border-color: #F7C1C1; }
#tab-pre_indicators .pi-chip-collapsing.on { background: #A32D2D; color: #fff; border-color: #A32D2D; font-weight: 500; }
#tab-pre_indicators .pi-tier-chip:hover { filter: brightness(0.96); }
#tab-pre_indicators .s1-rating-tiles .rating-tile.active { box-shadow: inset 0 0 0 1.5px currentColor; }
/* MD-V2-PRE-INDICATORS-MARKER-CSS-END */
/* MD-V2-POST-INDICATORS-MARKER-CSS-START */
/* Session 26 - generated from PI v3 CSS template, namespaced to #tab-post_indicators */
/* Session 25 rebuild (D-MD-V2-49,-50,-55,-56,-57,-58) */
#tab-post_indicators .group-captions { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 10px; margin: 16px 0 14px 0; }
#tab-post_indicators .group-captions .gcap { background: #fbfaf5; border: 1px solid #e0dcc8; border-left: 3px solid #b08a4e; border-radius: 4px; padding: 10px 12px; font-size: 11px; line-height: 1.45; color: #555; }
#tab-post_indicators .group-captions .gcap b { display: block; margin-bottom: 4px; font-weight: 700; color: #b08a4e; font-size: 11px; letter-spacing: 0.2px; }
#tab-post_indicators .group-captions .gcap-g1 { border-left-color: #0F6E56; }
#tab-post_indicators .group-captions .gcap-g1 b { color: #0F6E56; }
#tab-post_indicators .group-captions .gcap-g2 { border-left-color: #1D7A4E; }
#tab-post_indicators .group-captions .gcap-g2 b { color: #1D7A4E; }
#tab-post_indicators .group-captions .gcap-g3 { border-left-color: #A32D2D; }
#tab-post_indicators .group-captions .gcap-g3 b { color: #A32D2D; }

#tab-post_indicators .s1-rating-tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 8px; }
#tab-post_indicators .s1-rating-tiles .pi-tile-pullback   { background: rgba(15, 110, 86, 0.10); border: 1px solid rgba(15,110,86,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
#tab-post_indicators .s1-rating-tiles .pi-tile-basing     { background: rgba(29, 122, 78, 0.10); border: 1px solid rgba(29,122,78,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
#tab-post_indicators .s1-rating-tiles .pi-tile-collapsing { background: rgba(163, 45, 45, 0.10); border: 1px solid rgba(163,45,45,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
#tab-post_indicators .s1-rating-tiles .pi-tile-pullback.active   { background: rgba(15, 110, 86, 0.22); border: 1.5px solid #0F6E56; }
#tab-post_indicators .s1-rating-tiles .pi-tile-basing.active     { background: rgba(29, 122, 78, 0.22); border: 1.5px solid #1D7A4E; }
#tab-post_indicators .s1-rating-tiles .pi-tile-collapsing.active { background: rgba(163, 45, 45, 0.22); border: 1.5px solid #A32D2D; }
#tab-post_indicators .s1-rating-tiles .pi-strip-pullback   { background: #0F6E56; height: 4px; margin-top: 6px; border-radius: 2px; }
#tab-post_indicators .s1-rating-tiles .pi-strip-basing     { background: #1D7A4E; height: 4px; margin-top: 6px; border-radius: 2px; }
#tab-post_indicators .s1-rating-tiles .pi-strip-collapsing { background: #A32D2D; height: 4px; margin-top: 6px; border-radius: 2px; }
/* D-MD-V2-57: pass-count breakdown line - smaller text than the master count */
#tab-post_indicators .s1-rating-tiles .rt-breakdown { font-size: 9px; color: #888; margin-top: 4px; line-height: 1.35; }

#po-main-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 11px; table-layout: fixed; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }
#po-main-table thead { position: sticky; top: 0; z-index: 50; background: #fbfaf5; box-shadow: 0 2px 4px rgba(0,0,0,0.06); }
#po-main-table thead th { background: #fbfaf5 !important; border-bottom: 1px solid #e0dcc8; padding: 7px 3px; text-align: center; font-weight: 600; font-size: 10px; color: #666; cursor: pointer; user-select: none; line-height: 1.25; vertical-align: middle; }
#po-main-table thead th:hover { background: #f0ebd9 !important; }
/* Super-group banner row (D-MD-V2-56) */
#po-main-table thead .super-group-row th { background: #f3efe2 !important; font-size: 9px; text-transform: uppercase; font-weight: 700; letter-spacing: 0.5px; padding: 5px 3px; cursor: default; line-height: 1.25; }
#po-main-table thead .super-group-row th:hover { background: #f3efe2 !important; }
#po-main-table thead .super-group-row th.sg-spacer { background: #fbfaf5 !important; }
#po-main-table thead .super-group-row th.sg-positive { color: #0F6E56; border-bottom: 2px solid rgba(15,110,86,0.45); }
#po-main-table thead .super-group-row th.sg-negative { color: #A32D2D; border-bottom: 2px solid rgba(163,45,45,0.45); }
#po-main-table thead .group-header-row th { background: #f3efe2 !important; font-size: 9.5px; text-transform: none; font-weight: 700; letter-spacing: 0.2px; padding: 5px 3px; cursor: default; line-height: 1.25; }
#po-main-table thead .group-header-row th:hover { background: #f3efe2 !important; }
#po-main-table thead tr.super-group-row  th { position: sticky; top: 0; }
#po-main-table thead tr.group-header-row th { position: sticky; top: 24px; }
#po-main-table thead tr.col-header-row   th { position: sticky; top: 48px; border-top: 1px solid #e0dcc8; }
#po-main-table thead .gh-inputs { color: #555; }
#po-main-table thead .gh-g1 { color: #0F6E56; }
#po-main-table thead .gh-g2 { color: #1D7A4E; }
#po-main-table thead .gh-g3 { color: #A32D2D; }
#po-main-table .hd { display: inline-flex; align-items: center; justify-content: center; gap: 3px; width: 100%; }
#po-main-table .hd .lbl { white-space: normal; word-break: break-word; }
#po-main-table .hd .sort-arrow { font-size: 9px; color: #0F6E56; flex: 0 0 auto; line-height: 1; }
#po-main-table .hd .sort-placeholder { width: 9px; flex: 0 0 auto; }
#po-main-table td { padding: 5px 4px; border-bottom: 1px solid #efece0; text-align: center; vertical-align: middle; height: 38px; box-sizing: border-box; font-variant-numeric: tabular-nums; }
#po-main-table tr:hover { background: rgba(15,110,86,0.05); }
#po-main-table td.grp-start-g1, #po-main-table th.grp-start-g1 { border-left: 2px solid rgba(15,110,86,0.40); }
#po-main-table td.grp-start-g2, #po-main-table th.grp-start-g2 { border-left: 2px solid rgba(29,122,78,0.40); }
#po-main-table td.grp-start-g3, #po-main-table th.grp-start-g3 { border-left: 2px solid rgba(163,45,45,0.40); }
#po-main-table td.pi-pass { background: rgba(15,110,86,0.12); color: #0F6E56; font-weight: 700; }
#po-main-table td.pi-fail { color: #999; }
/* Rating + score column group per pattern (D-MD-V2-55) */
#po-main-table td.pi-rating-cell { padding: 3px 4px; }
#po-main-table .pi-pill { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 9px; font-weight: 700; line-height: 1.3; white-space: nowrap; }
#po-main-table .pi-pill-tint-prob { background: #0F6E56; color: #fff; }
#po-main-table .pi-pill-tint-pla  { background: rgba(15,110,86,0.30); color: #0a4a3a; }
#po-main-table .pi-pill-tint-pos  { background: rgba(15,110,86,0.14); color: #3a6a5a; }
#po-main-table .pi-pill-tint-none { background: #ece9dd; color: #999; }
#po-main-table td.pi-score-cell { padding: 4px 3px; }
#po-main-table .pi-pip-row { display: inline-flex; align-items: center; gap: 2px; justify-content: center; }
#po-main-table .pi-pip-row .pip { width: 6px; height: 6px; border-radius: 50%; background: #d8d4c4; display: inline-block; }
#po-main-table .pi-pip-row .pip.on { background: #0F6E56; }
#po-main-table .pi-pip-row .pi-score-num { font-size: 9px; color: #777; margin-left: 3px; font-weight: 600; }
#po-main-table td.name-cell { text-align: left; padding: 4px 4px 4px 8px; line-height: 1.15; }
#po-main-table td.name-cell .co { font-weight: 700; font-size: 11px; color: #2a2a2a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#po-main-table td.name-cell .tk { font-size: 9px; color: #999; font-weight: 500; margin-top: 1px; }
#po-main-table td.name-cell .live-dot { color: #2e7d32; font-weight: 700; margin-right: 4px; display: inline-block; vertical-align: middle; line-height: 1; font-size: 10px; }
#po-main-table td.taxon { text-align: left; font-size: 9px; line-height: 1.2; padding: 4px; }
#po-main-table td.taxon .ind { color: #666; font-weight: 500; }
#po-main-table td.taxon .sec { color: #999; }
#po-main-table col.c-name { width: 124px; }
#po-main-table col.c-taxon { width: 150px; }
#po-main-table col.c-price { width: 50px; }
#po-main-table col.c-52wh { width: 48px; }
#po-main-table col.c-52wl { width: 48px; }
#po-main-table col.c-ma150 { width: 48px; }
#po-main-table col.c-ma200 { width: 48px; }
#po-main-table col.c-pullback { width: 58px; }
#po-main-table col.c-rating { width: 64px; }
#po-main-table col.c-score { width: 52px; }
#po-main-table col.c-test { width: 64px; }
#po-main-table tr.tint-row td.name-cell, #po-main-table tr.tint-row td.taxon { background: var(--tint-bg) !important; }
#po-main-table tr.portfolio-band td:last-child { border-right: 4px solid var(--portfolio-color); }
#po-main-table tr.portfolio-tint { background: var(--portfolio-bg); }
#po-main-table tr.portfolio-tint:hover { background: var(--portfolio-bg-hover); }
/* MD-V2-PI-CHIPS-S25-MARKER: rating-tier multi-select chip filter (D-MD-V2-59) */
#tab-post_indicators .s1-rating-tiles .pi-tier-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 7px; }
#tab-post_indicators .pi-tier-chip { font-size: 10px; padding: 2px 6px; border-radius: var(--border-radius-md, 4px); cursor: pointer; user-select: none; border: 0.5px solid; line-height: 1.4; white-space: nowrap; transition: background 0.12s, color 0.12s; }
#tab-post_indicators .pi-chip-pullback { background: #E1F5EE; color: #0F6E56; border-color: #9FE1CB; }
#tab-post_indicators .pi-chip-pullback.on { background: #0F6E56; color: #fff; border-color: #0F6E56; font-weight: 500; }
#tab-post_indicators .pi-chip-basing { background: #E1F5EE; color: #0F6E56; border-color: #9FE1CB; }
#tab-post_indicators .pi-chip-basing.on { background: #1D7A4E; color: #fff; border-color: #1D7A4E; font-weight: 500; }
#tab-post_indicators .pi-chip-collapsing { background: #FCEBEB; color: #A32D2D; border-color: #F7C1C1; }
#tab-post_indicators .pi-chip-collapsing.on { background: #A32D2D; color: #fff; border-color: #A32D2D; font-weight: 500; }
#tab-post_indicators .pi-tier-chip:hover { filter: brightness(0.96); }
#tab-post_indicators .s1-rating-tiles .rating-tile.active { box-shadow: inset 0 0 0 1.5px currentColor; }
#tab-post_indicators .pi-chip-amber { background: #FAEEDA; color: #854F0B; border-color: #FAC775; }
#tab-post_indicators .pi-chip-amber.on { background: #BA7517; color: #fff; border-color: #BA7517; font-weight: 500; }
#tab-post_indicators .pi-chip-navy { background: #E6F1FB; color: #0C447C; border-color: #B5D4F4; }
#tab-post_indicators .pi-chip-navy.on { background: #185FA5; color: #fff; border-color: #185FA5; font-weight: 500; }
#tab-post_indicators .s1-rating-tiles .pi-tile-amber { background: rgba(186,117,23,0.10); border: 1px solid rgba(186,117,23,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
#tab-post_indicators .s1-rating-tiles .pi-tile-amber.active { background: rgba(186,117,23,0.22); border: 1.5px solid #BA7517; }
#tab-post_indicators .s1-rating-tiles .pi-strip-amber { background: #BA7517; height: 4px; margin-top: 6px; border-radius: 2px; }
#tab-post_indicators .s1-rating-tiles .pi-tile-navy { background: rgba(24,95,165,0.10); border: 1px solid rgba(24,95,165,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
#tab-post_indicators .s1-rating-tiles .pi-tile-navy.active { background: rgba(24,95,165,0.22); border: 1.5px solid #185FA5; }
#tab-post_indicators .s1-rating-tiles .pi-strip-navy { background: #185FA5; height: 4px; margin-top: 6px; border-radius: 2px; }
/* MD-V2-POST-INDICATORS-MARKER-CSS-END */
/* MD-V2-SETUPS-MARKER-CSS-START */
/* Session 26 - generated from PI v3 CSS template, namespaced to [id^="tab-setups"] */
/* Session 25 rebuild (D-MD-V2-49,-50,-55,-56,-57,-58) */
[id^="tab-setups"] .group-captions { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin: 16px 0 14px 0; }
[id^="tab-setups"] .group-captions .gcap { background: #fbfaf5; border: 1px solid #e0dcc8; border-left: 3px solid #b08a4e; border-radius: 4px; padding: 10px 12px; font-size: 11px; line-height: 1.45; color: #555; }
[id^="tab-setups"] .group-captions .gcap b { display: block; margin-bottom: 4px; font-weight: 700; color: #b08a4e; font-size: 11px; letter-spacing: 0.2px; }
[id^="tab-setups"] .group-captions .gcap-g1 { border-left-color: #0F6E56; }
[id^="tab-setups"] .group-captions .gcap-g1 b { color: #0F6E56; }
[id^="tab-setups"] .group-captions .gcap-g2 { border-left-color: #1D7A4E; }
[id^="tab-setups"] .group-captions .gcap-g2 b { color: #1D7A4E; }
[id^="tab-setups"] .group-captions .gcap-g3 { border-left-color: #A32D2D; }
[id^="tab-setups"] .group-captions .gcap-g3 b { color: #A32D2D; }

[id^="tab-setups"] .s1-rating-tiles { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
[id^="tab-setups"] .s1-rating-tiles .pi-tile-pullback   { background: rgba(15, 110, 86, 0.10); border: 1px solid rgba(15,110,86,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
[id^="tab-setups"] .s1-rating-tiles .pi-tile-basing     { background: rgba(29, 122, 78, 0.10); border: 1px solid rgba(29,122,78,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
[id^="tab-setups"] .s1-rating-tiles .pi-tile-collapsing { background: rgba(163, 45, 45, 0.10); border: 1px solid rgba(163,45,45,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
[id^="tab-setups"] .s1-rating-tiles .pi-tile-pullback.active   { background: rgba(15, 110, 86, 0.22); border: 1.5px solid #0F6E56; }
[id^="tab-setups"] .s1-rating-tiles .pi-tile-basing.active     { background: rgba(29, 122, 78, 0.22); border: 1.5px solid #1D7A4E; }
[id^="tab-setups"] .s1-rating-tiles .pi-tile-collapsing.active { background: rgba(163, 45, 45, 0.22); border: 1.5px solid #A32D2D; }
[id^="tab-setups"] .s1-rating-tiles .pi-strip-pullback   { background: #0F6E56; height: 4px; margin-top: 6px; border-radius: 2px; }
[id^="tab-setups"] .s1-rating-tiles .pi-strip-basing     { background: #1D7A4E; height: 4px; margin-top: 6px; border-radius: 2px; }
[id^="tab-setups"] .s1-rating-tiles .pi-strip-collapsing { background: #A32D2D; height: 4px; margin-top: 6px; border-radius: 2px; }
/* D-MD-V2-57: pass-count breakdown line - smaller text than the master count */
[id^="tab-setups"] .s1-rating-tiles .rt-breakdown { font-size: 9px; color: #888; margin-top: 4px; line-height: 1.35; }

.st-main-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 11px; table-layout: fixed; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }
.st-main-table thead { position: sticky; top: 0; z-index: 50; background: #fbfaf5; box-shadow: 0 2px 4px rgba(0,0,0,0.06); }
.st-main-table thead th { background: #fbfaf5 !important; border-bottom: 1px solid #e0dcc8; padding: 7px 3px; text-align: center; font-weight: 600; font-size: 10px; color: #666; cursor: pointer; user-select: none; line-height: 1.25; vertical-align: middle; }
.st-main-table thead th:hover { background: #f0ebd9 !important; }
/* Super-group banner row (D-MD-V2-56) */
.st-main-table thead .super-group-row th { background: #f3efe2 !important; font-size: 9px; text-transform: uppercase; font-weight: 700; letter-spacing: 0.5px; padding: 5px 3px; cursor: default; line-height: 1.25; }
.st-main-table thead .super-group-row th:hover { background: #f3efe2 !important; }
.st-main-table thead .super-group-row th.sg-spacer { background: #fbfaf5 !important; }
.st-main-table thead .super-group-row th.sg-positive { color: #0F6E56; border-bottom: 2px solid rgba(15,110,86,0.45); }
.st-main-table thead .super-group-row th.sg-negative { color: #A32D2D; border-bottom: 2px solid rgba(163,45,45,0.45); }
.st-main-table thead .group-header-row th { background: #f3efe2 !important; font-size: 9.5px; text-transform: none; font-weight: 700; letter-spacing: 0.2px; padding: 5px 3px; cursor: default; line-height: 1.25; }
.st-main-table thead .group-header-row th:hover { background: #f3efe2 !important; }
.st-main-table thead tr.super-group-row  th { position: sticky; top: 0; }
.st-main-table thead tr.group-header-row th { position: sticky; top: 24px; }
.st-main-table thead tr.col-header-row   th { position: sticky; top: 48px; border-top: 1px solid #e0dcc8; }
.st-main-table thead .gh-inputs { color: #555; }
.st-main-table thead .gh-g1 { color: #0F6E56; }
.st-main-table thead .gh-g2 { color: #1D7A4E; }
.st-main-table thead .gh-g3 { color: #A32D2D; }
.st-main-table .hd { display: inline-flex; align-items: center; justify-content: center; gap: 3px; width: 100%; }
.st-main-table .hd .lbl { white-space: normal; word-break: break-word; }
.st-main-table .hd .sort-arrow { font-size: 9px; color: #0F6E56; flex: 0 0 auto; line-height: 1; }
.st-main-table .hd .sort-placeholder { width: 9px; flex: 0 0 auto; }
.st-main-table td { padding: 5px 4px; border-bottom: 1px solid #efece0; text-align: center; vertical-align: middle; height: 38px; box-sizing: border-box; font-variant-numeric: tabular-nums; }
.st-main-table tr:hover { background: rgba(15,110,86,0.05); }
.st-main-table td.grp-start-g1, .st-main-table th.grp-start-g1 { border-left: 2px solid rgba(15,110,86,0.40); }
.st-main-table td.grp-start-g2, .st-main-table th.grp-start-g2 { border-left: 2px solid rgba(29,122,78,0.40); }
.st-main-table td.grp-start-g3, .st-main-table th.grp-start-g3 { border-left: 2px solid rgba(163,45,45,0.40); }
.st-main-table td.pi-pass { background: rgba(15,110,86,0.12); color: #0F6E56; font-weight: 700; }
.st-main-table td.pi-fail { color: #999; }
/* Rating + score column group per pattern (D-MD-V2-55) */
.st-main-table td.pi-rating-cell { padding: 3px 4px; }
.st-main-table .pi-pill { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 9px; font-weight: 700; line-height: 1.3; white-space: nowrap; }
.st-main-table .pi-pill-tint-prob { background: #0F6E56; color: #fff; }
.st-main-table .pi-pill-tint-pla  { background: rgba(15,110,86,0.30); color: #0a4a3a; }
.st-main-table .pi-pill-tint-pos  { background: rgba(15,110,86,0.14); color: #3a6a5a; }
.st-main-table .pi-pill-tint-none { background: #ece9dd; color: #999; }
.st-main-table td.pi-score-cell { padding: 4px 3px; }
.st-main-table .pi-pip-row { display: inline-flex; align-items: center; gap: 2px; justify-content: center; }
.st-main-table .pi-pip-row .pip { width: 6px; height: 6px; border-radius: 50%; background: #d8d4c4; display: inline-block; }
.st-main-table .pi-pip-row .pip.on { background: #0F6E56; }
.st-main-table .pi-pip-row .pi-score-num { font-size: 9px; color: #777; margin-left: 3px; font-weight: 600; }
.st-main-table td.name-cell { text-align: left; padding: 4px 4px 4px 8px; line-height: 1.15; }
.st-main-table td.name-cell .co { font-weight: 700; font-size: 11px; color: #2a2a2a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.st-main-table td.name-cell .tk { font-size: 9px; color: #999; font-weight: 500; margin-top: 1px; }
.st-main-table td.name-cell .live-dot { color: #2e7d32; font-weight: 700; margin-right: 4px; display: inline-block; vertical-align: middle; line-height: 1; font-size: 10px; }
.st-main-table td.taxon { text-align: left; font-size: 9px; line-height: 1.2; padding: 4px; }
.st-main-table td.taxon .ind { color: #666; font-weight: 500; }
.st-main-table td.taxon .sec { color: #999; }
.st-main-table col.c-name { width: 124px; }
.st-main-table col.c-taxon { width: 150px; }
.st-main-table col.c-price { width: 50px; }
.st-main-table col.c-52wh { width: 48px; }
.st-main-table col.c-52wl { width: 48px; }
.st-main-table col.c-ma150 { width: 48px; }
.st-main-table col.c-ma200 { width: 48px; }
.st-main-table col.c-pullback { width: 58px; }
.st-main-table col.c-rating { width: 64px; }
.st-main-table col.c-score { width: 52px; }
.st-main-table col.c-test { width: 64px; }
.st-main-table tr.tint-row td.name-cell, .st-main-table tr.tint-row td.taxon { background: var(--tint-bg) !important; }
.st-main-table tr.portfolio-band td:last-child { border-right: 4px solid var(--portfolio-color); }
.st-main-table tr.portfolio-tint { background: var(--portfolio-bg); }
.st-main-table tr.portfolio-tint:hover { background: var(--portfolio-bg-hover); }
/* MD-V2-PI-CHIPS-S25-MARKER: rating-tier multi-select chip filter (D-MD-V2-59) */
[id^="tab-setups"] .s1-rating-tiles .pi-tier-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 7px; }
[id^="tab-setups"] .pi-tier-chip { font-size: 10px; padding: 2px 6px; border-radius: var(--border-radius-md, 4px); cursor: pointer; user-select: none; border: 0.5px solid; line-height: 1.4; white-space: nowrap; transition: background 0.12s, color 0.12s; }
[id^="tab-setups"] .pi-chip-pullback { background: #E1F5EE; color: #0F6E56; border-color: #9FE1CB; }
[id^="tab-setups"] .pi-chip-pullback.on { background: #0F6E56; color: #fff; border-color: #0F6E56; font-weight: 500; }
[id^="tab-setups"] .pi-chip-basing { background: #E1F5EE; color: #0F6E56; border-color: #9FE1CB; }
[id^="tab-setups"] .pi-chip-basing.on { background: #1D7A4E; color: #fff; border-color: #1D7A4E; font-weight: 500; }
[id^="tab-setups"] .pi-chip-collapsing { background: #FCEBEB; color: #A32D2D; border-color: #F7C1C1; }
[id^="tab-setups"] .pi-chip-collapsing.on { background: #A32D2D; color: #fff; border-color: #A32D2D; font-weight: 500; }
[id^="tab-setups"] .pi-tier-chip:hover { filter: brightness(0.96); }
[id^="tab-setups"] .s1-rating-tiles .rating-tile.active { box-shadow: inset 0 0 0 1.5px currentColor; }
[id^="tab-setups"] .pi-chip-amber { background: #FAEEDA; color: #854F0B; border-color: #FAC775; }
[id^="tab-setups"] .pi-chip-amber.on { background: #BA7517; color: #fff; border-color: #BA7517; font-weight: 500; }
[id^="tab-setups"] .pi-chip-navy { background: #E6F1FB; color: #0C447C; border-color: #B5D4F4; }
[id^="tab-setups"] .pi-chip-navy.on { background: #185FA5; color: #fff; border-color: #185FA5; font-weight: 500; }
[id^="tab-setups"] .s1-rating-tiles .pi-tile-amber { background: rgba(186,117,23,0.10); border: 1px solid rgba(186,117,23,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
[id^="tab-setups"] .s1-rating-tiles .pi-tile-amber.active { background: rgba(186,117,23,0.22); border: 1.5px solid #BA7517; }
[id^="tab-setups"] .s1-rating-tiles .pi-strip-amber { background: #BA7517; height: 4px; margin-top: 6px; border-radius: 2px; }
[id^="tab-setups"] .s1-rating-tiles .pi-tile-navy { background: rgba(24,95,165,0.10); border: 1px solid rgba(24,95,165,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
[id^="tab-setups"] .s1-rating-tiles .pi-tile-navy.active { background: rgba(24,95,165,0.22); border: 1.5px solid #185FA5; }
[id^="tab-setups"] .s1-rating-tiles .pi-strip-navy { background: #185FA5; height: 4px; margin-top: 6px; border-radius: 2px; }
/* MD-V2-SETUPS-MARKER-CSS-END */
/* MD-V2-TESTS-MARKER-CSS-START */
/* MD-V2-TESTS-S27-MARKER: Session 27 rebuild - 4 deployment tests, in
   totality, 4-stage info block, Collapsing-rating info column, L5D/L20D
   recent-trigger windows. Base structure from the S26 ct CSS; this block
   adds the 4th pattern colour family + the new column kinds. */
#tab-tests .group-captions { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 16px 0 14px 0; }
#tab-tests .group-captions .gcap { background: #fbfaf5; border: 1px solid #e0dcc8; border-left: 3px solid #b08a4e; border-radius: 4px; padding: 10px 12px; font-size: 11px; line-height: 1.45; color: #555; }
#tab-tests .group-captions .gcap b { display: block; margin-bottom: 4px; font-weight: 700; color: #b08a4e; font-size: 11px; letter-spacing: 0.2px; }
#tab-tests .group-captions .gcap-g1 { border-left-color: #0F6E56; }
#tab-tests .group-captions .gcap-g1 b { color: #0F6E56; }
#tab-tests .group-captions .gcap-g2 { border-left-color: #1D7A4E; }
#tab-tests .group-captions .gcap-g2 b { color: #1D7A4E; }
#tab-tests .group-captions .gcap-g3 { border-left-color: #185FA5; }
#tab-tests .group-captions .gcap-g3 b { color: #185FA5; }
#tab-tests .group-captions .gcap-g4 { border-left-color: #BA7517; }
#tab-tests .group-captions .gcap-g4 b { color: #BA7517; }

#tab-tests .s1-rating-tiles { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
#tab-tests .s1-rating-tiles .pi-tile-pullback   { background: rgba(15, 110, 86, 0.10); border: 1px solid rgba(15,110,86,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
#tab-tests .s1-rating-tiles .pi-tile-basing     { background: rgba(29, 122, 78, 0.10); border: 1px solid rgba(29,122,78,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
#tab-tests .s1-rating-tiles .pi-tile-pullback.active   { background: rgba(15, 110, 86, 0.22); border: 1.5px solid #0F6E56; }
#tab-tests .s1-rating-tiles .pi-tile-basing.active     { background: rgba(29, 122, 78, 0.22); border: 1.5px solid #1D7A4E; }
#tab-tests .s1-rating-tiles .pi-strip-pullback   { background: #0F6E56; height: 4px; margin-top: 6px; border-radius: 2px; }
#tab-tests .s1-rating-tiles .pi-strip-basing     { background: #1D7A4E; height: 4px; margin-top: 6px; border-radius: 2px; }
/* D-MD-V2-57: pass-count breakdown line */
#tab-tests .s1-rating-tiles .rt-breakdown { font-size: 9px; color: #888; margin-top: 4px; line-height: 1.35; }

#ct-main-table { width: 100%; min-width: 3200px; border-collapse: separate; border-spacing: 0; font-size: 11px; table-layout: fixed; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; } /* MD-V2-S49-CT-MINWIDTH: UI Issue 4 — forces body scroll so last column always reachable */
#ct-main-table thead { position: sticky; top: 0; z-index: 50; background: #fbfaf5; box-shadow: 0 2px 4px rgba(0,0,0,0.06); }
#ct-main-table thead th { background: #fbfaf5 !important; border-bottom: 1px solid #e0dcc8; padding: 7px 3px; text-align: center; font-weight: 600; font-size: 10px; color: #666; cursor: pointer; user-select: none; line-height: 1.25; vertical-align: middle; }
#ct-main-table thead th:hover { background: #f0ebd9 !important; }
#ct-main-table thead .group-header-row th { background: #f3efe2 !important; font-size: 9.5px; text-transform: none; font-weight: 700; letter-spacing: 0.2px; padding: 5px 3px; cursor: default; line-height: 1.25; }
#ct-main-table thead .group-header-row th:hover { background: #f3efe2 !important; }
/* S27: two header rows only (no super-group row). group at top:0, cols at top:24px. */
#ct-main-table thead tr.group-header-row th { position: sticky; top: 0; }
#ct-main-table thead tr.col-header-row   th { position: sticky; top: 24px; border-top: 1px solid #e0dcc8; }
#ct-main-table thead .gh-inputs { color: #555; }
#ct-main-table thead .gh-stageinfo { color: #7a6a3a; }
#ct-main-table thead .gh-g1 { color: #0F6E56; }
#ct-main-table thead .gh-g2 { color: #1D7A4E; }
#ct-main-table thead .gh-g3 { color: #185FA5; }
#ct-main-table thead .gh-g4 { color: #BA7517; }
#ct-main-table .hd { display: inline-flex; align-items: center; justify-content: center; gap: 3px; width: 100%; }
#ct-main-table .hd .lbl { white-space: normal; word-break: break-word; }
#ct-main-table .hd .sort-arrow { font-size: 9px; color: #0F6E56; flex: 0 0 auto; line-height: 1; }
#ct-main-table .hd .sort-placeholder { width: 9px; flex: 0 0 auto; }
#ct-main-table td { padding: 5px 4px; border-bottom: 1px solid #efece0; text-align: center; vertical-align: middle; height: 38px; box-sizing: border-box; font-variant-numeric: tabular-nums; }
#ct-main-table tr:hover { background: rgba(15,110,86,0.05); }
/* group-start borders - 4 pattern families + stage-info block */
#ct-main-table td.grp-start-stageinfo, #ct-main-table th.grp-start-stageinfo { border-left: 2px solid rgba(122,106,58,0.40); }
#ct-main-table td.grp-start-g1, #ct-main-table th.grp-start-g1 { border-left: 2px solid rgba(15,110,86,0.40); }
#ct-main-table td.grp-start-g2, #ct-main-table th.grp-start-g2 { border-left: 2px solid rgba(29,122,78,0.40); }
#ct-main-table td.grp-start-g3, #ct-main-table th.grp-start-g3 { border-left: 2px solid rgba(24,95,165,0.40); }
#ct-main-table td.grp-start-g4, #ct-main-table th.grp-start-g4 { border-left: 2px solid rgba(186,117,23,0.40); }
#ct-main-table td.pi-pass { background: rgba(15,110,86,0.12); color: #0F6E56; font-weight: 700; }
#ct-main-table td.pi-fail { color: #999; }
/* test-column kind tints: setup / gate / vcp / trigger get a faint top accent */
#ct-main-table td.ct-test-gate.pi-fail    { background: rgba(122,106,58,0.04); }
#ct-main-table td.ct-test-setup.pi-fail   { background: rgba(60,90,120,0.03); }
#ct-main-table td.ct-test-vcp.pi-fail     { background: rgba(29,122,78,0.03); }
#ct-main-table td.ct-test-trigger.pi-fail { background: rgba(186,117,23,0.04); }
/* Rating + score column group (D-MD-V2-55) */
#ct-main-table td.pi-rating-cell { padding: 3px 4px; }
#ct-main-table .pi-pill { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 9px; font-weight: 700; line-height: 1.3; white-space: nowrap; }
#ct-main-table .pi-pill-tint-prob { background: #0F6E56; color: #fff; }
#ct-main-table .pi-pill-tint-pla  { background: rgba(15,110,86,0.30); color: #0a4a3a; }
#ct-main-table .pi-pill-tint-pos  { background: rgba(15,110,86,0.14); color: #3a6a5a; }
#ct-main-table .pi-pill-tint-none { background: #ece9dd; color: #999; }
#ct-main-table td.pi-score-cell { padding: 4px 3px; }
#ct-main-table .pi-pip-row { display: inline-flex; align-items: center; gap: 2px; justify-content: center; }
#ct-main-table .pi-pip-row .pip { width: 6px; height: 6px; border-radius: 50%; background: #d8d4c4; display: inline-block; }
#ct-main-table .pi-pip-row .pip.on { background: #0F6E56; }
#ct-main-table .pi-pip-row .pi-score-num { font-size: 9px; color: #777; margin-left: 3px; font-weight: 600; }
/* 4-stage info block + Collapsing-rating info column - muted, info-only */
#ct-main-table td.ct-stage-info-cell, #ct-main-table td.ct-info-cell { padding: 3px 4px; }
#ct-main-table .ct-info-label { display: inline-block; padding: 2px 5px; border-radius: 3px; font-size: 9px; font-weight: 600; line-height: 1.3; white-space: nowrap; }
#ct-main-table td.ct-stage-info-cell.tint-prob .ct-info-label, #ct-main-table td.ct-info-cell.tint-prob .ct-info-label { background: rgba(15,110,86,0.22); color: #0a4a3a; }
#ct-main-table td.ct-stage-info-cell.tint-pla  .ct-info-label, #ct-main-table td.ct-info-cell.tint-pla  .ct-info-label { background: rgba(15,110,86,0.13); color: #3a6a5a; }
#ct-main-table td.ct-stage-info-cell.tint-pos  .ct-info-label, #ct-main-table td.ct-info-cell.tint-pos  .ct-info-label { background: rgba(15,110,86,0.07); color: #6a7a72; }
#ct-main-table td.ct-stage-info-cell.tint-none .ct-info-label, #ct-main-table td.ct-info-cell.tint-none .ct-info-label { background: #f0ede1; color: #aaa; }
/* L5D / L20D recent-trigger window cells (D-MD-V2-67) */
#ct-main-table td.ct-window-col { padding: 3px 4px; font-size: 10px; }
#ct-main-table td.ct-window-fired-recent { background: rgba(15,110,86,0.16); }
#ct-main-table td.ct-window-fired-recent .ct-window-label { color: #0a4a3a; font-weight: 700; }
#ct-main-table td.ct-window-fired-older { background: rgba(186,117,23,0.14); }
#ct-main-table td.ct-window-fired-older .ct-window-label { color: #7a4e0a; font-weight: 600; }
#ct-main-table td.ct-window-none { color: #bbb; }
#ct-main-table td.ct-window-building { color: #b59a5a; font-style: italic; font-size: 9px; }
#ct-main-table td.ct-window-na { color: #ccc; }
#ct-main-table td.name-cell { text-align: left; padding: 4px 4px 4px 8px; line-height: 1.15; }
#ct-main-table td.name-cell .co { font-weight: 700; font-size: 11px; color: #2a2a2a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#ct-main-table td.name-cell .tk { font-size: 9px; color: #999; font-weight: 500; margin-top: 1px; }
#ct-main-table td.name-cell .live-dot { color: #2e7d32; font-weight: 700; margin-right: 4px; display: inline-block; vertical-align: middle; line-height: 1; font-size: 10px; }
#ct-main-table td.taxon { text-align: left; font-size: 9px; line-height: 1.2; padding: 4px; }
#ct-main-table td.taxon .ind { color: #666; font-weight: 500; }
#ct-main-table td.taxon .sec { color: #999; }
#ct-main-table col.c-name { width: 124px; }
#ct-main-table col.c-taxon { width: 150px; }
#ct-main-table col.c-price { width: 50px; }
#ct-main-table col.c-52wh { width: 48px; }
#ct-main-table col.c-52wl { width: 48px; }
#ct-main-table col.c-ma150 { width: 48px; }
#ct-main-table col.c-ma200 { width: 48px; }
#ct-main-table col.c-pullback { width: 58px; }
#ct-main-table col.c-stageinfo { width: 56px; }
#ct-main-table col.c-rating { width: 64px; }
#ct-main-table col.c-score { width: 52px; }
#ct-main-table col.c-test { width: 64px; }
#ct-main-table col.c-info { width: 60px; }
#ct-main-table col.c-window { width: 52px; }
#ct-main-table tr.tint-row td.name-cell, #ct-main-table tr.tint-row td.taxon { background: var(--tint-bg) !important; }
#ct-main-table tr.portfolio-band td:last-child { border-right: 4px solid var(--portfolio-color); }
#ct-main-table tr.portfolio-tint { background: var(--portfolio-bg); }
#ct-main-table tr.portfolio-tint:hover { background: var(--portfolio-bg-hover); }
/* MD-V2-PI-CHIPS-S25-MARKER: rating-tier multi-select chip filter (D-MD-V2-59) */
#tab-tests .s1-rating-tiles .pi-tier-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 7px; }
#tab-tests .pi-tier-chip { font-size: 10px; padding: 2px 6px; border-radius: var(--border-radius-md, 4px); cursor: pointer; user-select: none; border: 0.5px solid; line-height: 1.4; white-space: nowrap; transition: background 0.12s, color 0.12s; }
#tab-tests .pi-chip-pullback { background: #E1F5EE; color: #0F6E56; border-color: #9FE1CB; }
#tab-tests .pi-chip-pullback.on { background: #0F6E56; color: #fff; border-color: #0F6E56; font-weight: 500; }
#tab-tests .pi-chip-basing { background: #E1F5EE; color: #0F6E56; border-color: #9FE1CB; }
#tab-tests .pi-chip-basing.on { background: #1D7A4E; color: #fff; border-color: #1D7A4E; font-weight: 500; }
#tab-tests .pi-tier-chip:hover { filter: brightness(0.96); }
#tab-tests .s1-rating-tiles .rating-tile.active { box-shadow: inset 0 0 0 1.5px currentColor; }
#tab-tests .pi-chip-amber { background: #FAEEDA; color: #854F0B; border-color: #FAC775; }
#tab-tests .pi-chip-amber.on { background: #BA7517; color: #fff; border-color: #BA7517; font-weight: 500; }
#tab-tests .pi-chip-navy { background: #E6F1FB; color: #0C447C; border-color: #B5D4F4; }
#tab-tests .pi-chip-navy.on { background: #185FA5; color: #fff; border-color: #185FA5; font-weight: 500; }
#tab-tests .s1-rating-tiles .pi-tile-amber { background: rgba(186,117,23,0.10); border: 1px solid rgba(186,117,23,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
#tab-tests .s1-rating-tiles .pi-tile-amber.active { background: rgba(186,117,23,0.22); border: 1.5px solid #BA7517; }
#tab-tests .s1-rating-tiles .pi-strip-amber { background: #BA7517; height: 4px; margin-top: 6px; border-radius: 2px; }
#tab-tests .s1-rating-tiles .pi-tile-navy { background: rgba(24,95,165,0.10); border: 1px solid rgba(24,95,165,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
#tab-tests .s1-rating-tiles .pi-tile-navy.active { background: rgba(24,95,165,0.22); border: 1.5px solid #185FA5; }
#tab-tests .s1-rating-tiles .pi-strip-navy { background: #185FA5; height: 4px; margin-top: 6px; border-radius: 2px; }
/* MD-V2-TESTS-MARKER-CSS-END */
/* MD-V2-WAVE1-FROZEN-HEADERS-MARKER-CSS-START */
/* MD-V2-WAVE1B-STICKY-CORRECTIVE-MARKER: relocated after TESTS CSS so it wins the cascade */
/* Wave 1 (14-May-26): sticky ribbon + corrected frozen-header offsets.
   --header-height is 70px on V2 tabs. --v2-ribbon-h is measured at render
   time by the JS helper below (the ribbon wraps at narrow widths so a
   fixed guess is fragile); it falls back to 46px before first measure. */
body[data-active-tab^="stage_"],
body[data-active-tab="pre_indicators"],
body[data-active-tab="post_indicators"],
body[data-active-tab^="setups"],
body[data-active-tab="tests"],
body[data-active-tab="tests_healthy_vcp"],
body[data-active-tab="tests_speculative_bet"],
body[data-active-tab="tests_probing_bet_s1"],
body[data-active-tab="tests_probing_bet_s2"],
body[data-active-tab="setups_healthy_retest"],
body[data-active-tab="master_overview"] { --v2-ribbon-h: 46px; }

/* The ribbon: sticky directly under the fixed MD V2 nav header. */
body[data-active-tab^="stage_"] .controls.s1-controls,
body[data-active-tab="pre_indicators"] .controls.s1-controls,
body[data-active-tab="post_indicators"] .controls.s1-controls,
body[data-active-tab^="setups"] .controls.s1-controls,
body[data-active-tab="tests"] .controls.s1-controls,
body[data-active-tab="tests_healthy_vcp"] .controls.s1-controls,
body[data-active-tab="tests_speculative_bet"] .controls.s1-controls,
body[data-active-tab="tests_probing_bet_s1"] .controls.s1-controls,
body[data-active-tab="tests_probing_bet_s2"] .controls.s1-controls,
body[data-active-tab="setups_healthy_retest"] .controls.s1-controls,
body[data-active-tab="master_overview"] .controls.s1-controls {
  position: sticky;
  top: var(--header-height);
  left: 0;  /* MD-V2-WAVE3C-REAL-STICKY-FIX-MARKER: pin horizontally so the ribbon does not drift on horizontal page scroll */
  z-index: 60;
  box-shadow: 0 2px 5px rgba(0,0,0,0.07);
}

/* Frozen table headers: re-anchor every V2 table's sticky rows below the
   fixed header AND the sticky ribbon. Stage 1-4 tables have 2 header rows
   (group-header + col-header); PI/PO/ST have 3 (super-group + group +
   col); CT has 2. Each row stacks on the one above it. z-index lifted
   above the ribbon's 60. The thead's own sticky/top is neutralised so the
   per-ROW offsets are what take effect. */
#s1-main-table thead, #s2-main-table thead, #s3-main-table thead,
#s4-main-table thead, #pi-main-table thead, #po-main-table thead,
.st-main-table thead, #ct-main-table thead {
  position: static !important;
  z-index: auto !important;
  box-shadow: none !important;
}
/* Stage 1-4: group-header row height ~28px (matches old col-header top). */
#s1-main-table thead tr.group-header-row th,
#s2-main-table thead tr.group-header-row th,
#s3-main-table thead tr.group-header-row th,
#s4-main-table thead tr.group-header-row th {
  position: sticky;
  top: calc(var(--header-height) + var(--v2-ribbon-h));
  z-index: 70;
}
#s1-main-table thead tr.col-header-row th,
#s2-main-table thead tr.col-header-row th,
#s3-main-table thead tr.col-header-row th,
#s4-main-table thead tr.col-header-row th {
  position: sticky;
  top: calc(var(--header-height) + var(--v2-ribbon-h) + 28px);
  z-index: 70;
}
/* PI / PO / ST: 3 header rows. Row heights 24px (super-group) + 24px
   (group-header) measured from the existing 0/24/48 ladder. */
#pi-main-table thead tr.super-group-row th,
#po-main-table thead tr.super-group-row th,
.st-main-table thead tr.super-group-row th {
  position: sticky;
  top: calc(var(--header-height) + var(--v2-ribbon-h));
  z-index: 72;
}
#pi-main-table thead tr.group-header-row th,
#po-main-table thead tr.group-header-row th,
.st-main-table thead tr.group-header-row th {
  position: sticky;
  top: calc(var(--header-height) + var(--v2-ribbon-h) + 24px);
  z-index: 71;
}
#pi-main-table thead tr.col-header-row th,
#po-main-table thead tr.col-header-row th,
.st-main-table thead tr.col-header-row th {
  position: sticky;
  top: calc(var(--header-height) + var(--v2-ribbon-h) + 48px);
  z-index: 70;
}
/* MD-V2-WAVE2-TESTS-SUBGROUP-MARKER: CT now has 3 header rows -
   group-header -> sub-group -> col-header. Re-stacked from the Wave 1
   2-row state. Row heights: group ~24px, sub-group ~22px. */
#ct-main-table thead tr.group-header-row th {
  position: sticky;
  top: calc(var(--header-height) + var(--v2-ribbon-h));
  z-index: 72;
}
#ct-main-table thead tr.sub-group-row th {
  position: sticky;
  top: calc(var(--header-height) + var(--v2-ribbon-h) + 24px);
  z-index: 71;
  background: #f7f3e6 !important;
  font-size: 8.5px;
  text-transform: uppercase;
  font-weight: 700;
  letter-spacing: 0.5px;
  padding: 4px 3px;
  cursor: default;
  line-height: 1.2;
  color: #7a7560;
}
#ct-main-table thead tr.sub-group-row th:hover { background: #f7f3e6 !important; }
#ct-main-table thead tr.sub-group-row th.sg-spacer { background: #fbfaf5 !important; }
#ct-main-table thead tr.sub-group-row th.sub-g-rating  { color: #555; }
#ct-main-table thead tr.sub-group-row th.sub-g-setup   { color: #4a6a8a; border-bottom: 2px solid rgba(74,106,138,0.40); }
#ct-main-table thead tr.sub-group-row th.sub-g-trigger { color: #9a5a2a; border-bottom: 2px solid rgba(154,90,42,0.45); }
#ct-main-table thead tr.sub-group-row th.sub-g-context { color: #8a8674; }
#ct-main-table thead tr.col-header-row th {
  position: sticky;
  top: calc(var(--header-height) + var(--v2-ribbon-h) + 46px);
  z-index: 70;
}
/* MD-V2-WAVE2-TESTS-SUBGROUP-MARKER: horizontal scroll on the table wrap for every V2
   tab. The CT table is ~3340px wide; .table-wrap had overflow:visible
   so the right-hand columns spilled off-screen unreachable. overflow-x
   auto gives a horizontal scrollbar; overflow-y stays visible so the
   viewport-anchored sticky header `top:` offsets are unaffected. */
/* MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER: Wave 3b (14-May-26) corrective. The Wave 2 rule put
   overflow-x:auto on .table-wrap; CSS then coerces overflow-y to auto,
   making .table-wrap a scroll container that TRAPS the Wave 1 sticky
   thead rows so they never pin to the viewport. Fix: .table-wrap goes
   back to overflow:visible (not a scroll container -> sticky anchors to
   the viewport and freezes), and the horizontal scroll moves to a new
   inner wrapper .v2-hscroll. .v2-hscroll IS a scroll container but it
   scrolls HORIZONTALLY only; a horizontal-only scroll container does
   not become the containing block for VERTICAL sticky positioning, so
   the frozen headers keep working AND wide tables still scroll sideways. */
body[data-active-tab^="stage_"] .table-wrap,
body[data-active-tab="pre_indicators"] .table-wrap,
body[data-active-tab="post_indicators"] .table-wrap,
body[data-active-tab^="setups"] .table-wrap,
body[data-active-tab="tests"] .table-wrap,
body[data-active-tab="tests_healthy_vcp"] .table-wrap,
body[data-active-tab="tests_speculative_bet"] .table-wrap,
body[data-active-tab="tests_probing_bet_s1"] .table-wrap,
body[data-active-tab="tests_probing_bet_s2"] .table-wrap,
body[data-active-tab="setups_healthy_retest"] .table-wrap,
body[data-active-tab="master_overview"] .table-wrap {
  overflow: visible;
}
/* MD-V2-WAVE3C-REAL-STICKY-FIX-MARKER: Wave 3c (14-May-26). Wave 3b's theory was wrong - CSS
   coerces overflow-x:auto + overflow-y:visible to overflow:auto/auto, so
   .v2-hscroll became a full scroll container and trapped sticky just like
   .table-wrap did. Neutralise .v2-hscroll to overflow:visible (inert
   pass-through wrapper) and move the horizontal scroll to `body` itself -
   the only non-trapping option, since any intermediate overflow-x:auto
   ancestor also gets overflow-y:auto and steals the sticky anchor. */
body[data-active-tab^="stage_"] .v2-hscroll,
body[data-active-tab="pre_indicators"] .v2-hscroll,
body[data-active-tab="post_indicators"] .v2-hscroll,
body[data-active-tab^="setups"] .v2-hscroll,
body[data-active-tab="tests"] .v2-hscroll,
body[data-active-tab="tests_healthy_vcp"] .v2-hscroll,
body[data-active-tab="tests_speculative_bet"] .v2-hscroll,
body[data-active-tab="tests_probing_bet_s1"] .v2-hscroll,
body[data-active-tab="tests_probing_bet_s2"] .v2-hscroll,
body[data-active-tab="setups_healthy_retest"] .v2-hscroll,
body[data-active-tab="master_overview"] .v2-hscroll {
  overflow: visible;
}
/* MD-V2-WAVE3C-REAL-STICKY-FIX-MARKER: the page itself is the horizontal scroller on V2 tabs.
   Scoped to the 6 V2 tab-states so legacy tabs keep body overflow-x:hidden. */
body[data-active-tab^="stage_"],
body[data-active-tab="pre_indicators"],
body[data-active-tab="post_indicators"],
body[data-active-tab^="setups"],
body[data-active-tab="tests"],
body[data-active-tab="tests_healthy_vcp"],
body[data-active-tab="tests_speculative_bet"],
body[data-active-tab="tests_probing_bet_s1"],
body[data-active-tab="tests_probing_bet_s2"],
body[data-active-tab="setups_healthy_retest"],
body[data-active-tab="master_overview"] {
  overflow-x: auto;
}
/* MD-V2-WAVE3-MASTER-OVERVIEW-MATRIX-MARKER: Wave 3 (14-May-26) - Master Overview full rating
   matrix. A second table appended below the existing distribution table.
   Lives inside the Wave 1 CSS block so it is last in source order and wins
   the cascade against the base #mo-main-table rules (D-MD-V2-76 lesson).
   Sticky header stack reuses the Wave 1 --header-height + --v2-ribbon-h
   ladder: chip row -> section-group row -> column-title row. */
#mo-matrix-wrap { margin-top: 18px; }
#mo-matrix-caption { font-size: 11px; color: #7a7560; margin: 0 0 6px 2px; }
#mo-matrix-table { border-collapse: separate; border-spacing: 0; font-size: 12px; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; table-layout: fixed; }
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
  top: calc(var(--header-height) + var(--v2-ribbon-h));
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
  top: calc(var(--header-height) + var(--v2-ribbon-h) + 22px);
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
  overflow: hidden; text-overflow: ellipsis;
}
#mo-matrix-table tbody tr:hover td.mo-mx-name-cell { background: #f4f1e6; }
#mo-matrix-table tbody td.mo-mx-name-cell .mo-mx-co { font-weight: 600; color: #2a2a2a; }
#mo-matrix-table tbody td.mo-mx-name-cell .mo-mx-tk { color: #a39d88; font-size: 10px; margin-left: 0; }
#mo-matrix-table tbody td.mo-mx-name-cell .mo-mx-tk::before { content: ' \00B7 '; color: #c8c4b0; margin-right: 1px; }
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
/* MD-V2-WAVE1-FROZEN-HEADERS-MARKER-CSS-END */

/* MD-V2-MASTER-OVERVIEW-MARKER-CSS-START */
/* MD-V2-OVERVIEW-COOCCURRENCE-S35-MARKER: Master Overview summary table -
   transposed (the four rating tiers + a Total rated row run DOWN, the 20
   screens run ACROSS) and sized to the matrix's exact column widths
   (190px + 20x64px) so the two tables line up under the shared page-body
   horizontal scroll. The summary table is now a co-occurrence selector:
   clicking a count cell selects that screen-and-tier criterion; every cell
   then shows the count of stocks meeting all selected criteria AND its own;
   the matrix below filters to that set. Replaces the Wave 3 per-column chip
   filter (chips removed; the chip CSS above is now inert/dead). */
#mo-main-table { border-collapse: separate; border-spacing: 0; font-size: 12px; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; table-layout: fixed; }
#mo-main-table thead { position: static; }
#mo-main-table thead th { background: #f3efe2; border-bottom: 1px solid #e0dcc8; }
/* section-group band - reuses the matrix mo-mx-g-* colour hooks */
#mo-main-table thead tr.mo-group-row th { font-size: 9px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; padding: 5px 6px; text-align: center; border-left: 1px solid #e0dcc8; }
#mo-main-table thead tr.mo-group-row th.mo-mx-g-stages   { color: #1b5e20; }
#mo-main-table thead tr.mo-group-row th.mo-mx-g-pretest  { color: #0F6E56; }
#mo-main-table thead tr.mo-group-row th.mo-mx-g-posttest { color: #A32D2D; }
#mo-main-table thead tr.mo-group-row th.mo-mx-g-setups   { color: #BA7517; }
#mo-main-table thead tr.mo-group-row th.mo-mx-g-tests    { color: #185FA5; }
/* column-title row - one cell per screen, labels WRAP, click to open the tab */
#mo-main-table thead tr.mo-col-row th { width: 64px; min-width: 64px; max-width: 64px; font-size: 9.5px; font-weight: 700; color: #555; padding: 5px 4px; text-align: center; vertical-align: bottom; line-height: 1.2; white-space: normal; word-break: normal; overflow-wrap: break-word; cursor: pointer; }
#mo-main-table thead tr.mo-col-row th:hover { color: #0F6E56; text-decoration: underline; }
/* sticky-left first column - aligns with the matrix 190px Stock column */
#mo-main-table thead th.mo-corner { position: sticky; left: 0; z-index: 6; width: 190px; min-width: 190px; max-width: 190px; text-align: left; vertical-align: bottom; padding: 5px 10px; border-right: 1px solid #e0dcc8; font-size: 9px; color: #9a9582; text-transform: uppercase; letter-spacing: 0.4px; }
#mo-main-table tbody td { padding: 7px 6px; border-bottom: 1px solid #efece0; text-align: center; vertical-align: middle; font-variant-numeric: tabular-nums; }
#mo-main-table tbody td.mo-tier-label { position: sticky; left: 0; z-index: 5; background: #fbfaf5; text-align: left; font-weight: 600; color: #2a2a2a; padding: 7px 10px; border-right: 1px solid #e0dcc8; }
#mo-main-table tbody tr:hover td.mo-tier-label { background: #f4f1e6; }
#mo-main-table tbody tr.mo-data-row:hover { background: rgba(15,110,86,0.05); }
#mo-main-table td.mo-cell { cursor: pointer; font-weight: 600; transition: filter 0.12s; }
#mo-main-table td.mo-cell:hover { filter: brightness(0.94); outline: 1.5px solid rgba(15,110,86,0.4); outline-offset: -1.5px; }
#mo-main-table td.mo-cell.mo-zero { color: #c4c0b0; font-weight: 400; }
#mo-main-table td.mo-t-none.mo-has  { background: #f0ede1; color: #999; }
#mo-main-table td.mo-t-pos.mo-has   { background: rgba(15,110,86,0.10); color: #3a6a5a; }
#mo-main-table td.mo-t-pla.mo-has   { background: rgba(15,110,86,0.20); color: #1a5446; }
#mo-main-table td.mo-t-prob.mo-has  { background: rgba(15,110,86,0.34); color: #0a3a2e; }
/* a selected co-occurrence cell */
#mo-main-table td.mo-cell.mo-cell-sel { outline: 2.5px solid #BA7517; outline-offset: -2.5px; box-shadow: inset 0 0 0 2px rgba(186,117,23,0.30); font-weight: 700; color: #6e4310; background: rgba(186,117,23,0.12) !important; }
#mo-main-table td.mo-cell.mo-cell-sel:hover { filter: none; outline: 2.5px solid #BA7517; }
/* Total rated row */
#mo-main-table tr.mo-total-row td { border-top: 2px solid #e0dcc8; }
#mo-main-table tr.mo-total-row td.mo-total-cell { color: #777; font-weight: 700; background: #faf8f0; }
#mo-main-table tr.mo-total-row td.mo-tier-label { color: #777; }
/* the Clear-all button shows armed when a selection is active */
#mo-clear-btn.active { background: #BA7517; border-color: #BA7517; color: #fff; }
/* MD-V2-S38-SECTIONS-OVERVIEW-MARKER: comprehensive Overview supergroup grouping.
   Each supergroup column block gets BOTH a left border on its first cell and a
   right border on its last cell, on BOTH tables (summary + matrix). 2px wide,
   ~45% alpha so the bracketing reads as a guide rather than a hard line.
   The supergroup header cells also get a very subtle (~7% alpha) background
   tint towards their text colour, so the supergroup is visible even where the
   body cells happen to all be the same tier-tint. */
/* body-cell left borders (first column of each section) */
#mo-matrix-table tbody td.mo-sec-start-stages,   #mo-main-table tbody td.mo-sec-start-stages   { border-left: 2px solid rgba(27,94,32,0.45); }
#mo-matrix-table tbody td.mo-sec-start-pretest,  #mo-main-table tbody td.mo-sec-start-pretest  { border-left: 2px solid rgba(15,110,86,0.45); }
#mo-matrix-table tbody td.mo-sec-start-posttest, #mo-main-table tbody td.mo-sec-start-posttest { border-left: 2px solid rgba(163,45,45,0.45); }
#mo-matrix-table tbody td.mo-sec-start-setups,   #mo-main-table tbody td.mo-sec-start-setups   { border-left: 2px solid rgba(186,117,23,0.45); }
#mo-matrix-table tbody td.mo-sec-start-tests,    #mo-main-table tbody td.mo-sec-start-tests    { border-left: 2px solid rgba(24,95,165,0.45); }
/* body-cell right borders (last column of each section) */
#mo-matrix-table tbody td.mo-sec-end-stages,   #mo-main-table tbody td.mo-sec-end-stages   { border-right: 2px solid rgba(27,94,32,0.45); }
#mo-matrix-table tbody td.mo-sec-end-pretest,  #mo-main-table tbody td.mo-sec-end-pretest  { border-right: 2px solid rgba(15,110,86,0.45); }
#mo-matrix-table tbody td.mo-sec-end-posttest, #mo-main-table tbody td.mo-sec-end-posttest { border-right: 2px solid rgba(163,45,45,0.45); }
#mo-matrix-table tbody td.mo-sec-end-setups,   #mo-main-table tbody td.mo-sec-end-setups   { border-right: 2px solid rgba(186,117,23,0.45); }
#mo-matrix-table tbody td.mo-sec-end-tests,    #mo-main-table tbody td.mo-sec-end-tests    { border-right: 2px solid rgba(24,95,165,0.45); }
/* very subtle header tint on each supergroup group-band cell */
#mo-matrix-table thead tr.mo-mx-group-row th.mo-mx-g-stages,
#mo-main-table   thead tr.mo-group-row    th.mo-mx-g-stages   { background-color: rgba(27,94,32,0.07); }
#mo-matrix-table thead tr.mo-mx-group-row th.mo-mx-g-pretest,
#mo-main-table   thead tr.mo-group-row    th.mo-mx-g-pretest  { background-color: rgba(15,110,86,0.07); }
#mo-matrix-table thead tr.mo-mx-group-row th.mo-mx-g-posttest,
#mo-main-table   thead tr.mo-group-row    th.mo-mx-g-posttest { background-color: rgba(163,45,45,0.07); }
#mo-matrix-table thead tr.mo-mx-group-row th.mo-mx-g-setups,
#mo-main-table   thead tr.mo-group-row    th.mo-mx-g-setups   { background-color: rgba(186,117,23,0.07); }
#mo-matrix-table thead tr.mo-mx-group-row th.mo-mx-g-tests,
#mo-main-table   thead tr.mo-group-row    th.mo-mx-g-tests    { background-color: rgba(24,95,165,0.07); }
/* MD-V2-OVERVIEW-COLALIGN-S35B-MARKER: shared colgroup widths -
   240px first column + 20x76px screen columns; combined with
   table-layout:fixed on both tables, this is what makes the
   summary table line up column-for-column with the matrix. */
col.mo-cg-label  { width: 240px; }
col.mo-cg-screen { width: 76px; }
/* MD-V2-MASTER-OVERVIEW-MARKER-CSS-END */




/* MD-V2-REMOVE-SUMMARY-MARKER applied 20260513-184203 */
"""

    # ---- JavaScript ----
    js = r"""
(function(){
"use strict";
var D=MASTER_DATA;
var priceMap={},filterMap={},tmMap=D.ticker_mapping||{};
var currentTab="master_overview",currentSort={col:"chg_qual_count",dir:"desc"}; /* SUMMARY-TAB-DEFAULT MD-V2-DEFAULT-TAB-FIX-S27-MARKER: was stage_1, Master Overview is the default landing tab */
/* BOOTSTRAP-DEFAULT-TAB-FIX-1 */
if(typeof window!=="undefined"){window.__chgBootstrapDone=window.__chgBootstrapDone||false;var __chgBoot=function(){if(window.__chgBootstrapDone)return;if(typeof window.switchTab!=="function"){setTimeout(__chgBoot,30);return;}window.__chgBootstrapDone=true;try{window.switchTab(currentTab);}catch(e){console.error("bootstrap switchTab failed",e);}};if(document.readyState==="loading"){document.addEventListener("DOMContentLoaded",__chgBoot);}else{setTimeout(__chgBoot,30);}}
var mm99MinScore=0;
var utrMinCap=0;
var utrStageFilter="";  // ""=all, "early"=Early+, "late"=Late+, "capital"=Capital only
var utrFailedFilter="";  // ""=off, "L1W"=last 1 week, "L1M"=last 1 month
var utrShowInputs=false;  // default hidden
var chgSectorGrouping=false;  // CHANGES tab: sector separator rows off by default
var chgHighestQual=false;  // CHANGES tab: show each stock only in rightmost Capital filter tile
var displayMode="company";  /* Pass A.2: default to Company name across all tabs (was "ticker") */
var valueMode="tick";
var bpFirstVisit=true;  /* Pass A.2: flip to pct mode on first BP visit (only) */
var showRatings=false;
var TAB_IDS=[""" + tab_ids_js + r"""];
var TAB_LABELS=[""" + tab_labels_js + r"""];
var TAB_ACCENTS=[""" + tab_accents_js + r"""];
var activeGroups={};
// FEAT-5: Industry/sector filter state (resets on tab switch)
var indFilter={};  // {industry_name: true, ...}
var secFilter={};  // {sector_name: true, ...}
window.toggleIndFilter=function(ind){
  if(indFilter[ind])delete indFilter[ind];else indFilter[ind]=true;
  renderTab(currentTab);
};
window.toggleSecFilter=function(sec){
  if(secFilter[sec])delete secFilter[sec];else secFilter[sec]=true;
  renderTab(currentTab);
};
window.clearIndSecFilter=function(){
  indFilter={};secFilter={};renderTab(currentTab);
};
function hasIndSecFilter(){
  for(var k in indFilter)if(indFilter.hasOwnProperty(k))return true;
  for(var k in secFilter)if(secFilter.hasOwnProperty(k))return true;
  return false;
}
function passIndSecFilter(r){
  var hasInd=false,hasSec=false;
  for(var k in indFilter)if(indFilter.hasOwnProperty(k)){hasInd=true;break}
  for(var k in secFilter)if(secFilter.hasOwnProperty(k)){hasSec=true;break}
  if(!hasInd&&!hasSec)return true;
  var indOk=!hasInd||indFilter[r._tax_industry];
  var secOk=!hasSec||secFilter[r._tax_sector];
  return indOk&&secOk;
}
function applyIndSecFilter(rows){var out=[];for(var j=0;j<rows.length;j++){if(passIndSecFilter(rows[j]))out.push(rows[j])}return out}
function indSecFilterPills(){
  if(!hasIndSecFilter())return"";
  var h='<span class="filter-pill" onclick="clearIndSecFilter()" style="margin-left:12px;cursor:pointer;background:#e74c3c;color:#fff;padding:2px 10px;border-radius:12px;font-size:11px;font-weight:600">';
  var parts=[];
  for(var k in indFilter)if(indFilter.hasOwnProperty(k))parts.push(k);
  for(var k in secFilter)if(secFilter.hasOwnProperty(k))parts.push(k);
  h+=parts.join(" + ")+' &times;</span>';
  return h;
}
// FIX-S4-PBEXCL: Exclude toggles for PB tab
var pbExcludes={ex_mm99:false,ex_vcp:false,ex_utr:false};
window.togglePbExclude=function(k){pbExcludes[k]=!pbExcludes[k];renderTab("pb")};

// === SESSION 9: COMBO tab — TIMELINESS rating + stage/setup filter toggles ===
// D-MD-UI-7: All ON default, sticky across tab switches, reset only on full page reload.
// D-MD-FILTER-6: Capital Qual = stage==="Capital" per filter (already in data pipeline).
// D-MD-FILTER-7: Ladder A>B>C>F>D>− (F overrides D among negatives).
// D-MD-FILTER-10: Grade is independent of header toggles (computed from full filter universe).
var comboStageFilters={capital:true,late:true,early:true};
var comboSetupFilters={bp:true,pb:true,vcp:true,mm99:true,utr:true};
// SESSION 9 Pass 1.2: D-MD-UI-11 grade filter — applies to BOTH Qualified Stocks AND Live Portfolio.
var comboGradeFilters={A:true,B:true,C:true,D:true,F:true,N:true};
window.toggleComboStage=function(k){comboStageFilters[k]=!comboStageFilters[k];renderTab("combos")};
window.toggleComboSetup=function(k){comboSetupFilters[k]=!comboSetupFilters[k];renderTab("combos")};
window.toggleComboGrade=function(k){comboGradeFilters[k]=!comboGradeFilters[k];renderTab("combos")};

// Per-stock TIMELINESS grade (A/B/C/D/F/-).
// Pass 1: uses 5 existing filters. Collapse/S3/S4 placeholders return false.
function timeliness(r){
  var bp=r.f.basing_plateau,pb=r.f.probing_bet,vcp=r.f.vcp,mm=r.f.mm99,ut=r.f.uptrend_retest;
  var capUTR=ut&&ut.stage==="Capital";
  var capVCP=vcp&&vcp.stage==="Capital"; // D-MD-FILTER-6: VCP placeholder, always false in Pass 1
  var capMM=mm&&mm.stage==="Capital";
  var capPB=pb&&pb.stage==="Capital";
  var capCol=false; // Pass 2: Collapse filter
  var capBP=bp&&bp.stage==="Capital";
  var capS4=false; // Pass 2: Stage 4 Declining
  var capS3=false; // Pass 2: Stage 3 Topping
  if(capUTR||capVCP||capMM)return"A";
  if(capPB||capCol)return"B";
  if(capBP)return"C";
  if(capS4)return"F"; // F overrides D
  if(capS3)return"D";
  return"-";
}
function timelinessBadge(g){
  var cls=g==="-"?"tm-N":"tm-"+g;
  var label=g==="-"?"&mdash;":g;
  return'<span class="tm-grade '+cls+'">'+label+'</span>';
}
// Sort key: A=5, B=4, C=3, D=2, F=1, -=0 (descending = best first per D-MD-UI-8)
function timelinessSortKey(g){
  if(g==="A")return 5;if(g==="B")return 4;if(g==="C")return 3;
  if(g==="D")return 2;if(g==="F")return 1;return 0;
}

var CANONICAL_INDUSTRIES=[
  "A. Consumer staples","B. Healthcare","C. Telecoms",
  "E. Utilities","F. Defence",
  "G. Financials","H. Consumer discretionary",
  "I. Transportation","J. Technology",
  "K. Professional, business and consumer services",
  "L. Media","M. Materials","N. Real assets",
  "O. Industrials and capital goods",
  "P. Energy, commodities and metals mining"
];

var i;
for(i=0;i<D.prices.length;i++)priceMap[D.prices[i].ticker]=D.prices[i];
for(i=0;i<D.filters.length;i++)filterMap[D.filters[i].ticker]=D.filters[i];

// BUG-1-FIX: Build position ticker set + ensure all positions have filter stubs
var positionTickerSet={};
if(D.positions&&D.positions.investments){
  for(i=0;i<D.positions.investments.length;i++){
    var pt=D.positions.investments[i].ticker;
    positionTickerSet[pt]=true;
    // Create stub filter entry if missing
    if(!filterMap[pt]){
      filterMap[pt]={ticker:pt,mm99:{score_11:0,stage:"",group_a:{pass:false,tests:{T1:false,T2:false},ma200_months_rising:0},group_b:{pass:false,tests:{T3:false,T4:false}},group_c:{pass:false,tests:{T5:false,T6:false}},group_d:{pass:false,tests:{T7:false,T8:false}},group_e:{pass:false,tests:{T9:false,T10:false,T11:false},rs_vs_sector:null,rs_excess_sector:null,rs_excess_industry:null,rs_excess_market:null}},basing_plateau:{stage:"",group_a:{pass:false,tests:{T1:false,T2:false}},group_b:{pass:false,tests:{T3:false,T4:false,T5:false}},group_c:{pass:false,tests:{T6:false,T7:false,T8:false}}},probing_bet:{stage:"",group_a:{pass:false,tests:{T1:false,T2:false,T3:false,T4:false,T5:false}},group_b:{pass:false,tests:{T6:false,T7:false}},group_c:{pass:false,tests:{T8:false}},group_d:{pass:false,tests:{T9:false,T10:false}},group_e:{pass:false,tests:{T11:false,T12:false}}},uptrend_retest:{composite:0,signals:[]},vcp:{stage2:false}};
    }
    // Create stub price entry if missing
    if(!priceMap[pt]){
      var tax=getTaxonomy?getTaxonomy(pt):{industry:"",sector:""};
      D.prices.push({ticker:pt,company_name:pt,sector:tax.sector||"",industry:tax.industry||"",price:null,price_prev:null,high_52w:null,low_52w:null,mas:null,rs_percentile:null,rs_vs_sector:null,rs_composite:null,adv_1m:null,adv_3m:null,swing_high:null});
      priceMap[pt]=D.prices[D.prices.length-1];
    }
  }
}

document.getElementById("stat-count").textContent=D.meta.stock_count;
document.getElementById("stat-source").textContent=D.meta.source;
document.getElementById("stat-updated").textContent=D.meta.generated;
var _stUni=document.getElementById("stat-universe-updated");if(_stUni)_stUni.textContent=D.meta.universe_updated||"\u2014";  /* MD-V2-S36-BRIEF-MARKER */

// ---- Key panel column descriptions per tab ----
var KEY_DEFS={
  mm99:[
    ["Ticker","Stock ticker symbol"],["Sector","Industry sector classification"],["Price","Current stock price"],
    ["52W High","52-week high price (or % from high in % mode)"],["52W Low","52-week low price (or % from low in % mode)"],["RS","Relative Strength percentile (0-100)"],
    ["Score","Minervini 8-point technical score"],["Stage","Capital / Late / Early stage classification"],
    ["P>200D","Price above 200-day MA"],["200D Up","200-day MA trending upward (month count)"],
    ["P>150D","Price above 150-day MA"],["150>200","150-day MA above 200-day MA"],
    ["50>150","50-day MA above 150-day MA"],["P>50D","Price above 50-day MA"],
    ["P>20%L","Price at least 20% above 52-week low"],["P<25%H","Price within 25% of 52-week high"],
    ["Sector","Relative strength vs sector"],["Industry","Relative strength vs industry"],["Market","Relative strength vs market"]
  ],
  bp:[
    ["Ticker","Stock ticker symbol"],["Sector","Industry sector classification"],["Price","Current stock price"],
    ["Stage","Basing Plateau stage: Tight=Capital, Medium=Late, Loose=Early"],
    ["MA Map","Visual position of Price, 200D, 150D, 50D MAs"],
    ["T1-T2","Loose tests: Price and 50D within 15% of 200D"],
    ["T3-T5","Medium tests: Price, 50D, 150D within 10% of 200D"],
    ["T6-T8","Tight tests: Price, 50D, 150D within 5% of 200D"]
  ],
  pb:[
    ["Ticker","Stock ticker symbol"],["Stage","Probing Bet stage"],
    ["T1-T5","Group A: rising MAs (P, 5D, 10D, 20D, 50D)"],
    ["T6-T7","Group B: 20D and 50D rising"],
    ["Dead Cat","Group C: 30%+ below 52W high"],
    ["PB1/PB2","Capital entry: price above rising 20D/50D"]
  ],
  utr:[
    ["Ticker","Stock ticker symbol"],["Score","Composite pullback quality score (max 8)"],
    ["Depth-RS","8 signal assessments: pass/amber/fail"],
    ["EWS","Early warning signals count (5 max)"]
  ],
  vcp:[
    ["Ticker","Stock ticker symbol"],["Stage 2","In Stage 2 uptrend (Groups A+B pass)"],
    ["MM Score","Minervini 8-point score"]
  ],
  tech:[
    ["MAs","Moving averages at various periods"],["52W","52-week high and low"],["ADV","Average daily volume"]
  ],
  ssem:[
    ["EPS/EBITDA/Sales","Consensus revision % over 1M/3M/6M/12M"],
    ["TP","Target price revision %"],["Buy","% of analysts with Buy rating"],["Momentum","Composite momentum count"]
  ],
  val:[
    ["P/E","Current price-to-earnings ratio"],["Pctile","P/E percentile vs 10Y history (0=cheapest)"],
    ["Range","Visual: 10Y P/E range bar (green=below median, red=above)"],["EPS 24MF","24-month forward EPS estimate"]
  ]
};

// ---- Shared Utilities ----
function getTaxonomy(ticker){
  var m=tmMap[ticker];
  if(m)return{industry:m.industry||"",sector:m.sector||""};
  var p=priceMap[ticker];
  if(p)return{industry:p.industry||"",sector:p.sector||""};
  return{industry:"",sector:""};
}

window.switchTab=function(id){
  window.scrollTo(0,0);
  var b=document.querySelectorAll(".tab-btn");
  for(var j=0;j<b.length;j++){b[j].classList.remove("tab-active");if(b[j].getAttribute("data-tab")===id)b[j].classList.add("tab-active")}
  var c=document.querySelectorAll(".tab-content");
  for(var j=0;j<c.length;j++){c[j].style.display="none"}
  var el=document.getElementById("tab-"+id);
  if(el){
    el.style.display="block";
    currentTab=id;
    // Only render if tab is empty (first visit) or needs refresh
    if(!el.innerHTML||el.getAttribute("data-stale")==="1"){
      el.removeAttribute("data-stale");
      renderTab(id);
    } else {
      // Always refresh header controls even on cached tabs
      buildHeaderControls(id);
    }
  }
  // FIX-5: update toggles label — just "#4 Filters" (no tab name)
  var tl=document.getElementById("toggles-label");
  if(tl){tl.textContent="#4 Filters"}
  // Re-apply key rows if KEY is active
  if(keysVisible){
    var kt=el?el.querySelectorAll("table.data-table"):[];
    for(var ki=0;ki<kt.length;ki++)_buildKeyRow(kt[ki]);
  }
};
window.closeChart=function(){
  document.getElementById("chart-panel").classList.remove("open");
  document.body.classList.remove("chart-open");
  var _ccMain=document.querySelector(".main");
  _ccMain.style.marginRight="0";
  _ccMain.style.marginLeft="0";
  document.documentElement.style.setProperty("--chart-panel-w","0px");
};
window.setChartWidth=function(p){
  var pn=document.getElementById("chart-panel");
  pn.style.width=p+"%";
  document.documentElement.style.setProperty("--chart-panel-w",p+"vw");
  var _cwMain=document.querySelector(".main");
  // S41: always right-margin push (chart-from-left is dead post-S41).
  _cwMain.style.marginRight=p+"%";_cwMain.style.marginLeft="0";
  var b=document.querySelectorAll(".chart-width-btn");
  for(var j=0;j<b.length;j++)b[j].classList.remove("active");
  if(event&&event.target)event.target.classList.add("active");
  // Redraw chart at new panel width after transition
  if(chartTicker)setTimeout(function(){drawMasterChart(chartTicker)},350);
};
// FIX-S4-CHART-V2: Faithful port of pullback-monitor.html drawChart
var chartZoom="2Y";
// PHASE-4C 2026-05-04: y-axis scale mode for price panel ("lin" or "log"). Session-only.
var chartScaleMode="lin";
var chartTicker="";
// Default: 5D+10D off (except on PB tab where short MAs matter)
var chartVis={ma5:false,ma10:false,ma20:true,ma50:true,ma100:true,ma150:true,ma200:true,obv:true,vol:true,vol20:true,vol50:true};
// PHASE-4A 2026-05-04: nice-number tick algorithm (Heckbert 1990, {1,2,5} step set per Richard).
function niceNum(range,round){if(range<=0)return 1;var exponent=Math.floor(Math.log10(range));var fraction=range/Math.pow(10,exponent);var nf;if(round){if(fraction<1.5)nf=1;else if(fraction<3.5)nf=2;else if(fraction<7.5)nf=5;else nf=10}else{if(fraction<=1)nf=1;else if(fraction<=2)nf=2;else if(fraction<=5)nf=5;else nf=10}return nf*Math.pow(10,exponent)}
function niceTicks(min,max,maxTicks){if(!isFinite(min)||!isFinite(max)||max<=min)return{ticks:[min],min:min,max:max+1,step:1};var range=niceNum(max-min,false);var step=niceNum(range/(maxTicks-1),true);var nMin=Math.floor(min/step)*step;var nMax=Math.ceil(max/step)*step;var ticks=[];for(var t=nMin;t<=nMax+step/2;t+=step)ticks.push(t);return{ticks:ticks,min:nMin,max:nMax,step:step}}
// PHASE-4A 2026-05-04: B suffix + integer M (15M, not 15.0M).
function fmtVol(v){if(v==null)return"";var a=Math.abs(v);if(a>=1e9)return(v/1e9).toFixed(1)+"B";if(a>=1e6)return Math.round(v/1e6)+"M";if(a>=1e3)return Math.round(v/1e3)+"K";return Math.round(v).toString()}
function getChartSlice(chart,zoom){
  var n=chart.length;
  var days={"1M":Math.min(n,22),"3M":Math.min(n,63),"6M":Math.min(n,125),"12M":Math.min(n,252),"2Y":Math.min(n,504),"3Y":Math.min(n,756),"5Y":Math.min(n,1260)};
  var count=days[zoom]||days["6M"];
  return chart.slice(Math.max(0,n-count));
}
window.toggleChartLayer=function(layer){
  chartVis[layer]=!chartVis[layer];
  drawMasterChart(chartTicker);
  // Update legend opacity
  var el=document.getElementById("legend-"+layer);
  if(el)el.style.opacity=chartVis[layer]?"1":"0.3";
};
// === LAZY CHART LOADER ===
// Chart data lives in charts/<TICKER>.js files (~200KB each).
// Each file self-registers: var CHART_REGISTRY=CHART_REGISTRY||{};CHART_REGISTRY["TICKER"]=[...];
// Data is compact array format: [date, o, h, l, c, v, ma5, ma10, ma20, ma50, ma100, ma150, ma200]
// CHART_REGISTRY is declared at global scope (before IIFE) so eval'd chart files can register into it
var _chartLoading = {};

function _safeTickerFile(t){
  return t.replace(/[.\/]/g,"_");
}

function _expandChartRows(rows){
  // Convert compact [d,o,h,l,c,v,ma5,...,ma200] back to object format
  var maKeys=["ma5","ma10","ma20","ma50","ma100","ma150","ma200"];
  var out=[];
  for(var i=0;i<rows.length;i++){
    var r=rows[i];
    var obj={d:r[0],o:r[1],h:r[2],l:r[3],c:r[4],v:r[5]};
    for(var m=0;m<maKeys.length;m++){
      if(r[6+m]!=null)obj[maKeys[m]]=r[6+m];
    }
    out.push(obj);
  }
  return out;
}

function loadChartData(ticker, callback){
  // SESSION 12 D-MD-CHART-1: pure script-tag injection. XHR+eval path failed silently
  // on GitHub Pages because eval(xhr.responseText) runs in IIFE-local scope, and the
  // chart file's `var CHART_REGISTRY=CHART_REGISTRY||{}` shadows the global registry.
  // Script-tag injection executes at GLOBAL scope and writes to window.CHART_REGISTRY directly.
  // Already loaded?
  if(CHART_REGISTRY[ticker]){
    callback(_expandChartRows(CHART_REGISTRY[ticker]));
    return;
  }
  // Already loading?
  if(_chartLoading[ticker]){
    _chartLoading[ticker].push(callback);
    return;
  }
  _chartLoading[ticker]=[callback];
  var url="charts/"+_safeTickerFile(ticker)+".js";
  var s=document.createElement("script");
  s.src=url;
  s.onload=function(){
    var cbs=_chartLoading[ticker]||[];
    delete _chartLoading[ticker];
    var data=CHART_REGISTRY[ticker]?_expandChartRows(CHART_REGISTRY[ticker]):null;
    for(var i=0;i<cbs.length;i++)cbs[i](data);
  };
  s.onerror=function(){
    var cbs=_chartLoading[ticker]||[];
    delete _chartLoading[ticker];
    for(var i=0;i<cbs.length;i++)cbs[i](null);
  };
  document.head.appendChild(s);
}
// === END LAZY CHART LOADER ===

function drawMasterChart(ticker){
  var canvas=document.getElementById("chart-canvas");
  if(!canvas)return;
  // Use lazy-loaded registry data, fall back to legacy CHART_DATA for compatibility
  var chartAll=null;
  if(CHART_REGISTRY[ticker]){
    chartAll=_expandChartRows(CHART_REGISTRY[ticker]);
  }else if(typeof CHART_DATA!=="undefined"&&CHART_DATA[ticker]){
    chartAll=CHART_DATA[ticker];
  }
  if(!chartAll||chartAll.length===0){
    // Try lazy-loading — show loading message, then redraw on completion
    document.getElementById("chart-container").innerHTML='<div style="text-align:center;padding:40px;color:var(--text-dim)">Loading chart data for '+ticker+'...</div>';
    loadChartData(ticker,function(data){
      if(data&&data.length>0){drawMasterChart(ticker)}
      else{document.getElementById("chart-container").innerHTML='<div style="text-align:center;padding:40px;color:var(--text-dim)">No chart data for '+ticker+'</div>'}
    });
    return;
  }
  var vis=chartVis;
  var chart=getChartSlice(chartAll,chartZoom);
  var fullChart=chartAll;
  // FIX-S4-CHART-V3: Use canvas.getBoundingClientRect for true rendered size
  var dpr=window.devicePixelRatio||1;
  var rect=canvas.getBoundingClientRect();
  var W=Math.round(rect.width);
  var H=Math.max(400,Math.round(window.innerHeight-rect.top-20));
  canvas.style.height=H+"px";
  // Internal resolution = CSS size * DPI
  canvas.width=W*dpr;
  canvas.height=H*dpr;
  var ctx=canvas.getContext("2d");
  ctx.scale(dpr,dpr);
  var pad={t:22,r:68,b:62,l:78};
  var plotW=W-pad.l-pad.r;
  var plotH=H-pad.t-pad.b;
  var n=chart.length;
  // SESSION 12 D-MD-CHART-2: drop barW floor so bars shrink to fit.
  // Old: Math.max(4, plotW/n) — forced 4px min, caused overflow at 2Y zoom on narrow panels.
  var barW=plotW/n;
  var candleW=Math.max(1,barW*0.78);

  var monthFull=["JANUARY","FEBRUARY","MARCH","APRIL","MAY","JUNE","JULY","AUGUST","SEPTEMBER","OCTOBER","NOVEMBER","DECEMBER"];
  var monthShort=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  var dayNames=["Su","Mo","Tu","We","Th","Fr","Sa"];
  var dates=[];
  var i;for(i=0;i<chart.length;i++)dates.push(new Date(chart[i].d+"T00:00:00"));

  // Price range
  var allVals=[];var j,p;
  var maPeriods=[5,10,20,50,100,150,200];
  for(j=0;j<chart.length;j++){
    allVals.push(chart[j].h);allVals.push(chart[j].l);
    for(p=0;p<maPeriods.length;p++){var mk="ma"+maPeriods[p];if(chart[j][mk])allVals.push(chart[j][mk])}
  }
  var priceMin=Math.min.apply(null,allVals)*0.98;
  var priceMax=Math.max.apply(null,allVals)*1.02;
  var priceRange=priceMax-priceMin||1;

  // Volume
  var vols=[];for(j=0;j<chart.length;j++)vols.push(chart[j].v);
  var volMax=Math.max.apply(null,vols)||1;
  var volZoneH=plotH*0.50;

  // Volume MAs (20D + 50D)
  var fullVols=[];for(j=0;j<fullChart.length;j++)fullVols.push(fullChart[j].v);
  var visStart=fullChart.length-n;
  var volMA20=[],volMA50=[];
  for(j=0;j<n;j++){
    var ai=visStart+j;
    var s20=Math.max(0,ai-19);var sl20=fullVols.slice(s20,ai+1);
    volMA20.push(sl20.reduce(function(a,b){return a+b},0)/sl20.length);
    var s50=Math.max(0,ai-49);var sl50=fullVols.slice(s50,ai+1);
    volMA50.push(sl50.reduce(function(a,b){return a+b},0)/sl50.length);
  }
  var avgVol50=volMA50.length>0?volMA50[volMA50.length-1]:volMax*0.5;

  // OBV
  var obv=[0];
  for(j=1;j<chart.length;j++){
    if(chart[j].c>chart[j-1].c)obv.push(obv[j-1]+chart[j].v);
    else if(chart[j].c<chart[j-1].c)obv.push(obv[j-1]-chart[j].v);
    else obv.push(obv[j-1]);
  }
  var obvMin=Math.min.apply(null,obv);var obvMax=Math.max.apply(null,obv);var obvRange=obvMax-obvMin||1;

  // Coordinate functions
  // PHASE-4C 2026-05-04: priceY supports linear and log scales.
  // Log path uses Math.log10; clipped at minimum positive value to avoid log(0).
  function priceY(v){
    if(chartScaleMode==="log"){
      if(!(v>0))return pad.t+plotH;
      var lv=Math.log10(v);
      var lMin=Math.log10(priceMin>0?priceMin:0.01);
      var lMax=Math.log10(priceMax>0?priceMax:1);
      var lRange=lMax-lMin||1;
      return pad.t+plotH*(1-(lv-lMin)/lRange);
    }
    return pad.t+plotH*(1-(v-priceMin)/priceRange);
  }
  function volY(v){return pad.t+plotH-(v/volMax)*volZoneH}
  function volMALineY(v){return pad.t+plotH-(v/volMax)*volZoneH}
  var obvZoneTop=pad.t+plotH*0.75;var obvZoneBot=pad.t+plotH;var obvZoneH2=obvZoneBot-obvZoneTop;
  function obvY(v){return obvZoneBot-((v-obvMin)/obvRange)*obvZoneH2}
  function xPos(i){return pad.l+i*barW+barW/2}

  // Light theme colours
  var bgCol="#ffffff";var gridCol="rgba(180,190,200,0.6)";var gridColMonth="rgba(140,150,160,0.7)";var gridColWeek="rgba(200,210,220,0.5)";
  var textCol="#4a5568";var textColBright="#1f2328";
  var candleUpStroke="#26a641";var candleDnFill="#da3633";var candleDnStroke="#da3633";
  var maColors={5:"#8b0000",10:"#e88a9a",20:"#e74c3c",50:"#ff8c00",100:"#2ca02c",150:"#1a5276",200:"#4a3d9e"};
  var maWidths={200:5,150:3,100:2.5,50:2.2,20:1.8,10:1.5,5:1.5};

  // Clear
  ctx.fillStyle=bgCol;ctx.fillRect(0,0,W,H);

  // PHASE-4A 2026-05-04 + 4C 2026-05-04: nice-number ticks (linear mode) OR log ticks (log mode).
  var priceLo=Math.min.apply(null,allVals);var priceHi=Math.max.apply(null,allVals);
  var priceTickList;
  if(chartScaleMode==='log'){
    // PHASE-4D 2026-05-04: log-tick generation with cascading fallbacks for tight ranges.
    var loSafe=priceLo>0?priceLo:0.01;
    var hiSafe=priceHi>loSafe?priceHi:loSafe*1.1;
    // priceMin/priceMax track the ACTUAL data extents (not snapped to decades),
    // so the chart fills the available height regardless of where ticks land.
    priceMin=loSafe*0.97;priceMax=hiSafe*1.03;priceRange=priceMax-priceMin||1;
    var minExp=Math.floor(Math.log10(loSafe));
    var maxExp=Math.ceil(Math.log10(hiSafe));
    function _logTicks(mults){var out=[];for(var ee=minExp;ee<=maxExp;ee++){var base=Math.pow(10,ee);for(var mi2=0;mi2<mults.length;mi2++){var vv=mults[mi2]*base;if(vv>=priceMin&&vv<=priceMax)out.push(vv)}}return out}
    // Cascade: coarse {1,2,5} -> medium {1,1.5,2,3,5,7} -> dense {1..9}.
    priceTickList=_logTicks([1,2,5]);
    if(priceTickList.length<3)priceTickList=_logTicks([1,1.5,2,3,5,7]);
    if(priceTickList.length<3)priceTickList=_logTicks([1,2,3,4,5,6,7,8,9]);
    // Final fallback: if STILL no ticks (price range smaller than one decade with no integer multipliers),
    // compute linear nice-ticks and use those even in log-render mode. Labels are the priority.
    if(priceTickList.length<2){
      var fbNT=niceTicks(priceLo,priceHi,H>500?9:6);
      priceTickList=fbNT.ticks;
    }
  }else{
    var priceTickTarget=H>500?9:6;
    var priceNT=niceTicks(priceLo,priceHi,priceTickTarget);
    priceMin=priceNT.min;priceMax=priceNT.max;priceRange=priceMax-priceMin||1;
    priceTickList=priceNT.ticks;
  }
  for(var pti=0;pti<priceTickList.length;pti++){
    var ptVal=priceTickList[pti];var ptY=priceY(ptVal);
    if(ptY<pad.t-1||ptY>pad.t+plotH+1)continue;
    ctx.strokeStyle=gridCol;ctx.lineWidth=0.8;
    ctx.beginPath();ctx.moveTo(pad.l,ptY);ctx.lineTo(W-pad.r,ptY);ctx.stroke();
    var ptLabel=ptVal>=1000?Math.round(ptVal).toString():(ptVal<10?ptVal.toFixed(2):ptVal<100?ptVal.toFixed(1):Math.round(ptVal).toString());
    ctx.fillStyle=textCol;ctx.font="13px monospace";ctx.textAlign="left";
    ctx.fillText(ptLabel,W-pad.r+6,ptY+4);
  }

  // PHASE-4B 2026-05-04: tiered x-axis gridlines + labels.
  // Determine tier from n.
  var xt;
  if(n<=25)      xt={major:'week',  label:'D-Mon',  minor:'day',     labelTier:'day'};
  else if(n<=70) xt={major:'month', label:'Mon',    minor:'week',    labelTier:'week'};
  else if(n<=140)xt={major:'month', label:'Mon',    minor:'week',    labelTier:'week'};
  else if(n<=280)xt={major:'quarter',label:'Mon-YY',minor:'month',   labelTier:'month'};
  else if(n<=520)xt={major:'quarter',label:'Mon-YY',minor:'month',   labelTier:'quarter'};
  else if(n<=800)xt={major:'year',  label:'YYYY',   minor:'quarter', labelTier:'quarter'};
  else           xt={major:'year',  label:'YYYY',   minor:'quarter', labelTier:'year'};
  function _isMon(d){return d.getDay()===1}
  function _isMonthStart(d,prev){return !prev||d.getMonth()!==prev.getMonth()}
  function _isQuarterStart(d,prev){return !prev||(d.getMonth()!==prev.getMonth()&&[0,3,6,9].indexOf(d.getMonth())>=0)}
  function _isYearStart(d,prev){return !prev||d.getFullYear()!==prev.getFullYear()}
  function _isMajor(d,prev){if(xt.major==='week')return _isMon(d);if(xt.major==='month')return _isMonthStart(d,prev);if(xt.major==='quarter')return _isQuarterStart(d,prev);return _isYearStart(d,prev)}
  function _isMinor(d,prev){if(xt.minor==='day')return true;if(xt.minor==='week')return _isMon(d);if(xt.minor==='month')return _isMonthStart(d,prev);return _isQuarterStart(d,prev)}
  // Cap minor gridlines at ~30 across plot to avoid noise.
  var minorIdx=[];for(j=1;j<dates.length;j++){if(_isMinor(dates[j],dates[j-1]))minorIdx.push(j)}
  var minorSkip=Math.max(1,Math.ceil(minorIdx.length/30));
  for(var mi=0;mi<minorIdx.length;mi+=minorSkip){var jx=minorIdx[mi];var mxx=xPos(jx);ctx.strokeStyle='rgba(0,0,0,0.04)';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(mxx,pad.t);ctx.lineTo(mxx,pad.t+plotH);ctx.stroke()}
  // Major gridlines drawn on top of minors.
  var majorIdx=[];for(j=1;j<dates.length;j++){if(_isMajor(dates[j],dates[j-1]))majorIdx.push(j)}
  for(var mj=0;mj<majorIdx.length;mj++){var jx2=majorIdx[mj];var mxx2=xPos(jx2);ctx.strokeStyle='rgba(0,0,0,0.10)';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(mxx2,pad.t);ctx.lineTo(mxx2,pad.t+plotH+8);ctx.stroke()}

  // PHASE-4A 2026-05-04: volume axis uses niceTicks too. Volume always anchored at zero.
  var volNT=niceTicks(0,volMax,4);
  var volTickMax=volNT.max;
  // Reassign volMax so the volY/volMALineY closures (declared above) pick up the nice-tick max.
  // This keeps bar heights and tick positions in sync (avoids bars hugging zone top).
  volMax=volTickMax;
  ctx.fillStyle=textCol;ctx.font="12px monospace";ctx.textAlign="right";
  for(var vti=0;vti<volNT.ticks.length;vti++){
    var vVal=volNT.ticks[vti];var vy=volY(vVal);
    if(vy<pad.t+plotH-volZoneH-1||vy>pad.t+plotH+1)continue;
    ctx.fillText(fmtVol(vVal),pad.l-8,vy+4);
  }
  ctx.save();ctx.translate(14,pad.t+plotH-volZoneH/2);ctx.rotate(-Math.PI/2);
  ctx.fillStyle=textCol;ctx.font="12px sans-serif";ctx.textAlign="center";ctx.fillText("Volume",0,0);ctx.restore();

  // Volume bars — 4-colour (up/down x high/low vol)
  if(vis.vol){for(j=0;j<chart.length;j++){
    var vx=xPos(j)-candleW/2;var bh=(chart[j].v/volMax)*volZoneH;
    var upDay=j>0?chart[j].c>=chart[j-1].c:true;var highVol=chart[j].v>=avgVol50;
    if(upDay&&highVol)ctx.fillStyle="rgba(63,185,80,0.50)";
    else if(upDay)ctx.fillStyle="rgba(63,185,80,0.20)";
    else if(highVol)ctx.fillStyle="rgba(248,81,73,0.50)";
    else ctx.fillStyle="rgba(248,81,73,0.20)";
    ctx.fillRect(vx,pad.t+plotH-bh,candleW,bh);
  }}

  // Volume % labels inside bars (when bars wide enough)
  if(barW>16&&vis.vol){ctx.textAlign="center";
    for(j=0;j<chart.length;j++){var x2=xPos(j);var barBottom=pad.t+plotH;
      var pct50v=volMA50[j]>0?Math.round((chart[j].v/volMA50[j]-1)*100):0;
      var pct20v=volMA20[j]>0?Math.round((chart[j].v/volMA20[j]-1)*100):0;
      ctx.fillStyle="#9a6700";ctx.font="9px monospace";ctx.fillText((pct50v>=0?"+":"")+pct50v+"%",x2,barBottom-20);
      ctx.fillStyle="#0969da";ctx.fillText((pct20v>=0?"+":"")+pct20v+"%",x2,barBottom-10);
    }
  }

  // 50D volume MA line
  if(vis.vol50){ctx.strokeStyle="#9a6700";ctx.lineWidth=1.5;ctx.beginPath();
    for(j=0;j<volMA50.length;j++){var vx2=xPos(j),vy2=volMALineY(volMA50[j]);if(j===0)ctx.moveTo(vx2,vy2);else ctx.lineTo(vx2,vy2)}ctx.stroke()}
  // 20D volume MA line
  if(vis.vol20){ctx.strokeStyle="#0969da";ctx.lineWidth=1.5;ctx.beginPath();
    for(j=0;j<volMA20.length;j++){var vx3=xPos(j),vy3=volMALineY(volMA20[j]);if(j===0)ctx.moveTo(vx3,vy3);else ctx.lineTo(vx3,vy3)}ctx.stroke()}

  // OBV line
  if(vis.obv){ctx.strokeStyle="rgba(188,140,255,0.5)";ctx.lineWidth=1.2;ctx.beginPath();
    for(j=0;j<obv.length;j++){var ox=xPos(j),oy=obvY(obv[j]);if(j===0)ctx.moveTo(ox,oy);else ctx.lineTo(ox,oy)}ctx.stroke()}

  // Candlesticks (thicker wicks + bodies)
  for(j=0;j<chart.length;j++){
    var cx2=xPos(j);var upD=chart[j].c>=chart[j].o;
    var bTop=priceY(Math.max(chart[j].o,chart[j].c));var bBot=priceY(Math.min(chart[j].o,chart[j].c));var bH2=Math.max(1,bBot-bTop);
    ctx.strokeStyle=upD?candleUpStroke:candleDnStroke;ctx.lineWidth=1.5;
    ctx.beginPath();ctx.moveTo(cx2,priceY(chart[j].h));ctx.lineTo(cx2,priceY(chart[j].l));ctx.stroke();
    if(upD){ctx.fillStyle=bgCol;ctx.fillRect(cx2-candleW/2,bTop,candleW,bH2);ctx.strokeStyle=candleUpStroke;ctx.lineWidth=1.5;ctx.strokeRect(cx2-candleW/2,bTop,candleW,bH2)}
    else{ctx.fillStyle=candleDnFill;ctx.fillRect(cx2-candleW/2,bTop,candleW,bH2)}
  }

  // MA lines (graduated widths, 100D dashed)
  ctx.textAlign="left";
  for(p=0;p<maPeriods.length;p++){
    var per=maPeriods[p];if(!vis["ma"+per])continue;
    var mk2="ma"+per;ctx.strokeStyle=maColors[per];ctx.lineWidth=maWidths[per];
    ctx.setLineDash(per===100?[6,4]:[]);ctx.beginPath();var started=false;
    for(j=0;j<chart.length;j++){var mv=chart[j][mk2];if(mv){var mx=xPos(j),my=priceY(mv);if(!started){ctx.moveTo(mx,my);started=true}else ctx.lineTo(mx,my)}}
    ctx.stroke();ctx.setLineDash([]);
    var lastMaVal=null;for(j=chart.length-1;j>=0;j--){if(chart[j][mk2]){lastMaVal=chart[j][mk2];break}}
    if(lastMaVal!==null){var ly=priceY(lastMaVal);ctx.fillStyle=maColors[per];ctx.font="bold 12px monospace";ctx.textAlign="left";ctx.fillText(lastMaVal.toFixed(lastMaVal<100?2:1),W-pad.r+6,ly+4)}
  }

  // Current price label (bold, RHS)
  if(chart.length>0){var lastC=chart[chart.length-1].c;var lcy2=priceY(lastC);ctx.fillStyle=textColBright;ctx.font="bold 13px monospace";ctx.textAlign="left";ctx.fillText(lastC.toFixed(lastC<100?2:1),W-pad.r+6,lcy2+4)}

  // PHASE-4B 2026-05-04: single tiered x-axis label row, anchored on major gridlines.
  // Format determined by xt.label.
  function _fmtLabel(d){
    if(xt.label==='D-Mon')return d.getDate()+'-'+monthShort[d.getMonth()];
    if(xt.label==='Mon')return monthShort[d.getMonth()].toUpperCase();
    if(xt.label==='Mon-YY')return monthShort[d.getMonth()].toUpperCase()+'-'+String(d.getFullYear()).slice(-2);
    return String(d.getFullYear());
  }
  ctx.font='bold 12px sans-serif';ctx.fillStyle=textColBright;ctx.textAlign='center';
  // Anti-overlap: estimate per-label pixel width; drop alternating labels until labels fit.
  var sampleW=ctx.measureText(_fmtLabel(dates[majorIdx[0]||0])||'').width||30;
  var safeMin=sampleW+12;
  var lastLX=-9999;
  for(var li=0;li<majorIdx.length;li++){
    var jx3=majorIdx[li];var lxx=xPos(jx3);
    if(lxx-lastLX<safeMin)continue;
    var lblTxt=_fmtLabel(dates[jx3]);
    ctx.fillText(lblTxt,lxx,pad.t+plotH+22);
    lastLX=lxx;
  }
}

// Clickable legend HTML with toggle
function chartLegendHTML(){
  var items=[
    {key:"ma5",label:"MA-5D",color:"#8b0000"},{key:"ma10",label:"MA-10D",color:"#e88a9a"},
    {key:"ma20",label:"MA-20D",color:"#e74c3c"},{key:"ma50",label:"MA-50D",color:"#ff8c00"},
    {key:"ma100",label:"MA-100D",color:"#2ca02c"},{key:"ma150",label:"MA-150D",color:"#1a5276"},
    {key:"ma200",label:"MA-200D",color:"#4a3d9e"},{key:"obv",label:"OBV",color:"#bc8cff"},
    {key:"vol",label:"Volume",color:"rgba(204,180,0,0.6)"},{key:"vol50",label:"Vol 50D MA",color:"#9a6700"},
    {key:"vol20",label:"Vol 20D MA",color:"#0969da"}
  ];
  var h="";
  for(var j=0;j<items.length;j++){
    var it=items[j];var on=chartVis[it.key];
    h+='<span id="legend-'+it.key+'" onclick="toggleChartLayer(\''+it.key+'\')" style="cursor:pointer;opacity:'+(on?"1":"0.3")+';display:inline-flex;align-items:center;gap:2px;padding:1px 4px;border-radius:3px;border:1px solid '+(on?"var(--border)":"transparent")+';user-select:none">';
    h+='<span style="display:inline-block;width:12px;height:2px;background:'+it.color+';border-radius:1px"></span>';
    h+='<span style="font-size:10px;font-weight:600;color:'+it.color+';text-decoration:'+(on?"none":"line-through")+'">'+it.label+'</span></span>';
  }
  return h;
}

window.openChart=function(t){
  var _prevChartTicker=chartTicker;
  chartTicker=t;
  var p=document.getElementById("chart-panel");
  // MD-CHART-V2-WIRING-MARKER: V2 tabs slide the chart panel in from the LEFT; legacy keeps the right.
  var _v2chartTabs={stage_1:1,stage_2:1,stage_3:1,stage_4:1,pre_indicators:1,post_indicators:1,setups_s1pb:1,setups_s2vcp:1,tests:1,setups_healthy_retest:1,tests_probing_bet_s1:1,tests_probing_bet_s2:1,tests_speculative_bet:1,tests_healthy_vcp:1,master_overview:1};  /* MD-V2-S59-TAB-PB-SPLIT-MARKER */
  var _isV2chart=!!_v2chartTabs[currentTab];
  var _isStageChart=/^stage_[1-4]$/.test(currentTab);
  var _wasChartOpen=p.classList.contains("open");
  var _freshChart=(_prevChartTicker!==t)||!_wasChartOpen;
  var _bodyCl=document.body.classList;
  // MD-V2-S41-CHART-RIGHT-FREEZE-COL-MARKER -- V2 tabs no longer slide chart from LEFT; always use default right-slide so the new sticky-first-column on V2 tables keeps company/ticker visible while data cells scroll behind the chart panel.
  if(_bodyCl.contains("chart-from-left")){
    p.style.transition="none";
    _bodyCl.remove("chart-from-left");
    void p.offsetWidth;
    p.style.transition="";
  }
  // Default chart width: 50%
  p.style.width="50%";
  document.documentElement.style.setProperty("--chart-panel-w","50vw");
  p.classList.add("open");
  document.body.classList.add("chart-open");
  var _chartMain=document.querySelector(".main");
  // S41: always push the table to the LEFT with margin-right; chart slides from right on all tabs now.
  _chartMain.style.marginLeft="0";_chartMain.style.marginRight="50%";
  // FIX-S4-CHARTLAYOUT: Compact layout — one row for width+zoom, smaller legend, ticker inline
  // On PB tab, enable 5D+10D MAs by default
  // MD-CHART-V2-WIRING-MARKER: 5D+10D MAs on for PB (legacy) + non-Stage V2 tabs; off elsewhere.
  if(currentTab==="pb"||(_isV2chart&&!_isStageChart)){chartVis.ma5=true;chartVis.ma10=true}else{chartVis.ma5=false;chartVis.ma10=false}
  // Fresh open from a V2 tab resets zoom + the always-on series to the per-tab defaults.
  if(_freshChart&&_isV2chart){
    // MD-V2-CHART-ZOOM-PER-TAB-OVERRIDE-S42-MARKER: per-tab zoom override layered above the two-tier default. 200D break-down on post_indicators; vcp_after_s1_plateau on setups_s1pb; vcp_after_s2_base on setups_s2vcp.
    var _zoomByTabS42={post_indicators:"2Y",setups_s1pb:"3M",setups_s2vcp:"3M",setups_healthy_retest:"6M",stage_3:"6M"};
    chartZoom=_zoomByTabS42[currentTab]||(_isStageChart?"2Y":"6M");
    chartVis.ma20=true;chartVis.ma50=true;chartVis.ma100=true;chartVis.ma150=true;chartVis.ma200=true;
    chartVis.obv=true;chartVis.vol=true;chartVis.vol20=true;chartVis.vol50=true;
  }
  var cont=document.getElementById("chart-container");
  var company="";
  for(var j=0;j<D.universe.length;j++){if(D.universe[j].ticker===t){company=D.universe[j].company_name||"";break}}
  // Row 1: ticker + width toggles + zoom toggles
  var h='<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px;flex-wrap:wrap">';
  h+='<span style="font-size:14px;font-weight:700;color:var(--text-bright)">'+t+'</span>';
  h+='<span style="font-size:12px;color:var(--text-dim)">'+company+'</span>';
  h+='<span style="margin-left:auto;display:flex;gap:2px">';
  var widths=[{p:25,l:"\u00bc"},{p:33,l:"\u2153"},{p:50,l:"\u00bd"},{p:100,l:"Full"}];
  for(var w2=0;w2<widths.length;w2++){
    var wAct=parseInt(p.style.width)===widths[w2].p?" active":"";
    h+='<button class="chart-width-btn'+wAct+'" onclick="setChartWidth('+widths[w2].p+')">'+widths[w2].l+'</button>';
  }
  h+='</span>';
  // PHASE-4C 2026-05-04: LIN/LOG y-axis scale toggle. Own group with 12px gap on each side.
  h+='<span style="display:flex;gap:2px;margin-left:12px;margin-right:12px">';
  var scales=[{k:"lin",l:"LIN"},{k:"log",l:"LOG"}];
  for(var sci=0;sci<scales.length;sci++){
    var sAct=scales[sci].k===chartScaleMode?" active":"";
    h+='<button class="chart-width-btn'+sAct+'" onclick="setChartScaleMode(\''+scales[sci].k+'\')">'+scales[sci].l+'</button>';
  }
  h+='</span>';
  h+='<span style="display:flex;gap:2px">';
  var zooms=["1M","3M","6M","12M","2Y","3Y","5Y"];
  for(var z=0;z<zooms.length;z++){
    var act=zooms[z]===chartZoom?" active":"";
    h+='<button class="chart-width-btn'+act+'" onclick="setChartZoom(\''+zooms[z]+'\')">'+zooms[z]+'</button>';
  }
  h+='</span>';
  h+='<button class="close-btn" onclick="closeChart()" style="margin-left:4px">&times;</button>';
  h+='</div>';
  // Row 2: compact legend (smaller text, single row)
  h+='<div style="display:flex;flex-wrap:wrap;gap:1px;margin-bottom:4px;line-height:1.4">'+chartLegendHTML()+'</div>';
  // Canvas (fills remaining space)
  h+='<div id="chart-canvas-wrap" style="width:100%;position:relative"><canvas id="chart-canvas" style="width:100%;display:block"></canvas></div>';
  cont.innerHTML=h;
  // Pre-load chart data, then draw after CSS transition finishes (300ms)
  loadChartData(t,function(){
    setTimeout(function(){drawMasterChart(t)},350);
  });
};
window.setChartZoom=function(z){
  chartZoom=z;
  if(chartTicker)openChart(chartTicker);
};
// PHASE-4C 2026-05-04: set price-axis scale mode and re-render.
window.setChartScaleMode=function(m){
  if(m!=="lin"&&m!=="log")return;
  chartScaleMode=m;
  if(chartTicker)openChart(chartTicker);
};
// MD-CHART-V2-WIRING-MARKER: V2 tabs - clicking a company/ticker name-cell opens that stock's chart.
// This is the only chart entry point on V2 tabs (the header "Chart" button is hidden there via CSS).
document.addEventListener("click",function(e){
  var _v2ct={stage_1:1,stage_2:1,stage_3:1,stage_4:1,pre_indicators:1,post_indicators:1,setups_s1pb:1,setups_s2vcp:1,tests:1,setups_healthy_retest:1,tests_probing_bet_s1:1,tests_probing_bet_s2:1,tests_speculative_bet:1,tests_healthy_vcp:1,master_overview:1};  /* MD-V2-S59-TAB-PB-SPLIT-MARKER */
  if(!_v2ct[document.body.getAttribute("data-active-tab")])return;
  var _nameCell=e.target.closest("td.name-cell, td.mo-mx-name-cell");
  if(!_nameCell)return;
  var _tkEl=_nameCell.querySelector(".tk, .mo-mx-tk");
  var _tk=_tkEl?(_tkEl.textContent||"").trim():"";
  if(_tk)openChart(_tk);
});

// Key: toggle description rows built from .key-tip content in column headers
var keysVisible=false;
function _buildKeyRow(table){
  var existing=table.querySelector("tr.gen-key-row");
  if(existing)existing.parentNode.removeChild(existing);
  // UTR already has its own permanent key row — skip
  if(table.querySelector("tr.utr-key-row"))return;
  // Skip tables with no key-tip content (e.g. portfolio summary tables)
  if(!table.querySelector("thead .key-tip"))return;
  var colRow=table.querySelector("tr.col-header-row");
  if(!colRow){
    // Fallback: use last row in thead
    var allRows=table.querySelectorAll("thead tr");
    if(allRows.length>0)colRow=allRows[allRows.length-1];
  }
  if(!colRow)return;
  var ths=colRow.querySelectorAll("th");
  var kr=document.createElement("tr");
  kr.className="gen-key-row";
  for(var i=0;i<ths.length;i++){
    var td=document.createElement("td");
    var tip=ths[i].querySelector(".key-tip");
    if(tip&&tip.textContent){
      td.textContent=tip.textContent;
    }
    // Copy col-span from th if present
    var cs=ths[i].getAttribute("colspan");
    if(cs)td.setAttribute("colspan",cs);
    // Copy visibility classes for toggle columns
    td.className=ths[i].className.replace(/\bcol-header\b/g,"");
    kr.appendChild(td);
  }
  var thead=table.querySelector("thead");
  if(thead&&thead.firstChild)thead.insertBefore(kr,thead.firstChild);
  else if(thead)thead.appendChild(kr);
}
function _removeKeyRows(){
  var rows=document.querySelectorAll("tr.gen-key-row");
  for(var j=0;j<rows.length;j++)rows[j].parentNode.removeChild(rows[j]);
}
window.openKey=function(){
  keysVisible=!keysVisible;
  if(keysVisible){
    var tables=document.querySelectorAll("table.data-table");
    for(var j=0;j<tables.length;j++)_buildKeyRow(tables[j]);
  }else{
    _removeKeyRows();
  }
  var btn=document.querySelector("[onclick*='openKey']");
  if(btn){
    if(keysVisible){btn.textContent="Hide Key";btn.classList.add("active")}
    else{btn.textContent="Key";btn.classList.remove("active")}
  }
};
window.closeKey=function(){keysVisible=false;_removeKeyRows()};

window.toggleDisplayMode=function(){var cc=document.querySelectorAll(".tab-content");for(var ci=0;ci<cc.length;ci++)cc[ci].setAttribute("data-stale","1");
  displayMode=(displayMode==="ticker")?"company":"ticker";
  var btn=document.getElementById("btn-display-mode");
  if(btn){
    btn.textContent=(displayMode==="ticker")?"Ticker":"Company";
    if(displayMode==="company")btn.classList.add("active");
    else btn.classList.remove("active");
  }
  var main=document.querySelector(".main");
  if(main){
    if(displayMode==="company")main.classList.add("company-mode");
    else main.classList.remove("company-mode");
  }
  renderTab(currentTab);
};

// FIX-8: Rename "% Thr" to "%"
window.toggleValueMode=function(){var cc=document.querySelectorAll(".tab-content");for(var ci=0;ci<cc.length;ci++)cc[ci].setAttribute("data-stale","1");
  valueMode=(valueMode==="tick")?"pct":"tick";
  var btn=document.getElementById("btn-value-mode");
  if(btn){
    if(valueMode==="tick"){btn.textContent="\u2713\u2717";btn.classList.remove("active")}
    else{btn.textContent="% Distance";btn.classList.add("active")}
  }
  renderTab(currentTab);
};

// FIX-3: Ratings columns toggle
window.toggleRatings=function(){var cc=document.querySelectorAll(".tab-content");for(var ci=0;ci<cc.length;ci++)cc[ci].setAttribute("data-stale","1");
  showRatings=!showRatings;
  var btn=document.getElementById("btn-ratings");
  if(btn){
    if(showRatings){btn.classList.add("active");btn.textContent="Hide case ratings"}
    else{btn.classList.remove("active");btn.textContent="Show case ratings"}
  }
  var main=document.querySelector(".main");
  if(main){
    if(showRatings)main.classList.remove("ratings-hidden");
    else main.classList.add("ratings-hidden");
  }
};

// FIX-S4-JUMPTO: Find element within active tab to avoid duplicate ID conflicts
window.scrollToSection=function(id){
  var tabEl=document.getElementById("tab-"+currentTab);
  var el=tabEl?tabEl.querySelector("#"+id):document.getElementById(id);
  if(!el)el=document.getElementById(id);
  if(el)el.scrollIntoView({behavior:"smooth",block:"start"});
};

window.toggleGroup=function(grp){
  if(activeGroups[grp]){delete activeGroups[grp]}else{activeGroups[grp]=true}
  renderTab(currentTab);
};

function _sigRank(v){return v==="pass"?3:v==="amber"?2:v==="fail"?1:0}
function sortData(data,col,dir){
  return data.slice().sort(function(a,b){
    var av=gnv(a,col),bv=gnv(b,col);
    var an=av===null||av===undefined,bn=bv===null||bv===undefined;
    if(an&&bn)return 0;if(an)return 1;if(bn)return-1;
    // Sort pass/amber/fail signals numerically
    if(av==="pass"||av==="amber"||av==="fail"||bv==="pass"||bv==="amber"||bv==="fail"){av=_sigRank(av);bv=_sigRank(bv);return dir==="asc"?av-bv:bv-av}
    // Sort stage badges: Capital > Late > Early > None
    var stgMap={"Capital":4,"Late":3,"Early":2};if(stgMap[av]||stgMap[bv]){av=stgMap[av]||0;bv=stgMap[bv]||0;return dir==="asc"?av-bv:bv-av}
    if(typeof av==="string")return dir==="asc"?av.localeCompare(bv):bv.localeCompare(av);
    if(typeof av==="boolean"){av=av?1:0;bv=bv?1:0}
    return dir==="asc"?av-bv:bv-av;
  });
}
function gnv(o,p){var k=p.split(".");var v=o;for(var j=0;j<k.length;j++){if(v==null)return null;v=v[k[j]]}return v}
window.handleSort=function(c){
  if(currentSort.col===c)currentSort.dir=currentSort.dir==="asc"?"desc":"asc";
  else{currentSort.col=c;currentSort.dir="desc"}
  renderTab(currentTab);
};

function tick(v){return v?'<span class="tick">&#10003;</span>':'<span class="cross">&#10007;</span>'}
function badge(s){if(!s)return'<span class="badge badge-fail">&mdash;</span>';if(s==="Capital")return'<span class="badge badge-capital">Capital</span>';if(s==="Late")return'<span class="badge badge-late">Late</span>';if(s==="Early")return'<span class="badge badge-early">Early</span>';return'<span class="badge badge-fail">'+s+'</span>'}
// D-MD-UI-18: Navigable badge for TIMELINESS Qualification Screens columns.
// Uses data-nav-tab + data-nav-ticker attributes; event delegation handles click.
function navBadge(stage,ticker,tabId){
  if(!stage)return'<span class="badge badge-fail">&mdash;</span>';
  var cls=stage==="Capital"?"badge-capital":stage==="Late"?"badge-late":stage==="Early"?"badge-early":"badge-fail";
  return'<span class="badge '+cls+' nav-badge" data-nav-tab="'+tabId+'" data-nav-ticker="'+ticker+'" title="Go to '+tabId.toUpperCase()+' tab" style="cursor:pointer">'+stage+'</span>';
}
// D-MD-UI-18: Scroll a ticker row to the top of the visible table on the active tab.
window.scrollToTicker=function(ticker){
  var active=document.querySelector('.tab-content[style*="display: block"], .tab-content[style*="display:block"]');
  if(!active)return;
  var rows=active.querySelectorAll('tr[data-ticker="'+ticker+'"]');
  if(rows.length===0)return;
  var target=rows[rows.length>1?1:0]; // prefer QS row (2nd) over LP row (1st) if both exist
  var hdrH=parseInt(getComputedStyle(document.documentElement).getPropertyValue('--header-height'))||145;
  var y=target.getBoundingClientRect().top+window.pageYOffset-hdrH-4;
  window.scrollTo({top:y,behavior:'smooth'});
  target.style.transition='background 0.3s';target.style.background='rgba(221,107,32,0.18)';
  setTimeout(function(){target.style.background=''},2000);
};
// D-MD-UI-18: Event delegation for nav-badge clicks — switch tab + scroll to ticker.
document.addEventListener('click',function(e){
  var el=e.target.closest('.nav-badge[data-nav-tab]');
  if(!el)return;
  e.stopPropagation(); // prevent row-level openChart
  var tabId=el.getAttribute('data-nav-tab');
  var ticker=el.getAttribute('data-nav-ticker');
  window.scrollTo(0,0);
  switchTab(tabId);
  setTimeout(function(){scrollToTicker(ticker)},150);
});
// D-MD-UI-19: CHANGES tab tile stock names — single-click opens chart (6M), double-click navigates to filter tab.
// Uses timer to distinguish single from double click.
var _chgClickTimer=null;
document.addEventListener('dblclick',function(e){
  var el=e.target.closest('.chg-tile-stock[data-ticker]');
  if(!el)return;
  if(_chgClickTimer){clearTimeout(_chgClickTimer);_chgClickTimer=null}
  var tabId=el.getAttribute('data-tab');
  var ticker=el.getAttribute('data-ticker');
  if(!tabId)return; // placeholder filters (Collapse/S3/S4) have no tab
  window.scrollTo(0,0);
  switchTab(tabId);
  setTimeout(function(){scrollToTicker(ticker)},150);
});
document.addEventListener('click',function(e){
  var el=e.target.closest('.chg-tile-stock[data-ticker]');
  if(!el)return;
  var ticker=el.getAttribute('data-ticker');
  if(_chgClickTimer){clearTimeout(_chgClickTimer);_chgClickTimer=null}
  _chgClickTimer=setTimeout(function(){
    _chgClickTimer=null;
    chartZoom="6M";
    openChart(ticker);
  },250);
});
function scorePips(s,m){var h='<div class="score-bar">';for(var j=0;j<m;j++)h+='<div class="pip '+(j<s?'pip-on':'pip-off')+'"></div>';return h+'</div>'}
// Score pips mapped to individual test results (each pip = one test)
function testPips(tests){var h='<div class="score-bar">';for(var j=0;j<tests.length;j++)h+='<div class="pip '+(tests[j]?'pip-on':'pip-off')+'"></div>';return h+'</div>'}
function monthsPips(hist,count){var h='<div class="score-bar">';for(var j=0;j<hist.length;j++)h+='<div class="pip '+(hist[j]?'pip-on':'pip-off')+'"></div>';return h+' <span style="margin-left:4px;font-weight:600">'+count+'/12</span></div>'}
// BP daily duration strip: 63 daily pass/fail pips (oldest left, latest right)
// + streak (consecutive days currently meeting the test, walking back from today)
// + X/63 fraction. hist: array of bool (oldest first); passed: int; total: int; streak: int.
function bpDaysPips(hist,passed,total,streak){
  if(!hist||hist.length===0)return'<span style="color:#999">&mdash;</span>';
  var h='<div class="bp-days-bar"><div style="display:inline-flex;gap:0">';
  for(var j=0;j<hist.length;j++)h+='<div class="day-pip '+(hist[j]?'day-pip-on':'day-pip-off')+'"></div>';
  h+='</div>';
  h+='<span class="bp-days-frac">'+passed+'/'+total+'</span>';
  var sc=streak>0?"bp-days-streak":"bp-days-streak bp-days-streak-zero";
  h+='<span class="'+sc+'" title="Consecutive days currently meeting the test">'+streak+'d</span>';
  h+='</div>';return h;
}
function signalBar(sigs){var h='<div class="signal-bar">';for(var j=0;j<sigs.length;j++){var c=sigs[j]==="pass"?"seg-pass":sigs[j]==="amber"?"seg-amber":"seg-fail";h+='<div class="seg '+c+'"></div>'}return h+'</div>'}

function addCommas(s){var p=s.split(".");var i=p[0];var d=p.length>1?"."+p[1]:"";var r="";var c=0;for(var j=i.length-1;j>=0;j--){if(c>0&&c%3===0)r=","+r;r=i.charAt(j)+r;c++}return r+d}
function fp(v){
  if(v==null)return"&mdash;";
  var n=Number(v);
  var s;
  if(n>100)s=n.toFixed(0);
  else if(n>20)s=n.toFixed(1);
  else s=n.toFixed(2);
  return addCommas(s);
}
function fpc(v){
  if(v==null)return"&mdash;";
  var n=v*100;
  if(n<0)return"("+Math.abs(n).toFixed(0)+"%)";
  return n.toFixed(0)+"%";
}
// FIX-S4-0DP: All percentages at 0 decimal places
function fpc1(v){
  if(v==null)return"&mdash;";
  var n=v*100;
  if(n<0)return"("+Math.abs(n).toFixed(0)+"%)";
  return n.toFixed(0)+"%";
}
function fpcRaw(v){
  if(v==null)return"&mdash;";
  if(v<0)return"("+Math.abs(v).toFixed(0)+"%)";
  return Number(v).toFixed(0)+"%";
}
function pf(v){if(v==null)return"&mdash;";return fpc(v)}
function nf(v,d){if(v==null)return"&mdash;";return addCommas(Number(v).toFixed(d||0))}
function sa(c){
  if(currentSort.col===c)return'<span class="sort-arrow">'+(currentSort.dir==="asc"?"&#9650;":"&#9660;")+'</span>';
  return'<span class="sort-arrow">&#9650;</span>';
}
function th(l,c,cls,tip,sty){
  var s=currentSort.col===c?" sorted":"";
  var tipHtml=tip?'<span class="key-tip">'+tip+'</span>':"";
  var stAttr=sty?' style="'+sty+'"':"";
  return'<th class="'+(cls||"")+s+'"'+stAttr+' onclick="handleSort(\''+c+'\')">'+l+sa(c)+tipHtml+'</th>';
}

// FIX-16: graduated colour including grey neutral
function gradClass(v){
  if(v==null)return"neutral";
  var pct=v*100;
  if(pct>20)return"grad-green";
  if(pct>5)return"grad-lgreen";
  if(pct>-5)return"grad-neutral";
  if(pct>-20)return"grad-red";
  return"grad-dred";
}
function revClass(v){
  if(v==null)return"neutral";
  if(v>5)return"grad-green";
  if(v>1)return"grad-lgreen";
  if(v>-1)return"grad-neutral";
  if(v>-5)return"grad-red";
  return"grad-dred";
}
function pctileClass(v){
  if(v==null)return"neutral";
  if(v<20)return"grad-green";
  if(v<40)return"grad-lgreen";
  if(v<60)return"grad-neutral";
  if(v<80)return"grad-red";
  return"grad-dred";
}

// P/E range bar SVG
function buildRangeBar(lo,hi,cur){
  if(lo==null||hi==null||cur==null)return"&mdash;";
  if(hi<=lo)return"&mdash;";
  var w=100,ht=24,pad=4;
  var range=hi-lo;
  var median=(lo+hi)/2;
  var pos=pad+((cur-lo)/range)*(w-2*pad);
  if(pos<pad)pos=pad;if(pos>w-pad)pos=w-pad;
  var midX=pad+((median-lo)/range)*(w-2*pad);
  var isGreen=cur<=median;
  var markerColor=isGreen?"#2e7d32":"#c62828";
  var svg='<svg class="range-bar" width="'+w+'" height="'+ht+'" viewBox="0 0 '+w+' '+ht+'" xmlns="http://www.w3.org/2000/svg" style="vertical-align:middle">';
  svg+='<rect x="'+pad+'" y="9" width="'+(midX-pad)+'" height="6" rx="2" fill="#e8f5e9" />';
  svg+='<rect x="'+midX+'" y="9" width="'+(w-pad-midX)+'" height="6" rx="2" fill="#ffebee" />';
  svg+='<line x1="'+pad+'" y1="12" x2="'+(w-pad)+'" y2="12" stroke="#e8e3d4" stroke-width="1" />';
  svg+='<circle cx="'+pos.toFixed(1)+'" cy="12" r="4" fill="'+markerColor+'" />';
  // FIX-S4-MAMAP: Bigger text on range bar too
  svg+='<text x="'+pad+'" y="8" font-size="9" fill="#6b6b6b" font-family="var(--font)">'+nf(lo,1)+'</text>';
  svg+='<text x="'+(w-pad)+'" y="8" font-size="9" fill="#6b6b6b" font-family="var(--font)" text-anchor="end">'+nf(hi,1)+'</text>';
  svg+='<text x="'+pos.toFixed(1)+'" y="22" font-size="9" fill="'+markerColor+'" font-family="var(--font)" text-anchor="middle">'+nf(cur,1)+'</text>';
  svg+='</svg>';
  return svg;
}

// MA Map sparkline for Basing Plateau
// FIX-S4-MARANGE: Renamed MA Map→MA Range. Chart-matching colours. Normalised ±20% scale.
function buildMAMap(price,ma200,ma150,ma50){
  if(price==null)return"&mdash;";
  // Colours match the chart: Price=black, 50D=orange, 150D=navy, 200D=purple
  var vals=[],labels=[],colors=[],fmtVals=[];
  if(price!=null){vals.push(price);labels.push("P");colors.push("#1f2328");fmtVals.push(fp(price))}
  if(ma200!=null){vals.push(ma200);labels.push("200D");colors.push("#4a3d9e");fmtVals.push(fp(ma200))}
  if(ma150!=null){vals.push(ma150);labels.push("150D");colors.push("#1a5276");fmtVals.push(fp(ma150))}
  if(ma50!=null){vals.push(ma50);labels.push("50D");colors.push("#ff8c00");fmtVals.push(fp(ma50))}
  if(vals.length<2)return"&mdash;";
  // Normalised scale: ±20% around the 200D MA (or average if no 200D)
  var anchor=ma200||ma150||price;
  var scaleMin=anchor*0.80;
  var scaleMax=anchor*1.20;
  var range=scaleMax-scaleMin;if(range===0)range=1;
  // viewBox stays large (480) so internal coords have headroom; SVG fills container width.
  var w=480,ht=42,pad=10;
  var mid=20;
  var svg='<svg width="100%" height="'+ht+'" viewBox="0 0 '+w+' '+ht+'" preserveAspectRatio="xMidYMid meet" xmlns="http://www.w3.org/2000/svg" style="vertical-align:middle;display:block">';
  svg+='<line x1="'+pad+'" y1="'+mid+'" x2="'+(w-pad)+'" y2="'+mid+'" stroke="#d4d0c8" stroke-width="1" />';
  var j;
  for(j=0;j<vals.length;j++){
    var x=pad+((vals[j]-scaleMin)/range)*(w-2*pad);
    x=Math.max(pad,Math.min(w-pad,x));
    svg+='<circle cx="'+x.toFixed(1)+'" cy="'+mid+'" r="4" fill="'+colors[j]+'" />';
    svg+='<text x="'+x.toFixed(1)+'" y="'+(mid-8)+'" font-size="10" fill="'+colors[j]+'" font-family="var(--font)" text-anchor="middle" font-weight="600">'+labels[j]+'</text>';
    svg+='<text x="'+x.toFixed(1)+'" y="'+(mid+14)+'" font-size="9" fill="'+colors[j]+'" font-family="var(--font)" text-anchor="middle">'+fmtVals[j]+'</text>';
  }
  svg+='</svg>';
  return svg;
}

// FIX-12: testCell used on ALL tabs with test columns
// FIX-S4-TESTCELL: If no % value available, keep showing tick/cross even in % mode
function testCell(pass,pctVal,cls){
  if(valueMode==="pct"&&pctVal!=null){
    var gc=gradClass(pctVal);
    return'<td class="'+cls+' col-num '+gc+'">'+fpc1(pctVal)+'</td>';
  }
  return'<td class="'+cls+'">'+tick(pass)+'</td>';
}
// Pass A.2: BP-specific 3-tier test cell. Basing test is binary (in/out of ±15% band).
// Magnitude inside the band doesn't matter; magnitude outside only matters as
// "near-miss" vs "clear-miss." 3 tiers: pass (green) / near-miss ±15-20% (amber) / clear-miss (grey).
function bpTestCell(pctVal,passBand){
  if(pctVal==null) return '<td class="col-num col-filter"><span style="color:#999">&mdash;</span></td>';
  var absV = Math.abs(pctVal);
  var bg, fg;
  if(absV <= passBand){
    // Inside band: solid pass green
    bg = 'rgba(46,125,50,0.18)'; fg = '#1b5e20';
  } else if(absV <= passBand + 0.05){
    // Near-miss (within 5pp of pass band)
    bg = 'rgba(245,166,35,0.16)'; fg = '#8d6e00';
  } else {
    // Clear-miss
    bg = 'transparent'; fg = '#888';
  }
  if(valueMode==="pct"){
    return '<td class="col-num col-filter" style="background:'+bg+';color:'+fg+';font-variant-numeric:tabular-nums;font-weight:600">'+fpc1(pctVal)+'</td>';
  }
  // Tick mode: show tick/cross with the same background tint
  var symbol = (absV<=passBand) ? '<span class="tick">&#10003;</span>' : '<span class="cross">&#10007;</span>';
  return '<td class="col-filter" style="background:'+bg+'">'+symbol+'</td>';
}
// Pass A.2: streak length conditional class
function bpStreakColour(streak){
  if(streak >= 60) return {bg:'rgba(27,94,32,0.18)', fg:'#0d3817'};      // mature: dark green
  if(streak >= 30) return {bg:'rgba(46,125,50,0.14)', fg:'#1b5e20'};      // forming: mid green
  if(streak >= 10) return {bg:'rgba(245,166,35,0.14)', fg:'#8d6e00'};     // young: amber
  if(streak > 0)   return {bg:'transparent', fg:'#888'};                  // very young: light grey
  return {bg:'transparent', fg:'#bbb'};                                   // 0d
}
// Pass A.2: %63d conditional class
function bpPctColour(pct){
  if(pct >= 0.95) return {bg:'rgba(27,94,32,0.18)', fg:'#0d3817'};        // qualifies (≥95%)
  if(pct >= 0.80) return {bg:'rgba(46,125,50,0.14)', fg:'#1b5e20'};       // close (80-94%)
  if(pct >= 0.50) return {bg:'rgba(245,166,35,0.14)', fg:'#8d6e00'};      // mid (50-79%)
  return {bg:'transparent', fg:'#888'};                                   // weak (<50%)
}

// UTR: format pct with 0dp, (X)% for negatives, colour-coded
function utrPct(v){
  if(v==null)return'<span class="neutral">&mdash;</span>';
  var n=Number(v);
  var txt=n<0?"("+Math.abs(n).toFixed(0)+"%)":n.toFixed(0)+"%";
  var gc=n<=-15?"grad-dred":n<=-5?"grad-red":n>=-2?"grad-lgreen":n<=5?"grad-neutral":"grad-green";
  return'<span class="'+gc+'">'+txt+'</span>';
}
// UTR: format MA distance with 0dp, (X)% for negatives, colour-coded
function utrMaDist(v){
  if(v==null)return'<span class="neutral">&mdash;</span>';
  var n=Number(v);
  var txt=n<0?"("+Math.abs(n).toFixed(0)+"%)":n.toFixed(0)+"%";
  // Closer to 0 = better (near MA). Negative = broken below
  var gc=n<-3?"grad-dred":n<0?"grad-red":n<=2?"grad-green":n<=5?"grad-lgreen":"grad-neutral";
  return'<span class="'+gc+'">'+txt+'</span>';
}
// UTR: colour-code Test MA cell
function utrTestMa(ma){
  if(!ma)return"&mdash;";
  if(ma==="50D")return'<span class="ma-50d">50D</span>';
  if(ma==="100D")return'<span class="ma-100d">100D</span>';
  if(ma==="150D")return'<span class="ma-150d">150D</span>';
  if(ma==="200D")return'<span class="ma-200d">200D</span>';
  return ma;
}
// UTR signal cell: shows pass/amber/fail or raw numeric value when toggled
function utrSigCell(sig,rawVal,extraCls){
  var cls="col-filter"+(extraCls?" "+extraCls:"");
  if(valueMode==="pct"&&rawVal!=null){
    return'<td class="'+cls+' col-num" style="font-size:10px">'+rawVal+'</td>';
  }
  var sc=sig==="pass"?"pass":sig==="amber"?"amber":sig==="fail"?"fail":"neutral";
  var icon=sig==="pass"?'<span class="tick">&#10003;</span>':sig==="amber"?'<span style="color:var(--amber);font-weight:700">&#9679;</span>':'<span class="cross">&#10007;</span>';
  return'<td class="'+cls+' '+sc+'">'+icon+'</td>';
}

function sumStat(l,v,c){return'<div class="summary-stat"><span class="label">'+l+'</span><span class="value'+(c?" "+c:"")+'">'+v+'</span></div>'}

// FIX-10: X / Y format helper
function xyFmt(x,y){return x+" / "+y}

// Industries + Sectors tables
// FIX-S4-TILESORT: Sort rows within a tile table when column header clicked
window.tileSortTable=function(thEl){
  var table=thEl.closest("table");
  if(!table)return;
  var idx=0;var th2=thEl;while(th2.previousElementSibling){th2=th2.previousElementSibling;idx++}
  var tbody=table.querySelector("tbody");
  if(!tbody)return;
  var rowsArr=Array.prototype.slice.call(tbody.querySelectorAll("tr"));
  var dir=thEl.getAttribute("data-sort-dir")==="asc"?"desc":"asc";
  thEl.setAttribute("data-sort-dir",dir);
  rowsArr.sort(function(a,b){
    var ca=a.children[idx],cb=b.children[idx];
    if(!ca||!cb)return 0;
    var va=ca.textContent.trim(),vb=cb.textContent.trim();
    var na=parseFloat(va.replace(/[^0-9.\-]/g,"")),nb=parseFloat(vb.replace(/[^0-9.\-]/g,""));
    if(!isNaN(na)&&!isNaN(nb))return dir==="asc"?na-nb:nb-na;
    return dir==="asc"?va.localeCompare(vb):vb.localeCompare(va);
  });
  for(var j=0;j<rowsArr.length;j++)tbody.appendChild(rowsArr[j]);
};
function buildIndSecTables(rows,groupDefs){
  var indMap={},secMap={};
  var j,k,t,ind,sec;
  for(j=0;j<CANONICAL_INDUSTRIES.length;j++){
    var ci=CANONICAL_INDUSTRIES[j];
    indMap[ci]={count:0,groups:{}};
    if(groupDefs){
      for(k=0;k<groupDefs.length;k++){
        indMap[ci].groups[groupDefs[k].key]={pass:0,total:0};
      }
    }
  }
  for(j=0;j<rows.length;j++){
    t=getTaxonomy(rows[j].ticker);
    ind=t.industry||"Unknown";sec=t.sector||"Unknown";
    if(!indMap[ind])indMap[ind]={count:0,groups:{}};
    indMap[ind].count++;
    if(!secMap[sec])secMap[sec]={count:0,industry:ind,groups:{}};
    secMap[sec].count++;
    if(groupDefs){
      for(k=0;k<groupDefs.length;k++){
        var gk=groupDefs[k].key;
        if(!indMap[ind].groups[gk])indMap[ind].groups[gk]={pass:0,total:0};
        indMap[ind].groups[gk].total++;
        if(rows[j][gk])indMap[ind].groups[gk].pass++;
        if(!secMap[sec].groups[gk])secMap[sec].groups[gk]={pass:0,total:0};
        secMap[sec].groups[gk].total++;
        if(rows[j][gk])secMap[sec].groups[gk].pass++;
      }
    }
  }
  var indKeys=Object.keys(indMap).filter(function(k){return /^[A-Z]\.\s/.test(k)}).sort();
  var secKeys=Object.keys(secMap).filter(function(k){return /^[A-Z]+\.\d+\.\s/.test(k)}).sort();

  // FIX-10: X / Y in industry/sector counts
  var h='<div class="ind-sec-wrap" id="section-industries">';
  h+='<div class="half-table"><div class="half-title">Industries</div>';
  h+='<div class="data-table-wrap"><table class="data-table data-table-tile"><thead><tr><th class="col-txt" onclick="tileSortTable(this)" style="cursor:pointer">Industry</th><th class="col-num" onclick="tileSortTable(this)" style="cursor:pointer"># Stocks</th>';
  if(groupDefs){for(k=0;k<groupDefs.length;k++)h+='<th class="col-num" onclick="tileSortTable(this)" style="cursor:pointer">'+groupDefs[k].label+'</th>'}
  h+='</tr></thead><tbody>';
  for(j=0;j<indKeys.length;j++){
    var ik=indKeys[j],iv=indMap[ik];
    var indActive=indFilter[ik]?' style="font-size:11px;background:#e8f5e9;font-weight:700"':' style="font-size:11px"';
    h+='<tr onclick="toggleIndFilter(\''+ik.replace(/'/g,"\\'")+'\')" style="cursor:pointer"><td class="col-txt"'+indActive+'>'+ik+'</td><td class="col-num" style="font-weight:600">'+iv.count+'</td>';
    if(groupDefs){
      for(k=0;k<groupDefs.length;k++){
        var gk2=groupDefs[k].key;
        var gd=iv.groups[gk2];
        var passN=gd?gd.pass:0;var totalN=gd?gd.total:0;
        var pcCls=totalN>0?(passN/totalN>0.5?"pass":passN/totalN>0.2?"amber":"fail"):"neutral";
        h+='<td class="col-num '+pcCls+'">'+(iv.count>0?xyFmt(passN,totalN):"&mdash;")+'</td>';
      }
    }
    h+='</tr>';
  }
  h+='</tbody></table></div></div>';

  h+='<div class="half-table" id="section-sectors"><div class="half-title">Sectors</div>';
  h+='<div class="data-table-wrap"><table class="data-table data-table-tile"><thead><tr><th class="col-txt" style="width:35%;cursor:pointer" onclick="tileSortTable(this)">Sector</th><th class="col-txt" style="width:20%;cursor:pointer" onclick="tileSortTable(this)">Industry</th><th class="col-num" style="width:30px;cursor:pointer" onclick="tileSortTable(this)">#</th>';
  if(groupDefs){for(k=0;k<groupDefs.length;k++)h+='<th class="col-num" onclick="tileSortTable(this)" style="cursor:pointer">'+groupDefs[k].label+'</th>'}
  h+='</tr></thead><tbody>';
  for(j=0;j<secKeys.length;j++){
    var sk=secKeys[j],sv=secMap[sk];
    var secActive=secFilter[sk]?' style="font-size:11px;background:#e8f5e9;font-weight:700"':' style="font-size:11px"';
    h+='<tr onclick="toggleSecFilter(\''+sk.replace(/'/g,"\\'")+'\')" style="cursor:pointer"><td class="col-txt"'+secActive+'>'+sk+'</td><td class="col-txt" style="font-size:10px;color:var(--text-dim)">'+sv.industry+'</td><td class="col-num" style="font-weight:600">'+sv.count+'</td>';
    if(groupDefs){
      for(k=0;k<groupDefs.length;k++){
        var gk3=groupDefs[k].key;
        var gd2=sv.groups[gk3];
        var passN2=gd2?gd2.pass:0;var totalN2=gd2?gd2.total:0;
        var pcCls2=totalN2>0?(passN2/totalN2>0.5?"pass":passN2/totalN2>0.2?"amber":"fail"):"neutral";
        h+='<td class="col-num '+pcCls2+'">'+xyFmt(passN2,totalN2)+'</td>';
      }
    }
    h+='</tr>';
  }
  h+='</tbody></table></div></div></div>';
  return h;
}

// Qualification group tiles — same columns as main table, filtered per group
// headersFn: function returning thead HTML (same as main table)
// rowFn: function(r) returning tr HTML (same as main table)
function buildQualTilesV2(rows,groups,totalCount,headersFn,rowFn){
  var h='<div id="section-groups">';
  for(var g=0;g<groups.length;g++){
    var gr=groups[g];
    var passed=[];
    for(var j=0;j<rows.length;j++){if(rows[j][gr.key])passed.push(rows[j])}
    h+='<div class="qual-tile" id="grp-'+gr.key+'">';
    h+='<h4 style="display:flex;gap:16px;align-items:baseline">'+gr.label+' <span style="font-size:12px;font-weight:400;color:var(--text-dim)">'+xyFmt(passed.length,totalCount)+' stocks';
    h+=' &mdash; L12M: <span class="neutral">0</span> &bull; L6M: <span class="neutral">0</span> &bull; L3M: <span class="neutral">0</span> &bull; L1M: <span class="neutral">0</span>';
    h+='</span></h4>';
    if(passed.length===0){
      h+='<p style="color:var(--text-dim);padding:8px 0">No stocks currently meet this criteria.</p>';
    } else {
      h+='<div class="data-table-wrap"><table class="data-table data-table-tile"><thead>'+headersFn()+'</thead><tbody>';
      for(var j2=0;j2<passed.length;j2++)h+=rowFn(passed[j2]);
      h+='</tbody></table></div>';
    }
    h+='</div>';
  }
  h+='</div>';
  return h;
}
// Legacy wrapper (fallback for tabs not yet converted)
function buildQualTiles(rows,groups,totalCount){
  return buildQualTilesV2(rows,groups,totalCount,
    function(){return'<tr>'+commonCols()+'</tr>'},
    function(r){return'<tr>'+commonTds(r)+ratingsColTds(r)+'</tr>'}
  );
}

// ORIG-17: Live portfolio tile — appears above Qualified Stocks on every tab
// Returns set of position tickers for filtering
function getPositionTickers(){
  if(!D.positions||!D.positions.investments)return{};
  var pt={};
  var invs=D.positions.investments;
  for(var j=0;j<invs.length;j++)pt[invs[j].ticker]=true;
  return pt;
}
// Filter enriched rows to positions only
function filterToPositions(rows){
  var pt=getPositionTickers();
  var out=[];
  for(var j=0;j<rows.length;j++){if(pt[rows[j].ticker])out.push(rows[j])}
  return out;
}
// FIX-S4-PORTFOLIO: Generic portfolio tile for tabs without custom portfolio rendering
function buildPortfolioTile(tabId){
  var pt=getPositionTickers();
  var allR=baseRows();
  var posRows=[];
  for(var j=0;j<allR.length;j++){if(pt[allR[j].ticker]&&passIndSecFilter(allR[j]))posRows.push(allR[j])}
  // FIX-INPUTSORT 2026-05-04: generic LP tile rows now respect currentSort like QS rows.
  posRows=sortData(posRows,currentSort.col,currentSort.dir);
  if(posRows.length===0)return"";
  var totalCount=allR.length;
  // SESSION 9 Pass 1.2: D-MD-UI-9 — Live Portfolio columns mirror Qualified Stocks per tab.
  // SESSION 9 Pass 1.2: D-MD-UI-10 — data-table-portfolio class disables sticky thead.
  var h='<h3 class="qualified-title" id="section-portfolio">Live Portfolio ('+posRows.length+')</h3>';
  h+='<div class="data-table-wrap"><table class="data-table data-table-portfolio"><thead><tr>';
  // Tab-aware column structure — TIMELINESS gets full filter columns + grade.
  if(tabId==="combos"){
    // Enrich rows with filter stage data + tm_grade (mirrors renderCombos enrichment).
    for(var je=0;je<posRows.length;je++){
      var rE=posRows[je];
      rE.bp_stage=rE.f.basing_plateau?rE.f.basing_plateau.stage:"";
      rE.pb_stage=rE.f.probing_bet?rE.f.probing_bet.stage:"";
      rE.vcp_stage=rE.f.vcp?rE.f.vcp.stage:"";
      rE.mm_stage=rE.f.mm99?rE.f.mm99.stage:"";
      rE.utr_stage=rE.f.uptrend_retest?rE.f.uptrend_retest.stage:"";
      rE.tm_grade=timeliness(rE);
      rE.tm_key=timelinessSortKey(rE.tm_grade);
    }
    // D-MD-UI-11: Apply grade filter (filters BOTH tables — Q-PG8).
    var posRowsGF=[];
    for(var jg=0;jg<posRows.length;jg++){
      var gKey=posRows[jg].tm_grade==="-"?"N":posRows[jg].tm_grade;
      if(comboGradeFilters[gKey])posRowsGF.push(posRows[jg]);
    }
    posRows=posRowsGF;
    // TIMELINESS-GROUP-HEADER LP (D-MD-UI-17)
    h+='</tr><tr class="group-header-row">';
    h+='<th colspan="10" style="background:rgba(100,100,100,0.06)">Inputs</th>';
    h+='<th colspan="1" style="background:rgba(221,107,32,0.12)">Master</th>';
    h+='<th colspan="8" style="background:rgba(120,80,200,0.08)">Qualification Screens</th>';
    h+=ratingsColHeaders().length>0?'<th colspan="8" class="col-ratings">Ratings</th>':'';
    h+='</tr><tr>';
    h+=commonCols()
      +'<th class="col-txt col-filter">Timeliness</th>'
      +'<th class="col-txt col-filter combo-col-pending">Collapse</th>'
      +'<th class="col-txt col-filter">Basing Plateau</th>'
      +'<th class="col-txt col-filter">Probing Bet</th>'
      +'<th class="col-txt col-filter">VCP</th>'
      +'<th class="col-txt col-filter combo-col-pending">S3 Topping</th>'
      +'<th class="col-txt col-filter combo-col-pending">S4 Declining</th>'
      +'<th class="col-txt col-filter">MM 99</th>'
      +'<th class="col-txt col-filter">Uptrend Retest</th>'
      +ratingsColHeaders();
    h+='</tr></thead><tbody>';
    var pendBadgeLP='<span class="badge badge-fail" title="Pass 2 — pending">&mdash;</span>';
    for(var k=0;k<posRows.length;k++){
      var rk=posRows[k];
      h+='<tr onclick="openChart(\''+rk.ticker+'\')" style="cursor:pointer" data-ticker="'+rk.ticker+'">'+commonTds(rk)
        +'<td class="col-txt col-filter">'+timelinessBadge(rk.tm_grade)+'</td>'
        +'<td class="col-txt col-filter combo-col-pending">'+pendBadgeLP+'</td>'
        +'<td class="col-txt col-filter">'+navBadge(rk.bp_stage,rk.ticker,"bp")+'</td>'
        +'<td class="col-txt col-filter">'+navBadge(rk.pb_stage,rk.ticker,"pb")+'</td>'
        +'<td class="col-txt col-filter">'+navBadge(rk.vcp_stage,rk.ticker,"vcp")+'</td>'
        +'<td class="col-txt col-filter combo-col-pending">'+pendBadgeLP+'</td>'
        +'<td class="col-txt col-filter combo-col-pending">'+pendBadgeLP+'</td>'
        +'<td class="col-txt col-filter">'+navBadge(rk.mm_stage,rk.ticker,"mm99")+'</td>'
        +'<td class="col-txt col-filter">'+navBadge(rk.utr_stage,rk.ticker,"utr")+'</td>'
        +ratingsColTds(rk)+'</tr>';
    }
  } else if(tabId==="ssem"){
    // SESSION 12 D-MD-SSEM-7: LP table mirrors QS table on SSEM tab.
    // Enrich each LP row with SSEM data + score + rating.
    for(var jE=0;jE<posRows.length;jE++){
      var rE=posRows[jE];
      var ss=D.ssem ? D.ssem[rE.ticker] : null;
      if(ss){
        rE.eps_1m=ss.eps_rev?ss.eps_rev.L1M:null;rE.eps_3m=ss.eps_rev?ss.eps_rev.L3M:null;
        rE.eps_6m=ss.eps_rev?ss.eps_rev.L6M:null;rE.eps_12m=ss.eps_rev?ss.eps_rev.L12M:null;
        rE.ebitda_1m=ss.ebitda_rev?ss.ebitda_rev.L1M:null;rE.ebitda_3m=ss.ebitda_rev?ss.ebitda_rev.L3M:null;
        rE.ebitda_6m=ss.ebitda_rev?ss.ebitda_rev.L6M:null;rE.ebitda_12m=ss.ebitda_rev?ss.ebitda_rev.L12M:null;
        rE.sales_1m=ss.sales_rev?ss.sales_rev.L1M:null;rE.sales_3m=ss.sales_rev?ss.sales_rev.L3M:null;
        rE.sales_6m=ss.sales_rev?ss.sales_rev.L6M:null;rE.sales_12m=ss.sales_rev?ss.sales_rev.L12M:null;
        rE.tp_1m=ss.tp_rev?ss.tp_rev.L1M:null;rE.tp_3m=ss.tp_rev?ss.tp_rev.L3M:null;
        rE.tp_6m=ss.tp_rev?ss.tp_rev.L6M:null;rE.tp_12m=ss.tp_rev?ss.tp_rev.L12M:null;
        rE.buy_1m=ss.buy_rev?ss.buy_rev.L1M:null;rE.buy_3m=ss.buy_rev?ss.buy_rev.L3M:null;
        rE.buy_6m=ss.buy_rev?ss.buy_rev.L6M:null;rE.buy_12m=ss.buy_rev?ss.buy_rev.L12M:null;
        rE.buy_pct=ss.buy_pct;
        ssemEnrichRow(rE);
        // Look up rating from the full-universe bell-curve computed in renderSSEM.
        rE.ssem_rating = ssemRatingMap[rE.ticker] || "-";
      } else {
        rE.ssem_score=0; rE.ssem_rating="-"; rE.ssem_nulls=15;
      }
    }
    // Use ssemRowHTML helper (defined inside renderSSEM scope — duplicate inline to keep buildPortfolioTile self-contained)
    h+=ssemHeadersHTML()+'<tbody>';
    for(var jr2=0;jr2<posRows.length;jr2++){
      h+=ssemRowHTML(posRows[jr2]);
    }
  } else {
    // Other tabs: keep existing behaviour (commonCols + ratings).
    h+=commonCols()+ratingsColHeaders()+'</tr></thead><tbody>';
    for(var j=0;j<posRows.length;j++){
      h+='<tr onclick="openChart(\''+posRows[j].ticker+'\')" style="cursor:pointer" data-ticker="'+posRows[j].ticker+'">'+commonTds(posRows[j])+ratingsColTds(posRows[j])+'</tr>';
    }
  }
  h+='</tbody></table></div>';
  return h;
}

// FIX-7: Common columns - 52W High and 52W Low consolidated into single columns each
// FIX-9: alignment classes
// FIX-S4-COLW-V4: table-layout:auto — browser sizes columns by content
function commonCols(){
  var tkrW=displayMode==="company"?"width:140px;max-width:180px":"width:90px";
  return th("Ticker","_display_name","col-txt col-identity","Stock ticker or company name (toggle in header)",tkrW)
    +th("Sector","_tax_sector","col-txt col-identity","Industry sector classification","width:200px;max-width:200px")
    +th("Price","price","col-num col-price","Current stock price","width:52px")
    // FIX-INPUTSORT 2026-05-04: sort keys follow valueMode -- pct mode sorts by displayed % field.
    +th("52WH",valueMode==="pct"?"pct_52wh":"high_52w","col-num col-price","52-week high (toggle to %)","width:52px")
    +th("52WL",valueMode==="pct"?"pct_52wl":"low_52w","col-num col-price","52-week low (toggle to %)","width:52px")
    +th("20D",valueMode==="pct"?"pct_ma20":"_ma20","col-num col-price","20-day moving average","width:46px")
    +th("50D",valueMode==="pct"?"pct_ma50":"_ma50","col-num col-price","50-day moving average","width:46px")
    +th("150D",valueMode==="pct"?"pct_ma150":"_ma150","col-num col-price","150-day moving average","width:46px")
    +th("200D",valueMode==="pct"?"pct_ma200":"_ma200","col-num col-price","200-day moving average","width:46px")
    +th("RS","rs_pct","col-num col-rs","Relative Strength percentile 0-100 (IBD composite)","width:32px");
}
// UTR-specific common cols: Ticker+Sector always visible, rest have col-input class
function utrCommonCols(){
  var tkrW=displayMode==="company"?"width:140px;max-width:180px":"width:90px";
  return th("Ticker","_display_name","col-txt col-identity","Stock ticker or company name",tkrW)
    +th("Sector","_tax_sector","col-txt col-identity col-input","Sector","width:200px;max-width:200px")
    +th("Price","price","col-num col-price col-input","Price","width:52px")
    // FIX-INPUTSORT 2026-05-04: sort keys follow valueMode in UTR common cols too.
    +th("52WH",valueMode==="pct"?"pct_52wh":"high_52w","col-num col-price col-input","52-week high","width:52px")
    +th("52WL",valueMode==="pct"?"pct_52wl":"low_52w","col-num col-price col-input","52-week low","width:52px")
    +th("20D",valueMode==="pct"?"pct_ma20":"_ma20","col-num col-price col-input","20-day MA","width:46px")
    +th("50D",valueMode==="pct"?"pct_ma50":"_ma50","col-num col-price col-input","50-day MA","width:46px")
    +th("150D",valueMode==="pct"?"pct_ma150":"_ma150","col-num col-price col-input","150-day MA","width:46px")
    +th("200D",valueMode==="pct"?"pct_ma200":"_ma200","col-num col-price col-input","200-day MA","width:46px")
    +th("RS","rs_pct","col-num col-rs col-input","RS percentile","width:32px");
}
function utrCommonTds(r){
  var tax=getTaxonomy(r.ticker);
  var dn=(displayMode==="company")?(r.company||r.ticker):r.ticker;
  var rc=r.rs_pct>=70?"var(--green)":r.rs_pct>=40?"var(--text)":"var(--red)";
  var h52val,l52val;
  if(valueMode==="pct"){
    h52val='<td class="col-num col-price col-input '+(r.pct_52wh!=null?gradClass(-r.pct_52wh):"")+'">'+fpc(r.pct_52wh)+'</td>';
    l52val='<td class="col-num col-price col-input '+(r.pct_52wl!=null?gradClass(r.pct_52wl):"")+'">'+fpc(r.pct_52wl)+'</td>';
  } else {
    h52val='<td class="col-num col-price col-input">'+fp(r.high_52w)+'</td>';
    l52val='<td class="col-num col-price col-input">'+fp(r.low_52w)+'</td>';
  }
  var ma20=r.mas?r.mas["20D"]:null;
  var ma50=r.mas?r.mas["50D"]:null;
  var ma150=r.mas?r.mas["150D"]:null;
  var ma200=r.mas?r.mas["200D"]:null;
  return'<td class="col-txt col-identity">'+dn+'</td>'
    +'<td class="col-txt col-identity col-input" title="'+tax.sector+'">'+tax.sector+'</td>'
    +'<td class="col-num col-price col-input">'+fp(r.price)+'</td>'
    +h52val+l52val
    +'<td class="col-num col-price col-input">'+(ma20!=null?fp(ma20):"&mdash;")+'</td>'
    +'<td class="col-num col-price col-input">'+(ma50!=null?fp(ma50):"&mdash;")+'</td>'
    +'<td class="col-num col-price col-input">'+(ma150!=null?fp(ma150):"&mdash;")+'</td>'
    +'<td class="col-num col-price col-input">'+(ma200!=null?fp(ma200):"&mdash;")+'</td>'
    +'<td class="col-num col-rs col-input" style="color:'+rc+'">'+nf(r.rs_pct)+'</td>';
}
function commonTds(r){
  var tax=getTaxonomy(r.ticker);
  var dn=(displayMode==="company")?(r.company||r.ticker):r.ticker;
  var rc=r.rs_pct>=70?"var(--green)":r.rs_pct>=40?"var(--text)":"var(--red)";
  // FIX-7: 52W High shows price in tick mode, % in pct mode. Same for Low.
  var h52val,l52val;
  if(valueMode==="pct"){
    h52val='<td class="col-num col-price '+(r.pct_52wh!=null?gradClass(-r.pct_52wh):"")+'">'+fpc(r.pct_52wh)+'</td>';
    l52val='<td class="col-num col-price '+(r.pct_52wl!=null?gradClass(r.pct_52wl):"")+'">'+fpc(r.pct_52wl)+'</td>';
  } else {
    h52val='<td class="col-num col-price">'+fp(r.high_52w)+'</td>';
    l52val='<td class="col-num col-price">'+fp(r.low_52w)+'</td>';
  }
  var ma20=r.mas?r.mas["20D"]:null;
  var ma50=r.mas?r.mas["50D"]:null;
  var ma150=r.mas?r.mas["150D"]:null;
  var ma200=r.mas?r.mas["200D"]:null;
  // FIX-S4-INPUTPCT: In % mode, MA columns show % distance from MA
  var ma20td,ma50td,ma150td,ma200td;
  if(valueMode==="pct"){
    var p20=ma20?(r.price-ma20)/ma20:null;var p50=ma50?(r.price-ma50)/ma50:null;
    var p150=ma150?(r.price-ma150)/ma150:null;var p200=ma200?(r.price-ma200)/ma200:null;
    ma20td='<td class="col-num col-price '+(p20!=null?gradClass(p20):"")+'">'+fpc(p20)+'</td>';
    ma50td='<td class="col-num col-price '+(p50!=null?gradClass(p50):"")+'">'+fpc(p50)+'</td>';
    ma150td='<td class="col-num col-price '+(p150!=null?gradClass(p150):"")+'">'+fpc(p150)+'</td>';
    ma200td='<td class="col-num col-price '+(p200!=null?gradClass(p200):"")+'">'+fpc(p200)+'</td>';
  } else {
    ma20td='<td class="col-num col-price">'+fp(ma20)+'</td>';
    ma50td='<td class="col-num col-price">'+fp(ma50)+'</td>';
    ma150td='<td class="col-num col-price">'+fp(ma150)+'</td>';
    ma200td='<td class="col-num col-price">'+fp(ma200)+'</td>';
  }
  var mxW=displayMode==="company"?"max-width:180px;overflow:hidden;text-overflow:ellipsis;":"";
  return'<td class="col-txt col-identity" style="font-weight:600;color:var(--text-bright);white-space:nowrap;'+mxW+'" title="'+dn+'">'+dn+'</td>'
    +'<td class="col-txt col-identity" style="font-size:11px;white-space:nowrap;max-width:200px;overflow:hidden;text-overflow:ellipsis" title="'+tax.sector+'">'+tax.sector+'</td>'
    +'<td class="col-num col-price">'+fp(r.price)+'</td>'
    +h52val+l52val
    +ma20td+ma50td+ma150td+ma200td
    +'<td class="col-num col-rs" style="font-weight:600;color:'+rc+'">'+(r.rs_pct!=null?r.rs_pct:"&mdash;")+'</td>';
}

// FIX-3: Ratings columns (A-F pillars, Stage, Thematic Tags) on right side
// FIX-S4-2: Stage moved to far right of ratings group (after Tags) per Richard Message 3
// FIX-S4-QUAL: A-F ratings pulled from qualitative.json (IC Ratings Dashboard memos)
function ratingBadge(rating){
  // SESSION 9 Pass 1.1: full 5-colour A-F ramp matching D-MD-UI-2 palette.
  // +/- modifiers preserved in displayed text but use base-letter colour.
  if(!rating)return'&mdash;';
  var base=rating.replace('+','').replace('-','').replace(' (upper)','').replace(' (lower)','');
  var cls='pill-N';
  if(base==='A')cls='pill-A';
  else if(base==='B')cls='pill-B';
  else if(base==='C')cls='pill-C';
  else if(base==='D')cls='pill-D';
  else if(base==='F')cls='pill-F';
  return'<span class="rating-pill '+cls+'">'+rating+'</span>';
}
function ratingsColHeaders(){
  return'<th class="col-ratings col-txt" title="P1: Technical Strength">P1</th>'
    +'<th class="col-ratings col-txt" title="P2: Market Paradigm">P2</th>'
    +'<th class="col-ratings col-txt" title="P3: Fundamental Change">P3</th>'
    +'<th class="col-ratings col-txt" title="P4: Building Blocks">P4</th>'
    +'<th class="col-ratings col-txt" title="P5: SS Momentum">P5</th>'
    +'<th class="col-ratings col-txt" title="P6: Valuation/Upside">P6</th>'
    +'<th class="col-ratings col-txt">Tags</th>'
    +'<th class="col-ratings col-txt">Stage</th>';
}
function ratingsColTds(r){
  var stg=r.stage||r.bp_stage||r.pb_stage||r.utr_stage||"";
  var q=D.qualitative?D.qualitative[r.ticker]:null;
  if(q){
    return'<td class="col-ratings">'+ratingBadge(q.p1)+'</td>'
      +'<td class="col-ratings">'+ratingBadge(q.p2)+'</td>'
      +'<td class="col-ratings">'+ratingBadge(q.p3)+'</td>'
      +'<td class="col-ratings">'+ratingBadge(q.p4)+'</td>'
      +'<td class="col-ratings">'+ratingBadge(q.p5)+'</td>'
      +'<td class="col-ratings">'+ratingBadge(q.p6)+'</td>'
      +'<td class="col-ratings">&mdash;</td>'
      +'<td class="col-ratings col-txt">'+badge(q.stage||stg)+'</td>';
  }
  return'<td class="col-ratings">&mdash;</td><td class="col-ratings">&mdash;</td><td class="col-ratings">&mdash;</td>'
    +'<td class="col-ratings">&mdash;</td><td class="col-ratings">&mdash;</td><td class="col-ratings">&mdash;</td>'
    +'<td class="col-ratings">&mdash;</td>'
    +'<td class="col-ratings col-txt">'+badge(stg)+'</td>';
}

function baseRows(){
  var rows=[];
  for(var j=0;j<D.prices.length;j++){
    var p=D.prices[j],f=filterMap[p.ticker];
    if(!f)continue;
    var tax=getTaxonomy(p.ticker);
    rows.push({
      ticker:p.ticker,company:p.company_name,
      _display_name:(displayMode==="company")?(p.company_name||p.ticker):p.ticker,
      _tax_industry:tax.industry,_tax_sector:tax.sector,
      sector:p.sector,industry:p.industry,
      price:p.price,price_prev:p.price_prev,
      pct_52wh:p.high_52w>0?((p.high_52w-p.price)/p.high_52w):null,
      pct_52wl:p.low_52w>0?((p.price-p.low_52w)/p.low_52w):null,
      rs_pct:p.rs_percentile,rs_sector:p.rs_vs_sector,
      _ma20:p.mas?p.mas["20D"]:null,_ma50:p.mas?p.mas["50D"]:null,
      _ma150:p.mas?p.mas["150D"]:null,_ma200:p.mas?p.mas["200D"]:null,
      // FIX-INPUTSORT 2026-05-04: project pct_ma fields so sort keys can use them in % mode.
      pct_ma20:(p.mas&&p.mas["20D"])?(p.price-p.mas["20D"])/p.mas["20D"]:null,
      pct_ma50:(p.mas&&p.mas["50D"])?(p.price-p.mas["50D"])/p.mas["50D"]:null,
      pct_ma150:(p.mas&&p.mas["150D"])?(p.price-p.mas["150D"])/p.mas["150D"]:null,
      pct_ma200:(p.mas&&p.mas["200D"])?(p.price-p.mas["200D"])/p.mas["200D"]:null,
      mas:p.mas,high_52w:p.high_52w,low_52w:p.low_52w,
      adv_1m:p.adv_1m,adv_3m:p.adv_3m,
      adv_1m_up:p.adv_1m_up||0,adv_1m_dn:p.adv_1m_dn||0,
      adv_3m_up:p.adv_3m_up||0,adv_3m_dn:p.adv_3m_dn||0,
      f:f
    });
  }
  return rows;
}

// Build header tab controls (score filter + group toggles)
function buildHeaderControls(tabId){
  var el=document.getElementById("header-tab-controls");
  if(!el)return;
  var h="";
  if(tabId==="mm99"){
    h+='<div class="score-filter">';
    // FIX-S4-3: Score filter uses /11 (11 tests: T1-T8 + T9-T11 RS)
    var sc=[0,7,8,9,10,11];
    for(var s=0;s<sc.length;s++){
      var lb=sc[s]===0?"All":(sc[s]+"/11+");
      h+='<button class="score-btn'+(mm99MinScore===sc[s]?" active":"")+'" onclick="setMM99Score('+sc[s]+')">'+lb+'</button>';
    }
    h+='</div>';
    h+='<div class="group-toggles" style="margin-left:12px">';
    var grps=[{k:"ga",l:"Long-term"},{k:"gb",l:"Mid-term"},{k:"gc",l:"Short-term"},{k:"gd",l:"Leadership"},{k:"ge",l:"Relative Strength"}];
    for(var g=0;g<grps.length;g++){
      var act=activeGroups[grps[g].k]?" active":"";
      h+='<button class="group-toggle'+act+'" onclick="toggleGroup(\''+grps[g].k+'\')">'+grps[g].l+'</button>';
    }
    h+='</div>';
  } else if(tabId==="bp"){
    h+='<div class="group-toggles">';
    // Pass A.3 (03-May-26): score-tier toggles GOLD/SILVER/BRONZE/Base/Deep \u2014 match qual tiles + JUMP TO.
    // Toggle key reuses activeGroups (e.g. "_gold") \u2014 renderBP's row-skip logic reads these.
    var bpGrps=[
      {k:"_gold",l:"GOLD (4/4)"},
      {k:"_silver",l:"SILVER (3/4)"},
      {k:"_bronze",l:"BRONZE (2/4)"},
      {k:"_baseonly",l:"Base Only (1/4)"},
      {k:"gc",l:"Deep Base (Tight)"}
    ];
    for(var g2=0;g2<bpGrps.length;g2++){
      var act2=activeGroups[bpGrps[g2].k]?" active":"";
      h+='<button class="group-toggle'+act2+'" onclick="toggleGroup(\''+bpGrps[g2].k+'\')">'+bpGrps[g2].l+'</button>';
    }
    h+='</div>';
  } else if(tabId==="pb"){
    h+='<div class="group-toggles">';
    var pbGrps=[{k:"ga",l:"A: Early (3/5 rising)"},{k:"gb",l:"B: Late (20/50D)"},{k:"gc",l:"C: Dead Cat"},{k:"gd",l:"D: PB1 Capital"},{k:"ge",l:"E: PB2 Capital"}];
    for(var g3=0;g3<pbGrps.length;g3++){
      var act3=activeGroups[pbGrps[g3].k]?" active":"";
      h+='<button class="group-toggle'+act3+'" onclick="toggleGroup(\''+pbGrps[g3].k+'\')">'+pbGrps[g3].l+'</button>';
    }
    h+='</div>';
    // FIX-S4-PBEXCL: Exclude toggles for stocks meeting other filter criteria
    h+='<span style="border-left:1px solid var(--border);height:20px;margin:0 6px"></span>';
    h+='<div class="group-toggles">';
    var exGrps=[{k:"ex_mm99",l:"Exclude MM 99"},{k:"ex_vcp",l:"Exclude VCP"},{k:"ex_utr",l:"Exclude Retest"}];
    for(var e2=0;e2<exGrps.length;e2++){
      var eAct=pbExcludes[exGrps[e2].k]?" active":"";
      h+='<button class="group-toggle'+eAct+'" style="'+(pbExcludes[exGrps[e2].k]?"background:#c62828;border-color:#c62828;color:#fff":"")+'" onclick="togglePbExclude(\''+exGrps[e2].k+'\')">'+exGrps[e2].l+'</button>';
    }
    h+='</div>';
  } else if(tabId==="ssem"){buildSsemHeaderControls();return;
  } else if(tabId==="combos"){
    // SESSION 9: Stage filters + Setup filters. AND'd. All ON default. Sticky.
    h+='<div class="group-toggles">';
    var stages=[{k:"capital",l:"Capital"},{k:"late",l:"Late"},{k:"early",l:"Early"}];
    for(var cs=0;cs<stages.length;cs++){
      var csAct=comboStageFilters[stages[cs].k]?" active":"";
      h+='<button class="group-toggle'+csAct+'" onclick="toggleComboStage(\''+stages[cs].k+'\')">'+stages[cs].l+'</button>';
    }
    h+='</div>';
    h+='<span style="border-left:1px solid var(--border);height:20px;margin:0 6px"></span>';
    h+='<div class="group-toggles">';
    // Pass 1: 5 existing filters. Pass 2 will add Collapse, S3 Topping, S4 Declining buttons.
    var setups=[{k:"bp",l:"BP"},{k:"pb",l:"PB"},{k:"vcp",l:"VCP"},{k:"mm99",l:"MM99"},{k:"utr",l:"UTR"}];
    for(var cf=0;cf<setups.length;cf++){
      var cfAct=comboSetupFilters[setups[cf].k]?" active":"";
      h+='<button class="group-toggle'+cfAct+'" onclick="toggleComboSetup(\''+setups[cf].k+'\')">'+setups[cf].l+'</button>';
    }
    h+='</div>';
    // SESSION 9 Pass 1.2: Grade filter row (D-MD-UI-11).
    h+='<span style="border-left:1px solid var(--border);height:20px;margin:0 6px"></span>';
    h+='<div class="group-toggles">';
    var grades=[{k:"A",l:"A"},{k:"B",l:"B"},{k:"C",l:"C"},{k:"D",l:"D"},{k:"F",l:"F"}];
    for(var gf=0;gf<grades.length;gf++){
      var gfAct=comboGradeFilters[grades[gf].k]?" active":"";
      h+='<button class="group-toggle grade-toggle grade-toggle-'+grades[gf].k+gfAct+'" onclick="toggleComboGrade(\''+grades[gf].k+'\')">'+grades[gf].l+'</button>';
    }
    h+='</div>';
  } else if(tabId==="utr"){
    h+='<div class="group-toggles">';
    var stgBtns=[{k:"early",l:"Early+"},{k:"late",l:"Late+"},{k:"capital",l:"Capital"}];
    for(var sb=0;sb<stgBtns.length;sb++){
      var sAct=utrStageFilter===stgBtns[sb].k?" active":"";
      h+='<button class="group-toggle'+sAct+'" onclick="setUtrStageFilter(\''+stgBtns[sb].k+'\')">'+stgBtns[sb].l+'</button>';
    }
    h+='</div>';
    h+='<span style="border-left:1px solid var(--border);height:20px;margin:0 6px"></span>';
    h+='<div class="group-toggles">';
    var failFilters=[{k:"L1W",l:"Failed Retest (shallow)"},{k:"L1M",l:"Failed Retest (all)"}];
    for(var ff=0;ff<failFilters.length;ff++){
      var fAct=utrFailedFilter===failFilters[ff].k?" active":"";
      h+='<button class="group-toggle'+fAct+'" style="'+(utrFailedFilter===failFilters[ff].k?"background:#c62828;border-color:#c62828;color:#fff":"")+'" onclick="setUtrFailedFilter(\''+failFilters[ff].k+'\')">'+failFilters[ff].l+'</button>';
    }
    h+='</div>';
    h+='<span style="border-left:1px solid var(--border);height:20px;margin:0 6px"></span>';
    h+='<button class="group-toggle'+(utrShowInputs?" active":"")+'" onclick="toggleUtrInputs()">'+(utrShowInputs?"Hide Inputs":"Show Inputs")+'</button>';
  } else if(tabId==="changes"){
    h+='<div class="group-toggles">';
    h+='<button class="group-toggle'+(chgHighestQual?" active":"")+'" onclick="toggleChgHighestQual()">Highest qualification</button>';
    h+='<button class="group-toggle'+(chgSectorGrouping?" active":"")+'" onclick="toggleChgSectorGrouping()">Sector grouping</button>';
    h+='</div>';
  }
  el.innerHTML=h;

  // Populate per-group anchor links
  var gl=document.getElementById("group-links");
  if(gl){
    var gh="";
    var GROUP_LINKS={
      mm99:[{k:"ga",l:"Long-term"},{k:"gb",l:"Mid-term"},{k:"gc",l:"Short-term"},{k:"gd",l:"Leadership"},{k:"ge",l:"Rel. Strength"}],
      bp:[{k:"_gold",l:"GOLD"},{k:"_silver",l:"SILVER"},{k:"_bronze",l:"BRONZE"},{k:"_baseonly",l:"Base Only"},{k:"gc",l:"Deep Base"}],
      utr:[{k:"early",l:"Early+",fn:"setUtrStageFilter"},{k:"late",l:"Late+",fn:"setUtrStageFilter"},{k:"capital",l:"Capital",fn:"setUtrStageFilter"}],
      pb:[{k:"ga",l:"Early"},{k:"gb",l:"Late"},{k:"gc",l:"Dead Cat"},{k:"gd",l:"PB1"},{k:"ge",l:"PB2"}],
      changes:[{k:"section-summarybar",l:"Summary",direct:true},{k:"section-chg-industries",l:"Industries",direct:true},{k:"section-chg-sectors",l:"Sectors",direct:true},{k:"section-summary",l:"Changes",direct:true},{k:"section-stocks",l:"Qualified Stocks",direct:true}]
    };
    var links=GROUP_LINKS[tabId];
    if(links){
      for(var gl2=0;gl2<links.length;gl2++){
        var lk=links[gl2];
        if(lk.direct){
          gh+='<a class="anchor-link" onclick="scrollToSection(\''+lk.k+'\')">'+lk.l+'</a>';
        } else if(lk.fn){
          gh+='<a class="anchor-link" onclick="'+lk.fn+'(\''+lk.k+'\');setTimeout(function(){scrollToSection(\'section-stocks\')},50)">'+lk.l+'</a>';
        } else {
          gh+='<a class="anchor-link" onclick="scrollToSection(\'grp-'+lk.k+'\')">'+lk.l+'</a>';
        }
      }
    }
    gl.innerHTML=gh;
    // Hide default JUMP TO links when tab has its own group links (to prevent overflow)
    var defaultJumps=document.querySelectorAll('.default-jump');
    for(var dj=0;dj<defaultJumps.length;dj++){
      defaultJumps[dj].style.display=links?"none":"";
    }
  }
}

// ================================================================
// MM99 TAB
// ================================================================
function renderMM99(){
  buildHeaderControls("mm99");
  var allRows=baseRows();
  // FIX-7: Enrich ALL rows with MM99 test data first (for Live Portfolio tile)
  for(var j=0;j<allRows.length;j++){
    var r=allRows[j],mm=r.f.mm99;
    if(!mm||!mm.group_a){r.mm99_score=0;r.stage="";r.t1=false;r.t2=false;r.t3=false;r.t4=false;r.t5=false;r.t6=false;r.t7=false;r.t8=false;r.t9=false;r.t10=false;r.t11=false;r.ga=false;r.gb=false;r.gc=false;r.gd=false;r.ge=false;r.pb_stage=r.f.probing_bet?r.f.probing_bet.stage:"";r.bp_stage=r.f.basing_plateau?r.f.basing_plateau.stage:"";r.t1_pct=null;r.t2_pct=null;r.t3_pct=null;r.t4_pct=null;r.t5_pct=null;r.t6_pct=null;r.t7_pct=null;r.t8_pct=null;r.ma200_months=null;r.mm99_monthly=[];r.mm99_months_passing=0;continue;}
    r.mm99_score=mm.score_11;r.stage=mm.stage;
    r.t1=mm.group_a.tests.T1;r.t2=mm.group_a.tests.T2;r.t3=mm.group_b.tests.T3;r.t4=mm.group_b.tests.T4;
    r.t5=mm.group_c.tests.T5;r.t6=mm.group_c.tests.T6;r.t7=mm.group_d.tests.T7;r.t8=mm.group_d.tests.T8;
    r.t9=mm.group_e.tests.T9;r.t10=mm.group_e.tests.T10;r.t11=mm.group_e.tests.T11;
    r.ga=mm.group_a.pass;r.gb=mm.group_b.pass;r.gc=mm.group_c.pass;r.gd=mm.group_d.pass;r.ge=mm.group_e.pass;
    r.pb_stage=r.f.probing_bet?r.f.probing_bet.stage:"";r.bp_stage=r.f.basing_plateau?r.f.basing_plateau.stage:"";

    var m200=r.mas?r.mas["200D"]:null,m150=r.mas?r.mas["150D"]:null,m50=r.mas?r.mas["50D"]:null;
    r.t1_pct=m200?(r.price-m200)/m200:null;
    r.ma200_months=mm.group_a.ma200_months_rising!=null?mm.group_a.ma200_months_rising:null;
    r.t2_pct=null;
    r.t3_pct=m150?(r.price-m150)/m150:null;
    r.t4_pct=(m150&&m200)?(m150-m200)/m200:null;
    r.t5_pct=(m50&&m150)?(m50-m150)/m150:null;
    r.t6_pct=m50?(r.price-m50)/m50:null;
    r.t7_pct=r.low_52w?(r.price-r.low_52w)/r.low_52w:null;
    r.t8_pct=r.high_52w?(r.high_52w-r.price)/r.high_52w:null;
    // BUG-3-FIX: RS pct uses excess return (already decimal, e.g. 0.15 = 15%)
    var rse=mm.group_e;
    r.t9_pct=rse.rs_excess_sector!=null?rse.rs_excess_sector:null;
    r.t10_pct=rse.rs_excess_industry!=null?rse.rs_excess_industry:null;
    r.t11_pct=rse.rs_excess_market!=null?rse.rs_excess_market:null;
    r.mm99_monthly=mm.monthly_history||[];
    r.mm99_months_passing=mm.months_passing!=null?mm.months_passing:0;
  }
  // FIX-7: Now filter into rows by score + group toggles (AFTER enrichment)
  var rows=[];
  for(var j=0;j<allRows.length;j++){
    var r=allRows[j];
    if(r.mm99_score<mm99MinScore)continue;
    var skip=false;
    if(activeGroups.ga&&!r.ga)skip=true;
    if(activeGroups.gb&&!r.gb)skip=true;
    if(activeGroups.gc&&!r.gc)skip=true;
    if(activeGroups.gd&&!r.gd)skip=true;
    if(activeGroups.ge&&!r.ge)skip=true;
    if(skip)continue;
    rows.push(r);
  }
  rows=sortData(rows,currentSort.col,currentSort.dir);
  var totalCount=allRows.length;
  // FIX-S4-3: Summary stats use /11 scoring
  var p11=0,p9=0,cap=0,lat=0,ear=0;
  for(var j=0;j<rows.length;j++){if(rows[j].mm99_score>=11)p11++;if(rows[j].mm99_score>=9)p9++;if(rows[j].stage==="Capital")cap++;if(rows[j].stage==="Late")lat++;if(rows[j].stage==="Early")ear++}

  var h='<div class="summary-tile" id="section-summary"><h3>MM 99 &mdash; Minervini Technical Screen (11 tests)</h3><div class="summary-stats">'
    +sumStat("11/11",xyFmt(p11,rows.length),"green")+sumStat("9/11+",xyFmt(p9,rows.length),"amber")+sumStat("Capital",xyFmt(cap,rows.length),"green")+sumStat("Late",xyFmt(lat,rows.length),"amber")+sumStat("Early",ear)+sumStat("Shown",xyFmt(rows.length,totalCount))
    +'</div></div>';

  var groupDefs=[
    {key:"ga",label:"Long-term"},{key:"gb",label:"Mid-term"},{key:"gc",label:"Short-term"},
    {key:"gd",label:"Leadership"},{key:"ge",label:"Relative Strength"}
  ];
  h+=buildIndSecTables(applyIndSecFilter(allRows),groupDefs);

  // FIX-2: Qualified Stocks title
  // MM99 table rendering function (reused for portfolio tile and main table)
  function mm99Headers(){
    var hdr='<tr class="group-header-row">';
    // FIX-S4-MM99: RS in Inputs group, PB+BP as Setups
    hdr+='<th colspan="2"></th><th colspan="8" style="background:rgba(100,100,100,0.06)">Inputs</th><th colspan="2"></th>';
    hdr+='<th colspan="2" style="background:rgba(200,50,50,0.08)">Long-term</th>';
    hdr+='<th colspan="2" style="background:rgba(200,150,0,0.08)">Mid-term</th>';
    hdr+='<th colspan="2" style="background:rgba(50,150,50,0.08)">Short-term</th>';
    hdr+='<th colspan="2" style="background:rgba(50,100,200,0.08)">52W Leadership</th>';
    hdr+='<th colspan="3" style="background:rgba(120,80,200,0.08)">Relative Strength</th>';
    hdr+='<th colspan="2" style="background:rgba(180,100,50,0.08)">Setups</th>';
    hdr+=ratingsColHeaders().length>0?'<th colspan="8" class="col-ratings">Ratings</th>':"";
    hdr+='</tr><tr class="col-header-row">';
    hdr+=commonCols()+th("Score","mm99_score","col-num col-filter","Minervini 11-test score (8 technical + 3 RS)")
      +th("L12M","mm99_months_passing","col-num col-filter","Months passing all 8 technical tests (last 12 calendar months)")
      +th("P>200D","t1_pct","col-filter grp-lt-first","Price above 200-day MA")+th("200D Up","ma200_months","col-filter grp-lt-last","200-day MA months rising (of 12)")
      +th("P>150D","t3_pct","col-filter grp-mt-first","Price above 150-day MA")+th("150>200","t4_pct","col-filter grp-mt-last","150-day MA above 200-day MA")
      +th("50>150","t5_pct","col-filter grp-st-first","50-day MA above 150-day MA")+th("P>50D","t6_pct","col-filter grp-st-last","Price above 50-day MA")
      +th("P>20%L","t7_pct","col-filter grp-lead-first","Price at least 20% above 52-week low")+th("P<25%H","t8_pct","col-filter grp-lead-last","Price within 25% of 52-week high")
      +th("Sector","t9_pct","col-filter grp-rs-first","Relative strength vs sector")+th("Industry","t10_pct","col-filter","Relative strength vs industry")+th("Market","t11_pct","col-filter grp-rs-last","Relative strength vs market")
      +th("Probing","pb_stage","col-txt col-ref","Probing Bet filter stage")+th("Basing","bp_stage","col-txt col-ref","Basing Plateau filter stage")
      +ratingsColHeaders();
    hdr+='</tr>';
    return hdr;
  }
  function mm99Row(r){
    return'<tr onclick="openChart(\''+r.ticker+'\')" style="cursor:pointer" data-ticker="'+r.ticker+'">'+commonTds(r)
      +'<td class="col-num col-filter">'+testPips([r.t1,r.t2,r.t3,r.t4,r.t5,r.t6,r.t7,r.t8,r.t9,r.t10,r.t11])+' <span style="margin-left:4px;font-weight:600">'+r.mm99_score+'/11</span></td>'
      +'<td class="col-num col-filter">'+monthsPips(r.mm99_monthly,r.mm99_months_passing)+'</td>'
      +testCell(r.t1,r.t1_pct,"col-filter grp-lt-first")+'<td class="col-num col-filter grp-lt-last '+(r.ma200_months>=6?"pass":r.ma200_months>=3?"amber":r.ma200_months>=1?"":"fail")+'">'+(r.ma200_months!=null?r.ma200_months+"/12":"&mdash;")+'</td>'
      +testCell(r.t3,r.t3_pct,"col-filter grp-mt-first")+testCell(r.t4,r.t4_pct,"col-filter grp-mt-last")
      +testCell(r.t5,r.t5_pct,"col-filter grp-st-first")+testCell(r.t6,r.t6_pct,"col-filter grp-st-last")
      +testCell(r.t7,r.t7_pct,"col-filter grp-lead-first")+testCell(r.t8,r.t8_pct,"col-filter grp-lead-last")
      +testCell(r.t9,r.t9_pct,"col-filter grp-rs-first")+testCell(r.t10,r.t10_pct,"col-filter")+testCell(r.t11,r.t11_pct,"col-filter grp-rs-last")
      +'<td class="col-txt col-ref">'+badge(r.pb_stage)+'</td><td class="col-txt col-ref">'+badge(r.bp_stage)+'</td>'
      +ratingsColTds(r)+'</tr>';
  }

  // SESSION 10 — split Live Portfolio + Qualified Stocks into two separate tables, mirroring BP/PB/UTR pattern.
  // Each table has its own <thead> (LP non-sticky via data-table-portfolio class; QS sticky), each gets its own <h3> section heading.
  // FIX-INPUTSORT 2026-05-04: LP rows now respect currentSort like QS rows.
  var posRows=sortData(applyIndSecFilter(filterToPositions(allRows)),currentSort.col,currentSort.dir);
  rows=applyIndSecFilter(rows);
  if(posRows.length>0){
    h+='<h3 class="qualified-title" id="section-portfolio">Live Portfolio ('+posRows.length+')</h3>';
    h+='<div class="data-table-wrap" style="margin-bottom:12px"><table class="data-table data-table-portfolio"><thead>'+mm99Headers()+'</thead><tbody>';
    for(var pj=0;pj<posRows.length;pj++)h+=mm99Row(posRows[pj]);
    h+='</tbody></table></div>';
  }
  h+='<h3 class="qualified-title" id="section-stocks">Qualified Stocks ('+xyFmt(rows.length,totalCount)+')</h3>';
  h+='<div class="data-table-wrap"><table class="data-table"><thead>'+mm99Headers()+'</thead><tbody>';
  for(var j=0;j<rows.length;j++)h+=mm99Row(rows[j]);
  h+='</tbody></table></div>';
  h+=buildQualTilesV2(applyIndSecFilter(allRows),[
    {key:"ga",label:"Long-term Strength"},
    {key:"gb",label:"Mid-term Strength"},
    {key:"gc",label:"Short-term Strength"},
    {key:"gd",label:"52W Leadership"},
    {key:"ge",label:"Relative Strength"}
  ],totalCount,mm99Headers,mm99Row);
  document.getElementById("tab-mm99").innerHTML=h;
}
window.setMM99Score=function(s){mm99MinScore=s;renderTab("mm99")};
window.setUtrMinCap=function(s){utrMinCap=s;renderTab("utr")};
window.setUtrStageFilter=function(s){utrStageFilter=(utrStageFilter===s)?"":s;renderTab("utr")};
window.setUtrFailedFilter=function(f){utrFailedFilter=(utrFailedFilter===f)?"":f;renderTab("utr")};
window.toggleUtrInputs=function(){utrShowInputs=!utrShowInputs;renderTab("utr")};
window.toggleChgSectorGrouping=function(){chgSectorGrouping=!chgSectorGrouping;renderTab("changes")};
window.toggleChgHighestQual=function(){chgHighestQual=!chgHighestQual;renderTab("changes")};

// ================================================================
// BASING PLATEAU TAB \u2014 Pass A simplified (02-May-26)
// Drop Medium UI; rename Loose -> Basing; drop Inputs cols (BP-tab specific
// commonCols variant: Ticker + Sector only); double MA Range sparkline width;
// split Duration into 3 cols (Streak / %63d / Sparkline); keep Tight in
// pipeline but surface as separate "Deep Base" tile only.
// Cross-tab compat: bp.stage still returns Capital/Late/Early/None during
// Pass A (downstream TIMELINESS + Combos tabs unchanged). Pass B replaces
// the stage logic with composite-score mapping (D-MD-FILTER-12).
// ================================================================
function bpCommonCols(){
  // BP-specific: drop the 7 Inputs cols (52WH/52WL/20D/50D/150D/200D/RS).
  // Ticker + Sector + Price only -- MA Range sparkline + tests carry the rest.
  var tkrW=displayMode==="company"?"width:140px;max-width:180px":"width:90px";
  return th("Ticker","_display_name","col-txt col-identity","Stock ticker or company name (toggle in header)",tkrW)
    +th("Sector","_tax_sector","col-txt col-identity","Industry sector classification","width:200px;max-width:200px")
    +th("Price","price","col-num col-price","Current stock price","width:52px");
}
function bpCommonTds(r){
  var tax=getTaxonomy(r.ticker);
  var dn=(displayMode==="company")?(r.company||r.ticker):r.ticker;
  var tkrTd='<td class="col-txt col-identity"';
  if(displayMode==="company"){tkrTd+=' title="'+(r.company||r.ticker).replace(/"/g,"&quot;")+'" style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap"';}
  tkrTd+='>'+dn+'</td>';
  var sec=(tax&&tax.sector)||r.sector||"";
  return tkrTd
    +'<td class="col-txt col-identity" title="'+sec.replace(/"/g,"&quot;")+'" style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'+sec+'</td>'
    +'<td class="col-num col-price">'+fp(r.price)+'</td>';
}
function renderBP(){
  // Pass A.2: default to Pct mode on first BP visit (only). Sticky after — user can toggle off.
  // Pass B: also default-sort by BP Score desc on first BP visit.
  if(bpFirstVisit){
    bpFirstVisit=false;
    if(valueMode==="tick"){
      valueMode="pct";
      var vbtn=document.getElementById("btn-value-mode");
      if(vbtn){vbtn.classList.add("active");vbtn.textContent="% Distance";}
    }
    currentSort={col:"bp_score",dir:"desc"};
  }
  buildHeaderControls("bp");
  var allRows=baseRows();
  var rows=[];
  for(var j=0;j<allRows.length;j++){
    var r=allRows[j],bp=r.f.basing_plateau;
    if(!bp||!bp.group_a){r.bp_stage="";r.ga=false;r.gc=false;r.t1=false;r.t2=false;r.t1_pct=null;r.t2_pct=null;r.bp_score=0;r.bp_flat_pass=false;r.bp_vol_pass=false;r.bp_time_pass=false;r.bp_slope_200=null;r.bp_slope_150=null;r.bp_vol_ratio=null;r.bp_days_since_drop=null;r.bp_loose_hist=[];r.bp_loose_passed=0;r.bp_loose_total=0;r.bp_loose_streak=0;r.bp_loose_pct=0;r.bp_tight_streak=0;r.mm_stage=r.f.mm99?r.f.mm99.stage:"";r.pb_stage2=r.f.probing_bet?r.f.probing_bet.stage:"";r.vcp_s2=r.f.vcp?r.f.vcp.stage_2_uptrend:false;r.utr_stage2=r.f.uptrend_retest?r.f.uptrend_retest.stage:"";r.ssem_rating=(typeof ssemRatingMap!=="undefined"&&ssemRatingMap[r.ticker])?ssemRatingMap[r.ticker]:"-";var nbVl=(typeof D!=="undefined"&&D&&D.valuation)?D.valuation[r.ticker]:null;r.pe_pctile=nbVl?nbVl.pe_percentile:null;r.ma_map_price=r.price;r.ma_map_200=null;r.ma_map_150=null;r.ma_map_50=null;rows.push(r);continue;}
    r.bp_stage=bp.stage;r.ga=bp.group_a.pass;r.gc=bp.group_c.pass;
    r.t1=bp.group_a.tests.T1;r.t2=bp.group_a.tests.T2;
    // Pass B (03-May-26): composite + 3 new tests
    r.bp_score=bp.score!=null?bp.score:0;
    r.bp_flat_pass=bp.flat_mas_pass===true;
    r.bp_vol_pass=bp.vol_contraction_pass===true;
    r.bp_time_pass=bp.time_in_base_pass===true;
    r.bp_slope_200=bp.slope_200;r.bp_slope_150=bp.slope_150;r.bp_vol_ratio=bp.vol_ratio;r.bp_days_since_drop=bp.days_since_drop;
    // Duration history (per Pass-A: only Loose surfaced; Tight retained for Deep Base tile)
    r.bp_loose_hist=bp.group_a.history||[];r.bp_loose_passed=bp.group_a.days_passed||0;r.bp_loose_total=bp.group_a.days_total||0;r.bp_loose_streak=bp.group_a.streak||0;
    r.bp_loose_pct=r.bp_loose_total>0?(r.bp_loose_passed/r.bp_loose_total):0;
    r.bp_tight_streak=bp.group_c.streak||0;
    var m200=r.mas?r.mas["200D"]:null,m150=r.mas?r.mas["150D"]:null,m50=r.mas?r.mas["50D"]:null;
    r.t1_pct=m200?(r.price-m200)/m200:null;
    r.t2_pct=(m50&&m200)?(m50-m200)/m200:null;
    r.mm_stage=r.f.mm99?r.f.mm99.stage:"";r.pb_stage2=r.f.probing_bet?r.f.probing_bet.stage:"";
    // Pass A.1 (03-May-26): cross-filter columns — pull stage info from sibling filters
    r.vcp_s2=r.f.vcp?r.f.vcp.stage_2_uptrend:false;
    r.utr_stage2=r.f.uptrend_retest?r.f.uptrend_retest.stage:"";
    r.ssem_rating=(typeof ssemRatingMap!=="undefined"&&ssemRatingMap[r.ticker])?ssemRatingMap[r.ticker]:"-";
    var bpVl=(typeof D!=="undefined"&&D&&D.valuation)?D.valuation[r.ticker]:null;
    r.pe_pctile=bpVl?bpVl.pe_percentile:null;
    r.ma_map_price=r.price;r.ma_map_200=m200;r.ma_map_150=m150;r.ma_map_50=m50;

    // Pass A.3: filter by score tier (match new GOLD/SILVER/BRONZE/Base Only/Deep Base toggles).
    // Tag tier flags on row first.
    var rsc=r.bp_score!=null?r.bp_score:0;
    r._gold=(rsc===4); r._silver=(rsc===3); r._bronze=(rsc===2); r._baseonly=(rsc===1);
    var anyTierActive=activeGroups._gold||activeGroups._silver||activeGroups._bronze||activeGroups._baseonly||activeGroups.gc;
    if(anyTierActive){
      var keep=false;
      if(activeGroups._gold && r._gold)keep=true;
      if(activeGroups._silver && r._silver)keep=true;
      if(activeGroups._bronze && r._bronze)keep=true;
      if(activeGroups._baseonly && r._baseonly)keep=true;
      if(activeGroups.gc && r.gc)keep=true;
      if(!keep)continue;
    }

    rows.push(r);
  }
  rows=sortData(rows,currentSort.col,currentSort.dir);
  var totalCount=allRows.length;
  // Pass B: count by composite score (4=GOLD/Capital, 3=SILVER/Late, 2=BRONZE/Early, 1=Base-Only, 0=None)
  // Plus separate Deep Base count (Tight pass \u2014 long-horizon monitor, may overlap with above).
  var gold=0,silver=0,bronze=0,baseOnly=0,nada=0,deep=0;
  for(var j=0;j<rows.length;j++){
    var rj=rows[j], scj=rj.bp_score||0;
    if(scj===4)gold++;else if(scj===3)silver++;else if(scj===2)bronze++;else if(scj===1)baseOnly++;else nada++;
    if(rj.gc)deep++;
  }
  var h='<div class="summary-tile" id="section-summary"><h3>Basing Plateau &mdash; Stage 1 Detection Screen</h3>'
    +'<div class="sub">Composite of 4 orthogonal tests: Basing (\u00b115% MA convergence + 3mo duration) + Flat MAs + Volume Contraction + Time-in-Base. 4=GOLD, 3=SILVER, 2=BRONZE.</div>'
    +'<div class="summary-stats">'+sumStat("GOLD (4/4)",xyFmt(gold,rows.length),"green")+sumStat("SILVER (3/4)",xyFmt(silver,rows.length),"amber")+sumStat("BRONZE (2/4)",bronze)+sumStat("Base Only (1/4)",baseOnly)+sumStat("Deep Base (Tight)",deep)+sumStat("Shown",xyFmt(rows.length,totalCount))+'</div></div>';
  var bpGroupDefs=[{key:"ga",label:"Basing (\u00b115%)"},{key:"gc",label:"Deep Base \u2014 Tight (\u00b15%)"}];
  h+=buildIndSecTables(applyIndSecFilter(allRows),bpGroupDefs);

  function bpHeaders(){
    // Pass B (03-May-26): adds 3 new tests + BP Score composite.
    // 3(common) + 1(MA Range) + 1(BP Score) + 1(Basing) + 1(Flat MAs) + 1(Vol) + 1(Time-in-Base)
    //   + 3(Duration: Streak/%63d/Sparkline) + 6(Cross-filter) + 8(ratings) = 26
    var hdr='<tr class="group-header-row"><th colspan="3"></th><th></th>';
    hdr+='<th></th>';  // BP Score column
    hdr+='<th colspan="4" style="background:rgba(50,150,50,0.08)">Stage 1 tests (4 orthogonal)</th>';
    hdr+='<th colspan="3" style="background:rgba(50,100,200,0.06)">Basing duration (last 63 trading days)</th>';
    hdr+='<th colspan="6" style="background:rgba(120,80,160,0.06)">Cross-filter stage</th>';
    hdr+=ratingsColHeaders().length>0?'<th colspan="8" class="col-ratings">Ratings</th>':"";
    hdr+='</tr><tr class="col-header-row">';
    hdr+=bpCommonCols()
      +th("MA Range","ma_map_price","col-filter","Visual: relative positions of Price, 200D, 150D, 50D MAs","width:480px")
      +th("BP Score","bp_score","col-filter","Composite 0-4: Basing + Flat MAs + Vol Contraction + Time-in-Base. 4=Capital, 3=Late, 2=Early. Default sort key.","width:80px")
      +th("Basing","bp_basing_pass","col-filter","Test 1: \u00b115% MA convergence + 3-month duration","width:50px")
      +th("Flat MAs","bp_flat_pass","col-filter","Test 2: 200D slope \u2264\u00b12% AND 150D slope \u2264\u00b14% (annualised). Rules out stocks coasting through MAs in transit.","width:50px")
      +th("Vol Contr","bp_vol_pass","col-filter","Test 3: avg L3M volume / avg L12M volume < 0.90. Minervini accumulation marker.","width:50px")
      +th("Time-in","bp_time_pass","col-filter","Test 4: \u226560 trading days since last 20% drop AND no recent MM99 Capital. Genuine new base.","width:50px")
      +th("Streak","bp_loose_streak","col-filter","Consecutive trading days currently meeting the Basing test. Higher = more mature base.","width:60px")
      +th("%/63d","bp_loose_pct","col-filter","Fraction of last 63 trading days the Basing test passed (95% gate = qualifies).","width:60px")
      +th("Duration","bp_loose_streak","col-filter","Per-day pass/fail visual: 63 bars, oldest left, latest right. Green = test passed that day. Major ticks = months (22d), minor = weeks (5d).","width:140px")
      +th("MM 99","mm_stage","col-txt col-ref","MM99 filter stage","width:48px")
      +th("PB","pb_stage2","col-txt col-ref","Probing Bet filter stage","width:48px")
      +th("VCP","vcp_s2","col-txt col-ref","VCP filter \u2014 Stage 2 uptrend pass","width:42px")
      +th("UTR","utr_stage2","col-txt col-ref","Uptrend Retest filter stage","width:48px")
      +th("SSEM","ssem_rating","col-txt col-ref","SS Earnings Momentum rating (A-F)","width:48px")
      +th("Val","pe_pctile","col-num col-ref","P/E percentile in 10Y range \u2014 lower = cheaper","width:48px")
      +ratingsColHeaders();
    hdr+='</tr>';return hdr;
  }
  function bpRow(r){
    // VCP cell: simple S2 badge or em-dash
    var vcpCell=r.vcp_s2?'<span class="badge badge-capital">S2</span>':'<span class="badge badge-fail">&mdash;</span>';
    // SSEM cell: A-F pill via existing rating-pill classes if present, otherwise em-dash
    var ssemR=r.ssem_rating;
    var ssemCell;
    if(ssemR&&ssemR!=="-"&&ssemR!=="\u2014"){
      ssemCell='<span class="pill-'+ssemR+'" style="padding:2px 6px;border-radius:3px;font-weight:700;font-size:10px">'+ssemR+'</span>';
    } else {ssemCell='<span style="color:#999">&mdash;</span>';}
    // Valuation cell: P/E percentile if present
    var valCell;
    if(r.pe_pctile!=null){
      var pct=Math.round(r.pe_pctile);
      var col=pct<=25?'#1b5e20':pct<=50?'#2e7d32':pct<=75?'#8d6e00':'#c62828';
      valCell='<span style="color:'+col+';font-weight:600;font-variant-numeric:tabular-nums">'+pct+'<span style="font-weight:400;font-size:9px;margin-left:1px">pct</span></span>';
    } else {valCell='<span style="color:#999">&mdash;</span>';}
    // Pass A.2: 3-tier basing test cells, conditional streak + %63d colouring
    var sCol = bpStreakColour(r.bp_loose_streak||0);
    var pCol = bpPctColour(r.bp_loose_pct||0);
    var streakHtml = r.bp_loose_streak>0
      ? '<td class="col-num col-filter" style="background:'+sCol.bg+';color:'+sCol.fg+';font-weight:600;font-variant-numeric:tabular-nums">'+r.bp_loose_streak+'d</td>'
      : '<td class="col-num col-filter" style="color:#bbb">0d</td>';
    var pctHtml = r.bp_loose_total>0
      ? '<td class="col-num col-filter" style="background:'+pCol.bg+';color:'+pCol.fg+';font-variant-numeric:tabular-nums">'+Math.round(r.bp_loose_pct*100)+'%</td>'
      : '<td class="col-num col-filter">&mdash;</td>';
    // Pass B: BP Score + 4 individual test cells. Pass A.3: pct-mode shows underlying numeric.
    var sc = r.bp_score!=null ? r.bp_score : 0;
    var scoreHtml = '<td class="col-filter">'+scorePips(sc, 4)+' <span style="margin-left:4px;font-weight:600;font-variant-numeric:tabular-nums">'+sc+'/4</span></td>';
    var basingPass = r.ga===true;
    var flatPass = r.bp_flat_pass===true;
    var volPass = r.bp_vol_pass===true;
    var timePass = r.bp_time_pass===true;
    // pctCell: tick mode shows tick/cross; pct mode shows numeric with pass-tinted background.
    function pctCell(passFlag, numericText){
      if(valueMode==="pct" && numericText){
        var bg = passFlag ? 'rgba(46,125,50,0.18)' : 'transparent';
        var fg = passFlag ? '#1b5e20' : '#888';
        return '<td class="col-num col-filter" style="background:'+bg+';color:'+fg+';font-variant-numeric:tabular-nums;font-weight:600">'+numericText+'</td>';
      }
      return passFlag
        ? '<td class="col-filter" style="text-align:center"><span class="tick">&#10003;</span></td>'
        : '<td class="col-filter" style="text-align:center"><span class="cross">&#10007;</span></td>';
    }
    // Numerics for pct mode
    var basingNum = (r.t1_pct!=null) ? fpc1(r.t1_pct) : null;  // Price ~ 200D %
    var flatNum = (r.bp_slope_200!=null) ? fpc1(r.bp_slope_200) : null;  // 200D slope annualised
    var volNum = (r.bp_vol_ratio!=null) ? Math.round(r.bp_vol_ratio*100)+'%' : null;  // L3M/L12M ratio
    var timeNum = (r.bp_days_since_drop!=null) ? r.bp_days_since_drop+'d' : null;  // days since 20% drop
    return'<tr onclick="openChart(\''+r.ticker+'\')" style="cursor:pointer" data-ticker="'+r.ticker+'">'+bpCommonTds(r)
      +'<td class="col-filter">'+buildMAMap(r.ma_map_price,r.ma_map_200,r.ma_map_150,r.ma_map_50)+'</td>'
      +scoreHtml
      +pctCell(basingPass, basingNum)+pctCell(flatPass, flatNum)+pctCell(volPass, volNum)+pctCell(timePass, timeNum)
      +streakHtml
      +pctHtml
      +'<td class="col-filter">'+bpDaysPipsCompact(r.bp_loose_hist)+'</td>'
      +'<td class="col-txt col-ref">'+badge(r.mm_stage)+'</td>'
      +'<td class="col-txt col-ref">'+badge(r.pb_stage2)+'</td>'
      +'<td class="col-txt col-ref">'+vcpCell+'</td>'
      +'<td class="col-txt col-ref">'+badge(r.utr_stage2)+'</td>'
      +'<td class="col-txt col-ref">'+ssemCell+'</td>'
      +'<td class="col-num col-ref">'+valCell+'</td>'
      +ratingsColTds(r)+'</tr>';
  }
  // FIX-INPUTSORT 2026-05-04: LP rows now respect currentSort like QS rows.
  var posRowsBP=sortData(applyIndSecFilter(filterToPositions(allRows)),currentSort.col,currentSort.dir);
  // Enrich position rows with BP data (they may not have been enriched if filtered out)
  for(var pk=0;pk<posRowsBP.length;pk++){var pr=posRowsBP[pk];if(pr.bp_stage===undefined){var bpd=pr.f.basing_plateau;if(!bpd||!bpd.group_a){pr.bp_stage="";pr.ga=false;pr.gc=false;pr.t1=false;pr.t2=false;pr.bp_score=0;pr.bp_flat_pass=false;pr.bp_vol_pass=false;pr.bp_time_pass=false;pr.bp_loose_hist=[];pr.bp_loose_passed=0;pr.bp_loose_total=0;pr.bp_loose_streak=0;pr.bp_loose_pct=0;pr.bp_tight_streak=0;}else{pr.bp_stage=bpd.stage;pr.ga=bpd.group_a.pass;pr.gc=bpd.group_c.pass;pr.t1=bpd.group_a.tests.T1;pr.t2=bpd.group_a.tests.T2;pr.bp_score=bpd.score!=null?bpd.score:0;pr.bp_flat_pass=bpd.flat_mas_pass===true;pr.bp_vol_pass=bpd.vol_contraction_pass===true;pr.bp_time_pass=bpd.time_in_base_pass===true;pr.bp_loose_hist=bpd.group_a.history||[];pr.bp_loose_passed=bpd.group_a.days_passed||0;pr.bp_loose_total=bpd.group_a.days_total||0;pr.bp_loose_streak=bpd.group_a.streak||0;pr.bp_loose_pct=pr.bp_loose_total>0?(pr.bp_loose_passed/pr.bp_loose_total):0;pr.bp_tight_streak=bpd.group_c.streak||0;}var m200b=pr.mas?pr.mas["200D"]:null,m150b=pr.mas?pr.mas["150D"]:null,m50b=pr.mas?pr.mas["50D"]:null;pr.t1_pct=m200b?(pr.price-m200b)/m200b:null;pr.t2_pct=(m50b&&m200b)?(m50b-m200b)/m200b:null;pr.mm_stage=pr.f.mm99?pr.f.mm99.stage:"";pr.pb_stage2=pr.f.probing_bet?pr.f.probing_bet.stage:"";pr.vcp_s2=pr.f.vcp?pr.f.vcp.stage_2_uptrend:false;pr.utr_stage2=pr.f.uptrend_retest?pr.f.uptrend_retest.stage:"";pr.ssem_rating=(typeof ssemRatingMap!=="undefined"&&ssemRatingMap[pr.ticker])?ssemRatingMap[pr.ticker]:"-";var prVl=(typeof D!=="undefined"&&D&&D.valuation)?D.valuation[pr.ticker]:null;pr.pe_pctile=prVl?prVl.pe_percentile:null;pr.ma_map_price=pr.price;pr.ma_map_200=m200b;pr.ma_map_150=m150b;pr.ma_map_50=m50b;}}
  if(posRowsBP.length>0){
    h+='<h3 class="qualified-title" id="section-portfolio">Live Portfolio ('+posRowsBP.length+')</h3>';
    h+='<div class="data-table-wrap" style="margin-bottom:12px"><table class="data-table data-table-portfolio"><thead>'+bpHeaders()+'</thead><tbody>';
    for(var pj=0;pj<posRowsBP.length;pj++)h+=bpRow(posRowsBP[pj]);
    h+='</tbody></table></div>';
  }
  rows=applyIndSecFilter(rows);
  h+='<h3 class="qualified-title" id="section-stocks">Qualified Stocks ('+xyFmt(rows.length,totalCount)+')</h3>';
  h+='<div class="data-table-wrap"><table class="data-table"><thead>'+bpHeaders()+'</thead><tbody>';
  for(var j=0;j<rows.length;j++)h+=bpRow(rows[j]);
  h+='</tbody></table></div>';
  // Pass B: tag tier-flags onto allRows for qualification tiles (GOLD/SILVER/BRONZE/Base-Only/Deep)
  var allWithTier=applyIndSecFilter(allRows);
  for(var ti=0;ti<allWithTier.length;ti++){
    var tr=allWithTier[ti], tsc=tr.bp_score!=null?tr.bp_score:0;
    tr._gold=(tsc===4);tr._silver=(tsc===3);tr._bronze=(tsc===2);tr._baseonly=(tsc===1);
    // _deep already covered by tr.gc (Tight test pass)
  }
  h+=buildQualTilesV2(allWithTier,[
    {key:"_gold",label:"GOLD (4/4) \u2014 all 4 Stage 1 tests pass"},
    {key:"_silver",label:"SILVER (3/4) \u2014 3 of 4 tests pass"},
    {key:"_bronze",label:"BRONZE (2/4) \u2014 2 of 4 tests pass"},
    {key:"_baseonly",label:"Base Only (1/4) \u2014 Basing test only, reference"},
    {key:"gc",label:"Deep Base (\u00b15%) \u2014 Tight, long-horizon monitor"}
  ],totalCount,bpHeaders,bpRow);
  document.getElementById("tab-bp").innerHTML=h;
}
// Compact 63-bar duration sparkline with month + week ticks.
// Layout: stacked container \u2014 strip (11px) on top, ticks (5px) below.
// Major ticks (months) every 22 trading days; minor (weeks) every 5 days.
// Bars are 2px wide -> total strip width = 63*2 = 126px (matches CSS).
function bpDaysPipsCompact(hist){
  if(!hist||hist.length===0)return'<span style="color:#999">&mdash;</span>';
  var n=hist.length, pipW=2, totalW=n*pipW;
  var h='<div style="display:inline-block;line-height:1;vertical-align:middle">';
  // Strip
  h+='<div class="bp-days-bar" style="display:flex;gap:0;width:'+totalW+'px">';
  for(var j=0;j<n;j++)h+='<div class="day-pip '+(hist[j]?'day-pip-on':'day-pip-off')+'"></div>';
  h+='</div>';
  // Tick row \u2014 SVG underneath the strip
  h+='<svg width="'+totalW+'" height="6" style="display:block;margin-top:1px" xmlns="http://www.w3.org/2000/svg">';
  // Minor ticks every 5 days (weeks)
  for(var w=5;w<n;w+=5){
    var x=w*pipW;
    h+='<line x1="'+x+'" y1="0" x2="'+x+'" y2="2" stroke="#bcb7a6" stroke-width="1"/>';
  }
  // Major ticks every 22 days (months)
  for(var m=22;m<n;m+=22){
    var xm=m*pipW;
    h+='<line x1="'+xm+'" y1="0" x2="'+xm+'" y2="5" stroke="#7d756a" stroke-width="1"/>';
  }
  // "today" marker on the right edge
  h+='<line x1="'+(totalW-1)+'" y1="0" x2="'+(totalW-1)+'" y2="5" stroke="#1f2328" stroke-width="1"/>';
  h+='</svg>';
  h+='</div>';
  return h;
}

// ================================================================
// PROBING BET TAB
// FIX-12: testCell applied to PB test columns
// ================================================================
function renderPB(){
  buildHeaderControls("pb");
  var allRows=baseRows();
  var rows=[];
  for(var j=0;j<allRows.length;j++){
    var r=allRows[j],pb=r.f.probing_bet;
    if(!pb||!pb.group_a){r.pb_stage="";r.ga=false;r.a_met=0;r.gb=false;r.b_met=0;r.gc=false;r.dead_cat=false;r.pct_below=null;r.gd=false;r.ge=false;r.t1=false;r.t2=false;r.t3=false;r.t4=false;r.t5=false;r.t6=false;r.t7=false;r.t8=false;r.t9=false;r.t10=false;r.t11=false;r.t12=false;r.t1_pct=null;r.t2_pct=null;r.t3_pct=null;r.t4_pct=null;r.t5_pct=null;r.t6_pct=null;r.t7_pct=null;r.t8_pct=null;r.t9_pct=null;r.t10_pct=null;r.t11_pct=null;r.t12_pct=null;r.mm_stage=r.f.mm99?r.f.mm99.stage:"";r.bp_stage2=r.f.basing_plateau?r.f.basing_plateau.stage:"";r.utr_stage2=r.f.uptrend_retest?r.f.uptrend_retest.stage:"";r.vcp_s2=r.f.vcp?r.f.vcp.stage_2_uptrend:false;rows.push(r);continue;}
    r.pb_stage=pb.stage;
    r.ga=pb.group_a.pass;r.a_met=pb.group_a.met;
    r.gb=pb.group_b.pass;r.b_met=pb.group_b.met;
    r.gc=pb.group_c.pass;r.dead_cat=pb.group_c.tests.T8;r.pct_below=pb.group_c.pct_below_52wh;
    r.gd=pb.group_d.pass;r.ge=pb.group_e.pass;
    r.t1=pb.group_a.tests.T1;r.t2=pb.group_a.tests.T2;r.t3=pb.group_a.tests.T3;r.t4=pb.group_a.tests.T4;r.t5=pb.group_a.tests.T5;
    r.t6=pb.group_b.tests.T6;r.t7=pb.group_b.tests.T7;
    r.t8=pb.group_c.tests.T8;
    r.t9=pb.group_d.tests.T9;r.t10=pb.group_d.tests.T10;
    r.t11=pb.group_e.tests.T11;r.t12=pb.group_e.tests.T12;
    // pct values for PB (approximate)
    r.t1_pct=null;r.t2_pct=null;r.t3_pct=null;r.t4_pct=null;r.t5_pct=null;
    r.t6_pct=null;r.t7_pct=null;r.t8_pct=null;
    r.t9_pct=null;r.t10_pct=null;r.t11_pct=null;r.t12_pct=null;
    r.mm_stage=r.f.mm99?r.f.mm99.stage:"";r.bp_stage2=r.f.basing_plateau?r.f.basing_plateau.stage:"";
    r.utr_stage2=r.f.uptrend_retest?r.f.uptrend_retest.stage:"";r.vcp_s2=r.f.vcp?r.f.vcp.stage_2_uptrend:false;

    var skip=false;
    if(activeGroups.ga&&!r.ga)skip=true;
    if(activeGroups.gb&&!r.gb)skip=true;
    if(activeGroups.gc&&!r.gc)skip=true;
    if(activeGroups.gd&&!r.gd)skip=true;
    if(activeGroups.ge&&!r.ge)skip=true;
    // FIX-S4-PBEXCL: Exclude stocks meeting other filter criteria
    if(pbExcludes.ex_mm99&&(r.mm_stage==="Capital"||r.mm_stage==="Late"))skip=true;
    if(pbExcludes.ex_vcp&&r.vcp_s2)skip=true;
    if(pbExcludes.ex_utr&&(r.utr_stage2==="Capital"||r.utr_stage2==="Late"))skip=true;
    if(skip)continue;

    rows.push(r);
  }
  rows=sortData(rows,currentSort.col,currentSort.dir);
  var totalCount=allRows.length;
  var cap=0,lat=0,ear=0,dc=0;
  for(var j=0;j<rows.length;j++){var s=rows[j].pb_stage;if(s==="Capital")cap++;else if(s==="Late")lat++;else if(s==="Early")ear++;if(rows[j].dead_cat)dc++}
  var h='<div class="summary-tile" id="section-summary"><h3>Probing Bet &mdash; Entry Setup Screen</h3>'
    +'<div class="sub">A=Early (3/5 rising) | B=Late (20D/50D rising) | C=Dead Cat (&ge;30% below 52WH) | D=PB1 Capital (P&gt;20D+rising) | E=PB2 Capital (P&gt;50D+rising)</div>'
    +'<div class="summary-stats">'+sumStat("Capital",xyFmt(cap,rows.length),"green")+sumStat("Late",xyFmt(lat,rows.length),"amber")+sumStat("Early",ear)+sumStat("Dead Cat",dc,"red")+sumStat("Shown",xyFmt(rows.length,totalCount))+'</div></div>';
  var pbGroupDefs=[{key:"ga",label:"Early"},{key:"gb",label:"Late"},{key:"gd",label:"PB1 Capital"},{key:"ge",label:"PB2 Capital"}];
  h+=buildIndSecTables(applyIndSecFilter(allRows),pbGroupDefs);

  // PB table headers + rows extracted as functions for reuse in portfolio tile
  function pbHeaders(){
    var hdr='<tr class="group-header-row">';
    // PB: 10(common)+6(A)+3(B)+2(C)+3(D)+3(E)+2(refs)+8(ratings) = 37
    hdr+='<th colspan="2"></th><th colspan="7" style="background:rgba(100,100,100,0.06)">Inputs</th><th></th>';
    hdr+='<th colspan="6" style="background:rgba(50,100,200,0.08)">A: Early Stage (3 of 5)</th>';
    hdr+='<th colspan="3" style="background:rgba(200,150,0,0.08)">B: Late Stage</th>';
    hdr+='<th colspan="2" style="background:rgba(200,50,50,0.08)">C: Dead Cat</th>';
    hdr+='<th colspan="3" style="background:rgba(50,150,50,0.08)">D: PB1 Capital (20D)</th>';
    hdr+='<th colspan="3" style="background:rgba(120,80,200,0.08)">E: PB2 Capital (50D)</th>';
    hdr+='<th colspan="2"></th>';
    hdr+=ratingsColHeaders().length>0?"<th colspan=\"8\" class=\"col-ratings\">Ratings</th>":"";
    hdr+='</tr><tr class="col-header-row">';
    hdr+=commonCols()
      +th("P Up","t1","col-filter","Price rising day-on-day")+th("5D Up","t2","col-filter","5-day MA rising")+th("10D Up","t3","col-filter","10-day MA rising")+th("20D Up","t4","col-filter","20-day MA rising")+th("50D Up","t5","col-filter","50-day MA rising")+th("A(/5)","a_met","col-num col-filter","Group A: count of 5 rising signals met (need 3)")
      +th("20D Up","t6","col-filter","20-day MA rising (Late)")+th("50D Up","t7","col-filter","50-day MA rising (Late)")+th("B","gb","col-filter","Group B: Late stage (1 of 2)")
      +th("Dead Cat","dead_cat","col-filter","Price 30%+ below 52W high")+th("%<52WH","pct_below","col-num col-filter","% below 52-week high")
      +th("P>20D","t9","col-filter","Price above 20D MA (PB1 capital)")+th("20D Up","t10","col-filter","20D MA rising (PB1 capital)")+th("PB1","gd","col-green","PB1 capital qualification")
      +th("P>50D","t11","col-filter","Price above 50D MA (PB2 capital)")+th("50D Up","t12","col-filter","50D MA rising (PB2 capital)")+th("PB2","ge","col-green","PB2 capital qualification")
      +th("MM 99","mm_stage","col-txt col-ref","MM99 filter stage")+th("Basing","bp_stage2","col-txt col-ref","Basing Plateau filter stage")
      +ratingsColHeaders();
    hdr+='</tr>';return hdr;
  }
  function pbRow(r){
    return'<tr onclick="openChart(\''+r.ticker+'\')" style="cursor:pointer" data-ticker="'+r.ticker+'">'+commonTds(r)
      +testCell(r.t1,r.t1_pct,"col-filter")+testCell(r.t2,r.t2_pct,"col-filter")+testCell(r.t3,r.t3_pct,"col-filter")+testCell(r.t4,r.t4_pct,"col-filter")+testCell(r.t5,r.t5_pct,"col-filter")
      +'<td class="col-num col-filter" style="font-weight:600">'+r.a_met+'/5</td>'
      +testCell(r.t6,r.t6_pct,"col-filter")+testCell(r.t7,r.t7_pct,"col-filter")+'<td class="col-filter">'+tick(r.gb)+'</td>'
      +'<td class="col-filter '+(r.dead_cat?"fail":"")+'">'+tick(r.dead_cat)+'</td>'
      +'<td class="col-num col-filter '+(r.pct_below!=null?(r.pct_below>=0.3?"fail":r.pct_below>=0.2?"amber":"pass"):"neutral")+'">'+pf(r.pct_below)+'</td>'
      +testCell(r.t9,r.t9_pct,"col-filter")+testCell(r.t10,r.t10_pct,"col-filter")
      +'<td class="col-green" style="font-weight:700">'+tick(r.gd)+'</td>'
      +testCell(r.t11,r.t11_pct,"col-filter")+testCell(r.t12,r.t12_pct,"col-filter")
      +'<td class="col-green" style="font-weight:700">'+tick(r.ge)+'</td>'
      +'<td class="col-txt col-ref">'+badge(r.mm_stage)+'</td><td class="col-txt col-ref">'+badge(r.bp_stage2)+'</td>'
      +ratingsColTds(r)+'</tr>';
  }

  // Live Portfolio tile — ALL position stocks
  var posRowsPB2=filterToPositions(allRows);
  for(var pk2=0;pk2<posRowsPB2.length;pk2++){var pr2=posRowsPB2[pk2];if(pr2.pb_stage===undefined){var pbd2=pr2.f.probing_bet;if(!pbd2||!pbd2.group_a){pr2.pb_stage="";pr2.ga=false;pr2.a_met=0;pr2.gb=false;pr2.gc=false;pr2.gd=false;pr2.ge=false;pr2.dead_cat=false;pr2.pct_below=null;pr2.t1=false;pr2.t2=false;pr2.t3=false;pr2.t4=false;pr2.t5=false;pr2.t6=false;pr2.t7=false;pr2.t8=false;pr2.t9=false;pr2.t10=false;pr2.t11=false;pr2.t12=false;}else{pr2.pb_stage=pbd2.stage;pr2.ga=pbd2.group_a.pass;pr2.a_met=pbd2.group_a.met;pr2.gb=pbd2.group_b.pass;pr2.gc=pbd2.group_c.pass;pr2.gd=pbd2.group_d.pass;pr2.ge=pbd2.group_e.pass;pr2.dead_cat=pbd2.group_c.tests.T8;pr2.pct_below=pbd2.group_c.pct_below_52wh;pr2.t1=pbd2.group_a.tests.T1;pr2.t2=pbd2.group_a.tests.T2;pr2.t3=pbd2.group_a.tests.T3;pr2.t4=pbd2.group_a.tests.T4;pr2.t5=pbd2.group_a.tests.T5;pr2.t6=pbd2.group_b.tests.T6;pr2.t7=pbd2.group_b.tests.T7;pr2.t8=pbd2.group_c.tests.T8;pr2.t9=pbd2.group_d.tests.T9;pr2.t10=pbd2.group_d.tests.T10;pr2.t11=pbd2.group_e.tests.T11;pr2.t12=pbd2.group_e.tests.T12;}pr2.t1_pct=null;pr2.t2_pct=null;pr2.t3_pct=null;pr2.t4_pct=null;pr2.t5_pct=null;pr2.t6_pct=null;pr2.t7_pct=null;pr2.t8_pct=null;pr2.t9_pct=null;pr2.t10_pct=null;pr2.t11_pct=null;pr2.t12_pct=null;pr2.mm_stage=pr2.f.mm99?pr2.f.mm99.stage:"";pr2.bp_stage2=pr2.f.basing_plateau?pr2.f.basing_plateau.stage:"";pr2.utr_stage2=pr2.f.uptrend_retest?pr2.f.uptrend_retest.stage:"";}}
  // Apply ind/sec filter to portfolio too
  var posRowsPB2f=[];for(var pf2=0;pf2<posRowsPB2.length;pf2++){if(passIndSecFilter(posRowsPB2[pf2]))posRowsPB2f.push(posRowsPB2[pf2])}
  // FIX-INPUTSORT 2026-05-04: LP rows now respect currentSort like QS rows.
  posRowsPB2f=sortData(posRowsPB2f,currentSort.col,currentSort.dir);
  if(posRowsPB2f.length>0){
    h+='<h3 class="qualified-title" id="section-portfolio">Live Portfolio ('+posRowsPB2f.length+')</h3>';
    h+='<div class="data-table-wrap"><table class="data-table data-table-portfolio"><thead>'+pbHeaders()+'</thead><tbody>';
    for(var pj=0;pj<posRowsPB2f.length;pj++)h+=pbRow(posRowsPB2f[pj]);
    h+='</tbody></table></div>';
  }

  rows=applyIndSecFilter(rows);
  h+='<h3 class="qualified-title" id="section-stocks">Qualified Stocks ('+xyFmt(rows.length,totalCount)+')</h3>';
  h+='<div class="data-table-wrap"><table class="data-table"><thead>'+pbHeaders()+'</thead><tbody>';
  for(var j=0;j<rows.length;j++)h+=pbRow(rows[j]);
  h+='</tbody></table></div>';
  document.getElementById("tab-pb").innerHTML=h;
}

// ================================================================
// UPTREND RETEST TAB
// FIX-12: testCell for EWS columns
// ================================================================
function renderUTR(){
  buildHeaderControls("utr");
  var allRows=baseRows();
  var rows=[];
  for(var j=0;j<allRows.length;j++){
    var r=allRows[j],ut=r.f.uptrend_retest;
    if(!ut||!ut.tests){
      r.utr_stage="";r.depth_pct=null;r.test_ma="";r.test_ma_dist=null;r.retest_num=0;
      r.vol_q="";r.updn="";r.candle="";r.dist_d="";r.contr="";r.rs_h="";
      r.st_roll="";r.it_intact="";r.t_depth="";r.t_ma="";
      r.cap_count=0;r.late_quality=0;
      r.t_depth_v=null;r.t_ma_v=null;r.st_roll_v=null;r.it_intact_v=null;
      r.vol_q_v=null;r.updn_v=null;r.contr_v=null;r.dist_d_v=null;r.candle_v=null;r.rs_h_v=null;
      r.sort_vol=null;r.sort_updn=null;r.sort_contr=null;r.sort_dist=null;r.sort_candle=null;r.sort_rs=null;r.sort_st=null;r.sort_it=null;
      r.mm_stage=r.f.mm99?r.f.mm99.stage:"";r.pb_stage2=r.f.probing_bet?r.f.probing_bet.stage:"";
      r.utr_capital=false;r.utr_late=false;r.utr_early=false;
      rows.push(r);continue;
    }
    r.utr_stage=ut.stage;r.depth_pct=ut.depth_pct;r.test_ma=ut.test_ma||"";
    r.test_ma_dist=ut.test_ma_dist;r.retest_num=ut.current_retest_num||0;
    r.cap_count=ut.capital_count||0;r.late_quality=ut.late_quality||0;
    var t=ut.tests,stg=ut.stage;
    var mx=ut.metrics||{};
    r.t_depth=stg==="Capital"?t.c2_depth:stg==="Late"?t.l1_depth:t.e1_depth;
    r.t_ma=stg==="Capital"?t.c1_at_ma:t.l2_ma_approach;
    r.st_roll=t.e2_ma_roll;
    var md=ut.ma_direction||{};
    r.it_intact=(md["50d_rising"]&&md["150d_rising"])?"pass":md["50d_rising"]?"amber":"fail";
    r.vol_q=stg==="Capital"?t.c3_vol:stg==="Late"?t.l3_vol_dry:t.e3_vol;
    r.updn=stg==="Capital"?t.c4_updown:t.l4_updown;
    r.candle=t.c5_candle;
    r.dist_d=stg==="Capital"?t.c6_dist:stg==="Late"?t.l6_dist:t.e4_dist;
    // Raw numeric values for toggle display
    r.t_depth_v=r.depth_pct!=null?r.depth_pct.toFixed(1)+"%":null;
    r.t_ma_v=r.test_ma_dist!=null?r.test_ma_dist.toFixed(1)+"%":null;
    r.st_roll_v=(md["5d_declining"]?"5D\u2193":"5D\u2192")+" "+(md["10d_declining"]?"10D\u2193":"10D\u2192");
    r.it_intact_v=(md["50d_rising"]?"50D\u2191":"50D\u2193")+" "+(md["150d_rising"]?"150D\u2191":"150D\u2193");
    r.vol_q_v=mx.vol_trend!=null?mx.vol_trend.toFixed(2):null;
    r.updn_v=mx.updown_ratio!=null?mx.updown_ratio.toFixed(2):null;
    r.contr_v=mx.contraction!=null?mx.contraction.toFixed(2):null;
    r.dist_d_v=mx.dist_days!=null?mx.dist_days:null;
    r.candle_v=mx.candle_quality!=null?(mx.candle_quality*100).toFixed(0)+"%":null;
    r.rs_h_v=mx.rs_percentile!=null?mx.rs_percentile:null;
    // Raw numeric sort keys for UTR test columns
    r.sort_vol=mx.vol_trend!=null?mx.vol_trend:null;
    r.sort_updn=mx.updown_ratio!=null?mx.updown_ratio:null;
    r.sort_contr=mx.contraction!=null?mx.contraction:null;
    r.sort_dist=mx.dist_days!=null?mx.dist_days:null;
    r.sort_candle=mx.candle_quality!=null?mx.candle_quality:null;
    r.sort_rs=mx.rs_percentile!=null?mx.rs_percentile:null;
    r.sort_st=(md["5d_declining"]?1:0)+(md["10d_declining"]?1:0);
    r.sort_it=(md["50d_rising"]?1:0)+(md["150d_rising"]?1:0);
    r.contr=stg==="Capital"?t.c7_contraction:t.l5_contraction;
    r.rs_h=t.c8_rs;
    r.mm_stage=r.f.mm99?r.f.mm99.stage:"";r.pb_stage2=r.f.probing_bet?r.f.probing_bet.stage:"";
    r.utr_capital=r.utr_stage==="Capital";r.utr_late=r.utr_stage==="Late"||r.utr_stage==="Capital";r.utr_early=r.utr_stage==="Early"||r.utr_stage==="Late"||r.utr_stage==="Capital";
    // Failed retest = price has broken below the test MA (negative distance)
    r.utr_failed=r.test_ma_dist!=null&&r.test_ma_dist<0;
    r.utr_failed_deep=r.test_ma_dist!=null&&r.test_ma_dist<-3;  // deep break = probably >1 week
    rows.push(r);
  }
  // Apply UTR header filters
  if(utrStageFilter==="capital"){rows=rows.filter(function(r2){return r2.utr_stage==="Capital"})}
  else if(utrStageFilter==="late"){rows=rows.filter(function(r2){return r2.utr_stage==="Late"||r2.utr_stage==="Capital"})}
  else if(utrStageFilter==="early"){rows=rows.filter(function(r2){return r2.utr_stage==="Early"||r2.utr_stage==="Late"||r2.utr_stage==="Capital"})}
  if(utrFailedFilter==="L1W"){rows=rows.filter(function(r2){return r2.utr_failed&&!r2.utr_failed_deep})}
  else if(utrFailedFilter==="L1M"){rows=rows.filter(function(r2){return r2.utr_failed})}
  rows=sortData(rows,currentSort.col,currentSort.dir);
  var totalCount=allRows.length;
  var cap=0,lat=0,ear=0;
  for(var j=0;j<rows.length;j++){var s=rows[j].utr_stage;if(s==="Capital")cap++;else if(s==="Late")lat++;else if(s==="Early")ear++}
  var h='<div class="summary-tile" id="section-summary"><h3>Uptrend Retest &mdash; Pullback Lifecycle Screen</h3>'
    +'<div class="sub">Tracks orderly pullbacks from swing high through MA retest. Early (pulling back) &rarr; Late (approaching MA) &rarr; Capital (healthy retest, act today). Invalidated if depth &gt;25%, MA break &gt;5%, dist days &ge;6, or RS &lt;50.</div>'
    +'<div class="summary-stats">'+sumStat("Capital",xyFmt(cap,rows.length),"green")+sumStat("Late",xyFmt(lat,rows.length),"amber")+sumStat("Early",ear)+sumStat("Shown",xyFmt(rows.length,totalCount))+'</div></div>';
  var utrGroupDefs=[{key:"utr_early",label:"Early+"},{key:"utr_late",label:"Late+"},{key:"utr_capital",label:"Capital"}];
  h+=buildIndSecTables(applyIndSecFilter(allRows),utrGroupDefs);

  h+=buildPortfolioTile(currentTab);
  rows=applyIndSecFilter(rows);
  h+='<h3 class="qualified-title" id="section-stocks">Qualified Stocks ('+xyFmt(rows.length,totalCount)+')</h3>';
  var inputHide=utrShowInputs?"":" utr-inputs-hidden";
  h+='<div class="data-table-wrap"><table class="data-table'+inputHide+'"><thead>';
  // ── Row 1: Key descriptions (shown by default on UTR only) ──
  h+='<tr class="utr-key-row">';
  h+='<td></td>';  // Ticker
  h+='<td class="col-input"></td>';  // Sector
  h+='<td class="col-input"></td><td class="col-input"></td><td class="col-input"></td><td class="col-input"></td><td class="col-input"></td><td class="col-input"></td><td class="col-input"></td><td class="col-input"></td>';  // Price..RS
  h+='<td>Which MA is being tested (50D/100D/150D/200D)</td><td>Completed retest cycles of this MA since uptrend began</td>';  // Test MA, Retest
  h+='<td>% below swing high (how deep is the pullback)</td><td>% distance to the test MA (how close to support)</td>';  // Depth%, MA Dist%
  h+='<td class="utr-e-first">Is pullback depth within healthy range for this stage?</td><td>Is price approaching or at the support MA?</td><td>Are short-term MAs (5D, 10D) rolling over, confirming pullback?</td><td class="utr-e-last">Are intermediate MAs (50D, 150D) still rising, confirming trend intact?</td>';  // Early
  h+='<td class="utr-l-first">Has selling volume dried up vs average? Lower = more constructive</td><td>Up-day volume vs down-day volume ratio. Above 1.0 = net accumulation</td><td>Is price range contracting? Volatility contraction precedes next move</td><td class="utr-l-last">High-volume down days in last 25 sessions. Institutional selling signal</td>';  // Late
  h+='<td class="utr-c-first">% of recent closes in upper portion of daily range. Buyers stepping in</td><td class="utr-c-last">Relative strength percentile. Must hold above 70 for Capital</td>';  // Capital
  h+='<td>Count of Capital-grade quality signals passing</td>';  // C#
  h+='<td>Pullback lifecycle stage</td>';  // Stage
  h+='<td></td><td></td>';  // X-ref
  h+=ratingsColHeaders().length>0?'<td class="col-ratings"></td><td class="col-ratings"></td><td class="col-ratings"></td><td class="col-ratings"></td><td class="col-ratings"></td><td class="col-ratings"></td><td class="col-ratings"></td><td class="col-ratings"></td>':"";
  h+='</tr>';
  // ── Row 2: Stage group headers (MM99 pattern) ──
  h+='<tr class="group-header-row">';
  h+='<th></th><th colspan="9" class="col-input" style="background:rgba(100,100,100,0.06)">Inputs</th>';
  h+='<th colspan="2" style="background:rgba(100,100,100,0.06)">Setup</th>';
  h+='<th colspan="2" style="background:rgba(100,100,100,0.06)">Metrics</th>';
  h+='<th colspan="4" style="background:rgba(200,170,0,0.08)">Early</th>';
  h+='<th colspan="4" style="background:rgba(230,100,0,0.08)">+ Late</th>';
  h+='<th colspan="2" style="background:rgba(46,125,50,0.08)">+ Capital</th>';
  h+='<th></th>';
  h+='<th style="background:rgba(120,80,200,0.08)">Stage</th>';
  h+='<th colspan="2" style="background:rgba(180,100,50,0.08)">X-Ref</th>';
  h+=ratingsColHeaders().length>0?'<th colspan="8" class="col-ratings">Ratings</th>':"";
  h+='</tr><tr class="col-header-row">';
  // ── Row 3: Individual column headers ──
  h+=utrCommonCols()
    +th("Test MA","test_ma","col-txt col-filter","Which moving average the stock is pulling back towards. Scans 50D, 100D, 150D, 200D in order and picks the first one price is approaching from above. 50D retest in a strong uptrend is the bread-and-butter Minervini entry. 200D retest is last line of defence.")
    +th("Retest #","retest_num","col-num col-filter","How many completed retest cycles of this MA since the uptrend began. A completed retest = price came within 2% of the MA then moved 5%+ above it. 1st retest is highest conviction (Minervini). 2nd is acceptable. 3rd+ is a warning \u2014 the setup is getting stale.")
    +th("Depth %","depth_pct","col-num","Percentage below the swing high. Measures how deep the pullback has gone. Early: 3\u201310% (just started). Late: 8\u201320% (Minervini guideline for buyable pullbacks). Capital: must stay under 25%. Deeper than 25% = invalidated, trend probably broken.")
    +th("MA Dist %","test_ma_dist","col-num","Distance from the test MA as a percentage. Positive = still above the MA. Late stage: within 5% and approaching. Capital stage: within 2% (at the MA or slight undercut). Negative = price has broken below \u2014 if beyond -5%, pattern is invalidated.")
    +th("Depth","depth_pct","col-filter utr-e-first","Is the pullback depth within healthy range for the current stage? Early: 3\u201310% from high. Late: 8\u201320%. Capital: under 25%. Pass means the pullback is sized correctly \u2014 not so shallow it is noise, not so deep the trend is breaking.")
    +th("MA Prox","test_ma_dist","col-filter","Is price approaching or sitting at the support MA? Late: within 5% and closing in. Capital: within 2% (touching or slight undercut). Minervini\u2019s undercut-and-rally is acceptable; a decisive break below is not.")
    +th("ST Roll","sort_st","col-filter","Are the short-term MAs (5-day and 10-day) rolling over? This confirms the pullback is real and short-term in nature. Both declining = clear pullback signal. If short-term MAs are still rising, the stock hasn\u2019t actually started pulling back yet.")
    +th("IT Intact","sort_it","col-filter utr-e-last","Are the intermediate MAs (50-day and 150-day) still rising? This is the Minervini Stage 2 requirement: the long-term trend must remain intact even as price pulls back. Both rising = pass. If 150D is declining, the broader uptrend may be over.")
    +th("Vol Dry","sort_vol","col-filter utr-l-first","Has selling volume dried up? Measured as 10-day average volume divided by 50-day average. Lower = sellers exhausted (constructive). Late: below 0.85. Capital: below 0.80. Minervini: best setups show volume dropping 40\u201360% below average during the pullback.")
    +th("Up/Dn","sort_updn","col-filter","Ratio of average up-day volume to average down-day volume. Above 1.0 = more volume on up days than down days (quiet accumulation). Capital: needs above 1.1. Below 0.8 = distribution, institutions selling \u2014 the pullback is not constructive.")
    +th("Contract","sort_contr","col-filter","Volatility contraction: ATR(10) divided by ATR(20). Below 1.0 means the daily range is narrowing \u2014 the stock is coiling. Late: below 0.90. Capital: below 0.85. One of the strongest pre-breakout signals (Minervini + Weinstein). Tight coil = energy stored for next leg.")
    +th("Dist Days","sort_dist","col-filter utr-l-last","Distribution days in the last 25 sessions. A distribution day = close below prior close on volume 25%+ above the 50-day average. Institutional selling footprint. Early: 0\u20131 expected. Late: 0\u20133 acceptable. Capital: 0\u20132 required. 6+ = invalidation.")
    +th("Candle","sort_candle","col-filter utr-c-first","Candle quality: percentage of the last 10 closes in the upper 40% of the daily range. Measures whether buyers are stepping in at the MA. Capital gate: needs 50%+. High candle quality at a support MA = accumulation pattern, buyers defending the level.")
    +th("RS Hold","sort_rs","col-filter utr-c-last","Relative strength percentile vs the market. Must hold above 70 for Capital qualification \u2014 the market still rates this stock highly despite the pullback. Below 50 = invalidation. If RS collapses during a pullback, it signals stock-specific weakness, not healthy rest.")
    +th("C#","cap_count","col-num","Count of Capital-grade quality signals currently passing (out of C1\u2013C8). All 8 must pass for Capital stage. Useful as a quick read on how close a Late-stage stock is to becoming actionable \u2014 higher count = closer to a buy signal.")
    +th("Stage","utr_stage","col-txt col-filter","Pullback lifecycle stage. Early = pullback initiated, short-term MAs rolling, trend intact. Late = approaching the test MA, quality checks intensifying. Capital = healthy retest confirmed, all signals pass, act today. None = no active pullback or pattern invalidated.")
    +th("MM99","mm_stage","col-txt col-ref","Cross-reference: Minervini 99 filter stage for this stock")+th("PB","pb_stage2","col-txt col-ref","Cross-reference: Probing Bet filter stage for this stock")
    +ratingsColHeaders();
  h+='</tr></thead><tbody>';
  for(var j=0;j<rows.length;j++){
    var r=rows[j];
    h+='<tr onclick="openChart(\''+r.ticker+'\')" style="cursor:pointer" data-ticker="'+r.ticker+'">'+utrCommonTds(r)
      +'<td class="col-txt col-filter">'+utrTestMa(r.test_ma)+'</td>'
      +'<td class="col-num col-filter">'+(r.retest_num?r.retest_num:"&mdash;")+'</td>'
      +'<td class="col-num">'+utrPct(r.depth_pct)+'</td>'
      +'<td class="col-num">'+utrMaDist(r.test_ma_dist)+'</td>'
      +utrSigCell(r.t_depth,r.t_depth_v,"utr-e-first")+utrSigCell(r.t_ma,r.t_ma_v,"")+utrSigCell(r.st_roll,r.st_roll_v,"")+utrSigCell(r.it_intact,r.it_intact_v,"utr-e-last")
      +utrSigCell(r.vol_q,r.vol_q_v,"utr-l-first")+utrSigCell(r.updn,r.updn_v,"")+utrSigCell(r.contr,r.contr_v,"")+utrSigCell(r.dist_d,r.dist_d_v,"utr-l-last")
      +utrSigCell(r.candle,r.candle_v,"utr-c-first")+utrSigCell(r.rs_h,r.rs_h_v,"utr-c-last")
      +'<td class="col-num">'+r.cap_count+'/8</td>'
      +'<td class="col-txt col-filter">'+badge(r.utr_stage)+'</td>'
      +'<td class="col-txt col-ref">'+badge(r.mm_stage)+'</td><td class="col-txt col-ref">'+badge(r.pb_stage2)+'</td>'
      +ratingsColTds(r)+'</tr>';
  }
  h+='</tbody></table></div>';
  document.getElementById("tab-utr").innerHTML=h;
}

// ================================================================
// VCP TAB
// FIX-12: testCell for VCP test columns
// ================================================================
function renderVCP(){
  buildHeaderControls("vcp");
  var allRows=baseRows();
  var rows=[];
  for(var j=0;j<allRows.length;j++){
    var r=allRows[j],vc=r.f.vcp;
    r.stage2=vc?vc.stage_2_uptrend:false;
    r.mm_score=r.f.mm99?r.f.mm99.score_11:0;r.mm_stage=r.f.mm99?r.f.mm99.stage:"";
    r.mm_ga=r.f.mm99&&r.f.mm99.group_a?r.f.mm99.group_a.pass:false;r.mm_gb=r.f.mm99&&r.f.mm99.group_b?r.f.mm99.group_b.pass:false;
    r.mm_ga_pct=null;r.mm_gb_pct=null;
    r.pb_stage=r.f.probing_bet?r.f.probing_bet.stage:"";r.bp_stage=r.f.basing_plateau?r.f.basing_plateau.stage:"";
    rows.push(r);
  }
  rows=sortData(rows,currentSort.col,currentSort.dir);
  var totalCount=allRows.length;
  var s2=0;for(var j=0;j<rows.length;j++)if(rows[j].stage2)s2++;
  var h='<div class="summary-tile" id="section-summary"><h3>VCP &mdash; Volatility Contraction Pattern</h3>'
    +'<div class="sub">Pattern detection pending Phase 2. Currently showing Stage 2 uptrend check (MM99 Groups A+B pass = price above rising 200D+150D).</div>'
    +'<div class="summary-stats">'+sumStat("Stage 2 Uptrend",xyFmt(s2,rows.length),"green")+sumStat("Not Stage 2",rows.length-s2)+sumStat("Shown",xyFmt(rows.length,totalCount))+'</div></div>';
  var vcpGroupDefs=[{key:"stage2",label:"Stage 2"},{key:"mm_ga",label:"P>200D"},{key:"mm_gb",label:"P>150D"}];
  h+=buildIndSecTables(applyIndSecFilter(allRows),vcpGroupDefs);

  h+=buildPortfolioTile(currentTab);
  rows=applyIndSecFilter(rows);
  h+='<h3 class="qualified-title" id="section-stocks">Qualified Stocks ('+xyFmt(rows.length,totalCount)+')</h3>';
  h+='<div class="data-table-wrap"><table class="data-table"><thead><tr>';
  h+=commonCols()+th("Stage 2","stage2","col-filter")+th("P>200D","mm_ga","col-filter")+th("P>150D, 150>200","mm_gb","col-filter")
    +th("MM 99","mm_score","col-num col-filter")+th("MM Stage","mm_stage","col-txt col-ref")+th("PB","pb_stage","col-txt col-ref")+th("BP","bp_stage","col-txt col-ref")
    +ratingsColHeaders();
  h+='</tr></thead><tbody>';
  for(var j=0;j<rows.length;j++){
    var r=rows[j];
    // FIX-12: testCell for VCP
    h+='<tr onclick="openChart(\''+r.ticker+'\')" style="cursor:pointer" data-ticker="'+r.ticker+'">'+commonTds(r)
      +'<td class="col-filter" style="font-weight:700">'+(r.stage2?'<span class="pass">STAGE 2</span>':'<span class="fail">NO</span>')+'</td>'
      +testCell(r.mm_ga,r.mm_ga_pct,"col-filter")+testCell(r.mm_gb,r.mm_gb_pct,"col-filter")
      +'<td class="col-num col-filter">'+scorePips(r.mm_score,11)+' '+r.mm_score+'/11</td>'
      +'<td class="col-txt col-ref">'+badge(r.mm_stage)+'</td><td class="col-txt col-ref">'+badge(r.pb_stage)+'</td><td class="col-txt col-ref">'+badge(r.bp_stage)+'</td>'
      +ratingsColTds(r)+'</tr>';
  }
  h+='</tbody></table></div>';
  document.getElementById("tab-vcp").innerHTML=h;
}

// ================================================================
// TECH DATA TAB
// ================================================================
function renderTech(){
  buildHeaderControls("tech");
  var allRows=baseRows();
  var rows=[];
  for(var j=0;j<allRows.length;j++){
    var r=allRows[j];
    r.ma5=r.mas?r.mas["5D"]:null;r.ma10=r.mas?r.mas["10D"]:null;r.ma20=r.mas?r.mas["20D"]:null;r.ma50=r.mas?r.mas["50D"]:null;
    r.ma100=r.mas?r.mas["100D"]:null;r.ma150=r.mas?r.mas["150D"]:null;r.ma200=r.mas?r.mas["200D"]:null;
    r.h52=r.high_52w;r.l52=r.low_52w;
    r.mm_score=r.f.mm99?r.f.mm99.score_11:0;
    rows.push(r);
  }
  rows=sortData(rows,currentSort.col,currentSort.dir);
  var totalCount=allRows.length;
  var h='<div class="summary-tile" id="section-summary"><h3>Technical Data &mdash; Reference View</h3>'
    +'<div class="sub">Raw price, moving average, volume, and 52-week data for all stocks in the universe.</div>'
    +'<div class="summary-stats">'+sumStat("Stocks",xyFmt(rows.length,totalCount))+'</div></div>';

  h+=buildPortfolioTile(currentTab);
  rows=applyIndSecFilter(rows);
  h+='<h3 class="qualified-title" id="section-stocks">Qualified Stocks ('+xyFmt(rows.length,totalCount)+')</h3>';
  h+='<div class="data-table-wrap"><table class="data-table"><thead><tr>';
  h+=commonCols()+th("5D","ma5","col-num col-price")+th("10D","ma10","col-num col-price")+th("20D","ma20","col-num col-price")+th("50D","ma50","col-num col-price")
    +th("100D","ma100","col-num col-price")+th("150D","ma150","col-num col-price")+th("200D","ma200","col-num col-price")
    +th("ADV 1M","adv_1m","col-num col-price")+th("ADV 3M","adv_3m","col-num col-price")
    +th("1M Up","adv_1m_up","col-num col-price")+th("1M Dn","adv_1m_dn","col-num col-price")
    +th("3M Up","adv_3m_up","col-num col-price")+th("3M Dn","adv_3m_dn","col-num col-price")
    +th("MM 99","mm_score","col-num col-filter");
  h+='</tr></thead><tbody>';
  for(var j=0;j<rows.length;j++){
    var r=rows[j];
    h+='<tr onclick="openChart(\''+r.ticker+'\')" style="cursor:pointer" data-ticker="'+r.ticker+'">'+commonTds(r)
      +'<td class="col-num col-price">'+fp(r.ma5)+'</td><td class="col-num col-price">'+fp(r.ma10)+'</td>'
      +'<td class="col-num col-price">'+fp(r.ma20)+'</td><td class="col-num col-price">'+fp(r.ma50)+'</td>'
      +'<td class="col-num col-price">'+fp(r.ma100)+'</td><td class="col-num col-price">'+fp(r.ma150)+'</td><td class="col-num col-price">'+fp(r.ma200)+'</td>'
      +'<td class="col-num col-price">'+nf(r.adv_1m)+'</td><td class="col-num col-price">'+nf(r.adv_3m)+'</td>'
      +'<td class="col-num col-price">'+nf(r.adv_1m_up)+'</td><td class="col-num col-price">'+nf(r.adv_1m_dn)+'</td>'
      +'<td class="col-num col-price">'+nf(r.adv_3m_up)+'</td><td class="col-num col-price">'+nf(r.adv_3m_dn)+'</td>'
      +'<td class="col-num col-filter">'+scorePips(r.mm_score,11)+'</td></tr>';
  }
  h+='</tbody></table></div>';
  document.getElementById("tab-tech").innerHTML=h;
}

// ================================================================
// COMBINATIONS TAB
// ================================================================
function renderCombos(){
  buildHeaderControls("combos");
  var allRows=baseRows();
  var rows=[];
  // Stage rank for AND'd toggle logic: stage S "active" means stock has reached at least S.
  // Filter shows a stock if EXISTS (setup F, stage S) such that comboSetupFilters[F] && comboStageFilters[S]
  //   && stockReachedAtLeast(F, S). Per D-MD-UI-7 sticky AND semantics.
  var stageRank={"Early":1,"Late":2,"Capital":3};
  function reaches(stockStage,toggleStage){
    if(!stockStage)return false;
    return stageRank[stockStage]>=stageRank[toggleStage];
  }
  for(var j=0;j<allRows.length;j++){
    var r=allRows[j];
    r.bp_stage=r.f.basing_plateau?r.f.basing_plateau.stage:"";
    r.pb_stage=r.f.probing_bet?r.f.probing_bet.stage:"";
    r.vcp_stage=r.f.vcp?r.f.vcp.stage:"";
    r.mm_stage=r.f.mm99?r.f.mm99.stage:"";
    r.utr_stage=r.f.uptrend_retest?r.f.uptrend_retest.stage:"";
    r.tm_grade=timeliness(r);
    r.tm_key=timelinessSortKey(r.tm_grade);
    // SESSION 9 Pass 1.2 D-MD-UI-11: Apply grade filter (AND with stage/setup toggles).
    var gKeyR=r.tm_grade==="-"?"N":r.tm_grade;
    if(!comboGradeFilters[gKeyR])continue;
    // Apply header toggles. AND semantics: at least one (setup,stage) pair active AND stock matches.
    var keep=false;
    var pairs=[
      {f:"bp",s:r.bp_stage},{f:"pb",s:r.pb_stage},{f:"vcp",s:r.vcp_stage},
      {f:"mm99",s:r.mm_stage},{f:"utr",s:r.utr_stage}
    ];
    for(var p=0;p<pairs.length;p++){
      if(!comboSetupFilters[pairs[p].f])continue;
      if(comboStageFilters.capital&&reaches(pairs[p].s,"Capital")){keep=true;break}
      if(comboStageFilters.late&&reaches(pairs[p].s,"Late")){keep=true;break}
      if(comboStageFilters.early&&reaches(pairs[p].s,"Early")){keep=true;break}
    }
    if(keep)rows.push(r);
  }
  // D-MD-UI-8: default sort = TIMELINESS desc (best first); user can override by clicking columns.
  if(currentSort.col!=="tm_key"&&currentSort.col!=="mm99_score"){
    // first-visit default: tm_key desc
    rows=sortData(rows,"tm_key","desc");
  } else {
    rows=sortData(rows,currentSort.col,currentSort.dir);
  }
  var totalCount=allRows.length;
  // SESSION 9 Pass 1.1: Summary recut — 2 panes side by side.
  // Pane 1: Filter (Y) x Stage (X) cumulative counts grid.
  //   Cumulative = stocks reaching at least that stage on that filter (D-MD-UI-7 stage semantics).
  //   Denominator = total universe (allRows.length), independent of header toggles (Q-PG3).
  // Pane 2: TIMELINESS grade distribution (A/B/C/D/F/-).
  //   Computed from allRows (full universe per D-MD-FILTER-10), not from filtered rows.
  var stageCounts={
    bp:{e:0,l:0,c:0},col:{e:0,l:0,c:0},pb:{e:0,l:0,c:0},vcp:{e:0,l:0,c:0},
    s3:{e:0,l:0,c:0},s4:{e:0,l:0,c:0},mm99:{e:0,l:0,c:0},utr:{e:0,l:0,c:0}
  };
  var gA=0,gB=0,gC=0,gD=0,gF=0,gN=0;
  function bump(obj,stg){
    if(stg==="Capital"){obj.c++;obj.l++;obj.e++;}
    else if(stg==="Late"){obj.l++;obj.e++;}
    else if(stg==="Early"){obj.e++;}
  }
  for(var j2=0;j2<allRows.length;j2++){
    var rA=allRows[j2];
    bump(stageCounts.bp,rA.f.basing_plateau?rA.f.basing_plateau.stage:"");
    bump(stageCounts.pb,rA.f.probing_bet?rA.f.probing_bet.stage:"");
    bump(stageCounts.vcp,rA.f.vcp?rA.f.vcp.stage:"");
    bump(stageCounts.mm99,rA.f.mm99?rA.f.mm99.stage:"");
    bump(stageCounts.utr,rA.f.uptrend_retest?rA.f.uptrend_retest.stage:"");
    // Pass 2 placeholders: col/s3/s4 stay at 0 until Collapse/S3/S4 logic lands.
    var gA2=timeliness(rA);
    if(gA2==="A")gA++;else if(gA2==="B")gB++;else if(gA2==="C")gC++;
    else if(gA2==="D")gD++;else if(gA2==="F")gF++;else gN++;
  }
  var totalDen=allRows.length;
  function gridCell(n){return'<td class="combo-grid-cell">'+(n>0?n+'<span class="combo-grid-den"> / '+totalDen+'</span>':'<span class="combo-grid-zero">&mdash;</span>')+'</td>'}
  function gridRow(label,key,note){
    var pendingCls=(key==="col"||key==="s3"||key==="s4")?" combo-grid-row-pending":"";
    return'<tr class="'+pendingCls+'"><th class="combo-grid-rowlabel">'+label+(note?' <span class="combo-grid-note">'+note+'</span>':'')+'</th>'
      +gridCell(stageCounts[key].e)+gridCell(stageCounts[key].l)+gridCell(stageCounts[key].c)+'</tr>';
  }
  var gridHtml=''
    +'<table class="combo-grid"><thead><tr>'
    +'<th class="combo-grid-corner">FILTER</th>'
    +'<th class="combo-grid-colhdr">EARLY</th>'
    +'<th class="combo-grid-colhdr">LATE</th>'
    +'<th class="combo-grid-colhdr">CAPITAL</th>'
    +'</tr></thead><tbody>'
    +gridRow("Collapse","col","P2")
    +gridRow("Basing Plateau","bp","")
    +gridRow("Probing Bet","pb","")
    +gridRow("VCP","vcp","")
    +gridRow("Stage 3 Topping","s3","P2")
    +gridRow("Stage 4 Declining","s4","P2")
    +gridRow("MM 99","mm99","")
    +gridRow("Uptrend Retest","utr","")
    +'</tbody></table>';
  function gradePill(letter,n){
    var clsKey=letter==="-"?"N":letter;
    return'<div class="combo-grade-row"><span class="tm-grade tm-'+clsKey+'">'+(letter==="-"?"&mdash;":letter)+'</span>'
      +'<span class="combo-grade-count">'+n+'</span><span class="combo-grade-den"> / '+totalDen+'</span></div>';
  }
  var gradeHtml=''
    +'<div class="combo-grade-block"><div class="combo-grade-title">TIMELINESS GRADE DISTRIBUTION</div>'
    +gradePill("A",gA)+gradePill("B",gB)+gradePill("C",gC)
    +gradePill("D",gD)+gradePill("F",gF)+gradePill("-",gN)
    +'<div class="combo-grade-foot">Shown after toggles: '+xyFmt(rows.length,totalDen)+'</div></div>';
  var h='<div class="summary-tile" id="section-summary"><h3>TIMELINESS &mdash; Decision Lens</h3>'
    +'<div class="sub">Per-stock A/B/C/D/F grade collapsing 8 setup filters via priority ladder. Header toggles slice by stage &times; setup (AND). Grid below shows full-universe stage counts (cumulative — stocks reaching at least that stage). Distribution panel shows grade frequency.</div>'
    +'<div class="combo-summary-grid">'
    +'<div class="combo-summary-left">'+gridHtml+'</div>'
    +'<div class="combo-summary-right">'+gradeHtml+'</div>'
    +'</div></div>';

  h+=buildPortfolioTile(currentTab);
  rows=applyIndSecFilter(rows);
  h+='<h3 class="qualified-title" id="section-stocks">Qualified Stocks ('+xyFmt(rows.length,totalCount)+')</h3>';
  h+='<div class="data-table-wrap"><table class="data-table"><thead>';
  // TIMELINESS-GROUP-HEADER (D-MD-UI-17)
  h+='<tr class="group-header-row">';
  h+='<th colspan="10" style="background:rgba(100,100,100,0.06)">Inputs</th>';
  h+='<th colspan="1" style="background:rgba(221,107,32,0.12)">Master</th>';
  h+='<th colspan="8" style="background:rgba(120,80,200,0.08)">Qualification Screens</th>';
  h+=ratingsColHeaders().length>0?'<th colspan="8" class="col-ratings">Ratings</th>':'';
  h+='</tr><tr>';
  // SESSION 9 Pass 1.1: Final col order per D-MD-FILTER-8: TIMELINESS | Collapse | BP | PB | VCP | S3 Top | S4 Dec | MM99 | UTR.
  // Collapse/S3/S4 are Pass 2 placeholders — render — badge with title tooltip until Pass 2 lands.
  h+=commonCols()
    +th("Timeliness","tm_key","col-txt col-filter")
    +th("Collapse","_collapse_stage","col-txt col-filter combo-col-pending")
    +th("Basing Plateau","bp_stage","col-txt col-filter")
    +th("Probing Bet","pb_stage","col-txt col-filter")
    +th("VCP","vcp_stage","col-txt col-filter")
    +th("S3 Topping","_s3_stage","col-txt col-filter combo-col-pending")
    +th("S4 Declining","_s4_stage","col-txt col-filter combo-col-pending")
    +th("MM 99","mm_stage","col-txt col-filter")
    +th("Uptrend Retest","utr_stage","col-txt col-filter")
    +ratingsColHeaders();
  h+='</tr></thead><tbody>';
  var pendBadge='<span class="badge badge-fail" title="Pass 2 — pending">&mdash;</span>';
  for(var j=0;j<rows.length;j++){
    var r=rows[j];
    h+='<tr onclick="openChart(\''+r.ticker+'\')" style="cursor:pointer" data-ticker="'+r.ticker+'">'+commonTds(r)
      +'<td class="col-txt col-filter">'+timelinessBadge(r.tm_grade)+'</td>'
      +'<td class="col-txt col-filter combo-col-pending">'+pendBadge+'</td>'
      +'<td class="col-txt col-filter">'+navBadge(r.bp_stage,r.ticker,"bp")+'</td>'
      +'<td class="col-txt col-filter">'+navBadge(r.pb_stage,r.ticker,"pb")+'</td>'
      +'<td class="col-txt col-filter">'+navBadge(r.vcp_stage,r.ticker,"vcp")+'</td>'
      +'<td class="col-txt col-filter combo-col-pending">'+pendBadge+'</td>'
      +'<td class="col-txt col-filter combo-col-pending">'+pendBadge+'</td>'
      +'<td class="col-txt col-filter">'+navBadge(r.mm_stage,r.ticker,"mm99")+'</td>'
      +'<td class="col-txt col-filter">'+navBadge(r.utr_stage,r.ticker,"utr")+'</td>'
      +ratingsColTds(r)+'</tr>';
  }
  h+='</tbody></table></div>';
  document.getElementById("tab-combos").innerHTML=h;
}

// ================================================================
// POSITIONS TAB
// ================================================================
function renderPositions(){
  buildHeaderControls("positions");
  var container=document.getElementById("tab-positions");
  if(!D.positions){
    container.innerHTML='<div class="summary-tile" style="text-align:center;padding:40px"><h3>Positions</h3><p style="color:var(--text-dim);margin-top:8px">positions.json not loaded. Run build_dashboard.py with positions.json in COWORK root.</p></div>';
    return;
  }
  var pos=D.positions;
  var invs=pos.investments||[];
  var totalTrades=0,activeTrades=0;
  for(var j=0;j<invs.length;j++)for(var k=0;k<invs[j].trades.length;k++){totalTrades++;if(invs[j].trades[k].status!=="planned")activeTrades++}

  var h='<div class="summary-tile" id="section-summary"><h3>Position Management</h3>'
    +'<div class="sub">Schema v'+pos.schema_version+'. Trade types: PB1/PB2 (probing bets), S1-S4 (legacy scaling). V2 migration to PB1/PB2/MM99/UR1-UR3 pending.</div>'
    +'<div class="summary-stats">'+sumStat("Investments",invs.length)+sumStat("Total Trades",totalTrades)+sumStat("Active",xyFmt(activeTrades,totalTrades),"green")+'</div></div>';

  h+='<div class="data-table-wrap" id="section-stocks"><table class="data-table"><thead><tr>'
    +'<th class="col-txt" style="width:120px">Ticker</th><th class="col-txt" style="width:200px">Company</th><th class="col-txt" style="width:50px">Currency</th>'
    +'<th>PB1</th><th>PB2</th><th>S1</th><th>S2</th><th>S3</th><th>S4</th>'
    +'<th class="col-txt">Filter Status</th></tr></thead><tbody>';

  for(var j=0;j<invs.length;j++){
    var inv=invs[j];
    var p=priceMap[inv.ticker];
    var f=filterMap[inv.ticker];
    var tradeCells="";
    var TRADE_SLOTS=6;
    for(var k=0;k<TRADE_SLOTS;k++){
      if(k<inv.trades.length){
        var t2=inv.trades[k];
        var cls=t2.status==="planned"?"neutral":t2.status==="open"?"pass":"amber";
        tradeCells+='<td class="'+cls+'" style="text-align:center">'+t2.status.charAt(0).toUpperCase()+'</td>';
      } else {
        tradeCells+='<td class="neutral" style="text-align:center">&mdash;</td>';
      }
    }
    var fStatus="&mdash;";
    if(f){
      var stages=[];
      if(f.probing_bet.stage)stages.push("PB:"+f.probing_bet.stage);
      if(f.mm99.stage)stages.push("MM:"+f.mm99.stage);
      if(f.uptrend_retest.stage)stages.push("UTR:"+f.uptrend_retest.stage);
      if(f.basing_plateau.stage)stages.push("BP:"+f.basing_plateau.stage);
      fStatus=stages.length>0?stages.join(" | "):"None qualifying";
    }
    h+='<tr onclick="openChart(\''+inv.ticker+'\')" style="cursor:pointer" data-ticker="'+inv.ticker+'">'
      +'<td class="col-txt" style="font-weight:600;color:var(--text-bright)">'+inv.ticker+'</td>'
      +'<td class="col-txt">'+inv.name+'</td><td class="col-txt">'+inv.currency+'</td>'
      +tradeCells
      +'<td class="col-txt" style="font-size:11px">'+fStatus+'</td></tr>';
  }
  h+='</tbody></table></div>';
  container.innerHTML=h;
}

// ================================================================
// SSEM TAB
// ================================================================
// ================================================================
// SS EARNINGS MOMENTUM — Session 11 helpers (D-MD-SSEM-1..4)
// ================================================================
// Filter state — sticky across tab switches per D-MD-UI-7 pattern.
// SESSION 12 — D-MD-SSEM-5/6/7: column-order mode (TYPE=dim-grouped, TIME=timeframe-grouped) + value mode (CUMUL=raw FactSet, PERIOD=net-of-prior).
var ssemRatingMap = {};   // ticker -> A/B/C/D/F/- — populated by renderSSEM, read by buildPortfolioTile
var ssemColMode = "TYPE";       // "TYPE" or "TIME"
var ssemValueMode = "CUMUL";    // "CUMUL" or "PERIOD"
var ssemDimFilters = {eps: true, ebitda: true, sales: true, tp: true, buy: true};
var ssemRatingFilters = {A: true, B: true, C: true, D: true, F: true, N: true};

// SESSION 12 — D-MD-SSEM-5..7 helpers
// Returns the value to DISPLAY in a cell based on ssemValueMode toggle.
// CUMUL mode: raw FactSet value (cumulative). PERIOD mode: net-of-prior-period (matches scoring math).
// L1M is identical in both modes (no prior to subtract).
function ssemDisplayValue(L1M, L3M, L6M, L12M, timeframe) {
  if (ssemValueMode === "CUMUL") {
    if (timeframe === "L1M") return L1M;
    if (timeframe === "L3M") return L3M;
    if (timeframe === "L6M") return L6M;
    if (timeframe === "L12M") return L12M;
  } else { // PERIOD mode
    if (timeframe === "L1M") return L1M;
    if (timeframe === "L3M") return (L3M == null || L1M == null) ? null : (L3M - L1M);
    if (timeframe === "L6M") return (L6M == null || L3M == null) ? null : (L6M - L3M);
    if (timeframe === "L12M") return (L12M == null || L6M == null) ? null : (L12M - L6M);
  }
  return null;
}

// Cell heatmap class — subtle green/neutral/red bg by % value sign+magnitude. Thresholds: ±1pp = weak, ±5pp = mid, ±10pp = strong.
function ssemHeatClass(v) {
  if (v == null) return "ssem-cell-neutral";
  if (v >= 10) return "ssem-cell-pos-strong";
  if (v >= 5) return "ssem-cell-pos-mid";
  if (v >= 1) return "ssem-cell-pos-weak";
  if (v <= -10) return "ssem-cell-neg-strong";
  if (v <= -5) return "ssem-cell-neg-mid";
  if (v <= -1) return "ssem-cell-neg-weak";
  return "ssem-cell-neutral";
}

// Sub-score for one dimension using net-off logic.
// Net-off: L1M test = raw L1M, L3M test = (L3M - L1M), L6M test = (L6M - L3M).
// Each test: positive=+1, zero=0, negative=-1, null=0. Returns object with sub_score and net values.
function ssemDimScore(L1M, L3M, L6M) {
  function sgn(v) { if (v == null) return 0; if (v > 0) return 1; if (v < 0) return -1; return 0; }
  var l1 = (L1M == null) ? 0 : L1M;
  var l3 = (L3M == null) ? 0 : L3M;
  var l6 = (L6M == null) ? 0 : L6M;
  var test_l1m = l1;
  var test_l3m = l3 - l1;
  var test_l6m = l6 - l3;
  var sub = sgn(test_l1m) + sgn(test_l3m) + sgn(test_l6m);
  // Count nulls for null-aware rating eligibility
  var nullCount = (L1M == null ? 1 : 0) + (L3M == null ? 1 : 0) + (L6M == null ? 1 : 0);
  return {sub: sub, l1m_net: test_l1m, l3m_net: test_l3m, l6m_net: test_l6m, nulls: nullCount};
}

// Compute total SSEM score (-15 to +15) and per-dimension sub-scores.
// Mutates row r adding: r.ssem_score, r.ssem_dim_eps/ebitda/sales/tp/buy (sub-scores), r.ssem_nulls (count).
function ssemEnrichRow(r) {
  var dims = [
    {key: "eps", l1: r.eps_1m, l3: r.eps_3m, l6: r.eps_6m},
    {key: "ebitda", l1: r.ebitda_1m, l3: r.ebitda_3m, l6: r.ebitda_6m},
    {key: "sales", l1: r.sales_1m, l3: r.sales_3m, l6: r.sales_6m},
    {key: "tp", l1: r.tp_1m, l3: r.tp_3m, l6: r.tp_6m},
    {key: "buy", l1: r.buy_1m, l3: r.buy_3m, l6: r.buy_6m}
  ];
  var total = 0, totalNulls = 0;
  for (var d = 0; d < dims.length; d++) {
    var ds = ssemDimScore(dims[d].l1, dims[d].l3, dims[d].l6);
    r["ssem_dim_" + dims[d].key] = ds.sub;
    r["ssem_l3m_net_" + dims[d].key] = ds.l3m_net;
    total += ds.sub;
    totalNulls += ds.nulls;
  }
  r.ssem_score = total;
  r.ssem_nulls = totalNulls;
}

// Assign A/B/C/D/F/- ratings via bell-curve distribution: 10/15/25/25/25.
// Mutates each row in `rows`. Stocks with >=3 null tests get rating "-" and are excluded from the percentile ranking.
function ssemAssignRatings(rows) {
  var eligible = [];
  var ineligible = [];
  for (var j = 0; j < rows.length; j++) {
    if (rows[j].ssem_nulls >= 3) ineligible.push(rows[j]);
    else eligible.push(rows[j]);
  }
  // Sort eligible by score descending; ties broken by ticker ascending for stability.
  eligible.sort(function(a, b) {
    if (b.ssem_score !== a.ssem_score) return b.ssem_score - a.ssem_score;
    return (a.ticker || "").localeCompare(b.ticker || "");
  });
  var n = eligible.length;
  // Cut points (10% / 15% / 25% / 25% / 25%) — assign by ordinal rank.
  var cutA = Math.ceil(n * 0.10);
  var cutB = cutA + Math.ceil(n * 0.15);
  var cutC = cutB + Math.ceil(n * 0.25);
  var cutD = cutC + Math.ceil(n * 0.25);
  for (var i = 0; i < n; i++) {
    var rating;
    if (i < cutA) rating = "A";
    else if (i < cutB) rating = "B";
    else if (i < cutC) rating = "C";
    else if (i < cutD) rating = "D";
    else rating = "F";
    eligible[i].ssem_rating = rating;
  }
  for (var k = 0; k < ineligible.length; k++) {
    ineligible[k].ssem_rating = "-";
  }
}

// Pill HTML for SSEM rating
function ssemRatingPill(grade) {
  var key = (grade === "-") ? "N" : grade;
  var label = (grade === "-") ? "&mdash;" : grade;
  return '<span class="ssem-rating-pill ssem-rating-' + key + '">' + label + '</span>';
}

// Sort key for ratings (so A sorts above F when sorting by rating column).
function ssemRatingSortKey(grade) {
  var order = {A: 5, B: 4, C: 3, D: 2, F: 1, "-": 0};
  return order[grade] != null ? order[grade] : -1;
}

// Trend arrow: comparing avg L1M vs avg L6M with 1pp threshold.
// Returns HTML string with up/flat/down arrow.
function ssemTrendArrow(avgL1M, avgL6M) {
  if (avgL1M == null || avgL6M == null) return '<span class="ssem-trend-flat">&mdash;</span>';
  var delta = avgL1M - avgL6M;
  if (delta > 1) return '<span class="ssem-trend-up" title="Accelerating: avg L1M ' + avgL1M.toFixed(1) + '% vs avg L6M ' + avgL6M.toFixed(1) + '%">&uarr;</span>';
  if (delta < -1) return '<span class="ssem-trend-down" title="Decelerating: avg L1M ' + avgL1M.toFixed(1) + '% vs avg L6M ' + avgL6M.toFixed(1) + '%">&darr;</span>';
  return '<span class="ssem-trend-flat" title="Flat: avg L1M ' + avgL1M.toFixed(1) + '% vs avg L6M ' + avgL6M.toFixed(1) + '%">&rarr;</span>';
}

// Skew glyph: cross-sectional stdev of L3M values bucketed narrow/medium/wide.
function ssemSkewGlyph(stdev) {
  if (stdev == null) return '<span class="ssem-skew">&mdash;</span>';
  var glyph, label;
  if (stdev < 3) { glyph = "&lt;&gt;"; label = "narrow"; }
  else if (stdev < 8) { glyph = "&lt;&mdash;&gt;"; label = "medium"; }
  else { glyph = "&lt;&mdash;&mdash;&gt;"; label = "wide"; }
  return '<span class="ssem-skew" title="' + label + ' (stdev ' + stdev.toFixed(1) + 'pp)">' + glyph + '</span>';
}

// Average + stdev helpers
function ssemMean(values) {
  var vals = []; for (var i = 0; i < values.length; i++) if (values[i] != null) vals.push(values[i]);
  if (vals.length === 0) return null;
  var s = 0; for (var k = 0; k < vals.length; k++) s += vals[k];
  return s / vals.length;
}
function ssemStdev(values) {
  var vals = []; for (var i = 0; i < values.length; i++) if (values[i] != null) vals.push(values[i]);
  if (vals.length < 2) return null;
  var m = 0; for (var k = 0; k < vals.length; k++) m += vals[k]; m = m / vals.length;
  var sq = 0; for (var p = 0; p < vals.length; p++) sq += (vals[p] - m) * (vals[p] - m);
  return Math.sqrt(sq / vals.length);
}

// SSEM-specific industry/sector tiles: enriched with 5 dim x 2 cols (avg L3M%, trend+skew glyph).
function buildSsemIndSecTables(rows) {
  // Build aggregations per industry and per sector.
  var indMap = {};
  var secMap = {};
  for (var j = 0; j < rows.length; j++) {
    var r = rows[j];
    var tax = getTaxonomy(r.ticker);
    var ind = tax.industry || "";
    var sec = tax.sector || "";
    if (!indMap[ind]) indMap[ind] = {count: 0, eps_l1m: [], eps_l3m: [], eps_l6m: [], ebitda_l1m: [], ebitda_l3m: [], ebitda_l6m: [], sales_l1m: [], sales_l3m: [], sales_l6m: [], tp_l1m: [], tp_l3m: [], tp_l6m: [], buy_l1m: [], buy_l3m: [], buy_l6m: []};
    if (!secMap[sec]) secMap[sec] = {industry: ind, count: 0, eps_l1m: [], eps_l3m: [], eps_l6m: [], ebitda_l1m: [], ebitda_l3m: [], ebitda_l6m: [], sales_l1m: [], sales_l3m: [], sales_l6m: [], tp_l1m: [], tp_l3m: [], tp_l6m: [], buy_l1m: [], buy_l3m: [], buy_l6m: []};
    indMap[ind].count++;
    secMap[sec].count++;
    var dims = ["eps", "ebitda", "sales", "tp", "buy"];
    for (var d = 0; d < dims.length; d++) {
      indMap[ind][dims[d] + "_l1m"].push(r[dims[d] + "_1m"]);
      indMap[ind][dims[d] + "_l3m"].push(r[dims[d] + "_3m"]);
      indMap[ind][dims[d] + "_l6m"].push(r[dims[d] + "_6m"]);
      secMap[sec][dims[d] + "_l1m"].push(r[dims[d] + "_1m"]);
      secMap[sec][dims[d] + "_l3m"].push(r[dims[d] + "_3m"]);
      secMap[sec][dims[d] + "_l6m"].push(r[dims[d] + "_6m"]);
    }
  }
  // Render
  var dimsLabels = [{k: "eps", l: "EPS"}, {k: "ebitda", l: "EBITDA"}, {k: "sales", l: "Sales"}, {k: "tp", l: "TP"}, {k: "buy", l: "Buy"}];
  function renderTile(map, isSector) {
    var keys = Object.keys(map).filter(function(k){return isSector ? /^[A-Z]+\.\d+\.\s/.test(k) : /^[A-Z]\.\s/.test(k)}).sort();
    var titleLabelSingular = isSector ? "Sector" : "Industry";
    var titleLabelPlural = isSector ? "Sectors" : "Industries";
    var h = '<div class="half-table"><div class="half-title">' + titleLabelPlural + '</div>';
    var titleLabel = titleLabelSingular;
    h += '<div class="data-table-wrap"><table class="data-table data-table-tile"><thead><tr>';
    h += '<th class="col-txt" style="cursor:pointer" onclick="tileSortTable(this)">' + titleLabel + '</th>';
    if (isSector) h += '<th class="col-txt" style="cursor:pointer" onclick="tileSortTable(this)">Industry</th>';
    h += '<th class="col-num" style="cursor:pointer" onclick="tileSortTable(this)">#</th>';
    for (var d = 0; d < dimsLabels.length; d++) {
      var lbl = dimsLabels[d].l;
      h += '<th class="col-num" style="cursor:pointer" onclick="tileSortTable(this)" title="' + lbl + ' avg L3M revision %">' + lbl + ' L3M</th>';
      h += '<th class="col-num" style="cursor:pointer" title="' + lbl + ' trend (L1M vs L6M) and skew (cross-sectional stdev of L3M)">' + lbl + ' &uarr;&darr;</th>';
    }
    h += '</tr></thead><tbody>';
    for (var k = 0; k < keys.length; k++) {
      var key = keys[k];
      var m = map[key];
      h += '<tr><td class="col-txt" style="font-size:11px">' + key + '</td>';
      if (isSector) h += '<td class="col-txt" style="font-size:10px;color:var(--text-dim)">' + m.industry + '</td>';
      h += '<td class="col-num" style="font-weight:600">' + m.count + '</td>';
      for (var d = 0; d < dimsLabels.length; d++) {
        var dk = dimsLabels[d].k;
        var avgL1M = ssemMean(m[dk + "_l1m"]);
        var avgL3M = ssemMean(m[dk + "_l3m"]);
        var avgL6M = ssemMean(m[dk + "_l6m"]);
        var stdevL3M = ssemStdev(m[dk + "_l3m"]);
        var avgStr = (avgL3M == null) ? "&mdash;" : (avgL3M >= 0 ? "+" : "") + avgL3M.toFixed(1) + "%";
        h += '<td class="ssem-tile-cell ' + ssemHeatClass(avgL3M) + '">' + avgStr + '</td>';
        h += '<td class="ssem-tile-glyph">' + ssemTrendArrow(avgL1M, avgL6M) + " " + ssemSkewGlyph(stdevL3M) + '</td>';
      }
      h += '</tr>';
    }
    h += '</tbody></table></div></div>';
    return h;
  }
  return '<div class="ind-sec-wrap" id="section-industries">' + renderTile(indMap, false) + renderTile(secMap, true) + '</div>';
}

// Setters for SSEM filter toggles
window.toggleSsemDim = function(dim) { ssemDimFilters[dim] = !ssemDimFilters[dim]; renderTab("ssem"); };
window.toggleSsemRating = function(rating) { ssemRatingFilters[rating] = !ssemRatingFilters[rating]; renderTab("ssem"); };
window.setSsemColMode = function(mode) { ssemColMode = mode; renderTab("ssem"); };
window.setSsemValueMode = function(mode) { ssemValueMode = mode; renderTab("ssem"); };

// SSEM-specific header controls — Session 12: includes 2 mode toggles on the left + 5 dim toggles + 6 rating toggles
// Targets header-tab-controls DIV (the #4 FILTERS panel) — same target as combos/MM99 dispatch.
// Per Q6 (Richard 01-May-26 Session 12): mode toggles "in #3 TOGGLES group ATM, on left of HEADER bar" — pragmatically render them on the LEFT of the same row.
function buildSsemHeaderControls() {
  var ctrls = document.getElementById("header-tab-controls");
  if (!ctrls) return;
  var h = '<div class="ssem-filter-row">';
  // Mode toggles — leftmost
  h += '<span class="ssem-mode-label">VIEW:</span>';
  h += '<button class="ssem-mode-btn' + (ssemColMode === "TYPE" ? " active" : "") + '" onclick="setSsemColMode(\'TYPE\')" title="Group columns by dimension type (EPS, EBITDA, Sales, TP, Buy)">By type</button>';
  h += '<button class="ssem-mode-btn' + (ssemColMode === "TIME" ? " active" : "") + '" onclick="setSsemColMode(\'TIME\')" title="Group columns by timeframe (L1M, L3M, L6M, L12M)">By time</button>';
  h += '<span class="ssem-filter-divider"></span>';
  h += '<span class="ssem-mode-label">VALUES:</span>';
  h += '<button class="ssem-mode-btn' + (ssemValueMode === "CUMUL" ? " active" : "") + '" onclick="setSsemValueMode(\'CUMUL\')" title="Show cumulative (raw FactSet) revisions">Cumulative</button>';
  h += '<button class="ssem-mode-btn' + (ssemValueMode === "PERIOD" ? " active" : "") + '" onclick="setSsemValueMode(\'PERIOD\')" title="Show per-period (net-of-prior) revisions — matches the scoring math">Per-period</button>';
  h += '<span class="ssem-filter-divider"></span>';
  // Existing dim + rating filters
  h += '<span class="ssem-mode-label">DIMS:</span>';
  var dims = [{k: "eps", l: "EPS"}, {k: "ebitda", l: "EBITDA"}, {k: "sales", l: "Sales"}, {k: "tp", l: "TP"}, {k: "buy", l: "Buy"}];
  for (var d = 0; d < dims.length; d++) {
    var active = ssemDimFilters[dims[d].k] ? " active" : "";
    h += '<button class="ssem-filter-btn' + active + '" onclick="toggleSsemDim(\'' + dims[d].k + '\')" title="Filter to stocks where ' + dims[d].l + ' net L3M score is positive">' + dims[d].l + '</button>';
  }
  h += '<span class="ssem-filter-divider"></span>';
  h += '<span class="ssem-mode-label">RATING:</span>';
  var ratings = [{k: "A", l: "A"}, {k: "B", l: "B"}, {k: "C", l: "C"}, {k: "D", l: "D"}, {k: "F", l: "F"}, {k: "N", l: "&mdash;"}];
  for (var rr = 0; rr < ratings.length; rr++) {
    var ractive = ssemRatingFilters[ratings[rr].k] ? " active" : "";
    h += '<button class="ssem-filter-btn ssem-rating-btn-' + ratings[rr].k + ractive + '" onclick="toggleSsemRating(\'' + ratings[rr].k + '\')">' + ratings[rr].l + '</button>';
  }
  h += '</div>';
  ctrls.innerHTML = h;
}

// SESSION 12 — D-MD-SSEM-5..7: shared header + row helpers, used by renderSSEM AND buildPortfolioTile (SSEM branch).
// Defined OUTSIDE renderSSEM so buildPortfolioTile can call them. Reads ssemColMode + ssemValueMode for branch logic.
var SSEM_DIMS = [
  {k:"eps",     l:"EPS",    grpCls:"grp-eps",    grpBg:"rgba(50,150,50,0.08)"},
  {k:"ebitda",  l:"EBITDA", grpCls:"grp-ebitda", grpBg:"rgba(50,100,200,0.08)"},
  {k:"sales",   l:"Sales",  grpCls:"grp-sales",  grpBg:"rgba(200,150,0,0.08)"},
  {k:"tp",      l:"TP",     grpCls:"grp-tp",     grpBg:"rgba(120,80,200,0.08)"},
  {k:"buy",     l:"Buy",    grpCls:"grp-buy",    grpBg:"rgba(200,50,50,0.08)"}
];
var SSEM_TIMES = [
  {k:"L1M",  l:"1M",  bg:"rgba(50,100,200,0.08)"},
  {k:"L3M",  l:"3M",  bg:"rgba(50,150,50,0.08)"},
  {k:"L6M",  l:"6M",  bg:"rgba(200,150,0,0.08)"},
  {k:"L12M", l:"12M", bg:"rgba(120,80,200,0.08)"}
];

// Returns the raw value from a row for (dim, timeframe).
function ssemRowVal(r, dimKey, tfKey) {
  var key = dimKey + "_" + (tfKey === "L1M" ? "1m" : tfKey === "L3M" ? "3m" : tfKey === "L6M" ? "6m" : "12m");
  return r[key];
}

// Build the thead HTML for the SSEM table (mode-aware). Returns full <thead>...</thead> block.
function ssemHeadersHTML() {
  var h = '<thead>';
  h += '<tr class="group-header-row">';
  h += '<th colspan="3"></th>';
  if (ssemColMode === "TYPE") {
    // 5 groups of 4 timeframes each = 20 cols
    for (var d = 0; d < SSEM_DIMS.length; d++) {
      h += '<th colspan="4" style="background:' + SSEM_DIMS[d].grpBg + '">' + SSEM_DIMS[d].l + ' Revisions</th>';
    }
  } else {
    // 4 timeframe groups of 5 dims each = 20 cols
    for (var t = 0; t < SSEM_TIMES.length; t++) {
      h += '<th colspan="5" style="background:' + SSEM_TIMES[t].bg + '">' + SSEM_TIMES[t].l + (SSEM_TIMES[t].k === "L12M" ? ' (ref)' : '') + '</th>';
    }
  }
  h += '<th colspan="2" style="background:rgba(27,61,92,0.10)">SSEM Score</th>';
  h += '</tr>';
  h += '<tr class="col-header-row">';
  h += th("Ticker","_display_name","col-txt col-identity","Stock ticker","width:120px")
    + th("Sector","_tax_sector","col-txt col-identity","Sector","width:200px")
    + th("Price","price","col-num col-price","Current price","width:52px");
  if (ssemColMode === "TYPE") {
    for (var d2 = 0; d2 < SSEM_DIMS.length; d2++) {
      var dm = SSEM_DIMS[d2];
      for (var t2 = 0; t2 < SSEM_TIMES.length; t2++) {
        var tm = SSEM_TIMES[t2];
        var firstLast = (t2 === 0 ? " " + dm.grpCls + "-first" : (t2 === SSEM_TIMES.length-1 ? " " + dm.grpCls + "-last" : ""));
        var sortKey = dm.k + "_" + (tm.k === "L1M" ? "1m" : tm.k === "L3M" ? "3m" : tm.k === "L6M" ? "6m" : "12m");
        h += th(dm.l + " " + tm.l, sortKey, "col-num col-filter" + firstLast, dm.l + " revision % " + tm.k + (tm.k === "L12M" ? " (reference only — not scored)" : ""));
      }
    }
  } else {
    // TIME mode: 4 timeframe groups
    for (var t3 = 0; t3 < SSEM_TIMES.length; t3++) {
      var tm3 = SSEM_TIMES[t3];
      for (var d3 = 0; d3 < SSEM_DIMS.length; d3++) {
        var dm3 = SSEM_DIMS[d3];
        var firstLast3 = (d3 === 0 ? " grp-tp-first" : (d3 === SSEM_DIMS.length-1 ? " grp-tp-last" : ""));
        var sortKey3 = dm3.k + "_" + (tm3.k === "L1M" ? "1m" : tm3.k === "L3M" ? "3m" : tm3.k === "L6M" ? "6m" : "12m");
        h += th(dm3.l, sortKey3, "col-num col-filter" + firstLast3, dm3.l + " " + tm3.k + " revision %");
      }
    }
  }
  h += th("Score","ssem_score","col-num","Total SSEM score (-15 to +15) using net-off logic across 15 tests");
  h += th("Rating","ssem_rating_sort","col-txt","A-F rating via bell-curve over SSEM universe (10/15/25/25/25)");
  h += '</tr></thead>';
  return h;
}

// Build the row HTML for one SSEM row (mode-aware).
function ssemRowHTML(r) {
  var tax = getTaxonomy(r.ticker);
  var dn = (displayMode === "company") ? (r.company || r.ticker) : r.ticker;
  var h = '<tr onclick="openChart(\''+r.ticker+'\')" style="cursor:pointer" data-ticker="'+r.ticker+'">';
  h += '<td class="col-txt col-identity" style="font-weight:600;color:var(--text-bright)">' + dn + '</td>';
  h += '<td class="col-txt col-identity" style="font-size:11px">' + tax.sector + '</td>';
  h += '<td class="col-num col-price">' + fp(r.price) + '</td>';
  if (ssemColMode === "TYPE") {
    for (var d = 0; d < SSEM_DIMS.length; d++) {
      var dm = SSEM_DIMS[d];
      for (var t = 0; t < SSEM_TIMES.length; t++) {
        var tm = SSEM_TIMES[t];
        var firstLast = (t === 0 ? " " + dm.grpCls + "-first" : (t === SSEM_TIMES.length-1 ? " " + dm.grpCls + "-last" : ""));
        var rawVals = [ssemRowVal(r, dm.k, "L1M"), ssemRowVal(r, dm.k, "L3M"), ssemRowVal(r, dm.k, "L6M"), ssemRowVal(r, dm.k, "L12M")];
        var v = ssemDisplayValue(rawVals[0], rawVals[1], rawVals[2], rawVals[3], tm.k);
        h += '<td class="col-num col-filter' + firstLast + ' ' + ssemHeatClass(v) + '">' + fpcRaw(v) + '</td>';
      }
    }
  } else {
    for (var t2 = 0; t2 < SSEM_TIMES.length; t2++) {
      var tm2 = SSEM_TIMES[t2];
      for (var d2 = 0; d2 < SSEM_DIMS.length; d2++) {
        var dm2 = SSEM_DIMS[d2];
        var firstLast2 = (d2 === 0 ? " grp-tp-first" : (d2 === SSEM_DIMS.length-1 ? " grp-tp-last" : ""));
        var rawVals2 = [ssemRowVal(r, dm2.k, "L1M"), ssemRowVal(r, dm2.k, "L3M"), ssemRowVal(r, dm2.k, "L6M"), ssemRowVal(r, dm2.k, "L12M")];
        var v2 = ssemDisplayValue(rawVals2[0], rawVals2[1], rawVals2[2], rawVals2[3], tm2.k);
        h += '<td class="col-num col-filter' + firstLast2 + ' ' + ssemHeatClass(v2) + '">' + fpcRaw(v2) + '</td>';
      }
    }
  }
  // Score — rating-keyed colour (D-MD-SSEM-6)
  var ratingKey = (r.ssem_rating === "-") ? "N" : r.ssem_rating;
  h += '<td class="ssem-score-cell ssem-score-r' + ratingKey + '">' + (r.ssem_score > 0 ? "+" : "") + r.ssem_score + '</td>';
  h += '<td style="text-align:center">' + ssemRatingPill(r.ssem_rating) + '</td>';
  h += '</tr>';
  return h;
}

// Pass A.2: precompute ssemRatingMap at startup so cross-tab consumers (BP, etc.)
// can read SSEM ratings before user visits SSEM tab. Mirrors the data-prep block
// in renderSSEM() up to the rating assignment, then populates the global map.
function precomputeSsemRatings(){
  if(!D.ssem) return;
  var allRows = baseRows();
  var rowsAll = [];
  for(var j=0;j<allRows.length;j++){
    var r = allRows[j];
    var ss = D.ssem[r.ticker];
    if(!ss) continue;
    r.eps_1m=ss.eps_rev?ss.eps_rev.L1M:null;r.eps_3m=ss.eps_rev?ss.eps_rev.L3M:null;
    r.eps_6m=ss.eps_rev?ss.eps_rev.L6M:null;r.eps_12m=ss.eps_rev?ss.eps_rev.L12M:null;
    r.ebitda_1m=ss.ebitda_rev?ss.ebitda_rev.L1M:null;r.ebitda_3m=ss.ebitda_rev?ss.ebitda_rev.L3M:null;
    r.ebitda_6m=ss.ebitda_rev?ss.ebitda_rev.L6M:null;r.ebitda_12m=ss.ebitda_rev?ss.ebitda_rev.L12M:null;
    r.sales_1m=ss.sales_rev?ss.sales_rev.L1M:null;r.sales_3m=ss.sales_rev?ss.sales_rev.L3M:null;
    r.sales_6m=ss.sales_rev?ss.sales_rev.L6M:null;r.sales_12m=ss.sales_rev?ss.sales_rev.L12M:null;
    r.tp_1m=ss.tp_rev?ss.tp_rev.L1M:null;r.tp_3m=ss.tp_rev?ss.tp_rev.L3M:null;
    r.tp_6m=ss.tp_rev?ss.tp_rev.L6M:null;r.tp_12m=ss.tp_rev?ss.tp_rev.L12M:null;
    r.buy_1m=ss.buy_rev?ss.buy_rev.L1M:null;r.buy_3m=ss.buy_rev?ss.buy_rev.L3M:null;
    r.buy_6m=ss.buy_rev?ss.buy_rev.L6M:null;r.buy_12m=ss.buy_rev?ss.buy_rev.L12M:null;
    r.buy_pct=ss.buy_pct;
    r.momentum=ss.momentum!=null?ss.momentum:null;
    ssemEnrichRow(r);
    rowsAll.push(r);
  }
  ssemAssignRatings(rowsAll);
  ssemRatingMap = {};
  for(var rk=0;rk<rowsAll.length;rk++){ssemRatingMap[rowsAll[rk].ticker]=rowsAll[rk].ssem_rating;}
}

function renderSSEM(){
  buildHeaderControls("ssem");
  var container=document.getElementById("tab-ssem");
  if(!D.ssem){
    container.innerHTML='<div class="summary-tile" style="text-align:center;padding:40px"><h3>SS Earnings Momentum</h3><p style="color:var(--text-dim);margin-top:8px">factset-ssem.json not loaded.</p></div>';
    return;
  }
  var allRows=baseRows();
  var rowsAll=[];
  for(var j=0;j<allRows.length;j++){
    var r=allRows[j];
    var ss=D.ssem[r.ticker];
    if(!ss)continue;
    r.eps_1m=ss.eps_rev?ss.eps_rev.L1M:null;r.eps_3m=ss.eps_rev?ss.eps_rev.L3M:null;
    r.eps_6m=ss.eps_rev?ss.eps_rev.L6M:null;r.eps_12m=ss.eps_rev?ss.eps_rev.L12M:null;
    r.ebitda_1m=ss.ebitda_rev?ss.ebitda_rev.L1M:null;r.ebitda_3m=ss.ebitda_rev?ss.ebitda_rev.L3M:null;
    r.ebitda_6m=ss.ebitda_rev?ss.ebitda_rev.L6M:null;r.ebitda_12m=ss.ebitda_rev?ss.ebitda_rev.L12M:null;
    r.sales_1m=ss.sales_rev?ss.sales_rev.L1M:null;r.sales_3m=ss.sales_rev?ss.sales_rev.L3M:null;
    r.sales_6m=ss.sales_rev?ss.sales_rev.L6M:null;r.sales_12m=ss.sales_rev?ss.sales_rev.L12M:null;
    r.tp_1m=ss.tp_rev?ss.tp_rev.L1M:null;r.tp_3m=ss.tp_rev?ss.tp_rev.L3M:null;
    r.tp_6m=ss.tp_rev?ss.tp_rev.L6M:null;r.tp_12m=ss.tp_rev?ss.tp_rev.L12M:null;
    r.buy_1m=ss.buy_rev?ss.buy_rev.L1M:null;r.buy_3m=ss.buy_rev?ss.buy_rev.L3M:null;
    r.buy_6m=ss.buy_rev?ss.buy_rev.L6M:null;r.buy_12m=ss.buy_rev?ss.buy_rev.L12M:null;
    r.buy_pct=ss.buy_pct;
    r.momentum=ss.momentum!=null?ss.momentum:null;
    ssemEnrichRow(r);
    rowsAll.push(r);
  }
  ssemAssignRatings(rowsAll);
  // Populate global ticker->rating lookup so buildPortfolioTile (LP branch) shows the same rating.
  ssemRatingMap = {};
  for(var rk=0;rk<rowsAll.length;rk++){ssemRatingMap[rowsAll[rk].ticker]=rowsAll[rk].ssem_rating;}
  // Apply header filters
  var rows=[];
  for(var rj=0;rj<rowsAll.length;rj++){
    var rr=rowsAll[rj];
    var ratingKey=rr.ssem_rating==="-"?"N":rr.ssem_rating;
    if(!ssemRatingFilters[ratingKey])continue;
    var dimOK=true;
    var anyDimOn=false;
    var dims=["eps","ebitda","sales","tp","buy"];
    for(var dx=0;dx<dims.length;dx++){
      if(ssemDimFilters[dims[dx]]){
        anyDimOn=true;
        if(!(rr["ssem_l3m_net_"+dims[dx]]>0)){dimOK=false;break}
      }
    }
    if(anyDimOn && !dimOK)continue;
    rows.push(rr);
  }
  // Default sort: ssem_score desc, ticker asc tiebreak.
  if(currentSort.col==="" || currentSort.col==null || currentSort.col==="momentum"){
    rows.sort(function(a,b){if(b.ssem_score!==a.ssem_score)return b.ssem_score-a.ssem_score; return (a.ticker||"").localeCompare(b.ticker||"")});
  } else {
    rows=sortData(rows,currentSort.col,currentSort.dir);
  }
  var totalCount=allRows.length;
  // Distribution stats for summary tile.
  var distA=0,distB=0,distC=0,distD=0,distF=0,distN=0;
  for(var jc=0;jc<rowsAll.length;jc++){
    var g=rowsAll[jc].ssem_rating;
    if(g==="A")distA++;else if(g==="B")distB++;else if(g==="C")distC++;
    else if(g==="D")distD++;else if(g==="F")distF++;else distN++;
  }
  var h='<div class="summary-tile" id="section-summary"><h3>SS Earnings Momentum &mdash; Decision Lens</h3>'
    +'<div class="sub">15-test net-of-prior-period scoring across 5 dimensions (EPS, EBITDA, Sales, TP, Buy) x 3 timeframes (L1M, L3M-net, L6M-net). Score range -15 to +15. A-F bell-curve distribution across the SSEM-covered universe (10/15/25/25/25). L12M shown for visual reference only (not scored). Use VIEW toggle to switch column grouping (TYPE/TIME); use VALUES toggle to switch between cumulative (raw) and per-period (net) revisions.</div>'
    +'<div class="summary-stats">'
    +sumStat("Stocks",xyFmt(rowsAll.length,totalCount))
    +sumStat("A",distA,"green")+sumStat("B",distB,"green")+sumStat("C",distC,"amber")+sumStat("D",distD,"amber")+sumStat("F",distF,"red")+sumStat("&mdash;",distN)
    +'</div></div>';
  h+=buildSsemIndSecTables(rowsAll);
  h+=buildPortfolioTile(currentTab);
  rows=applyIndSecFilter(rows);
  h+='<h3 class="qualified-title" id="section-stocks">Qualified Stocks ('+xyFmt(rows.length,totalCount)+')</h3>';
  h+='<div class="data-table-wrap"><table class="data-table">'+ssemHeadersHTML()+'<tbody>';
  for(var jr=0;jr<rows.length;jr++){
    h+=ssemRowHTML(rows[jr]);
  }
  h+='</tbody></table></div>';
  container.innerHTML=h;
}

// ================================================================
// VALUATION TAB
// ================================================================
function renderVal(){
  buildHeaderControls("val");
  var container=document.getElementById("tab-val");
  if(!D.valuation){
    container.innerHTML='<div class="summary-tile" style="text-align:center;padding:40px"><h3>Valuation</h3><p style="color:var(--text-dim);margin-top:8px">factset-valuation.json not loaded.</p></div>';
    return;
  }
  var allRows=baseRows();
  var rows=[];
  for(var j=0;j<allRows.length;j++){
    var r=allRows[j];
    var vl=D.valuation[r.ticker];
    if(!vl)continue;
    r.pe_cur=vl.pe_current;r.pe_pctile=vl.pe_percentile;
    r.pe_10y_lo=vl.pe_10y_low;r.pe_10y_hi=vl.pe_10y_high;
    r.eps_24mf=vl.eps_24mf!=null?vl.eps_24mf:null;
    rows.push(r);
  }
  rows=sortData(rows,currentSort.col,currentSort.dir);
  var totalCount=allRows.length;

  var cheap=0,mid=0;
  for(var j=0;j<rows.length;j++){if(rows[j].pe_pctile!=null&&rows[j].pe_pctile<=25)cheap++;if(rows[j].pe_pctile!=null&&rows[j].pe_pctile<=50)mid++}

  var h='<div class="summary-tile" id="section-summary"><h3>Valuation &mdash; P/E Multiples &amp; History</h3>'
    +'<div class="sub">P/E: current, 10Y range (range bar: green=below median, red=above), percentile (0=cheapest, 100=most expensive), EPS 24MF.</div>'
    +'<div class="summary-stats">'+sumStat("Stocks",xyFmt(rows.length,totalCount))+sumStat("P/E &le;25th pctile",xyFmt(cheap,rows.length),"green")+sumStat("P/E &le;50th pctile",xyFmt(mid,rows.length),"amber")+'</div></div>';

  h+=buildIndSecTables(rows,null);

  h+=buildPortfolioTile(currentTab);
  rows=applyIndSecFilter(rows);
  h+='<h3 class="qualified-title" id="section-stocks">Qualified Stocks ('+xyFmt(rows.length,totalCount)+')</h3>';
  h+='<div class="data-table-wrap"><table class="data-table"><thead>';
  h+='<tr class="group-header-row">';
  h+='<th colspan="3"></th>';
  h+='<th colspan="4" style="background:rgba(50,150,50,0.08)">P/E Valuation</th>';
  h+='</tr>';
  h+='<tr class="col-header-row">';
  h+=th("Ticker","_display_name","col-txt col-identity","","width:120px")+th("Sector","_tax_sector","col-txt col-identity","","width:200px")+th("Price","price","col-num col-price","","width:52px")
    +th("P/E","pe_cur","col-num col-filter grp-pe-first")+th("P/E Pctile","pe_pctile","col-num col-filter")+'<th class="col-filter">P/E 10Y Range</th>'
    +th("EPS 24MF","eps_24mf","col-num col-filter grp-pe-last");
  h+='</tr></thead><tbody>';

  for(var j=0;j<rows.length;j++){
    var r=rows[j];
    var tax=getTaxonomy(r.ticker);
    var dn=(displayMode==="company")?(r.company||r.ticker):r.ticker;
    h+='<tr onclick="openChart(\''+r.ticker+'\')" style="cursor:pointer" data-ticker="'+r.ticker+'">'
      +'<td class="col-txt col-identity" style="font-weight:600;color:var(--text-bright)">'+dn+'</td>'
      +'<td class="col-txt col-identity" style="font-size:11px">'+tax.sector+'</td>'
      +'<td class="col-num col-price">'+fp(r.price)+'</td>';
    h+='<td class="col-num col-filter grp-pe-first" style="font-weight:600">'+nf(r.pe_cur,1)+'</td>';
    h+='<td class="col-num col-filter '+pctileClass(r.pe_pctile)+'" style="font-weight:600">'+nf(r.pe_pctile)+'</td>';
    h+='<td class="range-bar-cell">'+buildRangeBar(r.pe_10y_lo,r.pe_10y_hi,r.pe_cur)+'</td>';
    h+='<td class="col-num col-filter grp-pe-last">'+nf(r.eps_24mf,2)+'</td>';
    h+='</tr>';
  }
  h+='</tbody></table></div>';
  container.innerHTML=h;
}
// ================================================================
// TAB ROUTER
// ================================================================
function renderPlaceholder(id,title){
  var c=document.getElementById("tab-"+id);
  if(c)c.innerHTML='<div class="summary-tile" style="text-align:center;padding:40px"><h3>'+title+'</h3><p style="color:var(--text-dim);margin-top:8px">Pending &mdash; requires FactSet data or qualitative ratings (Phase 4+)</p></div>';
}


// FEAT-5: Update industry/sector filter pills
function updateIndSecPills(){
  var el=document.getElementById("indsec-pills");
  if(el)el.innerHTML=indSecFilterPills();
  // Highlight sector/industry columns when filter active
  var tables=document.querySelectorAll("table.data-table");
  for(var t=0;t<tables.length;t++){
    if(hasIndSecFilter())tables[t].classList.add("ind-sec-highlight");
    else tables[t].classList.remove("ind-sec-highlight");
  }
}
// ══════════════════════════════════════════════════════════════
// CHANGES TAB (D-MD-UI-19) — Stage changes over 4 time points
// ══════════════════════════════════════════════════════════════
function renderChanges(){
  buildHeaderControls("changes");
  var fh=D.filter_history;
  if(!fh||!fh.stages){
    document.getElementById("tab-changes").innerHTML='<div class="empty-state">No historical data. Run generate_master_data.py --with-history</div>';
    return;
  }
  var stages=fh.stages;
  var t0=stages["T-0"]||{};
  var t1=stages["T-1"]||{};
  var t5=stages["T-5"]||{};
  var t22=stages["T-22"]||{};
  var allRows=baseRows();
  var h='';

  // Shared filter definitions for both tiles and table
  var FILTER_ORDER=["basing_plateau","probing_bet","vcp","mm99","uptrend_retest","s3_topping","s4_declining","collapse"]; /* STAGE-REFACTOR-V3-MARKER */
  var FILTER_COLS={"collapse":"Collapse","basing_plateau":"Basing Plateau","probing_bet":"Probing Bet","mm99":"MM 99","vcp":"VCP","uptrend_retest":"Uptrend Retest","s3_topping":"Topping","s4_declining":"Declining"}; /* Q1Q2-CLEANUP-V1 */
  var TILE_BORDER={"collapse":"rgba(180,30,30,0.35)","basing_plateau":"rgba(39,103,73,0.35)","probing_bet":"rgba(107,70,193,0.35)","mm99":"rgba(27,61,92,0.35)","vcp":"rgba(156,66,33,0.35)","uptrend_retest":"rgba(116,66,16,0.35)","s3_topping":"rgba(200,100,0,0.35)","s4_declining":"rgba(150,20,20,0.35)"};
  var GRP_KEY={"collapse":"col","basing_plateau":"bp","probing_bet":"pb","mm99":"mm99","vcp":"vcp","uptrend_retest":"utr","s3_topping":"s3","s4_declining":"s4"};
  function stRank(s){return s==="Capital"?3:s==="Late"?2:s==="Early"?1:0}

  // Build lookup for stock metadata (needed by tiles and table)
  var metaLookup={};
  allRows.forEach(function(r){metaLookup[r.ticker]=r});

  // ── SECTION 1: Changes In/Out tiles ──────────────────────
  // Section title with date range
  var fhMeta=fh._meta||{};
  var t0DateStr=fhMeta.generated||D.meta.generated||'';
  var t0D=t0DateStr?new Date(t0DateStr.replace(' ','T')):new Date();
  var t1D=new Date(t0D);t1D.setDate(t1D.getDate()-1);
  var t5D=new Date(t0D);t5D.setDate(t5D.getDate()-7);
  var t22D=new Date(t0D);t22D.setDate(t22D.getDate()-31);
  var MON=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  function fmtDDM(d){return d.getDate()+"-"+MON[d.getMonth()]}

  // ── SUMMARY BAR — stage counts + multi-qualification insight ──
  // Count Capital/Late/Early per filter from T-0 data
  var stageCounts={};
  FILTER_ORDER.forEach(function(f){stageCounts[f]={Capital:0,Late:0,Early:0}});
  var multiMap={};  // ticker → list of filters where Capital
  for(var tk in t0){
    var capFilters=[];
    FILTER_ORDER.forEach(function(f){
      var st=t0[tk]&&t0[tk][f];
      if(st==="Capital"){stageCounts[f].Capital++;capFilters.push(f)}
      else if(st==="Late")stageCounts[f].Late++;
      else if(st==="Early")stageCounts[f].Early++;
    });
    if(capFilters.length>=2)multiMap[tk]=capFilters;
  }
  // Analyse multi-qualification combos
  var multiTickers=Object.keys(multiMap);
  var comboCount={};
  multiTickers.forEach(function(tk){
    var key=multiMap[tk].map(function(f){return FILTER_COLS[f]}).sort().join(" + ");
    if(!comboCount[key])comboCount[key]={count:0,tickers:[]};
    comboCount[key].count++;
    comboCount[key].tickers.push(tk);
  });
  var comboPairs=[];
  for(var ck in comboCount)comboPairs.push({combo:ck,count:comboCount[ck].count,tickers:comboCount[ck].tickers});
  comboPairs.sort(function(a,b){return b.count-a.count});

  // TERMINOLOGY-V1-MARKER — Build summary bar HTML (band-aggregate digest)
  var BG_MAP_SB={"collapse":"rgba(180,30,30,0.08)","basing_plateau":"rgba(39,103,73,0.08)","probing_bet":"rgba(107,70,193,0.08)","mm99":"rgba(27,61,92,0.08)","vcp":"rgba(156,66,33,0.08)","uptrend_retest":"rgba(116,66,16,0.08)","s3_topping":"rgba(200,100,0,0.08)","s4_declining":"rgba(150,20,20,0.08)"};
  // Pre-compute band aggregates per filter (mirrors chgClassify logic in tiles)
  var bandAgg={};
  FILTER_ORDER.forEach(function(f){bandAgg[f]={qual:0, newW:0, newM:0, lostW:0, lostM:0};});
  for(var tk_sb in t0){
    FILTER_ORDER.forEach(function(f){
      var c0  = t0[tk_sb]  && t0[tk_sb][f]  === "Capital";
      var c5  = t5[tk_sb]  && t5[tk_sb][f]  === "Capital";
      var c22 = t22[tk_sb] && t22[tk_sb][f] === "Capital";
      if(c0) bandAgg[f].qual++;
      if(c0 && !c5 && !c22) bandAgg[f].newW++;
      else if(c0 && c5 && !c22) bandAgg[f].newM++;
      if(!c0 && c5) bandAgg[f].lostW++;
      else if(!c0 && !c5 && c22) bandAgg[f].lostM++;
    });
  }
  h+='<div id="section-summarybar" style="display:flex;gap:12px;margin:12px 0;padding:10px 12px;background:var(--bg-secondary);border:1px solid var(--border);border-radius:8px;align-items:stretch">';
  // STAGE-MAIN-SUMMARY-V1-MARKER — Left side: 4 stage groups containing 8 filter columns
  h+='<div style="display:flex;gap:8px;flex:7;align-items:stretch">';
  var STAGE_OF_SB = {"basing_plateau":1,"probing_bet":1,"vcp":2,"mm99":2,"uptrend_retest":2,"s3_topping":3,"s4_declining":4,"collapse":4};
  var STAGE_BORDER_SB = {1:"rgba(39,103,73,0.5)",2:"rgba(27,61,92,0.5)",3:"rgba(180,83,9,0.5)",4:"rgba(153,27,27,0.5)"};
  var STAGE_LBL_SB = {1:"STAGE 1",2:"STAGE 2",3:"STAGE 3",4:"STAGE 4"};
  // Render one stage box at a time, containing its filter columns
  function _sbRenderFilterCol(f){
    var lab=FILTER_COLS[f];
    var bg=BG_MAP_SB[f]||"rgba(100,100,100,0.08)";
    var ba=bandAgg[f];
    var isPh = (f==='s3_topping' || f==='s4_declining' || f==='collapse');
    var phOp = isPh ? ';opacity:0.55' : '';
    var s='<div style="flex:1;min-width:0;text-align:center;padding:5px 3px;border-radius:3px;background:'+bg+phOp+'">';
    s+='<div style="font-size:9.5px;font-weight:700;color:var(--text-primary);margin-bottom:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'+lab+'</div>';
    s+='<div style="font-size:17px;font-weight:800;color:#1b3d5c;line-height:1">'+ba.qual+'</div>';
    s+='<div style="font-size:7.5px;color:var(--text-secondary);margin-bottom:2px;letter-spacing:.3px;text-transform:uppercase">Qualified</div>';
    s+='<div style="font-size:9px;line-height:1.35;color:var(--text-secondary)">';
    s+='<div><span style="color:#38a169;font-weight:700">+'+ba.newW+'</span> wk</div>';
    s+='<div><span style="color:#68d391;font-weight:700">+'+ba.newM+'</span> mo</div>';
    s+='<div><span style="color:#e53e3e;font-weight:700">-'+ba.lostW+'</span> recent</div>';
    s+='<div><span style="color:#a0aec0;font-weight:700">-'+ba.lostM+'</span> &ge;1mo</div>';
    s+='</div>';
    s+='</div>';
    return s;
  }
  [1,2,3,4].forEach(function(stageId){
    var stageFilters = FILTER_ORDER.filter(function(f){return STAGE_OF_SB[f] === stageId});
    if(stageFilters.length === 0) return;
    var flexGrow = stageFilters.length;
    h+='<div style="flex:'+flexGrow+' 1 0;min-width:0;border:1.5px solid '+STAGE_BORDER_SB[stageId]+';border-radius:6px;padding:3px 4px 5px;background:rgba(0,0,0,0.012);display:flex;flex-direction:column">';
    h+='<div style="font-size:8px;font-weight:700;color:#4a4a4a;letter-spacing:.5px;text-align:center;padding:0 0 3px">'+STAGE_LBL_SB[stageId]+'</div>';
    h+='<div style="display:flex;gap:2px;flex:1">';
    stageFilters.forEach(function(f){ h += _sbRenderFilterCol(f); });
    h+='</div></div>';
  });
  h+='</div>';
  // Right side: Multi-Qualified Stocks (~35%)
  h+='<div style="flex:3;padding:6px 10px;border-left:1px solid var(--border)">';
  h+='<div style="font-size:11px;font-weight:700;color:var(--text-primary);margin-bottom:6px">Multi-Qualified Stocks</div>';
  if(multiTickers.length===0){
    h+='<div style="font-size:11px;color:var(--text-secondary)">No stocks currently qualify in multiple screens.</div>';
  }else{
    h+='<div style="font-size:11px;color:var(--text-secondary);margin-bottom:4px"><strong>'+multiTickers.length+'</strong> stocks qualify in 2+ screens simultaneously.</div>';
    h+='<ul style="margin:0;padding-left:14px;font-size:10px;color:var(--text-secondary);line-height:1.5">';
    comboPairs.forEach(function(cp){
      if(cp.count>5){
        h+='<li><strong>'+cp.combo+'</strong>: '+cp.count+' stocks &mdash; dominant combination</li>';
      }else if(cp.count>1){
        h+='<li><strong>'+cp.combo+'</strong>: '+cp.count+' stocks ('+cp.tickers.join(", ")+')</li>';
      }else{
        h+='<li><strong>'+cp.combo+'</strong>: '+cp.tickers[0]+'</li>';
      }
    });
    h+='</ul>';
    // Qualitative summary
    if(comboPairs.length===1){
      h+='<div style="font-size:10px;color:var(--text-secondary);margin-top:4px;font-style:italic">All multi-qualifications are in the same pair &mdash; highly concentrated overlap.</div>';
    }else if(comboPairs.length<=3){
      h+='<div style="font-size:10px;color:var(--text-secondary);margin-top:4px;font-style:italic">'+comboPairs.length+' distinct combinations &mdash; overlap is narrow and concentrated.</div>';
    }else{
      h+='<div style="font-size:10px;color:var(--text-secondary);margin-top:4px;font-style:italic">'+comboPairs.length+' distinct combinations &mdash; broad overlap across filters.</div>';
    }
  }
  h+='</div></div>';

  // ── INDUSTRY & SECTOR TILES — Capital breakdown by industry/sector × 8 filters ──
  // Build per-industry and per-sector aggregates using getTaxonomy() (canonical source, matches MM99 tiles)
  var indAgg={};  // {industry: {total:N, filters:{filterKey:{cap:N,newCap:N,lostCap:N}}}}
  var secAgg={};  // {sector: {total:N, filters:{filterKey:{cap:N,newCap:N,lostCap:N}}}}
  // Build canonical industry lookup: map raw suffix to canonical (e.g. "Consumer Staples" → "A. Consumer staples")
  var _canonIndMap={};
  for(var ci2=0;ci2<CANONICAL_INDUSTRIES.length;ci2++){
    var ci_full=CANONICAL_INDUSTRIES[ci2];
    _canonIndMap[ci_full]=ci_full;  // exact match
    // Also map the suffix without prefix (e.g. "Consumer staples" from "A. Consumer staples")
    var ci_suffix=ci_full.replace(/^[A-Z]\.\s*/,'').toLowerCase();
    _canonIndMap[ci_suffix]=ci_full;
    indAgg[ci_full]={total:0,filters:{}};
  }
  function resolveCanonInd(raw){
    if(_canonIndMap[raw])return _canonIndMap[raw];
    var lc=raw.toLowerCase();
    if(_canonIndMap[lc])return _canonIndMap[lc];
    // Try partial match: canonical suffix contained in raw or vice versa
    for(var ci3=0;ci3<CANONICAL_INDUSTRIES.length;ci3++){
      var ci_s=CANONICAL_INDUSTRIES[ci3].replace(/^[A-Z]\.\s*/,'').toLowerCase();
      if(lc.indexOf(ci_s)>=0||ci_s.indexOf(lc)>=0)return CANONICAL_INDUSTRIES[ci3];
    }
    return null;  // truly unknown — skip
  }
  // Build canonical sector map: collect all sectors from getTaxonomy(), prefer prefixed versions
  var _rawSecSet={};
  allRows.forEach(function(r){
    var tax=getTaxonomy(r.ticker);
    var sec=tax.sector||'';
    if(sec)_rawSecSet[sec]=true;
  });
  // Separate prefixed (e.g. "A.1. Beverages - beer") from non-prefixed (e.g. "Beverages - beer")
  var _prefixedSecs=[];
  var _rawSecAll=Object.keys(_rawSecSet);
  _rawSecAll.forEach(function(s){ if(/^[A-Z]+\.\d+\.\s/.test(s))_prefixedSecs.push(s); });
  // Build canonical map: every raw sector → its prefixed canonical form
  var _canonSecMap={};
  _prefixedSecs.forEach(function(s){_canonSecMap[s]=s;});
  // Map non-prefixed to prefixed via suffix matching; keep as-is if no prefixed match
  _rawSecAll.forEach(function(s){
    if(_canonSecMap[s])return; // already prefixed
    var lc=s.toLowerCase();
    for(var si=0;si<_prefixedSecs.length;si++){
      var sfx=_prefixedSecs[si].replace(/^[A-Z]+\.\d+\.\s*/,'').toLowerCase();
      if(sfx===lc){_canonSecMap[s]=_prefixedSecs[si];return;}
    }
    // No prefixed match — keep as-is (genuinely unprefixed sector)
    _canonSecMap[s]=s;
  });
  function resolveCanonSec(raw){
    if(_canonSecMap[raw])return _canonSecMap[raw];
    var lc=raw.toLowerCase();
    for(var si=0;si<_prefixedSecs.length;si++){
      if(_prefixedSecs[si].toLowerCase()===lc)return _prefixedSecs[si];
      var sfx=_prefixedSecs[si].replace(/^[A-Z]+\.\d+\.\s*/,'').toLowerCase();
      if(sfx===lc)return _prefixedSecs[si];
    }
    return raw; // no match, use as-is
  }
  allRows.forEach(function(r){
    var tax=getTaxonomy(r.ticker);
    var rawInd=tax.industry||'Unknown';
    var rawSec=tax.sector||'Unknown';
    var ind=resolveCanonInd(rawInd);
    var sec=(rawSec==='Unknown')?null:resolveCanonSec(rawSec);
    // Aggregate industry (if canonical) and sector (if resolved) independently
    if(ind){
      if(!indAgg[ind])indAgg[ind]={total:0,filters:{}};
      indAgg[ind].total++;
    }
    if(sec){
      if(!secAgg[sec])secAgg[sec]={total:0,filters:{}};
      secAgg[sec].total++;
    }
    if(!ind&&!sec)return; // skip stocks with no canonical industry or sector
    FILTER_ORDER.forEach(function(f){
      var curr=t0[r.ticker]&&t0[r.ticker][f];
      var prev=t5[r.ticker]&&t5[r.ticker][f];
      if(ind){
        if(!indAgg[ind].filters[f])indAgg[ind].filters[f]={cap:0,newCap:0,lostCap:0};
        if(curr==="Capital")indAgg[ind].filters[f].cap++;
        if(curr==="Capital"&&prev!=="Capital")indAgg[ind].filters[f].newCap++;
        if(prev==="Capital"&&curr!=="Capital")indAgg[ind].filters[f].lostCap++;
      }
      if(sec){
        if(!secAgg[sec].filters[f])secAgg[sec].filters[f]={cap:0,newCap:0,lostCap:0};
        if(curr==="Capital")secAgg[sec].filters[f].cap++;
        if(curr==="Capital"&&prev!=="Capital")secAgg[sec].filters[f].newCap++;
        if(prev==="Capital"&&curr!=="Capital")secAgg[sec].filters[f].lostCap++;
      }
    });
  });

  // Format helper: uses global valueMode ("pct" = %, "tick" = X/Y)
  // col: "cap"=Capital, "new"=New, "prev"=Previous — affects % prefix/brackets
  function chgTileFmt(x,y,col){
    if(valueMode==="pct"){
      if(y===0)return'&mdash;';
      var pct=Math.round(100*x/y);
      if(col==="new")return'+'+pct+'%';
      if(col==="prev")return'('+pct+'%)';
      return pct+'%';
    }
    return x+'/'+y;
  }
  // Heatmap colour: green intensity proportional to ratio
  function chgTileHeatmap(x,y,isLost){
    if(y===0)return'';
    var ratio=x/y;
    if(isLost){
      if(ratio>=0.3)return'background:rgba(229,62,62,0.25)';
      if(ratio>=0.15)return'background:rgba(229,62,62,0.15)';
      if(ratio>=0.05)return'background:rgba(229,62,62,0.08)';
      if(x>0)return'background:rgba(229,62,62,0.04)';
      return'';
    }
    if(ratio>=0.5)return'background:rgba(56,161,105,0.30)';
    if(ratio>=0.3)return'background:rgba(56,161,105,0.20)';
    if(ratio>=0.15)return'background:rgba(56,161,105,0.12)';
    if(ratio>=0.05)return'background:rgba(56,161,105,0.06)';
    if(x>0)return'background:rgba(56,161,105,0.03)';
    return'';
  }

  // Render tile table for a given aggregation (industry or sector)
  function renderChgAggTile(agg,title){
    var keys=Object.keys(agg);
    // Industries: only prefixed (A., B., etc.) + ≥1 Capital stock
    if(title==="Industries"){
      keys=keys.filter(function(k){
        if(!/^[A-Z]\.\s/.test(k))return false;
        for(var fi=0;fi<FILTER_ORDER.length;fi++){
          if(agg[k].filters[FILTER_ORDER[fi]]&&agg[k].filters[FILTER_ORDER[fi]].cap>0)return true;
        }
        return false;
      });
    }
    // Sectors: only show prefixed entries (A.1., B.7., etc.) — non-prefixed are FactSet fallback names
    if(title==="Sectors"){
      keys=keys.filter(function(k){return /^[A-Z]+\.\d+\.\s/.test(k);});
    }
    // Sort alphabetically by prefix (A., B., A.1., A.2., etc.)
    keys.sort(function(a,b){return a.localeCompare(b)});

    var out='<div class="half-title">'+title+' ('+keys.length+')</div>';
    out+='<div class="data-table-wrap"><table class="data-table data-table-tile" style="font-size:10px;table-layout:fixed"><thead>';
    out+='<tr class="group-header-row">';
    out+='<th rowspan="2" style="background:rgba(100,100,100,0.06);text-align:left;width:130px;overflow:hidden;text-overflow:ellipsis">'+title.replace(/s$/,'')+'</th>';
    out+='<th rowspan="2" style="background:rgba(100,100,100,0.06);width:22px">#</th>';
    var TILE_SHORT={"collapse":"Col","basing_plateau":"BP","probing_bet":"PB","mm99":"MM99","vcp":"VCP","uptrend_retest":"UTR","s3_topping":"S3","s4_declining":"S4"};
    FILTER_ORDER.forEach(function(f){
      var lab=TILE_SHORT[f]||FILTER_COLS[f];
      var BG_MAP2={"collapse":"rgba(180,30,30,0.08)","basing_plateau":"rgba(39,103,73,0.08)","probing_bet":"rgba(107,70,193,0.08)","mm99":"rgba(27,61,92,0.08)","vcp":"rgba(156,66,33,0.08)","uptrend_retest":"rgba(116,66,16,0.08)","s3_topping":"rgba(200,100,0,0.08)","s4_declining":"rgba(150,20,20,0.08)"};
      var bg=BG_MAP2[f]||"rgba(100,100,100,0.08)";
      var gk=GRP_KEY[f];
      out+='<th colspan="3" class="grp-chg-'+gk+'-first grp-chg-'+gk+'-last" style="background:'+bg+';text-align:center;font-size:9px;white-space:nowrap;padding:2px 1px">'+lab+'</th>';
    });
    out+='</tr>';
    out+='<tr>';
    FILTER_ORDER.forEach(function(f){
      var gk=GRP_KEY[f];
      out+='<th class="grp-chg-'+gk+'-first" style="font-size:8px;text-align:center;color:var(--text-secondary);font-weight:400;padding:1px">Cap</th>';
      out+='<th style="font-size:8px;text-align:center;color:#38a169;font-weight:400;padding:1px">New</th>';
      out+='<th class="grp-chg-'+gk+'-last" style="font-size:8px;text-align:center;color:#e53e3e;font-weight:400;padding:1px">Prev</th>';
    });
    out+='</tr></thead><tbody>';

    keys.forEach(function(k){
      var a=agg[k];
      var y=a.total;
      out+='<tr style="font-size:10px">';
      out+='<td style="font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="'+k+'">'+k+'</td>';
      out+='<td style="text-align:center;font-weight:600;color:var(--text-secondary)">'+y+'</td>';
      FILTER_ORDER.forEach(function(f){
        var gk=GRP_KEY[f];
        var fd=a.filters[f]||{cap:0,newCap:0,lostCap:0};
        var capHeat=chgTileHeatmap(fd.cap,y,false);
        var newHeat=chgTileHeatmap(fd.newCap,y,false);
        var lostHeat=chgTileHeatmap(fd.lostCap,y,true);
        out+='<td class="grp-chg-'+gk+'-first" style="text-align:center;padding:2px 1px;'+capHeat+'">'+chgTileFmt(fd.cap,y,"cap")+'</td>';
        out+='<td style="text-align:center;padding:2px 1px;'+(fd.newCap>0?'color:#38a169;font-weight:600;':'')+newHeat+'">'+chgTileFmt(fd.newCap,y,"new")+'</td>';
        out+='<td class="grp-chg-'+gk+'-last" style="text-align:center;padding:2px 1px;'+(fd.lostCap>0?'color:#e53e3e;font-weight:600;':'')+lostHeat+'">'+chgTileFmt(fd.lostCap,y,"prev")+'</td>';
      });
      out+='</tr>';
    });
    out+='</tbody></table></div>';
    return out;
  }

  // Side-by-side layout matching MM99 pattern: Industries LEFT, Sectors RIGHT
  h+='<div class="ind-sec-wrap" id="chg-ind-sec-wrap">';
  h+='<div class="half-table" id="section-chg-industries">'+renderChgAggTile(indAgg,"Industries")+'</div>';
  h+='<div class="half-table" id="section-chg-sectors">'+renderChgAggTile(secAgg,"Sectors")+'</div>';
  h+='</div>';
  // After render: sync Sectors tile height to Industries tile height (Industries determines)
  setTimeout(function(){
    var indTile=document.getElementById("section-chg-industries");
    var secTile=document.getElementById("section-chg-sectors");
    if(indTile&&secTile){
      var indH=indTile.offsetHeight;
      secTile.style.height=indH+"px";
      secTile.style.overflow="hidden";
      var secWrap=secTile.querySelector(".data-table-wrap");
      if(secWrap){secWrap.style.maxHeight=(indH-30)+"px";secWrap.style.overflowY="auto";}
    }
  },50);

  var _ageDays=Math.round((new Date()-t0D)/86400000);var _ageNote=_ageDays<=1?'':_ageDays<=3?' &middot; <span style="color:#d69e2e">data '+_ageDays+'d old</span>':' &middot; <span style="color:#c53030;font-weight:700">data '+_ageDays+'d old &mdash; re-run pipeline</span>';h+='<h3 id="section-summary" style="margin:16px 0 8px;font-size:15px;font-weight:700;color:var(--text-primary);letter-spacing:.4px;display:flex;align-items:baseline;justify-content:space-between;flex-wrap:wrap;gap:8px"><span>CHANGES PER SCREEN/STAGE <span style="font-weight:500;color:var(--text-secondary);font-size:13px">&mdash; '+fmtDDM(t5D)+' to '+fmtDDM(t0D)+'</span></span><span style="font-size:11px;font-weight:400;color:var(--text-secondary);text-align:right">pipeline run '+fmtDDM(t0D)+_ageNote+'</span></h3>';

  // Pre-compute "highest qualification" map: each ticker → its rightmost Capital filter
  var _hqMap={};
  if(chgHighestQual){
    // For newCap: stock is Capital NOW — find rightmost Capital filter in t0
    for(var tk in t0){
      for(var fi=FILTER_ORDER.length-1;fi>=0;fi--){
        if(t0[tk]&&t0[tk][FILTER_ORDER[fi]]==="Capital"){
          _hqMap[tk]=FILTER_ORDER[fi];
          break;
        }
      }
    }
    // For lostCap: stock WAS Capital at t5 but is NOT at t0
    // These stocks need assignment based on where they WERE Capital (t5)
    // But we must NOT override a t0 assignment — a stock still Capital in some filter
    // should use its t0 rightmost, not its t5 rightmost
    for(var tk in t5){
      if(_hqMap[tk])continue;  // already has t0 assignment (still Capital somewhere)
      for(var fi=FILTER_ORDER.length-1;fi>=0;fi--){
        if(t5[tk]&&t5[tk][FILTER_ORDER[fi]]==="Capital"){
          _hqMap[tk]=FILTER_ORDER[fi];
          break;
        }
      }
    }
  }

  // STAGE-REFACTOR-V3-MARKER
  // Tile rendering V3 (11-May-26): stage-banded, current-state-first.
  // Each tile shows 3-col grid: Month / Week / **Now** (Now bold + primary).
  // Sub-group bands top-to-bottom by signal strength:
  //   1. Sustained Capital      (M+W+Now all in)
  //   2. Newly Capital this week (in Now, not in Week — fresh gain since week-end)
  //   3. Newly Capital this month, still in (in Now + Week, not in Month — recent + settling)
  //   4. Recently lost           (not in Now, was in Week)
  //   5. Long-lost               (not in Now, not in Week, but was in Month — muted)
  // Edge cases fold into closest band.
  // Layout: Row 1 = Stage 4 + Stage 1, Row 2 = Stage 2 + Stage 3 (4 tiles per row),
  // with STAGE-labelled banners spanning each stage's tiles within a row.

  var FILT_TAB={"basing_plateau":"bp","probing_bet":"pb","mm99":"mm99","vcp":"vcp","uptrend_retest":"utr"};
  var STAGE_OF={"basing_plateau":1,"probing_bet":1,"vcp":2,"mm99":2,"uptrend_retest":2,"s3_topping":3,"s4_declining":4,"collapse":4};
  var STAGE_LABEL={1:"STAGE 1 - Basing/bottoming",2:"STAGE 2 - Markup/breakout",3:"STAGE 3 - Topping",4:"STAGE 4 - Decline"};
  var STAGE_COLOR={1:"rgba(39,103,73,0.5)",2:"rgba(27,61,92,0.5)",3:"rgba(180,83,9,0.5)",4:"rgba(153,27,27,0.5)"};

  // Classify each ticker per filter into a band.
  // Returns band id 1-5 or null if ticker has no recent activity in this filter.
  function chgClassify(tk, filt){
    var c0  = t0[tk]  && t0[tk][filt]  === "Capital";
    var c5  = t5[tk]  && t5[tk][filt]  === "Capital";
    var c22 = t22[tk] && t22[tk][filt] === "Capital";
    // Truth table for (M, W, Now):
    //   T T T -> Sustained (band 1)
    //   F F T -> Newly this week (band 2)  — fresh
    //   F T T -> Newly this month, still in (band 3)
    //   T T T already caught
    //   T F T -> flicker: was, gone last week, back now -> fold into band 2 (fresh, looks like just gained)
    //   T T F -> Recently lost (band 4)
    //   F T F -> in last week only, gone now -> band 4 (recently lost)
    //   T F F -> Long-lost (band 5)
    //   F F F -> nothing
    if(c0 && c5 && c22) return 1;
    if(c0 && !c5 && !c22) return 2;          // pure fresh gain
    if(c0 && c5 && !c22) return 3;            // gained within the month, still in
    if(c0 && !c5 && c22) return 2;            // flicker back -> treat as fresh
    if(!c0 && c5) return 4;                    // recently lost (covers TTF and FTF)
    if(!c0 && !c5 && c22) return 5;            // long-lost
    return null;
  }

  // Cell rendering — pill or empty. isPrimary = bolder/larger (the "Now" column).
  function chgPill(state, isPrimary){
    // state: 'in' (qualified), 'out' (not qualified)
    if(state === 'out'){
      return '<span style="display:inline-block;min-width:38px;text-align:center;font-size:9px;color:#cbd5e0">—</span>';
    }
    var size = isPrimary ? {pad:'2px 8px',fs:'10px',mw:'44px'} : {pad:'1px 6px',fs:'9px',mw:'38px'};
    var bg = isPrimary ? '#1b3d5c' : '#276749';
    var fg = '#fff';
    var label = isPrimary ? 'NOW' : 'QUAL';
    var weight = isPrimary ? 800 : 700;
    return '<span style="display:inline-block;min-width:'+size.mw+';text-align:center;font-size:'+size.fs+';font-weight:'+weight+';padding:'+size.pad+';border-radius:3px;background:'+bg+';color:'+fg+';letter-spacing:.3px">'+label+'</span>';
  }

  // Band-level metadata: label, accent colour, default-visible — TERMINOLOGY-V1-MARKER
  var BAND_META = {
    1: {label:'Sustained qualification',  accent:'#276749', desc:'Qualified in all three periods'},
    2: {label:'Newly qualified — this week', accent:'#48bb78', desc:'Newly qualified since last week'},
    3: {label:'Newly qualified — this month', accent:'#68d391', desc:'Newly qualified within the month, still qualified'},
    4: {label:'Recently un-qualified',  accent:'#e53e3e', desc:'Was qualified recently, no longer'},
    5: {label:'Un-qualified ≥ 1 month',   accent:'#a0aec0', desc:'Was qualified a month ago, gone since'}
  };

  // Render a single tile for one filter.
  function chgRenderTile(filt){
    var label = FILTER_COLS[filt] || filt;
    var borderCol = TILE_BORDER[filt] || 'rgba(100,100,100,0.25)';
    var tabId = FILT_TAB[filt] || '';
    var isPlaceholder = (filt === 's3_topping' || filt === 's4_declining' || filt === 'collapse');

    // Classify every ticker
    var bands = {1:[], 2:[], 3:[], 4:[], 5:[]};
    for(var tk in t0){
      var b = chgClassify(tk, filt);
      if(b !== null) bands[b].push(tk);
    }
    // STAGE-MAIN-SUMMARY-V1-MARKER — sort by (canonical-sector, ticker) within each band
    function _secKey(tk){
      var m = metaLookup[tk] || {};
      var s = m.sector || 'zzzz_unknown';
      return s.toLowerCase();
    }
    for(var bi=1; bi<=5; bi++){
      bands[bi].sort(function(a,b){
        var sa = _secKey(a), sb = _secKey(b);
        if(sa !== sb) return sa < sb ? -1 : 1;
        return a < b ? -1 : 1;
      });
    }

    // Apply highest-qualification dedup: only applies to bands 1+2+3 (current-Capital tickers)
    if(chgHighestQual){
      [1,2,3].forEach(function(bi){
        bands[bi] = bands[bi].filter(function(tk){return _hqMap[tk]===filt});
      });
    }

    var nNow = bands[1].length + bands[2].length + bands[3].length;
    var nGone = bands[4].length + bands[5].length;
    var totalRows = nNow + nGone;

    var out = '<div style="flex:1;min-width:0;max-height:600px;background:var(--bg-secondary);border:2px solid '+borderCol+';border-radius:8px;padding:8px 10px;display:flex;flex-direction:column;overflow:hidden' + (isPlaceholder ? ';opacity:0.55' : '') + '">';

    // Header: filter label + Now/Gone counters
    out += '<div style="font-weight:700;font-size:13px;margin-bottom:5px;color:var(--text-primary);display:flex;justify-content:space-between;align-items:baseline">';
    out += '<span>' + label + '</span>';
    out += '<span style="font-size:11px;font-weight:500"><span style="color:#1b3d5c">Qual ' + nNow + '</span> <span style="color:#a0aec0">/</span> <span style="color:#9b2c2c">Un-qual ' + nGone + '</span></span>';
    out += '</div>';

    if(isPlaceholder){
      out += '<div style="font-size:11px;color:var(--text-secondary);font-style:italic;padding:6px 0">Filter logic pending (Pass 2 parked).</div>';
      out += '</div>';
      return out;
    }
    if(totalRows === 0){
      out += '<div style="font-size:11px;color:var(--text-secondary);font-style:italic;padding:6px 0">No qualification activity in last month.</div>';
      out += '</div>';
      return out;
    }

    // Column headers: Stock | Month | Week | NOW (widths match band-body grid)
    out += '<div style="display:grid;grid-template-columns:1fr 38px 38px 48px;gap:3px 4px;align-items:center;font-size:9px;color:var(--text-secondary);text-transform:uppercase;letter-spacing:.4px;font-weight:700;padding-bottom:3px;border-bottom:1px solid var(--border)">';
    out += '<div>Stock</div><div style="text-align:center">Month</div><div style="text-align:center">Week</div><div style="text-align:center;color:#1b3d5c">Now</div>';
    out += '</div>';

    // Body: scrollport
    out += '<div style="overflow-y:auto;flex:1;min-height:0;padding-top:3px">';

    for(var bandId = 1; bandId <= 5; bandId++){
      var bandTickers = bands[bandId];
      if(bandTickers.length === 0) continue;
      var bm = BAND_META[bandId];
      // Band header strip
      var bandHeaderStyle = bandId === 5
        ? 'background:#f5f5f4;color:#737373;font-style:italic'
        : 'background:' + bm.accent + '1a;color:' + bm.accent + ';font-weight:700';
      out += '<div style="' + bandHeaderStyle + ';font-size:9px;letter-spacing:.3px;padding:3px 6px;margin:5px 0 2px;border-radius:3px;border-left:3px solid ' + bm.accent + '">' + bm.label + ' (' + bandTickers.length + ')</div>';

      // Group tickers by canonical sector within this band
      var _secGroups = {};
      var _secOrder = [];
      bandTickers.forEach(function(tk){
        var m = metaLookup[tk] || {};
        var sec = m.sector || 'Unknown';
        if(!_secGroups[sec]){ _secGroups[sec] = []; _secOrder.push(sec); }
        _secGroups[sec].push(tk);
      });

      // Render each sector subgroup with its mini-header
      _secOrder.forEach(function(sec){
        var secTickers = _secGroups[sec];
        // Sector sub-header: tiny grey strip
        out += '<div style="font-size:8.5px;color:#737373;font-weight:600;letter-spacing:.2px;padding:3px 4px 1px;margin-top:3px;border-bottom:1px dotted #d4d4d4">' + sec + ' <span style="font-weight:400;color:#a3a3a3">(' + secTickers.length + ')</span></div>';
        // Body grid for this sector
        out += '<div style="display:grid;grid-template-columns:1fr 38px 38px 48px;gap:2px 4px;align-items:center;padding-top:1px">';
        secTickers.forEach(function(tk){
          var meta = metaLookup[tk] || {};
          var dn = (displayMode === 'company') ? (meta.company || tk) : tk;
          var rowColor = (bandId === 5) ? '#737373' : (bandId <= 3 ? '#1a1a1a' : '#9b2c2c');
          var rowOpacity = (bandId === 5) ? '0.7' : '1';
          var secSuffix = sec ? ' <span style="font-weight:400;font-size:9px;color:#a3a3a3">' + sec + '</span>' : '';

          // Determine cell states for this ticker
          var c0  = t0[tk]  && t0[tk][filt]  === "Capital";
          var c5  = t5[tk]  && t5[tk][filt]  === "Capital";
          var c22 = t22[tk] && t22[tk][filt] === "Capital";
          var monthCell = chgPill(c22 ? 'in' : 'out', false);
          var weekCell  = chgPill(c5  ? 'in' : 'out', false);
          var nowCell   = chgPill(c0  ? 'in' : 'out', true);

          out += '<div class="chg-tile-stock" data-ticker="' + tk + '" data-tab="' + tabId + '" style="font-size:10.5px;font-weight:600;color:' + rowColor + ';opacity:' + rowOpacity + ';cursor:pointer;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="' + (meta.company || tk) + ' - ' + sec + '">' + dn + secSuffix + '</div>';
          out += '<div style="text-align:center">' + monthCell + '</div>';
          out += '<div style="text-align:center">' + weekCell + '</div>';
          out += '<div style="text-align:center">' + nowCell + '</div>';
        });
        out += '</div>';
      });
    }
    out += '</div>'; // end scrollport

    out += '</div>'; // end tile
    return out;
  }

  // Render one stage-pair row: a flex row containing 1-2 stage groups,
  // each group has its own STAGE banner + the tiles for that stage.
  function chgRenderStageRow(stageList){
    var out = '<div style="display:flex;gap:14px;margin-bottom:14px;align-items:flex-start">';
    stageList.forEach(function(stageId){
      // Find all filters belonging to this stage, in FILTER_ORDER order
      var stageFilters = FILTER_ORDER.filter(function(f){return STAGE_OF[f]===stageId});
      if(stageFilters.length === 0) return;
      var stageLabel = STAGE_LABEL[stageId];
      var stageColor = STAGE_COLOR[stageId];
      // Stage group: banner above its tiles
      // flex-grow weighted by tile count so 3-tile stages get more room
      var flexGrow = stageFilters.length;
      out += '<div style="flex:' + flexGrow + ' 1 0;min-width:0;border:1.5px solid ' + stageColor + ';border-radius:8px;padding:6px 8px 8px;background:rgba(0,0,0,0.015)">';
      out += '<div style="font-size:10px;font-weight:700;color:#1a1a1a;letter-spacing:.4px;padding:1px 4px 6px;text-transform:uppercase">' + stageLabel + '</div>';
      out += '<div style="display:flex;gap:8px;align-items:flex-start">';
      stageFilters.forEach(function(filt){
        out += chgRenderTile(filt);
      });
      out += '</div>';
      out += '</div>';
    });
    out += '</div>';
    return out;
  }

  // Two rows of stage pairs:
  //   Row 1: Stage 4 + Stage 1
  //   Row 2: Stage 2 + Stage 3
  h += '<div class="changes-tiles-v3">';
  h += chgRenderStageRow([4, 1]);
  h += chgRenderStageRow([2, 3]);
  h += '</div>';

  // ── SECTION 2: Changes table — all stocks with any change ──
  // Slim inputs (3 cols) + 8 filter groups x 4 time columns
  var TIME_LABELS=["1M","1W","1D","Now"];
  var TIME_KEYS=["T-22","T-5","T-1","T-0"];

  // Tab ID map for navBadge click-through on Now column
  var CHG_TAB={"basing_plateau":"bp","probing_bet":"pb","mm99":"mm99","vcp":"vcp","uptrend_retest":"utr"};

  // Q1Q2-CLEANUP-V1 — Build row objects with projected stage keys + sum-of-Capital-qualifications rank
  var TIME_SUFFIXES=["1m","1w","1d","now"];
  // Sum-of-bits: count Capital qualifications across BP/PB/VCP/MM99/UTR.
  // Stocks qualified in more screens rank higher regardless of WHICH screens.
  var QUAL_FILTERS=["basing_plateau","probing_bet","vcp","mm99","uptrend_retest"];
  var chgRows=[];
  for(var tk in t0){
    var changed=false;
    for(var fi=0;fi<FILTER_ORDER.length;fi++){
      var f=FILTER_ORDER[fi];
      var s0=t0[tk]?t0[tk][f]:null;
      var s1=t1[tk]?t1[tk][f]:null;
      var s5=t5[tk]?t5[tk][f]:null;
      var s22=t22[tk]?t22[tk][f]:null;
      if(s0!==s22||s0!==s5||s0!==s1){changed=true;break}
    }
    if(!changed)continue;
    var meta=metaLookup[tk]||{};
    var row={ticker:tk,sector:meta.sector||'',industry:meta.industry||''};
    // Project stage values as sortable keys: chg_{filter}_{time}
    var chgScore=0;
    FILTER_ORDER.forEach(function(f){
      var gk=GRP_KEY[f];
      var tps=[t22,t5,t1,t0];
      var vals=new Set();
      tps.forEach(function(tp,ti){
        var st=(tp[tk]&&tp[tk][f])?tp[tk][f]:null;
        row["chg_"+gk+"_"+TIME_SUFFIXES[ti]]=st;
        if(st!=null)vals.add(st);else vals.add(null);
      });
      chgScore+=vals.size-1;
    });
    row.chg_score=chgScore;
    // Compute sum-of-bits qualification count (0-5 inclusive)
    var qualCount=0;
    QUAL_FILTERS.forEach(function(f){
      if(t0[tk] && t0[tk][f] === "Capital") qualCount++;
    });
    row.chg_qual_count = qualCount;
    chgRows.push(row);
  }
  // Sort: default uses chg_qual_count desc, ticker alpha as tiebreak. Explicit column sorts override.
  var _usingDefault=false;
  if(currentSort.col === "chg_qual_count"){
    chgRows.sort(function(a,b){
      if(a.chg_qual_count !== b.chg_qual_count) return b.chg_qual_count - a.chg_qual_count;
      return a.ticker < b.ticker ? -1 : 1;
    });
    _usingDefault=true;
  }else if(currentSort.col && currentSort.col.indexOf("chg_") === 0){
    chgRows=sortData(chgRows,currentSort.col,currentSort.dir);
  }else if(currentSort.col === "ticker" || currentSort.col === "industry"){
    chgRows=sortData(chgRows,currentSort.col,currentSort.dir);
  }else if(currentSort.col === "sector"){
    chgRows=sortData(chgRows,"sector",currentSort.dir);
  }else{
    chgRows.sort(function(a,b){
      if(a.chg_qual_count !== b.chg_qual_count) return b.chg_qual_count - a.chg_qual_count;
      return a.ticker < b.ticker ? -1 : 1;
    });
    _usingDefault=true;
  }
  // Sector-grouping toggle still applies — alpha-by-sector pass only when user explicitly enables it.

  h+='<div id="section-stocks" style="margin-top:8px;font-size:13px;color:var(--text-secondary)">'+chgRows.length+' stocks with stage changes (vs 1M ago)</div>';

  h+='<div class="chg-table-wrap"><table class="data-table chg-table">';
  // Colgroup: 3 Inputs cols (fixed width) + 32 stage cols (equal share of remaining space)
  h+='<colgroup><col style="width:110px"><col style="width:160px"><col style="width:160px">';
  for(var ci=0;ci<32;ci++)h+='<col>';
  h+='</colgroup><thead>';

  // Stage column-group header row (STAGE 1 / 2 / 3 / 4) - STAGE-MAIN-SUMMARY-V1-MARKER
  // Stage spans (in FILTER_ORDER): S1 = BP+PB (2 filters × 4 cols = 8), S2 = VCP+MM99+UTR (3 × 4 = 12),
  // S3 = Topping (1 × 4 = 4), S4 = Declining+Collapse (2 × 4 = 8). Total 32 filter cols + 3 Inputs.
  var STAGE_HDR_BG = {1:"rgba(39,103,73,0.18)",2:"rgba(27,61,92,0.18)",3:"rgba(180,83,9,0.18)",4:"rgba(153,27,27,0.18)"};
  var STAGE_HDR_BORDER = {1:"rgba(39,103,73,0.55)",2:"rgba(27,61,92,0.55)",3:"rgba(180,83,9,0.55)",4:"rgba(153,27,27,0.55)"};
  h+='<tr class="group-header-row">';
  h+='<th colspan="3" style="background:rgba(100,100,100,0.04);border-bottom:1px solid var(--border)"></th>';
  h+='<th colspan="8" style="background:'+STAGE_HDR_BG[1]+';border:2px solid '+STAGE_HDR_BORDER[1]+';border-bottom:none;font-weight:800;font-size:10px;letter-spacing:.5px;color:#1a1a1a">STAGE 1 - Basing</th>';
  h+='<th colspan="12" style="background:'+STAGE_HDR_BG[2]+';border:2px solid '+STAGE_HDR_BORDER[2]+';border-bottom:none;font-weight:800;font-size:10px;letter-spacing:.5px;color:#1a1a1a">STAGE 2 - Markup</th>';
  h+='<th colspan="4" style="background:'+STAGE_HDR_BG[3]+';border:2px solid '+STAGE_HDR_BORDER[3]+';border-bottom:none;font-weight:800;font-size:10px;letter-spacing:.5px;color:#1a1a1a">STAGE 3 - Topping</th>';
  h+='<th colspan="8" style="background:'+STAGE_HDR_BG[4]+';border:2px solid '+STAGE_HDR_BORDER[4]+';border-bottom:none;font-weight:800;font-size:10px;letter-spacing:.5px;color:#1a1a1a">STAGE 4 - Decline</th>';
  h+='</tr>';

  // Filter group header row (existing)
  h+='<tr class="group-header-row">';
  h+='<th colspan="3" style="background:rgba(100,100,100,0.06)">Inputs</th>';
  FILTER_ORDER.forEach(function(f){
    var lab=FILTER_COLS[f];
    var BG_MAP={"collapse":"rgba(180,30,30,0.08)","basing_plateau":"rgba(39,103,73,0.08)","probing_bet":"rgba(107,70,193,0.08)","mm99":"rgba(27,61,92,0.08)","vcp":"rgba(156,66,33,0.08)","uptrend_retest":"rgba(116,66,16,0.08)","s3_topping":"rgba(200,100,0,0.08)","s4_declining":"rgba(150,20,20,0.08)"};
    var bg=BG_MAP[f]||"rgba(100,100,100,0.08)";
    var gk=GRP_KEY[f];
    h+='<th colspan="4" class="grp-chg-'+gk+'-first grp-chg-'+gk+'-last" style="background:'+bg+'">'+lab+'</th>';
  });
  h+='</tr>';

  // Column header row — sortable via th() helper
  h+='<tr>';
  h+=th("Ticker","ticker","col-txt col-filter");
  h+=th("Industry","industry","col-txt col-filter");
  h+=th("Sector","sector","col-txt col-filter");
  FILTER_ORDER.forEach(function(f){
    var gk=GRP_KEY[f];
    TIME_SUFFIXES.forEach(function(sf,ti){
      var tl=TIME_LABELS[ti];
      var sortKey="chg_"+gk+"_"+sf;
      var isFirst=(ti===0);var isLast=(ti===3);
      var isNow=(ti===3);
      var cls='col-txt col-filter';
      if(isFirst)cls+=' grp-chg-'+gk+'-first';
      if(isLast)cls+=' grp-chg-'+gk+'-last';
      if(isNow)cls+=' chg-now-th';
      h+=th(tl,sortKey,cls,null,"font-size:10px");
    });
  });
  h+='</tr></thead><tbody>';

  // Render rows from sorted chgRows, with optional sector group separators
  var _prevSector='';
  chgRows.forEach(function(row){
    if(chgSectorGrouping&&row.sector!==_prevSector){
      var secLabel=row.sector||'Unknown';
      var secCount=chgRows.filter(function(r){return r.sector===row.sector}).length;
      h+='<tr class="group-header-row"><td colspan="35" style="background:rgba(100,100,100,0.06);font-weight:700;font-size:11px;padding:4px 8px;color:var(--text-primary)">'+secLabel+' <span style="font-weight:400;color:var(--text-secondary)">('+secCount+')</span></td></tr>';
      _prevSector=row.sector;
    }
    h+='<tr data-ticker="'+row.ticker+'">';
    h+='<td class="col-txt">'+row.ticker+'</td>';
    h+='<td class="col-txt">'+row.industry+'</td>';
    h+='<td class="col-txt">'+row.sector+'</td>';
    FILTER_ORDER.forEach(function(f){
      var gk=GRP_KEY[f];
      // Read stage values from projected row keys
      var stages_at=[row["chg_"+gk+"_1m"],row["chg_"+gk+"_1w"],row["chg_"+gk+"_1d"],row["chg_"+gk+"_now"]];
      // Render 4 cells with change highlighting + group borders + Now emphasis
      for(var ci=0;ci<4;ci++){
        var st=stages_at[ci];
        var prev_st=ci>0?stages_at[ci-1]:null;
        var cellStyle='';
        if(ci>0&&st!==prev_st){
          var r0=stRank(st);var r1=stRank(prev_st);
          if(r0>r1)cellStyle='background:rgba(56,161,105,0.15)';  // upgrade = green
          else if(r0<r1)cellStyle='background:rgba(229,62,62,0.15)';  // downgrade = red
        }
        var isFirst=(ci===0);var isLast=(ci===3);var isNow=(ci===3);
        var tdCls='col-txt';
        if(isFirst)tdCls+=' grp-chg-'+gk+'-first';
        if(isLast)tdCls+=' grp-chg-'+gk+'-last';
        if(isNow)tdCls+=' chg-now-cell';
        // Now column (ci===3): use navBadge for clickable navigation to filter tab
        if(isNow&&st&&CHG_TAB[f]){
          h+='<td class="'+tdCls+'" style="'+cellStyle+';text-align:center">'+navBadge(st,row.ticker,CHG_TAB[f])+'</td>';
        }else{
          var badge_cls=st==="Capital"?"badge-capital":st==="Late"?"badge-late":st==="Early"?"badge-early":"badge-fail";
          var badge_txt=st||'&mdash;';
          h+='<td class="'+tdCls+'" style="'+cellStyle+';text-align:center"><span class="badge '+badge_cls+'" style="font-size:10px">'+badge_txt+'</span></td>';
        }
      }
    });
    h+='</tr>';
  });

  h+='</tbody></table></div>';

  document.getElementById("tab-changes").innerHTML=h;
}

// =============================================================================
// SUMMARY TAB MODULE — V1.2 (12-May-26)
// =============================================================================
// SUMMARY-TAB-MARKER — idempotency marker for patcher detection
//
// V1.2 changes vs V1.1:
//   - Qualified Stocks table built to FULL spec: 29 columns
//     * Inputs (4): Ticker, Company, Industry, Sector
//     * TM Stage 1 (2): BP, PB stage pills
//     * TM Stage 2 (3): VCP, MM99, UTR stage pills
//     * TM Stage 3 (1): Topping pill
//     * TM Stage 4 (2): Declining, Collapse pills
//     * TM RS (4): rs_percentile, rs_vs_sector, rs_vs_industry, rs_excess_market
//     * SSEM (5): 1M / 3M / 6M / 12M timeframe scores + Total
//     * Valuation (2): pe_percentile + buildRangeBar sparkline
//     * Master Ratings (6): TM, Them, Fund, ICBB, SSEM, Val
//   - 3-row header: Group / Sub-group / Column name
//   - Conditional colour on all pill, RS, SSEM, Valuation cells
//   - No internal scroll on Qualified Stocks (per Richard Q14)
//
// V1 spec: decisions.md D-MD-UI-38..47
// =============================================================================

/* SUMMARY-TAB-MARKER-START */

var masterRatingsMap = {};
var summaryFilters = {tm:"",thematic:"",fund_chg:"",icbb:"",ssem:"",val:""};
var summarySectorGrouping = false;

var SUM_RATINGS = ["tm","thematic","fund_chg","icbb","ssem","val"];
var SUM_RATING_LABELS = {tm:"Technical Momentum",thematic:"Thematic Fit",fund_chg:"Fundamental Change",icbb:"ICBB",ssem:"SSEM",val:"Valuation"};
var SUM_RATING_SHORT = {tm:"TM",thematic:"Them",fund_chg:"Fund",icbb:"ICBB",ssem:"SSEM",val:"Val"};
var SUM_PLACEHOLDER_TOOLTIP = "Placeholder pending REPOSITORY A&J memo rollout";

// TM stage column order
var SUM_STAGE_COLS = [
  {id:"basing_plateau",  label:"BP",   stage:1},
  {id:"probing_bet",     label:"PB",   stage:1},
  {id:"vcp",             label:"VCP",  stage:2},
  {id:"mm99",            label:"MM99", stage:2},
  {id:"uptrend_retest",  label:"UTR",  stage:2},
  {id:"s3_topping",      label:"Top",  stage:3},
  {id:"s4_declining",    label:"Dec",  stage:4},
  {id:"collapse",        label:"Col",  stage:4}
];
var SUM_RS_COLS = [
  {key:"rs_percentile",     label:"RS%",     format:"pct100"},
  {key:"rs_vs_sector",      label:"vs Sec",  format:"pct100"},
  {key:"rs_vs_industry",    label:"vs Ind",  format:"pct100"},
  {key:"rs_excess_market",  label:"vs Mkt",  format:"signedPct"}
];
var SUM_SSEM_TIMEFRAMES = ["1m","3m","6m","12m"];
var SUM_SSEM_DIMS = ["eps","ebitda","sales","tp","buy"];

// V1 TM rating logic per Richard 12-May-26
function SUM_v1TmRating(tk) {
  var fm = (typeof filterMap !== "undefined") ? filterMap[tk] : null;
  if (!fm) return "-";
  var s = function(k) { return (fm[k] && fm[k].stage) ? fm[k].stage : null; };
  if (s("s4_declining") === "Capital" || s("collapse") === "Capital") return "F";
  if (s("s3_topping") === "Capital") return "D";
  if (s("mm99") === "Capital" || s("vcp") === "Capital" || s("uptrend_retest") === "Capital") return "A";
  if (s("probing_bet") === "Capital") return "B";
  if (s("basing_plateau") === "Capital") return "C";
  if (s("mm99") === "Late" || s("vcp") === "Late" || s("uptrend_retest") === "Late") return "C";
  return "-";
}

// SSEM per-timeframe total: sum signed scores across 5 dimensions for ONE timeframe
// Mirrors the existing ssemDimScore logic but for a single lookback.
function SUM_ssemTimeframeTotal(ss, tf) {
  if (!ss) return null;
  // tf = "1m" | "3m" | "6m" | "12m"
  // ss.eps_rev.L1M / L3M / L6M / L12M structure
  var keyMap = {"1m":"L1M","3m":"L3M","6m":"L6M","12m":"L12M"};
  var lookbackKey = keyMap[tf];
  if (!lookbackKey) return null;
  var total = 0;
  var hasAny = false;
  for (var di = 0; di < SUM_SSEM_DIMS.length; di++) {
    var dim = SUM_SSEM_DIMS[di];
    var revKey = dim + "_rev";
    var data = ss[revKey];
    if (!data) continue;
    var v = data[lookbackKey];
    if (v == null) continue;
    hasAny = true;
    // Sign-based scoring: positive = +1, negative = -1, zero = 0
    if (v > 0.001) total += 1;
    else if (v < -0.001) total -= 1;
  }
  return hasAny ? total : null;
}

function deriveMasterRatings() {
  if (!D || !D.prices) return;
  var valElig = [];
  if (D.valuation) {
    for (var tk in D.valuation) {
      if (!D.valuation.hasOwnProperty(tk)) continue;
      if (tk === "_meta") continue;
      var v = D.valuation[tk];
      if (v && v.pe_percentile != null) valElig.push({ticker: tk, pct: v.pe_percentile});
    }
  }
  valElig.sort(function(a,b){
    if (a.pct !== b.pct) return a.pct - b.pct;
    return (a.ticker || "").localeCompare(b.ticker || "");
  });
  var nVal = valElig.length;
  var vA = Math.ceil(nVal*0.10), vB = vA+Math.ceil(nVal*0.15), vC = vB+Math.ceil(nVal*0.25), vD = vC+Math.ceil(nVal*0.25);
  var valBuckets = {};
  for (var vi = 0; vi < nVal; vi++) {
    var vr;
    if (vi < vA) vr = "A";
    else if (vi < vB) vr = "B";
    else if (vi < vC) vr = "C";
    else if (vi < vD) vr = "D";
    else vr = "F";
    valBuckets[valElig[vi].ticker] = vr;
  }
  masterRatingsMap = {};
  for (var pi = 0; pi < D.prices.length; pi++) {
    var p = D.prices[pi];
    var tkr = p.ticker;
    masterRatingsMap[tkr] = {
      tm:       SUM_v1TmRating(tkr),
      thematic: "C",
      fund_chg: "C",
      icbb:     "C",
      ssem:     (typeof ssemRatingMap !== "undefined" && ssemRatingMap[tkr]) ? ssemRatingMap[tkr] : "-",
      val:      valBuckets[tkr] != null ? valBuckets[tkr] : "-"
    };
  }
}

function SUM_ratingSortKey(g) {
  var order = {A:5,B:4,C:3,D:2,F:1,"-":0};
  return order[g] != null ? order[g] : -1;
}

function SUM_passesFilter(rating, filterState) {
  if (filterState === "") return true;
  if (filterState === "A") return rating === "A";
  if (filterState === "AB") return rating === "A" || rating === "B";
  return true;
}

function SUM_ratingPill(grade, isPlaceholder) {
  var key = (grade === "-") ? "N" : grade;
  var label = (grade === "-") ? "&mdash;" : grade;
  var ttl = isPlaceholder ? ' title="' + SUM_PLACEHOLDER_TOOLTIP + '"' : "";
  return '<span class="ssem-rating-pill ssem-rating-' + key + '"' + ttl + '>' + label + '</span>';
}

// Stage status pill (Cap green / Late amber / Early pink / dash)
function SUM_stagePill(stage) {
  if (!stage || stage === "None") return '<span style="color:#888">&mdash;</span>';
  if (stage === "Capital") return '<span style="display:inline-block;padding:2px 6px;background:#E1F5EE;color:#085041;border-radius:10px;font-size:9px;font-weight:600">Cap</span>';
  if (stage === "Late")    return '<span style="display:inline-block;padding:2px 6px;background:#FAEEDA;color:#633806;border-radius:10px;font-size:9px;font-weight:600">Late</span>';
  if (stage === "Early")   return '<span style="display:inline-block;padding:2px 6px;background:#FBEAF0;color:#4B1528;border-radius:10px;font-size:9px;font-weight:600">Early</span>';
  return '<span style="color:#888">&mdash;</span>';
}

// 5-step conditional colour helper for percentile-like values (0-100; higher = better)
function SUM_pctileBucketStyle(v) {
  if (v == null) return "";
  if (v >= 85) return "background:#97C459;color:#173404;";
  if (v >= 70) return "background:#C0DD97;color:#173404;";
  if (v >= 50) return "background:#EAF3DE;color:#173404;";
  if (v >= 30) return "background:#FAEEDA;color:#412402;";
  return "background:#FCEBEB;color:#501313;";
}

// Conditional colour for inverted percentile (lower = better, e.g. PE percentile)
function SUM_invPctileBucketStyle(v) {
  if (v == null) return "";
  if (v <= 15) return "background:#97C459;color:#173404;";
  if (v <= 30) return "background:#C0DD97;color:#173404;";
  if (v <= 60) return "background:#EAF3DE;color:#173404;";
  if (v <= 80) return "background:#FAEEDA;color:#412402;";
  return "background:#FCEBEB;color:#501313;";
}

// Conditional colour for signed integer scores (e.g. SSEM scores -5 to +5)
function SUM_signedBucketStyle(v) {
  if (v == null) return "";
  if (v >= 4) return "background:#97C459;color:#173404;";
  if (v >= 2) return "background:#C0DD97;color:#173404;";
  if (v >= 1) return "background:#EAF3DE;color:#173404;";
  if (v === 0) return "";
  if (v >= -1) return "background:#FAEEDA;color:#412402;";
  return "background:#FCEBEB;color:#501313;";
}

// Conditional colour for excess-return decimals (e.g. rs_excess_market)
function SUM_excessBucketStyle(v) {
  if (v == null) return "";
  if (v >= 0.30) return "background:#97C459;color:#173404;";
  if (v >= 0.15) return "background:#C0DD97;color:#173404;";
  if (v >= 0.05) return "background:#EAF3DE;color:#173404;";
  if (v > -0.05) return "";
  if (v > -0.15) return "background:#FAEEDA;color:#412402;";
  return "background:#FCEBEB;color:#501313;";
}

// Format a signed percentile as +X% or -X%
function SUM_fmtSignedPct(v) {
  if (v == null) return "&mdash;";
  var pct = Math.round(v * 100);
  return (pct >= 0 ? "+" : "") + pct + "%";
}

// Format a signed integer score
function SUM_fmtSignedInt(v) {
  if (v == null) return "&mdash;";
  return (v > 0 ? "+" : "") + v;
}


window.cycleSummaryFilter = function(ratingId) {
  var cur = summaryFilters[ratingId];
  summaryFilters[ratingId] = cur === "" ? "A" : (cur === "A" ? "AB" : "");
  renderSummary();
};

window.toggleSummarySectorGrouping = function() {
  summarySectorGrouping = !summarySectorGrouping;
  renderSummary();
};

window.resetSummaryFilters = function() {
  summaryFilters = {tm:"",thematic:"",fund_chg:"",icbb:"",ssem:"",val:""};
  summarySectorGrouping = false;
  renderSummary();
};

function SUM_getTaxonomy(tkr) {
  if (typeof getTaxonomy === "function") return getTaxonomy(tkr);
  var tm = (D && D.ticker_mapping) ? D.ticker_mapping[tkr] : null;
  return {industry: tm ? tm.industry : "", sector: tm ? tm.sector : ""};
}

function SUM_filterToggleHTML(ratingId) {
  var state = summaryFilters[ratingId];
  var label = SUM_RATING_SHORT[ratingId];
  var stateLabel = state === "" ? "all" : (state === "A" ? "A" : "A|B");
  var activeClass = state === "" ? "" : "sum-tog-active";
  var bgStyle = state === "A" ? "background:#EAF3DE;border-color:#639922" :
                state === "AB" ? "background:#C0DD97;border-color:#639922" : "";
  return '<button class="tog sum-tog ' + activeClass + '" onclick="cycleSummaryFilter(\'' + ratingId + '\')" ' +
         'title="' + SUM_RATING_LABELS[ratingId] + ' filter: No filter -> A only -> A or B" ' +
         'style="display:inline-flex;align-items:center;gap:4px;padding:3px 8px;font-size:11px;' + bgStyle + '">' +
         '<span style="font-weight:700">' + label + '</span>' +
         '<span style="font-weight:600;font-size:10px">' + stateLabel + '</span></button>';
}

function renderSummary() {
  buildHeaderControls("summary");
  var container = document.getElementById("tab-summary");
  if (!container) return;
  if (Object.keys(masterRatingsMap).length === 0) deriveMasterRatings();
  var h = "";

  // Section 1: Header controls
  h += '<div class="summary-controls" style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:8px 12px;background:rgba(100,100,100,0.04);border-bottom:1px solid var(--border);margin-bottom:8px">';
  h += '<div style="font-size:11px;color:var(--text-secondary);font-weight:600;letter-spacing:.3px">MASTER RATING FILTERS:</div>';
  for (var ri = 0; ri < SUM_RATINGS.length; ri++) h += SUM_filterToggleHTML(SUM_RATINGS[ri]);
  var sgActive = summarySectorGrouping ? "sum-tog-active" : "";
  var sgLabel = summarySectorGrouping ? "ON" : "OFF";
  h += '<span style="color:var(--text-secondary);font-size:11px">|</span>';
  h += '<button class="tog sum-tog ' + sgActive + '" onclick="toggleSummarySectorGrouping()" style="padding:3px 8px;font-size:11px"><span style="font-weight:700">Sector grouping</span> <span style="color:#666;font-size:10px">' + sgLabel + '</span></button>';
  h += '<button class="tog" onclick="resetSummaryFilters()" style="padding:3px 8px;font-size:11px;margin-left:auto">Reset filters</button>';
  h += '</div>';

  // V1 watermark
  h += '<div style="padding:4px 12px;font-size:10px;color:var(--text-secondary);font-style:italic;background:rgba(180,120,30,0.06);border-bottom:1px solid rgba(180,120,30,0.15)">';
  h += 'V1: Technical Momentum uses placeholder dichotomy. Thematic Fit / Fundamental Change / ICBB use placeholder "C" (uniform). Bell-curve methodology and REPOSITORY rating sources are in development.';
  h += '</div>';

  h += SUM_renderWaterfall();
  h += SUM_renderIndustriesFlow();
  h += SUM_renderSectorsFlow();
  h += SUM_renderQualifiedStocks();
  container.innerHTML = h;
}

function SUM_renderWaterfall() {
  var tickers = [];
  for (var pi = 0; pi < D.prices.length; pi++) tickers.push(D.prices[pi].ticker);
  var Y = (D.meta && D.meta.stock_count) ? D.meta.stock_count : tickers.length;
  var THR = [
    {key:"A",   label:"A only",      passSet:{A:1}},
    {key:"AB",  label:"A or B",      passSet:{A:1,B:1}},
    {key:"ABC", label:"A or B or C", passSet:{A:1,B:1,C:1}}
  ];
  var rows = [];
  for (var ti = 0; ti < THR.length; ti++) {
    var thr = THR[ti], surv = tickers.slice(), cells = [];
    for (var ci = 0; ci < SUM_RATINGS.length; ci++) {
      var rid = SUM_RATINGS[ci], next = [], folded = 0;
      for (var si = 0; si < surv.length; si++) {
        var tkr = surv[si], mr = masterRatingsMap[tkr], rg = mr ? mr[rid] : "-";
        if (rg === "-") { next.push(tkr); folded++; }
        else if (thr.passSet[rg]) next.push(tkr);
      }
      cells.push({count:next.length, foldForwarded:folded});
      surv = next;
    }
    rows.push({key:thr.key, label:thr.label, cells:cells, muted:(thr.key==="ABC")});
  }
  var h = '<div class="summary-section" style="margin:8px 12px 16px 12px">';
  h += '<div style="font-size:13px;font-weight:700;color:var(--text-primary);margin-bottom:6px">Funnel - multi-rating pass-through</div>';
  h += '<div style="font-size:11px;color:var(--text-secondary);margin-bottom:6px;font-style:italic">Stocks without a rating in a column are folded forward (counted as passing). Row 3 (A/B/C) is greyed as cross-reference only.</div>';
  h += '<table class="data-table" style="width:100%;table-layout:fixed">';
  h += '<colgroup><col style="width:90px">';
  for (var cj = 0; cj < 6; cj++) h += '<col>';
  h += '</colgroup>';
  h += '<thead><tr><th style="background:rgba(100,100,100,0.06);text-align:left;padding:6px 8px">Threshold</th>';
  for (var rii = 0; rii < SUM_RATINGS.length; rii++) h += '<th style="background:rgba(100,100,100,0.06);font-size:11px;font-weight:700;text-align:center;padding:6px 8px">' + SUM_RATING_LABELS[SUM_RATINGS[rii]] + '</th>';
  h += '</tr></thead><tbody>';
  var ROW_BG = ["rgba(39,103,73,0.18)","rgba(56,161,105,0.10)","rgba(180,180,180,0.18)"];
  var ROW_TEXT = ["#1a4731","#22543d","#777"];
  for (var rri = 0; rri < rows.length; rri++) {
    var row = rows[rri];
    h += '<tr><td style="font-weight:700;padding:6px 8px;background:' + ROW_BG[rri] + ';color:' + ROW_TEXT[rri] + ';text-align:center;font-size:11px;letter-spacing:.3px">' + row.label + '</td>';
    for (var cn = 0; cn < row.cells.length; cn++) {
      var c = row.cells[cn];
      var cs = 'text-align:center;padding:8px;font-family:Menlo,monospace;font-size:13px;font-weight:600;';
      if (row.muted) cs += 'color:#777;background:rgba(200,200,200,0.06);';
      else cs += 'color:#1a4731;background:' + ROW_BG[rri] + ';';
      var ttl = c.foldForwarded > 0 ? c.foldForwarded + ' of these ' + c.count + ' stocks passed via missing-rating fold-forward' : 'No fold-forward in this cell';
      h += '<td style="' + cs + '" title="' + ttl + '">' + c.count + ' / ' + Y + '</td>';
    }
    h += '</tr>';
  }
  h += '</tbody></table></div>';
  return h;
}

function SUM_buildGroupAggregates(groupKey) {
  var groups = {};
  for (var pi = 0; pi < D.prices.length; pi++) {
    var p = D.prices[pi], tax = SUM_getTaxonomy(p.ticker), gn = tax[groupKey];
    if (!gn) continue;
    if (!groups[gn]) {
      groups[gn] = {groupName:gn, total:0, perRating:{}};
      for (var ri = 0; ri < SUM_RATINGS.length; ri++) groups[gn].perRating[SUM_RATINGS[ri]] = {A:0,B:0,C:0,D:0,F:0,dash:0};
    }
    groups[gn].total++;
    var mr = masterRatingsMap[p.ticker];
    if (!mr) continue;
    for (var rj = 0; rj < SUM_RATINGS.length; rj++) {
      var rid = SUM_RATINGS[rj], g = mr[rid];
      if (g === "-") groups[gn].perRating[rid].dash++;
      else if (g === "A" || g === "B" || g === "C" || g === "D" || g === "F") groups[gn].perRating[rid][g]++;
    }
  }
  var out = [];
  for (var gn2 in groups) {
    if (!groups.hasOwnProperty(gn2)) continue;
    var g2 = groups[gn2];
    for (var rk = 0; rk < SUM_RATINGS.length; rk++) {
      var pr = g2.perRating[SUM_RATINGS[rk]];
      pr.pct_AB = g2.total > 0 ? (pr.A + pr.B) / g2.total : 0;
    }
    out.push(g2);
  }
  out.sort(function(a,b){
    var ka = a.perRating.tm.pct_AB, kb = b.perRating.tm.pct_AB;
    if (ka !== kb) return kb - ka;
    var k2a = a.perRating.thematic.pct_AB, k2b = b.perRating.thematic.pct_AB;
    if (k2a !== k2b) return k2b - k2a;
    var k3a = a.perRating.fund_chg.pct_AB, k3b = b.perRating.fund_chg.pct_AB;
    if (k3a !== k3b) return k3b - k3a;
    return (a.groupName || "").localeCompare(b.groupName || "");
  });
  return out;
}

function SUM_heatmapCellColor(pct) {
  if (pct <= 0) return "background:#fafafa";
  var t = Math.min(pct, 1), alpha = 0.05 + t * 0.60;
  return "background:rgba(56,161,105," + alpha.toFixed(2) + ")";
}

function SUM_renderHeatmapMatrix(rows, title, maxVisibleRows, anchorId) {
  var h = '<div class="summary-section" style="margin:16px 12px" id="' + anchorId + '">';
  h += '<div style="font-size:13px;font-weight:700;color:var(--text-primary);margin-bottom:6px">' + title + '</div>';
  var wrapStyle = '';
  if (maxVisibleRows) wrapStyle = 'style="max-height:' + (maxVisibleRows*28+60) + 'px;overflow-y:auto;border:1px solid var(--border)"';
  h += '<div class="ind-sec-wrap" ' + wrapStyle + '>';
  h += '<table class="data-table" style="width:100%;table-layout:fixed">';
  h += '<colgroup><col style="width:30%">';
  for (var c = 0; c < 6; c++) h += '<col style="width:11.66%">';
  h += '</colgroup>';
  h += '<thead style="position:sticky;top:0;background:var(--bg-primary);z-index:2"><tr>';
  h += '<th style="background:rgba(100,100,100,0.06);text-align:left;padding:6px 8px;font-size:11px">' + title.replace(" flow","").replace(/s$/,"") + '</th>';
  for (var ri = 0; ri < SUM_RATINGS.length; ri++) h += '<th style="background:rgba(100,100,100,0.06);font-size:10px;font-weight:700;text-align:center;padding:6px 4px">' + SUM_RATING_SHORT[SUM_RATINGS[ri]] + '</th>';
  h += '</tr></thead><tbody>';
  for (var rr = 0; rr < rows.length; rr++) {
    var row = rows[rr];
    h += '<tr>';
    var nameAttr = row.groupName.replace(/'/g,"&#39;").replace(/"/g,"&quot;");
    h += '<td style="padding:4px 8px;font-size:11px;font-weight:600;color:var(--text-primary);cursor:default" title="' + nameAttr + ' (' + row.total + ' stocks)">' + row.groupName + ' <span style="color:var(--text-secondary);font-weight:400">(' + row.total + ')</span></td>';
    for (var rj = 0; rj < SUM_RATINGS.length; rj++) {
      var rid = SUM_RATINGS[rj], pr = row.perRating[rid], pct = pr.pct_AB;
      var color = SUM_heatmapCellColor(pct);
      var pctStr = pct > 0 ? Math.round(pct*100) + "%" : "-";
      var ttl = SUM_RATING_LABELS[rid] + ": A=" + pr.A + " B=" + pr.B + " C=" + pr.C + " D=" + pr.D + " F=" + pr.F + " of " + row.total;
      h += '<td style="text-align:center;padding:4px;font-family:Menlo,monospace;font-size:11px;font-weight:600;' + color + '" title="' + ttl + '">' + pctStr + '</td>';
    }
    h += '</tr>';
  }
  h += '</tbody></table></div></div>';
  return h;
}

function SUM_renderIndustriesFlow() { return SUM_renderHeatmapMatrix(SUM_buildGroupAggregates("industry"), "Industries flow", null, "sum-industries"); }
function SUM_renderSectorsFlow()    { return SUM_renderHeatmapMatrix(SUM_buildGroupAggregates("sector"),   "Sectors flow",    15,   "sum-sectors"); }


function SUM_renderQualifiedStocks() {
  // Build rows with all fields per stock
  var rows = [];
  for (var pi = 0; pi < D.prices.length; pi++) {
    var p = D.prices[pi];
    var mr = masterRatingsMap[p.ticker];
    if (!mr) continue;
    // Apply 6 master rating filters AND-combined
    var keep = true;
    for (var ri = 0; ri < SUM_RATINGS.length; ri++) {
      if (!SUM_passesFilter(mr[SUM_RATINGS[ri]], summaryFilters[SUM_RATINGS[ri]])) { keep = false; break; }
    }
    if (!keep) continue;

    var tax = SUM_getTaxonomy(p.ticker);
    var fm = (typeof filterMap !== "undefined") ? filterMap[p.ticker] : null;

    // TM stage statuses
    var stages = {};
    for (var sc = 0; sc < SUM_STAGE_COLS.length; sc++) {
      var sid = SUM_STAGE_COLS[sc].id;
      stages[sid] = (fm && fm[sid] && fm[sid].stage) ? fm[sid].stage : null;
    }

    // RS values
    var rsVals = {
      rs_percentile:    (p.rs_percentile != null) ? p.rs_percentile : null,
      rs_vs_sector:     (p.rs_vs_sector != null) ? p.rs_vs_sector : null,
      rs_vs_industry:   (p.rs_vs_industry != null) ? p.rs_vs_industry : null,
      rs_excess_market: (p.rs_excess_market != null) ? p.rs_excess_market : null
    };

    // SSEM per-timeframe totals
    var ssemTotals = {};
    var ssData = (D.ssem && D.ssem[p.ticker]) ? D.ssem[p.ticker] : null;
    var ssemGrand = 0, ssemHasAny = false;
    for (var ti = 0; ti < SUM_SSEM_TIMEFRAMES.length; ti++) {
      var tf = SUM_SSEM_TIMEFRAMES[ti];
      var t = SUM_ssemTimeframeTotal(ssData, tf);
      ssemTotals[tf] = t;
      if (t != null) { ssemGrand += t; ssemHasAny = true; }
    }
    ssemTotals.total = ssemHasAny ? ssemGrand : null;

    // Valuation
    var vl = (D.valuation && D.valuation[p.ticker]) ? D.valuation[p.ticker] : null;
    var valData = {
      pctile:   (vl && vl.pe_percentile != null) ? vl.pe_percentile : null,
      cur:      (vl && vl.pe_current != null) ? vl.pe_current : null,
      lo:       (vl && vl.pe_10y_low != null) ? vl.pe_10y_low : null,
      hi:       (vl && vl.pe_10y_high != null) ? vl.pe_10y_high : null
    };

    rows.push({
      ticker: p.ticker,
      company: p.company_name || p.ticker,
      industry: tax.industry || "",
      sector: tax.sector || "",
      mr: mr,
      stages: stages,
      rs: rsVals,
      ssem: ssemTotals,
      val: valData
    });
  }

  // Default 6-key cascade sort
  rows.sort(function(a,b){
    for (var k = 0; k < SUM_RATINGS.length; k++) {
      var rid = SUM_RATINGS[k];
      var ka = SUM_ratingSortKey(a.mr[rid]), kb = SUM_ratingSortKey(b.mr[rid]);
      if (ka !== kb) return kb - ka;
    }
    return (a.ticker || "").localeCompare(b.ticker || "");
  });

  // Optional sector grouping
  if (summarySectorGrouping) {
    rows.sort(function(a,b){
      var sa = a.sector || "zz_no_sector", sb = b.sector || "zz_no_sector";
      if (sa !== sb) return sa.localeCompare(sb);
      for (var k = 0; k < SUM_RATINGS.length; k++) {
        var rid = SUM_RATINGS[k];
        var ka = SUM_ratingSortKey(a.mr[rid]), kb = SUM_ratingSortKey(b.mr[rid]);
        if (ka !== kb) return kb - ka;
      }
      return (a.ticker || "").localeCompare(b.ticker || "");
    });
  }

  var h = '<div class="summary-section" style="margin:16px 12px" id="sum-qualified">';
  h += '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px">';
  h += '<div style="font-size:13px;font-weight:700;color:var(--text-primary)">Qualified Stocks</div>';
  h += '<div style="font-size:11px;color:var(--text-secondary)">' + rows.length + ' stocks pass all active filters</div>';
  h += '</div>';

  h += '<div style="max-height:700px;overflow-y:auto;overflow-x:auto;border:1px solid var(--border);border-radius:4px">';
  h += '<table class="data-table" style="font-size:10px;min-width:2400px">';

  // ROW 1 — Group header
  h += '<thead style="position:sticky;top:0;z-index:5;background:var(--bg-primary)"><tr>';
  h += '<th colspan="4" style="padding:6px 8px;background:#F1EFE8;color:#444441;text-align:left;font-weight:600;font-size:11px;letter-spacing:.3px;border-right:1px solid var(--border)">Inputs</th>';
  h += '<th colspan="12" style="padding:6px 8px;background:#EEEDFE;color:#3C3489;text-align:center;font-weight:600;font-size:11px;letter-spacing:.3px;border-right:1px solid var(--border)">Technical Momentum</th>';
  h += '<th colspan="5" style="padding:6px 8px;background:#E6F1FB;color:#0C447C;text-align:center;font-weight:600;font-size:11px;letter-spacing:.3px;border-right:1px solid var(--border)">SSEM</th>';
  h += '<th colspan="2" style="padding:6px 8px;background:#EAF3DE;color:#27500A;text-align:center;font-weight:600;font-size:11px;letter-spacing:.3px;border-right:1px solid var(--border)">Valuation</th>';
  h += '<th colspan="6" style="padding:6px 8px;background:#FAEEDA;color:#633806;text-align:center;font-weight:600;font-size:11px;letter-spacing:.3px">Master Ratings</th>';
  h += '</tr>';

  // ROW 2 — Sub-group header
  h += '<tr style="border-top:1px solid var(--border)">';
  h += '<th colspan="4" style="background:var(--bg-primary);border-right:1px solid var(--border)"></th>';
  h += '<th colspan="2" style="padding:4px;background:rgba(238,237,254,0.4);color:#3C3489;text-align:center;font-size:10px;font-weight:600;border-right:1px dashed var(--border)">Stage 1</th>';
  h += '<th colspan="3" style="padding:4px;background:rgba(238,237,254,0.4);color:#3C3489;text-align:center;font-size:10px;font-weight:600;border-right:1px dashed var(--border)">Stage 2</th>';
  h += '<th colspan="1" style="padding:4px;background:rgba(238,237,254,0.4);color:#3C3489;text-align:center;font-size:10px;font-weight:600;border-right:1px dashed var(--border)">Stage 3</th>';
  h += '<th colspan="2" style="padding:4px;background:rgba(238,237,254,0.4);color:#3C3489;text-align:center;font-size:10px;font-weight:600;border-right:1px dashed var(--border)">Stage 4</th>';
  h += '<th colspan="4" style="padding:4px;background:rgba(238,237,254,0.4);color:#3C3489;text-align:center;font-size:10px;font-weight:600;border-right:1px solid var(--border)">Relative Strength</th>';
  h += '<th colspan="5" style="background:var(--bg-primary);border-right:1px solid var(--border)"></th>';
  h += '<th colspan="2" style="background:var(--bg-primary);border-right:1px solid var(--border)"></th>';
  h += '<th colspan="6" style="background:var(--bg-primary)"></th>';
  h += '</tr>';

  // ROW 3 — Column header
  h += '<tr style="border-top:1px solid var(--border);background:rgba(100,100,100,0.04)">';
  h += '<th style="padding:5px 8px;text-align:left;font-size:10px;font-weight:600">Tkr</th>';
  h += '<th style="padding:5px 8px;text-align:left;font-size:10px;font-weight:600">Company</th>';
  h += '<th style="padding:5px 8px;text-align:left;font-size:10px;font-weight:600">Industry</th>';
  h += '<th style="padding:5px 8px;text-align:left;font-size:10px;font-weight:600;border-right:1px solid var(--border)">Sector</th>';
  for (var sc = 0; sc < SUM_STAGE_COLS.length; sc++) {
    var col = SUM_STAGE_COLS[sc];
    var rborder = (col.id === "probing_bet" || col.id === "uptrend_retest" || col.id === "s3_topping") ? "border-right:1px dashed var(--border);" : "";
    if (col.id === "collapse") rborder = "border-right:1px dashed var(--border);";
    h += '<th style="padding:5px 4px;text-align:center;font-size:10px;font-weight:600;' + rborder + '">' + col.label + '</th>';
  }
  for (var rs = 0; rs < SUM_RS_COLS.length; rs++) {
    var rsCol = SUM_RS_COLS[rs];
    var rb = (rs === SUM_RS_COLS.length - 1) ? "border-right:1px solid var(--border);" : "";
    h += '<th style="padding:5px 4px;text-align:center;font-size:10px;font-weight:600;' + rb + '">' + rsCol.label + '</th>';
  }
  for (var tf = 0; tf < SUM_SSEM_TIMEFRAMES.length; tf++) {
    h += '<th style="padding:5px 4px;text-align:center;font-size:10px;font-weight:600">' + SUM_SSEM_TIMEFRAMES[tf].toUpperCase() + '</th>';
  }
  h += '<th style="padding:5px 4px;text-align:center;font-size:10px;font-weight:600;border-right:1px solid var(--border)">Total</th>';
  h += '<th style="padding:5px 4px;text-align:center;font-size:10px;font-weight:600">Pctile</th>';
  h += '<th style="padding:5px 4px;text-align:center;font-size:10px;font-weight:600;border-right:1px solid var(--border)">P/E 10Y Range</th>';
  for (var rr = 0; rr < SUM_RATINGS.length; rr++) {
    h += '<th style="padding:5px 4px;text-align:center;font-size:10px;font-weight:600">' + SUM_RATING_SHORT[SUM_RATINGS[rr]] + '</th>';
  }
  h += '</tr></thead><tbody>';

  // Data rows
  var _prevSector = null;
  var colTotal = 4 + 12 + 5 + 2 + 6;
  for (var rwi = 0; rwi < rows.length; rwi++) {
    var row = rows[rwi];
    if (summarySectorGrouping && row.sector !== _prevSector) {
      var secCount = rows.filter(function(r){return r.sector === row.sector}).length;
      h += '<tr class="group-header-row"><td colspan="' + colTotal + '" style="background:rgba(100,100,100,0.06);font-weight:700;font-size:11px;padding:4px 8px;color:var(--text-primary)">' + (row.sector || "Unknown") + ' <span style="font-weight:400;color:var(--text-secondary)">(' + secCount + ')</span></td></tr>';
      _prevSector = row.sector;
    }
    h += '<tr>';
    h += '<td style="padding:4px 8px;font-size:10px;font-family:Menlo,monospace;font-weight:500">' + row.ticker + '</td>';
    h += '<td style="padding:4px 8px;font-size:10px">' + row.company + '</td>';
    h += '<td style="padding:4px 8px;font-size:9px;color:var(--text-secondary)">' + row.industry + '</td>';
    h += '<td style="padding:4px 8px;font-size:9px;color:var(--text-secondary);border-right:1px solid var(--border)">' + row.sector + '</td>';
    // Stage pills
    for (var sci = 0; sci < SUM_STAGE_COLS.length; sci++) {
      var col2 = SUM_STAGE_COLS[sci];
      var rb2 = (col2.id === "probing_bet" || col2.id === "uptrend_retest" || col2.id === "s3_topping" || col2.id === "collapse") ? "border-right:1px dashed var(--border);" : "";
      h += '<td style="padding:4px;text-align:center;' + rb2 + '">' + SUM_stagePill(row.stages[col2.id]) + '</td>';
    }
    // RS columns
    for (var rsi = 0; rsi < SUM_RS_COLS.length; rsi++) {
      var rsCol2 = SUM_RS_COLS[rsi];
      var v = row.rs[rsCol2.key];
      var style, content;
      if (rsCol2.format === "signedPct") {
        style = SUM_excessBucketStyle(v);
        content = SUM_fmtSignedPct(v);
      } else {
        style = SUM_pctileBucketStyle(v);
        content = (v != null) ? v : "&mdash;";
      }
      var rb3 = (rsi === SUM_RS_COLS.length - 1) ? "border-right:1px solid var(--border);" : "";
      h += '<td style="padding:4px;text-align:center;font-family:Menlo,monospace;font-size:10px;font-weight:600;' + style + rb3 + '">' + content + '</td>';
    }
    // SSEM timeframe cells
    for (var ti2 = 0; ti2 < SUM_SSEM_TIMEFRAMES.length; ti2++) {
      var tfv = row.ssem[SUM_SSEM_TIMEFRAMES[ti2]];
      var st = SUM_signedBucketStyle(tfv);
      h += '<td style="padding:4px;text-align:center;font-family:Menlo,monospace;font-size:10px;font-weight:600;' + st + '">' + SUM_fmtSignedInt(tfv) + '</td>';
    }
    // SSEM Total
    var totSt = SUM_signedBucketStyle(row.ssem.total);
    h += '<td style="padding:4px;text-align:center;font-family:Menlo,monospace;font-size:10px;font-weight:700;border-right:1px solid var(--border);' + totSt + '">' + SUM_fmtSignedInt(row.ssem.total) + '</td>';
    // Valuation percentile
    var valSt = SUM_invPctileBucketStyle(row.val.pctile);
    var valStr = row.val.pctile != null ? Math.round(row.val.pctile) + "%" : "&mdash;";
    h += '<td style="padding:4px;text-align:center;font-family:Menlo,monospace;font-size:10px;font-weight:600;' + valSt + '">' + valStr + '</td>';
    // Valuation sparkline (P/E 10Y range bar) — reuse buildRangeBar
    var sparkContent;
    if (row.val.lo != null && row.val.hi != null && row.val.cur != null && typeof buildRangeBar === "function") {
      sparkContent = buildRangeBar(row.val.lo, row.val.hi, row.val.cur);
    } else {
      sparkContent = '<span style="color:var(--text-tertiary)">&mdash;</span>';
    }
    h += '<td style="padding:4px;text-align:center;border-right:1px solid var(--border)">' + sparkContent + '</td>';
    // Master Ratings
    for (var mri = 0; mri < SUM_RATINGS.length; mri++) {
      var ridM = SUM_RATINGS[mri];
      var isPh = (ridM === "thematic" || ridM === "fund_chg" || ridM === "icbb");
      h += '<td style="padding:4px;text-align:center">' + SUM_ratingPill(row.mr[ridM], isPh) + '</td>';
    }
    h += '</tr>';
  }
  h += '</tbody></table></div></div>';
  return h;
}

/* SUMMARY-TAB-MARKER-END-V12 */


/* MD-V2-STAGE1-MARKER-MODULE-START */
// =============================================================================
// STAGE 1 TAB MODULE — Master Dashboard V2
// =============================================================================
// MD-V2-STAGE1-MARKER — idempotency marker for patcher detection
//
// Locked spec: handoff-2026-05-13-stage1-mockup-signed-off.md
// Mockup source of truth: PROJECTS/SA - Master Dashboard/mockups/stage1-tab-mockup-v8.html
//
// Reads from MASTER_DATA at render time:
//   - MASTER_DATA.stocks[i].md_v2.stage_1 — pre-computed by _md_v2_screens.py
//   - MASTER_DATA.stocks[i].md_v2.persistence.stage_1_persistence — 12-month bar array
//   - MASTER_DATA.prices[ticker] — price, MAs, high/low, MoM rates, higher_lows count
//   - MASTER_DATA.positions.investments — live position list
//
// Rating thresholds (per D-MD-V2-13, no double-weight bonus):
//   Possible = 2/8, Plausible = 3/8, Probable Early = 4/8, Probable Late = 5+/8
//
// Universal MD V2 tab pattern (D-MD-V2-15):
//   nav strip · controls (Inputs/Tests/Scope/Colour by/Portfolio tint) ·
//   5 rating tiles (faded→bold L→R) · 4 group captions · sticky thead table ·
//   sortable cols (mode-aware) · positional pips · qualification persistence ·
//   conditional colour-coding · portfolio tint right-edge
// =============================================================================

/* MD-V2-STAGE1-MARKER-START */

(function() {
  'use strict';

  // ===== State =====
  var s1State = {
    mode: { inputs: 'pct', tests: 'tick' },
    scope: 'all',
    ratingFilter: [],
    tint: 'none',     // none | industry | sector
    port: 'off',      // off | on
    sort: { col: 'count', dir: 'desc' }
  };

  // ===== Column definitions =====
  // MD-V2-S55-S1-COLS-REWRITE: G1 = long-term gate, G2 = short-term gate + 1M/3M+ stack streak
  var S1_COLS = [
    { id:'name',      label:'Company · Ticker',              sortKey:'company', cls:'name-cell' },
    { id:'taxon',     label:'Industry · Sector',             sortKey:'sector', cls:'taxon' },
    { id:'price',     label:'Price',                         sortKey:'price', cls:'num' },
    { id:'high_52w',  label:'52 week high',                  sortKey:'high_52w', cls:'num' },
    { id:'low_52w',   label:'52 week low',                   sortKey:'low_52w', cls:'num' },
    { id:'ma_150',    label:'150D MA',        sortKey:'ma_150', cls:'num' },
    { id:'ma_200',    label:'200D MA',        sortKey:'ma_200', cls:'num' },
    { id:'rating',    label:'Rating',                        sortKey:'rating_rank', cls:'grp-start-rating' },
    { id:'streak',    label:'Stack streak (days)',      sortKey:'streak', cls:'' },
    { id:'g200D',     label:'1. 200D MA still declining (gate)',sortKey:'gate_200D', cls:'grp-start-g1 grp-end-g1', colType:'gate', gateField:'gate_200D' },
    { id:'gp150',     label:'2. Price above 150D MA (gate)',sortKey:'gate_p150', cls:'grp-start-g2', colType:'gate', gateField:'gate_p150' },
    { id:'stack_1m',  label:'3. 50D > 150D and 150D > 200D for 1M',sortKey:'stack_1m_pass', cls:'', colType:'streak_thresh', threshold:21 },
    { id:'stack_3m',  label:'4. 50D > 150D and 150D > 200D for 3M+',sortKey:'stack_3m_pass', cls:'grp-end-g2', colType:'streak_thresh', threshold:63 },
    { id:'sec_in_ind',label:'# sectors in industry',        sortKey:'sectors_in_industry', cls:'grp-start-g3', colType:'count', countKey:'sectors_in_industry', countRedAt:2, countAmberAt:4 },
    { id:'co_in_sec', label:'# companies in sector',        sortKey:'companies_in_sector', cls:'grp-end-g3', colType:'count', countKey:'companies_in_sector', countRedAt:2, countAmberAt:5 },
    { id:'persist',   label:'Last 12 months',               sortKey:'persistence_count', cls:'grp-start-persist' }
  ];

  var S1_RATING_RANK = { 'Probable':5, 'Plausible':3, 'Possible':2, 'None':1 }; // MD-V2-S54-S1-RANK-CLEAN
  var S1_TINT_CLS = { 'Probable':'tint-pl','Plausible':'tint-pla','Possible':'tint-pos','None':'tint-none' };

  // ===== Data accessors =====
  function s1PricesLookup() {
    // MASTER_DATA.prices is an array; build ticker → price record map (cached)
    if (window._s1PricesByTicker) return window._s1PricesByTicker;
    var out = {};
    var arr = (window.MASTER_DATA && MASTER_DATA.prices) || [];
    for (var i = 0; i < arr.length; i++) {
      if (arr[i] && arr[i].ticker) out[arr[i].ticker] = arr[i];
    }
    window._s1PricesByTicker = out;
    return out;
  }
  function s1GetRows() {
    var raw = (window.MASTER_DATA && MASTER_DATA.filters) || [];
    var prices = s1PricesLookup();
    var liveTickers = s1LiveTickers();
    var liveSectors = s1LiveSectors();
    var liveIndustries = s1LiveIndustries();
    var rows = [];
    for (var i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || !s.md_v2 || !s.md_v2.stage_1) continue;
      var p = prices[s.ticker] || {};
      var s1 = s.md_v2.stage_1;
      var pers = (s.md_v2.persistence && s.md_v2.persistence.stage_1_persistence) || [];
      var mas = p.mas || {};
      rows.push({
        ticker: s.ticker,
        company: p.company_name || s.ticker,
        sector: p.sector || '',
        industry: p.industry || '',
        price: p.price,
        high_52w: p.high_52w,
        low_52w: p.low_52w,
        ma_150: mas['150D'],
        ma_200: mas['200D'],
        ma_50:  mas['50D'],
        rating: s1.rating,
        count: s1.count,
        tests: s1.tests || {},
        groups: s1.groups || {},
        persistence: pers,
        is_live: liveTickers[s.ticker] || false,
        sector_in_portfolio: !!liveSectors[p.sector],
        industry_in_portfolio: !!liveIndustries[p.industry],
        // MD-V2-S54 new fields
        streak: s1.streak || 0,
        gate_200D: !!(s1.gate_200D_declining_vs_80d),
        gate_p150: !!(s1.gate_price_above_150D),
        sectors_in_industry: (s.md_v2.sectors_in_industry_count || 0),
        companies_in_sector: (s.md_v2.companies_in_sector_count || 0)
      });
    }
    return rows;
  }

  function s1LiveTickers() {
    var out = {};
    var inv = (window.MASTER_DATA && MASTER_DATA.positions && MASTER_DATA.positions.investments) || [];
    for (var i = 0; i < inv.length; i++) {
      if (inv[i].ticker) out[inv[i].ticker] = true;
    }
    return out;
  }
  function s1LiveSectors() {
    var out = {};
    var tickers = s1LiveTickers();
    var prices = s1PricesLookup();
    for (var t in tickers) {
      var p = prices[t];
      if (p && p.sector) out[p.sector] = true;
    }
    return out;
  }
  function s1LiveIndustries() {
    var out = {};
    var tickers = s1LiveTickers();
    var prices = s1PricesLookup();
    for (var t in tickers) {
      var p = prices[t];
      if (p && p.industry) out[p.industry] = true;
    }
    return out;
  }
  function s1UniverseCounts(rows) {
    // MD-V2-S49-S1-MERGE-PROBABLE-MARKER: Probable Late + Probable Early → single Probable tile
    var c = {'Probable':0,'Plausible':0,'Possible':0,'None':0};
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i].rating;
      if (r === 'Probable Late' || r === 'Probable Early') c['Probable']++;
      else if (c[r] !== undefined) c[r]++;
    }
    return c;
  }

  // ===== Formatters =====
  function s1FmtNum(n) {
    if (n == null || isNaN(n)) return '—';
    var abs = Math.abs(n);
    var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);
    if (Math.abs(n - Math.round(n)) < 1e-9) dp = 0; /* MD-V2-S40-FMTNUM-INT-FIX-s1; S41 tolerance; MD-V2-S41-FMTNUM-NEAR-INTEGER-MARKER */
    var formatted = abs.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });
    return n < 0 ? '(' + formatted + ')' : formatted;
  }
  function s1FmtPct(p) {
    if (p == null || isNaN(p)) return '—';
    var r = Math.round(p);
    var abs = Math.abs(r);
    return r < 0 ? '(' + abs + ')%' : r + '%';
  }
  function s1ReformatPctString(s) {
    if (s == null) return '—';
    if (s.indexOf('/') > -1 && s.indexOf('%') > -1) {
      return s.split('/').map(function(p) { return s1ReformatPctString(p.trim()); }).join(' / ');
    }
    var m = s.match(/^(-?\d+(?:\.\d+)?)%$/);
    if (m) {
      var n = Math.round(parseFloat(m[1]));
      return n < 0 ? '(' + Math.abs(n) + ')%' : n + '%';
    }
    return s;
  }

  function s1ColourForIntensity(i) {
    if (i >= 0.6) return '#0a4012';
    if (i >= 0.25) return '#1f6325';
    if (i >= 0.05) return '#4a8050';
    if (i <= -0.6) return '#8b1a1a';
    if (i <= -0.25) return '#a83232';
    if (i <= -0.05) return '#c66666';
    return '#666';
  }

  // ===== Cell builders =====
  function s1InputCell(row, key, extraCls) {
    extraCls = extraCls || '';
    var v = row[key];
    if (key === 'price') return '<td class="num ' + extraCls + '">' + s1FmtNum(v) + '</td>';
    if (v == null || row.price == null) return '<td class="num ' + extraCls + '">—</td>';
    var pct = (row.price - v) / v * 100;
    var intensity = 0;
    if (key === 'high_52w') {
      intensity = Math.max(-1, Math.min(1, (pct + 20) / 20));
    } else if (key === 'low_52w') {
      intensity = Math.max(-1, Math.min(1, (pct - 20) / 30));
    } else if (key === 'ma_150' || key === 'ma_200') {
      intensity = Math.max(-1, Math.min(1, pct / 10));
    }
    var colour = s1ColourForIntensity(intensity);
    var text = (s1State.mode.inputs === 'pct') ? s1FmtPct(pct) : s1FmtNum(v);
    return '<td class="num ' + extraCls + '" style="color:' + colour + '">' + text + '</td>';
  }

  function s1TestValueFor(row, col) {
    // Compute the actual value to display for this test cell in val mode
    var rates150 = row._ma150_mom || [];
    var rates200 = row._ma200_mom || [];
    var lastRate = function(arr, idx) {
      if (!arr || arr.length < Math.abs(idx)) return null;
      return arr[arr.length + idx];
    };
    if (col.testKey === 'T1_150D') {
      var a = lastRate(rates150, -1), b = lastRate(rates150, -2);
      if (a == null || b == null) return '—';
      return s1FmtPct(a*100) + ' / ' + s1FmtPct(b*100);
    }
    if (col.testKey === 'T2_200D') {
      var a2 = lastRate(rates200, -1), b2 = lastRate(rates200, -2);
      if (a2 == null || b2 == null) return '—';
      return s1FmtPct(a2*100) + ' / ' + s1FmtPct(b2*100);
    }
    if (col.testKey === 'T3') {
      var r = lastRate(rates150, -1);
      return r == null ? '—' : s1FmtPct(r*100);
    }
    if (col.testKey === 'T4') {
      var r2 = lastRate(rates200, -1);
      return r2 == null ? '—' : s1FmtPct(r2*100);
    }
    if (col.testKey === 'T5') {
      if (row.ma_50 == null || row.ma_150 == null) return '—';
      return s1FmtPct(row.ma_50 / row.ma_150 * 100);
    }
    if (col.testKey === 'T6') {
      if (row.ma_150 == null || row.ma_200 == null) return '—';
      return s1FmtPct(row.ma_150 / row.ma_200 * 100);
    }
    if (col.testKey === 'T7' || col.testKey === 'T8') {
      return String(row._higher_lows);
    }
    return '—';
  }

  function s1TestPasses(row, col) {
    var g = row.groups;
    if (col.testGroup === 'g1') {
      if (col.testKey === 'T1_150D') return !!(g.g1_slowing_decline && g.g1_slowing_decline.T1_150D_decelerating);
      if (col.testKey === 'T2_200D') return !!(g.g1_slowing_decline && g.g1_slowing_decline.T2_200D_decelerating);
    } else if (col.testGroup === 'g2') return !!(g.g2_flat_mas && g.g2_flat_mas[col.testKey]);
    else if (col.testGroup === 'g3') return !!(g.g3_stack && g.g3_stack[col.testKey]);
    else if (col.testGroup === 'g4') return !!(g.g4_higher_lows && g.g4_higher_lows[col.testKey]);
    return false;
  }

  function s1TestCell(row, col) {
    // MD-V2-S54: gate and count column types; MD-V2-S55: streak_thresh
    if (col.colType === 'gate') {
      var gpass = !!(row[col.gateField]);
      var gcls = col.cls || '';
      if (gpass) return '<td class="test-pass ' + gcls + '"><span class="tick">✓</span></td>';
      return '<td class="test-fail ' + gcls + '">·</td>';
    }
    if (col.colType === 'streak_thresh') {
      var sVal = row.streak || 0;
      var sPass = sVal >= col.threshold;
      var stCls = col.cls || '';
      if (s1State.mode.tests === 'val') {
        var stCol = sPass ? s1ColourForIntensity(0.7) : s1ColourForIntensity(-0.4);
        return '<td class="test-val ' + stCls + '" style="color:' + stCol + '">' + sVal + 'd</td>';
      }
      if (sPass) return '<td class="test-pass ' + stCls + '"><span class="tick">✓</span></td>';
      return '<td class="test-fail ' + stCls + '">·</td>';
    }
    if (col.colType === 'count') {
      var n = row[col.countKey] || 0;
      var ccls = col.cls || '';
      var cstyle = n <= col.countRedAt ? 'color:#a83232' : (n <= col.countAmberAt ? 'color:#b45309' : 'color:#555');
      return '<td class="num ' + ccls + '" style="' + cstyle + '">' + n + '</td>';
    }
    var pass = s1TestPasses(row, col);
    var extra = col.cls || '';
    if (s1State.mode.tests === 'val') {
      var v = s1ReformatPctString(s1TestValueFor(row, col));
      var colour = pass ? s1ColourForIntensity(0.7) : s1ColourForIntensity(-0.4);
      return '<td class="test-val ' + extra + '" style="color:' + colour + '">' + v + '</td>';
    }
    if (pass) return '<td class="test-pass ' + extra + '"><span class="tick">✓</span></td>';
    return '<td class="test-fail ' + extra + '">·</td>';
  }

  // MD-V2-S54-S1-PILL: plain Probable only
  function s1PillFor(rating, count) {
    if (rating === 'Probable') return '<span class="pill pill-pl-7">Probable</span>';
    if (rating === 'Plausible') return '<span class="pill pill-pla">Plausible</span>';
    if (rating === 'Possible') return '<span class="pill pill-pos">Possible</span>';
    return '<span class="pill pill-none">None</span>';
  }

  function s1ScorePips(row) {
    // MD-V2-S58-GATE-DOTS: gate dots first, then test pips
    var t = row.tests;
    var passed = [
      !!t.T1_150D_decel, !!t.T2_200D_decel,
      !!t.T3_150D_flat,  !!t.T4_200D_flat,
      !!t.T5_50_above_150x97, !!t.T6_150_above_200x97,
      !!t.T7_higher_lows_1m,  !!t.T8_higher_lows_3m
    ];
    var count = passed.filter(Boolean).length;
    var g200D = !!row.gate_200D, gp150 = !!row.gate_p150;
    var s = '<span class="pip ' + (g200D ? 'gate-ok' : 'gate-x') + '"></span>' +
            '<span class="pip ' + (gp150 ? 'gate-ok' : 'gate-x') + '"></span>' +
            '<span class="pip-div"></span>';
    var divAfter = {1:true, 3:true, 5:true};
    for (var i = 0; i < 8; i++) {
      s += '<span class="pip ' + (passed[i] ? 'on' : '') + '"></span>';
      if (divAfter[i]) s += '<span class="pip-div"></span>';
    }
    return '<div class="score-pip-row">' + s + '<span class="score-num">' + count + '/8</span></div>';
  }

  function s1PersistCells(arr, rating) {
    // MD-V2-S49-S1-MERGE-PROBABLE-MARKER: Probable Late and Probable Early both use r-pl (dark green)
    var h = '';
    for (var i = 0; i < 12; i++) {
      if (i === 11 && arr && arr[11]) {
        var cls = rating === 'Probable' ? 'r-pl' :
                  rating === 'Plausible' ? 'r-pla' :
                  rating === 'Possible' ? 'r-pos' : 'r-none'; // MD-V2-S54-S1-PERSIST-CLEAN
        h += '<span class="persist-cell ' + cls + '" title="Current month: ' + rating + '"></span>';
      } else {
        h += '<span class="persist-cell r-none" title="Month -' + (11 - i) + ': not yet backfilled"></span>';
      }
    }
    return '<div class="persist-row">' + h + '</div>';
  }

  // ===== Industry/sector tint palette =====
  function s1HashColor(label, alpha) {
    if (!label) return null;
    var h = 0;
    for (var i = 0; i < label.length; i++) h = (h * 31 + label.charCodeAt(i)) & 0xffff;
    var hue = h % 360;
    return 'hsla(' + hue + ', 35%, 55%, ' + alpha + ')';
  }
  function s1PortfolioInfo(row) {
    if (row.is_live) return { color:'#1b5e20', bg:'rgba(27,94,32,0.10)', bgHover:'rgba(27,94,32,0.14)' };
    if (row.sector_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.05)', bgHover:'rgba(27,94,32,0.08)' };
    if (row.industry_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.025)', bgHover:'rgba(27,94,32,0.05)' };
    return null;
  }

  // ===== Sort =====
  function s1GetSortVal(row, key) {
    if (key === 'rating_rank') return S1_RATING_RANK[row.rating] || 0;
    if (key === 'persistence_count') return (row.persistence || []).filter(Boolean).length;
    if (key === 'g1_150') return row.groups.g1_slowing_decline && row.groups.g1_slowing_decline.T1_150D_decelerating ? 1 : 0;
    if (key === 'g1_200') return row.groups.g1_slowing_decline && row.groups.g1_slowing_decline.T2_200D_decelerating ? 1 : 0;
    if (key === 'g2_t3') return row.groups.g2_flat_mas && row.groups.g2_flat_mas.T3 ? 1 : 0;
    if (key === 'g2_t4') return row.groups.g2_flat_mas && row.groups.g2_flat_mas.T4 ? 1 : 0;
    if (key === 'g3_t5') return row.groups.g3_stack && row.groups.g3_stack.T5 ? 1 : 0;
    if (key === 'g3_t6') return row.groups.g3_stack && row.groups.g3_stack.T6 ? 1 : 0;
    if (key === 'g4_t7') return row.groups.g4_higher_lows && row.groups.g4_higher_lows.T7 ? 1 : 0;
    if (key === 'g4_t8') return row.groups.g4_higher_lows && row.groups.g4_higher_lows.T8 ? 1 : 0;
    if (key === 'stack_1m_pass') return (row.streak || 0) >= 21 ? 1 : 0;
    if (key === 'stack_3m_pass') return (row.streak || 0) >= 63 ? 1 : 0;
    var PCT_KEYS = ['high_52w','low_52w','ma_150','ma_200'];
    if (PCT_KEYS.indexOf(key) > -1 && s1State.mode.inputs === 'pct') {
      var ref = row[key];
      if (ref == null || row.price == null || ref === 0) return -Infinity;
      return (row.price - ref) / ref * 100;
    }
    if (key in row) return row[key];
    return 0;
  }

  function s1OnSort(key) {
    if (s1State.sort.col === key) s1State.sort.dir = s1State.sort.dir === 'desc' ? 'asc' : 'desc';
    else s1State.sort = { col: key, dir: 'desc' };
    s1BuildHeaderRow();
    s1RenderRows();
  }

  // ===== Render: header row =====
  function s1BuildHeaderRow() {
    var tr = document.getElementById('s1-col-header-row');
    if (!tr) return;
    var h = '';
    for (var i = 0; i < S1_COLS.length; i++) {
      var c = S1_COLS[i];
      var isSort = s1State.sort.col === c.sortKey;
      var arrow = isSort
        ? '<span class="sort-arrow">' + (s1State.sort.dir === 'desc' ? '▼' : '▲') + '</span>'
        : '<span class="sort-placeholder"></span>';
      h += '<th class="' + (c.cls || '') + '" data-sort-key="' + c.sortKey + '" title="' + c.label + '">' +
           '<span class="hd"><span class="lbl">' + c.label + '</span>' + arrow + '</span></th>';
    }
    tr.innerHTML = h;
  }

  // ===== Render: rating tiles =====
  function s1RatingTiles(rows) {
    // MD-V2-S49-S1-MERGE-PROBABLE-MARKER: single Probable tile (Late+Early combined)
    var tiles = document.getElementById('s1-rating-tiles');
    if (!tiles) return;
    var uc = s1UniverseCounts(rows);
    var total = rows.length;
    var order = ['None','Possible','Plausible','Probable'];
    var strip = {'Probable':'pl','Plausible':'pla','Possible':'pos','None':'none'};
    var S1_THRESH = {
      'Probable':  'Long-term still down \u00b7 price above 150D MA \u00b7 MA stack held \u22653 months',
      'Plausible': 'Long-term still down \u00b7 price above 150D MA \u00b7 MA stack held \u22651 month',
      'Possible':  'Long-term still down \u00b7 price above 150-day; stack not yet established',
      'None':      'Gate(s) fail \u00b7 no bottoming evidence'
    }; /* MD-V2-S55-PER-TILE-CRITERIA-s1 */
    var h = '';
    for (var i = 0; i < order.length; i++) {
      var r = order[i];
      var cnt = uc[r] || 0;
      var act = s1State.ratingFilter.indexOf(r) > -1 ? ' active' : '';
      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;
      h += '<div class="rating-tile ' + (S1_TINT_CLS[r] || 'tint-none') + act + '" data-rating="' + r + '">' +
           '<div class="rt-label">' + r + '</div>' +
           '<div class="rt-count">' + cnt.toLocaleString('en-GB') + '</div>' +
           '<div class="rt-sub">of ' + total.toLocaleString('en-GB') + ' \u00b7 ' + pct + '%</div>' +
           '<div class="rt-thresh">' + (S1_THRESH[r] || '\u00a0') + '</div>' +
           '<div class="rt-strip rt-strip-' + strip[r] + '"></div>' +
           '</div>';
    }
    tiles.innerHTML = h;
  }

  // ===== Render: scope counts in toggle buttons =====
  function s1UpdateScopeCounts(rows) {
    function setCnt(id, n) { var el = document.getElementById(id); if (el) el.textContent = '(' + n + ')'; }
    setCnt('s1-cnt-all',      rows.length);
    setCnt('s1-cnt-live',     rows.filter(function(r){ return r.is_live; }).length);
    setCnt('s1-cnt-sector',   rows.filter(function(r){ return r.sector_in_portfolio; }).length);
    setCnt('s1-cnt-industry', rows.filter(function(r){ return r.industry_in_portfolio; }).length);
  }

  // ===== Render: rows =====
  function s1RenderRows() {
    var tbody = document.getElementById('s1-tbody');
    if (!tbody) return;
    var allRows = s1GetRows();
    s1UpdateScopeCounts(allRows);
    s1RatingTiles(allRows);

    var rows = allRows.slice();
    if (s1State.scope === 'live') rows = rows.filter(function(r){ return r.is_live; });
    else if (s1State.scope === 'sector') rows = rows.filter(function(r){ return r.sector_in_portfolio; });
    else if (s1State.scope === 'industry') rows = rows.filter(function(r){ return r.industry_in_portfolio; });
    if (s1State.ratingFilter.length > 0) rows = rows.filter(function(r){ return s1State.ratingFilter.indexOf(r.rating) > -1; });

    rows.sort(function(a, b) {
      var va = s1GetSortVal(a, s1State.sort.col), vb = s1GetSortVal(b, s1State.sort.col);
      var cmp;
      if (typeof va === 'string') cmp = va.localeCompare(vb);
      else cmp = (va || 0) - (vb || 0);
      if (cmp === 0) cmp = a.ticker.localeCompare(b.ticker);
      return s1State.sort.dir === 'desc' ? -cmp : cmp;
    });

    var html = '';
    for (var i = 0; i < rows.length; i++) {
      var s = rows[i];
      var styles = [];
      var cls = [];
      if (s1State.tint === 'industry') {
        styles.push('--tint-bg: ' + s1HashColor(s.industry, 0.16));
        cls.push('tint-row');
      } else if (s1State.tint === 'sector') {
        styles.push('--tint-bg: ' + s1HashColor(s.sector, 0.16));
        cls.push('tint-row');
      }
      if (s1State.port === 'on') {
        var pi = s1PortfolioInfo(s);
        if (pi) {
          styles.push('--portfolio-color: ' + pi.color);
          styles.push('--portfolio-bg: ' + pi.bg);
          styles.push('--portfolio-bg-hover: ' + pi.bgHover);
          cls.push('portfolio-band');
          cls.push('portfolio-tint');
        }
      }
      var styleAttr = styles.length ? ' style="' + styles.join(';') + '"' : '';
      var clsAttr = cls.length ? ' class="' + cls.join(' ') + '"' : '';
      var liveDot = s.is_live ? '<span class="live-dot">●</span>' : '';

      html += '<tr' + clsAttr + styleAttr + '>' +
        '<td class="name-cell"><div class="co">' + liveDot + (s.company || s.ticker) + '</div><div class="tk">' + s.ticker + '</div></td>' +
        '<td class="taxon"><div class="ind">' + (s.industry || '') + '</div><div class="sec">' + (s.sector || '') + '</div></td>' +
        s1InputCell(s, 'price') +
        s1InputCell(s, 'high_52w') +
        s1InputCell(s, 'low_52w') +
        s1InputCell(s, 'ma_150') +
        s1InputCell(s, 'ma_200') +
        '<td class="grp-start-rating">' + s1PillFor(s.rating, s.count) + '</td>' +
        '<td class="num">' + (s.streak || 0) + '</td>' +
        s1TestCell(s, S1_COLS[9])  + s1TestCell(s, S1_COLS[10]) +
        s1TestCell(s, S1_COLS[11]) + s1TestCell(s, S1_COLS[12]) +
        s1TestCell(s, S1_COLS[13]) + s1TestCell(s, S1_COLS[14]) +
        '<td class="grp-start-persist">' + s1PersistCells(s.persistence, s.rating) + '</td>' +
        '</tr>';
    }
    tbody.innerHTML = html;
  }

  // ===== Controls =====
  function s1SetMode(kind, val) {
    s1State.mode[kind] = val;
    var btns = document.querySelectorAll('button[data-s1-grp="' + kind + '"]');
    for (var i = 0; i < btns.length; i++) {
      btns[i].classList.toggle('active', btns[i].getAttribute('data-s1-val') === val);
    }
    s1RenderRows();
  }
  function s1SetScope(s) {
    s1State.scope = s;
    var btns = document.querySelectorAll('button[data-s1-scope]');
    for (var i = 0; i < btns.length; i++) {
      btns[i].classList.toggle('active', btns[i].getAttribute('data-s1-scope') === s);
    }
    s1RenderRows();
  }
  function s1SetTint(t) {
    s1State.tint = t;
    var btns = document.querySelectorAll('button[data-s1-tint]');
    for (var i = 0; i < btns.length; i++) {
      btns[i].classList.toggle('active', btns[i].getAttribute('data-s1-tint') === t);
    }
    s1RenderRows();
  }
  function s1SetPort(p) {
    s1State.port = p;
    var btns = document.querySelectorAll('button[data-s1-port]');
    for (var i = 0; i < btns.length; i++) {
      btns[i].classList.toggle('active', btns[i].getAttribute('data-s1-port') === p);
    }
    s1RenderRows();
  }
  function s1ToggleRating(r) {
    var _i = s1State.ratingFilter.indexOf(r);
    if (_i > -1) s1State.ratingFilter.splice(_i, 1); else s1State.ratingFilter.push(r);
    s1RenderRows();
  }

  // Expose for inline onclick fallback
  window.s1SetMode = s1SetMode;
  window.s1SetScope = s1SetScope;
  window.s1SetTint = s1SetTint;
  window.s1SetPort = s1SetPort;
  window.s1ToggleRating = s1ToggleRating;
  window.s1OnSort = s1OnSort;

  // ===== Tab HTML scaffold (injected once on first render) =====
  function s1BuildScaffold() {
    var host = document.getElementById('tab-stage_1');
    if (!host) return false;
    if (host.querySelector('#s1-main-table')) return true;  // already built

    var html = '' +
      '<div class="s1-intro">Stage 1 looks for stocks where the long-term trend is <b>still pointing down</b>, but the short-term has begun to trough — the earliest, highest-conviction point at which a future Stage 2 uptrend can be anticipated. Four tests across two groups: <b>(G1)</b> long-term confirmed down so you are not chasing a strong uptrend, and <b>(G2)</b> short-term shows the first signs of bottoming — price above its 150-day MA and the moving-average stack consolidating for 1–3 months.</div>' +
      '<div class="controls s1-controls">' +
        '<div class="ctrl-grp"><span class="ctrl-label">Inputs</span>' +
          '<button class="toggle-btn active" data-s1-grp="inputs" data-s1-val="pct" onclick="s1SetMode(\'inputs\',\'pct\')">show as %</button>' +
          '<button class="toggle-btn" data-s1-grp="inputs" data-s1-val="raw" onclick="s1SetMode(\'inputs\',\'raw\')">show as numbers</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Tests</span>' +
          '<button class="toggle-btn active" data-s1-grp="tests" data-s1-val="tick" onclick="s1SetMode(\'tests\',\'tick\')">show ticks</button>' +
          '<button class="toggle-btn" data-s1-grp="tests" data-s1-val="val" onclick="s1SetMode(\'tests\',\'val\')">show test values</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Scope</span>' +
          '<button class="toggle-btn active" data-s1-scope="all" onclick="s1SetScope(\'all\')">All <span id="s1-cnt-all"></span></button>' +
          '<button class="toggle-btn" data-s1-scope="live" onclick="s1SetScope(\'live\')">Live <span id="s1-cnt-live"></span></button>' +
          '<button class="toggle-btn" data-s1-scope="sector" onclick="s1SetScope(\'sector\')">Sectors <span id="s1-cnt-sector"></span></button>' +
          '<button class="toggle-btn" data-s1-scope="industry" onclick="s1SetScope(\'industry\')">Industries <span id="s1-cnt-industry"></span></button>' +
          '<button class="toggle-btn disabled" title="Definition pending — placeholder">Peers</button>' +
          '<button class="toggle-btn disabled" title="Definition pending — placeholder">Cohorts</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Colour by</span>' +
          '<button class="toggle-btn active" data-s1-tint="none" onclick="s1SetTint(\'none\')">Off</button>' +
          '<button class="toggle-btn" data-s1-tint="industry" onclick="s1SetTint(\'industry\')">Industry</button>' +
          '<button class="toggle-btn" data-s1-tint="sector" onclick="s1SetTint(\'sector\')">Sector</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Portfolio tint</span>' +
          '<button class="toggle-btn active" data-s1-port="off" onclick="s1SetPort(\'off\')">Off</button>' +
          '<button class="toggle-btn" data-s1-port="on" onclick="s1SetPort(\'on\')">On</button>' +
        '</div>' +
      '</div>' +
      '<div class="rating-tiles s1-rating-tiles" id="s1-rating-tiles" style="grid-template-columns: repeat(4, 1fr);"></div>' +
      '<div class="group-captions" style="grid-template-columns: repeat(2, 1fr);">' +
        '<div class="gcap gcap-g1"><b>Group 1 · Longer-term trend downwards?</b>Stage 1 only makes sense if we are <span class="db">coming out of a downtrend</span> &mdash; not chasing weakness in an existing uptrend.<span class="intro">One long-term gate:</span><span class="tline"><span class="tnum">(1)</span> Is the <u>200-day MA still declining</u> versus where it sat 80 trading days ago?</span></div>' +
        '<div class="gcap gcap-g2"><b>Group 2 · Short-term trend troughed?</b>Even with the long-term still down, the <span class="db">short-term should show signs of bottoming</span> &mdash; price reclaiming its medium-term MA and the recent MA stack holding.<span class="intro">Three short-term tests:</span><span class="tline"><span class="tnum">(2)</span> Is <u>price above the 150-day MA</u>?</span><span class="tline"><span class="tnum">(3)</span> Has the <u>MA stack (50D>150D>200D) held for at least 1 month</u> (≥21 trading days)?</span><span class="tline"><span class="tnum">(4)</span> Has it <u>held for 3 months or more</u> (≥63 days)?</span></div>' +
      '</div>' +
      '<div class="table-wrap"><div class="v2-hscroll">' +  /* MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER */
        '<table class="data-table" id="s1-main-table">' +
          '<colgroup>' +
            '<col class="c-name"><col class="c-taxon">' +
            '<col class="c-price"><col class="c-52wh"><col class="c-52wl">' +
            '<col class="c-ma150"><col class="c-ma200">' +
            '<col class="c-rating"><col class="c-score">' +
            '<col class="c-test">' +
            '<col class="c-test"><col class="c-test"><col class="c-test">' +
            '<col class="c-test"><col class="c-test">' +
            '<col class="c-persist">' +
          '</colgroup>' +
          '<thead>' +
            '<tr class="group-header-row">' +
              '<th class="gh-inputs" colspan="7">Inputs</th>' +
              '<th class="gh-rating grp-start-rating" colspan="2">Stage 1 rating</th>' /* MD-V2-S55-gh-s1 */ +
              '<th class="gh-g1 grp-start-g1 grp-end-g1" colspan="1">Group 1 — Longer-term trend downwards?</th>' +
              '<th class="gh-g2 grp-start-g2 grp-end-g2" colspan="3">Group 2 — Short-term trend troughed?</th>' +
              '<th class="gh-g3 grp-start-g3 grp-end-g3" colspan="2">Group 3 — Taxonomy context?</th>' +
              '<th class="gh-persist grp-start-persist" colspan="1">Stage Qualification persistence</th>' +
            '</tr>' +
            '<tr class="col-header-row" id="s1-col-header-row"></tr>' +
          '</thead>' +
          '<tbody id="s1-tbody"></tbody>' +
        '</table>' +
      '</div></div>';  /* MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER */

    host.innerHTML = html;

    // Wire up rating tile click delegation
    var tiles = document.getElementById('s1-rating-tiles');
    if (tiles) {
      tiles.addEventListener('click', function(e) {
        var tile = e.target.closest('.rating-tile');
        if (!tile) return;
        var r = tile.getAttribute('data-rating');
        if (r) s1ToggleRating(r);
      });
    }
    // Wire up sort header click delegation
    var hdr = document.getElementById('s1-col-header-row');
    if (hdr) {
      hdr.addEventListener('click', function(e) {
        var th = e.target.closest('th');
        if (!th) return;
        var key = th.getAttribute('data-sort-key');
        if (key) s1OnSort(key);
      });
    }
    return true;
  }

  // ===== Public entry point =====
  function renderStage1() {
    if (!s1BuildScaffold()) return;
    s1BuildHeaderRow();
    s1RenderRows();
    if (window.measureV2Ribbon) measureV2Ribbon();  /* MD-V2-WAVE1B-STICKY-CORRECTIVE-MARKER */
  }
  window.renderStage1 = renderStage1;

})();

/* MD-V2-STAGE1-MARKER-END */

/* MD-V2-STAGE1-MARKER-MODULE-END */


/* MD-V2-STAGE2-MARKER-MODULE-START */
// =============================================================================
// STAGE 2 TAB MODULE — Master Dashboard V2
// =============================================================================
// MD-V2-STAGE2-MARKER — idempotency marker for patcher detection
//
// Stage 2 = Confirmed uptrend. 10 tests across 5 groups.
// Ratings: None (<5) / Possible (5) / Plausible (6) / Probable (7+).
// =============================================================================

/* MD-V2-STAGE2-MARKER-START */

(function() {
  'use strict';

  var s2State = {
    mode: { inputs: 'pct', tests: 'tick' },
    scope: 'all', ratingFilter: [], tint: 'none', port: 'off',
    sort: { col: 'count', dir: 'desc' }
  };

  // MD-V2-S55-S2-COLS-REWRITE: G1 long-term, G2 mid-term, G3 short-term, G4 RS, G5 taxonomy
  var S2_COLS = [
    { id:'name',      label:'Company · Ticker',              sortKey:'company', cls:'name-cell' },
    { id:'taxon',     label:'Industry · Sector',             sortKey:'sector', cls:'taxon' },
    { id:'price',     label:'Price',                         sortKey:'price', cls:'num' },
    { id:'high_52w',  label:'52 week high',                  sortKey:'high_52w', cls:'num' },
    { id:'low_52w',   label:'52 week low',                   sortKey:'low_52w', cls:'num' },
    { id:'ma_150',    label:'150D MA',        sortKey:'ma_150', cls:'num' },
    { id:'ma_200',    label:'200D MA',        sortKey:'ma_200', cls:'num' },
    { id:'rating',    label:'Rating',                        sortKey:'rating_rank', cls:'grp-start-rating' },
    { id:'count',     label:'Score',                         sortKey:'count', cls:'' },
    { id:'gp200',     label:'1. Price above 200D MA (gate)', sortKey:'gate_gp200', cls:'grp-start-g1', testGroup:'_gates', testKey:'g1_P_above_200D' },
    { id:'g150_200',  label:'2. 150D MA above 200D MA (gate)',sortKey:'gate_g150_200', cls:'grp-end-g1', testGroup:'_gates', testKey:'g3_150D_above_200D' },
    { id:'gp150',     label:'3. Price above 150D MA (gate)', sortKey:'gate_gp150', cls:'grp-start-g2', testGroup:'_gates', testKey:'g2_P_above_150D' },
    { id:'g52wh',     label:'4. Within 25% of 52w high (gate)',sortKey:'gate_g52wh', cls:'grp-end-g2', testGroup:'_gates', testKey:'g4_within_25pct_52WH' },
    { id:'t5',        label:'5. 50D MA above 150D MA',       sortKey:'t5_sort', cls:'grp-start-g3', testGroup:'g1_ma_stack', testKey:'T5' },
    { id:'t6',        label:'6. 50D MA above 200D MA',       sortKey:'t6_sort', cls:'grp-end-g3', testGroup:'g1_ma_stack', testKey:'T6' },
    { id:'t7',        label:'7. Industry pct. ≥70',         sortKey:'t7_sort', cls:'grp-start-g4', testGroup:'g2_rs', testKey:'T7' },
    { id:'t8',        label:'8. Sector pct. in industry ≥70',sortKey:'t8_sort', cls:'', testGroup:'g2_rs', testKey:'T8' },
    { id:'t9',        label:'9. Stock vs industry pct. ≥70',     sortKey:'t9_sort', cls:'grp-end-g4', testGroup:'g2_rs', testKey:'T9' },
    { id:'sec_in_ind',label:'# sectors in industry',        sortKey:'sectors_in_industry', cls:'grp-start-g5', colType:'count', countKey:'sectors_in_industry', countRedAt:2, countAmberAt:4 },
    { id:'co_in_sec', label:'# companies in sector',        sortKey:'companies_in_sector', cls:'grp-end-g5', colType:'count', countKey:'companies_in_sector', countRedAt:2, countAmberAt:5 },
    { id:'persist',   label:'Last 12 months',               sortKey:'persistence_count', cls:'grp-start-persist' }
  ];
  var S2_RATING_RANK = { 'Probable':4, 'Plausible':3, 'Possible':2, 'None':1 };
  var S2_TINT_CLS = { 'Probable':'tint-prob','Plausible':'tint-pla','Possible':'tint-pos','None':'tint-none' };

  function s2PricesLookup() {
    if (window._s2PricesByTicker) return window._s2PricesByTicker;
    var out = {};
    var arr = (window.MASTER_DATA && MASTER_DATA.prices) || [];
    for (var i = 0; i < arr.length; i++) if (arr[i] && arr[i].ticker) out[arr[i].ticker] = arr[i];
    window._s2PricesByTicker = out;
    return out;
  }
  function s2LiveTickers() {
    var out = {};
    var inv = (window.MASTER_DATA && MASTER_DATA.positions && MASTER_DATA.positions.investments) || [];
    for (var i = 0; i < inv.length; i++) if (inv[i].ticker) out[inv[i].ticker] = true;
    return out;
  }
  function s2LiveSectors() {
    var out = {}, t, prices = s2PricesLookup(), tickers = s2LiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.sector) out[p.sector] = true; }
    return out;
  }
  function s2LiveIndustries() {
    var out = {}, t, prices = s2PricesLookup(), tickers = s2LiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.industry) out[p.industry] = true; }
    return out;
  }
  function s2GetRows() {
    var raw = (window.MASTER_DATA && MASTER_DATA.filters) || [];
    var prices = s2PricesLookup();
    var live = s2LiveTickers(), liveS = s2LiveSectors(), liveI = s2LiveIndustries();
    var rows = [];
    for (var i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || !s.md_v2 || !s.md_v2.stage_2) continue;
      var p = prices[s.ticker] || {};
      var s2 = s.md_v2.stage_2;
      var pers = (s.md_v2.persistence && s.md_v2.persistence.stage_2_persistence) || [];
      var mas = p.mas || {};
      // MD-V2-S54: merge gates into groups as _gates, add count fields
      var s2grps = {}; var s2gsrc = s2.groups || {};
      for (var _k2 in s2gsrc) s2grps[_k2] = s2gsrc[_k2];
      if (s2.gates) s2grps._gates = s2.gates;
      rows.push({
        ticker: s.ticker, company: p.company_name || s.ticker,
        sector: p.sector || '', industry: p.industry || '',
        price: p.price, high_52w: p.high_52w, low_52w: p.low_52w,
        ma_50: mas['50D'], ma_150: mas['150D'], ma_200: mas['200D'],
        rating: s2.rating, count: s2.count,
        tests: s2.tests || {}, groups: s2grps, persistence: pers,
        rs_sector: p.rs_vs_sector_pct, rs_industry: p.rs_vs_industry_pct, rs_market: p.rs_market_pct,
        sectors_in_industry: (s.md_v2.sectors_in_industry_count || 0),
        companies_in_sector: (s.md_v2.companies_in_sector_count || 0),
        is_live: !!live[s.ticker],
        sector_in_portfolio: !!liveS[p.sector],
        industry_in_portfolio: !!liveI[p.industry]
      });
    }
    return rows;
  }
  function s2UniverseCounts(rows) {
    var c = {'Probable':0,'Plausible':0,'Possible':0,'None':0};
    for (var i = 0; i < rows.length; i++) if (c[rows[i].rating] !== undefined) c[rows[i].rating]++;
    return c;
  }

  function s2FmtNum(n) {
    if (n == null || isNaN(n)) return '—';
    var abs = Math.abs(n);
    var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);
    if (Math.abs(n - Math.round(n)) < 1e-9) dp = 0; /* MD-V2-S40-FMTNUM-INT-FIX-s2; S41 tolerance */
    var f = abs.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });
    return n < 0 ? '(' + f + ')' : f;
  }
  function s2FmtPct(p) {
    if (p == null || isNaN(p)) return '—';
    var r = Math.round(p), abs = Math.abs(r);
    return r < 0 ? '(' + abs + ')%' : r + '%';
  }
  function s2ColourForIntensity(i) {
    if (i >= 0.6) return '#0a4012';
    if (i >= 0.25) return '#1f6325';
    if (i >= 0.05) return '#4a8050';
    if (i <= -0.6) return '#8b1a1a';
    if (i <= -0.25) return '#a83232';
    if (i <= -0.05) return '#c66666';
    return '#666';
  }
  function s2InputCell(row, key, extraCls) {
    extraCls = extraCls || '';
    var v = row[key];
    if (key === 'price') return '<td class="num ' + extraCls + '">' + s2FmtNum(v) + '</td>';
    if (v == null || row.price == null) return '<td class="num ' + extraCls + '">—</td>';
    var pct = (row.price - v) / v * 100;
    var intensity = 0;
    if (key === 'high_52w') intensity = Math.max(-1, Math.min(1, (pct + 20) / 20));
    else if (key === 'low_52w') intensity = Math.max(-1, Math.min(1, (pct - 20) / 30));
    else if (key === 'ma_150' || key === 'ma_200') intensity = Math.max(-1, Math.min(1, pct / 10));
    var colour = s2ColourForIntensity(intensity);
    var text = (s2State.mode.inputs === 'pct') ? s2FmtPct(pct) : s2FmtNum(v);
    return '<td class="num ' + extraCls + '" style="color:' + colour + '">' + text + '</td>';
  }

  function s2TestValueFor(row, col) {
    var k = col.testKey;
    if (k === 'T1') return row.price != null && row.ma_200 != null ? s2FmtPct((row.price - row.ma_200) / row.ma_200 * 100) : '—';
    if (k === 'T3') return row.price != null && row.ma_150 != null ? s2FmtPct((row.price - row.ma_150) / row.ma_150 * 100) : '—';
    if (k === 'T4') return row.ma_150 != null && row.ma_200 != null ? s2FmtPct((row.ma_150 - row.ma_200) / row.ma_200 * 100) : '—';
    if (k === 'T5') return row.ma_50 != null && row.ma_150 != null ? s2FmtPct((row.ma_50 - row.ma_150) / row.ma_150 * 100) : '—';
    if (k === 'T6') return row.price != null && row.high_52w != null ? s2FmtPct((row.price - row.high_52w) / row.high_52w * 100) : '—';
    if (k === 'T7') return row.price != null && row.low_52w != null ? s2FmtPct((row.price - row.low_52w) / row.low_52w * 100) : '—';
    if (k === 'T8' && row.rs_sector != null) return Math.round(row.rs_sector) + '';
    if (k === 'T9' && row.rs_industry != null) return Math.round(row.rs_industry) + '';
    if (k === 'T10' && row.rs_market != null) return Math.round(row.rs_market) + '';
    return '—';
  }
  function s2TestCell(row, col) {
    // MD-V2-S54: count column type
    if (col.colType === 'count') {
      var n = row[col.countKey] || 0;
      var ccls = col.cls || '';
      var cstyle = n <= col.countRedAt ? 'color:#a83232' : (n <= col.countAmberAt ? 'color:#b45309' : 'color:#555');
      return '<td class="num ' + ccls + '" style="' + cstyle + '">' + n + '</td>';
    }
    var grp = (row.groups || {})[col.testGroup] || {};
    var pass = !!grp[col.testKey];
    var extra = col.cls || '';
    if (s2State.mode.tests === 'val') {
      var v = s2TestValueFor(row, col);
      var colour = pass ? s2ColourForIntensity(0.7) : s2ColourForIntensity(-0.4);
      return '<td class="test-val ' + extra + '" style="color:' + colour + '">' + v + '</td>';
    }
    if (pass) return '<td class="test-pass ' + extra + '"><span class="tick">✓</span></td>';
    return '<td class="test-fail ' + extra + '">·</td>';
  }

  function s2PillFor(rating, count) {
    if (rating === 'Probable') {
      var c = Math.min(Math.max(count, 7), 10);
      return '<span class="pill pill-prob-' + c + '">Probable</span>';
    }
    if (rating === 'Plausible') return '<span class="pill pill-pla">Plausible</span>';
    if (rating === 'Possible') return '<span class="pill pill-pos">Possible</span>';
    return '<span class="pill pill-none">None</span>';
  }
  // MD-V2-S58-S2-PIPS: gate dots + 5 tests (T5-T9)
  function s2ScorePips(row) {
    var t = row.tests;
    var passed = [
      !!t.T5_50D_above_150D, !!t.T6_50D_above_200D,
      !!t.T7_industry_RS_pct_ge70, !!t.T8_sector_RS_pct_ge70, !!t.T9_stock_RS_vs_industry_ge70
    ];
    var count = passed.filter(Boolean).length;
    var gates = (row.groups && row.groups._gates) || {};
    var s = '<span class="pip ' + (gates.g1_P_above_200D ? 'gate-ok' : 'gate-x') + '"></span>' +
            '<span class="pip ' + (gates.g3_150D_above_200D ? 'gate-ok' : 'gate-x') + '"></span>' +
            '<span class="pip ' + (gates.g2_P_above_150D ? 'gate-ok' : 'gate-x') + '"></span>' +
            '<span class="pip ' + (gates.g4_within_25pct_52WH ? 'gate-ok' : 'gate-x') + '"></span>' +
            '<span class="pip-div"></span>';
    var divAfter = {1:true};
    var rsIdx = {2:true, 3:true, 4:true};
    for (var i = 0; i < 5; i++) {
      var cls = passed[i] ? (rsIdx[i] ? 'rs-on' : 'on') : '';
      s += '<span class="pip ' + cls + '"></span>';
      if (divAfter[i]) s += '<span class="pip-div"></span>';
    }
    return '<div class="score-pip-row">' + s + '<span class="score-num">' + count + '/5</span></div>';
  }
  function s2PersistCells(arr, rating) {
    var h = '';
    for (var i = 0; i < 12; i++) {
      if (i === 11 && arr && arr[11]) {
        var cls = rating === 'Probable' ? 'r-prob' :
                  rating === 'Plausible' ? 'r-pla' :
                  rating === 'Possible' ? 'r-pos' : 'r-none';
        h += '<span class="persist-cell ' + cls + '" title="Current month: ' + rating + '"></span>';
      } else {
        h += '<span class="persist-cell r-none" title="Month -' + (11 - i) + ': not yet backfilled"></span>';
      }
    }
    return '<div class="persist-row">' + h + '</div>';
  }

  function s2HashColor(label, alpha) {
    if (!label) return null;
    var h = 0;
    for (var i = 0; i < label.length; i++) h = (h * 31 + label.charCodeAt(i)) & 0xffff;
    return 'hsla(' + (h % 360) + ', 35%, 55%, ' + alpha + ')';
  }
  function s2PortfolioInfo(row) {
    if (row.is_live) return { color:'#1b5e20', bg:'rgba(27,94,32,0.10)', bgHover:'rgba(27,94,32,0.14)' };
    if (row.sector_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.05)', bgHover:'rgba(27,94,32,0.08)' };
    if (row.industry_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.025)', bgHover:'rgba(27,94,32,0.05)' };
    return null;
  }

  function s2GetSortVal(row, key) {
    if (key === 'rating_rank') return S2_RATING_RANK[row.rating] || 0;
    if (key === 'persistence_count') return (row.persistence || []).filter(Boolean).length;
    if (key.indexOf('g') === 0 && key.indexOf('_t') > 0) {
      var col = S2_COLS.find(function(c) { return c.sortKey === key; });
      if (col) {
        var grp = (row.groups || {})[col.testGroup] || {};
        return grp[col.testKey] ? 1 : 0;
      }
    }
    var PCT_KEYS = ['high_52w','low_52w','ma_150','ma_200'];
    if (PCT_KEYS.indexOf(key) > -1 && s2State.mode.inputs === 'pct') {
      var ref = row[key];
      if (ref == null || row.price == null || ref === 0) return -Infinity;
      return (row.price - ref) / ref * 100;
    }
    if (key in row) return row[key];
    return 0;
  }
  function s2OnSort(key) {
    if (s2State.sort.col === key) s2State.sort.dir = s2State.sort.dir === 'desc' ? 'asc' : 'desc';
    else s2State.sort = { col: key, dir: 'desc' };
    s2BuildHeaderRow();
    s2RenderRows();
  }

  function s2BuildHeaderRow() {
    var tr = document.getElementById('s2-col-header-row');
    if (!tr) return;
    var h = '';
    for (var i = 0; i < S2_COLS.length; i++) {
      var c = S2_COLS[i];
      var isSort = s2State.sort.col === c.sortKey;
      var arrow = isSort
        ? '<span class="sort-arrow">' + (s2State.sort.dir === 'desc' ? '▼' : '▲') + '</span>'
        : '<span class="sort-placeholder"></span>';
      h += '<th class="' + (c.cls || '') + '" data-sort-key="' + c.sortKey + '" title="' + c.label + '">' +
           '<span class="hd"><span class="lbl">' + c.label + '</span>' + arrow + '</span></th>';
    }
    tr.innerHTML = h;
  }
  function s2RatingTiles(rows) {
    var tiles = document.getElementById('s2-rating-tiles');
    if (!tiles) return;
    var uc = s2UniverseCounts(rows);
    var total = rows.length;
    var order = ['None','Possible','Plausible','Probable'];
    var strip = {'Probable':'prob','Plausible':'pla','Possible':'pos','None':'none'};
    var S2_THRESH = {
      'Probable':  '4-5 of 5 tests · 4 hard gates pass · MA stack + RS both strong',
      'Plausible': '3 of 5 tests · gates pass · most uptrend conditions met',
      'Possible':  '2 of 5 tests · gates pass · partial uptrend signals',
      'None':      'Gate fail or fewer than 2 test signals'
    }; /* MD-V2-S49-PER-TILE-CRITERIA-s2 */
    var h = '';
    for (var i = 0; i < order.length; i++) {
      var r = order[i], cnt = uc[r] || 0;
      var act = s2State.ratingFilter.indexOf(r) > -1 ? ' active' : '';
      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;
      h += '<div class="rating-tile ' + S2_TINT_CLS[r] + act + '" data-rating="' + r + '">' +
           '<div class="rt-label">' + r + '</div>' +
           '<div class="rt-count">' + cnt.toLocaleString('en-GB') + '</div>' +
           '<div class="rt-sub">of ' + total.toLocaleString('en-GB') + ' · ' + pct + '%</div>' +
           '<div class="rt-thresh">' + (S2_THRESH[r] || '\u00a0') + '</div>' +
           '<div class="rt-strip rt-strip-' + strip[r] + '"></div>' +
           '</div>';
    }
    tiles.innerHTML = h;
  }
  function s2UpdateScopeCounts(rows) {
    function set(id, n) { var el = document.getElementById(id); if (el) el.textContent = '(' + n + ')'; }
    set('s2-cnt-all',      rows.length);
    set('s2-cnt-live',     rows.filter(function(r){ return r.is_live; }).length);
    set('s2-cnt-sector',   rows.filter(function(r){ return r.sector_in_portfolio; }).length);
    set('s2-cnt-industry', rows.filter(function(r){ return r.industry_in_portfolio; }).length);
  }

  function s2RenderRows() {
    var tbody = document.getElementById('s2-tbody');
    if (!tbody) return;
    var all = s2GetRows();
    s2UpdateScopeCounts(all);
    s2RatingTiles(all);
    var rows = all.slice();
    if (s2State.scope === 'live') rows = rows.filter(function(r){ return r.is_live; });
    else if (s2State.scope === 'sector') rows = rows.filter(function(r){ return r.sector_in_portfolio; });
    else if (s2State.scope === 'industry') rows = rows.filter(function(r){ return r.industry_in_portfolio; });
    if (s2State.ratingFilter.length > 0) rows = rows.filter(function(r){ return s2State.ratingFilter.indexOf(r.rating) > -1; });
    rows.sort(function(a,b) {
      var va = s2GetSortVal(a, s2State.sort.col), vb = s2GetSortVal(b, s2State.sort.col);
      var cmp = (typeof va === 'string') ? va.localeCompare(vb) : (va || 0) - (vb || 0);
      if (cmp === 0) cmp = a.ticker.localeCompare(b.ticker);
      return s2State.sort.dir === 'desc' ? -cmp : cmp;
    });
    var html = '';
    for (var i = 0; i < rows.length; i++) {
      var s = rows[i];
      var styles = [], cls = [];
      if (s2State.tint === 'industry') { styles.push('--tint-bg: ' + s2HashColor(s.industry, 0.16)); cls.push('tint-row'); }
      else if (s2State.tint === 'sector') { styles.push('--tint-bg: ' + s2HashColor(s.sector, 0.16)); cls.push('tint-row'); }
      if (s2State.port === 'on') {
        var pi = s2PortfolioInfo(s);
        if (pi) {
          styles.push('--portfolio-color: ' + pi.color);
          styles.push('--portfolio-bg: ' + pi.bg);
          styles.push('--portfolio-bg-hover: ' + pi.bgHover);
          cls.push('portfolio-band'); cls.push('portfolio-tint');
        }
      }
      var styleAttr = styles.length ? ' style="' + styles.join(';') + '"' : '';
      var clsAttr = cls.length ? ' class="' + cls.join(' ') + '"' : '';
      var liveDot = s.is_live ? '<span class="live-dot">●</span>' : '';
      html += '<tr' + clsAttr + styleAttr + '>' +
        '<td class="name-cell"><div class="co">' + liveDot + (s.company || s.ticker) + '</div><div class="tk">' + s.ticker + '</div></td>' +
        '<td class="taxon"><div class="ind">' + (s.industry || '') + '</div><div class="sec">' + (s.sector || '') + '</div></td>' +
        s2InputCell(s, 'price') + s2InputCell(s, 'high_52w') + s2InputCell(s, 'low_52w') +
        s2InputCell(s, 'ma_150') + s2InputCell(s, 'ma_200') +
        '<td class="grp-start-rating">' + s2PillFor(s.rating, s.count) + '</td>' +
        '<td>' + s2ScorePips(s) + '</td>';
      for (var j = 9; j <= 19; j++) html += s2TestCell(s, S2_COLS[j]); // MD-V2-S54
      html += '<td class="grp-start-persist">' + s2PersistCells(s.persistence, s.rating) + '</td>' +
        '</tr>';
    }
    tbody.innerHTML = html;
  }

  function s2SetMode(kind, val) {
    s2State.mode[kind] = val;
    var btns = document.querySelectorAll('button[data-s2-grp="' + kind + '"]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-s2-val') === val);
    s2RenderRows();
  }
  function s2SetScope(s) {
    s2State.scope = s;
    var btns = document.querySelectorAll('button[data-s2-scope]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-s2-scope') === s);
    s2RenderRows();
  }
  function s2SetTint(t) {
    s2State.tint = t;
    var btns = document.querySelectorAll('button[data-s2-tint]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-s2-tint') === t);
    s2RenderRows();
  }
  function s2SetPort(p) {
    s2State.port = p;
    var btns = document.querySelectorAll('button[data-s2-port]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-s2-port') === p);
    s2RenderRows();
  }
  function s2ToggleRating(r) {
    var _i = s2State.ratingFilter.indexOf(r);
    if (_i > -1) s2State.ratingFilter.splice(_i, 1); else s2State.ratingFilter.push(r);
    s2RenderRows();
  }
  window.s2SetMode = s2SetMode;
  window.s2SetScope = s2SetScope;
  window.s2SetTint = s2SetTint;
  window.s2SetPort = s2SetPort;
  window.s2ToggleRating = s2ToggleRating;
  window.s2OnSort = s2OnSort;

  function s2BuildScaffold() {
    var host = document.getElementById('tab-stage_2');
    if (!host) return false;
    if (host.querySelector('#s2-main-table')) return true;
    var html = '' +
      '<div class="s1-intro">Stage 2 looks for stocks already in a clear uptrend &mdash; long, mid, and short-term trends all pointing upwards, and price showing genuine relative strength against sector, industry, and the wider market. The aim is to identify quality holdings to initiate, add to, or hold as core positions. Nine tests across four groups: the more tests passing, the more confirmed the uptrend.</div>' +
      '<div class="controls s1-controls">' +
        '<div class="ctrl-grp"><span class="ctrl-label">Inputs</span>' +
          '<button class="toggle-btn active" data-s2-grp="inputs" data-s2-val="pct" onclick="s2SetMode(\'inputs\',\'pct\')">show as %</button>' +
          '<button class="toggle-btn" data-s2-grp="inputs" data-s2-val="raw" onclick="s2SetMode(\'inputs\',\'raw\')">show as numbers</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Tests</span>' +
          '<button class="toggle-btn active" data-s2-grp="tests" data-s2-val="tick" onclick="s2SetMode(\'tests\',\'tick\')">show ticks</button>' +
          '<button class="toggle-btn" data-s2-grp="tests" data-s2-val="val" onclick="s2SetMode(\'tests\',\'val\')">show test values</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Scope</span>' +
          '<button class="toggle-btn active" data-s2-scope="all" onclick="s2SetScope(\'all\')">All <span id="s2-cnt-all"></span></button>' +
          '<button class="toggle-btn" data-s2-scope="live" onclick="s2SetScope(\'live\')">Live <span id="s2-cnt-live"></span></button>' +
          '<button class="toggle-btn" data-s2-scope="sector" onclick="s2SetScope(\'sector\')">Sectors <span id="s2-cnt-sector"></span></button>' +
          '<button class="toggle-btn" data-s2-scope="industry" onclick="s2SetScope(\'industry\')">Industries <span id="s2-cnt-industry"></span></button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Peers</button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Cohorts</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Colour by</span>' +
          '<button class="toggle-btn active" data-s2-tint="none" onclick="s2SetTint(\'none\')">Off</button>' +
          '<button class="toggle-btn" data-s2-tint="industry" onclick="s2SetTint(\'industry\')">Industry</button>' +
          '<button class="toggle-btn" data-s2-tint="sector" onclick="s2SetTint(\'sector\')">Sector</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Portfolio tint</span>' +
          '<button class="toggle-btn active" data-s2-port="off" onclick="s2SetPort(\'off\')">Off</button>' +
          '<button class="toggle-btn" data-s2-port="on" onclick="s2SetPort(\'on\')">On</button>' +
        '</div>' +
      '</div>' +
      '<div class="rating-tiles s1-rating-tiles" id="s2-rating-tiles" style="grid-template-columns: repeat(4, 1fr);"></div>' +
      '<div class="group-captions" style="grid-template-columns: repeat(4, 1fr);">' +
        '<div class="gcap gcap-g1"><b>Group 1 · Long-term trend upwards?</b>The <span class="db">foundation of a Stage 2 uptrend</span> &mdash; the long-term trend must be pointing up before anything else matters.<span class="intro">Two long-term gates:</span><span class="tline"><span class="tnum">(1)</span> Is price trading <u>above its 200-day MA</u>?</span><span class="tline"><span class="tnum">(2)</span> Is the <u>150-day MA above the 200-day</u>?</span></div>' +
        '<div class="gcap gcap-g2"><b>Group 2 · Mid-term trend upwards?</b>The mid-term should be <span class="db">confirming the longer trend</span> &mdash; price holding above its 150-day MA and within striking distance of its 52-week high.<span class="intro">Two mid-term gates:</span><span class="tline"><span class="tnum">(3)</span> Is price <u>above its 150-day MA</u>?</span><span class="tline"><span class="tnum">(4)</span> Is price <u>within 25% of its 52-week high</u>?</span></div>' +
        '<div class="gcap gcap-g3"><b>Group 3 · Short-term trend upwards?</b>The <span class="db">fastest of the trend signals</span> &mdash; the short-term MAs sit above the longer ones, confirming the stack is the right way up.<span class="intro">Two short-term tests:</span><span class="tline"><span class="tnum">(5)</span> Is the <u>50-day MA above the 150-day</u>?</span><span class="tline"><span class="tnum">(6)</span> Is the <u>50-day MA above the 200-day</u>?</span></div>' +
        '<div class="gcap gcap-g4"><b>Group 4 · Relative strength</b>Is the stock <span class="db">outperforming its peers</span> &mdash; three independent reads on relative strength, not one?<span class="intro">Three relative-strength tests:</span><span class="tline"><span class="tnum">(7)</span> Is industry RS percentile <u>at or above 70</u>?</span><span class="tline"><span class="tnum">(8)</span> Is sector RS percentile within industry <u>at or above 70</u>?</span><span class="tline"><span class="tnum">(9)</span> Is stock RS versus industry <u>at or above 70</u>?</span></div>' +
      '</div>' +
      '<div class="table-wrap"><div class="v2-hscroll">' +  /* MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER */
        '<table class="data-table" id="s2-main-table">' +
          '<colgroup>' +
            '<col class="c-name"><col class="c-taxon">' +
            '<col class="c-price"><col class="c-52wh"><col class="c-52wl">' +
            '<col class="c-ma150"><col class="c-ma200">' +
            '<col class="c-rating"><col class="c-score">' +
            '<col class="c-test"><col class="c-test"><col class="c-test"><col class="c-test">' +
            '<col class="c-test"><col class="c-test">' +
            '<col class="c-test"><col class="c-test"><col class="c-test">' +
            '<col class="c-test"><col class="c-test">' +
            '<col class="c-persist">' +
          '</colgroup>' +
          '<thead>' +
            '<tr class="group-header-row">' +
              '<th class="gh-inputs" colspan="7">Inputs</th>' +
              '<th class="gh-rating grp-start-rating" colspan="2">Stage 2 rating</th>' /* MD-V2-S55-gh-s2 */ +
              '<th class="gh-g1 grp-start-g1 grp-end-g1" colspan="2">Group 1 — Long-term trend upwards?</th>' +
              '<th class="gh-g2 grp-start-g2 grp-end-g2" colspan="2">Group 2 — Mid-term trend upwards?</th>' +
              '<th class="gh-g3 grp-start-g3 grp-end-g3" colspan="2">Group 3 — Short-term trend upwards?</th>' +
              '<th class="gh-g4 grp-start-g4 grp-end-g4" colspan="3">Group 4 — Relative strength?</th>' +
              '<th class="gh-g5 grp-start-g5 grp-end-g5" colspan="2">Group 5 — Taxonomy context?</th>' +
              '<th class="gh-persist grp-start-persist" colspan="1">Stage Qualification persistence</th>' +
            '</tr>' +
            '<tr class="col-header-row" id="s2-col-header-row"></tr>' +
          '</thead>' +
          '<tbody id="s2-tbody"></tbody>' +
        '</table>' +
      '</div></div>';  /* MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER */
    host.innerHTML = html;
    var tiles = document.getElementById('s2-rating-tiles');
    if (tiles) {
      tiles.addEventListener('click', function(e) {
        var tile = e.target.closest('.rating-tile');
        if (!tile) return;
        var r = tile.getAttribute('data-rating');
        if (r) s2ToggleRating(r);
      });
    }
    var hdr = document.getElementById('s2-col-header-row');
    if (hdr) {
      hdr.addEventListener('click', function(e) {
        var th = e.target.closest('th');
        if (!th) return;
        var key = th.getAttribute('data-sort-key');
        if (key) s2OnSort(key);
      });
    }
    return true;
  }

  function renderStage2() {
    if (!s2BuildScaffold()) return;
    s2BuildHeaderRow();
    s2RenderRows();
    if (window.measureV2Ribbon) measureV2Ribbon();  /* MD-V2-WAVE1B-STICKY-CORRECTIVE-MARKER */
  }
  window.renderStage2 = renderStage2;

})();

/* MD-V2-STAGE2-MARKER-END */

/* MD-V2-STAGE2-MARKER-MODULE-END */


/* MD-V2-STAGE3-MARKER-MODULE-START */
// =============================================================================
// STAGE 3 TAB MODULE — Master Dashboard V2
// =============================================================================
// MD-V2-STAGE3-MARKER — idempotency marker for patcher detection
//
// Stage 3 = Topping / Invalidation. 10 tests across 5 groups.
// Ratings:
//   None                     (<2)
//   Possible Topping         (2-3)
//   Plausible Invalidation   (4-5)
//   Probable Invalidation    (6+)
// =============================================================================

/* MD-V2-STAGE3-MARKER-START */

(function() {
  'use strict';

  var s3State = {
    mode: { inputs: 'pct', tests: 'tick' },
    scope: 'all', ratingFilter: [], tint: 'none', port: 'off',
    sort: { col: 'count', dir: 'desc' }
  };

  // MD-V2-S54-S3-COLS-REWRITE
  // MD-V2-S55-S3-COLS-REWRITE
  var S3_COLS = [
    { id:'name',      label:'Company · Ticker',                    sortKey:'company', cls:'name-cell' },
    { id:'taxon',     label:'Industry · Sector',                   sortKey:'sector', cls:'taxon' },
    { id:'price',     label:'Price',                               sortKey:'price', cls:'num' },
    { id:'high_52w',  label:'52 week high',                        sortKey:'high_52w', cls:'num' },
    { id:'low_52w',   label:'52 week low',                         sortKey:'low_52w', cls:'num' },
    { id:'ma_150',    label:'150D MA',              sortKey:'ma_150', cls:'num' },
    { id:'ma_200',    label:'200D MA',              sortKey:'ma_200', cls:'num' },
    { id:'rating',    label:'Rating',                              sortKey:'rating_rank', cls:'grp-start-rating' },
    { id:'count',     label:'Score',                               sortKey:'count', cls:'' },
    { id:'g200D_r',   label:'1. 200D MA still rising vs 80D (gate)',  sortKey:'gate_g200D_r', cls:'grp-start-g1 grp-end-g1', testGroup:'_gates3', testKey:'gate_200D_still_rising_vs_80d' },
    { id:'gp200',     label:'2. Price above 200D MA (gate)',       sortKey:'gate_gp200_s3', cls:'grp-start-g2 grp-end-g2', testGroup:'_gates3', testKey:'gate_price_above_200D' },
    { id:'t3',        label:'3. 2+ bases (504d window)',              sortKey:'t3_s3', cls:'grp-start-g3 grp-end-g3', testGroup:'g1_base_deterioration', testKey:'T3' },
    { id:'t4',        label:'4. 50D MA ≤ 150D MA',            sortKey:'t4_s3', cls:'grp-start-g4', testGroup:'g1_base_deterioration', testKey:'T4' },
    { id:'t5',        label:'5. Down vol > up vol (L20d)',            sortKey:'t5_s3', cls:'', testGroup:'g2_distribution_signals', testKey:'T5' },
    { id:'t6',        label:'6. L1M volatility > P4M',    sortKey:'t6_s3', cls:'', testGroup:'g2_distribution_signals', testKey:'T6' },
    { id:'t7',        label:'7. ≥2 lower lows in last 2 months',     sortKey:'t7_s3', cls:'', testGroup:'g2_distribution_signals', testKey:'T7' },
    { id:'t8',        label:'8. 10%+ lower sector RS L3M', sortKey:'t8_s3', cls:'grp-end-g4', testGroup:'g3_rs_degradation', testKey:'T8' },
    { id:'sec_in_ind',label:'# sectors in industry',               sortKey:'sectors_in_industry', cls:'grp-start-g5', colType:'count', countKey:'sectors_in_industry', countRedAt:2, countAmberAt:4 },
    { id:'co_in_sec', label:'# companies in sector',               sortKey:'companies_in_sector', cls:'grp-end-g5', colType:'count', countKey:'companies_in_sector', countRedAt:2, countAmberAt:5 },
    { id:'persist',   label:'Last 12 months',                      sortKey:'persistence_count', cls:'grp-start-persist' }
  ];
  var S3_RATING_RANK = { 'Probable':4, 'Plausible':3, 'Possible':2, 'None':1, 'Probable Invalidation':4, 'Plausible Invalidation':3, 'Possible Topping':2 };
  var S3_TINT_CLS = {
    'Probable':'tint-prob',
    'Plausible':'tint-pla',
    'Possible':'tint-pos',
    'None':'tint-none',
    'Probable Invalidation':'tint-prob',
    'Plausible Invalidation':'tint-pla',
    'Possible Topping':'tint-pos'
  };

  function s3PricesLookup() {
    if (window._s3PricesByTicker) return window._s3PricesByTicker;
    var out = {};
    var arr = (window.MASTER_DATA && MASTER_DATA.prices) || [];
    for (var i = 0; i < arr.length; i++) if (arr[i] && arr[i].ticker) out[arr[i].ticker] = arr[i];
    window._s3PricesByTicker = out;
    return out;
  }
  function s3LiveTickers() {
    var out = {};
    var inv = (window.MASTER_DATA && MASTER_DATA.positions && MASTER_DATA.positions.investments) || [];
    for (var i = 0; i < inv.length; i++) if (inv[i].ticker) out[inv[i].ticker] = true;
    return out;
  }
  function s3LiveSectors() {
    var out = {}, t, prices = s3PricesLookup(), tickers = s3LiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.sector) out[p.sector] = true; }
    return out;
  }
  function s3LiveIndustries() {
    var out = {}, t, prices = s3PricesLookup(), tickers = s3LiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.industry) out[p.industry] = true; }
    return out;
  }
  function s3GetRows() {
    var raw = (window.MASTER_DATA && MASTER_DATA.filters) || [];
    var prices = s3PricesLookup();
    var live = s3LiveTickers(), liveS = s3LiveSectors(), liveI = s3LiveIndustries();
    var rows = [];
    for (var i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || !s.md_v2 || !s.md_v2.stage_3) continue;
      var p = prices[s.ticker] || {};
      var s3 = s.md_v2.stage_3;
      var pers = (s.md_v2.persistence && s.md_v2.persistence.stage_3_persistence) || [];
      var mas = p.mas || {};
      // MD-V2-S54: merge gate booleans into _gates3 group, add count fields
      var s3grps = {}; var s3gsrc = s3.groups || {};
      for (var _k3 in s3gsrc) s3grps[_k3] = s3gsrc[_k3];
      s3grps._gates3 = {
        gate_200D_still_rising_vs_80d: !!(s3.gate_200D_still_rising_vs_80d),
        gate_price_above_200D: !!(s3.gate_price_above_200D)
      };
      var _s3tv = s3.test_values || {};
      if (_s3tv.T3_base_count_504d != null && s3grps.g1_base_deterioration) {
        s3grps.g1_base_deterioration.T3 = (_s3tv.T3_base_count_504d >= 2);
      }
      rows.push({
        ticker: s.ticker, company: p.company_name || s.ticker,
        sector: p.sector || '', industry: p.industry || '',
        price: p.price, high_52w: p.high_52w, low_52w: p.low_52w,
        ma_50: mas['50D'], ma_150: mas['150D'], ma_200: mas['200D'],
        rating: s3.rating, count: s3.count,
        tests: s3.tests || {}, groups: s3grps, test_values: _s3tv, persistence: pers,
        rs_sector: p.rs_vs_sector_pct, rs_industry: p.rs_vs_industry_pct, rs_market: p.rs_market_pct,
        sectors_in_industry: (s.md_v2.sectors_in_industry_count || 0),
        companies_in_sector: (s.md_v2.companies_in_sector_count || 0),
        is_live: !!live[s.ticker],
        sector_in_portfolio: !!liveS[p.sector],
        industry_in_portfolio: !!liveI[p.industry]
      });
    }
    return rows;
  }
  function s3UniverseCounts(rows) {
    // MD-V2-S55: unify old + new labels into the new buckets for counting
    var c = {'Probable':0,'Plausible':0,'Possible':0,'None':0};
    var _s3map = {'Probable Invalidation':'Probable','Plausible Invalidation':'Plausible','Possible Topping':'Possible'};
    for (var i = 0; i < rows.length; i++) {
      var _r = rows[i].rating;
      var _mapped = _s3map[_r] || _r;
      if (c[_mapped] !== undefined) c[_mapped]++;
    }
    return c;
  }

  function s3FmtNum(n) {
    if (n == null || isNaN(n)) return '—';
    var abs = Math.abs(n);
    var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);
    if (Math.abs(n - Math.round(n)) < 1e-9) dp = 0; /* MD-V2-S40-FMTNUM-INT-FIX-s3; S41 tolerance */
    var f = abs.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });
    return n < 0 ? '(' + f + ')' : f;
  }
  function s3FmtPct(p) {
    if (p == null || isNaN(p)) return '—';
    var r = Math.round(p), abs = Math.abs(r);
    return r < 0 ? '(' + abs + ')%' : r + '%';
  }
  // Stage 3 intensity scale — INVERTED relative to Stage 1/2.
  // Bearish/topping signals are bad → use red colour scale for "passed".
  // Pass colour ramps red; fail stays neutral grey.
  function s3ColourForIntensity(i) {
    if (i >= 0.6) return '#8b1a1a';
    if (i >= 0.25) return '#a83232';
    if (i >= 0.05) return '#c66666';
    if (i <= -0.6) return '#0a4012';
    if (i <= -0.25) return '#1f6325';
    if (i <= -0.05) return '#4a8050';
    return '#666';
  }
  function s3InputCell(row, key, extraCls) {
    extraCls = extraCls || '';
    var v = row[key];
    if (key === 'price') return '<td class="num ' + extraCls + '">' + s3FmtNum(v) + '</td>';
    if (v == null || row.price == null) return '<td class="num ' + extraCls + '">—</td>';
    var pct = (row.price - v) / v * 100;
    // For Stage 3 (topping/invalidation), the bearish interpretation:
    // - Price below 52w high (negative pct vs high) is bearish
    // - Price near 52w low is bearish
    // - Price below 150D / 200D is bearish
    // Intensity: positive = "looks bearish" → red colour via inverted scale.
    var intensity = 0;
    if (key === 'high_52w') intensity = Math.max(-1, Math.min(1, (-pct - 10) / 20));   // below 52w high = bearish
    else if (key === 'low_52w') intensity = Math.max(-1, Math.min(1, (20 - pct) / 30)); // near 52w low = bearish
    else if (key === 'ma_150' || key === 'ma_200') intensity = Math.max(-1, Math.min(1, -pct / 10));
    var colour = s3ColourForIntensity(intensity);
    var text = (s3State.mode.inputs === 'pct') ? s3FmtPct(pct) : s3FmtNum(v);
    return '<td class="num ' + extraCls + '" style="color:' + colour + '">' + text + '</td>';
  }

  function s3TestValueFor(row, col) {
    var k = col.testKey;
    var t = row.tests || {};
    // G1: base counts (binary thresholds — no continuous value, show ✓/✗ only)
    if (k === 'T1' || k === 'T2') return t[k === 'T1' ? 'T1_3_plus_bases' : 'T2_4_plus_bases'] ? 'pass' : 'fail';
    // G2 T3: 200D flattening (binary derived) — no continuous % to show
    if (k === 'T3') return t.T3_200D_flattening ? 'flat' : 'rising';
    // G2 T4: 50D < 150D — show pct gap
    if (k === 'T4') return row.ma_50 != null && row.ma_150 != null ? s3FmtPct((row.ma_50 - row.ma_150) / row.ma_150 * 100) : '—';
    // G3 T5: volume down/up ratio (binary)
    if (k === 'T5') return t.T5_volume_down_up_ratio ? '≥1.1x' : '—';
    // G3 T6: volatility increase (binary)
    if (k === 'T6') return t.T6_volatility_increase ? '≥1.1x' : '—';
    // G3 T7: no breakout — price within 5% of 50D
    if (k === 'T7') return row.price != null && row.ma_50 != null ? s3FmtPct((row.price - row.ma_50) / row.ma_50 * 100) : '—';
    // G4 T8/T9: lower lows counts (binary)
    if (k === 'T8') return t.T8_lower_lows_1m ? '≥2' : '—';
    if (k === 'T9') return t.T9_lower_lows_3m ? '≥3' : '—';
    // G5 T10: RS trend weakening
    if (k === 'T10') return t.T10_RS_trend_weakening ? '< -5%' : '—';
    return '—';
  }
  function s3TestCell(row, col) {
    // MD-V2-S54: count column type
    if (col.colType === 'count') {
      var n = row[col.countKey] || 0;
      var ccls = col.cls || '';
      var cstyle = n <= col.countRedAt ? 'color:#a83232' : (n <= col.countAmberAt ? 'color:#b45309' : 'color:#555');
      return '<td class="num ' + ccls + '" style="' + cstyle + '">' + n + '</td>';
    }
    var grp = (row.groups || {})[col.testGroup] || {};
    var pass = !!grp[col.testKey];
    var extra = col.cls || '';
    if (s3State.mode.tests === 'val') {
      var v = s3TestValueFor(row, col);
      // Stage 3 passes are BEARISH — colour pass red, fail neutral grey
      var colour = pass ? s3ColourForIntensity(0.7) : '#999';
      return '<td class="test-val ' + extra + '" style="color:' + colour + '">' + v + '</td>';
    }
    if (pass) return '<td class="test-pass-bear ' + extra + '"><span class="tick">✓</span></td>';
    return '<td class="test-fail ' + extra + '">·</td>';
  }

  function s3PillFor(rating, count) {
    // MD-V2-S55: collapse old 'Invalidation/Topping' suffixes onto plain labels;
    // CSS palette stays bearish via the existing pill-*-inv / pill-pos-top classes.
    if (rating === 'Probable' || rating === 'Probable Invalidation') {
      var c = Math.min(Math.max(count, 6), 10);
      return '<span class="pill pill-prob-inv-' + c + '">Probable</span>';
    }
    if (rating === 'Plausible' || rating === 'Plausible Invalidation') return '<span class="pill pill-pla-inv">Plausible</span>';
    if (rating === 'Possible' || rating === 'Possible Topping') return '<span class="pill pill-pos-top">Possible</span>';
    return '<span class="pill pill-none">None</span>';
  }
  // MD-V2-S58-S3-PIPS: gate dots + 6 tests; T3 uses 2+ threshold
  function s3ScorePips(row) {
    var t = row.tests, _tv = row.test_values || {};
    var t3pass = (_tv.T3_base_count_504d != null) ? (_tv.T3_base_count_504d >= 2) : !!(t.T3_base_count_504d_ge2 || t.T3_base_count_504d_ge3);
    var passed = [
      t3pass, !!t.T4_50D_below_103pct_150D,
      !!t.T5_down_vol_exceeds_up_vol, !!t.T6_ATR_expansion_ge110, !!t.T7_price_below_50D_and_50D_rolling,
      !!t.T8_sector_RS_drift_gt10pts
    ];
    var count = passed.filter(Boolean).length;
    var g3 = (row.groups && row.groups._gates3) || {};
    var s = '<span class="pip pip-bear ' + (g3.gate_200D_still_rising_vs_80d ? 'gate-ok' : 'gate-x') + '"></span>' +
            '<span class="pip pip-bear ' + (g3.gate_price_above_200D ? 'gate-ok' : 'gate-x') + '"></span>' +
            '<span class="pip-div"></span>';
    var s3DivAfter = {1:true, 4:true};
    for (var i = 0; i < 6; i++) {
      s += '<span class="pip pip-bear ' + (passed[i] ? 'on' : '') + '"></span>';
      if (s3DivAfter[i]) s += '<span class="pip-div"></span>';
    }
    return '<div class="score-pip-row">' + s + '<span class="score-num">' + count + '/6</span></div>';
  }
  function s3PersistCells(arr, rating) {
    var h = '';
    for (var i = 0; i < 12; i++) {
      if (i === 11 && arr && arr[11]) {
        var cls = (rating === 'Probable' || rating === 'Probable Invalidation') ? 'r-prob-inv' :
                  (rating === 'Plausible' || rating === 'Plausible Invalidation') ? 'r-pla-inv' :
                  (rating === 'Possible' || rating === 'Possible Topping') ? 'r-pos-top' : 'r-none';
        h += '<span class="persist-cell ' + cls + '" title="Current month: ' + rating + '"></span>';
      } else {
        h += '<span class="persist-cell r-none" title="Month -' + (11 - i) + ': not yet backfilled"></span>';
      }
    }
    return '<div class="persist-row">' + h + '</div>';
  }

  function s3HashColor(label, alpha) {
    if (!label) return null;
    var h = 0;
    for (var i = 0; i < label.length; i++) h = (h * 31 + label.charCodeAt(i)) & 0xffff;
    return 'hsla(' + (h % 360) + ', 35%, 55%, ' + alpha + ')';
  }
  function s3PortfolioInfo(row) {
    if (row.is_live) return { color:'#1b5e20', bg:'rgba(27,94,32,0.10)', bgHover:'rgba(27,94,32,0.14)' };
    if (row.sector_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.05)', bgHover:'rgba(27,94,32,0.08)' };
    if (row.industry_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.025)', bgHover:'rgba(27,94,32,0.05)' };
    return null;
  }

  function s3GetSortVal(row, key) {
    if (key === 'rating_rank') return S3_RATING_RANK[row.rating] || 0;
    if (key === 'persistence_count') return (row.persistence || []).filter(Boolean).length;
    if (key.indexOf('g') === 0 && key.indexOf('_t') > 0) {
      var col = S3_COLS.find(function(c) { return c.sortKey === key; });
      if (col) {
        var grp = (row.groups || {})[col.testGroup] || {};
        return grp[col.testKey] ? 1 : 0;
      }
    }
    var PCT_KEYS = ['high_52w','low_52w','ma_150','ma_200'];
    if (PCT_KEYS.indexOf(key) > -1 && s3State.mode.inputs === 'pct') {
      var ref = row[key];
      if (ref == null || row.price == null || ref === 0) return -Infinity;
      return (row.price - ref) / ref * 100;
    }
    if (key in row) return row[key];
    return 0;
  }
  function s3OnSort(key) {
    if (s3State.sort.col === key) s3State.sort.dir = s3State.sort.dir === 'desc' ? 'asc' : 'desc';
    else s3State.sort = { col: key, dir: 'desc' };
    s3BuildHeaderRow();
    s3RenderRows();
  }

  function s3BuildHeaderRow() {
    var tr = document.getElementById('s3-col-header-row');
    if (!tr) return;
    var h = '';
    for (var i = 0; i < S3_COLS.length; i++) {
      var c = S3_COLS[i];
      var isSort = s3State.sort.col === c.sortKey;
      var arrow = isSort
        ? '<span class="sort-arrow">' + (s3State.sort.dir === 'desc' ? '▼' : '▲') + '</span>'
        : '<span class="sort-placeholder"></span>';
      h += '<th class="' + (c.cls || '') + '" data-sort-key="' + c.sortKey + '" title="' + c.label + '">' +
           '<span class="hd"><span class="lbl">' + c.label + '</span>' + arrow + '</span></th>';
    }
    tr.innerHTML = h;
  }
  function s3RatingTiles(rows) {
    var tiles = document.getElementById('s3-rating-tiles');
    if (!tiles) return;
    var uc = s3UniverseCounts(rows);
    var total = rows.length;
    var order = ['None','Possible','Plausible','Probable'];
    var strip = {
      'Probable':'prob-inv',
      'Plausible':'pla-inv',
      'Possible':'pos-top',
      'None':'none'
    };
    var S3_THRESH = { // MD-V2-S55-S3-THRESH
      'Probable':  '≥4 of 6 · gates pass · multiple breakdown signals (vol/ATR/lower-lows/RS)',
      'Plausible': '3 of 6 · gates pass · breakdown evidence building',
      'Possible':  '2 of 6 · gates pass · early warning signals',
      'None':      'Gate(s) fail · fewer than 2 breakdown signals · uptrend still intact'
    }; /* MD-V2-S55-PER-TILE-CRITERIA-s3 */
    var h = '';
    for (var i = 0; i < order.length; i++) {
      var r = order[i], cnt = uc[r] || 0;
      var act = s3State.ratingFilter.indexOf(r) > -1 ? ' active' : '';
      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;
      h += '<div class="rating-tile ' + S3_TINT_CLS[r] + act + '" data-rating="' + r + '">' +
           '<div class="rt-label">' + r + '</div>' +
           '<div class="rt-count">' + cnt.toLocaleString('en-GB') + '</div>' +
           '<div class="rt-sub">of ' + total.toLocaleString('en-GB') + ' · ' + pct + '%</div>' +
           '<div class="rt-thresh">' + (S3_THRESH[r] || '\u00a0') + '</div>' +
           '<div class="rt-strip rt-strip-' + strip[r] + '"></div>' +
           '</div>';
    }
    tiles.innerHTML = h;
  }
  function s3UpdateScopeCounts(rows) {
    function set(id, n) { var el = document.getElementById(id); if (el) el.textContent = '(' + n + ')'; }
    set('s3-cnt-all',      rows.length);
    set('s3-cnt-live',     rows.filter(function(r){ return r.is_live; }).length);
    set('s3-cnt-sector',   rows.filter(function(r){ return r.sector_in_portfolio; }).length);
    set('s3-cnt-industry', rows.filter(function(r){ return r.industry_in_portfolio; }).length);
  }

  function s3RenderRows() {
    var tbody = document.getElementById('s3-tbody');
    if (!tbody) return;
    var all = s3GetRows();
    s3UpdateScopeCounts(all);
    s3RatingTiles(all);
    var rows = all.slice();
    if (s3State.scope === 'live') rows = rows.filter(function(r){ return r.is_live; });
    else if (s3State.scope === 'sector') rows = rows.filter(function(r){ return r.sector_in_portfolio; });
    else if (s3State.scope === 'industry') rows = rows.filter(function(r){ return r.industry_in_portfolio; });
    if (s3State.ratingFilter.length > 0) rows = rows.filter(function(r){ return s3State.ratingFilter.indexOf(r.rating) > -1; });
    rows.sort(function(a,b) {
      var va = s3GetSortVal(a, s3State.sort.col), vb = s3GetSortVal(b, s3State.sort.col);
      var cmp = (typeof va === 'string') ? va.localeCompare(vb) : (va || 0) - (vb || 0);
      if (cmp === 0) cmp = a.ticker.localeCompare(b.ticker);
      return s3State.sort.dir === 'desc' ? -cmp : cmp;
    });
    var html = '';
    for (var i = 0; i < rows.length; i++) {
      var s = rows[i];
      var styles = [], cls = [];
      if (s3State.tint === 'industry') { styles.push('--tint-bg: ' + s3HashColor(s.industry, 0.16)); cls.push('tint-row'); }
      else if (s3State.tint === 'sector') { styles.push('--tint-bg: ' + s3HashColor(s.sector, 0.16)); cls.push('tint-row'); }
      if (s3State.port === 'on') {
        var pi = s3PortfolioInfo(s);
        if (pi) {
          styles.push('--portfolio-color: ' + pi.color);
          styles.push('--portfolio-bg: ' + pi.bg);
          styles.push('--portfolio-bg-hover: ' + pi.bg);
          cls.push('portfolio-band'); cls.push('portfolio-tint');
        }
      }
      var styleAttr = styles.length ? ' style="' + styles.join(';') + '"' : '';
      var clsAttr = cls.length ? ' class="' + cls.join(' ') + '"' : '';
      var liveDot = s.is_live ? '<span class="live-dot">●</span>' : '';
      html += '<tr' + clsAttr + styleAttr + '>' +
        '<td class="name-cell"><div class="co">' + liveDot + (s.company || s.ticker) + '</div><div class="tk">' + s.ticker + '</div></td>' +
        '<td class="taxon"><div class="ind">' + (s.industry || '') + '</div><div class="sec">' + (s.sector || '') + '</div></td>' +
        s3InputCell(s, 'price') + s3InputCell(s, 'high_52w') + s3InputCell(s, 'low_52w') +
        s3InputCell(s, 'ma_150') + s3InputCell(s, 'ma_200') +
        '<td class="grp-start-rating">' + s3PillFor(s.rating, s.count) + '</td>' +
        '<td>' + s3ScorePips(s) + '</td>';
      for (var j = 9; j <= 18; j++) html += s3TestCell(s, S3_COLS[j]);
      html += '<td class="grp-start-persist">' + s3PersistCells(s.persistence, s.rating) + '</td>' +
        '</tr>';
    }
    tbody.innerHTML = html;
  }

  function s3SetMode(kind, val) {
    s3State.mode[kind] = val;
    var btns = document.querySelectorAll('button[data-s3-grp="' + kind + '"]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-s3-val') === val);
    s3RenderRows();
  }
  function s3SetScope(s) {
    s3State.scope = s;
    var btns = document.querySelectorAll('button[data-s3-scope]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-s3-scope') === s);
    s3RenderRows();
  }
  function s3SetTint(t) {
    s3State.tint = t;
    var btns = document.querySelectorAll('button[data-s3-tint]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-s3-tint') === t);
    s3RenderRows();
  }
  function s3SetPort(p) {
    s3State.port = p;
    var btns = document.querySelectorAll('button[data-s3-port]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-s3-port') === p);
    s3RenderRows();
  }
  function s3ToggleRating(r) {
    var _i = s3State.ratingFilter.indexOf(r);
    if (_i > -1) s3State.ratingFilter.splice(_i, 1); else s3State.ratingFilter.push(r);
    s3RenderRows();
  }
  window.s3SetMode = s3SetMode;
  window.s3SetScope = s3SetScope;
  window.s3SetTint = s3SetTint;
  window.s3SetPort = s3SetPort;
  window.s3ToggleRating = s3ToggleRating;
  window.s3OnSort = s3OnSort;

  function s3BuildScaffold() {
    var host = document.getElementById('tab-stage_3');
    if (!host) return false;
    if (host.querySelector('#s3-main-table')) return true;
    var html = '' +
      '<div class="s1-intro">Stage 3 looks for stocks where a previously confirmed uptrend shows signs of <b>trend exhaustion</b>: the long-term and mid-term gates still pass, but the run is mature (base count), and short-term price action is breaking down (distribution volume, volatility expansion, lower lows, RS slipping). The aim is to spot positions to lighten or candidates approaching invalidation. Eight tests across four groups: more tests passing means the breakdown case is firmer.</div>' +
      '<div class="controls s1-controls">' +
        '<div class="ctrl-grp"><span class="ctrl-label">Inputs</span>' +
          '<button class="toggle-btn active" data-s3-grp="inputs" data-s3-val="pct" onclick="s3SetMode(\'inputs\',\'pct\')">show as %</button>' +
          '<button class="toggle-btn" data-s3-grp="inputs" data-s3-val="raw" onclick="s3SetMode(\'inputs\',\'raw\')">show as numbers</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Tests</span>' +
          '<button class="toggle-btn active" data-s3-grp="tests" data-s3-val="tick" onclick="s3SetMode(\'tests\',\'tick\')">show ticks</button>' +
          '<button class="toggle-btn" data-s3-grp="tests" data-s3-val="val" onclick="s3SetMode(\'tests\',\'val\')">show test values</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Scope</span>' +
          '<button class="toggle-btn active" data-s3-scope="all" onclick="s3SetScope(\'all\')">All <span id="s3-cnt-all"></span></button>' +
          '<button class="toggle-btn" data-s3-scope="live" onclick="s3SetScope(\'live\')">Live <span id="s3-cnt-live"></span></button>' +
          '<button class="toggle-btn" data-s3-scope="sector" onclick="s3SetScope(\'sector\')">Sectors <span id="s3-cnt-sector"></span></button>' +
          '<button class="toggle-btn" data-s3-scope="industry" onclick="s3SetScope(\'industry\')">Industries <span id="s3-cnt-industry"></span></button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Peers</button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Cohorts</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Colour by</span>' +
          '<button class="toggle-btn active" data-s3-tint="none" onclick="s3SetTint(\'none\')">Off</button>' +
          '<button class="toggle-btn" data-s3-tint="industry" onclick="s3SetTint(\'industry\')">Industry</button>' +
          '<button class="toggle-btn" data-s3-tint="sector" onclick="s3SetTint(\'sector\')">Sector</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Portfolio tint</span>' +
          '<button class="toggle-btn active" data-s3-port="off" onclick="s3SetPort(\'off\')">Off</button>' +
          '<button class="toggle-btn" data-s3-port="on" onclick="s3SetPort(\'on\')">On</button>' +
        '</div>' +
      '</div>' +
      '<div class="rating-tiles s1-rating-tiles" id="s3-rating-tiles" style="grid-template-columns: repeat(4, 1fr);"></div>' +
      '<div class="group-captions" style="grid-template-columns: repeat(4, 1fr);">' +
        '<div class="gcap gcap-g1"><b>Group 1 · Long-term trend upwards?</b>Stage 3 only applies to a <span class="db">previously confirmed uptrend</span> &mdash; if the long-term trend is not still up, the right place to look is Stage 1 or Stage 4.<span class="intro">One long-term gate:</span><span class="tline"><span class="tnum">(1)</span> Is the <u>200-day MA still higher</u> than it sat 80 trading days ago?</span></div>' +
        '<div class="gcap gcap-g2"><b>Group 2 · Mid-term trend upwards?</b>The mid-term must <span class="db">still be intact</span> for trend-exhaustion to even be meaningful &mdash; price has to be above its 200-day MA.<span class="intro">One mid-term gate:</span><span class="tline"><span class="tnum">(2)</span> Is <u>price above its 200-day MA</u>?</span></div>' +
        '<div class="gcap gcap-g3"><b>Group 3 · Mid-term trend extended?</b><span class="db">How mature is the run?</span> Each successive base built since the 52-week low raises the odds the trend is getting late.<span class="intro">One maturity test:</span><span class="tline"><span class="tnum">(3)</span> Has the stock built <u>2 or more bases</u> since its 52-week low (504-day window)?</span></div>' +
        '<div class="gcap gcap-g4"><b>Group 4 · Short-term trend breaking down?</b>Even with the long-term still up, the <span class="db">short term is now showing distribution</span> &mdash; MA stack tightening, volume rotating down, volatility expanding, swing lows printing lower, RS slipping.<span class="intro">Five breakdown tests:</span><span class="tline"><span class="tnum">(4)</span> Is the <u>50D MA at or below 150D MA</u> (i.e. within 3% below — stack tightening toward a cross)?</span><span class="tline"><span class="tnum">(5)</span> Is down-day volume <u>at least 10% above up-day volume</u> over the last ~20 days?</span><span class="tline"><span class="tnum">(6)</span> Is last-month volatility <u>above the prior 4-month average</u> (L1M ATR vs P4M average ATR)?</span><span class="tline"><span class="tnum">(7)</span> Are there <u>2 or more lower lows</u> in the last 2 months?</span><span class="tline"><span class="tnum">(8)</span> Has sector RS percentile <u>dropped more than 10 points</u> versus 3 months ago?</span></div>' +
      '</div>' +
      '<div class="table-wrap"><div class="v2-hscroll">' +  /* MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER */
        '<table class="data-table" id="s3-main-table">' +
          '<colgroup>' +
            '<col class="c-name"><col class="c-taxon">' +
            '<col class="c-price"><col class="c-52wh"><col class="c-52wl">' +
            '<col class="c-ma150"><col class="c-ma200">' +
            '<col class="c-rating"><col class="c-score">' +
            '<col class="c-test"><col class="c-test">' +
            '<col class="c-test"><col class="c-test">' +
            '<col class="c-test"><col class="c-test"><col class="c-test">' +
            '<col class="c-test">' +
            '<col class="c-test"><col class="c-test">' +
            '<col class="c-persist">' +
          '</colgroup>' +
          '<thead>' +
            '<tr class="group-header-row">' +
              '<th class="gh-inputs" colspan="7">Inputs</th>' +
              '<th class="gh-rating grp-start-rating" colspan="2">Stage 3 rating</th>' /* MD-V2-S55-gh-s3 */ +
              '<th class="gh-g1 grp-start-g1 grp-end-g1" colspan="1">Group 1 — Long-term trend upwards?</th>' +
              '<th class="gh-g2 grp-start-g2 grp-end-g2" colspan="1">Group 2 — Mid-term trend upwards?</th>' +
              '<th class="gh-g3 grp-start-g3 grp-end-g3" colspan="1">Group 3 — Mid-term trend extended?</th>' +
              '<th class="gh-g4 grp-start-g4 grp-end-g4" colspan="5">Group 4 — Short-term trend breaking down?</th>' +
              '<th class="gh-g5 grp-start-g5 grp-end-g5" colspan="2">Group 5 — Taxonomy context?</th>' +
              '<th class="gh-persist grp-start-persist" colspan="1">Stage Qualification persistence</th>' +
            '</tr>' +
            '<tr class="col-header-row" id="s3-col-header-row"></tr>' +
          '</thead>' +
          '<tbody id="s3-tbody"></tbody>' +
        '</table>' +
      '</div></div>';  /* MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER */
    host.innerHTML = html;
    var tiles = document.getElementById('s3-rating-tiles');
    if (tiles) {
      tiles.addEventListener('click', function(e) {
        var tile = e.target.closest('.rating-tile');
        if (!tile) return;
        var r = tile.getAttribute('data-rating');
        if (r) s3ToggleRating(r);
      });
    }
    var hdr = document.getElementById('s3-col-header-row');
    if (hdr) {
      hdr.addEventListener('click', function(e) {
        var th = e.target.closest('th');
        if (!th) return;
        var key = th.getAttribute('data-sort-key');
        if (key) s3OnSort(key);
      });
    }
    return true;
  }

  function renderStage3() {
    if (!s3BuildScaffold()) return;
    s3BuildHeaderRow();
    s3RenderRows();
    if (window.measureV2Ribbon) measureV2Ribbon();  /* MD-V2-WAVE1B-STICKY-CORRECTIVE-MARKER */
  }
  window.renderStage3 = renderStage3;

})();

/* MD-V2-STAGE3-MARKER-END */

/* MD-V2-STAGE3-MARKER-MODULE-END */


/* MD-V2-STAGE4-MARKER-MODULE-START */
// =============================================================================
// STAGE 4 TAB MODULE — Master Dashboard V2
// =============================================================================
// MD-V2-STAGE4-MARKER — idempotency marker for patcher detection
//
// Stage 4 = Decline / Capitulation. 7 tests across 3 groups.
// Ratings:
//   None       (0)
//   Possible   (1)
//   Plausible  (2)
//   Probable   (3+)
// =============================================================================

/* MD-V2-STAGE4-MARKER-START */

(function() {
  'use strict';

  var s4State = {
    mode: { inputs: 'pct', tests: 'tick' },
    scope: 'all', ratingFilter: null, tint: 'none', port: 'off',
    sort: { col: 'count', dir: 'desc' }
  };

  // MD-V2-S54-S4-COLS-REWRITE
  // MD-V2-S55-S4-COLS-REWRITE: relabel for long/mid/near-term framing
  var S4_COLS = [
    { id:'name',      label:'Company · Ticker',              sortKey:'company', cls:'name-cell' },
    { id:'taxon',     label:'Industry · Sector',             sortKey:'sector', cls:'taxon' },
    { id:'price',     label:'Price',                         sortKey:'price', cls:'num' },
    { id:'high_52w',  label:'52 week high',                  sortKey:'high_52w', cls:'num' },
    { id:'low_52w',   label:'52 week low',                   sortKey:'low_52w', cls:'num' },
    { id:'ma_150',    label:'150D MA',        sortKey:'ma_150', cls:'num' },
    { id:'ma_200',    label:'200D MA',        sortKey:'ma_200', cls:'num' },
    { id:'rating',    label:'Rating',                        sortKey:'rating_rank', cls:'grp-start-rating' },
    { id:'count',     label:'Score',                         sortKey:'count', cls:'' },
    { id:'gp200_s4',  label:'1. Price below 200D MA (gate)',    sortKey:'gate_gp200_s4', cls:'grp-start-g1 grp-end-g1', testGroup:'_gates4', testKey:'gate_price_below_200D' },
    { id:'t2',        label:'2. 100D MA MoM declining',         sortKey:'t2_s4', cls:'grp-start-g2', testGroup:'g1_ma_decline', testKey:'T2' },
    { id:'t3',        label:'3. 200D MA MoM declining',         sortKey:'t3_s4', cls:'grp-end-g2', testGroup:'g1_ma_decline', testKey:'T3' },
    { id:'t4',        label:'4. Full bearish stack (P<50<150<200)', sortKey:'t4_s4', cls:'grp-start-g3 grp-end-g3', testGroup:'g2_ma_stack', testKey:'T4' },
    { id:'sec_in_ind',label:'# sectors in industry',        sortKey:'sectors_in_industry', cls:'grp-start-g4', colType:'count', countKey:'sectors_in_industry', countRedAt:2, countAmberAt:4 },
    { id:'co_in_sec', label:'# companies in sector',        sortKey:'companies_in_sector', cls:'grp-end-g4', colType:'count', countKey:'companies_in_sector', countRedAt:2, countAmberAt:5 },
    { id:'persist',   label:'Last 12 months',               sortKey:'persistence_count', cls:'grp-start-persist' }
  ];
  var S4_RATING_RANK = { 'Probable':4, 'Plausible':3, 'Possible':2, 'None':1 };
  var S4_TINT_CLS = { 'Probable':'tint-prob','Plausible':'tint-pla','Possible':'tint-pos','None':'tint-none' };

  function s4PricesLookup() {
    if (window._s4PricesByTicker) return window._s4PricesByTicker;
    var out = {};
    var arr = (window.MASTER_DATA && MASTER_DATA.prices) || [];
    for (var i = 0; i < arr.length; i++) if (arr[i] && arr[i].ticker) out[arr[i].ticker] = arr[i];
    window._s4PricesByTicker = out;
    return out;
  }
  function s4LiveTickers() {
    var out = {};
    var inv = (window.MASTER_DATA && MASTER_DATA.positions && MASTER_DATA.positions.investments) || [];
    for (var i = 0; i < inv.length; i++) if (inv[i].ticker) out[inv[i].ticker] = true;
    return out;
  }
  function s4LiveSectors() {
    var out = {}, t, prices = s4PricesLookup(), tickers = s4LiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.sector) out[p.sector] = true; }
    return out;
  }
  function s4LiveIndustries() {
    var out = {}, t, prices = s4PricesLookup(), tickers = s4LiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.industry) out[p.industry] = true; }
    return out;
  }
  function s4GetRows() {
    var raw = (window.MASTER_DATA && MASTER_DATA.filters) || [];
    var prices = s4PricesLookup();
    var live = s4LiveTickers(), liveS = s4LiveSectors(), liveI = s4LiveIndustries();
    var rows = [];
    for (var i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || !s.md_v2 || !s.md_v2.stage_4) continue;
      var p = prices[s.ticker] || {};
      var s4 = s.md_v2.stage_4;
      var pers = (s.md_v2.persistence && s.md_v2.persistence.stage_4_persistence) || [];
      var mas = p.mas || {};
      // MD-V2-S54: merge gate boolean into _gates4 group, add count fields
      var s4grps = {}; var s4gsrc = s4.groups || {};
      for (var _k4 in s4gsrc) s4grps[_k4] = s4gsrc[_k4];
      s4grps._gates4 = { gate_price_below_200D: !!(s4.gate_price_below_200D) };
      rows.push({
        ticker: s.ticker, company: p.company_name || s.ticker,
        sector: p.sector || '', industry: p.industry || '',
        price: p.price, high_52w: p.high_52w, low_52w: p.low_52w,
        ma_50: mas['50D'], ma_150: mas['150D'], ma_200: mas['200D'],
        rating: s4.rating, count: s4.count,
        tests: s4.tests || {}, groups: s4grps, persistence: pers,
        rs_sector: p.rs_vs_sector_pct, rs_industry: p.rs_vs_industry_pct, rs_market: p.rs_market_pct,
        sectors_in_industry: (s.md_v2.sectors_in_industry_count || 0),
        companies_in_sector: (s.md_v2.companies_in_sector_count || 0),
        is_live: !!live[s.ticker],
        sector_in_portfolio: !!liveS[p.sector],
        industry_in_portfolio: !!liveI[p.industry]
      });
    }
    return rows;
  }
  // MD-V2-S54-S4-UNIVERSE: new data emits plain Probable only
  function s4UniverseCounts(rows) {
    var c = {'Probable':0,'Plausible':0,'Possible':0,'None':0};
    for (var i = 0; i < rows.length; i++) {
      var _r4 = rows[i].rating;
      if (c[_r4] !== undefined) c[_r4]++;
    }
    return c;
  }

  function s4FmtNum(n) {
    if (n == null || isNaN(n)) return '—';
    var abs = Math.abs(n);
    var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);
    if (Math.abs(n - Math.round(n)) < 1e-9) dp = 0; /* MD-V2-S40-FMTNUM-INT-FIX-s4; S41 tolerance */
    var f = abs.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });
    return n < 0 ? '(' + f + ')' : f;
  }
  function s4FmtPct(p) {
    if (p == null || isNaN(p)) return '—';
    var r = Math.round(p), abs = Math.abs(r);
    return r < 0 ? '(' + abs + ')%' : r + '%';
  }
  // Stage 4 INVERTED scale (same logic as Stage 3 — bearish passes coloured red)
  function s4ColourForIntensity(i) {
    if (i >= 0.6) return '#8b1a1a';
    if (i >= 0.25) return '#a83232';
    if (i >= 0.05) return '#c66666';
    if (i <= -0.6) return '#0a4012';
    if (i <= -0.25) return '#1f6325';
    if (i <= -0.05) return '#4a8050';
    return '#666';
  }
  function s4InputCell(row, key, extraCls) {
    extraCls = extraCls || '';
    var v = row[key];
    if (key === 'price') return '<td class="num ' + extraCls + '">' + s4FmtNum(v) + '</td>';
    if (v == null || row.price == null) return '<td class="num ' + extraCls + '">—</td>';
    var pct = (row.price - v) / v * 100;
    var intensity = 0;
    if (key === 'high_52w') intensity = Math.max(-1, Math.min(1, (-pct - 10) / 20));   // far below high = bearish
    else if (key === 'low_52w') intensity = Math.max(-1, Math.min(1, (20 - pct) / 30)); // near low = bearish
    else if (key === 'ma_150' || key === 'ma_200') intensity = Math.max(-1, Math.min(1, -pct / 10));
    var colour = s4ColourForIntensity(intensity);
    var text = (s4State.mode.inputs === 'pct') ? s4FmtPct(pct) : s4FmtNum(v);
    return '<td class="num ' + extraCls + '" style="color:' + colour + '">' + text + '</td>';
  }

  function s4TestValueFor(row, col) {
    var k = col.testKey;
    var t = row.tests || {};
    // G1: 200D declining + accelerating (binary derived)
    if (k === 'T1') return t.T1_200D_declining ? 'declining' : 'rising/flat';
    if (k === 'T2') return t.T2_200D_decline_accelerating ? 'accel.' : '—';
    // G2: MA stack — show pct gaps
    if (k === 'T3') return t.T3_total_stack_down ? 'P<50<150<200' : '—';
    if (k === 'T4') return row.ma_150 != null && row.ma_200 != null ? s4FmtPct((row.ma_150 - row.ma_200) / row.ma_200 * 100) : '—';
    if (k === 'T5') return row.ma_50 != null && row.ma_150 != null ? s4FmtPct((row.ma_50 - row.ma_150) / row.ma_150 * 100) : '—';
    // G3: RS values
    if (k === 'T6') {
      var bits = [];
      if (row.rs_industry != null) bits.push('ind ' + Math.round(row.rs_industry));
      if (row.rs_sector  != null) bits.push('sec ' + Math.round(row.rs_sector));
      return bits.length ? bits.join(' · ') : '—';
    }
    if (k === 'T7') return t.T7_RS_trend_weak ? '< -5%' : '—';
    return '—';
  }
  function s4TestCell(row, col) {
    // MD-V2-S54: count column type
    if (col.colType === 'count') {
      var n = row[col.countKey] || 0;
      var ccls = col.cls || '';
      var cstyle = n <= col.countRedAt ? 'color:#a83232' : (n <= col.countAmberAt ? 'color:#b45309' : 'color:#555');
      return '<td class="num ' + ccls + '" style="' + cstyle + '">' + n + '</td>';
    }
    var grp = (row.groups || {})[col.testGroup] || {};
    var pass = !!grp[col.testKey];
    var extra = col.cls || '';
    if (s4State.mode.tests === 'val') {
      var v = s4TestValueFor(row, col);
      // Stage 4 passes are BEARISH — colour pass red, fail neutral grey
      var colour = pass ? s4ColourForIntensity(0.7) : '#999';
      return '<td class="test-val ' + extra + '" style="color:' + colour + '">' + v + '</td>';
    }
    if (pass) return '<td class="test-pass-bear ' + extra + '"><span class="tick">✓</span></td>';
    return '<td class="test-fail ' + extra + '">·</td>';
  }

  function s4PillFor(rating, count) {
    if (rating === 'Probable') {
      var c = Math.min(Math.max(count, 3), 7);
      return '<span class="pill pill-prob-' + c + '">Probable</span>';
    }
    if (rating === 'Plausible') return '<span class="pill pill-pla">Plausible</span>';
    if (rating === 'Possible') return '<span class="pill pill-pos">Possible</span>';
    return '<span class="pill pill-none">None</span>';
  }
  // MD-V2-S58-S4-PIPS: gate dot + 3 tests (T2-T4)
  function s4ScorePips(row) {
    var t = row.tests;
    var passed = [
      !!t.T2_100D_MoM_declining, !!t.T3_200D_MoM_declining, !!t.T4_bearish_MA_stack
    ];
    var count = passed.filter(Boolean).length;
    var g4 = (row.groups && row.groups._gates4) || {};
    var s = '<span class="pip pip-bear ' + (g4.gate_price_below_200D ? 'gate-ok' : 'gate-x') + '"></span>' +
            '<span class="pip-div"></span>';
    var s4DivAfter = {1:true};
    for (var i = 0; i < 3; i++) {
      s += '<span class="pip pip-bear ' + (passed[i] ? 'on' : '') + '"></span>';
      if (s4DivAfter[i]) s += '<span class="pip-div"></span>';
    }
    return '<div class="score-pip-row">' + s + '<span class="score-num">' + count + '/3</span></div>';
  }
  function s4PersistCells(arr, rating) {
    var h = '';
    for (var i = 0; i < 12; i++) {
      if (i === 11 && arr && arr[11]) {
        var cls = rating === 'Probable' ? 'r-prob' :
                  rating === 'Plausible' ? 'r-pla' :
                  rating === 'Possible' ? 'r-pos' : 'r-none';
        h += '<span class="persist-cell ' + cls + '" title="Current month: ' + rating + '"></span>';
      } else {
        h += '<span class="persist-cell r-none" title="Month -' + (11 - i) + ': not yet backfilled"></span>';
      }
    }
    return '<div class="persist-row">' + h + '</div>';
  }

  function s4HashColor(label, alpha) {
    if (!label) return null;
    var h = 0;
    for (var i = 0; i < label.length; i++) h = (h * 31 + label.charCodeAt(i)) & 0xffff;
    return 'hsla(' + (h % 360) + ', 35%, 55%, ' + alpha + ')';
  }
  function s4PortfolioInfo(row) {
    if (row.is_live) return { color:'#1b5e20', bg:'rgba(27,94,32,0.10)', bgHover:'rgba(27,94,32,0.14)' };
    if (row.sector_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.05)', bgHover:'rgba(27,94,32,0.08)' };
    if (row.industry_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.025)', bgHover:'rgba(27,94,32,0.05)' };
    return null;
  }

  function s4GetSortVal(row, key) {
    if (key === 'rating_rank') return S4_RATING_RANK[row.rating] || 0;
    if (key === 'persistence_count') return (row.persistence || []).filter(Boolean).length;
    if (key.indexOf('g') === 0 && key.indexOf('_t') > 0) {
      var col = S4_COLS.find(function(c) { return c.sortKey === key; });
      if (col) {
        var grp = (row.groups || {})[col.testGroup] || {};
        return grp[col.testKey] ? 1 : 0;
      }
    }
    var PCT_KEYS = ['high_52w','low_52w','ma_150','ma_200'];
    if (PCT_KEYS.indexOf(key) > -1 && s4State.mode.inputs === 'pct') {
      var ref = row[key];
      if (ref == null || row.price == null || ref === 0) return -Infinity;
      return (row.price - ref) / ref * 100;
    }
    if (key in row) return row[key];
    return 0;
  }
  function s4OnSort(key) {
    if (s4State.sort.col === key) s4State.sort.dir = s4State.sort.dir === 'desc' ? 'asc' : 'desc';
    else s4State.sort = { col: key, dir: 'desc' };
    s4BuildHeaderRow();
    s4RenderRows();
  }

  function s4BuildHeaderRow() {
    var tr = document.getElementById('s4-col-header-row');
    if (!tr) return;
    var h = '';
    for (var i = 0; i < S4_COLS.length; i++) {
      var c = S4_COLS[i];
      var isSort = s4State.sort.col === c.sortKey;
      var arrow = isSort
        ? '<span class="sort-arrow">' + (s4State.sort.dir === 'desc' ? '▼' : '▲') + '</span>'
        : '<span class="sort-placeholder"></span>';
      h += '<th class="' + (c.cls || '') + '" data-sort-key="' + c.sortKey + '" title="' + c.label + '">' +
           '<span class="hd"><span class="lbl">' + c.label + '</span>' + arrow + '</span></th>';
    }
    tr.innerHTML = h;
  }
  function s4RatingTiles(rows) {
    var tiles = document.getElementById('s4-rating-tiles');
    if (!tiles) return;
    var uc = s4UniverseCounts(rows);
    var total = rows.length;
    var order = ['None','Possible','Plausible','Probable'];
    var strip = {'Probable':'prob','Plausible':'pla','Possible':'pos','None':'none'};
    var S4_THRESH = {
      'Probable':  'Gate pass \u00b7 100D + 200D both declining MoM \u00b7 full bearish stack',
      'Plausible': 'Gate pass \u00b7 100D + 200D both declining MoM \u00b7 stack not yet inverted',
      'Possible':  'Gate pass \u00b7 100-day declining MoM only \u00b7 early decline signal',
      'None':      'Gate fail (price not yet below 200-day) \u00b7 no confirmed decline'
    }; /* MD-V2-S55-PER-TILE-CRITERIA-s4 */
    var h = '';
    for (var i = 0; i < order.length; i++) {
      var r = order[i], cnt = uc[r] || 0;
      var act = s4State.ratingFilter === r ? ' active' : '';
      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;
      h += '<div class="rating-tile ' + S4_TINT_CLS[r] + act + '" data-rating="' + r + '">' +
           '<div class="rt-label">' + r + '</div>' +
           '<div class="rt-count">' + cnt.toLocaleString('en-GB') + '</div>' +
           '<div class="rt-sub">of ' + total.toLocaleString('en-GB') + ' · ' + pct + '%</div>' +
           '<div class="rt-thresh">' + (S4_THRESH[r] || '\u00a0') + '</div>' +
           '<div class="rt-strip rt-strip-' + strip[r] + '"></div>' +
           '</div>';
    }
    tiles.innerHTML = h;
  }
  function s4UpdateScopeCounts(rows) {
    function set(id, n) { var el = document.getElementById(id); if (el) el.textContent = '(' + n + ')'; }
    set('s4-cnt-all',      rows.length);
    set('s4-cnt-live',     rows.filter(function(r){ return r.is_live; }).length);
    set('s4-cnt-sector',   rows.filter(function(r){ return r.sector_in_portfolio; }).length);
    set('s4-cnt-industry', rows.filter(function(r){ return r.industry_in_portfolio; }).length);
  }

  function s4RenderRows() {
    var tbody = document.getElementById('s4-tbody');
    if (!tbody) return;
    var all = s4GetRows();
    s4UpdateScopeCounts(all);
    s4RatingTiles(all);
    var rows = all.slice();
    if (s4State.scope === 'live') rows = rows.filter(function(r){ return r.is_live; });
    else if (s4State.scope === 'sector') rows = rows.filter(function(r){ return r.sector_in_portfolio; });
    else if (s4State.scope === 'industry') rows = rows.filter(function(r){ return r.industry_in_portfolio; });
    if (s4State.ratingFilter) rows = rows.filter(function(r){ return s4State.ratingFilter === 'Probable' ? (r.rating && r.rating.indexOf('Probable') === 0) : r.rating === s4State.ratingFilter; });  /* MD-V2-S53-S4-PROBABLE-ACCEL-FIX */
    rows.sort(function(a,b) {
      var va = s4GetSortVal(a, s4State.sort.col), vb = s4GetSortVal(b, s4State.sort.col);
      var cmp = (typeof va === 'string') ? va.localeCompare(vb) : (va || 0) - (vb || 0);
      if (cmp === 0) cmp = a.ticker.localeCompare(b.ticker);
      return s4State.sort.dir === 'desc' ? -cmp : cmp;
    });
    var html = '';
    for (var i = 0; i < rows.length; i++) {
      var s = rows[i];
      var styles = [], cls = [];
      if (s4State.tint === 'industry') { styles.push('--tint-bg: ' + s4HashColor(s.industry, 0.16)); cls.push('tint-row'); }
      else if (s4State.tint === 'sector') { styles.push('--tint-bg: ' + s4HashColor(s.sector, 0.16)); cls.push('tint-row'); }
      if (s4State.port === 'on') {
        var pi = s4PortfolioInfo(s);
        if (pi) {
          styles.push('--portfolio-color: ' + pi.color);
          styles.push('--portfolio-bg: ' + pi.bg);
          styles.push('--portfolio-bg-hover: ' + pi.bgHover);
          cls.push('portfolio-band'); cls.push('portfolio-tint');
        }
      }
      var styleAttr = styles.length ? ' style="' + styles.join(';') + '"' : '';
      var clsAttr = cls.length ? ' class="' + cls.join(' ') + '"' : '';
      var liveDot = s.is_live ? '<span class="live-dot">●</span>' : '';
      html += '<tr' + clsAttr + styleAttr + '>' +
        '<td class="name-cell"><div class="co">' + liveDot + (s.company || s.ticker) + '</div><div class="tk">' + s.ticker + '</div></td>' +
        '<td class="taxon"><div class="ind">' + (s.industry || '') + '</div><div class="sec">' + (s.sector || '') + '</div></td>' +
        s4InputCell(s, 'price') + s4InputCell(s, 'high_52w') + s4InputCell(s, 'low_52w') +
        s4InputCell(s, 'ma_150') + s4InputCell(s, 'ma_200') +
        '<td class="grp-start-rating">' + s4PillFor(s.rating, s.count) + '</td>' +
        '<td>' + s4ScorePips(s) + '</td>';
      for (var j = 9; j <= 14; j++) html += s4TestCell(s, S4_COLS[j]); // MD-V2-S54
      html += '<td class="grp-start-persist">' + s4PersistCells(s.persistence, s.rating) + '</td>' +
        '</tr>';
    }
    tbody.innerHTML = html;
  }

  function s4SetMode(kind, val) {
    s4State.mode[kind] = val;
    var btns = document.querySelectorAll('button[data-s4-grp="' + kind + '"]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-s4-val') === val);
    s4RenderRows();
  }
  function s4SetScope(s) {
    s4State.scope = s;
    var btns = document.querySelectorAll('button[data-s4-scope]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-s4-scope') === s);
    s4RenderRows();
  }
  function s4SetTint(t) {
    s4State.tint = t;
    var btns = document.querySelectorAll('button[data-s4-tint]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-s4-tint') === t);
    s4RenderRows();
  }
  function s4SetPort(p) {
    s4State.port = p;
    var btns = document.querySelectorAll('button[data-s4-port]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-s4-port') === p);
    s4RenderRows();
  }
  function s4ToggleRating(r) {
    s4State.ratingFilter = (s4State.ratingFilter === r) ? null : r;
    s4RenderRows();
  }
  window.s4SetMode = s4SetMode;
  window.s4SetScope = s4SetScope;
  window.s4SetTint = s4SetTint;
  window.s4SetPort = s4SetPort;
  window.s4ToggleRating = s4ToggleRating;
  window.s4OnSort = s4OnSort;

  function s4BuildScaffold() {
    var host = document.getElementById('tab-stage_4');
    if (!host) return false;
    if (host.querySelector('#s4-main-table')) return true;
    var html = '' +
      '<div class="s1-intro">Stage 4 looks for stocks in <b>confirmed decline</b>: price below its 200-day MA (gate), and the trend pointing down across both the long-term and mid-term horizons. The aim is to flag positions that should be exited if held, and to identify capitulation candidates eligible for the pullback-tranche playbook on rebound. Four tests across three groups (long-term, mid-term, near-term): more tests passing means the decline is more entrenched.</div>' +
      '<div class="controls s1-controls">' +
        '<div class="ctrl-grp"><span class="ctrl-label">Inputs</span>' +
          '<button class="toggle-btn active" data-s4-grp="inputs" data-s4-val="pct" onclick="s4SetMode(\'inputs\',\'pct\')">show as %</button>' +
          '<button class="toggle-btn" data-s4-grp="inputs" data-s4-val="raw" onclick="s4SetMode(\'inputs\',\'raw\')">show as numbers</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Tests</span>' +
          '<button class="toggle-btn active" data-s4-grp="tests" data-s4-val="tick" onclick="s4SetMode(\'tests\',\'tick\')">show ticks</button>' +
          '<button class="toggle-btn" data-s4-grp="tests" data-s4-val="val" onclick="s4SetMode(\'tests\',\'val\')">show test values</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Scope</span>' +
          '<button class="toggle-btn active" data-s4-scope="all" onclick="s4SetScope(\'all\')">All <span id="s4-cnt-all"></span></button>' +
          '<button class="toggle-btn" data-s4-scope="live" onclick="s4SetScope(\'live\')">Live <span id="s4-cnt-live"></span></button>' +
          '<button class="toggle-btn" data-s4-scope="sector" onclick="s4SetScope(\'sector\')">Sectors <span id="s4-cnt-sector"></span></button>' +
          '<button class="toggle-btn" data-s4-scope="industry" onclick="s4SetScope(\'industry\')">Industries <span id="s4-cnt-industry"></span></button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Peers</button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Cohorts</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Colour by</span>' +
          '<button class="toggle-btn active" data-s4-tint="none" onclick="s4SetTint(\'none\')">Off</button>' +
          '<button class="toggle-btn" data-s4-tint="industry" onclick="s4SetTint(\'industry\')">Industry</button>' +
          '<button class="toggle-btn" data-s4-tint="sector" onclick="s4SetTint(\'sector\')">Sector</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Portfolio tint</span>' +
          '<button class="toggle-btn active" data-s4-port="off" onclick="s4SetPort(\'off\')">Off</button>' +
          '<button class="toggle-btn" data-s4-port="on" onclick="s4SetPort(\'on\')">On</button>' +
        '</div>' +
      '</div>' +
      '<div class="rating-tiles s1-rating-tiles" id="s4-rating-tiles" style="grid-template-columns: repeat(4, 1fr);"></div>' +
      '<div class="group-captions" style="grid-template-columns: repeat(3, 1fr);">' +
        '<div class="gcap gcap-g1"><b>Group 1 · Long-term trend</b>Is the <span class="db">long-term trend confirmed down</span>? Price below its 200-day MA is the hard prerequisite &mdash; nothing else in Stage 4 matters until that gate passes.<span class="intro">One long-term gate:</span><span class="tline"><span class="tnum">(1)</span> Is <u>price below its 200-day MA</u>?</span></div>' +
        '<div class="gcap gcap-g2"><b>Group 2 · Mid-term trend</b>The mid-term moving averages should also be <span class="db">pointing down</span> &mdash; both the 100-day and the 200-day falling month-on-month.<span class="intro">Two mid-term decline tests:</span><span class="tline"><span class="tnum">(2)</span> Is the <u>100-day MA lower month-on-month</u>?</span><span class="tline"><span class="tnum">(3)</span> Is the <u>200-day MA lower month-on-month</u>?</span></div>' +
        '<div class="gcap gcap-g3"><b>Group 3 · Near-term trend</b>The <span class="db">full moving-average stack should be inverted</span> &mdash; price stacked below every MA, in order. The clearest near-term confirmation that the decline is fully under way.<span class="intro">One near-term test:</span><span class="tline"><span class="tnum">(4)</span> Is the stack <u>fully inverted</u> &mdash; price below the 50-day, below the 150-day, below the 200-day?</span></div>' +
      '</div>' +
      '<div class="table-wrap"><div class="v2-hscroll">' +  /* MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER */
        '<table class="data-table" id="s4-main-table">' +
          '<colgroup>' +
            '<col class="c-name"><col class="c-taxon">' +
            '<col class="c-price"><col class="c-52wh"><col class="c-52wl">' +
            '<col class="c-ma150"><col class="c-ma200">' +
            '<col class="c-rating"><col class="c-score">' +
            '<col class="c-test">' +
            '<col class="c-test"><col class="c-test">' +
            '<col class="c-test">' +
            '<col class="c-test"><col class="c-test">' +
            '<col class="c-persist">' +
          '</colgroup>' +
          '<thead>' +
            '<tr class="group-header-row">' +
              '<th class="gh-inputs" colspan="7">Inputs</th>' +
              '<th class="gh-rating grp-start-rating" colspan="2">Stage 4 rating</th>' /* MD-V2-S55-gh-s4 */ +
              '<th class="gh-g1 grp-start-g1 grp-end-g1" colspan="1">Group 1 — Long-term trend declining?</th>' +
              '<th class="gh-g2 grp-start-g2 grp-end-g2" colspan="2">Group 2 — Mid-term trend declining?</th>' +
              '<th class="gh-g3 grp-start-g3 grp-end-g3" colspan="1">Group 3 — Near-term trend declining?</th>' +
              '<th class="gh-g4 grp-start-g4 grp-end-g4" colspan="2">Group 4 — Taxonomy context?</th>' +
              '<th class="gh-persist grp-start-persist" colspan="1">Stage Qualification persistence</th>' +
            '</tr>' +
            '<tr class="col-header-row" id="s4-col-header-row"></tr>' +
          '</thead>' +
          '<tbody id="s4-tbody"></tbody>' +
        '</table>' +
      '</div></div>';  /* MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER */
    host.innerHTML = html;
    var tiles = document.getElementById('s4-rating-tiles');
    if (tiles) {
      tiles.addEventListener('click', function(e) {
        var tile = e.target.closest('.rating-tile');
        if (!tile) return;
        var r = tile.getAttribute('data-rating');
        if (r) s4ToggleRating(r);
      });
    }
    var hdr = document.getElementById('s4-col-header-row');
    if (hdr) {
      hdr.addEventListener('click', function(e) {
        var th = e.target.closest('th');
        if (!th) return;
        var key = th.getAttribute('data-sort-key');
        if (key) s4OnSort(key);
      });
    }
    return true;
  }

  function renderStage4() {
    if (!s4BuildScaffold()) return;
    s4BuildHeaderRow();
    s4RenderRows();
    if (window.measureV2Ribbon) measureV2Ribbon();  /* MD-V2-WAVE1B-STICKY-CORRECTIVE-MARKER */
  }
  window.renderStage4 = renderStage4;

})();

/* MD-V2-STAGE4-MARKER-END */

/* MD-V2-STAGE4-MARKER-MODULE-END */


/* MD-V2-CHROME-PARITY-MARKER-JS-START */
(function() {
  'use strict';
  // MD-V2-WAVE1-FROZEN-HEADERS-MARKER: measure the sticky ribbon's rendered height and publish it
  // as the --v2-ribbon-h custom property so the frozen-header `top:`
  // offsets are exact even when the ribbon wraps at narrow widths.
  function measureV2Ribbon() {
    var active = document.body.getAttribute('data-active-tab') || '';
    var v2 = (active.indexOf('stage_') === 0 || active === 'pre_indicators' ||
              active === 'post_indicators' || active.indexOf('setups') === 0 ||
              active === 'tests' || active === 'master_overview');
    if (!v2) return;
    var pane = document.getElementById('tab-' + active);
    var ribbon = pane && pane.querySelector('.controls.s1-controls');
    if (!ribbon) return;
    var h = ribbon.getBoundingClientRect().height;
    if (h && h > 0) {
      document.body.style.setProperty('--v2-ribbon-h', Math.round(h) + 'px');
    }
  }
  window.measureV2Ribbon = measureV2Ribbon;
  if (!window._v2RibbonResizeWired) {
    window._v2RibbonResizeWired = true;
    window.addEventListener('resize', function() {
      // rAF-debounced so a drag-resize does not thrash layout.
      if (window._v2RibbonRaf) return;
      window._v2RibbonRaf = requestAnimationFrame(function() {
        window._v2RibbonRaf = 0;
        measureV2Ribbon();
      });
    });
  }
  function ensureV2Nav() {
    if (document.getElementById('v2-nav-strip')) return;
    var hdr = document.querySelector('.header');
    if (!hdr) return;
    var nav = document.createElement('div');
    nav.id = 'v2-nav-strip';
    nav.className = 'v2-nav';
    // MD-V2-PI-V2-S25-MARKER: EDIT 2 - Block B nav tier grouping + terminology
    // (D-MD-V2-48 + D-MD-V2-46). Group labels + separators between tiers;
    // internal tab keys unchanged (display-only rename).
    nav.innerHTML = ''
      + '<span class="v2-nav-label">MD V2</span>'
      + '<span class="v2-nav-grp-label">Stages - MT/LT trends</span>'
      + '<button class="v2-nav-btn v2-grp-stages" data-v2-tab="stage_1" onclick="switchTab(\'stage_1\')">Stage 1 (Basing)</button>'
      + '<button class="v2-nav-btn v2-grp-stages" data-v2-tab="stage_2" onclick="switchTab(\'stage_2\')">Stage 2 (Uptrend)</button>'
      + '<button class="v2-nav-btn v2-grp-stages" data-v2-tab="stage_3" onclick="switchTab(\'stage_3\')">Stage 3 (Topping)</button>'
      + '<button class="v2-nav-btn v2-grp-stages" data-v2-tab="stage_4" onclick="switchTab(\'stage_4\')">Stage 4 (Decline)</button>'
      + '<span class="v2-nav-sep"></span>'
      + '<span class="v2-nav-grp-label">Early-stage indicators</span>'
      + '<button class="v2-nav-btn v2-grp-indicators" data-v2-tab="pre_indicators" onclick="switchTab(\'pre_indicators\')">Pre-farfalle indicators</button>'
      + '<button class="v2-nav-btn v2-grp-indicators" data-v2-tab="post_indicators" onclick="switchTab(\'post_indicators\')">Post-farfalle indicators</button>'
      + '<span class="v2-nav-sep"></span>'
      + '<span class="v2-nav-grp-label">Late-stage capital qualification</span>'
      + '<button class="v2-nav-btn v2-grp-setups" data-v2-tab="setups_s1pb" onclick="switchTab(\'setups_s1pb\')">Stage 1 and Stage N PBs</button>'
      + '<button class="v2-nav-btn v2-grp-setups" data-v2-tab="setups_s2vcp" onclick="switchTab(\'setups_s2vcp\')">Stage 2 VCPs and retests</button>'
      + '<span class="v2-nav-sep"></span>'
      + '<span class="v2-nav-grp-label">Capital deployment</span>'
      + '<button class="v2-nav-btn v2-grp-tests" data-v2-tab="tests" onclick="switchTab(\'tests\')">Capital deployment tests</button>'
      + '<button class="v2-nav-btn v2-grp-tests" data-v2-tab="setups_healthy_retest" onclick="switchTab(\'setups_healthy_retest\')">Healthy Retest</button>'  /* MD-V2-S47-TAB-HEALTHY-RETEST-MARKER */
      + '<button class="v2-nav-btn v2-grp-tests" data-v2-tab="tests_probing_bet_s1" onclick="switchTab(\'tests_probing_bet_s1\')">S1 Probing Bet</button>'
      + '<button class="v2-nav-btn v2-grp-tests" data-v2-tab="tests_probing_bet_s2" onclick="switchTab(\'tests_probing_bet_s2\')">S2 Probing Bet</button>'  /* MD-V2-S59-TAB-PB-SPLIT-MARKER */
      + '<button class="v2-nav-btn v2-grp-tests" data-v2-tab="tests_speculative_bet" onclick="switchTab(\'tests_speculative_bet\')">Speculative Bets</button>'  /* MD-V2-S47-TAB-SPECULATIVE-BET-MARKER */
      + '<button class="v2-nav-btn v2-grp-tests" data-v2-tab="tests_healthy_vcp" onclick="switchTab(\'tests_healthy_vcp\')">Healthy VCP</button>'  /* MD-V2-S48-TAB-HEALTHY-VCP-MARKER */
      + '<span class="v2-nav-sep"></span>'
      + '<span class="v2-nav-sep"></span>'
      + '<span class="v2-nav-grp-label">Overview</span>'
      + '<button class="v2-nav-btn v2-grp-overview" data-v2-tab="master_overview" onclick="switchTab(\'master_overview\')">Overview</button>';  /* MD-V2-MASTER-OVERVIEW-S27-MARKER */
    hdr.appendChild(nav);
  }
  function syncV2State(id) {
    document.body.setAttribute('data-active-tab', id);
    ensureV2Nav();
    // MD-V2-WAVE1-FROZEN-HEADERS-MARKER: re-measure the sticky ribbon once this tab's layout settles.
    requestAnimationFrame(function(){ requestAnimationFrame(measureV2Ribbon); });
    var ACCENT = { 'stage_1':'v2-active-s1', 'stage_2':'v2-active-s2', 'stage_3':'v2-active-s3', 'stage_4':'v2-active-s4' };
    var btns = document.querySelectorAll('.v2-nav-btn');
    for (var i = 0; i < btns.length; i++) {
      var t = btns[i].getAttribute('data-v2-tab');
      btns[i].classList.remove('v2-active','v2-active-s1','v2-active-s2','v2-active-s3','v2-active-s4');
      if (t === id) {
        btns[i].classList.add(ACCENT[id] || 'v2-active');
      }
    }
  }
  // Wrap the existing switchTab so we sync state every time it runs.
  var _origSwitchTab = window.switchTab;
  window.switchTab = function(id) {
    syncV2State(id);
    if (typeof _origSwitchTab === 'function') return _origSwitchTab(id);
  };
  // Initial sync on load (currentTab is already set by bootstrap)
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function(){ ensureV2Nav(); syncV2State(window.currentTab || 'master_overview'); });
  } else {
    ensureV2Nav();
    syncV2State(window.currentTab || 'master_overview');
  }
})();
/* MD-V2-CHROME-PARITY-MARKER-JS-END */

/* MD-V2-S40-INPUTS-LIVE-COUNT: live row-count next to the "Inputs" supergroup
   column-header on every tab that carries one. Updates on tbody mutation
   (rating-tile filter change, sort, etc.). Self-contained IIFE; one
   injection covers all 8 tabs (Stage 1-4 + PI/PO/ST/CT). */
(function() {
  var attached = new WeakSet();
  function attachTo(table) {
    if (attached.has(table)) return;
    var th = table.querySelector('th.gh-inputs');
    var tbody = table.tBodies[0];
    if (!th || !tbody) return;
    if (!th.querySelector('.inputs-count')) {
      var orig = '';
      for (var i = 0; i < th.childNodes.length; i++) {
        if (th.childNodes[i].nodeType === 3) { orig += th.childNodes[i].nodeValue; }
      }
      orig = (orig || 'Inputs').trim();
      th.innerHTML = '<span class="inputs-text">' + orig + '</span> <span class="inputs-count" aria-live="polite"></span>';
    }
    var span = th.querySelector('.inputs-count');
    function refresh() {
      var n = tbody.querySelectorAll('tr').length;
      span.textContent = n > 0 ? '(' + n.toLocaleString('en-GB') + ')' : '';
    }
    attached.add(table);
    refresh();
    new MutationObserver(refresh).observe(tbody, { childList: true });
  }
  function scan() {
    var tables = document.querySelectorAll('table');
    for (var i = 0; i < tables.length; i++) {
      if (tables[i].querySelector('th.gh-inputs')) attachTo(tables[i]);
    }
  }
  function init() {
    scan();
    new MutationObserver(function(muts) {
      var needsScan = false;
      for (var i = 0; i < muts.length && !needsScan; i++) {
        var added = muts[i].addedNodes;
        if (!added) continue;
        for (var j = 0; j < added.length; j++) {
          var n = added[j];
          if (n.nodeType !== 1) continue;
          if (n.tagName === 'TABLE' || (n.querySelector && n.querySelector('table'))) { needsScan = true; break; }
        }
      }
      if (needsScan) scan();
    }).observe(document.body, { childList: true, subtree: true });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();



/* MD-V2-PRE-INDICATORS-MARKER-MODULE-START */
// =============================================================================
// PRE-TEST INDICATORS TAB MODULE - Master Dashboard V2 (Session 25 rebuild)
// =============================================================================
// MD-V2-PRE-INDICATORS-MARKER - idempotency marker for patcher detection
//
// Session 25 (14-May-26) rebuild. Locked decisions D-MD-V2-49,-50,-55,-56,-57,-58.
// Reads the structured md_v2.pre_indicators object emitted by _md_v2_screens.py.
//
// 3 pre-test indicator patterns, each = AND of named constituent tests:
//   Pulling back within MT/LT uptrend (4 tests)  [Positive]
//   Basing (4 tests)                              [Positive]
//   Collapsing (2 tests)                          [Negative]
//
// Each pattern column block = [Rating][Score][test columns...] - mirrors Stages.
// Super-group banding: "Positive pre-test indicators" / "Negative pre-test indicators".
// =============================================================================

/* MD-V2-PRE-INDICATORS-MARKER-START */

(function() {
  'use strict';

  // MD-V2-PI-CHIPS-S25-MARKER: rating-tier multi-select chip filter (D-MD-V2-59).
  // piState.tierFilter holds, per pattern, an array of selected rating tiers.
  // Empty array = no tier filter for that pattern (shows all). Intra-pattern
  // selections OR-combine; cross-pattern selections AND-combine.
  var piState = {
    mode: { inputs: 'pct', tests: 'tick' },
    scope: 'all',
    tierFilter: { pulling_back_uptrend: [], basing: [], collapsing: [] },
    tint: 'none',
    port: 'off',
    sort: { col: 'company', dir: 'asc' }
  };

  // The 3 pre-test indicator patterns. testKey values must match the keys in
  // md_v2.pre_indicators[patternKey].tests emitted by _md_v2_screens.py.
  // tierLadder: the Option A rating tiers this pattern can take (D-MD-V2-55).
  // 2-test patterns (Collapsing) have no Plausible tier.
  var PI_PATTERNS = [
    {
      key: 'pulling_back_uptrend',
      label: 'Pulling back within MT/LT uptrend',
      shortLabel: 'Pulling back',
      supergroup: 'positive',
      tierLadder: ['Possible', 'Plausible', 'Probable'],
      tooltip: 'Stock in a real medium/long-term uptrend (50-day and 150-day moving averages still rising) that is currently pulling back (5-day and 10-day moving averages rolling over).',
      caption: 'A stock in a <span class="db">real medium/long-term uptrend</span> that is <span class="db">currently inside a pullback</span> &mdash; the dip you want to see in a healthy trend.<span class="intro">Four tests &mdash; all must pass:</span><span class="tline"><span class="tnum">(1)</span> Is the <u>50-day MA still rising</u> (higher today than yesterday)?</span><span class="tline"><span class="tnum">(2)</span> Is the <u>150-day MA still rising</u>?</span><span class="tline"><span class="tnum">(3)</span> Is the <u>5-day MA rolling over</u> (lower today than yesterday &mdash; confirms the pullback)?</span><span class="tline"><span class="tnum">(4)</span> Is the <u>10-day MA rolling over</u> too?</span>',
      total: 4,
      tests: [
        { key: 't1_50d_rising',       label: '50-day MA still rising',  tooltip: '50-day moving average is higher today than yesterday' },
        { key: 't2_150d_rising',      label: '150-day MA still rising', tooltip: '150-day moving average is higher today than yesterday' },
        { key: 't3_5d_rolling_over',  label: '5-day MA rolling over',   tooltip: '5-day moving average is lower today than yesterday - confirms we are inside a pullback' },
        { key: 't4_10d_rolling_over', label: '10-day MA rolling over',  tooltip: '10-day moving average is lower today than yesterday' }
      ]
    },
    {
      key: 'basing',
      label: 'Basing',
      shortLabel: 'Basing',
      supergroup: 'positive',
      tierLadder: ['Possible', 'Plausible', 'Probable'],
      tooltip: 'Price fell at least 15% from a recent swing high to a recent low (even if partly reclawed since), has stayed below that high for at least 20 trading days, sits above its 200-day MA, and the 200-day MA is still rising.',
      caption: 'A <span class="db">genuine base forming within an intact long-term uptrend</span> &mdash; the pause that resets a trend, not a breakdown.<span class="intro">Four tests &mdash; all must pass:</span><span class="tline"><span class="tnum">(1)</span> Did price fall <u>at least 15%</u> from its recent swing high (deepest drawdown, even if partly reclaimed since)?</span><span class="tline"><span class="tnum">(2)</span> Has price stayed <u>below that high for at least 20 trading days</u>?</span><span class="tline"><span class="tnum">(3)</span> Is price <u>above its 200-day MA</u>?</span><span class="tline"><span class="tnum">(4)</span> Is the 200-day MA <u>still rising month-on-month</u>?</span>',
      total: 4,
      tests: [
        { key: 't1_price_pullback_ge15',   label: 'Price pullback at least 15%',    tooltip: 'Deepest drawdown from the recent swing high reached at least 15% - even if price has since reclawed some of the loss' },
        { key: 't2_time_below_high_ge20d', label: 'Below high at least L20D',        tooltip: 'Price has been below the recent swing high for at least the last 20 trading days' },
        { key: 't3_price_above_200d',      label: 'Price above 200-day MA',          tooltip: 'Current price is above the 200-day moving average' },
        { key: 't4_200d_rising',           label: '200-day MA still rising',         tooltip: '200-day moving average is rising month-on-month (this month versus last month)' }
      ]
    },
    {
      key: 'collapsing',
      label: 'Collapsing',
      shortLabel: 'Collapsing',
      supergroup: 'negative',
      tierLadder: ['Possible', 'Probable'],
      tooltip: 'Price is 30% or more below its 52-week high AND has fallen at least 20% from its recent high.',
      caption: 'A stock in <span class="db">genuine breakdown</span> &mdash; not a dip, a decisive failure.<span class="intro">Two tests &mdash; both must pass:</span><span class="tline"><span class="tnum">(1)</span> Is price <u>30% or more below its 52-week high</u>?</span><span class="tline"><span class="tnum">(2)</span> Has price <u>fallen at least 20% from its recent high</u>?</span>',
      total: 2,
      tests: [
        { key: 't1_price_le_70pct_52wh', label: 'Price 30%+ below 52W high', tooltip: 'Current price is 30% or more below the 52-week high' },
        { key: 't2_pullback_ge20',       label: 'Pullback at least 20%',     tooltip: 'Recent pullback from the recent high is at least 20%' }
      ]
    }
  ];

  var PI_RATING_RANK = { 'Probable':4, 'Plausible':3, 'Possible':2, 'None':1 };
  var PI_RATING_CLS  = { 'Probable':'tint-prob', 'Plausible':'tint-pla', 'Possible':'tint-pos', 'None':'tint-none' };

  function buildCols() {
    var cols = [
      { id:'name',     label:'Company - Ticker',       sortKey:'company',         cls:'name-cell', kind:'input' },
      { id:'taxon',    label:'Industry - Sector',      sortKey:'sector',          cls:'taxon',     kind:'input' },
      { id:'price',    label:'Price',                  sortKey:'price',           cls:'num',       kind:'input' },
      { id:'high_52w', label:'52 week high',           sortKey:'high_52w',        cls:'num',       kind:'input' },
      { id:'low_52w',  label:'52 week low',            sortKey:'low_52w',         cls:'num',       kind:'input' },
      { id:'ma_150',   label:'150D MA', sortKey:'ma_150',          cls:'num',       kind:'input' },
      { id:'ma_200',   label:'200D MA', sortKey:'ma_200',          cls:'num',       kind:'input' },
      { id:'pullback', label:'Recent pullback',        sortKey:'recent_pullback', cls:'num',       kind:'input' }
    ];
    for (var p = 0; p < PI_PATTERNS.length; p++) {
      var pat = PI_PATTERNS[p];
      var gi = p + 1;
      cols.push({ id:'p'+gi+'_rating', label:'Rating', sortKey:pat.key+'__rating', cls:'grp-start-g'+gi+' pi-rating-col', kind:'rating', patternKey:pat.key });
      cols.push({ id:'p'+gi+'_score',  label:'Score',  sortKey:pat.key+'__score',  cls:'pi-score-col',                   kind:'score',  patternKey:pat.key });
      for (var t = 0; t < pat.tests.length; t++) {
        var test = pat.tests[t];
        cols.push({
          id: 'p'+gi+'t'+(t+1),
          label: test.label,
          sortKey: pat.key + '__' + test.key,
          cls: '',
          tooltip: test.tooltip,
          kind: 'test',
          patternKey: pat.key,
          testKey: test.key
        });
      }
    }
    return cols;
  }
  var PI_COLS = buildCols();

  function piPricesLookup() {
    if (window._piPricesByTicker) return window._piPricesByTicker;
    var out = {};
    var arr = (window.MASTER_DATA && MASTER_DATA.prices) || [];
    for (var i = 0; i < arr.length; i++) if (arr[i] && arr[i].ticker) out[arr[i].ticker] = arr[i];
    window._piPricesByTicker = out;
    return out;
  }
  function piLiveTickers() {
    var out = {};
    var inv = (window.MASTER_DATA && MASTER_DATA.positions && MASTER_DATA.positions.investments) || [];
    for (var i = 0; i < inv.length; i++) if (inv[i].ticker) out[inv[i].ticker] = true;
    return out;
  }
  function piLiveSectors() {
    var out = {}, t, prices = piPricesLookup(), tickers = piLiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.sector) out[p.sector] = true; }
    return out;
  }
  function piLiveIndustries() {
    var out = {}, t, prices = piPricesLookup(), tickers = piLiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.industry) out[p.industry] = true; }
    return out;
  }

  function piPatternRec(row, patternKey) {
    var pi = row.md_v2 && row.md_v2.pre_indicators;
    return (pi && pi[patternKey]) || null;
  }
  function piEvalTest(row, patternKey, testKey) {
    var rec = piPatternRec(row, patternKey);
    if (!rec || !rec.tests) return false;
    return !!rec.tests[testKey];
  }
  function piRowRating(row, patternKey) {
    var rec = piPatternRec(row, patternKey);
    return rec ? (rec.rating || 'None') : 'None';
  }

  function piGetRows() {
    var raw = (window.MASTER_DATA && MASTER_DATA.filters) || [];
    var prices = piPricesLookup();
    var live = piLiveTickers(), liveS = piLiveSectors(), liveI = piLiveIndustries();
    var rows = [];
    for (var i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || !s.md_v2 || !s.md_v2.pre_indicators) continue;
      var p = prices[s.ticker] || {};
      var mas = p.mas || {};
      rows.push({
        ticker: s.ticker, company: p.company_name || s.ticker,
        sector: p.sector || '', industry: p.industry || '',
        price: p.price, high_52w: p.high_52w, low_52w: p.low_52w,
        recent_pullback: p.recent_pullback_pct,
        swing_high: p.swing_high,
        ma_150: mas['150D'], ma_200: mas['200D'],
        md_v2: s.md_v2,
        is_live: !!live[s.ticker],
        sector_in_portfolio: !!liveS[p.sector],
        industry_in_portfolio: !!liveI[p.industry]
      });
    }
    return rows;
  }

  // Per-pattern qualifying count (all tests pass).
  function piPatternCounts(rows) {
    var c = {};
    for (var pi = 0; pi < PI_PATTERNS.length; pi++) c[PI_PATTERNS[pi].key] = 0;
    for (var i = 0; i < rows.length; i++) {
      for (var p = 0; p < PI_PATTERNS.length; p++) {
        var rec = piPatternRec(rows[i], PI_PATTERNS[p].key);
        if (rec && rec.qualifies) c[PI_PATTERNS[p].key]++;
      }
    }
    return c;
  }
  // Per-pattern histogram of how many stocks pass exactly k tests (D-MD-V2-57).
  function piPassHistogram(rows, patternKey, total) {
    var h = [];
    for (var k = 0; k <= total; k++) h[k] = 0;
    for (var i = 0; i < rows.length; i++) {
      var rec = piPatternRec(rows[i], patternKey);
      var cnt = rec ? (rec.count || 0) : 0;
      if (cnt >= 0 && cnt <= total) h[cnt]++;
    }
    return h;
  }
  // MD-V2-PI-CHIPS-S25-MARKER: per-pattern, per-tier live counts (D-MD-V2-59).
  // Counted against the SCOPE-filtered row set (passed in) so chip counts
  // reflect what is currently in play, not the whole universe.
  function piTierCounts(rows, patternKey) {
    var c = { 'Possible':0, 'Plausible':0, 'Probable':0, 'None':0 };
    for (var i = 0; i < rows.length; i++) {
      var r = piRowRating(rows[i], patternKey);
      if (c[r] != null) c[r]++;
    }
    return c;
  }

  function piFmtNum(n) {
    if (n == null || isNaN(n)) return '-';
    var abs = Math.abs(n);
    var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);
    if (Math.abs(n - Math.round(n)) < 1e-9) dp = 0; /* MD-V2-S40-FMTNUM-INT-FIX-pi; S41 tolerance */
    var f = abs.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });
    return n < 0 ? '(' + f + ')' : f;
  }
  function piFmtPct(p) {
    if (p == null || isNaN(p)) return '-';
    var r = Math.round(p), abs = Math.abs(r);
    return r < 0 ? '(' + abs + ')%' : r + '%';
  }
  function piColourForIntensity(i) {
    if (i >= 0.6) return '#0F6E56';
    if (i >= 0.25) return '#1D9E75';
    if (i >= 0.05) return '#5DCAA5';
    if (i <= -0.6) return '#A32D2D';
    if (i <= -0.25) return '#E24B4A';
    if (i <= -0.05) return '#F09595';
    return '#888';
  }
  function piInputCell(row, key, extraCls) {
    extraCls = extraCls || '';
    var v = row[key];
    if (key === 'price') return '<td class="num ' + extraCls + '">' + piFmtNum(v) + '</td>';
    if (key === 'recent_pullback') {
      if (v == null || isNaN(v)) return '<td class="num ' + extraCls + '">-</td>';
      var pctVal = v * 100;
      var pi_intensity = Math.max(-1, Math.min(1, (pctVal - 5) / 20));
      var col = piColourForIntensity(-pi_intensity);
      return '<td class="num ' + extraCls + '" style="color:' + col + '">' + Math.round(pctVal) + '%</td>';
    }
    if (v == null || row.price == null) return '<td class="num ' + extraCls + '">-</td>';
    var pct = (row.price - v) / v * 100;
    var intensity = 0;
    if (key === 'high_52w') intensity = Math.max(-1, Math.min(1, (-pct - 5) / 20));
    else if (key === 'low_52w') intensity = Math.max(-1, Math.min(1, (pct - 20) / 30));
    else if (key === 'ma_150' || key === 'ma_200') intensity = Math.max(-1, Math.min(1, pct / 10));
    var colour = piColourForIntensity(intensity);
    var text = (piState.mode.inputs === 'pct') ? piFmtPct(pct) : piFmtNum(v);
    return '<td class="num ' + extraCls + '" style="color:' + colour + '">' + text + '</td>';
  }

  /* MD-V2-WAVE4-TEST-VALUES-TOGGLE-MARKER */
  function piTestValueFor(row, col) {
    var rec = piPatternRec(row, col.patternKey);
    var tv = rec && rec.test_values;
    if (!tv || !(col.testKey in tv)) return '\u2014';
    var v = tv[col.testKey];
    if (v === null || v === undefined) return '\u2014';
    if (typeof v === 'string') return v;
    if (typeof v === 'number') {
      if (isNaN(v)) return '\u2014';
      if (Math.abs(v) <= 1.5 && v !== Math.round(v)) return piFmtPct(v * 100);
      return piFmtNum(v);
    }
    return String(v);
  }
  function piTestCell(row, col) {
    var pass = piEvalTest(row, col.patternKey, col.testKey);
    var extra = col.cls || '';
    if (piState.mode.tests === 'val') {
      var v = piTestValueFor(row, col);
      var colour = pass ? piColourForIntensity(0.7) : piColourForIntensity(-0.4);
      return '<td class="test-val pi-' + (pass ? 'pass' : 'fail') + ' ' + extra + '" style="color:' + colour + '">' + v + '</td>';
    }
    if (pass) return '<td class="pi-pass ' + extra + '"><span class="tick">' + String.fromCharCode(10003) + '</span></td>';
    return '<td class="pi-fail ' + extra + '">.</td>';
  }
  function piRatingCell(row, col) {
    var rating = piRowRating(row, col.patternKey);
    var rcls = PI_RATING_CLS[rating] || 'tint-none';
    return '<td class="' + (col.cls || '') + ' pi-rating-cell ' + rcls + '"><span class="pi-pill pi-pill-' + rcls + '">' + rating + '</span></td>';
  }
  function piScoreCell(row, col) {
    var rec = piPatternRec(row, col.patternKey);
    var cnt = rec ? (rec.count || 0) : 0;
    var tot = rec ? (rec.total || 0) : 0;
    var s = '';
    for (var i = 0; i < tot; i++) s += '<span class="pip ' + (i < cnt ? 'on' : '') + '"></span>';
    return '<td class="' + (col.cls || '') + ' pi-score-cell"><div class="pi-pip-row">' + s +
           '<span class="pi-score-num">' + cnt + '/' + tot + '</span></div></td>';
  }

  function piHashColor(label, alpha) {
    if (!label) return null;
    var h = 0;
    for (var i = 0; i < label.length; i++) h = (h * 31 + label.charCodeAt(i)) & 0xffff;
    return 'hsla(' + (h % 360) + ', 35%, 55%, ' + alpha + ')';
  }
  function piPortfolioInfo(row) {
    if (row.is_live) return { color:'#1b5e20', bg:'rgba(27,94,32,0.10)', bgHover:'rgba(27,94,32,0.14)' };
    if (row.sector_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.05)', bgHover:'rgba(27,94,32,0.08)' };
    if (row.industry_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.025)', bgHover:'rgba(27,94,32,0.05)' };
    return null;
  }

  function piGetSortVal(row, key) {
    if (key.indexOf('__') > 0) {
      var parts = key.split('__');
      var patternKey = parts[0], sub = parts[1];
      var rec = piPatternRec(row, patternKey);
      if (sub === 'rating') return rec ? (PI_RATING_RANK[rec.rating] || 0) : 0;
      if (sub === 'score')  return rec ? (rec.count || 0) : 0;
      return piEvalTest(row, patternKey, sub) ? 1 : 0;
    }
    if (key === 'recent_pullback') {
      return row.recent_pullback == null ? -Infinity : row.recent_pullback;
    }
    var PCT_KEYS = ['high_52w','low_52w','ma_150','ma_200'];
    if (PCT_KEYS.indexOf(key) > -1 && piState.mode.inputs === 'pct') {
      var ref = row[key];
      if (ref == null || row.price == null || ref === 0) return -Infinity;
      return (row.price - ref) / ref * 100;
    }
    if (key in row) return row[key];
    return 0;
  }
  function piOnSort(key) {
    if (piState.sort.col === key) piState.sort.dir = piState.sort.dir === 'desc' ? 'asc' : 'desc';
    else piState.sort = { col: key, dir: key === 'company' ? 'asc' : 'desc' };
    piBuildHeaderRow();
    piRenderRows();
  }

  function piBuildHeaderRow() {
    var tr = document.getElementById('pi-col-header-row');
    if (!tr) return;
    var h = '';
    for (var i = 0; i < PI_COLS.length; i++) {
      var c = PI_COLS[i];
      var isSort = piState.sort.col === c.sortKey;
      var arrow = isSort
        ? '<span class="sort-arrow">' + (piState.sort.dir === 'desc' ? String.fromCharCode(9660) : String.fromCharCode(9650)) + '</span>'
        : '<span class="sort-placeholder"></span>';
      var title = c.tooltip || c.label;
      h += '<th class="' + (c.cls || '') + '" data-sort-key="' + c.sortKey + '" title="' + title + '">' +
           '<span class="hd"><span class="lbl">' + c.label + '</span>' + arrow + '</span></th>';
    }
    tr.innerHTML = h;
  }

  // MD-V2-PI-CHIPS-S25-MARKER: render pattern tiles + the rating-tier chip row.
  // The `scopeRows` argument is the SCOPE-filtered set (so chip counts and the
  // pass-count breakdown reflect the active scope), NOT the tier-filtered set.
  function piPatternTiles(scopeRows) {
    var tiles = document.getElementById('pi-pattern-tiles');
    if (!tiles) return;
    var counts = piPatternCounts(scopeRows);
    var total = scopeRows.length;
    var tintCls = { 'pulling_back_uptrend':'pi-tile-pullback', 'basing':'pi-tile-basing', 'collapsing':'pi-tile-collapsing' };
    var stripCls = { 'pulling_back_uptrend':'pi-strip-pullback', 'basing':'pi-strip-basing', 'collapsing':'pi-strip-collapsing' };
    var h = '';
    for (var i = 0; i < PI_PATTERNS.length; i++) {
      var pat = PI_PATTERNS[i];
      var cnt = counts[pat.key] || 0;
      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;
      var sel = piState.tierFilter[pat.key] || [];
      var anySel = sel.length > 0;
      // headline = filtered total when a tier filter is active, else the qualifying count
      var tierCounts = piTierCounts(scopeRows, pat.key);
      var headline = cnt, headSub = 'of ' + total.toLocaleString('en-GB') + ' &middot; ' + pct + '%';
      if (anySel) {
        var ft = 0;
        for (var z = 0; z < sel.length; z++) ft += (tierCounts[sel[z]] || 0);
        headline = ft;
        headSub = sel.join(' + ') + ' &middot; filtered';
      }
      // pass-count breakdown line (D-MD-V2-57)
      var hist = piPassHistogram(scopeRows, pat.key, pat.total);
      var breakdown = '';
      for (var k = 1; k <= pat.total; k++) {
        if (k > 1) breakdown += ' &middot; ';
        breakdown += k + ' of ' + pat.total + ': ' + (hist[k] || 0).toLocaleString('en-GB');
      }
      // rating-tier chip row (D-MD-V2-59)
      var chips = '';
      for (var c = 0; c < 3; c++) {  /* MD-V2-S37-FOLLOWUP-MARKER: canonical 3-tier chip set */
        var tier = ['Possible','Plausible','Probable'][c];
        var on = sel.indexOf(tier) > -1;
        var tc = tierCounts[tier] || 0;
        chips += '<span class="pi-tier-chip pi-chip-' + tintCls[pat.key].replace('pi-tile-','') +
                 (on ? ' on' : '') + '" data-pattern="' + pat.key + '" data-tier="' + tier + '">' +
                 tier + ' ' + tc.toLocaleString('en-GB') + (on ? ' ' + String.fromCharCode(10003) : '') + '</span>';
      }
      var activeCls = anySel ? ' active' : '';
      h += '<div class="rating-tile ' + tintCls[pat.key] + activeCls + '" data-pattern="' + pat.key + '" title="' + pat.tooltip + '">' +
           '<div class="rt-label">' + pat.shortLabel + '</div>' +
           '<div class="rt-count">' + headline.toLocaleString('en-GB') + '</div>' +
           '<div class="rt-sub">' + headSub + '</div>' +
           '<div class="rt-breakdown">' + breakdown + '</div>' +
           '<div class="pi-tier-chips" data-pattern="' + pat.key + '">' + chips + '</div>' +
           '<div class="rt-strip ' + stripCls[pat.key] + '"></div>' +
           '</div>';
    }
    tiles.innerHTML = h;
  }

  function piUpdateScopeCounts(rows) {
    function set(id, n) { var el = document.getElementById(id); if (el) el.textContent = '(' + n + ')'; }
    set('pi-cnt-all',      rows.length);
    set('pi-cnt-live',     rows.filter(function(r){ return r.is_live; }).length);
    set('pi-cnt-sector',   rows.filter(function(r){ return r.sector_in_portfolio; }).length);
    set('pi-cnt-industry', rows.filter(function(r){ return r.industry_in_portfolio; }).length);
  }

  // MD-V2-PI-CHIPS-S25-MARKER: apply scope, then the rating-tier filter.
  // Tier filter: for each pattern with a non-empty selected-tier list, the
  // row's rating for that pattern must be in the list (intra-pattern OR).
  // Patterns with non-empty lists AND-combine. Empty list = pattern ignored.
  function piApplyScope(all) {
    var rows = all.slice();
    if (piState.scope === 'live') rows = rows.filter(function(r){ return r.is_live; });
    else if (piState.scope === 'sector') rows = rows.filter(function(r){ return r.sector_in_portfolio; });
    else if (piState.scope === 'industry') rows = rows.filter(function(r){ return r.industry_in_portfolio; });
    return rows;
  }
  function piApplyTierFilter(rows) {
    var active = [];
    for (var p = 0; p < PI_PATTERNS.length; p++) {
      var k = PI_PATTERNS[p].key;
      var sel = piState.tierFilter[k] || [];
      if (sel.length > 0) active.push({ key: k, tiers: sel });
    }
    if (active.length === 0) return rows;
    return rows.filter(function(r) {
      for (var a = 0; a < active.length; a++) {
        var rating = piRowRating(r, active[a].key);
        if (active[a].tiers.indexOf(rating) === -1) return false;
      }
      return true;
    });
  }

  function piRenderRows() {
    var tbody = document.getElementById('pi-tbody');
    if (!tbody) return;
    var all = piGetRows();
    var scopeRows = piApplyScope(all);
    piUpdateScopeCounts(all);
    piPatternTiles(scopeRows);
    var rows = piApplyTierFilter(scopeRows);
    rows.sort(function(a,b) {
      var va = piGetSortVal(a, piState.sort.col), vb = piGetSortVal(b, piState.sort.col);
      var cmp = (typeof va === 'string') ? va.localeCompare(vb) : (va || 0) - (vb || 0);
      if (cmp === 0) cmp = a.ticker.localeCompare(b.ticker);
      return piState.sort.dir === 'desc' ? -cmp : cmp;
    });
    var html = '';
    for (var i = 0; i < rows.length; i++) {
      var s = rows[i];
      var styles = [], cls = [];
      if (piState.tint === 'industry') { styles.push('--tint-bg: ' + piHashColor(s.industry, 0.16)); cls.push('tint-row'); }
      else if (piState.tint === 'sector') { styles.push('--tint-bg: ' + piHashColor(s.sector, 0.16)); cls.push('tint-row'); }
      if (piState.port === 'on') {
        var pinf = piPortfolioInfo(s);
        if (pinf) {
          styles.push('--portfolio-color: ' + pinf.color);
          styles.push('--portfolio-bg: ' + pinf.bg);
          styles.push('--portfolio-bg-hover: ' + pinf.bgHover);
          cls.push('portfolio-band'); cls.push('portfolio-tint');
        }
      }
      var styleAttr = styles.length ? ' style="' + styles.join(';') + '"' : '';
      var clsAttr = cls.length ? ' class="' + cls.join(' ') + '"' : '';
      var liveDot = s.is_live ? '<span class="live-dot">' + String.fromCharCode(9679) + '</span>' : '';
      html += '<tr' + clsAttr + styleAttr + '>' +
        '<td class="name-cell"><div class="co">' + liveDot + (s.company || s.ticker) + '</div><div class="tk">' + s.ticker + '</div></td>' +
        '<td class="taxon"><div class="ind">' + (s.industry || '') + '</div><div class="sec">' + (s.sector || '') + '</div></td>' +
        piInputCell(s, 'price') + piInputCell(s, 'high_52w') + piInputCell(s, 'low_52w') +
        piInputCell(s, 'ma_150') + piInputCell(s, 'ma_200') + piInputCell(s, 'recent_pullback');
      for (var j = 8; j < PI_COLS.length; j++) {
        var col = PI_COLS[j];
        if (col.kind === 'rating') html += piRatingCell(s, col);
        else if (col.kind === 'score') html += piScoreCell(s, col);
        else html += piTestCell(s, col);
      }
      html += '</tr>';
    }
    tbody.innerHTML = html;
  }

  function piSetMode(kind, val) {
    piState.mode[kind] = val;
    var btns = document.querySelectorAll('button[data-pi-grp="' + kind + '"]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-pi-val') === val);
    piRenderRows();
  }
  function piSetScope(s) {
    piState.scope = s;
    var btns = document.querySelectorAll('button[data-pi-scope]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-pi-scope') === s);
    piRenderRows();
  }
  function piSetTint(t) {
    piState.tint = t;
    var btns = document.querySelectorAll('button[data-pi-tint]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-pi-tint') === t);
    piRenderRows();
  }
  function piSetPort(p) {
    piState.port = p;
    var btns = document.querySelectorAll('button[data-pi-port]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-pi-port') === p);
    piRenderRows();
  }
  // MD-V2-PI-CHIPS-S25-MARKER: toggle a single rating tier for a pattern.
  function piToggleTier(patternKey, tier) {
    var sel = piState.tierFilter[patternKey] || [];
    var idx = sel.indexOf(tier);
    if (idx > -1) sel.splice(idx, 1);
    else sel.push(tier);
    piState.tierFilter[patternKey] = sel;
    piRenderRows();
  }
  // MD-V2-PI-CHIPS-S25-MARKER: tile-body click selects ALL tiers for a pattern
  // (D-MD-V2-59 Option A). If all are already selected, clear them (toggle off).
  function piSelectAllTiers(patternKey) {
    // MD-V2-WAVE1-FROZEN-HEADERS-MARKER: tile-body click selects ONLY the Probable tier
    // (D-MD-V2-74). If exactly ['Probable'] is already selected,
    // clear it (toggle off). Tier chips remain direct multi-select.
    var pat = null;
    for (var p = 0; p < PI_PATTERNS.length; p++) if (PI_PATTERNS[p].key === patternKey) pat = PI_PATTERNS[p];
    if (!pat) return;
    var sel = piState.tierFilter[patternKey] || [];
    var probable = (pat.tierLadder.indexOf('Probable') > -1) ? 'Probable'
                   : pat.tierLadder[pat.tierLadder.length - 1];
    var onlyProbable = (sel.length === 1 && sel[0] === probable);
    piState.tierFilter[patternKey] = onlyProbable ? [] : [probable];
    piRenderRows();
  }
  window.piSetMode = piSetMode;
  window.piSetScope = piSetScope;
  window.piSetTint = piSetTint;
  window.piSetPort = piSetPort;
  window.piToggleTier = piToggleTier;
  window.piSelectAllTiers = piSelectAllTiers;
  window.piOnSort = piOnSort;

  function piBuildScaffold() {
    var host = document.getElementById('tab-pre_indicators');
    if (!host) return false;
    if (host.querySelector('#pi-main-table')) return true;

    var colgroupHtml = '<col class="c-name"><col class="c-taxon">' +
                       '<col class="c-price"><col class="c-52wh"><col class="c-52wl">' +
                       '<col class="c-ma150"><col class="c-ma200"><col class="c-pullback">';
    var inputsColspan = 8;

    var superHtml = '<th class="gh-inputs sg-spacer" colspan="' + inputsColspan + '"></th>';
    var groupHtml = '<th class="gh-inputs" colspan="' + inputsColspan + '">Inputs</th>';

    var posCols = 0, negCols = 0;
    for (var sp = 0; sp < PI_PATTERNS.length; sp++) {
      var cspan = 2 + PI_PATTERNS[sp].tests.length;
      if (PI_PATTERNS[sp].supergroup === 'positive') posCols += cspan;
      else negCols += cspan;
    }
    superHtml += '<th class="sg-positive" colspan="' + posCols + '">Positive pre-test indicators</th>';
    superHtml += '<th class="sg-negative" colspan="' + negCols + '">Negative pre-test indicators</th>';

    for (var p = 0; p < PI_PATTERNS.length; p++) {
      var pat = PI_PATTERNS[p];
      var gi = p + 1;
      var n = pat.tests.length;
      colgroupHtml += '<col class="c-rating"><col class="c-score">';
      for (var t = 0; t < n; t++) colgroupHtml += '<col class="c-test">';
      groupHtml += '<th class="gh-g' + gi + ' grp-start-g' + gi + '" colspan="' + (n + 2) + '">' + pat.label + '</th>';
    }

    var captionsHtml = '';
    for (var cp = 0; cp < PI_PATTERNS.length; cp++) {
      var cpat = PI_PATTERNS[cp];
      captionsHtml += '<div class="gcap gcap-g' + (cp+1) + '"><b>' + cpat.label + '</b>' + cpat.caption + '</div>';
    }

    var html = '' +
      '<div class="s1-intro">Pre-test indicators are three leading price-action patterns drawn directly from price and moving-average data. Each pattern is the AND of its named constituent tests, shown below as individual tick columns alongside a per-pattern rating and score. The two positive patterns (Pulling back within a medium/long-term uptrend, and Basing) sit under one super-group; Collapsing sits under the negative super-group. Each tile has a rating-tier filter row: click a tier chip to show only stocks at that tier, or click the tile body to select all tiers. Tier selections within a pattern combine as OR; selections across patterns combine as AND.</div>' +
      '<div class="controls s1-controls">' +
        '<div class="ctrl-grp"><span class="ctrl-label">Inputs</span>' +
          '<button class="toggle-btn active" data-pi-grp="inputs" data-pi-val="pct" onclick="piSetMode(\'inputs\',\'pct\')">show as %</button>' +
          '<button class="toggle-btn" data-pi-grp="inputs" data-pi-val="raw" onclick="piSetMode(\'inputs\',\'raw\')">show as numbers</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Tests</span>' +  /* MD-V2-WAVE4-TEST-VALUES-TOGGLE-MARKER */
          '<button class="toggle-btn active" data-pi-grp="tests" data-pi-val="tick" onclick="piSetMode(\'tests\',\'tick\')">show ticks</button>' +
          '<button class="toggle-btn" data-pi-grp="tests" data-pi-val="val" onclick="piSetMode(\'tests\',\'val\')">show test values</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Scope</span>' +
          '<button class="toggle-btn active" data-pi-scope="all" onclick="piSetScope(\'all\')">All <span id="pi-cnt-all"></span></button>' +
          '<button class="toggle-btn" data-pi-scope="live" onclick="piSetScope(\'live\')">Live <span id="pi-cnt-live"></span></button>' +
          '<button class="toggle-btn" data-pi-scope="sector" onclick="piSetScope(\'sector\')">Sectors <span id="pi-cnt-sector"></span></button>' +
          '<button class="toggle-btn" data-pi-scope="industry" onclick="piSetScope(\'industry\')">Industries <span id="pi-cnt-industry"></span></button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Peers</button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Cohorts</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Colour by</span>' +
          '<button class="toggle-btn active" data-pi-tint="none" onclick="piSetTint(\'none\')">Off</button>' +
          '<button class="toggle-btn" data-pi-tint="industry" onclick="piSetTint(\'industry\')">Industry</button>' +
          '<button class="toggle-btn" data-pi-tint="sector" onclick="piSetTint(\'sector\')">Sector</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Portfolio tint</span>' +
          '<button class="toggle-btn active" data-pi-port="off" onclick="piSetPort(\'off\')">Off</button>' +
          '<button class="toggle-btn" data-pi-port="on" onclick="piSetPort(\'on\')">On</button>' +
        '</div>' +
      '</div>' +
      '<div class="rating-tiles s1-rating-tiles" id="pi-pattern-tiles"></div>' +
      '<div class="group-captions">' + captionsHtml + '</div>' +
      '<div class="table-wrap"><div class="v2-hscroll">' +  /* MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER */
        '<table class="data-table" id="pi-main-table">' +
          '<colgroup>' + colgroupHtml + '</colgroup>' +
          '<thead>' +
            '<tr class="super-group-row">' + superHtml + '</tr>' +
            '<tr class="group-header-row">' + groupHtml + '</tr>' +
            '<tr class="col-header-row" id="pi-col-header-row"></tr>' +
          '</thead>' +
          '<tbody id="pi-tbody"></tbody>' +
        '</table>' +
      '</div></div>';  /* MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER */
    host.innerHTML = html;
    // MD-V2-PI-CHIPS-S25-MARKER: tile click delegation - a chip click toggles
    // that tier; a click anywhere else on the tile selects all tiers (Option A).
    var tiles = document.getElementById('pi-pattern-tiles');
    if (tiles) {
      tiles.addEventListener('click', function(e) {
        var chip = e.target.closest('.pi-tier-chip');
        if (chip) {
          var cp = chip.getAttribute('data-pattern');
          var ct = chip.getAttribute('data-tier');
          if (cp && ct) piToggleTier(cp, ct);
          return;
        }
        var tile = e.target.closest('.rating-tile');
        if (!tile) return;
        var k = tile.getAttribute('data-pattern');
        if (k) piSelectAllTiers(k);
      });
    }
    var hdr = document.getElementById('pi-col-header-row');
    if (hdr) {
      hdr.addEventListener('click', function(e) {
        var th = e.target.closest('th');
        if (!th) return;
        var key = th.getAttribute('data-sort-key');
        if (key) piOnSort(key);
      });
    }
    return true;
  }

  function renderPreIndicators() {
    // MD-V2-MDJUMP-CONSUMER-S27-MARKER: Master Overview cell-click handoff. Read
    // window._mdJump once; if it targets this tab, arm the chip filter
    // for the named pattern, then clear it so it fires exactly once.
    (function(){
      var j = window._mdJump;
      if (j && j.tab === 'pre_indicators') {
        if (j.patternKey && j.tier && piState.tierFilter &&
            piState.tierFilter.hasOwnProperty(j.patternKey)) {
          piState.tierFilter[j.patternKey] = [j.tier];
        }
        window._mdJump = null;
      }
    })();
    if (!piBuildScaffold()) return;
    piBuildHeaderRow();
    piRenderRows();
    if (window.measureV2Ribbon) measureV2Ribbon();  /* MD-V2-WAVE1B-STICKY-CORRECTIVE-MARKER */
  }
  window.renderPreIndicators = renderPreIndicators;

})();

/* MD-V2-PRE-INDICATORS-MARKER-END */
/* MD-V2-PRE-INDICATORS-MARKER-MODULE-END */
/* MD-V2-POST-INDICATORS-MARKER-MODULE-START */
// =============================================================================
// POST-INDICATORS TAB MODULE - Master Dashboard V2
// =============================================================================
// MD-V2-POST-INDICATORS-MARKER - idempotency marker for patcher detection
//
// Post-indicators = 5 trailing binary patterns from _md_v2_screens.py.
// Each pattern is the AND of constituent tests; each test gets its own column.
//
// PATTERNS AND CONSTITUENT TESTS:
//   Breakout (bull, 2 tests):
//     - Price > 1.08x 5D MA
//     - Up-volume >= 1.10x down-volume
//   Advancing (bull, 3 tests):
//     - Price > 20D MA
//     - 20D MA rising (vs 20D_prev)
//     - NOT in breakout (catch-all gate)
//   Breakdown 50D (bear, 2 tests):
//     - Price < 50D MA
//     - Price_prev was at/above 50D_prev (recently above)
//   Breakdown 150D (bear, 2 tests):
//     - Price < 150D MA
//     - Price_prev was at/above 150D_prev
//   Breakdown 200D (bear, 2 tests):
//     - Price < 200D MA
//     - Price_prev was at/above 200D_prev
// =============================================================================

/* MD-V2-POST-INDICATORS-MARKER-START */

(function() {
  'use strict';

  // MD-V2-S26-CHIPS-MARKER: po tab module - rating-tier multi-select chip
  // filter + per-pattern rating/score/test columns, structured identically to
  // the proven Pre-test indicators module. Reads md_v2.post_indicators.

  var poState = {
    mode: { inputs: 'pct', tests: 'tick' },
    scope: 'all',
    tierFilter: {},
    tint: 'none',
    port: 'off',
    sort: { col: 'company', dir: 'asc' }
  };

  var PO_PATTERNS = [
  {
    "key": "breakout",
    "label": "Breakout",
    "shortLabel": "Breakout",
    "supergroup": "bull",
    "tierLadder": [
      "Possible",
      "Probable"
    ],
    "total": 2,
    "tooltip": "Price more than 8% above its 5-day average, with up-day volume at least 10% above down-day volume.",
    "caption": "A <span class='db'>confirmed upside break</span> &mdash; price thrusting clear of its short-term average on real buying.<span class='intro'>Two tests &mdash; both must pass:</span><span class='tline'><span class='tnum'>(1)</span> Is price <u>more than 8% above its 5-day MA</u>?</span><span class='tline'><span class='tnum'>(2)</span> Is recent <u>up-day volume at least 10% above down-day volume</u>?</span>",
    "tests": [
      {
        "key": "t1_price_gt_108pct_5dma",
        "label": "Price 8%+ above 5-day MA",
        "tooltip": "Current price is more than 8% above the 5-day moving average"
      },
      {
        "key": "t2_updown_vol_ge110",
        "label": "Up-volume 10%+ above down-volume",
        "tooltip": "Recent up-day trading volume is at least 10% higher than down-day volume"
      }
    ]
  },
  {
    "key": "advancing",
    "label": "Advancing",
    "shortLabel": "Advancing",
    "supergroup": "bull",
    "tierLadder": [
      "Possible",
      "Plausible",
      "Probable"
    ],
    "total": 3,
    "tooltip": "Price above its 20-day average and the 20-day average rising - a steady advance without a breakout spike.",
    "caption": "A <span class='db'>steady advance without a breakout spike</span> &mdash; grinding higher rather than gapping.<span class='intro'>Three tests (the third is logic-only, not shown as a column):</span><span class='tline'><span class='tnum'>(1)</span> Is price <u>above its 20-day MA</u>?</span><span class='tline'><span class='tnum'>(2)</span> Is the <u>20-day MA rising</u>?</span><span class='tline'><span class='tnum'>(3)</span> Is the stock <u>not currently in a Breakout</u>?</span>",
    "tests": [
      {
        "key": "t1_price_above_20dma",
        "label": "Price above 20-day MA",
        "tooltip": "Current price is above the 20-day moving average"
      },
      {
        "key": "t2_20dma_rising",
        "label": "20-day MA rising",
        "tooltip": "20-day moving average is higher today than yesterday"
      }
    ]
  },
  {
    "key": "breakdown_50D",
    "label": "Negatively breaking through ST trend (50D MA)",
    "shortLabel": "Negatively breaking through ST trend (50D MA)",
    "supergroup": "bear",
    "tierLadder": [
      "Possible",
      "Probable"
    ],
    "total": 2,
    "tooltip": "Price has dropped below its 50-day average, having been at or above it on the prior bar.",
    "caption": "A <span class='db'>fresh break below medium-term support</span> &mdash; the first crack, caught as it happens.<span class='intro'>Two tests &mdash; both must pass:</span><span class='tline'><span class='tnum'>(1)</span> Is price <u>below its 50-day MA</u>?</span><span class='tline'><span class='tnum'>(2)</span> Was price <u>at or above the 50-day MA on the prior bar</u> (confirming this is a fresh break)?</span>",
    "tests": [
      {
        "key": "t1_price_below_50dma",
        "label": "Price below 50-day MA",
        "tooltip": "Current price is below the 50-day moving average"
      },
      {
        "key": "t2_prev_at_or_above_50dma",
        "label": "Was at/above 50-day MA",
        "tooltip": "Price was at or above the 50-day moving average on the prior bar - confirms this is a fresh break"
      }
    ]
  },
  {
    "key": "breakdown_150D",
    "label": "Negatively breaking through MT trend (150D MA)",
    "shortLabel": "Negatively breaking through MT trend (150D MA)",
    "supergroup": "bear",
    "tierLadder": [
      "Possible",
      "Probable"
    ],
    "total": 2,
    "tooltip": "Price has dropped below its 150-day average, having been at or above it on the prior bar.",
    "caption": "A <span class='db'>fresh break below the medium/long-term trend</span> &mdash; a more serious failure than the 50-day break.<span class='intro'>Two tests &mdash; both must pass:</span><span class='tline'><span class='tnum'>(1)</span> Is price <u>below its 150-day MA</u>?</span><span class='tline'><span class='tnum'>(2)</span> Was price <u>at or above the 150-day MA on the prior bar</u>?</span>",
    "tests": [
      {
        "key": "t1_price_below_150dma",
        "label": "Price below 150-day MA",
        "tooltip": "Current price is below the 150-day moving average"
      },
      {
        "key": "t2_prev_at_or_above_150dma",
        "label": "Was at/above 150-day MA",
        "tooltip": "Price was at or above the 150-day moving average on the prior bar"
      }
    ]
  },
  {
    "key": "breakdown_200D",
    "label": "Negatively breaking through LT trend (200D MA)",
    "shortLabel": "Negatively breaking through LT trend (200D MA)",
    "supergroup": "bear",
    "tierLadder": [
      "Possible",
      "Probable"
    ],
    "total": 2,
    "tooltip": "Price has dropped below its 200-day average, having been at or above it on the prior bar.",
    "caption": "A <span class='db'>fresh break below the long-term trend</span> &mdash; the most serious of the three breakdowns.<span class='intro'>Two tests &mdash; both must pass:</span><span class='tline'><span class='tnum'>(1)</span> Is price <u>below its 200-day MA</u>?</span><span class='tline'><span class='tnum'>(2)</span> Was price <u>at or above the 200-day MA on the prior bar</u>?</span>",
    "tests": [
      {
        "key": "t1_price_below_200dma",
        "label": "Price below 200-day MA",
        "tooltip": "Current price is below the 200-day moving average"
      },
      {
        "key": "t2_prev_at_or_above_200dma",
        "label": "Was at/above 200-day MA",
        "tooltip": "Price was at or above the 200-day moving average on the prior bar"
      }
    ]
  }
];
  var PO_SUPERGROUPS = [{"key": "bull", "label": "Bullish post-test indicators", "cls": "sg-positive"}, {"key": "bear", "label": "Bearish post-test indicators", "cls": "sg-negative"}];
  var PO_TONE = {"breakout": "pi-tile-pullback", "advancing": "pi-tile-basing", "breakdown_50D": "pi-tile-collapsing", "breakdown_150D": "pi-tile-amber", "breakdown_200D": "pi-tile-navy"};
  var PO_STRIP = {"breakout": "pi-strip-pullback", "advancing": "pi-strip-basing", "breakdown_50D": "pi-strip-collapsing", "breakdown_150D": "pi-strip-amber", "breakdown_200D": "pi-strip-navy"};
  var PO_CHIP = {"breakout": "pullback", "advancing": "basing", "breakdown_50D": "collapsing", "breakdown_150D": "amber", "breakdown_200D": "navy"};

  // init tierFilter keyed by pattern
  for (var _ip = 0; _ip < PO_PATTERNS.length; _ip++) {
    poState.tierFilter[PO_PATTERNS[_ip].key] = [];
  }

  var PO_RATING_RANK = { 'Probable':4, 'Plausible':3, 'Possible':2, 'None':1 };
  var PO_RATING_CLS  = { 'Probable':'tint-prob', 'Plausible':'tint-pla', 'Possible':'tint-pos', 'None':'tint-none' };

  function poBuildCols() {
    var cols = [
      { id:'name',     label:'Company - Ticker',       sortKey:'company',         cls:'name-cell', kind:'input' },
      { id:'taxon',    label:'Industry - Sector',      sortKey:'sector',          cls:'taxon',     kind:'input' },
      { id:'price',    label:'Price',                  sortKey:'price',           cls:'num',       kind:'input' },
      { id:'high_52w', label:'52 week high',           sortKey:'high_52w',        cls:'num',       kind:'input' },
      { id:'low_52w',  label:'52 week low',            sortKey:'low_52w',         cls:'num',       kind:'input' },
      { id:'ma_150',   label:'150D MA', sortKey:'ma_150',          cls:'num',       kind:'input' },
      { id:'ma_200',   label:'200D MA', sortKey:'ma_200',          cls:'num',       kind:'input' },
      { id:'pullback', label:'Recent pullback',        sortKey:'recent_pullback', cls:'num',       kind:'input' }
    ];
    for (var p = 0; p < PO_PATTERNS.length; p++) {
      var pat = PO_PATTERNS[p];
      var gi = p + 1;
      cols.push({ id:'p'+gi+'_rating', label:'Rating', sortKey:pat.key+'__rating', cls:'grp-start-g'+gi+' pi-rating-col', kind:'rating', patternKey:pat.key });
      cols.push({ id:'p'+gi+'_score',  label:'Score',  sortKey:pat.key+'__score',  cls:'pi-score-col',                   kind:'score',  patternKey:pat.key });
      for (var t = 0; t < pat.tests.length; t++) {
        var test = pat.tests[t];
        cols.push({
          id: 'p'+gi+'t'+(t+1), label: test.label, sortKey: pat.key + '__' + test.key,
          cls: '', tooltip: test.tooltip, kind: 'test', patternKey: pat.key, testKey: test.key
        });
      }
    }
    return cols;
  }
  var PO_COLS = poBuildCols();

  function poPricesLookup() {
    if (window._poPricesByTicker) return window._poPricesByTicker;
    var out = {};
    var arr = (window.MASTER_DATA && MASTER_DATA.prices) || [];
    for (var i = 0; i < arr.length; i++) if (arr[i] && arr[i].ticker) out[arr[i].ticker] = arr[i];
    window._poPricesByTicker = out;
    return out;
  }
  function poLiveTickers() {
    var out = {};
    var inv = (window.MASTER_DATA && MASTER_DATA.positions && MASTER_DATA.positions.investments) || [];
    for (var i = 0; i < inv.length; i++) if (inv[i].ticker) out[inv[i].ticker] = true;
    return out;
  }
  function poLiveSectors() {
    var out = {}, t, prices = poPricesLookup(), tickers = poLiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.sector) out[p.sector] = true; }
    return out;
  }
  function poLiveIndustries() {
    var out = {}, t, prices = poPricesLookup(), tickers = poLiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.industry) out[p.industry] = true; }
    return out;
  }

  function poPatternRec(row, patternKey) {
    var dk = row.md_v2 && row.md_v2.post_indicators;
    return (dk && dk[patternKey]) || null;
  }
  function poEvalTest(row, patternKey, testKey) {
    var rec = poPatternRec(row, patternKey);
    if (!rec || !rec.tests) return false;
    return !!rec.tests[testKey];
  }
  function poRowRating(row, patternKey) {
    var rec = poPatternRec(row, patternKey);
    return rec ? (rec.rating || 'None') : 'None';
  }

  function poGetRows() {
    var raw = (window.MASTER_DATA && MASTER_DATA.filters) || [];
    var prices = poPricesLookup();
    var live = poLiveTickers(), liveS = poLiveSectors(), liveI = poLiveIndustries();
    var rows = [];
    for (var i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || !s.md_v2 || !s.md_v2.post_indicators) continue;
      var p = prices[s.ticker] || {};
      var mas = p.mas || {};
      rows.push({
        ticker: s.ticker, company: p.company_name || s.ticker,
        sector: p.sector || '', industry: p.industry || '',
        price: p.price, high_52w: p.high_52w, low_52w: p.low_52w,
        recent_pullback: p.recent_pullback_pct,
        ma_150: mas['150D'], ma_200: mas['200D'],
        md_v2: s.md_v2,
        is_live: !!live[s.ticker],
        sector_in_portfolio: !!liveS[p.sector],
        industry_in_portfolio: !!liveI[p.industry]
      });
    }
    return rows;
  }

  function poPatternCounts(rows) {
    var c = {};
    for (var pi = 0; pi < PO_PATTERNS.length; pi++) c[PO_PATTERNS[pi].key] = 0;
    for (var i = 0; i < rows.length; i++) {
      for (var p = 0; p < PO_PATTERNS.length; p++) {
        var rec = poPatternRec(rows[i], PO_PATTERNS[p].key);
        if (rec && rec.qualifies) c[PO_PATTERNS[p].key]++;
      }
    }
    return c;
  }
  function poPassHistogram(rows, patternKey, total) {
    var h = [];
    for (var k = 0; k <= total; k++) h[k] = 0;
    for (var i = 0; i < rows.length; i++) {
      var rec = poPatternRec(rows[i], patternKey);
      var cnt = rec ? (rec.count || 0) : 0;
      if (cnt >= 0 && cnt <= total) h[cnt]++;
    }
    return h;
  }
  function poTierCounts(rows, patternKey) {
    var c = { 'Possible':0, 'Plausible':0, 'Probable':0, 'None':0 };
    for (var i = 0; i < rows.length; i++) {
      var r = poRowRating(rows[i], patternKey);
      if (c[r] != null) c[r]++;
    }
    return c;
  }

  function poFmtNum(n) {
    if (n == null || isNaN(n)) return '-';
    var abs = Math.abs(n);
    var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);
    if (Math.abs(n - Math.round(n)) < 1e-9) dp = 0; /* MD-V2-S40-FMTNUM-INT-FIX-po; S41 tolerance */
    var f = abs.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });
    return n < 0 ? '(' + f + ')' : f;
  }
  function poFmtPct(p) {
    if (p == null || isNaN(p)) return '-';
    var r = Math.round(p), abs = Math.abs(r);
    return r < 0 ? '(' + abs + ')%' : r + '%';
  }
  function poColourForIntensity(i) {
    if (i >= 0.6) return '#0F6E56';
    if (i >= 0.25) return '#1D9E75';
    if (i >= 0.05) return '#5DCAA5';
    if (i <= -0.6) return '#A32D2D';
    if (i <= -0.25) return '#E24B4A';
    if (i <= -0.05) return '#F09595';
    return '#888';
  }
  function poInputCell(row, key, extraCls) {
    extraCls = extraCls || '';
    var v = row[key];
    if (key === 'price') return '<td class="num ' + extraCls + '">' + poFmtNum(v) + '</td>';
    if (key === 'recent_pullback') {
      if (v == null || isNaN(v)) return '<td class="num ' + extraCls + '">-</td>';
      var pctVal = v * 100;
      var pi_intensity = Math.max(-1, Math.min(1, (pctVal - 5) / 20));
      var col = poColourForIntensity(-pi_intensity);
      return '<td class="num ' + extraCls + '" style="color:' + col + '">' + Math.round(pctVal) + '%</td>';
    }
    if (v == null || row.price == null) return '<td class="num ' + extraCls + '">-</td>';
    var pct = (row.price - v) / v * 100;
    var intensity = 0;
    if (key === 'high_52w') intensity = Math.max(-1, Math.min(1, (-pct - 5) / 20));
    else if (key === 'low_52w') intensity = Math.max(-1, Math.min(1, (pct - 20) / 30));
    else if (key === 'ma_150' || key === 'ma_200') intensity = Math.max(-1, Math.min(1, pct / 10));
    var colour = poColourForIntensity(intensity);
    var text = (poState.mode.inputs === 'pct') ? poFmtPct(pct) : poFmtNum(v);
    return '<td class="num ' + extraCls + '" style="color:' + colour + '">' + text + '</td>';
  }
  /* MD-V2-WAVE4-TEST-VALUES-TOGGLE-MARKER */
  function poTestValueFor(row, col) {
    var rec = poPatternRec(row, col.patternKey);
    var tv = rec && rec.test_values;
    if (!tv || !(col.testKey in tv)) return '\u2014';
    var v = tv[col.testKey];
    if (v === null || v === undefined) return '\u2014';
    if (typeof v === 'string') return v;
    if (typeof v === 'number') {
      if (isNaN(v)) return '\u2014';
      if (Math.abs(v) <= 1.5 && v !== Math.round(v)) return poFmtPct(v * 100);
      return poFmtNum(v);
    }
    return String(v);
  }
  function poTestCell(row, col) {
    var pass = poEvalTest(row, col.patternKey, col.testKey);
    var extra = col.cls || '';
    if (poState.mode.tests === 'val') {
      var v = poTestValueFor(row, col);
      var colour = pass ? poColourForIntensity(0.7) : poColourForIntensity(-0.4);
      return '<td class="test-val pi-' + (pass ? 'pass' : 'fail') + ' ' + extra + '" style="color:' + colour + '">' + v + '</td>';
    }
    if (pass) return '<td class="pi-pass ' + extra + '"><span class="tick">' + String.fromCharCode(10003) + '</span></td>';
    return '<td class="pi-fail ' + extra + '">.</td>';
  }
  function poRatingCell(row, col) {
    var rating = poRowRating(row, col.patternKey);
    var rcls = PO_RATING_CLS[rating] || 'tint-none';
    return '<td class="' + (col.cls || '') + ' pi-rating-cell ' + rcls + '"><span class="pi-pill pi-pill-' + rcls + '">' + rating + '</span></td>';
  }
  function poScoreCell(row, col) {
    var rec = poPatternRec(row, col.patternKey);
    var cnt = rec ? (rec.count || 0) : 0;
    var tot = rec ? (rec.total || 0) : 0;
    var s = '';
    for (var i = 0; i < tot; i++) s += '<span class="pip ' + (i < cnt ? 'on' : '') + '"></span>';
    return '<td class="' + (col.cls || '') + ' pi-score-cell"><div class="pi-pip-row">' + s +
           '<span class="pi-score-num">' + cnt + '/' + tot + '</span></div></td>';
  }
  function poHashColor(label, alpha) {
    if (!label) return null;
    var h = 0;
    for (var i = 0; i < label.length; i++) h = (h * 31 + label.charCodeAt(i)) & 0xffff;
    return 'hsla(' + (h % 360) + ', 35%, 55%, ' + alpha + ')';
  }
  function poPortfolioInfo(row) {
    if (row.is_live) return { color:'#1b5e20', bg:'rgba(27,94,32,0.10)', bgHover:'rgba(27,94,32,0.14)' };
    if (row.sector_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.05)', bgHover:'rgba(27,94,32,0.08)' };
    if (row.industry_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.025)', bgHover:'rgba(27,94,32,0.05)' };
    return null;
  }
  function poGetSortVal(row, key) {
    if (key.indexOf('__') > 0) {
      var parts = key.split('__');
      var patternKey = parts[0], sub = parts[1];
      var rec = poPatternRec(row, patternKey);
      if (sub === 'rating') return rec ? (PO_RATING_RANK[rec.rating] || 0) : 0;
      if (sub === 'score')  return rec ? (rec.count || 0) : 0;
      return poEvalTest(row, patternKey, sub) ? 1 : 0;
    }
    if (key === 'recent_pullback') return row.recent_pullback == null ? -Infinity : row.recent_pullback;
    var PCT_KEYS = ['high_52w','low_52w','ma_150','ma_200'];
    if (PCT_KEYS.indexOf(key) > -1 && poState.mode.inputs === 'pct') {
      var ref = row[key];
      if (ref == null || row.price == null || ref === 0) return -Infinity;
      return (row.price - ref) / ref * 100;
    }
    if (key in row) return row[key];
    return 0;
  }
  function poOnSort(key) {
    if (poState.sort.col === key) poState.sort.dir = poState.sort.dir === 'desc' ? 'asc' : 'desc';
    else poState.sort = { col: key, dir: key === 'company' ? 'asc' : 'desc' };
    poBuildHeaderRow();
    poRenderRows();
  }
  function poBuildHeaderRow() {
    var tr = document.getElementById('po-col-header-row');
    if (!tr) return;
    var h = '';
    for (var i = 0; i < PO_COLS.length; i++) {
      var c = PO_COLS[i];
      var isSort = poState.sort.col === c.sortKey;
      var arrow = isSort
        ? '<span class="sort-arrow">' + (poState.sort.dir === 'desc' ? String.fromCharCode(9660) : String.fromCharCode(9650)) + '</span>'
        : '<span class="sort-placeholder"></span>';
      var title = c.tooltip || c.label;
      h += '<th class="' + (c.cls || '') + '" data-sort-key="' + c.sortKey + '" title="' + title + '">' +
           '<span class="hd"><span class="lbl">' + c.label + '</span>' + arrow + '</span></th>';
    }
    tr.innerHTML = h;
  }
  function poPatternTiles(scopeRows) {
    var tiles = document.getElementById('po-pattern-tiles');
    if (!tiles) return;
    var counts = poPatternCounts(scopeRows);
    var total = scopeRows.length;
    var h = '';
    for (var i = 0; i < PO_PATTERNS.length; i++) {
      var pat = PO_PATTERNS[i];
      var cnt = counts[pat.key] || 0;
      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;
      var sel = poState.tierFilter[pat.key] || [];
      var anySel = sel.length > 0;
      var tierCounts = poTierCounts(scopeRows, pat.key);
      var headline = cnt, headSub = 'of ' + total.toLocaleString('en-GB') + ' &middot; ' + pct + '%';
      if (anySel) {
        var ft = 0;
        for (var z = 0; z < sel.length; z++) ft += (tierCounts[sel[z]] || 0);
        headline = ft;
        headSub = sel.join(' + ') + ' &middot; filtered';
      }
      var hist = poPassHistogram(scopeRows, pat.key, pat.total);
      var breakdown = '';
      for (var k = 1; k <= pat.total; k++) {
        if (k > 1) breakdown += ' &middot; ';
        breakdown += k + ' of ' + pat.total + ': ' + (hist[k] || 0).toLocaleString('en-GB');
      }
      var chips = '';
      for (var c = 0; c < 3; c++) {  /* MD-V2-S37-FOLLOWUP-MARKER: canonical 3-tier chip set */
        var tier = ['Possible','Plausible','Probable'][c];
        var on = sel.indexOf(tier) > -1;
        var tc = tierCounts[tier] || 0;
        chips += '<span class="pi-tier-chip pi-chip-' + PO_CHIP[pat.key] +
                 (on ? ' on' : '') + '" data-pattern="' + pat.key + '" data-tier="' + tier + '">' +
                 tier + ' ' + tc.toLocaleString('en-GB') + (on ? ' ' + String.fromCharCode(10003) : '') + '</span>';
      }
      var activeCls = anySel ? ' active' : '';
      h += '<div class="rating-tile ' + PO_TONE[pat.key] + activeCls + '" data-pattern="' + pat.key + '" title="' + pat.tooltip + '">' +
           '<div class="rt-label">' + pat.shortLabel + '</div>' +
           '<div class="rt-count">' + headline.toLocaleString('en-GB') + '</div>' +
           '<div class="rt-sub">' + headSub + '</div>' +
           '<div class="rt-breakdown">' + breakdown + '</div>' +
           '<div class="pi-tier-chips" data-pattern="' + pat.key + '">' + chips + '</div>' +
           '<div class="rt-strip ' + PO_STRIP[pat.key] + '"></div>' +
           '</div>';
    }
    tiles.innerHTML = h;
  }
  function poUpdateScopeCounts(rows) {
    function set(id, n) { var el = document.getElementById(id); if (el) el.textContent = '(' + n + ')'; }
    set('po-cnt-all',      rows.length);
    set('po-cnt-live',     rows.filter(function(r){ return r.is_live; }).length);
    set('po-cnt-sector',   rows.filter(function(r){ return r.sector_in_portfolio; }).length);
    set('po-cnt-industry', rows.filter(function(r){ return r.industry_in_portfolio; }).length);
  }
  function poApplyScope(all) {
    var rows = all.slice();
    if (poState.scope === 'live') rows = rows.filter(function(r){ return r.is_live; });
    else if (poState.scope === 'sector') rows = rows.filter(function(r){ return r.sector_in_portfolio; });
    else if (poState.scope === 'industry') rows = rows.filter(function(r){ return r.industry_in_portfolio; });
    return rows;
  }
  function poApplyTierFilter(rows) {
    var active = [];
    for (var p = 0; p < PO_PATTERNS.length; p++) {
      var k = PO_PATTERNS[p].key;
      var sel = poState.tierFilter[k] || [];
      if (sel.length > 0) active.push({ key: k, tiers: sel });
    }
    if (active.length === 0) return rows;
    return rows.filter(function(r) {
      for (var a = 0; a < active.length; a++) {
        var rating = poRowRating(r, active[a].key);
        if (active[a].tiers.indexOf(rating) === -1) return false;
      }
      return true;
    });
  }
  function poRenderRows() {
    var tbody = document.getElementById('po-tbody');
    if (!tbody) return;
    var all = poGetRows();
    var scopeRows = poApplyScope(all);
    poUpdateScopeCounts(all);
    poPatternTiles(scopeRows);
    var rows = poApplyTierFilter(scopeRows);
    rows.sort(function(a,b) {
      var va = poGetSortVal(a, poState.sort.col), vb = poGetSortVal(b, poState.sort.col);
      var cmp = (typeof va === 'string') ? va.localeCompare(vb) : (va || 0) - (vb || 0);
      if (cmp === 0) cmp = a.ticker.localeCompare(b.ticker);
      return poState.sort.dir === 'desc' ? -cmp : cmp;
    });
    var html = '';
    for (var i = 0; i < rows.length; i++) {
      var s = rows[i];
      var styles = [], cls = [];
      if (poState.tint === 'industry') { styles.push('--tint-bg: ' + poHashColor(s.industry, 0.16)); cls.push('tint-row'); }
      else if (poState.tint === 'sector') { styles.push('--tint-bg: ' + poHashColor(s.sector, 0.16)); cls.push('tint-row'); }
      if (poState.port === 'on') {
        var pinf = poPortfolioInfo(s);
        if (pinf) {
          styles.push('--portfolio-color: ' + pinf.color);
          styles.push('--portfolio-bg: ' + pinf.bg);
          styles.push('--portfolio-bg-hover: ' + pinf.bgHover);
          cls.push('portfolio-band'); cls.push('portfolio-tint');
        }
      }
      var styleAttr = styles.length ? ' style="' + styles.join(';') + '"' : '';
      var clsAttr = cls.length ? ' class="' + cls.join(' ') + '"' : '';
      var liveDot = s.is_live ? '<span class="live-dot">' + String.fromCharCode(9679) + '</span>' : '';
      html += '<tr' + clsAttr + styleAttr + '>' +
        '<td class="name-cell"><div class="co">' + liveDot + (s.company || s.ticker) + '</div><div class="tk">' + s.ticker + '</div></td>' +
        '<td class="taxon"><div class="ind">' + (s.industry || '') + '</div><div class="sec">' + (s.sector || '') + '</div></td>' +
        poInputCell(s, 'price') + poInputCell(s, 'high_52w') + poInputCell(s, 'low_52w') +
        poInputCell(s, 'ma_150') + poInputCell(s, 'ma_200') + poInputCell(s, 'recent_pullback');
      for (var j = 8; j < PO_COLS.length; j++) {
        var col = PO_COLS[j];
        if (col.kind === 'rating') html += poRatingCell(s, col);
        else if (col.kind === 'score') html += poScoreCell(s, col);
        else html += poTestCell(s, col);
      }
      html += '</tr>';
    }
    tbody.innerHTML = html;
  }
  function poSetMode(kind, val) {
    poState.mode[kind] = val;
    var btns = document.querySelectorAll('button[data-po-grp="' + kind + '"]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-po-val') === val);
    poRenderRows();
  }
  function poSetScope(s) {
    poState.scope = s;
    var btns = document.querySelectorAll('button[data-po-scope]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-po-scope') === s);
    poRenderRows();
  }
  function poSetTint(t) {
    poState.tint = t;
    var btns = document.querySelectorAll('button[data-po-tint]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-po-tint') === t);
    poRenderRows();
  }
  function poSetPort(p) {
    poState.port = p;
    var btns = document.querySelectorAll('button[data-po-port]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-po-port') === p);
    poRenderRows();
  }
  function poToggleTier(patternKey, tier) {
    var sel = poState.tierFilter[patternKey] || [];
    var idx = sel.indexOf(tier);
    if (idx > -1) sel.splice(idx, 1);
    else sel.push(tier);
    poState.tierFilter[patternKey] = sel;
    poRenderRows();
  }
  function poSelectAllTiers(patternKey) {
    // MD-V2-WAVE1-FROZEN-HEADERS-MARKER: tile-body click selects ONLY the Probable tier
    // (D-MD-V2-74). If exactly ['Probable'] is already selected,
    // clear it (toggle off). Tier chips remain direct multi-select.
    var pat = null;
    for (var p = 0; p < PO_PATTERNS.length; p++) if (PO_PATTERNS[p].key === patternKey) pat = PO_PATTERNS[p];
    if (!pat) return;
    var sel = poState.tierFilter[patternKey] || [];
    var probable = (pat.tierLadder.indexOf('Probable') > -1) ? 'Probable'
                   : pat.tierLadder[pat.tierLadder.length - 1];
    var onlyProbable = (sel.length === 1 && sel[0] === probable);
    poState.tierFilter[patternKey] = onlyProbable ? [] : [probable];
    poRenderRows();
  }
  window.poSetMode = poSetMode;
  window.poSetScope = poSetScope;
  window.poSetTint = poSetTint;
  window.poSetPort = poSetPort;
  window.poToggleTier = poToggleTier;
  window.poSelectAllTiers = poSelectAllTiers;
  window.poOnSort = poOnSort;

  function poBuildScaffold() {
    var host = document.getElementById('tab-post_indicators');
    if (!host) return false;
    if (host.querySelector('#po-main-table')) return true;

    var colgroupHtml = '<col class="c-name"><col class="c-taxon">' +
                       '<col class="c-price"><col class="c-52wh"><col class="c-52wl">' +
                       '<col class="c-ma150"><col class="c-ma200"><col class="c-pullback">';
    var inputsColspan = 8;
    var hasSuper = PO_SUPERGROUPS.length > 0;
    var superHtml = '<th class="gh-inputs sg-spacer" colspan="' + inputsColspan + '"></th>';
    var groupHtml = '<th class="gh-inputs" colspan="' + inputsColspan + '">Inputs</th>';

    if (hasSuper) {
      var sgCols = {};
      for (var sgi = 0; sgi < PO_SUPERGROUPS.length; sgi++) sgCols[PO_SUPERGROUPS[sgi].key] = 0;
      for (var sp = 0; sp < PO_PATTERNS.length; sp++) {
        var cspan = 2 + PO_PATTERNS[sp].tests.length;
        sgCols[PO_PATTERNS[sp].supergroup] += cspan;
      }
      for (var sgj = 0; sgj < PO_SUPERGROUPS.length; sgj++) {
        var sg = PO_SUPERGROUPS[sgj];
        superHtml += '<th class="' + sg.cls + '" colspan="' + sgCols[sg.key] + '">' + sg.label + '</th>';
      }
    }

    for (var p = 0; p < PO_PATTERNS.length; p++) {
      var pat = PO_PATTERNS[p];
      var gi = p + 1;
      var n = pat.tests.length;
      colgroupHtml += '<col class="c-rating"><col class="c-score">';
      for (var t = 0; t < n; t++) colgroupHtml += '<col class="c-test">';
      groupHtml += '<th class="gh-g' + gi + ' grp-start-g' + gi + '" colspan="' + (n + 2) + '">' + pat.label + '</th>';
    }

    var captionsHtml = '';
    for (var cp = 0; cp < PO_PATTERNS.length; cp++) {
      var cpat = PO_PATTERNS[cp];
      captionsHtml += '<div class="gcap gcap-g' + (cp+1) + '"><b>' + cpat.label + '</b>' + cpat.caption + '</div>';
    }

    var theadRows = '';
    if (hasSuper) theadRows += '<tr class="super-group-row">' + superHtml + '</tr>';
    theadRows += '<tr class="group-header-row">' + groupHtml + '</tr>';
    theadRows += '<tr class="col-header-row" id="po-col-header-row"></tr>';

    var html = '' +
      '<div class="s1-intro">Post-test indicators are five trailing price-action patterns that confirm what price has just done. Each pattern is the AND of its named constituent tests, shown below as individual tick columns alongside a per-pattern rating and score. The two bullish patterns (Breakout, Advancing) sit under one super-group; the three Breakdown patterns sit under the bearish super-group. Each tile has a rating-tier filter row: click a tier chip to show only stocks at that tier, or click the tile body to select all tiers. Tier selections within a pattern combine as OR; selections across patterns combine as AND.</div>' +
      '<div class="controls s1-controls">' +
        '<div class="ctrl-grp"><span class="ctrl-label">Inputs</span>' +
          '<button class="toggle-btn active" data-po-grp="inputs" data-po-val="pct" onclick="poSetMode(\'inputs\',\'pct\')">show as %</button>' +
          '<button class="toggle-btn" data-po-grp="inputs" data-po-val="raw" onclick="poSetMode(\'inputs\',\'raw\')">show as numbers</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Tests</span>' +  /* MD-V2-WAVE4-TEST-VALUES-TOGGLE-MARKER */
          '<button class="toggle-btn active" data-po-grp="tests" data-po-val="tick" onclick="poSetMode(\'tests\',\'tick\')">show ticks</button>' +
          '<button class="toggle-btn" data-po-grp="tests" data-po-val="val" onclick="poSetMode(\'tests\',\'val\')">show test values</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Scope</span>' +
          '<button class="toggle-btn active" data-po-scope="all" onclick="poSetScope(\'all\')">All <span id="po-cnt-all"></span></button>' +
          '<button class="toggle-btn" data-po-scope="live" onclick="poSetScope(\'live\')">Live <span id="po-cnt-live"></span></button>' +
          '<button class="toggle-btn" data-po-scope="sector" onclick="poSetScope(\'sector\')">Sectors <span id="po-cnt-sector"></span></button>' +
          '<button class="toggle-btn" data-po-scope="industry" onclick="poSetScope(\'industry\')">Industries <span id="po-cnt-industry"></span></button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Peers</button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Cohorts</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Colour by</span>' +
          '<button class="toggle-btn active" data-po-tint="none" onclick="poSetTint(\'none\')">Off</button>' +
          '<button class="toggle-btn" data-po-tint="industry" onclick="poSetTint(\'industry\')">Industry</button>' +
          '<button class="toggle-btn" data-po-tint="sector" onclick="poSetTint(\'sector\')">Sector</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Portfolio tint</span>' +
          '<button class="toggle-btn active" data-po-port="off" onclick="poSetPort(\'off\')">Off</button>' +
          '<button class="toggle-btn" data-po-port="on" onclick="poSetPort(\'on\')">On</button>' +
        '</div>' +
      '</div>' +
      '<div class="rating-tiles s1-rating-tiles" id="po-pattern-tiles"></div>' +
      '<div class="group-captions">' + captionsHtml + '</div>' +
      '<div class="table-wrap"><div class="v2-hscroll">' +  /* MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER */
        '<table class="data-table" id="po-main-table">' +
          '<colgroup>' + colgroupHtml + '</colgroup>' +
          '<thead>' + theadRows + '</thead>' +
          '<tbody id="po-tbody"></tbody>' +
        '</table>' +
      '</div></div>';  /* MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER */
    host.innerHTML = html;
    var tiles = document.getElementById('po-pattern-tiles');
    if (tiles) {
      tiles.addEventListener('click', function(e) {
        var chip = e.target.closest('.pi-tier-chip');
        if (chip) {
          var cp = chip.getAttribute('data-pattern');
          var ct = chip.getAttribute('data-tier');
          if (cp && ct) poToggleTier(cp, ct);
          return;
        }
        var tile = e.target.closest('.rating-tile');
        if (!tile) return;
        var k = tile.getAttribute('data-pattern');
        if (k) poSelectAllTiers(k);
      });
    }
    var hdr = document.getElementById('po-col-header-row');
    if (hdr) {
      hdr.addEventListener('click', function(e) {
        var th = e.target.closest('th');
        if (!th) return;
        var key = th.getAttribute('data-sort-key');
        if (key) poOnSort(key);
      });
    }
    return true;
  }

  function renderPostIndicators() {
    // MD-V2-MDJUMP-CONSUMER-S27-MARKER: Master Overview cell-click handoff. Read
    // window._mdJump once; if it targets this tab, arm the chip filter
    // for the named pattern, then clear it so it fires exactly once.
    (function(){
      var j = window._mdJump;
      if (j && j.tab === 'post_indicators') {
        if (j.patternKey && j.tier && poState.tierFilter &&
            poState.tierFilter.hasOwnProperty(j.patternKey)) {
          poState.tierFilter[j.patternKey] = [j.tier];
        }
        window._mdJump = null;
      }
    })();
    if (!poBuildScaffold()) return;
    poBuildHeaderRow();
    poRenderRows();
    if (window.measureV2Ribbon) measureV2Ribbon();  /* MD-V2-WAVE1B-STICKY-CORRECTIVE-MARKER */
  }
  window.renderPostIndicators = renderPostIndicators;

})();

/* MD-V2-POST-INDICATORS-MARKER-END */

/* MD-V2-POST-INDICATORS-MARKER-MODULE-END */
/* MD-V2-SETUPS-MARKER-MODULE-START */
// =============================================================================
// SETUPS TAB MODULE - Master Dashboard V2
// =============================================================================
// MD-V2-SETUPS-MARKER - idempotency marker for patcher detection
//
// Setups = 4 capital-deployment-eligibility patterns from _md_v2_screens.py.
// Each setup is the AND of constituent tests; each test gets its own column.
//
// SETUPS:
//   Probing Bet (2 tests):
//     - Any-of: S1 qualifying OR S3 invalidation OR S4 qualifying OR Collapsing
//     - Breakout pattern
//   VCP after S1->2 plateau (3 tests):
//     - S1 to S2 transition
//     - Higher-lows >= 2 (VCP pattern)
//     - Breakout
//   UTR after S2 pullback (3 tests):
//     - S2 uptrend
//     - Pullback-to-retest pattern
//     - UTR capital stage OR Breakout
//   VCP after S2 base (4 tests):
//     - S2 uptrend
//     - Basing-below-high pattern
//     - Higher-lows >= 2 (VCP pattern)
//     - Breakout
// =============================================================================

/* MD-V2-SETUPS-MARKER-START */

(function() {
  'use strict';

  // MD-V2-S26-CHIPS-MARKER: st tab module - rating-tier multi-select chip
  // filter + per-pattern rating/score/test columns, structured identically to
  // the proven Pre-test indicators module. Reads md_v2.setups.

  var stState = {
    mode: { inputs: 'pct', tests: 'tick' },
    scope: 'all',
    tierFilter: {},
    tint: 'none',
    port: 'off',
    sortByTab: {}
  };

  var ST_PATTERNS_ALL = [
  {
    "key": "probing_bet",
    "label": "Probing bet",
    "shortLabel": "Probing bet",
    "supergroup": null,
    "tierLadder": [
      "Possible",
      "Probable"
    ],
    "total": 2,
    "tooltip": "A stock in a weak or basing stage (or collapsing) that is showing a fresh breakout - worth a small starter position.",
    "caption": "A <span class='db'>small initial allocation</span> &mdash; a stock that has collapsed or is stuck in a struggling stage, but is showing a fresh breakout worth a starter position.<span class='intro'>Two tests:</span><span class='tline'><span class='tnum'>(1)</span> Is the stock in a <u>qualifying stage</u> (Stage 1 plausible+, Stage 3 invalidating, or Stage 4 plausible+) <u>or showing the Collapsing indicator</u>?</span><span class='tline'><span class='tnum'>(2)</span> Is the <u>Breakout post-test indicator firing</u>?</span>",
    "tests": [
      {
        "key": "t1_stage_qualifying_or_collapsing",
        "label": "Qualifying stage or Collapsing",
        "tooltip": "Stage 1 plausible-or-better, OR Stage 3 invalidating, OR Stage 4 plausible-or-better, OR the Collapsing indicator fires"
      },
      {
        "key": "t2_breakout",
        "label": "Breakout",
        "tooltip": "The Breakout post-test indicator fires"
      }
    ]
  },
  {
    "key": "vcp_after_s1_plateau",
    "label": "VCP after Stage 1-to-2 plateau",
    "shortLabel": "VCP after S1-2",
    "supergroup": null,
    "tierLadder": [
      "Possible",
      "Plausible",
      "Probable"
    ],
    "total": 4,
    "tooltip": "A stock transitioning from Stage 1 to Stage 2 showing a genuine volatility-contraction pattern.",
    "caption": "A <span class='db'>core position setup</span> &mdash; a stock coming out of a base into a new uptrend with a genuine volatility-contraction pattern.<span class='intro'>Four VCP tests &mdash; all must pass (plus the Stage 1-to-2 transition gate, shown as an info column):</span><span class='tline'><span class='tnum'>(1)</span> Are the price <u>contractions narrowing</u> &mdash; each pullback shallower than the one before?</span><span class='tline'><span class='tnum'>(2)</span> Are there <u>2 to 4 contractions</u> in the base?</span><span class='tline'><span class='tnum'>(3)</span> Is <u>volume declining</u> across successive contractions?</span><span class='tline'><span class='tnum'>(4)</span> Are the <u>contraction lows higher</u> &mdash; each above the previous?</span>",
    "tests": [
      {
        "key": "t1_narrowing_contractions",
        "label": "Narrowing contractions",
        "tooltip": "Each price contraction is strictly shallower than the one before it"
      },
      {
        "key": "t2_sufficient_count",
        "label": "2-4 contractions",
        "tooltip": "Between two and four contractions in the base"
      },
      {
        "key": "t3_volume_declining",
        "label": "Volume declining",
        "tooltip": "Average volume falls across successive contractions"
      },
      {
        "key": "t4_higher_lows",
        "label": "Higher lows",
        "tooltip": "Each contraction low sits above the previous contraction low"
      }
    ]
  },
  {
    "key": "healthy_retest",
    "label": "Healthy retest within MT/LT uptrend",
    "shortLabel": "Healthy retest",
    "supergroup": null,
    "tierLadder": [
      "Possible",
      "Plausible",
      "Probable"
    ],
    "total": 6,
    "tooltip": "A stock in a real uptrend whose pullback toward a moving average is orderly and healthy.",
    "caption": "A <span class='db'>core position setup</span> &mdash; a stock in a genuine uptrend whose pullback toward a moving average is <span class='db'>orderly, not violent</span>.<span class='intro'>Six tests &mdash; all must pass:</span><span class='tline'><span class='tnum'>(1)</span> Is <u>volume contracting</u> &mdash; 10-day average volume below the 50-day?</span><span class='tline'><span class='tnum'>(2)</span> Is <u>up-day volume at least 5% above down-day volume</u> over the last month?</span><span class='tline'><span class='tnum'>(3)</span> Are there <u>three or fewer distribution days</u> in the last 25 sessions?</span><span class='tline'><span class='tnum'>(4)</span> Is <u>volatility contracting</u> &mdash; the 10-day ATR below the 20-day?</span><span class='tline'><span class='tnum'>(5)</span> Has price come down to <u>within range of a meaningful MA</u> (50/100/150/200-day)?</span><span class='tline'><span class='tnum'>(6)</span> Is the stock <u>buying through the last 10 days</u> &mdash; at least half closing in the upper 40% of their daily range?</span>",
    "tests": [
      {
        "key": "t1_volume_contracting",
        "label": "Volume contracting",
        "tooltip": "10-day average volume is below the 50-day average volume"
      },
      {
        "key": "t2_updown_vol_ge105",
        "label": "Up-volume 5%+ above down",
        "tooltip": "Up-day volume is at least 5% above down-day volume"
      },
      {
        "key": "t3_few_distribution_days",
        "label": "Few distribution days",
        "tooltip": "Three or fewer distribution days in the last 25 sessions"
      },
      {
        "key": "t4_volatility_contracting",
        "label": "Volatility contracting",
        "tooltip": "Short-term volatility range is narrower than the medium-term range"
      },
      {
        "key": "t5_testing_meaningful_ma",
        "label": "Testing a meaningful MA",
        "tooltip": "Price has come down to within range of a 50/100/150/200-day moving average"
      },
      {
        "key": "t6_buying_through_l10d",
        "label": "Buying through last 10 days",
        "tooltip": "At least half of the last 10 days closed in the upper 40% of their daily range"
      }
    ]
  },
  {
    "key": "vcp_after_s2_base",
    "label": "VCP after Stage 2 base",
    "shortLabel": "VCP after S2",
    "supergroup": null,
    "tierLadder": [
      "Possible",
      "Plausible",
      "Probable"
    ],
    "total": 4,
    "tooltip": "A stock already in an uptrend that has built a fresh base with a genuine volatility-contraction pattern.",
    "caption": "A <span class='db'>core position setup</span> &mdash; a stock already in a Stage 2 uptrend that has built a <span class='db'>fresh base</span> with a genuine volatility-contraction pattern.<span class='intro'>Four VCP tests &mdash; all must pass (plus the Stage 2 base gate, shown as an info column):</span><span class='tline'><span class='tnum'>(1)</span> Are the price <u>contractions narrowing</u> &mdash; each pullback shallower than the last?</span><span class='tline'><span class='tnum'>(2)</span> Are there <u>2 to 4 contractions</u> in the base?</span><span class='tline'><span class='tnum'>(3)</span> Is <u>volume declining</u> across successive contractions?</span><span class='tline'><span class='tnum'>(4)</span> Are the <u>contraction lows higher</u> &mdash; each above the previous?</span>",
    "tests": [
      {
        "key": "t1_narrowing_contractions",
        "label": "Narrowing contractions",
        "tooltip": "Each price contraction is strictly shallower than the one before it"
      },
      {
        "key": "t2_sufficient_count",
        "label": "2-4 contractions",
        "tooltip": "Between two and four contractions in the base"
      },
      {
        "key": "t3_volume_declining",
        "label": "Volume declining",
        "tooltip": "Average volume falls across successive contractions"
      },
      {
        "key": "t4_higher_lows",
        "label": "Higher lows",
        "tooltip": "Each contraction low sits above the previous contraction low"
      }
    ]
  }
];
  var ST_SUPERGROUPS = [];
  var ST_TONE = {"probing_bet": "pi-tile-pullback", "vcp_after_s1_plateau": "pi-tile-basing", "healthy_retest": "pi-tile-navy", "vcp_after_s2_base": "pi-tile-amber"};
  var ST_STRIP = {"probing_bet": "pi-strip-pullback", "vcp_after_s1_plateau": "pi-strip-basing", "healthy_retest": "pi-strip-navy", "vcp_after_s2_base": "pi-strip-amber"};
  var ST_CHIP = {"probing_bet": "pullback", "vcp_after_s1_plateau": "basing", "healthy_retest": "navy", "vcp_after_s2_base": "amber"};

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
  var stCur = null;

  // init tierFilter keyed by pattern (all patterns, both tabs)
  for (var _ip = 0; _ip < ST_PATTERNS_ALL.length; _ip++) {
    stState.tierFilter[ST_PATTERNS_ALL[_ip].key] = [];
  }
  // MD-V2-SETUPS-SPLIT-S33-MARKER: per-tab sort state
  for (var _it = 0; _it < ST_TAB_DEFS.length; _it++) {
    stState.sortByTab[ST_TAB_DEFS[_it].tabId] = { col: 'company', dir: 'asc' };
  }

  var ST_RATING_RANK = { 'Probable':4, 'Plausible':3, 'Possible':2, 'None':1 };
  var ST_RATING_CLS  = { 'Probable':'tint-prob', 'Plausible':'tint-pla', 'Possible':'tint-pos', 'None':'tint-none' };

  function stBuildCols() {
    var cols = [
      { id:'name',     label:'Company - Ticker',       sortKey:'company',         cls:'name-cell', kind:'input' },
      { id:'taxon',    label:'Industry - Sector',      sortKey:'sector',          cls:'taxon',     kind:'input' },
      { id:'price',    label:'Price',                  sortKey:'price',           cls:'num',       kind:'input' },
      { id:'high_52w', label:'52 week high',           sortKey:'high_52w',        cls:'num',       kind:'input' },
      { id:'low_52w',  label:'52 week low',            sortKey:'low_52w',         cls:'num',       kind:'input' },
      { id:'ma_150',   label:'150D MA', sortKey:'ma_150',          cls:'num',       kind:'input' },
      { id:'ma_200',   label:'200D MA', sortKey:'ma_200',          cls:'num',       kind:'input' },
      { id:'pullback', label:'Recent pullback',        sortKey:'recent_pullback', cls:'num',       kind:'input' }
    ];
    for (var p = 0; p < stCur.patterns.length; p++) {
      var pat = stCur.patterns[p];
      var gi = p + 1;
      cols.push({ id:'p'+gi+'_rating', label:'Rating', sortKey:pat.key+'__rating', cls:'grp-start-g'+gi+' pi-rating-col', kind:'rating', patternKey:pat.key });
      cols.push({ id:'p'+gi+'_score',  label:'Score',  sortKey:pat.key+'__score',  cls:'pi-score-col',                   kind:'score',  patternKey:pat.key });
      for (var t = 0; t < pat.tests.length; t++) {
        var test = pat.tests[t];
        cols.push({
          id: 'p'+gi+'t'+(t+1), label: test.label, sortKey: pat.key + '__' + test.key,
          cls: '', tooltip: test.tooltip, kind: 'test', patternKey: pat.key, testKey: test.key
        });
      }
    }
    return cols;
  }

  function stPricesLookup() {
    if (window._stPricesByTicker) return window._stPricesByTicker;
    var out = {};
    var arr = (window.MASTER_DATA && MASTER_DATA.prices) || [];
    for (var i = 0; i < arr.length; i++) if (arr[i] && arr[i].ticker) out[arr[i].ticker] = arr[i];
    window._stPricesByTicker = out;
    return out;
  }
  function stLiveTickers() {
    var out = {};
    var inv = (window.MASTER_DATA && MASTER_DATA.positions && MASTER_DATA.positions.investments) || [];
    for (var i = 0; i < inv.length; i++) if (inv[i].ticker) out[inv[i].ticker] = true;
    return out;
  }
  function stLiveSectors() {
    var out = {}, t, prices = stPricesLookup(), tickers = stLiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.sector) out[p.sector] = true; }
    return out;
  }
  function stLiveIndustries() {
    var out = {}, t, prices = stPricesLookup(), tickers = stLiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.industry) out[p.industry] = true; }
    return out;
  }

  function stPatternRec(row, patternKey) {
    var dk = row.md_v2 && row.md_v2.setups;
    return (dk && dk[patternKey]) || null;
  }
  function stEvalTest(row, patternKey, testKey) {
    var rec = stPatternRec(row, patternKey);
    if (!rec || !rec.tests) return false;
    return !!rec.tests[testKey];
  }
  function stRowRating(row, patternKey) {
    var rec = stPatternRec(row, patternKey);
    return rec ? (rec.rating || 'None') : 'None';
  }

  function stGetRows() {
    var raw = (window.MASTER_DATA && MASTER_DATA.filters) || [];
    var prices = stPricesLookup();
    var live = stLiveTickers(), liveS = stLiveSectors(), liveI = stLiveIndustries();
    var rows = [];
    for (var i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || !s.md_v2 || !s.md_v2.setups) continue;
      var p = prices[s.ticker] || {};
      var mas = p.mas || {};
      rows.push({
        ticker: s.ticker, company: p.company_name || s.ticker,
        sector: p.sector || '', industry: p.industry || '',
        price: p.price, high_52w: p.high_52w, low_52w: p.low_52w,
        recent_pullback: p.recent_pullback_pct,
        ma_150: mas['150D'], ma_200: mas['200D'],
        md_v2: s.md_v2,
        is_live: !!live[s.ticker],
        sector_in_portfolio: !!liveS[p.sector],
        industry_in_portfolio: !!liveI[p.industry]
      });
    }
    return rows;
  }

  function stPatternCounts(rows) {
    var c = {};
    for (var pi = 0; pi < stCur.patterns.length; pi++) c[stCur.patterns[pi].key] = 0;
    for (var i = 0; i < rows.length; i++) {
      for (var p = 0; p < stCur.patterns.length; p++) {
        var rec = stPatternRec(rows[i], stCur.patterns[p].key);
        if (rec && rec.qualifies) c[stCur.patterns[p].key]++;
      }
    }
    return c;
  }
  function stPassHistogram(rows, patternKey, total) {
    var h = [];
    for (var k = 0; k <= total; k++) h[k] = 0;
    for (var i = 0; i < rows.length; i++) {
      var rec = stPatternRec(rows[i], patternKey);
      var cnt = rec ? (rec.count || 0) : 0;
      if (cnt >= 0 && cnt <= total) h[cnt]++;
    }
    return h;
  }
  function stTierCounts(rows, patternKey) {
    var c = { 'Possible':0, 'Plausible':0, 'Probable':0, 'None':0 };
    for (var i = 0; i < rows.length; i++) {
      var r = stRowRating(rows[i], patternKey);
      if (c[r] != null) c[r]++;
    }
    return c;
  }

  function stFmtNum(n) {
    if (n == null || isNaN(n)) return '-';
    var abs = Math.abs(n);
    var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);
    if (Math.abs(n - Math.round(n)) < 1e-9) dp = 0; /* MD-V2-S40-FMTNUM-INT-FIX-st; S41 tolerance */
    var f = abs.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });
    return n < 0 ? '(' + f + ')' : f;
  }
  function stFmtPct(p) {
    if (p == null || isNaN(p)) return '-';
    var r = Math.round(p), abs = Math.abs(r);
    return r < 0 ? '(' + abs + ')%' : r + '%';
  }
  function stColourForIntensity(i) {
    if (i >= 0.6) return '#0F6E56';
    if (i >= 0.25) return '#1D9E75';
    if (i >= 0.05) return '#5DCAA5';
    if (i <= -0.6) return '#A32D2D';
    if (i <= -0.25) return '#E24B4A';
    if (i <= -0.05) return '#F09595';
    return '#888';
  }
  function stInputCell(row, key, extraCls) {
    extraCls = extraCls || '';
    var v = row[key];
    if (key === 'price') return '<td class="num ' + extraCls + '">' + stFmtNum(v) + '</td>';
    if (key === 'recent_pullback') {
      if (v == null || isNaN(v)) return '<td class="num ' + extraCls + '">-</td>';
      var pctVal = v * 100;
      var pi_intensity = Math.max(-1, Math.min(1, (pctVal - 5) / 20));
      var col = stColourForIntensity(-pi_intensity);
      return '<td class="num ' + extraCls + '" style="color:' + col + '">' + Math.round(pctVal) + '%</td>';
    }
    if (v == null || row.price == null) return '<td class="num ' + extraCls + '">-</td>';
    var pct = (row.price - v) / v * 100;
    var intensity = 0;
    if (key === 'high_52w') intensity = Math.max(-1, Math.min(1, (-pct - 5) / 20));
    else if (key === 'low_52w') intensity = Math.max(-1, Math.min(1, (pct - 20) / 30));
    else if (key === 'ma_150' || key === 'ma_200') intensity = Math.max(-1, Math.min(1, pct / 10));
    var colour = stColourForIntensity(intensity);
    var text = (stState.mode.inputs === 'pct') ? stFmtPct(pct) : stFmtNum(v);
    return '<td class="num ' + extraCls + '" style="color:' + colour + '">' + text + '</td>';
  }
  /* MD-V2-WAVE4-TEST-VALUES-TOGGLE-MARKER */
  function stTestValueFor(row, col) {
    var rec = stPatternRec(row, col.patternKey);
    var tv = rec && rec.test_values;
    if (!tv || !(col.testKey in tv)) return '\u2014';
    var v = tv[col.testKey];
    if (v === null || v === undefined) return '\u2014';
    if (typeof v === 'string') return v;
    if (typeof v === 'number') {
      if (isNaN(v)) return '\u2014';
      if (Math.abs(v) <= 1.5 && v !== Math.round(v)) return stFmtPct(v * 100);
      return stFmtNum(v);
    }
    return String(v);
  }
  function stTestCell(row, col) {
    var pass = stEvalTest(row, col.patternKey, col.testKey);
    var extra = col.cls || '';
    if (stState.mode.tests === 'val') {
      var v = stTestValueFor(row, col);
      var colour = pass ? stColourForIntensity(0.7) : stColourForIntensity(-0.4);
      return '<td class="test-val pi-' + (pass ? 'pass' : 'fail') + ' ' + extra + '" style="color:' + colour + '">' + v + '</td>';
    }
    if (pass) return '<td class="pi-pass ' + extra + '"><span class="tick">' + String.fromCharCode(10003) + '</span></td>';
    return '<td class="pi-fail ' + extra + '">.</td>';
  }
  function stRatingCell(row, col) {
    var rating = stRowRating(row, col.patternKey);
    var rcls = ST_RATING_CLS[rating] || 'tint-none';
    return '<td class="' + (col.cls || '') + ' pi-rating-cell ' + rcls + '"><span class="pi-pill pi-pill-' + rcls + '">' + rating + '</span></td>';
  }
  function stScoreCell(row, col) {
    var rec = stPatternRec(row, col.patternKey);
    var cnt = rec ? (rec.count || 0) : 0;
    var tot = rec ? (rec.total || 0) : 0;
    var s = '';
    for (var i = 0; i < tot; i++) s += '<span class="pip ' + (i < cnt ? 'on' : '') + '"></span>';
    return '<td class="' + (col.cls || '') + ' pi-score-cell"><div class="pi-pip-row">' + s +
           '<span class="pi-score-num">' + cnt + '/' + tot + '</span></div></td>';
  }
  function stHashColor(label, alpha) {
    if (!label) return null;
    var h = 0;
    for (var i = 0; i < label.length; i++) h = (h * 31 + label.charCodeAt(i)) & 0xffff;
    return 'hsla(' + (h % 360) + ', 35%, 55%, ' + alpha + ')';
  }
  function stPortfolioInfo(row) {
    if (row.is_live) return { color:'#1b5e20', bg:'rgba(27,94,32,0.10)', bgHover:'rgba(27,94,32,0.14)' };
    if (row.sector_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.05)', bgHover:'rgba(27,94,32,0.08)' };
    if (row.industry_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.025)', bgHover:'rgba(27,94,32,0.05)' };
    return null;
  }
  function stGetSortVal(row, key) {
    if (key.indexOf('__') > 0) {
      var parts = key.split('__');
      var patternKey = parts[0], sub = parts[1];
      var rec = stPatternRec(row, patternKey);
      if (sub === 'rating') return rec ? (ST_RATING_RANK[rec.rating] || 0) : 0;
      if (sub === 'score')  return rec ? (rec.count || 0) : 0;
      return stEvalTest(row, patternKey, sub) ? 1 : 0;
    }
    if (key === 'recent_pullback') return row.recent_pullback == null ? -Infinity : row.recent_pullback;
    var PCT_KEYS = ['high_52w','low_52w','ma_150','ma_200'];
    if (PCT_KEYS.indexOf(key) > -1 && stState.mode.inputs === 'pct') {
      var ref = row[key];
      if (ref == null || row.price == null || ref === 0) return -Infinity;
      return (row.price - ref) / ref * 100;
    }
    if (key in row) return row[key];
    return 0;
  }
  function stOnSort(key) {
    stEnsureCur();
    var srt = stCur.sort;
    if (srt.col === key) srt.dir = srt.dir === 'desc' ? 'asc' : 'desc';
    else { srt.col = key; srt.dir = key === 'company' ? 'asc' : 'desc'; }
    stBuildHeaderRow();
    stRenderRows();
  }
  function stBuildHeaderRow() {
    var tr = document.getElementById(stCur.idp + '-col-header-row');
    if (!tr) return;
    var h = '';
    for (var i = 0; i < stCur.cols.length; i++) {
      var c = stCur.cols[i];
      var isSort = stCur.sort.col === c.sortKey;
      var arrow = isSort
        ? '<span class="sort-arrow">' + (stCur.sort.dir === 'desc' ? String.fromCharCode(9660) : String.fromCharCode(9650)) + '</span>'
        : '<span class="sort-placeholder"></span>';
      var title = c.tooltip || c.label;
      h += '<th class="' + (c.cls || '') + '" data-sort-key="' + c.sortKey + '" title="' + title + '">' +
           '<span class="hd"><span class="lbl">' + c.label + '</span>' + arrow + '</span></th>';
    }
    tr.innerHTML = h;
  }
  function stPatternTiles(scopeRows) {
    var tiles = document.getElementById(stCur.idp + '-pattern-tiles');
    if (!tiles) return;
    var counts = stPatternCounts(scopeRows);
    var total = scopeRows.length;
    var h = '';
    for (var i = 0; i < stCur.patterns.length; i++) {
      var pat = stCur.patterns[i];
      var cnt = counts[pat.key] || 0;
      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;
      var sel = stState.tierFilter[pat.key] || [];
      var anySel = sel.length > 0;
      var tierCounts = stTierCounts(scopeRows, pat.key);
      var headline = cnt, headSub = 'of ' + total.toLocaleString('en-GB') + ' &middot; ' + pct + '%';
      if (anySel) {
        var ft = 0;
        for (var z = 0; z < sel.length; z++) ft += (tierCounts[sel[z]] || 0);
        headline = ft;
        headSub = sel.join(' + ') + ' &middot; filtered';
      }
      var hist = stPassHistogram(scopeRows, pat.key, pat.total);
      var breakdown = '';
      for (var k = 1; k <= pat.total; k++) {
        if (k > 1) breakdown += ' &middot; ';
        breakdown += k + ' of ' + pat.total + ': ' + (hist[k] || 0).toLocaleString('en-GB');
      }
      var chips = '';
      for (var c = 0; c < 3; c++) {  /* MD-V2-S37-FOLLOWUP-MARKER: canonical 3-tier chip set */
        var tier = ['Possible','Plausible','Probable'][c];
        var on = sel.indexOf(tier) > -1;
        var tc = tierCounts[tier] || 0;
        chips += '<span class="pi-tier-chip pi-chip-' + ST_CHIP[pat.key] +
                 (on ? ' on' : '') + '" data-pattern="' + pat.key + '" data-tier="' + tier + '">' +
                 tier + ' ' + tc.toLocaleString('en-GB') + (on ? ' ' + String.fromCharCode(10003) : '') + '</span>';
      }
      var activeCls = anySel ? ' active' : '';
      h += '<div class="rating-tile ' + ST_TONE[pat.key] + activeCls + '" data-pattern="' + pat.key + '" title="' + pat.tooltip + '">' +
           '<div class="rt-label">' + pat.shortLabel + '</div>' +
           '<div class="rt-count">' + headline.toLocaleString('en-GB') + '</div>' +
           '<div class="rt-sub">' + headSub + '</div>' +
           '<div class="rt-breakdown">' + breakdown + '</div>' +
           '<div class="pi-tier-chips" data-pattern="' + pat.key + '">' + chips + '</div>' +
           '<div class="rt-strip ' + ST_STRIP[pat.key] + '"></div>' +
           '</div>';
    }
    tiles.innerHTML = h;
  }
  function stUpdateScopeCounts(rows) {
    function set(id, n) { var el = document.getElementById(id); if (el) el.textContent = '(' + n + ')'; }
    set(stCur.idp + '-cnt-all',      rows.length);
    set(stCur.idp + '-cnt-live',     rows.filter(function(r){ return r.is_live; }).length);
    set(stCur.idp + '-cnt-sector',   rows.filter(function(r){ return r.sector_in_portfolio; }).length);
    set(stCur.idp + '-cnt-industry', rows.filter(function(r){ return r.industry_in_portfolio; }).length);
  }
  function stApplyScope(all) {
    var rows = all.slice();
    if (stState.scope === 'live') rows = rows.filter(function(r){ return r.is_live; });
    else if (stState.scope === 'sector') rows = rows.filter(function(r){ return r.sector_in_portfolio; });
    else if (stState.scope === 'industry') rows = rows.filter(function(r){ return r.industry_in_portfolio; });
    return rows;
  }
  function stApplyTierFilter(rows) {
    var active = [];
    for (var p = 0; p < stCur.patterns.length; p++) {
      var k = stCur.patterns[p].key;
      var sel = stState.tierFilter[k] || [];
      if (sel.length > 0) active.push({ key: k, tiers: sel });
    }
    if (active.length === 0) return rows;
    return rows.filter(function(r) {
      for (var a = 0; a < active.length; a++) {
        var rating = stRowRating(r, active[a].key);
        if (active[a].tiers.indexOf(rating) === -1) return false;
      }
      return true;
    });
  }
  function stRenderRows() {
    var tbody = document.getElementById(stCur.idp + '-tbody');
    if (!tbody) return;
    var all = stGetRows();
    var scopeRows = stApplyScope(all);
    stUpdateScopeCounts(all);
    stPatternTiles(scopeRows);
    var rows = stApplyTierFilter(scopeRows);
    rows.sort(function(a,b) {
      var va = stGetSortVal(a, stCur.sort.col), vb = stGetSortVal(b, stCur.sort.col);
      var cmp = (typeof va === 'string') ? va.localeCompare(vb) : (va || 0) - (vb || 0);
      if (cmp === 0) cmp = a.ticker.localeCompare(b.ticker);
      return stCur.sort.dir === 'desc' ? -cmp : cmp;
    });
    var html = '';
    for (var i = 0; i < rows.length; i++) {
      var s = rows[i];
      var styles = [], cls = [];
      if (stState.tint === 'industry') { styles.push('--tint-bg: ' + stHashColor(s.industry, 0.16)); cls.push('tint-row'); }
      else if (stState.tint === 'sector') { styles.push('--tint-bg: ' + stHashColor(s.sector, 0.16)); cls.push('tint-row'); }
      if (stState.port === 'on') {
        var pinf = stPortfolioInfo(s);
        if (pinf) {
          styles.push('--portfolio-color: ' + pinf.color);
          styles.push('--portfolio-bg: ' + pinf.bg);
          styles.push('--portfolio-bg-hover: ' + pinf.bgHover);
          cls.push('portfolio-band'); cls.push('portfolio-tint');
        }
      }
      var styleAttr = styles.length ? ' style="' + styles.join(';') + '"' : '';
      var clsAttr = cls.length ? ' class="' + cls.join(' ') + '"' : '';
      var liveDot = s.is_live ? '<span class="live-dot">' + String.fromCharCode(9679) + '</span>' : '';
      html += '<tr' + clsAttr + styleAttr + '>' +
        '<td class="name-cell"><div class="co">' + liveDot + (s.company || s.ticker) + '</div><div class="tk">' + s.ticker + '</div></td>' +
        '<td class="taxon"><div class="ind">' + (s.industry || '') + '</div><div class="sec">' + (s.sector || '') + '</div></td>' +
        stInputCell(s, 'price') + stInputCell(s, 'high_52w') + stInputCell(s, 'low_52w') +
        stInputCell(s, 'ma_150') + stInputCell(s, 'ma_200') + stInputCell(s, 'recent_pullback');
      for (var j = 8; j < stCur.cols.length; j++) {
        var col = stCur.cols[j];
        if (col.kind === 'rating') html += stRatingCell(s, col);
        else if (col.kind === 'score') html += stScoreCell(s, col);
        else html += stTestCell(s, col);
      }
      html += '</tr>';
    }
    tbody.innerHTML = html;
  }
  function stSetMode(kind, val) {
    stEnsureCur();
    stState.mode[kind] = val;
    var btns = document.querySelectorAll('button[data-st-grp="' + kind + '"]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-st-val') === val);
    stRenderRows();
  }
  function stSetScope(s) {
    stEnsureCur();
    stState.scope = s;
    var btns = document.querySelectorAll('button[data-st-scope]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-st-scope') === s);
    stRenderRows();
  }
  function stSetTint(t) {
    stEnsureCur();
    stState.tint = t;
    var btns = document.querySelectorAll('button[data-st-tint]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-st-tint') === t);
    stRenderRows();
  }
  function stSetPort(p) {
    stEnsureCur();
    stState.port = p;
    var btns = document.querySelectorAll('button[data-st-port]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-st-port') === p);
    stRenderRows();
  }
  function stToggleTier(patternKey, tier) {
    stEnsureCur();
    var sel = stState.tierFilter[patternKey] || [];
    var idx = sel.indexOf(tier);
    if (idx > -1) sel.splice(idx, 1);
    else sel.push(tier);
    stState.tierFilter[patternKey] = sel;
    stRenderRows();
  }
  function stSelectAllTiers(patternKey) {
    stEnsureCur();
    // MD-V2-WAVE1-FROZEN-HEADERS-MARKER: tile-body click selects ONLY the Probable tier
    // (D-MD-V2-74). If exactly ['Probable'] is already selected,
    // clear it (toggle off). Tier chips remain direct multi-select.
    var pat = null;
    for (var p = 0; p < ST_PATTERNS_ALL.length; p++) if (ST_PATTERNS_ALL[p].key === patternKey) pat = ST_PATTERNS_ALL[p];
    if (!pat) return;
    var sel = stState.tierFilter[patternKey] || [];
    var probable = (pat.tierLadder.indexOf('Probable') > -1) ? 'Probable'
                   : pat.tierLadder[pat.tierLadder.length - 1];
    var onlyProbable = (sel.length === 1 && sel[0] === probable);
    stState.tierFilter[patternKey] = onlyProbable ? [] : [probable];
    stRenderRows();
  }
  window.stSetMode = stSetMode;
  window.stSetScope = stSetScope;
  window.stSetTint = stSetTint;
  window.stSetPort = stSetPort;
  window.stToggleTier = stToggleTier;
  window.stSelectAllTiers = stSelectAllTiers;
  window.stOnSort = stOnSort;

  function stBuildScaffold() {
    var host = document.getElementById(stCur.hostId);
    if (!host) return false;
    if (host.querySelector('.st-main-table')) return true;

    var colgroupHtml = '<col class="c-name"><col class="c-taxon">' +
                       '<col class="c-price"><col class="c-52wh"><col class="c-52wl">' +
                       '<col class="c-ma150"><col class="c-ma200"><col class="c-pullback">';
    var inputsColspan = 8;
    var hasSuper = ST_SUPERGROUPS.length > 0;
    var superHtml = '<th class="gh-inputs sg-spacer" colspan="' + inputsColspan + '"></th>';
    var groupHtml = '<th class="gh-inputs" colspan="' + inputsColspan + '">Inputs</th>';

    if (hasSuper) {
      var sgCols = {};
      for (var sgi = 0; sgi < ST_SUPERGROUPS.length; sgi++) sgCols[ST_SUPERGROUPS[sgi].key] = 0;
      for (var sp = 0; sp < stCur.patterns.length; sp++) {
        var cspan = 2 + stCur.patterns[sp].tests.length;
        sgCols[stCur.patterns[sp].supergroup] += cspan;
      }
      for (var sgj = 0; sgj < ST_SUPERGROUPS.length; sgj++) {
        var sg = ST_SUPERGROUPS[sgj];
        superHtml += '<th class="' + sg.cls + '" colspan="' + sgCols[sg.key] + '">' + sg.label + '</th>';
      }
    }

    for (var p = 0; p < stCur.patterns.length; p++) {
      var pat = stCur.patterns[p];
      var gi = p + 1;
      var n = pat.tests.length;
      colgroupHtml += '<col class="c-rating"><col class="c-score">';
      for (var t = 0; t < n; t++) colgroupHtml += '<col class="c-test">';
      groupHtml += '<th class="gh-g' + gi + ' grp-start-g' + gi + '" colspan="' + (n + 2) + '">' + pat.label + '</th>';
    }

    var captionsHtml = '';
    for (var cp = 0; cp < stCur.patterns.length; cp++) {
      var cpat = stCur.patterns[cp];
      captionsHtml += '<div class="gcap gcap-g' + (cp+1) + '"><b>' + cpat.label + '</b>' + cpat.caption + '</div>';
    }

    var theadRows = '';
    if (hasSuper) theadRows += '<tr class="super-group-row">' + superHtml + '</tr>';
    theadRows += '<tr class="group-header-row">' + groupHtml + '</tr>';
    theadRows += '<tr class="col-header-row" id="' + stCur.idp + '-col-header-row"></tr>';

    var html = '' +
      '<div class="s1-intro">' + stCur.intro + '</div>' +
      '<div class="controls s1-controls">' +
        '<div class="ctrl-grp"><span class="ctrl-label">Inputs</span>' +
          '<button class="toggle-btn active" data-st-grp="inputs" data-st-val="pct" onclick="stSetMode(\'inputs\',\'pct\')">show as %</button>' +
          '<button class="toggle-btn" data-st-grp="inputs" data-st-val="raw" onclick="stSetMode(\'inputs\',\'raw\')">show as numbers</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Tests</span>' +  /* MD-V2-WAVE4-TEST-VALUES-TOGGLE-MARKER */
          '<button class="toggle-btn active" data-st-grp="tests" data-st-val="tick" onclick="stSetMode(\'tests\',\'tick\')">show ticks</button>' +
          '<button class="toggle-btn" data-st-grp="tests" data-st-val="val" onclick="stSetMode(\'tests\',\'val\')">show test values</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Scope</span>' +
          '<button class="toggle-btn active" data-st-scope="all" onclick="stSetScope(\'all\')">All <span id="' + stCur.idp + '-cnt-all"></span></button>' +
          '<button class="toggle-btn" data-st-scope="live" onclick="stSetScope(\'live\')">Live <span id="' + stCur.idp + '-cnt-live"></span></button>' +
          '<button class="toggle-btn" data-st-scope="sector" onclick="stSetScope(\'sector\')">Sectors <span id="' + stCur.idp + '-cnt-sector"></span></button>' +
          '<button class="toggle-btn" data-st-scope="industry" onclick="stSetScope(\'industry\')">Industries <span id="' + stCur.idp + '-cnt-industry"></span></button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Peers</button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Cohorts</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Colour by</span>' +
          '<button class="toggle-btn active" data-st-tint="none" onclick="stSetTint(\'none\')">Off</button>' +
          '<button class="toggle-btn" data-st-tint="industry" onclick="stSetTint(\'industry\')">Industry</button>' +
          '<button class="toggle-btn" data-st-tint="sector" onclick="stSetTint(\'sector\')">Sector</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Portfolio tint</span>' +
          '<button class="toggle-btn active" data-st-port="off" onclick="stSetPort(\'off\')">Off</button>' +
          '<button class="toggle-btn" data-st-port="on" onclick="stSetPort(\'on\')">On</button>' +
        '</div>' +
      '</div>' +
      '<div class="rating-tiles s1-rating-tiles" id="' + stCur.idp + '-pattern-tiles"></div>' +
      '<div class="group-captions">' + captionsHtml + '</div>' +
      '<div class="table-wrap"><div class="v2-hscroll">' +  /* MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER */
        '<table class="data-table st-main-table" id="' + stCur.idp + '-main-table">' +
          '<colgroup>' + colgroupHtml + '</colgroup>' +
          '<thead>' + theadRows + '</thead>' +
          '<tbody id="' + stCur.idp + '-tbody"></tbody>' +
        '</table>' +
      '</div></div>';  /* MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER */
    host.innerHTML = html;
    var tiles = document.getElementById(stCur.idp + '-pattern-tiles');
    if (tiles) {
      tiles.addEventListener('click', function(e) {
        var chip = e.target.closest('.pi-tier-chip');
        if (chip) {
          var cp = chip.getAttribute('data-pattern');
          var ct = chip.getAttribute('data-tier');
          if (cp && ct) stToggleTier(cp, ct);
          return;
        }
        var tile = e.target.closest('.rating-tile');
        if (!tile) return;
        var k = tile.getAttribute('data-pattern');
        if (k) stSelectAllTiers(k);
      });
    }
    var hdr = document.getElementById(stCur.idp + '-col-header-row');
    if (hdr) {
      hdr.addEventListener('click', function(e) {
        var th = e.target.closest('th');
        if (!th) return;
        var key = th.getAttribute('data-sort-key');
        if (key) stOnSort(key);
      });
    }
    return true;
  }

  // MD-V2-SETUPS-SPLIT-S33-MARKER: control-bar state is shared across both setups
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
  window.renderSetupsS2VCP = renderSetupsS2VCP;

})();

/* MD-V2-SETUPS-MARKER-END */

/* MD-V2-SETUPS-MARKER-MODULE-END */
/* MD-V2-TESTS-MARKER-MODULE-START */
// =============================================================================
// CAPITAL QUALIFICATION TESTS TAB MODULE - Master Dashboard V2
// =============================================================================
// MD-V2-TESTS-MARKER - idempotency marker for patcher detection
//
// 3 capital qualification tests from _md_v2_screens.py md["tests"]:
//   Probing Bet test: stage flag (existing probing_bet filter)
//   VCP test: composite with 4 constituent checks
//   Uptrend Retest test: stage flag (existing uptrend_retest filter)
//
// Each test's constituent checks are surfaced as individual tick columns.
// =============================================================================

/* MD-V2-TESTS-MARKER-START */

(function() {
  'use strict';

  // MD-V2-TESTS-S27-MARKER: Capital deployment tests tab - Session 27 rebuild.
  // 4 tests (D-MD-V2-64): ma_retest_upwards / vcp_deploy_s1 / vcp_deploy_s2 /
  // probing_bet. Each test shown "in totality" (D-MD-V2-65): its related
  // setup's test columns + trigger columns side by side. Plus a 4-stage info
  // block (D-MD-V2-66), the Collapsing-rating info column on Probing bet, and
  // L5D/L20D recent-trigger columns (D-MD-V2-67, persist-and-append history).
  // Structure (chip filter, rating/score, pass-count breakdown, sortable
  // headers, scope/tint/portfolio controls) carried from the proven S26 ct
  // module unchanged.

  var ctState = {
    mode: { inputs: 'pct', tests: 'tick' },
    scope: 'all',
    tierFilter: {},
    tint: 'none',
    port: 'off',
    sort: { col: 'company', dir: 'asc' }
  };

  // Each pattern: key (matches md_v2.tests key), labels, tierLadder, total
  // (number of constituent tests), and the ordered `tests` list. Test keys
  // are prefixed by kind in the pipeline: g* = gate, s* = setup column,
  // v* = VCP contraction column, x* = trigger column. The module does not
  // care about the prefix beyond grouping/labelling.
  var CT_PATTERNS = [
    {
      "key": "ma_retest_upwards",
      "label": "Upwards moving average retest",
      "shortLabel": "MA retest",
      "tone": "teal",
      "tierLadder": ["Possible", "Plausible", "Probable"],
      "total": 8,
      "tooltip": "Price reclaims a test moving average on a healthy retest, with a confirming up-day.",
      "caption": "<span class='db'>The trigger that pairs with the Healthy retest setup</span> &mdash; price reclaiming the moving average it pulled back to.<span class='intro'>Six setup columns + two trigger columns. To qualify:</span><span class='tline'><span class='tnum'>(1)</span> Is price <u>testing a meaningful MA</u> and has it <u>closed back above it</u>?</span><span class='tline'><span class='tnum'>(2)</span> Is the reclaim <u>confirmed by a close at least 2% above yesterday</u>?</span><span class='tline'><span class='tnum'>(3)</span> Was the pullback itself <u>healthy</u> &mdash; orderly on volume, distribution, volatility and candles (the six setup columns)?</span>",
      "tests": [
        { "key": "s1_volume_contracting",      "label": "Volume contracting",        "group": "setup",   "tooltip": "10-day average volume below the 50-day - selling is drying up through the pullback" },
        { "key": "s2_updown_vol_ge105",        "label": "Up-vol ≥ down-vol",     "group": "setup",   "tooltip": "Up-day volume at least 5% above down-day volume over the last month" },
        { "key": "s3_few_distribution_days",   "label": "Few distribution days",      "group": "setup",   "tooltip": "Three or fewer distribution days over the last 25 sessions" },
        { "key": "s4_volatility_contracting",  "label": "Volatility contracting",     "group": "setup",   "tooltip": "10-day ATR below the 20-day - the pullback is orderly, not violent" },
        { "key": "s5_testing_meaningful_ma",   "label": "Testing a meaningful MA",    "group": "setup",   "tooltip": "Price has come down to within range of a 50/100/150/200-day moving average" },
        { "key": "s6_buying_through_l10d",     "label": "Buying through 10 days",     "group": "setup",   "tooltip": "At least half of the last 10 days closed in the upper 40% of their daily range" },
        { "key": "x1_reclaim_close_above_ma",  "label": "Reclaimed the MA",           "group": "trigger", "tooltip": "Current price is back above the moving average being tested" },
        { "key": "x2_confirmation_close_ge2pct","label": "Confirmation: close 2%+ up","group": "trigger", "tooltip": "Today's close is at least 2% above yesterday's - the confirmation test that avoids false starts" }
      ]
    },
    {
      "key": "vcp_deploy_s1",
      "label": "VCP after Stage 1→2",
      "shortLabel": "VCP after S1→2",
      "tone": "green",
      "tierLadder": ["Possible", "Plausible", "Probable"],
      "total": 7,
      "tooltip": "A volatility-contraction pattern firing out of a Stage 1 base that is rated Probable.",
      "caption": "<span class='db'>The deployment trigger for a VCP breaking out of a Stage 1 base</span>.<span class='intro'>One gate + four contraction + two trigger columns. To pass &mdash; gate AND all four contractions AND breakout AND confirmation:</span><span class='tline'><span class='tnum'>(1)</span> Gate: is <u>Stage 1 rated Probable</u> (Early or Late)?</span><span class='tline'><span class='tnum'>(2)</span> Do the four VCP tests pass &mdash; <u>narrowing contractions, 2-4 of them, declining volume, higher lows</u>?</span><span class='tline'><span class='tnum'>(3)</span> Trigger: is the <u>Breakout indicator firing</u>, <u>confirmed by a close at least 2% above yesterday</u>?</span>",
      "tests": [
        { "key": "g1_stage1_probable",          "label": "Stage 1 = Probable",        "group": "gate",    "tooltip": "Stage 1 rating is Probable Early or Probable Late - either qualifies" },
        { "key": "v1_narrowing_contractions",   "label": "Narrowing contractions",    "group": "vcp",     "tooltip": "Each price contraction is strictly shallower than the one before it" },
        { "key": "v2_sufficient_count",         "label": "2-4 contractions",          "group": "vcp",     "tooltip": "Between two and four contractions in the base" },
        { "key": "v3_volume_declining",         "label": "Volume declining",          "group": "vcp",     "tooltip": "Average volume falls across successive contractions" },
        { "key": "v4_higher_lows",              "label": "Higher lows",               "group": "vcp",     "tooltip": "Each contraction low sits above the previous contraction low" },
        { "key": "x1_breakout",                 "label": "Breakout",                  "group": "trigger", "tooltip": "The Breakout post-test indicator fires" },
        { "key": "x2_confirmation_close_ge2pct","label": "Confirmation: close 2%+ up","group": "trigger", "tooltip": "Today's close is at least 2% above yesterday's - the confirmation test that avoids false starts" }
      ]
    },
    {
      "key": "vcp_deploy_s2",
      "label": "VCP after Stage 2 base",
      "shortLabel": "VCP after S2 base",
      "tone": "navy",
      "tierLadder": ["Possible", "Plausible", "Probable"],
      "total": 7,
      "tooltip": "A volatility-contraction pattern firing out of a Stage 2 base that is consolidating.",
      "caption": "<span class='db'>The deployment trigger for a VCP breaking out of a fresh Stage 2 base</span>.<span class='intro'>One gate + four contraction + two trigger columns. To pass &mdash; gate AND all four contractions AND breakout AND confirmation:</span><span class='tline'><span class='tnum'>(1)</span> Gate: is the stock in a <u>Stage 2 uptrend with the Basing indicator qualifying</u>?</span><span class='tline'><span class='tnum'>(2)</span> Do the four VCP tests pass &mdash; <u>narrowing contractions, 2-4 of them, declining volume, higher lows</u>?</span><span class='tline'><span class='tnum'>(3)</span> Trigger: is the <u>Breakout indicator firing</u>, <u>confirmed by a close at least 2% above yesterday</u>?</span>",
      "tests": [
        { "key": "g1_stage2_basing",            "label": "Stage 2 basing",            "group": "gate",    "tooltip": "Stage 2 uptrend AND the Basing pre-test indicator qualifies" },
        { "key": "v1_narrowing_contractions",   "label": "Narrowing contractions",    "group": "vcp",     "tooltip": "Each price contraction is strictly shallower than the one before it" },
        { "key": "v2_sufficient_count",         "label": "2-4 contractions",          "group": "vcp",     "tooltip": "Between two and four contractions in the base" },
        { "key": "v3_volume_declining",         "label": "Volume declining",          "group": "vcp",     "tooltip": "Average volume falls across successive contractions" },
        { "key": "v4_higher_lows",              "label": "Higher lows",               "group": "vcp",     "tooltip": "Each contraction low sits above the previous contraction low" },
        { "key": "x1_breakout",                 "label": "Breakout",                  "group": "trigger", "tooltip": "The Breakout post-test indicator fires" },
        { "key": "x2_confirmation_close_ge2pct","label": "Confirmation: close 2%+ up","group": "trigger", "tooltip": "Today's close is at least 2% above yesterday's - the confirmation test that avoids false starts" }
      ]
    },
    {
      "key": "probing_bet",
      "label": "Probing bet",
      "shortLabel": "Probing bet",
      "tone": "amber",
      "tierLadder": ["Possible", "Plausible", "Probable"],
      "total": 3,
      "tooltip": "The probing-bet trigger - a qualifying probing-bet stage that breaks out with a confirming up-day.",
      "caption": "<span class='db'>The deployment trigger for the Probing bet setup</span> &mdash; a fresh breakout on a stock worth a small starter position.<span class='intro'>One setup + two trigger columns (Collapsing shown as context only). To pass:</span><span class='tline'><span class='tnum'>(1)</span> Setup: does the <u>Probing bet filter rate the stock Late or Capital</u>?</span><span class='tline'><span class='tnum'>(2)</span> Trigger: is the <u>Breakout indicator firing</u>?</span><span class='tline'><span class='tnum'>(3)</span> Trigger: is it <u>confirmed by a close at least 2% above yesterday</u>?</span>",
      "tests": [
        { "key": "s1_pb_stage_late_or_capital", "label": "PB stage late/capital",     "group": "setup",   "tooltip": "The probing-bet filter rates this stock Late or Capital" },
        { "key": "x1_breakout",                 "label": "Breakout",                  "group": "trigger", "tooltip": "The Breakout post-test indicator fires" },
        { "key": "x2_confirmation_close_ge2pct","label": "Confirmation: close 2%+ up","group": "trigger", "tooltip": "Today's close is at least 2% above yesterday's - the confirmation test that avoids false starts" }
      ]
    }
  ];

  // Tone -> CSS class fragments (reuses the PI tile/chip/strip families).
  var CT_TONE_TILE  = { teal:'pi-tile-pullback', green:'pi-tile-basing', navy:'pi-tile-navy', amber:'pi-tile-amber' };
  var CT_TONE_STRIP = { teal:'pi-strip-pullback', green:'pi-strip-basing', navy:'pi-strip-navy', amber:'pi-strip-amber' };
  var CT_TONE_CHIP  = { teal:'pullback', green:'basing', navy:'navy', amber:'amber' };

  for (var _ip = 0; _ip < CT_PATTERNS.length; _ip++) {
    ctState.tierFilter[CT_PATTERNS[_ip].key] = [];
  }

  var CT_RATING_RANK = { 'Probable':5, 'Probable Late':5, 'Probable Early':4, 'Plausible':3, 'Possible':2, 'None':1 };
  var CT_RATING_CLS  = { 'Probable':'tint-prob', 'Plausible':'tint-pla', 'Possible':'tint-pos', 'None':'tint-none' };

  // --- column model ---
  // Input columns (8) + 4-stage info block (4) + per-pattern blocks.
  // Each pattern block = [rating][score][...test columns...][L5D][L20D].
  // probing_bet additionally carries an info column for the Collapsing rating.
  function ctBuildCols() {
    var cols = [
      { id:'name',     label:'Company - Ticker',       sortKey:'company',         cls:'name-cell', kind:'input' },
      { id:'taxon',    label:'Industry - Sector',      sortKey:'sector',          cls:'taxon',     kind:'input' },
      { id:'price',    label:'Price',                  sortKey:'price',           cls:'num',       kind:'input' },
      { id:'high_52w', label:'52 week high',           sortKey:'high_52w',        cls:'num',       kind:'input' },
      { id:'low_52w',  label:'52 week low',            sortKey:'low_52w',         cls:'num',       kind:'input' },
      { id:'ma_150',   label:'150D MA', sortKey:'ma_150',          cls:'num',       kind:'input' },
      { id:'ma_200',   label:'200D MA', sortKey:'ma_200',          cls:'num',       kind:'input' },
      { id:'pullback', label:'Recent pullback',        sortKey:'recent_pullback', cls:'num',       kind:'input' }
    ];
    // 4-stage info block (D-MD-V2-66) - info only, not in any qualify logic.
    var STAGES = [
      { id:'stage_1', label:'Stage 1' }, { id:'stage_2', label:'Stage 2' },
      { id:'stage_3', label:'Stage 3' }, { id:'stage_4', label:'Stage 4' }
    ];
    for (var si = 0; si < STAGES.length; si++) {
      cols.push({
        id:'info_'+STAGES[si].id, label:STAGES[si].label, sortKey:'stageinfo__'+STAGES[si].id,
        cls:(si===0?'grp-start-stageinfo ':'')+'ct-stage-info-col', kind:'stageinfo', stageKey:STAGES[si].id,
        tooltip:STAGES[si].label+' rating for this stock - context only, not part of any test'
      });
    }
    // per-pattern blocks
    for (var p = 0; p < CT_PATTERNS.length; p++) {
      var pat = CT_PATTERNS[p];
      var gi = p + 1;
      cols.push({ id:'p'+gi+'_rating', label:'Rating', sortKey:pat.key+'__rating', cls:'grp-start-g'+gi+' pi-rating-col', kind:'rating', patternKey:pat.key });
      cols.push({ id:'p'+gi+'_score',  label:'Score',  sortKey:pat.key+'__score',  cls:'pi-score-col',                   kind:'score',  patternKey:pat.key });
      for (var t = 0; t < pat.tests.length; t++) {
        var test = pat.tests[t];
        cols.push({
          id:'p'+gi+'t'+(t+1), label:test.label, sortKey:pat.key+'__'+test.key,
          cls:'ct-test-'+test.group, tooltip:test.tooltip, kind:'test',
          patternKey:pat.key, testKey:test.key, testGroup:test.group
        });
      }
      // probing_bet: Collapsing-rating info column (D-MD-V2-65)
      if (pat.key === 'probing_bet') {
        cols.push({
          id:'p'+gi+'_collapsing', label:'Collapsing rating', sortKey:pat.key+'__info_collapsing',
          cls:'ct-info-col', kind:'infocollapsing', patternKey:pat.key,
          tooltip:'The Collapsing pre-test indicator rating - context only, not part of the probing-bet pass logic'
        });
      }
      // L5D / L20D recent-trigger windows (D-MD-V2-67)
      cols.push({
        id:'p'+gi+'_l5d', label:'Fired 5d', sortKey:pat.key+'__l5d',
        cls:'ct-window-col', kind:'window', patternKey:pat.key, windowKey:'l5d',
        tooltip:'Did this test fire in the last 5 trading days - shows days since the most recent fire'
      });
      cols.push({
        id:'p'+gi+'_l20d', label:'Fired 20d', sortKey:pat.key+'__l20d',
        cls:'ct-window-col', kind:'window', patternKey:pat.key, windowKey:'l20d',
        tooltip:'Did this test fire in the last 20 trading days - shows days since the most recent fire'
      });
    }
    return cols;
  }
  var CT_COLS = ctBuildCols();
  var CT_INPUT_COUNT = 8;
  var CT_STAGEINFO_COUNT = 4;

  // --- data lookups ---
  function ctPricesLookup() {
    if (window._ctPricesByTicker) return window._ctPricesByTicker;
    var out = {};
    var arr = (window.MASTER_DATA && MASTER_DATA.prices) || [];
    for (var i = 0; i < arr.length; i++) if (arr[i] && arr[i].ticker) out[arr[i].ticker] = arr[i];
    window._ctPricesByTicker = out;
    return out;
  }
  function ctLiveTickers() {
    var out = {};
    var inv = (window.MASTER_DATA && MASTER_DATA.positions && MASTER_DATA.positions.investments) || [];
    for (var i = 0; i < inv.length; i++) if (inv[i].ticker) out[inv[i].ticker] = true;
    return out;
  }
  function ctLiveSectors() {
    var out = {}, t, prices = ctPricesLookup(), tickers = ctLiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.sector) out[p.sector] = true; }
    return out;
  }
  function ctLiveIndustries() {
    var out = {}, t, prices = ctPricesLookup(), tickers = ctLiveTickers();
    for (t in tickers) { var p = prices[t]; if (p && p.industry) out[p.industry] = true; }
    return out;
  }
  function ctPatternRec(row, patternKey) {
    var dk = row.md_v2 && row.md_v2.tests;
    return (dk && dk[patternKey]) || null;
  }
  function ctEvalTest(row, patternKey, testKey) {
    var rec = ctPatternRec(row, patternKey);
    if (!rec || !rec.tests) return false;
    return !!rec.tests[testKey];
  }
  function ctRowRating(row, patternKey) {
    var rec = ctPatternRec(row, patternKey);
    return rec ? (rec.rating || 'None') : 'None';
  }
  function ctStageRating(row, stageKey) {
    var md = row.md_v2 || {};
    var st = md[stageKey];
    return (st && st.rating) || 'None';
  }
  function ctGetRows() {
    var raw = (window.MASTER_DATA && MASTER_DATA.filters) || [];
    var prices = ctPricesLookup();
    var live = ctLiveTickers(), liveS = ctLiveSectors(), liveI = ctLiveIndustries();
    var rows = [];
    for (var i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || !s.md_v2 || !s.md_v2.tests) continue;
      var p = prices[s.ticker] || {};
      var mas = p.mas || {};
      rows.push({
        ticker: s.ticker, company: p.company_name || s.ticker,
        sector: p.sector || '', industry: p.industry || '',
        price: p.price, high_52w: p.high_52w, low_52w: p.low_52w,
        recent_pullback: p.recent_pullback_pct,
        ma_150: mas['150D'], ma_200: mas['200D'],
        md_v2: s.md_v2,
        is_live: !!live[s.ticker],
        sector_in_portfolio: !!liveS[p.sector],
        industry_in_portfolio: !!liveI[p.industry]
      });
    }
    return rows;
  }

  // --- counts / histograms / tier counts ---
  function ctPatternCounts(rows) {
    var c = {};
    for (var pi = 0; pi < CT_PATTERNS.length; pi++) c[CT_PATTERNS[pi].key] = 0;
    for (var i = 0; i < rows.length; i++) {
      for (var p = 0; p < CT_PATTERNS.length; p++) {
        var rec = ctPatternRec(rows[i], CT_PATTERNS[p].key);
        if (rec && rec.qualifies) c[CT_PATTERNS[p].key]++;
      }
    }
    return c;
  }
  function ctPassHistogram(rows, patternKey, total) {
    var h = [];
    for (var k = 0; k <= total; k++) h[k] = 0;
    for (var i = 0; i < rows.length; i++) {
      var rec = ctPatternRec(rows[i], patternKey);
      var cnt = rec ? (rec.count || 0) : 0;
      if (cnt >= 0 && cnt <= total) h[cnt]++;
    }
    return h;
  }
  function ctTierCounts(rows, patternKey) {
    var c = { 'Possible':0, 'Plausible':0, 'Probable':0, 'None':0 };
    for (var i = 0; i < rows.length; i++) {
      var r = ctRowRating(rows[i], patternKey);
      if (c[r] != null) c[r]++;
    }
    return c;
  }

  // --- formatting helpers ---
  function ctFmtNum(n) {
    if (n == null || isNaN(n)) return '-';
    var abs = Math.abs(n);
    var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);
    if (Math.abs(n - Math.round(n)) < 1e-9) dp = 0; /* MD-V2-S40-FMTNUM-INT-FIX-ct; S41 tolerance */
    var f = abs.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });
    return n < 0 ? '(' + f + ')' : f;
  }
  function ctFmtPct(p) {
    if (p == null || isNaN(p)) return '-';
    var r = Math.round(p), abs = Math.abs(r);
    return r < 0 ? '(' + abs + ')%' : r + '%';
  }
  function ctColourForIntensity(i) {
    if (i >= 0.6) return '#0F6E56';
    if (i >= 0.25) return '#1D9E75';
    if (i >= 0.05) return '#5DCAA5';
    if (i <= -0.6) return '#A32D2D';
    if (i <= -0.25) return '#E24B4A';
    if (i <= -0.05) return '#F09595';
    return '#888';
  }
  function ctInputCell(row, key, extraCls) {
    extraCls = extraCls || '';
    var v = row[key];
    if (key === 'price') return '<td class="num ' + extraCls + '">' + ctFmtNum(v) + '</td>';
    if (key === 'recent_pullback') {
      if (v == null || isNaN(v)) return '<td class="num ' + extraCls + '">-</td>';
      var pctVal = v * 100;
      var pi_intensity = Math.max(-1, Math.min(1, (pctVal - 5) / 20));
      var col = ctColourForIntensity(-pi_intensity);
      return '<td class="num ' + extraCls + '" style="color:' + col + '">' + Math.round(pctVal) + '%</td>';
    }
    if (v == null || row.price == null) return '<td class="num ' + extraCls + '">-</td>';
    var pct = (row.price - v) / v * 100;
    var intensity = 0;
    if (key === 'high_52w') intensity = Math.max(-1, Math.min(1, (-pct - 5) / 20));
    else if (key === 'low_52w') intensity = Math.max(-1, Math.min(1, (pct - 20) / 30));
    else if (key === 'ma_150' || key === 'ma_200') intensity = Math.max(-1, Math.min(1, pct / 10));
    var colour = ctColourForIntensity(intensity);
    var text = (ctState.mode.inputs === 'pct') ? ctFmtPct(pct) : ctFmtNum(v);
    return '<td class="num ' + extraCls + '" style="color:' + colour + '">' + text + '</td>';
  }
  // 4-stage info block cell - shows the stage rating label, muted styling.
  function ctStageInfoCell(row, col) {
    var rating = ctStageRating(row, col.stageKey);
    var rcls = CT_RATING_CLS[rating] || (rating.indexOf('Probable') === 0 ? 'tint-prob'
              : rating.indexOf('Plausible') === 0 ? 'tint-pla'
              : rating.indexOf('Possible') === 0 ? 'tint-pos' : 'tint-none');
    return '<td class="' + (col.cls || '') + ' ct-stage-info-cell ' + rcls + '">' +
           '<span class="ct-info-label">' + rating + '</span></td>';
  }
  // Collapsing-rating info column on Probing bet.
  function ctInfoCollapsingCell(row, col) {
    var rec = ctPatternRec(row, col.patternKey);
    var rating = (rec && rec.info_collapsing_rating) || 'None';
    var rcls = CT_RATING_CLS[rating] || 'tint-none';
    return '<td class="' + (col.cls || '') + ' ct-info-cell ' + rcls + '">' +
           '<span class="ct-info-label">' + rating + '</span></td>';
  }
  /* MD-V2-WAVE4-TEST-VALUES-TOGGLE-MARKER */
  function ctTestValueFor(row, col) {
    var rec = ctPatternRec(row, col.patternKey);
    var tv = rec && rec.test_values;
    if (!tv || !(col.testKey in tv)) return '\u2014';
    var v = tv[col.testKey];
    if (v === null || v === undefined) return '\u2014';
    if (typeof v === 'string') return v;
    if (typeof v === 'number') {
      if (isNaN(v)) return '\u2014';
      if (Math.abs(v) <= 1.5 && v !== Math.round(v)) return ctFmtPct(v * 100);
      return ctFmtNum(v);
    }
    return String(v);
  }
  function ctTestCell(row, col) {
    var pass = ctEvalTest(row, col.patternKey, col.testKey);
    var extra = col.cls || '';
    if (ctState.mode.tests === 'val') {
      var v = ctTestValueFor(row, col);
      var colour = pass ? ctColourForIntensity(0.7) : ctColourForIntensity(-0.4);
      return '<td class="test-val pi-' + (pass ? 'pass' : 'fail') + ' ' + extra + '" style="color:' + colour + '">' + v + '</td>';
    }
    if (pass) return '<td class="pi-pass ' + extra + '"><span class="tick">' + String.fromCharCode(10003) + '</span></td>';
    return '<td class="pi-fail ' + extra + '">.</td>';
  }
  function ctRatingCell(row, col) {
    var rating = ctRowRating(row, col.patternKey);
    var rcls = CT_RATING_CLS[rating] || 'tint-none';
    return '<td class="' + (col.cls || '') + ' pi-rating-cell ' + rcls + '"><span class="pi-pill pi-pill-' + rcls + '">' + rating + '</span></td>';
  }
  function ctScoreCell(row, col) {
    var rec = ctPatternRec(row, col.patternKey);
    var cnt = rec ? (rec.count || 0) : 0;
    var tot = rec ? (rec.total || 0) : 0;
    var s = '';
    for (var i = 0; i < tot; i++) s += '<span class="pip ' + (i < cnt ? 'on' : '') + '"></span>';
    return '<td class="' + (col.cls || '') + ' pi-score-cell"><div class="pi-pip-row">' + s +
           '<span class="pi-score-num">' + cnt + '/' + tot + '</span></div></td>';
  }
  // L5D / L20D recent-trigger window cell (D-MD-V2-67).
  // Reads fired_l5d / fired_l20d / days_since_fired / history_depth, all
  // stamped onto the test record by the pipeline's apply_test_history().
  // Graceful degradation: if history_depth is too thin for this window,
  // the cell shows "building" rather than a misleading blank.
  function ctWindowCell(row, col) {
    var rec = ctPatternRec(row, col.patternKey);
    var extra = col.cls || '';
    if (!rec) return '<td class="' + extra + ' ct-window-na">-</td>';
    var depth = rec.history_depth || 0;
    var windowDays = (col.windowKey === 'l5d') ? 5 : 20;
    // Not enough accumulated history to make this window meaningful yet.
    if (depth < windowDays) {
      return '<td class="' + extra + ' ct-window-building" title="' + depth +
             ' of ' + windowDays + ' days of history accumulated">building</td>';
    }
    var fired = (col.windowKey === 'l5d') ? !!rec.fired_l5d : !!rec.fired_l20d;
    if (!fired) {
      return '<td class="' + extra + ' ct-window-none">-</td>';
    }
    var ds = rec.days_since_fired;
    var label, shadeCls;
    if (ds === 0) { label = 'today'; }
    else if (ds === 1) { label = '1d ago'; }
    else if (ds != null) { label = ds + 'd ago'; }
    else { label = 'fired'; }
    // shading: green within 5 days, amber within 20 (D-MD-V2-67)
    if (ds != null && ds <= 5) shadeCls = 'ct-window-fired-recent';
    else shadeCls = 'ct-window-fired-older';
    return '<td class="' + extra + ' ' + shadeCls + '" title="most recent fire ' + label + '">' +
           '<span class="ct-window-label">' + label + '</span></td>';
  }
  function ctHashColor(label, alpha) {
    if (!label) return null;
    var h = 0;
    for (var i = 0; i < label.length; i++) h = (h * 31 + label.charCodeAt(i)) & 0xffff;
    return 'hsla(' + (h % 360) + ', 35%, 55%, ' + alpha + ')';
  }
  function ctPortfolioInfo(row) {
    if (row.is_live) return { color:'#1b5e20', bg:'rgba(27,94,32,0.10)', bgHover:'rgba(27,94,32,0.14)' };
    if (row.sector_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.05)', bgHover:'rgba(27,94,32,0.08)' };
    if (row.industry_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.025)', bgHover:'rgba(27,94,32,0.05)' };
    return null;
  }

  // --- sorting ---
  function ctGetSortVal(row, key) {
    if (key.indexOf('stageinfo__') === 0) {
      var sk = key.split('__')[1];
      return CT_RATING_RANK[ctStageRating(row, sk)] || 0;
    }
    if (key.indexOf('__') > 0) {
      var parts = key.split('__');
      var patternKey = parts[0], sub = parts[1];
      var rec = ctPatternRec(row, patternKey);
      if (sub === 'rating') return rec ? (CT_RATING_RANK[rec.rating] || 0) : 0;
      if (sub === 'score')  return rec ? (rec.count || 0) : 0;
      if (sub === 'info_collapsing') return rec ? (CT_RATING_RANK[rec.info_collapsing_rating] || 0) : 0;
      if (sub === 'l5d' || sub === 'l20d') {
        // sort: fired-recently first (smaller days-since = higher), then
        // fired-older, then not-fired, then building/no-data last.
        if (!rec) return -1;
        var windowDays = (sub === 'l5d') ? 5 : 20;
        var depth = rec.history_depth || 0;
        if (depth < windowDays) return -2;  // building - sort to the bottom
        var fired = (sub === 'l5d') ? rec.fired_l5d : rec.fired_l20d;
        if (!fired) return -1;
        var ds = rec.days_since_fired;
        return (ds == null) ? 0 : (1000 - ds);  // smaller days-since ranks higher
      }
      return ctEvalTest(row, patternKey, sub) ? 1 : 0;
    }
    if (key === 'recent_pullback') return row.recent_pullback == null ? -Infinity : row.recent_pullback;
    var PCT_KEYS = ['high_52w','low_52w','ma_150','ma_200'];
    if (PCT_KEYS.indexOf(key) > -1 && ctState.mode.inputs === 'pct') {
      var ref = row[key];
      if (ref == null || row.price == null || ref === 0) return -Infinity;
      return (row.price - ref) / ref * 100;
    }
    if (key in row) return row[key];
    return 0;
  }
  function ctOnSort(key) {
    if (ctState.sort.col === key) ctState.sort.dir = ctState.sort.dir === 'desc' ? 'asc' : 'desc';
    else ctState.sort = { col: key, dir: key === 'company' ? 'asc' : 'desc' };
    ctBuildHeaderRow();
    ctRenderRows();
  }
  function ctBuildHeaderRow() {
    var tr = document.getElementById('ct-col-header-row');
    if (!tr) return;
    var h = '';
    for (var i = 0; i < CT_COLS.length; i++) {
      var c = CT_COLS[i];
      var isSort = ctState.sort.col === c.sortKey;
      var arrow = isSort
        ? '<span class="sort-arrow">' + (ctState.sort.dir === 'desc' ? String.fromCharCode(9660) : String.fromCharCode(9650)) + '</span>'
        : '<span class="sort-placeholder"></span>';
      var title = c.tooltip || c.label;
      h += '<th class="' + (c.cls || '') + '" data-sort-key="' + c.sortKey + '" title="' + title + '">' +
           '<span class="hd"><span class="lbl">' + c.label + '</span>' + arrow + '</span></th>';
    }
    tr.innerHTML = h;
  }
  // --- tiles (chip filter unchanged from S26 ct module) ---
  function ctPatternTiles(scopeRows) {
    var tiles = document.getElementById('ct-pattern-tiles');
    if (!tiles) return;
    var counts = ctPatternCounts(scopeRows);
    var total = scopeRows.length;
    var h = '';
    for (var i = 0; i < CT_PATTERNS.length; i++) {
      var pat = CT_PATTERNS[i];
      var cnt = counts[pat.key] || 0;
      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;
      var sel = ctState.tierFilter[pat.key] || [];
      var anySel = sel.length > 0;
      var tierCounts = ctTierCounts(scopeRows, pat.key);
      var headline = cnt, headSub = 'of ' + total.toLocaleString('en-GB') + ' &middot; ' + pct + '%';
      if (anySel) {
        var ft = 0;
        for (var z = 0; z < sel.length; z++) ft += (tierCounts[sel[z]] || 0);
        headline = ft;
        headSub = sel.join(' + ') + ' &middot; filtered';
      }
      var hist = ctPassHistogram(scopeRows, pat.key, pat.total);
      var breakdown = '';
      for (var k = 1; k <= pat.total; k++) {
        if (k > 1) breakdown += ' &middot; ';
        breakdown += k + ' of ' + pat.total + ': ' + (hist[k] || 0).toLocaleString('en-GB');
      }
      var chips = '';
      for (var c = 0; c < 3; c++) {  /* MD-V2-S37-FOLLOWUP-MARKER: canonical 3-tier chip set */
        var tier = ['Possible','Plausible','Probable'][c];
        var on = sel.indexOf(tier) > -1;
        var tc = tierCounts[tier] || 0;
        chips += '<span class="pi-tier-chip pi-chip-' + CT_TONE_CHIP[pat.tone] +
                 (on ? ' on' : '') + '" data-pattern="' + pat.key + '" data-tier="' + tier + '">' +
                 tier + ' ' + tc.toLocaleString('en-GB') + (on ? ' ' + String.fromCharCode(10003) : '') + '</span>';
      }
      var activeCls = anySel ? ' active' : '';
      h += '<div class="rating-tile ' + CT_TONE_TILE[pat.tone] + activeCls + '" data-pattern="' + pat.key + '" title="' + pat.tooltip + '">' +
           '<div class="rt-label">' + pat.shortLabel + '</div>' +
           '<div class="rt-count">' + headline.toLocaleString('en-GB') + '</div>' +
           '<div class="rt-sub">' + headSub + '</div>' +
           '<div class="rt-breakdown">' + breakdown + '</div>' +
           '<div class="pi-tier-chips" data-pattern="' + pat.key + '">' + chips + '</div>' +
           '<div class="rt-strip ' + CT_TONE_STRIP[pat.tone] + '"></div>' +
           '</div>';
    }
    tiles.innerHTML = h;
  }
  function ctUpdateScopeCounts(rows) {
    function set(id, n) { var el = document.getElementById(id); if (el) el.textContent = '(' + n + ')'; }
    set('ct-cnt-all',      rows.length);
    set('ct-cnt-live',     rows.filter(function(r){ return r.is_live; }).length);
    set('ct-cnt-sector',   rows.filter(function(r){ return r.sector_in_portfolio; }).length);
    set('ct-cnt-industry', rows.filter(function(r){ return r.industry_in_portfolio; }).length);
  }
  function ctApplyScope(all) {
    var rows = all.slice();
    if (ctState.scope === 'live') rows = rows.filter(function(r){ return r.is_live; });
    else if (ctState.scope === 'sector') rows = rows.filter(function(r){ return r.sector_in_portfolio; });
    else if (ctState.scope === 'industry') rows = rows.filter(function(r){ return r.industry_in_portfolio; });
    return rows;
  }
  function ctApplyTierFilter(rows) {
    var active = [];
    for (var p = 0; p < CT_PATTERNS.length; p++) {
      var k = CT_PATTERNS[p].key;
      var sel = ctState.tierFilter[k] || [];
      if (sel.length > 0) active.push({ key: k, tiers: sel });
    }
    if (active.length === 0) return rows;
    return rows.filter(function(r) {
      for (var a = 0; a < active.length; a++) {
        var rating = ctRowRating(r, active[a].key);
        if (active[a].tiers.indexOf(rating) === -1) return false;
      }
      return true;
    });
  }

  // --- main render ---
  function ctRenderRows() {
    var tbody = document.getElementById('ct-tbody');
    if (!tbody) return;
    var all = ctGetRows();
    var scopeRows = ctApplyScope(all);
    ctUpdateScopeCounts(all);
    ctPatternTiles(scopeRows);
    var rows = ctApplyTierFilter(scopeRows);
    rows.sort(function(a,b) {
      var va = ctGetSortVal(a, ctState.sort.col), vb = ctGetSortVal(b, ctState.sort.col);
      var cmp = (typeof va === 'string') ? va.localeCompare(vb) : (va || 0) - (vb || 0);
      if (cmp === 0) cmp = a.ticker.localeCompare(b.ticker);
      return ctState.sort.dir === 'desc' ? -cmp : cmp;
    });
    var html = '';
    for (var i = 0; i < rows.length; i++) {
      var s = rows[i];
      var styles = [], cls = [];
      if (ctState.tint === 'industry') { styles.push('--tint-bg: ' + ctHashColor(s.industry, 0.16)); cls.push('tint-row'); }
      else if (ctState.tint === 'sector') { styles.push('--tint-bg: ' + ctHashColor(s.sector, 0.16)); cls.push('tint-row'); }
      if (ctState.port === 'on') {
        var pinf = ctPortfolioInfo(s);
        if (pinf) {
          styles.push('--portfolio-color: ' + pinf.color);
          styles.push('--portfolio-bg: ' + pinf.bg);
          styles.push('--portfolio-bg-hover: ' + pinf.bgHover);
          cls.push('portfolio-band'); cls.push('portfolio-tint');
        }
      }
      var styleAttr = styles.length ? ' style="' + styles.join(';') + '"' : '';
      var clsAttr = cls.length ? ' class="' + cls.join(' ') + '"' : '';
      var liveDot = s.is_live ? '<span class="live-dot">' + String.fromCharCode(9679) + '</span>' : '';
      html += '<tr' + clsAttr + styleAttr + '>' +
        '<td class="name-cell"><div class="co">' + liveDot + (s.company || s.ticker) + '</div><div class="tk">' + s.ticker + '</div></td>' +
        '<td class="taxon"><div class="ind">' + (s.industry || '') + '</div><div class="sec">' + (s.sector || '') + '</div></td>' +
        ctInputCell(s, 'price') + ctInputCell(s, 'high_52w') + ctInputCell(s, 'low_52w') +
        ctInputCell(s, 'ma_150') + ctInputCell(s, 'ma_200') + ctInputCell(s, 'recent_pullback');
      // remaining columns: 4-stage info block + per-pattern blocks
      for (var j = CT_INPUT_COUNT; j < CT_COLS.length; j++) {
        var col = CT_COLS[j];
        if (col.kind === 'stageinfo') html += ctStageInfoCell(s, col);
        else if (col.kind === 'rating') html += ctRatingCell(s, col);
        else if (col.kind === 'score') html += ctScoreCell(s, col);
        else if (col.kind === 'infocollapsing') html += ctInfoCollapsingCell(s, col);
        else if (col.kind === 'window') html += ctWindowCell(s, col);
        else html += ctTestCell(s, col);
      }
      html += '</tr>';
    }
    tbody.innerHTML = html;
  }
  // --- control setters ---
  function ctSetMode(kind, val) {
    ctState.mode[kind] = val;
    var btns = document.querySelectorAll('button[data-ct-grp="' + kind + '"]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-ct-val') === val);
    ctRenderRows();
  }
  function ctSetScope(s) {
    ctState.scope = s;
    var btns = document.querySelectorAll('button[data-ct-scope]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-ct-scope') === s);
    ctRenderRows();
  }
  function ctSetTint(t) {
    ctState.tint = t;
    var btns = document.querySelectorAll('button[data-ct-tint]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-ct-tint') === t);
    ctRenderRows();
  }
  function ctSetPort(p) {
    ctState.port = p;
    var btns = document.querySelectorAll('button[data-ct-port]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-ct-port') === p);
    ctRenderRows();
  }
  function ctToggleTier(patternKey, tier) {
    var sel = ctState.tierFilter[patternKey] || [];
    var idx = sel.indexOf(tier);
    if (idx > -1) sel.splice(idx, 1);
    else sel.push(tier);
    ctState.tierFilter[patternKey] = sel;
    ctRenderRows();
  }
  function ctSelectAllTiers(patternKey) {
    // MD-V2-WAVE1-FROZEN-HEADERS-MARKER: tile-body click selects ONLY the Probable tier
    // (D-MD-V2-74). If exactly ['Probable'] is already selected,
    // clear it (toggle off). Tier chips remain direct multi-select.
    var pat = null;
    for (var p = 0; p < CT_PATTERNS.length; p++) if (CT_PATTERNS[p].key === patternKey) pat = CT_PATTERNS[p];
    if (!pat) return;
    var sel = ctState.tierFilter[patternKey] || [];
    var probable = (pat.tierLadder.indexOf('Probable') > -1) ? 'Probable'
                   : pat.tierLadder[pat.tierLadder.length - 1];
    var onlyProbable = (sel.length === 1 && sel[0] === probable);
    ctState.tierFilter[patternKey] = onlyProbable ? [] : [probable];
    ctRenderRows();
  }
  window.ctSetMode = ctSetMode;
  window.ctSetScope = ctSetScope;
  window.ctSetTint = ctSetTint;
  window.ctSetPort = ctSetPort;
  window.ctToggleTier = ctToggleTier;
  window.ctSelectAllTiers = ctSelectAllTiers;
  window.ctOnSort = ctOnSort;

  // --- scaffold ---
  // Per-pattern block width = 2 (rating+score) + N tests + 2 (L5D+L20D)
  //   + 1 extra for probing_bet's Collapsing-rating info column.
  function ctPatternBlockSpan(pat) {
    var span = 2 + pat.tests.length + 2;
    if (pat.key === 'probing_bet') span += 1;
    return span;
  }
  function ctBuildScaffold() {
    var host = document.getElementById('tab-tests');
    if (!host) return false;
    if (host.querySelector('#ct-main-table')) return true;

    // colgroup: inputs (8) + stage info (4) + per-pattern blocks
    var colgroupHtml = '<col class="c-name"><col class="c-taxon">' +
                       '<col class="c-price"><col class="c-52wh"><col class="c-52wl">' +
                       '<col class="c-ma150"><col class="c-ma200"><col class="c-pullback">';
    for (var sgc = 0; sgc < CT_STAGEINFO_COUNT; sgc++) colgroupHtml += '<col class="c-stageinfo">';

    // group-header row: Inputs span, Stage ratings span, then per-pattern
    var groupHtml = '<th class="gh-inputs" colspan="' + CT_INPUT_COUNT + '">Inputs</th>' +
                    '<th class="gh-stageinfo grp-start-stageinfo" colspan="' + CT_STAGEINFO_COUNT + '">Stage ratings</th>';

    for (var p = 0; p < CT_PATTERNS.length; p++) {
      var pat = CT_PATTERNS[p];
      var gi = p + 1;
      var span = ctPatternBlockSpan(pat);
      colgroupHtml += '<col class="c-rating"><col class="c-score">';
      for (var t = 0; t < pat.tests.length; t++) colgroupHtml += '<col class="c-test">';
      if (pat.key === 'probing_bet') colgroupHtml += '<col class="c-info">';
      colgroupHtml += '<col class="c-window"><col class="c-window">';
      groupHtml += '<th class="gh-g' + gi + ' grp-start-g' + gi + '" colspan="' + span + '">' + pat.label + '</th>';
    }

    var captionsHtml = '';
    for (var cp = 0; cp < CT_PATTERNS.length; cp++) {
      var cpat = CT_PATTERNS[cp];
      captionsHtml += '<div class="gcap gcap-g' + (cp+1) + '"><b>' + cpat.label + '</b>' + cpat.caption + '</div>';
    }

    var theadRows = '';
    // MD-V2-WAVE2-TESTS-SUBGROUP-MARKER: build the sub-group row. Each pattern block
    // splits into Rating | Setup | Trigger | Context sub-groups.
    // group in {setup,gate,vcp} -> Setup; group=trigger -> Trigger.
    var subGroupHtml = '<th class="sg-spacer" colspan="' + CT_INPUT_COUNT + '"></th>' +
                       '<th class="sg-spacer" colspan="' + CT_STAGEINFO_COUNT + '"></th>';
    for (var sp = 0; sp < CT_PATTERNS.length; sp++) {
      var spat = CT_PATTERNS[sp];
      var sgi = sp + 1;
      var setupCount = 0, triggerCount = 0;
      for (var st = 0; st < spat.tests.length; st++) {
        var grp = spat.tests[st].group;
        if (grp === 'trigger') triggerCount++;
        else setupCount++;
      }
      var contextCount = 2 + (spat.key === 'probing_bet' ? 1 : 0);
      subGroupHtml += '<th class="sub-g sub-g-rating sub-g' + sgi + '" colspan="2">Rating</th>';
      if (setupCount > 0) subGroupHtml += '<th class="sub-g sub-g-setup sub-g' + sgi + '" colspan="' + setupCount + '">Setup</th>';
      if (triggerCount > 0) subGroupHtml += '<th class="sub-g sub-g-trigger sub-g' + sgi + '" colspan="' + triggerCount + '">Trigger</th>';
      subGroupHtml += '<th class="sub-g sub-g-context sub-g' + sgi + '" colspan="' + contextCount + '">Context</th>';
    }
    theadRows += '<tr class="group-header-row">' + groupHtml + '</tr>';
    theadRows += '<tr class="sub-group-row">' + subGroupHtml + '</tr>';
    theadRows += '<tr class="col-header-row" id="ct-col-header-row"></tr>';

    var html = '' +
      '<div class="s1-intro">Capital deployment tests are the binary go / no-go triggers - the point at which a setup either passes its test (deploy capital) or fails it (wait or skip). Each test is shown in totality: its related setup&apos;s test columns and the trigger columns side by side, so you can see whether a stock is set up AND has just triggered in one row. The four stage ratings are carried as an info block for context. Each test also shows whether it fired in the last 5 and last 20 trading days - those windows build up day by day from saved history, so a window reads &quot;building&quot; until enough days have accumulated. Each tile has a rating-tier filter row: click a tier chip to show only stocks at that tier, or click the tile body to select all tiers. Tier selections within a test combine as OR; selections across tests combine as AND.</div>' +
      '<div class="controls s1-controls">' +
        '<div class="ctrl-grp"><span class="ctrl-label">Inputs</span>' +
          '<button class="toggle-btn active" data-ct-grp="inputs" data-ct-val="pct" onclick="ctSetMode(\'inputs\',\'pct\')">show as %</button>' +
          '<button class="toggle-btn" data-ct-grp="inputs" data-ct-val="raw" onclick="ctSetMode(\'inputs\',\'raw\')">show as numbers</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Tests</span>' +  /* MD-V2-WAVE4-TEST-VALUES-TOGGLE-MARKER */
          '<button class="toggle-btn active" data-ct-grp="tests" data-ct-val="tick" onclick="ctSetMode(\'tests\',\'tick\')">show ticks</button>' +
          '<button class="toggle-btn" data-ct-grp="tests" data-ct-val="val" onclick="ctSetMode(\'tests\',\'val\')">show test values</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Scope</span>' +
          '<button class="toggle-btn active" data-ct-scope="all" onclick="ctSetScope(\'all\')">All <span id="ct-cnt-all"></span></button>' +
          '<button class="toggle-btn" data-ct-scope="live" onclick="ctSetScope(\'live\')">Live <span id="ct-cnt-live"></span></button>' +
          '<button class="toggle-btn" data-ct-scope="sector" onclick="ctSetScope(\'sector\')">Sectors <span id="ct-cnt-sector"></span></button>' +
          '<button class="toggle-btn" data-ct-scope="industry" onclick="ctSetScope(\'industry\')">Industries <span id="ct-cnt-industry"></span></button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Peers</button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Cohorts</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Colour by</span>' +
          '<button class="toggle-btn active" data-ct-tint="none" onclick="ctSetTint(\'none\')">Off</button>' +
          '<button class="toggle-btn" data-ct-tint="industry" onclick="ctSetTint(\'industry\')">Industry</button>' +
          '<button class="toggle-btn" data-ct-tint="sector" onclick="ctSetTint(\'sector\')">Sector</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Portfolio tint</span>' +
          '<button class="toggle-btn active" data-ct-port="off" onclick="ctSetPort(\'off\')">Off</button>' +
          '<button class="toggle-btn" data-ct-port="on" onclick="ctSetPort(\'on\')">On</button>' +
        '</div>' +
      '</div>' +
      '<div class="rating-tiles s1-rating-tiles" id="ct-pattern-tiles"></div>' +
      '<div class="group-captions">' + captionsHtml + '</div>' +
      '<div class="table-wrap"><div class="v2-hscroll">' +  /* MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER */
        '<table class="data-table" id="ct-main-table">' +
          '<colgroup>' + colgroupHtml + '</colgroup>' +
          '<thead>' + theadRows + '</thead>' +
          '<tbody id="ct-tbody"></tbody>' +
        '</table>' +
      '</div></div>';  /* MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER */
    host.innerHTML = html;
    var tiles = document.getElementById('ct-pattern-tiles');
    if (tiles) {
      tiles.addEventListener('click', function(e) {
        var chip = e.target.closest('.pi-tier-chip');
        if (chip) {
          var cp = chip.getAttribute('data-pattern');
          var ct = chip.getAttribute('data-tier');
          if (cp && ct) ctToggleTier(cp, ct);
          return;
        }
        var tile = e.target.closest('.rating-tile');
        if (!tile) return;
        var k = tile.getAttribute('data-pattern');
        if (k) ctSelectAllTiers(k);
      });
    }
    var hdr = document.getElementById('ct-col-header-row');
    if (hdr) {
      hdr.addEventListener('click', function(e) {
        var th = e.target.closest('th');
        if (!th) return;
        var key = th.getAttribute('data-sort-key');
        if (key) ctOnSort(key);
      });
    }
    return true;
  }

  function renderTests() {
    // MD-V2-MDJUMP-CONSUMER-S27-MARKER: Master Overview cell-click handoff. Read
    // window._mdJump once; if it targets this tab, arm the chip filter
    // for the named pattern, then clear it so it fires exactly once.
    (function(){
      var j = window._mdJump;
      if (j && j.tab === 'tests') {
        if (j.patternKey && j.tier && ctState.tierFilter &&
            ctState.tierFilter.hasOwnProperty(j.patternKey)) {
          ctState.tierFilter[j.patternKey] = [j.tier];
        }
        window._mdJump = null;
      }
    })();
    if (!ctBuildScaffold()) return;
    ctBuildHeaderRow();
    ctRenderRows();
    if (window.measureV2Ribbon) measureV2Ribbon();  /* MD-V2-WAVE1B-STICKY-CORRECTIVE-MARKER */
  }
  // MD-V2-TESTS-S27-MARKER: dispatch calls renderCapTests(); the pre-S27
  // module exported only renderTests, so renderCapTests was undefined - a
  // latent ReferenceError on the Tests tab. Export BOTH names so the
  // dispatch works whichever name it uses (and the S27 dashboard patcher
  // also corrects the dispatch line to renderTests for cleanliness).
  window.renderTests = renderTests;
  window.renderCapTests = renderTests;

})();
/* MD-V2-S50-SCRIPT5-EXPORTS: expose IIFE-private symbols that Script 5 renderTab + global-init needs */
window.displayMode = displayMode;
window.updateIndSecPills = updateIndSecPills;
window.precomputeSsemRatings = precomputeSsemRatings;
window.deriveMasterRatings = deriveMasterRatings;
window.renderSummary = renderSummary;
window.renderMM99 = renderMM99;
window.renderBP = renderBP;
window.renderPB = renderPB;
window.renderUTR = renderUTR;
window.renderVCP = renderVCP;
window.renderTech = renderTech;
window.renderCombos = renderCombos;
window.renderChanges = renderChanges;
window.renderPositions = renderPositions;
window.renderSSEM = renderSSEM;
window.renderVal = renderVal;
window.buildHeaderControls = buildHeaderControls;
window.renderPlaceholder = renderPlaceholder;
window.TAB_IDS = TAB_IDS;
window.TAB_LABELS = TAB_LABELS;
})();  /* close main IIFE */

/* MD-V2-TESTS-MARKER-END */

/* MD-V2-TESTS-MARKER-MODULE-END */



</script>
<style>
/* MD-V2-S47-TAB-HEALTHY-RETEST-MARKER-CSS-START */
/* Healthy Retest of MA — 4-group redesign (S56) */
#tab-setups_healthy_retest .group-captions { display: grid; grid-template-columns: repeat(4,1fr); gap: 10px; margin: 16px 0 14px 0; }
#tab-setups_healthy_retest .group-captions .gcap { background: #fbfaf5; border: 1px solid #e0dcc8; border-left: 3px solid #aaa; border-radius: 4px; padding: 10px 12px; font-size: 11px; line-height: 1.45; color: #555; }
#tab-setups_healthy_retest .group-captions .gcap b { display: block; margin-bottom: 4px; font-weight: 700; font-size: 11px; letter-spacing: 0.2px; }
#tab-setups_healthy_retest .group-captions .gcap-g1 { border-left-color: #b08a4e; }
#tab-setups_healthy_retest .group-captions .gcap-g1 b { color: #b08a4e; }
#tab-setups_healthy_retest .group-captions .gcap-g2 { border-left-color: #4a6a8a; }
#tab-setups_healthy_retest .group-captions .gcap-g2 b { color: #4a6a8a; }
#tab-setups_healthy_retest .group-captions .gcap-g3 { border-left-color: #3a7a5a; }
#tab-setups_healthy_retest .group-captions .gcap-g3 b { color: #3a7a5a; }
#tab-setups_healthy_retest .group-captions .gcap-g4 { border-left-color: #8a4a3a; }
#tab-setups_healthy_retest .group-captions .gcap-g4 b { color: #8a4a3a; }
#tab-setups_healthy_retest .s1-rating-tiles { display: grid; grid-template-columns: 1fr; gap: 8px; }
#tab-setups_healthy_retest .s1-rating-tiles .pi-tile-pullback { background: rgba(46,125,50,0.10); border: 1px solid rgba(46,125,50,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
#tab-setups_healthy_retest .s1-rating-tiles .pi-tile-pullback.active { background: rgba(46,125,50,0.22); border: 1.5px solid #2E7D32; }
#tab-setups_healthy_retest .s1-rating-tiles .pi-strip-pullback { background: #2E7D32; height: 4px; margin-top: 6px; border-radius: 2px; }
#tab-setups_healthy_retest .s1-rating-tiles .rt-breakdown { font-size: 9px; color: #888; margin-top: 4px; line-height: 1.35; }
#tab-setups_healthy_retest .pi-tier-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 7px; }
#tab-setups_healthy_retest .pi-tier-chip { font-size: 10px; padding: 2px 6px; border-radius: 4px; cursor: pointer; user-select: none; border: 0.5px solid; line-height: 1.4; white-space: nowrap; transition: background 0.12s, color 0.12s; }
#tab-setups_healthy_retest .pi-chip-pullback { background: #E1F5EE; color: #2E7D32; border-color: #9FE1CB; }
#tab-setups_healthy_retest .pi-chip-pullback.on { background: #2E7D32; color: #fff; border-color: #2E7D32; font-weight: 500; }
#tab-setups_healthy_retest .pi-tier-chip:hover { filter: brightness(0.96); }
#tab-setups_healthy_retest .s1-rating-tiles .rating-tile.active { box-shadow: inset 0 0 0 1.5px currentColor; }
#hr-main-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 11px; table-layout: fixed; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }
#hr-main-table thead { position: sticky; top: 0; z-index: 50; background: #fbfaf5; box-shadow: 0 2px 4px rgba(0,0,0,0.06); }
#hr-main-table thead th { background: #fbfaf5 !important; border-bottom: 1px solid #e0dcc8; padding: 7px 3px; text-align: center; font-weight: 600; font-size: 10px; color: #666; cursor: pointer; user-select: none; line-height: 1.25; vertical-align: middle; }
#hr-main-table thead th:hover { background: #f0ebd9 !important; }
#hr-main-table thead .group-header-row th { background: #f3efe2 !important; font-size: 9.5px; text-transform: none; font-weight: 700; letter-spacing: 0.2px; padding: 5px 3px; cursor: default; line-height: 1.25; }
#hr-main-table thead .group-header-row th:hover { background: #f3efe2 !important; }
#hr-main-table thead tr.group-header-row th { position: sticky; top: 0; }
#hr-main-table thead tr.sub-group-row th { position: sticky; top: 24px; font-size: 9px; text-transform: uppercase; letter-spacing: 0.3px; color: #888; padding: 3px; font-weight: 600; background: #f8f6ee !important; border-bottom: 1px solid #e0dcc8; }
#hr-main-table thead tr.col-header-row th { position: sticky; top: 44px; border-top: 1px solid #e0dcc8; }
#hr-main-table thead .gh-inputs { color: #555; }
#hr-main-table thead .gh-g1 { color: #b08a4e; }
#hr-main-table thead .gh-rating { color: #2E7D32; }
#hr-main-table thead .gh-g2 { color: #4a6a8a; }
#hr-main-table thead .gh-g3 { color: #3a7a5a; }
#hr-main-table thead .gh-g4 { color: #8a4a3a; }
#hr-main-table thead .gh-context { color: #888; }
#hr-main-table .hd { display: inline-flex; align-items: center; justify-content: center; gap: 3px; width: 100%; }
#hr-main-table .hd .lbl { white-space: normal; word-break: break-word; }
#hr-main-table .hd .sort-arrow { font-size: 9px; color: #2E7D32; flex: 0 0 auto; line-height: 1; }
#hr-main-table .hd .sort-placeholder { width: 9px; flex: 0 0 auto; }
#hr-main-table td { padding: 5px 4px; border-bottom: 1px solid #efece0; text-align: center; vertical-align: middle; height: 38px; box-sizing: border-box; font-variant-numeric: tabular-nums; }
#hr-main-table tr:hover { background: rgba(46,125,50,0.05); }
#hr-main-table td.grp-start-g1, #hr-main-table th.grp-start-g1 { border-left: 2px solid rgba(176,138,78,0.50); }
#hr-main-table td.grp-start-rating, #hr-main-table th.grp-start-rating { border-left: 2px solid rgba(46,125,50,0.50); }
#hr-main-table td.grp-start-g2, #hr-main-table th.grp-start-g2 { border-left: 2px solid rgba(74,106,138,0.50); }
#hr-main-table td.grp-start-g3, #hr-main-table th.grp-start-g3 { border-left: 2px solid rgba(58,122,90,0.50); }
#hr-main-table td.grp-start-g4, #hr-main-table th.grp-start-g4 { border-left: 2px solid rgba(138,74,58,0.50); }
#hr-main-table td.grp-start-context, #hr-main-table th.grp-start-context { border-left: 2px solid rgba(136,136,136,0.35); }
#hr-main-table td.s2-gate-pass { background: rgba(176,138,78,0.18); color: #7a5a1a; font-weight: 700; }
#hr-main-table td.s2-gate-fail { color: #bbb; }
#hr-main-table td.s2-test-pass { background: rgba(176,138,78,0.12); color: #7a5a1a; font-weight: 700; }
#hr-main-table td.s2-test-fail { color: #ccc; }
#hr-main-table .s2-pill { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 9px; font-weight: 700; line-height: 1.3; white-space: nowrap; }
#hr-main-table .s2-pill-prob { background: #b08a4e; color: #fff; }
#hr-main-table .s2-pill-pla  { background: rgba(176,138,78,0.35); color: #6a4a10; }
#hr-main-table .s2-pill-pos  { background: rgba(176,138,78,0.15); color: #8a6a2a; }
#hr-main-table .s2-pill-none { background: #ece9dd; color: #aaa; }
#hr-main-table td.pi-rating-cell { padding: 3px 4px; background: rgba(46,125,50,0.04); }
#hr-main-table .pi-pill { display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 9.5px; font-weight: 800; line-height: 1.3; white-space: nowrap; letter-spacing: 0.1px; }
#hr-main-table .pi-pill-tint-qualified { background: #1b5e20; color: #fff; }
#hr-main-table .pi-pill-tint-prob { background: #2E7D32; color: #fff; }
#hr-main-table .pi-pill-tint-pla  { background: rgba(46,125,50,0.30); color: #0a4a3a; }
#hr-main-table .pi-pill-tint-pos  { background: rgba(46,125,50,0.14); color: #3a6a5a; }
#hr-main-table .pi-pill-tint-none { background: #ece9dd; color: #999; }
#hr-main-table td.pi-score-cell { padding: 4px 3px; background: rgba(46,125,50,0.04); border-right: 1px solid rgba(46,125,50,0.18); }
#hr-main-table .pi-pip-row { display: inline-flex; align-items: center; gap: 2px; justify-content: center; }
#hr-main-table .pi-pip-row .pip { width: 6px; height: 6px; border-radius: 50%; background: #d8d4c4; display: inline-block; }
#hr-main-table .pi-pip-row .pip.on { background: #2E7D32; }
#hr-main-table .pi-pip-row .pi-score-num { font-size: 9.5px; color: #444; margin-left: 4px; font-weight: 700; }
#hr-main-table td.pi-pass { background: rgba(46,125,50,0.12); color: #2E7D32; font-weight: 700; }
#hr-main-table td.pi-fail { color: #999; }
#hr-main-table td.pb-info-cell { color: #4a6a8a; font-weight: 600; font-size: 11px; }
#hr-main-table td.pb-info-cell.pb-deep { color: #8a4a3a; }
#hr-main-table td.ma-pct-pass { font-weight: 700; }
#hr-main-table td.ma-pct-none { color: #ccc; }
#hr-main-table td.ma-name-cell { font-size: 10px; color: #888; font-weight: 600; }
#hr-main-table td.ma-name-cell.ma-name-hit { color: #3a7a5a; font-weight: 700; }
#hr-main-table td.ct-window-col { padding: 3px 4px; font-size: 10px; }
#hr-main-table td.ct-window-fired-recent { background: rgba(46,125,50,0.16); }
#hr-main-table td.ct-window-fired-recent .ct-window-label { color: #0a4a3a; font-weight: 700; }
#hr-main-table td.ct-window-fired-older { background: rgba(186,117,23,0.14); }
#hr-main-table td.ct-window-fired-older .ct-window-label { color: #7a4e0a; font-weight: 600; }
#hr-main-table td.ct-window-none { color: #bbb; }
#hr-main-table td.ct-window-building { color: #b59a5a; font-style: italic; font-size: 9px; }
#hr-main-table td.ct-window-na { color: #ccc; }
#hr-main-table td.name-cell { text-align: left; padding: 4px 4px 4px 8px; line-height: 1.15; }
#hr-main-table td.name-cell .co { font-weight: 700; font-size: 11px; color: #2a2a2a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#hr-main-table td.name-cell .tk { font-size: 9px; color: #999; font-weight: 500; margin-top: 1px; }
#hr-main-table td.name-cell .live-dot { color: #2e7d32; font-weight: 700; margin-right: 4px; display: inline-block; vertical-align: middle; line-height: 1; font-size: 10px; }
#hr-main-table td.taxon { text-align: left; font-size: 9px; line-height: 1.2; padding: 4px; }
#hr-main-table td.taxon .ind { color: #666; font-weight: 500; }
#hr-main-table td.taxon .sec { color: #999; }
#hr-main-table col.c-name { width: 124px; }
#hr-main-table col.c-taxon { width: 150px; }
#hr-main-table col.c-price { width: 50px; }
#hr-main-table col.c-pullback { width: 58px; }
#hr-main-table col.c-s2-rating { width: 72px; }
#hr-main-table col.c-s2-gate { width: 40px; }
#hr-main-table col.c-s2-test { width: 40px; }
#hr-main-table col.c-rating { width: 72px; }
#hr-main-table col.c-score { width: 56px; }
#hr-main-table col.c-test { width: 40px; }
#hr-main-table col.c-pb-info { width: 52px; }
#hr-main-table col.c-ma-pct { width: 52px; }
#hr-main-table col.c-ma-name { width: 42px; }
#hr-main-table col.c-window { width: 52px; }
#hr-main-table tr.tint-row td.name-cell, #hr-main-table tr.tint-row td.taxon { background: var(--tint-bg) !important; }
#hr-main-table tr.portfolio-band td:last-child { border-right: 4px solid var(--portfolio-color); }
#hr-main-table tr.portfolio-tint { background: var(--portfolio-bg); }
#hr-main-table tr.portfolio-tint:hover { background: var(--portfolio-bg-hover); }
/* MD-V2-S47-TAB-HEALTHY-RETEST-MARKER-CSS-END */

</style>
<script>


/* MD-V2-S47-TAB-HEALTHY-RETEST-MARKER-MODULE-START */
// =============================================================================
// HEALTHY RETEST OF MA — S56 4-GROUP REDESIGN
// MD-V2-S47-TAB-HEALTHY-RETEST-MARKER — idempotency marker
// G1: Stage 2 rating + 4 gates + 5 tests
// G2: 5D/10D declining + pullback info
// G3: 4 setup tests + MA% + MA name + candle
// G4: reclaim + confirmation
// =============================================================================

(function() {
  'use strict';

  var HR_KEY = 'healthy_retest';
  var HR_TIERS = ['None', 'Possible', 'Plausible', 'Probable', 'Qualified'];
  var HR_TIER_DISPLAY = ['Possible', 'Plausible', 'Probable', 'Qualified'];
  var HR_RATING_RANK = { 'Qualified':6, 'Probable':5, 'Plausible':3, 'Possible':2, 'None':1 };
  var HR_RATING_CLS  = { 'Qualified':'tint-qualified', 'Probable':'tint-prob', 'Plausible':'tint-pla', 'Possible':'tint-pos', 'None':'tint-none' };

  var S2_GATES = [
    { key: 'g1_P_above_200D',      label: '1. P > 200D MA (gate)',  tooltip: 'Price above the 200-day MA' },
    { key: 'g2_P_above_150D',      label: '2. P > 150D MA (gate)',  tooltip: 'Price above the 150-day MA' },
    { key: 'g3_150D_above_200D',   label: '3. 150D MA > 200D MA (gate)', tooltip: '150-day MA above 200-day MA' },
    { key: 'g4_within_25pct_52WH', label: '4. Within 25% of 52w high (gate)', tooltip: 'Price within 25% of 52-week high' }
  ];
  var S2_TESTS = [
    { key: 'T5_50D_above_150D',            label: '5. 50D MA > 150D MA', tooltip: '50-day MA above 150-day MA' },
    { key: 'T6_50D_above_200D',            label: '6. 50D MA > 200D MA', tooltip: '50-day MA above 200-day MA' },
    { key: 'T7_industry_RS_pct_ge70',      label: '7. Industry pct. ≥70', tooltip: 'Industry RS percentile >= 70' },
    { key: 'T8_sector_RS_pct_ge70',        label: '8. Sector pct. in industry ≥70', tooltip: 'Sector RS percentile >= 70 within industry' },
    { key: 'T9_stock_RS_vs_industry_ge70', label: '9. Stock pct. vs industry ≥70', tooltip: 'Stock RS vs industry percentile >= 70' }
  ];
  var HR_TESTS_G2 = [
    { key: 'g2_b3_5d_declining',  label: '10. 5D MA declining', tooltip: '5-day MA declining day-over-day' },
    { key: 'g2_b4_10d_declining', label: '11. 10D MA declining', tooltip: '10-day MA declining day-over-day' }
  ];
  var HR_TESTS_G3 = [
    { key: 'g3_c1_volume_contracting',    label: '12. Vol contracting', tooltip: '10-day average volume below the 50-day' },
    { key: 'g3_c2_up_vol_gt_down_vol',    label: '13. Up-vol > down-vol', tooltip: 'Up-day volume exceeds down-day volume' },
    { key: 'g3_c3_few_distribution_days', label: '14. Few dist days', tooltip: '3 or fewer distribution days in last 25 sessions' },
    { key: 'g3_c4_volatility_reducing',   label: '15. Vol reducing',  tooltip: '10-day ATR below 20-day ATR' }
  ];
  var HR_TESTS_G4 = [
    { key: 'g4_d1_reclaimed_ma',              label: '17. Reclaimed MA', tooltip: 'Price crossed back above tested MA in last 10 days' },
    { key: 'g4_d2_confirmation_close_ge2pct', label: '18. Confirm 2%+ up', tooltip: "Today's close >= 2% above yesterday's" }
  ];

  var hrState = {
    mode: { inputs: 'pct', tests: 'tick' },
    scope: 'all', tierFilter: [], tint: 'none', port: 'off',
    sort: { col: 'company', dir: 'asc' }
  };

  function hrPricesLookup() {
    if (window._ctPricesByTicker) return window._ctPricesByTicker;
    var out = {};
    var arr = (window.MASTER_DATA && MASTER_DATA.prices) || [];
    for (var i = 0; i < arr.length; i++) if (arr[i] && arr[i].ticker) out[arr[i].ticker] = arr[i];
    window._ctPricesByTicker = out;
    return out;
  }
  function hrLiveTickers() {
    var out = {};
    var inv = (window.MASTER_DATA && MASTER_DATA.positions && MASTER_DATA.positions.investments) || [];
    for (var i = 0; i < inv.length; i++) if (inv[i].ticker) out[inv[i].ticker] = true;
    return out;
  }
  function hrLiveSectors() {
    var out = {}, prices = hrPricesLookup(), tickers = hrLiveTickers();
    for (var t in tickers) { var p = prices[t]; if (p && p.sector) out[p.sector] = true; }
    return out;
  }
  function hrLiveIndustries() {
    var out = {}, prices = hrPricesLookup(), tickers = hrLiveTickers();
    for (var t in tickers) { var p = prices[t]; if (p && p.industry) out[p.industry] = true; }
    return out;
  }
  function hrGetRec(row) {
    var dk = row.md_v2 && row.md_v2.tests;
    return (dk && dk[HR_KEY]) || null;
  }
  function hrEvalTest(row, testKey) {
    var rec = hrGetRec(row);
    if (!rec || !rec.tests) return false;
    return !!rec.tests[testKey];
  }
  function hrRowRating(row) {
    var rec = hrGetRec(row);
    return rec ? (rec.rating || 'None') : 'None';
  }
  function hrS2Rating(row) {
    var s2 = row.md_v2 && row.md_v2.stage_2;
    return (s2 && s2.rating) || 'None';
  }
  function hrS2GateVal(row, gateKey) {
    var s2 = row.md_v2 && row.md_v2.stage_2;
    if (!s2) return false;
    return !!(s2.gates && s2.gates[gateKey]);
  }
  function hrS2TestVal(row, testKey) {
    var s2 = row.md_v2 && row.md_v2.stage_2;
    if (!s2) return false;
    return !!(s2.tests && s2.tests[testKey]);
  }
  function hrGetMaInfo(row) {
    var rec = hrGetRec(row);
    var maLabel = rec && rec.info_ma_retested;
    if (!maLabel) return { pct: null, name: null };
    var maNum = maLabel.replace('D', '').replace('d', '');
    var maVal = row['ma_' + maNum];
    if (!maVal || !row.price) return { pct: null, name: maLabel };
    return { pct: (row.price - maVal) / maVal * 100, name: maLabel };
  }
  function hrGetRows() {
    var raw = (window.MASTER_DATA && MASTER_DATA.filters) || [];
    var prices = hrPricesLookup();
    var live = hrLiveTickers(), liveS = hrLiveSectors(), liveI = hrLiveIndustries();
    var rows = [];
    for (var i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || !s.md_v2 || !s.md_v2.tests) continue;
      var rec = s.md_v2.tests[HR_KEY];
      if (!rec) continue;
      var p = prices[s.ticker] || {};
      var mas = p.mas || {};
      rows.push({
        ticker: s.ticker, company: p.company_name || s.ticker,
        sector: p.sector || '', industry: p.industry || '',
        price: p.price, recent_pullback: p.recent_pullback_pct,
        ma_50: mas['50D'], ma_100: mas['100D'],
        ma_150: mas['150D'], ma_200: mas['200D'],
        md_v2: s.md_v2,
        is_live: !!live[s.ticker],
        sector_in_portfolio: !!liveS[p.sector],
        industry_in_portfolio: !!liveI[p.industry]
      });
    }
    return rows;
  }

  function hrTierCounts(rows) {
    var c = {};
    for (var i = 0; i < HR_TIERS.length; i++) c[HR_TIERS[i]] = 0;
    for (var j = 0; j < rows.length; j++) { var r = hrRowRating(rows[j]); if (c[r] != null) c[r]++; }
    return c;
  }
  function hrPassHistogram(rows) {
    var h = []; for (var k = 0; k <= 13; k++) h[k] = 0;
    for (var i = 0; i < rows.length; i++) { var rec = hrGetRec(rows[i]); var cnt = rec ? (rec.count || 0) : 0; if (cnt >= 0 && cnt <= 13) h[cnt]++; }
    return h;
  }

  function hrFmtNum(n) {
    if (n == null || isNaN(n)) return '-';
    var abs = Math.abs(n), dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2);
    if (Math.abs(n - Math.round(n)) < 1e-9) dp = 0;
    var f = abs.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp });
    return n < 0 ? '(' + f + ')' : f;
  }
  function hrFmtPct(p) {
    if (p == null || isNaN(p)) return '-';
    var r = Math.round(p), abs = Math.abs(r);
    return r < 0 ? '(' + abs + ')%' : r + '%';
  }
  function hrColourForIntensity(i) {
    if (i >= 0.6) return '#2E7D32'; if (i >= 0.25) return '#4CAF50'; if (i >= 0.05) return '#81C784';
    if (i <= -0.6) return '#A32D2D'; if (i <= -0.25) return '#E24B4A'; if (i <= -0.05) return '#F09595';
    return '#888';
  }
  function hrHashColor(label, alpha) {
    if (!label) return null;
    var h = 0;
    for (var i = 0; i < label.length; i++) h = (h * 31 + label.charCodeAt(i)) & 0xffff;
    return 'hsla(' + (h % 360) + ', 35%, 55%, ' + alpha + ')';
  }
  function hrPortfolioInfo(row) {
    if (row.is_live) return { color:'#1b5e20', bg:'rgba(27,94,32,0.10)', bgHover:'rgba(27,94,32,0.14)' };
    if (row.sector_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.05)', bgHover:'rgba(27,94,32,0.08)' };
    if (row.industry_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.025)', bgHover:'rgba(27,94,32,0.05)' };
    return null;
  }

  function hrInputCell(row, key, extraCls) {
    extraCls = extraCls || '';
    if (key === 'price') return '<td class="num ' + extraCls + '">' + hrFmtNum(row.price) + '</td>';
    if (key === 'recent_pullback') {
      var v = row.recent_pullback;
      if (v == null || isNaN(v)) return '<td class="num ' + extraCls + '">-</td>';
      var pctVal = v * 100;
      var intensity = Math.max(-1, Math.min(1, (pctVal - 5) / 20));
      return '<td class="num ' + extraCls + '" style="color:' + hrColourForIntensity(-intensity) + '">' + Math.round(pctVal) + '%</td>';
    }
    return '<td class="num ' + extraCls + '">-</td>';
  }
  function hrS2RatingCell(row, cls) {
    var rating = hrS2Rating(row);
    var pc = rating === 'Probable' ? 's2-pill-prob' : rating === 'Plausible' ? 's2-pill-pla' : rating === 'Possible' ? 's2-pill-pos' : 's2-pill-none';
    return '<td class="' + (cls||'') + '"><span class="s2-pill ' + pc + '">' + rating + '</span></td>';
  }
  function hrS2GateCell(row, gateKey, cls) {
    if (hrS2GateVal(row, gateKey)) return '<td class="s2-gate-pass ' + (cls||'') + '"><span class="tick">✓</span></td>';
    return '<td class="s2-gate-fail ' + (cls||'') + '">.</td>';
  }
  function hrS2TestCell(row, testKey, cls) {
    if (hrS2TestVal(row, testKey)) return '<td class="s2-test-pass ' + (cls||'') + '"><span class="tick">✓</span></td>';
    return '<td class="s2-test-fail ' + (cls||'') + '">.</td>';
  }
  function hrTestCell(row, testKey, cls) {
    var pass = hrEvalTest(row, testKey);
    if (pass) return '<td class="pi-pass ' + (cls||'') + '"><span class="tick">✓</span></td>';
    return '<td class="pi-fail ' + (cls||'') + '">.</td>';
  }
  function hrRatingCell(row, cls) {
    var rating = hrRowRating(row);
    var rcls = HR_RATING_CLS[rating] || 'tint-none';
    return '<td class="' + (cls||'') + ' pi-rating-cell ' + rcls + '"><span class="pi-pill pi-pill-' + rcls + '">' + rating + '</span></td>';
  }
  function hrScoreCell(row, cls) {
    var rec = hrGetRec(row);
    var cnt = rec ? (rec.count || 0) : 0, tot = rec ? (rec.total || 0) : 0;
    var s = '';
    for (var i = 0; i < tot; i++) s += '<span class="pip ' + (i < cnt ? 'on' : '') + '"></span>';
    return '<td class="' + (cls||'') + ' pi-score-cell"><div class="pi-pip-row">' + s + '<span class="pi-score-num">' + cnt + '/' + tot + '</span></div></td>';
  }
  function hrPullbackInfoCell(row, cls) {
    var v = row.recent_pullback;
    if (v == null || isNaN(v)) return '<td class="pb-info-cell ' + (cls||'') + '">-</td>';
    var pctVal = v * 100;
    return '<td class="pb-info-cell' + (pctVal < -15 ? ' pb-deep' : '') + ' ' + (cls||'') + '">' + Math.round(pctVal) + '%</td>';
  }
  function hrMaPctCell(row, cls) {
    var info = hrGetMaInfo(row);
    if (info.pct == null) return '<td class="ma-pct-none ' + (cls||'') + '">-</td>';
    var pct = info.pct;
    var sign = pct >= 0 ? '+' : '';
    var col = hrColourForIntensity(Math.max(-1, Math.min(1, pct / 6)));
    return '<td class="ma-pct-pass ' + (cls||'') + '" style="color:' + col + '">' + sign + pct.toFixed(1) + '%</td>';
  }
  function hrMaNameCell(row, cls) {
    var info = hrGetMaInfo(row);
    if (!info.name) return '<td class="ma-name-cell ' + (cls||'') + '">-</td>';
    return '<td class="ma-name-cell ma-name-hit ' + (cls||'') + '">' + info.name + '</td>';
  }
  function hrWindowCell(row, windowKey, cls) {
    var rec = hrGetRec(row);
    var extra = cls || '';
    if (!rec) return '<td class="' + extra + ' ct-window-na">-</td>';
    var depth = rec.history_depth || 0, windowDays = (windowKey === 'l5d') ? 5 : 20;
    if (depth < windowDays) return '<td class="' + extra + ' ct-window-building" title="' + depth + ' of ' + windowDays + ' days">building</td>';
    var fired = (windowKey === 'l5d') ? !!rec.fired_l5d : !!rec.fired_l20d;
    if (!fired) return '<td class="' + extra + ' ct-window-none">-</td>';
    var ds = rec.days_since_fired;
    var label = ds === 0 ? 'today' : ds === 1 ? '1d ago' : (ds != null ? ds + 'd ago' : 'fired');
    var shadeCls = (ds != null && ds <= 5) ? 'ct-window-fired-recent' : 'ct-window-fired-older';
    return '<td class="' + extra + ' ' + shadeCls + '" title="' + label + '"><span class="ct-window-label">' + label + '</span></td>';
  }

  var HR_COL_MODEL = null;
  var S2_RATING_RANK = { 'Probable':4, 'Plausible':3, 'Possible':2, 'None':1 };

  function hrBuildColModel() {
    if (HR_COL_MODEL) return HR_COL_MODEL;
    var cols = [
      { id:'name',     sortKey:'company',        kind:'name' },
      { id:'taxon',    sortKey:'sector',          kind:'taxon' },
      { id:'price',    sortKey:'price',           kind:'price' },
      { id:'pullback', sortKey:'recent_pullback', kind:'pullback' }
    ];
    cols.push({ id:'s2_rating', sortKey:'s2__rating', kind:'s2rating' });
    for (var gi = 0; gi < S2_GATES.length; gi++)
      cols.push({ id:'s2g'+gi, sortKey:'s2g__'+S2_GATES[gi].key, kind:'s2gate', gateKey:S2_GATES[gi].key, label:S2_GATES[gi].label, tooltip:S2_GATES[gi].tooltip });
    for (var ti = 0; ti < S2_TESTS.length; ti++)
      cols.push({ id:'s2t'+ti, sortKey:'s2t__'+S2_TESTS[ti].key, kind:'s2test', testKey:S2_TESTS[ti].key, label:S2_TESTS[ti].label, tooltip:S2_TESTS[ti].tooltip });
    cols.push({ id:'hr_rating', sortKey:'hr__rating', kind:'rating' });
    cols.push({ id:'hr_score',  sortKey:'hr__score',  kind:'score' });
    cols.push({ id:'hr_g2_0', sortKey:'hr__'+HR_TESTS_G2[0].key, kind:'hrtest', testKey:HR_TESTS_G2[0].key, label:HR_TESTS_G2[0].label, tooltip:HR_TESTS_G2[0].tooltip, grpStart:'g2' });
    cols.push({ id:'hr_g2_1', sortKey:'hr__'+HR_TESTS_G2[1].key, kind:'hrtest', testKey:HR_TESTS_G2[1].key, label:HR_TESTS_G2[1].label, tooltip:HR_TESTS_G2[1].tooltip });
    cols.push({ id:'g2_pb',   sortKey:'g2__pb_info', kind:'pb_info' });
    for (var g3i = 0; g3i < HR_TESTS_G3.length; g3i++)
      cols.push({ id:'hr_g3_'+g3i, sortKey:'hr__'+HR_TESTS_G3[g3i].key, kind:'hrtest', testKey:HR_TESTS_G3[g3i].key, label:HR_TESTS_G3[g3i].label, tooltip:HR_TESTS_G3[g3i].tooltip, grpStart: g3i===0?'g3':null });
    cols.push({ id:'g3_ma_pct',  sortKey:'g3__ma_pct',  kind:'ma_pct' });
    cols.push({ id:'g3_ma_name', sortKey:'g3__ma_name', kind:'ma_name' });
    cols.push({ id:'hr_g3_c6', sortKey:'hr__g3_c6_buying_through_l10d', kind:'hrtest', testKey:'g3_c6_buying_through_l10d', label:'16. Buying through 10 days', tooltip:'At least half of last 10 days closed in upper 40% of daily range' });
    cols.push({ id:'hr_g4_0', sortKey:'hr__'+HR_TESTS_G4[0].key, kind:'hrtest', testKey:HR_TESTS_G4[0].key, label:HR_TESTS_G4[0].label, tooltip:HR_TESTS_G4[0].tooltip, grpStart:'g4' });
    cols.push({ id:'hr_g4_1', sortKey:'hr__'+HR_TESTS_G4[1].key, kind:'hrtest', testKey:HR_TESTS_G4[1].key, label:HR_TESTS_G4[1].label, tooltip:HR_TESTS_G4[1].tooltip });
    cols.push({ id:'hr_l5d',  sortKey:'hr__l5d',  kind:'window', windowKey:'l5d',  grpStart:'context' });
    cols.push({ id:'hr_l20d', sortKey:'hr__l20d', kind:'window', windowKey:'l20d' });
    HR_COL_MODEL = cols;
    return cols;
  }

  function hrGetSortVal(row, key) {
    if (key === 'company') return row.company || '';
    if (key === 'sector')  return row.sector  || '';
    if (key === 'price')   return row.price   || 0;
    if (key === 'recent_pullback') return row.recent_pullback == null ? -Infinity : row.recent_pullback;
    if (key === 's2__rating') return S2_RATING_RANK[hrS2Rating(row)] || 0;
    if (key.indexOf('s2g__') === 0) return hrS2GateVal(row, key.substring(5)) ? 1 : 0;
    if (key.indexOf('s2t__') === 0) return hrS2TestVal(row, key.substring(5)) ? 1 : 0;
    if (key === 'hr__rating') return HR_RATING_RANK[hrRowRating(row)] || 0;
    if (key === 'hr__score') { var rec = hrGetRec(row); return rec ? (rec.count || 0) : 0; }
    if (key === 'g2__pb_info') return row.recent_pullback == null ? -Infinity : row.recent_pullback;
    if (key === 'g3__ma_pct') { var inf = hrGetMaInfo(row); return inf.pct == null ? -Infinity : inf.pct; }
    if (key === 'g3__ma_name') { var inf2 = hrGetMaInfo(row); return inf2.name || 'ZZZ'; }
    if (key === 'hr__l5d' || key === 'hr__l20d') {
      var rec2 = hrGetRec(row); if (!rec2) return -1;
      var sub = key.split('__')[1], wd = sub === 'l5d' ? 5 : 20;
      if ((rec2.history_depth || 0) < wd) return -2;
      var fi = sub === 'l5d' ? rec2.fired_l5d : rec2.fired_l20d;
      if (!fi) return -1;
      var ds = rec2.days_since_fired; return ds == null ? 0 : (1000 - ds);
    }
    if (key.indexOf('hr__') === 0) return hrEvalTest(row, key.substring(4)) ? 1 : 0;
    return 0;
  }
  function hrOnSort(key) {
    if (hrState.sort.col === key) hrState.sort.dir = hrState.sort.dir === 'desc' ? 'asc' : 'desc';
    else hrState.sort = { col: key, dir: (key === 'company' || key === 'sector') ? 'asc' : 'desc' };
    hrBuildHeaderRow();
    hrRenderRows();
  }

  function hrBuildHeaderRow() {
    var tr = document.getElementById('hr-col-header-row');
    if (!tr) return;
    var cols = hrBuildColModel();
    var h = '';
    for (var i = 0; i < cols.length; i++) {
      var c = cols[i];
      var isSort = hrState.sort.col === c.sortKey;
      var arrow = isSort ? '<span class="sort-arrow">' + (hrState.sort.dir === 'desc' ? '▼' : '▲') + '</span>' : '<span class="sort-placeholder"></span>';
      var label, title, cls = '';
      if (c.kind === 'name')      { label = 'Company · Ticker'; title = label; }
      else if (c.kind === 'taxon')   { label = 'Industry · Sector'; title = label; }
      else if (c.kind === 'price')   { label = 'Price'; title = 'Last price'; }
      else if (c.kind === 'pullback'){ label = 'Pullback'; title = 'Pullback from recent swing high (%)'; }
      else if (c.kind === 's2rating'){ label = 'S2 Rating'; title = 'Stage 2 uptrend rating'; cls = 'grp-start-g1'; }
      else if (c.kind === 's2gate')  { label = c.label; title = c.tooltip; }
      else if (c.kind === 's2test')  { label = c.label; title = c.tooltip; }
      else if (c.kind === 'rating')  { label = 'HR Rating'; title = 'Healthy Retest rating'; cls = 'grp-start-rating'; }
      else if (c.kind === 'score')   { label = 'Score'; title = 'Pass count / 13'; }
      else if (c.kind === 'hrtest') {
        label = c.label; title = c.tooltip;
        if (c.grpStart === 'g2') cls = 'grp-start-g2';
        else if (c.grpStart === 'g3') cls = 'grp-start-g3';
        else if (c.grpStart === 'g4') cls = 'grp-start-g4';
      }
      else if (c.kind === 'pb_info') { label = 'Pullback'; title = 'Pullback depth for context'; }
      else if (c.kind === 'ma_pct')  { label = 'Testing MA'; title = '% distance from price to the tested MA'; }
      else if (c.kind === 'ma_name') { label = 'Which MA'; title = 'Which MA is being tested (50D/100D/150D/200D)'; }
      else if (c.kind === 'window') {
        label = c.windowKey === 'l5d' ? 'Fired 5d' : 'Fired 20d'; title = label;
        cls = (c.grpStart === 'context' ? 'grp-start-context ' : '') + 'ct-window-col';
      }
      else { label = '?'; title = ''; }
      h += '<th class="' + cls + '" data-sort-key="' + c.sortKey + '" title="' + title.replace(/"/g, '&quot;') + '"><span class="hd"><span class="lbl">' + label + '</span>' + arrow + '</span></th>';
    }
    tr.innerHTML = h;
  }

  function hrPatternTile(scopeRows) {
    var tiles = document.getElementById('hr-pattern-tiles');
    if (!tiles) return;
    var tc = hrTierCounts(scopeRows), total = scopeRows.length;
    var cnt = total - (tc['None'] || 0), pct = total > 0 ? Math.round(cnt / total * 100) : 0;
    var sel = hrState.tierFilter, anySel = sel.length > 0;
    var headline = cnt, headSub = 'of ' + total.toLocaleString('en-GB') + ' · ' + pct + '%';
    if (anySel) {
      var ft = 0; for (var z = 0; z < sel.length; z++) ft += (tc[sel[z]] || 0);
      headline = ft; headSub = sel.join(' + ') + ' · filtered';
    }
    var hist = hrPassHistogram(scopeRows), breakdown = '';
    for (var k = 1; k <= 13; k++) { if (k > 1) breakdown += ' · '; breakdown += k + '/13: ' + (hist[k]||0).toLocaleString('en-GB'); }
    var chips = '';
    for (var ci = 0; ci < HR_TIER_DISPLAY.length; ci++) {
      var tier = HR_TIER_DISPLAY[ci], on = sel.indexOf(tier) > -1, tcc = tc[tier] || 0;
      chips += '<span class="pi-tier-chip pi-chip-pullback' + (on ? ' on' : '') + '" data-tier="' + tier + '">' + tier + ' ' + tcc.toLocaleString('en-GB') + (on ? ' ✓' : '') + '</span>';
    }
    tiles.innerHTML = '<div class="rating-tile pi-tile-pullback' + (anySel ? ' active' : '') + '" title="Healthy Retest of Upwards MA">' +
      '<div class="rt-label">Healthy Retest</div><div class="rt-count">' + headline.toLocaleString('en-GB') + '</div>' +
      '<div class="rt-sub">' + headSub + '</div><div class="rt-breakdown">' + breakdown + '</div>' +
      '<div class="pi-tier-chips">' + chips + '</div><div class="rt-strip pi-strip-pullback"></div></div>';
  }

  function hrUpdateScopeCounts(rows) {
    function set(id, n) { var el = document.getElementById(id); if (el) el.textContent = '(' + n + ')'; }
    set('hr-cnt-all', rows.length);
    set('hr-cnt-live',     rows.filter(function(r){ return r.is_live; }).length);
    set('hr-cnt-sector',   rows.filter(function(r){ return r.sector_in_portfolio; }).length);
    set('hr-cnt-industry', rows.filter(function(r){ return r.industry_in_portfolio; }).length);
  }
  function hrApplyScope(all) {
    var rows = all.slice();
    if (hrState.scope === 'live')     rows = rows.filter(function(r){ return r.is_live; });
    else if (hrState.scope === 'sector')   rows = rows.filter(function(r){ return r.sector_in_portfolio; });
    else if (hrState.scope === 'industry') rows = rows.filter(function(r){ return r.industry_in_portfolio; });
    return rows;
  }
  function hrApplyTierFilter(rows) {
    var sel = hrState.tierFilter; if (sel.length === 0) return rows;
    return rows.filter(function(r){ return sel.indexOf(hrRowRating(r)) > -1; });
  }

  function hrRenderRows() {
    var tbody = document.getElementById('hr-tbody'); if (!tbody) return;
    var all = hrGetRows(), scopeRows = hrApplyScope(all);
    hrUpdateScopeCounts(all); hrPatternTile(scopeRows);
    var rows = hrApplyTierFilter(scopeRows);
    rows.sort(function(a,b){
      var va = hrGetSortVal(a, hrState.sort.col), vb = hrGetSortVal(b, hrState.sort.col);
      var cmp = (typeof va === 'string') ? va.localeCompare(vb) : ((va||0)-(vb||0));
      if (cmp === 0) cmp = a.ticker.localeCompare(b.ticker);
      return hrState.sort.dir === 'desc' ? -cmp : cmp;
    });
    var html = '';
    for (var i = 0; i < rows.length; i++) {
      var s = rows[i], styles = [], cls = [];
      if (hrState.tint === 'industry') { styles.push('--tint-bg: ' + hrHashColor(s.industry, 0.16)); cls.push('tint-row'); }
      else if (hrState.tint === 'sector') { styles.push('--tint-bg: ' + hrHashColor(s.sector, 0.16)); cls.push('tint-row'); }
      if (hrState.port === 'on') {
        var pinf = hrPortfolioInfo(s);
        if (pinf) { styles.push('--portfolio-color:'+pinf.color,'--portfolio-bg:'+pinf.bg,'--portfolio-bg-hover:'+pinf.bgHover); cls.push('portfolio-band','portfolio-tint'); }
      }
      var sa = styles.length ? ' style="' + styles.join(';') + '"' : '';
      var ca = cls.length ? ' class="' + cls.join(' ') + '"' : '';
      var liveDot = s.is_live ? '<span class="live-dot">●</span>' : '';
      html += '<tr' + ca + sa + '>';
      // Inputs (4)
      html += '<td class="name-cell"><div class="co">' + liveDot + (s.company||s.ticker) + '</div><div class="tk">' + s.ticker + '</div></td>';
      html += '<td class="taxon"><div class="ind">' + (s.industry||'') + '</div><div class="sec">' + (s.sector||'') + '</div></td>';
      html += hrInputCell(s, 'price');
      html += hrInputCell(s, 'recent_pullback');
      // G1: S2 rating + 4 gates + 5 tests (10)
      html += hrS2RatingCell(s, 'grp-start-g1');
      for (var gi2 = 0; gi2 < S2_GATES.length; gi2++) html += hrS2GateCell(s, S2_GATES[gi2].key);
      for (var ti2 = 0; ti2 < S2_TESTS.length; ti2++) html += hrS2TestCell(s, S2_TESTS[ti2].key);
      // Rating + Score (2)
      html += hrRatingCell(s, 'grp-start-rating');
      html += hrScoreCell(s, '');
      // G2: 5D, 10D, pullback info (3)
      html += hrTestCell(s, HR_TESTS_G2[0].key, 'grp-start-g2');
      html += hrTestCell(s, HR_TESTS_G2[1].key, '');
      html += hrPullbackInfoCell(s, '');
      // G3: 4 tests + MA% + MA name + candle (7)
      html += hrTestCell(s, HR_TESTS_G3[0].key, 'grp-start-g3');
      for (var g3j = 1; g3j < HR_TESTS_G3.length; g3j++) html += hrTestCell(s, HR_TESTS_G3[g3j].key, '');
      html += hrMaPctCell(s, '');
      html += hrMaNameCell(s, '');
      html += hrTestCell(s, 'g3_c6_buying_through_l10d', '');
      // G4: reclaim + confirm (2)
      html += hrTestCell(s, HR_TESTS_G4[0].key, 'grp-start-g4');
      html += hrTestCell(s, HR_TESTS_G4[1].key, '');
      // Context (2)
      html += hrWindowCell(s, 'l5d', 'ct-window-col grp-start-context');
      html += hrWindowCell(s, 'l20d', 'ct-window-col');
      html += '</tr>';
    }
    tbody.innerHTML = html;
  }

  window.hrSetMode = function(kind, val) {
    hrState.mode[kind] = val;
    document.querySelectorAll('button[data-hr-grp="'+kind+'"]').forEach(function(b){ b.classList.toggle('active', b.getAttribute('data-hr-val')===val); });
    hrRenderRows();
  };
  window.hrSetScope = function(s) {
    hrState.scope = s;
    document.querySelectorAll('button[data-hr-scope]').forEach(function(b){ b.classList.toggle('active', b.getAttribute('data-hr-scope')===s); });
    hrRenderRows();
  };
  window.hrSetTint = function(t) {
    hrState.tint = t;
    document.querySelectorAll('button[data-hr-tint]').forEach(function(b){ b.classList.toggle('active', b.getAttribute('data-hr-tint')===t); });
    hrRenderRows();
  };
  window.hrSetPort = function(p) {
    hrState.port = p;
    document.querySelectorAll('button[data-hr-port]').forEach(function(b){ b.classList.toggle('active', b.getAttribute('data-hr-port')===p); });
    hrRenderRows();
  };
  window.hrToggleTier = function(tier) {
    var sel = hrState.tierFilter, idx = sel.indexOf(tier);
    if (idx > -1) sel.splice(idx, 1); else sel.push(tier);
    hrRenderRows();
  };
  window.hrSelectAllTiers = function() {
    var sel = hrState.tierFilter;
    hrState.tierFilter = (sel.length === 1 && sel[0] === 'Probable') ? [] : ['Probable'];
    hrRenderRows();
  };
  window.hrOnSort = hrOnSort;

  function hrBuildScaffold() {
    var host = document.getElementById('tab-setups_healthy_retest');
    if (!host) return false;
    if (host.querySelector('#hr-main-table')) return true;

    // colgroup: 4 inputs + 10 G1 + 2 rating + 3 G2 + 7 G3 + 2 G4 + 2 context = 30
    var cg = '<col class="c-name"><col class="c-taxon"><col class="c-price"><col class="c-pullback">' +
             '<col class="c-s2-rating"><col class="c-s2-gate"><col class="c-s2-gate"><col class="c-s2-gate"><col class="c-s2-gate">' +
             '<col class="c-s2-test"><col class="c-s2-test"><col class="c-s2-test"><col class="c-s2-test"><col class="c-s2-test">' +
             '<col class="c-rating"><col class="c-score">' +
             '<col class="c-test"><col class="c-test"><col class="c-pb-info">' +
             '<col class="c-test"><col class="c-test"><col class="c-test"><col class="c-test">' +
             '<col class="c-ma-pct"><col class="c-ma-name"><col class="c-test">' +
             '<col class="c-test"><col class="c-test">' +
             '<col class="c-window"><col class="c-window">';

    var gHdr = '<th class="gh-inputs" colspan="4">Inputs</th>' +
               '<th class="gh-g1 grp-start-g1" colspan="10">Group 1 — Upwards long-term trend?</th>' +
               '<th class="gh-rating grp-start-rating" colspan="2">Rating</th>' +
               '<th class="gh-g2 grp-start-g2" colspan="3">Group 2 — Pulling back mid-term trend?</th>' +
               '<th class="gh-g3 grp-start-g3" colspan="7">Group 3 — Healthy retest of rising MA?</th>' +
               '<th class="gh-g4 grp-start-g4" colspan="2">Group 4 — Successful test?</th>' +
               '<th class="gh-context grp-start-context" colspan="2">Context</th>';

    var subGrp = '<th class="sg-spacer" colspan="4"></th>' +
                 '<th class="sub-g grp-start-g1" colspan="1">Rating</th>' +
                 '<th class="sub-g" colspan="4">Gates</th>' +
                 '<th class="sub-g" colspan="5">Tests</th>' +
                 '<th class="sub-g grp-start-rating" colspan="2">Rating</th>' +
                 '<th class="sub-g grp-start-g2" colspan="2">Trend</th>' +
                 '<th class="sub-g" colspan="1">Info</th>' +
                 '<th class="sub-g grp-start-g3" colspan="4">Setup</th>' +
                 '<th class="sub-g" colspan="2">MA test</th>' +
                 '<th class="sub-g" colspan="1">Candle</th>' +
                 '<th class="sub-g grp-start-g4" colspan="2">Trigger</th>' +
                 '<th class="sub-g grp-start-context" colspan="2">Context</th>';

    var captionHtml =
      '<div class="gcap gcap-g1"><b>Group 1 — Upwards long-term trend (Stage)</b>' +
        '<span class="db">Is this stock in a confirmed Stage 2 uptrend? Four hard gates (price above both long MAs, 150D above 200D, within 25% of 52-week high) plus five tests deepening conviction: MA stack and relative strength vs industry, sector, and the broader market. The S2 rating shown is the existing Stage 2 tab rating for this stock.</span>' +
      '</div>' +
      '<div class="gcap gcap-g2"><b>Group 2 — Pulling back mid-term trend (Indicator)</b>' +
        '<span class="db">The short-term trend must be rolling over — a genuine pullback within the longer uptrend. Both the 5-day and 10-day MAs must be declining day-over-day. Pullback depth is shown for context. Both tests must pass for any Healthy Retest rating to fire.</span>' +
      '</div>' +
      '<div class="gcap gcap-g3"><b>Group 3 — Healthy retest of rising MA (Setup)</b>' +
        '<span class="db">Quality of the pullback. Volume should be drying up (not panic selling), up-day volume should dominate, distribution days should be few, and volatility should be contracting. The MA test column shows the % distance to whichever of the 50/100/150/200-day MAs price is nearest to. Daily close in upper candle checks that at least half the last 10 days closed in the upper 40% of their high-low range.</span>' +
      '</div>' +
      '<div class="gcap gcap-g4"><b>Group 4 — Successful test (Trigger)</b>' +
        '<span class="db">The deployment trigger. Price has pulled back to a rising MA and is now reclaiming it. Two tests: price must have crossed back above the tested MA in the last 10 trading days, and today\'s close must be at least 2% above yesterday\'s confirming follow-through buying.</span>' +
      '</div>';

    var html = '' +
      '<div class="s1-intro">Healthy Retest of Upwards MA — the 13-criterion test for a Core Minervini trade. A stock must be in a confirmed Stage 2 uptrend, pulling back towards an upwards-moving MA on healthy volume and volatility characteristics, then reclaiming the MA with a confirming up-day. Rating tiers: Qualified (all 13), Probable (12 of 13, missing only the confirmation), Plausible (gate + G2 indicators + 3+ of 6 G3 setup), Possible (gate + G2 indicators only).</div>' +
      '<div class="controls s1-controls">' +
        '<div class="ctrl-grp"><span class="ctrl-label">Scope</span>' +
          '<button class="toggle-btn active" data-hr-scope="all" onclick="hrSetScope(\'all\')">All <span id="hr-cnt-all"></span></button>' +
          '<button class="toggle-btn" data-hr-scope="live" onclick="hrSetScope(\'live\')">Live <span id="hr-cnt-live"></span></button>' +
          '<button class="toggle-btn" data-hr-scope="sector" onclick="hrSetScope(\'sector\')">Sectors <span id="hr-cnt-sector"></span></button>' +
          '<button class="toggle-btn" data-hr-scope="industry" onclick="hrSetScope(\'industry\')">Industries <span id="hr-cnt-industry"></span></button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Peers</button>' +
          '<button class="toggle-btn disabled" title="Definition pending">Cohorts</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Colour by</span>' +
          '<button class="toggle-btn active" data-hr-tint="none" onclick="hrSetTint(\'none\')">Off</button>' +
          '<button class="toggle-btn" data-hr-tint="industry" onclick="hrSetTint(\'industry\')">Industry</button>' +
          '<button class="toggle-btn" data-hr-tint="sector" onclick="hrSetTint(\'sector\')">Sector</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Portfolio tint</span>' +
          '<button class="toggle-btn active" data-hr-port="off" onclick="hrSetPort(\'off\')">Off</button>' +
          '<button class="toggle-btn" data-hr-port="on" onclick="hrSetPort(\'on\')">On</button>' +
        '</div>' +
      '</div>' +
      '<div class="rating-tiles s1-rating-tiles" id="hr-pattern-tiles"></div>' +
      '<div class="group-captions">' + captionHtml + '</div>' +
      '<div class="table-wrap"><div class="v2-hscroll">' +
        '<table class="data-table" id="hr-main-table"><colgroup>' + cg + '</colgroup>' +
        '<thead><tr class="group-header-row">' + gHdr + '</tr><tr class="sub-group-row">' + subGrp + '</tr><tr class="col-header-row" id="hr-col-header-row"></tr></thead>' +
        '<tbody id="hr-tbody"></tbody></table>' +
      '</div></div>';

    host.innerHTML = html;

    var tilesEl = document.getElementById('hr-pattern-tiles');
    if (tilesEl) {
      tilesEl.addEventListener('click', function(e) {
        var chip = e.target.closest('.pi-tier-chip');
        if (chip) { var ct = chip.getAttribute('data-tier'); if (ct) hrToggleTier(ct); return; }
        if (e.target.closest('.rating-tile')) hrSelectAllTiers();
      });
    }
    var hdrEl = document.getElementById('hr-col-header-row');
    if (hdrEl) {
      hdrEl.addEventListener('click', function(e) {
        var th = e.target.closest('th'); if (!th) return;
        var key = th.getAttribute('data-sort-key'); if (key) hrOnSort(key);
      });
    }
    return true;
  }

  function renderHealthyRetest() {
    if (!hrBuildScaffold()) return;
    hrBuildHeaderRow();
    hrRenderRows();
    if (window.measureV2Ribbon) measureV2Ribbon();
  }
  window.renderHealthyRetest = renderHealthyRetest;

})();

/* MD-V2-S47-TAB-HEALTHY-RETEST-MARKER-MODULE-END */



</script>
<style>
/* MD-V2-S59-TAB-PB-SPLIT-MARKER-CSS-START */
/* ── S1 Probing Bet ─────────────────────────────────────── */
#tab-tests_probing_bet_s1 .group-captions { display: grid; grid-template-columns: repeat(4,1fr); gap: 10px; margin: 16px 0 14px 0; }
#tab-tests_probing_bet_s1 .group-captions .gcap { background: #fbfaf5; border: 1px solid #e0dcc8; border-left: 3px solid #aaa; border-radius: 4px; padding: 10px 12px; font-size: 11px; line-height: 1.45; color: #555; }
#tab-tests_probing_bet_s1 .group-captions .gcap b { display: block; margin-bottom: 4px; font-weight: 700; font-size: 11px; letter-spacing: 0.2px; }
#tab-tests_probing_bet_s1 .group-captions .gcap-g1 { border-left-color: #b08a4e; } #tab-tests_probing_bet_s1 .group-captions .gcap-g1 b { color: #b08a4e; }
#tab-tests_probing_bet_s1 .group-captions .gcap-g2 { border-left-color: #5a8a6a; } #tab-tests_probing_bet_s1 .group-captions .gcap-g2 b { color: #5a8a6a; }
#tab-tests_probing_bet_s1 .group-captions .gcap-g3 { border-left-color: #4a6a8a; } #tab-tests_probing_bet_s1 .group-captions .gcap-g3 b { color: #4a6a8a; }
#tab-tests_probing_bet_s1 .group-captions .gcap-g4 { border-left-color: #888; }    #tab-tests_probing_bet_s1 .group-captions .gcap-g4 b { color: #888; }
#tab-tests_probing_bet_s1 .s1-rating-tiles { display: grid; grid-template-columns: 1fr; gap: 8px; }
#tab-tests_probing_bet_s1 .s1-rating-tiles .pi-tile-s1pb { background: rgba(27,94,32,0.08); border: 1px solid rgba(27,94,32,0.22); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
#tab-tests_probing_bet_s1 .s1-rating-tiles .pi-tile-s1pb.active { background: rgba(27,94,32,0.18); border: 1.5px solid #1b5e20; }
#tab-tests_probing_bet_s1 .s1-rating-tiles .pi-strip-s1pb { background: #1b5e20; height: 4px; margin-top: 6px; border-radius: 2px; }
#tab-tests_probing_bet_s1 .s1-rating-tiles .rt-breakdown { font-size: 9px; color: #888; margin-top: 4px; line-height: 1.35; }
#tab-tests_probing_bet_s1 .pi-tier-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 7px; }
#tab-tests_probing_bet_s1 .pi-tier-chip { font-size: 10px; padding: 2px 6px; border-radius: 4px; cursor: pointer; user-select: none; border: 0.5px solid; line-height: 1.4; white-space: nowrap; transition: background 0.12s, color 0.12s; }
#tab-tests_probing_bet_s1 .pi-chip-s1pb { background: #E8F5E9; color: #1b5e20; border-color: #A5D6A7; }
#tab-tests_probing_bet_s1 .pi-chip-s1pb.on { background: #1b5e20; color: #fff; border-color: #1b5e20; font-weight: 500; }
#tab-tests_probing_bet_s1 .pi-tier-chip:hover { filter: brightness(0.96); }
/* ── S2 Probing Bet ─────────────────────────────────────── */
#tab-tests_probing_bet_s2 .group-captions { display: grid; grid-template-columns: repeat(4,1fr); gap: 10px; margin: 16px 0 14px 0; }
#tab-tests_probing_bet_s2 .group-captions .gcap { background: #fbfaf5; border: 1px solid #e0dcc8; border-left: 3px solid #aaa; border-radius: 4px; padding: 10px 12px; font-size: 11px; line-height: 1.45; color: #555; }
#tab-tests_probing_bet_s2 .group-captions .gcap b { display: block; margin-bottom: 4px; font-weight: 700; font-size: 11px; letter-spacing: 0.2px; }
#tab-tests_probing_bet_s2 .group-captions .gcap-g1 { border-left-color: #b08a4e; } #tab-tests_probing_bet_s2 .group-captions .gcap-g1 b { color: #b08a4e; }
#tab-tests_probing_bet_s2 .group-captions .gcap-g2 { border-left-color: #5a8a6a; } #tab-tests_probing_bet_s2 .group-captions .gcap-g2 b { color: #5a8a6a; }
#tab-tests_probing_bet_s2 .group-captions .gcap-g3 { border-left-color: #4a6a8a; } #tab-tests_probing_bet_s2 .group-captions .gcap-g3 b { color: #4a6a8a; }
#tab-tests_probing_bet_s2 .group-captions .gcap-g4 { border-left-color: #888; }    #tab-tests_probing_bet_s2 .group-captions .gcap-g4 b { color: #888; }
#tab-tests_probing_bet_s2 .s1-rating-tiles { display: grid; grid-template-columns: 1fr; gap: 8px; }
#tab-tests_probing_bet_s2 .s1-rating-tiles .pi-tile-s2pb { background: rgba(46,125,50,0.08); border: 1px solid rgba(46,125,50,0.22); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
#tab-tests_probing_bet_s2 .s1-rating-tiles .pi-tile-s2pb.active { background: rgba(46,125,50,0.18); border: 1.5px solid #2e7d32; }
#tab-tests_probing_bet_s2 .s1-rating-tiles .pi-strip-s2pb { background: #2e7d32; height: 4px; margin-top: 6px; border-radius: 2px; }
#tab-tests_probing_bet_s2 .s1-rating-tiles .rt-breakdown { font-size: 9px; color: #888; margin-top: 4px; line-height: 1.35; }
#tab-tests_probing_bet_s2 .pi-tier-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 7px; }
#tab-tests_probing_bet_s2 .pi-tier-chip { font-size: 10px; padding: 2px 6px; border-radius: 4px; cursor: pointer; user-select: none; border: 0.5px solid; line-height: 1.4; white-space: nowrap; transition: background 0.12s, color 0.12s; }
#tab-tests_probing_bet_s2 .pi-chip-s2pb { background: #E8F5E9; color: #2e7d32; border-color: #A5D6A7; }
#tab-tests_probing_bet_s2 .pi-chip-s2pb.on { background: #2e7d32; color: #fff; border-color: #2e7d32; font-weight: 500; }
#tab-tests_probing_bet_s2 .pi-tier-chip:hover { filter: brightness(0.96); }
/* ── Shared table base (both tabs) ─────────────────────── */
#pb-s1-table, #pb-s2-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 11px; table-layout: fixed; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }
#pb-s1-table thead, #pb-s2-table thead { position: sticky; top: 0; z-index: 50; background: #fbfaf5; box-shadow: 0 2px 4px rgba(0,0,0,0.06); }
#pb-s1-table thead th, #pb-s2-table thead th { background: #fbfaf5 !important; border-bottom: 1px solid #e0dcc8; padding: 7px 3px; text-align: center; font-weight: 600; font-size: 10px; color: #666; cursor: pointer; user-select: none; line-height: 1.25; vertical-align: middle; text-transform: none; }
#pb-s1-table thead th:hover, #pb-s2-table thead th:hover { background: #f0ebd9 !important; }
#pb-s1-table thead .group-header-row th, #pb-s2-table thead .group-header-row th { background: #f3efe2 !important; font-size: 9.5px; text-transform: none; font-weight: 700; letter-spacing: 0.2px; padding: 5px 3px; cursor: default; line-height: 1.25; }
#pb-s1-table thead .group-header-row th:hover, #pb-s2-table thead .group-header-row th:hover { background: #f3efe2 !important; }
#pb-s1-table thead tr.group-header-row th, #pb-s2-table thead tr.group-header-row th { position: sticky; top: 0; }
#pb-s1-table thead tr.sub-group-row th, #pb-s2-table thead tr.sub-group-row th { position: sticky; top: 24px; font-size: 9px; text-transform: uppercase; letter-spacing: 0.3px; color: #888; padding: 3px; font-weight: 600; background: #f8f6ee !important; border-bottom: 1px solid #e0dcc8; }
#pb-s1-table thead tr.col-header-row th, #pb-s2-table thead tr.col-header-row th { position: sticky; top: 44px; border-top: 1px solid #e0dcc8; }
#pb-s1-table td, #pb-s2-table td { padding: 5px 4px; border-bottom: 1px solid #efece0; text-align: center; vertical-align: middle; height: 38px; box-sizing: border-box; font-variant-numeric: tabular-nums; }
/* S1 table colours */
#pb-s1-table thead .gh-inputs { color: #555; }
#pb-s1-table thead .gh-g1 { color: #b08a4e; }
#pb-s1-table thead .gh-rating { color: #1b5e20; }
#pb-s1-table thead .gh-g2 { color: #5a8a6a; }
#pb-s1-table thead .gh-g3 { color: #4a6a8a; }
#pb-s1-table thead .gh-context { color: #888; }
#pb-s1-table .hd { display: inline-flex; align-items: center; justify-content: center; gap: 3px; width: 100%; }
#pb-s1-table .hd .lbl { white-space: normal; word-break: break-word; }
#pb-s1-table .hd .sort-arrow { font-size: 9px; color: #1b5e20; flex: 0 0 auto; line-height: 1; }
#pb-s1-table .hd .sort-placeholder { width: 9px; flex: 0 0 auto; }
#pb-s1-table tr:hover { background: rgba(27,94,32,0.05); }
#pb-s1-table td.grp-start-g1, #pb-s1-table th.grp-start-g1 { border-left: 2px solid rgba(176,138,78,0.50); }
#pb-s1-table td.grp-start-rating, #pb-s1-table th.grp-start-rating { border-left: 2px solid rgba(27,94,32,0.50); }
#pb-s1-table td.grp-start-g2, #pb-s1-table th.grp-start-g2 { border-left: 2px solid rgba(90,138,106,0.50); }
#pb-s1-table td.grp-start-g3, #pb-s1-table th.grp-start-g3 { border-left: 2px solid rgba(74,106,138,0.50); }
#pb-s1-table td.grp-start-context, #pb-s1-table th.grp-start-context { border-left: 2px solid rgba(136,136,136,0.35); }
/* S2 table colours */
#pb-s2-table thead .gh-inputs { color: #555; }
#pb-s2-table thead .gh-g1 { color: #b08a4e; }
#pb-s2-table thead .gh-rating { color: #2e7d32; }
#pb-s2-table thead .gh-g2 { color: #5a8a6a; }
#pb-s2-table thead .gh-g3 { color: #4a6a8a; }
#pb-s2-table thead .gh-context { color: #888; }
#pb-s2-table .hd { display: inline-flex; align-items: center; justify-content: center; gap: 3px; width: 100%; }
#pb-s2-table .hd .lbl { white-space: normal; word-break: break-word; }
#pb-s2-table .hd .sort-arrow { font-size: 9px; color: #2e7d32; flex: 0 0 auto; line-height: 1; }
#pb-s2-table .hd .sort-placeholder { width: 9px; flex: 0 0 auto; }
#pb-s2-table tr:hover { background: rgba(46,125,50,0.05); }
#pb-s2-table td.grp-start-g1, #pb-s2-table th.grp-start-g1 { border-left: 2px solid rgba(176,138,78,0.50); }
#pb-s2-table td.grp-start-rating, #pb-s2-table th.grp-start-rating { border-left: 2px solid rgba(46,125,50,0.50); }
#pb-s2-table td.grp-start-g2, #pb-s2-table th.grp-start-g2 { border-left: 2px solid rgba(90,138,106,0.50); }
#pb-s2-table td.grp-start-g3, #pb-s2-table th.grp-start-g3 { border-left: 2px solid rgba(74,106,138,0.50); }
#pb-s2-table td.grp-start-context, #pb-s2-table th.grp-start-context { border-left: 2px solid rgba(136,136,136,0.35); }
/* Shared cell styles for both tables */
#pb-s1-table td.pi-pass, #pb-s2-table td.pi-pass { font-weight: 700; }
#pb-s1-table td.pi-pass { background: rgba(27,94,32,0.12); color: #1b5e20; }
#pb-s2-table td.pi-pass { background: rgba(46,125,50,0.12); color: #2e7d32; }
#pb-s1-table td.pi-fail, #pb-s2-table td.pi-fail { color: #999; }
#pb-s1-table td.s1ctx-pass, #pb-s2-table td.s2ctx-pass { background: rgba(176,138,78,0.14); color: #7a5a1a; font-weight: 700; }
#pb-s1-table td.s1ctx-fail, #pb-s2-table td.s2ctx-fail { color: #ccc; }
#pb-s1-table .s1ctx-pill, #pb-s2-table .s2ctx-pill { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 9px; font-weight: 700; line-height: 1.3; white-space: nowrap; }
#pb-s1-table .s1ctx-pill-prob { background: #b08a4e; color: #fff; }
#pb-s1-table .s1ctx-pill-pla  { background: rgba(176,138,78,0.35); color: #6a4a10; }
#pb-s1-table .s1ctx-pill-pos  { background: rgba(176,138,78,0.15); color: #8a6a2a; }
#pb-s1-table .s1ctx-pill-none { background: #ece9dd; color: #aaa; }
#pb-s2-table .s2ctx-pill-prob { background: #b08a4e; color: #fff; }
#pb-s2-table .s2ctx-pill-pla  { background: rgba(176,138,78,0.35); color: #6a4a10; }
#pb-s2-table .s2ctx-pill-pos  { background: rgba(176,138,78,0.15); color: #8a6a2a; }
#pb-s2-table .s2ctx-pill-none { background: #ece9dd; color: #aaa; }
#pb-s1-table td.pi-rating-cell, #pb-s2-table td.pi-rating-cell { padding: 3px 4px; }
#pb-s1-table td.pi-rating-cell { background: rgba(27,94,32,0.04); }
#pb-s2-table td.pi-rating-cell { background: rgba(46,125,50,0.04); }
#pb-s1-table .pi-pill, #pb-s2-table .pi-pill { display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 9.5px; font-weight: 800; line-height: 1.3; white-space: nowrap; }
#pb-s1-table .pi-pill-tint-qualified { background: #1b5e20; color: #fff; }
#pb-s1-table .pi-pill-tint-prob { background: #2E7D32; color: #fff; }
#pb-s1-table .pi-pill-tint-pla  { background: rgba(27,94,32,0.30); color: #0a4a3a; }
#pb-s1-table .pi-pill-tint-pos  { background: rgba(27,94,32,0.14); color: #3a6a5a; }
#pb-s1-table .pi-pill-tint-none { background: #ece9dd; color: #999; }
#pb-s2-table .pi-pill-tint-qualified { background: #1b5e20; color: #fff; }
#pb-s2-table .pi-pill-tint-prob { background: #2E7D32; color: #fff; }
#pb-s2-table .pi-pill-tint-pla  { background: rgba(46,125,50,0.30); color: #0a4a3a; }
#pb-s2-table .pi-pill-tint-pos  { background: rgba(46,125,50,0.14); color: #3a6a5a; }
#pb-s2-table .pi-pill-tint-none { background: #ece9dd; color: #999; }
#pb-s1-table td.pi-score-cell, #pb-s2-table td.pi-score-cell { padding: 4px 3px; border-right: 1px solid rgba(46,125,50,0.18); }
#pb-s1-table td.pi-score-cell { background: rgba(27,94,32,0.04); border-right-color: rgba(27,94,32,0.18); }
#pb-s2-table td.pi-score-cell { background: rgba(46,125,50,0.04); }
#pb-s1-table .pi-pip-row, #pb-s2-table .pi-pip-row { display: inline-flex; align-items: center; gap: 2px; justify-content: center; }
#pb-s1-table .pi-pip-row .pip, #pb-s2-table .pi-pip-row .pip { width: 6px; height: 6px; border-radius: 50%; background: #d8d4c4; display: inline-block; }
#pb-s1-table .pi-pip-row .pip.on { background: #1b5e20; }
#pb-s2-table .pi-pip-row .pip.on { background: #2e7d32; }
#pb-s1-table .pi-pip-row .pi-score-num, #pb-s2-table .pi-pip-row .pi-score-num { font-size: 9.5px; color: #444; margin-left: 4px; font-weight: 700; }
#pb-s1-table td.ct-window-col, #pb-s2-table td.ct-window-col { padding: 3px 4px; font-size: 10px; }
#pb-s1-table td.ct-window-fired-recent, #pb-s2-table td.ct-window-fired-recent { background: rgba(46,125,50,0.16); }
#pb-s1-table td.ct-window-fired-recent .ct-window-label, #pb-s2-table td.ct-window-fired-recent .ct-window-label { color: #0a4a3a; font-weight: 700; }
#pb-s1-table td.ct-window-fired-older, #pb-s2-table td.ct-window-fired-older { background: rgba(186,117,23,0.14); }
#pb-s1-table td.ct-window-fired-older .ct-window-label, #pb-s2-table td.ct-window-fired-older .ct-window-label { color: #7a4e0a; font-weight: 600; }
#pb-s1-table td.ct-window-none, #pb-s2-table td.ct-window-none { color: #bbb; }
#pb-s1-table td.ct-window-building, #pb-s2-table td.ct-window-building { color: #b59a5a; font-style: italic; font-size: 9px; }
#pb-s1-table td.rds-cell, #pb-s2-table td.rds-cell { padding: 3px 4px; font-size: 10px; }
#pb-s1-table td.rds-cell.rds-recent a, #pb-s2-table td.rds-cell.rds-recent a { color: #2e7d32; font-weight: 700; text-decoration: none; cursor: pointer; }
#pb-s1-table td.rds-cell.rds-older a, #pb-s2-table td.rds-cell.rds-older a { color: #7a5a1a; font-weight: 600; text-decoration: none; cursor: pointer; }
#pb-s1-table td.rds-cell a:hover, #pb-s2-table td.rds-cell a:hover { text-decoration: underline; }
#pb-s1-table td.rds-cell.rds-none, #pb-s2-table td.rds-cell.rds-none { color: #ccc; }
#pb-s1-table td.name-cell, #pb-s2-table td.name-cell { text-align: left; padding: 4px 4px 4px 8px; line-height: 1.15; }
#pb-s1-table td.name-cell .co, #pb-s2-table td.name-cell .co { font-weight: 700; font-size: 11px; color: #2a2a2a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#pb-s1-table td.name-cell .tk, #pb-s2-table td.name-cell .tk { font-size: 9px; color: #999; font-weight: 500; margin-top: 1px; }
#pb-s1-table td.name-cell .live-dot, #pb-s2-table td.name-cell .live-dot { color: #2e7d32; font-weight: 700; margin-right: 4px; display: inline-block; vertical-align: middle; }
#pb-s1-table td.taxon, #pb-s2-table td.taxon { text-align: left; font-size: 9px; line-height: 1.2; padding: 4px; }
#pb-s1-table td.taxon .ind, #pb-s2-table td.taxon .ind { color: #666; font-weight: 500; }
#pb-s1-table td.taxon .sec, #pb-s2-table td.taxon .sec { color: #999; }
#pb-s1-table col.c-name, #pb-s2-table col.c-name { width: 124px; }
#pb-s1-table col.c-taxon, #pb-s2-table col.c-taxon { width: 148px; }
#pb-s1-table col.c-price, #pb-s2-table col.c-price { width: 50px; }
#pb-s1-table col.c-pullback, #pb-s2-table col.c-pullback { width: 56px; }
#pb-s1-table col.c-ctx-rating, #pb-s2-table col.c-ctx-rating { width: 70px; }
#pb-s1-table col.c-ctx-gate, #pb-s2-table col.c-ctx-gate { width: 40px; }
#pb-s1-table col.c-ctx-test, #pb-s2-table col.c-ctx-test { width: 40px; }
#pb-s1-table col.c-ctx-streak, #pb-s2-table col.c-ctx-streak { width: 44px; }
#pb-s1-table col.c-rating, #pb-s2-table col.c-rating { width: 70px; }
#pb-s1-table col.c-score, #pb-s2-table col.c-score { width: 54px; }
#pb-s1-table col.c-test, #pb-s2-table col.c-test { width: 40px; }
#pb-s1-table col.c-window, #pb-s2-table col.c-window { width: 50px; }
#pb-s1-table col.c-rds, #pb-s2-table col.c-rds { width: 60px; }
#pb-s1-table tr.tint-row td.name-cell, #pb-s1-table tr.tint-row td.taxon,
#pb-s2-table tr.tint-row td.name-cell, #pb-s2-table tr.tint-row td.taxon { background: var(--tint-bg) !important; }
#pb-s1-table tr.portfolio-band td:last-child, #pb-s2-table tr.portfolio-band td:last-child { border-right: 4px solid var(--portfolio-color); }
#pb-s1-table tr.portfolio-tint, #pb-s2-table tr.portfolio-tint { background: var(--portfolio-bg); }
#pb-s1-table tr.portfolio-tint:hover, #pb-s2-table tr.portfolio-tint:hover { background: var(--portfolio-bg-hover); }
/* MD-V2-S59-TAB-PB-SPLIT-MARKER-CSS-END */

</style>
<script>


/* MD-V2-S59-TAB-PB-SPLIT-MARKER-MODULE-START */
// =============================================================================
// S1 PROBING BET — TAB MODULE (S59)
// =============================================================================
(function() {
  'use strict';
  var PB_KEY = 'probing_bet_s1';
  var STAGE_KEY = 'stage_1';
  var ACCENT = '#1b5e20';
  var TAB_ID = 'tests_probing_bet_s1';
  var TABLE_ID = 'pb-s1-table';
  var TILE_CLS = 'pi-tile-s1pb'; var STRIP_CLS = 'pi-strip-s1pb'; var CHIP_CLS = 'pi-chip-s1pb';
  var TIERS = ['None','Possible','Plausible','Probable','Qualified'];
  var TIER_RANK = {'Qualified':6,'Probable':5,'Plausible':3,'Possible':2,'None':1};
  var TIER_CLS  = {'Qualified':'tint-qualified','Probable':'tint-prob','Plausible':'tint-pla','Possible':'tint-pos','None':'tint-none'};
  var CTX_PILL_CLS = 's1ctx-pill';
  var CTX_PASS_CLS = 's1ctx-pass'; var CTX_FAIL_CLS = 's1ctx-fail';

  var S1_GATE_DEFS = [
    {key:'gate_200D_declining_vs_80d', label:'1. 200D MA &darr; vs 80D ago', tooltip:'200-day MA is lower than it was 80 days ago — prior downtrend present'},
    {key:'gate_price_above_150D',      label:'2. Price &gt; 150D MA',         tooltip:'Price above the 150-day moving average'}
  ];

  var PB_TESTS = [
    {key:'g1_stage_qualifies',           label:'1. Stage 1 qualifies',  grp:'gate',    tooltip:'Stage 1 rating is Probable or Plausible'},
    {key:'g2_5d_rising',                 label:'2. 5D MA rising',        grp:'setup',   tooltip:'5-day moving average is rising DoD'},
    {key:'g3_10d_rising',                label:'3. 10D MA rising',       grp:'setup',   tooltip:'10-day moving average is rising DoD'},
    {key:'g4_price_gt_20d',              label:'4. Price &gt; 20D MA',   grp:'setup',   tooltip:'Current price above the 20-day MA'},
    {key:'g5_20d_turn_last_5d',          label:'5. 20D MA turned up',    grp:'trigger', tooltip:'20D MA rising now AND was falling 5 days ago'},
    {key:'g6_followthrough_close_ge2pct',label:'6. Confirm: close 2%+', grp:'trigger', tooltip:'Close at least 2% above yesterday'}
  ];

  var pbs1State = {
    mode: {tests:'tick'}, scope:'all', tierFilter:[], tint:'none', port:'off',
    sort:{col:'company', dir:'asc'}
  };

  function pricesLookup() {
    if (window._ctPricesByTicker) return window._ctPricesByTicker;
    var out={}; var arr=(window.MASTER_DATA&&MASTER_DATA.prices)||[];
    for(var i=0;i<arr.length;i++) if(arr[i]&&arr[i].ticker) out[arr[i].ticker]=arr[i];
    window._ctPricesByTicker=out; return out;
  }
  function liveTickers(){var o={};var inv=(window.MASTER_DATA&&MASTER_DATA.positions&&MASTER_DATA.positions.investments)||[];for(var i=0;i<inv.length;i++)if(inv[i].ticker)o[inv[i].ticker]=true;return o;}
  function liveSectors(){var o={},p=pricesLookup(),t=liveTickers();for(var k in t){var px=p[k];if(px&&px.sector)o[px.sector]=true;}return o;}
  function liveIndustries(){var o={},p=pricesLookup(),t=liveTickers();for(var k in t){var px=p[k];if(px&&px.industry)o[px.industry]=true;}return o;}

  function getPbRec(row){var dk=row.md_v2&&row.md_v2.tests;return(dk&&dk[PB_KEY])||null;}
  function getStageRec(row){return(row.md_v2&&row.md_v2[STAGE_KEY])||null;}
  function pbRating(row){var r=getPbRec(row);return r?(r.rating||'None'):'None';}
  function pbTest(row,key){var r=getPbRec(row);return!!(r&&r.tests&&r.tests[key]);}
  function stageRating(row){var s=getStageRec(row);return(s&&s.rating)||'None';}
  function s1Gate(row,key){var s=getStageRec(row);return!!(s&&s[key]);}

  function getRows(){
    var raw=(window.MASTER_DATA&&MASTER_DATA.filters)||[];
    var prices=pricesLookup();
    var live=liveTickers(),liveS=liveSectors(),liveI=liveIndustries();
    var rows=[];
    for(var i=0;i<raw.length;i++){
      var s=raw[i];
      if(!s||!s.md_v2||!s.md_v2.tests) continue;
      var rec=s.md_v2.tests[PB_KEY]; if(!rec) continue;
      var p=prices[s.ticker]||{}; var mas=p.mas||{};
      rows.push({ticker:s.ticker,company:p.company_name||s.ticker,
        sector:p.sector||'',industry:p.industry||'',
        price:p.price,recent_pullback:p.recent_pullback_pct,
        md_v2:s.md_v2,is_live:!!live[s.ticker],
        sector_in_portfolio:!!liveS[p.sector],
        industry_in_portfolio:!!liveI[p.industry]});
    }
    return rows;
  }

  function fmtNum(n){if(n==null||isNaN(n))return'-';var abs=Math.abs(n),dp=abs>=100?0:(abs>=20?1:2);if(Math.abs(n-Math.round(n))<1e-9)dp=0;var f=abs.toLocaleString('en-GB',{minimumFractionDigits:dp,maximumFractionDigits:dp});return n<0?'('+f+')':f;}
  function fmtPct(p){if(p==null||isNaN(p))return'-';var r=Math.round(p),a=Math.abs(r);return r<0?'('+a+')%':r+'%';}
  function colGreen(i){if(i>=0.6)return ACCENT;if(i>=0.25)return'#4CAF50';if(i>=0.05)return'#81C784';if(i<=-0.6)return'#A32D2D';if(i<=-0.25)return'#E24B4A';if(i<=-0.05)return'#F09595';return'#888';}
  function hashColor(lbl,alpha){if(!lbl)return null;var h=0;for(var i=0;i<lbl.length;i++)h=(h*31+lbl.charCodeAt(i))&0xffff;return'hsla('+(h%360)+',35%,55%,'+alpha+')';}
  function portInfo(row){if(row.is_live)return{color:'#1b5e20',bg:'rgba(27,94,32,0.10)',bgHover:'rgba(27,94,32,0.14)'};if(row.sector_in_portfolio)return{color:'#1b5e20',bg:'rgba(27,94,32,0.05)',bgHover:'rgba(27,94,32,0.08)'};if(row.industry_in_portfolio)return{color:'#1b5e20',bg:'rgba(27,94,32,0.025)',bgHover:'rgba(27,94,32,0.05)'};return null;}

  function priceCell(row,cls){return'<td class="num '+(cls||'')+'">'  +fmtNum(row.price)+'</td>';}
  function pullbackCell(row,cls){var v=row.recent_pullback;if(v==null||isNaN(v))return'<td class="num '+(cls||'')+'">-</td>';var pv=v*100,i=Math.max(-1,Math.min(1,(pv-5)/20));return'<td class="num '+(cls||'')+'" style="color:'+colGreen(-i)+'">'+Math.round(pv)+'%</td>';}
  function s1RatingCell(row,cls){var r=stageRating(row);var pc=r==='Probable'?'s1ctx-pill-prob':r==='Plausible'?'s1ctx-pill-pla':r==='Possible'?'s1ctx-pill-pos':'s1ctx-pill-none';return'<td class="'+(cls||'')+'"><span class="'+CTX_PILL_CLS+' '+pc+'">'+r+'</span></td>';}
  function s1GateCell(row,key,cls){var p=s1Gate(row,key);return p?'<td class="'+CTX_PASS_CLS+' '+(cls||'')+'"><span class="tick">&#10003;</span></td>':'<td class="'+CTX_FAIL_CLS+' '+(cls||'')+'">.</td>';}
  function s1StreakCell(row,cls){var s=getStageRec(row);var v=s?s.streak:null;if(v==null)return'<td class="'+(cls||'')+'">-</td>';return'<td class="'+(cls||'')+'" style="color:'+colGreen(Math.max(-1,Math.min(1,(v-40)/80)))+'">'+v+'</td>';}
  function pbRatingCell(row,cls){var r=pbRating(row);var rc=TIER_CLS[r]||'tint-none';return'<td class="'+(cls||'')+' pi-rating-cell '+rc+'"><span class="pi-pill pi-pill-'+rc+'">'+r+'</span></td>';}
  function pbScoreCell(row,cls){var rec=getPbRec(row);var cnt=rec?(rec.count||0):0,tot=rec?(rec.total||0):0;var s='';for(var i=0;i<tot;i++)s+='<span class="pip '+(i<cnt?'on':'')+'"></span>';return'<td class="'+(cls||'')+' pi-score-cell"><div class="pi-pip-row">'+s+'<span class="pi-score-num">'+cnt+'/'+tot+'</span></div></td>';}
  function pbTestCell(row,key,cls){var p=pbTest(row,key);return p?'<td class="pi-pass '+(cls||'')+'"><span class="tick">&#10003;</span></td>':'<td class="pi-fail '+(cls||'')+'">.</td>';}
  function windowCell(row,wk,cls){var rec=getPbRec(row);var ex=cls||'';if(!rec)return'<td class="'+ex+' ct-window-none">-</td>';var d=rec.history_depth||0,wd=wk==='l5d'?5:20;if(d<wd)return'<td class="'+ex+' ct-window-building" title="'+d+' of '+wd+' days">building</td>';var fired=wk==='l5d'?!!rec.fired_l5d:!!rec.fired_l20d;if(!fired)return'<td class="'+ex+' ct-window-none">-</td>';var ds=rec.days_since_fired;var lbl=ds===0?'today':ds===1?'1d ago':(ds!=null?ds+'d ago':'fired');var sc=(ds!=null&&ds<=5)?'ct-window-fired-recent':'ct-window-fired-older';return'<td class="'+ex+' '+sc+'"><span class="ct-window-label">'+lbl+'</span></td>';}
  function rdsCell(row,cls){
    var idx=window.RDS_INDEX||{};var dt=idx[row.ticker];var ex=cls||'';
    if(!dt)return'<td class="rds-cell rds-none '+ex+'">-</td>';
    var parts=dt.split('-');var mon=['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
    var label=(parts[2]||'??')+'-'+(mon[parseInt(parts[1]||0,10)]||parts[1]||'??');
    var url='https://vfhqi.github.io/repository/#'+encodeURIComponent(row.ticker);
    var dDays=Math.round((Date.now()-new Date(dt).getTime())/(86400000));
    var ageCls=dDays<=21?'rds-recent':'rds-older';
    return'<td class="rds-cell '+ageCls+' '+ex+'"><a href="'+url+'" target="_blank" title="Open '+row.ticker+' in repository">'+label+'</a></td>';
  }

  function tierCounts(rows){var c={};for(var i=0;i<TIERS.length;i++)c[TIERS[i]]=0;for(var j=0;j<rows.length;j++){var r=pbRating(rows[j]);if(c[r]!=null)c[r]++;}return c;}
  function passHistogram(rows){var h=[];for(var k=0;k<=6;k++)h[k]=0;for(var i=0;i<rows.length;i++){var r=getPbRec(rows[i]);var cnt=r?(r.count||0):0;if(cnt>=0&&cnt<=6)h[cnt]++;}return h;}

  function updateScopeCounts(rows){function s(id,n){var e=document.getElementById(id);if(e)e.textContent='('+n+')';}s('pbs1-cnt-all',rows.length);s('pbs1-cnt-live',rows.filter(function(r){return r.is_live;}).length);s('pbs1-cnt-sector',rows.filter(function(r){return r.sector_in_portfolio;}).length);s('pbs1-cnt-industry',rows.filter(function(r){return r.industry_in_portfolio;}).length);}
  function applyScope(all){var rows=all.slice();if(pbs1State.scope==='live')rows=rows.filter(function(r){return r.is_live;});else if(pbs1State.scope==='sector')rows=rows.filter(function(r){return r.sector_in_portfolio;});else if(pbs1State.scope==='industry')rows=rows.filter(function(r){return r.industry_in_portfolio;});return rows;}
  function applyTierFilter(rows){var sel=pbs1State.tierFilter;if(!sel||sel.length===0)return rows;return rows.filter(function(r){return sel.indexOf(pbRating(r))>-1;});}

  function getSortVal(row,key){
    if(key==='company')return row.company||'';
    if(key==='sector')return row.sector||'';
    if(key==='price')return row.price||0;
    if(key==='recent_pullback')return row.recent_pullback==null?-Infinity:row.recent_pullback;
    if(key==='pb__rating')return TIER_RANK[pbRating(row)]||0;
    if(key==='pb__score'){var r=getPbRec(row);return r?(r.count||0):0;}
    if(key==='s1__rating')return TIER_RANK[stageRating(row)]||0;
    if(key==='s1__streak'){var s=getStageRec(row);return s?(s.streak||0):0;}
    if(key.indexOf('s1g__')===0){return s1Gate(row,key.slice(5))?1:0;}
    if(key.indexOf('pb__')===0){var tk=key.slice(4);if(tk==='l5d'||tk==='l20d'){var rec=getPbRec(row);if(!rec)return-1;var wd=tk==='l5d'?5:20;if((rec.history_depth||0)<wd)return-2;var fired=tk==='l5d'?rec.fired_l5d:rec.fired_l20d;if(!fired)return-1;var ds=rec.days_since_fired;return ds==null?0:1000-ds;}return pbTest(row,tk)?1:0;}
    if(key==='rds__date'){var idx=window.RDS_INDEX||{};return idx[row.ticker]||'';}
    return 0;
  }
  function onSort(key){if(pbs1State.sort.col===key)pbs1State.sort.dir=pbs1State.sort.dir==='desc'?'asc':'desc';else pbs1State.sort={col:key,dir:key==='company'?'asc':'desc'};buildHeader();renderRows();}

  function buildHeader(){
    var tr=document.getElementById('pbs1-col-header');if(!tr)return;
    var COL_LABELS={
      name:'Company - Ticker',taxon:'Industry - Sector',price:'Price',pullback:'Pullback',
      s1rating:'S1 Rating',s1g0:S1_GATE_DEFS[0].label,s1g1:S1_GATE_DEFS[1].label,s1streak:'Streak',
      pbrating:'Rating',pbscore:'Score',
      g1:'1. Gate: stage',g2:'2. 5D rising',g3:'3. 10D rising',g4:'4. P&gt;20D',
      g5:'5. 20D turned up',g6:'6. Close 2%+',
      l5d:'Fired 5d',l20d:'Fired 20d',rds:'RDS'
    };
    var COL_KEYS={name:'company',taxon:'sector',price:'price',pullback:'recent_pullback',
      s1rating:'s1__rating',s1g0:'s1g__'+S1_GATE_DEFS[0].key,s1g1:'s1g__'+S1_GATE_DEFS[1].key,s1streak:'s1__streak',
      pbrating:'pb__rating',pbscore:'pb__score',
      g1:'pb__g1_stage_qualifies',g2:'pb__g2_5d_rising',g3:'pb__g3_10d_rising',g4:'pb__g4_price_gt_20d',
      g5:'pb__g5_20d_turn_last_5d',g6:'pb__g6_followthrough_close_ge2pct',
      l5d:'pb__l5d',l20d:'pb__l20d',rds:'rds__date'};
    var COL_GRP_START={s1rating:'grp-start-g1',pbrating:'grp-start-rating',g1:'grp-start-g2',g5:'grp-start-g3',l5d:'grp-start-context'};
    var COL_TOOLTIPS={s1rating:'Stage 1 rating',s1g0:S1_GATE_DEFS[0].tooltip,s1g1:S1_GATE_DEFS[1].tooltip,s1streak:'Soft-stack streak (days)',
      pbrating:'PB S1 overall rating',pbscore:'Tests passed out of 6'};
    for(var i=0;i<PB_TESTS.length;i++)COL_TOOLTIPS['g'+(i+1)]=PB_TESTS[i].tooltip;
    var ORDER=['name','taxon','price','pullback','s1rating','s1g0','s1g1','s1streak','pbrating','pbscore','g1','g2','g3','g4','g5','g6','l5d','l20d','rds'];
    var h='';
    for(var ci=0;ci<ORDER.length;ci++){
      var id=ORDER[ci],sk=COL_KEYS[id],isSort=pbs1State.sort.col===sk;
      var arrow=isSort?'<span class="sort-arrow">'+(pbs1State.sort.dir==='desc'?'&#9660;':'&#9650;')+'</span>':'<span class="sort-placeholder"></span>';
      var gc=COL_GRP_START[id]||'';
      var tt=COL_TOOLTIPS[id]||COL_LABELS[id]||'';
      h+='<th class="'+gc+'" data-sort-key="'+sk+'" title="'+tt+'"><span class="hd"><span class="lbl">'+COL_LABELS[id]+'</span>'+arrow+'</span></th>';
    }
    tr.innerHTML=h;
  }

  function renderTile(scopeRows){
    var el=document.getElementById('pbs1-tile'); if(!el)return;
    var tc=tierCounts(scopeRows),total=scopeRows.length,cnt=total-(tc['None']||0);
    var sel=pbs1State.tierFilter||[],anySel=sel.length>0;
    var headline=cnt,headSub='of '+total.toLocaleString('en-GB')+' · '+Math.round(cnt/Math.max(1,total)*100)+'%';
    if(anySel){var ft=0;for(var z=0;z<sel.length;z++)ft+=(tc[sel[z]]||0);headline=ft;headSub=sel.join(' + ')+' · filtered';}
    var hist=passHistogram(scopeRows),breakdown='';
    for(var k=1;k<=6;k++){if(k>1)breakdown+=' · ';breakdown+=k+'/6: '+(hist[k]||0).toLocaleString('en-GB');}
    var chips='';
    var TIER_DISP=['Possible','Plausible','Probable','Qualified'];
    for(var c=0;c<TIER_DISP.length;c++){var t=TIER_DISP[c];var on=sel.indexOf(t)>-1;chips+='<span class="pi-tier-chip '+CHIP_CLS+(on?' on':'')+'" data-tier="'+t+'">'+t+' '+(tc[t]||0).toLocaleString('en-GB')+(on?' &#10003;':'')+'</span>';}
    el.innerHTML='<div class="rating-tile '+TILE_CLS+(anySel?' active':'')+'">'
      +'<div class="rt-label">S1 Probing Bet</div><div class="rt-count">'+headline.toLocaleString('en-GB')+'</div>'
      +'<div class="rt-sub">'+headSub+'</div><div class="rt-breakdown">'+breakdown+'</div>'
      +'<div class="pi-tier-chips">'+chips+'</div>'
      +'<div class="rt-strip '+STRIP_CLS+'"></div></div>';
    el.addEventListener('click',function(e){var chip=e.target.closest('.pi-tier-chip');if(chip){var t=chip.getAttribute('data-tier');if(t)window.pbs1ToggleTier(t);}});
  }

  function renderRows(){
    var tbody=document.getElementById('pbs1-tbody'); if(!tbody)return;
    var all=getRows(),scopeRows=applyScope(all);
    updateScopeCounts(all);renderTile(scopeRows);
    var rows=applyTierFilter(scopeRows);
    rows.sort(function(a,b){var va=getSortVal(a,pbs1State.sort.col),vb=getSortVal(b,pbs1State.sort.col);var cmp=typeof va==='string'?va.localeCompare(vb):(va||0)-(vb||0);if(cmp===0)cmp=a.ticker.localeCompare(b.ticker);return pbs1State.sort.dir==='desc'?-cmp:cmp;});
    var html='';
    for(var i=0;i<rows.length;i++){
      var s=rows[i],styles=[],cls=[];
      if(pbs1State.tint==='industry'){styles.push('--tint-bg: '+hashColor(s.industry,0.16));cls.push('tint-row');}
      else if(pbs1State.tint==='sector'){styles.push('--tint-bg: '+hashColor(s.sector,0.16));cls.push('tint-row');}
      if(pbs1State.port==='on'){var pi=portInfo(s);if(pi){styles.push('--portfolio-color:'+pi.color,'--portfolio-bg:'+pi.bg,'--portfolio-bg-hover:'+pi.bgHover);cls.push('portfolio-band','portfolio-tint');}}
      var sa=styles.length?' style="'+styles.join(';')+'"':'';
      var ca=cls.length?' class="'+cls.join(' ')+'"':'';
      var ld=s.is_live?'<span class="live-dot">&#9679;</span>':'';
      html+='<tr'+ca+sa+'>'
        +'<td class="name-cell"><div class="co">'+ld+(s.company||s.ticker)+'</div><div class="tk">'+s.ticker+'</div></td>'
        +'<td class="taxon"><div class="ind">'+(s.industry||'')+'</div><div class="sec">'+(s.sector||'')+'</div></td>'
        +priceCell(s,'')
        +pullbackCell(s,'')
        +s1RatingCell(s,'grp-start-g1')
        +s1GateCell(s,S1_GATE_DEFS[0].key,'')
        +s1GateCell(s,S1_GATE_DEFS[1].key,'')
        +s1StreakCell(s,'')
        +pbRatingCell(s,'grp-start-rating')
        +pbScoreCell(s,'')
        +pbTestCell(s,'g1_stage_qualifies','grp-start-g2')
        +pbTestCell(s,'g2_5d_rising','')
        +pbTestCell(s,'g3_10d_rising','')
        +pbTestCell(s,'g4_price_gt_20d','')
        +pbTestCell(s,'g5_20d_turn_last_5d','grp-start-g3')
        +pbTestCell(s,'g6_followthrough_close_ge2pct','')
        +windowCell(s,'l5d','ct-window-col grp-start-context')
        +windowCell(s,'l20d','ct-window-col')
        +rdsCell(s,'')
        +'</tr>';
    }
    tbody.innerHTML=html;
  }

  window.pbs1SetMode=function(k,v){pbs1State.mode[k]=v;var btns=document.querySelectorAll('button[data-pbs1-grp="'+k+'"]');for(var i=0;i<btns.length;i++)btns[i].classList.toggle('active',btns[i].getAttribute('data-pbs1-val')===v);renderRows();};
  window.pbs1SetScope=function(s){pbs1State.scope=s;var btns=document.querySelectorAll('button[data-pbs1-scope]');for(var i=0;i<btns.length;i++)btns[i].classList.toggle('active',btns[i].getAttribute('data-pbs1-scope')===s);renderRows();};
  window.pbs1SetTint=function(t){pbs1State.tint=t;var btns=document.querySelectorAll('button[data-pbs1-tint]');for(var i=0;i<btns.length;i++)btns[i].classList.toggle('active',btns[i].getAttribute('data-pbs1-tint')===t);renderRows();};
  window.pbs1SetPort=function(p){pbs1State.port=p;var btns=document.querySelectorAll('button[data-pbs1-port]');for(var i=0;i<btns.length;i++)btns[i].classList.toggle('active',btns[i].getAttribute('data-pbs1-port')===p);renderRows();};
  window.pbs1ToggleTier=function(tier){var sel=pbs1State.tierFilter||[],idx=sel.indexOf(tier);if(idx>-1)sel.splice(idx,1);else sel.push(tier);pbs1State.tierFilter=sel;renderRows();};
  window.pbs1OnSort=function(key){onSort(key);};

  function buildScaffold(){
    var host=document.getElementById('tab-'+TAB_ID); if(!host)return false;
    if(host.querySelector('#'+TABLE_ID))return true;
    var cg='<col class="c-name"><col class="c-taxon"><col class="c-price"><col class="c-pullback">'
      +'<col class="c-ctx-rating"><col class="c-ctx-gate"><col class="c-ctx-gate"><col class="c-ctx-streak">'
      +'<col class="c-rating"><col class="c-score">'
      +'<col class="c-test"><col class="c-test"><col class="c-test"><col class="c-test">'
      +'<col class="c-test"><col class="c-test">'
      +'<col class="c-window"><col class="c-window"><col class="c-rds">';
    var grpRow='<th class="gh-inputs" colspan="4">Inputs</th>'
      +'<th class="gh-g1 grp-start-g1" colspan="4">Group 1 — Stage 1 qualifying?</th>'
      +'<th class="gh-rating grp-start-rating" colspan="2">Rating</th>'
      +'<th class="gh-g2 grp-start-g2" colspan="4">Group 2 — Entry setup?</th>'
      +'<th class="gh-g3 grp-start-g3" colspan="2">Group 3 — Trigger?</th>'
      +'<th class="gh-context grp-start-context" colspan="3">Context</th>';
    var subRow='<th colspan="4"></th>'
      +'<th colspan="1">Stage rating</th><th colspan="2">Gates</th><th colspan="1">Streak</th>'
      +'<th colspan="1">Rating</th><th colspan="1">Score</th>'
      +'<th colspan="1">Gate</th><th colspan="3">Setup</th>'
      +'<th colspan="2">Trigger</th>'
      +'<th colspan="2">Fired</th><th colspan="1">RDS</th>';
    var thead='<tr class="group-header-row">'+grpRow+'</tr>'
      +'<tr class="sub-group-row">'+subRow+'</tr>'
      +'<tr class="col-header-row" id="pbs1-col-header"></tr>';
    host.innerHTML=
      '<div class="s1-intro">S1 Probing Bet — a small starter position on a Stage 1 (troughing/basing) stock that breaks out positively. Probes whether the trend is turning before committing a full position. The Stage 1 qualifying group shows context for the underlying trend state. Gate confirms stage qualifies; Setup checks MAs are rising and price is above 20D; Trigger requires the 20D MA to have freshly turned up, with a 2%+ follow-through close.</div>'
      +'<div class="controls s1-controls">'
        +'<div class="ctrl-grp"><span class="ctrl-label">Scope</span>'
          +'<button class="toggle-btn active" data-pbs1-scope="all" onclick="pbs1SetScope(\'all\')">All <span id="pbs1-cnt-all"></span></button>'
          +'<button class="toggle-btn" data-pbs1-scope="live" onclick="pbs1SetScope(\'live\')">Live <span id="pbs1-cnt-live"></span></button>'
          +'<button class="toggle-btn" data-pbs1-scope="sector" onclick="pbs1SetScope(\'sector\')">Sectors <span id="pbs1-cnt-sector"></span></button>'
          +'<button class="toggle-btn" data-pbs1-scope="industry" onclick="pbs1SetScope(\'industry\')">Industries <span id="pbs1-cnt-industry"></span></button>'
        +'</div>'
        +'<div class="ctrl-grp"><span class="ctrl-label">Colour by</span>'
          +'<button class="toggle-btn active" data-pbs1-tint="none" onclick="pbs1SetTint(\'none\')">Off</button>'
          +'<button class="toggle-btn" data-pbs1-tint="industry" onclick="pbs1SetTint(\'industry\')">Industry</button>'
          +'<button class="toggle-btn" data-pbs1-tint="sector" onclick="pbs1SetTint(\'sector\')">Sector</button>'
        +'</div>'
        +'<div class="ctrl-grp"><span class="ctrl-label">Portfolio tint</span>'
          +'<button class="toggle-btn active" data-pbs1-port="off" onclick="pbs1SetPort(\'off\')">Off</button>'
          +'<button class="toggle-btn" data-pbs1-port="on" onclick="pbs1SetPort(\'on\')">On</button>'
        +'</div>'
      +'</div>'
      +'<div class="s1-rating-tiles" id="pbs1-tile"></div>'
      +'<div class="table-wrap"><div class="v2-hscroll"><table class="data-table" id="'+TABLE_ID+'"><colgroup>'+cg+'</colgroup><thead>'+thead+'</thead><tbody id="pbs1-tbody"></tbody></table></div></div>';
    var hdr=document.getElementById('pbs1-col-header');
    if(hdr)hdr.addEventListener('click',function(e){var th=e.target.closest('th');if(!th)return;var k=th.getAttribute('data-sort-key');if(k)pbs1OnSort(k);});
    return true;
  }

  function renderProbingBetS1(){
    if(!buildScaffold())return;
    buildHeader();renderRows();
    if(window.measureV2Ribbon)measureV2Ribbon();
  }
  window.renderProbingBetS1=renderProbingBetS1;
})();

// =============================================================================
// S2 PROBING BET — TAB MODULE (S59)
// =============================================================================
(function() {
  'use strict';
  var PB_KEY = 'probing_bet_s2';
  var STAGE_KEY = 'stage_2';
  var ACCENT = '#2e7d32';
  var TAB_ID = 'tests_probing_bet_s2';
  var TABLE_ID = 'pb-s2-table';
  var TILE_CLS = 'pi-tile-s2pb'; var STRIP_CLS = 'pi-strip-s2pb'; var CHIP_CLS = 'pi-chip-s2pb';
  var TIERS = ['None','Possible','Plausible','Probable','Qualified'];
  var TIER_RANK = {'Qualified':6,'Probable':5,'Plausible':3,'Possible':2,'None':1};
  var TIER_CLS  = {'Qualified':'tint-qualified','Probable':'tint-prob','Plausible':'tint-pla','Possible':'tint-pos','None':'tint-none'};
  var CTX_PILL_CLS = 's2ctx-pill';
  var CTX_PASS_CLS = 's2ctx-pass'; var CTX_FAIL_CLS = 's2ctx-fail';

  var S2_GATE_DEFS = [
    {key:'g1_P_above_200D',      label:'1. P &gt; 200D MA',           tooltip:'Price above 200-day MA'},
    {key:'g2_P_above_150D',      label:'2. P &gt; 150D MA',           tooltip:'Price above 150-day MA'},
    {key:'g3_150D_above_200D',   label:'3. 150D &gt; 200D MA',        tooltip:'150-day MA above 200-day MA'},
    {key:'g4_within_25pct_52WH', label:'4. Within 25% of 52w high',   tooltip:'Price within 25% of 52-week high'}
  ];
  var S2_TEST_DEFS = [
    {key:'T5_50D_above_150D',            label:'5. 50D &gt; 150D MA',        tooltip:'50-day MA above 150-day MA'},
    {key:'T6_50D_above_200D',            label:'6. 50D &gt; 200D MA',        tooltip:'50-day MA above 200-day MA'},
    {key:'T7_industry_RS_pct_ge70',      label:'7. Industry pct. &ge;70',    tooltip:'Industry RS percentile at least 70'},
    {key:'T8_sector_RS_pct_ge70',        label:'8. Sector pct. &ge;70',      tooltip:'Sector RS percentile at least 70'},
    {key:'T9_stock_RS_vs_industry_ge70', label:'9. Stock pct. vs ind &ge;70',tooltip:'Stock RS vs industry percentile at least 70'}
  ];

  var PB_TESTS = [
    {key:'g1_stage_qualifies',           label:'1. Stage 2 qualifies', grp:'gate',    tooltip:'Stage 2 rating is Probable or Plausible'},
    {key:'g2_5d_rising',                 label:'2. 5D MA rising',       grp:'setup',   tooltip:'5-day MA rising DoD'},
    {key:'g3_10d_rising',                label:'3. 10D MA rising',      grp:'setup',   tooltip:'10-day MA rising DoD'},
    {key:'g4_price_gt_20d',              label:'4. P &gt; 20D MA',      grp:'setup',   tooltip:'Price above 20-day MA'},
    {key:'g5_20d_turn_last_5d',          label:'5. 20D MA turned up',   grp:'trigger', tooltip:'20D MA rising now, was falling 5d ago'},
    {key:'g6_followthrough_close_ge2pct',label:'6. Close 2%+',          grp:'trigger', tooltip:'Close at least 2% above yesterday'}
  ];

  var pbs2State = {
    mode:{tests:'tick'},scope:'all',tierFilter:[],tint:'none',port:'off',
    sort:{col:'company',dir:'asc'}
  };

  function pricesLookup(){if(window._ctPricesByTicker)return window._ctPricesByTicker;var out={};var arr=(window.MASTER_DATA&&MASTER_DATA.prices)||[];for(var i=0;i<arr.length;i++)if(arr[i]&&arr[i].ticker)out[arr[i].ticker]=arr[i];window._ctPricesByTicker=out;return out;}
  function liveTickers(){var o={};var inv=(window.MASTER_DATA&&MASTER_DATA.positions&&MASTER_DATA.positions.investments)||[];for(var i=0;i<inv.length;i++)if(inv[i].ticker)o[inv[i].ticker]=true;return o;}
  function liveSectors(){var o={},p=pricesLookup(),t=liveTickers();for(var k in t){var px=p[k];if(px&&px.sector)o[px.sector]=true;}return o;}
  function liveIndustries(){var o={},p=pricesLookup(),t=liveTickers();for(var k in t){var px=p[k];if(px&&px.industry)o[px.industry]=true;}return o;}

  function getPbRec(row){var dk=row.md_v2&&row.md_v2.tests;return(dk&&dk[PB_KEY])||null;}
  function getS2Rec(row){return(row.md_v2&&row.md_v2[STAGE_KEY])||null;}
  function pbRating(row){var r=getPbRec(row);return r?(r.rating||'None'):'None';}
  function pbTest(row,key){var r=getPbRec(row);return!!(r&&r.tests&&r.tests[key]);}
  function s2Rating(row){var s=getS2Rec(row);return(s&&s.rating)||'None';}
  function s2Gate(row,key){var s=getS2Rec(row);return!!(s&&s.gates&&s.gates[key]);}
  function s2Test(row,key){var s=getS2Rec(row);return!!(s&&s.tests&&s.tests[key]);}

  function getRows(){
    var raw=(window.MASTER_DATA&&MASTER_DATA.filters)||[];
    var prices=pricesLookup();var live=liveTickers(),liveS=liveSectors(),liveI=liveIndustries();
    var rows=[];
    for(var i=0;i<raw.length;i++){
      var s=raw[i];if(!s||!s.md_v2||!s.md_v2.tests)continue;
      var rec=s.md_v2.tests[PB_KEY];if(!rec)continue;
      var p=prices[s.ticker]||{};
      rows.push({ticker:s.ticker,company:p.company_name||s.ticker,
        sector:p.sector||'',industry:p.industry||'',
        price:p.price,recent_pullback:p.recent_pullback_pct,
        md_v2:s.md_v2,is_live:!!live[s.ticker],
        sector_in_portfolio:!!liveS[p.sector],
        industry_in_portfolio:!!liveI[p.industry]});
    }
    return rows;
  }

  function fmtNum(n){if(n==null||isNaN(n))return'-';var abs=Math.abs(n),dp=abs>=100?0:(abs>=20?1:2);if(Math.abs(n-Math.round(n))<1e-9)dp=0;var f=abs.toLocaleString('en-GB',{minimumFractionDigits:dp,maximumFractionDigits:dp});return n<0?'('+f+')':f;}
  function colGreen(i){if(i>=0.6)return ACCENT;if(i>=0.25)return'#4CAF50';if(i>=0.05)return'#81C784';if(i<=-0.6)return'#A32D2D';if(i<=-0.25)return'#E24B4A';if(i<=-0.05)return'#F09595';return'#888';}
  function hashColor(lbl,alpha){if(!lbl)return null;var h=0;for(var i=0;i<lbl.length;i++)h=(h*31+lbl.charCodeAt(i))&0xffff;return'hsla('+(h%360)+',35%,55%,'+alpha+')';}
  function portInfo(row){if(row.is_live)return{color:'#1b5e20',bg:'rgba(27,94,32,0.10)',bgHover:'rgba(27,94,32,0.14)'};if(row.sector_in_portfolio)return{color:'#1b5e20',bg:'rgba(27,94,32,0.05)',bgHover:'rgba(27,94,32,0.08)'};if(row.industry_in_portfolio)return{color:'#1b5e20',bg:'rgba(27,94,32,0.025)',bgHover:'rgba(27,94,32,0.05)'};return null;}

  function pullbackCell(row,cls){var v=row.recent_pullback;if(v==null||isNaN(v))return'<td class="num '+(cls||'')+'">-</td>';var pv=v*100,i=Math.max(-1,Math.min(1,(pv-5)/20));return'<td class="num '+(cls||'')+'" style="color:'+colGreen(-i)+'">'+Math.round(pv)+'%</td>';}
  function s2RatingCell(row,cls){var r=s2Rating(row);var pc=r==='Probable'?'s2ctx-pill-prob':r==='Plausible'?'s2ctx-pill-pla':r==='Possible'?'s2ctx-pill-pos':'s2ctx-pill-none';return'<td class="'+(cls||'')+'"><span class="'+CTX_PILL_CLS+' '+pc+'">'+r+'</span></td>';}
  function s2GateCell(row,key,cls){var p=s2Gate(row,key);return p?'<td class="'+CTX_PASS_CLS+' '+(cls||'')+'"><span class="tick">&#10003;</span></td>':'<td class="'+CTX_FAIL_CLS+' '+(cls||'')+'">.</td>';}
  function s2TestCell(row,key,cls){var p=s2Test(row,key);return p?'<td class="'+CTX_PASS_CLS+' '+(cls||'')+'"><span class="tick">&#10003;</span></td>':'<td class="'+CTX_FAIL_CLS+' '+(cls||'')+'">.</td>';}
  function pbRatingCell(row,cls){var r=pbRating(row);var rc=TIER_CLS[r]||'tint-none';return'<td class="'+(cls||'')+' pi-rating-cell '+rc+'"><span class="pi-pill pi-pill-'+rc+'">'+r+'</span></td>';}
  function pbScoreCell(row,cls){var rec=getPbRec(row);var cnt=rec?(rec.count||0):0,tot=rec?(rec.total||0):0;var s='';for(var i=0;i<tot;i++)s+='<span class="pip '+(i<cnt?'on':'')+'"></span>';return'<td class="'+(cls||'')+' pi-score-cell"><div class="pi-pip-row">'+s+'<span class="pi-score-num">'+cnt+'/'+tot+'</span></div></td>';}
  function pbTestCell(row,key,cls){var p=pbTest(row,key);return p?'<td class="pi-pass '+(cls||'')+'"><span class="tick">&#10003;</span></td>':'<td class="pi-fail '+(cls||'')+'">.</td>';}
  function windowCell(row,wk,cls){var rec=getPbRec(row);var ex=cls||'';if(!rec)return'<td class="'+ex+' ct-window-none">-</td>';var d=rec.history_depth||0,wd=wk==='l5d'?5:20;if(d<wd)return'<td class="'+ex+' ct-window-building" title="'+d+' of '+wd+' days">building</td>';var fired=wk==='l5d'?!!rec.fired_l5d:!!rec.fired_l20d;if(!fired)return'<td class="'+ex+' ct-window-none">-</td>';var ds=rec.days_since_fired;var lbl=ds===0?'today':ds===1?'1d ago':(ds!=null?ds+'d ago':'fired');var sc=(ds!=null&&ds<=5)?'ct-window-fired-recent':'ct-window-fired-older';return'<td class="'+ex+' '+sc+'"><span class="ct-window-label">'+lbl+'</span></td>';}
  function rdsCell(row,cls){var idx=window.RDS_INDEX||{};var dt=idx[row.ticker];var ex=cls||'';if(!dt)return'<td class="rds-cell rds-none '+ex+'">-</td>';var parts=dt.split('-');var mon=['','Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];var label=(parts[2]||'??')+'-'+(mon[parseInt(parts[1]||0,10)]||parts[1]||'??');var url='https://vfhqi.github.io/repository/#'+encodeURIComponent(row.ticker);var dDays=Math.round((Date.now()-new Date(dt).getTime())/(86400000));var ageCls=dDays<=21?'rds-recent':'rds-older';return'<td class="rds-cell '+ageCls+' '+ex+'"><a href="'+url+'" target="_blank" title="Open '+row.ticker+' in repository">'+label+'</a></td>';}

  function tierCounts(rows){var c={};for(var i=0;i<TIERS.length;i++)c[TIERS[i]]=0;for(var j=0;j<rows.length;j++){var r=pbRating(rows[j]);if(c[r]!=null)c[r]++;}return c;}
  function passHistogram(rows){var h=[];for(var k=0;k<=6;k++)h[k]=0;for(var i=0;i<rows.length;i++){var r=getPbRec(rows[i]);var cnt=r?(r.count||0):0;if(cnt>=0&&cnt<=6)h[cnt]++;}return h;}

  function updateScopeCounts(rows){function s(id,n){var e=document.getElementById(id);if(e)e.textContent='('+n+')';}s('pbs2-cnt-all',rows.length);s('pbs2-cnt-live',rows.filter(function(r){return r.is_live;}).length);s('pbs2-cnt-sector',rows.filter(function(r){return r.sector_in_portfolio;}).length);s('pbs2-cnt-industry',rows.filter(function(r){return r.industry_in_portfolio;}).length);}
  function applyScope(all){var rows=all.slice();if(pbs2State.scope==='live')rows=rows.filter(function(r){return r.is_live;});else if(pbs2State.scope==='sector')rows=rows.filter(function(r){return r.sector_in_portfolio;});else if(pbs2State.scope==='industry')rows=rows.filter(function(r){return r.industry_in_portfolio;});return rows;}
  function applyTierFilter(rows){var sel=pbs2State.tierFilter||[];if(!sel||sel.length===0)return rows;return rows.filter(function(r){return sel.indexOf(pbRating(r))>-1;});}

  function getSortVal(row,key){
    if(key==='company')return row.company||'';if(key==='sector')return row.sector||'';
    if(key==='price')return row.price||0;if(key==='recent_pullback')return row.recent_pullback==null?-Infinity:row.recent_pullback;
    if(key==='pb__rating')return TIER_RANK[pbRating(row)]||0;
    if(key==='pb__score'){var r=getPbRec(row);return r?(r.count||0):0;}
    if(key==='s2__rating')return TIER_RANK[s2Rating(row)]||0;
    if(key.indexOf('s2g__')===0)return s2Gate(row,key.slice(5))?1:0;
    if(key.indexOf('s2t__')===0)return s2Test(row,key.slice(5))?1:0;
    if(key.indexOf('pb__')===0){var tk=key.slice(4);if(tk==='l5d'||tk==='l20d'){var rec=getPbRec(row);if(!rec)return-1;var wd=tk==='l5d'?5:20;if((rec.history_depth||0)<wd)return-2;var fired=tk==='l5d'?rec.fired_l5d:rec.fired_l20d;if(!fired)return-1;var ds=rec.days_since_fired;return ds==null?0:1000-ds;}return pbTest(row,tk)?1:0;}
    if(key==='rds__date'){var idx=window.RDS_INDEX||{};return idx[row.ticker]||'';}
    return 0;
  }
  function onSort(key){if(pbs2State.sort.col===key)pbs2State.sort.dir=pbs2State.sort.dir==='desc'?'asc':'desc';else pbs2State.sort={col:key,dir:key==='company'?'asc':'desc'};buildHeader();renderRows();}

  function buildHeader(){
    var tr=document.getElementById('pbs2-col-header');if(!tr)return;
    var LABELS={
      name:'Company - Ticker',taxon:'Industry - Sector',price:'Price',pullback:'Pullback',
      s2rating:'S2 Rating',
      s2g0:S2_GATE_DEFS[0].label,s2g1:S2_GATE_DEFS[1].label,s2g2:S2_GATE_DEFS[2].label,s2g3:S2_GATE_DEFS[3].label,
      s2t0:S2_TEST_DEFS[0].label,s2t1:S2_TEST_DEFS[1].label,s2t2:S2_TEST_DEFS[2].label,s2t3:S2_TEST_DEFS[3].label,s2t4:S2_TEST_DEFS[4].label,
      pbrating:'Rating',pbscore:'Score',
      g1:'1. Gate: stage',g2:'2. 5D rising',g3:'3. 10D rising',g4:'4. P&gt;20D',
      g5:'5. 20D turned up',g6:'6. Close 2%+',
      l5d:'Fired 5d',l20d:'Fired 20d',rds:'RDS'
    };
    var KEYS={name:'company',taxon:'sector',price:'price',pullback:'recent_pullback',
      s2rating:'s2__rating',
      s2g0:'s2g__'+S2_GATE_DEFS[0].key,s2g1:'s2g__'+S2_GATE_DEFS[1].key,s2g2:'s2g__'+S2_GATE_DEFS[2].key,s2g3:'s2g__'+S2_GATE_DEFS[3].key,
      s2t0:'s2t__'+S2_TEST_DEFS[0].key,s2t1:'s2t__'+S2_TEST_DEFS[1].key,s2t2:'s2t__'+S2_TEST_DEFS[2].key,s2t3:'s2t__'+S2_TEST_DEFS[3].key,s2t4:'s2t__'+S2_TEST_DEFS[4].key,
      pbrating:'pb__rating',pbscore:'pb__score',
      g1:'pb__g1_stage_qualifies',g2:'pb__g2_5d_rising',g3:'pb__g3_10d_rising',g4:'pb__g4_price_gt_20d',
      g5:'pb__g5_20d_turn_last_5d',g6:'pb__g6_followthrough_close_ge2pct',
      l5d:'pb__l5d',l20d:'pb__l20d',rds:'rds__date'};
    var GRP_START={s2rating:'grp-start-g1',pbrating:'grp-start-rating',g1:'grp-start-g2',g5:'grp-start-g3',l5d:'grp-start-context'};
    var TOOLTIPS={s2rating:'Stage 2 rating',
      s2g0:S2_GATE_DEFS[0].tooltip,s2g1:S2_GATE_DEFS[1].tooltip,s2g2:S2_GATE_DEFS[2].tooltip,s2g3:S2_GATE_DEFS[3].tooltip,
      s2t0:S2_TEST_DEFS[0].tooltip,s2t1:S2_TEST_DEFS[1].tooltip,s2t2:S2_TEST_DEFS[2].tooltip,s2t3:S2_TEST_DEFS[3].tooltip,s2t4:S2_TEST_DEFS[4].tooltip,
      pbrating:'PB S2 overall rating',pbscore:'Tests passed out of 6'};
    for(var i=0;i<PB_TESTS.length;i++)TOOLTIPS['g'+(i+1)]=PB_TESTS[i].tooltip;
    var ORDER=['name','taxon','price','pullback','s2rating','s2g0','s2g1','s2g2','s2g3','s2t0','s2t1','s2t2','s2t3','s2t4','pbrating','pbscore','g1','g2','g3','g4','g5','g6','l5d','l20d','rds'];
    var h='';
    for(var ci=0;ci<ORDER.length;ci++){
      var id=ORDER[ci],sk=KEYS[id],isSort=pbs2State.sort.col===sk;
      var arrow=isSort?'<span class="sort-arrow">'+(pbs2State.sort.dir==='desc'?'&#9660;':'&#9650;')+'</span>':'<span class="sort-placeholder"></span>';
      var gc=GRP_START[id]||'';var tt=TOOLTIPS[id]||LABELS[id]||'';
      h+='<th class="'+gc+'" data-sort-key="'+sk+'" title="'+tt+'"><span class="hd"><span class="lbl">'+LABELS[id]+'</span>'+arrow+'</span></th>';
    }
    tr.innerHTML=h;
  }

  function renderTile(scopeRows){
    var el=document.getElementById('pbs2-tile');if(!el)return;
    var tc=tierCounts(scopeRows),total=scopeRows.length,cnt=total-(tc['None']||0);
    var sel=pbs2State.tierFilter||[],anySel=sel.length>0;
    var headline=cnt,headSub='of '+total.toLocaleString('en-GB')+' \xb7 '+Math.round(cnt/Math.max(1,total)*100)+'%';
    if(anySel){var ft=0;for(var z=0;z<sel.length;z++)ft+=(tc[sel[z]]||0);headline=ft;headSub=sel.join(' + ')+' \xb7 filtered';}
    var hist=passHistogram(scopeRows),breakdown='';
    for(var k=1;k<=6;k++){if(k>1)breakdown+=' \xb7 ';breakdown+=k+'/6: '+(hist[k]||0).toLocaleString('en-GB');}
    var chips='';var TIER_DISP=['Possible','Plausible','Probable','Qualified'];
    for(var c=0;c<TIER_DISP.length;c++){var t=TIER_DISP[c];var on=sel.indexOf(t)>-1;chips+='<span class="pi-tier-chip '+CHIP_CLS+(on?' on':'')+'" data-tier="'+t+'">'+t+' '+(tc[t]||0).toLocaleString('en-GB')+(on?' &#10003;':'')+'</span>';}
    el.innerHTML='<div class="rating-tile '+TILE_CLS+(anySel?' active':'')+'">'
      +'<div class="rt-label">S2 Probing Bet</div><div class="rt-count">'+headline.toLocaleString('en-GB')+'</div>'
      +'<div class="rt-sub">'+headSub+'</div><div class="rt-breakdown">'+breakdown+'</div>'
      +'<div class="pi-tier-chips">'+chips+'</div>'
      +'<div class="rt-strip '+STRIP_CLS+'"></div></div>';
    el.addEventListener('click',function(e){var chip=e.target.closest('.pi-tier-chip');if(chip){var t=chip.getAttribute('data-tier');if(t)window.pbs2ToggleTier(t);}});
  }

  function renderRows(){
    var tbody=document.getElementById('pbs2-tbody');if(!tbody)return;
    var all=getRows(),scopeRows=applyScope(all);
    updateScopeCounts(all);renderTile(scopeRows);
    var rows=applyTierFilter(scopeRows);
    rows.sort(function(a,b){var va=getSortVal(a,pbs2State.sort.col),vb=getSortVal(b,pbs2State.sort.col);var cmp=typeof va==='string'?va.localeCompare(vb):(va||0)-(vb||0);if(cmp===0)cmp=a.ticker.localeCompare(b.ticker);return pbs2State.sort.dir==='desc'?-cmp:cmp;});
    var html='';
    for(var i=0;i<rows.length;i++){
      var s=rows[i],styles=[],cls=[];
      if(pbs2State.tint==='industry'){styles.push('--tint-bg: '+hashColor(s.industry,0.16));cls.push('tint-row');}
      else if(pbs2State.tint==='sector'){styles.push('--tint-bg: '+hashColor(s.sector,0.16));cls.push('tint-row');}
      if(pbs2State.port==='on'){var pi=portInfo(s);if(pi){styles.push('--portfolio-color:'+pi.color,'--portfolio-bg:'+pi.bg,'--portfolio-bg-hover:'+pi.bgHover);cls.push('portfolio-band','portfolio-tint');}}
      var sa=styles.length?' style="'+styles.join(';')+'"':'';var ca=cls.length?' class="'+cls.join(' ')+'"':'';
      var ld=s.is_live?'<span class="live-dot">&#9679;</span>':'';
      html+='<tr'+ca+sa+'>'
        +'<td class="name-cell"><div class="co">'+ld+(s.company||s.ticker)+'</div><div class="tk">'+s.ticker+'</div></td>'
        +'<td class="taxon"><div class="ind">'+(s.industry||'')+'</div><div class="sec">'+(s.sector||'')+'</div></td>'
        +'<td class="num">'+fmtNum(s.price)+'</td>'
        +pullbackCell(s,'')
        +s2RatingCell(s,'grp-start-g1')
        +s2GateCell(s,S2_GATE_DEFS[0].key,'')
        +s2GateCell(s,S2_GATE_DEFS[1].key,'')
        +s2GateCell(s,S2_GATE_DEFS[2].key,'')
        +s2GateCell(s,S2_GATE_DEFS[3].key,'')
        +s2TestCell(s,S2_TEST_DEFS[0].key,'')
        +s2TestCell(s,S2_TEST_DEFS[1].key,'')
        +s2TestCell(s,S2_TEST_DEFS[2].key,'')
        +s2TestCell(s,S2_TEST_DEFS[3].key,'')
        +s2TestCell(s,S2_TEST_DEFS[4].key,'')
        +pbRatingCell(s,'grp-start-rating')
        +pbScoreCell(s,'')
        +pbTestCell(s,'g1_stage_qualifies','grp-start-g2')
        +pbTestCell(s,'g2_5d_rising','')
        +pbTestCell(s,'g3_10d_rising','')
        +pbTestCell(s,'g4_price_gt_20d','')
        +pbTestCell(s,'g5_20d_turn_last_5d','grp-start-g3')
        +pbTestCell(s,'g6_followthrough_close_ge2pct','')
        +windowCell(s,'l5d','ct-window-col grp-start-context')
        +windowCell(s,'l20d','ct-window-col')
        +rdsCell(s,'')
        +'</tr>';
    }
    tbody.innerHTML=html;
  }

  window.pbs2SetScope=function(s){pbs2State.scope=s;var btns=document.querySelectorAll('button[data-pbs2-scope]');for(var i=0;i<btns.length;i++)btns[i].classList.toggle('active',btns[i].getAttribute('data-pbs2-scope')===s);renderRows();};
  window.pbs2SetTint=function(t){pbs2State.tint=t;var btns=document.querySelectorAll('button[data-pbs2-tint]');for(var i=0;i<btns.length;i++)btns[i].classList.toggle('active',btns[i].getAttribute('data-pbs2-tint')===t);renderRows();};
  window.pbs2SetPort=function(p){pbs2State.port=p;var btns=document.querySelectorAll('button[data-pbs2-port]');for(var i=0;i<btns.length;i++)btns[i].classList.toggle('active',btns[i].getAttribute('data-pbs2-port')===p);renderRows();};
  window.pbs2ToggleTier=function(tier){var sel=pbs2State.tierFilter||[],idx=sel.indexOf(tier);if(idx>-1)sel.splice(idx,1);else sel.push(tier);pbs2State.tierFilter=sel;renderRows();};
  window.pbs2OnSort=function(key){onSort(key);};

  function buildScaffold(){
    var host=document.getElementById('tab-'+TAB_ID);if(!host)return false;
    if(host.querySelector('#'+TABLE_ID))return true;
    var cg='<col class="c-name"><col class="c-taxon"><col class="c-price"><col class="c-pullback">'
      +'<col class="c-ctx-rating">'
      +'<col class="c-ctx-gate"><col class="c-ctx-gate"><col class="c-ctx-gate"><col class="c-ctx-gate">'
      +'<col class="c-ctx-test"><col class="c-ctx-test"><col class="c-ctx-test"><col class="c-ctx-test"><col class="c-ctx-test">'
      +'<col class="c-rating"><col class="c-score">'
      +'<col class="c-test"><col class="c-test"><col class="c-test"><col class="c-test">'
      +'<col class="c-test"><col class="c-test">'
      +'<col class="c-window"><col class="c-window"><col class="c-rds">';
    var grpRow='<th class="gh-inputs" colspan="4">Inputs</th>'
      +'<th class="gh-g1 grp-start-g1" colspan="10">Group 1 — Stage 2 qualifying?</th>'
      +'<th class="gh-rating grp-start-rating" colspan="2">Rating</th>'
      +'<th class="gh-g2 grp-start-g2" colspan="4">Group 2 — Entry setup?</th>'
      +'<th class="gh-g3 grp-start-g3" colspan="2">Group 3 — Trigger?</th>'
      +'<th class="gh-context grp-start-context" colspan="3">Context</th>';
    var subRow='<th colspan="4"></th>'
      +'<th colspan="1">Stage rating</th><th colspan="4">Gates</th><th colspan="5">Tests</th>'
      +'<th colspan="1">Rating</th><th colspan="1">Score</th>'
      +'<th colspan="1">Gate</th><th colspan="3">Setup</th>'
      +'<th colspan="2">Trigger</th>'
      +'<th colspan="2">Fired</th><th colspan="1">RDS</th>';
    var thead='<tr class="group-header-row">'+grpRow+'</tr>'
      +'<tr class="sub-group-row">'+subRow+'</tr>'
      +'<tr class="col-header-row" id="pbs2-col-header"></tr>';
    host.innerHTML=
      '<div class="s1-intro">S2 Probing Bet — a small starter position on a Stage 2 (uptrend) stock that breaks out without first completing a standard pullback or basing pattern. Often event-driven or idiosyncratic. The Stage 2 qualifying group (G1) shows the underlying uptrend state: 4 gates and 5 tests from the Stage 2 screen. Same 6-criterion breakout test as S1 PB: stage gate + 5D/10D MA rising + price above 20D + 20D MA freshly turned up + 2%+ close.</div>'
      +'<div class="controls s1-controls">'
        +'<div class="ctrl-grp"><span class="ctrl-label">Scope</span>'
          +'<button class="toggle-btn active" data-pbs2-scope="all" onclick="pbs2SetScope(\'all\')">All <span id="pbs2-cnt-all"></span></button>'
          +'<button class="toggle-btn" data-pbs2-scope="live" onclick="pbs2SetScope(\'live\')">Live <span id="pbs2-cnt-live"></span></button>'
          +'<button class="toggle-btn" data-pbs2-scope="sector" onclick="pbs2SetScope(\'sector\')">Sectors <span id="pbs2-cnt-sector"></span></button>'
          +'<button class="toggle-btn" data-pbs2-scope="industry" onclick="pbs2SetScope(\'industry\')">Industries <span id="pbs2-cnt-industry"></span></button>'
        +'</div>'
        +'<div class="ctrl-grp"><span class="ctrl-label">Colour by</span>'
          +'<button class="toggle-btn active" data-pbs2-tint="none" onclick="pbs2SetTint(\'none\')">Off</button>'
          +'<button class="toggle-btn" data-pbs2-tint="industry" onclick="pbs2SetTint(\'industry\')">Industry</button>'
          +'<button class="toggle-btn" data-pbs2-tint="sector" onclick="pbs2SetTint(\'sector\')">Sector</button>'
        +'</div>'
        +'<div class="ctrl-grp"><span class="ctrl-label">Portfolio tint</span>'
          +'<button class="toggle-btn active" data-pbs2-port="off" onclick="pbs2SetPort(\'off\')">Off</button>'
          +'<button class="toggle-btn" data-pbs2-port="on" onclick="pbs2SetPort(\'on\')">On</button>'
        +'</div>'
      +'</div>'
      +'<div class="s1-rating-tiles" id="pbs2-tile"></div>'
      +'<div class="table-wrap"><div class="v2-hscroll"><table class="data-table" id="'+TABLE_ID+'"><colgroup>'+cg+'</colgroup><thead>'+thead+'</thead><tbody id="pbs2-tbody"></tbody></table></div></div>';
    var hdr=document.getElementById('pbs2-col-header');
    if(hdr)hdr.addEventListener('click',function(e){var th=e.target.closest('th');if(!th)return;var k=th.getAttribute('data-sort-key');if(k)pbs2OnSort(k);});
    return true;
  }

  function renderProbingBetS2(){if(!buildScaffold())return;buildHeader();renderRows();if(window.measureV2Ribbon)measureV2Ribbon();}
  window.renderProbingBetS2=renderProbingBetS2;
})();
/* MD-V2-S59-TAB-PB-SPLIT-MARKER-MODULE-END */




</script>
<style>
/* MD-V2-S47-TAB-SPECULATIVE-BET-MARKER-CSS-START */
/* Speculative Bets (S3+S4) — two 6-criterion test variants on one tab (S47) */
#tab-tests_speculative_bet .group-captions { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin: 16px 0 14px 0; }
#tab-tests_speculative_bet .group-captions .gcap { background: #fbfaf5; border: 1px solid #e0dcc8; border-left: 3px solid #c62828; border-radius: 4px; padding: 10px 12px; font-size: 11px; line-height: 1.45; color: #555; }
#tab-tests_speculative_bet .group-captions .gcap b { display: block; margin-bottom: 4px; font-weight: 700; color: #c62828; font-size: 11px; letter-spacing: 0.2px; }
#tab-tests_speculative_bet .group-captions .gcap-g1 { border-left-color: #c62828; }
#tab-tests_speculative_bet .group-captions .gcap-g1 b { color: #c62828; }
#tab-tests_speculative_bet .group-captions .gcap-g2 { border-left-color: #e65100; }
#tab-tests_speculative_bet .group-captions .gcap-g2 b { color: #e65100; }
#tab-tests_speculative_bet .s1-rating-tiles { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }
#tab-tests_speculative_bet .s1-rating-tiles .pi-tile-s3 { background: rgba(198,40,40,0.10); border: 1px solid rgba(198,40,40,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
#tab-tests_speculative_bet .s1-rating-tiles .pi-tile-s3.active { background: rgba(198,40,40,0.22); border: 1.5px solid #c62828; }
#tab-tests_speculative_bet .s1-rating-tiles .pi-strip-s3 { background: #c62828; height: 4px; margin-top: 6px; border-radius: 2px; }
#tab-tests_speculative_bet .s1-rating-tiles .pi-tile-s4 { background: rgba(230,81,0,0.10); border: 1px solid rgba(230,81,0,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
#tab-tests_speculative_bet .s1-rating-tiles .pi-tile-s4.active { background: rgba(230,81,0,0.22); border: 1.5px solid #e65100; }
#tab-tests_speculative_bet .s1-rating-tiles .pi-strip-s4 { background: #e65100; height: 4px; margin-top: 6px; border-radius: 2px; }
#tab-tests_speculative_bet .s1-rating-tiles .rt-breakdown { font-size: 9px; color: #888; margin-top: 4px; line-height: 1.35; }
#tab-tests_speculative_bet .pi-tier-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 7px; }
#tab-tests_speculative_bet .pi-tier-chip { font-size: 10px; padding: 2px 6px; border-radius: 4px; cursor: pointer; user-select: none; border: 0.5px solid; line-height: 1.4; white-space: nowrap; transition: background 0.12s, color 0.12s; }
#tab-tests_speculative_bet .pi-chip-s3 { background: #FFEBEE; color: #c62828; border-color: #EF9A9A; }
#tab-tests_speculative_bet .pi-chip-s3.on { background: #c62828; color: #fff; border-color: #c62828; font-weight: 500; }
#tab-tests_speculative_bet .pi-chip-s4 { background: #FFF3E0; color: #e65100; border-color: #FFCC80; }
#tab-tests_speculative_bet .pi-chip-s4.on { background: #e65100; color: #fff; border-color: #e65100; font-weight: 500; }
#tab-tests_speculative_bet .pi-tier-chip:hover { filter: brightness(0.96); }
/* Table styles — clone pb-main-table with red/amber accent */
#sb-main-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 11px; table-layout: fixed; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }
#sb-main-table thead { position: sticky; top: 0; z-index: 50; background: #fbfaf5; box-shadow: 0 2px 4px rgba(0,0,0,0.06); }
#sb-main-table thead th { background: #fbfaf5 !important; border-bottom: 1px solid #e0dcc8; padding: 7px 3px; text-align: center; font-weight: 600; font-size: 10px; color: #666; cursor: pointer; user-select: none; line-height: 1.25; vertical-align: middle; }
#sb-main-table thead th:hover { background: #f0ebd9 !important; }
#sb-main-table thead .group-header-row th { background: #f3efe2 !important; font-size: 9.5px; text-transform: none; font-weight: 700; letter-spacing: 0.2px; padding: 5px 3px; cursor: default; line-height: 1.25; }
#sb-main-table thead tr.group-header-row th { position: sticky; top: 0; }
#sb-main-table thead tr.sub-group-row th { position: sticky; top: 24px; font-size: 9px; text-transform: uppercase; letter-spacing: 0.3px; color: #888; padding: 3px; font-weight: 600; background: #f8f6ee !important; border-bottom: 1px solid #e0dcc8; }
#sb-main-table thead tr.col-header-row th { position: sticky; top: 44px; border-top: 1px solid #e0dcc8; }
#sb-main-table thead .gh-inputs { color: #555; }
#sb-main-table thead .gh-stageinfo { color: #7a6a3a; }
#sb-main-table thead .gh-g1 { color: #c62828; }
#sb-main-table thead .gh-g2 { color: #e65100; }
#sb-main-table .hd { display: inline-flex; align-items: center; justify-content: center; gap: 3px; width: 100%; }
#sb-main-table .hd .lbl { white-space: normal; word-break: break-word; }
#sb-main-table .hd .sort-arrow { font-size: 9px; color: #c62828; flex: 0 0 auto; line-height: 1; }
#sb-main-table .hd .sort-placeholder { width: 9px; flex: 0 0 auto; }
#sb-main-table td { padding: 5px 4px; border-bottom: 1px solid #efece0; text-align: center; vertical-align: middle; height: 38px; box-sizing: border-box; font-variant-numeric: tabular-nums; }
#sb-main-table tr:hover { background: rgba(198,40,40,0.05); }
#sb-main-table td.grp-start-stageinfo, #sb-main-table th.grp-start-stageinfo { border-left: 2px solid rgba(122,106,58,0.40); }
#sb-main-table td.grp-start-g1, #sb-main-table th.grp-start-g1 { border-left: 2px solid rgba(198,40,40,0.40); }
#sb-main-table td.grp-start-g2, #sb-main-table th.grp-start-g2 { border-left: 2px solid rgba(230,81,0,0.40); }
#sb-main-table td.pi-pass { background: rgba(198,40,40,0.12); color: #c62828; font-weight: 700; }
#sb-main-table td.pi-fail { color: #999; }
#sb-main-table td.pi-rating-cell { padding: 3px 4px; }
#sb-main-table .pi-pill { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 9px; font-weight: 700; line-height: 1.3; white-space: nowrap; }
#sb-main-table .pi-pill-tint-qualified { background: #7f1d1d; color: #fff; }
#sb-main-table .pi-pill-tint-prob { background: #c62828; color: #fff; }
#sb-main-table .pi-pill-tint-pla  { background: rgba(198,40,40,0.30); color: #7f1d1d; }
#sb-main-table .pi-pill-tint-pos  { background: rgba(198,40,40,0.14); color: #8a5a5a; }
#sb-main-table .pi-pill-tint-none { background: #ece9dd; color: #999; }
#sb-main-table td.pi-score-cell { padding: 4px 3px; }
#sb-main-table .pi-pip-row { display: inline-flex; align-items: center; gap: 2px; justify-content: center; }
#sb-main-table .pi-pip-row .pip { width: 6px; height: 6px; border-radius: 50%; background: #d8d4c4; display: inline-block; }
#sb-main-table .pi-pip-row .pip.on { background: #c62828; }
#sb-main-table .pi-pip-row .pi-score-num { font-size: 9px; color: #777; margin-left: 3px; font-weight: 600; }
#sb-main-table td.ct-stage-info-cell { padding: 3px 4px; }
#sb-main-table .ct-info-label { display: inline-block; padding: 2px 5px; border-radius: 3px; font-size: 9px; font-weight: 600; line-height: 1.3; white-space: nowrap; }
#sb-main-table td.ct-stage-info-cell.tint-prob .ct-info-label { background: rgba(198,40,40,0.22); color: #7f1d1d; }
#sb-main-table td.ct-stage-info-cell.tint-pla  .ct-info-label { background: rgba(198,40,40,0.13); color: #8a5a5a; }
#sb-main-table td.ct-stage-info-cell.tint-pos  .ct-info-label { background: rgba(198,40,40,0.07); color: #6a7a72; }
#sb-main-table td.ct-stage-info-cell.tint-none .ct-info-label { background: #f0ede1; color: #aaa; }
#sb-main-table td.ct-window-col { padding: 3px 4px; font-size: 10px; }
#sb-main-table td.ct-window-fired-recent { background: rgba(198,40,40,0.16); }
#sb-main-table td.ct-window-fired-recent .ct-window-label { color: #7f1d1d; font-weight: 700; }
#sb-main-table td.ct-window-fired-older { background: rgba(186,117,23,0.14); }
#sb-main-table td.ct-window-fired-older .ct-window-label { color: #7a4e0a; font-weight: 600; }
#sb-main-table td.ct-window-none { color: #bbb; }
#sb-main-table td.ct-window-building { color: #b59a5a; font-style: italic; font-size: 9px; }
#sb-main-table td.name-cell { text-align: left; padding: 4px 4px 4px 8px; line-height: 1.15; }
#sb-main-table td.name-cell .co { font-weight: 700; font-size: 11px; color: #2a2a2a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#sb-main-table td.name-cell .tk { font-size: 9px; color: #999; font-weight: 500; margin-top: 1px; }
#sb-main-table td.name-cell .live-dot { color: #2e7d32; font-weight: 700; margin-right: 4px; }
#sb-main-table td.taxon { text-align: left; font-size: 9px; line-height: 1.2; padding: 4px; }
#sb-main-table td.taxon .ind { color: #666; font-weight: 500; }
#sb-main-table td.taxon .sec { color: #999; }
#sb-main-table col.c-name { width: 124px; }
#sb-main-table col.c-taxon { width: 150px; }
#sb-main-table col.c-price { width: 50px; }
#sb-main-table col.c-52wh { width: 48px; }
#sb-main-table col.c-52wl { width: 48px; }
#sb-main-table col.c-ma150 { width: 48px; }
#sb-main-table col.c-ma200 { width: 48px; }
#sb-main-table col.c-pullback { width: 58px; }
#sb-main-table col.c-stageinfo { width: 56px; }
#sb-main-table col.c-rating { width: 64px; }
#sb-main-table col.c-score { width: 52px; }
#sb-main-table col.c-test { width: 64px; }
#sb-main-table col.c-window { width: 52px; }
#sb-main-table tr.tint-row td.name-cell, #sb-main-table tr.tint-row td.taxon { background: var(--tint-bg) !important; }
#sb-main-table tr.portfolio-band td:last-child { border-right: 4px solid var(--portfolio-color); }
#sb-main-table tr.portfolio-tint { background: var(--portfolio-bg); }
#sb-main-table tr.portfolio-tint:hover { background: var(--portfolio-bg-hover); }
/* MD-V2-S47-TAB-SPECULATIVE-BET-MARKER-CSS-END */
</style>
<script>
/* MD-V2-S47C-CSS-ESCAPE-MARKER (19-May-26): live SyntaxError hotfix — wrapped 3 Task-2 CSS blocks in <style> elements. */


/* MD-V2-S47-TAB-SPECULATIVE-BET-MARKER-MODULE-START */
// =============================================================================
// SPECULATIVE BETS (S3+S4) — TAB MODULE (S47)
// =============================================================================
// MD-V2-S47-TAB-SPECULATIVE-BET-MARKER
// Two 6-criterion test variants on one tab:
//   speculative_bet_s3: Stage 3 topping/declining + breakout => speculative short-side or contrarian bet
//   speculative_bet_s4: Stage 4 declining/basing + breakout => speculative early turnaround bet
// =============================================================================

(function() {
  'use strict';

  var SB_PATTERNS = [
    {
      key: 'speculative_bet_s3',
      label: 'Stage 3 topping/declining trend + breakout ⇒ S3 speculative bet',
      shortLabel: 'S3 Speculative',
      tone: 's3',
      tierLadder: ['Possible', 'Plausible', 'Probable', 'Qualified'],
      total: 6,
      tooltip: 'A breakout on a Stage 3 (topping/early decline) stock — a speculative position, often contrarian or short-side.',
      caption: '<span class="db">A positive breakout on a Stage 3 stock.</span> The 5D and 10D MAs must be rising. Price must be above the 20D MA, and the 20D MA must have turned up in the last 5 days. Confirmation requires a close 2%+ above yesterday. Stage 3 context makes this inherently speculative.',
      tests: [
        { key: 'g1_stage_qualifies',            label: 'Stage 3 qualifies',    group: 'gate',    tooltip: 'Stage 3 rating is Probable or Plausible — hard precondition' },
        { key: 'g2_5d_rising',                   label: '5D MA rising',         group: 'setup',   tooltip: '5-day moving average is rising day-over-day' },
        { key: 'g3_10d_rising',                  label: '10D MA rising',        group: 'setup',   tooltip: '10-day moving average is rising day-over-day' },
        { key: 'g4_price_gt_20d',                label: 'Price > 20D MA',       group: 'trigger', tooltip: 'Current price is above the 20-day moving average' },
        { key: 'g5_20d_turn_last_5d',            label: '20D MA turned up',     group: 'trigger', tooltip: '20D MA is rising now AND was falling 5 days ago — the turn' },
        { key: 'g6_followthrough_close_ge2pct',  label: 'Confirm: close 2%+',   group: 'trigger', tooltip: 'Today close at least 2% above yesterday — follow-through confirmation' }
      ]
    },
    {
      key: 'speculative_bet_s4',
      label: 'Stage 4 declining/basing trend + breakout ⇒ S4 speculative bet',
      shortLabel: 'S4 Speculative',
      tone: 's4',
      tierLadder: ['Possible', 'Plausible', 'Probable', 'Qualified'],
      total: 6,
      tooltip: 'A breakout on a Stage 4 (declining/bottoming) stock — a speculative early turnaround bet before the stage flips.',
      caption: '<span class="db">A positive breakout on a Stage 4 stock that has not yet transitioned to Stage 1.</span> Same criteria as S3 speculative bet, but the stock is in a confirmed decline or bottoming phase. These are the highest-risk bets — the trend is still against you.',
      tests: [
        { key: 'g1_stage_qualifies',            label: 'Stage 4 qualifies',    group: 'gate',    tooltip: 'Stage 4 rating is Probable or Plausible — hard precondition' },
        { key: 'g2_5d_rising',                   label: '5D MA rising',         group: 'setup',   tooltip: '5-day moving average is rising day-over-day' },
        { key: 'g3_10d_rising',                  label: '10D MA rising',        group: 'setup',   tooltip: '10-day moving average is rising day-over-day' },
        { key: 'g4_price_gt_20d',                label: 'Price > 20D MA',       group: 'trigger', tooltip: 'Current price is above the 20-day moving average' },
        { key: 'g5_20d_turn_last_5d',            label: '20D MA turned up',     group: 'trigger', tooltip: '20D MA is rising now AND was falling 5 days ago — the turn' },
        { key: 'g6_followthrough_close_ge2pct',  label: 'Confirm: close 2%+',   group: 'trigger', tooltip: 'Today close at least 2% above yesterday — follow-through confirmation' }
      ]
    }
  ];

  var SB_TONE_TILE  = { s3:'pi-tile-s3', s4:'pi-tile-s4' };
  var SB_TONE_STRIP = { s3:'pi-strip-s3', s4:'pi-strip-s4' };
  var SB_TONE_CHIP  = { s3:'s3', s4:'s4' };

  var sbState = {
    mode: { inputs: 'pct', tests: 'tick' },
    scope: 'all',
    tierFilter: {},
    tint: 'none',
    port: 'off',
    sort: { col: 'company', dir: 'asc' }
  };
  for (var _ip = 0; _ip < SB_PATTERNS.length; _ip++) sbState.tierFilter[SB_PATTERNS[_ip].key] = [];

  var SB_RATING_RANK = { 'Qualified':6, 'Probable':5, 'Plausible':3, 'Possible':2, 'None':1 };
  var SB_RATING_CLS  = { 'Qualified':'tint-qualified', 'Probable':'tint-prob', 'Plausible':'tint-pla', 'Possible':'tint-pos', 'None':'tint-none' };

  // --- data lookups ---
  function sbPricesLookup() {
    if (window._ctPricesByTicker) return window._ctPricesByTicker;
    var out = {};
    var arr = (window.MASTER_DATA && MASTER_DATA.prices) || [];
    for (var i = 0; i < arr.length; i++) if (arr[i] && arr[i].ticker) out[arr[i].ticker] = arr[i];
    window._ctPricesByTicker = out;
    return out;
  }
  function sbLiveTickers() { var o = {}; var inv = (window.MASTER_DATA && MASTER_DATA.positions && MASTER_DATA.positions.investments) || []; for (var i = 0; i < inv.length; i++) if (inv[i].ticker) o[inv[i].ticker] = true; return o; }
  function sbLiveSectors() { var o = {}, p = sbPricesLookup(), t = sbLiveTickers(); for (var k in t) { var px = p[k]; if (px && px.sector) o[px.sector] = true; } return o; }
  function sbLiveIndustries() { var o = {}, p = sbPricesLookup(), t = sbLiveTickers(); for (var k in t) { var px = p[k]; if (px && px.industry) o[px.industry] = true; } return o; }
  function sbPatternRec(row, patternKey) { var dk = row.md_v2 && row.md_v2.tests; return (dk && dk[patternKey]) || null; }
  function sbEvalTest(row, patternKey, testKey) { var rec = sbPatternRec(row, patternKey); if (!rec || !rec.tests) return false; return !!rec.tests[testKey]; }
  function sbRowRating(row, patternKey) { var rec = sbPatternRec(row, patternKey); return rec ? (rec.rating || 'None') : 'None'; }
  function sbStageRating(row, stageKey) { var md = row.md_v2 || {}; var st = md[stageKey]; return (st && st.rating) || 'None'; }
  function sbGetRows() {
    var raw = (window.MASTER_DATA && MASTER_DATA.filters) || [];
    var prices = sbPricesLookup();
    var live = sbLiveTickers(), liveS = sbLiveSectors(), liveI = sbLiveIndustries();
    var rows = [];
    for (var i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || !s.md_v2 || !s.md_v2.tests) continue;
      var p = prices[s.ticker] || {};
      var mas = p.mas || {};
      rows.push({
        ticker: s.ticker, company: p.company_name || s.ticker,
        sector: p.sector || '', industry: p.industry || '',
        price: p.price, high_52w: p.high_52w, low_52w: p.low_52w,
        recent_pullback: p.recent_pullback_pct,
        ma_150: mas['150D'], ma_200: mas['200D'],
        md_v2: s.md_v2,
        is_live: !!live[s.ticker],
        sector_in_portfolio: !!liveS[p.sector],
        industry_in_portfolio: !!liveI[p.industry]
      });
    }
    return rows;
  }

  // --- counts ---
  function sbTierCounts(rows, patternKey) { var c = { 'Qualified':0, 'Probable':0, 'Plausible':0, 'Possible':0, 'None':0 }; for (var i = 0; i < rows.length; i++) { var r = sbRowRating(rows[i], patternKey); if (c[r] != null) c[r]++; } return c; }
  function sbPassHistogram(rows, patternKey) { var h = []; for (var k = 0; k <= 6; k++) h[k] = 0; for (var i = 0; i < rows.length; i++) { var rec = sbPatternRec(rows[i], patternKey); var cnt = rec ? (rec.count || 0) : 0; if (cnt >= 0 && cnt <= 6) h[cnt]++; } return h; }

  // --- formatting helpers ---
  function sbFmtNum(n) { if (n == null || isNaN(n)) return '-'; var abs = Math.abs(n); var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2); if (Math.abs(n - Math.round(n)) < 1e-9) dp = 0; var f = abs.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp }); return n < 0 ? '(' + f + ')' : f; }
  function sbFmtPct(p) { if (p == null || isNaN(p)) return '-'; var r = Math.round(p), abs = Math.abs(r); return r < 0 ? '(' + abs + ')%' : r + '%'; }
  function sbColourForIntensity(i) { if (i >= 0.6) return '#c62828'; if (i >= 0.25) return '#e65100'; if (i >= 0.05) return '#ff8a65'; if (i <= -0.6) return '#A32D2D'; if (i <= -0.25) return '#E24B4A'; if (i <= -0.05) return '#F09595'; return '#888'; }
  function sbInputCell(row, key, extraCls) {
    extraCls = extraCls || '';
    var v = row[key];
    if (key === 'price') return '<td class="num ' + extraCls + '">' + sbFmtNum(v) + '</td>';
    if (key === 'recent_pullback') { if (v == null || isNaN(v)) return '<td class="num ' + extraCls + '">-</td>'; var pctVal = v * 100; var pi_i = Math.max(-1, Math.min(1, (pctVal - 5) / 20)); return '<td class="num ' + extraCls + '" style="color:' + sbColourForIntensity(-pi_i) + '">' + Math.round(pctVal) + '%</td>'; }
    if (v == null || row.price == null) return '<td class="num ' + extraCls + '">-</td>';
    var pct = (row.price - v) / v * 100;
    var intensity = 0;
    if (key === 'high_52w') intensity = Math.max(-1, Math.min(1, (-pct - 5) / 20));
    else if (key === 'low_52w') intensity = Math.max(-1, Math.min(1, (pct - 20) / 30));
    else if (key === 'ma_150' || key === 'ma_200') intensity = Math.max(-1, Math.min(1, pct / 10));
    var text = (sbState.mode.inputs === 'pct') ? sbFmtPct(pct) : sbFmtNum(v);
    return '<td class="num ' + extraCls + '" style="color:' + sbColourForIntensity(intensity) + '">' + text + '</td>';
  }
  function sbStageInfoCell(row, stageKey, cls) { var rating = sbStageRating(row, stageKey); var rcls = SB_RATING_CLS[rating] || (rating.indexOf('Probable') === 0 ? 'tint-prob' : rating.indexOf('Plausible') === 0 ? 'tint-pla' : rating.indexOf('Possible') === 0 ? 'tint-pos' : 'tint-none'); return '<td class="' + (cls || '') + ' ct-stage-info-cell ' + rcls + '"><span class="ct-info-label">' + rating + '</span></td>'; }
  function sbTestValueFor(row, patternKey, testKey) { var rec = sbPatternRec(row, patternKey); var tv = rec && rec.test_values; if (!tv || !(testKey in tv)) return '—'; var v = tv[testKey]; if (v === null || v === undefined) return '—'; if (typeof v === 'string') return v; if (typeof v === 'number') { if (isNaN(v)) return '—'; if (Math.abs(v) <= 1.5 && v !== Math.round(v)) return sbFmtPct(v * 100); return sbFmtNum(v); } return String(v); }
  function sbTestCell(row, patternKey, testKey, cls) {
    var pass = sbEvalTest(row, patternKey, testKey);
    var extra = cls || '';
    if (sbState.mode.tests === 'val') { var v = sbTestValueFor(row, patternKey, testKey); var colour = pass ? sbColourForIntensity(0.7) : sbColourForIntensity(-0.4); return '<td class="test-val pi-' + (pass ? 'pass' : 'fail') + ' ' + extra + '" style="color:' + colour + '">' + v + '</td>'; }
    if (pass) return '<td class="pi-pass ' + extra + '"><span class="tick">' + String.fromCharCode(10003) + '</span></td>';
    return '<td class="pi-fail ' + extra + '">.</td>';
  }
  function sbRatingCell(row, patternKey, cls) { var rating = sbRowRating(row, patternKey); var rcls = SB_RATING_CLS[rating] || 'tint-none'; return '<td class="' + (cls || '') + ' pi-rating-cell ' + rcls + '"><span class="pi-pill pi-pill-' + rcls + '">' + rating + '</span></td>'; }
  function sbScoreCell(row, patternKey, cls) { var rec = sbPatternRec(row, patternKey); var cnt = rec ? (rec.count || 0) : 0; var tot = rec ? (rec.total || 0) : 0; var s = ''; for (var i = 0; i < tot; i++) s += '<span class="pip ' + (i < cnt ? 'on' : '') + '"></span>'; return '<td class="' + (cls || '') + ' pi-score-cell"><div class="pi-pip-row">' + s + '<span class="pi-score-num">' + cnt + '/' + tot + '</span></div></td>'; }
  function sbWindowCell(row, patternKey, windowKey, cls) { var rec = sbPatternRec(row, patternKey); var extra = cls || ''; if (!rec) return '<td class="' + extra + ' ct-window-na">-</td>'; var depth = rec.history_depth || 0; var windowDays = (windowKey === 'l5d') ? 5 : 20; if (depth < windowDays) return '<td class="' + extra + ' ct-window-building" title="' + depth + ' of ' + windowDays + ' days of history accumulated">building</td>'; var fired = (windowKey === 'l5d') ? !!rec.fired_l5d : !!rec.fired_l20d; if (!fired) return '<td class="' + extra + ' ct-window-none">-</td>'; var ds = rec.days_since_fired; var label; if (ds === 0) label = 'today'; else if (ds === 1) label = '1d ago'; else if (ds != null) label = ds + 'd ago'; else label = 'fired'; var shadeCls = (ds != null && ds <= 5) ? 'ct-window-fired-recent' : 'ct-window-fired-older'; return '<td class="' + extra + ' ' + shadeCls + '"><span class="ct-window-label">' + label + '</span></td>'; }
  function sbHashColor(label, alpha) { if (!label) return null; var h = 0; for (var i = 0; i < label.length; i++) h = (h * 31 + label.charCodeAt(i)) & 0xffff; return 'hsla(' + (h % 360) + ', 35%, 55%, ' + alpha + ')'; }
  function sbPortfolioInfo(row) { if (row.is_live) return { color:'#1b5e20', bg:'rgba(27,94,32,0.10)', bgHover:'rgba(27,94,32,0.14)' }; if (row.sector_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.05)', bgHover:'rgba(27,94,32,0.08)' }; if (row.industry_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.025)', bgHover:'rgba(27,94,32,0.05)' }; return null; }

  // --- column model ---
  function sbBuildCols() {
    var cols = [
      { id:'name',     sortKey:'company',         kind:'input' },
      { id:'taxon',    sortKey:'sector',           kind:'input' },
      { id:'price',    sortKey:'price',            kind:'input' },
      { id:'high_52w', sortKey:'high_52w',         kind:'input' },
      { id:'low_52w',  sortKey:'low_52w',          kind:'input' },
      { id:'ma_150',   sortKey:'ma_150',           kind:'input' },
      { id:'ma_200',   sortKey:'ma_200',           kind:'input' },
      { id:'pullback', sortKey:'recent_pullback',  kind:'input' }
    ];
    var STAGES = ['stage_1','stage_2','stage_3','stage_4'];
    if (PB_STAGEINFO_COUNT > 0) { for (var si = 0; si < STAGES.length; si++) cols.push({ id:'info_'+STAGES[si], sortKey:'stageinfo__'+STAGES[si], kind:'stageinfo', stageKey:STAGES[si] }); }
    for (var p = 0; p < SB_PATTERNS.length; p++) {
      var pat = SB_PATTERNS[p];
      var gi = p + 1;
      cols.push({ id:'p'+gi+'_rating', sortKey:pat.key+'__rating', kind:'rating', patternKey:pat.key });
      cols.push({ id:'p'+gi+'_score',  sortKey:pat.key+'__score',  kind:'score',  patternKey:pat.key });
      for (var t = 0; t < pat.tests.length; t++) {
        cols.push({ id:'p'+gi+'t'+(t+1), sortKey:pat.key+'__'+pat.tests[t].key, kind:'test', patternKey:pat.key, testKey:pat.tests[t].key, group:pat.tests[t].group, label:pat.tests[t].label, tooltip:pat.tests[t].tooltip });
      }
      cols.push({ id:'p'+gi+'_l5d',  sortKey:pat.key+'__l5d',  kind:'window', patternKey:pat.key, windowKey:'l5d' });
      cols.push({ id:'p'+gi+'_l20d', sortKey:pat.key+'__l20d', kind:'window', patternKey:pat.key, windowKey:'l20d' });
    }
    return cols;
  }
  var SB_COLS = sbBuildCols();
  var SB_INPUT_COUNT = 8;
  var SB_STAGEINFO_COUNT = 4;

  // --- sorting ---
  function sbGetSortVal(row, key) {
    if (key.indexOf('stageinfo__') === 0) { var sk = key.split('__')[1]; return SB_RATING_RANK[sbStageRating(row, sk)] || 0; }
    if (key.indexOf('__') > 0) {
      var parts = key.split('__'); var patKey = parts[0], sub = parts[1];
      var rec = sbPatternRec(row, patKey);
      if (sub === 'rating') return rec ? (SB_RATING_RANK[rec.rating] || 0) : 0;
      if (sub === 'score')  return rec ? (rec.count || 0) : 0;
      if (sub === 'l5d' || sub === 'l20d') { if (!rec) return -1; var wd = (sub === 'l5d') ? 5 : 20; if ((rec.history_depth || 0) < wd) return -2; var fired = (sub === 'l5d') ? rec.fired_l5d : rec.fired_l20d; if (!fired) return -1; var ds = rec.days_since_fired; return (ds == null) ? 0 : (1000 - ds); }
      return sbEvalTest(row, patKey, sub) ? 1 : 0;
    }
    if (key === 'recent_pullback') return row.recent_pullback == null ? -Infinity : row.recent_pullback;
    var PCT_KEYS = ['high_52w','low_52w','ma_150','ma_200'];
    if (PCT_KEYS.indexOf(key) > -1 && sbState.mode.inputs === 'pct') { var ref = row[key]; if (ref == null || row.price == null || ref === 0) return -Infinity; return (row.price - ref) / ref * 100; }
    if (key in row) return row[key];
    return 0;
  }
  function sbOnSort(key) {
    if (sbState.sort.col === key) sbState.sort.dir = sbState.sort.dir === 'desc' ? 'asc' : 'desc';
    else sbState.sort = { col: key, dir: key === 'company' ? 'asc' : 'desc' };
    sbBuildHeaderRow();
    sbRenderRows();
  }
  function sbBuildHeaderRow() {
    var tr = document.getElementById('sb-col-header-row');
    if (!tr) return;
    var INPUT_LABELS = ['Company - Ticker','Industry - Sector','Price','52wk high','52wk low','150D MA','200D MA','Pullback'];
    var STAGE_LABELS = ['Stage 1','Stage 2','Stage 3','Stage 4'];
    var h = '';
    for (var i = 0; i < SB_COLS.length; i++) {
      var c = SB_COLS[i];
      var isSort = sbState.sort.col === c.sortKey;
      var arrow = isSort ? '<span class="sort-arrow">' + (sbState.sort.dir === 'desc' ? String.fromCharCode(9660) : String.fromCharCode(9650)) + '</span>' : '<span class="sort-placeholder"></span>';
      var label, title, cls = '';
      if (c.kind === 'input') { label = INPUT_LABELS[i]; title = label; }
      else if (c.kind === 'stageinfo') { label = STAGE_LABELS[i - SB_INPUT_COUNT]; title = label + ' rating'; cls = (i === SB_INPUT_COUNT ? 'grp-start-stageinfo ' : ''); }
      else if (c.kind === 'rating') { label = 'Rating'; title = c.patternKey + ' rating'; cls = 'grp-start-g' + (SB_PATTERNS.indexOf(SB_PATTERNS.filter(function(p){return p.key===c.patternKey})[0]) + 1) + ' '; }
      else if (c.kind === 'score') { label = 'Score'; title = 'Pass count out of 6'; }
      else if (c.kind === 'test') { label = c.label; title = c.tooltip || c.label; }
      else if (c.kind === 'window') { label = c.windowKey === 'l5d' ? 'Fired 5d' : 'Fired 20d'; title = label; cls = 'ct-window-col'; }
      else { label = '?'; title = ''; }
      h += '<th class="' + cls + '" data-sort-key="' + c.sortKey + '" title="' + title + '"><span class="hd"><span class="lbl">' + label + '</span>' + arrow + '</span></th>';
    }
    tr.innerHTML = h;
  }

  // --- tiles ---
  function sbPatternTiles(scopeRows) {
    var tiles = document.getElementById('sb-pattern-tiles');
    if (!tiles) return;
    var total = scopeRows.length;
    var h = '';
    for (var i = 0; i < SB_PATTERNS.length; i++) {
      var pat = SB_PATTERNS[i];
      var tierCounts = sbTierCounts(scopeRows, pat.key);
      var cnt = total - (tierCounts['None'] || 0);
      var pct = total > 0 ? Math.round(cnt / total * 100) : 0;
      var sel = sbState.tierFilter[pat.key] || [];
      var anySel = sel.length > 0;
      var headline = cnt, headSub = 'of ' + total.toLocaleString('en-GB') + ' · ' + pct + '%';
      if (anySel) { var ft = 0; for (var z = 0; z < sel.length; z++) ft += (tierCounts[sel[z]] || 0); headline = ft; headSub = sel.join(' + ') + ' · filtered'; }
      var hist = sbPassHistogram(scopeRows, pat.key);
      var breakdown = '';
      for (var k = 1; k <= 6; k++) { if (k > 1) breakdown += ' · '; breakdown += k + '/6: ' + (hist[k] || 0).toLocaleString('en-GB'); }
      var chips = '';
      var TIERS = ['Possible','Plausible','Probable','Qualified'];
      for (var c = 0; c < TIERS.length; c++) {
        var tier = TIERS[c]; var on = sel.indexOf(tier) > -1; var tc = tierCounts[tier] || 0;
        chips += '<span class="pi-tier-chip pi-chip-' + SB_TONE_CHIP[pat.tone] + (on ? ' on' : '') + '" data-pattern="' + pat.key + '" data-tier="' + tier + '">' + tier + ' ' + tc.toLocaleString('en-GB') + (on ? ' ' + String.fromCharCode(10003) : '') + '</span>';
      }
      var activeCls = anySel ? ' active' : '';
      h += '<div class="rating-tile ' + SB_TONE_TILE[pat.tone] + activeCls + '" data-pattern="' + pat.key + '" title="' + pat.tooltip + '">' +
           '<div class="rt-label">' + pat.shortLabel + '</div><div class="rt-count">' + headline.toLocaleString('en-GB') + '</div><div class="rt-sub">' + headSub + '</div>' +
           '<div class="rt-breakdown">' + breakdown + '</div><div class="pi-tier-chips" data-pattern="' + pat.key + '">' + chips + '</div>' +
           '<div class="rt-strip ' + SB_TONE_STRIP[pat.tone] + '"></div></div>';
    }
    tiles.innerHTML = h;
  }

  // --- scope / filter ---
  function sbUpdateScopeCounts(rows) { function set(id, n) { var el = document.getElementById(id); if (el) el.textContent = '(' + n + ')'; } set('sb2-cnt-all', rows.length); set('sb2-cnt-live', rows.filter(function(r){return r.is_live}).length); set('sb2-cnt-sector', rows.filter(function(r){return r.sector_in_portfolio}).length); set('sb2-cnt-industry', rows.filter(function(r){return r.industry_in_portfolio}).length); }
  function sbApplyScope(all) { var rows = all.slice(); if (sbState.scope === 'live') rows = rows.filter(function(r){return r.is_live}); else if (sbState.scope === 'sector') rows = rows.filter(function(r){return r.sector_in_portfolio}); else if (sbState.scope === 'industry') rows = rows.filter(function(r){return r.industry_in_portfolio}); return rows; }
  function sbApplyTierFilter(rows) {
    var active = [];
    for (var p = 0; p < SB_PATTERNS.length; p++) { var k = SB_PATTERNS[p].key; var sel = sbState.tierFilter[k] || []; if (sel.length > 0) active.push({ key: k, tiers: sel }); }
    if (active.length === 0) return rows;
    return rows.filter(function(r) { for (var a = 0; a < active.length; a++) { var rating = sbRowRating(r, active[a].key); if (active[a].tiers.indexOf(rating) === -1) return false; } return true; });
  }

  // --- main render ---
  function sbRenderRows() {
    var tbody = document.getElementById('sb-tbody');
    if (!tbody) return;
    var all = sbGetRows();
    var scopeRows = sbApplyScope(all);
    sbUpdateScopeCounts(all);
    sbPatternTiles(scopeRows);
    var rows = sbApplyTierFilter(scopeRows);
    rows.sort(function(a,b) { var va = sbGetSortVal(a, sbState.sort.col), vb = sbGetSortVal(b, sbState.sort.col); var cmp = (typeof va === 'string') ? va.localeCompare(vb) : (va || 0) - (vb || 0); if (cmp === 0) cmp = a.ticker.localeCompare(b.ticker); return sbState.sort.dir === 'desc' ? -cmp : cmp; });
    var STAGES = ['stage_1','stage_2','stage_3','stage_4'];
    var html = '';
    for (var i = 0; i < rows.length; i++) {
      var s = rows[i];
      var styles = [], cls = [];
      if (sbState.tint === 'industry') { styles.push('--tint-bg: ' + sbHashColor(s.industry, 0.16)); cls.push('tint-row'); }
      else if (sbState.tint === 'sector') { styles.push('--tint-bg: ' + sbHashColor(s.sector, 0.16)); cls.push('tint-row'); }
      if (sbState.port === 'on') { var pinf = sbPortfolioInfo(s); if (pinf) { styles.push('--portfolio-color: ' + pinf.color); styles.push('--portfolio-bg: ' + pinf.bg); styles.push('--portfolio-bg-hover: ' + pinf.bgHover); cls.push('portfolio-band'); cls.push('portfolio-tint'); } }
      var styleAttr = styles.length ? ' style="' + styles.join(';') + '"' : '';
      var clsAttr = cls.length ? ' class="' + cls.join(' ') + '"' : '';
      var liveDot = s.is_live ? '<span class="live-dot">' + String.fromCharCode(9679) + '</span>' : '';
      html += '<tr' + clsAttr + styleAttr + '>' +
        '<td class="name-cell"><div class="co">' + liveDot + (s.company || s.ticker) + '</div><div class="tk">' + s.ticker + '</div></td>' +
        '<td class="taxon"><div class="ind">' + (s.industry || '') + '</div><div class="sec">' + (s.sector || '') + '</div></td>' +
        sbInputCell(s, 'price') + sbInputCell(s, 'high_52w') + sbInputCell(s, 'low_52w') + sbInputCell(s, 'ma_150') + sbInputCell(s, 'ma_200') + sbInputCell(s, 'recent_pullback');
      for (var si = 0; si < STAGES.length; si++) html += sbStageInfoCell(s, STAGES[si], si === 0 ? 'grp-start-stageinfo' : '');
      for (var pi = 0; pi < SB_PATTERNS.length; pi++) {
        var pat = SB_PATTERNS[pi];
        var gi = pi + 1;
        html += sbRatingCell(s, pat.key, 'grp-start-g' + gi);
        html += sbScoreCell(s, pat.key, '');
        for (var ti = 0; ti < pat.tests.length; ti++) html += sbTestCell(s, pat.key, pat.tests[ti].key, '');
        html += sbWindowCell(s, pat.key, 'l5d', 'ct-window-col');
        html += sbWindowCell(s, pat.key, 'l20d', 'ct-window-col');
      }
      html += '</tr>';
    }
    tbody.innerHTML = html;
  }

  // --- control setters ---
  window.sb2SetMode = function(kind, val) { sbState.mode[kind] = val; var btns = document.querySelectorAll('button[data-sb2-grp="' + kind + '"]'); for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-sb2-val') === val); sbRenderRows(); };
  window.sb2SetScope = function(s) { sbState.scope = s; var btns = document.querySelectorAll('button[data-sb2-scope]'); for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-sb2-scope') === s); sbRenderRows(); };
  window.sb2SetTint = function(t) { sbState.tint = t; var btns = document.querySelectorAll('button[data-sb2-tint]'); for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-sb2-tint') === t); sbRenderRows(); };
  window.sb2SetPort = function(p) { sbState.port = p; var btns = document.querySelectorAll('button[data-sb2-port]'); for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-sb2-port') === p); sbRenderRows(); };
  window.sb2ToggleTier = function(patternKey, tier) { var sel = sbState.tierFilter[patternKey] || []; var idx = sel.indexOf(tier); if (idx > -1) sel.splice(idx, 1); else sel.push(tier); sbState.tierFilter[patternKey] = sel; sbRenderRows(); };
  window.sb2SelectAllTiers = function(patternKey) { var sel = sbState.tierFilter[patternKey] || []; var onlyProb = (sel.length === 1 && sel[0] === 'Probable'); sbState.tierFilter[patternKey] = onlyProb ? [] : ['Probable']; sbRenderRows(); };
  window.sb2OnSort = sbOnSort;

  // --- scaffold ---
  function sbPatternBlockSpan(pat) { return 2 + pat.tests.length + 2; }
  function sbBuildScaffold() {
    var host = document.getElementById('tab-tests_speculative_bet');
    if (!host) return false;
    if (host.querySelector('#sb-main-table')) return true;
    var cg = '<col class="c-name"><col class="c-taxon"><col class="c-price"><col class="c-52wh"><col class="c-52wl"><col class="c-ma150"><col class="c-ma200"><col class="c-pullback">';
    for (var sgc = 0; sgc < SB_STAGEINFO_COUNT; sgc++) cg += '<col class="c-stageinfo">';
    var groupHtml = '<th class="gh-inputs" colspan="' + SB_INPUT_COUNT + '">Inputs</th><th class="gh-stageinfo grp-start-stageinfo" colspan="' + SB_STAGEINFO_COUNT + '">Stage ratings</th>';
    var subGroupHtml = '<th class="sg-spacer" colspan="' + SB_INPUT_COUNT + '"></th><th class="sg-spacer" colspan="' + SB_STAGEINFO_COUNT + '"></th>';
    for (var p = 0; p < SB_PATTERNS.length; p++) {
      var pat = SB_PATTERNS[p]; var gi = p + 1; var span = sbPatternBlockSpan(pat);
      cg += '<col class="c-rating"><col class="c-score">'; for (var t = 0; t < pat.tests.length; t++) cg += '<col class="c-test">'; cg += '<col class="c-window"><col class="c-window">';
      groupHtml += '<th class="gh-g' + gi + ' grp-start-g' + gi + '" colspan="' + span + '">' + pat.shortLabel + '</th>';
      var setupCount = 0, triggerCount = 0; for (var st = 0; st < pat.tests.length; st++) { if (pat.tests[st].group === 'trigger') triggerCount++; else setupCount++; }
      subGroupHtml += '<th class="sub-g sub-g-rating sub-g' + gi + '" colspan="2">Rating</th>';
      if (setupCount > 0) subGroupHtml += '<th class="sub-g sub-g-setup sub-g' + gi + '" colspan="' + setupCount + '">Setup</th>';
      if (triggerCount > 0) subGroupHtml += '<th class="sub-g sub-g-trigger sub-g' + gi + '" colspan="' + triggerCount + '">Trigger</th>';
      subGroupHtml += '<th class="sub-g sub-g-context sub-g' + gi + '" colspan="2">Context</th>';
    }
    var captionsHtml = '';
    for (var cp = 0; cp < SB_PATTERNS.length; cp++) { var cpat = SB_PATTERNS[cp]; captionsHtml += '<div class="gcap gcap-g' + (cp+1) + '"><b>' + cpat.shortLabel + '</b>' + cpat.caption + '</div>'; }
    var theadRows = '<tr class="group-header-row">' + groupHtml + '</tr><tr class="sub-group-row">' + subGroupHtml + '</tr><tr class="col-header-row" id="sb-col-header-row"></tr>';
    var html = '<div class="s1-intro">Speculative Bets — Stage 3 and Stage 4 breakout tests. A speculative bet is a position on a stock that breaks out positively while in an unfavourable stage. In Stage 3 (topping/early decline), this is often a contrarian or short-side play. In Stage 4 (declining/bottoming), this is an early turnaround bet before the stage flips. Both use the same 6-criterion template as the probing bets: stage gate + 5D/10D MAs rising + price above 20D + 20D MA turned up in last 5 days + confirmation close. These carry the highest risk because the primary trend is against you.</div>' +
      '<div class="controls s1-controls">' +
        '<div class="ctrl-grp"><span class="ctrl-label">Inputs</span><button class="toggle-btn active" data-sb2-grp="inputs" data-sb2-val="pct" onclick="sb2SetMode(\'inputs\',\'pct\')">show as %</button><button class="toggle-btn" data-sb2-grp="inputs" data-sb2-val="raw" onclick="sb2SetMode(\'inputs\',\'raw\')">show as numbers</button></div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Tests</span><button class="toggle-btn active" data-sb2-grp="tests" data-sb2-val="tick" onclick="sb2SetMode(\'tests\',\'tick\')">show ticks</button><button class="toggle-btn" data-sb2-grp="tests" data-sb2-val="val" onclick="sb2SetMode(\'tests\',\'val\')">show test values</button></div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Scope</span><button class="toggle-btn active" data-sb2-scope="all" onclick="sb2SetScope(\'all\')">All <span id="sb2-cnt-all"></span></button><button class="toggle-btn" data-sb2-scope="live" onclick="sb2SetScope(\'live\')">Live <span id="sb2-cnt-live"></span></button><button class="toggle-btn" data-sb2-scope="sector" onclick="sb2SetScope(\'sector\')">Sectors <span id="sb2-cnt-sector"></span></button><button class="toggle-btn" data-sb2-scope="industry" onclick="sb2SetScope(\'industry\')">Industries <span id="sb2-cnt-industry"></span></button></div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Colour by</span><button class="toggle-btn active" data-sb2-tint="none" onclick="sb2SetTint(\'none\')">Off</button><button class="toggle-btn" data-sb2-tint="industry" onclick="sb2SetTint(\'industry\')">Industry</button><button class="toggle-btn" data-sb2-tint="sector" onclick="sb2SetTint(\'sector\')">Sector</button></div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Portfolio tint</span><button class="toggle-btn active" data-sb2-port="off" onclick="sb2SetPort(\'off\')">Off</button><button class="toggle-btn" data-sb2-port="on" onclick="sb2SetPort(\'on\')">On</button></div>' +
      '</div>' +
      '<div class="rating-tiles s1-rating-tiles" id="sb-pattern-tiles"></div>' +
      '<div class="group-captions">' + captionsHtml + '</div>' +
      '<div class="table-wrap"><div class="v2-hscroll"><table class="data-table" id="sb-main-table"><colgroup>' + cg + '</colgroup><thead>' + theadRows + '</thead><tbody id="sb-tbody"></tbody></table></div></div>';
    host.innerHTML = html;
    var tilesEl = document.getElementById('sb-pattern-tiles');
    if (tilesEl) { tilesEl.addEventListener('click', function(e) { var chip = e.target.closest('.pi-tier-chip'); if (chip) { var cp = chip.getAttribute('data-pattern'); var ct = chip.getAttribute('data-tier'); if (cp && ct) sb2ToggleTier(cp, ct); return; } var tile = e.target.closest('.rating-tile'); if (!tile) return; var k = tile.getAttribute('data-pattern'); if (k) sb2SelectAllTiers(k); }); }
    var hdr = document.getElementById('sb-col-header-row');
    if (hdr) { hdr.addEventListener('click', function(e) { var th = e.target.closest('th'); if (!th) return; var key = th.getAttribute('data-sort-key'); if (key) sb2OnSort(key); }); }
    return true;
  }

  function renderSpeculativeBet() {
    if (!sbBuildScaffold()) return;
    sbBuildHeaderRow();
    sbRenderRows();
    if (window.measureV2Ribbon) measureV2Ribbon();
  }
  window.renderSpeculativeBet = renderSpeculativeBet;

})();

/* MD-V2-S47-TAB-SPECULATIVE-BET-MARKER-MODULE-END */



</script>
<style>
/* MD-V2-S48-TAB-HEALTHY-VCP-MARKER-CSS-START */
/* Healthy VCP (Core MM Trade #2) -- single 7-criterion test tab (S48) */
#tab-tests_healthy_vcp .group-captions { display: grid; grid-template-columns: 1fr; gap: 10px; margin: 16px 0 14px 0; }
#tab-tests_healthy_vcp .group-captions .gcap { background: #fbfaf5; border: 1px solid #e0dcc8; border-left: 3px solid #1565C0; border-radius: 4px; padding: 10px 12px; font-size: 11px; line-height: 1.45; color: #555; }
#tab-tests_healthy_vcp .group-captions .gcap b { display: block; margin-bottom: 4px; font-weight: 700; color: #1565C0; font-size: 11px; letter-spacing: 0.2px; }
#tab-tests_healthy_vcp .s1-rating-tiles { display: grid; grid-template-columns: 1fr; gap: 8px; }
#tab-tests_healthy_vcp .s1-rating-tiles .pi-tile-hvcp { background: rgba(21,101,192,0.10); border: 1px solid rgba(21,101,192,0.25); border-radius: 4px; padding: 8px 10px; cursor: pointer; }
#tab-tests_healthy_vcp .s1-rating-tiles .pi-tile-hvcp.active { background: rgba(21,101,192,0.22); border: 1.5px solid #1565C0; }
#tab-tests_healthy_vcp .s1-rating-tiles .pi-strip-hvcp { background: #1565C0; height: 4px; margin-top: 6px; border-radius: 2px; }
#tab-tests_healthy_vcp .s1-rating-tiles .rt-breakdown { font-size: 9px; color: #888; margin-top: 4px; line-height: 1.35; }
#tab-tests_healthy_vcp .pi-tier-chips { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 7px; }
#tab-tests_healthy_vcp .pi-tier-chip { font-size: 10px; padding: 2px 6px; border-radius: 4px; cursor: pointer; user-select: none; border: 0.5px solid; line-height: 1.4; white-space: nowrap; transition: background 0.12s, color 0.12s; }
#tab-tests_healthy_vcp .pi-chip-hvcp { background: #E3F2FD; color: #1565C0; border-color: #90CAF9; }
#tab-tests_healthy_vcp .pi-chip-hvcp.on { background: #1565C0; color: #fff; border-color: #1565C0; font-weight: 500; }
#tab-tests_healthy_vcp .pi-tier-chip:hover { filter: brightness(0.96); }
/* Table styles */
#hvcp-main-table { width: 100%; border-collapse: separate; border-spacing: 0; font-size: 11px; table-layout: fixed; background: #fbfaf5; border: 1px solid #e0dcc8; border-radius: 4px; }
#hvcp-main-table thead { position: sticky; top: 0; z-index: 50; background: #fbfaf5; box-shadow: 0 2px 4px rgba(0,0,0,0.06); }
#hvcp-main-table thead th { background: #fbfaf5 !important; border-bottom: 1px solid #e0dcc8; padding: 7px 3px; text-align: center; font-weight: 600; font-size: 10px; color: #666; cursor: pointer; user-select: none; line-height: 1.25; vertical-align: middle; }
#hvcp-main-table thead th:hover { background: #f0ebd9 !important; }
#hvcp-main-table thead .group-header-row th { background: #f3efe2 !important; font-size: 9.5px; text-transform: none; font-weight: 700; letter-spacing: 0.2px; padding: 5px 3px; cursor: default; line-height: 1.25; }
#hvcp-main-table thead tr.group-header-row th { position: sticky; top: 0; }
#hvcp-main-table thead tr.sub-group-row th { position: sticky; top: 24px; font-size: 9px; text-transform: uppercase; letter-spacing: 0.3px; color: #888; padding: 3px; font-weight: 600; background: #f8f6ee !important; border-bottom: 1px solid #e0dcc8; }
#hvcp-main-table thead tr.col-header-row th { position: sticky; top: 44px; border-top: 1px solid #e0dcc8; }
#hvcp-main-table thead .gh-inputs { color: #555; }
#hvcp-main-table thead .gh-stageinfo { color: #7a6a3a; }
#hvcp-main-table thead .gh-g1 { color: #1565C0; }
#hvcp-main-table .hd { display: inline-flex; align-items: center; justify-content: center; gap: 3px; width: 100%; }
#hvcp-main-table .hd .lbl { white-space: normal; word-break: break-word; }
#hvcp-main-table .hd .sort-arrow { font-size: 9px; color: #1565C0; flex: 0 0 auto; line-height: 1; }
#hvcp-main-table .hd .sort-placeholder { width: 9px; flex: 0 0 auto; }
#hvcp-main-table td { padding: 5px 4px; border-bottom: 1px solid #efece0; text-align: center; vertical-align: middle; height: 38px; box-sizing: border-box; font-variant-numeric: tabular-nums; }
#hvcp-main-table tr:hover { background: rgba(21,101,192,0.05); }
#hvcp-main-table td.grp-start-stageinfo, #hvcp-main-table th.grp-start-stageinfo { border-left: 2px solid rgba(122,106,58,0.40); }
#hvcp-main-table td.grp-start-g1, #hvcp-main-table th.grp-start-g1 { border-left: 2px solid rgba(21,101,192,0.40); }
#hvcp-main-table td.pi-pass { background: rgba(21,101,192,0.12); color: #1565C0; font-weight: 700; }
#hvcp-main-table td.pi-fail { color: #999; }
#hvcp-main-table td.pi-rating-cell { padding: 3px 4px; }
#hvcp-main-table .pi-pill { display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 9px; font-weight: 700; line-height: 1.3; white-space: nowrap; }
#hvcp-main-table .pi-pill-tint-qualified { background: #0D47A1; color: #fff; }
#hvcp-main-table .pi-pill-tint-prob { background: #1565C0; color: #fff; }
#hvcp-main-table .pi-pill-tint-pla  { background: rgba(21,101,192,0.30); color: #0a3c78; }
#hvcp-main-table .pi-pill-tint-pos  { background: rgba(21,101,192,0.14); color: #1a4a8a; }
#hvcp-main-table .pi-pill-tint-none { background: #ece9dd; color: #999; }
#hvcp-main-table td.pi-score-cell { padding: 4px 3px; }
#hvcp-main-table .pi-pip-row { display: inline-flex; align-items: center; gap: 2px; justify-content: center; }
#hvcp-main-table .pi-pip-row .pip { width: 6px; height: 6px; border-radius: 50%; background: #d8d4c4; display: inline-block; }
#hvcp-main-table .pi-pip-row .pip.on { background: #1565C0; }
#hvcp-main-table .pi-pip-row .pi-score-num { font-size: 9px; color: #777; margin-left: 3px; font-weight: 600; }
#hvcp-main-table td.ct-stage-info-cell { padding: 3px 4px; }
#hvcp-main-table .ct-info-label { display: inline-block; padding: 2px 5px; border-radius: 3px; font-size: 9px; font-weight: 600; line-height: 1.3; white-space: nowrap; }
#hvcp-main-table td.ct-stage-info-cell.tint-prob .ct-info-label { background: rgba(21,101,192,0.22); color: #0a3c78; }
#hvcp-main-table td.ct-stage-info-cell.tint-pla  .ct-info-label { background: rgba(21,101,192,0.13); color: #1a4a8a; }
#hvcp-main-table td.ct-stage-info-cell.tint-pos  .ct-info-label { background: rgba(21,101,192,0.07); color: #5a7a9a; }
#hvcp-main-table td.ct-stage-info-cell.tint-none .ct-info-label { background: #f0ede1; color: #aaa; }
#hvcp-main-table td.ct-window-col { padding: 3px 4px; font-size: 10px; }
#hvcp-main-table td.ct-window-fired-recent { background: rgba(21,101,192,0.16); }
#hvcp-main-table td.ct-window-fired-recent .ct-window-label { color: #0a3c78; font-weight: 700; }
#hvcp-main-table td.ct-window-fired-older { background: rgba(186,117,23,0.14); }
#hvcp-main-table td.ct-window-fired-older .ct-window-label { color: #7a4e0a; font-weight: 600; }
#hvcp-main-table td.ct-window-none { color: #bbb; }
#hvcp-main-table td.ct-window-building { color: #b59a5a; font-style: italic; font-size: 9px; }
#hvcp-main-table td.name-cell { text-align: left; padding: 4px 4px 4px 8px; line-height: 1.15; }
#hvcp-main-table td.name-cell .co { font-weight: 700; font-size: 11px; color: #2a2a2a; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
#hvcp-main-table td.name-cell .tk { font-size: 9px; color: #999; font-weight: 500; margin-top: 1px; }
#hvcp-main-table td.name-cell .live-dot { color: #2e7d32; font-weight: 700; margin-right: 4px; }
#hvcp-main-table td.taxon { text-align: left; font-size: 9px; line-height: 1.2; padding: 4px; }
#hvcp-main-table td.taxon .ind { color: #666; font-weight: 500; }
#hvcp-main-table td.taxon .sec { color: #999; }
#hvcp-main-table col.c-name { width: 124px; }
#hvcp-main-table col.c-taxon { width: 150px; }
#hvcp-main-table col.c-price { width: 50px; }
#hvcp-main-table col.c-52wh { width: 48px; }
#hvcp-main-table col.c-52wl { width: 48px; }
#hvcp-main-table col.c-ma150 { width: 48px; }
#hvcp-main-table col.c-ma200 { width: 48px; }
#hvcp-main-table col.c-pullback { width: 58px; }
#hvcp-main-table col.c-stageinfo { width: 56px; }
#hvcp-main-table col.c-rating { width: 64px; }
#hvcp-main-table col.c-score { width: 52px; }
#hvcp-main-table col.c-test { width: 64px; }
#hvcp-main-table col.c-window { width: 52px; }
#hvcp-main-table tr.tint-row td.name-cell, #hvcp-main-table tr.tint-row td.taxon { background: var(--tint-bg) !important; }
#hvcp-main-table tr.portfolio-band td:last-child { border-right: 4px solid var(--portfolio-color); }
#hvcp-main-table tr.portfolio-tint { background: var(--portfolio-bg); }
#hvcp-main-table tr.portfolio-tint:hover { background: var(--portfolio-bg-hover); }
/* MD-V2-S48-TAB-HEALTHY-VCP-MARKER-CSS-END */
</style>
<script>

/* MD-V2-S48-TAB-HEALTHY-VCP-MARKER-MODULE-START */
// =============================================================================
// HEALTHY VCP (Core MM Trade #2) -- TAB MODULE (S48)
// =============================================================================
// MD-V2-S48-TAB-HEALTHY-VCP-MARKER
// Single 7-criterion test: Stage 2 basing gate + 4 VCP pattern tests + 2 triggers.
//   vcp_deploy_s2: Stage 2 in basing phase (hard gate) + narrowing VCP + breakout
// =============================================================================

(function() {
  'use strict';

  var HVCP_PATTERN = {
    key: 'vcp_deploy_s2',
    label: 'Stage 2 basing + VCP contraction + breakout \u21d2 Healthy VCP (Trade 2)',
    shortLabel: 'Healthy VCP',
    tone: 'hvcp',
    tierLadder: ['Possible', 'Plausible', 'Probable', 'Qualified'],
    total: 7,
    tooltip: 'Core MM Trade #2: a Volatility Contraction Pattern on a Stage 2 stock in a basing phase, confirmed by a clean breakout.',
    caption: '<span class="db">Stage 2 stock in a basing phase with a Volatility Contraction Pattern (VCP), broken out with confirmation.</span> Requires: Stage 2 + basing (hard gate), narrowing contractions, sufficient contraction count, declining volume on contractions, higher lows through the base, then a positive breakout and a close 2%+ above yesterday.',
    tests: [
      { key: 'g1_stage2_basing',              label: 'Stage 2 + basing',          group: 'gate',    tooltip: 'Stage 2 stock currently in a basing phase -- hard precondition for VCP deploy' },
      { key: 'v1_narrowing_contractions',      label: 'Narrowing contractions',     group: 'vcp',     tooltip: 'Each price contraction within the base is narrower than the previous one' },
      { key: 'v2_sufficient_count',            label: 'Sufficient count (\u22652)',  group: 'vcp',     tooltip: 'At least 2 VCP contractions have completed in the base' },
      { key: 'v3_volume_declining',            label: 'Volume declining',           group: 'vcp',     tooltip: 'Volume is declining through the contractions (drying up into the base)' },
      { key: 'v4_higher_lows',                 label: 'Higher lows',                group: 'vcp',     tooltip: 'Each successive low in the contraction is higher than the last' },
      { key: 'x1_breakout',                    label: 'Breakout',                   group: 'trigger', tooltip: 'Price has broken above the pivot point of the most recent contraction' },
      { key: 'x2_confirmation_close_ge2pct',   label: 'Confirm: close 2%+',         group: 'trigger', tooltip: 'Today close at least 2% above yesterday -- follow-through confirmation' }
    ]
  };

  var hvcpState = {
    mode: { inputs: 'pct', tests: 'tick' },
    scope: 'all',
    tierFilter: [],
    tint: 'none',
    port: 'off',
    sort: { col: 'company', dir: 'asc' }
  };

  var HVCP_RATING_RANK = { 'Qualified':6, 'Probable':5, 'Plausible':3, 'Possible':2, 'None':1 };
  var HVCP_RATING_CLS  = { 'Qualified':'tint-qualified', 'Probable':'tint-prob', 'Plausible':'tint-pla', 'Possible':'tint-pos', 'None':'tint-none' };

  function hvcpPricesLookup() { if (window._hvcpPricesByTicker) return window._hvcpPricesByTicker; var out = {}; var arr = (window.MASTER_DATA && MASTER_DATA.prices) || []; for (var i = 0; i < arr.length; i++) if (arr[i] && arr[i].ticker) out[arr[i].ticker] = arr[i]; window._hvcpPricesByTicker = out; return out; }
  function hvcpLiveTickers() { var o = {}; var inv = (window.MASTER_DATA && MASTER_DATA.positions && MASTER_DATA.positions.investments) || []; for (var i = 0; i < inv.length; i++) if (inv[i].ticker) o[inv[i].ticker] = true; return o; }
  function hvcpLiveSectors() { var o = {}, p = hvcpPricesLookup(), t = hvcpLiveTickers(); for (var k in t) { var px = p[k]; if (px && px.sector) o[px.sector] = true; } return o; }
  function hvcpLiveIndustries() { var o = {}, p = hvcpPricesLookup(), t = hvcpLiveTickers(); for (var k in t) { var px = p[k]; if (px && px.industry) o[px.industry] = true; } return o; }
  function hvcpPatternRec(row) { var dk = row.md_v2 && row.md_v2.tests; return (dk && dk[HVCP_PATTERN.key]) || null; }
  function hvcpEvalTest(row, testKey) { var rec = hvcpPatternRec(row); if (!rec || !rec.tests) return false; return !!rec.tests[testKey]; }
  function hvcpRowRating(row) { var rec = hvcpPatternRec(row); return rec ? (rec.rating || 'None') : 'None'; }
  function hvcpStageRating(row, stageKey) { var md = row.md_v2 || {}; var st = md[stageKey]; return (st && st.rating) || 'None'; }
  function hvcpGetRows() {
    var raw = (window.MASTER_DATA && MASTER_DATA.filters) || [];
    var prices = hvcpPricesLookup();
    var live = hvcpLiveTickers(), liveS = hvcpLiveSectors(), liveI = hvcpLiveIndustries();
    var rows = [];
    for (var i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || !s.md_v2 || !s.md_v2.tests) continue;
      var p = prices[s.ticker] || {};
      var mas = p.mas || {};
      rows.push({
        ticker: s.ticker, company: p.company_name || s.ticker,
        sector: p.sector || '', industry: p.industry || '',
        price: p.price, high_52w: p.high_52w, low_52w: p.low_52w,
        recent_pullback: p.recent_pullback_pct,
        ma_150: mas['150D'], ma_200: mas['200D'],
        md_v2: s.md_v2,
        is_live: !!live[s.ticker],
        sector_in_portfolio: !!liveS[p.sector],
        industry_in_portfolio: !!liveI[p.industry]
      });
    }
    return rows;
  }

  function hvcpTierCounts(rows) { var c = { 'Qualified':0, 'Probable':0, 'Plausible':0, 'Possible':0, 'None':0 }; for (var i = 0; i < rows.length; i++) { var r = hvcpRowRating(rows[i]); if (c[r] != null) c[r]++; } return c; }
  function hvcpPassHistogram(rows) { var h = []; for (var k = 0; k <= 7; k++) h[k] = 0; for (var i = 0; i < rows.length; i++) { var rec = hvcpPatternRec(rows[i]); var cnt = rec ? (rec.count || 0) : 0; if (cnt >= 0 && cnt <= 7) h[cnt]++; } return h; }

  function hvcpFmtNum(n) { if (n == null || isNaN(n)) return '-'; var abs = Math.abs(n); var dp = abs >= 100 ? 0 : (abs >= 20 ? 1 : 2); if (Math.abs(n - Math.round(n)) < 1e-9) dp = 0; var f = abs.toLocaleString('en-GB', { minimumFractionDigits: dp, maximumFractionDigits: dp }); return n < 0 ? '(' + f + ')' : f; }
  function hvcpFmtPct(p) { if (p == null || isNaN(p)) return '-'; var r = Math.round(p), abs = Math.abs(r); return r < 0 ? '(' + abs + ')%' : r + '%'; }
  function hvcpColourForIntensity(i) { if (i >= 0.6) return '#1565C0'; if (i >= 0.25) return '#1976D2'; if (i >= 0.05) return '#42A5F5'; if (i <= -0.6) return '#A32D2D'; if (i <= -0.25) return '#E24B4A'; if (i <= -0.05) return '#F09595'; return '#888'; }
  function hvcpInputCell(row, key, extraCls) {
    extraCls = extraCls || '';
    var v = row[key];
    if (key === 'price') return '<td class="num ' + extraCls + '">' + hvcpFmtNum(v) + '</td>';
    if (key === 'recent_pullback') { if (v == null || isNaN(v)) return '<td class="num ' + extraCls + '">-</td>'; var pctVal = v * 100; var pi_i = Math.max(-1, Math.min(1, (pctVal - 5) / 20)); return '<td class="num ' + extraCls + '" style="color:' + hvcpColourForIntensity(-pi_i) + '">' + Math.round(pctVal) + '%</td>'; }
    if (v == null || row.price == null) return '<td class="num ' + extraCls + '">-</td>';
    var pct = (row.price - v) / v * 100;
    var intensity = 0;
    if (key === 'high_52w') intensity = Math.max(-1, Math.min(1, (-pct - 5) / 20));
    else if (key === 'low_52w') intensity = Math.max(-1, Math.min(1, (pct - 20) / 30));
    else if (key === 'ma_150' || key === 'ma_200') intensity = Math.max(-1, Math.min(1, pct / 10));
    var text = (hvcpState.mode.inputs === 'pct') ? hvcpFmtPct(pct) : hvcpFmtNum(v);
    return '<td class="num ' + extraCls + '" style="color:' + hvcpColourForIntensity(intensity) + '">' + text + '</td>';
  }
  function hvcpStageInfoCell(row, stageKey, cls) { var rating = hvcpStageRating(row, stageKey); var rcls = HVCP_RATING_CLS[rating] || (rating.indexOf('Probable') === 0 ? 'tint-prob' : rating.indexOf('Plausible') === 0 ? 'tint-pla' : rating.indexOf('Possible') === 0 ? 'tint-pos' : 'tint-none'); return '<td class="' + (cls || '') + ' ct-stage-info-cell ' + rcls + '"><span class="ct-info-label">' + rating + '</span></td>'; }
  function hvcpTestValueFor(row, testKey) { var rec = hvcpPatternRec(row); var tv = rec && rec.test_values; if (!tv || !(testKey in tv)) return '\u2014'; var v = tv[testKey]; if (v === null || v === undefined) return '\u2014'; if (typeof v === 'string') return v; if (typeof v === 'number') { if (isNaN(v)) return '\u2014'; if (Math.abs(v) <= 1.5 && v !== Math.round(v)) return hvcpFmtPct(v * 100); return hvcpFmtNum(v); } return String(v); }
  function hvcpTestCell(row, testKey, cls) {
    var pass = hvcpEvalTest(row, testKey);
    var extra = cls || '';
    if (hvcpState.mode.tests === 'val') { var v = hvcpTestValueFor(row, testKey); var colour = pass ? hvcpColourForIntensity(0.7) : hvcpColourForIntensity(-0.4); return '<td class="test-val pi-' + (pass ? 'pass' : 'fail') + ' ' + extra + '" style="color:' + colour + '">' + v + '</td>'; }
    if (pass) return '<td class="pi-pass ' + extra + '"><span class="tick">\u2713</span></td>';
    return '<td class="pi-fail ' + extra + '">.</td>';
  }
  function hvcpRatingCell(row, cls) { var rating = hvcpRowRating(row); var rcls = HVCP_RATING_CLS[rating] || 'tint-none'; return '<td class="' + (cls || '') + ' pi-rating-cell ' + rcls + '"><span class="pi-pill pi-pill-' + rcls + '">' + rating + '</span></td>'; }
  function hvcpScoreCell(row, cls) { var rec = hvcpPatternRec(row); var cnt = rec ? (rec.count || 0) : 0; var tot = rec ? (rec.total || 0) : 0; var s = ''; for (var i = 0; i < tot; i++) s += '<span class="pip ' + (i < cnt ? 'on' : '') + '"></span>'; return '<td class="' + (cls || '') + ' pi-score-cell"><div class="pi-pip-row">' + s + '<span class="pi-score-num">' + cnt + '/' + tot + '</span></div></td>'; }
  function hvcpWindowCell(row, windowKey, cls) { var rec = hvcpPatternRec(row); var extra = cls || ''; if (!rec) return '<td class="' + extra + ' ct-window-na">-</td>'; var depth = rec.history_depth || 0; var windowDays = (windowKey === 'l5d') ? 5 : 20; if (depth < windowDays) return '<td class="' + extra + ' ct-window-building" title="' + depth + ' of ' + windowDays + ' days of history accumulated">building</td>'; var fired = (windowKey === 'l5d') ? !!rec.fired_l5d : !!rec.fired_l20d; if (!fired) return '<td class="' + extra + ' ct-window-none">-</td>'; var ds = rec.days_since_fired; var label; if (ds === 0) label = 'today'; else if (ds === 1) label = '1d ago'; else if (ds != null) label = ds + 'd ago'; else label = 'fired'; var shadeCls = (ds != null && ds <= 5) ? 'ct-window-fired-recent' : 'ct-window-fired-older'; return '<td class="' + extra + ' ' + shadeCls + '"><span class="ct-window-label">' + label + '</span></td>'; }
  function hvcpHashColor(label, alpha) { if (!label) return null; var h = 0; for (var i = 0; i < label.length; i++) h = (h * 31 + label.charCodeAt(i)) & 0xffff; return 'hsla(' + (h % 360) + ', 35%, 55%, ' + alpha + ')'; }
  function hvcpPortfolioInfo(row) { if (row.is_live) return { color:'#1b5e20', bg:'rgba(27,94,32,0.10)', bgHover:'rgba(27,94,32,0.14)' }; if (row.sector_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.05)', bgHover:'rgba(27,94,32,0.08)' }; if (row.industry_in_portfolio) return { color:'#1b5e20', bg:'rgba(27,94,32,0.025)', bgHover:'rgba(27,94,32,0.05)' }; return null; }

  var HVCP_COLS = (function() {
    var cols = [
      { id:'name',     sortKey:'company',        kind:'input' },
      { id:'taxon',    sortKey:'sector',          kind:'input' },
      { id:'price',    sortKey:'price',           kind:'input' },
      { id:'high_52w', sortKey:'high_52w',        kind:'input' },
      { id:'low_52w',  sortKey:'low_52w',         kind:'input' },
      { id:'ma_150',   sortKey:'ma_150',          kind:'input' },
      { id:'ma_200',   sortKey:'ma_200',          kind:'input' },
      { id:'pullback', sortKey:'recent_pullback', kind:'input' }
    ];
    var STAGES = ['stage_1','stage_2','stage_3','stage_4'];
    if (PB_STAGEINFO_COUNT > 0) { for (var si = 0; si < STAGES.length; si++) cols.push({ id:'info_'+STAGES[si], sortKey:'stageinfo__'+STAGES[si], kind:'stageinfo', stageKey:STAGES[si] }); }
    cols.push({ id:'g1_rating', sortKey:'hvcp__rating', kind:'rating' });
    cols.push({ id:'g1_score',  sortKey:'hvcp__score',  kind:'score' });
    var TESTS = HVCP_PATTERN.tests;
    for (var t = 0; t < TESTS.length; t++) cols.push({ id:'g1t'+(t+1), sortKey:'hvcp__'+TESTS[t].key, kind:'test', testKey:TESTS[t].key, group:TESTS[t].group, label:TESTS[t].label, tooltip:TESTS[t].tooltip });
    cols.push({ id:'g1_l5d',  sortKey:'hvcp__l5d',  kind:'window', windowKey:'l5d' });
    cols.push({ id:'g1_l20d', sortKey:'hvcp__l20d', kind:'window', windowKey:'l20d' });
    return cols;
  })();
  var HVCP_INPUT_COUNT = 8;
  var HVCP_STAGEINFO_COUNT = 4;

  function hvcpGetSortVal(row, key) {
    if (key.indexOf('stageinfo__') === 0) { var sk = key.split('__')[1]; return HVCP_RATING_RANK[hvcpStageRating(row, sk)] || 0; }
    if (key.indexOf('hvcp__') === 0) {
      var sub = key.split('__')[1];
      var rec = hvcpPatternRec(row);
      if (sub === 'rating') return rec ? (HVCP_RATING_RANK[rec.rating] || 0) : 0;
      if (sub === 'score')  return rec ? (rec.count || 0) : 0;
      if (sub === 'l5d' || sub === 'l20d') { if (!rec) return -1; var wd = (sub === 'l5d') ? 5 : 20; if ((rec.history_depth || 0) < wd) return -2; var fired = (sub === 'l5d') ? rec.fired_l5d : rec.fired_l20d; if (!fired) return -1; var ds = rec.days_since_fired; return (ds == null) ? 0 : (1000 - ds); }
      return hvcpEvalTest(row, sub) ? 1 : 0;
    }
    if (key === 'recent_pullback') return row.recent_pullback == null ? -Infinity : row.recent_pullback;
    var PCT_KEYS = ['high_52w','low_52w','ma_150','ma_200'];
    if (PCT_KEYS.indexOf(key) > -1 && hvcpState.mode.inputs === 'pct') { var ref = row[key]; if (ref == null || row.price == null || ref === 0) return -Infinity; return (row.price - ref) / ref * 100; }
    if (key in row) return row[key];
    return 0;
  }
  function hvcpOnSort(key) { if (hvcpState.sort.col === key) hvcpState.sort.dir = hvcpState.sort.dir === 'desc' ? 'asc' : 'desc'; else hvcpState.sort = { col: key, dir: key === 'company' ? 'asc' : 'desc' }; hvcpBuildHeaderRow(); hvcpRenderRows(); }
  function hvcpBuildHeaderRow() {
    var tr = document.getElementById('hvcp-col-header-row');
    if (!tr) return;
    var INPUT_LABELS = ['Company - Ticker','Industry - Sector','Price','52wk high','52wk low','150D MA','200D MA','Pullback'];
    var STAGE_LABELS = ['Stage 1','Stage 2','Stage 3','Stage 4'];
    var h = '';
    for (var i = 0; i < HVCP_COLS.length; i++) {
      var c = HVCP_COLS[i];
      var isSort = hvcpState.sort.col === c.sortKey;
      var arrow = isSort ? '<span class="sort-arrow">' + (hvcpState.sort.dir === 'desc' ? '\u25bc' : '\u25b2') + '</span>' : '<span class="sort-placeholder"></span>';
      var label, title, cls = '';
      if (c.kind === 'input') { label = INPUT_LABELS[i]; title = label; }
      else if (c.kind === 'stageinfo') { label = STAGE_LABELS[i - HVCP_INPUT_COUNT]; title = label + ' rating'; cls = (i === HVCP_INPUT_COUNT ? 'grp-start-stageinfo ' : ''); }
      else if (c.kind === 'rating') { label = 'Rating'; title = 'Healthy VCP rating'; cls = 'grp-start-g1 '; }
      else if (c.kind === 'score') { label = 'Score'; title = 'Pass count out of 7'; }
      else if (c.kind === 'test') { label = c.label; title = c.tooltip || c.label; }
      else if (c.kind === 'window') { label = c.windowKey === 'l5d' ? 'Fired 5d' : 'Fired 20d'; title = label; cls = 'ct-window-col '; }
      else { label = '?'; title = ''; }
      h += '<th class="' + cls + '" data-sort-key="' + c.sortKey + '" title="' + title + '"><span class="hd"><span class="lbl">' + label + '</span>' + arrow + '</span></th>';
    }
    tr.innerHTML = h;
  }

  function hvcpPatternTile(scopeRows) {
    var tiles = document.getElementById('hvcp-pattern-tiles');
    if (!tiles) return;
    var total = scopeRows.length;
    var tierCounts = hvcpTierCounts(scopeRows);
    var cnt = total - (tierCounts['None'] || 0);
    var pct = total > 0 ? Math.round(cnt / total * 100) : 0;
    var sel = hvcpState.tierFilter;
    var anySel = sel.length > 0;
    var headline = cnt, headSub = 'of ' + total.toLocaleString('en-GB') + ' \u00b7 ' + pct + '%';
    if (anySel) { var ft = 0; for (var z = 0; z < sel.length; z++) ft += (tierCounts[sel[z]] || 0); headline = ft; headSub = sel.join(' + ') + ' \u00b7 filtered'; }
    var hist = hvcpPassHistogram(scopeRows);
    var breakdown = '';
    for (var k = 1; k <= 7; k++) { if (k > 1) breakdown += ' \u00b7 '; breakdown += k + '/7: ' + (hist[k] || 0).toLocaleString('en-GB'); }
    var chips = '';
    var TIERS = ['Possible','Plausible','Probable','Qualified'];
    for (var c = 0; c < TIERS.length; c++) {
      var tier = TIERS[c]; var on = sel.indexOf(tier) > -1; var tc = tierCounts[tier] || 0;
      chips += '<span class="pi-tier-chip pi-chip-hvcp' + (on ? ' on' : '') + '" data-tier="' + tier + '">' + tier + ' ' + tc.toLocaleString('en-GB') + (on ? ' \u2713' : '') + '</span>';
    }
    var activeCls = anySel ? ' active' : '';
    tiles.innerHTML = '<div class="rating-tile pi-tile-hvcp' + activeCls + '" id="hvcp-main-tile" title="' + HVCP_PATTERN.tooltip + '">' +
      '<div class="rt-label">' + HVCP_PATTERN.shortLabel + '</div><div class="rt-count">' + headline.toLocaleString('en-GB') + '</div><div class="rt-sub">' + headSub + '</div>' +
      '<div class="rt-breakdown">' + breakdown + '</div><div class="pi-tier-chips" id="hvcp-tier-chips">' + chips + '</div>' +
      '<div class="rt-strip pi-strip-hvcp"></div></div>';
  }

  function hvcpUpdateScopeCounts(rows) { function set(id, n) { var el = document.getElementById(id); if (el) el.textContent = '(' + n + ')'; } set('hvcp-cnt-all', rows.length); set('hvcp-cnt-live', rows.filter(function(r){return r.is_live}).length); set('hvcp-cnt-sector', rows.filter(function(r){return r.sector_in_portfolio}).length); set('hvcp-cnt-industry', rows.filter(function(r){return r.industry_in_portfolio}).length); }
  function hvcpApplyScope(all) { var rows = all.slice(); if (hvcpState.scope === 'live') rows = rows.filter(function(r){return r.is_live}); else if (hvcpState.scope === 'sector') rows = rows.filter(function(r){return r.sector_in_portfolio}); else if (hvcpState.scope === 'industry') rows = rows.filter(function(r){return r.industry_in_portfolio}); return rows; }
  function hvcpApplyTierFilter(rows) { if (hvcpState.tierFilter.length === 0) return rows; return rows.filter(function(r) { return hvcpState.tierFilter.indexOf(hvcpRowRating(r)) > -1; }); }

  function hvcpRenderRows() {
    var tbody = document.getElementById('hvcp-tbody');
    if (!tbody) return;
    var all = hvcpGetRows();
    var scopeRows = hvcpApplyScope(all);
    hvcpUpdateScopeCounts(all);
    hvcpPatternTile(scopeRows);
    var rows = hvcpApplyTierFilter(scopeRows);
    rows.sort(function(a,b) { var va = hvcpGetSortVal(a, hvcpState.sort.col), vb = hvcpGetSortVal(b, hvcpState.sort.col); var cmp = (typeof va === 'string') ? va.localeCompare(vb) : (va || 0) - (vb || 0); if (cmp === 0) cmp = a.ticker.localeCompare(b.ticker); return hvcpState.sort.dir === 'desc' ? -cmp : cmp; });
    var STAGES = ['stage_1','stage_2','stage_3','stage_4'];
    var html = '';
    for (var i = 0; i < rows.length; i++) {
      var s = rows[i];
      var styles = [], cls = [];
      if (hvcpState.tint === 'industry') { styles.push('--tint-bg: ' + hvcpHashColor(s.industry, 0.16)); cls.push('tint-row'); }
      else if (hvcpState.tint === 'sector') { styles.push('--tint-bg: ' + hvcpHashColor(s.sector, 0.16)); cls.push('tint-row'); }
      if (hvcpState.port === 'on') { var pinf = hvcpPortfolioInfo(s); if (pinf) { styles.push('--portfolio-color: ' + pinf.color); styles.push('--portfolio-bg: ' + pinf.bg); styles.push('--portfolio-bg-hover: ' + pinf.bgHover); cls.push('portfolio-band'); cls.push('portfolio-tint'); } }
      var styleAttr = styles.length ? ' style="' + styles.join(';') + '"' : '';
      var clsAttr = cls.length ? ' class="' + cls.join(' ') + '"' : '';
      var liveDot = s.is_live ? '<span class="live-dot">\u25cf</span>' : '';
      html += '<tr' + clsAttr + styleAttr + '>' +
        '<td class="name-cell"><div class="co">' + liveDot + (s.company || s.ticker) + '</div><div class="tk">' + s.ticker + '</div></td>' +
        '<td class="taxon"><div class="ind">' + (s.industry || '') + '</div><div class="sec">' + (s.sector || '') + '</div></td>' +
        hvcpInputCell(s, 'price') + hvcpInputCell(s, 'high_52w') + hvcpInputCell(s, 'low_52w') + hvcpInputCell(s, 'ma_150') + hvcpInputCell(s, 'ma_200') + hvcpInputCell(s, 'recent_pullback');
      for (var si = 0; si < STAGES.length; si++) html += hvcpStageInfoCell(s, STAGES[si], si === 0 ? 'grp-start-stageinfo' : '');
      html += hvcpRatingCell(s, 'grp-start-g1');
      html += hvcpScoreCell(s, '');
      var TESTS = HVCP_PATTERN.tests;
      for (var ti = 0; ti < TESTS.length; ti++) html += hvcpTestCell(s, TESTS[ti].key, '');
      html += hvcpWindowCell(s, 'l5d', 'ct-window-col');
      html += hvcpWindowCell(s, 'l20d', 'ct-window-col');
      html += '</tr>';
    }
    tbody.innerHTML = html;
  }

  window.hvcpSetMode = function(kind, val) { hvcpState.mode[kind] = val; var btns = document.querySelectorAll('button[data-hvcp-grp="' + kind + '"]'); for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-hvcp-val') === val); hvcpRenderRows(); };
  window.hvcpSetScope = function(s) { hvcpState.scope = s; var btns = document.querySelectorAll('button[data-hvcp-scope]'); for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-hvcp-scope') === s); hvcpRenderRows(); };
  window.hvcpSetTint = function(t) { hvcpState.tint = t; var btns = document.querySelectorAll('button[data-hvcp-tint]'); for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-hvcp-tint') === t); hvcpRenderRows(); };
  window.hvcpSetPort = function(p) { hvcpState.port = p; var btns = document.querySelectorAll('button[data-hvcp-port]'); for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-hvcp-port') === p); hvcpRenderRows(); };
  window.hvcpToggleTier = function(tier) { var sel = hvcpState.tierFilter; var idx = sel.indexOf(tier); if (idx > -1) sel.splice(idx, 1); else sel.push(tier); hvcpRenderRows(); };
  window.hvcpSelectAllTiers = function() { var onlyProb = (hvcpState.tierFilter.length === 1 && hvcpState.tierFilter[0] === 'Probable'); hvcpState.tierFilter = onlyProb ? [] : ['Probable']; hvcpRenderRows(); };
  window.hvcpOnSort = hvcpOnSort;

  function hvcpBuildScaffold() {
    var host = document.getElementById('tab-tests_healthy_vcp');
    if (!host) return false;
    if (host.querySelector('#hvcp-main-table')) return true;
    var TESTS = HVCP_PATTERN.tests;
    var gateCount = 0, vcpCount = 0, trigCount = 0;
    for (var t = 0; t < TESTS.length; t++) { if (TESTS[t].group === 'gate') gateCount++; else if (TESTS[t].group === 'vcp') vcpCount++; else if (TESTS[t].group === 'trigger') trigCount++; }
    var totalSpan = 2 + TESTS.length + 2;
    var cg = '<col class="c-name"><col class="c-taxon"><col class="c-price"><col class="c-52wh"><col class="c-52wl"><col class="c-ma150"><col class="c-ma200"><col class="c-pullback">';
    for (var sgc = 0; sgc < HVCP_STAGEINFO_COUNT; sgc++) cg += '<col class="c-stageinfo">';
    cg += '<col class="c-rating"><col class="c-score">';
    for (var tc = 0; tc < TESTS.length; tc++) cg += '<col class="c-test">';
    cg += '<col class="c-window"><col class="c-window">';
    var groupHtml = '<th class="gh-inputs" colspan="' + HVCP_INPUT_COUNT + '">Inputs</th>' +
      '<th class="gh-stageinfo grp-start-stageinfo" colspan="' + HVCP_STAGEINFO_COUNT + '">Stage ratings</th>' +
      '<th class="gh-g1 grp-start-g1" colspan="' + totalSpan + '">Healthy VCP</th>';
    var subGroupHtml = '<th class="sg-spacer" colspan="' + HVCP_INPUT_COUNT + '"></th>' +
      '<th class="sg-spacer" colspan="' + HVCP_STAGEINFO_COUNT + '"></th>' +
      '<th class="sub-g sub-g-rating sub-g1" colspan="2">Rating</th>';
    if (gateCount > 0) subGroupHtml += '<th class="sub-g sub-g-gate sub-g1" colspan="' + gateCount + '">Gate</th>';
    if (vcpCount > 0) subGroupHtml += '<th class="sub-g sub-g-setup sub-g1" colspan="' + vcpCount + '">VCP pattern</th>';
    if (trigCount > 0) subGroupHtml += '<th class="sub-g sub-g-trigger sub-g1" colspan="' + trigCount + '">Trigger</th>';
    subGroupHtml += '<th class="sub-g sub-g-context sub-g1" colspan="2">Context</th>';
    var captionsHtml = '<div class="gcap gcap-g1"><b>' + HVCP_PATTERN.shortLabel + '</b>' + HVCP_PATTERN.caption + '</div>';
    var theadRows = '<tr class="group-header-row">' + groupHtml + '</tr><tr class="sub-group-row">' + subGroupHtml + '</tr><tr class="col-header-row" id="hvcp-col-header-row"></tr>';
    var html = '<div class="s1-intro">Healthy VCP \u2014 Core MM Trade #2. A Volatility Contraction Pattern on a Stage 2 stock that is in a basing phase. The stock has been in an uptrend (Stage 2), has consolidated into a base, and the base shows classic VCP characteristics: each contraction is narrower than the last, volume is drying up, and lows are rising. A clean breakout above the pivot with a strong close confirms the pattern. This is the highest-conviction entry in the Minervini methodology: stage qualification, pattern quality, and a confirmed trigger all together.</div>' +
      '<div class="controls s1-controls">' +
        '<div class="ctrl-grp"><span class="ctrl-label">Inputs</span><button class="toggle-btn active" data-hvcp-grp="inputs" data-hvcp-val="pct" onclick="hvcpSetMode(\'inputs\',\'pct\')">show as %</button><button class="toggle-btn" data-hvcp-grp="inputs" data-hvcp-val="raw" onclick="hvcpSetMode(\'inputs\',\'raw\')">show as numbers</button></div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Tests</span><button class="toggle-btn active" data-hvcp-grp="tests" data-hvcp-val="tick" onclick="hvcpSetMode(\'tests\',\'tick\')">show ticks</button><button class="toggle-btn" data-hvcp-grp="tests" data-hvcp-val="val" onclick="hvcpSetMode(\'tests\',\'val\')">show test values</button></div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Scope</span><button class="toggle-btn active" data-hvcp-scope="all" onclick="hvcpSetScope(\'all\')">All <span id="hvcp-cnt-all"></span></button><button class="toggle-btn" data-hvcp-scope="live" onclick="hvcpSetScope(\'live\')">Live <span id="hvcp-cnt-live"></span></button><button class="toggle-btn" data-hvcp-scope="sector" onclick="hvcpSetScope(\'sector\')">Sectors <span id="hvcp-cnt-sector"></span></button><button class="toggle-btn" data-hvcp-scope="industry" onclick="hvcpSetScope(\'industry\')">Industries <span id="hvcp-cnt-industry"></span></button></div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Colour by</span><button class="toggle-btn active" data-hvcp-tint="none" onclick="hvcpSetTint(\'none\')">Off</button><button class="toggle-btn" data-hvcp-tint="industry" onclick="hvcpSetTint(\'industry\')">Industry</button><button class="toggle-btn" data-hvcp-tint="sector" onclick="hvcpSetTint(\'sector\')">Sector</button></div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Portfolio tint</span><button class="toggle-btn active" data-hvcp-port="off" onclick="hvcpSetPort(\'off\')">Off</button><button class="toggle-btn" data-hvcp-port="on" onclick="hvcpSetPort(\'on\')">On</button></div>' +
      '</div>' +
      '<div class="rating-tiles s1-rating-tiles" id="hvcp-pattern-tiles"></div>' +
      '<div class="group-captions">' + captionsHtml + '</div>' +
      '<div class="table-wrap"><div class="v2-hscroll"><table class="data-table" id="hvcp-main-table"><colgroup>' + cg + '</colgroup><thead>' + theadRows + '</thead><tbody id="hvcp-tbody"></tbody></table></div></div>';
    host.innerHTML = html;
    var tilesEl = document.getElementById('hvcp-pattern-tiles');
    if (tilesEl) { tilesEl.addEventListener('click', function(e) { var chip = e.target.closest('.pi-tier-chip'); if (chip) { var ct = chip.getAttribute('data-tier'); if (ct) hvcpToggleTier(ct); return; } var tile = e.target.closest('.rating-tile'); if (tile) hvcpSelectAllTiers(); }); }
    var hdr = document.getElementById('hvcp-col-header-row');
    if (hdr) { hdr.addEventListener('click', function(e) { var th = e.target.closest('th'); if (!th) return; var key = th.getAttribute('data-sort-key'); if (key) hvcpOnSort(key); }); }
    return true;
  }

  function renderHealthyVCP() {
    if (!hvcpBuildScaffold()) return;
    hvcpBuildHeaderRow();
    hvcpRenderRows();
    if (window.measureV2Ribbon) measureV2Ribbon();
  }
  window.renderHealthyVCP = renderHealthyVCP;

})();

/* MD-V2-S48-TAB-HEALTHY-VCP-MARKER-MODULE-END */



/* MD-V2-MASTER-OVERVIEW-MARKER-MODULE-START */
/* MD-V2-MASTER-OVERVIEW-MARKER-START */
(function() {
  'use strict';

  // MD-V2-OVERVIEW-COOCCURRENCE-S35-MARKER: Master Overview ("Overview") tab.
  // Two stacked, column-aligned tables:
  //  - the summary table (transposed): the four rating tiers + a Total rated
  //    row run down; the 20 screens run across. It is a co-occurrence selector
  //    - click a count cell to select that screen-and-tier as a criterion;
  //    every cell then shows the count of stocks meeting ALL selected criteria
  //    AND its own; tiers within one screen OR, screens AND. Click a screen
  //    name to open that screen's own tab. "Clear all" resets the selection.
  //  - the full rating matrix: every md_v2 stock down the Y-axis, the 20
  //    screens across, a rating pill per cell. It filters to the stocks that
  //    match the summary table's selection.
  // The Wave 3 per-column filter chips are removed - the summary table is the
  // single shared filter for both tables.

  var moState = { scope: 'all' };

  // Row model: { section, key, label, ratingPath, tabId, patternKey }
  //   ratingPath - how to read this screen's rating from a stock's md_v2:
  //     'stage:<k>'     -> md_v2[k].rating
  //     'group:<g>:<k>' -> md_v2[<g>][<k>].rating
  //       (pre_indicators / post_indicators / setups / tests)
  //   tabId - the tab a screen-name click opens.
  var MO_ROWS = [
    // -- Stages --
    /* MD-V2-S51-OVERVIEW-STAGE1-UNIFIED: Stage 1 single row — Probable/Plausible/Possible/None tiers (replaces S41 Early/Late split). */
    { section:'Stages', key:'stage_1', label:'Stage 1 - Basing', short:'S1 Basing', ratingPath:'stage:stage_1', tabId:'stage_1', patternKey:null },
    { section:'Stages', key:'stage_2', label:'Stage 2 - Uptrend', short:'S2 Uptrend', ratingPath:'stage:stage_2', tabId:'stage_2', patternKey:null },
    { section:'Stages', key:'stage_3', label:'Stage 3 - Topping', short:'S3 Topping', ratingPath:'stage:stage_3', tabId:'stage_3', patternKey:null },
    { section:'Stages', key:'stage_4', label:'Stage 4 - Decline', short:'S4 Decline', ratingPath:'stage:stage_4', tabId:'stage_4', patternKey:null },
    // -- Pre-test indicators --
    { section:'Pre-farfalle indicators', key:'pulling_back_uptrend', label:'Pulling back within MT/LT uptrend', short:'Pulling back', ratingPath:'group:pre_indicators:pulling_back_uptrend', tabId:'pre_indicators', patternKey:'pulling_back_uptrend' },
    { section:'Pre-farfalle indicators', key:'basing', label:'Basing in a MT/LT uptrend', short:'Basing', ratingPath:'group:pre_indicators:basing', tabId:'pre_indicators', patternKey:'basing' },
    { section:'Pre-farfalle indicators', key:'collapsing', label:'Collapsing', short:'Collapsing', ratingPath:'group:pre_indicators:collapsing', tabId:'pre_indicators', patternKey:'collapsing' },
    // -- Post-test indicators (ratingPath -> md_v2.post_indicators.<k>.rating;
    //    md_v2.indicators.<k> is a bare boolean and has no .rating - Request 1) --
    { section:'Post-farfalle indicators', key:'breakout', label:'Breakout', short:'Breakout', ratingPath:'group:post_indicators:breakout', tabId:'post_indicators', patternKey:'breakout' },
    { section:'Post-farfalle indicators', key:'advancing', label:'Advancing', short:'Advancing', ratingPath:'group:post_indicators:advancing', tabId:'post_indicators', patternKey:'advancing' },
    { section:'Post-farfalle indicators', key:'breakdown_50D', label:'Negatively breaking through ST trend (50D MA)', short:'Breaking 50D', ratingPath:'group:post_indicators:breakdown_50D', tabId:'post_indicators', patternKey:'breakdown_50D' },
    { section:'Post-farfalle indicators', key:'breakdown_150D', label:'Negatively breaking through MT trend (150D MA)', short:'Breaking 150D', ratingPath:'group:post_indicators:breakdown_150D', tabId:'post_indicators', patternKey:'breakdown_150D' },
    { section:'Post-farfalle indicators', key:'breakdown_200D', label:'Negatively breaking through LT trend (200D MA)', short:'Breaking 200D', ratingPath:'group:post_indicators:breakdown_200D', tabId:'post_indicators', patternKey:'breakdown_200D' },
    // -- Capital qualification setups --
    { section:'Capital qualification setups', key:'probing_bet', label:'Probing bet', short:'Probing bet', ratingPath:'group:setups:probing_bet', tabId:'setups_s1pb', patternKey:'probing_bet' },
    { section:'Capital qualification setups', key:'vcp_after_s1_plateau', label:'VCP after Stage 1->2 plateau', short:'VCP S1 plateau', ratingPath:'group:setups:vcp_after_s1_plateau', tabId:'setups_s1pb', patternKey:'vcp_after_s1_plateau' },
    { section:'Capital qualification setups', key:'setup_healthy_retest', label:'Healthy retest within MT/LT uptrend', short:'Healthy retest', ratingPath:'group:setups:healthy_retest', tabId:'setups_s2vcp', patternKey:'healthy_retest' },
    { section:'Capital qualification setups', key:'vcp_after_s2_base', label:'VCP after Stage 2 base', short:'VCP S2 base', ratingPath:'group:setups:vcp_after_s2_base', tabId:'setups_s2vcp', patternKey:'vcp_after_s2_base' },
    // -- Capital deployment tests --
    { section:'Capital deployment tests', key:'ma_retest_upwards', label:'Upwards moving average retest', short:'MA retest', ratingPath:'group:tests:ma_retest_upwards', tabId:'tests', patternKey:'ma_retest_upwards' },
    { section:'Capital deployment tests', key:'vcp_deploy_s1', label:'VCP after Stage 1->2', short:'VCP S1 deploy', ratingPath:'group:tests:vcp_deploy_s1', tabId:'tests', patternKey:'vcp_deploy_s1' },
    { section:'Capital deployment tests', key:'vcp_deploy_s2_hvcp', label:'Healthy VCP (Trade 2)', short:'VCP S2', ratingPath:'group:tests:vcp_deploy_s2', tabId:'tests_healthy_vcp', patternKey:'vcp_deploy_s2' },
    { section:'Capital deployment tests', key:'vcp_deploy_s2', label:'VCP after Stage 2 base', short:'VCP S2 deploy', ratingPath:'group:tests:vcp_deploy_s2', tabId:'tests', patternKey:'vcp_deploy_s2' },
    { section:'Capital deployment tests', key:'probing_bet_test', label:'Probing bet', short:'PB deploy', ratingPath:'group:tests:probing_bet', tabId:'tests', patternKey:'probing_bet' }
  ]; /* MD-V2-S40-RESPONSIVE-SHORT-HEADERS — short forms added */

  // The 4 rating tiers (Stage 1 splits Probable into Early/Late upstream; the
  // normaliser folds both into Probable).
  var MO_TIERS = ['None', 'Possible', 'Plausible', 'Probable'];
  var MO_TIER_CLS = { 'None':'mo-t-none', 'Possible':'mo-t-pos', 'Plausible':'mo-t-pla', 'Probable':'mo-t-prob' };

  // section -> group-band colour-hook class (shared by both tables)
  var MO_GROUP_CLS = {
    'Stages': 'mo-mx-g-stages',
    'Pre-farfalle indicators': 'mo-mx-g-pretest',
    'Post-farfalle indicators': 'mo-mx-g-posttest',
    'Capital qualification setups': 'mo-mx-g-setups',
    'Capital deployment tests': 'mo-mx-g-tests'
  };
  // MD-V2-S36-BRIEF-MARKER: per-section class suffix for the body-cell visual
  // grouping border (CSS rule #mo-matrix-table tbody td.mo-sec-start-*).
  var MO_SECTION_BORDER_CLS = {
    'Stages': 'mo-sec-start-stages',
    'Pre-farfalle indicators': 'mo-sec-start-pretest',
    'Post-farfalle indicators': 'mo-sec-start-posttest',
    'Capital qualification setups': 'mo-sec-start-setups',
    'Capital deployment tests': 'mo-sec-start-tests'
  };
  // MD-V2-S38-SECTIONS-OVERVIEW-MARKER: matching end-of-section map.
  var MO_SECTION_END_BORDER_CLS = {
    'Stages': 'mo-sec-end-stages',
    'Pre-farfalle indicators': 'mo-sec-end-pretest',
    'Post-farfalle indicators': 'mo-sec-end-posttest',
    'Capital qualification setups': 'mo-sec-end-setups',
    'Capital deployment tests': 'mo-sec-end-tests'
  };
  function moIsSectionStart(idx){
    if (idx === 0) return MO_ROWS[0].section;
    if (MO_ROWS[idx].section !== MO_ROWS[idx-1].section) return MO_ROWS[idx].section;
    return null;
  }
  function moIsSectionEnd(idx){
    if (idx === MO_ROWS.length - 1) return MO_ROWS[idx].section;
    if (MO_ROWS[idx].section !== MO_ROWS[idx+1].section) return MO_ROWS[idx].section;
    return null;
  }
  function moSectionEdgeCls(idx){
    var a = moIsSectionStart(idx), b = moIsSectionEnd(idx);
    var s = '';
    if (a) s += ' ' + MO_SECTION_BORDER_CLS[a];
    if (b) s += ' ' + MO_SECTION_END_BORDER_CLS[b];
    return s;
  }
  // short section labels for the group band - the full names are long.
  var MO_GROUP_LABEL = {
    'Stages': 'Stages',
    'Pre-farfalle indicators': 'Pre-farfalle',
    'Post-farfalle indicators': 'Post-farfalle',
    'Capital qualification setups': 'Qualification setups',
    'Capital deployment tests': 'Deployment tests'
  };
  var MO_MX_TIER_PILL = {
    'None': 'mo-mx-p-none', 'Possible': 'mo-mx-p-pos',
    'Plausible': 'mo-mx-p-pla', 'Probable': 'mo-mx-p-prob'
  };

  // MD-V2-OVERVIEW-COLALIGN-S35B-MARKER: shared colgroup string.
  // Both the summary table and the matrix emit this same colgroup
  // so their columns share identical fixed widths under
  // table-layout:fixed - that is what makes the two tables align.
  var MO_COLGROUP = (function(){
    var s = '<col class="mo-cg-label">';
    for (var i = 0; i < MO_ROWS.length; i++) s += '<col class="mo-cg-screen">';
    return s;
  })();

  // ----- shared helpers (unchanged from S27 / Wave 3) -----
  function moPricesLookup() {
    if (window._moPricesByTicker) return window._moPricesByTicker;
    var out = {};
    var arr = (window.MASTER_DATA && MASTER_DATA.prices) || [];
    for (var i = 0; i < arr.length; i++) if (arr[i] && arr[i].ticker) out[arr[i].ticker] = arr[i];
    window._moPricesByTicker = out;
    return out;
  }
  function moLiveTickers() {
    var out = {};
    var inv = (window.MASTER_DATA && MASTER_DATA.positions && MASTER_DATA.positions.investments) || [];
    for (var i = 0; i < inv.length; i++) if (inv[i].ticker) out[inv[i].ticker] = true;
    return out;
  }
  function moNormaliseTier(raw, subTier) {
    if (!raw) return 'None';
    // MD-V2-S41-OVERVIEW-STAGE1-SPLIT: subTier-aware normalisation. When the
    // row carries a subTier (Stage 1 Early/Late split), the cell shows
    // "Probable" only when raw matches that specific tier; the OTHER Probable
    // variant downgrades to Plausible (visible-but-not-top-tier).
    if (subTier) {
      if (raw === subTier) return 'Probable';
      if (raw.indexOf('Probable') === 0) return 'Plausible';
    }
    if (raw.indexOf('Probable') === 0) return 'Probable';
    if (raw.indexOf('Plausible') === 0) return 'Plausible';
    if (raw.indexOf('Possible') === 0) return 'Possible';
    return 'None';
  }
  function moReadRating(md, ratingPath) {
    if (!md) return 'None';
    var parts = ratingPath.split(':');
    if (parts[0] === 'stage') {
      var st = md[parts[1]];
      if (!st) return null;                /* MD-V2-S52-OVERVIEW-NULL-FIX: absent key → null (not counted), not 'None' (rated None) */
      return st.rating || 'None';
    }
    if (parts[0] === 'group') {
      var grp = md[parts[1]];
      var rec = grp && grp[parts[2]];
      if (!rec) return null;               /* MD-V2-S52-OVERVIEW-NULL-FIX */
      return rec.rating || 'None';
    }
    return 'None';
  }
  function moGetRows() {
    var raw = (window.MASTER_DATA && MASTER_DATA.filters) || [];
    var prices = moPricesLookup();
    var live = moLiveTickers();
    var rows = [];
    for (var i = 0; i < raw.length; i++) {
      var s = raw[i];
      if (!s || !s.md_v2) continue;
      var p = prices[s.ticker] || {};
      rows.push({ ticker: s.ticker, company: p.company_name || s.ticker, md_v2: s.md_v2, is_live: !!live[s.ticker] });
    }
    return rows;
  }
  function moApplyScope(all) {
    if (moState.scope === 'live') return all.filter(function(r){ return r.is_live; });
    return all;
  }
  function moMxAttr(s) {
    return String(s).replace(/&/g, '&amp;').replace(/'/g, '&#39;').replace(/"/g, '&quot;');
  }
  function moMxText(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  // ----- co-occurrence selection state (replaces the Wave 3 chip filter) -----
  // moSel[rowKey] = { tier: true, ... } - only present tier keys are active; a
  // screen with no entry is unconstrained.
  var moSel = {};

  function moSelActive() {
    for (var k in moSel) {
      if (!moSel.hasOwnProperty(k)) continue;
      var f = moSel[k];
      for (var t in f) { if (f.hasOwnProperty(t) && f[t]) return true; }
    }
    return false;
  }
  // A stock passes if, for every screen with >=1 selected tier, the stock's
  // normalised tier for that screen is one of the selected tiers (OR within a
  // screen). Screens with no selection pass freely (AND across screens).
  function moSelRowPasses(md) {
    for (var r = 0; r < MO_ROWS.length; r++) {
      var row = MO_ROWS[r];
      var f = moSel[row.key];
      if (!f) continue;
      var keys = [];
      for (var kk in f) { if (f.hasOwnProperty(kk) && f[kk]) keys.push(kk); }
      if (keys.length === 0) continue;
      var tier = moNormaliseTier(moReadRating(md, row.ratingPath), row.subTier);  /* MD-V2-S41-OVERVIEW-STAGE1-SPLIT */
      var hit = false;
      for (var j = 0; j < keys.length; j++) { if (keys[j] === tier) { hit = true; break; } }
      if (!hit) return false;
    }
    return true;
  }
  function moSelIsOn(rowKey, tier) {
    var f = moSel[rowKey];
    return !!(f && f[tier]);
  }
  // Toggle one screen x tier cell in the selection, then re-render both tables.
  function moCellClick(rowKey, tier) {
    var f = moSel[rowKey];
    if (!f) { f = {}; moSel[rowKey] = f; }
    if (f[tier]) {
      delete f[tier];
      var anyLeft = false;
      for (var t in f) { if (f.hasOwnProperty(t) && f[t]) anyLeft = true; }
      if (!anyLeft) delete moSel[rowKey];
    } else {
      f[tier] = true;
    }
    moRenderTable();
    moRenderMatrix();
  }
  window.moCellClick = moCellClick;

  function moClearSel() {
    moSel = {};
    moRenderTable();
    moRenderMatrix();
  }
  window.moClearSel = moClearSel;

  // Screen-name click: open that screen's own tab (the relocated jump - the
  // cell click is now the co-occurrence selector). _mdJump carries the tab
  // only; there is no tier context from a label click.
  function moJumpToTab(rowKey) {
    var row = null;
    for (var i = 0; i < MO_ROWS.length; i++) if (MO_ROWS[i].key === rowKey) row = MO_ROWS[i];
    if (!row) return;
    window._mdJump = { tab: row.tabId };
    /* MD-V2-MDJUMP-CACHEHIT-FIX-S39: force re-render of target tab so the
       _mdJump consumer fires on cache-hit. Without this, switchTab serves the
       cached innerHTML and the chip filter never applies. S34 carry. */
    var _mdjTgt = document.getElementById('tab-' + row.tabId);
    if (_mdjTgt) _mdjTgt.setAttribute('data-stale', '1');
    if (typeof window.switchTab === 'function') window.switchTab(row.tabId);
  }
  window.moJumpToTab = moJumpToTab;

  function moSetScope(s) {
    moState.scope = s;
    var btns = document.querySelectorAll('button[data-mo-scope]');
    for (var i = 0; i < btns.length; i++) btns[i].classList.toggle('active', btns[i].getAttribute('data-mo-scope') === s);
    moRenderTable();
  }
  window.moSetScope = moSetScope;

  // ----- transposed summary table -----
  function moRenderTable() {
    var host = document.getElementById('tab-master_overview');
    if (!host) return;
    if (!host.querySelector('#mo-main-table')) {
      var intro = '<div class="s1-intro">Overview is the synoptic view of the whole MD V2 system. The summary table below is the control surface: every rating tier as a row, every screen - the four stages, the pre-test and post-test indicators, the capital qualification setups and the capital deployment tests - as a column, lined up with the full matrix beneath it. Click any count cell to select that screen-and-tier as a criterion; every cell then shows how many stocks meet all the criteria you have selected AND its own (the &quot;patterns&quot; you are looking for), and the matrix below filters to that set. Click multiple cells to build a pattern - tiers within one screen combine as OR, screens combine as AND. Click a screen name to open that screen&apos;s own tab. Use &quot;Clear all&quot; to reset.</div>';
      var controls = '<div class="controls s1-controls">' +
        '<div class="ctrl-grp"><span class="ctrl-label">Scope</span>' +
          '<button class="toggle-btn active" data-mo-scope="all" onclick="moSetScope(\'all\')">All</button>' +
          '<button class="toggle-btn" data-mo-scope="live" onclick="moSetScope(\'live\')">Live investments</button>' +
        '</div>' +
        '<div class="ctrl-grp"><span class="ctrl-label">Pattern selection</span>' +
          '<button class="toggle-btn" id="mo-clear-btn" onclick="moClearSel()">Clear all</button>' +
        '</div></div>';
      // transposed thead: section-group band + column-title row.
      var groupTr = '<tr class="mo-group-row"><th class="mo-corner" rowspan="2">Rated tier</th>';
      var gi = 0;
      while (gi < MO_ROWS.length) {
        var sec = MO_ROWS[gi].section;
        var span = 0;
        while (gi + span < MO_ROWS.length && MO_ROWS[gi + span].section === sec) span++;
        groupTr += '<th colspan="' + span + '" class="' + (MO_GROUP_CLS[sec] || '') + '">' +
          moMxText(MO_GROUP_LABEL[sec] || sec) + '</th>';
        gi += span;
      }
      groupTr += '</tr>';
      var colTr = '<tr class="mo-col-row">';
      for (var t = 0; t < MO_ROWS.length; t++) {
        colTr += '<th class="mo-col-with-short" title="' + moMxAttr(MO_ROWS[t].label + ' - open this screen\'s tab') + '" ' +
          'data-short="' + moMxAttr(MO_ROWS[t].short || MO_ROWS[t].label) + '" ' +
          'onclick="moJumpToTab(\'' + moMxAttr(MO_ROWS[t].key) + '\')">' +
          '<span class="mo-col-long">' + moMxText(MO_ROWS[t].label) + '</span></th>';
      }
      colTr += '</tr>';
      var table = '<div class="table-wrap"><div class="v2-hscroll"><table class="data-table" id="mo-main-table">' +  /* MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER */
        '<colgroup>' + MO_COLGROUP + '</colgroup><thead>' + groupTr + colTr + '</thead><tbody id="mo-tbody"></tbody></table></div></div>';  /* MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER */
      host.innerHTML = intro + controls + table;
    }

    var rows = moApplyScope(moGetRows());
    // tally co-occurrence counts: only stocks passing the selection filter are
    // counted, so each cell shows stocks meeting ALL selected criteria AND its
    // own. With nothing selected every stock passes -> plain counts.
    var counts = {};
    for (var r0 = 0; r0 < MO_ROWS.length; r0++) {
      counts[MO_ROWS[r0].key] = { 'None':0, 'Possible':0, 'Plausible':0, 'Probable':0 };
    }
    for (var i = 0; i < rows.length; i++) {
      var md = rows[i].md_v2;
      if (!moSelRowPasses(md)) continue;
      for (var k = 0; k < MO_ROWS.length; k++) {
        var rw = MO_ROWS[k];
        var _raw = moReadRating(md, rw.ratingPath);  /* MD-V2-S52-OVERVIEW-NULL-FIX */
        if (_raw !== null) { var tr = moNormaliseTier(_raw, rw.subTier); counts[rw.key][tr]++; }  /* MD-V2-S41-OVERVIEW-STAGE1-SPLIT */
      }
    }

    var tbody = document.getElementById('mo-tbody');
    if (!tbody) return;
    var html = '';
    var anySel = moSelActive();
    for (var ti = 0; ti < MO_TIERS.length; ti++) {
      var tier = MO_TIERS[ti];
      html += '<tr class="mo-data-row"><td class="mo-tier-label">' + tier + '</td>';
      for (var c = 0; c < MO_ROWS.length; c++) {
        var rowDef = MO_ROWS[c];
        var n = counts[rowDef.key][tier];
        var sel = moSelIsOn(rowDef.key, tier);
        var cls = 'mo-cell ' + MO_TIER_CLS[tier] + (n > 0 ? ' mo-has' : ' mo-zero') + (sel ? ' mo-cell-sel' : '') + moSectionEdgeCls(c);  /* MD-V2-S38-SECTIONS-OVERVIEW-MARKER */
        var tip = rowDef.label + ' / ' + tier + ' - ' + n + ' stock(s)' +
          (anySel ? ' meeting the selected pattern' : '') +
          (sel ? '; selected (click to remove)' : '; click to add to the pattern');
        html += '<td class="' + cls + '" onclick="moCellClick(\'' + rowDef.key + '\',\'' + tier + '\')" ' +
          'title="' + moMxAttr(tip) + '">' + n.toLocaleString('en-GB') + '</td>';
      }
      html += '</tr>';
    }
    // Total rated row = Possible + Plausible + Probable per screen (tracks the
    // active selection automatically). Not selectable - it is a derived total.
    html += '<tr class="mo-total-row"><td class="mo-tier-label mo-total-label">Total rated</td>';
    for (var c2 = 0; c2 < MO_ROWS.length; c2++) {
      var ck = MO_ROWS[c2].key;
      var tot = counts[ck]['Possible'] + counts[ck]['Plausible'] + counts[ck]['Probable'];
      html += '<td class="mo-total-cell' + moSectionEdgeCls(c2) + '" title="' + moMxAttr(MO_ROWS[c2].label + ' - ' + tot + ' rated' + (anySel ? ' within the selected pattern' : '')) + '">' +  /* MD-V2-S38-SECTIONS-OVERVIEW-MARKER */
        tot.toLocaleString('en-GB') + '</td>';
    }
    html += '</tr>';
    tbody.innerHTML = html;

    var clr = document.getElementById('mo-clear-btn');
    if (clr) clr.classList.toggle('active', anySel);
  }

  // ----- the full rating matrix (Wave 3; chip row removed in S35) -----
  // Build the two sticky header rows once: section-group row, column-title row.
  function moMxBuildHead(thead) {
    // section-group row: one cell per contiguous section run.
    var groupTr = '<tr class="mo-mx-group-row"><th class="mo-mx-corner mo-mx-screen-col"></th>';
    var gi = 0;
    while (gi < MO_ROWS.length) {
      var sec = MO_ROWS[gi].section;
      var span = 0;
      while (gi + span < MO_ROWS.length && MO_ROWS[gi + span].section === sec) span++;
      groupTr += '<th colspan="' + span + '" class="' + (MO_GROUP_CLS[sec] || '') + '">' +
        moMxText(MO_GROUP_LABEL[sec] || sec) + '</th>';
      gi += span;
    }
    groupTr += '</tr>';

    // column-title row: one cell per screen, labels WRAP; click opens the tab.
    var colTr = '<tr class="mo-mx-col-row"><th class="mo-mx-screen-col">Stock</th>';
    for (var t = 0; t < MO_ROWS.length; t++) {
      colTr += '<th class="mo-col-with-short" title="' + moMxAttr(MO_ROWS[t].label + ' - open this screen\'s tab') + '" ' +
        'data-short="' + moMxAttr(MO_ROWS[t].short || MO_ROWS[t].label) + '" ' +
        'onclick="moJumpToTab(\'' + moMxAttr(MO_ROWS[t].key) + '\')" style="cursor:pointer">' +
        '<span class="mo-col-long">' + moMxText(MO_ROWS[t].label) + '</span></th>';
    }
    colTr += '</tr>';

    thead.innerHTML = groupTr + colTr;
  }

  function moRenderMatrix() {
    var host = document.getElementById('tab-master_overview');
    if (!host) return;
    var wrap = host.querySelector('#mo-matrix-wrap');
    if (!wrap) {
      wrap = document.createElement('div');
      wrap.id = 'mo-matrix-wrap';
      wrap.innerHTML =
        '<div id="mo-matrix-caption">Full rating matrix: every stock against every screen. ' +
        'Each cell is the stock\'s rating for that screen; &#8211; where it does not qualify. ' +
        'Filtered by the pattern you select in the summary table above; click a screen ' +
        'name to open that screen\'s own tab.</div>' +
        '<div class="table-wrap"><div class="v2-hscroll"><table class="data-table" id="mo-matrix-table">' +  /* MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER */
        '<colgroup>' + MO_COLGROUP + '</colgroup><thead></thead><tbody id="mo-matrix-tbody"></tbody></table></div></div>' +  /* MD-V2-WAVE3B-STICKY-SCROLL-CONTAINER-MARKER */
        '<div id="mo-matrix-foot"></div>';
      host.appendChild(wrap);
    }
    var table = wrap.querySelector('#mo-matrix-table');
    var thead = table ? table.querySelector('thead') : null;
    var tbody = wrap.querySelector('#mo-matrix-tbody');
    if (!thead || !tbody) return;
    if (!thead.querySelector('tr.mo-mx-col-row')) moMxBuildHead(thead);

    // the matrix renders ALL md_v2 stocks; the summary-table selection filters
    // which rows are shown.
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
      if (!moSelRowPasses(md)) continue;
      shown++;
      html += '<tr><td class="mo-mx-name-cell">' +
        '<span class="mo-mx-co">' + moMxText(rec.company || rec.ticker) + '</span>' +
        '<span class="mo-mx-tk">' + moMxText(rec.ticker) + '</span></td>';
      for (var r = 0; r < MO_ROWS.length; r++) {
        var tier = moNormaliseTier(moReadRating(md, MO_ROWS[r].ratingPath), MO_ROWS[r].subTier);  /* MD-V2-S41-OVERVIEW-STAGE1-SPLIT */
        var edge = moSectionEdgeCls(r);  /* MD-V2-S38-SECTIONS-OVERVIEW-MARKER */
        var tdCls = edge ? (' class="' + edge.replace(/^ /, '') + '"') : '';
        if (tier === 'None') {
          html += '<td' + tdCls + '><span class="mo-mx-pill mo-mx-p-none">&#8211;</span></td>';
        } else {
          html += '<td' + tdCls + '><span class="mo-mx-pill ' + MO_MX_TIER_PILL[tier] + '">' + tier + '</span></td>';
        }
      }
      html += '</tr>';
    }
    if (shown === 0) {
      html = '<tr class="mo-mx-empty"><td colspan="' + colCount + '">' +
        'No stocks match the selected pattern.</td></tr>';
    }
    tbody.innerHTML = html;

    var foot = wrap.querySelector('#mo-matrix-foot');
    if (foot) {
      if (moSelActive()) {
        foot.textContent = shown.toLocaleString('en-GB') + ' of ' +
          all.length.toLocaleString('en-GB') + ' stocks match the selected pattern.';
        foot.className = 'mo-foot-active';
      } else {
        foot.textContent = 'Showing all ' + all.length.toLocaleString('en-GB') +
          ' stocks. Select cells in the summary table above to filter.';
        foot.className = '';
      }
    }
  }
  window.moRenderMatrix = moRenderMatrix;

  function renderMasterOverview() {
    moRenderTable();
    moRenderMatrix();
  }
  window.renderMasterOverview = renderMasterOverview;

})();
/* MD-V2-MASTER-OVERVIEW-MARKER-END */
/* MD-V2-MASTER-OVERVIEW-MARKER-MODULE-END */




function renderTab(id){
  try{
  if(id==="summary")renderSummary();
  else if(id==="stage_1")renderStage1();  /* MD-V2-STAGE1-MARKER */
  else if(id==="stage_2")renderStage2();  /* MD-V2-STAGE2-MARKER */
  else if(id==="stage_3")renderStage3();  /* MD-V2-STAGE3-MARKER */
  else if(id==="stage_4")renderStage4();  /* MD-V2-STAGE4-MARKER */
  else if(id==="pre_indicators")renderPreIndicators();  /* MD-V2-PRE-INDICATORS-MARKER */
  else if(id==="post_indicators")renderPostIndicators();  /* MD-V2-POST-INDICATORS-MARKER */
  else if(id==="setups_s1pb")renderSetupsS1PB();  /* MD-V2-SETUPS-MARKER */
  else if(id==="setups_s2vcp")renderSetupsS2VCP();  /* MD-V2-SETUPS-MARKER */
  else if(id==="master_overview")renderMasterOverview();  /* MD-V2-MASTER-OVERVIEW-S27-MARKER */
  else if(id==="tests")renderTests();  /* MD-V2-TESTS-MARKER MD-V2-TESTS-S27-MARKER: was renderCapTests (undefined) */
  else if(id==="setups_healthy_retest")renderHealthyRetest();  /* MD-V2-S47-TAB-HEALTHY-RETEST-MARKER */
  else if(id==="tests_probing_bet_s1")renderProbingBetS1();  /* MD-V2-S59-TAB-PB-SPLIT-MARKER */
  else if(id==="tests_probing_bet_s2")renderProbingBetS2();  /* MD-V2-S59-TAB-PB-SPLIT-MARKER */
  else if(id==="tests_speculative_bet")renderSpeculativeBet();  /* MD-V2-S47-TAB-SPECULATIVE-BET-MARKER */
  else if(id==="tests_healthy_vcp")renderHealthyVCP();  /* MD-V2-S48-TAB-HEALTHY-VCP-MARKER */
  else if(id==="mm99")renderMM99();
  else if(id==="bp")renderBP();
  else if(id==="pb")renderPB();
  else if(id==="utr")renderUTR();
  else if(id==="vcp")renderVCP();
  else if(id==="tech")renderTech();
  else if(id==="combos")renderCombos();
  else if(id==="changes")renderChanges();
  else if(id==="positions")renderPositions();
  else if(id==="ssem")renderSSEM();
  else if(id==="val")renderVal();
  else{
    buildHeaderControls(id);
    for(var j=0;j<TAB_IDS.length;j++){if(TAB_IDS[j]===id){renderPlaceholder(id,TAB_LABELS[j]);updateIndSecPills();return}}
    renderPlaceholder(id,id);
  }
  }catch(e){console.error("renderTab("+id+") error:",e)}
  updateIndSecPills();
}

// Init: hide ratings by default (FIX-3)
var mainEl=document.querySelector(".main");
if(mainEl)mainEl.classList.add("ratings-hidden");
// Pass A.2: default to Company-name display globally — apply company-mode CSS hook
if(mainEl && displayMode==="company") mainEl.classList.add("company-mode");

// Pass A.2 (03-May-26): precompute SSEM ratings at startup so cross-tab consumers
// (e.g. BP tab cross-filter SSEM column) populate on first visit, not only after
// SSEM tab has rendered. Was a known gap in Pass A.1.
precomputeSsemRatings();
deriveMasterRatings();  /* SUMMARY-TAB-MARKER */

renderTab("mm99");
"""

    html = (
        '<!DOCTYPE html>\n'
        '<html lang="en">\n'
        '<head>\n'
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        '<title>Master Dashboard &mdash; Viewforth</title>\n'
        '<style>\n'
        + css +
        '\n</style>\n'
        '</head>\n'
        '<body>\n'
        '<div class="header">\n'
        '  <!-- FIX-5 Row 1: Title + stats + Key + Chart -->\n'
        '  <div class="header-top">\n'
        '    <div class="header-title">Master Dashboard</div>\n'
        '    <div class="header-stats">\n'
        '      <span>Stocks: <span class="stat-value" id="stat-count">&mdash;</span></span>\n'
        '      <span>Data: <span class="stat-value" id="stat-source">&mdash;</span></span>\n'
        '      <span>Price data updated: <span class="stat-value" id="stat-updated">&mdash;</span></span>\n'
        '      <span>Stock universe updated: <span class="stat-value" id="stat-universe-updated">&mdash;</span></span>\n'
        '    </div>\n'
        '    <div class="header-right-btns">\n'
        # MD-V2-S41-REMOVE-KEY-BUTTON-MARKER -- "Key" button removed per S41 brief (16-May-26)
        '      <button class="ctrl-btn" id="hdr-chart-btn" onclick="openChart(\'Overview\')">Chart</button>\n'
        '      <a class="ctrl-btn" href="../../databases/soi-list.html" title="Standardised Stocks of Interest list">SOI List</a>\n'
        '      <a class="ctrl-btn" href="../../landing-page.html" title="Operating system landing page">Home</a>\n'
        '      <a class="ctrl-btn" href="../../reports-memos-repository.html" title="Research repository">Repository</a>\n'
        '    </div>\n'
        '  </div>\n'
        '  <!-- Row 2: #1 TABS (left) + #2 JUMP TO (right) -->\n'
        '  <div class="header-tabs-row">\n'
        '    <span class="row-label">#1 Tabs</span>\n'
        '    <div class="tab-nav">' + tab_buttons + '</div>\n'
        '    <div class="anchor-links" style="margin-left:auto">\n'
        '      <span class="row-label" style="margin-right:4px">#2 Jump to</span>\n'
        '      <a class="anchor-link default-jump" onclick="scrollToSection(\'section-summary\')">Summary</a>\n'
        '      <a class="anchor-link default-jump" onclick="scrollToSection(\'section-industries\')">Industries</a>\n'
        '      <a class="anchor-link default-jump" onclick="scrollToSection(\'section-sectors\')">Sectors</a>\n'
        '      <a class="anchor-link default-jump" onclick="scrollToSection(\'section-portfolio\')">Live Portfolio</a>\n'
        '      <a class="anchor-link default-jump" onclick="scrollToSection(\'section-stocks\')">Qualified Stocks</a>\n'
        '      <span id="group-links"></span>\n'
        '    </div>\n'
        '  </div>\n'
        '  <!-- Row 3: #3 TOGGLES (left) + #4 FILTERS (right) -->\n'
        '  <div class="header-controls-row">\n'
        '    <span class="row-label">#3 Toggles</span>\n'
        '    <button class="ctrl-btn active" id="btn-display-mode" onclick="toggleDisplayMode()">Company</button>\n'
        '    <button class="ctrl-btn" id="btn-value-mode" onclick="toggleValueMode()">&#10003;&#10007;</button>\n'
        '    <button class="ctrl-btn" id="btn-ratings" onclick="toggleRatings()">Show case ratings</button><span id="indsec-pills"></span>\n'
        '    <div style="margin-left:auto;display:flex;align-items:center;gap:6px">\n'
        '      <span class="row-label" id="toggles-label">#4 Filters</span>\n'
        '      <div id="header-tab-controls"></div>\n'
        '    </div>\n'
        '  </div>\n'
        '</div>\n'
        '<!-- FIX-1: Key panel overlay -->\n'
        '<div class="key-panel" id="key-panel"></div>\n'
        '<div class="main ratings-hidden">' + tab_containers + '</div>\n'
        '<div class="chart-panel" id="chart-panel">\n'
        '  <div id="chart-container" style="width:100%;min-height:calc(100vh - 200px)">Click a stock row to view chart</div>\n'
        '</div>\n'
        '<script>/* DATA_INJECTION_POINT */</script>\n'
        '<script>\n'
        + js +
        '\n</script>\n'
        '</body>\n'
        '</html>'
    )

    return html


def main():
    print("Loading data...")
    data_js = load_data()
    print("  Data JS: {:,} bytes".format(len(data_js)))

    # Auto-backup existing index.html before writing
    if OUTPUT_PATH.exists():
        backup_dir = PROJECT_DIR / "backups"
        backup_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M")
        backup_path = backup_dir / "index_{}.html".format(ts)
        shutil.copy2(OUTPUT_PATH, backup_path)
        print("  Pre-write backup: {}".format(backup_path))

    print("Building HTML...")
    html = build_html(data_js)
    html = html.replace("/* DATA_INJECTION_POINT */", data_js)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    size = os.path.getsize(OUTPUT_PATH)
    print("  Written: {} ({:,} bytes)".format(OUTPUT_PATH, size))
    # Post-write backup
    backup_dir = PROJECT_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    backup_path = backup_dir / "index_post_{}.html".format(ts)
    shutil.copy2(OUTPUT_PATH, backup_path)
    print("  Post-write backup: {}".format(backup_path))
    print("Done.")


if __name__ == "__main__":
    main()
