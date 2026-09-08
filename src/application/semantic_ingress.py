from collections.abc import Callable, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any, Literal

from src.ai.core_adapter import (
    AIConstraintAdapterResult,
    apply_approved_ai_constraint,
    convert_ai_constraint,
)
from src.application.models import (
    EvidenceTrace,
)
from src.application.evidence_trace import (
    build_source_reference,
    extract_explicit_source_pages,
    select_single_source_page,
)
from src.core.models import (
    EngineeringCase,
)


SemanticRole = Literal[
    "requirement",
    "verification",
]

SemanticExtractor = Callable[
    [str, SemanticRole, str],
    list[dict[str, Any]],
]


@dataclass(frozen=True)
class SemanticSourcePage:
    page_number: int
    text: str


@dataclass(frozen=True)
class SourceLocationReviewRecord:
    candidate_id: str
    source_sha256: str
    selected_page: int
    confirmed: bool


@dataclass(frozen=True)
class SemanticDocument:
    """
    Application Layer가 AI Semantic Parser에
    전달하는 하나의 Engineering 문서 입력.

    Phase 4A-2에서는 text 입력을 사용한다.
    실제 PDF/page ingestion은 Evidence Trace
    단계에서 확장한다.
    """

    role: SemanticRole
    source_name: str
    text: str
    source_sha256: str | None = None
    source_pages: tuple[
        SemanticSourcePage,
        ...,
    ] = ()
    source_format: Literal[
        "text",
        "pdf",
    ] = "text"


@dataclass
class SemanticCandidate:
    """
    AI가 문서에서 추출한 하나의
    Requirement / Verification 후보.

    AI 결과 자체와 deterministic Adapter 결과를
    함께 보존한다.
    """

    candidate_id: str

    role: SemanticRole
    source_name: str
    source_text: str
    source_block_id: str | None
    extraction: dict[str, Any]
    adapter_result: AIConstraintAdapterResult

    source_sha256: str | None = None
    source_page: int | None = None
    source_pages: tuple[int, ...] = ()
    source_location_candidates: tuple[
        int,
        ...,
    ] = ()
    source_location_status: str = (
        "SOURCE_LOCATION_NOT_APPLICABLE"
    )
    source_location_review: (
        SourceLocationReviewRecord | None
    ) = None

    approved: bool = False
    applied: bool = False

    @property
    def adapter_accepted(
        self,
    ) -> bool:
        return self.adapter_result.accepted

    @property
    def source_location_ready(
        self,
    ) -> bool:
        return self.source_location_status in {
            "SOURCE_LOCATION_NOT_APPLICABLE",
            "SOURCE_LOCATION_RESOLVED",
            "SOURCE_LOCATION_HUMAN_CONFIRMED",
        }

    @property
    def constraint_id(
        self,
    ) -> str:
        constraint = (
            self.adapter_result.constraint
        )

        if constraint is not None:
            return constraint.id

        return str(
            self.extraction.get(
                "constraint_id",
                "UNSPECIFIED",
            )
        )


@dataclass
class SemanticAnalysisResult:
    """
    AI Semantic Analysis의 고정된 결과.

    중요한 점:
    사용자가 승인한다고 해서
    AI extraction을 다시 실행하지 않는다.
    """

    status: str

    documents: list[
        SemanticDocument
    ] = field(
        default_factory=list
    )

    candidates: list[
        SemanticCandidate
    ] = field(
        default_factory=list
    )

    @property
    def has_candidates(
        self,
    ) -> bool:
        return bool(
            self.candidates
        )


@dataclass
class SemanticIngressResult:
    """
    Semantic candidate에 대한
    명시적 승인 적용 결과.

    ready_for_formal_workflow=True일 때만
    Assured Pipeline으로 넘길 수 있다.
    """

    status: str

    case: EngineeringCase

    candidates: list[
        SemanticCandidate
    ] = field(
        default_factory=list
    )

    evidence: list[
        EvidenceTrace
    ] = field(
        default_factory=list
    )

    issues: list[str] = field(
        default_factory=list
    )

    @property
    def ready_for_formal_workflow(
        self,
    ) -> bool:
        return (
            self.status
            == "READY_FOR_FORMAL_WORKFLOW"
        )


def _default_extractor(
    text: str,
    role: SemanticRole,
    source_name: str,
) -> list[dict[str, Any]]:
    """
    실제 AI parser는 필요한 순간에만 import한다.

    이렇게 하면 Application Layer 자체를 import하거나
    deterministic unit test를 실행하는 것만으로
    AI API 호출이 발생하지 않는다.
    """

    from src.ai.multi_constraint_parser import (
        extract_constraints_from_document,
    )

    return extract_constraints_from_document(
        text,
        role,
        source_name,
    )


def _build_candidate_id(
    *,
    role: str,
    source_name: str,
    source_block_id: str | None,
    constraint_id: str,
    index: int,
) -> str:
    block = (
        source_block_id
        if source_block_id
        else f"ITEM{index}"
    )

    return (
        f"{role}:"
        f"{source_name}:"
        f"{block}:"
        f"{constraint_id}:"
        f"{index}"
    )


