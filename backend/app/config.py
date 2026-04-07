"""Application configuration.

Settings are read from environment variables so that secrets are never
committed to source control.  Sensible defaults are provided for local
development — production deployments *must* override ``SECRET_KEY`` and
``DATABASE_URL`` via the environment (or a ``.env`` file; see
``.env.example``).
"""
from __future__ import annotations

import os


class Config:
    """Default configuration consumed by :func:`app.create_app`.

    All settings can be overridden by setting the corresponding
    environment variable before the application starts, or by supplying
    values in a ``.env`` file (see ``.env.example``).

    Attributes:
        SECRET_KEY: Cryptographic signing key used by itsdangerous to
            sign authentication tokens.  **Must** be set to a long
            random string in production via the ``SECRET_KEY``
            environment variable.  There is deliberately **no** insecure
            fallback value: the application will refuse to start if this
            variable is absent or too short (see :func:`app._validate_secret_key`).
        SQLALCHEMY_DATABASE_URI: SQLAlchemy connection string.  Defaults
            to a local SQLite file (``sqlite:///demo.db``).  Override
            with the ``DATABASE_URL`` environment variable to point at a
            production database such as PostgreSQL.
        SQLALCHEMY_TRACK_MODIFICATIONS: Disables SQLAlchemy's
            modification-tracking signal system.  Kept ``False`` to
            avoid unnecessary overhead; the application does not use
            these signals.
    """

    # ⚠️  SECRET_KEY has NO insecure fallback.  Set it via the environment
    # variable before starting the application (see .env.example).
    # Generate a secure value with:
    #   python -c "import secrets; print(secrets.token_hex(32))"
    # The startup guard in create_app() will raise ValueError and refuse to
    # boot if this is absent, empty, or shorter than 32 characters.
    SECRET_KEY: str = os.environ.get("SECRET_KEY", "")

    SQLALCHEMY_DATABASE_URI: str = os.environ.get("DATABASE_URL", "sqlite:///demo.db")

    # Disable the SQLAlchemy modification-tracking overhead; we don't use it.
    SQLALCHEMY_TRACK_MODIFICATIONS: bool = False
