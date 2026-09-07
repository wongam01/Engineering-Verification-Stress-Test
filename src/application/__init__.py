"""
Application layer for the Engineering Verification Stress Test.

This package orchestrates already-validated Core components.
It must not reimplement solver or validation semantics.
"""

from src.application.models import (
    EvidenceTrace,
    VerificationWorkflowResult,
)
from src.application.semantic_ingress import (
    SemanticAnalysisResult,
    SemanticCandidate,
    SemanticDocument,
    SemanticIngressResult,
    analyze_semantic_documents,
    apply_semantic_approvals,
)
from src.application.document_workflow import (
    DocumentVerificationWorkflowResult,
    run_document_verification_workflow,
)
from src.application.verification_workflow import (
    run_verification_workflow,
)
from src.application.gap_classification import (
    GapClassification,
    GapClassificationReport,
    classify_verification_gap,
)


from src.application.trace_view import (
    ConstraintTraceEntry,
    ConstraintTraceReport,
    build_constraint_trace_view,
)

__all__ = [
    "EvidenceTrace",
    "VerificationWorkflowResult",
    "SemanticDocument",
    "SemanticCandidate",
    "SemanticAnalysisResult",
    "SemanticIngressResult",
    "DocumentVerificationWorkflowResult",
    "analyze_semantic_documents",
    "apply_semantic_approvals",
    "run_document_verification_workflow",
    "run_verification_workflow",
    "GapClassification",
    "GapClassificationReport",
    "classify_verification_gap",
    "ConstraintTraceEntry",
    "ConstraintTraceReport",
    "build_constraint_trace_view",
]
