#!/usr/bin/env python3
"""
orchestrate_memo.py — the A&J Memo Batching pipeline spine (Stations 1-5 wiring).

Design: design/00-SHARED-BUILD-CONVENTIONS.md (rungs, state, disciplines), design/07-COLD-RESTART
(resume table), docs 01/02/03/04/08/09. Decisions D-AJ-9/10/12/17/18.

The spine is deterministic and idempotent: it reads the state file (the only oracle), and for each
stock does ONLY what is not yet done, per the design-07 resume table. Re-running a finished station
is a no-op (gate = read the completion marker).

Station handlers:
  Station 1 (context)   : Python — calls assemble_memo_context.assemble().
  Station 2 (writer)    : LLM — materializes the exact per-memo task prompt (doc 03 §9) + a
                          spawn-config JSON that HARD-WIRES D-AJ-17 (Sonnet, HIGH effort, extended
                          thinking ON). A Cowork agent then writes the memo + runs the QC fix-loop.
                          --writer-mode mock writes a deterministic stub for plumbing tests only.
  Station 3 (render-QC) : Python — runs generate_qc_audit.py --render-qc on; HARD gate (D-AJ-18).
                          The state field `render_qc` (PASS|FAIL|UNAVAILABLE) is the Station-3
                          completion marker, replacing the retired browser_qc_confirmed (doc-07
                          reconciliation, 2026-06-16).
  Station 4 (judge)     : LLM — materializes the judge task prompt (doc 04 §6). Agent writes the
                          verdict to the sidecar.
  Station 5 (publish)   : Python + git + Notion (doc 09). Deterministic.

Renderer warm-up: --warm runs watson-qc-render.sh once at batch start so the first memo does not eat
a cold-Chromium retry (handoff item B).

Author: Watson (Systems Architect, Opus build), 2026-06-16.
"""

import os
import sys
import json
import time
import shutil
import tempfile
import subprocess
import argparse
from pathlib import Path
from datetime import date

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import memo_state as ms
import assemble_memo_context as ctx

IA_SCRIPTS = "memory/skills/investment-analyst/scripts"
QC = f"{IA_SCRIPTS}/generate_qc_audit.py"
RENDERER = "scripts/watson-qc-render.sh"

# D-AJ-17 — the Writer model config, ENFORCED IN CODE (not just documented).
WRITER_SPAWN_CONFIG = {
    "model": "sonnet",
    "effort": "high",
    "extended_thinking": True,
    "max_effort_only_for": ["writer-flagged high-uncertainty", "deep-dive stage"],
    "decision": "D-AJ-17",
    "note": "Quality over cost; the Writer is the analytical core. Never silently drop to standard.",
}
JUDGE_SPAWN_CONFIG = {"model": "sonnet", "effort": "medium", "extended_thinking": False,
                      "decision": "D-AJ-12", "note": "Four checks; non-deep."}


def root() -> Path:
    return Path(os.environ.get("COWORK_ROOT", ".")).resolve()


def _run(cmd: list, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)


# ------------------------------------------------------------------
# Renderer warm-up (handoff item B)
# ------------------------------------------------------------------

def warm_renderer(R: Path) -> str:
    sh = R / RENDERER
    if not sh.exists():
        return "renderer script absent — skip warm-up"
    # A tiny self-contained page proves Chromium is warm without touching a real memo.
    tmp = Path(tempfile.mkdtemp()) / "warm.html"
    tmp.write_text("<html><head><title>warm</title></head><body>warm</body></html>")
    out = "/dev/shm/warm-qc.png"
    cp = _run(["bash", str(sh), "--file", str(tmp), "--out", out], R)
    return "renderer warm (PASS)" if cp.returncode == 0 else f"renderer warm returned {cp.returncode} (cold; retry/backoff covers it)"


# ------------------------------------------------------------------
# Station 2 — writer task prompt materialization (doc 03 §9)
# ------------------------------------------------------------------

