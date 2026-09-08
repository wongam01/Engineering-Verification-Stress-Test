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
    SourceLocationReviewRecord,
    SemanticAnalysisResult,
    SemanticCandidate,
    SemanticDocument,
    SemanticIngressResult,
    SemanticSourcePage,
    analyze_semantic_documents,
    apply_semantic_approvals,
    build_semantic_documents_signature,
    build_semantic_review_signature,
    confirm_ambiguous_source_location,
)
from src.application.pdf_ingress import (
    IngestedPdfDocument,
    PdfDocumentSetValidation,
    PdfIngestionIssue,
    PdfPageText,
    build_page_aware_text,
    build_pdf_page_preview,
    build_semantic_document,
    ingest_pdf_document,
    validate_pdf_document_set,
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
    "SemanticSourcePage",
    "SemanticCandidate",
    "SourceLocationReviewRecord",
    "SemanticAnalysisResult",
    "SemanticIngressResult",
    "DocumentVerificationWorkflowResult",
    "analyze_semantic_documents",
    "apply_semantic_approvals",
    "build_semantic_documents_signature",
    "build_semantic_review_signature",
    "confirm_ambiguous_source_location",
    "IngestedPdfDocument",
    "PdfDocumentSetValidation",
    "PdfIngestionIssue",
    "PdfPageText",
    "build_page_aware_text",
    "build_pdf_page_preview",
    "build_semantic_document",
    "ingest_pdf_document",
    "validate_pdf_document_set",
    "run_document_verification_workflow",
    "run_verification_workflow",
    "GapClassification",
    "GapClassificationReport",
    "classify_verification_gap",
    "ConstraintTraceEntry",
    "ConstraintTraceReport",
    "build_constraint_trace_view",
]
