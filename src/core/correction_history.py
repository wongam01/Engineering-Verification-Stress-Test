from dataclasses import dataclass


# =========================================================
# CORRECTION RECORD
# =========================================================

@dataclass(frozen=True)
class CorrectionRecord:
    """
    Engineer가 과거 Review에서 확인한
    Correction / Mapping 기록.

    decision이 approved인 기록만
    다음 Case의 Review Assistance에 사용한다.
    """

    target_type: str

    source_text: str
    corrected_value: str

    decision: str

    reviewer_reference: str | None = None
    reviewed_at: str | None = None

    note: str | None = None


# =========================================================
# CORRECTION SUGGESTION
# =========================================================

@dataclass(frozen=True)
class CorrectionSuggestion:
    """
    과거 승인 기록에서 가져온
    Review Assistance 제안.

    이 객체 자체는 Human Review 승인을
    의미하지 않는다.
    """

    target_type: str

    source_text: str
    suggested_value: str

    source_reviewer_reference: str
    source_reviewed_at: str

    note: str | None = None

    requires_human_review: bool = True


# =========================================================
# NORMALIZATION
# =========================================================

def normalize_source_text(
    value: str,
) -> str:
    """
    단순한 표현 차이를 줄이기 위한
    lookup normalization.

    의미 추론은 하지 않는다.
    """

    return " ".join(
        value
        .casefold()
        .split()
    )


# =========================================================
# REUSABLE APPROVED RECORD
# =========================================================

def is_reusable_approved_correction(
    record: CorrectionRecord,
) -> bool:
    """
    다음 Review에 참고할 수 있는
    과거 승인 기록인지 확인한다.
    """

    if record.decision != "approved":
        return False

    if not record.target_type.strip():
        return False

    if not record.source_text.strip():
        return False

    if not record.corrected_value.strip():
        return False

    if (
        record.reviewer_reference is None
        or
        not record.reviewer_reference.strip()
    ):
        return False

    if (
        record.reviewed_at is None
        or
        not record.reviewed_at.strip()
    ):
        return False

    return True


# =========================================================
# FIND REUSABLE CORRECTIONS
# =========================================================

def find_reusable_corrections(
    records: list[CorrectionRecord],
    target_type: str,
    source_text: str,
) -> list[CorrectionSuggestion]:
    """
    과거 승인 기록 중에서
    같은 Review Target Type과
    같은 정규화된 Source Text를 찾는다.

    반환값은 Approval이 아니라
    Human Review용 Suggestion이다.

    서로 다른 approved value가 존재하면
    임의로 하나를 선택하지 않고
    모두 반환한다.
    """

    normalized_source = (
        normalize_source_text(
            source_text
        )
    )

    suggestions = []

    for record in records:

        if not (
            is_reusable_approved_correction(
                record
            )
        ):
            continue

        if (
            record.target_type
            != target_type
        ):
            continue

        if (
            normalize_source_text(
                record.source_text
            )
            != normalized_source
        ):
            continue

        suggestions.append(
            CorrectionSuggestion(
                target_type=(
                    record.target_type
                ),
                source_text=(
                    source_text
                ),
                suggested_value=(
                    record.corrected_value
                ),
                source_reviewer_reference=(
                    record.reviewer_reference
                ),
                source_reviewed_at=(
                    record.reviewed_at
                ),
                note=record.note,
                requires_human_review=True,
            )
        )

    return suggestions