from decimal import Decimal

from z3 import (
    Real,
    RealVal,
    Optimize,
    Or,
    sat,
)


# =========================================================
# ENGINEERING CASE
# =========================================================

CASE = {
    "name": "Multiple Constraint Engineering Case",

    "variables": {
        "X": {
            "nominal": Decimal("10.00"),
            "feasible_min": Decimal("9.50"),
            "feasible_max": Decimal("10.50"),
            "verification_min": Decimal("9.90"),
            "verification_max": Decimal("10.10"),
        },

        "Y": {
            "nominal": Decimal("30.00"),
            "feasible_min": Decimal("29.50"),
            "feasible_max": Decimal("30.50"),
            "verification_min": Decimal("29.90"),
            "verification_max": Decimal("30.10"),
        },

        "D": {
            "nominal": Decimal("10.00"),
            "feasible_min": Decimal("9.50"),
            "feasible_max": Decimal("10.50"),
            "verification_min": Decimal("9.98"),
            "verification_max": Decimal("10.02"),
        },
    },

    "requirements": [
        {
            "id": "R1",
            "type": "range",
            "variable": "D",
            "min": Decimal("9.95"),
            "max": Decimal("10.05"),
            "description": "9.95 <= D <= 10.05",
        },

        {
            "id": "R2",
            "type": "difference_min",
            "left": "Y",
            "right": "X",
            "min": Decimal("20.00"),
            "description": "Y - X >= 20.00",
        },

        {
            "id": "R3",
            "type": "sum_upper",
            "variables": ["X", "Y"],
            "limit": Decimal("40.05"),
            "description": "X + Y <= 40.05",
        },
    ],
}


# =========================================================
# HELPERS
# =========================================================

def z3_value(value):
    """
    Decimal 값을 정확한 Z3 RealVal로 변환한다.
    """
    return RealVal(str(value))


def to_float(value):
    """
    Z3 rational 값을 Python float로 변환한다.
    """
    return (
        value.numerator_as_long()
        / value.denominator_as_long()
    )


# =========================================================
# VARIABLE CREATION
# =========================================================

