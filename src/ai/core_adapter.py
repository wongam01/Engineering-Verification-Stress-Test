from copy import deepcopy
from dataclasses import dataclass
from decimal import Decimal

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
# DETERMINISTIC AI EXTRACTION GUARD
# =========================================================

def validate_ai_extraction_structure(
    extraction: dict,
) -> tuple[bool, str]:

    """
    LLM이 needs_review=False라고 반환하더라도
    Constraint Type에 필요한 핵심 Field가
    실제로 존재하는지 결정론적으로 확인한다.

    여기서는 AI 출력 자체의 구조만 검사한다.

    존재하지 않는 Engineering Variable,
    Unit 관계, Feasible Domain 등은
    Core Validator의 책임이다.
    """

    constraint_type = extraction.get(
        "type"
    )

    # -----------------------------------------------------
    # RANGE
    # -----------------------------------------------------

    if constraint_type == "range":

        required = {
            "variable": extraction.get("variable"),
            "min": extraction.get("min"),
            "max": extraction.get("max"),
        }

    # -----------------------------------------------------
    # DIFFERENCE MIN
    # -----------------------------------------------------

    elif constraint_type == "lower_bound":

        required = {

            "variable": extraction.get("variable"),

            "min": extraction.get("min"),

        }

    elif constraint_type == "upper_bound":

        required = {

            "variable": extraction.get("variable"),

            "max": extraction.get("max"),

        }

    elif constraint_type == "difference_min":

        required = {
            "left": extraction.get("left"),
            "right": extraction.get("right"),
            "min": extraction.get("min"),
        }

    # -----------------------------------------------------
    # SUM UPPER
    # -----------------------------------------------------

    elif constraint_type == "sum_upper":

        variables = extraction.get(
            "variables"
        )

        if not variables:

            return (
                False,
                "sum_upper Constraint에 "
                "variables가 없습니다.",
            )

        required = {
            "limit": extraction.get("limit"),
        }

    # -----------------------------------------------------
    # ABS DIFFERENCE MAX
    # -----------------------------------------------------

    elif constraint_type == "abs_difference_max":

        required = {
            "left": extraction.get("left"),
            "right": extraction.get("right"),
            "limit": extraction.get("limit"),
        }

    else:

        return (
            True,
            "",
        )


    # -----------------------------------------------------
    # REQUIRED FIELD CHECK
    # -----------------------------------------------------

    for field_name, value in required.items():

        if value is None:

            return (
                False,
                (
                    f"{constraint_type} Constraint에 "
                    f"{field_name} 값이 없습니다."
                ),
            )


    # -----------------------------------------------------
    # NUMERIC FORMAT CHECK
    # -----------------------------------------------------

    numeric_fields = [
        "min",
        "max",
        "limit",
    ]

    for field_name in numeric_fields:

        value = extraction.get(
            field_name
        )

        if value is None:

            continue

        try:

            Decimal(
                str(value)
            )

        except Exception:

            return (
                False,
                (
                    f"{constraint_type} Constraint의 "
                    f"{field_name} 값이 숫자가 아닙니다: "
                    f"{value}"
                ),
            )


    # -----------------------------------------------------
    # ABS DIFFERENCE LIMIT
    # -----------------------------------------------------

    if (
        constraint_type
        == "abs_difference_max"
    ):

        limit = Decimal(
            str(
                extraction["limit"]
            )
        )

        if limit < 0:

            return (
                False,
                (
                    "abs_difference_max Constraint의 "
                    "limit은 음수일 수 없습니다."
                ),
            )


    return (
        True,
        "",
    )


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
    # DETERMINISTIC STRUCTURE GUARD
    # -----------------------------------------------------

    structure_valid, structure_message = (
        validate_ai_extraction_structure(
            extraction
        )
    )

    if not structure_valid:

        return AIConstraintAdapterResult(
            accepted=False,
            constraint_role=role,
            constraint=None,
            source_name=source_name,
            source_text=source_text,
            message=(
                "AI Constraint 구조 검증 실패: "
                + structure_message
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

    elif constraint_type == "lower_bound":

        core_data.update(

            {

                "variable": extraction[
                    "variable"
                ],

                "min": extraction[
                    "min"
                ],

            }

        )

    elif constraint_type == "upper_bound":

        core_data.update(

            {

                "variable": extraction[
                    "variable"
                ],

                "max": extraction[
                    "max"
                ],

            }

        )

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

    # =====================================================
    # ABSOLUTE DIFFERENCE MAX
    #
    # |left - right| <= limit
    # =====================================================

    elif (
        constraint_type
        == "abs_difference_max"
    ):

        core_data.update(
            {
                "left": extraction[
                    "left"
                ],

                "right": extraction[
                    "right"
                ],

                "limit": extraction[
                    "limit"
                ],
            }
        )


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