import unittest

from src.core.human_review_gate import (
    HumanReviewRecord,
    evaluate_human_review_gate,
)


def approved_record(
    target_type="variable_mapping",
    target_id="T_out",
):
    return HumanReviewRecord(
        target_type=target_type,
        target_id=target_id,
        decision="approved",
        reviewer_reference="engineer_demo",
        reviewed_at="2026-08-31T03:00:00+09:00",
    )


class HumanReviewGateTest(
    unittest.TestCase
):

    # =====================================================
    # ALL APPROVED
    # =====================================================

    def test_01_all_approved_ready_for_solver(
        self,
    ):
        records = [
            approved_record(
                "variable_mapping",
                "T_out",
            ),
            approved_record(
                "unit",
                "T_out:degC",
            ),
            approved_record(
                "inequality_direction",
                "R1",
            ),
            approved_record(
                "constraint_meaning",
                "R1",
            ),
            approved_record(
                "feasible_domain_source",
                "T_out",
            ),
        ]

        result = evaluate_human_review_gate(
            records
        )

        self.assertTrue(
            result.ready_for_solver
        )

        self.assertEqual(
            result.status,
            "READY_FOR_SOLVER",
        )

        self.assertEqual(
            result.issues,
            [],
        )

    # =====================================================
    # UNREVIEWED
    # =====================================================

    def test_02_unreviewed_blocks_solver(
        self,
    ):
        record = HumanReviewRecord(
            target_type="variable_mapping",
            target_id="T_out",
            decision="unreviewed",
        )

        result = evaluate_human_review_gate(
            [record]
        )

        self.assertFalse(
            result.ready_for_solver
        )

        self.assertEqual(
            result.status,
            "REVIEW_REQUIRED",
        )

    # =====================================================
    # REJECTED
    # =====================================================

    def test_03_rejected_blocks_solver(
        self,
    ):
        record = HumanReviewRecord(
            target_type="constraint_meaning",
            target_id="R2",
            decision="rejected",
            reviewer_reference="engineer_demo",
            reviewed_at=(
                "2026-08-31T03:00:00+09:00"
            ),
        )

        result = evaluate_human_review_gate(
            [record]
        )

        self.assertFalse(
            result.ready_for_solver
        )

        self.assertEqual(
            result.status,
            "REVIEW_REJECTED",
        )

    # =====================================================
    # UNKNOWN TARGET
    # =====================================================

    def test_04_unknown_target_is_invalid(
        self,
    ):
        record = approved_record(
            target_type="random_ai_field",
            target_id="X1",
        )

        result = evaluate_human_review_gate(
            [record]
        )

        self.assertFalse(
            result.ready_for_solver
        )

        self.assertEqual(
            result.status,
            "INVALID_REVIEW",
        )

    # =====================================================
    # UNKNOWN DECISION
    # =====================================================

    def test_05_unknown_decision_is_invalid(
        self,
    ):
        record = HumanReviewRecord(
            target_type="unit",
            target_id="P_out:bar",
            decision="yes",
            reviewer_reference="engineer_demo",
            reviewed_at=(
                "2026-08-31T03:00:00+09:00"
            ),
        )

        result = evaluate_human_review_gate(
            [record]
        )

        self.assertFalse(
            result.ready_for_solver
        )

        self.assertEqual(
            result.status,
            "INVALID_REVIEW",
        )

    # =====================================================
    # MISSING REVIEWER
    # =====================================================

    def test_06_approved_without_reviewer_invalid(
        self,
    ):
        record = HumanReviewRecord(
            target_type="unit",
            target_id="P_out:bar",
            decision="approved",
            reviewed_at=(
                "2026-08-31T03:00:00+09:00"
            ),
        )

        result = evaluate_human_review_gate(
            [record]
        )

        self.assertFalse(
            result.ready_for_solver
        )

        self.assertEqual(
            result.status,
            "INVALID_REVIEW",
        )

    # =====================================================
    # EMPTY REVIEW SET
    # =====================================================

    def test_07_empty_review_set_requires_review(
        self,
    ):
        result = evaluate_human_review_gate(
            []
        )

        self.assertFalse(
            result.ready_for_solver
        )

        self.assertEqual(
            result.status,
            "REVIEW_REQUIRED",
        )

    # =====================================================
    # REJECTED HAS PRIORITY OVER UNREVIEWED
    # =====================================================

    def test_08_rejected_and_unreviewed_preserved(
        self,
    ):
        records = [
            HumanReviewRecord(
                target_type="variable_mapping",
                target_id="T_out",
                decision="unreviewed",
            ),
            HumanReviewRecord(
                target_type="constraint_meaning",
                target_id="R2",
                decision="rejected",
                reviewer_reference=(
                    "engineer_demo"
                ),
                reviewed_at=(
                    "2026-08-31T03:00:00+09:00"
                ),
            ),
        ]

        result = evaluate_human_review_gate(
            records
        )

        self.assertFalse(
            result.ready_for_solver
        )

        self.assertEqual(
            result.status,
            "REVIEW_REJECTED",
        )

        codes = {
            issue.code
            for issue in result.issues
        }

        self.assertIn(
            "REVIEW_REQUIRED",
            codes,
        )

        self.assertIn(
            "REVIEW_REJECTED",
            codes,
        )


if __name__ == "__main__":
    unittest.main()