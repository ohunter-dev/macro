from src.kalshi import get_markets

# each FOMC meeting gets its own kalshi event ticker.
# NOTE: dates left as None where I haven't verified them against
# federalreserve.gov yet. do NOT trust a hardcoded fed calendar - the one
# I first wrote had a november meeting that doesn't exist and no october.
MEETINGS = [
    ("KXFED-26OCT", "2026-10-28"),
    ("KXFED-26DEC", None),
    ("KXFED-27JAN", None),
    ("KXFED-27MAR", None),
    ("KXFED-27APR", "2027-04-28"),
]


def strike_ladder(markets, event_ticker):
    # one meeting's strikes, low to high, with mid prices.
    # each row is P(rate ABOVE this strike) - cumulative, not discrete
    out = []
    for m in markets:
        if m.get("event_ticker") != event_ticker:
            continue
        bid = float(m.get("yes_bid_dollars") or 0)
        ask = float(m.get("yes_ask_dollars") or 0)
        if bid == 0 and ask == 0:
            continue                      # no quote at all, skip it
        out.append({
            "strike": float(m["floor_strike"]),
            "cum_prob": (bid + ask) / 2,
            "volume": float(m.get("volume_fp") or 0),
        })
    return sorted(out, key=lambda x: x["strike"])


def discrete_probs(ladder):
    # the ladder is cumulative: P(above 3.75) includes everything higher.
    # differencing adjacent strikes gives each bucket its own probability.
    #
    # IMPORTANT: a bucket sitting between strikes 3.50 and 3.75 means the rate
    # is above 3.50 but NOT above 3.75 - so the actual rate is 3.75, the UPPER
    # edge. using the lower edge understates every expected rate by 25bp.
    out = []
    for i, row in enumerate(ladder):
        next_cum = ladder[i + 1]["cum_prob"] if i + 1 < len(ladder) else 0.0
        upper = ladder[i + 1]["strike"] if i + 1 < len(ladder) else row["strike"] + 0.25
        out.append({
            "rate": upper,
            "prob": row["cum_prob"] - next_cum,
            "volume": row["volume"],
        })
    return out


def expected_rate(ladder):
    # probability-weighted expected upper bound of the target range
    return sum(p["rate"] * p["prob"] for p in discrete_probs(ladder))


def ladder_volume(ladder):
    # total traded volume across the meeting's strikes. a thin ladder gives
    # a real-looking expected rate built on quotes nobody traded
    return sum(row["volume"] for row in ladder)


def rules_text(markets, event_ticker):
    # the exchange's own settlement rules name the meeting date. more
    # reliable than a calendar typed from memory
    for m in markets:
        if m.get("event_ticker") == event_ticker:
            return m.get("rules_primary", "")
    return ""

def is_reliable(markets, event_ticker, max_avg_spread=0.05):
    # only trust a meeting's expected rate if the ladder is actually quoted
    # tightly. at 20c+ spreads the mid is arithmetic, not a price - proved
    # this by watching apr 2027 move 5bp between runs with zero trades
    rows = [m for m in markets if m.get("event_ticker") == event_ticker]
    spreads = []
    for m in rows:
        bid = float(m.get("yes_bid_dollars") or 0)
        ask = float(m.get("yes_ask_dollars") or 0)
        if bid == 0 and ask == 0:
            continue
        spreads.append(ask - bid)
    if not spreads:
        return False
    return (sum(spreads) / len(spreads)) <= max_avg_spread


if __name__ == "__main__":
    data = get_markets("KXFED")
    markets = data.get("markets", [])

    # sanity check: which meetings does kalshi actually list?
    tickers = sorted({m.get("event_ticker") for m in markets})
    print("kalshi event tickers available:", tickers)

    print(f"\n{'meeting':>14} {'date':>12} {'exp upper':>11} {'move':>9} {'volume':>12}")
    print("-" * 62)

    prev = None
    for ticker, mtg_date in MEETINGS:
        date_str = mtg_date if mtg_date else "TBC"
        ladder = strike_ladder(markets, ticker)

        if not ladder:
            print(f"{ticker:>14} {date_str:>12} {'no data':>11}")
            continue

        exp = expected_rate(ladder)
        vol = ladder_volume(ladder)
        move = f"{(exp - prev) * 100:+.0f}bp" if prev is not None else ""
        flag = "" if is_reliable(markets, ticker) else "  << wide, unreliable"
        print(f"{ticker:>14} {date_str:>12} {exp:>10.3f}% {move:>9} {vol:>12,.0f}{flag}")
        prev = exp

    print("\n--- October distribution ---")
    oct_ladder = strike_ladder(markets, "KXFED-26OCT")
    for p in discrete_probs(oct_ladder):
        if p["prob"] > 0.005:
            print(f"  upper bound {p['rate']:>5.2f}%: {p['prob'] * 100:>5.1f}%")

    print("\n--- meeting date, from kalshi's own rules text ---")
    print(rules_text(markets, "KXFED-26OCT")[:200])

    print("\n--- ladder completeness check ---")
    for ticker, _ in MEETINGS:
        ladder = strike_ladder(markets, ticker)
        if not ladder:
            continue
        strikes = [r["strike"] for r in ladder]
        gaps = [round(strikes[i+1] - strikes[i], 2) for i in range(len(strikes)-1)]
        has_holes = any(g > 0.25 for g in gaps)
        print(f"{ticker:>14}: {len(strikes)} strikes, "
              f"{'HOLES - expected rate unreliable' if has_holes else 'contiguous'}")


    print("\n--- probability mass check ---")
    for ticker, _ in MEETINGS:
        ladder = strike_ladder(markets, ticker)
        if not ladder:
            continue
        total = sum(p["prob"] for p in discrete_probs(ladder))
        # anything missing is mass sitting BELOW the lowest strike that the
        # ladder can't see. if this is big, the expected rate is biased high
        print(f"{ticker:>14}: probs sum to {total*100:>6.2f}%  "
              f"(missing {(1-total)*100:>5.2f}% below lowest strike)")


    print("\n--- spread width check ---")
    for ticker, _ in MEETINGS:
        rows = [m for m in markets if m.get("event_ticker") == ticker]
        spreads = []
        for m in rows:
            bid = float(m.get("yes_bid_dollars") or 0)
            ask = float(m.get("yes_ask_dollars") or 0)
            if bid == 0 and ask == 0:
                continue
            spreads.append(ask - bid)
        if spreads:
            avg = sum(spreads) / len(spreads)
            worst = max(spreads)
            print(f"{ticker:>14}: avg spread {avg*100:>5.1f}c, widest {worst*100:>5.1f}c")