import unittest
from unittest.mock import patch

from src.core.assurance_report import (
    build_assurance_report,
    render_assurance_report,
)

from src.core.json_io import (
    load_engineering_case,
)

from src.core.pipeline import (
    run_pipeline,
)

from src.core.stress_tester import (
    StressTestResult,
)


class AssuranceSolverIndeterminateTest(
    unittest.TestCase
):

    def setUp(self):
        self.case = load_engineering_case(
            "samples/heating_skid_case.json"
        )

    # =====================================================
    # UNKNOWN ONLY
    # =====================================================

    def test_01_unknown_is_reported_as_indeterminate(
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
            pipeline_result = run_pipeline(
                self.case,
                generate_patches=False,
            )

        report = build_assurance_report(
            case_name=self.case.name,
            pipeline_result=pipeline_result,
        )

        self.assertEqual(
            pipeline_result.status,
            "SOLVER_INDETERMINATE",
        )

        self.assertEqual(
            report.overall_status,
            "INDETERMINATE",
        )

        self.assertFalse(
            report.state_space.escape_found
        )

        self.assertEqual(
            report.state_space.requirements_tested,
            1,
        )

        self.assertEqual(
            report.state_space.escapes_found,
            0,
        )

        self.assertEqual(
            report.state_space.no_escape_found,
            0,
        )

        self.assertTrue(
            report
            .state_space
            .solver_indeterminate_found
        )

        self.assertEqual(
            report
            .state_space
            .solver_indeterminate_count,
            1,
        )

        self.assertEqual(
            report
            .state_space
            .requirement_statuses["R1"],
            "INDETERMINATE",
        )

        self.assertEqual(
            report
            .state_space
            .indeterminate_reasons["R1"],
            "timeout",
        )

        rendered = render_assurance_report(
            report
        )

        self.assertIn(
            "R1 : INDETERMINATE",
            rendered,
        )

        self.assertNotIn(
            "R1 : NO ESCAPE",
            rendered,
        )

        self.assertIn(
            "R1: timeout",
            rendered,
        )

    # =====================================================
    # ESCAPE + UNKNOWN
    # =====================================================

    def test_02_escape_and_unknown_are_both_preserved(
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
            pipeline_result = run_pipeline(
                self.case,
                generate_patches=False,
            )

        report = build_assurance_report(
            case_name=self.case.name,
            pipeline_result=pipeline_result,
        )

        self.assertEqual(
            pipeline_result.status,
            "VERIFICATION_GAP_FOUND",
        )

        self.assertEqual(
            report.overall_status,
            "VERIFICATION_GAP_FOUND",
        )

        self.assertTrue(
            report.state_space.escape_found
        )

        self.assertTrue(
            report
            .state_space
            .solver_indeterminate_found
        )

        self.assertEqual(
            report
            .state_space
            .requirement_statuses["R2"],
            "ESCAPE",
        )

        self.assertEqual(
            report
            .state_space
            .requirement_statuses["R3"],
            "INDETERMINATE",
        )

        self.assertEqual(
            report.state_space.escapes_found,
            1,
        )

        self.assertEqual(
            report
            .state_space
            .solver_indeterminate_count,
            1,
        )

        self.assertEqual(
            report.state_space.no_escape_found,
            0,
        )


if __name__ == "__main__":
    unittest.main()