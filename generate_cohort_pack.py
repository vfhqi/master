#!/usr/bin/env python3
"""
generate_cohort_pack.py — the grade-anchoring Cohort Context Pack generator (Station 1 helper).

Design: design/02-COHORT-CONTEXT-PACK.md (decision D-AJ-11, the enriched D-BATCH-25 cache,
promoted to DEFAULT-ON). Backbone: design/00-SHARED-BUILD-CONVENTIONS.md.

What it does (deterministic; no mandatory LLM call):
  G1  Resolve cohort + members from databases/data/cohorts-v3.json (tickers[T] -> [{cohort_id,
      zone, members[]}]).
  G2  For each peer, locate source material in priority order: same-stage A&J memo -> any-stage
      memo -> 4-report family set (newest) -> legacy. (Triaging cold-start: peers have CF reports,
      no prior TCM04 memos, so the anchor is struck from peer CF content -- design 02 §1.3/§7.)
  G3  Staleness gate (D-BATCH-17): Change-sensitive (CF/memo) skip > 2 months; other > 6 months.
  G4  Token budget from dials (design 02 §5); default normal/normal = 13,000.
  G5  Build per-peer grade-anchoring cards by DETERMINISTIC EXTRACTION of the CF report's
      EXECUTIVE SUMMARY (BLUF), §9 Key Drivers Synthesis, and Investment Case Verdict.
  G6  Build the cohort grade-matrix (cold-start: peer grades [?]), anchor-data table, and a
      deterministic meta-narrative (cohort identity, member count, data-quality, base-rate steer).
  G7  Write the pack FUSE-safe (sandbox -> cp -> verify) to
      Files/_cohort-sector-summaries/{SUBJECT-TICKER}-{date}.md with a YAML front-matter block.
  G8  Return an audit dict for the sidecar `cohort_injection` field.

Optional LLM enrichment (NOT required for a valid pack): a richer meta-narrative / card prose
can be layered by an agent later; the deterministic pack is a complete, usable grade anchor.

Author: Watson (Systems Architect, Opus build), 2026-06-16.
"""

import json
import os
import re
import sys
import time
import shutil
import tempfile
import argparse
from pathlib import Path
from datetime import datetime, date
from typing import Optional


def cowork_root() -> Path:
    return Path(os.environ.get("COWORK_ROOT", ".")).resolve()


# ------------------------------------------------------------------
# Budget table (design 02 §5)
# ------------------------------------------------------------------

def compute_budget(dial_cohort: str, dial_sector: str) -> int:
    table = {
        ("lot", "lot"): 50000, ("lot", "normal"): 30000, ("lot", "little"): 20000,
        ("normal", "lot"): 25000, ("normal", "normal"): 13000, ("normal", "little"): 10000,
    }
    if dial_cohort == "little":
        return 5000
    return table.get((dial_cohort, dial_sector), 13000)


# ------------------------------------------------------------------
# G1 — resolve cohort
# ------------------------------------------------------------------

def resolve_cohort(subject: str, root: Path) -> dict:
    data = json.load(open(root / "databases" / "data" / "cohorts-v3.json", encoding="utf-8"))
    rec = data["tickers"].get(subject)
    if not rec:
        raise KeyError(f"{subject} not found in cohorts-v3.json tickers")
    info = rec[0] if isinstance(rec, list) else rec
    members = [m["ticker"] for m in info.get("members", []) if m.get("ticker") != subject]
    return {
        "cohort_id": info.get("cohort_id", "UNKNOWN"),
        "cohort_full": info.get("cohort", ""),
        "zone": info.get("zone", ""),
        "members": members,
    }


# ------------------------------------------------------------------
# G2/G3 — locate peer source + staleness
# ------------------------------------------------------------------

def _parse_date(s: str) -> Optional[date]:
    for fmt in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(s.strip()[:10], fmt).date()
        except Exception:
            continue
    return None


