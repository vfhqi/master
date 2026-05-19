#!/usr/bin/env python3
# patch_md_v2_group_captions_2026_05_15.py
# -----------------------------------------------------------------------------
# Rewrites the 33 group-test caption tiles across the 8 V2 tabs that have them
# (Stage 1-4 inline strings + PI/PO/ST/CT pattern caption fields) to the format
# Richard signed off: title -> plain-English story line -> signpost intro line
# -> tests numbered one per line as questions; demi-bold (.db) on the concept +
# signpost words, underline (<u>) on the precise technical thresholds.
# Plus one global CSS block for the .db / .intro / .tline / .tnum classes.
# Dashboard-only change. No pipeline / data change. Idempotent (MARKER guard).
# Authored against git-HEAD copy of build_dashboard.py; run Windows-side.
# Usage: python patch_md_v2_group_captions_2026_05_15.py [path-to-build_dashboard.py]
# -----------------------------------------------------------------------------
import sys, os, hashlib, time, py_compile

MARKER = "MD-V2-GROUP-CAPTIONS-MARKER"

# ========================= EDIT 0 — CSS =========================
OLD_CSS = """body.chart-from-left #mo-matrix-table tbody td.mo-mx-name-cell,body.chart-from-left #mo-matrix-table thead th.mo-mx-screen-col{left:var(--chart-panel-w,0)!important;transition:left .3s ease}"""
NEW_CSS = OLD_CSS + """
/* MD-V2-GROUP-CAPTIONS-MARKER: signposting + emphasis for the rewritten group-test captions */
.gcap .db{font-weight:600;}
.gcap u{text-decoration:underline;text-underline-offset:2px;text-decoration-color:#bbb;}
.gcap .intro{display:block;font-weight:600;margin:6px 0 3px;}
.gcap .tline{display:block;padding-left:16px;text-indent:-16px;margin-top:2px;}
.gcap .tnum{font-weight:600;}"""

# ============== STAGE 1-4 — inline caption text (between </b> and </div>) ==============
# OLD = exact current caption text; NEW = rewritten HTML (double-quote attrs; no apostrophes).

OLD_S1G1 = """Is the long-term moving average still falling, but falling more slowly each month? A decelerating decline is the first hint that a downtrend is losing force. Two cells — one for the 150-day, one for the 200-day."""
NEW_S1G1 = """A <span class="db">downtrend running out of force</span> &mdash; the long-term moving averages are still falling, but each month they fall a little less than the last.<span class="intro">Two decline-deceleration tests:</span><span class="tline"><span class="tnum">(1)</span> Over the last 3 months, is the 150-day MA <u>declining but decelerating</u> &mdash; each monthly fall <u>smaller than the one before</u>?</span><span class="tline"><span class="tnum">(2)</span> The same test on the <u>200-day MA</u>?</span>"""

OLD_S1G2 = """Has the long-term trend genuinely stalled? Both 150-day and 200-day moving averages need to be within ±2% of where they were one, two, and three months ago. Flat moving averages are the clearest mechanical signature of a base."""
NEW_S1G2 = """<span class="db">The clearest mechanical signature of a base</span> &mdash; the long-term trend has genuinely stalled, neither rising nor falling.<span class="intro">Two flatness tests:</span><span class="tline"><span class="tnum">(1)</span> Is the 150-day MA <u>within &plusmn;2%</u> of where it sat <u>1, 2 and 3 months ago</u>?</span><span class="tline"><span class="tnum">(2)</span> The same test on the <u>200-day MA</u>?</span>"""

OLD_S1G3 = """Are shorter moving averages now sitting above longer ones? 50-day above 150-day (within 3%) and 150-day above 200-day (within 3%) show price has begun to lift the recent trend above the longer one — typical of a late base or early Stage 2 transition."""
NEW_S1G3 = """Price has begun to <span class="db">lift the recent trend above the longer one</span> &mdash; the look of a late base or an early Stage 2 transition.<span class="intro">Two stack tests:</span><span class="tline"><span class="tnum">(1)</span> Is the <u>50-day MA above the 150-day</u> (allowing a 3% tolerance)?</span><span class="tline"><span class="tnum">(2)</span> Is the <u>150-day MA above the 200-day</u> (same 3% tolerance)?</span>"""

