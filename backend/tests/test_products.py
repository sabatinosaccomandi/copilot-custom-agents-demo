"""Tests for the ``/products`` Blueprint.

Endpoint matrix
---------------
GET    /products/              – TestListProducts
GET    /products/<id>          – TestGetProduct
POST   /products/              – TestCreateProduct
PUT    /products/<id>          – TestUpdateProduct
POST   /products/<id>/discount – TestDiscountProduct
Flask error handlers           – TestGlobalErrorHandlers

Read endpoints (GET) are *public* — no authentication is required.
Write endpoints (POST, PUT) are admin-only via the ``require_admin``
decorator, so each write-endpoint class tests all four auth outcomes:
    • No ``Authorization`` header               → 401
    • Valid token with ``role="user"``          → 403
    • Valid token with ``role="admin"``         → 2xx or domain error

Validation rules (from ``product_service._validate_product_fields``):
    • ``name``  – non-empty string, ≤ 100 chars
    • ``price`` – positive number, bool explicitly rejected
    • ``stock`` – non-negative int, bool explicitly rejected (optional field)
Discount rules (from ``product_service._compute_discounted_price``):
    • Must be a number in [0, 100], bool explicitly rejected
"""
from __future__ import annotations

import pytest


# ===========================================================================
# GET /products/  — list all products
# ===========================================================================

