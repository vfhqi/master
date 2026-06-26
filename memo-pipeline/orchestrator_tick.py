#!/usr/bin/env python3
"""
orchestrator_tick.py -- Block B multi-batch deterministic orchestrator tick.

FREE, no-LLM. Spans ALL live memo batches. One tick:
  1. Enumerate live batch state files (mock/verify/test/fixture filtered, same
     convention as the Repository build_functional._load_pipeline_phases).
  2. For each batch with any blocked stock, run gate_monitor.poll() to release
     report-floor and E6 gates (deterministic filesystem check; free).
  3. Run orchestrate_memo.advance() per batch (deterministic stations + gate
     surfacing). Per-batch try/except so one bad batch cannot kill the tick.
  4. Classify every live stock into one queue:
       action_queue  -- awaiting Richard (single canonical signal, see awaiting_richard()).
       work_queue    -- needs an LLM agent (strawman | writer | judge); what the
                        costed dispatch layer consumes, respecting do-once + cap.
       researching   -- blocked on key-question research (waiting_e6).
       in_motion     -- deterministic station running, no human/LLM needed now.
       terminal      -- closed/published/completed (no-op).
  5. Emit a consolidated report to briefings/state/tick-report.json (atomic) and
     APPEND one line to briefings/state/tick-log.jsonl (never overwrite).

This module NEVER calls an LLM, so ticking is free and can run every ~15 min.
The dispatch layer (orchestrator_dispatch.py) reads tick-report.json.

Canonical "awaiting Richard" rule (Block B, single source of truth):
  In full-autonomy mode a fresh ESA/DD memo at waiting_e1 is NOT yet Richard's --
  the strawman agent owes a pre-draft first; it routes to the work queue. A memo
  is awaiting Richard iff strawman_ready is True (strawman parked for review) OR
  gate_state == waiting_e4 (key-question list proposed) OR waiting_for_richard is
  True (parked-for-Richard, or set explicitly by the strawman park step).

Author: Watson (Systems Architect, Opus build), 2026-06-25 (Block B autonomy).
"""

import os
import sys
import json
import time
import tempfile
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import memo_state as ms
import gate_monitor
import orchestrate_memo

MOCK_TOKENS = ("mock", "verify", "test", "fixture")
RICHARD_GATES = ("waiting_e1", "waiting_e4")
TERMINAL = ("closed", "published", "completed")


def root() -> Path:
    return Path(os.environ.get("COWORK_ROOT", ".")).resolve()


def is_mock(batch_id: str) -> bool:
    return any(tok in (batch_id or "") for tok in MOCK_TOKENS)


def live_batch_files(R: Path) -> list:
    """All live memo-batch state files, mock/verify/test/fixture filtered."""
    d = R / "briefings" / "state"
    out = []
    if not d.exists():
        return out
    for p in sorted(d.glob("memo-batch-*-state.json")):
        if is_mock(p.name):
            continue
        out.append(p)
    return out


def awaiting_richard(blk: dict) -> bool:
    """Canonical single-source signal: is this memo waiting on Richard NOW?

    waiting_e1-without-strawman is excluded on purpose: in full-autonomy mode the
    strawman agent owes a pre-draft before the memo reaches Richard, so it routes
    to the work queue (strawman dispatch), not the action queue.
    """
    if blk.get("strawman_ready"):
        return True
    if blk.get("gate_state") == "waiting_e4":
        return True
    if blk.get("waiting_for_richard"):
        return True
    return False


def richard_need(blk: dict) -> str:
    """Plain-English description of what Richard must do."""
    gs = blk.get("gate_state")
    if blk.get("strawman_ready"):
        return "review proposed sponsor answers + proposed key questions (one pass)"
    if gs == "waiting_e4":
        return "approve or amend the proposed key-question list"
    if blk.get("status") == "parked":
        return "parked: " + str(blk.get("parked_reason") or "review")
    if gs == "waiting_e1":
        return "answer sponsor Q&A (thesis, lead pillar, kill-shot, catalyst)"
    return "review"


def work_need(blk: dict, stage: str, ticker: str, R: Path) -> str:
    """What LLM agent (if any) this stock needs next. Empty string = none.
    Deterministic, derived from STATE not logs. The dispatch layer enforces
    do-once + concurrency cap on top of this."""
    s = blk.get("status")
    gs = blk.get("gate_state")
    if stage in ("esa", "dd") and gs == "waiting_e1" and not blk.get("strawman_ready"):
        return "strawman"
    if s == "in_production":
        memo = R / "Files" / ticker / "A-J-memo" / "memo.md"
        if not memo.exists():
            return "writer"
    if s == "rendered":
        return "judge"
    return ""


