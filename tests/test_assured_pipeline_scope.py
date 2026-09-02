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

from src.core.models import (
    EngineeringCase,
    RequirementSpec,
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


class AssuredPipelineScopeTest(
    unittest.TestCase
):

    # =====================================================
    # FEA
    # =====================================================

    def test_01_fea_blocks_core(
        self,
    ):
        case = EngineeringCase(
            name="FEA Scope Case",
            variables={},
            requirements=[
                RequirementSpec(
                    id="R_FEA",
                    type="fea",
                    unit="MPa",
                )
            ],
        )

        with patch(
            "src.core.assured_pipeline."
            "run_pipeline"
        ) as mocked_pipeline:

            result = run_assured_pipeline(
                case,
                review_records=[],
            )

            mocked_pipeline.assert_not_called()

        self.assertFalse(
            result.core_executed
        )

        self.assertEqual(
            result.status,
            "EXTERNAL_ANALYSIS_REQUIRED",
        )

        self.assertFalse(
            result.scope_assessment.supported
        )

        self.assertIsNone(
            result.assurance_readiness
        )

        self.assertIsNone(
            result.human_review
        )

    # =====================================================
    # UNKNOWN CONSTRAINT
    # =====================================================

    def test_02_unknown_constraint_blocks_core(
        self,
    ):
        case = EngineeringCase(
            name="Unsupported Scope Case",
            variables={},
            requirements=[
                RequirementSpec(
                    id="R_UNKNOWN",
                    type="custom_geometry_rule",
                    unit="mm",
                )
            ],
        )

        with patch(
            "src.core.assured_pipeline."
            "run_pipeline"
        ) as mocked_pipeline:

            result = run_assured_pipeline(
                case,
                review_records=[],
            )

            mocked_pipeline.assert_not_called()

        self.assertFalse(
            result.core_executed
        )

        self.assertEqual(
            result.status,
            "UNSUPPORTED_CONSTRAINT",
        )

        self.assertFalse(
            result.scope_assessment.supported
        )

    # =====================================================
    # SUPPORTED CASE STILL RUNS
    # =====================================================

    def test_03_heating_skid_runs_after_scope_check(
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
            result.scope_assessment.supported
        )

        self.assertEqual(
            result.scope_assessment.status,
            "AUTOMATED_STRESS_TEST_SUPPORTED",
        )

        self.assertTrue(
            result.assurance_readiness.ready
        )

        self.assertTrue(
            result.human_review.ready_for_solver
        )

        self.assertTrue(
            result.core_executed
        )

        self.assertEqual(
            result.status,
            "VERIFICATION_GAP_FOUND",
        )


if __name__ == "__main__":
    unittest.main()