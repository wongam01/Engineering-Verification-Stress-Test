from dataclasses import dataclass

from src.core.assurance_readiness import (
    AssuranceReadinessResult,
    evaluate_assurance_readiness,
)

from src.core.human_review_gate import (
    HumanReviewGateResult,
    HumanReviewRecord,
)

from src.core.models import (
    EngineeringCase,
)

from src.core.pipeline import (
    PipelineResult,
    run_pipeline,
)

from src.core.review_completeness import (
    evaluate_case_human_review_gate,
)

from src.core.scope_boundary import (
    ScopeAssessmentResult,
    assess_case_scope,
)


# =========================================================
# ASSURED PIPELINE RESULT
# =========================================================

@dataclass
class AssuredPipelineResult:
    """
    자동 분석 Scope,
    Engineering Evidence,
    Human Review를 통과한 뒤에만
    Deterministic Core를 실행한 결과.
    """

    status: str

    scope_assessment: (
        ScopeAssessmentResult
    )

    assurance_readiness: (
        AssuranceReadinessResult | None
    ) = None

    human_review: (
        HumanReviewGateResult | None
    ) = None

    pipeline_result: (
        PipelineResult | None
    ) = None

    @property
    def core_executed(self) -> bool:
        return (
            self.pipeline_result
            is not None
        )


# =========================================================
# ASSURED PIPELINE
# =========================================================

def run_assured_pipeline(
    case: EngineeringCase,
    review_records: list[
        HumanReviewRecord
    ],
    generate_patches: bool = True,
) -> AssuredPipelineResult:
    """
    현업용 안전 실행 경로.

    1. 자동 Stress Test 지원 범위 확인
    2. Feasible Domain Evidence 확인
    3. 필수 Human Review 확인
    4. 모든 Gate가 통과한 경우에만
       기존 Deterministic Core 실행

    FEA / CFD / Fatigue 등 외부 Physics가
    필요한 문제는 Solver에 넘기지 않는다.
    """

    # -----------------------------------------------------
    # GATE 0
    # SCOPE BOUNDARY
    # -----------------------------------------------------

    scope_assessment = (
        assess_case_scope(
            case
        )
    )

    if not scope_assessment.supported:
        return AssuredPipelineResult(
            status=(
                scope_assessment.status
            ),
            scope_assessment=(
                scope_assessment
            ),
        )

    # -----------------------------------------------------
    # GATE 1
    # FEASIBLE DOMAIN EVIDENCE
    # -----------------------------------------------------

    readiness = (
        evaluate_assurance_readiness(
            case
        )
    )

    if not readiness.ready:
        return AssuredPipelineResult(
            status=(
                "ASSURANCE_NOT_READY"
            ),
            scope_assessment=(
                scope_assessment
            ),
            assurance_readiness=(
                readiness
            ),
        )

    # -----------------------------------------------------
    # GATE 2
    # HUMAN REVIEW
    # -----------------------------------------------------

    human_review = (
        evaluate_case_human_review_gate(
            case,
            review_records,
        )
    )

    if (
        not human_review.ready_for_solver
    ):
        return AssuredPipelineResult(
            status=(
                "HUMAN_REVIEW_BLOCKED"
            ),
            scope_assessment=(
                scope_assessment
            ),
            assurance_readiness=(
                readiness
            ),
            human_review=(
                human_review
            ),
        )

    # -----------------------------------------------------
    # DETERMINISTIC CORE
    # -----------------------------------------------------

    pipeline_result = run_pipeline(
        case,
        generate_patches=(
            generate_patches
        ),
    )

    return AssuredPipelineResult(
        status=pipeline_result.status,
        scope_assessment=(
            scope_assessment
        ),
        assurance_readiness=(
            readiness
        ),
        human_review=(
            human_review
        ),
        pipeline_result=(
            pipeline_result
        ),
    )