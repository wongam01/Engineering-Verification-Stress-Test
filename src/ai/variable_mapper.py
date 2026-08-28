import json
from copy import deepcopy

from pydantic import BaseModel

from src.ai.constraint_parser import client


# =========================================================
# VARIABLE MAPPING OUTPUT
# =========================================================

class VariableMappingItem(
    BaseModel
):
    """
    문서에서 추출된 변수 이름 하나를
    Canonical Variable ID에 연결한 결과.
    """

    source_variable: str

    canonical_variable: str | None

    rationale: str

    needs_review: bool

    review_reason: str | None


class VariableMappingOutput(
    BaseModel
):
    mappings: list[
        VariableMappingItem
    ]


# =========================================================
# RAW VARIABLE EXTRACTION
# =========================================================

def get_constraint_variables(
    extraction: dict,
) -> list[str]:
    """
    Constraint Type과 관계없이
    사용된 변수 이름들을 가져온다.
    """

    variables = []

    variable = extraction.get(
        "variable"
    )

    if variable:
        variables.append(
            variable
        )

    left = extraction.get(
        "left"
    )

    if left:
        variables.append(
            left
        )

    right = extraction.get(
        "right"
    )

    if right:
        variables.append(
            right
        )

    for item in extraction.get(
        "variables",
        [],
    ):

        if item:
            variables.append(
                item
            )

    # 중복 제거 + 순서 보존
    return list(
        dict.fromkeys(
            variables
        )
    )


# =========================================================
# CANDIDATE FILTER
# =========================================================

def get_unit_compatible_candidates(
    source_unit: str | None,
    canonical_variables: dict,
) -> dict:
    """
    단위가 명시되어 있으면
    같은 단위의 Canonical Variable만
    AI 후보로 제공한다.

    단위가 없으면 후보를 줄일 수 없으므로
    전체를 반환한다.
    """

    if source_unit is None:

        return canonical_variables

    compatible = {}

    for (
        variable_id,
        info,
    ) in canonical_variables.items():

        if (
            info.get("unit")
            == source_unit
        ):

            compatible[
                variable_id
            ] = info

    return compatible


# =========================================================
# VARIABLE SEMANTIC MAPPING
# =========================================================

