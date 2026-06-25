#!/usr/bin/env python3
"""build_reference_summaries.py — Layer 2 of the peer-read-across mechanism.

Scans peer cards, groups them by cohort / sector / industry (Viewforth taxonomy:
industry BROAD, sector NARROW), and writes one living reference-summary JSON per
group with AUTO-COMPUTED base rates (grade distributions) from the cards' grades.
Deterministic + idempotent. Numeric fields computed, never written by hand.

Usage:
  python3 build_reference_summaries.py [--cowork DIR] [--cards-root DIR] [--out-root DIR] [--quiet]
  --cards-root : dir to scan for */peer-card.json (default COWORK/Files)
  --out-root   : where to write summaries  (default COWORK/databases/reference-summaries)
"""
import argparse, glob, json, os, re, tempfile, datetime, collections

GRANK = {"A": 5, "B": 4, "C": 3, "D": 2, "E": 1, "F": 0}
RGRANK = {5: "A", 4: "B", 3: "C", 2: "D", 1: "E", 0: "F"}

def cowork_root(cli):
    if cli:
        return cli
    p = os.path.dirname(os.path.abspath(__file__))
    while p and p != "/":
        if os.path.isdir(os.path.join(p, "master-dashboard")):
            return p
        p = os.path.dirname(p)
    return os.getcwd()

def safe_key(s):
    s = (s or "UNKNOWN").strip()
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")

def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return None

def find_cards(cards_root):
    cards = []
    for p in sorted(glob.glob(os.path.join(cards_root, "*", "peer-card.json"))):
        c = load_json(p)
        if c and c.get("ticker"):
            cards.append(c)
    return cards

def grade_dist(values):
    """values: list of letter grades -> {'A':n,...,'mean_grade':X,'n':N}"""
    vals = [str(v).strip("[]").upper() for v in values if v]
    vals = [v for v in vals if v in GRANK]
    if not vals:
        return None
    dist = dict(collections.Counter(vals))
    mean = round(sum(GRANK[v] for v in vals) / len(vals))
    out = {k: dist[k] for k in sorted(dist, key=lambda x: -GRANK[x])}
    out["mean_grade"] = RGRANK[mean]
    out["n"] = len(vals)
    return out

def composite(card):
    mr = card.get("grades", {}).get("master_ratings", {}) or {}
    sc, n = 0, 0
    for k, v in mr.items():
        g = (v.get("grade") if isinstance(v, dict) else v)
        g = str(g).strip("[]").upper()
        if g in GRANK:
            sc += GRANK[g]; n += 1
    return (sc / n) if n else -1

def mr_grade(card, code):
    mr = card.get("grades", {}).get("master_ratings", {}) or {}
    v = mr.get(code)
    if isinstance(v, dict):
        v = v.get("grade")
    return str(v).strip("[]").upper() if v else None

