#!/usr/bin/env python3
"""Chart freshness audit — scans master-dashboard/charts/*.js, reports which
per-stock charts are stale (last bar more than THRESHOLD calendar days behind the
most-recent bar seen across the whole universe). Zero dependency on the large
data JSONs. Writes a human report + a small JSON, and prints an at-a-glance line.
Run standalone or as a step in the daily refresh.  08-Jun-26."""
import os, re, json, glob, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
CHARTS = os.path.join(HERE, "..", "charts")
OUT_TXT = os.path.join(HERE, "..", "chart-freshness-report.txt")
OUT_JSON = os.path.join(HERE, "..", "data", "chart-freshness.json")
THRESHOLD = 5  # calendar days; matches the in-chart amber badge

DATE_RE = re.compile(rb'"(\d{4}-\d{2}-\d{2})"')

def last_date(path):
    """Cheap last-date read: scan the tail of the file for the final date token."""
    try:
        with open(path, "rb") as f:
            try:
                f.seek(-4096, os.SEEK_END)
            except OSError:
                f.seek(0)
            tail = f.read()
        ds = DATE_RE.findall(tail)
        return ds[-1].decode() if ds else None
    except OSError:
        return None

def main():
    files = sorted(glob.glob(os.path.join(CHARTS, "*.js")))
    rows = []
    for p in files:
        t = os.path.basename(p)[:-3]
        d = last_date(p)
        rows.append((t, d))
    dated = [(t, d) for t, d in rows if d]
    if not dated:
        print("[chart-freshness] no dated charts found"); return
    ref = max(d for _, d in dated)
    refd = datetime.date.fromisoformat(ref)
    def behind(d):
        return (refd - datetime.date.fromisoformat(d)).days
    stale = sorted(((t, d, behind(d)) for t, d in dated if behind(d) > THRESHOLD),
                   key=lambda x: -x[2])
    # LAGGING band, added 18-Aug-26.
    #
    # The 5-day threshold is well calibrated for what it was built to answer:
    # measured across the live 990-chart corpus the distribution is bimodal, 969
    # charts current and 12 dead at 81-168 days, with NOTHING between 5 and 80. So
    # ">5 days" isolates the dead series exactly, and it should not be moved.
    #
    # What it cannot see is the band that actually caused harm. On 17-Aug-26 a
    # block of Madrid-listed charts sat 2-4 days behind their own table rows, and
    # the header called every one of them "current" because they were inside 5
    # days -- while check_dead_price_series.py, using a 2-trading-day rule, was
    # flagging the same names to a file nobody displays. Two guards, two
    # thresholds, and the lax one was the one wired to the screen.
    #
    # Reporting the middle band separately, rather than moving the threshold, keeps
    # "stale = probably delisted" meaning what it has always meant and stops a
    # multi-day lag hiding inside the word "current". Additive fields only: total,
    # current and stale_count keep their existing definitions so every consumer
    # already reading this file is unaffected.
    LAG_MIN = 2
    lagging = sorted(((t, d, behind(d)) for t, d in dated
                      if LAG_MIN <= behind(d) <= THRESHOLD), key=lambda x: -x[2])
    nodate = [t for t, d in rows if not d]
    total, ncur, nstale = len(rows), len(dated) - len(stale), len(stale)
    nlag = len(lagging)
    nfresh = ncur - nlag          # charts inside the lagging floor, i.e. genuinely current
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []
    lines.append("CHART FRESHNESS AUDIT — %s" % ts)
    lines.append("Universe most-recent bar: %s   (threshold: >%d days behind = stale)" % (ref, THRESHOLD))
    lines.append("Total charts: %d   Current: %d   Lagging(%d-%dd): %d   Stale: %d   Undated: %d"
                 % (total, nfresh, LAG_MIN, THRESHOLD, nlag, nstale, len(nodate)))
    lines.append("")
    if lagging:
        lines.append("LAGGING — inside the stale threshold, but behind the universe:")
        for t, d, b in lagging:
            lines.append("  %-14s %s  %4dd" % (t, d, b))
        lines.append("")
    if stale:
        lines.append("STALE (ticker  last-bar  days-behind):")
        for t, d, b in stale:
            lines.append("  %-14s %s  %4dd" % (t, d, b))
    else:
        lines.append("No stale charts — all within threshold.")
    report = "\n".join(lines)
    try:
        with open(OUT_TXT, "w", encoding="utf-8") as f: f.write(report + "\n")
    except OSError: pass
    try:
        os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
        with open(OUT_JSON, "w", encoding="utf-8") as f:
            json.dump({"generated": ts, "reference_date": ref, "threshold_days": THRESHOLD,
                       "total": total, "current": ncur, "stale_count": nstale,
                       "lagging_floor_days": LAG_MIN, "fresh_count": nfresh,
                       "lagging_count": nlag,
                       "lagging": [{"ticker": t, "last": d, "days_behind": b} for t, d, b in lagging],
                       "stale": [{"ticker": t, "last": d, "days_behind": b} for t, d, b in stale]}, f, indent=0)
    except OSError: pass
    # at-a-glance line for the refresh log
    print("[chart-freshness] %s | current %d / %d | LAGGING %d | STALE %d%s" % (
        ref, nfresh, total, nlag, nstale,
        (": " + ", ".join("%s(%dd)" % (t, b) for t, d, b in stale[:12]) + (" ..." if nstale > 12 else "")) if stale else ""))

if __name__ == "__main__":
    main()
