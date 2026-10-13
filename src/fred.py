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

def get_vintages(series_id, observation_start=None, observation_end=None):
    # pulls every historical revision of a series, not just today's current
    # numbers. output_type=2 gives one row per reference period with a
    # column per vintage date - this is how we get the value AS IT WAS
    # FIRST PUBLISHED, before later revisions changed it
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": FRED_KEY,
        "file_type": "json",
        "realtime_start": "1776-07-04",   # FRED's own "give me everything" date
        "realtime_end": "9999-12-31",
        "output_type": 2,
    }
    if observation_start:
        params["observation_start"] = observation_start
    if observation_end:
        params["observation_end"] = observation_end
    r = requests.get(url, params=params)
    return r.json()["observations"]

def first_release(series_id, observation_start=None, observation_end=None):
    # each row has columns "<series_id>_YYYYMMDD", one per vintage. the
    # LEFTMOST column that isn't "." is the earliest vintage - the value as
    # originally reported, and the date in its column name is the actual
    # release date (not the reference month the number describes).
    #
    # a row where every column is "." means that period was never
    # published at all - e.g. Sept 2025 CPI, skipped in the shutdown.
    # skip it rather than invent a value.
    rows = get_vintages(series_id, observation_start, observation_end)
    prefix = series_id + "_"
    out = []
    for row in rows:
        vintage_cols = sorted(k for k in row if k.startswith(prefix))
        for col in vintage_cols:
            if row[col] != ".":
                d = col[len(prefix):]
                out.append({
                    "period": row["date"],
                    "release_date": f"{d[:4]}-{d[4:6]}-{d[6:]}",
                    "value": float(row[col]),
                })
                break
    return out