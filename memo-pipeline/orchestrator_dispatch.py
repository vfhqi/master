#!/usr/bin/env python3
"""
orchestrator_dispatch.py -- Block B autonomous AI dispatch agent.

Reads tick-report.json (written by orchestrator_tick.py) and selects work
items for the costed dispatch layer. Handles:
  - do-once guard (never re-draft a strawman already marked strawman_ready)
  - concurrency cap (max 3 per dispatch run, configurable)
  - brief-time batch_id guard (reject mock/verify/test/fixture IDs at brief time)
  - context preparation for strawman generation (reads CF/BF floors + brief-card)
  - state writing after strawman generation (capture_sponsor_answers + advance +
    capture_key_questions + strawman_ready flag)
  - brief creation helper (init_batch wrapper with ID guard)

This module NEVER generates LLM content itself. The calling SA session (or
scheduled dispatch task) reads context via prepare_strawman_context(), generates
proposed answers + key questions inline, then commits via write_strawman_complete().

Author: Watson (Systems Architect, Sonnet), 2026-06-26 (Block B dispatch).
"""

import os, sys, json, time, argparse, subprocess, tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: add memo-pipeline to path so we can import memo_state etc.
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import memo_state as ms
import orchestrate_memo

MOCK_TOKENS = ("mock", "verify", "test", "fixture")
DISPATCH_CAP = 3   # concurrency cap per run


def cowork_root() -> Path:
    """Resolve COWORK root: env override, sandbox auto-detect, or CWD."""
    if os.environ.get("COWORK_ROOT"):
        return Path(os.environ["COWORK_ROOT"]).resolve()
    candidates = sorted(Path("/sessions").glob("*/mnt/COWORK")) if Path("/sessions").exists() else []
    if candidates:
        return candidates[0].resolve()
    return Path(".").resolve()


# ---------------------------------------------------------------------------
# Guard: reject bad batch IDs at brief time (before any file is written)
# ---------------------------------------------------------------------------

def guard_batch_id(batch_id: str) -> None:
    """Raise ValueError if batch_id contains a filter token that would silently
    suppress the batch in the tick and Repository build.
    Convention: real batches use triaging-<tag>-<YYYYMMDD>, esa-<tag>-<YYYYMMDD>,
    dd-<tag>-<YYYYMMDD>.  Filter tokens: mock, verify, test, fixture."""
    bad = [t for t in MOCK_TOKENS if t in (batch_id or "")]
    if bad:
        raise ValueError(
            f"batch_id '{batch_id}' contains filter token(s) {bad!r}. "
            "Real batch IDs must NOT contain: mock, verify, test, fixture. "
            "Convention: triaging-<cohort_tag>-<YYYYMMDD>."
        )


# ---------------------------------------------------------------------------
# Brief creation helper
# ---------------------------------------------------------------------------

def create_brief(batch_id: str, stage: str, tickers: list,
                 cohort: str = None, dials: dict = None,
                 thematics_decision: str = "proceed",
                 priority: str = "normal") -> Path:
    """Create a new memo-pipeline batch state file with batch_id guard.
    Returns the path to the created state file."""
    guard_batch_id(batch_id)
    dials = dials or {"trust": "normal", "cohort": "normal", "sector": "normal"}
    R = cowork_root()
    path = ms.init_batch(
        batch_id,
        shape="individual",
        stage=stage,
        cohort=cohort,
        dials=dials,
        thematics_decision=thematics_decision,
        priority=priority,
        tickers=tickers,
        root=R,
    )
    return path


# ---------------------------------------------------------------------------
# Work selection
# ---------------------------------------------------------------------------

def select_work(max_concurrent: int = DISPATCH_CAP) -> list:
    """Read tick-report.json and return up to max_concurrent work items,
    filtered by do-once guard (skip strawman if strawman_ready already set).

    Returns a list of dicts from report["work_queue"] (fields: ticker,
    batch_id, stage, agent, status, gate_state)."""
    R = cowork_root()
    rp = R / "briefings" / "state" / "tick-report.json"
    if not rp.exists():
        raise FileNotFoundError("tick-report.json not found. Run orchestrator_tick.py first.")
    report = json.loads(rp.read_text(encoding="utf-8"))
    selected = []
    for item in report.get("work_queue", []):
        if len(selected) >= max_concurrent:
            break
        agent = item.get("agent")
        ticker = item.get("ticker")
        batch_id = item.get("batch_id")
        if agent == "strawman":
            # do-once guard: skip if strawman_ready already set in live state
            state_path = ms.state_file_path(batch_id)
            if state_path.exists():
                try:
                    st = ms.read_state(state_path)
                    blk = st["stocks"].get(ticker, {})
                    if blk.get("strawman_ready"):
                        continue   # already done
                except Exception:
                    pass
        selected.append(item)
    return selected


