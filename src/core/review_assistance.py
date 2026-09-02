from dataclasses import (
    dataclass,
    field,
)

from src.core.correction_history import (
    CorrectionRecord,
    CorrectionSuggestion,
    find_reusable_corrections,
)

from src.core.models import (
    EngineeringCase,
)

from src.core.review_completeness import (
    RequiredReviewTarget,
    build_required_review_targets,
)


# =========================================================
# REVIEW ASSISTANCE ITEM
# =========================================================

@dataclass
class ReviewAssistanceItem:
    """
    하나의 필수 Human Review Target에 대해
    과거 승인 이력을 참고용으로 연결한 결과.

    Suggestion이 존재해도
    현재 Case의 Human Approval을 의미하지 않는다.
    """

    target: RequiredReviewTarget

    source_text: str | None = None

    suggestions: list[
        CorrectionSuggestion
    ] = field(
        default_factory=list
    )

    requires_human_review: bool = True

    @property
    def has_suggestion(self) -> bool:
        return bool(
            self.suggestions
        )


# =========================================================
# REVIEW ASSISTANCE RESULT
# =========================================================

@dataclass
class ReviewAssistanceResult:
    """
    Case 전체 Human Review Checklist에 대한
    Assistance 결과.
    """

    items: list[
        ReviewAssistanceItem
    ] = field(
        default_factory=list
    )

    @property
    def total_targets(self) -> int:
        return len(
            self.items
        )

    @property
    def suggested_target_count(
        self,
    ) -> int:
        return sum(
            1
            for item
            in self.items
            if item.has_suggestion
        )

    @property
    def unassisted_target_count(
        self,
    ) -> int:
        return (
            self.total_targets
            - self.suggested_target_count
        )


# =========================================================
# BUILD REVIEW ASSISTANCE
# =========================================================

def build_review_assistance(
    case: EngineeringCase,
    correction_history: list[
        CorrectionRecord
    ],
    source_text_by_target: dict[
        tuple[str, str],
        str,
    ],
) -> ReviewAssistanceResult:
    """
    필수 Review Target과
    Approved Correction History를 연결한다.

    source_text_by_target key:

        (
            target_type,
            target_id,
        )

    예:

        (
            "variable_mapping",
            "variable:P_out",
        )

        -> "Outlet Pressure"

    중요한 정책:

    - source text를 target_id에서 추측하지 않는다.
    - 과거 기록은 Suggestion만 제공한다.
    - Suggestion은 Human Review Record를 생성하지 않는다.
    - 기존 Human Review Gate를 우회하지 않는다.
    """

    required_targets = (
        build_required_review_targets(
            case
        )
    )

    required_keys = {
        (
            target.target_type,
            target.target_id,
        )
        for target
        in required_targets
    }

    supplied_keys = set(
        source_text_by_target.keys()
    )

    unexpected_keys = (
        supplied_keys
        - required_keys
    )

    if unexpected_keys:
        raise ValueError(
            "Source text was supplied for "
            "an unknown review target: "
            + ", ".join(
                (
                    f"{target_type}/"
                    f"{target_id}"
                )
                for (
                    target_type,
                    target_id,
                )
                in sorted(
                    unexpected_keys
                )
            )
        )

    # -----------------------------------------------------
    # supplied source text validation
    # -----------------------------------------------------

    for (
        key,
        source_text,
    ) in source_text_by_target.items():

        if not isinstance(
            source_text,
            str,
        ):
            raise ValueError(
                "Review source text must "
                "be a string."
            )

        if not source_text.strip():
            raise ValueError(
                "Review source text must "
                "not be empty."
            )

    # -----------------------------------------------------
    # assistance generation
    # -----------------------------------------------------

    items = []

    for target in required_targets:

        key = (
            target.target_type,
            target.target_id,
        )

        source_text = (
            source_text_by_target.get(
                key
            )
        )

        suggestions = []

        if source_text is not None:

            suggestions = (
                find_reusable_corrections(
                    correction_history,
                    target_type=(
                        target.target_type
                    ),
                    source_text=(
                        source_text
                    ),
                )
            )

        items.append(
            ReviewAssistanceItem(
                target=target,
                source_text=source_text,
                suggestions=(
                    suggestions
                ),
                requires_human_review=True,
            )
        )

    return ReviewAssistanceResult(
        items=items
    )