WRITER_PROMPT_TMPL = """ROLE: Investment Analyst. Write the {STAGE} A&J memo for {TICKER} ({COMPANY}) to a very high standard.
MODEL CONFIG (D-AJ-17, non-negotiable): Sonnet, HIGH effort, extended thinking ON. Do NOT drop to standard.

CONTEXT: already assembled at Files/{TICKER}/A-J-memo/context/ — read coverage.md and
  sidecar-prefill.json FIRST. Do NOT re-run context assembly.
COHORT PACK (grade anchor): {COHORT_PACK}
SOURCE (floor): {CF_PATH}   (read in full; trace every claim)
DIALS: trust={TRUST}, cohort={COHORT_DIAL}, sector={SECTOR_DIAL}.

LOADS (LIVE, by path — never copy SOP prose):
  memory/skills/investment-analyst/aj-memo/02-THINKING-SOP.md (Procedure 1 for Triaging)
  memory/skills/investment-analyst/aj-memo/06-RESEARCH-SOURCE-MAP.md
  memory/skills/investment-analyst/aj-memo/05-IA-EXECUTION-DISCIPLINE.md (§3-§6 + Phase 4)
  memory/skills/investment-analyst/aj-memo/03-COMMUNICATING-SOP.md + 04-PRESENTING-SOP.md
  memory/skills/investment-analyst/aj-memo/skeletons/TRIAGING-skeleton.md (COPY and fill)
  "PROJECTS/SA - Investment Analyst A&J memos/briefing/04-elements-with-RAs-and-CQs-integrated.md"

FIRST artefact: author ratings.json in Files/{TICKER}/A-J-memo/ (geo-key-nested schema, keyed {TICKER}).
WALK (Triaging, in-scope E1/E5/E7/E8/E11 only; all else "not applicable at this stage"):
  copy the skeleton; write every in-scope Element to its floor (memo-floors-v1.json);
  grade against the LIVE COHORT (not the universe); the cohort anchor is COLD-START (CF-derived,
  no peer memos) — defend each grade from peer CF specifics and say so in Section F;
  use the live price ({PRICE}, {PRICE_DATE}) in the E1 entry-point read and MR1;
  E8 has the HIGHEST word floor (~3,500w) despite its light 3-bullet count — do NOT under-write it;
  thematics are STALE (canonical pause) — grade E5/MR3 with the stale-frame caveat (decision: proceed);
  run the specifics-retention sweep; identify the 1-2 E8 fit setups; author the Go-No-Go one-pager;
  fill the sidecar as you go (conviction_tiers + e8_fit_setups included).
FORMAT (D-AJ-21, MANDATORY — the QC gate HARD-fails violations):
  write NO prose paragraphs anywhere; every body block is a bullet or nested sub-bullet;
  write the executive summary, the B.3 Master-Ratings rationales, and EVERY section/element
  summary as bullets; put each section/element summary INSIDE its '> ' colour block as
  '> - **Verdict [grade].** the point' bullets (keep the colour block, NOT a prose sentence);
  keep each '#### MRn — ... [grade]' heading and bullet its rationale beneath it;
  hold every body bullet to 40 words (HARD ceiling) — split a long one into parent + sub-bullets;
  grade every judgement-bearing Core Question [A]-[F] in its label; tag a factual one [factual];
  pair every code with a plain-English description EVERY time (e.g. "the Benelux/Swiss integrated
  telecoms cohort (TCM04)"); spell out Element names; never use "L4"-style source shorthand.
FORMAT v2 (D-AJ-24, MANDATORY — these are HARD gates):
  SIGNPOST every bullet and EVERY sub-bullet with a bold label ("**Leverage:** ..."); capitalise the
  first word of every bullet; EMPHASIS minimums per memo: underline ~20% of bullet words (__text__),
  sentiment-highlight >30% of bullets (==+pos==/==-neg==/==~mixed==), italicise the nuance in >=20%
  of bullets (*text*); ONE consolidated judgement-summary box per Element holding the Element verdict
  + each Required-Attribute verdict as bullets; each Required Attribute leads its body with a one-line
  ANSWER bullet ("**RA1 (label) answer [C]:** ..."), and each Core Question's MAIN bullet carries a
  one-line ANSWER before its evidence ("**E5 RA1 CQ1 — question? [C]:** answer"), then signposted
  numbered sub-bullets (the viewer numbers 1 / 2.1 / 2.1.1); SPELL OUT the element name every time a
  code carries meaning ("Element E8 (Fit with acceptable case setups) verdict", never "E8 verdict");
  put the grade right after the signpost punctuation ("**...verdict [C].**", "**...market? [C]:**").
QC: run {QC} --memo Files/{TICKER}/A-J-memo/memo.md --stage {STAGE_LC} --meta {SIDECAR} --render-qc off
  in the fix-loop (cap 3); on clean, re-run with --render-qc ON (Station 3 hard gate).
ZERO bespoke research at Triaging — flag would-be gaps in the debrief §4/§5, do not run queries.
WRITE FUSE-safe (sandbox -> cp -> verify by ticker key -> vanish-guard). Set state when done.
Memo target ~9,000 words (excl. A and F). Back-brief in the self-review debrief.
"""


def _company_name(ticker: str, R: Path) -> str:
    """Resolve the human company name from universe.json; fall back to ticker."""
    try:
        uni = json.load(open(R / "master-dashboard" / "data" / "universe.json", encoding="utf-8"))
        stocks = uni.get("stocks", uni) if isinstance(uni, dict) else uni
        return next((s["company_name"] for s in stocks if s.get("ticker") == ticker), ticker)
    except Exception:
        return ticker


