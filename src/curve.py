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
        