OLD_S1G4 = """Are recent pullback lows higher than earlier ones? The most recent monthly low should be above the prior three monthly lows (1-month test); the most recent three-monthly low should be above the prior three (3-month test). Higher lows are the buyer-stepping-in signal."""
NEW_S1G4 = """<span class="db">Buyers stepping in earlier each time</span> &mdash; recent pullback lows are printing above the ones before them.<span class="intro">Two higher-low tests:</span><span class="tline"><span class="tnum">(1)</span> Are there <u>2 or more higher lows</u> in the recent swing structure?</span><span class="tline"><span class="tnum">(2)</span> Are there <u>3 or more</u> &mdash; the stronger signal?</span>"""

OLD_S2G1 = """Is the long-term trend up? Price above the 200-day moving average, and the 200-day rising month-on-month. The two foundational uptrend signals."""
NEW_S2G1 = """The <span class="db">foundation of a Stage 2 uptrend</span> &mdash; is the long-term trend genuinely pointing up?<span class="intro">Two foundational uptrend signals tested:</span><span class="tline"><span class="tnum">(1)</span> Is price trading <u>above its 200-day MA</u>?</span><span class="tline"><span class="tnum">(2)</span> Is the 200-day MA itself <u>rising month-on-month</u> (this month vs last)?</span>"""

OLD_S2G2 = """Is the medium-term trend up? Price above the 150-day moving average, and the 150-day above the 200-day. Confirms the long-term trend is supported by a healthy medium-term picture."""
NEW_S2G2 = """Confirmation that the long-term uptrend is <span class="db">supported by a healthy medium-term picture</span>.<span class="intro">Two medium-term tests:</span><span class="tline"><span class="tnum">(1)</span> Is price <u>above its 150-day MA</u>?</span><span class="tline"><span class="tnum">(2)</span> Is the <u>150-day MA above the 200-day</u>?</span>"""

OLD_S2G3 = """Is the short-term trend up? 50-day moving average above the 150-day. The fastest of the trend signals; turns positive at the inflection from base to breakout."""
NEW_S2G3 = """The <span class="db">fastest of the trend signals</span> &mdash; it turns positive right at the inflection from base to breakout.<span class="intro">One short-term test:</span><span class="tline"><span class="tnum">(1)</span> Is the <u>50-day MA above the 150-day</u>?</span>"""

OLD_S2G4 = """Is the stock leading on price? Within 25% of its 52-week high, and at least 25% above its 52-week low. Together: strength near highs, well off the bottom."""
NEW_S2G4 = """Is the stock <span class="db">leading on price</span> &mdash; strength near the highs, and well clear of the lows?<span class="intro">Two price-leadership tests:</span><span class="tline"><span class="tnum">(1)</span> Is price <u>within 25% of its 52-week high</u>?</span><span class="tline"><span class="tnum">(2)</span> Is price <u>more than 25% above its 52-week low</u>?</span>"""

OLD_S2G5 = """Is the stock outperforming peers? Relative strength above 70th percentile vs sector, industry, and market. Three independent strength signals across different peer groups."""
NEW_S2G5 = """Is the stock <span class="db">outperforming its peers</span> &mdash; three independent reads, not one?<span class="intro">Three relative-strength tests:</span><span class="tline"><span class="tnum">(1)</span> Is relative strength <u>above the 70th percentile vs its sector</u>?</span><span class="tline"><span class="tnum">(2)</span> The same <u>vs its industry</u>?</span><span class="tline"><span class="tnum">(3)</span> The same <u>vs the wider market</u>?</span>"""

OLD_S3G1 = """How many bases has the stock built since its 52-week low? Three or more (T1) signals a maturing run; four or more (T2) is the classic "late-stage base" warning."""
NEW_S3G1 = """<span class="db">How mature is the run?</span> Each successive base built since the low raises the odds the trend is getting late.<span class="intro">Two base-count tests:</span><span class="tline"><span class="tnum">(1)</span> Has the stock built <u>3 or more bases</u> since its 52-week low (a maturing run)?</span><span class="tline"><span class="tnum">(2)</span> <u>4 or more</u> &mdash; the classic late-stage-base warning?</span>"""

