from dataclasses import dataclass
from decimal import Decimal
from typing import Literal


MethodResultType = Literal[
    "value",
    "lower_bound",
]

MethodStatus = Literal[
    "PASS",
    "FAIL",
    "INDETERMINATE",
]

MethodRole = Literal[
    "current_verification",
    "cross_check",
    "unspecified",
]


# =========================================================
# DATA MODELS
# =========================================================


@dataclass(frozen=True)
class MetricRequirement:
    metric: str
    operator: str
    target: Decimal
    unit: str


@dataclass(frozen=True)
class MethodResult:
    method: str
    result_type: MethodResultType
    value: Decimal
    unit: str
    role: MethodRole = "unspecified"


@dataclass(frozen=True)
class MethodEvaluation:
    method: str
    status: MethodStatus
    value: Decimal
    result_type: MethodResultType
    role: MethodRole
    reason: str


@dataclass(frozen=True)
class MethodCheckResult:
    requirement: MetricRequirement
    evaluations: list[MethodEvaluation]

    disagreement_found: bool
    indeterminate_found: bool

    verification_risk_found: bool


# =========================================================
# RESULT EVALUATION
# =========================================================


def evaluate_method_result(
    requirement: MetricRequirement,
    result: MethodResult,
) -> MethodEvaluation:

    if result.unit != requirement.unit:

        raise ValueError(
            f"Unit mismatch: "
            f"{result.method}={result.unit}, "
            f"requirement={requirement.unit}"
        )

    if requirement.operator != ">=":

        raise ValueError(
            "현재 MVP Method Checker는 "
            "operator '>='만 지원합니다."
        )

    target = requirement.target
    value = result.value


    # -----------------------------------------------------
    # EXACT VALUE
    # -----------------------------------------------------

    if result.result_type == "value":

        if value >= target:

            return MethodEvaluation(
                method=result.method,
                status="PASS",
                value=value,
                result_type=result.result_type,
                role=result.role,
                reason=f"{value} >= {target}",
            )

        return MethodEvaluation(
            method=result.method,
            status="FAIL",
            value=value,
            result_type=result.result_type,
            role=result.role,
            reason=f"{value} < {target}",
        )


    # -----------------------------------------------------
    # LOWER BOUND
    # -----------------------------------------------------

    if result.result_type == "lower_bound":

        if value >= target:

            return MethodEvaluation(
                method=result.method,
                status="PASS",
                value=value,
                result_type=result.result_type,
                role=result.role,
                reason=(
                    f"lower bound {value} "
                    f">= target {target}"
                ),
            )

        return MethodEvaluation(
            method=result.method,
            status="INDETERMINATE",
            value=value,
            result_type=result.result_type,
            role=result.role,
            reason=(
                f"lower bound {value} "
                f"< target {target}; "
                "actual value may still pass"
            ),
        )


    raise ValueError(
        "지원하지 않는 result_type: "
        f"{result.result_type}"
    )


# =========================================================
# METHOD CROSS-CHECK
# =========================================================


def check_method_disagreement(
    requirement: MetricRequirement,
    method_results: list[MethodResult],
) -> MethodCheckResult:

    if not method_results:

        raise ValueError(
            "Method Result가 없습니다."
        )


    evaluations = [
        evaluate_method_result(
            requirement=requirement,
            result=result,
        )
        for result in method_results
    ]


    statuses = {
        evaluation.status
        for evaluation in evaluations
    }


    # -----------------------------------------------------
    # GENERIC DISAGREEMENT
    # -----------------------------------------------------

    disagreement_found = (
        "PASS" in statuses
        and
        "FAIL" in statuses
    )


    # -----------------------------------------------------
    # INDETERMINATE
    # -----------------------------------------------------

    indeterminate_found = (
        "INDETERMINATE" in statuses
    )


    # -----------------------------------------------------
    # VERIFICATION SUFFICIENCY RISK
    #
    # Current Verification은 PASS하지만
    # Cross-check Method 중 하나 이상이 FAIL하면
    # 현재 Verification Method의 충분성 검토 필요.
    # -----------------------------------------------------

    current_verification_pass = any(
        evaluation.role
        == "current_verification"

        and

        evaluation.status
        == "PASS"

        for evaluation in evaluations
    )


    cross_check_fail = any(
        evaluation.role
        == "cross_check"

        and

        evaluation.status
        == "FAIL"

        for evaluation in evaluations
    )


    verification_risk_found = (
        current_verification_pass
        and
        cross_check_fail
    )


    return MethodCheckResult(
        requirement=requirement,
        evaluations=evaluations,

        disagreement_found=disagreement_found,
        indeterminate_found=indeterminate_found,

        verification_risk_found=verification_risk_found,
    )