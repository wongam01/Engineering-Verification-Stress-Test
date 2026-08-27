from dataclasses import dataclass, field

from src.core.models import (
    EngineeringCase,
    RequirementSpec,
)


# =========================================================
# RESULT
# =========================================================

@dataclass
class ValidationIssue:
    """
    입력 데이터에서 발견한 하나의 문제.
    """

    location: str
    message: str


@dataclass
class ValidationResult:
    """
    전체 입력 검증 결과.
    """

    valid: bool

    issues: list[
        ValidationIssue
    ] = field(
        default_factory=list
    )


# =========================================================
# SUPPORTED CONSTRAINT TYPES
# =========================================================

SUPPORTED_TYPES = {
    "range",
    "difference_min",
    "sum_upper",
}


# =========================================================
# VARIABLE VALIDATION
# =========================================================

def validate_variables(
    case: EngineeringCase,
    issues: list[ValidationIssue],
):
    """
    변수 자체의 범위를 검사한다.
    """

    for (
        name,
        variable,
    ) in case.variables.items():

        # ---------------------------------------------
        # FEASIBLE RANGE
        # ---------------------------------------------

        if (
            variable.feasible_min
            > variable.feasible_max
        ):

            issues.append(
                ValidationIssue(
                    location=f"Variable {name}",
                    message=(
                        "feasible_min이 "
                        "feasible_max보다 큽니다."
                    ),
                )
            )

        # ---------------------------------------------
        # VERIFICATION RANGE
        # ---------------------------------------------

        if (
            variable.verification_min
            > variable.verification_max
        ):

            issues.append(
                ValidationIssue(
                    location=f"Variable {name}",
                    message=(
                        "verification_min이 "
                        "verification_max보다 큽니다."
                    ),
                )
            )

        # ---------------------------------------------
        # NOMINAL
        # ---------------------------------------------

        if not (
            variable.feasible_min
            <= variable.nominal
            <= variable.feasible_max
        ):

            issues.append(
                ValidationIssue(
                    location=f"Variable {name}",
                    message=(
                        "Nominal 값이 "
                        "Feasible Domain 밖에 있습니다."
                    ),
                )
            )

        # ---------------------------------------------
        # VERIFICATION / FEASIBLE OVERLAP
        # ---------------------------------------------

        no_overlap = (
            variable.verification_max
            < variable.feasible_min
            or
            variable.verification_min
            > variable.feasible_max
        )

        if no_overlap:

            issues.append(
                ValidationIssue(
                    location=f"Variable {name}",
                    message=(
                        "Verification Range와 "
                        "Feasible Domain이 겹치지 않습니다."
                    ),
                )
            )


# =========================================================
# UNIT CHECK
# =========================================================

def validate_constraint_units(
    case: EngineeringCase,
    constraint: RequirementSpec,
    location: str,
    issues: list[ValidationIssue],
):
    """
    하나의 Constraint가 참조하는 변수들의
    Unit이 Constraint Unit과 일치하는지 확인한다.
    """

    for variable_name in (
        constraint.referenced_variables()
    ):

        if variable_name not in case.variables:
            continue

        variable_unit = (
            case.variables[
                variable_name
            ].unit
        )

        if (
            variable_unit
            != constraint.unit
        ):

            issues.append(
                ValidationIssue(
                    location=location,
                    message=(
                        f"Unit 불일치: "
                        f"{variable_name}="
                        f"{variable_unit}, "
                        f"Constraint="
                        f"{constraint.unit}"
                    ),
                )
            )


# =========================================================
# ONE CONSTRAINT
# =========================================================

