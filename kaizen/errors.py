from __future__ import annotations

from typing import Any


class KaizenError(Exception):
    """Base exception for Kaizen SDK."""

    def __init__(
        self,
        message: str,
        status: int | None = None,
        code: str | None = None,
        request_id: str | None = None,
        data: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.status = status
        self.code = code
        self.request_id = request_id
        # Decoded JSON body for error responses (>=400). Lets callers read
        # typed body fields like {status, triggeredBy} on 429 dropped or
        # {status} on 409 stale without a separate decode.
        self.data = data or {}


class KaizenAuthError(KaizenError):
    """Authentication error."""

    def __init__(
        self,
        message: str = "Invalid or missing API key",
        request_id: str | None = None,
        data: dict[str, Any] | None = None,
    ):
        super().__init__(message, 401, "AUTH_ERROR", request_id=request_id, data=data)


class KaizenRateLimitError(KaizenError):
    """Rate limit exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
        request_id: str | None = None,
        data: dict[str, Any] | None = None,
    ):
        super().__init__(message, 429, "RATE_LIMIT", request_id=request_id, data=data)
        self.retry_after = retry_after


class KaizenValidationError(KaizenError):
    """Validation error for SDK inputs."""

    def __init__(self, message: str, field: str | None = None, request_id: str | None = None):
        super().__init__(message, 400, "VALIDATION_ERROR", request_id=request_id)
        self.field = field
