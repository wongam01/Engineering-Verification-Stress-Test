from copy import deepcopy
from decimal import Decimal


# =========================================================
# SUPPORTED CONSTRAINT TYPES
# =========================================================

SUPPORTED_REQUIREMENT_TYPES = {
    "range",
    "difference_min",
    "sum_upper",
}


# =========================================================
# VALID ENGINEERING CASE
# =========================================================

VALID_CASE = {
    "name": "Validated Engineering Case",

    "variables": {
        "X": {
            "unit": "mm",
            "nominal": Decimal("10.00"),
            "feasible_min": Decimal("9.50"),
            "feasible_max": Decimal("10.50"),
            "verification_min": Decimal("9.90"),
            "verification_max": Decimal("10.10"),
        },

        "Y": {
            "unit": "mm",
            "nominal": Decimal("30.00"),
            "feasible_min": Decimal("29.50"),
            "feasible_max": Decimal("30.50"),
            "verification_min": Decimal("29.90"),
            "verification_max": Decimal("30.10"),
        },

        "D": {
            "unit": "mm",
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
            "unit": "mm",
            "min": Decimal("9.95"),
            "max": Decimal("10.05"),
        },

        {
            "id": "R2",
            "type": "difference_min",
            "left": "Y",
            "right": "X",
            "unit": "mm",
            "min": Decimal("20.00"),
        },

        {
            "id": "R3",
            "type": "sum_upper",
            "variables": ["X", "Y"],
            "unit": "mm",
            "limit": Decimal("40.05"),
        },
    ],
}


# =========================================================
# ERROR HELPER
# =========================================================

def add_error(errors, location, message):
    """
    Validation Error를 동일한 구조로 저장한다.
    """

    errors.append(
        {
            "location": location,
            "message": message,
        }
    )


# =========================================================
# VARIABLE VALIDATION
# =========================================================

def validate_variables(case, errors):
    """
    Engineering Variable 자체가 정상적으로 정의되어 있는지 확인한다.

    검사 항목:

    1. Feasible min <= max
    2. Verification min <= max
    3. Nominal이 Feasible Domain 안에 존재
    4. Verification 범위와 Feasible Domain이 완전히 분리되어 있지 않음
    5. Unit 존재
    """

    variables = case.get("variables")

    if not isinstance(variables, dict) or not variables:

        add_error(
            errors,
            "variables",
            "No engineering variables defined.",
        )

        return

    required_fields = [
        "unit",
        "nominal",
        "feasible_min",
        "feasible_max",
        "verification_min",
        "verification_max",
    ]

    for name, data in variables.items():

        location = f"Variable {name}"

        # -------------------------------------------------
        # Required Fields
        # -------------------------------------------------

        missing_fields = [
            field
            for field in required_fields
            if field not in data
        ]

        if missing_fields:

            add_error(
                errors,
                location,
                "Missing fields: "
                + ", ".join(missing_fields),
            )

            # 값이 없으면 이후 숫자 비교를 할 수 없으므로
            # 해당 변수 검증은 여기서 중단
            continue

        # -------------------------------------------------
        # Unit
        # -------------------------------------------------

        if not data["unit"]:

            add_error(
                errors,
                location,
                "Unit is missing.",
            )

        # -------------------------------------------------
        # Feasible Domain
        # -------------------------------------------------

        feasible_min = data["feasible_min"]
        feasible_max = data["feasible_max"]

        if feasible_min > feasible_max:

            add_error(
                errors,
                location,
                (
                    "Invalid Feasible Domain: "
                    "minimum is greater than maximum."
                ),
            )

        # -------------------------------------------------
        # Verification Range
        # -------------------------------------------------

        verification_min = data["verification_min"]
        verification_max = data["verification_max"]

        if verification_min > verification_max:

            add_error(
                errors,
                location,
                (
                    "Invalid Verification Range: "
                    "minimum is greater than maximum."
                ),
            )

        # -------------------------------------------------
        # Nominal State
        # -------------------------------------------------

        nominal = data["nominal"]

        if (
            feasible_min <= feasible_max
            and not (
                feasible_min
                <= nominal
                <= feasible_max
            )
        ):

            add_error(
                errors,
                location,
                (
                    f"Nominal value {nominal} "
                    "is outside the Feasible Domain."
                ),
            )

        # -------------------------------------------------
        # Feasible / Verification Intersection
        # -------------------------------------------------

        if (
            feasible_min <= feasible_max
            and verification_min <= verification_max
        ):

            no_overlap = (
                verification_max < feasible_min
                or
                verification_min > feasible_max
            )

            if no_overlap:

                add_error(
                    errors,
                    location,
                    (
                        "Verification Range has no overlap "
                        "with the Feasible Domain."
                    ),
                )


