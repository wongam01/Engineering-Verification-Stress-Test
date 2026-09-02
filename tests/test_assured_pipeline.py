import unittest
from unittest.mock import patch

from src.core.assured_pipeline import (
    run_assured_pipeline,
)

from src.core.human_review_gate import (
    HumanReviewRecord,
)

from src.core.json_io import (
    load_engineering_case,
)

from src.core.review_completeness import (
    build_required_review_targets,
)


def make_approved_records(
    case,
):
    records = []

    for target in (
        build_required_review_targets(
            case
        )
    ):
        records.append(
            HumanReviewRecord(
                target_type=(
                    target.target_type
                ),
                target_id=(
                    target.target_id
                ),
                decision="approved",
                reviewer_reference=(
                    "engineer_demo"
                ),
                reviewed_at=(
                    "2026-08-31T03:00:00+09:00"
                ),
            )
        )

    return records


class AssuredPipelineTest(
    unittest.TestCase
):

    # =====================================================
    # INCOMPLETE REVIEW
    # =====================================================

    def test_01_incomplete_review_blocks_core(
        self,
    ):
        case = load_engineering_case(
            "samples/heating_skid_case.json"
        )

        partial_records = [
            HumanReviewRecord(
                target_type=(
                    "variable_mapping"
                ),
                target_id=(
                    "variable:T_in"
                ),
                decision="approved",
                reviewer_reference=(
                    "engineer_demo"
                ),
                reviewed_at=(
                    "2026-08-31T03:00:00+09:00"
                ),
            )
        ]

        with patch(
            "src.core.assured_pipeline."
            "run_pipeline"
        ) as mocked_pipeline:

            result = run_assured_pipeline(
                case,
                partial_records,
            )

            mocked_pipeline.assert_not_called()

        self.assertFalse(
            result.core_executed
        )

        self.assertEqual(
            result.status,
            "HUMAN_REVIEW_BLOCKED",
        )

        self.assertIsNotNone(
            result.human_review
        )

        self.assertFalse(
            result
            .human_review
            .ready_for_solver
        )

    # =====================================================
    # COMPLETE REVIEW
    # =====================================================

    def test_02_complete_review_runs_core(
        self,
    ):
        case = load_engineering_case(
            "samples/heating_skid_case.json"
        )

        records = (
            make_approved_records(
                case
            )
        )

        result = run_assured_pipeline(
            case,
            records,
            generate_patches=True,
        )

        self.assertTrue(
            result.core_executed
        )

        self.assertEqual(
            result.status,
            "VERIFICATION_GAP_FOUND",
        )

        self.assertIsNotNone(
            result.pipeline_result
        )

        self.assertTrue(
            result
            .human_review
            .ready_for_solver
        )

        self.assertEqual(
            result
            .human_review
            .status,
            "READY_FOR_SOLVER",
        )

    # =====================================================
    # REQUIRED REVIEW COUNT
    # =====================================================

    def test_03_heating_skid_review_checklist(
        self,
    ):
        case = load_engineering_case(
            "samples/heating_skid_case.json"
        )

        targets = (
            build_required_review_targets(
                case
            )
        )

        # 5 variables × 3 review items
        # 4 requirements × 3 review items
        #
        # verification_constraints = 0
        #
        # total = 27

        self.assertEqual(
            len(targets),
            27,
        )

    # =====================================================
    # SINGLE APPROVAL CANNOT BYPASS GATE
    # =====================================================

    def test_04_single_approval_cannot_bypass(
        self,
    ):
        case = load_engineering_case(
            "samples/heating_skid_case.json"
        )

        record = HumanReviewRecord(
            target_type="unit",
            target_id="variable:T_in",
            decision="approved",
            reviewer_reference=(
                "engineer_demo"
            ),
            reviewed_at=(
                "2026-08-31T03:00:00+09:00"
            ),
        )

        result = run_assured_pipeline(
            case,
            [record],
        )

        self.assertFalse(
            result.core_executed
        )

        self.assertEqual(
            result.status,
            "HUMAN_REVIEW_BLOCKED",
        )

        missing = [
            issue
            for issue
            in result.human_review.issues
            if issue.code
            == "REVIEW_REQUIRED"
        ]

        self.assertGreater(
            len(missing),
            0,
        )


if __name__ == "__main__":
    unittest.main()