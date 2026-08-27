from decimal import Decimal

from z3 import Real, RealVal, Solver, Optimize, sat


# ---------------------------------------------------------
# Engineering Model
# ---------------------------------------------------------

MODEL = {
    "nominal": {
        "A": Decimal("10.00"),
        "B": Decimal("20.00"),
    },

    "feasible": {
        "A": {
            "min": Decimal("9.50"),
            "max": Decimal("10.50"),
        },
        "B": {
            "min": Decimal("19.50"),
            "max": Decimal("20.50"),
        },
    },

    "verification": {
        "A": {
            "min": Decimal("9.90"),
            "max": Decimal("10.10"),
        },
        "B": {
            "min": Decimal("19.90"),
            "max": Decimal("20.10"),
        },
    },

    "requirement": {
        "type": "sum_upper",
        "variables": ["A", "B"],
        "limit": Decimal("30.05"),
    },
}


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def z3_value(value):
    """Decimal 값을 정확한 Z3 RealVal로 변환한다."""
    return RealVal(str(value))


def to_float(value):
    """Z3 rational 값을 Python float로 변환한다."""
    return (
        value.numerator_as_long()
        / value.denominator_as_long()
    )


# ---------------------------------------------------------
# Base Engineering Constraints
# ---------------------------------------------------------

def add_feasible_domain(solver, A, B):
    """현실적으로 가능한 Engineering State 범위."""

    solver.add(
        A >= z3_value(MODEL["feasible"]["A"]["min"])
    )
    solver.add(
        A <= z3_value(MODEL["feasible"]["A"]["max"])
    )

    solver.add(
        B >= z3_value(MODEL["feasible"]["B"]["min"])
    )
    solver.add(
        B <= z3_value(MODEL["feasible"]["B"]["max"])
    )


def add_verification_plan(solver, A, B):
    """현재 Verification Plan."""

    solver.add(
        A >= z3_value(MODEL["verification"]["A"]["min"])
    )
    solver.add(
        A <= z3_value(MODEL["verification"]["A"]["max"])
    )

    solver.add(
        B >= z3_value(MODEL["verification"]["B"]["min"])
    )
    solver.add(
        B <= z3_value(MODEL["verification"]["B"]["max"])
    )


# ---------------------------------------------------------
# Gap Detection
# ---------------------------------------------------------

def detect_gap():
    """
    현재 Prototype의 Requirement는
    A + B <= 30.05 관계조건이다.

    Verification Plan에는 해당 관계조건이 없으므로
    Relationship Gap으로 분류한다.
    """

    requirement = MODEL["requirement"]

    if requirement["type"] == "sum_upper":
        return {
            "gap_type": "relationship_gap",
            "requirement": requirement,
        }

    return {
        "gap_type": "unknown",
        "requirement": requirement,
    }


# ---------------------------------------------------------
# Automatic Patch Candidate Generation
# ---------------------------------------------------------

def generate_patch_candidates(gap):
    """
    Relationship Gap을 기반으로
    Patch 후보를 자동 생성한다.
    """

    if gap["gap_type"] != "relationship_gap":
        return []

    limit = gap["requirement"]["limit"]

    current_A_max = (
        MODEL["verification"]["A"]["max"]
    )

    current_B_max = (
        MODEL["verification"]["B"]["max"]
    )

    # PATCH 1
    # 관계조건 자체를 Verification에 추가
    relation_patch = {
        "name": "PATCH 1",
        "type": "add_relation",
        "description": f"Add A + B <= {limit}",
        "limit": limit,
    }

    # PATCH 2
    # B가 현재 최대값이어도 Requirement를 만족하도록
    # A의 상한을 계산
    generated_A_max = (
        limit - current_B_max
    )

    tighten_A_patch = {
        "name": "PATCH 2",
        "type": "tighten_A",
        "description": (
            f"Tighten A upper limit to "
            f"{generated_A_max}"
        ),
        "new_max": generated_A_max,
    }

    # PATCH 3
    # A가 현재 최대값이어도 Requirement를 만족하도록
    # B의 상한을 계산
    generated_B_max = (
        limit - current_A_max
    )

    tighten_B_patch = {
        "name": "PATCH 3",
        "type": "tighten_B",
        "description": (
            f"Tighten B upper limit to "
            f"{generated_B_max}"
        ),
        "new_max": generated_B_max,
    }

    return [
        relation_patch,
        tighten_A_patch,
        tighten_B_patch,
    ]


# ---------------------------------------------------------
# Apply Patch
# ---------------------------------------------------------

def apply_patch(solver, A, B, patch):
    """선택된 Patch를 Verification Plan에 적용한다."""

    patch_type = patch["type"]

    if patch_type == "add_relation":

        solver.add(
            A + B <= z3_value(patch["limit"])
        )

    elif patch_type == "tighten_A":

        solver.add(
            A <= z3_value(patch["new_max"])
        )

    elif patch_type == "tighten_B":

        solver.add(
            B <= z3_value(patch["new_max"])
        )

    else:

        raise ValueError(
            f"Unknown patch type: {patch_type}"
        )


# ---------------------------------------------------------
# Test A
# Does the Patch Close the Escape?
# ---------------------------------------------------------

