from copy import deepcopy
from decimal import Decimal

from constraint_validator import (
    VALID_CASE,
    validate_case,
)

from multi_constraint_engine import (
    evaluate_requirement,
)


# =========================================================
# VALIDATE -> SOLVE PIPELINE
# =========================================================

def run_verification_pipeline(case):
    """
    Engineering Case를 먼저 검증한 뒤,
    Validation을 통과한 경우에만
    Verification Solver를 실행한다.
    """

    print()
    print("========================================")
    print(" ENGINEERING VERIFICATION PIPELINE")
    print("========================================")
    print()

    print("CASE")
    print("----------------------------------------")
    print(case.get("name", "Unnamed Case"))

    # =====================================================
    # STEP 1
    # VALIDATION
    # =====================================================

    print()
    print()

    print("STEP 1 - CONSTRAINT VALIDATION")
    print("----------------------------------------")

    validation = validate_case(case)

    if not validation["valid"]:

        print("Validation       : FAILED")
        print("Solver Execution : BLOCKED")

        print()
        print("Detected Problems")

        for index, error in enumerate(
            validation["errors"],
            start=1,
        ):
            print(
                f"{index}. "
                f"[{error['location']}] "
                f"{error['message']}"
            )

        print()
        print(
            "Pipeline stopped before Solver execution."
        )

        return {
            "validation_passed": False,
            "solver_executed": False,
            "results": [],
        }

    print("Validation       : PASSED")
    print("Solver Execution : ALLOWED")

    # =====================================================
    # STEP 2
    # REQUIREMENT SUFFICIENCY ANALYSIS
    # =====================================================

    print()
    print()

    print("STEP 2 - VERIFICATION SUFFICIENCY")
    print("========================================")

    results = []

    for requirement in case["requirements"]:

        result = evaluate_requirement(
            case,
            requirement,
        )

        results.append(
            {
                "requirement": requirement,
                "result": result,
            }
        )

        print()
        print(requirement["id"])
        print("----------------------------------------")

        print(
            "Type        :",
            requirement["type"]
        )

        if result["escape_found"]:

            print("Sufficiency : FAILED")
            print("Escape Found: YES")

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

        else:

            print("Sufficiency : PASSED")
            print("Escape Found: NO")

    # =====================================================
    # STEP 3
    # SUMMARY
    # =====================================================

    sufficient = [
        item
        for item in results
        if not item["result"]["escape_found"]
    ]

    gaps = [
        item
        for item in results
        if item["result"]["escape_found"]
    ]

    print()
    print()

    print("STEP 3 - VERIFICATION SUMMARY")
    print("========================================")

    print()

    print(
        "Total Requirements :",
        len(results)
    )

    print(
        "Sufficient         :",
        len(sufficient)
    )

    print(
        "Verification Gaps  :",
        len(gaps)
    )

    print()

    if gaps:

        print("Gap Requirements:")

        for item in gaps:
            requirement = item["requirement"]

            print(
                "-",
                requirement["id"],
                requirement["type"]
            )

    else:

        print(
            "No modeled Verification Gap found."
        )

    print()

    return {
        "validation_passed": True,
        "solver_executed": True,
        "results": results,
    }


# =========================================================
# TEST CASES
# =========================================================

def build_valid_case():
    """
    Validator와 Solver가 모두 처리할 수 있는 정상 Case.
    """

    return deepcopy(VALID_CASE)


def build_invalid_case():
    """
    일부러 Unit Error를 만든 Case.

    X = mm
    Y = MPa

    이 상태에서 X + Y 관계식이 존재하므로
    Solver 실행 전에 차단되어야 한다.
    """

    case = deepcopy(VALID_CASE)

    case["name"] = (
        "Invalid Unit Engineering Case"
    )

    case["variables"]["Y"]["unit"] = "MPa"

    return case


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":

    # -----------------------------------------------------
    # TEST 12-A
    # Valid Input
    #
    # Validator PASS
    # -> Solver 실행
    # -----------------------------------------------------

    print()
    print()
    print("########################################")
    print(" TEST 12-A : VALID INPUT")
    print("########################################")

    valid_case = build_valid_case()

    valid_result = run_verification_pipeline(
        valid_case
    )

    # -----------------------------------------------------
    # TEST 12-B
    # Invalid Input
    #
    # Validator FAIL
    # -> Solver BLOCK
    # -----------------------------------------------------

    print()
    print()
    print("########################################")
    print(" TEST 12-B : INVALID INPUT")
    print("########################################")

    invalid_case = build_invalid_case()

    invalid_result = run_verification_pipeline(
        invalid_case
    )

    # -----------------------------------------------------
    # FINAL PIPELINE TEST
    # -----------------------------------------------------

    print()
    print()

    print("========================================")
    print(" PIPELINE TEST RESULT")
    print("========================================")

    print()

    valid_path_ok = (
        valid_result["validation_passed"]
        and
        valid_result["solver_executed"]
    )

    invalid_path_ok = (
        not invalid_result["validation_passed"]
        and
        not invalid_result["solver_executed"]
    )

    print(
        "Valid Input Path   :",
        "PASS"
        if valid_path_ok
        else "FAIL"
    )

    print(
        "Invalid Input Path :",
        "PASS"
        if invalid_path_ok
        else "FAIL"
    )

    print()

    if valid_path_ok and invalid_path_ok:

        print("PIPELINE TEST PASSED")

        print()

        print(
            "Validated Engineering Data reached "
            "the Solver."
        )

        print(
            "Invalid Engineering Data was blocked "
            "before Solver execution."
        )

    else:

        print(
            "Pipeline requires additional fixes."
        )

    print()