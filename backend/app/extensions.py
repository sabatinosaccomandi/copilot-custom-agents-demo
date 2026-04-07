"""Flask extension singletons shared across the application.

Extensions are instantiated here without a bound Flask application and
are wired to a concrete app instance inside :func:`app.create_app` via
the ``init_app`` pattern.  Keeping all extension objects in one module
avoids circular imports between the factory, models, and routes.
"""
from flask_bcrypt import Bcrypt
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

# Single application-wide Bcrypt instance, initialised in create_app()
bcrypt = Bcrypt()

# Rate-limiting extension, initialised in create_app().
#
# Key function: ``get_remote_address`` limits by the connecting client's IP.
# PRODUCTION NOTE: When the API runs behind a reverse proxy (nginx, ALB, etc.)
# you must configure trusted proxies so that X-Forwarded-For cannot be spoofed.
# See https://flask-limiter.readthedocs.io/en/stable/#configuring-a-key-function
#
# Storage: the default in-memory backend is suitable for a single-process
# deployment only.  Set the ``RATELIMIT_STORAGE_URI`` config key to a Redis
# URL (e.g. "redis://localhost:6379/0") for multi-process / multi-worker
# deployments.
limiter = Limiter(key_func=get_remote_address)
