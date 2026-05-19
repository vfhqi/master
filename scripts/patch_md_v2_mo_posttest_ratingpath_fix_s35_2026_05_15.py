#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# patch_md_v2_mo_posttest_ratingpath_fix_s35_2026_05_15.py
# =============================================================================
# MD V2 Master Dashboard - Session 35 (15-May-26)
# Request 1: the Master Overview page shows "-" for every Post-test indicator
# cell (Breakout, Advancing, Breakdown 50D/150D/200D) in BOTH the top summary
# table and the 946-row matrix below it.
#
# Root cause: the Master Overview row model (MO_ROWS) reads the five Post-test
# indicator ratings via ratingPath 'group:indicators:<key>', i.e.
# md_v2.indicators.<key>.rating. But in the data, md_v2.indicators.<key> is a
# bare boolean (e.g. false) - it has no .rating. The rated objects live under
# md_v2.post_indicators.<key>.rating - the exact source the Post-indicators tab
# itself reads (poGetRows: row.md_v2.post_indicators). moReadRating() therefore
# falls through to 'None' for every stock on all five rows.
#
# Fix: repoint the five Post-test indicator MO_ROWS ratingPaths from
# 'group:indicators:' to 'group:post_indicators:'. One substring, exactly five
# occurrences, all five are the broken rows (verified: grep -c 'group:indicators:'
# == 5; pre_indicators rows use 'group:pre_indicators:' and are unaffected).
# Fixing MO_ROWS fixes the summary table and the matrix in one edit - both
# share MO_ROWS.
#
# Discipline (matches the S33 setups-split patcher house style):
#  - Reads SOURCE from `git show HEAD:scripts/build_dashboard.py` (git object
#    store, immune to the COWORK FUSE stale-cache bug). Never reads the
#    working-tree file as the transform source.
#  - Idempotent: exits 0 if the old anchor is already absent (already patched).
#  - Safety gate: aborts if the working-tree build_dashboard.py differs from
#    HEAD and the old anchor is still present (unexpected state - the patcher
#    is designed to be run Windows-side, where the working tree == HEAD).
#  - The anchor edit asserts an exact occurrence count (5); any miss aborts.
#  - py_compile validates the result before it is written.
#  - Backs up the working-tree file to .bak-pre-mo-posttest-ratingpath-<ts>.
#
# Usage:
#   python scripts/patch_md_v2_mo_posttest_ratingpath_fix_s35_2026_05_15.py
#   python scripts/patch_md_v2_mo_posttest_ratingpath_fix_s35_2026_05_15.py --test SRC OUT
# =============================================================================
import sys, os, subprocess, hashlib, py_compile, datetime

OLD_ANCHOR = "ratingPath:'group:indicators:"
NEW_ANCHOR = "ratingPath:'group:post_indicators:"
EXPECT_N   = 5
TARGET     = os.path.join("scripts", "build_dashboard.py")


def transform(src):
    c = src.count(OLD_ANCHOR)
    if c != EXPECT_N:
        raise AssertionError(
            "[mo-posttest-ratingpath] expected %d occurrence(s) of %r, found %d"
            % (EXPECT_N, OLD_ANCHOR, c))
    out = src.replace(OLD_ANCHOR, NEW_ANCHOR)
    # post-conditions: old gone, new count went up by exactly EXPECT_N.
    if OLD_ANCHOR in out:
        raise AssertionError("[mo-posttest-ratingpath] old anchor still present after replace")
    if out.count(NEW_ANCHOR) != src.count(NEW_ANCHOR) + EXPECT_N:
        raise AssertionError("[mo-posttest-ratingpath] new-anchor count did not rise by %d" % EXPECT_N)
    return out


def _git_head_source():
    out = subprocess.check_output(["git", "show", "HEAD:scripts/build_dashboard.py"])
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
    if OLD_ANCHOR not in wt:
        print("Already patched (old anchor %r absent in working tree). Nothing to do." % OLD_ANCHOR)
        return 0

    head_src = _git_head_source()
    wt_md5  = hashlib.md5(wt.encode("utf-8", "replace")).hexdigest()
    head_md5 = hashlib.md5(head_src.encode("utf-8")).hexdigest()
    if wt_md5 != head_md5:
        print("ABORT: working-tree build_dashboard.py does not match HEAD and the")
        print("       old anchor is still present. Unexpected state -- resolve before patching.")
        print("       working-tree md5: %s" % wt_md5)
        print("       HEAD         md5: %s" % head_md5)
        print("       (If HEAD is clean, run `git checkout -- scripts/build_dashboard.py` first.)")
        return 3

    out = transform(head_src)

    # backup the working-tree file, then write via .tmp + atomic replace.
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = TARGET + ".bak-pre-mo-posttest-ratingpath-" + ts
    with open(bak, "w", encoding="utf-8") as f:
        f.write(wt)
    tmp = TARGET + ".tmp-s35"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(out)
    py_compile.compile(tmp, doraise=True)
    os.replace(tmp, TARGET)

    print("OK: Master Overview post-test indicator ratingPath fix applied.")
    print("    backup : %s" % bak)
    print("    target : %s  (%d -> %d bytes)" % (TARGET, len(head_src), len(out)))
    print("    next   : python scripts/build_dashboard.py  ->  git add -A  ->  commit  ->  push")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
