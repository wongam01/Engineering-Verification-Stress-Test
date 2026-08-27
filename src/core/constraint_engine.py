from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from z3 import (
    ArithRef,
    BoolRef,
    Real,
    RealVal,
)

from src.core.models import (
    EngineeringCase,
    RequirementSpec,
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
    하나의 EngineeringCase에서 생성된
    Z3 변수 모음.
    """

    variables: dict[str, ArithRef]

    def get(
        self,
        name: str,
    ) -> ArithRef:
        """
        변수 이름으로 Z3 Variable을 가져온다.
        """

        return self.variables[name]


# =========================================================
# REQUIREMENT EXPRESSION
# =========================================================

@dataclass
class RequirementExpression:
    """
    하나의 Requirement를 Z3 식으로 변환한 결과.

    pass_condition:
        Requirement를 만족하는 조건

    fail_condition:
        Requirement를 위반하는 조건

    measured_expression:
        실제 Engineering 값 계산에 사용되는 식

    limit_value:
        비교 기준값

    violation_direction:
        upper / lower / range
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
    """
    EngineeringCase의 Variable 이름을 읽어
    Z3 Real Variable을 자동 생성한다.

    예:

    X
    Y
    D

        ↓

    core_X
    core_Y
    core_D
    """

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
    """
    EngineeringCase의 Feasible Domain을
    Z3 Constraint 목록으로 변환한다.
    """

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
# VERIFICATION PLAN
# =========================================================

def build_verification_constraints(
    case: EngineeringCase,
    z3_variables: Z3VariableSet,
) -> list[BoolRef]:
    """
    현재 Verification Plan을
    Z3 Constraint 목록으로 변환한다.
    """

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
                variable_spec.verification_min
            )
        )

        constraints.append(
            variable
            <= z3_value(
                variable_spec.verification_max
            )
        )

    return constraints


# =========================================================
# RANGE REQUIREMENT
# =========================================================

def build_range_requirement(
    requirement: RequirementSpec,
    z3_variables: Z3VariableSet,
) -> RequirementExpression:
    """
    Range Requirement:

        minimum <= X <= maximum
    """

    variable = z3_variables.get(
        requirement.variable
    )

    minimum = z3_value(
        requirement.min_value
    )

    maximum = z3_value(
        requirement.max_value
    )

    pass_condition = (
        (variable >= minimum)
        &
        (variable <= maximum)
    )

    fail_condition = (
        (variable < minimum)
        |
        (variable > maximum)
    )

    return RequirementExpression(
        requirement_id=requirement.id,
        requirement_type=requirement.type,

        pass_condition=pass_condition,
        fail_condition=fail_condition,

        measured_expression=variable,

        violation_direction="range",
    )


# =========================================================
# DIFFERENCE MINIMUM
# =========================================================

def build_difference_requirement(
    requirement: RequirementSpec,
    z3_variables: Z3VariableSet,
) -> RequirementExpression:
    """
    Difference Minimum Requirement:

        left - right >= minimum
    """

    left = z3_variables.get(
        requirement.left
    )

    right = z3_variables.get(
        requirement.right
    )

    expression = (
        left - right
    )

    minimum = z3_value(
        requirement.min_value
    )

    pass_condition = (
        expression >= minimum
    )

    fail_condition = (
        expression < minimum
    )

    return RequirementExpression(
        requirement_id=requirement.id,
        requirement_type=requirement.type,

        pass_condition=pass_condition,
        fail_condition=fail_condition,

        measured_expression=expression,

        limit_value=(
            requirement.min_value
        ),

        violation_direction="lower",
    )


# =========================================================
# SUM UPPER
# =========================================================

def build_sum_upper_requirement(
    requirement: RequirementSpec,
    z3_variables: Z3VariableSet,
) -> RequirementExpression:
    """
    Sum Upper Requirement:

        X + Y + ... <= limit
    """

    expression = 0

    for variable_name in (
        requirement.variables
    ):

        expression = (
            expression
            + z3_variables.get(
                variable_name
            )
        )

    limit = z3_value(
        requirement.limit
    )

    pass_condition = (
        expression <= limit
    )

    fail_condition = (
        expression > limit
    )

    return RequirementExpression(
        requirement_id=requirement.id,
        requirement_type=requirement.type,

        pass_condition=pass_condition,
        fail_condition=fail_condition,

        measured_expression=expression,

        limit_value=(
            requirement.limit
        ),

        violation_direction="upper",
    )


# =========================================================
# GENERIC REQUIREMENT BUILDER
# =========================================================

def build_requirement_expression(
    requirement: RequirementSpec,
    z3_variables: Z3VariableSet,
) -> RequirementExpression:
    """
    Requirement Type을 확인한 뒤
    적절한 Z3 Constraint Builder로 전달한다.
    """

    if requirement.type == "range":

        return build_range_requirement(
            requirement,
            z3_variables,
        )

    if (
        requirement.type
        == "difference_min"
    ):

        return build_difference_requirement(
            requirement,
            z3_variables,
        )

    if requirement.type == "sum_upper":

        return build_sum_upper_requirement(
            requirement,
            z3_variables,
        )

    raise ValueError(
        "Unsupported requirement type: "
        f"{requirement.type}"
    )


# =========================================================
# ALL REQUIREMENTS
# =========================================================

def build_all_requirement_expressions(
    case: EngineeringCase,
    z3_variables: Z3VariableSet,
) -> list[RequirementExpression]:
    """
    EngineeringCase에 있는 모든 Requirement를
    Z3 Expression으로 변환한다.
    """

    expressions = []

    for requirement in (
        case.requirements
    ):

        expressions.append(
            build_requirement_expression(
                requirement,
                z3_variables,
            )
        )

    return expressions