from decimal import Decimal

from z3 import Real, RealVal, Optimize, sat


# ---------------------------------------------------------
# Engineering Model
# ---------------------------------------------------------

MODEL = {
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
# Helper
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# Base Model
# ---------------------------------------------------------

def add_feasible_domain(solver, A, B):
    """
    현실적으로 가능한 Engineering State.
    """

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
    """
    현재 Verification Plan.
    """

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
    현재 Prototype에서는 Requirement가 관계조건이고,
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
# Automatic Patch Candidate Generator
# ---------------------------------------------------------

def generate_patch_candidates(gap):
    """
    Relationship Gap을 기반으로
    Verification Patch 후보를 자동 생성한다.

    현재 규칙:

    Candidate 1
    → Requirement 관계조건 자체를 Verification에 추가

    Candidate 2
    → B가 현재 Verification 최대값에 있을 때도
      Requirement를 만족하도록 A upper limit 계산

    Candidate 3
    → A가 현재 Verification 최대값에 있을 때도
      Requirement를 만족하도록 B upper limit 계산
    """

    requirement = gap["requirement"]

    if gap["gap_type"] != "relationship_gap":
        return []

    limit = requirement["limit"]

    current_A_max = (
        MODEL["verification"]["A"]["max"]
    )

    current_B_max = (
        MODEL["verification"]["B"]["max"]
    )

    # -----------------------------------------------------
    # Candidate 1
    # 관계조건 직접 추가
    # -----------------------------------------------------

    relation_patch = {
        "name": "PATCH 1",
        "type": "add_relation",
        "description": (
            f"Add A + B <= {limit}"
        ),
        "limit": limit,
    }

    # -----------------------------------------------------
    # Candidate 2
    #
    # A + B <= limit
    #
    # B가 현재 최대값일 때:
    #
    # A <= limit - B_max
    # -----------------------------------------------------

    generated_A_max = (
        limit - current_B_max
    )

    tighten_A_patch = {
        "name": "PATCH 2",
        "type": "tighten_A",
        "description": (
            f"Tighten A upper limit "
            f"to {generated_A_max}"
        ),
        "new_max": generated_A_max,
    }

    # -----------------------------------------------------
    # Candidate 3
    #
    # A가 현재 최대값일 때:
    #
    # B <= limit - A_max
    # -----------------------------------------------------

    generated_B_max = (
        limit - current_A_max
    )

    tighten_B_patch = {
        "name": "PATCH 3",
        "type": "tighten_B",
        "description": (
            f"Tighten B upper limit "
            f"to {generated_B_max}"
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
    """
    자동 생성된 Patch를 Solver에 적용한다.
    """

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
# Stress Test
# ---------------------------------------------------------

def evaluate_plan(patch=None):
    """
    현재 Verification Plan 또는 Patch 적용 Plan에서

    Verification PASS
    AND
    Requirement FAIL

    상태가 존재하는지 확인한다.

    존재하면 Worst Undetected Violation도 계산한다.
    """

    patch_id = (
        patch["type"]
        if patch is not None
        else "current"
    )

    A = Real(f"{patch_id}_A")
    B = Real(f"{patch_id}_B")

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

    if patch is not None:

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

    # Worst Undetected Violation
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

        violation_value = (
            total
            - float(requirement_limit)
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
# Result
# ---------------------------------------------------------

def run_patch_generator():

    print()
    print("========================================")
    print(" AUTOMATIC PATCH CANDIDATE GENERATOR")
    print("========================================")
    print()

    # -----------------------------------------------------
    # Current Plan
    # -----------------------------------------------------

    print("CURRENT VERIFICATION PLAN")
    print("----------------------------------------")

    print(
        "A:",
        MODEL["verification"]["A"]["min"],
        "~",
        MODEL["verification"]["A"]["max"],
    )

    print(
        "B:",
        MODEL["verification"]["B"]["min"],
        "~",
        MODEL["verification"]["B"]["max"],
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
    # Current Stress Test
    # -----------------------------------------------------

    print()
    print()

    current_result = evaluate_plan()

    print("CURRENT STRESS TEST")
    print("----------------------------------------")

    if current_result["escape_found"]:

        print("Verification Sufficiency -> FAILED")

        print()

        print(
            f"Worst Violation = "
            f"{current_result['violation']:.3f}"
        )

        print()

        print("Worst Escape State")

        print(
            f"A = {current_result['A']:.3f}"
        )

        print(
            f"B = {current_result['B']:.3f}"
        )

    else:

        print("No modeled escape found.")

    # -----------------------------------------------------
    # Gap Detection
    # -----------------------------------------------------

    print()
    print()

    gap = detect_gap()

    print("GAP ANALYSIS")
    print("----------------------------------------")

    print(
        "Gap Type:",
        gap["gap_type"]
    )

    print(
        "Violated Requirement:",
        f"A + B <= {requirement_limit}"
    )

    # -----------------------------------------------------
    # Automatic Candidate Generation
    # -----------------------------------------------------

    candidates = generate_patch_candidates(
        gap
    )

    print()
    print()

    print("GENERATED PATCH CANDIDATES")
    print("----------------------------------------")

    for patch in candidates:

        print(
            patch["name"],
            "->",
            patch["description"]
        )

    # -----------------------------------------------------
    # Candidate Evaluation
    # -----------------------------------------------------

    print()
    print()

    print("PATCH STRESS TEST")
    print("----------------------------------------")

    results = []

    for patch in candidates:

        result = evaluate_plan(
            patch
        )

        results.append(
            {
                "patch": patch,
                "result": result,
            }
        )

        print()
        print(patch["name"])
        print(patch["description"])

        if result["escape_found"]:

            print(
                "Escape Found      : YES"
            )

            print(
                "Worst Violation   : "
                f"{result['violation']:.3f}"
            )

        else:

            print(
                "Escape Found      : NO"
            )

            print(
                "Worst Violation   : 0.000"
            )

    # -----------------------------------------------------
    # Summary
    # -----------------------------------------------------

    print()
    print()

    print("PATCH GENERATION RESULT")
    print("----------------------------------------")

    closed_gap = [
        item
        for item in results
        if not item["result"]["escape_found"]
    ]

    print(
        "Generated Candidates:",
        len(candidates)
    )

    print(
        "Candidates Closing Modeled Gap:",
        len(closed_gap)
    )

    print()

    if closed_gap:

        print(
            "Automatic candidate generation "
            "successfully produced"
        )

        print(
            "one or more patches that eliminate "
            "the modeled escape."
        )

    else:

        print(
            "No generated candidate eliminated "
            "the modeled escape."
        )

    print()


if __name__ == "__main__":
    run_patch_generator()