_PAGE_MARKER_LINE = re.compile(
    r"(?m)^\s*===== PDF PAGE \d+ =====\s*$"
)


def _normalized_source_text(
    value: str,
) -> str:
    without_markers = _PAGE_MARKER_LINE.sub(
        " ",
        value,
    )

    return " ".join(
        without_markers.split()
    )


def _resolve_candidate_source_location(
    document: SemanticDocument,
    source_text: str,
) -> tuple[
    str,
    int | None,
    tuple[int, ...],
    tuple[int, ...],
]:
    if document.source_format != "pdf":
        return (
            "SOURCE_LOCATION_NOT_APPLICABLE",
            None,
            (),
            (),
        )

    page_numbers = {
        page.page_number
        for page in document.source_pages
    }

    explicit_pages = extract_explicit_source_pages(
        source_text
    )

    normalized_block = _normalized_source_text(
        source_text
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
            for page in document.source_pages
            if page.page_number in explicit_pages
        )

        if normalized_block not in referenced_text:
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
        for page in document.source_pages
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


def confirm_ambiguous_source_location(
    candidate: SemanticCandidate,
    selected_page: int,
    confirmed: bool,
) -> SemanticCandidate:
    """
    Record an engineer's source-page choice without changing the
    extracted semantic constraint or approving that constraint.
    """

    updated = deepcopy(candidate)

    if candidate.source_location_status not in {
        "SOURCE_LOCATION_AMBIGUOUS",
        "SOURCE_LOCATION_HUMAN_CONFIRMED",
    }:
        raise ValueError(
            "Only an ambiguous source location can be human-resolved."
        )

    if selected_page not in candidate.source_location_candidates:
        raise ValueError(
            "Selected source page is not one of the exact matches."
        )

    if not confirmed:
        updated.source_page = None
        updated.source_pages = ()
        updated.source_location_status = (
            "SOURCE_LOCATION_AMBIGUOUS"
        )
        updated.source_location_review = None
        return updated

    if not candidate.source_sha256:
        raise ValueError(
            "PDF source identity is missing."
        )

    updated.source_page = selected_page
    updated.source_pages = (selected_page,)
    updated.source_location_status = (
        "SOURCE_LOCATION_HUMAN_CONFIRMED"
    )
    updated.source_location_review = (
        SourceLocationReviewRecord(
            candidate_id=candidate.candidate_id,
            source_sha256=candidate.source_sha256,
            selected_page=selected_page,
            confirmed=True,
        )
    )
    return updated


def build_semantic_documents_signature(
    documents: Sequence[SemanticDocument],
) -> str:
    payload = [
        {
            "role": document.role,
            "source_name": document.source_name,
            "source_sha256": document.source_sha256,
            "source_format": document.source_format,
            "text": document.text,
        }
        for document in documents
    ]

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def build_semantic_review_signature(
    analysis: SemanticAnalysisResult,
    approved_candidate_ids: Sequence[str],
) -> str:
    approved = set(approved_candidate_ids)
    payload = [
        {
            "candidate_id": candidate.candidate_id,
            "approved": candidate.candidate_id in approved,
            "source_location_status": (
                candidate.source_location_status
            ),
            "source_pages": candidate.source_pages,
        }
        for candidate in analysis.candidates
    ]

    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def analyze_semantic_documents(
    documents: Sequence[
        SemanticDocument
    ],
    *,
    extractor: SemanticExtractor | None = None,
) -> SemanticAnalysisResult:
    """
    Document → AI Candidate 분석 단계.

    이 함수는 EngineeringCase를 수정하지 않는다.
    Solver도 실행하지 않는다.
    Human Approval도 생성하지 않는다.

    AI 결과를 한 번 받아 Candidate로 고정한다.
    """

    document_list = list(
        documents
    )

    if not document_list:
        return SemanticAnalysisResult(
            status="SEMANTIC_INPUT_MISSING",
            documents=[],
            candidates=[],
        )

    selected_extractor = (
        extractor
        if extractor is not None
        else _default_extractor
    )

    candidates: list[
        SemanticCandidate
    ] = []

    for document in document_list:
        if document.role not in {
            "requirement",
            "verification",
        }:
            raise ValueError(
                "Semantic document role은 "
                "requirement 또는 verification이어야 합니다."
            )

        extractions = selected_extractor(
            document.text,
            document.role,
            document.source_name,
        )

        for index, extraction in enumerate(
            extractions,
            start=1,
        ):
            data = deepcopy(
                extraction
            )

            # -------------------------------------------------
            # Role / Source identity는 Application이 보존한다.
            # AI가 임의로 변경한 값에 의존하지 않는다.
            # -------------------------------------------------
            data[
                "constraint_role"
            ] = document.role

            data[
                "source_name"
            ] = document.source_name

            if not data.get(
                "source_text"
            ):
                data[
                    "source_text"
                ] = document.text

            adapter_result = (
                convert_ai_constraint(
                    data
                )
            )

            source_block_id = (
                data.get(
                    "source_line_id"
                )
            )

            raw_constraint_id = str(
                data.get(
                    "constraint_id",
                    "UNSPECIFIED",
                )
            )

            candidate_id = (
                _build_candidate_id(
                    role=document.role,
                    source_name=(
                        document.source_name
                    ),
                    source_block_id=(
                        source_block_id
                    ),
                    constraint_id=(
                        raw_constraint_id
                    ),
                    index=index,
                )
            )

            (
                source_location_status,
                source_page,
                source_pages,
                source_location_candidates,
            ) = _resolve_candidate_source_location(
                document,
                adapter_result.source_text,
            )

            candidates.append(
                SemanticCandidate(
                    candidate_id=(
                        candidate_id
                    ),
                    role=document.role,
                    source_name=(
                        adapter_result
                        .source_name
                    ),
                    source_text=(
                        adapter_result
                        .source_text
                    ),
                    source_block_id=(
                        source_block_id
                    ),
                    source_sha256=(
                        document.source_sha256
                    ),
                    source_page=source_page,
                    source_pages=source_pages,
                    source_location_candidates=(
                        source_location_candidates
                    ),
                    source_location_status=(
                        source_location_status
                    ),
                    extraction=data,
                    adapter_result=(
                        adapter_result
                    ),
                )
            )

    if not candidates:
        return SemanticAnalysisResult(
            status=(
                "NO_SEMANTIC_CANDIDATES"
            ),
            documents=document_list,
            candidates=[],
        )

    return SemanticAnalysisResult(
        status="SEMANTIC_REVIEW_REQUIRED",
        documents=document_list,
        candidates=candidates,
    )