def materialize_writer_prompt(ticker: str, stage: str, R: Path, blk: dict) -> Path:
    sc_path = R / blk["sidecar_file"]
    sc = json.load(open(sc_path)) if sc_path.exists() else {}
    cf = sc.get("research_reports", [{}])[0].get("path", f"Files/{ticker}/41-change-forces/highlighted.md")
    pack = sc.get("cohort_injection", {}).get("pack_path", "")
    price = sc.get("data_files", {}).get("prices", {})
    dials = sc.get("dial_settings", {})
    company = _company_name(ticker, R)  # D3: use real company name, not ticker
    sidecar_rel = blk["sidecar_file"]   # D4: explicit sidecar path for writer QC command
    prompt = WRITER_PROMPT_TMPL.format(
        STAGE=stage.capitalize(), STAGE_LC=stage.lower(),
        TICKER=ticker, COMPANY=company,
        COHORT_PACK=pack, CF_PATH=cf, QC=QC,
        SIDECAR=sidecar_rel,
        TRUST=dials.get("trust", "balanced"), COHORT_DIAL=dials.get("cohort", "normal"),
        SECTOR_DIAL=dials.get("sector", "normal"),
        PRICE=price.get("price", "n/a"), PRICE_DATE=price.get("date", "n/a"))
    out_dir = R / "Files" / ticker / "A-J-memo" / "context"
    out_dir.mkdir(parents=True, exist_ok=True)
    ppath = out_dir / "writer-task-prompt.md"
    ppath.write_text(prompt, encoding="utf-8")
    (out_dir / "writer-spawn-config.json").write_text(
        json.dumps(WRITER_SPAWN_CONFIG, indent=2), encoding="utf-8")
    return ppath


def mock_writer(ticker: str, R: Path) -> None:
    """TEST ONLY: write a minimal stub memo + ratings + go-no-go so the card-flow can be verified
    without spending LLM tokens. NOT a real memo. Marked clearly."""
    md = R / "Files" / ticker / "A-J-memo"
    md.mkdir(parents=True, exist_ok=True)
    (md / "memo.md").write_text(f"# [MOCK] {ticker} Triaging A&J Memo\n\nPLUMBING STUB — not a real memo.\n")
    (md / "ratings.json").write_text(json.dumps({ticker: {"ticker": ticker, "stage": "Triaging",
        "master_ratings": {f"MR{i}": "C" for i in range(1, 7)},
        "element_ratings": {e: "C" for e in ("E1", "E5", "E7", "E8", "E11")}}}))
    (md / "go-no-go.md").write_text("# [MOCK] Go-No-Go\n")


# ------------------------------------------------------------------
# Station 3 — render-QC gate (Python)
# ------------------------------------------------------------------

def run_render_qc(ticker: str, R: Path, stage: str = "triaging", sidecar_path: Path = None) -> tuple:
    """Station 3 render-QC HARD gate. Stage-parameterised (K1, doc 10 para I)."""
    memo = R / "Files" / ticker / "A-J-memo" / "memo.md"
    sc = sidecar_path if sidecar_path else (R / "Files" / ticker / "A-J-memo" / "context" / "sidecar-prefill.json")  # D7: use state pointer
    if not memo.exists():
        return "FAIL", "memo file absent"
    cp = _run(["python3", QC, "--memo", str(memo), "--stage", stage,
               "--meta", str(sc), "--render-qc", "on"], R)
    # generate_qc_audit exit: 0=PASS; 1=HARD FAIL (incl. cold renderer row); 2=bad args.
    # Exit code 3 is NEVER emitted by the script. A cold renderer becomes a HARD row (exit 1)
    # with "ENVIRONMENT" in the output. Detect it from output text, not exit code. (D9)
    rc = cp.returncode
    out_text = (cp.stdout or "") + (cp.stderr or "")
    if rc == 0:
        verdict = "PASS"
    elif rc == 1 and ("ENVIRONMENT" in out_text or "re-run when" in out_text.lower()):
        verdict = "UNAVAILABLE"
    else:
        verdict = "FAIL"
    return verdict, (cp.stdout or cp.stderr)[-400:]


# ------------------------------------------------------------------
# Station 4 — judge prompt materialization (doc 04 §6)
# ------------------------------------------------------------------

JUDGE_PROMPT_TMPL = """ROLE: Judge. You did NOT write this memo. Challenge it. Do NOT rewrite it.
MODEL CONFIG (D-AJ-12): Sonnet, medium effort, non-deep.
STAGE: {STAGE}
LOAD: Files/{TICKER}/A-J-memo/memo.md + go-no-go.md; source CF report; sidecar at {SIDECAR}
  (read conviction_tiers FIRST); cohort pack; 06-RESEARCH-SOURCE-MAP; price/valuation/ssem.
RUN four checks (rubric scales by stage -- doc 10 para H):
  (1) Grounding: price-used in E1 RA2 + MR1; at ESA/DD also Invalidation-threshold figures + driver-table numbers.
  (2) Specifics-retention: every cited figure/fact present in source; none invented.
  (3) Grade calibration: cohort-anchored + roll-up within 1 notch; at ESA/DD apply mediocrity-shunning lens
      to management quality, business quality, predictability, trackability.
  (4) Summary-to-body consistency: every summary box matches its section.
DD MEDIOCRITY GATE (Deep-Dive only): C/D/F on management quality, business quality, predictability,
  or trackability -> verify memo recommends PARK. If writer graded generously without park recommendation,
  flag REVISE with location. This is a recommendation gate; Richard makes final call.
TARGET effort by the writer's conviction tiers -- hardest where the writer flagged thin.
RETURN judge_result {{PASS|REVISE|ESCALATE}} + judge_defects[] with location + fix-pointer; write to sidecar at {SIDECAR}.
ESCALATE on any identity/family mismatch or fabrication.
"""


