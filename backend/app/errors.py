"""Centralised Flask error handlers.

All application-domain exceptions (subclasses of :class:`~app.exceptions.AppError`)
are caught here and turned into consistent JSON responses.  Standard HTTP
errors (404, 405, 500) are also handled so that *every* error response uses
JSON — never HTML — regardless of whether it was raised by application code
or by Flask/Werkzeug itself.

Route functions no longer need their own try/except blocks for domain
errors; they can simply call service functions and let exceptions propagate.
"""
from __future__ import annotations

from flask import Flask, Response, jsonify

from .exceptions import AppError


def register_error_handlers(app: Flask) -> None:
    """Attach centralised JSON error handlers to the Flask application.

    Registers handlers for:

    - All subclasses of :class:`~app.exceptions.AppError` (domain errors).
    - HTTP 404 Not Found.
    - HTTP 405 Method Not Allowed.
    - HTTP 500 Internal Server Error.

    After this function has been called, every error response produced by
    the application — whether raised by application code or by
    Flask/Werkzeug itself — will use JSON rather than the default HTML
    pages.

    Args:
        app: The :class:`flask.Flask` application instance to register the
            handlers on.  Typically called once inside
            :func:`app.create_app`.
    """

    @app.errorhandler(AppError)
    def handle_app_error(exc: AppError) -> tuple[Response, int]:
        """Translate any :class:`~app.exceptions.AppError` into a JSON response.

        Delegates body serialisation to the exception's own
        :meth:`~app.exceptions.AppError.to_response_body` method so that
        each subclass can control its response shape (e.g.
        :class:`~app.exceptions.ValidationError` returns a
        ``{"errors": {...}}`` dict).

        Args:
            exc: The caught domain exception instance.

        Returns:
            A ``(flask.Response, int)`` tuple whose status code is taken
            directly from ``exc.status_code``.
        """
        return jsonify(exc.to_response_body()), exc.status_code

    @app.errorhandler(404)
    def handle_404(exc: Exception) -> tuple[Response, int]:
        """Return a JSON 404 response for any unmatched URL.

        Args:
            exc: The underlying Werkzeug ``NotFound`` exception.

        Returns:
            ``({"error": "Not found"}, 404)``
        """
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def handle_405(exc: Exception) -> tuple[Response, int]:
        """Return a JSON 405 response when an HTTP method is not allowed.

        Args:
            exc: The underlying Werkzeug ``MethodNotAllowed`` exception.

        Returns:
            ``({"error": "Method not allowed"}, 405)``
        """
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def handle_500(exc: Exception) -> tuple[Response, int]:
        """Return a JSON 500 response for any unhandled server-side error.

        Args:
            exc: The unhandled exception that triggered the 500 response.

        Returns:
            ``({"error": "Internal server error"}, 500)``
        """
        return jsonify({"error": "Internal server error"}), 500
