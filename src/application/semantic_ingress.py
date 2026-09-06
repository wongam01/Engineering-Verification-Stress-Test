from collections.abc import Callable, Sequence
from copy import deepcopy
from dataclasses import dataclass, field
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

    approved: bool = False
    applied: bool = False

    @property
    def adapter_accepted(
        self,
    ) -> bool:
        return self.adapter_result.accepted

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
            extract_explicit_source_pages(
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
