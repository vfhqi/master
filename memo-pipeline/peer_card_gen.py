#!/usr/bin/env python3
"""peer_card_gen.py — emit a peer-card JSON for one stock (Layer 1 of the
peer-read-across mechanism). See PEER-CARD-AND-REFERENCE-SUMMARY-SCHEMA-v1.md.

Faithful + deterministic: classification from universe.json (SSoT), grades from
the memo's ratings.json (already structured), prose fields extracted from the
memo's curated Section A snapshot + B.2 BLUF (polarity-marked spans). Never
invents: absent fields become null.

Usage:
  python3 peer_card_gen.py --ticker BRAV-SE [--cowork /path/to/COWORK] [--stdout]
"""
import argparse, json, os, re, sys, tempfile, datetime

MR_LABELS = {
    "MR1": "Technical momentum",
    "MR2": "Sell-side earnings momentum",
    "MR3": "Thematic fit",
    "MR4": "Pillar I: Case change elements",
    "MR5": "Pillar II: Case building blocks",
    "MR6": "Pillar III: Investment case components",
}

cowork_recycle = None

def cowork_root(cli):
    if cli:
        return cli
    here = os.path.abspath(__file__)
    p = here
    for _ in range(4):
        p = os.path.dirname(p)
        if os.path.basename(p) == "COWORK":
            return p
    p = os.path.dirname(here)
    while p and p != "/":
        if os.path.isdir(os.path.join(p, "master-dashboard")):
            return p
        p = os.path.dirname(p)
    return os.getcwd()

