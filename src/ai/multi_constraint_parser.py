import re
from typing import Literal

from pydantic import BaseModel

from src.ai.constraint_parser import client


# =========================================================
# MULTI-CONSTRAINT AI OUTPUT
# =========================================================

class DocumentConstraintItem(
    BaseModel
):
    """
    문서에서 AI가 추출한
    하나의 Engineering Constraint 후보.
    """

    source_line_id: str

    constraint_id: str

    type: Literal[
        "range",
        "difference_min",
        "sum_upper",
        "unsupported",
    ]

    unit: str | None

    # range / difference_min
    variable: str | None
    min: str | None
    max: str | None

    # difference_min
    left: str | None
    right: str | None

    # sum_upper
    variables: list[str]
    limit: str | None

    needs_review: bool
    review_reason: str | None


class DocumentConstraintExtraction(
    BaseModel
):
    constraints: list[
        DocumentConstraintItem
    ]


# =========================================================
# DOCUMENT PREPROCESSING
# =========================================================

def prepare_document_lines(
    text: str,
) -> tuple[
    str,
    dict[str, str],
]:
    """
    실제 문서의 여러 줄을
    Requirement 단위의 논리 문장으로 묶는다.

    예:

    R4. Flow_A와 Flow_B의 합은
    21 L/min 이하여야 한다.

    ↓

    L4:
    R4. Flow_A와 Flow_B의 합은
    21 L/min 이하여야 한다.

    이렇게 하면 AI 추출 결과와
    전체 원문을 연결할 수 있다.
    """

    physical_lines = []

    for raw_line in text.splitlines():

        line = raw_line.strip()

        if not line:
            continue

        # [DESIGN SPECIFICATION] 같은
        # Section Heading 제외
        if (
            line.startswith("[")
            and
            line.endswith("]")
        ):
            continue

        physical_lines.append(
            line
        )

    if not physical_lines:
        return "", {}

    # -----------------------------------------------------
    # Requirement / Verification 시작 패턴
    #
    # R1.
    # R2:
    # V1.
    # V12)
    # 등을 인식
    # -----------------------------------------------------

    constraint_start_pattern = re.compile(
        r"^[A-Za-z]+\d+\s*[\.\:\)]"
    )

    logical_blocks = []

    current_block = []

    for line in physical_lines:

        starts_new_constraint = bool(
            constraint_start_pattern.match(
                line
            )
        )

        if starts_new_constraint:

            if current_block:

                logical_blocks.append(
                    current_block
                )

            current_block = [
                line
            ]

        else:

            if current_block:

                # 이전 Requirement의 계속 문장
                current_block.append(
                    line
                )

            else:

                # ID 없는 독립 문장
                current_block = [
                    line
                ]

    if current_block:

        logical_blocks.append(
            current_block
        )

    # -----------------------------------------------------
    # L1, L2 ... 논리 ID 부여
    # -----------------------------------------------------

    source_map = {}

    prepared_blocks = []

    for index, block in enumerate(
        logical_blocks,
        start=1,
    ):

        line_id = (
            f"L{index}"
        )

        # AI 입력용:
        # 한 줄로 연결해서 의미 파악을 쉽게 함
        ai_text = " ".join(
            block
        )

        # Traceability용:
        # 실제 원문 구조는 줄바꿈 보존
        source_text = "\n".join(
            block
        )

        source_map[
            line_id
        ] = source_text

        prepared_blocks.append(
            f"{line_id}: {ai_text}"
        )

    prepared_text = "\n".join(
        prepared_blocks
    )

    return (
        prepared_text,
        source_map,
    )


# =========================================================
# RESULT NORMALIZATION
# =========================================================

def normalize_constraint(
    data: dict,
) -> dict:
    """
    AI 출력 결과를
    Core와 약속한 Canonical Schema로 정규화한다.

    LLM이 의미는 맞게 이해했지만
    숫자를 유사한 다른 필드에 넣은 경우
    안전하게 정리한다.
    """

    constraint_type = data.get(
        "type"
    )

    # -----------------------------------------------------
    # difference_min
    #
    # Core 규칙:
    # left - right >= min
    #
    # 따라서 threshold는 반드시 min 사용
    # -----------------------------------------------------

    if (
        constraint_type
        == "difference_min"
    ):

        if (
            data.get("min") is None
            and
            data.get("limit") is not None
        ):

            data["min"] = (
                data["limit"]
            )

            data["limit"] = None

    # -----------------------------------------------------
    # sum_upper
    #
    # Core 규칙:
    # sum(variables) <= limit
    # -----------------------------------------------------

    if (
        constraint_type
        == "sum_upper"
    ):

        if (
            data.get("limit") is None
            and
            data.get("max") is not None
        ):

            data["limit"] = (
                data["max"]
            )

            data["max"] = None

    return data


