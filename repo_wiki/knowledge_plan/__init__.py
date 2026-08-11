"""First-class, version-managed knowledge plan APIs."""

from .generator import generate_plan
from .impact import analyze_impact
from .io import dump_plan_yaml, load_plan, load_plan_yaml, write_plan
from .schema import (
    DEFAULT_PLAN_PATH,
    SCHEMA_VERSION,
    ManualEditConflictError,
    ValidationIssue,
    attach_fingerprint,
    compute_managed_fingerprint,
    has_manual_managed_edits,
    validate_plan,
)

__all__ = [
    "DEFAULT_PLAN_PATH",
    "SCHEMA_VERSION",
    "ManualEditConflictError",
    "ValidationIssue",
    "analyze_impact",
    "attach_fingerprint",
    "compute_managed_fingerprint",
    "dump_plan_yaml",
    "generate_plan",
    "has_manual_managed_edits",
    "load_plan",
    "load_plan_yaml",
    "validate_plan",
    "write_plan",
]
