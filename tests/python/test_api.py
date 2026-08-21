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
