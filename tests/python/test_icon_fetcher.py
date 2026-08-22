from sqlalchemy import select

from dofus_touch_economy.icon_fetcher import (
    PNG_SIGNATURE,
    fetch_item_icons,
    sync_touch_catalog,
)
from dofus_touch_economy.models import Item


def test_syncs_exchangeable_touch_catalog_and_icons_idempotently(
    session_factory,
    catalog_item,
    tmp_path,
) -> None:
    items_payload = {
        "1": {
            "id": 1,
            "iconId": 100,
            "nameId": catalog_item.display_name,
            "typeId": 10,
            "exchangeable": True,
        },
        "2": {
            "id": 2,
            "iconId": 200,
            "nameId": "Alpha Ring",
            "typeId": 20,
            "exchangeable": True,
        },
        "3": {
            "id": 3,
            "iconId": 300,
            "nameId": "Alpha Ring",
            "typeId": 20,
            "exchangeable": True,
        },
        "4": {
            "id": 4,
            "iconId": 400,
            "nameId": "Hidden Ring",
            "typeId": 20,
            "exchangeable": False,
        },
    }
    types_payload = {
        "10": {"id": 10, "nameId": "Ore"},
        "20": {"id": 20, "nameId": "Ring"},
    }

    def fetch_json(url, payload):
        if "config.json" in url:
            return {
                "dataUrl": "https://data.ankama-games.com",
                "assetsUrl": "https://touch.cdn.ankama.com/assets/version",
            }
        if payload == {"class": "Items", "lang": "en"}:
            return items_payload
        if payload == {"class": "ItemTypes", "lang": "en"}:
            return types_payload
        raise AssertionError(f"unexpected request: {url} {payload}")

    downloaded_urls: list[str] = []

    def fetch_bytes(url):
        downloaded_urls.append(url)
        return PNG_SIGNATURE + b"synthetic"

    icon_directory = tmp_path / "icons"
    summary = sync_touch_catalog(
        session_factory,
        icon_directory,
        json_fetcher=fetch_json,
        bytes_fetcher=fetch_bytes,
    )

    assert summary.source_count == 2
    assert summary.matched_count == 1
    assert summary.created_count == 1
    assert summary.catalog_count == 2
    assert summary.cached_count == 0
    assert summary.downloaded_count == 2
    assert summary.failed_names == ()
    assert set(downloaded_urls) == {
        "https://touch.cdn.ankama.com/assets/version/gfx/items/100.png",
        "https://touch.cdn.ankama.com/assets/version/gfx/items/200.png",
    }
    with session_factory() as session:
        items = {item.display_name: item for item in session.scalars(select(Item)).all()}
    assert items["Alpha Ring"].category == "Ring"
    assert items["Alpha Ring"].created_source == "imported"
    assert "Hidden Ring" not in items
    assert (icon_directory / f"{items['Alpha Ring'].uuid}.png").is_file()

    repeated = sync_touch_catalog(
        session_factory,
        icon_directory,
        json_fetcher=fetch_json,
        bytes_fetcher=lambda _url: (_ for _ in ()).throw(AssertionError("unexpected download")),
    )

    assert repeated.matched_count == 2
    assert repeated.created_count == 0
    assert repeated.catalog_count == 2
    assert repeated.cached_count == 2
    assert repeated.downloaded_count == 0


def test_sync_preserves_existing_category_for_unique_exact_name(
    session_factory,
    catalog_item,
    tmp_path,
) -> None:
    def fetch_json(url, payload):
        if "config.json" in url:
            return {
                "dataUrl": "https://data.ankama-games.com",
                "assetsUrl": "https://touch.cdn.ankama.com/assets/version",
            }
        if payload == {"class": "Items", "lang": "en"}:
            return {
                "1": {
                    "id": 1,
                    "iconId": 100,
                    "nameId": catalog_item.display_name,
                    "typeId": 10,
                    "exchangeable": True,
                }
            }
        if payload == {"class": "ItemTypes", "lang": "en"}:
            return {"10": {"id": 10, "nameId": "Resource"}}
        raise AssertionError(f"unexpected request: {url} {payload}")

    summary = sync_touch_catalog(
        session_factory,
        tmp_path / "icons",
        json_fetcher=fetch_json,
        bytes_fetcher=lambda _url: PNG_SIGNATURE,
    )

    assert summary.matched_count == 1
    assert summary.created_count == 0
    with session_factory() as session:
        item = session.scalar(select(Item))
    assert item is not None
    assert item.uuid == catalog_item.uuid
    assert item.category == "Ore"