def create_variables(case, requirement_id):
    """
    Case Data를 읽어 Z3 변수를 자동 생성한다.

    Requirement별 Solver가 서로 독립적으로 동작하도록
    변수 이름에 Requirement ID를 붙인다.
    """

    variables = {}

    for variable_name in case["variables"]:

        variables[variable_name] = Real(
            f"{requirement_id}_{variable_name}"
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
    모든 Engineering Variable에
    Feasible Domain을 적용한다.
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
# VERIFICATION PLAN
# =========================================================

def add_verification_plan(
    solver,
    case,
    variables,
):
    """
    현재 Verification Plan의
    개별 변수 허용범위를 적용한다.
    """

    for name, data in case["variables"].items():

        variable = variables[name]

        solver.add(
            variable
            >= z3_value(
                data["verification_min"]
            )
        )

        solver.add(
            variable
            <= z3_value(
                data["verification_max"]
            )
        )


# =========================================================
# REQUIREMENT VIOLATION MODEL
# =========================================================

def add_requirement_violation(
    optimizer,
    requirement,
    variables,
):
    """
    Requirement Type에 따라

    Requirement FAIL 조건과
    Violation 크기를 만든다.

    현재 지원:

    1. range
    2. difference_min
    3. sum_upper
    """

    requirement_type = requirement["type"]

    # -----------------------------------------------------
    # TYPE 1
    # RANGE
    #
    # min <= D <= max
    # -----------------------------------------------------

    if requirement_type == "range":

        variable = variables[
            requirement["variable"]
        ]

        minimum = z3_value(
            requirement["min"]
        )

        maximum = z3_value(
            requirement["max"]
        )

        # Requirement 위반:
        #
        # D < min
        # OR
        # D > max

        optimizer.add(
            Or(
                variable < minimum,
                variable > maximum,
            )
        )

        # Range는 아래쪽 위반과 위쪽 위반이 있으므로
        # 각각 따로 최대화하기보다
        # evaluate_requirement()에서 별도로 처리한다.

        return {
            "type": "range",
            "variable": variable,
        }

    # -----------------------------------------------------
    # TYPE 2
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

        minimum = z3_value(
            requirement["min"]
        )

        expression = (
            left - right
        )

        # Requirement 위반
        optimizer.add(
            expression < minimum
        )

        # 위반 크기
        violation = (
            minimum - expression
        )

        optimizer.maximize(
            violation
        )

        return {
            "type": "difference_min",
            "expression": expression,
            "violation": violation,
        }

    # -----------------------------------------------------
    # TYPE 3
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

        limit = z3_value(
            requirement["limit"]
        )

        # Requirement 위반
        optimizer.add(
            expression > limit
        )

        violation = (
            expression - limit
        )

        optimizer.maximize(
            violation
        )

        return {
            "type": "sum_upper",
            "expression": expression,
            "violation": violation,
        }

    else:

        raise ValueError(
            "Unsupported requirement type: "
            + requirement_type
        )


# =========================================================
# RANGE REQUIREMENT SPECIAL EVALUATION
# =========================================================

def evaluate_range_requirement(
    case,
    requirement,
):
    """
    Range Requirement는

    D < minimum
    또는
    D > maximum

    두 방향의 Escape가 존재할 수 있으므로
    각각 Stress Test한 뒤 더 큰 위반을 선택한다.
    """

    results = []

    # -----------------------------------------------------
    # LOWER SIDE ATTACK
    # -----------------------------------------------------

    variables = create_variables(
        case,
        requirement["id"] + "_LOW"
    )

    optimizer = Optimize()

    add_feasible_domain(
        optimizer,
        case,
        variables,
    )

    add_verification_plan(
        optimizer,
        case,
        variables,
    )

    variable = variables[
        requirement["variable"]
    ]

    minimum = z3_value(
        requirement["min"]
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

        state = {}

        for name, z3_variable in variables.items():

            state[name] = to_float(
                model[z3_variable]
            )

        actual = state[
            requirement["variable"]
        ]

        violation_value = (
            float(requirement["min"])
            - actual
        )

        results.append(
            {
                "escape_found": True,
                "state": state,
                "actual": actual,
                "violation": violation_value,
                "direction": "below minimum",
            }
        )

    # -----------------------------------------------------
    # UPPER SIDE ATTACK
    # -----------------------------------------------------

    variables = create_variables(
        case,
        requirement["id"] + "_HIGH"
    )

    optimizer = Optimize()

    add_feasible_domain(
        optimizer,
        case,
        variables,
    )

    add_verification_plan(
        optimizer,
        case,
        variables,
    )

    variable = variables[
        requirement["variable"]
    ]

    maximum = z3_value(
        requirement["max"]
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

        state = {}

        for name, z3_variable in variables.items():

            state[name] = to_float(
                model[z3_variable]
            )

        actual = state[
            requirement["variable"]
        ]

        violation_value = (
            actual
            - float(requirement["max"])
        )

        results.append(
            {
                "escape_found": True,
                "state": state,
                "actual": actual,
                "violation": violation_value,
                "direction": "above maximum",
            }
        )

    # -----------------------------------------------------
    # No Escape
    # -----------------------------------------------------

    if not results:

        return {
            "escape_found": False,
            "violation": 0.0,
        }

    # 더 큰 Range Violation 선택

    worst = max(
        results,
        key=lambda item:
            item["violation"]
    )

    return worst


# =========================================================
# GENERIC REQUIREMENT EVALUATION
# =========================================================

def evaluate_requirement(
    case,
    requirement,
):
    """
    하나의 Requirement에 대해

    Feasible
    AND
    Verification PASS
    AND
    Requirement FAIL

    상태를 탐색한다.
    """

    # Range는 두 방향이 있어서 별도 처리
    if requirement["type"] == "range":

        return evaluate_range_requirement(
            case,
            requirement,
        )

    variables = create_variables(
        case,
        requirement["id"]
    )

    optimizer = Optimize()

    # Feasible Domain
    add_feasible_domain(
        optimizer,
        case,
        variables,
    )

    # Verification Plan
    add_verification_plan(
        optimizer,
        case,
        variables,
    )

    # Requirement FAIL 조건
    model_info = (
        add_requirement_violation(
            optimizer,
            requirement,
            variables,
        )
    )

    # -----------------------------------------------------
    # Solve
    # -----------------------------------------------------

    if optimizer.check() != sat:

        return {
            "escape_found": False,
            "violation": 0.0,
        }

    model = optimizer.model()

    state = {}

    for name, variable in variables.items():

        state[name] = to_float(
            model[variable]
        )

    # -----------------------------------------------------
    # Actual Requirement Value
    # -----------------------------------------------------

    if requirement["type"] == "difference_min":

        actual_value = (
            state[requirement["left"]]
            - state[requirement["right"]]
        )

        violation_value = (
            float(requirement["min"])
            - actual_value
        )

    elif requirement["type"] == "sum_upper":

        actual_value = sum(
            state[name]
            for name
            in requirement["variables"]
        )

        violation_value = (
            actual_value
            - float(requirement["limit"])
        )

    else:

        actual_value = None
        violation_value = 0.0

    return {
        "escape_found": True,
        "state": state,
        "actual": actual_value,
        "violation": violation_value,
    }


# =========================================================
# PRINT RESULT
# =========================================================

def print_requirement_result(
    requirement,
    result,
):
    """
    Requirement별 결과 출력.
    """

    print()
    print(requirement["id"])
    print("----------------------------------------")

    print(
        "Requirement :",
        requirement["description"]
    )

    print()

    if not result["escape_found"]:

        print(
            "Sufficiency : PASSED"
        )

        print(
            "Escape Found: NO"
        )

        print()

        print(
            "Current Verification Plan "
            "guarantees this requirement"
        )

        print(
            "within the modeled Feasible Domain."
        )

        return

    print(
        "Sufficiency : FAILED"
    )

    print(
        "Escape Found: YES"
    )

    print()

    print(
        "Worst Violation:",
        f"{result['violation']:.3f}"
    )

    print()

    print("Escape State")

    for name, value in result["state"].items():

        print(
            f"{name:<8} = {value:.3f}"
        )

    print()

    # Requirement Type별 실제 값 표시

    if requirement["type"] == "range":

        print(
            "Actual Value :",
            f"{result['actual']:.3f}"
        )

        print(
            "Direction    :",
            result["direction"]
        )

    elif requirement["type"] == "difference_min":

        print(
            f"{requirement['left']} - "
            f"{requirement['right']} = "
            f"{result['actual']:.3f}"
        )

        print(
            "Required Minimum =",
            f"{float(requirement['min']):.3f}"
        )

    elif requirement["type"] == "sum_upper":

        expression_text = " + ".join(
            requirement["variables"]
        )

        print(
            expression_text,
            "=",
            f"{result['actual']:.3f}"
        )

        print(
            "Required Maximum =",
            f"{float(requirement['limit']):.3f}"
        )

    print()

    print("Verification -> PASS")
    print("Requirement  -> FAIL")


# =========================================================
# MAIN ENGINE
# =========================================================

def run_multi_constraint_test():

    print()
    print("========================================")
    print(" MULTIPLE CONSTRAINT VERIFICATION ENGINE")
    print("========================================")
    print()

    print("CASE")
    print("----------------------------------------")

    print(
        CASE["name"]
    )

    print()
    print()

    print("VARIABLES")
    print("----------------------------------------")

    for name, data in CASE["variables"].items():

        print()

        print(name)

        print(
            "  Nominal      :",
            data["nominal"]
        )

        print(
            "  Verification :",
            data["verification_min"],
            "~",
            data["verification_max"]
        )

    print()
    print()

    print("REQUIREMENT SUFFICIENCY TEST")
    print("========================================")

    results = []

    for requirement in CASE["requirements"]:

        result = evaluate_requirement(
            CASE,
            requirement,
        )

        results.append(
            {
                "requirement": requirement,
                "result": result,
            }
        )

        print_requirement_result(
            requirement,
            result,
        )

    # =====================================================
    # Summary
    # =====================================================

    passed = [
        item
        for item in results
        if not item["result"]["escape_found"]
    ]

    failed = [
        item
        for item in results
        if item["result"]["escape_found"]
    ]

    print()
    print()

    print("========================================")
    print(" VERIFICATION SUMMARY")
    print("========================================")

    print()

    print(
        "Total Requirements :",
        len(results)
    )

    print(
        "Sufficient         :",
        len(passed)
    )

    print(
        "Verification Gaps  :",
        len(failed)
    )

    print()

    if failed:

        print(
            "Gap Requirements:"
        )

        for item in failed:

            print(
                "-",
                item["requirement"]["id"],
                item["requirement"]["description"]
            )

    else:

        print(
            "No modeled Verification Gap found."
        )

    print()


if __name__ == "__main__":
    run_multi_constraint_test()