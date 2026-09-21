# in src/fred.py, at the top

# DATA PRECISION NOTE
# FRED and Treasury publish yields to 2dp (0.01% = 1bp) and index levels to 3dp.
# That is the source precision - we are not truncating anything.
# Consequences to be aware of:
#   - differencing two 2dp values can produce +/-1bp of rounding noise
#   - identities (nominal = real + breakeven) may break by 1bp for this reason
#   - a 5bp+ break means something real, a 1bp break is rounding
# Treasury's par curve is itself a FITTED curve, not traded prices. ACM term
# premium is a model estimate - read changes, treat levels with caution.
# A real desk works off Bloomberg/Refinitiv tick data or raw CUSIP pricing.

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

def get_clean(series_id):
    # same "." filter every FRED-consuming module needs - FRED marks
    # missing observations this way, and float() chokes on it otherwise
    obs = get_fred_series(series_id)['observations']
    return {o['date']: float(o['value']) for o in obs if o['value'] != '.'}