class TestListProducts:
    """GET /products/ — public endpoint; no auth required."""

    def test_empty_catalogue_returns_empty_array(self, client):
        resp = client.get("/products/")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_returns_200_without_any_auth_token(self, client, sample_product):
        """Must be accessible without authentication."""
        resp = client.get("/products/")
        assert resp.status_code == 200

    def test_returns_json_array(self, client, sample_product):
        resp = client.get("/products/")
        assert isinstance(resp.get_json(), list)

    def test_persisted_products_appear_in_listing(self, client, sample_product):
        resp = client.get("/products/")
        ids = [p["id"] for p in resp.get_json()]
        assert sample_product["id"] in ids

    def test_response_objects_have_expected_keys(self, client, sample_product):
        resp = client.get("/products/")
        for product in resp.get_json():
            assert "id" in product
            assert "name" in product
            assert "price" in product
            assert "stock" in product

    def test_multiple_products_are_all_returned(self, client, admin_token):
        """Create two products and verify both appear."""
        client.post(
            "/products/",
            json={"name": "Alpha", "price": 1.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        client.post(
            "/products/",
            json={"name": "Beta", "price": 2.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        resp = client.get("/products/")
        names = {p["name"] for p in resp.get_json()}
        assert "Alpha" in names
        assert "Beta" in names


# ===========================================================================
# GET /products/<id>  — get single product
# ===========================================================================

class TestGetProduct:
    """GET /products/<id> — public endpoint; no auth required."""

    def test_happy_path_returns_200(self, client, sample_product):
        resp = client.get(f"/products/{sample_product['id']}")
        assert resp.status_code == 200

    def test_response_contains_correct_product_data(self, client, sample_product):
        resp = client.get(f"/products/{sample_product['id']}")
        data = resp.get_json()
        assert data["id"] == sample_product["id"]
        assert data["name"] == sample_product["name"]
        assert data["price"] == pytest.approx(sample_product["price"])
        assert data["stock"] == sample_product["stock"]

    def test_response_has_all_four_fields(self, client, sample_product):
        data = client.get(f"/products/{sample_product['id']}").get_json()
        for key in ("id", "name", "price", "stock"):
            assert key in data

    def test_nonexistent_id_returns_404(self, client):
        resp = client.get("/products/99999")
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_public_access_without_token(self, client, sample_product):
        """No Authorization header required for read."""
        resp = client.get(f"/products/{sample_product['id']}")
        assert resp.status_code == 200


# ===========================================================================
# POST /products/  — create product
# ===========================================================================

class TestCreateProduct:
    """POST /products/ — admin-only product creation."""

    # ------------------------------------------------------------------
    # Happy paths
    # ------------------------------------------------------------------

    def test_admin_can_create_product_returns_201(self, client, admin_token):
        resp = client.post(
            "/products/",
            json={"name": "New Product", "price": 9.99},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201

    def test_response_contains_id_and_name(self, client, admin_token):
        resp = client.post(
            "/products/",
            json={"name": "Widget", "price": 5.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = resp.get_json()
        assert "id" in data
        assert data["name"] == "Widget"
        assert isinstance(data["id"], int)

    def test_product_is_retrievable_after_creation(self, client, admin_token):
        create = client.post(
            "/products/",
            json={"name": "Gadget", "price": 12.50, "stock": 3},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        pid = create.get_json()["id"]
        get = client.get(f"/products/{pid}")
        assert get.status_code == 200
        data = get.get_json()
        assert data["name"] == "Gadget"
        assert data["price"] == pytest.approx(12.50)
        assert data["stock"] == 3

    def test_stock_defaults_to_zero_when_omitted(self, client, admin_token):
        create = client.post(
            "/products/",
            json={"name": "No Stock", "price": 1.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        pid = create.get_json()["id"]
        data = client.get(f"/products/{pid}").get_json()
        assert data["stock"] == 0

    def test_explicit_stock_zero_is_accepted(self, client, admin_token):
        resp = client.post(
            "/products/",
            json={"name": "Zero Stock", "price": 1.0, "stock": 0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201

    def test_integer_price_is_accepted(self, client, admin_token):
        """Price field accepts plain integers as well as floats."""
        resp = client.post(
            "/products/",
            json={"name": "Int Price", "price": 10},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201

    def test_name_is_stored_with_surrounding_whitespace_stripped(
        self, client, admin_token
    ):
        create = client.post(
            "/products/",
            json={"name": "  Padded  ", "price": 1.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        pid = create.get_json()["id"]
        data = client.get(f"/products/{pid}").get_json()
        assert data["name"] == "Padded"

    # ------------------------------------------------------------------
    # Authentication / authorisation guard
    # ------------------------------------------------------------------

    def test_no_auth_header_returns_401(self, client):
        resp = client.post(
            "/products/", json={"name": "X", "price": 1.0}
        )
        assert resp.status_code == 401
        assert "error" in resp.get_json()

    def test_regular_user_token_returns_403(self, client, user_token):
        resp = client.post(
            "/products/",
            json={"name": "X", "price": 1.0},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 403
        assert "error" in resp.get_json()

    def test_invalid_token_returns_401(self, client):
        resp = client.post(
            "/products/",
            json={"name": "X", "price": 1.0},
            headers={"Authorization": "Bearer totally.fake.token"},
        )
        assert resp.status_code == 401

    # ------------------------------------------------------------------
    # Field validation — name
    # ------------------------------------------------------------------

    def test_missing_name_returns_422_with_field_error(self, client, admin_token):
        resp = client.post(
            "/products/",
            json={"price": 5.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "name" in resp.get_json().get("errors", {})

    def test_empty_string_name_returns_422(self, client, admin_token):
        resp = client.post(
            "/products/",
            json={"name": "", "price": 5.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "name" in resp.get_json().get("errors", {})

    def test_whitespace_only_name_returns_422(self, client, admin_token):
        resp = client.post(
            "/products/",
            json={"name": "   ", "price": 5.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "name" in resp.get_json().get("errors", {})

    def test_name_too_long_returns_422(self, client, admin_token):
        resp = client.post(
            "/products/",
            json={"name": "x" * 101, "price": 5.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "name" in resp.get_json().get("errors", {})

    def test_name_exactly_100_chars_is_accepted(self, client, admin_token):
        resp = client.post(
            "/products/",
            json={"name": "n" * 100, "price": 5.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201

    def test_null_name_returns_422(self, client, admin_token):
        resp = client.post(
            "/products/",
            json={"name": None, "price": 5.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "name" in resp.get_json().get("errors", {})

    # ------------------------------------------------------------------
    # Field validation — price
    # ------------------------------------------------------------------

    def test_missing_price_returns_422_with_field_error(self, client, admin_token):
        resp = client.post(
            "/products/",
            json={"name": "Test"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "price" in resp.get_json().get("errors", {})

    def test_negative_price_returns_422(self, client, admin_token):
        resp = client.post(
            "/products/",
            json={"name": "Test", "price": -1.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "price" in resp.get_json().get("errors", {})

    def test_zero_price_returns_422(self, client, admin_token):
        """Price must be *strictly* positive — zero is rejected."""
        resp = client.post(
            "/products/",
            json={"name": "Test", "price": 0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "price" in resp.get_json().get("errors", {})

    def test_boolean_true_as_price_returns_422(self, client, admin_token):
        """bool is a subclass of int in Python; the service must reject it."""
        resp = client.post(
            "/products/",
            json={"name": "Test", "price": True},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "price" in resp.get_json().get("errors", {})

    def test_boolean_false_as_price_returns_422(self, client, admin_token):
        resp = client.post(
            "/products/",
            json={"name": "Test", "price": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "price" in resp.get_json().get("errors", {})

    def test_string_price_returns_422(self, client, admin_token):
        resp = client.post(
            "/products/",
            json={"name": "Test", "price": "9.99"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "price" in resp.get_json().get("errors", {})

    def test_null_price_returns_422(self, client, admin_token):
        resp = client.post(
            "/products/",
            json={"name": "Test", "price": None},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "price" in resp.get_json().get("errors", {})

    # ------------------------------------------------------------------
    # Field validation — stock
    # ------------------------------------------------------------------

    def test_negative_stock_returns_422(self, client, admin_token):
        resp = client.post(
            "/products/",
            json={"name": "Test", "price": 5.0, "stock": -1},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "stock" in resp.get_json().get("errors", {})

    def test_boolean_true_as_stock_returns_422(self, client, admin_token):
        resp = client.post(
            "/products/",
            json={"name": "Test", "price": 5.0, "stock": True},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "stock" in resp.get_json().get("errors", {})

    def test_float_stock_returns_422(self, client, admin_token):
        """Stock must be an integer — a float like 1.5 is rejected."""
        resp = client.post(
            "/products/",
            json={"name": "Test", "price": 5.0, "stock": 1.5},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "stock" in resp.get_json().get("errors", {})

    # ------------------------------------------------------------------
    # Multiple validation errors at once
    # ------------------------------------------------------------------

    def test_invalid_name_and_price_returns_both_errors(
        self, client, admin_token
    ):
        resp = client.post(
            "/products/",
            json={"name": "", "price": -5.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        errors = resp.get_json().get("errors", {})
        assert "name" in errors
        assert "price" in errors

    # ------------------------------------------------------------------
    # Malformed requests
    # ------------------------------------------------------------------

    def test_non_json_body_returns_400(self, client, admin_token):
        resp = client.post(
            "/products/",
            data="name=x&price=1",
            content_type="application/x-www-form-urlencoded",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_empty_body_returns_400(self, client, admin_token):
        resp = client.post(
            "/products/",
            data="",
            content_type="application/json",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_empty_json_object_returns_400(self, client, admin_token):
        """An empty JSON object ``{}`` is falsy — ``require_json_body``
        rejects it with 400 before field validation is reached.
        """
        resp = client.post(
            "/products/",
            json={},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_very_large_price_is_accepted(self, client, admin_token):
        """There is no upper bound on price in the service; a very large float
        must be stored and returned faithfully without error.
        """
        resp = client.post(
            "/products/",
            json={"name": "Luxury Item", "price": 999_999.99},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201
        pid = resp.get_json()["id"]
        data = client.get(f"/products/{pid}").get_json()
        assert data["price"] == pytest.approx(999_999.99)

    def test_minimum_valid_price_just_above_zero(self, client, admin_token):
        """A very small positive price (e.g. 0.01) sits just above the
        strictly-positive lower bound and must be accepted.
        """
        resp = client.post(
            "/products/",
            json={"name": "Penny Item", "price": 0.01},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 201

    def test_boolean_false_as_stock_returns_422(self, client, admin_token):
        """``False`` is a subclass of ``int`` in Python; the validator must
        reject it for the ``stock`` field just as it rejects ``True``.
        """
        resp = client.post(
            "/products/",
            json={"name": "Test", "price": 5.0, "stock": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "stock" in resp.get_json().get("errors", {})

    def test_non_integer_product_id_in_url_returns_404(self, client):
        """Flask's ``<int:product_id>`` converter rejects non-numeric path
        segments; the request falls through to the global 404 handler.
        """
        resp = client.get("/products/notanumber")
        assert resp.status_code == 404
        assert "error" in resp.get_json()


# ===========================================================================
# PUT /products/<id>  — update product
# ===========================================================================

class TestUpdateProduct:
    """PUT /products/<id> — admin-only partial (PATCH-style) update.

    Only keys present in the JSON body are modified; absent keys retain
    their current value.  The response shape is ``{id, name, price}`` —
    ``stock`` is intentionally absent from the PUT response.
    """

    # ------------------------------------------------------------------
    # Happy paths
    # ------------------------------------------------------------------

    def test_full_update_all_fields_returns_200(self, client, sample_product, admin_token):
        resp = client.put(
            f"/products/{sample_product['id']}",
            json={"name": "Updated Widget", "price": 29.99, "stock": 100},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

    def test_response_contains_id_name_price(self, client, sample_product, admin_token):
        resp = client.put(
            f"/products/{sample_product['id']}",
            json={"name": "Renamed", "price": 5.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = resp.get_json()
        assert "id" in data
        assert "name" in data
        assert "price" in data

    def test_partial_update_name_only_leaves_price_unchanged(
        self, client, sample_product, admin_token
    ):
        original_price = sample_product["price"]
        resp = client.put(
            f"/products/{sample_product['id']}",
            json={"name": "New Name Only"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["name"] == "New Name Only"
        assert data["price"] == pytest.approx(original_price)

    def test_partial_update_price_only_leaves_name_unchanged(
        self, client, sample_product, admin_token
    ):
        original_name = sample_product["name"]
        resp = client.put(
            f"/products/{sample_product['id']}",
            json={"price": 99.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["name"] == original_name
        assert data["price"] == pytest.approx(99.0)

    def test_partial_update_stock_persists_correctly(
        self, client, sample_product, admin_token
    ):
        """Stock does not appear in the PUT response; verify via GET."""
        client.put(
            f"/products/{sample_product['id']}",
            json={"stock": 999},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        get = client.get(f"/products/{sample_product['id']}")
        assert get.get_json()["stock"] == 999

    def test_body_with_only_unknown_fields_is_a_no_op_returning_200(
        self, client, sample_product, admin_token
    ):
        """A JSON body whose keys are *all* unrecognised (not ``name``,
        ``price``, or ``stock``) passes ``require_json_body`` (non-empty dict)
        and the partial validator skips every key.  The service applies no
        changes and returns 200 with the original product data intact.
        """
        resp = client.put(
            f"/products/{sample_product['id']}",
            json={"colour": "red"},   # not a recognised product field
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["name"] == sample_product["name"]
        assert data["price"] == pytest.approx(sample_product["price"])

    def test_empty_json_object_returns_400(
        self, client, sample_product, admin_token
    ):
        """``require_json_body`` uses ``if not data`` to guard the endpoint;
        ``{}`` is falsy (``not {} == True``), so it is rejected with 400
        *before* any route or service logic runs — it is not a valid no-op.
        """
        resp = client.put(
            f"/products/{sample_product['id']}",
            json={},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_unknown_fields_in_body_are_silently_ignored(
        self, client, sample_product, admin_token
    ):
        resp = client.put(
            f"/products/{sample_product['id']}",
            json={"name": "Changed", "colour": "red"},  # "colour" is unknown
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["name"] == "Changed"

    def test_update_is_persistent_across_subsequent_gets(
        self, client, sample_product, admin_token
    ):
        client.put(
            f"/products/{sample_product['id']}",
            json={"name": "Persistent Name", "price": 1.23},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = client.get(f"/products/{sample_product['id']}").get_json()
        assert data["name"] == "Persistent Name"
        assert data["price"] == pytest.approx(1.23)

    # ------------------------------------------------------------------
    # Authentication / authorisation guard
    # ------------------------------------------------------------------

    def test_no_auth_header_returns_401(self, client, sample_product):
        resp = client.put(
            f"/products/{sample_product['id']}",
            json={"name": "X"},
        )
        assert resp.status_code == 401

    def test_regular_user_token_returns_403(
        self, client, sample_product, user_token
    ):
        resp = client.put(
            f"/products/{sample_product['id']}",
            json={"name": "X"},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 403

    # ------------------------------------------------------------------
    # Not found
    # ------------------------------------------------------------------

    def test_nonexistent_product_returns_404(self, client, admin_token):
        resp = client.put(
            "/products/99999",
            json={"name": "Ghost"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    # ------------------------------------------------------------------
    # Field validation
    # ------------------------------------------------------------------

    def test_empty_name_in_update_returns_422(self, client, sample_product, admin_token):
        resp = client.put(
            f"/products/{sample_product['id']}",
            json={"name": ""},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "name" in resp.get_json().get("errors", {})

    def test_negative_price_in_update_returns_422(
        self, client, sample_product, admin_token
    ):
        resp = client.put(
            f"/products/{sample_product['id']}",
            json={"price": -5.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "price" in resp.get_json().get("errors", {})

    def test_zero_price_in_update_returns_422(
        self, client, sample_product, admin_token
    ):
        resp = client.put(
            f"/products/{sample_product['id']}",
            json={"price": 0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "price" in resp.get_json().get("errors", {})

    def test_boolean_price_in_update_returns_422(
        self, client, sample_product, admin_token
    ):
        resp = client.put(
            f"/products/{sample_product['id']}",
            json={"price": True},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "price" in resp.get_json().get("errors", {})

    def test_negative_stock_in_update_returns_422(
        self, client, sample_product, admin_token
    ):
        resp = client.put(
            f"/products/{sample_product['id']}",
            json={"stock": -10},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "stock" in resp.get_json().get("errors", {})

    # ------------------------------------------------------------------
    # Malformed requests
    # ------------------------------------------------------------------

    def test_non_json_body_returns_400(self, client, sample_product, admin_token):
        resp = client.put(
            f"/products/{sample_product['id']}",
            data="name=x",
            content_type="text/plain",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_empty_body_content_type_json_returns_400(
        self, client, sample_product, admin_token
    ):
        resp = client.put(
            f"/products/{sample_product['id']}",
            data="",
            content_type="application/json",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_whitespace_only_name_in_update_returns_422(
        self, client, sample_product, admin_token
    ):
        """The validator strips the name before checking; a whitespace-only
        string collapses to ``""`` which is falsy → 422.
        """
        resp = client.put(
            f"/products/{sample_product['id']}",
            json={"name": "   "},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "name" in resp.get_json().get("errors", {})

    def test_boolean_true_as_stock_in_update_returns_422(
        self, client, sample_product, admin_token
    ):
        """``True`` is a bool subclass of int; the partial validator must
        reject it for ``stock`` even in an update context.
        """
        resp = client.put(
            f"/products/{sample_product['id']}",
            json={"stock": True},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "stock" in resp.get_json().get("errors", {})

    def test_boolean_false_as_stock_in_update_returns_422(
        self, client, sample_product, admin_token
    ):
        resp = client.put(
            f"/products/{sample_product['id']}",
            json={"stock": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "stock" in resp.get_json().get("errors", {})

    def test_string_price_in_update_returns_422(
        self, client, sample_product, admin_token
    ):
        resp = client.put(
            f"/products/{sample_product['id']}",
            json={"price": "free"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "price" in resp.get_json().get("errors", {})

    def test_float_stock_in_update_returns_422(
        self, client, sample_product, admin_token
    ):
        """Stock must be an integer; a float like 2.5 must be rejected."""
        resp = client.put(
            f"/products/{sample_product['id']}",
            json={"stock": 2.5},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "stock" in resp.get_json().get("errors", {})

    def test_multiple_invalid_fields_in_update_returns_all_errors(
        self, client, sample_product, admin_token
    ):
        """The partial validator accumulates errors for every present-but-
        invalid field; all of them should appear in a single 422 response.
        """
        resp = client.put(
            f"/products/{sample_product['id']}",
            json={"name": "", "price": -1.0, "stock": -5},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        errors = resp.get_json().get("errors", {})
        assert "name" in errors
        assert "price" in errors
        assert "stock" in errors

    def test_non_integer_product_id_in_url_returns_404(self, client, admin_token):
        """Flask's ``<int:product_id>`` converter rejects non-numeric path
        segments; the request falls through to the global 404 handler.
        """
        resp = client.put(
            "/products/notanumber",
            json={"name": "X"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404

    def test_zero_product_id_returns_404(self, client, admin_token):
        """PKs start at 1; product ID 0 should never exist."""
        resp = client.put(
            "/products/0",
            json={"name": "X"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404


# ===========================================================================
# POST /products/<id>/discount  — apply percentage discount
# ===========================================================================

class TestDiscountProduct:
    """POST /products/<id>/discount — admin-only percentage price reduction.

    The discount is applied as: ``new_price = round(price * (1 - d/100), 2)``
    Valid range: [0, 100].  bool values are explicitly rejected even though
    bool is a subclass of int/float in Python.
    The response key is ``new_price``, not ``price``.
    """

    # ------------------------------------------------------------------
    # Happy paths — correct discount arithmetic
    # ------------------------------------------------------------------

    def test_happy_path_returns_200(self, client, sample_product, admin_token):
        resp = client.post(
            f"/products/{sample_product['id']}/discount",
            json={"discount": 10},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200

    def test_response_contains_id_and_new_price(
        self, client, sample_product, admin_token
    ):
        resp = client.post(
            f"/products/{sample_product['id']}/discount",
            json={"discount": 10},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = resp.get_json()
        assert "id" in data
        assert "new_price" in data
        assert data["id"] == sample_product["id"]

    def test_discount_calculation_is_mathematically_correct(
        self, client, admin_token
    ):
        """Use a clean price of 100.00 to make the expected result exact."""
        create = client.post(
            "/products/",
            json={"name": "Hundred Dollar Item", "price": 100.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        pid = create.get_json()["id"]

        resp = client.post(
            f"/products/{pid}/discount",
            json={"discount": 25},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.get_json()["new_price"] == pytest.approx(75.0)

    def test_zero_percent_discount_leaves_price_unchanged(
        self, client, sample_product, admin_token
    ):
        resp = client.post(
            f"/products/{sample_product['id']}/discount",
            json={"discount": 0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["new_price"] == pytest.approx(sample_product["price"])

    def test_hundred_percent_discount_makes_price_zero(
        self, client, sample_product, admin_token
    ):
        resp = client.post(
            f"/products/{sample_product['id']}/discount",
            json={"discount": 100},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["new_price"] == pytest.approx(0.0)

    def test_float_discount_value_is_accepted(self, client, admin_token):
        """Fractional discounts like 12.5 % are valid."""
        create = client.post(
            "/products/",
            json={"name": "Float Discount", "price": 200.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        pid = create.get_json()["id"]
        resp = client.post(
            f"/products/{pid}/discount",
            json={"discount": 12.5},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["new_price"] == pytest.approx(175.0)

    def test_discount_is_persisted_in_the_database(
        self, client, admin_token
    ):
        """After applying the discount, a subsequent GET should reflect the
        reduced price.
        """
        create = client.post(
            "/products/",
            json={"name": "Persistence Check", "price": 50.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        pid = create.get_json()["id"]
        client.post(
            f"/products/{pid}/discount",
            json={"discount": 50},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = client.get(f"/products/{pid}").get_json()
        assert data["price"] == pytest.approx(25.0)

    def test_discount_result_is_rounded_to_two_decimal_places(
        self, client, admin_token
    ):
        """10 % of £9.99 = £0.999 → stored as £8.99 (price * 0.9 = 8.991)."""
        create = client.post(
            "/products/",
            json={"name": "Rounding Test", "price": 9.99},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        pid = create.get_json()["id"]
        resp = client.post(
            f"/products/{pid}/discount",
            json={"discount": 10},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        new_price = resp.get_json()["new_price"]
        # Value should be rounded to 2 decimal places.
        assert new_price == round(new_price, 2)

    # ------------------------------------------------------------------
    # Authentication / authorisation guard
    # ------------------------------------------------------------------

    def test_no_auth_header_returns_401(self, client, sample_product):
        resp = client.post(
            f"/products/{sample_product['id']}/discount",
            json={"discount": 10},
        )
        assert resp.status_code == 401

    def test_regular_user_token_returns_403(
        self, client, sample_product, user_token
    ):
        resp = client.post(
            f"/products/{sample_product['id']}/discount",
            json={"discount": 10},
            headers={"Authorization": f"Bearer {user_token}"},
        )
        assert resp.status_code == 403

    # ------------------------------------------------------------------
    # Not found
    # ------------------------------------------------------------------

    def test_nonexistent_product_returns_404(self, client, admin_token):
        resp = client.post(
            "/products/99999/discount",
            json={"discount": 10},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    # ------------------------------------------------------------------
    # Discount value validation
    # ------------------------------------------------------------------

    def test_discount_above_100_returns_422(self, client, sample_product, admin_token):
        resp = client.post(
            f"/products/{sample_product['id']}/discount",
            json={"discount": 101},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "error" in resp.get_json()

    def test_negative_discount_returns_422(self, client, sample_product, admin_token):
        resp = client.post(
            f"/products/{sample_product['id']}/discount",
            json={"discount": -1},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "error" in resp.get_json()

    def test_missing_discount_field_returns_422(
        self, client, sample_product, admin_token
    ):
        # Send a non-empty body whose keys don't include "discount"; this
        # passes ``require_json_body`` (dict is truthy) and then hits the
        # ``if discount is None`` guard in the route, which returns 422.
        resp = client.post(
            f"/products/{sample_product['id']}/discount",
            json={"other": "field"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422
        assert "error" in resp.get_json()

    def test_boolean_true_as_discount_returns_422(
        self, client, sample_product, admin_token
    ):
        """bool is a subclass of int in Python; the service must reject it."""
        resp = client.post(
            f"/products/{sample_product['id']}/discount",
            json={"discount": True},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422

    def test_boolean_false_as_discount_returns_422(
        self, client, sample_product, admin_token
    ):
        resp = client.post(
            f"/products/{sample_product['id']}/discount",
            json={"discount": False},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422

    def test_string_discount_returns_422(self, client, sample_product, admin_token):
        resp = client.post(
            f"/products/{sample_product['id']}/discount",
            json={"discount": "10%"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422

    def test_null_discount_returns_422(self, client, sample_product, admin_token):
        """JSON ``null`` maps to Python ``None``; the route checks for ``None``
        before calling the service, returning 422 directly.
        """
        resp = client.post(
            f"/products/{sample_product['id']}/discount",
            json={"discount": None},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 422

    # ------------------------------------------------------------------
    # Malformed requests
    # ------------------------------------------------------------------

    def test_non_json_body_returns_400(self, client, sample_product, admin_token):
        resp = client.post(
            f"/products/{sample_product['id']}/discount",
            data="discount=10",
            content_type="text/plain",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_empty_body_returns_400(self, client, sample_product, admin_token):
        resp = client.post(
            f"/products/{sample_product['id']}/discount",
            data="",
            content_type="application/json",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400

    def test_empty_json_object_returns_400(self, client, sample_product, admin_token):
        """``require_json_body`` rejects ``{}`` with 400 before the
        ``discount is None`` route-level check (which would yield 422) runs.
        """
        resp = client.post(
            f"/products/{sample_product['id']}/discount",
            json={},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_discount_stacks_cumulatively_on_repeated_calls(
        self, client, admin_token
    ):
        """Discount is applied to the *current* price each time it is called.
        50 % off $100.00 → $50.00; a second 50 % off $50.00 → $25.00.
        """
        create = client.post(
            "/products/",
            json={"name": "Compound Discount", "price": 100.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        pid = create.get_json()["id"]
        client.post(
            f"/products/{pid}/discount",
            json={"discount": 50},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        resp = client.post(
            f"/products/{pid}/discount",
            json={"discount": 50},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.get_json()["new_price"] == pytest.approx(25.0)

    def test_discount_exactly_at_boundary_100_leaves_price_at_zero(
        self, client, admin_token
    ):
        """100 % is the inclusive upper boundary; the resulting price must
        be 0.00 (not negative and not a validation error).
        """
        create = client.post(
            "/products/",
            json={"name": "Boundary 100", "price": 49.99},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        pid = create.get_json()["id"]
        resp = client.post(
            f"/products/{pid}/discount",
            json={"discount": 100},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["new_price"] == pytest.approx(0.0)

    def test_discount_exactly_at_boundary_0_does_not_change_price(
        self, client, admin_token
    ):
        """0 % is the inclusive lower boundary; the price must remain
        unchanged (not raise a validation error).
        """
        create = client.post(
            "/products/",
            json={"name": "Boundary 0", "price": 10.0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        pid = create.get_json()["id"]
        resp = client.post(
            f"/products/{pid}/discount",
            json={"discount": 0},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        assert resp.get_json()["new_price"] == pytest.approx(10.0)

    def test_non_integer_product_id_returns_404(self, client, admin_token):
        """Flask's ``<int:product_id>`` converter rejects non-numeric path
        segments; the global 404 handler fires.
        """
        resp = client.post(
            "/products/notanumber/discount",
            json={"discount": 10},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 404
        assert "error" in resp.get_json()

    def test_discount_response_contains_correct_id(
        self, client, sample_product, admin_token
    ):
        """The ``id`` in the discount response must match the product that
        was discounted — not a default value or a different product.
        """
        resp = client.post(
            f"/products/{sample_product['id']}/discount",
            json={"discount": 10},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.get_json()["id"] == sample_product["id"]


# ===========================================================================
# Flask global error handlers
# ===========================================================================

class TestGlobalErrorHandlers:
    """Verify that the centralised JSON error handlers in ``errors.py`` fire
    correctly for common HTTP errors, so clients always receive JSON — never
    an HTML Werkzeug debug page.
    """

    def test_unknown_route_returns_404_json(self, client):
        resp = client.get("/this/route/does/not/exist")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data is not None
        assert "error" in data

    def test_wrong_http_method_returns_405_json(self, client):
        """DELETE is not defined on ``/products/``; must yield 405 JSON."""
        resp = client.delete("/products/")
        assert resp.status_code == 405
        data = resp.get_json()
        assert data is not None
        assert "error" in data

    def test_patch_on_users_list_returns_405_json(self, client):
        """PATCH is not a registered method on ``/users/``."""
        resp = client.patch("/users/")
        assert resp.status_code == 405
        data = resp.get_json()
        assert data is not None
        assert "error" in data

    def test_404_response_is_valid_json_content_type(self, client):
        resp = client.get("/nonexistent")
        assert "application/json" in resp.content_type

    def test_405_response_is_valid_json_content_type(self, client):
        resp = client.delete("/products/")
        assert "application/json" in resp.content_type

    def test_put_on_users_list_returns_405_json(self, client):
        """PUT is not registered on ``/users/``; the centralised 405 handler
        must return JSON, not an HTML Werkzeug debug page.
        """
        resp = client.put("/users/")
        assert resp.status_code == 405
        data = resp.get_json()
        assert data is not None
        assert "error" in data

    def test_post_on_user_detail_returns_405_json(self, client):
        """POST is not registered on ``/users/<id>``; must yield JSON 405."""
        resp = client.post("/users/1")
        assert resp.status_code == 405
        assert "error" in resp.get_json()

    def test_deeply_nested_nonexistent_route_returns_404_json(self, client):
        """Deeply nested, unregistered URLs must still produce JSON 404."""
        resp = client.get("/products/999/nonexistent/nested/path")
        assert resp.status_code == 404
        data = resp.get_json()
        assert data is not None
        assert "error" in data

    def test_404_error_body_has_error_key_with_string_value(self, client):
        """The 404 body shape must be ``{"error": "<string>"}``; any client
        parsing ``data["error"]`` must receive a string, not ``None``.
        """
        resp = client.get("/does/not/exist")
        data = resp.get_json()
        assert isinstance(data.get("error"), str)
        assert len(data["error"]) > 0

    def test_405_error_body_has_error_key_with_string_value(self, client):
        resp = client.delete("/products/")
        data = resp.get_json()
        assert isinstance(data.get("error"), str)
        assert len(data["error"]) > 0
