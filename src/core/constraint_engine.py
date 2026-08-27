from dataclasses import dataclass
from decimal import Decimal

from z3 import (
    And,
    ArithRef,
    BoolRef,
    Or,
    Real,
    RealVal,
)

from src.core.models import (
    ConstraintSpec,
    EngineeringCase,
)


# =========================================================
# Z3 HELPER
# =========================================================

def z3_value(value: Decimal) -> ArithRef:
    """
    Decimal 값을 정확한 Z3 RealVal로 변환한다.
    """

    return RealVal(str(value))


# =========================================================
# Z3 VARIABLE SET
# =========================================================

@dataclass
class Z3VariableSet:
    """
    EngineeringCase에서 생성한
    Z3 Variable 모음.
    """

    variables: dict[str, ArithRef]

    def get(
        self,
        name: str,
    ) -> ArithRef:

        return self.variables[name]


# =========================================================
# CONSTRAINT EXPRESSION
# =========================================================

@dataclass
class RequirementExpression:
    """
    Engineering Constraint를
    Z3 Expression으로 변환한 결과.

    기존 Core 코드와 호환하기 위해
    이름은 RequirementExpression을 유지한다.
    """

    requirement_id: str
    requirement_type: str

    pass_condition: BoolRef
    fail_condition: BoolRef

    measured_expression: ArithRef | None = None

    limit_value: Decimal | None = None

    violation_direction: str | None = None


# =========================================================
# VARIABLE CREATION
# =========================================================

def create_z3_variables(
    case: EngineeringCase,
    prefix: str = "core",
) -> Z3VariableSet:

    variables = {}

    for variable_name in case.variables:

        variables[variable_name] = Real(
            f"{prefix}_{variable_name}"
        )

    return Z3VariableSet(
        variables=variables
    )


# =========================================================
# FEASIBLE DOMAIN
# =========================================================

def build_feasible_constraints(
    case: EngineeringCase,
    z3_variables: Z3VariableSet,
) -> list[BoolRef]:

    constraints = []

    for name, variable_spec in (
        case.variables.items()
    ):

        variable = z3_variables.get(
            name
        )

        constraints.append(
            variable
            >= z3_value(
                variable_spec.feasible_min
            )
        )

        constraints.append(
            variable
            <= z3_value(
                variable_spec.feasible_max
            )
        )

    return constraints


# =========================================================
# RANGE
# =========================================================

def build_range_constraint(
    constraint: ConstraintSpec,
    z3_variables: Z3VariableSet,
) -> RequirementExpression:

    variable = z3_variables.get(
        constraint.variable
    )

    minimum = z3_value(
        constraint.min_value
    )

    maximum = z3_value(
        constraint.max_value
    )

    pass_condition = And(
        variable >= minimum,
        variable <= maximum,
    )

    fail_condition = Or(
        variable < minimum,
        variable > maximum,
    )

    return RequirementExpression(
        requirement_id=constraint.id,
        requirement_type=constraint.type,

        pass_condition=pass_condition,
        fail_condition=fail_condition,

        measured_expression=variable,

        violation_direction="range",
    )


# =========================================================
# DIFFERENCE MINIMUM
# =========================================================

def build_difference_constraint(
    constraint: ConstraintSpec,
    z3_variables: Z3VariableSet,
) -> RequirementExpression:

    left = z3_variables.get(
        constraint.left
    )

    right = z3_variables.get(
        constraint.right
    )

    expression = (
        left - right
    )

    minimum = z3_value(
        constraint.min_value
    )

    return RequirementExpression(
        requirement_id=constraint.id,
        requirement_type=constraint.type,

        pass_condition=(
            expression >= minimum
        ),

        fail_condition=(
            expression < minimum
        ),

        measured_expression=expression,

        limit_value=constraint.min_value,

        violation_direction="lower",
    )


# =========================================================
# SUM UPPER
# =========================================================

def build_sum_upper_constraint(
    constraint: ConstraintSpec,
    z3_variables: Z3VariableSet,
) -> RequirementExpression:

    expression = 0

    for variable_name in (
        constraint.variables
    ):

        expression = (
            expression
            + z3_variables.get(
                variable_name
            )
        )

    limit = z3_value(
        constraint.limit
    )

    return RequirementExpression(
        requirement_id=constraint.id,
        requirement_type=constraint.type,

        pass_condition=(
            expression <= limit
        ),

        fail_condition=(
            expression > limit
        ),

        measured_expression=expression,

        limit_value=constraint.limit,

        violation_direction="upper",
    )


# =========================================================
# GENERIC CONSTRAINT BUILDER
# =========================================================

def build_requirement_expression(
    requirement: ConstraintSpec,
    z3_variables: Z3VariableSet,
) -> RequirementExpression:
    """
    Requirement와 Verification Constraint가
    공통으로 사용하는 Z3 변환 함수.
    """

    if requirement.type == "range":

        return build_range_constraint(
            requirement,
            z3_variables,
        )

    if (
        requirement.type
        == "difference_min"
    ):

        return build_difference_constraint(
            requirement,
            z3_variables,
        )

    if requirement.type == "sum_upper":

        return build_sum_upper_constraint(
            requirement,
            z3_variables,
        )

    raise ValueError(
        "Unsupported constraint type: "
        f"{requirement.type}"
    )


# =========================================================
# VERIFICATION PLAN
# =========================================================

def build_verification_constraints(
    case: EngineeringCase,
    z3_variables: Z3VariableSet,
) -> list[BoolRef]:
    """
    Verification Plan 전체를 생성한다.

    1. 각 Variable의 Verification Range
    2. 추가 Verification 관계조건
    """

    constraints = []

    # -----------------------------------------------------
    # VARIABLE VERIFICATION RANGES
    # -----------------------------------------------------

    for name, variable_spec in (
        case.variables.items()
    ):

        variable = z3_variables.get(
            name
        )

        constraints.append(
            variable
            >= z3_value(
                variable_spec.verification_min
            )
        )

        constraints.append(
            variable
            <= z3_value(
                variable_spec.verification_max
            )
        )

    # -----------------------------------------------------
    # RELATIONAL VERIFICATION CONSTRAINTS
    # -----------------------------------------------------

    for verification_constraint in (
        case.verification_constraints
    ):

        expression = (
            build_requirement_expression(
                verification_constraint,
                z3_variables,
            )
        )

        constraints.append(
            expression.pass_condition
        )

    return constraints


# =========================================================
# ALL REQUIREMENTS
# =========================================================

def build_all_requirement_expressions(
    case: EngineeringCase,
    z3_variables: Z3VariableSet,
) -> list[RequirementExpression]:

    return [
        build_requirement_expression(
            requirement,
            z3_variables,
        )
        for requirement
        in case.requirements
    ]


# =========================================================
# VERIFICATION EXPRESSIONS
# =========================================================

def build_all_verification_expressions(
    case: EngineeringCase,
    z3_variables: Z3VariableSet,
) -> list[RequirementExpression]:

    return [
        build_requirement_expression(
            constraint,
            z3_variables,
        )
        for constraint
        in case.verification_constraints
    ]
