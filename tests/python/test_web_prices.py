from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError
from sqlalchemy import select

from dofus_touch_economy.importers.service import ImportService
from dofus_touch_economy.models import Item, PriceObservation, SaleListing
from dofus_touch_economy.schemas import SalePriceUpdate
from dofus_touch_economy.web_prices import price_command_values, price_thousands


@pytest.mark.parametrize(
    "entered,expected",
    [("77", 77000), ("77.5", 77500), ("0.001", 1), ("0.5", 500), ("1,000", 1000000)],
)
def test_thousands_conversion_round_trip(entered, expected):
    command = SalePriceUpdate.model_validate(
        price_command_values({"price_unit": "thousands"}, {"asking_price": entered})
    )
    assert command.asking_price == expected
    assert Decimal(price_thousands(expected)) * 1000 == expected


@pytest.mark.parametrize("entered", ["", "0", "-1", "77.0001", "NaN", "1e3", "77,5"])
def test_invalid_thousands_are_rejected_without_rounding(entered):
    with pytest.raises(ValidationError):
        SalePriceUpdate.model_validate(
            price_command_values({"price_unit": "thousands"}, {"asking_price": entered})
        )


@pytest.mark.parametrize(
    "path",
    [
        "/items/{uuid}/price",
        "/items/{uuid}/search-price",
        "/recipes/{uuid}/price",
        "/price-priorities/{uuid}/price",
        "/recipe-calculator/ingredients/{uuid}/price",
    ],
)
def test_web_price_endpoints_store_kamas_once(client, session_factory, catalog_item, path):
    field = "unit_price" if "ingredients" in path else "current_price"
    response = client.post(
        path.format(uuid=catalog_item.uuid),
        data={field: "77", "price_unit": "thousands"},
        follow_redirects=False,
    )
    assert response.status_code in (200, 303)
    with session_factory() as session:
        observations = list(session.scalars(select(PriceObservation)))
        assert len(observations) == 1
        assert observations[0].total_price == 77000
        assert session.scalar(select(SaleListing)) is None
    page = client.get(f"/items/{catalog_item.uuid}")
    assert 'value="77,000"' in page.text
    assert "77,000" in page.text
    assert "77 = 77 kamas" in page.text
    invalid = client.post(
        path.format(uuid=catalog_item.uuid), data={field: "77.0001", "price_unit": "thousands"}
    )
    assert invalid.status_code == 422
    with session_factory() as session:
        assert len(list(session.scalars(select(PriceObservation)))) == 1


