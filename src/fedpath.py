from datetime import date
from calendar import monthrange
from src.fred import get_fred_series

# 2026 FOMC decision dates. rate changes take effect the day AFTER the
# announcement, since they announce at 2pm ET
FOMC_DATES_2026 = [
    date(2026, 1, 28), date(2026, 3, 18), date(2026, 4, 29),
    date(2026, 6, 17), date(2026, 7, 29), date(2026, 9, 16),
    date(2026, 10, 28), date(2026, 12, 9),
]

def implied_rate(price):
    # ZQ quotes as 100 minus the rate, so a price of 96.25 means 3.75%
    return 100 - price

def split_month(year, month, fomc_dates=FOMC_DATES_2026):
    # work out how the month divides around a meeting, if there is one.
    # returns (days_at_old_rate, days_at_new_rate, total_days)
    total_days = monthrange(year, month)[1]

    meeting = next((d for d in fomc_dates
                    if d.year == year and d.month == month), None)
    if meeting is None:
        return total_days, 0, total_days

    # new rate effective the day after the announcement
    days_old = meeting.day
    days_new = total_days - days_old
    return days_old, days_new, total_days

def solve_post_meeting_rate(price, year, month, current_rate):
    # the contract settles on the month's AVERAGE rate. we know the average
    # (from the price) and the rate before the meeting, so solve for after
    avg = implied_rate(price)
    d_old, d_new, total = split_month(year, month)

    if d_new == 0:
        return None  # no meeting this month, nothing to solve for

    # avg = (d_old/total)*current + (d_new/total)*new
    post_rate = (avg * total - d_old * current_rate) / d_new
    return post_rate

def hike_probability(post_rate, current_rate, move_size=0.25):
    # the fed moves in 25bp steps or not at all - it can't hike by 17bp.
    # so a solved rate sitting between "no change" and "full hike" is really
    # a probability-weighted blend of those two outcomes. how far along that
    # line it sits IS the implied probability
    hiked_rate = current_rate + move_size
    return (post_rate - current_rate) / (hiked_rate - current_rate)

def fed_path_from_price(price, year, month, current_rate, move_size=0.25):
    post = solve_post_meeting_rate(price, year, month, current_rate)
    if post is None:
        return None
    return {
        'implied_avg': implied_rate(price),
        'post_meeting_rate': post,
        'implied_move_bp': (post - current_rate) * 100,
        'prob_of_move': hike_probability(post, current_rate, move_size),
    }

def get_current_effr():
    # EFFR trades a few bp below the target midpoint, so using the actual
    # published rate is more honest than assuming the midpoint
    obs = get_fred_series("EFFR")['observations']
    clean = [o for o in obs if o['value'] != '.']
    return float(clean[-1]['value']), clean[-1]['date']

if __name__ == "__main__":
    # gotta check the maths both ways using today's EFFR
    current, effr_date = get_current_effr()
    print(f"using EFFR {current}% as of {effr_date}\n")

    # if the market fully priced a 25bp hike on 16 Sept, what would the
    # september contract print? work it forward to check the maths
    d_old, d_new, total = split_month(2026, 9)
    print(f"September 2026: {d_old} days at old rate, {d_new} at new, {total} total")

    hiked = current + 0.25
    expected_avg = (d_old/total)*current + (d_new/total)*hiked
    expected_price = 100 - expected_avg
    print(f"if fully pricing a 25bp hike: avg={expected_avg:.4f}%, price={expected_price:.4f}")

    # now run it backwards - feed that price in and see if we recover the hike
    recovered = solve_post_meeting_rate(expected_price, 2026, 9, current)
    print(f"solved post-meeting rate: {recovered:.4f}% (should be {hiked:.4f}%)")

    print("\n--- implied probabilities across a range of prices ---")
    print(f"{'price':>9} {'implied avg':>12} {'post-mtg':>10} {'move bp':>9} {'P(hike)':>9}")
    for px in [96.3700, 96.3200, 96.2900, 96.2700, 96.2533]:
        r = fed_path_from_price(px, 2026, 9, current)
        print(f"{px:>9.4f} {r['implied_avg']:>11.4f}% {r['post_meeting_rate']:>9.3f}% "
              f"{r['implied_move_bp']:>8.1f} {r['prob_of_move']*100:>8.1f}%")


    # kalshi showed 86% when I ran this in sept 2026. what should the september ZQ contract print
    # if the futures market agrees? this is the cross-check - two completely
    # different markets, same underlying event
    print("\n--- implied ZQ price from Kalshi's 86% ---")
    kalshi_prob = 0.86
    implied_post = current + 0.25 * kalshi_prob
    d_old, d_new, total = split_month(2026, 9)
    implied_avg = (d_old/total)*current + (d_new/total)*implied_post
    implied_px = 100 - implied_avg
    print(f"P(hike)={kalshi_prob:.0%} -> post-meeting {implied_post:.4f}% "
          f"-> avg {implied_avg:.4f}% -> ZQ {implied_px:.4f}")