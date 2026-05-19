#!/usr/bin/env python3
"""Hotfix — s1UniverseCounts still uses old Probable Late/Early labels;
pill-pl-9 / pill-pl-10 CSS classes missing.

Created 2026-05-19 by SA (autonomous run).
"""
import hashlib, shutil, sys, tempfile
from pathlib import Path

BDB = Path("/sessions/admiring-jolly-noether/mnt/COWORK/master-dashboard/scripts/build_dashboard.py")


def _md5(p): return hashlib.md5(p.read_bytes()).hexdigest()


# Fix 1 — s1UniverseCounts label keys
F1_OLD = """  function s1UniverseCounts(rows) {
    var c = {'Probable Late':0,'Probable Early':0,'Plausible':0,'Possible':0,'None':0};
    for (var i = 0; i < rows.length; i++) {
      if (c[rows[i].rating] !== undefined) c[rows[i].rating]++;
    }
    return c;
  }"""

F1_NEW = """  function s1UniverseCounts(rows) {
    var c = {'Probable':0,'Plausible':0,'Possible':0,'None':0};
    for (var i = 0; i < rows.length; i++) {
      if (c[rows[i].rating] !== undefined) c[rows[i].rating]++;
    }
    return c;
  }"""

# Fix 2 — add pill-pl-9 + pill-pl-10 CSS
F2_OLD = """#s1-main-table .pill-pl-5 { background: #2e7d32; color: #fff; }
#s1-main-table .pill-pl-6 { background: #1e6a25; color: #fff; }
#s1-main-table .pill-pl-7 { background: #145718; color: #fff; }
#s1-main-table .pill-pl-8 { background: #08400d; color: #fff; }"""

F2_NEW = """#s1-main-table .pill-pl-5 { background: #2e7d32; color: #fff; }
#s1-main-table .pill-pl-6 { background: #1e6a25; color: #fff; }
#s1-main-table .pill-pl-7 { background: #145718; color: #fff; }
#s1-main-table .pill-pl-8 { background: #08400d; color: #fff; }
#s1-main-table .pill-pl-9 { background: #062f08; color: #fff; }
#s1-main-table .pill-pl-10 { background: #042205; color: #fff; }"""


def main():
    txt = BDB.read_text(encoding="utf-8")
    pre = _md5(BDB)
    print(f"  pre md5 {pre[:8]}")

    for name, old, new in [("F1 universeCounts", F1_OLD, F1_NEW), ("F2 pill CSS", F2_OLD, F2_NEW)]:
        n = txt.count(old)
        if n != 1:
            print(f"  ABORT {name}: matched {n}x")
            sys.exit(2)
        txt = txt.replace(old, new)
        print(f"  {name}: applied")

    exp = hashlib.md5(txt.encode()).hexdigest()
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, suffix=".py") as tf:
        tf.write(txt); tmp = Path(tf.name)
    if _md5(tmp) != exp: sys.exit("tmp md5 mismatch")
    shutil.copy2(tmp, BDB)
    if _md5(BDB) != exp: sys.exit("post-cp md5 mismatch")
    tmp.unlink()
    print(f"  post md5 {exp[:8]}  WRITTEN")

    import py_compile
    py_compile.compile(str(BDB), doraise=True)
    print("  py_compile OK")


if __name__ == "__main__":
    main()