def classify(blk: dict, stage: str, ticker: str, batch_id: str, R: Path) -> dict:
    s = blk.get("status")
    gs = blk.get("gate_state")
    base = {"ticker": ticker, "batch_id": batch_id, "stage": stage,
            "status": s, "gate_state": gs}
    if s in TERMINAL:
        base["queue"] = "terminal"
        return base
    if awaiting_richard(blk):
        base["queue"] = "action"
        base["need"] = richard_need(blk)
        return base
    w = work_need(blk, stage, ticker, R)
    if w:
        base["queue"] = "work"
        base["agent"] = w
        return base
    if s == "blocked" and gs == "waiting_e6":
        base["queue"] = "researching"
        base["detail"] = "awaiting key-question research reports"
        return base
    base["queue"] = "in_motion"
    return base


def tick(do_advance: bool = True, do_poll: bool = True) -> dict:
    R = root()
    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "batches": [], "errors": [],
        "action_queue": [], "work_queue": [],
        "researching": [], "in_motion": [], "terminal_count": 0,
    }
    for path in live_batch_files(R):
        try:
            st = ms.read_state(path)
        except Exception as e:
            report["errors"].append({"file": path.name, "error": str(e)[:200]})
            continue
        batch_id = st.get("batch_id", path.stem)
        if is_mock(batch_id):
            continue
        stage = st.get("stage", "triaging")
        if do_poll and any(b.get("status") == "blocked" for b in st["stocks"].values()):
            try:
                gate_monitor.poll(batch_id)
            except Exception as e:
                report["errors"].append({"batch": batch_id, "stage": "poll", "error": str(e)[:200]})
        if do_advance:
            try:
                orchestrate_memo.advance(batch_id, writer_mode="prompt")
            except Exception as e:
                report["errors"].append({"batch": batch_id, "stage": "advance", "error": str(e)[:200]})
        try:
            st = ms.read_state(path)
        except Exception as e:
            report["errors"].append({"file": path.name, "error": str(e)[:200]})
            continue
        bsummary = {"batch_id": batch_id, "stage": stage, "stocks": {}}
        for ticker, blk in st["stocks"].items():
            c = classify(blk, stage, ticker, batch_id, R)
            bsummary["stocks"][ticker] = c["queue"]
            q = c["queue"]
            if q == "action":
                report["action_queue"].append(c)
            elif q == "work":
                report["work_queue"].append(c)
            elif q == "researching":
                report["researching"].append(c)
            elif q == "in_motion":
                report["in_motion"].append(c)
            elif q == "terminal":
                report["terminal_count"] += 1
        report["batches"].append(bsummary)
    return report


def _atomic_write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, separators=(",", ":"), ensure_ascii=False)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise
    with open(path, "r", encoding="utf-8") as f:
        if json.load(f) != obj:
            raise IOError("tick-report write verify failed: " + str(path))


def write_report(report: dict, R: Path = None) -> Path:
    R = R or root()
    rp = R / "briefings" / "state" / "tick-report.json"
    _atomic_write_json(rp, report)
    logp = R / "briefings" / "state" / "tick-log.jsonl"
    line = {"ts": report["generated_at"],
            "action": len(report["action_queue"]),
            "work": len(report["work_queue"]),
            "researching": len(report["researching"]),
            "in_motion": len(report["in_motion"]),
            "terminal": report["terminal_count"],
            "errors": len(report["errors"])}
    with open(logp, "a", encoding="utf-8") as f:
        f.write(json.dumps(line, separators=(",", ":")) + "\n")
    return rp


def human_summary(report: dict) -> str:
    L = []
    L.append("ORCHESTRATOR TICK -- " + report["generated_at"])
    aq = report["action_queue"]
    L.append("")
    L.append("AWAITING YOU (%d):" % len(aq))
    if not aq:
        L.append("  (none)")
    for c in aq:
        L.append("  %-10s %-4s %-22s -> %s" % (c["ticker"], c["stage"][:4], c["batch_id"], c.get("need", "")))
    wq = report["work_queue"]
    L.append("")
    L.append("AGENT WORK PENDING (%d): %s" % (
        len(wq), ", ".join("%s:%s" % (c["ticker"], c["agent"]) for c in wq) or "(none)"))
    L.append("RESEARCHING (%d) | IN MOTION (%d) | TERMINAL (%d) | ERRORS (%d)" % (
        len(report["researching"]), len(report["in_motion"]),
        report["terminal_count"], len(report["errors"])))
    for e in report["errors"]:
        L.append("  ERROR: " + json.dumps(e))
    return "\n".join(L)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Block B multi-batch orchestrator tick (free, no-LLM)")
    ap.add_argument("--no-advance", action="store_true", help="classify only; do not run advance()")
    ap.add_argument("--no-poll", action="store_true", help="do not run gate_monitor.poll()")
    ap.add_argument("--no-write", action="store_true", help="do not write tick-report / tick-log")
    ap.add_argument("--json", action="store_true", help="print full JSON report")
    args = ap.parse_args()
    rep = tick(do_advance=not args.no_advance, do_poll=not args.no_poll)
    if not args.no_write:
        rp = write_report(rep)
        print("wrote " + str(rp))
    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print(human_summary(rep))
