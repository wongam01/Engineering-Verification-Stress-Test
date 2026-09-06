import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.application.escape_execution import (
    run_escape_core_pipeline,
    run_verification_escape_workflow,
)
from src.core.human_review_gate import (
    HumanReviewRecord,
)
from src.core.models import (
    EngineeringCase,
)
from src.core.review_completeness import (
    build_required_review_targets,
)


def build_case(
    feasible_min="58",
    feasible_max="60",
):
    return EngineeringCase.from_dict(
        {
            "name": (
                "Synthetic UI Escape Case"
            ),
            "variables": {
                "H": {
                    "unit": "HRC",
                    "feasible_min": (
                        feasible_min
                    ),
                    "feasible_max": (
                        feasible_max
                    ),
                    "feasible_evidence": {
                        "source_type": (
                            "observed_test_data"
                        ),
                        "source_reference": (
                            "synthetic_test:F_H"
                        ),
                        "approval_status": (
                            "approved"
                        ),
                    },
                },
            },
            "requirements": [
                {
                    "id": "R1",
                    "type": "range",
                    "unit": "HRC",
                    "variable": "H",
                    "min": "50",
                    "max": "57",
                    "description": (
                        "Synthetic hardness requirement"
                    ),
                },
            ],
            "verification_constraints": [
                {
                    "id": "V1",
                    "type": "lower_bound",
                    "unit": "HRC",
                    "variable": "H",
                    "min": "50",
                    "description": (
                        "Synthetic acceptance criterion"
                    ),
                },
            ],
        }
    )


def approved_reviews(
    case,
):
    return [
        HumanReviewRecord(
            target_type=(
                target.target_type
            ),
            target_id=(
                target.target_id
            ),
            decision="approved",
            reviewer_reference=(
                "TEST_REVIEWER"
            ),
            reviewed_at=(
                "2026-09-06T00:00:00+00:00"
            ),
        )
        for target
        in build_required_review_targets(
            case
        )
    ]


class EscapeExecutionTest(
    unittest.TestCase
):
    def test_01_f_and_not_r_is_not_blocked(
        self,
    ):
        case = build_case()

        result = (
            run_verification_escape_workflow(
                case,
                approved_reviews(
                    case
                ),
                generate_patches=False,
            )
        )

        self.assertEqual(
            result.status,
            "VERIFICATION_GAP_FOUND",
        )

        self.assertTrue(
            result.assured_result
            .core_executed
        )

        pipeline = (
            result.assured_result
            .pipeline_result
        )

        self.assertIsNotNone(
            pipeline
        )

        self.assertTrue(
            pipeline.has_escape
        )

        stress = (
            pipeline
            .requirement_results[0]
            .stress_result
        )

        h = stress.state["H"]

        self.assertGreaterEqual(
            h,
            58.0,
        )

        self.assertLessEqual(
            h,
            60.0,
        )

        self.assertGreaterEqual(
            h,
            50.0,
        )

        self.assertFalse(
            50.0 <= h <= 57.0
        )

    def test_02_missing_review_blocks_execution(
        self,
    ):
        case = build_case()

        result = (
            run_verification_escape_workflow(
                case,
                [],
                generate_patches=False,
            )
        )

        self.assertEqual(
            result.status,
            "HUMAN_REVIEW_BLOCKED",
        )

        self.assertFalse(
            result.assured_result
            .core_executed
        )

    def test_03_no_escape_is_preserved(
        self,
    ):
        case = build_case(
            feasible_min="50",
            feasible_max="57",
        )

        result = (
            run_verification_escape_workflow(
                case,
                approved_reviews(
                    case
                ),
                generate_patches=False,
            )
        )

        self.assertEqual(
            result.status,
            "NO_ESCAPE_FOUND",
        )

        self.assertFalse(
            result.assured_result
            .pipeline_result
            .has_escape
        )

    def test_04_unknown_is_not_no_escape(
        self,
    ):
        case = build_case()

        fake_unknown = (
            SimpleNamespace(
                requirement_id="R1",
                requirement_type="range",
                escape_found=False,
                solver_status="UNKNOWN",
            )
        )

        with patch(
            "src.application.escape_execution."
            "stress_test_case",
            return_value=[
                fake_unknown
            ],
        ):
            result = (
                run_escape_core_pipeline(
                    case,
                    generate_patches=False,
                )
            )

        self.assertEqual(
            result.status,
            "SOLVER_INDETERMINATE",
        )

        self.assertTrue(
            result.has_solver_indeterminate
        )


if __name__ == "__main__":
    unittest.main()
