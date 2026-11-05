# Macro / Rates

Python tools for reading the US rates picture from public data: where inflation is running, how the Treasury curve is moving, how the 10y splits into real yield, breakeven and term premium, and what futures and Kalshi are pricing for each FOMC meeting. Where possible, each number is checked against a second source.

## Example output

`python -m src.fedcurve`, run on 5 November 2026:

```
current target range upper bound: 4.00% (FRED DFEDTARU, as of 2026-11-04)

       meeting         date  exp upper  vs today  vs prev     volume
----------------------------------------------------------------------
   KXFED-26DEC   2026-12-09     4.196%      +20bp     +20bp    795,759
   KXFED-27JAN   2027-01-27     4.332%      +33bp     +14bp     59,809  << unreliable
   KXFED-27MAR   2027-03-17     4.365%      +37bp      +3bp     57,202  << unreliable
   KXFED-27APR   2027-04-28     4.857%      +86bp     +49bp    176,026  << unreliable

--- KXFED-26DEC (2026-12-09) distribution ---
  upper bound <=2.75%:    2.0%
  upper bound   3.00%:   -1.5%
  upper bound   3.25%:    0.5%
  upper bound   3.50%:   -0.5%
  upper bound   3.75%:    1.0%
  upper bound   4.00%:   18.0%  <- today
  upper bound   4.25%:   79.0%
  upper bound   4.50%:    1.0%
  upper bound   5.50%:    0.5%
  check: buckets sum to 100.0%, expected upper 4.196%

  vs today's 4.00%: hike 80% | hold 18% | cut 2%
  market read: hike is the most likely outcome (80%)

--- diagnostics per meeting ---
       meeting  contig  tail lo  tail hi    neg  excess  spread  reliable
   KXFED-26DEC    True     2.0%     0.5%  -2.0%    0.0%    1.4c      True
   KXFED-27JAN    True     1.5%     5.0%  -2.5%    0.0%    5.8c     False
   KXFED-27MAR    True     3.0%     3.5%  -3.0%    0.0%    7.6c     False
   KXFED-27APR    True     4.5%    28.5% -21.0%    0.0%   23.4c     False
```

**Reading it.** The target range is 3.75-4.00%. For 9 December the market puts 79% on an upper bound of 4.25%, so it is pricing a 25bp hike at about 80%, a hold at 18%, and almost nothing on a cut. The expected upper bound of 4.196% is 20bp above today, i.e. about four fifths of a full hike. December passes every check (1.4 cent spreads, about 796k contracts traded, small tails). The later meetings fail on spread, so the January to April path is shown but not used: April in particular has 28.5% of its probability above the top strike, which means the ladder doesn't reach the outcomes the market is pricing.

The small negative buckets and the 2% at "2.75% or lower" are not views. Contracts that far from the money are quoted at a cent or two, and the differences between those mids are noise inside the bid-ask spread. The `excess` column checks exactly that (see below).

## Setup

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

FRED needs a free API key (fred.stlouisfed.org). Put it in `config.py` in the repo root:

```python
FRED_KEY = "your_key_here"
```

`config.py` is gitignored. Treasury and Kalshi data need no key. Each module runs on its own from the repo root, e.g. `python -m src.curve`.

## Modules

| File | What it does |
| --- | --- |
| `src/fred.py` | FRED wrapper, plus first-release values (the number as first published, before revisions) |
| `src/inflation.py` | CPI, core CPI, PCE, core PCE, PPI and shelter: YoY, MoM, 3m and 6m annualised |
| `src/curve.py` | Treasury par curve, daily moves split into level and slope, regime labels, 2s10s / 5s30s / 3m10y |
| `src/realrates.py` | 10y nominal split into real yield (TIPS) and breakeven, plus the 5y5y forward |
| `src/termpremium.py` | ACM term premium and the expected rate path it implies |
| `src/fedpath.py` | Fed funds futures (ZQ) price to post-meeting rate and move probability |
| `src/kalshi.py` | Kalshi market data client, handles pagination |
| `src/meetings.py` | Finds the open Kalshi Fed meetings and their FOMC decision dates, with a Wednesday check |
| `src/fedcurve.py` | Probability distribution per FOMC meeting from Kalshi strike ladders, hike / hold / cut odds against today's rate, and checks on whether to trust it |

## Where is inflation running?

`inflation.py` pulls the main gauges and works out the rates people quote. Core PCE is the Fed's target. Shelter is about a third of core CPI and lags market rents by roughly a year, so it is tracked on its own. PCE comes out about a month after CPI, so comparisons use the latest month both series have.

## What is the curve doing?

Each day's change in the 2y and 10y is split into a level move (the average of the two) and a slope move (10y minus 2y):

