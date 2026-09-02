from dataclasses import dataclass, field
from typing import Any

from src.core.pipeline import PipelineResult

from src.core.method_case_io import (
    MethodCaseData,
    load_method_case,
)

from src.core.method_checker import (
    check_method_disagreement,
    evaluate_method_result,
)


# =========================================================
# STATE-SPACE EVIDENCE
# =========================================================

@dataclass
class EscapeEvidence:
    """
    하나의 Requirement에서 발견된
    Verification Escape 요약.
    """

    requirement_id: str
    requirement_type: str

    worst_violation: float
    actual_value: float | None
    direction: str | None

    state: dict[str, float] = field(
        default_factory=dict
    )

    selected_patch_description: (
        str | None
    ) = None

    selected_patch_closes_escape: (
        bool | None
    ) = None

    selected_patch_practical: (
        bool | None
    ) = None


@dataclass
class StateSpaceEvidence:
    """
    F ∩ V ∩ ¬R 기반
    State-space Stress Test 결과.
    """

    evaluated: bool

    pipeline_status: str

    escape_found: bool = False

    requirements_tested: int = 0

    escapes_found: int = 0

    no_escape_found: int = 0

    solver_indeterminate_found: bool = False

    solver_indeterminate_count: int = 0

    requirement_statuses: dict[
        str,
        str,
    ] = field(
        default_factory=dict
    )

    indeterminate_reasons: dict[
        str,
        str,
    ] = field(
        default_factory=dict
    )

    escapes: list[
        EscapeEvidence
    ] = field(
        default_factory=list
    )


# =========================================================
# METHOD EVIDENCE
# =========================================================

@dataclass
class MethodEvidenceItem:
    """
    하나의 Engineering Method 결과.
    """

    method: str
    role: str

    result_type: str

    value: str
    unit: str

    status: str


@dataclass
class MethodCrossCheckEvidence:
    """
    Engineering Method Cross-check 결과.
    """

    evaluated: bool

    requirement: str | None = None

    methods: list[
        MethodEvidenceItem
    ] = field(
        default_factory=list
    )

    disagreement_found: bool = False

    indeterminate_found: bool = False

    verification_risk_found: bool = False


# =========================================================
# ASSURANCE REPORT
# =========================================================

@dataclass
class AssuranceReport:
    """
    서로 다른 Verification Assurance Evidence를
    하나의 결과 구조로 묶는다.

    실제 제품의 안전 여부를 판정하는 모델이 아니다.
    """

    case_name: str

    overall_status: str

    state_space: StateSpaceEvidence

    method_cross_check: MethodCrossCheckEvidence

    source: dict[str, Any] | None = None


# =========================================================
# STATE-SPACE BUILDER
# =========================================================

