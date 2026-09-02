from dataclasses import dataclass

from src.core.human_review_gate import (
    HumanReviewGateResult,
    HumanReviewIssue,
    HumanReviewRecord,
    evaluate_human_review_gate,
)

from src.core.models import (
    EngineeringCase,
)


# =========================================================
# REQUIRED REVIEW TARGET
# =========================================================

@dataclass(frozen=True)
class RequiredReviewTarget:
    """
    Solver 실행 전에 반드시
    Human Review가 필요한 항목.
    """

    target_type: str
    target_id: str


# =========================================================
# REQUIRED TARGET GENERATION
# =========================================================

def build_required_review_targets(
    case: EngineeringCase,
) -> list[RequiredReviewTarget]:
    """
    EngineeringCase를 기준으로
    필수 Human Review Checklist를 자동 생성한다.

    Variable:
        - variable_mapping
        - unit
        - feasible_domain_source

    Requirement / Verification Constraint:
        - unit
        - inequality_direction
        - constraint_meaning
    """

    targets = []

    # -----------------------------------------------------
    # VARIABLES
    # -----------------------------------------------------

    for variable_name in case.variables:

        target_id = (
            f"variable:{variable_name}"
        )

        targets.extend(
            [
                RequiredReviewTarget(
                    target_type=(
                        "variable_mapping"
                    ),
                    target_id=target_id,
                ),

                RequiredReviewTarget(
                    target_type="unit",
                    target_id=target_id,
                ),

                RequiredReviewTarget(
                    target_type=(
                        "feasible_domain_source"
                    ),
                    target_id=target_id,
                ),
            ]
        )

    # -----------------------------------------------------
    # REQUIREMENTS
    # -----------------------------------------------------

    for requirement in case.requirements:

        target_id = (
            f"requirement:{requirement.id}"
        )

        targets.extend(
            [
                RequiredReviewTarget(
                    target_type="unit",
                    target_id=target_id,
                ),

                RequiredReviewTarget(
                    target_type=(
                        "inequality_direction"
                    ),
                    target_id=target_id,
                ),

                RequiredReviewTarget(
                    target_type=(
                        "constraint_meaning"
                    ),
                    target_id=target_id,
                ),
            ]
        )

    # -----------------------------------------------------
    # VERIFICATION CONSTRAINTS
    # -----------------------------------------------------

    for constraint in (
        case.verification_constraints
    ):

        target_id = (
            "verification_constraint:"
            f"{constraint.id}"
        )

        targets.extend(
            [
                RequiredReviewTarget(
                    target_type="unit",
                    target_id=target_id,
                ),

                RequiredReviewTarget(
                    target_type=(
                        "inequality_direction"
                    ),
                    target_id=target_id,
                ),

                RequiredReviewTarget(
                    target_type=(
                        "constraint_meaning"
                    ),
                    target_id=target_id,
                ),
            ]
        )

    return targets


# =========================================================
# CASE-LEVEL HUMAN REVIEW GATE
# =========================================================

def evaluate_case_human_review_gate(
    case: EngineeringCase,
    records: list[HumanReviewRecord],
) -> HumanReviewGateResult:
    """
    Case가 요구하는 모든 Review Target과
    실제 Human Review Record를 비교한다.

    단순히 '제공된 기록이 승인됐는가'뿐 아니라
    '필수 기록이 빠지지 않았는가'도 검사한다.
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

    provided_keys = [
        (
            record.target_type,
            record.target_id,
        )
        for record
        in records
    ]

    provided_key_set = set(
        provided_keys
    )

    completeness_issues = []

    # -----------------------------------------------------
    # DUPLICATE RECORD
    # -----------------------------------------------------

    if (
        len(provided_keys)
        != len(provided_key_set)
    ):
        completeness_issues.append(
            HumanReviewIssue(
                target_type=(
                    "human_review"
                ),
                target_id="ALL",
                code="INVALID_REVIEW",
                message=(
                    "Duplicate Human Review "
                    "records were provided."
                ),
            )
        )

    # -----------------------------------------------------
    # MISSING REQUIRED RECORDS
    # -----------------------------------------------------

    missing_keys = (
        required_keys
        - provided_key_set
    )

    for (
        target_type,
        target_id,
    ) in sorted(
        missing_keys
    ):
        completeness_issues.append(
            HumanReviewIssue(
                target_type=target_type,
                target_id=target_id,
                code="REVIEW_REQUIRED",
                message=(
                    "Required Human Review "
                    "record is missing."
                ),
            )
        )

    # -----------------------------------------------------
    # UNEXPECTED RECORDS
    # -----------------------------------------------------

    unexpected_keys = (
        provided_key_set
        - required_keys
    )

    for (
        target_type,
        target_id,
    ) in sorted(
        unexpected_keys
    ):
        completeness_issues.append(
            HumanReviewIssue(
                target_type=target_type,
                target_id=target_id,
                code="INVALID_REVIEW",
                message=(
                    "Unexpected Human Review "
                    "target was provided."
                ),
            )
        )

    # -----------------------------------------------------
    # EXISTING RECORD VALIDATION
    # -----------------------------------------------------

    record_result = (
        evaluate_human_review_gate(
            records
        )
    )

    issues = (
        completeness_issues
        + record_result.issues
    )

    if not issues:
        return HumanReviewGateResult(
            ready_for_solver=True,
            status="READY_FOR_SOLVER",
            issues=[],
        )

    codes = {
        issue.code
        for issue
        in issues
    }

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