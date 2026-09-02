from copy import deepcopy
from dataclasses import dataclass, field, replace
from decimal import Decimal

from src.core.models import (
    EngineeringCase,
    RequirementSpec,
)

from src.core.validator import (
    validate_case,
)

from src.core.stress_tester import (
    stress_test_case,
)


# =========================================================
# PATCH CANDIDATE
# =========================================================

@dataclass
class PatchCandidate:
    """
    검사계획 수정 후보.

    kind:

    1. add_constraint
       검사계획에 관계조건 추가

    2. change_range
       기존 변수의 검사범위 수정
    """

    patch_id: str

    target_requirement_id: str

    kind: str

    description: str

    # 관계조건 추가용
    constraint: RequirementSpec | None = None

    # 검사 Range 수정용
    variable: str | None = None

    new_verification_min: Decimal | None = None
    new_verification_max: Decimal | None = None


# =========================================================
# PATCH EVALUATION RESULT
# =========================================================

@dataclass
class PatchEvaluation:
    """
    하나의 Patch를 적용하고 다시 공격한 결과.
    """

    candidate: PatchCandidate

    valid_input: bool

    closes_escape: bool

    preserves_nominal: bool

    practical: bool

    remaining_worst_violation: float = 0.0

    validation_issues: list[str] = field(
        default_factory=list
    )

    patched_case: EngineeringCase | None = None

    @property
    def model_closure_candidate(
        self,
    ) -> bool:
        """
        현재 수학적 모델 안에서:

        1. Patch 입력이 유효하고
        2. Verification Escape를 닫으며
        3. Nominal State를 보존하는지 나타낸다.

        제조 가능성, 비용, 공정능력,
        검사시간의 적합성을 의미하지 않는다.
        """

        return (
            self.valid_input
            and
            self.closes_escape
            and
            self.preserves_nominal
        )

    @property
    def engineering_review_required(
        self,
    ) -> bool:
        """
        Model Closure Candidate는
        실제 적용 전에 Engineering Review가 필요하다.
        """

        return (
            self.model_closure_candidate
        )


# =========================================================
# CONSTRAINT VALUE CHECK
# =========================================================

def constraint_passes_state(
    constraint: RequirementSpec,
    state: dict[str, Decimal],
) -> bool:
    """
    특정 Engineering State가
    하나의 Constraint를 만족하는지 계산한다.

    Solver가 아니라 Nominal 상태 확인용이다.
    """

    # -----------------------------------------------------
    # RANGE
    # -----------------------------------------------------

    if constraint.type == "range":

        value = state[
            constraint.variable
        ]

        return (
            constraint.min_value
            <= value
            <= constraint.max_value
        )

    # -----------------------------------------------------
    # DIFFERENCE MIN
    # -----------------------------------------------------

    # -----------------------------------------------------
    # LOWER BOUND
    # X >= MIN
    # -----------------------------------------------------

    if constraint.type == "lower_bound":

        value = state[
            constraint.variable
        ]

        return (
            value
            >= constraint.min_value
        )

    # -----------------------------------------------------
    # UPPER BOUND
    # X <= MAX
    # -----------------------------------------------------

    if constraint.type == "upper_bound":

        value = state[
            constraint.variable
        ]

        return (
            value
            <= constraint.max_value
        )

    if (
        constraint.type
        == "difference_min"
    ):

        value = (
            state[constraint.left]
            - state[constraint.right]
        )

        return (
            value
            >= constraint.min_value
        )

    # -----------------------------------------------------
    # SUM UPPER
    # -----------------------------------------------------

    # -----------------------------------------------------

    # ABSOLUTE DIFFERENCE MAX

    # |LEFT - RIGHT| <= LIMIT

    # -----------------------------------------------------

    if (
        constraint.type
        == "abs_difference_max"
    ):

        value = abs(

            state[constraint.left]

            - state[constraint.right]

        )

        return (

            value
            <= constraint.limit

        )


    if constraint.type == "sum_upper":

        total = sum(
            (
                state[name]
                for name
                in constraint.variables
            ),
            Decimal("0"),
        )

        return (
            total
            <= constraint.limit
        )

    raise ValueError(
        "Unsupported constraint type: "
        f"{constraint.type}"
    )


