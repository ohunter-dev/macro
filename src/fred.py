import requests
from config import FRED_KEY

def get_fred_series(series_id):
    # thin wrapper round the FRED observations endpoint.
    # returns the raw json - parsing happens elsewhere so this stays reusable
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": FRED_KEY,
        "file_type": "json",
    }
    r = requests.get(url, params=params)
    return r.json()