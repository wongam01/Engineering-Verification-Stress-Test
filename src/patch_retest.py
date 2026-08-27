from z3 import Real, RealVal, Solver, sat


def to_float(value):
    """Z3 rational 값을 Python float로 변환한다."""
    return value.numerator_as_long() / value.denominator_as_long()


def add_feasible_domain(solver, A, B):
    """
    현실적으로 가능한 Engineering State.
    """

    solver.add(A >= RealVal("9.5"))
    solver.add(A <= RealVal("10.5"))

    solver.add(B >= RealVal("19.5"))
    solver.add(B <= RealVal("20.5"))


def add_base_verification_plan(solver, A, B):
    """
    현재 Verification Plan.

    A와 B의 개별 범위만 검사한다.
    """

    solver.add(A >= RealVal("9.9"))
    solver.add(A <= RealVal("10.1"))

    solver.add(B >= RealVal("19.9"))
    solver.add(B <= RealVal("20.1"))


def check_verification_sufficiency(use_patch=False):
    """
    현재 Verification Plan을 통과하면서
    Requirement를 위반하는 상태가 존재하는지 검사한다.

    use_patch=True이면
    관계조건 A + B <= 30.05를
    Verification Plan에 추가한다.
    """

    A = Real("patch_A")
    B = Real("patch_B")

    solver = Solver()

    # ------------------------------------------
    # Feasible Domain
    # ------------------------------------------

    add_feasible_domain(solver, A, B)

    # ------------------------------------------
    # Current Verification Plan
    # ------------------------------------------

    add_base_verification_plan(solver, A, B)

    # ------------------------------------------
    # Verification Patch
    # ------------------------------------------

    if use_patch:
        solver.add(A + B <= RealVal("30.05"))

    # ------------------------------------------
    # Engineering Requirement violation
    #
    # Requirement:
    # A + B <= 30.05
    #
    # Violation:
    # A + B > 30.05
    # ------------------------------------------

    solver.add(A + B > RealVal("30.05"))

    # ------------------------------------------
    # Search
    # ------------------------------------------

    if solver.check() == sat:
        model = solver.model()

        a_value = to_float(model[A])
        b_value = to_float(model[B])
        total = a_value + b_value

        return {
            "escape_found": True,
            "A": a_value,
            "B": b_value,
            "total": total,
        }

    return {
        "escape_found": False
    }


def run_patch_retest():
    """
    Patch 적용 전/후 Verification Sufficiency를 비교한다.
    """

    print()
    print("========================================")
    print(" VERIFICATION PATCH & RE-TEST")
    print("========================================")
    print()

    # ==========================================
    # BEFORE PATCH
    # ==========================================

    print("BEFORE PATCH")
    print("----------------------------------------")

    before = check_verification_sufficiency(
        use_patch=False
    )

    if before["escape_found"]:

        print("Verification Sufficiency -> FAILED")
        print()

        print("Escape Witness")
        print(f"A = {before['A']:.3f}")
        print(f"B = {before['B']:.3f}")
        print()

        print(f"A + B = {before['total']:.3f}")
        print("Requirement Limit = 30.050")
        print()

        print("Verification -> PASS")
        print("Requirement  -> FAIL")

    else:

        print("No counterexample found.")

    # ==========================================
    # PATCH
    # ==========================================

    print()
    print()

    print("PROPOSED PATCH")
    print("----------------------------------------")

    print("Add Verification Constraint:")
    print()
    print("A + B <= 30.05")

    # ==========================================
    # AFTER PATCH
    # ==========================================

    print()
    print()

    print("AFTER PATCH")
    print("----------------------------------------")

    after = check_verification_sufficiency(
        use_patch=True
    )

    if after["escape_found"]:

        print("Verification Sufficiency -> FAILED")
        print()

        print("Escape still exists.")
        print(f"A = {after['A']:.3f}")
        print(f"B = {after['B']:.3f}")

    else:

        print("Verification Sufficiency -> PASSED")
        print()
        print("NO COUNTEREXAMPLE FOUND")
        print()
        print(
            "No Verification-PASS / Requirement-FAIL "
            "state was found"
        )
        print(
            "within the modeled Feasible Domain."
        )

    # ==========================================
    # RESULT
    # ==========================================

    print()
    print()

    print("RE-TEST RESULT")
    print("----------------------------------------")

    if (
        before["escape_found"]
        and not after["escape_found"]
    ):

        print("Before Patch : VULNERABLE")
        print("After Patch  : NO ESCAPE FOUND")
        print()
        print("PATCH VERIFIED")

    else:

        print("Patch did not close the modeled gap.")

    print()


if __name__ == "__main__":
    run_patch_retest()