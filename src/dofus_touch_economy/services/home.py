from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, tzinfo

from sqlalchemy.orm import Session

from dofus_touch_economy.repositories.home import HomeRepository, HomeSnapshot
from dofus_touch_economy.services.sales import ACTIVE_PRICE_REVIEW_DAYS


@dataclass(frozen=True)
class HomeTask:
    key: str
    title: str
    description: str
    url: str
    link_label: str


@dataclass(frozen=True)
class HomeFocus:
    weekday: int
    task: HomeTask


WEEKLY_FOCUS = (
    HomeFocus(
        0,
        HomeTask(
            "price-priorities",
            "Refresh missing prices",
            "Work through Price Priorities to unlock more complete crafting profit calculations.",
            "/price-priorities",
            "Open Price Priorities",
        ),
    ),
    HomeFocus(
        4,
        HomeTask(
            "relist",
            "Review and relist older stock",
            "Compare costs and suggested prices, then update listings that need a new price.",
            "/sales/price-review",
            "Open Price Review",
        ),
    ),
)


@dataclass(frozen=True)
class HomeReport:
    today: date
    next_day_at: datetime
    snapshot: HomeSnapshot
    daily_tasks: tuple[HomeTask, ...]
    focus: HomeTask | None
    week: tuple[tuple[date, HomeTask | None], ...]


class HomeService:
    def __init__(self, session: Session, *, display_timezone: tzinfo) -> None:
        self._repository = HomeRepository(session)
        self._timezone = display_timezone

    def report(self, *, as_of: datetime | None = None) -> HomeReport:
        now = as_of or datetime.now(UTC)
        today = now.astimezone(self._timezone).date()
        start = datetime.combine(today, time.min, self._timezone)
        review_before = datetime.combine(
            today - timedelta(days=ACTIVE_PRICE_REVIEW_DAYS - 1),
            time.min,
            self._timezone,
        )
        snapshot = self._repository.snapshot(
            as_of=now.astimezone(UTC),
            day_started_at=start.astimezone(UTC),
            review_before=review_before.astimezone(UTC),
        )
        daily_tasks = (
            HomeTask(
                "sales",
                "Mark what has sold",
                f"Check your sale notifications first. "
                f"{snapshot.sold_today:,} sales recorded today.",
                "/sales#currently-selling",
                "Open Sales Activity",
            ),
            HomeTask(
                "restock",
                "Craft items that are out of stock",
                f"{snapshot.out_of_stock_count:,} previously sold items have no active listing. "
                "Review craftable candidates and add them to your calculator.",
                "/out-of-stock-items",
                "Open Out of Stock Items",
            ),
            HomeTask(
                "opportunities",
                "Craft profitable opportunities",
                "Review profitable recipes in your professions, check ingredient costs, "
                "and add the ones you want to craft.",
                "/profit-opportunities",
                "Open Profit Opportunities",
            ),
            HomeTask(
                "dashboard",
                "Check what is changing",
                "Compare the last 7 days with the previous week: sales, realized profit, "
                "and stock still waiting to sell.",
                "/dashboard?days=7",
                "Open Dashboard",
            ),
        )
        focuses = {focus.weekday: focus.task for focus in WEEKLY_FOCUS}
        monday = today - timedelta(days=today.weekday())
        return HomeReport(
            today=today,
            next_day_at=datetime.combine(today + timedelta(days=1), time.min, self._timezone),
            snapshot=snapshot,
            daily_tasks=daily_tasks,
            focus=focuses.get(today.weekday()),
            week=tuple((monday + timedelta(days=day), focuses.get(day)) for day in range(7)),
        )
