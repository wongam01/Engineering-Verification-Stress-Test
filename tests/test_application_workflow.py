import unittest

from src.application.models import (
    EvidenceTrace,
)
from src.application.verification_workflow import (
    run_verification_workflow,
)
from src.core.json_io import (
    load_engineering_case,
)
from src.core.models import (
    EngineeringCase,
)


class ApplicationWorkflowTest(
    unittest.TestCase
):
    def setUp(
        self,
    ):
        self.heating_case = (
            load_engineering_case(
                "samples/heating_skid_case.json"
            )
        )

    def test_01_missing_review_is_preserved(
        self,
    ):
        result = run_verification_workflow(
            self.heating_case,
            review_records=[],
            generate_patches=False,
        )

        self.assertEqual(
            result.status,
            "HUMAN_REVIEW_BLOCKED",
        )

        self.assertFalse(
            result.core_executed
        )

        self.assertFalse(
            result.has_escape
        )

        self.assertGreater(
            len(
                result
                .required_review_targets
            ),
            0,
        )

        self.assertEqual(
            result
            .assurance_report
            .state_space
            .pipeline_status,
            "NOT_EVALUATED",
        )

    def test_02_external_analysis_is_preserved(
        self,
    ):
        case = EngineeringCase.from_dict(
            {
                "name": (
                    "Application FEA Scope Case"
                ),
                "variables": {},
                "requirements": [
                    {
                        "id": "R_FEA",
                        "type": "fea",
                        "unit": "MPa",
                    }
                ],
                "verification_constraints": [],
            }
        )

        result = run_verification_workflow(
            case,
            review_records=[],
            generate_patches=False,
        )

        self.assertEqual(
            result.status,
            "EXTERNAL_ANALYSIS_REQUIRED",
        )

        self.assertFalse(
            result.core_executed
        )

        self.assertFalse(
            result.has_escape
        )

    def test_03_evidence_trace_is_preserved(
        self,
    ):
        case = EngineeringCase.from_dict(
            {
                "name": (
                    "Application Evidence Case"
                ),
                "variables": {},
                "requirements": [
                    {
                        "id": "R_FEA",
                        "type": "fea",
                        "unit": "MPa",
                    }
                ],
                "verification_constraints": [],
            }
        )

        trace = EvidenceTrace(
            role="requirement",
            target_id="R_FEA",
            source_name="design_spec.pdf",
            source_text=(
                "Stress shall be evaluated "
                "using finite element analysis."
            ),
            source_page=12,
            source_block_id="L4",
            source_reference=(
                "design_spec.pdf:p12:L4"
            ),
        )

        result = run_verification_workflow(
            case,
            review_records=[],
            evidence=[trace],
            generate_patches=False,
        )

        self.assertEqual(
            len(result.evidence),
            1,
        )

        self.assertEqual(
            result.evidence[0],
            trace,
        )

        summary = result.to_dict()

        self.assertEqual(
            summary["evidence"][0][
                "source_page"
            ],
            12,
        )

        self.assertEqual(
            summary["evidence"][0][
                "source_block_id"
            ],
            "L4",
        )

    def test_04_summary_does_not_rerun_core(
        self,
    ):
        result = run_verification_workflow(
            self.heating_case,
            review_records=[],
            generate_patches=False,
        )

        first_status = result.status

        summary = result.to_dict()

        self.assertEqual(
            summary["status"],
            first_status,
        )

        self.assertFalse(
            summary["core_executed"]
        )


if __name__ == "__main__":
    unittest.main()
