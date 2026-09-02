import json
import tempfile
import unittest
from pathlib import Path

from src.core.correction_history import (
    CorrectionRecord,
    find_reusable_corrections,
)

from src.core.correction_history_io import (
    load_correction_history,
    save_correction_history,
)


class CorrectionHistoryIOTest(
    unittest.TestCase
):

    # =====================================================
    # ROUND TRIP
    # =====================================================

    def test_01_save_and_load_round_trip(
        self,
    ):
        records = [
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
                    "2026-09-01T01:00:00+09:00"
                ),
                note=(
                    "Approved project terminology"
                ),
            )
        ]

        with tempfile.TemporaryDirectory() as tmp:

            path = (
                Path(tmp)
                / "history.json"
            )

            save_correction_history(
                path,
                records,
            )

            loaded = (
                load_correction_history(
                    path
                )
            )

        self.assertEqual(
            loaded,
            records,
        )

    # =====================================================
    # REUSE AFTER LOAD
    # =====================================================

    def test_02_loaded_history_can_generate_suggestion(
        self,
    ):
        records = [
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

        with tempfile.TemporaryDirectory() as tmp:

            path = (
                Path(tmp)
                / "history.json"
            )

            save_correction_history(
                path,
                records,
            )

            loaded = (
                load_correction_history(
                    path
                )
            )

        suggestions = (
            find_reusable_corrections(
                loaded,
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
            suggestions[0]
            .suggested_value,
            "P_out",
        )

        self.assertTrue(
            suggestions[0]
            .requires_human_review
        )

    # =====================================================
    # BROKEN JSON
    # =====================================================

    def test_03_broken_json_is_rejected(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:

            path = (
                Path(tmp)
                / "history.json"
            )

            path.write_text(
                "{broken",
                encoding="utf-8",
            )

            with self.assertRaises(
                ValueError
            ):
                load_correction_history(
                    path
                )

    # =====================================================
    # UNKNOWN SCHEMA
    # =====================================================

    def test_04_unknown_schema_is_rejected(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:

            path = (
                Path(tmp)
                / "history.json"
            )

            path.write_text(
                json.dumps(
                    {
                        "schema_version": 999,
                        "records": [],
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaises(
                ValueError
            ):
                load_correction_history(
                    path
                )

    # =====================================================
    # MISSING FIELD
    # =====================================================

    def test_05_missing_required_field_is_rejected(
        self,
    ):
        payload = {
            "schema_version": 1,
            "records": [
                {
                    "target_type": (
                        "variable_mapping"
                    ),
                    "source_text": (
                        "Outlet Pressure"
                    ),
                    "decision": (
                        "approved"
                    ),
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:

            path = (
                Path(tmp)
                / "history.json"
            )

            path.write_text(
                json.dumps(
                    payload
                ),
                encoding="utf-8",
            )

            with self.assertRaises(
                ValueError
            ):
                load_correction_history(
                    path
                )

    # =====================================================
    # UNKNOWN FIELD
    # =====================================================

    def test_06_unknown_record_field_is_rejected(
        self,
    ):
        payload = {
            "schema_version": 1,
            "records": [
                {
                    "target_type": (
                        "variable_mapping"
                    ),
                    "source_text": (
                        "Outlet Pressure"
                    ),
                    "corrected_value": (
                        "P_out"
                    ),
                    "decision": (
                        "approved"
                    ),
                    "hallucinated_field": (
                        "unexpected"
                    ),
                }
            ],
        }

        with tempfile.TemporaryDirectory() as tmp:

            path = (
                Path(tmp)
                / "history.json"
            )

            path.write_text(
                json.dumps(
                    payload
                ),
                encoding="utf-8",
            )

            with self.assertRaises(
                ValueError
            ):
                load_correction_history(
                    path
                )


if __name__ == "__main__":
    unittest.main()