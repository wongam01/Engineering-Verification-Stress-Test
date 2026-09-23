from src.ai.numeric_normalizer import normalize_numeric_contract

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
        "lower_bound",
        "upper_bound",
        "difference_min",
        "sum_upper",
        "abs_difference_max",
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

    # -----------------------------------------------------
    # PHYSICAL PARAGRAPH PRESERVATION
    #
    # Blank lines are meaningful source boundaries.
    #
    # 같은 paragraph 내부의 physical line wrapping은
    # 하나의 paragraph로 유지하지만,
    # blank line으로 분리된 anonymous paragraph에는
    # 직전 Requirement ID를 자동 상속하지 않는다.
    # -----------------------------------------------------

    paragraphs = []
    current_paragraph = []

    for raw_line in text.splitlines():
        line = raw_line.strip()

        if not line:
            if current_paragraph:
                paragraphs.append(
                    current_paragraph
                )
                current_paragraph = []
            continue

        # [DESIGN SPECIFICATION] 같은
        # bracket-only Section Heading은 제외한다.
        if (
            line.startswith("[")
            and
            line.endswith("]")
        ):
            continue

        current_paragraph.append(
            line
        )

    if current_paragraph:
        paragraphs.append(
            current_paragraph
        )

    if not paragraphs:
        return "", {}

    # -----------------------------------------------------
    # Requirement / Verification 시작 패턴
    #
    # R1.
    # R2:
    # V1.
    # V12)
    # REQ 10:
    # a. [ABC 18]
    # (1) [ABC 29]
    # 등을 인식
    # -----------------------------------------------------

    constraint_start_pattern = re.compile(
        r"^(?:"
        r"[A-Za-z]+\d+\s*[.:)]"
        r"|[A-Z][A-Z0-9_-]{1,15}\s+\d+\s*[.:)]"
        r"|(?:(?:"
        r"[A-Za-z]\s*[.)]"
        r"|\(\d+\)"
        r"|\d+\s*[.)]"
        r")\s*)?"
        r"\[[A-Z][A-Z0-9_-]{1,15}\s+\d+\]"
        r")"
    )

    # -----------------------------------------------------
    # LOGICAL BLOCK BUILDING
    #
    # 핵심 계약:
    #
    # 1. 같은 paragraph의 줄바꿈은 이어 붙인다.
    # 2. explicit ID가 나타나면 새 constraint block.
    # 3. blank-separated anonymous paragraph는
    #    독립 block으로 유지한다.
    # 4. 따라서 anonymous paragraph가 직전
    #    Requirement ID를 강제로 상속하지 않는다.
    # -----------------------------------------------------

    logical_blocks = []

    for paragraph in paragraphs:
        paragraph_blocks = []
        current_block = []

        for line in paragraph:
            starts_new_constraint = bool(
                constraint_start_pattern.match(
                    line
                )
            )

            if starts_new_constraint:
                if current_block:
                    paragraph_blocks.append(
                        current_block
                    )

                current_block = [
                    line
                ]

            else:
                if current_block:
                    current_block.append(
                        line
                    )
                else:
                    current_block = [
                        line
                    ]

        if current_block:
            paragraph_blocks.append(
                current_block
            )

        logical_blocks.extend(
            paragraph_blocks
        )

    # -----------------------------------------------------
    # SYNTHETIC PDF PAGE-BOUNDARY BRIDGE
    #
    # PDF text extraction 과정에서 삽입된
    #
    # ===== PDF PAGE N =====
    #
    # 경계 때문에 하나의 Requirement가
    # 인위적으로 끊어지는 것을 방지한다.
    #
    # 단:
    # - 직전 block이 explicit constraint이고
    # - 직전 문장이 terminal punctuation 없이
    #   페이지 끝에서 끊긴 경우에만 연결한다.
    #
    # 일반 blank-separated anonymous paragraph는
    # 계속 독립 attribution block으로 유지한다.
    #
    # Page marker / header text는 삭제하지 않고
    # source traceability를 위해 source block에 보존한다.
    # -----------------------------------------------------

    page_marker_pattern = re.compile(
        r"^===== PDF PAGE \d+ =====$"
    )

    page_count_pattern = re.compile(
        r"^(?:Page\s+)?"
        r"\d+\s*(?:of|/)\s*\d+$",
        re.IGNORECASE,
    )

    terminal_punctuation = (
        ".",
        "?",
        "!",
    )

    merged_logical_blocks = []

    block_index = 0

    while block_index < len(
        logical_blocks
    ):
        block = logical_blocks[
            block_index
        ]

        is_page_marker_block = bool(
            block
            and
            page_marker_pattern.match(
                block[0]
            )
        )

        if (
            is_page_marker_block
            and
            merged_logical_blocks
        ):
            previous_block = (
                merged_logical_blocks[-1]
            )

            previous_is_explicit = bool(
                previous_block
                and
                constraint_start_pattern.match(
                    previous_block[0]
                )
            )

            previous_last_line = (
                previous_block[-1].rstrip()
                if previous_block
                else ""
            )

            previous_is_incomplete = bool(
                previous_last_line
                and
                not previous_last_line.endswith(
                    terminal_punctuation
                )
            )

            if (
                previous_is_explicit
                and
                previous_is_incomplete
            ):
                # Page marker block 자체도
                # traceability를 위해 보존한다.
                previous_block.extend(
                    block
                )

                page_count_seen = any(
                    page_count_pattern.match(
                        line.strip()
                    )
                    for line in block
                )

                block_index += 1

                # Page header / page count /
                # 이어지는 semantic continuation을
                # 다음 explicit constraint 직전까지 검사한다.
                while block_index < len(
                    logical_blocks
                ):
                    next_block = (
                        logical_blocks[
                            block_index
                        ]
                    )

                    next_is_explicit = bool(
                        next_block
                        and
                        constraint_start_pattern.match(
                            next_block[0]
                        )
                    )

                    if next_is_explicit:
                        break

                    previous_block.extend(
                        next_block
                    )

                    if any(
                        page_count_pattern.match(
                            line.strip()
                        )
                        for line in next_block
                    ):
                        page_count_seen = True

                    block_index += 1

                    # Page count를 지난 뒤
                    # 실제 continuation이 완전한 문장으로
                    # 종료되면 bridge를 끝낸다.
                    if (
                        page_count_seen
                        and
                        previous_block
                        and
                        previous_block[-1]
                        .rstrip()
                        .endswith(
                            terminal_punctuation
                        )
                    ):
                        break

                continue

        merged_logical_blocks.append(
            block
        )

        block_index += 1

    logical_blocks = (
        merged_logical_blocks
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

    # -----------------------------------------------------
    # abs_difference_max
    #
    # Core 규칙:
    # |left - right| <= limit
    # -----------------------------------------------------

    if (
        constraint_type
        == "abs_difference_max"
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


    data = normalize_numeric_contract(
        data
    )

    return data


# =========================================================
# ROLE-SPECIFIC DISCOVERY LENS
# =========================================================

def build_constraint_role_directive(
    constraint_role: str,
) -> str:
    """
    Narrow candidate discovery to the proposed engineering role.

    This does not establish role truth.
    Role Grounding + Engineer Review remain downstream gates.
    """

    if constraint_role == "requirement":
        return """
현재 Proposed Role Lens는 REQUIREMENT 입니다.

Requirement 후보만 추출하십시오.

Requirement 후보란:
- 설계/기술/제품이 만족해야 하는 명시적 normative condition
- shall, must, required, specification, tolerance 등
  의무 또는 허용범위를 나타내는 조건
- source text 자체가 engineering requirement임을
  뒷받침하는 numeric constraint

다음은 Requirement로 자동 간주하지 마십시오:
- 단순 측정값 또는 관측 결과
- 시험 결과
- inspection / verification / acceptance pass-fail 기준
- target / nominal / recommendation
- 장비 capability
- 단순 operating/control/alarm limit
- 설명을 위한 숫자

Requirement인지 애매하지만 원문에 normative 의미가
일부 존재한다면 candidate로 남길 수 있으나
needs_review=true로 설정하십시오.

단순히 숫자가 있다는 이유만으로 후보를 만들지 마십시오.
"""

    if constraint_role == "verification":
        return """
현재 Proposed Role Lens는 VERIFICATION 입니다.

Verification 후보만 추출하십시오.

Verification 후보란:
- inspection / test / verification / quality-control /
  acceptance 과정에서 합격·불합격 또는 적합성 판정에
  실제로 사용되는 명시적 numeric criterion
- source text 자체가 검사·시험·검증 기준임을
  뒷받침하는 조건

다음은 Verification Criterion으로 자동 간주하지 마십시오:
- 설계 Requirement 자체
- 단순 측정값 또는 관측 결과
- target / nominal / recommendation
- 일반 operating/control/alarm limit
- 장비 capability 또는 measurement range
- 단순히 시험 문서 안에 등장한 숫자

Requirement와 Verification Criterion은 서로 자동으로
동일하다고 간주하지 마십시오.

Verification 역할이 애매하지만 원문에 inspection /
test / acceptance 의미가 일부 존재한다면 candidate로
남길 수 있으나 needs_review=true로 설정하십시오.

단순히 숫자가 있다는 이유만으로 후보를 만들지 마십시오.
"""

    raise ValueError(
        "constraint_role must be requirement or verification."
    )


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

    role_directive = (
        build_constraint_role_directive(
            constraint_role
        )
    )

    system_prompt = f"""
{role_directive}

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


2. lower_bound

하나의 변수에 대한 최소 허용값입니다.

수학적 형태:

X >= min

예:

Pressure >= 4 bar

반드시 다음 필드를 사용하십시오.

type = lower_bound

variable = Pressure

min = 4

중요:

lower_bound의 기준값은 반드시 min 필드에 넣으십시오.

max 또는 limit 필드를 사용하지 마십시오.


3. upper_bound

하나의 변수에 대한 최대 허용값입니다.

수학적 형태:

X <= max

예:

Pressure <= 6 bar

반드시 다음 필드를 사용하십시오.

type = upper_bound

variable = Pressure

max = 6

중요:

upper_bound의 기준값은 반드시 max 필드에 넣으십시오.

min 또는 limit 필드를 사용하지 마십시오.



Numeric field contract:

- min, max, limit에는 반드시 단일 numeric literal만 넣으십시오.
- 일반 decimal 또는 scientific notation을 사용하십시오.
  예: 5, 3.25, 1e-6
- 원문이 1x10-6, 1×10^-6처럼 명확한 scientific notation이면
  숫자 의미를 유지하십시오.
- 다른 engineering quantity와의 관계식은 단일 숫자가 아닙니다.
  예: X >= 1.5 × reference_value
- 이런 관계식을 min/max/limit에 문자열로 넣지 마십시오.
- 현재 지원 schema로 의미를 손실 없이 표현할 수 없다면
  type = unsupported,
  needs_review = true 로 반환하십시오.
- 관계식을 임의의 scalar 값으로 축약하지 마십시오.

4. difference_min

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


5. sum_upper

예:
Flow_A + Flow_B <= 21

반드시 다음 필드를 사용하십시오.

type = sum_upper
variables = [Flow_A, Flow_B]
limit = 21

중요:
sum_upper의 상한값은
반드시 limit 필드에 넣으십시오.



6. abs_difference_max

두 변수 사이의 방향과 무관한
절대 차이의 최대 허용값입니다.

수학적 형태:

|A - B| <= limit

예:

Zone A와 Zone B의 온도차는
4 degC를 초과해서는 안 된다.

또는:

The temperature difference between
Zone A and Zone B shall not exceed 4 degC.

반드시 다음 필드를 사용하십시오.

type = abs_difference_max

left = Zone A

right = Zone B

limit = 4

중요:

abs_difference_max에서는
left와 right 두 변수를 사용하십시오.

상한값은 반드시 limit 필드에 넣으십시오.

min 또는 max 필드를
threshold 저장용으로 사용하지 마십시오.

"Y는 X보다 최소 20 높아야 한다"처럼
방향이 명확한 조건은
difference_min으로 분류하십시오.

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