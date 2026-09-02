from dataclasses import dataclass, field

from src.core.models import (
    EngineeringCase,
    RequirementSpec,
)

from src.core.validator import (
    SUPPORTED_TYPES,
)


# =========================================================
# EXTERNAL ANALYSIS TYPES
# =========================================================

EXTERNAL_ANALYSIS_TYPES = {
    "fea",
    "cfd",
    "fatigue_analysis",
    "thermal_analysis",
    "fracture_mechanics",
}


# =========================================================
# SCOPE ISSUE
# =========================================================

@dataclass(frozen=True)
class ScopeIssue:
    """
    현재 Verification Stress Test Core의
    자동 분석 범위를 벗어난 Constraint.
    """

    location: str

    constraint_id: str
    constraint_type: str

    code: str
    message: str


# =========================================================
# SCOPE RESULT
# =========================================================

@dataclass
class ScopeAssessmentResult:
    """
    Engineering Case가 현재 MVP의
    자동 Stress Test 범위 안에 있는지 나타낸다.
    """

    supported: bool

    status: str

    issues: list[
        ScopeIssue
    ] = field(
        default_factory=list
    )


# =========================================================
# SINGLE CONSTRAINT
# =========================================================

def _check_constraint_scope(
    constraint: RequirementSpec,
    location: str,
) -> ScopeIssue | None:
    """
    하나의 Constraint가 현재 Core에서
    자동 분석 가능한지 판단한다.
    """

    # -----------------------------------------------------
    # SUPPORTED
    # -----------------------------------------------------

    if (
        constraint.type
        in SUPPORTED_TYPES
    ):
        return None

    # -----------------------------------------------------
    # EXTERNAL PHYSICS / CAE
    # -----------------------------------------------------

    if (
        constraint.type
        in EXTERNAL_ANALYSIS_TYPES
    ):
        return ScopeIssue(
            location=location,
            constraint_id=constraint.id,
            constraint_type=(
                constraint.type
            ),
            code=(
                "EXTERNAL_ANALYSIS_REQUIRED"
            ),
            message=(
                "This constraint requires "
                "external engineering analysis "
                "such as CAE or a dedicated "
                "physics model."
            ),
        )

    # -----------------------------------------------------
    # OTHER UNSUPPORTED CONSTRAINT
    # -----------------------------------------------------

    return ScopeIssue(
        location=location,
        constraint_id=constraint.id,
        constraint_type=constraint.type,
        code="UNSUPPORTED_CONSTRAINT",
        message=(
            "This explicit constraint type "
            "is not supported by the current "
            "Verification Stress Test Core."
        ),
    )


# =========================================================
# CASE SCOPE ASSESSMENT
# =========================================================

def assess_case_scope(
    case: EngineeringCase,
) -> ScopeAssessmentResult:
    """
    Requirement와 Verification Constraint를
    모두 검사해서 현재 자동 분석 범위인지
    판정한다.
    """

    issues = []

    # -----------------------------------------------------
    # REQUIREMENTS
    # -----------------------------------------------------

    for requirement in (
        case.requirements
    ):
        issue = _check_constraint_scope(
            requirement,
            location=(
                f"Requirement {requirement.id}"
            ),
        )

        if issue is not None:
            issues.append(
                issue
            )

    # -----------------------------------------------------
    # VERIFICATION CONSTRAINTS
    # -----------------------------------------------------

    for constraint in (
        case.verification_constraints
    ):
        issue = _check_constraint_scope(
            constraint,
            location=(
                "Verification Constraint "
                f"{constraint.id}"
            ),
        )

        if issue is not None:
            issues.append(
                issue
            )

    # -----------------------------------------------------
    # FULLY SUPPORTED
    # -----------------------------------------------------

    if not issues:
        return ScopeAssessmentResult(
            supported=True,
            status=(
                "AUTOMATED_STRESS_TEST_SUPPORTED"
            ),
            issues=[],
        )

    codes = {
        issue.code
        for issue
        in issues
    }

    # -----------------------------------------------------
    # UNKNOWN / UNSUPPORTED TYPE가 있으면
    # 가장 먼저 표시
    # -----------------------------------------------------

    if (
        "UNSUPPORTED_CONSTRAINT"
        in codes
    ):
        status = (
            "UNSUPPORTED_CONSTRAINT"
        )

    else:
        status = (
            "EXTERNAL_ANALYSIS_REQUIRED"
        )

    return ScopeAssessmentResult(
        supported=False,
        status=status,
        issues=issues,
    )