# =========================================================
# REQUIREMENT VARIABLE CHECK
# =========================================================

def validate_variable_reference(
    variable_name,
    requirement_id,
    case,
    errors,
):
    """
    Requirement가 존재하지 않는 변수를 참조하는지 검사한다.
    """

    if variable_name not in case["variables"]:

        add_error(
            errors,
            f"Requirement {requirement_id}",
            (
                f"Unknown variable: {variable_name}"
            ),
        )

        return False

    return True


# =========================================================
# UNIT CHECK
# =========================================================

def validate_units(
    variable_names,
    requirement,
    case,
    errors,
):
    """
    하나의 관계식에 들어가는 변수들의 Unit이 서로 같은지 검사한다.

    현재 Prototype에서는
    동일 단위의 선형 관계만 허용한다.
    """

    requirement_id = requirement["id"]

    valid_variables = [
        name
        for name in variable_names
        if name in case["variables"]
    ]

    if not valid_variables:
        return

    variable_units = {
        case["variables"][name]["unit"]
        for name in valid_variables
    }

    # -----------------------------------------------------
    # Variable끼리 Unit이 다른 경우
    # -----------------------------------------------------

    if len(variable_units) > 1:

        add_error(
            errors,
            f"Requirement {requirement_id}",
            (
                "Unit mismatch between variables: "
                + ", ".join(
                    f"{name}="
                    f"{case['variables'][name]['unit']}"
                    for name in valid_variables
                )
            ),
        )

        return

    # -----------------------------------------------------
    # Requirement Unit과 Variable Unit 비교
    # -----------------------------------------------------

    requirement_unit = requirement.get("unit")

    if requirement_unit is None:

        add_error(
            errors,
            f"Requirement {requirement_id}",
            "Requirement unit is missing.",
        )

        return

    variable_unit = next(
        iter(variable_units)
    )

    if requirement_unit != variable_unit:

        add_error(
            errors,
            f"Requirement {requirement_id}",
            (
                f"Requirement unit {requirement_unit} "
                f"does not match variable unit "
                f"{variable_unit}."
            ),
        )


# =========================================================
# REQUIREMENT VALIDATION
# =========================================================

def validate_requirements(case, errors):
    """
    Requirement 구조가 정상적인지 검사한다.

    현재 지원:

    1. range
    2. difference_min
    3. sum_upper
    """

    requirements = case.get("requirements")

    if not isinstance(requirements, list) or not requirements:

        add_error(
            errors,
            "requirements",
            "No engineering requirements defined.",
        )

        return

    seen_ids = set()

    for requirement in requirements:

        requirement_id = requirement.get("id")

        # -------------------------------------------------
        # Requirement ID
        # -------------------------------------------------

        if not requirement_id:

            add_error(
                errors,
                "Requirement",
                "Requirement ID is missing.",
            )

            continue

        if requirement_id in seen_ids:

            add_error(
                errors,
                f"Requirement {requirement_id}",
                "Duplicate Requirement ID.",
            )

        seen_ids.add(requirement_id)

        # -------------------------------------------------
        # Requirement Type
        # -------------------------------------------------

        requirement_type = requirement.get(
            "type"
        )

        if requirement_type not in (
            SUPPORTED_REQUIREMENT_TYPES
        ):

            add_error(
                errors,
                f"Requirement {requirement_id}",
                (
                    "Unsupported constraint type: "
                    f"{requirement_type}"
                ),
            )

            continue

        # =================================================
        # RANGE
        # =================================================

        if requirement_type == "range":

            variable_name = requirement.get(
                "variable"
            )

            if variable_name is None:

                add_error(
                    errors,
                    f"Requirement {requirement_id}",
                    "Range variable is missing.",
                )

                continue

            variable_exists = (
                validate_variable_reference(
                    variable_name,
                    requirement_id,
                    case,
                    errors,
                )
            )

            if (
                "min" not in requirement
                or
                "max" not in requirement
            ):

                add_error(
                    errors,
                    f"Requirement {requirement_id}",
                    "Range min/max is missing.",
                )

                continue

            minimum = requirement["min"]
            maximum = requirement["max"]

            if minimum > maximum:

                add_error(
                    errors,
                    f"Requirement {requirement_id}",
                    (
                        "Invalid requirement range: "
                        "minimum is greater than maximum."
                    ),
                )

            if variable_exists:

                validate_units(
                    [variable_name],
                    requirement,
                    case,
                    errors,
                )

        # =================================================
        # DIFFERENCE MINIMUM
        # =================================================

        elif requirement_type == "difference_min":

            left = requirement.get("left")
            right = requirement.get("right")

            if left is None or right is None:

                add_error(
                    errors,
                    f"Requirement {requirement_id}",
                    (
                        "Difference constraint requires "
                        "left and right variables."
                    ),
                )

                continue

            left_exists = (
                validate_variable_reference(
                    left,
                    requirement_id,
                    case,
                    errors,
                )
            )

            right_exists = (
                validate_variable_reference(
                    right,
                    requirement_id,
                    case,
                    errors,
                )
            )

            if "min" not in requirement:

                add_error(
                    errors,
                    f"Requirement {requirement_id}",
                    (
                        "Difference minimum value "
                        "is missing."
                    ),
                )

            if left_exists and right_exists:

                validate_units(
                    [left, right],
                    requirement,
                    case,
                    errors,
                )

        # =================================================
        # SUM UPPER
        # =================================================

        elif requirement_type == "sum_upper":

            variable_names = requirement.get(
                "variables"
            )

            if (
                not isinstance(variable_names, list)
                or
                not variable_names
            ):

                add_error(
                    errors,
                    f"Requirement {requirement_id}",
                    (
                        "Sum constraint requires "
                        "one or more variables."
                    ),
                )

                continue

            all_exist = True

            for variable_name in variable_names:

                exists = (
                    validate_variable_reference(
                        variable_name,
                        requirement_id,
                        case,
                        errors,
                    )
                )

                if not exists:
                    all_exist = False

            if "limit" not in requirement:

                add_error(
                    errors,
                    f"Requirement {requirement_id}",
                    "Sum upper limit is missing.",
                )

            if all_exist:

                validate_units(
                    variable_names,
                    requirement,
                    case,
                    errors,
                )


