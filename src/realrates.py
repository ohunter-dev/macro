from src.fred import get_fred_series

# DGS10   - nominal 10y
# DFII10  - 10y TIPS, i.e. the real yield
# T10YIE  - 10y breakeven (FRED calculates it, but we'll derive our own to check)
# DFII5   - 5y real
# T5YIE   - 5y breakeven
# T5YIFR  - 5y5y forward breakeven: expected inflation for the 5 years
#           STARTING 5 years from now. strips out near-term noise, so it's the
#           cleanest read on whether long-run expectations are anchored
SERIES = {
    'nominal_10y':   'DGS10',
    'real_10y':      'DFII10',
    'breakeven_10y': 'T10YIE',
    'real_5y':       'DFII5',
    'breakeven_5y':  'T5YIE',
    'fwd_5y5y':      'T5YIFR',
}

def get_clean(series_id):
    obs = get_fred_series(series_id)['observations']
    # same "." filter as the inflation module - FRED marks gaps this way
    return {o['date']: float(o['value']) for o in obs if o['value'] != '.'}

def build_table(n_days=5):
    data = {label: get_clean(sid) for label, sid in SERIES.items()}

    # only keep dates every series has, otherwise we compare across periods
    common = set.intersection(*[set(d.keys()) for d in data.values()])
    dates = sorted(common)[-n_days:]

    rows = []
    for date in dates:
        row = {'date': date}
        for label in SERIES:
            row[label] = data[label][date]
        # derive breakeven ourselves and check it against FRED's published one
        row['derived_be_10y'] = row['nominal_10y'] - row['real_10y']
        rows.append(row)
    return rows

if __name__ == "__main__":
    rows = build_table(5)

    print(f"{'date':>12} {'nom10y':>8} {'real10y':>8} {'BE10y':>7} {'derived':>8} {'5y5y':>7}")
    print("-" * 56)
    for r in rows:
        print(f"{r['date']:>12} {r['nominal_10y']:>7.2f}% {r['real_10y']:>7.2f}% "
              f"{r['breakeven_10y']:>6.2f}% {r['derived_be_10y']:>7.2f}% {r['fwd_5y5y']:>6.2f}%")

    print("\nday-over-day changes (bp):")
    for i in range(1, len(rows)):
        d_nom = (rows[i]['nominal_10y'] - rows[i-1]['nominal_10y']) * 100
        d_real = (rows[i]['real_10y'] - rows[i-1]['real_10y']) * 100
        d_be = (rows[i]['breakeven_10y'] - rows[i-1]['breakeven_10y']) * 100
        print(f"{rows[i]['date']:>12}  nominal {d_nom:+5.0f}  = real {d_real:+5.0f}  "
              f"+ breakeven {d_be:+5.0f}")