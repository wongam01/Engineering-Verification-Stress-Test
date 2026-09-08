import unittest

from src.application.gap_classification import (
    GapClassification,
    GapClassificationReport,
)
from src.application.result_presentation import (
    build_derived_value_view,
    build_gap_classification_rows,
    format_constraint,
)
from src.core.models import RequirementSpec


class ResultPresentationTest(unittest.TestCase):
    def test_01_difference_min_uses_canonical_min_field(self):
        rendered = format_constraint(
            {
                "type": "difference_min",
                "left": "T_out",
                "right": "T_in",
                "min": "20",
                "limit": None,
                "unit": "degC",
            }
        )

        self.assertEqual(
            rendered,
            "T_out - T_in ≥ 20 degC",
        )

    def test_02_relationship_actual_value_is_human_readable(self):
        requirement = RequirementSpec.from_dict(
            {
                "id": "R_BALANCE",
                "type": "abs_difference_max",
                "unit": "degC",
                "left": "T_A",
                "right": "T_B",
                "limit": "2",
            }
        )

        view = build_derived_value_view(
            requirement,
            5.0,
        )

        self.assertIsNotNone(view)
        self.assertEqual(view.label, "Derived Value")
        self.assertEqual(view.expression, "|T_A - T_B|")
        self.assertEqual(view.value, "5.0 degC")

    def test_03_gap_classification_uses_existing_display_data(self):
        report = GapClassificationReport(
            case_name="Thermal",
            status="CLASSIFIED",
            items=(
                GapClassification(
                    requirement_id="R_BALANCE",
                    status="CLASSIFIED",
                    classification_code=(
                        "RELATIONAL_ACCEPTANCE_BOUNDARY_GAP"
                    ),
                    display_label=(
                        "Relational Acceptance Boundary Gap"
                    ),
                    verification_ids=("V_BALANCE",),
                    missing_verification=False,
                    rationale=(
                        "Verification allows a wider boundary."
                    ),
                    escape_found=True,
                ),
            ),
        )

        rows = build_gap_classification_rows(report)

        self.assertEqual(
            rows,
            [
                {
                    "Requirement": "R_BALANCE",
                    "Status": "Classified",
                    "Classification": (
                        "Relational Acceptance Boundary Gap"
                    ),
                    "Explanation": (
                        "Verification allows a wider boundary."
                    ),
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
