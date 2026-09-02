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


from src.core.solver_control import (
    SolverIndeterminateError,
    check_optimizer_decisive,
    create_optimizer,
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

    solver_status: str = "SOLVED"

    solver_reason: str | None = None


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

    optimizer = create_optimizer()

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

    if check_optimizer_decisive(optimizer) == sat:

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

    optimizer = create_optimizer()

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

    if check_optimizer_decisive(optimizer) == sat:

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

    optimizer = create_optimizer()

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

    if check_optimizer_decisive(optimizer) != sat:

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


# =========================================================

# ABSOLUTE DIFFERENCE MAX STRESS TEST

# =========================================================

def stress_test_abs_difference_max(

    case: EngineeringCase,

    requirement: RequirementSpec,

) -> StressTestResult:

    """
    Absolute Difference Requirement:

        |left - right| <= limit

    현재 Verification Plan을 PASS하면서
    절대 차이가 limit을 얼마나 크게
    초과할 수 있는지 탐색한다.
    """

    z3_variables = create_z3_variables(

        case,

        prefix=(
            f"stress_{requirement.id}"
        ),

    )


    optimizer = create_optimizer()


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


    # Requirement를 위반하는 상태만 공격
    optimizer.add(

        requirement_expression.fail_condition

    )


    absolute_difference = (

        requirement_expression.measured_expression

    )


    limit = z3_value(

        requirement.limit

    )


    violation = (

        absolute_difference

        - limit

    )


    # 검사를 통과하면서
    # Requirement 위반 정도를 최대화
    optimizer.maximize(

        violation

    )


    if check_optimizer_decisive(optimizer) != sat:

        return StressTestResult(

            requirement_id=(
                requirement.id
            ),

            requirement_type=(
                requirement.type
            ),

            escape_found=False,

        )


    model = optimizer.model()


    state = extract_state(

        model,

        z3_variables,

    )


    actual = abs(

        state[requirement.left]

        - state[requirement.right]

    )


    violation_value = (

        actual

        - float(requirement.limit)

    )


    return StressTestResult(

        requirement_id=(
            requirement.id
        ),

        requirement_type=(
            requirement.type
        ),

        escape_found=True,

        worst_violation=(
            violation_value
        ),

        state=state,

        actual_value=actual,

        direction=(
            "above_maximum"
        ),

    )


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

    optimizer = create_optimizer()

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

    if check_optimizer_decisive(optimizer) != sat:

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
# ONE-SIDED BOUND STRESS TEST
# =========================================================

def stress_test_one_sided_bound(
    case: EngineeringCase,
    requirement: RequirementSpec,
) -> StressTestResult:

    z3_variables = create_z3_variables(
        case,
        prefix=f"stress_{requirement.id}",
    )

    optimizer = create_optimizer()

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

    if requirement.type == "lower_bound":

        limit = z3_value(
            requirement.min_value
        )

        violation = (
            limit - expression
        )

        direction = "below_minimum"

    elif requirement.type == "upper_bound":

        limit = z3_value(
            requirement.max_value
        )

        violation = (
            expression - limit
        )

        direction = "above_maximum"

    else:

        raise ValueError(
            "stress_test_one_sided_bound received "
            f"unsupported type: {requirement.type}"
        )

    optimizer.maximize(
        violation
    )

    if check_optimizer_decisive(optimizer) != sat:

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

    actual = state[
        requirement.variable
    ]

    if requirement.type == "lower_bound":

        violation_value = (
            float(requirement.min_value)
            - actual
        )

    else:

        violation_value = (
            actual
            - float(requirement.max_value)
        )

    return StressTestResult(
        requirement_id=requirement.id,
        requirement_type=requirement.type,
        escape_found=True,
        worst_violation=violation_value,
        state=state,
        actual_value=actual,
        direction=direction,
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

    if requirement.type in {
        "lower_bound",
        "upper_bound",
    }:
        return stress_test_one_sided_bound(
            case,
            requirement,
        )

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

    if (
        requirement.type
        == "abs_difference_max"
    ):

        return (
            stress_test_abs_difference_max(

                case,

                requirement,

            )
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

    Solver가 timeout / unknown이면
    NO ESCAPE로 처리하지 않고
    UNKNOWN 결과를 보존한다.
    """

    results = []

    for requirement in case.requirements:

        try:
            result = stress_test_requirement(
                case,
                requirement,
            )

        except SolverIndeterminateError as exc:

            result = StressTestResult(
                requirement_id=(
                    requirement.id
                ),
                requirement_type=(
                    requirement.type
                ),
                escape_found=False,
                solver_status="UNKNOWN",
                solver_reason=(
                    exc.reason
                ),
            )

        results.append(
            result
        )

    return results

