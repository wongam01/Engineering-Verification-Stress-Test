from collections.abc import Sequence

from src.application.models import (
    EvidenceTrace,
    VerificationWorkflowResult,
)
from src.application.evidence_trace import (
    assemble_workflow_evidence,
)
from src.core.assurance_readiness import (
    evaluate_assurance_readiness,
)
from src.core.assurance_report import (
    build_assurance_report,
    render_assurance_report,
)
from src.core.assured_pipeline import (
    AssuredPipelineResult,
)
from src.core.human_review_gate import (
    HumanReviewRecord,
)
from src.core.models import (
    EngineeringCase,
)
from src.core.patch_engine import (
    evaluate_patch_candidates,
    select_model_closure_candidate,
)
from src.core.pipeline import (
    PipelineResult,
    RequirementPipelineResult,
)
from src.core.review_completeness import (
    build_required_review_targets,
    evaluate_case_human_review_gate,
)
from src.core.scope_boundary import (
    assess_case_scope,
)
from src.core.stress_tester import (
    stress_test_case,
)
from src.core.validator import (
    validate_case,
)


def run_escape_core_pipeline(
    case: EngineeringCase,
    generate_patches: bool = True,
) -> PipelineResult:
    """
    Verification Escape 탐색 전용 Application execution path.

    Formal target:
        exists x:
        F(x) and V(x) and not R(x)

    기존 run_pipeline()의 logical-consistency pre-check는
    F와 R의 joint satisfiability를 요구할 수 있으므로,
    F and not R 상태 자체를 탐색해야 하는 이 경로의
    선행 차단 조건으로 사용하지 않는다.

    Deterministic validator, stress tester, patch engine은
    기존 Core 구현을 그대로 재사용한다.
    """

    validation = validate_case(
        case
    )

    if not validation.valid:
        return PipelineResult(
            status="INVALID_INPUT",
            validation=validation,
        )

    stress_results = stress_test_case(
        case
    )

    requirement_results = []

    for stress_result in stress_results:
        patch_evaluations = []
        selected_patch = None

        if (
            stress_result.escape_found
            and generate_patches
        ):
            patch_evaluations = (
                evaluate_patch_candidates(
                    case,
                    stress_result.requirement_id,
                )
            )

            selected_patch = (
                select_model_closure_candidate(
                    patch_evaluations
                )
            )

        requirement_results.append(
            RequirementPipelineResult(
                requirement_id=(
                    stress_result.requirement_id
                ),
                stress_result=(
                    stress_result
                ),
                patch_evaluations=(
                    patch_evaluations
                ),
                selected_patch=(
                    selected_patch
                ),
            )
        )

    escape_found = any(
        result.stress_result.escape_found
        for result
        in requirement_results
    )

    solver_indeterminate = any(
        (
            result
            .stress_result
            .solver_status
            == "UNKNOWN"
        )
        for result
        in requirement_results
    )

    if escape_found:
        status = (
            "VERIFICATION_GAP_FOUND"
        )

    elif solver_indeterminate:
        status = (
            "SOLVER_INDETERMINATE"
        )

    else:
        status = (
            "NO_ESCAPE_FOUND"
        )

    return PipelineResult(
        status=status,
        validation=validation,
        consistency=None,
        requirement_results=(
            requirement_results
        ),
    )


def run_assured_escape_pipeline(
    case: EngineeringCase,
    review_records: Sequence[
        HumanReviewRecord
    ],
    generate_patches: bool = True,
) -> AssuredPipelineResult:
    """
    Scope, evidence, Human Review gate를 통과한 경우에만
    Verification Escape stress-test path를 실행한다.
    """

    records = list(
        review_records
    )

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

    readiness = (
        evaluate_assurance_readiness(
            case
        )
    )

    if not readiness.ready:
        return AssuredPipelineResult(
            status="ASSURANCE_NOT_READY",
            scope_assessment=(
                scope_assessment
            ),
            assurance_readiness=(
                readiness
            ),
        )

    human_review = (
        evaluate_case_human_review_gate(
            case,
            records,
        )
    )

    if not human_review.ready_for_solver:
        return AssuredPipelineResult(
            status="HUMAN_REVIEW_BLOCKED",
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

    pipeline_result = (
        run_escape_core_pipeline(
            case,
            generate_patches=(
                generate_patches
            ),
        )
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


def run_verification_escape_workflow(
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
    Product-level Verification Escape workflow.
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
        run_assured_escape_pipeline(
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
        assured_result=(
            assured_result
        ),
        assurance_report=(
            assurance_report
        ),
        rendered_report=(
            rendered_report
        ),
        evidence=traces,
    )
