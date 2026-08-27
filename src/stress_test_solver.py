from z3 import Real, RealVal, Solver, Optimize, sat


# ---------------------------------------------------------
# Helper
# ---------------------------------------------------------

def to_float(value):
    """Z3의 정확한 유리수를 Python float로 변환한다."""
    return value.numerator_as_long() / value.denominator_as_long()


# ---------------------------------------------------------
# Engineering Model
# ---------------------------------------------------------

def add_feasible_domain(solver, A, B):
    """
    현실적으로 발생 가능한 Engineering State 범위.
    현재 Prototype에서는 사용자가 정의한 범위라고 가정한다.
    """

    solver.add(A >= RealVal("9.5"))
    solver.add(A <= RealVal("10.5"))

    solver.add(B >= RealVal("19.5"))
    solver.add(B <= RealVal("20.5"))


def add_verification_plan(solver, A, B):
    """
    현재 Verification / Inspection Plan.
    이 조건을 모두 만족하면 검사에서는 PASS라고 가정한다.
    """

    solver.add(A >= RealVal("9.9"))
    solver.add(A <= RealVal("10.1"))

    solver.add(B >= RealVal("19.9"))
    solver.add(B <= RealVal("20.1"))


# ---------------------------------------------------------
# TEST 1
# Escape Existence
# ---------------------------------------------------------

def find_escape():
    """
    Feasible Domain 안에서
    Verification Plan은 PASS하지만
    Engineering Requirement는 FAIL하는 상태를 찾는다.
    """

    A = Real("escape_A")
    B = Real("escape_B")

    solver = Solver()

    add_feasible_domain(solver, A, B)
    add_verification_plan(solver, A, B)

    # Engineering Requirement
    # A + B <= 30.05
    #
    # Requirement 위반:
    # A + B > 30.05

    solver.add(A + B > RealVal("30.05"))

    if solver.check() == sat:
        model = solver.model()

        a_value = to_float(model[A])
        b_value = to_float(model[B])
        total = a_value + b_value

        print("ESCAPE FOUND")
        print("-----------------------------")
        print(f"A = {a_value:.3f}")
        print(f"B = {b_value:.3f}")
        print(f"A + B = {total:.3f}")
        print()
        print("Feasible Domain   -> PASS")
        print("Verification Plan -> PASS")
        print("Requirement       -> FAIL")

        return True

    print("NO ESCAPE FOUND")
    return False


# ---------------------------------------------------------
# TEST 2
# Worst Undetected Violation
# ---------------------------------------------------------

def find_worst_undetected_violation():
    """
    Verification Plan을 통과할 수 있는 상태 중에서
    Engineering Requirement를 가장 심하게 위반하는 상태를 찾는다.
    """

    A = Real("worst_A")
    B = Real("worst_B")

    optimizer = Optimize()

    add_feasible_domain(optimizer, A, B)
    add_verification_plan(optimizer, A, B)

    requirement_limit = RealVal("30.05")

    # Requirement 위반 상태만 고려
    optimizer.add(A + B > requirement_limit)

    # 위반 크기
    violation = A + B - requirement_limit

    # 최대 위반 상태 탐색
    optimizer.maximize(violation)

    if optimizer.check() == sat:
        model = optimizer.model()

        a_value = to_float(model[A])
        b_value = to_float(model[B])

        total = a_value + b_value
        violation_value = total - 30.05

        print("WORST UNDETECTED VIOLATION")
        print("-----------------------------")
        print(f"A = {a_value:.3f}")
        print(f"B = {b_value:.3f}")
        print()
        print(f"A + B              = {total:.3f}")
        print("Requirement Limit  = 30.050")
        print(f"Violation          = {violation_value:.3f}")
        print()
        print("Feasible Domain   -> PASS")
        print("Verification Plan -> PASS")
        print("Requirement       -> FAIL")

        return violation_value

    print("NO UNDETECTED VIOLATION FOUND")
    return None


# ---------------------------------------------------------
# TEST 3
# Feasible Domain Boundary
# ---------------------------------------------------------

def test_feasible_domain_boundary():
    """
    Feasible Domain이 Verification Plan보다 좁을 때,
    Solver가 현실적으로 허용된 범위를 넘어가지 않는지 확인한다.
    """

    A = Real("boundary_A")
    B = Real("boundary_B")

    optimizer = Optimize()

    # ------------------------------------------
    # 좁은 Feasible Domain
    # ------------------------------------------

    optimizer.add(A >= RealVal("9.5"))
    optimizer.add(A <= RealVal("10.04"))

    optimizer.add(B >= RealVal("19.5"))
    optimizer.add(B <= RealVal("20.04"))

    # ------------------------------------------
    # Verification Plan
    # ------------------------------------------

    optimizer.add(A >= RealVal("9.9"))
    optimizer.add(A <= RealVal("10.1"))

    optimizer.add(B >= RealVal("19.9"))
    optimizer.add(B <= RealVal("20.1"))

    # ------------------------------------------
    # Engineering Requirement
    # ------------------------------------------

    requirement_limit = RealVal("30.05")

    optimizer.add(A + B > requirement_limit)

    violation = A + B - requirement_limit

    optimizer.maximize(violation)

    if optimizer.check() == sat:
        model = optimizer.model()

        a_value = to_float(model[A])
        b_value = to_float(model[B])

        total = a_value + b_value
        violation_value = total - 30.05

        print("FEASIBLE DOMAIN BOUNDARY TEST")
        print("-----------------------------")
        print(f"A = {a_value:.3f}")
        print(f"B = {b_value:.3f}")
        print()
        print(f"A + B              = {total:.3f}")
        print("Requirement Limit  = 30.050")
        print(f"Violation          = {violation_value:.3f}")
        print()
        print("Expected maximum:")
        print("A <= 10.040")
        print("B <= 20.040")

        return violation_value

    print("NO ESCAPE FOUND INSIDE FEASIBLE DOMAIN")
    return None


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

if __name__ == "__main__":

    print()
    print("========================================")
    print(" ENGINEERING VERIFICATION STRESS TEST")
    print("========================================")
    print()

    # TEST 1
    print("TEST 1")
    print("Escape Existence")
    print()
    find_escape()

    print()
    print()

    # TEST 2
    print("TEST 2")
    print("Worst Undetected Violation")
    print()
    find_worst_undetected_violation()

    print()
    print()

    # TEST 3
    print("TEST 3")
    print("Feasible Domain Boundary")
    print()
    test_feasible_domain_boundary()

    print()