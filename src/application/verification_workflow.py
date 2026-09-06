from collections.abc import Sequence

from src.application.models import (
    EvidenceTrace,
    VerificationWorkflowResult,
)
from src.application.evidence_trace import (
    assemble_workflow_evidence,
)
from src.core.assurance_report import (
    build_assurance_report,
    render_assurance_report,
)
from src.core.assured_pipeline import (
    run_assured_pipeline,
)
from src.core.human_review_gate import (
    HumanReviewRecord,
)
from src.core.models import (
    EngineeringCase,
)
from src.core.review_completeness import (
    build_required_review_targets,
)


def run_verification_workflow(
    case: EngineeringCase,
    review_records: Sequence[
        HumanReviewRecord
    ],
    *,
    evidence: Sequence[
        EvidenceTrace
    ] | None = None,
    generate_patches: bool = True,
) -> VerificationWorkflowResult:
    """
    Engineering Verification Stress Test의
    Application-level 단일 실행 경로.

    이 함수는 기존 검증된 모듈을 orchestration만 한다.

    순서:
    1. Human Review target 생성
    2. Assured Pipeline 실행
       - Scope Gate
       - Feasible Evidence Gate
       - Human Review Gate
       - Validated Deterministic Core
    3. 기존 Pipeline 결과로 Assurance Report 생성
    4. UI/CLI가 사용할 단일 WorkflowResult 반환

    중요:
    - Solver logic을 새로 구현하지 않는다.
    - Validation logic을 새로 구현하지 않는다.
    - Core 결과를 재계산하지 않는다.
    - Gate를 우회하지 않는다.
    """

    records = list(
        review_records
    )

    traces = (
        assemble_workflow_evidence(
            case,
            evidence,
        )
    )

    required_targets = (
        build_required_review_targets(
            case
        )
    )

    assured_result = (
        run_assured_pipeline(
            case,
            review_records=records,
            generate_patches=(
                generate_patches
            ),
        )
    )

    assurance_report = (
        build_assurance_report(
            case_name=case.name,
            pipeline_result=(
                assured_result
                .pipeline_result
            ),
        )
    )

    rendered_report = (
        render_assurance_report(
            assurance_report
        )
    )

    return VerificationWorkflowResult(
        status=assured_result.status,
        case=case,
        required_review_targets=(
            required_targets
        ),
        review_records=records,
        assured_result=assured_result,
        assurance_report=(
            assurance_report
        ),
        rendered_report=(
            rendered_report
        ),
        evidence=traces,
    )