def test_fetches_exact_touch_and_dofusdb_fallback_icons(
    session_factory,
    catalog_item,
    tmp_path,
) -> None:
    with session_factory() as session:
        fallback_item = Item(
            display_name="Fallback Resource",
            normalized_name="fallback resource",
            category="resource",
            identity_category="resource",
        )
        session.add(fallback_item)
        session.commit()

    def fetch_json(url, payload):
        if "config.json" in url:
            return {
                "dataUrl": "https://data.ankama-games.com",
                "assetsUrl": "https://touch.cdn.ankama.com/assets/version",
            }
        if payload is not None:
            return {"1": {"id": 1, "iconId": 100, "nameId": catalog_item.display_name}}
        return {
            "total": 1,
            "data": [
                {
                    "id": 2,
                    "iconId": 200,
                    "name": {"en": fallback_item.display_name},
                }
            ],
        }

    downloaded_urls: list[str] = []

    def fetch_bytes(url):
        downloaded_urls.append(url)
        return PNG_SIGNATURE + b"synthetic"

    icon_directory = tmp_path / "icons"
    summary = fetch_item_icons(
        session_factory,
        icon_directory,
        json_fetcher=fetch_json,
        bytes_fetcher=fetch_bytes,
    )

    assert summary.catalog_count == 2
    assert summary.touch_match_count == 1
    assert summary.fallback_match_count == 1
    assert summary.wiki_match_count == 0
    assert summary.downloaded_count == 2
    assert summary.missing_names == ()
    assert summary.failed_names == ()
    assert set(downloaded_urls) == {
        "https://touch.cdn.ankama.com/assets/version/gfx/items/100.png",
        "https://api.dofusdb.fr/img/items/200.png",
    }
    assert (icon_directory / f"{catalog_item.uuid}.png").is_file()
    assert (icon_directory / f"{fallback_item.uuid}.png").is_file()

    with session_factory() as session:
        sources = {
            item.normalized_name: item.icon_source_url
            for item in session.scalars(select(Item)).all()
        }
    assert sources["synthetic ore"].endswith("/gfx/items/100.png")
    assert sources["fallback resource"].endswith("/items/200.png")


def test_uses_lowest_item_id_for_ambiguous_exact_name(
    session_factory,
    catalog_item,
    tmp_path,
) -> None:
    def fetch_json(url, payload):
        if "config.json" in url:
            return {
                "dataUrl": "https://data.ankama-games.com",
                "assetsUrl": "https://touch.cdn.ankama.com/assets/version",
            }
        if payload is not None:
            return {
                "9": {"id": 9, "iconId": 900, "nameId": catalog_item.display_name},
                "3": {"id": 3, "iconId": 300, "nameId": catalog_item.display_name},
            }
        raise AssertionError(f"unexpected fallback request: {url}")

    summary = fetch_item_icons(
        session_factory,
        tmp_path / "icons",
        json_fetcher=fetch_json,
        bytes_fetcher=lambda _url: PNG_SIGNATURE,
    )

    assert summary.ambiguous_match_count == 1
    with session_factory() as session:
        source_url = session.scalar(select(Item.icon_source_url))
    assert source_url is not None
    assert source_url.endswith("/gfx/items/300.png")


def test_does_not_guess_nonexact_item_names(session_factory, catalog_item, tmp_path) -> None:
    def fetch_json(url, payload):
        if "config.json" in url:
            return {
                "dataUrl": "https://data.ankama-games.com",
                "assetsUrl": "https://touch.cdn.ankama.com/assets/version",
            }
        if payload is not None:
            return {}
        if "fandom.com" in url:
            return {"query": {"pages": []}}
        return {
            "total": 1,
            "data": [
                {
                    "id": 2,
                    "iconId": 200,
                    "name": {"en": f"{catalog_item.display_name}s"},
                }
            ],
        }

    summary = fetch_item_icons(
        session_factory,
        tmp_path / "icons",
        json_fetcher=fetch_json,
        bytes_fetcher=lambda _url: PNG_SIGNATURE,
    )

    assert summary.downloaded_count == 0
    assert summary.missing_names == (catalog_item.display_name,)


