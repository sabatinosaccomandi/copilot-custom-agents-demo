"""Product-domain business logic.

This module is the single source of truth for all product-related operations.
Route handlers should delegate to these functions rather than interacting
with the database, running field validation, or computing discounts directly.

Raises domain exceptions (:mod:`app.exceptions`) that propagate to the
centralised error handlers in :mod:`app.errors`.
"""
from __future__ import annotations

from sqlalchemy import select

from .db import db
from .exceptions import NotFoundError, ValidationError
from .models.product import Product

# ---------------------------------------------------------------------------
# Module-level constants (private)
# ---------------------------------------------------------------------------

_MAX_NAME_LEN: int = 100


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _validate_product_fields(data: dict, *, partial: bool = False) -> dict[str, str]:
    """Validate product fields and return a mapping of field names to error messages.

    When *partial* is ``True``, only keys that are present in *data* are
    validated — this enables PATCH-style PUT updates where omitted fields
    retain their current database values.

    Args:
        data: A dictionary of product fields to validate.  Expected keys
            are ``"name"``, ``"price"``, and optionally ``"stock"``.
        partial: When ``True``, silently skips validation for any key
            that is absent from *data*.  Defaults to ``False``, meaning
            all required fields are validated unconditionally.

    Returns:
        A dictionary mapping each invalid field name to a human-readable
        error message.  Returns an empty dictionary when all provided
        fields are valid.
    """
    errors: dict[str, str] = {}

    if not partial or "name" in data:
        name = data.get("name")
        if not isinstance(name, str) or not name.strip():
            errors["name"] = "name must be a non-empty string"
        elif len(name.strip()) > _MAX_NAME_LEN:
            errors["name"] = f"name must be at most {_MAX_NAME_LEN} characters"

    if not partial or "price" in data:
        price = data.get("price")
        # bool is a subclass of int/float in Python — reject it explicitly.
        if not isinstance(price, (int, float)) or isinstance(price, bool) or price <= 0:
            errors["price"] = "price must be a positive number"

    if not partial or "stock" in data:
        stock = data.get("stock")
        if stock is not None:
            if isinstance(stock, bool) or not isinstance(stock, int) or stock < 0:
                errors["stock"] = "stock must be a non-negative integer"

    return errors


def _compute_discounted_price(price: float, discount: float) -> float:
    """Return *price* reduced by *discount* percent, rounded to 2 decimal places.

    Args:
        price: The original price to discount.  Must be a positive number
            (enforcement is the caller's responsibility).
        discount: The percentage to deduct from *price*.  Must be a
            numeric value in the inclusive range ``[0, 100]``.

    Returns:
        The discounted price rounded to two decimal places.

    Raises:
        ValidationError: If *discount* is not a numeric type (booleans are
            explicitly rejected), or if the value falls outside ``[0, 100]``.
    """
    if not isinstance(discount, (int, float)) or isinstance(discount, bool):
        raise ValidationError("discount must be a number")
    if not (0 <= discount <= 100):
        raise ValidationError(f"discount must be between 0 and 100, got {discount}")
    return round(price * (1 - discount / 100), 2)


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

def get_all_products() -> list[Product]:
    """Return every product record, unfiltered.

    Returns:
        A list of all :class:`~app.models.product.Product` instances
        currently stored in the database.  Returns an empty list when
        no products exist.
    """
    return db.session.scalars(select(Product)).all()


def get_product_by_id(product_id: int) -> Product:
    """Return the :class:`~app.models.product.Product` with *product_id*.

    Args:
        product_id: The integer primary key of the product to retrieve.

    Returns:
        The matching :class:`~app.models.product.Product` instance.

    Raises:
        NotFoundError: If no product with the given *product_id* exists
            in the database.
    """
    product = db.session.get(Product, product_id)
    if product is None:
        raise NotFoundError("Product not found")
    return product


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

def create_product(data: dict) -> Product:
    """Validate *data*, persist a new product, and return it.

    Args:
        data: A dictionary containing the product fields.  Expected keys:

            - ``"name"`` *(str, required)*: Non-empty string, max 100 chars.
            - ``"price"`` *(float, required)*: Positive number.
            - ``"stock"`` *(int, optional)*: Non-negative integer; defaults
              to ``0`` when omitted.

    Returns:
        The newly created and committed
        :class:`~app.models.product.Product` instance.

    Raises:
        ValidationError: If any field fails validation.  The response
            body will be ``{"errors": {"<field>": "<message>"}}``.
    """
    errors = _validate_product_fields(data)
    if errors:
        raise ValidationError(errors)

    product = Product(
        name=data["name"].strip(),
        price=float(data["price"]),
        stock=int(data.get("stock", 0)),
    )
    db.session.add(product)
    db.session.commit()
    return product


def update_product(product_id: int, data: dict) -> Product:
    """Apply a partial update to the product with *product_id* and return it.

    Only keys present in *data* are updated (PATCH-style PUT semantics),
    so callers may send any non-empty subset of ``"name"``, ``"price"``,
    and ``"stock"``.

    Args:
        product_id: The integer primary key of the product to update.
        data: A dictionary containing one or more of the following keys:

            - ``"name"`` *(str)*: New product name; max 100 characters.
            - ``"price"`` *(float)*: New positive price.
            - ``"stock"`` *(int)*: New non-negative stock count.

    Returns:
        The updated and committed
        :class:`~app.models.product.Product` instance.

    Raises:
        NotFoundError: If no product with the given *product_id* exists.
        ValidationError: If any provided field fails validation.
    """
    product = db.session.get(Product, product_id)
    if product is None:
        raise NotFoundError("Product not found")

    errors = _validate_product_fields(data, partial=True)
    if errors:
        raise ValidationError(errors)

    if "name" in data:
        product.name = data["name"].strip()
    if "price" in data:
        product.price = float(data["price"])
    if "stock" in data:
        product.stock = int(data["stock"])

    db.session.commit()
    return product


def apply_discount_to_product(product_id: int, discount: float) -> Product:
    """Apply a percentage discount to a product's current price and persist it.

    Delegates the price computation to
    :func:`_compute_discounted_price`, which rounds the result to two
    decimal places.

    Args:
        product_id: The integer primary key of the product to discount.
        discount: The percentage to deduct from the current price.  Must
            be a numeric value in the inclusive range ``[0, 100]``.

    Returns:
        The updated and committed
        :class:`~app.models.product.Product` instance with the new
        discounted price applied.

    Raises:
        NotFoundError: If no product with the given *product_id* exists.
        ValidationError: If *discount* is not a valid number in
            ``[0, 100]``.
    """
    product = db.session.get(Product, product_id)
    if product is None:
        raise NotFoundError("Product not found")

    product.price = _compute_discounted_price(product.price, discount)
    db.session.commit()
    return product
