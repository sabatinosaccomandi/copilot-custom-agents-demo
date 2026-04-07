"""Shared utilities for Flask route handlers.

Keep this module minimal — only helpers that are genuinely reused across
multiple blueprints belong here.  Per-blueprint helpers should stay local
to the relevant route module.
"""
from __future__ import annotations

from flask import request

from ..exceptions import BadRequestError


def require_json_body() -> dict:
    """Parse and return the JSON request body, or raise :exc:`BadRequestError`.

    This function eliminates the repeated ``get_json(silent=True)`` / 400-guard
    boilerplate that previously appeared in every write endpoint.  The raised
    :exc:`~app.exceptions.BadRequestError` propagates automatically to the
    centralised error handler in :mod:`app.errors`, so callers never need
    their own ``try/except``.

    The function enforces **two** distinct conditions:

    1. The request body must be present, non-empty, and valid JSON.
    2. The top-level JSON value must be a JSON *object* (Python ``dict``).
       Sending a JSON array (``[...]``), string, or other primitive as the
       root value would otherwise pass the truthiness check and later raise an
       ``AttributeError`` when route code calls ``.get()`` on the result.

    Returns:
        The parsed request body as a plain :class:`dict`.

    Raises:
        BadRequestError: When the request body is absent, empty, cannot be
            decoded as JSON, or is valid JSON but not an object.
            Response body: ``{"error": "Request body must be a JSON object"}``.

    Example::

        @bp.route("/", methods=["POST"])
        def create() -> tuple[Response, int]:
            data = require_json_body()          # raises 400 if body is missing
            item = some_service.create(data)
            return jsonify(item.to_dict()), 201
    """
    data = request.get_json(silent=True)
    # Check isinstance first: a non-dict truthy value (e.g. a JSON array)
    # would pass a plain ``if not data`` guard but would crash later when
    # route code calls ``.get()`` on it.  An empty dict ``{}`` is a falsy
    # dict, so ``not data`` catches it as a missing body — matching the
    # documented behaviour and the existing test coverage.
    if not isinstance(data, dict) or not data:
        raise BadRequestError("Request body must be a JSON object")
    return data
