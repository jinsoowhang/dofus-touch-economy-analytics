import importlib.util
from datetime import UTC, datetime
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).resolve().parents[2]
    / ".agents/skills/dofus-sales-catch-up/scripts/allocate_sales.py"
)
spec = importlib.util.spec_from_file_location("sales_catch_up_allocation", SCRIPT)
allocation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(allocation)
NOW = datetime(2026, 10, 11, 4, tzinfo=UTC)


def payload(count=10):
    return {
        "previous_reported_date": "2026-10-05",
        "observed_at": "2026-10-10T19:00:00-07:00",
        "timezone": "America/Los_Angeles",
        "training_daily_counts": {f"2026-09-{day:02}": 10 for day in range(7, 14)},
        "sales": [
            {
                "listing_uuid": str(index),
                "asking_price": 1001 + index,
                "selling_started_at": "2026-10-01T12:00:00+00:00",
                "image_number": 1,
            }
            for index in range(count)
        ],
    }


def test_conserves_whole_sales_prices_evidence_and_revenue():
    source = payload(13)
    result = allocation.plan_allocation(source, now=NOW)
    assert [day["sales"] for day in result["daily"]] == [3, 3, 3, 2, 2]
    assert sum(day["revenue"] for day in result["daily"]) == result["revenue"]
    assert result["sale_count"] == sum(day["sales"] for day in result["daily"]) == 13
    for original, assigned in zip(source["sales"], result["assigned"], strict=True):
        assert all(assigned[key] == value for key, value in original.items())
        assert assigned["sale_source"] == "manual_estimated_date"
    assert result["assigned"][-1]["sold_at"] == "2026-10-11T02:00:00+00:00"


def test_unequal_weekday_exposure_uses_means_not_totals():
    source = payload(10)
    source["training_daily_counts"]["2026-09-15"] = 10  # A second observed Tuesday.
    result = allocation.plan_allocation(source, now=NOW)
    assert [day["sales"] for day in result["daily"]] == [2, 2, 2, 2, 2]
    assert result["weekday"][1]["observed_days"] == 2


def test_known_zero_sales_days_remain_in_exposure():
    source = payload(8)
    source["training_daily_counts"]["2026-09-08"] = 0
    result = allocation.plan_allocation(source, now=NOW)
    assert [day["sales"] for day in result["daily"]] == [0, 2, 2, 2, 2]


def test_single_day_is_manual_and_empty_batch_is_conserved():
    source = payload(1)
    source["previous_reported_date"] = "2026-10-09"
    result = allocation.plan_allocation(source, now=NOW)
    assert not result["estimated_dates"]
    assert result["assigned"][0]["sale_source"] == "manual"
    assert allocation.plan_allocation(payload(0), now=NOW)["sale_count"] == 0


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("observed_at", "2026-10-12T19:00:00-07:00", "future"),
        ("observed_at", "2026-10-10T19:00:00", "timezone"),
        ("previous_reported_date", "2026-10-10", "follow"),
        ("training_daily_counts", {"2026-09-07": 10}, "seven weekdays"),
        ("training_daily_counts", {"2026-10-06": 10}, "earlier verified"),
    ],
)
def test_rejects_unsupported_dates_and_training(key, value, message):
    source = payload()
    source[key] = value
    with pytest.raises(ValueError, match=message):
        allocation.plan_allocation(source, now=NOW)


def test_rejects_zero_weights_duplicate_listings_and_fractional_prices():
    source = payload()
    source["training_daily_counts"] = dict.fromkeys(source["training_daily_counts"], 0)
    with pytest.raises(ValueError, match="no observed weekday sales"):
        allocation.plan_allocation(source, now=NOW)
    source = payload()
    source["sales"][1]["listing_uuid"] = source["sales"][0]["listing_uuid"]
    with pytest.raises(ValueError, match="distinct"):
        allocation.plan_allocation(source, now=NOW)
    source = payload()
    source["sales"][0]["asking_price"] = 1.5
    with pytest.raises(ValueError, match="whole kamas"):
        allocation.plan_allocation(source, now=NOW)


def test_rejects_dates_before_listing_creation_without_moving_sales():
    source = payload()
    source["sales"][0]["selling_started_at"] = "2026-10-10T00:00:00+00:00"
    with pytest.raises(ValueError, match="listing/evidence bounds"):
        allocation.plan_allocation(source, now=NOW)
