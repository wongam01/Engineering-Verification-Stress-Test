from collections.abc import Sequence
from dataclasses import dataclass

from src.application.semantic_ingress import (
    SemanticAnalysisResult,
    SemanticIngressResult,
    apply_semantic_approvals,
)
from src.application.verification_workflow import (
    run_verification_workflow,
)
from src.application.models import (
    VerificationWorkflowResult,
)
from src.core.human_review_gate import (
    HumanReviewRecord,
)
from src.core.models import (
    EngineeringCase,
)


@dataclass
class DocumentVerificationWorkflowResult:
    """
    Semantic Analysis → Semantic Approval →
    Formal Verification Workflow를 연결한
    Application-level 결과.
    """

    status: str

    semantic_ingress: (
        SemanticIngressResult
    )

    formal_result: (
        VerificationWorkflowResult
        | None
    ) = None

    @property
    def formal_workflow_executed(
        self,
    ) -> bool:
        return (
            self.formal_result
            is not None
        )

    @property
    def core_executed(
        self,
    ) -> bool:
        if self.formal_result is None:
            return False

        return (
            self.formal_result
            .core_executed
        )


def run_document_verification_workflow(
    base_case: EngineeringCase,
    semantic_analysis: SemanticAnalysisResult,
    approved_candidate_ids: Sequence[
        str
    ],
    review_records: Sequence[
        HumanReviewRecord
    ],
    *,
    generate_patches: bool = True,
) -> DocumentVerificationWorkflowResult:
    """
    이미 분석되어 고정된 AI Semantic Candidate를
    실제 Formal Verification Workflow로 연결한다.

    중요:
    이 함수는 AI extraction을 다시 실행하지 않는다.
    """

    ingress = (
        apply_semantic_approvals(
            base_case,
            semantic_analysis,
            approved_candidate_ids,
        )
    )

    if not ingress.ready_for_formal_workflow:
        return (
            DocumentVerificationWorkflowResult(
                status=ingress.status,
                semantic_ingress=ingress,
                formal_result=None,
            )
        )

    formal_result = (
        run_verification_workflow(
            ingress.case,
            review_records,
            evidence=ingress.evidence,
            generate_patches=(
                generate_patches
            ),
        )
    )

    return (
        DocumentVerificationWorkflowResult(
            status=formal_result.status,
            semantic_ingress=ingress,
            formal_result=formal_result,
        )
    )
