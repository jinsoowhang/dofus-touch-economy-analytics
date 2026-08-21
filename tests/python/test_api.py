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
