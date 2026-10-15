Main Macro Concept:

Building python tools for reading the US rates picture from public data: where inflation is running, how the Treasury curve is moving, how the 10y splits into real yield, breakeven and term premium, and what futures and Kalshi are pricing for each FOMC meeting. Where possible, each number is checked against a second source for validity. 

Output (Example case):

python -m src.fedcurve, run on [14/10/2026]:

kalshi event tickers available: ['KXFED-26DEC', 'KXFED-26OCT', 'KXFED-27APR', 'KXFED-27DEC', 'KXFED-27JAN', 'KXFED-27JUL', 'KXFED-27JUN', 'KXFED-27MAR', 'KXFED-27OCT', 'KXFED-27SEP', 'KXFED-28JAN']

Note: Move = move on previous meeting (rather than against today's rate)
       meeting         date   exp upper      move       volume
--------------------------------------------------------------
   KXFED-26OCT   2026-10-28      4.038%                339,205
   KXFED-26DEC   2026-12-09      4.215%     +18bp      399,665
   KXFED-27JAN   2027-01-30      4.822%     +61bp       59,140  << wide, unreliable
   KXFED-27MAR          TBC      4.496%     -33bp       55,812  << wide, unreliable
   KXFED-27APR   2027-04-28      4.718%     +22bp      166,355  << wide, unreliable

--- October distribution ---
  upper bound  4.00%:  79.0%
  upper bound  4.25%:  20.0%

--- diagnostics per meeting ---
       meeting  contiguous    mass  avg spread  reliable
   KXFED-26OCT        True   99.5%       1.0c      True
   KXFED-26DEC        True   99.0%       1.8c      True
   KXFED-27JAN        True   97.5%      23.4c     False
   KXFED-27MAR        True   96.0%      26.1c     False
   KXFED-27APR        True   93.0%      30.1c     False

Inference of the above tables - October reliable - The distribution shows 79% hold at 4.00 and 20% hike to 4.25. The spread is 1c and 99.5% of the probability is captured. December in a similar vein as the above, pricing in a rate hike by EOY. Jan-April unreliable (given 2x+ hikes and then a chance of a cut in March - urealistic). High volumes do not necessarily imply reliability here.

Setup required:
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

FRED needs a free API key (fred.stlouisfed.org). Put it in config.py in the repo root:

python
FRED_KEY = "your_key_here"

config.py is gitignored / Treasury and Kalshi data need no keys. Each module runs on its own from the repo root, e.g. python -m src.curve.


Modules: what each script contains/does: 

src/fred.py	FRED wrapper, plus first-release values (the number as first published, before revisions)
src/inflation.py	CPI, core CPI, PCE, core PCE, PPI and shelter: YoY, MoM, 3m and 6m annualised
src/curve.py	Treasury par curve, daily moves split into level and slope, regime labels, 2s10s / 5s30s / 3m10y
src/realrates.py	10y nominal split into real yield (TIPS) and breakeven, plus the 5y5y forward
src/termpremium.py	ACM term premium and the expected rate path it implies
src/fedpath.py	Fed funds futures (ZQ) price to post-meeting rate and move probability
src/kalshi.py	Kalshi market data client, handles pagination
src/fedcurve.py	Expected rate per FOMC meeting from Kalshi strike ladders, with checks on whether to trust it

Where is inflation running?

inflation.py pulls the main gauges and works out the rates people quote. Core PCE is the Fed's target - shelter is about a third of core CPI and lags market rents by roughly a year, so it is tracked on its own. PCE comes out about a month after CPI, so comparisons use the latest month both series have.

What is the curve doing?

Each day's change in the 2y and 10y is split into a level move (the average of the two) and a slope move (10y minus 2y):

bear flattening: yields up, front end leading, usually hikes being priced
bear steepening: yields up, long end leading, usually term premium or supply
bull steepening: yields down, front end leading, usually cuts being priced
bull flattening: yields down, long end leading, usually growth worries

Days where both moves are under 3bp are labelled quiet, since the sign is mostly noise. Rerunning 2026 at 2bp, 3bp and 5bp thresholds, bear flattening was the most common regime every time, so the result doesn't depend on where the noise cut-off sits.

What is the 10y made of?

Two ways of splitting it:

nominal = real yield + breakeven. I calculate the breakeven myself (DGS10 minus DFII10) and check it against FRED's T10YIE. They agree to within 1bp (rounding).

nominal = expected average short rate + term premium, using the ACM model. It's a model estimate, so I read it for direction more than level, and print the gap between the market 10y and the model's fitted 10y.

What is the market pricing for the Fed?

Futures (fedpath.py). ZQ settles on the average effective fed funds rate over the month. If the meeting is mid-month, the price blends the rates before and after, weighted by days. From the price and the current EFFR, I can solve for the post-meeting rate and the probability of a 25bp move. I tested it both ways: build a price from a known probability, feed it back in, get the same probability out.

Worked example: September 2026 (meeting on the 16th, EFFR 3.63%):

30 days in the month: 16 at the old rate, 14 at the new one
Kalshi had an 86% chance of a 25bp hike, so the expected post-meeting rate is 3.63 + (0.25 x 0.86) = 3.845%
expected monthly average = (16/30 x 3.63) + (14/30 x 3.845) = 3.7303%
ZQ price = 100 - 3.7303 = 96.2697
going the other way, a price of 96.2700 gives a post-meeting rate of 3.844% and a hike probability of 85.7%

So the two markets agreed to within 0.03bp on price.

Kalshi (fedcurve.py). Each meeting is a ladder of contracts paying out if the upper bound ends above a strike. These are cumulative, so differencing neighbouring strikes gives the probability of each outcome. Aka - the bucket between 3.75 and 4.00 means the rate ends at 4.00, the upper strike. Using the lower one understates every expected rate by 25bp.

How much should I trust it?

For each meeting: do the bucket probabilities add up to roughly 100%? Are the strikes evenly spaced with no gaps? Is the average bid-ask spread 5 cents or less?

In September 2026, October and December 2026 passed (1 to 1.5 cent spreads, full probability mass). January 2027 onwards failed (30 to 45 cent spreads, incomplete mass). The April 2027 expected rate moved 5bp between two runs with no trades in between. So the far meetings are flagged rather than actually used. 

Limitations
The futures engine assumes at most one rate change per settlement month.
The 5 cent spread cut-off is a judgement call from the contracts I looked at, not a model of fair spread.
Treasury par yields and ACM figures are fitted or modelled and published to 2 decimal places, so 1bp breaks in identity checks are rounding.
Kalshi meeting dates are typed in by hand and checked against each market's rules text. For example, I ran into an issue in an earlier version where I had a November meeting that doesn't exist.
Kalshi fees and settlement rounding are ignored.

In progress:
Event studies: how yields move around CPI, PPI and payrolls surprises, using first-release values from fred.py.
A rates volatility section.