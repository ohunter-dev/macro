import requests

BASE = "https://api.elections.kalshi.com/trade-api/v2"
# despite the "elections" subdomain this serves ALL kalshi markets - economics
# included. no auth needed for read-only market data

def get_markets(series_ticker, status="open", limit=200):
    r = requests.get(f"{BASE}/markets",
                     params={"series_ticker": series_ticker,
                             "status": status,
                             "limit": limit})
    r.raise_for_status()
    return r.json()

def find_meeting_markets(series_ticker, event_ticker):
    # kalshi lists a LADDER of strikes per meeting ("will the upper bound be
    # above X%"), not a single hike/hold contract. so we filter to one meeting
    # and get the whole distribution
    data = get_markets(series_ticker)
    markets = [m for m in data.get("markets", [])
               if m.get("event_ticker") == event_ticker]
    return sorted(markets, key=lambda m: m.get("floor_strike", 0))

if __name__ == "__main__":
    # september 2026 meeting. current target range is 3.50-3.75, so the
    # UPPER BOUND is 3.75. "above 3.75%" resolving yes == they hiked
    mkts = find_meeting_markets("KXFED", "KXFED-26SEP")
    print(f"found {len(mkts)} strikes for the Sept meeting\n")

    print(f"{'strike':>8} {'yes_bid':>9} {'yes_ask':>9} {'mid':>8} {'volume':>10}")
    for m in mkts:
        bid = m.get('yes_bid_dollars') or 0
        ask = m.get('yes_ask_dollars') or 0
        mid = (float(bid) + float(ask)) / 2
        print(f"{m.get('floor_strike'):>8} {bid:>9} {ask:>9} {mid:>8.2f} "
              f"{m.get('volume_fp'):>10}")