OLD_S3G2 = """Is the price trend losing momentum? The 200-day moving average is flattening (recent month-on-month change near zero and decelerating), and the 50-day has crossed below the 150-day."""
NEW_S3G2 = """<span class="db">The trend is losing its lift</span> &mdash; the long-term average is going flat and the short-term has already crossed below.<span class="intro">Two roll-over tests:</span><span class="tline"><span class="tnum">(1)</span> Is the <u>200-day MA flattening</u> &mdash; recently rising, but now its month-on-month change is <u>near zero (under 1.5%) and decelerating</u>?</span><span class="tline"><span class="tnum">(2)</span> Has the <u>50-day MA crossed below the 150-day</u>?</span>"""

OLD_S3G3 = """Three confirming distribution signals: down-volume now exceeds up-volume on a 10-day window, recent volatility is rising versus a year-ago baseline, and the price is still within 5% of the 50-day (no decisive breakout up or down)."""
NEW_S3G3 = """The clear mid-term uptrend of Stage 2 is becoming a <span class="db">tug-of-war between buyers and sellers</span> &mdash; choppier price action as <span class="db">distribution</span> creeps in.<span class="intro">Three distribution signals tested:</span><span class="tline"><span class="tnum">(1)</span> Is down-day volume <u>at least 10% above up-day volume</u>, averaged over <u>the last ~20 trading days</u>?</span><span class="tline"><span class="tnum">(2)</span> Is short-run volatility expanding &mdash; the <u>10-day ATR at least 10% above the 20-day ATR</u>?</span><span class="tline"><span class="tnum">(3)</span> Yet is price still <u>within 5% of the 50-day MA</u> &mdash; no decisive breakout up or down?</span>"""

OLD_S3G4 = """Lower lows count: two or more lower lows in the last month (T8), or three or more in the last three months (T9). Confirms downside structure is forming."""
NEW_S3G4 = """<span class="db">Downside structure is forming</span> &mdash; pullback lows are now printing below the ones before them.<span class="intro">Two lower-low tests:</span><span class="tline"><span class="tnum">(1)</span> Are there <u>2 or more lower lows in the last month</u>?</span><span class="tline"><span class="tnum">(2)</span> <u>3 or more in the last three months</u>?</span>"""

OLD_S3G5 = """Has relative strength turned down? Three-month RS change worse than minus five percent. A single test, but on a leading indicator that often turns ahead of price."""
NEW_S3G5 = """<span class="db">Relative strength has turned down</span> &mdash; a single test, but on a signal that often leads price.<span class="intro">One relative-strength test:</span><span class="tline"><span class="tnum">(1)</span> Has the stock <u>underperformed its benchmark by more than 5%</u> over the last 3 months?</span>"""

OLD_S4G1 = """Is the long-term trend confirmed down? The 200-day moving average is now lower month-on-month (T1), and the rate of decline is accelerating (T2). Two foundational decline signals."""
NEW_S4G1 = """<span class="db">The long-term trend is confirmed down</span> &mdash; and getting worse, not better.<span class="intro">Two decline tests:</span><span class="tline"><span class="tnum">(1)</span> Is the <u>200-day MA now lower month-on-month</u>?</span><span class="tline"><span class="tnum">(2)</span> Is the <u>rate of decline accelerating</u> &mdash; the latest monthly fall steeper than the one before?</span>"""

OLD_S4G2 = """Three structural tests of an inverted MA stack: full inversion P&lt;50&lt;150&lt;200 (T3), 150-day below 200-day (T4), and 50-day below 150-day (T5). Together: the stock has rolled over across all three time-horizon trends."""
NEW_S4G2 = """<span class="db">The stock has rolled over across every time horizon</span> &mdash; the moving averages are stacked upside-down.<span class="intro">Three inversion tests:</span><span class="tline"><span class="tnum">(1)</span> Is the stack <u>fully inverted</u> &mdash; price below the 50-day, below the 150-day, below the 200-day?</span><span class="tline"><span class="tnum">(2)</span> Is the <u>150-day below the 200-day</u>?</span><span class="tline"><span class="tnum">(3)</span> Is the <u>50-day below the 150-day</u>?</span>"""

OLD_S4G3 = """Is relative strength weak both in absolute level and trend? RS percentile or vs-industry below 50 (T6), and three-month RS change worse than minus five percent (T7)."""
NEW_S4G3 = """<span class="db">Relative strength is weak on both counts</span> &mdash; poor level, and still deteriorating.<span class="intro">Two relative-strength tests:</span><span class="tline"><span class="tnum">(1)</span> Is RS <u>below the 50th percentile</u> versus its industry or the wider market?</span><span class="tline"><span class="tnum">(2)</span> Has the stock <u>underperformed its benchmark by more than 5%</u> over the last 3 months?</span>"""

