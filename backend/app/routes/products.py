"""Product-catalogue HTTP route handlers (Blueprint: ``products``).

This module defines all endpoints under the ``/products`` URL prefix:

- ``GET    /products/``                      – list all products (public)
- ``GET    /products/<id>``                  – fetch a single product (public)
- ``POST   /products/``                      – create a product (admin only)
- ``PUT    /products/<id>``                  – update a product (admin only)
- ``POST   /products/<id>/discount``         – apply a discount (admin only)

This module is intentionally thin: it handles HTTP-layer concerns only
(request parsing, response serialisation, auth decoration).  All business
logic lives in :mod:`app.product_service`.  Domain exceptions raised there
propagate to the centralised handlers in :mod:`app.errors` — no per-route
try/except boilerplate is needed.

Read endpoints are intentionally unauthenticated so the product catalogue
can be browsed without an account.  Write endpoints are protected by the
:func:`app.auth.require_admin` decorator.
"""
from __future__ import annotations

from flask import Blueprint, Response, jsonify

from .. import product_service
from ..auth import require_admin
from .utils import require_json_body

products_bp = Blueprint("products", __name__)


# ---------------------------------------------------------------------------
# Public read endpoints (no auth required – product catalogue is public)
# ---------------------------------------------------------------------------

@products_bp.route("/", methods=["GET"])
def get_products() -> Response:
    """List all products in the catalogue.

    This endpoint is public and does not require authentication.

    Returns:
        ``200 OK`` – JSON array of ``{"id", "name", "price", "stock"}``
        objects representing every product in the database.
    """
    products = product_service.get_all_products()
    return jsonify([p.to_dict() for p in products])


@products_bp.route("/<int:product_id>", methods=["GET"])
def get_product(product_id: int) -> Response:
    """Fetch a single product by its numeric ID.

    This endpoint is public and does not require authentication.  A
    ``NotFoundError`` raised by the service propagates to the centralised
    404 handler — no explicit guard is required here.

    Returns:
        - ``200 OK``        – ``{"id", "name", "price", "stock"}``
        - ``404 Not Found`` – no product with the given ID exists.
    """
    product = product_service.get_product_by_id(product_id)
    return jsonify(product.to_dict())


# ---------------------------------------------------------------------------
# Write endpoints – admin only
# ---------------------------------------------------------------------------

@products_bp.route("/", methods=["POST"])
@require_admin
def create_product() -> tuple[Response, int]:
    """Create a new product in the catalogue.  Requires admin token.

    All field validation is delegated to
    :func:`app.product_service.create_product`.  ``ValidationError`` bubbles
    up to the centralised error handlers.

    Returns:
        - ``201 Created``              – ``{"id": <int>, "name": <str>}``
        - ``400 Bad Request``          – body is not valid JSON.
        - ``401 Unauthorized``         – no valid bearer token.
        - ``403 Forbidden``            – token does not have admin role.
        - ``422 Unprocessable Entity`` – field validation failed;
          body: ``{"errors": {<field>: <message>}}``.
    """
    data = require_json_body()
    product = product_service.create_product(data)
    return jsonify({"id": product.id, "name": product.name}), 201


@products_bp.route("/<int:product_id>", methods=["PUT"])
@require_admin
def update_product(product_id: int) -> Response:
    """Update one or more fields of an existing product.  Requires admin token.

    Only fields present in the request body are modified (PATCH-style
    semantics).  ``NotFoundError`` and ``ValidationError`` propagate to the
    centralised error handlers.

    Returns:
        - ``200 OK``                   – ``{"id", "name", "price"}``
        - ``400 Bad Request``          – body is not valid JSON.
        - ``401 Unauthorized``         – no valid bearer token.
        - ``403 Forbidden``            – token does not have admin role.
        - ``404 Not Found``            – no product with the given ID exists.
        - ``422 Unprocessable Entity`` – field validation failed.
    """
    data = require_json_body()
    product = product_service.update_product(product_id, data)
    return jsonify({"id": product.id, "name": product.name, "price": product.price})


@products_bp.route("/<int:product_id>/discount", methods=["POST"])
@require_admin
def discount_product(product_id: int) -> tuple[Response, int]:
    """Apply a percentage discount to a product's current price.  Requires admin token.

    ``NotFoundError`` and ``ValidationError`` (for invalid discount values)
    propagate to the centralised error handlers.

    Returns:
        - ``200 OK``                   – ``{"id": <int>, "new_price": <float>}``
        - ``400 Bad Request``          – body is not valid JSON.
        - ``401 Unauthorized``         – no valid bearer token.
        - ``403 Forbidden``            – token does not have admin role.
        - ``404 Not Found``            – no product with the given ID exists.
        - ``422 Unprocessable Entity`` – ``discount`` field is missing or
          invalid (must be a number in ``[0, 100]``).
    """
    data = require_json_body()

    discount = data.get("discount")
    if discount is None:
        return jsonify({"error": "discount field is required"}), 422

    product = product_service.apply_discount_to_product(product_id, discount)
    return jsonify({"id": product.id, "new_price": product.price}), 200

