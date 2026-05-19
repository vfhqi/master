#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# patch_md_v2_s37_followup_2026_05_15.py
# =============================================================================
# MD V2 Master Dashboard - Session 37 follow-up (15-May-26)
# Pushes through the remaining S36-brief items that S36 left for a follow-up.
#
# Items in this patcher:
#   * Post-farfalle pattern .label fields renamed to match the S36 shortLabels
#     (so the .gcap <b>...</b> caption titles match the rating-tile titles -
#     fixes the half-renamed state Chrome verification flagged after S36).
#   * .s1-intro page-description ribbon: drop the max-width:920px so it wraps
#     full-width (Richard: "should always wrap to full width and use the full
#     space - be less tall vertically").
#   * Tier-chip rendering on every tile (pi/po/st/ct) always emits the
#     canonical three-chip set {Possible, Plausible, Probable} with the count
#     for each tier, including zeros where the pattern's rating ladder can't
#     reach a tier (Richard's Q5 confirm: show zero, more helpful).
#
# DEFERRED to a later patcher (captured in task #6 backlog):
#   * Per-tile thresholds for stage tabs (move "thresholds X/X" from group
#     caption to per-rating-tile)
#   * Inputs supergroup header live stock count
#   * Column-header alignment fixes (Company/ticker + Industry/sector
#     left-align; centred-but-too-far-left)
#   * Probing bet description correction (Richard parked at his request)
#   * Sticky inputs/scope ribbon
#   * Responsive contracted column headers
#   * Android tablet header overflow
#   * Combine indicator/setup/test buttons (Richard "Hold off")
#   * Comprehensive caption rewrites — Watson's read after surveying the
#     code is that the existing tile + supergroup descriptions on Stage 1-4
#     and on most pattern tabs ALREADY match Richard's signposted +
#     technical-specific style example (demi-bold, underline, numbered tests,
#     intro line). A current-state survey doc is saved alongside this patcher
#     so Richard can scan all captions in one place and mark up the ones that
#     genuinely need polish.
#
# Same house style (FUSE-immune source via `git show HEAD:`, idempotent on
# MARKER, working-tree-vs-HEAD safety gate, exact anchor count assertions,
# py_compile pre-write, pre-write backup).
#
# Usage:
#   python scripts/patch_md_v2_s37_followup_2026_05_15.py
#   python scripts/patch_md_v2_s37_followup_2026_05_15.py --test SRC OUT
# =============================================================================
import sys, os, subprocess, hashlib, py_compile, datetime

MARKER = "MD-V2-S37-FOLLOWUP-MARKER"
TARGET = os.path.join("scripts", "build_dashboard.py")


# Each entry: (label, old_string, new_string, expected_count).
EDITS = [
    # ---- 1. Post-farfalle pattern .label fields - match the S36 shortLabels ----
    ("po-label-bd50",
     '"label": "Breakdown through 50-day MA",',
     '"label": "Negatively breaking through ST trend (50D MA)",',
     1),
    ("po-label-bd150",
     '"label": "Breakdown through 150-day MA",',
     '"label": "Negatively breaking through MT trend (150D MA)",',
     1),
    ("po-label-bd200",
     '"label": "Breakdown through 200-day MA",',
     '"label": "Negatively breaking through LT trend (200D MA)",',
     1),

    # ---- 2. .s1-intro: drop max-width so page-description ribbon wraps full-width ----
    ("css-s1intro-fullwidth",
     ".s1-intro { background: var(--bg-card, #fbfaf5); border: 1px solid var(--border, #e0dcc8); border-radius: 4px; padding: 12px 16px; margin-bottom: 14px; font-size: 12px; color: var(--text-muted, #666); max-width: 920px; }",
     "/* MD-V2-S37-FOLLOWUP-MARKER: .s1-intro is the page-description ribbon at the top of every tab. Dropped max-width so it wraps full-width and uses the row, rather than being a tall narrow column. */\n.s1-intro { background: var(--bg-card, #fbfaf5); border: 1px solid var(--border, #e0dcc8); border-radius: 4px; padding: 12px 16px; margin-bottom: 14px; font-size: 12px; color: var(--text-muted, #666); }",
     1),

    # ---- 3. Tier-chip rendering on every tile: always emit the canonical
    #         three-chip set {Possible, Plausible, Probable} (zeros included).
    #         The 4-occurrence anchor is the loop header that drives the chip emission.
    ("tier-chip-loop-canonical",
     "for (var c = 0; c < pat.tierLadder.length; c++) {\n        var tier = pat.tierLadder[c];",
     "for (var c = 0; c < 3; c++) {  /* MD-V2-S37-FOLLOWUP-MARKER: canonical 3-tier chip set */\n        var tier = ['Possible','Plausible','Probable'][c];",
     4),
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
        print("ABORT: working-tree build_dashboard.py does not match HEAD and the S37 marker is absent.")
        print("       working-tree md5: %s" % wt_md5)
        print("       HEAD         md5: %s" % head_md5)
        return 3

    out = transform(head_src)

    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = TARGET + ".bak-pre-s37-followup-" + ts
    with open(bak, "w", encoding="utf-8") as f:
        f.write(wt)
    tmp = TARGET + ".tmp-s37"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(out)
    py_compile.compile(tmp, doraise=True)
    os.replace(tmp, TARGET)

    print("OK: S37 follow-up patcher applied.")
    print("    backup : %s" % bak)
    print("    target : %s  (%d -> %d chars)" % (TARGET, len(head_src), len(out)))
    print("    next   : python scripts/build_dashboard.py  ->  git add -A  ->  commit  ->  push")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
