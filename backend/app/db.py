"""SQLAlchemy database instance shared across the application.

The :data:`db` object is created here without being bound to a specific
Flask application.  Binding happens lazily inside :func:`app.create_app`
via ``db.init_app(app)``, which follows the Flask application-factory
pattern and allows the same extension instance to be reused across
multiple application instances (e.g. during testing).
"""
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