def materialize_judge_prompt(ticker: str, R: Path, stage: str = "triaging",
                             sidecar_rel: str = "") -> Path:
    """Materialise the Judge prompt; rubric scales by stage (doc 10 para H)."""
    out = R / "Files" / ticker / "A-J-memo" / "context" / "judge-task-prompt.md"
    if not sidecar_rel:
        sidecar_rel = f"Files/{ticker}/A-J-memo/context/sidecar-prefill.json"
    out.write_text(JUDGE_PROMPT_TMPL.format(TICKER=ticker, STAGE=stage.upper(),
                                            SIDECAR=sidecar_rel), encoding="utf-8")
    (out.parent / "judge-spawn-config.json").write_text(json.dumps(JUDGE_SPAWN_CONFIG, indent=2))
    return out


# ------------------------------------------------------------------
# The advance loop (design-07 resume table; idempotent)
# ------------------------------------------------------------------

def advance(batch_id: str, writer_mode: str = "prompt", do_warm: bool = False) -> dict:
    R = root()
    path = ms.state_file_path(batch_id)
    st = ms.read_state(path)
    stage = st.get("stage", "triaging")
    log = []
    needs_agent: dict = {}  # populated when Station 4 materialises judge prompt but cannot dispatch
    if do_warm:
        log.append("WARM: " + warm_renderer(R))
    for ticker, blk in list(st["stocks"].items()):
        s = blk["status"]
        gs = blk.get("gate_state")
        # --- Terminal ---
        if s in ("closed", "parked", "qc_hard_fail"):
            log.append(f"{ticker}: {s} (terminal/no-op)")
            continue
        # --- ESA/DD human gate: surface, do not proceed (K3/K5, doc 10 para B) ---
        if s == "pending" and gs in ("waiting_e1", "waiting_e4"):
            log.append(_gate_state_surface(ticker, blk))
            continue
        # --- blocked non-E6: delegate to gate_monitor.py ---
        if s == "blocked" and gs not in ("waiting_e6",):
            log.append(f"{ticker}: blocked (run gate_monitor.py --batch {batch_id} to poll)")
            continue
        # --- Context assembly: pending with gate open or e6_satisfied (or Triaging pending) ---
        if s in ("blocked", "pending") and gs in (None, "e1_answered", "e6_satisfied"):
            _dials = st.get("dials", {})  # D6: read dials from batch state, not hardcoded
            res = ctx.assemble(ticker, stage, batch_id,
                               _dials.get("cohort", "normal"), _dials.get("sector", "normal"),
                               st.get("thematics_decision", "proceed"))
            log.append(f"{ticker}: context -> {res['status']}")
            continue
        # --- Writer dispatch by stage (K1+K7) ---
        if s == "context_assembled":
            # E3→E6 gate: ESA/DD writer must not fire until KQ research loop complete (non-mock only).
            # Triaging and mock mode bypass this gate (Triaging has no KQ loop; mock tests writer dispatch directly).
            if stage in ("esa", "dd") and writer_mode != "mock" and gs != "e6_satisfied":
                if gs == "waiting_e4":
                    log.append(_gate_state_surface(ticker, blk))
                elif gs == "e4_approved":
                    log.append(f"{ticker}: context_assembled -- E4 approved; E5 brief emission pending; emit KQ research briefs then call record_kq_briefs()")
                else:  # gs is e1_answered, None, or unexpected
                    log.append(f"{ticker}: context_assembled -- E3 pending; Watson to generate key questions and call capture_key_questions()")
                continue
            if writer_mode == "mock":
                mock_writer(ticker, R)
                ms.set_status(path, ticker, "in_production")
                log.append(f"{ticker}: MOCK writer wrote stub -> in_production")
            elif stage == "esa":
                p = materialize_esa_writer_prompt(ticker, R, blk)
                ms.set_status(path, ticker, "in_production")
                log.append(f"{ticker}: ESA delta writer prompt materialised ({p.relative_to(R)}); AWAITING WRITER AGENT")
            elif stage == "dd":
                p = materialize_dd_writer_prompt(ticker, R, blk)
                ms.set_status(path, ticker, "in_production")
                log.append(f"{ticker}: DD delta writer prompt materialised ({p.relative_to(R)}); AWAITING WRITER AGENT")
            else:
                p = materialize_writer_prompt(ticker, stage, R, blk)
                ms.set_status(path, ticker, "in_production")
                log.append(f"{ticker}: writer prompt materialised ({p.relative_to(R)}); AWAITING WRITER AGENT")
            continue
        # --- Station 3: Render-QC HARD gate (K1) ---
        if s == "in_production":
            memo = R / "Files" / ticker / "A-J-memo" / "memo.md"
            if not memo.exists():
                log.append(f"{ticker}: in_production -- memo not yet written by agent; AWAITING")
                continue
            verdict, detail = run_render_qc(ticker, R, stage, sidecar_path=R / blk["sidecar_file"])  # D7
            ms.set_status(path, ticker, "rendered" if verdict == "PASS" else "in_production",
                          render_qc=verdict)
            if verdict == "PASS":
                log.append(f"{ticker}: render-QC PASS -> rendered")
            elif verdict == "UNAVAILABLE":
                log.append(f"{ticker}: render-QC UNAVAILABLE (cold) -- re-run when warm")
            else:
                n = ms.bump_fix_attempts(path, ticker)
                if n >= 3:
                    ms.add_flag(path, ticker, f"QC fix-loop cap reached ({n}) -- escalate to morning briefing")
                    ms.set_status(path, ticker, "qc_hard_fail")
                    log.append(f"{ticker}: render-QC FAIL x{n} -- cap -> qc_hard_fail")
                else:
                    log.append(f"{ticker}: render-QC FAIL (attempt {n}/3) -- {detail[:120]}")
            continue
        # --- Station 4: Judge -- materialise + K9 auto-advance if verdict in sidecar (K8+K9) ---
        # Dispatch model: advance() materialises the judge prompt + spawn config, emits
        # needs_agent["judge"] in its return dict, and sets the log line with exact paths.
        # The calling SA session reads needs_agent and dispatches a Sonnet sub-agent.
        # Re-running advance() after the judge writes its verdict auto-advances to "judged".
        if s == "rendered":
            p = materialize_judge_prompt(ticker, R, stage, sidecar_rel=blk.get("sidecar_file", ""))
            sc_path = R / blk["sidecar_file"]
            _judge_done = False
            if sc_path.exists():
                try:
                    sc = json.load(open(sc_path))
                    jv = sc.get("judge_result")
                    if jv == "PASS":
                        ms.set_status(path, ticker, "judged")
                        log.append(f"{ticker}: judge PASS (read from sidecar) -> judged")
                        _judge_done = True
                    elif jv in ("REVISE", "ESCALATE"):
                        ms.add_flag(path, ticker, f"JUDGE: {jv} -- see sidecar judge_defects")
                        log.append(f"{ticker}: judge {jv} (read from sidecar) -- writer fix needed")
                        _judge_done = True
                except Exception:
                    pass
            if not _judge_done:
                spawn_cfg = p.parent / "judge-spawn-config.json"
                log.append(
                    f"{ticker}: judge prompt materialised at {p.relative_to(R)}; "
                    f"spawn config at {spawn_cfg.relative_to(R)}; "
                    f"DISPATCH JUDGE AGENT (Sonnet medium non-deep {stage.upper()} rubric) "
                    f"then re-run advance('{batch_id}') to auto-advance"
                )
                needs_agent["judge"] = str(p.relative_to(R))
            continue
        # --- Station 5: Publish + close (K9 auto-advance) ---
        if s == "judged":
            pub_msg = auto_publish(ticker, R, stage)
            ms.set_status(path, ticker, "published")
            ms.set_status(path, ticker, "closed")
            log.append(f"{ticker}: -> published -> closed. {pub_msg}")
            # --- Station 6 (non-critical): peer card + reference-summary refresh ---
            peer_msg = emit_peer_artifacts(ticker, R, stage)
            log.append(f"{ticker}: peer artifacts -- {peer_msg}")
            continue
        log.append(f"{ticker}: status={s} gate_state={gs} (no handler)")
    return {"log": log, "needs_agent": needs_agent}


