from copy import deepcopy
from decimal import Decimal

from z3 import (
    Real,
    RealVal,
    Solver,
    sat,
    unsat,
)

from constraint_validator import (
    VALID_CASE,
    validate_case,
)


# =========================================================
# HELPERS
# =========================================================

def z3_value(value):
    """Decimal 값을 정확한 Z3 RealVal로 변환한다."""
    return RealVal(str(value))


def to_float(value):
    """Z3 rational 값을 Python float로 변환한다."""
    return (
        value.numerator_as_long()
        / value.denominator_as_long()
    )


# =========================================================
# VARIABLE CREATION
# =========================================================

def create_variables(case):
    """
    Case Data에 있는 모든 변수를
    Z3 Real 변수로 만든다.
    """

    variables = {}

    for name in case["variables"]:
        variables[name] = Real(
            f"conflict_{name}"
        )

    return variables


# =========================================================
# TRACKED CONSTRAINT HELPER
# =========================================================

def add_tracked_constraint(
    solver,
    constraint,
    label,
    description,
    descriptions,
):
    """
    Constraint를 Solver에 추가하면서
    추적용 Label을 붙인다.

    UNSAT가 발생하면 Z3가
    어떤 Label들이 충돌에 관여했는지 알려준다.
    """

    solver.assert_and_track(
        constraint,
        label,
    )

    descriptions[label] = description


# =========================================================
# FEASIBLE DOMAIN
# =========================================================

def add_feasible_domain_with_tracking(
    solver,
    case,
    variables,
    descriptions,
):
    """
    Feasible Domain의 각 경계조건을
    추적 가능한 Constraint로 추가한다.
    """

    for name, data in case["variables"].items():

        variable = variables[name]

        min_label = f"F_{name}_MIN"
        max_label = f"F_{name}_MAX"

        add_tracked_constraint(
            solver,
            variable
            >= z3_value(data["feasible_min"]),
            min_label,
            (
                f"Feasible Domain: "
                f"{name} >= "
                f"{data['feasible_min']} "
                f"{data['unit']}"
            ),
            descriptions,
        )

        add_tracked_constraint(
            solver,
            variable
            <= z3_value(data["feasible_max"]),
            max_label,
            (
                f"Feasible Domain: "
                f"{name} <= "
                f"{data['feasible_max']} "
                f"{data['unit']}"
            ),
            descriptions,
        )


# =========================================================
# REQUIREMENT TRACKING
# =========================================================

def add_requirement_with_tracking(
    solver,
    requirement,
    variables,
    descriptions,
):
    """
    Engineering Requirement를
    실제 만족 조건으로 Solver에 넣는다.

    모든 Requirement에는 추적용 Label을 붙인다.
    """

    requirement_id = requirement["id"]
    requirement_type = requirement["type"]

    # -----------------------------------------------------
    # RANGE
    #
    # min <= D <= max
    # -----------------------------------------------------

    if requirement_type == "range":

        variable_name = requirement["variable"]
        variable = variables[variable_name]

        min_label = (
            f"R_{requirement_id}_MIN"
        )

        max_label = (
            f"R_{requirement_id}_MAX"
        )

        add_tracked_constraint(
            solver,
            variable
            >= z3_value(requirement["min"]),
            min_label,
            (
                f"{requirement_id}: "
                f"{variable_name} >= "
                f"{requirement['min']} "
                f"{requirement['unit']}"
            ),
            descriptions,
        )

        add_tracked_constraint(
            solver,
            variable
            <= z3_value(requirement["max"]),
            max_label,
            (
                f"{requirement_id}: "
                f"{variable_name} <= "
                f"{requirement['max']} "
                f"{requirement['unit']}"
            ),
            descriptions,
        )

    # -----------------------------------------------------
    # DIFFERENCE MIN
    #
    # Y - X >= minimum
    # -----------------------------------------------------

    elif requirement_type == "difference_min":

        left = variables[
            requirement["left"]
        ]

        right = variables[
            requirement["right"]
        ]

        label = f"R_{requirement_id}"

        add_tracked_constraint(
            solver,
            left - right
            >= z3_value(requirement["min"]),
            label,
            (
                f"{requirement_id}: "
                f"{requirement['left']} - "
                f"{requirement['right']} >= "
                f"{requirement['min']} "
                f"{requirement['unit']}"
            ),
            descriptions,
        )

    # -----------------------------------------------------
    # SUM UPPER
    #
    # X + Y + ... <= limit
    # -----------------------------------------------------

    elif requirement_type == "sum_upper":

        expression = 0

        for variable_name in requirement["variables"]:
            expression += variables[
                variable_name
            ]

        label = f"R_{requirement_id}"

        expression_text = " + ".join(
            requirement["variables"]
        )

        add_tracked_constraint(
            solver,
            expression
            <= z3_value(requirement["limit"]),
            label,
            (
                f"{requirement_id}: "
                f"{expression_text} <= "
                f"{requirement['limit']} "
                f"{requirement['unit']}"
            ),
            descriptions,
        )

    else:

        raise ValueError(
            "Unsupported requirement type: "
            + requirement_type
        )


