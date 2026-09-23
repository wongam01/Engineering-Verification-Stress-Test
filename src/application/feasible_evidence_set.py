from __future__ import annotations

from collections.abc import Callable, Iterable
import hashlib

from src.application.feasible_evidence_ingress import (
    FeasibleEvidenceAnalysisResult,
    analyze_feasible_evidence_pdf,
)
from src.application.pdf_ingress import (
    IngestedPdfDocument,
)


FeasibleDocumentAnalyzer = Callable[
    [IngestedPdfDocument],
    FeasibleEvidenceAnalysisResult,
]


def analyze_feasible_evidence_documents(
    documents: Iterable[IngestedPdfDocument],
    *,
    analyzer: FeasibleDocumentAnalyzer | None = None,
    max_workers: int = 1,
) -> FeasibleEvidenceAnalysisResult | None:
    """
    Run the existing feasible-evidence analyzer independently
    across multiple physical source PDFs, then aggregate only
    the candidate review state.

    Candidate source_name / source_sha256 / source pages remain
    attached to their original document.
    """

    analyze_one = (
        analyzer
        if analyzer is not None
        else analyze_feasible_evidence_pdf
    )

    unique_documents = []
    seen_hashes = set()

    for document in documents:
        if document.content_sha256 in seen_hashes:
            continue

        seen_hashes.add(
            document.content_sha256
        )
        unique_documents.append(document)

    if not unique_documents:
        return None

    if max_workers < 1:
        raise ValueError(
            "max_workers must be at least 1."
        )

    if (
        max_workers == 1
        or len(unique_documents) < 2
    ):
        analyses = [
            analyze_one(document)
            for document in unique_documents
        ]
    else:
        from concurrent.futures import (
            ThreadPoolExecutor,
        )

        with ThreadPoolExecutor(
            max_workers=min(
                max_workers,
                len(unique_documents),
            )
        ) as executor:
            # Keep source/result ordering deterministic.
            analyses = list(
                executor.map(
                    analyze_one,
                    unique_documents,
                )
            )

    source_set_hash = hashlib.sha256(
        "\n".join(
            sorted(
                analysis.source_sha256
                for analysis in analyses
            )
        ).encode("utf-8")
    ).hexdigest()

    statuses = {
        analysis.status
        for analysis in analyses
    }

    combined_status = (
        analyses[0].status
        if len(statuses) == 1
        else "MULTI_SOURCE_MIXED_STATUS"
    )

    return FeasibleEvidenceAnalysisResult(
        status=combined_status,
        source_name=(
            "Engineering Source Set"
        ),
        source_sha256=source_set_hash,
        candidates=[
            candidate
            for analysis in analyses
            for candidate in analysis.candidates
        ],
        analysis_scope="FULL_DOCUMENT",
    )
