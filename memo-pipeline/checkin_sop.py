#!/usr/bin/env python3
"""
checkin_sop.py -- "IA A&J RB input check in SOP"

On-demand check-in view for Richard. Reads tick-report.json and emits:
  Section 1 (J): ACTION QUEUE — every memo awaiting Richard, grouped by action type
  Section 2 (A): LIVE STATUS TABLE — all active memos, phase + next step
  Section 3 (I): COUNTS SUMMARY — pipeline totals

Usage:
  python3 scripts/memo-pipeline/checkin_sop.py
  python3 scripts/memo-pipeline/checkin_sop.py --refresh   # re-run tick first
  python3 scripts/memo-pipeline/checkin_sop.py --md        # markdown output (default)
  python3 scripts/memo-pipeline/checkin_sop.py --plain     # plain text (no markdown symbols)

Output goes to stdout and (optionally) --out FILE.

The J-A-I ordering ensures Richard sees what he must do before anything else.
"""

import os, sys, json, subprocess, argparse, textwrap
from pathlib import Path
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def cowork_root() -> Path:
    if os.environ.get("COWORK_ROOT"):
        return Path(os.environ["COWORK_ROOT"]).resolve()
    candidates = sorted(Path("/sessions").glob("*/mnt/COWORK")) if Path("/sessions").exists() else []
    if candidates:
        return candidates[0].resolve()
    return Path(".").resolve()


# ---------------------------------------------------------------------------
# Action labels (what Richard must do for each gate)
# ---------------------------------------------------------------------------
ACTION_LABELS = {
    "e4_review":        "Review strawman — amend sponsor answers + approve/revise KQs",
    "e1_answer":        "Answer sponsor questions (E1 gate — kick off context assembly)",
    "e4_cold":          "Write key questions from scratch (no strawman — E4 gate)",
    "waiting_richard":  "Manual hold — check memo log for required action",
}

PHASE_LABELS = {
    "action_queue":  "⏳ Awaiting Richard",
    "work_queue":    "🤖 Agent queued",
    "researching":   "🔍 Researching (E6)",
    "in_motion":     "⚙️  In motion",
    "terminal":      "✅ Terminal",
    "error":         "❌ Error",
}

GATE_PHASE = {
    "waiting_e1":  "Sponsor Q&A (E1)",
    "e1_answered": "Context assembly (E2/E3)",
    "waiting_e4":  "KQ review (E4)",
    "e4_approved": "Writer dispatch (E5)",
    "waiting_e6":  "Research wait (E6)",
    "e6_satisfied":"Writer ready",
}

STATUS_LABEL = {
    "pending":           "Pending",
    "context_assembled": "Context ready",
    "in_production":     "In production",
    "rendered":          "Rendered (QC)",
    "judged":            "Judged",
    "published":         "Published",
    "completed":         "Completed",
    "closed":            "Closed",
    "parked":            "Parked",
    "blocked":           "Blocked",
}

# ---------------------------------------------------------------------------
# Read report
# ---------------------------------------------------------------------------

def read_report(R: Path) -> dict:
    rp = R / "briefings" / "state" / "tick-report.json"
    if not rp.exists():
        raise FileNotFoundError(
            "tick-report.json not found. Run orchestrator_tick.py first, "
            "or use --refresh flag."
        )
    report = json.loads(rp.read_text(encoding="utf-8"))
    return report


def run_tick(R: Path) -> dict:
    """Run orchestrator_tick.py and return fresh report."""
    tick_py = HERE / "orchestrator_tick.py"
    subprocess.run(
        [sys.executable, str(tick_py)],
        cwd=str(R),
        check=True,
        capture_output=True,
    )
    return read_report(R)


# ---------------------------------------------------------------------------
# Classify Richard's required action for an action_queue item
# ---------------------------------------------------------------------------

def richard_action(item: dict) -> str:
    """Return action key from ACTION_LABELS."""
    if item.get("strawman_ready"):
        return "e4_review"
    gate = item.get("gate_state", "")
    if gate == "waiting_e1":
        return "e1_answer"
    if gate == "waiting_e4":
        return "e4_cold"
    if item.get("waiting_for_richard"):
        return "waiting_richard"
    return "waiting_richard"


