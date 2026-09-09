from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel


FeasibleEvidenceType = Literal[
    "observed_test_data",
    "manufacturing_record",
    "engineering_analysis",
    "other",
    "unsupported",
]


class FeasibleEvidenceItem(BaseModel):
    """
    One AI-extracted candidate describing an evidence-backed
    feasible operating range for one engineering variable.

    This is NOT a Requirement or Verification constraint.
    It is only a candidate for the Feasible Domain.
    """

    source_line_id: str

    variable: str | None
    min: str | None
    max: str | None
    unit: str | None

    evidence_type: FeasibleEvidenceType

    needs_review: bool
    review_reason: str | None


class DocumentFeasibleEvidenceExtraction(BaseModel):
    evidence: list[FeasibleEvidenceItem]


def _append_review_reason(
    data: dict,
    reason: str,
) -> None:
    current = str(
        data.get("review_reason") or ""
    ).strip()

    if current:
        data["review_reason"] = (
            current + " " + reason
        )
    else:
        data["review_reason"] = reason

    data["needs_review"] = True


def normalize_feasible_evidence(
    item: dict,
) -> dict:
    """
    Deterministic structural guard for an AI Feasible Evidence
    candidate.

    This function does NOT decide whether evidence is true.
    It only verifies that the candidate has a supported,
    machine-readable range structure.
    """

    data = deepcopy(item)

    source_line_id = str(
        data.get("source_line_id") or ""
    ).strip()

    variable = str(
        data.get("variable") or ""
    ).strip()

    unit = str(
        data.get("unit") or ""
    ).strip()

    data["source_line_id"] = source_line_id
    data["variable"] = variable or None
    data["unit"] = unit or None

    if not source_line_id:
        _append_review_reason(
            data,
            "source_line_id가 없습니다.",
        )

    if not variable:
        _append_review_reason(
            data,
            "Engineering variable을 확인할 수 없습니다.",
        )

    if not unit:
        _append_review_reason(
            data,
            "Engineering unit을 확인할 수 없습니다.",
        )

    evidence_type = data.get(
        "evidence_type"
    )

    if evidence_type == "unsupported":
        _append_review_reason(
            data,
            "현재 Feasible Evidence schema로 지원되지 않습니다.",
        )

    numeric_values = {}

    for field_name in (
        "min",
        "max",
    ):
        raw_value = data.get(
            field_name
        )

        if raw_value is None:
            _append_review_reason(
                data,
                f"{field_name} 값이 없습니다.",
            )
            continue

        value = str(
            raw_value
        ).strip()

        if not value:
            _append_review_reason(
                data,
                f"{field_name} 값이 비어 있습니다.",
            )
            continue

        try:
            decimal_value = Decimal(
                value
            )
        except (
            InvalidOperation,
            ValueError,
        ):
            _append_review_reason(
                data,
                f"{field_name} 값이 numeric literal이 아닙니다: {value}",
            )
            continue

        if not decimal_value.is_finite():
            _append_review_reason(
                data,
                f"{field_name} 값은 finite numeric literal이어야 합니다.",
            )
            continue

        numeric_values[
            field_name
        ] = decimal_value

        data[
            field_name
        ] = value

    if {
        "min",
        "max",
    }.issubset(
        numeric_values
    ):
        if (
            numeric_values["min"]
            > numeric_values["max"]
        ):
            _append_review_reason(
                data,
                "Feasible minimum이 maximum보다 큽니다.",
            )

    return data


def finalize_feasible_evidence_items(
    items: list[dict],
    *,
    source_map: dict[str, str],
    source_name: str,
) -> list[dict]:
    """
    Bind AI output back to deterministic source blocks.

    AI does not control source_name or source_text.
    Unknown source_line_id values fail safe into review-required.
    """

    results = []

    for raw_item in items:
        data = normalize_feasible_evidence(
            raw_item
        )

        line_id = data.get(
            "source_line_id",
            "",
        )

        if line_id not in source_map:
            _append_review_reason(
                data,
                "AI가 존재하지 않는 source_line_id를 반환했습니다.",
            )
            source_text = ""
        else:
            source_text = (
                source_map[
                    line_id
                ]
            )

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


