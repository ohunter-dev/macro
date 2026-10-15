from src.kalshi import get_markets, ladder_stats

# each FOMC meeting gets its own kalshi event ticker.
# NOTE: post-hike world (16 Sept 2026 hike to 3.75-4.00%). September itself
# is settled and no longer appears in the open-markets list.
MEETINGS = [
    ("KXFED-26OCT", "2026-10-28"),
    ("KXFED-26DEC", "2026-12-09"),
    ("KXFED-27JAN", "2027-01-30"),
    ("KXFED-27MAR", None),
    ("KXFED-27APR", "2027-04-28"),   # confirmed from the market's own rules text
]


def discrete_probs(ladder):
    # the ladder is cumulative: P(above 3.75) includes everything higher.
    # differencing adjacent strikes gives each bucket its own probability.
    #
    # IMPORTANT: a bucket sitting between strikes 3.75 and 4.00 means the rate
    # is above 3.75 but NOT above 4.00 - so the actual rate is 4.00, the UPPER
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


def probability_mass(ladder):
    # how much of the distribution the ladder actually captures. anything
    # missing sits BELOW the lowest strike, where there's no contract to
    # price it - a large gap means the expected rate is unreliable
    return sum(row["cum_prob"] - (ladder[i + 1]["cum_prob"] if i + 1 < len(ladder) else 0.0)
               for i, row in enumerate(ladder))


def is_contiguous(ladder):
    # strikes should sit exactly 0.25 apart. a gap means a missing quote in
    # the middle of the ladder, which would make the differencing wrong
    strikes = [row["strike"] for row in ladder]
    gaps = [round(strikes[i + 1] - strikes[i], 2) for i in range(len(strikes) - 1)]
    return all(g <= 0.25 for g in gaps)


def avg_spread(ladder):
    return sum(row["spread"] for row in ladder) / len(ladder) if ladder else None


def is_reliable(ladder, max_avg_spread=0.05):
    # only trust a meeting's expected rate if it's quoted tightly. proved the
    # need for this by watching a 2027 contract move 5bp between two runs
    # with zero trades in between - the mid was arithmetic, not a price
    spread = avg_spread(ladder)
    return spread is not None and spread <= max_avg_spread


def meeting_date_from_rules(markets, event_ticker):
    # the exchange's own settlement rules name the meeting date - more
    # reliable than a hardcoded calendar (an earlier version of this had
    # a november meeting that doesn't exist and was missing october)
    for m in markets:
        if m.get("event_ticker") == event_ticker:
            return m.get("rules_primary", "")
    return ""


if __name__ == "__main__":
    data = get_markets("KXFED")
    markets = data.get("markets", [])

    tickers = sorted({m.get("event_ticker") for m in markets})
    print("kalshi event tickers available:", tickers)

    print(f"\n{'meeting':>14} {'date':>12} {'exp upper':>11} {'move':>9} {'volume':>12}")
    print("-" * 62)

    prev = None
    for ticker, mtg_date in MEETINGS:
        date_str = mtg_date if mtg_date else "TBC"
        ladder = ladder_stats(markets, ticker)

        if not ladder:
            print(f"{ticker:>14} {date_str:>12} {'no data':>11}")
            continue

        exp = expected_rate(ladder)
        vol = ladder_volume(ladder)
        move = f"{(exp - prev) * 100:+.0f}bp" if prev is not None else ""
        flag = "" if is_reliable(ladder) else "  << wide, unreliable"
        print(f"{ticker:>14} {date_str:>12} {exp:>10.3f}% {move:>9} {vol:>12,.0f}{flag}")
        prev = exp

    print("\n--- October distribution ---")
    oct_ladder = ladder_stats(markets, "KXFED-26OCT")
    for p in discrete_probs(oct_ladder):
        if p["prob"] > 0.005:
            print(f"  upper bound {p['rate']:>5.2f}%: {p['prob'] * 100:>5.1f}%")

    print("\n--- diagnostics per meeting ---")
    print(f"{'meeting':>14} {'contiguous':>11} {'mass':>7} {'avg spread':>11} {'reliable':>9}")
    for ticker, _ in MEETINGS:
        ladder = ladder_stats(markets, ticker)
        if not ladder:
            continue
        mass = probability_mass(ladder) * 100
        spread = avg_spread(ladder) * 100
        print(f"{ticker:>14} {str(is_contiguous(ladder)):>11} {mass:>6.1f}% "
              f"{spread:>9.1f}c {str(is_reliable(ladder)):>9}")