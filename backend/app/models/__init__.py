"""SQLAlchemy ORM models for the application.

This package re-exports all database models so they can be imported from a
single, predictable location::

    from app.models import User, Product

Every model is imported here so that SQLAlchemy's metadata registry is fully
populated before :func:`db.create_all` is called.  Without these imports,
tables that have never been referenced in the call-site module would be
silently omitted from the schema.

Models
------
User    – registered user accounts (:mod:`app.models.user`)
Product – catalogue items           (:mod:`app.models.product`)
"""

from .product import Product
from .user import User

__all__ = ["Product", "User"]