# ============== PI_PATTERNS — caption field, single-quoted (double-quote attrs, no apostrophes) ==============
OLD_PI1 = """In a genuine medium/long-term uptrend AND currently inside a pullback. Four tests, all must pass: 50-day MA still rising AND 150-day MA still rising AND 5-day MA rolling over AND 10-day MA rolling over."""
NEW_PI1 = """A stock in a <span class="db">real medium/long-term uptrend</span> that is <span class="db">currently inside a pullback</span> &mdash; the dip you want to see in a healthy trend.<span class="intro">Four tests &mdash; all must pass:</span><span class="tline"><span class="tnum">(1)</span> Is the <u>50-day MA still rising</u> (higher today than yesterday)?</span><span class="tline"><span class="tnum">(2)</span> Is the <u>150-day MA still rising</u>?</span><span class="tline"><span class="tnum">(3)</span> Is the <u>5-day MA rolling over</u> (lower today than yesterday &mdash; confirms the pullback)?</span><span class="tline"><span class="tnum">(4)</span> Is the <u>10-day MA rolling over</u> too?</span>"""

OLD_PI2 = """A genuine base forming within a long-term uptrend. Four tests, all must pass: price fell at least 15% from recent swing high AND price below that high for at least 20 trading days AND price above the 200-day MA AND the 200-day MA still rising month-on-month."""
NEW_PI2 = """A <span class="db">genuine base forming within an intact long-term uptrend</span> &mdash; the pause that resets a trend, not a breakdown.<span class="intro">Four tests &mdash; all must pass:</span><span class="tline"><span class="tnum">(1)</span> Did price fall <u>at least 15%</u> from its recent swing high (deepest drawdown, even if partly reclaimed since)?</span><span class="tline"><span class="tnum">(2)</span> Has price stayed <u>below that high for at least 20 trading days</u>?</span><span class="tline"><span class="tnum">(3)</span> Is price <u>above its 200-day MA</u>?</span><span class="tline"><span class="tnum">(4)</span> Is the 200-day MA <u>still rising month-on-month</u>?</span>"""

OLD_PI3 = """A stock in genuine breakdown. Two tests, both must pass: price 30%+ below the 52-week high AND price fallen at least 20% from its recent high."""
NEW_PI3 = """A stock in <span class="db">genuine breakdown</span> &mdash; not a dip, a decisive failure.<span class="intro">Two tests &mdash; both must pass:</span><span class="tline"><span class="tnum">(1)</span> Is price <u>30% or more below its 52-week high</u>?</span><span class="tline"><span class="tnum">(2)</span> Has price <u>fallen at least 20% from its recent high</u>?</span>"""

# ============== PO_PATTERNS — "caption" field, double-quoted (single-quote attrs, no double-quotes) ==============
OLD_PO1 = """A confirmed upside break. Two tests, both must pass: price more than 8% above the 5-day moving average AND recent up-day volume at least 10% higher than down-day volume."""
NEW_PO1 = """A <span class='db'>confirmed upside break</span> &mdash; price thrusting clear of its short-term average on real buying.<span class='intro'>Two tests &mdash; both must pass:</span><span class='tline'><span class='tnum'>(1)</span> Is price <u>more than 8% above its 5-day MA</u>?</span><span class='tline'><span class='tnum'>(2)</span> Is recent <u>up-day volume at least 10% above down-day volume</u>?</span>"""

OLD_PO2 = """A steady advance without a breakout spike. Qualifies on three tests (price above the 20-day moving average, 20-day moving average rising, and not currently in a breakout) - the not-in-breakout test is part of the logic but not shown as a column."""
NEW_PO2 = """A <span class='db'>steady advance without a breakout spike</span> &mdash; grinding higher rather than gapping.<span class='intro'>Three tests (the third is logic-only, not shown as a column):</span><span class='tline'><span class='tnum'>(1)</span> Is price <u>above its 20-day MA</u>?</span><span class='tline'><span class='tnum'>(2)</span> Is the <u>20-day MA rising</u>?</span><span class='tline'><span class='tnum'>(3)</span> Is the stock <u>not currently in a Breakout</u>?</span>"""