# =========================================================
# NOMINAL PRESERVATION
# =========================================================

def nominal_passes_verification(
    case: EngineeringCase,
) -> bool:
    """
    정상 설계 상태(Nominal State)가
    수정된 검사계획에서도 PASS하는지 확인한다.

    이 검사가 필요한 이유:

    수학적으로 Escape를 막더라도
    정상 설계 상태까지 Reject한다면
    실용적인 Patch라고 보기 어렵기 때문이다.
    """

    nominal_state = {
        name: variable.nominal
        for (
            name,
            variable,
        ) in case.variables.items()
    }

    # -----------------------------------------------------
    # BASIC VERIFICATION RANGES
    # -----------------------------------------------------

    for (
        name,
        variable,
    ) in case.variables.items():

        nominal = variable.nominal

        if not (
            variable.verification_min
            <= nominal
            <= variable.verification_max
        ):

            return False

    # -----------------------------------------------------
    # RELATIONAL VERIFICATION CONSTRAINTS
    # -----------------------------------------------------

    for constraint in (
        case.verification_constraints
    ):

        if not constraint_passes_state(
            constraint,
            nominal_state,
        ):

            return False

    return True


# =========================================================
# PATCH GENERATOR
# =========================================================

def generate_patch_candidates(
    case: EngineeringCase,
    requirement_id: str,
) -> list[PatchCandidate]:
    """
    Requirement Gap을 기반으로
    간단한 검사계획 수정 후보를 생성한다.

    현재 지원:

    - range
    - difference_min
    - sum_upper
    """

    requirement = (
        case.get_requirement(
            requirement_id
        )
    )

    candidates: list[
        PatchCandidate
    ] = []

    # =====================================================
    # CANDIDATE 1
    #
    # Requirement 자체를 Verification Plan에 추가
    # =====================================================

    relation_patch = replace(
        requirement,

        id=(
            f"V_PATCH_"
            f"{requirement.id}"
        ),

        description=(
            "Requirement relationship "
            "added to Verification Plan"
        ),
    )

    candidates.append(
        PatchCandidate(
            patch_id="P1",

            target_requirement_id=(
                requirement.id
            ),

            kind="add_constraint",

            description=(
                "설계 요구조건을 "
                "검사계획의 추가 조건으로 반영"
            ),

            constraint=relation_patch,
        )
    )

    # =====================================================
    # RANGE
    # =====================================================

    if requirement.type == "range":

        candidates.append(
            PatchCandidate(
                patch_id="P2",

                target_requirement_id=(
                    requirement.id
                ),

                kind="change_range",

                description=(
                    f"{requirement.variable}의 "
                    "검사 범위를 Requirement와 동일하게 조정"
                ),

                variable=(
                    requirement.variable
                ),

                new_verification_min=(
                    requirement.min_value
                ),

                new_verification_max=(
                    requirement.max_value
                ),
            )
        )

    # =====================================================
    # SUM UPPER
    #
    # X + Y <= LIMIT
    #
    # 변수 하나만 조정해서 Gap을 막으려면:
    #
    # X_max <= LIMIT - Y_max
    # =====================================================

    elif requirement.type == "sum_upper":

        patch_number = 2

        for target_variable in (
            requirement.variables
        ):

            other_max_sum = sum(
                (
                    case.variables[
                        other_variable
                    ].verification_max

                    for other_variable
                    in requirement.variables

                    if (
                        other_variable
                        != target_variable
                    )
                ),
                Decimal("0"),
            )

            new_max = (
                requirement.limit
                - other_max_sum
            )

            candidates.append(
                PatchCandidate(
                    patch_id=(
                        f"P{patch_number}"
                    ),

                    target_requirement_id=(
                        requirement.id
                    ),

                    kind="change_range",

                    description=(
                        f"{target_variable} "
                        f"검사 상한을 "
                        f"{new_max}로 조정"
                    ),

                    variable=(
                        target_variable
                    ),

                    new_verification_max=(
                        new_max
                    ),
                )
            )

            patch_number += 1

    # =====================================================
    # DIFFERENCE MIN
    #
    # LEFT - RIGHT >= LIMIT
    #
    # LEFT 최소값을 높이거나
    # RIGHT 최대값을 낮추는 후보 생성
    # =====================================================

    elif (
        requirement.type
        == "difference_min"
    ):

        left_variable = (
            case.variables[
                requirement.left
            ]
        )

        right_variable = (
            case.variables[
                requirement.right
            ]
        )

        new_left_min = (
            requirement.min_value
            + right_variable.verification_max
        )

        new_right_max = (
            left_variable.verification_min
            - requirement.min_value
        )

        candidates.append(
            PatchCandidate(
                patch_id="P2",

                target_requirement_id=(
                    requirement.id
                ),

                kind="change_range",

                description=(
                    f"{requirement.left} "
                    f"검사 하한을 "
                    f"{new_left_min}로 조정"
                ),

                variable=(
                    requirement.left
                ),

                new_verification_min=(
                    new_left_min
                ),
            )
        )

        candidates.append(
            PatchCandidate(
                patch_id="P3",

                target_requirement_id=(
                    requirement.id
                ),

                kind="change_range",

                description=(
                    f"{requirement.right} "
                    f"검사 상한을 "
                    f"{new_right_max}로 조정"
                ),

                variable=(
                    requirement.right
                ),

                new_verification_max=(
                    new_right_max
                ),
            )
        )

    return candidates


