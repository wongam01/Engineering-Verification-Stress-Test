from dataclasses import dataclass, field

from src.core.models import (
    EngineeringCase,
    VariableSpec,
)


# =========================================================
# READINESS ISSUE
# =========================================================

@dataclass(frozen=True)
class ReadinessIssue:
    """
    Assurance Readiness를 방해하는
    하나의 Engineering Evidence 문제.
    """

    variable_name: str
    code: str
    message: str


# =========================================================
# READINESS RESULT
# =========================================================

@dataclass
class AssuranceReadinessResult:
    """
    Feasible Domain Evidence가
    Engineering Assurance 분석에 사용할 만큼
    준비되었는지를 나타낸다.

    이 결과는 Solver의 수학적 유효성과 별개다.
    """

    ready: bool

    status: str

    issues: list[
        ReadinessIssue
    ] = field(
        default_factory=list
    )


# =========================================================
# INTERNAL CHECK
# =========================================================

def _check_variable_evidence(
    variable_name: str,
    variable: VariableSpec,
) -> list[ReadinessIssue]:

    issues = []

    evidence = variable.feasible_evidence

    # -----------------------------------------------------
    # Evidence 자체가 없음
    # -----------------------------------------------------

    if evidence is None:
        issues.append(
            ReadinessIssue(
                variable_name=variable_name,
                code="MISSING_EVIDENCE",
                message=(
                    "Feasible Domain source "
                    "evidence is missing."
                ),
            )
        )

        return issues

    # -----------------------------------------------------
    # Source Type
    # -----------------------------------------------------

    if not evidence.source_type.strip():
        issues.append(
            ReadinessIssue(
                variable_name=variable_name,
                code="INVALID_EVIDENCE",
                message=(
                    "Feasible Domain "
                    "source_type is empty."
                ),
            )
        )

    # -----------------------------------------------------
    # Source Reference
    # -----------------------------------------------------

    if not evidence.source_reference.strip():
        issues.append(
            ReadinessIssue(
                variable_name=variable_name,
                code="INVALID_EVIDENCE",
                message=(
                    "Feasible Domain "
                    "source_reference is empty."
                ),
            )
        )

    # -----------------------------------------------------
    # Approval Status
    # -----------------------------------------------------

    allowed_statuses = {
        "approved",
        "unreviewed",
    }

    if (
        evidence.approval_status
        not in allowed_statuses
    ):
        issues.append(
            ReadinessIssue(
                variable_name=variable_name,
                code="INVALID_EVIDENCE",
                message=(
                    "Unknown Feasible Domain "
                    "approval_status: "
                    f"{evidence.approval_status}"
                ),
            )
        )

    elif (
        evidence.approval_status
        != "approved"
    ):
        issues.append(
            ReadinessIssue(
                variable_name=variable_name,
                code="UNREVIEWED_EVIDENCE",
                message=(
                    "Feasible Domain evidence "
                    "has not been approved "
                    "by an engineer."
                ),
            )
        )

    return issues


# =========================================================
# VARIABLE COLLECTION CHECK
# =========================================================

def check_feasible_domain_readiness(
    variables: dict[
        str,
        VariableSpec,
    ],
) -> AssuranceReadinessResult:
    """
    모든 Engineering 변수의
    Feasible Domain Evidence를 검사한다.
    """

    issues = []

    for (
        variable_name,
        variable,
    ) in variables.items():

        issues.extend(
            _check_variable_evidence(
                variable_name,
                variable,
            )
        )

    # -----------------------------------------------------
    # READY
    # -----------------------------------------------------

    if not issues:
        return AssuranceReadinessResult(
            ready=True,
            status="READY",
            issues=[],
        )

    # -----------------------------------------------------
    # Primary Status
    #
    # 모든 문제는 issues에 보존하고,
    # 가장 심각한 문제를 대표 status로 사용한다.
    # -----------------------------------------------------

    codes = {
        issue.code
        for issue in issues
    }

    if "INVALID_EVIDENCE" in codes:
        status = "INVALID_EVIDENCE"

    elif "MISSING_EVIDENCE" in codes:
        status = "MISSING_EVIDENCE"

    else:
        status = "UNREVIEWED_EVIDENCE"

    return AssuranceReadinessResult(
        ready=False,
        status=status,
        issues=issues,
    )


# =========================================================
# ENGINEERING CASE CHECK
# =========================================================

def evaluate_assurance_readiness(
    case: EngineeringCase,
) -> AssuranceReadinessResult:
    """
    EngineeringCase 전체의
    Feasible Domain Assurance Readiness를
    평가한다.
    """

    return check_feasible_domain_readiness(
        case.variables
    )