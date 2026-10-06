from tests.helpers import create_category, create_product


def test_list_and_filter_products(client, admin_token):
    cat = create_category(client, admin_token)
    create_product(
        client, admin_token, category_id=cat["id"], slug="grey-sofa",
        name="Grey Sofa", price_cents=50000, color="grey", material="Fabric",
    )
    create_product(
        client, admin_token, category_id=cat["id"], slug="blue-sofa",
        name="Blue Sofa", price_cents=90000, color="blue", material="Leather",
        sku="TEST-SKU-2",
    )

    # List all
    r = client.get("/api/v1/catalog/products")
    assert r.status_code == 200
    assert r.json()["total"] == 2

    # Filter by color
    r = client.get("/api/v1/catalog/products", params={"color": "blue"})
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["slug"] == "blue-sofa"

    # Filter by material
    r = client.get("/api/v1/catalog/products", params={"material": "Fabric"})
    assert r.json()["total"] == 1

    # Price range
    r = client.get("/api/v1/catalog/products", params={"price_max": 60000})
    assert r.json()["total"] == 1
    assert r.json()["items"][0]["slug"] == "grey-sofa"


def test_sort_by_price(client, admin_token):
    cat = create_category(client, admin_token)
    create_product(client, admin_token, category_id=cat["id"], slug="cheap", name="Cheap",
                   price_cents=10000, sku="C1")
    create_product(client, admin_token, category_id=cat["id"], slug="pricey", name="Pricey",
                   price_cents=99000, sku="C2")
    r = client.get("/api/v1/catalog/products", params={"sort": "price_asc"})
    slugs = [i["slug"] for i in r.json()["items"]]
    assert slugs == ["cheap", "pricey"]
    r = client.get("/api/v1/catalog/products", params={"sort": "price_desc"})
    slugs = [i["slug"] for i in r.json()["items"]]
    assert slugs == ["pricey", "cheap"]


def test_search_and_autocomplete(client, admin_token):
    cat = create_category(client, admin_token)
    create_product(client, admin_token, category_id=cat["id"], slug="oak-table",
                   name="Oak Dining Table", sku="S1")
    r = client.get("/api/v1/catalog/products", params={"q": "oak"})
    assert r.json()["total"] == 1
    r = client.get("/api/v1/catalog/autocomplete", params={"q": "oak"})
    assert r.json()[0]["slug"] == "oak-table"


def test_product_detail_and_facets(client, admin_token):
    cat = create_category(client, admin_token)
    create_product(client, admin_token, category_id=cat["id"], slug="detail-sofa",
                   name="Detail Sofa", color="green", room_type="Study")
    r = client.get("/api/v1/catalog/products/detail-sofa")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Detail Sofa"
    assert len(body["variants"]) == 1
    assert body["variants"][0]["in_stock"] is True

    f = client.get("/api/v1/catalog/facets").json()
    assert "green" in f["colors"]
    assert "Study" in f["room_types"]


def test_detail_404_for_unknown_slug(client):
    assert client.get("/api/v1/catalog/products/nope").status_code == 404


def test_pagination(client, admin_token):
    cat = create_category(client, admin_token)
    for i in range(5):
        create_product(client, admin_token, category_id=cat["id"], slug=f"p{i}",
                       name=f"Product {i}", sku=f"SKU{i}")
    r = client.get("/api/v1/catalog/products", params={"page": 1, "page_size": 2})
    body = r.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2
