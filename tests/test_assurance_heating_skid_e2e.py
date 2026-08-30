import unittest

from src.core.json_io import (
    load_engineering_case,
)

from src.core.pipeline import (
    run_pipeline,
)

from src.core.assurance_report import (
    build_assurance_report,
    render_assurance_report,
)


class HeatingSkidAssuranceE2ETest(
    unittest.TestCase
):

    def test_heating_skid_full_assurance_flow(
        self,
    ):
        # =================================================
        # INPUT
        # =================================================

        case = load_engineering_case(
            "samples/heating_skid_case.json"
        )

        self.assertEqual(
            case.name,
            "Heating Skid Verification Case",
        )

        # =================================================
        # CORE PIPELINE
        # =================================================

        pipeline_result = run_pipeline(
            case,
            generate_patches=True,
        )

        self.assertEqual(
            pipeline_result.status,
            "VERIFICATION_GAP_FOUND",
        )

        self.assertTrue(
            pipeline_result.has_escape
        )

        # =================================================
        # ASSURANCE REPORT
        # =================================================

        report = build_assurance_report(
            case_name=case.name,
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

        self.assertEqual(
            report.state_space.requirements_tested,
            4,
        )

        self.assertEqual(
            report.state_space.escapes_found,
            3,
        )

        self.assertEqual(
            report.state_space.no_escape_found,
            1,
        )

        # =================================================
        # REQUIREMENT SUMMARY
        # =================================================

        self.assertEqual(
            report.state_space.requirement_statuses,
            {
                "R1": "NO ESCAPE",
                "R2": "ESCAPE",
                "R3": "ESCAPE",
                "R4": "ESCAPE",
            },
        )

        # =================================================
        # ESCAPE DETAILS
        # =================================================

        escapes = {
            escape.requirement_id: escape
            for escape
            in report.state_space.escapes
        }

        self.assertEqual(
            set(escapes),
            {
                "R2",
                "R3",
                "R4",
            },
        )

        self.assertAlmostEqual(
            escapes["R2"].worst_violation,
            10.0,
        )

        self.assertAlmostEqual(
            escapes["R3"].worst_violation,
            0.2,
        )

        self.assertAlmostEqual(
            escapes["R4"].worst_violation,
            3.0,
        )

        # =================================================
        # COUNTEREXAMPLE
        # =================================================

        self.assertAlmostEqual(
            escapes["R2"].state["T_in"],
            85.0,
        )

        self.assertAlmostEqual(
            escapes["R2"].state["T_out"],
            95.0,
        )

        self.assertAlmostEqual(
            escapes["R3"].state["P_out"],
            5.0,
        )

        self.assertAlmostEqual(
            escapes["R4"].state["Flow_A"],
            12.0,
        )

        self.assertAlmostEqual(
            escapes["R4"].state["Flow_B"],
            12.0,
        )

        # =================================================
        # PATCH RE-TEST
        # =================================================

        for escape in escapes.values():
            self.assertTrue(
                escape.selected_patch_closes_escape
            )

            self.assertTrue(
                escape.selected_patch_practical
            )

        # =================================================
        # METHOD CHECK NOT USED
        # =================================================

        self.assertFalse(
            report.method_cross_check.evaluated
        )

        # =================================================
        # HUMAN-READABLE REPORT
        # =================================================

        rendered = render_assurance_report(
            report
        )

        self.assertIn(
            "Requirements Tested : 4",
            rendered,
        )

        self.assertIn(
            "Escapes Found       : 3",
            rendered,
        )

        self.assertIn(
            "R1 : NO ESCAPE",
            rendered,
        )

        self.assertIn(
            "R2 : ESCAPE",
            rendered,
        )

        self.assertIn(
            "Worst Violation: 0.2",
            rendered,
        )

        self.assertIn(
            "VERIFICATION_GAP_FOUND",
            rendered,
        )


if __name__ == "__main__":
    unittest.main()