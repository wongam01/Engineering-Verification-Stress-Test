import json
from typing import Literal

from pydantic import BaseModel

from src.ai.constraint_parser import client


# =========================================================
# AI MAPPING OUTPUT MODEL
# =========================================================

class RequirementMappingItem(
    BaseModel
):
    """
    하나의 Requirement에 대해
    의미적으로 관련된 Verification 후보를 표현한다.
    """

    requirement_id: str

    verification_ids: list[str]

    mapping_type: Literal[
        "direct",
        "related_variables",
        "no_candidate",
        "ambiguous",
    ]

    rationale: str

    needs_review: bool

    review_reason: str | None


class RequirementVerificationMapping(
    BaseModel
):
    mappings: list[
        RequirementMappingItem
    ]


# =========================================================
# INPUT PREPARATION
# =========================================================

def _prepare_constraint(
    item: dict,
) -> dict:
    """
    Semantic Mapping에 필요한 정보만
    AI에게 전달한다.

    Feasible Domain / Nominal 등은
    Mapping 목적에 필요하지 않으므로 제외한다.
    """

    return {
        "id": item.get(
            "constraint_id"
        ),

        "type": item.get(
            "type"
        ),

        "unit": item.get(
            "unit"
        ),

        "variable": item.get(
            "variable"
        ),

        "min": item.get(
            "min"
        ),

        "max": item.get(
            "max"
        ),

        "left": item.get(
            "left"
        ),

        "right": item.get(
            "right"
        ),

        "variables": item.get(
            "variables",
            [],
        ),

        "limit": item.get(
            "limit"
        ),

        "source_text": item.get(
            "source_text",
            "",
        ),
    }


# =========================================================
# SEMANTIC MAPPING
# =========================================================

def map_requirements_to_verifications(
    requirements: list[dict],
    verifications: list[dict],
) -> list[dict]:
    """
    Requirement와 Verification 사이의
    의미적 대응 후보를 AI가 찾는다.

    중요:
    이 함수는 Verification Sufficiency를
    최종 판정하지 않는다.

    AI는 오직
    '어떤 Verification이 이 Requirement와
    의미적으로 관련되어 있는가?'
    를 판단한다.
    """

    prepared_requirements = [
        _prepare_constraint(
            item
        )
        for item in requirements
    ]

    prepared_verifications = [
        _prepare_constraint(
            item
        )
        for item in verifications
    ]

    requirement_ids = {
        item["id"]
        for item in prepared_requirements
    }

    verification_ids = {
        item["id"]
        for item in prepared_verifications
    }

    input_data = {
        "requirements":
        prepared_requirements,

        "verifications":
        prepared_verifications,
    }

    system_prompt = """
당신은 Engineering Requirement와
Verification Plan 사이의 Semantic Mapping 도구입니다.

목표:

각 Requirement에 대해 의미적으로 관련된
Verification 항목을 찾으십시오.

중요:
당신은 Verification Plan의 충분성을
최종 판정하는 Solver가 아닙니다.

따라서 다음 표현을 최종 확정하지 마십시오.

- 충분하다
- 불충분하다
- 안전하다
- 위험하다
- Requirement가 만족된다
- Gap이 확정되었다

오직 의미적 대응 관계만 분석하십시오.


Mapping Type 정의:

1. direct

Requirement와 Verification이
동일한 공학량 또는 동일한 관계조건을
직접 다루는 경우.

예:

Requirement:
P_out <= 4.8 bar

Verification:
P_out <= 5.0 bar

숫자 범위가 다르더라도
동일한 P_out 제한을 직접 검사하므로
Semantic Mapping은 direct입니다.

충분성 여부는 이후 Solver가 판단합니다.


2. related_variables

Requirement의 변수들은 Verification에서
검사되고 있지만,
Requirement가 요구하는 관계식 자체는
직접 검사되지 않는 경우.

예:

Requirement:
Flow_A + Flow_B <= 21

Verification:
Flow_A range 검사
Flow_B range 검사

이 경우 related_variables입니다.


3. no_candidate

현재 Verification 목록에서
해당 Requirement와 직접 또는 부분적으로
관련된 검사 항목을 찾을 수 없는 경우.


4. ambiguous

문장의 의미가 불명확하거나
여러 Mapping이 가능하여
Engineer 확인이 필요한 경우.


규칙:

- 모든 Requirement를 반드시 한 번씩 분석하십시오.
- 입력에 없는 Requirement ID를 만들지 마십시오.
- 입력에 없는 Verification ID를 만들지 마십시오.
- 하나의 Requirement에 여러 Verification이
  관련될 수 있습니다.
- 숫자가 다르다는 이유만으로
  Semantic Mapping을 끊지 마십시오.
- 같은 변수를 사용한다는 이유만으로
  무조건 direct로 판단하지 마십시오.
- 관계조건 Requirement와
  개별 변수 Verification은
  related_variables가 적절합니다.
- Verification이 전혀 없다면
  no_candidate를 사용하십시오.
- 애매하면 needs_review=true로 설정하십시오.
- 최종 Gap 판정을 하지 마십시오.
"""

    response = client.responses.parse(
        model="gpt-5.6-terra",

        input=[
            {
                "role": "system",
                "content":
                system_prompt,
            },
            {
                "role": "user",
                "content":
                json.dumps(
                    input_data,
                    ensure_ascii=False,
                    indent=2,
                ),
            },
        ],

        text_format=(
            RequirementVerificationMapping
        ),
    )

    parsed = (
        response.output_parsed
    )

    if parsed is None:

        raise RuntimeError(
            "Semantic Mapping 결과가 없습니다."
        )

    results = []

    mapped_requirement_ids = set()

    for mapping in parsed.mappings:

        data = (
            mapping.model_dump()
        )

        requirement_id = data[
            "requirement_id"
        ]

        # -------------------------------------------------
        # 존재하지 않는 Requirement 방어
        # -------------------------------------------------

        if (
            requirement_id
            not in requirement_ids
        ):

            continue

        mapped_requirement_ids.add(
            requirement_id
        )

        # -------------------------------------------------
        # 존재하지 않는 Verification ID 방어
        # -------------------------------------------------

        invalid_verification_ids = [
            verification_id
            for verification_id
            in data[
                "verification_ids"
            ]
            if verification_id
            not in verification_ids
        ]

        if invalid_verification_ids:

            data[
                "needs_review"
            ] = True

            data[
                "review_reason"
            ] = (
                "AI가 존재하지 않는 "
                "Verification ID를 반환했습니다: "
                + ", ".join(
                    invalid_verification_ids
                )
            )

            data[
                "verification_ids"
            ] = [
                verification_id
                for verification_id
                in data[
                    "verification_ids"
                ]
                if verification_id
                in verification_ids
            ]

        results.append(
            data
        )

    # -----------------------------------------------------
    # AI가 Requirement 하나를 누락했을 경우
    # 자동으로 안전 판정하지 않고
    # Engineer Review 대상으로 만든다.
    # -----------------------------------------------------

    missing_requirement_ids = (
        requirement_ids
        - mapped_requirement_ids
    )

    for requirement_id in sorted(
        missing_requirement_ids
    ):

        results.append(
            {
                "requirement_id":
                requirement_id,

                "verification_ids":
                [],

                "mapping_type":
                "ambiguous",

                "rationale":
                (
                    "AI Mapping 결과에서 "
                    "Requirement가 누락되었습니다."
                ),

                "needs_review":
                True,

                "review_reason":
                (
                    "Semantic Mapping 누락"
                ),
            }
        )

    return results
