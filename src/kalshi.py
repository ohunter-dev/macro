import requests

BASE = "https://api.elections.kalshi.com/trade-api/v2"
# despite the "elections" subdomain this serves ALL kalshi markets - economics
# included. no auth needed for read-only market data

def get_markets(series_ticker, status="open", limit=200):
    # kalshi pages results - a full page plus a cursor means there's more.
    # keep asking until the cursor comes back empty, otherwise you silently
    # get a slice and think markets have disappeared
    all_markets = []
    cursor = None

    while True:
        params = {"series_ticker": series_ticker, "status": status, "limit": limit}
        if cursor:
            params["cursor"] = cursor

        r = requests.get(f"{BASE}/markets", params=params)
        r.raise_for_status()
        data = r.json()

        page = data.get("markets", [])
        all_markets.extend(page)

        cursor = data.get("cursor")
        if not cursor or not page:
            break

    return {"markets": all_markets}

def find_meeting_markets(series_ticker, event_ticker):
    # kalshi lists a LADDER of strikes per meeting ("will the upper bound be
    # above X%"), not a single hike/hold contract. so we filter to one meeting
    # and get the whole distribution
    data = get_markets(series_ticker)
    markets = [m for m in data.get("markets", [])
               if m.get("event_ticker") == event_ticker]
    return sorted(markets, key=lambda m: m.get("floor_strike", 0))

if __name__ == "__main__":
    data = get_markets("KXFED")
    markets = data.get("markets", [])
    print(f"total markets across all pages: {len(markets)}")
    tickers = sorted({m.get("event_ticker") for m in markets})
    print("event tickers:", tickers)

   