# ---------------------------------------------------------------------------
# Format helpers
# ---------------------------------------------------------------------------

def _hr(char="─", width=72):
    return char * width


def _phase_label(item: dict) -> str:
    gs = item.get("gate_state")
    st = item.get("status", "?")
    if gs and gs in GATE_PHASE:
        return GATE_PHASE[gs]
    return STATUS_LABEL.get(st, st)


def _ticker_display(item: dict) -> str:
    t = item.get("ticker", "?")
    stage = item.get("stage", "")
    return f"{t} ({stage.upper()})" if stage else t


def _age_str(item: dict) -> str:
    """Return rough age of memo from created_at if present."""
    try:
        created = item.get("created_at", "")
        if not created:
            return ""
        dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - dt
        days = diff.days
        if days == 0:
            return "today"
        elif days == 1:
            return "1d"
        else:
            return f"{days}d"
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# Format output
# ---------------------------------------------------------------------------

def format_checkin(report: dict, mode: str = "md") -> str:
    """Return formatted check-in string (J-A-I order)."""

    def h1(t):
        return f"# {t}\n" if mode == "md" else f"\n{'='*72}\n{t}\n{'='*72}"

    def h2(t):
        return f"\n## {t}\n" if mode == "md" else f"\n{'-'*60}\n{t}\n{'-'*60}"

    def bold(t):
        return f"**{t}**" if mode == "md" else t

    lines = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    tick_at = report.get("generated_at", "unknown")

    lines.append(h1(f"IA A&J Memo Check-In — {now_str}"))
    lines.append(f"_Tick data: {tick_at}_\n")

    # ------------------------------------------------------------------
    # Section J: ACTION QUEUE (what Richard must do)
    # ------------------------------------------------------------------
    action_items = report.get("action_queue", [])

    lines.append(h2("J — ACTION QUEUE  (items awaiting Richard)"))

    if not action_items:
        lines.append("_No memos awaiting Richard. ✓_\n")
    else:
        # Group by action type
        groups: dict[str, list] = {}
        for item in action_items:
            key = richard_action(item)
            groups.setdefault(key, []).append(item)

        for key in ["e4_review", "e1_answer", "e4_cold", "waiting_richard"]:
            if key not in groups:
                continue
            label = ACTION_LABELS[key]
            items = groups[key]
            lines.append(f"\n### {bold(label)} ({len(items)})\n")
            for item in items:
                t = _ticker_display(item)
                age = _age_str(item)
                age_str = f"  _{age}_" if age else ""
                batch = item.get("batch_id", "?")
                lines.append(f"- {bold(t)}{age_str}  ·  batch: `{batch}`")

                # Add specific guidance per action type
                if key == "e4_review":
                    lines.append(
                        f"  → Open `Files/{item.get('ticker')}/A-J-memo/context/` "
                        f"— review `sponsor-e1.json` and `key-questions.json`; "
                        f"then run `ms.set_gate_state(path, ticker, 'e4_approved')`"
                    )
                elif key == "e1_answer":
                    lines.append(
                        f"  → Provide sponsor answers for `{item.get('ticker')}` "
                        f"(thesis, pillar, kill_shot, catalyst, excite, worry)"
                    )
                elif key == "e4_cold":
                    lines.append(
                        f"  → Write key questions for `{item.get('ticker')}` "
                        f"and call `ms.capture_key_questions(...)` then set e4_approved"
                    )
    # ------------------------------------------------------------------
    # Section A: LIVE STATUS TABLE
    # ------------------------------------------------------------------
    lines.append(h2("A — LIVE STATUS"))

    # Collect all items across queues for table
    all_items = []
    for queue_key in ["action_queue", "work_queue", "researching", "in_motion"]:
        for item in report.get(queue_key, []):
            item["_queue"] = queue_key
            all_items.append(item)

    terminal = report.get("terminal", [])
    recent_terminal = terminal[-5:] if len(terminal) > 5 else terminal  # show last 5

    if not all_items and not recent_terminal:
        lines.append("_No live memos._\n")
    else:
        if mode == "md":
            lines.append(
                "| Ticker | Stage | Phase | Queue | Age |"
            )
            lines.append("|--------|-------|-------|-------|-----|")
            for item in all_items:
                t = item.get("ticker", "?")
                stage = item.get("stage", "?").upper()
                phase = _phase_label(item)
                queue = PHASE_LABELS.get(item["_queue"], item["_queue"])
                age = _age_str(item) or "—"
                lines.append(f"| {t} | {stage} | {phase} | {queue} | {age} |")
            if recent_terminal:
                lines.append("")
                lines.append("**Recent terminal:**")
                for item in recent_terminal:
                    t = item.get("ticker", "?")
                    st = STATUS_LABEL.get(item.get("status", ""), item.get("status", "?"))
                    lines.append(f"| {t} | — | {st} | ✅ Terminal | — |")
        else:
            # Plain text table
            col_w = [12, 10, 25, 20, 6]
            hdr = [
                "Ticker".ljust(col_w[0]),
                "Stage".ljust(col_w[1]),
                "Phase".ljust(col_w[2]),
                "Queue".ljust(col_w[3]),
                "Age".ljust(col_w[4]),
            ]
            lines.append("  ".join(hdr))
            lines.append(_hr())
            for item in all_items:
                row = [
                    item.get("ticker", "?")[:col_w[0]].ljust(col_w[0]),
                    item.get("stage", "?").upper()[:col_w[1]].ljust(col_w[1]),
                    _phase_label(item)[:col_w[2]].ljust(col_w[2]),
                    PHASE_LABELS.get(item["_queue"], "")[:col_w[3]].ljust(col_w[3]),
                    (_age_str(item) or "—")[:col_w[4]].ljust(col_w[4]),
                ]
                lines.append("  ".join(row))

    # ------------------------------------------------------------------
    # Section I: COUNTS SUMMARY
    # ------------------------------------------------------------------
    lines.append(h2("I — COUNTS"))
    aq = len(report.get("action_queue", []))
    wq = len(report.get("work_queue", []))
    rs = len(report.get("researching", []))
    mo = len(report.get("in_motion", []))
    tm = len(report.get("terminal", []))
    err = len(report.get("error", []))

    lines.append(f"- Awaiting Richard: {bold(str(aq))}")
    lines.append(f"- Agent queued:     {wq}")
    lines.append(f"- Researching (E6): {rs}")
    lines.append(f"- In motion:        {mo}")
    lines.append(f"- Terminal:         {tm}")
    if err:
        lines.append(f"- {bold('Errors:')}          {err}  ← investigate")
    lines.append("")
    lines.append(
        f"_Total live: {aq + wq + rs + mo} | "
        f"Total ever: {aq + wq + rs + mo + tm}_\n"
    )

    # Footer
    lines.append(_hr("─"))
    lines.append(
        "_Trigger phrase: \"IA A&J RB input check in SOP\" · "
        "Source: briefings/state/tick-report.json_\n"
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(
        description="IA A&J Memo check-in SOP — J-A-I status report for Richard"
    )
    ap.add_argument("--refresh", action="store_true",
                    help="Re-run orchestrator_tick.py before generating report")
    ap.add_argument("--plain", action="store_true",
                    help="Plain text output (no markdown symbols)")
    ap.add_argument("--out", metavar="FILE",
                    help="Also write output to FILE (appends timestamp header)")
    args = ap.parse_args()

    R = cowork_root()
    mode = "plain" if args.plain else "md"

    try:
        if args.refresh:
            report = run_tick(R)
        else:
            report = read_report(R)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print(f"ERROR running tick: {e}", file=sys.stderr)
        sys.exit(1)

    output = format_checkin(report, mode=mode)
    print(output)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        with open(out_path, "a", encoding="utf-8") as f:
            f.write(f"\n\n<!-- check-in {ts} -->\n\n")
            f.write(output)
        print(f"\n[Written to: {out_path}]", file=sys.stderr)


if __name__ == "__main__":
    main()