OLD_PO3 = """A fresh break below medium-term support. Two tests, both must pass: price below the 50-day moving average AND price was at or above the 50-day moving average on the prior bar."""
NEW_PO3 = """A <span class='db'>fresh break below medium-term support</span> &mdash; the first crack, caught as it happens.<span class='intro'>Two tests &mdash; both must pass:</span><span class='tline'><span class='tnum'>(1)</span> Is price <u>below its 50-day MA</u>?</span><span class='tline'><span class='tnum'>(2)</span> Was price <u>at or above the 50-day MA on the prior bar</u> (confirming this is a fresh break)?</span>"""

OLD_PO4 = """A fresh break below the medium/long-term trend. Two tests, both must pass: price below the 150-day moving average AND price was at or above the 150-day moving average on the prior bar."""
NEW_PO4 = """A <span class='db'>fresh break below the medium/long-term trend</span> &mdash; a more serious failure than the 50-day break.<span class='intro'>Two tests &mdash; both must pass:</span><span class='tline'><span class='tnum'>(1)</span> Is price <u>below its 150-day MA</u>?</span><span class='tline'><span class='tnum'>(2)</span> Was price <u>at or above the 150-day MA on the prior bar</u>?</span>"""

OLD_PO5 = """A fresh break below the long-term trend - the most serious of the three. Two tests, both must pass: price below the 200-day moving average AND price was at or above the 200-day moving average on the prior bar."""
NEW_PO5 = """A <span class='db'>fresh break below the long-term trend</span> &mdash; the most serious of the three breakdowns.<span class='intro'>Two tests &mdash; both must pass:</span><span class='tline'><span class='tnum'>(1)</span> Is price <u>below its 200-day MA</u>?</span><span class='tline'><span class='tnum'>(2)</span> Was price <u>at or above the 200-day MA on the prior bar</u>?</span>"""

# ============== ST_PATTERNS — "caption" field, double-quoted (single-quote attrs) ==============
OLD_ST1 = """A small initial allocation when a stock has collapsed or is in a struggling stage but shows a fresh breakout. Two tests: a qualifying stage or collapsing indicator AND a breakout."""
NEW_ST1 = """A <span class='db'>small initial allocation</span> &mdash; a stock that has collapsed or is stuck in a struggling stage, but is showing a fresh breakout worth a starter position.<span class='intro'>Two tests:</span><span class='tline'><span class='tnum'>(1)</span> Is the stock in a <u>qualifying stage</u> (Stage 1 plausible+, Stage 3 invalidating, or Stage 4 plausible+) <u>or showing the Collapsing indicator</u>?</span><span class='tline'><span class='tnum'>(2)</span> Is the <u>Breakout post-test indicator firing</u>?</span>"""

OLD_ST2 = """A core position setup - a stock coming out of a base into a new uptrend with a genuine volatility-contraction pattern. Four VCP tests, all must pass; qualification also needs the Stage 1-to-2 transition (shown as an info column)."""
NEW_ST2 = """A <span class='db'>core position setup</span> &mdash; a stock coming out of a base into a new uptrend with a genuine volatility-contraction pattern.<span class='intro'>Four VCP tests &mdash; all must pass (plus the Stage 1-to-2 transition gate, shown as an info column):</span><span class='tline'><span class='tnum'>(1)</span> Are the price <u>contractions narrowing</u> &mdash; each pullback shallower than the one before?</span><span class='tline'><span class='tnum'>(2)</span> Are there <u>2 to 4 contractions</u> in the base?</span><span class='tline'><span class='tnum'>(3)</span> Is <u>volume declining</u> across successive contractions?</span><span class='tline'><span class='tnum'>(4)</span> Are the <u>contraction lows higher</u> &mdash; each above the previous?</span>"""

OLD_ST3 = """A core position setup - a stock in a genuine uptrend whose pullback toward a moving average is orderly: contracting volume, contracting volatility, few distribution days, buying through the last ten days. Six tests, all must pass."""
NEW_ST3 = """A <span class='db'>core position setup</span> &mdash; a stock in a genuine uptrend whose pullback toward a moving average is <span class='db'>orderly, not violent</span>.<span class='intro'>Six tests &mdash; all must pass:</span><span class='tline'><span class='tnum'>(1)</span> Is <u>volume contracting</u> &mdash; 10-day average volume below the 50-day?</span><span class='tline'><span class='tnum'>(2)</span> Is <u>up-day volume at least 5% above down-day volume</u> over the last month?</span><span class='tline'><span class='tnum'>(3)</span> Are there <u>three or fewer distribution days</u> in the last 25 sessions?</span><span class='tline'><span class='tnum'>(4)</span> Is <u>volatility contracting</u> &mdash; the 10-day ATR below the 20-day?</span><span class='tline'><span class='tnum'>(5)</span> Has price come down to <u>within range of a meaningful MA</u> (50/100/150/200-day)?</span><span class='tline'><span class='tnum'>(6)</span> Is the stock <u>buying through the last 10 days</u> &mdash; at least half closing in the upper 40% of their daily range?</span>"""

