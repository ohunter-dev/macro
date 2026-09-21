# Macro / Rates

Self-study project building desk-level tools for pricing and interpreting the
US rates and inflation landscape — real data, validated two ways wherever possible.

## Structure

- `src/fred.py` — FRED API wrapper
- `src/inflation.py` — CPI/PCE/PPI pulls, YoY/MoM/3m/6m annualized rates
- `src/curve.py` — Treasury par curve, daily change decomposition, regime
  classification (bear/bull × flattener/steepener)
- `src/realrates.py` — nominal/real/breakeven decomposition (TIPS-implied)
- `src/termpremium.py` — ACM term premium (NY Fed model via FRED)
- `src/fedpath.py` — Fed funds futures (ZQ) meeting-weighted probability engine
- `src/kalshi.py` — Kalshi prediction-market client (pagination-safe)
- `src/fedcurve.py` — multi-meeting Fed path built from Kalshi ladders, with
  reliability diagnostics

## Phase 1 — Inflation and curve foundations

CPI vs PCE vs PPI (weights, scope, formula differences), core vs headline vs
supercore, shelter's lag behind market rents. Treasury par curve mechanics
and the instrument ladder (fed funds → SOFR → bills → notes → bonds).

## Phase 2 — Regime classification and real yields

Daily curve moves decomposed into level/slope shifts, classified into four
regimes (bear flattening, bear steepening, bull steepening, bull flattening)
against a noise threshold. Real yields and breakevens (nominal = real +
breakeven), and the ACM term premium as the third decomposition of the
nominal yield (nominal = expected average short rate + term premium).

## Phase 3 — Pricing the Fed: futures math and prediction markets

The question this phase answers: what does the market actually think the Fed
funds rate will be after each upcoming meeting, and how much should you trust
that number?

**Two independent methods, built and cross-checked against each other:**

1. **Fed funds futures (`fedpath.py`)** — ZQ futures settle on the monthly
   *average* effective rate, not a point-in-time rate. For a meeting that
   falls mid-month, the contract's implied rate is a days-weighted blend of
   the pre-meeting and post-meeting rate. `solve_post_meeting_rate` inverts
   that weighting to back out the market-implied post-meeting rate from the
   futures price, and `hike_probability` converts that into a probability
   against the current effective rate. Validated with a round-trip test
   (construct a scenario table with known probabilities → generate the
   implied price → recover the same probabilities) and cross-checked live
   against Kalshi's own quoted probability for the September meeting — the
   two methods agreed almost exactly (96.2697 engine vs 96.2700/85.7% from
   the constructed table).

2. **Kalshi prediction markets (`kalshi.py`, `fedcurve.py`)** — Kalshi lists
   each FOMC meeting as an event with a *ladder* of cumulative strikes:
   each market quotes P(rate above X), not a single discrete outcome.
   `strike_ladder` pulls one meeting's ladder; `discrete_probs` differences
   adjacent cumulative strikes into per-bucket probabilities. The bucket
   between two strikes takes the *upper* strike as its rate — being "above
   3.50 but not above 3.75" means the rate is 3.75, not 3.50. Getting this
   backwards silently understates every expected rate by exactly one hike
   step (25bp).

   `expected_rate` gives the probability-weighted expected upper bound of
   the target range per meeting; `ladder_volume` gives the traded size
   behind it.

**Reliability, not just output:** a probability table is worthless if it's
built on quotes nobody actually traded. Three independent diagnostics are run
per meeting:

- `probability_mass` — do the discrete buckets sum to ~100%? Missing mass
  means probability sitting below the lowest quoted strike that the ladder
  can't see.
- `is_contiguous` — are the strikes gapless? A hole in the ladder means an
  expected-rate calculation is silently wrong, not just imprecise.
- `is_reliable` (avg spread ≤ 5c) — the actual trust boundary. Wide spreads
  mean the "mid price" is arithmetic, not a market view. Proved this
  concretely: watched the April 2027 expected rate move 5bp between two
  consecutive runs with zero change in volume — a market that isn't trading
  doesn't produce information, whatever its quoted mid says.

**Result:** October and December 2026 meetings are reliable (tight spreads,
full probability mass, real volume). January 2027 onward are not (30–45 cent
spreads vs 1–1.5 cents on the near months, incomplete mass, prices that move
with no trades behind them). This boundary is documented as a finding, not
patched around — knowing where a tool stops being trustworthy is part of
what the tool is for.

Meeting dates are pulled from each market's own `rules_primary` text rather
than a hardcoded calendar — an earlier hardcoded list invented a nonexistent
November 2026 meeting and omitted October entirely.

## Usage

```bash
python -m src.fedcurve
```

Prints: all live Kalshi FOMC event tickers found → a per-meeting expected
upper-bound table with implied move (bp) and volume, flagging any meeting
whose spreads are too wide to trust → the discrete probability distribution
for the nearest meeting → the three reliability diagnostics per meeting.

## Known simplifications

- Fed funds futures engine assumes each meeting is the only rate-change event
  in its settlement month — doesn't yet handle two changes in one month.
- `is_reliable`'s 5-cent spread threshold is a judgment call, tuned against
  the observed 2026 vs 2027 spread gap on this specific set of contracts, not
  derived from a model of fair bid-ask width.
- FRED/Treasury series (curve, ACM term premium) are published to 2 decimal
  places and are themselves model/fitted outputs, not raw traded prices —
  ~1bp "breaks" in identity checks against them are rounding noise, not a bug.
- No adjustment yet for Kalshi contract fees/rounding on settlement.
- Phase 4 (event studies: regressing yield changes on CPI/PPI/NFP surprises)
  and Phase 5 (rates vol overlay) are planned, not built.