# =========================================================
# MAIN VALIDATOR
# =========================================================

def validate_case(case):
    """
    전체 Engineering Case를 검사한다.

    반환:

    {
        "valid": True / False,
        "errors": [...]
    }
    """

    errors = []

    validate_variables(
        case,
        errors,
    )

    # Variables 구조 자체가 없는 경우
    # Requirement Validation 중 KeyError가 발생하지 않도록 방지

    if (
        isinstance(case.get("variables"), dict)
        and case["variables"]
    ):

        validate_requirements(
            case,
            errors,
        )

    return {
        "valid": len(errors) == 0,
        "errors": errors,
    }


# =========================================================
# SOLVER GATE
# =========================================================

def solver_gate(case):
    """
    Validator가 통과한 Case만
    Solver로 전달할 수 있도록 Gate 역할을 한다.
    """

    result = validate_case(case)

    if result["valid"]:

        return {
            "solver_allowed": True,
            "validation": result,
        }

    return {
        "solver_allowed": False,
        "validation": result,
    }


# =========================================================
# TEST RESULT PRINTER
# =========================================================

def print_validation_result(
    title,
    case,
):
    """
    Validation Test 결과를 보기 쉽게 출력한다.
    """

    print()
    print(title)
    print("----------------------------------------")

    result = solver_gate(case)

    if result["solver_allowed"]:

        print("Validation       : PASSED")
        print("Solver Execution : ALLOWED")

    else:

        print("Validation       : FAILED")
        print("Solver Execution : BLOCKED")

        print()

        print("Detected Problems")

        for index, error in enumerate(
            result["validation"]["errors"],
            start=1,
        ):

            print(
                f"{index}. "
                f"[{error['location']}] "
                f"{error['message']}"
            )

    return result


# =========================================================
# INVALID TEST CASE GENERATOR
# =========================================================

