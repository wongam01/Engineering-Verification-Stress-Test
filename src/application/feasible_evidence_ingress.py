from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
import re
from typing import Any

from src.application.evidence_trace import (
    extract_explicit_source_pages,
    select_single_source_page,
)
from src.application.pdf_ingress import (
    IngestedPdfDocument,
    build_page_aware_text,
)


FeasibleEvidenceExtractor = Callable[
    [str, str],
    list[dict[str, Any]],
]


@dataclass(frozen=True)
class FeasibleSourceLocationReviewRecord:
    candidate_id: str
    source_sha256: str
    selected_page: int
    confirmed: bool


@dataclass
class FeasibleEvidenceCandidate:
    """
    One AI-extracted Feasible Domain candidate.

    This object is evidence/review state only.
    It does not modify EngineeringCase.
    """

    candidate_id: str

    source_name: str
    source_text: str
    source_block_id: str | None
    extraction: dict[str, Any]

    source_sha256: str
    source_page: int | None = None
    source_pages: tuple[int, ...] = ()
    source_location_candidates: tuple[int, ...] = ()
    source_location_status: str = (
        "SOURCE_LOCATION_UNRESOLVED"
    )

    source_location_review: (
        FeasibleSourceLocationReviewRecord | None
    ) = None

    approved: bool = False

    @property
    def source_location_ready(
        self,
    ) -> bool:
        return self.source_location_status in {
            "SOURCE_LOCATION_RESOLVED",
            "SOURCE_LOCATION_HUMAN_CONFIRMED",
        }


@dataclass
class FeasibleEvidenceAnalysisResult:
    status: str
    source_name: str
    source_sha256: str

    candidates: list[
        FeasibleEvidenceCandidate
    ] = field(
        default_factory=list
    )
    analysis_scope: str = "FULL_DOCUMENT"
    vision_processed_page_numbers: tuple[int, ...] = ()
    vision_unprocessed_candidate_page_numbers: tuple[int, ...] = ()

    @property
    def full_document_coverage(
        self,
    ) -> bool:
        return (
            self.analysis_scope
            == "FULL_DOCUMENT"
        )



_PAGE_MARKER_LINE = re.compile(
    r"(?m)^\s*===== PDF PAGE \d+ =====\s*$"
)


def _normalized_source_text(
    value: str,
) -> str:
    without_markers = (
        _PAGE_MARKER_LINE.sub(
            " ",
            value,
        )
    )

    return " ".join(
        without_markers.split()
    )


def _resolve_source_location(
    document: IngestedPdfDocument,
    source_text: str,
) -> tuple[
    str,
    int | None,
    tuple[int, ...],
    tuple[int, ...],
]:
    page_numbers = {
        page.page_number
        for page in document.pages
    }

    explicit_pages = (
        extract_explicit_source_pages(
            source_text
        )
    )

    normalized_block = (
        _normalized_source_text(
            source_text
        )
    )

    if explicit_pages:
        if (
            not normalized_block
            or any(
                page not in page_numbers
                for page in explicit_pages
            )
        ):
            return (
                "SOURCE_LOCATION_MISMATCH",
                None,
                (),
                explicit_pages,
            )

        referenced_text = " ".join(
            _normalized_source_text(
                page.text
            )
            for page in document.pages
            if page.page_number
            in explicit_pages
        )

        if (
            normalized_block
            not in referenced_text
        ):
            return (
                "SOURCE_LOCATION_MISMATCH",
                None,
                (),
                explicit_pages,
            )

        return (
            "SOURCE_LOCATION_RESOLVED",
            select_single_source_page(
                explicit_pages
            ),
            explicit_pages,
            explicit_pages,
        )

    if not normalized_block:
        return (
            "SOURCE_LOCATION_UNRESOLVED",
            None,
            (),
            (),
        )

    matched_pages = tuple(
        page.page_number
        for page in document.pages
        if normalized_block
        in _normalized_source_text(
            page.text
        )
    )

    if not matched_pages:
        return (
            "SOURCE_LOCATION_UNRESOLVED",
            None,
            (),
            (),
        )

    if len(matched_pages) > 1:
        return (
            "SOURCE_LOCATION_AMBIGUOUS",
            None,
            (),
            matched_pages,
        )

    return (
        "SOURCE_LOCATION_RESOLVED",
        matched_pages[0],
        matched_pages,
        matched_pages,
    )


def _default_extractor(
    text: str,
    source_name: str,
) -> list[dict[str, Any]]:
    from src.ai.feasible_evidence_parser import (
        extract_feasible_evidence_from_document,
    )

    return (
        extract_feasible_evidence_from_document(
            text,
            source_name,
        )
    )


