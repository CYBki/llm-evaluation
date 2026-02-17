"""Domain exceptions — independent of HTTP layer."""


class AppError(Exception):
    """Base application error."""


class DuplicateEmailError(AppError):
    """Raised when a user tries to register with an existing email."""

    def __init__(self, email: str) -> None:
        self.email = email
        super().__init__(f"Email already registered: {email}")
