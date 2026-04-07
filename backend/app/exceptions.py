"""Domain-level exceptions raised by service functions.

Each exception carries:
- an HTTP ``status_code`` so the central error handler can map it to the
  correct HTTP response without any per-route try/except boilerplate.
- a ``to_response_body()`` method that returns the exact JSON-serialisable
  dict the client will receive, preserving the existing API contract:

  * Most errors   → ``{"error": "<message>"}``
  * Field errors  → ``{"errors": {"<field>": "<message>", ...}}``
"""
from __future__ import annotations


class AppError(Exception):
    """Base class for all application-domain errors.

    Subclasses should override :attr:`status_code` to reflect the
    appropriate HTTP status and may override
    :meth:`to_response_body` to customise the JSON response shape.

    Attributes:
        status_code: HTTP status code that will be used when this
            exception is converted to an HTTP response.  Defaults to
            ``500``.
        message: Human-readable error description set by ``__init__``.
    """

    status_code: int = 500

    def __init__(self, message: str) -> None:
        """Initialise the error with a human-readable message.

        Args:
            message: A concise description of what went wrong.  This
                string is forwarded to :class:`Exception` and stored on
                :attr:`message` for use by :meth:`to_response_body`.
        """
        super().__init__(message)
        self.message = message

    def to_response_body(self) -> dict:
        """Return a JSON-serialisable dictionary describing this error.

        Returns:
            A dictionary of the form ``{"error": "<message>"}`` that
            will be sent as the HTTP response body.
        """
        return {"error": self.message}


class BadRequestError(AppError):
    """Raised when the request is malformed or missing required data (HTTP 400).

    Examples: non-JSON body, missing required top-level field.
    """

    status_code = 400


class NotFoundError(AppError):
    """Raised when a requested resource does not exist (HTTP 404)."""

    status_code = 404


class ConflictError(AppError):
    """Raised on uniqueness or state-conflict violations (HTTP 409)."""

    status_code = 409


class ValidationError(AppError):
    """Raised when input data fails business-rule validation (HTTP 422).

    *errors* may be either:

    - a ``str``               — a single human-readable message
                                → ``{"error": "..."}``
    - a ``dict[str, str]``   — per-field messages collected during
                                structured validation
                                → ``{"errors": {"field": "msg", ...}}``
    """

    status_code = 422

    def __init__(self, errors: str | dict[str, str]) -> None:
        """Initialise the validation error with either a message or field errors.

        Args:
            errors: Either a plain string describing the overall validation
                failure, or a mapping of field names to per-field error
                messages collected during structured input validation.
                The type determines which response shape
                :meth:`to_response_body` will produce.
        """
        if isinstance(errors, str):
            super().__init__(errors)
            self.message: str = errors
            self.field_errors: dict[str, str] | None = None
        else:
            super().__init__("Validation failed")
            self.message = "Validation failed"
            self.field_errors: dict[str, str] | None = errors

    def to_response_body(self) -> dict:
        """Return the JSON-serialisable body for this validation error.

        The response shape varies depending on how this exception was
        constructed:

        - If ``field_errors`` is set (dict constructor), returns
          ``{"errors": {"<field>": "<message>", ...}}``.
        - Otherwise returns the standard ``{"error": "<message>"}``
          produced by the parent class.

        Returns:
            A dictionary suitable for direct JSON serialisation as the
            HTTP response body.
        """
        if self.field_errors is not None:
            return {"errors": self.field_errors}
        return {"error": self.message}