OLD_ST4 = """A core position setup - a stock already in a Stage 2 uptrend that has built a fresh base with a genuine volatility-contraction pattern. Four VCP tests, all must pass; qualification also needs the Stage 2 base (shown as an info column)."""
NEW_ST4 = """A <span class='db'>core position setup</span> &mdash; a stock already in a Stage 2 uptrend that has built a <span class='db'>fresh base</span> with a genuine volatility-contraction pattern.<span class='intro'>Four VCP tests &mdash; all must pass (plus the Stage 2 base gate, shown as an info column):</span><span class='tline'><span class='tnum'>(1)</span> Are the price <u>contractions narrowing</u> &mdash; each pullback shallower than the last?</span><span class='tline'><span class='tnum'>(2)</span> Are there <u>2 to 4 contractions</u> in the base?</span><span class='tline'><span class='tnum'>(3)</span> Is <u>volume declining</u> across successive contractions?</span><span class='tline'><span class='tnum'>(4)</span> Are the <u>contraction lows higher</u> &mdash; each above the previous?</span>"""

# ============== CT_PATTERNS — "caption" field, double-quoted (single-quote attrs) ==============
OLD_CT1 = """Pairs with the Healthy retest setup. Six setup columns describe how orderly the pullback into the moving average was; two trigger columns confirm the reclaim. Pass: testing a meaningful MA AND closed back above it AND confirmed, with the pullback healthy on volume or candles."""
NEW_CT1 = """<span class='db'>The trigger that pairs with the Healthy retest setup</span> &mdash; price reclaiming the moving average it pulled back to.<span class='intro'>Six setup columns + two trigger columns. To qualify:</span><span class='tline'><span class='tnum'>(1)</span> Is price <u>testing a meaningful MA</u> and has it <u>closed back above it</u>?</span><span class='tline'><span class='tnum'>(2)</span> Is the reclaim <u>confirmed by a close at least 2% above yesterday</u>?</span><span class='tline'><span class='tnum'>(3)</span> Was the pullback itself <u>healthy</u> &mdash; orderly on volume, distribution, volatility and candles (the six setup columns)?</span>"""

OLD_CT2 = """Pairs with the VCP-after-Stage-1→2 setup. A gate column requires Stage 1 to be rated Probable (Early or Late); four contraction columns describe the VCP; two trigger columns confirm the breakout. Pass: gate AND all four contraction tests AND breakout AND confirmation."""
NEW_CT2 = """<span class='db'>The deployment trigger for a VCP breaking out of a Stage 1 base</span>.<span class='intro'>One gate + four contraction + two trigger columns. To pass &mdash; gate AND all four contractions AND breakout AND confirmation:</span><span class='tline'><span class='tnum'>(1)</span> Gate: is <u>Stage 1 rated Probable</u> (Early or Late)?</span><span class='tline'><span class='tnum'>(2)</span> Do the four VCP tests pass &mdash; <u>narrowing contractions, 2-4 of them, declining volume, higher lows</u>?</span><span class='tline'><span class='tnum'>(3)</span> Trigger: is the <u>Breakout indicator firing</u>, <u>confirmed by a close at least 2% above yesterday</u>?</span>"""

OLD_CT3 = """Pairs with the VCP-after-Stage-2-base setup. A gate column requires a Stage 2 uptrend with the Basing pre-test indicator qualifying; four contraction columns describe the VCP; two trigger columns confirm the breakout. Pass: gate AND all four contraction tests AND breakout AND confirmation."""
NEW_CT3 = """<span class='db'>The deployment trigger for a VCP breaking out of a fresh Stage 2 base</span>.<span class='intro'>One gate + four contraction + two trigger columns. To pass &mdash; gate AND all four contractions AND breakout AND confirmation:</span><span class='tline'><span class='tnum'>(1)</span> Gate: is the stock in a <u>Stage 2 uptrend with the Basing indicator qualifying</u>?</span><span class='tline'><span class='tnum'>(2)</span> Do the four VCP tests pass &mdash; <u>narrowing contractions, 2-4 of them, declining volume, higher lows</u>?</span><span class='tline'><span class='tnum'>(3)</span> Trigger: is the <u>Breakout indicator firing</u>, <u>confirmed by a close at least 2% above yesterday</u>?</span>"""

