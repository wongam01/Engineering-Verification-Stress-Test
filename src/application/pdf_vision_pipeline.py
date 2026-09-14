from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Callable

from src.ai.pdf_page_triage import (
    PdfPageTriageResult,
    PdfTwoStageTriageResult,
    recommend_pdf_pages_two_stage,
)
from src.application.pdf_ingress import (
    IngestedPdfDocument,
    VisionPageExtractor,
    ingest_pdf_document,
    pdf_document_can_attempt_vision,
    pdf_document_requires_vision,
)
from src.application.pdf_vision_selection import (
    PdfVisionSelectionPlan,
    build_pdf_vision_selection_plan,
    validate_pdf_vision_page_selection,
)


PdfPageTriageRecommender = Callable[
    [
        IngestedPdfDocument,
        PdfVisionSelectionPlan,
    ],
    PdfPageTriageResult,
]


@dataclass(frozen=True)
class PdfVisionPreparationResult:
    status: str
    document: IngestedPdfDocument
    selection_plan: PdfVisionSelectionPlan | None = None
    triage_result: PdfPageTriageResult | None = None
    coarse_triage_result: PdfPageTriageResult | None = None
    selected_page_numbers: tuple[int, ...] = ()
    issue_codes: tuple[str, ...] = ()

    @property
    def ready(self) -> bool:
        return (
            self.document.ready_for_semantic_analysis
            and self.status
            in {
                "VISION_NOT_REQUIRED",
                "VISION_PREPARATION_READY",
            }
        )


def prepare_pdf_document_with_page_triage(
    document: IngestedPdfDocument,
    *,
    vision_page_extractor: VisionPageExtractor,
    triage_recommender: PdfPageTriageRecommender | None = None,
) -> PdfVisionPreparationResult:
    """
    Prepare a PDF for semantic analysis using bounded Vision recovery.

    Flow:
    1. Detect pages without embedded text.
    2. Build a deterministic Vision-selection plan.
    3. If over budget, obtain a bounded triage recommendation.
    4. Revalidate the recommendation with the application-layer
       selection contract.
    5. Run high-detail Vision only on the validated selected pages.

    Partial analysis remains explicitly marked as selected-page scope.
    """

    if not pdf_document_requires_vision(document):
        return PdfVisionPreparationResult(
            status="VISION_NOT_REQUIRED",
            document=document,
        )

    if not pdf_document_can_attempt_vision(document):
        return PdfVisionPreparationResult(
            status="VISION_PREPARATION_BLOCKED",
            document=document,
            issue_codes=(
                "VISION_DOCUMENT_NOT_RECOVERABLE",
            ),
        )

    plan = build_pdf_vision_selection_plan(
        document
    )

    triage_result: PdfPageTriageResult | None = None

    if plan.selection_required:
        if triage_recommender is None:
            return PdfVisionPreparationResult(
                status="VISION_PREPARATION_BLOCKED",
                document=document,
                selection_plan=plan,
                issue_codes=(
                    "VISION_PAGE_SELECTION_REQUIRED",
                ),
            )

        try:
            triage_result = triage_recommender(
                document,
                plan,
            )
        except Exception:
            return PdfVisionPreparationResult(
                status="VISION_PREPARATION_BLOCKED",
                document=document,
                selection_plan=plan,
                issue_codes=(
                    "VISION_PAGE_TRIAGE_FAILED",
                ),
            )

        validation = (
            validate_pdf_vision_page_selection(
                plan,
                triage_result.selected_page_numbers,
            )
        )
    else:
        validation = (
            validate_pdf_vision_page_selection(
                plan,
                None,
            )
        )

    if not validation.valid:
        return PdfVisionPreparationResult(
            status="VISION_PREPARATION_BLOCKED",
            document=document,
            selection_plan=plan,
            triage_result=triage_result,
            issue_codes=validation.issue_codes,
        )

    selected_page_numbers = (
        validation.selected_page_numbers
    )

    prepared = ingest_pdf_document(
        role=document.role,
        filename=document.filename,
        content=document.raw_bytes,
        vision_page_extractor=vision_page_extractor,
        vision_page_numbers=selected_page_numbers,
    )

    if not prepared.ready_for_semantic_analysis:
        return PdfVisionPreparationResult(
            status="VISION_PREPARATION_BLOCKED",
            document=prepared,
            selection_plan=plan,
            triage_result=triage_result,
            selected_page_numbers=(
                selected_page_numbers
            ),
            issue_codes=tuple(
                issue.code
                for issue in prepared.issues
                if issue.severity == "ERROR"
            ),
        )

    return PdfVisionPreparationResult(
        status="VISION_PREPARATION_READY",
        document=prepared,
        selection_plan=plan,
        triage_result=triage_result,
        selected_page_numbers=(
            selected_page_numbers
        ),
    )


def prepare_pdf_document_with_two_stage_triage(
    document: IngestedPdfDocument,
    *,
    vision_page_extractor: VisionPageExtractor,
    triage_client,
) -> PdfVisionPreparationResult:
    """
    Prepare a PDF using bounded two-stage page triage.

    Documents within the automatic Vision-page budget bypass triage
    and retain the existing automatic-all behavior.

    Over-budget documents use generic two-stage triage, then pass the
    focused recommendation through the same deterministic selection
    contract and selected-page Vision ingress used by the existing
    application pipeline.

    Coarse and focused triage provenance remain separately available.
    """

    decision: PdfTwoStageTriageResult | None = None

    def two_stage_recommender(
        current_document: IngestedPdfDocument,
        plan: PdfVisionSelectionPlan,
    ) -> PdfPageTriageResult:
        nonlocal decision

        decision = recommend_pdf_pages_two_stage(
            current_document.raw_bytes,
            candidate_page_numbers=(
                plan.candidate_page_numbers
            ),
            document_role=current_document.role,
            max_selected_pages=(
                plan.max_selected_pages
            ),
            client=triage_client,
        )

        return decision.focused_result

    result = prepare_pdf_document_with_page_triage(
        document,
        vision_page_extractor=vision_page_extractor,
        triage_recommender=two_stage_recommender,
    )

    return replace(
        result,
        coarse_triage_result=(
            decision.coarse_result
            if decision is not None
            else None
        ),
    )