# =========================================================
# MULTI-CONSTRAINT EXTRACTION
# =========================================================

def extract_constraints_from_document(
    text: str,

    constraint_role: Literal[
        "requirement",
        "verification",
    ],

    source_name: str,
) -> list[dict]:
    """
    Engineering 문서에서
    여러 Constraint를 한 번의 AI 호출로 추출한다.

    AI는 명시된 정보만 추출한다.

    원문 Traceability는
    프로그램이 source_line_id를 통해
    직접 연결한다.
    """

    (
        prepared_text,
        source_map,
    ) = prepare_document_lines(
        text
    )

    if not source_map:

        return []

    system_prompt = """
당신은 Engineering Document Constraint Extraction 도구입니다.

입력에는 L1, L2, L3 등의 ID가 붙은
Engineering Requirement 또는 Verification 문장이 제공됩니다.

각 L 항목을 독립적으로 분석하여
명시적으로 존재하는 Engineering Constraint를 추출하십시오.

현재 지원하는 Constraint Type은 다음과 같습니다.

1. range

예:
95 <= T_out <= 105

필드:
type = range
variable = T_out
min = 95
max = 105


2. difference_min

예:
T_out - T_in >= 20

반드시 다음 필드를 사용하십시오.

type = difference_min
left = T_out
right = T_in
min = 20

중요:
difference_min의 기준값은
반드시 min 필드에 넣으십시오.

limit 필드를 사용하지 마십시오.


3. sum_upper

예:
Flow_A + Flow_B <= 21

반드시 다음 필드를 사용하십시오.

type = sum_upper
variables = [Flow_A, Flow_B]
limit = 21

중요:
sum_upper의 상한값은
반드시 limit 필드에 넣으십시오.


규칙:

- 문서에 없는 숫자를 추측하지 마십시오.
- 문서에 없는 단위를 추측하지 마십시오.
- 변수 이름을 임의로 변경하지 마십시오.
- Nominal 값을 만들지 마십시오.
- Feasible Domain을 만들지 마십시오.
- 입력에 없는 Requirement를 생성하지 마십시오.
- source_line_id는 입력에 존재하는 L ID만 사용하십시오.
- 애매하면 needs_review=true로 설정하십시오.
- 지원되지 않는 조건은 type=unsupported로 설정하십시오.
- 숫자는 문자열로 반환하십시오.
- Constraint ID가 명시되어 있지 않다면
  constraint_id=UNSPECIFIED로 설정하고
  needs_review=true로 설정하십시오.
"""

    response = client.responses.parse(
        model="gpt-5.6-terra",

        input=[
            {
                "role": "system",
                "content": system_prompt,
            },
            {
                "role": "user",
                "content": prepared_text,
            },
        ],

        text_format=(
            DocumentConstraintExtraction
        ),
    )

    parsed = (
        response.output_parsed
    )

    if parsed is None:

        raise RuntimeError(
            "AI Document Constraint "
            "추출 결과가 없습니다."
        )

    results = []

    for item in parsed.constraints:

        data = (
            item.model_dump()
        )

        # -------------------------------------------------
        # Core Schema 정규화
        # -------------------------------------------------

        data = normalize_constraint(
            data
        )

        line_id = data[
            "source_line_id"
        ]

        # -------------------------------------------------
        # 존재하지 않는 Source ID 방어
        # -------------------------------------------------

        if line_id not in source_map:

            data[
                "needs_review"
            ] = True

            data[
                "review_reason"
            ] = (
                "AI가 존재하지 않는 "
                "source_line_id를 반환했습니다."
            )

            source_text = ""

        else:

            source_text = (
                source_map[
                    line_id
                ]
            )

        # -------------------------------------------------
        # Role / Source는 AI에게 맡기지 않음
        # -------------------------------------------------

        data[
            "constraint_role"
        ] = constraint_role

        data[
            "source_name"
        ] = source_name

        data[
            "source_text"
        ] = source_text

        results.append(
            data
        )

    return results