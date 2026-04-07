"""ORM model representing a product in the catalogue."""
from __future__ import annotations

from ..db import db


class Product(db.Model):
    """SQLAlchemy model for the ``product`` database table.

    Each row represents a single item available in the product catalogue.

    Attributes:
        id (int): Auto-incremented primary key.
        name (str): Human-readable product name, up to 100 characters.
        price (float): Current sale price; must be a positive number.
        stock (int): Number of units currently available; defaults to ``0``.
    """

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    stock = db.Column(db.Integer, default=0)

    def to_dict(self) -> dict:
        """Return the full public representation of this product.

        Returns:
            A dictionary with the following keys:

            - ``"id"`` *(int)*: The product's primary key.
            - ``"name"`` *(str)*: The product's display name.
            - ``"price"`` *(float)*: The product's current sale price.
            - ``"stock"`` *(int)*: The number of units currently available.
        """
        return {
            "id": self.id,
            "name": self.name,
            "price": self.price,
            "stock": self.stock,
        }