def _months_old(d: date) -> float:
    return (date.today() - d).days / 30.44


def locate_peer_source(peer: str, root: Path) -> dict:
    """Return {kind, path, date, stale, stale_reason}. Triaging: CF highlighted.md is the floor."""
    cf = root / "Files" / peer / "41-change-forces" / "highlighted.md"
    cf_raw = root / "Files" / peer / "41-change-forces" / "raw-AS.md"
    src = None
    kind = None
    if cf.exists() and cf.stat().st_size > 2000:
        src, kind = cf, "change_forces_highlighted"
    elif cf_raw.exists() and cf_raw.stat().st_size > 2000:
        src, kind = cf_raw, "change_forces_raw"
    if src is None:
        return {"kind": "none", "path": None, "date": None, "stale": True,
                "stale_reason": "no Change Forces report on disk"}
    # date: try to read "Extracted:" / "Highlighted:" line; else file mtime
    head = src.read_text(encoding="utf-8", errors="ignore")[:1500]
    m = re.search(r"(?:Extracted|Highlighted|Date)[:*\s]+(\d{4}-\d{2}-\d{2})", head)
    d = _parse_date(m.group(1)) if m else date.fromtimestamp(src.stat().st_mtime)
    stale = _months_old(d) > 2.0
    return {"kind": kind, "path": str(src.relative_to(root)), "date": d.isoformat(),
            "stale": stale, "stale_reason": (f"CF report {_months_old(d):.1f} months old" if stale else "")}


# ------------------------------------------------------------------
# G5 — deterministic extraction of grade-anchoring content
# ------------------------------------------------------------------

def _section(text: str, header_regex: str, max_chars: int) -> str:
    """Return the body under the first heading matching header_regex up to the next ## heading."""
    lines = text.splitlines()
    out, capture = [], False
    for ln in lines:
        if re.match(r"^##\s", ln):
            if capture:
                break
            if re.search(header_regex, ln, re.IGNORECASE):
                capture = True
                continue
        elif capture:
            out.append(ln)
    body = "\n".join(out).strip()
    return body[:max_chars]


def _company_oneliner(text: str, peer: str) -> str:
    m = re.search(r"^#\s+(.+?)\s+[—-]\s+Change Forces", text, re.MULTILINE)
    name = m.group(1).strip() if m else peer
    return name


def load_peer_card(peer: str, root: Path):
    p = root / "Files" / peer / "peer-card.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None


def _card_mr_line(card) -> str:
    mr = (card.get("grades") or {}).get("master_ratings") or {}
    parts = []
    for k in ("MR1", "MR2", "MR3", "MR4", "MR5", "MR6"):
        v = mr.get(k); g = v.get("grade") if isinstance(v, dict) else v
        if g:
            parts.append(f"{k}:[{g}]")
    return "  ".join(parts)


def _card_elem_line(card, codes=("E1", "E5", "E7", "E8", "E11")) -> str:
    el = (card.get("grades") or {}).get("elements") or {}
    return "  ".join(f"{c}:[{el[c]}]" for c in codes if el.get(c))