# ------------------------------------------------------------------
# ESA + DD cumulative-delta writer prompt templates (doc 10 para G, K7)
# ------------------------------------------------------------------

ESA_WRITER_PROMPT_TMPL = """ROLE: Investment Analyst. Write the ESA A&J memo for {TICKER} ({COMPANY}) by GROWING the prior Triaging memo to ESA depth.
MODEL CONFIG (D-AJ-17, non-negotiable): Sonnet, HIGH effort, extended thinking ON. Do NOT drop to standard.

CONTEXT: assembled at Files/{TICKER}/A-J-memo/context/ -- read coverage.md and sidecar-prefill.json FIRST.
PRIOR MEMO (Triaging baseline): {PRIOR_MEMO_PATH}
SPONSOR ANSWERS (E1 Q&A -- null answers = no steer, do NOT invent): {SPONSOR_ANSWERS_FILE}
KEY-QUESTION REPORTS (E5 research -- flag Option-B gaps in self-review debrief): {KQ_REPORTS}
COHORT PACK: {COHORT_PACK}
DIALS: trust={TRUST}, cohort={COHORT_DIAL}, sector={SECTOR_DIAL}.

LOADS (LIVE): 02-THINKING-SOP.md (Procedure 2); 06-RESEARCH-SOURCE-MAP.md;
  05-IA-EXECUTION-DISCIPLINE.md; 03/04-COMMUNICATING/PRESENTING-SOP.md;
  skeletons/ESA-skeleton.md (COPY and fill);
  "PROJECTS/SA - Investment Analyst A&J memos/briefing/04-elements-with-RAs-and-CQs-integrated.md"

WHAT ESA ADDS (~21,000-word floor):
  Deepen Change Forces, Thematic Fit, Simplicity, Value Chain (carry + deepen from Triaging).
  First-write: Case Outputs, Valuation Upside, Technical, Operator, Advantaged Business, Industry Structure,
  Secular Growth, Transmission. Section D FIRST APPEARS: position playbook, monitoring plan,
  10 Invalidation Thresholds verbatim, two seven-column driver tables (upstream + downstream).
  Deepen only the 1-2 E8 fit setups from the Triaging sidecar e8_fit_setups.
  Carry sponsor thesis/pillar/concern/catalyst steer. Flag Option-B KQ gaps in self-review debrief para4/para5.
  If prior memo is pre-v2 format, re-apply v2 emphasis to all carried sections as you deepen them (doc 10 L2).

FORMAT (D-AJ-21 + D-AJ-24 + F5, MANDATORY -- QC gate HARD-fails violations):
  No prose; all bullets; 40-word ceiling (HARD); grade every judgement CQ [A]-[F]; signpost every bullet.
  ONE consolidated judgement-summary box per Element; each RA + each graded CQ main bullet carries
  a one-line ANSWER clause (F5, D-AJ-27). Highlight ~35%, italic ~20%, underline ~20% of words.

QC: run {QC} --memo Files/{TICKER}/A-J-memo/memo.md --stage esa --meta {SIDECAR} --render-qc off
  in fix-loop (cap 3); on clean, re-run with --render-qc ON (Station 3 HARD gate).
WRITE FUSE-safe. Set state when done. Memo target ~21,000 words.
"""


