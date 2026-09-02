from dataclasses import dataclass
from decimal import Decimal

from z3 import (
    And,
    ArithRef,
    BoolRef,
    If,
    Or,
    Real,
    RealVal,
)

from src.core.models import (
    EngineeringCase,
    RequirementSpec,
)


# =========================================================
# Z3 VALUE
# =========================================================

def z3_value(
    value: Decimal,
) -> ArithRef:
    """
    Decimal 값을 정확한 Z3 숫자로 변환한다.
    """

    return RealVal(
        str(value)
    )


# =========================================================
# Z3 VARIABLE SET
# =========================================================

@dataclass
class Z3VariableSet:
    """
    Engineering 변수와
    Z3 변수를 연결하는 구조.
    """

    variables: dict[
        str,
        ArithRef,
    ]

    def get(
        self,
        name: str,
    ) -> ArithRef:

        return self.variables[
            name
        ]


# =========================================================
# REQUIREMENT EXPRESSION
# =========================================================

@dataclass
class RequirementExpression:
    """
    하나의 공학 조건을
    Z3 식으로 변환한 결과.
    """

    requirement_id: str
    requirement_type: str

    pass_condition: BoolRef
    fail_condition: BoolRef

    measured_expression: (
        ArithRef | None
    ) = None

    limit_value: (
        Decimal | None
    ) = None

    violation_direction: (
        str | None
    ) = None


# =========================================================
# CREATE Z3 VARIABLES
# =========================================================

