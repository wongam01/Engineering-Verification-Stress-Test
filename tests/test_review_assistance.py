import unittest

from src.core.correction_history import (
    CorrectionRecord,
)

from src.core.human_review_gate import (
    HumanReviewRecord,
)

from src.core.json_io import (
    load_engineering_case,
)

from src.core.review_assistance import (
    build_review_assistance,
)

from src.core.review_completeness import (
    evaluate_case_human_review_gate,
)


class ReviewAssistanceTest(
    unittest.TestCase
):

    def setUp(self):
        self.case = load_engineering_case(
            "samples/heating_skid_case.json"
        )

    # =====================================================
    # COMPLETE CHECKLIST
    # =====================================================

    def test_01_assistance_preserves_all_required_targets(
        self,
    ):
        result = build_review_assistance(
            self.case,
            correction_history=[],
            source_text_by_target={},
        )

        self.assertEqual(
            result.total_targets,
            27,
        )

        self.assertEqual(
            result.suggested_target_count,
            0,
        )

        self.assertEqual(
            result.unassisted_target_count,
            27,
        )

    # =====================================================
    # APPROVED HISTORY SUGGESTION
    # =====================================================

    def test_02_approved_mapping_is_suggested(
        self,
    ):
        history = [
            CorrectionRecord(
                target_type=(
                    "variable_mapping"
                ),
                source_text=(
                    "Outlet Pressure"
                ),
                corrected_value="P_out",
                decision="approved",
                reviewer_reference=(
                    "engineer_A"
                ),
                reviewed_at=(
                    "2026-09-01"
                ),
            )
        ]

        result = build_review_assistance(
            self.case,
            correction_history=history,
            source_text_by_target={
                (
                    "variable_mapping",
                    "variable:P_out",
                ): "Outlet Pressure",
            },
        )

        item = next(
            item
            for item
            in result.items
            if (
                item.target.target_type
                == "variable_mapping"
                and
                item.target.target_id
                == "variable:P_out"
            )
        )

        self.assertTrue(
            item.has_suggestion
        )

        self.assertEqual(
            len(item.suggestions),
            1,
        )

        self.assertEqual(
            item
            .suggestions[0]
            .suggested_value,
            "P_out",
        )

        self.assertTrue(
            item.requires_human_review
        )

    # =====================================================
    # NO SOURCE TEXT GUESSING
    # =====================================================

    def test_03_source_text_is_not_inferred_from_target_id(
        self,
    ):
        history = [
            CorrectionRecord(
                target_type=(
                    "variable_mapping"
                ),
                source_text="P_out",
                corrected_value="P_out",
                decision="approved",
                reviewer_reference=(
                    "engineer_A"
                ),
                reviewed_at=(
                    "2026-09-01"
                ),
            )
        ]

        result = build_review_assistance(
            self.case,
            correction_history=history,
            source_text_by_target={},
        )

        item = next(
            item
            for item
            in result.items
            if (
                item.target.target_type
                == "variable_mapping"
                and
                item.target.target_id
                == "variable:P_out"
            )
        )

        self.assertIsNone(
            item.source_text
        )

        self.assertFalse(
            item.has_suggestion
        )

    # =====================================================
    # CONFLICTING HISTORY
    # =====================================================

    def test_04_conflicting_history_is_preserved(
        self,
    ):
        history = [
            CorrectionRecord(
                target_type=(
                    "variable_mapping"
                ),
                source_text=(
                    "Outlet Pressure"
                ),
                corrected_value="P_out",
                decision="approved",
                reviewer_reference=(
                    "engineer_A"
                ),
                reviewed_at=(
                    "2026-08-01"
                ),
            ),
            CorrectionRecord(
                target_type=(
                    "variable_mapping"
                ),
                source_text=(
                    "Outlet Pressure"
                ),
                corrected_value=(
                    "P_discharge"
                ),
                decision="approved",
                reviewer_reference=(
                    "engineer_B"
                ),
                reviewed_at=(
                    "2026-08-20"
                ),
            ),
        ]

        result = build_review_assistance(
            self.case,
            correction_history=history,
            source_text_by_target={
                (
                    "variable_mapping",
                    "variable:P_out",
                ): "Outlet Pressure",
            },
        )

        item = next(
            item
            for item
            in result.items
            if (
                item.target.target_type
                == "variable_mapping"
                and
                item.target.target_id
                == "variable:P_out"
            )
        )

        values = {
            suggestion.suggested_value
            for suggestion
            in item.suggestions
        }

        self.assertEqual(
            values,
            {
                "P_out",
                "P_discharge",
            },
        )

    # =====================================================
    # TARGET TYPE MUST MATCH
    # =====================================================

    def test_05_history_target_type_must_match(
        self,
    ):
        history = [
            CorrectionRecord(
                target_type="unit",
                source_text=(
                    "Outlet Pressure"
                ),
                corrected_value="bar",
                decision="approved",
                reviewer_reference=(
                    "engineer_A"
                ),
                reviewed_at=(
                    "2026-09-01"
                ),
            )
        ]

        result = build_review_assistance(
            self.case,
            correction_history=history,
            source_text_by_target={
                (
                    "variable_mapping",
                    "variable:P_out",
                ): "Outlet Pressure",
            },
        )

        item = next(
            item
            for item
            in result.items
            if (
                item.target.target_type
                == "variable_mapping"
                and
                item.target.target_id
                == "variable:P_out"
            )
        )

        self.assertFalse(
            item.has_suggestion
        )

    # =====================================================
    # UNKNOWN TARGET SOURCE IS REJECTED
    # =====================================================

    def test_06_unknown_source_target_is_rejected(
        self,
    ):
        with self.assertRaises(
            ValueError
        ):
            build_review_assistance(
                self.case,
                correction_history=[],
                source_text_by_target={
                    (
                        "variable_mapping",
                        "variable:DOES_NOT_EXIST",
                    ): "Fake Variable",
                },
            )

    # =====================================================
    # ASSISTANCE CANNOT BYPASS GATE
    # =====================================================

    def test_07_assistance_does_not_create_approval(
        self,
    ):
        history = [
            CorrectionRecord(
                target_type=(
                    "variable_mapping"
                ),
                source_text=(
                    "Outlet Pressure"
                ),
                corrected_value="P_out",
                decision="approved",
                reviewer_reference=(
                    "engineer_A"
                ),
                reviewed_at=(
                    "2026-09-01"
                ),
            )
        ]

        assistance = (
            build_review_assistance(
                self.case,
                correction_history=history,
                source_text_by_target={
                    (
                        "variable_mapping",
                        "variable:P_out",
                    ): "Outlet Pressure",
                },
            )
        )

        self.assertEqual(
            assistance
            .suggested_target_count,
            1,
        )

        # 중요:
        # Assistance가 있다고 해서
        # HumanReviewRecord를 자동 생성하지 않는다.
        records: list[
            HumanReviewRecord
        ] = []

        gate = (
            evaluate_case_human_review_gate(
                self.case,
                records,
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