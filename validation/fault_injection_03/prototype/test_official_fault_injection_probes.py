import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from src.core.assured_pipeline import (
    run_assured_pipeline,
)
from src.core.correction_history import (
    CorrectionRecord,
    find_reusable_corrections,
)
from src.core.json_io import (
    load_engineering_case,
)
from src.core.models import (
    EngineeringCase,
)
from src.core.pipeline import (
    run_pipeline,
)


ROOT = Path(__file__).resolve().parents[3]


class OfficialFaultInjectionProbeTest(
    unittest.TestCase
):
    def test_t3_03_invalid_input_blocks_core(
        self,
    ):
        data = {
            "name": "T3 Invalid Input Probe",
            "variables": {
                "X": {
                    "unit": "mm",
                    "nominal": Decimal("10.00"),
                    "feasible_min": Decimal("9.50"),
                    "feasible_max": Decimal("10.50"),
                    "verification_min": Decimal("10.10"),
                    "verification_max": Decimal("9.90"),
                }
            },
            "requirements": [],
            "verification_constraints": [],
        }

        case = EngineeringCase.from_dict(data)

        with patch(
            "src.core.pipeline.stress_test_case"
        ) as mocked_solver:
            result = run_pipeline(case)

            mocked_solver.assert_not_called()

        self.assertEqual(
            result.status,
            "INVALID_INPUT",
        )

        self.assertFalse(
            result.validation.valid
        )

    def test_t3_04_missing_evidence_blocks_core(
        self,
    ):
        original = load_engineering_case(
            ROOT / "samples/heating_skid_case.json"
        )

        data = original.to_dict()

        first_variable = next(
            iter(data["variables"].values())
        )

        first_variable.pop(
            "feasible_evidence",
            None,
        )

        case = EngineeringCase.from_dict(data)

        with patch(
            "src.core.assured_pipeline.run_pipeline"
        ) as mocked_core:
            result = run_assured_pipeline(
                case,
                review_records=[],
            )

            mocked_core.assert_not_called()

        self.assertEqual(
            result.status,
            "ASSURANCE_NOT_READY",
        )

        self.assertFalse(
            result.core_executed
        )

        self.assertIsNotNone(
            result.assurance_readiness
        )

        self.assertFalse(
            result.assurance_readiness.ready
        )

    def test_t3_05_incomplete_review_blocks_core(
        self,
    ):
        case = load_engineering_case(
            ROOT / "samples/heating_skid_case.json"
        )

        with patch(
            "src.core.assured_pipeline.run_pipeline"
        ) as mocked_core:
            result = run_assured_pipeline(
                case,
                review_records=[],
            )

            mocked_core.assert_not_called()

        self.assertEqual(
            result.status,
            "HUMAN_REVIEW_BLOCKED",
        )

        self.assertFalse(
            result.core_executed
        )

        self.assertIsNotNone(
            result.human_review
        )

        self.assertFalse(
            result.human_review.ready_for_solver
        )

    def test_t3_08_conflict_requires_review(
        self,
    ):
        records = [
            CorrectionRecord(
                target_type="variable_mapping",
                source_text="Outlet Pressure",
                corrected_value="P_out",
                decision="approved",
                reviewer_reference="engineer_A",
                reviewed_at="2026-08-01",
            ),
            CorrectionRecord(
                target_type="variable_mapping",
                source_text="Outlet Pressure",
                corrected_value="P_discharge",
                decision="approved",
                reviewer_reference="engineer_B",
                reviewed_at="2026-08-20",
            ),
        ]

        suggestions = find_reusable_corrections(
            records,
            target_type="variable_mapping",
            source_text="Outlet Pressure",
        )

        self.assertEqual(
            len(suggestions),
            2,
        )

        values = {
            suggestion.suggested_value
            for suggestion in suggestions
        }

        self.assertEqual(
            values,
            {
                "P_out",
                "P_discharge",
            },
        )

        self.assertTrue(
            all(
                suggestion.requires_human_review
                for suggestion in suggestions
            )
        )


if __name__ == "__main__":
    unittest.main()
