from copy import deepcopy
from decimal import Decimal

from z3 import (
    Real,
    RealVal,
    Solver,
    sat,
)

from constraint_validator import (
    VALID_CASE,
    validate_case,
)


# =========================================================
# HELPERS
# =========================================================

def z3_value(value):
    """
    Decimal 값을 정확한 Z3 값으로 변환한다.
    """
    return RealVal(str(value))


# =========================================================
# VARIABLE CREATION
# =========================================================

def create_variables(case, prefix):
    """
    Case에 정의된 Engineering Variable을
    Z3 Real 변수로 자동 생성한다.
    """

    variables = {}

    for name in case["variables"]:
        variables[name] = Real(
            f"{prefix}_{name}"
        )

    return variables


# =========================================================
# FEASIBLE DOMAIN
# =========================================================

def add_feasible_domain(
    solver,
    case,
    variables,
):
    """
    현실적으로 가능한 Engineering State 범위를 추가한다.
    """

    for name, data in case["variables"].items():

        variable = variables[name]

        solver.add(
            variable
            >= z3_value(data["feasible_min"])
        )

        solver.add(
            variable
            <= z3_value(data["feasible_max"])
        )


# =========================================================
# REQUIREMENT SATISFACTION
# =========================================================

def add_requirement(
    solver,
    requirement,
    variables,
):
    """
    Requirement를 위반 조건이 아니라
    실제 만족 조건으로 Solver에 추가한다.

    지원 타입:

    1. range
    2. difference_min
    3. sum_upper
    """

    requirement_type = requirement["type"]

    # -----------------------------------------------------
    # RANGE
    #
    # min <= D <= max
    # -----------------------------------------------------

    if requirement_type == "range":

        variable = variables[
            requirement["variable"]
        ]

        solver.add(
            variable
            >= z3_value(requirement["min"])
        )

        solver.add(
            variable
            <= z3_value(requirement["max"])
        )

    # -----------------------------------------------------
    # DIFFERENCE MINIMUM
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

        solver.add(
            left - right
            >= z3_value(requirement["min"])
        )

    # -----------------------------------------------------
    # SUM UPPER
    #
    # X + Y + ... <= limit
    # -----------------------------------------------------

    elif requirement_type == "sum_upper":

        expression = 0

        for variable_name in requirement["variables"]:

            expression = (
                expression
                + variables[variable_name]
            )

        solver.add(
            expression
            <= z3_value(requirement["limit"])
        )

    else:

        raise ValueError(
            "Unsupported requirement type: "
            + requirement_type
        )


# =========================================================
# LOGICAL CONSISTENCY CHECK
# =========================================================

def check_logical_consistency(case):
    """
    질문:

    현실적으로 가능한 상태 중에서
    모든 Engineering Requirement를
    동시에 만족하는 상태가 존재하는가?

    SAT:
        적어도 하나 존재

    UNSAT:
        Requirement들이 서로 또는
        Feasible Domain과 모순됨
    """

    variables = create_variables(
        case,
        "consistency"
    )

    solver = Solver()

    # -----------------------------------------------------
    # Feasible Domain
    # -----------------------------------------------------

    add_feasible_domain(
        solver,
        case,
        variables,
    )

    # -----------------------------------------------------
    # All Engineering Requirements
    # -----------------------------------------------------

    for requirement in case["requirements"]:

        add_requirement(
            solver,
            requirement,
            variables,
        )

    # -----------------------------------------------------
    # Solve
    # -----------------------------------------------------

    if solver.check() == sat:

        model = solver.model()

        example_state = {}

        for name, variable in variables.items():

            value = model[
                variable
            ]

            if value is not None:

                example_state[name] = (
                    value.numerator_as_long()
                    / value.denominator_as_long()
                )

        return {
            "consistent": True,
            "example_state": example_state,
        }

    return {
        "consistent": False,
        "example_state": None,
    }


# =========================================================
# FULL MODEL GATE
# =========================================================

def engineering_model_gate(case):
    """
    두 단계로 입력을 검증한다.

    STEP 1
    Structural Validation

    STEP 2
    Logical Consistency Validation
    """

    # -----------------------------------------------------
    # STEP 1
    # Structural Validator
    # -----------------------------------------------------

    structural = validate_case(case)

    if not structural["valid"]:

        return {
            "allowed": False,
            "stage": "structural_validation",
            "errors": structural["errors"],
        }

    # -----------------------------------------------------
    # STEP 2
    # Logical Consistency
    # -----------------------------------------------------

    logical = check_logical_consistency(
        case
    )

    if not logical["consistent"]:

        return {
            "allowed": False,
            "stage": "logical_consistency",
            "errors": [
                {
                    "location": "Engineering Model",
                    "message": (
                        "No feasible state can satisfy "
                        "all Engineering Requirements "
                        "simultaneously."
                    ),
                }
            ],
        }

    # -----------------------------------------------------
    # PASS
    # -----------------------------------------------------

    return {
        "allowed": True,
        "stage": "passed",
        "example_state": logical[
            "example_state"
        ],
    }