def map_constraint_variables(
    extraction: dict,
    canonical_variables: dict,
) -> list[dict]:
    """
    AI가 추출한 문서 변수명을
    Core에서 사용하는 Canonical Variable ID에 연결한다.

    AI에게 모든 변수명을 자유롭게 만들게 하지 않고,
    제공된 Canonical ID 중 하나만 선택하게 한다.
    """

    source_variables = (
        get_constraint_variables(
            extraction
        )
    )

    if not source_variables:

        return []

    source_unit = extraction.get(
        "unit"
    )

    candidates = (
        get_unit_compatible_candidates(
            source_unit=source_unit,
            canonical_variables=canonical_variables,
        )
    )

    # 단위가 맞는 후보가 하나도 없으면
    # AI에게 억지로 Mapping시키지 않는다.
    if not candidates:

        return [
            {
                "source_variable":
                source_variable,

                "canonical_variable":
                None,

                "rationale":
                (
                    "동일 단위의 Canonical Variable "
                    "후보가 없습니다."
                ),

                "needs_review":
                True,

                "review_reason":
                "Unit-compatible candidate 없음",
            }

            for source_variable
            in source_variables
        ]

    input_data = {
        "constraint": {
            "type":
            extraction.get("type"),

            "unit":
            source_unit,

            "source_text":
            extraction.get(
                "source_text",
                "",
            ),

            "source_variables":
            source_variables,
        },

        "canonical_variables":
        candidates,
    }

    system_prompt = """
당신은 Engineering Variable Semantic Mapping 도구입니다.

문서에서 추출된 source_variable을
시스템이 사용하는 Canonical Variable ID와 연결하십시오.

중요 규칙:

- canonical_variable은 제공된 Canonical Variable ID 중에서만 선택하십시오.
- 입력에 없는 Canonical Variable ID를 만들지 마십시오.
- 단순 문자열 유사도만 보지 말고 공학적 의미와 문맥을 고려하십시오.
- 단위를 반드시 고려하십시오.
- 서로 다른 물리량을 억지로 연결하지 마십시오.
- 확실한 대응이 없다면 canonical_variable=null로 설정하십시오.
- 애매하면 needs_review=true로 설정하십시오.
- source_variable은 입력 문자열 그대로 반환하십시오.
- 최종 Engineering 판단을 하지 마십시오.
- Nominal 값이나 Feasible Domain을 생성하지 마십시오.

예:

source_variable:
"Outlet process temperature"

Canonical 후보:
T_out:
"Outlet or discharge process temperature"

이면 T_out으로 연결할 수 있습니다.

반대로 문맥만으로 확실히 구분할 수 없는
Temperature Sensor가 여러 개 존재하면
임의로 선택하지 말고 needs_review=true로 설정하십시오.
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
            VariableMappingOutput
        ),
    )

    parsed = (
        response.output_parsed
    )

    if parsed is None:

        raise RuntimeError(
            "Variable Mapping 결과가 없습니다."
        )

    allowed_ids = set(
        candidates.keys()
    )

    results = []

    returned_sources = set()

    for mapping in parsed.mappings:

        data = (
            mapping.model_dump()
        )

        source_variable = data[
            "source_variable"
        ]

        canonical_variable = data[
            "canonical_variable"
        ]

        # AI가 입력에 없던 Source Variable을
        # 만들어낸 경우 무시
        if (
            source_variable
            not in source_variables
        ):

            continue

        returned_sources.add(
            source_variable
        )

        # AI가 허용되지 않은 Canonical ID를
        # 만들어낸 경우 차단
        if (
            canonical_variable
            is not None
            and
            canonical_variable
            not in allowed_ids
        ):

            data[
                "canonical_variable"
            ] = None

            data[
                "needs_review"
            ] = True

            data[
                "review_reason"
            ] = (
                "AI가 허용되지 않은 "
                "Canonical Variable ID를 반환했습니다."
            )

        results.append(
            data
        )

    # AI가 Source Variable 하나를
    # 누락했으면 자동 승인하지 않는다.
    for source_variable in source_variables:

        if (
            source_variable
            in returned_sources
        ):

            continue

        results.append(
            {
                "source_variable":
                source_variable,

                "canonical_variable":
                None,

                "rationale":
                (
                    "AI Mapping 결과에서 "
                    "변수가 누락되었습니다."
                ),

                "needs_review":
                True,

                "review_reason":
                "Variable Mapping 누락",
            }
        )

    return results


# =========================================================
# APPLY MAPPING
# =========================================================

def apply_variable_mappings(
    extraction: dict,
    mappings: list[dict],
    approved: bool,
) -> dict:
    """
    Engineer가 승인한 Variable Mapping을
    Constraint Extraction 결과에 적용한다.

    원래 AI 추출 결과는 수정하지 않고
    복사본을 반환한다.
    """

    if not approved:

        raise ValueError(
            "Engineer approval이 필요합니다."
        )

    replacement = {}

    for mapping in mappings:

        if mapping.get(
            "needs_review",
            True,
        ):

            raise ValueError(
                "Engineer Review가 필요한 "
                "Variable Mapping이 존재합니다."
            )

        canonical = mapping.get(
            "canonical_variable"
        )

        if canonical is None:

            raise ValueError(
                "Canonical Variable이 없는 "
                "Mapping이 존재합니다."
            )

        replacement[
            mapping[
                "source_variable"
            ]
        ] = canonical

    updated = deepcopy(
        extraction
    )

    variable = updated.get(
        "variable"
    )

    if variable in replacement:

        updated[
            "variable"
        ] = replacement[
            variable
        ]

    left = updated.get(
        "left"
    )

    if left in replacement:

        updated[
            "left"
        ] = replacement[
            left
        ]

    right = updated.get(
        "right"
    )

    if right in replacement:

        updated[
            "right"
        ] = replacement[
            right
        ]

    updated[
        "variables"
    ] = [
        replacement.get(
            variable_name,
            variable_name,
        )

        for variable_name
        in updated.get(
            "variables",
            [],
        )
    ]

    # Traceability용으로
    # Mapping 결과도 같이 보존
    updated[
        "variable_mappings"
    ] = mappings

    return updated