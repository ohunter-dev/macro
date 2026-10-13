import requests
import io
import pandas as pd

def get_treasury_curve(year=2026):
    # treasury publishes the daily par yield curve as a csv, no key needed.
    # this is same-day, unlike FRED's mirror which lags by a day
    url = ("https://home.treasury.gov/resource-center/data-chart-center/"
           "interest-rates/daily-treasury-rates.csv/{}/all".format(year))
    params = {"type": "daily_treasury_yield_curve", "field_tdr_date_value": year, "_format": "csv"}

    r = requests.get(url, params=params, headers={"User-Agent": "Mozilla/5.0"})
    # pandas can read a csv straight from a string if we wrap it in StringIO
    df = pd.read_csv(io.StringIO(r.text))
    df['Date'] = pd.to_datetime(df['Date'])
    # treasury returns newest first - flip so it reads chronologically
    return df.sort_values('Date').reset_index(drop=True)

TENORS = ['1 Mo', '3 Mo', '6 Mo', '1 Yr', '2 Yr', '3 Yr', '5 Yr', '7 Yr', '10 Yr', '20 Yr', '30 Yr']

def daily_change(df, tenors=TENORS):
    # bp move per tenor, day over day. multiply by 100 because the csv is in percent
    changes = df[tenors].diff() * 100
    changes['Date'] = df['Date']
    return changes

def classify_regime(row, short='2 Yr', long='10 Yr', threshold_bp=3):
    # threshold stops us dignifying 1bp of noise with a regime label.
    # on quiet days the sign of the move is basically random
    d_short, d_long = row[short], row[long]
    if pd.isna(d_short) or pd.isna(d_long):
        return "n/a"

    level_move = (d_short + d_long) / 2      # average move = level shift
    slope_move = d_long - d_short            # +ve means long end leading

    if abs(level_move) < threshold_bp and abs(slope_move) < threshold_bp:
        return "quiet"

    rising = level_move > 0
    steepening = slope_move > 0

    if rising and not steepening:
        label = "bear flattening (pricing hikes)"
    elif rising and steepening:
        label = "bear steepening (term premium / supply)"
    elif not rising and steepening:
        label = "bull steepening (pricing cuts)"
    else:
        label = "bull flattening (growth fear)"

    # tag how much of the move was level vs slope - a big level shift with a
    # tiny slope change is a different animal from a genuine curve reshaping
    return f"{label}  [level {level_move:+.0f}bp, slope {slope_move:+.0f}bp]"

def spreads(df):
    out = pd.DataFrame({'Date': df['Date']})
    out['2s10s'] = (df['10 Yr'] - df['2 Yr']) * 100
    out['5s30s'] = (df['30 Yr'] - df['5 Yr']) * 100
    out['3m10y'] = (df['10 Yr'] - df['3 Mo']) * 100
    return out

def regime_history(df, threshold_bp=3):
    # threshold passed through so we can test how sensitive the whole
    # distribution is to where we draw the "this is just noise" line
    chg = daily_change(df)
    out = []
    for i in range(1, len(df)):
        label = classify_regime(chg.loc[i], threshold_bp=threshold_bp)
        bare = label.split('  [')[0]
        out.append({'date': df.loc[i, 'Date'].date(), 'regime': bare})
    return out

def regime_summary(history):
    counts = {}
    for h in history:
        counts[h['regime']] = counts.get(h['regime'], 0) + 1
    return counts

def current_run(history):
    # how many consecutive sessions in the current regime.
    # regimes persist because the narrative behind them changes slowly,
    # so an unusually long run is worth noticing
    latest = history[-1]['regime']
    run = 0
    for h in reversed(history):
        if h['regime'] == latest:
            run += 1
        else:
            break
    return latest, run

if __name__ == "__main__":
    df = get_treasury_curve(2026)
    chg = daily_change(df)
    spr = spreads(df)

    print("last 5 sessions:\n")
    for i in range(len(df) - 5, len(df)):
        date = df.loc[i, 'Date'].date()
        regime = classify_regime(chg.loc[i])
        print(f"{date}  2y={df.loc[i,'2 Yr']:.2f}% ({chg.loc[i,'2 Yr']:+.0f}bp)  "
              f"10y={df.loc[i,'10 Yr']:.2f}% ({chg.loc[i,'10 Yr']:+.0f}bp)  "
              f"2s10s={spr.loc[i,'2s10s']:.0f}bp   {regime}")

    print("\n--- regime frequency, 2026 YTD, at different thresholds ---")
    for thresh in [2, 3, 5]:
        hist = regime_history(df, threshold_bp=thresh)
        total = len(hist)
        print(f"\nthreshold = {thresh}bp:")
        for regime, count in sorted(regime_summary(hist).items(), key=lambda x: -x[1]):
            print(f"  {regime:>42}: {count:>3} days ({count/total*100:>4.1f}%)")

    # current run at the default threshold
    hist = regime_history(df, threshold_bp=3)
    latest, run = current_run(hist)
    print(f"\ncurrent (3bp): {latest}, running {run} sessions")
        