def build_state_space_evidence(
    pipeline_result: PipelineResult | None,
) -> StateSpaceEvidence:
    """
    기존 Core Pipeline 결과를
    Assurance Report용 구조로 변환한다.

    Solver를 다시 실행하지 않는다.
    """

    if pipeline_result is None:
        return StateSpaceEvidence(
            evaluated=False,
            pipeline_status="NOT_EVALUATED",
        )

    escapes = []

    requirement_statuses = {}

    indeterminate_reasons = {}

    for requirement_result in (
        pipeline_result.requirement_results
    ):
        stress = (
            requirement_result.stress_result
        )

        if (
            stress.solver_status
            == "UNKNOWN"
        ):
            requirement_statuses[
                stress.requirement_id
            ] = "INDETERMINATE"

            indeterminate_reasons[
                stress.requirement_id
            ] = (
                stress.solver_reason
                or
                "unknown"
            )

            continue

        if stress.escape_found:
            requirement_statuses[
                stress.requirement_id
            ] = "ESCAPE"

        else:
            requirement_statuses[
                stress.requirement_id
            ] = "NO ESCAPE"

            continue

        selected_patch = (
            requirement_result.selected_patch
        )

        patch_description = None
        patch_closes_escape = None
        patch_practical = None

        if selected_patch is not None:
            patch_description = (
                selected_patch
                .candidate
                .description
            )

            patch_closes_escape = (
                selected_patch.closes_escape
            )

            patch_practical = (
                selected_patch.model_closure_candidate
            )

        escapes.append(
            EscapeEvidence(
                requirement_id=(
                    stress.requirement_id
                ),
                requirement_type=(
                    stress.requirement_type
                ),
                worst_violation=(
                    stress.worst_violation
                ),
                actual_value=(
                    stress.actual_value
                ),
                direction=(
                    stress.direction
                ),
                state=dict(
                    stress.state
                ),
                selected_patch_description=(
                    patch_description
                ),
                selected_patch_closes_escape=(
                    patch_closes_escape
                ),
                selected_patch_practical=(
                    patch_practical
                ),
            )
        )

    requirements_tested = len(
        requirement_statuses
    )

    escapes_found = len(
        escapes
    )

    solver_indeterminate_count = len(
        indeterminate_reasons
    )

    no_escape_found = sum(
        1
        for status
        in requirement_statuses.values()
        if status == "NO ESCAPE"
    )

    return StateSpaceEvidence(
        evaluated=True,
        pipeline_status=(
            pipeline_result.status
        ),
        escape_found=(
            escapes_found > 0
        ),
        requirements_tested=(
            requirements_tested
        ),
        escapes_found=(
            escapes_found
        ),
        no_escape_found=(
            no_escape_found
        ),
        solver_indeterminate_found=(
            solver_indeterminate_count > 0
        ),
        solver_indeterminate_count=(
            solver_indeterminate_count
        ),
        requirement_statuses=(
            requirement_statuses
        ),
        indeterminate_reasons=(
            indeterminate_reasons
        ),
        escapes=escapes,
    )


# =========================================================
# METHOD BUILDER
# =========================================================

def build_method_cross_check_evidence(
    method_case: MethodCaseData | None,
) -> MethodCrossCheckEvidence:
    """
    기존 Method Checker 결과를
    Assurance Report용 구조로 변환한다.

    Engineering 계산식을 새로 구현하지 않는다.
    """

    if method_case is None:
        return MethodCrossCheckEvidence(
            evaluated=False,
        )

    requirement = method_case.requirement

    check = check_method_disagreement(
        requirement,
        method_case.methods,
    )

    methods = []

    for method in method_case.methods:
        evaluation = evaluate_method_result(
            requirement,
            method,
        )

        methods.append(
            MethodEvidenceItem(
                method=method.method,
                role=method.role,
                result_type=(
                    method.result_type
                ),
                value=str(
                    method.value
                ),
                unit=method.unit,
                status=(
                    evaluation.status
                ),
            )
        )

    requirement_text = (
        f"{requirement.metric} "
        f"{requirement.operator} "
        f"{requirement.target} "
        f"{requirement.unit}"
    )

    return MethodCrossCheckEvidence(
        evaluated=True,
        requirement=requirement_text,
        methods=methods,
        disagreement_found=(
            check.disagreement_found
        ),
        indeterminate_found=(
            check.indeterminate_found
        ),
        verification_risk_found=(
            check.verification_risk_found
        ),
    )


# =========================================================
# OVERALL STATUS
# =========================================================

def determine_assurance_status(
    state_space: StateSpaceEvidence,
    method_cross_check: MethodCrossCheckEvidence,
) -> str:
    """
    여러 Assurance Evidence를
    deterministic rule로 통합한다.

    주의:
    이 status는 제품 안전 판정이 아니다.
    """

    if (
        state_space.evaluated
        and
        state_space.pipeline_status
        == "INVALID_INPUT"
    ):
        return "INVALID_INPUT"

    if (
        state_space.evaluated
        and
        state_space.pipeline_status
        == "INCONSISTENT_MODEL"
    ):
        return "INCONSISTENT_MODEL"

    verification_gap = (
        state_space.escape_found
    )

    solver_indeterminate = (
        state_space
        .solver_indeterminate_found
    )

    verification_risk = (
        method_cross_check
        .verification_risk_found
    )

    method_disagreement = (
        method_cross_check
        .disagreement_found
    )

    indeterminate = (
        method_cross_check
        .indeterminate_found
    )

    method_issue = (
        verification_risk
        or
        method_disagreement
        or
        indeterminate
    )

    if (
        verification_gap
        and
        method_issue
    ):
        return (
            "MULTIPLE_ASSURANCE_ISSUES"
        )

    if verification_gap:
        return (
            "VERIFICATION_GAP_FOUND"
        )

    if solver_indeterminate:
        return "INDETERMINATE"

    if verification_risk:
        return (
            "METHOD_RISK_FOUND"
        )

    if method_disagreement:
        return (
            "METHOD_DISAGREEMENT_FOUND"
        )

    if indeterminate:
        return "INDETERMINATE"

    if (
        not state_space.evaluated
        and
        not method_cross_check.evaluated
    ):
        return "NOT_EVALUATED"

    return (
        "NO_ISSUE_FOUND_IN_EXECUTED_CHECKS"
    )