def _build_candidate_id(
    *,
    source_sha256: str,
    source_block_id: str | None,
    variable: str | None,
    index: int,
) -> str:
    block = (
        source_block_id
        if source_block_id
        else f"ITEM{index}"
    )

    variable_id = (
        str(variable)
        if variable
        else "UNSPECIFIED"
    )

    return (
        "feasible:"
        + source_sha256[:12]
        + ":"
        + block
        + ":"
        + variable_id
        + ":"
        + str(index)
    )


def analyze_feasible_evidence_pdf(
    document: IngestedPdfDocument,
    *,
    extractor: (
        FeasibleEvidenceExtractor | None
    ) = None,
) -> FeasibleEvidenceAnalysisResult:
    """
    Operating Evidence PDF -> fixed Feasible Evidence candidates.

    PDF bytes are not sent to AI.
    This function does not approve candidates and does not modify Core.
    """

    if document.role != "feasible":
        raise ValueError(
            "Feasible Evidence analysis requires "
            "a feasible-role PDF."
        )

    if not (
        document.ready_for_semantic_analysis
    ):
        return (
            FeasibleEvidenceAnalysisResult(
                status=(
                    "FEASIBLE_DOCUMENT_NOT_READY"
                ),
                source_name=document.filename,
                source_sha256=(
                    document.content_sha256
                ),
                candidates=[],
                analysis_scope="NOT_ANALYZED",
                vision_processed_page_numbers=(
                    document.vision_processed_page_numbers
                ),
                vision_unprocessed_candidate_page_numbers=(
                    document.vision_unprocessed_candidate_page_numbers
                    or tuple(
                        page.page_number
                        for page in document.pages
                        if not page.text.strip()
                    )
                ),
            )
        )

    selected_extractor = (
        extractor
        if extractor is not None
        else _default_extractor
    )

    page_aware_text = (
        build_page_aware_text(
            document
        )
    )

    extractions = selected_extractor(
        page_aware_text,
        document.filename,
    )

    candidates = []

    for index, extraction in enumerate(
        extractions,
        start=1,
    ):
        data = deepcopy(
            extraction
        )

        # Source identity belongs to Application,
        # not to AI output.
        data[
            "source_name"
        ] = document.filename

        source_text = str(
            data.get(
                "source_text"
            )
            or ""
        )

        source_block_id = (
            data.get(
                "source_line_id"
            )
        )

        (
            source_location_status,
            source_page,
            source_pages,
            source_location_candidates,
        ) = _resolve_source_location(
            document,
            source_text,
        )

        candidate_id = (
            _build_candidate_id(
                source_sha256=(
                    document.content_sha256
                ),
                source_block_id=(
                    source_block_id
                ),
                variable=data.get(
                    "variable"
                ),
                index=index,
            )
        )

        candidates.append(
            FeasibleEvidenceCandidate(
                candidate_id=(
                    candidate_id
                ),
                source_name=(
                    document.filename
                ),
                source_text=(
                    source_text
                ),
                source_block_id=(
                    source_block_id
                ),
                source_sha256=(
                    document.content_sha256
                ),
                source_page=(
                    source_page
                ),
                source_pages=(
                    source_pages
                ),
                source_location_candidates=(
                    source_location_candidates
                ),
                source_location_status=(
                    source_location_status
                ),
                extraction=data,
            )
        )

    if not candidates:
        status = (
            "NO_FEASIBLE_EVIDENCE_CANDIDATES"
        )
    else:
        status = (
            "FEASIBLE_EVIDENCE_REVIEW_REQUIRED"
        )

    return (
        FeasibleEvidenceAnalysisResult(
            status=status,
            source_name=document.filename,
            source_sha256=(
                document.content_sha256
            ),
            candidates=candidates,
            analysis_scope=(
                "FULL_DOCUMENT"
                if document.full_document_coverage
                else "SELECTED_PAGES"
            ),
            vision_processed_page_numbers=(
                document.vision_processed_page_numbers
            ),
            vision_unprocessed_candidate_page_numbers=(
                document.vision_unprocessed_candidate_page_numbers
            ),
        )
    )


def confirm_ambiguous_feasible_source_location(
    candidate: FeasibleEvidenceCandidate,
    selected_page: int,
    confirmed: bool,
) -> FeasibleEvidenceCandidate:
    """
    Human-resolve an exact repeated source block.

    This changes source-location review only.
    It does not change AI extraction and does not approve F.
    """

    updated = deepcopy(
        candidate
    )

    if (
        candidate.source_location_status
        not in {
            "SOURCE_LOCATION_AMBIGUOUS",
            "SOURCE_LOCATION_HUMAN_CONFIRMED",
        }
    ):
        raise ValueError(
            "Only an ambiguous feasible source "
            "location can be human-resolved."
        )

    if (
        selected_page
        not in candidate
        .source_location_candidates
    ):
        raise ValueError(
            "Selected page is not one "
            "of the exact source matches."
        )

    if not confirmed:
        updated.source_page = None
        updated.source_pages = ()
        updated.source_location_status = (
            "SOURCE_LOCATION_AMBIGUOUS"
        )
        updated.source_location_review = (
            None
        )

        return updated

    updated.source_page = (
        selected_page
    )
    updated.source_pages = (
        selected_page,
    )
    updated.source_location_status = (
        "SOURCE_LOCATION_HUMAN_CONFIRMED"
    )

    updated.source_location_review = (
        FeasibleSourceLocationReviewRecord(
            candidate_id=(
                candidate.candidate_id
            ),
            source_sha256=(
                candidate.source_sha256
            ),
            selected_page=(
                selected_page
            ),
            confirmed=True,
        )
    )

    return updated


