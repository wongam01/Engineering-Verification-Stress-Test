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
        "difference_min",
        "sum_upper",
        "unsupported",
    ]

    unit: str | None

    # range
    variable: str | None
    min: str | None
    max: str | None

    # difference_min
    left: str | None
    right: str | None

    # sum_upper
    variables: list[str]
    limit: str | None

    # 사람이 다시 확인해야 하는가?
    needs_review: bool

    review_reason: str | None


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

2. difference_min
예:
Y - X >= 20.00

3. sum_upper
예:
A + B <= 30.05

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