def build_group(level, key, label, cards):
    cards_sorted = sorted(cards, key=composite, reverse=True)
    mr_codes = ["MR1", "MR2", "MR3", "MR4", "MR5", "MR6"]
    mr_labels = {}
    base_mr = {}
    for code in mr_codes:
        gs = [mr_grade(c, code) for c in cards]
        d = grade_dist(gs)
        if d:
            base_mr[code] = d
        for c in cards:
            mrm = c.get("grades", {}).get("master_ratings", {}) or {}
            if code in mrm and isinstance(mrm[code], dict):
                mr_labels[code] = mrm[code].get("label", code)
    med = grade_dist([])  # placeholder
    med_results = [c.get("grades", {}).get("mediocrity_gate", {}).get("result") for c in cards]
    med_dist = dict(collections.Counter([m for m in med_results if m])) or None

    drivers, seen = [], set()
    for c in cards_sorted:
        for d in (c.get("key_drivers") or []):
            k = d.lower()[:50]
            if k not in seen:
                seen.add(k); drivers.append({"ticker": c["ticker"], "driver": d})
    constraints, seenc = [], set()
    for c in cards_sorted:
        for d in (c.get("key_constraints") or []):
            k = d.lower()[:50]
            if k not in seenc:
                seenc.add(k); constraints.append({"ticker": c["ticker"], "constraint": d})

    cross_in = []
    for c in cards:
        for lk in (c.get("organic_cross_links") or []):
            if lk.get("target_level") == level and safe_key(lk.get("target")) == safe_key(key):
                cross_in.append({"from": c["ticker"], "insight": lk.get("insight")})

    summ = {
        "schema": "reference-summary/v1",
        "level": level,
        "key": key,
        "label": label,
        "member_count": len(cards),
        "members": [c["ticker"] for c in cards_sorted],
        "mr_labels": mr_labels,
        "base_rates": {
            "master_ratings": base_mr,
            "mediocrity_gate": med_dist,
        },
        "ranked_quality": [{"ticker": c["ticker"], "mr_composite": round(composite(c), 2),
                             "recommendation": c.get("recommendation"),
                             "conviction": c.get("conviction")} for c in cards_sorted],
        "shared_change_forces": drivers[:12],
        "shared_constraints": constraints[:12],
        "differentiators": [],
        "cross_links_in": cross_in,
        "thematic_anchor": None,
        "contributing_cards": [{"ticker": c["ticker"], "stage": c.get("stage"),
                                "card_date": c.get("memo_date")} for c in cards_sorted],
        "generated": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "generator": "build_reference_summaries v1",
    }
    summ["word_count"] = len(json.dumps(summ).split())
    return summ

def fuse_write(path, data_bytes):
    d = os.path.dirname(path)
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, suffix=".tmp")
    with os.fdopen(fd, "wb") as f:
        f.write(data_bytes); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cowork", default=None)
    ap.add_argument("--cards-root", default=None)
    ap.add_argument("--out-root", default=None)
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()
    cowork = cowork_root(args.cowork)
    cards_root = args.cards_root or os.path.join(cowork, "Files")
    out_root = args.out_root or os.path.join(cowork, "databases", "reference-summaries")

    cards = find_cards(cards_root)
    levels = {"industry": {}, "sector": {}, "cohort": {}}
    labels = {"industry": {}, "sector": {}, "cohort": {}}
    for c in cards:
        cl = c.get("classification") or {}
        keymap = {"industry": cl.get("industry"), "sector": cl.get("sector"), "cohort": cl.get("cohort")}
        labmap = {"industry": cl.get("industry"), "sector": cl.get("sector"), "cohort": cl.get("cohort_name") or cl.get("cohort")}
        for lvl, key in keymap.items():
            if not key:
                continue
            levels[lvl].setdefault(key, []).append(c)
            labels[lvl][key] = labmap[lvl]

    index = {"generated": datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
             "cards_scanned": len(cards), "summaries": []}
    written = 0
    for lvl, groups in levels.items():
        for key, gcards in groups.items():
            summ = build_group(lvl, key, labels[lvl][key], gcards)
            fn = os.path.join(out_root, lvl, safe_key(key) + ".json")
            fuse_write(fn, json.dumps(summ, indent=2, ensure_ascii=False).encode())
            written += 1
            index["summaries"].append({"level": lvl, "key": key, "members": summ["member_count"],
                                       "file": os.path.relpath(fn, out_root)})
            if not args.quiet:
                print(f"  {lvl:8s} {key:40.40s} n={summ['member_count']} -> {os.path.relpath(fn, out_root)}")
    fuse_write(os.path.join(out_root, "INDEX.json"), json.dumps(index, indent=2, ensure_ascii=False).encode())
    if not args.quiet:
        print(f"DONE: {len(cards)} cards -> {written} summaries (+INDEX) under {os.path.relpath(out_root, cowork) if out_root.startswith(cowork) else out_root}")

if __name__ == "__main__":
    main()