# =========================================================
# APPLY PATCH
# =========================================================

def apply_patch(
    case: EngineeringCase,
    candidate: PatchCandidate,
) -> EngineeringCase:
    """
    Patch Candidate를 EngineeringCase의
    실제 Verification Plan에 적용한다.

    원본 Case는 수정하지 않는다.
    """

    patched_case = deepcopy(
        case
    )

    # =====================================================
    # ADD RELATIONAL CONSTRAINT
    # =====================================================

    if (
        candidate.kind
        == "add_constraint"
    ):

        if candidate.constraint is None:

            raise ValueError(
                "Patch constraint is missing."
            )

        patched_case.verification_constraints.append(
            candidate.constraint
        )

        return patched_case

    # =====================================================
    # CHANGE VARIABLE VERIFICATION RANGE
    # =====================================================

    if (
        candidate.kind
        == "change_range"
    ):

        if candidate.variable is None:

            raise ValueError(
                "Patch variable is missing."
            )

        current = (
            patched_case.variables[
                candidate.variable
            ]
        )

        new_min = (
            candidate.new_verification_min
            if (
                candidate.new_verification_min
                is not None
            )
            else current.verification_min
        )

        new_max = (
            candidate.new_verification_max
            if (
                candidate.new_verification_max
                is not None
            )
            else current.verification_max
        )

        patched_case.variables[
            candidate.variable
        ] = replace(
            current,

            verification_min=new_min,
            verification_max=new_max,
        )

        return patched_case

    raise ValueError(
        "Unsupported patch kind: "
        f"{candidate.kind}"
    )


# =========================================================
# TARGET RESULT
# =========================================================

def find_stress_result(
    case: EngineeringCase,
    requirement_id: str,
):
    """
    특정 Requirement의 Stress Test 결과를 가져온다.
    """

    results = stress_test_case(
        case
    )

    for result in results:

        if (
            result.requirement_id
            == requirement_id
        ):

            return result

    raise KeyError(
        "Stress Test result not found: "
        f"{requirement_id}"
    )