# =========================================================
# REPORT BUILDER
# =========================================================

def build_assurance_report(
    case_name: str,
    pipeline_result: PipelineResult | None = None,
    method_case: MethodCaseData | None = None,
) -> AssuranceReport:
    """
    기존 분석 결과들을 하나의
    Verification Assurance Report로 묶는다.
    """

    state_space = (
        build_state_space_evidence(
            pipeline_result
        )
    )

    method_cross_check = (
        build_method_cross_check_evidence(
            method_case
        )
    )

    overall_status = (
        determine_assurance_status(
            state_space,
            method_cross_check,
        )
    )

    source = None

    if method_case is not None:
        source = method_case.source

    return AssuranceReport(
        case_name=case_name,
        overall_status=overall_status,
        state_space=state_space,
        method_cross_check=(
            method_cross_check
        ),
        source=source,
    )


# =========================================================
# TEXT RENDERER
# =========================================================

def render_assurance_report(
    report: AssuranceReport,
) -> str:
    """
    AssuranceReport를 사람이 읽을 수 있는
    deterministic text report로 변환한다.
    """

    lines = []

    lines.append(
        "========================================"
    )

    lines.append(
        " VERIFICATION ASSURANCE REPORT"
    )

    lines.append(
        "========================================"
    )

    lines.append("")

    lines.append(
        f"Case: {report.case_name}"
    )

    lines.append("")

    # =====================================================
    # STATE-SPACE
    # =====================================================

    lines.append(
        "[1] STATE-SPACE STRESS TEST"
    )

    lines.append(
        "----------------------------------------"
    )

    if not report.state_space.evaluated:
        lines.append(
            "Status: NOT EVALUATED"
        )

    else:
        lines.append(
            "Pipeline Status: "
            f"{report.state_space.pipeline_status}"
        )

        lines.append(
            "Escape Found   : "
            f"{report.state_space.escape_found}"
        )

        lines.append(
            "Requirements Tested : "
            f"{report.state_space.requirements_tested}"
        )

        lines.append(
            "Escapes Found       : "
            f"{report.state_space.escapes_found}"
        )

        lines.append(
            "No Escape Found     : "
            f"{report.state_space.no_escape_found}"
        )

        lines.append(
            "Solver Indeterminate: "
            f"{report.state_space.solver_indeterminate_found}"
        )

        lines.append(
            "Indeterminate Count : "
            f"{report.state_space.solver_indeterminate_count}"
        )

        if (
            report
            .state_space
            .requirement_statuses
        ):
            lines.append("")

            lines.append(
                "Requirement Summary:"
            )

            for (
                requirement_id,
                status,
            ) in (
                report
                .state_space
                .requirement_statuses
                .items()
            ):
                lines.append(
                    f"  {requirement_id} : {status}"
                )

        if (
            report
            .state_space
            .indeterminate_reasons
        ):
            lines.append("")

            lines.append(
                "Indeterminate Solver Results:"
            )

            for (
                requirement_id,
                reason,
            ) in (
                report
                .state_space
                .indeterminate_reasons
                .items()
            ):
                lines.append(
                    f"  {requirement_id}: {reason}"
                )

        for escape in (
            report.state_space.escapes
        ):
            lines.append("")

            lines.append(
                "Requirement: "
                f"{escape.requirement_id}"
            )

            lines.append(
                "Type       : "
                f"{escape.requirement_type}"
            )

            lines.append(
                "Worst Violation: "
                f"{escape.worst_violation:.6g}"
            )

            lines.append(
                "Direction      : "
                f"{escape.direction}"
            )

            if escape.state:
                lines.append(
                    "Counterexample State:"
                )

                for (
                    variable,
                    value,
                ) in sorted(
                    escape.state.items()
                ):
                    lines.append(
                        f"  {variable} = {value}"
                    )

            if (
                escape
                .selected_patch_description
                is not None
            ):
                lines.append(
                    "Mathematical Patch Candidate:"
                )

                lines.append(
                    "  "
                    + escape
                    .selected_patch_description
                )

                lines.append(
                    "  Closes Modeled Escape      : "
                    f"{escape.selected_patch_closes_escape}"
                )

                lines.append(
                    "  Model Closure Candidate    : "
                    f"{escape.selected_patch_practical}"
                )

                lines.append(
                    "  Engineering Review Required: "
                    "True"
                )

                lines.append(
                    "  External Feasibility Check : "
                    "NOT PERFORMED"
                )

    lines.append("")

    # =====================================================
    # METHOD CROSS-CHECK
    # =====================================================

    lines.append(
        "[2] ENGINEERING METHOD CROSS-CHECK"
    )

    lines.append(
        "----------------------------------------"
    )

    method_section = (
        report.method_cross_check
    )

    if not method_section.evaluated:
        lines.append(
            "Status: NOT EVALUATED"
        )

    else:
        lines.append(
            "Requirement: "
            f"{method_section.requirement}"
        )

        lines.append("")

        for method in method_section.methods:
            display_value = method.value

            if method.result_type == "lower_bound":
                display_value = (
                    f"lower bound {display_value}"
                )

            lines.append(
                f"{method.method}: "
                f"{display_value} "
                f"{method.unit} "
                f"→ {method.status} "
                f"[{method.role}]"
            )

        lines.append("")

        lines.append(
            "Method Disagreement     : "
            f"{method_section.disagreement_found}"
        )

        lines.append(
            "Indeterminate Found     : "
            f"{method_section.indeterminate_found}"
        )

        lines.append(
            "Verification Risk Found : "
            f"{method_section.verification_risk_found}"
        )

    # =====================================================
    # SOURCE
    # =====================================================

    if report.source is not None:
        lines.append("")

        lines.append(
            "[3] SOURCE TRACEABILITY"
        )

        lines.append(
            "----------------------------------------"
        )

        regulatory = (
            report.source.get(
                "regulatory_context",
                {},
            )
        )

        benchmark = (
            report.source.get(
                "benchmark_source",
                {},
            )
        )

        if regulatory:
            lines.append(
                "Regulatory Context:"
            )

            lines.append(
                "  "
                + str(
                    regulatory.get(
                        "document",
                        "UNKNOWN",
                    )
                )
            )

        if benchmark:
            lines.append(
                "Engineering Benchmark:"
            )

            lines.append(
                "  "
                + str(
                    benchmark.get(
                        "document_id",
                        "UNKNOWN",
                    )
                )
            )

            lines.append(
                "  "
                + str(
                    benchmark.get(
                        "section",
                        "UNKNOWN",
                    )
                )
            )

    # =====================================================
    # OVERALL STATUS
    # =====================================================

    lines.append("")

    lines.append(
        "[4] ASSURANCE STATUS"
    )

    lines.append(
        "----------------------------------------"
    )

    lines.append(
        report.overall_status
    )

    lines.append("")

    lines.append(
        "NOTE: This status evaluates the "
        "verification evidence modeled and "
        "executed by this prototype. "
        "It is not a declaration of absolute "
        "physical system safety."
    )

    return "\n".join(lines)


# =========================================================
# MANUAL CER DEMO
# =========================================================

def main():
    """
    CER Method Case를
    통합 Assurance Report 형식으로 출력한다.
    """

    method_case = load_method_case(
        "samples/cer_dent_method_case.json"
    )

    case_name = (
        method_case.case_name
        or
        method_case.case_id
        or
        "UNKNOWN_CASE"
    )

    report = build_assurance_report(
        case_name=case_name,
        method_case=method_case,
    )

    print()
    print(
        render_assurance_report(
            report
        )
    )
    print()


if __name__ == "__main__":
    main()