def apply_semantic_approvals(
    base_case: EngineeringCase,
    analysis: SemanticAnalysisResult,
    approved_candidate_ids: Sequence[
        str
    ],
) -> SemanticIngressResult:
    """
    이미 고정된 SemanticAnalysisResult에
    사람의 명시적 승인을 적용한다.

    여기서는 AI를 다시 호출하지 않는다.

    하나라도:
    - 승인되지 않았거나
    - Adapter가 거부했거나
    - 지원되지 않거나
    - review가 필요한 경우

    Formal Workflow로 진행하지 않는다.
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
        return SemanticIngressResult(
            status=(
                "INVALID_SEMANTIC_APPROVAL"
            ),
            case=deepcopy(
                base_case
            ),
            candidates=deepcopy(
                analysis.candidates
            ),
            issues=[
                (
                    "Unknown semantic candidate "
                    f"approval: {candidate_id}"
                )
                for candidate_id
                in sorted(
                    unknown_ids
                )
            ],
        )

    updated_case = deepcopy(
        base_case
    )

    candidates = deepcopy(
        analysis.candidates
    )

    evidence: list[
        EvidenceTrace
    ] = []

    issues: list[str] = []

    for candidate in candidates:
        candidate.approved = (
            candidate.candidate_id
            in approved_ids
        )

        if not candidate.adapter_accepted:
            issues.append(
                (
                    f"{candidate.candidate_id}: "
                    f"{candidate.adapter_result.message}"
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

        if not candidate.approved:
            issues.append(
                (
                    f"{candidate.candidate_id}: "
                    "Engineer semantic approval required."
                )
            )
            continue

        updated_case = (
            apply_approved_ai_constraint(
                updated_case,
                candidate.adapter_result,
                approved=True,
            )
        )

        candidate.applied = True

        source_pages = (
            candidate.source_pages
            if candidate.source_pages
            else extract_explicit_source_pages(
                candidate.source_text
            )
        )

        source_page = (
            select_single_source_page(
                source_pages
            )
        )

        source_reference = (
            build_source_reference(
                source_name=(
                    candidate.source_name
                ),
                source_block_id=(
                    candidate.source_block_id
                ),
                source_pages=source_pages,
            )
        )

        evidence.append(
            EvidenceTrace(
                role=candidate.role,
                target_id=(
                    candidate.constraint_id
                ),
                source_name=(
                    candidate.source_name
                ),
                source_sha256=(
                    candidate.source_sha256
                ),
                source_text=(
                    candidate.source_text
                ),
                source_page=(
                    source_page
                ),
                source_pages=(
                    source_pages
                ),
                source_block_id=(
                    candidate.source_block_id
                ),
                source_reference=(
                    source_reference
                ),
                source_location_status=(
                    candidate.source_location_status
                ),
            )
        )

    if issues:
        return SemanticIngressResult(
            status=(
                "SEMANTIC_REVIEW_REQUIRED"
            ),
            case=updated_case,
            candidates=candidates,
            evidence=evidence,
            issues=issues,
        )

    return SemanticIngressResult(
        status=(
            "READY_FOR_FORMAL_WORKFLOW"
        ),
        case=updated_case,
        candidates=candidates,
        evidence=evidence,
        issues=[],
    )