def test_relist_thousands_and_canonical_suggestions(client, session_factory, catalog_item):
    with session_factory() as session:
        listing = SaleListing(
            item_id=catalog_item.id,
            lot_quantity=1,
            asking_price=100000,
            selling_started_at=datetime.now(UTC) - timedelta(days=20),
        )
        session.add(listing)
        session.commit()
        listing_uuid = listing.uuid
    page = client.get("/sales/price-review")
    assert 'value="thousands"' in page.text
    assert "77 = 77,000 kamas" in page.text
    response = client.post(
        f"/sales/price-review/{listing_uuid}/price",
        data={"asking_price": "77", "price_unit": "thousands"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert f'data-listing-uuid="{listing_uuid}"' not in client.get("/sales/price-review").text
    with session_factory() as session:
        assert session.scalar(select(SaleListing.asking_price)) == 77000
        assert session.scalar(select(PriceObservation.total_price)) == 77000
    # Suggestion buttons and older forms still post full kamas without the marker.
    assert (
        client.post(
            f"/sales/{listing_uuid}/price", data={"asking_price": "75000"}, follow_redirects=False
        ).status_code
        == 303
    )
    with session_factory() as session:
        assert session.scalar(select(SaleListing.asking_price)) == 75000
    assert (
        client.post(
            f"/sales/{listing_uuid}/price",
            data={"asking_price": "74", "price_unit": "thousands"},
            follow_redirects=False,
        ).status_code
        == 303
    )
    with session_factory() as session:
        assert session.scalar(select(SaleListing.asking_price)) == 74000


def test_calculator_uses_thousands_and_recipe_ingredient_uses_full_kamas(
    client, session_factory, fixture_dir
):
    ImportService(session_factory, market_context="Dodge").import_files(
        fixture_dir / "item_cost_valid.csv", fixture_dir / "item_recipes_valid.csv"
    )
    with session_factory() as session:
        items = {item.normalized_name: item.uuid for item in session.scalars(select(Item))}
    craft, ingredient = items["synthetic widget"], items["synthetic ore"]
    update = client.post(
        f"/items/{craft}/recipe-ingredients/{ingredient}/price",
        data={"unit_price": "500", "price_unit": "kamas"},
        follow_redirects=False,
    )
    assert update.status_code == 303
    sale = client.post(
        "/recipe-calculator/sales",
        data={
            "sale_item_uuid": str(craft),
            "selected_item_uuid": str(craft),
            f"quantity_{craft}": "2",
            f"sale_price_{craft}": "77",
            "price_unit": "thousands",
        },
        follow_redirects=False,
    )
    assert sale.status_code == 303
    with session_factory() as session:
        assert list(session.scalars(select(SaleListing.asking_price))) == [77000, 77000]
        assert (
            session.scalar(
                select(PriceObservation.total_price).where(
                    PriceObservation.note == "Recipe ingredient price update"
                )
            )
            == 500
        )


def test_sales_price_filters_use_thousands_and_preserve_canonical_links(
    client, session_factory, catalog_item
):
    with session_factory() as session:
        session.add_all(
            [
                SaleListing(
                    item_id=catalog_item.id,
                    lot_quantity=1,
                    asking_price=price,
                    selling_started_at=datetime.now(UTC),
                )
                for price in (77000, 100000)
            ]
        )
        session.commit()
    page = client.get("/sales?min_price=77&max_price=80&price_unit=thousands")
    assert "1 active · Total Price: 77,000" in page.text
    assert 'name="min_price" inputmode="decimal" value="77"' in page.text
    assert "min_price=77000" in page.text


def test_mixed_catalog_units_and_per_unit_prices(client, session_factory, fixture_dir):
    import re

    ImportService(session_factory, market_context="Dodge").import_files(
        fixture_dir / "item_cost_valid.csv", fixture_dir / "item_recipes_valid.csv"
    )
    with session_factory() as session:
        items = {item.normalized_name: item.uuid for item in session.scalars(select(Item))}
        for observation in session.scalars(select(PriceObservation)):
            observation.invalidated_at = datetime.now(UTC)
            observation.invalidation_reason = "Synthetic missing-price scenario"
        session.commit()
    craft, ingredient = items["synthetic widget"], items["synthetic ore"]
    for url, prefix, suffix in [
        ("/items", "/items/", "/search-price"),
        ("/price-priorities", "/price-priorities/", "/price"),
    ]:
        page = client.get(url)
        for item_uuid, unit in [(craft, "thousands"), (ingredient, "kamas")]:
            if url == "/price-priorities":
                unit = "kamas"
            form = re.search(
                r'<form\b[^>]*action="' + prefix + str(item_uuid) + suffix + r'[^\"]*".*?</form>',
                page.text,
                re.S,
            )
            assert form is not None
            assert f'name="price_unit" value="{unit}"' in form[0]
            response = client.post(
                prefix + str(item_uuid) + suffix,
                data={"current_price": "77", "price_unit": unit},
                follow_redirects=False,
            )
            assert response.status_code == 303
        # Reset the missing-price scenario for the next page.
        if url == "/items":
            with session_factory() as session:
                for observation in session.scalars(select(PriceObservation)):
                    observation.invalidated_at = datetime.now(UTC)
                    observation.invalidation_reason = "Synthetic missing-price scenario"
                session.commit()
    raw_page = client.get(f"/items/{ingredient}")
    assert 'value="77"' in raw_page.text
    assert 'name="price_unit" value="kamas"' in raw_page.text
    craft_page = client.get(f"/items/{craft}")
    assert 'value="0.077"' in craft_page.text
    assert 'name="price_unit" value="thousands"' in craft_page.text
    assert "kamas per unit" in craft_page.text
    calculator = client.post(
        "/recipe-calculator", data={"selected_item_uuid": str(craft), f"quantity_{craft}": "1"}
    )
    assert 'name="price_unit" value="kamas"' in calculator.text
    assert "kamas per unit" in calculator.text
    update = client.post(
        f"/recipe-calculator/ingredients/{ingredient}/price",
        data={"unit_price": "77", "price_unit": "kamas"},
    )
    assert update.json()["unit_price"] == 77
    with session_factory() as session:
        prices = list(
            session.scalars(
                select(PriceObservation.total_price).where(
                    PriceObservation.invalidated_at.is_(None)
                )
            )
        )
        assert sorted(prices) == [77, 77, 77]
