from src.fred import get_fred_series

def to_series(observations):
    # FRED hands back everything as strings, and uses "." for missing values.
    # strip the gaps out and convert to floats before doing any maths
    return [(o['date'], float(o['value'])) for o in observations if o['value'] != '.']

def compute_rates(series):
    # series is a list of (date, index_level) oldest-first.
    # start at i=12 because you can't do a year-on-year without a year of history
    results = []
    for i in range(12, len(series)):
        date, value = series[i]

        yoy = (value / series[i-12][1] - 1) * 100
        mom = (value / series[i-1][1] - 1) * 100

        # annualising: compound the period rate up to a full year.
        # 3m reacts faster than YoY but is noisier - use it to spot turns early
        ann_3m = ((value / series[i-3][1]) ** (12/3) - 1) * 100
        ann_6m = ((value / series[i-6][1]) ** (12/6) - 1) * 100

        results.append({'date': date, 'index': value, 'yoy': yoy,
                        'mom': mom, 'ann_3m': ann_3m, 'ann_6m': ann_6m})
    return results

def get_inflation(series_id):
    # one call: fetch, clean, compute
    obs = get_fred_series(series_id)['observations']
    return compute_rates(to_series(obs))

# the gauges that matter, and why:
#   CPIAUCSL  - headline CPI, what the news quotes
#   CPILFESL  - core CPI, strips food+energy
#   PCEPI     - headline PCE
#   PCEPILFE  - CORE PCE: this is the one the Fed actually targets
#   PPIFIS    - producer prices, the upstream input (this is what moved 10 Sept)
#   CUSR0000SAH1 - shelter, ~35% of core, lags market rents by ~12m
SERIES = {
    'CPI headline':  'CPIAUCSL',
    'CPI core':      'CPILFESL',
    'PCE headline':  'PCEPI',
    'PCE core':      'PCEPILFE',
    'PPI':           'PPIFIS',
    'Shelter':       'CUSR0000SAH1',
}

def latest_common_date(series_a, series_b):
    # PCE lags CPI by about a month, so grabbing each series' own latest
    # compares different periods. find the most recent month BOTH have.
    dates_a = {r['date'] for r in series_a}
    dates_b = {r['date'] for r in series_b}
    return max(dates_a & dates_b)

if __name__ == "__main__":
    print(f"{'gauge':>14} {'date':>12} {'YoY':>7} {'MoM':>7} {'3m ann':>8} {'6m ann':>8}")
    print("-" * 60)

    for label, series_id in SERIES.items():
        rates = get_inflation(series_id)
        latest = rates[-1]
        print(f"{label:>14} {latest['date']:>12} {latest['yoy']:>6.2f}% "
              f"{latest['mom']:>6.2f}% {latest['ann_3m']:>7.2f}% {latest['ann_6m']:>7.2f}%")