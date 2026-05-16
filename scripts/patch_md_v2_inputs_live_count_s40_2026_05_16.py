"""
=============================================================================
PATCHER — P5 (S40, 16-May-26) — Inputs supergroup live stock count (A1)
=============================================================================
Adds a parenthesised live row-count alongside the "Inputs" supergroup
column-header label on every tab that carries one (Stage 1-4 + V2 PI/PO/
ST/CT). Count updates whenever the table's tbody mutates (rating-tile
filter change, sort, etc.).

Architecture: ONE self-contained IIFE injected at the end of the embedded
JS. The module:
  - Scans the document for table elements that contain a `th.gh-inputs`.
  - For each such table, wraps the existing "Inputs" text in a `.inputs-text`
    span and appends a `.inputs-count` span; updates the span text on every
    tbody childList mutation.
  - A top-level MutationObserver on document.body catches lazy-rendered
    tables (other V2 tabs are not in the DOM until first switchTab).

No per-tab edits required; works across all 8 tabs from one injection.

Edits:
  1 JS injection   after  `/* MD-V2-CHROME-PARITY-MARKER-JS-END */`
  1 CSS injection  after  `#s1-main-table thead .gh-inputs { color: #555; }`

Per D-MD-INFRA-5: text-mode I/O.
=============================================================================
"""
from __future__ import annotations
import ast
import datetime as _dt
import difflib
import hashlib
import os
import py_compile
import subprocess
import sys
import tempfile

REPO_ROOT_HINT = "master-dashboard"
TARGET_REL     = os.path.join("scripts", "build_dashboard.py")
MARKER         = "MD-V2-S40-INPUTS-LIVE-COUNT"
BAK_TAG        = "inputs-live-count"
ENABLE_PY_COMPILE = True

# ----- EDIT 1: JS injection -----
JS_ANCHOR = """})();
/* MD-V2-CHROME-PARITY-MARKER-JS-END */
"""

JS_REPLACEMENT = """})();
/* MD-V2-CHROME-PARITY-MARKER-JS-END */

/* """ + MARKER + """: live row-count next to the "Inputs" supergroup
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

"""

# ----- EDIT 2: CSS -----
CSS_ANCHOR = "#s1-main-table thead .gh-inputs { color: #555; }"
CSS_REPLACEMENT = (
    "#s1-main-table thead .gh-inputs { color: #555; }\n"
    "/* " + MARKER + ": live row count appended to 'Inputs' supergroup\n"
    "   column-header. Slightly muted relative to the label. */\n"
    "th.gh-inputs .inputs-count { font-weight: 500; color: #888; margin-left: 4px; font-variant-numeric: tabular-nums; }"
)

EDITS: list[tuple[str, str, str]] = [
    ("JS",  JS_ANCHOR,  JS_REPLACEMENT),
    ("CSS", CSS_ANCHOR, CSS_REPLACEMENT),
]
EXPECTED_MARKER = 2


def _find_repo_root() -> str:
    cur = os.path.abspath(os.path.dirname(__file__))
    cand = os.path.abspath(os.path.join(cur, os.pardir))
    if os.path.basename(cand) == REPO_ROOT_HINT and os.path.exists(os.path.join(cand, ".git")):
        return cand
    walk = cur
    for _ in range(6):
        if os.path.exists(os.path.join(walk, ".git")):
            return walk
        walk = os.path.abspath(os.path.join(walk, os.pardir))
    raise SystemExit(f"[ABORT] cannot locate repo root from {cur}")


def _git_show_head_text(repo: str, rel: str) -> str:
    rel_posix = rel.replace(os.sep, "/")
    out = subprocess.run(
        ["git", "show", f"HEAD:{rel_posix}"],
        cwd=repo, check=True, capture_output=True,
    )
    return out.stdout.decode("utf-8")


