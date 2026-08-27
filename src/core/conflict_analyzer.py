from dataclasses import dataclass, field

from z3 import (
    Solver,
    sat,
    unsat,
)

from src.core.models import (
    EngineeringCase,
    RequirementSpec,
)

from src.core.constraint_engine import (
    create_z3_variables,
    build_feasible_constraints,
    build_requirement_expression,
)


# =========================================================
# RESULT MODELS
# =========================================================

@dataclass
class ConflictItem:
    """
    Unsat Core에 포함된 하나의 Constraint.
    """

    label: str
    description: str


@dataclass
class ConflictAnalysisResult:
    """
    Engineering Model 논리 일관성 분석 결과.
    """

    consistent: bool

    example_state: dict[str, float] = field(
        default_factory=dict
    )

    conflict_items: list[ConflictItem] = field(
        default_factory=list
    )


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
# TRACKED CONSTRAINT
# =========================================================

def add_tracked_constraint(
    solver,
    constraint,
    label: str,
    description: str,
    descriptions: dict[str, str],
):
    """
    Constraint를 Solver에 넣으면서
    추적용 Label을 붙인다.

    UNSAT 발생 시 Z3 Unsat Core에서
    충돌 Constraint를 확인할 수 있다.
    """

    solver.assert_and_track(
        constraint,
        label,
    )

    descriptions[label] = description


# =========================================================
# FEASIBLE DOMAIN TRACKING
# =========================================================

def add_feasible_constraints_with_tracking(
    solver,
    case: EngineeringCase,
    z3_variables,
    descriptions: dict[str, str],
):
    """
    Feasible Domain의 각 min/max 조건을
    추적 가능한 Constraint로 추가한다.
    """

    for name, variable_spec in (
        case.variables.items()
    ):

        variable = z3_variables.get(
            name
        )

        # -------------------------------------------------
        # MIN
        # -------------------------------------------------

        min_label = (
            f"F_{name}_MIN"
        )

        min_constraint = (
            variable
            >= variable_spec.feasible_min
        )

        add_tracked_constraint(
            solver,
            min_constraint,
            min_label,
            (
                f"Feasible Domain: "
                f"{name} >= "
                f"{variable_spec.feasible_min} "
                f"{variable_spec.unit}"
            ),
            descriptions,
        )

        # -------------------------------------------------
        # MAX
        # -------------------------------------------------

        max_label = (
            f"F_{name}_MAX"
        )

        max_constraint = (
            variable
            <= variable_spec.feasible_max
        )

        add_tracked_constraint(
            solver,
            max_constraint,
            max_label,
            (
                f"Feasible Domain: "
                f"{name} <= "
                f"{variable_spec.feasible_max} "
                f"{variable_spec.unit}"
            ),
            descriptions,
        )


# =========================================================
# REQUIREMENT DESCRIPTION
# =========================================================

def build_requirement_description(
    requirement: RequirementSpec,
) -> str:
    """
    Requirement를 사람이 읽을 수 있는
    문자열로 변환한다.
    """

    if requirement.type == "range":

        return (
            f"{requirement.id}: "
            f"{requirement.min_value} <= "
            f"{requirement.variable} <= "
            f"{requirement.max_value} "
            f"{requirement.unit}"
        )

    if (
        requirement.type
        == "difference_min"
    ):

        return (
            f"{requirement.id}: "
            f"{requirement.left} - "
            f"{requirement.right} >= "
            f"{requirement.min_value} "
            f"{requirement.unit}"
        )

    if requirement.type == "sum_upper":

        expression = " + ".join(
            requirement.variables
        )

        return (
            f"{requirement.id}: "
            f"{expression} <= "
            f"{requirement.limit} "
            f"{requirement.unit}"
        )

    return (
        f"{requirement.id}: "
        f"{requirement.type}"
    )


# =========================================================
# REQUIREMENT TRACKING
# =========================================================