OLD_CT4 = """Pairs with the Probing bet setup. One setup column requires the probing-bet stage to be Late or Capital; two trigger columns confirm the breakout. The Collapsing pre-test indicator rating is shown as an info column - context only, not part of the pass logic."""
NEW_CT4 = """<span class='db'>The deployment trigger for the Probing bet setup</span> &mdash; a fresh breakout on a stock worth a small starter position.<span class='intro'>One setup + two trigger columns (Collapsing shown as context only). To pass:</span><span class='tline'><span class='tnum'>(1)</span> Setup: does the <u>Probing bet filter rate the stock Late or Capital</u>?</span><span class='tline'><span class='tnum'>(2)</span> Trigger: is the <u>Breakout indicator firing</u>?</span><span class='tline'><span class='tnum'>(3)</span> Trigger: is it <u>confirmed by a close at least 2% above yesterday</u>?</span>"""

EDITS = [
    ("EDIT 0  CSS: .db / .intro / .tline / .tnum classes", OLD_CSS, NEW_CSS),
    ("EDIT 1  Stage 1 G1 - Slowing decline",        ">" + OLD_S1G1 + "</div>", ">" + NEW_S1G1 + "</div>"),
    ("EDIT 2  Stage 1 G2 - Flat moving averages",   ">" + OLD_S1G2 + "</div>", ">" + NEW_S1G2 + "</div>"),
    ("EDIT 3  Stage 1 G3 - Moving average stack",   ">" + OLD_S1G3 + "</div>", ">" + NEW_S1G3 + "</div>"),
    ("EDIT 4  Stage 1 G4 - Higher lows",            ">" + OLD_S1G4 + "</div>", ">" + NEW_S1G4 + "</div>"),
    ("EDIT 5  Stage 2 G1 - Long-term trend",        ">" + OLD_S2G1 + "</div>", ">" + NEW_S2G1 + "</div>"),
    ("EDIT 6  Stage 2 G2 - Medium-term trend",      ">" + OLD_S2G2 + "</div>", ">" + NEW_S2G2 + "</div>"),
    ("EDIT 7  Stage 2 G3 - Short-term trend",       ">" + OLD_S2G3 + "</div>", ">" + NEW_S2G3 + "</div>"),
    ("EDIT 8  Stage 2 G4 - Price leadership",       ">" + OLD_S2G4 + "</div>", ">" + NEW_S2G4 + "</div>"),
    ("EDIT 9  Stage 2 G5 - Relative strength",      ">" + OLD_S2G5 + "</div>", ">" + NEW_S2G5 + "</div>"),
    ("EDIT 10 Stage 3 G1 - Base count",             ">" + OLD_S3G1 + "</div>", ">" + NEW_S3G1 + "</div>"),
    ("EDIT 11 Stage 3 G2 - Price trend rolling over",">" + OLD_S3G2 + "</div>", ">" + NEW_S3G2 + "</div>"),
    ("EDIT 12 Stage 3 G3 - The debate",             ">" + OLD_S3G3 + "</div>", ">" + NEW_S3G3 + "</div>"),
    ("EDIT 13 Stage 3 G4 - Lower lows",             ">" + OLD_S3G4 + "</div>", ">" + NEW_S3G4 + "</div>"),
    ("EDIT 14 Stage 3 G5 - RS trend",               ">" + OLD_S3G5 + "</div>", ">" + NEW_S3G5 + "</div>"),
    ("EDIT 15 Stage 4 G1 - Price trend down",       ">" + OLD_S4G1 + "</div>", ">" + NEW_S4G1 + "</div>"),
    ("EDIT 16 Stage 4 G2 - MA stack inverted",      ">" + OLD_S4G2 + "</div>", ">" + NEW_S4G2 + "</div>"),
    ("EDIT 17 Stage 4 G3 - Relative strength weak", ">" + OLD_S4G3 + "</div>", ">" + NEW_S4G3 + "</div>"),
    ("EDIT 18 PI - Pulling back",   "caption: '" + OLD_PI1 + "'", "caption: '" + NEW_PI1 + "'"),
    ("EDIT 19 PI - Basing",         "caption: '" + OLD_PI2 + "'", "caption: '" + NEW_PI2 + "'"),
    ("EDIT 20 PI - Collapsing",     "caption: '" + OLD_PI3 + "'", "caption: '" + NEW_PI3 + "'"),
    ('EDIT 21 PO - Breakout',          '"caption": "' + OLD_PO1 + '"', '"caption": "' + NEW_PO1 + '"'),
    ('EDIT 22 PO - Advancing',         '"caption": "' + OLD_PO2 + '"', '"caption": "' + NEW_PO2 + '"'),
    ('EDIT 23 PO - Breakdown 50D',     '"caption": "' + OLD_PO3 + '"', '"caption": "' + NEW_PO3 + '"'),
    ('EDIT 24 PO - Breakdown 150D',    '"caption": "' + OLD_PO4 + '"', '"caption": "' + NEW_PO4 + '"'),
    ('EDIT 25 PO - Breakdown 200D',    '"caption": "' + OLD_PO5 + '"', '"caption": "' + NEW_PO5 + '"'),
    ('EDIT 26 ST - Probing bet',       '"caption": "' + OLD_ST1 + '"', '"caption": "' + NEW_ST1 + '"'),
    ('EDIT 27 ST - VCP after S1-2',    '"caption": "' + OLD_ST2 + '"', '"caption": "' + NEW_ST2 + '"'),
    ('EDIT 28 ST - Healthy retest',    '"caption": "' + OLD_ST3 + '"', '"caption": "' + NEW_ST3 + '"'),
    ('EDIT 29 ST - VCP after S2 base', '"caption": "' + OLD_ST4 + '"', '"caption": "' + NEW_ST4 + '"'),
    ('EDIT 30 CT - MA retest upwards', '"caption": "' + OLD_CT1 + '"', '"caption": "' + NEW_CT1 + '"'),
    ('EDIT 31 CT - VCP deploy S1',     '"caption": "' + OLD_CT2 + '"', '"caption": "' + NEW_CT2 + '"'),
    ('EDIT 32 CT - VCP deploy S2',     '"caption": "' + OLD_CT3 + '"', '"caption": "' + NEW_CT3 + '"'),
    ('EDIT 33 CT - Probing bet',       '"caption": "' + OLD_CT4 + '"', '"caption": "' + NEW_CT4 + '"'),
]