EMPH = re.compile(r"[=_*~`]+")
def strip_emph(s):
    if s is None:
        return None
    s = s.strip()
    s = EMPH.sub("", s)
    s = re.sub(r"^\s*[+\-~]\s*", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.strip(" ;,")

def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None

def classify(cowork, ticker):
    uni = load_json(os.path.join(cowork, "master-dashboard", "data", "universe.json"))
    if not uni:
        return None
    for s in uni.get("stocks", []):
        if s.get("ticker") == ticker:
            return {
                "industry": s.get("industry"),
                "sector": s.get("sector"),
                "cohort": s.get("cohort"),
                "cohort_name": s.get("cohort_name"),
            }
    return None

def exec_region(memo_text):
    a = memo_text.find("## Section A")
    if a < 0:
        a = 0
    end = memo_text.find("### B.3")
    if end < 0:
        end = memo_text.find("## Section C")
    if end < 0:
        end = min(len(memo_text), a + 9000)
    return memo_text[a:end]

POLARITY = {
    "+": re.compile(r"==\+(.+?)=="),
    "-": re.compile(r"==-(.+?)=="),
}

def _clean_span(txt):
    if not txt or len(txt) < 15:
        return False
    if " " not in txt:
        return False
    if txt.count("(") > txt.count(")"):
        return False
    if txt.rstrip().endswith(("(", ",", "and", "the", "of", "to")):
        return False
    return True

def extract_polarity(region, sign, cap=4):
    out, seen = [], set()
    for m in POLARITY[sign].finditer(region):
        txt = strip_emph(m.group(1))
        if not _clean_span(txt):
            continue
        key = txt.lower()[:40]
        if any(key in s.lower() or s.lower()[:40] == key for s in out):
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(txt)
        if len(out) >= cap:
            break
    return out

def first_sentence(s, maxlen=260):
    s = strip_emph(s)
    if not s:
        return None
    m = re.search(r"(.+?[\.;])(\s|$)", s)
    out = m.group(1) if m else s
    return out[:maxlen].strip()

def extract_thesis(memo_text):
    m = re.search(r"Page-level BLUF[:—\-]*\s*(.+)", memo_text)
    if m:
        return first_sentence(m.group(1))
    m = re.search(r"### B\.2 — BLUF\s*(.+?)(?:\n###|\n## )", memo_text, re.S)
    if m:
        for ln in m.group(1).strip().splitlines():
            t = strip_emph(ln)
            if t and len(t) > 20:
                return first_sentence(t)
    return None

def snap_field(region, label):
    m = re.search(r"\*\*%s:\*\*\s*(.+)" % re.escape(label), region)
    if not m:
        m = re.search(r"%s:\s*(.+)" % re.escape(label), region)
    return strip_emph(m.group(1)) if m else None

def build_valuation(region):
    return {
        "forward_pe": snap_field(region, "Forward P/E"),
        "target_price": snap_field(region, "Target price"),
        "live_price": snap_field(region, "Live price"),
        "buy_pct": snap_field(region, "Buy rating %"),
        "revenue_ltm": snap_field(region, "Revenue (LTM)"),
        "ebit_margin_ltm": snap_field(region, "EBIT margin (LTM)"),
    }

def build_card(cowork, ticker, source_type="memo"):
    tdir = os.path.join(cowork, "Files", ticker, "A-J-memo")
    ratings = load_json(os.path.join(tdir, "ratings.json")) or {}
    memo_path = os.path.join(tdir, "memo.md")
    memo_text = ""
    if os.path.exists(memo_path):
        with open(memo_path, errors="replace") as f:
            memo_text = f.read()
    region = exec_region(memo_text) if memo_text else ""
    cls = classify(cowork, ticker)
    mr = ratings.get("master_ratings") or {}
    master_ratings = {k: {"grade": v, "label": MR_LABELS.get(k, k)} for k, v in mr.items()}

    card = {
        "schema": "peer-card/v1",
        "ticker": ticker,
        "company": ratings.get("company") or ticker,
        "source_type": source_type,
        "stage": ratings.get("stage"),
        "memo_date": ratings.get("memo_date"),
        "source_path": os.path.relpath(memo_path, cowork) if memo_text else None,
        "classification": cls,
        "memo_cohort_tag": ratings.get("cohort"),
        "thesis_one_line": extract_thesis(memo_text) if memo_text else None,
        "lead_pillar": None,
        "key_drivers": extract_polarity(region, "+") if region else [],
        "key_constraints": extract_polarity(region, "-") if region else [],
        "grades": {
            "master_ratings": master_ratings,
            "elements": ratings.get("elements") or {},
            "mediocrity_gate": {
                "result": ratings.get("mediocrity_gate"),
                **(ratings.get("mediocrity_gate_dimensions") or {}),
            },
        },
        "kill_shot": ratings.get("kill_shot"),
        "catalysts": [c for c in [
            ratings.get("add_gate") and ("Add gate: " + ratings["add_gate"]),
        ] if c],
        "valuation_snapshot": build_valuation(region) if region else {},
        "recommendation": ratings.get("recommendation"),
        "conviction": ratings.get("conviction"),
        "entry_range": ratings.get("entry_range_sek"),
        "organic_cross_links": [],
        "staleness_date": ratings.get("memo_date"),
        "generated": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "generator": "peer_card_gen v1",
    }
    grank = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1, "F": 0}
    pillar_map = [("MR4", "Case change elements (Pillar I)"),
                  ("MR6", "Investment case components (Pillar III)"),
                  ("MR5", "Case building blocks (Pillar II)")]
    best = None
    for code, name in pillar_map:
        g = mr.get(code)
        if g is None:
            continue
        score = grank.get(str(g).strip("[]").upper(), -1)
        if best is None or score > best[0]:
            best = (score, name)
    card["lead_pillar"] = best[1] if best else None
    return card

def fuse_write(path, data_bytes):
    global cowork_recycle
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    if os.path.exists(path) and cowork_recycle:
        os.makedirs(cowork_recycle, exist_ok=True)
        rec = os.path.join(cowork_recycle, os.path.basename(path) + "." + datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
        try:
            os.replace(path, rec)
        except Exception:
            pass
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    with os.fdopen(fd, "wb") as f:
        f.write(data_bytes); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ticker", required=True)
    ap.add_argument("--cowork", default=None)
    ap.add_argument("--source-type", default="memo")
    ap.add_argument("--stdout", action="store_true")
    args = ap.parse_args()
    cowork = cowork_root(args.cowork)
    global cowork_recycle
    cowork_recycle = os.path.join(cowork, "recycling-bin")
    card = build_card(cowork, args.ticker, args.source_type)
    blob = json.dumps(card, indent=2, ensure_ascii=False).encode()
    if args.stdout:
        sys.stdout.write(blob.decode()); sys.stdout.flush()
        return
    out = os.path.join(cowork, "Files", args.ticker, "peer-card.json")
    fuse_write(out, blob)
    print("WROTE", os.path.relpath(out, cowork), len(blob), "bytes")

if __name__ == "__main__":
    main()
