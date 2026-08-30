import unittest

from src.core.validator import (
    ValidationResult,
)

from src.core.stress_tester import (
    StressTestResult,
)

from src.core.pipeline import (
    PipelineResult,
    RequirementPipelineResult,
)

from src.core.method_case_io import (
    load_method_case,
)

from src.core.assurance_report import (
    StateSpaceEvidence,
    MethodCrossCheckEvidence,
    build_assurance_report,
    determine_assurance_status,
    render_assurance_report,
)


class AssuranceReportTest(
    unittest.TestCase
):

    # =====================================================
    # HELPER
    # =====================================================

    def _make_pipeline_result(
        self,
        escape_found: bool,
    ) -> PipelineResult:

        stress_result = StressTestResult(
            requirement_id="R_TEST",
            requirement_type="range",
            escape_found=escape_found,
            worst_violation=(
                2.5
                if escape_found
                else 0.0
            ),
            state=(
                {
                    "X": 11.0,
                }
                if escape_found
                else {}
            ),
            actual_value=(
                11.0
                if escape_found
                else None
            ),
            direction=(
                "above_maximum"
                if escape_found
                else None
            ),
        )

        requirement_result = (
            RequirementPipelineResult(
                requirement_id="R_TEST",
                stress_result=stress_result,
            )
        )

        status = (
            "VERIFICATION_GAP_FOUND"
            if escape_found
            else "NO_ESCAPE_FOUND"
        )

        return PipelineResult(
            status=status,
            validation=ValidationResult(
                valid=True,
            ),
            requirement_results=[
                requirement_result,
            ],
        )

    # =====================================================
    # 1. CER METHOD RISK
    # =====================================================

    def test_cer_case_builds_method_risk_report(
        self,
    ):

        method_case = load_method_case(
            "samples/cer_dent_method_case.json"
        )

        report = build_assurance_report(
            case_name=(
                method_case.case_name
                or
                method_case.case_id
            ),
            method_case=method_case,
        )

        self.assertEqual(
            report.overall_status,
            "METHOD_RISK_FOUND",
        )

        self.assertFalse(
            report.state_space.evaluated
        )

        self.assertTrue(
            report.method_cross_check.evaluated
        )

        self.assertTrue(
            report
            .method_cross_check
            .disagreement_found
        )

        self.assertTrue(
            report
            .method_cross_check
            .verification_risk_found
        )

        self.assertEqual(
            report.source[
                "benchmark_source"
            ]["document_id"],
            "SRNL-STI-2023-00088",
        )

        rendered = render_assurance_report(
            report
        )

        self.assertIn(
            (
                "INGAA_Table_6: "
                "lower bound 308 years "
                "→ PASS "
                "[current_verification]"
            ),
            rendered,
        )

    # =====================================================
    # 2. STATE-SPACE GAP
    # =====================================================

    def test_state_space_escape_builds_gap_status(
        self,
    ):

        pipeline_result = (
            self._make_pipeline_result(
                escape_found=True,
            )
        )

        report = build_assurance_report(
            case_name="Synthetic Gap Case",
            pipeline_result=pipeline_result,
        )

        self.assertEqual(
            report.overall_status,
            "VERIFICATION_GAP_FOUND",
        )

        self.assertTrue(
            report.state_space.evaluated
        )

        self.assertTrue(
            report.state_space.escape_found
        )

        self.assertFalse(
            report.method_cross_check.evaluated
        )

        self.assertEqual(
            len(
                report.state_space.escapes
            ),
            1,
        )

        escape = (
            report.state_space.escapes[0]
        )

        self.assertEqual(
            escape.requirement_id,
            "R_TEST",
        )

        self.assertEqual(
            escape.worst_violation,
            2.5,
        )

        self.assertEqual(
            escape.state["X"],
            11.0,
        )

    # =====================================================
    # 3. MULTIPLE ASSURANCE ISSUES
    # =====================================================

    def test_gap_and_method_risk_build_multiple_status(
        self,
    ):

        pipeline_result = (
            self._make_pipeline_result(
                escape_found=True,
            )
        )

        method_case = load_method_case(
            "samples/cer_dent_method_case.json"
        )

        report = build_assurance_report(
            case_name="Combined Test Case",
            pipeline_result=pipeline_result,
            method_case=method_case,
        )

        self.assertEqual(
            report.overall_status,
            "MULTIPLE_ASSURANCE_ISSUES",
        )

        self.assertTrue(
            report.state_space.escape_found
        )

        self.assertTrue(
            report
            .method_cross_check
            .verification_risk_found
        )

    # =====================================================
    # 4. NOTHING EVALUATED
    # =====================================================

    def test_no_analysis_returns_not_evaluated(
        self,
    ):

        report = build_assurance_report(
            case_name="Empty Case",
        )

        self.assertEqual(
            report.overall_status,
            "NOT_EVALUATED",
        )

        self.assertFalse(
            report.state_space.evaluated
        )

        self.assertFalse(
            report.method_cross_check.evaluated
        )

    # =====================================================
    # 5. EXECUTED CHECKS FIND NO ISSUE
    # =====================================================

    def test_no_escape_returns_no_issue_status(
        self,
    ):

        pipeline_result = (
            self._make_pipeline_result(
                escape_found=False,
            )
        )

        report = build_assurance_report(
            case_name="No Gap Case",
            pipeline_result=pipeline_result,
        )

        self.assertEqual(
            report.overall_status,
            "NO_ISSUE_FOUND_IN_EXECUTED_CHECKS",
        )

        self.assertTrue(
            report.state_space.evaluated
        )

        self.assertFalse(
            report.state_space.escape_found
        )

    # =====================================================
    # 6. DISAGREEMENT WITHOUT VERIFICATION RISK
    # =====================================================

    def test_method_disagreement_has_distinct_status(
        self,
    ):

        state_space = StateSpaceEvidence(
            evaluated=False,
            pipeline_status="NOT_EVALUATED",
        )

        method_evidence = (
            MethodCrossCheckEvidence(
                evaluated=True,
                disagreement_found=True,
                indeterminate_found=False,
                verification_risk_found=False,
            )
        )

        status = determine_assurance_status(
            state_space,
            method_evidence,
        )

        self.assertEqual(
            status,
            "METHOD_DISAGREEMENT_FOUND",
        )

    # =====================================================
    # 7. INDETERMINATE
    # =====================================================

    def test_indeterminate_has_distinct_status(
        self,
    ):

        state_space = StateSpaceEvidence(
            evaluated=False,
            pipeline_status="NOT_EVALUATED",
        )

        method_evidence = (
            MethodCrossCheckEvidence(
                evaluated=True,
                disagreement_found=False,
                indeterminate_found=True,
                verification_risk_found=False,
            )
        )

        status = determine_assurance_status(
            state_space,
            method_evidence,
        )

        self.assertEqual(
            status,
            "INDETERMINATE",
        )

    # =====================================================
    # 8. INVALID CORE INPUT
    # =====================================================

    def test_invalid_pipeline_input_is_preserved(
        self,
    ):

        pipeline_result = PipelineResult(
            status="INVALID_INPUT",
            validation=ValidationResult(
                valid=False,
            ),
        )

        report = build_assurance_report(
            case_name="Invalid Case",
            pipeline_result=pipeline_result,
        )

        self.assertEqual(
            report.overall_status,
            "INVALID_INPUT",
        )


if __name__ == "__main__":
    unittest.main()
