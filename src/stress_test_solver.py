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
# Test 1
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

    # Engineering Requirement:
    #
    # A + B <= 30.05
    #
    # 따라서 Requirement 위반 상태는:
    #
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
# Test 2
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

    # 실제 Requirement 위반 상태만 고려한다.
    optimizer.add(A + B > requirement_limit)

    # 위반 크기:
    #
    # (실제 값) - (Requirement Limit)
    #
    # 이 값을 최대화한다.
    violation = A + B - requirement_limit

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
# Main
# ---------------------------------------------------------

if __name__ == "__main__":

    print()
    print("========================================")
    print(" ENGINEERING VERIFICATION STRESS TEST")
    print("========================================")
    print()

    print("TEST 1")
    print("Escape Existence")
    print()
    find_escape()

    print()
    print()

    print("TEST 2")
    print("Worst Undetected Violation")
    print()
    find_worst_undetected_violation()

    print()