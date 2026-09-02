import unittest
from unittest.mock import patch

from src.core.json_io import (
    load_engineering_case,
)

from src.core.pipeline import (
    run_pipeline,
)

from src.core.stress_tester import (
    StressTestResult,
)


class PipelineSolverIndeterminateTest(
    unittest.TestCase
):

    def setUp(self):
        self.case = load_engineering_case(
            "samples/heating_skid_case.json"
        )

    # =====================================================
    # UNKNOWN ONLY
    # =====================================================

    def test_01_unknown_is_not_no_escape(
        self,
    ):
        unknown_result = StressTestResult(
            requirement_id="R1",
            requirement_type="range",
            escape_found=False,
            solver_status="UNKNOWN",
            solver_reason="timeout",
        )

        with patch(
            "src.core.pipeline."
            "stress_test_case",
            return_value=[
                unknown_result
            ],
        ):
            result = run_pipeline(
                self.case,
                generate_patches=False,
            )

        self.assertEqual(
            result.status,
            "SOLVER_INDETERMINATE",
        )

        self.assertFalse(
            result.has_escape
        )

        self.assertTrue(
            result.has_solver_indeterminate
        )

        self.assertNotEqual(
            result.status,
            "NO_ESCAPE_FOUND",
        )

    # =====================================================
    # CONFIRMED ESCAPE + UNKNOWN
    # =====================================================

    def test_02_escape_is_preserved_with_unknown(
        self,
    ):
        escape_result = StressTestResult(
            requirement_id="R2",
            requirement_type=(
                "difference_min"
            ),
            escape_found=True,
            worst_violation=10.0,
            solver_status="SOLVED",
        )

        unknown_result = StressTestResult(
            requirement_id="R3",
            requirement_type="range",
            escape_found=False,
            solver_status="UNKNOWN",
            solver_reason="timeout",
        )

        with patch(
            "src.core.pipeline."
            "stress_test_case",
            return_value=[
                escape_result,
                unknown_result,
            ],
        ):
            result = run_pipeline(
                self.case,
                generate_patches=False,
            )

        self.assertEqual(
            result.status,
            "VERIFICATION_GAP_FOUND",
        )

        self.assertTrue(
            result.has_escape
        )

        self.assertTrue(
            result.has_solver_indeterminate
        )

    # =====================================================
    # NORMAL SOLVED NO ESCAPE
    # =====================================================

    def test_03_solved_no_escape_remains_no_escape(
        self,
    ):
        solved_result = StressTestResult(
            requirement_id="R1",
            requirement_type="range",
            escape_found=False,
            solver_status="SOLVED",
        )

        with patch(
            "src.core.pipeline."
            "stress_test_case",
            return_value=[
                solved_result
            ],
        ):
            result = run_pipeline(
                self.case,
                generate_patches=False,
            )

        self.assertEqual(
            result.status,
            "NO_ESCAPE_FOUND",
        )

        self.assertFalse(
            result.has_escape
        )

        self.assertFalse(
            result.has_solver_indeterminate
        )


if __name__ == "__main__":
    unittest.main()