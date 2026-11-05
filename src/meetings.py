"""Find the open Kalshi Fed meetings and their FOMC decision dates.

Replaces the hand-typed MEETINGS list in fedcurve.py.
"""
from datetime import datetime, timedelta

import requests

BASE = "https://api.elections.kalshi.com/trade-api/v2"
DATE_FIELDS = ("expected_expiration_time", "close_time")  # tried in this order


def _decision_date(market):
    """Market timestamp converted to a US Eastern calendar date (UTC-5 is close enough for the date)."""
    for field in DATE_FIELDS:
        ts = market.get(field)
        if ts:
            utc = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            return (utc - timedelta(hours=5)).date(), field
    return None, None


def discover_meetings(n=4):
    """Return the next n open meetings as [(event_ticker, 'YYYY-MM-DD'), ...], soonest first."""
    r = requests.get(f"{BASE}/events",
                     params={"series_ticker": "KXFED", "status": "open",
                             "with_nested_markets": "true", "limit": 200},
                     timeout=20)
    r.raise_for_status()

    meetings = []
    for ev in r.json().get("events", []):
        markets = ev.get("markets") or []
        if not markets:
            continue
        d, field = _decision_date(markets[0])
        if d is None:
            print(f"check {ev['event_ticker']}: no date field found")
            continue
        if d.weekday() != 2:  # FOMC decisions land on a Wednesday
            print(f"check {ev['event_ticker']}: {field} gives {d:%a %d %b %Y}, not a Wednesday")
        meetings.append((ev["event_ticker"], d.isoformat()))

    meetings.sort(key=lambda m: m[1])
    return meetings[:n]


if __name__ == "__main__":
    for ticker, d in discover_meetings(n=10):
        print(ticker, d)