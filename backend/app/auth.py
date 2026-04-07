"""
Token-based authentication helpers and Flask route decorators.

Tokens are signed with the application SECRET_KEY using itsdangerous
(ships with Flask), so no extra dependency is required.  Each token
encodes the user_id and role and expires after TOKEN_MAX_AGE_SECONDS.
"""
from __future__ import annotations

from functools import wraps
from typing import Any, Callable, TypeVar

from flask import Response, current_app, g, jsonify, request
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

TOKEN_MAX_AGE_SECONDS = 3600  # 1 hour
_SALT = "auth-token"

# TypeVar used to preserve the exact callable signature through auth decorators,
# so that type checkers understand decorated route functions retain their types.
_F = TypeVar("_F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def generate_token(user_id: int, role: str) -> str:
    """Generate a signed, time-limited authentication token.

    The token payload encodes the caller's *user_id* and *role* and is
    signed with the application ``SECRET_KEY`` using
    :class:`itsdangerous.URLSafeTimedSerializer`.  The token expires after
    :data:`TOKEN_MAX_AGE_SECONDS` seconds (default: 1 hour).

    Args:
        user_id: Primary-key identifier of the authenticated user.
        role: Access-level string for the user (e.g. ``"user"`` or
            ``"admin"``).

    Returns:
        A URL-safe, signed token string that can be sent to the client
        and later verified with :func:`verify_token`.
    """
    s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    return s.dumps({"user_id": user_id, "role": role}, salt=_SALT)


def verify_token(token: str) -> dict | None:
    """Verify a signed authentication token and return its decoded payload.

    The token's signature and expiry are both checked.  Any token that has
    been tampered with, has an invalid signature, or has exceeded
    :data:`TOKEN_MAX_AGE_SECONDS` is rejected.

    Args:
        token: A token string previously produced by :func:`generate_token`.

    Returns:
        A dictionary containing the decoded payload keys ``user_id`` and
        ``role`` when the token is valid, or ``None`` if the token is
        invalid, tampered-with, or expired.
    """
    s = URLSafeTimedSerializer(current_app.config["SECRET_KEY"])
    try:
        return s.loads(token, salt=_SALT, max_age=TOKEN_MAX_AGE_SECONDS)
    except (BadSignature, SignatureExpired):
        return None


# ---------------------------------------------------------------------------
# Internal helper shared by both decorators
# ---------------------------------------------------------------------------

def _load_user_from_header() -> tuple[dict[str, Any] | None, tuple[Response, int] | None]:
    """Read and verify the ``Authorization: Bearer <token>`` request header.

    This is an internal helper shared by :func:`require_auth` and
    :func:`require_admin` to avoid duplicating token-extraction logic.

    Returns:
        A 2-tuple ``(payload, None)`` when the header is present and the
        token passes verification, where *payload* is the decoded token
        dictionary (keys: ``user_id``, ``role``).

        A 2-tuple ``(None, error_response)`` when the header is missing,
        malformed, or contains an invalid/expired token, where
        *error_response* is a ``(flask.Response, int)`` tuple ready to be
        returned directly from a Flask view.
    """
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return None, (jsonify({"error": "Missing or invalid Authorization header"}), 401)

    token = auth_header[len("Bearer "):]
    payload = verify_token(token)
    if payload is None:
        return None, (jsonify({"error": "Invalid or expired token"}), 401)

    return payload, None


# ---------------------------------------------------------------------------
# Route decorators
# ---------------------------------------------------------------------------

def require_auth(f: _F) -> _F:
    """Decorator that enforces authentication on a Flask route.

    Reads the ``Authorization: Bearer <token>`` header, verifies the token
    with :func:`verify_token`, and stores the decoded payload in
    :data:`flask.g.current_user` for use by the wrapped view.

    Args:
        f: The Flask view function to protect.

    Returns:
        The wrapped view function that rejects unauthenticated callers
        with an HTTP ``401 Unauthorized`` response before the original
        function is invoked.
    """
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        """Verify the bearer token and delegate to the wrapped view.

        Args:
            *args: Positional arguments forwarded to the wrapped view.
            **kwargs: Keyword arguments forwarded to the wrapped view.

        Returns:
            The return value of the wrapped view function when the token
            is valid, or a ``(flask.Response, 401)`` tuple when
            authentication fails.
        """
        payload, err = _load_user_from_header()
        if err:
            return err
        g.current_user = payload
        return f(*args, **kwargs)
    return decorated  # type: ignore[return-value]


def require_admin(f: _F) -> _F:
    """Decorator that enforces admin-level authorisation on a Flask route.

    Extends :func:`require_auth` by additionally requiring the authenticated
    user's role to equal ``"admin"``.  The decoded token payload is stored in
    :data:`flask.g.current_user` before the wrapped view is called.

    Args:
        f: The Flask view function to protect.

    Returns:
        The wrapped view function that:

        - Returns HTTP ``401 Unauthorized`` when no valid token is supplied.
        - Returns HTTP ``403 Forbidden`` when the token is valid but the
          user does not hold the ``"admin"`` role.
        - Delegates to the original view function otherwise.
    """
    @wraps(f)
    def decorated(*args: Any, **kwargs: Any) -> Any:
        """Verify the bearer token, check for admin role, then delegate.

        Args:
            *args: Positional arguments forwarded to the wrapped view.
            **kwargs: Keyword arguments forwarded to the wrapped view.

        Returns:
            The return value of the wrapped view function when both
            authentication and authorisation succeed.  Returns a
            ``(flask.Response, 401)`` tuple on missing/invalid token,
            or a ``(flask.Response, 403)`` tuple when the user is
            authenticated but does not hold the ``"admin"`` role.
        """
        payload, err = _load_user_from_header()
        if err:
            return err
        g.current_user = payload
        if g.current_user.get("role") != "admin":
            return jsonify({"error": "Admin privileges required"}), 403
        return f(*args, **kwargs)
    return decorated  # type: ignore[return-value]