# =========================================================
# ENGINEER REVIEW → UI PREFILL
# =========================================================

from src.application.evidence_trace import (
    build_source_reference,
)


@dataclass(frozen=True)
class FeasibleEvidencePrefill:
    """
    Engineer-approved Feasible Evidence candidate converted into
    deterministic UI/form prefill data.

    This object does NOT modify EngineeringCase.
    """

    candidate_id: str

    source_variable: str
    canonical_variable: str

    unit: str
    feasible_min: str
    feasible_max: str

    evidence_type: str
    evidence_reference: str

    source_name: str
    source_text: str
    source_sha256: str
    source_page: int | None
    source_pages: tuple[int, ...]
    source_block_id: str | None
    source_location_status: str
    analysis_scope: str = "FULL_DOCUMENT"
    vision_processed_page_numbers: tuple[int, ...] = ()
    vision_unprocessed_candidate_page_numbers: tuple[int, ...] = ()

    @property
    def full_document_coverage(
        self,
    ) -> bool:
        return (
            self.analysis_scope
            == "FULL_DOCUMENT"
        )


@dataclass
class FeasibleEvidencePrefillResult:
    status: str

    prefills: list[
        FeasibleEvidencePrefill
    ] = field(
        default_factory=list
    )

    issues: list[str] = field(
        default_factory=list
    )
    analysis_scope: str = "FULL_DOCUMENT"
    vision_processed_page_numbers: tuple[int, ...] = ()
    vision_unprocessed_candidate_page_numbers: tuple[int, ...] = ()

    @property
    def full_document_coverage(
        self,
    ) -> bool:
        return (
            self.analysis_scope
            == "FULL_DOCUMENT"
        )

    @property
    def ready(
        self,
    ) -> bool:
        return (
            self.status
            == "FEASIBLE_PREFILL_READY"
        )


