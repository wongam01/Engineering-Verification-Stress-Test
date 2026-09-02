from src.ai.numeric_normalizer import normalize_numeric_contract

import os

from typing import Literal

from dotenv import load_dotenv

from openai import OpenAI

from pydantic import BaseModel


# =========================================================
# ENVIRONMENT
# =========================================================

load_dotenv(
    dotenv_path=".env"
)

api_key = os.getenv(
    "OPENAI_API_KEY"
)

if not api_key:

    raise RuntimeError(
        "OPENAI_API_KEY를 불러올 수 없습니다."
    )


client = OpenAI(
    api_key=api_key
)


# =========================================================
# AI OUTPUT MODEL
# =========================================================

class ConstraintExtraction(
    BaseModel
):

    """
    AI가 공학 문장에서 추출할
    하나의 Constraint 구조.
    """

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

    # range
    variable: str | None
    min: str | None
    max: str | None

    # difference_min / abs_difference_max
    left: str | None
    right: str | None

    # sum_upper
    variables: list[str]

    # sum_upper / abs_difference_max
    limit: str | None

    # 사람이 다시 확인해야 하는가?
    needs_review: bool
    review_reason: str | None


# =========================================================
# RESULT NORMALIZATION
# =========================================================

def normalize_constraint(
    data: dict,
) -> dict:

    """
    AI가 의미는 올바르게 이해했지만
    threshold 값을 비슷한 다른 필드에 넣은 경우
    Core Schema에 맞게 정규화한다.
    """

    constraint_type = data.get(
        "type"
    )

    # -----------------------------------------------------
    # difference_min
    #
    # left - right >= min
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
# AI CONSTRAINT EXTRACTION
# =========================================================

def extract_constraint(

    text: str,

    constraint_role: Literal[
        "requirement",
        "verification",
    ],

    source_name: str = "manual_input",

) -> dict:

    """
    자연어 Engineering 문장을
    구조화된 Constraint로 변환한다.

    AI는 원문에 명시된 정보만 추출한다.

    Source 정보는 AI에게 생성시키지 않고
    프로그램이 원문 그대로 보존한다.
    """

    system_prompt = """
당신은 Engineering Constraint Extraction 도구입니다.

입력된 공학 문장에서 명시적으로 확인되는 정보만
구조화하십시오.

현재 시스템이 지원하는 Constraint Type은 다음과 같습니다.

1. range

예:
9.95 <= D <= 10.05

필드:
type = range
variable = D
min = 9.95
max = 10.05


2. lower_bound

하나의 변수에 대한 최소 허용값입니다.

수학적 형태:

X >= min

예:

Pressure >= 4 bar

필드:

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

필드:

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

방향성이 있는 최소 차이 조건입니다.

예:
Y - X >= 20.00

또는:
Y는 X보다 최소 20 높아야 한다.

필드:
type = difference_min
left = Y
right = X
min = 20

중요:
difference_min의 기준값은
반드시 min 필드에 넣으십시오.
limit 필드를 사용하지 마십시오.


5. sum_upper

예:
A + B <= 30.05

필드:
type = sum_upper
variables = [A, B]
limit = 30.05


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

필드:
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
방향이 명시된 조건은 abs_difference_max가 아니라
difference_min입니다.


규칙:

- 문서에 없는 숫자를 추측하지 마십시오.
- 문서에 없는 단위를 추측하지 마십시오.
- 변수 이름을 임의로 바꾸지 마십시오.
- Nominal 값을 만들지 마십시오.
- Feasible Domain을 만들지 마십시오.
- 명확하게 지원 형태로 변환할 수 없다면
  type을 unsupported로 설정하십시오.
- 정보가 부족하거나 애매하면
  needs_review를 true로 설정하십시오.
- 숫자는 문자열로 반환하십시오.
- Constraint ID가 원문에 없으면
  constraint_id를 UNSPECIFIED로 설정하고
  needs_review를 true로 설정하십시오.
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
                "content": text,
            },
        ],

        text_format=ConstraintExtraction,

    )

    parsed = response.output_parsed

    if parsed is None:

        raise RuntimeError(
            "AI Constraint 추출 결과가 없습니다."
        )

    result = parsed.model_dump()

    result = normalize_constraint(
        result
    )

    result[
        "constraint_role"
    ] = constraint_role

    result[
        "source_name"
    ] = source_name

    result[
        "source_text"
    ] = text

    return result