def validate_constraint(
    case: EngineeringCase,
    constraint: RequirementSpec,
    location: str,
    issues: list[ValidationIssue],
):
    """
    하나의 Requirement 또는
    Verification Constraint를 검사한다.
    """

    # -----------------------------------------------------
    # TYPE
    # -----------------------------------------------------

    if (
        constraint.type
        not in SUPPORTED_TYPES
    ):

        issues.append(
            ValidationIssue(
                location=location,
                message=(
                    "지원하지 않는 Constraint Type: "
                    f"{constraint.type}"
                ),
            )
        )

        return

    # -----------------------------------------------------
    # REFERENCED VARIABLES
    # -----------------------------------------------------

    referenced = (
        constraint.referenced_variables()
    )

    for variable_name in referenced:

        if (
            variable_name
            not in case.variables
        ):

            issues.append(
                ValidationIssue(
                    location=location,
                    message=(
                        "존재하지 않는 변수 참조: "
                        f"{variable_name}"
                    ),
                )
            )

    # Unit 검사는 존재하는 변수만 대상으로 한다.
    validate_constraint_units(
        case,
        constraint,
        location,
        issues,
    )

    # -----------------------------------------------------
    # RANGE
    # -----------------------------------------------------

    if constraint.type == "range":

        if constraint.variable is None:

            issues.append(
                ValidationIssue(
                    location=location,
                    message=(
                        "range Constraint에 "
                        "variable이 없습니다."
                    ),
                )
            )

        if (
            constraint.min_value is None
            or
            constraint.max_value is None
        ):

            issues.append(
                ValidationIssue(
                    location=location,
                    message=(
                        "range Constraint에 "
                        "min/max 값이 없습니다."
                    ),
                )
            )

        elif (
            constraint.min_value
            > constraint.max_value
        ):

            issues.append(
                ValidationIssue(
                    location=location,
                    message=(
                        "Constraint의 min이 "
                        "max보다 큽니다."
                    ),
                )
            )

    # -----------------------------------------------------
    # DIFFERENCE MIN
    # -----------------------------------------------------

    elif (
        constraint.type
        == "difference_min"
    ):

        if (
            constraint.left is None
            or
            constraint.right is None
        ):

            issues.append(
                ValidationIssue(
                    location=location,
                    message=(
                        "difference_min Constraint에 "
                        "left/right 변수가 없습니다."
                    ),
                )
            )

        if (
            constraint.min_value
            is None
        ):

            issues.append(
                ValidationIssue(
                    location=location,
                    message=(
                        "difference_min Constraint에 "
                        "최소값이 없습니다."
                    ),
                )
            )

    # -----------------------------------------------------
    # SUM UPPER
    # -----------------------------------------------------

    elif constraint.type == "sum_upper":

        if (
            len(
                constraint.variables
            )
            == 0
        ):

            issues.append(
                ValidationIssue(
                    location=location,
                    message=(
                        "sum_upper Constraint에 "
                        "변수가 없습니다."
                    ),
                )
            )

        if (
            constraint.limit
            is None
        ):

            issues.append(
                ValidationIssue(
                    location=location,
                    message=(
                        "sum_upper Constraint에 "
                        "limit 값이 없습니다."
                    ),
                )
            )


# =========================================================
# CONSTRAINT GROUP
# =========================================================

def validate_constraint_group(
    case: EngineeringCase,
    constraints: list[RequirementSpec],
    group_name: str,
    issues: list[ValidationIssue],
):
    """
    Requirement 또는 Verification Constraint
    그룹 전체를 검사한다.
    """

    seen_ids = set()

    for constraint in constraints:

        location = (
            f"{group_name} "
            f"{constraint.id}"
        )

        # ---------------------------------------------
        # DUPLICATE ID
        # ---------------------------------------------

        if constraint.id in seen_ids:

            issues.append(
                ValidationIssue(
                    location=location,
                    message=(
                        "중복된 Constraint ID입니다."
                    ),
                )
            )

        seen_ids.add(
            constraint.id
        )

        # ---------------------------------------------
        # CONTENT
        # ---------------------------------------------

        validate_constraint(
            case,
            constraint,
            location,
            issues,
        )


# =========================================================
# MAIN VALIDATOR
# =========================================================

def validate_case(
    case: EngineeringCase,
) -> ValidationResult:
    """
    EngineeringCase 전체를 검사한다.

    검사 순서:

    1. 변수 범위
    2. 설계 Requirement
    3. Verification Plan 관계조건

    문제가 하나라도 있으면
    Solver 실행 전에 차단할 수 있다.
    """

    issues: list[
        ValidationIssue
    ] = []

    # -----------------------------------------------------
    # VARIABLES
    # -----------------------------------------------------

    validate_variables(
        case,
        issues,
    )

    # -----------------------------------------------------
    # REQUIREMENTS
    # -----------------------------------------------------

    validate_constraint_group(
        case=case,
        constraints=case.requirements,
        group_name="Requirement",
        issues=issues,
    )

    # -----------------------------------------------------
    # VERIFICATION PLAN
    # -----------------------------------------------------

    validate_constraint_group(
        case=case,
        constraints=(
            case.verification_constraints
        ),
        group_name=(
            "Verification Constraint"
        ),
        issues=issues,
    )

    return ValidationResult(
        valid=(
            len(issues) == 0
        ),
        issues=issues,
    )