# ---------------------------------------------------------------------------
# Strawman context preparation
# ---------------------------------------------------------------------------

def _read_floor(path: Path, max_chars: int = 20000) -> str:
    """Read a floor report, capping at max_chars to keep prompt manageable."""
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
        return text[:max_chars] + ("\n[TRUNCATED]" if len(text) > max_chars else "")
    except Exception:
        return ""


def prepare_strawman_context(batch_id: str, ticker: str) -> dict:
    """Read context files for a stock and return a dict with everything the
    LLM needs to generate proposed sponsor answers + key questions.

    Returns:
        {
          "ticker": str,
          "company": str,       # from universe.json if available
          "stage": str,
          "batch_id": str,
          "cf_text": str,       # Change-Forces highlighted floor (capped 20k chars)
          "bf_text": str,       # Business-Foundations highlighted floor (capped 20k chars)
          "peer_card": dict,    # peer-card.json if exists, else {}
          "sidecar": dict,      # existing sidecar-prefill.json if exists, else {}
          "cohort_name": str,   # from cohorts-v3.json
          "sponsor_answers_file": str,  # relative path for capture_sponsor_answers
          "kq_file": str,               # relative path for capture_key_questions
        }
    """
    R = cowork_root()
    # Stage from state file
    state_path = ms.state_file_path(batch_id)
    stage = "triaging"
    if state_path.exists():
        try:
            st = ms.read_state(state_path)
            stage = st.get("stage", "triaging")
        except Exception:
            pass
    # CF / BF floors
    cf_file = R / "Files" / ticker / "41-change-forces" / "highlighted.md"
    bf_file = R / "Files" / ticker / "42-business-foundations" / "highlighted.md"
    cf_text = _read_floor(cf_file)
    bf_text = _read_floor(bf_file)
    # Peer card
    peer_card_path = R / "Files" / ticker / "peer-card.json"
    peer_card = {}
    if peer_card_path.exists():
        try:
            peer_card = json.loads(peer_card_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Sidecar
    sidecar_path = R / "Files" / ticker / "A-J-memo" / "context" / "sidecar-prefill.json"
    sidecar = {}
    if sidecar_path.exists():
        try:
            sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Company name from universe.json
    company = ticker
    try:
        uni_path = R / "master-dashboard" / "data" / "universe.json"
        if uni_path.exists():
            uni = json.loads(uni_path.read_text(encoding="utf-8"))
            # universe.json may be a list of dicts or a dict
            if isinstance(uni, list):
                for row in uni:
                    if row.get("ticker") == ticker:
                        company = row.get("company", row.get("name", ticker))
                        break
            elif isinstance(uni, dict):
                row = uni.get(ticker, {})
                company = row.get("company", row.get("name", ticker))
    except Exception:
        pass
    # Cohort name from cohorts-v3.json
    cohort_name = ""
    try:
        coh_path = R / "databases" / "data" / "cohorts-v3.json"
        if coh_path.exists():
            coh_data = json.loads(coh_path.read_text(encoding="utf-8"))
            entries = coh_data.get("tickers", {}).get(ticker, [])
            if entries:
                cohort_name = entries[0].get("cohort", "")
    except Exception:
        pass
    # Output file paths (relative to COWORK root)
    memo_dir = f"Files/{ticker}/A-J-memo"
    sponsor_answers_file = f"{memo_dir}/context/sponsor-e1.json"
    kq_file = f"{memo_dir}/context/key-questions.json"
    return {
        "ticker": ticker,
        "company": company,
        "stage": stage,
        "batch_id": batch_id,
        "cf_text": cf_text,
        "bf_text": bf_text,
        "peer_card": peer_card,
        "sidecar": sidecar,
        "cohort_name": cohort_name,
        "sponsor_answers_file": sponsor_answers_file,
        "kq_file": kq_file,
    }


# ---------------------------------------------------------------------------
# Strawman completion: write proposed content and advance state
# ---------------------------------------------------------------------------

def write_strawman_complete(batch_id: str, ticker: str, answers: dict,
                             questions: list) -> str:
    """Write proposed sponsor answers + key questions to the pipeline and
    advance state to waiting_e4 with strawman_ready=True.

    `answers`   -- dict matching sponsor-e1.json format (see example).
    `questions` -- list of {id, question, type, rationale, status} dicts;
                   status should be "proposed" (Richard will approve/amend at E4).

    Returns a plain-English log line."""
    R = cowork_root()
    state_path = ms.state_file_path(batch_id)
    # E1: write proposed sponsor answers (advances gate_state to e1_answered)
    answers_file = f"Files/{ticker}/A-J-memo/context/sponsor-e1.json"
    answers["generated_by"] = "strawman_agent"
    answers["proposed"] = True
    answers["proposed_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    ms.capture_sponsor_answers(state_path, ticker, answers, answers_file)
    # E2/E3: assemble context (advance() sees e1_answered → calls ctx.assemble)
    adv = orchestrate_memo.advance(batch_id)
    # E3: write proposed key questions (advances gate_state to waiting_e4)
    for q in questions:
        q.setdefault("status", "proposed")
    kq_file = f"Files/{ticker}/A-J-memo/context/key-questions.json"
    ms.capture_key_questions(state_path, ticker, questions, kq_file)
    # Mark strawman complete: strawman_ready=True, waiting_for_richard=True
    ms.set_gate_state(state_path, ticker, "waiting_e4",
                      strawman_ready=True, waiting_for_richard=True)
    return (f"{ticker}: strawman complete → proposed sponsor answers + "
            f"{len(questions)} proposed key questions written; "
            f"gate=waiting_e4, strawman_ready=True, awaiting Richard review")


# ---------------------------------------------------------------------------
# Logging helper
# ---------------------------------------------------------------------------

def append_dispatch_log(R: Path, lines: list) -> None:
    """Append plain-text lines to briefings/dispatch-log.md (APPEND not overwrite)."""
    logp = R / "briefings" / "dispatch-log.md"
    logp.parent.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")
    entry = f"\n\n## Dispatch run {ts}\n\n" + "\n".join(str(l) for l in lines) + "\n"
    with open(logp, "a", encoding="utf-8") as f:
        f.write(entry)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _fmt_work(items: list) -> str:
    if not items:
        return "  (none)\n"
    return "\n".join(f"  {i['ticker']:10} {i.get('agent','?'):8} {i['batch_id']}" for i in items) + "\n"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Block B dispatch helper")
    ap.add_argument("--select-work", action="store_true", help="Print work queue (JSON lines)")
    ap.add_argument("--prepare-context", nargs=2, metavar=("BATCH_ID","TICKER"),
                    help="Print strawman context JSON for a ticker")
    ap.add_argument("--guard", metavar="BATCH_ID", help="Test batch_id guard (exits 0=ok, 1=fail)")
    ap.add_argument("--max", type=int, default=DISPATCH_CAP, help="Concurrency cap for --select-work")
    args = ap.parse_args()

    if args.guard:
        try:
            guard_batch_id(args.guard)
            print(f"OK: '{args.guard}' passes batch_id guard")
        except ValueError as e:
            print(f"REJECTED: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.select_work:
        items = select_work(args.max)
        print(f"Selected {len(items)} work item(s) (cap={args.max}):")
        print(_fmt_work(items))
        print(json.dumps(items, indent=2))
    elif args.prepare_context:
        batch_id, ticker = args.prepare_context
        ctx = prepare_strawman_context(batch_id, ticker)
        # Print a human-readable summary + the JSON
        print(f"CONTEXT FOR STRAWMAN: {ticker} ({ctx['company']}) stage={ctx['stage']}")
        print(f"  Cohort: {ctx['cohort_name']}")
        print(f"  CF floor: {len(ctx['cf_text'])} chars")
        print(f"  BF floor: {len(ctx['bf_text'])} chars")
        print(f"  Peer card: {'YES' if ctx['peer_card'] else 'none'}")
        print(f"  Sponsor answers file: {ctx['sponsor_answers_file']}")
        print(f"  KQ file: {ctx['kq_file']}")
        print()
        print(json.dumps(ctx, indent=2, ensure_ascii=False)[:4000])
    else:
        ap.print_help()
