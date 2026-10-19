from typing import Optional


class AppError(Exception):
    """A business-rule failure. Services raise it; main.py turns it into a JSON response."""

    def __init__(self, status_code: int, detail: str, code: Optional[str] = None,
                 headers: Optional[dict] = None):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
        self.code = code
        self.headers = headers or {}