def test_uses_exact_wiki_redirect_as_final_fallback(
    session_factory,
    catalog_item,
    tmp_path,
) -> None:
    def fetch_json(url, payload):
        if "config.json" in url:
            return {
                "dataUrl": "https://data.ankama-games.com",
                "assetsUrl": "https://touch.cdn.ankama.com/assets/version",
            }
        if payload is not None:
            return {}
        if "api.dofusdb.fr" in url:
            return {"total": 0, "data": []}
        return {
            "query": {
                "redirects": [{"from": catalog_item.display_name, "to": "Canonical Item Name"}],
                "pages": [
                    {
                        "pageid": 42,
                        "title": "Canonical Item Name",
                        "original": {"source": "https://static.wikia.nocookie.net/dofus/item.png"},
                    }
                ],
            }
        }

    summary = fetch_item_icons(
        session_factory,
        tmp_path / "icons",
        json_fetcher=fetch_json,
        bytes_fetcher=lambda _url: PNG_SIGNATURE,
    )

    assert summary.wiki_match_count == 1
    assert summary.missing_names == ()
    with session_factory() as session:
        source_url = session.scalar(select(Item.icon_source_url))
    assert source_url is not None
    assert source_url.endswith("item.png?format=original")


def test_uses_reviewed_legacy_alias_for_exact_touch_match(
    session_factory,
    catalog_item,
    tmp_path,
) -> None:
    with session_factory() as session:
        item = session.get(Item, catalog_item.id)
        assert item is not None
        item.display_name = "Spifoux Skin"
        item.normalized_name = "spifoux skin"
        session.commit()

    def fetch_json(url, payload):
        if "config.json" in url:
            return {
                "dataUrl": "https://data.ankama-games.com",
                "assetsUrl": "https://touch.cdn.ankama.com/assets/version",
            }
        if payload is not None:
            return {"1": {"id": 1, "iconId": 100, "nameId": "Spitfoux Skin"}}
        raise AssertionError(f"unexpected fallback request: {url}")

    summary = fetch_item_icons(
        session_factory,
        tmp_path / "icons",
        json_fetcher=fetch_json,
        bytes_fetcher=lambda _url: PNG_SIGNATURE,
    )

    assert summary.touch_match_count == 1
    assert summary.missing_names == ()


def test_uses_exact_wiki_file_when_item_page_has_no_image(
    session_factory,
    catalog_item,
    tmp_path,
) -> None:
    with session_factory() as session:
        item = session.get(Item, catalog_item.id)
        assert item is not None
        item.display_name = "Whitish Fang Fur"
        item.normalized_name = "whitish fang fur"
        session.commit()

    def fetch_json(url, payload):
        if "config.json" in url:
            return {
                "dataUrl": "https://data.ankama-games.com",
                "assetsUrl": "https://touch.cdn.ankama.com/assets/version",
            }
        if payload is not None:
            return {}
        if "api.dofusdb.fr" in url:
            return {"total": 0, "data": []}
        if "prop=pageimages" in url:
            return {"query": {"pages": []}}
        return {
            "query": {
                "pages": [
                    {
                        "pageid": 55,
                        "title": "File:Whitish Fang Fur.png",
                        "imageinfo": [{"url": "https://static.wikia.nocookie.net/dofus/fur.png"}],
                    }
                ]
            }
        }

    summary = fetch_item_icons(
        session_factory,
        tmp_path / "icons",
        json_fetcher=fetch_json,
        bytes_fetcher=lambda _url: PNG_SIGNATURE,
    )

    assert summary.wiki_match_count == 1
    assert summary.missing_names == ()
    with session_factory() as session:
        source_url = session.scalar(select(Item.icon_source_url))
    assert source_url is not None
    assert source_url.endswith("fur.png?format=original")