# =========================================================
# CONFLICT DIAGNOSIS
# =========================================================

def diagnose_conflict(case):
    """
    Engineering Model 전체를 검사한다.

    SAT:
        모든 Requirement를 만족하는
        현실적 상태가 존재함

    UNSAT:
        모순 존재

        -> Z3 Unsat Core를 사용해
           충돌에 관여한 Constraint subset을 반환
    """

    # -----------------------------------------------------
    # STEP 1
    # Structural Validation
    # -----------------------------------------------------

    validation = validate_case(case)

    if not validation["valid"]:

        return {
            "status": "structural_error",
            "errors": validation["errors"],
        }

    # -----------------------------------------------------
    # STEP 2
    # Logical Model
    # -----------------------------------------------------

    variables = create_variables(case)

    solver = Solver()

    # Unsat Core 기능 사용
    solver.set(
        unsat_core=True
    )

    descriptions = {}

    # Feasible Domain
    add_feasible_domain_with_tracking(
        solver,
        case,
        variables,
        descriptions,
    )

    # Requirements
    for requirement in case["requirements"]:

        add_requirement_with_tracking(
            solver,
            requirement,
            variables,
            descriptions,
        )

    # -----------------------------------------------------
    # Solve
    # -----------------------------------------------------

    result = solver.check()

    # =====================================================
    # SAT
    # =====================================================

    if result == sat:

        model = solver.model()

        state = {}

        for name, variable in variables.items():

            value = model[variable]

            if value is not None:

                state[name] = to_float(
                    value
                )

        return {
            "status": "consistent",
            "state": state,
        }

    # =====================================================
    # UNSAT
    # =====================================================

    if result == unsat:

        core = solver.unsat_core()

        conflict_items = []

        for item in core:

            label = str(item)

            conflict_items.append(
                {
                    "label": label,
                    "description": (
                        descriptions.get(
                            label,
                            "Unknown tracked constraint",
                        )
                    ),
                }
            )

        return {
            "status": "conflict",
            "conflict_items": conflict_items,
        }

    return {
        "status": "unknown"
    }


# =========================================================
# TEST CASES
# =========================================================

def build_consistent_case():
    """
    기존 정상 Case.
    """

    case = deepcopy(
        VALID_CASE
    )

    case["name"] = (
        "Consistent Engineering Model"
    )

    return case


def build_conflicting_case():
    """
    형식은 정상이나 논리적으로 불가능한 Case.

    Feasible Domain:

        X >= 9.50
        Y >= 29.50

    따라서:

        X + Y >= 39.00

    새로운 Requirement:

        R4
        X + Y <= 38.90

    서로 동시에 만족할 수 없다.
    """

    case = deepcopy(
        VALID_CASE
    )

    case["name"] = (
        "Conflicting Engineering Model"
    )

    case["requirements"].append(
        {
            "id": "R4",
            "type": "sum_upper",
            "variables": [
                "X",
                "Y",
            ],
            "unit": "mm",
            "limit": Decimal("38.90"),
        }
    )

    return case