def build_feasible_evidence_prefills(
    analysis: FeasibleEvidenceAnalysisResult,
    *,
    approved_candidate_ids: list[str],
    canonical_variable_by_candidate: dict[
        str,
        str,
    ],
) -> FeasibleEvidencePrefillResult:
    """
    Apply explicit Engineer Approval to fixed F candidates and build
    deterministic prefill values.

    Rules:
    - AI extraction is never rerun.
    - Unknown approvals fail safe.
    - source location must be resolved/reviewed.
    - AI review-required candidates cannot be promoted.
    - canonical variable mapping must be explicit.
    - no Core mutation occurs here.
    """

    approved_ids = set(
        approved_candidate_ids
    )

    known_ids = {
        candidate.candidate_id
        for candidate
        in analysis.candidates
    }

    unknown_ids = (
        approved_ids
        - known_ids
    )

    if unknown_ids:
        return (
            FeasibleEvidencePrefillResult(
                status=(
                    "INVALID_FEASIBLE_APPROVAL"
                ),
                issues=[
                    (
                        "Unknown feasible candidate "
                        f"approval: {candidate_id}"
                    )
                    for candidate_id
                    in sorted(
                        unknown_ids
                    )
                ],
                analysis_scope=(
                    analysis.analysis_scope
                ),
                vision_processed_page_numbers=(
                    analysis.vision_processed_page_numbers
                ),
                vision_unprocessed_candidate_page_numbers=(
                    analysis.vision_unprocessed_candidate_page_numbers
                ),
            )
        )

    prefills: list[
        FeasibleEvidencePrefill
    ] = []

    issues: list[str] = []

    for candidate in analysis.candidates:
        if (
            candidate.candidate_id
            not in approved_ids
        ):
            issues.append(
                (
                    f"{candidate.candidate_id}: "
                    "Engineer approval required."
                )
            )
            continue

        if not candidate.source_location_ready:
            issues.append(
                (
                    f"{candidate.candidate_id}: "
                    "Source location review is incomplete: "
                    f"{candidate.source_location_status}."
                )
            )
            continue

        extraction = (
            candidate.extraction
        )

        if extraction.get(
            "needs_review",
            True,
        ):
            reason = str(
                extraction.get(
                    "review_reason"
                )
                or ""
            ).strip()

            issue = (
                f"{candidate.candidate_id}: "
                "Feasible Evidence candidate "
                "requires review."
            )

            if reason:
                issue += (
                    " "
                    + reason
                )

            issues.append(
                issue
            )
            continue

        source_variable = str(
            extraction.get(
                "variable"
            )
            or ""
        ).strip()

        if not source_variable:
            issues.append(
                (
                    f"{candidate.candidate_id}: "
                    "Source variable is missing."
                )
            )
            continue

        canonical_variable = str(
            canonical_variable_by_candidate.get(
                candidate.candidate_id,
                "",
            )
        ).strip()

        if not canonical_variable:
            issues.append(
                (
                    f"{candidate.candidate_id}: "
                    "Canonical variable mapping required."
                )
            )
            continue

        feasible_min = str(
            extraction.get(
                "min"
            )
            or ""
        ).strip()

        feasible_max = str(
            extraction.get(
                "max"
            )
            or ""
        ).strip()

        unit = str(
            extraction.get(
                "unit"
            )
            or ""
        ).strip()

        evidence_type = str(
            extraction.get(
                "evidence_type"
            )
            or ""
        ).strip()

        if not (
            feasible_min
            and feasible_max
            and unit
            and evidence_type
        ):
            issues.append(
                (
                    f"{candidate.candidate_id}: "
                    "Approved candidate is missing "
                    "required prefill data."
                )
            )
            continue

        source_reference = (
            build_source_reference(
                source_name=(
                    candidate.source_name
                ),
                source_block_id=(
                    candidate.source_block_id
                ),
                source_pages=(
                    candidate.source_pages
                ),
            )
        )

        if not source_reference:
            issues.append(
                (
                    f"{candidate.candidate_id}: "
                    "Deterministic source reference "
                    "could not be built."
                )
            )
            continue

        prefills.append(
            FeasibleEvidencePrefill(
                candidate_id=(
                    candidate.candidate_id
                ),
                source_variable=(
                    source_variable
                ),
                canonical_variable=(
                    canonical_variable
                ),
                unit=unit,
                feasible_min=(
                    feasible_min
                ),
                feasible_max=(
                    feasible_max
                ),
                evidence_type=(
                    evidence_type
                ),
                evidence_reference=(
                    source_reference
                ),
                source_name=(
                    candidate.source_name
                ),
                source_text=(
                    candidate.source_text
                ),
                source_sha256=(
                    candidate.source_sha256
                ),
                source_page=(
                    candidate.source_page
                ),
                source_pages=(
                    candidate.source_pages
                ),
                source_block_id=(
                    candidate.source_block_id
                ),
                source_location_status=(
                    candidate.source_location_status
                ),
                analysis_scope=(
                    analysis.analysis_scope
                ),
                vision_processed_page_numbers=(
                    analysis.vision_processed_page_numbers
                ),
                vision_unprocessed_candidate_page_numbers=(
                    analysis.vision_unprocessed_candidate_page_numbers
                ),
            )
        )

    if issues:
        status = (
            "FEASIBLE_PREFILL_REVIEW_REQUIRED"
        )
    elif not prefills:
        status = (
            "NO_FEASIBLE_PREFILLS"
        )
    else:
        status = (
            "FEASIBLE_PREFILL_READY"
        )

    return (
        FeasibleEvidencePrefillResult(
            status=status,
            prefills=prefills,
            issues=issues,
            analysis_scope=(
                analysis.analysis_scope
            ),
            vision_processed_page_numbers=(
                analysis.vision_processed_page_numbers
            ),
            vision_unprocessed_candidate_page_numbers=(
                analysis.vision_unprocessed_candidate_page_numbers
            ),
        )
    )


def build_feasible_evidence_trace(
    prefill: FeasibleEvidencePrefill,
):
    """
    Convert one approved source-bound Feasible Evidence prefill
    into a rich Application-level EvidenceTrace.

    The validated Core model remains unchanged.
    """
    from src.application.models import EvidenceTrace

    return EvidenceTrace(
        role="feasible_domain",
        target_id=prefill.canonical_variable,
        source_name=prefill.source_name,
        source_text=prefill.source_text,
        source_sha256=prefill.source_sha256,
        source_page=prefill.source_page,
        source_pages=prefill.source_pages,
        source_block_id=prefill.source_block_id,
        source_reference=prefill.evidence_reference,
        source_location_status=(
            prefill.source_location_status
        ),
        analysis_scope=prefill.analysis_scope,
        vision_processed_page_numbers=(
            prefill.vision_processed_page_numbers
        ),
        vision_unprocessed_candidate_page_numbers=(
            prefill.vision_unprocessed_candidate_page_numbers
        ),
    )