def md5(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "build_dashboard.py")
    if not os.path.isfile(path):
        print("ERROR: target not found: %s" % path); sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    print("Target : %s" % path)
    print("Before : %d bytes  md5 %s" % (len(content.encode("utf-8")), md5(content)))

    if MARKER in content:
        print("Already patched (MARKER present) -- no-op, exiting clean.")
        sys.exit(0)

    for label, old, new in EDITS:
        n = content.count(old)
        if n != 1:
            print("ERROR: %s -- anchor found %d times (expected 1). Aborting, file untouched." % (label, n))
            sys.exit(2)
        content = content.replace(old, new, 1)
        print("  ok  %s" % label)

    mk = content.count(MARKER)
    if mk != 1:
        print("ERROR: MARKER count is %d (expected 1). Aborting, file untouched." % mk)
        sys.exit(3)

    tmp = path + ".tmp-groupcaps"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    try:
        py_compile.compile(tmp, doraise=True)
    except py_compile.PyCompileError as e:
        print("ERROR: patched file fails py_compile -- aborting. %s" % e)
        os.remove(tmp); sys.exit(4)

    bak = path + ".bak-pre-group-captions-" + time.strftime("%Y%m%d-%H%M%S")
    with open(path, "r", encoding="utf-8") as f:
        orig = f.read()
    with open(bak, "w", encoding="utf-8") as f:
        f.write(orig)
    os.replace(tmp, path)

    with open(path, "r", encoding="utf-8") as f:
        final = f.read()
    print("After  : %d bytes  md5 %s" % (len(final.encode("utf-8")), md5(final)))
    print("Backup : %s" % bak)
    print("MARKER occurrences: %d   py_compile: OK" % final.count(MARKER))
    print("DONE -- 34 edits applied (1 CSS + 17 stage + 16 pattern captions). Next: python scripts/build_dashboard.py")

if __name__ == "__main__":
    main()