def build_peer_card(peer: str, src: dict, root: Path) -> str:
    """Grade-anchoring card. Prefers the persistent peer-card.json (real memo grades);
    falls back to deterministic Change-Forces extraction (cold-start) when no card exists."""
    _pc = load_peer_card(peer, root)
    if _pc:
        cls = _pc.get("classification") or {}
        med = (_pc.get("grades") or {}).get("mediocrity_gate", {}).get("result")
        lines = [
            f"## PEER: {peer}",
            f"source: persistent peer-card.json (stage {_pc.get('stage')}, {_pc.get('memo_date')})",
            f"classification: {cls.get('cohort_full') or cls.get('cohort_id')} | sector {cls.get('sector')} | industry {cls.get('industry')}",
            "",
            "### (a) Business / thesis one-liner",
            _pc.get("thesis_one_line") or "[thesis not captured]",
            "",
            "### (b) Real A&J memo grades -- LOAD-BEARING (peer has a graded memo)",
            "Master Ratings: " + (_card_mr_line(_pc) or "n/a"),
            "Elements: " + (_card_elem_line(_pc) or "n/a"),
            f"Mediocrity gate: {med}",
            "",
            "### (c) Key drivers",
            "; ".join(_pc.get("key_drivers") or []) or "n/a",
            "### (d) Key constraints",
            "; ".join(_pc.get("key_constraints") or []) or "n/a",
            "### (e) Recommendation / conviction / kill-shot",
            f"{_pc.get('recommendation')} | {_pc.get('conviction')} | kill-shot: {_pc.get('kill_shot')}",
            "",
        ]
        return "\n".join(lines)
    if src["kind"] == "none":
        return (f"## PEER: {peer}\nsource: none\n\n"
                f"### (c) Prior A&J memo grades — same stage\nNo prior memo and no Change Forces "
                f"report on disk — grades unavailable; peer excluded from anchor.\n")
    text = (root / src["path"]).read_text(encoding="utf-8", errors="ignore")
    name = _company_oneliner(text, peer)
    bluf = _section(text, r"EXECUTIVE SUMMARY|BLUF", 2600)
    verdict = ""
    mv = re.search(r"(?:One-line verdict|Investment Case Verdict)[:\s]*(.+)", bluf)
    if mv:
        verdict = mv.group(1).strip()[:600]
    drivers = _section(text, r"§9|Key Drivers Synthesis", 1400)
    card = []
    card.append(f"## PEER: {peer}")
    card.append(f"source_report: {src['path']}")
    card.append(f"source_date: {src['date']}    staleness: {'STALE' if src['stale'] else 'fresh'}")
    card.append("")
    card.append("### (a) Business one-liner")
    card.append(f"{name} (see Change Forces BLUF below for cohort-specific positioning).")
    card.append("")
    card.append("### (b) Primary change forces (from CF BLUF)")
    card.append(bluf if bluf else "[CF BLUF not extractable — read source report directly]")
    card.append("")
    card.append("### (c) Prior A&J memo grades — same stage [LOAD-BEARING]")
    card.append("No prior A&J memo on disk for this peer (cold-start). Grades [?]; strike the "
                "subject's grade against peer CF content below, not against peer memo grades.")
    card.append("E1: [?]  E5: [?]  E7: [?]  E8: [?]  E11: [?]")
    if verdict:
        card.append("")
        card.append("### (c-ii) Peer one-line investment verdict (CF)")
        card.append(verdict)
    if drivers:
        card.append("")
        card.append("### (d) Key drivers synthesis (anchor data)")
        card.append(drivers)
    card.append("")
    return "\n".join(card)


# ------------------------------------------------------------------
# G6 — cohort-level sections (deterministic)
# ------------------------------------------------------------------