def create_z3_variables(
    case: EngineeringCase,
    prefix: str = "core",
) -> Z3VariableSet:

    variables = {}

    for variable_name in (
        case.variables
    ):

        variables[
            variable_name
        ] = Real(
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
    현실적으로 가능한 범위를
    Z3 Constraint로 만든다.
    """

    constraints = []

    for (
        name,
        variable_spec,
    ) in case.variables.items():

        variable = (
            z3_variables.get(
                name
            )
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

def build_range_requirement(
    requirement: RequirementSpec,
    z3_variables: Z3VariableSet,
) -> RequirementExpression:

    variable = (
        z3_variables.get(
            requirement.variable
        )
    )

    minimum = z3_value(
        requirement.min_value
    )

    maximum = z3_value(
        requirement.max_value
    )

    return RequirementExpression(
        requirement_id=(
            requirement.id
        ),

        requirement_type=(
            requirement.type
        ),

        pass_condition=And(
            variable >= minimum,
            variable <= maximum,
        ),

        fail_condition=Or(
            variable < minimum,
            variable > maximum,
        ),

        measured_expression=(
            variable
        ),

        violation_direction=(
            "range"
        ),
    )


# =========================================================
# LOWER BOUND
# =========================================================

def build_lower_bound_requirement(
    requirement: RequirementSpec,
    z3_variables: Z3VariableSet,
) -> RequirementExpression:

    variable = z3_variables.get(
        requirement.variable
    )

    minimum = z3_value(
        requirement.min_value
    )

    return RequirementExpression(
        requirement_id=requirement.id,
        requirement_type=requirement.type,
        pass_condition=(
            variable >= minimum
        ),
        fail_condition=(
            variable < minimum
        ),
        measured_expression=variable,
        limit_value=requirement.min_value,
        violation_direction="lower",
    )


# =========================================================
# UPPER BOUND
# =========================================================

def build_upper_bound_requirement(
    requirement: RequirementSpec,
    z3_variables: Z3VariableSet,
) -> RequirementExpression:

    variable = z3_variables.get(
        requirement.variable
    )

    maximum = z3_value(
        requirement.max_value
    )

    return RequirementExpression(
        requirement_id=requirement.id,
        requirement_type=requirement.type,
        pass_condition=(
            variable <= maximum
        ),
        fail_condition=(
            variable > maximum
        ),
        measured_expression=variable,
        limit_value=requirement.max_value,
        violation_direction="upper",
    )


# =========================================================
# DIFFERENCE MIN
# =========================================================

def build_difference_requirement(
    requirement: RequirementSpec,
    z3_variables: Z3VariableSet,
) -> RequirementExpression:

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

    return RequirementExpression(
        requirement_id=(
            requirement.id
        ),

        requirement_type=(
            requirement.type
        ),

        pass_condition=(
            expression >= minimum
        ),

        fail_condition=(
            expression < minimum
        ),

        measured_expression=(
            expression
        ),

        limit_value=(
            requirement.min_value
        ),

        violation_direction=(
            "lower"
        ),
    )


# =========================================================
# SUM UPPER
# =========================================================


# =========================================================

# ABSOLUTE DIFFERENCE MAX

# |LEFT - RIGHT| <= LIMIT

# =========================================================

def build_abs_difference_max_requirement(

    requirement: RequirementSpec,

    z3_variables: Z3VariableSet,

) -> RequirementExpression:

    """
    Absolute Difference Requirement:

        |left - right| <= limit
    """

    left = z3_variables.get(
        requirement.left
    )

    right = z3_variables.get(
        requirement.right
    )

    difference = (
        left - right
    )

    absolute_difference = If(
        difference >= 0,
        difference,
        -difference,
    )

    limit = z3_value(
        requirement.limit
    )

    return RequirementExpression(

        requirement_id=requirement.id,

        requirement_type=requirement.type,

        pass_condition=(
            absolute_difference <= limit
        ),

        fail_condition=(
            absolute_difference > limit
        ),

        measured_expression=(
            absolute_difference
        ),

        limit_value=(
            requirement.limit
        ),

        violation_direction="upper",

    )


def build_sum_upper_requirement(
    requirement: RequirementSpec,
    z3_variables: Z3VariableSet,
) -> RequirementExpression:

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

    return RequirementExpression(
        requirement_id=(
            requirement.id
        ),

        requirement_type=(
            requirement.type
        ),

        pass_condition=(
            expression <= limit
        ),

        fail_condition=(
            expression > limit
        ),

        measured_expression=(
            expression
        ),

        limit_value=(
            requirement.limit
        ),

        violation_direction=(
            "upper"
        ),
    )


# =========================================================
# GENERIC REQUIREMENT BUILDER
# =========================================================

def build_requirement_expression(
    requirement: RequirementSpec,
    z3_variables: Z3VariableSet,
) -> RequirementExpression:
    """
    조건 Type에 맞는 Z3 식을 만든다.

    이 함수는 Requirement뿐 아니라
    Verification Plan 관계조건에도
    동일하게 사용할 수 있다.
    """

    if (
        requirement.type
        == "range"
    ):

        return (
            build_range_requirement(
                requirement,
                z3_variables,
            )
        )

    if (
        requirement.type
        == "lower_bound"
    ):
        return (
            build_lower_bound_requirement(
                requirement,
                z3_variables,
            )
        )

    if (
        requirement.type
        == "upper_bound"
    ):
        return (
            build_upper_bound_requirement(
                requirement,
                z3_variables,
            )
        )

    if (
        requirement.type
        == "difference_min"
    ):

        return (
            build_difference_requirement(
                requirement,
                z3_variables,
            )
        )
    if (

        requirement.type

        == "abs_difference_max"

    ):

        return (

            build_abs_difference_max_requirement(

                requirement,

                z3_variables,

            )

        )



    if (
        requirement.type
        == "sum_upper"
    ):

        return (
            build_sum_upper_requirement(
                requirement,
                z3_variables,
            )
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
    현재 검사계획에서 PASS가 되기 위한
    모든 조건을 만든다.

    1. 각 변수의 기본 검사 Range
    2. 추가 관계조건
       예: X + Y <= 40.05
    """

    constraints = []

    # -----------------------------------------------------
    # 기본 Variable 검사 범위
    # -----------------------------------------------------

    for (
        name,
        variable_spec,
    ) in case.variables.items():

        variable = (
            z3_variables.get(
                name
            )
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
    # 추가 Verification 관계조건
    # -----------------------------------------------------

    for constraint in (
        case.verification_constraints
    ):

        expression = (
            build_requirement_expression(
                constraint,
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
) -> list[
    RequirementExpression
]:

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