DD_WRITER_PROMPT_TMPL = """ROLE: Investment Analyst. Write the Deep-Dive A&J memo for {TICKER} ({COMPANY}) by GROWING the prior ESA memo.
MODEL CONFIG (D-AJ-17): Sonnet, HIGH effort + MAX for high-uncertainty sections, extended thinking ON.

CONTEXT: Files/{TICKER}/A-J-memo/context/ -- read coverage.md and sidecar-prefill.json FIRST.
PRIOR MEMO (ESA baseline): {PRIOR_MEMO_PATH}
SPONSOR ANSWERS: {SPONSOR_ANSWERS_FILE}
KEY-QUESTION REPORTS (DD research): {KQ_REPORTS}
COHORT PACK: {COHORT_PACK}
DIALS: trust={TRUST}, cohort={COHORT_DIAL}, sector={SECTOR_DIAL}.

LOADS (LIVE): 02-THINKING-SOP.md (Procedure 3); 06-RESEARCH-SOURCE-MAP.md;
  05-IA-EXECUTION-DISCIPLINE.md; 03/04-COMMUNICATING/PRESENTING-SOP.md;
  skeletons/Deep-Dive-skeleton.md (COPY and fill).

WHAT DEEP-DIVE ADDS (~28,000-word floor):
  Deepen almost everything to solid/robust. First-write: Risk Elements (Invalidating Attributes,
  Seek-to-Avoid, Capital-Constraining) + Sell-Side Momentum. Section D to FULL driver tables.
  10 Invalidation Thresholds VERBATIM -- QC HARD-fails a missing or paraphrased set.
  MEDIOCRITY GATE: C/D/F on management quality, business quality, predictability or trackability ->
  memo MUST recommend PARK. Richard makes final call at Friday review; surface in morning briefing.

BULLET FLOOR FORMULA (mandatory -- QC hard-fails if not met):
  Each RA block floor = depth_floor x (1 + n_cq) where n_cq = number of distinct CQ
  references in that block. Per-element depth floors at DD:
    E1: 10, E2: 8, E3: 4, E5: 10, E6: 3, E7: 10, E8: 3, E9: 4, E10: 3,
    E11: 4, E12: 3 (RA1 override: 16), E13: 4, E15: 3 (RA2 override: 6),
    E16: 3, E17: 3, E18: 4, E19: 4, E20: 4
  Example: E1 RA1 with 8 CQs and floor=10 -> you need at least 10x(1+8)=90 bullets.
  Write ~8 analysis sub-bullets per CQ; split every bullet >40 words into
  parent + sub-bullets.

FORMAT: same as ESA (D-AJ-21 + D-AJ-24 + F5). All floors apply.

QC: run {QC} --memo Files/{TICKER}/A-J-memo/memo.md --stage dd --meta {SIDECAR} --render-qc off
  in fix-loop (cap 3); on clean, re-run with --render-qc ON.
WRITE FUSE-safe. Memo target ~28,000 words.

SET STATE WHEN DONE (run this exact Python -- do NOT write your own summary file):
import json, os
COWORK_ROOT = os.environ.get("COWORK_ROOT", "/sessions/ecstatic-peaceful-brown/mnt/COWORK")
p = os.path.join(COWORK_ROOT, "briefings/state/{BATCH_ID}-state.json")
d = json.load(open(p))
assert "stocks" in d, "STOP: state file has wrong schema -- do not overwrite"
d["stocks"]["{TICKER}"]["status"] = "rendered"
d["stocks"]["{TICKER}"]["render_qc"] = "PASS"
tmp = p + ".tmp"
with open(tmp, "w") as f: json.dump(d, f, indent=2)
os.replace(tmp, p)
"""


