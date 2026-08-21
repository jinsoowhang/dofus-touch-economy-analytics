from uuid import uuid4


def test_rejects_cross_origin_mutation(client, catalog_item) -> None:
    response = client.post(
        f"/api/v1/items/{catalog_item.uuid}/price-observations",
        headers={"origin": "https://example.com"},
        json={
            "lot_quantity": 1,
            "total_price": 100,
            "observed_at": "2026-08-20T12:00:00Z",
        },
    )

    assert response.status_code == 403


def test_api_search_matches_html_catalog(client, catalog_item) -> None:
    response = client.get("/api/v1/items", params={"q": "  ORE "})

    assert response.status_code == 200
    assert [item["uuid"] for item in response.json()] == [str(catalog_item.uuid)]


def test_api_creates_manual_item_and_makes_it_searchable(client) -> None:
    created = client.post(
        "/api/v1/items",
        json={"display_name": "  New   Blade  ", "category": " Sword "},
    )

    assert created.status_code == 201
    assert created.json()["display_name"] == "New Blade"
    assert created.json()["category"] == "Sword"
    assert created.json()["created_source"] == "manual"
    search = client.get("/api/v1/items", params={"q": "new blade"})
    assert [item["uuid"] for item in search.json()] == [created.json()["uuid"]]


def test_api_rejects_duplicate_manual_item_with_existing_candidate(client, catalog_item) -> None:
    response = client.post(
        "/api/v1/items",
        json={"display_name": "synthetic ore", "category": "ORE"},
    )

    assert response.status_code == 409
    assert response.json()["detail"]["candidates"][0]["uuid"] == str(catalog_item.uuid)


def test_api_rejects_blank_manual_item_name(client) -> None:
    response = client.post("/api/v1/items", json={"display_name": "   "})

    assert response.status_code == 422


def test_unknown_api_item_returns_404(client) -> None:
    response = client.get(f"/api/v1/items/{uuid4()}")

    assert response.status_code == 404


def test_records_lot_price_and_returns_recalculated_detail(client, catalog_item) -> None:
    response = client.post(
        f"/api/v1/items/{catalog_item.uuid}/price-observations",
        json={
            "lot_quantity": 10,
            "total_price": 1250,
            "observed_at": "2026-08-20T12:00:00Z",
            "note": "Manual market check",
        },
    )

    assert response.status_code == 201
    assert response.json()["current_price"]["unit_price"] == "125"


def test_invalidates_observation_and_restores_previous_api_price(client, priced_item) -> None:
    response = client.post(
        f"/api/v1/price-observations/{priced_item.current_uuid}/invalidation",
        json={"reason": "Mistyped price"},
    )

    assert response.status_code == 200
    assert response.json()["current_price"]["observation_uuid"] == str(priced_item.previous_uuid)


def test_rejects_repeated_invalidation(client, priced_item) -> None:
    path = f"/api/v1/price-observations/{priced_item.current_uuid}/invalidation"
    assert client.post(path, json={"reason": "Mistyped price"}).status_code == 200

    response = client.post(path, json={"reason": "Again"})

    assert response.status_code == 409


def test_unknown_observation_returns_404(client) -> None:
    response = client.post(
        f"/api/v1/price-observations/{uuid4()}/invalidation",
        json={"reason": "Mistyped price"},
    )

    assert response.status_code == 404


def test_unknown_item_price_create_returns_404(client) -> None:
    response = client.post(
        f"/api/v1/items/{uuid4()}/price-observations",
        json={
            "lot_quantity": 1,
            "total_price": 100,
            "observed_at": "2026-08-20T12:00:00Z",
        },
    )

    assert response.status_code == 404


def test_rejects_invalid_price_commands(client, catalog_item) -> None:
    path = f"/api/v1/items/{catalog_item.uuid}/price-observations"
    nonpositive = client.post(
        path,
        json={
            "lot_quantity": 0,
            "total_price": 100,
            "observed_at": "2026-08-20T12:00:00Z",
        },
    )
    naive_time = client.post(
        path,
        json={
            "lot_quantity": 1,
            "total_price": 100,
            "observed_at": "2026-08-20T12:00:00",
        },
    )

    assert nonpositive.status_code == 422
    assert naive_time.status_code == 422


def test_observation_timestamps_are_normalized_and_returned_as_utc(client, catalog_item) -> None:
    path = f"/api/v1/items/{catalog_item.uuid}/price-observations"
    created = client.post(
        path,
        json={
            "lot_quantity": 1,
            "total_price": 100,
            "observed_at": "2026-08-20T12:00:00+05:00",
        },
    )
    reloaded = client.get(f"/api/v1/items/{catalog_item.uuid}")

    assert created.status_code == 201
    assert created.json()["current_price"]["observed_at"] == "2026-08-20T07:00:00Z"
    assert reloaded.json()["current_price"]["observed_at"] == "2026-08-20T07:00:00Z"
    assert reloaded.json()["current_price"]["recorded_at"].endswith("Z")
