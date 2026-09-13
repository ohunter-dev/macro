from src.fred import get_fred_series

# ACM model, published by the NY Fed and mirrored on FRED.
#   THREEFYTP10 - estimated term premium on a 10y zero coupon bond
#   THREEFY10    - the model's fitted 10y yield
#   DGS10        - the actual market 10y, for comparison
# nominal = expected average short rate + term premium
# so: expected rate path = fitted yield - term premium
SERIES = {
    'term_premium_10y': 'THREEFYTP10',
    'fitted_10y':       'THREEFY10',
    'market_10y':       'DGS10',
}

def get_clean(series_id):
    obs = get_fred_series(series_id)['observations']
    return {o['date']: float(o['value']) for o in obs if o['value'] != '.'}

def build_table(n_days=6):
    data = {label: get_clean(sid) for label, sid in SERIES.items()}
    common = set.intersection(*[set(d.keys()) for d in data.values()])
    dates = sorted(common)[-n_days:]

    rows = []
    for date in dates:
        row = {'date': date}
        for label in SERIES:
            row[label] = data[label][date]
        # back out what the model says the market expects rates to average
        row['expected_path'] = row['fitted_10y'] - row['term_premium_10y']
        rows.append(row)
    return rows

if __name__ == "__main__":
    rows = build_table(6)

    print(f"{'date':>12} {'mkt 10y':>8} {'exp path':>9} {'term prem':>10}")
    print("-" * 42)
    for r in rows:
        print(f"{r['date']:>12} {r['market_10y']:>7.2f}% {r['expected_path']:>8.2f}% "
              f"{r['term_premium_10y']:>9.2f}%")

    print("\nday-over-day (bp), decomposing the MODEL's fitted yield:")
    for i in range(1, len(rows)):
        d_fit = (rows[i]['fitted_10y'] - rows[i-1]['fitted_10y']) * 100
        d_exp = (rows[i]['expected_path'] - rows[i-1]['expected_path']) * 100
        d_tp = (rows[i]['term_premium_10y'] - rows[i-1]['term_premium_10y']) * 100
        resid = (rows[i]['market_10y'] - rows[i]['fitted_10y']) * 100
        print(f"{rows[i]['date']:>12}  fitted {d_fit:+5.0f} = path {d_exp:+5.0f} "
              f"+ TP {d_tp:+5.0f}   (mkt-fit gap {resid:+5.0f}bp)")