def build_test_cases():
    """
    Validator를 일부러 공격하기 위한
    잘못된 Engineering Case들을 만든다.
    """

    test_cases = []

    # -----------------------------------------------------
    # TEST 1
    # 정상 Case
    # -----------------------------------------------------

    test_cases.append(
        (
            "TEST 1 - Valid Engineering Case",
            deepcopy(VALID_CASE),
            True,
        )
    )

    # -----------------------------------------------------
    # TEST 2
    # 존재하지 않는 변수 Z 사용
    # -----------------------------------------------------

    unknown_variable_case = deepcopy(
        VALID_CASE
    )

    unknown_variable_case[
        "requirements"
    ].append(
        {
            "id": "R4",
            "type": "sum_upper",
            "variables": ["X", "Z"],
            "unit": "mm",
            "limit": Decimal("50.00"),
        }
    )

    test_cases.append(
        (
            "TEST 2 - Unknown Variable",
            unknown_variable_case,
            False,
        )
    )

    # -----------------------------------------------------
    # TEST 3
    # Verification min > max
    # -----------------------------------------------------

    invalid_verification_case = deepcopy(
        VALID_CASE
    )

    invalid_verification_case[
        "variables"
    ]["X"]["verification_min"] = (
        Decimal("10.20")
    )

    invalid_verification_case[
        "variables"
    ]["X"]["verification_max"] = (
        Decimal("10.10")
    )

    test_cases.append(
        (
            "TEST 3 - Invalid Verification Range",
            invalid_verification_case,
            False,
        )
    )

    # -----------------------------------------------------
    # TEST 4
    # Nominal State가 Feasible Domain 밖
    # -----------------------------------------------------

    invalid_nominal_case = deepcopy(
        VALID_CASE
    )

    invalid_nominal_case[
        "variables"
    ]["X"]["nominal"] = Decimal("11.00")

    test_cases.append(
        (
            "TEST 4 - Nominal Outside Feasible Domain",
            invalid_nominal_case,
            False,
        )
    )

    # -----------------------------------------------------
    # TEST 5
    # Verification과 Feasible Domain이 완전히 분리
    # -----------------------------------------------------

    no_overlap_case = deepcopy(
        VALID_CASE
    )

    no_overlap_case[
        "variables"
    ]["X"]["verification_min"] = (
        Decimal("11.00")
    )

    no_overlap_case[
        "variables"
    ]["X"]["verification_max"] = (
        Decimal("12.00")
    )

    test_cases.append(
        (
            "TEST 5 - Verification Outside Feasible Domain",
            no_overlap_case,
            False,
        )
    )

    # -----------------------------------------------------
    # TEST 6
    # 지원하지 않는 Constraint Type
    # -----------------------------------------------------

    unsupported_case = deepcopy(
        VALID_CASE
    )

    unsupported_case[
        "requirements"
    ][0]["type"] = "product_upper"

    test_cases.append(
        (
            "TEST 6 - Unsupported Constraint Type",
            unsupported_case,
            False,
        )
    )

    # -----------------------------------------------------
    # TEST 7
    # Unit mismatch
    #
    # Y를 mm가 아닌 MPa로 바꿔서
    # X + Y 같은 잘못된 수식을 탐지
    # -----------------------------------------------------

    unit_mismatch_case = deepcopy(
        VALID_CASE
    )

    unit_mismatch_case[
        "variables"
    ]["Y"]["unit"] = "MPa"

    test_cases.append(
        (
            "TEST 7 - Unit Mismatch",
            unit_mismatch_case,
            False,
        )
    )

    return test_cases


# =========================================================
# MAIN
# =========================================================

def run_validator_tests():

    print()
    print("========================================")
    print(" ENGINEERING CONSTRAINT VALIDATOR")
    print("========================================")
    print()

    test_cases = build_test_cases()

    passed_tests = 0

    for (
        title,
        case,
        expected_valid,
    ) in test_cases:

        result = print_validation_result(
            title,
            case,
        )

        actual_valid = (
            result["solver_allowed"]
        )

        expected_result = (
            actual_valid == expected_valid
        )

        print()

        print(
            "Expected Solver Access :",
            (
                "ALLOWED"
                if expected_valid
                else "BLOCKED"
            ),
        )

        print(
            "Test Result             :",
            (
                "PASS"
                if expected_result
                else "FAIL"
            ),
        )

        if expected_result:
            passed_tests += 1

        print()

    # =====================================================
    # SUMMARY
    # =====================================================

    print()
    print("========================================")
    print(" VALIDATOR TEST SUMMARY")
    print("========================================")
    print()

    print(
        "Total Tests :",
        len(test_cases)
    )

    print(
        "Passed      :",
        passed_tests
    )

    print(
        "Failed      :",
        len(test_cases) - passed_tests
    )

    print()

    if passed_tests == len(test_cases):

        print(
            "ALL VALIDATOR TESTS PASSED"
        )

        print()

        print(
            "Invalid Engineering Data was blocked"
        )

        print(
            "before Solver execution."
        )

    else:

        print(
            "Validator requires additional fixes."
        )

    print()


if __name__ == "__main__":
    run_validator_tests()