def test_escape_closure(patch):
    """
    Patch 적용 후에도

    Verification PASS
    AND
    Requirement FAIL

    상태가 존재하는지 확인한다.

    존재하면 Patch가 Gap을 닫지 못한 것이다.
    """

    patch_id = patch["type"]

    A = Real(f"{patch_id}_escape_A")
    B = Real(f"{patch_id}_escape_B")

    optimizer = Optimize()

    add_feasible_domain(
        optimizer,
        A,
        B,
    )

    add_verification_plan(
        optimizer,
        A,
        B,
    )

    apply_patch(
        optimizer,
        A,
        B,
        patch,
    )

    requirement_limit = (
        MODEL["requirement"]["limit"]
    )

    # Requirement 위반 상태
    optimizer.add(
        A + B > z3_value(requirement_limit)
    )

    violation = (
        A
        + B
        - z3_value(requirement_limit)
    )

    optimizer.maximize(violation)

    if optimizer.check() == sat:

        model = optimizer.model()

        a_value = to_float(model[A])
        b_value = to_float(model[B])

        total = a_value + b_value

        return {
            "closes_escape": False,
            "escape_found": True,
            "A": a_value,
            "B": b_value,
            "violation": (
                total
                - float(requirement_limit)
            ),
        }

    return {
        "closes_escape": True,
        "escape_found": False,
        "violation": 0.0,
    }


# ---------------------------------------------------------
# Test B
# Does the Patch Preserve the Nominal State?
# ---------------------------------------------------------

def test_nominal_preservation(patch):
    """
    정상 설계 상태가 Patch 적용 후에도
    Verification Plan을 통과할 수 있는지 확인한다.

    Nominal:
    A = 10.00
    B = 20.00
    """

    A = Real(
        f"{patch['type']}_nominal_A"
    )

    B = Real(
        f"{patch['type']}_nominal_B"
    )

    solver = Solver()

    # 기존 Verification Plan
    add_verification_plan(
        solver,
        A,
        B,
    )

    # Patch 적용
    apply_patch(
        solver,
        A,
        B,
        patch,
    )

    # Nominal State 고정
    solver.add(
        A == z3_value(
            MODEL["nominal"]["A"]
        )
    )

    solver.add(
        B == z3_value(
            MODEL["nominal"]["B"]
        )
    )

    if solver.check() == sat:

        return {
            "preserves_nominal": True
        }

    return {
        "preserves_nominal": False
    }


# ---------------------------------------------------------
# Full Engineering Patch Evaluation
# ---------------------------------------------------------

def evaluate_patch(patch):
    """
    하나의 Patch에 대해 두 가지를 동시에 검사한다.

    1. Escape를 제거하는가?
    2. Nominal State를 보존하는가?
    """

    escape_result = (
        test_escape_closure(patch)
    )

    nominal_result = (
        test_nominal_preservation(patch)
    )

    closes_escape = (
        escape_result["closes_escape"]
    )

    preserves_nominal = (
        nominal_result["preserves_nominal"]
    )

    # Engineering Validity
    #
    # Escape 제거
    # AND
    # Nominal 보존

    valid_patch = (
        closes_escape
        and preserves_nominal
    )

    return {
        "patch": patch,
        "closes_escape": closes_escape,
        "preserves_nominal": preserves_nominal,
        "valid_patch": valid_patch,
        "violation": escape_result["violation"],
    }


# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def run_practicality_filter():

    print()
    print("========================================")
    print(" ENGINEERING PATCH PRACTICALITY TEST")
    print("========================================")
    print()

    print("NOMINAL STATE")
    print("----------------------------------------")

    print(
        "A =",
        MODEL["nominal"]["A"]
    )

    print(
        "B =",
        MODEL["nominal"]["B"]
    )

    print()

    print("ENGINEERING REQUIREMENT")
    print("----------------------------------------")

    requirement_limit = (
        MODEL["requirement"]["limit"]
    )

    print(
        f"A + B <= {requirement_limit}"
    )

    # -----------------------------------------------------
    # Gap Detection
    # -----------------------------------------------------

    gap = detect_gap()

    candidates = (
        generate_patch_candidates(gap)
    )

    # -----------------------------------------------------
    # Patch Evaluation
    # -----------------------------------------------------

    print()
    print()

    print("PATCH EVALUATION")
    print("========================================")

    results = []

    for patch in candidates:

        result = evaluate_patch(patch)

        results.append(result)

        print()
        print(patch["name"])
        print("----------------------------------------")

        print(
            patch["description"]
        )

        print()

        print(
            "Closes Escape       :",
            "YES"
            if result["closes_escape"]
            else "NO"
        )

        print(
            "Preserves Nominal   :",
            "YES"
            if result["preserves_nominal"]
            else "NO"
        )

        print()

        if result["valid_patch"]:

            print(
                "Engineering Status  : VALID"
            )

        else:

            print(
                "Engineering Status  : REJECTED"
            )

            if not result["closes_escape"]:

                print(
                    "Reason              : "
                    "Escape still exists"
                )

            elif not result["preserves_nominal"]:

                print(
                    "Reason              : "
                    "Rejects intended nominal state"
                )

    # -----------------------------------------------------
    # Valid Patch Selection
    # -----------------------------------------------------

    print()
    print()

    print("VALID PATCHES")
    print("----------------------------------------")

    valid_patches = [
        result
        for result in results
        if result["valid_patch"]
    ]

    if valid_patches:

        for result in valid_patches:

            patch = result["patch"]

            print(
                patch["name"],
                "->",
                patch["description"]
            )

    else:

        print(
            "No generated patch passed "
            "the Engineering Practicality Filter."
        )

    # -----------------------------------------------------
    # Recommended Patch
    # -----------------------------------------------------

    print()
    print()

    print("RECOMMENDED PATCH")
    print("----------------------------------------")

    if valid_patches:

        recommended = (
            valid_patches[0]["patch"]
        )

        print(
            recommended["name"]
        )

        print(
            recommended["description"]
        )

        print()

        print(
            "Reason:"
        )

        print(
            "This patch closes the modeled Escape"
        )

        print(
            "while preserving the intended "
            "Nominal State."
        )

    else:

        print(
            "No acceptable patch found."
        )

        print(
            "Engineer review required."
        )

    print()


if __name__ == "__main__":
    run_practicality_filter()