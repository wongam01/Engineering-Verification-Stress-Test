from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any

from src.core.human_review_gate import (
    HumanReviewRecord,
)
from src.core.review_completeness import (
    RequiredReviewTarget,
)


REVIEW_ITEM_LABELS = {
    "variable_mapping": "Variable Mapping",
    "unit": "Engineering Unit",
    "feasible_domain_source": (
        "Feasible Domain Evidence"
    ),
    "inequality_direction": (
        "Inequality Direction"
    ),
    "constraint_meaning": (
        "Constraint Meaning"
    ),
}


REVIEW_TARGET_LABELS = {
    "variable": "Variable",
    "requirement": "Requirement",
    "verification_constraint": (
        "Verification"
    ),
}


ReviewStateSignature = tuple[
    str,
    bool,
]


def format_code_label(
    value: str,
) -> str:
    """
    snake_case status/code를 deterministic한 표시명으로
    변환한다.
    """

    return " ".join(
        value.strip().replace(
            "_",
            " ",
        ).split()
    ).title()


def format_review_target_id(
    target_id: str,
) -> str:
    """
    Core의 exact target ID는 유지하면서 UI 표시만 읽기
    쉬운 형태로 변환한다.
    """

    prefix, separator, identifier = (
        target_id.partition(":")
    )

    if not separator:
        return format_code_label(
            target_id
        )

    prefix_label = (
        REVIEW_TARGET_LABELS.get(
            prefix,
            format_code_label(prefix),
        )
    )

    return (
        f"{prefix_label} · "
        f"{identifier}"
    )


def review_item_label(
    target_type: str,
) -> str:
    return REVIEW_ITEM_LABELS.get(
        target_type,
        format_code_label(
            target_type
        ),
    )


def build_review_summary_rows(
    required_targets: Sequence[
        RequiredReviewTarget
    ],
) -> list[dict[str, str]]:
    """
    모든 exact review target을 생략 없이 UI-ready row로
    표현한다.
    """

    return [
        {
            "Target": (
                format_review_target_id(
                    target.target_id
                )
            ),
            "Review Item": (
                review_item_label(
                    target.target_type
                )
            ),
        }
        for target in required_targets
    ]


def build_exact_approved_review_records(
    required_targets: Sequence[
        RequiredReviewTarget
    ],
    reviewer_reference: str,
    confirmed: bool,
    *,
    reviewed_at: str | None = None,
) -> list[HumanReviewRecord]:
    """
    하나의 명시적 UI 최종 승인을 모든 exact target의
    HumanReviewRecord로 1:1 확장한다.

    reviewer 또는 confirmation이 없으면 빈 기록을 반환해
    기존 Core Human Review Gate가 계속 실행을 차단하게 한다.
    """

    reviewer = (
        reviewer_reference.strip()
    )

    if not reviewer or not confirmed:
        return []

    timestamp = (
        reviewed_at
        if reviewed_at is not None
        else datetime.now(
            timezone.utc
        ).isoformat()
    )

    return [
        HumanReviewRecord(
            target_type=(
                target.target_type
            ),
            target_id=target.target_id,
            decision="approved",
            reviewer_reference=reviewer,
            reviewed_at=timestamp,
            note=(
                "Approved through the "
                "Application UI formal "
                "review workflow."
            ),
        )
        for target in required_targets
    ]


def build_review_state_signature(
    reviewer_reference: str,
    confirmed: bool,
) -> ReviewStateSignature:
    """
    Verification 결과와 결합할 deterministic review state.

    표시상 의미가 없는 주변 공백은 상태 변경으로 취급하지
    않는다.
    """

    return (
        reviewer_reference.strip(),
        bool(confirmed),
    )


def has_review_state_changed(
    executed_state: (
        ReviewStateSignature | None
    ),
    reviewer_reference: str,
    confirmed: bool,
) -> bool:
    return (
        executed_state
        != build_review_state_signature(
            reviewer_reference,
            confirmed,
        )
    )


def format_value_with_unit(
    value: Any,
    unit: str | None,
) -> str:
    rendered = str(value)

    if not unit:
        return rendered

    return rendered + " " + unit
