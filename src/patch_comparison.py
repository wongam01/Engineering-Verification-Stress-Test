from z3 import Real, RealVal, Optimize, sat


# ---------------------------------------------------------
# Helper
# ---------------------------------------------------------

def to_float(value):
    """Z3 rational 값을 Python float로 변환한다."""
    return value.numerator_as_long() / value.denominator_as_long()


# ---------------------------------------------------------
# Base Engineering Model
# ---------------------------------------------------------

def add_feasible_domain(solver, A, B):
    """
    현실적으로 가능한 Engineering State 범위.
    """

    solver.add(A >= RealVal("9.5"))
    solver.add(A <= RealVal("10.5"))

    solver.add(B >= RealVal("19.5"))
    solver.add(B <= RealVal("20.5"))


def add_base_verification_plan(solver, A, B):
    """
    현재 Verification Plan.

    A와 B를 각각 검사하지만,
    A + B 관계조건은 검사하지 않는다.
    """

    solver.add(A >= RealVal("9.9"))
    solver.add(A <= RealVal("10.1"))

    solver.add(B >= RealVal("19.9"))
    solver.add(B <= RealVal("20.1"))


# ---------------------------------------------------------
# Patch Definitions
# ---------------------------------------------------------

def apply_patch(solver, A, B, patch_name):
    """
    선택된 Verification Patch를 적용한다.
    """

    if patch_name == "none":
        # 기존 Verification Plan 그대로
        pass

    elif patch_name == "relation":
        # PATCH 1
        # 관계조건 자체를 Verification에 추가
        solver.add(A + B <= RealVal("30.05"))

    elif patch_name == "tighten_A":
        # PATCH 2
        # A의 허용 상한을 좁힘
        solver.add(A <= RealVal("10.05"))

    elif patch_name == "tighten_B":
        # PATCH 3
        # B의 허용 상한을 좁힘
        solver.add(B <= RealVal("20.05"))

    else:
        raise ValueError(f"Unknown patch: {patch_name}")


# ---------------------------------------------------------
# Stress Test
# ---------------------------------------------------------

def evaluate_patch(patch_name):
    """
    Patch를 적용한 뒤,

    Verification Plan을 통과하면서
    Requirement를 위반하는 상태가 존재하는지 확인하고,

    존재한다면 Worst Undetected Violation을 계산한다.
    """

    A = Real(f"{patch_name}_A")
    B = Real(f"{patch_name}_B")

    optimizer = Optimize()

    # ------------------------------------------
    # Feasible Domain
    # ------------------------------------------

    add_feasible_domain(optimizer, A, B)

    # ------------------------------------------
    # Current Verification Plan
    # ------------------------------------------

    add_base_verification_plan(optimizer, A, B)

    # ------------------------------------------
    # Candidate Patch
    # ------------------------------------------

    apply_patch(
        optimizer,
        A,
        B,
        patch_name
    )

    # ------------------------------------------
    # Engineering Requirement
    #
    # A + B <= 30.05
    #
    # Escape 상태:
    # A + B > 30.05
    # ------------------------------------------

    requirement_limit = RealVal("30.05")

    optimizer.add(
        A + B > requirement_limit
    )

    # ------------------------------------------
    # Worst Undetected Violation
    # ------------------------------------------

    violation = (
        A + B - requirement_limit
    )

    optimizer.maximize(violation)

    # ------------------------------------------
    # Solve
    # ------------------------------------------

    if optimizer.check() == sat:

        model = optimizer.model()

        a_value = to_float(model[A])
        b_value = to_float(model[B])

        total = a_value + b_value

        violation_value = (
            total - 30.05
        )

        return {
            "escape_found": True,
            "A": a_value,
            "B": b_value,
            "total": total,
            "violation": violation_value,
        }

    return {
        "escape_found": False,
        "violation": 0.0,
    }


# ---------------------------------------------------------
# Result Printer
# ---------------------------------------------------------

def print_result(title, description, result):
    """
    각 Patch 결과를 화면에 출력한다.
    """

    print(title)
    print("----------------------------------------")
    print(description)
    print()

    if result["escape_found"]:

        print("Escape Found             : YES")
        print(
            f"Worst Violation          : "
            f"{result['violation']:.3f}"
        )

        print()

        print("Worst Escape State")
        print(
            f"A = {result['A']:.3f}"
        )
        print(
            f"B = {result['B']:.3f}"
        )

        print()

        print(
            f"A + B = {result['total']:.3f}"
        )

    else:

        print("Escape Found             : NO")
        print("Worst Violation          : 0.000")
        print()
        print(
            "No Verification-PASS / "
            "Requirement-FAIL state found."
        )

    print()


# ---------------------------------------------------------
# Main Comparison
# ---------------------------------------------------------

def run_patch_comparison():

    print()
    print("========================================")
    print(" VERIFICATION PATCH COMPARISON")
    print("========================================")
    print()

    # ------------------------------------------
    # Current Plan
    # ------------------------------------------

    current = evaluate_patch("none")

    print_result(
        "CURRENT PLAN",
        "A <= 10.10, B <= 20.10",
        current
    )

    # ------------------------------------------
    # Patch 1
    # ------------------------------------------

    patch_1 = evaluate_patch("relation")

    print_result(
        "PATCH 1",
        "Add: A + B <= 30.05",
        patch_1
    )

    # ------------------------------------------
    # Patch 2
    # ------------------------------------------

    patch_2 = evaluate_patch("tighten_A")

    print_result(
        "PATCH 2",
        "Tighten: A <= 10.05",
        patch_2
    )

    # ------------------------------------------
    # Patch 3
    # ------------------------------------------

    patch_3 = evaluate_patch("tighten_B")

    print_result(
        "PATCH 3",
        "Tighten: B <= 20.05",
        patch_3
    )

    # ------------------------------------------
    # Comparison
    # ------------------------------------------

    candidates = [
        {
            "name": "PATCH 1",
            "description": "Add A + B <= 30.05",
            "result": patch_1,
        },
        {
            "name": "PATCH 2",
            "description": "Tighten A <= 10.05",
            "result": patch_2,
        },
        {
            "name": "PATCH 3",
            "description": "Tighten B <= 20.05",
            "result": patch_3,
        },
    ]

    print("PATCH COMPARISON")
    print("----------------------------------------")

    for candidate in candidates:

        result = candidate["result"]

        if result["escape_found"]:
            status = (
                f"Worst Violation "
                f"{result['violation']:.3f}"
            )
        else:
            status = "NO ESCAPE FOUND"

        print(
            f"{candidate['name']:<8} "
            f"-> {status}"
        )

    print()
    print()

    # ------------------------------------------
    # Best Patch
    # ------------------------------------------

    no_escape_candidates = [
        candidate
        for candidate in candidates
        if not candidate["result"]["escape_found"]
    ]

    print("BEST PATCH")
    print("----------------------------------------")

    if no_escape_candidates:

        best = no_escape_candidates[0]

        print(best["name"])
        print(best["description"])

        print()
        print(
            "Reason:"
        )
        print(
            "This candidate eliminated the modeled "
            "Verification Escape."
        )

    else:

        best = min(
            candidates,
            key=lambda candidate:
                candidate["result"]["violation"]
        )

        print(best["name"])
        print(best["description"])

        print()
        print(
            "Reason:"
        )
        print(
            "No candidate eliminated the Escape, "
            "but this candidate produced the "
            "smallest remaining Worst Violation."
        )

    print()


if __name__ == "__main__":
    run_patch_comparison()