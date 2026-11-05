from src.fred import get_clean
from src.kalshi import get_markets, ladder_stats
from src.meetings import discover_meetings

STEP = 0.25            # the Fed moves in 25bp steps
MAX_SPREAD = 0.05      # avg bid-ask above 5c = the mid is arithmetic, not a price
MAX_TAIL = 0.05        # >5% sitting beyond the end strikes = ladder too short
MAX_NEG = 0.02         # >2pts of negative probability = ladder not monotone


def get_ladder(markets, ticker):
    # sorted by strike so the differencing below always runs low to high
    return sorted(ladder_stats(markets, ticker) or [], key=lambda r: r["strike"])


def discrete_probs(ladder):
    # the ladder is cumulative: P(above 3.75) includes everything higher.
    # differencing adjacent strikes gives each outcome its own probability.
    #
    # a bucket between strikes 3.75 and 4.00 means the rate is above 3.75 but
    # NOT above 4.00, so the rate ends at 4.00, the UPPER edge.
    #
    # the bottom bucket (NOT above the lowest strike) is included, at the
    # lowest strike, so the probabilities add to 100%. leaving it out
    # understates the expected rate.
    out = [{"rate": ladder[0]["strike"], "prob": 1.0 - ladder[0]["cum_prob"], "bottom": True}]
    for i, row in enumerate(ladder):
        next_cum = ladder[i + 1]["cum_prob"] if i + 1 < len(ladder) else 0.0
        upper = ladder[i + 1]["strike"] if i + 1 < len(ladder) else row["strike"] + STEP
        out.append({"rate": upper, "prob": row["cum_prob"] - next_cum, "bottom": False})
    return out


def expected_rate(ladder):
    # probability-weighted expected upper bound of the target range
    return sum(p["rate"] * p["prob"] for p in discrete_probs(ladder))


def policy_odds(ladder, current):
    # hike / hold / cut probabilities measured against TODAY's upper bound
    probs = discrete_probs(ladder)
    hike = sum(p["prob"] for p in probs if p["rate"] > current + 1e-9)
    cut = sum(p["prob"] for p in probs if p["rate"] < current - 1e-9)
    return {"hike": hike, "hold": 1.0 - hike - cut, "cut": cut}


def ladder_volume(ladder):
    # a thin ladder gives a real-looking expected rate built on quotes nobody traded
    return sum(row["volume"] for row in ladder)


def tails(ladder):
    # probability at or below the lowest strike, and above the highest.
    # both are lumped onto a single rate, so if either is large the ladder
    # doesn't cover the outcomes the market cares about
    return 1.0 - ladder[0]["cum_prob"], ladder[-1]["cum_prob"]


def negative_mass(ladder):
    # if a higher strike is priced above a lower one, differencing gives a
    # negative probability. small amounts are mid-price noise; large amounts
    # mean the ladder is internally inconsistent
    return sum(p["prob"] for p in discrete_probs(ladder) if p["prob"] < 0)


def excess_negative(ladder):
    # each bucket is the difference of two mid prices, and each mid is only
    # known to within its bid-ask spread. a negative bucket smaller than the
    # spreads of its two strikes is quote noise; count only what's left over
    total = 0.0
    for i, row in enumerate(ladder):
        nxt = ladder[i + 1] if i + 1 < len(ladder) else None
        prob = row["cum_prob"] - (nxt["cum_prob"] if nxt else 0.0)
        tolerance = (row["spread"] + (nxt["spread"] if nxt else 0.0)) / 2
        total += min(0.0, prob + tolerance)
    return total


def is_contiguous(ladder):
    # strikes should sit exactly 0.25 apart. a gap means a missing quote in
    # the middle of the ladder, which would make the differencing wrong
    strikes = [row["strike"] for row in ladder]
    return all(round(b - a, 2) <= STEP for a, b in zip(strikes, strikes[1:]))


def avg_spread(ladder):
    return sum(row["spread"] for row in ladder) / len(ladder) if ladder else None