# =========================================================
# TEST CASES
# =========================================================

def build_valid_case():
    """
    기존 정상 Engineering Case.
    """

    case = deepcopy(
        VALID_CASE
    )

    case["name"] = (
        "Logically Consistent Engineering Case"
    )

    return case


def build_contradictory_case():
    """
    각 값의 형식은 정상이다.

    하지만 새로운 Requirement:

        X + Y <= 38.90

    를 추가한다.

    Feasible Domain:

        X >= 9.50
        Y >= 29.50

    따라서 최소 가능한 합:

        X + Y >= 39.00

    즉

        X + Y <= 38.90

    을 만족할 현실적 상태가 존재하지 않는다.
    """

    case = deepcopy(
        VALID_CASE
    )

    case["name"] = (
        "Logically Contradictory Engineering Case"
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

def print_gate_result(
    title,
    case,
):
    """
    Engineering Model Gate 결과 출력.
    """

    print()
    print(title)
    print("----------------------------------------")

    print(
        "Case:",
        case["name"]
    )

    print()

    result = engineering_model_gate(
        case
    )

    if result["allowed"]:

        print(
            "Structural Validation : PASSED"
        )

        print(
            "Logical Consistency   : PASSED"
        )

        print(
            "Solver Access         : ALLOWED"
        )

        print()

        print(
            "Example Valid Engineering State"
        )

        for name, value in (
            result["example_state"].items()
        ):

            print(
                f"{name:<8} = {value:.3f}"
            )

    else:

        if (
            result["stage"]
            == "structural_validation"
        ):

            print(
                "Structural Validation : FAILED"
            )

            print(
                "Logical Consistency   : NOT RUN"
            )

        elif (
            result["stage"]
            == "logical_consistency"
        ):

            print(
                "Structural Validation : PASSED"
            )

            print(
                "Logical Consistency   : FAILED"
            )

        print(
            "Solver Access         : BLOCKED"
        )

        print()

        print("Detected Problems")

        for index, error in enumerate(
            result["errors"],
            start=1,
        ):

            print(
                f"{index}. "
                f"[{error['location']}] "
                f"{error['message']}"
            )

    return result


# =========================================================
# MAIN TEST
# =========================================================

def run_logical_consistency_tests():

    print()
    print("========================================")
    print(" ENGINEERING LOGICAL CONSISTENCY TEST")
    print("========================================")
    print()

    # =====================================================
    # TEST 13-A
    # Valid Model
    # =====================================================

    valid_case = build_valid_case()

    valid_result = print_gate_result(
        "TEST 13-A - CONSISTENT MODEL",
        valid_case,
    )

    # =====================================================
    # TEST 13-B
    # Contradictory Model
    # =====================================================

    print()
    print()

    invalid_case = (
        build_contradictory_case()
    )

    invalid_result = print_gate_result(
        "TEST 13-B - CONTRADICTORY MODEL",
        invalid_case,
    )

    # =====================================================
    # FINAL TEST RESULT
    # =====================================================

    print()
    print()

    print("========================================")
    print(" LOGICAL CONSISTENCY TEST RESULT")
    print("========================================")
    print()

    valid_path_ok = (
        valid_result["allowed"]
    )

    contradictory_path_ok = (
        not invalid_result["allowed"]
        and
        invalid_result["stage"]
        == "logical_consistency"
    )

    print(
        "Consistent Model Path     :",
        "PASS"
        if valid_path_ok
        else "FAIL"
    )

    print(
        "Contradictory Model Path  :",
        "PASS"
        if contradictory_path_ok
        else "FAIL"
    )

    print()

    if (
        valid_path_ok
        and contradictory_path_ok
    ):

        print(
            "LOGICAL CONSISTENCY TEST PASSED"
        )

        print()

        print(
            "Structurally valid but logically "
            "impossible Engineering Data"
        )

        print(
            "was blocked before Verification "
            "Stress Testing."
        )

    else:

        print(
            "Logical consistency checking "
            "requires additional fixes."
        )

    print()


if __name__ == "__main__":
    run_logical_consistency_tests()