- bear flattening: yields up, front end leading, usually hikes being priced
- bear steepening: yields up, long end leading, usually term premium or supply
- bull steepening: yields down, front end leading, usually cuts being priced
- bull flattening: yields down, long end leading, usually growth worries

Days where both moves are under 3bp are labelled quiet, since the sign is mostly noise. Rerunning 2026 at 2bp, 3bp and 5bp thresholds, bear flattening was the most common regime every time, so the result doesn't depend on where the noise cut-off sits.

## What is the 10y made of?

Two ways of splitting it:

- nominal = real yield + breakeven. I calculate the breakeven myself (DGS10 minus DFII10) and check it against FRED's T10YIE. They agree to within 1bp, which is rounding.
- nominal = expected average short rate + term premium, using the ACM model. It's a model estimate, so I read it for direction more than level, and print the gap between the market 10y and the model's fitted 10y.

## What is the market pricing for the Fed?

**Futures (`fedpath.py`).** ZQ settles on the average effective fed funds rate over the month. If the meeting is mid-month, the price blends the rates before and after, weighted by days. From the price and the current EFFR, you can solve for the post-meeting rate and the probability of a 25bp move. Tested both ways: build a price from a known probability, feed it back in, get the same probability out.

Worked example, September 2026 (meeting on the 16th, EFFR 3.63%):

- 30 days in the month: 16 at the old rate, 14 at the new one
- Kalshi had an 86% chance of a 25bp hike, so the expected post-meeting rate is 3.63 + 0.25 x 0.86 = 3.845%
- expected monthly average = (16/30 x 3.63) + (14/30 x 3.845) = 3.7303%
- ZQ price = 100 - 3.7303 = 96.2697
- going the other way, a price of 96.2700 gives a post-meeting rate of 3.844% and a hike probability of 85.7%

So the two markets agreed to within 0.03bp on price.

**Kalshi (`fedcurve.py`).** Each meeting is a ladder of contracts paying out if the upper bound ends above a strike. These are cumulative, so differencing neighbouring strikes gives the probability of each outcome:

- the bucket between 3.75 and 4.00 means the rate ends at 4.00, the upper strike. Using the lower one understates every expected rate by 25bp.
- the bottom bucket (not above the lowest strike) is kept, at the lowest strike, so the outcomes add to 100%. An earlier version dropped it and understated the expected rate by about 6bp.
- hike, hold and cut odds are measured against today's upper bound from FRED (`DFEDTARU`).

Meetings and their dates come from Kalshi's open markets, not a typed-in list, so a meeting drops out once it settles.

## How much should you trust it?

Four checks per meeting, and a meeting is only used if it passes all of them:

- **contiguous:** strikes sit 25bp apart with no gaps.
- **tails:** at most 5% of the probability sits beyond the lowest or highest strike, since everything out there is lumped onto one rate.
- **excess negative:** a higher strike priced above a lower one gives a negative bucket. Each bucket is the difference of two mids, each only known to within its bid-ask spread, so negatives smaller than the spreads are noise. Only what's left over counts, and it must be under 2 points.
- **spread:** the average bid-ask is 5 cents or less.

On 5 November 2026, December passed every check. January (5.8c) and March (7.6c) failed narrowly on spread, which shows the 5 cent line is a judgement call. April failed clearly: 23.4c spreads and 28.5% of its probability above the top strike. In September, a 2027 contract's expected rate moved 5bp between two runs with no trades in between, which is why the spread rule exists.

## Limitations

- The futures engine assumes at most one rate change per settlement month.
- The 5 cent spread and 5% tail cut-offs are judgement calls from the contracts I looked at, not a model of fair value.
- The excess-negative check is weak exactly where spreads are wide, since wide spreads excuse large negatives. The spread rule is what catches those meetings.
- Probability beyond the end strikes is placed on a single rate (the lowest strike, or the top strike plus 25bp), which is approximate when the tails are large.
- `DFEDTARU` is published with a lag of a day or so, so "today" can be yesterday's rate around a meeting.
- Meeting dates come from each Kalshi market's own timestamps and are checked to fall on a Wednesday; any that don't are printed as a warning. An earlier hand-typed version had a November meeting that doesn't exist.
- Treasury par yields and ACM figures are fitted or modelled and published to 2 decimal places, so 1bp breaks in identity checks are rounding.
- Kalshi fees and settlement rounding are ignored.

## In progress

- Cross-checking the December Kalshi odds against ZQ futures in `fedpath.py`, as in the September example.
- Event studies: how yields move around CPI, PPI and payrolls surprises, using first-release values from `fred.py`.
- A rates volatility section.
