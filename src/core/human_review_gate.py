from dataclasses import dataclass, field


# =========================================================
# ALLOWED VALUES
# =========================================================

ALLOWED_REVIEW_TARGETS = {
    "variable_mapping",
    "unit",
    "inequality_direction",
    "constraint_meaning",
    "feasible_domain_source",
}

ALLOWED_REVIEW_DECISIONS = {
    "approved",
    "unreviewed",
    "rejected",
}


# =========================================================
# REVIEW RECORD
# =========================================================

@dataclass(frozen=True)
class HumanReviewRecord:
    """
    AI가 구조화한 Engineering 정보에 대해
    엔지니어가 수행한 하나의 검토 기록.

    reviewer_reference는 실제 제품에서는
    사내 사용자 ID 또는 승인자 식별자로
    연결할 수 있다.
    """

    target_type: str
    target_id: str

    decision: str = "unreviewed"

    reviewer_reference: str | None = None
    reviewed_at: str | None = None

    note: str | None = None


# =========================================================
# REVIEW ISSUE
# =========================================================

@dataclass(frozen=True)
class HumanReviewIssue:
    """
    Solver 투입 전에 해결해야 하는
    Human Review 문제.
    """

    target_type: str
    target_id: str

    code: str
    message: str


# =========================================================
# GATE RESULT
# =========================================================

@dataclass
class HumanReviewGateResult:
    """
    Human-in-the-Loop 검토가
    Solver 실행 준비 상태인지 나타낸다.
    """

    ready_for_solver: bool

    status: str

    issues: list[
        HumanReviewIssue
    ] = field(
        default_factory=list
    )


# =========================================================
# SINGLE RECORD VALIDATION
# =========================================================

def _check_review_record(
    record: HumanReviewRecord,
) -> list[HumanReviewIssue]:

    issues = []

    # -----------------------------------------------------
    # Target Type
    # -----------------------------------------------------

    if (
        not record.target_type.strip()
        or
        record.target_type
        not in ALLOWED_REVIEW_TARGETS
    ):
        issues.append(
            HumanReviewIssue(
                target_type=record.target_type,
                target_id=record.target_id,
                code="INVALID_REVIEW",
                message=(
                    "Unknown or empty "
                    "review target type."
                ),
            )
        )

    # -----------------------------------------------------
    # Target ID
    # -----------------------------------------------------

    if not record.target_id.strip():
        issues.append(
            HumanReviewIssue(
                target_type=record.target_type,
                target_id=record.target_id,
                code="INVALID_REVIEW",
                message=(
                    "Review target ID "
                    "is empty."
                ),
            )
        )

    # -----------------------------------------------------
    # Decision
    # -----------------------------------------------------

    if (
        record.decision
        not in ALLOWED_REVIEW_DECISIONS
    ):
        issues.append(
            HumanReviewIssue(
                target_type=record.target_type,
                target_id=record.target_id,
                code="INVALID_REVIEW",
                message=(
                    "Unknown review decision: "
                    f"{record.decision}"
                ),
            )
        )

        return issues

    # -----------------------------------------------------
    # Unreviewed
    # -----------------------------------------------------

    if record.decision == "unreviewed":
        issues.append(
            HumanReviewIssue(
                target_type=record.target_type,
                target_id=record.target_id,
                code="REVIEW_REQUIRED",
                message=(
                    "Engineer review "
                    "is still required."
                ),
            )
        )

        return issues

    # -----------------------------------------------------
    # Approved / Rejected에는
    # reviewer traceability가 필요
    # -----------------------------------------------------

    if (
        record.reviewer_reference is None
        or
        not record.reviewer_reference.strip()
    ):
        issues.append(
            HumanReviewIssue(
                target_type=record.target_type,
                target_id=record.target_id,
                code="INVALID_REVIEW",
                message=(
                    "Reviewed item has no "
                    "reviewer reference."
                ),
            )
        )

    if (
        record.reviewed_at is None
        or
        not record.reviewed_at.strip()
    ):
        issues.append(
            HumanReviewIssue(
                target_type=record.target_type,
                target_id=record.target_id,
                code="INVALID_REVIEW",
                message=(
                    "Reviewed item has no "
                    "review timestamp."
                ),
            )
        )

    # -----------------------------------------------------
    # Rejected
    # -----------------------------------------------------

    if record.decision == "rejected":
        issues.append(
            HumanReviewIssue(
                target_type=record.target_type,
                target_id=record.target_id,
                code="REVIEW_REJECTED",
                message=(
                    "Engineer rejected "
                    "the structured result."
                ),
            )
        )

    return issues


# =========================================================
# HUMAN REVIEW GATE
# =========================================================

def evaluate_human_review_gate(
    records: list[HumanReviewRecord],
) -> HumanReviewGateResult:
    """
    모든 Human Review Record를 확인하고
    Solver 투입 가능 여부를 판정한다.

    모든 항목이 유효하게 approved 된 경우에만
    READY_FOR_SOLVER가 된다.
    """

    # -----------------------------------------------------
    # Review Record 자체가 없음
    # -----------------------------------------------------

    if not records:
        issue = HumanReviewIssue(
            target_type="human_review",
            target_id="ALL",
            code="REVIEW_REQUIRED",
            message=(
                "No Human Review records "
                "were provided."
            ),
        )

        return HumanReviewGateResult(
            ready_for_solver=False,
            status="REVIEW_REQUIRED",
            issues=[issue],
        )

    issues = []

    for record in records:
        issues.extend(
            _check_review_record(
                record
            )
        )

    # -----------------------------------------------------
    # 모든 Review 통과
    # -----------------------------------------------------

    if not issues:
        return HumanReviewGateResult(
            ready_for_solver=True,
            status="READY_FOR_SOLVER",
            issues=[],
        )

    codes = {
        issue.code
        for issue in issues
    }

    # -----------------------------------------------------
    # 대표 Status 우선순위
    # -----------------------------------------------------

    if "INVALID_REVIEW" in codes:
        status = "INVALID_REVIEW"

    elif "REVIEW_REJECTED" in codes:
        status = "REVIEW_REJECTED"

    else:
        status = "REVIEW_REQUIRED"

    return HumanReviewGateResult(
        ready_for_solver=False,
        status=status,
        issues=issues,
    )