def _locate_kq_reports(ticker: str, R: Path, kq_ids: list) -> str:
    """Resolve each KQ card id to its report file on disk (doc 10 L3).
    Resolution order:
      1. Subdirectory: kq_dir/<cid>/raw-AS.md  (legacy layout)
      2. Glob: any file under kq_dir matching *<cid>*
      3. Brief-card lookup: scan 3-production-inbox/ for card with kq_brief_id==cid,
         read raw_as_path field, resolve relative to R.
    """
    parts = []
    kq_dir = R / "Files" / ticker / "47-kq-research"
    prod_inbox = R / "briefings" / "pipeline" / "3-production-inbox"
    for cid in kq_ids:
        # 1. Subdirectory layout
        candidate = kq_dir / cid / "raw-AS.md"
        if candidate.exists():
            parts.append(f"  {cid}: {candidate} [PRESENT]")
            continue
        # 2. Glob under kq_dir
        found = list(kq_dir.glob(f"*{cid}*")) if kq_dir.exists() else []
        if found:
            parts.append(f"  {cid}: {found[0]} [PRESENT]")
            continue
        # 3. Brief-card lookup via 3-production-inbox
        resolved = None
        if prod_inbox.exists():
            for card_path in prod_inbox.glob("*.md"):
                try:
                    text = card_path.read_text(encoding="utf-8")
                    if f"kq_brief_id: {cid}" in text:
                        for line in text.splitlines():
                            if line.startswith("raw_as_path:"):
                                raw_rel = line.split(":", 1)[1].strip()
                                raw_abs = R / raw_rel
                                if raw_abs.exists():
                                    resolved = raw_abs
                                break
                except Exception:
                    continue
                if resolved:
                    break
        if resolved:
            parts.append(f"  {cid}: {resolved} [PRESENT]")
        else:
            parts.append(f"  {cid}: [OPTION-B: not found -- flag gap in self-review debrief para4/para5]")
    return chr(10).join(parts) if parts else "(no KQ card ids)"


def materialize_esa_writer_prompt(ticker: str, R: Path, blk: dict) -> Path:
    """ESA cumulative-delta writer prompt (doc 10 para G)."""
    sc_path = R / blk["sidecar_file"]
    sc = json.load(open(sc_path)) if sc_path.exists() else {}
    pack = sc.get("cohort_injection", {}).get("pack_path", "")
    dials = sc.get("dial_settings", {})
    prior_path = blk.get("prior_memo_path") or "(no prior Triaging memo -- write ESA full from scratch)"
    sponsor_file = blk.get("sponsor_answers_file") or "(no sponsor answers -- proceed with no steer)"
    kq_ids = blk.get("kq_brief_ids") or []
    kq_reports = _locate_kq_reports(ticker, R, kq_ids) if kq_ids else "(no KQ reports)"
    sidecar_rel = blk["sidecar_file"]  # D4: explicit sidecar path for QC command
    prompt = ESA_WRITER_PROMPT_TMPL.format(
        TICKER=ticker, COMPANY=_company_name(ticker, R),
        PRIOR_MEMO_PATH=prior_path, SPONSOR_ANSWERS_FILE=sponsor_file,
        KQ_REPORTS=kq_reports, COHORT_PACK=pack, QC=QC,
        SIDECAR=sidecar_rel,
        TRUST=dials.get("trust", "balanced"),
        COHORT_DIAL=dials.get("cohort", "normal"),
        SECTOR_DIAL=dials.get("sector", "normal"))
    out_dir = R / "Files" / ticker / "A-J-memo" / "context"
    out_dir.mkdir(parents=True, exist_ok=True)
    ppath = out_dir / "writer-task-prompt.md"
    ppath.write_text(prompt, encoding="utf-8")
    (out_dir / "writer-spawn-config.json").write_text(json.dumps(WRITER_SPAWN_CONFIG, indent=2))
    return ppath


