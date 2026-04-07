"""Shared pytest configuration and fixtures for the Flask test suite.

All fixtures defined here are automatically available to every test module
in this package without explicit imports — pytest discovers conftest.py
files automatically.

Design decisions
----------------
* ``scope="function"`` on the ``app`` fixture ensures every test function
  receives a completely isolated in-memory SQLite database; no test can
  pollute another.
* ``StaticPool`` forces SQLAlchemy to reuse a single underlying connection
  for the lifetime of each test.  This is **required** for in-memory SQLite
  because a second connection would see an entirely different (empty)
  database — fixture setup writes would be invisible inside request handlers.
* ``BCRYPT_LOG_ROUNDS = 4`` drops bcrypt's work-factor from the default 12
  to 4, cutting per-hash time from ~300 ms to ~1 ms so the suite stays fast.
* Tokens are generated directly via :func:`app.auth.generate_token` rather
  than going through the login endpoint, so authentication tests can target
  the login route independently without coupling.
* ``admin_user`` is created by inserting a ``User`` row directly (bypassing
  ``user_service.create_user``) because the service intentionally forces
  ``role="user"`` on every registration — a key security invariant tested
  separately in ``test_users.py``.
"""
from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool

import app.product_service as product_service
import app.user_service as user_service
from app import create_app
from app.db import db as _db
from app.extensions import bcrypt
from app.models.user import User


# ---------------------------------------------------------------------------
# Test configuration
# ---------------------------------------------------------------------------

class TestConfig:
    """Minimal Flask configuration for the isolated test environment.

    Every attribute must be uppercase for ``app.config.from_object`` to pick
    it up.  Values are hardcoded (no ``os.environ`` reads) so tests are fully
    reproducible in any environment.
    """

    TESTING = True

    # Fixed secret so token generation is deterministic across test runs.
    # Long enough to pass the _MIN_SECRET_KEY_LEN >= 32 startup guard in
    # app/__init__.py, and distinct from every value in _KNOWN_INSECURE_DEFAULTS.
    SECRET_KEY: str = "test-secret-key-for-pytest-only-do-not-use-in-prod"

    # In-memory SQLite — never touches the production demo.db file.
    SQLALCHEMY_DATABASE_URI: str = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False

    # StaticPool: reuse a single connection so data written by fixtures
    # (outside a request context) is visible inside request handlers.
    SQLALCHEMY_ENGINE_OPTIONS: dict = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }

    # 4 rounds of bcrypt keeps hashing to ~1 ms per call during tests.
    BCRYPT_LOG_ROUNDS: int = 4

    # Disable Flask-Limiter during tests so that repeated login calls in the
    # test suite are never throttled by the 5-per-minute login rate limit.
    RATELIMIT_ENABLED: bool = False


# ---------------------------------------------------------------------------
# Core infrastructure fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="function")
def app():
    """Create a fully-wired Flask application backed by a fresh in-memory DB.

    Lifecycle
    ---------
    1. Build app from :class:`TestConfig`.
    2. Push an application context (required for db and bcrypt operations in
       other fixtures and for ``generate_token`` which calls ``current_app``).
    3. Create all tables.
    4. *yield* the app to the test.
    5. Drop all tables and remove the scoped session on teardown.
    """
    flask_app = create_app(TestConfig)
    with flask_app.app_context():
        _db.create_all()
        yield flask_app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):  # noqa: F811  (shadows the `app` parameter intentionally)
    """Return a :class:`flask.testing.FlaskClient` bound to the test app."""
    return app.test_client()


# ---------------------------------------------------------------------------
# User fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def regular_user(app):
    """Persist a ``role="user"`` account and return ``(user_dict, password)``.

    ``user_service.create_user`` is used deliberately so that the bcrypt
    hashing and validation code paths are exercised the same way production
    code exercises them.

    Returns
    -------
    tuple[dict, str]
        ``user_dict`` contains ``id``, ``username``, ``email``, ``role``.
        The second element is the plain-text password for login tests.
    """
    user = user_service.create_user(
        username="regularuser",
        email="regular@example.com",
        password="password123",
    )
    return (
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
        },
        "password123",
    )


@pytest.fixture
def admin_user(app):
    """Persist a ``role="admin"`` account and return ``(user_dict, password)``.

    The ORM is used directly because ``user_service.create_user`` always
    forces ``role="user"`` — which is the correct production behaviour and is
    tested explicitly in ``TestUserRegistration``.

    Returns
    -------
    tuple[dict, str]
        Same shape as :func:`regular_user`.
    """
    hashed_pw = bcrypt.generate_password_hash("adminpass123").decode("utf-8")
    user = User(
        username="adminuser",
        email="admin@example.com",
        password=hashed_pw,
        role="admin",
    )
    _db.session.add(user)
    _db.session.commit()
    return (
        {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
        },
        "adminpass123",
    )


@pytest.fixture
def user_token(app, regular_user):
    """Return a signed bearer token valid for the regular user.

    Token is generated directly (not via the login endpoint) so that
    ``TestUserLogin`` tests can target that route independently.
    """
    from app.auth import generate_token  # import inside fixture: current_app must be active

    user_dict, _ = regular_user
    return generate_token(user_dict["id"], user_dict["role"])


@pytest.fixture
def admin_token(app, admin_user):
    """Return a signed bearer token valid for the admin user."""
    from app.auth import generate_token

    user_dict, _ = admin_user
    return generate_token(user_dict["id"], user_dict["role"])


# ---------------------------------------------------------------------------
# Product fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_product(app):
    """Persist a sample product and return its full ``dict`` representation.

    Uses ``product_service.create_product`` so all validation logic is
    exercised.  The dict mirrors :meth:`Product.to_dict` output:
    ``{id, name, price, stock}``.
    """
    product = product_service.create_product(
        {"name": "Test Widget", "price": 19.99, "stock": 50}
    )
    return {
        "id": product.id,
        "name": product.name,
        "price": product.price,
        "stock": product.stock,
    }