def extract_feasible_evidence_from_document(
    text: str,
    source_name: str,
) -> list[dict]:
    """
    Extract candidate Feasible Domain evidence from engineering
    operating/test/manufacturing evidence.

    The PDF bytes are never sent here. Callers provide extracted,
    page-aware text.

    This function creates CANDIDATES only. It never creates an
    EngineeringCase variable and never implies engineer approval.
    """

    # Lazy imports preserve deterministic/unit-test use without
    # requiring an API call when this module is merely imported.
    from src.ai.multi_constraint_parser import (
        prepare_document_lines,
    )
    from src.ai.constraint_parser import (
        client,
    )

    (
        prepared_text,
        source_map,
    ) = prepare_document_lines(
        text
    )

    if not source_map:
        return []

    system_prompt = """
당신은 Engineering Feasible Evidence Extraction 도구입니다.

입력에는 L1, L2, L3 등의 source ID가 붙은
Engineering operating/test/manufacturing evidence 문장이 제공됩니다.

목표는 설계 Requirement나 Inspection Criterion을 추출하는 것이 아니라,
실제로 관측되었거나 시험/생산/운전/공학 분석에 의해 뒷받침되는
Feasible Domain 후보만 추출하는 것입니다.

현재 Phase에서 지원하는 Feasible Evidence는
하나의 engineering variable에 대한 numeric closed range뿐입니다.

출력 필드:

source_line_id
variable
min
max
unit
evidence_type
needs_review
review_reason

evidence_type은 다음 중 하나입니다.

- observed_test_data
- manufacturing_record
- engineering_analysis
- other
- unsupported

추출 가능한 예:

"Measured production hardness ranged from 58 to 60 HRC."

variable = H 또는 원문에 명시된 실제 variable name
min = 58
max = 60
unit = HRC
evidence_type = observed_test_data

또는 단일 관측값:

"Measured hardness H was 59 HRC."

이 경우:
min = 59
max = 59

중요한 규칙:

1. 원문에 없는 숫자를 추측하지 마십시오.
2. 원문에 없는 단위를 추측하지 마십시오.
3. 변수 이름을 임의로 변경하지 마십시오.
4. Requirement를 Feasible Evidence로 사용하지 마십시오.
5. Verification / Acceptance Criterion을 Feasible Evidence로 사용하지 마십시오.
6. Recommended / target / nominal design range를
   Feasible Evidence로 사용하지 마십시오.
7. Instrument measurement range, machine capacity,
   catalog limit, generic capability range를 실제 관측 가능한
   Feasible Domain으로 간주하지 마십시오.
8. 단순 hypothetical example을 실제 evidence로 간주하지 마십시오.
9. 한쪽 bound만 명시된 evidence는 현재 schema에서
   자동 확정하지 말고 unsupported + needs_review=true로 하십시오.
10. relational evidence 또는 여러 변수의 joint relation은
    현재 Phase에서는 unsupported + needs_review=true로 하십시오.
11. min/max에는 반드시 단일 numeric literal만 사용하십시오.
12. source_line_id는 입력에 실제 존재하는 L ID만 사용하십시오.
13. 애매하면 needs_review=true로 하십시오.
14. 이 출력은 Engineer Approval 전의 candidate일 뿐입니다.
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
            DocumentFeasibleEvidenceExtraction
        ),
    )

    parsed = (
        response.output_parsed
    )

    if parsed is None:
        raise RuntimeError(
            "AI Feasible Evidence 추출 결과가 없습니다."
        )

    raw_items = [
        item.model_dump()
        for item in parsed.evidence
    ]

    return finalize_feasible_evidence_items(
        raw_items,
        source_map=source_map,
        source_name=source_name,
    )
