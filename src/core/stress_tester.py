from dataclasses import dataclass, field

from z3 import (
    Optimize,
    sat,
)

from src.core.models import (
    EngineeringCase,
    RequirementSpec,
)

from src.core.constraint_engine import (
    create_z3_variables,
    build_feasible_constraints,
    build_verification_constraints,
    build_requirement_expression,
    z3_value,
)


# =========================================================
# RESULT MODEL
# =========================================================

@dataclass
class StressTestResult:
    """
    하나의 Requirement에 대한
    Verification Stress Test 결과.
    """

    requirement_id: str
    requirement_type: str

    escape_found: bool

    worst_violation: float = 0.0

    state: dict[str, float] = field(
        default_factory=dict
    )

    actual_value: float | None = None

    direction: str | None = None


# =========================================================
# Z3 VALUE CONVERSION
# =========================================================

def z3_to_float(value) -> float:
    """
    Z3 Rational 값을 Python float로 변환한다.
    """

    return (
        value.numerator_as_long()
        /
        value.denominator_as_long()
    )


# =========================================================
# MODEL STATE EXTRACTION
# =========================================================

def extract_state(
    model,
    z3_variables,
) -> dict[str, float]:
    """
    Z3 Model에서 Engineering State를 추출한다.
    """

    state = {}

    for name, variable in (
        z3_variables.variables.items()
    ):

        value = model[variable]

        if value is not None:

            state[name] = z3_to_float(
                value
            )

    return state


# =========================================================
# COMMON STRESS TEST SETUP
# =========================================================

def add_common_constraints(
    optimizer,
    case: EngineeringCase,
    z3_variables,
):
    """
    모든 Stress Test에 공통으로 필요한:

    Feasible Domain
    AND
    Verification PASS

    조건을 추가한다.
    """

    feasible = build_feasible_constraints(
        case,
        z3_variables,
    )

    verification = (
        build_verification_constraints(
            case,
            z3_variables,
        )
    )

    optimizer.add(
        *feasible
    )

    optimizer.add(
        *verification
    )


# =========================================================
# RANGE STRESS TEST
# =========================================================

def stress_test_range(
    case: EngineeringCase,
    requirement: RequirementSpec,
) -> StressTestResult:
    """
    Range Requirement:

        min <= X <= max

    는 아래쪽 Escape와 위쪽 Escape가
    모두 가능하므로 각각 공격한다.

    더 큰 Violation을 Worst Escape로 선택한다.
    """

    candidates = []

    # =====================================================
    # LOWER ATTACK
    #
    # X < minimum
    # =====================================================

    z3_variables = create_z3_variables(
        case,
        prefix=(
            f"stress_{requirement.id}_low"
        ),
    )

    optimizer = Optimize()

    add_common_constraints(
        optimizer,
        case,
        z3_variables,
    )

    variable = z3_variables.get(
        requirement.variable
    )

    minimum = z3_value(
        requirement.min_value
    )

    optimizer.add(
        variable < minimum
    )

    violation = (
        minimum - variable
    )

    optimizer.maximize(
        violation
    )

    if optimizer.check() == sat:

        model = optimizer.model()

        state = extract_state(
            model,
            z3_variables,
        )

        actual = state[
            requirement.variable
        ]

        violation_value = (
            float(requirement.min_value)
            - actual
        )

        candidates.append(
            StressTestResult(
                requirement_id=requirement.id,
                requirement_type=requirement.type,

                escape_found=True,

                worst_violation=violation_value,

                state=state,

                actual_value=actual,

                direction="below_minimum",
            )
        )

    # =====================================================
    # UPPER ATTACK
    #
    # X > maximum
    # =====================================================

    z3_variables = create_z3_variables(
        case,
        prefix=(
            f"stress_{requirement.id}_high"
        ),
    )

    optimizer = Optimize()

    add_common_constraints(
        optimizer,
        case,
        z3_variables,
    )

    variable = z3_variables.get(
        requirement.variable
    )

    maximum = z3_value(
        requirement.max_value
    )

    optimizer.add(
        variable > maximum
    )

    violation = (
        variable - maximum
    )

    optimizer.maximize(
        violation
    )

    if optimizer.check() == sat:

        model = optimizer.model()

        state = extract_state(
            model,
            z3_variables,
        )

        actual = state[
            requirement.variable
        ]

        violation_value = (
            actual
            - float(requirement.max_value)
        )

        candidates.append(
            StressTestResult(
                requirement_id=requirement.id,
                requirement_type=requirement.type,

                escape_found=True,

                worst_violation=violation_value,

                state=state,

                actual_value=actual,

                direction="above_maximum",
            )
        )

    # =====================================================
    # NO ESCAPE
    # =====================================================

    if not candidates:

        return StressTestResult(
            requirement_id=requirement.id,
            requirement_type=requirement.type,
            escape_found=False,
        )

    # =====================================================
    # WORST RANGE ESCAPE
    # =====================================================

    return max(
        candidates,
        key=lambda result:
            result.worst_violation,
    )


