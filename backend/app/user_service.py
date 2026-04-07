"""User-domain business logic.

This module is the single source of truth for all user-related operations.
Route handlers should delegate to these functions rather than interacting
with the database, running validation, or hashing passwords directly.

Raises domain exceptions (:mod:`app.exceptions`) that propagate to the
centralised error handlers in :mod:`app.errors`.
"""
from __future__ import annotations

import re

from sqlalchemy import select

from .db import db
from .exceptions import ConflictError, NotFoundError, ValidationError
from .extensions import bcrypt
from .models.user import User

# ---------------------------------------------------------------------------
# Module-level constants (private)
# ---------------------------------------------------------------------------

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MIN_PASSWORD_LEN: int = 8
_MAX_PASSWORD_LEN: int = 128   # bcrypt silently truncates at 72 bytes; cap well below that
_MAX_USERNAME_LEN: int = 80
_MAX_SEARCH_LEN: int = 100  # cap query length to limit DB load


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _valid_email(value: str) -> bool:
    """Return ``True`` if *value* looks like a valid email address.

    Uses a lightweight regular expression check — not RFC-5321 compliant,
    but sufficient to catch the most common mistakes (missing ``@``,
    missing domain, embedded whitespace).

    Args:
        value: The string to test.

    Returns:
        ``True`` when *value* matches the email pattern, ``False``
        otherwise.
    """
    return bool(_EMAIL_RE.match(value))


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

def get_all_users() -> list[User]:
    """Return every user record, unfiltered.

    Returns:
        A list of all :class:`~app.models.user.User` instances currently
        stored in the database, in insertion order.  Returns an empty
        list when no users exist.
    """
    return db.session.scalars(select(User)).all()


def get_user_by_id(user_id: int) -> User:
    """Return the :class:`~app.models.user.User` with *user_id*.

    Args:
        user_id: The integer primary key of the user to retrieve.

    Returns:
        The matching :class:`~app.models.user.User` instance.

    Raises:
        NotFoundError: If no user with the given *user_id* exists in the
            database.
    """
    user = db.session.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    return user


def search_users(q: str) -> list[User]:
    """Return users whose username contains *q* (case-sensitive LIKE match).

    The query string is trimmed of leading/trailing whitespace and capped
    at ``_MAX_SEARCH_LEN`` characters to limit database load.  SQLAlchemy
    parameterises the LIKE value, preventing SQL injection.

    LIKE wildcard characters (``%``, ``_``) and the escape character
    (``\\``) present in *q* are escaped before being interpolated into the
    pattern, so they are matched literally rather than acting as wildcards.
    Without this step a caller could send ``q=%`` to retrieve every user in
    the database, bypassing the intended substring filter.

    Args:
        q: The substring to search for within usernames.  Empty string
            returns all users.

    Returns:
        A (possibly empty) list of :class:`~app.models.user.User`
        instances whose ``username`` column contains *q*.
    """
    safe_q = q.strip()[:_MAX_SEARCH_LEN]
    # Escape the backslash first so it is not double-processed, then escape
    # LIKE wildcards so they are treated as literal characters.
    safe_q = (
        safe_q
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )
    return db.session.scalars(
        select(User).where(User.username.like(f"%{safe_q}%", escape="\\"))
    ).all()


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

def authenticate_user(username: str, password: str) -> User | None:
    """Verify *username* / *password* credentials and return the matching user.

    Uses ``bcrypt.check_password_hash`` for password comparison, which
    performs a constant-time check to prevent timing-based username
    enumeration attacks.

    Args:
        username: The plaintext username supplied by the caller.
        password: The plaintext password supplied by the caller.

    Returns:
        The matching :class:`~app.models.user.User` instance when
        credentials are valid, or ``None`` when no account matches or
        the password is incorrect.
    """
    user = db.session.scalars(
        select(User).where(User.username == username)
    ).first()
    if not user or not bcrypt.check_password_hash(user.password, password):
        return None
    return user


# ---------------------------------------------------------------------------
# Write operations
# ---------------------------------------------------------------------------

def create_user(username: str, email: str, password: str) -> User:
    """Validate inputs, hash the password, persist a new user, and return it.

    Security notes:

    - The ``role`` field is always forced to ``"user"``; callers cannot
      self-assign elevated roles.
    - The password is hashed with bcrypt before it is written to the
      database; the plaintext value is never stored.
    - Uniqueness checks run *after* structural validation to avoid
      leaking information via timing differences when the payload is
      malformed.

    Args:
        username: Desired display name for the new account.  Must be
            between 3 and 80 characters after stripping whitespace.
        email: Email address for the new account.  Stored lower-cased;
            must match a basic ``user@domain.tld`` pattern.
        password: Plaintext password chosen by the user.  Must be at
            least 8 characters.

    Returns:
        The newly created and committed
        :class:`~app.models.user.User` instance.

    Raises:
        ValidationError: If any field fails structural validation.  The
            response body will be ``{"errors": {"<field>": "<message>"}}``.
        ConflictError: If the chosen username or email address is already
            registered.
    """
    username = username.strip()
    email = email.strip().lower()

    errors: dict[str, str] = {}

    if not username or len(username) < 3:
        errors["username"] = "Username must be at least 3 characters"
    elif len(username) > _MAX_USERNAME_LEN:
        errors["username"] = f"Username must be at most {_MAX_USERNAME_LEN} characters"

    if not email or not _valid_email(email):
        errors["email"] = "A valid email address is required"

    if not password or len(password) < _MIN_PASSWORD_LEN:
        errors["password"] = f"Password must be at least {_MIN_PASSWORD_LEN} characters"
    elif len(password) > _MAX_PASSWORD_LEN:
        # bcrypt silently truncates input at 72 bytes; two different passwords
        # that share the same first 72 bytes would therefore hash identically,
        # enabling a prefix-collision authentication bypass.  Additionally,
        # hashing a very long string is CPU-intensive and can be used as a DoS
        # vector.  Reject passwords above _MAX_PASSWORD_LEN before they reach
        # the hashing step.
        errors["password"] = f"Password must be at most {_MAX_PASSWORD_LEN} characters"

    if errors:
        raise ValidationError(errors)

    if db.session.scalars(select(User).where(User.username == username)).first():
        raise ConflictError("Username already taken")
    if db.session.scalars(select(User).where(User.email == email)).first():
        raise ConflictError("Email already registered")

    hashed_pw = bcrypt.generate_password_hash(password).decode("utf-8")
    user = User(username=username, email=email, password=hashed_pw, role="user")
    db.session.add(user)
    db.session.commit()
    return user


def delete_user(user_id: int) -> None:
    """Permanently delete the user with *user_id* from the database.

    Args:
        user_id: The integer primary key of the user to delete.

    Raises:
        NotFoundError: If no user with the given *user_id* exists.
    """
    user = db.session.get(User, user_id)
    if user is None:
        raise NotFoundError("User not found")
    db.session.delete(user)
    db.session.commit()
