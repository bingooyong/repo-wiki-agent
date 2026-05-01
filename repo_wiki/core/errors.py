from __future__ import annotations

from enum import Enum


class ErrorCategory(str, Enum):
    BOOTSTRAP = "bootstrap"
    CONFIG = "config"
    SECURITY = "security"
    SCANNER = "scanner"
    VALIDATION = "validation"
    IO = "io"
    UNKNOWN = "unknown"


class RepoWikiError(Exception):
    def __init__(self, message: str, category: ErrorCategory, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.category = category
        self.details = details or {}

    def to_dict(self) -> dict:
        return {
            "message": self.message,
            "category": self.category.value,
            "details": self.details,
        }
