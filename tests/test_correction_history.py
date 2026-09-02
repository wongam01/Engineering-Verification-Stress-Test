import unittest

from src.core.correction_history import (
    CorrectionRecord,
    find_reusable_corrections,
    normalize_source_text,
)

from src.core.json_io import (
    load_engineering_case,
)

from src.core.review_completeness import (
    evaluate_case_human_review_gate,
)


class CorrectionHistoryTest(
    unittest.TestCase
):

    # =====================================================
    # APPROVED MAPPING
    # =====================================================

    def test_01_approved_mapping_is_reusable(
        self,
    ):
        records = [
            CorrectionRecord(
                target_type="variable_mapping",
                source_text="Outlet Pressure",
                corrected_value="P_out",
                decision="approved",
                reviewer_reference="engineer_A",
                reviewed_at=(
                    "2026-09-01T01:00:00+09:00"
                ),
            )
        ]

        suggestions = (
            find_reusable_corrections(
                records,
                target_type=(
                    "variable_mapping"
                ),
                source_text=(
                    "Outlet Pressure"
                ),
            )
        )

        self.assertEqual(
            len(suggestions),
            1,
        )

        self.assertEqual(
            suggestions[0].suggested_value,
            "P_out",
        )

    # =====================================================
    # NORMALIZATION
    # =====================================================

    def test_02_minor_text_format_difference_matches(
        self,
    ):
        records = [
            CorrectionRecord(
                target_type="variable_mapping",
                source_text=(
                    "Outlet   Pressure"
                ),
                corrected_value="P_out",
                decision="approved",
                reviewer_reference="engineer_A",
                reviewed_at="2026-09-01",
            )
        ]

        suggestions = (
            find_reusable_corrections(
                records,
                target_type=(
                    "variable_mapping"
                ),
                source_text=(
                    "  outlet pressure  "
                ),
            )
        )

        self.assertEqual(
            len(suggestions),
            1,
        )

        self.assertEqual(
            normalize_source_text(
                "Outlet   Pressure"
            ),
            "outlet pressure",
        )

    # =====================================================
    # UNREVIEWED
    # =====================================================

    def test_03_unreviewed_record_is_not_reused(
        self,
    ):
        records = [
            CorrectionRecord(
                target_type="unit",
                source_text="Pressure",
                corrected_value="bar",
                decision="unreviewed",
                reviewer_reference="engineer_A",
                reviewed_at="2026-09-01",
            )
        ]

        suggestions = (
            find_reusable_corrections(
                records,
                target_type="unit",
                source_text="Pressure",
            )
        )

        self.assertEqual(
            suggestions,
            [],
        )

    # =====================================================
    # REJECTED
    # =====================================================

    def test_04_rejected_record_is_not_reused(
        self,
    ):
        records = [
            CorrectionRecord(
                target_type="unit",
                source_text="Pressure",
                corrected_value="psi",
                decision="rejected",
                reviewer_reference="engineer_A",
                reviewed_at="2026-09-01",
            )
        ]

        suggestions = (
            find_reusable_corrections(
                records,
                target_type="unit",
                source_text="Pressure",
            )
        )

        self.assertEqual(
            suggestions,
            [],
        )

    # =====================================================
    # DIFFERENT TARGET TYPE
    # =====================================================

    def test_05_target_type_must_match(
        self,
    ):
        records = [
            CorrectionRecord(
                target_type="variable_mapping",
                source_text="Pressure",
                corrected_value="P_out",
                decision="approved",
                reviewer_reference="engineer_A",
                reviewed_at="2026-09-01",
            )
        ]

        suggestions = (
            find_reusable_corrections(
                records,
                target_type="unit",
                source_text="Pressure",
            )
        )

        self.assertEqual(
            suggestions,
            [],
        )

    # =====================================================
    # CONFLICTING HISTORY
    # =====================================================

    def test_06_conflicting_history_is_not_auto_resolved(
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

        suggestions = (
            find_reusable_corrections(
                records,
                target_type=(
                    "variable_mapping"
                ),
                source_text=(
                    "Outlet Pressure"
                ),
            )
        )

        self.assertEqual(
            len(suggestions),
            2,
        )

        values = {
            suggestion.suggested_value
            for suggestion
            in suggestions
        }

        self.assertEqual(
            values,
            {
                "P_out",
                "P_discharge",
            },
        )

    # =====================================================
    # HUMAN REVIEW IS STILL REQUIRED
    # =====================================================

    def test_07_history_cannot_bypass_human_review_gate(
        self,
    ):
        case = load_engineering_case(
            "samples/heating_skid_case.json"
        )

        history = [
            CorrectionRecord(
                target_type="variable_mapping",
                source_text="Outlet Pressure",
                corrected_value="P_out",
                decision="approved",
                reviewer_reference="engineer_A",
                reviewed_at="2026-08-01",
            )
        ]

        suggestions = (
            find_reusable_corrections(
                history,
                target_type=(
                    "variable_mapping"
                ),
                source_text=(
                    "Outlet Pressure"
                ),
            )
        )

        self.assertEqual(
            len(suggestions),
            1,
        )

        self.assertTrue(
            suggestions[0]
            .requires_human_review
        )

        gate = (
            evaluate_case_human_review_gate(
                case,
                records=[],
            )
        )

        self.assertFalse(
            gate.ready_for_solver
        )

        self.assertEqual(
            gate.status,
            "REVIEW_REQUIRED",
        )


if __name__ == "__main__":
    unittest.main()