def add_requirement_with_tracking(
    solver,
    requirement: RequirementSpec,
    z3_variables,
    descriptions: dict[str, str],
):
    """
    Requirement PASS 조건을 추적 가능한
    Solver Constraint로 추가한다.

    Range는 lower / upper를 따로 추적하고,
    나머지는 Requirement 단위로 추적한다.
    """

    expression = (
        build_requirement_expression(
            requirement,
            z3_variables,
        )
    )

    # =====================================================
    # RANGE
    #
    # min <= X <= max
    #
    # Range는 두 개의 경계조건으로 분리한다.
    # =====================================================

    if requirement.type == "range":

        variable = z3_variables.get(
            requirement.variable
        )

        min_label = (
            f"R_{requirement.id}_MIN"
        )

        max_label = (
            f"R_{requirement.id}_MAX"
        )

        add_tracked_constraint(
            solver,
            variable
            >= requirement.min_value,
            min_label,
            (
                f"{requirement.id}: "
                f"{requirement.variable} >= "
                f"{requirement.min_value} "
                f"{requirement.unit}"
            ),
            descriptions,
        )

        add_tracked_constraint(
            solver,
            variable
            <= requirement.max_value,
            max_label,
            (
                f"{requirement.id}: "
                f"{requirement.variable} <= "
                f"{requirement.max_value} "
                f"{requirement.unit}"
            ),
            descriptions,
        )

        return

    # =====================================================
    # DIFFERENCE / SUM
    # =====================================================

    label = (
        f"R_{requirement.id}"
    )

    add_tracked_constraint(
        solver,
        expression.pass_condition,
        label,
        build_requirement_description(
            requirement
        ),
        descriptions,
    )


# =========================================================
# MAIN CONFLICT ANALYSIS
# =========================================================

def analyze_conflicts(
    case: EngineeringCase,
) -> ConflictAnalysisResult:
    """
    질문:

    Feasible Domain 안에서
    모든 Engineering Requirement를
    동시에 만족하는 상태가 존재하는가?

    SAT:
        Logical Consistency PASS

    UNSAT:
        Logical Conflict 존재
        → Unsat Core 반환
    """

    z3_variables = create_z3_variables(
        case,
        prefix="conflict"
    )

    solver = Solver()

    solver.set(
        unsat_core=True
    )

    descriptions: dict[
        str,
        str,
    ] = {}

    # =====================================================
    # FEASIBLE DOMAIN
    # =====================================================

    add_feasible_constraints_with_tracking(
        solver,
        case,
        z3_variables,
        descriptions,
    )

    # =====================================================
    # REQUIREMENTS
    # =====================================================

    for requirement in (
        case.requirements
    ):

        add_requirement_with_tracking(
            solver,
            requirement,
            z3_variables,
            descriptions,
        )

    # =====================================================
    # SOLVE
    # =====================================================

    result = solver.check()

    # -----------------------------------------------------
    # SAT
    # -----------------------------------------------------

    if result == sat:

        model = solver.model()

        example_state = {}

        for name, variable in (
            z3_variables.variables.items()
        ):

            value = model[
                variable
            ]

            if value is not None:

                example_state[name] = (
                    z3_to_float(
                        value
                    )
                )

        return ConflictAnalysisResult(
            consistent=True,
            example_state=example_state,
        )

    # -----------------------------------------------------
    # UNSAT
    # -----------------------------------------------------

    if result == unsat:

        core = solver.unsat_core()

        conflict_items = []

        for core_item in core:

            label = str(
                core_item
            )

            conflict_items.append(
                ConflictItem(
                    label=label,
                    description=(
                        descriptions.get(
                            label,
                            "Unknown constraint",
                        )
                    ),
                )
            )

        return ConflictAnalysisResult(
            consistent=False,
            conflict_items=conflict_items,
        )

    # -----------------------------------------------------
    # UNKNOWN
    # -----------------------------------------------------

    raise RuntimeError(
        "Z3 returned UNKNOWN during "
        "logical consistency analysis."
    )
