"""Service-layer exceptions for user-facing workflow failures."""


class ServiceError(Exception):
    """Base exception for recoverable workflow errors."""

    flash_category = "danger"


class AuthenticationError(ServiceError):
    """The request could not be authenticated."""


class AuthorizationError(ServiceError):
    """The acting user is not allowed to perform the requested action."""


class ConflictError(ServiceError):
    """The requested action conflicts with the current model state."""

    flash_category = "warning"


class InformationalError(ServiceError):
    """The workflow cannot proceed, but the state is otherwise normal."""

    flash_category = "info"


class InvalidActionError(ServiceError):
    """The requested action itself is invalid."""