def is_reliable(ladder):
    # only trust a meeting if it's quoted tightly, the strikes are complete,
    # the tails are small and the ladder is (nearly) monotone. the spread rule
    # came from watching a 2027 contract move 5bp between two runs with zero
    # trades in between
    below, above = tails(ladder)
    return (is_contiguous(ladder)
            and avg_spread(ladder) <= MAX_SPREAD
            and max(below, above) <= MAX_TAIL
            and excess_negative(ladder) >= -MAX_NEG)


def current_upper():
    # today's upper bound of the fed funds target range, from FRED.
    # get_clean returns {date: value}; take the latest date with a real value
    data = get_clean("DFEDTARU")
    if "observations" in data:
        data = {o["date"]: o["value"] for o in data["observations"]}
    points = []
    for d, v in data.items():
        try:
            points.append((str(d)[:10], float(v)))
        except (TypeError, ValueError):
            continue  # FRED marks missing days with "." or None
    as_of, value = max(points)
    return value, as_of


if __name__ == "__main__":
    meetings = discover_meetings()
    markets = get_markets("KXFED").get("markets", [])
    now, as_of = current_upper()

    print(f"\ncurrent target range upper bound: {now:.2f}% (FRED DFEDTARU, as of {as_of})")
    print(f"\n{'meeting':>14} {'date':>12} {'exp upper':>10} {'vs today':>9} "
          f"{'vs prev':>8} {'volume':>10}")
    print("-" * 70)

    prev = now
    for ticker, mtg_date in meetings:
        ladder = get_ladder(markets, ticker)
        if not ladder:
            print(f"{ticker:>14} {mtg_date:>12} {'no data':>10}")
            continue
        exp = expected_rate(ladder)
        flag = "" if is_reliable(ladder) else "  << unreliable"
        print(f"{ticker:>14} {mtg_date:>12} {exp:>9.3f}% {(exp - now) * 100:>+8.0f}bp "
              f"{(exp - prev) * 100:>+7.0f}bp {ladder_volume(ladder):>10,.0f}{flag}")
        prev = exp

    # ---- next meeting in detail ----
    ticker, mtg_date = meetings[0]
    ladder = get_ladder(markets, ticker)
    probs = discrete_probs(ladder)
    print(f"\n--- {ticker} ({mtg_date}) distribution ---")
    for p in probs:
        if abs(p["prob"]) >= 0.001:
            label = f"<={p['rate']:.2f}%" if p["bottom"] else f"{p['rate']:.2f}%"
            mark = "  <- today" if abs(p["rate"] - now) < 1e-9 else ""
            print(f"  upper bound {label:>7}: {p['prob'] * 100:>6.1f}%{mark}")
    print(f"  check: buckets sum to {sum(p['prob'] for p in probs) * 100:.1f}%, "
          f"expected upper {expected_rate(ladder):.3f}%")

    odds = policy_odds(ladder, now)
    call, p_call = max(odds.items(), key=lambda kv: kv[1])
    print(f"\n  vs today's {now:.2f}%: hike {odds['hike'] * 100:.0f}% | "
          f"hold {odds['hold'] * 100:.0f}% | cut {odds['cut'] * 100:.0f}%")
    print(f"  market read: {call} is the most likely outcome ({p_call * 100:.0f}%)"
          f"{'' if is_reliable(ladder) else ' - but this ladder fails the reliability checks'}")

    # ---- diagnostics ----
    print("\n--- diagnostics per meeting ---")
    print(f"{'meeting':>14} {'contig':>7} {'tail lo':>8} {'tail hi':>8} {'neg':>6} "
          f"{'excess':>7} {'spread':>7} {'reliable':>9}")
    for ticker, _ in meetings:
        ladder = get_ladder(markets, ticker)
        if not ladder:
            continue
        below, above = tails(ladder)
        print(f"{ticker:>14} {str(is_contiguous(ladder)):>7} {below * 100:>7.1f}% "
              f"{above * 100:>7.1f}% {negative_mass(ladder) * 100:>5.1f}% "
              f"{excess_negative(ladder) * 100:>6.1f}% {avg_spread(ladder) * 100:>6.1f}c {str(is_reliable(ladder)):>9}")