# =========================================================
# DIFFERENCE STRESS TEST
# =========================================================

def stress_test_difference(
    case: EngineeringCase,
    requirement: RequirementSpec,
) -> StressTestResult:
    """
    Difference Requirement:

        left - right >= minimum

    Verification을 PASS하면서
    이 값이 얼마나 minimum 아래로
    내려갈 수 있는지 계산한다.
    """

    z3_variables = create_z3_variables(
        case,
        prefix=(
            f"stress_{requirement.id}"
        ),
    )

    optimizer = Optimize()

    add_common_constraints(
        optimizer,
        case,
        z3_variables,
    )

    requirement_expression = (
        build_requirement_expression(
            requirement,
            z3_variables,
        )
    )

    optimizer.add(
        requirement_expression.fail_condition
    )

    expression = (
        requirement_expression.measured_expression
    )

    minimum = z3_value(
        requirement.min_value
    )

    violation = (
        minimum - expression
    )

    optimizer.maximize(
        violation
    )

    if optimizer.check() != sat:

        return StressTestResult(
            requirement_id=requirement.id,
            requirement_type=requirement.type,
            escape_found=False,
        )

    model = optimizer.model()

    state = extract_state(
        model,
        z3_variables,
    )

    actual = (
        state[requirement.left]
        - state[requirement.right]
    )

    violation_value = (
        float(requirement.min_value)
        - actual
    )

    return StressTestResult(
        requirement_id=requirement.id,
        requirement_type=requirement.type,

        escape_found=True,

        worst_violation=violation_value,

        state=state,

        actual_value=actual,

        direction="below_minimum",
    )


# =========================================================
# SUM UPPER STRESS TEST
# =========================================================

def stress_test_sum_upper(
    case: EngineeringCase,
    requirement: RequirementSpec,
) -> StressTestResult:
    """
    Sum Upper Requirement:

        X + Y + ... <= limit

    Verification을 PASS하면서
    합계가 limit을 얼마나 초과할 수 있는지 계산한다.
    """

    z3_variables = create_z3_variables(
        case,
        prefix=(
            f"stress_{requirement.id}"
        ),
    )

    optimizer = Optimize()

    add_common_constraints(
        optimizer,
        case,
        z3_variables,
    )

    requirement_expression = (
        build_requirement_expression(
            requirement,
            z3_variables,
        )
    )

    optimizer.add(
        requirement_expression.fail_condition
    )

    expression = (
        requirement_expression.measured_expression
    )

    limit = z3_value(
        requirement.limit
    )

    violation = (
        expression - limit
    )

    optimizer.maximize(
        violation
    )

    if optimizer.check() != sat:

        return StressTestResult(
            requirement_id=requirement.id,
            requirement_type=requirement.type,
            escape_found=False,
        )

    model = optimizer.model()

    state = extract_state(
        model,
        z3_variables,
    )

    actual = sum(
        state[name]
        for name in requirement.variables
    )

    violation_value = (
        actual
        - float(requirement.limit)
    )

    return StressTestResult(
        requirement_id=requirement.id,
        requirement_type=requirement.type,

        escape_found=True,

        worst_violation=violation_value,

        state=state,

        actual_value=actual,

        direction="above_maximum",
    )


# =========================================================
# GENERIC REQUIREMENT STRESS TEST
# =========================================================

def stress_test_requirement(
    case: EngineeringCase,
    requirement: RequirementSpec,
) -> StressTestResult:
    """
    Requirement Type에 따라
    적절한 Stress Test를 실행한다.
    """

    if requirement.type == "range":

        return stress_test_range(
            case,
            requirement,
        )

    if (
        requirement.type
        == "difference_min"
    ):

        return stress_test_difference(
            case,
            requirement,
        )

    if requirement.type == "sum_upper":

        return stress_test_sum_upper(
            case,
            requirement,
        )

    raise ValueError(
        "Unsupported requirement type: "
        f"{requirement.type}"
    )


# =========================================================
# FULL CASE STRESS TEST
# =========================================================

def stress_test_case(
    case: EngineeringCase,
) -> list[StressTestResult]:
    """
    EngineeringCase 안의 모든 Requirement를
    각각 Stress Test한다.
    """

    results = []

    for requirement in case.requirements:

        results.append(
            stress_test_requirement(
                case,
                requirement,
            )
        )

    return results