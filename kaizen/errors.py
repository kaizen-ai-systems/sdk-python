from __future__ import annotations


class KaizenError(Exception):
    """Base exception for Kaizen SDK."""

    def __init__(
        self,
        message: str,
        status: int | None = None,
        code: str | None = None,
        request_id: str | None = None,
    ):
        super().__init__(message)
        self.status = status
        self.code = code
        self.request_id = request_id


class KaizenAuthError(KaizenError):
    """Authentication error."""

    def __init__(self, message: str = "Invalid or missing API key", request_id: str | None = None):
        super().__init__(message, 401, "AUTH_ERROR", request_id=request_id)


class KaizenRateLimitError(KaizenError):
    """Rate limit exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int | None = None,
        request_id: str | None = None,
    ):
        super().__init__(message, 429, "RATE_LIMIT", request_id=request_id)
        self.retry_after = retry_after


class KaizenValidationError(KaizenError):
    """Validation error for SDK inputs."""

    def __init__(self, message: str, field: str | None = None, request_id: str | None = None):
        super().__init__(message, 400, "VALIDATION_ERROR", request_id=request_id)
        self.field = field
