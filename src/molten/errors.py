"""Moltbook API errors."""


class MoltenError(Exception):
    """Base error for all Molten SDK exceptions."""


class AuthenticationError(MoltenError):
    """Invalid or missing API key."""


class RateLimitError(MoltenError):
    """Rate limit exceeded."""

    def __init__(self, retry_after: int, message: str = "Rate limit exceeded"):
        self.retry_after = retry_after
        super().__init__(f"{message} — retry after {retry_after}s")


class NotFoundError(MoltenError):
    """Resource not found."""


class ValidationError(MoltenError):
    """Request validation failed."""


class ApiError(MoltenError):
    """Generic API error."""

    def __init__(self, status_code: int, message: str, hint: str | None = None):
        self.status_code = status_code
        self.hint = hint
        super().__init__(f"[{status_code}] {message}" + (f" ({hint})" if hint else ""))
