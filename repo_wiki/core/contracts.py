from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class RepositoryInfo(BaseModel):
    name: str
    root_path: str
    language: str = "unknown"
    framework: str = "unknown"
    package_manager: str = "unknown"
    entry_points: list[str] = Field(default_factory=list)
    key_directories: list[str] = Field(default_factory=list)


class Module(BaseModel):
    name: str
    path: str
    responsibility: str
    exports: list[str] = Field(default_factory=list)
    depends_on: list[str] = Field(default_factory=list)
    depended_by: list[str] = Field(default_factory=list)
    interfaces: list[str] = Field(default_factory=list)
    data_models: list[str] = Field(default_factory=list)
    owner: str = "unknown"
    doc_path: str
    # Business domain classification (added in Phase 06)
    domain: str = "unknown"  # High-level business domain (e.g., 'core-platform', 'ai-services', 'frontend')
    service_family: str = "unknown"  # Service family within domain (e.g., 'python-backend', 'javascript-frontend')
    runtime_role: str = "unknown"  # Runtime role (e.g., 'api-server', 'worker', 'data-pipeline', 'tooling')
    domain_confidence: float = 0.0  # Classification confidence 0.0-1.0
    domain_classification_reason: str = ""  # Human-readable reason for classification


class Endpoint(BaseModel):
    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"]
    path: str
    module: str
    handler: str
    file_path: str
    # Enriched metadata (Phase 25)
    service_family: str = "unknown"  # Service family (e.g., 'python-backend', 'typescript-frontend')
    domain: str = "unknown"  # Business domain (e.g., 'core-platform', 'ai-services')
    runtime_role: str = "unknown"  # Runtime role (e.g., 'api-server', 'worker')
    auth_type: str = "unknown"  # Authentication type: 'bearer', 'none', 'api-key', 'oauth'
    auth_required: bool = False  # Whether auth is required
    request_body: bool = False  # Whether endpoint accepts request body
    response_type: str = "json"  # Response content type
    error_codes: list[int] = Field(default_factory=list)  # Common error codes
    line_number: int = 0  # Handler line citation (1-based)
    line_end: int = 0  # Handler end line for span citation


class DataModel(BaseModel):
    name: str
    type: str
    module: str
    file_path: str


class RepositoryStats(BaseModel):
    total_files: int = 0
    scanned_files: int = 0
    skipped_files: int = 0
    module_count: int = 0
    endpoint_count: int = 0
    data_model_count: int = 0


class VerifyResult(BaseModel):
    status: Literal["ok", "warning", "error"]
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checked_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ImpactSet(BaseModel):
    changed_modules: list[str] = Field(default_factory=list)
    changed_endpoints: list[str] = Field(default_factory=list)
    changed_data_models: list[str] = Field(default_factory=list)
    requires_regeneration: bool = False


class RepositorySnapshot(BaseModel):
    repository: RepositoryInfo
    modules: list[Module] = Field(default_factory=list)
    endpoints: list[Endpoint] = Field(default_factory=list)
    data_models: list[DataModel] = Field(default_factory=list)
    commands: dict[str, str] = Field(default_factory=dict)
    stats: RepositoryStats = Field(default_factory=RepositoryStats)


# =============================================================================
# SHARED UTILITY FUNCTIONS
# =============================================================================


# Common API page prefixes that are not service families
_API_COMMON_PREFIXES: frozenset[str] = frozenset({
    "auth", "authentication", "error", "health", "core", "data", "admin", "status", "convention",
})


def extract_service_family_from_page_id(page_id: str) -> str | None:
    """Extract service family name from API page ID.

    Args:
        page_id: Page ID like 'api-python-backend' or 'api-authentication'

    Returns:
        Service family name (e.g., 'python-backend') or None for special pages

    Examples:
        >>> extract_service_family_from_page_id('api-python-backend')
        'python-backend'
        >>> extract_service_family_from_page_id('api-authentication')
        None
        >>> extract_service_family_from_page_id('api-core-service')
        'core-service'
    """
    if not page_id.startswith("api-"):
        return None

    parts = page_id.split("-")[1:]

    # Skip common prefixes that are not service families
    if parts and parts[0] in _API_COMMON_PREFIXES:
        return None

    if len(parts) >= 2:
        return "-".join(parts)
    return parts[0] if parts else None