def build_cohort_sections(coh: dict, peers_used: list, peers_skipped: list, stage: str, peer_cards: Optional[dict] = None) -> str:
    out = []
    out.append("## COHORT COMPARATIVE TABLES")
    out.append("")
    out.append(f"### Grade matrix — {stage} stage — generated {date.today().isoformat()}")
    out.append("")
    out.append("| Ticker | MR1 | MR3 | MR4 | MR5 | Mediocrity |")
    out.append("|--------|-----|-----|-----|-----|-----------|")
    out.append("| SUBJECT* | — | — | — | — | — |")
    for p in peers_used:
        _c = (peer_cards or {}).get(p["ticker"])
        if _c:
            _mr = (_c.get("grades") or {}).get("master_ratings") or {}
            def _g(k, _mr=_mr):
                v = _mr.get(k)
                return (v.get("grade") if isinstance(v, dict) else v) or "?"
            _med = (_c.get("grades") or {}).get("mediocrity_gate", {}).get("result") or "?"
            out.append(f"| {p['ticker']} | [{_g('MR1')}] | [{_g('MR3')}] | [{_g('MR4')}] | [{_g('MR5')}] | {_med} |")
        else:
            out.append(f"| {p['ticker']} | [?] | [?] | [?] | [?] | ? |")
    out.append("")
    out.append("\\* = subject (filled by writer). Real grades shown where a peer A&J memo exists; "
               "[?] = cold-start peer (CF-only).")
    out.append("")
    out.append("## COHORT META-NARRATIVE")
    out.append("")
    n_used, n_skip = len(peers_used), len(peers_skipped)
    n_graded = sum(1 for p in peers_used if (peer_cards or {}).get(p["ticker"]))
    out.append(f"Cohort {coh['cohort_id']} — {coh['cohort_full']} (zone: {coh['zone']}). "
               f"{n_used} peer(s) anchored, {n_skip} skipped stale, {n_graded} with a graded A&J memo.")
    out.append("")
    out.append("Cohort-wide change picture: read each peer card's grades, drivers and CF BLUF for "
               "the specific internal/external forces; the cohort base rate is the grade "
               "distribution across peers that carry a graded A&J memo.")
    out.append("")
    out.append("Grade distribution: peer grade tokens are real where a peer carries a graded A&J "
               "memo, else [?] (cold-start). The grade anchor is real peer memo grades where "
               "available, peer CF content otherwise.")
    out.append("")
    if n_graded:
        out.append("Base-rate steer for the writer: a real cohort base rate exists (grade distribution "
                   "in the matrix above). Strike the subject's grades against it and state the cohort "
                   "base rate explicitly per D-BATCH-25; note which peers are graded vs cold-start.")
    else:
        out.append("Base-rate steer for the writer: strike the subject's grades against this cohort's "
                   "CF-evidenced change momentum and competitive position. Because no peer memo grades "
                   "exist yet, defend each grade explicitly from peer CF specifics. State 'cohort grade "
                   "anchor is cold-start (CF-derived, no peer memos)' in Section F.")
    out.append("")
    out.append(f"Data quality note: {n_used}/{n_used + n_skip} peer(s) anchored; {n_graded} carry a "
               f"graded A&J memo. Treat the anchor as directional where graded coverage is thin.")
    out.append("")
    return "\n".join(out)


# ------------------------------------------------------------------
# Front matter + FUSE-safe write
# ------------------------------------------------------------------

def front_matter(subject, stage, coh, peers_used, peers_skipped, tokens, cap,
                 dial_cohort, dial_sector) -> str:
    return ("---\n"
            f'pack_subject: "{subject}"\n'
            f'pack_stage: "{stage}"\n'
            f'generated_at: "{date.today().isoformat()}"\n'
            f'cohort_id: "{coh["cohort_id"]}"\n'
            f'cohort_full: "{coh["cohort_full"]}"\n'
            f"peers_used_count: {len(peers_used)}\n"
            f"peers_skipped_stale_count: {len(peers_skipped)}\n"
            f"tokens_consumed: {tokens}\n"
            f"budget_cap: {cap}\n"
            f"summary_of_summaries_used: false\n"
            f'dial_cohort: "{dial_cohort}"\n'
            f'dial_sector: "{dial_sector}"\n'
            "---\n")


def fuse_safe_write(dest: Path, text: str) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmpdir = "/tmp" if os.path.isdir("/tmp") and shutil.disk_usage("/tmp").free > 5_000_000 else "/dev/shm"
    fd, tmpname = tempfile.mkstemp(dir=tmpdir, suffix=".md")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(text)
    shutil.copyfile(tmpname, dest)
    # verify by content + a key marker; vanish-guard
    for _ in range(3):
        if dest.exists() and dest.stat().st_size > 0:
            got = dest.read_text(encoding="utf-8", errors="ignore")
            if "pack_subject" in got[:200] and len(got) >= len(text) * 0.98:
                os.unlink(tmpname)
                return
        time.sleep(2)
        shutil.copyfile(tmpname, dest)
    os.unlink(tmpname)
    raise IOError(f"cohort pack write verify failed (FUSE): {dest}")


