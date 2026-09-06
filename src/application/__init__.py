"""
Application layer for the Engineering Verification Stress Test.

This package orchestrates already-validated Core components.
It must not reimplement solver or validation semantics.
"""

from src.application.models import (
    EvidenceTrace,
    VerificationWorkflowResult,
)
from src.application.verification_workflow import (
    run_verification_workflow,
)

__all__ = [
    "EvidenceTrace",
    "VerificationWorkflowResult",
    "run_verification_workflow",
]
