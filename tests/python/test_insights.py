from datetime import UTC, datetime
from decimal import Decimal

from dofus_touch_economy.models import ImportBatch, Item, Recipe, SaleListing, SourceRecord
from dofus_touch_economy.services.insights import InsightsService


def test_insights_report_synthesizes_trends_categories_and_action_signals(session) -> None:
    alpha = Item(
        display_name="Alpha Hat",
        normalized_name="alpha hat",
        category="Hat",
        identity_category="hat",
    )
    beta = Item(
        display_name="Beta Ring",
        normalized_name="beta ring",
        category="Ring",
        identity_category="ring",
    )
    session.add_all([alpha, beta])
    session.flush()
    batch = ImportBatch(
        dataset="synthetic_recipes",
        filename="synthetic.json",
        checksum="a" * 64,
        accepted_count=2,
        status="completed",
    )
    session.add(batch)
    for row_number, item, profession in (
        (1, alpha, "Tailor"),
        (2, beta, "Jeweller"),
    ):
        session.add(
            Recipe(
                crafted_item=item,
                profession=profession,
                source_record=SourceRecord(
                    import_batch=batch,
                    row_number=row_number,
                    raw_payload_json="{}",
                    status="accepted",
                ),
            )
        )
    session.add_all(
        [
            SaleListing(
                item_id=alpha.id,
                lot_quantity=1,
                asking_price=100,
                recipe_cost_at_sale=Decimal(80),
                selling_started_at=datetime(2026, 8, 1, tzinfo=UTC),
                date_sold=datetime(2026, 8, 2, tzinfo=UTC),
            ),
            SaleListing(
                item_id=alpha.id,
                lot_quantity=1,
                asking_price=200,
                recipe_cost_at_sale=Decimal(150),
                selling_started_at=datetime(2026, 8, 8, tzinfo=UTC),
                date_sold=datetime(2026, 8, 10, tzinfo=UTC),
            ),
            SaleListing(
                item_id=beta.id,
                lot_quantity=1,
                asking_price=300,
                recipe_cost_at_sale=Decimal(250),
                selling_started_at=datetime(2026, 8, 12, tzinfo=UTC),
                date_sold=datetime(2026, 8, 15, tzinfo=UTC),
            ),
            SaleListing(
                item_id=alpha.id,
                lot_quantity=1,
                asking_price=250,
                selling_started_at=datetime(2026, 8, 1, tzinfo=UTC),
            ),
        ]
    )
    session.commit()

    report = InsightsService(
        session,
        "Dodge",
        as_of=datetime(2026, 8, 29, tzinfo=UTC),
    ).report()

    assert report.first_sale_date.isoformat() == "2026-08-02"
    assert report.latest_sale_date.isoformat() == "2026-08-15"
    assert report.completed_sale_count == 3
    assert report.priced_sale_count == 3
    assert report.total_revenue == 600
    assert report.average_days_to_sell == Decimal(2)
    assert report.active_listing_count == 1
    assert report.active_listed_value == 250
    assert report.price_review_count == 1
    assert report.out_of_stock_count == 1
    assert report.cost_covered_sale_count == 3
    assert report.cost_coverage == Decimal(1)
    assert report.total_known_profit == Decimal(120)
    assert report.known_profit_margin == Decimal("0.2")
    assert report.latest_period is not None
    assert report.latest_period.sold_count == 2
    assert report.latest_period.revenue == 500
    assert report.latest_period.average_days_to_sell == Decimal("2.5")
    assert report.previous_period is not None
    assert report.previous_period.sold_count == 1
    assert report.previous_period.revenue == 100
    assert report.sales_count_change == Decimal(1)
    assert report.revenue_change == Decimal(4)
    assert report.top_seller is not None
    assert report.top_seller.display_name == "Alpha Hat"
    assert report.top_revenue_item is not None
    assert report.top_revenue_item.display_name == "Alpha Hat"
    assert report.fastest_repeat_seller is not None
    assert report.fastest_repeat_seller.display_name == "Alpha Hat"
    assert report.top_revenue_share == Decimal("0.5")
    assert report.top_profit_opportunity is None
    assert report.top_roi_opportunity is None
    assert report.profitable_recipe_count == 0
    assert [category.category for category in report.category_insights] == ["Hat", "Ring"]
    hat, ring = report.category_insights
    assert (hat.sold_count, hat.item_count, hat.revenue) == (2, 1, 300)
    assert hat.professions == ("Tailor",)
    assert hat.average_days_to_sell == Decimal("1.5")
    assert hat.active_listing_count == 1
    assert (ring.sold_count, ring.item_count, ring.revenue) == (1, 1, 300)
    assert ring.professions == ("Jeweller",)
    assert ring.average_days_to_sell == Decimal(3)
    assert ring.active_listing_count == 0


def test_insights_report_keeps_empty_data_explicit(session) -> None:
    report = InsightsService(session, "Dodge").report()

    assert report.completed_sale_count == 0
    assert report.priced_sale_count == 0
    assert report.total_revenue == 0
    assert report.average_days_to_sell is None
    assert report.latest_period is None
    assert report.previous_period is None
    assert report.cost_coverage is None
    assert report.known_profit_margin is None
    assert report.category_insights == ()


def test_insights_rolls_cape_categories_into_cloak_family(session) -> None:
    items = [
        Item(
            display_name=f"Synthetic {category}",
            normalized_name=f"synthetic {category.casefold()}",
            category=category,
            identity_category=category.casefold(),
        )
        for category in ("Cloak", "Cape", "Ceremonial Cape")
    ]
    session.add_all(items)
    session.flush()
    batch = ImportBatch(
        dataset="synthetic_recipes",
        filename="synthetic-cloaks.json",
        checksum="b" * 64,
        accepted_count=3,
        status="completed",
    )
    session.add(batch)
    for row_number, item, profession in zip(
        range(1, 4),
        items,
        ("Tailor", "Tailor", "Costumagus"),
        strict=True,
    ):
        session.add(
            Recipe(
                crafted_item=item,
                profession=profession,
                source_record=SourceRecord(
                    import_batch=batch,
                    row_number=row_number,
                    raw_payload_json="{}",
                    status="accepted",
                ),
            )
        )
    for index, item in enumerate(items, start=1):
        session.add_all(
            [
                SaleListing(
                    item_id=item.id,
                    lot_quantity=1,
                    asking_price=index * 100,
                    selling_started_at=datetime(2026, 8, 1, tzinfo=UTC),
                    date_sold=datetime(2026, 8, index + 1, tzinfo=UTC),
                ),
                SaleListing(
                    item_id=item.id,
                    lot_quantity=1,
                    asking_price=index * 100,
                    selling_started_at=datetime(2026, 8, 10, tzinfo=UTC),
                ),
            ]
        )
    session.commit()

    report = InsightsService(session, "Dodge").report()

    assert len(report.category_insights) == 1
    cloak = report.category_insights[0]
    assert cloak.category == "Cloak"
    assert cloak.professions == ("Costumagus", "Tailor")
    assert (cloak.sold_count, cloak.item_count, cloak.revenue) == (3, 3, 600)
    assert cloak.average_days_to_sell == Decimal(2)
    assert cloak.active_listing_count == 3
