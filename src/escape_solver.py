from z3 import Real, RealVal, Solver, sat


def to_float(value):
    """Z3의 정확한 유리수를 Python 숫자로 변환한다."""
    return value.numerator_as_long() / value.denominator_as_long()


def find_escape(verification_checks_relation=False):
    A = Real("A")
    B = Real("B")

    solver = Solver()

    # ------------------------------------------
    # Verification / Inspection Plan
    # ------------------------------------------
    solver.add(A >= RealVal("9.9"))
    solver.add(A <= RealVal("10.1"))

    solver.add(B >= RealVal("19.9"))
    solver.add(B <= RealVal("20.1"))

    # Case 2에서는 검사계획도 관계조건을 확인한다.
    if verification_checks_relation:
        solver.add(A + B <= RealVal("30.05"))

    # ------------------------------------------
    # Engineering Requirement를 위반하는
    # 상태가 존재하는지 탐색
    # ------------------------------------------
    solver.add(A + B > RealVal("30.05"))

    if solver.check() == sat:
        model = solver.model()

        a_value = to_float(model[A])
        b_value = to_float(model[B])
        total = a_value + b_value

        print("COUNTEREXAMPLE FOUND")
        print("--------------------")
        print(f"A = {a_value:.2f}")
        print(f"B = {b_value:.2f}")
        print()
        print("Verification:")
        print("A range -> PASS")
        print("B range -> PASS")

        if verification_checks_relation:
            print("A + B relation -> PASS")

        print()
        print(f"A + B = {total:.2f}")
        print("Requirement: A + B <= 30.05")
        print("Requirement -> FAIL")

    else:
        print("NO COUNTEREXAMPLE FOUND")
        print("-----------------------")
        print("현재 Verification Plan을 통과하면서")
        print("Requirement를 위반하는 상태를 찾을 수 없습니다.")


if __name__ == "__main__":
    print("===== CASE 1: 관계조건을 검사하지 않음 =====")
    find_escape(verification_checks_relation=False)

    print()
    print()

    print("===== CASE 2: 관계조건까지 검사함 =====")
    find_escape(verification_checks_relation=True)