"""User-related HTTP route handlers (Blueprint: ``users``).

This module defines all endpoints under the ``/users`` URL prefix:

- ``POST   /users/login``          – obtain a bearer token
- ``GET    /users/``               – list all users (auth required)
- ``GET    /users/<id>``           – fetch a single user (auth required)
- ``POST   /users/``               – register a new account
- ``DELETE /users/<id>``           – delete an account (auth required)
- ``GET    /users/search?q=``      – search users by username (auth required)

This module is intentionally thin: it handles HTTP-layer concerns only
(request parsing, response serialisation, auth decoration).  All business
logic lives in :mod:`app.user_service`.  Domain exceptions raised there
propagate to the centralised handlers in :mod:`app.errors` — no per-route
try/except boilerplate is needed.
"""
from __future__ import annotations

from flask import Blueprint, Response, g, jsonify, request

from .. import user_service
from ..auth import generate_token, require_auth
from ..extensions import limiter
from .utils import require_json_body

users_bp = Blueprint("users", __name__)


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------

@users_bp.route("/login", methods=["POST"])
@limiter.limit(
    "5 per minute",
    error_message="Too many login attempts — please wait before trying again.",
)
def login() -> tuple[Response, int]:
    """Exchange valid credentials for a signed bearer token.

    Rate-limited to **5 requests per minute per IP** to protect against
    brute-force and credential-stuffing attacks (OWASP A07).

    Returns:
        - ``200 OK``           – ``{"token": "<signed-token>"}``
        - ``400 Bad Request``  – body is not valid JSON or required fields
          are missing.
        - ``401 Unauthorized`` – credentials do not match any account.
        - ``429 Too Many Requests`` – rate limit exceeded.
    """
    data = require_json_body()

    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "username and password are required"}), 400

    user = user_service.authenticate_user(username, password)
    if user is None:
        # Deliberately vague – do not reveal whether the username exists.
        return jsonify({"error": "Invalid credentials"}), 401

    token = generate_token(user.id, user.role)
    return jsonify({"token": token}), 200


# ---------------------------------------------------------------------------
# User CRUD
# ---------------------------------------------------------------------------

@users_bp.route("/", methods=["GET"])
@require_auth
def get_users() -> Response:
    """List all registered user accounts.  Requires a valid bearer token.

    Returns:
        - ``200 OK``           – JSON array of ``{"id", "username", "email",
          "role"}`` objects (password hashes never included).
        - ``401 Unauthorized`` – no valid bearer token was provided.
    """
    users = user_service.get_all_users()
    return jsonify([u.to_dict() for u in users])


@users_bp.route("/<int:user_id>", methods=["GET"])
@require_auth
def get_user(user_id: int) -> Response:
    """Fetch a single user by their numeric ID.  Requires a valid bearer token.

    A ``NotFoundError`` raised by the service propagates to the centralised
    404 handler — no explicit guard is required here.

    Returns:
        - ``200 OK``           – ``{"id", "username", "email", "role"}``
        - ``401 Unauthorized`` – no valid bearer token was provided.
        - ``404 Not Found``    – no user with the given ID exists.
    """
    user = user_service.get_user_by_id(user_id)
    return jsonify(user.to_dict())


@users_bp.route("/", methods=["POST"])
def create_user() -> tuple[Response, int]:
    """Register a new user account.

    All validation, uniqueness checks, and password hashing are delegated to
    :func:`app.user_service.create_user`.  ``ValidationError`` and
    ``ConflictError`` bubble up to the centralised error handlers.

    Returns:
        - ``201 Created``             – ``{"id": <int>, "username": <str>}``
        - ``400 Bad Request``         – body is not valid JSON.
        - ``409 Conflict``            – username or email already registered.
        - ``422 Unprocessable Entity``– field validation failed;
          body: ``{"errors": {<field>: <message>}}``.
    """
    data = require_json_body()

    user = user_service.create_user(
        username=data.get("username", ""),
        email=data.get("email", ""),
        password=data.get("password", ""),
    )
    return jsonify({"id": user.id, "username": user.username}), 201


@users_bp.route("/<int:user_id>", methods=["DELETE"])
@require_auth
def delete_user(user_id: int) -> tuple[Response, int]:
    """Delete a user account.

    Access rules:

    - Admin users may delete **any** account.
    - Regular users may only delete **their own** account.

    A ``NotFoundError`` raised by the service propagates to the centralised
    404 handler.

    Returns:
        - ``200 OK``           – ``{"message": "Deleted"}``
        - ``401 Unauthorized`` – no valid bearer token was provided.
        - ``403 Forbidden``    – caller lacks permission to delete this account.
        - ``404 Not Found``    – no user with the given ID exists.
    """
    current = g.current_user
    if current["role"] != "admin" and current["user_id"] != user_id:
        return jsonify({"error": "Forbidden"}), 403

    user_service.delete_user(user_id)
    return jsonify({"message": "Deleted"}), 200


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

@users_bp.route("/search", methods=["GET"])
@require_auth
def search_users() -> Response:
    """Search users by username substring.  Requires authentication.

    Requiring auth prevents unauthenticated user enumeration.  Query length
    is capped in the service layer to limit DB load.

    Query Parameters:
        q (str): Substring to match against usernames (defaults to ``""``).

    Returns:
        - ``200 OK``           – JSON array of ``{"id", "username"}`` objects.
        - ``401 Unauthorized`` – no valid bearer token was provided.
    """
    q = request.args.get("q", "")
    results = user_service.search_users(q)
    return jsonify([{"id": u.id, "username": u.username} for u in results])