# =========================================================
# EVALUATE ONE PATCH
# =========================================================

def evaluate_patch(
    case: EngineeringCase,
    candidate: PatchCandidate,
) -> PatchEvaluation:
    """
    Patch 하나에 대해 다음을 확인한다.

    1. 수정된 입력이 유효한가?
    2. Escape가 제거되는가?
    3. Nominal State를 보존하는가?
    """

    patched_case = apply_patch(
        case,
        candidate,
    )

    # -----------------------------------------------------
    # VALIDATION
    # -----------------------------------------------------

    validation = validate_case(
        patched_case
    )

    if not validation.valid:

        return PatchEvaluation(
            candidate=candidate,

            valid_input=False,

            closes_escape=False,

            preserves_nominal=False,

            practical=False,

            validation_issues=[
                (
                    f"{issue.location}: "
                    f"{issue.message}"
                )
                for issue
                in validation.issues
            ],

            patched_case=patched_case,
        )

    # -----------------------------------------------------
    # NOMINAL CHECK
    # -----------------------------------------------------

    preserves_nominal = (
        nominal_passes_verification(
            patched_case
        )
    )

    # -----------------------------------------------------
    # RE-ATTACK
    # -----------------------------------------------------

    result = find_stress_result(
        patched_case,
        candidate.target_requirement_id,
    )

    closes_escape = (
        not result.escape_found
    )

    remaining_worst_violation = (
        0.0
        if closes_escape
        else result.worst_violation
    )

    # -----------------------------------------------------
    # MODEL CLOSURE CANDIDATE
    #
    # legacy compatibility field:
    # practical
    #
    # 여기서 practical은 제조성/비용을 의미하지 않는다.
    # 모델 안에서 Escape를 닫고
    # Nominal State를 보존하는지만 확인한다.
    # -----------------------------------------------------

    practical = (
        closes_escape
        and
        preserves_nominal
    )

    return PatchEvaluation(
        candidate=candidate,

        valid_input=True,

        closes_escape=closes_escape,

        preserves_nominal=(
            preserves_nominal
        ),

        practical=practical,

        remaining_worst_violation=(
            remaining_worst_violation
        ),

        patched_case=patched_case,
    )


# =========================================================
# EVALUATE ALL PATCHES
# =========================================================

def evaluate_patch_candidates(
    case: EngineeringCase,
    requirement_id: str,
) -> list[PatchEvaluation]:
    """
    자동 생성한 모든 Patch Candidate를
    적용하고 다시 Stress Test한다.
    """

    candidates = (
        generate_patch_candidates(
            case,
            requirement_id,
        )
    )

    return [
        evaluate_patch(
            case,
            candidate,
        )
        for candidate
        in candidates
    ]


# =========================================================
# SELECT PRACTICAL PATCH
# =========================================================

def select_model_closure_candidate(
    evaluations: list[PatchEvaluation],
) -> PatchEvaluation | None:
    """
    현재 Prototype에서 첫 번째
    Model Closure Candidate를 선택한다.

    Model Closure Candidate 조건:

    1. Patch 입력이 유효함
    2. Modeled Escape 제거
    3. Nominal State 보존

    이 판정은 제조 가능성, 비용,
    공정능력, 검사시간 또는 적용 난이도를
    평가하지 않는다.

    실제 적용은 별도의
    Engineering Review가 필요하다.
    """

    for evaluation in evaluations:

        if evaluation.model_closure_candidate:

            return evaluation

    return None


# =========================================================
# LEGACY COMPATIBILITY
# =========================================================

def select_practical_patch(
    evaluations: list[PatchEvaluation],
) -> PatchEvaluation | None:
    """
    Backward-compatible wrapper.

    기존 practical이라는 이름은
    실제 제조성 또는 비용 적합성을
    의미하지 않는다.

    새 코드는
    select_model_closure_candidate()
    사용을 권장한다.
    """

    return select_model_closure_candidate(
        evaluations
    )