def materialize_dd_writer_prompt(ticker: str, R: Path, blk: dict) -> Path:
    """DD cumulative-delta writer prompt (doc 10 para G)."""
    sc_path = R / blk["sidecar_file"]
    sc = json.load(open(sc_path)) if sc_path.exists() else {}
    pack = sc.get("cohort_injection", {}).get("pack_path", "")
    dials = sc.get("dial_settings", {})
    prior_path = blk.get("prior_memo_path") or "(no prior ESA memo -- write DD from scratch)"
    sponsor_file = blk.get("sponsor_answers_file") or "(no sponsor answers)"
    kq_ids = blk.get("kq_brief_ids") or []
    kq_reports = _locate_kq_reports(ticker, R, kq_ids) if kq_ids else "(no DD KQ reports)"
    sidecar_rel = blk["sidecar_file"]  # D4: explicit sidecar path for QC command
    prompt = DD_WRITER_PROMPT_TMPL.format(
        TICKER=ticker, COMPANY=_company_name(ticker, R),
        PRIOR_MEMO_PATH=prior_path, SPONSOR_ANSWERS_FILE=sponsor_file,
        KQ_REPORTS=kq_reports, COHORT_PACK=pack, QC=QC,
        SIDECAR=sidecar_rel,
        TRUST=dials.get("trust", "balanced"),
        COHORT_DIAL=dials.get("cohort", "normal"),
        SECTOR_DIAL=dials.get("sector", "normal"))
    out_dir = R / "Files" / ticker / "A-J-memo" / "context"
    out_dir.mkdir(parents=True, exist_ok=True)
    ppath = out_dir / "writer-task-prompt.md"
    ppath.write_text(prompt, encoding="utf-8")
    spawn = dict(WRITER_SPAWN_CONFIG)
    spawn["note"] = "DD: self-escalate to max effort for high-uncertainty sections per D-AJ-17"
    (out_dir / "writer-spawn-config.json").write_text(json.dumps(spawn, indent=2))
    return ppath


def _gate_state_surface(ticker: str, blk: dict) -> str:
    """Morning-briefing surface string for a human-gate wait."""
    gs = blk.get("gate_state")
    if gs == "waiting_e1":
        return (f"{ticker}: AWAITING E1 SPONSOR Q&A -- "
                "Watson will ask Richard 5 standing questions (thesis / pillar / concern / catalyst / excite-worry). "
                "Reply with answers to advance gate.")
    if gs == "waiting_e4":
        kqf = blk.get("key_questions_file", "(key-questions.json not yet written)")
        return (f"{ticker}: AWAITING E4 KEY-QUESTION APPROVAL -- "
                f"proposed questions at {kqf}. "
                "Review, approve/amend/cut, then confirm to advance gate.")
    return f"{ticker}: gate_state={gs} (no surface handler)"


def emit_peer_artifacts(ticker: str, R: Path, stage: str) -> str:
    """Station 6 (non-critical): emit this stock's peer card (Layer 1) and refresh the
    cohort/sector/industry reference summaries (Layer 2). Wrapped so it can NEVER block
    publish/close -- peer artifacts are a read-across convenience, not part of the memo."""
    try:
        here = Path(__file__).parent
        gen = here / "peer_card_gen.py"
        roll = here / "build_reference_summaries.py"
        msgs = []
        if gen.exists():
            _run(["python3", str(gen), "--ticker", ticker, "--cowork", str(R)], R)
            msgs.append("card emitted")
        if roll.exists():
            _run(["python3", str(roll), "--cowork", str(R), "--quiet"], R)
            msgs.append("summaries refreshed")
        return "; ".join(msgs) if msgs else "peer scripts absent -- skipped"
    except Exception as e:
        return f"peer-artifacts error (non-blocking): {e}"


def auto_publish(ticker: str, R: Path, stage: str) -> str:
    """Station 5 publish handler (K9 doc 09).

    triaging: generates per-stock viewer HTML; defers full deploy to nightly refresh_repository.py.
    esa/dd:   generates viewer HTML then runs refresh_repository.py (full build + deploy + git push)
              so the memo is visible on GitHub Pages immediately after close.
    """
    BUILD_SCRIPTS = R / "projects" / "SA - Reports & Memos Repository" / "build-scripts"
    gen_viewer = BUILD_SCRIPTS / "gen_memo_viewer.py"
    refresh_repo = BUILD_SCRIPTS / "refresh_repository.py"
    memo = R / "Files" / ticker / "A-J-memo" / "memo.md"
    try:
        if not gen_viewer.exists() or not memo.exists():
            return "viewer generator or memo absent -- skip viewer; state advanced to published"
        # Step 1: generate per-stock viewer HTML (all stages)
        _run(["python3", str(gen_viewer), ticker, stage, str(memo)], R)
        if stage == "triaging":
            # Triaging memos are swept up by the nightly refresh_repository.py scheduled task.
            return "viewer generated; full deploy deferred to nightly refresh_repository.py (triaging)"
        # Step 2: ESA/DD — run full refresh + git push immediately (doc 09 §5-6)
        if not refresh_repo.exists():
            return f"viewer generated; refresh_repository.py absent -- deploy manually ({stage.upper()})"
        _run(["python3", str(refresh_repo)], R)
        return f"viewer generated; refresh_repository.py complete; deployed to GitHub Pages ({stage.upper()})"
    except Exception as e:
        return f"auto_publish error ({stage}): {e}"


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="A&J memo pipeline orchestrator")
    ap.add_argument("--batch", required=True)
    ap.add_argument("--writer-mode", default="prompt", choices=("prompt", "mock"))
    ap.add_argument("--warm", action="store_true", help="warm the headless renderer once at start")
    args = ap.parse_args()
    res = advance(args.batch, args.writer_mode, args.warm)
    for line in res["log"]:
        print(line)