# =========================================================
# RESULT PRINTER
# =========================================================

def print_result(title, case):

    print()
    print(title)
    print("----------------------------------------")

    print(
        "Case:",
        case["name"]
    )

    print()

    result = diagnose_conflict(
        case
    )

    # =====================================================
    # STRUCTURAL ERROR
    # =====================================================

    if result["status"] == "structural_error":

        print(
            "Structural Validation : FAILED"
        )

        print(
            "Conflict Diagnosis     : NOT RUN"
        )

        print()

        for index, error in enumerate(
            result["errors"],
            start=1,
        ):

            print(
                f"{index}. "
                f"[{error['location']}] "
                f"{error['message']}"
            )

    # =====================================================
    # CONSISTENT
    # =====================================================

    elif result["status"] == "consistent":

        print(
            "Structural Validation : PASSED"
        )

        print(
            "Logical Consistency   : PASSED"
        )

        print(
            "Conflict Detected     : NO"
        )

        print()

        print(
            "Example Valid Engineering State"
        )

        for name, value in (
            result["state"].items()
        ):

            print(
                f"{name:<8} = {value:.3f}"
            )

    # =====================================================
    # CONFLICT
    # =====================================================

    elif result["status"] == "conflict":

        print(
            "Structural Validation : PASSED"
        )

        print(
            "Logical Consistency   : FAILED"
        )

        print(
            "Conflict Detected     : YES"
        )

        print()

        print(
            "CONFLICT CORE"
        )

        print(
            "----------------------------------------"
        )

        for index, item in enumerate(
            result["conflict_items"],
            start=1,
        ):

            print(
                f"{index}. "
                f"[{item['label']}]"
            )

            print(
                "   "
                + item["description"]
            )

        print()

        print(
            "Interpretation:"
        )

        print(
            "These tracked constraints form "
            "a conflicting subset."
        )

        print(
            "They cannot all be satisfied "
            "at the same time."
        )

    else:

        print(
            "Solver returned UNKNOWN."
        )

    return result


# =========================================================
# MAIN
# =========================================================

def run_conflict_diagnosis_tests():

    print()
    print("========================================")
    print(" ENGINEERING CONFLICT DIAGNOSIS")
    print("========================================")
    print()

    # =====================================================
    # TEST 14-A
    # Consistent
    # =====================================================

    consistent_case = (
        build_consistent_case()
    )

    consistent_result = print_result(
        "TEST 14-A - CONSISTENT MODEL",
        consistent_case,
    )

    # =====================================================
    # TEST 14-B
    # Conflict
    # =====================================================

    print()
    print()

    conflicting_case = (
        build_conflicting_case()
    )

    conflicting_result = print_result(
        "TEST 14-B - CONFLICTING MODEL",
        conflicting_case,
    )

    # =====================================================
    # TEST RESULT
    # =====================================================

    print()
    print()

    print("========================================")
    print(" CONFLICT DIAGNOSIS TEST RESULT")
    print("========================================")
    print()

    consistent_ok = (
        consistent_result["status"]
        == "consistent"
    )

    conflict_ok = (
        conflicting_result["status"]
        == "conflict"
    )

    print(
        "Consistent Model Path :",
        "PASS"
        if consistent_ok
        else "FAIL"
    )

    print(
        "Conflict Model Path   :",
        "PASS"
        if conflict_ok
        else "FAIL"
    )

    print()

    if (
        consistent_ok
        and conflict_ok
    ):

        print(
            "CONFLICT DIAGNOSIS TEST PASSED"
        )

        print()

        print(
            "The system detected logical "
            "inconsistency and identified"
        )

        print(
            "a conflicting subset of "
            "Engineering Constraints."
        )

    else:

        print(
            "Conflict diagnosis requires fixes."
        )

    print()


if __name__ == "__main__":
    run_conflict_diagnosis_tests()