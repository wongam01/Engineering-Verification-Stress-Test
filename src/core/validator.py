from dataclasses import dataclass, field

from src.core.models import (
    EngineeringCase,
    RequirementSpec,
)


# =========================================================
# SUPPORTED CONSTRAINT TYPES
# =========================================================

SUPPORTED_REQUIREMENT_TYPES = {
    "range",
    "difference_min",
    "sum_upper",
}


# =========================================================
# VALIDATION RESULT
# =========================================================

@dataclass
class ValidationIssue:
    """
    하나의 Engineering Validation 문제.
    """

    location: str
    message: str


@dataclass
class ValidationResult:
    """
    전체 Engineering Case 검증 결과.
    """

    valid: bool

    issues: list[ValidationIssue] = field(
        default_factory=list
    )


# =========================================================
# VARIABLE VALIDATION
# =========================================================

def validate_variables(
    case: EngineeringCase,
    issues: list[ValidationIssue],
):
    """
    Variable 정의 자체를 검사한다.

    검사 항목:

    1. Unit 존재
    2. Feasible min <= max
    3. Verification min <= max
    4. Nominal이 Feasible Domain 안에 존재
    5. Verification과 Feasible Domain이
       완전히 분리되어 있지 않음
    """

    if not case.variables:

        issues.append(
            ValidationIssue(
                location="variables",
                message=(
                    "No engineering variables defined."
                ),
            )
        )

        return

    for name, variable in case.variables.items():

        location = f"Variable {name}"

        # -------------------------------------------------
        # UNIT
        # -------------------------------------------------

        if not variable.unit:

            issues.append(
                ValidationIssue(
                    location=location,
                    message="Unit is missing.",
                )
            )

        # -------------------------------------------------
        # FEASIBLE DOMAIN
        # -------------------------------------------------

        if (
            variable.feasible_min
            > variable.feasible_max
        ):

            issues.append(
                ValidationIssue(
                    location=location,
                    message=(
                        "Invalid Feasible Domain: "
                        "minimum is greater than maximum."
                    ),
                )
            )

        # -------------------------------------------------
        # VERIFICATION RANGE
        # -------------------------------------------------

        if (
            variable.verification_min
            > variable.verification_max
        ):

            issues.append(
                ValidationIssue(
                    location=location,
                    message=(
                        "Invalid Verification Range: "
                        "minimum is greater than maximum."
                    ),
                )
            )

        # -------------------------------------------------
        # NOMINAL
        # -------------------------------------------------

        if (
            variable.feasible_min
            <= variable.feasible_max
        ):

            if not (
                variable.feasible_min
                <= variable.nominal
                <= variable.feasible_max
            ):

                issues.append(
                    ValidationIssue(
                        location=location,
                        message=(
                            f"Nominal value "
                            f"{variable.nominal} "
                            "is outside the "
                            "Feasible Domain."
                        ),
                    )
                )

        # -------------------------------------------------
        # FEASIBLE / VERIFICATION INTERSECTION
        # -------------------------------------------------

        ranges_are_valid = (
            variable.feasible_min
            <= variable.feasible_max
            and
            variable.verification_min
            <= variable.verification_max
        )

        if ranges_are_valid:

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
                        location=location,
                        message=(
                            "Verification Range has "
                            "no overlap with the "
                            "Feasible Domain."
                        ),
                    )
                )


# =========================================================
# VARIABLE REFERENCE VALIDATION
# =========================================================

def variable_exists(
    case: EngineeringCase,
    requirement: RequirementSpec,
    variable_name: str,
    issues: list[ValidationIssue],
) -> bool:
    """
    Requirement가 존재하지 않는 Variable을
    참조하는지 검사한다.
    """

    if variable_name not in case.variables:

        issues.append(
            ValidationIssue(
                location=(
                    f"Requirement {requirement.id}"
                ),
                message=(
                    f"Unknown variable: "
                    f"{variable_name}"
                ),
            )
        )

        return False

    return True


# =========================================================
# UNIT VALIDATION
# =========================================================

def validate_units(
    case: EngineeringCase,
    requirement: RequirementSpec,
    variable_names: tuple[str, ...],
    issues: list[ValidationIssue],
):
    """
    현재 Prototype에서는 하나의 관계식에
    사용되는 Variable들이 같은 Unit을
    사용하는 경우만 허용한다.

    또한 Requirement의 Unit과
    Variable Unit도 같아야 한다.
    """

    existing_names = [
        name
        for name in variable_names
        if name in case.variables
    ]

    if not existing_names:
        return

    variable_units = {
        case.variables[name].unit
        for name in existing_names
    }

    # -----------------------------------------------------
    # VARIABLE끼리 UNIT MISMATCH
    # -------------------------------------------------

    if len(variable_units) > 1:

        unit_text = ", ".join(
            f"{name}="
            f"{case.variables[name].unit}"
            for name in existing_names
        )

        issues.append(
            ValidationIssue(
                location=(
                    f"Requirement {requirement.id}"
                ),
                message=(
                    "Unit mismatch between variables: "
                    + unit_text
                ),
            )
        )

        return

    # -----------------------------------------------------
    # REQUIREMENT UNIT
    # -------------------------------------------------

    if not requirement.unit:

        issues.append(
            ValidationIssue(
                location=(
                    f"Requirement {requirement.id}"
                ),
                message=(
                    "Requirement unit is missing."
                ),
            )
        )

        return

    variable_unit = next(
        iter(variable_units)
    )

    if requirement.unit != variable_unit:

        issues.append(
            ValidationIssue(
                location=(
                    f"Requirement {requirement.id}"
                ),
                message=(
                    f"Requirement unit "
                    f"{requirement.unit} "
                    f"does not match "
                    f"variable unit "
                    f"{variable_unit}."
                ),
            )
        )


