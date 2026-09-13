import requests
from secrets import FRED_KEY

def get_fred_series(series_id):
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": FRED_KEY,
        "file_type": "json",
    }
    r = requests.get(url, params=params)
    return r.json()

def compute_inflation_rates(observations):
    # FRED marks missing/not-yet-published values as "." — skip those
    series = [(o['date'], float(o['value'])) for o in observations if o['value'] != '.']

    results = []
    for i in range(12, len(series)):
        date, value = series[i]
        value_1yr_ago = series[i - 12][1]
        value_1mo_ago = series[i - 1][1]

        yoy = (value / value_1yr_ago - 1) * 100
        mom = (value / value_1mo_ago - 1) * 100

        results.append({'date': date, 'index': value, 'yoy_pct': yoy, 'mom_pct': mom})

    return results

if __name__ == "__main__":
    data = get_fred_series("CPIAUCSL")
    obs = data["observations"]
    rates = compute_inflation_rates(obs)

    bad = [o for o in obs if o['value'] == '.']
    print("Observations with missing value:", bad)

    print("\n--- Headline CPI ---")
    print("Last 6 months:") 
    for row in rates[-6:]:
        print(f"  {row['date']}  index={row['index']:>8.2f}  "
              f"YoY={row['yoy_pct']:>5.2f}%  MoM={row['mom_pct']:>5.2f}%")

    print("\n--- Shelter CPI ---")
    shelter_data = get_fred_series("CUSR0000SAH1")
    shelter_obs = shelter_data["observations"]
    shelter_rates = compute_inflation_rates(shelter_obs)
    print("Last 3 months:")
    for row in shelter_rates[-3:]:
        print(f"  {row['date']}  index={row['index']:>8.2f}  "
              f"YoY={row['yoy_pct']:>5.2f}%  MoM={row['mom_pct']:>5.2f}%")

    print("\n--- Core CPI (ex food & energy) ---")
    core_data = get_fred_series("CPILFESL")
    core_obs = core_data["observations"]
    core_rates = compute_inflation_rates(core_obs)
    print("Last 3 months:")
    for row in core_rates[-3:]:
        print(f"  {row['date']}  index={row['index']:>8.2f}  "
              f"YoY={row['yoy_pct']:>5.2f}%  MoM={row['mom_pct']:>5.2f}%")
