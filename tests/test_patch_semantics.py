import unittest

from src.core.assurance_report import (
    build_assurance_report,
    render_assurance_report,
)

from src.core.json_io import (
    load_engineering_case,
)

from src.core.patch_engine import (
    evaluate_patch_candidates,
    select_practical_patch,
)

from src.core.pipeline import (
    run_pipeline,
)


class PatchSemanticsTest(
    unittest.TestCase
):

    def setUp(self):
        self.case = load_engineering_case(
            "samples/heating_skid_case.json"
        )

    # =====================================================
    # MODEL CLOSURE CANDIDATE
    # =====================================================

    def test_01_selected_patch_is_model_closure_candidate(
        self,
    ):
        evaluations = (
            evaluate_patch_candidates(
                self.case,
                "R2",
            )
        )

        selected = (
            select_practical_patch(
                evaluations
            )
        )

        self.assertIsNotNone(
            selected
        )

        self.assertTrue(
            selected.model_closure_candidate
        )

        self.assertTrue(
            selected.engineering_review_required
        )

        self.assertTrue(
            selected.closes_escape
        )

        self.assertTrue(
            selected.preserves_nominal
        )

    # =====================================================
    # REPORT LANGUAGE
    # =====================================================

    def test_02_report_does_not_claim_practicality(
        self,
    ):
        pipeline_result = run_pipeline(
            self.case,
            generate_patches=True,
        )

        report = build_assurance_report(
            case_name=self.case.name,
            pipeline_result=pipeline_result,
        )

        rendered = (
            render_assurance_report(
                report
            )
        )

        self.assertIn(
            "Mathematical Patch Candidate:",
            rendered,
        )

        self.assertIn(
            "Closes Modeled Escape",
            rendered,
        )

        self.assertIn(
            "Model Closure Candidate",
            rendered,
        )

        self.assertIn(
            "Engineering Review Required",
            rendered,
        )

        self.assertIn(
            "External Feasibility Check : "
            "NOT PERFORMED",
            rendered,
        )

        self.assertNotIn(
            "Practical    :",
            rendered,
        )


if __name__ == "__main__":
    unittest.main()