def _wt_text(repo: str, rel: str) -> str:
    with open(os.path.join(repo, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def _md5_text(s: str) -> str:
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def main(argv: list[str]) -> int:
    test_mode = "--test" in argv
    repo = _find_repo_root()
    rel = TARGET_REL
    abs_target = os.path.join(repo, rel)

    print(f"[*] Repo root:      {repo}")
    print(f"[*] Target:         {rel}")
    print(f"[*] Marker:         {MARKER}")
    print(f"[*] Edits:          {len(EDITS)}")
    print(f"[*] Mode:           {'DRY-RUN (--test)' if test_mode else 'WRITE'}")

    head_src = _git_show_head_text(repo, rel)
    wt_src   = _wt_text(repo, rel)

    if _md5_text(wt_src) != _md5_text(head_src):
        msg = "Working tree diverges from HEAD."
        if test_mode:
            print(f"[WARN] {msg}")
            print("       Dry-run continues -- gates operate on HEAD source.")
        else:
            print(f"[ABORT] {msg}")
            return 2

    if MARKER in head_src:
        print(f"[OK] MARKER already in HEAD -- this patch has already shipped.")
        return 0
    if MARKER in wt_src:
        print(f"[OK] MARKER already in WT but not in HEAD -- applied but not committed yet.")
        return 0

    new_src = head_src
    for name, anchor, replacement in EDITS:
        n = new_src.count(anchor)
        print(f"[*] {name:<4} anchor matches: {n} (expected 1)")
        if n != 1:
            print(f"[ABORT] {name} anchor count != 1.")
            return 3
        new_src = new_src.replace(anchor, replacement, 1)

    n_marker = new_src.count(MARKER)
    if n_marker != EXPECTED_MARKER:
        print(f"[ABORT] expected {EXPECTED_MARKER} MARKER occurrences, got {n_marker}")
        return 4

    print(f"[*] Char delta:     {len(new_src) - len(head_src):+d}")

    if ENABLE_PY_COMPILE:
        try:
            ast.parse(new_src)
        except SyntaxError as e:
            print(f"[ABORT] ast.parse failed: {e}")
            return 5
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8") as tf:
            tf.write(new_src)
            tmp_py = tf.name
        try:
            py_compile.compile(tmp_py, doraise=True)
            print(f"[*] py_compile:     OK")
        except py_compile.PyCompileError as e:
            print(f"[ABORT] py_compile failed: {e}")
            return 6
        finally:
            try: os.unlink(tmp_py)
            except OSError: pass

    print("\n--- DIFF (first 50 lines) ---")
    diff_text = "".join(difflib.unified_diff(
        head_src.splitlines(keepends=True),
        new_src.splitlines(keepends=True),
        fromfile=f"HEAD:{rel}", tofile=f"PATCHED:{rel}", n=1,
    ))
    print("".join(diff_text.splitlines(keepends=True)[:50]))
    print("--- END DIFF (truncated) ---\n")

    if test_mode:
        print("[OK] DRY-RUN: gates passed.")
        return 0

    ts = _dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = abs_target + f".bak-pre-{BAK_TAG}-{ts}"
    with open(bak, "w", encoding="utf-8") as fh:
        fh.write(wt_src)
    print(f"[*] Backup:         {os.path.relpath(bak, repo)}")

    target_dir = os.path.dirname(abs_target)
    fd, tmp_out = tempfile.mkstemp(prefix=".patch-", suffix=".tmp", dir=target_dir)
    os.close(fd)
    with open(tmp_out, "w", encoding="utf-8") as fh:
        fh.write(new_src)
    os.replace(tmp_out, abs_target)

    after = _wt_text(repo, rel)
    if _md5_text(after) != _md5_text(new_src):
        print(f"[ABORT] Post-write md5 mismatch!")
        return 7
    if MARKER not in after:
        print("[ABORT] Post-write MARKER missing.")
        return 8

    print(f"[OK] WRITE complete. {len(after)} chars on disk.")
    print(f"[OK] Next: python scripts/build_dashboard.py && git add scripts/build_dashboard.py index.html && git commit && git push")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