# ------------------------------------------------------------------
# Main entry
# ------------------------------------------------------------------

def generate_cohort_pack(subject_ticker: str, stage: str = "triaging",
                         dial_cohort: str = "normal", dial_sector: str = "normal",
                         force_refresh: bool = False, root: Optional[Path] = None) -> dict:
    root = root or cowork_root()
    cache_dir = root / "Files" / "_cohort-sector-summaries"
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / f"{subject_ticker}-{date.today().isoformat()}.md"
    cap = compute_budget(dial_cohort, dial_sector)

    # cache hit?
    if dest.exists() and not force_refresh and dest.stat().st_size > 2000:
        return {"pack_path": str(dest.relative_to(root)), "cache_hit": True,
                "cohort_id": "", "cohort_full": "", "peers_used": [], "peers_skipped_stale": [],
                "tokens_consumed": 0, "budget_cap": cap,
                "summary_of_summaries_used": False,
                "dial_cohort": dial_cohort, "dial_sector": dial_sector}

    coh = resolve_cohort(subject_ticker, root)
    peers_used, peers_skipped, cards = [], [], []
    peer_cards = {}
    for peer in coh["members"]:
        _pc = load_peer_card(peer, root)
        if _pc:
            peer_cards[peer] = _pc
            peers_used.append({"ticker": peer, "source_type": "peer-card", "source_date": _pc.get("memo_date")})
            cards.append(build_peer_card(peer, {"kind": "card", "path": None, "date": _pc.get("memo_date"), "stale": False}, root))
            continue
        src = locate_peer_source(peer, root)
        if src["kind"] == "none" or src["stale"]:
            peers_skipped.append({"ticker": peer, "reason": src.get("stale_reason") or "no source"})
            continue
        peers_used.append({"ticker": peer, "source_type": src["kind"], "source_date": src["date"]})
        cards.append(build_peer_card(peer, src, root))

    tokens = sum(len(c) for c in cards) // 4  # rough token estimate
    body = (front_matter(subject_ticker, stage, coh, peers_used, peers_skipped, tokens, cap,
                         dial_cohort, dial_sector)
            + f"\n# COHORT CONTEXT PACK — {subject_ticker} — {coh['cohort_id']}\n\n"
            + build_cohort_sections(coh, peers_used, peers_skipped, stage, peer_cards) + "\n"
            + "## PER-PEER GRADE-ANCHORING CARDS\n\n"
            + "\n".join(cards))
    fuse_safe_write(dest, body)

    return {"pack_path": str(dest.relative_to(root)), "cache_hit": False,
            "cohort_id": coh["cohort_id"], "cohort_full": coh["cohort_full"],
            "peers_used": peers_used, "peers_skipped_stale": peers_skipped,
            "tokens_consumed": tokens, "budget_cap": cap,
            "summary_of_summaries_used": False,
            "dial_cohort": dial_cohort, "dial_sector": dial_sector}


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generate a cohort grade-anchoring pack")
    ap.add_argument("--subject", required=True, help="subject TICKER-EX")
    ap.add_argument("--stage", default="triaging", choices=("triaging", "esa", "dd"))
    ap.add_argument("--dial-cohort", default="normal", choices=("lot", "normal", "little"))
    ap.add_argument("--dial-sector", default="normal", choices=("lot", "normal", "little"))
    ap.add_argument("--force-refresh", action="store_true")
    args = ap.parse_args()
    res = generate_cohort_pack(args.subject, args.stage, args.dial_cohort, args.dial_sector,
                               args.force_refresh)
    print(json.dumps(res, indent=2))
