from __future__ import annotations

import re

from decimal import (
    Decimal,
    InvalidOperation,
)
from typing import Any


EXECUTABLE_TYPES = {
    "range",
    "lower_bound",
    "upper_bound",
    "difference_min",
    "sum_upper",
    "abs_difference_max",
}

NUMERIC_FIELDS = (
    "min",
    "max",
    "limit",
)

EXECUTION_FIELDS = (
    "variable",
    "min",
    "max",
    "left",
    "right",
    "variables",
    "limit",
)


# 다음과 같은 engineering scientific notation만
# canonical numeric literal로 변환한다.
#
#   1x10-6
#   1 x 10^-6
#   1×10^-6
#   2.5 * 10^3
#
# 반면:
#
#   1.5xMEOP
#   4xReferencePressure
#
# 같은 engineering relationship은 매칭하지 않는다.
SCIENTIFIC_MULTIPLICATION_PATTERN = re.compile(
    r"""
    ^\s*
    (
        [+-]?
        (?:
            \d+(?:\.\d*)?
            |
            \.\d+
        )
    )
    \s*
    [x×*]
    \s*
    10
    \s*
    (?:\^\s*)?
    \(?
    \s*
    ([+-]?\d+)
    \s*
    \)?
    \s*
    $
    """,
    re.VERBOSE,
)


def _is_finite_decimal(
    text: str,
) -> bool:
    try:
        value = Decimal(
            text
        )
    except (
        InvalidOperation,
        ValueError,
    ):
        return False

    return value.is_finite()


def canonicalize_numeric_literal(
    value: Any,
) -> str | None:
    """
    Core의 Decimal로 안전하게 표현 가능한
    numeric literal만 반환한다.

    반환값이 None이면 자동 실행 가능한
    숫자 literal이라고 판단하지 않는다.
    """

    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        return None

    text = str(
        value
    ).strip()

    if not text:
        return None

    # -----------------------------------------------------
    # 이미 Decimal이 이해하는 일반 numeric literal
    #
    # 5
    # -3.2
    # 1e-6
    # 1E+3
    # -----------------------------------------------------

    if _is_finite_decimal(
        text
    ):
        return text

    # -----------------------------------------------------
    # Engineering-style scientific notation
    #
    # 1x10-6
    # 1×10^-6
    #
    # 만 deterministic하게 변환
    # -----------------------------------------------------

    match = (
        SCIENTIFIC_MULTIPLICATION_PATTERN
        .fullmatch(
            text
        )
    )

    if match is None:
        return None

    coefficient = (
        match.group(1)
    )

    exponent_text = (
        match.group(2)
    )

    if not _is_finite_decimal(
        coefficient
    ):
        return None

    try:
        exponent = int(
            exponent_text
        )
    except ValueError:
        return None

    return (
        f"{coefficient}"
        f"e{exponent}"
    )


def _append_review_reason(
    existing_reason: str | None,
    new_reason: str,
) -> str:
    if not existing_reason:
        return new_reason

    return (
        f"{existing_reason} | "
        f"{new_reason}"
    )


def normalize_numeric_contract(
    data: dict,
) -> dict:
    """
    AI extraction과 deterministic Core 사이의
    numeric contract를 강제한다.

    1. 안전한 numeric literal은 유지한다.
    2. 명확한 scientific notation은 canonicalize한다.
    3. numeric field에 engineering expression이
       들어간 경우 의미를 임의로 축약하지 않고
       unsupported + needs_review로 fail-safe 처리한다.
    """

    constraint_type = (
        data.get(
            "type"
        )
    )

    if (
        constraint_type
        not in EXECUTABLE_TYPES
    ):
        return data

    invalid_fields = []

    for field_name in NUMERIC_FIELDS:
        raw_value = data.get(
            field_name
        )

        if raw_value is None:
            continue

        canonical = (
            canonicalize_numeric_literal(
                raw_value
            )
        )

        if canonical is None:
            invalid_fields.append(
                (
                    field_name,
                    raw_value,
                )
            )
            continue

        data[
            field_name
        ] = canonical

    if not invalid_fields:
        return data

    original_type = (
        constraint_type
    )

    invalid_description = ", ".join(
        (
            f"{field_name}="
            f"{raw_value!r}"
        )
        for (
            field_name,
            raw_value,
        )
        in invalid_fields
    )

    numeric_reason = (
        "Automatic execution blocked because "
        "a supported constraint contained a "
        "non-literal numeric expression "
        f"({invalid_description}). "
        "The engineering expression was not "
        "reduced to a scalar because doing so "
        "could change its meaning. "
        f"Original type: {original_type}."
    )

    data[
        "type"
    ] = "unsupported"

    data[
        "needs_review"
    ] = True

    data[
        "review_reason"
    ] = _append_review_reason(
        data.get(
            "review_reason"
        ),
        numeric_reason,
    )

    # -----------------------------------------------------
    # unsupported 결과가 다시 numeric structure guard에
    # 걸리지 않도록 executable 필드는 제거한다.
    #
    # 원래 expression은 review_reason과 source_text에
    # 그대로 trace된다.
    # -----------------------------------------------------

    for field_name in EXECUTION_FIELDS:
        if field_name == "variables":
            data[
                field_name
            ] = []
        else:
            data[
                field_name
            ] = None

    return data