"""Flask route blueprints for the application.

This package groups all URL route handlers into focused blueprints:

- :mod:`app.routes.users`    – user registration, authentication, and management
- :mod:`app.routes.products` – product catalogue read/write endpoints

Blueprints are registered on the application in :func:`app.create_app`
with URL prefixes ``/users`` and ``/products`` respectively.
"""
