from copy import deepcopy
from dataclasses import dataclass

from src.core.models import (
    EngineeringCase,
    RequirementSpec,
)


# =========================================================
# AI → CORE 변환 결과
# =========================================================

@dataclass
class AIConstraintAdapterResult:
    """
    AI가 추출한 Constraint를
    Core에서 사용할 수 있는지 판단한 결과.
    """

    accepted: bool

    constraint_role: str

    constraint: RequirementSpec | None

    source_name: str
    source_text: str

    message: str


# =========================================================
# AI EXTRACTION → CORE CONSTRAINT
# =========================================================

def convert_ai_constraint(
    extraction: dict,
) -> AIConstraintAdapterResult:
    """
    AI 추출 결과를 Core의 RequirementSpec으로 변환한다.

    다음 경우에는 자동 변환하지 않는다.

    1. AI가 needs_review=True라고 판단한 경우
    2. unsupported Constraint
    3. requirement / verification 역할이 잘못된 경우
    """

    role = extraction.get(
        "constraint_role"
    )

    source_name = extraction.get(
        "source_name",
        "unknown_source",
    )

    source_text = extraction.get(
        "source_text",
        "",
    )

    # -----------------------------------------------------
    # ROLE CHECK
    # -----------------------------------------------------

    if role not in {
        "requirement",
        "verification",
    }:

        return AIConstraintAdapterResult(
            accepted=False,
            constraint_role=str(role),
            constraint=None,
            source_name=source_name,
            source_text=source_text,
            message=(
                "Requirement 또는 Verification "
                "역할을 확인할 수 없습니다."
            ),
        )

    # -----------------------------------------------------
    # HUMAN REVIEW REQUIRED
    # -----------------------------------------------------

    if extraction.get(
        "needs_review",
        True,
    ):

        reason = extraction.get(
            "review_reason"
        )

        return AIConstraintAdapterResult(
            accepted=False,
            constraint_role=role,
            constraint=None,
            source_name=source_name,
            source_text=source_text,
            message=(
                "AI가 사람의 검토가 필요하다고 판단했습니다."
                + (
                    f" 이유: {reason}"
                    if reason
                    else ""
                )
            ),
        )

    # -----------------------------------------------------
    # UNSUPPORTED
    # -----------------------------------------------------

    constraint_type = extraction.get(
        "type"
    )

    if constraint_type == "unsupported":

        return AIConstraintAdapterResult(
            accepted=False,
            constraint_role=role,
            constraint=None,
            source_name=source_name,
            source_text=source_text,
            message=(
                "현재 Core에서 지원하지 않는 "
                "Constraint입니다."
            ),
        )

    # -----------------------------------------------------
    # CORE DATA
    # -----------------------------------------------------

    core_data = {
        "id": extraction[
            "constraint_id"
        ],

        "type": constraint_type,

        "unit": extraction[
            "unit"
        ],

        "description": source_text,
    }

    # =====================================================
    # RANGE
    # =====================================================

    if constraint_type == "range":

        core_data.update(
            {
                "variable": extraction[
                    "variable"
                ],

                "min": extraction[
                    "min"
                ],

                "max": extraction[
                    "max"
                ],
            }
        )

    # =====================================================
    # DIFFERENCE MIN
    # =====================================================

    elif (
        constraint_type
        == "difference_min"
    ):

        core_data.update(
            {
                "left": extraction[
                    "left"
                ],

                "right": extraction[
                    "right"
                ],

                "min": extraction[
                    "min"
                ],
            }
        )

    # =====================================================
    # SUM UPPER
    # =====================================================

    elif constraint_type == "sum_upper":

        core_data.update(
            {
                "variables": extraction[
                    "variables"
                ],

                "limit": extraction[
                    "limit"
                ],
            }
        )

    else:

        return AIConstraintAdapterResult(
            accepted=False,
            constraint_role=role,
            constraint=None,
            source_name=source_name,
            source_text=source_text,
            message=(
                "알 수 없는 Constraint Type입니다: "
                f"{constraint_type}"
            ),
        )

    # -----------------------------------------------------
    # CORE MODEL 생성
    # -----------------------------------------------------

    constraint = (
        RequirementSpec.from_dict(
            core_data
        )
    )

    return AIConstraintAdapterResult(
        accepted=True,
        constraint_role=role,
        constraint=constraint,
        source_name=source_name,
        source_text=source_text,
        message=(
            "AI Constraint가 Core 형식으로 "
            "변환되었습니다."
        ),
    )


# =========================================================
# 승인된 AI CONSTRAINT 적용
# =========================================================

def apply_approved_ai_constraint(
    case: EngineeringCase,
    adapter_result: AIConstraintAdapterResult,
    approved: bool,
) -> EngineeringCase:
    """
    사람이 승인한 AI Constraint만
    EngineeringCase에 적용한다.

    AI가 자동으로 Solver 입력을 확정하지 않도록
    approved=True가 반드시 필요하다.
    """

    if not approved:

        raise ValueError(
            "Engineer approval이 필요합니다."
        )

    if not adapter_result.accepted:

        raise ValueError(
            "Core에 적용할 수 없는 AI Constraint입니다."
        )

    if adapter_result.constraint is None:

        raise ValueError(
            "변환된 Constraint가 없습니다."
        )

    updated_case = deepcopy(
        case
    )

    # -----------------------------------------------------
    # REQUIREMENT
    # -----------------------------------------------------

    if (
        adapter_result.constraint_role
        == "requirement"
    ):

        updated_case.requirements.append(
            adapter_result.constraint
        )

        return updated_case

    # -----------------------------------------------------
    # VERIFICATION
    # -----------------------------------------------------

    if (
        adapter_result.constraint_role
        == "verification"
    ):

        updated_case.verification_constraints.append(
            adapter_result.constraint
        )

        return updated_case

    raise ValueError(
        "알 수 없는 Constraint Role입니다."
    )