# =========================================================
# RANGE REQUIREMENT
# =========================================================

def validate_range_requirement(
    case: EngineeringCase,
    requirement: RequirementSpec,
    issues: list[ValidationIssue],
):
    """
    Range Requirement 검사.

    min <= X <= max
    """

    location = (
        f"Requirement {requirement.id}"
    )

    if requirement.variable is None:

        issues.append(
            ValidationIssue(
                location=location,
                message=(
                    "Range variable is missing."
                ),
            )
        )

        return

    exists = variable_exists(
        case,
        requirement,
        requirement.variable,
        issues,
    )

    if (
        requirement.min_value is None
        or
        requirement.max_value is None
    ):

        issues.append(
            ValidationIssue(
                location=location,
                message=(
                    "Range min/max is missing."
                ),
            )
        )

        return

    if (
        requirement.min_value
        > requirement.max_value
    ):

        issues.append(
            ValidationIssue(
                location=location,
                message=(
                    "Invalid requirement range: "
                    "minimum is greater than maximum."
                ),
            )
        )

    if exists:

        validate_units(
            case,
            requirement,
            (requirement.variable,),
            issues,
        )


# =========================================================
# DIFFERENCE REQUIREMENT
# =========================================================

def validate_difference_requirement(
    case: EngineeringCase,
    requirement: RequirementSpec,
    issues: list[ValidationIssue],
):
    """
    Difference Minimum Requirement 검사.

    left - right >= minimum
    """

    location = (
        f"Requirement {requirement.id}"
    )

    if (
        requirement.left is None
        or
        requirement.right is None
    ):

        issues.append(
            ValidationIssue(
                location=location,
                message=(
                    "Difference constraint requires "
                    "left and right variables."
                ),
            )
        )

        return

    left_exists = variable_exists(
        case,
        requirement,
        requirement.left,
        issues,
    )

    right_exists = variable_exists(
        case,
        requirement,
        requirement.right,
        issues,
    )

    if requirement.min_value is None:

        issues.append(
            ValidationIssue(
                location=location,
                message=(
                    "Difference minimum value "
                    "is missing."
                ),
            )
        )

    if left_exists and right_exists:

        validate_units(
            case,
            requirement,
            (
                requirement.left,
                requirement.right,
            ),
            issues,
        )


# =========================================================
# SUM REQUIREMENT
# =========================================================

def validate_sum_requirement(
    case: EngineeringCase,
    requirement: RequirementSpec,
    issues: list[ValidationIssue],
):
    """
    Sum Upper Requirement 검사.

    X + Y + ... <= limit
    """

    location = (
        f"Requirement {requirement.id}"
    )

    if not requirement.variables:

        issues.append(
            ValidationIssue(
                location=location,
                message=(
                    "Sum constraint requires "
                    "one or more variables."
                ),
            )
        )

        return

    all_exist = True

    for variable_name in requirement.variables:

        exists = variable_exists(
            case,
            requirement,
            variable_name,
            issues,
        )

        if not exists:
            all_exist = False

    if requirement.limit is None:

        issues.append(
            ValidationIssue(
                location=location,
                message=(
                    "Sum upper limit is missing."
                ),
            )
        )

    if all_exist:

        validate_units(
            case,
            requirement,
            requirement.variables,
            issues,
        )


# =========================================================
# REQUIREMENT VALIDATION
# =========================================================

def validate_requirements(
    case: EngineeringCase,
    issues: list[ValidationIssue],
):
    """
    Engineering Requirements 전체 검사.
    """

    if not case.requirements:

        issues.append(
            ValidationIssue(
                location="requirements",
                message=(
                    "No engineering requirements "
                    "defined."
                ),
            )
        )

        return

    seen_ids = set()

    for requirement in case.requirements:

        location = (
            f"Requirement {requirement.id}"
        )

        # -------------------------------------------------
        # ID
        # -------------------------------------------------

        if not requirement.id:

            issues.append(
                ValidationIssue(
                    location="Requirement",
                    message=(
                        "Requirement ID is missing."
                    ),
                )
            )

            continue

        if requirement.id in seen_ids:

            issues.append(
                ValidationIssue(
                    location=location,
                    message=(
                        "Duplicate Requirement ID."
                    ),
                )
            )

        seen_ids.add(
            requirement.id
        )

        # -------------------------------------------------
        # TYPE
        # -------------------------------------------------

        if (
            requirement.type
            not in SUPPORTED_REQUIREMENT_TYPES
        ):

            issues.append(
                ValidationIssue(
                    location=location,
                    message=(
                        "Unsupported constraint type: "
                        f"{requirement.type}"
                    ),
                )
            )

            continue

        # -------------------------------------------------
        # TYPE-SPECIFIC VALIDATION
        # -------------------------------------------------

        if requirement.type == "range":

            validate_range_requirement(
                case,
                requirement,
                issues,
            )

        elif (
            requirement.type
            == "difference_min"
        ):

            validate_difference_requirement(
                case,
                requirement,
                issues,
            )

        elif requirement.type == "sum_upper":

            validate_sum_requirement(
                case,
                requirement,
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
    """

    issues: list[ValidationIssue] = []

    validate_variables(
        case,
        issues,
    )

    validate_requirements(
        case,
        issues,
    )

    return ValidationResult(
        valid=(len(issues) == 0),
        issues=issues,
    )
