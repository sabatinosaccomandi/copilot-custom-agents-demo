"""ORM model representing a registered user account."""
from __future__ import annotations

from ..db import db


class User(db.Model):
    """SQLAlchemy model for the ``user`` database table.

    Each row represents a single registered account.  Passwords are stored
    as bcrypt hashes; plain-text passwords are never persisted.

    Attributes:
        id (int): Auto-incremented primary key.
        username (str): Unique display name, 3–80 characters.
        email (str): Unique, lower-cased email address, up to 120 characters.
        password (str): Bcrypt password hash, up to 200 characters.
        role (str): Access level; either ``"user"`` (default) or ``"admin"``.
    """

    id = db.Column(db.Integer, primary_key=True)
    # unique=True prevents duplicate accounts and makes lookups unambiguous.
    username = db.Column(db.String(80), nullable=False, unique=True)
    email = db.Column(db.String(120), nullable=False, unique=True)
    # Stores a bcrypt hash, never a plain-text password.
    # 200 chars is sufficient for a bcrypt digest (60 chars) with room to grow.
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")

    def to_dict(self) -> dict:
        """Return a safe public representation of this user.

        The ``password`` field is intentionally omitted so that bcrypt
        hashes are never exposed through the API.

        Returns:
            A dictionary with the following keys:

            - ``"id"`` *(int)*: The user's primary key.
            - ``"username"`` *(str)*: The user's display name.
            - ``"email"`` *(str)*: The user's lower-cased email address.
            - ``"role"`` *(str)*: The user's access level (``"user"``
              or ``"admin"``).
        """
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
        }
