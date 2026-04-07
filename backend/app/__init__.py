"""Flask application factory and top-level package initialiser.

This module exposes :func:`create_app`, the single entry point used to
construct and configure a fully-wired Flask application instance.  The
factory pattern makes it straightforward to create multiple isolated
instances during testing without relying on a module-level global.

Configuration is read from :class:`app.config.Config`, which in turn reads
environment variables (see ``.env.example``).  Calling ``load_dotenv()``
before the factory runs ensures a local ``.env`` file is honoured in
development without affecting production deployments.
"""
from dotenv import load_dotenv
from flask import Flask, Response

from .config import Config
from .db import db
from .errors import register_error_handlers
from .extensions import bcrypt, limiter

# Load variables from a .env file when present (development convenience).
# In production, environment variables should be injected by the platform.
load_dotenv()

# ---------------------------------------------------------------------------
# Startup security constants
# ---------------------------------------------------------------------------

# Minimum acceptable byte-length for SECRET_KEY.  A 32-character hex string
# (produced by ``secrets.token_hex(32)``) gives 256 bits of entropy.
_MIN_SECRET_KEY_LEN: int = 32

# Reject any key that matches one of these known-insecure values even if the
# caller explicitly passed them via the environment variable.
_KNOWN_INSECURE_DEFAULTS: frozenset[str] = frozenset({
    "",
    "hardcoded-secret-123",          # previous insecure fallback
    "replace-with-a-long-random-secret-min-32-chars",  # .env.example placeholder
})


def _validate_secret_key(app: Flask) -> None:
    """Raise :exc:`ValueError` at startup when ``SECRET_KEY`` is unsafe.

    This guard runs once inside :func:`create_app`, before any extension is
    initialised or any request is served.  It prevents the application from
    booting with a key that would allow an attacker to forge authentication
    tokens.

    Checks performed:

    1. The key must not be the empty string or a known placeholder value.
    2. The key must be at least :data:`_MIN_SECRET_KEY_LEN` characters long.

    The check is intentionally *not* skipped for ``TESTING`` configs because
    the test suite supplies its own sufficiently strong key
    (``"test-secret-key-for-pytest-only-do-not-use-in-prod"``), so the guard
    passes without modification.

    Args:
        app: The configured Flask application instance.

    Raises:
        ValueError: When ``SECRET_KEY`` is absent, matches a known-insecure
            default, or is shorter than :data:`_MIN_SECRET_KEY_LEN`
            characters.
    """
    key: str = app.config.get("SECRET_KEY", "")
    if not key or key in _KNOWN_INSECURE_DEFAULTS or len(key) < _MIN_SECRET_KEY_LEN:
        raise ValueError(
            f"SECRET_KEY must be set to a cryptographically secure random string "
            f"of at least {_MIN_SECRET_KEY_LEN} characters. "
            'Generate one with: python -c "import secrets; print(secrets.token_hex(32))"'
        )


def create_app(config_class: type = Config) -> Flask:
    """Create and configure the Flask application instance.

    The factory performs the following steps in order:

    1. Loads configuration from *config_class* (defaults to
       :class:`~app.config.Config`).
    2. Validates that ``SECRET_KEY`` is cryptographically strong.
    3. Initialises SQLAlchemy, Flask-Bcrypt, and Flask-Limiter extensions.
    4. Registers the ``users`` and ``products`` blueprints.
    5. Attaches centralised JSON error handlers.
    6. Registers an ``after_request`` hook that appends security headers to
       every response.
    7. Creates all database tables that do not yet exist.

    Args:
        config_class: A configuration class whose attributes are loaded into
            ``app.config``.  Override in tests to inject isolated settings.

    Returns:
        A fully configured :class:`flask.Flask` application ready to serve
        requests or be used in tests.

    Raises:
        ValueError: If ``SECRET_KEY`` is absent, matches a known-insecure
            value, or is shorter than :data:`_MIN_SECRET_KEY_LEN` characters.
    """
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Refuse to start with an insecure signing key.
    _validate_secret_key(app)

    db.init_app(app)
    bcrypt.init_app(app)
    limiter.init_app(app)

    from .routes.users import users_bp
    from .routes.products import products_bp

    app.register_blueprint(users_bp, url_prefix="/users")
    app.register_blueprint(products_bp, url_prefix="/products")

    register_error_handlers(app)

    @app.after_request
    def add_security_headers(response: Response) -> Response:
        """Append security headers to every outgoing HTTP response.

        Applied at the application level so all blueprints, routes, and error
        handlers benefit automatically.

        Headers set:

        - ``X-Content-Type-Options: nosniff`` — prevents browsers from
          MIME-sniffing the declared Content-Type (mitigates content-injection
          attacks).
        - ``X-Frame-Options: DENY`` — disallows embedding in ``<iframe>``
          elements, protecting against clickjacking.
        - ``Cache-Control: no-store`` — instructs clients and intermediaries
          never to cache responses; protects sensitive data (tokens, PII) from
          being stored in browser or proxy caches.
        - ``Referrer-Policy: strict-origin-when-cross-origin`` — limits the
          ``Referer`` header to the origin (not full path) for cross-origin
          requests, reducing information leakage.

        ``setdefault`` is used so that individual routes can still override a
        specific header when needed without being silently clobbered.

        Args:
            response: The outgoing :class:`flask.Response` object.

        Returns:
            The same response object, with security headers attached.
        """
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return response

    with app.app_context():
        db.create_all()

    return app
