"""Plan whole-sale weekday allocations; never read or write application databases."""

import argparse
import json
from collections import Counter
from datetime import UTC, date, datetime, time, timedelta
from fractions import Fraction
from pathlib import Path
from zoneinfo import ZoneInfo


def aware_timestamp(value):
    result = datetime.fromisoformat(value)
    if result.tzinfo is None:
        raise ValueError("timestamps must include a timezone")
    return result


def plan_allocation(payload, *, now=None):
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        raise ValueError("current time must include a timezone")
    timezone = ZoneInfo(payload["timezone"])
    previous = date.fromisoformat(payload["previous_reported_date"])
    observed = aware_timestamp(payload["observed_at"])
    end = observed.astimezone(timezone).date()
    start = previous + timedelta(days=1)
    if observed > now or end < start:
        raise ValueError("report must follow the previous reporting date and not be in the future")

    exposure, totals = Counter(), Counter()
    for key, count in payload["training_daily_counts"].items():
        day = date.fromisoformat(key)
        if day > previous or type(count) is not int or count < 0:
            raise ValueError("training requires earlier verified nonnegative whole daily counts")
        exposure[day.weekday()] += 1
        totals[day.weekday()] += count
    if set(exposure) != set(range(7)):
        raise ValueError("verified observation exposure is required for all seven weekdays")
    means = {weekday: Fraction(totals[weekday], exposure[weekday]) for weekday in range(7)}
    days = [start + timedelta(days=offset) for offset in range((end - start).days + 1)]
    denominator = sum(means[day.weekday()] for day in days)
    if denominator == 0:
        raise ValueError("no observed weekday sales support this interval")

    sales = payload["sales"]
    identifiers = [row["listing_uuid"] for row in sales]
    if any(not isinstance(key, str) or not key.strip() for key in identifiers) or len(
        set(identifiers)
    ) != len(identifiers):
        raise ValueError("each sale must identify a distinct nonempty listing")
    if any(type(row["asking_price"]) is not int or row["asking_price"] <= 0 for row in sales):
        raise ValueError("sale prices must be positive whole kamas")
    expected = {day: len(sales) * means[day.weekday()] / denominator for day in days}
    counts = {day: int(expected[day]) for day in days}
    remaining = len(sales) - sum(counts.values())
    for day in sorted(days, key=lambda day: (-(expected[day] - counts[day]), day))[:remaining]:
        counts[day] += 1

    source = "manual_estimated_date" if len(days) > 1 else "manual"
    slots = [day for day in days for _ in range(counts[day])]
    assigned, revenue = [], Counter()
    for row, day in zip(sales, slots, strict=True):
        sold_at = datetime.combine(day, time(23, 59, 59), timezone).astimezone(UTC)
        if day == end:
            sold_at = min(sold_at, observed.astimezone(UTC))
        if not aware_timestamp(row["selling_started_at"]) <= sold_at <= observed <= now:
            raise ValueError(
                f"assigned date violates listing/evidence bounds: {row['listing_uuid']}"
            )
        assigned.append({**row, "sold_at": sold_at.isoformat(), "sale_source": source})
        revenue[day] += row["asking_price"]

    return {
        "previous_reported_date": str(previous),
        "observed_at": observed.isoformat(),
        "timezone": payload["timezone"],
        "interval_start": str(start),
        "interval_end": str(end),
        "estimated_dates": len(days) > 1,
        "training_daily_counts": payload["training_daily_counts"],
        "weekday": [
            {
                "weekday": weekday,
                "observed_days": exposure[weekday],
                "sales": totals[weekday],
                "mean_sales_per_day": str(means[weekday]),
            }
            for weekday in range(7)
        ],
        "sale_count": len(sales),
        "revenue": sum(row["asking_price"] for row in sales),
        "daily": [
            {"date": str(day), "sales": counts[day], "revenue": revenue[day]} for day in days
        ],
        "assigned": assigned,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    result = plan_allocation(json.loads(arguments.input.read_text()))
    # Refuse overwriting a reviewed allocation or its input evidence.
    with arguments.output.open("x") as handle:
        handle.write(json.dumps(result, indent=2) + "\n")
    print(json.dumps({key: result[key] for key in ("sale_count", "revenue", "daily")}, indent=2))


if __name__ == "__main__":
    main()
